# A recorded result must name what it is a claim about

A QA result is not a fact. It is a claim, and the claim has five axes:

| axis | pinned where | re-checked by |
|---|---|---|
| the requirement | the assertion's `(FR-0xx)` citation | the plan's regeneration rule |
| the code | `**Under test:** <branch> @ <commit>` | `run` step 1, against the env's build identity |
| the environment | each result's `` `<env>`: `` suffix | written per environment, never merged |
| **the rules that scored it** | `**Recorded under:** v<version>` | `status` / `report` declare a mismatch |
| **the subject it was exercised as** | `**Exercised as:** <class>` | the suffix key, which a run may not widen |

The last two are what this page adds. `PASS` is not a primitive — it is whatever the contract in
force at the time said it was. So is the boundary between a defect and a blocker, the authority an
adjudication annotation carries, and the condition under which a green retest closes a defect rather
than merely failing to reproduce it. And it is not a verdict on the product either: it is a verdict
on what *one* subject could reach.

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

## The fifth axis is already observed — it is just written where nothing scores from it

The version axis was missing. The subject axis is not: `qa-runs.md`'s run header has always carried
`Subject: <account/fixture id>`, and `reference/run.md` step 1 tells a run to record the observed
build **"beside `Subject:`"**. The two values sit on the same line of the same header. One of them
is also pinned in the plan as `**Under test:**` and re-checked before a single scenario is walked;
the other is pinned nowhere and re-checked by nothing. An axis recorded only in the append-only log
can be read afterwards, but it cannot invalidate anything, because nothing is keyed on it.

And the result is keyed on the environment alone — `run` step 6 writes "for the selected
environment only", and the plan says a run "rewrites only its own environment's entry". So run 3 as
an owner and run 4 as a member write the same slot, and the second silently replaces the first.

**The environment is not a proxy for the subject.** Each environment block in `qa-config.md` has
its own `### Credentials` section, and that section is a *list* — `- <account>: <identifier>`. One
environment, several subjects, one key. A product whose behaviour does not depend on who is asking
has no fifth axis to pin; the moment it has roles, the suffix is ambiguous.

**Why a class and not the identifier.** The one place in the whole plugin that acknowledges this
axis exists is the redaction contract, which notes a run is "signed in as somebody" in order to
scrub the credential on the way out. That is correct, and it is why `**Exercised as:**` takes
`owner` / `member` / `anonymous` rather than an account: the permission level is the thing the
result varies over, and unlike the identifier it is not a secret. Redaction closed the accidental
channel; it did not open a deliberate one.

**Why it keys rather than declares.** The version axis fails by *staleness* — old results, current
rules, a well-formed but dated answer — so declaring the mismatch is the honest minimum. This one
fails by *falsification*: a member's FAIL written into an owner's slot is not a dated record, it is
a wrong one, and §3's Money, Legal and Data blockers are precisely the classes whose behaviour *is*
the permission. "Consent recorded before the product is delivered", verified as an owner, says
nothing about the account that cannot reach the consent screen. A run that cannot key its result
does not get to overwrite someone else's: it adds the key, or it records `BLOCKED`.

The adjudication annotation carries the same scope for the same reason. It was already scoped by
environment — `env: <name> | all` — because a ruling about a local quirk is not a ruling about
staging. A ruling is equally a judgement about one subject: "not a defect, the button is hidden
here" is true for the account that may not press it and false for the one that may. So the
annotation gains `as: <class> | all`, and an unscoped ruling is written `all` deliberately rather
than by omission — the default a blank leaves behind is the widest one, applied to runs the
operator never saw.

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

**It does not make every campaign enumerate subject classes.** Most products have one, and then
`**Exercised as:**` is a single value and the suffix is unchanged — the second key appears only
when the line declares more than one class, which is the same condition under which the suffix was
already ambiguous. A campaign that names one class has not claimed the others were tested; it has
said which claim it is making, which is the whole of the rule.

**It does not restate the key in `qa-runs.md`'s run header.** That header already records
`Subject:`, and its rows are scored as they are written — the same reason the version stamp needs
no preservation rule there. What was missing was never the observation; it was a *key* on the
artifact a later reader treats as truth. Aligning the run header's `Subject:` to name the class as
well as the id is a one-line follow-up, left out here only because that line is being rewritten by
the open work on what a run creates in a shared environment.
