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
