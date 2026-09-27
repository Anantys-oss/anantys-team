#!/usr/bin/env python3
"""Fixture tests for pr_landing_order — run: python3 -m unittest discover scripts"""

import os
import shutil
import subprocess
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


MOVED = ("- **An adjudication** is the single highest-value artifact a "
         "campaign produces, and it is never re-derived.")
KEPT = ("A case the runner could not reach is BLOCKED and never PASS, "
        "whatever the rest of the scenario did.")


class RelocatedText(unittest.TestCase):
    """A real repo: one branch splits a file, another edits what it moved.

    This is the shape the queue actually has — a progressive-disclosure refactor
    open alongside content PRs on the file it empties.
    """

    def git(self, *args):
        subprocess.run(("git",) + args, check=True, capture_output=True)

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.dir)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        Path("doc.md").write_text(f"# Doc\n\n{MOVED}\n\n{KEPT}\n")
        self.git("add", "doc.md")
        self.git("commit", "-qm", "base")

        self.git("checkout", "-qb", "split")
        Path("doc.md").write_text(f"# Doc\n\nSee reference.\n\n{KEPT}\n")
        Path("ref.md").write_text(f"# Reference\n\n{MOVED}\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "split the doc")

        self.git("checkout", "-q", "main")
        self.git("checkout", "-qb", "edit")
        Path("doc.md").write_text(
            f"# Doc\n\n{MOVED}\nIt is written back into the plan.\n\n{KEPT}\n")
        self.git("commit", "-qam", "edit what split moved")

        self.git("checkout", "-q", "main")
        self.git("checkout", "-qb", "elsewhere")
        Path("doc.md").write_text(
            f"# Doc\n\n{MOVED}\n\n{KEPT}\nSay so in the blocker list.\n")
        self.git("commit", "-qam", "edit what split kept")
        self.git("checkout", "-q", "main")

    def test_an_edited_line_is_an_anchor(self):
        self.assertIn(MOVED, p.anchors("main", "edit", "doc.md"))

    def test_a_short_line_is_not_an_anchor(self):
        # "# Doc" matches anywhere; resolving it would name every file.
        self.assertNotIn("# Doc", p.anchors("main", "edit", "doc.md"))

    def test_the_destination_is_the_file_the_text_moved_to(self):
        # MOVED is a markdown bullet, so it opens with "- " — a search that
        # reads it as an option reports no destination and looks like a clean
        # rebase. Most prose lines in this repo are bullets.
        self.assertTrue(MOVED.startswith("- "))
        self.assertEqual(
            p.moved("split", "doc.md", p.anchors("main", "edit", "doc.md")),
            ["ref.md"])

    def test_an_edit_to_text_that_stayed_reports_no_destination(self):
        # Same shared file, same conflicting pair — but a plain rebase fixes it.
        self.assertEqual(
            p.moved("split", "doc.md", p.anchors("main", "elsewhere", "doc.md")),
            [])

    def test_the_shared_file_is_never_offered_as_its_own_destination(self):
        self.assertNotIn(
            "doc.md",
            p.moved("split", "doc.md", p.anchors("main", "edit", "doc.md")))

    def test_a_path_the_branch_does_not_have_reports_no_destination(self):
        self.assertEqual(p.moved("split", "gone.md", [MOVED]), [])


class Relocations(unittest.TestCase):
    """Both directions of every edge, and silence when nothing moved."""

    prs = [(1, "splitter", "", {"doc.md"}), (2, "editor", "", {"doc.md"})]
    edge = {frozenset((1, 2)): ["doc.md"]}

    def stub(self, *destinations):
        """Only `origin/splitter` moved anything; nobody's anchors are read."""
        self.addCleanup(setattr, p, "moved", p.moved)
        self.addCleanup(setattr, p, "anchors", p.anchors)
        p.anchors = lambda *a, **k: ["a line long enough to be an anchor"]
        p.moved = lambda ref, path, needles, probes=5: (
            list(destinations) if ref == "origin/splitter" else [])

    def test_it_names_the_loser_the_winner_and_the_destination(self):
        self.stub("ref.md")
        self.assertEqual(p.relocations("main", self.prs, self.edge),
                         {(2, 1): {"doc.md": ["ref.md"]}})

    def test_a_pair_with_nothing_moved_is_absent_not_empty(self):
        # An empty entry would print a relocation warning for a plain rebase.
        self.stub()
        self.assertEqual(p.relocations("main", self.prs, self.edge), {})

    def test_a_clean_queue_has_no_relocations(self):
        self.stub("ref.md")
        self.assertEqual(p.relocations("main", self.prs, {}), {})


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


class SuiteIsAGate(unittest.TestCase):
    """A real tree: one checker, one test beside it. CI runs both.

    The suite is asserted through `run_checkers` rather than a discovery helper
    because that is where the gate set is decided, and the question is whether a
    red test reaches the operator at all.
    """

    def git(self, *args):
        subprocess.run(("git",) + args, check=True, capture_output=True)

    def commit(self, body):
        Path("scripts").mkdir(exist_ok=True)
        Path("scripts/check_a.py").write_text("")
        Path("scripts/test_check_a.py").write_text(
            "import unittest\n\n"
            "class T(unittest.TestCase):\n"
            f"    def test_a(self):\n        {body}\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "gates")

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.dir)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")

    def test_a_passing_suite_is_reported_green_beside_the_checkers(self):
        self.commit("pass")
        results = p.run_checkers("HEAD")
        self.assertEqual(sorted(results), ["check_a.py", p.SUITE])
        self.assertEqual(results[p.SUITE][0], 0)

    def test_a_failing_test_makes_the_round_red(self):
        # The checker still passes: without the suite the round reads green.
        self.commit("self.fail('boom')")
        results = p.run_checkers("HEAD")
        self.assertEqual(results["check_a.py"][0], 0)
        self.assertNotEqual(results[p.SUITE][0], 0)

    def test_a_failing_test_is_named_so_the_operator_can_find_it(self):
        self.commit("self.fail('boom')")
        self.assertTrue(any("test_a" in line
                            for line in p.run_checkers("HEAD")[p.SUITE][1]))

    def test_only_can_re_test_the_suite_alone(self):
        self.commit("pass")
        self.assertEqual(sorted(p.run_checkers("HEAD", only=[p.SUITE])),
                         [p.SUITE])

    def test_only_a_checker_does_not_drag_the_suite_along(self):
        self.commit("self.fail('boom')")
        self.assertEqual(sorted(p.run_checkers("HEAD", only=["check_a.py"])),
                         ["check_a.py"])

    def test_a_tree_with_no_scripts_has_no_gates(self):
        # `unittest discover -s scripts` errors on a missing directory; an empty
        # tree must report nothing to verify, not a failure to verify.
        Path("README.md").write_text("no scripts here\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "no scripts")
        self.assertEqual(p.run_checkers("HEAD"), {})


class AGitAwareGateCanAskGit(unittest.TestCase):
    """A real tree whose checker asks git a question, and gets an answer.

    `check_version_bump.py` is git-aware by design — freshness is a claim about
    a diff, not about a tree — and when it cannot resolve a base ref it prints
    "skipping" and exits 0. Under an extracted tree that is every round, so the
    gate reads `OK` having never run. The checker here is inverted (red exactly
    when git answers) so the assertion fails against a tree with no `.git`
    rather than passing for the wrong reason.
    """

    def git(self, *args):
        subprocess.run(("git",) + args, check=True, capture_output=True)

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.dir)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        Path("scripts").mkdir()
        Path("scripts/check_git.py").write_text(
            "import subprocess, sys\n"
            "asked = subprocess.run(['git', 'rev-parse', 'HEAD'],\n"
            "                       capture_output=True).returncode\n"
            "sys.exit(1 if asked == 0 else 0)\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "a git-aware gate")

    def test_the_gate_reaches_git_and_its_red_reaches_the_operator(self):
        self.assertNotEqual(p.run_checkers("HEAD")["check_git.py"][0], 0)

    def test_the_checkout_is_not_left_registered_behind(self):
        p.run_checkers("HEAD")
        listed = subprocess.run(("git", "worktree", "list"),
                                capture_output=True, text=True, check=True)
        self.assertEqual(len(listed.stdout.strip().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
