# What landing the queue actually costs

Measured 2026-10-10 against the 30 open pull requests and re-measured 2026-10-14
against 48, so that the next person to price this does not re-derive it from the
shape of the branches.

## The version scalar is free; the lines next to it are not

`plugin.json` and `marketplace.json` are the repo's highest-churn files, and the
version scalar in them is the line every content branch rewrites. That makes them
look like the thing the queue contends over. The scalar itself is not: 44 of 48
heads make the *identical* `0.6.0` → `0.6.1` edit in both files, and git merges
two branches that write the same line identically without asking.

What does cost is a branch that edits a line **inside the same hunk**. Four do,
and they carry the whole manifest conflict surface:

| head | what it puts in the version hunk | siblings it conflicts with |
|---|---|---|
| `the-command-name-is-not-the-skill-name` | rewrites `description`, the next line | 33 |
| `retest-knows-what-was-fixed` | names `0.7.0`, not the queue's `0.6.1` | 33 |
| `one-version-one-home` | *deletes* the scalar from `marketplace.json` | 33 |
| `the-gates-land-together` | added an `author` block after it | 30 → **3** |
| each of the other 44 heads | the identical bump, nothing else | 4, 3, or **0** |

123 pairwise manifest edges over the queue; 14 heads have none at all. Folding all
48 costs **11** hand resolutions with those four last and **13** with them first —
of the 11, four are in a manifest and seven are prose or script. The contended
content file is `skills/anantys.design/SKILL.md`, then `scripts/check_plugins.py`.

`author` is not a field `check_plugins` requires — `name`, `version` and
`description` are. Dropping those three lines took this branch from 35 conflicting
siblings to 9, and from 30 manifest conflicts to 3, with all nine gates green. A
manifest is four lines; everything optional you put in it is adjacent to the one
line the whole queue has to touch.

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

The tag buys that back only while the queue names **one** value, and as of
2026-10-14 it names three: `0.6.0` (15 heads, untouched), `0.6.1` (32) and `0.7.0`
(one). Nothing checks this — `check_version_bump` reads a single checkout and
cannot see a sibling. It is a convention held by whoever opens the next branch:
name what the queue already names, and put nothing else on those lines.

## Where this was measured wrong before

Earlier passes priced pairwise conflicts with `--merge-base main` pinned for every
pair. A pairwise count over-reports a fold: once a branch lands, the next branch
merges against the moved `main`, not against `main`. And a fold that *aborts* a
conflicting merge instead of resolving it drops that branch's content from every
later merge, hiding the conflicts it would have caused. Resolve and continue, or
report the number as the lower bound it is.
