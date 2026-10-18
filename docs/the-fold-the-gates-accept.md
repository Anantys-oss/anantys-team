# The fold the gates accept

A verdict about a merge is a claim about the assembled tree, never about a branch.
This repo's queue has been folded five times and measured fifteen; what had not been
done is pointing the gates *at a fold*. This branch is that: the product fold
(`koan/the-product-the-queue-actually-wrote`, 26 product PRs) merged onto the gate
fold (`koan/a-scope-the-loader-drops`, nine checkers plus the README fix), with the
gates then run as the arbiter.

## The cross-product first

`scripts/gate_matrix.py` over every remote head, 78 × 9:

| finding | heads | owner |
|---|---|---|
| `doc_actions`: a `qa` action in the table and in no README command block | 76 | this branch's own line (#76 → #84) |
| `version_bump`: still 0.6.0 with content changed | 7 | the two-file version convention |
| `tool_grants`: `Bash(git diff:*)` on an agent scopes nothing | 3 | fixed here |
| `plugins`: `qa` over the on-invoke ceiling | 2 | PR #5's router split |
| `plugins`: always-on over 1000 tok | 2 | the roles' `description`s |
| `mcp_grants`: `update_plan` is not a `claude-in-chrome` tool | 1 | `the-browser-is-a-manifest-field` |
| `platform`: `allowed-tools` declared three times | 1 | fixed here |
| `delegation_grants`: `debug` dispatches `spec-tester` with no `Task` | 1 | fixed here |

`origin/main` is green on eight of nine. So is every branch but two. The queue is not
failing its own gates — **the fold is**, and only the fold, which is the one tree no
push has ever run them against.

## What only the assembled tree has

Three siblings each added `allowed-tools` to `anantys.debug`, one added it to
`anantys.design`. Git merged all four without a conflict: each is an independent
insertion of a new line. The loader does not union them — it keeps the **last** and
drops the rest, silently. On `debug` the surviving line was the one without `Task`, so
the fold shipped a role whose prose dispatches `anantys.spec-tester` and whose
effective grant cannot. `anantys.design`'s `disallowed-tools` narrowing was buried the
same way.

This is the failure mode a per-branch CI cannot reach, in both directions: no sibling's
tree contains the duplicate, so no sibling's green run is wrong, and the defect is
created by the merge rather than by any commit in it. A duplicate frontmatter key is
worth checking for precisely because it is the shape git never reports.

`anantys.code-auditor`'s `tools: ["Bash(git diff:*)", …]` is the second. An agent's
`tools:` is a toolset, not a permission list: the loader splits each entry into
`{toolName, ruleContent}` and discards `ruleContent` for every tool but `Task`. The
role held an unrestricted shell behind a frontmatter line that reads as read-only,
under a description promising it "writes no code". The remedy is never a tighter
scope — no scope is kept. It is `Bash` plainly, plus the restriction stated where it
can live: the prompt.

## What this tree still owes

`check_plugins` reports `anantys.qa` at 20800 on-invoke tokens against a 12000
ceiling. Inherited, not introduced — and the fix is already written, on PR #5's router
split. It cannot simply be merged in: one hunk is 860 lines of this fold's rewritten
prose against the three lines the split left behind, because the split *moves* the
prose 26 PRs then rewrote. Landing it is a redistribution of the fold's own text into
the five `reference/` topic files, by hand, and it deserves its own branch rather than
a resolution buried in a merge commit.

## Verification

- `python3 -m unittest discover -s scripts` — 457 tests, OK.
- Eight of nine gates exit 0; `check_plugins` reports the one ceiling above.
- `claude plugin install` into a sealed `HOME`, then `plugin details`: installs at
  0.7.0, inventory of 5 skills and 2 agents, always-on ~755 tok (ceiling 1000),
  `anantys.qa` on-invoke ~20.8k — the gate and the loader agree on the number.

The gates read text. The loader is the thing that ships. A fold that passes only one
of them has not been verified.
