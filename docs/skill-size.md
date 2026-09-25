# Skill size

A `SKILL.md` is loaded **in full on every invocation**, so it costs context even for the
action that needs none of it. Past ~200 lines, split it: keep the mission, the action
router and the invariants in `SKILL.md`, and move each action's procedure into
`reference/<topic>.md`, named in a **Read first** column of the actions table. `anantys.qa`
is the worked example — it reached 513 lines before the split.

## What may move, and what may not

The router reads **one** reference file per invocation, so a rule written in one is a rule the
other actions never see. That makes the split a way to lose a guard, not just context:
`anantys.qa` moved "never read `.env` values into the transcript" into `reference/init.md`, and
`run` — which captures a URL and a console error out of a signed-in browser — stopped being bound
by it.

The test is **who the rule binds**, not which action happens to mention it:

- **Binds every action → `SKILL.md`.** It stays loaded, so it cannot be skipped.
- **Binds one action → that action's reference file.** This is the whole point of the split.
- **Binds some but not all → a reference file that declares its own readers**, and every action it
  binds names it as a Read-first. `reference/environments.md` is the worked example: its first line
  is "Read this before any action that reads or writes results — `run`, `retest`, `note`, `status`,
  `report` — and before `init`."

A rule with one home does not need a copy in `SKILL.md` *and* the reference file. Point at it
instead — a rule restated in two places drifts into two rules.
