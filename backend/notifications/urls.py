from django.urls import path

from .views import (
    MarkAllNotificationsReadView,
    UserNotificationDetailView,
    UserNotificationListView,
)

app_name = "notifications"

urlpatterns = [
    path("", UserNotificationListView.as_view(), name="notification-list"),
    path(
        "mark-all-read/",
        MarkAllNotificationsReadView.as_view(),
        name="notification-mark-all-read",
    ),
    path(
        "<int:pk>/",
        UserNotificationDetailView.as_view(),
        name="notification-detail",
    ),
]
