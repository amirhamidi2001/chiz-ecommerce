"""Helpers shared by the sitemap tests (shop, blog and core)."""

from xml.etree import ElementTree as ET

from django.contrib.sitemaps.views import sitemap
from django.test import RequestFactory

SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

# Where the Django API (and so /sitemap.xml) is served from in these tests: deliberately NOT
# the frontend host, so a URL that leaked the request host would be caught.
BACKEND_HOST = "api.chiz.example"


def render_sitemaps(sitemaps, host=BACKEND_HOST):
    """Call the real sitemap view directly for a request that arrived on ``host``."""
    request = RequestFactory().get("/sitemap.xml", HTTP_HOST=host)
    response = sitemap(request, sitemaps=sitemaps)
    response.render()
    return response


def parse_locs(content):
    """Parse sitemap XML (raises ParseError if malformed) and return every ``<loc>``."""
    root = ET.fromstring(content)
    assert root.tag == f"{{{SITEMAP_NS['sm']}}}urlset", root.tag
    return [loc.text for loc in root.findall("sm:url/sm:loc", SITEMAP_NS)]
