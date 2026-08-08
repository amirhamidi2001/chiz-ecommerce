from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Post


class BlogSitemap(Sitemap):
    protocol = "https"
    changefreq = "daily"
    priority = 0.8

    def items(self):
        return Post.objects.filter(status=Post.Status.PUBLISHED).select_related(
            "category"
        )

    def lastmod(self, obj):
        # Prefer published_at if you have it, fallback to created_at
        return getattr(obj, "updated_at", None) or getattr(obj, "published_at", None)

    def location(self, obj):
        # IMPORTANT: must match your frontend route
        return f"/blog/{obj.slug}/"
