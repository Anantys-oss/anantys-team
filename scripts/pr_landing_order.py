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
sections of one file merge cleanly) and would hide nothing useful. Always
against `main` as the merge base, never the pair's own: the merge being
predicted is the one onto `main`, and two heads that share a lineage past it
share a tree that already holds whatever they contest.

Output is a set of waves. A wave is a set of PRs that are mutually clean: land
them in any order, no rebase between them. Only crossing a wave boundary costs
a rebase, so N waves means N-1 rebase rounds for the whole queue.

A rebase is the cheap case, and not every boundary is one. When a PR in an
earlier wave *restructures* a file that a later one edits — a split into
`reference/*.md`, a rule hoisted into a shared contract — the later PR's hunks
do not merely move, they lose their anchors: the lines they patch are no longer
in that file. Git reports the conflict in the restructured path anyway, and the
report below names that same path, so both point at the one file the change must
not be applied to. The destination lives only on the
restructurer's side of the diff. Each conflicting pair is therefore classified,
and a relocated one is named as what it is — and then *ordered around*, because
it is the one edge whose two directions do not cost the same. Landing the
restructurer first makes every partner a hand re-authoring; landing it last
costs it one rebase of its own split, which is a mechanical redo of the thing it
already did on purpose. Degree-first would pick the expensive direction every
time — the restructurer collides with the most PRs, so it sorts to the front —
so a relocation is a precedence constraint on the waves, not merely a warning
printed under them.

And not every conflict is an ordering question at all. Two heads that change
*exactly* the same files and still conflict are successive drafts of one change:
neither leaves a path at `main`'s version for the other to rebase into, so the
second to land has no hunk left to move and a rebase would re-apply a draft over
its own successor. Git ancestry catches this only when the later work extended
the earlier one; re-author it instead and the two share no commit, so the pair
reads as an ordinary collision. What the operator owes there is a decision —
which authoring `main` keeps — and closing the other removes the edge, which no
ordering does.

Not every ordering constraint is a conflict, and the ones that are not are the
ones no tool here could see. A PR whose prose links a file another PR adds
shares no path with it: `merge-tree` is clean, the file intersection is empty,
and degree-first is free to land the consumer first. What lands is a role that
says *read this before acting* pointing at a path `main` does not have — green
by every gate, because CI asks each PR about a tree containing only that PR,
and the branch that answers the question is in someone else's. So a link whose
target another open head provides is a precedence edge too, of the same kind as
a relocation and from the opposite evidence: not a shared file, but an unshared
one.

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

Every claim above is about the queue, and the queue is an input this file reads
from two places that can disagree: the open list comes from the API, every tree
comes from `origin/<head>`. Nothing downstream can tell a stale or absent ref
from a real answer — `merge-tree` returns the same status for an unknown ref as
for a conflict — so the whole report is as good as that one collection step and
no better. `unreportable` is where it refuses.

That collection step reads the API's *open list*, so the queue it builds is not
the set of changes waiting on `main` — it is the subset of them someone opened a
PR for. A branch pushed to `origin` and never opened is in the same state as
every PR here and in none of the output: no wave, no round, no pair. It is also
the only position no ordering helps, because it does not land at all.
`unopened` names those branches and the commits that exist nowhere else.

One claim here is not about the queue at all, and it is the one every per-PR
verdict rests on: that CI asks each PR the questions this report declines to
re-ask. A `pull_request` run is evaluated at the merge of the head into its
base, so the gates a PR is judged by are the gates **`main`** has — not the ones
the queue holds. In a queue where every gate arrives on its own branch, `main`
can hold none, and then the deferral points at a run that never happened: no
red, no pending, nothing on the PR to notice. `unasked` measures it instead of
asserting it, because the remedy is the thing this report exists to recommend —
land the round, and the sentence becomes true.

Usage: python3 scripts/pr_landing_order.py [--limit N] [--verify] [--contracts]
Exit 0 on any queue it could read — this is an operator report, not a gate. Exit
1 only when it could not read one, which is not a verdict about the queue.
"""

import argparse
import contextlib
import json
import posixpath
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def run(*args):
    """Capture stdout; raise on failure."""
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout


def unreportable(prs, limit):
    """Why this queue cannot be reported on, or None.

    Two ways the input set is wrong while every line below still prints.

    A head this clone has never seen is not a merge conflict, but
    `git merge-tree --write-tree` exits 1 for an unknown ref exactly as it does
    for a conflicted merge — `merge-tree: <ref> - not something we can merge`,
    status 1, and `conflicts()` reads status only. So an unfetched PR is
    recorded as colliding with *every* other PR, which files it in a terminal
    wave of its own and keeps it out of every round `--verify` certifies. The
    conflict graph is invented and nothing says so. `open_prs` fetches first,
    which is what makes the API's queue and these trees one moment; what
    survives a fetch is a head not on `origin` — a fork, a deleted branch — and
    that is named rather than merged.

    And `gh` truncates at `--limit` in silence. A queue cut short still prints
    waves, `N-1 rebase rounds for the whole queue`, and a verified-green round,
    each a claim about a subset presented as the queue — and the PRs it drops
    are the oldest, which are the ones landing next. `len(prs) == limit` is the
    only signal the API offers, so an exactly-full page is read as truncated:
    the safe direction, since the remedy is one flag.
    """
    if len(prs) == limit:
        return (f"--limit {limit} returned exactly {limit} open PRs — the page is "
                f"full, so the queue is probably longer than this and every wave, "
                f"rebase count and verified round below would describe a subset. "
                f"Re-run with --limit {limit * 2}.")
    unknown = [f"#{n} ({ref})" for n, ref, *_ in prs
               if subprocess.run(["git", "rev-parse", "--verify", f"origin/{ref}"],
                                 capture_output=True).returncode]
    if unknown:
        return ("no `origin` ref for " + ", ".join(unknown) + " — a fork or a "
                "deleted head. `merge-tree` reads an unknown ref as a conflict, "
                "so these would be reported as colliding with the whole queue.")
    return None


def open_prs(limit):
    """[(number, headRefName, title, {files}, {checks})] — open queue, oldest first.

    Fetches first: the queue is read from the API and every tree below from
    `origin/<head>`, and nothing else makes those the same moment. A failed
    fetch raises rather than falling back to whatever this clone last saw —
    see `unreportable` for what a stale or missing ref does to the graph.

    `checks` is what CI actually ran, by name, and it comes from the API rather
    than from the workflow files because the question is not which workflows
    exist — see `unasked`.
    """
    run("git", "fetch", "--quiet", "origin")
    raw = run("gh", "pr", "list", "--state", "open", "--limit", str(limit),
              "--json", "number,headRefName,title,files,statusCheckRollup")
    prs = [(p["number"], p["headRefName"], p["title"],
            {f["path"] for f in p["files"]},
            {c.get("name") or c.get("context", "?")
             for c in p["statusCheckRollup"] or ()})
           for p in json.loads(raw)]
    prs = sorted(prs)
    if why := unreportable(prs, limit):
        sys.exit(why)
    return prs


def ruled_on(branch):
    """True when `branch` has ever had a PR — open, merged or closed."""
    return bool(json.loads(run("gh", "pr", "list", "--head", branch,
                               "--state", "all", "--json", "number")))


def unopened(prs, ruled=ruled_on):
    """[(branch, [subjects])] — `origin` branches no open PR will land.

    `unreportable` guards the queue against a PR with no ref. This is the
    mirror: a ref with no PR. A branch pushed to `origin` and never opened is a
    change in exactly the state every line below is about — cut from `main`, not
    landed, editing the files the queue edits — and it appears in no wave, no
    round, no fold and no conflicting pair, because the queue is read from the
    API's open list and that list is the one place it is absent. Nothing errors.
    The report is simply about a smaller queue than the repository holds, and
    `N-1 rebase rounds for the whole queue` is a claim about the whole of a
    subset.

    It is also the one position here that no ordering and no rebase improves. A
    PR in a later wave lands late; a branch with no PR does not land, and its
    cost grows with the queue rather than with its own content: every head
    opened after it edits the files it was cut to change, so the work it carries
    is re-found and re-authored rather than merged, and the authoring that
    reaches `main` is whichever one someone remembered to open.

    The test is reachability, not age. A branch whose every commit is reachable
    from `main` or from an open head has already been landed or superseded, and
    is stale rather than pending; what survives it is a diff that exists nowhere
    else in the repository. Reachability is also why this runs before the API is
    asked anything: it is local, it cuts the field to a handful, and each
    survivor can then be checked exactly — `--head <branch> --state all`, which
    has no page to truncate. A branch whose PR was *closed* is excluded by that
    check and not reported, because a closed PR is a ruling. Listing a declined
    change as forgotten work is how a section like this earns the habit of being
    scrolled past.

    Reachability's one blind spot is the same one `stacked` has, from the same
    cause: a re-authoring shares no commit with its original. Lift a forgotten
    branch's fix onto an open head and the branch keeps being reported, because
    the commit that carries it is a different one. `patch-id` is the obvious
    answer and does not work — the lift that prompts this is a cherry-pick with
    a conflict, so the hunk lands with different context and hashes to something
    else. The row that survives is therefore not a false positive to suppress
    but the last thing holding a ref nobody will merge: the operator deletes it,
    and until they do, a branch whose content has landed is reported in the one
    way that costs an extra line rather than a lost fix.
    """
    landed = ["main", *(f"origin/{ref}" for _, ref, *_ in prs)]
    out = []
    for ref in run("git", "for-each-ref", "--format=%(refname:short)",
                   "refs/remotes/origin").split():
        if ref in ("origin", "origin/main") or ref in landed:
            continue
        carried = run("git", "log", "--no-merges", "--format=%s",
                      ref, "--not", *landed).splitlines()
        branch = ref.split("/", 1)[1]
        if carried and not ruled(branch):
            out.append((branch, carried))
    return out


def stacked(prs):
    """{contained: container} when one PR's head is an ancestor of another's.

    A stacked PR carries no diff of its own once its container lands, and it
    breaks a fold: the pair merges cleanly (their merge base *is* the contained
    head) but folding the contained tree first and then merging the container
    against `main` re-reads the shared files as two independent edits. Landing
    the container closes both, so the contained PR leaves the graph.

    Containment is asymmetric everywhere except one case: two PRs opened on the
    *same* head are each other's ancestor. Recorded both ways, the caller drops
    both and the queue loses the change outright — and the report tells the
    operator to land each in order to close the other, which closes neither.
    That pair is a duplicate, not a stack, so the tie is broken on number: the
    lower one is the original and carries the review history, and it survives.
    """
    def ancestor(child, parent):
        return subprocess.run(
            ["git", "merge-base", "--is-ancestor",
             f"origin/{child}", f"origin/{parent}"],
            capture_output=True).returncode == 0

    out = {}
    for a, ref_a, *_ in prs:
        for b, ref_b, *_ in prs:
            if a == b or not ancestor(ref_a, ref_b):
                continue
            if a < b and ancestor(ref_b, ref_a):
                continue
            out[a] = b
    # A container that is itself contained has already left the plan, so naming
    # it sends the operator to land a PR the same report just dropped. Follow
    # the chain to the one that survives.
    for pr in out:
        while out[pr] in out:
            out[pr] = out[out[pr]]
    return out


def rounds(order, refs):
    """Cumulative landing rounds: what `main` holds after each wave lands."""
    out, seen = [], []
    for wave in order:
        seen = seen + [(n, refs[n]) for n in wave]
        out.append(list(seen))
    return out


def conflicts(base, prs):
    """{frozenset({a, b}): [conflicted paths]} for pairs that do not merge.

    The paths come from `merge-tree --name-only`, not from intersecting the two
    diffs. A pair's changed-file sets overlap far more widely than the merge
    fails: every PR here bumps the same two version manifests to the same
    string, so those two paths sit in 24 of this queue's 25 intersections and
    conflict in none of them — git takes an identical edit from both sides
    without asking. Printing the intersection sends the resolver to 96 files to
    resolve 29, and the noise is not evenly spread: one pair's intersection
    lists four role files where a single one disagrees, with the real one third
    in the list. The question this report exists to answer is which file a
    human has to open, and only the merge knows that.

    An intersection is still the fallback when the command fails with no paths
    to name, which is a git error rather than a conflict. `unreportable` turns
    the one reachable cause away first; this keeps the older, wider answer for
    anything that gets past it rather than reporting a clean merge.

    Measured against `base`, explicitly, because the merge the operator is
    going to perform is onto `main` and no other tree. Left to itself
    `merge-tree` infers the pair's own merge base, which is `main` only for
    branches that share nothing else — and in a queue where each session
    builds on the last, two heads routinely share a lineage well past it. That
    shared tip already holds the content the pair contests, so the merge git
    answers about is a no-op and the conflict is simply not there.

    One such pair is enough to empty the second half of this report. Its two
    members look independent, so `waves` seats them together; the fold that
    assembles the wave does pin `base`, refuses one of them, and every round
    the run would have verified becomes unassemblable. The relation the waves
    are built from has to be the relation the fold enforces.

    Neither is it caught upstream: `stacked` drops a head whose whole diff
    another contains, and these two diverged after the tip they share, so each
    holds commits the other does not and both stay in the plan.
    """
    found = {}
    for i, (a, ref_a, _, files_a, *_) in enumerate(prs):
        for b, ref_b, _, files_b, *_ in prs[i + 1:]:
            merged = subprocess.run(
                ["git", "merge-tree", "--write-tree", "--name-only",
                 "--merge-base", base, f"origin/{ref_a}", f"origin/{ref_b}"],
                capture_output=True, text=True)
            if merged.returncode != 0:
                # <tree oid>\n<conflicted path>*\n\n<informational messages>
                named = merged.stdout.split("\n\n")[0].splitlines()[1:]
                found[frozenset((a, b))] = named or sorted(files_a & files_b)
    return found


def siblings(base, refs, edges):
    """Edge pairs whose conflict is shared history, not contested content.

    Returns {frozenset({a, b}): the commit the pair actually branches from}.

    `conflicts` pins `--merge-base base` on purpose and has to: the fold that
    assembles a wave pins it too, so the relation the waves are built from must
    be the one the fold enforces. For two heads that diverged well past `main`
    that pinning reports an add/add over every path their shared trunk created —
    a conflict their real merge does not have. As an ordering input the
    over-count is safe: a wave boundary where none was needed costs a rebase
    round nobody has to run.

    It is not safe for `competing`, which reads that same edge plus equal file
    sets as "successive drafts of one change" and emits *close the other*. A
    shared trunk guarantees equal file sets — each side carries every path the
    trunk touched, whatever it went on to do — so the rivalry signature fires on
    sibling heads for the very reason their conflict is false, and closing either
    one deletes the commits it alone holds. The two readings disagree about
    something answerable, so ask it: does the pair merge at its own base?

    Over this queue's 25 edges exactly one pair has a merge base past `main`
    (#6 and #50, thirteen commits of shared trunk), it merges clean there, and
    it is the only pair `competing` names.
    """
    at = run("git", "rev-parse", base).strip()
    out = {}
    for pair in edges:
        a, b = sorted(pair)
        heads = [f"origin/{refs[a]}", f"origin/{refs[b]}"]
        found = subprocess.run(["git", "merge-base", *heads],
                               capture_output=True, text=True)
        tip = found.stdout.strip()
        # No merge base at all (unrelated histories) is not a shared trunk.
        if found.returncode != 0 or not tip or tip == at:
            continue
        if subprocess.run(["git", "merge-tree", "--write-tree",
                           "--merge-base", tip, *heads],
                          capture_output=True).returncode == 0:
            out[pair] = tip
    return out


def competing(files, edges, kin=()):
    """Conflicting pairs that change *exactly* the same files — rival authorings.

    `stacked` catches the case where one head's history is inside another's.
    That is the cheap half of supersession. The other half is a head that was
    re-authored rather than extended: the later work keeps the same file set,
    rewrites the same lines, and shares no commit with the draft it replaces.
    Ancestry sees nothing, so both stay in the graph as an ordinary conflict.

    They are not an ordinary conflict, and the difference is an instruction.
    A conflict between two changes means each has a hunk the other's tree does
    not account for, and the second to land rebases those hunks. Here neither
    PR touches a path the other leaves at `base`: whichever lands second has no
    file left to rebase *into* — every one of them has already been rewritten
    by the first. So the resolution is not a rebase, it is a choice of which
    authoring `main` keeps, and closing the one not kept removes the edge
    outright. A rebase cannot: it would re-apply a draft over its own successor.

    Equal file sets are the whole test, and they are a narrow one by design.
    Nesting is not enough — a PR that edits two of another's twelve paths is
    routinely an unrelated change that happens to collide. Equality says the
    two diffs were cut around the same unit of work, and a conflict says they
    disagree about its content.

    Narrow is not sufficient. Equality was claimed to fire "only on heads that
    are literally successive drafts of one checker", and over this queue it
    fires on one pair that is not: two sessions that branched from a common tip
    and extended it in different directions. A shared trunk produces both halves
    of the signature by itself — the same file set on each side, and an add/add
    against `main` over every one of those files — so the test cannot tell a
    re-authoring from a sibling, and the instruction it emits is destructive in
    the wrong direction. `kin` is `siblings`, the pairs that merge at their own
    base; they are an ordering question and never a close.

    No ordering is emitted for what survives. Both directions cost the same —
    nothing — because only one of the two is meant to land, and which one is the
    operator's call: the newer head carries the later audits, the older carries
    the review history. Naming the pair is the report's job; picking is not.
    """
    return {pair for pair in edges
            if files[min(pair)] == files[max(pair)] and pair not in kin}


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
    file at all. Git still reports the conflict there, and the path this report
    prints is that same file, so both send the resolver to the one place the
    change must not be applied. The destination only ever appears on the
    restructurer's side of the diff, never among the conflicted paths.

    The distinction is the operator's cost, not a detail: a same-file conflict
    is a rebase either way round, and a relocated one is a hand re-authoring in
    one direction only. `loser` before `winner` and the hunks apply to the file
    they were written against; `winner` first and they have nowhere to go. The
    keys are therefore read as precedence pairs by `waves`, which is the whole
    reason to classify the edge rather than just report it.
    """
    refs = {n: f"origin/{ref}" for n, ref, *_ in prs}
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


LINK = re.compile(r"\]\(([^)\s]+?\.md)(?:#[^)]*)?\)")


def links(path, text):
    """Repo-relative targets of the local `.md` links written in `path`.

    Anchors are stripped before resolution: a link is to a file, and one
    written with a `#section` suffix points at the same file as one without.
    A checker that requires the target to *end* in `.md` silently drops every
    deep link, which is the form prose reaches for most.
    """
    base = posixpath.dirname(path)
    return sorted({
        posixpath.normpath(posixpath.join(base, target))
        for target in LINK.findall(text)
        if not target.startswith(("http:", "https:", "//", "/"))
    })


def dangling(prs):
    """{(provider, consumer): {path: [targets]}} — links a clean merge breaks.

    A relative link is prose, not a hunk. A PR that writes "read this before
    acting" and the PR that adds the file it names touch no common path, so
    `merge-tree` reports no conflict and `waves` is free to place the consumer
    first. The result merges green and reads broken: `main` carries a role
    pointing at a file `main` does not have. Mergeable is not coherent, and
    this is the cross-PR form of it — invisible to CI, which asks each PR
    about a tree that contains only that PR.

    Only a target some *other open PR* provides becomes an edge. A link no
    head resolves is not an ordering problem at all: template prose resolves
    against the consumer's repository, never this one, so the same absence
    that would be a defect in a role is the intended state in a template.
    Requiring a provider separates the two without naming either.
    """
    heads = {n: f"origin/{ref}" for n, ref, *_ in prs}

    def blob(ref, path):
        found = subprocess.run(["git", "show", f"{ref}:{path}"],
                               capture_output=True, text=True)
        return found.stdout if found.returncode == 0 else None

    out = {}
    for number, _, _, paths, *_ in prs:
        for path in sorted(p for p in paths if p.endswith(".md")):
            text = blob(heads[number], path)
            if text is None:  # the PR deletes it — nothing left to resolve
                continue
            for target in links(path, text):
                if blob(heads[number], target) is not None:
                    continue
                for other, *_ in prs:
                    if other != number and blob(heads[other], target) is not None:
                        out.setdefault((other, number), {}).setdefault(
                            path, []).append(target)
    return out


def waves(numbers, edges, precedes=()):
    """Group PR numbers into internally conflict-free waves.

    Highest-degree first: a PR that collides with many others is the one whose
    delay costs the most rebases, so it goes in the earliest wave it fits.

    `precedes` holds (before, after) pairs — the keys of `relocations` — and
    overrides that heuristic where the two directions of an edge cost
    different things. Degree cannot see direction, and a restructurer is by
    construction the highest-degree node in its cluster, so degree alone always
    schedules the one order that turns its partners into hand re-authorings.
    A constrained PR waits for every predecessor to be *placed*, not merely
    scheduled alongside it, so the restructurer rebases over content that has
    already landed.

    Constraints that cycle are dropped rather than deadlock the queue: a cycle
    means each PR relocates the other's text, which no ordering fixes, and a
    printed wave the operator can argue with beats no output at all.
    """
    numbers = list(numbers)
    present = set(numbers)
    after = {}
    for before, later in precedes:
        if before in present and later in present:
            after.setdefault(later, set()).add(before)
    degree = {n: sum(1 for e in edges if n in e) for n in numbers}
    remaining = sorted(numbers, key=lambda n: (-degree[n], n))
    out, placed = [], set()
    while remaining:
        wave = []
        for pr in remaining:
            if after.get(pr, set()) - placed:
                continue
            if all(frozenset((pr, w)) not in edges for w in wave):
                wave.append(pr)
        if not wave:  # every candidate is blocked — the constraints cycle
            after = {}
            continue
        out.append(sorted(wave))
        placed.update(wave)
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

    `only` narrows the set by name, for asking a tree about one named gate —
    `per_member`, where the question is a gate the round introduces and the other
    verdicts genuinely are not it. Never where the output is an instruction about
    the whole tree: see `clearing`, which asks for all of them.
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

    `only` restricts the run to gates of that name, for a caller whose question
    really is about one gate. `SUITE` is a name like any other there. A caller
    that reports a *verdict about the tree* must not narrow: a subset re-run can
    only move the answer toward green, since no gate outside the subset is given
    the chance to fail.
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


def scope(base, tree, refs):
    """Per ref, the files a rebase onto `tree` will have to re-author.

    A refusal is where this report stops, and `unverifiable` turns that into one
    instruction: land the round below, rebase, re-run. But the rebase is the
    work, and the operator is handed PR numbers with no idea what any of them
    costs — a version-scalar collision and a hand re-authored contract read
    identically as "conflicts with an earlier round". `merge-tree` names the
    conflicted paths on the fold that produced the refusal, and `union_tree`
    drops them on the floor; this asks again and keeps them.

    Measured against the *assembled* tree rather than the accumulation at the
    moment each ref was refused. That is the tree the operator is going to land,
    so it is the one their rebase will actually meet — and it makes the answer
    independent of the order the fold happened to visit the refs in.
    """
    out = {}
    for number, ref in refs:
        done = subprocess.run(
            ["git", "merge-tree", "--write-tree", "--merge-base", base,
             tree, f"origin/{ref}"], capture_output=True, text=True)
        out[number] = sorted(
            {ln.split(" in ", 1)[1] for ln in done.stdout.splitlines()
             if ln.startswith("CONFLICT") and " in " in ln})
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
        held = set(refused)
        # Not "conflict with an earlier round": that is the usual cause and the
        # caller's `unverifiable` already says it, but round 1 has no earlier
        # round, and a fold can refuse there too — pairwise clean is a weaker
        # property than folds. Naming a cause this function cannot observe
        # sends the operator to rebase onto a round that may not exist.
        lines = ["not assembled — "
                 + ", ".join(f"#{n}" for n in refused)
                 + " do not fold into the rest of this round; their resolved "
                   "content does not exist yet",
                 "  what each one will owe once the round below lands:"]
        for number, paths in scope(
                base, commit, [r for r in refs if r[0] in held]).items():
            lines.append(f"    #{number}  " + (", ".join(paths) or
                                               "(clean against the assembled "
                                               "tree — refused by fold order)"))
        return lines, refused, []

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

    A gate already on `main` has judged every open branch, because a
    `pull_request` run is evaluated at the merge of the head into its base — so
    `main`'s gate set is the one every PR answers to, whatever its own head
    carries. `unasked` is where that holds or does not. One arriving in this
    round has judged nothing but the branch that
    wrote it, and `--verify` does not close that gap: it asks each gate once,
    about the union. For a gate whose subject is a *tree* that is the right
    question. For one whose subject is a *diff* it is a question nobody will
    ever be asked — `check_version_bump.py` reads the union as a single change,
    so one member's version bump answers for the round's entire content.
    """
    return sorted(gates_in(commit) - gates_in(base))


def gates_in(ref):
    """Gate filenames in `ref`'s `scripts/` tree."""
    listed = run("git", "ls-tree", "-r", "--name-only", ref, "scripts/")
    return {name for name in (Path(p).name for p in listed.splitlines())
            if name.startswith("check_") and name.endswith(".py")}


def unasked(prs):
    """Numbers whose CI ran nothing at all, in queue order.

    `introduced` and `per_member` both stop at "CI asks each of them
    separately", and the fold verdict is only honest because that sentence is
    true. It is a claim about the *base branch*: a `pull_request` run is
    evaluated at the merge of the head into its base, so a PR is judged by the
    gates `main` has. When `main` has none — which is exactly the queue this
    report is written for, every gate still on its own branch — the deferral
    names a run that did not happen.

    Zero is the only state worth naming. A red or pending check is a verdict
    already on the PR, where the operator will see it; an absent one is the
    question going unasked, and nothing distinguishes that from a pass. It is
    read from the API rather than from the workflow files on each head because
    those answer which workflows *exist*, and a workflow can exist and still
    not run — wrong event, a path filter, a cancelled run.
    """
    return [n for n, _, _, _, checks in prs if not checks]


def per_member(base, refs, gates):
    """Each member of the round judged by the round's new gates, one at a time.

    The subject is not the member's own head: a gate is only present once its
    own PR lands, and these gates read the tree they sit in. The honest tree is
    the round's tooling plus this one member — what `refs/pull/N/merge` becomes
    the moment the tooling is on `main`, and the verdict CI will actually print.

    One member cannot be judged that way: the one bringing a gate is inside its
    own subject tree, so it is folded into the base and the fold is reported as
    the single verdict it is. What decides the fold is whether the member adds
    or edits one of `gates` — not whether it happens to touch `scripts/` or
    `.github/workflows/`. Those paths hold plenty that no gate reads: a report
    generator, a docs job, a gate's own tests. Folding by path swept them in and
    then printed the fold's colour against each of their numbers, which is this
    report's own indictment turned inward — "the union answers it once, CI asks
    per PR" is exactly what a fold of six does to five PRs that are individually
    green. A member that brings no gate is judged singly like any other.

    The fold's verdict still answers for none of its own members, and says so:
    it is one tree, and the tree each carrier lands in holds the others.

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
            Path(f).name in gates for f in changed) else judged
        bucket.append((number, ref))

    landing, folded, refused = union_tree(base, carriers)
    if refused:
        return ["  the round's tooling does not assemble — "
                + ", ".join(f"#{n}" for n in refused)
                + " conflict with it; no member can be judged as CI will"]

    lines = [f"  gates this round introduces: {', '.join(gates)}"]
    fold = (", ".join(f"#{n}" for n in folded) + " (the gates themselves)"
            if folded else None)
    subjects = [(fold, landing)] if folded else []
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
        if label == fold:
            lines.append("      one verdict about one tree, and it is not any "
                         "of theirs: a gate cannot judge the PR that brings it. "
                         "Each is asked separately only once the others are on "
                         "`main` — a `pull_request` run reads the base's gates, "
                         "and this round is what puts them there.")
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
    answer is not simply withheld for the PRs most likely to be the fix. That
    trim is itself a change to the subject, and it must be controlled for: a
    gate whose cause was one of the removed members comes back green with the
    candidate merely standing in the tree, and the instruction then names a PR
    that did nothing. So a blocked candidate is credited only for gates still
    red in the trimmed round *without* it. Same control as the one below, on the
    other axis: there the baseline is every gate rather than the red ones, here
    it is the tree the candidate actually joined rather than the round it was
    never in. A removal that turns a gate green is reported as the removal —
    it is a landing-order fact, and the only alternative wording this has is
    "a defect in the assembled tree", which would be false.

    The trim runs in the other direction too, and the baseline is one baseline.
    A blocker can be the *provider* a gate wants, not the cause of its red: take
    it out and a gate green in the round is red in the tree the candidate was
    tested in, with the candidate again merely standing there. Measured against
    the round, that reads back as "it also turns X red — the move trades one
    failure for another", which is an instruction to decline a move that fixed
    what it claimed to. Credit and blame are the same comparison and must use the
    same tree: green in the trimmed round, red once the candidate joins it.
    Unblocked, nothing was removed and the trimmed round is the round.

    Every gate is re-run, not only the failing ones. `only=failing` is the right
    narrowing for `per_member`, which asks about one gate on purpose; here the
    output is an *instruction* — "move it here" — and that is a claim about the
    whole tree the move produces. Asked about the red gates alone, the trial is
    one-sided in the direction that costs: a candidate can only ever improve the
    verdict, because nothing that was green is given the chance to stop being so.
    What the operator would land is then a round that trades one red for another,
    reported as the fix for the first.
    """
    numbers = [n for n, _ in landed]
    lines, cleared = [], {name: [] for name in failing}
    # Per blocker set, the gates still red once those members are out. The trim
    # is what makes a blocked candidate judgeable, and it takes its blockers'
    # content with it — so a gate they were the cause of comes back green with
    # the candidate merely present for it. Keyed, because a queue's candidates
    # share blocker sets and each entry costs a fold and a full gate run.
    trims, removal = {}, {}
    for number in remaining:
        blocked = blockers(number, numbers, edges)
        trimmed = [pr for pr in landed if pr[0] not in blocked]
        commit, _, refused = union_tree(base, trimmed + [(number, refs[number])])
        if refused:
            continue
        results = run_checkers(commit)
        key = tuple(blocked)
        if key and key not in trims:
            kept, _, denied = union_tree(base, trimmed)
            trims[key] = set(failing) if denied else {
                name for name, (code, _) in run_checkers(kept).items() if code}
            for name in set(failing) - trims[key]:
                removal.setdefault(name, set()).update(blocked)
        # One baseline, both directions: the tree the candidate actually joined.
        # Unblocked, nothing was removed and that tree is the round itself.
        baseline = trims.get(key, failing)
        # Green in the baseline, red once this candidate joins it. A gate missing
        # from the fold counts as unresolved, not as cleared.
        broke = sorted(name for name, (code, _) in results.items()
                       if code and name not in baseline)
        for name in failing:
            if name not in baseline:
                continue
            if results.get(name, (1, []))[0] == 0:
                cleared[name].append((number, blocked, broke))
    for name in failing:
        if not cleared[name]:
            lines.append(
                f"  nothing in the remaining queue clears {name} — "
                + (("the round without "
                    + ", ".join(f"#{n}" for n in sorted(removal[name]))
                    + " is green on it, so the cause is a member of this round, "
                      "not the assembled tree")
                   if name in removal else
                   "a defect in the assembled tree, not a landing order"))
            continue
        for number, blocked, broke in cleared[name]:
            if blocked:
                line = (f"  #{number} clears {name}, but conflicts with "
                        + ", ".join(f"#{n}" for n in blocked)
                        + " in this round — a green `main` means resolving them "
                          "together, not landing the round as it stands")
            else:
                line = (f"  #{number} clears {name} and merges clean into "
                        f"this round — move it here")
            if broke:
                line += ("; it also turns " + ", ".join(broke)
                         + " red, which was green in the round — the move trades "
                           "one failure for another, it does not end them")
            lines.append(line)
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
    titles = {n: t for n, _, t, _, _ in prs}
    refs = {n: ref for n, ref, *_ in prs}
    files = {n: paths for n, _, _, paths, _ in prs}
    contained = stacked(prs)
    if contained:
        prs = [pr for pr in prs if pr[0] not in contained]
    base = run("git", "rev-parse", "main").strip()
    edges = conflicts(base, prs)
    kin = siblings(base, refs, edges)
    rival = competing(files, edges, kin)
    relocated = relocations(base, prs, edges) if edges else {}
    unresolved = dangling(prs)
    order = waves([n for n, *_ in prs], edges,
                  list(relocated) + list(unresolved))

    print(f"{len(prs)} open PRs, {len(edges)} conflicting pairs, "
          f"{len(order)} waves ({max(len(order) - 1, 0)} rebase rounds)\n")
    if pending := unopened(prs):
        carried = sum(len(subjects) for _, subjects in pending)
        print(f"{len(pending)} branch(es) on `origin` carry {carried} commit(s) "
              f"that no open PR lands, and no wave, round or conflicting pair "
              f"below counts them — the queue is the API's open list, and these "
              f"are the one thing missing from it:")
        for branch, subjects in pending:
            print(f"  {branch}")
            for subject in subjects:
                print(f"    {subject}")
        print("A PR in a later wave lands late; a branch without one does not "
              "land. Every head opened after it edits the files it was cut to "
              "change, so what it carries gets re-found and re-authored instead "
              "of merged. Opening a PR is what puts it in the graph below.\n")
    if blind := unasked(prs):
        print(f"CI ran no check at all on {len(blind)} of {len(prs)}: "
              + ", ".join(f"#{n}" for n in blind)
              + ". A `pull_request` run is evaluated at the merge of the head "
                "into its base, so a PR is judged by the gates `main` has — "
                "and `main` holds "
              + (", ".join(sorted(gates_in(base))) or "none")
              + ". Every per-PR verdict below is therefore deferred to a run "
                "that did not happen, which looks exactly like a pass. Landing "
                "the round that carries the gates is what asks the question; "
                "nothing on these PRs needs fixing first.\n")
    for small, big in sorted(contained.items()):
        print(f"#{small} is contained in #{big} — landing #{big} closes it; "
              f"not counted above\n")
    for pair in sorted(rival, key=sorted):
        a, b = sorted(pair)
        alone = [n for n in (a, b)
                 if sum(1 for e in edges if n in e) == 1]
        print(f"#{a} and #{b} change exactly the same {len(files[a])} file(s) "
              f"and conflict — rival authorings of one change, not two changes. "
              f"Neither leaves a path at `main`'s version for the other to "
              f"rebase into, so the second to land has nothing to move: decide "
              f"which one `main` keeps and close the other. "
              + (f"That also removes the only conflict "
                 + " and ".join(f"#{n}" for n in alone)
                 + f" {'has' if len(alone) == 1 else 'have'}, "
                   f"which a rebase would not.\n"
                 if alone else "A rebase re-applies a draft over its own "
                               "successor.\n"))
    for pair, tip in sorted(kin.items(), key=lambda kv: sorted(kv[0])):
        a, b = sorted(pair)
        print(f"#{a} and #{b} branch from {run('git', 'rev-parse', '--short', tip).strip()} "
              f"— {run('git', 'log', '-1', '--format=%s', tip).strip()} — and "
              f"merge clean there. The conflict below is measured against "
              f"`main`, which does not have that trunk yet, so it counts the "
              f"files the trunk created on both sides at once. Nothing is in "
              f"contention: each holds commits the other does not "
              f"(#{a}: {len(run('git', 'rev-list', f'{tip}..origin/{refs[a]}').split())}, "
              f"#{b}: {len(run('git', 'rev-list', f'{tip}..origin/{refs[b]}').split())}), "
              f"and once either lands the trunk is on `main` and the other "
              f"applies over it. Land them in either order; close neither. The "
              f"wave boundary between them below is this report being "
              f"conservative, not a rebase you owe.\n")
    for i, wave in enumerate(order, 1):
        print(f"Wave {i} — land in any order, no rebase between them:")
        for n in wave:
            print(f"  #{n:<4} {titles[n]}")
        print()
    if edges:
        print("Conflicting pairs and the files the merge actually fails in:")
        for pair, shared in sorted(edges.items(), key=lambda kv: sorted(kv[0])):
            a, b = sorted(pair)
            print(f"  #{a} <-> #{b}: {', '.join(shared) or '(no path named)'}")
            for loser, winner in ((a, b), (b, a)):
                for path, destinations in sorted(
                        relocated.get((loser, winner), {}).items()):
                    print(f"    #{winner} moves that text out of {path} — "
                          f"#{loser}'s hunks belong in "
                          f"{', '.join(destinations)}, not there. "
                          f"#{loser} is therefore ordered before #{winner} "
                          f"above: a rebase cannot move a hunk across files, "
                          f"but #{winner} can re-split a file that already "
                          f"contains it.")

    if unresolved:
        print("\nLinks that only resolve once another PR lands — no conflict, "
              "so nothing else here sees them:")
        for (provider, consumer), where in sorted(unresolved.items()):
            for path, targets in sorted(where.items()):
                print(f"  #{consumer} {path} -> {', '.join(targets)} — "
                      f"added by #{provider}, absent from #{consumer}'s own "
                      f"head. The pair merges clean, so #{consumer} can land "
                      f"first and leave `main` pointing at a file it does not "
                      f"have. #{provider} is ordered before #{consumer} above.")

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
                                     [n for n, *_ in prs if n not in landed],
                                     failing, edges, refs):
                    print(line)
            if refused:
                print(unverifiable(i))
                break
            gates = introduced(base, union_tree(base, cumulative)[0])
            if gates:
                print("\n  A gate landing with the content it judges has judged "
                      "none of it — the union answers it once, and CI will ask "
                      "per PR only once these are on the base:")
                for line in per_member(base, cumulative, gates):
                    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
