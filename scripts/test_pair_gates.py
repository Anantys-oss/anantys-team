#!/usr/bin/env python3
"""The selection and the subtraction, which is where a pair sweep reports the wrong thing.

Both bugs these cover were in the sweep's first run, not hypothetical. The subtraction
ran per head, so two queue-wide red gates vetoed all 9 heads it had measured and the
tool printed a clean bill over zero comparisons. The selection paired fold branches with
their own contents, which is a merge nobody performs.
"""

import unittest

import gate_matrix as gm
import pair_gates as pg


class TheSubtractionIsPerGateNotPerHead(unittest.TestCase):
    def test_a_gate_red_on_the_pair_and_green_apart_is_reported(self) -> None:
        self.assertEqual(pg.pair_only(set(), set(), {"check_plugins"}), {"check_plugins"})

    def test_a_gate_red_on_a_head_alone_is_not_this_tools_finding(self) -> None:
        self.assertEqual(pg.pair_only({"check_plugins"}, set(), {"check_plugins"}), set())

    def test_an_unrelated_red_gate_does_not_veto_the_whole_head(self) -> None:
        # `check_doc_actions` is red on 76 of 78 heads here. Letting it hide a real
        # `check_plugins` pair failure is the bug that made the first sweep vacuous.
        self.assertEqual(
            pg.pair_only(
                {"check_doc_actions"},
                {"check_doc_actions", "check_version_bump"},
                {"check_doc_actions", "check_version_bump", "check_plugins"},
            ),
            {"check_plugins"},
        )

    def test_a_pair_greener_than_its_heads_reports_nothing(self) -> None:
        self.assertEqual(pg.pair_only({"check_plugins"}, {"check_plugins"}, set()), set())


class AFoldIsWideNotMerelyContaining(unittest.TestCase):
    def test_a_head_touching_most_of_the_universe_is_a_fold(self) -> None:
        sets = {"fold": {"a", "b", "c"}, "x": {"a"}, "y": {"b"}, "z": {"d"}}
        self.assertEqual(pg.folds(sets, 0.5), {"fold"})  # 3 of 4 files

    def test_containing_three_singletons_is_not_enough(self) -> None:
        # The bug this replaced: in a queue where every head edits one of six role
        # files, a two-file PR contains three one-file PRs by accident. That criterion
        # dropped 25 of 48 open heads, two-file ones included.
        sets = {"small": {"a", "b"}, "x": {"a"}, "y": {"b"}, "z": {"c"}, "w": {"d"}, "v": {"e"}}
        self.assertEqual(pg.folds(sets, 0.4), set())  # contains three, but 2 of 5 files

    def test_identical_write_sets_are_both_kept(self) -> None:
        # Two heads editing exactly one same file are the pair most worth measuring.
        sets = {"a": {"f"}, "b": {"f"}, "c": {"g"}, "d": {"h"}}
        self.assertEqual(pg.folds(sets, 0.4), set())

    def test_an_empty_write_set_is_never_a_fold(self) -> None:
        sets = {"big": {"a", "b", "c"}, "empty": set(), "x": {"a"}}
        self.assertEqual(pg.folds(sets, 0.5), {"big"})

    def test_an_empty_queue_names_no_folds_instead_of_dividing_by_it(self) -> None:
        self.assertEqual(pg.folds({}, 0.4), set())
        self.assertEqual(pg.folds({"a": set()}, 0.4), set())


class TheTalliesSayWhatWasNotMeasured(unittest.TestCase):
    def test_a_conflicting_pair_is_not_counted_as_assembled(self) -> None:
        out = pg.report({}, {("a", "b"): ("conflict merging b", {}, {"f"})})
        self.assertIn("1 pair(s) selected — 0 assembled, 1 would not merge", out)

    def test_a_green_sweep_names_the_gates_that_could_not_speak(self) -> None:
        # The claim "no pair-only failure" is worth less when two of nine gates were
        # already red on every head, and a reader cannot tell from the verdict alone.
        out = pg.report(
            {"a": {"check_doc_actions"}, "b": {"check_doc_actions"}},
            {("a", "b"): ("", {"check_doc_actions": gm.Cell(1, "stale")}, {"f"})},
        )
        self.assertIn("no gate is red on a pair", out)
        self.assertIn("doc_actions (2/2 heads)", out)

    def test_a_pair_only_failure_names_the_shared_file_and_the_finding(self) -> None:
        out = pg.report(
            {"a": set(), "b": set()},
            {("a", "b"): ("", {"check_plugins": gm.Cell(1, "error: 12300 tokens")}, {"x/y.md"})},
        )
        self.assertIn("shares: x/y.md", out)
        self.assertIn("plugins: error: 12300 tokens", out)
        self.assertIn("1 with a pair-only failure", out)

    def test_an_all_green_sweep_mentions_no_blind_gates(self) -> None:
        out = pg.report({"a": set(), "b": set()}, {("a", "b"): ("", {"check_a": gm.Cell(0)}, {"f"})})
        self.assertNotIn("already red alone", out)


class TheVersionHomesAreExcludedFromSelectionOnly(unittest.TestCase):
    def test_both_manifests_are_named(self) -> None:
        # Two files, one field. The pair selection would otherwise be dominated by it:
        # 903 and 990 of 1371 overlapping pairs here overlap only on these.
        self.assertEqual(len(pg.VERSION_HOMES), 2)
        self.assertTrue(all(h.endswith(".json") for h in pg.VERSION_HOMES))


if __name__ == "__main__":
    unittest.main()
