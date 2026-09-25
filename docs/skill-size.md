# Skill size

A `SKILL.md` is loaded **in full on every invocation**, so it costs context even for the
action that needs none of it. Past ~200 lines, split it: keep the mission, the action
router and the invariants in `SKILL.md`, and move each action's procedure into
`reference/<topic>.md`, named in a **Read first** column of the actions table. `anantys.qa`
is the worked example — it reached 513 lines before the split.
