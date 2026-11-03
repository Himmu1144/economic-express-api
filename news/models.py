import math, re
import nh3
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.text import slugify
from .media import prepare_image

TAGS = {
    "p",
    "h2",
    "h3",
    "ul",
    "ol",
    "li",
    "b",
    "strong",
    "i",
    "em",
    "a",
    "blockquote",
    "figure",
    "img",
    "figcaption",
    "br",
}


def sanitize(value):
    return nh3.clean(
        value,
        tags=TAGS,
        attributes={"a": {"href"}, "img": {"src", "alt"}},
        url_schemes={"https", "http", "mailto"},
        link_rel=None,
    )


def unique_slug(instance, source):
    root = slugify(source)[:170] or "story"
    candidate, n = root, 1
    while (
        type(instance).objects.filter(slug=candidate).exclude(pk=instance.pk).exists()
    ):
        n += 1
        candidate = f"{root}-{n}"
    return candidate


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, max_length=200)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.name


class Author(models.Model):
    name = models.CharField(max_length=150)
    slug = models.SlugField(unique=True)
    photo = models.ImageField(upload_to="authors/", blank=True)
    bio = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        prepare_image(self.photo)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name


class ArticleQuerySet(models.QuerySet):
    def public(self):
        return self.filter(
            status="published",
            archived_at__isnull=True,
            published_at__lte=timezone.now(),
        )

    def delete(self):
        count = 0
        for obj in self.iterator():
            obj.delete()
            count += 1
        return count, {"news.Article": count}


class Article(models.Model):
    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    author = models.ForeignKey(Author, on_delete=models.PROTECT)
    summary = models.TextField()
    body_html = models.TextField()
    cover_upload = models.ImageField(upload_to="covers/", blank=True)
    cover_image = models.URLField(
        max_length=1000,
        blank=True,
        help_text="HTTPS fallback for imported seed images.",
    )
    cover_alt = models.CharField(max_length=300)
    cover_caption = models.CharField(max_length=500)
    tags = models.ManyToManyField(Tag, blank=True)
    status = models.CharField(
        max_length=12,
        choices=[("draft", "Draft"), ("published", "Published")],
        default="draft",
        db_index=True,
    )
    published_at = models.DateTimeField(default=timezone.now, db_index=True)
    first_published_at = models.DateTimeField(null=True, blank=True, editable=False)
    archived_at = models.DateTimeField(null=True, blank=True, db_index=True)
    is_breaking = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    is_editors_pick = models.BooleanField(default=False)
    is_opinion = models.BooleanField(default=False)
    is_explainer = models.BooleanField(default=False)
    key_points = models.TextField(blank=True, help_text="One point per line.")
    reading_time = models.PositiveIntegerField(default=1, editable=False)
    views = models.PositiveBigIntegerField(default=0, editable=False)
    meta_title = models.CharField(max_length=300, blank=True)
    meta_description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_articles",
        null=True,
        editable=False,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="updated_articles",
        null=True,
        editable=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = ArticleQuerySet.as_manager()

    class Meta:
        ordering = ["-published_at", "-id"]
        indexes = [models.Index(fields=["status", "archived_at", "-published_at"])]

    def clean(self):
        if not self.cover_upload and not self.cover_image:
            raise ValidationError("A cover image is required.")
        if self.cover_image and not self.cover_image.startswith("https://"):
            raise ValidationError("Cover URLs must use HTTPS.")
        if not self.cover_alt.strip() or not self.cover_caption.strip():
            raise ValidationError("Cover alt text and caption are required.")

    def save(self, *args, **kwargs):
        old = type(self).objects.filter(pk=self.pk).first() if self.pk else None
        if old and old.first_published_at:
            self.slug = old.slug
        if not self.slug:
            self.slug = unique_slug(self, self.title)
        self.body_html = sanitize(self.body_html)
        self.reading_time = max(
            1, math.ceil(len(re.findall(r"\S+", strip_tags(self.body_html))) / 200)
        )
        self.meta_title = self.meta_title or self.title
        self.meta_description = self.meta_description or self.summary
        if self.status == "published" and not self.first_published_at:
            self.first_published_at = timezone.now()
        prepare_image(self.cover_upload)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.archived_at = timezone.now()
        self.save()

    def __str__(self):
        return self.title


class DailyViews(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE)
    day = models.DateField()
    count = models.PositiveBigIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["article", "day"], name="article_day_unique"
            )
        ]


class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Video(models.Model):
    youtube_id = models.CharField(
        max_length=11, unique=True, help_text="11-character YouTube ID"
    )
    title = models.CharField(max_length=250)
    source = models.CharField(max_length=100)
    duration = models.CharField(max_length=20)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]

    def clean(self):
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", self.youtube_id):
            raise ValidationError("Invalid YouTube ID.")

    def __str__(self):
        return self.title


class TickerSnapshot(models.Model):
    data = models.JSONField()
    updated_at = models.DateTimeField(auto_now=True)


class RateBucket(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)


class Revalidation(models.Model):
    tags = models.JSONField()
    due_at = models.DateTimeField(default=timezone.now, db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    delivered_at = models.DateTimeField(null=True, blank=True)
