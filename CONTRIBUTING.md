# Contributing

Four conventions. Each one is here because the open queue measurably broke it.

## 1. The version lives in `plugin.json`, and nowhere else

`.claude-plugin/marketplace.json` must not carry a `version` field. The Claude Code CLI
reads the version from the plugin's own `plugin.json` for every operation that needs it —
verified against `plugin validate`, `plugin install`, `plugin details` and `plugin update`
(a bump applied only to `plugin.json` is detected and applied as `0.6.0 -> 0.7.0`).

A second copy is not a safety net, it is a desync waiting to happen — and it made
`marketplace.json` the repository's most-churned file.

## 2. Bump the version at release, not in the change

A pull request that changes a role's prose does not know what it will ship as. It only
knows what the version was when it branched.

Of 38 open pull requests, 27 bump the version — all 27 to the identical `0.6.1`, against
a `main` at `0.6.0`. Git does not flag this, because the lines are the same: merge three
of those branches and the tree still says `0.6.1` for three changes. The bump carries no
information and silently stops being true after the first merge.

Bump once, on `main`, when cutting a release, and tag it. The repository currently has no
tags, which is why there is no floor to compare a branch's version against.

## 3. A pull request is product or tooling, not both

**Product** is `plugins/`, `.claude-plugin/` and `README.md` — what a user installs.
**Tooling** is `scripts/`, `evals/`, `.github/` and `docs/` — how we check the product.

Across the open queue, 30,997 of 40,588 changed lines (76%) touch no product file, and
seven pull requests touch nothing but tooling. Mixing the two means a reviewer who wants
to assess a three-line prose fix is handed a gate and its test suite as well.

Split them. The product change is the one that needs the human's judgement.

## 4. One checker, one home — and one rule, one bullet

Two branches may not introduce rival authorings of the same file. The queue holds three
redundancies that only review can catch: `#26` and `#58` are byte-identical pull requests,
and `#45` and `#47` re-author the same `scripts/check_plugins.py` and
`scripts/check_tool_grants.py` that `#6` and `#11` already add.

The same applies inside a role: a new rule appends its own bullet to a named list. The
queue's one genuine product conflict is two unrelated rules claiming the same slot in
`agents/anantys.code-auditor.md` — both correct, mutually exclusive only in placement.

## Checks

Before pushing, run:

```bash
claude plugin validate .
```

Warnings about a missing marketplace `description` or plugin `author` are pre-existing.
Errors are not.
