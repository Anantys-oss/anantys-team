#!/usr/bin/env python3
"""An unnamed field is only a defect if the heading is a field and the template is read.

Both qualifiers carry the gate's whole false-positive budget, so each is tested against
the two shipped shapes it has to separate: an instance heading (`## Environment: staging`)
from a field heading (`### Agent limits`), and a preamble claiming a reader from one
claiming only authorship.
"""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import check_template_fields as ctf


class Preamble(unittest.TestCase):
    def test_stops_at_the_first_example_block(self) -> None:
        text = "# T\n\nRead by `plan`.\n\n```markdown\n## Surfaces\n```\n"
        self.assertNotIn("Surfaces", ctf.preamble(text))
        self.assertIn("Read by", ctf.preamble(text))

    def test_a_template_with_no_block_is_all_preamble(self) -> None:
        self.assertEqual(ctf.preamble("# T\n\nprose\n"), "# T\n\nprose\n")


class IsRead(unittest.TestCase):
    def test_read_by_claims_a_reader(self) -> None:
        self.assertTrue(ctf.is_read("Written by `init`, read by every other action.\n"))

    def test_source_for_claims_a_reader(self) -> None:
        self.assertTrue(ctf.is_read("The non-spec-kit source for `/anantys.qa plan`.\n"))

    def test_authorship_alone_does_not(self) -> None:
        self.assertFalse(ctf.is_read("Written by `/anantys.qa plan` into the spec-kit dir.\n"))

    def test_a_claim_inside_the_block_does_not_count(self) -> None:
        self.assertFalse(ctf.is_read("# T\n\nWritten by `plan`.\n\n```markdown\nread by all\n```\n"))


class Fields(unittest.TestCase):
    def block(self, *lines: str) -> str:
        return "# T\n\nRead by `plan`.\n\n```markdown\n" + "\n".join(lines) + "\n```\n"

    def test_reports_a_field_with_its_line(self) -> None:
        self.assertEqual(ctf.fields(self.block("### Agent limits")), [(6, "Agent limits")])

    def test_drops_a_trailing_gloss(self) -> None:
        text = self.block("### Agent limits — steps a browser agent cannot perform")
        self.assertEqual(ctf.fields(text), [(6, "Agent limits")])

    def test_drops_a_parenthetical(self) -> None:
        self.assertEqual(ctf.fields(self.block("## Reset (local only)")), [(6, "Reset")])

    def test_drops_an_enumerator(self) -> None:
        self.assertEqual(ctf.fields(self.block("## 5. Report format")), [(6, "Report format")])

    def test_a_valued_heading_is_an_instance_not_a_field(self) -> None:
        text = self.block("## Environment: staging (`kind: shared`)", "### Surfaces")
        self.assertEqual(ctf.fields(text), [(7, "Surfaces")])

    def test_a_placeholder_only_heading_is_not_a_field(self) -> None:
        self.assertEqual(ctf.fields(self.block("### A — <journey name>")), [])

    def test_the_preamble_declares_nothing(self) -> None:
        self.assertEqual(ctf.fields("## Not a field\n\nRead by `plan`.\n"), [])

    def test_reports_every_declaration_including_repeats(self) -> None:
        text = self.block("### Credentials", "### Known drift", "### Credentials")
        self.assertEqual([name for _, name in ctf.fields(text)], ["Credentials", "Known drift", "Credentials"])


class Names(unittest.TestCase):
    def test_matches_case_insensitively_inside_a_sentence(self) -> None:
        self.assertTrue(ctf.names("Agent limits", "respect the agent limits block"))

    def test_absent_is_absent(self) -> None:
        self.assertFalse(ctf.names("Agent limits", "respect the credentials block"))

    def test_either_side_of_an_alternation_suffices(self) -> None:
        self.assertTrue(ctf.names("Not shipped / known gaps", "the Not shipped section"))
        self.assertTrue(ctf.names("Not shipped / known gaps", "the known gaps section"))
        self.assertFalse(ctf.names("Not shipped / known gaps", "neither one"))


class Gate(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.skill = self.root / "plugins/p/skills/s"
        (self.skill / "templates").mkdir(parents=True)
        previous = ctf.ROOT
        ctf.ROOT = self.root
        self.addCleanup(setattr, ctf, "ROOT", previous)
        self.stub_git(baseline="base", changed=set())

    def stub_git(self, baseline: str | None, changed: set[str]) -> None:
        for name, value in (("baseline_ref", lambda: baseline), ("changed_paths", lambda _: changed)):
            previous = getattr(ctf, name)
            setattr(ctf, name, value)
            self.addCleanup(setattr, ctf, name, previous)

    def write(self, prose: str, template: str) -> None:
        (self.skill / "SKILL.md").write_text(prose, encoding="utf-8")
        (self.skill / "templates/t.md").write_text(template, encoding="utf-8")

    def run_gate(self) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = ctf.main()
        return code, out.getvalue()

    READ = "# T\n\nRead by `plan`.\n\n```markdown\n### Agent limits\n```\n"
    WRITTEN = "# T\n\nWritten by `plan`.\n\n```markdown\n### Agent limits\n```\n"

    def test_green_when_the_prose_names_the_field(self) -> None:
        self.write("consult the Agent limits block\n", self.READ)
        code, out = self.run_gate()
        self.assertEqual(code, 0)
        self.assertIn("1 fields, 0 unnamed", out)
        self.assertIn("0 errors, 0 warnings", out)

    def test_error_when_the_branch_changed_the_template(self) -> None:
        self.stub_git("base", {"plugins/p/skills/s/templates/t.md"})
        self.write("nothing relevant\n", self.READ)
        code, out = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn("ERROR plugins/p/skills/s/templates/t.md:6", out)
        self.assertIn("1 errors, 0 warnings", out)

    def test_error_when_the_branch_changed_the_prose(self) -> None:
        self.stub_git("base", {"plugins/p/skills/s/SKILL.md"})
        self.write("nothing relevant\n", self.READ)
        self.assertEqual(self.run_gate()[0], 1)

    def test_warn_when_the_branch_touched_neither_file(self) -> None:
        self.stub_git("base", {"plugins/p/skills/s/templates/other.md", "README.md"})
        self.write("nothing relevant\n", self.READ)
        code, out = self.run_gate()
        self.assertEqual(code, 0)
        self.assertIn("WARN plugins/p/skills/s/templates/t.md:6", out)
        self.assertIn("0 errors, 1 warnings", out)

    def test_warn_and_say_so_when_there_is_no_baseline(self) -> None:
        self.stub_git(None, set())
        self.write("nothing relevant\n", self.READ)
        code, out = self.run_gate()
        self.assertEqual(code, 0)
        self.assertIn("baseline none (every mismatch is a warning)", out)

    def test_a_reference_topic_can_name_the_field(self) -> None:
        self.stub_git("base", {"plugins/p/skills/s/templates/t.md"})
        (self.skill / "reference").mkdir()
        (self.skill / "reference/run.md").write_text("read the Agent limits\n", encoding="utf-8")
        self.write("see `reference/run.md`\n", self.READ)
        self.assertEqual(self.run_gate()[0], 0)

    def test_a_written_only_template_is_skipped_visibly(self) -> None:
        self.stub_git("base", {"plugins/p/skills/s/templates/t.md"})
        self.write("nothing relevant\n", self.WRITTEN)
        code, out = self.run_gate()
        self.assertEqual(code, 0)
        self.assertIn("written only", out)
        self.assertNotIn("ERROR", out)

    def test_red_when_no_template_matched(self) -> None:
        code, out = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn("no templates matched", out)


class ThisRepo(unittest.TestCase):
    def test_shipped_templates_carry_no_branch_owned_mismatch(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = ctf.main()
        self.assertEqual(code, 0, out.getvalue())
        self.assertNotIn("ERROR", out.getvalue())

    def test_every_shipped_template_is_classified(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            ctf.main()
        for path in sorted(ctf.ROOT.glob(ctf.TEMPLATES)):
            shown = str(path.relative_to(ctf.ROOT))
            self.assertRegex(out.getvalue(), rf"{shown}: (read by an action|written only)")


if __name__ == "__main__":
    unittest.main()
