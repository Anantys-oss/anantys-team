#!/usr/bin/env python3
"""Report the files the open queue carries in versions no landing order reconciles.

`pr_landing_order.py` asks whether two heads *apply* together and
`queue_adjudications.py` asks whether their overlapping text *agrees*. Both read
pairs. Neither asks the question a lander actually faces on a file that twelve
heads rewrote: of the N copies of this path now in flight, is there one that
contains the rest?

When the versions of a path lie on a single ancestry chain the answer is yes and
the work is free — land the tip and every earlier copy arrives inside it. When
they do not, the copies are *incomparable*: no ref in the queue holds the union,
and whichever lands first defines the file until someone merges the others by
hand. Git will not say so. Two incomparable copies conflict exactly as loudly as
two copies one commit apart, and a resolver taking "theirs" on a conflict in a
checker is choosing its semantics without being told that is the choice.

Measured on the queue this was written against, 89 open heads:

    $ python3 scripts/queue_forks.py
    54 path(s) carried in more than one version
     7 with a total order — land the tip and the rest arrive inside it
    47 forked — no ref in the queue holds the union

The widest is `anantys.qa/SKILL.md` at 33 incomparable versions, which is the
queue working as intended: thirty-three heads each fixing one defect in the
file every role reads. That number is a cost, not a bug. Restricted to the
tooling (`--prefix scripts/`) it is 19 forked of 22, and those are a bug:
twenty-odd checkers exist in copies that disagree about what they reject.

`scripts/check_plugins.py` is the clearest, at five incomparable versions over
thirteen open heads, and the fork is not cosmetic. Four of those heads carry the
copy that requires a skill's frontmatter `name:` to equal its directory, dot
included; nine carry the copy that sanitizes the directory name first. A booted
loader settles which is right: a skill is exposed under its *directory* name
with every character outside `[A-Za-z0-9_-]` replaced, and the frontmatter
`name:` is read by nothing — a tree declaring `anantys.qa`, a tree declaring
`anantys-qa` and a tree declaring neither all expose `anantys-qa` (CLI 2.1.278,
four installs into sealed config directories). So four heads hold the gate to a
name no session produces. One fork of nineteen, and the one whose wrong
resolution reddens a tree assembled from individually-green heads.

So this is a report and not a gate. A fork is a standing property of the queue,
owned by no single head — the same reason `check_version_bump` warns rather than
errors on a name a branch merely inherited. It exits 0 with findings and 1 only
when it could not ask git.

Usage:
    python3 scripts/queue_forks.py [--all] [--prefix scripts/] [--limit N]

`--all` reads every `origin/koan/*` ref instead of the open pull requests, which
is the superset that includes the orphan branches with no PR.
"""

import argparse
import collections
import itertools
import json
import subprocess
import sys

CHAIN, FORK = "chain", "fork"


def git(*args):
    """stdout of a git command, or None when it failed."""
    done = subprocess.run(["git", *args], capture_output=True, text=True)
    return done.stdout if done.returncode == 0 else None


def open_heads():
    """Refs for the open pull requests, or None when `gh` cannot answer.

    The open queue is the default subject because a closed PR is a ruling: its
    head still exists and still holds a copy, and counting it would report a
    fork between a live file and one somebody already declined.
    """
    done = subprocess.run(
        ["gh", "pr", "list", "--state", "open", "--limit", "500",
         "--json", "headRefName"],
        capture_output=True, text=True,
    )
    if done.returncode != 0:
        return None
    return [f"origin/{p['headRefName']}" for p in json.loads(done.stdout)]


def all_heads():
    out = git("branch", "-r", "--list", "origin/koan/*") or ""
    return sorted(line.strip() for line in out.splitlines() if line.strip())


def versions(refs, prefix):
    """{path: {blob sha: [refs carrying it]}} for every tracked path under ``prefix``.

    Keyed on the blob rather than on a diff: two heads that arrived at byte-identical
    text by different routes are carrying one version, which is the only sense in
    which a lander has nothing to choose.
    """
    found = collections.defaultdict(lambda: collections.defaultdict(list))
    for ref in refs:
        for line in (git("ls-tree", "-r", ref) or "").splitlines():
            meta, _, path = line.partition("\t")
            parts = meta.split()
            if len(parts) != 3 or parts[1] != "blob":
                continue
            if prefix and not path.startswith(prefix):
                continue
            found[path][parts[2]].append(ref)
    return found


def touched(ref, path):
    """The last commit on ``ref`` that wrote ``path`` — the version's position in history."""
    out = git("log", "-1", "--format=%H", ref, "--", path)
    return (out or "").strip() or None


def classify(commits, is_ancestor):
    """CHAIN when every pair of version-commits is ordered, FORK otherwise.

    Pure, so the ancestry predicate is injected: the shape of the answer is
    combinatorial and the shape of the question is a git call, and only the first
    is worth testing exhaustively.

    A single version is a chain of one. A version whose commit git could not name
    (``None`` — the path arrived in the ref's initial import, or history was
    rewritten) is incomparable with everything, including itself, so it forks:
    reporting a path as safe on the strength of an unknown position is the one
    error this function must not make.
    """
    if len(commits) < 2:
        return CHAIN
    if any(c is None for c in commits):
        return FORK
    return CHAIN if all(
        is_ancestor(a, b) or is_ancestor(b, a)
        for a, b in itertools.combinations(commits, 2)
    ) else FORK


def survey(found, position, is_ancestor):
    """[(path, verdict, [(commit, [refs])])] for the multi-version paths, worst first.

    ``position`` maps (ref, path) to a commit so the caller supplies history the
    same way it supplies ancestry.
    """
    rows = []
    for path, blobs in found.items():
        if len(blobs) < 2:
            continue
        carriers = [(position(refs[0], path), sorted(refs)) for refs in blobs.values()]
        verdict = classify([c for c, _ in carriers], is_ancestor)
        rows.append((path, verdict, sorted(carriers, key=lambda c: -len(c[1]))))
    rows.sort(key=lambda row: (row[1] != FORK, -len(row[2]), row[0]))
    return rows


def report(rows, refs_read, limit):
    """The lines to print. Pure, so the counts are testable without a repository."""
    forks = [r for r in rows if r[1] == FORK]
    lines = [
        f"{len(refs_read)} head(s) read",
        f"{len(rows)} path(s) carried in more than one version",
        f"{len(rows) - len(forks)} with a total order — land the tip and the rest arrive inside it",
        f"{len(forks)} forked — no ref in the queue holds the union, so whoever lands first decides",
        "",
    ]
    for path, verdict, carriers in forks[:limit]:
        lines.append(f"FORK  {len(carriers)} versions  {path}")
        for commit, refs in carriers:
            at = commit[:8] if commit else "untraced"
            shown = ", ".join(r.split("/", 1)[-1] for r in refs[:3])
            more = f" (+{len(refs) - 3})" if len(refs) > 3 else ""
            lines.append(f"        {at}  {len(refs):>2} head(s)  {shown}{more}")
    if len(forks) > limit:
        lines.append(f"... {len(forks) - limit} more forked path(s)")
    return lines


def main(argv=None):
    parsed = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parsed.add_argument("--all", action="store_true", help="every origin/koan/* ref, not just open PRs")
    parsed.add_argument("--prefix", default="", help="restrict to paths under this prefix")
    parsed.add_argument("--limit", type=int, default=20, help="forked paths to detail")
    args = parsed.parse_args(argv)

    refs = all_heads() if args.all else open_heads()
    if refs is None:
        print("queue_forks: gh could not list the open pull requests; retry with --all")
        return 1
    if not refs:
        print("queue_forks: no heads to read")
        return 0

    def is_ancestor(a, b):
        return subprocess.run(
            ["git", "merge-base", "--is-ancestor", a, b], capture_output=True
        ).returncode == 0

    rows = survey(versions(refs, args.prefix), touched, is_ancestor)
    print("\n".join(report(rows, refs, args.limit)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
