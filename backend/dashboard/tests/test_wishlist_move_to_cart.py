"""
Wishlist -> cart moves: POST /dashboard/wishlist/{id}/move-to-cart/ and
POST /dashboard/wishlist/move-all-to-cart/.

A wishlist item is a PRODUCT; a cart line is a specific VARIANT. So the
endpoint must resolve the variant: automatically when exactly one is
purchasable, by asking (HTTP 300 + the choices) when several are, and by
refusing (400) when none are.

Sections:
  1. Single move — one purchasable variant
  2. Single move — several variants (300 -> choose -> done)
  3. Invalid / mismatched variant_id
  4. Nothing purchasable
  5. Cart merge behaviour (existing line is incremented)
  6. Bulk "move all"
  7. Eligibility rules stay in step with the cart's own validator
  8. Ownership, guests, atomicity
"""

from datetime import timedelta
from unittest.mock import patch

import pytest
from cart.models import Cart, CartItem
from cart.serializers import CartItemSerializer
from dashboard.models import Wishlist
from dashboard.services import (
    get_purchasable_variants,
    move_wishlist_item_to_cart,
)
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

WISHLIST_URL = "/api/dashboard/wishlist/"
MOVE_ALL_URL = f"{WISHLIST_URL}move-all-to-cart/"


def move_url(item_id):
    return f"{WISHLIST_URL}{item_id}/move-to-cart/"


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def wish(customer):
    """wish(product) -> a user-owned wishlist row."""
    return lambda product: Wishlist.objects.create(user=customer, product=product)


@pytest.fixture
def cart_lines(customer):
    """{variant_id: quantity} for the customer's cart."""
    return lambda: {
        ci.variant_id: ci.quantity
        for ci in CartItem.objects.filter(cart__user=customer)
    }


@pytest.fixture
def single_variant_product(make_product, make_variant):
    product = make_product()
    variant = make_variant(product=product, price="20.00")
    return product, variant


@pytest.fixture
def multi_variant_product(make_product, make_variant):
    """Two purchasable variants (+ an inactive and a sold-out one that must
    never be offered)."""
    product = make_product()
    dear = make_variant(product=product, price="30.00")
    cheap = make_variant(product=product, price="10.00")
    make_variant(product=product, price="5.00", is_active=False)
    make_variant(product=product, price="6.00", stock=0)
    return product, cheap, dear


# ══════════════════════════════════════════════════════════════════════════════
# 1. Single move — one purchasable variant
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestMoveSingleVariantProduct:

    def test_moves_immediately_and_removes_the_wishlist_item(
        self, customer_client, wish, single_variant_product, cart_lines
    ):
        product, variant = single_variant_product
        item = wish(product)

        res = customer_client.post(move_url(item.pk))

        assert res.status_code == status.HTTP_200_OK
        assert res.data == {"detail": "Moved to cart."}
        assert not Wishlist.objects.filter(pk=item.pk).exists()
        assert cart_lines() == {variant.pk: 1}

    def test_inactive_and_sold_out_variants_do_not_make_it_ambiguous(
        self, customer_client, wish, make_product, make_variant, cart_lines
    ):
        product = make_product()
        good = make_variant(product=product)
        make_variant(product=product, is_active=False)
        make_variant(product=product, stock=0)
        item = wish(product)

        res = customer_client.post(move_url(item.pk))

        assert res.status_code == status.HTTP_200_OK
        assert cart_lines() == {good.pk: 1}

    def test_a_matching_variant_id_is_accepted(
        self, customer_client, wish, single_variant_product, cart_lines
    ):
        product, variant = single_variant_product
        item = wish(product)
        res = customer_client.post(move_url(item.pk), {"variant_id": variant.pk})
        assert res.status_code == status.HTTP_200_OK
        assert cart_lines() == {variant.pk: 1}

    def test_moving_one_item_leaves_the_rest_of_the_wishlist_alone(
        self, customer_client, wish, single_variant_product, make_product
    ):
        product, _ = single_variant_product
        other = wish(make_product())
        item = wish(product)

        customer_client.post(move_url(item.pk))

        assert Wishlist.objects.filter(pk=other.pk).exists()


# ══════════════════════════════════════════════════════════════════════════════
# 2. Single move — several variants
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestMoveMultiVariantProduct:

    def test_without_variant_id_returns_the_choices_and_changes_nothing(
        self, customer_client, wish, multi_variant_product, cart_lines
    ):
        product, cheap, dear = multi_variant_product
        item = wish(product)

        res = customer_client.post(move_url(item.pk))

        assert res.status_code == status.HTTP_300_MULTIPLE_CHOICES
        assert res.data["needs_selection"] is True
        assert res.data["detail"] == (
            "This product has multiple options — please choose one."
        )
        # Only the purchasable variants, cheapest first — never the
        # inactive or sold-out ones.
        assert [v["id"] for v in res.data["variants"]] == [cheap.pk, dear.pk]
        # Full variant payload (what a picker needs to render).
        assert {"id", "price", "effective_price", "color", "stock"} <= set(
            res.data["variants"][0]
        )
        # Nothing moved, nothing deleted.
        assert Wishlist.objects.filter(pk=item.pk).exists()
        assert cart_lines() == {}

    def test_same_request_with_a_valid_variant_id_completes_the_move(
        self, customer_client, wish, multi_variant_product, cart_lines
    ):
        product, cheap, dear = multi_variant_product
        item = wish(product)
        assert (
            customer_client.post(move_url(item.pk)).status_code
            == status.HTTP_300_MULTIPLE_CHOICES
        )

        res = customer_client.post(move_url(item.pk), {"variant_id": dear.pk})

        assert res.status_code == status.HTTP_200_OK
        assert not Wishlist.objects.filter(pk=item.pk).exists()
        assert cart_lines() == {dear.pk: 1}

    def test_variant_id_may_be_sent_as_a_string(
        self, customer_client, wish, multi_variant_product, cart_lines
    ):
        product, cheap, _ = multi_variant_product
        item = wish(product)
        res = customer_client.post(
            move_url(item.pk), {"variant_id": str(cheap.pk)}, format="json"
        )
        assert res.status_code == status.HTTP_200_OK
        assert cart_lines() == {cheap.pk: 1}


# ══════════════════════════════════════════════════════════════════════════════
# 3. Invalid / mismatched variant_id
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestInvalidVariantId:

    def _assert_rejected(self, res, item, cart_lines):
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert res.data == {"variant_id": "Invalid variant for this product."}
        assert Wishlist.objects.filter(pk=item.pk).exists()
        assert cart_lines() == {}

    def test_variant_of_a_different_product_is_rejected(
        self, customer_client, wish, multi_variant_product, make_variant, cart_lines
    ):
        product, _, _ = multi_variant_product
        foreign = make_variant()  # belongs to some other product
        item = wish(product)

        res = customer_client.post(move_url(item.pk), {"variant_id": foreign.pk})

        self._assert_rejected(res, item, cart_lines)

    def test_nonexistent_variant_is_rejected(
        self, customer_client, wish, multi_variant_product, cart_lines
    ):
        product, _, _ = multi_variant_product
        item = wish(product)
        res = customer_client.post(move_url(item.pk), {"variant_id": 999999})
        self._assert_rejected(res, item, cart_lines)

    def test_non_numeric_variant_id_is_a_400_not_a_500(
        self, customer_client, wish, multi_variant_product, cart_lines
    ):
        product, _, _ = multi_variant_product
        item = wish(product)
        res = customer_client.post(
            move_url(item.pk), {"variant_id": "red"}, format="json"
        )
        self._assert_rejected(res, item, cart_lines)

    def test_same_product_but_inactive_variant_is_rejected(
        self, customer_client, wish, make_product, make_variant, cart_lines
    ):
        product = make_product()
        make_variant(product=product)
        make_variant(product=product)
        retired = make_variant(product=product, is_active=False)
        item = wish(product)

        res = customer_client.post(move_url(item.pk), {"variant_id": retired.pk})

        self._assert_rejected(res, item, cart_lines)

    def test_same_product_but_sold_out_variant_is_rejected(
        self, customer_client, wish, make_product, make_variant, cart_lines
    ):
        product = make_product()
        make_variant(product=product)
        make_variant(product=product)
        sold_out = make_variant(product=product, stock=0)
        item = wish(product)

        res = customer_client.post(move_url(item.pk), {"variant_id": sold_out.pk})

        self._assert_rejected(res, item, cart_lines)

    def test_stale_pick_is_not_silently_swapped_for_the_last_variant_left(
        self, customer_client, wish, make_product, make_variant, cart_lines
    ):
        """Customer picked shade B; B sold out meanwhile, leaving only A.
        Auto-resolving to A would put a shade in the cart they never chose."""
        product = make_product()
        remaining = make_variant(product=product)
        sold_out = make_variant(product=product, stock=0)
        item = wish(product)

        res = customer_client.post(move_url(item.pk), {"variant_id": sold_out.pk})

        self._assert_rejected(res, item, cart_lines)
        assert remaining.pk not in cart_lines()


# ══════════════════════════════════════════════════════════════════════════════
# 4. Nothing purchasable
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestUnavailableProduct:

    def _assert_unavailable(self, customer_client, item, cart_lines):
        res = customer_client.post(move_url(item.pk))
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert res.data == {"detail": "This product is currently unavailable."}
        assert Wishlist.objects.filter(pk=item.pk).exists()
        assert cart_lines() == {}

    def test_all_variants_inactive(
        self, customer_client, wish, make_product, make_variant, cart_lines
    ):
        product = make_product()
        make_variant(product=product, is_active=False)
        make_variant(product=product, is_active=False)
        self._assert_unavailable(customer_client, wish(product), cart_lines)

    def test_all_variants_sold_out(
        self, customer_client, wish, make_product, make_variant, cart_lines
    ):
        product = make_product()
        make_variant(product=product, stock=0)
        make_variant(product=product, stock=0)
        self._assert_unavailable(customer_client, wish(product), cart_lines)

    def test_product_with_no_variants(
        self, customer_client, wish, make_product, cart_lines
    ):
        self._assert_unavailable(customer_client, wish(make_product()), cart_lines)

    def test_only_variant_is_past_its_expiration_date(
        self, customer_client, wish, make_product, make_variant, cart_lines
    ):
        product = make_product()
        variant = make_variant(product=product)
        variant.expiration_date = timezone.now().date() - timedelta(days=1)
        variant.save()  # still is_active=True — the nightly sweep hasn't run
        self._assert_unavailable(customer_client, wish(product), cart_lines)


# ══════════════════════════════════════════════════════════════════════════════
# 5. Existing cart line
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestMoveIntoAnExistingCartLine:

    def test_increments_quantity_instead_of_duplicating_the_line(
        self, customer_client, customer, wish, single_variant_product, cart_lines
    ):
        product, variant = single_variant_product
        cart = Cart.objects.create(user=customer)
        CartItem.objects.create(cart=cart, variant=variant, quantity=2)
        item = wish(product)

        res = customer_client.post(move_url(item.pk))

        assert res.status_code == status.HTTP_200_OK
        assert CartItem.objects.filter(cart=cart, variant=variant).count() == 1
        assert cart_lines() == {variant.pk: 3}
        assert not Wishlist.objects.filter(pk=item.pk).exists()

    def test_a_chosen_variant_already_in_the_cart_is_incremented(
        self, customer_client, customer, wish, multi_variant_product, cart_lines
    ):
        product, cheap, dear = multi_variant_product
        cart = Cart.objects.create(user=customer)
        CartItem.objects.create(cart=cart, variant=cheap, quantity=1)
        item = wish(product)

        customer_client.post(move_url(item.pk), {"variant_id": cheap.pk})

        assert cart_lines() == {cheap.pk: 2}

    def test_a_different_variant_of_the_same_product_gets_its_own_line(
        self, customer_client, customer, wish, multi_variant_product, cart_lines
    ):
        product, cheap, dear = multi_variant_product
        cart = Cart.objects.create(user=customer)
        CartItem.objects.create(cart=cart, variant=cheap, quantity=1)
        item = wish(product)

        customer_client.post(move_url(item.pk), {"variant_id": dear.pk})

        assert cart_lines() == {cheap.pk: 1, dear.pk: 1}


# ══════════════════════════════════════════════════════════════════════════════
# 6. Bulk "move all"
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestMoveAllToCart:

    @pytest.fixture
    def mixed_wishlist(self, wish, make_product, make_variant):
        single_a = make_product(name="Single A")
        single_a_variant = make_variant(product=single_a)
        single_d = make_product(name="Single D")
        single_d_variant = make_variant(product=single_d)

        multi = make_product(name="Multi B")
        multi_cheap = make_variant(product=multi, price="10.00")
        multi_dear = make_variant(product=multi, price="20.00")

        gone = make_product(name="Gone C")
        make_variant(product=gone, stock=0)

        items = {
            "single_a": wish(single_a),
            "multi": wish(multi),
            "gone": wish(gone),
            "single_d": wish(single_d),
        }
        return {
            "items": items,
            "single_variants": {single_a_variant.pk, single_d_variant.pk},
            "multi_variants": [multi_cheap.pk, multi_dear.pk],
        }

    def test_partitions_a_mixed_wishlist_into_the_three_buckets(
        self, customer_client, mixed_wishlist
    ):
        res = customer_client.post(MOVE_ALL_URL)

        assert res.status_code == status.HTTP_200_OK
        assert sorted(res.data["moved"]) == ["Single A", "Single D"]

        (needs,) = res.data["needs_selection"]
        assert needs["wishlist_item_id"] == mixed_wishlist["items"]["multi"].pk
        assert needs["product"] == "Multi B"
        assert [v["id"] for v in needs["variants"]] == mixed_wishlist["multi_variants"]

        (gone,) = res.data["unavailable"]
        assert gone == {
            "wishlist_item_id": mixed_wishlist["items"]["gone"].pk,
            "product": "Gone C",
        }

    def test_only_the_genuinely_moved_items_leave_the_wishlist_and_enter_the_cart(
        self, customer_client, mixed_wishlist, cart_lines
    ):
        customer_client.post(MOVE_ALL_URL)

        remaining = set(Wishlist.objects.values_list("pk", flat=True))
        assert remaining == {
            mixed_wishlist["items"]["multi"].pk,
            mixed_wishlist["items"]["gone"].pk,
        }
        assert set(cart_lines()) == mixed_wishlist["single_variants"]
        assert all(qty == 1 for qty in cart_lines().values())

    def test_ambiguous_item_can_then_be_finished_with_a_chosen_variant(
        self, customer_client, mixed_wishlist, cart_lines
    ):
        res = customer_client.post(MOVE_ALL_URL)
        (needs,) = res.data["needs_selection"]
        chosen = needs["variants"][1]["id"]

        done = customer_client.post(
            move_url(needs["wishlist_item_id"]), {"variant_id": chosen}
        )

        assert done.status_code == status.HTTP_200_OK
        assert chosen in cart_lines()
        assert not Wishlist.objects.filter(pk=needs["wishlist_item_id"]).exists()

    def test_moving_everything_in_one_pass_leaves_an_empty_wishlist(
        self, customer_client, customer, wish, make_product, make_variant, cart_lines
    ):
        variants = []
        for _ in range(3):
            product = make_product()
            variants.append(make_variant(product=product))
            wish(product)

        res = customer_client.post(MOVE_ALL_URL)

        assert len(res.data["moved"]) == 3
        assert res.data["needs_selection"] == [] and res.data["unavailable"] == []
        assert not Wishlist.objects.filter(user=customer).exists()
        assert set(cart_lines()) == {v.pk for v in variants}

    def test_bulk_increments_lines_already_in_the_cart(
        self, customer_client, customer, wish, single_variant_product, cart_lines
    ):
        product, variant = single_variant_product
        cart = Cart.objects.create(user=customer)
        CartItem.objects.create(cart=cart, variant=variant, quantity=4)
        wish(product)

        customer_client.post(MOVE_ALL_URL)

        assert cart_lines() == {variant.pk: 5}
        assert CartItem.objects.filter(cart=cart).count() == 1

    def test_empty_wishlist_returns_three_empty_buckets(self, customer_client):
        res = customer_client.post(MOVE_ALL_URL)
        assert res.status_code == status.HTTP_200_OK
        assert res.data == {"moved": [], "needs_selection": [], "unavailable": []}

    def test_a_wishlist_with_nothing_movable_does_not_create_a_cart(
        self, customer_client, customer, wish, make_product, make_variant
    ):
        wish(make_product())  # no variants
        multi = make_product()
        make_variant(product=multi)
        make_variant(product=multi)
        wish(multi)

        customer_client.post(MOVE_ALL_URL)

        assert not Cart.objects.filter(user=customer).exists()

    def test_the_url_is_not_swallowed_by_the_detail_route(self, customer_client):
        """`move-all-to-cart` must hit the list action, not be read as a pk."""
        res = customer_client.post(MOVE_ALL_URL)
        assert res.status_code != status.HTTP_404_NOT_FOUND


# ══════════════════════════════════════════════════════════════════════════════
# 7. Eligibility stays in step with the cart's own validator
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestEligibilityMatchesTheCart:
    """get_purchasable_variants() re-states the rules in
    CartItemSerializer.validate_variant_id. If they ever drift, a move
    could either offer variants the cart then rejects or hide ones it
    would accept — these tests pin the two together."""

    @staticmethod
    def cart_accepts(variant):
        return CartItemSerializer(
            data={"variant_id": variant.pk, "quantity": 1}
        ).is_valid()

    @pytest.fixture
    def product(self, make_product):
        return make_product()

    def _check(self, product, variant, expected):
        assert self.cart_accepts(variant) is expected
        assert (variant in get_purchasable_variants(product)) is expected

    def test_a_normal_variant(self, product, make_variant):
        self._check(product, make_variant(product=product), True)

    def test_inactive(self, product, make_variant):
        self._check(product, make_variant(product=product, is_active=False), False)

    def test_out_of_stock(self, product, make_variant):
        self._check(product, make_variant(product=product, stock=0), False)

    def test_expired_yesterday(self, product, make_variant):
        variant = make_variant(product=product)
        variant.expiration_date = timezone.now().date() - timedelta(days=1)
        variant.save()
        self._check(product, variant, False)

    def test_expiring_today_is_still_purchasable(self, product, make_variant):
        variant = make_variant(product=product)
        variant.expiration_date = timezone.now().date()
        variant.save()
        self._check(product, variant, True)

    def test_no_expiration_date_is_not_expired(self, product, make_variant):
        variant = make_variant(product=product)
        assert variant.expiration_date is None
        self._check(product, variant, True)

    def test_results_are_ordered_cheapest_first(self, product, make_variant):
        dear = make_variant(product=product, price="9.00")
        cheap = make_variant(product=product, price="3.00")
        assert get_purchasable_variants(product) == [cheap, dear]


# ══════════════════════════════════════════════════════════════════════════════
# 8. Ownership, guests, atomicity
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestOwnershipGuestsAndAtomicity:

    def test_cannot_move_another_users_wishlist_item(
        self, customer_client, make_user, single_variant_product, cart_lines
    ):
        product, _ = single_variant_product
        theirs = Wishlist.objects.create(
            user=make_user(email="other@example.com"), product=product
        )

        res = customer_client.post(move_url(theirs.pk))

        assert res.status_code == status.HTTP_404_NOT_FOUND
        assert Wishlist.objects.filter(pk=theirs.pk).exists()
        assert cart_lines() == {}

    def test_move_all_only_touches_the_callers_items(
        self, customer_client, make_user, single_variant_product, cart_lines
    ):
        product, _ = single_variant_product
        theirs = Wishlist.objects.create(
            user=make_user(email="other@example.com"), product=product
        )

        res = customer_client.post(MOVE_ALL_URL)

        assert res.data["moved"] == []
        assert Wishlist.objects.filter(pk=theirs.pk).exists()
        assert cart_lines() == {}

    def test_moving_the_same_item_twice_does_not_double_add(
        self, customer_client, wish, single_variant_product, cart_lines
    ):
        product, variant = single_variant_product
        item = wish(product)

        first = customer_client.post(move_url(item.pk))
        second = customer_client.post(move_url(item.pk))

        assert first.status_code == status.HTTP_200_OK
        assert second.status_code == status.HTTP_404_NOT_FOUND
        assert cart_lines() == {variant.pk: 1}

    def test_service_reports_false_when_the_item_is_already_gone(
        self, customer, wish, single_variant_product
    ):
        product, variant = single_variant_product
        item = wish(product)
        cart = Cart.objects.create(user=customer)
        Wishlist.objects.filter(pk=item.pk).delete()  # moved by someone else

        assert move_wishlist_item_to_cart(cart, item, variant) is False
        assert not CartItem.objects.filter(cart=cart).exists()

    def test_a_failure_part_way_leaves_neither_a_cart_line_nor_a_lost_item(
        self, customer_client, wish, single_variant_product, cart_lines
    ):
        """The add and the delete are one atomic step: if the delete blows
        up, the cart line that was just added must roll back too."""
        product, _ = single_variant_product
        item = wish(product)

        with patch.object(Wishlist, "delete", side_effect=RuntimeError("boom")):
            with pytest.raises(RuntimeError):
                customer_client.post(move_url(item.pk))

        assert Wishlist.objects.filter(pk=item.pk).exists()
        assert cart_lines() == {}

    # ── guests (session-based wishlist + session-based cart) ────────────────

    def test_guest_can_move_a_session_wishlist_item_into_the_session_cart(
        self, anon_client, single_variant_product
    ):
        product, variant = single_variant_product
        item_id = anon_client.post(WISHLIST_URL, {"product_id": product.pk}).data["id"]

        res = anon_client.post(move_url(item_id))

        assert res.status_code == status.HTTP_200_OK
        assert not Wishlist.objects.filter(pk=item_id).exists()
        cart = Cart.objects.get(session_key=anon_client.session.session_key)
        assert {ci.variant_id: ci.quantity for ci in cart.items.all()} == {
            variant.pk: 1
        }

    def test_guest_move_all(self, anon_client, make_product, make_variant):
        for _ in range(2):
            product = make_product()
            make_variant(product=product)
            anon_client.post(WISHLIST_URL, {"product_id": product.pk})

        res = anon_client.post(MOVE_ALL_URL)

        assert len(res.data["moved"]) == 2
        cart = Cart.objects.get(session_key=anon_client.session.session_key)
        assert cart.items.count() == 2

    def test_one_guest_cannot_move_another_guests_item(self, single_variant_product):
        product, _ = single_variant_product
        owner, intruder = APIClient(), APIClient()
        item_id = owner.post(WISHLIST_URL, {"product_id": product.pk}).data["id"]

        res = intruder.post(move_url(item_id))

        assert res.status_code == status.HTTP_404_NOT_FOUND
        assert Wishlist.objects.filter(pk=item_id).exists()
