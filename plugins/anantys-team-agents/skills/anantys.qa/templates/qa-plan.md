# QA campaign template — `qa-plan.md`

Written by `/anantys.qa plan` into the feature's spec-kit directory, beside `tasks.md`.
It is a **runnable campaign, not a reading list**: worked top to bottom, one assertion at a time.

**Two numbers, not one.** The progress table measures how many of the plan's own assertions have a
result — precision. It says nothing about whether the assertions cover the feature. The plan is
written by the same role that then walks it, so `100% PASS` alone means only *"I did everything I
decided to do."* §1's coverage table supplies the missing half: one row per requirement id **from
the source**, which is a denominator the campaign did not author. Index it by requirement, never by
journey — a journey-indexed table lists what each scenario covers and so can never show a
requirement nothing covers, which is the only omission worth catching.

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

**Progress — `<env>` · <N> assertions** (the default environment's from `plan`, plus one per
environment that has results — who writes and refreshes each: SKILL.md, "Progress table")

| ✅ Done | 🟢 PASS | 🔴 DEFECT | 🟠 BLOCKED | ⚪ Not run |
|---|---|---|---|---|
| 0% (0) | 0% (0) | 0% (0) | 0% (0) | 100% (<N>) |

**Coverage — <c> of <R> requirements asserted.** Progress is of this plan's own assertions and
cannot detect a requirement the plan never asserted. Both numbers are quoted together, always.

---

## 1. Scope

**Requirement coverage.** One row per requirement id in the source — every id, including the ones
nothing covers. `<R>` above is this table's row count; `<c>` is the rows with at least one
assertion. Never drop a row to make the ratio look better: an uncovered requirement is a stated
gap, a missing row is a false claim.

| Req | Source | Weight | Asserted by | Status |
|---|---|---|---|---|
| FR-0xx | `spec.md` §<n> | money | A1, A2 | covered |
| US<n> | `spec.md` US<n> | — | B3 | covered |
| R4 | `brief.md` Requirements | data | — | **UNCOVERED** — <why nothing asserts it, and what it would take> |

**UNCOVERED** is not `BLOCKED`. `BLOCKED` is an assertion that exists and could not be run;
UNCOVERED is a requirement with no assertion at all, so no run can ever surface it. An UNCOVERED
requirement carrying money / legal / data weight is a **release blocker** in §3 on its own — it is
untested by construction, and the blocker list is where untested money paths get said out loud.

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
- [ ] A2 <observable outcome> (FR-0yy). — `local`: FAIL · `staging`: not run
      ⚠️ *Adjudicated <date> (operator, run <n>, env: `<name>` | `all`): <ruling + reason>. Only
      <narrowed condition> is a real A2 failure.*
- [ ] ~~A3 <dropped behaviour>~~ — **REMOVED from the product** (<date>, operator, env:
      `all`, decided in <spec §/issue/PR>). Do not report its absence as a defect.

An adjudication is the only thing that turns a FAIL into a PASS, and this file is committed —
anyone can type one. `run <n>` points at the `qa-runs.md` section recording the FAIL that was ruled
on; a REMOVED line points at where the product decision was made. A run that cannot find that
witness still applies the ruling but reports it as **unverified**, and a ruling never removes a §3
blocker from the verdict — see SKILL.md, "Judging rules".

The per-environment suffix (`` `<env>`: PASS | FAIL | BLOCKED | not run ``) is the authoritative
result, required on every assertion that has run on any environment; a run rewrites only its own
environment's entry. The checkbox is checked only when **every** declared environment is PASS.

### B — <journey name>

…

## 3. Blockers — a FAIL here stops the release

1. **Money**: <ids> — <what they protect>
2. **Legal**: <ids> — consent recorded before the product is delivered
3. **Data**: <ids> — no overwrite of existing user data
4. **Journey**: <ids> — the product never claims a state it has not reached

5. **Untested weight**: <req ids> — UNCOVERED in §1 and carrying money / legal / data weight.
   Nothing in §2 can fail for these; they are listed here because that is the point.

Everything else is a defect to file, not a blocker.

A blocker that passes **because of an adjudication** is listed here as `<id> PASS by ruling <date>`,
never as a plain pass. Narrowing a blocker is legitimate; doing it invisibly is not.

⚠️ Passing every blocker is not the same as having tested everything. See §1 and §4.

## 4. Known gaps — never observed, only inferred. Never record these as PASS

Assertions that exist and cannot be reached. A requirement with no assertion does not belong
here — it is UNCOVERED in §1, and putting it here would hide it among cases a run at least knows
to skip.

- **<assertion / path>** — <why an agent cannot reach it, and the exact human step needed>

## 5. Report format

| ID | Scenario | Env | Result | Evidence |
|----|----------|-----|--------|----------|
| A1 | <short> | `local` | PASS | <what was observed — exact copy, URL, screenshot> |

For each FAIL: what you saw, what the case expected, the URL, and the console/network error.

The release verdict quotes **both** numbers — `<x>% PASS of <N> assertions, covering <c> of <R>
requirements` — and names every UNCOVERED requirement. A verdict that quotes only the first is
answering a question nobody asked.
```

---

## Companion: `qa-runs.md`

Appended by `run` / `retest` — **never overwritten**. Prior runs are how a later reader
recognises a re-occurrence instead of re-diagnosing it from scratch.

```markdown
# Run log — <feature>

> **Status as of run <n>, per environment:** `local`: <open blockers, or "no open defects"> ·
> `staging`: <…>. A result on one environment says nothing about another.

## Run <n> — <date> — `run` | `retest` — env: `<name>` — mode: autonomous | interactive

Environment: `<name>` (`local` | `shared`). Subject: <account/fixture id>. Build observed:
<branch/commit the env was serving, from its build-identity check — omit only when the plan has no
**Under test:** line>. Path walked: <one line>.

| ID | Result | Evidence |
|----|--------|----------|
| A1 | ✅ | <observation> |
| A4 | ❌ | <what was seen> vs <what was expected> — <url> |
| C2 | ⛔ BLOCKED | <why unreachable> |

### Defects opened this run
- **<id>** — <one line>

### Closed this run — do not re-file
| ID | Was | Now |
|----|-----|-----|
| <id> | <symptom> | ✅ FIXED — <how it was verified> |
| <id> | <symptom> | **NOT A DEFECT** — <operator ruling + reason> |
```
