from django.contrib import admin
from django.urls import path, include
from news import views
from news.admin import inline_upload, preview

urlpatterns = [
    path("api/resolve/<str:kind>/<slug:slug>/", views.resolve),
    path("admin/inline-upload/", admin.site.admin_view(inline_upload)),
    path(
        "admin/article-preview/<int:pk>/",
        admin.site.admin_view(preview),
        name="article-preview",
    ),
    path("admin/", admin.site.urls),
    path("tinymce/", include("tinymce.urls")),
    path("api/home/", views.home),
    path("api/categories/", views.categories),
    path("api/articles/", views.articles),
    path("api/articles/<slug:slug>/", views.article),
    path("api/articles/<slug:slug>/view/", views.view),
    path("api/trending/", views.trending),
    path("api/videos/", views.videos),
    path("api/newsletter/", views.newsletter),
    path("api/market/ticker/", views.ticker),
]
