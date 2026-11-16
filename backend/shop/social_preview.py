"""
EXPLORATORY PROOF OF CONCEPT (Task 15.1.2.3 spike). NOT production code.

Serves a tiny, script-free HTML page with Open Graph tags for ONE product. The frontend's
nginx routes link-preview crawlers (TelegramBot, WhatsApp, facebookexternalhit, ...) to it
instead of the SPA shell, because those crawlers do not run JavaScript and so never see the
tags react-helmet-async injects in the browser. Everyone else (browsers, Googlebot) keeps
getting the normal SPA. See frontend/docs/prerendering-evaluation.md and
frontend/poc/nginx.social-preview.conf.

Known PoC shortcuts a real implementation must fix (details in the evaluation doc, section 8):
  * the title/description/price/image rules are a Python COPY of frontend/src/utils/seo.js
    (buildProductOpenGraph / buildProductMetaDescription); they will drift. Make the backend
    the single source and have the SPA consume it.
  * no caching, no rate limiting, no blog/category pages, no image resizing (WhatsApp drops
    large thumbnails), absolute image URLs come from the request Host header.
"""

import re
from html import escape
from urllib.parse import quote

from django.conf import settings
from django.db.models import Min
from django.http import Http404, HttpResponse

from .models import Product

STORE_NAME = "Chiz"  # copy of frontend/src/constants/store.js
META_DESCRIPTION_MAX = 155
META_DESCRIPTION_MIN_USEFUL = 50
CURRENCY = "IRR"  # raw Rial, ADR 0001 (never Toman)


def _normalize(text):
    text = re.sub(r"<[^>]*>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def truncate_at_word(text, limit=META_DESCRIPTION_MAX):
    """Cut at a WORD boundary (ZWNJ is not whitespace, so Persian words stay whole)."""
    text = _normalize(text)
    if len(text) <= limit:
        return text
    room = limit - 1
    cut = text[:room]
    if not text[room].isspace():
        last_space = max(cut.rfind(" "), -1)
        if last_space > room / 2:
            cut = cut[:last_space]
    return re.sub(r"[\s،,;؛:\-–—.]+$", "", cut) + "…"


def _description(product):
    short = _normalize(product.short_description)
    if len(short) >= META_DESCRIPTION_MIN_USEFUL:
        return truncate_at_word(short)
    brand = _normalize(product.brand.name) if product.brand_id else ""
    category = _normalize(product.category.name) if product.category_id else ""
    sentence = (
        f"خرید آنلاین {_normalize(product.name)}"
        + (f" از برند {brand}" if brand else "")
        + (f" در دسته {category}" if category else "")
        + f" از {STORE_NAME}. مشخصات، قیمت و نظرات کاربران را ببینید و با اطمینان سفارش دهید."
    )
    return truncate_at_word(sentence)


def _lowest_price(product):
    """Lowest REGULAR price in Rial across active variants, else the legacy product price."""
    lowest = product.variants.filter(is_active=True).aggregate(m=Min("price"))["m"]
    return lowest if lowest is not None else product.price


def _image_url(request, product):
    if product.thumbnail:
        return request.build_absolute_uri(product.thumbnail.url)
    first = product.images.first()
    if first and first.image:
        return request.build_absolute_uri(first.image.url)
    return f"{settings.FRONTEND_URL.rstrip('/')}/og-default.jpg"  # branded fallback


def build_product_preview(request, product):
    name = _normalize(product.name)
    brand = _normalize(product.brand.name) if product.brand_id else ""
    price = _lowest_price(product)
    return {
        "title": " | ".join(p for p in (name, brand, STORE_NAME) if p),
        "name": name,
        "description": _description(product),
        "url": f"{settings.FRONTEND_URL.rstrip('/')}/product/{quote(product.slug, safe='-_.~')}",
        "image": _image_url(request, product),
        "price": str(int(price)) if price is not None else None,
    }


def render_preview_html(data):
    e = lambda value: escape(str(value), quote=True)  # noqa: E731
    og = [
        ("og:site_name", STORE_NAME),
        ("og:locale", "fa_IR"),
        ("og:type", "product"),
        ("og:title", data["name"]),
        ("og:description", data["description"]),
        ("og:url", data["url"]),
        ("og:image", data["image"]),
        ("og:image:alt", data["name"]),
    ]
    if data["price"] is not None:
        og += [
            ("product:price:amount", data["price"]),
            ("product:price:currency", CURRENCY),
        ]
    meta = "\n".join(f'<meta property="{p}" content="{e(v)}">' for p, v in og)
    return (
        '<!doctype html>\n<html lang="fa" dir="rtl">\n<head>\n<meta charset="utf-8">\n'
        f'<title>{e(data["title"])}</title>\n'
        f'<meta name="description" content="{e(data["description"])}">\n'
        f'<link rel="canonical" href="{e(data["url"])}">\n'
        f"{meta}\n"
        '<meta name="twitter:card" content="summary_large_image">\n'
        "</head>\n<body>\n"
        f'<h1>{e(data["name"])}</h1>\n<p>{e(data["description"])}</p>\n'
        f'<p><a href="{e(data["url"])}">{e(data["url"])}</a></p>\n'
        "</body>\n</html>\n"
    )


def share_product_preview(request, slug):
    """GET /share/product/<slug>: link-preview HTML for one product (404 if unknown)."""
    try:
        product = Product.objects.select_related("brand", "category").get(slug=slug)
    except Product.DoesNotExist:
        raise Http404("Unknown product") from None
    response = HttpResponse(
        render_preview_html(build_product_preview(request, product)),
        content_type="text/html; charset=utf-8",
    )
    response["Cache-Control"] = "public, max-age=300"
    return response
