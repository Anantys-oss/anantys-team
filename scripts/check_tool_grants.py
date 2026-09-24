#!/usr/bin/env python3
"""Check that every role's prose and its tool grants agree.

A skill or agent is a prompt plus a capability list. The two drift in both
directions, and each direction fails differently:

  * a tool the prose needs but the frontmatter withholds -> the role silently
    does something weaker than what it documents;
  * a tool granted but never referenced -> an unaudited capability sitting on a
    role that has no use for it.

Usage: python3 scripts/check_tool_grants.py [root]
Exit 1 on errors, 0 on warnings only.
"""

import re
import sys
from pathlib import Path

# Grants that are inherently generic — never reported as unreferenced.
GENERIC = {"Bash", "Read", "Write", "Edit", "Glob", "Grep"}

MCP_IN_PROSE = re.compile(r"`([a-z_]+)`|mcp__[a-z-]+__([a-z_]+)")
BASH_FENCE = re.compile(r"```(?:bash|sh|shell)\n(.*?)```", re.S)
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.S)


def parse(path):
    """Return (grants, body) or None when the file has no frontmatter."""
    m = FRONTMATTER.match(path.read_text(encoding="utf-8"))
    if not m:
        return None
    field = None
    for line in m.group(1).splitlines():
        if line.startswith(("allowed-tools:", "tools:")):
            field = line.split(":", 1)[1].strip()
    if field is None:
        return [], m.group(2)
    # agents use tools: ["Bash", "Read"]; skills use a bare comma-separated list
    grants = [g.strip().strip('"[]') for g in field.split(",")]
    return [g for g in grants if g], m.group(2)


def bash_commands(body):
    """First word of every command line inside a bash-fenced block."""
    found = set()
    for block in BASH_FENCE.findall(body):
        for line in block.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                found.add(line.split()[0])
    return found


def check(path, grants, body, known_mcp):
    errors, warnings = [], []
    lowered = body.lower()

    mcp_used = {a or b for a, b in MCP_IN_PROSE.findall(body)}
    mcp_granted = {g.rsplit("__", 1)[-1] for g in grants if g.startswith("mcp__")}
    bash_grants = {g[5:-1].split(":", 1)[0] for g in grants if g.startswith("Bash(")}
    has_bare_bash = "Bash" in grants

    for tool in sorted(mcp_used & known_mcp - mcp_granted):
        errors.append(f"prose uses browser tool `{tool}` but it is not granted")

    # A role that says it drives a browser must be able to. Naming the tools is
    # optional in prose; having them is not.
    if "browser" in lowered and not mcp_granted:
        errors.append("prose commits to driving a browser but grants no browser tool")

    if bash_grants and not has_bare_bash:
        for cmd in sorted(bash_commands(body) - bash_grants):
            errors.append(f"prose runs `{cmd}` but only {sorted(bash_grants)} are granted")

    # Browser primitives are used implicitly ("take a screenshot" is `computer`),
    # so only named, discretionary grants are held to being mentioned.
    for grant in grants:
        if grant in GENERIC or grant.startswith("mcp__"):
            continue
        name = grant[5:-1].split(":", 1)[0] if grant.startswith("Bash(") else grant
        if name.lower() not in lowered:
            warnings.append(f"grants `{grant}` but the prose never mentions it")

    return errors, warnings


def main(root):
    files = sorted(root.glob("plugins/*/skills/*/SKILL.md")) + sorted(
        root.glob("plugins/*/agents/*.md")
    )
    if not files:
        print(f"no skills or agents found under {root}", file=sys.stderr)
        return 1

    parsed = [(f, parse(f)) for f in files]
    # Every mcp tool named by any role — the vocabulary prose is checked against,
    # so a backticked word is only flagged when it is a real tool somewhere.
    known_mcp = {
        g.rsplit("__", 1)[-1]
        for _, p in parsed
        if p
        for g in p[0]
        if g.startswith("mcp__")
    }

    failed = False
    for path, p in parsed:
        rel = path.relative_to(root)
        if p is None:
            print(f"ERROR {rel}: no frontmatter")
            failed = True
            continue
        errors, warnings = check(path, *p, known_mcp)
        for e in errors:
            print(f"ERROR {rel}: {e}")
        for w in warnings:
            print(f"WARN  {rel}: {w}")
        failed = failed or bool(errors)

    print("tool-grant check: FAILED" if failed else "tool-grant check: OK")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()))
