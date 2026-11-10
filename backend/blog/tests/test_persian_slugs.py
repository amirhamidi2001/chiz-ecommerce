"""Task 14.4.1.2: the blog models had the same plain-slugify() bug (ADR 0002)."""

import pytest
from blog.models import Category, Post


@pytest.mark.django_db
class TestPersianBlogSlugs:
    def test_category_slug(self):
        assert (
            Category.objects.create(name="راهنمای مراقبت از پوست").slug
            == "rahnmay-mraqbt-az-pust"
        )

    def test_post_slug_with_mixed_script_title(self):
        post = Post.objects.create(title="راهنمای ویتامین C", content="x")
        assert post.slug == "rahnmay-vitamin-c"

    def test_post_collision_loop(self):
        a = Post.objects.create(title="ضدآفتاب", content="x")
        b = Post.objects.create(title="ضدآفتاب ", content="y")
        assert (a.slug, b.slug) == ("zdaftab", "zdaftab-1")

    def test_two_persian_categories_do_not_crash(self):
        Category.objects.create(name="مقالات")  # old behaviour: slug ''
        Category.objects.create(name="اخبار")  # old behaviour: IntegrityError
        assert Category.objects.filter(slug="").count() == 0

    def test_fallbacks_and_explicit_slug(self):
        assert Post.objects.create(title="!!!", content="x").slug == "post"
        assert Category.objects.create(name="!!!").slug == "category"
        assert (
            Post.objects.create(title="ضدآفتاب", content="x", slug="mine").slug
            == "mine"
        )
