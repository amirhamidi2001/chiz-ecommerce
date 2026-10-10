from rest_framework import serializers
from shop.models import Product

from .models import FlashSale

# How many product summaries to embed per sale. A sale can cover hundreds of
# products and the homepage only needs a taste; the full list is a filtered
# product listing (?flash_sale=<id>).
PRODUCT_PREVIEW_LIMIT = 8


class FlashSaleProductSerializer(serializers.ModelSerializer):
    """Lightweight product summary embedded in a flash sale."""

    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ("id", "name", "slug", "price", "thumbnail_url")

    def get_thumbnail_url(self, obj):
        request = self.context.get("request")
        if obj.thumbnail and request:
            return request.build_absolute_uri(obj.thumbnail.url)
        return None


class ActiveFlashSaleSerializer(serializers.ModelSerializer):
    """
    A currently-running flash sale, with what a banner needs: its name,
    discount and end time, how many products it covers, and a short preview
    of them. Expects the queryset to annotate `product_count`.
    """

    product_count = serializers.IntegerField(read_only=True)
    products = serializers.SerializerMethodField()

    class Meta:
        model = FlashSale
        fields = (
            "id",
            "name",
            "discount_percent",
            "starts_at",
            "ends_at",
            "product_count",
            "products",
        )

    def get_products(self, obj):
        preview = obj.products.order_by("id")[:PRODUCT_PREVIEW_LIMIT]
        return FlashSaleProductSerializer(preview, many=True, context=self.context).data
