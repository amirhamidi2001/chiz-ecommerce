from django import template

register = template.Library()


@register.filter
def invoice_attributes(value):
    """
    Render an OrderItem.variant_attributes_json snapshot ({"color": "Rose"})
    as "Color: Rose", skipping empty values.
    """
    if not isinstance(value, dict):
        return ""
    return ", ".join(
        f"{str(key).replace('_', ' ').capitalize()}: {val}"
        for key, val in value.items()
        if val not in (None, "")
    )
