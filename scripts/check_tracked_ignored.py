#!/usr/bin/env python3
"""A tracked file must not be one git was told to ignore.

`.gitignore` does not untrack. A path already in the index stays there, and the
ignore rule then suppresses the one signal that would ever surface it: `git status`
goes quiet, every per-PR gate stays green, and the file is carried in every clone
forever. The failure is therefore silent *by construction*, and it gets quieter the
moment someone does the thing that looks like the fix.

That shape is already in this queue. Three open branches each committed two
`scripts/__pycache__/*.pyc`; two different branches add a `.gitignore` naming
`__pycache__/`. Every one of those five is individually green, and they merge
pairwise clean, because the files sit at different paths and nothing compares the
index against the exclude rules. Only the assembled tree holds both halves.

Both halves answer a question about *git's* state, so both must be asked in git's
units. A marker is a directory when it says so (a trailing `/`), not when its first
character happens to be a dot; and the exclude rules `--exclude-standard` consults
are not one root `.gitignore`. And the inventory of those rules is a *model* of what
git consults, so it may only choose the warning — never gate the measurement. Where
this still cannot see: a rule file git reads and the inventory does not (a global
`core.excludesFile`) leaves the warning claiming less was measured, never more.

Exit 0 = clean (warnings allowed), 1 = at least one error.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Output a tool regenerates from tracked sources. Never a legitimate tracked file,
#: with or without an exclude rule — which is what keeps this check from being inert
#: on the branches that have no `.gitignore` yet.
GENERATED = ("__pycache__/", ".pyc", ".pyo", ".DS_Store", ".egg-info/")


def git(*args: str) -> list[str]:
    out = subprocess.run(
        # `core.quotePath` defaults on, and a quoted path ends in `"` — which is how a
        # tracked `.pyc` under a non-ASCII directory slips every suffix marker below.
        ("git", "-C", str(ROOT), "-c", "core.quotePath=false", *args),
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in out.stdout.splitlines() if line]


def generated(path: str) -> bool:
    """A trailing `/` makes a marker a directory — match it anywhere in the path.

    Dispatching on the *first* character instead silently killed `.egg-info/`:
    `git ls-files` never emits a trailing slash, so no path can end with one.
    """
    return any(m in path if m.endswith("/") else path.endswith(m) for m in GENERATED)


def probe(marker: str) -> str:
    """A path `marker` must match. Keeps a dead marker from shipping unnoticed."""
    return f"pkg/{marker}out" if marker.endswith("/") else f"pkg/x{marker}"


def exclude_sources() -> list[str]:
    """What `--exclude-standard` consults and this repo can carry, in git's own units.

    A nested `sub/.gitignore` and a rule in `info/exclude` are each enough for the
    measurement to answer; neither is a root `.gitignore`. Where `info/exclude` lives
    is git's to say — in a linked worktree (which is how `pr_landing_order.py --verify`
    runs every gate) `ROOT/.git` is a file, so composing the path by hand finds nothing.
    """
    seen = (*git("ls-files"), *git("ls-files", "--others", "--exclude-standard"))
    sources = sorted({p for p in seen if Path(p).name == ".gitignore"})
    label = git("rev-parse", "--git-path", "info/exclude")[0]
    info = ROOT / label
    if info.is_file() and any(
        line.strip() and not line.lstrip().startswith("#")
        for line in info.read_text(encoding="utf-8").splitlines()
    ):
        sources.append(label)
    return sources


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    for marker in GENERATED:
        if not generated(probe(marker)):
            errors.append(f"{marker}: marker matches nothing — `generated()` cannot see it")

    flagged = {path for path in git("ls-files") if generated(path)}
    for path in sorted(flagged):
        errors.append(f"{path}: generated output is tracked — `git rm -r --cached` it")

    # The general rule, asked of git unconditionally. Gating it on `exclude_sources()`
    # made a hand-rolled inventory of git's rule files able to *drop* a path git had
    # already named: on any tree without a root `.gitignore`, `ls-files -i -c` returned
    # the file and this printed "no exclude source … goes unmeasured" and exited 0.
    ignored = sorted(set(git("ls-files", "-i", "-c", "--exclude-standard")) - flagged)
    for path in ignored:
        errors.append(
            f"{path}: tracked, and ignored — `.gitignore` hides it from `git status` "
            f"instead of removing it; `git rm --cached` it, or stop ignoring it"
        )

    # An absent exclude source is not an error — the `.gitignore` is a file some *other*
    # change lands, and reddening every branch until it arrives forces an order on changes
    # that have none. It is not silence either: a check that prints nothing reports health
    # it never measured. A finding of its own settles the question, so only ask when empty.
    if not ignored and not exclude_sources():
        warnings.append(
            "no exclude source, so only generated output is checked — a tracked file "
            "ignored by some other rule goes unmeasured until one lands"
        )

    for warning in warnings:
        print(f"warning: {warning}")
    for error in errors:
        print(f"error: {error}")
    print(f"{len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
