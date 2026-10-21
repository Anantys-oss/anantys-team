#!/usr/bin/env python3
"""Find the heads in a branch queue that another head already contains.

Every other checker in this family reads one branch, or reads every branch
against one fold. This reads the branches against *each other*, which is the
one question no per-branch gate can be pointed at: a branch's own tree is
always complete and always passes, and a reviewer looking at a list of 63 pull
request titles cannot see that four of them ship the same file.

That is not hypothetical. At the time this was written the queue held two
*separate* open pull requests whose diffs touched the same five paths and whose
substantive content matched line for line, and two more whose patches were
byte-identical to each other and contained in both. Nothing reported it,
because nothing compares heads. The duplication is generative rather than
careless: a session cannot see the queue it is adding to, so it solves the
problem it was given and the queue grows a copy.

**Containment is a fact; near-duplication is a prompt.** The two outputs are
not the same kind of claim and the report keeps them apart:

  * A head is *contained* when every substantive line it adds and every one it
    removes also appears in another head's patch. Merging the container lands
    this head's content, so closing it afterwards loses nothing. That is set
    containment over the patch, checked against the recorded base, and
    ``git merge-base --is-ancestor`` is reported beside it when it also holds —
    ancestry is the stronger evidence, and it is the only supersede evidence
    that is not somebody's assertion.
  * A *near-duplicate* pair is two heads whose added lines overlap above a
    threshold without either containing the other. Usually that is one rule
    reworded on two branches. It needs a human to say which wording wins, so
    it is printed as a pair and never as a ruling.

**Matching is verbatim, so every number here is a floor.** A line one head
rewrote reads as absent on the other, which can only ever *under*-report
redundancy. That asymmetry is deliberate: an over-reported containment would
have a reader close work that was never carried, and one false row is what
teaches them to skip the section.

**Folds are reported, not excluded.** A branch that deliberately gathers the
queue contains most of it by construction, which makes it the loudest row here
and says nothing new. But it is a real container, and whether its tip is the
place the content should land is the reviewer's decision, not this script's —
so the containers are ranked by how many heads they absorb and the reader can
see at a glance which rows are a fold doing its job.

There is no exit code. A head contained in another is a fact about two
branches, and the remedy — close one, or land the other first — lives in
neither branch's diff. A gate that fails a branch for a property it cannot fix
alone forces an order on changes that may not have one. This ranks heads for a
human to read; it does not rule on them.

Run: ``python3 scripts/queue_redundancy.py``
"""

import argparse
import itertools
import subprocess
import sys

FLOOR = 40
NEAR = 0.6


def git(*args):
    """Run git, returning stdout. Raises on a failing git."""
    return subprocess.run(("git",) + args, capture_output=True, text=True,
                          check=True).stdout


def substantive(diff, floor=FLOOR):
    """The (added, removed) line sets of ``diff``, minus the boilerplate.

    Lines shorter than ``floor`` characters carry no content worth matching on
    — a closing brace, a blank, a bumped version number — and would match
    across unrelated heads. File headers start with the same characters as
    content lines and are dropped by name.
    """
    added, removed = set(), set()
    for line in diff.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            target = added
        elif line.startswith("-"):
            target = removed
        else:
            continue
        body = line[1:].strip()
        if len(body) >= floor:
            target.add(body)
    return added, removed


def contains(outer, inner):
    """True when patch ``outer`` holds every substantive line of ``inner``.

    ``outer`` and ``inner`` are ``(added, removed)`` pairs. Equal patches are
    not containment in either direction — that is a duplicate, and reporting it
    twice with the arrow pointing both ways tells the reader nothing about
    which to keep.
    """
    outer_add, outer_rem = outer
    inner_add, inner_rem = inner
    if not inner_add and not inner_rem:
        return False
    if not (inner_add <= outer_add and inner_rem <= outer_rem):
        return False
    return len(inner_add) < len(outer_add) or len(inner_rem) < len(outer_rem)


def identical(a, b):
    """True when two patches add and remove exactly the same lines."""
    return a == b and bool(a[0] or a[1])


def overlap(a, b):
    """Added-line overlap of two patches as (coverage of the smaller, jaccard).

    Coverage answers "how much of the smaller head is in the larger", which is
    what redundancy means. Jaccard is reported with it because coverage alone
    reads at ceiling for any head compared against a fold: a 30-line change is
    fully inside a 6,000-line gather, and that pair is not a duplicate.
    """
    a_add, b_add = a[0], b[0]
    if not a_add or not b_add:
        return 0.0, 0.0
    shared = len(a_add & b_add)
    if not shared:
        return 0.0, 0.0
    smaller = min(len(a_add), len(b_add))
    return shared / smaller, shared / len(a_add | b_add)


def find_containment(patches):
    """Every (inner, outer) pair where outer's patch contains inner's.

    ``patches`` maps a head name to its ``(added, removed)`` pair. Sorted by
    the contained head's size so the cheap, obvious rows read first.
    """
    found = [(inner, outer)
             for inner, outer in itertools.permutations(patches, 2)
             if contains(patches[outer], patches[inner])]
    return sorted(found, key=lambda pair: (len(patches[pair[0]][0]), pair[0]))


def find_near(patches, near=NEAR):
    """Near-duplicate pairs: high mutual overlap, neither containing the other.

    The jaccard threshold is what keeps folds out. A pair that shares most of
    the *union* of their lines is two heads doing one job; a pair that shares
    most of the smaller head only is a head inside a gather.
    """
    found = []
    for a, b in itertools.combinations(sorted(patches), 2):
        if contains(patches[a], patches[b]) or contains(patches[b], patches[a]):
            continue
        cov, jac = overlap(patches[a], patches[b])
        if jac >= near:
            found.append((round(cov, 2), round(jac, 2), a, b))
    return sorted(found, reverse=True)


def heads(prefix):
    """The remote branch names under ``prefix``, shortest-path form."""
    refs = git("for-each-ref", "--format=%(refname:short)", f"refs/remotes/{prefix}")
    return [line.strip() for line in refs.splitlines() if line.strip()]


def is_ancestor(ancestor, descendant):
    """True when ``ancestor`` is reachable from ``descendant``."""
    return subprocess.run(("git", "merge-base", "--is-ancestor", ancestor, descendant),
                          capture_output=True).returncode == 0


def pr_numbers():
    """Map head branch name -> open PR number, empty when ``gh`` cannot answer.

    A head with no PR is not an error and is not skipped: an orphan branch is
    invisible to every report that reads the PR queue, which is exactly the
    kind of work this script exists to surface.
    """
    try:
        import json
        out = subprocess.run(
            ("gh", "pr", "list", "--state", "open", "--limit", "500",
             "--json", "number,headRefName"),
            capture_output=True, text=True, check=True).stdout
        return {pr["headRefName"]: pr["number"] for pr in json.loads(out)}
    except Exception:
        return {}


def label(head, prefix, prs):
    """``#42 branch-name`` for a head with a PR, ``(no PR) name`` otherwise.

    Only the remote name is stripped to look the head up, never the whole
    prefix: a PR's ``headRefName`` is the branch as the remote holds it
    (``koan/x``), so stripping ``origin/koan`` would leave ``x`` and match
    nothing — and a lookup that silently misses reads as "every head is an
    orphan", which is the one claim this report must not invent.
    """
    _, _, branch = head.partition("/")
    short = head.rsplit("/", 1)[-1]
    number = prs.get(branch)
    return f"#{number} {short}" if number else f"(no PR) {short}"


def report(patches, prefix, prs, near=NEAR, ancestry=None):
    """The whole report as a list of lines."""
    ancestry = ancestry if ancestry is not None else is_ancestor
    out = [f"{len(patches)} heads under {prefix}/, compared against each other.", ""]

    dupes = [(a, b) for a, b in itertools.combinations(sorted(patches), 2)
             if identical(patches[a], patches[b])]
    out.append(f"## Identical patches ({len(dupes)})")
    out.append("")
    if dupes:
        out.append("Same added and removed lines. One of each pair is free to close.")
        out.append("")
        for a, b in dupes:
            out.append(f"  {label(a, prefix, prs)}  ==  {label(b, prefix, prs)}")
    else:
        out.append("None.")
    out.append("")

    found = find_containment(patches)
    out.append(f"## Contained heads ({len({inner for inner, _ in found})})")
    out.append("")
    if found:
        out.append("Merging the right-hand head lands the left-hand one's content.")
        out.append("")
        for inner, outer in found:
            size = len(patches[inner][0])
            anc = "  [ancestor]" if ancestry(inner, outer) else ""
            out.append(f"  {label(inner, prefix, prs)} ({size} lines)"
                       f"  in  {label(outer, prefix, prs)}{anc}")
        absorbed = {}
        for inner, outer in found:
            absorbed.setdefault(outer, []).append(inner)
        out.append("")
        out.append("Containers, by heads absorbed:")
        out.append("")
        for outer, inners in sorted(absorbed.items(), key=lambda kv: -len(kv[1])):
            out.append(f"  {len(inners):3}  {label(outer, prefix, prs)}")
    else:
        out.append("None.")
    out.append("")

    contained = {inner for inner, _ in found}
    orphans = [h for h in sorted(patches)
               if not prs.get(h.partition("/")[2])]
    out.append(f"## Heads with no open PR ({len(orphans)})")
    out.append("")
    if orphans and prs:
        out.append("Invisible to every report that reads the PR queue. "
                   "Marked when another head already contains them.")
        out.append("")
        for head in orphans:
            held = "  — contained above" if head in contained else ""
            out.append(f"  {label(head, prefix, prs)} "
                       f"({len(patches[head][0])} lines){held}")
    elif not prs:
        out.append("Not checked: `gh` did not answer, so every head reads as an orphan.")
    else:
        out.append("None.")
    out.append("")

    pairs = find_near(patches, near)
    out.append(f"## Near-duplicate pairs ({len(pairs)})")
    out.append("")
    if pairs:
        out.append(f"Added-line jaccard >= {near}, neither containing the other. "
                   "A human picks the wording.")
        out.append("")
        for cov, jac, a, b in pairs:
            out.append(f"  cov {cov:.2f} jac {jac:.2f}  "
                       f"{label(a, prefix, prs)}  vs  {label(b, prefix, prs)}")
    else:
        out.append("None.")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default="main", help="ref every head is diffed against")
    ap.add_argument("--prefix", default="origin/koan", help="remote ref prefix to sweep")
    ap.add_argument("--floor", type=int, default=FLOOR,
                    help="minimum line length to count as substantive")
    ap.add_argument("--near", type=float, default=NEAR,
                    help="added-line jaccard above which a pair is near-duplicate")
    args = ap.parse_args(argv)

    refs = heads(args.prefix)
    if not refs:
        print(f"no heads under refs/remotes/{args.prefix}/", file=sys.stderr)
        return
    patches = {ref: substantive(git("diff", f"{args.base}..{ref}"), args.floor)
               for ref in refs}
    print("\n".join(report(patches, args.prefix, pr_numbers(), args.near)))


if __name__ == "__main__":
    main()
