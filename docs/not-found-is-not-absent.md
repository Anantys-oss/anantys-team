# Not found is not absent

A role that keeps history across invocations starts by looking for its own prior artifact. When the
look comes up empty, the role concludes *this is the first time* — and that conclusion licenses the
most destructive thing the role can do: write the artifact from scratch.

The two states are not the same, and no role in this repo distinguished them.

## The shape

| what happened | what the role sees | what it concludes | what it does |
|---|---|---|---|
| no campaign has ever run | glob matches nothing | first run | writes a fresh artifact ✅ |
| invoked from a subdirectory | glob matches nothing | first run | **overwrites nothing, starts a parallel history** |
| detached HEAD / renamed branch | branch name matches no dir | first run | **same** |
| mistyped `<slug>` | named dir absent | first run | **same** |
| fresh worktree / shallow clone | artifact not checked out | first run | **same** |
| another feature normalizes to the same slug | dir present, plan tracked | **found** | **regenerates a stranger's plan over its adjudication history** |

Only the first row is a first run. The next four are lookup failures wearing its clothes, and the
role cannot tell them apart because it asked the filesystem a question the filesystem cannot answer.

The last row is the dual, and it is the one this document nearly missed: a lookup that **succeeds**
and returns the wrong thing. Everything below about proving an absence is silent about it, because
the proof it prescribes — ask git — comes back green.

## Why it was invisible

`anantys.qa`'s "Locating the feature" section is careful in both the directions anyone reviews. It
fails closed on **ambiguity** ("never guess between two, ask") and on the **wrong candidate** ("never
fall back to `specs_dir` … a spec dir sharing the PR's branch name is a different, stale campaign").
It is silent on **zero candidates** — the only one of the three whose default action is destructive.

The section even names this exact failure once, for one cause: an un-normalized slashed branch "would
write the campaign to a directory the discovery rule below cannot find, orphaning the plan and its
run history." The cause got patched. The consequence did not, so every other route to the same
not-found state still ends in a regenerated plan.

That is the general lesson. When a lookup can fail for several reasons, patching the reason you
happened to hit leaves the others live. Handle the **state**, not the cause.

## The fourth state: found, and wrong

Three states, and the section above credits itself with two of them: ambiguity ("never guess between
two, ask") and the wrong candidate ("never fall back to `specs_dir`"). Zero candidates is what this
document closes. There is a fourth, and the patch that closed the *cause* in row four is what
manufactured it.

A `<slug>` is normalized — "lowercase, then every run of non-alphanumeric characters — `/` included —
becomes a single `-`". That map is **many-to-one**. `feat/checkout` and `feat-checkout` are the same
directory. So are `SKU-231` and a brief titled `SKU 231`, and so are the two spellings anyone lands
on when a branch convention changes mid-project. The normalization exists so that a re-run finds its
own directory; the same property makes a different feature find it too.

That is worse than not-found, for one reason: **the absence proof passes.** Step 2 below asks git
whether a plan is tracked. In a collision it is — the wrong one. The guard reads green at the one
moment the role is holding a stranger's `qa-runs.md`, and `plan` regenerates `qa-plan.md` whole. The
closed-defect history that backs *"a defect is never re-filed twice"* survives the overwrite and is
now scoring a feature it never saw.

The other qa guard is the tell. `never fall back to specs_dir … a spec dir sharing the PR's branch
name is a different, stale campaign` is this exact defect, correctly diagnosed — and guarded only
across the `specs/` ⇄ `.anantys/qa/` boundary. Inside `.anantys/qa/`, a name-sharing directory is
accepted without a question.

The general form is not qa-specific: any role that derives a durable path from project state is
making a claim about identity, and a derived name that already exists is the moment to check the
claim rather than the moment to write. `anantys.ops` derives its journal entry the same way, from a
date.

**The rule.** A directory name is a lookup key, never an identity. So the identity has to be written
down: the feature directory records the value its slug was derived from, verbatim and
un-normalized. `plan` reads that record **before** it copies anything over it, and a recorded source
that disagrees with the one in hand is not this campaign — name both and stop, rather than picking
the one that happens to be on disk. Every action after `plan` matches on the record, not on the
normalized branch name.

Nothing here is a second identifier. The value is already what the slug was computed from; the
defect is that only the lossy output of that computation was ever kept.

## The rule

Two steps, in this order, before any role treats not-found as absent:

1. **Anchor, then look.** Durable paths resolve from the repo root (`git rev-parse --show-toplevel`),
   never the current working directory. A relative path in a contract is a path whose meaning depends
   on who invoked the role. If the repo root cannot be determined, ask the operator — do not search
   from the cwd.
2. **Ask git, not just the filesystem.** Git knows what the project has had; the working tree only
   knows what is there now. If git tracks an artifact that discovery did not surface, the artifact
   exists and was not found: name the path found and the path expected, and **stop**.

Step 2 is what makes the distinction decidable, and it is why the artifacts have to be committed.
`.anantys/qa.md` already was. `qa-plan.md`, `qa-runs.md` and `qa-report.md` are now stated to be —
an untracked highest-value artifact is one `git clean` from gone, and an untracked one gives step 2
nothing to answer with.

## Applying it

- **`anantys.qa`** — stated under `## Actions`, beside the inference it corrects
  (`no qa-plan.md → plan`), and binding on every action including the feature-directory discovery. A
  named `<slug>` whose directory is missing is a typo, not a new campaign; never create the directory
  to resolve it.
- **`anantys.ops`** — "first audit" is earned, not defaulted. Phase 6 overwrites `current.md` whole
  and rebuilds the Audit History from the previous copy, so a wrong first-audit call drops every
  past row and every pending action's age.

## Where this does not apply

A role reading an *optional* input it does not own — `anantys.design` discovering a style guide,
`anantys.qa` reading `README.md` during `init` — may treat not-found as absent. The distinction only
matters when the artifact is the role's **own prior output**, because only then does a wrong answer
license the role to replace history it should have extended.

## Placement

Measured with `git merge-tree --write-tree` against all 19 open heads, three placements for the
`anantys.qa` block: the end of "Locating the feature" (1 conflict edge), a new section after Mission
(3 edges — the top of the file is where #8 and #17 both insert), and beside the Actions table
(1 edge). One is the floor: #5 rewrites the whole file body below the Actions table, so any insertion
in `anantys.qa/SKILL.md` collides with it. The resolution is mechanical — the block moves verbatim,
and the discovery prose it refers to now lives in `reference/sources.md`.

`anantys.ops` adds one, on its `allowed-tools` line, and it is the useful kind. The absence proof
runs three git subcommands; ops held `Bash(git:*)`, and #9 removes it outright, so the union of #9
and this change would have ops calling git with no git grant. `check_tool_grants` is green on that
union — its prose-to-grant direction catches browser and Task tools, not Bash subcommands — which is
the reminder that a green gate is not the union working. The grant is narrowed here to
`Bash(git rev-parse:*)`, `Bash(git log:*)`, `Bash(git ls-files:*)`: strictly less than main, so a
reduction either way, and the branch is coherent alone. Resolution against #9 is to take the narrow
list.

The new doc adds zero edges.

## Not done

No static gate. The property is "a durable path is anchored", which reads as prose intent rather
than as a checkable token; a five-role repo does not earn a heuristic checker that would flag every
literal path in every file. Revisit if a third role grows a prior-artifact lookup, or if one of these
two regresses in review.
