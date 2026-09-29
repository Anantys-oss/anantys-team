# A file a role writes is tracked or ignored — never neither

Two of these roles write into the operator's repository, not just into the conversation:

| role | writes |
|---|---|
| `anantys.qa` | `.anantys/qa.md`, and per campaign `.anantys/qa/<slug>/{qa-plan,qa-report,qa-runs}.md` |
| `anantys.ops` | `.anantys/ops.md`, `<workspace>/{current.md,rulings.md}`, `<workspace>/journal/<date>-analysis.md` |

Search the plugin for what git is supposed to do with any of them:

```
$ grep -rniE 'gitignore|untracked|commit (the|this) file' plugins/
$
```

Nothing. Every one of those paths lands in a working tree in the third state — **present,
unmentioned, and untracked** — which is not a neutral default. It is the one state in which a
file is invisible to every mechanism that would otherwise protect it:

- **It survives `git checkout`.** `/anantys.review` checks the branch under review into the
  working tree, merges the base, and ends on `<base>`. An untracked `qa-report.md` written
  against the branch rides along through all of it and is still sitting there after the PR is
  closed. Its content pins the branch and commit it was taken on; its *location* now claims
  otherwise, and location is what the next reader sees first.
- **It stops `/anantys.review` before it starts.** Pre-flight step 1 requires a clean tree and
  STOPs otherwise, offering *commit or stash*. After any QA campaign in the same repo the tree
  is dirty, and both offers are wrong: committing puts the QA report inside the diff the review
  exists to summarise, and stashing removes the only copy of an append-only log —
  [the destructive branch](./nothing-irreversible-before-durable.md) of this repo's own rule.
- **It is not there for the next context.** `.anantys/<skill>.md` exists so a role can read the
  project's facts instead of asking for them — the case that motivates it being the dispatched
  one, which has nobody to ask. A fresh clone, a CI checkout and a second worktree each get a
  repo with no config file, and the role halts on an interview it was written to make
  unnecessary. The argument for the file's existence is an argument for committing it.

## The rule

> **A role names the git status of every file it writes, and there are only two answers.**
> Tracked, or listed in `.gitignore` by the same change that starts writing it. A path in
> neither is a defect, not a default.

Which answer is not a preference. The `.anantys/<skill>.md` convention already sorts what may be
written by what it is a property of: a property of the **project** outlives the run, so it
persists for everyone who clones the repo — tracked. A property of the **run** is not written
down at all. There is no third class, so in practice:

- `.anantys/**` is **tracked**, config and campaign artifacts alike. The operator commits it;
  the role says so when it creates it.
- A role that wants scratch space writes **outside the repo** (`$TMPDIR`), where nothing can
  mistake it for work.
- `.gitignore` is therefore where nothing a role writes belongs — if a path wants to be ignored,
  it wanted to be a temp file.

## What it costs the roles

One sentence each, at the point of the write, naming the status. The one that is not a sentence
is `/anantys.review`'s Pre-flight: a pending change to a team artifact is not review state, and
"commit or stash" is the wrong pair of options for it. That narrowing lands in the role, not
here.
