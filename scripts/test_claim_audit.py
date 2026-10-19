#!/usr/bin/env python3
"""Tests for claim_audit.py — extraction, classification and report shape.

The verifiers that shell out to git are exercised through their pure halves:
`verdict_no_bump` takes a diff, `names_foreign_tree` takes the text after a
claim, `report` takes rows. What is left impure is the worktree checkout, and a
test that re-ran it would be testing `unittest` discovering itself.
"""

import io
import unittest

import claim_audit as ca


class ExtractClaims(unittest.TestCase):
    def test_finds_each_kind(self):
        msg = ("Stacked on #78. No version bump — scripts/ is not plugin content.\n"
               "145 tests pass (139 before). Clean against 43 of 46 heads.")
        kinds = [c[0] for c in ca.extract_claims(msg)]
        self.assertEqual(sorted(kinds),
                         ["no-bump", "queue-size", "stacked", "tests"])

    def test_returns_claims_in_message_order(self):
        msg = "No version bump. 12 tests pass. Stacked on #4."
        self.assertEqual([c[0] for c in ca.extract_claims(msg)],
                         ["no-bump", "tests", "stacked"])

    def test_captures_the_numbers(self):
        (kind, text, groups, _), = ca.extract_claims("7 tests pass")
        self.assertEqual((kind, text, groups), ("tests", "7 tests pass", ("7",)))

    def test_queue_size_captures_both_numbers(self):
        (_, _, groups, _), = ca.extract_claims("clean on 43 of 46 heads")
        self.assertEqual(groups, ("43", "46"))

    def test_is_case_insensitive(self):
        self.assertEqual(len(ca.extract_claims("no version bump")), 1)

    def test_every_inflection_of_the_claim_counts(self):
        for text in ("1 test passes", "1 test pass", "4 tests passed"):
            with self.subTest(text=text):
                self.assertEqual(len(ca.extract_claims(text)), 1)

    def test_a_count_of_something_else_is_not_a_test_claim(self):
        self.assertEqual(ca.extract_claims("3 gates pass"), [])

    def test_tail_carries_the_text_after_the_claim(self):
        (_, _, _, tail), = ca.extract_claims("412 tests pass with #59's gates")
        self.assertIn("#59", tail)

    def test_no_claims_in_ordinary_prose(self):
        self.assertEqual(ca.extract_claims("Refactor the loader. See README."), [])


class ForeignTree(unittest.TestCase):
    def test_a_pr_reference_after_the_claim_marks_it_foreign(self):
        self.assertTrue(ca.names_foreign_tree(" with #59's gates applied"))

    def test_an_unqualified_count_is_not_foreign(self):
        self.assertFalse(ca.names_foreign_tree(" (139 before). Pushed."))


class NoBumpVerdict(unittest.TestCase):
    def test_confirmed_when_no_version_line_changes(self):
        diff = '--- a/README.md\n+++ b/README.md\n+a line\n-another\n'
        self.assertEqual(ca.verdict_no_bump(diff)[0], "CONFIRMED")

    def test_false_when_a_version_field_moves(self):
        diff = '-  "version": "0.6.0",\n+  "version": "0.6.1",\n'
        verdict, detail = ca.verdict_no_bump(diff)
        self.assertEqual(verdict, "FALSE")
        self.assertIn("2", detail)

    def test_a_mentioned_version_in_context_is_not_a_change(self):
        diff = '   "version": "0.6.0",\n+  "name": "x",\n'
        self.assertEqual(ca.verdict_no_bump(diff)[0], "CONFIRMED")


class Report(unittest.TestCase):
    rows = [
        ("origin/a", "a" * 40, "tests", "9 tests pass", "CONFIRMED", "9 tests"),
        ("origin/b", "b" * 40, "tests", "9 tests pass", "STALE", "runs 8"),
        ("origin/c", "c" * 40, "tests", "9 tests pass", "FOREIGN-TREE", "no suite"),
    ]

    def render(self, rows):
        out = io.StringIO()
        ca.report(rows, out=out)
        return out.getvalue()

    def test_worst_verdict_comes_first(self):
        text = self.render(self.rows)
        self.assertLess(text.index("STALE"), text.index("FOREIGN-TREE"))
        self.assertLess(text.index("FOREIGN-TREE"), text.index("CONFIRMED"))

    def test_unscored_rows_are_out_of_the_denominator(self):
        self.assertIn("3 claims, 2 re-measurable, 1 still hold.",
                      self.render(self.rows))

    def test_empty_input_says_so(self):
        self.assertIn("No re-measurable claims", self.render([]))

    def test_every_verdict_the_code_emits_has_a_place_in_the_order(self):
        emitted = {"CONFIRMED", "STALE", "FALSE", "FOREIGN-TREE", "DATED",
                   "UNMEASURABLE", "SKIPPED"}
        self.assertEqual(emitted - set(ca.ORDER), set())


if __name__ == "__main__":
    unittest.main()
