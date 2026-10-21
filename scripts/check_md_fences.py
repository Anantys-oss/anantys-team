#!/usr/bin/env python3
"""Hold every markdown file to a fence structure that means what it looks like.

Three of this repo's four role templates wrap the artifact they describe in one
fenced block, so a reader sees the shape and not a document pretending to *be*
one. `templates/qa-config.md` wraps 105 lines that way and contains five
``` ```bash ``` blocks of its own — and three backticks cannot nest inside three
backticks. Measured with a CommonMark parser, that file parsed as **six** blocks
instead of one, the outer block ending at its first inner closer:

    templates/feature-brief.md    1 fence   1 heading
    templates/qa-plan.md          2 fences  2 headings
    templates/qa-config.md        6 fences  13 headings   <- 12 of them leaked

The 12 extra headings are the giveaway. `## Environment: staging`, two
`### Credentials`, `### Reset — NONE` — template *content* promoted into the
document's own outline, because the lines between one stray closer and the next
opener render as live prose. Half the file rendered as instructions to the
reader; the other half rendered as code it was never meant to be. The fix is one
character twice: a four-backtick outer fence, which three-backtick blocks nest
inside legally.

This is not only a rendering defect, which is why it is worth a gate. Four
scripts in this directory partition a markdown file by fence to decide which
lines they may read:

    check_plugins.py       FENCED = re.compile(r"^```.*?^```", re.S | re.M)
    check_doc_actions.py   toggles on any line starting with ```
    check_tool_grants.py   BASH_FENCE pairs ```bash ... ```
    ownership_map.py       FENCE = re.compile(r"^\\s*(```|~~~)")

Every one of them pairs fences by **position parity**. On a file with no nesting
parity and CommonMark agree, so the shortcut is sound and no test ever caught
it. On `qa-config.md` they disagreed about 32 consecutive lines — the regex
stripped the staging block as code while CommonMark rendered it as prose.

Be precise about what the fix buys, because the obvious claim is false and was
written here before a test contradicted it: **a four-backtick outer fence fixes
the rendering and does not fix parity.** `^```` still matches a four-backtick
line and still stops at the inner ``` ```bash ``` , so parity reads the repaired
file as two blocks where CommonMark reads one, and the lines between the inner
closer and the outer one fall outside both of parity's pairs. The divergence
shrinks from 32 lines to a handful; it does not reach zero. `test_check_md_fences`
asserts that, rather than the tidier thing.

What makes that survivable rather than a second defect is *which* files the
parity readers point at, measured on this tree: `check_plugins` strips fences in
`README.md` alone, `check_doc_actions` in `*/skills/*/SKILL.md`, `check_tool_grants`
in role files, `ownership_map` in whatever head it is given. None of them reads a
`templates/` file through a parity partition, and no role file in this tree nests
fences at all — so the one file where parity is wrong is a file no gate parses
that way. Verified by running the other ten gates before and after the fix:
byte-identical output, except `check_ci_coverage`'s own count going 10 -> 11,
which this file caused by existing and the fix did not. The divergence is latent,
and this gate is what keeps it latent, by refusing the nesting that creates it in
a file some future gate might read.

## What is checked

Two findings, both errors, because both remedies are one edit inside the file
the finding names — no other branch to wait on, the line `check_contract_clauses`
and `check_version_bump` already draw.

- **A fence opener inside a fence of the same delimiter, at a length that
  cannot nest.** The author meant nesting; the delimiter cannot express it.
  CommonMark keeps an info-bearing line as content and ends the block at the
  next *bare* run instead, so the block boundaries land somewhere nobody wrote.
  Remedy: lengthen the outer fence.
- **A fence never closed before end of file.** Everything after it is code,
  including the headings a reader navigates by.

A bare closing run never reaches the first check, by construction: CommonMark
consumes it as the closer, so it is not content. That is what makes the check
precise rather than a heuristic about backticks — the only lines it can ever
flag are openers that carry an info string, and a literal ``` ```bash ``` inside
a three-backtick block is not something a writer can mean.

## Why not a markdown library

The sibling gates are stdlib-only and CI installs nothing. The fence rules this
needs are small and closed: CommonMark 4.5 says an opener is a run of at least
three backticks or tildes, indented at most three spaces; a closer is a run of
the *same* character, at least as long, with nothing but whitespace after it;
and a backtick info string may not itself contain a backtick. That is the whole
specification, and `scan` below is it.

Usage: python3 scripts/check_md_fences.py [root]
Exit 1 on errors.
"""

import re
import sys
from pathlib import Path

# Named, not shape-matched, for the reason `check_exposed_names.SKIP_PARTS`
# records: a guard phrased as "skip hidden directories" drops `.claude-plugin/`,
# which is tree nobody meant to exempt.
SKIP_PARTS = {".git", "__pycache__", "node_modules"}

#: A fence delimiter line: up to three spaces of indent, then a run of one
#: delimiter character, then the info string. Groups: indent, run, info.
FENCE = re.compile(r"^( {0,3})(`{3,}|~{3,})(.*)$")


def fences(text):
    """Yield every fence block in `text` as (open_line, close_line, run, content).

    Line numbers are 1-based. `close_line` is None for a block the file never
    closes. `content` is the lines strictly between the delimiters.

    The three rules that matter, and they are the only three: a closer uses the
    same character as its opener, is at least as long, and carries nothing but
    whitespace. A line that fails any of them is content — which is precisely
    why an inner ``` ```bash ``` does not end the block it appears in, and why
    the resulting boundaries surprise the author.
    """
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        start = FENCE.match(lines[i])
        if not start:
            i += 1
            continue
        run = start.group(2)
        # A backtick info string may not contain a backtick (CommonMark 4.5), so
        # ```` ```` is a closer-shaped line, never an opener with "`" as info.
        if run[0] == "`" and "`" in start.group(3):
            i += 1
            continue
        body = []
        j = i + 1
        while j < len(lines):
            end = FENCE.match(lines[j])
            if end and end.group(2)[0] == run[0] and len(end.group(2)) >= len(run) and not end.group(3).strip():
                break
            body.append(lines[j])
            j += 1
        yield i + 1, (j + 1 if j < len(lines) else None), run, body
        i = j + 1


def problems(rel, text):
    """Yield one message per finding in a single file."""
    for opened, closed, run, body in fences(text):
        if closed is None:
            yield (
                f"{rel}:{opened}: a `{run}` fence is never closed — every line after it "
                "is code, headings included"
            )
            continue
        for offset, line in enumerate(body, start=opened + 1):
            inner = FENCE.match(line)
            if not inner or inner.group(2)[0] != run[0] or len(inner.group(2)) < len(run):
                continue
            yield (
                f"{rel}:{offset}: `{inner.group(2)}{inner.group(3).strip()}` opens a fence inside "
                f"the `{run}` fence at line {opened}, which cannot nest at that length — the block "
                f"ends somewhere nobody wrote it. Lengthen the outer fence to "
                f"`{run[0] * (len(run) + 1)}`"
            )


def main(root):
    files = sorted(
        p for p in root.glob("**/*.md") if not SKIP_PARTS.intersection(p.parts)
    )
    errors = []
    for path in files:
        errors += list(problems(path.relative_to(root), path.read_text(encoding="utf-8")))

    for error in errors:
        print(f"ERROR {error}")
    print(f"{len(files)} markdown file(s) read")
    print("fence check: FAILED" if errors else "fence check: OK")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()))
