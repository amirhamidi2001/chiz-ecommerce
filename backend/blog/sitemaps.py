from core.sitemaps import FrontendDomainSitemapMixin, frontend_slug
from django.contrib.sitemaps import Sitemap

from .models import Post


class BlogSitemap(FrontendDomainSitemapMixin, Sitemap):
    changefreq = "daily"
    priority = 0.8

    def items(self):
        return (
            Post.objects.filter(status=Post.Status.PUBLISHED)
            .exclude(slug="")
            .only("id", "slug", "updated_at", "published_at")
            .order_by("id")
        )

    def lastmod(self, obj):
        return getattr(obj, "updated_at", None) or getattr(obj, "published_at", None)

    def location(self, obj):
        # Matches the SPA route /blog/:slug.
        return f"/blog/{frontend_slug(obj.slug)}"
