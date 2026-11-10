"""
Seed the blog with realistic Persian articles, categories and comments.

Like seed_shop (Task 14.4.1.3, ADR 0002) this NEVER passes ``slug=``: every slug
comes from the model's own ``save()`` (``persian_slugify`` + collision loop), so
running it exercises the real slug path end to end.

Fixes over the previous version: it no longer crashes on a fresh database
(``create_user(username=...)`` - the user model has no ``username``), it no
longer deletes all blog data on every run (use ``--clear`` explicitly), and it is
deterministic and Faker-free. Notation: ``~`` in the data below is ZWNJ.
"""

import random
import re
from datetime import timedelta

from blog.models import Category, Comment, Post
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

User = get_user_model()

VALID_SLUG = re.compile(r"^[a-z0-9_]+(-[a-z0-9_]+)*$")
RNG_SEED = 14_4_1_3


def z(text):
    """Seed-data notation: '~' -> ZWNJ (invisible in editors)."""
    return text.replace("~", "\u200c")


CATEGORIES = [
    "راهنمای مراقبت از پوست",
    "آرایش و زیبایی",
    "مراقبت از مو",
    "عطر و ادکلن",
    "سلامت و تغذیه",
]

# (title, category index)
POSTS = [
    ("راهنمای کامل انتخاب ضدآفتاب مناسب پوست", 0),
    ("ترتیب صحیح استفاده از سرم و مرطوب~کننده", 0),
    ("ویتامین C چیست و چه فوایدی برای پوست دارد؟", 0),
    ("چگونه پوست خشک را در زمستان مرطوب نگه داریم؟", 0),
    ("۵ اشتباه رایج در شستشوی صورت", 0),
    ("نیاسینامید برای پوست~های چرب؛ همه آنچه باید بدانید", 0),
    ("بهترین رنگ رژ لب متناسب با رنگ پوست", 1),
    ("آموزش انتخاب کرم پودر مناسب", 1),
    ("مراقبت از موهای رنگ~شده در تابستان", 2),
    ("ماسک مو کراتین: کی و چطور استفاده کنیم؟", 2),
    ("تفاوت عطر، ادکلن و ادوپرفیوم", 3),
    ("چطور ماندگاری عطر را بیشتر کنیم؟", 3),
]

EXCERPTS = [
    "در این مقاله نکات کاربردی و ساده را برای شروع مراقبت اصولی مرور می‌کنیم.",
    "پاسخ به رایج‌ترین پرسش‌ها، همراه با توصیه‌هایی که می‌توانید همین امروز امتحان کنید.",
    "اگر تازه شروع کرده‌اید، این راهنما مسیر انتخاب درست را برایتان روشن می‌کند.",
]
PARAGRAPHS = [
    "مراقبت اصولی از پوست و مو نیازی به استفاده از ده‌ها محصول ندارد؛ مهم این است "
    "که محصولی مناسب نوع پوست خود انتخاب کنید و آن را به‌طور منظم و در زمان "
    "درست استفاده کنید.",
    "پیش از استفاده از هر محصول جدید، آزمایش حساسیت روی ناحیه کوچکی از پوست "
    "انجام دهید و در صورت بروز قرمزی یا سوزش، مصرف آن را متوقف کنید.",
    "نتیجه‌گیری از مراقبت‌های پوستی زمان‌بر است. معمولاً بین چهار تا شش هفته "
    "استفاده مداوم لازم است تا تغییرات قابل مشاهده شود.",
    "همیشه برچسب محصول را بخوانید و به فهرست مواد تشکیل‌دهنده توجه کنید. "
    "ترکیب‌های فعال را به‌تدریج و یکی‌یکی وارد برنامه مراقبتی خود کنید.",
    "تغذیه مناسب، خواب کافی و نوشیدن آب به اندازه کافی در کنار محصولات "
    "مراقبتی، نقش مهمی در سلامت و شادابی پوست و مو دارند.",
    "اگر مشکل پوستی شما ادامه‌دار است، حتماً با پزشک متخصص پوست مشورت کنید؛ "
    "محصولات آرایشی و بهداشتی جایگزین درمان پزشکی نیستند.",
]
COMMENTER_NAMES = [
    "سارا احمدی",
    "مریم کریمی",
    "زهرا حسینی",
    "علیرضا نوری",
    "پریسا جعفری",
    "مهدی کاظمی",
    "نیلوفر عباسی",
    "الهام محمدی",
]
COMMENT_BODIES = [
    "مطلب خیلی مفیدی بود، ممنون از توضیحات کامل‌تان.",
    "من هم همین مشکل را داشتم و با این روش بهتر شد.",
    "ممنون می‌شوم درباره پوست حساس هم یک مقاله بنویسید.",
    "عالی بود! بالاخره تفاوت این‌ها را متوجه شدم.",
]


class Command(BaseCommand):
    help = "Seed the blog with realistic Persian categories, posts, and comments"

    def add_arguments(self, parser):
        parser.add_argument(
            "--posts",
            type=int,
            default=len(POSTS),
            help="Number of posts (titles repeat after %d)" % len(POSTS),
        )
        parser.add_argument(
            "--comments", type=int, default=40, help="Number of comments to create"
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing blog comments, posts and categories first",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        rng = random.Random(RNG_SEED)

        if options["clear"]:
            self.stdout.write("Clearing existing blog data...")
            Comment.objects.all().delete()
            Post.objects.all().delete()
            Category.objects.all().delete()

        categories = [
            Category.objects.get_or_create(name=z(name))[0] for name in CATEGORIES
        ]
        self.stdout.write(f"Categories: {len(categories)}")

        authors = list(User.objects.all())
        if not authors:
            for n in range(1, 4):
                authors.append(
                    User.objects.create_user(
                        email=f"author{n}@example.com",
                        password="password123",
                        is_verified=True,
                    )
                )
            self.stdout.write("Created 3 demo authors (password: password123)")

        posts, created_posts = [], 0
        for i in range(options["posts"]):
            title, cat_index = POSTS[i % len(POSTS)]
            title = z(title)
            published = i % 6 != 5  # every 6th post stays a draft
            post, created = Post.objects.get_or_create(
                title=title,
                defaults={
                    "excerpt": rng.choice(EXCERPTS),
                    "content": "\n\n".join(rng.sample(PARAGRAPHS, k=4)),
                    "author": rng.choice(authors),
                    "category": categories[cat_index],
                    "status": (
                        Post.Status.PUBLISHED if published else Post.Status.DRAFT
                    ),
                    "is_featured": i % 4 == 0,
                    "views_count": rng.randint(0, 5000),
                },
            )
            if created:
                created_posts += 1
                if published:
                    post.published_at = post.created_at + timedelta(
                        days=rng.randint(0, 30)
                    )
                    post.save(update_fields=["published_at"])
            posts.append(post)
        self.stdout.write(f"Posts: {created_posts} new ({Post.objects.count()} total)")

        if created_posts:
            comments = []
            for n in range(options["comments"]):
                parent = (
                    rng.choice(comments) if comments and rng.random() < 0.2 else None
                )
                comment = Comment.objects.create(
                    post=parent.post if parent else rng.choice(posts),
                    parent=parent,
                    name=rng.choice(COMMENTER_NAMES),
                    email=f"reader{n + 1}@example.com",
                    body=rng.choice(COMMENT_BODIES),
                    is_approved=rng.random() < 0.8,
                )
                comments.append(comment)
            self.stdout.write(f"Comments: {len(comments)}")

        self._verify_slugs()

    def _verify_slugs(self):
        bad = [
            f"{type(o).__name__} #{o.pk} {getattr(o, 'name', None) or o.title!r}: {o.slug!r}"
            for model in (Category, Post)
            for o in model.objects.all()
            if not VALID_SLUG.match(o.slug)
        ]
        if bad:
            raise CommandError(
                "Slug generation produced invalid slugs:\n  " + "\n  ".join(bad)
            )
        self.stdout.write(
            self.style.SUCCESS("All blog category/post slugs are valid and non-empty.")
        )
