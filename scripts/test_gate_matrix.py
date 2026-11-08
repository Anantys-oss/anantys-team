#!/usr/bin/env python3
"""The reporting half, which is where a sweep quietly lies.

The first run of this sweep by hand reported every one of 315 cells green. The bug was
in the recording, not the gates: the exit code was read after a command substitution had
already reset it, so each cell stored the formatting step's status. A sweep that cannot
distinguish "passed" from "was not measured" is worse than no sweep, so those two
outcomes are what these cover.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import gate_matrix as gm


class ACellSaysWhichOfThreeThingsHappened(unittest.TestCase):
    NAMES = ["check_a", "check_b"]

    def test_a_passing_head_reads_ok(self) -> None:
        out = gm.table({"origin/koan/x": {"check_a": 0, "check_b": 0}}, self.NAMES)
        self.assertEqual(out.count("ok"), 2)
        self.assertNotIn("FAIL", out)

    def test_a_failing_gate_reports_its_exit_code(self) -> None:
        out = gm.table({"origin/koan/x": {"check_a": 0, "check_b": 1}}, self.NAMES)
        self.assertIn("FAIL 1", out)

    def test_an_unmeasured_head_is_not_reported_as_passing(self) -> None:
        # The empty dict is `run`'s "would not check out". Printing it as a row of
        # blanks is how a sweep claims a green it never ran.
        out = gm.table({"origin/koan/x": {}}, self.NAMES)
        self.assertIn("will not check out", out)
        self.assertNotIn("ok", out)

    def test_the_tally_counts_heads_not_cells(self) -> None:
        out = gm.table(
            {
                "origin/koan/x": {"check_a": 1, "check_b": 1},
                "origin/koan/y": {"check_a": 0, "check_b": 0},
            },
            self.NAMES,
        )
        self.assertIn("2 head(s) x 2 gate(s) — 1 head(s) with a failing gate", out)

    def test_a_head_that_only_failed_to_check_out_is_not_counted_as_failing(self) -> None:
        out = gm.table({"origin/koan/x": {}}, self.NAMES)
        self.assertIn("0 head(s) with a failing gate", out)

    def test_the_tally_names_the_heads_it_could_not_measure(self) -> None:
        # The assertion above is correct and used to be the whole tally: an unmeasured
        # head is not a failing one. It is also not a passing one, and "1 head(s) x 2
        # gate(s) — 0 head(s) with a failing gate" is what a reader quotes as a sweep.
        out = gm.table({"origin/koan/x": {}}, self.NAMES)
        self.assertIn("1 not measured", out)

    def test_a_measured_sweep_does_not_mention_measuring(self) -> None:
        out = gm.table({"origin/koan/x": {"check_a": 0, "check_b": 1}}, self.NAMES)
        self.assertNotIn("not measured", out)


class AFailingCellCarriesItsFinding(unittest.TestCase):
    """A coordinate is not a finding, and the overlay is what makes re-reading costly."""

    NAMES = ["check_a", "check_b"]

    def test_the_message_is_printed_with_its_head_and_gate(self) -> None:
        out = gm.table(
            {"origin/koan/x": {"check_a": gm.Cell(0), "check_b": gm.Cell(1, "error: too big")}},
            self.NAMES,
        )
        self.assertIn("origin/koan/x b: error: too big", out)

    def test_a_passing_cell_contributes_no_message(self) -> None:
        # A gate is allowed to print on its way to exit 0, and a clean cell with a
        # line under it reads as a failure the table marked `ok`.
        out = gm.table({"origin/koan/x": {"check_a": gm.Cell(0, "error: stale")}}, ["check_a"])
        self.assertNotIn("stale", out)

    def test_plain_int_rows_still_render(self) -> None:
        # Every other test in this file builds rows by hand out of `int`.
        out = gm.table({"origin/koan/x": {"check_a": 1}}, ["check_a"])
        self.assertIn("FAIL 1", out)

    def test_the_first_error_line_is_the_finding(self) -> None:
        stdout = "warning: cosmetic\nerror: a: the real one\nerror: b: the second\n"
        self.assertEqual(gm.finding(stdout, ""), "error: a: the real one")

    def test_an_uppercase_prefix_is_matched_too(self) -> None:
        # `check_mcp_grants` writes `ERROR `, `check_platform` writes `error:`.
        self.assertEqual(gm.finding("ERROR path: nope\n", ""), "ERROR path: nope")

    def test_a_finding_on_stderr_is_found(self) -> None:
        # `check_version_bump`'s live shape: the changed files land on stdout and the
        # finding on stderr. Reading only stdout returns a path and no sentence.
        out = "plugins/anantys-team-agents/skills/anantys.review/SKILL.md\n"
        err = "error: anantys-team-agents: version is still 0.6.0\n1 error(s)\n"
        self.assertEqual(gm.finding(out, err), "error: anantys-team-agents: version is still 0.6.0")

    def test_a_gate_that_raises_reports_its_exception(self) -> None:
        # No `error:` line exists, and the sweep's own docstring calls a gate that
        # raises a finding of its own — so the exception is what must survive.
        err = 'Traceback (most recent call last):\n  File "x", line 1\nKeyError: \'tools\'\n'
        self.assertEqual(gm.finding("", err), "KeyError: 'tools'")

    def test_a_silent_failure_yields_no_message_rather_than_a_guess(self) -> None:
        self.assertEqual(gm.finding("", ""), "")


class TheSweepRulesOnlyOnItsOwnMeasuring(unittest.TestCase):
    """`main`'s exit code, which is about the sweep and never about the gates."""

    def test_a_failing_gate_is_reported_not_ruled_on(self) -> None:
        with mock.patch.object(gm, "table", return_value=""):
            self.assertEqual(self._main_over({"origin/koan/x": {"check_a": 1}}), 0)

    def test_a_sweep_where_no_head_resolved_exits_nonzero(self) -> None:
        # Two unresolvable refs printed a confident tally and exited 0. A sweep that
        # measured nothing has produced no report, so it has nothing to be silent about.
        with mock.patch.object(gm, "table", return_value=""):
            self.assertEqual(self._main_over({"origin/koan/typo": {}}), 1)

    def test_one_measured_head_is_enough_to_have_measured(self) -> None:
        with mock.patch.object(gm, "table", return_value=""):
            rows = {"origin/koan/typo": {}, "origin/koan/x": {"check_a": 0}}
            self.assertEqual(self._main_over(rows), 0)

    def test_no_heads_at_all_exits_nonzero(self) -> None:
        with mock.patch.object(gm, "heads", return_value=[]):
            self.assertEqual(gm.main([]), 1)

    @staticmethod
    def _main_over(rows: dict[str, dict[str, int]]) -> int:
        """`main` with the git work replaced, so only the verdict is under test."""
        with (
            mock.patch.object(gm, "git", return_value=""),
            mock.patch.object(gm, "gates", return_value=["check_a"]),
            mock.patch.object(gm, "run", side_effect=lambda _t, ref, _n: rows[ref]),
        ):
            return gm.main(list(rows))


class RunIsTheSeamThatTalksToGit(unittest.TestCase):
    """`run` and `heads` were the two untested functions, and both shell out.

    `table` is pure and was covered exhaustively, which is exactly why nothing asked
    whether the dict it formats is the one git produced. The "will not check out"
    sentinel in particular is an empty dict that only `run` can return.
    """

    def test_a_ref_that_does_not_resolve_yields_the_unmeasured_sentinel(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp) / "head"
            gm.git("worktree", "add", "--detach", str(tree), "HEAD")
            try:
                cells = gm.run(tree, "refs/remotes/origin/koan/no-such-head", ["check_a"])
            finally:
                gm.git("worktree", "remove", "--force", str(tree))
        self.assertEqual(cells, {})

    def test_this_repos_own_head_resolves_and_scores_every_gate(self) -> None:
        names = gm.gates()
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp) / "head"
            gm.git("worktree", "add", "--detach", str(tree), "HEAD")
            try:
                cells = gm.run(tree, "HEAD", names)
            finally:
                gm.git("worktree", "remove", "--force", str(tree))
        self.assertEqual(sorted(cells), sorted(names))
        self.assertTrue(all(isinstance(code, int) for code in cells.values()))

    def test_no_gate_rules_on_the_invocation_rather_than_the_head(self) -> None:
        """A cell must report the head's content, never this tool's command line.

        The gates do not agree on what a positional *means* — four read a root, one
        reads a base ref, three read none — so the `"."` this once passed to all of
        them was the tree to some and the unresolvable ref `.` to `check_version_bump`.
        The overlay roots every gate twice already: `cwd` is the head and these scripts
        were copied into it. A refusal message in a cell means the argument came back.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp) / "head"
            gm.git("worktree", "add", "--detach", str(tree), "HEAD")
            try:
                cells = gm.run(tree, "HEAD", gm.gates())
            finally:
                gm.git("worktree", "remove", "--force", str(tree))
        for gate, cell in cells.items():
            for refusal in ("unrecognised argument", "cannot be pointed at", "no commit"):
                self.assertNotIn(refusal, cell.why, f"{gate} ruled on its argument")


class HeadsComeFromTheRepositoryNotFromANamingConvention(unittest.TestCase):
    def test_the_sweep_is_not_restricted_to_one_branch_prefix(self) -> None:
        # `refs/remotes/origin/koan/*` is where the queue happens to live. A head that
        # will land and is spelled otherwise was reported as nothing at all.
        found = gm.heads()
        outside = gm.git(
            "for-each-ref", "--format=%(refname:short)", "refs/remotes/origin/**"
        ).splitlines()
        outside = [r for r in outside if r and r != "origin" and not r.startswith("origin/koan/")]
        if not outside:  # nothing is spelled otherwise here, so nothing to assert
            self.skipTest("every refs/remotes/origin/** ref is under origin/koan/")
        self.assertTrue(all(r.startswith("origin/") for r in found))
        self.assertNotIn("origin", found)  # origin/HEAD, which is a symref to a row
        for ref in outside:
            self.assertIn(ref, found)


class TheGateListComesFromTheTree(unittest.TestCase):
    def test_every_checker_in_scripts_is_swept(self) -> None:
        # The sweep must not carry its own hand-written list of gates: a gate added on
        # another branch and overlaid here would be silently skipped.
        found = gm.gates()
        self.assertIn("check_plugins", found)
        self.assertTrue(all(n.startswith("check_") for n in found))


if __name__ == "__main__":
    unittest.main()
