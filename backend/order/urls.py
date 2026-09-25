from django.urls import path

from .views import OrderDetailView, OrderListCreateView, RefundRequestCreateView

app_name = "order"

urlpatterns = [
    path("", OrderListCreateView.as_view(), name="order-list-create"),
    path("<int:pk>/", OrderDetailView.as_view(), name="order-detail"),
    path(
        "<int:pk>/refund-request/",
        RefundRequestCreateView.as_view(),
        name="order-refund-request",
    ),
]
