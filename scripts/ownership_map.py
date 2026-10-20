#!/usr/bin/env python3
"""Report which open heads already claim a region of `main`, before you read it.

`pr_landing_order.py` and `fold_coverage.py` both answer a reviewer's question:
in what order does the queue land, and does a fold carry it. This answers the
*author's* question, which is asked earlier and far more often: the file I am
about to read for defects — which parts of it does the queue already own?

The cost of not asking is measured, and it is the single most repeated cost in
this project's history. Nine sessions' notes record the same loop: read a role,
find a defect, discover a head already shipped the fix, drop it. One session
logged "~25 tool calls, four branches saved"; another "~20, three saved". Those
are the *successful* sweeps — each one a hand-rolled `git show` loop over every
head, rewritten from scratch because nothing in the repo does it.

The measurement that motivates the section view, taken over 58 open heads:

    anantys.qa      453 of 513 lines claimed   (88%)
    anantys.design   24 of 115                 (21%)
    anantys.ops      24 of 131                 (18%)
    spec-tester       7 of  53                 (13%)

The queue's attention is not spread over the product, it is concentrated in one
file. A session that picks its target by "what looks defective" picks `qa` —
the longest file, the one with the most rules — and spends its budget
rediscovering rulings. Picking by *what the queue has not read* is a different
and cheaper question, and it is the one this answers.

**The number is a floor on ownership, not a verdict on it.** Three reasons, and
all three push the same way — the report under-claims, never over-claims:

  * A head can own a rule without touching the lines that state it. A fix to
    "overwrite `current.md` only from state you read" lands in the Rules list,
    while the symptom lives in the Phase 6 template thirty lines up. Judge the
    *concept*, and the untouched template reads as unclaimed.
  * Line identity is `main`-relative. Two heads that rewrite one section in
    mutually exclusive ways both report as touching it, which is right; a head
    that moved the section elsewhere reports as touching it too, which is also
    right, and says nothing about where the rule now lives.
  * A pure insertion modifies no line at all. `@@ -42,0 +43,5 @@` adds a
    paragraph after line 42 without replacing anything, so a length-0 hunk has
    no old-side lines to record. Dropping it is the one false *negative* that
    matters — an appended rule is a claim on its section — so the anchor line
    is recorded instead, and `--lines` says when a hit came from one.

So the output is a **read list**, never a ruling: these heads have an opinion
about these lines, go read their diffs. It exits 0 always.

Usage:
    python3 scripts/ownership_map.py --summary
    python3 scripts/ownership_map.py <path>
    python3 scripts/ownership_map.py <path> --lines 85-110
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+")
PLUS_FILE = re.compile(r"^\+\+\+ b/(.*)$")
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
FENCE = re.compile(r"^\s*(```|~~~)")


def run(args: list[str], cwd: str | None = None) -> str:
    """Run a command and return stdout, or "" if it failed."""
    done = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    return done.stdout if done.returncode == 0 else ""


def parse_diff_old_lines(diff: str) -> dict[str, set[int]]:
    """Map each file to the `main`-side line numbers its hunks claim.

    A length-0 hunk (a pure insertion) claims its anchor line: the paragraph
    lands inside that section, so the section is spoken for.
    """
    claimed: dict[str, set[int]] = {}
    path = None
    for line in diff.splitlines():
        m = PLUS_FILE.match(line)
        if m:
            path = m.group(1)
            claimed.setdefault(path, set())
            continue
        m = HUNK.match(line)
        if m and path is not None:
            start = int(m.group(1))
            length = 1 if m.group(2) is None else int(m.group(2))
            if length == 0:
                claimed[path].add(start)  # insertion anchor, not a replacement
            else:
                claimed[path].update(range(start, start + length))
    return {p: s for p, s in claimed.items() if s}


def sections(text: str) -> list[tuple[str, int, int]]:
    """Split markdown into (heading, first_line, last_line), 1-indexed.

    Lines before the first heading are a leading section named for the file's
    frontmatter or preamble; they carry `allowed-tools`, which is where a
    surprising share of this queue's changes land.
    """
    lines = text.splitlines()
    marks = []
    fenced = False
    for i, line in enumerate(lines):
        if FENCE.match(line):
            # Every role here embeds its output template in a fence, and those
            # templates are full of `## KPI Dashboard` and `# SEO Audit Report`.
            # Read inside the fence and one file becomes a dozen fake sections,
            # each with a line range that belongs to its neighbour.
            fenced = not fenced
            continue
        if not fenced and (m := HEADING.match(line)):
            marks.append((i + 1, m.group(2).strip()))
    if not marks:
        return [("(whole file)", 1, len(lines))] if lines else []
    out = []
    if marks[0][0] > 1:
        out.append(("(frontmatter / preamble)", 1, marks[0][0] - 1))
    for (start, title), nxt in zip(marks, marks[1:] + [(len(lines) + 1, "")]):
        out.append((title, start, nxt[0] - 1))
    return out


def open_heads(repo: str | None) -> list[dict]:
    """The open PRs, as {number, head, title}. Empty if `gh` is unavailable."""
    raw = run(
        ["gh", "pr", "list", "--state", "open", "--limit", "200",
         "--json", "number,headRefName,title"],
        cwd=repo,
    )
    if not raw:
        return []
    return [
        {"number": p["number"], "head": p["headRefName"], "title": p["title"]}
        for p in json.loads(raw)
    ]


def claims(repo: str | None, base: str, heads: list[dict]) -> dict[str, dict[str, set[int]]]:
    """Per head ref, the `main`-side lines it claims, per file."""
    return {
        h["head"]: parse_diff_old_lines(
            run(["git", "diff", "-U0", f"{base}...origin/{h['head']}"], cwd=repo)
        )
        for h in heads
    }


def tracked_files(repo: str | None, base: str) -> list[str]:
    return sorted(run(["git", "ls-tree", "-r", "--name-only", base], cwd=repo).splitlines())


def file_text(repo: str | None, base: str, path: str) -> str:
    return run(["git", "show", f"{base}:{path}"], cwd=repo)


def pct(part: int, whole: int) -> str:
    return "—" if not whole else f"{round(100 * part / whole)}%"


def report_summary(repo, base, heads, by_head, stream) -> None:
    rows = []
    for path in tracked_files(repo, base):
        total = len(file_text(repo, base, path).splitlines())
        owners = {h for h, files in by_head.items() if files.get(path)}
        hit = set().union(*(by_head[h][path] for h in owners)) if owners else set()
        rows.append((pct(len(hit), total), len(hit), total, len(owners), path))
    rows.sort(key=lambda r: (-r[1] / r[2] if r[2] else 0, r[4]))
    print(f"Saturation of `{base}` by {len(heads)} open heads — least-read last\n", file=stream)
    print("| claimed | lines | heads | file |", file=stream)
    print("|---|---|---|---|", file=stream)
    for p, hit, total, nheads, path in rows:
        print(f"| {p} | {hit}/{total} | {nheads} | `{path}` |", file=stream)


def report_sections(repo, base, heads, by_head, path, stream) -> None:
    text = file_text(repo, base, path)
    if not text:
        print(f"{path}: not in {base}", file=stream)
        return
    titles = {h["head"]: (h["number"], h["title"]) for h in heads}
    print(f"`{path}` — which open heads claim each section\n", file=stream)
    print("| lines | section | heads | PRs |", file=stream)
    print("|---|---|---|---|", file=stream)
    for title, start, end in sections(text):
        span = set(range(start, end + 1))
        owners = sorted(
            (titles[h][0] for h, files in by_head.items() if files.get(path, set()) & span)
        )
        prs = " ".join(f"#{n}" for n in owners) or "—"
        print(f"| {start}-{end} | {title} | {len(owners)} | {prs} |", file=stream)


def report_lines(repo, base, heads, by_head, path, start, end, stream) -> None:
    span = set(range(start, end + 1))
    titles = {h["head"]: (h["number"], h["title"]) for h in heads}
    print(f"`{path}` lines {start}-{end} — read these before judging them\n", file=stream)
    found = False
    for head, files in sorted(by_head.items()):
        hit = files.get(path, set()) & span
        if not hit:
            continue
        found = True
        number, title = titles[head]
        print(f"#{number} {head}\n    {title}\n    claims: {compact(hit)}", file=stream)
    if not found:
        print("No open head claims these lines. The floor is zero; the ceiling is not —", file=stream)
        print("a head can own the rule without touching the lines that state it.", file=stream)


def compact(nums: set[int]) -> str:
    out, run_ = [], []
    for n in sorted(nums):
        if run_ and n == run_[-1] + 1:
            run_.append(n)
        else:
            if run_:
                out.append(run_)
            run_ = [n]
    if run_:
        out.append(run_)
    return ", ".join(str(r[0]) if len(r) == 1 else f"{r[0]}-{r[-1]}" for r in out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("path", nargs="?", help="file in the base ref to break down by section")
    ap.add_argument("--summary", action="store_true", help="per-file saturation table")
    ap.add_argument("--lines", help="A-B — list the heads claiming that range of PATH")
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--repo", default=None)
    args = ap.parse_args(argv)

    if not args.summary and not args.path:
        ap.error("give a path, or --summary")

    heads = open_heads(args.repo)
    if not heads:
        print("No open PRs found (is `gh` authenticated?). Nothing to report.", file=sys.stderr)
        return 0
    by_head = claims(args.repo, args.base, heads)

    if args.summary:
        report_summary(args.repo, args.base, heads, by_head, sys.stdout)
    elif args.lines:
        lo, _, hi = args.lines.partition("-")
        report_lines(args.repo, args.base, heads, by_head, args.path,
                     int(lo), int(hi or lo), sys.stdout)
    else:
        report_sections(args.repo, args.base, heads, by_head, args.path, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
