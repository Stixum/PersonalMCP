import hmac
import os


class BearerAuthMiddleware:
    """
    ASGI middleware that validates a Bearer token on every HTTP request.

    Token is read from the MCP_BEARER_TOKEN environment variable.
    Uses constant-time comparison (hmac.compare_digest) to prevent timing attacks.
    Returns 401 immediately if the token is missing, wrong scheme, or incorrect.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            # Pass through lifespan, websocket, and other non-HTTP events
            await self.app(scope, receive, send)
            return

        expected = os.environ.get("MCP_BEARER_TOKEN", "")
        token = self._extract_bearer_token(scope)

        # Short-circuit on empty expected/token: requests without a token are rejected
        # faster than requests with a wrong token (timing side-channel). This is an
        # accepted tradeoff for a personal server — constant-time rejection of all paths
        # would require always calling compare_digest with dummy values.
        if not expected or not token or not hmac.compare_digest(token, expected):
            await self._reject_401(send)
            return

        await self.app(scope, receive, send)

    def _extract_bearer_token(self, scope) -> str:
        """Extract the token value from Authorization: Bearer <token> header."""
        headers = dict(scope.get("headers", []))
        auth = headers.get(b"authorization", b"").decode("utf-8")
        if auth.startswith("Bearer "):
            return auth[len("Bearer "):]
        return ""

    async def _reject_401(self, send):
        await send({
            "type": "http.response.start",
            "status": 401,
            "headers": [(b"content-type", b"application/json")],
        })
        await send({
            "type": "http.response.body",
            "body": b'{"error": "Unauthorized"}',
        })
