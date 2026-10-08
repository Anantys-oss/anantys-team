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


class RelocationPrecedence(unittest.TestCase):
    """A relocation edge is directed; degree-first always picks the bad way.

    The live queue's shape: one PR splits `anantys.qa/SKILL.md` into
    `reference/*.md` and therefore collides with every PR editing that file.
    Degree-first reads "collides with five others" as "land it first", which is
    exactly the direction that leaves those five with hunks whose anchors no
    longer exist anywhere in the file they patch.
    """

    def test_the_restructurer_lands_after_what_it_relocates(self):
        graph = edges((5, 15), (5, 16), (5, 19), (5, 31), (5, 33))
        without = p.waves([5, 15, 16, 19, 31, 33], graph)
        self.assertEqual(without[0], [5])  # degree-first, the expensive way
        order = p.waves([5, 15, 16, 19, 31, 33], graph,
                        [(15, 5), (16, 5), (19, 5), (31, 5), (33, 5)])
        self.assertEqual(order, [[15, 16, 19, 31, 33], [5]])

    def test_a_predecessor_in_the_same_wave_does_not_count_as_placed(self):
        # 2 may not join 1's wave merely because 1 was scheduled beside it.
        order = p.waves([1, 2], edges((1, 2)), [(1, 2)])
        self.assertEqual(order, [[1], [2]])

    def test_precedence_naming_an_absent_pr_is_ignored(self):
        # `stacked` drops contained PRs after the edges were built.
        self.assertEqual(p.waves([1, 2], {}, [(9, 1)]), [[1, 2]])

    def test_a_cycle_is_dropped_rather_than_deadlocking(self):
        order = p.waves([1, 2, 3], edges((1, 2)), [(1, 2), (2, 1)])
        self.assertEqual(sorted(n for wave in order for n in wave), [1, 2, 3])

    def test_every_pr_still_appears_exactly_once(self):
        order = p.waves([1, 2, 3, 4], edges((1, 2), (3, 4)), [(2, 1), (4, 3)])
        landed = [n for wave in order for n in wave]
        self.assertEqual(sorted(landed), [1, 2, 3, 4])

    def test_waves_stay_internally_conflict_free(self):
        graph = edges((1, 2), (2, 3), (1, 3))
        for wave in p.waves([1, 2, 3], graph, [(3, 1), (2, 3)]):
            for a in wave:
                for b in wave:
                    self.assertNotIn(frozenset((a, b)), graph)


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

    def test_precedence_weakens_it_to_some_earlier_wave_not_the_last(self):
        """What `--verify` actually needs, and all a constrained wave gives.

        A precedence-deferred PR waits on a predecessor that may itself be
        deferred, so it can skip past the wave it conflicts with. The
        conclusion is unaffected — a round is a cumulative *prefix*, so one
        conflicting pair anywhere below still makes it unassemblable — but
        "conflicts with the wave immediately below" was an artifact of the
        unconstrained greedy, not a property of the partition.
        """
        graph = edges((1, 2), (1, 3), (3, 4))
        order = p.waves([1, 2, 3, 4], graph, [(2, 1), (4, 3)])
        for i, wave in enumerate(order[1:], 1):
            earlier = {n for w in order[:i] for n in w}
            for pr in wave:
                self.assertTrue(
                    any(frozenset((pr, n)) in graph for n in earlier),
                    f"#{pr} in wave {i + 1} conflicts with nothing below it")

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


class Stacked(unittest.TestCase):
    """A real repo: a stack, a duplicate, and an unrelated branch.

    `stacked` is the one function that *removes* PRs from the plan, so a wrong
    answer here is a change the landing order never mentions again.
    """

    def git(self, *args):
        subprocess.run(("git",) + args, check=True, capture_output=True)

    def head(self, name, ref="HEAD"):
        """Publish `ref` as origin/<name> — `stacked` only reads remote refs."""
        oid = subprocess.run(["git", "rev-parse", ref], check=True,
                             capture_output=True, text=True).stdout.strip()
        self.git("update-ref", f"refs/remotes/origin/{name}", oid)

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.dir)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        Path("doc.md").write_text("# Doc\n")
        self.git("add", "doc.md")
        self.git("commit", "-qm", "base")

        self.git("checkout", "-qb", "lower")
        Path("doc.md").write_text("# Doc\n\nFirst.\n")
        self.git("commit", "-qam", "first")
        self.head("lower")
        # Same commit, opened twice — the duplicate the queue actually produces.
        self.head("copy")

        self.git("checkout", "-qb", "upper")
        Path("doc.md").write_text("# Doc\n\nFirst.\nSecond.\n")
        self.git("commit", "-qam", "second")
        self.head("upper")

        self.git("checkout", "-q", "main")
        self.git("checkout", "-qb", "apart")
        Path("other.md").write_text("Unrelated.\n")
        self.git("add", "other.md")
        self.git("commit", "-qm", "apart")
        self.head("apart")
        self.git("checkout", "-q", "main")

    def pr(self, *pairs):
        return [(n, ref, f"pr {n}", set()) for n, ref in pairs]

    def test_an_independent_pr_is_contained_by_nobody(self):
        self.assertEqual(p.stacked(self.pr((1, "lower"), (2, "apart"))), {})

    def test_the_ancestor_is_the_one_that_leaves_the_graph(self):
        self.assertEqual(p.stacked(self.pr((1, "lower"), (2, "upper"))), {1: 2})

    def test_arrival_order_does_not_decide_who_contains_whom(self):
        # #9 is cut from #3's head: the stack is the ancestry, not the numbering.
        self.assertEqual(p.stacked(self.pr((9, "lower"), (3, "upper"))), {9: 3})

    def test_a_duplicate_head_leaves_one_pr_standing(self):
        # Both directions of ancestry hold. Recorded both ways the caller drops
        # both and the change vanishes from every wave.
        self.assertEqual(p.stacked(self.pr((1, "lower"), (2, "copy"))), {2: 1})

    def test_the_survivor_of_a_duplicate_is_the_original(self):
        contained = p.stacked(self.pr((7, "copy"), (4, "lower")))
        self.assertEqual(contained, {7: 4})

    def test_a_duplicate_survivor_stays_in_the_queue(self):
        prs = self.pr((1, "lower"), (2, "copy"))
        contained = p.stacked(prs)
        kept = [n for n, _, _, _ in prs if n not in contained]
        self.assertEqual(kept, [1])

    def test_the_container_named_is_one_that_survives(self):
        # #2 duplicates #1 and #1 is contained in #3. Naming #1 as #2's
        # container points at a PR this same report has already dropped.
        contained = p.stacked(self.pr((1, "lower"), (2, "copy"), (3, "upper")))
        self.assertEqual(contained, {1: 3, 2: 3})



class Links(unittest.TestCase):
    """Where a relative link points, read from the file that writes it."""

    def test_a_sibling_link_resolves_beside_its_writer(self):
        self.assertEqual(p.links("docs/a.md", "see [b](./b.md)"), ["docs/b.md"])

    def test_a_link_is_to_a_file_not_to_a_section(self):
        # `]([^)]+\.md)` — the form every checker reaches for — matches nothing
        # here, so a deep link is silently counted as no link at all.
        self.assertEqual(p.links("docs/a.md", "see [b](./b.md#rules)"),
                         ["docs/b.md"])

    def test_a_link_climbs_out_of_its_directory(self):
        self.assertEqual(
            p.links("plugins/pkg/skills/s/SKILL.md", "[c](../../CONTRACT.md)"),
            ["plugins/pkg/CONTRACT.md"])

    def test_an_external_link_is_not_a_path_in_this_repo(self):
        self.assertEqual(p.links("a.md", "[x](https://example.com/y.md)"), [])

    def test_a_target_named_twice_is_one_target(self):
        self.assertEqual(p.links("a.md", "[x](./b.md) and [y](./b.md#z)"),
                         ["b.md"])

    def test_a_non_markdown_target_is_not_a_page(self):
        self.assertEqual(p.links("a.md", "[img](./d.png)"), [])


class LinkPrecedence(unittest.TestCase):
    """A link across two branches is an ordering edge with no conflict in it.

    The pair shares no path, so `merge-tree` is clean and the file intersection
    is empty: every other signal this report computes says the two are
    independent. Landing them in the wrong order puts prose on `main` that
    points at a file `main` does not have.
    """

    def git(self, *args):
        subprocess.run(("git",) + args, check=True, capture_output=True)

    def head(self, name):
        oid = subprocess.run(["git", "rev-parse", "HEAD"], check=True,
                             capture_output=True, text=True).stdout.strip()
        self.git("update-ref", f"refs/remotes/origin/{name}", oid)

    def branch(self, name, files):
        self.git("checkout", "-q", "main")
        self.git("checkout", "-qb", name)
        for path, body in files.items():
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(body)
        self.git("add", "-A")
        self.git("commit", "-qm", name)
        self.head(name)
        self.git("checkout", "-q", "main")

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.dir)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        Path("README.md").write_text("# Base\n")
        self.git("add", "README.md")
        self.git("commit", "-qm", "base")
        # The consumer cites a page; the provider is the branch that writes it.
        self.branch("cites", {"docs/role.md": "Read [why](./why.md) first.\n"})
        self.branch("writes", {"docs/why.md": "# Why\n"})
        self.branch("apart", {"other.md": "Unrelated.\n"})

    def pr(self, *triples):
        return [(n, ref, f"pr {n}", set(paths)) for n, ref, paths in triples]

    def test_the_provider_is_ordered_before_the_consumer(self):
        found = p.dangling(self.pr((1, "cites", ["docs/role.md"]),
                                   (2, "writes", ["docs/why.md"])))
        self.assertEqual(found, {(2, 1): {"docs/role.md": ["docs/why.md"]}})

    def test_the_pair_that_needs_ordering_has_no_conflict_to_find_it_by(self):
        prs = self.pr((1, "cites", ["docs/role.md"]),
                      (2, "writes", ["docs/why.md"]))
        self.assertEqual(p.conflicts("main", prs), {})

    def test_waves_place_the_provider_first(self):
        prs = self.pr((1, "cites", ["docs/role.md"]),
                      (2, "writes", ["docs/why.md"]))
        order = p.waves([n for n, _, _, _ in prs], {}, list(p.dangling(prs)))
        self.assertEqual(order, [[2], [1]])

    def test_a_link_nobody_provides_is_not_an_ordering_problem(self):
        # A template's links resolve in the consumer's repository. No open head
        # carries them, so requiring a provider drops them without a carve-out.
        self.branch("template", {
            "templates/plan.md": "Fill in [tasks](./tasks.md).\n"})
        found = p.dangling(self.pr((1, "template", ["templates/plan.md"]),
                                   (2, "apart", ["other.md"])))
        self.assertEqual(found, {})

    def test_a_link_its_own_head_resolves_is_not_an_edge(self):
        self.branch("whole", {"docs/role.md": "Read [why](./why.md) first.\n",
                              "docs/why.md": "# Why\n"})
        found = p.dangling(self.pr((1, "whole", ["docs/role.md",
                                                 "docs/why.md"]),
                                   (2, "writes", ["docs/why.md"])))
        self.assertEqual(found, {})

    def test_a_deleted_file_has_no_links_left_to_resolve(self):
        # `files` names every path the PR touched, removals included, so the
        # head it names them on need not still have them.
        self.branch("drops", {"docs/gone.md": "Read [why](./why.md).\n"})
        self.git("checkout", "-q", "drops")
        self.git("rm", "-q", "docs/gone.md")
        self.git("commit", "-qm", "drop it")
        self.head("drops")
        self.git("checkout", "-q", "main")
        found = p.dangling(self.pr((1, "drops", ["docs/gone.md"]),
                                   (2, "writes", ["docs/why.md"])))
        self.assertEqual(found, {})


class Clearing(unittest.TestCase):
    """A red round, and three candidates for clearing it.

    Two gates sit on `main`, so every fold has both. The round fails one of them;
    the question is what the report says about a candidate that satisfies that one
    and breaks the other. `clearing` emits an instruction, so its subject is the
    tree the instruction produces — not the gate that prompted it.
    """

    NEEDS = ("import pathlib, sys\n"
             "if not pathlib.Path('x.txt').exists():\n"
             "    sys.exit('error: x.txt is missing')\n")
    FORBIDS = ("import pathlib, sys\n"
               "if pathlib.Path('y.txt').exists():\n"
               "    sys.exit('error: y.txt must not exist')\n")

    def git(self, *args):
        return subprocess.run(("git",) + args, check=True, capture_output=True,
                              text=True).stdout

    def branch(self, name, files):
        self.git("checkout", "-q", "main")
        self.git("checkout", "-qb", name)
        for path, text in files.items():
            Path(path).parent.mkdir(parents=True, exist_ok=True)
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
        Path("scripts").mkdir()
        Path("scripts/check_needs_x.py").write_text(self.NEEDS)
        Path("scripts/check_forbids_y.py").write_text(self.FORBIDS)
        # `run_checkers` runs the suite as a gate, and `unittest discover` exits
        # non-zero on "NO TESTS RAN" — so a tree with checkers and no test module
        # is red on the suite, which would read here as a candidate breaking it.
        Path("scripts/test_nothing.py").write_text(
            "import unittest\n\n"
            "class T(unittest.TestCase):\n"
            "    def test_ok(self):\n        pass\n")
        Path("role.md").write_text("# Role\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "base")
        self.git("update-ref", "refs/remotes/origin/main", "main")
        self.base = self.git("rev-parse", "main").strip()
        self.branch("round", {"role.md": "# Role\n\nedited\n"})
        self.branch("both", {"x.txt": "here\n", "y.txt": "also here\n"})
        self.branch("only-x", {"x.txt": "here\n"})
        self.branch("neither", {"other.md": "unrelated\n"})
        self.landed = [(1, "round")]
        self.refs = {1: "round", 2: "both", 3: "only-x", 4: "neither"}
        self.failing = ["check_needs_x.py"]

    def report(self, remaining=(2, 3, 4), edges=None):
        return "\n".join(p.clearing(self.base, self.landed, list(remaining),
                                    self.failing, edges or {}, self.refs))

    def test_the_round_is_red_on_one_gate_and_green_on_the_other(self):
        results = p.run_checkers(p.union_tree(self.base, self.landed)[0])
        self.assertNotEqual(results["check_needs_x.py"][0], 0)
        self.assertEqual(results["check_forbids_y.py"][0], 0)

    def test_narrowing_to_the_failing_gate_calls_the_trade_a_fix(self):
        # The mechanism: asked only about the gate it satisfies, the candidate
        # that also breaks the other one is indistinguishable from the one that
        # does not. This is why `clearing` may not narrow.
        fold = p.union_tree(self.base, self.landed + [(2, "both")])[0]
        narrowed = p.run_checkers(fold, only=self.failing)
        self.assertEqual(narrowed["check_needs_x.py"][0], 0)
        self.assertNotIn("check_forbids_y.py", narrowed)

    def test_a_candidate_that_only_clears_is_the_move(self):
        line = [ln for ln in self.report().splitlines() if "#3" in ln]
        self.assertEqual(len(line), 1)
        self.assertIn("move it here", line[0])
        self.assertNotIn("trades", line[0])

    def test_a_candidate_that_breaks_another_gate_says_so(self):
        line = [ln for ln in self.report().splitlines() if "#2" in ln]
        self.assertEqual(len(line), 1)
        self.assertIn("clears check_needs_x.py", line[0])
        self.assertIn("check_forbids_y.py red", line[0])
        self.assertIn("trades", line[0])

    def test_a_candidate_that_clears_nothing_is_not_reported_as_clearing(self):
        self.assertNotIn("#4", self.report())

    def test_a_gate_already_red_in_the_round_is_not_counted_as_broken(self):
        # Only a green-to-red transition is the candidate's doing. A round that
        # was failing both gates must not have the second one read back to the
        # PR that fixed the first.
        self.branch("round-and-y", {"role.md": "# Role\n\nedited\n",
                                    "y.txt": "already here\n"})
        self.landed = [(5, "round-and-y")]
        self.refs[5] = "round-and-y"
        self.failing = ["check_needs_x.py", "check_forbids_y.py"]
        out = self.report(remaining=(3,))
        self.assertIn("#3 clears check_needs_x.py", out)
        self.assertNotIn("trades", out)
        self.assertIn("nothing in the remaining queue clears "
                      "check_forbids_y.py", out)

    def test_nothing_in_the_queue_clears_it_when_nothing_adds_the_file(self):
        self.assertIn("nothing in the remaining queue clears check_needs_x.py",
                      self.report(remaining=(4,)))

    def test_a_blocked_candidate_still_reports_what_else_it_breaks(self):
        out = self.report(remaining=(2,), edges=edges((1, 2)))
        self.assertIn("conflicts with #1", out)
        self.assertIn("check_forbids_y.py red", out)


class TheTrimIsNotTheFix(unittest.TestCase):
    """A blocked candidate is judged against the round it is actually tested in.

    Trimming the blockers out of the round is what makes a blocked candidate
    judgeable at all, but it also removes whatever those blockers brought — so a
    gate they were the cause of comes back green, and the candidate is standing
    there when it does. The control is the same shape as the one `clearing`
    already applies across gates: compare against the tree the candidate joined,
    not against the round it was never in.
    """

    git = Clearing.git
    branch = Clearing.branch

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.dir)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        Path("scripts").mkdir()
        Path("scripts/check_forbids_y.py").write_text(Clearing.FORBIDS)
        Path("scripts/test_nothing.py").write_text(
            "import unittest\n\n"
            "class T(unittest.TestCase):\n"
            "    def test_ok(self):\n        pass\n")
        Path("role.md").write_text("# Role\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "base")
        self.git("update-ref", "refs/remotes/origin/main", "main")
        self.base = self.git("rev-parse", "main").strip()
        # #1 is the round, and it is the reason the gate is red.
        self.branch("round", {"role.md": "# Role\n\nedited\n",
                              "y.txt": "here\n"})
        # #2 adds an unrelated file. It cannot clear anything.
        self.branch("bystander", {"other.md": "unrelated\n"})
        self.refs = {1: "round", 2: "bystander"}
        self.failing = ["check_forbids_y.py"]

    def report(self, edges_=None):
        return "\n".join(p.clearing(self.base, [(1, "round")], [2],
                                    self.failing, edges_ or {}, self.refs))

    def test_the_round_is_red_because_of_its_own_member(self):
        fold = p.union_tree(self.base, [(1, "round")])[0]
        self.assertNotEqual(
            p.run_checkers(fold)["check_forbids_y.py"][0], 0)

    def test_an_unblocked_bystander_clears_nothing(self):
        self.assertIn("nothing in the remaining queue clears "
                      "check_forbids_y.py", self.report())

    def test_a_blocked_bystander_clears_nothing_either(self):
        # Declared conflicting, so the round is trimmed to nothing and the gate
        # goes green with the bystander in the tree. The bystander did not do it.
        self.assertNotIn("#2 clears", self.report(edges((1, 2))))

    def test_the_removal_is_named_as_what_cleared_it(self):
        # And the red is not a defect in the assembled tree: a member of the
        # round is the cause, which is a landing-order fact the operator needs.
        out = self.report(edges((1, 2)))
        self.assertIn("nothing in the remaining queue clears "
                      "check_forbids_y.py", out)
        self.assertIn("the round without #1 is green on it", out)
        self.assertNotIn("a defect in the assembled tree", out)


class TheQueueIsAnInput(unittest.TestCase):
    """Every wave, round and verdict is a claim about the set collected first.

    Both shapes here are silent downstream: an unknown ref answers `merge-tree`
    with a conflict's exit status, and a truncated page answers `gh` with a
    perfectly well-formed queue.
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
        Path("doc.md").write_text("# Doc\n")
        self.git("add", "doc.md")
        self.git("commit", "-qm", "base")
        oid = subprocess.run(["git", "rev-parse", "HEAD"], check=True,
                             capture_output=True, text=True).stdout.strip()
        self.git("update-ref", "refs/remotes/origin/here", oid)

    def pr(self, *refs):
        return [(n, ref, f"pr {n}", set()) for n, ref in enumerate(refs, 1)]

    def test_a_fetched_head_is_reportable(self):
        self.assertIsNone(p.unreportable(self.pr("here"), 50))

    def test_an_unknown_head_is_refused_by_name(self):
        why = p.unreportable(self.pr("here", "never-fetched"), 50)
        self.assertIn("never-fetched", why)
        self.assertIn("#2", why)

    def test_merge_tree_cannot_tell_an_unknown_ref_from_a_conflict(self):
        # The reason the refusal above has to exist: `conflicts()` reads exit
        # status, and git spends status 1 on both answers.
        unknown = subprocess.run(
            ["git", "merge-tree", "--write-tree", "origin/here", "origin/nope"],
            capture_output=True)
        self.assertEqual(unknown.returncode, 1)

    def test_an_unknown_head_would_otherwise_conflict_with_everything(self):
        edges = p.conflicts("main", self.pr("here", "never-fetched"))
        self.assertEqual(edges, {frozenset((1, 2)): []})

    def test_a_full_page_is_read_as_a_truncated_queue(self):
        why = p.unreportable(self.pr("here", "here"), 2)
        self.assertIn("--limit 4", why)

    def test_a_short_page_is_the_whole_queue(self):
        self.assertIsNone(p.unreportable(self.pr("here"), 2))

    def test_truncation_is_reported_before_the_refs_are_read(self):
        # A truncated page's members are all fetchable, so checking refs first
        # would report nothing and let the subset through.
        self.assertIn("--limit", p.unreportable(self.pr("here", "nope"), 2))


class TheMergeBaseIsTheLanding(unittest.TestCase):
    """Two heads that share a lineage past `main`, each editing it further.

    The shape the queue produces constantly: a session branches off the last
    session's head to keep its work, both stay open, and they diverge. Neither
    contains the other, so both are in the plan — and their own merge base is
    the tip they share, which already holds the file they now disagree about.
    """

    def git(self, *args):
        subprocess.run(("git",) + args, check=True, capture_output=True)

    def head(self, name):
        oid = subprocess.run(["git", "rev-parse", "HEAD"], check=True,
                             capture_output=True, text=True).stdout.strip()
        self.git("update-ref", f"refs/remotes/origin/{name}", oid)

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.dir)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        Path("README.md").write_text("# Base\n")
        self.git("add", "README.md")
        self.git("commit", "-qm", "base")
        self.head("main")

        # `main` has no gate.py at all — both heads add one.
        self.git("checkout", "-qb", "shared")
        Path("gate.py").write_text("A\nB\nC\n")
        self.git("add", "gate.py")
        self.git("commit", "-qm", "the work both sessions share")

        # `first` carries the shared gate.py and goes on to do its own thing
        # elsewhere; `second` is the one that edits the gate further. From the
        # shared tip that is a one-sided change. From `main` they are two
        # branches adding the same new file with different contents.
        self.git("checkout", "-qb", "first")
        Path("notes.md").write_text("first\n")
        self.git("add", "notes.md")
        self.git("commit", "-qm", "first")
        self.head("first")

        self.git("checkout", "-q", "shared")
        self.git("checkout", "-qb", "second")
        Path("gate.py").write_text("A\nsecond\nC\n")
        self.git("commit", "-qam", "second")
        self.head("second")
        self.git("checkout", "-q", "main")

    def pr(self):
        return [(1, "first", "pr 1", {"gate.py"}),
                (2, "second", "pr 2", {"gate.py"})]

    def test_git_calls_the_pair_clean_on_the_base_it_infers(self):
        # Why the flag has to be explicit: with no `--merge-base`, git merges
        # from `shared`, which already has gate.py, and there is nothing left
        # to conflict over.
        inferred = subprocess.run(
            ["git", "merge-tree", "--write-tree", "origin/first",
             "origin/second"], capture_output=True)
        self.assertEqual(inferred.returncode, 0)

    def test_the_pair_conflicts_on_the_base_it_will_land_against(self):
        edges = p.conflicts("main", self.pr())
        self.assertEqual(edges, {frozenset((1, 2)): ["gate.py"]})

    def test_neither_head_is_dropped_as_contained(self):
        # `stacked` is the other place a shared lineage is read, and it is
        # right to keep both: each holds a commit the other does not.
        self.assertEqual(p.stacked(self.pr()), {})

    def test_the_wave_the_fold_refuses_is_not_a_wave(self):
        # The consequence, end to end: seated together on the inferred base,
        # the wave the operator is told to land in any order is one the fold
        # cannot even assemble.
        numbers = [n for n, _, _, _ in self.pr()]
        seated = p.waves(numbers, {})
        self.assertEqual(seated, [[1, 2]])
        _, _, refused = p.union_tree("main", [(1, "first"), (2, "second")])
        self.assertEqual(refused, [2])

        self.assertEqual(p.waves(numbers, p.conflicts("main", self.pr())),
                         [[1], [2]])


if __name__ == "__main__":
    unittest.main()
