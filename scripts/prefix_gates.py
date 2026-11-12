#!/usr/bin/env python3
"""Land the queue one merge at a time and run the gates after each one.

`pair_gates.py` opened the right question and answered it for N=2: the tree a merge
hands the next author is where a class of defect lives that no single-head sweep can
see. Its cell is the *pair*, and its own docstring names the limit — the fold branches
found `anantys.debug` carrying three `allowed-tools` lines "as a property of folding all
26, which tells a reader the fold is broken and not which merge broke it."

A pair sweep closes that gap for defects two heads are sufficient to cause. It is
structurally blind to the ones that need three, and this repo has the shape that
produces them:

  * **Additive budgets.** `check_plugins.py` reads `scripts/role-load-baseline.txt` as a
    ratchet. Three heads can each add eight lines to a role file, pass alone, pass in
    every pair, and blow the ceiling on the third merge. The cell that holds the finding
    has no two-element subset.
  * **Counted sets.** `check_template_paths` counts templates and escaping links;
    `check_ci_coverage` counts gates against workflow steps. A count crosses its
    threshold at some *k*, and *k* is not 2 just because 2 is the number a sweep can
    afford.
  * **Last-writer frontmatter.** Two heads adding a key each is already a duplicate; a
    third makes the triple the fold branches actually hit. The pair finding and the
    triple finding are different sentences about different trees.

So the cell here is the *prefix* — `main` plus the first k heads of a landing order —
and the verdict worth printing is narrower than "red at k". A gate red at k is almost
never news: it may be red on `main` (inherited by everything), red on the incoming head
alone (`gate_matrix.py`'s finding), or red on some pair inside the prefix
(`pair_gates.py`'s). What is news is a gate whose **smallest reddening subset of the
landed heads has three or more members**, because that subset is unreachable from every
sweep this repo has. So each new failure is reduced before it is reported, and the
subset's size is printed next to it: a 2 is an acknowledgement that `pair_gates.py` owns
the row, and a 3-or-more is this tool's reason to exist.

    python3 scripts/prefix_gates.py                 # chronological landing, every open head
    python3 scripts/prefix_gates.py --limit 25      # the first 25 merges, for a timing probe
    python3 scripts/prefix_gates.py --no-reduce     # skip the reduction, report first-red only

**What the run found, and the number is not the one it was built for.** Over 127 open
heads offered and 6 of 14 gates excluded, run with `--no-reduce`: every gate that went
red went red on the **incoming head alone** — `template_fields`, `tool_grants`,
`tracked_ignored` — so the unreduced bucket is empty and there was no composition
finding to reduce. The walk reached **34 merges**. The other 93 heads
stopped on a conflict and no verdict above covers any of them — which makes the headline
a statement about the first quarter of the queue, and the *reach* the result worth
reading. So the report prints the reach before the excuses, and the conflict histogram as
its second output rather than a footnote:

  * `anantys.qa/SKILL.md` is in 45 of the 93 stops and is the *only* file in 29 of them.
    Half of the queue's hand-adjudication cost is one file, and most of that is one
    reviewer reading one file. This is the one row that held its shape as the queue grew
    from 89 heads to 132.
  * **The gates are not a tenth of the cost; they are most of what is left.** Of the 42
    files in the histogram, 23 are under `scripts/` or `.github/`. Four of them —
    `check_plugins.py`, `check_tool_grants.py`, `check_version_bump.py` and its test —
    are in 13 stops each, `pr_landing_order.py` and its test in 11, and fifteen more in
    6 apiece. All 18 `scripts/` rows have **0** in the alone column: the gates never
    fork alone, they fork as a block, so a maintainer meeting one of these stops is
    handed a dozen files at once and `.github/workflows/validate.yml` — alone in 3 — is
    the only piece of the machinery that ever asks for one decision by itself.
  * The two manifests appear in 7 and 5 stops and `marketplace.json` is alone in one of
    them. Nine sessions priced the version convention as the queue's landing cost;
    landed in sequence it is the decision a stop is waiting on exactly once in 93.

That second row is new, and it is new because the sweep was not previously allowed to see
it — see `landing_order` for the filter that hid it and the 32 heads it removed.

**The order is chronological and that is a choice, not a result.** `pr_landing_order.py`
computes an order optimised against conflicts; oldest-tip-first is the order the queue
was *written* in and the one a maintainer draining it by age performs. A cumulative
finding is a property of a *set*, so the reduced subset below is order-independent even
though the k that surfaced it is not — which is why the subset, not k, is the finding.

**The gates are the union across the queue, not this checkout's.** `gate_matrix.union`
already argues why: a gate set assembled from one branch can only ask that branch's
questions. The cost is that two heads' copies of a gate pair can be mutually
incompatible — `check_plugin_agents` imports a name from a `check_delegation_grants`
that a different head wrote — and a gate that cannot import is not a gate that failed.
Those land in the same bucket as the gates red on `main`: named, excluded, and counted
in the report, because a sweep that silently drops six of fourteen gates reads as
fourteen gates clearing the queue. Six is the measured number and it is growing — five
red on `main` (`ci_coverage`, `doc_actions`, `md_fences`, `registry`, `template_paths`)
and one that cannot import (`plugin_agents`). The walk therefore rules on eight gates,
and the clean bill at the top of the report is a claim about those eight.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

import gate_matrix as gm
import pair_gates as pg

BASE = pg.BASE


def fold_cut(sets: dict[str, set[str]], fold_share: float) -> tuple[set[str], str]:
    """The folds to drop, and the line that says whether the cut still separates.

    `pair_gates.folds` marks a head a fold when its write set is wider than
    `fold_share` of the universe, and its own docstring sets the condition for
    believing the number: the default "sits in the gap between 18 and 8", and "if a
    later queue closes that gap, this number is a guess again and the sweep should say
    so rather than pick a side." Nothing was watching the gap. A width threshold is a
    guess that reads as a measurement, and the only cheap defence is to print the two
    numbers it sits between every time it is used.

    The warning it appends is not another guess. `folds` drops a head when its width is
    *strictly* greater than the threshold, so a threshold that is less than or equal to
    the widest head it keeps is sitting exactly on an observed width rather than in a
    gap, and one file in either direction moves a branch across it. Measured at 132 open
    heads: universe 45 under `plugins`, threshold 18.0, five dropped at width 22, widest
    kept **18** — and that head is the branch named `the-whole-queue-lands`. The gap the
    default was calibrated in (18 to 8) has closed to a tie, which is the condition its
    author wrote down and nothing was checking.
    """
    universe = len(set().union(*sets.values())) if sets else 0
    skip = pg.folds(sets, fold_share)
    widths = {h: len(s) for h, s in sets.items()}
    low = min((widths[h] for h in skip), default=0)
    high = max((w for h, w in widths.items() if h not in skip), default=0)
    threshold = fold_share * universe
    line = (
        f"fold cut: {len(skip)} dropped above {threshold:.1f}"
        f" (={fold_share} x {universe} files), narrowest dropped {low}, widest kept {high}"
    )
    if skip and high >= threshold:
        line += " — the threshold sits on a kept head's width, so one file moves it"
    return skip, line


def landing_order(share: str, fold_share: float) -> tuple[list[str], str]:
    """Every open head, folds dropped, oldest tip first — and the fold cut's margin.

    Open PRs rather than every ref, for `pair_gates.open_heads`'s reason: a merge order
    is a question about work that will land, and a closed PR is a ruling. Folds are
    dropped for its other one — a fold already contains its siblings, so landing it
    *and* them is not an order anyone performs, and it would charge the prefix with
    every line in the queue at whichever k it happens to sit at.

    **Every open head, not only the ones that write under `share`.** The first version
    of this reused `pair_gates`'s selection whole, which drops a head whose write set
    under `--share` is empty. That is a *pair* criterion: two heads are worth assembling
    only if they share a file. A landing order has no such excuse — a maintainer
    draining the queue merges whatever is open, and a head that shares nothing still
    changes the tree the next one is handed. Measured at 132 open heads, the filter
    dropped **32**, and the dropped set is not a random quarter: it is every head that
    edits only `scripts/`, `.github/` and `docs/` — the gates and the instruments. Two
    of the three defect shapes this file exists for live there. `check_ci_coverage`
    counting gates against workflow steps cannot be crossed by a head under `plugins/`
    at all, and `check_plugins.py`'s role-load ratchet is a file under `scripts/`. So
    the sweep was blind to the heads carrying its own motivating examples, and printed
    "of 89 head(s) offered" where 89 was the surviving fraction and not the queue.

    `share` still sizes the fold cut, which is where it was calibrated and the one place
    a narrower universe is the right one: a fold of the role files is what makes a
    prefix meaningless, and that width is measured against the role files.
    """
    heads = pg.open_heads()
    if not heads:
        return [], ""
    sets = {h: pg.writes(h, share) for h in heads}
    skip, line = fold_cut({h: s for h, s in sets.items() if s}, fold_share)
    return gm.by_tip_date([h for h in heads if h not in skip]), line


def still_red(tree: Path, gate: str, refs: tuple[str, ...], overlay: Path) -> bool:
    """True when `refs` assemble and `gate` is red on the result.

    A subset that will not merge is not evidence that the gate needs the ref that was
    dropped, so it answers False and the reduction keeps the ref. That biases the
    reported subset *upwards* — towards 3 when 2 would do — so the size is a ceiling,
    and the report says so rather than claiming a minimum it did not prove.
    """
    if pg.assemble(tree, refs):
        return False
    return bool(pg.verdict(gm.check(tree, [gate], overlay=overlay)))


def reduce_subset(landed: list[str], trigger: str, is_red) -> list[str]:
    """The smallest subset of `landed` this could show still reddens the gate.

    Backward elimination, one ref at a time, `trigger` pinned: it is the merge that
    turned the gate red, so a subset without it is answering a different question. Not
    a true minimum — elimination is greedy and a conflicting subset reads as green — and
    the docstring above only ever claims the number is a ceiling. That is enough for the
    one distinction the report makes: at 2 the row belongs to `pair_gates.py`, above 2
    it belongs to nothing that exists.

    `is_red` is injected because the real one costs a worktree, |landed| merges and a
    gate run per trial. The elimination is the part that can be wrong, and it is wrong
    in ways a predicate stub shows and a live sweep hides.
    """
    current = list(landed)
    i = 0
    while i < len(current):
        if current[i] == trigger or len(current) == 1:
            i += 1
            continue
        trial = current[:i] + current[i + 1 :]
        if is_red(tuple(trial)):
            current = trial
        else:
            i += 1
    return current


def clear_overlay(tree: Path) -> None:
    """Delete the gate overlay from `tree` before the walk's next merge.

    `gate_matrix.check` copies `scripts/` and `.github/` in and leaves them there, which
    is right for a one-shot caller and wrong for a walk: the next head that *tracks*
    those paths meets them as untracked files and `git merge` refuses with "untracked
    working tree files would be overwritten". `pair_gates.assemble` already removes them
    for this reason and the walk merges between its calls, so it owes the same removal.

    Measured, because the symptom is indistinguishable from the subject: the first full
    run reported 72 stops, and **13 of them named no conflicting file at all** — every
    one this tool's own artifact charged to the queue. With the removal in place the walk
    lands 20 instead of 17 and no stop is nameless, which is also what a bare merge loop
    with no gates in it reported. A harness failure that reads as a finding is the only
    kind worth a named function.
    """
    for name in gm.OVERLAY:
        subprocess.run(("rm", "-rf", str(tree / name)), check=False)


def unmerged(tree: Path) -> tuple[str, ...]:
    """The files left conflicting by the merge that just failed, sorted.

    `("<no file named>",)` is kept rather than smoothed away: a merge can fail without a
    conflicted path, and when it does the stop is about the harness, not the queue.
    """
    out = subprocess.run(
        ("git", "diff", "--name-only", "--diff-filter=U"),
        cwd=tree,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.split()
    return tuple(sorted(out)) or ("<no file named>",)


def walk(
    tree: Path, order: list[str], usable: list[str], overlay: Path, reduce: bool
) -> tuple[list[dict], list[str], Counter]:
    """Merge `order` into `tree` one ref at a time, reporting each gate's first red.

    Cumulative, not re-assembled per k: the subject is one landing, so a conflict is a
    ref the maintainer would stop and adjudicate, and the walk records *which files* it
    stopped on and carries on with the tree it already has.

    **A conflicting ref is not retried, because retrying was measured to be worth
    nothing.** The obvious objection to a single pass is that a head conflicting at k
    may merge at some k' > k once the sibling it collided with has landed. Measured at
    89 open heads under the old selection, five retry passes over the skipped set gained
    **zero** heads on the first pass and the loop stopped there — and that measurement
    has not been re-run against the 127 heads now offered, so it is the one claim in
    this file still resting on the pruned queue. These are not order-sensitive collisions that
    a later tree resolves; they are two authors writing different sentences on the same
    line, and no merge order makes them agree. That is why the conflict histogram below
    is the report's second output and not its footnote: the walk's reach is set by how
    much hand adjudication the queue needs, and the histogram says where.
    """
    pg.assemble(tree, ())
    red: set[str] = set()
    findings: list[dict] = []
    landed: list[str] = []
    stops: Counter = Counter()
    for ref in order:
        clear_overlay(tree)
        done = subprocess.run(
            ("git", "merge", "--no-edit", "--quiet", ref),
            cwd=tree,
            capture_output=True,
            check=False,
        )
        if done.returncode:
            stops[unmerged(tree)] += 1
            subprocess.run(("git", "merge", "--abort"), cwd=tree, capture_output=True)
            continue
        landed.append(ref)
        now = pg.verdict(gm.check(tree, usable, overlay=overlay)) & set(usable)
        for gate in sorted(now - red):
            # The incoming head alone is `gate_matrix.py`'s cell, so a gate red there is
            # inherited by any prefix holding it and is not a composition finding.
            solo = pg.assemble(tree, (ref,))
            alone = not solo and gate in pg.verdict(gm.check(tree, [gate], overlay=overlay))
            subset = (
                [ref]
                if alone or not reduce
                else reduce_subset(
                    landed, ref, lambda refs: still_red(tree, gate, refs, overlay)
                )
            )
            findings.append(
                {"gate": gate, "k": len(landed), "ref": ref, "alone": alone, "subset": subset}
            )
            pg.assemble(tree, tuple(landed))  # restore the walk's tree
        red = now
    return findings, landed, stops


def by_file(stops: Counter) -> list[tuple[str, int, int]]:
    """Each conflicting file as (path, stops it appears in, stops it is alone in).

    Both numbers, because they answer different questions and the pair is the finding.
    The appearance count is the file's share of the queue's hand-adjudication cost. The
    alone count is how much of that share is *only* that file — a row naming one file is
    one decision for one reviewer, and a row naming ten is a wave.
    """
    appears: Counter = Counter()
    solo: Counter = Counter()
    for files, n in stops.items():
        for f in files:
            appears[f] += n
        if len(files) == 1:
            solo[files[0]] += n
    return [(f, n, solo[f]) for f, n in appears.most_common()]


def report(
    findings: list[dict],
    landed: list[str],
    stops: Counter,
    excluded: dict[str, str],
    order: int = 0,
    fold_line: str = "",
) -> str:
    """Rows ordered by subset size, descending — the unreachable cells first.

    Every finding reaches exactly one bucket. It used to reach at most one: a
    composition finding under `--no-reduce` has `alone` false and a one-element subset,
    which matched none of the three buckets and was printed nowhere, while the clean
    bill at the top still read "no gate needed three or more heads together". The one
    flag whose documented purpose is "report first-red only" was the one that reported
    nothing, and it failed *green*. The unreduced bucket exists so the arithmetic is
    visible: four buckets, and the clean bill is only claimed when the reduction ran.
    """
    out = []
    skipped = sum(stops.values())
    composite = [f for f in findings if not f["alone"] and len(f["subset"]) >= 3]
    pairs = [f for f in findings if not f["alone"] and len(f["subset"]) == 2]
    unreduced = [f for f in findings if not f["alone"] and len(f["subset"]) < 2]
    solo = [f for f in findings if f["alone"]]
    if composite:
        out.append("gates needing three or more heads together — unreachable from any other sweep:")
        for f in sorted(composite, key=lambda f: -len(f["subset"])):
            out.append(f"  {f['gate'].removeprefix('check_')} — first red at merge {f['k']}")
            out.append(f"    smallest subset shown ({len(f['subset'])} heads, a ceiling):")
            out.extend(f"      {r}" for r in f["subset"])
    elif not unreduced:
        out.append("no gate needed three or more heads together")
    if unreduced:
        out.append("red on a prefix but not on the incoming head — size unmeasured, the reduction was skipped:")
        for f in unreduced:
            out.append(
                f"  {f['gate'].removeprefix('check_')} — first red at merge {f['k']}, on {f['ref']}"
            )
    if pairs:
        out.append("\nreducible to a pair — `pair_gates.py` owns these rows:")
        for f in pairs:
            out.append(f"  {f['gate'].removeprefix('check_')}: {' + '.join(f['subset'])}")
    if solo:
        names = ", ".join(sorted({f["gate"].removeprefix("check_") for f in solo}))
        out.append(f"\nred on the incoming head alone, so `gate_matrix.py`'s rows: {names}")
    # The reach, stated before the excuses: every verdict above is about `main` plus
    # these k merges and says nothing whatever about the heads that never entered a
    # prefix. A sweep that prints "no three-head failure" without this line is claiming
    # the queue composes cleanly when it mostly refused to assemble.
    out.append(
        f"\nreach: {len(landed)} merge(s) deep"
        + (f" of {order} head(s) offered" if order else "")
        + f" — {skipped} stopped on a conflict, so no verdict covers them"
    )
    # The cut that set the denominator, printed next to it. "of N offered" is a number
    # the reader cannot check without it: the heads a filter removed before the walk are
    # exactly as uncovered as the ones that stopped on a conflict, and only one of the
    # two used to appear in the report.
    if fold_line:
        out.append(fold_line)
    if rows := by_file(stops):
        out.append("where the queue stops, by file — appearances (alone):")
        for path, n, alone in rows:
            out.append(f"  {n:4d} ({alone:3d})  {path}")
    if excluded:
        why = ", ".join(f"{g.removeprefix('check_')} ({r})" for g, r in sorted(excluded.items()))
        out.append(f"gates excluded, so they could produce no finding here: {why}")
    return "\n".join(out)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--share", default="plugins", help="the universe the fold cut is sized against")
    ap.add_argument("--limit", type=int, default=0, help="stop after this many heads")
    ap.add_argument("--fold-share", type=float, default=0.4, help="write-set width that marks a fold")
    ap.add_argument("--no-reduce", action="store_true", help="report first-red without reducing")
    args = ap.parse_args(argv)

    order, fold_line = landing_order(args.share, args.fold_share)
    if not order:
        print("no open heads to land (is `gh` authenticated?)", file=sys.stderr)
        return 1
    if args.limit:
        order = order[: args.limit]

    with tempfile.TemporaryDirectory() as tmp:
        overlay = Path(tmp) / "gates"
        overlay.mkdir()
        gm.union(gm.by_tip_date([r for r in gm.heads() if "/koan/" in r]), overlay)
        names = gm.gates(overlay)
        tree = Path(tmp) / "prefix"
        gm.git("worktree", "add", "--detach", str(tree), "HEAD")
        try:
            pg.assemble(tree, ())
            # A gate red on `main` is inherited by every prefix, and one that cannot even
            # import is not a gate that failed. Both are unusable as a prefix signal and
            # both have to be named: the alternative is a report that looks like a clean
            # bill from a sweep that was never asking.
            on_base = gm.check(tree, names, overlay=overlay)
            excluded = {
                g: ("cannot run" if "Error" in getattr(c, "why", "") else "red on main")
                for g, c in on_base.items()
                if c
            }
            usable = [g for g in names if g not in excluded]
            findings, landed, stops = walk(tree, order, usable, overlay, not args.no_reduce)
        finally:
            gm.git("worktree", "remove", "--force", str(tree))

    print(report(findings, landed, stops, excluded, len(order), fold_line))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
