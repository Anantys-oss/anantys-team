#!/usr/bin/env python3
"""Mutations of a known-good eval suite, plus the live one.

A checker pointed only at the tree it was written from can only confirm that
tree. Each test below breaks one property the real suite holds and asserts the
error names it.
"""

import pathlib
import tempfile
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

    def __init__(
        self, case=GOOD_CASE, readme=GOOD_README, skill="anantys.qa", agent=None
    ):
        self.tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(self.tmp.name)
        self.evals = root / "plugins" / "p" / "evals"
        (self.evals / "a-case").mkdir(parents=True)
        (self.evals / "a-case" / "case.yaml").write_text(case)
        (self.evals / "a-case" / "scaffold.sh").write_text("#!/bin/sh\n")
        (self.evals / "README.md").write_text(readme)
        if skill:
            (root / "plugins" / "p" / "skills" / skill).mkdir(parents=True)
            (root / "plugins" / "p" / "skills" / skill / "SKILL.md").write_text("x")
        if agent:
            (root / "plugins" / "p" / "agents").mkdir(parents=True, exist_ok=True)
            (root / "plugins" / "p" / "agents" / f"{agent}.md").write_text("x")
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

    def test_quoting_a_scalar_does_not_change_what_it_says(self):
        # Every rule in the checker is an equality against a bare spelling, and
        # YAML has three spellings of each. The case files already quote
        # `schema_version`, so the quoted form is in the format's normal register.
        quoted = (
            GOOD_CASE.replace("match: not_contains", 'match: "not_contains"')
            .replace("    max: 0", '    max: "0"')
            .replace("exists: true", "exists: 'true'")
            .replace("name: nothing-was-pushed", 'name: "nothing-was-pushed"')
        )
        self.assertEqual(
            check_evals.parse_case(quoted)["graders"],
            check_evals.parse_case(GOOD_CASE)["graders"],
        )

    def test_a_bare_dash_opens_a_new_grader_instead_of_extending_the_last(self):
        # `-` alone on its line is a block sequence item like any other. Read as
        # a continuation, the keys below it overwrite the previous grader's name
        # and pattern: one grader scored twice, the other gone from the list.
        case = GOOD_CASE + (
            "  -\n"
            "    type: regex\n"
            "    name: a-second-pattern\n"
            "    target: trace\n"
            "    pattern: nope\n"
            "    match: not_contains\n"
        )
        names = [g.get("name") for g in check_evals.parse_case(case)["graders"]]
        self.assertEqual(names[-2:], ["hands-it-back", "a-second-pattern"])

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

    def test_a_quoted_max_0_is_still_an_unsatisfiable_range(self):
        errors = self.mutate("    min: 0\n    max: 0", '    max: "0"')
        self.assertTrue(any("max: 0 without min: 0" in e for e in errors), errors)

    def test_a_quoted_not_contains_is_still_an_absence_grader(self):
        # Same trim as `test_a_case_of_nothing_but_absences_has_no_witness`, with
        # the one surviving pattern grader quoted. Read literally, the quotes make
        # it a non-absence grader, so the case acquires a witness it does not have
        # — a crashed run reports it as passing.
        trimmed = GOOD_CASE[: GOOD_CASE.index("  - type: file_exists")]
        quoted = trimmed.replace("match: not_contains", 'match: "not_contains"')
        with SuiteFixture(case=quoted) as fixture:
            self.assertTrue([e for e in fixture.errors() if "witnesses" in e])

    def test_a_flow_mapping_grader_is_reported_not_skipped(self):
        # Partitioned on its first colon, `- {type: regex, …}` yields the junk key
        # `{type` and a grader with no type: every check below is a no-op on it and
        # the witness rule accepts it.
        errors = self.mutate(
            "  - type: regex\n    name: nothing-was-pushed",
            "  - {type: regex, name: nothing-was-pushed,"
            " target: trace, pattern: x, match: not_contains}\n"
            "  - type: regex\n    name: nothing-was-pushed",
        )
        self.assertTrue(any("cannot read" in e for e in errors), errors)

    def test_an_unknown_grader_type_is_not_a_free_witness(self):
        errors = self.mutate("  - type: regex\n", "  - type: Regex\n")
        self.assertTrue(any("not\none this checker has a rule for" in e
                            or "has a rule for" in e for e in errors), errors)

    def test_a_refusal_of_an_ungranted_tool_cannot_be_scored(self):
        errors = self.mutate("[Skill, Bash, Read, Write]", "[Skill, Bash, Read]")
        self.assertTrue(
            any("verdict about Write, which the case does not grant" in e
                for e in errors),
            errors,
        )

    def test_a_demanded_call_on_an_ungranted_tool_cannot_be_scored(self):
        """The mirror of the refusal case: `min: 1` on a tool nobody granted.

        The harness reports this one, but only against `--allow-tools`; a case
        whose own `allowed_tools` withholds the tool passes its reachability
        check and then holds a grader that can never be satisfied.
        """
        errors = self.mutate("    tool: Skill\n", "    tool: WebFetch\n")
        self.assertTrue(
            any("verdict about WebFetch, which the case does not grant" in e
                for e in errors),
            errors,
        )

    def test_exists_true_needs_a_tool_that_can_write_a_file(self):
        errors = self.mutate("[Skill, Bash, Read, Write]", "[Skill, Read]")
        self.assertTrue(
            any("passes only if the run creates src/checkout.js" in e
                for e in errors),
            errors,
        )

    def test_exists_true_is_reachable_through_bash_alone(self):
        """Write is not the only way a run puts a file on disk."""
        errors = self.mutate("[Skill, Bash, Read, Write]", "[Skill, Bash, Read]")
        self.assertFalse(
            [e for e in errors if "passes only if the run creates" in e], errors
        )

    def test_exists_false_does_not_need_a_write_grant(self):
        case = GOOD_CASE.replace(
            "[Skill, Bash, Read, Write]", "[Skill, Read]"
        ).replace("exists: true", "exists: false")
        with SuiteFixture(case=case) as fixture:
            errors = fixture.errors()
        self.assertFalse(
            [e for e in errors if "passes only if the run creates" in e], errors
        )

    def test_a_trace_grader_needs_bash(self):
        errors = self.mutate("[Skill, Bash, Read, Write]", "[Skill, Read, Write]")
        self.assertTrue(any("does not grant Bash" in e for e in errors))

    def test_a_skill_grader_must_name_a_skill_that_exists(self):
        with SuiteFixture(skill="anantys.other") as fixture:
            self.assertTrue(
                any("not in p" in e for e in fixture.errors())
            )

    def dispatch_case(self):
        """GOOD_CASE with its skill-dispatch grader asking about an agent.

        A skill is witnessed by `tool_used: Skill`; an agent is reached through
        `Task`, so the same grader is spelled with a `Task` tool and the agent's
        name in `input_match`. The skill side of that pair is checked against
        the tree; the agent side was not, so a typo in an agent name produced a
        grader that can never fire — and since it is `arm: with-only`, nothing
        downstream would have noticed the dispatch verdict going missing.
        """
        return GOOD_CASE.replace(
            "    tool: Skill\n    input_match: anantys.qa",
            "    tool: Task\n    input_match: anantys.code-auditor",
        ).replace("[Skill, Bash, Read, Write]", "[Task, Bash, Read, Write]")

    def test_a_task_grader_must_name_an_agent_that_exists(self):
        with SuiteFixture(case=self.dispatch_case()) as fixture:
            self.assertTrue(
                any(
                    "matches agent 'anantys.code-auditor'" in e
                    for e in fixture.errors()
                ),
                fixture.errors(),
            )

    def test_a_task_grader_naming_a_present_agent_is_clean(self):
        with SuiteFixture(
            case=self.dispatch_case(), agent="anantys.code-auditor"
        ) as fixture:
            self.assertEqual(fixture.errors(), [])

    def test_name_must_be_the_directory_name(self):
        errors = self.mutate("name: a-case\n", "name: another-case\n")
        self.assertTrue(any("is not the directory name" in e for e in errors))

    def test_a_scaffold_path_escaping_the_case_directory_is_caught(self):
        errors = self.mutate(
            "scaffold_script: scaffold.sh", "scaffold_script: ../other/scaffold.sh"
        )
        self.assertTrue(any("escapes the case directory" in e for e in errors))

    def test_an_absolute_scaffold_path_is_caught(self):
        errors = self.mutate(
            "scaffold_script: scaffold.sh", "scaffold_script: /tmp/scaffold.sh"
        )
        self.assertTrue(any("escapes the case directory" in e for e in errors))

    def test_a_scaffold_path_naming_nothing_is_caught(self):
        errors = self.mutate(
            "scaffold_script: scaffold.sh", "scaffold_script: setup.sh"
        )
        self.assertTrue(any("does not exist" in e for e in errors))

    def test_a_subdirectory_scaffold_path_is_not_an_escape(self):
        # `..` and absolute are the two spellings the harness refuses; a path
        # deeper inside the case directory is legitimate and must stay clean.
        with SuiteFixture(
            case=GOOD_CASE.replace(
                "scaffold_script: scaffold.sh", "scaffold_script: fixture/scaffold.sh"
            )
        ) as fixture:
            nested = fixture.evals / "a-case" / "fixture"
            nested.mkdir()
            (nested / "scaffold.sh").write_text("#!/bin/sh\n")
            self.assertEqual(fixture.errors(), [])

    def test_a_case_with_no_scaffold_is_not_a_finding(self):
        with SuiteFixture(
            case=GOOD_CASE.replace("context:\n  scaffold_script: scaffold.sh\n", "")
        ) as fixture:
            self.assertEqual(fixture.errors(), [])

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
