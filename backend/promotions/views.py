from django.db.models import Count
from django.utils import timezone
from rest_framework import generics
from rest_framework.permissions import AllowAny

from .models import FlashSale
from .serializers import ActiveFlashSaleSerializer


class ActiveFlashSaleListView(generics.ListAPIView):
    """
    GET /api/promotions/active-flash-sales/

    Flash sales running right now (is_active and now within
    [starts_at, ends_at]), soonest-ending first, so clients wanting a single
    banner can take the first. Public and unpaginated: only a handful of
    sales are ever live at once.
    """

    permission_classes = [AllowAny]
    serializer_class = ActiveFlashSaleSerializer
    pagination_class = None

    def get_queryset(self):
        now = timezone.now()
        return (
            FlashSale.objects.filter(
                is_active=True, starts_at__lte=now, ends_at__gte=now
            )
            .annotate(product_count=Count("products"))
            .order_by("ends_at", "pk")
        )
