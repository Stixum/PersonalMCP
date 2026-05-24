# placeholder.example — Template portfolio files

These are **generic templates** showing the shape and intended content of each
of the 10 personal-context files this MCP server exposes. They contain **no
personal data** — they're safe to commit and share.

## How this directory relates to `placeholder/`

| Directory | Tracked? | Contents |
|-----------|----------|----------|
| `placeholder.example/` | ✅ Committed to git | Sanitized templates (this directory) |
| `placeholder/` | ❌ Gitignored | The operator's **real** personal content — local working copies that get synced to S3 |

Same pattern as `.env.example` / `.env`.

## Getting started for a new operator

```bash
# 1. Copy templates into your local working directory
cp -R placeholder.example/* placeholder/    # placeholder/ is gitignored

# 2. Fill in each file with your own content (any text editor)
$EDITOR placeholder/identity.md

# 3. Sync to your S3 bucket (the live source the Lambda reads from)
aws s3 sync placeholder/ s3://<your-bucket>/
```

## File purposes

| File | Purpose |
|------|---------|
| `identity.md` | Who you are at the highest level — name, role, location, one-line summary |
| `role-and-responsibilities.md` | What you do for work — title, scope, industry focus, typical deliverables |
| `goals-and-priorities.md` | Active goals across professional / project / personal axes |
| `domain-knowledge.md` | Areas of deep expertise the AI should assume |
| `communication-style.md` | How you want responses formatted — length, voice, structure |
| `preferences-and-constraints.md` | General work-style preferences (tools, AI autonomy level, code style) |
| `operational-rules.md` | Hard rules the AI must follow — deploy/data principles, project-specific mechanics |
| `ai-assistant-instructions.md` | Procedural rituals the AI runs (session start, post-deploy, when X happens) |
| `tools-and-systems.md` | Toolset overview, cloud philosophy, knowledge-base layout |
| `current-projects.md` | Table-of-contents of active projects with deep-note pointers |

## Design philosophy

The 10 files are intentionally split by **purpose**, not by topic. The split
matches how AI assistants need to read context:

- **Stable identity layer** (`identity`, `role-and-responsibilities`, `domain-knowledge`) — rarely changes
- **Style layer** (`communication-style`, `preferences-and-constraints`) — how to respond
- **Rules layer** (`operational-rules`, `ai-assistant-instructions`) — what to do and not do
- **State layer** (`goals-and-priorities`, `current-projects`, `tools-and-systems`) — what's current

Keep each file focused on its slot. When a file balloons past ~10KB it's
usually mixing layers and wants to be split.
