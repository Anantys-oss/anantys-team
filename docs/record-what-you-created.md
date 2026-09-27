# Record what you created, not only what you observed

Every artifact this plugin writes is a record of an **observation**: an assertion's result, a KPI
row, a finding, a verdict. None of them was a record of a **write** — and one role in the team is
explicitly authorised to write to a live system:

> `/anantys.qa` on a `shared` env (staging, a preview, production) never resets, so a test subject
> is created **additively** — a new record, a new account, a new run.

The write was announced and then forgotten. `run` step 1 echoes "the scenarios that will create
data there" to the operator and waits for an explicit go. That enumeration exists, in the right
shape, at exactly the right moment — and is discarded the instant consent is given. The consent is
spent in one prompt. The data persists for as long as the environment does.

Three things break once the footprint is unrecorded:

- **Nobody can clean up.** `qa-runs.md` recorded `Subject:` — one id, a `local`/fixture notion.
  Twenty runs against staging leave twenty footprints that no artifact names, so no operator can
  find them and no command can remove them.
- **The environment's precondition becomes self-satisfying.** Staging preflight S3 asks that the
  behaviour under test exist on a real record, because a shared env has no fixtures and a campaign
  against one with no such data can only report `BLOCKED`. Run 1 creates that record additively.
  Run 2's S3 now passes on run 1's leftovers — a check written to detect "this env has no such
  data" answered by our own writes, with no product change in between.
- **An existing rule loses its evidence.** The skill already says *"state you created yourself by
  re-walking a flow invalidates the result — a defect you caused is not a defect."* Within one run
  a walker can know that. Across runs it cannot, because nothing wrote it down. On a `shared` env,
  which is never reset, across-runs is the normal case.

So the remedy adds no new judgement, only a record:

> **A run that writes to an environment records what it wrote, where to find it, and how to remove
> it** — in the `qa-runs.md` run section, beside the results. It is the same list the run already
> echoed for consent. A precondition met by a row in any prior run's table is state the campaign
> created: `BLOCKED`, never PASS.

`local` answers this in three words ("the reset covers it"). `shared` cannot, which is the whole
point: the table is only load-bearing exactly where the blast radius is real data.

The general shape, for any role that acts outside the repo: **consent is per-run, a side effect is
not.** A gate that asks permission and keeps no record has protected the moment and nothing after
it.
