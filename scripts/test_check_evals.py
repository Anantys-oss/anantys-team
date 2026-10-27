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
  timeout_seconds: 420
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
    target: files
    pattern: git\\s+push
    match: not_contains

  - type: tool_used
    name: nothing-was-merged
    tool: Bash
    input_match: git\\s+merge
    min: 0
    max: 0

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
| `nothing-was-merged` — `git\\s+merge` | `git merge x` | `git rebase x` |

| Case | Witness |
|------|---------|
| `a-case` | `the-workspace-survived` |

| Field | Floor | Why this number |
|-------|-------|-----------------|
| `max_turns` | `20` | a case that stops inside it |
| `timeout_seconds` | `420` | uniform across the suite |
| `runs` | `3` | one sample is not a behaviour |

| Case | `--ablation none` | default `with-without` |
|------|-------------------|------------------------|
| `a-case` | `0.50` | `0.60` |
"""

FLOOR_ROW = "| `a-case` | `0.50` | `0.60` |"


def with_floor(none, default, readme=GOOD_README):
    """`readme` with the case's declared crashed-run floor rewritten.

    A test that adds or drops a grader moves the floor, and `check_evals`
    objects to a row that no longer matches — which is the rule working. Such a
    test restates the floor its mutation produces rather than exempting itself.
    """
    return readme.replace(FLOOR_ROW, f"| `a-case` | `{none}` | `{default}` |")


GOOD_SCAFFOLD = """\
#!/usr/bin/env bash
set -euo pipefail
cat > src/checkout.js <<'JS'
const total = subtotal - coupon;
JS
"""


class SuiteFixture:
    """A plugin tree the checker can be pointed at."""

    def __init__(
        self,
        case=GOOD_CASE,
        readme=GOOD_README,
        skill="anantys.qa",
        agent=None,
        scaffold=GOOD_SCAFFOLD,
    ):
        self.tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(self.tmp.name)
        self.evals = root / "plugins" / "p" / "evals"
        (self.evals / "a-case").mkdir(parents=True)
        (self.evals / "a-case" / "case.yaml").write_text(case)
        (self.evals / "a-case" / "scaffold.sh").write_text(scaffold)
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
                "nothing-was-merged",
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
        case = GOOD_CASE.replace("    target: files\n", "    target: trace\n")
        with SuiteFixture(
            case=case.replace("[Skill, Bash, Read, Write]", "[Skill, Read, Write]")
        ) as fixture:
            errors = fixture.errors()
        self.assertTrue(any("does not grant Bash" in e for e in errors), errors)

    def test_a_not_contains_over_the_trace_also_forbids_the_prose(self):
        # `trace` is the whole message stream, so the pattern is matched against
        # the assistant's own words. Every refusal here orders the role to hand
        # the forbidden command back, which makes the compliant run the one that
        # fails. The verdict belongs on the call.
        errors = self.mutate("    target: files\n", "    target: trace\n")
        self.assertTrue(any("assistant's own prose" in e for e in errors), errors)

    def test_a_contains_over_the_trace_is_not_the_same_mistake(self):
        # A witness grader asserts the role *did* something; the extra prose can
        # only make it easier to satisfy, never wrong.
        errors = self.mutate(
            "    target: files\n    pattern: git\\s+push\n    match: not_contains",
            "    target: trace\n    pattern: git\\s+push\n    match: contains",
        )
        self.assertEqual([e for e in errors if "prose" in e], [])

    def test_an_input_match_pattern_is_verified_against_its_row(self):
        # A `tool_used` `input_match` on a plain tool carries the same two-sided
        # risk a `regex` pattern does, so it earns the same README row.
        errors = self.mutate("    input_match: git\\s+merge", "    input_match: git")
        self.assertTrue(any("drifted" in e for e in errors), errors)

    def test_an_input_match_row_that_matches_a_legitimate_command_fails(self):
        readme = GOOD_README.replace("`git rebase x`", "`git merge x`")
        errors = self.mutate("    input_match: git\\s+merge", "    input_match: git\\s+merge", readme=readme)
        self.assertTrue(any("which is\nlegitimate" in e or "legitimate" in e for e in errors), errors)

    def test_a_router_input_match_needs_no_vector_row(self):
        # `input_match: anantys.qa` names a role, not a pattern over a command.
        with SuiteFixture() as fixture:
            self.assertEqual(
                [e for e in fixture.errors() if "skill-fired" in e], []
            )

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


class TestFixtureSupply(unittest.TestCase):
    """A `contains` pattern the case's own scaffold writes into the workspace."""

    # One `contains` grader beside the known-good case's witness. The pattern is
    # the number the fixture below puts in the file, which is the shape
    # `asserts-the-spec-value` had: an outcome grader a read makes green.
    OUTCOME = """\
  - type: regex
    name: asserts-the-value
    target: trace
    pattern: 108\\.0
    match: contains

"""
    ROW = "| `asserts-the-value` — `108\\.0` | `== 108.0` | `110.0` |\n"

    def fixture(self, scaffold, **kwargs):
        case = GOOD_CASE.replace("  - type: llm", self.OUTCOME + "  - type: llm")
        # The outcome grader is a seventh, non-vacuous verdict: 3/7 and 3/6.
        return SuiteFixture(
            case=case,
            readme=with_floor("0.43", "0.50") + self.ROW,
            scaffold=scaffold,
            **kwargs,
        )

    def test_a_pattern_the_scaffold_writes_into_the_fixture_is_caught(self):
        scaffold = GOOD_SCAFFOLD + "cat > spec.md <<'MD'\nreturns 108.00\nMD\n"
        with self.fixture(scaffold) as fixture:
            errors = [e for e in fixture.errors() if "asserts-the-value" in e]
        self.assertTrue(
            any("satisfied by spec.md" in e for e in errors),
            f"expected the fixture-supply error, got {errors}",
        )

    def test_the_same_pattern_is_clean_when_the_fixture_does_not_supply_it(self):
        with self.fixture(GOOD_SCAFFOLD) as fixture:
            self.assertEqual(fixture.errors(), [])

    def test_the_declared_witness_may_be_supplied_by_the_fixture(self):
        # `the-changed-symbol-was-traced` is satisfied by reading the file the
        # scaffold wrote, on purpose: a witness separates a run from a crash,
        # and the empty trace a sealed sandbox leaves holds nothing the scaffold
        # wrote. Declaring this grader the witness has to exempt it.
        scaffold = GOOD_SCAFFOLD + "cat > spec.md <<'MD'\nreturns 108.00\nMD\n"
        readme = with_floor("0.43", "0.50").replace(
            "| `a-case` | `the-workspace-survived` |",
            "| `a-case` | `asserts-the-value` |",
        )
        case = GOOD_CASE.replace("  - type: llm", self.OUTCOME + "  - type: llm")
        with SuiteFixture(
            case=case, readme=readme + self.ROW, scaffold=scaffold
        ) as fixture:
            self.assertEqual(fixture.errors(), [])

    def test_the_path_a_witness_names_is_not_fixture_content(self):
        # The discriminator is the heredoc body, never the `cat >` target: a
        # witness pattern naming the file it asserts a read of would otherwise
        # report itself.
        written = check_evals.scaffold_fixture(
            "cat > specs/412-order-total/spec.md <<'MD'\nAC2.\nMD\n"
        )
        self.assertEqual(written, {"specs/412-order-total/spec.md": "AC2."})

    def test_a_printf_written_file_is_not_read_as_fixture_content(self):
        # Only the heredoc idiom is parsed. The handful of `printf` writes in
        # this suite hold one line of code each, and keeping the parser to one
        # shape is what keeps this checker shell-free.
        self.assertEqual(check_evals.scaffold_fixture("printf 'x\\n' > a.js\n"), {})

    def test_a_case_with_no_witness_row_is_an_error(self):
        with SuiteFixture(readme=GOOD_README.replace("| `a-case` |", "| `b` |")) as f:
            self.assertTrue([e for e in f.errors() if "no witness row" in e])

    def test_a_declared_witness_that_is_not_scored_is_an_error(self):
        # The role was silently reassigned: the grader README names is gone, and
        # `witnesses()` alone would accept whichever one is left.
        readme = GOOD_README.replace("`the-workspace-survived`", "`the-source-was-read`")
        with SuiteFixture(readme=readme) as fixture:
            errors = [e for e in fixture.errors() if "the-source-was-read" in e]
        self.assertTrue(any("is the witness" in e for e in errors), errors)


class TestVectorTable(unittest.TestCase):
    def test_typographic_dashes_in_a_vector_are_normalised(self):
        row = "| `g` — `a‑b` | `a‑b` | `c` |"
        self.assertEqual(check_evals.code_spans(check_evals.split_row(row)[1]), ["a-b"])

    def test_a_row_without_an_em_dash_is_not_a_vector_row(self):
        row = "| `plain` | `cell` | `cell` |"
        self.assertEqual(check_evals.parse_vector_table(row), {})


class TestBudgetFloors(unittest.TestCase):
    """A run that does not finish errors, and an errored run scores by absence.

    The loader rejects `0` for each of these three fields and accepts `1`, so
    `max_turns: 1` is the same crash as `max_turns: 0` in a spelling the schema
    likes.
    """

    def test_the_good_fixture_sits_on_or_above_every_floor(self):
        with SuiteFixture() as fixture:
            self.assertEqual(
                [e for e in fixture.errors() if "floor" in e or e.endswith("by 0")],
                [],
            )

    def test_a_turn_budget_below_the_floor_is_caught(self):
        case = GOOD_CASE.replace("max_turns: 25", "max_turns: 1")
        with SuiteFixture(case=case) as fixture:
            self.assertTrue([e for e in fixture.errors() if "below the floor" in e])

    def test_a_timeout_below_the_floor_is_caught(self):
        case = GOOD_CASE.replace("timeout_seconds: 420", "timeout_seconds: 1")
        with SuiteFixture(case=case) as fixture:
            self.assertTrue([e for e in fixture.errors() if "below the floor" in e])

    def test_a_single_run_is_not_a_behaviour(self):
        case = GOOD_CASE.replace("runs: 3", "runs: 1")
        with SuiteFixture(case=case) as fixture:
            self.assertTrue([e for e in fixture.errors() if "below the floor" in e])

    def test_a_missing_budget_field_is_the_harness_default(self):
        case = GOOD_CASE.replace("  timeout_seconds: 420\n", "")
        with SuiteFixture(case=case) as fixture:
            self.assertTrue([e for e in fixture.errors() if "no timeout_seconds" in e])

    def test_a_floor_the_readme_stops_declaring_is_an_error(self):
        readme = "\n".join(
            line for line in GOOD_README.splitlines() if "| `max_turns` |" not in line
        )
        with SuiteFixture(readme=readme) as fixture:
            self.assertTrue(
                [e for e in fixture.errors() if "no floor row for 'max_turns'" in e]
            )

    def test_the_floor_table_is_not_read_as_a_witness_row(self):
        # Three cells, so `parse_witness_table`'s two-cell shape skips it; one
        # code span in the first cell, so the vector table's two-span head does
        # too. A floor row misread as a witness row hands the case a witness
        # named `20`.
        self.assertEqual(
            check_evals.parse_witness_table(GOOD_README),
            {"a-case": "the-workspace-survived"},
        )
        self.assertEqual(
            check_evals.parse_floor_table(GOOD_README),
            {"max_turns": 20, "timeout_seconds": 420, "runs": 3},
        )


class TestWithOnlyIsTheRoutingIndicator(unittest.TestCase):
    """`arm: with-only` takes a grader out of the score, silently.

    `witnesses()` honours the same flag, so the gate that would have noticed the
    missing verdict stops counting the grader too — the case keeps its witness
    and simply scores one thing fewer than it reads as scoring.
    """

    def test_the_indicator_itself_is_clean(self):
        with SuiteFixture() as fixture:
            self.assertEqual(
                [e for e in fixture.errors() if "routing indicator" in e], []
            )

    def test_the_flag_on_a_regex_grader_is_caught(self):
        case = GOOD_CASE.replace(
            "    match: not_contains\n",
            "    match: not_contains\n    arm: with-only\n",
        )
        with SuiteFixture(case=case) as fixture:
            errors = [e for e in fixture.errors() if "routing indicator" in e]
            self.assertTrue(errors)
            self.assertIn("nothing-was-pushed", errors[0])

    def test_the_flag_on_a_tool_used_grader_about_a_plain_tool_is_caught(self):
        case = GOOD_CASE.replace(
            """    tool: Write
    min: 0
    max: 0
""",
            """    tool: Write
    min: 0
    max: 0
    arm: with-only
""",
        )
        with SuiteFixture(case=case) as fixture:
            self.assertTrue([e for e in fixture.errors() if "routing indicator" in e])

    def test_a_task_router_is_as_valid_as_a_skill_router(self):
        case = GOOD_CASE.replace(
            "    tool: Skill\n    input_match: anantys.qa",
            "    tool: Task\n    input_match: an-agent",
        )
        with SuiteFixture(case=case, agent="an-agent") as fixture:
            self.assertEqual(
                [e for e in fixture.errors() if "routing indicator" in e], []
            )


class TestCrashedRunFloor(unittest.TestCase):
    """The floor is a number, and `--ablation` decides which number it is.

    The fixture holds six graders: one `arm: with-only` indicator and three that
    pass by absence. `--ablation none` scores all six (3/6 = 0.50); the default
    `with-without` scores five (3/5 = 0.60). Measured on CLI 2.1.278 against the
    live suite, the same two columns differ for every case that has an
    indicator — which is every case here.
    """

    def test_both_columns_are_computed_from_the_graders(self):
        graders = check_evals.parse_case(GOOD_CASE)["graders"]
        self.assertEqual(check_evals.crash_floors(graders), ("0.50", "0.60"))

    def test_the_documented_floors_are_read_without_the_other_tables(self):
        self.assertEqual(
            check_evals.parse_case_floor_table(GOOD_README),
            {"a-case": ("0.50", "0.60")},
        )
        # Two decimals keep the budget-floor rows out: `20` is `isdigit()`, so
        # a row misread the other way would declare a floor of `max_turns`.
        self.assertNotIn("max_turns", check_evals.parse_case_floor_table(GOOD_README))
        self.assertEqual(
            check_evals.parse_floor_table(GOOD_README),
            {"max_turns": 20, "timeout_seconds": 420, "runs": 3},
        )

    def test_the_good_fixture_agrees_with_its_documented_floor(self):
        with SuiteFixture() as fixture:
            self.assertEqual(
                [e for e in fixture.errors() if "crashed-run floor" in e or
                 "documented as floor" in e],
                [],
            )

    def test_a_case_with_no_floor_row_is_an_error(self):
        readme = "\n".join(
            line for line in GOOD_README.splitlines() if "`0.50`" not in line
        )
        with SuiteFixture(readme=readme) as fixture:
            errors = [e for e in fixture.errors() if "no crashed-run floor row" in e]
            self.assertTrue(errors)
            self.assertIn("0.60", errors[0])

    def test_a_dropped_absence_grader_moves_the_floor_and_is_caught(self):
        case = GOOD_CASE.replace(
            """  - type: tool_used
    name: nothing-was-written
    tool: Write
    min: 0
    max: 0

""",
            "",
        )
        with SuiteFixture(case=case) as fixture:
            errors = [e for e in fixture.errors() if "documented as floor" in e]
            self.assertTrue(errors)
            self.assertIn("0.40/0.50", errors[0])

    def test_marking_a_grader_with_only_moves_the_floor_and_is_caught(self):
        # The flag's own rule catches this too, but through a different reading:
        # it objects to the flag's placement, this one reports the number the
        # placement changed. A case can be mutated into a clean placement with a
        # moved floor — adding a second router — and then only this rule speaks.
        case = GOOD_CASE.replace(
            "    input_match: anantys.qa\n    min: 1\n    arm: with-only\n",
            "    input_match: anantys.qa\n    min: 1\n",
        )
        with SuiteFixture(case=case) as fixture:
            errors = [e for e in fixture.errors() if "documented as floor" in e]
            self.assertTrue(errors)
            self.assertIn("0.50/0.50", errors[0])

    def test_the_live_suite_matches_what_its_readme_declares(self):
        # The gate asserts this for the tree it runs in; this test asserts the
        # two columns were not transcribed from the docstring they replaced.
        evals = check_evals.REPO / "plugins" / "anantys-team-agents" / "evals"
        declared = check_evals.parse_case_floor_table((evals / "README.md").read_text())
        self.assertEqual(len(declared), 10)
        self.assertEqual(declared["debug-stops-without-the-browser"], ("0.40", "0.50"))
        for case_file in sorted(evals.glob("*/case.yaml")):
            graders = check_evals.parse_case(case_file.read_text())["graders"]
            self.assertEqual(
                check_evals.crash_floors(graders),
                declared[case_file.parent.name],
                case_file.parent.name,
            )


if __name__ == "__main__":
    unittest.main()
