"""Photo uploads on reviews: verified purchasers only, max 5, real images only."""

import io
import os

import pytest
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APIRequestFactory
from shop.models import Review, ReviewImage
from shop.serializers import ReviewSerializer
from shop.tests.factories import ProductFactory, ReviewFactory
from shop.tests.test_review_moderation import _order_for
from shop.validators import validate_review_image

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    """Keep uploaded files out of the real MEDIA_ROOT."""
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


def _image_file(name="photo.png", fmt="PNG", content_type=None, size=(64, 64)):
    """A genuine image with random pixels (so it's not trivially tiny)."""
    img = Image.frombytes("RGB", size, os.urandom(size[0] * size[1] * 3))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return SimpleUploadedFile(
        name, buf.getvalue(), content_type=content_type or f"image/{fmt.lower()}"
    )


def _stored_files(root):
    return [p for p in root.rglob("*") if p.is_file()]


def _post(client, product, images=None, **extra):
    data = {"rating": 5, "headline": "Gorgeous", "comment": "Great shade.", **extra}
    if images is not None:
        data["images"] = images
    return client.post(
        reverse("product-review-create", kwargs={"slug": product.slug}),
        data,
        format="multipart",
    )


@pytest.fixture
def verified_product(user):
    product = ProductFactory()
    _order_for(user, product)
    return product


class TestVerifiedPurchaserUploads:
    @pytest.mark.parametrize("count", [1, 3, 5])
    def test_images_are_created_and_linked(
        self, auth_client, user, verified_product, count, media_root
    ):
        res = _post(
            auth_client,
            verified_product,
            [_image_file(f"p{i}.png") for i in range(count)],
        )

        assert res.status_code == status.HTTP_201_CREATED
        review = Review.objects.get(product=verified_product, user=user)
        assert review.is_verified_purchase is True
        assert review.images.count() == count
        assert ReviewImage.objects.filter(review=review).count() == count
        assert len(_stored_files(media_root)) == count
        # The create response echoes the photos back with absolute URLs.
        assert len(res.data["images"]) == count
        assert all(i["image"].startswith("http") for i in res.data["images"])

    def test_jpeg_and_webp_are_accepted(self, auth_client, verified_product):
        files = [
            _image_file("a.jpg", "JPEG"),
            _image_file("b.webp", "WEBP"),
        ]
        res = _post(auth_client, verified_product, files)
        assert res.status_code == status.HTTP_201_CREATED
        assert ReviewImage.objects.count() == 2

    def test_review_without_images_still_works(self, auth_client, verified_product):
        res = _post(auth_client, verified_product)
        assert res.status_code == status.HTTP_201_CREATED
        assert res.data["images"] == []
        assert ReviewImage.objects.count() == 0


class TestNonVerifiedPurchaserCannotUpload:
    def test_rejected_with_specific_message_and_nothing_is_saved(
        self, auth_client, media_root
    ):
        product = ProductFactory()  # user has no delivered order for it

        res = _post(auth_client, product, [_image_file(), _image_file("b.png")])

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "Only verified purchasers" in str(res.data["images"])
        # Nothing written at all — not partially successful.
        assert Review.objects.count() == 0
        assert ReviewImage.objects.count() == 0
        assert _stored_files(media_root) == []

    def test_text_only_review_from_non_verified_user_still_works(
        self, auth_client, user
    ):
        product = ProductFactory()

        res = _post(auth_client, product)

        assert res.status_code == status.HTTP_201_CREATED
        assert Review.objects.get(product=product, user=user).is_approved is False


class TestImageValidation:
    def test_more_than_five_images_is_rejected(
        self, auth_client, verified_product, media_root
    ):
        res = _post(
            auth_client, verified_product, [_image_file(f"p{i}.png") for i in range(6)]
        )

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "images" in res.data
        assert Review.objects.count() == 0
        assert _stored_files(media_root) == []

    def test_text_file_with_image_extension_and_content_type_is_rejected(
        self, auth_client, verified_product
    ):
        fake = SimpleUploadedFile(
            "totally-a-photo.jpg",
            b"just some text, not pixels",
            content_type="image/jpeg",
        )

        res = _post(auth_client, verified_product, [fake])

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "images" in res.data
        assert Review.objects.count() == 0

    def test_pdf_disguised_as_png_is_rejected(self, auth_client, verified_product):
        fake = SimpleUploadedFile(
            "scan.png", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n", content_type="image/png"
        )

        res = _post(auth_client, verified_product, [fake])

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert Review.objects.count() == 0

    def test_real_image_in_disallowed_format_is_rejected(
        self, auth_client, verified_product
    ):
        gif = _image_file("anim.gif", "GIF")

        res = _post(auth_client, verified_product, [gif])

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "Only JPEG, PNG and WebP" in str(res.data["images"])
        assert Review.objects.count() == 0

    def test_one_bad_file_rejects_the_whole_submission(
        self, auth_client, verified_product, media_root
    ):
        good = _image_file("ok.png")
        bad = SimpleUploadedFile("bad.png", b"nope", content_type="image/png")

        res = _post(auth_client, verified_product, [good, bad])

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert Review.objects.count() == 0
        assert _stored_files(media_root) == []

    def test_oversized_image_is_rejected(
        self, auth_client, verified_product, monkeypatch
    ):
        monkeypatch.setattr("shop.validators.REVIEW_IMAGE_MAX_BYTES", 100)

        res = _post(auth_client, verified_product, [_image_file()])

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "under" in str(res.data["images"])
        assert Review.objects.count() == 0


class TestValidateReviewImageUnit:
    @pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP"])
    def test_accepts_allowed_formats(self, fmt):
        validate_review_image(_image_file(f"x.{fmt.lower()}", fmt))

    def test_rejects_garbage_regardless_of_name_and_content_type(self):
        fake = SimpleUploadedFile("x.png", b"\x00\x01\x02", content_type="image/png")
        with pytest.raises(DjangoValidationError) as exc:
            validate_review_image(fake)
        assert exc.value.code == "invalid_image"

    def test_rewinds_file_after_checking(self):
        f = _image_file()
        validate_review_image(f)
        assert f.tell() == 0


class TestReviewSerializerOutput:
    def _context(self):
        request = APIRequestFactory().get("/")
        return {"request": request}

    def test_includes_nested_image_urls(self):
        review = ReviewFactory(is_approved=True)
        a = ReviewImage.objects.create(review=review, image=_image_file("a.png"))
        b = ReviewImage.objects.create(review=review, image=_image_file("b.png"))

        data = ReviewSerializer(review, context=self._context()).data

        assert [i["id"] for i in data["images"]] == [a.id, b.id]
        assert all(
            i["image"].startswith("http://testserver/media/reviews/images/")
            for i in data["images"]
        )

    def test_empty_list_when_review_has_no_images(self):
        review = ReviewFactory(is_approved=True)

        data = ReviewSerializer(review, context=self._context()).data

        assert data["images"] == []

    def test_product_detail_exposes_images_for_approved_reviews_only(self, api_client):
        product = ProductFactory()
        approved = ReviewFactory(product=product, is_approved=True)
        pending = ReviewFactory(product=product, is_approved=False)
        ReviewImage.objects.create(review=approved, image=_image_file("a.png"))
        ReviewImage.objects.create(review=pending, image=_image_file("p.png"))

        res = api_client.get(reverse("product-detail", kwargs={"slug": product.slug}))

        assert res.status_code == status.HTTP_200_OK
        assert [r["id"] for r in res.data["reviews"]] == [approved.id]
        assert len(res.data["reviews"][0]["images"]) == 1
