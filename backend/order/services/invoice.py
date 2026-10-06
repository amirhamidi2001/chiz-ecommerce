"""
PDF invoice generation.

An invoice must show exactly what was ordered and charged, so it is rendered
ONLY from the frozen snapshot fields on Order / OrderItem (product_name,
unit_price, variant_attributes_json, shipping_cost, ...) — never from the
live Product / ProductVariant rows, which may have been renamed, repriced or
deleted since.
"""

from django.template.loader import render_to_string

# TODO: make store details configurable via settings/admin. These are clearly
# labelled placeholders until a real business supplies its legal details.
STORE_DETAILS = {
    "name": "Chiz Store (placeholder name)",
    "address": "Placeholder address, Tehran, Iran",
    "email": "support@example.com",
    "phone": "+98 21 0000 0000",
    "tax_id": "Tax ID: PLACEHOLDER",
}


def generate_invoice_pdf(order) -> bytes:
    # Imported lazily: WeasyPrint loads Pango via the OS at import time, so a
    # missing system library should only break invoices, never Django startup
    # (order.views is imported by the URLconf for the whole API).
    import weasyprint

    html_string = render_to_string(
        "order/invoice.html",
        {
            "order": order,
            "items": order.items.all(),
            "store": STORE_DETAILS,
        },
    )
    return weasyprint.HTML(string=html_string).write_pdf()
