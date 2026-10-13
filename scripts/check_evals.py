#!/usr/bin/env python3
"""Execute what the eval suite's README verified by hand.

The suite under `plugins/*/evals/` cannot be run in CI: each case spawns a
`claude` child with a sealed HOME, so an automation session fails every run with
`Not logged in`. Measured on CLI 2.1.278, this repo's six cases, `--runs 1
--ablation none`:

    qa-stops-on-failed-preflight     score 0.50   (run never started)
    debug-stops-without-the-browser  score 0.50   (run never started)
    qa-blocks-the-known-gaps         score 0.00   (run never started)

A crashed run is not scored 0. When a run errors the harness seals the sandbox
*before* the graders evaluate, so every `file_exists` resolves to absent and
every `not_contains` sees an empty trace — the absence-graders pass. A case's
floor on a crashed run is therefore the share of its scored weight held by
graders that pass by absence, and two of these three cases read 0.50 having
verified nothing. `--threshold 1.0` still exits non-zero, but the per-case
number a human reads says "half right".

So the suite is prose with YAML syntax until something executes it. Two of its
load-bearing properties are checkable with no credential at all, and both are
documented in `evals/README.md` as having been verified once, by hand, at
authoring time:

  1. **The `not_contains` patterns.** Four graders pass by the *absence* of a
     pattern, so a pattern that can never match is a gate that is always green.
     The README carries a table of must-match / must-not-match spellings per
     grader — the two directions that make such a pattern correct. It is a set
     of test vectors written in markdown that nothing runs. This checker runs
     them against the pattern actually in `case.yaml`, which is what catches the
     drift the table cannot: a pattern tightened in the case file while the row
     documenting it stays as it was.

  2. **The vacuity floor.** `min` defaults to 1, so a `tool_used` grader with a
     bare `max: 0` asks for `expected 1..0` and fails on a correct refusal; and
     a case whose scored weight is mostly absence-graders reports a passing-looking
     number on a run that never happened. Both are rules the README states and
     nothing enforces.

What this checker deliberately does not do: score a role. That needs the agent
runs, a credential, and a human reading the result. It asserts only that the
suite is capable of scoring one.
"""

from __future__ import annotations

import pathlib
import re
import sys
import unicodedata

REPO = pathlib.Path(__file__).resolve().parent.parent

# A grader that passes when the run produced nothing. `file_exists exists: false`
# resolves to absent on a sealed sandbox; `not_contains` matches an empty trace;
# `tool_used max: 0` is satisfied by a session that made no calls at all.
VACUOUS = "vacuous"
# The share of a case's scored weight that may pass by absence. Above a half, a
# crashed run reads as a majority-passing case.
VACUITY_CEILING = 0.5


def parse_case(text: str) -> dict:
    """Read the subset of YAML these case files use.

    Shallow mappings, one flow sequence (`allowed_tools`), and a list of grader
    mappings whose values are scalars or folded blocks. Anything else is a shape
    this checker has not been pointed at, and it says so rather than guessing:
    a parser that silently drops a grader turns this gate into the thing it is
    here to prevent.
    """
    case: dict = {"graders": []}
    grader: dict | None = None
    in_graders = False
    pending_block: tuple[dict, str, int] | None = None

    for raw in text.splitlines():
        if pending_block is not None:
            owner, key, indent = pending_block
            if raw.strip() and (len(raw) - len(raw.lstrip())) > indent:
                owner[key] = (owner[key] + " " + raw.strip()).strip()
                continue
            pending_block = None

        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()

        if indent == 0:
            in_graders = stripped == "graders:"
            grader = None
            if not in_graders and ":" in stripped:
                key, _, value = stripped.partition(":")
                case[key.strip()] = value.strip()
            continue

        if in_graders:
            if stripped.startswith("- "):
                grader = {}
                case["graders"].append(grader)
                stripped = stripped[2:].strip()
            if grader is None or ":" not in stripped:
                continue
            key, _, value = stripped.partition(":")
            key, value = key.strip(), value.strip()
            if value in (">", "|", ">-", "|-"):
                grader[key] = ""
                pending_block = (grader, key, indent)
            else:
                grader[key] = value
            continue

        # `execution:` / `context:` — one level of nesting, scalars only.
        if ":" in stripped:
            key, _, value = stripped.partition(":")
            case.setdefault(key.strip(), value.strip())

    allowed = case.get("allowed_tools", "")
    case["allowed_tools"] = [
        t.strip() for t in allowed.strip("[]").split(",") if t.strip()
    ]
    return case


def grader_kind(grader: dict) -> str | None:
    """`VACUOUS` when the grader passes on a run that produced nothing."""
    gtype = grader.get("type")
    if gtype == "regex" and grader.get("match") == "not_contains":
        return VACUOUS
    if gtype == "file_exists" and grader.get("exists") == "false":
        return VACUOUS
    if gtype == "tool_used" and grader.get("max") == "0":
        return VACUOUS
    return None


def split_row(row: str) -> list[str]:
    """Split a markdown table row on its unescaped pipes."""
    cells = re.split(r"(?<!\\)\|", row.strip())
    if cells and not cells[0].strip():
        cells = cells[1:]
    if cells and not cells[-1].strip():
        cells = cells[:-1]
    return [c.replace("\\|", "|").strip() for c in cells]


def code_spans(cell: str) -> list[str]:
    """The backticked spans in a table cell, as the markdown source wrote them.

    The README is prose, so it carries typographic punctuation an author's editor
    inserted; a vector is a shell command and must be compared as ASCII.
    """
    spans = re.findall(r"`([^`]+)`", cell)
    # NFKD folds the non-breaking hyphen to U+2010, which is still not the ASCII
    # hyphen a shell command contains.
    return [
        unicodedata.normalize("NFKD", s).replace("‐", "-") for s in spans
    ]


def parse_vector_table(readme: str) -> dict[str, dict]:
    """Rows of `| `grader-name` — `pattern` | must match | must not match |`."""
    vectors: dict[str, dict] = {}
    for row in readme.splitlines():
        cells = split_row(row)
        if len(cells) != 3:
            continue
        head = code_spans(cells[0])
        if len(head) != 2 or "—" not in cells[0]:
            continue
        name, pattern = head
        vectors[name] = {
            "pattern": pattern,
            "must_match": code_spans(cells[1]),
            "must_not_match": code_spans(cells[2]),
        }
    return vectors


def check_suite(evals_dir: pathlib.Path) -> list[str]:
    errors: list[str] = []
    readme = evals_dir / "README.md"
    vectors = parse_vector_table(readme.read_text()) if readme.is_file() else {}
    documented = set()

    for case_file in sorted(evals_dir.glob("*/case.yaml")):
        where = case_file.relative_to(REPO)
        case = parse_case(case_file.read_text())
        graders = case["graders"]
        allowed = case["allowed_tools"]

        if not graders:
            errors.append(f"{where}: no graders parsed — unreadable case shape")
            continue
        if case.get("name") != case_file.parent.name:
            errors.append(
                f"{where}: name '{case.get('name')}' is not the directory name "
                f"'{case_file.parent.name}' — `--case` filters by name"
            )

        scored = vacuous = 0
        for grader in graders:
            gname = grader.get("name", "<unnamed>")
            gtype = grader.get("type")

            if gtype == "tool_used":
                tool = grader.get("tool")
                if grader.get("max") == "0":
                    if grader.get("min") != "0":
                        errors.append(
                            f"{where}: grader '{gname}' has max: 0 without min: 0 — "
                            f"min defaults to 1, so it asks for 1..0 and fails on a "
                            f"correct refusal"
                        )
                    if tool not in allowed:
                        errors.append(
                            f"{where}: grader '{gname}' scores a refusal of {tool}, "
                            f"which the case does not grant — a refusal only counts "
                            f"when the action was available"
                        )
                if tool == "Skill" and "Skill" not in allowed:
                    errors.append(
                        f"{where}: grader '{gname}' asserts a Skill call, but the "
                        f"case does not grant Skill"
                    )
                skill = grader.get("input_match")
                if tool == "Skill" and skill:
                    plugin = evals_dir.parent
                    if not (plugin / "skills" / skill / "SKILL.md").is_file():
                        errors.append(
                            f"{where}: grader '{gname}' matches skill '{skill}', "
                            f"which is not in {plugin.name}"
                        )

            if gtype == "regex":
                if grader.get("target") == "trace" and "Bash" not in allowed:
                    errors.append(
                        f"{where}: grader '{gname}' scores the shell trace, but the "
                        f"case does not grant Bash — the trace cannot contain a command"
                    )
                errors += check_pattern(where, gname, grader, vectors)
                documented.add(gname)

            if gtype == "file_exists" and not grader.get("path"):
                errors.append(f"{where}: grader '{gname}' has no path")

            if grader.get("arm") == "with-only":
                continue
            scored += 1
            if grader_kind(grader) == VACUOUS:
                vacuous += 1

        if scored and vacuous / scored > VACUITY_CEILING:
            errors.append(
                f"{where}: {vacuous} of {scored} scored graders pass by absence "
                f"({vacuous / scored:.0%}) — a crashed run would score that high "
                f"having verified nothing; add a grader that cannot go green by "
                f"accident (README: 'prefer `exists: true`')"
            )

    for name in sorted(vectors.keys() - documented):
        errors.append(
            f"{readme.relative_to(REPO)}: vector row for '{name}' matches no "
            f"regex grader in the suite"
        )
    return errors


def check_pattern(where, gname: str, grader: dict, vectors: dict) -> list[str]:
    """Run the README's two-sided vectors against the live pattern."""
    pattern = grader.get("pattern")
    row = vectors.get(gname)
    if row is None:
        # Either direction is a gate that can be permanently green: a
        # `not_contains` whose pattern can never match, a `contains` whose
        # pattern always matches. Both need the two spellings written down.
        return [
            f"{where}: grader '{gname}' is decided by a pattern, and "
            f"evals/README.md carries no must-match / must-not-match row for it "
            f"— an unverified pattern may be a gate that never changes verdict"
        ]
    if row["pattern"] != pattern:
        return [
            f"{where}: grader '{gname}' pattern has drifted from the row that "
            f"verified it\n    case:   {pattern}\n    README: {row['pattern']}"
        ]
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        return [f"{where}: grader '{gname}' pattern does not compile: {exc}"]

    errors = []
    if not row["must_match"] or not row["must_not_match"]:
        errors.append(
            f"{where}: grader '{gname}' is verified in one direction only — a "
            f"row needs both a must-match and a must-not-match spelling"
        )
    for vector in row["must_match"]:
        if not compiled.search(vector):
            errors.append(
                f"{where}: grader '{gname}' no longer matches {vector!r} — the "
                f"forbidden action would go unnoticed"
            )
    for vector in row["must_not_match"]:
        if compiled.search(vector):
            errors.append(
                f"{where}: grader '{gname}' now matches {vector!r}, which is "
                f"legitimate — the grader fails a correct run"
            )
    return errors


def main() -> int:
    suites = sorted(REPO.glob("plugins/*/evals"))
    if not suites:
        print("check_evals: no plugins/*/evals suite — nothing to check")
        return 0

    errors: list[str] = []
    for suite in suites:
        errors += check_suite(suite)

    if errors:
        print("check_evals: FAIL")
        for error in errors:
            print(f"  ✗ {error}")
        return 1

    cases = sum(len(list(s.glob("*/case.yaml"))) for s in suites)
    print(f"check_evals: ok — {cases} case(s) in {len(suites)} suite(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
