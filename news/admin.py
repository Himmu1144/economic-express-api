import csv
from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.html import format_html
from django.views.decorators.http import require_POST
from django.core.files.storage import default_storage
from tinymce.widgets import TinyMCE
from .models import Article, Author, Category, Tag, Video, NewsletterSubscriber
from .media import optimized_image


def editor(user):
    return user.is_superuser or user.groups.filter(name="Editor").exists()


def writer(user):
    return user.groups.filter(name="Writer").exists() and not editor(user)


class ArticleForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = "__all__"
        widgets = {"body_html": TinyMCE()}

    def clean_cover_upload(self):
        value = self.cleaned_data.get("cover_upload")
        if value and hasattr(value, "content_type"):
            value = optimized_image(value)
        return value


class AuthorForm(forms.ModelForm):
    class Meta:
        model = Author
        fields = "__all__"

    def clean_photo(self):
        value = self.cleaned_data.get("photo")
        if value and hasattr(value, "content_type"):
            value = optimized_image(value)
        return value


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    form = ArticleForm
    list_display = [
        "title",
        "status",
        "published_at",
        "is_breaking",
        "is_featured",
        "is_editors_pick",
        "is_opinion",
        "is_explainer",
        "archived_at",
    ]
    list_editable = [
        "is_breaking",
        "is_featured",
        "is_editors_pick",
        "is_opinion",
        "is_explainer",
    ]
    list_filter = ["status", "category", "archived_at", "is_featured"]
    search_fields = ["title", "summary", "slug"]
    filter_horizontal = ["tags"]
    readonly_fields = [
        "created_by",
        "updated_by",
        "created_at",
        "updated_at",
        "reading_time",
        "views",
        "preview_link",
        "archived_at",
    ]
    actions = ["archive", "restore"]

    class Media:
        js = ["news/upload.js"]

    def get_queryset(self, request):
        qs = (
            super()
            .get_queryset(request)
            .select_related("category", "author", "created_by")
        )
        return (
            qs.filter(created_by=request.user, status="draft", archived_at__isnull=True)
            if writer(request.user)
            else qs
        )

    def get_list_display(self, request):
        return (
            ["title", "status", "published_at"]
            if writer(request.user)
            else self.list_display
        )

    def get_changelist_instance(self, request):
        instance = super().get_changelist_instance(request)
        if writer(request.user):
            instance.list_editable = ()
        return instance

    def get_readonly_fields(self, request, obj=None):
        return list(self.readonly_fields) + (
            [
                "status",
                "is_breaking",
                "is_featured",
                "is_editors_pick",
                "is_opinion",
                "is_explainer",
            ]
            if writer(request.user)
            else []
        )

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and (
            obj is None
            or editor(request.user)
            or (
                obj.created_by_id == request.user.pk
                and obj.status == "draft"
                and not obj.archived_at
            )
        )

    def has_delete_permission(self, request, obj=None):
        return editor(request.user)

    def save_model(self, request, obj, form, change):
        if writer(request.user):
            if obj.pk:
                old = Article.objects.get(pk=obj.pk)
                if (
                    old.created_by_id != request.user.pk
                    or old.status != "draft"
                    or old.archived_at
                ):
                    raise PermissionDenied
            obj.status = "draft"
            for flag in self.list_editable:
                setattr(obj, flag, False)
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description="Draft preview")
    def preview_link(self, obj):
        return (
            format_html(
                '<a href="{}" target="_blank">Preview saved content</a>',
                reverse("article-preview", args=[obj.pk]),
            )
            if obj.pk
            else "Save first"
        )

    @admin.action(description="Archive selected articles")
    def archive(self, request, queryset):
        if not editor(request.user):
            raise PermissionDenied
        for obj in queryset:
            obj.updated_by = request.user
            obj.delete()

    @admin.action(description="Restore selected articles as drafts")
    def restore(self, request, queryset):
        if not editor(request.user):
            raise PermissionDenied
        for obj in queryset:
            obj.archived_at = None
            obj.status = "draft"
            obj.updated_by = request.user
            obj.save()

    def delete_model(self, request, obj):
        obj.updated_by = request.user
        obj.delete()

    def delete_queryset(self, request, queryset):
        self.archive(request, queryset)


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    form = AuthorForm
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "order"]
    list_editable = ["order"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ["title", "order", "is_active"]
    list_editable = ["order", "is_active"]


@admin.register(NewsletterSubscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = ["email", "created_at"]
    search_fields = ["email"]
    actions = ["export_csv"]

    @admin.action(description="Export selected subscribers to CSV")
    def export_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="subscribers.csv"'
        out = csv.writer(response)
        out.writerow(["email", "created_at"])
        for row in queryset.iterator():
            email = row.email
            if email[:1] in "=+-@":
                email = "'" + email
            out.writerow([email, row.created_at.isoformat()])
        return response


@require_POST
def inline_upload(request):
    if not request.user.has_perm("news.add_article"):
        raise PermissionDenied
    upload = request.FILES.get("file")
    if not upload:
        return JsonResponse({"error": "Missing file"}, status=400)
    try:
        content = optimized_image(upload)
    except ValidationError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    name = default_storage.save("inline/" + content.name, content)
    return JsonResponse({"location": default_storage.url(name)})


def preview(request, pk):
    obj = get_object_or_404(Article, pk=pk)
    if not editor(request.user) and not (
        writer(request.user)
        and obj.created_by_id == request.user.pk
        and obj.status == "draft"
    ):
        raise PermissionDenied
    # Authenticated CMS preview; no draft content exposed via the public API.
    response = HttpResponse(
        format_html(
            '<!doctype html><meta name="robots" content="noindex,nofollow"><title>Draft preview</title><h1>{}</h1><p>{}</p>',
            obj.title,
            obj.summary,
        )
        + obj.body_html
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


admin.site.site_header = "Economic.Express CMS"
admin.site.site_title = "Economic.Express CMS"
admin.site.index_title = "Editorial desk"
