#!/usr/bin/env python3
"""Run every gate in this tree against every other head, and print the cells.

CI answers one question per push: does *this* head pass the gates *it* carries. In a
queue where each gate arrived on its own branch, that cross-product is nearly empty —
a checker pointed only at the work it was written from can only confirm that work. The
cell that matters is the one no push ever runs: this branch's gates against a sibling's
content.

Filling it found two defects in `check_plugins` that every green CI run had missed: a
skill-name rule asserting a string the runtime does not expose, and an unguarded
`entry[field]` that raised `KeyError` out of `main` on a sibling that legitimately drops
the field. Neither was reachable from this branch's own tree.

    python3 scripts/gate_matrix.py                        # every head on origin
    python3 scripts/gate_matrix.py origin/koan/a-head ...  # just these

The gates are overlaid onto each head, so what is measured is the head's *content*
against this branch's checkers — not whatever checkers the head happens to carry.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
#: Overlaid onto each head. `.github` comes too: a gate may read the workflow that runs it.
OVERLAY = ("scripts", ".github")


def git(*args: str, cwd: Path | None = None) -> str:
    done = subprocess.run(
        ("git", *args), cwd=cwd or ROOT, capture_output=True, text=True, check=False
    )
    return done.stdout.strip() if done.returncode == 0 else ""


def gates() -> list[str]:
    return sorted(p.stem for p in (ROOT / "scripts").glob("check_*.py"))


def heads() -> list[str]:
    """Every remote-tracking head, not every head whose *name* matches a convention.

    This swept `origin/koan/*`, which is where the queue's branches happen to live.
    A head is in the sweep because it will land, not because of how it is spelled:
    `origin/qa/non-speckit-sources` carries commits and matched nothing. `origin/main`
    is the sharper omission — it is the destination, it carries none of these gates,
    so CI has never run one against it, which is the exact cell this tool exists for.
    """
    refs = git("for-each-ref", "--format=%(refname:short)", "refs/remotes/origin/**")
    return [r for r in refs.splitlines() if r and r != "origin"]  # `origin` is origin/HEAD


class Cell(int):
    """A gate's exit code for one head, carrying the line it failed on.

    The cell stays an `int` because the exit code is what the table rules on. But a
    failing cell that reports only that code hands the reader a coordinate and no
    finding, and reading it back is not a re-run of one gate: this file's whole
    contribution is the *overlay*, so the reader has to rebuild the checkout-strip-copy
    dance by hand, once per head, to see a sentence the sweep already had. Ten failing
    cells here cost ten hand-built worktrees to classify — seven of which turned out to
    be one untagged release, which the message says and the exit code cannot.
    """

    why: str

    def __new__(cls, code: int, why: str = "") -> "Cell":
        self = super().__new__(cls, code)
        self.why = why
        return self


def finding(out: str, err: str) -> str:
    """The first error line a gate printed, or the last line it died on.

    The eight gates agree on an `error:`/`ERROR ` prefix and on nothing else, so the
    prefix is the match. Both streams are scanned: they do not agree on which one a
    finding goes to either — `check_plugins` writes it to stdout, `check_version_bump`
    writes the *changed file list* to stdout and the finding to stderr, and reading
    only stdout returns a bare path with no sentence attached to it.

    A gate that *raises* prints no such line at all, and the last line of its traceback
    is the exception — which is this tool's own finding rather than the head's, and the
    one most worth carrying out of a sweep.
    """
    for line in (out + "\n" + err).splitlines():
        if line.lstrip().lower().startswith("error"):
            return line.strip()
    tail = [line.strip() for line in (err or out).splitlines() if line.strip()]
    return tail[-1] if tail else ""


def run(tree: Path, head: str, names: list[str]) -> dict[str, Cell]:
    """Exit code per gate for one head's content. Empty when the head will not check out."""
    for name in OVERLAY:  # a head that tracks these would conflict with the checkout
        subprocess.run(("rm", "-rf", str(tree / name)), check=False)
    if subprocess.run(
        ("git", "checkout", "--detach", head, "--quiet"), cwd=tree, capture_output=True
    ).returncode:
        return {}
    git("checkout", "--", ".", cwd=tree)
    for name in OVERLAY:  # the head's own copies lose to ours, on purpose
        subprocess.run(("rm", "-rf", str(tree / name)), check=False)
        subprocess.run(("cp", "-R", str(ROOT / name), str(tree / name)), check=False)
    # `check=False` and the returncode read together: a gate is allowed to fail, and a
    # gate that raises is a finding of its own, so a traceback must not stop the sweep.
    cells = {}
    for gate in names:
        # No positional. The eight gates do not agree on what one *means* — four read a
        # root, one reads a base ref, three read none — so a `"."` passed to all eight is
        # the tree to four of them and the ref `.` to `check_version_bump`, which resolved
        # to no commit. The overlay already roots every gate twice over: `cwd` is the head
        # and these scripts were copied into it, so `ROOT` is the head too.
        done = subprocess.run(
            (sys.executable, str(tree / "scripts" / f"{gate}.py")),
            cwd=tree,
            capture_output=True,
            text=True,
            check=False,
        )
        cells[gate] = Cell(
            done.returncode, finding(done.stdout, done.stderr) if done.returncode else ""
        )
    return cells


def table(rows: dict[str, dict[str, int]], names: list[str]) -> str:
    short = [n.removeprefix("check_") for n in names]
    width = max(len(h) for h in rows) if rows else 0
    out = [" " * width + "  " + " ".join(f"{s[:9]:>9}" for s in short)]
    for head, cells in rows.items():
        if not cells:
            out.append(f"{head:<{width}}  {'will not check out':>9}")
            continue
        marks = " ".join(f"{('ok' if cells[n] == 0 else f'FAIL {cells[n]}'):>9}" for n in names)
        out.append(f"{head:<{width}}  {marks}")
    # `getattr`, because `table` is called with plain ints by anything that builds rows
    # itself, and a cell with no message must read as a cell with nothing to add.
    whys = [
        f"{head} {n.removeprefix('check_')}: {getattr(cells[n], 'why', '')}"
        for head, cells in rows.items()
        for n in names
        if cells.get(n) and getattr(cells[n], "why", "")
    ]
    if whys:
        out.append("")
        out.extend(whys)
    failing = sum(1 for cells in rows.values() if any(cells.values()))
    unmeasured = sum(1 for cells in rows.values() if not cells)
    tally = f"\n{len(rows)} head(s) x {len(names)} gate(s) — {failing} head(s) with a failing gate"
    # A cell has three outcomes and this line reported two, so an unmeasured head landed
    # in the same bucket as a passing one. `len(rows) x len(names)` then reads as a count
    # of cells that were run. Name the third outcome wherever it occurred.
    if unmeasured:
        tally += f", {unmeasured} not measured"
    out.append(tally)
    return "\n".join(out)


def main(argv: list[str]) -> int:
    names, refs = gates(), argv or heads()
    if not refs:
        print("no heads to sweep", file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        tree = Path(tmp) / "head"
        git("worktree", "add", "--detach", str(tree), "HEAD")
        try:
            rows = {ref: run(tree, ref, names) for ref in refs}
        finally:
            git("worktree", "remove", "--force", str(tree))
    print(table(rows, names))
    # A reported cell is the output, so a failing cell is not this tool's verdict — it is
    # the thing the reader was asked to look at. An *unmeasured* cell is the absence of
    # the output, and a sweep where none resolved (a typo'd ref, a worktree that would not
    # add) printed a confident tally and exited 0. Rule on the measuring, not the gates.
    if not any(rows.values()):
        print("nothing was measured: no head resolved", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
