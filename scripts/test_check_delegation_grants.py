#!/usr/bin/env python3
"""Tests for check_delegation_grants. Run: python3 scripts/test_check_delegation_grants.py"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from check_delegation_grants import check, covers, main, parse, prose_surface  # noqa: E402


def skill(name, grants, body=""):
    return (name, set(grants), body)


def test_dispatch_within_grants_is_clean():
    errors, _ = check(
        [skill("s", {"Task", "Read", "Bash"}, "ask `a` about it")],
        {"a": {"Read", "Bash"}},
    )
    assert errors == [], errors


def test_dispatch_escalating_beyond_grants_is_an_error():
    errors, _ = check(
        [skill("review", {"Task", "Read"}, "dispatch the `tester` agent")],
        {"tester": {"Read", "Write", "Edit"}},
    )
    assert len(errors) == 1, errors
    assert "Edit, Write" in errors[0]


def test_dispatch_without_task_grant_is_an_error():
    errors, _ = check([skill("s", {"Read"}, "dispatch `a`")], {"a": {"Read"}})
    assert any("no Agent grant" in e for e in errors), errors


def test_either_spelling_of_the_agent_tool_covers_a_dispatch():
    """The loader resolves `Task` and `Agent` to one tool; so must this gate."""
    for spelling in ("Task", "Agent"):
        errors, _ = check([skill("s", {spelling, "Read"}, "dispatch `a`")], {"a": {"Read"}})
        assert not any("grant" in e and "dispatches" in e for e in errors), (spelling, errors)


def test_an_agents_agent_tool_is_not_an_escalation_past_the_old_spelling():
    """An agent granting `Agent` under a skill granting `Task` escalates nothing."""
    errors, _ = check([skill("s", {"Task", "Read"}, "dispatch `a`")], {"a": {"Agent", "Read"}})
    assert errors == [], errors


def test_unmentioned_agent_is_not_a_dispatch():
    errors, warnings = check([skill("s", {"Read"}, "no agents here")], {"a": {"Write"}})
    assert errors == []
    assert any("no skill dispatches it" in w for w in warnings), warnings


def test_agent_named_without_backticks_is_prose_not_a_dispatch():
    errors, _ = check([skill("s", {"Read"}, "see also tester")], {"tester": {"Write"}})
    assert errors == []


def test_bare_bash_covers_scoped_bash():
    assert covers({"Bash"}, "Bash(git:*)")
    assert not covers({"Bash(ls:*)"}, "Bash")


def test_scoped_bash_on_agent_needs_bash_on_skill():
    errors, _ = check(
        [skill("s", {"Task", "Bash(ls:*)"}, "use `a`")],
        {"a": {"Bash(git:*)"}},
    )
    assert any("Bash(git:*)" in e for e in errors), errors


def test_declined_dispatch_is_not_an_escalation():
    body = "- recommend `tester` on the spec. You do not dispatch it yourself — it writes files."
    errors, warnings = check([skill("review", {"Read"}, body)], {"tester": {"Read", "Write"}})
    assert errors == [], errors
    assert not any("no skill dispatches it" in w for w in warnings), warnings


def test_disclaimer_in_another_block_does_not_excuse_a_dispatch():
    body = "- dispatch the `tester` agent now.\n\n- elsewhere: you never dispatch it.\n"
    errors, _ = check([skill("review", {"Task", "Read"}, body)], {"tester": {"Write"}})
    assert any("Write" in e for e in errors), errors


def test_a_negated_verb_about_something_else_is_not_a_disclaimer():
    """`anantys.qa` carries two "never run on <env>" blocks whose only relation to
    delegation is the verb. Reading one as a disclaimer would switch the grant union
    off for a real dispatch sharing the block."""
    body = "- **Never run on production:** it charges a real card. Then ask `tester`."
    errors, _ = check([skill("qa", {"Task", "Read"}, body)], {"tester": {"Write"}})
    assert any("Write" in e for e in errors), errors


def test_a_disclaimer_names_the_agent_it_declines():
    """Two agents, one block, one declined — the other is still dispatched."""
    body = "- recommend `safe`; you do not dispatch `safe` yourself. Then run `wide`."
    errors, _ = check(
        [skill("s", {"Task", "Read"}, body)],
        {"safe": {"Write"}, "wide": {"Edit"}},
    )
    assert [e for e in errors if "Edit" in e], errors
    assert not [e for e in errors if "Write" in e], errors


def test_declining_also_drops_the_task_grant_requirement():
    errors, _ = check(
        [skill("s", {"Read"}, "never invoke `a` — recommend it to the human")],
        {"a": {"Read"}},
    )
    assert errors == [], errors


def test_parse_reads_both_grant_dialects(tmp_path):
    agent = tmp_path / "a.md"
    agent.write_text('---\nname: x\ntools: ["Bash", "Read"]\n---\nbody\n')
    assert parse(agent) == ("x", {"Bash", "Read"}, "body\n")

    sk = tmp_path / "SKILL.md"
    sk.write_text("---\nname: y\nallowed-tools: Read, Task\n---\nbody\n")
    assert parse(sk) == ("y", {"Read", "Task"}, "body\n")


def test_parse_reads_a_block_sequence_grant_list(tmp_path):
    """The dialect the loader accepts that nothing in this tree writes yet."""
    agent = tmp_path / "a.md"
    agent.write_text("---\nname: x\ntools:\n  - Bash\n  - Write\nmodel: opus\n---\nbody\n")
    assert parse(agent) == ("x", {"Bash", "Write"}, "body\n")


def test_parse_reads_an_unindented_block_sequence(tmp_path):
    """A block sequence may sit at its key's own column. Same list to the loader."""
    agent = tmp_path / "a.md"
    agent.write_text("---\nname: x\ntools:\n- Bash\n- Write\nmodel: opus\n---\nbody\n")
    assert parse(agent) == ("x", {"Bash", "Write"}, "body\n")


def test_an_unindented_agent_list_is_still_an_escalation(tmp_path):
    """The parse feeds `check`, so reading that list as empty certifies the dispatch."""
    agent = tmp_path / "a.md"
    agent.write_text("---\nname: auditor\ntools:\n- Bash\n- Glob\n---\nbody\n")
    name, grants, _ = parse(agent)
    errors, _ = check([skill("s", {"Task", "Read"}, "dispatch `auditor`")], {name: grants})
    assert len(errors) == 1, errors
    assert "Bash, Glob" in errors[0], errors


def test_an_absent_grant_key_is_not_an_empty_one(tmp_path):
    """No `tools:` key means every tool, so it cannot parse as no tools."""
    agent = tmp_path / "a.md"
    agent.write_text("---\nname: x\nmodel: opus\n---\nbody\n")
    assert parse(agent) == ("x", None, "body\n")

    empty = tmp_path / "b.md"
    empty.write_text("---\nname: y\ntools: []\n---\nbody\n")
    assert parse(empty) == ("y", set(), "body\n")


def test_a_valueless_grant_key_is_read_as_absent(tmp_path):
    """`tools:` with nothing after it is YAML null — every tool, not no tools."""
    agent = tmp_path / "a.md"
    agent.write_text("---\nname: x\ntools:\nmodel: opus\n---\nbody\n")
    assert parse(agent) == ("x", None, "body\n")


def test_a_whole_server_mcp_grant_covers_its_tools():
    """`check_mcp_grants` reads both spellings as the server's whole tool list."""
    assert covers({"mcp__chrome__*"}, "mcp__chrome__get-console-logs")
    assert covers({"mcp__chrome"}, "mcp__chrome__get-console-logs")
    assert not covers({"mcp__chrome__*"}, "mcp__other__read")
    assert not covers({"mcp__chrome__read"}, "mcp__chrome__write")


def test_an_agents_mcp_tool_under_a_wildcard_skill_is_not_an_escalation():
    errors, _ = check(
        [skill("design", {"Task", "mcp__chrome__*"}, "dispatch `shot`")],
        {"shot": {"mcp__chrome__take-screenshot"}},
    )
    assert errors == [], errors


def test_dispatching_an_agent_that_declares_no_tools_is_an_escalation():
    """The widest grant the format has must not read as the narrowest."""
    errors, _ = check([skill("s", {"Task", "Read"}, "ask `a` about it")], {"a": None})
    assert len(errors) == 1, errors
    assert "every tool" in errors[0]


def test_an_unbounded_skill_absorbs_an_unbounded_agent():
    """Neither declares a ceiling, so the dispatch widens nothing."""
    errors, _ = check([("s", None, "ask `a` about it")], {"a": None})
    assert errors == [], errors


def test_an_unbounded_skill_holds_the_task_grant():
    errors, _ = check([("s", None, "ask `a` about it")], {"a": {"Read"}})
    assert errors == [], errors


def test_parse_returns_none_without_frontmatter(tmp_path):
    plain = tmp_path / "p.md"
    plain.write_text("# no frontmatter\n")
    assert parse(plain) is None


def test_main_exits_nonzero_on_escalation(tmp_path):
    sd = tmp_path / "plugins" / "p" / "skills" / "s"
    sd.mkdir(parents=True)
    (sd / "SKILL.md").write_text("---\nname: s\nallowed-tools: Read, Task\n---\ncall `a`\n")
    ad = tmp_path / "plugins" / "p" / "agents"
    ad.mkdir(parents=True)
    (ad / "a.md").write_text('---\nname: a\ntools: ["Read", "Write"]\n---\nbody\n')
    assert main(tmp_path) == 1


def test_main_errors_when_no_roles_exist(tmp_path):
    assert main(tmp_path) == 1


def _escalating_plugin(root):
    """A skill that dispatches a wider agent, under whatever `root` is handed."""
    sd = root / "skills" / "s"
    sd.mkdir(parents=True)
    (sd / "SKILL.md").write_text("---\nname: s\nallowed-tools: Read, Task\n---\ncall `a`\n")
    ad = root / "agents"
    ad.mkdir(parents=True)
    (ad / "a.md").write_text('---\nname: a\ntools: ["Read", "Write"]\n---\nbody\n')


def _report(root):
    """(exit code, report) — the exit code alone cannot witness this one.

    An empty subject set also exits 1, via `no roles found under <root>`. So a
    test that reads only the code goes green on the defect it was written for:
    the gate did not audit the plugin, it failed to find it. The finding has to
    be the sentence.
    """
    import contextlib
    import io

    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main(root)
    return code, out.getvalue()


def test_a_plugin_outside_plugins_is_still_audited(tmp_path):
    """`marketplace.json`'s `source` is a free-form path; `plugins/*/` is not the rule.

    `check_plugins` walks `**/.claude-plugin/plugin.json`, so a plugin at
    `vendor/extra` is listed, installable and validated there. Globbing
    `plugins/*/skills/...` here meant its dispatch escalations were never read —
    a role the sweep skips is certified in silence.
    """
    _escalating_plugin(tmp_path / "vendor" / "extra")
    code, report = _report(tmp_path)
    assert code == 1, report
    assert "1 skills, 1 agents" in report, report
    assert "Write" in report, report


def test_the_same_plugin_under_plugins_is_the_control(tmp_path):
    """Positive control: the error above is the escalation, not the path."""
    _escalating_plugin(tmp_path / "plugins" / "p")
    code, report = _report(tmp_path)
    assert code == 1, report
    assert "1 skills, 1 agents" in report, report


def _split_skill(tmp_path, procedure, agent_tools='["Bash", "Write"]'):
    """A skill whose procedure lives in a named reference file, plus one agent."""
    sd = tmp_path / "plugins" / "p" / "skills" / "s"
    (sd / "reference").mkdir(parents=True)
    (sd / "SKILL.md").write_text(
        "---\nname: s\nallowed-tools: Read, Task\n---\nProcedure: `reference/run.md`.\n"
    )
    (sd / "reference" / "run.md").write_text(procedure)
    ad = tmp_path / "plugins" / "p" / "agents"
    ad.mkdir(parents=True)
    (ad / "wide.md").write_text(f'---\nname: wide\ntools: {agent_tools}\n---\nbody\n')
    return sd


def test_dispatch_in_a_reference_file_is_still_a_dispatch(tmp_path):
    """The sanctioned SKILL.md split must not move a dispatch out of the gate's view.

    Before prose_surface, this skill passed silently *and* the agent was reported
    as dispatched by nobody — the checker stating the opposite of the truth twice.
    """
    _split_skill(tmp_path, "Dispatch `wide` to apply the fix.\n")
    assert main(tmp_path) == 1


def test_a_disclaimer_in_a_reference_file_still_declines(tmp_path):
    _split_skill(tmp_path, "Recommend `wide`; you never dispatch it yourself.\n")
    assert main(tmp_path) == 0


def test_a_disclaimer_does_not_leak_across_the_file_join(tmp_path):
    """SKILL.md's trailing block must not absorb the reference file's opening one."""
    sd = _split_skill(tmp_path, "Dispatch `wide` now.\n")
    (sd / "SKILL.md").write_text(
        "---\nname: s\nallowed-tools: Read, Task\n---\n"
        "Procedure: `reference/run.md`. You never dispatch `wide` from here."
    )
    assert main(tmp_path) == 1


def test_unnamed_reference_file_is_reported_not_read(tmp_path):
    sd = _split_skill(tmp_path, "Dispatch `wide` now.\n")
    (sd / "SKILL.md").write_text("---\nname: s\nallowed-tools: Read, Task\n---\nno links here\n")
    assert main(tmp_path) == 0  # the dispatch is unreachable prose, not an escalation
    body, warnings = prose_surface(sd / "SKILL.md", "no links here\n")
    assert "wide" not in body
    assert any("reference/run.md" in w for w in warnings), warnings


def test_skill_without_a_reference_dir_is_untouched(tmp_path):
    sk = tmp_path / "SKILL.md"
    sk.write_text("x")
    assert prose_surface(sk, "body") == ("body", [])


def load_tests(loader, tests, pattern):
    """Make these pytest-style functions visible to `unittest discover`.

    The repo's CI step is `python3 -m unittest discover -s scripts`, which
    collects TestCase subclasses only. A module of bare functions collects
    *zero* tests and reports OK — a green wall in front of an empty room. This
    adapter registers each one and supplies the temp directory pytest would
    have injected as `tmp_path`, so one suite runs under both runners.
    """
    suite = unittest.TestSuite()
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue

        def run(case, fn=fn):
            if fn.__code__.co_argcount:
                with tempfile.TemporaryDirectory() as d:
                    fn(Path(d))
            else:
                fn()

        suite.addTest(type(name, (unittest.TestCase,), {name: run})(name))
    return suite


if __name__ == "__main__":
    unittest.main(verbosity=2)
