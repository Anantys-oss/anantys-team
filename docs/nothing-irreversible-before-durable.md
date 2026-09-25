# One shared rule: nothing irreversible before it is durable

Every role here acts on real systems — a working tree, a remote, a dashboard, an accumulating
report. The rule that keeps that safe is the same in all of them:

> A role may destroy or overwrite only state it can reconstruct, or state it has already put
> somewhere durable. **Local-only work is not durable. A file you did not read is not a backup.**

What it looks like in practice:

- `/anantys.review` never pushes — so it never deletes a branch either, and never hand-closes a PR
  it merged. The merge lives in one local working tree; destroying the other copy would be the end
  of the work.
- `/anantys.qa` appends every campaign run to a log it never rewrites, and regenerates the report
  from that log. Prior runs are how a later reader recognises a re-occurrence.
- `/anantys.ops` keeps an append-only journal whose entries each carry their own KPI row, and
  regenerates `current.md` from it — refusing the overwrite when it couldn't load what it would be
  replacing.

The split is always the same: **an append-only source of truth, and a derived view that may be
regenerated.** Overwriting the derived view is free. Overwriting the log is not.
