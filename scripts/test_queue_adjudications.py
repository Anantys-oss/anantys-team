#!/usr/bin/env python3
"""Tests for queue_adjudications.py. Stdlib only: `python3 scripts/test_queue_adjudications.py`.

Two halves, for the reason `test_ownership_map.py` gives: the pure functions get
exhaustive cases because that is where the hunk arithmetic and the verdict live,
and `edges` gets a real repository with real branches because a suite that only
exercises the parsers proves they parse and says nothing about whether anything
ever hands them a real `git diff`.
"""

import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import queue_adjudications as qa


def git(repo, *args):
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"},
    )


class ParseHunks(unittest.TestCase):
    def test_replacement_keeps_its_span_and_added_lines(self):
        diff = "--- a/f.md\n+++ b/f.md\n@@ -10,3 +10,2 @@\n-a\n-b\n-c\n+x\n+y\n"
        self.assertEqual(qa.parse_hunks(diff), {"f.md": [(10, 3, ["x", "y"])]})

    def test_hunk_without_a_length_spans_one_line(self):
        diff = "--- a/f.md\n+++ b/f.md\n@@ -7 +7 @@\n-a\n+b\n"
        self.assertEqual(qa.parse_hunks(diff), {"f.md": [(7, 1, ["b"])]})

    def test_pure_insertion_is_dropped(self):
        # `-42,0` removes nothing, so two heads inserting different rules at the
        # same anchor both keep their text. Reporting that as a decision would
        # make every appended section look like a contradiction.
        diff = "--- a/f.md\n+++ b/f.md\n@@ -42,0 +43,2 @@\n+new\n+rule\n"
        self.assertEqual(qa.parse_hunks(diff), {})

    def test_deletion_with_no_replacement_still_spans_its_lines(self):
        diff = "--- a/f.md\n+++ b/f.md\n@@ -5,2 +4,0 @@\n-a\n-b\n"
        self.assertEqual(qa.parse_hunks(diff), {"f.md": [(5, 2, [])]})

    def test_several_files_and_hunks(self):
        diff = (
            "--- a/a.md\n+++ b/a.md\n@@ -1,2 +1,1 @@\n-x\n-y\n+p\n"
            "@@ -20 +19 @@\n-z\n+w\n"
            "--- a/b.md\n+++ b/b.md\n@@ -5 +5 @@\n-m\n+n\n"
        )
        self.assertEqual(
            qa.parse_hunks(diff),
            {"a.md": [(1, 2, ["p"]), (20, 1, ["w"])], "b.md": [(5, 1, ["n"])]},
        )

    def test_a_file_with_no_replacement_hunks_is_absent(self):
        diff = "--- a/f.md\n+++ b/f.md\n@@ -1,0 +2 @@\n+only an insertion\n"
        self.assertEqual(qa.parse_hunks(diff), {})

    def test_a_deleted_file_keeps_its_own_path(self):
        # `+++ /dev/null` names no subject, so it comes off the `--- a/` side.
        # Keyed on `+++ b/` alone the region lands under `a.md`, which never had
        # those lines, and `gone.md` vanishes from a report about who decides it.
        diff = (
            "diff --git a/a.md b/a.md\n--- a/a.md\n+++ b/a.md\n@@ -5 +5 @@\n-old\n+a rule\n"
            "diff --git a/gone.md b/gone.md\ndeleted file mode 100644\n"
            "--- a/gone.md\n+++ /dev/null\n@@ -1,3 +0,0 @@\n-x\n-y\n-z\n"
        )
        self.assertEqual(
            qa.parse_hunks(diff),
            {"a.md": [(5, 1, ["a rule"])], "gone.md": [(1, 3, [])]},
        )

    def test_a_new_file_asserts_nothing_about_the_base(self):
        diff = "--- /dev/null\n+++ b/new.md\n@@ -0,0 +1,2 @@\n+a\n+b\n"
        self.assertEqual(qa.parse_hunks(diff), {})

    def test_a_header_naming_neither_side_plainly_is_dropped_not_misfiled(self):
        # git quotes a path containing a space. Guessing is worse than losing it:
        # the previous file would be charged with a region it does not have.
        diff = (
            "--- a/a.md\n+++ b/a.md\n@@ -5 +5 @@\n-old\n+a rule\n"
            '--- "a/odd name.md"\n+++ "b/odd name.md"\n@@ -1 +1 @@\n-p\n+q\n'
        )
        self.assertEqual(qa.parse_hunks(diff), {"a.md": [(5, 1, ["a rule"])]})

    def test_a_removed_line_that_looks_like_a_header_does_not_steal_the_subject(self):
        # A deleted markdown line `-- note` renders as `--- note` in the diff.
        diff = (
            "--- a/a.md\n+++ b/a.md\n@@ -5,2 +5 @@\n--- note\n-old\n+a rule\n"
            "--- a/gone.md\n+++ /dev/null\n@@ -1 +0,0 @@\n-x\n"
        )
        self.assertEqual(
            qa.parse_hunks(diff),
            {"a.md": [(5, 2, ["a rule"])], "gone.md": [(1, 1, [])]},
        )

    def test_a_minus_line_belonging_to_a_dropped_hunk_is_not_captured(self):
        # The insertion hunk is skipped; the `+` under it must not leak into the
        # replacement hunk that follows, or the verdict is computed from text the
        # other head never saw.
        diff = (
            "--- a/f.md\n+++ b/f.md\n@@ -1,0 +2 @@\n+appended\n"
            "@@ -9 +11 @@\n-old\n+new\n"
        )
        self.assertEqual(qa.parse_hunks(diff), {"f.md": [(9, 1, ["new"])]})

    def test_empty_diff(self):
        self.assertEqual(qa.parse_hunks(""), {})


class Classify(unittest.TestCase):
    def test_same_text_is_identical(self):
        self.assertEqual(qa.classify(["version: 0.6.1"], ["version: 0.6.1"]), "identical")

    def test_reindented_text_is_identical(self):
        # A rewrap is not a product decision.
        self.assertEqual(qa.classify(["  a rule"], ["a rule  "]), "identical")

    def test_blank_lines_are_not_content(self):
        self.assertEqual(qa.classify(["a", "", "b"], ["a", "b"]), "identical")

    def test_a_superset_is_subsumed(self):
        self.assertEqual(qa.classify(["a"], ["a", "b"]), "subsumed")

    def test_a_subset_is_subsumed_in_either_order(self):
        self.assertEqual(qa.classify(["a", "b"], ["a"]), "subsumed")

    def test_each_asserting_its_own_line_is_divergent(self):
        self.assertEqual(qa.classify(["route it to §4"], ["record an annotation"]),
                         "divergent")

    def test_partial_overlap_is_divergent(self):
        # Sharing a line is not agreeing: each still says something the other
        # does not, so there is no resolution that keeps both.
        self.assertEqual(qa.classify(["shared", "mine"], ["shared", "yours"]),
                         "divergent")

    def test_a_deletion_against_a_replacement_is_subsumed(self):
        # One head removes the line, the other rewrites it. The empty side
        # asserts nothing, so taking the rewrite loses no text.
        self.assertEqual(qa.classify([], ["a rule"]), "subsumed")

    def test_two_deletions_are_identical(self):
        self.assertEqual(qa.classify([], []), "identical")


class Relocated(unittest.TestCase):
    def test_a_file_that_shrinks_is_a_move_out(self):
        self.assertEqual(qa.relocated("41\t429\tskill.md\n"), {"skill.md"})

    def test_a_file_that_grows_is_an_edit(self):
        self.assertEqual(qa.relocated("291\t48\tskill.md\n"), set())

    def test_equal_counts_are_an_edit_not_a_move(self):
        # A same-size rewrite is the ordinary in-place case.
        self.assertEqual(qa.relocated("10\t10\tskill.md\n"), set())

    def test_only_the_shrinking_paths_of_a_mixed_diff(self):
        stat = "41\t429\tskill.md\n400\t0\treference/run.md\n2\t9\tREADME.md\n"
        self.assertEqual(qa.relocated(stat), {"skill.md", "README.md"})

    def test_a_binary_file_has_no_counts_and_is_skipped(self):
        self.assertEqual(qa.relocated("-\t-\tlogo.png\n"), set())

    def test_a_rename_row_is_not_a_path_which_is_why_edges_disables_renames(self):
        # With rename detection on, git collapses the move-out into one row whose
        # third field is a transform, not a filename. Nothing from `parse_hunks`
        # ever equals it, so the relocation would silently never be found.
        self.assertEqual(qa.relocated("41\t429\tskill.md => reference/run.md\n"),
                         {"skill.md => reference/run.md"})

    def test_empty_numstat(self):
        self.assertEqual(qa.relocated(""), set())


class EdgesOverRealBranches(unittest.TestCase):
    """`edges` against a fixture *clone*: three heads cut from one base.

    The heads live on a remote and the working copy holds only `main`, because
    that is the shape `edges` runs in and the shape in which a bare branch name
    is not a revision. A single-repository fixture is the one topology where
    reading `headRefName` directly happens to work, which is why it did.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.origin = str(Path(self.tmp.name, "origin"))
        Path(self.origin).mkdir()
        git(self.origin, "init", "-q", "-b", "main")
        base = "\n".join(f"line {n}" for n in range(1, 11)) + "\n"
        Path(self.origin, "skill.md").write_text(base)
        Path(self.origin, "manifest.json").write_text('{"version": "0.6.0"}\n')
        git(self.origin, "add", "-A")
        git(self.origin, "commit", "-qm", "base")
        self._clone = None

    @property
    def repo(self):
        """A clone of the fixture remote, made once every head exists."""
        if self._clone is None:
            self._clone = str(Path(self.tmp.name, "work"))
            git(self.tmp.name, "clone", "-q", self.origin, self._clone)
        return self._clone

    def write(self, edits):
        for path, text in edits.items():
            target = Path(self.origin, path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)

    def head(self, name, edits, remove=()):
        git(self.origin, "checkout", "-q", "-b", name, "main")
        self.write(edits)
        for path in remove:
            git(self.origin, "rm", "-q", path)
        git(self.origin, "add", "-A")
        git(self.origin, "commit", "-qm", name)
        git(self.origin, "checkout", "-q", "main")
        return {"number": int(name[1:]), "headRefName": name, "title": name,
                "ref": f"origin/{name}"}

    def replaced(self, line, text):
        lines = [f"line {n}" for n in range(1, 11)]
        lines[line - 1] = text
        return "\n".join(lines) + "\n"

    def test_divergent_rewrites_of_one_line_are_reported(self):
        heads = [
            self.head("p1", {"skill.md": self.replaced(5, "route it to section 4")}),
            self.head("p2", {"skill.md": self.replaced(5, "record an annotation")}),
        ]
        rows = qa.edges("main", heads, repo=self.repo)
        self.assertEqual(len(rows), 1)
        self.assertEqual(
            (rows[0]["a"], rows[0]["b"], rows[0]["path"], rows[0]["line"],
             rows[0]["verdict"]),
            (1, 2, "skill.md", 5, "divergent"),
        )
        self.assertEqual(rows[0]["text_a"], ["route it to section 4"])

    def test_the_same_bump_on_a_shared_line_is_identical_not_a_cost(self):
        bumped = '{"version": "0.6.1"}\n'
        heads = [
            self.head("p1", {"manifest.json": bumped}),
            self.head("p2", {"manifest.json": bumped}),
        ]
        rows = qa.edges("main", heads, repo=self.repo)
        self.assertEqual([row["verdict"] for row in rows], ["identical"])

    def test_heads_editing_different_lines_produce_no_edge(self):
        heads = [
            self.head("p1", {"skill.md": self.replaced(2, "mine")}),
            self.head("p2", {"skill.md": self.replaced(9, "yours")}),
        ]
        self.assertEqual(qa.edges("main", heads, repo=self.repo), [])

    def test_heads_editing_different_files_produce_no_edge(self):
        heads = [
            self.head("p1", {"skill.md": self.replaced(5, "mine")}),
            self.head("p2", {"manifest.json": '{"version": "0.7.0"}\n'}),
        ]
        self.assertEqual(qa.edges("main", heads, repo=self.repo), [])

    def test_a_restructurer_collides_as_a_relocation_not_a_decision(self):
        # p1 lifts the file's prose out to a new path; p2 edits line 5 in place.
        # The texts differ, but p1 is not arguing for a different rule there.
        # p1 leaves a pointer where the section was, so its added text is a real
        # non-empty fragment — not the pure deletion `subsumed` already covers.
        moved = "line 1\nline 2\nsee reference/run.md\n"
        heads = [
            self.head("p1", {"skill.md": moved,
                             "reference/run.md": "the prose\n" * 9}),
            self.head("p2", {"skill.md": self.replaced(5, "a real rule")}),
        ]
        rows = qa.edges("main", heads, repo=self.repo)
        self.assertEqual([row["verdict"] for row in rows], ["relocation"])

    def test_a_relocation_that_matches_is_still_identical(self):
        # The move-out only reclassifies divergence; it never upgrades agreement
        # into work.
        heads = [
            self.head("p1", {"skill.md": "line 1\n", "reference/run.md": "x\n"}),
            self.head("p2", {"skill.md": "line 1\n", "reference/run.md": "x\n"}),
        ]
        self.assertEqual({row["verdict"] for row in qa.edges("main", heads, repo=self.repo)},
                         {"identical"})

    def test_every_pair_of_three_colliding_heads_is_an_edge(self):
        heads = [
            self.head("p1", {"skill.md": self.replaced(5, "one")}),
            self.head("p2", {"skill.md": self.replaced(5, "two")}),
            self.head("p3", {"skill.md": self.replaced(5, "three")}),
        ]
        rows = qa.edges("main", heads, repo=self.repo)
        self.assertEqual([(r["a"], r["b"]) for r in rows], [(1, 2), (1, 3), (2, 3)])
        self.assertTrue(all(r["verdict"] == "divergent" for r in rows))

    def stacked_on(self, parent, number, edits):
        git(self.origin, "checkout", "-q", "-b", f"p{number}", parent)
        self.write(edits)
        git(self.origin, "add", "-A")
        git(self.origin, "commit", "-qm", f"p{number}")
        git(self.origin, "checkout", "-q", "main")
        return {"number": number, "headRefName": f"p{number}", "title": f"p{number}",
                "ref": f"origin/p{number}"}

    def test_a_head_stacked_on_another_is_not_a_decision(self):
        # p2 is cut from p1 and rewrites the very line p1 rewrote. Their merge
        # base is `main`, so p2's diff carries p1's hunk and the pair reads as a
        # collision — but the descendant already contains the ancestor's text,
        # and there is nothing to decide. Ancestry, not the merge base, settles it.
        first = self.head("p1", {"skill.md": self.replaced(5, "one")})
        second = self.stacked_on("p1", 2, {"skill.md": self.replaced(5, "two")})
        self.assertEqual(qa.edges("main", [first, second], repo=self.repo), [])

    def test_a_sibling_of_a_stacked_head_still_adjudicates(self):
        # The skip is ancestry-scoped: p3 is unrelated to the p1/p2 stack, so
        # both of its edges survive.
        first = self.head("p1", {"skill.md": self.replaced(5, "one")})
        second = self.stacked_on("p1", 2, {"skill.md": self.replaced(5, "two")})
        third = self.head("p3", {"skill.md": self.replaced(5, "three")})
        rows = qa.edges("main", [first, second, third], repo=self.repo)
        self.assertEqual([(r["a"], r["b"]) for r in rows], [(1, 3), (2, 3)])
        self.assertTrue(all(r["verdict"] == "divergent" for r in rows))

    def test_a_stale_local_branch_of_the_same_name_does_not_decide_the_report(self):
        # The defect this fixture used to hide. `gh` names a branch on the
        # remote; a leftover local `p2` resolves too, and git prefers it. Here
        # the local copy agrees with p1, so reading it reports `identical` —
        # no decision — about two heads that in fact contradict each other.
        heads = [
            self.head("p1", {"skill.md": self.replaced(5, "route it to section 4")}),
            self.head("p2", {"skill.md": self.replaced(5, "record an annotation")}),
        ]
        repo = self.repo
        git(repo, "branch", "p2", "origin/p1")
        rows = qa.edges("main", heads, repo=repo)
        self.assertEqual([row["verdict"] for row in rows], ["divergent"])
        self.assertEqual(rows[0]["text_b"], ["record an annotation"])

    def test_a_move_out_git_calls_a_rename_still_collides(self):
        # p1 moves the whole file to a new path; p2 rewrites line 5 in place.
        # With rename detection on, p1's hunks are keyed under `reference/run.md`
        # and nothing is keyed under `skill.md`, so the pair shares no path and
        # the collision is reported as absent — the loudest possible silence,
        # because a resolver taking p1 loses p2's rule without a conflict.
        moved = "\n".join(f"line {n}" for n in range(1, 11)) + "\n"
        heads = [
            self.head("p1", {"reference/run.md": moved}, remove=["skill.md"]),
            self.head("p2", {"skill.md": self.replaced(5, "a real rule")}),
        ]
        rows = qa.edges("main", heads, repo=self.repo)
        self.assertEqual([(row["path"], row["verdict"]) for row in rows],
                         [("skill.md", "subsumed")])


class Report(unittest.TestCase):
    def row(self, verdict, **kw):
        base = {"a": 1, "b": 2, "path": "f.md", "line": 5, "verdict": verdict,
                "title_a": "first", "title_b": "second",
                "text_a": ["mine"], "text_b": ["yours"]}
        return {**base, **kw}

    def render(self, rows, show_all=False):
        out = io.StringIO()
        qa.report(rows, "origin/main", show_all, out)
        return out.getvalue()

    def test_counts_every_class_including_the_empty_ones(self):
        text = self.render([self.row("identical")])
        self.assertIn("1  identical", text)
        self.assertIn("0  divergent", text)

    def test_no_decisions_stops_after_the_counts(self):
        text = self.render([self.row("subsumed")])
        self.assertIn("0 divergent regions", text)
        self.assertNotIn("Decisions by file", text)

    def test_a_decision_prints_both_candidate_texts(self):
        text = self.render([self.row("divergent")])
        self.assertIn("f.md:5", text)
        self.assertIn("| mine", text)
        self.assertIn("| yours", text)

    def test_the_listing_is_capped_until_all(self):
        rows = [self.row("divergent", line=n) for n in range(1, 20)]
        self.assertIn("--all for the rest.", self.render(rows))
        self.assertNotIn("--all for the rest.", self.render(rows, show_all=True))

    def test_the_sample_reaches_a_rare_file_before_a_second_row_of_a_common_one(self):
        # In edge order the manifests' 194 version bumps fill the first screen.
        rows = [self.row("divergent", path="manifest.json", line=n)
                for n in range(1, 30)]
        rows.append(self.row("divergent", path="skill.md", line=7))
        text = self.render(rows)
        self.assertIn("skill.md:7", text)

    def test_all_still_lists_every_decision_after_the_round_robin(self):
        rows = [self.row("divergent", path="manifest.json", line=n)
                for n in range(1, 30)]
        rows.append(self.row("divergent", path="skill.md", line=7))
        text = self.render(rows, show_all=True)
        self.assertIn("(30 of 30 shown)", text)


if __name__ == "__main__":
    unittest.main()
