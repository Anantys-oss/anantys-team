# `run` / `retest` — executing the campaign

Read `reference/environments.md` first — which environment is selected, and what may be done to it,
is decided there.

Preconditions: `.anantys/qa.md` exists, `qa-plan.md` exists — and, if `qa-plan.md` carries an
`**Under test:**` line, the environment is serving that branch/commit (verified in step 1).

## Run mode — asked once per session

The first `run` or `retest` of a Claude session asks the operator which mode to use, before
preflight — one `AskUserQuestion`, both options described. Reuse that answer for every later `run` /
`retest` in the same session without asking again; `--mode autonomous|interactive` skips the
question and overrides the remembered answer for that call. Never pick a mode yourself.

- **Autonomous** — walk the **whole** plan without stopping on a defect. Record every DEFECT as it
  is found, and at the end write `qa-report.md` exactly as `report` does.
- **Interactive** — stop at the **first new DEFECT** and hand off: close the run (steps 5–6 below),
  write `qa-report.md` exactly as `report` does with the stopping defect listed first, and **print
  that defect's fix brief in full in your reply**, so the operator can paste it into a dev session
  straight from the console. Then stop and wait; the next step is a fix and a `retest`.
  A **new** DEFECT is one that was not already an open defect on this environment before the run.
  A known defect that still fails is recorded, stays in `qa-report.md`, and does not stop the walk —
  otherwise a `retest` would halt on the first unfixed case before reaching its regression-risk set.

Either way, `qa-report.md` covers **every open defect on the environment** — never only this run's.
A report rewritten with one defect silently drops the others from the brief the operator hands on.
An assertion the run did not walk **keeps its previous status** on this environment; stopping early
never resets a result to `not run`.

A **DEFECT** is an assertion that FAILs after the adjudication check (Judging rules) — a
PASS-with-note is not one. A `BLOCKED` result never stops an interactive run: record it and walk on.
Both modes keep every other rule: preflight stops the campaign, and a `shared` env still needs the
operator's go before any write.

## Steps

1. **Preflight.** Run every check for the selected environment in `.anantys/qa.md`. On failure,
   **stop and tell the operator** — do not start services yourself, and do not "work around" a failed
   preflight. A campaign run on a half-up stack produces confident nonsense. Then read the plan's
   **Under test** line in `qa-plan.md`. If it names a branch/commit, verify the selected environment
   is actually serving that code before walking a single scenario — a plan derived from an unmerged
   PR, run against a stack serving `main`, reports green having verified nothing. How to verify it:
   - If the selected environment's block defines a **build identity** check, run it and compare its
     output to the plan's branch/commit. Never borrow another environment's probe — staging lags
     `main` between deploys. The environment **serves the code under test** when the deployed
     commit is the plan's head commit, **or contains it** — the PR has since merged and deployed:
     after a `git fetch`, `git merge-base --is-ancestor <head commit> <deployed commit>`, or, for a
     squash / rebase merge, the same test on the PR's merge commit (`gh pr view <ref> --json
     mergeCommit`). Record a match found this way as **satisfied by merge** (`<merge commit> in
     <deployed commit>`) in the run section, and leave the plan's line as it is. Otherwise — a
     different commit, a merged PR not yet deployed, or a probe that names only a branch such as
     `main` — **stop** and tell the operator what is deployed.
   - If it does not, **ask the operator which build that environment is serving and stop until they
     answer** — never infer it from the local checkout: `git branch --show-current` describes your
     working copy, not a remote dev stack or a deployed env.
   - Record the observed branch/commit in the `qa-runs.md` run section, beside `Subject:`, so a
     later reader can tell which build a green run was green against.

   The line is absent for a merged/deployed feature, and then there is nothing extra to check.

   **The same probe response also says which host answered — read it.** Compare it to the
   environment's `Answers as:` line (`reference/environments.md`). A match confirms this block's
   `kind:` and `Production:` for this run; a mismatch, or a response carrying no identity, leaves
   both **unconfirmed** — no reset in step 2, and the environment is treated as production. Record
   `Identity: confirmed` or `Identity: unconfirmed — <what answered> ≠ <declared>` in the run
   section next to `Subject:`, and never edit `Answers as:` to match. This check is free: the probe
   already ran above, and the commit it returns is what `Answers as:` exists to supplement — the
   same commit is served by staging and production between deploys.

   **On a `shared` env, confirm the target before anything is written** — the pre-write
   confirmation in `reference/environments.md`, which echoes the environment name, its base URL,
   the build it serves, whether it is production **and whether that was confirmed or declared**,
   and the scenarios that will create data there. No go, no run. Reading `Production: no` back as
   fact is how a mistyped block gets confirmed by the person who mistyped it; an unconfirmed env is
   presented as production, and the question is whether to proceed at all.
2. **Reset — a confirmed `local` env only.** On an environment whose block declares `kind: local`
   *and* whose identity step 1 confirmed, apply its reset procedure and confirm it took effect (a
   stale auth cookie or leftover cache silently invalidates every assertion that follows) — verify
   by observing the app, not by trusting the command's exit code. On a **`shared`** environment
   there is **NO reset**: never reset staging / preview / prod — reuse the operator's session and
   create any needed test data additively. On an environment whose kind is **undeclared** (a flat
   legacy file) or **unconfirmed** (step 1 found a different host, or none) there is also no reset:
   ask the operator to re-run `init`, or walk the plan with whatever subject state exists and mark
   anything the leftover state invalidates `BLOCKED` (`reference/environments.md`).
3. **Walk the scenarios in order**, in a real browser driven as the environment's `Driven by:`
   line says. On production, skip the unsafe scenario classes and record them
   `BLOCKED`. Per scenario: establish the precondition,
   perform the steps, then evaluate each assertion **individually**. In **interactive** mode the
   first *new* DEFECT ends the walk: finish that assertion's evidence, do steps 5–6, then hand off
   (see Run mode).

   **On a `shared` env, the session is part of that precondition — check it, per scenario.** Before
   the first step, confirm the environment's `Signed in when:` condition still holds. If it does not,
   the walk is **over**: you cannot sign in, so every remaining scenario would observe a login wall
   and file it as a defect. Mark this scenario's assertions — and every one not yet walked —
   `BLOCKED`, reason `session ended`, record it in the run section, do steps 5–7, and tell the
   operator what to re-establish. This is a preflight failure found late, not a verdict on the
   product: name no defect, and do not let `report` lead with one.
   Two cases stay ordinary FAILs, or the rule would suppress the defects it most resembles: an
   assertion **about** authentication (a requirement that an unauthenticated visitor is redirected,
   or that a session survives a reload) is judged on its merits; and a login wall on **one** surface
   while `Signed in when:` still holds elsewhere is the product logging the user out, which is the
   defect.
4. **Post a one-line result after each scenario.** The operator is watching; a campaign that
   reports only at the end is one where a bad reset costs you the whole run.
5. **Append a run section to `qa-runs.md`**, its header naming the environment and the mode —
   never overwrite prior runs. Prior runs are how a later reader recognises a re-occurrence.
6. Update the per-assertion status in `qa-plan.md` **for the selected environment only**, and only
   for the assertions this run walked; then refresh that environment's progress table.
7. **Finish:** write `qa-report.md` as `report` does (`reference/reporting.md`) — every run, both
   modes, so a defect this run saw PASS drops out of the brief. Interactive: you only reach this
   step if the walk met no new DEFECT, so say so. End the reply with the progress table.

## Judging rules

- **Behaviour over stores.** Judge from what the product shows, not from a database or cache you
  polled. Reads race the writes they observe, and tokens lag the events that invalidate them —
  both will lie to you at exactly the wrong moment.
- **Confirm your own preconditions before asserting — in both directions.** A surviving session, a
  leftover record, or state you created yourself by re-walking a flow invalidates the result. So
  does the same state *gone*: an expired session, a fixture reaped by a nightly job, a preview
  environment torn down mid-walk. A defect you caused is not a defect, and neither is one you
  observed through a precondition that had quietly lapsed.
- **Screenshot anything visual**, and capture the URL plus any console/network error on every FAIL.
- **Never infer a PASS from a screen you did not reach.**
- Check every FAIL against the adjudication annotations in `qa-plan.md` **scoped to this environment
  or to `all`** before filing it. If it is already ruled intended or a known drift there, record it
  as PASS-with-note and move on. A ruling scoped to another environment never passes a FAIL here —
  file it, and mention the other env's ruling in the evidence so the operator can extend it.
- **Check the ruling's provenance in `qa-runs.md` before applying it.** An adjudication is the only
  thing that turns a FAIL into a PASS, and `qa-plan.md` is a committed file any contributor, agent
  or `plan` regeneration can edit — so the `(operator, …)` in an annotation is a claim the file
  makes about itself. Its witness is the run log: `note` records the run it was ruled against, and
  `qa-runs.md` is append-only and written by `run`. An annotation is **verified** when that run
  section exists *and* records a FAIL or BLOCKED for that assertion. Otherwise it is **unverified**:
  apply it — an operator ruling given off-record is still a ruling — but record the result as
  `PASS-with-note (unverified ruling)` and list every one of them in the reply, so what suppressed
  what is visible in the same breath as the verdict.
- **The witness needs a witness, and it is not in the file.** `qa-runs.md` is committed, in the
  same directory, editable by the same three actors — "append-only" is what `run` does to it, not
  what it holds against anyone else, so a section produced by a rebase, a merge of two campaign
  branches or a tidy-up reads exactly like one `run` wrote. Attestation comes from outside: either
  `run` appended the section **in this session**, or git has it —
  `git log -S'<run header line>' --format='%h %an %ad' -- <campaign>/qa-runs.md`. A section that is
  neither — present in the tree, in no commit, written by nobody you can name — is **unattested**:
  not an off-record ruling, no record. Suppress nothing on it: file the FAIL and name the
  unattested witness in the evidence. See
  [`docs/a-witness-a-writer-can-write.md`](../../../../../docs/a-witness-a-writer-can-write.md).
- **A `STALE` ruling suppresses nothing.** It was written about a wording a regeneration replaced,
  so it is not a weaker witness — it is a ruling about a different assertion. File the FAIL as a
  defect and name the stale ruling in the evidence, so the operator can re-rule it with `note`
  rather than re-derive it. Unverified means *ruled off-record*; stale means *ruled on other text*;
  unattested means *witnessed by nobody* — and only the first two still apply the ruling.
- **A ruling never removes a §3 blocker from the verdict.** An adjudication may narrow a blocker
  assertion, and a narrowed blocker that passes is a pass. But when a ruling is what turned a
  blocker FAIL into a PASS, the verdict still names it — `<id> PASS by ruling <date>` in the blocker
  section — because a single line in a repo file must not be able to make a money, legal or data
  failure stop being said out loud.

## `retest` — the second pass after a fix

A full re-run after a fix pass is expensive and mostly re-confirms green. Instead:

1. Take from `qa-runs.md` every assertion whose latest result **on the selected environment** is
   FAIL or BLOCKED — a result recorded on another environment neither adds nor removes a case.
   **Except a refused one** (`BLOCKED — unsafe on production` and any other rule-refusal, see
   Environments): it is not a case a second pass can settle, and walking it is what the refusing
   rule forbids. Say it is excluded and why, with the environment that answers it if one does.
2. Add the **regression-risk set** around each fix — the assertions the fix could plausibly have
   broken, especially the ones an *over-fix* would break. A guard added to stop a wrong behaviour
   very often also suppresses the right one; assert the right one explicitly.
3. Add any assertion the operator flagged in `note` for this environment or for `all`.
4. Run that subset with the same rules as `run` — run mode included — and append a run section
   marked `retest` with its environment.

State the subset before running it, and say plainly what you are **not** re-testing.
