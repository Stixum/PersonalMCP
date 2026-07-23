# The context model

Ten files. What each one is for, what belongs in it, and the heading outline of a real
working portfolio.

The outlines below are **structure only** — every heading is real, every piece of content
under it has been removed. Project names, employers, and product names are replaced with
`<placeholders>`. The point is to show the shape that survived a year of daily use, not
to show one person's data.

---

## Why ten files and not one

The split is by **purpose**, not by topic — because that's how an assistant reads context.
Four layers:

| Layer | Files | Changes | Answers |
|-------|-------|---------|---------|
| **Identity** | `identity`, `role-and-responsibilities`, `domain-knowledge` | Yearly | Who is this, and what can I assume they already know? |
| **Style** | `communication-style`, `preferences-and-constraints` | Rarely | How should I talk to them and work with them? |
| **Rules** | `operational-rules`, `ai-assistant-instructions` | Per incident | What must I never do, and what must I always do? |
| **State** | `goals-and-priorities`, `current-projects`, `tools-and-systems` | Weekly | What's true right now? |

Keeping the layers separate is what makes selective retrieval work. An assistant writing
a commit message needs the Rules layer and nothing else. One drafting a doc needs Style.
Merge the layers into one file and every task pays for every layer.

**Sizing heuristic:** past roughly 10KB, a file is usually mixing layers and wants to
split. The exceptions are `operational-rules` and `ai-assistant-instructions`, which grow
monotonically because they accrete one entry per incident — that's the point of them. Use
heading-addressed reads on those instead of trying to keep them small.

---

## The routing question

Most authoring mistakes are misfiled facts, not badly written ones. When a new fact
arrives, ask in this order:

1. **Did an incident cause this?** → `operational-rules.md`. Rules earn their place by
   costing something.
2. **Is the assistant the actor?** → `ai-assistant-instructions.md` ("when X happens, do
   Y"). If the operator is the actor, it's an operational rule.
3. **Is this a judgment call I want respected, not a hard rule?** →
   `preferences-and-constraints.md`.
4. **Is it about wording rather than working?** → `communication-style.md`.
5. **Will it be false in three months?** → State layer (`goals-and-priorities`,
   `current-projects`, `tools-and-systems`).
6. **Otherwise** → Identity layer.

The most common misfile is stuffing preferences into `operational-rules.md`. Keep that
file expensive to add to — a rule with no incident behind it dilutes the ones that have
one.

---

## The ten files

### `identity.md`

The elevator pitch. Stable, small, and the only file returned in full by the index — so
everything in it is paid for on every no-argument call. Keep it under ~1KB.

```markdown
# Identity

## Professional
**Name:** / **Title:** / **Location:**
One paragraph: what you do, who you serve, what you're known for.

## Side Projects
One or two lines — that a personal portfolio exists, and roughly what kind.
Enough for an assistant to know work requests and project requests are different modes.

## Personal
Location and the handful of interests that actually affect working context.
```

Not here: responsibilities, project lists, goals.

---

### `role-and-responsibilities.md`

What's actually on your plate. `identity.md` is the pitch; this is the job.

```markdown
# Role & Responsibilities

## Title & Firm
## Core Responsibilities
## Primary Deliverables      ← the artifacts you produce or own
## Industry Focus
## Working Style             ← cadence, decision authority, how you run engagements
```

Not here: client or customer names. Ever. See operational rule 7.

---

### `goals-and-priorities.md`

What you're currently optimizing for. The most perishable file in the Identity/State
boundary — stale goals produce confidently wrong suggestions.

```markdown
# Goals & Priorities

## Professional (12–18 Month Horizon)
## Side Projects
## Personal
## Deprioritization          ← what you are deliberately NOT doing right now
```

`Deprioritization` is the section most people skip and the one that pays most. Without
it, an assistant helpfully proposes the thing you already decided to drop, and you spend
your turn re-litigating a settled decision. Naming the dropped things once ends that.

---

### `domain-knowledge.md`

Calibration, not a résumé. It tells the assistant where to skip the explanation and where
to add scaffolding.

```markdown
# Domain Knowledge

## Core Expertise                        ← where to assume fluency and skip the basics
## <Functional domain> Transformation    ← deep professional domain
## AI & Software (Side-Project Derived)  ← what you learned building, not from the day job
## Adjacent Knowledge                    ← competent but not expert; explain a bit more here
```

The Core/Adjacent split is the working part. "Expert in everything" and "expert in
nothing" produce the same undifferentiated output.

---

### `communication-style.md`

How you want to be talked to. Small file, outsized effect — it's read on essentially
every session, so a word change here compounds across hundreds of responses.

```markdown
# Communication Style

## Preferred Response Format          ← bullets vs prose, headers, lead with the answer
## Directness                         ← tolerance for hedging, when to raise counterpoints
## Writing Voice (When Producing Content)   ← your voice in artifacts, distinct from chat
## What to Avoid                      ← verbosity, reflexive caveats, invented specifics
```

Separating *how you talk to me* from *how you write for me* matters more than it looks.
Chat can be terse; a client-facing draft usually can't.

---

### `preferences-and-constraints.md`

The "how I like to work" layer — soft, contextual, judgment calls. When a preference
starts causing incidents, promote it to `operational-rules.md`.

```markdown
# Preferences & Constraints

## Writing & Document Tools
## AI Autonomy                  ← when to act, when to ask, when to stop and check
## Client & Sensitive Content   ← what may never leave the machine or enter a prompt
## Code Preferences
## General Work Style

## <Dated preference> (YYYY-MM-DD)   ← preferences confirmed in the moment, timestamped

## Design / UI Standards (YYYY-MM-DD)
### Brand & Naming
### Color
### Typography
### Layout & Spacing
### Components (reuse these)
### Dark Mode
### Iconography & Favicons
### Motion
### OG / Social Cards
### Accessibility Baseline
### Best-in-class references
### Per-product exceptions
```

Two things worth copying:

- **A design-standards block.** Once it exists, "make it look like my other stuff" becomes
  a real instruction instead of a wish. It's the single highest-leverage section here if
  you ship anything with a UI.
- **Dated preference entries.** A preference confirmed on a specific day, with the date
  attached, is auditable later. Undated preferences accumulate and nobody can tell which
  ones are still true.

---

### `operational-rules.md`

The scar tissue. Hard rules, each one paid for by a real incident. This file and the next
are the two that justify the whole system — everything else is context, this is
constraint.

```markdown
# Operational Rules

## Global Principles
### 1. Deploy only from a clean, committed source
### 2. Unique-identifier registries are write-once
### 3. Worktree hygiene — replicate config before running; audit when live disagrees
### 4. Prod data mutations follow dry-run → review → snapshot → apply
### 5. Snapshot before any "replace-style" config API; pass at-risk fields explicitly
### 6. Read the compliance doc before proposing infra cuts on compliance-positioned projects
### 7. Personal data never enters any shared git host

## Project-Specific Mechanics
### <Project> — Web / Lambda
### <Project> — iOS / TestFlight
### <This repo> — ./deploy.sh
### <Project> — compliance gate
### <Project> — build artifact hygiene
```

Those seven global principles are shown verbatim on purpose: they generalize. Most
operators building on cloud infrastructure with an AI assistant will earn some version of
each, and reading them beats earning them.

Give every rule four parts:

- **The rule**, as an imperative
- **What it prevents** — the failure mode, in one line
- **The incident** — date, what was attempted, what went wrong, what recovery cost
- **Apply** — the concrete trigger that should fire the rule in an assistant's reasoning

Keep the incident. A rule without its story gets argued with; a rule with a dated
incident attached does not.

The Global/Project-specific split matters for retrieval: global principles apply
everywhere, project mechanics are dead weight outside their project. Split at the
heading level and clients can pull one project's mechanics by slug.

---

### `ai-assistant-instructions.md`

Rituals. Where `operational-rules.md` says "never do X," this says "**when** Z happens,
**do** W." The assistant is the actor in every entry.

```markdown
# Instructions for AI Assistants

## 1. At the start of every session
## 2. When working in a git worktree, edit through the worktree path
## 3. After every deploy, ship, or significant change
## 4. Keep public docs in sync with the app
## 5. When a band-aid spiral is forming, offer the architectural alternative
## 6. Verify subagent-authored facts against source files before trusting their output
## 7. Capture new patterns into personal context
```

Each ritual needs a **trigger** (concrete and recognizable), **steps** (ordered), and
**failure modes** (what breaks when it's skipped).

Rule 7 is the one that makes the system self-sustaining, and it's worth spelling out in
your own copy. It should enumerate:

- **Capture triggers** — the operator corrects your approach; the operator explicitly
  validates a non-obvious call you made; an incident produces a new rule; a new way of
  working surfaces; priorities shift; the toolset changes.
- **A file map** — trigger → destination file, so routing isn't re-derived each time.
- **The write path** — which tool to use, and how to verify the write landed.

Capture confirmations, not just corrections. "Yes, that was right" is as informative as
"no, don't do that," and almost nobody writes it down.

---

### `tools-and-systems.md`

The lookup table. Stops an assistant from suggesting a stack you don't run.

```markdown
# Tools & Systems

## Side Project Stack
## AI Tools
## Professional / <Employer> Toolset
## Personal Productivity
## Infrastructure Philosophy    ← the "why" behind the stack: cost posture, serverless bias
## <Admin dashboard> — cross-portfolio control plane
## <Knowledge base>
### Key files by project
### CLAUDE.md files (per-project AI instructions)
### Update protocol
```

`Infrastructure Philosophy` does more work than the tool lists. Knowing *which* database
you run tells an assistant what to write; knowing you optimize for near-zero idle cost
tells it what to propose.

Never here: credentials, tokens, connection strings. Those live in a secrets manager and
nowhere else.

---

### `current-projects.md`

A table of contents, not a project archive. Deep detail belongs in your knowledge base;
this file exists to route there.

```markdown
# Current Projects

## Active        ← one block per project: what it is, stack, status, pointer to deep notes
## On Deck
## Notes         ← cross-project conventions; how backlogs are tracked and where
```

Suggested entry shape:

```markdown
## <Project> (<url or identifier>) — <status, dated>
- **What it is:** one line
- **Stack:** main technologies
- **Status:** active / paused / shipped / archived
- **Deep notes:** path or link to the canonical doc
```

Keep entries to three to five lines. The pressure to inline "just a bit" of detail here is
constant and should be resisted every time — this file loads often, and duplicated project
detail goes stale faster than anything else in the portfolio.

---

## Maintaining it

**Update in place, don't append a changelog.** The failure mode of an append-only write
tool is a file whose bottom contradicts its top: an original section, then a dated update
superseding it, then an update to the update. A reader has to reconstruct current state
from a diff history. Use `update_subsection` to rewrite the affected heading and fold the
change in. Keep the date on the heading if provenance matters — but keep one section per
fact, not one section per revision. (See [tools.md](tools.md).)

**Date anything perishable.** Preferences, project statuses, and any "as of now" claim.
An assistant six months out can then discount appropriately instead of treating a stale
fact as current.

**Prune on a cadence.** Shipped projects move out of `current-projects.md`. Achieved goals
leave `goals-and-priorities.md`. Only `operational-rules.md` and
`ai-assistant-instructions.md` should grow without bound.

**Keep the index honest.** The no-argument index is built from headings and the first
non-heading line of each file. A file that opens with a bullet gets that bullet as its
summary. Open each file with one plain descriptive sentence and the index reads well for
free.

## Anti-patterns

| Anti-pattern | Why it fails |
|---|---|
| One giant `context.md` | Every task pays for every layer; nothing is selectively retrievable |
| Rules with no incident behind them | Dilutes the rules that were actually paid for |
| Inlining project detail into `current-projects.md` | Goes stale fastest, loads most often, duplicates the real source |
| Undated preferences | Unfalsifiable later; nobody can tell what's still true |
| Append-only updates | The file's bottom contradicts its top |
| Client or customer names anywhere | The portfolio syncs to cloud storage and is read by multiple clients |
| Credentials in `tools-and-systems.md` | It's a lookup table, not a vault |
