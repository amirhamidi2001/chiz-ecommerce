import pytest
from shop.filters import ProductFilter
from shop.models import Product
from shop.tests.factories import (
    BrandFactory,
    CategoryFactory,
    ColorFactory,
    ProductColorFactory,
    ProductFactory,
)


def apply_filter(data):
    """Helper: run ProductFilter over all Products and return the QS."""
    qs = Product.objects.select_related("category", "brand").prefetch_related(
        "colors__color"
    )
    f = ProductFilter(data=data, queryset=qs)
    return f.qs


@pytest.mark.django_db
class TestProductFilterCategory:

    def test_filter_by_category_slug(self):
        cat_a = CategoryFactory(name="Electronics", slug="electronics")
        cat_b = CategoryFactory(name="Clothing", slug="clothing")
        ProductFactory.create_batch(3, category=cat_a)
        ProductFactory.create_batch(2, category=cat_b)

        qs = apply_filter({"category": "electronics"})
        assert qs.count() == 3
        assert all(p.category.slug == "electronics" for p in qs)

    def test_filter_by_category_id(self):
        cat = CategoryFactory()
        ProductFactory.create_batch(2, category=cat)
        ProductFactory()  # different category

        qs = apply_filter({"category": str(cat.id)})
        assert qs.count() == 2

    def test_unknown_category_returns_empty(self):
        ProductFactory.create_batch(3)
        qs = apply_filter({"category": "nonexistent-slug"})
        assert qs.count() == 0


@pytest.mark.django_db
class TestProductFilterBrand:

    def test_filter_by_single_brand_slug(self):
        brand_a = BrandFactory(slug="nike")
        brand_b = BrandFactory(slug="adidas")
        ProductFactory.create_batch(3, brand=brand_a)
        ProductFactory.create_batch(2, brand=brand_b)

        qs = apply_filter({"brand": "nike"})
        assert qs.count() == 3

    def test_filter_by_multiple_brand_slugs(self):
        brand_a = BrandFactory(slug="nike")
        brand_b = BrandFactory(slug="adidas")
        brand_c = BrandFactory(slug="puma")
        ProductFactory.create_batch(2, brand=brand_a)
        ProductFactory.create_batch(2, brand=brand_b)
        ProductFactory.create_batch(2, brand=brand_c)

        qs = apply_filter({"brand": "nike,adidas"})
        assert qs.count() == 4

    def test_filter_by_brand_id(self):
        brand = BrandFactory()
        ProductFactory.create_batch(2, brand=brand)
        ProductFactory()

        qs = apply_filter({"brand": str(brand.id)})
        assert qs.count() == 2

    def test_empty_brand_returns_all(self):
        ProductFactory.create_batch(4)
        qs = apply_filter({"brand": ""})
        assert qs.count() == 4


@pytest.mark.django_db
class TestProductFilterColor:

    def test_filter_by_color_name(self):
        red = ColorFactory(name="Red", hex_code="#ff0000")
        blue = ColorFactory(name="Blue", hex_code="#0000ff")
        p_red = ProductFactory()
        p_blue = ProductFactory()
        ProductColorFactory(product=p_red, color=red)
        ProductColorFactory(product=p_blue, color=blue)

        qs = apply_filter({"color": "Red"})
        assert p_red in qs
        assert p_blue not in qs

    def test_filter_by_multiple_color_ids(self):
        red = ColorFactory(name="Red", hex_code="#ff0000")
        blue = ColorFactory(name="Blue", hex_code="#0000ff")
        p1 = ProductFactory()
        p2 = ProductFactory()
        p3 = ProductFactory()  # no color
        ProductColorFactory(product=p1, color=red)
        ProductColorFactory(product=p2, color=blue)

        qs = apply_filter({"color": f"{red.id},{blue.id}"})
        assert p1 in qs
        assert p2 in qs
        assert p3 not in qs


@pytest.mark.django_db
class TestProductFilterPrice:

    def test_min_price(self):
        ProductFactory(name="Cheap", price=10)
        ProductFactory(name="Mid", price=50)
        ProductFactory(name="Expensive", price=200)

        qs = apply_filter({"min_price": 49})
        names = list(qs.values_list("name", flat=True))
        assert "Cheap" not in names
        assert "Mid" in names
        assert "Expensive" in names

    def test_max_price(self):
        ProductFactory(name="Cheap", price=10)
        ProductFactory(name="Mid", price=50)
        ProductFactory(name="Expensive", price=200)

        qs = apply_filter({"max_price": 51})
        names = list(qs.values_list("name", flat=True))
        assert "Cheap" in names
        assert "Mid" in names
        assert "Expensive" not in names

    def test_price_range(self):
        ProductFactory(name="Low", price=5)
        ProductFactory(name="Mid", price=50)
        ProductFactory(name="High", price=500)

        qs = apply_filter({"min_price": 10, "max_price": 100})
        names = list(qs.values_list("name", flat=True))
        assert names == ["Mid"]


@pytest.mark.django_db
class TestProductFilterFlags:

    def test_is_new_filter(self):
        ProductFactory.create_batch(3, is_new=True)
        ProductFactory.create_batch(2, is_new=False)

        qs = apply_filter({"is_new": True})
        assert qs.count() == 3
        assert all(p.is_new for p in qs)

    def test_is_sale_filter(self):
        ProductFactory.create_batch(4, is_sale=True)
        ProductFactory.create_batch(3, is_sale=False)

        qs = apply_filter({"is_sale": True})
        assert qs.count() == 4

    def test_combined_flags_filter(self):
        ProductFactory.create_batch(2, is_new=True, is_sale=True)
        ProductFactory.create_batch(2, is_new=True, is_sale=False)
        ProductFactory.create_batch(2, is_new=False, is_sale=True)

        qs = apply_filter({"is_new": True, "is_sale": True})
        assert qs.count() == 2


@pytest.mark.django_db
class TestProductFilterSkinType:

    def test_filter_by_single_skin_type(self):
        ProductFactory.create_batch(3, skin_type="oily")
        ProductFactory.create_batch(2, skin_type="dry")

        qs = apply_filter({"skin_type": "oily"})
        assert qs.count() == 3
        assert all(p.skin_type == "oily" for p in qs)

    def test_filter_by_multiple_skin_types_matches_either(self):
        ProductFactory.create_batch(2, skin_type="oily")
        ProductFactory.create_batch(2, skin_type="dry")
        ProductFactory.create_batch(2, skin_type="sensitive")

        qs = apply_filter({"skin_type": "oily,dry"})
        assert qs.count() == 4
        assert all(p.skin_type in ("oily", "dry") for p in qs)

    def test_unmatched_skin_type_returns_empty(self):
        ProductFactory.create_batch(3, skin_type="oily")
        qs = apply_filter({"skin_type": "combination"})
        assert qs.count() == 0

    def test_empty_skin_type_returns_all(self):
        ProductFactory.create_batch(4)
        qs = apply_filter({"skin_type": ""})
        assert qs.count() == 4


@pytest.mark.django_db
class TestProductFilterHairType:

    def test_filter_by_single_hair_type(self):
        ProductFactory.create_batch(2, hair_type="curly")
        ProductFactory.create_batch(3, hair_type="straight")

        qs = apply_filter({"hair_type": "curly"})
        assert qs.count() == 2
        assert all(p.hair_type == "curly" for p in qs)

    def test_filter_by_multiple_hair_types_matches_either(self):
        ProductFactory.create_batch(2, hair_type="curly")
        ProductFactory.create_batch(2, hair_type="coily")
        ProductFactory.create_batch(2, hair_type="straight")

        qs = apply_filter({"hair_type": "curly,coily"})
        assert qs.count() == 4
        assert all(p.hair_type in ("curly", "coily") for p in qs)


@pytest.mark.django_db
class TestProductFilterGender:

    def test_filter_by_gender(self):
        ProductFactory.create_batch(2, gender="male")
        ProductFactory.create_batch(3, gender="female")
        ProductFactory.create_batch(1, gender="unisex")

        qs = apply_filter({"gender": "male"})
        assert qs.count() == 2
        assert all(p.gender == "male" for p in qs)

    def test_filter_by_unisex_gender(self):
        ProductFactory.create_batch(2, gender="unisex")
        ProductFactory.create_batch(2, gender="female")

        qs = apply_filter({"gender": "unisex"})
        assert qs.count() == 2


@pytest.mark.django_db
class TestProductFilterSpf:

    def test_min_spf_excludes_lower_values(self):
        ProductFactory(name="Low SPF", spf=15)
        ProductFactory(name="Mid SPF", spf=30)
        ProductFactory(name="High SPF", spf=50)

        qs = apply_filter({"min_spf": 30})
        names = list(qs.values_list("name", flat=True))
        assert "Low SPF" not in names
        assert "Mid SPF" in names
        assert "High SPF" in names

    def test_min_spf_excludes_null_spf_values(self):
        """
        Explicitly confirm Django's __gte lookup excludes NULL rather
        than assuming it — a product with no SPF at all (spf=None,
        e.g. most haircare) must never match a min_spf filter.
        """
        ProductFactory(name="No SPF", spf=None)
        ProductFactory(name="High SPF", spf=50)

        qs = apply_filter({"min_spf": 30})
        names = list(qs.values_list("name", flat=True))
        assert "No SPF" not in names
        assert "High SPF" in names
        assert qs.count() == 1

    def test_max_spf_excludes_higher_values(self):
        ProductFactory(name="Low SPF", spf=15)
        ProductFactory(name="Mid SPF", spf=30)
        ProductFactory(name="High SPF", spf=50)

        qs = apply_filter({"max_spf": 30})
        names = list(qs.values_list("name", flat=True))
        assert "Low SPF" in names
        assert "Mid SPF" in names
        assert "High SPF" not in names

    def test_max_spf_excludes_null_spf_values(self):
        ProductFactory(name="No SPF", spf=None)
        ProductFactory(name="Low SPF", spf=15)

        qs = apply_filter({"max_spf": 30})
        names = list(qs.values_list("name", flat=True))
        assert "No SPF" not in names
        assert "Low SPF" in names

    def test_spf_range(self):
        ProductFactory(name="Too Low", spf=10)
        ProductFactory(name="In Range", spf=30)
        ProductFactory(name="Too High", spf=70)
        ProductFactory(name="No SPF", spf=None)

        qs = apply_filter({"min_spf": 20, "max_spf": 50})
        names = list(qs.values_list("name", flat=True))
        assert names == ["In Range"]


@pytest.mark.django_db
class TestProductFilterCertificationBadges:

    def test_is_cruelty_free_filter(self):
        ProductFactory.create_batch(3, is_cruelty_free=True)
        ProductFactory.create_batch(2, is_cruelty_free=False)

        qs = apply_filter({"is_cruelty_free": True})
        assert qs.count() == 3
        assert all(p.is_cruelty_free for p in qs)

    def test_is_vegan_filter(self):
        ProductFactory.create_batch(2, is_vegan=True)
        ProductFactory.create_batch(4, is_vegan=False)

        qs = apply_filter({"is_vegan": True})
        assert qs.count() == 2
        assert all(p.is_vegan for p in qs)

    def test_is_organic_filter(self):
        ProductFactory.create_batch(1, is_organic=True)
        ProductFactory.create_batch(3, is_organic=False)

        qs = apply_filter({"is_organic": True})
        assert qs.count() == 1
        assert all(p.is_organic for p in qs)

    def test_is_vegan_false_returns_only_non_vegan(self):
        ProductFactory.create_batch(2, is_vegan=True)
        ProductFactory.create_batch(3, is_vegan=False)

        qs = apply_filter({"is_vegan": False})
        assert qs.count() == 3
        assert all(not p.is_vegan for p in qs)


@pytest.mark.django_db
class TestProductFilterCosmeticsCombined:
    """
    Realistic filter-sidebar usage: multiple new filters applied
    together must AND correctly, exactly as a real frontend filter
    sidebar would query.
    """

    def test_combined_skin_type_vegan_and_min_spf(self):
        # Matches all three criteria.
        match = ProductFactory(name="Match", skin_type="oily", is_vegan=True, spf=30)
        # Fails is_vegan.
        ProductFactory(name="NotVegan", skin_type="oily", is_vegan=False, spf=30)
        # Fails skin_type.
        ProductFactory(name="WrongSkin", skin_type="dry", is_vegan=True, spf=30)
        # Fails min_spf.
        ProductFactory(name="TooLowSpf", skin_type="oily", is_vegan=True, spf=15)
        # Fails min_spf via NULL.
        ProductFactory(name="NoSpf", skin_type="oily", is_vegan=True, spf=None)

        qs = apply_filter({"skin_type": "oily", "is_vegan": True, "min_spf": 30})
        names = list(qs.values_list("name", flat=True))
        assert names == ["Match"]
        assert qs.first().id == match.id

    def test_combined_multi_skin_type_with_gender_and_cruelty_free(self):
        match_a = ProductFactory(
            skin_type="oily", gender="female", is_cruelty_free=True
        )
        match_b = ProductFactory(skin_type="dry", gender="female", is_cruelty_free=True)
        # Fails skin_type (not in the requested set).
        ProductFactory(skin_type="sensitive", gender="female", is_cruelty_free=True)
        # Fails gender.
        ProductFactory(skin_type="oily", gender="male", is_cruelty_free=True)
        # Fails is_cruelty_free.
        ProductFactory(skin_type="oily", gender="female", is_cruelty_free=False)

        qs = apply_filter(
            {
                "skin_type": "oily,dry",
                "gender": "female",
                "is_cruelty_free": True,
            }
        )
        result_ids = set(qs.values_list("id", flat=True))
        assert result_ids == {match_a.id, match_b.id}
