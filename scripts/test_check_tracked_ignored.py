#!/usr/bin/env python3
"""The two cells that are not symmetric: tracked-and-ignored, and no rule to ignore by.

Every case runs against a real index, because the defect only exists in the relation
between the index and the exclude rules — a fake of either half cannot show it.
"""

import contextlib
import io
import subprocess
import tempfile
import unittest
from pathlib import Path

import check_tracked_ignored as cti


class Harness(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        cti.ROOT = self.root
        self.addCleanup(setattr, cti, "ROOT", cti.ROOT)
        self.git("init", "-q")

    def git(self, *args: str) -> None:
        subprocess.run(("git", "-C", str(self.root), *args), check=True, capture_output=True)

    def track(self, name: str, text: str = "x") -> None:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self.git("add", "-f", name)

    def run_check(self) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cti.main()
        return rc, out.getvalue()


class TrackedIgnored(Harness):
    def test_clean_tree_with_gitignore_passes(self) -> None:
        self.track(".gitignore", "__pycache__/\n")
        self.track("scripts/check.py")
        rc, out = self.run_check()
        self.assertEqual(rc, 0)
        self.assertIn("0 error(s), 0 warning(s)", out)

    def test_generated_output_errors_without_any_gitignore(self) -> None:
        """The non-inert half: this is the state every branch in the queue is actually in."""
        self.track("scripts/__pycache__/check.cpython-314.pyc")
        rc, out = self.run_check()
        self.assertEqual(rc, 1)
        self.assertIn("scripts/__pycache__/check.cpython-314.pyc", out)
        self.assertIn("generated output is tracked", out)

    def test_absent_gitignore_warns_naming_what_is_unmeasured(self) -> None:
        self.track("scripts/check.py")
        rc, out = self.run_check()
        self.assertEqual(rc, 0)
        self.assertIn("warning: no .gitignore", out)

    def test_tracked_and_ignored_errors_even_when_not_generated(self) -> None:
        """The general rule: `.gitignore` hid it from `git status`, so nothing else can see it."""
        self.track(".gitignore", "build/\n")
        self.track("build/out.txt")
        rc, out = self.run_check()
        self.assertEqual(rc, 1)
        self.assertIn("build/out.txt", out)
        self.assertIn("tracked, and ignored", out)

    def test_a_generated_path_is_reported_once_not_twice(self) -> None:
        """Both rules match a tracked `.pyc` once an exclude rule exists."""
        self.track(".gitignore", "__pycache__/\n")
        self.track("scripts/__pycache__/check.cpython-314.pyc")
        rc, out = self.run_check()
        self.assertEqual(rc, 1)
        self.assertEqual(out.count("scripts/__pycache__/check.cpython-314.pyc"), 1)
        self.assertIn("1 error(s), 0 warning(s)", out)

    def test_an_untracked_ignored_file_is_fine(self) -> None:
        """The cell that is *supposed* to be empty of signal — scratch output."""
        self.track(".gitignore", "__pycache__/\n")
        (self.root / "scripts").mkdir(parents=True, exist_ok=True)
        (self.root / "scripts/__pycache__").mkdir(parents=True, exist_ok=True)
        (self.root / "scripts/__pycache__/x.pyc").write_text("x", encoding="utf-8")
        rc, out = self.run_check()
        self.assertEqual(rc, 0)
        self.assertIn("0 error(s), 0 warning(s)", out)


if __name__ == "__main__":
    unittest.main()
