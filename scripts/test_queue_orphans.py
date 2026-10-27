#!/usr/bin/env python3
"""Tests for queue_orphans.

The pure half — `classify`, `survey`, `report` — is covered with an injected
ancestry function, because what can be wrong there is the bookkeeping and not
the git call. Two of those cases are the ones that would silently empty the
report rather than fail loudly: a head counted as its own descendant, and a
head rescued by a descendant whose pull request was closed.

The git-shelling half — `pushed_heads`, `measurement`, and the real
`merge-base --is-ancestor` closure built in `main` — runs against a fixture
repository with a real remote, real stacked branches, and one branch written to
conflict with `main`.
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import queue_orphans as qo  # noqa: E402


def forest(parents):
    """`descendants` for a {head: parent-or-None} forest, excluding the head itself."""

    def ancestors(node):
        while node is not None:
            yield node
            node = parents[node]

    return lambda head: sorted(
        other for other in parents
        if other != head and head in set(ancestors(other))
    )


NONE = forest({})


class TestClassify(unittest.TestCase):
    def test_an_open_pull_request_is_open(self):
        self.assertEqual(qo.classify("a", {"a": 1}, {}, NONE), qo.OPEN)

    def test_a_closed_pull_request_is_a_ruling(self):
        self.assertEqual(qo.classify("a", {}, {"a": 1}, NONE), qo.RULED)

    def test_an_open_pull_request_outranks_a_closed_one_on_the_same_head(self):
        # A head reopened under a new PR must not read as decided.
        self.assertEqual(qo.classify("a", {"a": 2}, {"a": 1}, NONE), qo.OPEN)

    def test_a_head_with_no_pull_request_and_no_descendant_is_orphaned(self):
        self.assertEqual(qo.classify("a", {}, {}, NONE), qo.ORPHANED)

    def test_an_ancestor_of_an_open_pull_request_is_in_flight(self):
        descendants = forest({"base": None, "tip": "base"})
        self.assertEqual(
            qo.classify("base", {"tip": 7}, {}, descendants), qo.INFLIGHT
        )

    def test_a_head_is_not_its_own_descendant(self):
        # `merge-base --is-ancestor X X` succeeds; a descendant set that kept the
        # head would report every open PR's own base as in flight and print no
        # orphans at all.
        self.assertEqual(
            qo.classify("a", {"a": 1}, {}, lambda head: ["a"]), qo.OPEN
        )
        self.assertEqual(
            qo.classify("b", {}, {}, lambda head: ["b"]), qo.ORPHANED
        )

    def test_a_declined_descendant_does_not_rescue_a_head(self):
        descendants = forest({"base": None, "tip": "base"})
        self.assertEqual(
            qo.classify("base", {}, {"tip": 9}, descendants), qo.ORPHANED
        )

    def test_a_descendant_with_no_pull_request_does_not_rescue_a_head(self):
        descendants = forest({"base": None, "tip": "base"})
        self.assertEqual(qo.classify("base", {}, {}, descendants), qo.ORPHANED)

    def test_a_distant_ancestor_of_an_open_pull_request_is_in_flight(self):
        descendants = forest({"a": None, "b": "a", "c": "b", "d": "c"})
        self.assertEqual(qo.classify("a", {"d": 3}, {}, descendants), qo.INFLIGHT)

    def test_heads_at_the_same_commit_each_contain_the_other(self):
        # Two names for one commit: the unopened one is covered by the opened one.
        self.assertEqual(qo.classify("y", {"x": 4}, {}, lambda head: ["x"]), qo.INFLIGHT)
        self.assertEqual(qo.classify("x", {"x": 4}, {}, lambda head: ["y"]), qo.OPEN)


def sized(**sizes):
    """`measure` returning a fixed size per head, recording which heads were asked."""
    asked = []

    def measure(head):
        asked.append(head)
        added, removed = sizes[head]
        return {"date": "2026-01-01", "commits": 1, "files": 1,
                "added": added, "removed": removed, "merge": "clean"}

    return measure, asked


class TestSurvey(unittest.TestCase):
    def test_orphans_sort_last_and_smallest_first(self):
        measure, _ = sized(big=(500, 0), small=(2, 1))
        rows = qo.survey(
            ["big", "small", "opened"], {"opened": 1}, {}, NONE, measure
        )
        self.assertEqual(
            [(r["head"], r["verdict"]) for r in rows],
            [("opened", qo.OPEN), ("small", qo.ORPHANED), ("big", qo.ORPHANED)],
        )

    def test_deletions_count_toward_size(self):
        measure, _ = sized(a=(1, 90), b=(10, 10))
        rows = qo.survey(["a", "b"], {}, {}, NONE, measure)
        self.assertEqual([r["head"] for r in rows], ["b", "a"])

    def test_only_orphans_are_measured(self):
        measure, asked = sized(lonely=(1, 0))
        qo.survey(["opened", "closed", "lonely"], {"opened": 1}, {"closed": 2},
                  NONE, measure)
        self.assertEqual(asked, ["lonely"])

    def test_an_orphan_names_the_pull_requests_closed_below_it(self):
        measure, _ = sized(base=(1, 0))
        descendants = forest({"base": None, "tip": "base"})
        rows = qo.survey(["base", "tip"], {}, {"tip": 9}, descendants, measure)
        base = next(r for r in rows if r["head"] == "base")
        self.assertEqual(base["declined_descendants"], [9])

    def test_every_head_appears_exactly_once(self):
        measure, _ = sized(c=(1, 1))
        rows = qo.survey(["a", "b", "c"], {"a": 1}, {"b": 2}, NONE, measure)
        self.assertEqual(sorted(r["head"] for r in rows), ["a", "b", "c"])

    def test_an_open_head_carries_its_pull_request_number(self):
        rows = qo.survey(["a"], {"a": 42}, {}, NONE, lambda h: {})
        self.assertEqual(rows[0]["pr"], 42)


class TestReport(unittest.TestCase):
    def rows(self):
        measure, _ = sized(small=(2, 0), big=(90, 0))
        return qo.survey(
            ["opened", "shut", "base", "small", "big"],
            {"opened": 1}, {"shut": 2},
            forest({"base": None, "opened": "base", "shut": None,
                    "small": None, "big": None}),
            measure,
        )

    def test_the_counts_name_every_head(self):
        lines = qo.report(self.rows(), {"opened": 1}, {"shut": 2}, limit=50)
        self.assertIn("5 pushed head(s) read, 1 open PR(s), 1 closed", lines[0])
        self.assertIn("1 open", lines[1])
        self.assertIn("1 ruled", lines[2])
        self.assertIn("1 in flight", lines[3])
        self.assertIn("2 ORPHANED", lines[4])

    def test_only_orphans_get_a_detail_line(self):
        lines = qo.report(self.rows(), {"opened": 1}, {"shut": 2}, limit=50)
        detail = [l for l in lines if l.startswith("ORPHANED  ")]
        self.assertEqual(len(detail), 2)
        self.assertIn("small", detail[0])
        self.assertIn("big", detail[1])

    def test_the_limit_truncates_and_says_so(self):
        lines = qo.report(self.rows(), {"opened": 1}, {"shut": 2}, limit=1)
        self.assertEqual(len([l for l in lines if l.startswith("ORPHANED  ")]), 1)
        self.assertIn("... 1 more orphaned head(s)", lines)

    def test_an_empty_queue_still_reports_its_zeroes(self):
        lines = qo.report([], {}, {}, limit=50)
        self.assertIn("0 pushed head(s) read", lines[0])
        self.assertIn("0 ORPHANED", lines[4])


def run(*args, cwd):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


class TestAgainstARepository(unittest.TestCase):
    """`pushed_heads`, `measurement`, and the real ancestry closure from `main`."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(
            dir=os.environ.get("TMPDIR"), prefix="queue-orphans-"
        )
        root = Path(cls.tmp.name)
        bare, work = root / "origin.git", root / "work"
        run("git", "init", "--bare", "-b", "main", str(bare), cwd=root)
        run("git", "init", "-b", "main", str(work), cwd=root)
        cls.work = str(work)
        for key, value in (("user.email", "t@t"), ("user.name", "t"),
                           ("commit.gpgsign", "false")):
            run("git", "config", key, value, cwd=cls.work)
        run("git", "remote", "add", "origin", str(bare), cwd=cls.work)

        (work / "role.md").write_text("one\ntwo\nthree\n")
        run("git", "add", "-A", cwd=cls.work)
        run("git", "commit", "-m", "main", cwd=cls.work)
        run("git", "push", "-q", "origin", "main", cwd=cls.work)

        # base <- tip, a two-commit stack; and a sibling that rewrites line one.
        run("git", "checkout", "-q", "-b", "koan/base", cwd=cls.work)
        (work / "role.md").write_text("one\ntwo\nthree\nfour\n")
        run("git", "commit", "-qam", "base", cwd=cls.work)
        run("git", "checkout", "-q", "-b", "koan/tip", cwd=cls.work)
        (work / "role.md").write_text("one\ntwo\nthree\nfour\nfive\n")
        run("git", "commit", "-qam", "tip", cwd=cls.work)

        run("git", "checkout", "-q", "-b", "koan/clash", "main", cwd=cls.work)
        (work / "role.md").write_text("ONE\ntwo\nthree\n")
        run("git", "commit", "-qam", "clash", cwd=cls.work)
        run("git", "checkout", "-q", "-b", "other/outside", "main", cwd=cls.work)
        (work / "role.md").write_text("one\ntwo\nthree\nsix\n")
        run("git", "commit", "-qam", "outside", cwd=cls.work)

        run("git", "push", "-q", "origin", "koan/base", "koan/tip",
            "koan/clash", "other/outside", cwd=cls.work)
        run("git", "checkout", "-q", "main", cwd=cls.work)
        run("git", "fetch", "-q", "origin", cwd=cls.work)
        # main must move away from the branches, or `main...ref` is empty — and
        # it must rewrite the line koan/clash rewrote, or nothing conflicts.
        (work / "README.md").write_text("read me\n")
        (work / "role.md").write_text("uno\ntwo\nthree\n")
        run("git", "add", "-A", cwd=cls.work)
        run("git", "commit", "-qm", "readme", cwd=cls.work)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.previous = os.getcwd()
        os.chdir(self.work)
        self.addCleanup(os.chdir, self.previous)

    def test_pushed_heads_reads_the_remote_and_drops_main(self):
        self.assertEqual(
            qo.pushed_heads("*"),
            ["koan/base", "koan/clash", "koan/tip", "other/outside"],
        )

    def test_pushed_heads_honours_the_pattern(self):
        self.assertEqual(
            qo.pushed_heads("koan/*"), ["koan/base", "koan/clash", "koan/tip"]
        )

    def test_pushed_heads_can_match_nothing(self):
        self.assertEqual(qo.pushed_heads("nobody/*"), [])

    def test_measurement_counts_the_whole_stack_not_the_last_commit(self):
        tip = qo.measurement("koan/tip")
        self.assertEqual(tip["commits"], 2)
        self.assertEqual((tip["files"], tip["added"], tip["removed"]), (1, 2, 0))
        self.assertEqual(tip["merge"], "clean")

    def test_measurement_reports_a_conflicting_head(self):
        self.assertEqual(qo.measurement("koan/clash")["merge"], "conflicts")

    def test_measurement_dates_the_head(self):
        self.assertRegex(qo.measurement("koan/base")["date"], r"^\d{4}-\d{2}-\d{2}$")

    def test_end_to_end_classification_over_the_fixture(self):
        heads = qo.pushed_heads("koan/*")

        def descendants(head):
            return [
                other for other in heads
                if other != head and subprocess.run(
                    ["git", "merge-base", "--is-ancestor",
                     f"origin/{head}", f"origin/{other}"], capture_output=True
                ).returncode == 0
            ]

        # koan/tip is the only one anybody opened.
        verdicts = {h: qo.classify(h, {"koan/tip": 1}, {}, descendants) for h in heads}
        self.assertEqual(verdicts, {
            "koan/base": qo.INFLIGHT,   # contained by the open tip
            "koan/tip": qo.OPEN,
            "koan/clash": qo.ORPHANED,  # a sibling contains nothing
        })


if __name__ == "__main__":
    unittest.main()
