from datetime import timedelta

from django.contrib import admin
from django.db.models import F
from django.utils import timezone

from .models import (
    Brand,
    Category,
    Color,
    Product,
    ProductColor,
    ProductImage,
    ProductVariant,
    Review,
    StockAlertSubscription,
    StockMovement,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "parent", "created_at")
    list_filter = ("parent",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)


@admin.register(Color)
class ColorAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "hex_code")
    search_fields = ("name",)
    ordering = ("name",)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


class ProductColorInline(admin.TabularInline):
    model = ProductColor
    extra = 1


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    fields = (
        "sku",
        "barcode",
        "color",
        "price",
        "original_price",
        "stock",
        "low_stock_threshold",
        "volume_ml",
        "weight_g",
        "manufacture_date",
        "expiration_date",
        "batch_number",
        "is_active",
    )


@admin.action(description="Mark selected products as regulatory-verified")
def mark_regulatory_verified(modeladmin, request, queryset):
    updated = queryset.update(regulatory_verified=True)
    modeladmin.message_user(request, f"{updated} product(s) marked as verified.")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "category",
        "brand",
        "price",
        "original_price",
        "stock",
        "rating",
        "reviews_count",
        "is_new",
        "is_sale",
        "regulatory_verified",
        "created_at",
    )
    list_filter = (
        "category",
        "brand",
        "is_new",
        "is_sale",
        "skin_type",
        "hair_type",
        "gender",
        "is_cruelty_free",
        "is_vegan",
        "is_organic",
        "regulatory_verified",
    )
    search_fields = (
        "name",
        "slug",
        "short_description",
        "country_of_origin",
        "irc_regulatory_code",
    )
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("-created_at",)
    inlines = [ProductImageInline, ProductColorInline, ProductVariantInline]
    readonly_fields = ("created_at",)
    list_per_page = 25
    actions = [mark_regulatory_verified]


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "image")
    search_fields = ("product__name",)


@admin.register(ProductColor)
class ProductColorAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "color")
    list_filter = ("color",)
    search_fields = ("product__name", "color__name")


class NearExpiryFilter(admin.SimpleListFilter):
    """
    Business-relevant quick-filter for inventory staff, complementing
    (not replacing) the plain expiration_date filter already in
    list_filter — that one is still useful for browsing by specific
    date ranges via Django's default date-hierarchy buckets, while
    this offers the two views staff actually want to check regularly.
    """

    title = "expiry status"
    parameter_name = "expiry_status"

    def lookups(self, request, model_admin):
        return (
            ("near", "Expiring within 90 days"),
            ("expired", "Already expired"),
        )

    def queryset(self, request, queryset):
        today = timezone.now().date()
        if self.value() == "near":
            return queryset.filter(
                expiration_date__isnull=False,
                expiration_date__gte=today,
                expiration_date__lte=today + timedelta(days=90),
            )
        if self.value() == "expired":
            return queryset.filter(
                expiration_date__isnull=False,
                expiration_date__lt=today,
            )
        return queryset


class LowStockFilter(admin.SimpleListFilter):
    title = "stock status"
    parameter_name = "stock_status"

    def lookups(self, request, model_admin):
        return (("low", "Low stock"), ("out", "Out of stock"))

    def queryset(self, request, queryset):
        if self.value() == "low":
            return queryset.filter(stock__gt=0, stock__lte=F("low_stock_threshold"))
        if self.value() == "out":
            return queryset.filter(stock=0)
        return queryset


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "product",
        "sku",
        "color",
        "price",
        "stock",
        "low_stock_threshold",
        "volume_ml",
        "weight_g",
        "manufacture_date",
        "expiration_date",
        "is_active",
    )
    list_filter = (
        "is_active",
        "color",
        "expiration_date",
        NearExpiryFilter,
        LowStockFilter,
    )
    search_fields = ("sku", "barcode", "product__name", "batch_number")
    autocomplete_fields = ("product", "color")
    # Soonest-to-expire first by default — a reasonable ordering
    # regardless of which filter is active, so a static ordering is
    # used rather than a get_ordering() override keyed on the request's
    # expiry_status param (that would add complexity for little real
    # benefit, since "soonest expiration first" is what inventory staff
    # want to see whether or not the Near Expiry filter is applied).
    ordering = ("expiration_date", "product__name")


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "variant",
        "reason",
        "quantity_delta",
        "stock_after",
        "actor",
        "created_at",
    )
    list_filter = ("reason", "created_at")
    search_fields = ("variant__sku", "variant__product__name", "note")
    ordering = ("-created_at",)
    readonly_fields = [f.name for f in StockMovement._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(StockAlertSubscription)
class StockAlertSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "variant", "created_at", "notified_at")
    list_filter = ("notified_at",)
    search_fields = ("user__email", "variant__sku", "variant__product__name")
    readonly_fields = ("user", "variant", "created_at", "notified_at")

    def has_add_permission(self, request):
        return False


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "product", "rating", "headline", "created_at")
    list_filter = ("rating", "product")
    search_fields = ("name", "headline", "comment", "product__name")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
