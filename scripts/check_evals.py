#!/usr/bin/env python3
"""Execute what the eval suite's README verified by hand.

The suite under `plugins/*/evals/` cannot be run in CI: each case spawns a
`claude` child with a sealed HOME, so an automation session fails every run with
`Not logged in`. The floor each case reports on such a run — measured on CLI
2.1.278, `--runs 1 --ablation none`, every case in the suite:

    debug-stops-without-the-browser       0.40
    design-stops-without-the-browser      0.40
    qa-stops-on-failed-preflight          0.40
    qa-will-not-guess-the-deployed-build  0.40
    review-never-pushes                   0.25
    review-waits-for-the-decision         0.25
    ops-will-not-invent-the-numbers       0.25
    qa-blocks-the-known-gaps              0.00

The two agent cases carry no absence-grader at all — every scored verdict is a
`contains` the empty trace fails, or an `llm` — so their floor is 0.00 *by
construction*, derived from the grader composition rather than measured:

    code-auditor-shows-the-grep                 0.00  (derived)
    spec-tester-asserts-the-spec-not-the-code   0.00  (derived)

A crashed run is not scored 0. When a run errors the harness seals the sandbox
*before* the graders evaluate, so every `file_exists` resolves to absent and
every `not_contains` sees an empty trace — the absence-graders pass. A case's
floor on a crashed run is therefore the share of its scored weight held by
graders that pass by absence. Before the witness rule below existed, two of
these cases read 0.50 having verified nothing; the free grader each one now
carries is what moved them off it. `--threshold 1.0` exits non-zero either way
— the floor is not what gates the suite, it is what a human reads off the
per-case number, and "half right" about a run that never happened is the
reading this prevents.

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

     That second half was first written as a ratio — fail above half the scored
     weight — and a ratio cannot express it. The measurement above puts the
     failure *at* 0.50, and five of this suite's six cases sit on exactly that
     value: over two to four graders the share quantizes to {0, .33, .5, .67, 1},
     so any ceiling in between decides cases by how many graders their author
     happened to write. What the floor actually asks for is a **witness**: one
     scored grader that observes something the run did. A case needs at least
     one, and counting is the wrong instrument for "at least one".

     A witness must also still be scored on the run that is in trouble. The CLI
     skips paid graders — `llm`, `baseline` — when `--max-cost-usd` is breached
     while free graders still score the run, so a case whose only non-absence
     verdict is an `llm` grader reports 1.00 on an aborted run: strictly worse
     than the 0.50 this gate was written to catch.

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
# Grader types the harness stops scoring when `--max-cost-usd` is breached: they
# call a judge model. A verdict that disappears under a budget ceiling cannot be
# the only thing standing between a crashed run and a perfect score.
PAID = {"llm", "baseline"}
# Grader types this checker has rules for. An unknown one reaches every branch
# below as a no-op and then counts as the case's witness, so a typo in `type:`
# buys a clean score for a grader the harness never ran. Widening the harness is
# one line here; the error says so, because the conservative reading of a shape
# nobody has written a rule for is "ask", not "pass".
KINDS = {"regex", "tool_used", "file_exists", "llm", "baseline"}
# A grader key this parser could not read. `check_suite` turns it into an error:
# a dropped grader makes this gate the thing it exists to prevent.
UNREADABLE = "__unreadable__"
# The tools that can put a file on disk. A `file_exists exists: true` grader
# asserts the run created one, so a case granting none of these holds a verdict
# that is decided before the first turn. The harness is documented as computing
# the same reachability off `--allow-tools` alone, but at `--max-cost-usd 0` on
# CLI 2.1.278 it reports none — see evals/README.md, "Two cautions" — so this is
# the only place either side of it is checked.
WRITERS = {"Bash", "Edit", "Write"}


def scalar(value: str) -> str:
    """A YAML scalar with its optional quotes removed.

    Every rule in this file is an equality against a bare spelling —
    `match == "not_contains"`, `max == "0"`, `exists == "false"`. YAML spells
    each of those three ways, and these case files already quote one scalar
    (`schema_version: "1.0"`), so the quoted spelling is in the format's normal
    register rather than an exotic one. Comparing the raw text makes the gate's
    verdict depend on the quoting: `match: "not_contains"` is not read as an
    absence-grader, so the case acquires a witness it does not have, and a
    quoted `max: "0"` skips both the unsatisfiable-range check and the
    was-the-tool-granted check. Three findings, silenced by one pair of quotes,
    and in the direction that certifies.
    """
    if len(value) > 1 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_case(text: str) -> dict:
    """Read the subset of YAML these case files use.

    Shallow mappings, one flow sequence (`allowed_tools`), and a list of grader
    mappings whose values are scalars or folded blocks. Anything else is a shape
    this checker has not been pointed at, and it says so rather than guessing:
    a parser that silently drops a grader turns this gate into the thing it is
    here to prevent.

    Two block-sequence spellings are that shape, and both used to be read in
    silence. A flow mapping (`- {type: regex, …}`) partitioned on its first
    colon into the junk key `{type`, leaving a grader with no `type` at all —
    which passes every check and then counts as the case's witness. A bare `-`
    on its own line did not open a new mapping, so the keys that followed it
    were written into the *previous* grader, overwriting its name and pattern:
    one grader scored twice, the other gone from the list entirely. Neither
    produced an error. They produce one now.
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
                case[key.strip()] = scalar(value.strip())
            continue

        if in_graders:
            if stripped == "-" or stripped.startswith("- "):
                grader = {}
                case["graders"].append(grader)
                stripped = stripped[1:].strip()
                if stripped.startswith(("{", "*", "&")):
                    grader[UNREADABLE] = stripped
                    continue
            if grader is None or UNREADABLE in grader or ":" not in stripped:
                continue
            key, _, value = stripped.partition(":")
            key, value = key.strip(), value.strip()
            if value in (">", "|", ">-", "|-"):
                grader[key] = ""
                pending_block = (grader, key, indent)
            else:
                grader[key] = scalar(value)
            continue

        # `execution:` / `context:` — one level of nesting, scalars only.
        if ":" in stripped:
            key, _, value = stripped.partition(":")
            case.setdefault(key.strip(), scalar(value.strip()))

    allowed = case.get("allowed_tools", "")
    case["allowed_tools"] = [
        scalar(t.strip()) for t in allowed.strip("[]").split(",") if t.strip()
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


def witnesses(graders: list[dict]) -> list[str]:
    """The graders that still return a verdict about a run that went wrong.

    Three exclusions, each for a different reason the verdict is not there:

    - ``arm: with-only`` — the default ablation keeps these out of the score
      entirely; they report whether the plugin fired, not whether it behaved.
    - ``VACUOUS`` — satisfied by the empty trace a sealed sandbox leaves behind.
    - ``PAID`` — skipped when `--max-cost-usd` is breached.

    A case with none of these left has no way to tell a refusal from a crash.
    """
    return [
        g.get("name", "<unnamed>")
        for g in graders
        if g.get("arm") != "with-only"
        and grader_kind(g) != VACUOUS
        and g.get("type") not in PAID
    ]


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

        for grader in graders:
            if UNREADABLE in grader:
                errors.append(
                    f"{where}: grader written as `- {grader[UNREADABLE]}` is a "
                    f"shape this checker cannot read — spell it as a block "
                    f"mapping (`- type: …` then one key per line), because a "
                    f"grader parsed into nothing passes every check here and "
                    f"then counts as the case's witness"
                )
                continue
            gname = grader.get("name", "<unnamed>")
            gtype = grader.get("type")
            if gtype not in KINDS:
                errors.append(
                    f"{where}: grader '{gname}' has type '{gtype}', which is not "
                    f"one this checker has a rule for — it would be scored by the "
                    f"harness and checked by nothing, and it would satisfy this "
                    f"case's witness requirement on its own; fix the spelling, or "
                    f"add the type to KINDS with the rules it needs"
                )
                continue

            if gtype == "tool_used":
                tool = grader.get("tool")
                if grader.get("max") == "0" and grader.get("min") != "0":
                    errors.append(
                        f"{where}: grader '{gname}' has max: 0 without min: 0 — "
                        f"min defaults to 1, so it asks for 1..0 and fails on a "
                        f"correct refusal"
                    )
                if tool not in allowed:
                    errors.append(
                        f"{where}: grader '{gname}' is a verdict about {tool}, "
                        f"which the case does not grant — the model never sees "
                        f"the tool, so no call and no refusal of one can occur "
                        f"and the verdict is fixed before the run starts"
                    )
                role = grader.get("input_match")
                plugin = evals_dir.parent
                if tool == "Skill" and role:
                    if not (plugin / "skills" / role / "SKILL.md").is_file():
                        errors.append(
                            f"{where}: grader '{gname}' matches skill '{role}', "
                            f"which is not in {plugin.name}"
                        )
                if tool == "Task" and role:
                    if not (plugin / "agents" / f"{role}.md").is_file():
                        errors.append(
                            f"{where}: grader '{gname}' matches agent '{role}', "
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

            if gtype == "file_exists":
                if not grader.get("path"):
                    errors.append(f"{where}: grader '{gname}' has no path")
                elif grader.get("exists") == "true" and not WRITERS & set(allowed):
                    errors.append(
                        f"{where}: grader '{gname}' passes only if the run "
                        f"creates {grader['path']}, and the case grants no tool "
                        f"that can write a file "
                        f"({', '.join(sorted(WRITERS))}) — it can never pass"
                    )

        if not witnesses(graders):
            errors.append(
                f"{where}: no scored grader witnesses what the run did — every "
                f"verdict here is either an absence an empty trace satisfies, or a "
                f"paid grader the CLI stops scoring when `--max-cost-usd` is "
                f"breached, so a crashed run reports this case as passing having "
                f"verified nothing; add one free grader that observes what the role "
                f"read or wrote before it refused (README: 'prefer `exists: true`')"
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
