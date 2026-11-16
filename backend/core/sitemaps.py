"""
Shared sitemap plumbing.

This project is decoupled: Django serves the API (and /sitemap.xml), while the pages a
sitemap describes live on the separate React SPA at ``settings.FRONTEND_URL``. Django's
Sitemap machinery builds every ``<loc>`` as ``<protocol>://<domain><location>``, taking
the domain from the Sites framework or, failing that, from the request that hit
``/sitemap.xml``. Neither is the frontend, so without the mixin below every URL names the
backend host (``https://api.example.com/...``, or ``testserver``/``localhost:8000`` in
development), a page that does not exist there.

Frontend routes the sitemaps point at (keep in sync with ``frontend/src/App.jsx``; a test
in ``shop/tests/test_sitemaps.py`` fails if those routes change):

=================================  ==========================================
``/product/<slug>``                product detail
``/category?category=<slug>``      category listing (the category is a QUERY
                                   param on the SPA, there is no /category/<slug>)
``/category?brand=<slug>``         a brand's products (a filtered listing)
``/blog/<slug>``                   blog post
=================================  ==========================================

URLs carry no trailing slash and no extra parameters, exactly like the page's own
``<link rel="canonical">``, so the sitemap lists the canonical form of each URL.
"""

from urllib.parse import quote, urlparse

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def frontend_slug(slug):
    """Percent-encode a slug for use in a URL path or query value."""
    return quote(slug, safe="-_.~")


class FrontendDomainSitemapMixin:
    """
    Make a ``Sitemap`` describe pages on the SPA (``settings.FRONTEND_URL``), not on the
    Django host that happens to serve ``/sitemap.xml``.

    Overrides the two supported hooks ``Sitemap.get_urls`` calls: ``get_domain`` and
    ``get_protocol``. The scheme comes from ``FRONTEND_URL`` itself (so a development
    ``http://localhost:3000`` stays http rather than being forced to https). A path prefix
    in ``FRONTEND_URL`` is honoured, as it is by every other use of the setting
    (``f"{settings.FRONTEND_URL}/checkout/..."``). Put it BEFORE ``Sitemap`` in the bases.

    Also drops rows whose slug is blank, which would otherwise be emitted as the bare
    section URL (``/product``) and listed as a page that is not there.
    """

    def _frontend_url(self):
        parsed = urlparse(settings.FRONTEND_URL or "")
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ImproperlyConfigured(
                "FRONTEND_URL must be an absolute http(s) URL such as "
                f"'https://example.com' to build sitemap URLs; got {settings.FRONTEND_URL!r}."
            )
        return parsed

    def get_domain(self, site=None):
        # ``site`` (the Sites framework / request host) is deliberately ignored.
        parsed = self._frontend_url()
        return parsed.netloc + parsed.path.rstrip("/")

    def get_protocol(self, protocol=None):
        return self._frontend_url().scheme
