#!/usr/bin/env python3
"""Tests for queue_forks.

The pure halves — `classify`, `survey`, `report` — are covered exhaustively with
an injected ancestry predicate, because the thing that can be wrong there is the
combinatorics and not the git call. The git-shelling half (`versions`,
`touched`, and the real `merge-base --is-ancestor`) runs against a fixture
repository built here with real commits, including the two shapes the report
exists to tell apart: a path rewritten down one line of descent, and the same
path rewritten independently on two siblings.
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import queue_forks as qf  # noqa: E402


def chain_ancestry(order):
    """`is_ancestor` for commits laid out in a single line, earliest first."""
    rank = {c: i for i, c in enumerate(order)}
    return lambda a, b: rank[a] <= rank[b]


def tree_ancestry(parents):
    """`is_ancestor` for a {commit: parent-or-None} forest."""

    def walk(node):
        while node is not None:
            yield node
            node = parents[node]

    return lambda a, b: a in set(walk(b))


class TestClassify(unittest.TestCase):
    def test_single_version_is_a_chain(self):
        self.assertEqual(qf.classify(["a"], chain_ancestry(["a"])), qf.CHAIN)

    def test_no_versions_is_a_chain(self):
        self.assertEqual(qf.classify([], lambda a, b: False), qf.CHAIN)

    def test_linear_history_is_a_chain_at_every_length(self):
        order = ["a", "b", "c", "d", "e"]
        for size in range(2, len(order) + 1):
            with self.subTest(size=size):
                self.assertEqual(
                    qf.classify(order[:size], chain_ancestry(order)), qf.CHAIN
                )

    def test_order_of_the_input_does_not_change_the_verdict(self):
        order = ["a", "b", "c"]
        self.assertEqual(qf.classify(["c", "a", "b"], chain_ancestry(order)), qf.CHAIN)

    def test_two_siblings_fork(self):
        # a -> b, a -> c: b and c are incomparable.
        is_ancestor = tree_ancestry({"a": None, "b": "a", "c": "a"})
        self.assertEqual(qf.classify(["b", "c"], is_ancestor), qf.FORK)

    def test_one_incomparable_pair_forks_an_otherwise_ordered_set(self):
        is_ancestor = tree_ancestry({"a": None, "b": "a", "c": "a", "d": "b"})
        self.assertEqual(qf.classify(["a", "b", "d", "c"], is_ancestor), qf.FORK)

    def test_an_untraced_version_forks_rather_than_certifying_safety(self):
        self.assertEqual(qf.classify(["a", None], chain_ancestry(["a"])), qf.FORK)

    def test_a_lone_untraced_version_also_forks(self):
        self.assertEqual(qf.classify([None, None], lambda a, b: True), qf.FORK)


class TestSurvey(unittest.TestCase):
    def setUp(self):
        self.position = lambda ref, path: {"r1": "a", "r2": "b", "r3": "c"}[ref]

    def test_single_version_paths_are_dropped(self):
        found = {"p": {"sha": ["r1", "r2"]}}
        self.assertEqual(qf.survey(found, self.position, chain_ancestry(["a", "b"])), [])

    def test_a_chain_is_reported_as_a_chain(self):
        found = {"p": {"s1": ["r1"], "s2": ["r2"]}}
        rows = qf.survey(found, self.position, chain_ancestry(["a", "b"]))
        self.assertEqual([(r[0], r[1]) for r in rows], [("p", qf.CHAIN)])

    def test_siblings_are_reported_as_a_fork(self):
        found = {"p": {"s1": ["r1"], "s2": ["r2"]}}
        is_ancestor = tree_ancestry({"a": None, "b": None})
        rows = qf.survey(found, self.position, is_ancestor)
        self.assertEqual(rows[0][1], qf.FORK)

    def test_forks_sort_ahead_of_chains_and_wider_forks_ahead_of_narrower(self):
        found = {
            "chained": {"x": ["r1"], "y": ["r2"]},
            "narrow": {"x": ["r1"], "y": ["r3"]},
            "wide": {"x": ["r1"], "y": ["r2"], "z": ["r3"]},
        }
        # a is an ancestor of b only; c is a sibling of both.
        is_ancestor = tree_ancestry({"a": None, "b": "a", "c": None})
        rows = qf.survey(found, self.position, is_ancestor)
        self.assertEqual([r[0] for r in rows], ["wide", "narrow", "chained"])

    def test_carriers_are_sorted_by_how_many_heads_hold_them(self):
        found = {"p": {"s1": ["r1"], "s2": ["r2", "r3"]}}
        position = lambda ref, path: {"r1": "a", "r2": "b", "r3": "b"}[ref]  # noqa: E731
        rows = qf.survey(found, position, tree_ancestry({"a": None, "b": None}))
        self.assertEqual([len(refs) for _, refs in rows[0][2]], [2, 1])

    def test_the_position_of_a_version_is_read_from_one_of_its_carriers(self):
        seen = []

        def position(ref, path):
            seen.append((ref, path))
            return "a"

        qf.survey({"p": {"s1": ["r2", "r1"], "s2": ["r3"]}}, position, lambda a, b: True)
        # One lookup per version, never per head, and on a carrier of that version.
        self.assertEqual(len(seen), 2)
        self.assertEqual({ref for ref, _ in seen}, {"r2", "r3"})


class TestReport(unittest.TestCase):
    def test_counts_separate_chains_from_forks(self):
        rows = [
            ("a", qf.FORK, [("c1", ["origin/x"]), ("c2", ["origin/y"])]),
            ("b", qf.CHAIN, [("c1", ["origin/x"]), ("c2", ["origin/y"])]),
        ]
        lines = qf.report(rows, ["origin/x", "origin/y"], limit=20)
        self.assertIn("2 head(s) read", lines[0])
        self.assertIn("2 path(s) carried in more than one version", lines[1])
        self.assertIn("1 with a total order", lines[2])
        self.assertIn("1 forked", lines[3])

    def test_only_forked_paths_are_detailed(self):
        rows = [("kept", qf.FORK, [("c1", ["origin/x"])]),
                ("quiet", qf.CHAIN, [("c1", ["origin/x"])])]
        body = "\n".join(qf.report(rows, ["origin/x"], limit=20))
        self.assertIn("kept", body)
        self.assertNotIn("quiet", body)

    def test_head_names_lose_the_remote_prefix(self):
        rows = [("p", qf.FORK, [("c0ffee12ab", ["origin/koan/some-head"])])]
        body = "\n".join(qf.report(rows, ["origin/koan/some-head"], limit=20))
        self.assertIn("koan/some-head", body)
        self.assertIn("c0ffee12", body)

    def test_a_long_carrier_list_is_summarised(self):
        refs = [f"origin/koan/h{i}" for i in range(6)]
        rows = [("p", qf.FORK, [("c1", refs)])]
        body = "\n".join(qf.report(rows, refs, limit=20))
        self.assertIn("(+3)", body)

    def test_an_untraced_version_prints_as_untraced(self):
        rows = [("p", qf.FORK, [(None, ["origin/x"])])]
        self.assertIn("untraced", "\n".join(qf.report(rows, ["origin/x"], limit=20)))

    def test_the_limit_truncates_and_says_so(self):
        rows = [(f"p{i}", qf.FORK, [("c1", ["origin/x"])]) for i in range(5)]
        body = "\n".join(qf.report(rows, ["origin/x"], limit=2))
        self.assertIn("... 3 more forked path(s)", body)
        self.assertNotIn("p4", body)

    def test_an_empty_survey_still_reports_the_heads_it_read(self):
        lines = qf.report([], ["origin/x"], limit=20)
        self.assertIn("1 head(s) read", lines[0])
        self.assertIn("0 forked", lines[3])


class TestAgainstAGitRepository(unittest.TestCase):
    """`versions`, `touched` and real ancestry, on a tree with a chain and a fork."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.have_git = cls._build()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @classmethod
    def _run(cls, *args):
        return subprocess.run(
            ["git", *args], cwd=cls.root, capture_output=True, text=True,
        )

    @classmethod
    def _commit(cls, path, text, message):
        target = cls.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        cls._run("add", "-A")
        cls._run("commit", "-m", message)

    @classmethod
    def _build(cls):
        if cls._run("init", "-q", "-b", "main").returncode != 0:
            return False
        cls._run("config", "user.email", "t@example.invalid")
        cls._run("config", "user.name", "t")
        cls._commit("scripts/gate.py", "v0\n", "base")
        cls._commit("scripts/steady.py", "same\n", "steady")
        cls._run("branch", "base")
        # One line of descent: gate.py v0 -> v1 -> v2.
        cls._run("checkout", "-q", "-b", "chainA", "base")
        cls._commit("scripts/gate.py", "v1\n", "chainA")
        cls._run("checkout", "-q", "-b", "chainB", "chainA")
        cls._commit("scripts/gate.py", "v2\n", "chainB")
        # A sibling that rewrote the same file independently.
        cls._run("checkout", "-q", "-b", "sibling", "base")
        cls._commit("scripts/gate.py", "other\n", "sibling")
        cls._run("checkout", "-q", "main")
        return True

    def setUp(self):
        if not self.have_git:
            self.skipTest("git unavailable")
        self._cwd = os.getcwd()
        os.chdir(self.root)

    def tearDown(self):
        os.chdir(self._cwd)

    @staticmethod
    def _is_ancestor(a, b):
        return subprocess.run(
            ["git", "merge-base", "--is-ancestor", a, b], capture_output=True
        ).returncode == 0

    def test_versions_groups_heads_by_blob(self):
        found = qf.versions(["chainA", "chainB", "sibling"], "scripts/")
        self.assertEqual(len(found["scripts/gate.py"]), 3)
        # Every head carries the identical steady.py, so it is one version.
        self.assertEqual(len(found["scripts/steady.py"]), 1)

    def test_the_prefix_excludes_paths_outside_it(self):
        self.assertEqual(qf.versions(["chainA"], "nowhere/"), {})

    def test_touched_names_the_commit_that_wrote_the_version(self):
        here = qf.touched("chainB", "scripts/gate.py")
        self.assertEqual(
            here,
            self._run("rev-parse", "chainB").stdout.strip(),
            "chainB's own commit is the one that wrote v2",
        )
        # steady.py was last written before the branches diverged.
        self.assertEqual(
            qf.touched("chainB", "scripts/steady.py"),
            qf.touched("sibling", "scripts/steady.py"),
        )

    def test_touched_returns_none_for_a_path_the_ref_never_had(self):
        self.assertIsNone(qf.touched("chainB", "scripts/absent.py"))

    def test_a_descent_line_alone_is_a_chain(self):
        rows = qf.survey(
            qf.versions(["base", "chainA", "chainB"], "scripts/"),
            qf.touched, self._is_ancestor,
        )
        self.assertEqual([(r[0], r[1]) for r in rows], [("scripts/gate.py", qf.CHAIN)])

    def test_adding_the_sibling_turns_the_same_path_into_a_fork(self):
        rows = qf.survey(
            qf.versions(["base", "chainA", "chainB", "sibling"], "scripts/"),
            qf.touched, self._is_ancestor,
        )
        self.assertEqual([(r[0], r[1]) for r in rows], [("scripts/gate.py", qf.FORK)])
        self.assertEqual(len(rows[0][2]), 4, "v0, v1, v2 and the sibling's own")

    def test_a_file_no_head_changed_never_reaches_the_report(self):
        rows = qf.survey(
            qf.versions(["base", "chainA", "chainB", "sibling"], "scripts/"),
            qf.touched, self._is_ancestor,
        )
        self.assertNotIn("scripts/steady.py", [r[0] for r in rows])


if __name__ == "__main__":
    unittest.main()
