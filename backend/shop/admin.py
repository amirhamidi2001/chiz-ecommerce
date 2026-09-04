from django.contrib import admin

from .models import (
    Brand,
    Category,
    Color,
    Product,
    ProductColor,
    ProductImage,
    ProductVariant,
    Review,
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


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "product",
        "sku",
        "color",
        "price",
        "stock",
        "volume_ml",
        "weight_g",
        "manufacture_date",
        "expiration_date",
        "is_active",
    )
    list_filter = ("is_active", "color", "expiration_date")
    search_fields = ("sku", "barcode", "product__name", "batch_number")
    autocomplete_fields = ("product", "color")
    ordering = ("product__name", "id")


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "product", "rating", "headline", "created_at")
    list_filter = ("rating", "product")
    search_fields = ("name", "headline", "comment", "product__name")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
