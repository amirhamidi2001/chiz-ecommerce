import pytest
from blog.models import Comment, Post
from blog.tests.conftest import (
    CategoryFactory,
    CommentFactory,
    DraftPostFactory,
    PostFactory,
    ReplyFactory,
)
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

# ─── URL helpers ─────────────────────────────────────────────────────────────


def url_categories():
    return reverse("blog:category-list")  # /api/blog/categories/


def url_posts():
    return reverse("blog:post-list")  # /api/blog/posts/


def url_post_detail(slug):
    return reverse("blog:post-detail", kwargs={"slug": slug})


def url_related(slug):
    return reverse("blog:post-related", kwargs={"slug": slug})


def url_comments(slug):
    return reverse("blog:comment-create", kwargs={"slug": slug})


@pytest.fixture
def client():
    return APIClient()


# ═══════════════════════════════════════════════════════════════════════════════
# CategoryListView  — GET /api/blog/categories/
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestCategoryListView:

    def test_returns_200(self, client):
        response = client.get(url_categories())
        assert response.status_code == status.HTTP_200_OK

    def test_unauthenticated_access_allowed(self, client):
        # No token attached — should still return 200
        response = client.get(url_categories())
        assert response.status_code == status.HTTP_200_OK

    def test_empty_list_when_no_categories_with_published_posts(self, client):
        CategoryFactory()  # exists but has no posts
        response = client.get(url_categories())
        assert response.data == []

    def test_returns_only_categories_with_published_posts(self, client):
        cat_with_post = CategoryFactory()
        PostFactory(category=cat_with_post, status=Post.Status.PUBLISHED)
        CategoryFactory()  # no posts — should be excluded

        response = client.get(url_categories())
        assert len(response.data) == 1
        assert response.data[0]["slug"] == cat_with_post.slug

    def test_excludes_categories_with_only_draft_posts(self, client):
        cat = CategoryFactory()
        DraftPostFactory(category=cat)
        response = client.get(url_categories())
        assert response.data == []

    def test_post_count_annotation_is_correct(self, client):
        cat = CategoryFactory()
        PostFactory(category=cat)
        PostFactory(category=cat)
        DraftPostFactory(category=cat)  # draft — should NOT count

        response = client.get(url_categories())
        assert response.data[0]["post_count"] == 2

    def test_ordered_alphabetically_by_name(self, client):
        for name in ["Zebra", "Apple", "Mango"]:
            cat = CategoryFactory(name=name)
            PostFactory(category=cat)

        response = client.get(url_categories())
        names = [c["name"] for c in response.data]
        assert names == sorted(names)

    def test_response_shape_per_category(self, client):
        cat = CategoryFactory()
        PostFactory(category=cat)
        response = client.get(url_categories())
        keys = set(response.data[0].keys())
        assert keys == {"id", "name", "slug", "post_count"}

    def test_multiple_categories_all_returned(self, client):
        for _ in range(3):
            cat = CategoryFactory()
            PostFactory(category=cat)
        response = client.get(url_categories())
        assert len(response.data) == 3


# ═══════════════════════════════════════════════════════════════════════════════
# PostListView  — GET /api/blog/posts/
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestPostListView:

    # ── Auth & basic status ───────────────────────────────────────────────────

    def test_returns_200(self, client):
        response = client.get(url_posts())
        assert response.status_code == status.HTTP_200_OK

    def test_unauthenticated_access_allowed(self, client):
        response = client.get(url_posts())
        assert response.status_code == status.HTTP_200_OK

    # ── Published/draft filtering ─────────────────────────────────────────────

    def test_returns_only_published_posts(self, client):
        PostFactory(status=Post.Status.PUBLISHED)
        DraftPostFactory()
        response = client.get(url_posts())
        assert response.data["count"] == 1

    def test_draft_posts_not_in_results(self, client):
        draft = DraftPostFactory()
        pub = PostFactory(status=Post.Status.PUBLISHED)
        response = client.get(url_posts())
        slugs = [p["slug"] for p in response.data["results"]]
        assert draft.slug not in slugs
        assert pub.slug in slugs

    def test_empty_results_when_no_published_posts(self, client):
        DraftPostFactory.create_batch(3)
        response = client.get(url_posts())
        assert response.data["count"] == 0
        assert response.data["results"] == []

    # ── Response shape ────────────────────────────────────────────────────────

    def test_result_item_does_not_expose_content(self, client):
        PostFactory()
        response = client.get(url_posts())
        assert "content" not in response.data["results"][0]

    def test_result_item_exposes_slug(self, client):
        PostFactory(slug="my-test-post")
        response = client.get(url_posts())
        assert response.data["results"][0]["slug"] == "my-test-post"

    def test_result_item_nested_category(self, client):
        cat = CategoryFactory(name="Tech")
        PostFactory(category=cat)
        response = client.get(url_posts())
        assert response.data["results"][0]["category"]["name"] == "Tech"

    # ── Default ordering ──────────────────────────────────────────────────────

    def test_default_ordering_is_newest_first(self, client):
        p3 = PostFactory()
        response = client.get(url_posts())
        slugs = [p["slug"] for p in response.data["results"]]
        assert slugs[0] == p3.slug

    # ── Category filter ───────────────────────────────────────────────────────

    def test_category_filter_returns_matching_posts(self, client):
        cat = CategoryFactory(slug="python")
        PostFactory(category=cat)
        PostFactory()  # different category
        response = client.get(url_posts() + "?category=python")
        assert response.data["count"] == 1
        assert response.data["results"][0]["category"]["slug"] == "python"

    def test_category_filter_empty_returns_all(self, client):
        PostFactory()
        PostFactory()
        response = client.get(url_posts() + "?category=")
        assert response.data["count"] == 2

    def test_category_filter_unknown_slug_returns_nothing(self, client):
        PostFactory()
        response = client.get(url_posts() + "?category=unknown-xyz")
        assert response.data["count"] == 0

    # ── is_featured filter ────────────────────────────────────────────────────

    def test_is_featured_true_returns_only_featured(self, client):
        PostFactory(is_featured=True)
        PostFactory(is_featured=False)
        response = client.get(url_posts() + "?is_featured=true")
        assert response.data["count"] == 1
        assert response.data["results"][0]["is_featured"] is True

    def test_is_featured_false_returns_only_non_featured(self, client):
        PostFactory(is_featured=True)
        PostFactory(is_featured=False)
        response = client.get(url_posts() + "?is_featured=false")
        assert response.data["count"] == 1
        assert response.data["results"][0]["is_featured"] is False

    # ── Search ────────────────────────────────────────────────────────────────

    def test_search_matches_title(self, client):
        PostFactory(title="Django ORM Deep Dive")
        PostFactory(title="React Hooks Explained")
        response = client.get(url_posts() + "?search=Django")
        assert response.data["count"] == 1
        assert "Django" in response.data["results"][0]["title"]

    def test_search_matches_excerpt(self, client):
        PostFactory(excerpt="An exclusive look at async views")
        PostFactory(excerpt="A guide to CSS grid")
        response = client.get(url_posts() + "?search=exclusive")
        assert response.data["count"] == 1

    def test_search_matches_content(self, client):
        PostFactory(content="This post covers advanced metaclass usage in Python")
        PostFactory(content="This post is about REST APIs")
        response = client.get(url_posts() + "?search=metaclass")
        assert response.data["count"] == 1

    def test_search_is_case_insensitive(self, client):
        PostFactory(title="Python Testing Guide")
        response = client.get(url_posts() + "?search=python")
        assert response.data["count"] == 1

    def test_search_no_match_returns_empty(self, client):
        PostFactory(title="Python Testing")
        response = client.get(url_posts() + "?search=zzznomatch")
        assert response.data["count"] == 0

    # ── Ordering ──────────────────────────────────────────────────────────────

    def test_ordering_by_views_count_descending(self, client):
        low = PostFactory(views_count=5)
        high = PostFactory(views_count=100)
        response = client.get(url_posts() + "?ordering=-views_count")
        slugs = [p["slug"] for p in response.data["results"]]
        assert slugs[0] == high.slug
        assert slugs[-1] == low.slug

    def test_ordering_by_views_count_ascending(self, client):
        PostFactory(views_count=100)
        low = PostFactory(views_count=1)
        response = client.get(url_posts() + "?ordering=views_count")
        assert response.data["results"][0]["slug"] == low.slug

    def test_disallowed_ordering_field_is_ignored(self, client):
        # Ordering by 'id' is not in ordering_fields; should fall back to default
        PostFactory.create_batch(3)
        response = client.get(url_posts() + "?ordering=id")
        assert response.status_code == status.HTTP_200_OK


# ═══════════════════════════════════════════════════════════════════════════════
# PostDetailView  — GET /api/blog/posts/<slug>/
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestPostDetailView:

    # ── Auth & HTTP status ────────────────────────────────────────────────────

    def test_returns_200_for_published_post(self, client):
        post = PostFactory()
        response = client.get(url_post_detail(post.slug))
        assert response.status_code == status.HTTP_200_OK

    def test_unauthenticated_access_allowed(self, client):
        post = PostFactory()
        response = client.get(url_post_detail(post.slug))
        assert response.status_code == status.HTTP_200_OK

    def test_returns_404_for_draft_post(self, client):
        draft = DraftPostFactory()
        response = client.get(url_post_detail(draft.slug))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_returns_404_for_nonexistent_slug(self, client):
        response = client.get(url_post_detail("slug-that-does-not-exist"))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    # ── Response shape ────────────────────────────────────────────────────────

    def test_response_includes_content_field(self, client):
        post = PostFactory(content="Full article body here.")
        response = client.get(url_post_detail(post.slug))
        assert response.data["content"] == "Full article body here."

    def test_response_includes_comments_and_comments_count(self, client):
        post = PostFactory()
        response = client.get(url_post_detail(post.slug))
        assert "comments" in response.data
        assert "comments_count" in response.data

    def test_response_includes_nested_category(self, client):
        cat = CategoryFactory(name="OS Design")
        post = PostFactory(category=cat)
        response = client.get(url_post_detail(post.slug))
        assert response.data["category"]["name"] == "OS Design"

    # ── View counter ──────────────────────────────────────────────────────────

    def test_views_count_incremented_in_db_on_each_request(self, client):
        post = PostFactory(views_count=0)
        client.get(url_post_detail(post.slug))
        post.refresh_from_db()
        assert post.views_count == 1

    def test_views_count_increments_cumulatively(self, client):
        post = PostFactory(views_count=0)
        client.get(url_post_detail(post.slug))
        client.get(url_post_detail(post.slug))
        client.get(url_post_detail(post.slug))
        post.refresh_from_db()
        assert post.views_count == 3

    def test_views_count_on_draft_is_not_incremented(self, client):
        draft = DraftPostFactory(views_count=0)
        client.get(url_post_detail(draft.slug))  # 404 — no increment
        draft.refresh_from_db()
        assert draft.views_count == 0

    # ── Comments in response ──────────────────────────────────────────────────

    def test_approved_comments_returned_in_response(self, client):
        post = PostFactory()
        c1 = CommentFactory(post=post, is_approved=True)
        c2 = CommentFactory(post=post, is_approved=True)
        response = client.get(url_post_detail(post.slug))
        ids = {c["id"] for c in response.data["comments"]}
        assert ids == {c1.pk, c2.pk}

    def test_unapproved_comments_excluded_from_response(self, client):
        post = PostFactory()
        CommentFactory(post=post, is_approved=False)
        response = client.get(url_post_detail(post.slug))
        assert response.data["comments"] == []
        assert response.data["comments_count"] == 0

    def test_replies_not_in_top_level_comments(self, client):
        post = PostFactory()
        parent = CommentFactory(post=post, is_approved=True)
        ReplyFactory(parent=parent)
        response = client.get(url_post_detail(post.slug))
        assert len(response.data["comments"]) == 1
        assert response.data["comments"][0]["id"] == parent.pk

    def test_replies_nested_inside_parent_comment(self, client):
        post = PostFactory()
        parent = CommentFactory(post=post, is_approved=True)
        reply = ReplyFactory(parent=parent)
        response = client.get(url_post_detail(post.slug))
        assert len(response.data["comments"][0]["replies"]) == 1
        assert response.data["comments"][0]["replies"][0]["id"] == reply.pk

    def test_comments_count_includes_replies(self, client):
        post = PostFactory()
        parent = CommentFactory(post=post, is_approved=True)
        ReplyFactory(parent=parent)
        response = client.get(url_post_detail(post.slug))
        assert response.data["comments_count"] == 2

    def test_comments_count_excludes_unapproved(self, client):
        post = PostFactory()
        CommentFactory(post=post, is_approved=True)
        CommentFactory(post=post, is_approved=False)
        response = client.get(url_post_detail(post.slug))
        assert response.data["comments_count"] == 1

    def test_slug_lookup_is_case_sensitive(self, client):
        PostFactory(slug="my-post")
        response = client.get(url_post_detail("My-Post"))
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ═══════════════════════════════════════════════════════════════════════════════
# RelatedPostsView  — GET /api/blog/posts/<slug>/related/
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestRelatedPostsView:

    def test_returns_200_for_published_post(self, client):
        post = PostFactory()
        response = client.get(url_related(post.slug))
        assert response.status_code == status.HTTP_200_OK

    def test_unauthenticated_access_allowed(self, client):
        post = PostFactory()
        response = client.get(url_related(post.slug))
        assert response.status_code == status.HTTP_200_OK

    def test_returns_404_for_draft_post(self, client):
        draft = DraftPostFactory()
        response = client.get(url_related(draft.slug))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_returns_404_for_nonexistent_slug(self, client):
        response = client.get(url_related("no-such-post"))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_excludes_the_post_itself(self, client):
        cat = CategoryFactory()
        post = PostFactory(category=cat)
        related = PostFactory(category=cat)
        response = client.get(url_related(post.slug))
        slugs = [p["slug"] for p in response.data]
        assert post.slug not in slugs
        assert related.slug in slugs

    def test_returns_posts_from_same_category(self, client):
        cat = CategoryFactory()
        other_cat = CategoryFactory()
        post = PostFactory(category=cat)
        PostFactory(category=cat)
        PostFactory(category=other_cat)
        response = client.get(url_related(post.slug))
        for item in response.data:
            assert item["category"]["slug"] == cat.slug

    def test_returns_maximum_three_posts(self, client):
        cat = CategoryFactory()
        post = PostFactory(category=cat)
        PostFactory.create_batch(5, category=cat)
        response = client.get(url_related(post.slug))
        assert len(response.data) <= 3

    def test_fallback_to_latest_when_no_category_match(self, client):
        # Post with no category — should fall back to latest published posts
        post = PostFactory(category=None)
        fallback1 = PostFactory()
        fallback2 = PostFactory()
        response = client.get(url_related(post.slug))
        slugs = [p["slug"] for p in response.data]
        assert fallback1.slug in slugs or fallback2.slug in slugs

    def test_fallback_when_category_has_no_other_posts(self, client):
        # Category exists but the post is the only one in it
        cat = CategoryFactory()
        post = PostFactory(category=cat)
        response = client.get(url_related(post.slug))
        # Fallback fires; should return the other post
        slugs = [p["slug"] for p in response.data]
        assert post.slug not in slugs

    def test_excludes_draft_posts_from_related(self, client):
        cat = CategoryFactory()
        post = PostFactory(category=cat)
        draft = DraftPostFactory(category=cat)
        response = client.get(url_related(post.slug))
        slugs = [p["slug"] for p in response.data]
        assert draft.slug not in slugs

    def test_response_is_list_not_paginated(self, client):
        cat = CategoryFactory()
        post = PostFactory(category=cat)
        PostFactory(category=cat)
        response = client.get(url_related(post.slug))
        # RelatedPostsView has no pagination — raw list
        assert isinstance(response.data, list)

    def test_returns_empty_list_when_no_other_posts_exist(self, client):
        post = PostFactory(category=None)
        response = client.get(url_related(post.slug))
        assert response.data == []


# ═══════════════════════════════════════════════════════════════════════════════
# CommentCreateView  — POST /api/blog/posts/<slug>/comments/
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestCommentCreateView:

    VALID_PAYLOAD = {
        "name": "Alice Smith",
        "email": "alice@example.com",
        "body": "This is a thoughtful comment.",
    }

    # ── Happy path ────────────────────────────────────────────────────────────

    def test_returns_201_on_valid_data(self, client):
        post = PostFactory()
        response = client.post(url_comments(post.slug), self.VALID_PAYLOAD)
        assert response.status_code == status.HTTP_201_CREATED

    def test_unauthenticated_user_can_post_comment(self, client):
        post = PostFactory()
        response = client.post(url_comments(post.slug), self.VALID_PAYLOAD)
        assert response.status_code == status.HTTP_201_CREATED

    def test_comment_linked_to_correct_post(self, client):
        post = PostFactory()
        client.post(url_comments(post.slug), self.VALID_PAYLOAD)
        comment = Comment.objects.get()
        assert comment.post == post

    def test_comment_attributes_saved_correctly(self, client):
        post = PostFactory()
        client.post(url_comments(post.slug), self.VALID_PAYLOAD)
        comment = Comment.objects.get()
        assert comment.name == "Alice Smith"
        assert comment.email == "alice@example.com"
        assert comment.body == "This is a thoughtful comment."

    def test_comment_is_approved_by_default(self, client):
        post = PostFactory()
        client.post(url_comments(post.slug), self.VALID_PAYLOAD)
        comment = Comment.objects.get()
        assert comment.is_approved is True

    def test_comment_has_no_parent_by_default(self, client):
        post = PostFactory()
        client.post(url_comments(post.slug), self.VALID_PAYLOAD)
        comment = Comment.objects.get()
        assert comment.parent is None

    def test_response_body_contains_new_comment_id(self, client):
        post = PostFactory()
        response = client.post(url_comments(post.slug), self.VALID_PAYLOAD)
        assert "id" in response.data
        assert Comment.objects.filter(pk=response.data["id"]).exists()

    # ── Optional fields ───────────────────────────────────────────────────────

    def test_website_field_is_optional(self, client):
        post = PostFactory()
        payload = {**self.VALID_PAYLOAD}  # no website key
        response = client.post(url_comments(post.slug), payload)
        assert response.status_code == status.HTTP_201_CREATED

    def test_website_saved_when_provided(self, client):
        post = PostFactory()
        payload = {**self.VALID_PAYLOAD, "website": "https://alice.dev"}
        client.post(url_comments(post.slug), payload)
        comment = Comment.objects.get()
        assert comment.website == "https://alice.dev"

    # ── Reply creation ────────────────────────────────────────────────────────

    def test_reply_created_with_valid_parent(self, client):
        post = PostFactory()
        parent = CommentFactory(post=post)
        payload = {**self.VALID_PAYLOAD, "parent": parent.pk}
        response = client.post(url_comments(post.slug), payload)
        assert response.status_code == status.HTTP_201_CREATED
        reply = Comment.objects.get(pk=response.data["id"])
        assert reply.parent == parent

    def test_reply_rejected_when_parent_belongs_to_different_post(self, client):
        post_a = PostFactory()
        post_b = PostFactory()
        parent_on_b = CommentFactory(post=post_b)
        payload = {**self.VALID_PAYLOAD, "parent": parent_on_b.pk}
        response = client.post(url_comments(post_a.slug), payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "parent" in response.data

    # ── Validation errors ─────────────────────────────────────────────────────

    def test_missing_name_returns_400(self, client):
        post = PostFactory()
        payload = {k: v for k, v in self.VALID_PAYLOAD.items() if k != "name"}
        response = client.post(url_comments(post.slug), payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "name" in response.data

    def test_missing_email_returns_400(self, client):
        post = PostFactory()
        payload = {k: v for k, v in self.VALID_PAYLOAD.items() if k != "email"}
        response = client.post(url_comments(post.slug), payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in response.data

    def test_missing_body_returns_400(self, client):
        post = PostFactory()
        payload = {k: v for k, v in self.VALID_PAYLOAD.items() if k != "body"}
        response = client.post(url_comments(post.slug), payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "body" in response.data

    def test_invalid_email_format_returns_400(self, client):
        post = PostFactory()
        payload = {**self.VALID_PAYLOAD, "email": "not-a-valid-email"}
        response = client.post(url_comments(post.slug), payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in response.data

    def test_invalid_website_url_returns_400(self, client):
        post = PostFactory()
        payload = {**self.VALID_PAYLOAD, "website": "not-a-url"}
        response = client.post(url_comments(post.slug), payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "website" in response.data

    def test_empty_body_returns_400(self, client):
        post = PostFactory()
        payload = {**self.VALID_PAYLOAD, "body": ""}
        response = client.post(url_comments(post.slug), payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    # ── 404 for non-published posts ───────────────────────────────────────────

    def test_returns_404_for_draft_post(self, client):
        draft = DraftPostFactory()
        response = client.post(url_comments(draft.slug), self.VALID_PAYLOAD)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_returns_404_for_nonexistent_slug(self, client):
        response = client.post(url_comments("no-such-post"), self.VALID_PAYLOAD)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_no_comment_created_for_draft_post(self, client):
        draft = DraftPostFactory()
        client.post(url_comments(draft.slug), self.VALID_PAYLOAD)
        assert Comment.objects.count() == 0

    # ── Multiple comments on same post ────────────────────────────────────────

    def test_multiple_comments_can_be_posted_on_same_post(self, client):
        post = PostFactory()
        for i in range(3):
            payload = {**self.VALID_PAYLOAD, "name": f"User {i}"}
            response = client.post(url_comments(post.slug), payload)
            assert response.status_code == status.HTTP_201_CREATED
        assert Comment.objects.filter(post=post).count() == 3

    def test_comments_on_different_posts_are_independent(self, client):
        post_a = PostFactory()
        post_b = PostFactory()
        client.post(url_comments(post_a.slug), self.VALID_PAYLOAD)
        client.post(url_comments(post_b.slug), self.VALID_PAYLOAD)
        assert Comment.objects.filter(post=post_a).count() == 1
        assert Comment.objects.filter(post=post_b).count() == 1
