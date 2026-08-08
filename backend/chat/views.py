from django.http import Http404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ChatMessage, ChatRoom
from .serializers import (
    ChatMessageSerializer,
    ChatRoomSerializer,
    CreateChatRoomSerializer,
)

# ─── Permissions ─────────────────────────────────────────────────────────────


class IsAdminOrAgent(permissions.BasePermission):
    """Grant access to staff users and users with type 2 or 3."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_staff or getattr(request.user, "type", 1) in (2, 3))
        )


# ─── Customer endpoints ───────────────────────────────────────────────────────


class MyChatRoomView(APIView):
    """
    GET  /api/chat/room/
         Return the customer's active (open/assigned) room, or 404.

    POST /api/chat/room/
         Open a new room. Body: { "subject": "…" } (optional).
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        room = (
            ChatRoom.objects.filter(
                customer=request.user,
                status__in=[ChatRoom.Status.OPEN, ChatRoom.Status.ASSIGNED],
            )
            .order_by("-created_at")
            .first()
        )
        if not room:
            return Response(
                {"detail": "No active chat room."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(ChatRoomSerializer(room, context={"request": request}).data)

    def post(self, request):
        serializer = CreateChatRoomSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        room = serializer.save(customer=request.user, status=ChatRoom.Status.OPEN)
        return Response(
            ChatRoomSerializer(room, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class RoomMessagesView(generics.ListAPIView):
    """
    GET /api/chat/room/<room_id>/messages/
    Return paginated message history. Marks unread messages as read.
    Customers can only access their own rooms.
    """

    serializer_class = ChatMessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        room_id = self.kwargs["room_id"]
        user = self.request.user
        is_staff = user.is_staff or getattr(user, "type", 1) in (2, 3)

        # Check room existence and ownership for non‑staff users
        try:
            room = ChatRoom.objects.get(id=room_id)
        except ChatRoom.DoesNotExist:
            raise Http404("No ChatRoom matches the given query.")

        if not is_staff and room.customer != user:
            raise Http404("No ChatRoom matches the given query.")

        qs = ChatMessage.objects.filter(room=room)

        # Mark the other party's messages as read
        qs.filter(is_read=False).exclude(sender=user).update(is_read=True)
        return qs.select_related("sender").order_by("created_at")


# ─── Admin / Agent endpoints ──────────────────────────────────────────────────


class AdminChatRoomListView(generics.ListAPIView):
    """
    GET /api/chat/admin/rooms/?status=open
    List all chat rooms (optionally filtered by status).
    """

    serializer_class = ChatRoomSerializer
    permission_classes = [IsAdminOrAgent]

    def get_queryset(self):
        qs = ChatRoom.objects.select_related("customer", "agent").prefetch_related(
            "messages"
        )
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx


class AdminChatRoomDetailView(generics.RetrieveUpdateAPIView):
    """
    GET   /api/chat/admin/rooms/<id>/  — Retrieve a room with full details.
    PATCH /api/chat/admin/rooms/<id>/  — Update status or assign agent.
    """

    serializer_class = ChatRoomSerializer
    permission_classes = [IsAdminOrAgent]
    queryset = ChatRoom.objects.select_related("customer", "agent")
    lookup_field = "id"

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx
