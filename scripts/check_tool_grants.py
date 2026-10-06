#!/usr/bin/env python3
"""Check that every role's prose and its tool grants agree.

A skill or agent is a prompt plus a capability list. The two drift in both
directions, and each direction fails differently:

  * a tool the prose needs but the frontmatter withholds -> the role silently
    does something weaker than what it documents;
  * a tool granted but never referenced -> an unaudited capability sitting on a
    role that has no use for it;
  * a grant that reads as a narrowing but bounds nothing -> the audit records a
    restriction the runtime does not impose. See `UNBOUNDED`.

The second direction is only as good as what counts as a reference. Matching the
grant name as a case-folded substring makes any grant whose name is also an
ordinary word self-discharging, and the prose that *does* exercise a grant does
not always spell it: a role dispatches `anantys.code-auditor`, never `Task`. Both
errors landed on the same grant and pointed opposite ways — `qa` held an
unexercised `Task` in silence because it writes about `tasks.md`, while `review`,
the one role that dispatches, was reported as not mentioning it.

The first direction is only as good as what counts as a command. Reading them
out of ```bash fences alone left the check with nothing to read: `ops` is the
only role here with a narrowed grant set, so the only role the check runs on,
and it has no bash fence — it runs `mkdir -p` mid-sentence. The three grants it
narrows were never compared against anything, and the gate printed OK. See
`bash_commands`.

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

# Commands that run other commands. `Bash(<one of these>:*)` is bare `Bash`
# spelled as a narrowing: the prefix bounds the first word and nothing after it.
# `git` is the instance in this tree — `git config alias.x '!<shell>'` then
# `git x` is two calls, both inside `Bash(git:*)`, and `git fetch <url>` reaches
# the network. Naming a subcommand escapes this set on purpose: the hatches are
# themselves subcommands, so `Bash(git diff:*)` rejects `git config` already.
UNBOUNDED = {
    "bash",
    "docker",
    "env",
    "find",
    "git",
    "make",
    "node",
    "npm",
    "npx",
    "perl",
    "python",
    "python3",
    "sh",
    "ssh",
    "xargs",
    "zsh",
}

BASELINE = Path(__file__).with_name("tool-grants-baseline.txt")

# Prose that withholds or forbids a command, up to the span it governs. Anchored
# at the end so it must reach the span, and `[^.`\n]*` keeps it inside the one
# clause — a `not` in an earlier sentence governs nothing here. See `negated`.
WITHHELD = re.compile(
    r"\b(?:no|not|never|without|forbids?|forbidden|withholds?|denies|denied)\b[^.`\n]*\Z",
    re.I,
)

MCP_IN_PROSE = re.compile(r"`([a-z_]+)`|mcp__[a-z-]+__([a-z_]+)")
BASH_FENCE = re.compile(r"```(?:bash|sh|shell)\n(.*?)```", re.S)
INLINE_CODE = re.compile(r"`([a-z][\w./-]*(?: [^`\n]*)?)`")
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


def bash_commands(body, heads=frozenset(), known_mcp=frozenset()):
    """Every command the prose runs: bash-fenced lines, plus inline code spans.

    Fenced lines are kept whole because a grant may name a subcommand:
    `Bash(git diff:*)` permits `git diff --stat` and nothing else `git`.
    Truncating to the first word would compare `git` against `git diff` and
    reject every narrowed grant — pushing authors to `Bash(git:*)`, which
    `UNBOUNDED` rejects.

    Inline spans are read too, because a fence is not where a role writes a
    one-off command. These roles write prose, not runbooks: of 37 fences in the
    tree 29 carry no language tag and are report skeletons, while the one
    command any narrowed role runs — `ops` and its `mkdir -p` — sits in a
    sentence. On fences alone this function returns the empty set for every
    role the caller invokes it for.

    Two anchors bound that widening, because nothing in the markup separates
    `mkdir -p` from `current.md` and an unanchored read would call filenames
    commands:

      * the first word heads a granted prefix or is in `UNBOUNDED` — the span
        is about a command family the grants already speak about, so the grant
        can judge the specific form (`Bash(git log:*)` vs `git rev-parse`);
      * or a flag follows it. A lowercase word whose next token starts with `-`
        is an invocation and nothing else. This is the anchor that reaches a
        command no grant mentions at all — `rm -rf build` heads nothing and is
        not `UNBOUNDED`, so the first anchor cannot see it.

    Known mcp tool names are then removed: a one-word span is ambiguous between
    a command and a tool, and `find` is live in this tree as both — an
    `UNBOUNDED` shell command and a granted browser tool `ops` calls by name.

    A span the surrounding clause withholds or forbids is then dropped: prose
    saying a grant is absent is documenting the narrowing, not asking for it.
    Without this the gate's own purpose is reversed — `ops` justifies holding no
    `git`, and the two cheapest ways to silence the resulting error are to grant
    `Bash(git:*)` (which `UNBOUNDED` rejects) or to delete the justification.
    Only spans are read this way; a fence line is a runbook line whatever the
    prose around it says.

    What still escapes: a bare, flagless command that heads no grant and is
    not in `UNBOUNDED` — `` `curl` `` on its own. Without a command
    vocabulary it is indistinguishable from a backticked noun, and guessing
    one would trade silence for noise.
    """
    found = set()
    for block in BASH_FENCE.findall(body):
        for line in block.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                found.add(line)
    for m in INLINE_CODE.finditer(body):
        word, _, rest = m.group(1).partition(" ")
        if word not in known_mcp and (word in heads or rest.startswith("-")):
            if not WITHHELD.search(body[:m.start()]):
                found.add(m.group(1).strip())
    return found


def permitted(command, prefixes):
    """Is `command` covered by one of the granted command prefixes?"""
    return any(command == p or command.startswith(p + " ") for p in prefixes)


def check(path, grants, body, known_mcp, agents=()):
    errors, warnings = [], []
    lowered = body.lower()
    dispatched = sorted(a for a in agents if a in body)

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

    # A narrowing that bounds only the first word is not a narrowing, and the
    # mention check cannot catch it: its single warning says the prose never
    # names the grant, so its remedy is to write the word. Discharging it leaves
    # the unbounded grant in place and removes the last signal about it.
    for prefix in sorted(bash_grants & UNBOUNDED):
        errors.append(
            f"`Bash({prefix}:*)` is not a narrowing — `{prefix}` runs other "
            f"commands; grant the subcommands it needs"
        )

    if bash_grants and not has_bare_bash:
        # First word of each prefix: `Bash(git diff:*)` heads at `git`, so a
        # one-word span `git` is a candidate the narrowed grant then rejects.
        heads = {p.split()[0] for p in bash_grants} | UNBOUNDED
        for cmd in sorted(bash_commands(body, heads, known_mcp)):
            if not permitted(cmd, bash_grants):
                errors.append(f"prose runs `{cmd}` but only {sorted(bash_grants)} are granted")

    # Dispatching an agent needs `Task`, and the prose names the agent, never the
    # tool — so this direction is invisible to the mention check below. It is the
    # direction that matters most: a dispatched agent runs with the dispatcher's
    # grants, so `Task` is not one capability but the whole union, delegated.
    if dispatched and "Task" not in grants:
        errors.append(f"prose dispatches {', '.join(dispatched)} but `Task` is not granted")

    # Browser primitives are used implicitly ("take a screenshot" is `computer`),
    # so only named, discretionary grants are held to being mentioned.
    for grant in grants:
        if grant in GENERIC or grant.startswith("mcp__"):
            continue
        name = grant[5:-1].split(":", 1)[0] if grant.startswith("Bash(") else grant
        # Case-sensitively, on a word boundary. A case-folded substring test lets
        # an ordinary English word discharge a grant that shares its spelling:
        # `Task` was satisfied by "tasks.md", `Bash(ls:*)` by "tools". Those are
        # the two grants here whose names are also common words, and both were
        # silent on roles that never exercise them.
        if not re.search(rf"\b{re.escape(name)}\b", body) and not (
            grant == "Task" and dispatched
        ):
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
    # Dispatch targets, from the tree — an agent that exists is the only thing a
    # role can dispatch. A body never names its own file's agent (the `name:`
    # field is frontmatter, which `parse` strips), so this needs no self-exclusion.
    agents = {p.stem for p in root.glob("plugins/*/agents/*.md")}

    declared, matched = baseline(), set()
    failed = False
    for path, p in parsed:
        rel = path.relative_to(root)
        if p is None:
            print(f"ERROR {rel}: no frontmatter")
            failed = True
            continue
        body, orphans = prose_surface(path, p[1])
        errors, warnings = check(path, p[0], body, known_mcp, agents)
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
