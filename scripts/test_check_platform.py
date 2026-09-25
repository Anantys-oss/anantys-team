#!/usr/bin/env python3
"""Every case here is a mutation the loader was measured to accept in silence."""

import tempfile
import unittest
from pathlib import Path

import check_platform as cp

GOOD_SKILL = """---
name: anantys.debug
description: Debug by observing the running app.
allowed-tools: mcp__claude-in-chrome__navigate, Read, Bash(git:*)
---

body
"""


class CheckPlatform(unittest.TestCase):
    def setUp(self) -> None:
        cp.errors.clear()
        cp.warnings.clear()
        self.tmp = tempfile.TemporaryDirectory()
        cp.ROOT = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def check(self, text: str) -> list[str]:
        path = cp.ROOT / "SKILL.md"
        path.write_text(text, encoding="utf-8")
        cp.check_component(path, cp.SKILL_KEYS, "allowed-tools")
        return cp.errors

    def test_known_good_skill_is_clean(self) -> None:
        self.assertEqual(self.check(GOOD_SKILL), [])

    def test_underscore_typo_unsets_the_grant(self) -> None:
        found = self.check(GOOD_SKILL.replace("allowed-tools:", "allowed_tools:"))
        self.assertEqual(len(found), 1)
        self.assertIn("allowed_tools", found[0])

    def test_single_underscore_mcp_name_is_not_a_tool(self) -> None:
        found = self.check(GOOD_SKILL.replace("mcp__claude-in-chrome__navigate", "mcp_chrome_nav"))
        self.assertEqual(len(found), 1)
        self.assertIn("mcp_chrome_nav", found[0])

    def test_scoped_bash_grant_is_well_formed(self) -> None:
        self.assertEqual(self.check(GOOD_SKILL.replace("Bash(git:*)", "Bash(mkdir:*)")), [])

    def test_multi_word_scoped_grant_is_one_token(self) -> None:
        # `Bash(git diff:*)` holds a space. A checker that splits on whitespace
        # rejects the narrowest grants and pushes authors back to `Bash(git:*)`.
        narrowed = "allowed-tools: Bash(git diff:*), Bash(gh pr view:*), Read"
        self.assertEqual(self.check(GOOD_SKILL.replace(GOOD_SKILL.splitlines()[3], narrowed)), [])

    def test_unclosed_frontmatter_drops_every_field(self) -> None:
        found = self.check("---\nname: x\ndescription: y\n\nbody\n")
        self.assertEqual(len(found), 1)
        self.assertIn("never closed", found[0])

    def test_missing_frontmatter_is_an_error(self) -> None:
        found = self.check("just a body\n")
        self.assertEqual(len(found), 1)
        self.assertIn("no frontmatter", found[0])

    def test_agent_keys_differ_from_skill_keys(self) -> None:
        path = cp.ROOT / "agent.md"
        path.write_text(
            '---\nname: a\ndescription: d\ntools: ["Bash", "Read"]\nmodel: opus\n---\nbody\n',
            encoding="utf-8",
        )
        cp.check_component(path, cp.AGENT_KEYS, "tools")
        self.assertEqual(cp.errors, [])


if __name__ == "__main__":
    unittest.main()
