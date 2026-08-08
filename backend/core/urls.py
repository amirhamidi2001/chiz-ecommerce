"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from blog.sitemaps import BlogSitemap
from decouple import config
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from shop.sitemaps import CategorySitemap, ProductSitemap

sitemaps = {
    "blog": BlogSitemap,
    "products": ProductSitemap,
    "categories": CategorySitemap,
}

ADMIN_URL = config("ADMIN_URL", default="admin/")

urlpatterns = [
    # Admin
    path(ADMIN_URL, admin.site.urls),
    # Apps
    path("api/auth/", include("accounts.urls")),
    path("api/contact/", include("contact.urls")),
    path("api/", include("shop.urls")),
    path("api/cart/", include("cart.urls")),
    path("api/orders/", include("order.urls")),
    path("api/dashboard/", include("dashboard.urls", namespace="dashboard")),
    path("api/chat/", include("chat.urls", namespace="chat")),
    path("api/blog/", include("blog.urls", namespace="blog")),
    # OpenAPI / Docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/schema/swagger/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/schema/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
