#!/usr/bin/env python3
"""Fixture tests for check_version_bump.py. Stdlib only: `python3 scripts/test_check_version_bump.py`.

Each case builds a throwaway git repo shaped like this one, commits a base, tags
it as the last release, then commits a branch change and asserts the exit code.
The checker reads git history, so a real repo is the only honest fixture.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CHECKER = Path(__file__).resolve().parent / "check_version_bump.py"
PLUGIN = "plugins/demo"


class VersionBumpCase(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path(tempfile.mkdtemp(prefix="version-bump-"))
        self.sh("git", "init", "-q", "-b", "main")
        self.sh("git", "config", "user.email", "t@example.com")
        self.sh("git", "config", "user.name", "T")
        (self.repo / "scripts").mkdir()
        (self.repo / "scripts/check_version_bump.py").write_text(CHECKER.read_text())
        self.write_marketplace(["./" + PLUGIN])
        self.write_plugin("0.1.0")
        self.write(f"{PLUGIN}/skills/demo/SKILL.md", "---\nname: demo\n---\n\nbody\n")
        self.commit("base")
        self.sh("git", "tag", "v0.1.0")  # the released baseline the version is measured against

    def sh(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(args, cwd=self.repo, capture_output=True, text=True, check=True)

    def write(self, rel: str, text: str) -> None:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def write_marketplace(self, sources: list[str]) -> None:
        plugins = [
            {"name": Path(s).name, "version": "0.1.0", "source": s} for s in sources
        ]
        self.write(".claude-plugin/marketplace.json", json.dumps({"plugins": plugins}))

    def write_plugin(self, version: str, plugin: str = PLUGIN) -> None:
        self.write(
            f"{plugin}/.claude-plugin/plugin.json",
            json.dumps({"name": Path(plugin).name, "version": version}),
        )

    def commit(self, message: str) -> None:
        self.sh("git", "add", "-A")
        self.sh("git", "commit", "-qm", message)

    def check(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "scripts/check_version_bump.py", "main"],
            cwd=self.repo,
            capture_output=True,
            text=True,
        )

    def branch(self) -> None:
        self.sh("git", "checkout", "-qb", "topic")

    # --- the defect this exists to catch -------------------------------------

    def test_content_change_without_bump_fails(self) -> None:
        self.branch()
        self.write(f"{PLUGIN}/skills/demo/SKILL.md", "---\nname: demo\n---\n\nrewritten\n")
        self.commit("edit skill")
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("still 0.1.0", result.stderr)
        self.assertIn("SKILL.md", result.stderr)

    def test_content_change_with_bump_passes(self) -> None:
        self.branch()
        self.write(f"{PLUGIN}/skills/demo/SKILL.md", "---\nname: demo\n---\n\nrewritten\n")
        self.write_plugin("0.2.0")
        self.commit("edit skill + bump")
        self.assertEqual(self.check().returncode, 0)

    def test_reference_page_counts_as_content(self) -> None:
        """Not just SKILL.md — anything the installed plugin ships."""
        self.branch()
        self.write(f"{PLUGIN}/skills/demo/reference/run.md", "detail\n")
        self.commit("add reference page")
        self.assertEqual(self.check().returncode, 1)

    # --- things that must NOT fail ------------------------------------------

    def test_change_outside_the_plugin_needs_no_bump(self) -> None:
        self.branch()
        self.write("README.md", "docs\n")
        self.write(".github/workflows/ci.yml", "on: push\n")
        self.commit("docs + ci")
        self.assertEqual(self.check().returncode, 0)

    def test_bumping_the_manifest_alone_needs_no_bump(self) -> None:
        """The manifest is excluded from content, so a lone bump is not self-justifying."""
        self.branch()
        self.write_plugin("0.2.0")
        self.commit("bump only")
        self.assertEqual(self.check().returncode, 0)

    def test_no_changes_against_base_passes(self) -> None:
        self.branch()
        self.assertEqual(self.check().returncode, 0)

    def test_brand_new_plugin_owes_no_bump(self) -> None:
        self.branch()
        self.write_marketplace(["./" + PLUGIN, "./plugins/fresh"])
        self.write_plugin("0.1.0", plugin="plugins/fresh")
        self.write("plugins/fresh/skills/fresh/SKILL.md", "---\nname: fresh\n---\n\nbody\n")
        self.commit("add a second plugin")
        self.assertEqual(self.check().returncode, 0)

    # --- the baseline is the release, not the merge-base ---------------------

    def test_siblings_may_name_the_same_next_version(self) -> None:
        """Two independent PRs naming 0.2.0 both pass, even after the first lands.

        The second is branched from the updated main — the state any rebase puts a
        queued branch in. Measured against the merge-base it would fail: its base
        already says 0.2.0, so it would owe a further, distinct bump, and the
        sibling behind it a further one still. Measured against the release it is
        simply the same unreleased version, which is what it is.
        """
        self.branch()
        self.write(f"{PLUGIN}/skills/demo/SKILL.md", "---\nname: demo\n---\n\nby A\n")
        self.write_plugin("0.2.0")
        self.commit("A: edit skill + name 0.2.0")
        self.assertEqual(self.check().returncode, 0)

        self.sh("git", "checkout", "-q", "main")
        self.sh("git", "merge", "-q", "--no-edit", "topic")  # A lands; no release cut yet

        self.sh("git", "checkout", "-qb", "topic-b")
        self.write(f"{PLUGIN}/skills/demo/reference/b.md", "by B\n")
        self.write_plugin("0.2.0")
        self.commit("B: edit skill + name the same 0.2.0")
        result = self.check()
        self.assertEqual(result.returncode, 0)
        # ...and the debt that buys: 0.2.0 is on main, untagged, so the floor is still v0.1.0.
        self.assertIn("warning:", result.stderr)
        self.assertIn("already names 0.2.0", result.stderr)

    # --- the debt the release baseline runs on ------------------------------

    def test_a_version_landed_but_never_tagged_is_reported(self) -> None:
        """The floor is the tag, so content landed under an untagged version is invisible.

        This is the price of measuring against the release: nothing in the repo
        makes the release happen. Report it, do not fail it — failing would put
        the queue back on N distinct values, which is what the tag baseline
        bought us out of.
        """
        self.sh("git", "checkout", "-q", "main")
        self.write(f"{PLUGIN}/skills/demo/SKILL.md", "---\nname: demo\n---\n\nlanded\n")
        self.write_plugin("0.2.0")
        self.commit("land 0.2.0 without cutting a release")

        self.branch()
        self.write(f"{PLUGIN}/skills/demo/reference/more.md", "more\n")
        self.write_plugin("0.2.0")
        self.commit("another change under the same unreleased version")
        result = self.check()
        self.assertEqual(result.returncode, 0)
        self.assertIn("already names 0.2.0", result.stderr)
        self.assertIn("v0.1.0", result.stderr)

    def test_no_debt_reported_when_the_base_matches_the_tag(self) -> None:
        self.branch()
        self.write(f"{PLUGIN}/skills/demo/SKILL.md", "---\nname: demo\n---\n\nrewritten\n")
        self.write_plugin("0.2.0")
        self.commit("edit skill + bump")
        result = self.check()
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("warning:", result.stderr)

    def test_untagged_debt_is_not_reported_in_merge_base_mode(self) -> None:
        """Without a tag the published version always moves — there is no debt to name."""
        self.sh("git", "tag", "-d", "v0.1.0")
        self.sh("git", "checkout", "-q", "main")
        self.write(f"{PLUGIN}/skills/demo/SKILL.md", "---\nname: demo\n---\n\nlanded\n")
        self.write_plugin("0.2.0")
        self.commit("land 0.2.0")

        self.branch()
        self.write(f"{PLUGIN}/skills/demo/reference/more.md", "more\n")
        self.write_plugin("0.3.0")
        self.commit("the next distinct value the fallback forces")
        result = self.check()
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("warning:", result.stderr)

    def test_no_release_tag_falls_back_to_the_merge_base(self) -> None:
        """A repo that has never published still gets the original gate, not a free pass."""
        self.sh("git", "tag", "-d", "v0.1.0")
        self.branch()
        self.write(f"{PLUGIN}/skills/demo/SKILL.md", "---\nname: demo\n---\n\nrewritten\n")
        self.commit("edit skill")
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("no release tag", result.stdout)

    def test_non_semver_tags_are_not_release_baselines(self) -> None:
        self.sh("git", "tag", "-d", "v0.1.0")
        self.sh("git", "tag", "nightly")
        self.branch()
        self.write(f"{PLUGIN}/skills/demo/SKILL.md", "---\nname: demo\n---\n\nrewritten\n")
        self.commit("edit skill")
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("no release tag", result.stdout)

    def test_newest_release_tag_wins(self) -> None:
        """v0.10.0 is newer than v0.9.0 — version order, not string order."""
        for version in ("0.9.0", "0.10.0"):
            self.write_plugin(version)
            self.commit(f"ship {version}")
            self.sh("git", "tag", f"v{version}")
        self.branch()
        self.write(f"{PLUGIN}/skills/demo/SKILL.md", "---\nname: demo\n---\n\nrewritten\n")
        self.write_plugin("0.9.5")  # ahead of v0.9.0, behind v0.10.0
        self.commit("edit skill + name a version the last release already passed")
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("v0.10.0", result.stderr)

    # --- a bump must be a real one ------------------------------------------

    def test_lowered_version_fails(self) -> None:
        self.branch()
        self.write(f"{PLUGIN}/skills/demo/SKILL.md", "---\nname: demo\n---\n\nrewritten\n")
        self.write_plugin("0.0.9")
        self.commit("edit + downgrade")
        self.assertEqual(self.check().returncode, 1)

    def test_non_semver_version_fails(self) -> None:
        self.branch()
        self.write(f"{PLUGIN}/skills/demo/SKILL.md", "---\nname: demo\n---\n\nrewritten\n")
        self.write_plugin("0.2")
        self.commit("edit + malformed version")
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("MAJOR.MINOR.PATCH", result.stderr + result.stdout)

    def test_patch_bump_is_enough(self) -> None:
        self.branch()
        self.write(f"{PLUGIN}/skills/demo/SKILL.md", "---\nname: demo\n---\n\nrewritten\n")
        self.write_plugin("0.1.1")
        self.commit("edit + patch bump")
        self.assertEqual(self.check().returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
