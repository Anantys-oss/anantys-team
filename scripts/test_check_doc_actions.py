#!/usr/bin/env python3
"""The cell this gate exists for: an action in the table, absent from the reference.

Every case writes a real `SKILL.md` and a real `README.md`, because the defect lives in
the relation between the two files and a fake of either half cannot hold it. The cases
that must *not* fire get as much room as the one that must: a gate that reddens on prose
mentioning an action, or on a skill that takes an argument instead of a subcommand, is a
gate nobody leaves wired in.
"""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import check_doc_actions as cda

TABLE = """\
---
name: anantys.qa
---

## Actions

Invoked as `/anantys.qa <action> [args]`.

| Action | What it does |
|---|---|
{rows}

## Rules

Something else entirely.
"""


class Harness(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        previous = cda.ROOT
        cda.ROOT = self.root
        self.addCleanup(setattr, cda, "ROOT", previous)

    def skill(self, name: str, *actions: str) -> None:
        path = self.root / "plugins" / "pack" / "skills" / name / "SKILL.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = "\n".join(f"| `{a}` | does {a} |" for a in actions)
        path.write_text(TABLE.format(rows=rows), encoding="utf-8")

    def readme(self, *lines: str) -> None:
        body = ["# pack", "", "```bash", *lines, "```", ""]
        (self.root / "README.md").write_text("\n".join(body), encoding="utf-8")

    def run_check(self) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cda.main()
        return rc, out.getvalue()


class TableAgainstReadme(Harness):
    def test_every_action_documented_passes(self) -> None:
        self.skill("anantys.qa", "init", "run", "report")
        self.readme("/anantys.qa init", "/anantys.qa run --env staging", "/anantys.qa report")
        rc, out = self.run_check()
        self.assertEqual(rc, 0)
        self.assertIn("0 error(s), 0 warning(s)", out)

    def test_undocumented_action_errors(self) -> None:
        self.skill("anantys.qa", "init", "run", "status")
        self.readme("/anantys.qa init", "/anantys.qa run")
        rc, out = self.run_check()
        self.assertEqual(rc, 1)
        self.assertIn("`status`", out)
        self.assertNotIn("`init`", out)

    def test_namespaced_spelling_documents_the_same_action(self) -> None:
        """The command's spelling is contested in this queue; the action is not."""
        self.skill("anantys.qa", "run")
        self.readme("/anantys-team-agents:anantys-qa run")
        self.assertEqual(self.run_check()[0], 0)

    def test_prose_mention_does_not_document(self) -> None:
        """Outside a fence a command is being discussed, not shown."""
        self.skill("anantys.qa", "status")
        (self.root / "README.md").write_text(
            "Run `/anantys.qa status` to see where you are.\n", encoding="utf-8"
        )
        rc, out = self.run_check()
        self.assertEqual(rc, 1)
        self.assertIn("`status`", out)

    def test_action_word_elsewhere_in_the_block_does_not_document(self) -> None:
        """`report` is an English noun in this README three times over."""
        self.skill("anantys.qa", "report")
        self.readme("# produce a quantified report", "/anantys.qa run")
        self.assertEqual(self.run_check()[0], 1)

    def test_another_skills_action_does_not_document_this_one(self) -> None:
        self.skill("anantys.qa", "run")
        self.skill("anantys.ops", "run")
        self.readme("/anantys.qa run")
        rc, out = self.run_check()
        self.assertEqual(rc, 1)
        self.assertIn("anantys.ops", out)
        self.assertNotIn("anantys.qa:", out)


class NotApplicable(Harness):
    def test_skill_without_an_actions_table_is_not_checked(self) -> None:
        """A skill that takes a freeform argument has no action to document."""
        path = self.root / "plugins" / "pack" / "skills" / "anantys.design" / "SKILL.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\nname: anantys.design\n---\n\n## Mission\n\nFix a page.\n", "utf-8")
        self.readme("/anantys.design https://dev.example.com/pricing — fix the hero")
        rc, out = self.run_check()
        self.assertEqual(rc, 0)
        self.assertIn("inert on this tree", out)

    def test_no_table_anywhere_warns_rather_than_reporting_health(self) -> None:
        rc, out = self.run_check()
        self.assertEqual(rc, 0)
        self.assertIn("inert on this tree", out)

    def test_missing_readme_warns_and_does_not_error(self) -> None:
        """The README is the file some other change lands; its absence is not a table defect."""
        self.skill("anantys.qa", "run")
        rc, out = self.run_check()
        self.assertEqual(rc, 1)
        self.assertIn("no README.md", out)
        self.assertIn("`run`", out)

    def test_alias_named_only_in_prose_is_not_owed_a_line(self) -> None:
        """`testplan` is kept for people who already typed it, not advertised."""
        self.skill("anantys.qa", "plan")
        body = (self.root / "plugins" / "pack" / "skills" / "anantys.qa" / "SKILL.md")
        body.write_text(
            body.read_text(encoding="utf-8").replace(
                "## Rules", "`testplan` is still accepted as an alias of `plan`.\n\n## Rules"
            ),
            encoding="utf-8",
        )
        self.readme("/anantys.qa plan")
        self.assertEqual(self.run_check()[0], 0)


class Extraction(unittest.TestCase):
    """`invocation()` against lines written out, never against lines it built."""

    def test_bare_invocation_names_no_action(self) -> None:
        self.assertEqual(cda.invocation("/anantys.qa"), ("qa", None))

    def test_flag_before_a_subcommand_is_not_an_action(self) -> None:
        self.assertEqual(cda.invocation("/anantys.qa --env staging"), ("qa", None))

    def test_url_argument_is_not_an_action(self) -> None:
        self.assertEqual(
            cda.invocation("/anantys.design https://dev.example.com/x — fix it"), ("design", None)
        )

    def test_indented_command_still_invokes(self) -> None:
        self.assertEqual(cda.invocation("    /anantys.qa note A4"), ("qa", "note"))

    def test_line_that_does_not_start_with_the_command_is_not_one(self) -> None:
        self.assertEqual(cda.invocation("see /anantys.qa status"), (None, None))

    def test_declared_spellings_all_read_as_stated(self) -> None:
        for line, skill, action in cda.SPELLINGS:
            with self.subTest(line=line):
                self.assertEqual(cda.invocation(line), (skill, action))


class Positional(unittest.TestCase):
    def test_a_tree_on_the_command_line_is_refused(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            cda.main(["/some/other/tree"])
        self.assertIn("gate_matrix.py", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
