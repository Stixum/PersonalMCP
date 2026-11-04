import os
import pytest
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport


async def _dummy_app(scope, receive, send):
    """Minimal ASGI app that always returns 200 OK."""
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


@pytest.fixture
def protected_app():
    from auth import BearerAuthMiddleware
    return BearerAuthMiddleware(_dummy_app)


@pytest.mark.asyncio
async def test_missing_auth_header_returns_401(protected_app):
    with patch.dict(os.environ, {"MCP_BEARER_TOKEN": "test-secret-token"}):
        async with AsyncClient(
            transport=ASGITransport(app=protected_app), base_url="http://test"
        ) as client:
            response = await client.get("/")
    assert response.status_code == 401
    assert response.json() == {"error": "Unauthorized"}


@pytest.mark.asyncio
async def test_wrong_token_returns_401(protected_app):
    with patch.dict(os.environ, {"MCP_BEARER_TOKEN": "correct-token"}):
        async with AsyncClient(
            transport=ASGITransport(app=protected_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/", headers={"Authorization": "Bearer wrong-token"}
            )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_correct_token_passes_through(protected_app):
    with patch.dict(os.environ, {"MCP_BEARER_TOKEN": "correct-token"}):
        async with AsyncClient(
            transport=ASGITransport(app=protected_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/", headers={"Authorization": "Bearer correct-token"}
            )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_non_bearer_scheme_returns_401(protected_app):
    with patch.dict(os.environ, {"MCP_BEARER_TOKEN": "correct-token"}):
        async with AsyncClient(
            transport=ASGITransport(app=protected_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/", headers={"Authorization": "Basic correct-token"}
            )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_empty_env_token_always_rejects(protected_app):
    """Server with no token configured should reject everything."""
    with patch.dict(os.environ, {"MCP_BEARER_TOKEN": ""}):
        async with AsyncClient(
            transport=ASGITransport(app=protected_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/", headers={"Authorization": "Bearer anything"}
            )
    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "raw_header",
    [
        pytest.param("Bearer é".encode("utf-8"), id="non-ascii-utf8"),
        pytest.param(b"Bearer \xe9", id="non-utf8-byte"),
    ],
)
async def test_non_ascii_token_returns_401_and_logs_failure(protected_app, raw_header, caplog):
    """Bytes that aren't ASCII/UTF-8 must reach the normal rejection path, not raise."""
    with patch.dict(os.environ, {"MCP_BEARER_TOKEN": "correct-token"}):
        async with AsyncClient(
            transport=ASGITransport(app=protected_app), base_url="http://test"
        ) as client:
            with caplog.at_level("WARNING", logger="auth"):
                response = await client.get("/", headers={"Authorization": raw_header})
    assert response.status_code == 401
    assert response.json() == {"error": "Unauthorized"}
    assert "auth_failure reason=invalid_token" in caplog.text


@pytest.mark.asyncio
async def test_non_ascii_configured_token_accepts_exact_match(protected_app):
    """Comparison is on UTF-8 bytes, so a non-ASCII configured token still works."""
    with patch.dict(os.environ, {"MCP_BEARER_TOKEN": "tökén"}):
        async with AsyncClient(
            transport=ASGITransport(app=protected_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/", headers={"Authorization": "Bearer tökén".encode("utf-8")}
            )
    assert response.status_code == 200
