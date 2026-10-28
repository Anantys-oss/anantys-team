#!/usr/bin/env python3
"""Break `main` on purpose, then ask which of the queue's gates noticed.

Fourteen `check_*.py` gates sit on the queue's branches; none is merged, so `main`
is ungated. `gate_matrix.py` already answers "does head H pass gate G" — head health.
That leaves the dual question unasked, and it is the one a reviewer deciding what
to merge actually has: *what is each gate worth?* A gate earns its place by
rejecting a tree a human would call broken. A gate that cannot be made to fail by
any realistic regression is inert however green its CI badge is, and two gates
that reject exactly the same trees are one gate with two maintenance costs.

So the axis here is gate × mutation, not gate × head:

    python3 scripts/gate_power.py                 # full matrix
    python3 scripts/gate_power.py version-drift   # just these mutations

Each run assembles one tree per mutation — `origin/main` in a throwaway worktree,
every gate in the queue overlaid on top, the mutation committed — and records each
gate's exit code. A gate green on pristine `main` and red on mutation M *catches*
M. Three things fall out of the matrix that no single branch can see: gates with
identical catch-sets (redundant), gates with an empty catch-set (inert against
this product), and mutations no gate catches at all (the queue's blind spots).

The mutations are deliberately dull — a version bumped in one of its two homes, a
read-only agent handed `Write`, a template a role references deleted. Exotic
breakage proves nothing; these are the regressions this repo has actually shipped.

Every mutation is a literal quoted out of the product, which makes the anchors the
instrument's own expiry date. `MUTATIONS` and the toll together pinned this file to
one value of one scalar — `"version": "0.6.0"` — and the queue holds two separate
events that falsify it. A release bumps both manifests, which `check_version_bump`
warns is overdue and nothing else in the repo will do for it. And one head deletes
`version` from `marketplace.json` altogether, on the measured ground that the
loader never reads it: a bump applied there alone leaves `plugin update` answering
`already at the latest version`, while `plugin.json`'s value drives install,
`details`, `update` and the cache directory name. Either event used to end the run
on the first mutation, from inside the toll — so the sweep that prices fourteen
gates reported nothing, and the reason was a string in this file rather than anything
about a gate. Version anchors are now read from the tree, and a stale anchor of any
kind costs its own row and no other.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "origin/main"

PLUGIN = "plugins/anantys-team-agents/.claude-plugin/plugin.json"
MARKET = ".claude-plugin/marketplace.json"
QA = "plugins/anantys-team-agents/skills/anantys.qa/SKILL.md"
QA_PLAN = "plugins/anantys-team-agents/skills/anantys.qa/templates/qa-plan.md"
AUDITOR = "plugins/anantys-team-agents/agents/anantys.code-auditor.md"
REVIEW = "plugins/anantys-team-agents/skills/anantys.review/SKILL.md"

#: An op's `old` when it means "whatever version this manifest carries".
#:
#: A version written out as a literal is a claim that `main` still says `0.6.0`, and
#: it is the one claim in this file the repo is under standing instruction to
#: falsify: `check_version_bump` warns that the floor never moves until someone
#: tags a release, and the release that answers it bumps both manifests. A head in
#: this queue goes further and deletes `version` from `marketplace.json` outright,
#: on the measured ground that the loader never reads it — `plugin install`,
#: `details`, `update` and the cache path all take `plugin.json`'s. Either event
#: leaves `apply` with an anchor that matches nothing, which is why the value is
#: read from the tree at sweep time instead. `expand` is the only consumer, so the
#: sentinel is inert in both positions if an op reaches `apply` unresolved.
VERSION = "\0version"

#: Applied on top of every mutation, because a mutation has to look like a PR.
#:
#: Without it the matrix is unreadable: `check_version_bump` demands a bump whenever
#: content changes, so it reddens on 13 of 14 mutations and "catches" a deleted
#: template by complaining about a version. Every gate that rules on the *diff*
#: rather than on the tree would do the same. Bumping both manifests pays that toll
#: once, so a red cell means the gate objected to the mutation and not to the
#: housekeeping around it.
BUMP = [
    (PLUGIN, VERSION, VERSION),
    (MARKET, VERSION, VERSION),
]
#: Mutations that write the version themselves; the toll above would collide.
NO_BUMP = ("version-drift",)

#: `(path, old, new)` — `old=None` appends `new`, `new=None` deletes the file.
#: One mutation may need several ops; a one-op mutation is the common case.
MUTATIONS: dict[str, list[tuple[str, str | None, str | None]]] = {
    # The version lives in two files. Bumping one is this repo's most-shipped regression.
    "version-drift": [(PLUGIN, VERSION, VERSION)],
    # Nothing resolves the marketplace entry back to the plugin it names.
    "name-mismatch": [(PLUGIN, '"name": "anantys-team-agents"', '"name": "anantys-agents"')],
    "broken-source": [(MARKET, '"source": "./plugins/anantys-team-agents"', '"source": "./plugins/gone"')],
    "invalid-json": [(MARKET, '"category": "development",', '"category": "development",,')],
    # A skill the loader cannot index.
    "skill-no-name": [(QA, "name: anantys.qa\n", "")],
    "skill-no-description": [(QA, "description: Run a browser-driven QA campaign", "summary: Run a browser-driven QA campaign")],
    "unterminated-frontmatter": [(REVIEW, "---\nname: anantys.review", "name: anantys.review")],
    # A role renamed without touching the two descriptions that advertise its slash command.
    "slash-name-drift": [(QA, "name: anantys.qa\n", "name: anantys.quality\n")],
    # Read-only by contract, by its own prose, and now granted a writer.
    "auditor-gains-write": [(AUDITOR, '"Bash", "Read", "Glob", "Grep"', '"Bash", "Read", "Write", "Glob", "Grep"')],
    # A step reaches for a tool the frontmatter never granted.
    "ungranted-tool": [(QA, None, "\n## Step 99 — publish\n\nUse `WebFetch` to post the report upstream.\n")],
    # A role whose body cites a template that is no longer in the tree.
    "dangling-template": [(QA_PLAN, None, None)],
    # Both descriptions still say five skills and name the five.
    "skill-count-drift": [
        (PLUGIN, "5 skills (/anantys.design", "6 skills (/anantys.design"),
        (MARKET, "5 skills (/anantys.design", "6 skills (/anantys.design"),
    ],
    # An agent whose frontmatter name is not the name its filename exposes.
    "agent-name-mismatch": [(AUDITOR, "name: anantys.code-auditor", "name: code-auditor")],
    # A role that grants a tool nobody audited, in a repo with a grants baseline.
    "silent-grant-widening": [(QA, "allowed-tools: Bash, Read", "allowed-tools: Bash, BashOutput, Read")],
}


def git(*args: str, cwd: Path | None = None) -> str:
    done = subprocess.run(
        ("git", *args), cwd=cwd or ROOT, capture_output=True, text=True, check=False
    )
    return done.stdout.strip() if done.returncode == 0 else ""


def heads() -> list[str]:
    refs = git("for-each-ref", "--format=%(refname:short)", "refs/remotes/origin/**")
    return [r for r in refs.splitlines() if r and r != "origin"]


def overlay() -> dict[str, bytes]:
    """Every gate in the queue, newest commit wins.

    A gate is read from the head that committed it last rather than from the head
    that happens to sort first: several gates were amended on a descendant branch,
    and running the ancestor's copy would price a version nobody proposes to merge.
    Support files come along — a grants gate without its baseline is a crash, not a
    verdict, and `.github` matters because a gate may read the workflow running it.
    """
    newest: dict[str, tuple[int, str]] = {}
    for ref in heads():
        when = int(git("show", "-s", "--format=%ct", ref) or 0)
        for path in git("ls-tree", "-r", "--name-only", ref, "--", "scripts", ".github").splitlines():
            keep = path.startswith("scripts/check_") or path.endswith(("-baseline.txt", ".yml"))
            if keep and when >= newest.get(path, (0, ""))[0]:
                newest[path] = (when, ref)
    files = {}
    for path, (_, ref) in newest.items():
        blob = subprocess.run(
            ("git", "show", f"{ref}:{path}"), cwd=ROOT, capture_output=True, check=False
        )
        if blob.returncode == 0:
            files[path] = blob.stdout
    # The checkout wins over every remote head, committed or not. Otherwise the
    # tool prices the queue as it was pushed and stays silent about the gate the
    # reader is editing — the one case where the answer could still change
    # something. A `git show` of a ref cannot see a worktree.
    for path in files:
        local = ROOT / path
        if local.is_file():
            files[path] = local.read_bytes()
    return files


class AnchorGone(Exception):
    """A mutation's anchor is no longer in the product text it targets.

    Raised instead of exiting, because the blast radius is the difference between
    a usable report and none. Every anchor in `MUTATIONS` is a literal quoted out
    of a role file or a manifest, and the queue rewrites exactly those lines — so
    an anchor going stale is the expected end of a mutation's life, not an
    accident. Killing the process on the first one costs the other thirteen rows,
    and the reader is then told nothing about any gate by a tool whose whole job
    is pricing them.
    """


def successor(version: str) -> str:
    """The next patch, so the toll is a bump and not a no-op.

    The value only has to differ from what the tree carries — no gate reads which
    component moved — so a version that does not end in a number still gets a
    distinct string rather than an exception.
    """
    head, _, patch = version.rpartition(".")
    return f"{head}.{int(patch) + 1}" if patch.isdigit() else f"{version}+1"


def versions() -> dict[str, str]:
    """The version each manifest carries at `BASE`, keyed by path.

    A manifest with no `version` is absent from the mapping rather than an error:
    it has nothing to bump, and a sweep that dies on that is reporting a string in
    this file instead of anything about a gate.
    """
    found = {}
    for rel, pick in ((PLUGIN, lambda d: d["version"]),
                      # The catalog holds one entry per plugin and this repo ships one.
                      (MARKET, lambda d: d["plugins"][0]["version"])):
        try:
            found[rel] = pick(json.loads(git("show", f"{BASE}:{rel}")))
        except (ValueError, KeyError, IndexError, TypeError):
            continue
    return found


def expand(ops: list, found: dict[str, str]) -> list:
    """Resolve `VERSION` sentinels against the versions `BASE` actually carries."""
    out = []
    for rel, old, new in ops:
        if old is not VERSION:
            out.append((rel, old, new))
        elif rel in found:
            out.append((rel, f'"version": "{found[rel]}"',
                        f'"version": "{successor(found[rel])}"'))
    return out


def apply(tree: Path, ops: list[tuple[str, str | None, str | None]]) -> None:
    for rel, old, new in ops:
        target = tree / rel
        if new is None:
            if not target.is_file():
                raise AnchorGone(f"{rel}: already absent")
            target.unlink()
        elif old is None:
            target.write_text(target.read_text() + new)
        else:
            body = target.read_text()
            if old not in body:
                raise AnchorGone(f"{rel}: {old!r}")
            target.write_text(body.replace(old, new, 1))


def build(tree: Path, files: dict[str, bytes], ops: list) -> None:
    git("worktree", "add", "--detach", "-q", str(tree), BASE)
    for path, blob in files.items():
        dest = tree / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(blob)
    apply(tree, ops)
    git("add", "-A", cwd=tree)
    git("-c", "user.email=gate@power", "-c", "user.name=gate_power", "commit", "-qm", "mutation", cwd=tree)


def finding(out: str) -> str:
    """The first line of a gate's complaint.

    An exit code alone says a cell is red and nothing about *why*, and the why is
    load-bearing here: a gate can redden on a mutation while objecting to something
    else entirely. Printing the sentence is what lets a reader tell a catch from a
    coincidence, so a gate whose complaint names a version while the mutation
    deleted a template can be struck off by hand.
    """
    for line in out.splitlines():
        text = line.strip()
        if text.startswith(("error:", "ERROR", "FAIL")) or ": error" in text:
            return text[:140]
    tail = [l.strip() for l in out.splitlines() if l.strip()]
    return tail[-1][:140] if tail else "(silent)"


def run_gates(tree: Path) -> dict[str, tuple[int, str]]:
    """Exit code and complaint per gate. A gate that cannot start counts as red, loudly.

    Timeouts are a verdict too: `check_evals` shells out to the Claude CLI, which is
    absent on a CI box and interactive on a laptop. Hanging the sweep on it would
    report nothing about the other ten.
    """
    cells = {}
    for gate in sorted((tree / "scripts").glob("check_*.py")):
        try:
            done = subprocess.run(
                (sys.executable, str(gate)), cwd=tree, capture_output=True, text=True, timeout=120
            )
            cells[gate.stem] = (done.returncode, finding(done.stdout + done.stderr))
        except subprocess.TimeoutExpired:
            cells[gate.stem] = (124, "timed out after 120s")
    return cells


Cells = dict[str, tuple[int, str]]


def sweep(names: list[str]) -> tuple[Cells, dict[str, Cells], dict[str, str]]:
    """Each mutation's cells, plus the ones whose anchor the product no longer has.

    A stale anchor is one unpriceable row, so it is reported as such and the sweep
    continues. The pristine tree is the exception: it applies no ops, so an
    `AnchorGone` there could only come from the toll, and without the toll every
    later row is measured against a baseline the rest of the matrix does not share.
    """
    files = overlay()
    found = versions()
    runs: dict[str, Cells] = {}
    unavailable: dict[str, str] = {}
    for label, ops in [("(pristine)", [])] + [(n, MUTATIONS[n]) for n in names]:
        toll = [] if label in NO_BUMP or not ops else BUMP
        tree = Path(tempfile.mkdtemp(prefix="koan-gate-power-")) / "t"
        try:
            build(tree, files, expand(ops + toll, found))
            runs[label] = run_gates(tree)
        except AnchorGone as gone:
            if label == "(pristine)":
                raise SystemExit(f"error: the version toll no longer applies — {gone}")
            unavailable[label] = str(gone)
        finally:
            git("worktree", "remove", "--force", str(tree))
            shutil.rmtree(tree.parent, ignore_errors=True)
    return runs.pop("(pristine)"), runs, unavailable


def verdicts(baseline: Cells, runs: dict[str, Cells]) -> dict:
    """What the matrix says, separated from how it prints.

    `subsumed` is the relation worth having and `dupes` is the degenerate case of
    it. Two gates with *identical* catch-sets is a coincidence of this mutation
    list; one gate's catches being a subset of another's is the shape that tells a
    reviewer what to merge first. Both are evidence, not proof: a subset over
    fourteen mutations says the narrower gate adds nothing *here*, never that it
    adds nothing. A gate red on `main` is excluded from every verdict rather than
    counted as catching nothing — it was not asked.
    """
    gates = sorted(baseline)
    usable = [g for g in gates if baseline[g][0] == 0]
    caught = {
        g: sorted(m for m, cs in runs.items() if cs.get(g, (0, ""))[0] != 0) for g in usable
    }
    sets = {g: set(hits) for g, hits in caught.items()}
    return {
        "gates": gates,
        "usable": usable,
        "caught": caught,
        "blind": sorted(m for m in runs if not any(runs[m].get(g, (0, ""))[0] for g in usable)),
        "inert": sorted(g for g, hits in caught.items() if not hits),
        "dupes": sorted(
            tuple(sorted(gs))
            for gs in {
                frozenset(a for a in sets if sets[a] == sets[g]) for g in sets if sets[g]
            }
            if len(gs) > 1
        ),
        "subsumed": sorted(
            (narrow, wide)
            for narrow in sets
            for wide in sets
            if narrow != wide and sets[narrow] and sets[narrow] < sets[wide]
        ),
    }


def report(baseline: Cells, runs: dict[str, Cells], unavailable: dict[str, str]) -> None:
    v = verdicts(baseline, runs)
    gates, usable, caught = v["gates"], v["usable"], v["caught"]

    print(f"\n{len(gates)} gates overlaid on {BASE}, {len(runs)} mutations\n")

    if unavailable:
        print(f"Unpriceable — the anchor is gone from the product ({len(unavailable)}):")
        for m, why in sorted(unavailable.items()):
            print(f"  - {m}: {why}")
        print("  Re-anchor each on text the tree still has; until then no gate was asked.\n")
    print(f"{'gate':<26} {'main':>5}  catches")
    for g in gates:
        if baseline[g][0]:
            print(f"{g:<26} {'RED':>5}  unassessable — {baseline[g][1]}")
        else:
            hits = caught[g]
            print(f"{g:<26} {'ok':>5}  {len(hits):>2}  {', '.join(hits) or '(nothing)'}")

    if v["blind"]:
        print(f"\nCaught by no green gate ({len(v['blind'])}/{len(runs)}):")
        for m in v["blind"]:
            print(f"  - {m}")
        if len(usable) < len(gates):
            print(f"  ({len(gates) - len(usable)} gate(s) red on main could not be asked)")

    if v["dupes"]:
        print("\nIdentical catch-sets (one rule, several gates):")
        for gs in v["dupes"]:
            print(f"  - {' = '.join(gs)}")

    if v["subsumed"]:
        print("\nSubsumed on this mutation list — merge the wider gate first:")
        for narrow, wide in v["subsumed"]:
            print(f"  - {narrow} ⊂ {wide}")

    if v["inert"]:
        print(f"\nNo mutation reaches ({len(v['inert'])}): {', '.join(v['inert'])}")

    print("\nWhy each catch fired — a complaint that does not name the mutation is a coincidence:")
    for g in sorted(caught):
        for m in caught[g]:
            print(f"  {g:<24} {m:<24} {runs[m][g][1]}")


def main(argv: list[str]) -> int:
    as_json = "--json" in argv
    names = [a for a in argv if a != "--json"] or sorted(MUTATIONS)
    unknown = [n for n in names if n not in MUTATIONS]
    if unknown:
        print(f"error: unknown mutation(s): {', '.join(unknown)}", file=sys.stderr)
        print(f"known: {', '.join(sorted(MUTATIONS))}", file=sys.stderr)
        return 2
    baseline, runs, unavailable = sweep(names)
    if as_json:
        print(json.dumps(
            {"baseline": baseline, "runs": runs, "unavailable": unavailable}, indent=2))
    else:
        report(baseline, runs, unavailable)
    # A stale anchor is a defect in this file, not a verdict on the queue, and it
    # is the one outcome a caller can act on — so it is the only nonzero exit.
    return 1 if unavailable else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
