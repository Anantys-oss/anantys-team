# `note`, `report`, `status` — adjudication and hand-off

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
for all environments (see "Progress table" in `${CLAUDE_SKILL_DIR}/SKILL.md`).

### `--durable` — a drift ruling outlives the feature that found it

`qa-plan.md` is **per feature**. Both existing scopes are environment axes, so a drift ruling —
"this env's sandbox key prices differently", "this env never sends mail" — is a property of the
environment that happens to have been discovered by one campaign, and it dies with that campaign's
directory. The next feature's first run re-files it as a defect, which is precisely the
re-diagnosis this action exists to prevent.

`--durable` therefore also appends the ruling to the **`### Known drift`** list of each environment
in its scope in `.anantys/qa.md` (`--env <name>` → that block; `--env all` → every block; a flat
legacy file is the one `local` environment, see `${CLAUDE_SKILL_DIR}/reference/environments.md`), after the assertion annotation is
written — creating the section if that block has none. Promoted entries carry their origin, so a
later reader can retire one when the drift is fixed:

```markdown
### Known drift — never file these as defects
- Checkout price does not match the grid — sandbox key drift, not a product defect. A real failure
  is a mismatch in **plan or period**. _(promoted 2026-08-03 from `sku-231` A4)_
```

Three limits:

- **Only drift is promotable.** Intended behaviour and a REMOVED strike-through are rulings about
  *this* product's behaviour; they narrow one assertion and belong to its plan. `--env all` on
  such a ruling means "on every environment", never "for every feature" — reject `--durable` on
  it and say why.
- **Never promote without the flag.** Without `--durable`, apply the ruling to the plan, then say
  in one line that it is feature-scoped and give the `note … --durable` call that would widen it.
  Widening is the operator's call, exactly as it is for `--env all`.
- **`.anantys/qa.md` is committed and holds no secrets.** A promoted entry carries the observed
  behaviour and the reason — never a credential, a token, or a URL with one in it.

A ruling that reaches the contract is read back by **two** places: `run`'s adjudication check
(see Judging rules in `${CLAUDE_SKILL_DIR}/reference/run.md`), and the next `init`, which keeps every promoted entry when it updates an
environment block.

## `report` — the fix brief

Select the environment first (`--env <name>`, else the most recent run's — see `${CLAUDE_SKILL_DIR}/reference/environments.md`) and
name it at the top of the report. Write `qa-report.md` **following `${CLAUDE_SKILL_DIR}/templates/qa-report.md`** —
the brief has its own shape, and it is not the run table the plan's §5 shows — addressed to a
**dev agent in a fresh session** that has the spec context but not yours. For each open defect:

- **Assertion id and what the spec requires** (with its requirement id).
- **What you observed** — exact copy, URL, console/network error.
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

"Open defect" here means open on **any** environment, not only the selected one (see `${CLAUDE_SKILL_DIR}/reference/environments.md`):
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

---
