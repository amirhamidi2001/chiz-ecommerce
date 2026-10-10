from django.urls import path

from .views import ActiveFlashSaleListView

app_name = "promotions"

urlpatterns = [
    path(
        "active-flash-sales/",
        ActiveFlashSaleListView.as_view(),
        name="active-flash-sales",
    ),
]
