---
name: anantys.debug
description: Debug by observing the running app, not by guessing — a tight reproduce → inspect runtime (browser console, network, logs) → fix → re-prove loop. The proof is the observed behavior, never a plausible-looking diff. Use to diagnose and fix a bug where you can exercise the app live (a "Ralf loop").
allowed-tools: ToolSearch, mcp__claude-in-chrome__tabs_context_mcp, mcp__claude-in-chrome__tabs_create_mcp, mcp__claude-in-chrome__list_connected_browsers, mcp__claude-in-chrome__select_browser, mcp__claude-in-chrome__navigate, mcp__claude-in-chrome__computer, mcp__claude-in-chrome__read_page, mcp__claude-in-chrome__javascript_tool, mcp__claude-in-chrome__read_console_messages, mcp__claude-in-chrome__read_network_requests, mcp__Claude_in_Chrome, mcp__Claude_Browser, mcp__Claude_Preview, Read, Write, Edit, Bash, Glob, Grep, TaskCreate, TaskUpdate, TaskList
---

## Mission

You fix bugs by **closing the feedback loop with the running system**. The cycle: reproduce the bug live, read the *actual* runtime signals (console errors, network responses, server logs, computed state), form a hypothesis, fix it in the source, then **re-run and observe** that the behavior changed. Observed behavior is the only proof. A diff that "should" fix it is a hypothesis, not a result.

This is a **Ralf loop** — the model's limit is rarely the model; it's the feedback it receives. Your value is wiring that feedback tight: the app's own runtime tells you what's wrong and whether you fixed it.

## Hard preconditions

1. **A way to exercise the app live.** For web bugs, call `tabs_context_mcp` first. Three states look like "no browser" and are not: the toolset may be registered under **another server name** than `mcp__claude-in-chrome__` (resolve it first — see "Which browser server" — every name below is written with that prefix and must be rewritten with the one you resolved), the Chrome tools may be **deferred** in this session, and several browsers may be connected with none selected — `list_connected_browsers` + `select_browser` resolves the third. For the deferred case, load every tool this loop needs in **one** `ToolSearch` call, before the probe, not one tool at a time (each extra call is a wasted round-trip):

   ```text
   ToolSearch query: select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__list_connected_browsers,mcp__claude-in-chrome__select_browser,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__read_page,mcp__claude-in-chrome__javascript_tool,mcp__claude-in-chrome__read_console_messages,mcp__claude-in-chrome__read_network_requests
   ```

   Size the batch to the whole loop, not to the probe: `read_network_requests` is needed at step 4, long after the precondition passed, and discovering it missing there costs a second call. STOP and say so only when no browser is connected under any name. For non-browser bugs, confirm you can run the failing path (a command, a test, a request) and read its output/logs.
2. **A concrete repro.** Get the exact steps, URL, input, or failing test from the user. If you can't reproduce it, say so and gather more signal — never "fix" a bug you haven't seen fail.

## Which browser server

The same browser toolset is registered under several server names, so the absence of one
spelling is **not** the absence of a browser. Resolve which one this session exposes before the
probe, and use that prefix for every browser call — and inside every `ToolSearch select:` — that
follows:

| prefix | surface |
|---|---|
| `mcp__claude-in-chrome__` | the Chrome extension |
| `mcp__Claude_in_Chrome__` | the Cowork desktop server |
| `mcp__Claude_Browser__`, `mcp__Claude_Preview__` | the Claude Desktop pane (both names are live) |

A browser bridged from another machine through Claude Code Remote appears under
`mcp__remote-devices__…` and is deliberately **not** granted to this skill, which also carries
computer-use of that machine: report *that* rather than "no browser", and fall back to the
non-browser repro path.

## Workflow

### 1. Reproduce first

- Drive the app to the failing state (navigate + interact, or run the failing command/test).
- **Capture the failure signal** before touching anything: `read_console_messages` for JS errors, `read_network_requests` for a bad call's status and response, the server log line, the assertion diff, a screenshot (`computer` with `{"action": "screenshot"}` — there is no `screenshot` tool). This is your baseline — you'll compare against it.
- If it doesn't reproduce, stop and widen the net (env, data, timing) rather than guessing at a fix.

### 2. Locate by evidence, not assumption

- Follow the captured signal to its source: the stack trace's top frame, the failing request's handler, the log's emitting line. `Grep` for the error string / symbol.
- Read the actual runtime state at the failure point (`javascript_tool` to inspect variables/DOM/computed values; a log line; a breakpoint-style print). Confirm *why* it fails — don't pattern-match a fix onto a symptom.

### 3. Fix in the source, minimally

- One hypothesis at a time. Edit the **source files**, smallest change that addresses the root cause (not the symptom). Match surrounding style; reuse existing utilities.
- State the hypothesis explicitly before applying: "the bug is X because <evidence>; this change should make <observable> become <expected>."

### 4. Re-prove by observation

- **Reload / re-run the exact repro path.** A normal reload re-fetches your changes.
- Observe the same signal you captured in step 1 **with the same tool**: the console error is gone, `read_network_requests` shows the call returning 200, the log shows the right value, the test passes, the screenshot is correct. `read_network_requests` clears on cross-domain navigation — re-read it after the reload, not before.
- **Not resolved? Iterate** — back to step 2 with the new signal. Do NOT mark fixed on a plausible diff. Wrong hypotheses are normal; an unverified "fix" is not allowed.

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

## Rules

- **The proof is the observation**, never the diff. Reload and look before claiming a fix.
- **Reproduce before fixing**; if you can't see it fail, you can't confirm it's fixed.
- **Root cause over symptom** — read the runtime state, don't pattern-match.
- One hypothesis per iteration; wrong ones are expected, unverified ones are not.
- **Never commit, push, or open a PR** unless the user explicitly asks — stop at the verified local fix.
