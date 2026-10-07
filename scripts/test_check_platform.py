#!/usr/bin/env python3
"""Every case here is a mutation the loader was measured to accept in silence."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import check_platform as cp

GOOD_SKILL = """---
name: anantys.debug
description: Debug by observing the running app.
allowed-tools: mcp__claude-in-chrome__navigate, Read, Bash(git:*)
---

body
"""


class CheckPlatform(unittest.TestCase):
    def setUp(self) -> None:
        cp.errors.clear()
        cp.warnings.clear()
        self.tmp = tempfile.TemporaryDirectory()
        cp.ROOT = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def check(self, text: str) -> list[str]:
        path = cp.ROOT / "SKILL.md"
        path.write_text(text, encoding="utf-8")
        cp.check_component(path, cp.SKILL_KEYS, "allowed-tools")
        return cp.errors

    def test_known_good_skill_is_clean(self) -> None:
        self.assertEqual(self.check(GOOD_SKILL), [])

    def test_underscore_typo_unsets_the_grant(self) -> None:
        found = self.check(GOOD_SKILL.replace("allowed-tools:", "allowed_tools:"))
        self.assertEqual(len(found), 1)
        self.assertIn("allowed_tools", found[0])

    def test_single_underscore_mcp_name_is_not_a_tool(self) -> None:
        found = self.check(GOOD_SKILL.replace("mcp__claude-in-chrome__navigate", "mcp_chrome_nav"))
        self.assertEqual(len(found), 1)
        self.assertIn("mcp_chrome_nav", found[0])

    def test_scoped_bash_grant_is_well_formed(self) -> None:
        self.assertEqual(self.check(GOOD_SKILL.replace("Bash(git:*)", "Bash(mkdir:*)")), [])

    def test_multi_word_scoped_grant_is_one_token(self) -> None:
        # `Bash(git diff:*)` holds a space. A checker that splits on whitespace
        # rejects the narrowest grants and pushes authors back to `Bash(git:*)`.
        narrowed = "allowed-tools: Bash(git diff:*), Bash(gh pr view:*), Read"
        self.assertEqual(self.check(GOOD_SKILL.replace(GOOD_SKILL.splitlines()[3], narrowed)), [])

    def test_block_sequence_grants_are_still_checked(self) -> None:
        # The form a 500-character grant line invites. Read only the key's own
        # line and the value is the empty string: nothing is iterated, and the
        # typo below comes back as a clean tree.
        wrapped = (
            "allowed-tools:\n"
            "  - mcp__claude-in-chrome__navigate\n"
            "  - mcp_chrome_nav\n"
            "  - Bash(git diff:*)"
        )
        found = self.check(GOOD_SKILL.replace(GOOD_SKILL.splitlines()[3], wrapped))
        self.assertEqual(len(found), 1)
        self.assertIn("mcp_chrome_nav", found[0])

    def test_a_well_formed_block_sequence_stays_clean(self) -> None:
        wrapped = "allowed-tools:\n  - Read\n  - Bash(git diff:*)\n  - mcp__chrome__read_page"
        self.assertEqual(self.check(GOOD_SKILL.replace(GOOD_SKILL.splitlines()[3], wrapped)), [])

    def test_a_flow_sequence_wrapped_onto_a_second_line_is_checked(self) -> None:
        wrapped = "allowed-tools: [Read,\n  mcp_chrome_nav, Bash(git:*)]"
        found = self.check(GOOD_SKILL.replace(GOOD_SKILL.splitlines()[3], wrapped))
        self.assertEqual(len(found), 1)
        self.assertIn("mcp_chrome_nav", found[0])

    def test_a_declared_but_empty_grant_list_is_an_error(self) -> None:
        # `allowed-tools:` with nothing under it sets no narrowing at all, and
        # reads to any line-wise parser exactly like a file that never declared
        # the key — the one case this gate must not report as clean.
        found = self.check(GOOD_SKILL.replace(GOOD_SKILL.splitlines()[3], "allowed-tools:"))
        self.assertEqual(len(found), 1)
        self.assertIn("no tool under it", found[0])

    def test_an_absent_grant_key_is_charged_as_the_widest_grant(self) -> None:
        # Not the empty-list error — a distinct one. Both end in grants unset, but
        # only this shape leaves nothing in the file for a reviewer to read, and
        # only this one is reached by deleting a line rather than mangling it.
        found = self.check("---\nname: x\ndescription: y\n---\n\nbody\n")
        self.assertEqual(len(found), 1)
        self.assertIn("no `allowed-tools:`", found[0])

    def test_an_unreadable_block_is_reported_once(self) -> None:
        # The absent-key error must not pile onto a file whose frontmatter never
        # parsed: nothing was declared because nothing was read.
        found = self.check("---\nname: x\ndescription: y\n\nbody\n")
        self.assertEqual(len(found), 1)
        self.assertIn("never closed", found[0])

    def test_unclosed_frontmatter_drops_every_field(self) -> None:
        found = self.check("---\nname: x\ndescription: y\n\nbody\n")
        self.assertEqual(len(found), 1)
        self.assertIn("never closed", found[0])

    def test_missing_frontmatter_is_an_error(self) -> None:
        found = self.check("just a body\n")
        self.assertEqual(len(found), 1)
        self.assertIn("no frontmatter", found[0])

    def test_a_key_declared_twice_is_reported(self) -> None:
        # `claude plugin validate` passes this file and YAML keeps only the last
        # occurrence, so neither the loader nor a reader says which one is in force.
        found = self.check(GOOD_SKILL.replace("\n---\n\nbody", "\nallowed-tools: Read\n---\n\nbody"))
        self.assertTrue(any("declares `allowed-tools` 2 times" in e for e in found), found)

    def test_the_shape_check_reads_the_declaration_the_loader_keeps(self) -> None:
        # A malformed identifier in the *last* declaration is the one that loads.
        # Reading the first instead shape-checks a list that was thrown away.
        found = self.check(
            GOOD_SKILL.replace("\n---\n\nbody", "\nallowed-tools: mcp_bad_tool\n---\n\nbody")
        )
        self.assertTrue(any("`mcp_bad_tool` is not a well-formed" in e for e in found), found)

    def test_a_single_declaration_is_not_reported_as_duplicated(self) -> None:
        self.assertEqual(self.check(GOOD_SKILL), [])

    def test_a_block_sequence_grant_list_still_reads_as_declared(self) -> None:
        # The value is the empty string on the key's own line; the grants follow on
        # indented lines. Truthiness on that string is how this check goes quiet.
        found = self.check(
            "---\nname: x\ndescription: y\nallowed-tools:\n  - Read\n  - mcp_bad\n---\n\nbody\n"
        )
        self.assertTrue(any("`mcp_bad` is not a well-formed" in e for e in found), found)

    def test_agent_keys_differ_from_skill_keys(self) -> None:
        path = cp.ROOT / "agent.md"
        path.write_text(
            '---\nname: a\ndescription: d\ntools: ["Bash", "Read"]\nmodel: opus\n---\nbody\n',
            encoding="utf-8",
        )
        cp.check_component(path, cp.AGENT_KEYS, "tools")
        self.assertEqual(cp.errors, [])


class Discovery(unittest.TestCase):
    """What the gate does when it is asked about a tree it cannot see."""

    def setUp(self) -> None:
        cp.errors.clear()
        cp.warnings.clear()
        self.tmp = tempfile.TemporaryDirectory()
        cp.ROOT = Path(self.tmp.name)
        self.asked: list[Path] = []
        # The two things `main` reaches outside the tree: the CLI, and the call
        # that runs it. Stub both so the test measures discovery and nothing else.
        self.enterContext(mock.patch.object(cp.shutil, "which", return_value="/usr/bin/claude"))
        self.enterContext(
            mock.patch.object(cp, "ask_the_loader", lambda d, strict: self.asked.append(d))
        )
        self.addCleanup(self.tmp.cleanup)

    def plugin(self, name: str) -> Path:
        manifest = cp.ROOT / "plugins" / name / ".claude-plugin" / "plugin.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text("{}", encoding="utf-8")
        return manifest.parent.parent

    def skill(self, plugin_dir: Path, name: str, text: str) -> None:
        path = plugin_dir / "skills" / name / "SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_text(text, encoding="utf-8")

    def test_empty_discovery_fails_rather_than_reporting_clean(self) -> None:
        # Zero matches used to print `0 error(s), 0 warning(s)` and exit 0 —
        # byte-identical to a healthy run, with the loader never asked.
        self.assertEqual(cp.main([]), 1)
        self.assertEqual(self.asked, [])

    def test_an_error_in_one_plugin_does_not_mute_the_loader_on_the_next(self) -> None:
        first = self.plugin("a-first")
        self.skill(first, "s", GOOD_SKILL.replace("allowed-tools:", "allowed_tools:"))
        second = self.plugin("z-second")
        self.skill(second, "s", GOOD_SKILL)
        self.assertEqual(cp.main([]), 1)
        self.assertEqual(self.asked, [first, second])


class AskTheLoader(unittest.TestCase):
    """What the gate does when the program it asks answers in a shape it predates.

    Every other case in this file stubs `ask_the_loader` out, so the one piece of
    this gate that parses an external program's output had no coverage at all —
    and `platform.yml` installs that program unpinned.
    """

    def setUp(self) -> None:
        cp.errors.clear()
        cp.warnings.clear()
        self.tmp = tempfile.TemporaryDirectory()
        cp.ROOT = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def ask(self, report: dict, strict: bool = False) -> None:
        completed = subprocess.CompletedProcess([], 0, json.dumps(report), "")
        with mock.patch.object(cp.subprocess, "run", return_value=completed):
            cp.ask_the_loader(cp.ROOT / "plugins" / "p", strict)

    # The shape measured at 2.1.278, verbatim down to the empty `contents`.
    def test_current_shape_surfaces_a_finding(self) -> None:
        self.ask(
            {
                "success": False,
                "manifest": {"file": "plugin.json", "errors": [{"path": "name", "message": "gone"}]},
                "contents": [],
            }
        )
        self.assertEqual(cp.errors, ["loader: plugin.json: name: gone"])

    def test_a_clean_report_stays_clean(self) -> None:
        self.ask({"success": True, "manifest": {"file": "plugin.json"}, "contents": []})
        self.assertEqual((cp.errors, cp.warnings), ([], []))

    def test_warnings_alone_do_not_read_as_drift(self) -> None:
        # Non-strict, warnings only: the validator still passes, and a drift check
        # that ignored `success` would redden every healthy run of this gate.
        self.ask(
            {
                "success": True,
                "manifest": {"file": "plugin.json", "warnings": [{"path": "author", "message": "n"}]},
                "contents": [],
            }
        )
        self.assertEqual(cp.errors, [])
        self.assertEqual(len(cp.warnings), 1)

    def test_renamed_sections_are_drift_not_silence(self) -> None:
        self.ask(
            {
                "success": False,
                "plugin": {"file": "plugin.json", "errors": [{"path": "name", "message": "gone"}]},
                "components": [],
            }
        )
        self.assertEqual(len(cp.errors), 1)
        self.assertIn("'components', 'plugin', 'success'", cp.errors[0])

    def test_renamed_findings_key_is_drift_not_silence(self) -> None:
        self.ask(
            {
                "success": False,
                "manifest": {"file": "plugin.json", "problems": [{"path": "n", "message": "gone"}]},
                "contents": [],
            }
        )
        self.assertEqual(len(cp.errors), 1)
        self.assertIn("did not pass yet reported nothing", cp.errors[0])

    def test_a_dropped_verdict_field_is_itself_drift(self) -> None:
        self.ask({"manifest": {"file": "plugin.json", "errors": []}, "contents": []})
        self.assertEqual(len(cp.errors), 1)

    def test_strict_warnings_are_not_reported_twice(self) -> None:
        # Under --strict the validator fails on warnings alone; the warning is a
        # real finding, so the drift check must not also fire.
        self.ask(
            {
                "success": False,
                "manifest": {"file": "plugin.json", "warnings": [{"path": "author", "message": "n"}]},
                "contents": [],
            },
            strict=True,
        )
        self.assertEqual(cp.errors, [])
        self.assertEqual(len(cp.warnings), 1)


if __name__ == "__main__":
    unittest.main()
