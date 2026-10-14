# anantys-team

A small, vendor-neutral marketplace that turns Claude Code into a **specialized mini-team**.

The `anantys-team-agents` plugin gives Claude a set of **roles** — each one a way to put
*Claude + a real browser* to work, not just for writing code, but for piloting your tools
like a teammate would:

Installed, the roles are **namespaced by the plugin** — the skills additionally have their
dots rewritten to hyphens, because a skill's identity is its *directory* name and the loader
sanitizes it. The names below are the ones the session actually exposes; typing `/anantys`
autocompletes all seven.

| Role | Invoke | Pattern | What they do |
|------|--------|---------|--------------|
| 🎨 **Frontend Designer** | skill `/anantys-team-agents:anantys-design` | **Dev loop** | Refines a web page's design in a tight edit → reload → screenshot loop. The screenshot is the proof — never a "looks done" diff. |
| 📈 **Growth / Ops Analyst** | skill `/anantys-team-agents:anantys-ops` | **Ops loop** | Drives the browser across live pages and SaaS dashboards (Search Console, Analytics, SERP) to produce a quantified, prioritized SEO/acquisition report with trend deltas. |
| 🐞 **Runtime Debugger** | skill `/anantys-team-agents:anantys-debug` | **Ralf loop** | Reproduces a bug live, reads runtime signals (console, network, logs), fixes, and re-proves by observation — never by a plausible diff. |
| 🔀 **PR Reviewer** | skill `/anantys-team-agents:anantys-review` | **Decision-ready review** | Cleanly reviews one agent-pushed PR branch: rebases on its base, summarizes only its own changes, assesses value/risk, and recommends Merge / Close / Skip / Audit — then waits for the human. |
| 🧭 **QA Campaign Runner** | skill `/anantys-team-agents:anantys-qa` | **Campaign loop** | Turns a finished feature — a spec-kit `tasks.md`, a written brief, tracker issues, or a GitHub PR — into an executable browser campaign, runs it against a local dev stack or a deployed env (`--env staging`) recording PASS/FAIL/BLOCKED **per assertion**, accumulates operator rulings so a non-defect is never re-filed, and emits a fix brief for a fresh dev session. |
| 🔍 **Code Auditor** | agent `anantys-team-agents:anantys.code-auditor` | **Adversarial review** | Runs in a fresh context after a large LLM-generated change and reports what it *omitted* — implicit contracts, edge cases, violated conventions the brief never spelled out. Restores cognitive control over mass-generated code. |
| 🧪 **Spec Tester** | agent `anantys-team-agents:anantys.spec-tester` | **Spec-first testing** | Writes tests from the spec, deliberately *not* from the implementation, so they can fail against existing code — instead of just confirming what the model already wrote. |

**Skills** are invoked directly (`/anantys-team-agents:anantys-design …`) — type `/anantys` to
see the whole team.
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

Then invoke a skill directly. Every command is prefixed `anantys-team-agents:` — type
`/anantys` and let the completion fill it in:

```bash
/anantys-team-agents:anantys-design  https://dev.example.com/pricing — fix the hero spacing
/anantys-team-agents:anantys-ops     audit example.com, hub /blog, target "trail shoes 2026"
/anantys-team-agents:anantys-debug   the cart total is wrong on checkout — here's the repro
/anantys-team-agents:anantys-review  review the branch agent/123-add-export — safe to merge?

# the QA role takes a subcommand
/anantys-team-agents:anantys-qa  init                 # describe your environments, once
/anantys-team-agents:anantys-qa  plan 206-checkout    # derive from specs/206-checkout/tasks.md
/anantys-team-agents:anantys-qa  plan --from pr:42    # …or from a PR that's ready on GitHub
/anantys-team-agents:anantys-qa  plan --brief feat.md # …or from a hand-written feature brief
/anantys-team-agents:anantys-qa  run                  # walk it in a real browser, local env
/anantys-team-agents:anantys-qa  run --env staging    # …or a deployed env — additive only
/anantys-team-agents:anantys-qa  report               # fix brief to paste into a dev session
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

A skill's installed name comes from its **directory**, not from the `name:` in its frontmatter,
and non-alphanumerics are rewritten — so `skills/anantys.qa/` ships as `anantys-qa`. Agent names
come from their file and keep the dot. To check what a session really exposes, ask it:

```bash
claude --print --output-format stream-json --verbose x | head -1   # .skills / .agents / .slash_commands
```

## License

Provided as-is for consulting and educational use.
