#!/usr/bin/env python3
"""Tests for check_plugin_agents. Run: python3 scripts/test_check_plugin_agents.py"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from check_plugin_agents import (  # noqa: E402
    agent_type,
    check_dispatch_spelling,
    check_frontmatter,
    frontmatter_keys,
    main,
    plugin_name,
)


def agent(label="agents/a.md", **keys):
    return (label, keys)


def skill(name, body):
    return (name, {"Task"}, body)


# --- the registered name -----------------------------------------------------

def test_agent_type_is_plugin_then_name():
    root = Path("/p/plugins/team/agents")
    assert agent_type(root / "a.md", root, "team", "anantys.x") == "team:anantys.x"


def test_namespace_directories_sit_between_plugin_and_name():
    root = Path("/p/plugins/team/agents")
    got = agent_type(root / "review" / "a.md", root, "team", "x")
    assert got == "team:review:x", got


def test_dots_in_the_name_survive_so_only_the_prefix_differs():
    root = Path("/p/plugins/anantys-team-agents/agents")
    got = agent_type(root / "a.md", root, "anantys-team-agents", "anantys.code-auditor")
    assert got == "anantys-team-agents:anantys.code-auditor", got


# --- dispatch spelling -------------------------------------------------------

def test_bare_name_dispatch_is_an_error():
    errors = check_dispatch_spelling(
        [skill("review", "dispatch the `anantys.code-auditor` agent")],
        {"team:anantys.code-auditor": agent()},
    )
    assert len(errors) == 1, errors
    assert "team:anantys.code-auditor" in errors[0]


def test_registered_name_in_the_same_block_is_clean():
    errors = check_dispatch_spelling(
        [skill("review", "dispatch `team:anantys.code-auditor`")],
        {"team:anantys.code-auditor": agent()},
    )
    assert errors == [], errors


def test_both_spellings_in_one_block_is_clean():
    body = (
        "dispatch the code auditor: `team:x` when installed as a plugin, and `x`\n"
        "when the file sits loose in `.claude/agents/`"
    )
    assert check_dispatch_spelling([skill("review", body)], {"team:x": agent()}) == []


def test_the_registered_name_must_be_in_the_dispatching_block_not_merely_the_file():
    """A spelling note three sections away does not reach the reader of the call."""
    body = "the agent type is `team:x`\n\nlater: you choose whether to dispatch `x`"
    errors = check_dispatch_spelling([skill("review", body)], {"team:x": agent()})
    assert len(errors) == 1, errors


def test_name_without_backticks_is_prose_not_a_dispatch():
    body = "the spec-tester agent, team:x, is described here"
    assert check_dispatch_spelling([skill("s", body)], {"team:x": agent()}) == []


def test_an_undispatched_agent_produces_nothing():
    assert check_dispatch_spelling([skill("s", "no agents")], {"team:x": agent()}) == []


# --- the keys the loader drops ----------------------------------------------

def test_permission_mode_hooks_and_mcp_servers_are_errors():
    errors = check_frontmatter(
        {"team:x": agent(permissionMode="acceptEdits", hooks="", mcpServers="")}
    )
    assert len(errors) == 3, errors
    assert all("does not get it" in e for e in errors), errors


def test_a_plain_agent_file_is_clean():
    errors = check_frontmatter(
        {"team:x": agent(name="x", description="d", tools='["Read"]', model="opus")}
    )
    assert errors == [], errors


def test_memory_must_name_a_layer_the_loader_accepts():
    assert check_frontmatter({"team:x": agent(memory="session")}) != []
    assert check_frontmatter({"team:x": agent(memory="project")}) == []


def test_isolation_accepts_only_worktree():
    assert check_frontmatter({"team:x": agent(isolation="remote")}) != []
    assert check_frontmatter({"team:x": agent(isolation="worktree")}) == []


def test_max_turns_must_be_a_positive_integer():
    assert check_frontmatter({"team:x": agent(maxTurns="0")}) != []
    assert check_frontmatter({"team:x": agent(maxTurns="many")}) != []
    assert check_frontmatter({"team:x": agent(maxTurns="12")}) == []


# --- reading the files -------------------------------------------------------

def test_frontmatter_keys_returns_none_without_frontmatter():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "a.md"
        p.write_text("no frontmatter here\n", encoding="utf-8")
        assert frontmatter_keys(p) is None


def test_a_nested_mapping_key_still_registers():
    """`hooks:` with a block under it is dropped too — the key line is the claim."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "a.md"
        p.write_text("---\nname: x\nhooks:\n  PreToolUse: []\n---\nbody\n", encoding="utf-8")
        assert "hooks" in frontmatter_keys(p)


def test_plugin_name_comes_from_the_manifest_not_the_directory():
    with tempfile.TemporaryDirectory() as d:
        plugin = Path(d) / "some-dir"
        (plugin / ".claude-plugin").mkdir(parents=True)
        (plugin / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": "real-name"}), encoding="utf-8"
        )
        assert plugin_name(plugin) == "real-name"


def test_plugin_name_falls_back_to_the_directory_without_a_manifest():
    with tempfile.TemporaryDirectory() as d:
        plugin = Path(d) / "some-dir"
        plugin.mkdir()
        assert plugin_name(plugin) == "some-dir"


# --- the sweep ---------------------------------------------------------------

def test_main_fails_when_there_are_no_plugin_agents():
    with tempfile.TemporaryDirectory() as d:
        assert main(Path(d)) == 1


def test_main_passes_on_a_correctly_spelled_tree():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "plugins/p/.claude-plugin").mkdir(parents=True)
        (root / "plugins/p/.claude-plugin/plugin.json").write_text(
            json.dumps({"name": "p"}), encoding="utf-8"
        )
        (root / "plugins/p/agents").mkdir()
        (root / "plugins/p/agents/a.md").write_text(
            '---\nname: a\ntools: ["Read"]\n---\nbody\n', encoding="utf-8"
        )
        (root / "plugins/p/skills/s").mkdir(parents=True)
        (root / "plugins/p/skills/s/SKILL.md").write_text(
            "---\nname: s\nallowed-tools: Task\n---\ndispatch `p:a`\n", encoding="utf-8"
        )
        assert main(root) == 0


def test_main_fails_on_the_bare_spelling_in_a_real_tree():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "plugins/p/.claude-plugin").mkdir(parents=True)
        (root / "plugins/p/.claude-plugin/plugin.json").write_text(
            json.dumps({"name": "p"}), encoding="utf-8"
        )
        (root / "plugins/p/agents").mkdir()
        (root / "plugins/p/agents/a.md").write_text(
            '---\nname: a\ntools: ["Read"]\n---\nbody\n', encoding="utf-8"
        )
        (root / "plugins/p/skills/s").mkdir(parents=True)
        (root / "plugins/p/skills/s/SKILL.md").write_text(
            "---\nname: s\nallowed-tools: Task\n---\ndispatch `a`\n", encoding="utf-8"
        )
        assert main(root) == 1


def test_a_loose_agent_outside_plugins_is_not_this_gate_s_business():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / ".claude/agents").mkdir(parents=True)
        (root / ".claude/agents/a.md").write_text(
            "---\nname: a\npermissionMode: acceptEdits\n---\nbody\n", encoding="utf-8"
        )
        assert main(root) == 1  # no plugin agents at all, so nothing to rule on


def load_tests(loader, tests, pattern):
    """Wrap the module's plain `test_*` functions so `unittest discover` runs them.

    Same shape as the sibling suites: the gates are written as free functions so
    they read as assertions about the checker rather than as methods, and this is
    what makes `gates.yml`'s single discover step pick them up.
    """
    suite = unittest.TestSuite()
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue

        def run(case, fn=fn):
            fn()

        suite.addTest(type(name, (unittest.TestCase,), {name: run})(name))
    return suite


if __name__ == "__main__":
    unittest.main(verbosity=2)
