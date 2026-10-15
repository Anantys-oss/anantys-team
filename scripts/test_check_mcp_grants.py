#!/usr/bin/env python3
"""Fixture tests for check_mcp_grants — run: python3 -m unittest discover scripts"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import check_mcp_grants as c  # noqa: E402

PLUGIN = "anantys-team-agents"
CHROME = c.exposed(PLUGIN, "claude-in-chrome")
SPEC = {"claude-in-chrome": {"command": "claude", "args": ["--claude-in-chrome-mcp"]}}
TOOLS = {"claude-in-chrome": {"navigate", "computer", "tabs_context_mcp"}}


def run(servers, grants, advertised):
    return c.check(PLUGIN, servers, [("skills/r/SKILL.md", grants)], advertised)


class UndeclaredServer(unittest.TestCase):
    def test_grants_with_no_declared_server_are_charged_to_the_manifest_once(self):
        errors, _ = run({}, ["mcp__claude-in-chrome__navigate", "mcp__claude-in-chrome__computer"], {})
        self.assertEqual(len(errors), 1)
        path, message = errors[0]
        self.assertTrue(path.endswith("plugin.json"))
        self.assertIn("declares no `mcpServers`", message)

    def test_a_tree_with_no_mcp_grants_at_all_is_clean(self):
        errors, warnings = run({}, ["Read", "Bash(git diff:*)"], {})
        self.assertEqual((errors, warnings), ([], []))

    def test_bare_server_name_is_an_error_when_the_plugin_declares_it(self):
        errors, _ = run(SPEC, ["mcp__claude-in-chrome__navigate"], TOOLS)
        path, message = errors[0]
        self.assertEqual(path, "skills/r/SKILL.md")
        self.assertIn(CHROME, message)

    def test_an_unknown_server_segment_is_the_roles_own_error(self):
        errors, _ = run(SPEC, ["mcp__plugin_other_whatever__navigate"], TOOLS)
        path, message = errors[0]
        self.assertEqual(path, "skills/r/SKILL.md")
        self.assertIn("does not declare", message)

    def test_the_namespaced_prefix_resolves(self):
        errors, _ = run(SPEC, [f"mcp__{CHROME}__navigate"], TOOLS)
        self.assertEqual(errors, [])


class ToolExistence(unittest.TestCase):
    def test_a_tool_the_server_does_not_advertise_is_an_error(self):
        errors, _ = run(SPEC, [f"mcp__{CHROME}__update_plan"], TOOLS)
        path, message = errors[0]
        self.assertEqual(path, "skills/r/SKILL.md")
        self.assertIn("update_plan", message)
        self.assertIn("does not", message)

    def test_an_unprobed_server_verifies_no_tool_name_and_warns(self):
        errors, warnings = run(SPEC, [f"mcp__{CHROME}__update_plan"], {"claude-in-chrome": None})
        self.assertEqual(errors, [])
        self.assertIn("went unverified", warnings[0][1])

    def test_an_empty_tool_list_is_not_an_unprobed_server(self):
        errors, _ = run(SPEC, [f"mcp__{CHROME}__navigate"], {"claude-in-chrome": set()})
        self.assertIn("navigate", errors[0][1])


class DeclaredButUngranted(unittest.TestCase):
    def test_a_server_no_role_grants_warns(self):
        _, warnings = run(SPEC, ["Read"], TOOLS)
        self.assertIn("that no role grants", warnings[0][1])

    def test_a_granted_server_does_not_warn_as_ungranted(self):
        _, warnings = run(SPEC, [f"mcp__{CHROME}__navigate"], TOOLS)
        self.assertEqual(warnings, [])


class Grants(unittest.TestCase):
    def frontmatter(self, block):
        d = Path(tempfile.mkdtemp())
        p = d / "SKILL.md"
        p.write_text(f"---\n{block}\n---\n\nbody\n", encoding="utf-8")
        return c.grants_of(p)

    def test_a_wrapped_block_sequence_is_read(self):
        self.assertEqual(
            self.frontmatter("name: r\ntools:\n  - Read\n  - mcp__x__navigate"),
            ["Read", "mcp__x__navigate"],
        )

    def test_a_flow_sequence_is_read(self):
        self.assertEqual(self.frontmatter('tools: ["Bash", "Read"]'), ["Bash", "Read"])

    def test_a_scoped_grant_holding_a_space_is_one_token(self):
        self.assertEqual(self.frontmatter("allowed-tools: Bash(git diff:*), Read"),
                         ["Bash(git diff:*)", "Read"])

    def test_the_last_declaration_wins_as_the_loader_reads_it(self):
        self.assertEqual(self.frontmatter("tools: Read\ntools: Write"), ["Write"])

    def test_an_unclosed_block_yields_nothing_rather_than_guessing(self):
        d = Path(tempfile.mkdtemp())
        p = d / "SKILL.md"
        p.write_text("---\ntools: Read\n", encoding="utf-8")
        self.assertEqual(c.grants_of(p), [])


class GrantShape(unittest.TestCase):
    def test_a_malformed_identifier_is_left_to_check_platform(self):
        errors, _ = run(SPEC, ["mcp_chrome_nav"], TOOLS)
        self.assertEqual(errors, [])

    def test_a_third_separator_lands_in_the_tool_segment(self):
        errors, _ = run(SPEC, [f"mcp__{CHROME}__a__b"], TOOLS)
        self.assertIn("`a__b`", errors[0][1])


class Probe(unittest.TestCase):
    def test_a_command_that_does_not_exist_is_unprobed_not_empty(self):
        self.assertIsNone(c.probe({"command": "koan-no-such-binary-xyz"}))

    def test_a_server_with_no_command_is_unprobed(self):
        self.assertIsNone(c.probe({"args": ["--x"]}))

    def test_a_reply_among_notifications_is_found(self):
        script = (
            "import sys,json\n"
            "sys.stdin.readline()\n"
            "print(json.dumps({'jsonrpc':'2.0','method':'notifications/message'}),flush=True)\n"
            "print(json.dumps({'jsonrpc':'2.0','id':2,'result':"
            "{'tools':[{'name':'navigate'},{'name':'computer'}]}}),flush=True)\n"
        )
        self.assertEqual(
            c.probe({"command": sys.executable, "args": ["-c", script]}),
            {"navigate", "computer"},
        )

    def test_a_server_that_answers_nothing_is_unprobed(self):
        self.assertIsNone(c.probe({"command": sys.executable, "args": ["-c", "pass"]}))


#: A stdio server that answers `tools/list` from `pages`, keyed by the cursor it
#: was asked with (`None` for the first page). Each value is the `result` verbatim,
#: so a test writes the exact shape the spec allows.
PAGINATING = """
import sys, json
pages = json.loads({pages!r})
for line in sys.stdin:
    if not line.strip():
        continue
    msg = json.loads(line)
    if msg.get("method") == "initialize":
        print(json.dumps({{"jsonrpc": "2.0", "id": msg["id"], "result": {{}}}}), flush=True)
    elif msg.get("method") == "tools/list":
        cursor = (msg.get("params") or {{}}).get("cursor") or "first"
        print(json.dumps({{"jsonrpc": "2.0", "id": msg["id"],
                          "result": pages[cursor]}}), flush=True)
"""


def paginating(pages: dict) -> set[str] | None:
    script = PAGINATING.format(pages=json.dumps(pages))
    return c.probe({"command": sys.executable, "args": ["-c", script]}, timeout=10.0)


class Pagination(unittest.TestCase):
    """`tools/list` is paginated, and the first page read as the whole list is an error."""

    def test_every_page_is_collected(self):
        self.assertEqual(
            paginating(
                {
                    "first": {"tools": [{"name": "navigate"}], "nextCursor": "p2"},
                    "p2": {"tools": [{"name": "computer"}], "nextCursor": "p3"},
                    "p3": {"tools": [{"name": "update_plan"}]},
                }
            ),
            {"navigate", "computer", "update_plan"},
        )

    def test_a_tool_on_a_later_page_is_not_reported_as_unadvertised(self):
        tools = paginating(
            {
                "first": {"tools": [{"name": "navigate"}], "nextCursor": "p2"},
                "p2": {"tools": [{"name": "update_plan"}]},
            }
        )
        # Asserted, not implied: an unprobed `None` would also produce no error,
        # which is the one way this test could go green while the defect stands.
        self.assertEqual(tools, {"navigate", "update_plan"})
        errors, _ = run(SPEC, [f"mcp__{CHROME}__update_plan"], {"claude-in-chrome": tools})
        self.assertEqual(errors, [])

    def test_a_single_page_is_the_whole_list(self):
        self.assertEqual(
            paginating({"first": {"tools": [{"name": "navigate"}]}}), {"navigate"}
        )

    def test_a_cursor_the_server_never_clears_is_unprobed_not_partial(self):
        self.assertIsNone(paginating({"first": {"tools": [{"name": "navigate"}], "nextCursor": "first"}}))

    def test_a_page_the_server_does_not_answer_is_unprobed_not_partial(self):
        # `p2` is absent, so the server raises and dies rather than replying: the
        # first page's one tool must not become the server's whole advertised set.
        self.assertIsNone(
            paginating({"first": {"tools": [{"name": "navigate"}], "nextCursor": "p2"}})
        )


if __name__ == "__main__":
    unittest.main()
