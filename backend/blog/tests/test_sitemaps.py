"""BlogSitemap (Task 15.2): frontend domain, the SPA's /blog/:slug route, current slugs,
published posts only."""

from urllib.parse import urlparse

import pytest
from blog.models import Post
from blog.sitemaps import BlogSitemap
from blog.tests.conftest import DraftPostFactory, PostFactory
from core.tests.sitemap_helpers import BACKEND_HOST, parse_locs, render_sitemaps

FRONTEND_URL = "https://chiz.example"
FRONTEND = urlparse(FRONTEND_URL)


@pytest.fixture(autouse=True)
def frontend_settings(settings):
    """A frontend origin that differs from the backend host the request arrives on."""
    settings.FRONTEND_URL = FRONTEND_URL
    settings.ALLOWED_HOSTS = [BACKEND_HOST, "testserver"]


@pytest.mark.django_db
def test_every_loc_uses_the_frontend_domain_not_the_request_host():
    PostFactory.create_batch(3)

    locs = parse_locs(render_sitemaps({"blog": BlogSitemap}).content)

    assert len(locs) == 3
    for loc in locs:
        parsed = urlparse(loc)
        assert parsed.netloc == FRONTEND.netloc, loc
        assert parsed.scheme == FRONTEND.scheme, loc
        assert BACKEND_HOST not in loc and "testserver" not in loc, loc


@pytest.mark.django_db
def test_persian_titled_post_has_a_transliterated_non_empty_slug_in_its_loc():
    post = PostFactory(title="راهنمای خرید ضدآفتاب", slug="")
    post.refresh_from_db()
    assert post.slug and post.slug.isascii()  # Epic 14's persian_slugify, not ''

    locs = parse_locs(render_sitemaps({"blog": BlogSitemap}).content)

    assert locs == [f"{FRONTEND_URL}/blog/{post.slug}"]


@pytest.mark.django_db
def test_uses_the_spas_blog_route_without_a_trailing_slash():
    PostFactory(title="Hello", slug="hello-world")

    locs = parse_locs(render_sitemaps({"blog": BlogSitemap}).content)

    assert locs == [f"{FRONTEND_URL}/blog/hello-world"]  # SPA route is /blog/:slug


@pytest.mark.django_db
def test_only_published_posts_are_listed():
    PostFactory(slug="live-post")
    DraftPostFactory(slug="draft-post")

    locs = parse_locs(render_sitemaps({"blog": BlogSitemap}).content)

    assert locs == [f"{FRONTEND_URL}/blog/live-post"]


@pytest.mark.django_db
def test_reflects_the_current_slug_and_a_lastmod():
    post = PostFactory(slug="old-slug")
    Post.objects.filter(pk=post.pk).update(slug="new-slug")

    response = render_sitemaps({"blog": BlogSitemap})

    assert parse_locs(response.content) == [f"{FRONTEND_URL}/blog/new-slug"]
    assert "<lastmod>" in response.content.decode()  # from updated_at


@pytest.mark.django_db
def test_a_blank_slug_row_is_skipped():
    post = PostFactory(slug="soon-blank")
    Post.objects.filter(pk=post.pk).update(slug="")
    PostFactory(slug="fine")

    locs = parse_locs(render_sitemaps({"blog": BlogSitemap}).content)

    assert locs == [f"{FRONTEND_URL}/blog/fine"]
