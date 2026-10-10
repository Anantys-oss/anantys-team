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

All of which assumes the trigger being read is `pull_request` at all, and that
assumption was tested two different ways in the same function. A nested `on:`
block is matched by *key*, so `pull_request_target:` is correctly a different
event. A flow-form `on:` — `on: pull_request`, `on: [push, pull_request]` — was
matched by *containment*, and three real events spell the name as a prefix:
`pull_request_target`, `pull_request_review`, `pull_request_review_comment`. So
one wiring got two opposite verdicts depending only on which YAML style spelled
it, and the loose style was the one that certified. `pull_request_review` is the
sharp case: it fires when a human submits a review and never on open or
synchronize, so a gate wired only there has not run at the moment the merge
button becomes available. Whole tokens, both branches.

A flow *mapping* — `on: {pull_request: {types: [closed]}}` — is still read as
unfiltered, because the filters live inside a shape this branch does not walk.
Stated, not covered, like `paths:` and composite actions: nobody writes it, and
the direction to be wrong in is the one that is also loud.

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

The trigger is not the only level at which a workflow stops being able to fail,
and the test above — "can this workflow fail while the branch is still a
branch" — has to be asked of the *step*, not only of `on:`. Two shapes answer it
with no while the trigger still says yes, and neither is visible to a reader of
the `on:` block:

- `continue-on-error: true` on the step, or on the job around it. The gate runs,
  prints every error it found, exits 1, and the check is green. It reads as a
  considered exemption, and it is one line.
- an `if:` on the step or the job. Whether the condition holds on the pull
  request that matters is not a fact in the YAML — the same unknowable the
  `paths:` case already fails closed on, so this one fails closed too.

Both are read per step, because a workflow legitimately gates one checker and
neuters another; a job-level guard disqualifies the whole file.

And the `run:` line itself has to be a `run:` line. `NAMED` used to scan the
whole file, so `# we used to run scripts/check_a.py here` certified the gate it
documents the removal of — the rename direction above, arriving by the one route
that leaves a plausible-looking trail. Comments are stripped before matching.

Stripping them is not enough, because a comment is the *weakest* trail a removed
gate can leave, not the only one. Confining the match to step bodies still read
every key of the step, and a step has keys that cite a command without running
it — `name:`, `env:`, `with:`. So

    - name: scripts/check_a.py
      run: echo skipping for now

certified the gate, and the trail here is strictly better-looking than the
comment's: GitHub renders `name:` in the checks UI, so the evidence a reviewer
sees is a green tick carrying the gate's own name. Matching is therefore confined
to `run:` values — inline and block-scalar alike, per step, nothing else.

Both of this file's directions were wrong together, as they have to be when the
input to each is the same mis-scoped text: a `name:` citing a *deleted* script
raised `runs scripts/X, which does not exist`, an assertion about a `run:` line
nobody had read. A false certificate and a false error are one defect.

A step that reaches a gate by any route other than `run:` — a composite action,
say — is now uncovered. That is the `paths:` trade again, taken the same way:
fail closed, and let the wiring be visible in the file that claims it.

Confining the match to `run:` was still not enough, because a `run:` line only
runs something if the workflow around it parses. GitHub refuses an invalid file
whole — no jobs, no steps, an invalid-workflow banner instead of a run — so a
single stray tab anywhere in `gates.yml` un-runs every gate it names while this
file reports full coverage. That is a better false certificate than either route
above: the `run:` line is a real `run:` line naming the real script, and the only
thing wrong is that nothing ever loaded it. `unloadable` therefore disqualifies
the workflow before `blocking` is consulted.

That paragraph used to call `continue-on-error:` the *only* way to neuter a gate
while leaving the `run:` line where a reviewer looks for it, and used that to
justify reading the two guards per step and stopping. The claim is false, and the
route it misses is the better-looking one, because it is inside the `run:` value
the rest of this file worked to confine matching to:

    - run: python3 scripts/check_a.py || true

Eight characters, no new key, nothing for a reviewer scanning the step's keys to
see — and GitHub's default `bash -e` stops at none of the three shapes that throw
the gate's exit status away:

- `|| …` — `-e` does not apply to the left of a `||`, and the list succeeds.
- a pipeline — the step's status is the *last* command's, and `pipefail` is not
  set. `python3 scripts/check_a.py | tee gate.log` is the accidental form; it is
  a natural thing to write and it is a total neuter.
- a trailing `&` — the gate is backgrounded and the shell exits 0 without it.

`;` is deliberately not among them: under `-e` the shell stops at the failing
command, so `gate; echo done` still fails the step. `set +e`, `if gate; then`,
and `! gate` are the remaining apertures — stated, not covered, the same way
`paths:` and composite actions are.

These are read per *line* of a step's `run:` values rather than per step, because
one `run: |` body legitimately gates one checker on one line and discards
another's status on the next. The same per-line test applies to the discovery
step, which is otherwise the one place a single `|| true` buys back every
assertion the third error above makes.

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
# The only step key that executes anything. `NAMED` and `DISCOVER` are matched
# against these values and nowhere else in the step: a `name:`, an `env:` or a
# `with:` may cite a gate without running it.
RUN = re.compile(r"^\s*(?:-\s*)?run:(.*)$")
# `on:` at column 0 — the key, not the phrase. `pull_request` also appears in
# comments and in `github.event.pull_request.*` expressions inside a step. YAML
# lets the key be quoted, because bare `on` is also the boolean `true`.
ON = re.compile(r"^(?:on|['\"]on['\"]):(.*)$")
# A YAML comment, stripped before anything above is matched. A `#` only opens one
# at the start of a line or after whitespace, so `--arg=a#b` survives. A `#`
# inside a quoted scalar does not, and that is the safe direction: dropping a
# mention un-covers a gate, it never certifies one.
COMMENT = re.compile(r"(?m)(?:(?<=\s)|^)#.*$")
# A step, or a job, that reports without being able to fail the check. `if:` is
# included unconditionally: whether the condition holds on the pull request that
# matters is not a fact this file can read.
NEUTERED = re.compile(r"^\s*(?:-\s*)?(?:continue-on-error:\s*true|if:)(?:\s|$)", re.M)
# The same thing one level further in: a shell construct on the `run:` line that
# throws the gate's exit status away. Matched per line, against lines that already
# name a gate, so an unrelated pipe elsewhere in the body is not read.
DISCARDED = re.compile(r"\|\||\||&\s*$")
# The `pull_request` activity types that fire while the branch is still a branch.
# Anything outside this set reports on a decision already taken.
PREVENTIVE = {"opened", "synchronize", "reopened", "ready_for_review", "edited"}
# A tab used as indentation. YAML forbids it outright, in every parser.
TABBED = re.compile(r"^ *\t", re.M)
# A plain scalar holding `: ` — `name: gate: the gates`. Also fatal in every
# parser, and the one a human writes by accident. Values that open with a quote,
# a block indicator or a flow collector may legally contain it, so they are
# exempt; both patterns see structural lines only, since a `run: |` body may hold
# a tab or a colon as ordinary shell.
PLAIN_COLON = re.compile(
    r"""(?m)^\s*(?:-\s*)?[\w.-]+:[ ]+(?![-#|>&*!'"\[{])[^'"\n]*?:(?:[ ]|$)"""
)


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


def steps(text):
    """Every `- ` bullet under a `steps:` key, as one block of text each."""
    lines = text.splitlines()
    blocks = []
    for i, line in enumerate(lines):
        if not re.match(r"^\s*steps:\s*$", line):
            continue
        body = nested(lines, i)
        starts = [n for n, ln in enumerate(body) if re.match(r"^\s*-", ln)]
        for n, start in enumerate(starts):
            end = starts[n + 1] if n + 1 < len(starts) else len(body)
            blocks.append("\n".join(body[start:end]))
    return blocks


def commands(block):
    """What one step actually executes — its `run:` values, and nothing else.

    Indentation is measured from the `run:` key rather than the line start, so a
    block scalar stops at the step's next key instead of swallowing it.
    """
    lines = block.splitlines()
    body = []
    for i, line in enumerate(lines):
        if not (run := RUN.match(line)):
            continue
        if (inline := run.group(1).strip()) and inline[0] not in "|>":
            body.append(inline)
            continue
        outer = line.index("run:")
        for after in lines[i + 1:]:
            if not after.strip():
                continue
            if len(after) - len(after.lstrip()) <= outer:
                break
            body.append(after)
    return "\n".join(body)


def unloadable(text, bodies):
    """None if GitHub can load this workflow, else why it cannot.

    Two unconditionally-fatal shapes, not a parser: PyYAML is not stdlib and
    every checker in `scripts/` is. Duplicate keys, bad anchors and the rest are
    not caught — stated here rather than hidden, the same way the `paths:` and
    composite-action apertures are. The direction is the safe one: a shape this
    misses leaves coverage as it was, it never invents an error.

    `text` is comment-stripped, which is what makes the tab pattern safe to run:
    a tab-indented *comment* is legal YAML, and stripping leaves it as a
    whitespace-only line that the filter below drops.
    """
    structural = text
    for body in bodies:
        structural = structural.replace(body, "")
    structural = "\n".join(ln for ln in structural.splitlines() if ln.strip())
    if TABBED.search(structural):
        return "indents with a tab, which no YAML parser accepts — GitHub loads no jobs from it"
    if PLAIN_COLON.search(structural):
        return "has an unquoted `: ` in a plain scalar — GitHub loads no jobs from it"
    return None


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
            # `on: pull_request` or `on: [push, pull_request]` — no filters
            # possible. Read as whole tokens, not as a substring: three real
            # events spell `pull_request` as a prefix, and the nested branch
            # below already rejects all three because it matches a key.
            listed = set(re.findall(r"[\w-]+", inline))
            return None if "pull_request" in listed else "does not trigger on pull_request"
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
        text = COMMENT.sub("", workflow.read_text(encoding="utf-8"))
        blocks = steps(text)
        outside = text
        for block in blocks:
            outside = outside.replace(block, "")
        reason = unloadable(text, [commands(b) for b in blocks]) or blocking(text) or (
            "runs its gates in a job that cannot fail the check"
            if NEUTERED.search(outside) else None
        )
        if reason:
            why[workflow.name] = reason
        for block in blocks:
            guarded = reason or (
                "runs the gate in a step that cannot fail the check"
                if NEUTERED.search(block) else None
            )
            for line in commands(block).splitlines():
                discarded = guarded or (
                    "runs the gate in a shell construct that discards its exit status"
                    if DISCARDED.search(line) else None
                )
                if not discarded and DISCOVER.search(line):
                    discovers = True
                for name in NAMED.findall(line):
                    named.setdefault(name, []).append(workflow.name)
                    if discarded:
                        why.setdefault(workflow.name, discarded)
                    else:
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
