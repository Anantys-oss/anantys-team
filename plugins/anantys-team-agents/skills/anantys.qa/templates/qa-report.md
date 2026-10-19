# QA fix brief template — `qa-report.md`

Written by `/anantys.qa report`, and by every `run` / `retest` as their last step, into the
feature directory beside `qa-plan.md`. **Overwritten** each time: it is the current state of the
open defects, never a history — `qa-runs.md` is the history.

Its reader is a **dev agent in a fresh session** that has the spec but none of your run. That is
why the shape below leads with a repro and ends with what a fix must not break: no other artifact
in the campaign carries either, and the second one is why over-fixes ship.

One report per environment — the selected one (SKILL.md, "`report`"). Paths below are relative to
**this file's own directory**, which is the feature directory.

---

```markdown
# QA fix brief — <feature> — env: `<name>`

From [`qa-plan.md`](./qa-plan.md) · runs: [`qa-runs.md`](./qa-runs.md) · environment contract:
`.anantys/qa.md` at the repo root. Environment `<name>` (`local` | `shared`, production: yes|no),
serving <branch/commit observed>. As of run <n> — <date>.

Other environments with results: `<name>`: <open defects there, or "none open">. A defect recorded
on another environment is not re-filed here — and not fixed by this brief either.

## Open defects

Every open defect on this environment, not only the last run's. Money and legal paths first.

### <A4> — <one-line symptom>

- **Requires** (<FR-0xx>): <what the requirement demands, in its own terms — not the diff's>
- **Observed**: <exact copy, URL, console/network error — credentials and real person's data redacted>
- **Repro**: <shortest path from a clean state, numbered, starting at the reset or the signed-in session>
- **Blast radius**: money | legal | data | journey | cosmetic
- **A fix must not break**: <the ids currently PASSing that the obvious fix would regress, and what
  to re-assert — especially what an *over*-fix would suppress>

## Release verdict

| Blocker | IDs | Status |
|---|---|---|
| Money | <ids> | <PASS / DEFECT / BLOCKED> |
| Legal | <ids> | … |
| Data | <ids> | … |
| Journey | <ids> | … |

**Never observed** — untested, not passing: <ids, and the human step each one needs>.

<One sentence: can this ship, and what a green blocker list is still hiding.>
```
