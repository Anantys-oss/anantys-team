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
README never mentions, a role whose preamble does not link `TEAM-CONTRACT.md`, a companion a
role names that is not in the tree, and either token budget the loader's own cost table puts
the plugin over. CI runs it on every push and pull request.

## Linking the contract is not optional

`TEAM-CONTRACT.md` opens *"Rules that bind **every** role in this plugin"* and *"Every role
file points here"*. Those were assertions about the tree that nothing verified — true only
because every author had so far remembered. A new role that simply never mentions the
contract was a complete, installable, green role bound by nothing.

The incentive ran the wrong way, too. The retired line ceiling counted the contract into
every role that pointed at it, so the five roles that linked it loaded 207–733 against a
limit of 200, and deleting the one line that bound a role took it under the ceiling with the
run still green: the cheapest way to satisfy that ceiling was to stop being bound. The
loader charges the contract nothing, so the incentive is gone — and this check no longer
stands on it. It stands on the first paragraph: the contract asserts the binding, and an
assertion about the tree is checkable.

The link must sit in the **preamble** — above the role's first `## ` heading. A link below
one is read when the reader reaches it, which is after the role has already acted.

A plugin with no `TEAM-CONTRACT.md` at all is a **warning**, not an error: the contract is a
file some other change lands, and a gate that reddens every branch until it arrives forces
an order on changes that have none. It is not silent either — a check whose input is absent
must say so rather than print the output of a healthy run.

## What a role costs, in the loader's own currency

A role used to be priced at **200 lines**, summed over the role file, its preamble links, the
largest `reference/` topic it named and the largest `templates/` file — justified by a single
sentence: *a role loads in full, every invocation*. Nine rounds of work refined that ceiling's
severity arms, argued over who owned its remedy, and reported a paradox: the remedy, *split
detail into `reference/`*, pointed into a directory the ceiling itself charged, so past some
size emptying the role file changed nothing and the advice was arithmetic nonsense.

Nobody measured the premise. `claude plugin details` does — it prints the loader's own cost
table, tokenized locally, with no credential and no network. Measured:

| change to a role | always-on | on invoke |
|---|---|---|
| +4000 lines in `SKILL.md` | unchanged | 950 → **73k** |
| +4000-line `reference/huge.md`, named in the role's prose | unchanged | **unchanged** |

So the premise is false twice over. A role's **body** is charged on the invocation that fires
it, not on every session. A **companion is charged nothing at all** — the loader never loads
it; the role `Read`s it at runtime, on the one action that needs it. The ceiling was in the
wrong currency *and* over the wrong population, and the paradox was an artifact of its own
accounting: against the loader the remedy works exactly as intended. Prose only `plan` needs
is not paid by `run` or `report`. That is progressive disclosure, it is the design the
platform intends, and it is not a hole to be closed by charging for it.

`check_cost` reads that table instead, and bills in the two currencies the loader does
— they are not fungible, so neither number substitutes for the other:

- **`ALWAYS_ON_MAX` (1000) over the plugin's total.** Every session with the plugin enabled
  pays this whether or not it ever invokes a role, which makes it the only truly non-optional
  cost. The column is the roles' frontmatter `description`s — what the loader shows the model
  deciding whether to fire a skill — so it is a *plugin*-level number: no single description
  is the problem, the sum is. Seven roles measure **716**, leaving room for roughly three more.
- **`ON_INVOKE_MAX` (12000) per component.** Paid once by the session that fires the role,
  against which a campaign's own spend is far larger. Loose on purpose: it bounds the preamble
  a role charges before doing any work. Six roles measure 820–2.1k; `anantys.qa` measures
  **8.6k** and is the only role this number is about.

Both are **errors**, on the test the rest of the gate uses: the remedy is wholly inside the
branch's own diff. A description and a role body are the role's own files, arriving in the
role's own change, with no other branch to wait on. The old ceiling needed an inherited-debt
arm precisely because it charged `TEAM-CONTRACT.md`, which is seven roles' at once; the
contract is in neither column here, so that arm is gone with it — and so is the merge-base
baseline the ceiling needed to tell a crossing from standing debt.

**A gate that cannot measure does not rule.** With no `claude` on `PATH` the check warns and
says so. CI installs the CLI for exactly that reason: a budget nothing measures is a number
in a docstring, which is what the 200 turned out to be.

The CLI's own `claude plugin validate .` runs in CI beside this gate, and the two do not
overlap much — it is a manifest schema check, and it accepts a skill whose frontmatter `name`
disagrees with its directory, an empty skill directory, and a marketplace entry whose
`source` points at nothing. Those stay this file's job.

### Why the companion surface is still resolved

Nothing above prices a `reference/` page, but the checker still discovers every one a role
names — see the next section. The surface is the same it always was; what changed is the
question it answers. It used to be *how much does this cost*, which the loader answers better.
It is now *does this file exist*, which the loader does not answer at all.

The two grant gates stay on `reference/` and leave `templates/` alone, and that is not an
oversight: a template is a file shape, it names no tools, and there is nothing in it to union
into a grant set. Authority and existence are different questions, and neither is cost.

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

The surface is the preamble's markdown links, the `reference/` topics the role names, and
the `templates/` the role or one of those topics names — two levels, because a role's own
split moves an action's template mention into the topic that action reads. A link a role
writes **below** its first `## ` heading is out of it. Widening discovery past the preamble is a question `check_tool_grants` and
`check_delegation_grants` answer the same way, and one gate must not widen alone. The
`docs/*.md` pages a role links from a rule body are the live case that boundary leaves
unmeasured, and closing it is a change to all three gates at once.
