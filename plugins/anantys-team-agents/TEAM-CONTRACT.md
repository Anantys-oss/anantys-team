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

Nothing is in this file that a role is not required to do. Everything addressed to
whoever *edits* it — what is admitted here, what is not, and where a candidate rule goes
instead — is in `docs/team-contract-maintenance.md` in the source repository,
which no role loads.
