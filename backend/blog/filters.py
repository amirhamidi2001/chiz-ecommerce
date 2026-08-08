import django_filters

from .models import Post


class PostFilter(django_filters.FilterSet):
    """
    Filterset for the public Post list endpoint.

    Supported query params:
      ?category=<slug>          — filter by category slug
      ?is_featured=true|false   — filter featured posts
    """

    category = django_filters.CharFilter(
        field_name="category__slug", lookup_expr="exact"
    )
    is_featured = django_filters.BooleanFilter(field_name="is_featured")

    class Meta:
        model = Post
        fields = ["category", "is_featured"]
