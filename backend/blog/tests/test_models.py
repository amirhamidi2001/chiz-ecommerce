import pytest
from blog.models import Category, Comment, Post
from blog.tests.conftest import (
    CategoryFactory,
    CommentFactory,
    PostFactory,
    ReplyFactory,
)
from django.db import IntegrityError
from django.utils.text import slugify

# ═══════════════════════════════════════════════════════════════════════════════
# Category
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestCategoryModel:

    def test_str_returns_name(self):
        cat = CategoryFactory(name="Technology")
        assert str(cat) == "Technology"

    def test_slug_auto_generated_from_name(self):
        cat = CategoryFactory(name="Web Development")
        assert cat.slug == "web-development"

    def test_slug_not_overwritten_when_already_set(self):
        cat = CategoryFactory(name="Django Tips", slug="my-custom-slug")
        assert cat.slug == "my-custom-slug"

    def test_slug_uses_slugify_logic(self):
        cat = CategoryFactory(name="C++ & Algorithms!")
        assert cat.slug == slugify("C++ & Algorithms!")

    def test_name_must_be_unique(self):
        CategoryFactory(name="Duplicate")
        with pytest.raises(IntegrityError):
            CategoryFactory(name="Duplicate")

    def test_slug_must_be_unique(self):
        CategoryFactory(name="Alpha", slug="same-slug")
        with pytest.raises(IntegrityError):
            CategoryFactory(name="Beta", slug="same-slug")

    def test_default_ordering_is_alphabetical(self):
        CategoryFactory(name="Zebra")
        CategoryFactory(name="Apple")
        CategoryFactory(name="Mango")
        names = list(Category.objects.values_list("name", flat=True))
        assert names == sorted(names)

    def test_verbose_name_plural(self):
        assert Category._meta.verbose_name_plural == "categories"


# ═══════════════════════════════════════════════════════════════════════════════
# Post
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestPostModel:

    # ── Defaults ──────────────────────────────────────────────────────────────

    def test_default_status_is_draft(self):
        # PostFactory defaults to PUBLISHED; create one explicitly without status
        post = Post.objects.create(
            title="Bare Post",
            content="hello world",
        )
        assert post.status == Post.Status.DRAFT

    def test_default_is_featured_false(self):
        post = PostFactory()
        assert post.is_featured is False

    def test_default_views_count_zero(self):
        post = PostFactory()
        assert post.views_count == 0

    def test_published_at_is_nullable(self):
        post = PostFactory(published_at=None)
        assert post.published_at is None

    # ── Status choices ────────────────────────────────────────────────────────

    def test_status_choices_values(self):
        assert Post.Status.DRAFT == "draft"
        assert Post.Status.PUBLISHED == "published"

    # ── Auto-slug ─────────────────────────────────────────────────────────────

    def test_slug_auto_generated_from_title(self):
        post = PostFactory(title="Hello World Post")
        assert post.slug == "hello-world-post"

    def test_slug_not_overwritten_when_provided(self):
        post = PostFactory(title="Some Title", slug="my-custom-slug")
        assert post.slug == "my-custom-slug"

    def test_slug_must_be_unique(self):
        PostFactory(title="Unique Title", slug="fixed-slug")
        with pytest.raises(IntegrityError):
            PostFactory(title="Another Title", slug="fixed-slug")

    # ── Auto-read_time ────────────────────────────────────────────────────────

    def test_read_time_minimum_is_one(self):
        # Single word → round(1/200) = 0 → max(1, 0) = 1
        post = PostFactory(content="hello")
        assert post.read_time == 1

    def test_read_time_for_empty_content(self):
        # Edge-case: no words at all
        post = PostFactory(content="   ")
        assert post.read_time == 1

    def test_read_time_for_exactly_200_words(self):
        content = " ".join(["word"] * 200)
        post = PostFactory(content=content)
        assert post.read_time == 1  # round(200/200) = 1

    def test_read_time_for_400_words(self):
        content = " ".join(["word"] * 400)
        post = PostFactory(content=content)
        assert post.read_time == 2  # round(400/200) = 2

    def test_read_time_for_800_words(self):
        content = " ".join(["word"] * 800)
        post = PostFactory(content=content)
        assert post.read_time == 4  # round(800/200) = 4

    def test_read_time_recalculated_on_update(self):
        post = PostFactory(content=" ".join(["word"] * 200))
        assert post.read_time == 1
        post.content = " ".join(["word"] * 400)
        post.save()
        post.refresh_from_db()
        assert post.read_time == 2

    # ── FK behaviour ──────────────────────────────────────────────────────────

    def test_post_can_have_no_category(self):
        post = PostFactory(category=None)
        assert post.category is None

    # ── Ordering ──────────────────────────────────────────────────────────────

    def test_default_ordering_is_newest_first(self):
        p3 = PostFactory()
        pks = list(Post.objects.values_list("pk", flat=True))
        # Newest (largest PK in sequential creation) should be first
        assert pks[0] == p3.pk

    # ── __str__ ───────────────────────────────────────────────────────────────

    def test_str_returns_title(self):
        post = PostFactory(title="My Great Post")
        assert str(post) == "My Great Post"


# ═══════════════════════════════════════════════════════════════════════════════
# Comment
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestCommentModel:

    def test_str_includes_name_and_post_title(self):
        post = PostFactory(title="Django Secrets")
        comment = CommentFactory(post=post, name="Alice")
        assert str(comment) == "Comment by Alice on «Django Secrets»"

    def test_default_is_approved_true(self):
        comment = CommentFactory()
        assert comment.is_approved is True

    def test_top_level_comment_has_no_parent(self):
        comment = CommentFactory(parent=None)
        assert comment.parent is None

    def test_reply_links_to_parent(self):
        parent = CommentFactory()
        reply = CommentFactory(post=parent.post, parent=parent)
        assert reply.parent == parent
        assert reply.parent.pk == parent.pk

    def test_reply_accessible_via_replies_reverse_relation(self):
        parent = CommentFactory()
        reply = CommentFactory(post=parent.post, parent=parent)
        assert reply in parent.replies.all()

    def test_website_is_optional(self):
        comment = CommentFactory(website="")
        assert comment.website == ""

    def test_comment_cascades_on_post_delete(self):
        post = PostFactory()
        CommentFactory(post=post)
        CommentFactory(post=post)
        post.delete()
        assert Comment.objects.count() == 0

    def test_reply_cascades_on_parent_delete(self):
        parent = CommentFactory()
        ReplyFactory(parent=parent)
        parent.delete()
        # Cascade: reply is also deleted
        assert Comment.objects.count() == 0

    def test_ordering_is_oldest_first(self):
        post = PostFactory()
        c1 = CommentFactory(post=post)
        c2 = CommentFactory(post=post)
        comments = list(post.comments.all())
        assert comments[0].pk == c1.pk
        assert comments[1].pk == c2.pk

    def test_comments_accessible_via_reverse_relation(self):
        post = PostFactory()
        c1 = CommentFactory(post=post)
        c2 = CommentFactory(post=post)
        assert set(post.comments.all()) == {c1, c2}

    def test_unapproved_comment_is_persisted(self):
        comment = CommentFactory(is_approved=False)
        comment.refresh_from_db()
        assert comment.is_approved is False
