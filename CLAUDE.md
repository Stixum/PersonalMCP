# PersonalMCP — Claude Code Context

## What This Is

Personal MCP server. Exposes personal context to any MCP client (Claude Desktop,
Claude Code, claude.ai) via four tools backed by 10 markdown portfolio files in S3:
`get_personal_context(section)` (whole file, `section#heading` subsection, or a
no-arg index), `update_context(name, content)` (full-file replace),
`append_to_context(name, content)` (incremental append), and
`update_subsection(name, heading, content)` (heading-addressed in-place replace —
the write mirror of `get_personal_context("name#heading")`).

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
| `placeholder/` | **Gitignored.** Local *snapshot* of the 10 portfolio .md files. Not the source of truth — see below. |
| `README.md`, `docs/` | **Committed, public-facing.** Architecture, tool reference, setup, and the data-free context-model outline. No personal content. |

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

`deploy.sh` does six things in order: build arm64 zip → update `$LATEST` code → publish a new version → wait for the new version's `State` to be `Active` → re-point alias `live` at the new version → once the URL answers 401, delete old versions, keeping the new one, the previous `live` target (rollback) and any alias target. SnapStart bills a cached snapshot per published version (~$1/mo each), so without the prune they pile up. If the version doesn't reach `Active`, the script exits non-zero without moving the alias. If the URL check fails, it exits non-zero, prunes nothing and prints the rollback command; the alias has already moved, so roll back or fix it right away. The Function URL targets the alias, so the URL itself does not change across deploys — only an alias swap. **Do not** invoke `aws lambda update-function-code` directly; the alias would still point at the previous version.

## Updating Portfolio Content (no redeploy needed)

**S3 is the source of truth. `placeholder/` is a stale snapshot.** Context is written
through the MCP tools (`update_subsection` / `update_context` / `append_to_context`)
straight to S3; nothing pushes those writes back down to the local directory. As of
2026-07-23, five of the ten local copies were behind S3 by ~29K chars combined
(`operational-rules` −11.8K, `preferences-and-constraints` −8.1K, `current-projects`
−7.2K, `tools-and-systems` −1.3K, `ai-assistant-instructions` −0.3K).

Preferred — from any MCP client, no shell:

1. `update_subsection(name, heading, content)` — rewrites one heading in place. Default choice.
2. `update_context(name, content)` — full-file replace; for restructuring or renaming headings.
3. Verify with `get_personal_context("<name>#<heading>")` after any write.

If a shell write is genuinely needed, pull first and never push blind:

```bash
aws s3 sync s3://$S3_BUCKET/ placeholder/            # pull down (safe)
aws s3 sync placeholder/ s3://$S3_BUCKET/ --dryrun   # inspect before any push
```

**Never run `aws s3 sync placeholder/ s3://$S3_BUCKET/` without `--dryrun` first.** A
stale local directory reverts every MCP-tool write since the last pull. Bucket versioning
is the only undo — confirm it's enabled.

## AWS Resources

Dedicated, isolated from all other projects. ARNs, account ID, and resource
names are kept in operator-private notes outside this repo. The bearer
token lives only in Lambda environment variables — never in code or any
file in this repo.
