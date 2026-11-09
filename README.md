# anantys-team

A small, vendor-neutral marketplace that turns Claude Code into a **specialized mini-team**.

The `anantys-team-agents` plugin gives Claude a set of **roles** — each one a way to put
*Claude + a real browser* to work, not just for writing code, but for piloting your tools
like a teammate would:

Installed, the roles are **namespaced by the plugin** — the skills additionally have their
dots rewritten to hyphens, because a skill registers under its *directory* name with every
character outside `[A-Za-z0-9_-]` replaced. The names below are the ones the session actually
exposes; the `anantys-team-agents:` prefix is optional (see [Command names](#command-names)),
and typing `/anantys` autocompletes all seven.

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

Then invoke a skill directly. The bare name is enough — type `/anantys` and let the
completion fill it in:

```bash
/anantys-design  https://dev.example.com/pricing  — fix the hero spacing and button contrast
/anantys-ops     audit example.com, hub /blog, target "best running shoes" "trail shoes 2026"
/anantys-debug   the cart total is wrong on the checkout page — here's the repro
/anantys-review  review the branch agent/123-add-export — is it safe to merge?

# the QA role takes a subcommand
/anantys-qa      init                     # one-off: describe your environments (local, staging…)
/anantys-qa      plan 206-checkout        # derive the campaign from specs/206-checkout/tasks.md
/anantys-qa      plan --from pr:42        # …or from a PR that's ready on GitHub
/anantys-qa      plan --brief feat.md     # …or from a hand-written feature brief
/anantys-qa      run                      # walk it in a real browser, on the local env
/anantys-qa      run --env staging        # …or on a deployed env — never reset, additive only
/anantys-qa      report                   # fix brief to paste into a dev session
```

### Command names

A skill's command id is `<plugin>:<directory name, sanitized>` — every character outside
`[A-Za-z0-9_-]` becomes `-`, so `skills/anantys.qa/` registers as
`anantys-team-agents:anantys-qa`. Agents register from their **filename** with the dot
intact, which is why `anantys.code-auditor` is spelled that way.

That was measured, not inferred — the frontmatter `name:` looks like it should decide and
does not:

| What you change | What the session exposes |
|---|---|
| `skills/anantys.design/`, `name: anantys.design` | `anantys-team-agents:anantys-design` |
| same dir, `name: zzz.renamed` | `anantys-team-agents:anantys-design` — unchanged |
| `skills/zzz.dirmoved/`, `name: anantys.design` | `anantys-team-agents:zzz-dirmoved` |

Lookup is exact string equality against the registered id and its bare `:`-suffix. So
`/anantys-qa` and `/anantys-team-agents:anantys-qa` both reach the skill, and **`/anantys.qa`
reaches nothing**: no registered id equals it and none ends with `:anantys.qa`.

The trap: `claude plugin details` prints the directory name **unsanitized** —
`Skills (5) anantys.debug, anantys.design, …` — so it shows the one spelling that routes
nothing, and shows it whatever the frontmatter says. It is an inventory label; reading that
table as the registry is how the dots got restored here once already. The registry is the
session's own `init` event, and asking it costs nothing:

```bash
claude --plugin-dir ./plugins/anantys-team-agents \
       --print --output-format stream-json --verbose x </dev/null | head -1
# .skills / .agents / .slash_commands — verified on claude 2.1.278
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

See [Command names](#command-names) for how a directory, a frontmatter `name:` and an agent
filename each turn into the string you type.

## License

Provided as-is for consulting and educational use.
