from django.db.models import Avg, Count

from .models import Product


def refresh_product_review_stats(product: Product) -> None:
    """
    Recompute and persist the product's denormalised `rating` and
    `reviews_count` from its APPROVED reviews only.

    Must be called whenever a review's visibility changes: on creation (when
    auto-approved), on admin approve/unapprove, and when an approved review is
    deleted. Pending/rejected reviews never contribute to the public numbers.
    """
    stats = product.reviews.filter(is_approved=True).aggregate(
        avg_rating=Avg("rating"),
        total=Count("id"),
    )
    product.rating = round(stats["avg_rating"] or 0.0, 1)
    product.reviews_count = stats["total"] or 0
    product.save(update_fields=["rating", "reviews_count"])
