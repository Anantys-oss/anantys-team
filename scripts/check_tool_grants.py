#!/usr/bin/env python3
"""Check that every role's prose and its tool grants agree.

A skill or agent is a prompt plus a capability list. The two drift in both
directions, and each direction fails differently:

  * a tool the prose needs but the frontmatter withholds -> the role silently
    does something weaker than what it documents;
  * a tool granted but never referenced -> an unaudited capability sitting on a
    role that has no use for it.

Errors that predate this gate are declared in `tool-grants-baseline.txt` rather
than fixed here — see `baseline()` for why the gate may not fix its own subject.

Usage: python3 scripts/check_tool_grants.py [root]
Exit 1 on undeclared errors, 0 on warnings and declared ones.
"""

import re
import sys
from pathlib import Path

# Grants that are inherently generic — never reported as unreferenced.
GENERIC = {"Bash", "Read", "Write", "Edit", "Glob", "Grep"}

BASELINE = Path(__file__).with_name("tool-grants-baseline.txt")

MCP_IN_PROSE = re.compile(r"`([a-z_]+)`|mcp__[a-z-]+__([a-z_]+)")
BASH_FENCE = re.compile(r"```(?:bash|sh|shell)\n(.*?)```", re.S)
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.S)
REFERENCE_LINK = re.compile(r"`(reference/[\w.-]+\.md)`")


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


def prose_surface(path, body):
    """A skill's prose is its SKILL.md plus every reference file it names.

    `docs/skill-size.md` makes moving an action's procedure into
    `reference/<topic>.md` the sanctioned remedy for an oversized SKILL.md. That
    relocation must not move prose out of this checker's view, or the split
    silences the gate in both directions: a grant justified only in a reference
    file reads as unaudited, and a command run only there escapes the check
    entirely. The unit is the surface the role loads, not the file it starts in.

    Returns (body, warnings). A reference file no action names is prose nothing
    ever reads — reported, because otherwise this widening quietly skips it.
    """
    ref_dir = path.parent / "reference"
    if not ref_dir.is_dir():
        return body, []
    named = set(REFERENCE_LINK.findall(body))
    parts, warnings = [body], []
    for ref in sorted(ref_dir.glob("*.md")):
        rel = f"reference/{ref.name}"
        if rel in named:
            parts.append(ref.read_text(encoding="utf-8"))
        else:
            warnings.append(f"{rel} is not named in SKILL.md — no action loads it")
    return "\n".join(parts), warnings


def bash_commands(body):
    """Every command line inside a bash-fenced block, whole.

    Kept whole because a grant may name a subcommand: `Bash(git diff:*)` permits
    `git diff --stat` and nothing else `git`. Truncating to the first word would
    compare `git` against `git diff` and reject every narrowed grant — pushing
    authors to the over-broad `Bash(git:*)` this checker exists to discourage.
    """
    found = set()
    for block in BASH_FENCE.findall(body):
        for line in block.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                found.add(line)
    return found


def permitted(command, prefixes):
    """Is `command` covered by one of the granted command prefixes?"""
    return any(command == p or command.startswith(p + " ") for p in prefixes)


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
        for cmd in sorted(bash_commands(body)):
            if not permitted(cmd, bash_grants):
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


def baseline():
    """Errors this gate was introduced alongside, and so may not fail on.

    A checker added to a repo that already violates it cannot go green on its
    own. Fixing the violation here would duplicate — and conflict with — the
    change that owns that fix, so the gate and the fix become mergeable only in
    one order, each looking optional until the other lands. Declaring the known
    error instead makes the two orderings independent.

    A declared error that no longer occurs is a warning, never a failure: the
    fix landing must not turn this gate red in its turn. The warning is the
    signal to delete the line.
    """
    if not BASELINE.is_file():
        return set()
    lines = BASELINE.read_text(encoding="utf-8").splitlines()
    return {s for s in (line.strip() for line in lines) if s and not s.startswith("#")}


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

    declared, matched = baseline(), set()
    failed = False
    for path, p in parsed:
        rel = path.relative_to(root)
        if p is None:
            print(f"ERROR {rel}: no frontmatter")
            failed = True
            continue
        body, orphans = prose_surface(path, p[1])
        errors, warnings = check(path, p[0], body, known_mcp)
        warnings += orphans
        for e in errors:
            entry = f"{rel}: {e}"
            if entry in declared:
                matched.add(entry)
                print(f"BASE  {entry} (declared in {BASELINE.name})")
            else:
                print(f"ERROR {entry}")
                failed = True
        for w in warnings:
            print(f"WARN  {rel}: {w}")

    for stale in sorted(declared - matched):
        print(f"WARN  fixed, so delete from {BASELINE.name}: {stale}")

    print("tool-grant check: FAILED" if failed else "tool-grant check: OK")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()))
