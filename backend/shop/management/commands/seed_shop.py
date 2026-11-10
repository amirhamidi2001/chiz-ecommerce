"""
Seed the shop with realistic Persian cosmetics demo data.

Why this command is written the way it is (Task 14.4.1.3, ADR 0002):

* It NEVER passes ``slug=`` anywhere. Every Category/Brand/Product slug is
  produced by the model's own ``save()`` (``persian_slugify`` + collision
  loop), so running this command is an end-to-end exercise of the real code
  path, not of ``persian_slugify`` in isolation. (An earlier version computed
  slugs itself in ``get_or_create(defaults={"slug": ...})``, which bypassed
  ``save()`` and so could never have caught a regression in it.)
* Lookups use the NORMALISED name, but creation passes the RAW name. Stored
  names have ZWNJ stripped by ``normalize_persian_text``, so looking a row up by
  its raw name would never match on a re-run (duplicates), while creating from
  the normalised name would throw away the ZWNJ that ``persian_slugify`` needs as
  a word boundary ("مرطوب‌کننده" -> "mrtub-knnde", not "mrtubknnde").
* It verifies its own result and fails loudly if any slug is empty/malformed.
* Output is deterministic (fixed RNG seed), so tests can pin exact slugs.

Notation: in the data below ``~`` stands for ZWNJ (U+200C), which is invisible
in an editor; it is converted by ``z()`` before use.
"""

import random
import re

from core.money import to_whole_toman_rial
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from shop.models import (
    Brand,
    Category,
    Color,
    Product,
    ProductColor,
    ProductVariant,
    Review,
)
from shop.text_utils import normalize_persian_text

ZWNJ = "\u200c"
VALID_SLUG = re.compile(r"^[a-z0-9_]+(-[a-z0-9_]+)*$")
RNG_SEED = 14_4_1_3


def z(text):
    """Seed-data notation: '~' -> ZWNJ."""
    return text.replace("~", ZWNJ)


# (parent, [sub-categories])
CATEGORIES = [
    (
        "مراقبت از پوست",
        [
            "پاک~کننده و شوینده صورت",
            "مرطوب~کننده",
            "سرم و ضد پیری",
            "ضدآفتاب",
            "ماسک صورت",
        ],
    ),
    ("آرایش", ["آرایش صورت", "آرایش چشم", "رژ لب", "لاک ناخن"]),
    ("مراقبت از مو", ["شامپو", "ماسک و نرم~کننده مو", "روغن و سرم مو"]),
    ("عطر و ادکلن", ["عطر زنانه", "عطر مردانه"]),
    ("مراقبت از بدن", ["کرم و لوسیون بدن", "دئودورانت"]),
]

# (name, country of origin). Mix of Persian-script and Latin brand names, as
# Persian shops list both.
BRANDS = [
    ("لورآل پاریس", "فرانسه"),
    ("نیوآ", "آلمان"),
    ("گارنیر", "فرانسه"),
    ("ایزادورا", "سوئد"),
    ("گلدن رز", "ترکیه"),
    ("بیودرما", "فرانسه"),
    ("نوتروژینا", "آمریکا"),
    ("ویشی", "فرانسه"),
    ("اوسرین", "آلمان"),
    ("سراوی", "آمریکا"),
    ("میبلین", "آمریکا"),
    ("The Ordinary", "کانادا"),
    ("Dr. Jart+", "کره جنوبی"),
]

COLORS = [
    ("مشکی", "#111111"),
    ("قهوه~ای", "#5D4037"),
    ("صورتی گلبهی", "#E8A0B4"),
    ("قرمز آتشین", "#C0262B"),
    ("رزگلد", "#B76E79"),
    ("نارنجی مرجانی", "#F2785C"),
    ("آلبالویی", "#7B1F3A"),
    ("بژ روشن", "#EBD3B7"),
    ("بژ طبیعی", "#E2C3A0"),
    ("بژ تیره", "#C49A6C"),
]

# price: Toman (whole). discount: percent or None. variants: list of dicts with
# optional volume (ml) / color / extra (Toman added to the base price).
PRODUCTS = [
    # ── مراقبت از پوست ───────────────────────────────────────────────
    {
        "name": "سرم ویتامین سی ۱۵ درصد روشن~کننده",
        "category": "سرم و ضد پیری",
        "brand": "لورآل پاریس",
        "price": 1_250_000,
        "discount": 20,
        "skin": "all",
        "vegan": True,
        "variants": [{"volume": 30}],
    },
    {
        "name": "سرم هیالورونیک اسید آبرسان",
        "category": "سرم و ضد پیری",
        "brand": "بیودرما",
        "price": 890_000,
        "skin": "dry",
        "variants": [{"volume": 30}, {"volume": 60, "extra": 520_000}],
    },
    {
        "name": "سرم ویتامین C ۱۰٪ ضد لک",
        "category": "سرم و ضد پیری",
        "brand": "ویشی",
        "price": 1_480_000,
        "skin": "all",
        "variants": [{"volume": 30}],
    },
    {
        "name": "The Ordinary Niacinamide 10% + Zinc 1%",
        "category": "سرم و ضد پیری",
        "brand": "The Ordinary",
        "price": 760_000,
        "skin": "oily",
        "vegan": True,
        "cruelty_free": True,
        "variants": [{"volume": 30}],
    },
    {
        "name": "کرم مرطوب~کننده روزانه مناسب پوست خشک",
        "category": "مرطوب~کننده",
        "brand": "نیوآ",
        "price": 389_000,
        "skin": "dry",
        "variants": [{"volume": 50}, {"volume": 100, "extra": 220_000}],
    },
    {
        # Same name as the previous one, different brand: exercises the
        # "-1" collision suffix through the real seeding path.
        "name": "کرم مرطوب~کننده روزانه مناسب پوست خشک",
        "category": "مرطوب~کننده",
        "brand": "اوسرین",
        "price": 640_000,
        "skin": "dry",
        "variants": [{"volume": 50}],
    },
    {
        "name": "ژل شستشوی صورت مناسب پوست چرب",
        "category": "پاک~کننده و شوینده صورت",
        "brand": "سراوی",
        "price": 520_000,
        "discount": 10,
        "skin": "oily",
        "variants": [{"volume": 236}],
    },
    {
        "name": "ضدآفتاب بی~رنگ SPF50+ مناسب پوست چرب",
        "category": "ضدآفتاب",
        "brand": "ویشی",
        "price": 495_000,
        "skin": "oily",
        "spf": 50,
        "variants": [{"volume": 50}, {"volume": 75, "extra": 150_000}],
    },
    {
        # Same name again (second brand) -> "-1".
        "name": "ضدآفتاب بی~رنگ SPF50+ مناسب پوست چرب",
        "category": "ضدآفتاب",
        "brand": "نوتروژینا",
        "price": 430_000,
        "discount": 15,
        "skin": "oily",
        "spf": 50,
        "variants": [{"volume": 50}],
    },
    {
        "name": "ضدآفتاب رنگی SPF30 پوست مختلط",
        "category": "ضدآفتاب",
        "brand": "ایزادورا",
        "price": 575_000,
        "skin": "combination",
        "spf": 30,
        "variants": [
            {"color": "بژ روشن", "volume": 40},
            {"color": "بژ طبیعی", "volume": 40},
        ],
    },
    {
        "name": "ماسک صورت زغال فعال ۱۰۰ میلی~لیتر",
        "category": "ماسک صورت",
        "brand": "گارنیر",
        "price": 210_000,
        "skin": "oily",
        "variants": [{"volume": 100}],
    },
    {
        "name": "تونر نیاسینامید ۱۰٪ کنترل~کننده چربی",
        "category": "پاک~کننده و شوینده صورت",
        "brand": "سراوی",
        "price": 480_000,
        "skin": "oily",
        "variants": [{"volume": 200}],
    },
    {
        "name": "کرم دور چشم رتینول ضد چروک",
        "category": "سرم و ضد پیری",
        "brand": "بیودرما",
        "price": 1_050_000,
        "skin": "sensitive",
        "variants": [{"volume": 15}],
    },
    {
        "name": "Dr. Jart+ Cicapair Tiger Grass Cream",
        "category": "مرطوب~کننده",
        "brand": "Dr. Jart+",
        "price": 1_890_000,
        "discount": 12,
        "skin": "sensitive",
        "cruelty_free": True,
        "variants": [{"volume": 50}],
    },
    # ── آرایش ────────────────────────────────────────────────────────
    {
        "name": "کرم پودر مات 24H",
        "category": "آرایش صورت",
        "brand": "میبلین",
        "price": 720_000,
        "skin": "combination",
        "spf": 15,
        "variants": [
            {"color": "بژ روشن", "volume": 30},
            {"color": "بژ طبیعی", "volume": 30},
            {"color": "بژ تیره", "volume": 30},
        ],
    },
    {
        "name": "ریمل حجم~دهنده ضدآب",
        "category": "آرایش چشم",
        "brand": "میبلین",
        "price": 340_000,
        "variants": [{"color": "مشکی"}],
    },
    {
        "name": "خط چشم ماژیکی مشکی ماندگار",
        "category": "آرایش چشم",
        "brand": "ایزادورا",
        "price": 275_000,
        "discount": 10,
        "variants": [{"color": "مشکی"}, {"color": "قهوه~ای"}],
    },
    {
        "name": "رژ لب مایع مات ماندگار",
        "category": "رژ لب",
        "brand": "گلدن رز",
        "price": 285_000,
        "discount": 15,
        "cruelty_free": True,
        "variants": [
            {"color": "صورتی گلبهی"},
            {"color": "قرمز آتشین"},
            {"color": "رزگلد", "extra": 10_000},
            {"color": "نارنجی مرجانی"},
        ],
    },
    {
        "name": "رژ لب جامد کرمی",
        "category": "رژ لب",
        "brand": "ایزادورا",
        "price": 360_000,
        "variants": [{"color": "آلبالویی"}, {"color": "صورتی گلبهی"}],
    },
    {
        "name": "لاک ناخن ژله~ای",
        "category": "لاک ناخن",
        "brand": "گلدن رز",
        "price": 95_000,
        "variants": [
            {"color": "قرمز آتشین"},
            {"color": "آلبالویی"},
            {"color": "رزگلد"},
        ],
    },
    # ── مراقبت از مو ─────────────────────────────────────────────────
    {
        "name": "شامپو ترمیم~کننده موهای رنگ~شده",
        "category": "شامپو",
        "brand": "لورآل پاریس",
        "price": 265_000,
        "discount": 10,
        "hair": "all",
        "variants": [{"volume": 250}, {"volume": 400, "extra": 120_000}],
    },
    {
        "name": "ماسک مو کراتین ۲۵۰ میلی~لیتر",
        "category": "ماسک و نرم~کننده مو",
        "brand": "گارنیر",
        "price": 410_000,
        "hair": "all",
        "variants": [{"volume": 250}],
    },
    {
        "name": "روغن آرگان مو بدون آبکشی",
        "category": "روغن و سرم مو",
        "brand": "گارنیر",
        "price": 340_000,
        "hair": "curly",
        "organic": True,
        "variants": [{"volume": 100}],
    },
    {
        "name": "سرم تقویت~کننده ریشه مو",
        "category": "روغن و سرم مو",
        "brand": "ویشی",
        "price": 1_150_000,
        "hair": "all",
        "variants": [{"volume": 90}],
    },
    # ── عطر و ادکلن ──────────────────────────────────────────────────
    {
        "name": "ادکلن زنانه گل~های بهاری ۱۰۰ میلی~لیتر",
        "category": "عطر زنانه",
        "brand": "گلدن رز",
        "price": 2_150_000,
        "gender": "female",
        "variants": [{"volume": 100}],
    },
    {
        "name": "ادکلن مردانه چوب و عنبر ۱۰۰ میلی~لیتر",
        "category": "عطر مردانه",
        "brand": "گلدن رز",
        "price": 2_350_000,
        "gender": "male",
        "variants": [{"volume": 100}],
    },
    # ── مراقبت از بدن ────────────────────────────────────────────────
    {
        "name": "لوسیون بدن شیر و عسل",
        "category": "کرم و لوسیون بدن",
        "brand": "نیوآ",
        "price": 275_000,
        "variants": [{"volume": 250}, {"volume": 400, "extra": 90_000}],
    },
    {
        "name": "کرم دست ترمیم~کننده",
        "category": "کرم و لوسیون بدن",
        "brand": "نیوآ",
        "price": 140_000,
        "variants": [{"volume": 75}],
    },
    {
        "name": "دئودورانت ضد تعریق مردانه",
        "category": "دئودورانت",
        "brand": "نیوآ",
        "price": 185_000,
        "gender": "male",
        "variants": [{"volume": 150}],
    },
]

SHORT_DESCRIPTIONS = [
    "فرمولی سبک و غیرچرب برای استفاده روزانه.",
    "جذب سریع، بدون حس چسبندگی؛ مناسب تمام فصل‌ها.",
    "تولید شده با مواد اولیه مرغوب و آزمایش‌شده.",
    "انتخاب مناسب برای مراقبت روزمره و نتیجه ماندگار.",
]
DESCRIPTIONS = [
    "این محصول با فرمولی سبک و غیرچرب طراحی شده و به‌راحتی در استفاده روزانه "
    "جایگزین می‌شود. مواد فعال آن آزمایش شده‌اند و پس از چند هفته استفاده "
    "منظم نتیجه قابل مشاهده است. پیش از اولین استفاده، آزمایش حساسیت روی "
    "ناحیه کوچکی از پوست توصیه می‌شود.",
    "بافتی لطیف و جذب سریع دارد و حس چسبندگی روی پوست یا مو باقی نمی‌گذارد. "
    "برای استفاده در تمام فصل‌ها مناسب است و با سایر محصولات مراقبتی "
    "هم‌خوانی دارد.",
]
USAGE = [
    "پس از شستن و خشک کردن، مقدار کمی از محصول را روی ناحیه مورد نظر بمالید "
    "و به‌آرامی ماساژ دهید. صبح و شب قابل استفاده است.",
]
WARNINGS = [
    "فقط جهت استفاده خارجی. از تماس با چشم‌ها خودداری کنید و در صورت بروز "
    "تحریک، مصرف را قطع کنید. دور از دسترس کودکان نگه‌داری شود.",
]
INGREDIENTS = "Aqua, Glycerin, Niacinamide, Tocopherol, Parfum"

REVIEW_NAMES = [
    "سارا احمدی",
    "مریم کریمی",
    "نگار رضایی~فر",
    "زهرا حسینی",
    "الهام محمدی",
    "فاطمه موسوی",
    "علیرضا نوری",
    "پریسا جعفری",
    "نسترن صادقی",
    "مهدی کاظمی",
    "الهه رحیمی",
    "نیلوفر عباسی",
]
REVIEW_HEADLINES = [
    "خیلی راضی هستم",
    "کیفیت عالی",
    "ارزش خرید دارد",
    "مناسب پوست من بود",
    "بسته‌بندی مرتب",
    "نتیجه بعد از دو هفته",
    "معمولی بود",
    "دوباره می‌خرم",
]
REVIEW_COMMENTS = [
    "بعد از دو هفته استفاده نتیجه‌اش رو دیدم. بافتش سبک و زود جذب میشه.",
    "بسته‌بندی مرتب بود و سریع به دستم رسید. کیفیت محصول با قیمتش همخوانی داره.",
    "برای پوست من که حساسه مناسب بود و هیچ حساسیتی ایجاد نکرد.",
    "رایحه‌اش ملایمه و ماندگاری خوبی داره، فقط کاش حجمش بیشتر بود.",
    "انتظار بیشتری داشتم؛ بد نیست ولی خیلی هم فوق‌العاده نبود.",
    "همون چیزیه که توضیح داده شده. قیمتش نسبت به بقیه فروشگاه‌ها مناسب‌تره.",
]


def get_or_create_named(model, raw_name, lookup=None, **fields):
    """
    Idempotent get-or-create that goes through the REAL ``save()`` slug path.

    Looks the row up by the NORMALISED name (what is stored) but creates it from
    the RAW name, so ``save()`` still sees the ZWNJ word boundaries. Never
    passes ``slug``. Returns ``(obj, created)``.
    """
    lookup = lookup or {}
    existing = model.objects.filter(
        name=normalize_persian_text(raw_name), **lookup
    ).first()
    if existing:
        return existing, False
    obj = model(name=raw_name, **lookup, **fields)
    obj.save()
    return obj, True


class Command(BaseCommand):
    help = "Seed the shop with realistic Persian cosmetics demo data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing shop data before seeding",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        rng = random.Random(RNG_SEED)

        if options["clear"]:
            self.stdout.write("Clearing existing shop data...")
            Review.objects.all().delete()
            ProductColor.objects.all().delete()
            Product.objects.all().delete()  # cascades to variants/images
            Color.objects.all().delete()
            Brand.objects.all().delete()
            Category.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("Cleared."))

        # ── Categories ───────────────────────────────────────────────────
        self.stdout.write("Creating categories...")
        categories = {}
        for parent_name, subs in CATEGORIES:
            parent, _ = get_or_create_named(Category, z(parent_name), {"parent": None})
            categories[parent_name] = parent
            for sub_name in subs:
                sub, _ = get_or_create_named(Category, z(sub_name), {"parent": parent})
                categories[sub_name] = sub
        self.stdout.write(self.style.SUCCESS(f"  {len(categories)} categories."))

        # ── Brands ───────────────────────────────────────────────────────
        self.stdout.write("Creating brands...")
        brands, countries = {}, {}
        for name, country in BRANDS:
            brands[name], _ = get_or_create_named(Brand, z(name))
            countries[name] = country
        self.stdout.write(self.style.SUCCESS(f"  {len(brands)} brands."))

        # ── Colors ───────────────────────────────────────────────────────
        colors = {}
        for name, hex_code in COLORS:
            colors[name], _ = Color.objects.get_or_create(
                name=normalize_persian_text(z(name)), defaults={"hex_code": hex_code}
            )

        # ── Products (+ variants, colors, reviews) ───────────────────────
        self.stdout.write("Creating products...")
        created = 0
        for index, spec in enumerate(PRODUCTS):
            brand = brands[spec["brand"]]
            product, was_created = get_or_create_named(
                Product,
                z(spec["name"]),
                {"brand": brand},
                category=categories[spec["category"]],
                short_description=rng.choice(SHORT_DESCRIPTIONS),
                description=rng.choice(DESCRIPTIONS),
                ingredients=INGREDIENTS,
                usage_instructions=USAGE[0],
                warnings=WARNINGS[0],
                country_of_origin=countries[spec["brand"]],
                price=to_whole_toman_rial(spec["price"] * 10),
                stock=0,
                is_new=index % 5 == 0,
                is_sale=bool(spec.get("discount")),
                is_vegan=spec.get("vegan", False),
                is_cruelty_free=spec.get("cruelty_free", False),
                is_organic=spec.get("organic", False),
                skin_type=spec.get("skin", ""),
                hair_type=spec.get("hair", ""),
                gender=spec.get("gender", "unisex"),
                spf=spec.get("spf"),
            )
            if not was_created:
                continue
            created += 1
            self._create_variants(product, spec, colors, rng)
            self._create_reviews(product, rng)

        self.stdout.write(
            self.style.SUCCESS(
                f"  {created} new products ({Product.objects.count()} total)."
            )
        )

        self._verify_slugs()
        self.stdout.write(self.style.SUCCESS("\n✅  Shop seeding complete!"))
        self.stdout.write(
            "  Note: product images/thumbnails must be uploaded via admin or API."
        )

    # ------------------------------------------------------------------ #

    def _create_variants(self, product, spec, colors, rng):
        discount = spec.get("discount")
        in_stock_somewhere = False
        total_stock = 0
        prices = []
        for position, v in enumerate(spec["variants"]):
            original = to_whole_toman_rial((spec["price"] + v.get("extra", 0)) * 10)
            price = (
                to_whole_toman_rial(original * (100 - discount) / 100)
                if discount
                else original
            )
            # Make sure at least one variant is purchasable; allow the odd
            # sold-out variant so the out-of-stock UI has something to show.
            stock = (
                rng.choice([0, 4, 12, 30, 60]) if position else rng.choice([12, 30, 60])
            )
            in_stock_somewhere |= stock > 0
            total_stock += stock
            color = colors[v["color"]] if "color" in v else None
            ProductVariant.objects.create(
                product=product,
                color=color,
                volume_ml=v.get("volume"),
                price=price,
                original_price=original if discount else None,
                stock=stock,
                is_active=True,
            )
            prices.append(price)
            if color is not None:
                ProductColor.objects.get_or_create(product=product, color=color)
        assert in_stock_somewhere
        Product.objects.filter(pk=product.pk).update(
            price=min(prices),
            original_price=(
                to_whole_toman_rial(spec["price"] * 10) if discount else None
            ),
            stock=total_stock,
        )

    def _create_reviews(self, product, rng):
        ratings = []
        for _ in range(rng.randint(2, 5)):
            rating = rng.choice([3, 4, 4, 5, 5, 5])
            ratings.append(rating)
            Review.objects.create(
                product=product,
                name=z(rng.choice(REVIEW_NAMES)),
                rating=rating,
                headline=rng.choice(REVIEW_HEADLINES),
                comment=rng.choice(REVIEW_COMMENTS),
                is_verified_purchase=rng.random() < 0.5,
                is_approved=True,
            )
        Product.objects.filter(pk=product.pk).update(
            rating=round(sum(ratings) / len(ratings), 1),
            reviews_count=len(ratings),
        )

    def _verify_slugs(self):
        """Fail loudly if the real save() path produced any empty/malformed slug."""
        bad = []
        for model in (Category, Brand, Product):
            for obj in model.objects.all():
                if not VALID_SLUG.match(obj.slug):
                    bad.append(f"{model.__name__} #{obj.pk} {obj.name!r}: {obj.slug!r}")
        if bad:
            raise CommandError(
                "Slug generation produced invalid slugs:\n  " + "\n  ".join(bad)
            )
        self.stdout.write("  Sample slugs (name -> slug):")
        for product in Product.objects.order_by("pk")[:4]:
            self.stdout.write(f"    {product.name}  ->  {product.slug}")
        self.stdout.write(
            self.style.SUCCESS(
                "  All category/brand/product slugs are valid and non-empty."
            )
        )
