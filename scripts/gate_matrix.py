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
    python3 scripts/gate_matrix.py --union                # with the queue's whole gate set

The gates are overlaid onto each head, so what is measured is the head's *content*
against this branch's checkers — not whatever checkers the head happens to carry.

`--union` moves that overlay off this branch. The sentence above holds the blind
spot one level up: *this branch's* checkers are 19 of the queue's 22 tools, because
each tool arrived on its own branch too. See `union`.
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


def gates(overlay: Path = ROOT) -> list[str]:
    return sorted(p.stem for p in (overlay / "scripts").glob("check_*.py"))


def union(refs: list[str], into: Path) -> dict[str, str]:
    """Assemble every head's newest copy of the overlay into `into`. Returns provenance.

    `gates()` reads `ROOT`, so a sweep's instrument is whatever the branch it was
    launched from happens to carry. That is the same blind spot this file opens by
    naming, one level up: a gate pointed only at the work it was written from can
    only confirm that work, and a *gate set* assembled from one branch can only ask
    that branch's questions. Measured over 87 open heads, the richest single head
    carried 19 of the queue's 22 tools; `check_evals.py`, `claim_audit.py` and
    `fold_absorbs.py` live on three others, so no sweep launched from anywhere could
    run them. `origin/main` carries none, which is `heads()`'s point about the cell
    CI never fills, repeated about the instrument instead of the subject.

    **Newest wins, by the carrying head's tip date.** Approximate on purpose: the
    exact answer is the commit that last touched each path on each head, which is a
    `git log` per path per head. The tip date is one call per head and orders the
    queue the way a reader does.

    **This is not `gate_drift.py`'s merge, and the difference is the whole licence
    for it.** That tool objects — rightly — that merging diverged copies of a gate
    "produces a `check_plugins.py` that no author wrote, reviewed, or ran". Nothing
    here is merged. Every file written is one head's blob, byte for byte, so the
    *tree* is new and no *file* in it is. A finding from this overlay is reproducible
    by checking out the head the provenance names.

    **Every file, not just `check_*.py`.** A grants gate is a `.py` and a
    `-baseline.txt` that declares the errors predating it, and the gate reads that
    ledger relative to its own `__file__`. An assembly that copies only the Python
    drops the ledger, at which point `check_mcp_grants` and `check_tool_grants`
    report their *declared* debt as live errors — a sweep built that way called both
    red on `main` and on all 87 heads, and the finding was the harness. `.github`
    comes along for the reason `OVERLAY` already says.
    """
    provenance: dict[str, str] = {}
    for ref in refs:  # oldest tip first, so a newer head overwrites
        listing = git("ls-tree", "-r", "--name-only", ref, *OVERLAY)
        for path in listing.splitlines():
            if not path or "__pycache__" in path:
                continue
            blob = subprocess.run(
                ("git", "show", f"{ref}:{path}"), cwd=ROOT, capture_output=True, check=False
            )
            if blob.returncode:
                continue
            target = into / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(blob.stdout)
            provenance[path] = ref
    for name in OVERLAY:  # `check` copies each one unconditionally
        (into / name).mkdir(parents=True, exist_ok=True)
    return provenance


def by_tip_date(refs: list[str]) -> list[str]:
    """`refs` oldest tip first. A ref with no resolvable date sorts first, not last."""
    return sorted(refs, key=lambda r: int(git("log", "-1", "--format=%ct", r) or 0))


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


def check(tree: Path, names: list[str], overlay: Path = ROOT) -> dict[str, Cell]:
    """Overlay these gates onto whatever `tree` currently holds, and run them there.

    Split out of `run` so a caller that builds its subject some other way than a
    checkout gets the same instrument. `pair_gates.py` assembles its tree with two
    merges, and a second copy of the overlay-then-run dance is a second place for the
    exit code to be read wrong — which is the one bug this sweep has already had.

    `overlay` is where the gate set is copied *from*, and it is a parameter because
    `ROOT` is one branch's answer to a question about the queue. See `union`.
    """
    for name in OVERLAY:  # the subject's own copies lose to ours, on purpose
        subprocess.run(("rm", "-rf", str(tree / name)), check=False)
        subprocess.run(("cp", "-R", str(overlay / name), str(tree / name)), check=False)
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


def run(tree: Path, head: str, names: list[str], overlay: Path = ROOT) -> dict[str, Cell]:
    """Exit code per gate for one head's content. Empty when the head will not check out."""
    for name in OVERLAY:  # a head that tracks these would conflict with the checkout
        subprocess.run(("rm", "-rf", str(tree / name)), check=False)
    if subprocess.run(
        ("git", "checkout", "--detach", head, "--quiet"), cwd=tree, capture_output=True
    ).returncode:
        return {}
    git("checkout", "--", ".", cwd=tree)
    return check(tree, names, overlay)


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
    pooled = "--union" in argv
    refs = [a for a in argv if a != "--union"] or heads()
    if not refs:
        print("no heads to sweep", file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        tree = Path(tmp) / "head"
        overlay = ROOT
        if pooled:
            overlay = Path(tmp) / "union"
            held = union(by_tip_date(heads()), overlay)
            print(f"union overlay: {len(held)} file(s), {len(gates(overlay))} gate(s)")
            for path, ref in sorted(held.items()):
                if path.startswith("scripts/") and not Path(path).name.startswith("test_"):
                    print(f"  {path} <- {ref}")
            print()
        names = gates(overlay)
        git("worktree", "add", "--detach", str(tree), "HEAD")
        try:
            rows = {ref: run(tree, ref, names, overlay) for ref in refs}
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
