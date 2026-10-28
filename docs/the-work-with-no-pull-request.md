# The work with no pull request

Every instrument in this repository enumerates `gh pr list`. On 2026-10-28 that population was
**123 of the 172 `koan/*` heads on `origin`**. The other **49 were pushed and never got a PR** —
28% of the work ever done here, invisible to every fold, every landing-order script and every
gate×head sweep, because none of them can name a branch that no PR points at.

Measured with `git branch -r` minus the `headRefName` of every PR in any state:

| population | count |
|---|---|
| `koan/*` heads on `origin` | 172 |
| heads with a PR (open, merged or closed) | 123 |
| **heads with no PR** | **49** |

Of those 49, **26 carry product lines that appear on no PR'd head** — 493 lines in total, scored by
matching each head's added lines (over `plugins/`, `README.md`, `.claude-plugin/`, `docs/`) against
the union of every PR'd head's product text. That match is a floor: it under-reports rewording and
cannot over-report, so a high score proves inclusion and a low score is a prompt, not a verdict.

This branch folds the 19 of those heads that are product-only, ≥25% unique and ≤3 commits — 26
commits, 14 applied clean, 12 needing resolution, 3 already present. It is not the whole 49: the
four heads with 100+ commits are folds of folds, 2–5% unique, and belong to whoever owns them.

## What the fold found that no contributing branch could

A branch sees its own diff. Three conflicts here exist only in the assembled tree.

### 1. The always-on ceiling admits neither convention

`check_plugins.py` caps the plugin's always-on cost at **1,000 tokens** — the column every session
pays before invoking anything, which the loader charges to the roles' frontmatter. `main` measures
716. Two orphan conventions each add to that column, and measured with the real loader
(`claude --plugin-dir <dir> plugin details`, claude 2.1.278):

| tree | always-on |
|---|---|
| `origin/main` | 716 |
| + `when_to_use` on five skills, nothing else | 1,197 |
| + mutation disclosures on seven roles, no `when_to_use` | 1,034 |
| this fold (both) | 1,515 |
| this fold, both trimmed of their overlap | 1,379 |

The ceiling admits **neither convention alone**. Trimming the duplicated routing sentence out of
every `description` — the obvious remedy, since `when_to_use` now carries the triggers — recovers
136 tokens and leaves it 379 over. Twelve open heads add `when_to_use`; one adds the disclosures.
Whichever lands first reddens the other for a number it did not move, and hands it a remedy that
does not reach. The number that has to move is `ALWAYS_ON_MAX`, or the role count — not the prose.

### 2. An inline `mcpServers` object in `plugin.json` is dropped

`koan/the-browser-is-a-manifest-field` is right that the browser should be a manifest field rather
than an operator chore, and wrong about where to write it. Measured on claude 2.1.278:

| where the server is declared | `claude plugin details` reports |
|---|---|
| `plugin.json`, inline `"mcpServers": { … }` | `MCP servers (0)` |
| `.mcp.json` at the plugin root | `MCP servers (1)  claude-in-chrome` |
| `.mcp.json` + `"mcpServers": "./.mcp.json"` in `plugin.json` | `MCP servers (1)  claude-in-chrome` |

So this fold ships the `.mcp.json` form. The plugin now provides the browser it grants; the roles'
runtime `tabs_context_mcp` check stays the hard gate, as `README.md` says.

### 3. `check_mcp_grants.py` cannot see either working form

The gate reads `plugin.json`'s `mcpServers` key and nothing else, so it reports this tree as
`declares no mcpServers` while the loader reports one — and given the pointer form it raises
`AttributeError: 'str' object has no attribute 'items'`, because it expects an inline object: the
one spelling that does not register. The gate is red on this branch and the error is a true
statement about the gate, not about the tree. It belongs to whoever owns that file.

## Gate status

Run with the eleven gates from `origin/koan/a-cell-is-a-finding-only-if-it-differs`, against both
this tree and `origin/main`, so inherited failures are not reported as this branch's:

| gate | main | fold |
|---|---|---|
| `check_ci_coverage` | FAIL | FAIL (inherited) |
| `check_doc_actions` | FAIL | FAIL (inherited) |
| `check_md_fences` | FAIL | FAIL (inherited) |
| `check_mcp_grants` | pass | FAIL — §2/§3 above |
| `check_plugins` | pass | FAIL — §1 above |
| the other six | pass | pass |

## The conflicting conclusions this fold had to resolve

Three heads rewrote the same `README.md` section about tool grants with mutually exclusive
conclusions, and two of them took opposite *actions* on the same frontmatter:

- `a-scoped-denial-denies-the-whole-tool` (Oct 24) **removes** every `disallowed-tools:` line,
  because the field is parsed by name only — `Bash(git push:*)` denies all of `Bash`, and every
  step of `anantys.review` is `git`/`gh`.
- `the-denial-expires-before-the-decision` (Oct 25) **keeps** them and documents that the field is
  turn-scoped, so the deny is gone by the time the confirmation phase runs.

Both facts are true and independent; only the action conflicts. The removal wins — a denial that
silently costs a role its shell is worse than no denial — and both explanations are kept, now
composed into one four-item list. `anantys.review`'s own prose, which referred to "this skill's
`disallowed-tools` deny", was stale the moment the field was removed and now says why it has none.

`anantys.ops` needed the same treatment at a smaller scale: two heads independently moved the
top-page deep-dive relative to Search Console, producing a tree with both a Phase 1b and a Phase
2b doing the same work. Phase 1b is kept, with the ordering rule that makes it correct on a first
audit.
