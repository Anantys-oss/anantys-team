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
        ("git", "-C", str(ROOT), *args), capture_output=True, text=True, check=True
    )
    return [line for line in out.stdout.splitlines() if line]


def generated(path: str) -> bool:
    return any(path.endswith(m) if m[0] == "." else m in path for m in GENERATED)


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    flagged = {path for path in git("ls-files") if generated(path)}
    for path in sorted(flagged):
        errors.append(f"{path}: generated output is tracked — `git rm -r --cached` it")

    # The general rule needs an exclude source to measure against. An absent one is not
    # an error — the `.gitignore` is a file some *other* change lands, and reddening every
    # branch until it arrives forces an order on changes that have none. It is not silence
    # either: a check that prints nothing reports health it never measured.
    if (ROOT / ".gitignore").is_file():
        for path in sorted(set(git("ls-files", "-i", "-c", "--exclude-standard")) - flagged):
            errors.append(
                f"{path}: tracked, and ignored — `.gitignore` hides it from `git status` "
                f"instead of removing it; `git rm --cached` it, or stop ignoring it"
            )
    else:
        warnings.append(
            "no .gitignore, so only generated output is checked — a tracked file ignored "
            "by some other rule goes unmeasured until the .gitignore lands"
        )

    for warning in warnings:
        print(f"warning: {warning}")
    for error in errors:
        print(f"error: {error}")
    print(f"{len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
