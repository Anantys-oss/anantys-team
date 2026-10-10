# Adding a role


`marketplace.json` duplicates the plugin's name, version and description, and this README
enumerates every role — three places that silently go stale when a role is added or a
version bumped. Run the checker before pushing (stdlib only, no install):

```bash
python3 scripts/check_plugins.py
```

It fails on: a version/name/description mismatch between the two manifests, a skill whose
frontmatter `name` doesn't match its directory, an agent missing `name`/`description`/
`tools`/`model`, a role count in the description that the tree contradicts, a role the
README never mentions, and a role whose preamble does not link `TEAM-CONTRACT.md`. CI runs
it on every push and pull request.

## Linking the contract is not optional

`TEAM-CONTRACT.md` opens *"Rules that bind **every** role in this plugin"* and *"Every role
file points here"*. Those were assertions about the tree that nothing verified — true only
because every author had so far remembered. A new role that simply never mentions the
contract was a complete, installable, green role bound by nothing.

The incentive ran the wrong way, too. The contract counts toward the ceiling below, so the
five roles that point at it load 207–733 against a limit of 200. Deleting the one line that
binds each of them takes three under the ceiling and leaves the run green: the cheapest way
to satisfy the ceiling was to stop being bound. The ceiling may make a role shorter; it may
not make it unbound, so the link is now an error to omit and the warning's remedy says so.

The link must sit in the **preamble** — above the role's first `## ` heading. A link below
one is read when the reader reaches it, which is after the role has already acted; the check
measures the same region `check_load` does, for the same reason.

A plugin with no `TEAM-CONTRACT.md` at all is a **warning**, not an error: the contract is a
file some other change lands, and a gate that reddens every branch until it arrives forces
an order on changes that have none. It is not silent either — a check whose input is absent
must say so rather than print the output of a healthy run.

**A clause is what it says, not the heading a role cites.** `check_contract_clauses` held
the clause *labels*: deleting or relabelling `## C2` is an error, because `C2` is what the
role files cite. Keeping both headings and deleting the 95 lines under them left the label
set identical — and that is the same unbinding, reached by the one route the check did not
look down. It is also the profitable one. The contract is what puts `anantys.design` (221),
`anantys.ops` (238) and `anantys.spec-tester` (204) over the ceiling below, so gutting it
turned five load warnings into one, reading *"loads 668 lines, down from 754"*. Relabelling
one clause errors; emptying every clause was reported as the roles getting better.

So an emptied clause is an error too. A shrink *short* of empty is a **warning**: content
legitimately moves out of this file — the candidates split moved 400 lines — and a gate
whose remedy is "put the lines back" would forbid the split it asked for. Silence is what it
may not be, because the only other check that reads these lines reports losing them as an
improvement, so the warning names the clause and the delta.

A role over 200 lines is loaded in full on every invocation, so past that size the per-action
detail belongs in a `reference/` page the actions table links to — and that page is counted
too, see below.

**Taking a role over the ceiling is an error; finding it there is a warning.** The checker
prices the load against the merge-base so it can tell those apart, and for a while the
distinction changed only the wording of a warning. Measured over the open queue, four
branches each take a role that is *clean at the base* past the ceiling on their own —
`anantys.design` 115 → 261 and 115 → 221, `anantys.ops` 131 → 204, 131 → 213, 131 → 238 —
and ten more add to `anantys.qa`, already at 648, one of them by 253 lines. Every one of
those runs exits 0. A ceiling nothing ever fails is a number in a docstring.

So the line is the one the contract-clause and version-bump gates already draw: a regression
is an error, inherited debt is a warning. A crossing is a regression, and it is wholly inside
the branch's own diff — the role, its `reference/` pages and its `templates/` all arrive in
the same change, so the remedy is available on that branch and there is no other branch to
wait on. That is the same test the dangling-companion error earns below. Growth above a
ceiling the base already broke is *not* this branch's regression; it stays a warning until
the head that splits the role lands, and the gate then holds the result.

**The 200 is a ceiling on the load, not on the file.** A role's preamble — everything above
its first `## ` heading — is where it names what binds it before it acts, so every local
`.md` it links there is read on the same invocation and counts toward the total. The checker
discovers those from the links, never from a filename: a role that points somewhere else is
measured against what it actually points at, and one that points nowhere is measured on
itself alone, exactly as before. The warning prints the breakdown, so the file to shrink is
visible without reopening any of them.

That distinction is not hypothetical. All seven roles open by linking a shared contract and
saying *"read it before acting"*; at 502 lines it made every one of them — including two
under 100 lines of their own — invoke at between 578 and 733 against a ceiling of 200, while
the checker reported one warning, for the one file that was individually long. A ceiling
measured on the wrong unit reads as compliance.

**The remedy is inside the unit, not outside it.** `reference/` is where this page sends
the detail, so it is where the load goes — a ceiling that stopped at the always-loaded set
would be satisfiable by relocating prose into a file every action still reads. So the total
also carries the **largest** `reference/*.md` the role names: an action reads one topic on
top of the always-loaded set, and a ceiling is a worst-case bound. Splitting into several
small topics lowers the measured load; moving the same prose into one big topic file does
not. `check_tool_grants` and `check_delegation_grants` already read these files, for the
same reason and with the same backticked-path convention; this is the gate that prices them.

**`templates/` is read on the same invocation, so it is charged the same way.** The reason
written beside the 200 is that *a role loads in full, every invocation* — and a template an
action is told to *follow* satisfies that reason exactly. It was not priced. `anantys.qa`'s
`plan` step says *"Write `qa-plan.md` following `templates/qa-plan.md`"*, a file that on the
assembled queue runs to 229 lines, longer than the whole ceiling, against a role the gate
reported at 513. Any directory whose files an action reads is a place the prose can go, so
the escape is closed by **directory, not by file**: the total carries the largest named
`reference/*.md` *and* the largest named `templates/*.md`. They sum rather than compete —
one action reads at most one of each, but it can read both.

**A directory is only closed if the mention is scanned where it is written.** The rule above
was applied to the role file alone, and that is not where a template is named: the action
told to follow one is the action whose detail the split moved into `reference/`, so the
mention went with it. `anantys.qa` names none of its three templates in `SKILL.md` — `plan`
names `templates/qa-plan.md` from `reference/sources.md`, `init` names `templates/qa-config.md`
from `reference/init.md` — so the arm that this page introduced, citing that exact `plan`
sentence, charged nothing on the one role it was written for. On the queue as it assembles
today the gate reported `anantys.qa` at **283** (153 + 130 `reference/sources.md`) where its
`plan` action reads **491**, the 208-line `templates/qa-plan.md` uncharged; unsplit
`anantys.ops` was charged normally. Templates are therefore discovered in the role **plus
the topics it names**, and the escape is worth stating plainly: this check's own remedy is
the thing that hid the mention, so the arm switched off at exactly the load it exists to
price.

Topic discovery stays one level deep — a `reference/` page naming another is a question the
two grant gates answer the same way, and one gate must not widen alone. There is no
directory glob either: every companion on disk is named today, and those gates already warn
about a `reference/` file no action names.

The two grant gates stay on `reference/` alone, and that is not an oversight: a template is
a file shape, it names no tools, and there is nothing in it to union into a grant set. Load
is a claim about bytes; authority is not. The units genuinely differ here, which is why this
page says so rather than leaving the next reader to call it an inconsistency.

It is a floor, not an exact load: an action that reads two topic files pays for both, and
the checker charges one. Measured on the assembled queue, `anantys.qa` — the only split
role today — invokes at 385 (160 + 95 contract + 130 `reference/sources.md`) where the
always-loaded set alone reported 255. No individual branch shows this: the split lands on
one head, the contract on another, and this checker on a third.

## A companion you name has to be there

Everything above discovers a companion by resolving a path the role wrote, and every one of
those sites moves on when the file is absent. That makes **named but absent** the same state
as **not named**, and the two are opposite failures: the first is a role whose action reads
nothing where it says it reads a page, the second is a role with nothing to say. Only the
second was ever reported.

`check_tool_grants` is blind to it from the other end, and for a reason worth stating. It
builds a skill's prose surface by globbing `reference/*.md` **on disk** and reporting the
pages no action names — the orphan direction — so a name with no file is one its loop never
visits. Delete a topic page and leave its citation in `SKILL.md` and all seven gates pass.
The one line that moves is worse than silence: `grants `AskUserQuestion` but the prose never
mentions it`, which names the *grant* as the suspect when the defect is that the page
documenting the need is gone, and whose remedy — drop the grant — removes a capability the
role still uses. Cite a page that was never created at all and nothing anywhere prints.

So the dangling direction lives here, where the names are iterated, exactly as the orphan
direction lives there, where the files are. It is an **error**, not a warning: a companion
sits inside the role's own directory and arrives in the role's own change, so there is no
other branch for it to be waiting on — the absent-input rule the contract check follows does
not apply — and a role shipped with a dead citation is broken for the user who installs it
whatever tree it came from. Across every open head today zero citations dangle, so this
reddens nothing: it is a regression gate with live input, not one waiting for its input to
land.

The surface is exactly the one `measured_load` resolves — the preamble's markdown links, the
`reference/` topics the role names, and the `templates/` the role or one of those topics
names. A link a role writes **below** its first `## ` heading is out of it, as it is out of
the ceiling above. Widening discovery past the preamble is a question `check_tool_grants` and
`check_delegation_grants` answer the same way, and one gate must not widen alone. The
`docs/*.md` pages a role links from a rule body are the live case that boundary leaves
unmeasured, and closing it is a change to all three gates at once.
