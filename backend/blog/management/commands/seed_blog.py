import random
from datetime import timedelta

from blog.models import Category, Comment, Post
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from faker import Faker

User = get_user_model()
fake = Faker()


class Command(BaseCommand):
    help = "Generate fake blog posts, categories, and comments"

    def add_arguments(self, parser):
        parser.add_argument(
            "--posts", type=int, default=50, help="Number of posts to create"
        )
        parser.add_argument(
            "--comments", type=int, default=200, help="Number of comments to create"
        )

    def handle(self, *args, **options):
        self.stdout.write("Clearing existing data...")
        Comment.objects.all().delete()
        Post.objects.all().delete()
        Category.objects.all().delete()

        # ---------- Categories ----------
        categories = []
        category_names = [
            "Technology",
            "Lifestyle",
            "Travel",
            "Food",
            "Health",
            "Business",
            "Education",
            "Entertainment",
            "Sports",
            "Science",
        ]
        for name in category_names:
            cat = Category(name=name)
            cat.save()  # save individually to trigger slug generation
            categories.append(cat)
        self.stdout.write(f"Created {len(categories)} categories")

        # ---------- Users (authors) ----------
        # If you have no users yet, create a few
        users = list(User.objects.all())
        if not users:
            for _ in range(5):
                user = User.objects.create_user(
                    username=fake.unique.user_name(),
                    email=fake.email(),
                    password="password123",
                )
                users.append(user)
            self.stdout.write("Created 5 demo users (password: password123)")

        # ---------- Posts ----------
        posts = []
        for i in range(options["posts"]):
            title = fake.sentence(nb_words=8)[:-1]  # remove trailing dot
            content = "\n\n".join(fake.paragraphs(nb=15))
            excerpt = fake.paragraph(nb_sentences=3)
            status = random.choice([Post.Status.DRAFT, Post.Status.PUBLISHED])
            is_featured = random.choice([True, False])
            views = random.randint(0, 5000)
            author = random.choice(users) if users else None
            category = random.choice(categories)

            post = Post(
                title=title,
                excerpt=excerpt,
                content=content,
                author=author,
                category=category,
                status=status,
                is_featured=is_featured,
                views_count=views,
            )
            # We save each post so that slug and read_time are auto‑computed
            post.save()

            # Set published_at only for published posts
            if status == Post.Status.PUBLISHED:
                post.published_at = post.created_at + timedelta(
                    days=random.randint(0, 30)
                )
                post.save(update_fields=["published_at"])

            posts.append(post)

            if (i + 1) % 20 == 0:
                self.stdout.write(f"Created {i + 1} posts")

        self.stdout.write(f"Created {len(posts)} posts")

        # ---------- Comments (including nested replies) ----------
        comments = []
        for i in range(options["comments"]):
            post = random.choice(posts)
            # 20% chance of being a reply to an existing comment
            if comments and random.random() < 0.2:
                parent = random.choice(comments)
            else:
                parent = None

            comment = Comment(
                post=post,
                parent=parent,
                name=fake.name(),
                email=fake.email(),
                website=fake.url() if random.random() < 0.3 else "",
                body=fake.paragraph(),
                is_approved=random.choice([True, False]),
            )
            comment.save()
            comments.append(comment)

            if (i + 1) % 50 == 0:
                self.stdout.write(f"Created {i + 1} comments")

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully created {len(categories)} categories, "
                f"{len(posts)} posts, {len(comments)} comments"
            )
        )
