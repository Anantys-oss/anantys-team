# A shared append point is a conflict edge

Measured on this repo's own queue, 2026-09-25, with `git merge-tree --write-tree` over all
153 pairs of the 18 open PRs: **14 conflicting pairs**. Every one of them was a *content*
conflict in a file two PRs both appended to — never a disagreement about what the text
should say.

Four of the fourteen were pure artifacts of where the text landed:

| pair | file | what actually collided |
|---|---|---|
| #5 ↔ #6, #5 ↔ #9, #6 ↔ #9 | `README.md` | three independent convention sections, all inserted just above `## License` |
| #11 ↔ #20 | `.gitignore` | two branches each created the file; the contents differed by `*.pyc` vs `*.py[cod]` |

Removing the anchor removed the edges — 14 → 10, with no change to what any PR asserts.

## The rule

**A file with one append point serialises every PR that has something to add to it.**
README had exactly one: the region above `## License`. So did `.gitignore` — it did not
exist, and "create it" is the same anchor for everyone.

Before adding a section to a shared file, ask how many open PRs would put their section in
the same place. If the answer is more than zero, the content wants its own path:

- A cross-cutting convention → its own file in `docs/`. README points at the directory,
  and never enumerates it again.
- A file several branches all need to create (`.gitignore`, a CI workflow) → make the
  contents byte-identical across those branches. Git merges an identical add/add clean;
  it conflicts on a one-character difference.

The remaining ten edges are the same shape one level down: each role's `SKILL.md` ends in a
single `Rules` list, and every PR that adds a rule appends to it. That is what a shared
team contract fixes — one home per rule, instead of one copy per role.
