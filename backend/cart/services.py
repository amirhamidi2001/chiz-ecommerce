from django.db import transaction

from .models import Cart


def merge_session_cart_into_user_cart(request, user):
    """
    If the current session has an anonymous cart, merge its items into
    `user`'s persistent cart, then delete the anonymous cart. Existing
    quantities are summed when the same variant appears in both carts.

    Called from all three login/registration entry points (LoginView,
    OTPVerifyView, RegisterView) — a visitor may authenticate via any
    of them after building up an anonymous cart, and each path should
    get the same merge treatment.
    """
    session_key = request.session.session_key
    if not session_key:
        return

    try:
        session_cart = Cart.objects.prefetch_related("items").get(
            session_key=session_key
        )
    except Cart.DoesNotExist:
        return

    if not session_cart.items.exists():
        session_cart.delete()
        return

    with transaction.atomic():
        user_cart, _ = Cart.objects.get_or_create(user=user)
        for item in session_cart.items.all():
            existing = user_cart.items.filter(variant=item.variant).first()
            if existing:
                existing.quantity += item.quantity
                existing.save(update_fields=["quantity"])
            else:
                # Clone rather than reassign the FK on the original row —
                # session_cart is about to be deleted anyway, so there's
                # no ambiguity about which row survives.
                item.pk = None
                item.cart = user_cart
                item.save()
        session_cart.delete()
