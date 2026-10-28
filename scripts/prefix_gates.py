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

**What the first full run found, and the number is not the one it was built for.** Over
89 open heads and 9 usable gates: no gate needed three or more heads, one was red on the
incoming head alone, and the walk reached **20 merges**. The other 69 heads stopped on a
conflict and no verdict above covers any of them — which makes the headline a statement
about the first fifth of the queue, and the *reach* the result worth reading. So the
report prints the reach before the excuses, and the conflict histogram as its second
output rather than a footnote:

  * `anantys.qa/SKILL.md` is in 41 of the 69 stops and is the *only* file in 26 of them.
    Three fifths of the queue's hand-adjudication cost is one file, and most of that is
    one reviewer reading one file.
  * The two manifests appear in 4 stops and in none of them alone. Nine sessions priced
    the version convention as the queue's landing cost; landed in sequence it is never
    the decision a stop is waiting on.
  * 7 stops are `check_plugins.py` + `check_tool_grants.py` + `test_check_plugins.py`
    together — a tenth of the cost is the gates forking, not the product.

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
in the report, because a sweep that silently drops five of fourteen gates reads as
fourteen gates clearing the queue.
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


def landing_order(share: str, fold_share: float) -> list[str]:
    """Open heads that touch `share`, folds dropped, oldest tip first.

    Open PRs rather than every ref, for `pair_gates.open_heads`'s reason: a merge order
    is a question about work that will land, and a closed PR is a ruling. Folds are
    dropped for its other one — a fold already contains its siblings, so landing it
    *and* them is not an order anyone performs, and it would charge the prefix with
    every line in the queue at whichever k it happens to sit at.
    """
    heads = pg.open_heads()
    if not heads:
        return []
    sets = {h: pg.writes(h, share) for h in heads}
    skip = pg.folds(sets, fold_share)
    return gm.by_tip_date([h for h, s in sets.items() if s and h not in skip])


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
    may merge at some k' > k once the sibling it collided with has landed. Over the 89
    open heads here, five retry passes over the skipped set gained **zero** heads on the
    first pass and the loop stopped there. These are not order-sensitive collisions that
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
) -> str:
    """Rows ordered by subset size, descending — the unreachable cells first."""
    out = []
    skipped = sum(stops.values())
    composite = [f for f in findings if not f["alone"] and len(f["subset"]) >= 3]
    pairs = [f for f in findings if not f["alone"] and len(f["subset"]) == 2]
    solo = [f for f in findings if f["alone"]]
    if composite:
        out.append("gates needing three or more heads together — unreachable from any other sweep:")
        for f in sorted(composite, key=lambda f: -len(f["subset"])):
            out.append(f"  {f['gate'].removeprefix('check_')} — first red at merge {f['k']}")
            out.append(f"    smallest subset shown ({len(f['subset'])} heads, a ceiling):")
            out.extend(f"      {r}" for r in f["subset"])
    else:
        out.append("no gate needed three or more heads together")
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
    ap.add_argument("--share", default="plugins", help="heads must touch a file under this path")
    ap.add_argument("--limit", type=int, default=0, help="stop after this many heads")
    ap.add_argument("--fold-share", type=float, default=0.4, help="write-set width that marks a fold")
    ap.add_argument("--no-reduce", action="store_true", help="report first-red without reducing")
    args = ap.parse_args(argv)

    order = landing_order(args.share, args.fold_share)
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

    print(report(findings, landed, stops, excluded, len(order)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
