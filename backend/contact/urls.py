from django.urls import path

from .views import ContactCreateAPIView

app_name = "contact"

urlpatterns = [
    path("", ContactCreateAPIView.as_view(), name="create"),
]
