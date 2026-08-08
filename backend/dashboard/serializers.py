from accounts.models import Profile
from blog.models import Comment, Post
from contact.models import ContactMessage
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db.models import Sum
from order.models import Order, OrderItem
from rest_framework import serializers
from shop.models import Brand, Category, Product, Review

from .models import Address, Wishlist

User = get_user_model()


# ═══════════════════════════════════════════════════════════════════════════════
# USER DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════


class ProfileSerializer(serializers.ModelSerializer):
    """Read-only full profile view."""

    email = serializers.EmailField(source="user.email", read_only=True)
    is_verified = serializers.BooleanField(source="user.is_verified", read_only=True)
    user_type = serializers.IntegerField(source="user.type", read_only=True)
    member_since = serializers.DateTimeField(source="user.created_date", read_only=True)
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "avatar_url",
            "order_updates",
            "promotions",
            "newsletter",
            "is_verified",
            "user_type",
            "member_since",
        ]
        read_only_fields = fields

    def get_avatar_url(self, obj):
        request = self.context.get("request")
        if obj.image and hasattr(obj.image, "url"):
            return (
                request.build_absolute_uri(obj.image.url) if request else obj.image.url
            )
        return None


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Writable profile fields."""

    class Meta:
        model = Profile
        fields = ["first_name", "last_name", "phone_number"]

    def validate_first_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("First name cannot be blank.")
        return value.strip()

    def validate_last_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Last name cannot be blank.")
        return value.strip()


class AvatarUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ["image"]

    def validate_image(self, value):
        max_mb = 5
        if value.size > max_mb * 1024 * 1024:
            raise serializers.ValidationError(f"Image must be under {max_mb} MB.")
        allowed = ["image/jpeg", "image/png", "image/webp"]
        if hasattr(value, "content_type") and value.content_type not in allowed:
            raise serializers.ValidationError("Only JPEG, PNG and WebP are allowed.")
        return value


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(write_only=True, required=True)
    confirm_password = serializers.CharField(write_only=True, required=True)

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )
        validate_password(attrs["new_password"], self.context["request"].user)
        return attrs

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user


class NotificationSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ["order_updates", "promotions", "newsletter"]


# ─── Addresses ───────────────────────────────────────────────────────────────


class AddressSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Address
        fields = [
            "id",
            "label",
            "first_name",
            "last_name",
            "full_name",
            "phone",
            "address_line",
            "apartment",
            "city",
            "state",
            "zip_code",
            "country",
            "is_default",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "full_name"]

    def get_full_name(self, obj):
        return obj.full_name


# ─── Wishlist ─────────────────────────────────────────────────────────────────


class WishlistProductSerializer(serializers.ModelSerializer):
    thumbnail_url = serializers.SerializerMethodField()
    discount_percent = serializers.IntegerField(read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "price",
            "original_price",
            "thumbnail_url",
            "rating",
            "reviews_count",
            "is_sale",
            "is_new",
            "stock",
            "discount_percent",
            "category_name",
        ]

    def get_thumbnail_url(self, obj):
        request = self.context.get("request")
        if obj.thumbnail and hasattr(obj.thumbnail, "url"):
            return (
                request.build_absolute_uri(obj.thumbnail.url)
                if request
                else obj.thumbnail.url
            )
        return None


class WishlistSerializer(serializers.ModelSerializer):
    product = WishlistProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), write_only=True, source="product"
    )

    class Meta:
        model = Wishlist
        fields = ["id", "product", "product_id", "added_at"]
        read_only_fields = ["id", "added_at"]

    def validate(self, attrs):
        user = self.context["request"].user
        if Wishlist.objects.filter(user=user, product=attrs["product"]).exists():
            raise serializers.ValidationError(
                {"product_id": "Product is already in your wishlist."}
            )
        return attrs

    # def create(self, validated_data):
    #     return Wishlist.objects.create(
    #         user=self.context["request"].user, **validated_data
    #     )


# ─── Orders ──────────────────────────────────────────────────────────────────


class OrderItemSerializer(serializers.ModelSerializer):
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product",
            "product_name",
            "product_slug",
            "product_image",
            "unit_price",
            "quantity",
            "subtotal",
        ]


class UserOrderListSerializer(serializers.ModelSerializer):
    items_count = serializers.SerializerMethodField()
    preview_images = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "status",
            "total",
            "created_at",
            "items_count",
            "preview_images",
            "payment_method",
            "card_last_four",
        ]

    def get_items_count(self, obj):
        return obj.items.count()

    def get_preview_images(self, obj):
        return list(obj.items.values_list("product_image", flat=True)[:3])


class UserOrderDetailSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "status",
            "created_at",
            "updated_at",
            "first_name",
            "last_name",
            "email",
            "phone",
            "shipping_address",
            "shipping_apartment",
            "shipping_city",
            "shipping_state",
            "shipping_zip",
            "shipping_country",
            "billing_same_as_shipping",
            "payment_method",
            "card_last_four",
            "subtotal",
            "shipping_cost",
            "tax",
            "discount",
            "total",
            "notes",
            "items",
        ]


# ─── Reviews ─────────────────────────────────────────────────────────────────


class UserReviewSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_slug = serializers.CharField(source="product.slug", read_only=True)
    product_thumbnail = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = [
            "id",
            "product",
            "product_name",
            "product_slug",
            "product_thumbnail",
            "rating",
            "headline",
            "comment",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "product",
            "product_name",
            "product_slug",
            "product_thumbnail",
        ]

    def get_product_thumbnail(self, obj):
        request = self.context.get("request")
        try:
            if obj.product and obj.product.thumbnail:
                return (
                    request.build_absolute_uri(obj.product.thumbnail.url)
                    if request
                    else obj.product.thumbnail.url
                )
        except Exception:
            pass
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

# ─── Admin: Users ─────────────────────────────────────────────────────────────


class AdminUserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    total_orders = serializers.SerializerMethodField()
    total_spent = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "full_name",
            "phone",
            "avatar_url",
            "type",
            "is_active",
            "is_verified",
            "is_staff",
            "created_date",
            "total_orders",
            "total_spent",
        ]
        read_only_fields = [
            "id",
            "email",
            "created_date",
            "full_name",
            "phone",
            "avatar_url",
            "total_orders",
            "total_spent",
        ]

    def get_full_name(self, obj):
        try:
            return obj.profile.get_fullname()
        except Exception:
            return ""

    def get_phone(self, obj):
        try:
            return obj.profile.phone_number or ""
        except Exception:
            return ""

    def get_avatar_url(self, obj):
        request = self.context.get("request")
        try:
            if obj.profile.image:
                return (
                    request.build_absolute_uri(obj.profile.image.url)
                    if request
                    else obj.profile.image.url
                )
        except Exception:
            pass
        return None

    def get_total_orders(self, obj):
        return obj.orders.count()

    def get_total_spent(self, obj):
        result = obj.orders.filter(
            status__in=["processing", "shipped", "delivered"]
        ).aggregate(t=Sum("total"))["t"]
        return float(result or 0)


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["is_active", "is_staff", "type"]


# ─── Admin: Products ──────────────────────────────────────────────────────────


class AdminProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    brand_name = serializers.CharField(source="brand.name", read_only=True)
    thumbnail_url = serializers.SerializerMethodField()
    total_sold = serializers.SerializerMethodField()
    discount_percent = serializers.IntegerField(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "category",
            "category_name",
            "brand",
            "brand_name",
            "price",
            "original_price",
            "stock",
            "rating",
            "reviews_count",
            "is_new",
            "is_sale",
            "thumbnail",
            "thumbnail_url",
            "short_description",
            "description",
            "created_at",
            "total_sold",
            "discount_percent",
        ]
        read_only_fields = [
            "id",
            "slug",
            "created_at",
            "thumbnail_url",
            "total_sold",
            "discount_percent",
        ]

    def get_thumbnail_url(self, obj):
        request = self.context.get("request")
        if obj.thumbnail and hasattr(obj.thumbnail, "url"):
            return (
                request.build_absolute_uri(obj.thumbnail.url)
                if request
                else obj.thumbnail.url
            )
        return None

    def get_total_sold(self, obj):
        result = obj.order_items.aggregate(t=Sum("quantity"))["t"]
        return result or 0


# ─── Admin: Categories ────────────────────────────────────────────────────────


class AdminCategorySerializer(serializers.ModelSerializer):
    product_count = serializers.SerializerMethodField()
    parent_name = serializers.CharField(source="parent.name", read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "slug",
            "parent",
            "parent_name",
            "image",
            "image_url",
            "created_at",
            "product_count",
        ]
        read_only_fields = ["id", "slug", "created_at", "parent_name", "image_url"]

    def get_product_count(self, obj):
        return obj.products.count()

    def get_image_url(self, obj):
        request = self.context.get("request")
        if obj.image and hasattr(obj.image, "url"):
            return (
                request.build_absolute_uri(obj.image.url) if request else obj.image.url
            )
        return None


# ─── Admin: Brands ───────────────────────────────────────────────────────────


class AdminBrandSerializer(serializers.ModelSerializer):
    product_count = serializers.SerializerMethodField()
    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = Brand
        fields = ["id", "name", "slug", "logo", "logo_url", "product_count"]
        read_only_fields = ["id", "slug", "logo_url"]

    def get_product_count(self, obj):
        return obj.products.count()

    def get_logo_url(self, obj):
        request = self.context.get("request")
        if obj.logo and hasattr(obj.logo, "url"):
            return request.build_absolute_uri(obj.logo.url) if request else obj.logo.url
        return None


# ─── Admin: Orders ───────────────────────────────────────────────────────────


class AdminOrderListSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    items_count = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "full_name",
            "email",
            "phone",
            "status",
            "payment_method",
            "total",
            "items_count",
            "created_at",
        ]

    def get_items_count(self, obj):
        return obj.items.count()


class AdminOrderDetailSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = Order
        fields = "__all__"


class AdminOrderStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ["status"]

    def validate_status(self, value):
        valid = [choice[0] for choice in Order.Status.choices]
        if value not in valid:
            raise serializers.ValidationError(
                f"'{value}' is not a valid status. Choose from: {valid}"
            )
        return value


# ─── Admin: Reviews ──────────────────────────────────────────────────────────


class AdminReviewSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_id = serializers.IntegerField(source="product.id", read_only=True)

    class Meta:
        model = Review
        fields = [
            "id",
            "product",
            "product_id",
            "product_name",
            "name",
            "rating",
            "headline",
            "comment",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "product_name", "product_id"]


# ─── Admin: Contact Messages ─────────────────────────────────────────────────


class AdminContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = ["id", "name", "email", "subject", "message", "created_at"]
        read_only_fields = ["id", "created_at"]


# ─── Admin: Blog Categories ────────────────────────────────────────────────────


class BlogCategorySerializer(serializers.ModelSerializer):
    posts_count = serializers.SerializerMethodField()

    class Meta:
        from blog.models import Category as BlogCategory

        model = BlogCategory
        fields = [
            "id",
            "name",
            "slug",
            "posts_count",
        ]
        read_only_fields = ["id", "slug"]

    def get_posts_count(self, obj):
        return obj.posts.count()


# ─── Admin: Blog Posts ────────────────────────────────────────────────────────


class AdminPostSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    author_name = serializers.SerializerMethodField()
    author_email = serializers.SerializerMethodField()
    cover_image_url = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id",
            "title",
            "slug",
            "excerpt",
            "content",
            "cover_image",
            "cover_image_url",
            "author",
            "author_name",
            "author_email",
            "category",
            "category_name",
            "status",
            "is_featured",
            "views_count",
            "read_time",
            "created_at",
            "updated_at",
            "published_at",
            "comments_count",
        ]
        read_only_fields = [
            "id",
            "slug",
            "views_count",
            "read_time",
            "created_at",
            "updated_at",
            "author_name",
            "author_email",
            "category_name",
            "cover_image_url",
            "comments_count",
        ]

    def get_author_name(self, obj):
        if obj.author:
            try:
                return obj.author.profile.get_fullname() or obj.author.email
            except Exception:
                return obj.author.email
        return None

    def get_author_email(self, obj):
        return obj.author.email if obj.author else None

    def get_cover_image_url(self, obj):
        request = self.context.get("request")
        if obj.cover_image and hasattr(obj.cover_image, "url"):
            return (
                request.build_absolute_uri(obj.cover_image.url)
                if request
                else obj.cover_image.url
            )
        return None

    def get_comments_count(self, obj):
        return obj.comments.count()


# ─── Admin: Blog Comments ─────────────────────────────────────────────────────


class AdminCommentSerializer(serializers.ModelSerializer):
    post_title = serializers.CharField(source="post.title", read_only=True)
    reply_count = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id",
            "post",
            "post_title",
            "parent",
            "name",
            "email",
            "website",
            "body",
            "is_approved",
            "created_at",
            "reply_count",
        ]
        read_only_fields = ["id", "created_at", "post_title", "reply_count"]

    def get_reply_count(self, obj):
        return obj.replies.count()
