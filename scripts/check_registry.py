#!/usr/bin/env python3
r"""Ask the loader which names it registered, and hold the repo to that answer.

Two gates here already run the CLI, and neither of them can answer this file's
question. `claude plugin validate` reads manifests. `claude plugin details`
prints the cost table — and prints each component under its *directory* name,
unsanitized, which is the one spelling that routes nothing. So the repo's only
statement about what a user can actually type is `check_plugins.exposed_skill_name`:
a Python re-implementation of the loader's sanitizer, established by hand on CLI
2.1.278 and re-verified by nothing since.

The session's own `system`/`init` event is the registry. It lists `skills`,
`agents` and `slash_commands` under the ids the router matches against, it is
emitted before the first model call, and it needs no credential — probed here
against `ANTHROPIC_API_KEY=sk-ant-invalid-probe`, which still prints the full
table and only then fails to authenticate. That makes it usable as a gate on
every pull request at zero token cost, on the runner `platform.yml` already
installs the CLI on.

Three checks, each closing a hole the static gates cannot reach:

1. **Every component in the tree is registered.** A skill directory or agent
   file the loader silently declines to load is a role that ships, passes every
   other gate, and does not exist at runtime.

2. **`exposed_skill_name` agrees with the registry.** The sanitizer rule is
   asserted against the program it describes rather than against the memory of a
   probe. If a future CLI stops folding `.` to `-`, or starts folding something
   else, this reddens on the next pull request instead of being discovered the
   next time somebody re-reads a docstring.

3. **Every role name the manifest descriptions advertise resolves.** This is the
   check with a live defect to catch. Both descriptions sell the skills as
   `/anantys-team-agents:anantys.design` — and the registry has
   `anantys-team-agents:anantys-design`, so none of the five advertised commands
   routes. `check_plugins` reads those same descriptions for their *counts*
   ("5 skills", "2 review agents") and never for the names, which is how the
   catalog came to tell every browsing user to type a string that resolves to
   nothing. Resolution is exact equality against the registered id or its bare
   `:`-suffix, so `anantys-design` and `anantys-team-agents:anantys-design` both
   pass and the dotted form fails on either reading.

A `:`-led fragment (`, :anantys.ops`) is read as an elision of the plugin
prefix, not as a spelling a user types: the check completes it and rules on the
part after the colon. Narrowing it further would be a style opinion, and this
file has none.

Exit 0 = clean (warnings allowed), 1 = at least one error. No `claude` on PATH,
or a readout this file cannot parse, is a warning: a gate that cannot measure
must not rule.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from check_plugins import exposed_skill_name

ROOT = Path(__file__).resolve().parent.parent

#: A role reference inside a manifest description. `/`-led is a command a user
#: types; `:`-led is the prefix-elided continuation the descriptions use after
#: the first entry. Agent names appear bare, which is indistinguishable from
#: prose, so they are checked by their registration (check 1) and not by grep.
#: At least one `.` or `-` is required so that an ordinary slashed word — the
#: `or` of `and/or` — is prose rather than a command this gate rules on.
ADVERTISED = re.compile(r"[/:]([A-Za-z0-9_]*[.-][A-Za-z0-9_.-]*)")
#: Stripped before scanning: a link's path segments are not commands.
URL = re.compile(r"\bhttps?://\S+")

errors: list[str] = []
warnings: list[str] = []


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def registry(plugin_dir: Path) -> dict | None:
    """The `system`/`init` event for a session with ``plugin_dir`` loaded, or ``None``.

    The prompt is a throwaway: the event is emitted during startup, so the run is
    killed by its own missing credential long before the prompt means anything.
    The key is forced to an invalid value rather than unset, so a runner holding a
    real one cannot turn this gate into a billable call.
    """
    try:
        done = subprocess.run(
            ["claude", "--plugin-dir", str(plugin_dir),
             "--print", "--output-format", "stream-json", "--verbose", "x"],
            cwd=ROOT, capture_output=True, text=True, timeout=180,
            stdin=subprocess.DEVNULL,
            env={**os.environ, "ANTHROPIC_API_KEY": "sk-ant-invalid-probe"},
        )
    except (OSError, subprocess.SubprocessError):
        return None
    first = done.stdout.partition("\n")[0]
    try:
        event = json.loads(first)
    except ValueError:
        return None
    return event if event.get("subtype") == "init" else None


def ids(event: dict, key: str, plugin: str) -> set[str]:
    """Registered ids under ``key`` that belong to ``plugin``, prefix stripped."""
    return {
        entry.removeprefix(f"{plugin}:")
        for entry in event.get(key) or []
        if isinstance(entry, str) and entry.startswith(f"{plugin}:")
    }


def declared_agent_name(path: Path) -> str:
    """An agent's registered identity: its frontmatter `name:`, or its stem if unset.

    The mirror image of a skill, and the reason this cannot reuse one rule for
    both — see `check_plugins.exposed_skill_name`. Falling back to the stem keeps
    a missing `name:` as `check_plugins`' finding to report, not a second copy here.
    """
    found = re.search(r"^name:[ \t]*(\S.*?)[ \t]*$", path.read_text(encoding="utf-8"), re.M)
    return found.group(1) if found else path.stem


def check_components(event: dict, plugin_dir: Path, plugin: str) -> None:
    registered = ids(event, "skills", plugin) | ids(event, "agents", plugin)
    for skill_dir in sorted(d for d in (plugin_dir / "skills").glob("*") if d.is_dir()):
        expected = exposed_skill_name(skill_dir)
        if expected in registered:
            continue
        if skill_dir.name in registered:
            errors.append(
                f"{rel(skill_dir)}: the loader registered `{skill_dir.name}`, but "
                f"`exposed_skill_name` says `{expected}` — the sanitizer rule in "
                f"check_plugins.py no longer describes this CLI, and every name "
                f"derived from it is now wrong"
            )
        else:
            errors.append(
                f"{rel(skill_dir)}: not registered as `{expected}` or anything else — "
                f"the loader declined this skill, so it ships and does not exist"
            )
    for agent in sorted((plugin_dir / "agents").glob("*.md")):
        expected = declared_agent_name(agent)
        if expected not in registered:
            errors.append(
                f"{rel(agent)}: not registered as `{expected}` — an agent is registered "
                f"under its frontmatter `name:`, so nothing can delegate to this file"
            )


def check_advertised(event: dict, path: Path, description: str, plugin: str) -> None:
    """Error on a role name a description sells that the router does not match."""
    resolvable = set()
    for key in ("slash_commands", "agents"):
        for entry in event.get(key) or []:
            if isinstance(entry, str) and entry.startswith(f"{plugin}:"):
                resolvable |= {entry, entry.removeprefix(f"{plugin}:")}
    if not resolvable:
        warnings.append(
            f"{rel(path)}: the registry lists nothing under `{plugin}`, so the names "
            f"its description advertises went unmeasured"
        )
        return
    for token in ADVERTISED.findall(URL.sub("", description)):
        if token in resolvable or f"{plugin}:{token}" in resolvable or token == plugin:
            continue
        # A name that resolves once its separators are folded is the whole defect
        # here: the dot in the directory never reached the router. Naming that one
        # id beats listing seven, because the remedy is a character edit.
        folded = re.sub(r"[^A-Za-z0-9_]", "-", token)
        meant = f" — did you mean `{folded}`?" if folded in resolvable else ""
        errors.append(
            f"{rel(path)}: description advertises `{token}`, which the loader does not "
            f"register, so a user reading the catalog types it and gets nothing{meant}"
        )


def main(argv: list[str] = ()) -> int:
    if stray := [a for a in argv if Path(a).resolve() != ROOT]:
        sys.exit(
            f"error: this gate checks {ROOT}, the tree its own file is in — it cannot be "
            f"pointed at {', '.join(stray)}"
        )
    marketplace_path = ROOT / ".claude-plugin" / "marketplace.json"
    marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
    for entry in marketplace["plugins"]:
        plugin_dir = (ROOT / entry["source"]).resolve()
        plugin = entry["name"]
        event = registry(plugin_dir)
        if event is None:
            warnings.append(
                f"{entry['source']}: no `system`/`init` readout — `claude` is absent or "
                f"printed something this gate cannot parse, so nothing here was measured "
                f"against the loader"
            )
            continue
        check_components(event, plugin_dir, plugin)
        check_advertised(event, marketplace_path, entry["description"], plugin)
        manifest_path = plugin_dir / ".claude-plugin" / "plugin.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        check_advertised(event, manifest_path, manifest.get("description", ""), plugin)

    for warning in warnings:
        print(f"warning: {warning}")
    for error in errors:
        print(f"error: {error}")
    print(f"{len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
