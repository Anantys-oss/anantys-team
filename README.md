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
The two that edit your source — Designer and Debugger — stop at an *uncommitted* fix and hand
back **the named list of files they own**, measured against the working tree as they found it.
Whatever was already dirty stays untouched, and rejected attempts are reverted rather than
left riding along; you stage the named set, or commit it to a branch for the PR Reviewer.
More roles can be added over time without changing how you install the team.

## Requirements

- [Claude Code](https://claude.com/claude-code)
- The **Claude-in-Chrome** extension, attached to a browser.

You do not wire the browser up yourself. `plugin.json` declares the Claude-in-Chrome MCP
server, so installing the plugin connects it — the three browser roles' granted tool names
exist from the first session. What the plugin cannot supply is the extension: without it the
server still reports `connected`, but a tool call waits on a browser that never answers.
Attach the extension before invoking a browser role.

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
- **`$ARGUMENTS` can be used, not named.** The loader substitutes *every* occurrence in a
  `SKILL.md` body with the invocation's argument text, so a role that mentions the placeholder
  in prose gets that sentence rewritten around the user's whole argument string. Write `\$ARGUMENTS`
  to refer to it literally, or point at the block that holds it. A body with no live placeholder is
  not deprived of the arguments — the loader appends them as a trailing `ARGUMENTS: <text>` line.

## Tool grants: which field actually withholds a capability

The two frontmatter dialects in this tree are **not** the same mechanism, and only one of
them restricts anything:

| Field | Used by | What it does |
|-------|---------|--------------|
| `tools:` | `agents/*.md` | A **ceiling**. The subagent gets exactly these tools; anything absent is unreachable. |
| `allowed-tools:` | `skills/*/SKILL.md` | An **allow-rule** — "tools available to the model while this file is active". It auto-approves the tools it lists. It is *not* a ceiling: a tool left out is still reachable, it just raises a permission prompt. |
| `disallowed-tools:` | `skills/*/SKILL.md` | The only field on a skill that **removes** a tool — but it removes it **by name**. Cleared when the user sends their next message. |

Four consequences worth keeping in mind when editing a role:

1. **Omitting a tool from a skill's `allowed-tools` does not withhold it.** It costs the
   operator a prompt, not the capability. So a skill rule like "never push" is advisory,
   and — see (2) and (3) — frontmatter cannot make it binding. The prose rule *is* the
   enforcement.
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

3. **`disallowed-tools` is turn-scoped, not consent-scoped.** A skill's denies are written
   into the session's `command` deny scope, and every user input *replaces* that scope with
   whatever denies the new input carries — none, for ordinary prose. The reset never reads
   the message: in `claude` 2.1.278 it is one unconditional call on the user-input path,
   guarded only by flags named `isAlreadyProcessing` and `skipSkillPermissionReset`. So
   "unless the user explicitly asks" is **not** what the field implements. Asking lifts the
   denial, but so does refusing, and so does "what about the tests?". Treat the field as a
   guard over the current assistant turn and nothing more.
4. **Listing a tool auto-approves it.** The browser grants on `anantys.design`,
   `anantys.debug` and `anantys.ops` include `computer` and `javascript_tool` — full
   input control and arbitrary JS in the operator's signed-in session, with no prompt.
   That is deliberate (these roles are useless at one prompt per refresh), but it is a
   grant, not a declaration of intent: add a browser tool only if the loop needs it.

(2) and (3) compose badly, and `anantys.review` is where it shows. Even a name-only deny —
the only kind the field honours — would not guard it: its destructive section is *"Acting on
the decision (only after explicit confirmation)"*, which by construction begins after a user
message, so the deny scope is already empty by the time it merges, closes PRs and deletes
branches. `anantys.debug` and `anantys.design` are the opposite case, running many assistant
turns inside one user turn, which is the shape the field is good at — but a `Bash`-wide
denial is not a price an editing loop can pay either. For any rule that has to hold across
the human's answer, the prose rule is the guard; keep it explicit and do not let the
frontmatter read as a backstop it is not.

The plugin itself ships **no MCP servers** (`claude plugin details` confirms: `MCP servers (0)`).
The browser grants therefore cannot *provide* the browser — they only pre-approve it when the
operator has the extension connected. Every browser role checks availability at runtime via
`tabs_context_mcp` and stops if it is missing; that check, not the grant list, is the hard gate.

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
