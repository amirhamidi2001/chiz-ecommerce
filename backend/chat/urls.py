from django.urls import path

from . import views

app_name = "chat"

urlpatterns = [
    # ── Customer ─────────────────────────────────────────────────────────
    path("room/", views.MyChatRoomView.as_view(), name="my-room"),
    path(
        "room/<uuid:room_id>/messages/",
        views.RoomMessagesView.as_view(),
        name="room-messages",
    ),
    # ── Admin / Agent ─────────────────────────────────────────────────────
    path("admin/rooms/", views.AdminChatRoomListView.as_view(), name="admin-rooms"),
    path(
        "admin/rooms/<uuid:id>/",
        views.AdminChatRoomDetailView.as_view(),
        name="admin-room-detail",
    ),
]
