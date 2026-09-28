#!/usr/bin/env python3
"""Fail a branch that changes a plugin's content without bumping its version.

`check_plugins.py` already asserts the two manifests *agree* on a version. That is
parity, not freshness: both files can say `0.6.0` while the skill tree underneath
them has been rewritten. The version is the only signal a user's installed copy
consults, so an unbumped version means the change never reaches anyone — a perfect
fix that does not ship is indistinguishable from no fix at all.

This check is deliberately git-aware (its sibling is not): freshness is a claim
about the diff, not about the tree.

Two questions, two baselines — and they are not the same ref:

  * *which files changed* is a claim about the diff, so its baseline is the
    merge-base with the target branch.
  * *what version users already have* is a claim about what shipped, so its
    baseline is the newest release tag.

Measuring the version against the merge-base makes the verdict depend on the
branch's position rather than on its content. An un-rebased branch is stable —
its fork point never moves — but rebasing one is enough to flip it: onto a main
that has already landed 0.6.1, the base now says 0.6.1, so the branch owes
0.6.2, and the next rebased sibling owes 0.6.3. A queue of N independent PRs is
pushed onto N distinct values of one scalar in two fixed files, each invalidated
whenever the landing order changes — and none of that is a fact about whether
the change ships. Against a release tag they may all name the same next version
(identical edits to one line merge without conflict) and one release ships them
together: a bump is owed once per release, not once per pull request.

With no release tag the check falls back to the merge-base, because a repo that
has never published has no better answer for what users have installed. That
fallback is the pre-existing behaviour, so adopting a release tag is a strict
improvement and never a prerequisite.

Usage: check_version_bump.py [base-ref]
Exit 0 = clean or nothing to compare, 1 = a content change with no bump.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def git(*args: str) -> str:
    return subprocess.run(
        ("git", "-C", str(ROOT), *args), capture_output=True, text=True, check=True
    ).stdout.strip()


def resolve_base(argv: list[str]) -> str | None:
    """First ref that exists among: the argument, CI's base branch, main."""
    candidates = [*argv[1:2]]
    if ref := os.environ.get("GITHUB_BASE_REF"):
        candidates += [f"origin/{ref}", ref]
    candidates += ["origin/main", "main"]
    for ref in candidates:
        try:
            return git("merge-base", ref, "HEAD")
        except subprocess.CalledProcessError:
            continue
    return None


def released_tag() -> str | None:
    """Newest MAJOR.MINOR.PATCH tag (optionally `v`-prefixed), or None if none exist."""
    tags = git("tag", "--list", "--sort=-v:refname").splitlines()
    return next((t for t in tags if re.fullmatch(r"v?\d+\.\d+\.\d+", t)), None)


def semver(raw: str, where: str) -> tuple[int, ...]:
    if not re.fullmatch(r"\d+\.\d+\.\d+", raw):
        sys.exit(f"error: {where} version {raw!r} is not MAJOR.MINOR.PATCH")
    return tuple(int(part) for part in raw.split("."))


def main(argv: list[str]) -> int:
    base = resolve_base(argv)
    if base is None:
        print("no base ref to compare against — skipping")
        return 0

    changed = set(git("diff", "--name-only", base, "HEAD").splitlines())
    if not changed:
        print("no changes against base — nothing to check")
        return 0

    shipped_ref = released_tag()
    if shipped_ref is None:
        shipped_ref = base
        print("no release tag — measuring the version against the merge-base")

    errors: list[str] = []
    marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())

    for entry in marketplace["plugins"]:
        source = str(Path(entry["source"]).relative_to("."))
        manifest = f"{source}/.claude-plugin/plugin.json"
        touched = sorted(f for f in changed if f.startswith(f"{source}/") and f != manifest)
        if not touched:
            continue

        try:
            shipped = json.loads(git("show", f"{shipped_ref}:{manifest}"))["version"]
        except (subprocess.CalledProcessError, KeyError):
            continue  # no version to measure against: a brand-new plugin owes no bump

        after = json.loads((ROOT / manifest).read_text())["version"]
        if semver(after, manifest) > semver(shipped, f"{manifest}@{shipped_ref}"):
            print(f"{entry['name']}: {shipped} → {after} ({len(touched)} file(s) changed)")
            continue

        errors.append(
            f"{entry['name']}: version is still {after}, the version already at {shipped_ref}, "
            f"but {len(touched)} content file(s) changed — name the next version in {manifest} "
            f"and in .claude-plugin/marketplace.json. Sibling branches may name the same one.\n"
            + "\n".join(f"    {f}" for f in touched)
        )

    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
