"""DRF counterpart of core.fields.RialField."""

from rest_framework import serializers

from .money import MAX_RIAL_AMOUNT, validate_whole_toman


class RialSerializerField(serializers.IntegerField):
    """A whole-Toman Rial amount on the wire: a JSON integer, never a string."""

    def __init__(self, **kwargs):
        kwargs.setdefault("min_value", 0)
        kwargs.setdefault("max_value", MAX_RIAL_AMOUNT)
        super().__init__(**kwargs)
        self.validators.append(validate_whole_toman)
