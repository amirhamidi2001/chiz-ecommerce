"""Tests for blog/migrations/0002_regenerate_persian_slugs.py (Task 14.4.1.2)."""

import importlib

import pytest
from blog.models import Category, Post
from django.apps import apps

migration = importlib.import_module("blog.migrations.0002_regenerate_persian_slugs")


def legacy(model, slug="", **kw):
    obj = model.objects.create(**kw)
    model.objects.filter(pk=obj.pk).update(slug=slug)
    return obj


def slug_of(obj):
    return type(obj).objects.get(pk=obj.pk).slug


@pytest.mark.django_db
class TestBlogSlugMigration:
    def test_before_after(self):
        cat = legacy(Category, name="مقالات آموزشی")
        post = legacy(Post, title="راهنمای ضدآفتاب", content="x")
        mixed = legacy(Post, title="سرم ویتامین C", content="y", slug="c")
        assert (slug_of(cat), slug_of(post), slug_of(mixed)) == ("", "", "c")

        migration.regenerate_slugs(apps, None)

        assert slug_of(cat) == "mqalat-amuzshi"
        assert slug_of(post) == "rahnmay-zdaftab"
        assert slug_of(mixed) == "serum-vitamin-c"

    def test_hand_set_and_latin_slugs_untouched_and_idempotent(self):
        keep = legacy(Post, title="راهنمای ضدآفتاب", content="x", slug="custom")
        latin = legacy(
            Post, title="Sunscreen Guide", content="x", slug="sunscreen-guide"
        )
        migration.regenerate_slugs(apps, None)
        migration.regenerate_slugs(apps, None)
        assert (slug_of(keep), slug_of(latin)) == ("custom", "sunscreen-guide")
