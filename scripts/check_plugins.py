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
#: A fenced block in README — a layout listing, an install snippet, a usage example.
#: Matched non-greedily from one fence to the next so the gaps between blocks survive.
FENCED = re.compile(r"^```.*?^```", re.S | re.M)

#: How a role names a topic file an action loads on top of its always-loaded set.
#: Same literal as ``check_tool_grants`` and ``check_delegation_grants``: the
#: convention is a backticked path, not a markdown link.
REFERENCE_LINK = re.compile(r"`(reference/[\w.-]+\.md)`")

#: How a role names a file shape an action is told to *follow* (`templates/qa-plan.md`).
#: Read on that invocation exactly as a reference topic is, so it costs the same lines.
#: It names no tools, which is why the two grant gates stay on ``reference/`` alone:
#: load is a claim about bytes, authority is not, and the units do not coincide.
TEMPLATE_LINK = re.compile(r"`(templates/[\w.-]+\.md)`")

#: How a role names a file it loads *before* acting — an ordinary markdown link, read
#: from the preamble only. Shared with ``load_parts`` so the discovery surface this
#: file resolves and the surface ``check_companions`` holds in place are one literal.
PREAMBLE_LINK = re.compile(r"\]\(([^)]+\.md)\)")

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
    for link in PREAMBLE_LINK.findall(text.split("\n## ", 1)[0]):
        target = (path.parent / link).resolve()
        if (body := read(target)) is not None:
            parts.append((target, len(body.splitlines())))
    return parts


def named_parts(path: Path, pattern: re.Pattern, text: str, read) -> list[tuple[Path, str]]:
    """Every companion ``pattern`` names in ``text``, as ``(file, body)`` pairs.

    Bodies rather than line counts, because one caller needs the text back to
    search it: a companion can name a companion.
    """
    found = []
    for name in sorted(set(pattern.findall(text))):
        if (body := read(target := (path.parent / name).resolve())) is not None:
            found.append((target, body))
    return found


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

    **A template is named where its action's detail lives, which is not always this
    file.** Scanning the role alone made the template arm dead on the only role it
    was written for: `anantys.qa` names none of its three templates in `SKILL.md` —
    every mention sits in the `reference/` topic whose action follows it (`plan` in
    `reference/sources.md`, `init` in `reference/init.md`). And that is not an
    accident of style, it is this very check's remedy: splitting an over-ceiling role
    moves action detail into `reference/`, so the fix for the warning is what hides
    the template mention from a scan of the role file. The arm therefore switched off
    at exactly the load where it mattered — on the assembled queue `anantys.qa`
    reported 283 while its `plan` action reads 491, the 208-line `templates/qa-plan.md`
    uncharged, and unsplit `anantys.ops` was charged normally. So templates are
    discovered in the role **plus the topics it names**.

    Topic discovery stays one level deep: a `reference/` page naming another is a
    question ``check_tool_grants`` and ``check_delegation_grants`` answer the same way,
    and one gate must not widen alone. Nor is there a directory glob here — on the
    assembled queue every companion on disk is named, and the two grant gates already
    warn about a `reference/` file no action names.

    A floor, not an exact load: an action that reads two topic files pays for both.
    """
    text = read(path) or ""
    topics = named_parts(path, REFERENCE_LINK, text, read)
    templates = named_parts(
        path, TEMPLATE_LINK, "\n".join([text, *(body for _, body in topics)]), read
    )
    return [
        max(((p, len(b.splitlines())) for p, b in group), key=lambda part: part[1])
        for group in (topics, templates)
        if group
    ]


def measured_load(path: Path, read) -> list[tuple[Path, int]]:
    """Every file one action of ``path`` reads, worst case, as ``(file, lines)`` pairs."""
    return load_parts(path, read) + worst_action_part(path, read)


def named_companions(path: Path) -> list[str]:
    """Every companion path ``path`` names, as written — the surface ``measured_load`` resolves.

    Same three patterns, same two levels: the preamble's markdown links, the
    ``reference/`` topics the role names, and the ``templates/`` the role or one of
    those topics names. Returned as the written strings rather than resolved paths,
    because the question here is about a name that resolves to nothing.
    """
    text = disk(path) or ""
    topics = named_parts(path, REFERENCE_LINK, text, disk)
    return (
        PREAMBLE_LINK.findall(text.split("\n## ", 1)[0])
        + REFERENCE_LINK.findall(text)
        + TEMPLATE_LINK.findall("\n".join([text, *(body for _, body in topics)]))
    )


def check_companions(path: Path) -> None:
    """Error when a role names a companion file that is not in the tree.

    Every discovery path above resolves a name and moves on when the file is not
    there — ``load_parts`` and ``named_parts`` both skip a missing target silently.
    That makes *named but absent* indistinguishable from *not named*, and the two
    are opposite failures: one is a role that reads nothing where it says it reads a
    page, the other is a role with nothing to say.

    ``check_tool_grants`` has the same blind spot from the other end. It builds a
    skill's prose surface by globbing ``reference/*.md`` on disk and reporting the
    files no action names — so it cannot reach a name with no file at all, because
    the loop never visits one. Deleting a topic page and leaving its citation in
    ``SKILL.md`` passes all seven gates: the only output that moves is a *misdirected*
    warning, ``grants `AskUserQuestion` but the prose never mentions it``, naming the
    grant as the suspect when the real defect is that the page documenting the need
    is gone. Its remedy — drop the grant — removes a capability the role still uses.
    Citing a page that was never created at all produces no output anywhere.

    So the dangling direction belongs here, where the names are iterated, exactly as
    the orphan direction belongs there, where the files are. An error rather than a
    warning: a companion lives inside the role's own directory and arrives in the
    role's own change, so there is no other branch for it to be waiting on, and a
    role shipped with a dead citation is broken for the user who installs it
    whatever tree it came from. Across every open head today, zero citations dangle —
    this is a regression gate with live input, not one waiting for its input to land.

    Links a role writes *below* its first ``## `` heading are out of this surface, as
    they are out of ``measured_load``'s: widening discovery is a separate question,
    and ``check_tool_grants`` and ``check_delegation_grants`` answer it the same way
    this file does. One gate must not widen alone.
    """
    for name in sorted(set(named_companions(path))):
        if not (path.parent / name).is_file():
            errors.append(
                f"{rel(path)}: names `{name}`, which is not in the tree — an action "
                "told to read it reads nothing, and every check that resolves this "
                "path treats the absence as if the role had never named it"
            )


def check_load(path: Path) -> None:
    """Report a role whose worst-case *one-action load* exceeds the ceiling — and say who did it.

    An absolute total is the same number on every branch, so a warning phrased
    only as "loads N lines" says nothing about the change being reviewed: a commit
    that adds forty lines to an over-ceiling role and one that adds none report
    identically. That is how a queue of individually-clean changes walks a role
    past the ceiling without any single one of them being the branch that did it.

    So the load is also priced against ``BASE``, and the message names the delta.

    **The crossing is an error; the standing fact is a warning.** The baseline was
    added to separate those two, and for a while the separation changed only the
    wording. It should not: measured over the open queue, four branches each take a
    role that is *clean at the base* past the ceiling on their own — `anantys.design`
    115 -> 261 and 115 -> 221, `anantys.ops` 131 -> 204, 131 -> 213, 131 -> 238 — and
    ten more add to `anantys.qa`, already at 648, one of them by 253 lines. Every one
    of those runs exits 0. A ceiling nothing ever fails is a number in a docstring.

    The line between them is the one `check_contract_clauses` and `check_version_bump`
    already draw: a regression is an error, inherited debt is a warning. A crossing is
    a regression and it is **wholly inside the branch's own diff** — the role, its
    `reference/` pages and its `templates/` all arrive in the same change, so the
    remedy is available on that branch and there is no other branch to wait on. That
    is exactly the test ``check_companions`` used to earn its error. Growth above a
    ceiling the base already broke is not this branch's regression, so it stays a
    warning until the head that fixes the role lands; the gate then holds the result.

    **The floor is priced separately, because the remedy can be unreachable.** The
    remedy below moves detail into ``reference/``, and ``worst_action_part`` counts
    that directory — so past some size the advice is arithmetic nonsense: emptying
    the role file changes nothing. On the assembled queue `anantys.qa` is there, its
    companions alone at 698 (99 contract + 292 `reference/sources.md` + 307
    `templates/qa-plan.md`) against a 200 ceiling, up from 135 at the base. Its
    224-line `SKILL.md` is not the constraint and trimming it to zero still fails,
    yet the report advised a split into the directory that caused it — and filed it
    as a warning, because the *total* was already over at the base.

    That is the one case the crossing arm above gets backwards. "Inherited debt is a
    warning" is justified by *the head that fixes the role will land*; no head
    trimming a role can lower its floor, so there is nothing to wait on and the
    regression is wholly inside this diff — the error's own test. A floor the base
    already broke stays a warning on the same rule as before.
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
        "and whose clauses — labels and bodies both — `check_contract_clauses` holds "
        "in place, so shrinking it is not a route under this ceiling either"
    )
    base_parts = measured_load(path, lambda p: at(BASE, p)) if BASE else None
    before = sum(n for _, n in base_parts) if base_parts is not None else None

    # The floor is everything but the role file: the companions the remedy above
    # relocates *into*. Once it alone clears the ceiling the remedy is arithmetic
    # nonsense — emptying the role changes nothing — and the load has to come down
    # in the companions instead. A floor this diff pushed over is a regression no
    # later head trimming the role can undo, so it is an error even when the total
    # was already over; a floor the base already broke stays inherited debt.
    floor = total - dict(parts)[path]
    floor_before = sum(n for p, n in base_parts if p != path) if base_parts is not None else None
    floor_crossed = floor_before is not None and floor_before <= ROLE_MAX_LINES < floor
    unreachable = ""
    if floor > ROLE_MAX_LINES:
        delta = f", {floor_before} -> {floor}" if floor_crossed else ""
        unreachable = (
            f"emptying this file leaves {floor} lines (> {ROLE_MAX_LINES}) in companions "
            f"alone{delta}; "
        )
        remedy = (
            "relocating prose cannot reach this ceiling — the largest reference/ topic "
            "and the largest templates/ file are already counted, so what has to come "
            "down is the companions themselves, or the ceiling has to become a number "
            "some role in this tree can meet"
        )

    crossed = before is not None and before != total and before <= ROLE_MAX_LINES
    if before is None or before == total:
        change = f"loads {total} lines (> {ROLE_MAX_LINES})"
    elif crossed:
        change = f"this change pushes the load over the ceiling, {before} -> {total} (> {ROLE_MAX_LINES})"
    elif total > before:
        change = f"this change grows a load already over the ceiling, {before} -> {total} (+{total - before})"
    else:
        change = f"loads {total} lines (> {ROLE_MAX_LINES}), down from {before}"
    (errors if crossed or floor_crossed else warnings).append(
        f"{rel(path)}: {change} — {breakdown}; {unreachable}{remedy}"
    )


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


def clauses(text: str) -> dict[str, int]:
    """The contract's binding rules: each `## C<N>` label mapped to its body's size.

    The title after the dash is prose and may be reworded; the label is what the
    role files cite (`say so and stop (C2)`), so it is the identity.

    The count is what that identity is worth. A clause's force is the prose under
    the heading, and keying on the label alone left the prose unread: emptying every
    clause in place keeps the label set identical, so the gate below saw no change.
    """
    return {
        found.group(1): sum(1 for line in section.splitlines()[1:] if line.strip())
        for section in re.split(r"^## ", text, flags=re.MULTILINE)[1:]
        if (found := re.match(r"(C\d+)\b", section))
    }


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

    Holding the label set is not holding the contract, and the gap between the two
    is the same move again. On the queue as it assembles, this file is 99 lines and
    it is what puts `anantys.design` (221), `anantys.ops` (238) and
    `anantys.spec-tester` (204) over a 200 ceiling. Keep both headings, delete the
    95 lines under them: the clause set is identical, so the check above says
    nothing, and `check_load` goes from five warnings to one — *"loads 668 lines,
    down from 754"*. Relabelling one clause is an error; emptying every clause is
    reported as the roles getting better. The profitable edit was the quiet one.

    So an emptied clause is an error too — a clause is what it says, not the heading
    the role files cite. A shrink short of empty is a *warning*: content legitimately
    moves out of this file, and a gate whose remedy is "put the lines back" would
    forbid the split it asked for. It may not be silent, though, because the only
    other check that reads these lines reports losing them as an improvement.

    Adding a clause is how the contract grows, and a reworded title is not a changed
    rule — the label is the identity because the label is what the role files cite.
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
    was, now = clauses(before), clauses(here)
    if gone := sorted(set(was) - set(now)):
        errors.append(
            f"{rel(contract)}: {', '.join(gone)} present at the baseline and gone here — "
            "a clause the role files cite may not be dropped or relabelled silently; "
            "retire it by name in the same change that removes the citations"
        )
    # Keeping the label and deleting the prose under it is the drop above, taken the
    # one step that evades it: the set is unchanged, so nothing above fires, and every
    # role's load falls by the whole body at once. The role files still cite the label.
    if emptied := sorted(label for label, size in was.items() if size and not now.get(label, 1)):
        errors.append(
            f"{rel(contract)}: {', '.join(emptied)} kept the label and lost the body — "
            "a clause is what it says, not the heading the role files cite; retire it by "
            "name in the same change that removes the citations"
        )
    # Short of empty, a shrink is legitimate — content moves out, as the candidates
    # split did. It may not be *silent*, because `check_load` prices the same lines and
    # reports their loss as every role getting better: the queue's greenest possible
    # commit is the one that guts this file. So the delta is named where the clause is.
    thinned = [f"{c} {was[c]} -> {now[c]}" for c in sorted(now) if 0 < now[c] < was.get(c, 0)]
    if thinned:
        warnings.append(
            f"{rel(contract)}: {', '.join(thinned)} lost body lines — the roles that link "
            "this file all load less as a result, so `check_load` reports the loss as an "
            "improvement; say in the change what moved out of the clause and where it went"
        )


def require(path: Path, fm: dict[str, str], keys: tuple[str, ...], expected_name: str) -> None:
    for key in keys:
        if not fm.get(key):
            errors.append(f"{rel(path)}: frontmatter is missing `{key}`")
    if fm.get("name", expected_name) != expected_name:
        errors.append(f"{rel(path)}: frontmatter name `{fm['name']}` != `{expected_name}`")


def check_unlisted(marketplace: dict) -> None:
    """Error on a plugin tree the catalog does not point at.

    Every check here hangs off ``for entry in marketplace["plugins"]`` — the catalog
    is the only thing that discovers a tree to check, so it is also the only thing
    that can hide one. Delete an entry and the role sizes, the frontmatter, the
    contract links, the description counts and the README mentions all go quiet for
    that tree in a single JSON edit, while its files stay in the repo and stay
    installable by path. Deleting the last entry takes every invariant in this file
    with it and still exits 0.

    Deleting an entry *and* its tree is a legitimate removal and stays silent: there
    is nothing left to govern. Deleting only the entry is the case this names.
    """
    listed = {(ROOT / entry["source"]).resolve() for entry in marketplace["plugins"]}
    for manifest_path in sorted(ROOT.glob("**/.claude-plugin/plugin.json")):
        if manifest_path.parent.parent not in listed:
            errors.append(
                f"{rel(manifest_path)}: no marketplace.json entry points at this tree. "
                f"Every check here iterates the catalog, so an unlisted plugin is "
                f"governed by nothing while staying installable — list it, or delete it."
            )


def main() -> int:
    global BASE
    BASE = merge_base()
    marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
    check_unlisted(marketplace)

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
            check_companions(skill)
            check_load(skill)

        for agent in agents:
            require(agent, frontmatter(agent), ("name", "description", "tools", "model"), agent.stem)
            if contract:
                check_contract(agent, contract)
            check_companions(agent)
            check_load(agent)

        # The description advertises counts ("5 skills … 2 review agents") to users browsing
        # the marketplace, and nothing keeps them true when a role is added.
        for actual, noun in ((len(skills), "skills"), (len(agents), "agents")):
            claimed = re.search(rf"(\d+)\s+(?:\w+\s+)?{noun}", entry["description"])
            if claimed and int(claimed.group(1)) != actual:
                errors.append(
                    f"description claims {claimed.group(1)} {noun}, tree has {actual}"
                )

        # README is the only place a user reads before installing — so the mention has
        # to be prose. Tested over the whole file, the "Repository layout" block named
        # every role's path, and that listing alone satisfied all seven: the role table,
        # the only text that says what a role *does*, deleted with zero errors, and a
        # new role joined the user-facing surface on one line of ASCII tree. Same unit
        # mismatch as the ceiling above — the reason says "reads", the measurement
        # accepted "appears". Fenced blocks are not read; drop them first.
        raw_readme = (ROOT / "README.md").read_text(encoding="utf-8")
        readme = FENCED.sub("", raw_readme)
        for name in [d.name for d in skills] + [a.stem for a in agents]:
            if name not in readme:
                errors.append(f"README.md does not describe `{name}` outside a code block")

        # One fenced block is not like the others. The install snippet is the only text
        # in this repo a user *executes*, and both names in it are names this check
        # already reads for the drift test. The strip above was justified by "fenced
        # blocks are not read" — true of the layout listing, false of this one. So:
        # renaming the catalog in both manifests kept drift satisfied and killed the
        # command at 0 errors; deleting the Install section outright, 0 errors; pointing
        # it at a plugin and a marketplace that exist nowhere, 0 errors. Read the fences
        # back in for this one question. The `marketplace add <owner>/<repo>` line above
        # it stays unchecked: the repo slug is in no manifest, so the tree cannot answer.
        if market := marketplace.get("name"):
            target = f"{manifest['name']}@{market}"
            if not re.search(rf"/plugin\s+install\s+{re.escape(target)}(?!\S)", raw_readme):
                errors.append(
                    f"README.md has no `/plugin install {target}` — the install snippet "
                    "is the one text a user runs, and nothing else gates its names"
                )
        else:
            warnings.append(
                "marketplace.json has no `name`, so the `@<marketplace>` half of the "
                "`/plugin install` line in README.md went unmeasured"
            )

    for warning in warnings:
        print(f"warning: {warning}")
    for error in errors:
        print(f"error: {error}")
    print(f"{len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
