#!/usr/bin/env python3
"""Check that every gate in `scripts/` is actually invoked by CI on a pull request.

Every checker in this repo gates the plugin. Nothing gates the checkers. A gate
is two artifacts — a script and a workflow step that runs it — and only the
script is reviewable: it has a docstring, tests, and a diff a human reads. The
step is one line in a YAML file, frequently in a *different* commit, and when it
is missing nothing anywhere is red. The gate imports cleanly, its unit tests
pass, and it has never once been pointed at the tree it was written to protect.

That failure is silent in the worst way, because the evidence points the other
way. `python3 -m unittest discover -s scripts` collects a checker's tests
whether or not any workflow runs the checker, so an orphaned gate shows a green
tick next to its own name. The tests prove the script is correct about a fixture.
Only a workflow step proves it ever read this repo.

Two directions, both errors:

- a `scripts/check_*.py` that no pull-request-triggered workflow runs. Guarding
  nothing. A workflow that fires only `on: push: branches: [main]` does not
  count: it reports after the merge it was supposed to prevent.
- a workflow step naming a `scripts/*.py` that does not exist. This is the
  rename direction, and it is how a working gate becomes a missing one without
  anybody editing the gate.

Coverage is satisfied by *any* PR-triggered workflow, so a gate may keep its own
workflow file or join an existing one — this fixes the wiring, not the layout.

Usage: python3 scripts/check_ci_coverage.py [root]
Exit 1 on errors, 0 otherwise.
"""

import re
import sys
from pathlib import Path

# `run: python3 scripts/foo.py` — a step that names one script. Deliberately
# does not match `unittest discover -s scripts`: discovery runs test modules,
# never the checkers, so a repo whose CI is discovery alone runs zero gates.
NAMED = re.compile(r"scripts/([\w.-]+\.py)")
# `on:` needs the key, not the phrase — `pull_request` also appears in comments
# and in `github.event.pull_request.*` expressions inside a step.
PULL_REQUEST = re.compile(r"^\s{2,}pull_request:\s*$", re.M)


def scan(root):
    """(checkers, {script name: [workflow]}, {script name: [PR-triggered workflow]})."""
    checkers = {p.name for p in (root / "scripts").glob("check_*.py")}
    named, gating = {}, {}
    for workflow in sorted((root / ".github/workflows").glob("*.y*ml")):
        text = workflow.read_text(encoding="utf-8")
        for name in NAMED.findall(text):
            named.setdefault(name, []).append(workflow.name)
            if PULL_REQUEST.search(text):
                gating.setdefault(name, []).append(workflow.name)
    return checkers, named, gating


def check(checkers, named, gating, present):
    """(errors, warnings) for one tree. `present` is every file in `scripts/`."""
    errors = []
    for name in sorted(checkers - gating.keys()):
        where = named.get(name)
        errors.append(
            f"scripts/{name}: run only by {', '.join(where)}, which does not trigger "
            "on pull_request — it reports after the merge it should have blocked"
            if where else
            f"scripts/{name}: no workflow runs it — the gate guards nothing"
        )
    for name in sorted(named.keys() - present):
        errors.append(
            f"{', '.join(named[name])}: runs `scripts/{name}`, which does not exist"
        )
    return errors, []


def main(argv=None):
    root = Path((argv or sys.argv[1:] or ["."])[0]).resolve()
    checkers, named, gating = scan(root)
    present = {p.name for p in (root / "scripts").glob("*.py")}
    errors, warnings = check(checkers, named, gating, present)

    for warning in warnings:
        print(f"warning: {warning}")
    for error in errors:
        print(f"error: {error}")
    print(f"{len(checkers)} checker(s), {len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
