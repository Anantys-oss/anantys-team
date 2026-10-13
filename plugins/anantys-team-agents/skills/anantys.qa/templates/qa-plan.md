# QA campaign template — `qa-plan.md`

Written by `/anantys.qa plan` into the feature's spec-kit directory, beside `tasks.md`.
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
- [ ] A2 <observable outcome> (FR-0yy). — `local`: FAIL · `staging`: not run
      ⚠️ *Adjudicated <date> (operator, env: `<name>` | `all`): <ruling + reason>. Only <narrowed
      condition> is a real A2 failure.*
- [ ] ~~A3 <dropped behaviour>~~ — **REMOVED from the product** (<date>, operator, env:
      `all`). Do not report its absence as a defect.
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

⚠️ Passing every blocker is not the same as having tested everything. See §4.

⚠️ A blocker that §4 blocks by construction on an environment **cannot go green there**. On a
`Production: yes` environment that is most of this list by design — money, consent and notification
are exactly what is unsafe there — so a production campaign clears a release verdict for no one.
`report` names which environment can.

## 4. Known gaps — never observed, only inferred. Never record these as PASS

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
