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


class AGateLandsWithItsSubject(unittest.TestCase):
    """A round that brings its own gate, and one member's bump for everyone.

    `check_stamp.py` is `check_version_bump.py` in miniature: a change to the
    content owes a bump to one shared file. Three members — the gate, a member
    that bumps, a member that does not. The union holds both a content change
    and a bump, so the gate passes there; neither member pushes the union.
    """

    def git(self, *args):
        return subprocess.run(("git",) + args, check=True, capture_output=True,
                              text=True).stdout

    def branch(self, name, files):
        self.git("checkout", "-qb", name, "main")
        for path, text in files.items():
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(text)
        self.git("add", "-A")
        self.git("commit", "-qm", name)
        self.git("update-ref", f"refs/remotes/origin/{name}", "HEAD")
        self.git("checkout", "-q", "main")

    GATE = (
        "import subprocess, sys\n"
        "def g(*a):\n"
        "    return subprocess.run(['git', *a], capture_output=True,\n"
        "                          text=True).stdout.strip()\n"
        "base = g('merge-base', 'origin/main', 'HEAD')\n"
        "changed = g('diff', '--name-only', base, 'HEAD').split()\n"
        "if 'role.md' in changed and 'stamp.txt' not in changed:\n"
        "    sys.exit('error: role.md changed without a stamp bump')\n")

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.dir)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        Path("role.md").write_text("# Role\n\ntop\n\nbottom\n")
        Path("stamp.txt").write_text("0\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "base")
        self.git("update-ref", "refs/remotes/origin/main", "main")
        self.base = self.git("rev-parse", "main").strip()
        self.branch("gate", {"scripts/check_stamp.py": self.GATE})
        self.branch("bump", {"role.md": "# Role\n\ntop\nbumped\n\nbottom\n",
                             "stamp.txt": "1\n"})
        self.branch("plain", {"role.md": "# Role\n\ntop\n\nbottom\nplain\n"})
        self.landing = [(1, "gate"), (2, "bump"), (3, "plain")]

    def gates(self):
        union = p.union_tree(self.base, self.landing)[0]
        return p.introduced(self.base, union)

    def report(self):
        return "\n".join(p.per_member(self.base, self.landing, self.gates()))

    def test_the_gate_the_round_brings_is_the_one_reported_as_new(self):
        self.assertEqual(self.gates(), ["check_stamp.py"])

    def test_a_gate_already_on_main_is_not_new(self):
        self.git("checkout", "-q", "main")
        Path("scripts").mkdir(exist_ok=True)
        Path("scripts/check_stamp.py").write_text(self.GATE)
        self.git("add", "-A")
        self.git("commit", "-qm", "gate on main")
        self.git("update-ref", "refs/remotes/origin/main", "main")
        self.assertEqual(p.introduced(self.git("rev-parse", "main").strip(),
                                      self.git("rev-parse", "gate").strip()),
                         [])

    def test_the_union_is_green_on_the_gate_the_round_brings(self):
        # The defect this report exists for: one member's bump answers for the
        # round's whole content, so the union cannot see what CI will see.
        union = p.union_tree(self.base, self.landing)[0]
        self.assertEqual(p.run_checkers(union)["check_stamp.py"][0], 0)

    def test_the_member_that_does_not_bump_is_red_beside_it(self):
        out = self.report()
        self.assertRegex(out, r"#3\s+RED\s+check_stamp\.py")
        self.assertIn("without a stamp bump", out)

    def test_the_member_that_bumps_is_green(self):
        self.assertRegex(self.report(), r"#2\s+green")

    def test_the_gate_is_judged_as_the_one_group_it_is(self):
        self.assertIn("#1 (the gates themselves)", self.report())

    def test_the_folds_verdict_disclaims_its_own_members(self):
        self.assertIn("it is not any of theirs", self.report())

    def test_a_member_that_conflicts_with_the_gate_is_not_judged(self):
        self.branch("clash", {"scripts/check_stamp.py": "import sys\n"})
        self.landing.append((4, "clash"))
        # #4 brings the gate too, so it refuses inside the gate base itself.
        self.assertIn("does not assemble", self.report())

    def test_a_script_no_gate_reads_is_judged_singly_not_folded(self):
        self.branch("tool", {"scripts/make_report.py": "print('hi')\n"})
        self.landing.append((4, "tool"))
        out = self.report()
        self.assertNotIn("#4", out.splitlines()[1])  # absent from the fold label
        self.assertRegex(out, r"#4\s+green")

    def test_a_scripts_pr_that_also_changes_content_is_red_on_its_own(self):
        # Folded by path it hid behind the gate's verdict; the bump it owes is
        # its own, and CI will ask it for one.
        self.branch("tool-and-role", {"scripts/make_report.py": "print('hi')\n",
                                      "role.md": "# Role\n\ntop\n\nbottom\nx\n"})
        self.landing.append((4, "tool-and-role"))
        self.assertRegex(self.report(), r"#4\s+RED\s+check_stamp\.py")


if __name__ == "__main__":
    unittest.main()


class Convergence(unittest.TestCase):
    """What a round risks on `main`, which is a property of paths, not of PRs."""

    tracked = {"live.md", "also-live.md"}

    def test_a_pr_of_only_new_paths_is_additive(self):
        additive, converged = p.convergence(self.tracked, [(1, {"new.md"})])
        self.assertEqual((additive, converged), ([1], {}))

    def test_one_existing_path_is_enough_to_stop_being_additive(self):
        additive, converged = p.convergence(
            self.tracked, [(1, {"new.md", "live.md"})])
        self.assertEqual(additive, [])
        self.assertEqual(converged, {"live.md": [1]})

    def test_a_new_path_of_an_editing_pr_is_not_listed(self):
        _, converged = p.convergence(self.tracked, [(1, {"new.md", "live.md"})])
        self.assertNotIn("new.md", converged)

    def test_a_shared_path_names_every_pr_that_reaches_it(self):
        _, converged = p.convergence(
            self.tracked,
            [(3, {"live.md"}), (1, {"live.md"}), (2, {"also-live.md"})])
        self.assertEqual(converged["live.md"], [3, 1])
        self.assertEqual(converged["also-live.md"], [2])

    def test_an_empty_main_makes_the_whole_round_additive(self):
        additive, converged = p.convergence(
            set(), [(1, {"live.md"}), (2, {"new.md"})])
        self.assertEqual((additive, converged), ([1, 2], {}))


class Folds(unittest.TestCase):
    """A real round: two PRs converge on one live file, a third only adds."""

    def git(self, *args):
        return subprocess.run(("git",) + args, check=True, capture_output=True,
                              text=True).stdout

    def branch(self, name, path, text):
        self.git("checkout", "-q", "main")
        self.git("checkout", "-qb", name)
        Path(path).write_text(text)
        self.git("add", "-A")
        self.git("commit", "-qm", name)
        self.git("update-ref", f"refs/remotes/origin/{name}", "HEAD")
        self.git("checkout", "-q", "main")

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.dir)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        Path("role.md").write_text("# Role\n\ntop\n\nbottom\n")
        self.git("add", "role.md")
        self.git("commit", "-qm", "base")
        self.base = self.git("rev-parse", "main").strip()
        self.branch("one", "role.md", "# Role\n\ntop\nfirst rule\n\nbottom\n")
        self.branch("two", "role.md", "# Role\n\ntop\n\nbottom\nsecond rule\n")
        self.branch("three", "new.md", "# New\n")
        self.landing = [(1, "one"), (2, "two"), (3, "three")]
        self.files = {1: {"role.md"}, 2: {"role.md"}, 3: {"new.md"}}

    def report(self):
        return "\n".join(p.folds(self.base, self.landing, self.files))

    def test_the_additive_pr_is_named_and_its_path_is_not_a_risk(self):
        out = self.report()
        self.assertIn("#3", out.split("\n")[0])
        self.assertNotIn("new.md", out)

    def test_the_shared_file_names_both_prs_that_edit_it(self):
        self.assertIn("role.md  +2 -0  <- #1, #2", self.report())

    def test_the_named_commit_still_resolves_after_the_run(self):
        # The point of printing a command instead of 5,000 lines of diff: the
        # union has to survive the process that built it. A fold nobody can
        # read afterwards is the same as no report.
        sha = self.report().rsplit("git diff ", 1)[1].split()[1]
        fold = self.git("diff", self.base, sha, "--", "role.md")
        self.assertIn("+first rule", fold)
        self.assertIn("+second rule", fold)

    def test_a_round_that_does_not_assemble_reports_no_folds(self):
        # Same line, both sides: merge-tree refuses, and a refused round has no
        # tree to read. Reporting the smaller union as the round would name a
        # fold the operator is not landing.
        self.branch("clash", "role.md", "# Role\n\nrewritten\n\nbottom\n")
        self.landing.append((4, "clash"))
        self.files[4] = {"role.md"}
        report = self.report()
        self.assertIn("nothing is verifiable", report)
        self.assertNotIn("role.md  +", report)


    def late(self):
        """A PR that rewrites the line `one` edits, plus a file nobody shares.

        The shape of every deferred wave member: one contended file it will have
        to re-author, and content the round below never sees.
        """
        self.branch("late", "role.md", "# Role\n\nrewritten\n\nbottom\n")
        self.git("checkout", "-q", "late")
        Path("other.md").write_text("# Other\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "late-second-file")
        self.git("update-ref", "refs/remotes/origin/late", "HEAD")
        self.git("checkout", "-q", "main")
        return "\n".join(
            p.verify(self.base, [(1, "one"), (2, "two"), (4, "late")])[0])

    def test_the_refused_pr_names_the_file_its_rebase_will_re_author(self):
        report = self.late()
        self.assertIn("not assembled", report)
        self.assertIn("#4  role.md", report)

    def test_a_file_the_round_does_not_touch_is_not_reported_as_owed(self):
        # `other.md` exists only on the refused branch, so it merges clean and
        # is no part of the rebase cost. Naming it would inflate the estimate.
        self.assertNotIn("other.md", self.late())

    def test_a_round_that_assembles_reports_no_scope_at_all(self):
        lines, refused, _ = p.verify(self.base, [(1, "one"), (2, "two")])
        self.assertEqual([], refused)
        self.assertNotIn("will owe", "\n".join(lines))

    def test_scope_is_measured_against_the_tree_not_the_fold_position(self):
        # The answer is a property of what lands, so reversing the order the
        # assembled members were folded in must not change what #4 owes.
        self.late()

        def owed(members):
            return [ln for ln in p.verify(self.base, members)[0]
                    if ln.startswith("    #")]

        self.assertEqual(owed([(1, "one"), (2, "two"), (4, "late")]),
                         owed([(2, "two"), (1, "one"), (4, "late")]))
