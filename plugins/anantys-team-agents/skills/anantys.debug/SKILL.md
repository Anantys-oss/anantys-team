---
name: anantys.debug
description: Debug by observing the running app, not by guessing — a tight reproduce → inspect runtime (browser console, network, logs) → fix → re-prove loop. The proof is the observed behavior, never a plausible-looking diff. Use to diagnose and fix a bug where you can exercise the app live (a "Ralf loop").
allowed-tools: mcp__claude-in-chrome__tabs_context_mcp, mcp__claude-in-chrome__tabs_create_mcp, mcp__claude-in-chrome__navigate, mcp__claude-in-chrome__computer, mcp__claude-in-chrome__read_page, mcp__claude-in-chrome__javascript_tool, mcp__claude-in-chrome__read_console_messages, Read, Write, Edit, Bash, Glob, Grep, TaskCreate, TaskUpdate, TaskList
---

## Mission

You fix bugs by **closing the feedback loop with the running system**. The cycle: reproduce the bug live, read the *actual* runtime signals (console errors, network responses, server logs, computed state), form a hypothesis, fix it in the source, then **re-run and observe** that the behavior changed. Observed behavior is the only proof. A diff that "should" fix it is a hypothesis, not a result.

This is a **Ralf loop** — the model's limit is rarely the model; it's the feedback it receives. Your value is wiring that feedback tight: the app's own runtime tells you what's wrong and whether you fixed it.

## Hard preconditions

1. **A way to exercise the app live.** For web bugs, call `mcp__claude-in-chrome__tabs_context_mcp` first; if the browser tools aren't available, STOP and say so. For non-browser bugs, confirm you can run the failing path (a command, a test, a request) and read its output/logs.
2. **A concrete repro.** Get the exact steps, URL, input, or failing test from the user. If you can't reproduce it, say so and gather more signal — never "fix" a bug you haven't seen fail.
3. **A known tree state — because you will need to undo.** You edit source files and this loop can
   end UNRESOLVED (step 4b), which obliges you to leave the tree as you found it. You cannot undo to
   a state you never recorded. Before the first edit, run `git status --porcelain` and
   `git branch --show-current`, and **report both to the user**:
   - **Modified tracked files** (` M`, `M `, `A `) — the changes are the user's, not yours. STOP and
     ask them to commit or stash. Do not start and do not stash for them: after three of your own
     edits, nothing distinguishes their line from yours, and an undo that reverts a whole file
     destroys work you never saw.
   - **Untracked files** (`??`) — not the same risk, and not a reason to stop. Your undo is
     `git checkout --`, which cannot touch a path git does not know; a stray note or build artifact
     is in no danger from it. **List them by path in the snapshot you report** and continue. They are
     the entries you must still see at the end — proof you removed only your own.
   - **Unexpected branch** — the checkout is ambient state you did not set. A previous session may
     have left it on a review branch or a feature branch. Name the branch and confirm it is where
     the fix belongs before editing; a verified fix on the wrong branch is not a delivered fix.

   The snapshot has two halves because the undo does. `git checkout -- <files you touched>` restores
   **tracked** files; a file *you created* is untracked, so that command fails on it
   (`error: pathspec '<path>' did not match any file(s) known to git`) and the file survives. Record
   edits and creations separately as you go, and undo each with its own command: `git checkout --`
   for the edits, `rm` for the creations, by path. **Never `git clean`** — it does not distinguish
   your `??` entries from the ones you listed on entry.

## Workflow

### 1. Reproduce first

- Drive the app to the failing state (navigate + interact, or run the failing command/test).
- **Capture the failure signal** before touching anything: `read_console_messages` for JS errors, the network response for a bad call, the server log line, the assertion diff, a screenshot. This is your baseline — you'll compare against it.
- If it doesn't reproduce, stop and widen the net (env, data, timing) rather than guessing at a fix.

### 2. Locate by evidence, not assumption

- Follow the captured signal to its source: the stack trace's top frame, the failing request's handler, the log's emitting line. `Grep` for the error string / symbol.
- Read the actual runtime state at the failure point (`javascript_tool` to inspect variables/DOM/computed values; a log line; a breakpoint-style print). Confirm *why* it fails — don't pattern-match a fix onto a symptom.

### 3. Fix in the source, minimally

- One hypothesis at a time. Edit the **source files**, smallest change that addresses the root cause (not the symptom). Match surrounding style; reuse existing utilities.
- State the hypothesis explicitly before applying: "the bug is X because <evidence>; this change should make <observable> become <expected>."

### 4. Re-prove by observation

- **Reload / re-run the exact repro path.** A normal reload re-fetches your changes.
- Observe the same signal you captured in step 1: the console error is gone, the network call returns 200, the log shows the right value, the test passes, the screenshot is correct.
- **Not resolved? Revert that hypothesis, then iterate** — `git checkout -- <the files it edited>`,
  `rm <the files it created>`, scoped to that hypothesis alone (precondition 3's two lists, kept
  per-hypothesis). Only then back to step 2 with the new signal. A rejected hypothesis was *rejected
  by observation*; leaving its edit in the tree makes every later re-proof an observation of the
  accumulation, so a signal that flips on hypothesis 3 may be flipping because 1 is still there — and
  step 3's statement ("**this change** should make <observable> become <expected>") is a claim about
  one edit, not a conjunction. Carrying rejected edits costs the verdict, not just the diff: it can
  make FIXED true and the reported root cause wrong.
- Do NOT mark fixed on a plausible diff. Wrong hypotheses are normal; an unverified "fix" is not allowed.

### 4b. Stop when the loop stops learning

Iteration is bounded, and **UNRESOLVED is a result** — the third verdict alongside fixed and
still-iterating. Without it, a loop with no exit has only one pressure valve left: relaxing what
counts as proof. That is the one rule this skill cannot afford to lose.

Declare UNRESOLVED and hand back when **either** holds:

- **Three consecutive hypotheses rejected by observation** with no new signal — you are guessing, not
  narrowing. A fourth guess against the same evidence is a lottery ticket.
- **The next hypothesis needs something you don't have** — a permission, a service you must not
  start, a repro that only happens in an environment you cannot drive, a code path behind a flag you
  cannot set. Name it; do not work around it.

Handing back is not failure — it is the honest version of the same evidence trail. Report the
rejected hypotheses and *what observation killed each one*; that is the expensive part and the next
agent (or the human) should not pay for it twice. Then **restore the tree to the state precondition
3 recorded** — `git checkout -- <the files you edited>`, `rm <the files you created>`, and
`git status --porcelain` back to the snapshot you reported: empty of your edits, still carrying the
`??` entries that were there before you. Not *empty* — a run that reports an empty porcelain in a
tree that started with untracked files deleted something that was not its to delete.
An UNRESOLVED handoff that also ships four dead edits is worse than no attempt. If step 4 reverted
each rejected hypothesis as it was rejected, only the current one is left to undo here — and that is
the point: this restore is the loop's last check, not its only one.
(That is the *tree*'s starting state. The word "baseline" in step 1 means the failure signal you
captured, which you keep — it is the evidence.)

### 5. Guard against regressions

- Once observed-fixed, add or point to a test that would have caught it (or note why one isn't feasible).
- Quickly check adjacent paths the fix could affect.

## Report

End with the evidence trail:

```
| Stage | Signal observed |
|-------|-----------------|
| Repro (before) | <error / bad value / failing assertion> |
| Root cause | <file:line — why it failed> |
| Fix | <files changed, one-line intent> |
| Re-proof (after) | <console clean / 200 / right value / test green> |
| Verdict | FIXED (observed) — or UNRESOLVED, + what is missing to go further |
```

An UNRESOLVED report keeps the same table: the Repro row still holds, Root cause says how far you
got, Fix is empty, and Re-proof lists each hypothesis with the observation that rejected it.

## Rules

- **The proof is the observation**, never the diff. Reload and look before claiming a fix.
- **Reproduce before fixing**; if you can't see it fail, you can't confirm it's fixed.
- **Root cause over symptom** — read the runtime state, don't pattern-match.
- One hypothesis per iteration; wrong ones are expected, unverified ones are not.
- **UNRESOLVED is a result, not a failure** — three rejected hypotheses with no new signal, or a
  blocker you must not work around, ends the loop. Never buy an exit by lowering the bar for proof.
- **A rejected hypothesis is reverted where it was rejected** — in step 4, before the next one, not
  only at 4b. The success path is the one that accumulates: UNRESOLVED restores the tree, FIXED ships
  it, and this role never commits, so no diff boundary tells the fix from the debris. Worse, the proof
  here *is* an observation over the tree, so a retained rejected edit can carry the verdict and
  misattribute the root cause.
- **Record the tree before you edit it, and say where you are.** Clean tree, named branch, both
  reported. A loop that may have to undo cannot start from a state it did not read, and a fix
  verified on a branch nobody chose is not delivered.
- **"Dirty" means modified tracked files; untracked ones you list and keep.** The undo is two
  commands because the snapshot is two classes — `git checkout --` for what you edited, `rm` for
  what you created. `git checkout --` cannot remove a file you created, and `git clean` cannot
  spare the user's.
- **Never commit, push, or open a PR** unless the user explicitly asks — stop at the verified local fix.
