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

**Recorded under:** anantys-team-agents v<running plugin version>. The rules that scored the
statuses below — what counts as PASS, when a green retest closes a defect, what an adjudication
annotation authorises. The other header lines pin the code and the requirements; this one pins the
contract, so a later reader is not silently applying today's rules to an older campaign's results.
`plan` **preserves** this line on a regeneration rather than refreshing it: restamping carried-over
statuses would assert that the new rules scored results they never saw. `status` and `report` name a
mismatch in the ship sentence; nothing invalidates or blocks on it, since the version also moves for
changes that touch no scoring rule.

The value is the `version` field of the running plugin's `.claude-plugin/plugin.json` — **read it,
never recall it**, since a version you remember is the one you were trained on, not the one scoring
this campaign. If it cannot be read, write `unknown`: never omit the line, never guess a number.
`unknown` **never matches** any version, so a reader declares a mismatch exactly as it would for a
real one. A stamp that goes quiet when it cannot be produced restores the gap it was added to close.

**Exercised as:** `<subject class>` per declared environment — the permission level the statuses
below are claims about (`owner`, `member`, `anonymous`, …), never the account identifier, which is
a credential. An environment's block may list several accounts; this line says which of them the
plan speaks for. §3's Money, Legal and Data blockers are the classes whose behaviour *is* the
permission, so a blocker green as an owner has been tested for nobody else. Where a campaign's
results span more than one class the per-assertion suffix keys on both — `` `staging`/`member`:
PASS `` — exactly as it already keys on the environment, and a run rewrites only the entry for the
pair it used. A run whose class this line does not name may not overwrite another class's verdict:
add the key, or record `BLOCKED`. Unlike **Recorded under:**, this is not a staleness question —
a member's FAIL written into an owner's slot does not date the record, it falsifies it.

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
      ⚠️ *Adjudicated <date> (operator, env: `<name>` | `all`, as: `<class>` | `all`): <ruling +
      reason>. Only <narrowed condition> is a real A2 failure.*
- [ ] ~~A3 <dropped behaviour>~~ — **REMOVED from the product** (<date>, operator, env:
      `all`). Do not report its absence as a defect.

The per-environment suffix (`` `<env>`: PASS | FAIL | BLOCKED | not run ``, or ``
`<env>`/`<class>`: `` where **Exercised as:** declares more than one) is the authoritative
result, required on every assertion that has run on any environment; a run rewrites only its own
key's entry. The checkbox is checked only when **every** declared key is PASS.

### B — <journey name>

…

## 3. Blockers — a FAIL here stops the release

1. **Money**: <ids> — <what they protect>
2. **Legal**: <ids> — consent recorded before the product is delivered
3. **Data**: <ids> — no overwrite of existing user data
4. **Journey**: <ids> — the product never claims a state it has not reached

Everything else is a defect to file, not a blocker.

⚠️ Passing every blocker is not the same as having tested everything. See §4.

## 4. Known gaps — never observed, only inferred. Never record these as PASS

- **<assertion / path>** — <why an agent cannot reach it, and the exact human step needed>

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
**Under test:** line>. Recorded under: anantys-team-agents v<running version, read from
`.claude-plugin/plugin.json`; `unknown` if unreadable>. Path walked: <one line>.

| ID | Result | Evidence |
|----|--------|----------|
| A1 | ✅ | <observation> |
| A4 | ❌ | <what was seen> vs <what was expected> — <url> |
| C2 | ⛔ BLOCKED | <why unreachable> |

### Created in the environment this run

**Run state:** in progress | complete — written `in progress` when this section is opened, which
is *before* the walk, and flipped to `complete` by `run` step 5. It is a property of the whole run
section; it lives here because this is the part of it that must exist first.

| What | How to find it | How to remove it |
|----|----|----|
| <record / account / order / upload> | <id, or the query that finds it> | <command, or "operator only"> |

This is the same list `run` echoed to get the operator's go before writing anything (SKILL.md,
`run` step 1). The consent is spent in one prompt; the data is not. On a `local` env "the reset
covers it" is a complete answer. On a **`shared`** env the environment is never reset, so this
table is the only record that the campaign's footprint exists at all — every run's rows persist,
and nobody can remove what no artifact names.

An assertion whose precondition is satisfied by a row in **any** prior run's table is standing on
state the campaign created, not on the product's own data: record it `BLOCKED`, never PASS. "A
defect you caused is not a defect" cuts both ways, and across runs this table is the only way to
tell the difference.

**A prior run with no such table wrote nothing that can be ruled out.** It predates this section;
it is not a run that created nothing. So on a `shared` env, every record is trivially absent from
every prior table, and a check reading that absence as clearance — staging preflight S3, and this
rule — passes on exactly the leftovers it exists to reject. Until each prior run in `qa-runs.md`
either carries this table or is struck as unaccounted, treat the campaign's footprint as unknown:
S3 is `BLOCKED`, and so is any assertion whose precondition needs data the campaign did not create.
An unaccounted footprint is the one thing a later run cannot reconstruct by looking.

**The section is opened before the first write, not written at the end.** `run` appends the run
section to `qa-runs.md` at step 5, after the step-3 walk that creates the data — so everything
between the operator's go and the end of the walk is a live environment holding records that no
artifact names. That is not an edge case: it is every run that is interrupted, and a
forty-scenario campaign against staging is exactly the shape that runs out of context, loses its
browser session, or gets `^C`'d. So `run` writes the run header and this empty table
**immediately after the go**, marked `in progress`, and appends **each row before performing the
write it describes**. Step 5 then fills in results and flips the state to `complete`.

A row may therefore name a record that was never created — the write it preceded did not happen.
That asymmetry is deliberate: a phantom row costs one lookup, a missing row costs an unfindable
record in an environment that is never reset.

**A section left `in progress` is a run that stopped without saying so**, and it is the only
durable trace of one. Read it as a footprint, never as results: its rows count for the rule above
(a precondition they satisfy is `BLOCKED`), and its result table counts for nothing — the
assertions it does not list were not walked and keep their previous status. Do not delete it and
do not fold it into the next run; a later `run`, `retest`, `status` or `report` that finds one
says so, because an operator who does not know a run died does not know to go looking. And note
what this buys the rule above: *a prior run with no such table* fires on a **section** that lacks
the table. A run that died before writing its section leaves no section at all, so nothing fires
and `qa-runs.md` reads exactly as if the run never happened. Opening the section first is what
gives that rule something the failure cannot erase.

### Defects opened this run
- **<id>** — <one line>

### Closed this run — do not re-file
| ID | Was | Now |
|----|-----|-----|
| <id> | <symptom> | ✅ FIXED — <how it was verified> |
| <id> | <symptom> | **NOT A DEFECT** — <operator ruling + reason> |
```
