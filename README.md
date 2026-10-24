# anantys-team

A small, vendor-neutral marketplace that turns Claude Code into a **specialized mini-team**.

The `anantys-team-agents` plugin gives Claude a set of **roles** — each one a way to put
*Claude + a real browser* to work, not just for writing code, but for piloting your tools
like a teammate would:

| Role | Invoke | Pattern | What they do |
|------|--------|---------|--------------|
| 🎨 **Frontend Designer** | skill `/anantys.design` | **Dev loop** | Refines a web page's design in a tight edit → reload → screenshot loop. The screenshot is the proof — never a "looks done" diff. |
| 📈 **Growth / Ops Analyst** | skill `/anantys.ops` | **Ops loop** | Drives the browser across live pages and SaaS dashboards (Search Console, Analytics, SERP) to produce a quantified, prioritized SEO/acquisition report with trend deltas. |
| 🐞 **Runtime Debugger** | skill `/anantys.debug` | **Ralf loop** | Reproduces a bug live, reads runtime signals (console, network, logs), fixes, and re-proves by observation — never by a plausible diff. |
| 🔀 **PR Reviewer** | skill `/anantys.review` | **Decision-ready review** | Cleanly reviews one agent-pushed PR branch: rebases on its base, summarizes only its own changes, assesses value/risk, and recommends Merge / Close / Skip / Audit — then waits for the human. |
| 🧭 **QA Campaign Runner** | skill `/anantys.qa` | **Campaign loop** | Turns a finished feature — a spec-kit `tasks.md`, a written brief, tracker issues, or a GitHub PR — into an executable browser campaign, runs it against a local dev stack or a deployed env (`--env staging`) recording PASS/FAIL/BLOCKED **per assertion**, accumulates operator rulings so a non-defect is never re-filed, and emits a fix brief for a fresh dev session. |
| 🔍 **Code Auditor** | agent `anantys.code-auditor` | **Adversarial review** | Runs in a fresh context after a large LLM-generated change and reports what it *omitted* — implicit contracts, edge cases, violated conventions the brief never spelled out. Restores cognitive control over mass-generated code. |
| 🧪 **Spec Tester** | agent `anantys.spec-tester` | **Spec-first testing** | Writes tests from the spec, deliberately *not* from the implementation, so they can fail against existing code — instead of just confirming what the model already wrote. |

**Skills** are invoked directly (`/anantys.design …`) — type `/anantys` to see the whole team.
**Agents** are dispatched as isolated subagents (via the `Task`/Agent tool) — a deliberately
*fresh context* so their review/testing isn't biased by the reasoning that produced the code.

Every role is **project-agnostic**: no hardcoded domains, paths, or design tokens. They ask
for what they need (a dev URL, a property, target queries) or infer it from the project.
More roles can be added over time without changing how you install the team.

## Requirements

- [Claude Code](https://claude.com/claude-code)
- A connected browser for the browser tools (e.g. the **Claude-in-Chrome** extension).

## Install

```bash
# 1. Add this marketplace
/plugin marketplace add Anantys-OSS/anantys-team

# 2. Install the pack (the whole team)
/plugin install anantys-team-agents@anantys-oss
```

Then invoke a skill directly:

```bash
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
```

## Repository layout

```
anantys-team/
├── .claude-plugin/marketplace.json     # the catalog (what `marketplace add` reads)
└── plugins/
    └── anantys-team-agents/
        ├── .claude-plugin/plugin.json  # the installable unit (name + version)
        ├── skills/                     # invoked directly (/anantys.*)
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
| `disallowed-tools:` | `skills/*/SKILL.md` | The only field on a skill that **removes** a tool — but it removes it **by name**. Cleared when the user sends their next message. |

Three consequences worth keeping in mind when editing a role:

1. **Omitting a tool from a skill's `allowed-tools` does not withhold it.** It costs the
   operator a prompt, not the capability. So a skill rule like "never push" is advisory,
   and — see (2) — frontmatter cannot make it binding. The prose rule *is* the enforcement.
2. **A scoped denial is a total denial, so no role here carries one.** `disallowed-tools`
   is parsed by the same name-only path as `tools:`: the rule in parentheses is read and
   then dropped, leaving the bare tool name. On a *grant* that is merely a no-op. On a
   *denial* it inverts the author's intent — `disallowed-tools: Bash(git push:*)` denies
   **all** of `Bash`, which for `anantys.review` (every step is `git`/`gh`),
   `anantys.debug` and `anantys.design` means the role resolves with no shell at all.
   Nothing warns you: the file installs clean and `claude plugin validate --strict`
   stays quiet. The only place rule content is honoured is the operator's own settings,
   and those rules are session-wide rather than per-role:

   ```json
   { "permissions": { "deny": ["Bash(git push:*)", "Bash(gh pr create:*)"] } }
   ```

3. **Listing a tool auto-approves it.** The browser grants on `anantys.design`,
   `anantys.debug` and `anantys.ops` include `computer` and `javascript_tool` — full
   input control and arbitrary JS in the operator's signed-in session, with no prompt.
   That is deliberate (these roles are useless at one prompt per refresh), but it is a
   grant, not a declaration of intent: add a browser tool only if the loop needs it.

The plugin itself ships **no MCP servers** (`claude plugin details` confirms: `MCP servers (0)`).
The `mcp__claude-in-chrome__*` grants therefore cannot *provide* the browser — they only
pre-approve it when the operator has the extension connected. Every browser role checks
availability at runtime via `tabs_context_mcp` and stops if it is missing; that check, not
the grant list, is the hard gate.

## License

Provided as-is for consulting and educational use.
