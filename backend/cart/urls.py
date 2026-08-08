from django.urls import path

from .views import CartClearView, CartItemView, CartView

app_name = "cart"

urlpatterns = [
    path("", CartView.as_view(), name="cart"),
    path("item/<int:item_id>/", CartItemView.as_view(), name="cart-item"),
    path("clear/", CartClearView.as_view(), name="cart-clear"),
]
