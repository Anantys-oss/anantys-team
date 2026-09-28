#!/usr/bin/env python3
"""Order the open-PR queue so it can be landed with the fewest rebase rounds.

A review queue is not a list, it is a graph. Every PR here is cut from `main`,
so mergeability is pairwise: two PRs that touch disjoint regions can land in
either order, two that touch the same region force whichever lands second to
rebase. Reviewing in arrival order therefore pays a rebase for every collision
it happens to walk into, and the cost is invisible until the merge button.

This computes the graph instead of guessing it. Conflicts come from
`git merge-tree --write-tree`, which performs a real merge in memory — not a
filename-overlap heuristic, which over-reports (two PRs appending to different
sections of one file merge cleanly) and would hide nothing useful.

Output is a set of waves. A wave is a set of PRs that are mutually clean: land
them in any order, no rebase between them. Only crossing a wave boundary costs
a rebase, so N waves means N-1 rebase rounds for the whole queue.

A rebase is the cheap case, and not every boundary is one. When a PR in an
earlier wave *restructures* a file that a later one edits — a split into
`reference/*.md`, a rule hoisted into a shared contract — the later PR's hunks
do not merely move, they lose their anchors: the lines they patch are no longer
in that file. Git reports the conflict in the shared path anyway, and the file
intersection reported below names that same path, so both point at the one file
the change must not be applied to. The destination lives only on the
restructurer's side of the diff. Each conflicting pair is therefore classified,
and a relocated one is named as what it is — a re-authoring by hand that no
ordering of the queue avoids.

Mergeable is not green. A wave says the trees combine without a conflict; it
says nothing about whether the combined tree still passes the repo's own checks.
Every checker in this queue was written against `main` and validated against the
one branch that carries it, so the assembled result — the thing `main` actually
becomes — is the one state no checker has ever run in. `--verify` builds that
state (fold the branches with `merge-tree`, check it out as a detached worktree,
never touch a branch or the working tree) and runs every gate found inside it — the
`scripts/check_*.py`, and the unit-test suite CI discovers over the whole
`scripts/` tree. Both are gates because both turn `main` red; the suite is the
one whose contents the union changes, since discovery picks up every branch's
tests at once and none of them has ever run beside another's.

It does so **per landing round**, not once for the whole queue. Waves land one at
a time, so `main` passes through every prefix of them, and a checker in an early
wave whose error is only cleared by a later one is red on `main` for the whole
gap. Verifying only the full union hides exactly that: the union contains the
fix, the round the operator actually lands does not.

In practice that means **one round per run: the next one.** A PR sits in a later
wave precisely because it conflicts with an earlier one, so every round past the
first contains a conflicting pair and cannot be assembled here — its members'
rebased content does not exist yet, and the rebase is a human's edit, not a
derivation. This is structural, not a property of today's queue. The loop is:
verify the next round, land it, rebase what conflicted, re-run.

When a round is red, the report then names **what clears it**. A wave is grouped
by merge conflicts, which have nothing to do with greenness, so the PR carrying a
fix routinely lands rounds after the checker it satisfies — and the operator has
no way to tell that from a tree that is simply broken. Each remaining PR is
folded into the round (minus whichever members it conflicts with, since those are
exactly the resolutions a human would make) and the failing checkers re-run.

Green is not reviewed, and `--contracts` reports the gap between them. Everything
above is a claim about the tree: it combines, it passes. What the operator has to
decide is a claim about the *content* — whether what the round makes `main` say is
coherent — and the report's unit for that decision is wrong. It is the PR; the
unit of risk is the file. A PR whose every path is new to `main` cannot regress
behaviour that exists, so it is read once, in any order, against nothing. A path
that several of the round's PRs edit is the opposite case: every one of those
hunks was argued for against the `main` it was cut from, and none of those
arguments is about the fold the round actually lands. So `--contracts` separates
the two and lists the shared paths most-converged first, with the PRs that reach
each one. It renders no judgement — the fold is prose, and a script has no
opinion about prose. It puts the whole fold on one screen, which is the only form
in which a human has one.

Usage: python3 scripts/pr_landing_order.py [--limit N] [--verify] [--contracts]
Exit 0 always — this is an operator report, not a gate.
"""

import argparse
import contextlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def run(*args):
    """Capture stdout; raise on failure."""
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout


def open_prs(limit):
    """[(number, headRefName, title, {files})] for the open queue, oldest first."""
    raw = run("gh", "pr", "list", "--state", "open", "--limit", str(limit),
              "--json", "number,headRefName,title,files")
    prs = [(p["number"], p["headRefName"], p["title"],
            {f["path"] for f in p["files"]}) for p in json.loads(raw)]
    return sorted(prs)


def stacked(prs):
    """{contained: container} when one PR's head is an ancestor of another's.

    A stacked PR carries no diff of its own once its container lands, and it
    breaks a fold: the pair merges cleanly (their merge base *is* the contained
    head) but folding the contained tree first and then merging the container
    against `main` re-reads the shared files as two independent edits. Landing
    the container closes both, so the contained PR leaves the graph.
    """
    out = {}
    for a, ref_a, _, _ in prs:
        for b, ref_b, _, _ in prs:
            if a != b and subprocess.run(
                    ["git", "merge-base", "--is-ancestor",
                     f"origin/{ref_a}", f"origin/{ref_b}"],
                    capture_output=True).returncode == 0:
                out[a] = b
    return out


def rounds(order, refs):
    """Cumulative landing rounds: what `main` holds after each wave lands."""
    out, seen = [], []
    for wave in order:
        seen = seen + [(n, refs[n]) for n in wave]
        out.append(list(seen))
    return out


def conflicts(prs):
    """{frozenset({a, b}): sorted(shared files)} for pairs that do not merge."""
    found = {}
    for i, (a, ref_a, _, files_a) in enumerate(prs):
        for b, ref_b, _, files_b in prs[i + 1:]:
            merged = subprocess.run(
                ["git", "merge-tree", "--write-tree",
                 f"origin/{ref_a}", f"origin/{ref_b}"],
                capture_output=True, text=True)
            if merged.returncode != 0:
                found[frozenset((a, b))] = sorted(files_a & files_b)
    return found


def anchors(base, ref, path, minimum=30):
    """The text in `path` that `ref`'s edits are attached to.

    Not the whole context window: a hunk carries three lines either side, and
    at that width an edit near an untouched paragraph looks attached to it. The
    attachment points are the lines a change actually rewrites and the context
    immediately abutting each run of them — those are what say *where* the edit
    belongs. Short lines (a heading, a list marker, a lone fence) match
    anywhere, so they name every file and are dropped.
    """
    out, previous, inside = [], None, False
    for line in run("git", "diff", f"{base}...{ref}", "--", path).splitlines():
        if line.startswith("@@"):
            previous, inside = None, False
        elif line.startswith(("+++", "---")):
            continue
        elif line[:1] in ("+", "-"):
            if not inside and previous:
                out.append(previous)
            inside = True
            if line.startswith("-"):
                out.append(line[1:].strip())
        elif line[:1] == " ":
            if inside:
                out.append(line[1:].strip())
                inside = False
            previous = line[1:].strip()
    return [anchor for anchor in out if len(anchor) >= minimum]


def moved(ref, path, needles, probes=5):
    """Files in `ref` that hold `needles` after `ref` removed them from `path`.

    Only the absent needles are searched, so a PR that restructures nothing
    costs no `git grep` at all.
    """
    try:
        body = run("git", "show", f"{ref}:{path}")
    except subprocess.CalledProcessError:
        return []
    destinations = set()
    for needle in sorted(set(needles), key=len, reverse=True):
        if probes <= 0:
            break
        if needle in body:
            continue
        probes -= 1
        # -e, because a prose line routinely starts with "- " and would
        # otherwise be read as an option and silently match nothing.
        found = subprocess.run(["git", "grep", "-lF", "-e", needle, ref],
                               capture_output=True, text=True)
        destinations.update(line.split(":", 1)[1]
                            for line in found.stdout.splitlines() if ":" in line)
    return sorted(d for d in destinations if d != path)


def relocations(base, prs, edges):
    """{(loser, winner): {path: [destinations]}} — conflicts a rebase cannot fix.

    A shared filename is where the conflict *is*. It is not always where the
    resolution *goes*. When one PR of a pair restructures a file — splitting
    prose into new ones, as a progressive-disclosure refactor does — the other's
    hunks lose their anchors: the lines they patch are no longer in the shared
    file at all. Git still reports the conflict there, and the intersection this
    report prints names that same file, so both send the resolver to the one
    place the change must not be applied. The destination only ever appears on
    the restructurer's side of the diff, never in the intersection.

    The distinction is the operator's cost, not a detail: a same-file conflict is
    a rebase, and a relocated one is a re-authoring by hand that no ordering of
    the queue avoids.
    """
    refs = {n: f"origin/{ref}" for n, ref, _, _ in prs}
    out = {}
    for pair, shared in edges.items():
        a, b = sorted(pair)
        for loser, winner in ((a, b), (b, a)):
            for path in shared:
                destinations = moved(refs[winner], path,
                                     anchors(base, refs[loser], path))
                if destinations:
                    out.setdefault((loser, winner), {})[path] = destinations
    return out


def waves(numbers, edges):
    """Group PR numbers into internally conflict-free waves.

    Highest-degree first: a PR that collides with many others is the one whose
    delay costs the most rebases, so it goes in the earliest wave it fits.
    """
    degree = {n: sum(1 for e in edges if n in e) for n in numbers}
    remaining = sorted(numbers, key=lambda n: (-degree[n], n))
    out = []
    while remaining:
        wave = []
        for pr in remaining:
            if all(frozenset((pr, w)) not in edges for w in wave):
                wave.append(pr)
        out.append(sorted(wave))
        remaining = [p for p in remaining if p not in wave]
    return out


def union_tree(base, refs, start=None):
    """Fold `refs` onto `base` in memory. Returns (commit, joined, refused).

    Refused refs are the ones that conflict with the accumulation so far — they
    are reported, not forced, because a resolved conflict is a human's call and
    guessing one would verify a tree nobody is going to land.

    `start` folds onto an accumulation that already exists while still measuring
    every ref against `base` — the merge base a branch cut from `main` actually
    has. Used to add one member to a tree built from other members.
    """
    acc, joined, refused = start or base, [], []
    for number, ref in refs:
        merged = subprocess.run(
            ["git", "merge-tree", "--write-tree", "--merge-base", base,
             acc, f"origin/{ref}"], capture_output=True, text=True)
        if merged.returncode != 0:
            refused.append(number)
            continue
        tree = merged.stdout.splitlines()[0]
        acc = run("git", "commit-tree", tree, "-p", acc,
                  "-m", f"union #{number}").strip()
        joined.append(number)
    return acc, joined, refused


def checker_scripts(scripts_dir, only=None):
    """Every checker in a tree: `check_*.py`, never their `test_*` siblings.

    A `test_check_a.py` is not excluded because it does not matter — it is a CI
    gate too — but because invoking it as a script is not how CI runs it. It is
    discovered, alongside every other branch's tests, by the suite `run_checkers`
    runs once over the whole tree.

    `only` narrows the set by name, for re-testing a tree against a checker
    already known to fail — the other verdicts are not the question being asked.
    """
    return sorted(p for p in Path(scripts_dir).glob("check_*.py")
                  if not p.name.startswith("test_")
                  and (only is None or p.name in only))


SUITE = "unittest discover -s scripts"


@contextlib.contextmanager
def checkout(commit):
    """The union as a real repository, not an extracted tree.

    `git archive | tar -x` is cheaper and was the obvious choice, but it yields
    a directory with no `.git` — and a checker that asks git a question cannot
    ask it there. `check_version_bump.py` is exactly that checker: with no ref
    to resolve, `resolve_base` returns None, it prints "no base ref to compare
    against — skipping" and exits 0. So the one gate whose subject is the
    freshness of the version the union ships was reported `OK` on every round
    without once having run. A skip that exits 0 is indistinguishable from a
    pass, and this report exists to be trusted with seventeen merges.

    A detached worktree costs a checkout and gives the checkers the refs they
    need — `origin/main` among them, which is the base the union is measured
    against and the comparison the operator is actually asking for. It touches
    no branch and not the working tree; it is registered under `.git/worktrees`
    and removed on the way out.
    """
    with tempfile.TemporaryDirectory(prefix="pr-union-") as parent:
        tree = Path(parent) / "tree"
        run("git", "worktree", "add", "--detach", str(tree), commit)
        try:
            yield tree
        finally:
            subprocess.run(["git", "worktree", "remove", "--force", str(tree)],
                           capture_output=True)


def run_checkers(commit, only=None):
    """{gate name: (exit code, error lines)} for every gate in `commit`.

    A gate is anything whose red turns `main` red, which is the tree's
    `check_*.py` *and* its unit-test suite: CI runs `unittest discover -s
    scripts`, so a failing test blocks a merge exactly like a failing checker.
    Reporting a round green on the checkers alone answers a narrower question
    than the operator asked — and narrower in the direction that matters, since
    discovery is tree-wide. Each branch's tests have only ever run beside their
    own; the union is the first process to import them all together, and a
    module-level fixture, a `sys.path` entry or a chdir that two of them share
    is visible nowhere else.

    `only` restricts the run to gates of that name — used when re-testing a tree
    against a known failure, where the other verdicts are not the question being
    asked. `SUITE` is a name like any other there.
    """
    out = {}
    with checkout(commit) as tmp:
        for script in checker_scripts(Path(tmp) / "scripts", only):
            done = subprocess.run([sys.executable, str(script), tmp],
                                  capture_output=True, text=True, cwd=tmp)
            out[script.name] = (done.returncode, [
                ln for ln in (done.stdout + done.stderr).strip().splitlines()
                if ln.startswith(("ERROR", "error"))])
        if (only is None or SUITE in only) and (Path(tmp) / "scripts").is_dir():
            done = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", "scripts"],
                capture_output=True, text=True, cwd=tmp)
            out[SUITE] = (done.returncode, [
                ln for ln in done.stderr.strip().splitlines()
                if ln.startswith(("FAIL:", "ERROR:"))])
    return out


def verify(base, refs):
    """Checkers inside the union of `refs`. Returns (lines, refused, failing).

    A round that refuses anything was not assembled, so its checker results
    belong to a smaller tree than the caller asked for — the caller must say so
    rather than present them as the round's verdict.
    """
    commit, joined, refused = union_tree(base, refs)
    lines = [f"Union of {len(joined)} PRs: "
             + (", ".join(f"#{n}" for n in joined) or "(none)")]
    if refused:
        return ["not assembled — "
                + ", ".join(f"#{n}" for n in refused)
                + " conflict with an earlier round, which is why they are in "
                  "this one; their rebased content does not exist yet"], refused, []

    results = run_checkers(commit)
    if not results:
        lines.append("  no gates in the union — nothing to verify")
    for name, (code, errors) in sorted(results.items()):
        lines.append(f"  {'OK  ' if code == 0 else 'FAIL'} {name}")
        lines += [f"       {ln}" for ln in errors]
    return lines, [], sorted(n for n, (code, _) in results.items() if code)


def unverifiable(round_number):
    """Why the run stops here, and what the operator does to move it forward.

    Rounds past the first refuse by construction, not by accident: `waves` defers
    a PR exactly when it conflicts with one already placed, so every later round
    holds a conflicting pair. Saying "a human must resolve them" invites the
    operator to resolve something now; the resolution that matters is the rebase
    that only exists *after* the round below it has landed.
    """
    if round_number == 1:
        return ("  nothing is verifiable: this round's members are pairwise "
                "clean but do not combine, so no tree exists to check")
    return (f"  rounds {round_number} and later are not verifiable today — "
            f"their members conflict with an earlier round, which is why they "
            f"are in a later one, and their rebased content does not exist "
            f"yet. Land round {round_number - 1}, rebase them onto the new "
            f"`main`, re-run: round {round_number} becomes round 1.")


def introduced(base, commit):
    """Gate names in `commit` that `base` does not have.

    A gate already on `main` has judged every open branch — CI ran it on each
    push. One arriving in this round has judged nothing but the branch that
    wrote it, and `--verify` does not close that gap: it asks each gate once,
    about the union. For a gate whose subject is a *tree* that is the right
    question. For one whose subject is a *diff* it is a question nobody will
    ever be asked — `check_version_bump.py` reads the union as a single change,
    so one member's version bump answers for the round's entire content.
    """
    def gates(ref):
        listed = run("git", "ls-tree", "-r", "--name-only", ref, "scripts/")
        return {name for name in (Path(p).name for p in listed.splitlines())
                if name.startswith("check_") and name.endswith(".py")}

    return sorted(gates(commit) - gates(base))


def per_member(base, refs, gates):
    """Each member of the round judged by the round's new gates, one at a time.

    The subject is not the member's own head: a gate is only present once its
    own PR lands, and these gates read the tree they sit in. The honest tree is
    the round's tooling plus this one member — what `refs/pull/N/merge` becomes
    the moment the tooling is on `main`, and the verdict CI will actually print.

    Members that carry tooling are folded into that base and reported as the one
    group they are; judging them individually would need a base that already
    holds the gate a member is bringing. The rest are judged against it singly.

    A wave is advertised as landing "in any order, no rebase between them".
    That holds for conflicts, which is all `waves` measured. It does not survive
    a gate whose remedy is one shared location: the second member to land finds
    the first has already spent it.
    """
    carriers, judged = [], []
    for number, ref in refs:
        changed = run("git", "diff", "--name-only", base,
                      f"origin/{ref}").splitlines()
        bucket = carriers if any(
            f.startswith(("scripts/", ".github/workflows/"))
            for f in changed) else judged
        bucket.append((number, ref))

    landing, folded, refused = union_tree(base, carriers)
    if refused:
        return ["  the round's tooling does not assemble — "
                + ", ".join(f"#{n}" for n in refused)
                + " conflict with it; no member can be judged as CI will"]

    lines = [f"  gates this round introduces: {', '.join(gates)}"]
    subjects = [(", ".join(f"#{n}" for n in folded) + " (the tooling itself)",
                 landing)] if folded else []
    for number, ref in judged:
        commit, _, denied = union_tree(base, [(number, ref)], start=landing)
        subjects.append((f"#{number}", None if denied else commit))

    for label, commit in subjects:
        if commit is None:
            lines.append(f"  {label:<26}  conflicts with the round's tooling "
                         f"— not judgeable")
            continue
        results = run_checkers(commit, only=gates)
        red = sorted(name for name, (code, _) in results.items() if code)
        lines.append(f"  {label:<26}  "
                     + ("RED  " + ", ".join(red) if red else "green"))
        for name in red:
            lines += [f"      {line}" for line in results[name][1]]
    return lines


def convergence(tracked, members):
    """Split a round by what it risks: (additive PRs, {path: [PRs that edit it]}).

    `tracked` is what `main` already ships. A member whose every path is absent
    from it adds only new files, so nothing on `main` changes shape and no
    ordering among such members exists to get wrong. Everything else edits a
    contract that is already live, and a path reached by more than one member is
    where the round says something no PR does.
    """
    additive, converged = [], {}
    for number, paths in members:
        existing = sorted(paths & tracked)
        if not existing:
            additive.append(number)
        for path in existing:
            converged.setdefault(path, []).append(number)
    return additive, converged


def folds(base, landing, files):
    """What the next round changes, ordered by file rather than by PR.

    The union is built the same way `verify` builds it and for the same reason:
    the fold is the artifact under review, and it exists in no branch. The commit
    is left in the object store so the per-path diff it names can be run
    afterwards — printing 5,000 lines of diff here would reproduce the problem
    this is meant to solve.
    """
    commit, joined, refused = union_tree(base, landing)
    if refused:
        return [unverifiable(1)]
    tracked = set(run("git", "ls-tree", "-r", "-z", "--name-only",
                      base).split("\0")) - {""}
    additive, converged = convergence(tracked, [(n, files[n]) for n in joined])
    lines = []
    if additive:
        lines += [f"  {len(additive)} of {len(joined)} add new paths only — "
                  + ", ".join(f"#{n}" for n in additive),
                  "    Nothing on `main` changes; read each once, in any order."]
    if not converged:
        return lines + ["  the round edits nothing `main` already ships"]
    lines.append(f"\n  {len(converged)} paths `main` already ships, "
                 f"most-converged first:")
    for path, numbers in sorted(converged.items(),
                                key=lambda kv: (-len(kv[1]), kv[0])):
        stat = run("git", "diff", "--numstat", base, commit, "--", path).split()
        delta = f"+{stat[0]} -{stat[1]}" if stat else "+0 -0"
        lines.append(f"    {len(numbers)}  {path}  {delta}  <- "
                     + ", ".join(f"#{n}" for n in numbers))
    lines.append(f"\n  Read a fold: git diff {base[:12]} {commit[:12]} "
                 f"-- <path>")
    return lines


def blockers(candidate, landed, edges):
    """Members of `landed` that `candidate` cannot merge alongside."""
    return sorted(n for n in landed if frozenset((candidate, n)) in edges)


def clearing(base, landed, remaining, failing, edges, refs):
    """Which still-unlanded PRs turn this round's failing checkers green.

    Waves are computed from merge conflicts alone, so a checker can land rounds
    ahead of the change that satisfies it — and `main` is red for the whole gap.
    Mergeability and greenness are different graphs; the partition only ever saw
    the first one. Reporting the failure without this is reporting half of it:
    the operator cannot tell a landing-order artifact, which a resolution fixes
    today, from a real defect in the assembled tree, which nothing in the queue
    fixes at all.

    A candidate that conflicts with the round is tested against the round minus
    those members — the tree a human would produce by resolving them — so the
    answer is not simply withheld for the PRs most likely to be the fix.
    """
    numbers = [n for n, _ in landed]
    lines, cleared = [], {name: [] for name in failing}
    for number in remaining:
        blocked = blockers(number, numbers, edges)
        trimmed = [pr for pr in landed if pr[0] not in blocked]
        commit, _, refused = union_tree(base, trimmed + [(number, refs[number])])
        if refused:
            continue
        for name, (code, _) in run_checkers(commit, only=failing).items():
            if code == 0:
                cleared[name].append((number, blocked))
    for name in failing:
        if not cleared[name]:
            lines.append(f"  nothing in the remaining queue clears {name} — a "
                         f"defect in the assembled tree, not a landing order")
            continue
        for number, blocked in cleared[name]:
            if blocked:
                lines.append(
                    f"  #{number} clears {name}, but conflicts with "
                    + ", ".join(f"#{n}" for n in blocked)
                    + " in this round — a green `main` means resolving them "
                      "together, not landing the round as it stands")
            else:
                lines.append(f"  #{number} clears {name} and merges clean into "
                             f"this round — move it here")
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--verify", action="store_true",
                    help="build the merged tree and run its checkers in it")
    ap.add_argument("--contracts", action="store_true",
                    help="what the next round changes, by file rather than PR")
    args = ap.parse_args()

    prs = open_prs(args.limit)
    if not prs:
        print("no open PRs")
        return 0
    titles = {n: t for n, _, t, _ in prs}
    refs = {n: ref for n, ref, _, _ in prs}
    files = {n: paths for n, _, _, paths in prs}
    contained = stacked(prs)
    if contained:
        prs = [pr for pr in prs if pr[0] not in contained]
    base = run("git", "rev-parse", "main").strip()
    edges = conflicts(prs)
    order = waves([n for n, _, _, _ in prs], edges)

    print(f"{len(prs)} open PRs, {len(edges)} conflicting pairs, "
          f"{len(order)} waves ({max(len(order) - 1, 0)} rebase rounds)\n")
    for small, big in sorted(contained.items()):
        print(f"#{small} is contained in #{big} — landing #{big} closes it; "
              f"not counted above\n")
    for i, wave in enumerate(order, 1):
        print(f"Wave {i} — land in any order, no rebase between them:")
        for n in wave:
            print(f"  #{n:<4} {titles[n]}")
        print()
    if edges:
        relocated = relocations(base, prs, edges)
        print("Conflicting pairs and the files they share:")
        for pair, shared in sorted(edges.items(), key=lambda kv: sorted(kv[0])):
            a, b = sorted(pair)
            print(f"  #{a} <-> #{b}: {', '.join(shared) or '(no shared path)'}")
            for loser, winner in ((a, b), (b, a)):
                for path, destinations in sorted(
                        relocated.get((loser, winner), {}).items()):
                    print(f"    #{winner} moves that text out of {path} — "
                          f"#{loser}'s hunks belong in "
                          f"{', '.join(destinations)}, not there. "
                          f"Re-authored by hand; a rebase cannot move a hunk "
                          f"across files.")

    if args.contracts and order:
        print("\nWhat the next round changes, read by file rather than by PR "
              "— mergeable is not coherent:")
        for line in folds(base, [(n, refs[n]) for n in order[0]], files):
            print(line)

    if args.verify:
        print("\nVerifying the next landing round — a wave is not a tree:")
        for i, cumulative in enumerate(rounds(order, refs), 1):
            print(f"\nAfter wave {i} lands:")
            lines, refused, failing = verify(base, cumulative)
            for line in lines:
                print(line)
            if failing:
                landed = {n for n, _ in cumulative}
                for line in clearing(base, cumulative,
                                     [n for n, _, _, _ in prs if n not in landed],
                                     failing, edges, refs):
                    print(line)
            if refused:
                print(unverifiable(i))
                break
            gates = introduced(base, union_tree(base, cumulative)[0])
            if gates:
                print("\n  A gate landing with the content it judges has judged "
                      "none of it — the union answers it once, CI asks per PR:")
                for line in per_member(base, cumulative, gates):
                    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
