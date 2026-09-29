# `today` is read, never recalled — the evidence for `ops` Phase 0a

Maintenance note for `plugins/anantys-team-agents/skills/anantys.ops/SKILL.md`. Nothing
loads this file; it records what was measured, and why the rule landed inline in one role
rather than in the team contract.

## The measurement

Across all 28 open heads plus `main` — 29 refs, whole tree, not added lines only:

| phrasing | hits |
|---|---|
| `date \+%\|`date`\|system clock\|current date` | **0** |
| control — `screenshot` | 685 |
| control — `read from\|unreadable` | 64 |
| control — a string that does not exist | 0 |

Ten date-shaped placeholders exist in the plugin tree and not one of them names a source:

| file | placeholders |
|---|---|
| `anantys.ops/SKILL.md` | `Date: <today>`, `journal/<YYYY-MM-DD>-analysis.md`, `Last audit: <YYYY-MM-DD>` |
| `anantys.ops/templates/ops-rulings.md` | `Ruled: <YYYY-MM-DD>`, `superseded by R<m> on <YYYY-MM-DD>` |
| `anantys.qa/templates/qa-plan.md` | `Run <n> — <date>`, two `Adjudicated <date>` |
| `anantys.qa/templates/qa-config.md` | `Last updated: <YYYY-MM-DD>` |
| `anantys.qa/templates/feature-brief.md` | `Assembled <YYYY-MM-DD>` |

The two date-writing roles fail differently, and `ops` fails worse. `qa` grants plain
`Bash`, so it *can* run `date` and is simply never told to. `ops` narrows its grant to
`Bash(mkdir:*), Bash(git:*), Bash(ls:*)` — so the role that computes with dates could not
read one even if it tried. Phase 0a therefore lands with `Bash(date:*)` added to the grant;
an instruction to run an ungranted command is the defect `scripts/check_tool_grants.py`
exists to catch, and it only inspects grant→prose.

## Why `ops`, and why inline

A wrong date is a dated record in eight of those ten places — bad, bounded, visible to a
human reading the file. In `ops` it is an **operand**. Phase 1c computes

    E = today − `Last audit:` in current.md

and sets every dashboard to an `E`-day range. Both operands are model-supplied strings, and
the second one is *this rule's own output from the previous run*. So the failure compounds
along a path no reader crosses:

1. Run *n* recalls a date. Phase 6 writes it to `Last audit:`; Phase 5 names the journal
   file after it.
2. Run *n+1* subtracts it. Every delta in the report is rescaled by the error — and Phase
   1c's whole argument is that a delta means nothing unless its windows are equal and
   adjacent, which is exactly what the subtraction is supposed to guarantee.
3. Phase 0 step 2 reads "the last 3 journal entries" by name, so a wrong filename reorders
   its own history. `#41`'s rulings lapse against the same clock; `#42` grades the previous
   audit's advice against it.

It binds two roles — `ops` and `qa` — which is below the contract's three-role threshold,
so it stays inline in the role where it is load-bearing. `docs/a-stop-is-a-result.md`
measured `TEAM-CONTRACT.md`'s remaining headroom at **8 lines** and spent them; this rule
could not have gone there regardless, and pretending otherwise would have pushed a second
role over the ceiling to buy breadth this rule does not need.

## The precedent it generalises

`qa` already holds the general form for a different fact. `qa-plan.md` records

> `Recorded under: anantys-team-agents v<running version, read from
> .claude-plugin/plugin.json; unknown if unreadable>`

— a recorded fact that names its source and carries an explicit value for an unreadable
source. Phase 0a is that same shape applied to the one fact nobody applied it to. The
`unknown` half matters as much as the source half: `date` failing is not a licence to
recall, it is a licence to say the date is unknown and skip the comparisons, which Phase 0
already does when no prior audit exists.

## Why a recalled date is the hiding kind of invented value

C1 forbids inventing a value to fill a gap and asks for uncertainty flagged at the point of
the claim. Both halves fail silently here. A recalled date is well-formed, plausible and
unfalsifiable inside the run, so nothing prompts the flag; and the only reader that could
catch it is the next audit, which does not check it — it subtracts it.

## The cost, measured

`scripts/check_plugins.py` on the wave-1 union, before and after. Phase 0a adds 16 lines to
one role file and none to any shared file:

| role | before | after |
|---|---|---|
| `ops` | 326 | 342 |
| `design` | 212 | 212 |
| `review` | 262 | 262 |
| `qa` | 250 | 250 |
| `debug` | 181 | 181 |

4 warnings before, 4 after — `ops` was already the furthest over the 200-line ceiling and
this makes it worse; it introduces no new warning. All six gates and `unittest discover -s
scripts` are green on the union with this change. The alternative — the contract — would
have added the same 16 lines to all seven roles and pushed `design` further past a ceiling
it only just crossed.

## The conflict cost, measured

`git merge-tree --write-tree` against all 27 other open heads, before and after:

| | edges |
|---|---|
| `#39` head as-is | 1 (`#42`) |
| with Phase 0a | 3 (`#42`, `#9`, `#31`) |

The prose block adds none — it is a new section between `Phase 0` and `Pre-flight`, distant
from every other head's hunks, and the `docs/` page is a new path. **Both added edges come
from the one-word grant edit on line 4.** That line is already a forced merge point without
me: `#9` deletes `Bash(git:*)` and `#31` narrows it to three subcommands, and those two
conflict with each other today. Adding `Bash(date:*)` puts a third value on a line that
cannot auto-merge in any case. The alternative is to ship the instruction without the
grant, which is a rule that cannot execute.

## Deliberately not here

- **`qa`'s eight placeholders.** The same rule applies to them and is not written there.
  `anantys.qa/SKILL.md` is edited by three open heads and its templates by two more;
  stating the rule in both roles costs conflict edges for a case where the failure is a
  dated record rather than a rescaled measurement. When `qa` next lands a change in its
  templates, the line belongs with it — and if a third role grows a date, the rule has met
  the contract's threshold and should move there instead.
- **A gate on it.** Nothing can check from the text whether a date was read or recalled.
