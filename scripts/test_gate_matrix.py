#!/usr/bin/env python3
"""The reporting half, which is where a sweep quietly lies.

The first run of this sweep by hand reported every one of 315 cells green. The bug was
in the recording, not the gates: the exit code was read after a command substitution had
already reset it, so each cell stored the formatting step's status. A sweep that cannot
distinguish "passed" from "was not measured" is worse than no sweep, so those two
outcomes are what these cover.
"""

import unittest

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


class TheGateListComesFromTheTree(unittest.TestCase):
    def test_every_checker_in_scripts_is_swept(self) -> None:
        # The sweep must not carry its own hand-written list of gates: a gate added on
        # another branch and overlaid here would be silently skipped.
        found = gm.gates()
        self.assertIn("check_plugins", found)
        self.assertTrue(all(n.startswith("check_") for n in found))


if __name__ == "__main__":
    unittest.main()
