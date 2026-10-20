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
            mock.patch.object(gm, "run", side_effect=lambda _t, ref, *_: rows[ref]),
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

    def test_the_gate_list_can_be_read_from_somewhere_other_than_root(self) -> None:
        # The assertion above is the reason this one exists: "from the tree" meant
        # *this* tree, and the sweep's instrument is then whichever gates the branch
        # it was launched from happens to carry.
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "scripts").mkdir()
            (Path(tmp) / "scripts" / "check_elsewhere.py").write_text("")
            self.assertEqual(gm.gates(Path(tmp)), ["check_elsewhere"])


class AUnionOverlayIsAssembledNotMerged(unittest.TestCase):
    """`union` builds a gate set from the whole queue instead of from one branch.

    The licence for it is that no file is synthesized: every byte written is some
    head's blob, so a finding is reproducible from the head the provenance names.
    These cover that promise, the newest-wins rule, and the support files whose
    absence inverts two gates' verdicts.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        self._git("init", "--quiet", "--initial-branch=base")
        self._git("config", "user.email", "t@example.com")
        self._git("config", "user.name", "t")
        # Never `head` — on a case-insensitive filesystem it aliases HEAD.
        self._commit(
            "older", {"scripts/check_a.py": "a-from-older\n"}, "2020-01-01T00:00:00+0000"
        )
        self._git("checkout", "--quiet", "-b", "newer", "base")
        self._commit(
            "newer",
            {
                "scripts/check_a.py": "a-from-newer\n",
                "scripts/check_b.py": "b-from-newer\n",
                "scripts/a-baseline.txt": "declared\n",
            },
            "2021-01-01T00:00:00+0000",
        )

    def _git(self, *args: str, when: str | None = None) -> str:
        import os
        import subprocess

        env = dict(os.environ)
        if when:  # `--date` sets only the *author* date; `by_tip_date` reads `%ct`
            env["GIT_COMMITTER_DATE"] = env["GIT_AUTHOR_DATE"] = when
        done = subprocess.run(
            ("git", *args), cwd=self.repo, capture_output=True, text=True, check=False, env=env
        )
        return done.stdout.strip()

    def _commit(self, message: str, files: dict[str, str], when: str) -> None:
        for path, body in files.items():
            target = self.repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body)
        self._git("add", "-A")
        self._git("commit", "--quiet", "-m", message, when=when)

    def _union(self, refs: list[str]) -> tuple[Path, dict[str, str]]:
        into = Path(self.tmp.name) / "union"
        with mock.patch.object(gm, "ROOT", self.repo):
            return into, gm.union(refs, into)

    def test_a_file_only_one_head_carries_is_in_the_union(self) -> None:
        into, held = self._union(["base", "newer"])
        self.assertEqual((into / "scripts" / "check_b.py").read_text(), "b-from-newer\n")
        self.assertEqual(held["scripts/check_b.py"], "newer")

    def test_the_last_ref_wins_a_contested_path(self) -> None:
        into, held = self._union(["base", "newer"])
        self.assertEqual((into / "scripts" / "check_a.py").read_text(), "a-from-newer\n")
        self.assertEqual(held["scripts/check_a.py"], "newer")

    def test_the_caller_orders_the_refs_so_the_earlier_one_can_win(self) -> None:
        into, held = self._union(["newer", "base"])
        self.assertEqual((into / "scripts" / "check_a.py").read_text(), "a-from-older\n")
        self.assertEqual(held["scripts/check_a.py"], "base")

    def test_a_support_file_comes_along_with_its_gate(self) -> None:
        # The defect this flag was built out of: a grants gate is a `.py` plus a
        # `-baseline.txt` it reads relative to its own `__file__`. An assembly that
        # copies only the Python reports that gate's *declared* debt as live errors,
        # and the sweep's finding is then its own harness.
        into, _ = self._union(["base", "newer"])
        self.assertEqual((into / "scripts" / "a-baseline.txt").read_text(), "declared\n")

    def test_every_file_in_the_union_is_some_head_s_blob_verbatim(self) -> None:
        # Not `gate_drift.py`'s merge. Nothing here is synthesized, which is what
        # makes a finding reproducible by checking out the named head.
        into, held = self._union(["base", "newer"])
        for path, ref in held.items():
            with mock.patch.object(gm, "ROOT", self.repo):
                self.assertEqual(
                    (into / path).read_bytes(), gm.git("show", f"{ref}:{path}").encode() + b"\n"
                )

    def test_both_overlay_directories_exist_even_when_no_head_carries_one(self) -> None:
        # `check` copies each `OVERLAY` entry unconditionally; a missing source makes
        # that a silent `cp` failure and the subject keeps its own gates.
        into, _ = self._union(["base", "newer"])
        for name in gm.OVERLAY:
            self.assertTrue((into / name).is_dir(), name)

    def test_tip_dates_order_the_queue_oldest_first(self) -> None:
        with mock.patch.object(gm, "ROOT", self.repo):
            self.assertEqual(gm.by_tip_date(["newer", "base"]), ["base", "newer"])

    def test_a_ref_with_no_resolvable_date_does_not_crash_the_ordering(self) -> None:
        with mock.patch.object(gm, "ROOT", self.repo):
            self.assertEqual(gm.by_tip_date(["newer", "nope"])[0], "nope")


class TheOverlaySourceIsAParameter(unittest.TestCase):
    """`check` and `run` copied from `ROOT`, so `--union` would have changed nothing."""

    def test_check_runs_the_gates_it_was_handed_not_this_branch_s(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            overlay = Path(tmp) / "overlay"
            for name in gm.OVERLAY:
                (overlay / name).mkdir(parents=True)
            (overlay / "scripts" / "check_elsewhere.py").write_text("import sys\nsys.exit(3)\n")
            subject = Path(tmp) / "subject"
            subject.mkdir()
            cells = gm.check(subject, ["check_elsewhere"], overlay)
            self.assertEqual(cells["check_elsewhere"], 3)
            self.assertTrue((subject / "scripts" / "check_elsewhere.py").is_file())

    def test_the_overlay_still_defaults_to_this_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            subject = Path(tmp) / "subject"
            subject.mkdir()
            gm.check(subject, [])
            self.assertTrue((subject / "scripts" / "gate_matrix.py").is_file())


if __name__ == "__main__":
    unittest.main()
