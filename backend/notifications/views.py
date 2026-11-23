from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import UserNotification
from .serializers import UserNotificationSerializer


class UserNotificationListView(generics.ListAPIView):
    """
    GET /api/notifications/ → the authenticated user's in-app notifications,
    most recent first, paginated with the project's StandardResultsPagination
    (the global DRF default).
    """

    permission_classes = [IsAuthenticated]
    serializer_class = UserNotificationSerializer
    # The global OrderingFilter/SearchFilter would let ?ordering= override
    # "most recent first"; this inbox has one fixed order.
    filter_backends = []

    def get_queryset(self):
        return UserNotification.objects.filter(user=self.request.user).order_by(
            "-created_at", "-id"
        )


class UserNotificationDetailView(generics.UpdateAPIView):
    """
    PATCH /api/notifications/<id>/ → mark one notification read.

    The queryset is scoped to request.user, so another user's notification id
    is a plain 404 — indistinguishable from a nonexistent id, which avoids
    leaking that the row exists. PUT is not offered.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = UserNotificationSerializer
    http_method_names = ["patch", "options"]

    def get_queryset(self):
        return UserNotification.objects.filter(user=self.request.user)


class MarkAllNotificationsReadView(APIView):
    """POST /api/notifications/mark-all-read/ → mark every unread one read."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        updated = UserNotification.objects.filter(
            user=request.user, is_read=False
        ).update(is_read=True)
        return Response({"updated": updated}, status=status.HTTP_200_OK)
