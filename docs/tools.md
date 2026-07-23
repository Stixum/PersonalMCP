# Tool reference

Four tools: one read, three writes. All operate on the ten portfolio files, addressed by
stem (no `.md`).

Valid names: `identity`, `role-and-responsibilities`, `goals-and-priorities`,
`domain-knowledge`, `communication-style`, `preferences-and-constraints`,
`operational-rules`, `ai-assistant-instructions`, `tools-and-systems`, `current-projects`.

An unknown name raises with the valid list. Empty content is rejected on every write.

---

## Addressing

Two address forms, used by both reads and writes:

| Address | Resolves to |
|---------|-------------|
| `identity` | The whole file |
| `operational-rules#deploy-only-from-a-clean-committed-source` | One subsection |

**Slugs** are derived from heading text: lowercased, every run of non-alphanumeric
characters collapsed to a single hyphen, ends trimmed. `### 4. Prod data mutations follow
dry-run → review → snapshot → apply` becomes
`4-prod-data-mutations-follow-dry-run-review-snapshot-apply`. You never compute these by
hand — the index lists them.

**A subsection** runs from its heading line to the next heading of equal-or-higher level,
or end of file. So an `##` section includes all its `###` children; addressing a `###`
gets just that child.

---

## `get_personal_context(section="")`

Three modes.

**No argument — the index.** Returns `identity` in full, plus for every other file: its
size, a one-line summary, and every addressable heading slug, nested by level. It does
*not* return the portfolio; that's the point. Start here, then pull what the task needs.

```
### operational-rules  (29.0K chars)
Rules that shape how the operator works across projects. The Global Principles…
Subsections:
  - operational-rules#global-principles
    - operational-rules#1-deploy-only-from-a-clean-committed-source
    …
```

All ten files are fetched concurrently to build it.

The summary line is the first non-blank line that isn't a heading, blockquote, rule, or
table row — so the first sentence of each file is load-bearing. Open files with a plain
descriptive sentence rather than a bullet.

**`section="<name>"`** — the whole file.

**`section="<name>#<heading>"`** — one subsection. Matching tries slug equality first,
then falls back to a slug *substring* match, so `operational-rules#deploy` finds the
deploy rule. A miss raises with the available slugs listed, which makes recovery a
one-shot retry rather than a guess.

---

## `update_subsection(name, heading, content)`

Replaces one subsection in place. The write mirror of `get_personal_context("name#heading")`,
and **the write you should reach for by default**.

```python
update_subsection(
    name="operational-rules",
    heading="7-personal-data-never-enters-any-shared-git-host",
    content="### 7. Personal data never enters any shared git host\n\n...",
)
```

Three guards, all deliberate:

- **Exact slug match only.** No substring fallback. Convenient for reading, unacceptable
  for a destructive write.
- **Ambiguity raises.** If two headings share a slug, it refuses rather than picking one.
- **The replacement must open with the same heading** — same level, same slug. This
  catches the failure where a model returns just the body and silently deletes the
  heading, or re-levels it and breaks its address. To rename or re-level, use
  `update_context`.

Inter-section spacing is normalized to one blank line and line endings to LF, so repeated
writes are idempotent rather than slowly accreting whitespace.

---

## `update_context(name, content)`

Full-file replace. Use for restructuring, renaming headings, or changing heading levels —
the things `update_subsection` refuses to do.

It is a straight overwrite with no merge and no diff. Read the file first, and be aware
that anything written between your read and your write is lost. Enable S3 bucket
versioning; it's the only undo.

---

## `append_to_context(name, content, separator="\n\n")`

Appends to the end of a file. Fetches, concatenates, writes back.

Useful for genuinely additive entries — a new project block, a new rule at the bottom of
a list. **Not** for revising something that already exists: appending a correction leaves
the file's bottom contradicting its top, and readers have to reconstruct current state
from a pile of dated updates. That's what `update_subsection` is for.

Rule of thumb: appending a heading that starts with "UPDATE:" means you wanted
`update_subsection`.

---

## Cache behavior

Reads go through a process-level `{key: (etag, content)}` cache that survives warm Lambda
invocations. Cached keys are re-fetched with `If-None-Match`; S3 answers unchanged objects
with a 304 (~5ms) instead of a body (~30ms).

All three writes invalidate the key they touch, so a read-after-write in the same or a
later invocation sees the new content. Verify with `get_personal_context` after any write —
a different warm container may still be holding a stale copy briefly.

---

## Errors

| Condition | Behavior |
|---|---|
| Unknown section name | Raises, lists all ten valid names |
| Unknown heading | Raises, lists every available slug in that file |
| Ambiguous heading (writes) | Raises; suggests disambiguating or using `update_context` |
| Replacement heading mismatch | Raises; states the required level and text |
| Empty content | Raises |
| Missing/wrong bearer token | HTTP 401 before any tool runs |
| `GET /mcp` | HTTP 405 — server-push is unsupported; clients use POST-only |
