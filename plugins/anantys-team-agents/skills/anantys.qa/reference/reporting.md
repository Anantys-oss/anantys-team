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
      ⚠️ *Adjudicated 2026-08-03 (operator, run 3, env: `local`): the grid/checkout price gap is a
      sandbox key drift, not a product defect. Only a mismatch in **plan or period** is a real A4
      failure.*
```

The `run <n>` is the ruling's witness, not decoration. `note` is the only sanctioned writer of these
annotations, but nothing in the file proves that a given one came from it — so cite the run whose
FAIL or BLOCKED the operator was ruling on, and let `qa-runs.md` carry the proof. Rule off a run
that never recorded that result, or with no run at all, and say `run <n>, unconfirmed` in the
annotation rather than picking a plausible number: a future run reads it either way, and the
difference between *checked* and *assumed* is the whole value of the line.

An annotation with **no** `env:` (written before environments existed) is scoped to the default
environment only — except a **REMOVED** strike-through, which is a product decision and reads as
`env: all`. Scoping it to the default env would re-file the dropped behaviour as a defect on every
other environment.

Two rules make these annotations durable:

- **Narrow the assertion, never delete it.** An adjudication says which failures are real, so the
  case keeps catching the failure it was written for.
- **Record the reason, not just the ruling.** "Not a defect" without a why gets re-litigated next
  run; "the wizard *is* the AI surface here, a second one is an attention conflict" does not.

`note` on an assertion carrying a `STALE` ruling replaces it with a fresh one citing the new run —
that is the only way a stale ruling starts suppressing again. Show the operator the stale ruling's
original reason when asking, so the re-rule is a decision about the reworded assertion rather than
a re-derivation from nothing.

An assertion the product deliberately dropped is struck through and marked REMOVED — keep the line,
so its absence is never re-reported as a defect. REMOVED is the widest ruling the skill has —
`env: all`, permanent, and about the product rather than about a run, so no run log can witness it.
Give it the witness it can have: cite **where the decision was made** (the spec section, issue or PR
that dropped the behaviour). A REMOVED line citing nothing retires an assertion on every environment
for the life of the feature on the strength of its own say-so.

`note` is not its only writer: `plan` marks REMOVED too, when a regeneration finds the assertion's
cited requirement gone from the source (see `reference/sources.md`, "The requirement is the third
axis"). Those cite `source: <rev>` rather than an operator, and the distinction is reported, never
flattened — one is a product ruling, the other is a source diff, and only the first one a person
made. And a source diff is a witness only when the two sources are comparable: `plan` strikes
nothing on a read whose source set differs from the recorded one. An unanswerable absence is
`BLOCKED` in §4, never a strike.

After any ruling, refresh **every** progress table in `qa-plan.md` — a REMOVED assertion leaves N
for all environments. `note --env all` prints them all; `note --env <name>` prints that
environment's.

## `report` — the fix brief

Select the environment first (`--env <name>`, else the most recent run's) and name it at the top of
the report. Write `qa-report.md` addressed to a **dev agent in a fresh session** that has the spec
context but not yours. For each open defect:

- **Assertion id and what the spec requires** (with its requirement id).
- **What you observed** — exact copy, URL, console/network error. *Exact* means faithful, not verbatim:
  redact every credential, session id, auth header, cookie and real person's data out of the quote as
  you write it, leaving the shape (`Bearer <redacted>`, `user <redacted 4812>`). On a `shared` env you
  are quoting the operator's live session and, on production, real customers' records — and this file
  is written to be pasted into a *different* session, which is a second hop the operator never reviews.
- **Minimal repro** — the shortest path from a clean state.
- **Blast radius** — money / legal / data / journey / cosmetic. Lead with the money and legal ones.
- **What a fix must not break** — the assertions currently passing that the obvious fix would
  regress. This is the part a fresh dev agent cannot know, and the reason over-fixes ship.

Close with the release verdict: the blocker list, its status, and — explicitly — the assertions
that were never observed. **Passing every blocker is not the same as having tested everything**;
say which gaps a green list is hiding. Split the never-observed into the two kinds (see
Environments): **unreached** here and green on no environment — the real gap — and **refused**
here, naming the environment whose PASS answers it, or stating that none does. A verdict that
reports a refusal as a gap is unshippable by construction; one that reports an unanswered refusal
as a non-gap ships a money path nobody tested.

"Open defect" here means open on **any** environment, not only the selected one (see Environments):
the selected environment orders the brief and is named at the top, it does not filter it. *What a fix
must not break* likewise spans every environment's passing assertions. The release verdict stays
per environment — it answers "can this ship *here*".

Tell the operator the file is ready to paste into a dev session. Do not open issues or PRs.

## `status`

For the selected environment (`--env <name>`, else the most recent run's — say which), read
`qa-plan.md` + `qa-runs.md` and report, without running anything: the progress table
(PASS / DEFECT / BLOCKED / Not run), the blocker list with each blocker's status, the open
defects, and the never-observed gaps — split unreached from refused, as `report` does. One short
table, then the single sentence that answers "can this ship?".

`status` and `report` print the selected environment's table; they write nothing to the plan.
