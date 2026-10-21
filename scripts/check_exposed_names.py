#!/usr/bin/env python3
"""Ask a booted loader which names it exposes, and hold the tree to them.

`claude plugin validate` — the gate `.github/workflows/validate.yml` runs — is
the loader, and that is exactly why it is trusted. But it answers one question:
does this manifest parse, do these components have well-formed frontmatter. It
never reports a *name*. So the one defect a user meets first is outside its
reach: typing an advertised command and getting nothing.

The loader does answer it. A session's `system`/`init` event lists `skills`,
`agents` and `slash_commands` as the loader resolved them, and it is emitted
before any model call:

    claude --print --output-format stream-json --verbose x < /dev/null | head -1

`apiKeySource` on that event reads `none` with every credential unset, so this
runs in CI with no secret — the same property that makes `validate` safe to run
there.

What the booted loader says about this tree, and it is not what the tree says:

    skills   anantys-team-agents:anantys-debug ... :anantys-review
    agents   anantys-team-agents:anantys.code-auditor, :anantys.spec-tester

A skill's name comes from its *directory*, sanitized — `anantys.qa/` exposes
`anantys-qa`, and the frontmatter `name:` it disagrees with is what `claude
plugin details` prints and nothing routes on. An agent's comes from its
*filename*, which keeps the dot. So the two halves of one plugin are spelled
differently on purpose, and no amount of reading the tree reveals which half a
given string belongs to. `check_plugins` predicts the skill half with
`re.sub(r"[^A-Za-z0-9_-]", "-", ...)`; that prediction happens to be right, and
a prediction is still not the loader.

Two findings, and they are deliberately not the same severity:

  * a role in the tree that the loader exposes nothing for -> error. The role
    ships and loads as nothing; the remedy is wholly inside whatever change
    introduced it.
  * an advertised command that near-misses an exposed name -> warning, per file.
    `/anantys.qa` is a command no session has; the remedy is a documentation
    change this gate does not own, and erroring would force the two to land in
    one order. Same line `check_tool_grants` draws for bare `Bash`: per-tree,
    attributable, and silent once the owning change lands — so no baseline file
    to keep in step.

"Near-misses" is the whole of the second check's precision. A `/`-token is
compared to the exposed names with every non-alphanumeric character stripped, so
`/anantys.qa` is reported against `anantys-qa`. A token that resembles no exposed
name is somebody else's command, not a typo of ours.

That filter alone is not enough, because a *path* segment can also resemble an
exposed name. `./plugins/anantys-team-agents` is ignored for the wrong reason —
no exposed name resembles it — while `skills/anantys.qa/` squashes to exactly
`anantys-qa` and was reported as a dead command. It is the sentence explaining
this gate's own premise, in the one tree that had already fixed every real
occurrence: the gate's only finding there was the documentation of why it exists.

So the `/` must *open* a token, not continue a path: nothing word-like, no dot,
hyphen or slash before it. Every command this tree advertises sits after a
backtick, a brace, a parenthesis or whitespace, and every path segment sits after
a name character — which makes the boundary the discriminator, and the
resemblance filter only a second opinion.

Usage: python3 scripts/check_exposed_names.py [root]
Exit 1 on errors, 0 on warnings.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# Where a tree advertises a command to a reader, as opposed to defining one.
# `**` rather than a fixed prefix for the reason `check_tool_grants.main`
# records: `marketplace.json`'s `source` is a free-form relative path, so a
# plugin at `vendor/extra` is installable and its README is just as read.
#
# The manifests belong in this set and were the hardest to keep in it. A
# plugin's `description` is the one string every session pays for — `claude
# plugin details` prices it at always-on — and both manifests live under a
# `.claude-plugin/` directory, so the obvious "skip hidden paths" guard for
# `.git` silently dropped the two files with the widest reach. Hence SKIP_PARTS:
# name the directories to skip, never a shape they share with the subject.
ADVERTISING = ("**/*.md", "**/.claude-plugin/*.json")
SKIP_PARTS = {".git", "__pycache__", "node_modules"}

# The lookbehind is the path guard: a command's `/` opens a token, a path
# segment's `/` follows one. See the "Near-misses" paragraph above.
SLASH_TOKEN = re.compile(r"(?<![\w./-])/([A-Za-z0-9][A-Za-z0-9._:-]*)")


def squash(name):
    """A name with its punctuation removed, for comparing two spellings of one.

    The dot/hyphen split is the only difference this gate is looking for, and it
    is not a difference the loader will ever report back — it resolved one
    spelling and dropped the other.
    """
    return re.sub(r"[^a-z0-9]", "", name.lower())


def expose(root):
    """Install the tree's own marketplace into a throwaway HOME and ask.

    A sealed HOME is not hygiene, it is the measurement: the names depend on
    what is installed, so reading the developer's own session would report their
    other plugins and whichever version of this one they last installed.

    Returns the exposed bare names, or None when the loader could not be asked.
    A gate that cannot run must say so rather than certify silence, but it may
    not redden a pull request over a missing CLI.
    """
    catalog = root / ".claude-plugin" / "marketplace.json"
    if not catalog.is_file():
        return None, f"no {catalog.relative_to(root)} — nothing to install"
    plugins = json.loads(catalog.read_text(encoding="utf-8"))
    market = plugins["name"]
    names = [p["name"] for p in plugins["plugins"]]

    env = {k: v for k, v in os.environ.items() if not _is_credential(k)}
    with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as cwd:
        env["HOME"] = home
        run = lambda *a: subprocess.run(  # noqa: E731 - three identical calls
            ["claude", *a],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
        )
        try:
            add = run("plugin", "marketplace", "add", str(root))
        except FileNotFoundError:
            return None, "claude CLI not on PATH — the loader could not be asked"
        if add.returncode != 0:
            return None, f"marketplace add failed: {add.stderr.strip()[:200]}"
        for name in names:
            got = run("plugin", "install", f"{name}@{market}")
            if got.returncode != 0:
                return None, f"install {name} failed: {got.stderr.strip()[:200]}"
        session = run("--print", "--output-format", "stream-json", "--verbose", "x")
        first = session.stdout.strip().splitlines()
        if not first:
            return None, f"no init event: {session.stderr.strip()[:200]}"
        init = json.loads(first[0])

    # Both halves, and the namespace stripped: a reader writing `/anantys-qa`
    # without the plugin prefix is spelling the name right, which is all this
    # gate claims to measure.
    full = set(init.get("skills", [])) | set(init.get("agents", []))
    return full | {n.rsplit(":", 1)[-1] for n in full}, None


def _is_credential(key):
    return key.startswith("ANTHROPIC_") or key in {"CLAUDE_CODE_OAUTH_TOKEN"}


def roles(root):
    """Every role file, by the same sweep its sibling gates use."""
    return sorted(root.glob("**/skills/*/SKILL.md")) + sorted(root.glob("**/agents/*.md"))


def unexposed(root, exposed):
    """Role files the loader resolved no name for.

    Keyed on the squashed name so a role is reported for being absent, not for
    the dot/hyphen spelling the second check already covers.
    """
    squashed = {squash(n) for n in exposed}
    for path in roles(root):
        stem = path.parent.name if path.name == "SKILL.md" else path.stem
        if squash(stem) not in squashed:
            yield f"{path.relative_to(root)}: the loader exposes no name for `{stem}` — the role ships and loads as nothing"


def misspellings(root, exposed):
    """Advertised commands that resolve to nothing but name something that does.

    Yields `(relative path, {bad spelling: exposed spelling})`.
    """
    bare = {squash(n): n for n in exposed if ":" not in n}
    seen = set()
    for pattern in ADVERTISING:
        for path in sorted(root.glob(pattern)):
            if path in seen or SKIP_PARTS.intersection(path.parts):
                continue
            seen.add(path)
            found = {}
            for token in SLASH_TOKEN.findall(path.read_text(encoding="utf-8")):
                if token in exposed:
                    continue
                right = bare.get(squash(token.rsplit(":", 1)[-1]))
                if right:
                    found[token] = right
            if found:
                yield path.relative_to(root), found


def main(root):
    exposed, why = expose(root)
    if exposed is None:
        print(f"check_exposed_names: SKIP — {why}")
        return 0

    print(f"loader exposes: {', '.join(sorted(n for n in exposed if ':' in n))}")

    failed = False
    for error in unexposed(root, exposed):
        print(f"ERROR {error}")
        failed = True

    files = 0
    for rel, found in misspellings(root, exposed):
        files += 1
        fixes = ", ".join(f"`/{bad}` -> `{right}`" for bad, right in sorted(found.items()))
        print(f"WARN  {rel}: advertises {len(found)} command(s) no session exposes: {fixes}")
    if files:
        print(
            f"WARN  {files} file(s) teach a command the loader does not resolve — a reader "
            "who types one gets nothing. Owned by the change that documents the names."
        )

    print("exposed-name check: FAILED" if failed else "exposed-name check: OK")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()))
