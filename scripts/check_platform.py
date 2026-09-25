#!/usr/bin/env python3
"""Ask the loader, then cover what the loader does not answer.

Every other checker in `scripts/` compares the repo to itself — the marketplace
against the manifest, the prose against the tool grants, one branch against
another. None of them asks the program that actually loads the plugin. This one
does, and then measures what that answer is worth.

What `claude plugin validate` was measured to do (v2.1.278, seven mutations of a
known-good tree, both invocation targets):

  * Pointed at the repo root it reads `.claude-plugin/marketplace.json` and
    reports *no component findings at all* — a SKILL.md with its description
    deleted comes back clean. Each plugin directory must be passed by name.
  * Pointed at a plugin directory it reports missing component metadata, and
    nothing else: not a skill `name` that disagrees with its directory, not an
    unknown tool in `allowed-tools`, not `allowed_tools` misspelled with an
    underscore, not `model: gpt-4`.

So the loader is one input here, not the gate. The two checks below cover the
gap that matters, both of which end the same way — a capability declaration
that silently stops applying:

  1. **Frontmatter keys must be recognized.** `allowed_tools:` is not
     `allowed-tools:`; the block parses, the key is ignored, and the skill loads
     with its grants unset. `anantys.ops` narrows Bash to three verbs — one
     underscore un-narrows it, and nothing anywhere in this repo or in the
     loader says a word.
  2. **Tool identifiers must be well-shaped.** An MCP tool is
     `mcp__server__tool`; a single underscore anywhere in that name makes it a
     tool that does not exist, the skill loads without it, and the prose that
     depends on it ("capture the console error") becomes unexecutable at the
     one moment it is needed.

Neither check invents a registry of real tool names — that would go stale and
is not ours to maintain. They check spelling and shape, which is where the
silent failures actually live.

Exit 0 = clean. 1 = at least one error, or the CLI is absent. `--strict` also
fails on warnings.
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The loader's own vocabulary, read off its validation messages.
SKILL_KEYS = frozenset(
    {"name", "description", "allowed-tools", "model", "shell", "hooks", "disable-model-invocation"}
)
AGENT_KEYS = frozenset({"name", "description", "tools", "model", "color"})

# `Read`, `Bash(git:*)`, `mcp__claude-in-chrome__navigate` — and nothing else.
TOOL_SHAPE = re.compile(r"^(?:mcp__[a-z0-9-]+__[a-z0-9_]+|[A-Z][A-Za-z]*(?:\([^)]*\))?)$")

errors: list[str] = []
warnings: list[str] = []


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def ask_the_loader(plugin_dir: Path, strict: bool) -> None:
    """Run `claude plugin validate` on a plugin directory and record what it says."""
    cmd = ["claude", "plugin", "validate", str(plugin_dir), "--json"] + (["--strict"] * strict)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    try:
        report = json.loads(proc.stdout)
    except json.JSONDecodeError:
        errors.append(f"{rel(plugin_dir)}: validator produced no report ({proc.stderr.strip()})")
        return
    for section in [report.get("manifest") or {}, *(report.get("contents") or [])]:
        where = Path(section.get("file", plugin_dir)).name
        for kind, sink in (("errors", errors), ("warnings", warnings)):
            for item in section.get(kind) or []:
                sink.append(f"loader: {where}: {item.get('path')}: {item['message']}")


def frontmatter_keys(path: Path) -> tuple[list[str], str]:
    """Top-level keys of the leading `---` block, and its raw body.

    A block that never closes is the silent-drop case the loader does not warn
    about, so it is an error here rather than an empty result.
    """
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        errors.append(f"{rel(path)}: no frontmatter block — every field is dropped at load time")
        return [], ""
    block, sep, _ = text[4:].partition("\n---\n")
    if not sep:
        errors.append(f"{rel(path)}: frontmatter block is never closed — every field is dropped")
        return [], ""
    return [line.split(":", 1)[0] for line in block.splitlines() if re.match(r"^\S+:", line)], block


def check_component(path: Path, known: frozenset[str], tools_key: str) -> None:
    keys, block = frontmatter_keys(path)
    for key in keys:
        if key not in known:
            errors.append(
                f"{rel(path)}: unrecognized frontmatter key `{key}` — it is ignored at load "
                f"time with no warning; known keys are {', '.join(sorted(known))}"
            )
    declared = re.search(rf"^{tools_key}:(.*)$", block, re.MULTILINE)
    if declared:
        # Split on commas only — a scoped grant is one token even when it holds a
        # space (`Bash(git diff:*)`). Splitting on whitespace instead is how a
        # grant checker comes to reject every narrowed grant it was written to
        # encourage.
        value = declared.group(1).strip(" []").replace('"', "").replace("'", "")
        for tool in (t.strip() for t in re.findall(r"[^,]*\([^)]*\)|[^,]+", value)):
            if not TOOL_SHAPE.match(tool):
                errors.append(
                    f"{rel(path)}: `{tool}` is not a well-formed tool identifier — the skill "
                    "loads without it and the prose that needs it cannot run"
                )


def main(argv: list[str]) -> int:
    strict = "--strict" in argv
    if shutil.which("claude") is None:
        errors.append("the `claude` CLI is not on PATH — this gate asks it, it cannot guess")

    for manifest in sorted(ROOT.glob("plugins/*/.claude-plugin/plugin.json")):
        plugin_dir = manifest.parent.parent
        if not errors:
            ask_the_loader(plugin_dir, strict)
        for skill in sorted(plugin_dir.glob("skills/*/SKILL.md")):
            check_component(skill, SKILL_KEYS, "allowed-tools")
        for agent in sorted(plugin_dir.glob("agents/*.md")):
            check_component(agent, AGENT_KEYS, "tools")

    for warning in warnings:
        print(f"warning: {warning}")
    for error in errors:
        print(f"error: {error}")
    print(f"{len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors or (strict and warnings) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
