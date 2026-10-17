#!/usr/bin/env python3
"""Measure how much of each open PR's content a proposed fold already carries.

`pr_landing_order.py` prices the queue landed one PR at a time. This prices the
other proposal on the table: one branch that claims to be *the product the open
PRs agree on*, merged alone. That claim is the whole of its value and nothing in
the repo checks it. A fold is 3,000 lines of prose; a reviewer cannot hold the
queue in their head while reading it, so "did this drop anything" is the one
question they cannot answer and the one that decides the merge.

So answer it mechanically. For every open head, take the lines it adds to the
product and ask whether the fold's tree contains them.

**The number is a floor, and the floor is the point.** Matching is verbatim, so
a line the fold rewrote reads as absent. That asymmetry is what makes the report
usable: a high score is proof of inclusion, and a low score is a *prompt*, never
a verdict. The two are distinguished by hand, in one grep, and the distinction
is not cosmetic — it is the difference between the fold's author paraphrasing a
rule and the fold predating it:

  * `evidence-redaction-contract` scores 62% and every missing line is its own
    wording of a rule the fold states in eight files. Carried.
  * `the-field-that-withholds` scores 0% and the phrase it exists to add
    appears in the fold zero times, exactly as often as in `main`. Not carried.

Hence `--absent`, which prints the lines a head is missing so that grep is one
copy-paste away, and hence no exit code: this ranks heads for a human to read,
it does not rule on them.

A score answers *what* the fold is missing and says nothing about the cost of
adding it, which is the question the fold's reviewer actually has — and the two
are independent. So the `merge` column prices the remedy: the conflicted paths
from merging the head into the fold, performed in memory by `merge-tree`. It
splits the low scorers into the two cases that look identical in the score
alone. A 0% head that merges clean is a head the fold simply predates: one
`git merge` carries it, and the fold's claim survives. A 0% head that conflicts
is a head the fold *overwrote* — its prose and the fold's occupy the same lines,
so there is no merge to run and carrying it means re-authoring the fold's
version of that rule by hand.

The second case is what gives a fold a shelf life, and the shelf life is the
number this column exists to expose. Measured on this queue on 2026-10-17, the
fold at `koan/the-product-without-the-scaffolding` (authored 2026-10-13) carried
24 of 41 heads at 75-100% and 12 at exactly 0% — and every one of those 12
conflicts with it, 1 to 5 files each. None of them can be merged in. A fold
reviewed slower than the queue produces product PRs is therefore not a landing
strategy but a recurring re-authoring, and the score alone reads as if four
days of drift were four `git merge` calls away.

The follow-up section is scoped to the 0% rows on purpose. A head carried at
98% with one line absent and a conflicting file is a rewording, which is the
documented floor doing its job; listing it as "cannot merge" is the same false
row the scope rules exist to avoid. Only a head the fold carries *nothing* of
makes the clean/conflicting distinction load-bearing.

Scope follows the fold's own declaration. A fold that advertises itself as the
product *without the scaffolding* is not failing when it omits an eval suite or
a checker, so `evals/` and any line naming `scripts/` are out of the comparison.
Judging a branch against a contract it disclaimed produces exactly the one false
row that teaches a reader to skip the section.

Usage: python3 scripts/fold_coverage.py <fold-ref> [--limit N] [--absent N]
Exit 0 always — this is an operator report, not a gate.
"""

import argparse
import itertools
import json
import subprocess
import sys

# Shorter lines are boilerplate — list bullets, table rules, closing fences —
# and match some unrelated file by accident, which inflates every score.
MIN_LEN = 40

PRODUCT = ("plugins", "README.md")


def run(*args):
    """Capture stdout; raise on failure."""
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout


def in_scope(paths):
    """The product paths a scaffolding-free fold is answerable for."""
    return [p for p in paths if "/evals/" not in p]


def added(diff, min_len=MIN_LEN):
    """The substantive lines a diff adds, stripped and deduplicated in order."""
    seen = {}
    for line in diff.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        text = line[1:].strip()
        if len(text) >= min_len and "scripts/" not in text:
            seen.setdefault(text, None)
    return list(seen)


def absent(want, corpus):
    """The wanted lines the corpus does not contain, verbatim."""
    return [line for line in want if line not in corpus]


def corpus(ref):
    """Every stripped line of every text file in ``ref``.

    The whole tree, not just the product paths: a fold relocates rules into
    `docs/` and `reference/` on purpose, and reading only where the line used to
    live would score that relocation as a loss.
    """
    files = [f for f in run("git", "ls-tree", "-r", "--name-only", ref).splitlines()
             if f.endswith((".md", ".json", ".yml", ".yaml"))]
    return {line.strip()
            for f in files
            for line in run("git", "show", f"{ref}:{f}").splitlines()}


def changed(head):
    """The product paths ``head`` touches, relative to main."""
    numstat = run("git", "diff", "--numstat", f"origin/main..origin/{head}",
                  "--", *PRODUCT)
    return in_scope(line.split("\t")[2] for line in numstat.splitlines())


def conflicted(output):
    """The paths ``git merge-tree --name-only`` reports as conflicted.

    Its output is the merged tree's oid, then one path per conflicted file,
    then a blank line and git's own prose. Stopping at the blank line is what
    keeps `CONFLICT (content): Merge conflict in <path>` out of the count — it
    names every one of those same paths a second time.
    """
    return list(itertools.takewhile(str.strip, output.splitlines()[1:]))


def cost(fold, head):
    """The paths that conflict when ``head`` is merged into ``fold``.

    `merge-tree --write-tree` performs the merge in memory, so this prices the
    remedy without touching the working tree. Exit 0 is a clean merge, 1 is
    conflicts; anything else is git failing to answer and must not read as
    "clean".
    """
    done = subprocess.run(("git", "merge-tree", "--write-tree", "--name-only",
                           fold, f"origin/{head}"), capture_output=True, text=True)
    if done.returncode > 1:
        raise RuntimeError(f"merge-tree {fold} origin/{head}: {done.stderr.strip()}")
    return conflicted(done.stdout) if done.returncode else []


def remedy(blocked):
    """How the ``merge`` column reads a head's conflict list."""
    return "clean" if not blocked else f"{len(blocked)} file(s)"


def open_prs(limit):
    out = run("gh", "pr", "list", "--state", "open", "--limit", str(limit),
              "--json", "number,headRefName,createdAt")
    return json.loads(out)


def measure(fold, prs):
    """``(carried, total, pr, head, opened, absent, blocked)`` per contributing head."""
    held = corpus(fold)
    rows = []
    for pr in prs:
        head = pr["headRefName"]
        if f"origin/{head}" == fold or head == fold:
            continue
        paths = changed(head)
        if not paths:
            continue
        want = added(run("git", "diff", f"origin/main..origin/{head}", "--", *paths))
        if not want:
            continue
        missing = absent(want, held)
        rows.append((len(want) - len(missing), len(want), pr["number"], head,
                     pr["createdAt"][:10], missing, cost(fold, head)))
    rows.sort(key=lambda row: (row[0] / row[1], -row[1]))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("fold", help="the ref proposing to carry the queue")
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--absent", type=int, default=0, metavar="N",
                    help="print up to N absent lines per head scoring under 100%%")
    args = ap.parse_args()

    rows = measure(args.fold, open_prs(args.limit))
    print(f"Fold: {args.fold}   heads adding product lines: {len(rows)}\n")
    print(f"{'carried':>7}  {'lines':>12}  {'merge':<9} "
          f"{'pr':<6} {'opened':<11} head")
    for held, total, number, head, opened, _, blocked in rows:
        print(f"{held / total:7.0%}  {held:5d}/{total:<6d} {remedy(blocked):<9} "
              f"#{number:<5d} {opened}  {head}")

    stuck = [row for row in rows if row[0] == 0 and row[6]]
    if stuck:
        print(f"\n{len(stuck)} head(s) carried at 0% that also conflict — the "
              f"fold overwrote these, so carrying them is re-authoring, not a "
              f"merge:")
        for _, total, number, head, _, _, blocked in stuck:
            print(f"  #{number} {head}: {total} line(s), none carried; "
                  f"conflicts in {', '.join(blocked)}")

    if not args.absent:
        return
    for held, total, number, head, _, missing, _ in rows:
        if not missing:
            continue
        print(f"\n--- #{number} {head}: {len(missing)} of {total} absent verbatim")
        for line in missing[:args.absent]:
            print(f"    {line}")


if __name__ == "__main__":
    main()
