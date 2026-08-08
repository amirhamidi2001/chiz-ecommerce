import django_filters

from .models import Product


class ProductFilter(django_filters.FilterSet):
    # Price range
    min_price = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="price", lookup_expr="lte")

    # Category — filter by slug or id
    category = django_filters.CharFilter(method="filter_category")

    # Brand — comma-separated slugs e.g. ?brand=nike,adidas
    brand = django_filters.CharFilter(method="filter_brand")

    # Color — comma-separated color ids e.g. ?color=1,3
    color = django_filters.CharFilter(method="filter_color")

    # Flags
    is_new = django_filters.BooleanFilter(field_name="is_new")
    is_sale = django_filters.BooleanFilter(field_name="is_sale")

    class Meta:
        model = Product
        fields = [
            "min_price",
            "max_price",
            "category",
            "brand",
            "color",
            "is_new",
            "is_sale",
        ]

    def filter_category(self, queryset, name, value):
        """Accept category slug or numeric id."""
        if value.isdigit():
            return queryset.filter(category__id=int(value))
        return queryset.filter(category__slug=value)

    def filter_brand(self, queryset, name, value):
        """Accept comma-separated brand slugs or ids."""
        values = [v.strip() for v in value.split(",") if v.strip()]
        if not values:
            return queryset
        if values[0].isdigit():
            return queryset.filter(
                brand__id__in=[int(v) for v in values if v.isdigit()]
            )
        return queryset.filter(brand__slug__in=values)

    def filter_color(self, queryset, name, value):
        """Accept comma-separated color ids or names."""
        values = [v.strip() for v in value.split(",") if v.strip()]
        if not values:
            return queryset
        if values[0].isdigit():
            return queryset.filter(
                colors__color__id__in=[int(v) for v in values if v.isdigit()]
            )
        return queryset.filter(colors__color__name__in=values)
