# Current Projects

A **table of contents** of active projects, with pointers to their deep
documentation. This file is intentionally shallow — the actual project
detail lives in the operator's knowledge base (Notion, a local markdown
vault, etc.), not here.

## Why shallow

This file loads into every AI session. Deep project content would:
1. Bloat the context window
2. Go stale quickly
3. Duplicate the canonical source

A TOC pointer keeps the universal layer light and routes the AI to the
authoritative on-demand layer.

## Format suggestion

```
## <Project name> — <one-line status>

- **What it is:** <one-line description>
- **Stack:** <main technologies>
- **Status:** <active / paused / archived>
- **Deep notes:** <path / link to the canonical project doc>
```

## Maintenance

- Add an entry when a project starts
- Update status when it changes (active → paused, paused → archived)
- Remove when truly done — historical archive lives in the knowledge base, not here
- Keep entries to ~3-5 lines; resist the urge to inline detail
