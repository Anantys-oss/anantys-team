# QA campaign template — `qa-plan.md`

Written by `/anantys-team-agents:anantys-qa plan` into the feature's spec-kit directory, beside `tasks.md`.
It is a **runnable campaign, not a reading list**: worked top to bottom, one assertion at a time.

---

```markdown
# QA campaign — <feature>

Derived from [`tasks.md`](./tasks.md) (what is built) and [`spec.md`](./spec.md) (what each case
cites). Environment: [`.anantys/qa.md`](../../.anantys/qa.md). Runs: [`qa-runs.md`](./qa-runs.md).

**Under test:** <branch> @ <head commit> — <environment> (pr: <ref>). A `--from pr:` campaign
records the head branch and commit it was derived from here, and `run` verifies the environment is
actually serving that code before walking a single scenario — a plan built from an unmerged PR, run
against a stack serving `main`, reports green having verified nothing. Once the PR has merged and
deployed, a deployed commit that contains it satisfies the line; there is no need to edit it. Omit
it for a feature that was already merged and deployed when the plan was written.

**How to use.** Preflight first — stop if it fails. Reset (a `local` env only — never a `shared`
one). Then walk §2 in order. Each scenario states its **precondition**, its **steps**, and what to
**assert**. Record PASS/FAIL/BLOCKED **per assertion and per environment**, never one verdict per
scenario. A case you could not run is `BLOCKED`.

Phases covered: <n> of <m> from `tasks.md`. **Excluded: Phase <k> (Polish)** — optional hardening,
not user-observable.

**Progress — `<env>` · <N> assertions** (one per declared environment, written by `plan` and
refreshed per SKILL.md, "Progress table". A fresh plan is not all Not run: each environment's
construction blocks are already `BLOCKED`, so the counts differ between environments. Below, `<b>`
is this environment's count of them — `0` for an environment that blocks nothing.)

| ✅ Done | 🟢 PASS | 🔴 DEFECT | 🟠 BLOCKED | ⚪ Not run |
|---|---|---|---|---|
| …% (<b>) | 0% (0) | 0% (0) | …% (<b>) | …% (<N − b>) |

---

## 1. Scope

| Journey | Covers tasks | Requirements |
|---|---|---|
| A — <name> | T0xx–T0yy | FR-0xx, US<n> |

## 2. Scenarios

### A — <journey name> (<why this one matters>)

**Precondition**: <clean state required, and why a leftover one changes the test>

1. <step>
2. <step>

**Assert**

- [ ] A1 <observable outcome> (FR-0xx). — `local`: PASS · `staging`: not run
- [ ] A2 <observable outcome> (FR-0yy). — `local`: PASS-with-note · `staging`: not run
      ⚠️ *Adjudicated <date> (operator, env: `<name>` | `all`): <ruling + reason>. Only <narrowed
      condition> is a real A2 failure.*
- [ ] ~~A3 <dropped behaviour>~~ — **REMOVED from the product** (<date>, operator, env:
      `all`). Do not report its absence as a defect.
- [ ] A4 <observable outcome> (FR-0zz). — `local`: BLOCKED (out of reach) · `staging`: not run
      ⛔ *Out of reach on `local`: <why no fix clears it> — <the named human step, or the
      environment where it can be observed>.*
- [ ] A7 <observable outcome> (FR-0ww). — `local`: PASS (unstable) · `staging`: not run

The per-environment suffix (`` `<env>`: PASS | PASS-with-note | PASS (unstable) | FAIL | BLOCKED |
BLOCKED (out of reach) | not run ``) is the authoritative result, required on every assertion that
has run on any environment; a run rewrites only its own environment's entry. The checkbox is
checked only when **every** declared environment is PASS.

`PASS-with-note` is the suffix of an adjudicated FAIL: the observation stands, the operator ruled it
not a defect, and the annotation above says under what narrowed condition a real failure still
counts. It counts as PASS everywhere a result is counted, and the ruling writes it (SKILL.md,
`note`). An annotated assertion still suffixed `FAIL` on the ruling's environment is a ruling that
never landed — the table calls it a DEFECT and `qa-report.md` hands it to a dev agent. Never written
from a `BLOCKED` or a `not run`: there is no observation to settle.

`BLOCKED (out of reach)` is a plain BLOCKED everywhere a result is counted — the progress table's
BLOCKED column, `Done`, the release verdict's untested list. The qualifier says one further thing
and only that: **no fix on this environment can clear it**, so `retest` leaves it out of the subset
(SKILL.md, `retest`) and the operator, not the dev agent, owns closing it. Record the step that
would. An item a fix or a deploy *does* clear — an undeployed backend half, an open stacked PR — is
a plain BLOCKED and belongs in the subset.
- [ ] A4 <observable outcome> (FR-0zz). — `local`: not run · `production`: BLOCKED
      ⛔ *Blocked by construction (env: `production`): <why no run there can reach it — charges a
      real card, needs an emailed code, no sandbox instrument>. Human step: <the step that would
      clear it, or "none — verify on `<other env>`">.*

The per-environment suffix (`` `<env>`: PASS | FAIL | BLOCKED | not run ``) is the authoritative
result, required on every assertion that has run on any environment or is blocked by construction on
one; a run rewrites only its own environment's entry. The checkbox is checked when **every**
environment that can run the assertion is PASS — an environment that blocks it by construction is
not one of them, or the case stays unchecked forever.

### B — <journey name>

…

## 3. Blockers — a FAIL here stops the release

1. **Money**: <ids> — <what they protect>
2. **Legal**: <ids> — consent recorded before the product is delivered
3. **Data**: <ids> — no overwrite of existing user data
4. **Journey**: <ids> — the product never claims a state it has not reached

Everything else is a defect to file, not a blocker.

⚠️ Passing every blocker is not the same as having tested everything. See §4 — and a blocker's PASS
is a statement about the build it was observed on, which after a fix pass is rarely the one now
being served (SKILL.md, "A PASS belongs to the build it was observed on").

⚠️ A blocker that §4 blocks by construction on an environment **cannot go green there**. On a
`Production: yes` environment that is most of this list by design — money, consent and notification
are exactly what is unsafe there — so a production campaign clears a release verdict for no one.
`report` names which environment can.

## 4. Known gaps — never observed, only inferred. Never record these as PASS

- **<assertion / path>** — <why an agent cannot reach it, and the exact human step needed>
  — `out of reach` (no fix clears it) | `pending` (a fix or a deploy does)
Every construction block (SKILL.md, "Construction blocks") is listed here with the environments it
applies to, written by `plan` — not discovered by a run.

| Assertion(s) | Blocked on | Why no run there can reach it | Human step that would clear it |
|---|---|---|---|
| <ids> | `all` | <CAPTCHA, emailed code, true mobile viewport> | <the exact step> |
| <ids> | `production` | unsafe on production — <charges / consent / notifies> | none — verify on `<env>` |
| <ids> | `local` | <no sandbox instrument / no record exhibiting it> | <provision it> |

## 5. Report format

| ID | Scenario | Env | Result | Evidence |
|----|----------|-----|--------|----------|
| A1 | <short> | `local` | PASS | <what was observed — exact copy, URL, screenshot> |

For each FAIL: what you saw, what the case expected, the URL, and the console/network error.
```

---

## Companion: `qa-runs.md`

Appended by `run` / `retest` — **never overwritten**. Prior runs are how a later reader
recognises a re-occurrence instead of re-diagnosing it from scratch. A run's section is opened
**before** its first scenario and each result row appended as it is judged, so a walk that is cut
short still leaves what it observed.

Two parts, two rules. The `## Run <n>` **sections** are append-only. The `> Status as of run <n>`
**block above them is a summary**, rewritten by every `run` / `retest` from the plan's current
results, for every environment that has any (SKILL.md, `run` step 5). A summary nothing rewrites
reports the first run's blockers under the last run's log.

```markdown
# Run log — <feature>

> **Status as of run <n>, per environment:** `local`: <open blockers, or "no open defects"> ·
> `staging`: <…>. A result on one environment says nothing about another.

## Run <n> — <date> — `run` | `retest` — env: `<name>` — mode: autonomous | interactive
⏳ in progress | ✅ complete

Environment: `<name>` (`local` | `shared`). Subject: <account/fixture id>. Build observed:
<branch/commit the env was serving, from its build-identity check — omit only when the environment
declares no such check *and* the plan has no **Under test:** line>. Path walked: <one line>.

`Build observed:` is what dates every result in the table below. A later reader compares it to the
build now served to tell which of this campaign's PASSes are still statements about live code; a
section that omits it leaves its rows undatable forever.

| ID | Result | Evidence |
|----|--------|----------|
| A1 | ✅ | <observation> |
| A4 | ❌ | <what was seen> vs <what was expected> — <url> |
| A7 | ✅ PASS (unstable) | <observation> — green only after <what was retried>; first showed <what> |
| C2 | ⛔ BLOCKED | <why unreachable> |

### Defects opened this run
- **<id>** — <one line>

### Closed this run — do not re-file
| ID | Was | Now | What changed |
|----|-----|-----|--------------|
| <id> | <symptom> | ✅ FIXED — <how it was verified> | <commit, or the operator's statement of the fix> |
| <id> | <symptom> | **NOT A DEFECT** — <operator ruling + reason> | — |
```

A FAIL that came back PASS with nothing to put in **What changed** does not belong in this table: it
did not reproduce on the same build, which is not a fix. It keeps its FAIL suffix and stays open —
see SKILL.md, "A green retest is a fix only when something names the change".

**A `NOT A DEFECT` row is an echo of an annotation that is already in `qa-plan.md`, never the
record of the ruling.** The adjudication check reads the plan and nothing else, so a ruling that
exists only here suppresses nothing: the next run re-files the defect the operator closed. Whoever
received the ruling writes the annotation first — `note`, or the run itself for a mid-walk ruling —
**and sets that environment's suffix to `PASS-with-note`**, so the FAIL the next run would re-file
is no longer recorded. This row then points at a suppression that exists.

`PASS (unstable)` is the same asymmetry on the green side: an assertion that needed more than one
observation to go green. It counts as PASS everywhere a result is counted, and like every other
qualifier it is carried into the plan's suffix — that is where `retest` selects from and the only
file an adjudication lands in. This row holds the evidence the suffix cannot: what was retried, and
what the earlier observation showed. See SKILL.md, "A PASS is a single observation too".

The line under the header is written `⏳ in progress` when the section is opened and replaced with
`✅ complete` by step 5 once the walk has ended and steps 6–7 have run. **`⏳ in progress` on
the last section means the run was interrupted**: the rows it holds are real results, the
assertions below them were never walked, and `qa-plan.md` and `qa-report.md` have not been updated
for that run. A later `run`, `retest`, `report` or `status` reads that marker before it reads the
plan, and says so instead of presenting a stale plan as current. Interactive mode's deliberate
stop is *not* this case — it runs steps 5–7 and closes its section normally.
