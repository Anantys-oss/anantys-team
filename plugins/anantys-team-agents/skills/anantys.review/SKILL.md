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
3. **Update the base — to the base this branch will *land in*.** `git fetch origin --prune`, then fast-forward the base to `origin/<base>`. If the local base is *ahead* of `origin/<base>`, that is a merge from an earlier review in this same sitting: it is unpushed, so it exists nowhere else. Keep it, say so, and review against it. Never `reset --hard origin/<base>` to "start clean" — that silently discards a landing the user already approved, and re-computes your verdict against a tree that no longer describes where the branch is going.
4. **Record the branch you started on, and say where you will leave it.** Step A's checkout is
   mandatory, so this skill *always* moves the working tree — and the working tree is shared. The
   next session in this repo (a debug loop, a design pass, a test run) inherits whatever branch you
   leave behind, and none of them asks which one it is; a fix verified on a stale review branch is
   not a delivered fix. Note `git branch --show-current` before you touch anything, and end every
   verdict — Merge, Close, Skip, **and Audit** — back on `<base>` unless the user says otherwise.
   State it in the report: *"tree left on `<base>`, at `<sha>`."* You entered someone else's
   checkout; hand it back somewhere predictable.

## Discovery (only if the branch wasn't specified)

- Local branches: `git branch --list`.
- Open PRs: `gh pr list --state open --json number,title,headRefName,author,isDraft` (if `gh` is unavailable, fall back to `git branch -r`).
- Present the candidates and ask which one to review.

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

### Step C2 — Locate the branch in the queue
A **Merge** verdict is a claim about the tree the branch will *land in*, not the tree it was branched from. With one open PR those are the same tree. With N they are not — and that gap is where a branch-at-a-time review goes wrong: N branches each green against the base can still be red in whatever order you land them.

List the siblings and test this branch against each. Read-only — no checkout, no index, no working tree touched:
```bash
gh pr list --state open --json number,headRefName --jq '.[].headRefName'
git merge-tree --write-tree HEAD origin/<sibling> >/dev/null || echo "conflicts: <sibling>"
```
(`--write-tree` needs git ≥ 2.38. Older git's `merge-tree` is a different command that prints a diff and **exits 0 on conflict** — check `git --version` first, or you will report "no conflicts" for every sibling.)

Report two things, briefly:

- **Textual edges** — which siblings this branch conflicts with, and in which file. That is not a defect in either branch; it is the *cost of landing in this order*, and the user is the one who chooses to pay it or reorder.
- **Semantic edges** — a sibling that adds a rule, check, or convention this branch's content is subject to, or that this branch's content would newly violate (and the reverse). `merge-tree` is blind to these: both branches are green alone, the assembled tree is red. You find them by reading the siblings' titles and one-line intents — not their diffs, which is the wall of diff this skill exists to avoid.

If either kind of edge exists, the Merge recommendation is **conditional on order**: say which order is safe, or say plainly that you could not tell. An unqualified Merge is a claim that you looked and found the branch independent.

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

Then **wait for the user's decision.** Do not act on Merge/Close until they confirm.

## Acting on the decision (only after explicit confirmation)

- **Merge:** `git checkout <base> && git merge <branch> --no-edit`, then `gh pr close <n> --comment "Merged into <base>." --delete-branch` and `git branch -D <branch>`. Remind the user to `git push origin <base>` — **you do not push**.
- **Close:** `gh pr close <n> --comment "<reason>" --delete-branch` and `git branch -D <branch>`.
- **Skip:** return to base, leave the branch untouched.

## Rules

- **Check out the branch locally** — always `git checkout <branch>` into the working tree; never review off remote-ref diffs. The human reads the diff in their editor.
- **One branch at a time** — never batch diffs or decisions. That bounds what you *read*, not what you *account for*: the verdict still has to name the queue the branch lands into (Step C2).
- **A Merge verdict names the base it was computed against** — report `git rev-parse <base>` with it. If the base moved after you said it, the verdict expired; re-run Step C2 before anyone acts on it.
- **Summarize the diff** — a readable table + assessment beats a wall of raw diff.
- **Base wins on conflicts** — the branch adapts to the base.
- **Show PR info before the verdict** — context first.
- **Wait for the user** before merging or closing. The recommendation is yours; the decision is theirs.
- **Never push** — stop at the local merge and hand the push command to the user.
- Report what you actually verified (tests run, audit done), not what you assume.
