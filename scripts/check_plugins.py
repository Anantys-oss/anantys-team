#!/usr/bin/env python3
"""Validate the marketplace against what the plugin tree actually contains.

Nothing here is a style opinion: every check below is an invariant that, when
broken, ships a marketplace a user cannot install or a catalog that lies about
its contents. Run it with no arguments from anywhere in the repo.

Exit 0 = clean (warnings allowed), 1 = at least one error.
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = "TEAM-CONTRACT.md"  # the rules every role in a plugin shares; each must link it

#: Tokens every session pays for having the plugin enabled, whether or not a role
#: is ever invoked — the sum of the per-component always-on column. The only
#: non-optional cost the plugin imposes, so the only one with a tight ceiling:
#: seven roles measure 716, and this leaves room for roughly three more.
ALWAYS_ON_MAX = 1_000
#: Tokens one role's body costs on the invocation that fires it. Paid once per
#: campaign rather than once per session, so the ceiling is loose — it bounds the
#: preamble a role spends before doing any work. Six roles measure 820-2.1k;
#: `anantys.qa` measures 8.6k and is the only one this number is about.
#: Loose per branch, not per queue: that 8.6k is 72% of the ceiling already spent,
#: twelve open heads append to the same file, and two of them pass alone and are
#: 14.7k together. Which one gets the error is decided by merge order, so the fold
#: has to be priced in this column too — see `docs/landing-the-queue.md`.
ON_INVOKE_MAX = 12_000
#: `Always-on:   ~716 tok   added to every session`
#: A cost under the loader's reporting floor prints as `< 20` rather than `~N`, so
#: both forms are accepted and `< 20` is read as its own upper bound — the alternative
#: is a row this gate silently skips, which is the failure mode it exists to replace.
LOADER_TOTAL = re.compile(r"^\s*Always-on:\s+[~<] ?([\d.,k]+) tok", re.M)
#: `  anantys.qa                 ~190      ~8.6k` — component, always-on, on-invoke.
#: The `component  always-on  on-invoke` header carries neither marker, so it is not a row.
#: Both capture digits rather than non-space, so a count this gate cannot read fails to
#: match and is reported as a changed table shape — never passed to ``tokens`` to crash on.
LOADER_ROW = re.compile(r"^ +(\S+) +[~<] ?([\d.,k]+) +[~<] ?([\d.,k]+)$", re.M)
#: A fenced block in README — a layout listing, an install snippet, a usage example.
#: Matched non-greedily from one fence to the next so the gaps between blocks survive.
FENCED = re.compile(r"^```.*?^```", re.S | re.M)

#: How a role names a topic file an action loads on top of its always-loaded set.
#: Same literal as ``check_tool_grants`` and ``check_delegation_grants``: the
#: convention is a backticked path, not a markdown link.
REFERENCE_LINK = re.compile(r"`(reference/[\w.-]+\.md)`")

#: How a role names a file shape an action is told to *follow* (`templates/qa-plan.md`).
#: Read on that invocation exactly as a reference topic is — and, exactly as a
#: reference topic is, charged to that action alone and to no token budget the loader
#: reports. It names no tools, which is why the two grant gates stay on ``reference/``
#: alone: the question there is authority, and these files carry a file shape.
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

    ``None`` is not a pass: every check that reads it reports its standing finding
    and only loses the ability to attribute a change to the branch under review.
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


def named_companions(path: Path) -> list[str]:
    """Every companion path ``path`` names, as written — the surface this file resolves.

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
    they are out of ``named_companions``'s: widening discovery is a separate question,
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


def loader_details(plugin_dir: Path, name: str) -> str | None:
    """`claude plugin details` for the plugin at ``plugin_dir``, or ``None`` if it cannot run.

    The cost table is produced by tokenizing the tree, not by calling the API: it
    needs no credential and no network, which is what makes it usable as a gate.
    ``None`` when the CLI is absent or fails — a gate that cannot measure must not
    rule, so the caller warns instead.
    """
    try:
        done = subprocess.run(
            ["claude", "--plugin-dir", str(plugin_dir), "plugin", "details", name],
            cwd=plugin_dir, capture_output=True, text=True, timeout=180,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def baseline_details(plugin_dir: Path, name: str) -> str | None:
    """The same cost table at ``BASE``, or ``None`` when it cannot be measured.

    ``at`` is no help here: the loader prices a *tree*, so the baseline has to be
    materialised as one. ``git archive`` writes the plugin directory as it stood at
    the merge base and the loader reads it there — tokenized locally, same as the
    working tree's table, so this costs one more CLI run and no credential.

    ``None`` on any failure, including ``BASE is None``. The caller treats that as
    "no baseline", which keeps the pre-baseline behaviour: every crossing is this
    branch's until something can say otherwise.
    """
    if BASE is None:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "base.tar"
        try:
            done = subprocess.run(
                ["git", "archive", "--output", str(archive), BASE, "--", rel(plugin_dir)],
                cwd=ROOT, capture_output=True, text=True, timeout=60,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if done.returncode != 0:
            return None
        try:
            shutil.unpack_archive(archive, tmp)
        except (ValueError, OSError):
            return None
        return loader_details(Path(tmp) / rel(plugin_dir), name)


def tokens(printed: str) -> int:
    """`190` -> 190, `8.6k` -> 8600, `1,736` -> 1736. The loader rounds; so does this.

    Three notations in one column: the thousands separator appears once a count has
    four digits, and the `k` suffix once the loader stops printing them exactly.
    """
    bare = printed.replace(",", "").rstrip("k")
    return round(float(bare) * (1000 if printed.endswith("k") else 1))


def crossing(finding: str, now: int, before: int | None, limit: int) -> None:
    """File ``finding`` as an error when this branch moved ``now`` past ``limit``.

    ``before`` is the same number at the merge base, or ``None`` when no baseline
    could be measured. The split is the one `require`, `check_contract_clauses` and
    `check_version_bump` draw — severity is remedy locality — and the condition for a
    warning is both halves together: the baseline was *already* over, **and** this
    branch did not raise it. A branch that pushes an already-red number further owns
    the lines it added; a branch that only inherits the number owns nothing, and a
    branch that lowered it but not enough has already done the only thing it can.

    On a push to the default branch the merge base is HEAD, so ``now == before`` and a
    standing overflow warns rather than failing the build. That is the same thing
    `require` does there and for the same reason: there is no branch to fix it in.
    """
    if before is not None and before > limit and now <= before:
        verb = "the same" if now == before else f"lower than the baseline's {before}"
        warnings.append(
            f"{finding} — over at the baseline too and {verb} here, so the crossing is "
            "not this branch's to fix"
        )
    else:
        errors.append(finding)


def check_cost(plugin_dir: Path, name: str, details: str | None, base: str | None = None) -> None:
    """Error when *this branch* puts a plugin over one of the loader's two budgets.

    This replaces a 200-**line** ceiling over a role's "worst-case one-action load"
    — the role file, its preamble links, the largest `reference/` topic it names and
    the largest `templates/` file — justified by *a role loads in full, every
    invocation*. Nine rounds of work refined which arm of that ceiling was an error,
    who owned the remedy, and whether the shared contract's lines were attributable.
    None of them measured the premise. `claude plugin details` does, and it says:

    - A role's **body** is charged **on invoke**, not always-on. Appending 4000 lines
      to `anantys.debug/SKILL.md` moves its on-invoke cost 950 -> 73k and its
      always-on cost **not at all**; the plugin total stays 716. Always-on is the
      frontmatter `description`, which is what the loader shows the model when it is
      deciding whether to fire the skill.
    - A **companion** is charged **nothing**. A 4000-line `reference/huge.md`, named
      in the role's own prose, moves neither column by a token. The old gate counted
      it in full.

    So the ceiling was in the wrong currency *and* over the wrong population, and the
    paradox a previous round reported — that the remedy, *move detail into
    `reference/`*, pointed into a directory the gate itself charged, making the advice
    arithmetic nonsense for the one role it was written for — was an artifact of the
    accounting rather than a property of the tree. Against the loader the remedy works
    exactly as intended: prose only the `plan` action needs, read by that action alone,
    is not paid by `run` or `report`. That is progressive disclosure, and it is the
    design the platform intends — not a hole to be closed by charging for it.

    Two budgets, because the loader bills in two currencies and they are not fungible:

    - ``ALWAYS_ON_MAX`` over the plugin's **total**. Every session with the plugin
      enabled pays this whether or not it ever invokes a role, so it is the only truly
      non-optional cost — and it is a *plugin*-level number, not a role-level one: no
      single role's description is the problem, the sum is. Reported against the whole
      plugin for that reason.
    - ``ON_INVOKE_MAX`` per **component**. Paid once by the session that fires the
      role, against which a campaign's own token spend is far larger. Loose, and it
      bounds one thing: the preamble a role charges before doing any work.

    Both are errors on the test the rest of this file uses — the remedy is wholly
    inside the branch's own diff — **when the branch is what moved them**, which is
    why ``base`` is read. The argument that retired the baseline here was that a
    description and a role body are the role's own files, so there is no other branch
    to wait on. That is a claim about who owns a *file*, and the budgets are not
    file-shaped:

    - Always-on is a **sum over every role**, as the bullet above says in as many
      words. Seven descriptions in seven files, arriving in up to seven changes. It is
      the shared-cost shape the old line ceiling needed its inherited-debt arm for; the
      arm was dropped because the *contract* is in neither column, which identified the
      wrong thing as the shared cost. The other six descriptions are the shared cost.
    - On-invoke is per component, but a branch that never opens ``anantys.qa/SKILL.md``
      is still handed its row. Role-local is not branch-local.

    Measured on the queue this gate ships into: two of the open heads price at 1,034
    always-on against a 1,000 ceiling, and one prices ``anantys.qa`` at 12.8k against
    12,000. Without the baseline, the first of those to merge reddens every one of the
    other heads for a number it did not move — and hands each of them a remedy
    (*shorten those descriptions*, *move detail into `reference/`*) in files it does
    not own. That is the order-forcing this file refuses everywhere else.
    """
    if details is None:
        warnings.append(
            f"{name}: `claude plugin details` did not run, so neither token budget was "
            "checked — install the Claude Code CLI to measure the cost the loader "
            "actually charges (it needs no credential: the table is tokenized locally)"
        )
        return

    if not (total := LOADER_TOTAL.search(details)):
        errors.append(
            f"{name}: `claude plugin details` printed no always-on total — this gate "
            "reads the CLI's cost table and the table's shape has changed"
        )
        return

    # A baseline whose own table this gate cannot read attributes nothing, and must not
    # be mistaken for a baseline that measured 0: `None` means "no baseline".
    base_total = LOADER_TOTAL.search(base) if base else None
    was = {c: tokens(oi) for c, _, oi in LOADER_ROW.findall(base or "")}

    if (always_on := tokens(total.group(1))) > ALWAYS_ON_MAX:
        crossing(
            f"{name}: {always_on} always-on tokens (> {ALWAYS_ON_MAX}) — every session "
            "with this plugin enabled pays them before invoking anything; the column is "
            "the roles' frontmatter `description`s, so what has to shorten is those, or "
            "the plugin has fewer roles",
            always_on,
            tokens(base_total.group(1)) if base_total else None,
            ALWAYS_ON_MAX,
        )

    for component, _, on_invoke in LOADER_ROW.findall(details):
        if (cost := tokens(on_invoke)) > ON_INVOKE_MAX:
            crossing(
                f"{component}: {cost} tokens on invoke (> {ON_INVOKE_MAX}) — move detail "
                "a given action does not need into `reference/` topic files, which the "
                "loader charges only to the action that reads them, and this column not "
                "at all",
                cost,
                # A component the baseline did not have is new here, so it is this
                # branch's — absent from `was` must not read as "was 0 and is over now"
                # by way of a default that happens to be under the limit.
                was.get(component),
                ON_INVOKE_MAX,
            )


def check_contract(path: Path, contract: Path) -> None:
    """Error when a role's preamble does not link the contract that claims to bind it.

    ``TEAM-CONTRACT.md`` opens *"Rules that bind every role in this plugin"*, *"Every
    role file points here"* and *"This file is loaded before every action of every
    role"*. Those are three assertions about the tree, and nothing checked any of
    them — the binding was a convention that happened to hold.

    Worse, the one check that read the link read it as a cost: the retired line
    ceiling counted the contract into every role that pointed at it, so deleting the
    single line that bound a role took it under the ceiling and the run stayed green.
    The cheapest way to satisfy that ceiling was to stop being bound. ``check_cost``
    does not charge the contract — the loader does not load it — so that incentive is
    gone and this gate no longer stands on it. It stands on the first paragraph: the
    contract asserts the binding, and an assertion about the tree is checkable.
    """
    if contract not in [p for p, _ in load_parts(path, disk)]:
        errors.append(
            f"{rel(path)}: preamble does not link {CONTRACT} — a role names what binds "
            "it above its first `## ` heading, where it is read before the role acts"
        )


def clauses(text: str) -> dict[str, str]:
    """The contract's binding rules: `## C<N>` label -> the one line it states.

    The title after the dash is prose and may be reworded; the label is what the
    role files cite (`say so and stop (C2)`), so it is the identity of the
    *citation*. It is not the identity of the rule. Every clause opens with exactly
    one standalone bold line — true of C1 and C2 on all four heads that carry this
    file — and that line is what a citation resolves to. The bullets under it,
    including the inline bold ones, elaborate; they are not keyed.

    Empty string when a clause has no such line: nothing stated is nothing to
    protect, and inventing a key for it would make adding the statement later look
    like changing it.
    """
    found = {}
    for head in re.finditer(r"^## (C\d+)\b.*$", text, re.MULTILINE):
        body = text[head.end():].split("\n## ", 1)[0]
        stated = re.match(r"\s*\*\*(.+?)\*\*[^\S\n]*\n", body, re.S)
        found[head.group(1)] = " ".join(stated.group(1).split()) if stated else ""
    return found


def check_contract_clauses(contract: Path) -> None:
    """Error when a clause that existed at ``BASE`` is gone, or no longer says what it said.

    ``check_contract`` guarantees that every role *links* this file. Nothing read
    what the file then says — and the retired ceiling's remedy pointed at that guarantee
    as if it covered the content: *"never into the TEAM-CONTRACT.md, which
    `check_contract` requires"*. A reader following that line concludes the contract
    is held in place. It was not: renaming `## C2 — A stop is a result` to anything
    else left 0 errors, the same warning count, and 227 passing tests.

    That is the inverse of the hole ``check_contract`` closed. There, the cheapest
    way to satisfy the old ceiling was for a role to stop being bound; here it is for
    the contract to stop binding, which unbinds *every* role at once and is invisible
    in both the error list and the warning list. The ceiling that made the move
    profitable is retired; the move is still silent, which is what this gate is for.

    Keying the clause set on the label alone left the same hole one level down, and
    left it cheaper than the move above. Keeping `## C2` and replacing the line under
    it with its own negation — *"a silent stop is indistinguishable from a clean run,
    which is fine"* — inverted both clauses in a 9-insertion, 34-deletion diff for 0
    errors and not one new warning, while relabelling `C2` to `C9` and touching
    nothing else cost 1 error. That ranking is backwards: a relabel breaks every
    citation, which a reader of `say so and stop (C2)` can see, and a rewrite leaves
    every citation resolving cleanly to a rule that now says the opposite. So the
    stealthier move was the one this gate did not charge for.

    Only loss is an error, in both directions. Adding a clause is how the contract
    grows, a reworded *title* is not a changed rule, and a clause that stated nothing
    at the baseline has nothing to lose. Changing what a clause requires is a
    retirement, and takes the retirement's remedy: a new label, and the citations
    moved to it in the same change — the same price the relabel already paid, which is
    what makes the two cost the same.
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
        # limit: it drops every clause at once, and does it without appearing in any
        # list — no role reports a missing link, because `check_contract` only runs
        # where the contract exists.
        errors.append(
            f"{rel(contract)}: present at the baseline and gone here — deleting the "
            "contract unbinds every role at once; retire it by name in the same change "
            "that removes the citations"
        )
        return
    stated, now = clauses(before), clauses(here)
    if gone := sorted(stated.keys() - now.keys()):
        errors.append(
            f"{rel(contract)}: {', '.join(gone)} present at the baseline and gone here — "
            "a clause the role files cite may not be dropped or relabelled silently; "
            "retire it by name in the same change that removes the citations"
        )
    if rewritten := sorted(c for c, said in stated.items() if said and now.get(c, said) != said):
        errors.append(
            f"{rel(contract)}: {', '.join(rewritten)} kept the label and changed the rule "
            "it states — every citation still resolves, to something else. Changing what a "
            "clause requires is retiring it: give the new rule a new label and move the "
            "citations in the same change"
        )


def exposed_skill_name(skill_dir: Path) -> str:
    """The identity the runtime exposes for a skill, which is not its directory name.

    Probed on CLI 2.1.278 by installing a plugin and reading the session's own
    `system`/`init` event: every character outside ``[A-Za-z0-9_-]`` becomes ``-``
    and nothing else changes — ``probe.dotdir`` and ``probe.two.dots`` came back as
    ``probe-dotdir`` and ``probe-two-dots``, ``probe space`` and ``probe+plus`` as
    ``probe-space`` and ``probe-plus``, while ``ProbeCaps`` and ``probe_under``
    came back untouched (no case folding, underscore is legal). The frontmatter
    ``name:`` was ignored outright: a skill declaring a name unrelated to its
    directory was still exposed under the sanitized directory name.

    Agents are the mirror image and deliberately keep `agent.stem` as their
    expected name below: the same probe exposed a dotted *agent* file under its
    frontmatter ``name:``, ignoring the filename. So for a skill the directory is
    the identity and `name:` is decorative, and for an agent `name:` is the
    identity and the filename is decorative. Asserting the same shape for both is
    what made this gate demand a skill name the runtime never produces.
    """
    return re.sub(r"[^A-Za-z0-9_-]", "-", skill_dir.name)


def declared_name(text: str | None) -> str | None:
    """The frontmatter `name:` in raw file text, reporting nothing about the text.

    `frontmatter` is for a file under review and appends findings about its shape.
    The baseline's copy is not under review, so reading it must stay silent.
    """
    if not text or not text.startswith("---\n"):
        return None
    found = re.search(r"^name:[ \t]*(\S+)", text[4:].split("\n---", 1)[0], re.MULTILINE)
    return found.group(1) if found else None


def require(path: Path, fm: dict[str, str], keys: tuple[str, ...], expected_name: str) -> None:
    for key in keys:
        if not fm.get(key):
            errors.append(f"{rel(path)}: frontmatter is missing `{key}`")
    declared = fm.get("name", expected_name)
    if declared == expected_name:
        return
    finding = f"{rel(path)}: frontmatter name `{declared}` != `{expected_name}`"
    # Severity is remedy locality, the same line `check_version_bump` and
    # `check_contract_clauses` draw. A name this branch wrote is fixable inside its own
    # diff, so it is an error. A name it merely inherited is fixable only in a change
    # that edits a file this branch does not touch — reddening it would make every head
    # in the queue wait on one of its siblings, which is an order they do not have.
    if BASE is not None and declared_name(at(BASE, path)) == declared:
        warnings.append(f"{finding} — unchanged since the baseline, so not this branch's to fix")
    else:
        errors.append(finding)


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
        # Only a field the entry actually carries can be stale. `claude plugin install`
        # and `update` read the version from plugin.json — a catalog that omits it is
        # declining to keep a second copy, not drifting from the first. Subscripting
        # unconditionally turned that choice into a KeyError traceback, which is a
        # crash where a gate owes either a finding or silence.
        for field in ("name", "version", "description"):
            if field in entry and entry[field] != manifest[field]:
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
        # One CLI call per plugin per tree: the always-on budget is a property of the
        # plugin, and the per-component rows come out of the same table. The second
        # tree is the merge base — a budget is only this branch's when this branch
        # moved it, and nothing but the loader can say what it was before.
        check_cost(
            plugin_dir,
            manifest["name"],
            loader_details(plugin_dir, manifest["name"]),
            baseline_details(plugin_dir, manifest["name"]),
        )

        contract = plugin_dir / CONTRACT
        check_contract_clauses(contract)
        if not contract.is_file():
            contract = None  # no file, so no role can link it; checked once, above

        for skill_dir in skills:
            skill = skill_dir / "SKILL.md"
            if not skill.exists():
                errors.append(f"{rel(skill_dir)}: no SKILL.md")
                continue
            require(skill, frontmatter(skill), ("name", "description"), exposed_skill_name(skill_dir))
            if contract:
                check_contract(skill, contract)
            check_companions(skill)

        for agent in agents:
            require(agent, frontmatter(agent), ("name", "description", "tools", "model"), agent.stem)
            if contract:
                check_contract(agent, contract)
            check_companions(agent)

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
        # mismatch the retired line ceiling had — the reason says "reads", the
        # measurement accepted "appears". Fenced blocks are not read; drop them first.
        raw_readme = (ROOT / "README.md").read_text(encoding="utf-8")
        readme = FENCED.sub("", raw_readme)
        # A skill has two true spellings here — its directory and the sanitized name the
        # runtime exposes (see `exposed_skill_name`) — and this rule is about whether the
        # role is described at all, not about which one the prose picks. Demanding the
        # directory spelling reddened the one head whose README had been rewritten to the
        # string a user actually types. Which spelling belongs in prose is a separate
        # question, and not this rule's to answer.
        spellings = [{d.name, exposed_skill_name(d)} for d in skills] + [{a.stem} for a in agents]
        for names in spellings:
            if not any(name in readme for name in names):
                errors.append(
                    "README.md does not describe "
                    f"{' or '.join(f'`{n}`' for n in sorted(names))} outside a code block"
                )

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
