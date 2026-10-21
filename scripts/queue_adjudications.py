#!/usr/bin/env python3
"""Split the queue's conflicts into the ones a rebase settles and the ones a human must decide.

`pr_landing_order.py` groups the open queue into waves and reports the cost of
landing it as rebase rounds. That number is right and it is also the wrong unit,
because a rebase and a decision are not the same work. A rebase is mechanical:
the resolver reapplies their own change somewhere else and nothing about the
product changes. A decision is a product question — two heads assert different
rules over the same line of `main`, and whoever resolves the conflict chooses
which rule ships. The resolver is usually not the author of either.

Nothing here separates them, and the separation is what the open queue's own
history argues for. Every head in it is `MERGEABLE` against `main` — all of
them, at the time of writing — so GitHub shows the queue as 88 green buttons.
Merging any one of them turns a share of the rest into hand work, and the badge
cannot say whether that hand work is twenty minutes of rebasing or a design
call nobody has made.

So classify the *text*, which is the one thing a script can do here without
having an opinion about prose:

  * **identical** — both heads replace the line with the same thing. Not a
    conflict at all; `merge-tree` resolves it. This is the common case for a
    manifest version bump and it is why a shared line is not a cost.
  * **subsumed** — one head's replacement contains every line of the other's.
    Mechanical: take the superset and no content is lost. Still no opinion —
    containment is a fact about the two texts, not a judgement of them.
  * **relocation** — the texts differ, but one head is moving that file's prose
    out rather than editing it, so git anchored its removal to lines the partner
    rewrites in place. Mechanical again, and in the one direction
    `pr_landing_order.py` already names: land the restructurer last and it
    re-applies its own split. Three heads in this queue are of that shape, and
    leaving them in the divergent bucket is what turned 272 decisions into 903.
  * **divergent** — each head writes a line the other does not, and neither is
    relocating. There is no resolution that keeps both texts, so somebody picks,
    and picking drops a rule that was argued for on its own pull request.
    **This is the report.**

A divergent edge is not a merge defect. Both heads are correct against the
`main` they were cut from; the incompatibility exists only in the tree that
contains both, which is the tree no reviewer is ever shown. The concrete case
this was written from: two open heads rewrite the same `plan` bullet about what
a browser agent cannot reach. One routes the resulting `BLOCKED` verdict into
the report's Known-gaps section; the other records it as an environment-scoped
annotation in the plan. Each is coherent alone. Landed together the skill has
two homes for one fact, and a resolver reading either diff cannot see the other.

The output is a finite decision list, which is the point. "88 pull requests" is
not a thing a human can act on. "N decisions, each one line of `main` and two
candidate texts" is.

Divergence is reported per shared *main-side line*, not per file. The file-level
view already exists (`pr_landing_order.py --contracts` lists converged paths)
and it does not locate anything: in this repo nineteen of twenty-one heads edit
one `SKILL.md`, which tells a reviewer only that the file is popular.

Usage: python3 scripts/queue_adjudications.py [--base REF] [--limit N] [--all]
Exit 0 always — this is an operator report, not a gate.
"""

import argparse
import collections
import itertools
import json
import re
import subprocess
import sys

HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+")


def run(args: list[str], cwd: str | None = None) -> str:
    """Capture stdout; raise on failure."""
    return subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, check=True
    ).stdout


def parse_hunks(diff: str) -> dict[str, list[tuple[int, int, list[str]]]]:
    """{path: [(old_start, old_count, added_lines)]} for hunks that replace text.

    Pure insertions (`-N,0`) are dropped. Two heads appending different rules at
    the same anchor both keep their text, so there is nothing to decide; only a
    hunk that removes a line forces a choice about that line.
    """
    out: dict[str, list[tuple[int, int, list[str]]]] = collections.defaultdict(list)
    path: str | None = None
    pending: tuple[str, int, int] | None = None
    added: list[str] = []

    def flush() -> None:
        if pending:
            p, start, count = pending
            out[p].append((start, count, added))

    for line in diff.split("\n"):
        if line.startswith("+++ b/"):
            flush()
            path, pending, added = line[6:], None, []
            continue
        match = HUNK.match(line)
        if match:
            flush()
            added = []
            count = int(match.group(2)) if match.group(2) is not None else 1
            pending = (path, int(match.group(1)), count) if path and count else None
        elif pending and line.startswith("+") and not line.startswith("+++"):
            added.append(line[1:])
    flush()
    return dict(out)


def classify(added_a: list[str], added_b: list[str]) -> str:
    """'identical' | 'subsumed' | 'divergent' for two replacements of one region.

    Compared as sets of whitespace-stripped non-empty lines: reindented or
    rewrapped prose that says the same thing is not a decision, and a blank line
    is not content either side asserts.
    """
    a = {line.strip() for line in added_a if line.strip()}
    b = {line.strip() for line in added_b if line.strip()}
    if a == b:
        return "identical"
    if a <= b or b <= a:
        return "subsumed"
    return "divergent"


def open_heads(limit: int, repo: str | None = None) -> list[dict]:
    """[{number, headRefName, title}] for the open queue, lowest number first."""
    args = ["gh", "pr", "list", "--state", "open", "--limit", str(limit),
            "--json", "number,headRefName,title"]
    return sorted(json.loads(run(args, cwd=repo)), key=lambda p: p["number"])


def relocated(numstat: str) -> set[str]:
    """Paths the diff removes more lines from than it adds — a move-out.

    A head that lifts prose into a new file still removes it here, so git anchors
    the removal to lines the partner head is editing in place. The texts then
    differ for a reason that is not a disagreement: one of them is a fragment of
    a section whose destination exists only on the restructurer's side. Counting
    those as decisions is how a report of 285 head pairs stops being read.

    `pr_landing_order.py` reaches the same classification from `merge-tree` and
    orders around it. This needs only the direction of the line count.
    """
    out = set()
    for line in numstat.strip().split("\n"):
        fields = line.split("\t")
        if len(fields) == 3 and fields[0].isdigit() and fields[1].isdigit():
            if int(fields[1]) > int(fields[0]):
                out.add(fields[2])
    return out


def is_ancestor(ref: str, other: str, repo: str | None = None) -> bool:
    """True when `ref` is reachable from `other` — a stacked pair, not a decision.

    A head cut from another head carries its container's hunks in its own diff
    against `base`, because that is their merge base. Left in, the descendant
    reads as adjudicating against the branch it extends.
    """
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", ref, other],
        cwd=repo, capture_output=True, text=True,
    ).returncode == 0


def edges(base: str, heads: list[dict], repo: str | None = None) -> list[dict]:
    """One row per pair of heads that replace an overlapping region of `base`."""
    per_head, refs, moves = {}, {}, {}
    for head in heads:
        ref = head["headRefName"]
        merge_base = run(["git", "merge-base", base, ref], cwd=repo).strip() or base
        span = f"{merge_base}..{ref}"
        per_head[head["number"]] = parse_hunks(
            run(["git", "diff", "--unified=0", span], cwd=repo))
        moves[head["number"]] = relocated(
            run(["git", "diff", "--numstat", span], cwd=repo))
        refs[head["number"]] = ref

    titles = {h["number"]: h["title"] for h in heads}
    found = []
    numbers = sorted(per_head)
    for i, a in enumerate(numbers):
        for b in numbers[i + 1:]:
            if is_ancestor(refs[a], refs[b], repo) or is_ancestor(refs[b], refs[a], repo):
                continue
            shared = set(per_head[a]) & set(per_head[b])
            for path in sorted(shared):
                for start_a, count_a, add_a in per_head[a][path]:
                    for start_b, count_b, add_b in per_head[b][path]:
                        if start_a + count_a <= start_b or start_b + count_b <= start_a:
                            continue
                        moved = path in moves[a] or path in moves[b]
                        verdict = classify(add_a, add_b)
                        if moved and verdict == "divergent":
                            verdict = "relocation"
                        found.append({
                            "a": a, "b": b, "path": path,
                            "line": max(start_a, start_b),
                            "verdict": verdict,
                            "title_a": titles.get(a, ""), "title_b": titles.get(b, ""),
                            "text_a": add_a, "text_b": add_b,
                        })
    return found


def report(rows: list[dict], base: str, show_all: bool, stream) -> None:
    counts = collections.Counter(row["verdict"] for row in rows)
    write = stream.write
    write(f"Overlapping replacements of {base}, by what resolving one costs:\n\n")
    for verdict, cost in (("identical", "nothing — merge-tree resolves it"),
                          ("subsumed", "mechanical — take the superset"),
                          ("relocation", "a re-apply — the partner moved the text out"),
                          ("divergent", "a decision — one rule is dropped")):
        write(f"  {counts[verdict]:5d}  {verdict:<10} {cost}\n")

    divergent = [row for row in rows if row["verdict"] == "divergent"]
    pairs = {(row["a"], row["b"]) for row in divergent}
    write(f"\n{len(divergent)} divergent regions across {len(pairs)} head pairs")
    write(f" and {len({row['path'] for row in divergent})} files.\n")
    if not divergent:
        return

    by_file = collections.Counter(row["path"] for row in divergent)
    write("\nDecisions by file:\n")
    for path, n in by_file.most_common():
        write(f"  {n:5d}  {path}\n")

    # Round-robin the sample across files. In edge order the two manifests
    # supply 194 of the 430 decisions — all of them one head saying 0.6.1 where
    # another says 0.7.0 — and a first screen of version bumps hides the prose
    # decisions, which are the ones with no obvious resolution.
    queues = collections.defaultdict(list)
    for row in divergent:
        queues[row["path"]].append(row)
    spread = [row for group in itertools.zip_longest(*queues.values())
              for row in group if row is not None]
    shown = spread if show_all else spread[:12]
    write(f"\nThe decisions ({len(shown)} of {len(divergent)} shown):\n")
    for row in shown:
        write(f"\n  {row['path']}:{row['line']}\n")
        for side in ("a", "b"):
            write(f"    #{row[side]} {row['title_' + side]}\n")
            for line in row["text_" + side][:4]:
                write(f"      | {line.rstrip()}\n")
    if not show_all and len(divergent) > len(shown):
        write("\n  --all for the rest.\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--all", action="store_true", help="print every decision")
    args = parser.parse_args(argv)

    heads = open_heads(args.limit)
    if not heads:
        print("No open pull requests — nothing to adjudicate.")
        return 0
    report(edges(args.base, heads), args.base, args.all, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
