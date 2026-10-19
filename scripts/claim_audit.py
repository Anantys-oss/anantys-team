#!/usr/bin/env python3
"""Re-measure the numeric claims this repo's commit messages make about its trees.

Every tool in `scripts/` reads the tree. None reads the argument. That asymmetry
is backwards here, because the tree is not what a reviewer is handed: a queue of
seventy pull requests cut from one `main` presents four hundred commit messages,
and those messages are long, and they are the review. They say *145 tests pass*,
*no version bump*, *stacked on #78*, *43 of 46 heads*. Each is a measurement the
author took, in a tree that existed at the time, and each is load-bearing — a
reviewer who re-derives them is doing the author's work twice, and one who does
not is trusting prose.

Prose rots, and this repo has already recorded the mechanism three times in its
own history: a checker's docstring quoting the floors that motivated it, which
the checker then moved; a fold's commit message stating a cliff as "nine heads,
256 lines" that was fifteen and 336 a week later; a hand audit of 38 pull
requests that was two rows short seven days on. In all three the evidence stayed
in the tree reading as current and matching nothing. Nothing here detects that,
because detecting it means reading the claim, and no gate reads claims.

So read them. Four forms are re-measurable without interpretation:

  * `N tests pass`      — check the commit out and count what `unittest` finds.
  * `no version bump`   — the commit's own diff must not touch a version field.
  * `stacked on #N`     — that pull request's head must be an ancestor.
  * `N of M heads`      — M is not re-measurable; the queue it described is gone.
                          Report it against today's count, which dates the claim
                          rather than judging it.

The first three get a verdict. The fourth gets a date, and the difference is the
point: a tool that cannot re-measure a claim must say so rather than score it,
or the one false row teaches a reader to skip the section.

A test count has a third case, and it is the one worth the tool. *412 tests pass
with #59's gates* is neither confirmed nor stale — it was measured in a tree
assembled from two branches, which exists nowhere, so no reviewer can reach it
and no CI run has ever produced it. Same for a suite count asserted by a commit
whose tree carries no suite. Those are reported as FOREIGN-TREE and left
unscored, because the defect is not the number.

This is a report, not a gate: exit 0 always. A commit message is immutable once
pushed, so a red CI run on a stale claim would demand a history rewrite to clear
— the wrong remedy for a true statement that has merely aged. What the operator
does with a STALE row is a judgement about whether the branch still means what it
said, and that judgement is theirs.

    python3 scripts/claim_audit.py                 # every open head on origin
    python3 scripts/claim_audit.py HEAD            # just this branch
    python3 scripts/claim_audit.py --no-tests      # skip the worktree checkouts
"""

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# A claim is (kind, regex). The regex's groups are the numbers to re-measure.
CLAIM_PATTERNS = (
    ("tests", re.compile(r"\b(\d+)\s+tests?\s+pass(?:es|ed)?\b", re.I)),
    ("no-bump", re.compile(r"\bno version bump\b", re.I)),
    ("stacked", re.compile(r"\bstacked on #(\d+)", re.I)),
    ("queue-size", re.compile(r"\b(\d+)\s+of\s+(\d+)\s+heads\b", re.I)),
)

VERSION_FIELD = re.compile(r'^[+-]\s*"version"\s*:')

# A test count qualified by another pull request — "412 tests pass with #59's
# gates" — is a measurement of a tree that exists on no branch. It is not stale
# and it is not wrong; it is unreachable, and saying so is the whole finding.
FOREIGN = re.compile(r"#\d+")
FOREIGN_WINDOW = 60


def git(*args, check=True):
    """Capture stdout of a git command run in the repo."""
    r = subprocess.run(
        ("git", "-C", str(ROOT)) + args, capture_output=True, text=True
    )
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def extract_claims(message):
    """Pull every re-measurable claim out of one commit message.

    Returns a list of (kind, matched_text, groups). Order follows the message so
    a reader can find the sentence the row came from.
    """
    found = []
    for kind, pattern in CLAIM_PATTERNS:
        for m in pattern.finditer(message):
            found.append((kind, m.group(0), m.groups(), m.start()))
    found.sort(key=lambda c: c[3])
    return [(k, t, g, message[s:s + FOREIGN_WINDOW]) for k, t, g, s in found]


def names_foreign_tree(tail):
    """Does the text right after a claim attribute it to another pull request?"""
    return bool(FOREIGN.search(tail))


def verdict_no_bump(diff):
    """A `no version bump` claim holds when the diff touches no version field."""
    touched = [l for l in diff.splitlines() if VERSION_FIELD.match(l)]
    if touched:
        return "FALSE", f"diff changes a version field ({len(touched)} lines)"
    return "CONFIRMED", "no version field in the diff"


def count_tests(worktree):
    """Run the repo's own suite in `worktree` and return (count, detail)."""
    if not (worktree / "scripts").is_dir():
        return None, "no scripts/ in this tree"
    r = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "scripts"],
        cwd=worktree,
        capture_output=True,
        text=True,
    )
    m = re.search(r"^Ran (\d+) tests?", r.stderr, re.M)
    if not m:
        return None, "unittest produced no count"
    count = int(m.group(1))
    if r.returncode:
        return count, "suite is red"
    return count, "suite is green"


def verdict_tests(commit, claimed, tail, enabled):
    if not enabled:
        return "SKIPPED", "--no-tests"
    if names_foreign_tree(tail):
        return "FOREIGN-TREE", "counted in a tree assembled with another branch"
    with tempfile.TemporaryDirectory(prefix="claim-audit-") as tmp:
        wt = Path(tmp) / "t"
        git("worktree", "add", "--detach", "--quiet", str(wt), commit)
        try:
            actual, detail = count_tests(wt)
        finally:
            git("worktree", "remove", "--force", str(wt), check=False)
    if actual is None:
        if detail == "no scripts/ in this tree":
            return "FOREIGN-TREE", "claims a suite count in a tree with no suite"
        return "UNMEASURABLE", detail
    if actual == claimed:
        return "CONFIRMED", f"{actual} tests, {detail}"
    return "STALE", f"claimed {claimed}, tree runs {actual} ({detail})"


def verdict_stacked(commit, pr_number, pr_heads):
    """`stacked on #N` holds when N's head commit is an ancestor of this one."""
    head = pr_heads.get(pr_number)
    if head is None:
        return "UNMEASURABLE", f"#{pr_number} is not an open pull request"
    sha = git("rev-parse", "--verify", "--quiet", head, check=False).strip()
    if not sha:
        return "UNMEASURABLE", f"no local ref for {head}"
    ancestor = subprocess.run(
        ("git", "-C", str(ROOT), "merge-base", "--is-ancestor", sha, commit),
        capture_output=True,
    )
    if ancestor.returncode == 0:
        return "CONFIRMED", f"#{pr_number} ({head}) is an ancestor"
    return "STALE", f"#{pr_number} ({head}) has moved off this history"


def open_pr_heads():
    """Map open PR number -> `origin/<branch>`. Empty when `gh` is unavailable."""
    r = subprocess.run(
        ("gh", "pr", "list", "--state", "open", "--limit", "300",
         "--json", "number,headRefName"),
        capture_output=True, text=True, cwd=str(ROOT),
    )
    if r.returncode:
        return {}
    import json

    return {e["number"]: "origin/" + e["headRefName"] for e in json.loads(r.stdout)}


def remote_heads():
    refs = git("for-each-ref", "--format=%(refname:short)", "refs/remotes/origin").split()
    return [r for r in refs if r not in ("origin/HEAD", "origin/main")]


def audit(heads, run_tests=True):
    """Yield one row per claim: (head, commit, kind, text, verdict, detail)."""
    pr_heads = open_pr_heads()
    today_heads = len(remote_heads())
    seen = set()
    for head in heads:
        for commit in git("log", "--format=%H", f"origin/main..{head}").split():
            if commit in seen:
                continue
            seen.add(commit)
            message = git("log", "-1", "--format=%B", commit)
            for kind, text, groups, tail in extract_claims(message):
                if kind == "no-bump":
                    v, d = verdict_no_bump(git("show", "--format=", commit))
                elif kind == "tests":
                    v, d = verdict_tests(commit, int(groups[0]), tail, run_tests)
                elif kind == "stacked":
                    v, d = verdict_stacked(commit, int(groups[0]), pr_heads)
                else:
                    v, d = "DATED", f"queue was {groups[1]} heads, today it is {today_heads}"
                yield head, commit, kind, text, v, d


ORDER = ("FALSE", "STALE", "FOREIGN-TREE", "DATED", "UNMEASURABLE", "SKIPPED",
         "CONFIRMED")


def report(rows, out=sys.stdout):
    rows = list(rows)
    if not rows:
        print("No re-measurable claims found.", file=out)
        return
    for verdict in ORDER:
        group = [r for r in rows if r[4] == verdict]
        if not group:
            continue
        print(f"\n{verdict}  ({len(group)})", file=out)
        for head, commit, kind, text, _, detail in group:
            print(f"  {commit[:8]}  {head.replace('origin/', ''):42.42}  "
                  f"{kind:10} {text!r} — {detail}", file=out)
    counted = [r for r in rows if r[4] in ("CONFIRMED", "STALE", "FALSE")]
    held = sum(1 for r in counted if r[4] == "CONFIRMED")
    print(f"\n{len(rows)} claims, {len(counted)} re-measurable, {held} still hold.", file=out)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("heads", nargs="*", help="refs to audit (default: every open head)")
    p.add_argument("--no-tests", action="store_true",
                   help="skip the worktree checkouts that re-count the suite")
    a = p.parse_args(argv)
    report(audit(a.heads or remote_heads(), run_tests=not a.no_tests))
    return 0


if __name__ == "__main__":
    sys.exit(main())
