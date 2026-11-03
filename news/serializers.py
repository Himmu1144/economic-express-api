from rest_framework import serializers
from .models import Article, Category, Video


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug", "description", "order"]


class CardSerializer(serializers.ModelSerializer):
    category = serializers.SerializerMethodField()
    author = serializers.SerializerMethodField()
    cover_image = serializers.SerializerMethodField()

    def get_category(self, obj):
        return {"name": obj.category.name, "slug": obj.category.slug}

    def get_author(self, obj):
        return {
            "name": obj.author.name,
            "avatar": obj.author.photo.url if obj.author.photo else "",
        }

    def get_cover_image(self, obj):
        return obj.cover_upload.url if obj.cover_upload else obj.cover_image

    class Meta:
        model = Article
        fields = [
            "id",
            "title",
            "slug",
            "summary",
            "cover_image",
            "cover_alt",
            "cover_caption",
            "category",
            "author",
            "published_at",
            "reading_time",
            "views",
            "is_breaking",
            "is_featured",
            "is_editors_pick",
            "is_opinion",
            "is_explainer",
        ]


class DetailSerializer(CardSerializer):
    tags = serializers.SerializerMethodField()
    key_points = serializers.SerializerMethodField()
    related = serializers.SerializerMethodField()

    def get_tags(self, obj):
        return [{"name": t.name, "slug": t.slug} for t in obj.tags.all()]

    def get_key_points(self, obj):
        return [s.strip() for s in obj.key_points.splitlines() if s.strip()]

    def get_related(self, obj):
        qs = (
            Article.objects.public()
            .exclude(pk=obj.pk)
            .select_related("category", "author")
        )
        same = list(qs.filter(category=obj.category)[:3])
        if len(same) < 3:
            same += list(
                qs.exclude(pk__in=[a.pk for a in same])
                .filter(tags__in=obj.tags.all())
                .distinct()[: 3 - len(same)]
            )
        return CardSerializer(same, many=True).data

    class Meta(CardSerializer.Meta):
        fields = CardSerializer.Meta.fields + [
            "body_html",
            "tags",
            "key_points",
            "meta_title",
            "meta_description",
            "related",
        ]


class VideoSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="youtube_id")

    class Meta:
        model = Video
        fields = ["id", "title", "source", "duration"]


class NewsletterSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
