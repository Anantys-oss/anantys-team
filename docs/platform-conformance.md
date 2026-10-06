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
