#!/usr/bin/env python3
"""Fixture tests for check_md_fences — run: python3 -m unittest discover scripts

`scan`-level tests here are not decoration: the gate's whole precision claim is
that its three CommonMark rules (same character, at-least-as-long, nothing but
whitespace after) make a false positive impossible, so each rule gets a case
that fails the gate if the rule is dropped. The regression case at the bottom is
the real `qa-config.md` shape that motivated the gate, reduced to nine lines.
"""

import io
import re
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
import check_md_fences as c  # noqa: E402


def tree(files):
    root = Path(tempfile.mkdtemp())
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def run(files):
    """The gate's exit code and output over a throwaway tree."""
    out = io.StringIO()
    with redirect_stdout(out):
        code = c.main(tree(files))
    return code, out.getvalue()


#: `check_plugins.FENCED`, verbatim — the parity shortcut four sibling gates use.
PARITY = re.compile(r"^```.*?^```", re.S | re.M)


def parity_lines(text):
    """The 1-based lines a parity partition treats as inside a fence."""
    inside = set()
    for match in PARITY.finditer(text):
        first = text[: match.start()].count("\n") + 1
        inside |= set(range(first, first + match.group().count("\n") + 1))
    return inside


def commonmark_lines(text):
    """The same, as `c.fences` (and a CommonMark parser) resolves it."""
    inside = set()
    for opened, closed, _, _ in c.fences(text):
        inside |= set(range(opened, (closed or text.count("\n") + 1) + 1))
    return inside


class Scan(unittest.TestCase):
    def test_a_plain_block_is_one_fence(self):
        got = list(c.fences("```bash\nls\n```\n"))
        self.assertEqual(len(got), 1)
        opened, closed, run, body = got[0]
        self.assertEqual((opened, closed, run, body), (1, 3, "```", ["ls"]))

    def test_an_info_bearing_run_does_not_close_a_block(self):
        """The rule that makes the defect possible, so the gate must honour it."""
        (opened, closed, _, body), = c.fences("````markdown\n```bash\nls\n```\n````\n")
        self.assertEqual((opened, closed), (1, 5))
        self.assertEqual(body, ["```bash", "ls", "```"])

    def test_a_shorter_run_does_not_close_a_longer_fence(self):
        (opened, closed, _, body), = c.fences("````\n```\nstill inside\n````\n")
        self.assertEqual((opened, closed), (1, 4))
        self.assertEqual(body, ["```", "still inside"])

    def test_a_tilde_run_does_not_close_a_backtick_fence(self):
        (_, closed, _, body), = c.fences("```\n~~~\n```\n")
        self.assertEqual(closed, 3)
        self.assertEqual(body, ["~~~"])

    def test_trailing_whitespace_still_closes(self):
        (_, closed, _, _), = c.fences("```\nx\n```   \n")
        self.assertEqual(closed, 3)

    def test_an_unclosed_fence_reports_no_closer(self):
        (opened, closed, _, body), = c.fences("```bash\nls\n")
        self.assertEqual((opened, closed, body), (1, None, ["ls"]))

    def test_a_bare_four_run_is_a_closer_not_an_opener_with_backtick_info(self):
        """CommonMark 4.5: a backtick info string may not contain a backtick."""
        (opened, closed, run, _), = c.fences("````\nx\n````\n")
        self.assertEqual((opened, closed, run), (1, 3, "````"))

    def test_four_spaces_of_indent_is_not_a_fence(self):
        self.assertEqual(list(c.fences("    ```bash\n    ls\n")), [])

    def test_two_sibling_blocks_are_two_fences(self):
        self.assertEqual(len(list(c.fences("```\na\n```\n\n```\nb\n```\n"))), 2)


class Findings(unittest.TestCase):
    def test_a_correctly_nested_template_passes(self):
        code, out = run({"t.md": "````markdown\n# T\n\n```bash\nls\n```\n````\n"})
        self.assertEqual(code, 0)
        self.assertIn("fence check: OK", out)

    def test_a_same_length_inner_opener_is_an_error(self):
        code, out = run({"t.md": "```markdown\n# T\n\n```bash\nls\n```\n```\n"})
        self.assertEqual(code, 1)
        self.assertIn("t.md:4:", out)
        self.assertIn("cannot nest at that length", out)

    def test_the_error_names_the_longer_delimiter_to_use(self):
        _, out = run({"t.md": "```markdown\n```bash\nls\n```\n```\n"})
        self.assertIn("`````", out)

    def test_an_unclosed_fence_is_an_error(self):
        code, out = run({"t.md": "# T\n\n```bash\nls\n"})
        self.assertEqual(code, 1)
        self.assertIn("t.md:3:", out)
        self.assertIn("never closed", out)

    def test_a_file_with_no_fences_passes(self):
        code, _ = run({"t.md": "# T\n\nprose only.\n"})
        self.assertEqual(code, 0)

    def test_a_bare_inner_run_is_never_flagged(self):
        """It closes the block, so it is not content — the precision claim."""
        code, _ = run({"t.md": "```\n```\n"})
        self.assertEqual(code, 0)

    def test_skipped_directories_are_not_read(self):
        code, out = run({".git/t.md": "```bash\nunclosed\n"})
        self.assertEqual(code, 0)
        self.assertIn("0 markdown file(s) read", out)

    def test_every_file_is_reported_not_just_the_first(self):
        code, out = run(
            {
                "a.md": "```md\n```sh\nx\n```\n```\n",
                "b/c.md": "```sh\nunclosed\n",
            }
        )
        self.assertEqual(code, 1)
        self.assertIn("a.md:2:", out)
        self.assertIn("c.md:1:", out)


class QaConfigRegression(unittest.TestCase):
    """The shape that motivated the gate, and the shape that fixes it."""

    BROKEN = (
        "# QA environment contract\n"
        "\n"
        "```markdown\n"
        "# QA environment — <project>\n"
        "\n"
        "### Build identity\n"
        "```bash\n"
        "<command>\n"
        "```\n"
        "\n"
        "## Environment: staging\n"
        "```\n"
    )

    def test_the_broken_shape_fails(self):
        code, out = run({"templates/qa-config.md": self.BROKEN})
        self.assertEqual(code, 1)
        self.assertIn("qa-config.md:7:", out)

    def test_lengthening_the_outer_fence_fixes_it(self):
        fixed = self.BROKEN.replace("```markdown", "````markdown").replace(
            "## Environment: staging\n```\n", "## Environment: staging\n````\n"
        )
        code, out = run({"templates/qa-config.md": fixed})
        self.assertEqual(code, 0, out)

    def test_the_fix_shrinks_the_parity_divergence_without_closing_it(self):
        """The claim the gate's docstring originally got wrong, pinned.

        `check_plugins.FENCED` and friends pair fences by position parity. A
        four-backtick outer fence repairs the rendering but NOT parity: `^```
        still matches a four-backtick line and still stops at the inner opener.
        So the divergence shrinks and does not vanish — which is why the gate
        claims to keep the nesting out of the tree rather than to make the
        shortcut correct.
        """
        broken = parity_lines(self.BROKEN) ^ commonmark_lines(self.BROKEN)
        fixed_text = self.BROKEN.replace("```markdown", "````markdown").replace(
            "## Environment: staging\n```\n", "## Environment: staging\n````\n"
        )
        fixed = parity_lines(fixed_text) ^ commonmark_lines(fixed_text)

        self.assertTrue(broken, "the broken shape must diverge")
        self.assertTrue(fixed, "a longer outer fence does not make parity correct")
        self.assertLess(len(fixed), len(broken))

    def test_no_nesting_at_all_makes_parity_agree(self):
        """The only shape on which the shortcut is actually sound."""
        plain = "# T\n\n```bash\nls\n```\n\nprose\n\n```sh\npwd\n```\n"
        self.assertEqual(parity_lines(plain), commonmark_lines(plain))


if __name__ == "__main__":
    unittest.main()
