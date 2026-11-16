"""FrontendDomainSitemapMixin: sitemap URLs must describe the SPA, not the Django host."""

import pytest
from core.sitemaps import FrontendDomainSitemapMixin, frontend_slug
from django.contrib.sitemaps import Sitemap
from django.core.exceptions import ImproperlyConfigured


class FakeSite:
    """What Django passes for the request host; must be ignored."""

    domain = "api.chiz.example"


class Pages(FrontendDomainSitemapMixin, Sitemap):
    def items(self):
        return ["a", "b c"]

    def location(self, obj):
        return f"/page/{frontend_slug(obj)}"


class TestDomainAndProtocol:
    def test_domain_and_scheme_come_from_frontend_url_not_the_site(self, settings):
        settings.FRONTEND_URL = "https://chiz.example"
        page = Pages()
        assert page.get_domain(FakeSite()) == "chiz.example"
        assert page.get_protocol("https") == "https"

    def test_site_is_ignored_even_when_none(self, settings):
        """Django's own get_domain(None) raises without the sites framework."""
        settings.FRONTEND_URL = "https://chiz.example"
        assert Pages().get_domain(None) == "chiz.example"
        urls = Pages().get_urls(site=None)
        assert [u["location"] for u in urls] == [
            "https://chiz.example/page/a",
            "https://chiz.example/page/b%20c",
        ]

    def test_keeps_the_frontend_scheme_instead_of_forcing_https(self, settings):
        settings.FRONTEND_URL = "http://localhost:3000"
        urls = Pages().get_urls(site=FakeSite(), protocol="https")
        assert urls[0]["location"] == "http://localhost:3000/page/a"

    @pytest.mark.parametrize(
        "configured", ["https://chiz.example/", "https://chiz.example//"]
    )
    def test_trailing_slash_does_not_double_up(self, settings, configured):
        settings.FRONTEND_URL = configured
        assert Pages().get_urls()[0]["location"] == "https://chiz.example/page/a"

    def test_honours_a_path_prefix_like_every_other_use_of_the_setting(self, settings):
        settings.FRONTEND_URL = "https://chiz.example/shop/"
        assert Pages().get_urls()[0]["location"] == "https://chiz.example/shop/page/a"

    def test_port_is_kept(self, settings):
        settings.FRONTEND_URL = "https://chiz.example:8443"
        assert (
            Pages().get_urls()[0]["location"].startswith("https://chiz.example:8443/")
        )


class TestMisconfiguration:
    @pytest.mark.parametrize(
        "bad",
        ["", None, "chiz.example", "//chiz.example", "ftp://chiz.example", "https://"],
    )
    def test_fails_loudly_instead_of_emitting_broken_urls(self, settings, bad):
        settings.FRONTEND_URL = bad
        with pytest.raises(ImproperlyConfigured, match="FRONTEND_URL"):
            Pages().get_urls()


class TestFrontendSlug:
    def test_ascii_slugs_are_unchanged(self):
        assert frontend_slug("serum-vitamin-c_2.0~x") == "serum-vitamin-c_2.0~x"

    def test_everything_else_is_percent_encoded(self):
        assert frontend_slug("سرم") == "%D8%B3%D8%B1%D9%85"
        assert frontend_slug("a b&c=d/e?f") == "a%20b%26c%3Dd%2Fe%3Ff"
