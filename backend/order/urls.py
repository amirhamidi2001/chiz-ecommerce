from django.urls import path

from .views import (
    OrderDetailView,
    OrderInvoiceView,
    OrderListCreateView,
    RefundRequestCreateView,
)

app_name = "order"

urlpatterns = [
    path("", OrderListCreateView.as_view(), name="order-list-create"),
    path("<int:pk>/", OrderDetailView.as_view(), name="order-detail"),
    path("<int:pk>/invoice/", OrderInvoiceView.as_view(), name="order-invoice"),
    path(
        "<int:pk>/refund-request/",
        RefundRequestCreateView.as_view(),
        name="order-refund-request",
    ),
]
