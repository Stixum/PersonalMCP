# Operational Rules

Hard rules that came out of real incidents. Where `preferences-and-constraints.md`
is soft guidance, this is "don't do X, ever — here's the incident that proved it."

## Structure

Two kinds of rules:

1. **Global principles** — apply to every project (e.g., "deploy only from clean committed source")
2. **Project-specific mechanics** — apply to a single project (e.g., "Project X requires running migration Y before deploy Z")

## Each rule should have

- The **rule** itself, stated as an imperative
- The **incident** that produced it (date, what went wrong, what was lost)
- The **failure mode** the rule prevents
- Optional: the **detection signal** that catches near-misses

## Format suggestion

```
## <N>. <Rule, as an imperative>

**What it prevents:** <One-line description of the failure mode>

**Incident — <date>:** <One paragraph: what was attempted, what went wrong, recovery.>

**Apply:** <Concrete trigger — when this rule should fire in the AI's decisionmaking.>
```

## Maintenance

- Add new rules immediately after the incident that produced them (don't wait)
- Update existing rules in place when a new incident reshapes the rule
- If a rule has never fired and there's no incident behind it, it doesn't belong here
