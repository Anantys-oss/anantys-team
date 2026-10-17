#!/usr/bin/env python3
"""Fixture tests for fold_coverage — run: python3 -m unittest discover scripts"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fold_coverage as f  # noqa: E402


def diff(*added_lines):
    """A diff hunk adding ``added_lines``, with the noise a real one carries."""
    body = "".join(f"+{line}\n" for line in added_lines)
    return ("--- a/plugins/x/SKILL.md\n"
            "+++ b/plugins/x/SKILL.md\n"
            "@@ -1,2 +1,4 @@\n"
            " context line that is long enough to pass the length floor\n"
            "-a removed line that is also long enough to pass the floor\n"
            + body)


LONG = "a sentence long enough to clear the boilerplate floor comfortably"


class Added(unittest.TestCase):
    def test_keeps_substantive_added_lines(self):
        self.assertEqual(f.added(diff(LONG)), [LONG])

    def test_drops_the_file_header_that_also_starts_with_plus(self):
        # `+++ b/path` is an addition by prefix and a path by meaning.
        self.assertNotIn("+ b/plugins/x/SKILL.md", f.added(diff(LONG)))

    def test_ignores_removed_and_context_lines(self):
        self.assertEqual(f.added(diff()), [])

    def test_drops_boilerplate_under_the_length_floor(self):
        # Table rules and short bullets match some unrelated file by accident.
        self.assertEqual(f.added(diff("| --- | --- |", "- yes")), [])

    def test_strips_indentation_so_a_relocated_line_still_matches(self):
        # A fold that moves a rule into reference/ re-indents it; the content
        # is carried and the leading whitespace is not evidence of anything.
        self.assertEqual(f.added(diff("      " + LONG)), [LONG])

    def test_deduplicates_while_keeping_first_appearance_order(self):
        other = LONG.replace("comfortably", "and then some more")
        self.assertEqual(f.added(diff(LONG, other, LONG)), [LONG, other])

    def test_excludes_lines_naming_scripts(self):
        # A scaffolding-free fold disclaims checkers; a README tree line that
        # names one is not a gap in it.
        self.assertEqual(f.added(diff(LONG + " scripts/check_plugins.py")), [])

    def test_the_length_floor_is_tunable(self):
        self.assertEqual(f.added(diff("- yes"), min_len=3), ["- yes"])


class InScope(unittest.TestCase):
    def test_keeps_role_files(self):
        paths = ["plugins/p/skills/s/SKILL.md", "README.md"]
        self.assertEqual(f.in_scope(paths), paths)

    def test_drops_the_eval_suite(self):
        # Declared out of the fold's contract, so judging it there is a false row.
        self.assertEqual(f.in_scope(["plugins/p/evals/c/case.yaml"]), [])

    def test_a_head_that_only_touches_evals_scopes_to_nothing(self):
        # measure() skips such a head entirely rather than scoring it 0%.
        self.assertEqual(f.in_scope(["plugins/p/evals/a.md", "plugins/p/evals/b.md"]), [])

    def test_a_path_merely_containing_evals_is_not_the_suite(self):
        self.assertEqual(f.in_scope(["plugins/p/skills/evals-guide.md"]),
                         ["plugins/p/skills/evals-guide.md"])


class Absent(unittest.TestCase):
    def test_a_carried_line_is_not_absent(self):
        self.assertEqual(f.absent([LONG], {LONG}), [])

    def test_a_dropped_line_is_absent(self):
        self.assertEqual(f.absent([LONG], {"something else entirely"}), [LONG])

    def test_matching_is_verbatim_so_a_rewording_reads_as_absent(self):
        # The documented floor: this is why a low score is a prompt to grep,
        # never a verdict that the fold dropped the rule.
        reworded = LONG.replace("comfortably", "well enough")
        self.assertEqual(f.absent([LONG], {reworded}), [LONG])

    def test_an_empty_fold_carries_nothing(self):
        self.assertEqual(f.absent([LONG], set()), [LONG])


if __name__ == "__main__":
    unittest.main()
