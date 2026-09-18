from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("initiate/", views.PaymentInitiateView.as_view(), name="initiate"),
    path(
        "callback/<str:gateway>/", views.PaymentCallbackView.as_view(), name="callback"
    ),
]
