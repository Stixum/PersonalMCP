import hmac
import logging
import os

logger = logging.getLogger(__name__)


class BearerAuthMiddleware:
    """
    ASGI middleware that validates a Bearer token on every HTTP request.

    Token is read from the MCP_BEARER_TOKEN environment variable.
    Uses constant-time comparison (hmac.compare_digest) to prevent timing attacks.
    Returns 401 immediately if the token is missing, wrong scheme, or incorrect.
    Only lifespan passes through unauthenticated; other non-HTTP scopes are refused.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            # Carries no client request; FastMCP needs it to start its task group
            await self.app(scope, receive, send)
            return

        if scope["type"] != "http":
            # Tokens are only checked on HTTP, so anything else must not reach the app
            logger.warning("auth_failure reason=unsupported_scope type=%s", scope["type"])
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
            return

        expected = os.environ.get("MCP_BEARER_TOKEN", "")
        token = self._extract_bearer_token(scope)

        # Short-circuit on empty expected/token: requests without a token are rejected
        # faster than requests with a wrong token (timing side-channel). This is an
        # accepted tradeoff for a personal server — constant-time rejection of all paths
        # would require always calling compare_digest with dummy values.
        if not expected or not token or not hmac.compare_digest(token, expected.encode("utf-8")):
            logger.warning("auth_failure reason=%s", "missing_token" if not token else "invalid_token")
            await self._reject_401(send)
            return

        await self.app(scope, receive, send)

    def _extract_bearer_token(self, scope) -> bytes:
        """Extract the raw token bytes from Authorization: Bearer <token> header."""
        headers = dict(scope.get("headers", []))
        auth = headers.get(b"authorization", b"")
        if auth.startswith(b"Bearer "):
            return auth[len(b"Bearer "):]
        return b""

    async def _reject_401(self, send):
        await send({
            "type": "http.response.start",
            "status": 401,
            "headers": [(b"content-type", b"application/json")],
        })
        await send({
            "type": "http.response.body",
            "body": b'{"error": "Unauthorized"}',
            "more_body": False,
        })
