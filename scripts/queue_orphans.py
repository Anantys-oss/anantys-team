#!/usr/bin/env python3
"""Report the pushed heads nothing in the queue asks anyone to review.

Every other instrument here starts from `gh pr list`. That is the right subject
for a question about review order, and the wrong one for a question about work:
a branch is pushed by one command and opened by another, and when the second
fails the first leaves a finished, tested, reported-as-shipped branch that no
reviewer will ever be shown. `gh pr list` cannot report it, because the thing
that is missing is the pull request.

Counting bare heads overcorrects. Most sessions here stack: a branch is cut off
the previous one, so an ancestor with no PR of its own is not forgotten — its
commits are inside the diff of the descendant that does have one, and opening a
second PR for it would ask for the same review twice. The question is therefore
not "does this head have a PR" but "does any open PR contain it".

    pushed head ──has an open PR?────────────► open
                ──has a closed PR?──────────► ruled   (a closed PR is a ruling)
                ──an open PR descends it?───► in flight
                ──none of the above─────────► ORPHANED

Measured on the queue this was written against, 127 pull requests ever opened:

    $ python3 scripts/queue_orphans.py
    169 pushed head(s) read, 122 open PR(s), 5 closed
      122 open      — a pull request already asks for review
        1 ruled     — a closed pull request decided it
        5 in flight — no PR of its own; an open PR contains it
       41 ORPHANED  — pushed and finished, and nothing asks for it

Forty-one, not five. Two standing issues put this number at seven (#54) and six
(#62); both were measured by hand a month and ~110 heads ago, and neither
subtracted the stacked ancestors, so the figure was small enough to read as
housekeeping. It is a quarter of the queue. Ten of the forty-one were pushed in
the last four days, three of them on the day this was written, each one the
subject of a session that reported the work shipped. The oldest,
`koan/the-orphan-work-has-no-pr`, has been orphaned since October 9th.

Four of the five closed pull requests do not appear in the counts because their
heads were deleted; `ruled` counts heads that still exist, which is the set a
reader can still be shown.

All forty-one merge clean. That is a claim about each one *against `main`
alone* — `main` has not moved in a month, so every head still applies to the
commit it was cut from. It is not a claim that they land clean *together*;
`pr_landing_order.py` answers that, and the answer is no. What it does mean is
that none of the forty-one is stale, so none of them is waiting on anything.

A closed pull request on a *descendant* does not rescue a head: the ruling was
cast on the pull request that was opened, which says nothing about whether the
commits underneath it were read. Such heads stay ORPHANED and name the closed
PR, so a reviewer can tell the two cases apart without re-deriving the ancestry.

Orphans are printed smallest diff first, each with the verdict `git merge-tree`
gives against `main`, because the actionable ones are the single-commit docs
fixes that land clean today, not the sixteen-thousand-line instrument stacks
that need a different kind of afternoon.

This is a report and not a gate: an orphan is a property of the queue, owned by
no single head, and no branch can be asked to fix it from inside its own diff.
It exits 0 with findings and 1 only when it could not ask git or `gh`.

Usage:
    python3 scripts/queue_orphans.py [--pattern origin/koan/*] [--limit N] [--json]
"""

import argparse
import fnmatch
import json
import subprocess
import sys

OPEN, RULED, INFLIGHT, ORPHANED = "open", "ruled", "in flight", "ORPHANED"
VERDICTS = (OPEN, RULED, INFLIGHT, ORPHANED)


def git(*args):
    """stdout of a git command, or None when it failed."""
    done = subprocess.run(["git", *args], capture_output=True, text=True)
    return done.stdout if done.returncode == 0 else None


def pushed_heads(pattern):
    """Short names of the remote heads matching ``pattern``, or None when git failed.

    Read from `ls-remote` rather than `branch -r` so the answer is the server's
    and not this checkout's: a head pushed by another session is exactly the
    kind this report exists to find, and a stale local remote-tracking ref would
    hide it.
    """
    out = git("ls-remote", "--heads", "origin")
    if out is None:
        return None
    names = []
    for line in out.splitlines():
        _, _, ref = line.partition("\t")
        name = ref.strip().replace("refs/heads/", "", 1)
        if name and name != "main" and fnmatch.fnmatch(name, pattern):
            names.append(name)
    return sorted(names)


def pull_requests():
    """({open head: number}, {closed head: number}), or None when `gh` cannot answer."""
    done = subprocess.run(
        ["gh", "pr", "list", "--state", "all", "--limit", "500",
         "--json", "number,headRefName,state"],
        capture_output=True, text=True,
    )
    if done.returncode != 0:
        return None
    live, ruled = {}, {}
    for pr in json.loads(done.stdout):
        bucket = live if pr["state"] == "OPEN" else ruled
        bucket.setdefault(pr["headRefName"], pr["number"])
    return live, ruled


def classify(head, live, ruled, descendants):
    """One head's verdict. Pure — ``descendants`` supplies the ancestry.

    ``descendants`` returns the heads strictly containing ``head``; "strictly"
    matters because `merge-base --is-ancestor X X` is true, so a head left in
    its own descendant set would report itself in flight and hide every orphan.
    """
    if head in live:
        return OPEN
    if head in ruled:
        return RULED
    if any(d in live for d in descendants(head)):
        return INFLIGHT
    return ORPHANED


def survey(heads, live, ruled, descendants, measure):
    """[row] for every head, orphans last and smallest first within each verdict.

    ``measure`` maps a head to its (date, commits, files, added, removed, merge)
    detail; it is only called for the orphans, which is the only place the
    report prints it and the only place the git calls are worth paying for.
    """
    rows = []
    for head in heads:
        verdict = classify(head, live, ruled, descendants)
        row = {"head": head, "verdict": verdict,
               "pr": live.get(head) or ruled.get(head)}
        if verdict == ORPHANED:
            row.update(measure(head))
            row["declined_descendants"] = sorted(
                ruled[d] for d in descendants(head) if d in ruled
            )
        rows.append(row)
    rows.sort(key=lambda r: (
        VERDICTS.index(r["verdict"]),
        r.get("added", 0) + r.get("removed", 0),
        r["head"],
    ))
    return rows


def report(rows, live, ruled, limit):
    """The lines to print. Pure, so the counts are testable without a repository."""
    counts = {v: sum(1 for r in rows if r["verdict"] == v) for v in VERDICTS}
    lines = [
        f"{len(rows)} pushed head(s) read, {len(live)} open PR(s), {len(ruled)} closed",
        f"  {counts[OPEN]:>3} open      — a pull request already asks for review",
        f"  {counts[RULED]:>3} ruled     — a closed pull request decided it",
        f"  {counts[INFLIGHT]:>3} in flight — no PR of its own; an open PR contains it",
        f"  {counts[ORPHANED]:>3} ORPHANED  — pushed and finished, and nothing asks for it",
        "",
    ]
    orphans = [r for r in rows if r["verdict"] == ORPHANED]
    for row in orphans[:limit]:
        declined = row.get("declined_descendants") or []
        tail = f"  (declined below: {', '.join('#%d' % n for n in declined)})" if declined else ""
        lines.append(
            f"ORPHANED  {row['date']}  {row['commits']:>3} commit(s)"
            f"  {row['files']:>2} file(s)  +{row['added']}/-{row['removed']}"
            f"  {row['merge']:<8}  {row['head']}{tail}"
        )
    if len(orphans) > limit:
        lines.append(f"... {len(orphans) - limit} more orphaned head(s)")
    return lines


def measurement(head):
    """Size, age and landing verdict for one orphan, read from git."""
    ref = f"origin/{head}"
    added = removed = files = 0
    for line in (git("diff", "--numstat", f"main...{ref}") or "").splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        files += 1
        if parts[0].isdigit():
            added += int(parts[0])
            removed += int(parts[1])
    merged = subprocess.run(
        ["git", "merge-tree", "--write-tree", "main", ref], capture_output=True
    )
    return {
        "date": (git("log", "-1", "--format=%cs", ref) or "").strip() or "unknown",
        "commits": len((git("rev-list", f"main..{ref}") or "").split()),
        "files": files,
        "added": added,
        "removed": removed,
        # 0 clean, 1 conflicts, anything else means merge-tree refused to answer.
        "merge": {0: "clean", 1: "conflicts"}.get(merged.returncode, "unknown"),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pattern", default="koan/*",
                        help="glob over head names (default: koan/*)")
    parser.add_argument("--limit", type=int, default=50,
                        help="orphans to detail (default: 50)")
    parser.add_argument("--json", action="store_true", help="emit rows as JSON")
    args = parser.parse_args(argv)

    heads = pushed_heads(args.pattern)
    if heads is None:
        print("queue_orphans: git could not read origin")
        return 1
    requests = pull_requests()
    if requests is None:
        print("queue_orphans: gh could not list the pull requests")
        return 1
    live, ruled = requests
    if not heads:
        print(f"queue_orphans: no pushed head matches {args.pattern!r}")
        return 0

    def descendants(head):
        return [
            other for other in heads
            if other != head and subprocess.run(
                ["git", "merge-base", "--is-ancestor",
                 f"origin/{head}", f"origin/{other}"], capture_output=True
            ).returncode == 0
        ]

    rows = survey(heads, live, ruled, descendants, measurement)
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        print("\n".join(report(rows, live, ruled, args.limit)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
