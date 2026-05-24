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
- **SnapStart enabled.** The Function URL targets the `live` alias of a published version (not `$LATEST`). `deploy.sh` publishes a new version and re-points the alias on every deploy — do not bypass it.

## Key Files

| File | Purpose |
|------|---------|
| `server.py` | FastMCP + 3 tools + ETag cache + Lambda handler |
| `auth.py` | BearerAuthMiddleware (ASGI, hmac.compare_digest) |
| `deploy.sh` | Build zip and push to Lambda |
| `placeholder.example/` | **Committed.** Generic templates describing each portfolio file — safe to share, no personal data. |
| `placeholder/` | **Gitignored.** The operator's real local copies of the 10 portfolio .md files. Edit here, then `aws s3 sync placeholder/ s3://$S3_BUCKET/` to push live. |

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

`deploy.sh` does five things in order: build arm64 zip → update `$LATEST` code → publish a new version → wait for the SnapStart snapshot to optimize → re-point alias `live` at the new version. The Function URL targets the alias, so the URL itself does not change across deploys — only an alias swap. **Do not** invoke `aws lambda update-function-code` directly; the alias would still point at the previous version.

## Updating Portfolio Content (no redeploy needed)

```bash
aws s3 cp placeholder/current-projects.md s3://$S3_BUCKET/
# or sync all:
aws s3 sync placeholder/ s3://$S3_BUCKET/
```

## AWS Resources (dedicated, isolated from all other projects)

See private project notes for ARNs, account ID, and resource names.
Token is in Lambda env vars — never stored here.
