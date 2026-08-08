from django.contrib import admin

from .models import Brand, Category, Color, Product, ProductColor, ProductImage, Review


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
        "created_at",
    )
    list_filter = ("category", "brand", "is_new", "is_sale")
    search_fields = ("name", "slug", "short_description")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("-created_at",)
    inlines = [ProductImageInline, ProductColorInline]
    readonly_fields = ("created_at",)
    list_per_page = 25


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "image")
    search_fields = ("product__name",)


@admin.register(ProductColor)
class ProductColorAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "color")
    list_filter = ("color",)
    search_fields = ("product__name", "color__name")


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "product", "rating", "headline", "created_at")
    list_filter = ("rating", "product")
    search_fields = ("name", "headline", "comment", "product__name")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
