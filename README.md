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
| 🔍 **Code Auditor** | agent `anantys.code-auditor` — name it, or `/anantys.review` dispatches it | **Adversarial review** | Runs in a fresh context after a large LLM-generated change and reports what it *omitted* — implicit contracts, edge cases, violated conventions the brief never spelled out. Restores cognitive control over mass-generated code. |
| 🧪 **Spec Tester** | agent `anantys.spec-tester` — name it in a request | **Spec-first testing** | Writes tests from the spec, deliberately *not* from the implementation, so they can fail against existing code — instead of just confirming what the model already wrote. |

**Skills** are invoked directly (`/anantys.design …`) — type `/anantys` to list the five of them.
**Agents are not slash commands**, so `/anantys` never shows them — that menu is five sevenths of
the team. You reach an agent by **naming it in a request** ("use the `anantys.spec-tester` agent
on …"); `/anantys.review` also dispatches `anantys.code-auditor` on its own for a large change.
Either way they run as isolated subagents (via the `Task`/Agent tool) — a deliberately
*fresh context* so their review/testing isn't biased by the reasoning that produced the code.

> **Don't "fix" these names.** Installed, a skill's *registered* name comes from its directory
> with every non-`[A-Za-z0-9_-]` character rewritten, so the dot becomes a hyphen:
> `anantys-team-agents:anantys-design`. The frontmatter `name:` is not discarded — the loader
> keeps it as the skill's user-facing name **and as a bare alias**, and dispatch matches a typed
> command against all three. So `/anantys.design`, `/anantys-team-agents:anantys.design` and
> `/anantys-team-agents:anantys-design` all reach the same skill (`claude` 2.1.278). Agents keep
> the dot in their registered name, so `anantys.code-auditor` is dispatched as written.
>
> A session's `system`/`init` event lists registered names only, never aliases — it omits
> `/login` for the same reason. Absence from that list is not evidence a command cannot be typed.

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

The two agents have no slash command — name one in plain language and Claude dispatches it:

```text
use the anantys.code-auditor agent on branch agent/123-add-export — the PR description is the only brief
use the anantys.spec-tester agent for specs/206-checkout — write the tests from the spec, not from the code
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
- **`$ARGUMENTS` can be used, not named.** The loader substitutes *every* occurrence in a
  `SKILL.md` body with the invocation's argument text, so a role that mentions the placeholder
  in prose gets that sentence rewritten around the user's whole argument string. Write `\$ARGUMENTS`
  to refer to it literally, or point at the block that holds it. A body with no live placeholder is
  not deprived of the arguments — the loader appends them as a trailing `ARGUMENTS: <text>` line.

## Conventions

Cross-cutting rules — the ones that bind every role rather than one skill — live in
[`docs/`](./docs/), one file per rule. A new convention is a new file there, never
another section here: README has a single append point, and every PR that used it
collided with every other PR that used it.

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

## What constrains a role (and what doesn't)

A role's frontmatter is a tool-**name** list, not a permission policy. Worth knowing before you
trust one with a repo:

- **`tools:` and `disallowedTools:` match names only.** `Bash(git diff:*)` is parsed, the rule in
  parentheses is **discarded**, and the bare `Bash` tool is granted — identical to writing `Bash`.
  The one exception is the agent-spawn tool, where `Agent(a,b)` does restrict which agent types may
  be spawned. Nothing warns you: a scoped spelling installs clean, shows up in the component
  inventory, and `claude plugin validate --strict` stays quiet about it.
- **`permissionMode:`, `hooks:` and `mcpServers:` are ignored for plugin agents.** The loader logs a
  warning pointing you at a loose `.claude/agents/` copy, which is the only place those bind.

So `anantys.code-auditor` holds an **unrestricted shell** and its "writes no code" contract is
behavioural, stated in the agent's own prose. If you need it enforced, deny in your own settings —
rule content *is* honoured there, but the rules are session-wide, not per-agent:

```json
{ "permissions": { "deny": ["Bash(git commit:*)", "Bash(git push:*)", "Bash(git checkout:*)"] } }
```

### The install boundary

`marketplace add` clones this whole repo. `plugin install` then copies **only the
directory the catalog entry points at** (`source: ./plugins/anantys-team-agents`)
into a versioned cache, and that copy — not the clone — is what a role runs from:

```text
~/.claude/plugins/
├── marketplaces/anantys-oss/                        # the full repo clone, dev-time only
└── cache/anantys-oss/anantys-team-agents/<version>/ # ← what an installed role sees
    ├── .claude-plugin/plugin.json
    ├── skills/
    └── agents/
```

`<version>` is the one in `plugin.json` (a commit suffix may be appended, and a
plugin that declares no version caches under `unknown`). Read the real paths off
a live install rather than trusting this diagram:

```bash
jq -r '.plugins | to_entries[] | "\(.key)\t\(.value[0].installPath)"' \
  ~/.claude/plugins/installed_plugins.json
```

So the boundary is load-bearing, in both directions:

- **Anything a role needs at runtime must sit inside `plugins/anantys-team-agents/`** —
  the way `anantys.qa/templates/` does. A sibling of `plugins/` is present in a git
  checkout and **absent for every installed user**: a repo-root `docs/note.md` that a
  `SKILL.md` links as `../../../../docs/note.md` resolves, from the cache copy, to
  `cache/anantys-oss/docs/note.md` — a path `plugin install` never wrote. The link
  works for exactly the one reader who does not need it, the contributor who wrote it.
- **Anything that only serves contributors should stay outside it** — this README, CI
  config, measurements, review notes. It ships to no one, which is the point; shipping
  it only grows what every install downloads.

## License

Provided as-is for consulting and educational use.
