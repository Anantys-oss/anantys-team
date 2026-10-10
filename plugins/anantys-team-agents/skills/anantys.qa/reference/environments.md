# Environments — `local` vs `shared` (staging / preview / prod)

Read this before any action that reads or writes results — `run`, `retest`, `note`, `status`,
`report` — and before `init`. `SKILL.md` carries only the selection rule; the semantics and the
guards are here.

## The two kinds

`.anantys/qa.md` may declare **more than one environment**, so the same campaign can run against a
local dev stack *or* a deployed one. Each environment is one of two **kinds**:

- **`local`** — the developer's own stack (Docker, a dev server). It is **resettable**. Normally the
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
- The pre-write confirmation is mandatory (it applies to every `shared` env): before anything is
  written, echo the environment name, its base URL, the build it serves, whether it is production,
  and the scenarios that will create data there — then wait for the operator's explicit go. No go,
  no run.

## Selecting one

Select with `--env <name>` on any action that reads or writes results — `run`, `retest`, `note`,
`status`, `report` (`/anantys.qa run --env staging`). With none:

- `run` / `retest` use the environment marked **default**, whatever its kind — normally the `local`
  one. A contract with no `local` environment must mark a `shared` one default; a bare `run` then
  targets it, pre-write confirmation included.
- `status` / `report` / `note` use **the environment of the most recent run** in `qa-runs.md` (the
  default if there is none) — so `run --env staging` followed by a bare `report` reports staging.
  **A run header that names no environment** (a `qa-runs.md` written before environments existed)
  **is a run on the default environment.**

Always state which environment was selected, and how. Every surface URL, preflight check,
build-identity check, reset step, credential and drift note then comes from **that** environment's
block in `.anantys/qa.md`.

**A `.anantys/qa.md` with no `## Environment:` blocks** (written by an earlier `init`: flat
`## Surfaces` / `## Preflight` / `## Reset` / `## Credentials` sections) **is a single `local`
environment named `local`, and it is the default** — run it exactly as before, reset included.
`--env <other>` against such a file is an error: stop and tell the operator to re-run `init`, which
migrates the file before declaring the new environment (see `reference/init.md`). Never guess an
environment's kind; an env whose kind you cannot establish is not run.

## Results are per environment

An assertion can pass on one environment and fail on another (a fix deployed to staging but not the
local stack, or the reverse):

- Every `qa-runs.md` run header names its environment (`templates/qa-plan.md`).
- The per-assertion status in `qa-plan.md` is recorded **per environment** (`local: FAIL ·
  staging: PASS`) — the suffix is the authoritative record, required on every assertion that has
  run anywhere; the checkbox is checked only when every declared environment is PASS. A run
  updates only the selected environment's status, never another's.
- `retest`, `status` and `report` read only the results recorded for the selected environment and
  say which environment they describe. `status` and `report` also name every other environment
  that has results, so a defect recorded elsewhere is never silently out of view.
- **Adjudications are scoped too** (see `reference/reporting.md`): most are drift rulings, and
  drift is per-environment. A ruling applies only to its own environment, or to all of them when
  scoped `all`.

Testing a shipped feature on `staging` is often easier than reproducing its data locally —
but the `shared` rules above are not optional, because the blast radius of a reset or a stray write
there is real data, not a fixture.
