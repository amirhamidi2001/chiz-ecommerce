# cart.views.get_or_create_cart is Epic 5 Task 5.1.1.2's cart-resolution
# helper: the authenticated user's cart if logged in, otherwise a
# session-based anonymous cart. Checked for circularity before importing
# directly: cart/views.py, models.py and serializers.py only import from
# shop, never shipping, and cart loads before shipping in INSTALLED_APPS
# (core/settings/base.py) — so this top-level import is safe today, same
# reasoning as the IranProvince import in shipping/models.py and
# shipping/serializers.py (Task 7.1.1.3).
from cart.views import get_or_create_cart
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ShippingCarrier, ShippingRate
from .serializers import ShippingQuoteSerializer


class ShippingQuoteView(APIView):
    """
    POST /api/shipping/quote/ (Task 7.2.1.6)

    Discovery/quote endpoint: given a destination province+city, returns
    every active carrier+rate combination available for the REQUESTING
    CART's current weight (resolved server-side, never trusted from the
    client — same principle as every other checkout pricing input). This
    is what lets the checkout UI show the customer their shipping choices
    BEFORE they submit, and is where the shipping_carrier_id/
    shipping_rate_id that Task 7.1.1.4 requires on POST /api/orders/
    actually come from.

    Pricing here is sourced entirely from the static ShippingRate table
    (Task 7.1.1.3) via ShippingRate.find_rate() — not live carrier APIs.
    If a given carrier's provider (Tasks 7.2.1.2-7.2.1.5) ever supports
    real-time quoting, that would be an enhancement layered on top of this
    endpoint, not a change to its core contract.

    AllowAny (not IsAuthenticated): must work for guest checkout too, per
    Epic 5 — a shopper who hasn't logged in still has a session-based cart
    via get_or_create_cart(), and still needs to see shipping options
    before deciding whether to check out at all.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ShippingQuoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        province = serializer.validated_data["province"]
        city = serializer.validated_data["city"]

        cart = get_or_create_cart(request)
        weight_g = sum(
            item.variant.weight_g_or_estimate() * item.quantity
            for item in cart.items.select_related("variant").all()
        )

        options = []
        for carrier in ShippingCarrier.objects.filter(is_active=True):
            rate = ShippingRate.find_rate(carrier, province, city, weight_g)
            if rate:
                options.append(
                    {
                        "carrier_id": carrier.id,
                        "carrier_name": carrier.display_name,
                        "rate_id": rate.id,
                        "price": str(rate.price),
                        "estimated_days_min": rate.estimated_days_min,
                        "estimated_days_max": rate.estimated_days_max,
                    }
                )
        return Response({"options": options}, status=status.HTTP_200_OK)
