#!/usr/bin/env python3
"""Tests for check_delegation_grants. Run: python3 scripts/test_check_delegation_grants.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from check_delegation_grants import check, covers, main, parse  # noqa: E402


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
    assert any("no Task grant" in e for e in errors), errors


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


def test_parse_reads_both_grant_dialects(tmp):
    agent = tmp / "a.md"
    agent.write_text('---\nname: x\ntools: ["Bash", "Read"]\n---\nbody\n')
    assert parse(agent) == ("x", {"Bash", "Read"}, "body\n")

    sk = tmp / "SKILL.md"
    sk.write_text("---\nname: y\nallowed-tools: Read, Task\n---\nbody\n")
    assert parse(sk) == ("y", {"Read", "Task"}, "body\n")


def test_parse_returns_none_without_frontmatter(tmp):
    plain = tmp / "p.md"
    plain.write_text("# no frontmatter\n")
    assert parse(plain) is None


def test_main_exits_nonzero_on_escalation(tmp):
    sd = tmp / "plugins" / "p" / "skills" / "s"
    sd.mkdir(parents=True)
    (sd / "SKILL.md").write_text("---\nname: s\nallowed-tools: Read, Task\n---\ncall `a`\n")
    ad = tmp / "plugins" / "p" / "agents"
    ad.mkdir(parents=True)
    (ad / "a.md").write_text('---\nname: a\ntools: ["Read", "Write"]\n---\nbody\n')
    assert main(tmp) == 1


def test_main_errors_when_no_roles_exist(tmp):
    assert main(tmp) == 1


if __name__ == "__main__":
    import tempfile

    failures = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_"):
            continue
        try:
            if fn.__code__.co_argcount:
                with tempfile.TemporaryDirectory() as d:
                    fn(Path(d))
            else:
                fn()
            print(f"ok   {name}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {name}: {exc}")
    print(f"\n{failures} failures")
    sys.exit(1 if failures else 0)
