#!/usr/bin/env python3
"""Validate the marketplace against what the plugin tree actually contains.

Nothing here is a style opinion: every check below is an invariant that, when
broken, ships a marketplace a user cannot install or a catalog that lies about
its contents. Run it with no arguments from anywhere in the repo.

Exit 0 = clean (warnings allowed), 1 = at least one error.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROLE_MAX_LINES = 200  # see README "Skill size" — a role loads in full, every invocation
CONTRACT = "TEAM-CONTRACT.md"  # the rules every role in a plugin shares; each must link it

#: Commit the working tree departs from, so a load can be reported as a *change*
#: rather than as a standing fact. ``None`` = no baseline available; see ``merge_base``.
BASE: str | None = None

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


def merge_base() -> str | None:
    """The commit the working tree departs from, or ``None`` when git cannot say.

    Absence of a baseline is not a pass: ``check_load`` keeps its absolute warning
    and only loses the ability to attribute growth to the change under review.
    """
    for ref in ("origin/main", "main"):
        try:
            done = subprocess.run(
                ["git", "merge-base", "HEAD", ref],
                cwd=ROOT, capture_output=True, text=True, timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if done.returncode == 0 and done.stdout.strip():
            return done.stdout.strip()
    return None


def at(commit: str, path: Path) -> str | None:
    """``path``'s content at ``commit``, or ``None`` when it was not there."""
    done = subprocess.run(
        ["git", "show", f"{commit}:{rel(path)}"],
        cwd=ROOT, capture_output=True, text=True,
    )
    return done.stdout if done.returncode == 0 else None


def disk(path: Path) -> str | None:
    """``path``'s content in the working tree, or ``None`` when it is not there."""
    return path.read_text(encoding="utf-8") if path.is_file() else None


def load_parts(path: Path, read) -> list[tuple[Path, int]]:
    """What a role loads before its first action, as ``(file, lines)`` pairs.

    The role file itself, plus every local `.md` its *preamble* links — everything
    above the first `## ` heading is where a role names what binds it before it
    acts, and those files are read on the same invocation.

    Discovered from the links, never from a filename, so a role that points
    somewhere else is measured against what it actually points at. ``read`` decides
    *which tree* is measured, which is what lets the same rule price a baseline.
    """
    text = read(path)
    if text is None:
        return []
    parts = [(path, len(text.splitlines()))]
    for link in re.findall(r"\]\(([^)]+\.md)\)", text.split("\n## ", 1)[0]):
        target = (path.parent / link).resolve()
        if (body := read(target)) is not None:
            parts.append((target, len(body.splitlines())))
    return parts


def check_load(path: Path) -> None:
    """Warn when a role's *pre-action load* exceeds the ceiling — and say who did it.

    An absolute total is the same number on every branch, so a warning phrased
    only as "loads N lines" says nothing about the change being reviewed: a commit
    that adds forty lines to an over-ceiling role and one that adds none report
    identically. That is how a queue of individually-clean changes walks a role
    past the ceiling without any single one of them being the branch that did it.

    So the load is also priced against ``BASE``, and the warning names the delta.
    """
    parts = load_parts(path, disk)
    total = sum(n for _, n in parts)
    if total <= ROLE_MAX_LINES:
        return

    breakdown = " + ".join(f"{n} {rel(p)}" for p, n in parts)
    remedy = (
        "move detail a given action does not need into reference/ and link it there "
        f"— never the {CONTRACT}, which `check_contract` requires"
    )
    before = sum(n for _, n in load_parts(path, lambda p: at(BASE, p))) if BASE else None

    if before is None or before == total:
        change = f"loads {total} lines (> {ROLE_MAX_LINES})"
    elif before <= ROLE_MAX_LINES:
        change = f"this change pushes the load over the ceiling, {before} -> {total} (> {ROLE_MAX_LINES})"
    elif total > before:
        change = f"this change grows a load already over the ceiling, {before} -> {total} (+{total - before})"
    else:
        change = f"loads {total} lines (> {ROLE_MAX_LINES}), down from {before}"
    warnings.append(f"{rel(path)}: {change} — {breakdown}; {remedy}")


def check_contract(path: Path, contract: Path) -> None:
    """Error when a role's preamble does not link the contract that claims to bind it.

    ``TEAM-CONTRACT.md`` opens *"Rules that bind every role in this plugin"*, *"Every
    role file points here"* and *"This file is loaded before every action of every
    role"*. Those are three assertions about the tree, and nothing checked any of
    them — the binding was a convention that happened to hold.

    Worse, the one check that read the link read it as a cost. The contract counts
    toward ``check_load``'s ceiling, so the five roles that point at it load 207-723
    against a 200 limit; deleting the single line that binds them takes three of
    those under the ceiling and the run stays green. The cheapest way to satisfy the
    ceiling was to stop being bound. A ceiling may make a role shorter; it may not
    make it unbound.
    """
    if contract not in [p for p, _ in load_parts(path, disk)]:
        errors.append(
            f"{rel(path)}: preamble does not link {CONTRACT} — a role names what binds "
            "it above its first `## ` heading, where it is read before the role acts"
        )


def require(path: Path, fm: dict[str, str], keys: tuple[str, ...], expected_name: str) -> None:
    for key in keys:
        if not fm.get(key):
            errors.append(f"{rel(path)}: frontmatter is missing `{key}`")
    if fm.get("name", expected_name) != expected_name:
        errors.append(f"{rel(path)}: frontmatter name `{fm['name']}` != `{expected_name}`")


def main() -> int:
    global BASE
    BASE = merge_base()
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

        # An absent contract is not an error: the file is one some *other* change lands,
        # and a gate that reddens every branch until it arrives forces an order on changes
        # that have none. It is not silence either — an absent input that prints nothing
        # is a check reporting health it never measured.
        contract = plugin_dir / CONTRACT
        if not contract.is_file():
            warnings.append(f"{rel(plugin_dir)}: no {CONTRACT}, so no role's binding is checked")
            contract = None

        for skill_dir in skills:
            skill = skill_dir / "SKILL.md"
            if not skill.exists():
                errors.append(f"{rel(skill_dir)}: no SKILL.md")
                continue
            require(skill, frontmatter(skill), ("name", "description"), skill_dir.name)
            if contract:
                check_contract(skill, contract)
            check_load(skill)

        for agent in agents:
            require(agent, frontmatter(agent), ("name", "description", "tools", "model"), agent.stem)
            if contract:
                check_contract(agent, contract)
            check_load(agent)

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
