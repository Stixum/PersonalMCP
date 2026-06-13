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
import re
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


# Matches ATX markdown headings ("## Heading"); group 1 = hashes, group 2 = text.
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


def _slug(text: str) -> str:
    """Lowercase, collapse non-alphanumerics to single hyphens (heading -> address)."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _headings(content: str) -> list[tuple[int, int, str]]:
    """Return (line_index, level, text) for each ATX heading in document order."""
    out = []
    for i, line in enumerate(content.splitlines()):
        m = _HEADING_RE.match(line)
        if m:
            out.append((i, len(m.group(1)), m.group(2)))
    return out


def _summary(content: str) -> str:
    """First non-blank, non-heading, non-quote line, trimmed to one sentence-ish line."""
    for line in content.splitlines():
        s = line.strip()
        if s and not s.startswith(("#", ">", "---", "|")):
            return s[:160] + ("…" if len(s) > 160 else "")
    return ""


def _locate_section(
    content: str,
    heading_query: str,
    *,
    exact_only: bool = False,
    require_unique: bool = False,
) -> tuple[int, int, int, str]:
    """
    Locate the subsection under the heading matching `heading_query`.

    Returns (start, end, level, text): the slice runs from the matched heading line
    `start` up to (not including) `end` — the next heading of equal-or-higher level,
    or end-of-file.

    Matching is by slug equality first. With `exact_only=False` it falls back to a
    slug-substring match (retrieval convenience). With `require_unique=True` a slug
    that matches 2+ headings raises instead of guessing — destructive writes must not
    silently pick one. Raises ValueError listing available slugs when nothing matches.
    """
    target = _slug(heading_query)
    heads = _headings(content)
    exact = [h for h in heads if h[2] and _slug(h[2]) == target]
    if exact:
        if require_unique and len(exact) > 1:
            raise ValueError(
                f"Heading {heading_query!r} is ambiguous: {len(exact)} headings share "
                f"slug {target!r}. Disambiguate, or use update_context for a full rewrite."
            )
        match = exact[0]
    else:
        match = None if exact_only else next(
            (h for h in heads if target and target in _slug(h[2])), None
        )
        if match is None:
            avail = ", ".join(_slug(h[2]) for h in heads) or "(no headings in this section)"
            raise ValueError(
                f"Heading {heading_query!r} not found. Available headings: {avail}"
            )
    start, level, text = match
    end = next(
        (i for (i, lvl, _) in heads if i > start and lvl <= level),
        len(content.splitlines()),
    )
    return start, end, level, text


def _slice_section(content: str, heading_query: str) -> str:
    """Return the subsection text under the heading matching `heading_query`."""
    start, end, _, _ = _locate_section(content, heading_query)
    return "\n".join(content.splitlines()[start:end]).strip()


def _build_manifest(sections: dict[str, str]) -> str:
    """
    Build the lightweight index returned by a no-argument call.

    Includes `identity` in full (small and always relevant) plus, for every other
    section, its size, a one-line summary, and the addressable heading slugs. The
    caller uses this to pull only what a task needs instead of the whole portfolio.
    """
    parts = [
        "# Personal context — index",
        "",
        'Pull only what you need: call get_personal_context("<section>") for a '
        'whole section, or get_personal_context("<section>#<heading-slug>") for a '
        "single subsection. The addressable slugs are listed under each section "
        "below. (A no-argument call returns this index, not the full portfolio.)",
        "",
        "---",
        "",
        sections.get("identity", "").strip(),
        "",
        "---",
        "",
        "## Available sections",
    ]
    for name in PORTFOLIO_FILES:
        if name == "identity":
            continue
        content = sections.get(name, "")
        size = len(content)
        size_str = f"{size / 1000:.1f}K chars" if size >= 1000 else f"{size} chars"
        parts.append("")
        parts.append(f"### {name}  ({size_str})")
        summary = _summary(content)
        if summary:
            parts.append(summary)
        subs = [(lvl, text) for (_, lvl, text) in _headings(content) if lvl >= 2]
        if subs:
            parts.append("Subsections:")
            for lvl, text in subs:
                indent = "  " * (lvl - 2)
                parts.append(f"  {indent}- {name}#{_slug(text)}")
    return "\n".join(parts)


@mcp.tool()
def get_personal_context(section: str = "") -> str:
    """
    Read the operator's personal context from the portfolio.

    Three call modes:
      - No argument: returns a lightweight INDEX — `identity` in full plus, for
        every other section, its size, a one-line summary, and the addressable
        heading slugs. Start here to see what exists, then pull what you need.
        (It does NOT return the full portfolio; that is too large to load at once.)
      - section="<name>": returns that whole section.
      - section="<name>#<heading-slug>": returns just that subsection of the file
        (slugs come from the index, e.g. "operational-rules#deployment").

    Available sections: identity, role-and-responsibilities, goals-and-priorities,
    domain-knowledge, communication-style, preferences-and-constraints,
    operational-rules, ai-assistant-instructions, tools-and-systems,
    current-projects
    """
    if "#" in section:
        name, _, heading = section.partition("#")
        if name not in PORTFOLIO_FILES:
            raise ValueError(
                f"Unknown section {name!r}. Valid sections: {', '.join(PORTFOLIO_FILES)}"
            )
        return _slice_section(_fetch(f"{name}.md"), heading)

    if section:
        if section not in PORTFOLIO_FILES:
            raise ValueError(
                f"Unknown section {section!r}. Valid sections: {', '.join(PORTFOLIO_FILES)}"
            )
        return _fetch(f"{section}.md")

    keys = [f"{name}.md" for name in PORTFOLIO_FILES]
    with ThreadPoolExecutor(max_workers=len(keys)) as pool:
        contents = list(pool.map(_fetch, keys))
    return _build_manifest(dict(zip(PORTFOLIO_FILES, contents)))


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


@mcp.tool()
def update_subsection(name: str, heading: str, content: str) -> str:
    """
    Replace a single subsection of a portfolio file in place, addressed by heading.

    This is the write counterpart to get_personal_context("<name>#<heading>"): it
    rewrites only the slice under the matched heading and leaves the rest of the file
    untouched — no need to read, regenerate, and rewrite the whole file.

    Args:
        name: Section name without .md (one of the valid portfolio files).
        heading: The heading identifying the subsection — its slug or heading text,
            the same address used by get_personal_context("name#heading"). Must match
            exactly one heading (slug equality, no substring); an unknown or ambiguous
            heading raises with the available slugs.
        content: The full replacement for that subsection, INCLUDING its heading line.
            The first non-blank line must be a heading whose level and slug match the
            target — this guards against silently dropping, renaming, or re-leveling
            the heading (which would change its address). To rename or restructure,
            use update_context for a full-file rewrite.

    Inter-section spacing is normalized to a single blank line and line endings to LF.
    """
    if name not in PORTFOLIO_FILES:
        raise ValueError(
            f"Unknown context file: {name!r}. Valid names: {', '.join(PORTFOLIO_FILES)}"
        )
    if not content.strip():
        raise ValueError("content must be non-empty")
    bucket = os.environ["S3_BUCKET"]
    existing = s3_client.get_object(Bucket=bucket, Key=f"{name}.md")["Body"].read().decode("utf-8")
    start, end, level, text = _locate_section(
        existing, heading, exact_only=True, require_unique=True
    )

    new_block = content.strip("\n")
    first = next((ln for ln in new_block.splitlines() if ln.strip()), "")
    m = _HEADING_RE.match(first)
    if not m or len(m.group(1)) != level or _slug(m.group(2)) != _slug(text):
        raise ValueError(
            f"Replacement for {name}#{_slug(text)} must begin with the heading "
            f"{'#' * level} {text!r} (matching level and slug); got {first!r}. "
            f"Use update_context to rename or restructure."
        )

    lines = existing.splitlines()
    before = "\n".join(lines[:start]).rstrip("\n")
    after = "\n".join(lines[end:]).lstrip("\n")
    merged = "\n\n".join(p for p in (before, new_block, after) if p).rstrip("\n") + "\n"
    s3_client.put_object(Bucket=bucket, Key=f"{name}.md", Body=merged.encode("utf-8"))
    _cache.pop(f"{name}.md", None)
    return f"Replaced {name}#{_slug(text)} ({len(content)} chars)"


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
