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

It does so **per landing round**, not once for the whole queue. Waves land one at
a time, so `main` passes through every prefix of them, and a checker in an early
wave whose error is only cleared by a later one is red on `main` for the whole
gap. Verifying only the full union hides exactly that: the union contains the
fix, the round the operator actually lands does not.

In practice that means **one round per run: the next one.** A PR sits in a later
wave precisely because it conflicts with an earlier one, so every round past the
first contains a conflicting pair and cannot be assembled here — its members'
rebased content does not exist yet, and the rebase is a human's edit, not a
derivation. This is structural, not a property of today's queue. The loop is:
verify the next round, land it, rebase what conflicted, re-run.

When a round is red, the report then names **what clears it**. A wave is grouped
by merge conflicts, which have nothing to do with greenness, so the PR carrying a
fix routinely lands rounds after the checker it satisfies — and the operator has
no way to tell that from a tree that is simply broken. Each remaining PR is
folded into the round (minus whichever members it conflicts with, since those are
exactly the resolutions a human would make) and the failing checkers re-run.

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


def checker_scripts(scripts_dir, only=None):
    """Every checker in a tree: `check_*.py`, never their `test_*` siblings.

    `only` narrows the set by name, for re-testing a tree against a checker
    already known to fail — the other verdicts are not the question being asked.
    """
    return sorted(p for p in Path(scripts_dir).glob("check_*.py")
                  if not p.name.startswith("test_")
                  and (only is None or p.name in only))


def run_checkers(commit, only=None):
    """{checker name: (exit code, error lines)} for every checker in `commit`.

    `only` restricts the run to checkers of that name — used when re-testing a
    tree against a known failure, where the other checkers' verdicts are not
    the question being asked.
    """
    out = {}
    with tempfile.TemporaryDirectory(prefix="pr-union-") as tmp:
        subprocess.run(f"git archive {commit} | tar -x -C {tmp}",
                       shell=True, check=True)
        for script in checker_scripts(Path(tmp) / "scripts", only):
            done = subprocess.run([sys.executable, str(script), tmp],
                                  capture_output=True, text=True, cwd=tmp)
            out[script.name] = (done.returncode, [
                ln for ln in (done.stdout + done.stderr).strip().splitlines()
                if ln.startswith(("ERROR", "error"))])
    return out


def verify(base, refs):
    """Checkers inside the union of `refs`. Returns (lines, refused, failing).

    A round that refuses anything was not assembled, so its checker results
    belong to a smaller tree than the caller asked for — the caller must say so
    rather than present them as the round's verdict.
    """
    commit, joined, refused = union_tree(base, refs)
    lines = [f"Union of {len(joined)} PRs: "
             + (", ".join(f"#{n}" for n in joined) or "(none)")]
    if refused:
        return ["not assembled — "
                + ", ".join(f"#{n}" for n in refused)
                + " conflict with an earlier round, which is why they are in "
                  "this one; their rebased content does not exist yet"], refused, []

    results = run_checkers(commit)
    if not results:
        lines.append("  no checkers in the union — nothing to verify")
    for name, (code, errors) in sorted(results.items()):
        lines.append(f"  {'OK  ' if code == 0 else 'FAIL'} {name}")
        lines += [f"       {ln}" for ln in errors]
    return lines, [], sorted(n for n, (code, _) in results.items() if code)


def unverifiable(round_number):
    """Why the run stops here, and what the operator does to move it forward.

    Rounds past the first refuse by construction, not by accident: `waves` defers
    a PR exactly when it conflicts with one already placed, so every later round
    holds a conflicting pair. Saying "a human must resolve them" invites the
    operator to resolve something now; the resolution that matters is the rebase
    that only exists *after* the round below it has landed.
    """
    if round_number == 1:
        return ("  nothing is verifiable: this round's members are pairwise "
                "clean but do not combine, so no tree exists to check")
    return (f"  rounds {round_number} and later are not verifiable today — "
            f"their members conflict with an earlier round, which is why they "
            f"are in a later one, and their rebased content does not exist "
            f"yet. Land round {round_number - 1}, rebase them onto the new "
            f"`main`, re-run: round {round_number} becomes round 1.")


def blockers(candidate, landed, edges):
    """Members of `landed` that `candidate` cannot merge alongside."""
    return sorted(n for n in landed if frozenset((candidate, n)) in edges)


def clearing(base, landed, remaining, failing, edges, refs):
    """Which still-unlanded PRs turn this round's failing checkers green.

    Waves are computed from merge conflicts alone, so a checker can land rounds
    ahead of the change that satisfies it — and `main` is red for the whole gap.
    Mergeability and greenness are different graphs; the partition only ever saw
    the first one. Reporting the failure without this is reporting half of it:
    the operator cannot tell a landing-order artifact, which a resolution fixes
    today, from a real defect in the assembled tree, which nothing in the queue
    fixes at all.

    A candidate that conflicts with the round is tested against the round minus
    those members — the tree a human would produce by resolving them — so the
    answer is not simply withheld for the PRs most likely to be the fix.
    """
    numbers = [n for n, _ in landed]
    lines, cleared = [], {name: [] for name in failing}
    for number in remaining:
        blocked = blockers(number, numbers, edges)
        trimmed = [pr for pr in landed if pr[0] not in blocked]
        commit, _, refused = union_tree(base, trimmed + [(number, refs[number])])
        if refused:
            continue
        for name, (code, _) in run_checkers(commit, only=failing).items():
            if code == 0:
                cleared[name].append((number, blocked))
    for name in failing:
        if not cleared[name]:
            lines.append(f"  nothing in the remaining queue clears {name} — a "
                         f"defect in the assembled tree, not a landing order")
            continue
        for number, blocked in cleared[name]:
            if blocked:
                lines.append(
                    f"  #{number} clears {name}, but conflicts with "
                    + ", ".join(f"#{n}" for n in blocked)
                    + " in this round — a green `main` means resolving them "
                      "together, not landing the round as it stands")
            else:
                lines.append(f"  #{number} clears {name} and merges clean into "
                             f"this round — move it here")
    return lines


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
        print("\nVerifying the next landing round — a wave is not a tree:")
        for i, cumulative in enumerate(rounds(order, refs), 1):
            print(f"\nAfter wave {i} lands:")
            lines, refused, failing = verify(base, cumulative)
            for line in lines:
                print(line)
            if failing:
                landed = {n for n, _ in cumulative}
                for line in clearing(base, cumulative,
                                     [n for n, _, _, _ in prs if n not in landed],
                                     failing, edges, refs):
                    print(line)
            if refused:
                print(unverifiable(i))
                break
    return 0


if __name__ == "__main__":
    sys.exit(main())
