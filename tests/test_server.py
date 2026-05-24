import os
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
from asgi_lifespan import LifespanManager


@pytest.fixture
def mock_env():
    return {"MCP_BEARER_TOKEN": "test-token", "S3_BUCKET": "test-bucket"}


@pytest.fixture
def mock_s3_body():
    body = MagicMock()
    body.read.return_value = b"# Identity\n\nPlaceholder content."
    return body


def test_create_app_returns_callable():
    """create_app() must return a valid ASGI callable."""
    from server import create_app
    app = create_app()
    assert callable(app)


@pytest.mark.asyncio
async def test_unauthenticated_request_returns_401(mock_env):
    """Requests without Authorization header must be rejected at ASGI layer."""
    with patch.dict(os.environ, mock_env):
        from server import create_app
        app = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/mcp", json={})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_mcp_initialize_responds(mock_env, mock_s3_body):
    """Authenticated MCP initialize request must get a valid JSON-RPC response."""
    with patch.dict(os.environ, mock_env), \
         patch("server.s3_client") as mock_s3:
        mock_s3.get_object.return_value = {"Body": mock_s3_body}
        from server import create_app
        app = create_app()
        # LifespanManager triggers ASGI lifespan startup (initialises FastMCP task group)
        async with LifespanManager(app) as manager:
            async with AsyncClient(
                transport=ASGITransport(app=manager.app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/mcp",
                    headers={
                        "Authorization": "Bearer test-token",
                        "Accept": "application/json, text/event-stream",
                    },
                    json={
                        "jsonrpc": "2.0",
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {},
                            "clientInfo": {"name": "test", "version": "0.0.1"},
                        },
                        "id": 1,
                    },
                )
    assert response.status_code == 200
    # The MCP streamable-HTTP transport returns SSE; extract the JSON from the data line.
    import json as _json
    sse_text = response.text
    data_line = next(line for line in sse_text.splitlines() if line.startswith("data:"))
    body = _json.loads(data_line[len("data:"):].strip())
    assert body.get("jsonrpc") == "2.0"
    assert "result" in body


def test_update_context_writes_to_s3(mock_env):
    """update_context tool must write content to the correct S3 key."""
    with patch.dict(os.environ, mock_env), \
         patch("server.s3_client") as mock_s3:
        from server import update_context
        result = update_context("identity", "# New content")
        mock_s3.put_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="identity.md",
            Body=b"# New content",
        )
        assert "identity" in result


def test_update_context_rejects_unknown_name(mock_env):
    """update_context tool must raise ValueError for unknown file names."""
    with patch.dict(os.environ, mock_env):
        from server import update_context
        with pytest.raises(ValueError, match="Unknown context file"):
            update_context("nonexistent", "content")


def test_update_context_rejects_empty_content(mock_env):
    """update_context must reject empty or whitespace-only content to prevent accidental wipes."""
    with patch.dict(os.environ, mock_env):
        from server import update_context
        with pytest.raises(ValueError, match="non-empty"):
            update_context("identity", "   \n  ")


def test_append_to_context_concatenates_and_writes(mock_env):
    """append_to_context fetches existing content, appends, and writes back."""
    body = MagicMock()
    body.read.return_value = b"# Identity\n\nExisting content."
    with patch.dict(os.environ, mock_env), \
         patch("server.s3_client") as mock_s3:
        mock_s3.get_object.return_value = {"Body": body}
        from server import append_to_context
        result = append_to_context("identity", "New paragraph.")
        mock_s3.get_object.assert_called_once_with(Bucket="test-bucket", Key="identity.md")
        put_kwargs = mock_s3.put_object.call_args.kwargs
        assert put_kwargs["Bucket"] == "test-bucket"
        assert put_kwargs["Key"] == "identity.md"
        assert put_kwargs["Body"] == b"# Identity\n\nExisting content.\n\nNew paragraph."
        assert "Appended" in result


def test_append_to_context_rejects_unknown_name(mock_env):
    with patch.dict(os.environ, mock_env):
        from server import append_to_context
        with pytest.raises(ValueError, match="Unknown context file"):
            append_to_context("nonexistent", "content")


def test_append_to_context_rejects_empty_content(mock_env):
    with patch.dict(os.environ, mock_env):
        from server import append_to_context
        with pytest.raises(ValueError, match="non-empty"):
            append_to_context("identity", "")


def test_get_personal_context_single_section(mock_env, mock_s3_body):
    """get_personal_context with a section name reads only that S3 key."""
    with patch.dict(os.environ, mock_env), \
         patch("server.s3_client") as mock_s3:
        mock_s3.get_object.return_value = {"Body": mock_s3_body}
        from server import get_personal_context
        result = get_personal_context("identity")
        mock_s3.get_object.assert_called_once_with(Bucket="test-bucket", Key="identity.md")
        assert "Identity" in result


def test_portfolio_files_list_is_complete():
    """PORTFOLIO_FILES must contain all 10 expected file names."""
    from server import PORTFOLIO_FILES
    expected = {
        "identity",
        "role-and-responsibilities",
        "goals-and-priorities",
        "domain-knowledge",
        "communication-style",
        "preferences-and-constraints",
        "operational-rules",
        "ai-assistant-instructions",
        "tools-and-systems",
        "current-projects",
    }
    assert set(PORTFOLIO_FILES) == expected
