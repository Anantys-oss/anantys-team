#!/usr/bin/env python3
"""Fixture tests for check_exposed_names — run: python3 -m unittest discover scripts

`expose()` boots a real loader and takes seconds, so nothing here calls it: the
workflow running the gate against this tree is that function's test, and it is
the only test of it that proves anything. What these cover is every decision
made *about* the loader's answer, against a tree on disk.
"""

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock
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

    def test_a_path_segment_spelled_like_an_exposed_name_is_ignored(self):
        """The resemblance filter cannot save this one — the segment *is* the name."""
        self.assertEqual(self.find({"README.md": "`skills/anantys.qa/SKILL.md`"}), {})

    def test_the_sentence_explaining_the_naming_rule_is_clean(self):
        """Verbatim from the tree that had fixed every real occurrence."""
        text = "so `skills/anantys.qa/` ships as `anantys-qa`."
        self.assertEqual(self.find({"README.md": text}), {})

    def test_a_command_inside_a_manifest_description_is_still_reported(self):
        """The boundary must admit `(` — the manifests' own delimiter."""
        doc = '{"description": "5 skills (/anantys.qa, /anantys.ops)"}'
        found = self.find({".claude-plugin/marketplace.json": doc})
        self.assertEqual(
            found[Path(".claude-plugin/marketplace.json")], {"anantys.qa": "anantys-qa"}
        )

    def test_a_command_opening_a_line_is_still_reported(self):
        found = self.find({"README.md": "run it:\n/anantys.qa report\n"})
        self.assertEqual(found[Path("README.md")], {"anantys.qa": "anantys-qa"})

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


class Contradictions(unittest.TestCase):
    """Two dead spellings of one name — what a fold produces and a diff hides."""

    def found(self, text):
        (found,) = dict(c.misspellings(tree({"README.md": text}), EXPOSED)).values()
        return found

    def test_one_dead_spelling_is_not_a_contradiction(self):
        self.assertEqual(list(c.contradictions({"anantys.qa": "anantys-qa"})), [])

    def test_two_dead_spellings_of_one_name_are_reported(self):
        found = {"anantys.qa": "anantys-qa", "p:anantys.qa": "anantys-qa"}
        self.assertEqual(
            list(c.contradictions(found)),
            [("anantys-qa", ["anantys.qa", "p:anantys.qa"])],
        )

    def test_dead_spellings_of_different_names_are_not_a_contradiction(self):
        """Five roles each misspelled once is main's state, not a merge artifact."""
        found = {"anantys.qa": "anantys-qa", "anantys.ops": "anantys-ops"}
        self.assertEqual(list(c.contradictions(found)), [])

    def test_the_table_a_fold_produced(self):
        """The shape on koan/the-agent-type-the-loader-registers: both rows kept."""
        doc = (
            "the skills additionally have their dots rewritten to hyphens\n"
            "| skill `/p:anantys.qa` |\n"
            "| skill `/anantys.qa` |\n"
        )
        self.assertEqual(
            list(c.contradictions(self.found(doc))),
            [("anantys-qa", ["anantys.qa", "p:anantys.qa"])],
        )

    def test_the_live_spelling_beside_a_dead_one_is_not_a_contradiction(self):
        """Only dead spellings reach `found`; teaching the real name is no clash."""
        self.assertEqual(
            list(c.contradictions(self.found("`/anantys-qa` (formerly `/anantys.qa`)"))),
            [],
        )


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

    def test_two_dead_spellings_of_one_name_fail_the_gate(self):
        """The remedy is deleting a line in this file — nothing has to land first."""
        code, out = self.run_main({"README.md": "`/p:anantys.qa` and `/anantys.qa`"})
        self.assertEqual(code, 1)
        self.assertIn("2 dead spellings of `anantys-qa`", out)
        self.assertIn("exposed-name check: FAILED", out)

    def test_the_contradicting_file_is_still_warned_with_its_full_inventory(self):
        """The error names the clash; the warning stays the per-file inventory."""
        doc = "`/p:anantys.qa` `/anantys.qa` `/anantys.ops`"
        _, out = self.run_main({"README.md": doc}, exposed=EXPOSED | {"anantys-ops"})
        self.assertIn("advertises 3 command(s)", out)

    def test_several_names_each_misspelled_once_still_only_warns(self):
        """This tree's actual state on `main`: five roles, one dead spelling each."""
        doc = "`/anantys.qa` `/anantys.ops`"
        code, out = self.run_main({"README.md": doc}, exposed=EXPOSED | {"anantys-ops"})
        self.assertEqual(code, 0)
        self.assertNotIn("ERROR", out)

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


class LoaderEnv(unittest.TestCase):
    """The seal. `CLAUDE_CONFIG_DIR` outranks `HOME`, so it must be assigned."""

    def test_the_config_dir_is_sealed_under_the_throwaway_home(self):
        env = c.loader_env("/tmp/throwaway")
        self.assertTrue(env["CLAUDE_CONFIG_DIR"].startswith("/tmp/throwaway"))

    def test_an_inherited_config_dir_does_not_survive(self):
        """The developer's own config dir is what the gate must not read or write."""
        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": "/home/dev/.claude"}):
            env = c.loader_env("/tmp/throwaway")
        self.assertNotEqual(env["CLAUDE_CONFIG_DIR"], "/home/dev/.claude")

    def test_home_is_the_throwaway(self):
        self.assertEqual(c.loader_env("/tmp/throwaway")["HOME"], "/tmp/throwaway")

    def test_credentials_are_still_stripped(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-x"}):
            self.assertNotIn("ANTHROPIC_API_KEY", c.loader_env("/tmp/throwaway"))

    def test_ordinary_variables_still_reach_the_loader(self):
        with mock.patch.dict(os.environ, {"PATH": "/usr/bin"}):
            self.assertEqual(c.loader_env("/tmp/throwaway")["PATH"], "/usr/bin")


if __name__ == "__main__":
    unittest.main()
