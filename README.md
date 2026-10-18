# anantys-team

A small, project-agnostic marketplace that turns Claude Code into a **specialized mini-team**.

The `anantys-team-agents` plugin gives Claude a set of **roles** — each one a way to put
*Claude + a real browser* to work, not just for writing code, but for piloting your tools
like a teammate would:

Installed, the roles are **namespaced by the plugin** — the skills additionally have their
dots rewritten to hyphens, because a skill's identity is its *directory* name and the loader
sanitizes it. The names below are the ones the session actually exposes; typing `/anantys`
autocompletes all seven.

| Role | Invoke | Pattern | What they do |
|------|--------|---------|--------------|
| 🎨 **Frontend Designer** | skill `/anantys-team-agents:anantys.design` | **Dev loop** | Refines a web page's design in a tight edit → reload → screenshot loop. The screenshot is the proof — never a "looks done" diff. |
| 📈 **Growth / Ops Analyst** | skill `/anantys-team-agents:anantys.ops` | **Ops loop** | Drives the browser across live pages and SaaS dashboards (Search Console, Analytics, SERP) to produce a quantified, prioritized SEO/acquisition report with trend deltas. |
| 🐞 **Runtime Debugger** | skill `/anantys-team-agents:anantys.debug` | **Ralf loop** | Reproduces a bug live, reads runtime signals (console, network, logs), fixes, and re-proves by observation — never by a plausible diff. |
| 🔀 **PR Reviewer** | skill `/anantys-team-agents:anantys.review` | **Decision-ready review** | Cleanly reviews one agent-pushed PR branch: rebases on its base, summarizes only its own changes, assesses value/risk, and recommends Merge / Close / Skip / Audit — then waits for the human. |
| 🧭 **QA Campaign Runner** | skill `/anantys-team-agents:anantys.qa` | **Campaign loop** | Turns a finished feature — a spec-kit `tasks.md`, a written brief, tracker issues, or a GitHub PR — into an executable browser campaign, runs it against a local dev stack or a deployed env (`--env staging`) recording PASS/FAIL/BLOCKED **per assertion**, accumulates operator rulings so a non-defect is never re-filed, and emits a fix brief for a fresh dev session. |
| 🔍 **Code Auditor** | agent `anantys-team-agents:anantys.code-auditor` | **Adversarial review** | Runs in a fresh context after a large LLM-generated change and reports what it *omitted* — implicit contracts, edge cases, violated conventions the brief never spelled out. Restores cognitive control over mass-generated code. |
| 🧪 **Spec Tester** | agent `anantys-team-agents:anantys.spec-tester` | **Spec-first testing** | Writes tests from the spec, deliberately *not* from the implementation, so they can fail against existing code — instead of just confirming what the model already wrote. |
| 🎨 **Frontend Designer** | skill `/anantys.design` | **Dev loop** | Refines a web page's design in a tight edit → reload → screenshot loop. The screenshot is the proof — never a "looks done" diff. |
| 📈 **Growth / Ops Analyst** | skill `/anantys.ops` | **Ops loop** | Drives the browser across live pages and SaaS dashboards (Search Console, Analytics, SERP) to produce a quantified, prioritized SEO/acquisition report with trend deltas. |
| 🐞 **Runtime Debugger** | skill `/anantys.debug` | **Ralf loop** | Reproduces a bug live, reads runtime signals (console, network, logs), fixes, and re-proves by observation — never by a plausible diff. |
| 🔀 **PR Reviewer** | skill `/anantys.review` | **Decision-ready review** | Cleanly reviews one agent-pushed PR branch: rebases on its base, summarizes only its own changes, assesses value/risk, and recommends Merge / Close / Skip / Audit — then waits for the human. |
| 🧭 **QA Campaign Runner** | skill `/anantys.qa` | **Campaign loop** | Turns a finished feature — a spec-kit `tasks.md`, a written brief, tracker issues, or a GitHub PR — into an executable browser campaign, runs it against a local dev stack or a deployed env (`--env staging`) recording PASS/FAIL/BLOCKED **per assertion**, accumulates operator rulings so a non-defect is never re-filed, and emits a fix brief for a fresh dev session. After a fix, `retest --fixed <ref>` re-reads the actual diff so the regression set is the one that fix put at risk, not a guess from the symptoms. |
| 🔍 **Code Auditor** | agent `anantys.code-auditor` | **Adversarial review** | Runs in a fresh context after a large LLM-generated change and reports what it *omitted* — implicit contracts, edge cases, violated conventions the brief never spelled out. Restores cognitive control over mass-generated code. |
| 🧪 **Spec Tester** | agent `anantys.spec-tester` | **Spec-first testing** | Writes tests from the spec, deliberately *not* from the implementation, so they can fail against existing code — instead of just confirming what the model already wrote. |

**Skills** are invoked directly (`/anantys-team-agents:anantys.design …`) — type `/anantys` to
see the whole team.
**Agents** are dispatched as isolated subagents (via the `Task`/Agent tool) — a deliberately
*fresh context* so their review/testing isn't biased by the reasoning that produced the code.

Every role is **project-agnostic**: no hardcoded domains, paths, or design tokens. They ask
for what they need (a dev URL, a property, target queries) or infer it from the project.
More roles can be added over time without changing how you install the team.

## How the roles hand off

A team is defined by its handoffs, not by its headcount. The two agents exist because of a
single rule: **a context cannot independently check its own work.** The reasoning that wrote
a fix will write a test that confirms that fix; the reasoning that wrote a feature will
review it as complete. So the skills delegate exactly the steps where self-assessment is
worthless:

```
/anantys.debug   defect spec  ──▶  anantys.spec-tester   regression test, fresh context
/anantys.review  spec/ticket  ──▷  anantys.spec-tester   are the PR's tests change-detectors?
                                                         (recommended as Audit, you authorize)
/anantys.review  the diff     ──▶  anantys.code-auditor  what did it omit?
```

A solid arrow is a dispatch the skill performs; `──▷` is one it recommends and you authorize.
`review` is read-only by declaration — it may not hand its clean working tree to an agent that
writes files, so the test run it needs is a verdict, not a side effect.

What crosses the boundary is always the **spec, never the diff**. Hand `spec-tester` the
expected behavior and it can write a test that fails; hand it the implementation and it can
only write one that passes. Same for the auditor: it gets the change as a suspect, not the
reasoning that justified it.

## Requirements

- [Claude Code](https://claude.com/claude-code)
- **Claude-in-Chrome**, for the four browser-driven roles (`design`, `ops`, `debug`, `qa`).

  The team is agnostic about *your project* — no hardcoded domains, paths, or design
  tokens — but not about the browser backend. Each browser role names the
  `mcp__claude-in-chrome__*` tools in its `allowed-tools`, and that list is a hard
  allowlist: a different browser MCP (Playwright, chrome-devtools, …) is unreachable
  from the skill even while connected. To swap backends, edit the role's
  `allowed-tools` to its equivalent tools — tab context, navigate, click/type, read
  page, console. The roles' prose is written against capabilities, not against one
  vendor, so nothing else needs to change.

  That list is a **tool** allowlist, not a **destination** allowlist — it says which
  verbs a role holds, never where it may point them. The browser it drives is *yours*,
  signed into everything you use, so each browser role additionally declares its own
  navigation scope up front: the approved domain list you sign off on (`ops`), the dev
  URL (`design`), the repro's URL (`debug`), the selected environment's Surfaces
  (`qa`). `ops` — the one role aimed at live SaaS dashboards under your real account —
  is read-only there as well as on the codebase: it may change what a page *shows* it,
  never what the service *stores*.

## Install

```bash
# 1. Add this marketplace
/plugin marketplace add Anantys-OSS/anantys-team

# 2. Install the pack (the whole team)
/plugin install anantys-team-agents@anantys-oss
```

Then invoke a skill directly. Every command is prefixed `anantys-team-agents:` — type
`/anantys` and let the completion fill it in:

```bash
/anantys-team-agents:anantys.design  https://dev.example.com/pricing — fix the hero spacing
/anantys-team-agents:anantys.ops     audit example.com, hub /blog, target "trail shoes 2026"
/anantys-team-agents:anantys.debug   the cart total is wrong on checkout — here's the repro
/anantys-team-agents:anantys.review  review the branch agent/123-add-export — safe to merge?

# the QA role takes a subcommand
/anantys-team-agents:anantys.qa  init                 # describe your environments, once
/anantys-team-agents:anantys.qa  plan 206-checkout    # derive from specs/206-checkout/tasks.md
/anantys-team-agents:anantys.qa  plan --from pr:42    # …or from a PR that's ready on GitHub
/anantys-team-agents:anantys.qa  plan --brief feat.md # …or from a hand-written feature brief
/anantys-team-agents:anantys.qa  run                  # walk it in a real browser, local env
/anantys-team-agents:anantys.qa  run --env staging    # …or a deployed env — additive only
/anantys-team-agents:anantys.qa  report               # fix brief to paste into a dev session
/anantys.design  https://dev.example.com/pricing  — fix the hero spacing and button contrast
/anantys.ops     audit example.com, hub /blog, target "best running shoes" "trail shoes 2026"
/anantys.debug   the cart total is wrong on the checkout page — here's the repro
/anantys.review  review the branch agent/123-add-export — is it safe to merge?
/anantys.qa      init                     # one-off: describe your environments (local, staging…)
/anantys.qa      plan 206-checkout        # derive the campaign from specs/206-checkout/tasks.md
/anantys.qa      plan --from pr:42        # …or from a PR that's ready on GitHub
/anantys.qa      plan --brief feat.md     # …or from a hand-written feature brief
/anantys.qa      run                      # walk it in a real browser, on the local env (asks: autonomous or interactive)
/anantys.qa      run --env staging        # …or on a deployed env — never reset, additive only
/anantys.qa      report                   # fix brief to paste into a dev session
/anantys.qa      retest --fixed pr:43     # …then re-test the unresolved set + what that fix put at risk
```

## Repository layout

```
anantys-team/
├── .claude-plugin/marketplace.json     # the catalog (what `marketplace add` reads)
└── plugins/
    └── anantys-team-agents/
        ├── .claude-plugin/plugin.json  # the installable unit (name + version)
        ├── skills/                     # one dir per skill — the dir name IS the command
        │   ├── anantys.design/SKILL.md
        │   ├── anantys.ops/SKILL.md
        │   ├── anantys.debug/SKILL.md
        │   ├── anantys.review/SKILL.md
        │   └── anantys.qa/
        │       ├── SKILL.md
        │       └── templates/           # qa-config.md, qa-plan.md, feature-brief.md
        └── agents/                     # dispatched as isolated subagents
            ├── anantys.code-auditor.md
            └── anantys.spec-tester.md
```

- **marketplace** = the catalog (the repo you add).
- **plugin** = the installable, versioned unit a user enables in one shot.
- **skills** = the actual capabilities Claude invokes.

## Tool grants: which field actually withholds a capability

The two frontmatter dialects in this tree are **not** the same mechanism, and only one of
them restricts anything:

| Field | Used by | What it does |
|-------|---------|--------------|
| `tools:` | `agents/*.md` | A **ceiling**. The subagent gets exactly these tools; anything absent is unreachable. |
| `allowed-tools:` | `skills/*/SKILL.md` | An **allow-rule** — "tools available to the model while this file is active". It auto-approves the tools it lists. It is *not* a ceiling: a tool left out is still reachable, it just raises a permission prompt. |
| `disallowed-tools:` | `skills/*/SKILL.md` | The only field on a skill that **removes** a tool. Cleared when the user sends their next message. |

Two consequences worth keeping in mind when editing a role:

1. **Omitting a tool from a skill's `allowed-tools` does not withhold it.** It costs the
   operator a prompt, not the capability. So a skill rule like "never push" is advisory
   unless `disallowed-tools` carries it — which is why `anantys.debug`, `anantys.design`
   and `anantys.review` now deny `git push` (and, for the two editing loops, `git commit`
   and `gh pr create`) in frontmatter rather than only in prose. The field clearing on the
   user's next message is the right shape here: the rules say *"unless the user explicitly
   asks"*, and the asking is what lifts the denial.
2. **Listing a tool auto-approves it.** The browser grants on `anantys.design`,
   `anantys.debug` and `anantys.ops` include `computer` and `javascript_tool` — full
   input control and arbitrary JS in the operator's signed-in session, with no prompt.
   That is deliberate (these roles are useless at one prompt per refresh), but it is a
   grant, not a declaration of intent: add a browser tool only if the loop needs it.

The plugin itself ships **no MCP servers** (`claude plugin details` confirms: `MCP servers (0)`).
The `mcp__claude-in-chrome__*` grants therefore cannot *provide* the browser — they only
pre-approve it when the operator has the extension connected. Every browser role checks
availability at runtime via `tabs_context_mcp` and stops if it is missing; that check, not
the grant list, is the hard gate.
A skill's installed name comes from its **directory**, not from the `name:` in its frontmatter,
and non-alphanumerics are rewritten — so `skills/anantys.qa/` ships as `anantys.qa`. Agent names
come from their file and keep the dot. To check what a session really exposes, ask it:

```bash
claude --print --output-format stream-json --verbose x | head -1   # .skills / .agents / .slash_commands
```

## License

Provided as-is for consulting and educational use.
