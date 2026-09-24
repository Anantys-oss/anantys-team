---
name: anantys.qa
description: Run a browser-driven QA campaign against a completed feature. Derives an executable test plan from a spec-kit tasks.md, a freeform feature brief (--brief), or a set of tracker issues (--from linear:SKU-…), executes it in a real browser — against a local dev stack or a deployed environment (staging / a preview), selected with --env — recording PASS/FAIL/BLOCKED per assertion, accumulates operator adjudications so a defect is never re-filed twice, and emits a copy-pasteable fix brief for the dev agent. Environment specifics live in a project-local .anantys/qa.md, never in the skill. Use to QA a finished feature — however it was built — before release.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Task, TaskCreate, TaskUpdate, TaskList
---

## Mission

A spec-kit epic that reports "all tasks done" has been verified by the agent that wrote it — which is no verification at all. You are the **independent QA pass**: you drive the real product in a real browser, assert against the **spec's intent** rather than the implementation, and hand back a decision-ready verdict.

Three properties make this useful rather than ceremonial:

1. **Assertion-level results.** Most features fail in exactly one place while looking fine everywhere else. Record PASS/FAIL/BLOCKED **per assertion**, never one verdict per scenario.
2. **Adjudication memory.** Half of what a first run reports as a defect turns out to be intended behaviour, a known env drift, or a deliberate product decision. Every such ruling is written back into the plan so no future run re-diagnoses it from scratch. This is the single highest-value artifact the campaign produces.
3. **No inferred passes.** A case you could not reach is `BLOCKED`. Never `PASS`.

## Actions

Invoked as `/anantys.qa <action> [args]`. If no action is given, infer it: no `.anantys/qa.md` → `init`; no `qa-plan.md` → `testplan`; otherwise → `status`.

| Action | What it does |
|---|---|
| `init` | Interview the operator and write `.anantys/qa.md` — the project's environment contract |
| `testplan` | Derive `qa-plan.md` from the feature source: a spec-kit dir, a `--brief <file.md>`, or `--from linear:<SKU-…>` |
| `run` | Execute the plan in a browser — `--env <name>` targets a deployed environment (staging / preview); default is the local one — recording results and appending to `qa-runs.md` |
| `retest` | Re-run only what is unresolved plus the regression-risk cases around each fix (`--env <name>` as for `run`) |
| `note` | Record an operator adjudication into the plan so it is never re-filed |
| `report` | Emit `qa-report.md` — a fix brief to paste into a dev session |
| `status` | Summarize coverage and remaining blockers without running anything |

---

## Locating the feature

`testplan` needs a **feature source** — where the requirements (each with a stable id), *what
shipped*, and *what did not* come from. Every other action needs the **feature directory** — where
the campaign artifacts (`qa-plan.md`, `qa-runs.md`, `qa-report.md`) live. A source is one of three
kinds; all resolve to a single feature directory, so everything after `testplan` is identical no
matter how the plan was derived.

1. **spec-kit dir** (default) — a folder holding `tasks.md` (and usually `spec.md`, `plan.md`). The
   folder IS the feature directory; artifacts are written beside `tasks.md`.
   - Named: `/anantys.qa testplan 206-subscribe-funnel`.
   - Else read `specs_dir` from `.anantys/qa.md` (default `specs/`), list its subdirectories, and
     take the one matching the current git branch's name; otherwise ask.
2. **`--brief <file.md>`** — a single markdown brief you wrote by hand (`templates/feature-brief.md`),
   carrying **Requirements** (each with a stable id), a **What shipped** summary, and a **Not
   shipped / known gaps** section. The universal, dependency-free path for any feature NOT built
   with spec-kit — a bot-loop feature, a hotfix, a design doc. `testplan` **copies** the brief to
   `.anantys/qa/<slug>/brief.md` — it never edits the operator's original — and that
   `.anantys/qa/<slug>/` directory is the feature directory.
3. **`--from linear:SKU-12,SKU-13,…`** — a convenience adapter that *produces* the same brief:
   fetch the named tracker issues and their linked PRs using the session's tracker access (the
   Linear MCP tools if present, else `gh` for the GitHub issues/PRs that carry the `Linear: SKU-n`
   backlink), distil issue descriptions → **Requirements**, merged PRs → **What shipped**, and the
   issues' not-done / deferred notes → **Not shipped / known gaps**. Write the assembled brief to
   `.anantys/qa/<slug>/brief.md` and **confirm it with the operator before proceeding** — never
   invent requirements; if the session has no tracker access, say so and ask for a `--brief`. From
   there it is identical to `--brief`.

**The `<slug>`** is a stable kebab-case name, so a re-run reuses the same directory instead of
orphaning its plan and run history: for `--brief`, the brief's title heading (else the file's
basename); for `--from linear:`, the primary SKU (e.g. `sku-231`). State the slug you chose, and
reuse it verbatim on every later action.

Never guess between two candidate sources. Ask.

**Every action after `testplan` resolves the feature directory the same way:** a spec-kit dir is
itself; a brief- or linear-derived campaign lives under `.anantys/qa/<slug>/`. Locate it by the
named slug, else the `.anantys/qa/` subdirectory matching the current git branch, else the sole one
present — never guess between two, ask. All artifacts are written **inside the feature directory**,
beside its source (`tasks.md` or `brief.md`):

- `qa-plan.md` — the campaign (regenerated by `testplan`, annotated by `note`)
- `qa-runs.md` — the run log: one section per run, plus the closed-defect history
- `qa-report.md` — the fix brief for the dev agent (overwritten by `report`)

---

## `init` — write the environment contract

The skill knows *how* to QA. It must know nothing about *this* project's stack. Everything
environment-specific goes into `.anantys/qa.md` at the repo root.

Read `templates/qa-config.md` for the shape. Fill it by **interviewing the operator**, but do the
legwork first so the questions are few and precise:

- Read `README.md`, `CLAUDE.md`/`AGENTS.md`, `Makefile`, `docker-compose*.yml`, `.env.example`, `package.json` scripts.
- Detect running services: `docker ps`, and probe likely dev hostnames.
- **Never read `.env` values into the transcript.** Reference *how* to obtain a secret (`grep -oE 'X=.*' .env`), never the secret itself.

Then ask the operator only what you could not infer, in one batch:

- **Which environments exist** — the local stack, and any deployed ones worth testing against
  (staging, a PR preview). Give each a name and a `kind:` (`local` / `shared`, see Environments),
  and mark exactly one `local` as **default**.
- **Per environment:** the real base URLs (a dev stack behind a reverse proxy is rarely on
  `localhost:<port>`), **what drives the browser** (`Driven by:` — the operator's connected
  browser, or a named local command such as a screenshot script or headless runner), the preflight
  checks whose failure would waste a whole campaign, test credentials, and any known drift that
  must not be filed as a defect.
- **`local` only:** the reset procedure for a fresh test subject, and a payment sandbox instrument
  (test card / token) if any journey touches money — without one, every checkout case is BLOCKED.
- **`shared` only:** how the operator's signed-in browser session is made available to you, whether
  a real record exhibiting the behaviour under test exists there (a shared env has no fixtures), and
  how deploy lag shows up (a fix merged but not yet deployed), and **whether it is production**
  (`Production: yes | no`). A `shared` block is always written with `Reset — NONE`, never a reset
  command — do not ask for one.

Write only the environments the operator named, with real values — never copy a template block
full of `<placeholders>` into the contract. Re-running `init` on an existing file adds or updates
environment blocks and leaves the others untouched.

Confirm the file back to the operator before writing. `.anantys/qa.md` is committed — so it must
contain **no secrets**, only the commands that retrieve them.

## `testplan` — derive the campaign from the feature source

Resolve the source (see "Locating the feature"), then read it for the two roles — the
**requirements** (what each assertion cites) and **what shipped** (what was actually built):

- **spec-kit dir:** read, in this order, `spec.md` (the requirements), `tasks.md` (what was built),
  then `plan.md` / `data-model.md` / `contracts/` for anything left implicit. **Exclude the final
  Polish phase** — spec-kit's last phase is optional hardening (docs, cleanup, perf), not
  user-observable, and QA-ing it wastes a run; drop any trailing phase titled Polish / Polishing /
  Cleanup / Documentation. If the last phase is ambiguous, say which one you dropped and why — do
  not silently truncate.
- **`--brief` / `--from linear:`:** read the copied brief at `.anantys/qa/<slug>/brief.md`. Its
  **Requirements** section is the requirements role (the ids assertions cite); its **What shipped**
  section is the `tasks.md` role; and its **Not shipped / known gaps** section is load-bearing —
  each item there is a case that is `BLOCKED`-by-construction (a backend half not deployed, a step a
  browser cannot reach), **not a FAIL**. Route every such item into the plan's §4 (Known gaps) and
  mark the assertions it covers `BLOCKED` with that reason, exactly as an adjudication would —
  skipping it makes the plan FAIL the very gaps it was told to expect, which is the case this whole
  section exists to prevent. There is no Polish phase to drop. If a requirement carries no stable
  id, assign one (`R1`, `R2`, …) and write it back into the **copy** (never the operator's original)
  — ids are referenced by runs, notes and reports forever.

Then transform into scenarios (identical for every source):

- **Group by user journey, not by task.** Requirements are written by concern; a campaign must be
  journey-ordered, because that is the only order a browser can actually walk. A dozen items across
  backend, frontend and jobs usually collapse into one scenario.
- **Write assertions against the requirement, not the implementation.** Cite the requirement id
  (`FR-030`, `US4`, or the brief's `R-` ids) on each assertion. An assertion that restates the diff
  can only confirm what the model already did.
- **Prioritise the money/legal/data paths.** Anything touching payment, consent, or overwriting
  existing user data goes in the blocker list.
- **Mark what a browser agent cannot do** — CAPTCHA, emailed codes, real payment credentials,
  true mobile viewports. These are `BLOCKED` by construction and need a named human step. Say so
  in the plan rather than letting a run discover it.

Write `qa-plan.md` following `templates/qa-plan.md`. Every assertion gets a stable id
(`A1`, `B5`, …) — ids are referenced by runs, notes and reports forever, so **never renumber
them**. On a regeneration, keep existing ids and their adjudication annotations; append new ones.

Show the operator the scenario list and the blocker list before writing.

## Environments — `local` vs `shared` (staging / preview / prod)

`.anantys/qa.md` may declare **more than one environment**, so the same campaign can run against a
local dev stack *or* a deployed one. Each environment is one of two **kinds**:

- **`local`** — the developer's own stack (Docker, a dev server). It is **resettable**. This is the
  default.
- **`shared`** — a deployed, persistent environment reached over the network: **staging**, a PR
  **preview**, or **production**. It is **NEVER reset** — it may hold real data and other people rely
  on it — so a test subject is created **additively** (a new record; a new PR → a real run), and it
  is driven through the **operator's already-signed-in browser session**: the agent reuses that
  session, and never signs in, never resets, never runs a destructive command against it.

**How each environment is driven is read from its `Driven by:` line**, never assumed: the
operator's connected browser (e.g. Claude-in-Chrome), or a named local command. A `shared` env is
always driven by the operator's connected browser. An environment with no `Driven by:` line — a
legacy file included — is driven by the operator's connected browser.

**Production is a `shared` env with `Production: yes`**, and gets two extra guards:

- **Never run on production:** any scenario that charges a real card, records a real consent, or
  sends a notification (email, SMS, push) to a real person. Those assertions are `BLOCKED` on
  production **by construction** — reason "unsafe on production" — never walked.
- The pre-write confirmation below is mandatory (it applies to every `shared` env).

Select one with `--env <name>` on `run` / `retest` (`/anantys.qa run --env staging`); with none, use
the environment marked **default** (the local one). Every surface URL, preflight check, reset step,
credential and drift note then comes from **that** environment's block in `.anantys/qa.md`.

**A `.anantys/qa.md` with no `## Environment:` blocks** (written by an earlier `init`: flat
`## Surfaces` / `## Preflight` / `## Reset` / `## Credentials` sections) **is a single `local`
environment named `local`, and it is the default** — run it exactly as before, reset included.
`--env <other>` against such a file is an error: stop and tell the operator to re-run `init` to
declare the environment. Never guess an environment's kind; an env whose kind you cannot establish
is not run.

**Results are per environment**, since an assertion can pass on one and fail on another (a fix
deployed to staging but not the local stack, or the reverse):

- Every `qa-runs.md` run header names its environment (`templates/qa-plan.md`).
- The per-assertion status in `qa-plan.md` is recorded **per environment** (`local: FAIL ·
  staging: PASS`); a run updates only the selected environment's status, never another's.
- `retest`, `status` and `report` read only the results recorded for the selected environment
  (the default when no `--env` is given), and say which environment they describe.

Testing a shipped feature on `staging` is often easier than reproducing its data locally —
but the `shared` rules above are not optional, because the blast radius of a reset or a stray write
there is real data, not a fixture.

## `run` — execute the campaign

Preconditions: `.anantys/qa.md` exists, `qa-plan.md` exists.

1. **Preflight.** Run every check for the selected environment in `.anantys/qa.md`. On failure,
   **stop and tell the operator** — do not start services yourself, and do not "work around" a failed
   preflight. A campaign run on a half-up stack produces confident nonsense.
   **On a `shared` env, confirm the target before anything is written:** echo the environment name,
   its base URL, whether it is production, and the scenarios that will create data there — then
   wait for the operator's explicit go. No go, no run.
2. **Reset — `local` only.** On a `local` environment, apply its reset procedure and confirm it took
   effect (a stale auth cookie or leftover cache silently invalidates every assertion that follows) —
   verify by observing the app, not by trusting the command's exit code. On a **`shared`**
   environment there is **NO reset**: never reset staging / preview / prod — reuse the operator's
   session and create any needed test data additively (see Environments).
3. **Walk the scenarios in order**, in a real browser driven as the environment's `Driven by:`
   line says (see Environments). On production, skip the unsafe scenario classes and record them
   `BLOCKED`. Per scenario: establish the precondition,
   perform the steps, then evaluate each assertion **individually**.
4. **Post a one-line result after each scenario.** The operator is watching; a campaign that
   reports only at the end is one where a bad reset costs you the whole run.
5. **Append a run section to `qa-runs.md`**, its header naming the environment — never overwrite
   prior runs. Prior runs are how a later reader recognises a re-occurrence.
6. Update the per-assertion status in `qa-plan.md` **for the selected environment only**.

### Judging rules

- **Behaviour over stores.** Judge from what the product shows, not from a database or cache you
  polled. Reads race the writes they observe, and tokens lag the events that invalidate them —
  both will lie to you at exactly the wrong moment.
- **Confirm your own preconditions before asserting.** A surviving session, a leftover record, or
  state you created yourself by re-walking a flow invalidates the result. A defect you caused is
  not a defect.
- **Screenshot anything visual**, and capture the URL plus any console/network error on every FAIL.
- **Never infer a PASS from a screen you did not reach.**
- Check every FAIL against the adjudication annotations in `qa-plan.md` before filing it. If it is
  already ruled intended or a known drift, record it as PASS-with-note and move on.

## `retest` — the second pass after a fix

A full re-run after a fix pass is expensive and mostly re-confirms green. Instead:

1. Take from `qa-runs.md` every assertion whose latest result **on the selected environment** is
   FAIL or BLOCKED — a result recorded on another environment neither adds nor removes a case.
2. Add the **regression-risk set** around each fix — the assertions the fix could plausibly have
   broken, especially the ones an *over-fix* would break. A guard added to stop a wrong behaviour
   very often also suppresses the right one; assert the right one explicitly.
3. Add any assertion the operator flagged in `note`.
4. Run that subset with the same rules as `run`, append a run section marked `retest` with its
   environment.

State the subset before running it, and say plainly what you are **not** re-testing.

## `note` — record an operator adjudication

`/anantys.qa note A4 known dev-env price drift, do not file`

Append the ruling as an annotation on that assertion in `qa-plan.md`, with the date and the
reason, in the form future runs will read:

```markdown
- [ ] A4 Checkout is priced for the selected plan and period (FR-012).
      ⚠️ *Adjudicated 2026-08-03 (operator): the grid/checkout price gap on the dev stack is a
      sandbox key drift, not a product defect. Only a mismatch in **plan or period** is a real
      A4 failure.*
```

Two rules make these annotations durable:

- **Narrow the assertion, never delete it.** An adjudication says which failures are real, so the
  case keeps catching the failure it was written for.
- **Record the reason, not just the ruling.** "Not a defect" without a why gets re-litigated next
  run; "the wizard *is* the AI surface here, a second one is an attention conflict" does not.

An assertion the product deliberately dropped is struck through and marked REMOVED — keep the line,
so its absence is never re-reported as a defect.

## `report` — the fix brief

Write `qa-report.md` addressed to a **dev agent in a fresh session** that has the spec context but
not yours. For each open defect:

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

Read `qa-plan.md` + `qa-runs.md` and report, without running anything: counts of
PASS / FAIL / BLOCKED / not-yet-run, the blocker list with each blocker's status, the open
defects, and the never-observed gaps. One short table, then the single sentence that answers
"can this ship?".

---

## Rules

- **Environment details live in `.anantys/qa.md`, never in this skill and never in `qa-plan.md`.**
  A plan that hardcodes a hostname stops working for the next project — and for the next dev stack.
- **Never reset — or write destructively to — a `shared` environment** (staging, a preview, prod).
  It is persistent and may hold real data; create test subjects additively and drive it through the
  operator's existing browser session, after they confirm the target. Reset is for a `local` env
  only; on production, never charge, record consent for, or notify a real person.
- **Never start, restart or repair the stack.** A failed preflight stops the campaign and goes back
  to the operator.
- **Never modify product code.** You observe and report; fixing is a separate session, which is
  the entire point of `report`.
- **Assertion ids are permanent.** Never renumber. Runs, notes and reports reference them for the
  life of the feature.
- **Append runs, never overwrite them.** The history is what stops a fixed defect from being
  re-diagnosed six weeks later.
- **BLOCKED is a real result.** Report it as loudly as a FAIL — an unreachable case is untested,
  and a green blocker list that quietly contains one is worse than a red one.
- Report what you actually observed. Never a PASS you inferred.
