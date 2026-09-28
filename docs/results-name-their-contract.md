# A recorded result must name the rules that scored it

A QA result is not a fact. It is a claim, and the claim has four axes:

| axis | pinned where | re-checked by |
|---|---|---|
| the requirement | the assertion's `(FR-0xx)` citation | the plan's regeneration rule |
| the code | `**Under test:** <branch> @ <commit>` | `run` step 1, against the env's build identity |
| the environment | each result's `` `<env>`: `` suffix | written per environment, never merged |
| **the rules that scored it** | **nowhere** | **nothing** |

The fourth axis is the one this page adds. `PASS` is not a primitive — it is whatever the contract in
force at the time said it was. So is the boundary between a defect and a blocker, the authority an
adjudication annotation carries, and the condition under which a green retest closes a defect rather
than merely failing to reproduce it.

## Why the omission is silent rather than loud

The three pinned axes all fail **loudly**. A plan whose `Under test:` line does not match the
deployed build stops `run` before it walks a single scenario. A result carries its environment in its
own suffix, so it cannot be read as another environment's. A requirement change invalidates the
assertion that cites it.

The fourth fails **quietly**, and in the one direction that matters: the reader applies today's rules
to yesterday's statuses and gets a well-formed answer. `status` ends with a single sentence answering
"can this ship?" — computed from a table of statuses, some of which may have been scored under rules
that have since changed. Nothing in the artifact lets it notice.

This repo is the worked example. A queue of open changes redefines, among other things, what closes
an intermittent defect, what the coverage denominator counts, and what a regeneration must preserve.
Every `qa-plan.md` already committed in an operator's repo was written under the rules that preceded
them. After they land, those files are indistinguishable from files written after.

## The rule

`qa-plan.md` carries a `**Recorded under:**` header naming the plugin version whose rules produced
the statuses below it. `qa-runs.md` carries the same value per run header.

Three properties make it cheap:

1. **`plan` preserves it, never refreshes it.** It joins the fields a regeneration already carries
   forward — ids, adjudication annotations, per-environment suffixes, `REMOVED` strike-throughs.
   Restamping a preserved status is worse than not stamping it: it asserts the new rules scored
   results they never saw.
2. **The reader declares, it does not act.** `status` and `report` name the mismatch in the ship
   sentence. `run` does not block on it.
3. **The run log needs no preservation rule at all.** A run's results are scored as they are written,
   so the header's version is exact by construction.

## Where the value comes from, and what it is when it cannot be got

A provenance field is only as good as its source, and a role has no privileged knowledge of its own
version. Nothing in this plugin — not one skill, not one agent — tells a role where to find it.
Left unsaid, `v<running plugin version>` resolves the way every unsourced placeholder resolves: from
recall. A recalled version is the one the model was trained on, not the one scoring this campaign,
and it is wrong in the one direction that defeats the stamp — it is *plausible*, so it matches.

So the source is named: the `version` field of the running plugin's `.claude-plugin/plugin.json`.
Read, never recalled. That file is the same scalar `check_version_bump.py` gates, which is what makes
the stamp worth trusting at all — the value moves because a checker forces it to, not because a role
remembered to.

The second half is the absence. A read can fail — the plugin installed by a path this role cannot
reach, a truncated manifest, a sandbox that denies it. The failure must not be free to ignore:

| what a run writes | how a reader must take it |
|---|---|
| a version read from the manifest | compare against the running version |
| `unknown` | **a mismatch** — declare it exactly as a real one |
| no `Recorded under:` line at all | a plan written before this rule; same declaration |

`unknown` never matches any version, including another `unknown`. This is the asymmetry that makes
the mechanism honest: the states are *these results were scored under a named contract* and *nobody
knows what scored these results*, and the second is the pre-stamp state this page exists to end.
Omitting the line on a failed read, or filling it with a guess, collapses the second into the first —
a stamp whose failure mode is silence restores the gap it was added to close, while looking like it
closed it.

This is the same shape as `BLOCKED` in the run itself, and it resolves the same way. A case the run
could not reach is never `PASS`; a version the run could not read is never a match.

## What this deliberately does not do

**It does not invalidate on mismatch.** The plugin version bumps on every content change, including
one that touches no scoring rule. Invalidating a mismatched plan would discard every campaign in the
repo the first time someone fixes a typo in an unrelated role — a freshness gate on a shared scalar,
paid for by everyone. Declaring is the honest minimum; the version is a *pointer to a question*, not
an answer.

**It does not add a second, finer version number** tracking the scoring vocabulary alone. That would
be precise enough to invalidate on, and hand-maintained with no gate — a fourth copy of a fact no
checker owns. Revisit if a change ever needs to invalidate rather than declare: the stamp is the
prerequisite for naming a threshold, and nothing can name one until results carry a version at all.

**It does not stamp the other roles' artifacts.** `anantys.qa` is the only role on `main` whose
durable output is a *scored verdict* read back as truth by a later invocation. It is not the only one
in the queue: the open work that gives `anantys.ops` a ruling outliving its run, and a later audit
that scores the recommendation an earlier one made, gives `ops` an artifact of exactly this kind.
When that lands, `.anantys/ops/current.md` needs the header and this section's absence rule with it —
the mechanism is the role-independent half, and it transfers unchanged.
