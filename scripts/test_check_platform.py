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

    def test_plugin_scoped_mcp_server_is_well_formed(self) -> None:
        # A server declared in plugin.json is exposed as
        # `mcp__plugin_<plugin>_<server>__<tool>`. Measured on CLI 2.1.278: the
        # session lists that name and the grant resolves against it. A server
        # class that excludes `_` rejects every such grant.
        scoped = "mcp__plugin_anantys-team-agents_claude-in-chrome__navigate"
        self.assertEqual(
            self.check(GOOD_SKILL.replace("mcp__claude-in-chrome__navigate", scoped)), []
        )

    def test_the_mcp_class_is_the_loader_rule_from_the_binary(self) -> None:
        # `^mcp__[\w-]+(?:__(?:[\w.-]+|\*))?$`, read off the 2.1.278 binary. Each
        # case below is a grant the session resolves; a narrower class here calls
        # every one of them a dropped grant, which is this gate's own failure mode.
        for grant in (
            "mcp__claude-in-chrome__*",
            "mcp__plugin_anantys-team-agents_claude-in-chrome__*",
            "mcp__chrome__get-console-logs",
            "mcp__chrome__read.file",
            "mcp__Chrome__navigateTo",
        ):
            with self.subTest(grant=grant):
                cp.errors.clear()
                self.assertEqual(
                    self.check(GOOD_SKILL.replace("mcp__claude-in-chrome__navigate", grant)), []
                )

    def test_the_wildcard_a_long_grant_line_collapses_to_stays_clean(self) -> None:
        # The live shape: `anantys.debug` enumerates seven tools from one server on
        # one line. Collapsing them to the loader's wildcard is the obvious edit,
        # and it must not come back as a malformed identifier.
        seven = ", ".join(
            f"mcp__claude-in-chrome__{t}"
            for t in ("tabs_context_mcp", "navigate", "computer", "read_page")
        )
        self.assertEqual(self.check(GOOD_SKILL.replace("mcp__claude-in-chrome__navigate", seven)), [])
        cp.errors.clear()
        self.assertEqual(
            self.check(GOOD_SKILL.replace("mcp__claude-in-chrome__navigate", "mcp__chrome__*")), []
        )

    def test_one_segment_after_mcp_is_ambiguous_and_charged(self) -> None:
        # Loader-legal both ways, which is why shape alone cannot settle it: a
        # whole-server grant and a `__` typo are the same string. Erroring on it
        # as "not well-formed" was false in both readings — the loader resolves it.
        for grant in ("mcp__claude-in-chrome", "mcp__claude-in-chrome_navigate"):
            with self.subTest(grant=grant):
                cp.errors.clear()
                found = self.check(GOOD_SKILL.replace("mcp__claude-in-chrome__navigate", grant))
                self.assertEqual(len(found), 1)
                self.assertIn("names one segment after `mcp__`", found[0])
                self.assertIn(f"`{grant}__*`", found[0])
                self.assertNotIn("not a well-formed", found[0])

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

    def test_disallowed_tools_is_the_live_shape_and_is_read(self) -> None:
        # `koan/the-field-that-withholds` adds exactly this line to three skills.
        # It is the only field on a skill that *removes* a tool, so reporting it as
        # "ignored at load time" asks an author to delete a narrowing and calls
        # that the remedy — this gate's own sentence, pointed the wrong way.
        withheld = "disallowed-tools: Bash(git commit:*), Bash(git push:*)"
        self.assertEqual(
            self.check(GOOD_SKILL.replace("---\n\nbody", f"{withheld}\n---\n\nbody")), []
        )

    def test_every_key_in_the_loader_schema_is_recognized(self) -> None:
        # Read off the 2.1.278 frontmatter schema, in its declaration order. A
        # vocabulary narrower than the loader's turns each of these into an error
        # whose text is false: the loader reads the key.
        for key, value in (
            ("disallowedTools", "Bash(git push:*)"),
            ("argument-hint", "<path>"),
            ("user-invocable", "false"),
            ("effort", "high"),
            ("when_to_use", "When the app misbehaves."),
            ("paths", '["src/**"]'),
            ("context", "fork"),
            ("agent", "anantys.debug"),
            ("background", "false"),
            ("metadata", "{tier: internal}"),
        ):
            with self.subTest(key=key):
                cp.errors.clear()
                line = f"{key}: {value}"
                self.assertEqual(
                    self.check(GOOD_SKILL.replace("---\n\nbody", f"{line}\n---\n\nbody")), []
                )

    def test_a_misspelled_key_is_still_charged(self) -> None:
        # The widening must not reach the case the check exists for: a key one
        # character off a real one loads as nothing, and the loader says nothing.
        for key in ("disallowed_tools", "when-to-use", "allowedTools"):
            with self.subTest(key=key):
                cp.errors.clear()
                found = self.check(GOOD_SKILL.replace("---\n\nbody", f"{key}: Read\n---\n\nbody"))
                self.assertTrue(
                    any(f"unrecognized frontmatter key `{key}`" in e for e in found), found
                )

    def test_the_two_schemas_stay_two(self) -> None:
        # Different objects in the binary, and the overlap is partial: an agent
        # takes `tools`/`disallowedTools`/`permissionMode`, a skill takes
        # `allowed-tools`/`disallowed-tools`/`shell`. One merged set would certify
        # each file against the other's vocabulary.
        self.assertNotIn("allowed-tools", cp.AGENT_KEYS)
        self.assertNotIn("disallowed-tools", cp.AGENT_KEYS)
        self.assertNotIn("permissionMode", cp.SKILL_KEYS)
        self.assertNotIn("shell", cp.AGENT_KEYS)
        for key in ("effort", "disallowedTools", "mcpServers", "maxTurns", "isolation"):
            with self.subTest(key=key):
                self.assertIn(key, cp.AGENT_KEYS)

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

    def plugin(self, name: str, under: str = "plugins") -> Path:
        manifest = cp.ROOT / under / name / ".claude-plugin" / "plugin.json"
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

    def test_a_plugin_outside_plugins_is_asked_about_too(self) -> None:
        """`plugins/*/` is not where a plugin lives — `marketplace.json`'s `source` is.

        `check_plugins` reads the catalog and so already walks `**`. On a tree with
        a plugin at `vendor/extra` it reported three errors about that plugin's
        roles while this gate reported none: the loader was never asked and the
        frontmatter vocabulary was never read. Two gates in one CI run,
        disagreeing about which files the repo contains.
        """
        vendored = self.plugin("extra", under="vendor")
        self.skill(vendored, "s", GOOD_SKILL.replace("allowed-tools:", "allowed_tools:"))
        self.assertEqual(cp.main([]), 1)
        self.assertEqual(self.asked, [vendored])

    def test_the_same_plugin_under_plugins_is_the_control(self) -> None:
        """Positive control: the error is the frontmatter key, not the path."""
        listed = self.plugin("extra")
        self.skill(listed, "s", GOOD_SKILL.replace("allowed-tools:", "allowed_tools:"))
        self.assertEqual(cp.main([]), 1)
        self.assertEqual(self.asked, [listed])


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


class Argv(unittest.TestCase):
    """`--strict` was read by membership, so every other argument was dropped."""

    def setUp(self) -> None:
        cp.errors.clear()
        cp.warnings.clear()
        self.tmp = tempfile.TemporaryDirectory()
        cp.ROOT = Path(self.tmp.name).resolve()
        self.addCleanup(self.tmp.cleanup)

    def test_a_mistyped_strict_flag_is_refused(self) -> None:
        """Dropped, it ran unstrict and exited 0 on the warnings it was asked to gate."""
        with self.assertRaises(SystemExit) as caught:
            cp.main(["--stict"])
        self.assertIn("--stict", str(caught.exception))

    def test_a_foreign_tree_is_refused(self) -> None:
        other = Path(tempfile.mkdtemp())
        self.addCleanup(subprocess.run, ("rm", "-rf", str(other)))
        with self.assertRaises(SystemExit) as caught:
            cp.main([str(other)])
        self.assertIn(str(other), str(caught.exception))

    def test_strict_and_this_tree_get_past_the_guard(self) -> None:
        """`gate_matrix.py` overlays these scripts and runs them in the tree they land in."""
        with mock.patch("shutil.which", return_value="/usr/bin/claude"):
            self.assertEqual(cp.main(["--strict", str(cp.ROOT)]), 1)  # no plugins to find
        self.assertEqual(cp.errors, [])


class StrictIsSatisfiable(unittest.TestCase):
    """The CI step passes `--strict`, so the shipped manifests owe it two fields.

    Measured on 2.1.278: an absent `author` is a warning, but a bare string is an
    error (`author: Invalid input`) and so is an object without `name`
    (`author.name: Invalid input`). The obvious wrong fix reddens the same step
    the right one greens, which is why the shape is asserted and not just the key.
    """

    REPO = Path(__file__).resolve().parent.parent

    def load(self, *parts: str) -> dict:
        return json.loads((self.REPO.joinpath(*parts)).read_text(encoding="utf-8"))

    def test_plugin_manifest_carries_an_object_author_with_a_name(self) -> None:
        author = self.load("plugins", "anantys-team-agents", ".claude-plugin", "plugin.json").get("author")
        self.assertIsInstance(author, dict)
        self.assertTrue(author.get("name"))

    def test_marketplace_carries_a_description(self) -> None:
        self.assertTrue(self.load(".claude-plugin", "marketplace.json").get("description"))


if __name__ == "__main__":
    unittest.main()
