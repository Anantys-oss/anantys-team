#!/usr/bin/env python3
"""Fixture tests for fold_absorbs — run: python3 -m unittest discover scripts"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fold_absorbs as f  # noqa: E402


class Verdict(unittest.TestCase):
    def test_unchanged_tree_is_absorbed(self):
        self.assertEqual(f.verdict(False, "t", "t"), f.ABSORBED)

    def test_grown_tree_is_live_work(self):
        self.assertEqual(f.verdict(False, "t", "other"), f.ADDS)

    def test_a_failed_merge_never_reads_the_tree(self):
        # The worktree is mid-conflict, so its tree equals the fold's and a
        # tree-first classifier would call the conflict `absorbed`.
        self.assertEqual(f.verdict(True, "t", "t"), f.CONFLICT)


def repo(path):
    """A git repo at ``path`` with one commit on main. Returns a runner."""
    def git(*args, check=True):
        return subprocess.run(("git", "-C", str(path)) + args, check=check,
                              capture_output=True, text=True).stdout.strip()

    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    (path / "SKILL.md").write_text("base\n")
    git("add", "-A")
    git("commit", "-qm", "base")
    return git


class Probe(unittest.TestCase):
    """The git-shelling half, against a real repository."""

    def setUp(self):
        self.box = tempfile.TemporaryDirectory(prefix="fold-absorbs-test-")
        self.path = Path(self.box.name) / "repo"
        self.path.mkdir()
        self.git = repo(self.path)
        self.addCleanup(self.box.cleanup)

    def commit(self, branch, text, base="main"):
        self.git("checkout", "-q", "-b", branch, base)
        (self.path / "SKILL.md").write_text(text)
        self.git("commit", "-qam", branch)
        self.git("checkout", "-q", "main")
        return branch

    def probe(self, fold, head):
        tree = self.git("rev-parse", f"{fold}^{{tree}}")
        with tempfile.TemporaryDirectory(prefix="fold-absorbs-wt-") as wt:
            self.git("worktree", "add", "--detach", wt, fold)
            try:
                return f.attempt(wt, fold, tree, head)
            finally:
                self.git("worktree", "remove", "--force", wt, check=False)

    def test_a_rewritten_fold_absorbs_a_head_it_does_not_descend_from(self):
        # The case ancestry misses: the fold reproduces the head's content
        # without ever merging it, so --is-ancestor says no and the merge is
        # still a no-op. This is the whole reason the script exists.
        self.commit("candidate", "base\nrule\n")
        self.commit("fold", "base\nrule\n")
        self.assertNotEqual(self.git("rev-parse", "candidate"),
                            self.git("rev-parse", "fold"))
        self.assertNotEqual(
            0, subprocess.run(("git", "-C", str(self.path), "merge-base",
                               "--is-ancestor", "candidate", "fold"),
                              capture_output=True).returncode)
        self.assertEqual(self.probe("fold", "candidate")[0], f.ABSORBED)

    def test_a_head_the_fold_lacks_reports_adds_with_a_shortstat(self):
        # The fold leaves SKILL.md alone, so the head's rule merges cleanly in.
        self.commit("candidate", "base\nrule\n")
        self.git("checkout", "-q", "-b", "fold", "main")
        (self.path / "OTHER.md").write_text("unrelated\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "fold")
        self.git("checkout", "-q", "main")
        got, stat = self.probe("fold", "candidate")
        self.assertEqual(got, f.ADDS)
        self.assertIn("1 file changed", stat)

    def test_incompatible_edits_to_one_line_report_conflict(self):
        self.commit("candidate", "base\nthis wording\n")
        self.commit("fold", "base\nthat wording\n")
        self.assertEqual(self.probe("fold", "candidate")[0], f.CONFLICT)

    def test_a_conflicted_probe_does_not_poison_the_next_head(self):
        # attempt() resets before merging, so a verdict never depends on the
        # leftovers of the one before it.
        self.commit("conflicting", "base\nthis wording\n")
        self.commit("fold", "base\nthat wording\n")
        self.commit("carried", "base\nthat wording\n")
        tree = self.git("rev-parse", "fold^{tree}")
        with tempfile.TemporaryDirectory(prefix="fold-absorbs-wt-") as wt:
            self.git("worktree", "add", "--detach", wt, "fold")
            try:
                self.assertEqual(f.attempt(wt, "fold", tree, "conflicting")[0],
                                 f.CONFLICT)
                self.assertEqual(f.attempt(wt, "fold", tree, "carried")[0],
                                 f.ABSORBED)
            finally:
                self.git("worktree", "remove", "--force", wt, check=False)


if __name__ == "__main__":
    unittest.main()
