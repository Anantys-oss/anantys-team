#!/usr/bin/env python3
"""An action the skill accepts and the README never names is unreachable.

A skill with subcommands has two surfaces and only one of them is read before
install. `anantys.qa` ships an Actions table of seven; the README's command block
shows four. The three missing ones are not degraded — they are invisible, because
the block *is* the reference: nothing else in the repo lists an invocation, and a
user does not read `SKILL.md` to find out what to type.

The gap is silent in both directions at once. Every existing gate reads the plugin
tree, so an action added to the table ships green; the README is at the repo root,
outside `check_version_bump`'s subject set, so it is not even a content change. And
the README can *describe* the behaviour while withholding the verb — this one sells
"accumulates operator rulings so a non-defect is never re-filed" and never names
`note`, the action that does it. A reader is told the feature exists and cannot
reach it, which is worse than not being told.

The sharpest case is the default. `anantys.qa` infers `status` when a plan exists,
so a bare invocation lands on the one action no README in this queue mentions — the
command a user reaches first is the one the documentation does not have.

Two things keep this from matching its own output. The action token is taken from a
fenced block line that *invokes the skill*, never from prose: `report` appears three
times in this README as an English noun, so a bare substring search over the file
certifies every skill that has a `report` action and reads nothing. And the command's
spelling is not fixed — `/anantys.qa` and `/anantys-team-agents:anantys-qa` are the
same skill, one of them live in this queue — so the match is on the final segment,
and `SPELLINGS` proves the extractor against lines written out literally rather than
against lines built by the same split the extractor applies.

A gap is an error only when this branch opened it. The three `anantys.qa` actions
this gate was written from are undocumented *on `main`*, so every branch inherits
them: overlaying these scripts onto each open head (`scripts/gate_matrix.py`) on
2026-10-25 reddened 104 of 116 for a README nobody in the queue had touched, and the
gate was green on exactly one head — the one that also edited the README. A gate
wired into `pull_request` that fails on the base it merges into blocks the whole
queue and names no remedy any single branch can reach, which is why `check_plugins`,
`check_tool_grants` and `check_mcp_grants` all price inherited debt separately. So
does this one, by the same mechanism: the gap set is recomputed at the merge base and
a gap found there too is a warning. With no merge base nothing is attributable, and
every gap stays an error — that is a lost distinction, not a pass.

Exit 0 = clean (warnings allowed), 1 = at least one error.
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGINS = "plugins"
README = "README.md"

#: A command line and the action it must yield, written out. The extractor may not be
#: proved against input it derived: building a line from `segments()` and then asking
#: `segments()` to read it back holds for any splitting rule at all, including one that
#: matches no line this README contains. Both live spellings are here — the dotted one
#: on `main`, the namespaced one on `koan/the-command-name-is-not-the-skill-name` — plus
#: the shapes that must yield nothing, since a false action is how a table row gets
#: certified by a line that never named it.
SPELLINGS = (
    ("/anantys.qa      init                     # one-off: describe your envs", "qa", "init"),
    ("/anantys.qa      plan --from pr:42        # …or from a PR", "qa", "plan"),
    ("/anantys.qa      run --env staging        # …or on a deployed env", "qa", "run"),
    ("/anantys-team-agents:anantys-qa report", "qa", "report"),
    ("/anantys.design  https://dev.example.com/pricing — fix the hero", "design", None),
    ("/anantys.qa", "qa", None),  # the bare invocation documents no action
    ("/anantys.qa      --env staging", "qa", None),  # `-` is in `[\\w-]`; a flag is not an action
    ("  /anantys.qa   note A4 --env local", "qa", "note"),
    ("not a command: /anantys.qa status", None, None),
)


def tail(token: str) -> str:
    """The segment that distinguishes a skill from its namespace.

    `/anantys.qa`, `/anantys-qa` and `/anantys-team-agents:anantys-qa` name one skill;
    which of the three a branch writes is itself contested in this queue, so neither
    the separator nor the prefix can be the thing matched on.
    """
    return re.split(r"[.:\-]", token.lstrip("/"))[-1]


def invocation(line: str) -> tuple[str | None, str | None]:
    """`(skill tail, action)` for a line that invokes a skill, else `(None, None)`.

    A command starts the line — prose that merely mentions `/anantys.qa status` is
    talking about the action, not showing it, and counting it would let the README
    satisfy this gate by describing the gap it has.
    """
    words = line.split()
    if not words or not words[0].startswith("/"):
        return None, None
    # The action is the token *immediately* after the command, and only if it is a bare
    # word. Scanning forward for the first bare word instead read `fix` out of the
    # `anantys.design` line's freeform prompt — a skill that takes an argument rather
    # than a subcommand has no action here, and any later word is part of that argument.
    # `[\w-]+` admits `--env`, because `-` is in the class — so an action must *start*
    # with a word character. Without that, a skill whose only example passes a flag
    # reads as documenting an action named `--env`, and the real one goes unreported.
    following = words[1] if len(words) > 1 else ""
    action = following if re.fullmatch(r"\w[\w-]*", following) else None
    return tail(words[0]), action


def fenced(text: str) -> list[str]:
    """Lines inside ``` fences. Outside them a command is prose, and prose is not a reference."""
    lines, out, inside = text.splitlines(), [], False
    for line in lines:
        if line.lstrip().startswith("```"):
            inside = not inside
        elif inside:
            out.append(line)
    return out


def merge_base() -> str | None:
    """The commit the working tree departs from, or ``None`` when git cannot say.

    ``None`` is not a pass: the standing finding is still reported, and only the
    ability to attribute it to the branch under review is lost.
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
        ["git", "show", f"{commit}:{path.relative_to(ROOT)}"],
        cwd=ROOT, capture_output=True, text=True,
    )
    return done.stdout if done.returncode == 0 else None


def actions(body: str) -> list[str]:
    """Canonical actions from the `## Actions` table: the first-column code span per row.

    Takes the file's *text*, not its path, so the same rule reads the working tree and
    the merge base. The table is the canonical list on purpose: `anantys.qa` names
    `testplan` in prose below it as "the action's former name — still accepted"; an
    alias kept for people who already typed it is not something the README owes a line,
    and requiring one would make every deprecation a documentation error.
    """
    block = re.search(r"^## Actions\b(.*?)(?=^## |\Z)", body, re.MULTILINE | re.DOTALL)
    if block is None:
        return []
    found = re.findall(r"^\|\s*`([^`]+)`\s*\|", block.group(1), re.MULTILINE)
    return [a for a in dict.fromkeys(found) if re.fullmatch(r"[\w-]+", a)]


def gaps(readme: str | None, skills: list[tuple[str, str]]) -> set[tuple[str, str]]:
    """`(skill directory, action)` for every table row no README command block shows.

    One function for both trees, so "was this gap already here?" is answered by the
    rule that reports it rather than by a second, drifting copy of it.
    """
    documented = {
        (skill, action)
        for skill, action in map(invocation, fenced(readme or ""))
        if skill and action
    }
    return {
        (name, action)
        for name, body in skills
        for action in actions(body)
        if (tail(name), action) not in documented
    }


def main(argv: list[str] = ()) -> int:
    if stray := [a for a in argv if Path(a).resolve() != ROOT]:
        sys.exit(
            f"error: this gate checks {ROOT}, the tree its own file is in — it cannot be "
            f"pointed at {stray[0]!r}. Overlay these scripts onto another head with "
            f"scripts/gate_matrix.py, which is what that tool is for"
        )
    errors: list[str] = []
    warnings: list[str] = []

    for line, want_skill, want_action in SPELLINGS:
        got = invocation(line)
        if got != (want_skill, want_action):
            errors.append(
                f"`invocation()` reads {line.strip()!r} as {got} — the README's own "
                f"spelling must read as {(want_skill, want_action)}"
            )

    readme = ROOT / README
    if not readme.is_file():
        warnings.append(f"no {README} — there is no reference to check the tables against")

    paths = sorted((ROOT / PLUGINS).glob("*/skills/*/SKILL.md"))
    here = [(p.parent.name, p.read_text(encoding="utf-8")) for p in paths]
    tables = sum(1 for _, body in here if actions(body))

    shown = readme.read_text(encoding="utf-8") if readme.is_file() else None
    found = gaps(shown, here)

    # Only a tree with a gap has anything to attribute, so the baseline is read only
    # then: a clean tree must not spend two `git` calls to say nothing, nor warn about
    # a distinction that would change no verdict.
    inherited: set[tuple[str, str]] = set()
    base = merge_base() if found else None
    if found and base is None:
        warnings.append(
            "no merge base, so no gap below is attributable to this branch — each is "
            "reported as an error, inherited ones included"
        )
    elif base is not None:
        before = ((p.parent.name, at(base, p)) for p in paths)
        inherited = gaps(at(base, readme), [(n, b) for n, b in before if b is not None])

    for name, action in sorted(found):
        finding = (
            f"{name}: action `{action}` is in the Actions table and in "
            f"no {README} command block — the block is the only invocation reference "
            f"a reader sees before install, so the action is unreachable"
        )
        if (name, action) in inherited:
            warnings.append(
                f"{finding} — undocumented at the merge base too, so not this branch's "
                f"to fix; it is owned by the change that documents the action"
            )
        else:
            errors.append(finding)

    # No table is not a clean tree, it is an unmeasured one: every skill here could have
    # grown subcommands in prose instead, and this gate would print nothing and exit 0.
    if not tables:
        warnings.append(
            "no skill ships an `## Actions` table, so no invocation was checked — this "
            "gate is inert on this tree, not satisfied by it"
        )

    for warning in warnings:
        print(f"warning: {warning}")
    for error in errors:
        print(f"error: {error}")
    print(f"{len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
