import random

from django.core.management.base import BaseCommand
from django.utils.text import slugify
from shop.models import (
    Brand,
    Category,
    Color,
    Product,
    ProductColor,
    ProductImage,
    Review,
)

CATEGORIES = [
    {
        "name": "Electronics",
        "subs": ["Smartphones", "Laptops", "Tablets", "Audio", "Cameras"],
    },
    {
        "name": "Clothing",
        "subs": ["Men's Wear", "Women's Wear", "Kids' Clothing", "Activewear"],
    },
    {
        "name": "Home & Kitchen",
        "subs": ["Furniture", "Kitchen Appliances", "Home Decor", "Bedding"],
    },
    {
        "name": "Beauty & Personal Care",
        "subs": ["Skincare", "Makeup", "Hair Care", "Fragrances"],
    },
    {
        "name": "Sports & Outdoors",
        "subs": ["Fitness Equipment", "Outdoor Gear", "Sports Apparel"],
    },
    {"name": "Books", "subs": []},
    {
        "name": "Toys & Games",
        "subs": ["Board Games", "Puzzles", "Action Figures", "Educational Toys"],
    },
]

BRANDS = [
    "Nike",
    "Adidas",
    "Apple",
    "Samsung",
    "Sony",
    "Puma",
    "Reebok",
    "Under Armour",
    "New Balance",
    "Converse",
    "Dell",
    "LG",
    "Bose",
    "Logitech",
    "Philips",
]

COLORS = [
    ("Black", "#000000"),
    ("White", "#FFFFFF"),
    ("Red", "#E74C3C"),
    ("Blue", "#3498DB"),
    ("Teal", "#1ABC9C"),
    ("Yellow", "#F1C40F"),
    ("Purple", "#9B59B6"),
    ("Orange", "#E67E22"),
    ("Pink", "#FD79A8"),
    ("Brown", "#795548"),
    ("Gray", "#95A5A6"),
    ("Navy", "#2C3E50"),
]

REVIEW_NAMES = [
    "Sarah Martinez",
    "David Chen",
    "Emily Rodriguez",
    "James Wilson",
    "Olivia Johnson",
    "Liam Brown",
    "Sophia Davis",
    "Noah Garcia",
    "Ava Miller",
    "William Moore",
    "Isabella Taylor",
    "Mason Anderson",
]

REVIEW_HEADLINES = [
    "Outstanding quality and value!",
    "Exceeded my expectations",
    "Great product, fast delivery",
    "Highly recommend this item",
    "Perfect for everyday use",
    "Good product with minor issues",
    "Exactly as described",
    "Very satisfied with this purchase",
    "Will buy again",
    "Worth every penny",
]

REVIEW_COMMENTS = [
    "Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium doloremque laudantium. Totam rem aperiam eaque ipsa quae ab illo inventore veritatis.",
    "Nemo enim ipsam voluptatem quia voluptas sit aspernatur aut odit aut fugit, sed quia consequuntur magni dolores eos qui ratione voluptatem sequi nesciunt.",
    "At vero eos et accusamus et iusto odio dignissimos ducimus qui blanditiis praesentium voluptatum deleniti atque corrupti quos dolores.",
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam.",
    "Quis autem vel eum iure reprehenderit qui in ea voluptate velit esse quam nihil molestiae consequatur, vel illum qui dolorem eum fugiat quo voluptas nulla pariatur.",
]

PRODUCT_NAMES = [
    "Pro Wireless Headphones",
    "Ultra Slim Laptop",
    "4K Smart TV",
    "Running Shoes Elite",
    "Casual Linen Shirt",
    "Ergonomic Office Chair",
    "Ceramic Coffee Mug Set",
    "Anti-Aging Serum",
    "Yoga Mat Premium",
    "Strategy Board Game",
    "Wireless Bluetooth Speaker",
    "Mechanical Keyboard",
    "Stainless Steel Water Bottle",
    "Leather Wallet",
    "Fitness Tracker Band",
    "Noise-Cancelling Earbuds",
    "Gaming Mouse",
    "Bamboo Cutting Board",
    "Face Moisturizer SPF 50",
    "Trail Running Backpack",
    "Smart Watch Series X",
    "Premium Denim Jacket",
    "Portable Charger 20000mAh",
    "Cast Iron Skillet",
    "Kids' Building Blocks Set",
    "Memory Foam Pillow",
    "Electric Toothbrush",
    "Outdoor Camping Tent",
    "Silk Pillowcase",
    "Protein Powder Vanilla",
]

SHORT_DESCRIPTIONS = [
    "Premium quality product crafted for performance and durability.",
    "Modern design meets everyday functionality in this must-have item.",
    "Experience top-tier quality at an unbeatable price point.",
    "Designed for those who demand the best in style and performance.",
    "The perfect blend of comfort, quality, and value.",
]


class Command(BaseCommand):
    help = "Seed the shop database with sample data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing shop data before seeding",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            self.stdout.write("Clearing existing shop data...")
            Review.objects.all().delete()
            ProductColor.objects.all().delete()
            ProductImage.objects.all().delete()
            Product.objects.all().delete()
            Color.objects.all().delete()
            Brand.objects.all().delete()
            Category.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("Cleared."))

        # ── Categories ───────────────────────────────────────────────────
        self.stdout.write("Creating categories...")
        cat_objects = {}
        for cat_data in CATEGORIES:
            parent, _ = Category.objects.get_or_create(
                name=cat_data["name"],
                defaults={"slug": slugify(cat_data["name"])},
            )
            cat_objects[cat_data["name"]] = parent
            for sub_name in cat_data["subs"]:
                Category.objects.get_or_create(
                    name=sub_name,
                    defaults={"slug": slugify(sub_name), "parent": parent},
                )
        self.stdout.write(
            self.style.SUCCESS(f"  {Category.objects.count()} categories created.")
        )

        # ── Brands ───────────────────────────────────────────────────────
        self.stdout.write("Creating brands...")
        brand_objects = []
        for brand_name in BRANDS:
            brand, _ = Brand.objects.get_or_create(
                name=brand_name,
                defaults={"slug": slugify(brand_name)},
            )
            brand_objects.append(brand)
        self.stdout.write(self.style.SUCCESS(f"  {len(brand_objects)} brands created."))

        # ── Colors ───────────────────────────────────────────────────────
        self.stdout.write("Creating colors...")
        color_objects = []
        for color_name, hex_code in COLORS:
            color, _ = Color.objects.get_or_create(
                name=color_name, defaults={"hex_code": hex_code}
            )
            color_objects.append(color)
        self.stdout.write(self.style.SUCCESS(f"  {len(color_objects)} colors created."))

        # ── Products ─────────────────────────────────────────────────────
        self.stdout.write("Creating products...")
        all_categories = list(Category.objects.all())
        created_products = []

        for i, product_name in enumerate(PRODUCT_NAMES):
            price = round(random.uniform(15, 400), 2)
            has_discount = random.random() > 0.4
            original_price = (
                round(price * random.uniform(1.15, 1.6), 2) if has_discount else None
            )
            rating = round(random.uniform(3.5, 5.0), 1)
            reviews_count = random.randint(5, 250)
            stock = random.randint(0, 100)

            product, created = Product.objects.get_or_create(
                name=product_name,
                defaults={
                    "category": random.choice(all_categories),
                    "brand": random.choice(brand_objects),
                    "short_description": random.choice(SHORT_DESCRIPTIONS),
                    "description": (
                        "Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium "
                        "doloremque laudantium, totam rem aperiam, eaque ipsa quae ab illo inventore "
                        "veritatis et quasi architecto beatae vitae dicta sunt explicabo. Nemo enim "
                        "ipsam voluptatem quia voluptas sit aspernatur aut odit aut fugit, sed quia "
                        "consequuntur magni dolores eos qui ratione voluptatem sequi nesciunt."
                    ),
                    "price": price,
                    "original_price": original_price,
                    "stock": stock,
                    "rating": rating,
                    "reviews_count": reviews_count,
                    "is_new": i % 6 == 0,
                    "is_sale": has_discount and i % 5 == 2,
                },
            )

            if created:
                # Assign 2-4 random colors
                chosen_colors = random.sample(color_objects, k=random.randint(2, 4))
                for color in chosen_colors:
                    ProductColor.objects.get_or_create(product=product, color=color)

                # Create 3-6 reviews
                num_reviews = random.randint(3, 6)
                for _ in range(num_reviews):
                    Review.objects.create(
                        product=product,
                        name=random.choice(REVIEW_NAMES),
                        rating=random.randint(3, 5),
                        headline=random.choice(REVIEW_HEADLINES),
                        comment=random.choice(REVIEW_COMMENTS),
                    )

            created_products.append(product)

        self.stdout.write(
            self.style.SUCCESS(f"  {len(created_products)} products processed.")
        )
        self.stdout.write(self.style.SUCCESS("\n✅  Shop seeding complete!"))
        self.stdout.write(
            "  Note: Product images/thumbnails must be uploaded manually via admin or API.\n"
            "  You can use placeholder images from: https://picsum.photos/400/300"
        )
