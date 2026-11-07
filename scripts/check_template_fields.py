#!/usr/bin/env python3
"""A field the operator is interviewed to fill must be named by the prose that reads it.

`anantys.qa/templates/qa-config.md` declares `### Agent limits` in both of its example
environment blocks, and `/anantys.qa init` interviews the operator to fill it. Nothing
reads it: the string appears zero times in that skill's prose. An operator answers a
question whose answer no action will ever consult, and `plan` re-derives the same class
of information from a hardcoded list instead.

That is not a dead link, so no path-resolving gate sees it. Both files exist and both
are well-formed; what is broken is the *relation* between them. Seven checkers and
forty-two audited heads passed it.

The contract this gate holds: for a template the skill reads back, every field it
declares must be named somewhere in that skill's prose surface. Unnamed means
unreachable — prose is the only mechanism by which an action consults a field, so a
field no sentence names cannot be consulted, whatever the file contains.

**Direction comes from the template's own preamble**, not from a list kept here. A
template says what it is for in its first paragraph — `qa-config.md`: "Written by
`/anantys.qa init` … read by every other action"; `feature-brief.md`: "the `--brief` …
source for `/anantys.qa plan`"; `qa-plan.md`: "Written by `/anantys.qa plan` into the
feature's spec-kit directory", and nothing more. The first two are read, the third
declares only authorship. A template that never claims to be read is skipped, because
for a file the skill *writes* the template is the authority and the prose owes it no
second copy — #49's "the copy is what goes stale" argument, applied to headings.

Keying on prose means the gate's reach is set by wording rather than by truth, and a
reworded preamble silently narrows it. So every template's classification is printed,
every run: a skipped template is visible and arguable, never silent. `qa-plan.md` is in
fact read back by `run`, and its preamble understating that is a prose defect this gate
reports by omission rather than hides.

Severity follows the repo's rule — a mismatch whose fix is wholly inside the branch's
diff is an error, inherited drift is a warning. A mismatch has exactly two files that
can hold its fix: the template declaring the field, and the prose that should name it.
A branch that changed neither did not introduce the mismatch and cannot close it in its
own diff, so it is warned at, not failed — attribution is per mismatch, not per skill.
With no baseline (a shallow checkout, or no git at all) nothing is attributable and
every mismatch is a warning; the baseline used is printed so that mode cannot pass for
a green verdict.
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = "plugins/*/skills/*/templates/*.md"

# A preamble claims the file is consumed, not merely produced.
READ_CLAIM = re.compile(r"\bread by\b|\bsource for\b", re.I)
HEADING = re.compile(r"^#{2,6}[ \t]+(.+?)[ \t]*$", re.M)
# "1. Scope", "A — <journey name>": the enumerator is position, not name.
ENUMERATOR = re.compile(r"^(?:\d+\.|[A-Z](?=\s+[—–-]\s))\s*[—–-]?\s*")
# " — why it matters", " (`kind: local`)": a trailing gloss is not part of the name.
GLOSS = re.compile(r"\s+[—–]\s+|\s*\(")
PLACEHOLDER = re.compile(r"<[^>]*>")


def preamble(text: str) -> str:
    """What the template says about itself, before its first example block."""
    return text.split("\n```", 1)[0]


def is_read(text: str) -> bool:
    """Does the template's preamble claim an action consumes the filled file?"""
    return bool(READ_CLAIM.search(preamble(text)))


def fields(text: str) -> list[tuple[int, str]]:
    """The named fields a template declares, as (line, name).

    Headings carrying a value (`## Environment: staging`, `## Run <n>`) name an
    instance the operator supplies, not a field the prose can be asked to read, so
    they are not fields. Neither is a heading that is only a placeholder.
    """
    found = []
    body = text[len(preamble(text)) :]
    offset = len(preamble(text))
    for match in HEADING.finditer(body):
        raw = match.group(1)
        if ":" in raw:
            continue
        name = PLACEHOLDER.sub("", GLOSS.split(ENUMERATOR.sub("", raw))[0]).replace("`", "").strip()
        if name:
            found.append((text.count("\n", 0, offset + match.start()) + 1, name))
    return found


def names(name: str, prose: str) -> bool:
    """Is the field named in the prose? `A / B` is named by either side."""
    return any(part.strip().lower() in prose.lower() for part in name.split("/") if part.strip())


def changed_paths(baseline: str | None) -> set[str]:
    """Repo-relative paths this branch changed, or an empty set with no baseline."""
    if not baseline:
        return set()
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), "diff", "--name-only", baseline],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return set()
    return {line for line in out.splitlines() if line}


def baseline_ref() -> str | None:
    """The merge-base with the target branch, or None if it cannot be resolved."""
    for ref in ("origin/main", "main"):
        try:
            out = subprocess.run(
                ["git", "-C", str(ROOT), "merge-base", ref, "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            continue
        if out:
            return out
    return None


def prose_surface(skill: Path) -> list[Path]:
    """SKILL.md plus the reference topics beside it — the prose an action can reach."""
    return [skill / "SKILL.md"] + sorted(skill.glob("reference/*.md"))


def main() -> int:
    templates = sorted(ROOT.glob(TEMPLATES))
    if not templates:
        print(f"check_template_fields: no templates matched {TEMPLATES}")
        return 1

    baseline = baseline_ref()
    changed = changed_paths(baseline)
    errors = warnings = 0

    for path in templates:
        skill = path.parent.parent
        text = path.read_text(encoding="utf-8")
        shown = path.relative_to(ROOT)
        if not is_read(text):
            print(f"{shown}: written only — its preamble claims no reader, fields unchecked")
            continue
        surface = [p for p in prose_surface(skill) if p.exists()]
        prose = "\n".join(p.read_text(encoding="utf-8") for p in surface)
        fixable = {str(p.relative_to(ROOT)) for p in [path, *surface]}
        owned = bool(fixable & changed)
        unnamed = [(line, name) for line, name in fields(text) if not names(name, prose)]
        print(f"{shown}: read by an action — {len(fields(text))} fields, {len(unnamed)} unnamed")
        for line, name in unnamed:
            level = "ERROR" if owned else "WARN"
            print(
                f"{level} {shown}:{line}: field `{name}` is named nowhere in "
                f"{skill.name}'s prose, so no action can consult it — name it where it "
                f"is read, or drop the heading"
            )
            if owned:
                errors += 1
            else:
                warnings += 1

    where = baseline[:12] if baseline else "none (every mismatch is a warning)"
    print(
        f"check_template_fields: {len(templates)} templates, baseline {where} — "
        f"{errors} errors, {warnings} warnings"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
