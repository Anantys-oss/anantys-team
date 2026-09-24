#!/usr/bin/env python3
"""Check that dispatching an agent does not silently widen a skill's grants.

`allowed-tools` reads like a capability ceiling. It is not one. A skill that
holds `Task` and names an agent in its prose gains, for the length of that
dispatch, everything the agent's own `tools:` list holds — and nothing in the
skill's frontmatter says so. The human auditing the skill sees the narrow list.

So a role's *effective* grant set is the union of its own and every agent it
dispatches. This script computes that union and fails when it exceeds what the
role declares. There is deliberately no suppression flag: the three honest
resolutions are to narrow the agent, widen the skill's declared list so the
capability is visible, or stop dispatching.

Usage: python3 scripts/check_delegation_grants.py [root]
Exit 1 on errors, 0 on warnings only.
"""

import re
import sys
from pathlib import Path

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.S)


def parse(path):
    """Return (name, grants, body), or None when the file has no frontmatter."""
    m = FRONTMATTER.match(path.read_text(encoding="utf-8"))
    if not m:
        return None
    name, field = path.stem, None
    for line in m.group(1).splitlines():
        if line.startswith("name:"):
            name = line.split(":", 1)[1].strip()
        elif line.startswith(("allowed-tools:", "tools:")):
            field = line.split(":", 1)[1].strip()
    # agents write tools: ["Bash", "Read"]; skills write a bare comma list
    grants = {g.strip().strip('"[]') for g in (field or "").split(",")}
    return name, grants - {""}, m.group(2)


def covers(grants, needed):
    """Is `needed` within `grants`? `Bash` subsumes any `Bash(...)` form."""
    if needed in grants:
        return True
    return needed.startswith("Bash(") and "Bash" in grants


def check(skills, agents):
    errors, warnings = [], []
    dispatched = set()

    for name, grants, body in skills:
        for agent, agent_grants in sorted(agents.items()):
            if f"`{agent}`" not in body:
                continue
            dispatched.add(agent)
            if "Task" not in grants:
                errors.append(
                    f"{name}: dispatches `{agent}` but has no Task grant — "
                    f"the prose describes a step the skill cannot take"
                )
            escalation = sorted(g for g in agent_grants if not covers(grants, g))
            if escalation:
                errors.append(
                    f"{name}: dispatching `{agent}` grants it {', '.join(escalation)}, "
                    f"which {name} does not declare — narrow the agent, declare the "
                    f"capability, or drop the dispatch"
                )

    for agent in sorted(set(agents) - dispatched):
        warnings.append(f"{agent}: shipped but no skill dispatches it — reachable only by name")

    return errors, warnings


def main(root):
    skills, agents = [], {}
    for path in sorted(root.glob("plugins/*/skills/*/SKILL.md")):
        if parsed := parse(path):
            skills.append(parsed)
    for path in sorted(root.glob("plugins/*/agents/*.md")):
        if parsed := parse(path):
            agents[parsed[0]] = parsed[1]

    if not skills and not agents:
        print(f"no roles found under {root}", file=sys.stderr)
        return 1

    errors, warnings = check(skills, agents)
    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    print(f"\n{len(skills)} skills, {len(agents)} agents — {len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1] if len(sys.argv) > 1 else ".")))
