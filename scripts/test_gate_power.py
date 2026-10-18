#!/usr/bin/env python3
"""Fixture tests for gate_power — run: python3 -m unittest discover scripts"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import gate_power as g  # noqa: E402


def cells(**kw):
    """`{gate: (code, why)}` from `{gate: code}`."""
    return {k: (v, "why" if v else "") for k, v in kw.items()}


class Verdicts(unittest.TestCase):
    def test_a_gate_green_on_main_and_red_on_a_mutation_catches_it(self):
        v = g.verdicts(cells(a=0), {"m": cells(a=1)})
        self.assertEqual(v["caught"], {"a": ["m"]})

    def test_a_gate_red_on_main_is_unassessable_not_inert(self):
        """It was never asked, so counting it as catching nothing would read as
        a finding about the gate rather than about the tree it starts red on."""
        v = g.verdicts(cells(a=1), {"m": cells(a=1)})
        self.assertEqual(v["usable"], [])
        self.assertEqual(v["inert"], [])

    def test_a_mutation_only_a_red_gate_reddens_on_is_still_blind(self):
        v = g.verdicts(cells(a=1, b=0), {"m": cells(a=1, b=0)})
        self.assertEqual(v["blind"], ["m"])

    def test_a_mutation_a_green_gate_catches_is_not_blind(self):
        v = g.verdicts(cells(a=0), {"m": cells(a=1)})
        self.assertEqual(v["blind"], [])

    def test_identical_catch_sets_are_reported_once_as_a_pair(self):
        v = g.verdicts(cells(a=0, b=0), {"m": cells(a=1, b=1)})
        self.assertEqual(v["dupes"], [("a", "b")])

    def test_two_gates_that_catch_nothing_are_not_duplicates(self):
        """Empty catch-sets match each other trivially; that is the inert
        finding, and reporting it as redundancy would recommend a deletion the
        matrix has no evidence for."""
        v = g.verdicts(cells(a=0, b=0), {"m": cells(a=0, b=0)})
        self.assertEqual(v["dupes"], [])
        self.assertEqual(v["inert"], ["a", "b"])

    def test_a_subset_catch_set_is_subsumed(self):
        runs = {"m": cells(a=1, b=1), "n": cells(a=0, b=1)}
        v = g.verdicts(cells(a=0, b=0), runs)
        self.assertEqual(v["subsumed"], [("a", "b")])

    def test_equal_catch_sets_are_not_subsumed_in_either_direction(self):
        v = g.verdicts(cells(a=0, b=0), {"m": cells(a=1, b=1)})
        self.assertEqual(v["subsumed"], [])

    def test_a_timeout_counts_as_red(self):
        v = g.verdicts(cells(a=0), {"m": {"a": (124, "timed out")}})
        self.assertEqual(v["caught"], {"a": ["m"]})


class Finding(unittest.TestCase):
    def test_the_first_error_line_wins_over_later_noise(self):
        out = "reading tree\nerror: version drift\nerror: second thing\n"
        self.assertEqual(g.finding(out), "error: version drift")

    def test_a_traceback_falls_back_to_the_line_it_died_on(self):
        out = "Traceback (most recent call last):\n  File x\nKeyError: 'name'\n"
        self.assertEqual(g.finding(out), "KeyError: 'name'")

    def test_a_gate_that_prints_nothing_says_so(self):
        self.assertEqual(g.finding(""), "(silent)")


class Apply(unittest.TestCase):
    def setUp(self):
        self.tree = Path(tempfile.mkdtemp(prefix="koan-gp-test-"))
        (self.tree / "f.md").write_text("one two one\n")

    def test_a_replacement_hits_the_first_occurrence_only(self):
        g.apply(self.tree, [("f.md", "one", "ONE")])
        self.assertEqual((self.tree / "f.md").read_text(), "ONE two one\n")

    def test_a_missing_anchor_is_fatal_not_a_silent_no_op(self):
        """A mutation that applied nothing would be recorded as caught by no
        gate — a blind spot invented by a typo in its own anchor."""
        with self.assertRaises(SystemExit):
            g.apply(self.tree, [("f.md", "absent", "x")])

    def test_a_none_old_appends(self):
        g.apply(self.tree, [("f.md", None, "three\n")])
        self.assertEqual((self.tree / "f.md").read_text(), "one two one\nthree\n")

    def test_a_none_new_deletes(self):
        g.apply(self.tree, [("f.md", None, None)])
        self.assertFalse((self.tree / "f.md").exists())


class MutationTable(unittest.TestCase):
    def test_every_mutation_that_writes_a_version_opts_out_of_the_toll(self):
        """The toll bumps both manifests. A mutation that writes a version too
        would either collide on the anchor or have its subject overwritten."""
        for name, ops in g.MUTATIONS.items():
            if any(old and "version" in old for _, old, _ in ops):
                self.assertIn(name, g.NO_BUMP, name)


if __name__ == "__main__":
    unittest.main()
