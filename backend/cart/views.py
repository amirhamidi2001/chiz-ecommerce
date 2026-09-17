from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from shop.models import ProductVariant

from .models import Cart, CartItem
from .serializers import CartItemSerializer, CartSerializer


def get_or_create_cart(request):
    """
    Resolve the cart for this request: the authenticated user's cart if
    logged in, otherwise a session-based anonymous cart.
    """
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return cart

    if not request.session.session_key:
        request.session.create()
    session_key = request.session.session_key
    cart, _ = Cart.objects.get_or_create(session_key=session_key)
    return cart


class CartView(APIView):
    """
    GET  /api/cart/        → return the requesting user's (or anonymous
                              session's) cart
    POST /api/cart/        → add a variant to the cart (or increment qty)
    DELETE /api/cart/clear/ → empty the entire cart
    """

    permission_classes = [AllowAny]

    # ── GET: retrieve full cart ───────────────────────────────────────────────
    def get(self, request):
        cart = get_or_create_cart(request)
        serializer = CartSerializer(cart, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    # ── POST: add item (or bump quantity) ────────────────────────────────────
    def post(self, request):
        variant_id = request.data.get("variant_id")
        quantity = int(request.data.get("quantity", 1))

        if not variant_id:
            return Response(
                {"variant_id": "This field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate via serializer
        serializer = CartItemSerializer(
            data={"variant_id": variant_id, "quantity": quantity},
            context={"request": request},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        cart = get_or_create_cart(request)

        try:
            variant = ProductVariant.objects.get(pk=variant_id)
        except ProductVariant.DoesNotExist:
            return Response(
                {"variant_id": "Product variant not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Upsert: increment if already in cart, otherwise create
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            variant=variant,
            defaults={"quantity": quantity},
        )
        if not created:
            cart_item.quantity += quantity
            cart_item.save()

        cart.refresh_from_db()
        response_serializer = CartSerializer(cart, context={"request": request})
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class CartItemView(APIView):
    """
    PUT/PATCH /api/cart/item/<item_id>/  → update quantity of a specific item
    DELETE    /api/cart/item/<item_id>/  → remove a specific item from the cart
    """

    permission_classes = [AllowAny]

    def _get_item(self, request, item_id):
        """
        Helper: fetch a CartItem that belongs to the requesting cart.
        Resolves the requesting cart first via get_or_create_cart(request)
        rather than filtering CartItem by cart__user=request.user directly
        — the latter only works for authenticated users and would either
        match nothing or (worse) ambiguously match cart__user=None rows
        across DIFFERENT anonymous sessions for an AnonymousUser. Scoping
        to one resolved cart's own pk is correct for both auth states and
        is a single clear lookup rather than a cross-table filter.
        """
        cart = get_or_create_cart(request)
        try:
            return CartItem.objects.select_related("cart").get(pk=item_id, cart=cart)
        except CartItem.DoesNotExist:
            return None

    # ── PUT / PATCH: update quantity ─────────────────────────────────────────
    def put(self, request, item_id):
        return self._update(request, item_id)

    def patch(self, request, item_id):
        return self._update(request, item_id)

    def _update(self, request, item_id):
        item = self._get_item(request, item_id)
        if not item:
            return Response(
                {"detail": "Cart item not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        quantity = request.data.get("quantity")
        if quantity is None:
            return Response(
                {"quantity": "This field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            return Response(
                {"quantity": "Must be a valid integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if quantity < 1:
            return Response(
                {"quantity": "Quantity must be at least 1."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        item.quantity = quantity
        item.save()

        cart_serializer = CartSerializer(item.cart, context={"request": request})
        return Response(cart_serializer.data, status=status.HTTP_200_OK)

    # ── DELETE: remove single item ───────────────────────────────────────────
    def delete(self, request, item_id):
        item = self._get_item(request, item_id)
        if not item:
            return Response(
                {"detail": "Cart item not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        cart = item.cart
        item.delete()

        cart_serializer = CartSerializer(cart, context={"request": request})
        return Response(cart_serializer.data, status=status.HTTP_200_OK)


class CartClearView(APIView):
    """
    DELETE /api/cart/clear/ → delete all items from the requesting cart
    """

    permission_classes = [AllowAny]

    def delete(self, request):
        cart = get_or_create_cart(request)
        cart.items.all().delete()
        cart_serializer = CartSerializer(cart, context={"request": request})
        return Response(cart_serializer.data, status=status.HTTP_200_OK)
