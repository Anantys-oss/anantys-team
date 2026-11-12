#!/usr/bin/env python3
"""The reduction, the ranking, and the denominator — where a prefix sweep over-claims.

A prefix sweep's whole value is one number per row: how many heads the failure needs. Get
that wrong upwards and the tool invents findings `pair_gates.py` already owns; get it
wrong downwards and it reports a pair that does not reproduce. Both failures look like a
confident table, which is why they are tested here and not read off a live run.

The third over-claim is the denominator, and the first version of this file did not cover
it: *which heads were offered at all*. The reduction and the ranking were exhaustively
tested and `landing_order` was not, which is how a pair-selection filter survived inside
a landing order and quietly removed a quarter of the queue before the walk began.
"""

import unittest
from collections import Counter

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


class TheHistogramSeparatesAppearingFromBeingAlone(unittest.TestCase):
    def test_a_file_alone_in_a_stop_is_counted_in_both_columns(self) -> None:
        rows = p.by_file(Counter({("qa.md",): 26, ("qa.md", "plan.md"): 7}))
        self.assertEqual(rows[0], ("qa.md", 33, 26))
        self.assertEqual(rows[1], ("plan.md", 7, 0))

    def test_a_file_never_alone_reports_zero_in_the_alone_column(self) -> None:
        # The manifests, measured: in 4 stops here and alone in none of them. A single
        # column would have reported them as a landing cost of 4 and hidden that every
        # one of those stops needed a different decision made first.
        rows = p.by_file(Counter({("marketplace.json", "plugin.json", "qa.md"): 4}))
        self.assertEqual([(f, n, a) for f, n, a in rows if f.endswith(".json")],
                         [("marketplace.json", 4, 0), ("plugin.json", 4, 0)])

    def test_no_stops_produce_no_rows(self) -> None:
        self.assertEqual(p.by_file(Counter()), [])

    def test_a_nameless_stop_stays_in_the_table(self) -> None:
        # 13 of the first run's 72 stops named no file, and every one was the overlay
        # this tool left in the tree. Smoothing the row away would have hidden the
        # harness bug behind a plausible queue number.
        self.assertEqual(p.by_file(Counter({("<no file named>",): 13})),
                         [("<no file named>", 13, 13)])


class TheReportRanksByWhatNothingElseCanSee(unittest.TestCase):
    def test_a_three_head_subset_leads_and_says_the_size_is_a_ceiling(self) -> None:
        out = p.report(
            [{"gate": "check_plugins", "k": 7, "ref": "c", "alone": False,
              "subset": ["a", "b", "c"]}],
            ["a", "b", "c"], Counter(), {},
        )
        self.assertIn("three or more heads", out.splitlines()[0])
        self.assertIn("(3 heads, a ceiling)", out)
        self.assertIn("first red at merge 7", out)

    def test_a_pair_sized_subset_is_credited_to_pair_gates(self) -> None:
        out = p.report(
            [{"gate": "check_plugins", "k": 4, "ref": "b", "alone": False,
              "subset": ["a", "b"]}],
            ["a", "b"], Counter(), {},
        )
        self.assertIn("no gate needed three or more heads together", out)
        self.assertIn("`pair_gates.py` owns these rows", out)
        self.assertIn("a + b", out)

    def test_a_head_red_alone_is_credited_to_gate_matrix(self) -> None:
        out = p.report(
            [{"gate": "check_tool_grants", "k": 2, "ref": "b", "alone": True, "subset": ["b"]}],
            ["a", "b"], Counter(), {},
        )
        self.assertIn("`gate_matrix.py`'s rows: tool_grants", out)
        self.assertNotIn("pair_gates.py` owns", out)

    def test_the_reach_is_stated_against_what_was_offered(self) -> None:
        # The measured run: 20 of 89. Printing "no three-head failure" without this is
        # claiming the queue composes when 69 of its heads never entered a prefix.
        out = p.report([], ["a"] * 20, Counter({("qa.md",): 69}), {}, 89)
        self.assertIn("reach: 20 merge(s) deep of 89 head(s) offered", out)
        self.assertIn("69 stopped on a conflict, so no verdict covers them", out)
        self.assertIn("69 ( 69)  qa.md", out)

    def test_a_green_sweep_names_the_gates_that_could_not_speak(self) -> None:
        # The failure `pair_gates.py` was fixed for, in a new place: five of fourteen
        # gates here are red on `main` or cannot import, and a report that omits them
        # reads as fourteen gates clearing the queue.
        out = p.report(
            [], ["a"], Counter({("x.md",): 1}),
            {"check_doc_actions": "red on main", "check_plugin_agents": "cannot run"},
        )
        self.assertIn("doc_actions (red on main)", out)
        self.assertIn("plugin_agents (cannot run)", out)

    def test_an_unexcluded_sweep_claims_no_blind_gates(self) -> None:
        out = p.report([], ["a"], Counter(), {})
        self.assertNotIn("excluded", out)
        self.assertNotIn("where the queue stops", out)


class TheOrderOffersTheWholeQueue(unittest.TestCase):
    """`landing_order`, with the two shell calls it makes replaced.

    Both substitutions are the functions whose *answers* the ordering depends on, not
    the ordering itself, so what is under test is the selection rule and nothing else.
    """

    def order(self, writes: dict[str, set[str]], fold_share: float = 0.4):
        saved = (p.pg.open_heads, p.pg.writes, p.gm.by_tip_date)
        p.pg.open_heads = lambda: {h: i for i, h in enumerate(writes)}
        p.pg.writes = lambda head, share: writes[head]
        p.gm.by_tip_date = sorted
        try:
            return p.landing_order("plugins", fold_share)
        finally:
            p.pg.open_heads, p.pg.writes, p.gm.by_tip_date = saved

    def test_a_head_writing_nothing_under_share_is_still_offered(self) -> None:
        # The defect: 32 of 132 open heads write only under `scripts/`, `.github/` and
        # `docs/`, and every one was dropped before the walk. They are the heads that
        # carry the gates — including the two defect shapes this file exists for.
        writes = {"gate-only": set(), "r1": {"a.md"}, "r2": {"b.md"}, "r3": {"c.md"}}
        order, _ = self.order(writes)
        self.assertEqual(order, ["gate-only", "r1", "r2", "r3"])

    def test_a_fold_is_still_dropped(self) -> None:
        # The one exclusion a landing order has an argument for: a fold contains its
        # siblings, so landing it *and* them is not an order anyone performs.
        wide = {f"f{i}" for i in range(9)}
        order, _ = self.order({"fold": wide, "a": {"f0"}, "b": {"f1"}})
        self.assertEqual(order, ["a", "b"])

    def test_an_empty_write_set_cannot_be_called_a_fold(self) -> None:
        # Width 0 against a universe of 0 is the degenerate case: with every head now
        # offered, a share nobody writes under must not resolve to "everything is a
        # fold" and hand the walk an empty order.
        order, _ = self.order({"a": set(), "b": set()})
        self.assertEqual(order, ["a", "b"])

    def test_no_open_heads_yields_no_order_and_no_fold_line(self) -> None:
        self.assertEqual(self.order({}), ([], ""))


class TheFoldCutPrintsWhatTheThresholdSitsBetween(unittest.TestCase):
    def test_the_margin_names_the_narrowest_dropped_and_the_widest_kept(self) -> None:
        sets = {"fold": set(range(9)), "a": set(range(2)), "b": {9}}
        skip, line = p.fold_cut(sets, 0.4)
        self.assertEqual(skip, {"fold"})
        self.assertIn("1 dropped above 4.0 (=0.4 x 10 files)", line)
        self.assertIn("narrowest dropped 9, widest kept 2", line)

    def test_a_threshold_on_a_kept_head_s_width_says_one_file_moves_it(self) -> None:
        # Measured on the live queue: universe 45, threshold 18.0, widest kept 18 — and
        # that head is the branch named `the-whole-queue-lands`. `folds` drops on a
        # strict `>`, so a tie means one file decides whether the queue's own fold is
        # treated as a fold.
        sets = {"keep": set(range(4)), "fold": set(range(4, 10))}
        _, line = p.fold_cut(sets, 0.4)
        self.assertIn("above 4.0 (=0.4 x 10 files), narrowest dropped 6, widest kept 4", line)
        self.assertIn("one file moves it", line)

    def test_a_real_gap_appends_no_warning(self) -> None:
        sets = {"fold": set(range(9)), "a": {0}, "b": {9}}
        _, line = p.fold_cut(sets, 0.4)
        self.assertNotIn("one file moves it", line)

    def test_no_sets_is_a_cut_that_dropped_nothing(self) -> None:
        self.assertEqual(p.fold_cut({}, 0.4)[0], set())
        self.assertNotIn("one file moves it", p.fold_cut({}, 0.4)[1])


class EveryFindingReachesABucket(unittest.TestCase):
    def test_an_unreduced_composition_finding_is_printed(self) -> None:
        # `--no-reduce` produces exactly this shape, and it used to appear nowhere: the
        # documented flag for "report first-red only" reported nothing, and green.
        f = {"gate": "check_plugins", "k": 7, "ref": "c", "alone": False, "subset": ["c"]}
        out = p.report([f], ["a", "b", "c"], Counter(), {})
        self.assertIn("size unmeasured, the reduction was skipped", out)
        self.assertIn("plugins — first red at merge 7, on c", out)

    def test_an_unreduced_finding_withholds_the_clean_bill(self) -> None:
        f = {"gate": "check_plugins", "k": 7, "ref": "c", "alone": False, "subset": ["c"]}
        self.assertNotIn(
            "no gate needed three or more heads together",
            p.report([f], ["a", "b", "c"], Counter(), {}),
        )

    def test_no_findings_at_all_still_states_the_clean_bill(self) -> None:
        self.assertIn(
            "no gate needed three or more heads together", p.report([], ["a"], Counter(), {})
        )


class TheReachPrintsTheCutThatSetItsDenominator(unittest.TestCase):
    def test_the_fold_line_follows_the_reach(self) -> None:
        out = p.report([], ["a"], Counter(), {}, 127, "fold cut: 5 dropped above 18.0")
        lines = [l for l in out.splitlines() if l]
        self.assertIn("of 127 head(s) offered", lines[-2])
        self.assertEqual(lines[-1], "fold cut: 5 dropped above 18.0")

    def test_no_cut_prints_no_line(self) -> None:
        self.assertNotIn("fold cut", p.report([], ["a"], Counter(), {}, 1))


if __name__ == "__main__":
    unittest.main()
