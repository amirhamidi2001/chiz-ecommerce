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

    # Skin type / hair type — comma-separated e.g. ?skin_type=oily,dry
    # A Product only stores ONE skin_type/hair_type value each (plain
    # single-value CharField, not a multi-select), but a filter sidebar
    # reasonably wants to match products against SEVERAL selected
    # values at once (show products suitable for either "oily" or
    # "dry"), so this uses the same comma-split-then-__in pattern as
    # filter_brand/filter_color above rather than a plain single-value
    # filter.
    skin_type = django_filters.CharFilter(method="filter_skin_type")
    hair_type = django_filters.CharFilter(method="filter_hair_type")

    # Gender — kept as a simple single-value filter (mirroring
    # min_price/is_new style): rarely useful to select multiple
    # genders at once in a filter sidebar, unlike skin_type/hair_type.
    gender = django_filters.CharFilter(field_name="gender")

    # SPF range
    min_spf = django_filters.NumberFilter(field_name="spf", lookup_expr="gte")
    max_spf = django_filters.NumberFilter(field_name="spf", lookup_expr="lte")

    # Certification badges
    is_cruelty_free = django_filters.BooleanFilter(field_name="is_cruelty_free")
    is_vegan = django_filters.BooleanFilter(field_name="is_vegan")
    is_organic = django_filters.BooleanFilter(field_name="is_organic")

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
            "skin_type",
            "hair_type",
            "gender",
            "min_spf",
            "max_spf",
            "is_cruelty_free",
            "is_vegan",
            "is_organic",
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

    def filter_skin_type(self, queryset, name, value):
        """Accept comma-separated skin_type choice values, matched with __in."""
        values = [v.strip() for v in value.split(",") if v.strip()]
        if not values:
            return queryset
        return queryset.filter(skin_type__in=values)

    def filter_hair_type(self, queryset, name, value):
        """Accept comma-separated hair_type choice values, matched with __in."""
        values = [v.strip() for v in value.split(",") if v.strip()]
        if not values:
            return queryset
        return queryset.filter(hair_type__in=values)
