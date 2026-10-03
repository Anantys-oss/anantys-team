# Team contract

Rules that bind **every** role in this plugin — the skills under `skills/` and the
agents under `agents/`. Each role's own file carries only what is specific to it.

Every role file points here. Read this before acting.

---

## C1 — Observation over inference

**Report what you actually observed. Never what you expected, assumed, or inferred.**

- A result you did not see is not a result. Name it as unreached, unverified, or
  blocked — never fold it into a pass.
- A change you did not exercise is a hypothesis, not a fix. The proof is the
  observation: the reload, the screenshot, the console line, the test run, the
  dashboard number.
- Where you are uncertain, say so at the point of the claim. A flagged uncertainty
  is a finding; a smoothed-over one is a defect you shipped.
- Never invent a value to fill a gap.

Every role in this plugin had derived this for itself, in its own words, at its own
strength — seven files, seven phrasings, no two the same. Divergent statements of
one invariant drift apart silently, and one of them is always the weakest. It is
stated once here so there is nothing to drift from.

---

## C2 — A stop is a result

**A run that stops before it finishes records the stop where its result would have gone.**

C1 governs a result you did not observe; this governs the run you did not finish. Every
role here gates — no browser, a dirty tree, consent withheld, a precondition you must not
work around. Stopping there is correct. Stopping there *silently* is not.

- **Name the stop as the verdict**, with the gate that fired and what passing it needs.
- **Write that into the artifact a finished run would have written** — once you know where
  that artifact is and what it already says. A file a stopped run left untouched is
  byte-identical to one a finished run had no reason to change, and the next reader — often
  the next run — cannot tell those apart. An append-only log gains a stopped entry; a
  snapshot *you have read* gains a dated line saying no run refreshed it. A snapshot you
  have **not** read is not amended but rewritten whole from its own prior content, so a stop
  that fires before that read records the stop in the reply and names the file it could not
  reach. Rewriting a snapshot blind destroys the history this clause exists to preserve.
- **Recording the stop publishes nothing else** — not the partial result as a whole one.

A missing record is not a smaller failure than a wrong one. It is the same failure with
nobody looking for it.

---

## What belongs here

A rule belongs in this file when it binds **three or more roles** and is not
specific to any of them. Below that threshold it stays inline, in the role that
needs it.

Amending a shared rule is then one edit to this file — not one edit per role, in
N phrasings, each free to land at a different strength.

**This is not enforced by CI, deliberately.** A gate whose only remedy is "edit this
file" puts every concurrent change on the same few lines and turns a parallel queue
into a serial one. The threshold is a review question: when a change would add the
same rule to a third role, it belongs here instead.

---

## What does not belong here

**This file is loaded before every action of every role.** All seven role files open
with *"the team contract binds you — read it before acting"*, so its length is a cost
charged to every invocation — the same cost the skill-size convention caps a `SKILL.md`
at, at ~200 lines, for the same reason. That cap is measured on `SKILL.md` alone, so this
file was never counted: `ops` invokes at 231 + 502 lines against a ceiling of 200, and the
checker reports 231. Making the measurement match the load is a change to
`scripts/check_plugins.py`, which this branch does not own; it lands on
`plugin-manifest-checks`, and until it does the bound below is a review question like the
threshold above.

That convention's test applies unchanged here: **who does the text bind?** Content that
binds every role stays. Content addressed to whoever *maintains* this file — an argument
for promoting a rule, a measurement that dates a citation, a conflict to resolve at
landing — binds no role and lives in `docs/team-contract-candidates.md`, which nothing
loads.

The distinction is not cosmetic, because a role cannot act on non-binding text by
choosing not to. This file carried 459 such lines against 43 binding ones: eleven
candidate rules, each one a finding written in the imperative (*"make the work durable,
then ask"*), several stating the opposite of the role file they describe, under a
heading that says *"a candidate does not bind"* — and, at the end, instructions for a
human resolving a rebase. A disclaimer in the middle of a file is not a boundary; the
file a role is told to read is.

**So: nothing enters this file that a role is not required to do.** Where a candidate and
a role file disagree, the role file governs — and a role blocked by that disagreement has
found the argument for promoting the candidate, which is a note for the operator, not a
side to pick.
