# The gate is a merge subject

`origin/main` has no `scripts/` directory. Every checker in this repo lives only on
unmerged branches, and a branch that wants one copies it forward — so the gates have
been forking quietly for the length of the queue.

Measured on 2026-10-18, over 85 remote heads, by `scripts/gate_drift.py`:

| script | heads | versions | forked pairs | conflict | test-conflict | clean |
|---|---|---|---|---|---|---|
| `check_plugins.py` | 13 | 7 | 52 | 36 | 3 | 13 |
| `check_tracked_ignored.py` | 13 | 5 | 50 | 19 | — | 31 |
| `check_tool_grants.py` | 10 | 7 | 24 | 19 | — | 5 |
| `check_platform.py` | 11 | 4 | 22 | 16 | — | 6 |
| `check_version_bump.py` | 9 | 3 | 20 | 13 | — | 7 |
| `pr_landing_order.py` | 9 | 5 | 19 | 13 | 6 | — |
| `check_ci_coverage.py` | 9 | 3 | 12 | 6 | — | 6 |
| `check_delegation_grants.py` | 9 | 2 | 12 | 6 | — | 6 |
| rest | — | 1 each | 2 | 2 | — | — |
| **total** | | | **213** | **123** | **9** | **81** |

A *forked* pair is two carriers holding different content with no ancestry to order
them: each edited the gate independently, and git has no basis for preferring one. 52
of the 62 differing `check_plugins.py` pairs are forked, so this is the normal case
here, not the exception.

## The result is negative, and that is the useful part

Of the 81 pairs where both the gate and its test file merged clean — git silently
assembling a checker no author wrote, reviewed, or ran — **zero fail the merged tests**.
Not one. The divergence in this queue is expensive and entirely loud.

So the landing order is not a correctness question for the gates. A reviewer can take
these heads in any sequence without a checker going quietly wrong underneath them. What
the queue actually owes is **132 hand resolutions** (123 + 9), concentrated in two files
that thirteen heads each carry a different version of.

The first run of this sweep reported 51 silent breakages. All 51 were the harness: it
invoked the tests as `python3 -m unittest scripts.test_x`, and the test modules import
their subject as a sibling, so every gate failed everywhere — including on its own head.
A per-head baseline is therefore not a refinement of this tool, it is the tool: a verdict
about what a *merge* broke is worthless without the measurement of what was already red.
`verdict()` takes `solo` for exactly this, and `red-alone` is a distinct outcome from
`broken` for exactly this.

## Passing is not certification

The merged test file is itself a merge. Two test modules that each cover their own
author's branch do not between them cover the union, so a clean verdict means "no
evidence of breakage" — the strongest claim available without writing the tests nobody
has. The number worth trusting is the conflict count, which is a fact about the text.

## The cost is quadratic in carriers

Pairs grow as the square of the carrier count. `check_plugins.py` at 13 heads is 52
forked pairs; at 20 it would be roughly 120. Every new branch that copies a gate forward
rather than rebasing onto a landed one pays into that, and nothing in CI can see it,
because CI measures one head.

The remedy is not a gate. It is to land the gates first — any single infra head makes
`scripts/` real on `main`, and every later branch then edits one canonical copy instead
of forking a thirteenth.

    python3 scripts/gate_drift.py
    python3 scripts/gate_drift.py --file check_plugins.py
