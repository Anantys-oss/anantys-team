#!/usr/bin/env python3
"""The pair selection and the verdict, which is where this sweep reported 51 defects it
had invented.

Both bugs covered here ran against the real queue before they were found, and both
produced a confident table. The verdict called a pair broken without ever asking whether
either head was red on its own, so a harness error that failed every gate everywhere read
as fifty-one silent merge breakages. The selection is the cheaper half and the one that
decides what gets measured at all: an ancestry-ordered pair is not a fork, and pairing a
head with its own ancestor charges a conflict to a merge nobody performs.
"""

import unittest

import gate_drift as gd


class OnlyAForkIsWorthMerging(unittest.TestCase):
    def test_two_heads_with_the_same_blob_are_one_version(self) -> None:
        self.assertEqual(gd.forks({"a": "x", "b": "x"}, lambda *_: False), [])

    def test_differing_heads_with_no_ancestry_are_a_fork(self) -> None:
        self.assertEqual(
            gd.forks({"a": "x", "b": "y"}, lambda *_: False), [("a", "b")]
        )

    def test_a_descendant_already_contains_its_ancestors_edit(self) -> None:
        self.assertEqual(
            gd.forks({"a": "x", "b": "y"}, lambda p, q: (p, q) == ("a", "b")), []
        )

    def test_ancestry_is_checked_in_both_directions(self) -> None:
        self.assertEqual(
            gd.forks({"a": "x", "b": "y"}, lambda p, q: (p, q) == ("b", "a")), []
        )

    def test_one_carrier_forks_with_nobody(self) -> None:
        self.assertEqual(gd.forks({"a": "x"}, lambda *_: False), [])

    def test_three_versions_give_every_unordered_pair_once(self) -> None:
        pairs = gd.forks({"a": "x", "b": "y", "c": "z"}, lambda *_: False)
        self.assertEqual(pairs, [("a", "b"), ("a", "c"), ("b", "c")])


class AVerdictNamesWhatTheMergeDid(unittest.TestCase):
    def test_a_conflicting_gate_is_loud_and_is_not_a_finding(self) -> None:
        self.assertEqual(
            gd.verdict("check_a.py", {"scripts/check_a.py"}, None), "conflict"
        )

    def test_a_gate_merging_under_a_conflicting_test_is_called_out_separately(self) -> None:
        self.assertEqual(
            gd.verdict("check_a.py", {"scripts/test_check_a.py"}, None), "test-conflict"
        )

    def test_the_gates_own_conflict_outranks_its_tests(self) -> None:
        both = {"scripts/check_a.py", "scripts/test_check_a.py"}
        self.assertEqual(gd.verdict("check_a.py", both, None), "conflict")

    def test_a_conflict_in_an_unrelated_file_does_not_excuse_the_gate(self) -> None:
        self.assertEqual(
            gd.verdict("check_a.py", {"README.md"}, True), "broken"
        )

    def test_a_clean_merge_that_still_passes_is_clean(self) -> None:
        self.assertEqual(gd.verdict("check_a.py", set(), False), "clean")

    def test_a_gate_already_red_on_a_head_was_not_broken_by_the_merge(self) -> None:
        self.assertEqual(
            gd.verdict("check_a.py", set(), True, solo=True), "red-alone"
        )

    def test_a_pair_that_repairs_a_red_head_is_still_not_this_tools_finding(self) -> None:
        self.assertEqual(
            gd.verdict("check_a.py", set(), False, solo=True), "red-alone"
        )

    def test_a_tree_with_no_test_module_cannot_be_called_broken(self) -> None:
        self.assertEqual(gd.verdict("check_a.py", set(), None), "clean")


class ConflictsAreReadFromTheMergeNotGuessed(unittest.TestCase):
    def test_a_content_conflict_names_its_path(self) -> None:
        out = "Auto-merging a\nCONFLICT (content): Merge conflict in scripts/check_a.py\n"
        self.assertEqual(gd.CONFLICT.findall(out), ["scripts/check_a.py"])

    def test_a_clean_merge_names_nothing(self) -> None:
        self.assertEqual(gd.CONFLICT.findall("Auto-merging scripts/check_a.py\n"), [])

    def test_a_path_with_spaces_survives_to_the_end_of_the_line(self) -> None:
        out = "CONFLICT (add/add): Merge conflict in docs/a file.md\n"
        self.assertEqual(gd.CONFLICT.findall(out), ["docs/a file.md"])


if __name__ == "__main__":
    unittest.main()
