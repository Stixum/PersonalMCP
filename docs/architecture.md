# Architecture

```
MCP client                     Lambda Function URL              S3
──────────                     ───────────────────              ──
POST /mcp        ──────────→   alias `live` → version N
Authorization: Bearer <t>      ├─ BearerAuthMiddleware  (401 on bad token)
                               ├─ GET short-circuit     (405, no SSE)
                               ├─ Mangum → ASGI
                               └─ FastMCP (stateless)   ──────→  10 × <stem>.md
                                    └─ ETag cache (warm)  ←────  304 or body
```

One Lambda, one bucket, no database, no VPC. Idle cost is the S3 storage of ten small
markdown files.

---

## Request path

**Transport.** Streamable HTTP, served by FastMCP in `stateless_http=True` mode. Stateless
is required: Lambda gives no session affinity, so any invocation must be able to serve any
request.

**`GET /mcp` returns 405 immediately.** FastMCP's SSE stream for server-initiated events
never closes, which on Lambda means a 30-second hang and a 502. Returning 405 tells
clients (including `mcp-remote`) that server-push is unsupported so they fall back to
POST-only. This is a routing shim in front of the ASGI app, before FastMCP sees the
request.

**DNS-rebinding protection is disabled.** It guards browser-based attacks against
localhost MCP servers. There is no localhost here, and leaving it on returns 421 for
non-localhost `Host` headers — i.e. every real request.

**Warm-invocation session manager reset.** FastMCP caches a `StreamableHTTPSessionManager`
on `mcp._session_manager`, and that manager's `.run()` is single-use. A warm Lambda reuses
the same Python process, so the handler sets `mcp._session_manager = None` before each
invocation to force a fresh manager and let `lifespan="auto"` succeed every time. Without
this, the second request to any warm container fails.

---

## Auth

`BearerAuthMiddleware` (see [auth.py](../auth.py)) wraps everything. It compares the
`Authorization: Bearer` value against `MCP_BEARER_TOKEN` using `hmac.compare_digest`, and
returns 401 before any MCP machinery runs.

Known and accepted properties of this model, for a single-operator server:

- **One token, all four tools.** There's no read-only credential. Anyone holding the token
  can rewrite the portfolio.
- **Rejection timing differs.** A missing token short-circuits faster than a wrong one.
  Constant-time rejection across all paths would mean always running `compare_digest`
  against a dummy. The leak is "was a token present," not token content.
- **No rate limiting and no rotation mechanism.** Rotation is: change the env var,
  redeploy, update clients.

If this ever serves more than one operator, all three need revisiting first.

---

## Content in S3, not in the deploy

The ten files live in S3 rather than in the Lambda zip. Editing context is an S3 write;
it takes effect on the next read with no redeploy. That's what makes
`update_context` / `update_subsection` viable as live tools — a self-updating portfolio
bundled into the artifact would require a deploy per edit.

It also means **S3 is the source of truth.** Any local copy is a snapshot that drifts the
moment a client writes through the MCP tools. Enable bucket versioning: `update_context`
is an unversioned full overwrite, and versioning is the only undo.

---

## Caching

A module-level `_cache: dict[str, tuple[str, str]]` maps S3 key → `(etag, content)`. It
lives in the Python process, so it survives warm invocations and dies with the container.

Cached keys are re-fetched with `If-None-Match`. S3 returns 304 for unchanged objects
(~5ms) instead of the body (~30ms) — so the steady state is a conditional request, not a
blind trust of stale content. Correctness is preserved across containers, and multiple
clients writing to the same bucket can't serve each other stale data for longer than one
request.

Writes pop their own key. The index path fetches all ten keys through a
`ThreadPoolExecutor` so the no-argument call is one round trip wide, not ten deep.

---

## Cold start

Three choices, in order of impact:

1. **SnapStart**, which requires the Function URL to target a *published version* — so it
   points at alias `live`, and `live` points at a version.
2. **arm64/Graviton**, with dependencies installed for `manylinux2014_aarch64`.
3. **A small zip** — `boto3` is not bundled (the Lambda runtime provides it), and
   `__pycache__` is stripped at package time.

The SnapStart constraint drives the whole deploy sequence:

```
build zip → update $LATEST → publish version N → wait for snapshot → point alias live → N
```

`update-function-code` alone changes `$LATEST` only. The Function URL targets the alias,
so **the URL keeps serving the previous snapshot** until the alias moves. Always deploy
via [`deploy.sh`](../deploy.sh), never with a bare `update-function-code`.

`deploy.sh` then polls the live URL with an unauthenticated POST until it gets a 401 —
proof that the new version's auth middleware is serving, since alias routing takes 10–15
seconds to propagate. A 504 during that window means it's still routing to a container
that isn't up yet.

---

## Failure modes worth knowing

| Symptom | Cause |
|---|---|
| 502 after ~30s on a `GET` | SSE stream never closing — the 405 shim exists to prevent this |
| 421 on every request | DNS-rebinding protection re-enabled |
| Second request to a warm container fails | `mcp._session_manager` not reset |
| Deploy "succeeds," behavior unchanged | `$LATEST` updated but alias not re-pointed |
| 504 for ~15s right after deploy | Normal alias-routing propagation |
| Stale content right after a write | Another warm container's ETag cache; resolves on its next conditional GET |

---

## Testing

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

36 tests over the tool surface and auth: cache hit/invalidation, index construction,
heading slicing, and every `update_subsection` guard (exact-match-only, ambiguity,
heading mismatch, wrong level, spacing normalization, round-trip idempotence). S3 is
mocked; there's no live-AWS integration test.
