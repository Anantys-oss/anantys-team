#!/usr/bin/env python3
"""Assemble two heads onto main and run the gates on the result.

Every sweep this repo has is one-dimensional. CI runs a head's own gates against its
own tree. `gate_matrix.py` runs *these* gates against each head's tree. `gate_power.py`
runs them against mutations of `main`. All three measure one head at a time, and a
queue 67 deep does not land one head at a time — it lands them in some order, and each
merge hands the next one a tree neither author wrote.

That tree is where a whole class of defect lives and cannot be seen from anywhere else:

  * `git merge-tree` reports a pair clean when both heads add a line to the same list,
    because adding two different lines to one list is not a textual conflict. The
    assembled frontmatter then carries the key twice. The fold branches found exactly
    this (`anantys.debug` with three `allowed-tools` lines) — as a property of folding
    all 26, which tells a reader the fold is broken and not which merge broke it.
  * A head may satisfy a gate by a route a sibling removes. Neither diff touches the
    other's files, `merge-tree` is clean, both pushes are green, and the gate goes red
    on the first `main` that holds both.

So the cell is the *pair*, and the verdict worth printing is narrow: both heads green
alone, red together. A pair that was already red alone is a finding `gate_matrix.py`
owns, and repeating it here is how a 500-row table teaches a reader to skip the table.

    python3 scripts/pair_gates.py                 # every open-PR pair sharing a role file
    python3 scripts/pair_gates.py --limit 40      # the first 40 pairs, for a timing probe
    python3 scripts/pair_gates.py --share docs    # pairs sharing a file under docs/ instead

The subject is built with two real merges, not an overlay: an overlay would silently
pick a winner per file, which is the thing being measured. The gates come from *this*
checkout, so a gate being edited here is the one doing the ruling.
"""

from __future__ import annotations

import argparse
import itertools
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

import gate_matrix as gm

ROOT = gm.ROOT
BASE = "origin/main"
#: Shared edits to these are excluded from pair selection, not from the assembly.
#:
#: Both manifests carry the same version field, so nearly every head touches both: 903
#: and 990 of the 1371 overlapping pairs here overlap *only* there. They are also the
#: one shared edit already measured — 38 of 41 heads bump to the same value, and
#: `merge-tree` resolves identical changes without an edge. Selecting on them would
#: spend the sweep re-deriving a known number. A pair that shares a role file *and* the
#: manifest is still measured with the manifest in it.
VERSION_HOMES = (
    ".claude-plugin/marketplace.json",
    "plugins/anantys-team-agents/.claude-plugin/plugin.json",
)


def open_heads() -> dict[str, int]:
    """Remote head -> PR number, for open PRs only.

    Not `for-each-ref`: `gate_matrix.py` sweeps every ref because a gate's verdict on
    any tree is information. A *merge order* is only a question about work that will
    land, and a closed PR is a ruling — pairing its head with a live one invents a
    merge nobody will perform.
    """
    done = subprocess.run(
        ("gh", "pr", "list", "--state", "open", "--limit", "500", "--json", "number,headRefName"),
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode:
        return {}
    import json

    return {f"origin/{p['headRefName']}": p["number"] for p in json.loads(done.stdout)}


def writes(head: str, share: str) -> set[str]:
    """The files `head` adds or changes under `share`, excluding the version homes."""
    out = gm.git("diff", "--name-only", f"{BASE}...{head}", "--", share)
    return {f for f in out.splitlines() if f and f not in VERSION_HOMES}


def stacked(ancestor: str, descendant: str) -> bool:
    """True when `descendant` already contains `ancestor`'s commits.

    `gm.git` cannot answer this: it reports failure as an empty string, and
    `--is-ancestor` says what it means in the exit code and prints nothing either way.
    """
    return (
        subprocess.run(
            ("git", "merge-base", "--is-ancestor", ancestor, descendant),
            cwd=ROOT,
            capture_output=True,
        ).returncode
        == 0
    )


def folds(sets: dict[str, set[str]], share: float = 0.4) -> set[str]:
    """Heads touching more than `share` of every file the queue touches — the folds.

    A fold branch overlaps everything, so it pairs with everything, and the pair is not
    a merge order anyone will run: the fold already contains the sibling. Detected by
    the shape of the write set rather than by a list of branch names, because the next
    fold will be spelled differently and the property is what disqualifies it.

    Width, not set containment. The first version of this called a head a fold when its
    write set strictly contained three or more other heads' sets, which dropped 25 of
    48 heads — including two-file ones. In a queue where 67 heads edit the same six
    role files, containing three singletons is what a two-file PR does by accident, so
    containment counts coincidences of a narrow file universe.

    Width separates cleanly here, which is why the knob has a number it can defend: the
    open heads' widths are 22, 22, 18, 18, 8, 8, 6, 6, … against a universe of 44. The
    default sits in the gap between 18 and 8, and the four it drops are the branches
    whose stated purpose is to carry the others. If a later queue closes that gap, this
    number is a guess again and the sweep should say so rather than pick a side.
    """
    universe = len(set().union(*sets.values())) if sets else 0
    return {h for h, s in sets.items() if universe and len(s) > share * universe}


def assemble(tree: Path, refs: tuple[str, ...]) -> str:
    """Merge `refs` onto BASE in `tree`. Returns "" on success, else what went wrong.

    The overlay directories are removed first and the merge runs before the gates are
    copied back in: `main` tracks neither, so a copy left in place turns every head
    that adds `scripts/` into "untracked working tree files would be overwritten" —
    a merge failure that is this tool's own and would be reported as the pair's.
    """
    for name in gm.OVERLAY:
        subprocess.run(("rm", "-rf", str(tree / name)), check=False)
    if subprocess.run(
        ("git", "checkout", "--detach", BASE, "--quiet"), cwd=tree, capture_output=True
    ).returncode:
        return f"{BASE} will not check out"
    subprocess.run(("git", "reset", "--hard", BASE, "--quiet"), cwd=tree, capture_output=True)
    for ref in refs:
        done = subprocess.run(
            ("git", "merge", "--no-edit", "--quiet", ref),
            cwd=tree,
            capture_output=True,
            text=True,
            check=False,
        )
        if done.returncode:
            subprocess.run(("git", "merge", "--abort"), cwd=tree, capture_output=True)
            return f"conflict merging {ref}"
    return ""


def verdict(cells: dict[str, gm.Cell]) -> set[str]:
    """The gates that failed, named. Empty set reads as green *and* as unmeasured."""
    return {n for n, c in cells.items() if c}


def pair_only(
    a_failed: set[str], b_failed: set[str], pair_failed: set[str]
) -> set[str]:
    """The gates red on the assembled pair and green on each head alone.

    The subtraction is per *gate*, and the first version of this subtracted per *head*:
    a pair was skipped entirely if either head was red on anything. That discarded 9 of
    the first 9 heads measured, because two gates here are red on almost every head in
    the queue — `check_doc_actions` on 76 of 78, and `check_version_bump` on any head
    that changes content without bumping the manifest. Both are owned findings. Letting
    either veto the whole head means the sweep can only run in a queue that is already
    green, which is not the queue a merge order is needed for.
    """
    return pair_failed - a_failed - b_failed


def report(
    singles: dict[str, set[str]],
    results: dict[tuple[str, str], tuple[str, dict[str, gm.Cell], set[str]]],
) -> str:
    """Only gates that are green on both heads apart and red on the pair, plus tallies.

    The tallies are not decoration. A sweep that prints "no pair-only failures" after
    skipping every pair as conflicting has reported nothing and reads as a clean bill.
    """
    out, new, conflicted, measured = [], [], 0, 0
    for (a, b), (why, cells, shared) in sorted(results.items()):
        if why:
            conflicted += 1
            continue
        measured += 1
        if gates := pair_only(singles.get(a, set()), singles.get(b, set()), verdict(cells)):
            new.append((a, b, {g: cells[g] for g in gates}, shared))
    if new:
        out.append("gates green on each head apart, red on the pair:")
        for a, b, gates, shared in new:
            out.append(f"  {a}\n  + {b}")
            out.append(f"    shares: {', '.join(sorted(shared))}")
            # The sentence, not just the gate's name. Reading a pair-only cell back by
            # hand costs a two-merge worktree per row, and nine rows here turned out to
            # be one finding — an additive token budget — which the message says and
            # the gate's name cannot. `gate_matrix.py` learned this and this file
            # dropped it: a sweep's rows are its output, so they carry the finding.
            for g, cell in sorted(gates.items()):
                out.append(f"    {g.removeprefix('check_')}: {getattr(cell, 'why', '')}")
    else:
        out.append("no gate is red on a pair that was green on both heads apart")
    out.append(
        f"\n{len(results)} pair(s) selected — {measured} assembled, "
        f"{conflicted} would not merge, {len(new)} with a pair-only failure"
    )
    # Which gates could never produce a finding here, and on how many heads. Without it
    # a green sweep looks like 9 gates clearing the queue when it was 7.
    blind = Counter(g for failed in singles.values() for g in failed)
    if blind:
        worst = ", ".join(
            f"{g.removeprefix('check_')} ({n}/{len(singles)} heads)" for g, n in blind.most_common()
        )
        out.append(f"already red alone, so unusable as a pair signal on those heads: {worst}")
    return "\n".join(out)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--share", default="plugins", help="pairs must share a file under this path")
    ap.add_argument("--limit", type=int, default=0, help="stop after this many pairs")
    ap.add_argument(
        "--fold-share", type=float, default=0.4, help="fraction of touched files that marks a fold"
    )
    args = ap.parse_args(argv)

    heads = open_heads()
    if not heads:
        print("no open PRs to pair (is `gh` authenticated?)", file=sys.stderr)
        return 1
    sets = {h: writes(h, args.share) for h in heads}
    skip = folds(sets, args.fold_share)
    live = sorted(h for h, s in sets.items() if s and h not in skip)

    selected = []
    for a, b in itertools.combinations(live, 2):
        shared = sets[a] & sets[b]
        if not shared:
            continue
        # Ancestry, not the PR body's word for it: a stacked head already contains its
        # base, so the "pair" is one landing and its gates ran as the descendant alone.
        if stacked(a, b) or stacked(b, a):
            continue
        selected.append((a, b, shared))
    if args.limit:
        selected = selected[: args.limit]
    if not selected:
        print(f"no two open heads share a file under {args.share}/", file=sys.stderr)
        return 1

    names = gm.gates()
    needed = sorted({h for a, b, _ in selected for h in (a, b)})
    with tempfile.TemporaryDirectory() as tmp:
        tree = Path(tmp) / "pair"
        gm.git("worktree", "add", "--detach", str(tree), "HEAD")
        try:
            singles = {}
            for h in needed:
                # A head that will not merge onto `main` alone was never green on any
                # gate, so every gate is marked red for it: anything its pairs fail is
                # inherited, not pair-only, and crediting it here would be this tool
                # reporting a merge conflict as a semantic finding.
                singles[h] = set(names) if assemble(tree, (h,)) else verdict(gm.check(tree, names))
            results = {}
            for a, b, shared in selected:
                why = assemble(tree, (a, b))
                results[(a, b)] = (why, {} if why else gm.check(tree, names), shared)
        finally:
            gm.git("worktree", "remove", "--force", str(tree))

    print(report(singles, results))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
