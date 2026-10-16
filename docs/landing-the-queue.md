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

## A clean merge is not a green merge: the on-invoke budget is first-come-first-served

Everything above prices the queue in hand resolutions. That is one currency.
`check_cost` on this branch bills a second one — `ON_INVOKE_MAX = 12_000` tokens
per component — and the two point in **opposite** directions, because the budget
is spent on one shared file that nearly half the queue appends to.

`anantys.qa` measures **8.6k** on `main`: 72% of the ceiling consumed before any
branch lands, and 3.4k left for the twelve open heads that add to it. One head is
already over on its own (`a-green-retest-is-not-a-fix`, 725 lines, **12.8k**); two
more sit inside 5% of the line (`qa-coverage-denominator` 11.8k,
`reset-targets-are-declared` 11.4k). Those two **pass individually and merge
cleanly, and together they are 14.7k.**

Folded in ascending PR order onto `main`, taking only the merges that need no hand
resolution:

| merge (all conflict-free) | `anantys.qa` on-invoke |
|---|---|
| `main` | 8.6k |
| `+ browser-capability-contract` | 9.2k |
| `+ qa-coverage-denominator` | **12.5k — over** |
| `+ reset-targets-are-declared` | 15.3k |
| `+ not-found-is-not-absent` | 16.2k |
| `+ a-minted-id-has-no-witness` | 16.7k |
| `+ the-companion-path-the-role-can-open` | 16.8k |

Six merges, **zero** hand resolutions, and the gate on this branch errors from the
second one onward. Not a prediction — `main` + this branch + those first three
heads is a clean four-way merge, and `python3 scripts/check_plugins.py` on it says
`error: anantys.qa: 15300 tokens on invoke (> 12000)`. The conflict-minimal order
is the one that reddens `main`, and a fold priced only in resolutions reports this
path as free.

## The remedy is a head, and it is the oldest one open

`qa-skill-progressive-disclosure` (PR #5, open 20 days) splits `anantys.qa/SKILL.md`
from 513 lines to 125 with the detail in `reference/` topics. The loader charges a
companion **nothing** and the role body on invoke, so `anantys.qa` drops **8.6k →
1.9k**: the ceiling goes from 3.4k of headroom to 10.1k, and every one of the twelve
heads fits.

It is not free. Landing it first turns 2 of those 12 clean merges into 10
conflicts, because it relocated the prose they edit. But those resolutions are not
new work — resolving one means putting that head's paragraphs in the `reference/`
topic rather than in `SKILL.md`, which is **exactly** what `check_cost`'s own
remedy line tells each of them to do, and what each would have to do anyway to get
back under 12k. The two orders cost the same restructuring. One charges it as a
conflict a human resolves while merging; the other charges it as a red gate on
`main`, on a merge that conflicted with nothing, attributed to whichever branch
happened to be second.

Land PR #5 before the `anantys.qa` heads.

Re-measure before citing any number above — it is a property of the heads as they
stand, and `--plugin-dir` reads a worktree, not a ref:

```bash
P=$PWD/plugins/anantys-team-agents
claude --plugin-dir "$P" plugin details anantys-team-agents
```

## A resolution count is not a resolution size, and one head holds most of it

Every one of the 48 open heads merges into `main` **clean** — 48 of 48, no
exceptions. The queue does not contend with what shipped; it contends with itself.
So the only number that ranks heads is how many *siblings* each one conflicts with.
Measured over all 1,128 pairs:

| head | conflicting siblings | what the conflict is in |
|---|---|---|
| `the-product-without-the-scaffolding` (#63) | **36** | content — every skill, both agents, the README |
| `the-command-name-is-not-the-skill-name` (#72) | 34 | the manifest `description` line |
| `retest-knows-what-was-fixed` (#73) | 33 | the manifest version scalar |
| `one-version-one-home` (#66) | 33 | the manifest version scalar |
| `the-whole-queue-lands` (#60) | 16 | `scripts/` |
| `qa-skill-progressive-disclosure` (#5) | 13 | relocated `anantys.qa` prose |
| 5 heads | 0 | — |

The section above named the three manifest heads as carrying "the whole manifest
conflict surface". They do — and a manifest conflict is one line. #63 outranks all
of them, and its edges are not the manifest: it makes the same `0.6.0` → `0.6.1`
bump 44 other heads make, and **35 of its 36 conflicts involve a content file**,
one is manifest-only. The contended paths are the product itself —
`anantys.qa/SKILL.md` in 15 of them, `README.md` in 12, `anantys.ops/SKILL.md` in
12, `review`/`design`/`debug` in 10 each.

Fold the other 47 onto `main` in ascending PR order and 22 merge with no hands (a
lower bound, per the next section). Then merge #63: one merge, **13 files, 33
conflict hunks** — the two agents, all five skills, all four templates,
`TEAM-CONTRACT.md` and the README. That is what "11 resolutions" buys you when the
count is the only thing counted.

This is PR #5's trade-off at eight times the size, and unlike #5 the restructuring
is not work those heads would have to do anyway. So decide #63 before pricing any
order: land it first and 36 heads rebase their prose into relocated files, land it
last and one human re-does the relocation by hand, or close it and the 22 product
heads land on `main`, where they are already clean. Ordering the other 47 is noise
beside that one choice.

```bash
# conflict degree per head, over all pairs
f=$(mktemp); gh pr list --state open --limit 60 \
  --json number,headRefName --jq '.[] | "\(.number) \(.headRefName)"' > "$f"
while read -r na ra; do deg=0
  while read -r nb rb; do [ "$na" = "$nb" ] && continue
    git merge-tree --write-tree "origin/$ra" "origin/$rb" >/dev/null 2>&1 || deg=$((deg+1))
  done < "$f"; echo "$deg $na $ra"
done < "$f" | sort -rn
```

Read that loop before reusing it: `while read` is deliberate. `for a in $refs`
does not split on newlines under zsh — it iterates **once**, over the whole list,
and reports a degree for a ref that does not exist.

## Where this was measured wrong before

Earlier passes priced pairwise conflicts with `--merge-base main` pinned for every
pair. A pairwise count over-reports a fold: once a branch lands, the next branch
merges against the moved `main`, not against `main`. And a fold that *aborts* a
conflicting merge instead of resolving it drops that branch's content from every
later merge, hiding the conflicts it would have caused. Resolve and continue, or
report the number as the lower bound it is.
