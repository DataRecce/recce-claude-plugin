# Gap Report — Eval Run `<YYYY-MM-DD>`

Action-prioritized shortlist of backend gaps revealed by the eval. **Target ≤5 entries.** This is a discipline against the broader capability backlog bleeding back in; it is not an ordinal performance score.

If after a receipts-style review you have ≥6 genuinely independent blockers that cannot be subsumed under each other or deferred to a later iteration, exceed the target and add one line at the top of the entries section: `Target exceeded because <reason>.` "Genuinely independent" is the bar — if two entries share a fix, they are one entry.

Items not promoted to this report are explicitly NOT in scope for v1 backend additions; they remain in the broader capability backlog as reference for future iterations.

## Prioritization criteria (qualitative, not a formula)

When deciding what to promote and in what order, consider — as case-study judgment factors, **not weights to multiply**:

- Whether the gap blocked the agent on multiple fixtures vs one.
- Whether a cheap fix exists at all (skill-side change, MCP tool addition, or honest single-env degradation).
- Whether closing the gap would decisively shift the agent's verdict on the affected fixtures.
- Whether Super / 205DataLab would hit this on their first real PR.

These are reasons you give in prose, not a score you compute. If you find yourself ranking entries by a numeric product, stop — that's the leaderboard trap.

## Entries

### 1. `<gap-name>`

- Fixtures where this blocked the agent: `<pr-id, pr-id, ...>`
- What the gap is, in plain terms: `<one sentence — no Recce-internal jargon>`
- Cheapest fix: `<skill-side prompt change | MCP tool addition | honest single-env degradation — pick one>`
- Why this fix beats the other two: `<one sentence>`

### 2. ...

### 3. ...

### 4. ...

### 5. ...

## Not promoted to this report

Receipts. List the candidate gaps that surfaced in the case studies (or were under active consideration from the broader capability backlog) and were **not** promoted here. One line each, with the reason. Acceptable reasons:

- "Not blocking any fixture in this run."
- "Covered by an existing skill-side prompt."
- "Deferred to v2 — out of v1 scope per project description."
- "Subsumed by entry #N above."

This section is not a completeness audit against the full backlog — only the candidates we actually considered for this run. It exists so a reader can see what was *deliberately* pruned, not what slipped through.
