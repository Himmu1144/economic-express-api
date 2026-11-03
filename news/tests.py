from datetime import timedelta
from io import BytesIO
from unittest.mock import patch
from PIL import Image
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from .models import (
    Article,
    Author,
    Category,
    DailyViews,
    NewsletterSubscriber,
    Revalidation,
    TickerSnapshot,
)
from .media import optimized_image
from .admin import ArticleAdmin
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory


@override_settings(
    SECURE_SSL_REDIRECT=False,
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    },
)
class BackendTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name="Markets", slug="markets")
        cls.author = Author.objects.create(name="Desk", slug="desk")

    def story(self, **kwargs):
        values = dict(
            title="A story",
            summary="Summary",
            body_html="<p>Body</p>",
            category=self.category,
            author=self.author,
            cover_image="https://images.example.com/cover.jpg",
            cover_alt="Cover",
            cover_caption="Caption",
            status="published",
            published_at=timezone.now() - timedelta(minutes=1),
        )
        values.update(kwargs)
        return Article.objects.create(**values)

    def test_sanitizer_and_derived_fields(self):
        a = self.story(
            body_html='<script>alert(1)</script><p onclick="bad()">Hello</p><img src="https://x.test/a" onerror="bad()"><a href="javascript:bad()">Link</a>'
        )
        self.assertNotIn("script", a.body_html)
        self.assertNotIn("onerror", a.body_html)
        self.assertNotIn("onclick", a.body_html)
        self.assertNotIn("javascript:", a.body_html)
        self.assertEqual(a.reading_time, 1)
        self.assertEqual(a.meta_title, a.title)
        original = a.slug
        a.slug = "changed"
        a.save()
        self.assertEqual(a.slug, original)
        b = self.story()
        self.assertNotEqual(b.slug, a.slug)

    def test_public_visibility_and_soft_delete(self):
        a = self.story()
        draft = self.story(status="draft")
        future = self.story(published_at=timezone.now() + timedelta(minutes=2))
        for obj in [draft, future]:
            self.assertEqual(
                self.client.get(f"/api/articles/{obj.slug}/").status_code, 404
            )
        self.assertEqual(self.client.get("/api/articles/missing/").status_code, 404)
        self.assertEqual(self.client.get("/api/articles/").json()["count"], 1)
        with patch(
            "django.utils.timezone.now",
            return_value=timezone.now() + timedelta(minutes=3),
        ):
            self.assertEqual(
                self.client.get(f"/api/articles/{future.slug}/").status_code, 200
            )
        a.delete()
        self.assertTrue(Article.objects.filter(pk=a.pk).exists())
        self.assertEqual(self.client.get(f"/api/articles/{a.slug}/").status_code, 404)

    def test_home_queries_and_fallbacks(self):
        self.story(is_breaking=True)
        self.story(is_breaking=True, published_at=timezone.now() - timedelta(hours=13))
        for i in range(8):
            c = Category.objects.create(name=f"C{i}", slug=f"c{i}", order=i + 1)
            for j in range(5):
                self.story(category=c, title=f"{i}-{j}", is_explainer=True)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get("/api/home/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["breaking"]), 1)
        self.assertEqual(len(data["latest"]), 8)
        self.assertEqual(len(data["editors_picks"]), 4)
        self.assertEqual(len(data["explained"]), 2)
        self.assertTrue(all(len(s["articles"]) <= 4 for s in data["sections"]))
        self.assertLessEqual(len(queries), 15)

    def test_weekly_views_and_bots(self):
        a = self.story(views=10000)
        b = self.story()
        DailyViews.objects.create(
            article=a, day=timezone.localdate() - timedelta(days=8), count=10000
        )
        DailyViews.objects.create(article=b, day=timezone.localdate(), count=10)
        self.assertEqual(self.client.get("/api/trending/").json()[0]["id"], b.id)
        self.client.post(f"/api/articles/{b.slug}/view/", HTTP_USER_AGENT="Googlebot")
        b.refresh_from_db()
        self.assertEqual(b.views, 0)
        self.client.post(f"/api/articles/{b.slug}/view/", HTTP_USER_AGENT="Mozilla/5.0")
        b.refresh_from_db()
        self.assertEqual(b.views, 1)

    def test_newsletter_duplicate_and_throttle(self):
        for _ in range(5):
            self.assertEqual(
                self.client.post(
                    "/api/newsletter/",
                    {"email": "Desk@Example.com"},
                    content_type="application/json",
                ).status_code,
                200,
            )
        self.assertEqual(NewsletterSubscriber.objects.count(), 1)
        self.assertEqual(
            self.client.post(
                "/api/newsletter/",
                {"email": "a@example.com"},
                content_type="application/json",
            ).status_code,
            429,
        )

    def test_view_throttle(self):
        a = self.story()
        for _ in range(30):
            self.client.post(
                f"/api/articles/{a.slug}/view/", HTTP_USER_AGENT="Mozilla/5.0"
            )
        self.assertEqual(
            self.client.post(f"/api/articles/{a.slug}/view/").status_code, 429
        )

    def test_upload_validation(self):
        with self.assertRaises(ValidationError):
            optimized_image(
                SimpleUploadedFile(
                    "x.png", b'<svg onload="bad()"/>', content_type="image/png"
                )
            )
        image = Image.new("RGB", (2000, 1000))
        out = BytesIO()
        image.save(out, "PNG")
        file = optimized_image(SimpleUploadedFile("x.png", out.getvalue()))
        with Image.open(file) as result:
            self.assertEqual(result.width, 1600)
            self.assertEqual(result.format, "WEBP")
        with self.assertRaises(ValidationError):
            optimized_image(SimpleUploadedFile("x.jpg", b"x" * (5 * 1024 * 1024 + 1)))

    def test_queue_schedule_and_retry(self):
        a = self.story(published_at=timezone.now() + timedelta(minutes=2))
        self.assertTrue(Revalidation.objects.filter(due_at=a.published_at).exists())
        from .signals import deliver_pending

        with (
            override_settings(
                FRONTEND_URL="https://example.test", REVALIDATE_SECRET="test"
            ),
            patch("news.signals.requests.post") as post,
        ):
            deliver_pending()
            self.assertTrue(post.called)
            self.assertTrue(
                Revalidation.objects.filter(delivered_at__isnull=False).exists()
            )
            self.assertTrue(
                Revalidation.objects.filter(
                    due_at=a.published_at, delivered_at__isnull=True
                ).exists()
            )

    def test_ticker_last_good_and_fallback(self):
        response = self.client.get("/api/market/ticker/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["items"]), 7)
        data = response.json()
        data["source"] = "test-last-good"
        TickerSnapshot.objects.create(pk=1, data=data)
        self.assertEqual(
            self.client.get("/api/market/ticker/").json()["source"], "test-last-good"
        )

    def test_writer_permissions(self):
        call_command("seed")
        user = get_user_model().objects.create_user("writer", is_staff=True)
        user.groups.add(Group.objects.get(name="Writer"))
        other = get_user_model().objects.create_user("other", is_staff=True)
        own = self.story(status="draft", created_by=user)
        foreign = self.story(status="draft", created_by=other)
        published = self.story(created_by=user)
        request = RequestFactory().get("/")
        request.user = user
        modeladmin = ArticleAdmin(Article, AdminSite())
        self.assertTrue(modeladmin.has_change_permission(request, own))
        self.assertFalse(modeladmin.has_change_permission(request, foreign))
        self.assertFalse(modeladmin.has_change_permission(request, published))
        self.assertFalse(modeladmin.has_delete_permission(request, own))
        self.assertEqual(list(modeladmin.get_queryset(request)), [own])
        own.status = "published"
        modeladmin.save_model(request, own, None, True)
        self.assertEqual(own.status, "draft")
        self.client.force_login(user)
        self.assertEqual(
            self.client.get(f"/admin/article-preview/{foreign.pk}/").status_code, 403
        )
        response = self.client.get(f"/admin/article-preview/{own.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])

    def test_seed_idempotence(self):
        call_command("seed", demo=True)
        count = Article.objects.count()
        call_command("seed", demo=True)
        self.assertEqual(Article.objects.count(), count)
        self.assertEqual(count, 29)
        self.assertEqual(Category.objects.count(), 9)

    def test_pagination_search_and_tags(self):
        for i in range(15):
            self.story(title=f"Article {i}")
        page = self.client.get("/api/articles/").json()
        self.assertEqual(page["count"], 15)
        self.assertEqual(len(page["results"]), 12)
        self.assertTrue(page["next"])
        self.assertEqual(
            len(self.client.get("/api/articles/?page=2").json()["results"]), 3
        )
        self.assertEqual(
            self.client.get("/api/articles/?search=Article%2014").json()["count"], 1
        )

    def test_admin_login_rate_limit(self):
        for _ in range(5):
            self.client.post(
                "/admin/login/", {"username": "missing", "password": "wrong"}
            )
        self.assertEqual(
            self.client.post(
                "/admin/login/", {"username": "missing", "password": "wrong"}
            ).status_code,
            429,
        )

    def test_admin_uploads_and_writer_list(self):
        from django.contrib.auth.models import Group

        call_command("seed")
        user = get_user_model().objects.create_user("writer-upload", is_staff=True)
        user.groups.add(Group.objects.get(name="Writer"))
        self.client.force_login(user)
        self.assertEqual(self.client.get("/admin/news/article/").status_code, 200)
        self.assertEqual(self.client.get("/admin/news/article/add/").status_code, 200)
        out = BytesIO()
        Image.new("RGB", (1800, 900)).save(out, "PNG")
        response = self.client.post(
            "/admin/inline-upload/",
            {
                "file": SimpleUploadedFile(
                    "image.png", out.getvalue(), content_type="image/png"
                )
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(".webp", response.json()["location"])
        self.assertEqual(
            self.client.post(
                "/admin/inline-upload/",
                {"file": SimpleUploadedFile("bad.png", b"invalid")},
            ).status_code,
            400,
        )

    def test_related_priority_and_key_points(self):
        from .models import Tag

        a = self.story(key_points="One\n\n Two ")
        same = self.story()
        c = Category.objects.create(name="Economy", slug="economy")
        shared = self.story(category=c)
        unrelated = self.story(category=c)
        tag = Tag.objects.create(name="RBI", slug="rbi")
        a.tags.add(tag)
        shared.tags.add(tag)
        result = self.client.get(f"/api/articles/{a.slug}/").json()
        self.assertEqual(result["key_points"], ["One", "Two"])
        self.assertEqual([x["id"] for x in result["related"]], [same.pk, shared.pk])
        self.assertNotIn(unrelated.pk, [x["id"] for x in result["related"]])

    def test_failed_revalidation_retries(self):
        import requests
        from .signals import deliver_pending

        self.story()
        with (
            override_settings(
                FRONTEND_URL="https://example.test", REVALIDATE_SECRET="test"
            ),
            patch("news.signals.requests.post", side_effect=requests.Timeout),
        ):
            deliver_pending()
        self.assertTrue(
            Revalidation.objects.filter(attempts=1, delivered_at__isnull=True).exists()
        )

    def test_yahoo_failure_preserves_snapshot(self):
        import requests
        from .ticker import refresh, get_ticker

        data = get_ticker()
        data["source"] = "last-good-proof"
        TickerSnapshot.objects.create(pk=1, data=data)
        with (
            patch("news.ticker.close_old_connections"),
            patch("news.ticker.fetch_symbol", side_effect=requests.Timeout),
        ):
            refresh()
        self.assertEqual(get_ticker()["source"], "last-good-proof")

    def test_resolver_hides_drafts_and_archive(self):
        a = self.story(status="draft")
        self.assertEqual(
            self.client.get(f"/api/resolve/article/{a.slug}/").status_code, 404
        )
        a.status = "published"
        a.save()
        self.assertEqual(
            self.client.get(f"/api/resolve/article/{a.slug}/").status_code, 200
        )
        a.delete()
        self.assertEqual(
            self.client.get(f"/api/resolve/article/{a.slug}/").status_code, 404
        )
        self.assertEqual(
            self.client.get("/api/resolve/category/markets/").status_code, 200
        )
        self.assertEqual(
            self.client.get("/api/resolve/category/missing/").status_code, 404
        )
