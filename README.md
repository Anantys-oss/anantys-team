# generic-skills

A small, vendor-neutral marketplace that turns Claude Code into a **specialized mini-team**.

The `anantys-team-agents` plugin gives Claude a set of **roles** — each one a way to put
*Claude + a real browser* to work, not just for writing code, but for piloting your tools
like a teammate would:

| Role | Type | Pattern | What they do |
|------|------|---------|--------------|
| 🎨 **Frontend Designer** | skill `frontend-designer` | **Dev loop** | Refines a web page's design in a tight edit → reload → screenshot loop. The screenshot is the proof — never a "looks done" diff. |
| 📈 **Growth / Ops Analyst** | skill `web-ops-reviewer` | **Ops loop** | Drives the browser across live pages and SaaS dashboards (Search Console, Analytics, SERP) to produce a quantified, prioritized SEO/acquisition report with trend deltas. |
| 🧱 **Incremental Builder** | skill `incremental-builder` | **Construction, not dumping** | Builds a feature in small reviewable steps (~200 lines max), pausing at each to keep the developer's mental model alive. Defeats the mass-dump failure mode. |
| 🐞 **Runtime Debugger** | skill `runtime-debug-loop` | **Ralf loop** | Reproduces a bug live, reads runtime signals (console, network, logs), fixes, and re-proves by observation — never by a plausible diff. |
| 🔍 **Blind-Spot Auditor** | agent `blind-spot-auditor` | **Adversarial review** | Runs in a fresh context after a large LLM-generated change and reports what it *omitted* — implicit contracts, edge cases, violated conventions the brief never spelled out. Restores cognitive control over mass-generated code. |
| 🧪 **Independent QA** | agent `test-by-spec` | **Spec-first testing** | Writes tests from the spec, deliberately *not* from the implementation, so they can fail against existing code — instead of just confirming what the model already wrote. |

**Skills** are invoked directly (`/frontend-designer …`). **Agents** are dispatched as
isolated subagents (via the `Task`/Agent tool) — a deliberately *fresh context* so their
review/testing isn't biased by the reasoning that produced the code.

Every role is **project-agnostic**: no hardcoded domains, paths, or design tokens. They ask
for what they need (a dev URL, a property, target queries) or infer it from the project.
More roles can be added over time without changing how you install the team.

## Requirements

- [Claude Code](https://claude.com/claude-code)
- A connected browser for the browser tools (e.g. the **Claude-in-Chrome** extension).

## Install

```bash
# 1. Add this marketplace
/plugin marketplace add Anantys/generic-skills

# 2. Install the pack (the whole team)
/plugin install anantys-team-agents
```

Then invoke a skill directly:

```bash
/frontend-designer  https://dev.example.com/pricing  — fix the hero spacing and button contrast
/web-ops-reviewer   audit example.com, hub /blog, target "best running shoes" "trail shoes 2026"
```

## Repository layout

```
generic-skills/
├── .claude-plugin/marketplace.json     # the catalog (what `marketplace add` reads)
└── plugins/
    └── anantys-team-agents/
        ├── .claude-plugin/plugin.json  # the installable unit (name + version)
        ├── skills/                     # invoked directly (/name)
        │   ├── frontend-designer/SKILL.md
        │   ├── web-ops-reviewer/SKILL.md
        │   ├── incremental-builder/SKILL.md
        │   └── runtime-debug-loop/SKILL.md
        └── agents/                     # dispatched as isolated subagents
            ├── blind-spot-auditor.md
            └── test-by-spec.md
```

- **marketplace** = the catalog (the repo you add).
- **plugin** = the installable, versioned unit a user enables in one shot.
- **skills** = the actual capabilities Claude invokes.

## License

Provided as-is for consulting and educational use.
