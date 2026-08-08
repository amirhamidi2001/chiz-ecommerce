import factory
import pytest
from blog.models import Category, Comment, Post
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APIRequestFactory

User = get_user_model()


# ─── Model factories ──────────────────────────────────────────────────────────


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    password = factory.PostGenerationMethodCall("set_password", "testpass123!")


class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Category

    # Unique names prevent IntegrityError in parallel tests
    name = factory.Sequence(lambda n: f"Category {n}")
    # slug is intentionally left blank — model.save() auto-generates it


class PostFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Post

    title = factory.Sequence(lambda n: f"Post Title {n}")
    # 20 words → read_time = max(1, round(20/200)) = 1
    content = factory.LazyAttribute(lambda _: " ".join(["word"] * 20))
    excerpt = factory.Faker("sentence")
    author = factory.SubFactory(UserFactory)
    category = factory.SubFactory(CategoryFactory)
    status = Post.Status.PUBLISHED
    is_featured = False
    views_count = 0


class DraftPostFactory(PostFactory):
    status = Post.Status.DRAFT


class CommentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Comment

    post = factory.SubFactory(PostFactory)
    name = factory.Faker("name")
    email = factory.Faker("email")
    website = ""
    body = factory.Faker("paragraph")
    is_approved = True
    parent = None


class ReplyFactory(CommentFactory):
    """A Comment whose parent is another Comment on the same post."""

    parent = factory.SubFactory(CommentFactory)

    @factory.lazy_attribute
    def post(self):
        return self.parent.post


# ─── Request helpers ──────────────────────────────────────────────────────────


def make_request(method="get", path="/", data=None):
    """Return a minimal DRF request for use in serializer context."""
    factory = APIRequestFactory()
    fn = getattr(factory, method)
    return fn(path, data or {})


# ─── pytest fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def request_factory():
    return APIRequestFactory()


@pytest.fixture
def user(db):
    return UserFactory()


@pytest.fixture
def category(db):
    return CategoryFactory()


@pytest.fixture
def published_post(db):
    return PostFactory(status=Post.Status.PUBLISHED)


@pytest.fixture
def draft_post(db):
    return PostFactory(status=Post.Status.DRAFT)


@pytest.fixture
def comment(db, published_post):
    return CommentFactory(post=published_post)
