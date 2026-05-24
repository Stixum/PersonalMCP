"""
Personal MCP Server — Lambda handler

Serves 10 personal context portfolio files from S3 as MCP tools.
Auth is handled by BearerAuthMiddleware (custom ASGI, constant-time compare).
Transport: Streamable HTTP via Mangum (BUFFERED Lambda Function URL).

Environment variables required:
  MCP_BEARER_TOKEN  - bearer token for all MCP clients
  S3_BUCKET         - S3 bucket name containing the 10 .md files
"""

import os
from concurrent.futures import ThreadPoolExecutor
import boto3
from botocore.exceptions import ClientError
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from auth import BearerAuthMiddleware

PORTFOLIO_FILES = [
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
]

# DNS-rebinding protection is unnecessary for a Lambda deployment (no direct
# localhost exposure); disabling avoids 421 responses on non-localhost hosts.
mcp = FastMCP("personal-context", stateless_http=True, transport_security=TransportSecuritySettings(
    enable_dns_rebinding_protection=False,
))
s3_client = boto3.client("s3")

# Process-level cache: persists across warm Lambda invocations.
# {key: (etag, decoded_content)}. ETag-conditional GETs let S3 short-circuit
# unchanged files with a 304 (~5ms vs ~30ms for a full body fetch).
_cache: dict[str, tuple[str, str]] = {}


def _fetch(key: str) -> str:
    """Fetch an S3 object, using a cached copy when the ETag matches."""
    bucket = os.environ["S3_BUCKET"]
    cached = _cache.get(key)
    kwargs = {"Bucket": bucket, "Key": key}
    if cached:
        kwargs["IfNoneMatch"] = cached[0]
    try:
        response = s3_client.get_object(**kwargs)
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "304":
            return cached[1]
        raise
    content = response["Body"].read().decode("utf-8")
    etag = response.get("ETag", "")
    if etag:
        _cache[key] = (etag, content)
    return content


@mcp.tool()
def get_personal_context(section: str = "") -> str:
    """
    Read personal context about the operator from the portfolio.

    If section is empty or omitted, returns all sections concatenated.
    If section is specified, returns just that section.

    Available sections: identity, role-and-responsibilities, goals-and-priorities,
    domain-knowledge, communication-style, preferences-and-constraints,
    operational-rules, ai-assistant-instructions, tools-and-systems,
    current-projects
    """
    if section and section in PORTFOLIO_FILES:
        return _fetch(f"{section}.md")

    keys = [f"{name}.md" for name in PORTFOLIO_FILES]
    with ThreadPoolExecutor(max_workers=len(keys)) as pool:
        contents = list(pool.map(_fetch, keys))
    return "\n\n---\n\n".join(
        f"## {name}\n\n{content}" for name, content in zip(PORTFOLIO_FILES, contents)
    )


@mcp.tool()
def update_context(name: str, content: str) -> str:
    """
    Write a portfolio context file to S3 (replaces entire file).

    Args:
        name: Section name without .md extension. Must be one of:
            identity, role-and-responsibilities, goals-and-priorities,
            domain-knowledge, communication-style, preferences-and-constraints,
            operational-rules, ai-assistant-instructions, tools-and-systems,
            current-projects
        content: Full markdown content to write (replaces the file).
    """
    if name not in PORTFOLIO_FILES:
        raise ValueError(
            f"Unknown context file: {name!r}. Valid names: {', '.join(PORTFOLIO_FILES)}"
        )
    if not content.strip():
        raise ValueError("content must be non-empty")
    bucket = os.environ["S3_BUCKET"]
    s3_client.put_object(Bucket=bucket, Key=f"{name}.md", Body=content.encode("utf-8"))
    _cache.pop(f"{name}.md", None)
    return f"Updated {name}.md"


@mcp.tool()
def append_to_context(name: str, content: str, separator: str = "\n\n") -> str:
    """
    Append content to an existing portfolio context file in S3.

    Use this for incremental additions (new entries, sub-sections) so the caller
    does not need to read, regenerate, and rewrite the whole file. The current
    file is fetched, the new content is concatenated with the separator, and the
    result is written back.

    Args:
        name: Section name without .md extension (see update_context for the list).
        content: Markdown content to append.
        separator: String inserted between existing content and the appended
            content. Defaults to a blank line ("\\n\\n").
    """
    if name not in PORTFOLIO_FILES:
        raise ValueError(
            f"Unknown context file: {name!r}. Valid names: {', '.join(PORTFOLIO_FILES)}"
        )
    if not content.strip():
        raise ValueError("content must be non-empty")
    bucket = os.environ["S3_BUCKET"]
    existing = s3_client.get_object(Bucket=bucket, Key=f"{name}.md")["Body"].read().decode("utf-8")
    merged = existing.rstrip() + separator + content
    s3_client.put_object(Bucket=bucket, Key=f"{name}.md", Body=merged.encode("utf-8"))
    _cache.pop(f"{name}.md", None)
    return f"Appended {len(content)} chars to {name}.md"


async def _reject_get_sse(scope, receive, send):
    """
    Return 405 for GET /mcp immediately.

    In stateless Lambda deployments, FastMCP's SSE stream for server-initiated
    events never closes — causing a 30s timeout and a 502. Returning 405 signals
    to clients (e.g. mcp-remote) that server-push is unsupported and they should
    use POST-only mode.
    """
    await send({"type": "http.response.start", "status": 405,
                "headers": [(b"content-type", b"application/json")]})
    await send({"type": "http.response.body",
                "body": b'{"error": "Method Not Allowed"}', "more_body": False})


def create_app():
    """Return the ASGI app. Called per Lambda invocation (see handler below)."""
    asgi_app = mcp.streamable_http_app()

    async def routing_app(scope, receive, send):
        if scope["type"] == "http" and scope["method"] == "GET":
            await _reject_get_sse(scope, receive, send)
            return
        await asgi_app(scope, receive, send)

    return BearerAuthMiddleware(routing_app)


# Lambda entry point — Mangum translates Lambda JSON event → ASGI
# FastMCP caches the StreamableHTTPSessionManager on mcp._session_manager, and
# that manager's .run() can only be called once per instance. On a warm Lambda
# invocation the same Python process reuses mcp, so we must reset the cached
# manager to None before each invocation so streamable_http_app() constructs a
# fresh one — allowing lifespan="auto" to succeed every time.
if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
    from mangum import Mangum

    def handler(event, context):
        mcp._session_manager = None  # force fresh StreamableHTTPSessionManager
        app = create_app()
        return Mangum(app, lifespan="auto")(event, context)
