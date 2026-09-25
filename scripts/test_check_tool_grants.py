#!/usr/bin/env python3
"""Fixture tests for check_tool_grants — run: python3 -m unittest discover scripts"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import check_tool_grants as c  # noqa: E402


def role(grants, body):
    return c.check(Path("role.md"), grants, body, {"navigate", "tabs_context_mcp"})


class ToolGrants(unittest.TestCase):
    def test_browser_prose_without_browser_grant_is_an_error(self):
        errors, _ = role(["Bash", "Read"], "Walk the scenarios in a real browser.")
        self.assertIn("grants no browser tool", errors[0])

    def test_browser_prose_with_a_browser_grant_passes(self):
        errors, _ = role(["mcp__x__navigate"], "Drive the browser to the page.")
        self.assertEqual(errors, [])

    def test_named_browser_tool_must_be_granted(self):
        errors, _ = role(["mcp__x__navigate"], "Call `tabs_context_mcp` first.")
        self.assertIn("`tabs_context_mcp`", errors[0])

    def test_backticked_non_tool_word_is_not_a_tool(self):
        errors, _ = role(["mcp__x__navigate"], "Read `document.title` in the browser.")
        self.assertEqual(errors, [])

    def test_constrained_bash_rejects_an_ungranted_command(self):
        errors, _ = role(["Bash(ls:*)"], "```bash\nrm -rf build\n```")
        self.assertIn("`rm -rf build`", errors[0])

    def test_subcommand_grant_permits_its_own_subcommand(self):
        errors, _ = role(["Bash(git diff:*)"], "```bash\ngit diff --stat main...HEAD\n```")
        self.assertEqual(errors, [])

    def test_subcommand_grant_rejects_a_sibling_subcommand(self):
        errors, _ = role(["Bash(git diff:*)"], "```bash\ngit push origin HEAD\n```")
        self.assertIn("`git push origin HEAD`", errors[0])

    def test_subcommand_grant_is_not_a_bare_prefix_match(self):
        errors, _ = role(["Bash(git diff:*)"], "```bash\ngit difftool\n```")
        self.assertIn("`git difftool`", errors[0])

    def test_bare_bash_grant_allows_any_command(self):
        errors, _ = role(["Bash"], "```bash\nrm -rf build\n```")
        self.assertEqual(errors, [])

    def test_unreferenced_grant_warns(self):
        _, warnings = role(["Bash(git:*)"], "Read the journal.")
        self.assertIn("`Bash(git:*)`", warnings[0])

    def test_generic_grants_are_never_unreferenced(self):
        _, warnings = role(["Read", "Write", "Glob"], "Do the thing.")
        self.assertEqual(warnings, [])


class Parse(unittest.TestCase):
    def _write(self, text):
        path = Path(self.tmp) / "r.md"
        path.write_text(text, encoding="utf-8")
        return path

    def setUp(self):
        import tempfile

        self.tmp = tempfile.mkdtemp()

    def test_agent_style_quoted_list(self):
        p = self._write('---\ntools: ["Bash", "Read"]\n---\nbody\n')
        self.assertEqual(c.parse(p), (["Bash", "Read"], "body\n"))

    def test_skill_style_bare_list(self):
        p = self._write("---\nallowed-tools: Bash, Read\n---\nbody\n")
        self.assertEqual(c.parse(p), (["Bash", "Read"], "body\n"))

    def test_missing_frontmatter(self):
        self.assertIsNone(c.parse(self._write("no frontmatter here\n")))


if __name__ == "__main__":
    unittest.main()
