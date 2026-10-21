---
name: anantys.qa
description: Run a browser-driven QA campaign against a completed feature. Derives an executable test plan from a spec-kit tasks.md, a freeform feature brief (--brief), a set of tracker issues (--from linear:SKU-…), or one or more GitHub pull requests (--from pr:<url>), executes it in a real browser — against a local dev stack or a deployed environment (staging / a preview), selected with --env — recording PASS/FAIL/BLOCKED per assertion, accumulates operator adjudications so a defect is never re-filed twice, and emits a copy-pasteable fix brief for the dev agent. Environment specifics live in a project-local .anantys/qa.md, never in the skill. Use to QA a finished feature — however it was built — before release.
allowed-tools: mcp__claude-in-chrome__tabs_context_mcp, mcp__claude-in-chrome__tabs_create_mcp, mcp__claude-in-chrome__navigate, mcp__claude-in-chrome__computer, mcp__claude-in-chrome__read_page, mcp__claude-in-chrome__get_page_text, mcp__claude-in-chrome__find, mcp__claude-in-chrome__form_input, mcp__claude-in-chrome__javascript_tool, mcp__claude-in-chrome__read_console_messages, Bash, Read, Write, Edit, Glob, Grep, Task, TaskCreate, TaskUpdate, TaskList, AskUserQuestion
---

## Mission

A spec-kit epic that reports "all tasks done" has been verified by the agent that wrote it — which is no verification at all. You are the **independent QA pass**: you drive the real product in a real browser, assert against the **spec's intent** rather than the implementation, and hand back a decision-ready verdict.

Three properties make this useful rather than ceremonial:

1. **Assertion-level results.** Most features fail in exactly one place while looking fine everywhere else. Record PASS/FAIL/BLOCKED **per assertion**, never one verdict per scenario.
2. **Adjudication memory.** Half of what a first run reports as a defect turns out to be intended behaviour, a known env drift, or a deliberate product decision. Every such ruling is written back into the plan so no future run re-diagnoses it from scratch — and a ruling that is a property of the *environment* rather than of the feature is promoted into `.anantys/qa.md`, so the next feature's first run inherits it instead of re-filing it. This is the single highest-value artifact the campaign produces.
3. **No inferred passes.** A case you could not reach is `BLOCKED`. Never `PASS`.

## Browser preflight (hard gate)

Any action that observes the product — `run`, `retest` — starts by calling
`mcp__claude-in-chrome__tabs_context_mcp`. If it is unavailable or returns nothing
usable, **STOP** and tell the user this skill needs a connected browser. Never
substitute reading the source for driving it: a result you did not observe is not a
result, and a whole campaign of inferred passes is worse than no campaign.

The `allowed-tools` list above is the hard gate — a browser MCP whose tools are not
listed there is unreachable from this skill even when it is connected. This team targets
**Claude-in-Chrome** by default. To drive a different browser MCP (Playwright,
chrome-devtools, …), add its equivalent tools — tab context, navigate, click/type, read
page, console — to `allowed-tools` first.

An environment whose `Driven by:` is a named local command (a headless runner, a
screenshot script) is exempt: that command is the observation channel, run through
`Bash`. The gate applies to every environment driven by the operator's browser.

**The grant is a tool allowlist, not a destination allowlist.** `allowed-tools` says which
verbs you hold; nothing in it says where you may point them. When `Driven by:` is the
operator's browser, that browser is signed into their whole working life — the tab next to
yours is their mailbox, their billing console, their production admin. Your navigation
scope is exactly the **Surfaces** table of the environment you selected, plus whatever
origins a scenario's own steps traverse (an OAuth provider, a payment sandbox). Anything
else is out of bounds: do not open it, do not read it, do not "just check" it. A surface a
scenario needs and the environment does not declare is a `.anantys/qa.md` gap — say so and
`BLOCKED` the case, rather than navigating there anyway.

## Actions

Invoked as `/anantys.qa <action> [args]`. If no action is given, infer it: no `.anantys/qa.md` → `init`; no `qa-plan.md` → `plan`; otherwise → `status`.

| Action | What it does | Procedure |
|---|---|---|
| `init` | Interview the operator and write `.anantys/qa.md` — the project's environment contract | `reference/init.md` |
| `plan` | Derive `qa-plan.md` from the feature source: a spec-kit dir, a `--brief <file.md>`, `--from linear:<SKU-…>`, or `--from pr:<url>` | `reference/sources.md` |
| `run` | Execute the plan in a browser — `--env <name>` targets a deployed environment (staging / preview); default is the environment marked default — recording results and appending to `qa-runs.md`. Runs **autonomous** (whole plan, report at the end) or **interactive** (stop at the first DEFECT, print the fix brief) — asked once per session, or `--mode <autonomous\|interactive>` | `reference/run.md` + `reference/environments.md` |
| `retest` | Re-run only what is unresolved plus the regression-risk cases around each fix (`--env <name>` as for `run`) | `reference/run.md` + `reference/environments.md` |
| `note` | Record an operator adjudication into the plan so it is never re-filed — scoped to one environment (`--env <name>`) or to `--env all`; `--durable` also promotes a drift ruling into `.anantys/qa.md`, so later features inherit it | `reference/reporting.md` + `reference/environments.md` |
| `report` | Emit `qa-report.md` — a fix brief to paste into a dev session (`--env <name>`; default: the last run's environment) | `reference/reporting.md` + `reference/environments.md` |
| `status` | Summarize coverage and remaining blockers without running anything (`--env` as for `report`) | `reference/reporting.md` + `reference/environments.md` |

`testplan` — the action's former name — is still accepted as an alias of `plan`.

**Read the action's Procedure files, in full, before doing anything the action does** — each
`${CLAUDE_SKILL_DIR}/<path>` (see Rules). This file is the dispatch table and the rules that hold
for every action; it is **not** the procedure. The Procedure column is where an action's steps,
its preconditions and the order they run in live, and the table above is a summary of them, never
a substitute: an action executed from this file alone will skip a guard it never read. An action
that lists two files needs both — `reference/environments.md` is how every `--env`, surface,
reset, credential and drift lookup resolves.

**Every action ends its reply with the progress table** (see "Progress table"), `init` excepted.

---

## Progress table

Every action but `init` ends its reply with this table, and `qa-plan.md` keeps the same tables
under its header. Which tables, and who writes them:

- `plan` writes the **default** environment's table (all Not run), and keeps any existing ones —
  recomputed, since a regeneration can change N.
- `run` / `retest` add or refresh the **selected** environment's table.
- `note` refreshes **every** table: a REMOVED assertion changes N for all of them. `note --env all`
  prints them all; `note --env <name>` prints that environment's.
- `status` / `report` print the selected environment's table; they write nothing to the plan.

Percentages are of the plan's **total assertions** — REMOVED ones excluded — each with its count;
they are computed from `qa-plan.md`, never estimated.

```markdown
**Progress — `<env>` · <N> assertions**

| ✅ Done | 🟢 PASS | 🔴 DEFECT | 🟠 BLOCKED | ⚪ Not run |
|---|---|---|---|---|
| 0% (0) | 0% (0) | 0% (0) | 0% (0) | 100% (<N>) |
```

**DEFECT** counts the assertions whose status on this environment is FAIL; a PASS-with-note counts
as PASS. **Done** = has a result on this environment (PASS, DEFECT or BLOCKED). The identities hold for the
**counts** — Done = PASS + DEFECT + BLOCKED, Done + Not run = N — never for the rounded
percentages, so never adjust a count to make the percentages add up. Round each percentage to a
whole number on its own; show a non-zero value below 1% as `<1%` (never `0%`) and a value above
99% but short of 100% as `>99%` (never `100%`).

---

## Rules

- **A file bundled with this skill is named `${CLAUDE_SKILL_DIR}/<path>`, never bare.** The
  placeholder is substituted with this skill's own directory when the skill loads. A companion
  named *without* it is a relative path, and resolves against the session's working directory —
  the operator's repo — where it does not exist. Applies to everything under `templates/` and
  `reference/`, the Procedure column included: the column names each file bare so the table stays
  readable, and you prefix the placeholder when you open it.
- **Environment details live in `.anantys/qa.md`, never in this skill and never in `qa-plan.md`.**
  A plan that hardcodes a hostname stops working for the next project — and for the next dev stack.
- **Never reset — or write destructively to — a `shared` environment** (staging, a preview, prod).
  It is persistent and may hold real data; create test subjects additively and drive it through the
  operator's existing browser session, after they confirm the target. Reset is for a `local` env
  only; on production, never charge, record consent for, or notify a real person.
- **Never start, restart or repair the stack.** A failed preflight stops the campaign and goes back
  to the operator.
- **Never modify product code.** You observe and report; fixing is a separate session, which is
  the entire point of `report`.
- **Assertion ids are permanent.** Never renumber. Runs, notes and reports reference them for the
  life of the feature.
- **Append runs, never overwrite them.** The history is what stops a fixed defect from being
  re-diagnosed six weeks later.
- **BLOCKED is a real result.** Report it as loudly as a FAIL — an unreachable case is untested,
  and a green blocker list that quietly contains one is worse than a red one. A `BLOCKED` this
  skill **refused** to walk is answered by another environment's PASS, not by a louder report
  (see `${CLAUDE_SKILL_DIR}/reference/environments.md`).
- Report what you actually observed. Never a PASS you inferred.
