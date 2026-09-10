"""
shop/signals.py
────────────────
Signal receivers for the shop app. Wired via ShopConfig.ready()
(shop/apps.py) so they're registered when Django starts.
"""

from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Category
from .views import CATEGORY_TREE_CACHE_KEY


@receiver([post_save, post_delete], sender=Category)
def invalidate_category_tree_cache(sender, **kwargs):
    """
    Invalidate the cached category tree on any Category create, update,
    or delete. Fires on every save regardless of which field changed —
    Category writes are infrequent enough that this coarser approach
    costs essentially nothing and avoids the complexity of precise
    field-change detection.
    """
    cache.delete(CATEGORY_TREE_CACHE_KEY)
