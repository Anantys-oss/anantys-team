#!/usr/bin/env python3
"""Fail a branch that changes a plugin's content without bumping its version.

`check_plugins.py` already asserts the two manifests *agree* on a version. That is
parity, not freshness: both files can say `0.6.0` while the skill tree underneath
them has been rewritten. The version is the only signal a user's installed copy
consults, so an unbumped version means the change never reaches anyone — a perfect
fix that does not ship is indistinguishable from no fix at all.

This check is deliberately git-aware (its sibling is not): freshness is a claim
about the diff, not about the tree.

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

    errors: list[str] = []
    marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())

    for entry in marketplace["plugins"]:
        source = str(Path(entry["source"]).relative_to("."))
        manifest = f"{source}/.claude-plugin/plugin.json"
        touched = sorted(f for f in changed if f.startswith(f"{source}/") and f != manifest)
        if not touched:
            continue

        try:
            before = json.loads(git("show", f"{base}:{manifest}"))["version"]
        except (subprocess.CalledProcessError, KeyError):
            continue  # no version at base: a brand-new plugin owes no bump

        after = json.loads((ROOT / manifest).read_text())["version"]
        if semver(after, manifest) > semver(before, f"{manifest}@base"):
            print(f"{entry['name']}: {before} → {after} ({len(touched)} file(s) changed)")
            continue

        errors.append(
            f"{entry['name']}: version is still {after} but {len(touched)} content file(s) "
            f"changed — bump it in {manifest} and in .claude-plugin/marketplace.json.\n"
            + "\n".join(f"    {f}" for f in touched)
        )

    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
