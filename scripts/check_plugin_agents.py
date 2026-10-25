#!/usr/bin/env python3
"""Check a plugin agent file against what the plugin agent loader does with it.

An agent file in `.claude/agents/` and the same file shipped inside a plugin are
not loaded by the same code, and the plugin path is narrower in two ways this
tree can get wrong.

**The registered name is namespaced.** The loader builds the agent's dispatchable
identity as `[pluginName, *namespaceDirs, name].join(":")` — so this tree's
`anantys.code-auditor` is registered as `anantys-team-agents:anantys.code-auditor`
and nothing else. The Agent tool resolves `subagent_type` by exact match on that
string, then by a normaliser that lowercases and strips whitespace, dashes and
underscores (`e.normalize("NFKC").toLowerCase().replace(/[\\p{White_Space}\\p{Pd}_]+/gu,"")`
in `claude` 2.1.278). It does not strip the prefix, and a colon is not whitespace,
a dash or an underscore. So a bare `anantys.code-auditor` normalises to
`anantys.codeauditor`, the registered name normalises to
`anantysteamagents:anantys.code-auditor`, the two are unequal, and the dispatch
fails with `Agent type 'anantys.code-auditor' not found`.

This is the one place the agents differ from the skills beside them. The plugin
*skill* loader mints a bare-name alias (`name` without a colon becomes an alias
for `plugin:name`), which is why `/anantys.qa` works and is not a finding. The
plugin *agent* loader returns no alias field, and the resolver matches only on
the registered name. A role that names an agent for dispatch must therefore name
the installed spelling in the same block, or it describes a call that errors.

**Three frontmatter keys are silently dropped.** `permissionMode`, `hooks` and
`mcpServers` are read, warned about on the loader's own log and discarded for
plugin agents — "Use .claude/agents/ for this level of control." A plugin agent
file that sets one claims a control it does not have, and the only reader who
finds out is whoever is watching the debug log at load time. Three more keys are
range-checked and dropped on a bad value rather than rejecting the file:
`memory`, `isolation` and `maxTurns`.

What this gate does *not* re-read: whether a dispatch's grant union exceeds the
dispatching role's ceiling. `check_delegation_grants` states that rule and acts
on it, and it is also where "is this block a dispatch?" is defined — a second
reading of either here would let the two gates disagree about the same sentence,
so both come from there by import.

Usage: python3 scripts/check_plugin_agents.py [root]
Exit 1 on errors, 0 on warnings only.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from check_delegation_grants import (  # noqa: E402
    BLOCK,
    FRONTMATTER,
    names,
    parse,
    prose_surface,
)

# Keys the plugin agent loader reads, warns about and throws away. Setting one in
# a plugin agent file is a claim of control the installed agent does not have.
DROPPED = ("permissionMode", "hooks", "mcpServers")
# Keys the loader range-checks, keeping the agent and dropping just the value.
MEMORY_LAYERS = ("user", "project", "local")
# `M.isolation==="worktree"?"worktree":void 0` — one accepted value, no error.
ISOLATION_VALUES = ("worktree",)
SCALAR = re.compile(r"\A(\w+):\s*(.*?)\s*\Z")


def frontmatter_keys(path):
    """Return the agent file's top-level scalar frontmatter as a dict, or None.

    Only the top level, and only scalars: every key this gate rules on is a
    scalar in every spelling the loader accepts for it. A nested mapping under
    `hooks:` still registers, because its key line is what `DROPPED` is about —
    the value is discarded either way.
    """
    m = FRONTMATTER.match(path.read_text(encoding="utf-8"))
    if not m:
        return None
    keys = {}
    for line in m.group(1).splitlines():
        if (s := SCALAR.match(line)) is not None:
            keys[s.group(1)] = s.group(2)
    return keys


def agent_type(path, agents_dir, plugin_name, declared_name):
    """The identity the loader registers: plugin, then namespace dirs, then name.

    `namespaceDirs` is the path from the plugin's `agents/` down to the file's
    own directory, which is empty for this tree today and is the reason a
    namespaced agent would otherwise read as merely prefixed. `declared_name`
    is the frontmatter `name`, falling back to the filename stem exactly as the
    loader's `(M.name ?? basename) ` does.
    """
    namespace = path.parent.relative_to(agents_dir).parts
    return ":".join([plugin_name, *namespace, declared_name])


def plugin_name(plugin_dir):
    """The manifest `name`, which is what the loader joins — not the directory.

    A plugin whose directory and manifest name disagree would register its
    agents under the manifest's spelling, so reading the directory here would
    make every dispatch in the tree look wrong (or right) for the wrong reason.
    Falls back to the directory name when there is no readable manifest, which
    is the loader's own behaviour for a plugin it still loads.
    """
    manifest = plugin_dir / ".claude-plugin" / "plugin.json"
    if manifest.is_file():
        try:
            if name := json.loads(manifest.read_text(encoding="utf-8")).get("name"):
                return str(name)
        except json.JSONDecodeError:
            pass
    return plugin_dir.name


def check_frontmatter(agents):
    """Rule the keys the loader drops. `agents` is {agent_type: (label, keys)}."""
    errors = []
    for registered, (label, keys) in sorted(agents.items()):
        for key in DROPPED:
            if key in keys:
                errors.append(
                    f"{label}: sets `{key}`, which the plugin agent loader reads, "
                    f"warns about and discards — the installed agent does not get "
                    f"it. Drop the key, or ship the agent in `.claude/agents/`"
                )
        if (value := keys.get("memory")) is not None and value not in MEMORY_LAYERS:
            errors.append(
                f"{label}: `memory: {value}` is not one of "
                f"{', '.join(MEMORY_LAYERS)} — the loader drops the value and the "
                f"agent gets no memory"
            )
        if (value := keys.get("isolation")) is not None and value not in ISOLATION_VALUES:
            errors.append(
                f"{label}: `isolation: {value}` is dropped — a plugin agent file "
                f"may only ask for {', '.join(ISOLATION_VALUES)}"
            )
        if (value := keys.get("maxTurns")) is not None and not (
            value.isdigit() and int(value) > 0
        ):
            errors.append(
                f"{label}: `maxTurns: {value}` is not a positive integer — the "
                f"loader drops the value and the agent runs to the default cap"
            )
    return errors


def check_dispatch_spelling(skills, agents):
    """Every block that dispatches an agent must name the registered spelling.

    The block is the unit because that is where a reader looks for the name to
    pass, and because `check_delegation_grants` already scopes a dispatch to one.
    Naming the bare form *as well* is fine and is what a role documenting both
    install shapes does — the error is a block that names only the bare one,
    because that block describes a call that returns "not found".
    """
    errors = []
    for name, _grants, body in skills:
        for block in BLOCK.split(body):
            for registered, (label, _keys) in sorted(agents.items()):
                bare = registered.rsplit(":", 1)[1]
                if not names(block, bare) or registered in block:
                    continue
                errors.append(
                    f"{name}: dispatches `{bare}`, but the loader registers that "
                    f"agent as `{registered}` and the Agent tool matches only "
                    f"that spelling — name it in the same block as the dispatch"
                )
    return errors


def main(root):
    """Sweep every plugin's agents, then every role's prose for their names.

    Only `plugins/*/agents/` is swept: a file in `.claude/agents/` is loaded by
    the other path, where none of these rules hold.
    """
    agents, skills = {}, []
    for agents_dir in sorted(root.glob("plugins/*/agents")):
        name = plugin_name(agents_dir.parent)
        for path in sorted(agents_dir.glob("**/*.md")):
            keys = frontmatter_keys(path)
            if keys is None:
                continue
            declared = keys.get("name") or path.stem
            registered = agent_type(path, agents_dir, name, declared)
            agents[registered] = (str(path.relative_to(root)), keys)
    for path in sorted(root.glob("**/skills/*/SKILL.md")):
        if parsed := parse(path):
            skill_name, grants, body = parsed
            body, _unnamed = prose_surface(path, body)
            skills.append((skill_name, grants, body))

    if not agents:
        print(f"no plugin agents found under {root}", file=sys.stderr)
        return 1

    errors = check_frontmatter(agents) + check_dispatch_spelling(skills, agents)
    for e in errors:
        print(f"ERROR {e}")
    for registered in sorted(agents):
        print(f"  registers {registered}")
    print(f"\n{len(agents)} plugin agents, {len(skills)} skills — {len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1] if len(sys.argv) > 1 else ".")))
