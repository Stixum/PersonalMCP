# Tools and Systems

The toolset the operator works in. Tells the AI what's available, what's
preferred, and where things live.

## What to include

- **Editors / IDEs** — what's open and integrated
- **Cloud / hosting** — primary provider, account structure, regions
- **Knowledge base** — where notes/docs live (e.g., a Notion workspace, a local markdown vault, etc.)
- **Source control** — GitHub org/user, branching conventions
- **Communication tools** — Slack, email, etc., if relevant to async tasks
- **MCP servers** — what's connected, what each provides
- **Local conventions** — directory structure for projects, shared scripts, etc.

## What NOT to include

- Credentials (those live in a password manager / secrets vault)
- Detailed configuration (those live in each project's repo / CLAUDE.md)

## Why this matters

When the AI suggests "store this in a database" or "publish to a queue," it
should be picking from the operator's actual stack — not random defaults.
This file is the lookup table.
