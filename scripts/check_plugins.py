#!/usr/bin/env python3
"""Validate the marketplace against what the plugin tree actually contains.

Nothing here is a style opinion: every check below is an invariant that, when
broken, ships a marketplace a user cannot install or a catalog that lies about
its contents. Run it with no arguments from anywhere in the repo.

Exit 0 = clean (warnings allowed), 1 = at least one error.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROLE_MAX_LINES = 200  # see docs/adding-a-role.md — a role loads in full, every invocation
CONTRACT = "TEAM-CONTRACT.md"  # the rules every role in a plugin shares; each must link it

#: How a role names a topic file an action loads on top of its always-loaded set.
#: Same literal as ``check_tool_grants`` and ``check_delegation_grants``: the
#: convention is a backticked path, not a markdown link.
REFERENCE_LINK = re.compile(r"`(reference/[\w.-]+\.md)`")

#: How a role names a file shape an action is told to *follow* (`templates/qa-plan.md`).
#: Read on that invocation exactly as a reference topic is, so it costs the same lines.
#: It names no tools, which is why the two grant gates stay on ``reference/`` alone:
#: load is a claim about bytes, authority is not, and the units do not coincide.
TEMPLATE_LINK = re.compile(r"`(templates/[\w.-]+\.md)`")

#: Commit the working tree departs from, so a load can be reported as a *change*
#: rather than as a standing fact. ``None`` = no baseline available; see ``merge_base``.
BASE: str | None = None

errors: list[str] = []
warnings: list[str] = []


def frontmatter(path: Path) -> dict[str, str]:
    """Top-level `key: value` pairs of a YAML frontmatter block. Values stay raw strings."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        errors.append(f"{rel(path)}: missing YAML frontmatter")
        return {}
    _, block, _ = text.split("---\n", 2)
    return dict(
        (line.partition(":")[0].strip(), line.partition(":")[2].strip())
        for line in block.splitlines()
        if line[:1].isalpha() and ":" in line
    )


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def merge_base() -> str | None:
    """The commit the working tree departs from, or ``None`` when git cannot say.

    Absence of a baseline is not a pass: ``check_load`` keeps its absolute warning
    and only loses the ability to attribute growth to the change under review.
    """
    for ref in ("origin/main", "main"):
        try:
            done = subprocess.run(
                ["git", "merge-base", "HEAD", ref],
                cwd=ROOT, capture_output=True, text=True, timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if done.returncode == 0 and done.stdout.strip():
            return done.stdout.strip()
    return None


def at(commit: str, path: Path) -> str | None:
    """``path``'s content at ``commit``, or ``None`` when it was not there."""
    done = subprocess.run(
        ["git", "show", f"{commit}:{rel(path)}"],
        cwd=ROOT, capture_output=True, text=True,
    )
    return done.stdout if done.returncode == 0 else None


def disk(path: Path) -> str | None:
    """``path``'s content in the working tree, or ``None`` when it is not there."""
    return path.read_text(encoding="utf-8") if path.is_file() else None


def load_parts(path: Path, read) -> list[tuple[Path, int]]:
    """What a role loads before its first action, as ``(file, lines)`` pairs.

    The role file itself, plus every local `.md` its *preamble* links — everything
    above the first `## ` heading is where a role names what binds it before it
    acts, and those files are read on the same invocation.

    Discovered from the links, never from a filename, so a role that points
    somewhere else is measured against what it actually points at. ``read`` decides
    *which tree* is measured, which is what lets the same rule price a baseline.
    """
    text = read(path)
    if text is None:
        return []
    parts = [(path, len(text.splitlines()))]
    for link in re.findall(r"\]\(([^)]+\.md)\)", text.split("\n## ", 1)[0]):
        target = (path.parent / link).resolve()
        if (body := read(target)) is not None:
            parts.append((target, len(body.splitlines())))
    return parts


def worst_action_part(path: Path, read) -> list[tuple[Path, int]]:
    """The largest companion file per companion directory, as ``(file, lines)`` pairs.

    ``check_load``'s own remedy is to move detail into ``reference/``, so that
    directory is where a role's load *goes* — measuring the always-loaded set alone
    would make the remedy a way to satisfy the ceiling without lowering the load.
    An action reads one topic file on top of that set and the ceiling is a worst-case
    bound, so the largest named file is the part that counts.

    ``templates/`` is the second such directory and was the hole in that argument.
    The ceiling's stated reason is that *the role loads in full, every invocation*;
    a template an action is told to follow satisfies that reason exactly, and nothing
    priced it. `anantys.qa`'s plan action is told to follow a 229-line template —
    longer than the whole ceiling — while the gate reported the role at 513. Any
    directory whose files an action reads is a place the prose can go, so the escape
    is closed by directory, not by file: a template is charged like a topic.

    One per directory, summed: an action reads at most one topic and at most one
    template, but it can read both, so maxing across the union would understate it.

    ``check_tool_grants`` and ``check_delegation_grants`` read ``reference/`` only,
    and deliberately — a template names no tools, so it grants nothing to union.

    A floor, not an exact load: an action that reads two topic files pays for both.
    """
    text = read(path) or ""
    parts = []
    for pattern in (REFERENCE_LINK, TEMPLATE_LINK):
        sized = []
        for name in sorted(set(pattern.findall(text))):
            if (body := read(target := (path.parent / name).resolve())) is not None:
                sized.append((target, len(body.splitlines())))
        if sized:
            parts.append(max(sized, key=lambda part: part[1]))
    return parts


def measured_load(path: Path, read) -> list[tuple[Path, int]]:
    """Every file one action of ``path`` reads, worst case, as ``(file, lines)`` pairs."""
    return load_parts(path, read) + worst_action_part(path, read)


def check_load(path: Path) -> None:
    """Warn when a role's worst-case *one-action load* exceeds the ceiling — and say who did it.

    An absolute total is the same number on every branch, so a warning phrased
    only as "loads N lines" says nothing about the change being reviewed: a commit
    that adds forty lines to an over-ceiling role and one that adds none report
    identically. That is how a queue of individually-clean changes walks a role
    past the ceiling without any single one of them being the branch that did it.

    So the load is also priced against ``BASE``, and the warning names the delta.
    """
    parts = measured_load(path, disk)
    total = sum(n for _, n in parts)
    if total <= ROLE_MAX_LINES:
        return

    breakdown = " + ".join(f"{n} {rel(p)}" for p, n in parts)
    remedy = (
        "split detail a given action does not need into reference/ topic files — the "
        "largest reference/ and the largest templates/ the role names are counted too, "
        "so one big topic file, or a template carrying the prose, relocates the load "
        f"without lowering it; never into the {CONTRACT}, whose lines every role pays "
        "and whose clauses `check_contract_clauses` holds in place"
    )
    before = sum(n for _, n in measured_load(path, lambda p: at(BASE, p))) if BASE else None

    if before is None or before == total:
        change = f"loads {total} lines (> {ROLE_MAX_LINES})"
    elif before <= ROLE_MAX_LINES:
        change = f"this change pushes the load over the ceiling, {before} -> {total} (> {ROLE_MAX_LINES})"
    elif total > before:
        change = f"this change grows a load already over the ceiling, {before} -> {total} (+{total - before})"
    else:
        change = f"loads {total} lines (> {ROLE_MAX_LINES}), down from {before}"
    warnings.append(f"{rel(path)}: {change} — {breakdown}; {remedy}")


def check_contract(path: Path, contract: Path) -> None:
    """Error when a role's preamble does not link the contract that claims to bind it.

    ``TEAM-CONTRACT.md`` opens *"Rules that bind every role in this plugin"*, *"Every
    role file points here"* and *"This file is loaded before every action of every
    role"*. Those are three assertions about the tree, and nothing checked any of
    them — the binding was a convention that happened to hold.

    Worse, the one check that read the link read it as a cost. The contract counts
    toward ``check_load``'s ceiling, so the five roles that point at it load 207-723
    against a 200 limit; deleting the single line that binds them takes three of
    those under the ceiling and the run stays green. The cheapest way to satisfy the
    ceiling was to stop being bound. A ceiling may make a role shorter; it may not
    make it unbound.
    """
    if contract not in [p for p, _ in load_parts(path, disk)]:
        errors.append(
            f"{rel(path)}: preamble does not link {CONTRACT} — a role names what binds "
            "it above its first `## ` heading, where it is read before the role acts"
        )


def clauses(text: str) -> set[str]:
    """The contract's binding rules, keyed by their `## C<N>` label.

    The title after the dash is prose and may be reworded; the label is what the
    role files cite (`say so and stop (C2)`), so it is the identity.
    """
    return set(re.findall(r"^## (C\d+)\b", text, re.MULTILINE))


def check_contract_clauses(contract: Path) -> None:
    """Error when a clause that existed at ``BASE`` is no longer in the contract.

    ``check_contract`` guarantees that every role *links* this file. Nothing read
    what the file then says — and ``check_load``'s remedy pointed at that guarantee
    as if it covered the content: *"never into the TEAM-CONTRACT.md, which
    `check_contract` requires"*. A reader following that line concludes the contract
    is held in place. It was not: renaming `## C2 — A stop is a result` to anything
    else left 0 errors, the same warning count, and 227 passing tests.

    That is the inverse of the hole ``check_contract`` closed. There, the cheapest
    way to satisfy the ceiling was for a role to stop being bound; here it is for
    the contract to stop binding, which takes *every* role under the ceiling at once
    and is invisible in both the error list and the warning list.

    Only deletion is an error. Adding a clause is how the contract grows, and a
    reworded title is not a changed rule — the label is the identity because the
    label is what the role files cite.
    """
    if BASE is None:
        warnings.append(
            f"{rel(contract)}: no baseline, so no clause deletion is checked — "
            "the absolute content of the contract is not something this check can price"
        )
        return
    before = at(BASE, contract)
    here = disk(contract)
    if before is None:
        # The contract arrives on the branch under review, or is nowhere yet — either
        # way there is no clause set to lose, and saying nothing here is how this check
        # would ship inert. The contract is added by one open head, so for the whole
        # queue before it lands this is the only branch the check takes; a silent one is
        # a check reporting health it never measured, which is the gap it closes.
        state = "new at the baseline" if here is not None else "not in this tree"
        warnings.append(
            f"{rel(contract)}: {state}, so no clause deletion is checked — "
            "this check only has a clause set to protect once the contract is on main"
        )
        return
    if here is None:
        # Deleting the file is the same move as relabelling a clause, taken to its
        # limit: it drops every clause at once. It is also the profitable one, because
        # the contract's lines are what put the roles over `check_load`'s ceiling, so
        # the deletion that unbinds all of them is the edit that makes them all clean.
        errors.append(
            f"{rel(contract)}: present at the baseline and gone here — deleting the "
            "contract unbinds every role at once; retire it by name in the same change "
            "that removes the citations"
        )
        return
    if gone := sorted(clauses(before) - clauses(here)):
        errors.append(
            f"{rel(contract)}: {', '.join(gone)} present at the baseline and gone here — "
            "a clause the role files cite may not be dropped or relabelled silently; "
            "retire it by name in the same change that removes the citations"
        )


def require(path: Path, fm: dict[str, str], keys: tuple[str, ...], expected_name: str) -> None:
    for key in keys:
        if not fm.get(key):
            errors.append(f"{rel(path)}: frontmatter is missing `{key}`")
    if fm.get("name", expected_name) != expected_name:
        errors.append(f"{rel(path)}: frontmatter name `{fm['name']}` != `{expected_name}`")


def main() -> int:
    global BASE
    BASE = merge_base()
    marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())

    for entry in marketplace["plugins"]:
        plugin_dir = (ROOT / entry["source"]).resolve()
        manifest_path = plugin_dir / ".claude-plugin/plugin.json"
        if not manifest_path.exists():
            errors.append(f"marketplace.json: source `{entry['source']}` has no plugin.json")
            continue
        manifest = json.loads(manifest_path.read_text())

        # The catalog is a copy of the manifest; a stale copy installs the wrong version.
        for field in ("name", "version", "description"):
            if entry[field] != manifest[field]:
                errors.append(
                    f"{field} drift: marketplace.json has {entry[field]!r}, "
                    f"{rel(manifest_path)} has {manifest[field]!r}"
                )

        skills = sorted(p for p in (plugin_dir / "skills").iterdir() if p.is_dir())
        agents = sorted((plugin_dir / "agents").glob("*.md"))

        # An absent contract is not an error *by itself*: the file is one some other
        # change lands, and a gate that reddens every branch until it arrives forces an
        # order on changes that have none. Whether this absence is that one is a question
        # about the baseline, which is `check_contract_clauses`'s subject — so absence is
        # routed into it rather than short-circuited around it. Deciding here, where the
        # baseline is not read, is what let a deletion pass as a not-landed-yet file.
        contract = plugin_dir / CONTRACT
        check_contract_clauses(contract)
        if not contract.is_file():
            contract = None  # no file, so no role can link it; checked once, above

        for skill_dir in skills:
            skill = skill_dir / "SKILL.md"
            if not skill.exists():
                errors.append(f"{rel(skill_dir)}: no SKILL.md")
                continue
            require(skill, frontmatter(skill), ("name", "description"), skill_dir.name)
            if contract:
                check_contract(skill, contract)
            check_load(skill)

        for agent in agents:
            require(agent, frontmatter(agent), ("name", "description", "tools", "model"), agent.stem)
            if contract:
                check_contract(agent, contract)
            check_load(agent)

        # The description advertises counts ("5 skills … 2 review agents") to users browsing
        # the marketplace, and nothing keeps them true when a role is added.
        for actual, noun in ((len(skills), "skills"), (len(agents), "agents")):
            claimed = re.search(rf"(\d+)\s+(?:\w+\s+)?{noun}", entry["description"])
            if claimed and int(claimed.group(1)) != actual:
                errors.append(
                    f"description claims {claimed.group(1)} {noun}, tree has {actual}"
                )

        # README is the only place a user reads before installing.
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for name in [d.name for d in skills] + [a.stem for a in agents]:
            if name not in readme:
                errors.append(f"README.md does not mention `{name}`")

    for warning in warnings:
        print(f"warning: {warning}")
    for error in errors:
        print(f"error: {error}")
    print(f"{len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
