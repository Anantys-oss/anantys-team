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

## The loader prices `SKILL.md`, and nothing else

Ask it rather than estimating. `claude plugin install` into a throwaway `HOME`, then
`claude plugin details anantys-team-agents`, prints an `on-invoke` column per component.
Against 2.1.278 that column is linear in the role's `SKILL.md` line count at ~17 tok/line,
and `templates/` and `reference/` cost nothing until something reads them:

| tree | `anantys.qa` `SKILL.md` | on-invoke | whole plugin |
|---|---|---|---|
| before the split | 513 lines | ~8.6k | ~16.6k |
| after the split | 125 lines | ~1.9k | ~9.9k |

The always-on budget does not move — ~716 tok either way. It prices descriptions, so a
split neither helps nor hurts it. The number a split moves is on-invoke, and only that.

## A split needs a router

The ~200-line threshold is a prompt to look, never the reason. What a split actually buys
is the part of the body an invocation **does not read**, so the saving exists only where
something chooses: `anantys.qa` dispatches seven actions, and each one loads one of five
reference files. A role that runs its body top to bottom has no such part.

`anantys.ops` is the counter-example. Six phases, every run walks all of them. Carving the
phases into `reference/` would cut its reported on-invoke by more than half and change what
a run costs by nothing — the phases are read a moment later, off the loader's meter. The
column measures `SKILL.md`; optimising against it directly is measuring the ruler.

So the order is fixed: give the role a router first, or leave the file long. A long role
with no branches is a design question — does it need actions? — and splitting it answers
the question by hiding it.
