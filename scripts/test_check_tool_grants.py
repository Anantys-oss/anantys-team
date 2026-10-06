#!/usr/bin/env python3
"""Fixture tests for check_tool_grants — run: python3 -m unittest discover scripts"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import check_tool_grants as c  # noqa: E402


def role(grants, body, agents=()):
    return c.check(Path("role.md"), grants, body, {"navigate", "tabs_context_mcp"}, agents)


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
        _, warnings = role(["Bash(ls:*)"], "Read the journal.")
        self.assertIn("`Bash(ls:*)`", warnings[0])

    def test_generic_grants_are_never_unreferenced(self):
        _, warnings = role(["Read", "Write", "Glob"], "Do the thing.")
        self.assertEqual(warnings, [])


class UnboundedGrant(unittest.TestCase):
    """A prefix that bounds only the first word is bare `Bash` in disguise."""

    def test_a_command_that_runs_other_commands_is_not_a_narrowing(self):
        errors, _ = role(["Bash(git:*)"], "Commit the report with git.")
        self.assertIn("`Bash(git:*)` is not a narrowing", errors[0])

    def test_it_fires_even_when_the_prose_exercises_the_grant(self):
        """The mention warning is silent in exactly this case — the common one."""
        errors, warnings = role(["Bash(git:*)"], "```bash\ngit log --oneline -1\n```")
        self.assertIn("is not a narrowing", errors[0])
        self.assertEqual(warnings, [])

    def test_naming_a_subcommand_is_a_narrowing(self):
        errors, _ = role(["Bash(git log:*)"], "```bash\ngit log --oneline -1\n```")
        self.assertEqual(errors, [])

    def test_a_bounded_command_is_not_reported(self):
        errors, _ = role(["Bash(mkdir:*)"], "```bash\nmkdir -p out\n```")
        self.assertEqual(errors, [])

    def test_bare_bash_is_not_reported_as_a_false_narrowing(self):
        """`Bash` claims nothing, so there is no narrowing to contradict."""
        errors, _ = role(["Bash"], "```bash\ngit push origin HEAD\n```")
        self.assertEqual(errors, [])


class InlineCommands(unittest.TestCase):
    """A command written mid-sentence is still a command the grant must permit.

    On bash fences alone this check had an empty input set for every role it
    ran on: `ops` is the only role with a narrowed grant set, and it writes its
    one command — `mkdir -p` — in a sentence.
    """

    def test_an_inline_span_is_checked_against_the_grant(self):
        errors, _ = role(["Bash(ls:*)"], "Create it first with `mkdir -p out`.")
        self.assertIn("`mkdir -p out`", errors[0])

    def test_a_flag_reaches_a_command_no_grant_mentions(self):
        """`rm` heads no grant and is not UNBOUNDED — the head anchor is blind to it."""
        errors, _ = role(["Bash(ls:*)"], "Clear it with `rm -rf build`.")
        self.assertIn("`rm -rf build`", errors[0])

    def test_a_flagless_ungranted_command_is_the_documented_gap(self):
        """Named so the gap is a decision, not a surprise. See `bash_commands`."""
        errors, _ = role(["Bash(ls:*)"], "Fetch it with `curl`.")
        self.assertEqual(errors, [])

    def test_an_inline_span_its_grant_permits_passes(self):
        errors, _ = role(["Bash(mkdir:*)"], "Create it first with `mkdir -p out`.")
        self.assertEqual(errors, [])

    def test_a_narrowed_grant_rejects_a_sibling_subcommand_inline(self):
        errors, _ = role(["Bash(git log:*)"], "Record it with `git rev-parse HEAD`.")
        self.assertIn("`git rev-parse HEAD`", errors[0])

    def test_a_backticked_path_is_not_a_command(self):
        """Nothing in the markup separates `mkdir -p` from `current.md`."""
        errors, _ = role(["Bash(ls:*)"], "Overwrite `current.md` and `./seo/`.")
        self.assertEqual(errors, [])

    def test_a_known_mcp_tool_name_is_not_a_command(self):
        """`find` is live in this tree as both a shell command and a browser tool."""
        errors, _ = c.check(
            Path("role.md"), ["Bash(ls:*)", "mcp__x__find"], "Use `find` to locate it.", {"find"}
        )
        self.assertEqual(errors, [])

    def test_the_same_span_is_a_command_when_no_tool_claims_the_name(self):
        """The exclusion is the mcp vocabulary, not a hardcoded word."""
        errors, _ = role(["Bash(ls:*)"], "Use `find` to locate it.")
        self.assertIn("`find`", errors[0])


class NamingIsNotRunning(unittest.TestCase):
    """A role that justifies a grant it withholds must not be read as wanting it.

    This is the one direction where a false positive inverts the gate: the
    cheapest way to discharge it is to add the grant, or to delete the sentence
    explaining why the grant is absent. Live in this tree — `ops` writes
    "`allowed-tools` grants no `git`", and `git` is `UNBOUNDED`, so the head
    anchor read the justification as an invocation.
    """

    def test_a_grant_the_prose_says_it_withholds_is_not_an_invocation(self):
        errors, _ = role(
            ["Bash(mkdir:*)", "Bash(ls:*)"],
            "`allowed-tools` grants no `git` — this role never needs it.",
        )
        self.assertEqual(errors, [])

    def test_a_forbidden_command_is_not_an_invocation(self):
        errors, _ = role(["Bash(ls:*)"], "Never run `git reset --hard` here.")
        self.assertEqual(errors, [])

    def test_negation_does_not_reach_across_a_sentence(self):
        """Otherwise one `not` anywhere above discharges the rest of the file."""
        errors, _ = role(["Bash(ls:*)"], "This is not a runbook. Record it with `git log`.")
        self.assertIn("`git log`", errors[0])

    def test_an_unnegated_mention_is_still_a_command(self):
        errors, _ = role(["Bash(ls:*)"], "Record it with `git log --oneline`.")
        self.assertIn("`git log --oneline`", errors[0])

    def test_a_fenced_command_is_an_invocation_whatever_the_prose_says(self):
        """A fence is a runbook line. Negation reads spans, never fences."""
        errors, _ = role(["Bash(ls:*)"], "Never do this:\n\n```bash\ngit reset --hard\n```\n")
        self.assertIn("`git reset --hard`", errors[0])


class MentionIsNotSpelling(unittest.TestCase):
    """What counts as referencing a grant. Both cases here were live in this tree."""

    AUDITOR = "anantys.code-auditor"

    def test_an_ordinary_word_does_not_discharge_a_grant_that_shares_it(self):
        """`qa` held an unexercised `Task` in silence because it writes about tasks."""
        _, warnings = role(["Task"], "Read tasks.md, then group by task, not by concern.")
        self.assertIn("`Task`", warnings[0])

    def test_a_substring_of_another_word_does_not_discharge_a_command_grant(self):
        _, warnings = role(["Bash(ls:*)"], "Use whichever tools the role was granted.")
        self.assertIn("`Bash(ls:*)`", warnings[0])

    def test_the_grant_named_as_written_still_passes(self):
        _, warnings = role(["AskUserQuestion"], "Confirm with AskUserQuestion first.")
        self.assertEqual(warnings, [])

    def test_a_dispatch_discharges_the_task_grant(self):
        """`review` names the agent, never the tool — and it is the role that dispatches."""
        _, warnings = role(["Task"], f"Dispatch the `{self.AUDITOR}` agent.", {self.AUDITOR})
        self.assertEqual(warnings, [])

    def test_dispatching_without_the_task_grant_is_an_error(self):
        errors, _ = role(["Read"], f"Dispatch the `{self.AUDITOR}` agent.", {self.AUDITOR})
        self.assertIn(self.AUDITOR, errors[0])
        self.assertIn("`Task` is not granted", errors[0])

    def test_a_name_that_is_no_agent_in_the_tree_is_not_a_dispatch(self):
        errors, _ = role(["Read"], f"Dispatch the `{self.AUDITOR}` agent.", set())
        self.assertEqual(errors, [])


class ProseSurface(unittest.TestCase):
    """A split SKILL.md must not shrink what the checker reads."""

    def setUp(self):
        import tempfile

        self.skill = Path(tempfile.mkdtemp()) / "SKILL.md"
        self.skill.parent.mkdir(parents=True, exist_ok=True)

    def _skill(self, body, **refs):
        self.skill.write_text(body, encoding="utf-8")
        if refs:
            (self.skill.parent / "reference").mkdir(exist_ok=True)
            for name, text in refs.items():
                (self.skill.parent / "reference" / f"{name}.md").write_text(text, encoding="utf-8")
        return self.skill

    def test_a_skill_without_a_reference_dir_is_unchanged(self):
        body, warnings = c.prose_surface(self._skill("just prose\n"), "just prose\n")
        self.assertEqual((body, warnings), ("just prose\n", []))

    def test_a_named_reference_file_joins_the_prose(self):
        text = "Read `reference/run.md` first.\n"
        body, warnings = c.prose_surface(self._skill(text, run="Ask with AskUserQuestion.\n"), text)
        self.assertIn("AskUserQuestion", body)
        self.assertEqual(warnings, [])

    def test_a_grant_justified_only_in_a_reference_file_is_not_unreferenced(self):
        """The false positive the qa split introduces: the sole body mention moved."""
        text = "Actions are in `reference/run.md`.\n"
        path = self._skill(text, run="Confirm with AskUserQuestion before running.\n")
        body, _ = c.prose_surface(path, text)
        _, warnings = c.check(path, ["AskUserQuestion"], body, set())
        self.assertEqual(warnings, [])

    def test_an_ungranted_command_in_a_reference_file_is_still_an_error(self):
        text = "Steps: `reference/run.md`.\n"
        path = self._skill(text, run="```bash\nrm -rf build\n```\n")
        body, _ = c.prose_surface(path, text)
        errors, _ = c.check(path, ["Bash(ls:*)"], body, set())
        self.assertIn("`rm -rf build`", errors[0])

    def test_an_unnamed_reference_file_warns(self):
        text = "Only `reference/run.md` is named.\n"
        path = self._skill(text, run="steps\n", orphan="prose no action reads\n")
        body, warnings = c.prose_surface(path, text)
        self.assertNotIn("no action reads", body)
        self.assertEqual(warnings, ["reference/orphan.md is not named in SKILL.md — no action loads it"])


class Baseline(unittest.TestCase):
    """A gate must be introducible green while its violations still exist."""

    OFFENCE = "plugins/p/skills/s/SKILL.md: prose commits to driving a browser but grants no browser tool"

    def setUp(self):
        import tempfile

        self.root = Path(tempfile.mkdtemp())
        skill = self.root / "plugins/p/skills/s/SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("---\nallowed-tools: Read\n---\nDrive a browser.\n", encoding="utf-8")
        self.addCleanup(setattr, c, "BASELINE", c.BASELINE)
        c.BASELINE = self.root / "baseline.txt"

    def _declare(self, text):
        c.BASELINE.write_text(text, encoding="utf-8")

    def _run(self):
        """(exit code, report) — captured, so a suite run stays readable."""
        import contextlib
        import io

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = c.main(self.root)
        return code, out.getvalue()

    def test_an_undeclared_error_fails(self):
        self.assertEqual(self._run()[0], 1)

    def test_a_declared_error_does_not_fail(self):
        self._declare(f"# comment\n\n{self.OFFENCE}\n")
        code, report = self._run()
        self.assertEqual(code, 0)
        self.assertIn("BASE ", report)

    def test_declaring_one_error_does_not_excuse_another(self):
        self._declare("plugins/p/skills/s/SKILL.md: something else entirely\n")
        self.assertEqual(self._run()[0], 1)

    def test_a_stale_entry_warns_instead_of_failing(self):
        """The fix landing must not turn the gate red in its turn."""
        self._declare("plugins/p/skills/s/SKILL.md: an error nothing reports\n")
        skill = self.root / "plugins/p/skills/s/SKILL.md"
        skill.write_text("---\nallowed-tools: Read\n---\nNo hands here.\n", encoding="utf-8")
        code, report = self._run()
        self.assertEqual(code, 0)
        self.assertIn("fixed, so delete", report)


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
