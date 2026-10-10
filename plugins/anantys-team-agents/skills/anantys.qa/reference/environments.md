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
always driven by the operator's connected browser — its kind *derives* the line, which is a
declaration, not an absence. A **declared** env missing the line is not assumed to be: ask which
drives it, fold the question into the run-mode question below, and write the answer into
`.anantys/qa.md`. Never fall back to the operator's connected browser — it is the widest capability
this skill has, and a missing line is the one case where nobody chose to grant it.

**Production is a `shared` env with `Production: yes`**. A `shared` block with **no** `Production:`
line is treated as production until the operator says otherwise — being wrong that way costs a
handful of `BLOCKED` assertions, being wrong the other way charges a real card or emails a real
person. Production gets two extra guards:

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
environment named `local`, and it is the default** — its surfaces, preflight checks, credentials and
drift notes are read exactly as before. Its **kind is undeclared**, so its Reset block is **not
run**: the flat layout predates the `local`/`shared` distinction, nothing in it was written under a
rule that asked which kind it targets, and it carries neither a declared Target nor a probe to
compare one against. A campaign needing a fresh subject there asks the operator to re-run `init`
first. `--env <other>` against such a file is an error: stop and tell the operator to re-run `init`,
which migrates the file before declaring the new environment (see `reference/init.md`). Never guess
an environment's kind; an env whose kind you cannot establish is not reset and not run.

**An absent declaration is never a permission** — the general rule the three paragraphs above
apply, stated once in `templates/qa-config.md`. A field this skill gates an action on can be
missing: an older `init` wrote the file, a hand edit dropped a line, the operator skipped the
question. Missing resolves to the **narrower** branch, and a field whose absence would widen what an
action may do is asked, never inferred. Note which way the existing defaults already lean: the two
fields about *being able to verify* fail closed (no build-identity probe ⇒ ask and stop; no payment
instrument ⇒ every checkout case `BLOCKED`). The fields about *permission to act* are the ones to
watch, because their permissive branch reads like backward compatibility.

**And a present declaration is not an observation** — the complement, also stated once in
`templates/qa-config.md`. `kind:` and `Production:` are typed at `init` and read forever after as if
they described the host; they describe a URL, and the URL is what moves — a retired staging hostname
repointed at prod, a repointed dev box behind a `local` block (whose surface is *expected* not to be
`localhost`), a `shared` block copied with only the name changed. No field is missing in any of
those, so every rule above passes while the campaign resets real data or walks the money assertions
it was meant to `BLOCK`. Each environment therefore records an **`Answers as:`** line beside its
build-identity probe — an identity in the probe's own response, never the commit, since staging and
production serve the same commit right after a deploy — and `run` step 1 compares it, free, because
the probe already ran. No match, or no identity in the response, ⇒ `kind:`/`Production:`
**unconfirmed** ⇒ the narrower branch above: not reset, treated as production.

**And an observation is a measurement at a time, not a property of the run.** The two rules above
read a field once and compare it once, at step 1 — correct for `kind:` and `Production:`, which a
deploy changes between campaigns rather than during one. One precondition does not hold still:
on a `shared` env the whole campaign rides the **operator's signed-in browser session**, and the
agent may not sign in, so this is the only load-bearing precondition it can neither establish nor
repair. Sessions expire, and an autonomous walk is long. Past that point the product answers every
request with a login wall, "judge from what the product shows" reads it as the feature being gone,
and the run files consecutive FAILs — money and legal ones first, since those scenarios are ordered
first — against code that is fine. Nothing in the file is wrong and no probe disagrees; the
observation simply aged. So each `shared` env records a **`Signed in when:`** line — the cheapest
visible proof the session is still live — and `run` re-checks it per scenario (step 3), reporting
its loss as `BLOCKED`, which is what an unreachable case has always been.

## Results are per environment

An assertion can pass on one environment and fail on another (a fix deployed to staging but not the
local stack, or the reverse):

- Every `qa-runs.md` run header names its environment (`templates/qa-plan.md`).
- The per-assertion status in `qa-plan.md` is recorded **per environment** (`local: FAIL ·
  staging: PASS`) — the suffix is the authoritative record, required on every assertion that has
  run anywhere; the checkbox is checked only when every declared environment **it was permitted to
  run on** is PASS (see "a refusal is not a gap" below). A run updates only the selected
  environment's status, never another's.
- `retest`, `status` and `report` read only the results recorded for the selected environment and
  say which environment they describe. `status` and `report` also name every other environment
  that has results, so a defect recorded elsewhere is never silently out of view.
- **Adjudications are scoped too** (see `reference/reporting.md`): most are drift rulings, and
  drift is per-environment. A ruling applies only to its own environment, or to all of them when
  scoped `all`.

**But a brief is work, not evidence, and the work is not per environment.** The rules above scope
*results*, correctly: an observation belongs to the environment it was made on. `qa-report.md` is
not a result. It is the one artifact that leaves the campaign, addressed to a dev agent that has the
spec but neither the plan nor this session — and the code it asks for is the same code on every
environment. Yet the file is a **single slot, rewritten in full** by `report` and by step 7 of every
`run`. A campaign with open defects on two environments can therefore hand off only one of them: the
second write replaces the first brief, and the repro, blast radius and *what a fix must not break*
it carried survive nowhere — `qa-runs.md` keeps one line per defect, which is a record, not a brief.
Bullet three above makes that loss visible rather than silent, which is strictly better, but it
points the reader at a brief that no longer exists.

So **`qa-report.md` covers every environment that has an open defect**, selected environment first,
each defect naming the environments it was observed on, and one entry per product problem rather
than one per environment that saw it. *What a fix must not break* is then computed against the
assertions passing **anywhere** — a fix validated only against `staging`'s passing set can regress
an assertion that passes only on the local stack, and no per-environment rule above can see that.

**And a refusal is not a gap.** `BLOCKED` carries two things. A case the run *could not reach* — a
CAPTCHA, an emailed code, a torn-down preview — is untested, and reporting it as loudly as a FAIL is
right. A case this skill **refused to walk** is not: the production guard above `BLOCKED`s every
money, consent and notification assertion by construction, and those are exactly §3's Money and
Legal blockers. A production campaign that behaved perfectly therefore reports its whole blocker
list `BLOCKED`, every run, forever — and the `Production:`-is-missing rule above widens that to any
under-declared `shared` block. One status, two meanings, and the surfaces answering "can this ship?"
read the louder one. So record the reason and let the other environments answer it:

- Write a refused result as `BLOCKED — unsafe on production` (or the refusing rule's own reason).
  Its own environment can never resolve it; only another one can.
- It is a **coverage gap only when no environment has a PASS for it** — the cross-environment read
  `status` and `report` already do. Blocked on production, green on staging, is *verified
  elsewhere*; blocked on production and green nowhere is a real gap, and the loudest kind.
- It is **not retestable** (`retest` step 1): that is the one place the subset rule orders a walk
  another rule forbids.

`note` is the wrong repair — an adjudication records what the *operator* ruled about the product,
and this is the skill declining to act; re-typing it per assertion per campaign would dress a safety
guard as operator-approved drift.

Testing a shipped feature on `staging` is often easier than reproducing its data locally —
but the `shared` rules above are not optional, because the blast radius of a reset or a stray write
there is real data, not a fixture.
