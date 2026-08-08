import factory
from django.utils.text import slugify
from factory.django import DjangoModelFactory
from shop.models import (
    Brand,
    Category,
    Color,
    Product,
    ProductColor,
    ProductImage,
    Review,
)


class CategoryFactory(DjangoModelFactory):
    class Meta:
        model = Category
        django_get_or_create = ("slug",)

    name = factory.Sequence(lambda n: f"Category {n}")
    slug = factory.LazyAttribute(lambda o: slugify(o.name))
    parent = None
    image = None


class ChildCategoryFactory(CategoryFactory):
    parent = factory.SubFactory(CategoryFactory)


class BrandFactory(DjangoModelFactory):
    class Meta:
        model = Brand

    name = factory.Sequence(lambda n: f"Brand {n}")
    slug = factory.LazyAttribute(lambda o: slugify(o.name))
    logo = None


class ColorFactory(DjangoModelFactory):
    class Meta:
        model = Color

    name = factory.Iterator(["Black", "White", "Red", "Blue", "Green"])
    hex_code = factory.Iterator(["#000000", "#FFFFFF", "#E74C3C", "#3498DB", "#2ECC71"])


class ProductFactory(DjangoModelFactory):
    class Meta:
        model = Product
        django_get_or_create = ("slug",)

    category = factory.SubFactory(CategoryFactory)
    brand = factory.SubFactory(BrandFactory)
    name = factory.Sequence(lambda n: f"Product {n}")
    slug = factory.LazyAttribute(lambda o: slugify(o.name))
    short_description = factory.Faker("sentence", nb_words=10)
    description = factory.Faker("paragraph", nb_sentences=5)
    price = factory.Faker("pydecimal", left_digits=3, right_digits=2, positive=True)
    original_price = None
    stock = factory.Faker("pyint", min_value=0, max_value=200)
    rating = factory.Faker(
        "pydecimal", left_digits=1, right_digits=1, min_value=1, max_value=5
    )
    reviews_count = factory.Faker("pyint", min_value=0, max_value=500)
    is_new = False
    is_sale = False
    thumbnail = None


class SaleProductFactory(ProductFactory):
    is_sale = True
    original_price = factory.LazyAttribute(lambda o: o.price * 2)


class NewProductFactory(ProductFactory):
    is_new = True


class ProductImageFactory(DjangoModelFactory):
    class Meta:
        model = ProductImage

    product = factory.SubFactory(ProductFactory)
    image = factory.django.ImageField(color="blue")


class ProductColorFactory(DjangoModelFactory):
    class Meta:
        model = ProductColor

    product = factory.SubFactory(ProductFactory)
    color = factory.SubFactory(ColorFactory)


class ReviewFactory(DjangoModelFactory):
    class Meta:
        model = Review

    product = factory.SubFactory(ProductFactory)
    name = factory.Faker("name")
    rating = factory.Faker("pyint", min_value=1, max_value=5)
    headline = factory.Faker("sentence", nb_words=6)
    comment = factory.Faker("paragraph", nb_sentences=3)
