#!/usr/bin/env python3
"""Fixture tests for pr_landing_order — run: python3 -m unittest discover scripts"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pr_landing_order as p  # noqa: E402


def edges(*pairs):
    return {frozenset(pair): [] for pair in pairs}


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


if __name__ == "__main__":
    unittest.main()
