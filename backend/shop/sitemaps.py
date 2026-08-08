from django.contrib.sitemaps import Sitemap

from .models import Category, Product


class ProductSitemap(Sitemap):
    protocol = "https"
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return Product.objects.select_related("category", "brand").all()

    def lastmod(self, obj):
        return getattr(obj, "updated_at", None) or getattr(obj, "created_at", None)

    def location(self, obj):
        return f"/products/{obj.slug}/"


class CategorySitemap(Sitemap):
    protocol = "https"
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        return Category.objects.all()

    def location(self, obj):
        return f"/category/{obj.slug}/"
