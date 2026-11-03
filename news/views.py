from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.db.models import F, Q, Sum, Prefetch
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from .models import Article, Category, DailyViews, NewsletterSubscriber, Video
from .serializers import (
    CardSerializer,
    DetailSerializer,
    CategorySerializer,
    NewsletterSerializer,
    VideoSerializer,
)
from .throttles import DatabaseThrottle, NewsletterThrottle


def public():
    return Article.objects.public().select_related("category", "author")


def cards(qs):
    return CardSerializer(qs, many=True).data


def ranked():
    return (
        public()
        .annotate(
            week_views=Coalesce(
                Sum(
                    "dailyviews__count",
                    filter=Q(
                        dailyviews__day__gte=timezone.localdate() - timedelta(days=6)
                    ),
                ),
                0,
            )
        )
        .order_by("-week_views", "-published_at", "-id")
    )


@api_view(["GET"])
def home(request):
    qs = public()
    lead = qs.filter(is_featured=True).first() or qs.first()
    picks = list(qs.filter(is_editors_pick=True)[:4])
    picks += list(ranked().exclude(pk__in=[a.pk for a in picks])[: 4 - len(picks)])
    # Sliced prefetch uses a window function: one article query for all categories.
    categories = Category.objects.prefetch_related(
        Prefetch("article_set", queryset=qs[:4], to_attr="latest_articles")
    )
    return Response(
        {
            "breaking": cards(
                qs.filter(
                    is_breaking=True,
                    published_at__gte=timezone.now()
                    - timedelta(hours=settings.BREAKING_HOURS),
                )
            ),
            "lead": CardSerializer(lead).data if lead else None,
            "top": cards(qs.exclude(pk=lead.pk if lead else None)[:3]),
            "latest": cards(qs[:8]),
            "sections": [
                {
                    "category": {"name": c.name, "slug": c.slug},
                    "articles": cards(c.latest_articles),
                }
                for c in categories
            ],
            "trending": cards(ranked()[:5]),
            "opinion": cards(qs.filter(is_opinion=True)[:3]),
            "editors_picks": cards(picks),
            "explained": cards(qs.filter(is_explainer=True)[:2]),
            "videos": VideoSerializer(
                Video.objects.filter(is_active=True), many=True
            ).data,
        }
    )


@api_view(["GET"])
def categories(request):
    return Response(CategorySerializer(Category.objects.all(), many=True).data)


@api_view(["GET"])
def articles(request):
    qs = public()
    for param, field in [("category", "category__slug"), ("tag", "tags__slug")]:
        if request.query_params.get(param):
            qs = qs.filter(**{field: request.query_params[param]})
    term = request.query_params.get("search", "").strip()[:200]
    if term:
        qs = qs.filter(
            Q(title__icontains=term)
            | Q(summary__icontains=term)
            | Q(body_html__icontains=term)
        )
    pager = PageNumberPagination()
    pager.page_size = 12
    return pager.get_paginated_response(
        cards(pager.paginate_queryset(qs.distinct(), request))
    )


@api_view(["GET"])
def article(request, slug):
    return Response(
        DetailSerializer(
            get_object_or_404(public().prefetch_related("tags"), slug=slug)
        ).data
    )


@api_view(["POST"])
@throttle_classes([DatabaseThrottle])
def view(request, slug):
    obj = get_object_or_404(public(), slug=slug)
    agent = request.META.get("HTTP_USER_AGENT", "").lower()
    if agent and not any(
        s in agent for s in ["bot", "crawler", "spider", "headless", "preview"]
    ):
        with transaction.atomic():
            Article.objects.filter(pk=obj.pk).update(views=F("views") + 1)
            row, _ = DailyViews.objects.get_or_create(
                article=obj, day=timezone.localdate()
            )
            DailyViews.objects.filter(pk=row.pk).update(count=F("count") + 1)
        obj.refresh_from_db(fields=["views"])
    return Response({"views": obj.views})


@api_view(["GET"])
def trending(request):
    return Response(cards(ranked()[:5]))


@api_view(["GET"])
def videos(request):
    return Response(
        VideoSerializer(Video.objects.filter(is_active=True), many=True).data
    )


@api_view(["POST"])
@throttle_classes([NewsletterThrottle])
def newsletter(request):
    serializer = NewsletterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    NewsletterSubscriber.objects.get_or_create(
        email=serializer.validated_data["email"].lower()
    )
    return Response({"ok": True})


@api_view(["GET"])
def ticker(request):
    from .ticker import get_ticker

    return Response(get_ticker())


@api_view(["GET"])
def resolve(request, kind, slug):
    """Cheap existence check before Next streams a cached page or its 404 UI."""
    exists = (
        public().filter(slug=slug).exists()
        if kind == "article"
        else Category.objects.filter(slug=slug).exists()
        if kind == "category"
        else False
    )
    response = Response({"exists": exists}, status=200 if exists else 404)
    response["Cache-Control"] = "no-store"
    return response
