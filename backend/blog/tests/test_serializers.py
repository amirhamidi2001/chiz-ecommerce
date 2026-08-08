from unittest.mock import MagicMock

import pytest
from blog.serializers import (
    CategorySerializer,
    CommentCreateSerializer,
    CommentSerializer,
    PostDetailSerializer,
    PostListSerializer,
    ReplySerializer,
)
from blog.tests.conftest import (
    CategoryFactory,
    CommentFactory,
    PostFactory,
    ReplyFactory,
)
from rest_framework.test import APIRequestFactory

request_factory = APIRequestFactory()


def fake_request():
    """Minimal GET request used to build absolute URIs in serializers."""
    return request_factory.get("/")


# ═══════════════════════════════════════════════════════════════════════════════
# CategorySerializer
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestCategorySerializer:

    def test_exposes_expected_fields(self):
        cat = CategoryFactory()
        data = CategorySerializer(cat).data
        assert set(data.keys()) == {"id", "name", "slug", "post_count"}

    def test_id_name_slug_values(self):
        cat = CategoryFactory(name="Django", slug="django")
        data = CategorySerializer(cat).data
        assert data["id"] == cat.pk
        assert data["name"] == "Django"
        assert data["slug"] == "django"

    def test_post_count_defaults_to_zero_without_annotation(self):
        # When the queryset is NOT annotated (e.g. direct serialization)
        # the field uses its declared default of 0
        cat = CategoryFactory()
        data = CategorySerializer(cat).data
        assert data["post_count"] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# ReplySerializer
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestReplySerializer:

    def test_exposes_expected_fields(self):
        reply = ReplyFactory()
        data = ReplySerializer(reply).data
        assert set(data.keys()) == {"id", "name", "body", "created_at"}

    def test_values_match_instance(self):
        reply = ReplyFactory(name="Bob", body="Nice reply!")
        data = ReplySerializer(reply).data
        assert data["name"] == "Bob"
        assert data["body"] == "Nice reply!"

    def test_email_is_not_exposed(self):
        reply = ReplyFactory()
        data = ReplySerializer(reply).data
        assert "email" not in data


# ═══════════════════════════════════════════════════════════════════════════════
# CommentSerializer
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestCommentSerializer:

    def test_exposes_expected_fields(self):
        comment = CommentFactory()
        data = CommentSerializer(comment).data
        assert set(data.keys()) == {"id", "name", "body", "created_at", "replies"}

    def test_replies_is_empty_list_when_no_replies(self):
        comment = CommentFactory()
        data = CommentSerializer(comment).data
        assert data["replies"] == []

    def test_replies_contains_nested_reply_data(self):
        comment = CommentFactory()
        reply = ReplyFactory(parent=comment)
        data = CommentSerializer(comment).data
        assert len(data["replies"]) == 1
        assert data["replies"][0]["id"] == reply.pk
        assert data["replies"][0]["name"] == reply.name

    def test_replies_exposes_only_reply_fields(self):
        comment = CommentFactory()
        ReplyFactory(parent=comment)
        data = CommentSerializer(comment).data
        reply_keys = set(data["replies"][0].keys())
        assert reply_keys == {"id", "name", "body", "created_at"}

    def test_email_not_exposed_in_comment(self):
        comment = CommentFactory(email="private@example.com")
        data = CommentSerializer(comment).data
        assert "email" not in data

    def test_multiple_replies_are_all_listed(self):
        comment = CommentFactory()
        r1 = ReplyFactory(parent=comment)
        r2 = ReplyFactory(parent=comment)
        data = CommentSerializer(comment).data
        ids = [r["id"] for r in data["replies"]]
        assert set(ids) == {r1.pk, r2.pk}


# ═══════════════════════════════════════════════════════════════════════════════
# CommentCreateSerializer
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestCommentCreateSerializer:

    def _valid_data(self):
        return {"name": "Alice", "email": "alice@example.com", "body": "Great post!"}

    def test_valid_data_is_accepted(self):
        s = CommentCreateSerializer(data=self._valid_data())
        assert s.is_valid(), s.errors

    def test_name_is_required(self):
        data = self._valid_data()
        data.pop("name")
        s = CommentCreateSerializer(data=data)
        assert not s.is_valid()
        assert "name" in s.errors

    def test_email_is_required(self):
        data = self._valid_data()
        data.pop("email")
        s = CommentCreateSerializer(data=data)
        assert not s.is_valid()
        assert "email" in s.errors

    def test_body_is_required(self):
        data = self._valid_data()
        data.pop("body")
        s = CommentCreateSerializer(data=data)
        assert not s.is_valid()
        assert "body" in s.errors

    def test_invalid_email_rejected(self):
        data = {**self._valid_data(), "email": "not-an-email"}
        s = CommentCreateSerializer(data=data)
        assert not s.is_valid()
        assert "email" in s.errors

    def test_website_is_optional(self):
        s = CommentCreateSerializer(data=self._valid_data())
        assert s.is_valid(), s.errors

    def test_website_with_valid_url_accepted(self):
        data = {**self._valid_data(), "website": "https://example.com"}
        s = CommentCreateSerializer(data=data)
        assert s.is_valid(), s.errors

    def test_parent_none_is_valid(self):
        data = {**self._valid_data(), "parent": None}
        s = CommentCreateSerializer(data=data)
        assert s.is_valid(), s.errors

    def test_validate_parent_accepts_matching_post(self):
        post = PostFactory()
        parent = CommentFactory(post=post)
        data = {**self._valid_data(), "parent": parent.pk}
        s = CommentCreateSerializer(data=data, context={"post": post})
        assert s.is_valid(), s.errors

    def test_validate_parent_rejects_comment_from_different_post(self):
        post_a = PostFactory()
        post_b = PostFactory()
        parent_on_b = CommentFactory(post=post_b)
        data = {**self._valid_data(), "parent": parent_on_b.pk}
        # Context says we are commenting on post_a, but parent belongs to post_b
        s = CommentCreateSerializer(data=data, context={"post": post_a})
        assert not s.is_valid()
        assert "parent" in s.errors

    def test_validate_parent_returns_none_for_none_input(self):
        s = CommentCreateSerializer(data=self._valid_data())
        s.is_valid()
        # validate_parent is not called for absent/None parent — just check
        # that no parent key raises no error
        assert "parent" not in s.errors

    def test_fields_exposed_in_create_serializer(self):
        # Should expose id on output so the view can return the new comment
        post = PostFactory()
        comment = CommentFactory.build(post=post)
        s = CommentCreateSerializer(comment)
        assert "id" in s.data


# ═══════════════════════════════════════════════════════════════════════════════
# PostListSerializer
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestPostListSerializer:

    EXPECTED_FIELDS = {
        "id",
        "title",
        "slug",
        "excerpt",
        "cover_image_url",
        "category",
        "is_featured",
        "views_count",
        "read_time",
        "created_at",
        "published_at",
    }

    def test_exposes_expected_fields(self):
        post = PostFactory()
        data = PostListSerializer(post, context={"request": fake_request()}).data
        assert set(data.keys()) == self.EXPECTED_FIELDS

    def test_content_not_exposed(self):
        post = PostFactory()
        data = PostListSerializer(post).data
        assert "content" not in data

    def test_cover_image_url_none_when_no_image(self):
        post = PostFactory(cover_image=None)
        data = PostListSerializer(post).data
        assert data["cover_image_url"] is None

    def test_cover_image_url_returns_relative_url_without_request(self):
        # When no request is in context, returns the raw URL
        post = PostFactory()
        # Attach a mock cover_image
        mock_image = MagicMock()
        mock_image.url = "/media/blog/covers/test.jpg"
        post.cover_image = mock_image
        data = PostListSerializer(post, context={}).data
        assert data["cover_image_url"] == "/media/blog/covers/test.jpg"

    def test_cover_image_url_builds_absolute_uri_with_request(self):
        post = PostFactory()
        mock_image = MagicMock()
        mock_image.url = "/media/blog/covers/test.jpg"
        post.cover_image = mock_image
        request = fake_request()
        data = PostListSerializer(post, context={"request": request}).data
        assert data["cover_image_url"].startswith("http")
        assert "/media/blog/covers/test.jpg" in data["cover_image_url"]

    def test_nested_category_data(self):
        cat = CategoryFactory(name="Science", slug="science")
        post = PostFactory(category=cat)
        data = PostListSerializer(post).data
        assert data["category"]["name"] == "Science"
        assert data["category"]["slug"] == "science"

    def test_category_is_none_when_post_has_no_category(self):
        post = PostFactory(category=None)
        data = PostListSerializer(post).data
        assert data["category"] is None


# ═══════════════════════════════════════════════════════════════════════════════
# PostDetailSerializer
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestPostDetailSerializer:

    def test_includes_all_list_fields_plus_extra(self):
        post = PostFactory()
        data = PostDetailSerializer(post).data
        assert "content" in data
        assert "comments" in data
        assert "comments_count" in data

    def test_content_field_is_present(self):
        post = PostFactory(content="Hello World content")
        data = PostDetailSerializer(post).data
        assert data["content"] == "Hello World content"

    def test_comments_count_zero_with_no_comments(self):
        post = PostFactory()
        data = PostDetailSerializer(post).data
        assert data["comments_count"] == 0

    def test_comments_count_only_counts_approved(self):
        post = PostFactory()
        CommentFactory(post=post, is_approved=True)
        CommentFactory(post=post, is_approved=True)
        CommentFactory(post=post, is_approved=False)
        data = PostDetailSerializer(post).data
        assert data["comments_count"] == 2

    def test_comments_includes_approved_top_level_comments(self):
        post = PostFactory()
        c1 = CommentFactory(post=post, is_approved=True)
        c2 = CommentFactory(post=post, is_approved=True)
        data = PostDetailSerializer(post).data
        ids = {c["id"] for c in data["comments"]}
        assert ids == {c1.pk, c2.pk}

    def test_comments_excludes_unapproved(self):
        post = PostFactory()
        CommentFactory(post=post, is_approved=False)
        data = PostDetailSerializer(post).data
        assert data["comments"] == []

    def test_comments_excludes_replies_from_top_level(self):
        post = PostFactory()
        parent = CommentFactory(post=post)
        ReplyFactory(parent=parent)
        data = PostDetailSerializer(post).data
        # Only the parent should be at the top level
        assert len(data["comments"]) == 1
        assert data["comments"][0]["id"] == parent.pk

    def test_replies_are_nested_inside_parent_comment(self):
        post = PostFactory()
        parent = CommentFactory(post=post)
        reply = ReplyFactory(parent=parent)
        data = PostDetailSerializer(post).data
        parent_data = data["comments"][0]
        assert len(parent_data["replies"]) == 1
        assert parent_data["replies"][0]["id"] == reply.pk

    def test_replies_count_included_in_comments_count(self):
        post = PostFactory()
        parent = CommentFactory(post=post, is_approved=True)
        ReplyFactory(parent=parent)
        # Both parent and reply are approved
        data = PostDetailSerializer(post).data
        assert data["comments_count"] == 2
