# `note`, `report`, `status` — adjudication and output

Read `reference/environments.md` first: each of these actions selects an environment, and a ruling
is scoped to one.

## `note` — record an operator adjudication

`/anantys.qa note A4 --env local known dev-env price drift, do not file`

Every ruling has an **environment scope**: `--env <name>` for a ruling true of one environment (any
drift), `--env all` for a product decision true everywhere (intended behaviour, a REMOVED
assertion). With no `--env`, scope it to the most recent run's environment and say so — never
default to `all`; widening a ruling is the operator's call.

Append the ruling as an annotation on that assertion in `qa-plan.md`, with the date, the scope and
the reason, in the form future runs will read:

```markdown
- [ ] A4 Checkout is priced for the selected plan and period (FR-012).
      ⚠️ *Adjudicated 2026-08-03 (operator, env: `local`): the grid/checkout price gap is a sandbox
      key drift, not a product defect. Only a mismatch in **plan or period** is a real A4 failure.*
```

An annotation with **no** `env:` (written before environments existed) is scoped to the default
environment only — except a **REMOVED** strike-through, which is a product decision and reads as
`env: all`. Scoping it to the default env would re-file the dropped behaviour as a defect on every
other environment.

Two rules make these annotations durable:

- **Narrow the assertion, never delete it.** An adjudication says which failures are real, so the
  case keeps catching the failure it was written for.
- **Record the reason, not just the ruling.** "Not a defect" without a why gets re-litigated next
  run; "the wizard *is* the AI surface here, a second one is an attention conflict" does not.

An assertion the product deliberately dropped is struck through and marked REMOVED — keep the line,
so its absence is never re-reported as a defect.

After any ruling, refresh **every** progress table in `qa-plan.md` — a REMOVED assertion leaves N
for all environments. `note --env all` prints them all; `note --env <name>` prints that
environment's.

## `report` — the fix brief

Select the environment first (`--env <name>`, else the most recent run's) and name it at the top of
the report. Write `qa-report.md` addressed to a **dev agent in a fresh session** that has the spec
context but not yours. For each open defect:

- **Assertion id and what the spec requires** (with its requirement id).
- **What you observed** — exact copy, URL, console/network error.
- **Minimal repro** — the shortest path from a clean state.
- **Blast radius** — money / legal / data / journey / cosmetic. Lead with the money and legal ones.
- **What a fix must not break** — the assertions currently passing that the obvious fix would
  regress. This is the part a fresh dev agent cannot know, and the reason over-fixes ship.

Close with the release verdict: the blocker list, its status, and — explicitly — the assertions
that were never observed. **Passing every blocker is not the same as having tested everything**;
say which gaps a green list is hiding.

Tell the operator the file is ready to paste into a dev session. Do not open issues or PRs.

## `status`

For the selected environment (`--env <name>`, else the most recent run's — say which), read
`qa-plan.md` + `qa-runs.md` and report, without running anything: the progress table
(PASS / DEFECT / BLOCKED / Not run), the blocker list with each blocker's status, the open
defects, and the never-observed gaps. One short table, then the single sentence that answers
"can this ship?".

`status` and `report` print the selected environment's table; they write nothing to the plan.
