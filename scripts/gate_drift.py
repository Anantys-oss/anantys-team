#!/usr/bin/env python3
"""Merge the queue's diverged copies of a gate and run that gate's own tests.

Every sweep here measures a gate against a tree. `gate_matrix.py` runs these gates
against each head. `gate_power.py` runs them against mutations of `main`. `pair_gates.py`
assembles two heads and runs the gates on the result. All four treat the gate as the
fixed thing and the product as the variable, and in this repo that is backwards.

`origin/main` carries no `scripts/` directory at all. Every gate lives only on unmerged
branches, and a branch that wants to use a gate copies it forward — so `check_plugins.py`
exists in seven different versions across thirteen heads, `check_tool_grants.py` in seven
across ten. Those versions are not a chain. Fifty-two of the sixty-two differing pairs of
`check_plugins.py` carriers are incomparable: neither head is an ancestor of the other, so
each edited the gate independently and git has no basis for preferring one.

Which means the gate is a merge subject like any other file, and landing two carriers
produces a `check_plugins.py` that no author wrote, reviewed, or ran. The reviewable
artifact — the diff a human reads on each PR — is not the artifact that ships.

Three outcomes, and only one of them is quiet:

  * the gate file conflicts. Loud: somebody resolves it by hand and reads what they wrote.
  * the gate merges clean and its *test* file conflicts. Still loud, and worth separating,
    because the thing that stopped the merge is the evidence, not the subject. The gate
    was combined silently; the resolver's attention is on the test.
  * both merge clean. Git has assembled a new gate, every check was green on both heads,
    and the only question left is whether the result still passes the tests that are the
    sole reason to believe either version was right. When it does not, nothing anywhere
    was red before the merge and nothing names the pair afterwards.

That third case is the error this reports. The second is a warning: an honest cost, but
one that hides which file actually changed. The first is noise and is counted, not listed.

A pair whose merged gate passes is not certified — the merged tests are themselves a
merge, and two test files that each cover their own author's branch do not between them
cover the union. Passing means "no evidence of breakage", which is the strongest claim
available without writing the tests nobody has.

    python3 scripts/gate_drift.py                      # every gate, every incomparable pair
    python3 scripts/gate_drift.py --file check_plugins.py
    python3 scripts/gate_drift.py --limit 20           # timing probe

Exit 1 when some pair merges clean and fails, 0 otherwise.
"""

from __future__ import annotations

import argparse
import itertools
import re
import subprocess
import sys
import tempfile
from pathlib import Path

CONFLICT = re.compile(r"^CONFLICT \([^)]*\): Merge conflict in (.+)$", re.M)


def git(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=check)


def heads(remote: str) -> list[str]:
    out = git("for-each-ref", "--format=%(refname:short)", f"refs/remotes/{remote}")
    return [r for r in out.stdout.split() if not r.endswith("/HEAD")]


def gates(refs: list[str]) -> dict[str, dict[str, str]]:
    """{gate file: {head: blob}} for every non-test `scripts/*.py` any head carries."""
    found: dict[str, dict[str, str]] = {}
    for ref in refs:
        out = git("ls-tree", "-r", "--format=%(objectname) %(path)", ref, "--", "scripts")
        for line in out.stdout.splitlines():
            blob, path = line.split(" ", 1)
            name = path.rsplit("/", 1)[-1]
            if name.endswith(".py") and not name.startswith("test_"):
                found.setdefault(name, {})[ref] = blob
    return found


def ancestor(a: str, b: str) -> bool:
    return git("merge-base", "--is-ancestor", a, b).returncode == 0


def forks(carriers: dict[str, str], related=ancestor) -> list[tuple[str, str]]:
    """Carrier pairs holding different content with no ancestry to order them.

    An ancestry-ordered pair needs no verdict: the descendant already contains the
    other's edit, so the merge is a fast-forward of this file and the later author
    read the earlier version.
    """
    return [
        (a, b)
        for a, b in itertools.combinations(sorted(carriers), 2)
        if carriers[a] != carriers[b] and not related(a, b) and not related(b, a)
    ]


def merge(a: str, b: str) -> tuple[str, set[str]]:
    """(merged tree oid, conflicted paths) for a real three-way merge of two heads."""
    out = git("merge-tree", "--write-tree", a, b)
    return out.stdout.splitlines()[0], set(CONFLICT.findall(out.stdout))


def verdict(gate: str, conflicts: set[str], failed: bool | None, solo: bool = False) -> str:
    """Which outcome a merged pair landed in. `failed` is None when the merge never
    got far enough to run anything; `solo` is True when some head is red on its own.

    A pair whose gate was already failing on one head is `red-alone`, never `broken`.
    The claim this file exists to make is that the *merge* broke something, and a gate
    that never passed cannot be broken by combining it with anything.
    """
    if f"scripts/{gate}" in conflicts:
        return "conflict"
    if f"scripts/test_{gate}" in conflicts:
        return "test-conflict"
    if solo:
        return "red-alone"
    return "broken" if failed else "clean"


def tested(tree: str, gate: str) -> bool | None:
    """Run one gate's tests inside a tree. None when the tree has no test module.

    `discover -s scripts` rather than `-m unittest scripts.test_x`: the test modules
    import their subject as a sibling (`import check_plugins`), which only resolves
    with `scripts/` itself on `sys.path`. Running them as a package member raises
    ImportError, and unittest reports that as a failing test — a harness that spells
    the invocation the other way marks every gate broken, including on its own head.
    This is also the spelling CI uses, which is the point: the verdict has to be the
    one the merge would actually get.

    The subject is a worktree rather than an unpacked `git archive`, for the same
    reason. Several test modules here shell out to git — `test_gate_matrix.py` reads
    refs — and an archive is a directory of files with no repository under it, so they
    error on a tree that is fine. CI runs them in a checkout; so does this. A merged
    tree has no commit, so one is made for it and thrown away with the worktree.
    """
    oid = git("rev-parse", f"{tree}^{{tree}}", check=True).stdout.strip()
    commit = git("commit-tree", oid, "-m", "gate_drift", check=True).stdout.strip()
    tmp = tempfile.mkdtemp(prefix="koan-gate-drift-")
    try:
        git("worktree", "add", "--detach", "--quiet", tmp, commit, check=True)
        if not (Path(tmp) / "scripts" / f"test_{gate}").exists():
            return None
        run = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "scripts",
             "-p", f"test_{gate}"],
            cwd=tmp, capture_output=True, text=True,
        )
        return run.returncode != 0
    finally:
        git("worktree", "remove", "--force", tmp)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--file", help="one gate file name, e.g. check_plugins.py")
    ap.add_argument("--limit", type=int, help="stop after this many pairs per gate")
    args = ap.parse_args(argv)

    found = gates(heads(args.remote))
    if args.file:
        found = {k: v for k, v in found.items() if k == args.file}
        if not found:
            print(f"no head carries scripts/{args.file}", file=sys.stderr)
            return 2

    broken, alone = [], {}
    for gate, carriers in sorted(found.items()):
        pairs = forks(carriers)[: args.limit]
        tally = {"conflict": 0, "test-conflict": 0, "red-alone": 0, "broken": 0, "clean": 0}
        for a, b in pairs:
            tree, conflicts = merge(a, b)
            failed = None
            if not conflicts & {f"scripts/{gate}", f"scripts/test_{gate}"}:
                failed = tested(tree, gate)
                for head in (a, b):
                    alone.setdefault((gate, head), tested(head, gate))
            name = verdict(gate, conflicts, failed, any(alone.get((gate, h)) for h in (a, b)))
            tally[name] += 1
            if name == "broken":
                broken.append((gate, a, b))
        versions = len(set(carriers.values()))
        print(
            f"{gate:<34} {len(carriers):>3} heads {versions:>2} versions "
            f"{len(pairs):>3} forked  "
            + "  ".join(f"{k}={v}" for k, v in tally.items() if v)
        )

    for gate, a, b in broken:
        print(f"\nerror: scripts/{gate} merges clean from {a} + {b} and fails its own tests")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
