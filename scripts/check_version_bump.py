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

It is an improvement with a precondition, though, and the precondition is not
this script's to enforce: releases have to actually happen. The floor is the tag,
not `main`, so a version that a queue of PRs names, lands, and nobody tags leaves
the floor exactly where it was — and every later content change may keep naming
that same version and pass. The merge-base fallback never freezes — its floor
moves on every merge — whereas this one can freeze while the tree under it is
rewritten, which is the failure the check exists to prevent, reached through the
remedy instead of the defect. So the check also *reports* when the base branch
has moved past the newest tag. That is a warning, never an error — failing the
PR would put the queue back on N distinct values, and the debt belongs to the
release, not to whoever happens to push next.

The same report is owed in the opposite state, and for the same reason. A repo
with *no* release tag never enters the mode described above: the fallback is the
only behaviour it ever has, so the whole release baseline is inert and the queue
is on N distinct values by default. A moving floor is not a published version —
nothing has been published at all — and it is the floor's movement that does the
damage: land one wave and every branch behind it owes a value above whatever
landed, re-typed in both manifests after each merge, once per wave. That is
strictly worse than the stale-floor case, and it was the quieter of the two. So
an absent tag is reported on the same terms: a warning naming the one action —
tag what is already shipped — that lets siblings share a version again.

The two manifests are excluded from the content set so that a lone bump cannot
justify itself. That reason is about one key — `version` — and excluding the
files wholesale extended it to every other key in them. `description` is shipped
content by the same argument the check rests on: it is the text a marketplace
client displays and a model reads to decide whether to load the plugin at all.
So the exclusion is narrowed to what its reason covers: a manifest counts as
content whenever anything *other than* `version` differs from the base. The
comparison is semantic, not textual — reindenting a manifest ships nothing.

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
MARKETPLACE = ".claude-plugin/marketplace.json"


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


def json_at(ref: str, path: str) -> dict | None:
    """The JSON document at `path` in `ref`, or None if it is absent or unreadable."""
    try:
        return json.loads(git("show", f"{ref}:{path}"))
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None


def entry_of(catalog: dict | None, name: str) -> dict | None:
    return next((e for e in (catalog or {}).get("plugins", []) if e.get("name") == name), None)


def sans_version(doc: dict | None) -> dict | None:
    return None if doc is None else {k: v for k, v in doc.items() if k != "version"}


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
    unreleased: list[str] = []

    tag = released_tag()
    shipped_ref = tag
    if shipped_ref is None:
        shipped_ref = base
        print("no release tag — measuring the version against the merge-base")
    marketplace = json.loads((ROOT / MARKETPLACE).read_text())
    base_catalog = json_at(base, MARKETPLACE)

    for entry in marketplace["plugins"]:
        source = str(Path(entry["source"]).relative_to("."))
        manifest = f"{source}/.claude-plugin/plugin.json"
        touched = [f for f in changed if f.startswith(f"{source}/") and f != manifest]

        # A manifest is excluded so a lone bump cannot justify itself — `version`
        # only. Any other key in either one is shipped content.
        for path, before, after_doc in (
            (manifest, json_at(base, manifest), json.loads((ROOT / manifest).read_text())),
            (MARKETPLACE, entry_of(base_catalog, entry["name"]), entry),
        ):
            if before is not None and sans_version(before) != sans_version(after_doc):
                touched.append(path)

        if not touched:
            continue
        touched.sort()

        try:
            shipped = json.loads(git("show", f"{shipped_ref}:{manifest}"))["version"]
        except (subprocess.CalledProcessError, KeyError):
            continue  # no version to measure against: a brand-new plugin owes no bump

        if tag is None:
            # Same terms as the stale-tag note below: reported only for a plugin
            # this run actually measured, so a scripts-only PR gets no release talk.
            unreleased.append(
                f"{entry['name']}: no release tag exists, so the floor is the merge-base and "
                "the release baseline this check is built on is inert. That floor moves on "
                "every merge, so each branch behind the one that lands owes a version above "
                f"it — one distinct value per wave, re-typed in {manifest} and "
                f"{MARKETPLACE} after every merge. Tag what is already shipped and siblings "
                "may name the same next version again."
            )

        if tag is not None:
            try:
                on_base = json.loads(git("show", f"{base}:{manifest}"))["version"]
            except (subprocess.CalledProcessError, KeyError):
                on_base = shipped
            if semver(on_base, f"{manifest}@{base}") > semver(shipped, f"{manifest}@{tag}"):
                unreleased.append(
                    f"{entry['name']}: the base branch already names {on_base}, but the newest "
                    f"release tag is {tag} ({shipped}). Until {on_base} is tagged, the floor this "
                    f"check measures against does not move, so any further content change may "
                    f"keep naming {on_base} and pass — cut the release."
                )

        after = json.loads((ROOT / manifest).read_text())["version"]
        if semver(after, manifest) > semver(shipped, f"{manifest}@{shipped_ref}"):
            print(f"{entry['name']}: {shipped} → {after} ({len(touched)} file(s) changed)")
            continue

        # The sibling-sharing advice holds against a tag and not against the
        # merge-base, where the floor moves on every merge — see the note above.
        sharing = (
            "Sibling branches may name the same one."
            if tag is not None
            else "Siblings cannot share it until a release is tagged."
        )
        errors.append(
            f"{entry['name']}: version is still {after}, the version already at {shipped_ref}, "
            f"but {len(touched)} content file(s) changed — name the next version in {manifest} "
            f"and in .claude-plugin/marketplace.json. {sharing}\n"
            + "\n".join(f"    {f}" for f in touched)
        )

    for note in unreleased:
        print(f"warning: {note}", file=sys.stderr)
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
