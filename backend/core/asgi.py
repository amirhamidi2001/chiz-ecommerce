"""
ASGI config for core project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

# CRITICAL: set the settings module BEFORE any Django/Channels imports
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

from django.core.asgi import get_asgi_application

# Initialize Django apps before importing local modules
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from chat.middleware import JWTAuthMiddleware  # noqa: E402
from chat.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        # Standard Django HTTP stack (DRF, etc.)
        "http": django_asgi_app,
        # WebSocket — authenticated via JWT query parameter
        "websocket": JWTAuthMiddleware(URLRouter(websocket_urlpatterns)),
    }
)
