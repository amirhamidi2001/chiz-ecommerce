import logging
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken

logger = logging.getLogger(__name__)
User = get_user_model()


@database_sync_to_async
def _resolve_user(token_str: str):
    """Validate the JWT and return the matching User, or AnonymousUser."""
    try:
        token = AccessToken(token_str)
        return User.objects.get(pk=token["user_id"])
    except (InvalidToken, TokenError, User.DoesNotExist, KeyError) as exc:
        logger.debug("WebSocket JWT auth failed: %s", exc)
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """
    ASGI middleware that authenticates WebSocket connections via JWT.

    Usage (asgi.py):
        JWTAuthMiddleware(URLRouter(websocket_urlpatterns))

    The frontend must pass the access token as a query parameter:
        new WebSocket(`ws://…/ws/chat/<room_id>/?token=${accessToken}`)
    """

    async def __call__(self, scope, receive, send):
        qs = scope.get("query_string", b"").decode()
        params = parse_qs(qs)
        tokens = params.get("token", [])
        scope["user"] = await _resolve_user(tokens[0]) if tokens else AnonymousUser()
        return await super().__call__(scope, receive, send)
