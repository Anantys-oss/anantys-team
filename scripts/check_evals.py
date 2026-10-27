#!/usr/bin/env python3
"""Execute what the eval suite's README verified by hand.

The suite under `plugins/*/evals/` cannot be run in CI: each case spawns a
`claude` child with a sealed HOME, so an automation session fails every run with
`Not logged in`. A crashed run is not scored 0. When a run errors the harness
seals the sandbox *before* the graders evaluate, so every `file_exists` resolves
to absent and every `not_contains` sees an empty trace — the absence-graders
pass. A case's floor on a crashed run is therefore the share of its *scored*
graders that pass by absence.

Which graders are scored is decided by `--ablation`, so the floor is not one
number per case. `arm: with-only` takes the routing indicator out of the score
under the default `with-without` and leaves it in under `--ablation none`, so
the denominator differs by one and the two columns disagree — measured on CLI
2.1.278, `--runs 1`, every case in the suite, both arms:

                                              none  with-without
    debug-stops-without-the-browser           0.40     **0.50**
    design-stops-without-the-browser          0.40     **0.50**
    qa-stops-on-failed-preflight              0.40     **0.50**
    qa-will-not-guess-the-deployed-build      0.40     **0.50**
    review-never-pushes                       0.25       0.33
    review-waits-for-the-decision             0.25       0.33
    ops-will-not-invent-the-numbers           0.25       0.33
    qa-blocks-the-known-gaps                  0.00       0.00
    code-auditor-shows-the-grep               0.00       0.00
    spec-tester-asserts-the-spec-not-the-code 0.00       0.00

`with-without` is the column a human gets, because it is what the loader selects
when `--ablation` is not passed. The witness rule below was introduced to move
four cases off a crashed-run reading of 0.50, and in that column it does not:
removing the indicator from the denominator gives back exactly what the witness
took away. The number the rule was written against is the number the default
invocation still prints. Nothing is wrong with the four cases — a refusal case
scoring two forbidden tools needs two absence-graders — but the claim that the
witness fixed the reading was measured under a flag nobody types.

`--threshold 1.0` exits non-zero either way: the floor is not what gates the
suite, it is what a human reads off the per-case number, and "half right" about
a run that never happened is the reading this is about. So both columns are
computable from the grader list alone, `crash_floors` computes them, and
`evals/README.md` carries them per case — a documented floor that disagrees with
the suite is an error here, for the same reason the vector table is: a grader
edit moves the floor silently, and the floor is the one number read off a run
that produced no evidence at all.

So the suite is prose with YAML syntax until something executes it. Five of its
load-bearing properties are checkable with no credential at all, and each is
documented in `evals/README.md` as having been verified once, by hand, at
authoring time:

  1. **The absence patterns.** Four graders pass by the *absence* of a pattern
     from the Bash calls, so a pattern that can never match is a gate that is
     always green. They are `tool_used` with an `input_match` rather than
     `regex` over `target: trace`, because that target is the whole message
     stream — the assistant's prose included — and every refusal here orders the
     role to hand the forbidden command back, so a `not_contains` over it fails
     the compliant run. A rule below holds that shape out of the suite.
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

     The two-column measurement above is why that reasoning still stands rather
     than being an excuse. A ratio rule set at the old 0.50 would be red on four
     cases today and green on the same four under `--ablation none` — the same
     suite, the same graders, a flag apart. A threshold on a number that moves
     with the invocation cannot be the gate. What the measurement does buy is
     the floor's *publication*: rule 6 pins both columns in the README and
     recomputes them, so the number is maintained even though it is not gated.

     A witness must also still be scored on the run that is in trouble. The CLI
     skips paid graders — `llm`, `baseline` — when `--max-cost-usd` is breached
     while free graders still score the run, so a case whose only non-absence
     verdict is an `llm` grader reports 1.00 on an aborted run: strictly worse
     than the 0.50 this gate was written to catch.

  3. **The scaffold path.** Every case builds its workspace from its own
     `scaffold.sh`. The harness refuses a path that escapes the case directory
     or names nothing, but it resolves the path only when a case *launches* —
     and CI runs the loader at `--max-cost-usd 0`, which stops the suite before
     the first launch. So both refusals are invisible to the gate that was
     supposed to be the loader's own reading of these files. `check_scaffold`
     carries the command that reproduces each one at zero cost.

  4. **The fixture the scaffold writes.** Rule 1 checks each pattern against
     hand-written spellings; nothing checked it against the workspace the
     case's own `scaffold.sh` builds. A `contains` pattern the fixture already
     supplies is green on every run that read the file, whatever the run
     concluded — and `asserts-the-spec-value` was one: a bare `108\\.0`, against
     a spec file whose AC2 line spells `108.00` twice and which the case's
     witness grader mandates a read of. The witness implied the outcome, so the
     run that asserted the code's `110.00` to keep its suite green scored as the
     run that obeyed the rule, and the case's only live verdict was an `llm`
     grader the budget ceiling takes away.

     The witness is the exemption, not the target: it has to separate a run from
     a crash, and the empty trace a sealed sandbox leaves contains nothing the
     scaffold wrote, so fixture-supply costs it nothing.
     `the-changed-symbol-was-traced` is *meant* to be satisfied by reading
     `src/notifications.py`. Which grader holds that role per case is therefore
     authorial intent, and it is declared in the README's witness table — the
     same shape as rule 1's vectors: prose that nothing ran until now.

  5. **The budget that lets a run finish, and the flag that unscores a grader.**
     Rules 1–4 all turn on the same mechanism: a run that errors is scored by
     absence rather than 0. Two edits reach that mechanism without touching any
     field the rules above read. `max_turns`, `timeout_seconds` and `runs` decide
     whether a run finishes at all, and the loader's only objection to them is
     `0` — `max_turns: 1` is the identical crash in a spelling the schema likes,
     and it passed both gates (measured on CLI 2.1.278, one mutation at a time,
     against this suite). Their floors are the suite's own minimums and live in
     the README beside the per-case values, read here rather than restated.
     `arm: with-only` is the second: it is the routing indicator's flag, and on
     any other grader it takes a scored verdict out of the score in silence —
     `witnesses()` honours the same flag, so the one rule that might have
     noticed stops counting the grader too. The case keeps its witness and
     simply scores one thing fewer than it reads as scoring.

  6. **The crashed-run floor, per case, per ablation.** Rules 1–5 are each a
     property of one case file. The floor is a *number*, it is the only thing a
     human reads off a run that produced no evidence, and it lived in this
     docstring measured under one flag — so it was both unverified and, in the
     `with-without` column, wrong. It is computable: `crash_floors` divides the
     absence-graders by the scored ones, twice, and reproduces all twenty
     measured values above. `evals/README.md` now declares both columns per
     case, and a declared floor that disagrees with the case's graders is an
     error. Nothing here gates on the value; the rule gates on the *claim*,
     which is what goes stale when a grader is added, removed or marked
     `with-only`.

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
# The fields that decide whether a run gets to finish. A run cut off by
# `max_turns` or `timeout_seconds` errors, and an errored run is not scored 0 —
# the harness seals the sandbox before the graders evaluate, so the
# absence-graders pass and the case reports its floor. The loader rejects `0`
# for each of these and accepts `1`, which is the same crash with a different
# spelling; `runs: 1` is the third, a single sample reported as the case's
# behaviour. Measured on CLI 2.1.278 over this suite: `max_turns: 1`,
# `timeout_seconds: 1` and `runs: 1` are each accepted by the loader at
# `--max-cost-usd 0` and by every other rule in this file. The floors
# themselves live in `evals/README.md`, beside the per-case values they are
# drawn from.
BUDGETS = {"max_turns", "timeout_seconds", "runs"}
# `arm: with-only` is the routing indicator: `tool_used` on `Skill` or `Task`,
# reporting whether the role's `description` got it selected. The flag also
# takes a grader out of the score under the default ablation, so marking any
# other grader with it deletes a verdict in silence — and `witnesses()` reads
# the same flag, so the deleted verdict is one this gate then stops counting.
ROUTERS = {"Skill", "Task"}


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


def crash_floors(graders: list[dict]) -> tuple[str, str]:
    """The score a crashed run reports, as (`--ablation none`, default).

    A crashed run's score is the share of its *scored* graders that pass by
    absence, and `arm: with-only` decides which graders those are: the default
    `with-without` keeps the routing indicator out of the score, `--ablation
    none` scores it. So one grader list has two floors, and the default — the
    column a human gets — is the higher one.
    """
    scored = [g for g in graders if g.get("arm") != "with-only"] or graders
    share = lambda gs: f"{sum(grader_kind(g) == VACUOUS for g in gs) / len(gs):.2f}"
    return share(graders), share(scored)


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


def parse_witness_table(readme: str) -> dict[str, str]:
    """Rows of `| `case-name` | `grader-name` |` — one declared witness a case."""
    return {
        spans[0]: spans[1]
        for row in readme.splitlines()
        if len(cells := split_row(row)) == 2
        and len(spans := [s for c in cells for s in code_spans(c)]) == 2
    }


def parse_floor_table(readme: str) -> dict[str, int]:
    """Rows of `| `field` | `floor` | why |` — the budget floors, from the README.

    Three cells, so the witness table's two-cell shape does not read them; one
    code span in the first cell, so the vector table's two-span head does not
    either.
    """
    floors: dict[str, int] = {}
    for row in readme.splitlines():
        cells = split_row(row)
        if len(cells) != 3:
            continue
        field, floor = code_spans(cells[0]), code_spans(cells[1])
        if len(field) == 1 and len(floor) == 1 and floor[0].isdigit():
            floors[field[0]] = int(floor[0])
    return floors


CRASH_FLOOR = re.compile(r"^\d\.\d\d$")


def parse_case_floor_table(readme: str) -> dict[str, tuple[str, str]]:
    """Rows of `| `case` | `none` | `with-without` | — the crashed-run floors.

    Three cells like the budget-floor and vector tables, told apart from both by
    the two decimals: `parse_floor_table` wants `isdigit()` in cell 1 and
    `parse_vector_table` wants two code spans and an em dash in cell 0.
    """
    return {
        case[0]: (none[0], default[0])
        for row in readme.splitlines()
        if len(cells := split_row(row)) == 3
        and len(case := code_spans(cells[0])) == 1
        and len(none := code_spans(cells[1])) == 1
        and len(default := code_spans(cells[2])) == 1
        and CRASH_FLOOR.match(none[0])
        and CRASH_FLOOR.match(default[0])
    }


HEREDOC = re.compile(
    r"^(?:cat|tee)\s+(?:-a\s+)?>>?\s*(\S+)\s*<<-?\s*'?([A-Za-z_]\w*)'?$"
)


def scaffold_fixture(script: str) -> dict[str, str]:
    """The files a scaffold writes through a heredoc, path to content.

    Every file in this suite that carries prose is written as
    `cat > <path> <<'TAG'`; the handful written with `printf` hold one line of
    code each. Reading the heredocs keeps this checker what the rest of it is —
    static, on a bare `python3`, with no shell and no temp tree — and the thing
    a pattern must not be satisfied by is the file content, never the path: a
    witness naming `412-order-total/spec.md` matches the path it asserts a read
    of, which is the assertion, not a defect.
    """
    files: dict[str, list[str]] = {}
    lines = script.splitlines()
    index = 0
    while index < len(lines):
        match = HEREDOC.match(lines[index].strip())
        index += 1
        if not match:
            continue
        path, tag = match.groups()
        body: list[str] = []
        while index < len(lines) and lines[index].strip() != tag:
            body.append(lines[index])
            index += 1
        files.setdefault(path, []).append("\n".join(body))
    return {path: "\n".join(bodies) for path, bodies in files.items()}


def check_fixture_supply(
    where, graders: list[dict], witness: str | None, script: pathlib.Path
) -> list[str]:
    """A `contains` pattern the scaffold's own workspace already satisfies.

    Skipped for the declared witness, which is allowed to be satisfied by the
    fixture — see rule 4 in the module docstring.
    """
    if not script.is_file():
        return []
    fixture = scaffold_fixture(script.read_text())
    errors = []
    for grader in graders:
        name = grader.get("name", "<unnamed>")
        if name == witness or grader.get("arm") == "with-only":
            continue
        if grader.get("type") != "regex" or grader.get("match") != "contains":
            continue
        try:
            compiled = re.compile(grader.get("pattern", ""))
        except re.error:
            continue
        for path, body in sorted(fixture.items()):
            if compiled.search(body):
                errors.append(
                    f"{where}: grader '{name}' is satisfied by {path}, which "
                    f"{script.parent.name}/{script.name} writes — every run "
                    f"that read that file is green whatever it concluded, so "
                    f"the grader scores the read and not the outcome; require "
                    f"the spelling only a correct run produces, or declare this "
                    f"grader the case's witness"
                )
                break
    return errors


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
    readme_text = readme.read_text() if readme.is_file() else ""
    vectors = parse_vector_table(readme_text)
    declared = parse_witness_table(readme_text)
    floors = parse_floor_table(readme_text)
    case_floors = parse_case_floor_table(readme_text)
    documented = set()

    for field in sorted(BUDGETS - floors.keys()):
        errors.append(
            f"{readme.relative_to(REPO)}: no floor row for '{field}' — the "
            f"value that decides whether a run finishes is unbounded below, and "
            f"a run that does not finish reports the case's floor as a score"
        )

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

        for field, floor in sorted(floors.items()):
            value = case.get(field)
            if value is None:
                errors.append(
                    f"{where}: no {field} — the harness default decides it, and "
                    f"a run cut off by it is scored by absence, not by 0"
                )
            elif not value.isdigit() or int(value) < floor:
                errors.append(
                    f"{where}: {field}: {value} is below the floor of {floor} "
                    f"README.md declares — a run that does not finish errors, "
                    f"and an errored run reports this case's absence-graders as "
                    f"passes; raise the floor with a measurement, not a case"
                )

        errors += check_scaffold(where, case, case_file.parent)
        witness = declared.get(case_file.parent.name)
        errors += check_fixture_supply(
            where,
            graders,
            witness,
            case_file.parent / (case.get("scaffold_script") or "scaffold.sh"),
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

            if grader.get("arm") == "with-only" and not (
                gtype == "tool_used" and grader.get("tool") in ROUTERS
            ):
                errors.append(
                    f"{where}: grader '{gname}' is `arm: with-only`, which is "
                    f"the routing indicator's flag — `tool_used` on "
                    f"{' or '.join(sorted(ROUTERS))}. On anything else it "
                    f"deletes a scored verdict under the default ablation, and "
                    f"nothing reports the deletion: the case still has its "
                    f"witness, so it reads as a case that scores one thing fewer"
                )

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
                # On anything but a router the `input_match` is a pattern over the
                # call's input, so it carries the same two-sided risk a `regex`
                # grader's does and earns a README row the same way.
                if tool not in ROUTERS and role:
                    errors += check_pattern(
                        where, gname, grader, vectors, key="input_match"
                    )
                    documented.add(gname)

            if gtype == "regex":
                if grader.get("target") == "trace" and "Bash" not in allowed:
                    errors.append(
                        f"{where}: grader '{gname}' scores the shell trace, but the "
                        f"case does not grant Bash — the trace cannot contain a command"
                    )
                if (
                    grader.get("target") == "trace"
                    and grader.get("match") == "not_contains"
                ):
                    errors.append(
                        f"{where}: grader '{gname}' forbids a spelling anywhere in "
                        f"`target: trace`, which is the whole message stream — the "
                        f"assistant's own prose included. Every refusal in this "
                        f"plugin tells the role to hand the forbidden command back "
                        f"to the operator, so the compliant run writes that spelling "
                        f"and fails. Score the action: `tool_used` on the tool that "
                        f"performs it, with the pattern as `input_match` and "
                        f"`min: 0`, `max: 0`"
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

        measured = crash_floors(graders)
        documented_floor = case_floors.get(case_file.parent.name)
        if documented_floor is None:
            errors.append(
                f"{readme.relative_to(REPO)}: no crashed-run floor row for case "
                f"'{case_file.parent.name}' — it is {measured[0]} under "
                f"`--ablation none` and {measured[1]} under the default "
                f"`with-without`, and that second number is what a human reads "
                f"off a run this suite cannot execute in CI"
            )
        elif documented_floor != measured:
            errors.append(
                f"{readme.relative_to(REPO)}: case "
                f"'{case_file.parent.name}' is documented as floor "
                f"{documented_floor[0]}/{documented_floor[1]} (none/default) "
                f"and its graders now give {measured[0]}/{measured[1]} — a "
                f"grader added, removed or marked `arm: with-only` moves the "
                f"floor, and the floor is the only number read off a run that "
                f"verified nothing"
            )

        scored = witnesses(graders)
        if scored and witness is None:
            errors.append(
                f"{readme.relative_to(REPO)}: no witness row for case "
                f"'{case_file.parent.name}' — which grader holds that role is "
                f"authorial intent, and it decides both the vacuity rule and "
                f"which `contains` pattern the fixture is allowed to supply"
            )
        elif witness is not None and witness not in scored:
            errors.append(
                f"{where}: '{witness}' is the witness README.md declares for "
                f"this case, and it is not a scored free grader here — it is "
                f"absent, or `arm: with-only`, or paid, or satisfied by the "
                f"empty trace; some other grader has silently taken the role"
            )
        if not scored:
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


def check_scaffold(where, case: dict, case_dir: pathlib.Path) -> list[str]:
    """The two scaffold paths the harness refuses, checked before it is asked.

    The harness resolves `context.scaffold_script` when the case *launches*, and
    refuses an escaping or missing path there — verified on CLI 2.1.278, with no
    credential and at $0.00, by:

        claude plugin eval ./plugins/<plugin> --case <case> --runs 1 \\
          --ablation none --scaffold --allow-tools Bash Edit Write Task \\
          --trust-plugin --no-publish --max-cost-usd 0.01

    which reports `path "…" escapes the case directory` / `path "…" does not
    exist` and exits 1 before the first turn. The ceiling has to be a nonzero
    cent: at `--max-cost-usd 0` the suite stops *before* any run launches, so
    nothing resolves the path — which is exactly the invocation CI uses, and why
    both of these land green and then fail for every reader who runs the suite
    for real.
    """
    script = case.get("scaffold_script")
    if not script:
        return []
    parts = pathlib.PurePosixPath(script)
    if parts.is_absolute() or ".." in parts.parts:
        return [
            f"{where}: scaffold_script '{script}' escapes the case directory "
            f"(`..` or an absolute path) — the harness refuses it at launch, and "
            f"CI's `--max-cost-usd 0` never gets that far"
        ]
    if not (case_dir / script).is_file():
        return [
            f"{where}: scaffold_script '{script}' does not exist — the case has "
            f"no workspace to build, and every grader about what the run read or "
            f"wrote is decided by that absence"
        ]
    return []


def check_pattern(
    where, gname: str, grader: dict, vectors: dict, key: str = "pattern"
) -> list[str]:
    """Run the README's two-sided vectors against the live pattern.

    `key` is the field holding it: `pattern` on a `regex` grader, `input_match`
    on a `tool_used` one.
    """
    pattern = grader.get(key)
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
