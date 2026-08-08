from rest_framework import serializers

from .models import Category, Comment, Post

# ─── Category ─────────────────────────────────────────────────────────────────


class CategorySerializer(serializers.ModelSerializer):
    post_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "post_count"]


# ─── Comments ─────────────────────────────────────────────────────────────────


class ReplySerializer(serializers.ModelSerializer):
    """Flat representation of a single reply (no further nesting)."""

    class Meta:
        model = Comment
        fields = ["id", "name", "body", "created_at"]


class CommentSerializer(serializers.ModelSerializer):
    """Top-level comment with nested replies."""

    replies = ReplySerializer(many=True, read_only=True)

    class Meta:
        model = Comment
        fields = ["id", "name", "body", "created_at", "replies"]


class CommentCreateSerializer(serializers.ModelSerializer):
    """
    Serializer used when a visitor submits a comment.
    `post` is injected by the view (not from the request body).
    `parent` is optional — pass a comment PK to reply to an existing comment.
    """

    class Meta:
        model = Comment
        fields = ["id", "name", "email", "website", "body", "parent"]

    def validate_parent(self, value):
        if value is None:
            return value
        # The view injects `post` into self.context during perform_create
        post = self.context.get("post")
        if post and value.post_id != post.pk:
            raise serializers.ValidationError(
                "Parent comment does not belong to this post."
            )
        return value


# ─── Posts ────────────────────────────────────────────────────────────────────


class PostListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for list views — omits full content and comments
    to keep list payloads small.
    """

    category = CategorySerializer(read_only=True)
    cover_image_url = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id",
            "title",
            "slug",
            "excerpt",
            "cover_image_url",
            "category",
            "is_featured",
            "views_count",
            "read_time",
            "created_at",
            "published_at",
        ]

    def get_cover_image_url(self, obj):
        if not obj.cover_image:
            return None
        request = self.context.get("request")
        url = obj.cover_image.url
        return request.build_absolute_uri(url) if request else url


class PostDetailSerializer(PostListSerializer):
    """
    Full serializer for the post detail endpoint — includes content and comments.
    """

    comments = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()

    class Meta(PostListSerializer.Meta):
        fields = PostListSerializer.Meta.fields + [
            "content",
            "comments_count",
            "comments",
        ]

    def get_comments(self, obj):
        top_level = obj.comments.filter(is_approved=True, parent__isnull=True)
        return CommentSerializer(top_level, many=True, context=self.context).data

    def get_comments_count(self, obj):
        return obj.comments.filter(is_approved=True).count()
