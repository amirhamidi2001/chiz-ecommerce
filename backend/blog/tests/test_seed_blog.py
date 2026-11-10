"""Task 14.4.1.3 - the real ``seed_blog`` command, end to end (ADR 0002)."""

import re
from io import StringIO

import pytest
from blog.models import Category, Comment, Post
from django.contrib.auth import get_user_model
from django.core.management import call_command

VALID = re.compile(r"^[a-z0-9_]+(-[a-z0-9_]+)*$")


def seed(*args):
    out = StringIO()
    call_command("seed_blog", *args, stdout=out)
    return out.getvalue()


@pytest.fixture
def seeded(db):
    seed()


def test_works_on_a_fresh_database_with_no_users(db):
    # Regression: it used to crash in create_user(username=...) - no such field.
    assert get_user_model().objects.count() == 0
    seed()
    assert get_user_model().objects.count() == 3
    assert Post.objects.count() == 12


def test_nothing_is_empty_or_malformed(seeded):
    assert not Post.objects.filter(slug="").exists()
    assert not Category.objects.filter(slug="").exists()
    for model in (Post, Category):
        assert all(VALID.match(s) for s in model.objects.values_list("slug", flat=True))


@pytest.mark.parametrize(
    "title, expected",
    [
        (
            "۵ اشتباه رایج در شستشوی صورت",
            "5-ashtbah-rayj-dr-shstshui-surt",
        ),  # Persian digit
        (
            "ویتامین C چیست و چه فوایدی برای پوست دارد؟",
            "vitamin-c-chist-va-che-fuaydi-bray-pust-dard",
        ),  # mixed script
        (
            "ترتیب صحیح استفاده از سرم و مرطوب\u200cکننده",
            "trtib-shih-astfade-az-serum-va-mrtub-knnde",
        ),  # ZWNJ
    ],
)
def test_post_slugs(seeded, title, expected):
    assert Post.objects.get(title=title).slug == expected


def test_category_slugs(seeded):
    assert Category.objects.get(name="عطر و ادکلن").slug == "atr-va-cologne"
    assert (
        Category.objects.get(name="راهنمای مراقبت از پوست").slug
        == "rahnmay-mraqbt-az-pust"
    )


def test_rerun_is_idempotent_and_non_destructive(seeded):
    keep = Post.objects.create(title="مقاله دستی", content="x")
    before = sorted(Post.objects.values_list("slug", flat=True))
    out = seed()
    assert "Posts: 0 new" in out
    assert sorted(Post.objects.values_list("slug", flat=True)) == before
    assert Post.objects.filter(
        pk=keep.pk
    ).exists()  # no longer wipes the blog on every run


def test_clear_wipes_then_reseeds_the_same_slugs(seeded):
    before = sorted(Post.objects.values_list("slug", flat=True))
    Post.objects.create(title="مقاله دستی", content="x")
    seed("--clear")
    assert sorted(Post.objects.values_list("slug", flat=True)) == before
    assert Comment.objects.count() == 40


def test_asking_for_more_posts_than_titles_does_not_duplicate(db):
    seed("--posts", "14")  # the 12 titles repeat, but get_or_create(title) dedupes
    assert Post.objects.count() == 12
