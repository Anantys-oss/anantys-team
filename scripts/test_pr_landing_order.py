#!/usr/bin/env python3
"""Fixture tests for pr_landing_order — run: python3 -m unittest discover scripts"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pr_landing_order as p  # noqa: E402


def edges(*pairs):
    return {frozenset(pair): [] for pair in pairs}


class CheckerDiscovery(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)

    def write(self, *names):
        for n in names:
            (self.dir / n).write_text("")

    def names(self):
        return [found.name for found in p.checker_scripts(self.dir)]

    def test_finds_checkers(self):
        self.write("check_a.py", "check_b.py")
        self.assertEqual(self.names(), ["check_a.py", "check_b.py"])

    def test_skips_a_checkers_own_tests(self):
        # test_check_a.py imports check_a and would be run as if it were a gate.
        self.write("check_a.py", "test_check_a.py")
        self.assertEqual(self.names(), ["check_a.py"])

    def test_skips_unrelated_scripts(self):
        self.write("check_a.py", "pr_landing_order.py", "helper.py")
        self.assertEqual(self.names(), ["check_a.py"])

    def test_empty_tree_has_no_checkers(self):
        self.assertEqual(self.names(), [])

    def test_only_narrows_to_the_named_checkers(self):
        self.write("check_a.py", "check_b.py")
        self.assertEqual(
            [f.name for f in p.checker_scripts(self.dir, ["check_b.py"])],
            ["check_b.py"])

    def test_only_still_refuses_a_checkers_own_tests(self):
        self.write("check_a.py", "test_check_a.py")
        self.assertEqual(
            p.checker_scripts(self.dir, ["test_check_a.py"]), [])

    def test_an_empty_only_runs_nothing(self):
        # A round with no failures must not silently re-run the whole set.
        self.write("check_a.py")
        self.assertEqual(p.checker_scripts(self.dir, []), [])


class Blockers(unittest.TestCase):
    """Which members of a round stand between it and a candidate fix."""

    def test_a_clean_candidate_is_blocked_by_nobody(self):
        self.assertEqual(p.blockers(9, [1, 2], edges((1, 2))), [])

    def test_only_the_conflicting_members_are_named(self):
        self.assertEqual(p.blockers(9, [1, 2, 3], edges((9, 1), (9, 3))), [1, 3])

    def test_conflicts_outside_the_round_are_not_the_rounds_problem(self):
        self.assertEqual(p.blockers(9, [1], edges((9, 2))), [])

    def test_the_result_is_ordered_so_the_report_is_stable(self):
        self.assertEqual(p.blockers(9, [3, 1, 2], edges((9, 3), (9, 1))), [1, 3])

    def test_an_empty_round_blocks_nothing(self):
        self.assertEqual(p.blockers(9, [], edges((9, 1))), [])


class Waves(unittest.TestCase):
    def test_no_conflicts_is_one_wave(self):
        self.assertEqual(p.waves([1, 2, 3], {}), [[1, 2, 3]])

    def test_a_conflicting_pair_splits_into_two_waves(self):
        self.assertEqual(p.waves([1, 2], edges((1, 2))), [[1], [2]])

    def test_independent_pr_joins_the_first_wave(self):
        self.assertEqual(p.waves([1, 2, 3], edges((1, 2))), [[1, 3], [2]])

    def test_highest_degree_pr_lands_first(self):
        # 3 collides with both 1 and 2; delaying it would cost two rebases.
        self.assertEqual(p.waves([1, 2, 3], edges((1, 3), (2, 3))), [[3], [1, 2]])

    def test_a_chain_needs_only_two_waves(self):
        # 1-2-3-4 path: alternate ends, no PR shares a wave with its neighbour.
        order = p.waves([1, 2, 3, 4], edges((1, 2), (2, 3), (3, 4)))
        self.assertEqual(len(order), 2)
        for wave in order:
            for a in wave:
                self.assertNotIn(a + 1, wave)

    def test_a_triangle_needs_three_waves(self):
        order = p.waves([1, 2, 3], edges((1, 2), (2, 3), (1, 3)))
        self.assertEqual(order, [[1], [2], [3]])

    def test_every_pr_appears_exactly_once(self):
        order = p.waves([1, 2, 3, 4, 5], edges((1, 2), (2, 3), (4, 5)))
        landed = [n for wave in order for n in wave]
        self.assertEqual(sorted(landed), [1, 2, 3, 4, 5])


class LaterWavesAlwaysConflictBackwards(unittest.TestCase):
    """The property that makes every round past the first unassemblable.

    `waves` defers a PR exactly when it collides with one already placed in the
    current wave, so a later wave's member always conflicts with the wave below
    it. A round is a cumulative prefix, so round k>1 always contains a
    conflicting pair and `union_tree` must refuse it. This is why `--verify`
    reports one round and stops — and it is a fact about the partition, not
    about any particular queue.
    """

    def assert_conflicts_backwards(self, numbers, graph):
        order = p.waves(numbers, graph)
        for i, wave in enumerate(order[1:], 1):
            for pr in wave:
                self.assertTrue(
                    any(frozenset((pr, earlier)) in graph
                        for earlier in order[i - 1]),
                    f"#{pr} in wave {i + 1} conflicts with nothing in wave {i}")

    def test_a_chain(self):
        self.assert_conflicts_backwards(
            [1, 2, 3, 4], edges((1, 2), (2, 3), (3, 4)))

    def test_a_triangle(self):
        self.assert_conflicts_backwards([1, 2, 3], edges((1, 2), (2, 3), (1, 3)))

    def test_a_star_with_bystanders(self):
        self.assert_conflicts_backwards(
            [1, 2, 3, 4, 5], edges((1, 2), (1, 3), (1, 4)))

    def test_one_wave_has_no_later_wave_to_check(self):
        self.assert_conflicts_backwards([1, 2, 3], {})


class Unverifiable(unittest.TestCase):
    def test_it_names_the_round_to_land_and_the_one_that_follows(self):
        message = p.unverifiable(2)
        self.assertIn("Land round 1", message)
        self.assertIn("round 2 becomes round 1", message)

    def test_it_never_tells_the_operator_to_land_round_zero(self):
        # Round 1 can only refuse if pairwise-clean PRs fail to combine;
        # there is no earlier round to land, so the remedy must not claim one.
        self.assertNotIn("round 0", p.unverifiable(1))

    def test_it_does_not_ask_for_a_resolution_that_cannot_happen_yet(self):
        # The rebase exists only after the round below lands — inviting a
        # resolution now sends the operator at work that is not theirs to do.
        self.assertNotIn("must first resolve", p.unverifiable(3))


class Rounds(unittest.TestCase):
    refs = {1: "a", 2: "b", 3: "c"}

    def test_each_round_is_a_prefix_of_the_queue(self):
        self.assertEqual(
            p.rounds([[1, 2], [3]], self.refs),
            [[(1, "a"), (2, "b")], [(1, "a"), (2, "b"), (3, "c")]],
        )

    def test_one_wave_is_one_round(self):
        self.assertEqual(p.rounds([[1]], self.refs), [[(1, "a")]])

    def test_the_last_round_holds_the_whole_queue(self):
        last = p.rounds([[1], [2], [3]], self.refs)[-1]
        self.assertEqual([n for n, _ in last], [1, 2, 3])

    def test_an_earlier_round_never_sees_a_later_wave(self):
        first = p.rounds([[1], [2, 3]], self.refs)[0]
        self.assertEqual([n for n, _ in first], [1])

    def test_no_waves_is_no_rounds(self):
        self.assertEqual(p.rounds([], self.refs), [])


if __name__ == "__main__":
    unittest.main()
