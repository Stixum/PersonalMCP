# PersonalMCP — Claude Code Context

## What This Is

Personal MCP resource server. Exposes 10 markdown portfolio files from S3 as MCP
resources so any MCP client (Claude Desktop, Claude Code, claude.ai) automatically
has personal context without copy-pasting.

## Stack

- Python 3.13 (must match Lambda runtime — use `python3.13` not `python3`)
- MCP SDK: `mcp[cli]` — FastMCP from `mcp.server.fastmcp`
- Starlette/ASGI served via Mangum on Lambda Function URL (BUFFERED mode)
- S3 for file storage — update files without redeploying

## Key Files

| File | Purpose |
|------|---------|
| `server.py` | FastMCP + 10 resource registrations + Lambda handler |
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
