# What the loader checks, and what it does not

Claude Code ships its own validator, `claude plugin validate`. This repo had
never run it. The obvious move was to adopt it and retire some of the
hand-rolled checking in `scripts/`. Measurement says the opposite: it is a
useful input, and a poor gate.

## The measurement

Seven single-field mutations of a known-good tree, each run against three
gates. `loader@root` is `claude plugin validate .` from the repo root —
the invocation anyone would reach for first.

| mutation | loader @ repo root | loader @ plugin dir | `check_plugins.py` | `check_platform.py` |
|---|---|---|---|---|
| control (unmodified) | clean | clean | clean | clean |
| `allowed_tools:` (underscore) | — | — | — | **error** |
| `mcp_chrome_navigate` (single underscore) | — | — | — | **error** |
| frontmatter block never closed | — | — | **error** | **error** |
| skill `name` ≠ its directory | — | — | **error** | — |
| skill `description` deleted | — | warning | **error** | warning |
| agent `tools:` names a malformed tool | — | — | — | **error** |

Claude Code 2.1.278, macOS arm64.

## Two things that follow

**Pointed at the repo root, the validator reports nothing about components.**
The root holds `.claude-plugin/marketplace.json`, so the validator validates a
marketplace: it returns `"contents": []` and never opens a SKILL.md. The one
finding it is capable of producing — a missing description — appears only when
each plugin *directory* is passed by name. A workflow step that runs
`claude plugin validate .` and goes green is reporting on the catalog, not on
the plugin. `scripts/check_platform.py` passes the plugin directories.

**What the loader accepts in silence is the part that matters here.** Every
mutation in the middle of that table ends the same way: a capability
declaration that stops applying, with nothing said at normal verbosity. The
loader's own documentation is explicit about the mechanism — when frontmatter
fails to parse, *every* field is dropped, the name falls back to the directory
and the description to the first line of the body, and `allowed-tools`,
`model`, and `disable-model-invocation` silently stop applying.

A misspelled key is the same failure with a smaller blast radius.
`anantys.ops` narrows Bash to `mkdir`, `git`, `ls`; `allowed_tools:` with an
underscore is valid YAML, is ignored, and leaves that narrowing unset. The skill
still loads. The grant does not. Nothing in this repo, and nothing in the
loader, said a word about it before this gate.

## A well-shaped grant that still bounds nothing

`Name(scope)` is well-shaped on an agent and silently loses its scope there.
A skill's `allowed-tools` entries are permission rules the runtime keeps whole,
so `Bash(git diff:*)` really does reject `git push`. An agent's `tools:` is a
set of tool *names*: the runtime parses each entry into a name and a scope,
keeps the name, and discards the scope for every tool except the one that
spawns agents — where the scope becomes the list of allowed agent types.

So `tools: ["Bash(git diff:*)", "Read"]` resolves to the whole `Bash` tool.
The subagent holds unrestricted shell, and the frontmatter that documents the
restriction is the audit record that it was imposed. `anantys.code-auditor`
carried five such grants and `claude plugin validate` was happy with all five:
a scope that is valid, parsed, and thrown away leaves no trace to check.

There is no agent-level field that narrows this. `disallowedTools` on an agent
is documented as *"ignored if `tools` is set"*, so the two cannot be combined.
The honest spelling is bare `Bash` with the bound in prose — which is why the
role is now one of the six `check_tool_grants.py` names in its bare-`Bash`
warning rather than silently exempt from it. The same five grants are still
open on PR #63 and PR #13, which are not ancestors of this branch.

## Scope

`check_platform.py` checks spelling and shape: that every frontmatter key is one
the loader recognizes, and that every tool identifier is `Name`, `Name(scope)`,
or `mcp__server__tool`. It deliberately does **not** carry a list of real tool
names — that list is not ours to maintain and would be wrong within a release.
`NotARealTool` is well-shaped and passes. The typo classes above are the ones
that actually occur, and they are all detectable without a registry.

The grant list is read across every indented line YAML lets it wrap onto.
`anantys.ops` declares twelve grants on one 500-character line, so wrapping it —
into a block sequence, or a flow sequence broken over two lines — is the obvious
thing to do with it, and both forms are valid YAML the loader says nothing about.
A shape check that reads only the key's own line iterates nothing on either one
and prints `0 error(s)`: this gate's own silent-drop failure, in the half of it
that exists *because* the loader is silent. A key declared with nothing under it
gets the same treatment for the same reason — an empty grant list is
indistinguishable from an absent one, and it must not read as clean. The
line-wise reading is not unique to this file; `check_tool_grants.py` resolves
`allowed-tools:` the same way, and whoever lands there owns that half.

The gate runs non-strict in CI. `--strict` currently fails on a pre-existing
missing-author warning in the manifests; those two files are under contention in
the open queue, so the fix belongs with whoever lands there, not here.
