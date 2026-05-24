# AI Assistant Instructions

Procedural rituals the AI must run at specific moments. Where
`operational-rules.md` says "don't do X" and `preferences-and-constraints.md`
says "I like Y," this file says "**when** Z **happens**, **do** W."

## Typical sections

- **At session start** — what to read before doing anything (e.g., a knowledge-base index, project overview)
- **When working in a worktree / isolated branch** — path conventions to respect
- **After a deploy or significant change** — what notes to update, what to verify
- **When public docs are affected** — sync requirements
- **When a band-aid spiral is forming** — when to stop and propose architecture instead
- **When a new pattern emerges** — what to capture and where

## Format suggestion

Each ritual should have:
- A **trigger** — concrete and recognizable
- **Steps** — what to do, in order
- **Failure modes** — what happens if the ritual is skipped (with incident references if any)

## Why this is separate from `operational-rules.md`

- `operational-rules.md` is about **what** (don't deploy dirty trees, don't skip migrations)
- `ai-assistant-instructions.md` is about **when and how** the AI itself operates (read this file, update that file, run this check)

The AI is the actor in this file. In `operational-rules.md` the operator is.
