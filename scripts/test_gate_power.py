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


class Rivals(unittest.TestCase):
    """An outvoted version of a gate is a second opinion, not a second gate."""

    def test_a_rival_version_is_not_counted_as_a_gate(self):
        v = g.verdicts(cells(a=0, **{"a@h": 0}), {"m": cells(a=1)})
        self.assertEqual(v["gates"], ["a"])
        self.assertEqual(v["usable"], ["a"])

    def test_a_rival_asked_of_nothing_is_not_an_inert_gate(self):
        """It was never run on `m`. Absent is unasked, not silent."""
        v = g.verdicts(cells(a=0, **{"a@h": 0}), {"m": cells(a=1)})
        self.assertEqual(v["inert"], [])
        self.assertEqual(v["dupes"], [])

    def test_a_blind_mutation_a_rival_reddens_on_is_rescued_by_name(self):
        v = g.verdicts(cells(a=0, **{"a@h": 0}), {"m": cells(a=0, **{"a@h": 1})})
        self.assertEqual(v["blind"], ["m"])
        self.assertEqual(v["rescued"], {"m": ["a@h"]})

    def test_a_rival_red_on_pristine_main_cannot_rescue(self):
        """Red everywhere is a broken version, not a sharper one."""
        v = g.verdicts(cells(a=0, **{"a@h": 1}), {"m": cells(a=0, **{"a@h": 1})})
        self.assertEqual(v["blind"], ["m"])
        self.assertEqual(v["rescued"], {"m": []})

    def test_a_mutation_the_matrix_catches_gets_no_rescue_entry(self):
        v = g.verdicts(cells(a=0, **{"a@h": 0}), {"m": cells(a=1, **{"a@h": 1})})
        self.assertEqual(v["blind"], [])
        self.assertEqual(v["rescued"], {})

    def test_blind_ignores_a_gate_that_was_already_red_on_main(self):
        """The rival pass must fire on a mutation only a red gate reddened on."""
        self.assertTrue(g.blind(cells(a=1, b=0), cells(a=1, b=0)))
        self.assertFalse(g.blind(cells(a=1, b=0), cells(a=1, b=1)))


class RunRivals(unittest.TestCase):
    """Swapping a version in is a real edit to the tree the sweep is mid-way through."""

    def setUp(self):
        self.tree = Path(tempfile.mkdtemp())
        (self.tree / "scripts").mkdir()
        self.gate = self.tree / "scripts" / "check_x.py"
        self.gate.write_text("import sys\nsys.exit(0)\n")

    def exits(self, code, why):
        return f"import sys\nprint({why!r})\nsys.exit({code})\n".encode()

    def test_each_version_gets_its_own_row_named_for_its_head(self):
        out = g.run_rivals(
            self.tree,
            {"scripts/check_x.py": [("origin/koan/a", self.exits(1, "ERROR a")), ("origin/koan/b", self.exits(0, "ok"))]},
        )
        self.assertEqual(sorted(out), ["check_x@koan/a", "check_x@koan/b"])
        self.assertEqual(out["check_x@koan/a"], (1, "ERROR a"))
        self.assertEqual(out["check_x@koan/b"][0], 0)

    def test_the_selected_version_is_put_back(self):
        """The matrix row for this gate was already recorded from the file on disk;
        leaving a rival in place would silently repoint every later read of it."""
        before = self.gate.read_bytes()
        g.run_rivals(self.tree, {"scripts/check_x.py": [("origin/koan/a", self.exits(1, "ERROR a"))]})
        self.assertEqual(self.gate.read_bytes(), before)

    def test_a_rival_of_a_gate_absent_from_this_tree_is_skipped(self):
        """A head can carry a gate `main` has no counterpart for."""
        self.assertEqual(
            g.run_rivals(self.tree, {"scripts/check_gone.py": [("origin/koan/a", self.exits(1, "x"))]}),
            {},
        )


class MutationTable(unittest.TestCase):
    def test_every_mutation_that_writes_a_version_opts_out_of_the_toll(self):
        """The toll bumps both manifests. A mutation that writes a version too
        would either collide on the anchor or have its subject overwritten."""
        for name, ops in g.MUTATIONS.items():
            if any(old and "version" in old for _, old, _ in ops):
                self.assertIn(name, g.NO_BUMP, name)

    def test_the_absent_grant_mutation_removes_a_field_rather_than_renaming_one(self):
        """A renamed key is an unknown field — a gate may object to that instead,
        and the cell then reads as a catch of a widening nobody checked."""
        (path, old, new), = g.MUTATIONS["absent-grant"]
        self.assertTrue(new.lstrip().startswith("#"), new)
        self.assertEqual(new.replace("#", "").strip(), old.strip())


if __name__ == "__main__":
    unittest.main()
