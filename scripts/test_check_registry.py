#!/usr/bin/env python3
"""Where this gate decides differently from the obvious reading of its rule.

Every case below feeds a synthetic `system`/`init` event, because the point of
the gate is the *disagreement* between the repo and a registry — and a real CLI
run can only ever produce the one registry this tree already agrees with. The
readout's shape is the thing taken from the real binary (CLI 2.1.278): a single
JSON object on stdout's first line, `subtype: "init"`, with `skills`, `agents`
and `slash_commands` holding fully-prefixed `plugin:id` strings.
"""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import check_registry as cr

PLUGIN = "anantys-team-agents"


def event(*, skills=(), agents=(), commands=None) -> dict:
    """An init readout listing `skills`/`agents` by bare id, prefix added here."""
    bare = list(skills)
    return {
        "type": "system",
        "subtype": "init",
        "skills": [f"{PLUGIN}:{n}" for n in bare],
        "agents": [f"{PLUGIN}:{n}" for n in agents],
        "slash_commands": [f"{PLUGIN}:{n}" for n in (bare if commands is None else commands)],
    }


class Harness(unittest.TestCase):
    def setUp(self) -> None:
        cr.errors.clear()
        cr.warnings.clear()
        self.tmp = tempfile.TemporaryDirectory()
        cr.ROOT = Path(self.tmp.name).resolve()
        self.addCleanup(self.tmp.cleanup)
        self.plugin_dir = cr.ROOT / "plugins" / PLUGIN
        (self.plugin_dir / "skills").mkdir(parents=True)
        (self.plugin_dir / "agents").mkdir(parents=True)

    def skill(self, directory: str) -> None:
        d = self.plugin_dir / "skills" / directory
        d.mkdir()
        (d / "SKILL.md").write_text(f"---\nname: {directory}\n---\n", encoding="utf-8")

    def agent(self, stem: str, declared: str | None = None) -> None:
        name = f"name: {stem if declared is None else declared}\n" if declared != "" else ""
        (self.plugin_dir / "agents" / f"{stem}.md").write_text(
            f"---\n{name}description: d\n---\n", encoding="utf-8"
        )

    def findings(self, readout: dict) -> list[str]:
        cr.check_components(readout, self.plugin_dir, PLUGIN)
        return cr.errors


class ComponentsAreCheckedAgainstTheRegistryNotEachOther(Harness):
    def test_a_registered_tree_is_silent(self) -> None:
        self.skill("anantys.qa")
        self.agent("anantys.code-auditor")
        found = self.findings(event(skills=["anantys-qa"], agents=["anantys.code-auditor"]))
        self.assertEqual(found, [])

    def test_a_skill_the_loader_declined_is_an_error(self) -> None:
        self.skill("anantys.qa")
        error, = self.findings(event(skills=[]))
        self.assertIn("not registered as `anantys-qa`", error)
        self.assertIn("ships and does not exist", error)

    def test_the_directory_spelling_coming_back_is_read_as_sanitizer_drift(self) -> None:
        # The only case where the gate reports on `check_plugins` rather than on the
        # tree: a CLI that stopped folding `.` to `-` would leave every name derived
        # from `exposed_skill_name` wrong while each file on disk is untouched.
        self.skill("anantys.qa")
        error, = self.findings(event(skills=["anantys.qa"]))
        self.assertIn("the loader registered `anantys.qa`", error)
        self.assertIn("`exposed_skill_name` says `anantys-qa`", error)
        self.assertIn("check_plugins.py", error)

    def test_an_agent_is_looked_up_under_its_frontmatter_name_not_its_filename(self) -> None:
        # The mirror image of a skill, and the asymmetry this gate exists to hold:
        # renaming the *file* moves nothing, so a registry holding the stem is a miss.
        self.agent("whatever", declared="anantys.code-auditor")
        self.assertEqual(self.findings(event(agents=["anantys.code-auditor"])), [])
        cr.errors.clear()
        error, = self.findings(event(agents=["whatever"]))
        self.assertIn("not registered as `anantys.code-auditor`", error)

    def test_an_agent_name_containing_a_space_is_reported_whole(self) -> None:
        # The loader registers nothing for it, so the finding has to name what was
        # declared — truncating at the space would blame a name nobody wrote.
        self.agent("a", declared="anantys probe auditor")
        error, = self.findings(event(agents=[]))
        self.assertIn("`anantys probe auditor`", error)

    def test_a_dot_in_an_agent_name_survives_and_is_not_an_error(self) -> None:
        self.agent("anantys.spec-tester")
        self.assertEqual(self.findings(event(agents=["anantys.spec-tester"])), [])

    def test_a_skill_needs_a_slash_command_not_only_a_skill_entry(self) -> None:
        # Both lists come back on a healthy load; the component check reads `skills`,
        # and `check_advertised` is the one that reads `slash_commands`. Keeping them
        # separate is what lets a description be judged on what a user can type.
        self.skill("anantys.qa")
        self.assertEqual(self.findings(event(skills=["anantys-qa"], commands=[])), [])


class AdvertisedNamesAreJudgedByWhatTheRouterMatches(Harness):
    def advertised(self, description: str, commands=("anantys-qa",)) -> list[str]:
        cr.check_advertised(
            event(skills=list(commands)), cr.ROOT / "m.json", description, PLUGIN
        )
        return cr.errors + cr.warnings

    def test_the_bare_id_and_the_prefixed_id_both_resolve(self) -> None:
        self.assertEqual(self.advertised("type /anantys-qa or /anantys-team-agents:anantys-qa"), [])

    def test_the_dotted_spelling_fails_and_the_remedy_is_named(self) -> None:
        error, = self.advertised("5 skills (/anantys.qa)")
        self.assertIn("advertises `anantys.qa`", error)
        self.assertIn("did you mean `anantys-qa`?", error)

    def test_a_prefix_elided_continuation_is_completed_before_being_judged(self) -> None:
        # The descriptions write the first entry in full and elide the prefix after
        # it: `(/anantys-team-agents:anantys.design, :anantys.ops, …)`. Reading the
        # fragments as prose is how five dead names shipped as one checked one.
        error, = self.advertised("(/anantys-team-agents:anantys-qa, :anantys.ops)")
        self.assertIn("advertises `anantys.ops`", error)

    def test_a_name_nothing_resembles_fails_without_a_suggestion(self) -> None:
        error, = self.advertised("/anantys-gone")
        self.assertNotIn("did you mean", error)

    def test_the_plugins_own_name_is_a_prefix_not_a_command(self) -> None:
        self.assertEqual(self.advertised(f"install /{PLUGIN}:anantys-qa"), [])

    def test_an_ordinary_slashed_word_is_prose(self) -> None:
        # `and/or` is the shape that would make this gate unusable in a description
        # written by somebody who has never heard of it.
        self.assertEqual(self.advertised("vendor-neutral and/or project-agnostic"), [])

    def test_a_link_path_is_not_a_command(self) -> None:
        self.assertEqual(self.advertised("see https://example.com/docs/anantys.qa-guide"), [])

    def test_an_empty_registry_for_the_plugin_is_a_warning_not_a_pass(self) -> None:
        warning, = self.advertised("/anantys.qa", commands=())
        self.assertIn("went unmeasured", warning)


class AGateThatCannotMeasureDoesNotRule(Harness):
    def manifest(self, description: str) -> None:
        (cr.ROOT / ".claude-plugin").mkdir()
        (cr.ROOT / ".claude-plugin" / "marketplace.json").write_text(json.dumps(
            {"name": "m", "plugins": [
                {"name": PLUGIN, "description": description,
                 "source": f"./plugins/{PLUGIN}"}]}
        ), encoding="utf-8")
        (self.plugin_dir / ".claude-plugin").mkdir()
        (self.plugin_dir / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": PLUGIN, "description": description}), encoding="utf-8"
        )

    def test_no_cli_warns_and_exits_clean(self) -> None:
        self.manifest("/anantys.qa")  # would be an error if anything had been read
        with patch("check_registry.subprocess.run", side_effect=OSError):
            self.assertEqual(cr.main(), 0)
        warning, = cr.warnings
        self.assertIn("no `system`/`init` readout", warning)
        self.assertEqual(cr.errors, [])

    def test_a_first_line_that_is_not_the_init_event_is_not_trusted(self) -> None:
        # An authentication failure, a version banner, a newer CLI that leads with
        # something else: all of them read as "nothing was measured", never as a
        # registry with no components — which would error on every role at once.
        for first in ('{"type":"system","subtype":"compact_boundary"}', "not json", ""):
            with self.subTest(first=first):
                done = subprocess.CompletedProcess([], 0, first + "\n", "")
                with patch("check_registry.subprocess.run", return_value=done):
                    self.assertIsNone(cr.registry(self.plugin_dir))

    def test_the_probe_cannot_become_a_billable_call(self) -> None:
        # The readout is emitted before the first model call, so the run is free and
        # ends on a credential error. Forcing the key to an invalid value rather than
        # leaving it unset is what keeps that true on a runner that holds a real one.
        done = subprocess.CompletedProcess([], 0, "", "")
        with patch("check_registry.subprocess.run", return_value=done) as run:
            cr.registry(self.plugin_dir)
        self.assertEqual(run.call_args.kwargs["env"]["ANTHROPIC_API_KEY"], "sk-ant-invalid-probe")
        self.assertEqual(run.call_args.kwargs["stdin"], subprocess.DEVNULL)

    def test_a_tree_the_gate_does_not_live_in_is_refused_rather_than_ignored(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            cr.main(["/elsewhere"])
        self.assertIn("the tree its own file is in", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
