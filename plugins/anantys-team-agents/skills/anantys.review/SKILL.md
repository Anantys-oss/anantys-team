---
name: anantys.review
when_to_use: Use when the user wants one agent-pushed PR branch reviewed and a Merge / Close / Skip / Audit recommendation before they decide. Triggers — "review this PR", "is it safe to merge", "what does this branch actually change", "triage this agent branch". Examples — "review the branch agent/123-add-export", "PR #42, worth merging?".
description: Cleanly review a single agent-pushed PR branch and help decide its fate. Brings the branch up to date with its base, shows only the branch's own changes as a digestible summary (never a wall of diff), assesses value and risk, and recommends Merge / Close / Skip / Audit — then waits for the human to decide. Use to review an autonomous-agent PR before merging.
allowed-tools: Bash, Read, Glob, Grep, Task, TaskCreate, TaskUpdate, TaskList
---

## Mission

You review **one** PR branch — typically pushed by an autonomous coding agent — and help the human decide what to do with it. Agent-pushed PRs are the new bottleneck: the code is cheap, the *review* is the scarce, fallible step. Your job is to make that review **fast, honest, and decision-ready**, never a rubber stamp and never a wall of unreadable diff.

## Inputs

The user names the branch to review (a branch name, a PR number/URL, or "the current branch"). If nothing is given, list candidate branches (see Discovery) and ask which one. Review **one branch at a time** — if the user wants several, loop this skill, finishing each before the next.

## Pre-flight

1. **Clean working tree — and sort what made it dirty.** `git status --porcelain` — if there are uncommitted changes, STOP. Never review on top of dirty state. But read the paths before offering a remedy: a pending change under `.anantys/` is another role's artifact, not review state, and *commit or stash* is the wrong pair for it. A QA or ops log is append-only, so a stash is the only copy — ask for a commit instead, on the branch the artifact describes. If the path is **untracked**, say so plainly: it follows your `git checkout` into every branch you touch and is still sitting there after the PR is closed. See [`docs/artifacts-declare-their-git-status.md`](../../../../docs/artifacts-declare-their-git-status.md).
2. **Detect the base branch** — do not assume `main`. In order: an explicit base the user gave; the PR's base from `gh pr view <n> --json baseRefName`; the repo default (`git symbolic-ref refs/remotes/origin/HEAD`); else fall back to the first of `main`, `master`, `develop`, `staging` that exists.
3. **Update the base.** `git fetch origin --prune` then bring the base up to date.

## Discovery (only if the branch wasn't specified)

- Local branches: `git branch --list`.
- Open PRs: `gh pr list --state open --limit 200 --json number,title,headRefName,author,isDraft` (if `gh` is unavailable, fall back to `git branch -r`). **`--limit` is not optional:** `gh` defaults to 30 and truncates *silently* — nothing on stderr, no marker in the JSON. An agent-pushed queue is precisely where the thirty-first branch lives.
- **If the row count equals the limit you passed, assume you were cut off** — raise it, re-run, and only then present the list. Say how many you found.
- Present the candidates and ask which one to review.

## Review workflow

### Step A — Check out the branch locally, then bring it up to date with base
**You MUST actually check out the PR branch into the working tree.** Do not review by diffing remote refs (`git diff origin/<base>...origin/<branch>`) — the human reads the diff in their editor, which requires the files to be checked out locally on the branch. Enter the branch first, every time:
```bash
git checkout <branch>          # MANDATORY — be on the branch locally
git rev-parse <branch> origin/<branch>   # not the PR head until these two match
git merge <base> --no-edit
```
**A local branch of that name is not the PR.** `git checkout` prefers an existing local ref and never consults `origin/<branch>`; pre-flight refreshed the *base*, not the branch. Agent branches are amended and force-pushed between reviews, so the ref an earlier `Skip` left behind is a tree the PR no longer has. Compare the two SHAs before assessing and classify — never `reset --hard`, which discards an unpushed landing that exists nowhere else:

- **Equal** — review it.
- **Local contains `origin/<branch>`** — an earlier review's unpushed merge. Keep it, say so, review against it.
- **Local is behind** — the agent pushed since: `git merge --ff-only origin/<branch>`.
- **Diverged** — STOP. Show both SHAs and ask which one is the subject. A verdict on the wrong tree reads exactly like a verdict on the right one.

Confirm you are on the branch (`git branch --show-current`) before assessing. If conflicts arise, resolve them (the **base wins** on conflicts — the branch adapts to the base, not the reverse), then commit the resolution. If conflicts are non-trivial, surface them to the user rather than guessing.

**This merge is local-only.** You do not push, so the branch now diverges from `origin/<branch>` and the PR on GitHub still shows the old, conflicting head. Say so explicitly and hand the user the one command that closes the gap, theirs to run:

```bash
git push origin <branch>       # only if they want the resolution on the PR
```

A conflict resolution you commit and never surface is work thrown away silently.

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
- **Merge** — solid; merge into base locally, hand the push to the user.
- **Close** — superseded/obsolete; close the PR, leave both branches standing.
- **Skip** — keep the branch for now, decide later.
- **Audit** — not decidable on what you have; name the deeper look you need, then run it (below).

Then **wait for the user's decision.** Do not act on Merge/Close until they confirm.

## Acting on the decision (only after explicit confirmation)

You run the reversible half. The user runs the irreversible half — because **you never push**, and
nothing you have done is durable until they do.

- **Merge:**
  ```bash
  git checkout <base>
  git merge <branch> --no-edit
  git merge-base --is-ancestor <branch> HEAD   # verify the commits really landed
  ```
  Then STOP and hand over:
  ```bash
  git push origin <base>     # this auto-closes the PR as *Merged*
  ```
  **Do not run `gh pr close` on a merge.** Pushing the base closes the PR as *Merged* by itself;
  closing it by hand records the work as *rejected* in the project's history, which is the opposite
  of the decision that was just made.

- **Close:** `gh pr close <n> --comment "<reason>"`. Closing is reversible; the branches are the
  only copy of the work, so leave them standing. Deleting them is a separate decision the user
  makes afterwards, never a flag bundled into the close.

- **Skip:** return to base, leave the branch untouched.

- **Audit:** stay on the branch — the audit reads the checked-out tree. Dispatch the
  `anantys.code-auditor` agent over the branch's own range (`<merge-base>...HEAD`), and run the
  tests you skipped in Step D. If Step D already dispatched the auditor, do not dispatch it again:
  the open question is whatever its findings left unresolved, so name that and answer it. Report
  what came back, then **re-recommend — Merge, Close, or Skip only.** Audit is not a verdict you
  may return twice; a second one means you are not going to resolve it here, which is a Skip.

**Never delete a branch — local or remote.** Not with `--delete-branch`, not with `git branch -D`.
On the Merge path the merge commit lives only in an unpushed local base, so deleting both copies
destroys the work outright; on the Close path the branch *is* the work. Deletion buys nothing a
later `git branch -d` can't, and it is the one step in this whole skill that cannot be undone.

## Rules

- **Check out the branch locally** — always `git checkout <branch>` into the working tree; never review off remote-ref diffs. The human reads the diff in their editor.
- **The PR head is the subject** — compare `<branch>` to `origin/<branch>` before assessing. A stale local ref produces a confident verdict on code the PR does not contain.
- **One branch at a time** — never batch diffs or decisions.
- **Bound every list you run.** Any `gh ... list` without `--limit` returns the first 30 and tells you nothing. A candidate list you can't vouch is complete is worse than no list: the human reads it as the queue.
- **Summarize the diff** — a readable table + assessment beats a wall of raw diff.
- **Base wins on conflicts** — the branch adapts to the base.
- **Show PR info before the verdict** — context first.
- **Wait for the user** before merging or closing. The recommendation is yours; the decision is theirs.
- **Never push** — stop at the local merge and hand the push command to the user.
- **Nothing irreversible before it is durable.** You don't push, so every merge and conflict
  resolution you make exists in exactly one place: this working tree. Never destroy the other copy
  — no branch deletion, no `gh pr close` on a merge — while that is true.
- Report what you actually verified (tests run, audit done), not what you assume.
