#!/usr/bin/env python3
"""Order the open-PR queue so it can be landed with the fewest rebase rounds.

A review queue is not a list, it is a graph. Every PR here is cut from `main`,
so mergeability is pairwise: two PRs that touch disjoint regions can land in
either order, two that touch the same region force whichever lands second to
rebase. Reviewing in arrival order therefore pays a rebase for every collision
it happens to walk into, and the cost is invisible until the merge button.

This computes the graph instead of guessing it. Conflicts come from
`git merge-tree --write-tree`, which performs a real merge in memory — not a
filename-overlap heuristic, which over-reports (two PRs appending to different
sections of one file merge cleanly) and would hide nothing useful.

Output is a set of waves. A wave is a set of PRs that are mutually clean: land
them in any order, no rebase between them. Only crossing a wave boundary costs
a rebase, so N waves means N-1 rebase rounds for the whole queue.

Usage: python3 scripts/pr_landing_order.py [--limit N]
Exit 0 always — this is an operator report, not a gate.
"""

import argparse
import json
import subprocess
import sys


def run(*args):
    """Capture stdout; raise on failure."""
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout


def open_prs(limit):
    """[(number, headRefName, title, {files})] for the open queue, oldest first."""
    raw = run("gh", "pr", "list", "--state", "open", "--limit", str(limit),
              "--json", "number,headRefName,title,files")
    prs = [(p["number"], p["headRefName"], p["title"],
            {f["path"] for f in p["files"]}) for p in json.loads(raw)]
    return sorted(prs)


def conflicts(prs):
    """{frozenset({a, b}): sorted(shared files)} for pairs that do not merge."""
    found = {}
    for i, (a, ref_a, _, files_a) in enumerate(prs):
        for b, ref_b, _, files_b in prs[i + 1:]:
            merged = subprocess.run(
                ["git", "merge-tree", "--write-tree",
                 f"origin/{ref_a}", f"origin/{ref_b}"],
                capture_output=True, text=True)
            if merged.returncode != 0:
                found[frozenset((a, b))] = sorted(files_a & files_b)
    return found


def waves(numbers, edges):
    """Group PR numbers into internally conflict-free waves.

    Highest-degree first: a PR that collides with many others is the one whose
    delay costs the most rebases, so it goes in the earliest wave it fits.
    """
    degree = {n: sum(1 for e in edges if n in e) for n in numbers}
    remaining = sorted(numbers, key=lambda n: (-degree[n], n))
    out = []
    while remaining:
        wave = []
        for pr in remaining:
            if all(frozenset((pr, w)) not in edges for w in wave):
                wave.append(pr)
        out.append(sorted(wave))
        remaining = [p for p in remaining if p not in wave]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=50)
    args = ap.parse_args()

    prs = open_prs(args.limit)
    if not prs:
        print("no open PRs")
        return 0
    titles = {n: t for n, _, t, _ in prs}
    edges = conflicts(prs)
    order = waves([n for n, _, _, _ in prs], edges)

    print(f"{len(prs)} open PRs, {len(edges)} conflicting pairs, "
          f"{len(order)} waves ({max(len(order) - 1, 0)} rebase rounds)\n")
    for i, wave in enumerate(order, 1):
        print(f"Wave {i} — land in any order, no rebase between them:")
        for n in wave:
            print(f"  #{n:<4} {titles[n]}")
        print()
    if edges:
        print("Conflicting pairs and the files they share:")
        for pair, shared in sorted(edges.items(), key=lambda kv: sorted(kv[0])):
            a, b = sorted(pair)
            print(f"  #{a} <-> #{b}: {', '.join(shared) or '(no shared path)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
