import django_filters
from blog.models import Category, Comment, Post
from django.contrib.auth import get_user_model
from order.models import Order
from shop.models import Product

User = get_user_model()


# ─── Admin: Orders ────────────────────────────────────────────────────────────


class AdminOrderFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(field_name="status", lookup_expr="exact")
    payment_method = django_filters.CharFilter(
        field_name="payment_method", lookup_expr="exact"
    )
    date_from = django_filters.DateFilter(
        field_name="created_at", lookup_expr="date__gte"
    )
    date_to = django_filters.DateFilter(
        field_name="created_at", lookup_expr="date__lte"
    )
    min_total = django_filters.NumberFilter(field_name="total", lookup_expr="gte")
    max_total = django_filters.NumberFilter(field_name="total", lookup_expr="lte")

    class Meta:
        model = Order
        fields = [
            "status",
            "payment_method",
            "date_from",
            "date_to",
            "min_total",
            "max_total",
        ]


# ─── Admin: Products ─────────────────────────────────────────────────────────


class AdminProductFilter(django_filters.FilterSet):
    category = django_filters.NumberFilter(field_name="category__id")
    brand = django_filters.NumberFilter(field_name="brand__id")
    is_sale = django_filters.BooleanFilter(field_name="is_sale")
    is_new = django_filters.BooleanFilter(field_name="is_new")
    min_price = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="price", lookup_expr="lte")
    in_stock = django_filters.BooleanFilter(method="filter_in_stock")

    def filter_in_stock(self, queryset, name, value):
        if value is True:
            return queryset.filter(stock__gt=0)
        if value is False:
            return queryset.filter(stock=0)
        return queryset

    class Meta:
        model = Product
        fields = [
            "category",
            "brand",
            "is_sale",
            "is_new",
            "min_price",
            "max_price",
            "in_stock",
        ]


# ─── Admin: Users ────────────────────────────────────────────────────────────


class AdminUserFilter(django_filters.FilterSet):
    is_active = django_filters.BooleanFilter(field_name="is_active")
    is_verified = django_filters.BooleanFilter(field_name="is_verified")
    type = django_filters.NumberFilter(field_name="type")
    date_from = django_filters.DateFilter(
        field_name="created_date", lookup_expr="date__gte"
    )
    date_to = django_filters.DateFilter(
        field_name="created_date", lookup_expr="date__lte"
    )

    class Meta:
        model = User
        fields = ["is_active", "is_verified", "type", "date_from", "date_to"]


# ─── User: Orders ────────────────────────────────────────────────────────────


class UserOrderFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(field_name="status", lookup_expr="exact")

    class Meta:
        model = Order
        fields = ["status"]


# ─── Admin: Blog Posts ─────────────────────────────────────────────────────────


class AdminPostFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=Post.Status.choices)
    category = django_filters.NumberFilter(field_name="category__id")
    author = django_filters.NumberFilter(field_name="author__id")
    is_featured = django_filters.BooleanFilter()
    published_from = django_filters.DateFilter(
        field_name="published_at", lookup_expr="date__gte"
    )
    published_to = django_filters.DateFilter(
        field_name="published_at", lookup_expr="date__lte"
    )
    created_from = django_filters.DateFilter(
        field_name="created_at", lookup_expr="date__gte"
    )
    created_to = django_filters.DateFilter(
        field_name="created_at", lookup_expr="date__lte"
    )

    class Meta:
        model = Post
        fields = [
            "status",
            "category",
            "author",
            "is_featured",
            "published_from",
            "published_to",
            "created_from",
            "created_to",
        ]


# ─── Admin: Categories ─────────────────────────────────────────────────────────


class AdminCategoryFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = Category
        fields = ["name"]


# ─── Admin: Comments ───────────────────────────────────────────────────────────


class AdminCommentFilter(django_filters.FilterSet):
    post = django_filters.NumberFilter(field_name="post__id")
    is_approved = django_filters.BooleanFilter()
    created_from = django_filters.DateFilter(
        field_name="created_at", lookup_expr="date__gte"
    )
    created_to = django_filters.DateFilter(
        field_name="created_at", lookup_expr="date__lte"
    )
    name = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = Comment
        fields = ["post", "is_approved", "created_from", "created_to", "name"]
