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

  1. **Frontmatter keys must be recognized, and declared once.** `allowed_tools:`
     is not `allowed-tools:`; the block parses, the key is ignored, and the skill
     loads with its grants unset. `anantys.ops` narrows Bash to three verbs — one
     underscore un-narrows it, and nothing anywhere in this repo or in the
     loader says a word. A key declared *twice* is the same silent drop without
     the typo: YAML keeps the last occurrence, discards the earlier one, and
     `claude plugin validate` was measured to pass the file. Both declarations
     read as live in the block, so the one that is not loaded is the one a
     reviewer is as likely to be reading — and the check below must read the
     one the loader keeps, or it shape-checks a list that was thrown away and
     leaves the live one unexamined.
  2. **Tool identifiers must be well-shaped.** An MCP tool is
     `mcp__server__tool`; a single underscore anywhere in that name makes it a
     tool that does not exist, the skill loads without it, and the prose that
     depends on it ("capture the console error") becomes unexecutable at the
     one moment it is needed. The grant list is read across the indented lines
     YAML lets it wrap onto, because a check that only reads the key's own line
     goes quiet on every wrapped form — and quiet is the thing being checked for.

Neither check invents a registry of real tool names — that would go stale and
is not ours to maintain. They check spelling and shape, which is where the
silent failures actually live.

Exit 0 = clean. 1 = at least one error, the CLI is absent, the discovery glob
matched no plugin at all, or the loader answered in a shape the keys above do not
fit — a gate whose input set is empty, or whose reading of a non-empty answer
came back empty, must say so, because `0 error(s), 0 warning(s)` is otherwise
indistinguishable from a healthy run. `--strict` also fails on warnings.
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
    before = len(errors) + len(warnings)
    for section in [report.get("manifest") or {}, *(report.get("contents") or [])]:
        where = Path(section.get("file", plugin_dir)).name
        for kind, sink in (("errors", errors), ("warnings", warnings)):
            for item in section.get(kind) or []:
                sink.append(f"loader: {where}: {item.get('path')}: {item['message']}")
    # The report states its own verdict in `success`. Read it, and check that it
    # agrees with what the keys above yielded: a tree the validator says did not
    # pass, with nothing this parser could extract, means the shape moved and the
    # loader half of the gate has gone quiet — printing `0 error(s)` exactly as a
    # clean run does. `platform.yml` installs the CLI unpinned, so that drift
    # arrives without a commit and no test in this repo would catch it.
    if report.get("success") is not True and len(errors) + len(warnings) == before:
        errors.append(
            f"{rel(plugin_dir)}: validator did not pass yet reported nothing this gate could "
            f"read — findings live under `manifest`/`contents` as `errors`/`warnings`, and the "
            f"report's top-level keys are {sorted(report)}"
        )


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
    # A key declared twice is the same silent drop as a key spelled wrong, minus the
    # typo: YAML keeps the last occurrence and discards the earlier one without a
    # word, and `claude plugin validate` passes the file. Both declarations read as
    # live to anyone looking at the block, so the one that is not loaded is the one a
    # reviewer is as likely to be reading.
    for key in sorted({k for k in keys if keys.count(k) > 1}):
        errors.append(
            f"{rel(path)}: frontmatter declares `{key}` {keys.count(key)} times — the loader "
            "keeps the last one and drops the rest silently; a reader cannot tell which "
            "declaration is in force"
        )
    # Read the key's whole value, not just the rest of its line. `anantys.ops`
    # declares twelve grants on one 500-character line; the obvious thing to do
    # with it is wrap it, and YAML lets the value continue on any indented line —
    # as a block sequence (`- Read`) or a wrapped flow sequence. Matching `.*$`
    # alone yields the empty string for the block form, and the check below then
    # iterates nothing and prints `0 error(s)`: this gate's own silent-drop
    # failure, in the half of it that exists because the loader is silent too.
    # Last, not first: YAML resolves a repeated key to its final occurrence, so
    # `re.search` would shape-check a list the loader threw away — and leave the one
    # it actually loaded unexamined. The duplicate is reported above; reading it the
    # loader's way is what keeps this check pointed at the live declaration anyway.
    found = re.findall(rf"^{tools_key}:(.*(?:\n[ \t]+.*)*)$", block, re.MULTILINE)
    declared = found[-1] if found else None
    # `is not None`, not truthiness: a key declared with nothing under it yields the
    # empty string, and that is the case the empty-grant error below exists for.
    if declared is not None:
        # Split on commas and line breaks only — a scoped grant is one token even
        # when it holds a space (`Bash(git diff:*)`). Splitting on whitespace
        # instead is how a grant checker comes to reject every narrowed grant it
        # was written to encourage.
        value = re.sub(r"^[ \t]*-[ \t]*", "", declared, flags=re.MULTILINE)
        value = re.sub(r"[\[\]\"']", " ", value)
        tools = [t.strip() for t in re.findall(r"[^,\n]*\([^)]*\)|[^,\n]+", value)]
        tools = [t for t in tools if t]
        if not tools:
            # A key with nothing under it reads exactly like no key at all, so
            # both the narrowing and this check vanish together, silently.
            errors.append(
                f"{rel(path)}: `{tools_key}:` is declared with no tool under it — an empty "
                "grant list is indistinguishable from an absent one, so the narrowing it "
                "looks like it sets is not set"
            )
        for tool in tools:
            if not TOOL_SHAPE.match(tool):
                errors.append(
                    f"{rel(path)}: `{tool}` is not a well-formed tool identifier — the skill "
                    "loads without it and the prose that needs it cannot run"
                )


def main(argv: list[str]) -> int:
    strict = "--strict" in argv
    have_cli = shutil.which("claude") is not None
    if not have_cli:
        errors.append("the `claude` CLI is not on PATH — this gate asks it, it cannot guess")

    manifests = sorted(ROOT.glob("plugins/*/.claude-plugin/plugin.json"))
    if not manifests:
        print(f"no plugins found under {ROOT}", file=sys.stderr)
        return 1

    for manifest in manifests:
        plugin_dir = manifest.parent.parent
        # Gate on the CLI alone. Gating on `errors` instead makes a component
        # error found in one plugin silently stop the loader being asked about
        # every plugin after it — the half of this gate that cannot be guessed.
        if have_cli:
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
