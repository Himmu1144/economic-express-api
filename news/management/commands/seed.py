import json, os
from pathlib import Path
from datetime import timedelta
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import Group, Permission
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from django.utils.text import slugify
from news.models import Category, Author, Article, Tag, Video, DailyViews


class Command(BaseCommand):
    help = "Create roles; optionally import demo news with --demo. Existing articles are never overwritten."

    def add_arguments(self, parser):
        parser.add_argument("--demo", action="store_true")

    def handle(self, *args, **options):
        for name, models, actions in [
            ("Writer", ["article", "tag"], ["view", "add", "change"]),
            (
                "Editor",
                ["article", "tag", "newslettersubscriber"],
                ["view", "add", "change", "delete"],
            ),
        ]:
            group, _ = Group.objects.get_or_create(name=name)
            group.permissions.set(
                Permission.objects.filter(
                    content_type__app_label="news",
                    content_type__model__in=models,
                    codename__in=[f"{a}_{m}" for a in actions for m in models],
                )
            )
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
        if username and not get_user_model().objects.filter(username=username).exists():
            password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")
            if not password:
                raise CommandError("DJANGO_SUPERUSER_PASSWORD is required")
            validate_password(password)
            get_user_model().objects.create_superuser(
                username, os.environ.get("DJANGO_SUPERUSER_EMAIL", ""), password
            )
        if not options["demo"]:
            return
        data = json.loads((Path(settings.BASE_DIR) / "seed/content.json").read_text())
        for c in data["categories"]:
            Category.objects.get_or_create(
                slug=c["slug"],
                defaults={k: v for k, v in c.items() if k not in {"id", "slug"}},
            )
        for i, a in enumerate(data["articles"]):
            author, _ = Author.objects.get_or_create(
                slug=slugify(a["author"]["name"]),
                defaults={"name": a["author"]["name"]},
            )
            defaults = {
                k: a[k]
                for k in [
                    "title",
                    "summary",
                    "body_html",
                    "cover_image",
                    "is_breaking",
                    "is_featured",
                    "is_editors_pick",
                    "is_opinion",
                    "meta_title",
                    "meta_description",
                    "views",
                ]
            }
            defaults.update(
                author=author,
                category=Category.objects.get(slug=a["category"]["slug"]),
                cover_caption=a["cover_caption"] or a["title"],
                cover_alt=a["title"],
                key_points="\n".join(a.get("key_points") or []),
                is_explainer=a["slug"] in data["explained"],
                status="published",
                published_at=timezone.now() - timedelta(minutes=i * 10 + 1),
            )
            obj, created = Article.objects.get_or_create(
                slug=a["slug"], defaults=defaults
            )
            if created:
                for t in a["tags"]:
                    tag, _ = Tag.objects.get_or_create(
                        slug=t["slug"], defaults={"name": t["name"]}
                    )
                    obj.tags.add(tag)
                DailyViews.objects.create(
                    article=obj, day=timezone.localdate(), count=a["views"]
                )
        for i, v in enumerate(data["videos"]):
            Video.objects.get_or_create(
                youtube_id=v["id"],
                defaults={
                    **{k: v[k] for k in ["title", "source", "duration"]},
                    "order": i,
                },
            )
        self.stdout.write(
            f"Demo content: {Article.objects.count()} articles, {Category.objects.count()} categories. Do not present these samples as live news."
        )
