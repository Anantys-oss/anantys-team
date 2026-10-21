#!/usr/bin/env python3
"""Fixture tests for check_exposed_names — run: python3 -m unittest discover scripts

`expose()` boots a real loader and takes seconds, so nothing here calls it: the
workflow running the gate against this tree is that function's test, and it is
the only test of it that proves anything. What these cover is every decision
made *about* the loader's answer, against a tree on disk.
"""

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import check_exposed_names as c  # noqa: E402

EXPOSED = {
    "p:anantys-qa",
    "p:anantys.code-auditor",
    "anantys-qa",
    "anantys.code-auditor",
}


def tree(files):
    root = Path(tempfile.mkdtemp())
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


class Squash(unittest.TestCase):
    def test_two_spellings_of_one_name_collapse(self):
        self.assertEqual(c.squash("anantys.qa"), c.squash("anantys-qa"))

    def test_different_names_do_not_collapse(self):
        self.assertNotEqual(c.squash("anantys-qa"), c.squash("anantys-ops"))


class Unexposed(unittest.TestCase):
    def test_a_skill_the_loader_named_is_clean(self):
        root = tree({"plugins/p/skills/anantys.qa/SKILL.md": "x"})
        self.assertEqual(list(c.unexposed(root, EXPOSED)), [])

    def test_a_skill_the_loader_named_nothing_for_is_an_error(self):
        root = tree({"plugins/p/skills/anantys.ghost/SKILL.md": "x"})
        (error,) = c.unexposed(root, EXPOSED)
        self.assertIn("loads as nothing", error)
        self.assertIn("anantys.ghost", error)

    def test_a_skill_is_named_by_its_directory_not_its_filename(self):
        """SKILL.md is every skill's filename; the directory is the identity."""
        root = tree({"plugins/p/skills/anantys-qa/SKILL.md": "x"})
        self.assertEqual(list(c.unexposed(root, EXPOSED)), [])

    def test_an_agent_is_named_by_its_filename(self):
        root = tree({"plugins/p/agents/anantys.code-auditor.md": "x"})
        self.assertEqual(list(c.unexposed(root, EXPOSED)), [])

    def test_an_agent_the_loader_dropped_is_an_error(self):
        root = tree({"plugins/p/agents/anantys.ghost.md": "x"})
        (error,) = c.unexposed(root, EXPOSED)
        self.assertIn("anantys.ghost", error)

    def test_a_role_at_an_unconventional_depth_is_still_swept(self):
        root = tree({"vendor/extra/skills/anantys.ghost/SKILL.md": "x"})
        self.assertEqual(len(list(c.unexposed(root, EXPOSED))), 1)


class Misspellings(unittest.TestCase):
    def find(self, files):
        return dict(c.misspellings(tree(files), EXPOSED))

    def test_a_dotted_command_is_reported_against_the_exposed_one(self):
        found = self.find({"README.md": "Run `/anantys.qa` on the branch."})
        self.assertEqual(found[Path("README.md")], {"anantys.qa": "anantys-qa"})

    def test_the_exposed_spelling_is_not_reported(self):
        self.assertEqual(self.find({"README.md": "Run `/anantys-qa`."}), {})

    def test_the_namespaced_spelling_is_not_reported(self):
        self.assertEqual(self.find({"README.md": "Run `/p:anantys-qa`."}), {})

    def test_a_namespaced_misspelling_is_reported(self):
        found = self.find({"README.md": "Run `/p:anantys.qa`."})
        self.assertEqual(found[Path("README.md")], {"p:anantys.qa": "anantys-qa"})

    def test_a_slash_token_resembling_nothing_exposed_is_ignored(self):
        """Not every `/foo` in a repo is a claim about this plugin."""
        self.assertEqual(self.find({"README.md": "See /usr/bin and `/commit`."}), {})

    def test_a_path_that_merely_starts_with_the_prefix_is_ignored(self):
        self.assertEqual(self.find({"README.md": '"./plugins/anantys-team-agents"'}), {})

    def test_a_manifest_under_a_dot_directory_is_read(self):
        """The widest-reach file in the tree lives behind a leading dot."""
        found = self.find({".claude-plugin/marketplace.json": '{"d": "/anantys.qa"}'})
        self.assertIn(Path(".claude-plugin/marketplace.json"), found)

    def test_a_plugin_manifest_is_read(self):
        found = self.find({"plugins/p/.claude-plugin/plugin.json": '{"d": "/anantys.qa"}'})
        self.assertIn(Path("plugins/p/.claude-plugin/plugin.json"), found)

    def test_git_internals_are_not_read(self):
        self.assertEqual(self.find({".git/COMMIT_EDITMSG": "/anantys.qa"}), {})

    def test_a_file_is_reported_once_per_spelling_not_per_occurrence(self):
        found = self.find({"README.md": "/anantys.qa /anantys.qa /anantys.qa"})
        self.assertEqual(found[Path("README.md")], {"anantys.qa": "anantys-qa"})

    def test_a_non_markdown_non_manifest_file_is_not_advertising(self):
        self.assertEqual(self.find({"scripts/x.py": "'/anantys.qa'"}), {})


class Verdict(unittest.TestCase):
    def run_main(self, files, exposed=EXPOSED):
        root = tree(files)
        self.enterContext = None  # keep the patch local and obvious
        original = c.expose
        c.expose = lambda _root: (exposed, None)
        try:
            out = io.StringIO()
            with redirect_stdout(out):
                code = c.main(root)
            return code, out.getvalue()
        finally:
            c.expose = original

    def test_a_misspelling_alone_does_not_fail_the_gate(self):
        """The remedy is a documentation change this gate does not own."""
        code, out = self.run_main({"README.md": "/anantys.qa"})
        self.assertEqual(code, 0)
        self.assertIn("WARN", out)
        self.assertIn("exposed-name check: OK", out)

    def test_an_unexposed_role_fails_the_gate(self):
        code, out = self.run_main({"plugins/p/skills/anantys.ghost/SKILL.md": "x"})
        self.assertEqual(code, 1)
        self.assertIn("exposed-name check: FAILED", out)

    def test_a_clean_tree_reports_neither(self):
        code, out = self.run_main({"README.md": "Run `/p:anantys-qa`."})
        self.assertEqual(code, 0)
        self.assertNotIn("WARN", out)

    def test_the_loader_answer_is_printed_so_the_log_carries_the_measurement(self):
        _, out = self.run_main({"README.md": "x"})
        self.assertIn("p:anantys-qa", out)

    def test_an_unaskable_loader_skips_without_failing(self):
        original = c.expose
        c.expose = lambda _root: (None, "claude CLI not on PATH")
        try:
            out = io.StringIO()
            with redirect_stdout(out):
                code = c.main(tree({"plugins/p/skills/anantys.ghost/SKILL.md": "x"}))
        finally:
            c.expose = original
        self.assertEqual(code, 0)
        self.assertIn("SKIP", out.getvalue())
        self.assertNotIn("ERROR", out.getvalue())


class Sealing(unittest.TestCase):
    def test_every_credential_shape_is_stripped_from_the_loader_env(self):
        """`apiKeySource: none` is what makes this gate runnable in CI."""
        for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN"):
            self.assertTrue(c._is_credential(key), key)

    def test_ordinary_variables_survive(self):
        self.assertFalse(c._is_credential("PATH"))


if __name__ == "__main__":
    unittest.main()
