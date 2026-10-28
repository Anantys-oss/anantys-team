#!/usr/bin/env python3
"""Tests for queue_redundancy — run: python3 -m unittest discover scripts

The pure functions are covered against synthetic line sets. The git-shelling
layer is covered against a real throwaway repository, because a suite that only
exercises the pure half is evidence that the impure half was never asked
anything: ``heads``, ``is_ancestor`` and the diff parsing of real ``git diff``
output are where a wrong ref format or a changed flag actually breaks.
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import queue_redundancy as q  # noqa: E402

LONG = "a sentence that is comfortably longer than the forty character floor"
LONG2 = "a second sentence, also well past the floor, with different words"
LONG3 = "a third distinct sentence of more than forty characters in total"


def patch(added=(), removed=()):
    return (set(added), set(removed))


def diff(added=(), removed=(), path="plugins/x/SKILL.md"):
    """A diff hunk with the noise a real one carries."""
    body = "".join(f"-{line}\n" for line in removed)
    body += "".join(f"+{line}\n" for line in added)
    return (f"--- a/{path}\n"
            f"+++ b/{path}\n"
            "@@ -1,2 +1,4 @@\n"
            " a context line that is itself long enough to pass the floor\n"
            + body)


class Substantive(unittest.TestCase):
    def test_splits_added_from_removed(self):
        self.assertEqual(q.substantive(diff([LONG], [LONG2])),
                         ({LONG}, {LONG2}))

    def test_drops_the_context_line_that_passes_the_floor(self):
        added, removed = q.substantive(diff([LONG]))
        self.assertEqual(added, {LONG})
        self.assertEqual(removed, set())

    def test_drops_the_file_headers_that_start_like_content(self):
        added, removed = q.substantive(diff([LONG], path="a" * 80))
        self.assertEqual(added, {LONG})
        self.assertEqual(removed, set())

    def test_drops_lines_under_the_floor(self):
        self.assertEqual(q.substantive(diff(["}", "version: 0.6.1"])),
                         (set(), set()))

    def test_floor_is_configurable(self):
        self.assertEqual(q.substantive(diff(["short"]), floor=3),
                         ({"short"}, set()))

    def test_strips_surrounding_whitespace_so_reindentation_still_matches(self):
        a, _ = q.substantive(diff([f"    {LONG}"]))
        b, _ = q.substantive(diff([f"\t\t{LONG}"]))
        self.assertEqual(a, b)

    def test_empty_diff_is_two_empty_sets(self):
        self.assertEqual(q.substantive(""), (set(), set()))


class Contains(unittest.TestCase):
    def test_superset_of_added_lines_contains(self):
        self.assertTrue(q.contains(patch([LONG, LONG2]), patch([LONG])))

    def test_equal_patches_do_not_contain_either_way(self):
        a, b = patch([LONG]), patch([LONG])
        self.assertFalse(q.contains(a, b))
        self.assertFalse(q.contains(b, a))

    def test_an_unshared_added_line_defeats_containment(self):
        self.assertFalse(q.contains(patch([LONG]), patch([LONG, LONG2])))

    def test_an_unshared_removed_line_defeats_containment(self):
        self.assertFalse(
            q.contains(patch([LONG, LONG2]), patch([LONG], [LONG3])))

    def test_removals_must_be_contained_too(self):
        self.assertTrue(
            q.contains(patch([LONG, LONG2], [LONG3]), patch([LONG], [LONG3])))

    def test_an_empty_patch_is_never_contained(self):
        self.assertFalse(q.contains(patch([LONG]), patch()))

    def test_growth_in_removals_alone_is_containment(self):
        self.assertTrue(
            q.contains(patch([LONG], [LONG2, LONG3]), patch([LONG], [LONG2])))


class Identical(unittest.TestCase):
    def test_same_lines_are_identical(self):
        self.assertTrue(q.identical(patch([LONG]), patch([LONG])))

    def test_different_lines_are_not(self):
        self.assertFalse(q.identical(patch([LONG]), patch([LONG2])))

    def test_two_empty_patches_are_not_reported_as_duplicates(self):
        self.assertFalse(q.identical(patch(), patch()))


class Overlap(unittest.TestCase):
    def test_full_overlap_of_the_smaller_head_reads_at_ceiling(self):
        cov, jac = q.overlap(patch([LONG, LONG2]), patch([LONG]))
        self.assertEqual(cov, 1.0)
        self.assertEqual(jac, 0.5)

    def test_identical_heads_score_one_on_both(self):
        self.assertEqual(q.overlap(patch([LONG]), patch([LONG])), (1.0, 1.0))

    def test_disjoint_heads_score_zero(self):
        self.assertEqual(q.overlap(patch([LONG]), patch([LONG2])), (0.0, 0.0))

    def test_an_empty_patch_scores_zero_rather_than_dividing_by_it(self):
        self.assertEqual(q.overlap(patch(), patch([LONG])), (0.0, 0.0))


class FindContainment(unittest.TestCase):
    def test_reports_the_pair_in_inner_outer_order(self):
        patches = {"small": patch([LONG]), "big": patch([LONG, LONG2])}
        self.assertEqual(q.find_containment(patches), [("small", "big")])

    def test_a_chain_reports_every_container(self):
        patches = {"a": patch([LONG]),
                   "b": patch([LONG, LONG2]),
                   "c": patch([LONG, LONG2, LONG3])}
        self.assertEqual(q.find_containment(patches),
                         [("a", "b"), ("a", "c"), ("b", "c")])

    def test_identical_heads_produce_no_containment_row(self):
        patches = {"a": patch([LONG]), "b": patch([LONG])}
        self.assertEqual(q.find_containment(patches), [])

    def test_sorted_by_the_contained_head_size(self):
        patches = {"one": patch([LONG]),
                   "two": patch([LONG, LONG2]),
                   "all": patch([LONG, LONG2, LONG3])}
        self.assertEqual([inner for inner, _ in q.find_containment(patches)][0],
                         "one")


class FindNear(unittest.TestCase):
    def test_a_reworded_pair_is_near_duplicate(self):
        patches = {"a": patch([LONG, LONG2]), "b": patch([LONG, LONG3])}
        self.assertEqual(q.find_near(patches, near=0.3),
                         [(0.5, 0.33, "a", "b")])

    def test_a_contained_pair_is_not_reported_as_near(self):
        patches = {"a": patch([LONG]), "b": patch([LONG, LONG2])}
        self.assertEqual(q.find_near(patches, near=0.1), [])

    def test_below_threshold_is_dropped(self):
        patches = {"a": patch([LONG, LONG2]), "b": patch([LONG, LONG3])}
        self.assertEqual(q.find_near(patches, near=0.9), [])

    def test_a_head_inside_a_fold_is_kept_out_by_the_jaccard_floor(self):
        fold = patch([LONG, LONG2, LONG3, "x" * 60, "y" * 60])
        patches = {"fold": fold, "head": patch([LONG, "z" * 60])}
        self.assertEqual(q.find_near(patches, near=0.6), [])

    def test_own_measure_drops_a_pair_that_only_shares_its_base(self):
        """Two siblings off one deep base: identical base..head, disjoint work."""
        patches = {"a": patch([LONG, LONG2]), "b": patch([LONG, LONG2])}
        own = lambda a, b: (patch(["a" * 60]), patch(["b" * 60]))
        self.assertEqual(q.find_near(patches, near=0.6), [(1.0, 1.0, "a", "b")])
        self.assertEqual(q.find_near(patches, near=0.6, own=own), [])

    def test_own_measure_drops_a_head_paired_with_its_descendant(self):
        """An empty own-patch means the head IS the merge-base: ancestry."""
        patches = {"a": patch([LONG, LONG2]), "b": patch([LONG, LONG3])}
        own = lambda a, b: (patch([]), patch([LONG3]))
        self.assertEqual(q.find_near(patches, near=0.3, own=own), [])

    def test_own_measure_keeps_a_genuine_rewording_and_rescores_it(self):
        patches = {"a": patch([LONG, LONG2]), "b": patch([LONG, LONG3])}
        own = lambda a, b: (patch([LONG2]), patch([LONG2, LONG3]))
        self.assertEqual(q.find_near(patches, near=0.3, own=own),
                         [(1.0, 0.5, "a", "b")])

    def test_the_cheap_filter_still_gates_which_pairs_are_re_measured(self):
        """Below the base-relative threshold a pair is never own-measured."""
        calls = []

        def own(a, b):
            calls.append((a, b))
            return patch([LONG]), patch([LONG])

        patches = {"a": patch([LONG, LONG2]), "b": patch([LONG, LONG3])}
        self.assertEqual(q.find_near(patches, near=0.9, own=own), [])
        self.assertEqual(calls, [])


class Report(unittest.TestCase):
    def setUp(self):
        self.patches = {"origin/koan/small": patch([LONG]),
                        "origin/koan/big": patch([LONG, LONG2]),
                        "origin/koan/twin": patch([LONG3])}
        self.prs = {"koan/small": 5, "koan/big": 90}

    def test_the_pr_lookup_keys_on_the_branch_not_the_remote_ref(self):
        # A head read as an orphan when a PR exists is the one false row this
        # report must not invent, so pin the key the lookup uses.
        self.assertEqual(q.label("origin/koan/small", "origin/koan", self.prs),
                         "#5 small")

    def render(self, **kw):
        kw.setdefault("ancestry", lambda a, b: False)
        return "\n".join(q.report(self.patches, "origin/koan", self.prs, **kw))

    def test_names_a_head_by_its_pr_number(self):
        self.assertIn("#5 small", self.render())

    def test_names_an_orphan_head_as_having_no_pr(self):
        self.assertIn("(no PR) twin", self.render())

    def test_reports_the_containment_direction(self):
        self.assertIn("#5 small (1 lines)  in  #90 big", self.render())

    def test_marks_ancestry_when_it_holds(self):
        self.assertIn("[ancestor]", self.render(ancestry=lambda a, b: True))

    def test_omits_the_ancestry_marker_otherwise(self):
        self.assertNotIn("[ancestor]", self.render())

    def test_lists_an_orphan_head_in_its_own_section(self):
        out = self.render()
        self.assertIn("## Heads with no open PR (1)", out)
        self.assertIn("(no PR) twin", out)

    def test_marks_an_orphan_that_another_head_already_contains(self):
        self.patches["origin/koan/twin"] = patch([LONG])
        self.assertIn("(no PR) twin (1 lines)  — contained above", self.render())

    def test_says_the_orphan_check_did_not_run_when_gh_is_silent(self):
        self.prs = {}
        self.assertIn("`gh` did not answer", self.render())

    def test_counts_distinct_contained_heads_not_pairs(self):
        self.patches["origin/koan/bigger"] = patch([LONG, LONG2, LONG3])
        self.assertIn("## Contained heads (3)", self.render())

    def test_ranks_containers_by_heads_absorbed(self):
        self.patches["origin/koan/bigger"] = patch([LONG, LONG2, LONG3])
        lines = self.render().splitlines()
        ranked = [l for l in lines if l.startswith("    ") and " bigger" in l
                  or l.startswith("    ") and " big" in l]
        self.assertTrue(ranked[0].strip().startswith("3"))

    def test_an_empty_section_says_none_rather_than_nothing(self):
        self.patches = {"origin/koan/a": patch([LONG])}
        out = self.render()
        self.assertIn("## Identical patches (0)", out)
        self.assertIn("None.", out)

    def test_reports_identical_patches_as_their_own_section(self):
        self.patches["origin/koan/copy"] = patch([LONG3])
        self.assertIn("(no PR) copy", self.render())
        self.assertIn("## Identical patches (1)", self.render())


class GitLayer(unittest.TestCase):
    """The impure half, against a real repository."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(
            prefix="koan-queue-redundancy-", dir=os.environ.get("TMPDIR"))
        cls.repo = Path(cls.tmp.name) / "repo"
        cls.repo.mkdir()
        cls.git_cmd("init", "-q", "-b", "main")
        cls.git_cmd("config", "user.email", "t@example.com")
        cls.git_cmd("config", "user.name", "t")
        (cls.repo / "f.md").write_text("a baseline line of ample length for the floor\n")
        cls.git_cmd("add", "-A")
        cls.git_cmd("commit", "-qm", "base")
        # A one-line change, and a branch that is its descendant plus one more.
        cls.git_cmd("checkout", "-q", "-b", "small")
        (cls.repo / "f.md").write_text(
            f"a baseline line of ample length for the floor\n{LONG}\n")
        cls.git_cmd("commit", "-qam", "small")
        cls.git_cmd("checkout", "-q", "-b", "big")
        (cls.repo / "f.md").write_text(
            f"a baseline line of ample length for the floor\n{LONG}\n{LONG2}\n")
        cls.git_cmd("commit", "-qam", "big")
        # An unrelated branch off main, so not every pair is contained.
        cls.git_cmd("checkout", "-q", "-b", "other", "main")
        (cls.repo / "g.md").write_text(f"{LONG3}\n")
        cls.git_cmd("add", "-A")
        cls.git_cmd("commit", "-qm", "other")
        cls.git_cmd("checkout", "-q", "main")
        # Publish them under a remote prefix the sweep can find.
        cls.git_cmd("remote", "add", "origin", str(cls.repo))
        cls.git_cmd("fetch", "-q", "origin",
                "small:refs/remotes/origin/koan/small",
                "big:refs/remotes/origin/koan/big",
                "other:refs/remotes/origin/koan/other")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @classmethod
    def git_cmd(cls, *args):
        subprocess.run(("git",) + args, cwd=cls.repo, check=True,
                       capture_output=True, text=True)

    def setUp(self):
        self.cwd = os.getcwd()
        os.chdir(self.repo)

    def tearDown(self):
        os.chdir(self.cwd)

    def test_heads_finds_the_refs_under_the_prefix(self):
        self.assertEqual(sorted(q.heads("origin/koan")),
                         ["origin/koan/big", "origin/koan/other",
                          "origin/koan/small"])

    def test_heads_is_empty_for_an_unused_prefix(self):
        self.assertEqual(q.heads("origin/nope"), [])

    def test_is_ancestor_agrees_with_the_commit_graph(self):
        self.assertTrue(q.is_ancestor("origin/koan/small", "origin/koan/big"))
        self.assertFalse(q.is_ancestor("origin/koan/big", "origin/koan/small"))
        self.assertFalse(q.is_ancestor("origin/koan/other", "origin/koan/big"))

    def test_real_diff_output_parses_into_the_expected_sets(self):
        added, removed = q.substantive(q.git("diff", "main..origin/koan/big"))
        self.assertEqual(added, {LONG, LONG2})
        self.assertEqual(removed, set())

    def test_containment_holds_end_to_end_on_real_branches(self):
        patches = {ref: q.substantive(q.git("diff", f"main..{ref}"))
                   for ref in q.heads("origin/koan")}
        self.assertEqual(q.find_containment(patches),
                         [("origin/koan/small", "origin/koan/big")])

    def test_the_unrelated_branch_is_not_a_container(self):
        patches = {ref: q.substantive(q.git("diff", f"main..{ref}"))
                   for ref in q.heads("origin/koan")}
        containers = {outer for _, outer in q.find_containment(patches)}
        self.assertNotIn("origin/koan/other", containers)

    def test_own_patches_measures_each_head_from_the_shared_commit(self):
        a, b = q.own_patches("origin/koan/big", "origin/koan/other")
        # merge-base is main: each head's own work, and it is disjoint.
        self.assertEqual(a[0], {LONG, LONG2})
        self.assertEqual(b[0], {LONG3})

    def test_own_patches_is_empty_for_the_ancestor_of_the_pair(self):
        a, b = q.own_patches("origin/koan/small", "origin/koan/big")
        self.assertEqual(a[0], set())
        self.assertEqual(b[0], {LONG2})

    def test_main_runs_against_a_real_repo_and_prints_the_row(self):
        script = str(Path(__file__).parent / "queue_redundancy.py")
        out = subprocess.run((sys.executable, script), cwd=self.repo,
                             capture_output=True, text=True, check=True).stdout
        self.assertIn("3 heads under origin/koan/", out)
        self.assertIn("small", out)
        self.assertIn("in", out)


if __name__ == "__main__":
    unittest.main()
