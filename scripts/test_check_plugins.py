#!/usr/bin/env python3
"""The ceiling is on the load, not on the file — these are the cases that differ."""

import tempfile
import unittest
from pathlib import Path

import check_plugins as cp


class CheckLoad(unittest.TestCase):
    def setUp(self) -> None:
        cp.errors.clear()
        cp.warnings.clear()
        self.tmp = tempfile.TemporaryDirectory()
        cp.ROOT = Path(self.tmp.name).resolve()  # check_load resolves its links
        self.addCleanup(self.tmp.cleanup)
        cp.ROLE_MAX_LINES = 10

    def write(self, name: str, lines: int, body: str = "x") -> None:
        (cp.ROOT / name).write_text("\n".join([body] * lines) + "\n", encoding="utf-8")

    def check(self, text: str) -> list[str]:
        path = cp.ROOT / "SKILL.md"
        path.write_text(text, encoding="utf-8")
        cp.check_load(path)
        return cp.warnings

    def test_role_alone_under_the_ceiling_is_silent(self) -> None:
        self.assertEqual(self.check("one\ntwo\n"), [])

    def test_a_preamble_link_counts_toward_the_load(self) -> None:
        self.write("CONTRACT.md", 20)
        warning, = self.check("Read the [contract](CONTRACT.md) before acting.\n")
        self.assertIn("loads 21 lines", warning)
        self.assertIn("1 SKILL.md + 20 CONTRACT.md", warning)

    def test_a_link_below_the_first_heading_does_not(self) -> None:
        self.write("CONTRACT.md", 20)
        self.assertEqual(self.check("preamble\n\n## Step\n\n[c](CONTRACT.md)\n"), [])

    def test_a_link_to_a_file_that_is_not_there_is_ignored(self) -> None:
        self.assertEqual(self.check("[gone](MISSING.md)\n"), [])


if __name__ == "__main__":
    unittest.main()
