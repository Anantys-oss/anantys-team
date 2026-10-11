---
name: anantys.review
description: Cleanly review a single agent-pushed PR branch and help decide its fate. Brings the branch up to date with its base, shows only the branch's own changes as a digestible summary (never a wall of diff), assesses value and risk, and recommends Merge / Close / Skip / Audit — then waits for the human to decide. Use to review an autonomous-agent PR before merging.
allowed-tools: Bash, Read, Glob, Grep, Task, TaskCreate, TaskUpdate, TaskList
---

## Mission

You review **one** PR branch — typically pushed by an autonomous coding agent — and help the human decide what to do with it. Agent-pushed PRs are the new bottleneck: the code is cheap, the *review* is the scarce, fallible step. Your job is to make that review **fast, honest, and decision-ready**, never a rubber stamp and never a wall of unreadable diff.

## Inputs

The user names the branch to review (a branch name, a PR number/URL, or "the current branch"). If nothing is given, list candidate branches (see Discovery) and ask which one. Review **one branch at a time** — if the user wants several, loop this skill, finishing each before the next.

## Pre-flight

1. **Clean working tree.** `git status --porcelain` — if there are uncommitted changes, STOP and ask the user to commit or stash first. Never review on top of dirty state.
2. **Detect the base branch** — do not assume `main`. In order: an explicit base the user gave; the PR's base from `gh pr view <n> --json baseRefName`; the repo default (`git symbolic-ref refs/remotes/origin/HEAD`); else fall back to the first of `main`, `master`, `develop`, `staging` that exists.
3. **Update the base.** `git fetch origin --prune` then bring the base up to date.

## Discovery (only if the branch wasn't specified)

- Local branches: `git branch --list`.
- Open PRs: `gh pr list --state open --json number,title,headRefName,author,isDraft` (if `gh` is unavailable, fall back to `git branch -r`).
- **Collapse the queue by ancestry before presenting it** (below).
- Present the **independent** heads — each with what it subsumes — and ask which one to review.

### Collapse the queue by ancestry

An agent queue is a **graph, not a list**: agents branch from each other's work, so one head
routinely contains several other open PRs outright. Presenting every PR as an equal candidate is
what makes a queue unreviewable — the human counts N decisions where there are far fewer, and a
flat list gives no entry point, so none gets reviewed. Reduce it first, with two facts from the
commit graph:

```bash
git fetch origin --prune
git rev-parse origin/<head>                                  # identical SHA ⇒ one branch, two PRs
git merge-base --is-ancestor origin/<a> origin/<b>            # exit 0 ⇒ #a is contained in #b
```

- A PR whose head is an **ancestor** of another open PR's head is **contained**: merging the
  descendant lands it unchanged. It is not a decision of its own.
- Two PRs whose heads are the **same commit** are one branch reviewed twice.
- The **independent heads** — contained in nothing else open — are the actual decision set.

Report both numbers (`41 open PRs · 8 independent heads`) and, under each independent head, the
PRs it subsumes. Then review the independent heads one at a time; the contained ones are settled
by whichever descendant the human merges, and need no diff review (see Step E).

Ancestry is a property of the commit graph, not a claim anyone made, so it is the one piece of
supersede evidence that cannot be wrong. It is also **directional**: it says the descendant
contains this work, never that the work is unwanted. A head contained in a PR the human closes is
back to being an independent decision — recheck after any close.

## Review workflow

### Step A — Check out the branch locally, then bring it up to date with base
**You MUST actually check out the PR branch into the working tree.** Do not review by diffing remote refs (`git diff origin/<base>...origin/<branch>`) — the human reads the diff in their editor, which requires the files to be checked out locally on the branch. Enter the branch first, every time:
```bash
git checkout <branch>          # MANDATORY — be on the branch locally
git merge <base> --no-edit
```
Confirm you are on the branch (`git branch --show-current`) before assessing. If conflicts arise, resolve them (the **base wins** on conflicts — the branch adapts to the base, not the reverse), then commit the resolution. If conflicts are non-trivial, surface them to the user rather than guessing.

### Step B — Identify the PR
`gh pr view <branch> --json number,state,author,url,isDraft,title` (fallback: skip if no `gh`). Show PR number, author, state, URL up front — context before verdict.

### Step C — Show only the branch's own changes
Diff against the **merge base**, so base changes don't pollute the review:
```bash
git log <base>..HEAD --oneline --no-merges
git diff $(git merge-base <base> HEAD)...HEAD --stat
```
Read the actual diff, but **present it as a digestible summary, not a raw dump**:

| File | Change |
|------|--------|
| `path/to/file` | one-line description of what changed and why |

### Step D — Assess (this is the value you add)
Go beyond "it compiles." Check, and report concisely:
- **What it does** — 1-2 sentences.
- **Correctness & scope** — does the diff actually do what the PR claims? Anything out of scope / unrelated?
- **Tests** — is the new behavior tested? Run the relevant tests if quick; report results honestly.
- **Conventions & safety** — matches the codebase's patterns? Any security/data-integrity/migration concern?
- **Blind spots** — for a large or sensitive change, dispatch the `anantys.code-auditor` agent (fresh context) to surface what the agent *omitted* (implicit contracts, edge cases), and fold its findings in.

### Step E — Recommend, then STOP
Give one clear recommendation with a one-line rationale:
- **Merge** — solid; merge into base, close PR, delete branch.
- **Close** — superseded/obsolete; close PR, delete branch.
- **Skip** — keep the branch for now, decide later.
- **Audit** — needs deeper review/testing before deciding.

A **contained** PR (Discovery) skips Steps A–D entirely: its verdict follows the descendant that
contains it, so there is no diff to read and no independent judgement to make. Recommend **Close
— contained in #N**, citing the `--is-ancestor` check, *after* #N is merged; before that it is
**Skip**, because closing it while #N is still open discards the work. Never reach a Close verdict
for a contained PR by reviewing its diff — that re-decides, one PR at a time, what the human
already decided once.

Then **wait for the user's decision.** Do not act on Merge/Close until they confirm.

## Acting on the decision (only after explicit confirmation)

- **Merge:** `git checkout <base> && git merge <branch> --no-edit`, then `gh pr close <n> --comment "Merged into <base>." --delete-branch` and `git branch -D <branch>`. Remind the user to `git push origin <base>` — **you do not push**.
- **Close:** `gh pr close <n> --comment "<reason>" --delete-branch` and `git branch -D <branch>`.
- **Skip:** return to base, leave the branch untouched.

## Rules

- **Check out the branch locally** — always `git checkout <branch>` into the working tree; never review off remote-ref diffs. The human reads the diff in their editor.
- **One branch at a time** — never batch diffs or decisions. "One at a time" applies to the
  **independent** heads; a queue presented without collapsing it first charges the human a review
  per PR for a decision set that is smaller, often far smaller.
- **Summarize the diff** — a readable table + assessment beats a wall of raw diff.
- **Base wins on conflicts** — the branch adapts to the base.
- **Show PR info before the verdict** — context first.
- **Wait for the user** before merging or closing. The recommendation is yours; the decision is theirs.
- **Never push** — stop at the local merge and hand the push command to the user.
- Report what you actually verified (tests run, audit done), not what you assume.
