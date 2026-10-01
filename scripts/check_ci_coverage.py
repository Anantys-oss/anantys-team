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

`push: branches: [main]` is one way a trigger fires too late, not the only one,
and the others live *under* the `pull_request:` key rather than beside it. The
test is therefore not "is `pull_request` present" but "can this workflow fail
while the branch is still a branch":

- `types:` naming only events that follow the decision — `closed`, `labeled` —
  fires on a pull request and still reports after the merge. Same defect as
  `push: [main]`, one nesting level deeper.
- `paths:` / `paths-ignore:` narrows the trigger to a subtree. Whether that
  subtree contains what the gate reads is a fact about the gate, and a checker
  that greps `run:` lines cannot know it: `check_plugins.py` reads `plugins/`,
  `check_ci_coverage.py` reads `.github/` and `scripts/`, and nothing in the
  YAML says so. A filtered trigger is therefore not counted — give the gate an
  unfiltered workflow, or drop the filter. Fail closed: the alternative is
  certifying a gate that never once ran on the tree it guards.

Both shapes are the failure this checker exists to catch, dressed as coverage.

And one more, in the direction the argument above points away from. Discovery is
used twice as the counter-example — it collects a checker's tests whether or not
any workflow runs the checker, so `NAMED` deliberately does not match it. But
`python3 -m unittest discover -s scripts` is *also* the only step that runs any
test in this repo: six of the seven test modules are named by no workflow line at
all. Delete both discover steps and every assertion above still holds — the gates
are wired, each to a blocking workflow, and nothing is left proving one of them
is correct about anything. So a third error: a tree with test modules must run
them before the merge too. Not per module, which would put every new test file on
a workflow edit; once, for the step that collects them all.

The rename direction has no equivalent here and is deliberately left open: a
module renamed out of `test_*.py` drops out of discovery silently, and the only
check that would catch it is one that names each module in CI — the serialisation
this error exists to avoid.

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
# The step `NAMED` is written not to see. Nothing else runs a test module here, so
# its absence has to be an error of its own.
DISCOVER = re.compile(r"unittest\s+discover")
# `on:` at column 0 — the key, not the phrase. `pull_request` also appears in
# comments and in `github.event.pull_request.*` expressions inside a step. YAML
# lets the key be quoted, because bare `on` is also the boolean `true`.
ON = re.compile(r"^(?:on|['\"]on['\"]):(.*)$")
# The `pull_request` activity types that fire while the branch is still a branch.
# Anything outside this set reports on a decision already taken.
PREVENTIVE = {"opened", "synchronize", "reopened", "ready_for_review", "edited"}


def nested(lines, index):
    """The lines under `lines[index]` — strictly more indented, blanks dropped."""
    outer = len(lines[index]) - len(lines[index].lstrip())
    body = []
    for line in lines[index + 1:]:
        if not line.strip():
            continue
        if len(line) - len(line.lstrip()) <= outer:
            break
        body.append(line)
    return body


def blocking(text):
    """None if this workflow can fail before the merge, else why it cannot.

    Hand-rolled on purpose: every checker in `scripts/` is stdlib-only, and the
    shapes that matter are two levels deep.
    """
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not (on := ON.match(line)):
            continue
        if inline := on.group(1).split("#", 1)[0].strip():
            # `on: pull_request` or `on: [push, pull_request]` — no filters possible.
            return None if "pull_request" in inline else "does not trigger on pull_request"
        body = nested(lines, i)
        keys = [n for n, ln in enumerate(body) if re.match(r"^\s*pull_request:", ln)]
        if not keys:
            return "does not trigger on pull_request"
        inner = nested(body, keys[0])
        for n, ln in enumerate(inner):
            if re.match(r"^\s*paths(-ignore)?:", ln):
                return ("fires on pull_request only for selected paths, which may exclude "
                        "what the gate reads")
            if kinds := re.match(r"^\s*types:\s*(.*)$", ln):
                listed = set(re.findall(r"[\w-]+", kinds.group(1))) or set(
                    re.findall(r"[\w-]+", " ".join(nested(inner, n)))
                )
                if not listed & PREVENTIVE:
                    return ("fires on pull_request only for "
                            f"{', '.join(sorted(listed))}, all after the decision")
        return None
    return "does not trigger on pull_request"


def scan(root):
    """(checkers, {script: [workflow]}, {script: [blocking workflow]}, {workflow: why not},
    whether some blocking workflow runs the test suite)."""
    checkers = {p.name for p in (root / "scripts").glob("check_*.py")}
    named, gating, why = {}, {}, {}
    discovers = False
    for workflow in sorted((root / ".github/workflows").glob("*.y*ml")):
        text = workflow.read_text(encoding="utf-8")
        reason = blocking(text)
        if reason:
            why[workflow.name] = reason
        else:
            discovers = discovers or bool(DISCOVER.search(text))
        for name in NAMED.findall(text):
            named.setdefault(name, []).append(workflow.name)
            if reason is None:
                gating.setdefault(name, []).append(workflow.name)
    return checkers, named, gating, why, discovers


def check(checkers, named, gating, present, why, discovers):
    """(errors, warnings) for one tree. `present` is every file in `scripts/`."""
    why = why or {}
    errors = []
    if not discovers and any(name.startswith("test_") for name in present):
        errors.append(
            "no pull-request workflow runs `unittest discover -s scripts` — the gates "
            "are wired, and nothing runs the tests that say they are right"
        )
    for name in sorted(checkers - gating.keys()):
        where = named.get(name)
        errors.append(
            f"scripts/{name}: run only by "
            + "; ".join(f"{w}, which {why.get(w, 'does not trigger on pull_request')}" for w in where)
            + " — the gate cannot block the merge it exists to prevent"
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
    checkers, named, gating, why, discovers = scan(root)
    present = {p.name for p in (root / "scripts").glob("*.py")}
    errors, warnings = check(checkers, named, gating, present, why, discovers)

    for warning in warnings:
        print(f"warning: {warning}")
    for error in errors:
        print(f"error: {error}")
    print(f"{len(checkers)} checker(s), {len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
