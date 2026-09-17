from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("initiate/", views.PaymentInitiateView.as_view(), name="initiate"),
]
