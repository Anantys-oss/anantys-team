#!/usr/bin/env python3
"""Report the files the open queue carries in versions no landing order reconciles.

`pr_landing_order.py` asks whether two heads *apply* together and
`queue_adjudications.py` asks whether their overlapping text *agrees*. Both read
pairs. Neither asks the question a lander actually faces on a file that twelve
heads rewrote: of the N copies of this path now in flight, is there one that
contains the rest?

When one of the versions contains every other the answer is yes and the work is
free — land that one and the rest arrive inside it. The report names it, because
"land the tip" is advice nobody can act on without the sha. Note that this is a
**maximum**, not a total order: a head that merged two siblings holds their
union, and the two siblings are still incomparable to each other. Asking for a
total order would call that free landing a fork (see `holder`). When no version
contains the rest, the copies are *incomparable*: no ref in the queue holds the union,
and whichever lands first defines the file until someone merges the others by
hand. Git will not say so. Two incomparable copies conflict exactly as loudly as
two copies one commit apart, and a resolver taking "theirs" on a conflict in a
checker is choosing its semantics without being told that is the choice.

Measured on the queue of 2026-11-09, 130 open heads — the counts move with the
queue, the shapes do not:

    $ python3 scripts/queue_forks.py
    130 head(s) read
    64 path(s) carried in more than one version
    16 held — one version contains the rest; land it and they arrive inside it
    48 forked — no ref in the queue holds the union, so whoever lands first decides

The widest is `anantys.qa/SKILL.md` at 49 incomparable versions, which is the
queue working as intended: forty-nine heads each fixing one defect in the file
every role reads. That number is a cost, not a bug. Restricted to the tooling
(`--prefix scripts/`) it is 19 forked of 26, and those are a bug: twenty-odd
checkers exist in copies that disagree about what they reject.

`scripts/check_plugins.py` is the clearest, at five incomparable versions, and
the fork is not cosmetic. Some of those heads carry the copy that requires a
skill's frontmatter `name:` to equal its directory, dot included; the rest carry
the copy that sanitizes the directory name first. A booted loader settles which
is right: a skill is exposed under its *directory* name with every character
outside `[A-Za-z0-9_-]` replaced, and the frontmatter `name:` is read by nothing
— a tree declaring `anantys.qa`, a tree declaring `anantys-qa` and a tree
declaring neither all expose `anantys-qa` (CLI 2.1.278, four installs into
sealed config directories). So some heads hold the gate to a name no session
produces. One fork of nineteen, and the one whose wrong resolution reddens a
tree assembled from individually-green heads.

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


def holder(commits, is_ancestor):
    """The one version-commit that contains every other, or None when there is none.

    Pure, so the ancestry predicate is injected: the shape of the answer is
    combinatorial and the shape of the question is a git call, and only the first
    is worth testing exhaustively.

    This is a **maximum**, not a total order, and the difference is the whole
    point. Land-the-tip is free exactly when some copy contains the rest —
    which does not require the copies to be comparable *to each other*. Two
    siblings both contained by a later third are reconciled by that third;
    demanding every pair be ordered calls that shape a fork and sends a lander
    to merge by hand a union the queue already holds. A set that is totally
    ordered always has a maximum, so no real fork is missed by asking the
    weaker question.

    A version whose commit git could not name (``None`` — the path arrived in
    the ref's initial import, or history was rewritten) is incomparable with
    everything, including itself, so nothing holds the set: reporting a path as
    safe on the strength of an unknown position is the one error this function
    must not make.
    """
    if any(c is None for c in commits):
        return None
    for candidate in commits:
        if all(is_ancestor(other, candidate) for other in commits if other != candidate):
            return candidate
    return None


def classify(commits, is_ancestor):
    """CHAIN when one version-commit contains the rest, FORK otherwise.

    A single version is a chain of one.
    """
    if len(commits) < 2:
        return CHAIN
    return CHAIN if holder(commits, is_ancestor) else FORK


def survey(found, position, is_ancestor):
    """[(path, verdict, [(commit, [refs])], tip)] for the multi-version paths, worst first.

    ``position`` maps (ref, path) to a commit so the caller supplies history the
    same way it supplies ancestry. ``tip`` is the version-commit that contains
    the rest (None on a fork) — the headline tells a lander to land it, so the
    row has to name it.
    """
    rows = []
    for path, blobs in found.items():
        if len(blobs) < 2:
            continue
        carriers = [(position(refs[0], path), sorted(refs)) for refs in blobs.values()]
        tip = holder([c for c, _ in carriers], is_ancestor)
        verdict = FORK if tip is None else CHAIN
        rows.append((path, verdict, sorted(carriers, key=lambda c: -len(c[1])), tip))
    rows.sort(key=lambda row: (row[1] != FORK, -len(row[2]), row[0]))
    return rows


def report(rows, refs_read, limit):
    """The lines to print. Pure, so the counts are testable without a repository."""
    forks = [r for r in rows if r[1] == FORK]
    held = [r for r in rows if r[1] != FORK]
    lines = [
        f"{len(refs_read)} head(s) read",
        f"{len(rows)} path(s) carried in more than one version",
        f"{len(held)} held — one version contains the rest; land it and they arrive inside it",
        f"{len(forks)} forked — no ref in the queue holds the union, so whoever lands first decides",
        "",
    ]
    for path, _verdict, carriers, _tip in forks[:limit]:
        lines.append(f"FORK  {len(carriers)} versions  {path}")
        for commit, refs in carriers:
            at = commit[:8] if commit else "untraced"
            shown = ", ".join(r.split("/", 1)[-1] for r in refs[:3])
            more = f" (+{len(refs) - 3})" if len(refs) > 3 else ""
            lines.append(f"        {at}  {len(refs):>2} head(s)  {shown}{more}")
    if len(forks) > limit:
        lines.append(f"... {len(forks) - limit} more forked path(s)")
    for path, _verdict, carriers, tip in held[:limit]:
        at = tip[:8]
        holders = next(refs for commit, refs in carriers if commit == tip)
        shown = ", ".join(r.split("/", 1)[-1] for r in holders[:3])
        lines.append(f"HELD  {len(carriers)} versions  {path} — land {at} ({shown})")
    if len(held) > limit:
        lines.append(f"... {len(held) - limit} more held path(s)")
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
