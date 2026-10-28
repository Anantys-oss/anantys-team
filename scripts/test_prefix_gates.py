#!/usr/bin/env python3
"""The reduction and the ranking — where a prefix sweep claims more than it measured.

A prefix sweep's whole value is one number per row: how many heads the failure needs. Get
that wrong upwards and the tool invents findings `pair_gates.py` already owns; get it
wrong downwards and it reports a pair that does not reproduce. Both failures look like a
confident table, which is why they are tested here and not read off a live run.
"""

import unittest

import prefix_gates as p


class TheReductionPinsTheTrigger(unittest.TestCase):
    def test_a_lone_cause_reduces_to_one_head_plus_the_trigger(self) -> None:
        # Red iff both `a` and `c` are present. Nine other heads landed first and none
        # of them matters; a sweep that reported all eleven would bury the finding.
        landed = [f"h{i}" for i in range(9)] + ["a", "c"]
        red = lambda refs: "a" in refs and "c" in refs
        self.assertEqual(p.reduce_subset(landed, "c", red), ["a", "c"])

    def test_the_trigger_survives_even_when_dropping_it_stays_red(self) -> None:
        # The trigger is the merge that turned the gate red, so a subset without it is a
        # claim about a tree the walk already measured green. Pinning it is what keeps
        # the row an answer to "what did this merge do".
        self.assertEqual(p.reduce_subset(["a", "b"], "b", lambda refs: True), ["b"])

    def test_a_three_head_cause_does_not_collapse_to_a_pair(self) -> None:
        # The reason this file exists: an additive budget crossed on the third merge has
        # no two-element witness, and reporting one would be unreproducible.
        landed = ["a", "b", "c", "d"]
        red = lambda refs: len({"a", "b", "c"} & set(refs)) == 3
        self.assertEqual(p.reduce_subset(landed, "c", red), ["a", "b", "c"])

    def test_a_subset_that_will_not_merge_keeps_the_ref(self) -> None:
        # `still_red` answers False for a conflicting subset, which is indistinguishable
        # from green. The reduction must then keep the ref, so the size is a ceiling.
        landed = ["a", "b", "c"]
        self.assertEqual(p.reduce_subset(landed, "c", lambda refs: False), landed)

    def test_a_single_landed_head_is_never_emptied(self) -> None:
        self.assertEqual(p.reduce_subset(["a"], "a", lambda refs: True), ["a"])


class TheReportRanksByWhatNothingElseCanSee(unittest.TestCase):
    def test_a_three_head_subset_leads_and_says_the_size_is_a_ceiling(self) -> None:
        out = p.report(
            [{"gate": "check_plugins", "k": 7, "ref": "c", "alone": False,
              "subset": ["a", "b", "c"]}],
            ["a", "b", "c"], [], {},
        )
        self.assertIn("three or more heads", out.splitlines()[0])
        self.assertIn("(3 heads, a ceiling)", out)
        self.assertIn("first red at merge 7", out)

    def test_a_pair_sized_subset_is_credited_to_pair_gates(self) -> None:
        out = p.report(
            [{"gate": "check_plugins", "k": 4, "ref": "b", "alone": False,
              "subset": ["a", "b"]}],
            ["a", "b"], [], {},
        )
        self.assertIn("no gate needed three or more heads together", out)
        self.assertIn("`pair_gates.py` owns these rows", out)
        self.assertIn("a + b", out)

    def test_a_head_red_alone_is_credited_to_gate_matrix(self) -> None:
        out = p.report(
            [{"gate": "check_tool_grants", "k": 2, "ref": "b", "alone": True, "subset": ["b"]}],
            ["a", "b"], [], {},
        )
        self.assertIn("`gate_matrix.py`'s rows: tool_grants", out)
        self.assertNotIn("pair_gates.py` owns", out)

    def test_a_green_sweep_names_the_gates_that_could_not_speak(self) -> None:
        # The failure `pair_gates.py` was fixed for, in a new place: five of fourteen
        # gates here are red on `main` or cannot import, and a report that omits them
        # reads as fourteen gates clearing the queue.
        out = p.report(
            [], ["a"], ["b"],
            {"check_doc_actions": "red on main", "check_plugin_agents": "cannot run"},
        )
        self.assertIn("1 head(s) landed, 1 would not merge", out)
        self.assertIn("doc_actions (red on main)", out)
        self.assertIn("plugin_agents (cannot run)", out)

    def test_an_unexcluded_sweep_claims_no_blind_gates(self) -> None:
        out = p.report([], ["a"], [], {})
        self.assertNotIn("excluded", out)


if __name__ == "__main__":
    unittest.main()
