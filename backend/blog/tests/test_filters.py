import pytest
from blog.filters import PostFilter
from blog.models import Post
from blog.tests.conftest import CategoryFactory, PostFactory


@pytest.mark.django_db
class TestPostFilter:

    def _published_qs(self):
        """Base queryset identical to the one used by PostListView."""
        return Post.objects.filter(status=Post.Status.PUBLISHED)

    # ── Category filter ───────────────────────────────────────────────────────

    def test_category_filter_returns_matching_posts(self):
        cat = CategoryFactory(slug="python")
        PostFactory(category=cat)
        PostFactory(category=cat)
        PostFactory()  # Different auto-generated category

        f = PostFilter({"category": "python"}, queryset=self._published_qs())
        assert f.qs.count() == 2

    def test_category_filter_returns_nothing_for_unknown_slug(self):
        PostFactory()
        f = PostFilter({"category": "does-not-exist"}, queryset=self._published_qs())
        assert f.qs.count() == 0

    def test_category_filter_empty_string_returns_all(self):
        PostFactory()
        PostFactory()
        f = PostFilter({"category": ""}, queryset=self._published_qs())
        assert f.qs.count() == 2

    def test_category_filter_is_exact_not_partial_match(self):
        cat = CategoryFactory(slug="python-tips")
        PostFactory(category=cat)
        # 'python' should NOT match 'python-tips' (exact lookup)
        f = PostFilter({"category": "python"}, queryset=self._published_qs())
        assert f.qs.count() == 0

    # ── is_featured filter ────────────────────────────────────────────────────

    def test_is_featured_true_returns_only_featured(self):
        PostFactory(is_featured=True)
        PostFactory(is_featured=True)
        PostFactory(is_featured=False)

        f = PostFilter({"is_featured": "true"}, queryset=self._published_qs())
        assert f.qs.count() == 2
        assert all(p.is_featured for p in f.qs)

    def test_is_featured_false_returns_only_non_featured(self):
        PostFactory(is_featured=True)
        PostFactory(is_featured=False)
        PostFactory(is_featured=False)

        f = PostFilter({"is_featured": "false"}, queryset=self._published_qs())
        assert f.qs.count() == 2
        assert not any(p.is_featured for p in f.qs)

    def test_is_featured_absent_returns_all(self):
        PostFactory(is_featured=True)
        PostFactory(is_featured=False)

        f = PostFilter({}, queryset=self._published_qs())
        assert f.qs.count() == 2

    # ── Combined filters ──────────────────────────────────────────────────────

    def test_category_and_is_featured_combined(self):
        cat = CategoryFactory(slug="django")
        PostFactory(category=cat, is_featured=True)
        PostFactory(category=cat, is_featured=False)
        PostFactory(is_featured=True)  # Different category, featured

        f = PostFilter(
            {"category": "django", "is_featured": "true"},
            queryset=self._published_qs(),
        )
        assert f.qs.count() == 1
        assert f.qs.first().category.slug == "django"
        assert f.qs.first().is_featured is True

    # ── Draft posts are not in the base qs ────────────────────────────────────

    def test_filter_does_not_surface_draft_posts(self):
        cat = CategoryFactory(slug="misc")
        PostFactory(category=cat, status=Post.Status.DRAFT)
        PostFactory(category=cat, status=Post.Status.PUBLISHED)

        f = PostFilter({"category": "misc"}, queryset=self._published_qs())
        assert f.qs.count() == 1
        assert f.qs.first().status == Post.Status.PUBLISHED
