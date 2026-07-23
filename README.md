# Personal MCP

A single-operator [MCP](https://modelcontextprotocol.io) server that gives every AI
client the same picture of who you are, how you work, and what you're working on —
and lets those clients keep that picture current.

Ten markdown files in S3. Four tools. One Lambda.

```
Claude Desktop ─┐
Claude Code    ─┼─→ Lambda Function URL ─→ S3 ─→ 10 × portfolio .md
claude.ai      ─┘      (bearer auth)
```

## The problem it solves

Every AI client starts cold. You re-explain your role, your stack, your deploy rules,
and your in-flight projects — per client, per session, forever. Project-level files
(`CLAUDE.md`, rules files) fix this *inside one repo*; nothing fixes it *across* clients.

This puts that context in one place, behind a network boundary, readable and writable
by any MCP client you authorize. Correct it once, everywhere gets it.

## What makes it work

- **Index by default.** A no-argument read returns a manifest — sizes, one-line
  summaries, and addressable heading slugs — not the whole portfolio. Clients pull only
  what a task needs.
- **Heading-addressed reads and writes.** `get_personal_context("operational-rules#deployment")`
  returns one subsection; `update_subsection(...)` rewrites exactly that slice in place.
  No read-regenerate-rewrite of a 20KB file to fix one rule.
- **Content lives in S3, not in the deploy.** Editing context never requires a redeploy.
- **Cold start stays cheap.** SnapStart on arm64, ETag-conditional GETs, a process-level
  cache that survives warm invocations.

## Docs

| Doc | What's in it |
|-----|--------------|
| [Context model](docs/context-model.md) | **The interesting part.** What the ten files are, what belongs in each, and the full heading outline of a real portfolio — structure only, no personal content. |
| [Tool reference](docs/tools.md) | The four tools, their call modes, addressing rules, and errors |
| [Architecture](docs/architecture.md) | Request path, caching, SnapStart/alias model, auth, why each choice |
| [Setup](docs/setup.md) | Standing up your own: AWS resources, deploy, client config |

Templates you can copy straight into your own portfolio live in
[`placeholder.example/`](placeholder.example/).

## Quick start

```bash
git clone https://github.com/Stixum/PersonalMCP.git && cd PersonalMCP
cp -R placeholder.example/* placeholder/   # placeholder/ is gitignored — your real content
```

Fill in the files, then follow [docs/setup.md](docs/setup.md) to create the bucket,
Lambda, and Function URL, and point your clients at it.

## Stack

Python 3.13 · FastMCP (`mcp` SDK) · Starlette/ASGI via Mangum · Lambda Function URL
(BUFFERED, arm64, SnapStart) · S3 · pytest

## Design constraint

Real portfolio content is never committed. `placeholder/` and `docs/` design notes are
gitignored; the live source of truth is the S3 bucket. The bearer token exists only as a
Lambda environment variable. See [.gitignore](.gitignore) and
[operational rule 7](docs/context-model.md#operational-rulesmd).
