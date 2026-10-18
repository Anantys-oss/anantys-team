# What the gates catch

Eleven `check_*.py` gates are in flight on eleven branches. CI answers one
question about each: does the branch carrying it pass it. `gate_matrix.py`
answers the harder version — does *every other head* pass it. Both measure
trees. Neither measures the gate.

A reviewer deciding what to merge has the dual question: **what is each gate
worth?** A gate earns its place by rejecting a tree a human would call broken.
One that no realistic regression can redden is inert however green its badge is,
and two gates that reject the same trees are one gate with two maintenance
costs.

`scripts/gate_power.py` measures that. It breaks `main` on purpose, fourteen
ways, and records which gates noticed.

```
python3 scripts/gate_power.py                 # full matrix
python3 scripts/gate_power.py version-drift   # one mutation
python3 scripts/gate_power.py --json          # the cells, for a diff
```

Each mutation gets its own tree: `origin/main` in a throwaway worktree, every
gate in the queue overlaid on top, the mutation committed. A gate green on
pristine `main` and red on mutation M *catches* M.

## The result, 2026-10-18

| gate | catches |
|---|---|
| `check_plugins` | 11 |
| `check_exposed_names` | 4 |
| `check_platform` | 2 |
| `check_tool_grants` | 2 |
| `check_version_bump` | 2 |
| `check_delegation_grants` | 1 |
| `check_evals`, `check_mcp_grants`, `check_tracked_ignored` | 0 |
| `check_ci_coverage`, `check_doc_actions` | red on the overlay — not asked |

Three things fall out that no single branch can see.

**`check_plugins` is the queue.** It catches eleven of fourteen, and the catches
of `check_exposed_names`, `check_platform` and `check_version_bump` are each a
subset of its own. On this mutation list those three add nothing it does not
already reject. That is a merge-order fact, not a deletion order: a subset over
fourteen mutations is evidence the narrower gate is redundant *here*, never
proof it is redundant. Merge the wider gate first and the queue's floor arrives
in one PR.

**Three gates are unreached.** `check_evals`, `check_mcp_grants` and
`check_tracked_ignored` rule on things no mutation here touches — eval configs,
browser grants, the ignore file. That is a gap in the mutation list, and the
honest reading of a zero is "add a mutation", not "drop the gate". Each new
mutation is three lines in `MUTATIONS`.

**One regression nothing blocks.** `silent-grant-widening` — a role quietly
adding `BashOutput` to its `allowed-tools` — is reported by `check_tool_grants`
as a *warning*, deliberately: a grant the prose never names is often a browser
primitive used implicitly, and erroring on it would be noise. The consequence is
that a new unaudited capability cannot redden any gate in the queue. Whether
that is the right trade is a judgement about this product, which is why the
matrix reports it rather than fixing it.

A fourteenth mutation used to be blind too. `ungranted-tool` — a step reading
"use `WebFetch` to post the report" on a role granted no `WebFetch` — passed
every gate, because `check_tool_grants` implemented its first direction for two
vocabularies, mcp tool names and shell commands, and both anchor on a lowercase
first character. First-party tool names start with a capital and fell between
them. `FIRST_PARTY` closes that; the matrix is how the hole was found.

## Reading a cell

Every catch prints the gate's first complaint, because an exit code is a
coordinate and not a finding. The complaint is also the only check on the
method: a gate can redden on a mutation while objecting to something else
entirely. Three of the catches above are tracebacks rather than diagnoses —
`check_version_bump` dies with `FileNotFoundError` on a broken `source` path,
and two gates die inside `json.load` on a trailing comma. CI still blocks, so
they count; a reviewer handed the traceback learns less than the gate knows.

Two gates are red on the overlay and so were never asked anything.
`check_ci_coverage` reports that `check_exposed_names.py` has no workflow
running it, and `check_doc_actions` reports a `qa` action missing from the
README's command block. Both are properties of the *assembled* queue, not of
`main` and not of any one branch: the overlay takes the newest commit of each
file, so a gate and the workflow meant to run it can arrive from different
heads. That is what merging the queue as it stands would produce.

## Why a version bump rides along

`check_version_bump` demands a bump whenever product content changes. Without
paying that toll, every mutation reddens it, and the matrix reports a gate that
"catches" a deleted template by complaining about a version. So each mutation
bumps both manifests. A red cell then means the gate objected to the mutation
and not to the housekeeping around it — `version-drift`, which bumps one
manifest of the two, opts out and is the only cell where that gate fires.

## Adding a mutation

Three lines, keyed by name, in `MUTATIONS`:

```python
"skill-count-drift": [
    (PLUGIN, "5 skills (/anantys.design", "6 skills (/anantys.design"),
    (MARKET, "5 skills (/anantys.design", "6 skills (/anantys.design"),
],
```

`(path, old, new)`; `old=None` appends, `new=None` deletes the file. An anchor
that matches nothing is fatal rather than a no-op — a typo in an anchor would
otherwise be recorded as a blind spot the gates invented.

Keep them dull. Exotic breakage proves nothing about a gate; these fourteen are
regressions this repo has actually shipped, or is one careless edit away from.
