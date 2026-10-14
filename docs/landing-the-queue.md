# What landing the queue actually costs

Measured 2026-10-10 against the 30 open pull requests, so that the next person to
price this does not re-derive it from the shape of the branches.

## The two manifests are not the conflict surface

`plugin.json` and `marketplace.json` are the repo's highest-churn files, and the
version scalar in them is the line every content branch rewrites. That makes them
look like the thing the queue contends over. They are not:

| | |
|---|---|
| conflicting pairs, `git merge-tree` over all 435 pairs | **20** |
| of those, in either manifest | **0** |
| heads declaring a version above `main`'s `0.6.0` | 22 of 30 — all of them `0.6.1` |
| distinct values named across the queue | **1** |
| hand resolutions folding all 30, union-resolved, 7 orders | **7–11** |
| of those, in either manifest | **0** in every order |

Git merges two branches that write the same line identically without asking. The
queue agrees on `0.6.1`, so the scalar costs nothing today. The contended file is
`skills/anantys.ops/SKILL.md` (7 of the 20 pairs), then `skills/anantys.qa/SKILL.md`
(3) — prose in monolithic role files, not an integer in a four-line manifest.

## The cost the scalar does have is conditional, and one tag removes it

`check_version_bump` falls back to the merge-base when no release tag exists, and
there are none. The floor therefore moves on every merge: the moment one PR lands
at `0.6.1`, every sibling still naming `0.6.1` has `after == shipped` and the gate
*errors*. Each wave then needs its own value, re-typed in both manifests — and
*those* re-typings do conflict, because they are no longer the same line.

So the ordering of the predicted cost matters: it is charged after the first merge,
not now, and only while a tag is missing. Tag what is already on `main` and every
sibling may name the same next version again. That is one command, and it is worth
more than any landing order — across 7 fold orders the spread is 4 resolutions.

## Where this was measured wrong before

Earlier passes priced pairwise conflicts with `--merge-base main` pinned for every
pair. A pairwise count over-reports a fold: once a branch lands, the next branch
merges against the moved `main`, not against `main`. And a fold that *aborts* a
conflicting merge instead of resolving it drops that branch's content from every
later merge, hiding the conflicts it would have caused. Resolve and continue, or
report the number as the lower bound it is.
