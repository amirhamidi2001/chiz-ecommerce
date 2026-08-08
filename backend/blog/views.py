from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .filters import PostFilter
from .models import Category, Post
from .pagination import BlogPagination
from .serializers import (
    CategorySerializer,
    CommentCreateSerializer,
    PostDetailSerializer,
    PostListSerializer,
)

# ─── Categories ───────────────────────────────────────────────────────────────


class CategoryListView(generics.ListAPIView):
    """
    GET /api/blog/categories/
    Returns all categories that have at least one published post,
    annotated with the published post count.
    """

    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        return (
            Category.objects.annotate(
                post_count=Count("posts", filter=Q(posts__status=Post.Status.PUBLISHED))
            )
            .filter(post_count__gt=0)
            .order_by("name")
        )


# ─── Post list ────────────────────────────────────────────────────────────────


class PostListView(generics.ListAPIView):
    """
    GET /api/blog/posts/

    Query parameters:
      ?page=<n>                  Pagination (default page_size=6)
      ?page_size=<n>             Override page size (max 24)
      ?category=<slug>           Filter by category slug
      ?is_featured=true|false    Filter featured posts
      ?search=<q>                Full-text search across title, excerpt, content
      ?ordering=<field>          One of: created_at, -created_at, views_count,
                                          -views_count, published_at, -published_at
                                 Default: -created_at
    """

    serializer_class = PostListSerializer
    permission_classes = [AllowAny]
    pagination_class = BlogPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = PostFilter
    search_fields = ["title", "excerpt", "content"]
    ordering_fields = ["created_at", "published_at", "views_count"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return Post.objects.filter(status=Post.Status.PUBLISHED).select_related(
            "author", "category"
        )


# ─── Post detail ──────────────────────────────────────────────────────────────


class PostDetailView(generics.RetrieveAPIView):
    """
    GET /api/blog/posts/<slug>/
    Returns full post data including content and approved comments.
    Atomically increments the view counter on every request.
    """

    serializer_class = PostDetailSerializer
    permission_classes = [AllowAny]
    lookup_field = "slug"

    def get_queryset(self):
        return (
            Post.objects.filter(status=Post.Status.PUBLISHED)
            .select_related("author", "category")
            .prefetch_related(
                "comments",
                "comments__replies",
            )
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        # Atomic increment — safe under concurrent requests
        Post.objects.filter(pk=instance.pk).update(views_count=F("views_count") + 1)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


# ─── Related posts ────────────────────────────────────────────────────────────


class RelatedPostsView(generics.ListAPIView):
    """
    GET /api/blog/posts/<slug>/related/
    Returns up to 3 published posts in the same category, excluding the current post.
    Falls back to the most recent published posts when no category match exists.
    """

    serializer_class = PostListSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        post = get_object_or_404(
            Post, slug=self.kwargs["slug"], status=Post.Status.PUBLISHED
        )
        qs = (
            Post.objects.filter(status=Post.Status.PUBLISHED)
            .exclude(pk=post.pk)
            .select_related("author", "category")
        )
        if post.category_id:
            related = qs.filter(category=post.category).order_by("-created_at")[:3]
            if related.count() >= 1:
                return related
        # Fallback: latest posts regardless of category
        return qs.order_by("-created_at")[:3]


# ─── Comments ─────────────────────────────────────────────────────────────────


class CommentCreateView(generics.CreateAPIView):
    """
    POST /api/blog/posts/<slug>/comments/
    Body: { name, email, website?, body, parent? }
    Creates a new comment (or reply when `parent` is provided).
    No authentication required — open commenting.
    """

    serializer_class = CommentCreateSerializer
    permission_classes = [AllowAny]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["post"] = get_object_or_404(
            Post, slug=self.kwargs["slug"], status=Post.Status.PUBLISHED
        )
        return context

    def perform_create(self, serializer):
        post = get_object_or_404(
            Post, slug=self.kwargs["slug"], status=Post.Status.PUBLISHED
        )
        serializer.save(post=post)
