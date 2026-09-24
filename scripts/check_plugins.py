#!/usr/bin/env python3
"""Validate the marketplace against what the plugin tree actually contains.

Nothing here is a style opinion: every check below is an invariant that, when
broken, ships a marketplace a user cannot install or a catalog that lies about
its contents. Run it with no arguments from anywhere in the repo.

Exit 0 = clean (warnings allowed), 1 = at least one error.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_MAX_LINES = 200  # see README "Skill size" — a SKILL.md loads in full, every invocation

errors: list[str] = []
warnings: list[str] = []


def frontmatter(path: Path) -> dict[str, str]:
    """Top-level `key: value` pairs of a YAML frontmatter block. Values stay raw strings."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        errors.append(f"{rel(path)}: missing YAML frontmatter")
        return {}
    _, block, _ = text.split("---\n", 2)
    return dict(
        (line.partition(":")[0].strip(), line.partition(":")[2].strip())
        for line in block.splitlines()
        if line[:1].isalpha() and ":" in line
    )


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def require(path: Path, fm: dict[str, str], keys: tuple[str, ...], expected_name: str) -> None:
    for key in keys:
        if not fm.get(key):
            errors.append(f"{rel(path)}: frontmatter is missing `{key}`")
    if fm.get("name", expected_name) != expected_name:
        errors.append(f"{rel(path)}: frontmatter name `{fm['name']}` != `{expected_name}`")


def main() -> int:
    marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())

    for entry in marketplace["plugins"]:
        plugin_dir = (ROOT / entry["source"]).resolve()
        manifest_path = plugin_dir / ".claude-plugin/plugin.json"
        if not manifest_path.exists():
            errors.append(f"marketplace.json: source `{entry['source']}` has no plugin.json")
            continue
        manifest = json.loads(manifest_path.read_text())

        # The catalog is a copy of the manifest; a stale copy installs the wrong version.
        for field in ("name", "version", "description"):
            if entry[field] != manifest[field]:
                errors.append(
                    f"{field} drift: marketplace.json has {entry[field]!r}, "
                    f"{rel(manifest_path)} has {manifest[field]!r}"
                )

        skills = sorted(p for p in (plugin_dir / "skills").iterdir() if p.is_dir())
        agents = sorted((plugin_dir / "agents").glob("*.md"))

        for skill_dir in skills:
            skill = skill_dir / "SKILL.md"
            if not skill.exists():
                errors.append(f"{rel(skill_dir)}: no SKILL.md")
                continue
            require(skill, frontmatter(skill), ("name", "description"), skill_dir.name)
            lines = len(skill.read_text(encoding="utf-8").splitlines())
            if lines > SKILL_MAX_LINES:
                warnings.append(
                    f"{rel(skill)}: {lines} lines (> {SKILL_MAX_LINES}) — "
                    "move per-action detail into reference/ and link it from the actions table"
                )

        for agent in agents:
            require(agent, frontmatter(agent), ("name", "description", "tools", "model"), agent.stem)

        # The description advertises counts ("5 skills … 2 review agents") to users browsing
        # the marketplace, and nothing keeps them true when a role is added.
        for actual, noun in ((len(skills), "skills"), (len(agents), "agents")):
            claimed = re.search(rf"(\d+)\s+(?:\w+\s+)?{noun}", entry["description"])
            if claimed and int(claimed.group(1)) != actual:
                errors.append(
                    f"description claims {claimed.group(1)} {noun}, tree has {actual}"
                )

        # README is the only place a user reads before installing.
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for name in [d.name for d in skills] + [a.stem for a in agents]:
            if name not in readme:
                errors.append(f"README.md does not mention `{name}`")

    for warning in warnings:
        print(f"warning: {warning}")
    for error in errors:
        print(f"error: {error}")
    print(f"{len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
