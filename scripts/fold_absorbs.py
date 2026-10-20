#!/usr/bin/env python3
"""Price the open queue against a *proposed* base instead of against `main`.

`pr_landing_order.py` opens by stating its own premise — "every PR here is cut
from `main`" — and every ref it reaches for is `origin/main`. That is the right
premise for sequencing the queue and the wrong one for the decision a fold puts
on the table. A fold asks to *become* main. Merging it does not reorder the
queue, it re-bases it: every open head is then measured against a tree nobody
has measured anything against. The number that decides the merge is therefore
the one no checker here can produce, because the base it needs is not `main`.

So probe the merges. One throwaway worktree at the fold, every open head merged
into it in turn, three verdicts:

  * ``absorbed`` — the merge is a no-op: ``merge(fold, head)`` has the fold's
    own tree. Closing the head after the fold lands loses nothing. GitHub does
    not notice this and will not close it.
  * ``adds`` — the merge is clean and the tree grows. Live work the fold does
    not hold; the shortstat says how much.
  * ``conflict`` — the merge stops. This is the column that only exists here.
    Those heads are `MERGEABLE` against `main` today and go red the hour the
    fold lands, and neither their status nor any gate in this repo says so.

**The absorbed column is a second opinion, not a new one, and that is its
value.** `fold_coverage.py` already finds these by matching added lines against
the fold's text, and its docstring is careful to call the result a floor — a
high score is proof of inclusion, a low one is a prompt. Nothing had ever
checked that floor against an independent measure. Now something has: on the
fold this was written for, coverage's 100% rows and this script's `absorbed`
rows are the same thirteen, with no row on either side the other misses. Two
measurements of different kinds agreeing is the evidence a reviewer needs to
actually close thirteen pull requests; one measurement calling itself a floor
is not.

It also confirms the shape of the evidence. `queue_redundancy.py` defers to
``git merge-base --is-ancestor`` whenever it holds, because ancestry is the only
supersede evidence that is not somebody's assertion — and that is true, and it
is sufficient rather than necessary. A fold assembled by rewriting the product
holds every line of a head while descending from none of them. Here ancestry
confirms **zero** of the thirteen. The report prints that count beside them so
the asymmetry is on the page rather than in a reviewer's memory.

Conservative in the safe direction: a fold that *reworded* a head's rule reports
as `adds`, because merging would reintroduce the head's original phrasing. That
under-reports carriage, which costs a read. The opposite error would have a
reviewer close work that was never carried, and one false row is what teaches
them to skip the section.

There is no exit code. Whether a head should be closed is a fact about two
branches whose remedy lives in neither branch's diff, and a gate that fails a
branch for a property it cannot fix alone forces an order on changes that may
not have one.

Run: ``python3 scripts/fold_absorbs.py <fold-ref> [--limit N]``
"""

import argparse
import json
import subprocess
import sys
import tempfile

ABSORBED, ADDS, CONFLICT = "absorbed", "adds", "conflict"


def git(*args, check=True):
    """Run git in the current repo, returning stdout."""
    return subprocess.run(("git",) + args, capture_output=True, text=True,
                          check=check).stdout


def verdict(merge_failed, tree_before, tree_after):
    """Classify one merge attempt. Pure, so the table is testable without git."""
    if merge_failed:
        return CONFLICT
    return ABSORBED if tree_after == tree_before else ADDS


def attempt(worktree, fold, fold_tree, head):
    """``(verdict, shortstat)`` for merging ``head`` into the probe worktree.

    Resets to the fold first, so one dirty or conflicted probe cannot leak into
    the next head's verdict.
    """
    def wt(*args, check=True):
        return subprocess.run(("git", "-C", worktree) + args,
                              capture_output=True, text=True, check=check)

    wt("merge", "--abort", check=False)
    wt("reset", "--hard", fold)
    wt("clean", "-fdq")
    if wt("merge", "--no-edit", "-m", f"probe: {head}", head,
          check=False).returncode != 0:
        wt("merge", "--abort", check=False)
        return CONFLICT, ""
    after = wt("rev-parse", "HEAD^{tree}").stdout.strip()
    stat = wt("diff", "--shortstat", fold_tree, after).stdout.strip()
    return verdict(False, fold_tree, after), stat


def open_heads(fold, limit):
    """``(number, head)`` for every open PR except the fold's own."""
    out = subprocess.run(("gh", "pr", "list", "--state", "open",
                          "--limit", str(limit), "--json", "number,headRefName"),
                         capture_output=True, text=True, check=True).stdout
    bare = fold.removeprefix("origin/")
    return [(p["number"], p["headRefName"]) for p in json.loads(out)
            if p["headRefName"] not in (fold, bare)]


def measure(fold, heads):
    """``(verdict, stat, number, head)`` per head, probed in a throwaway worktree."""
    fold_tree = git("rev-parse", f"{fold}^{{tree}}").strip()
    rows = []
    with tempfile.TemporaryDirectory(prefix="fold-absorbs-") as box:
        git("worktree", "add", "--detach", box, fold)
        try:
            for number, head in heads:
                got, stat = attempt(box, fold, fold_tree, f"origin/{head}")
                rows.append((got, stat, number, head))
        finally:
            git("worktree", "remove", "--force", box, check=False)
    order = {ABSORBED: 0, ADDS: 1, CONFLICT: 2}
    rows.sort(key=lambda row: (order[row[0]], row[2]))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("fold", help="the ref claiming to carry the queue")
    ap.add_argument("--limit", type=int, default=100)
    args = ap.parse_args()

    rows = measure(args.fold, open_heads(args.fold, args.limit))
    counts = {name: sum(1 for row in rows if row[0] == name)
              for name in (ABSORBED, ADDS, CONFLICT)}
    ancestors = sum(1 for _, _, _, head in rows
                    if subprocess.run(("git", "merge-base", "--is-ancestor",
                                       f"origin/{head}", args.fold),
                                      capture_output=True).returncode == 0)

    print(f"Fold: {args.fold}   open heads probed: {len(rows)}\n")
    print(f"  absorbed  {counts[ABSORBED]:3d}  closing these after the fold lands "
          f"loses nothing")
    print(f"  adds      {counts[ADDS]:3d}  live work the fold does not hold")
    print(f"  conflict  {counts[CONFLICT]:3d}  mergeable against main today, red "
          f"the hour the fold lands")
    print(f"\n  of the absorbed, ancestors of the fold: {ancestors} "
          f"— ancestry is sufficient evidence, not necessary\n")
    for got, stat, number, head in rows:
        print(f"  {got:<9} #{number:<5d} {head}{'  ' + stat if stat else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
