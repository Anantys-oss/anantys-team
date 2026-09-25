#!/usr/bin/env python3
"""Check that dispatching an agent does not silently widen a skill's grants.

`allowed-tools` reads like a capability ceiling. It is not one. A skill that
holds `Task` and names an agent in its prose gains, for the length of that
dispatch, everything the agent's own `tools:` list holds — and nothing in the
skill's frontmatter says so. The human auditing the skill sees the narrow list.

So a role's *effective* grant set is the union of its own and every agent it
dispatches. This script computes that union and fails when it exceeds what the
role declares. There is deliberately no suppression flag: the honest resolutions
are to narrow the agent, widen the skill's declared list so the capability is
visible, stop dispatching — or *recommend* the run instead of performing it, and
say so where the agent is named. A skill that tells the human "run `X` yourself,
I will not" never holds X's grants, so pointing at an agent is not the same act
as invoking one. Naming an agent still counts as a dispatch by default; only an
explicit, machine-readable disclaimer in the same block downgrades it, which is
documentation rather than a way to silence the check.

Usage: python3 scripts/check_delegation_grants.py [root]
Exit 1 on errors, 0 on warnings only.
"""

import re
import sys
from pathlib import Path

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.S)
# "you do not dispatch it", "never invoke `x`" — the prose declining the dispatch
DECLINED = re.compile(r"\b(?:do(?:es)?\s+not|don'?t|never|rather\s+than)\s+\w*\s*"
                      r"(?:dispatch|invoke|launch|delegate|run)", re.I)
# a markdown block: paragraph, bullet, or numbered step — the unit a disclaimer scopes to
BLOCK = re.compile(r"\n\s*\n|\n(?=\s*(?:[-*+]\s|\d+\.\s))")


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
        blocks = BLOCK.split(body)
        for agent, agent_grants in sorted(agents.items()):
            named = [b for b in blocks if f"`{agent}`" in b]
            if not named:
                continue
            dispatched.add(agent)
            if all(DECLINED.search(b) for b in named):
                continue  # recommended to the human, not run by the skill
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
                    f"capability, drop the dispatch, or state in that block that the "
                    f"skill does not dispatch it and only recommends the run"
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
