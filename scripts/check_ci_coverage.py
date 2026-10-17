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

Three directions, all errors:

- a `scripts/check_*.py` that no pull-request-triggered workflow runs. Guarding
  nothing. A workflow that fires only `on: push: branches: [main]` does not
  count: it reports after the merge it was supposed to prevent.
- a workflow step naming a `scripts/*.py` that does not exist. This is the
  rename direction, and it is how a working gate becomes a missing one without
  anybody editing the gate.
- a `scripts/test_*.py` that the discovery step reaches and collects nothing
  from. Reaching a module is not the same as the module handing the loader a
  case, and the gap between the two is this file's own subject one level in:
  `unittest` sees `TestCase` subclasses and a `load_tests` hook, so a module of
  bare `test_*` functions yields zero cases while `unittest discover` prints
  `NO TESTS RAN` and exits 0. See `yieldless`.

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

- `branches:` / `branches-ignore:` sit under `pull_request:` beside `paths:` and
  were read as neither, so every branch filter counted as coverage. That is the
  right answer for `branches: [main]` — a branch filter is not a path filter, and
  a test says so — but the reasoning does not generalise, and two filters it
  certified fire for no pull request into `main` at all:

      on:                        on:
        pull_request:              pull_request:
          branches: [release]        branches-ignore: ['**']

  The second is the sharp one. It fires for zero pull requests, on any branch,
  and the verdict was that the wiring could block a merge. Unlike `paths:`, this
  axis is readable — the filter lists base branches, and which base matters is
  `main` — so it is decided rather than failed closed: a `branches:` list has to
  admit `main`, a `branches-ignore:` list has to not exclude it.

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

A physical line is not a command, and the whole argument above was priced
against the wrong string. One backslash defeats every shape it enumerates:

    - run: |
        python3 scripts/check_a.py --root . \
          --verbose | tee gate.log

The first line names the gate and holds no construct; the second holds the
construct and names no gate. Both halves of the per-line test are individually
correct and together they certify the accidental form this file calls out by
name. Continuations are therefore joined before matching — and joined only
there, because `unloadable` removes `run:` bodies from the text it scans by
substring and needs them verbatim.

Wrapping breaks the *step* as well, one level out. A step is found by its `- `
bullet, and a wrapped invocation's `--flag` continuation is a bullet to that
pattern:

    - run: |
        python3 scripts/check_a.py \
          --root .
      continue-on-error: true

The `--root .` line opens a second step, so `continue-on-error:` sits in a block
that runs no gate and the gate sits in a block with no guard — and because both
blocks are removed from the text the job-level test reads, nothing sees it
either. Bullets are taken at the outermost bullet indentation only; shell is not
YAML and may not vote on where a step begins.

Indentation is where the YAML reading was wrong in the other direction too. A
block sequence may sit level with the key that owns it, which GitHub's own
documentation does for both keys this file walks:

    steps:
    - run: python3 scripts/check_a.py

Read as empty, that is every gate in the file "guards nothing"; the same shape
under `types:` yields an empty activity set, and the error says the trigger
fires on nothing at all. Loud, unlike the two above, and still a gate that is
wrong about a tree a human can read correctly.

Both of those readings decide where a block *starts*; a blank line is the shape
that decides what a block *contains*, and it was dropped. Three of the rules
above are not applied to text this file reads — they are applied to the file
minus the step blocks, and minus each step's `run:` body, subtracted by verbatim
string. Drop a blank line from either and the subtraction matches nothing, so the
text it was meant to remove stays:

    - run: |
        python3 scripts/check_a.py --soft

        python3 scripts/check_a.py --report
      continue-on-error: true
    - run: python3 scripts/check_b.py

One blank line, between two commands of one `run:` body, in the shape anybody
writes. The guard belongs to the first step and the verdict should name one gate;
instead the step is still in the job's text, so `continue-on-error:` is read as
job-level and `check_b.py` — and this checker, wherever it runs beside them — is
reported as unable to block a merge it blocks. The same miss aims the tab scan at
ordinary indented shell, and a tab is fatal to the whole workflow, so a heredoc
with a blank line above it un-covers every gate in the file.

Both are errors in the loud direction, which is the only reason nine months of
this file's history did not include them: a false error on a wired gate is
noticed the day it fires. It is still a gate that is wrong about a tree a human
reads correctly, and it is wrong about *other* gates than the one it is reading —
the failure mode this file exists to deny. Blanks are kept where they are
interior to a block and dropped where they are not.

Coverage is satisfied by *any* PR-triggered workflow, so a gate may keep its own
workflow file or join an existing one — this fixes the wiring, not the layout.

Usage: python3 scripts/check_ci_coverage.py [root]
Exit 1 on errors, 0 otherwise.
"""

import re
import sys
from fnmatch import fnmatchcase
from pathlib import Path

# The branch a pull request has to be gated *into*. Hard-named, the way
# `check_plugins` and `check_version_bump` hard-name their `origin/main` fallback:
# a `branches:` filter is a claim about base branches, and which base matters is a
# fact about the repo, not about the workflow. GitHub's `*` does not cross `/`;
# `fnmatchcase`'s does, which can only differ for a base branch holding a `/`.
INTEGRATION = "main"

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
# A backslash continuation, joined before `DISCARDED` and `NAMED` are matched. A
# physical line is not a command: wrap a long invocation and the construct that
# throws its status away moves onto a line that names no gate, which is both
# halves of the per-line test disagreeing about the same command. Not applied to
# the text `unloadable` removes, which has to match the file verbatim.
CONTINUED = re.compile(r"\\\n\s*")
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
# The two shapes `unittest`'s loader can see in a test module, and the shape it
# cannot. All three anchored at column 0: a commented-out `#def load_tests` is
# not a hook, and a nested `def test_x` is a closure, not a case.
LOAD_TESTS = re.compile(r"(?m)^def load_tests\b")
TEST_CASE = re.compile(r"(?m)^class\s+\w+\s*\([^)]*TestCase")
BARE_TEST = re.compile(r"(?m)^def (test_\w+)")


def yieldless(text):
    """Why `unittest` collects nothing from this test module, or None.

    `scan` establishes that a discovery step reaches `scripts/`. Reaching a
    module is not the same as the module handing the loader a case: `unittest`
    collects `TestCase` subclasses and a `load_tests` hook, and nothing else. A
    module of bare `test_*` functions — the pytest dialect, which the two
    largest suites here are written in — yields *zero* cases, and `unittest
    discover` reports `NO TESTS RAN` and exits 0. Every gate stays green over a
    suite whose every assertion is false.

    Both such modules in this repo carry a hand-written `load_tests` adapter, so
    the failure is one deletion and one new file away rather than live. That is
    the whole reason to check it here: the adapter is duplicated prose that
    nothing requires, and the gate asserting the suite runs is the only thing
    that can make its absence loud.

    Static on purpose. Executing the module to count its cases would make this
    gate the thing it is checking — green because an import happened to work.
    """
    if LOAD_TESTS.search(text) or TEST_CASE.search(text):
        return None
    bare = BARE_TEST.findall(text)
    if bare:
        return (
            f"defines {len(bare)} bare `test_*` function(s) ({bare[0]}, …) and neither a "
            "`TestCase` subclass nor a `load_tests` hook — `unittest discover` collects "
            "none of them and still exits 0"
        )
    return "hands `unittest discover` no `TestCase` subclass and no `load_tests` hook"


def nested(lines, index):
    """The lines under `lines[index]`, verbatim, interior blanks kept.

    More indented, or a sequence bullet at the key's own indentation: YAML lets a
    block sequence sit level with the key that owns it, and `steps:` and `types:`
    are both written that way in GitHub's own documentation. A strict
    more-indented test reads those blocks as empty, which is wrong in both
    directions at once — no steps found means every gate the file runs "guards
    nothing", and no `types:` found means the set of activity types is empty, so
    the trigger is reported as firing on nothing.

    A blank line cannot end a block — it carries no indentation to compare — but
    dropping one is not free either, because `scan` and `unloadable` subtract
    these lines from the file by *verbatim text* to decide what is shell and what
    is YAML structure. Drop a blank and the subtraction silently matches nothing,
    so a step stays in the text the job-level guard check reads and its `run:`
    body stays in the text the tab scan reads. One blank line inside a guarded
    step therefore moved that step's `continue-on-error:` onto the job and
    condemned every *other* gate in the file; one blank line inside a `run: |`
    body exposed ordinary tab-indented shell to a check that calls a tab fatal,
    which disqualifies the workflow whole. Blanks are buffered and flushed only
    when a later line proves them interior, so a trailing run of blanks before
    the next key is still not part of the block.
    """
    outer = len(lines[index]) - len(lines[index].lstrip())
    body, blanks = [], []
    for line in lines[index + 1:]:
        if not line.strip():
            blanks.append(line)
            continue
        indent = len(line) - len(line.lstrip())
        if indent < outer or (indent == outer and not line.lstrip().startswith("-")):
            break
        body.extend(blanks)
        blanks.clear()
        body.append(line)
    return body


def steps(text):
    """Every `- ` bullet under a `steps:` key, as one block of text each.

    Bullets are taken at the outermost bullet indentation only. A step's `run:`
    body is shell, and a shell line may open with `-`: a wrapped invocation's
    `--flag` continuation is a bullet to this pattern and to nothing else. Split
    there and the step's remaining keys — `continue-on-error:`, `if:` — land in a
    block of their own, which `scan` then reads as a step that runs no gate. The
    gate's own step is left looking unguarded, and the guard is attributed to
    nothing. A false certificate assembled out of two correct-looking halves.
    """
    lines = text.splitlines()
    blocks = []
    for i, line in enumerate(lines):
        if not re.match(r"^\s*steps:\s*$", line):
            continue
        body = nested(lines, i)
        bullets = [n for n, ln in enumerate(body) if re.match(r"^\s*-", ln)]
        depth = min((len(body[n]) - len(body[n].lstrip()) for n in bullets), default=0)
        starts = [n for n in bullets if len(body[n]) - len(body[n].lstrip()) == depth]
        for n, start in enumerate(starts):
            end = starts[n + 1] if n + 1 < len(starts) else len(body)
            blocks.append("\n".join(body[start:end]))
    return blocks


def commands(block):
    """What one step actually executes — its `run:` values, and nothing else.

    Indentation is measured from the `run:` key rather than the line start, so a
    block scalar stops at the step's next key instead of swallowing it.

    Interior blanks are kept, for the reason `nested` gives: `unloadable`
    subtracts this text from the file verbatim to exempt shell from the YAML
    scan, and a blank line between two commands of one `run: |` body is the
    ordinary way to write it.
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
        blanks = []
        for after in lines[i + 1:]:
            if not after.strip():
                blanks.append(after)
                continue
            if len(after) - len(after.lstrip()) <= outer:
                break
            body.extend(blanks)
            blanks.clear()
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
            if base := re.match(r"^\s*(branches(?:-ignore)?):\s*(.*)$", ln):
                key, raw = base.group(1), base.group(2) or " ".join(nested(inner, n))
                listed = {p for p in re.split(r"[\s,\[\]'\"]+", raw.replace("- ", " ")) if p}
                admits = any(fnmatchcase(INTEGRATION, p) for p in listed)
                if admits is (key == "branches-ignore"):
                    return (f"fires on pull_request with {key}: "
                            f"{', '.join(sorted(listed)) or 'nothing'} — "
                            f"no pull request into `{INTEGRATION}` triggers it")
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
            for line in CONTINUED.sub(" ", commands(block)).splitlines():
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


def check(checkers, named, gating, present, why, discovers, sources=None):
    """(errors, warnings) for one tree. `present` is every file in `scripts/`.

    `sources` maps a test module's name to its text; omit it to skip the
    collectability check and assert wiring only.
    """
    why = why or {}
    errors = []
    if not discovers and any(name.startswith("test_") for name in present):
        errors.append(
            "no pull-request workflow runs `unittest discover -s scripts` — the gates "
            "are wired, and nothing runs the tests that say they are right"
        )
    if discovers:
        for name, text in sorted((sources or {}).items()):
            why_not = yieldless(text)
            if why_not:
                errors.append(f"scripts/{name}: {why_not}")
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
    sources = {
        p.name: p.read_text(encoding="utf-8")
        for p in sorted((root / "scripts").glob("test_*.py"))
    }
    errors, warnings = check(checkers, named, gating, present, why, discovers, sources)

    for warning in warnings:
        print(f"warning: {warning}")
    for error in errors:
        print(f"error: {error}")
    print(f"{len(checkers)} checker(s), {len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
