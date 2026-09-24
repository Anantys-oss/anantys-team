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
3. **A recorded baseline of the working tree.** Run `git status --porcelain` and keep the result. Everything dirty at that moment belongs to the human, not to you: you never revert it, never stage it, never describe it as part of your fix. If the tree is already dirty, say which files are pre-existing before you touch anything — after your first edit, nothing can tell the two apart.

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
- **Not resolved? Revert, then iterate.** `git checkout -- <the files you edited in step 3>` (baseline files excluded — see preconditions) *before* returning to step 2 with the new signal. A rejected hypothesis that stays in the tree is no longer a hypothesis; it is an unexplained change riding along with the real fix, and the next re-proof measures the pile rather than the one edit. "One hypothesis at a time" is a rule about what is *present* in the tree, not only about what you add to it.
- Do NOT mark fixed on a plausible diff. Wrong hypotheses are normal; an unverified "fix" is not allowed.

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
```

Then hand off the tree explicitly. List **the files you own** — `git status --porcelain` now, minus the baseline you recorded before starting — so the human can stage exactly that set and nothing else. If any of your edits could not be reverted cleanly, or a dead attempt survived, say so here by name. You leave uncommitted work behind on purpose; an unlabelled dirty tree is not a deliverable, it is a puzzle.

## Rules

- **The proof is the observation**, never the diff. Reload and look before claiming a fix.
- **Reproduce before fixing**; if you can't see it fail, you can't confirm it's fixed.
- **Root cause over symptom** — read the runtime state, don't pattern-match.
- One hypothesis per iteration; wrong ones are expected, unverified ones are not. **Revert a rejected hypothesis before trying the next** — the tree holds one live hypothesis, never a stack of them.
- **Own your diff.** You may only revert, stage, or report files you yourself edited after the recorded baseline. The human's pre-existing dirty state is untouchable.
- **Never commit, push, or open a PR** unless the user explicitly asks — stop at the verified local fix, and name the files that fix consists of.
