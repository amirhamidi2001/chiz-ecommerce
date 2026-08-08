from django.contrib import admin

from .models import ChatMessage, ChatRoom


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ["sender", "content", "message_type", "is_read", "created_at"]
    can_delete = False
    show_change_link = False


@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "customer",
        "agent",
        "status",
        "subject",
        "created_at",
        "updated_at",
    ]
    list_filter = ["status"]
    search_fields = ["customer__email", "agent__email", "subject"]
    readonly_fields = ["id", "created_at", "updated_at"]
    raw_id_fields = ["customer", "agent"]
    inlines = [ChatMessageInline]


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ["id", "room", "sender", "message_type", "is_read", "created_at"]
    list_filter = ["message_type", "is_read"]
    search_fields = ["content", "sender__email"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["sender", "room"]
