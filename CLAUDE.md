# PersonalMCP — Claude Code Context

## What This Is

Personal MCP server. Exposes personal context to any MCP client (Claude Desktop,
Claude Code, claude.ai) via three tools backed by 10 markdown portfolio files in S3:
`get_personal_context(section)`, `update_context(name, content)` (full-file replace),
and `append_to_context(name, content)` (incremental append).

## Stack

- Python 3.13 (must match Lambda runtime — use `python3.13` not `python3`)
- MCP SDK: `mcp` — FastMCP from `mcp.server.fastmcp`
- Starlette/ASGI served via Mangum on Lambda Function URL (BUFFERED mode), arm64/Graviton
- S3 for file storage — update files without redeploying; warm Lambdas cache by ETag

## Key Files

| File | Purpose |
|------|---------|
| `server.py` | FastMCP + 3 tools + ETag cache + Lambda handler |
| `auth.py` | BearerAuthMiddleware (ASGI, hmac.compare_digest) |
| `deploy.sh` | Build zip and push to Lambda |
| `placeholder/` | Local reference copies of portfolio .md files |

## Environment Variables (Lambda only — never in code)

| Var | Value |
|-----|-------|
| `MCP_BEARER_TOKEN` | Bearer token for all MCP clients |
| `S3_BUCKET` | S3 bucket name (personal-context-portfolio-<account-id>) |

## Running Tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

## Deploying Code Updates

```bash
./deploy.sh
```

Requires `python3.13` on PATH. Install via `brew install python@3.13` if missing.

## Updating Portfolio Content (no redeploy needed)

```bash
aws s3 cp placeholder/current-projects.md s3://$S3_BUCKET/
# or sync all:
aws s3 sync placeholder/ s3://$S3_BUCKET/
```

## AWS Resources (dedicated, isolated from all other projects)

See private project notes for ARNs, account ID, and resource names.
Token is in Lambda env vars — never stored here.
