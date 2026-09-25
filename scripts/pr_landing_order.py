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

Mergeable is not green. A wave says the trees combine without a conflict; it
says nothing about whether the combined tree still passes the repo's own checks.
Every checker in this queue was written against `main` and validated against the
one branch that carries it, so the assembled result — the thing `main` actually
becomes — is the one state no checker has ever run in. `--verify` builds that
state (fold the branches with `merge-tree`, extract with `git archive`, never
touch a branch or the working tree) and runs every `scripts/check_*.py` found
inside it.

It does so **once per landing round**, not once for the whole queue. Waves land
one at a time, so `main` passes through every prefix of them, and a checker in an
early wave whose error is only cleared by a later one is red on `main` for the
whole gap. Verifying only the full union hides exactly that: the union contains
the fix, the round the operator actually lands does not.

Usage: python3 scripts/pr_landing_order.py [--limit N] [--verify]
Exit 0 always — this is an operator report, not a gate.
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


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


def stacked(prs):
    """{contained: container} when one PR's head is an ancestor of another's.

    A stacked PR carries no diff of its own once its container lands, and it
    breaks a fold: the pair merges cleanly (their merge base *is* the contained
    head) but folding the contained tree first and then merging the container
    against `main` re-reads the shared files as two independent edits. Landing
    the container closes both, so the contained PR leaves the graph.
    """
    out = {}
    for a, ref_a, _, _ in prs:
        for b, ref_b, _, _ in prs:
            if a != b and subprocess.run(
                    ["git", "merge-base", "--is-ancestor",
                     f"origin/{ref_a}", f"origin/{ref_b}"],
                    capture_output=True).returncode == 0:
                out[a] = b
    return out


def rounds(order, refs):
    """Cumulative landing rounds: what `main` holds after each wave lands."""
    out, seen = [], []
    for wave in order:
        seen = seen + [(n, refs[n]) for n in wave]
        out.append(list(seen))
    return out


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


def union_tree(base, refs):
    """Fold `refs` onto `base` in memory. Returns (commit, joined, refused).

    Refused refs are the ones that conflict with the accumulation so far — they
    are reported, not forced, because a resolved conflict is a human's call and
    guessing one would verify a tree nobody is going to land.
    """
    acc, joined, refused = base, [], []
    for number, ref in refs:
        merged = subprocess.run(
            ["git", "merge-tree", "--write-tree", "--merge-base", base,
             acc, f"origin/{ref}"], capture_output=True, text=True)
        if merged.returncode != 0:
            refused.append(number)
            continue
        tree = merged.stdout.splitlines()[0]
        acc = run("git", "commit-tree", tree, "-p", acc,
                  "-m", f"union #{number}").strip()
        joined.append(number)
    return acc, joined, refused


def checker_scripts(scripts_dir):
    """Every checker in a tree: `check_*.py`, never their `test_*` siblings."""
    return sorted(p for p in Path(scripts_dir).glob("check_*.py")
                  if not p.name.startswith("test_"))


def verify(base, refs):
    """Run every checker inside the union of `refs`. Returns (lines, refused).

    A round that refuses anything was not assembled, so its checker results
    belong to a smaller tree than the caller asked for — the caller must say so
    rather than present them as the round's verdict.
    """
    commit, joined, refused = union_tree(base, refs)
    lines = [f"Union of {len(joined)} PRs: "
             + (", ".join(f"#{n}" for n in joined) or "(none)")]
    if refused:
        return ["not assembled — a human must first resolve "
                + ", ".join(f"#{n}" for n in refused)
                + " against the tree the previous wave leaves behind"], refused

    with tempfile.TemporaryDirectory(prefix="pr-union-") as tmp:
        subprocess.run(f"git archive {commit} | tar -x -C {tmp}",
                       shell=True, check=True)
        found = checker_scripts(Path(tmp) / "scripts")
        if not found:
            lines.append("  no checkers in the union — nothing to verify")
        for script in found:
            done = subprocess.run([sys.executable, str(script), tmp],
                                  capture_output=True, text=True, cwd=tmp)
            status = "OK  " if done.returncode == 0 else "FAIL"
            lines.append(f"  {status} {script.name}")
            if done.returncode != 0:
                lines += [f"       {ln}" for ln
                          in (done.stdout + done.stderr).strip().splitlines()
                          if ln.startswith(("ERROR", "error"))]
    return lines, []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--verify", action="store_true",
                    help="build the merged tree and run its checkers in it")
    args = ap.parse_args()

    prs = open_prs(args.limit)
    if not prs:
        print("no open PRs")
        return 0
    titles = {n: t for n, _, t, _ in prs}
    refs = {n: ref for n, ref, _, _ in prs}
    contained = stacked(prs)
    if contained:
        prs = [pr for pr in prs if pr[0] not in contained]
    edges = conflicts(prs)
    order = waves([n for n, _, _, _ in prs], edges)

    print(f"{len(prs)} open PRs, {len(edges)} conflicting pairs, "
          f"{len(order)} waves ({max(len(order) - 1, 0)} rebase rounds)\n")
    for small, big in sorted(contained.items()):
        print(f"#{small} is contained in #{big} — landing #{big} closes it; "
              f"not counted above\n")
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

    if args.verify:
        base = run("git", "rev-parse", "main").strip()
        print("\nVerifying every landing round — a wave is not a tree:")
        for i, cumulative in enumerate(rounds(order, refs), 1):
            print(f"\nAfter wave {i} lands:")
            lines, refused = verify(base, cumulative)
            for line in lines:
                print(line)
            if refused:
                print(f"  rounds after wave {i} not verified — they sit on a tree "
                      f"only a human can produce")
                break
    return 0


if __name__ == "__main__":
    sys.exit(main())
