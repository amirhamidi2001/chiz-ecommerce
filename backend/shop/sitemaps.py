from core.sitemaps import FrontendDomainSitemapMixin, frontend_slug
from django.contrib.sitemaps import Sitemap

from .models import Brand, Category, Product

# Product, Category and Brand have no published / active / deleted concept (see the tripwire
# test in tests/test_sitemaps.py), so every row is a live page and nothing is filtered out,
# including products that are out of stock: the page is still valid, indexable content.
# Only a blank slug is skipped, since it cannot form a URL.


class ProductSitemap(FrontendDomainSitemapMixin, Sitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        # Only the columns the sitemap reads: Product carries several large text fields.
        return (
            Product.objects.exclude(slug="")
            .only("id", "slug", "created_at")
            .order_by("id")
        )

    def lastmod(self, obj):
        # Product has no updated_at, so this is its creation date.
        return getattr(obj, "updated_at", None) or getattr(obj, "created_at", None)

    def location(self, obj):
        return f"/product/{frontend_slug(obj.slug)}"


class CategorySitemap(FrontendDomainSitemapMixin, Sitemap):
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        return Category.objects.exclude(slug="").only("id", "slug").order_by("id")

    def location(self, obj):
        # On the SPA the category is a query parameter, not part of the path.
        return f"/category?category={frontend_slug(obj.slug)}"


class BrandSitemap(FrontendDomainSitemapMixin, Sitemap):
    changefreq = "monthly"
    priority = 0.5

    def items(self):
        return Brand.objects.exclude(slug="").only("id", "slug").order_by("id")

    def location(self, obj):
        # There is no dedicated brand page on the SPA: a brand is a filter on the listing.
        return f"/category?brand={frontend_slug(obj.slug)}"
