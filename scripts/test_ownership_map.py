#!/usr/bin/env python3
"""Tests for ownership_map.py.

Two halves on purpose. The pure parsers get exhaustive cases — they are where
the hunk arithmetic lives. The git-shelling half gets a real fixture repository
with a real base and two real branches, because a suite that only exercises the
pure functions proves the parser works and says nothing about whether anything
ever calls it with a real `git diff`.
"""

import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import ownership_map as om


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


class ParseDiffOldLines(unittest.TestCase):
    def test_replacement_hunk_claims_every_old_line(self):
        diff = "--- a/f.md\n+++ b/f.md\n@@ -10,3 +10,2 @@\n-a\n-b\n-c\n+x\n+y\n"
        self.assertEqual(om.parse_diff_old_lines(diff), {"f.md": {10, 11, 12}})

    def test_hunk_without_a_length_claims_one_line(self):
        diff = "--- a/f.md\n+++ b/f.md\n@@ -7 +7 @@\n-a\n+b\n"
        self.assertEqual(om.parse_diff_old_lines(diff), {"f.md": {7}})

    def test_pure_insertion_claims_its_anchor(self):
        # `-42,0` replaces nothing. Recording no line would report an appended
        # rule as a section nobody claims, which is the false negative that
        # would make the report lie in the dangerous direction.
        diff = "--- a/f.md\n+++ b/f.md\n@@ -42,0 +43,2 @@\n+new\n+rule\n"
        self.assertEqual(om.parse_diff_old_lines(diff), {"f.md": {42}})

    def test_several_files_and_hunks(self):
        diff = (
            "--- a/a.md\n+++ b/a.md\n@@ -1,2 +1,2 @@\n-x\n-y\n+p\n+q\n"
            "@@ -20,1 +20,1 @@\n-z\n+w\n"
            "--- a/b.md\n+++ b/b.md\n@@ -5,1 +5,1 @@\n-m\n+n\n"
        )
        self.assertEqual(
            om.parse_diff_old_lines(diff), {"a.md": {1, 2, 20}, "b.md": {5}}
        )

    def test_a_file_with_no_hunks_is_not_reported(self):
        # A pure rename or mode change yields a `+++ b/` with nothing under it.
        diff = "--- a/f.md\n+++ b/f.md\n"
        self.assertEqual(om.parse_diff_old_lines(diff), {})

    def test_empty_diff(self):
        self.assertEqual(om.parse_diff_old_lines(""), {})

    def test_added_file_has_no_base_side_lines(self):
        diff = "--- /dev/null\n+++ b/new.py\n@@ -0,0 +1,3 @@\n+a\n+b\n+c\n"
        # Anchor 0 is recorded; the file is absent from the base, so a section
        # report over it finds nothing, which is correct.
        self.assertEqual(om.parse_diff_old_lines(diff), {"new.py": {0}})

    def test_body_text_resembling_a_hunk_header_is_not_a_hunk(self):
        # A diff that adds documentation *about* diffs. The added line starts
        # with `+`, so it can never be mistaken for a header, and must not be.
        diff = "--- a/f.md\n+++ b/f.md\n@@ -3,1 +3,2 @@\n-x\n+@@ -99,5 +99,5 @@\n"
        self.assertEqual(om.parse_diff_old_lines(diff), {"f.md": {3}})


class Sections(unittest.TestCase):
    def test_frontmatter_before_the_first_heading_is_its_own_section(self):
        text = "---\nname: x\n---\n\n## Mission\nbody\n"
        self.assertEqual(
            om.sections(text),
            [("(frontmatter / preamble)", 1, 4), ("Mission", 5, 6)],
        )

    def test_consecutive_headings_and_the_last_section_reaches_eof(self):
        text = "# A\n## B\ntext\n## C\nmore\n"
        self.assertEqual(om.sections(text), [("A", 1, 1), ("B", 2, 3), ("C", 4, 5)])

    def test_a_file_starting_with_a_heading_has_no_preamble(self):
        self.assertEqual(om.sections("# Top\nx\n"), [("Top", 1, 2)])

    def test_a_file_with_no_heading_is_one_whole_file_section(self):
        self.assertEqual(om.sections("just\ntext\n"), [("(whole file)", 1, 2)])

    def test_empty_file(self):
        self.assertEqual(om.sections(""), [])

    def test_a_fenced_hash_comment_is_not_a_heading(self):
        # Shell and python samples are common in these skills; `#!/bin/sh` and
        # `# a comment` must not split a section.
        text = "## Code\n```sh\n#!/bin/sh\n# a comment\n```\ntail\n"
        self.assertEqual(om.sections(text), [("Code", 1, 6)])

    def test_a_fenced_output_template_does_not_become_a_dozen_sections(self):
        # This is the shape of anantys.ops Phase 5, which embeds its whole
        # report skeleton in a fence. Read inside it and the one real section
        # fragments, and every line range after it belongs to the wrong name.
        text = (
            "## Phase 5: Analysis & Report\n"
            "Compile findings into a report.\n"
            "```\n"
            "# SEO Audit Report\n"
            "## 1. Current Performance Summary\n"
            "## 2. Landing Page Health\n"
            "```\n"
            "## Phase 6: Update Status File\n"
            "body\n"
        )
        self.assertEqual(
            om.sections(text),
            [("Phase 5: Analysis & Report", 1, 7), ("Phase 6: Update Status File", 8, 9)],
        )

    def test_a_tilde_fence_counts_too(self):
        self.assertEqual(om.sections("## A\n~~~\n## fake\n~~~\n"), [("A", 1, 4)])

    def test_an_unclosed_fence_swallows_the_rest_rather_than_inventing_sections(self):
        # Under-reporting sections is recoverable; inventing one with a bogus
        # line range silently misattributes every head after it.
        self.assertEqual(om.sections("## A\n```\n## not a heading\n"), [("A", 1, 3)])

    def test_six_hashes_is_a_heading_and_seven_is_not(self):
        self.assertEqual([t for t, _, _ in om.sections("###### Deep\nx\n")], ["Deep"])
        self.assertEqual(
            [t for t, _, _ in om.sections("####### Nope\nx\n")], ["(whole file)"]
        )


class Compact(unittest.TestCase):
    def test_runs_collapse_and_singletons_stay(self):
        self.assertEqual(om.compact({1, 2, 3, 7, 10, 11}), "1-3, 7, 10-11")

    def test_a_single_line(self):
        self.assertEqual(om.compact({5}), "5")

    def test_empty(self):
        self.assertEqual(om.compact(set()), "")


class Pct(unittest.TestCase):
    def test_a_zero_denominator_is_not_a_division(self):
        self.assertEqual(om.pct(0, 0), "—")

    def test_rounds_to_a_whole_number(self):
        self.assertEqual(om.pct(1, 3), "33%")
        self.assertEqual(om.pct(2, 3), "67%")


class AgainstARealRepository(unittest.TestCase):
    """The half the pure tests cannot reach: does this work on real `git diff`?"""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.repo = cls.tmp.name
        git(cls.repo, "init", "-q", "-b", "main")
        role = Path(cls.repo, "role.md")
        role.write_text(
            "---\nname: r\nallowed-tools: Read\n---\n"
            "\n## Mission\nmission body\n"
            "\n## Rules\n- one\n- two\n"
        )
        Path(cls.repo, "other.md").write_text("untouched\nby\nanyone\n")
        git(cls.repo, "add", "-A")
        git(cls.repo, "commit", "-qm", "base")

        # Head A rewrites the grant line (line 3) only.
        git(cls.repo, "checkout", "-q", "-b", "head-a")
        role.write_text(role.read_text().replace("allowed-tools: Read", "allowed-tools: Read, Write"))
        git(cls.repo, "commit", "-qam", "a")

        # Head B appends a rule — a pure insertion at the end of Rules.
        git(cls.repo, "checkout", "-q", "main")
        git(cls.repo, "checkout", "-q", "-b", "head-b")
        role.write_text(role.read_text() + "- three\n")
        git(cls.repo, "commit", "-qam", "b")
        git(cls.repo, "checkout", "-q", "main")

        cls.heads = [
            {"number": 1, "head": "head-a", "title": "widen the grant"},
            {"number": 2, "head": "head-b", "title": "append a rule"},
        ]
        # `claims` reads `origin/<head>`; in a repo with no remote, point the
        # refs at themselves so the same code path runs unmodified.
        for h in ("head-a", "head-b"):
            git(cls.repo, "update-ref", f"refs/remotes/origin/{h}", h)
        cls.by_head = om.claims(cls.repo, "main", cls.heads)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_a_grant_rewrite_is_located_on_the_grant_line(self):
        self.assertEqual(self.by_head["head-a"], {"role.md": {3}})

    def test_an_appended_rule_claims_the_end_of_the_file(self):
        # 11 lines in the base; the insertion anchors on the last one.
        self.assertEqual(self.by_head["head-b"], {"role.md": {11}})

    def test_tracked_files_come_from_the_base_ref(self):
        self.assertEqual(om.tracked_files(self.repo, "main"), ["other.md", "role.md"])

    def test_the_section_report_attributes_each_head_to_its_own_section(self):
        buf = io.StringIO()
        om.report_sections(self.repo, "main", self.heads, self.by_head, "role.md", buf)
        out = buf.getvalue()
        self.assertRegex(out, r"\| 1-5 \| \(frontmatter / preamble\) \| 1 \| #1 \|")
        self.assertRegex(out, r"\| 6-8 \| Mission \| 0 \| — \|")
        self.assertRegex(out, r"\| 9-11 \| Rules \| 1 \| #2 \|")

    def test_the_summary_ranks_the_unclaimed_file_last(self):
        buf = io.StringIO()
        om.report_summary(self.repo, "main", self.heads, self.by_head, buf)
        lines = [l for l in buf.getvalue().splitlines() if l.startswith("| ")]
        self.assertIn("`role.md`", lines[-2])
        self.assertIn("`other.md`", lines[-1])
        self.assertIn("0/3", lines[-1])

    def test_a_range_no_head_claims_says_the_floor_is_zero(self):
        buf = io.StringIO()
        om.report_lines(self.repo, "main", self.heads, self.by_head, "role.md", 6, 8, buf)
        self.assertIn("No open head claims these lines", buf.getvalue())
        self.assertIn("without touching the lines that state it", buf.getvalue())

    def test_a_claimed_range_names_the_pr_and_its_lines(self):
        buf = io.StringIO()
        om.report_lines(self.repo, "main", self.heads, self.by_head, "role.md", 1, 4, buf)
        out = buf.getvalue()
        self.assertIn("#1 head-a", out)
        self.assertIn("widen the grant", out)
        self.assertIn("claims: 3", out)
        self.assertNotIn("head-b", out)

    def test_a_path_absent_from_the_base_is_reported_not_crashed(self):
        buf = io.StringIO()
        om.report_sections(self.repo, "main", self.heads, self.by_head, "gone.md", buf)
        self.assertIn("not in main", buf.getvalue())

    def test_run_returns_empty_on_a_failing_command(self):
        self.assertEqual(om.run(["git", "cat-file", "-p", "nope"], cwd=self.repo), "")


if __name__ == "__main__":
    unittest.main()
