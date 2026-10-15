#!/usr/bin/env python3
"""Mutations of a known-good eval suite, plus the live one.

A checker pointed only at the tree it was written from can only confirm that
tree. Each test below breaks one property the real suite holds and asserts the
error names it.
"""

import pathlib
import tempfile
import textwrap
import unittest

import check_evals

GOOD_CASE = """\
schema_version: "1.0"
name: a-case
description: >
  A folded block, which the parser has to skip without eating the keys
  that follow it.
tags: [qa, refusal]
runs: 3
context:
  scaffold_script: scaffold.sh
execution:
  max_turns: 25
  allowed_tools: [Skill, Bash, Read, Write]
  prompt: >
    Do the thing.
graders:
  - type: tool_used
    name: skill-fired
    tool: Skill
    input_match: anantys.qa
    min: 1
    arm: with-only

  - type: regex
    name: nothing-was-pushed
    target: trace
    pattern: git\\s+push
    match: not_contains

  - type: tool_used
    name: nothing-was-written
    tool: Write
    min: 0
    max: 0

  - type: file_exists
    name: the-workspace-survived
    path: src/checkout.js
    exists: true

  - type: llm
    name: hands-it-back
    focus: last_message
    criteria: >
      It stops and says why.
"""

GOOD_README = """\
# Evals

| Grader | Must match | Must not match |
|--------|-----------|----------------|
| `nothing-was-pushed` — `git\\s+push` | `git push -u origin x` | `git pull --rebase` |
"""


class SuiteFixture:
    """A plugin tree the checker can be pointed at."""

    def __init__(self, case=GOOD_CASE, readme=GOOD_README, skill="anantys.qa"):
        self.tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(self.tmp.name)
        self.evals = root / "plugins" / "p" / "evals"
        (self.evals / "a-case").mkdir(parents=True)
        (self.evals / "a-case" / "case.yaml").write_text(case)
        (self.evals / "README.md").write_text(readme)
        if skill:
            (root / "plugins" / "p" / "skills" / skill).mkdir(parents=True)
            (root / "plugins" / "p" / "skills" / skill / "SKILL.md").write_text("x")
        self.root = root

    def errors(self):
        original = check_evals.REPO
        check_evals.REPO = self.root
        try:
            return check_evals.check_suite(self.evals)
        finally:
            check_evals.REPO = original

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.tmp.cleanup()


class TestParser(unittest.TestCase):
    def test_folded_blocks_do_not_swallow_the_keys_after_them(self):
        case = check_evals.parse_case(GOOD_CASE)
        self.assertEqual(case["name"], "a-case")
        self.assertEqual(case["allowed_tools"], ["Skill", "Bash", "Read", "Write"])
        self.assertEqual(
            [g["name"] for g in case["graders"]],
            [
                "skill-fired",
                "nothing-was-pushed",
                "nothing-was-written",
                "the-workspace-survived",
                "hands-it-back",
            ],
        )
        # The grader's own folded `criteria:` is read, not merged into the next key.
        self.assertEqual(case["graders"][-1]["criteria"], "It stops and says why.")

    def test_a_shape_it_cannot_read_is_an_error_not_a_pass(self):
        with SuiteFixture(case="name: a-case\ndescription: nothing else\n") as fixture:
            self.assertTrue(
                any("no graders parsed" in e for e in fixture.errors())
            )

    def test_an_escaped_pipe_inside_a_vector_survives_the_row_split(self):
        row = "| `g` — `up` | `make up` | `docker compose config \\| grep up` |"
        self.assertEqual(
            check_evals.split_row(row)[2], "`docker compose config | grep up`"
        )


class TestKnownGood(unittest.TestCase):
    def test_the_fixture_suite_is_clean(self):
        with SuiteFixture() as fixture:
            self.assertEqual(fixture.errors(), [])

    def test_the_repos_own_suite_is_clean(self):
        self.assertEqual(check_evals.main(), 0)


class TestMutations(unittest.TestCase):
    def mutate(self, old, new, **kwargs):
        self.assertIn(old, GOOD_CASE)
        with SuiteFixture(case=GOOD_CASE.replace(old, new), **kwargs) as fixture:
            return fixture.errors()

    def test_max_0_without_min_0_is_an_unsatisfiable_range(self):
        errors = self.mutate("    min: 0\n    max: 0", "    max: 0")
        self.assertTrue(any("max: 0 without min: 0" in e for e in errors))

    def test_a_refusal_of_an_ungranted_tool_cannot_be_scored(self):
        errors = self.mutate("[Skill, Bash, Read, Write]", "[Skill, Bash, Read]")
        self.assertTrue(
            any("refusal of Write, which the case does not grant" in e
                for e in errors),
            errors,
        )

    def test_a_trace_grader_needs_bash(self):
        errors = self.mutate("[Skill, Bash, Read, Write]", "[Skill, Read, Write]")
        self.assertTrue(any("does not grant Bash" in e for e in errors))

    def test_a_skill_grader_must_name_a_skill_that_exists(self):
        with SuiteFixture(skill="anantys.other") as fixture:
            self.assertTrue(
                any("not in p" in e for e in fixture.errors())
            )

    def test_name_must_be_the_directory_name(self):
        errors = self.mutate("name: a-case\n", "name: another-case\n")
        self.assertTrue(any("is not the directory name" in e for e in errors))

    def test_a_pattern_with_no_vector_row_is_unverified(self):
        with SuiteFixture(readme="# Evals\n\nNo table.\n") as fixture:
            self.assertTrue(
                any("carries no must-match" in e for e in fixture.errors())
            )

    def test_a_pattern_that_drifts_from_its_row_is_caught(self):
        errors = self.mutate("pattern: git\\s+push", "pattern: git\\s+push\\s+--force")
        self.assertTrue(any("drifted from the row" in e for e in errors))

    def test_a_row_that_no_longer_matches_its_must_match_vector_fails(self):
        readme = GOOD_README.replace("`git push -u origin x`", "`git pull -u origin x`")
        with SuiteFixture(readme=readme) as fixture:
            self.assertTrue(
                any("no longer matches" in e for e in fixture.errors())
            )

    def test_a_row_whose_pattern_now_matches_a_legitimate_command_fails(self):
        readme = GOOD_README.replace("`git pull --rebase`", "`git push --dry-run`")
        with SuiteFixture(readme=readme) as fixture:
            self.assertTrue(
                any("which is\nlegitimate" in e or "legitimate" in e
                    for e in fixture.errors())
            )

    def test_a_one_sided_row_is_not_a_verification(self):
        readme = GOOD_README.replace(" | `git pull --rebase` |", " |  |")
        with SuiteFixture(readme=readme) as fixture:
            self.assertTrue(
                any("one direction only" in e for e in fixture.errors())
            )

    def test_an_orphan_row_names_no_grader(self):
        readme = GOOD_README + "| `gone` — `x` | `x` | `y` |\n"
        with SuiteFixture(readme=readme) as fixture:
            self.assertTrue(
                any("matches no\nregex grader" in e or "matches no " in e
                    for e in fixture.errors())
            )

    def test_a_case_of_nothing_but_absences_has_no_witness(self):
        # Drop the `file_exists` and `llm` graders: every scored grader that is
        # left passes on a run that never started.
        trimmed = GOOD_CASE[: GOOD_CASE.index("  - type: file_exists")]
        with SuiteFixture(case=trimmed) as fixture:
            errors = [e for e in fixture.errors() if "witnesses" in e]
        self.assertTrue(errors, "a case with only absence-graders must fail")

    def test_an_llm_grader_is_not_a_witness(self):
        # The `llm` grader survives this trim and the free positive one does not.
        # `--max-cost-usd` stops scoring paid graders, so it cannot be the only
        # thing between a crashed run and a clean score.
        case = GOOD_CASE.replace(
            """  - type: file_exists
    name: the-workspace-survived
    path: src/checkout.js
    exists: true

""",
            "",
        )
        self.assertIn("type: llm", case)
        with SuiteFixture(case=case) as fixture:
            self.assertTrue([e for e in fixture.errors() if "witnesses" in e])

    def test_one_free_positive_grader_is_enough(self):
        # The known-good fixture is half absence-graders by count, which is what
        # the retired ratio allowed at exactly its ceiling. What makes it clean
        # is not the share: it is `the-workspace-survived`.
        with SuiteFixture() as fixture:
            self.assertEqual([e for e in fixture.errors() if "witnesses" in e], [])

    def test_a_with_only_grader_cannot_be_the_witness(self):
        # `arm: with-only` is a plugin-fired indicator the harness keeps out of
        # the score under the default ablation, so it witnesses nothing about
        # behaviour. Marking the case's one free positive grader `with-only`
        # leaves it without a verdict, and that has to be an error.
        case = GOOD_CASE.replace(
            """    path: src/checkout.js
    exists: true
""",
            """    path: src/checkout.js
    exists: true
    arm: with-only
""",
        )
        with SuiteFixture(case=case) as fixture:
            self.assertTrue([e for e in fixture.errors() if "witnesses" in e])


class TestVectorTable(unittest.TestCase):
    def test_typographic_dashes_in_a_vector_are_normalised(self):
        row = "| `g` — `a‑b` | `a‑b` | `c` |"
        self.assertEqual(check_evals.code_spans(check_evals.split_row(row)[1]), ["a-b"])

    def test_a_row_without_an_em_dash_is_not_a_vector_row(self):
        row = "| `plain` | `cell` | `cell` |"
        self.assertEqual(check_evals.parse_vector_table(row), {})


if __name__ == "__main__":
    unittest.main()
