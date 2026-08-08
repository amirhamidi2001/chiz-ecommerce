import pytest
from django.db import IntegrityError

# ══════════════════════════════════════════════════════════════════════════════
# Address
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestAddressModel:

    def _make_addr(self, user, is_default=False, label="home"):
        from dashboard.models import Address

        return Address.objects.create(
            user=user,
            label=label,
            first_name="John",
            last_name="Doe",
            phone="5550001111",
            address_line="1 Test Lane",
            city="Testville",
            state="CA",
            zip_code="90001",
            country="US",
            is_default=is_default,
        )

    def test_first_address_can_be_default(self, customer):
        addr = self._make_addr(customer, is_default=True)
        addr.refresh_from_db()
        assert addr.is_default is True

    def test_setting_new_default_unsets_previous(self, customer):
        first = self._make_addr(customer, is_default=True)
        second = self._make_addr(customer, is_default=True)

        first.refresh_from_db()
        second.refresh_from_db()

        assert second.is_default is True
        assert first.is_default is False

    def test_non_default_address_does_not_affect_others(self, customer):
        default_addr = self._make_addr(customer, is_default=True)
        non_default = self._make_addr(customer, is_default=False)

        default_addr.refresh_from_db()
        assert default_addr.is_default is True
        assert non_default.is_default is False

    def test_different_users_can_both_have_default(self, make_user):
        user_a = make_user(email="a@example.com")
        user_b = make_user(email="b@example.com")
        addr_a = self._make_addr(user_a, is_default=True)
        addr_b = self._make_addr(user_b, is_default=True)

        addr_a.refresh_from_db()
        addr_b.refresh_from_db()
        assert addr_a.is_default is True
        assert addr_b.is_default is True

    def test_full_name_property(self, customer):
        from dashboard.models import Address

        addr = Address(first_name="Jane", last_name="Smith", user=customer)
        assert addr.full_name == "Jane Smith"

    def test_str_contains_label_and_email(self, customer):
        addr = self._make_addr(customer)
        assert "home" in str(addr)
        assert customer.email in str(addr)

    def test_ordering_default_first(self, customer):
        from dashboard.models import Address

        default = self._make_addr(customer, is_default=True)
        addrs = list(Address.objects.filter(user=customer))
        assert addrs[0].id == default.id


# ══════════════════════════════════════════════════════════════════════════════
# Wishlist
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestWishlistModel:

    def test_create_wishlist_item(self, customer, make_product):
        from dashboard.models import Wishlist

        product = make_product()
        item = Wishlist.objects.create(user=customer, product=product)
        assert item.pk is not None

    def test_duplicate_raises_integrity_error(self, customer, make_product):
        from dashboard.models import Wishlist

        product = make_product()
        Wishlist.objects.create(user=customer, product=product)
        with pytest.raises(IntegrityError):
            Wishlist.objects.create(user=customer, product=product)

    def test_same_product_different_users_allowed(self, make_user, make_product):
        from dashboard.models import Wishlist

        user_a = make_user(email="wa@example.com")
        user_b = make_user(email="wb@example.com")
        product = make_product()
        item_a = Wishlist.objects.create(user=user_a, product=product)
        item_b = Wishlist.objects.create(user=user_b, product=product)
        assert item_a.pk != item_b.pk

    def test_str_contains_user_email_and_product_name(self, customer, make_product):
        from dashboard.models import Wishlist

        product = make_product(name="Test Widget")
        item = Wishlist.objects.create(user=customer, product=product)
        assert customer.email in str(item)
        assert "Test Widget" in str(item)

    def test_ordering_newest_first(self, customer, make_product):
        from dashboard.models import Wishlist

        p2 = make_product()
        w2 = Wishlist.objects.create(user=customer, product=p2)
        items = list(Wishlist.objects.filter(user=customer))
        # Newest (w2) should come first
        assert items[0].id == w2.id
