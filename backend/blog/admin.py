from django.contrib import admin
from django.utils.html import format_html

from .models import Category, Comment, Post


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ["name"]


class CommentInline(admin.TabularInline):
    model = Comment
    fk_name = "post"
    extra = 0
    readonly_fields = ["name", "email", "website", "body", "created_at", "parent"]
    fields = ["name", "email", "body", "is_approved", "created_at", "parent"]
    can_delete = True
    show_change_link = True


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "category",
        "status",
        "is_featured",
        "views_count",
        "read_time",
        "created_at",
        "cover_preview",
    ]
    list_filter = ["status", "is_featured", "category", "created_at"]
    search_fields = ["title", "excerpt", "content"]
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = [
        "views_count",
        "read_time",
        "created_at",
        "updated_at",
        "cover_preview",
    ]
    date_hierarchy = "created_at"
    ordering = ["-created_at"]
    inlines = [CommentInline]

    fieldsets = (
        (
            "Content",
            {
                "fields": (
                    "title",
                    "slug",
                    "excerpt",
                    "content",
                    "cover_image",
                    "cover_preview",
                )
            },
        ),
        (
            "Publishing",
            {
                "fields": (
                    "category",
                    "status",
                    "is_featured",
                    "published_at",
                )
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "views_count",
                    "read_time",
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def cover_preview(self, obj):
        if obj.cover_image:
            return format_html(
                '<img src="{}" style="max-height:80px;border-radius:4px;" />',
                obj.cover_image.url,
            )
        return "—"

    cover_preview.short_description = "Cover"


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["name", "email", "post", "parent", "is_approved", "created_at"]
    list_filter = ["is_approved", "created_at"]
    search_fields = ["name", "email", "body"]
    readonly_fields = ["created_at"]
    actions = ["approve_comments", "reject_comments"]

    @admin.action(description="Approve selected comments")
    def approve_comments(self, request, queryset):
        queryset.update(is_approved=True)

    @admin.action(description="Reject selected comments")
    def reject_comments(self, request, queryset):
        queryset.update(is_approved=False)
