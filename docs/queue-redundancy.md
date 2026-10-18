# The queue contains itself

Measured 2026-10-18 against `main` at `0ff88da4`, over the 77 heads under
`refs/remotes/origin/koan/`. Reproduce with:

```
python3 scripts/queue_redundancy.py
```

Every row below is a set relation over patch content, and the ones marked
`[ancestor]` are also a fact about the commit graph (`git merge-base
--is-ancestor`). Nothing here is a judgement about which branch is better.

## What the measurement found

| | |
|---|---|
| heads under `origin/koan/` | 77 |
| open pull requests | 63 |
| heads with no pull request | 14 |
| heads whose patch another head fully contains | 22 |
| pairs of heads with identical patches | 1 |
| near-duplicate pairs (added-line jaccard ≥ 0.6, neither containing the other) | 25 |

Matching is verbatim, so all of those are **floors**. A rule one branch
reworded reads as absent on the other, which can only under-report.

## Closeable with no content loss

Five open pull requests have their entire substantive content inside another
open pull request, with ancestry to prove it. Merge the right-hand one and the
left-hand one has nothing left to land.

| contained | container | evidence |
|---|---|---|
| #26 `verify-the-assembled-queue` | #58 `the-order-is-not-the-cost` | **the same commit**, `6e27bfdd` |
| #26, #58 | #78 `the-fold-must-prove-it-carries-them` | ancestor |
| #26, #58, #78 | #89 `a-fold-is-a-prefix` | ancestor of #26/#58; #78's content is 1402 of its 1405 lines |
| #5 `qa-skill-progressive-disclosure` | #90 `a-split-needs-a-router` | ancestor |
| #77 `the-loader-is-the-first-gate` | #79 `the-loader-names-what-it-exposes` | ancestor |

The first four rows are one finding: **`scripts/fold_coverage.py` and
`scripts/pr_landing_order.py` are shipped by four separate open pull
requests**, touching the same five paths. #26 and #58 are not merely similar —
they are two pull requests opened on one commit. #89 is the tip of the chain:
the three lines #78 adds that #89 does not are print-format lines #89 replaced
with a richer report, and #89 adds 44 of its own on top.

Order matters in one direction only: closing a contained pull request **before**
its container merges destroys the work. Ancestry says the descendant holds the
content; it never says the content is wanted.

## Needs a ruling, not a close

These pairs overlap heavily without either containing the other — one rule
written twice, in two wordings. Neither is free to close; a human picks the
wording. Grouped by the gate they are both trying to be:

| family | heads | jaccard |
|---|---|---|
| plugin/marketplace manifest validation | #6, #45, `the-marker-and-the-match`*, `an-unlisted-tree-is-ungoverned`* | 0.63 – 0.78 |
| loader-first CI gate | #29, #52, #59, #76, #84, `an-absent-grant-is-the-widest-one`* | 0.62 – 0.97 |
| tool-grant coherence | #11, #47 | 0.62 |
| queue-landing tooling | #26, #58, #78, #89, `a-zero-that-can-still-be-merged`*, `the-trim-is-not-the-regression`* | 0.73 – 1.00 |

`*` has no open pull request.

## Heads no pull request exposes

Fourteen, including the two largest trees in the queue:
`the-product-is-the-reviewable-unit` (6,850 lines) and `the-fold-the-gates-accept`
(5,768). Both are folds — they contain 9 and 10 other heads respectively — and
neither is reachable from the pull request list. Any report that enumerates the
queue by reading open pull requests is blind to all fourteen.

## Why nothing caught this

Each of these branches passes every gate in the queue, because a gate reads one
tree and each tree is internally complete and correct. The redundancy is a
property of the *queue*, which no branch can observe: a session is handed a
problem, cannot see the 70-odd heads already open, solves it, and the queue
grows a copy. The duplication is structural, not careless — which is why the
remedy is a measurement that runs across heads rather than a rule inside one.

`scripts/queue_redundancy.py` has no exit code, deliberately. A head contained
in another is a fact about two branches, and the remedy — close one, or land the
other first — lives in neither branch's diff. A gate that failed a branch for
that would be forcing an order on changes that may not have one.
