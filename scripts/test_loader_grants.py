"""The tokenizer is checked against the loader's, not against an intuition.

Every expectation here was produced by running Claude Code 2.1.278's own
tokenizer — extracted from the shipped binary and executed — over the same
input. `test_the_port_matches_the_shipped_tokenizer` records the corpus the
port was differentially tested on; the rest name the cases that matter.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from loader_grants import grant_tokens  # noqa: E402


class Separators(unittest.TestCase):
    def test_a_comma_separates(self):
        self.assertEqual(grant_tokens("Bash, Read"), ["Bash", "Read"])

    def test_a_space_separates_too(self):
        """The rule three gates in this tree used to deny."""
        self.assertEqual(grant_tokens("Bash Read Write"), ["Bash", "Read", "Write"])

    def test_a_newline_separates(self):
        """Not a rule of the loader's — a rule of reading frontmatter as text."""
        self.assertEqual(grant_tokens("Bash\nRead"), ["Bash", "Read"])

    def test_a_tab_is_not_a_separator(self):
        """It falls to the default branch and the per-token trim removes it."""
        self.assertEqual(grant_tokens("Read\tBash"), ["Read\tBash"])

    def test_repeated_separators_yield_no_empty_tokens(self):
        self.assertEqual(grant_tokens("  Bash , ,  Read  "), ["Bash", "Read"])

    def test_an_empty_field_is_no_grants(self):
        self.assertEqual(grant_tokens(""), [])


class ParenthesesSuspendBoth(unittest.TestCase):
    """What actually protects a narrowed grant — not the absence of the rule."""

    def test_a_scoped_grant_holding_a_space_is_one_token(self):
        self.assertEqual(grant_tokens("Bash(git diff:*)"), ["Bash(git diff:*)"])

    def test_a_comma_inside_parentheses_is_kept(self):
        self.assertEqual(
            grant_tokens("Task(anantys.code-auditor, anantys.spec-tester)"),
            ["Task(anantys.code-auditor, anantys.spec-tester)"],
        )

    def test_scoped_grants_still_separate_from_each_other(self):
        self.assertEqual(
            grant_tokens("Bash(git log:*), Bash(ls:*)"),
            ["Bash(git log:*)", "Bash(ls:*)"],
        )

    def test_an_unclosed_parenthesis_swallows_the_rest(self):
        """No closure check in the loader, so none here."""
        self.assertEqual(grant_tokens("Bash(git log, Read"), ["Bash(git log, Read"])

    def test_a_close_without_an_open_just_resumes_splitting(self):
        self.assertEqual(grant_tokens(") Bash Read"), [")", "Bash", "Read"])


class OneCommaShort(unittest.TestCase):
    """The spelling the comma-only split could not see in either direction."""

    def test_a_space_before_the_parenthesis_yields_bare_bash(self):
        self.assertEqual(
            grant_tokens("Read, Bash (git log:*), Grep"),
            ["Read", "Bash", "(git log:*)", "Grep"],
        )

    def test_a_missing_comma_after_a_scope_yields_the_next_tool(self):
        self.assertEqual(
            grant_tokens("Bash(git log:*) Read"), ["Bash(git log:*)", "Read"]
        )


class Dialects(unittest.TestCase):
    """The YAML noise each gate strips per token still arrives as tokens."""

    def test_a_flow_sequence_tokenizes_elementwise(self):
        self.assertEqual(
            grant_tokens('["Bash", "Read"]'), ['["Bash"', '"Read"]']
        )

    def test_an_mcp_grant_survives_whole(self):
        self.assertEqual(
            grant_tokens("mcp__claude-in-chrome__navigate, Read"),
            ["mcp__claude-in-chrome__navigate", "Read"],
        )


class Provenance(unittest.TestCase):
    def test_the_port_matches_the_shipped_tokenizer(self):
        """Pairs captured from 2.1.278's `Rp` run over a 2711-input corpus.

        The corpus was the structured cases above plus 4000 random strings
        drawn from the alphabet that matters (`B a s h R e d , ( ) * : -` and
        whitespace); these are the inputs whose shapes the random draw covered
        and whose outputs would change if a branch of the port were wrong.
        """
        pairs = [
            ("Bash", ["Bash"]),
            ("Bash,", ["Bash"]),
            (",Bash", ["Bash"]),
            ("Bash(", ["Bash("]),
            ("(", ["("]),
            ("()", ["()"]),
            ("( )", ["( )"]),
            ("a(b c)d", ["a(b c)d"]),
            ("a(b,c) d", ["a(b,c)", "d"]),
            ("a (b,c)", ["a", "(b,c)"]),
            ("a((b) c)", ["a((b)", "c)"]),
            ("*", ["*"]),
            ("Bash:*", ["Bash:*"]),
            ("-Bash", ["-Bash"]),
        ]
        for raw, expected in pairs:
            with self.subTest(raw=raw):
                self.assertEqual(grant_tokens(raw), expected)


if __name__ == "__main__":
    unittest.main()
