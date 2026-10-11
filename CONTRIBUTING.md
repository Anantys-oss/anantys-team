# Contributing

Four conventions. Each one is here because the open queue measurably broke it.

## 1. The version lives in `plugin.json`, and nowhere else

`.claude-plugin/marketplace.json` must not carry a `version` field. The Claude Code CLI
reads the version from the plugin's own `plugin.json` for every operation that needs it —
verified against `plugin validate`, `plugin install`, `plugin details` and `plugin update`
(a bump applied only to `plugin.json` is detected and applied as `0.6.0 -> 0.7.0`).

With the field removed, `plugin install` still caches the plugin under `0.6.0` — the key
comes from `plugin.json` alone.

The converse holds too, and it is the reason the field has to go: a bump applied only to
`marketplace.json` is **not** detected. `plugin update` answers `already at the latest
version` and the user keeps the old tree. So the second copy cannot ship anything — it can
only advertise a version nobody receives.

A second copy is not a safety net, it is a desync waiting to happen — and it made
`marketplace.json` the repository's most-churned file.

## 2. Bump the version at release, not in the change

The `plugin.json` version is not a label on the release. It is the **delivery gate**: the
CLI caches an installed plugin under `plugins/cache/<marketplace>/<plugin>/<version>/`, so
the version string *is* the cache directory name. Merge content without bumping it and
`plugin update` reports `already at the latest version` — the change is on `main` and on
GitHub, and no installed user will ever see it.

`main` is at `0.6.0` and carries no tags. Every change merged into it at `0.6.0` is
invisible to anyone who has already installed. Cutting a release is therefore not
bookkeeping; it is the only act that ships.

A pull request that changes a role's prose does not know what it will ship as. It only
knows what the version was when it branched.

Of 38 open pull requests, 27 bump the version — all 27 to the identical `0.6.1`, against
a `main` at `0.6.0`. Git does not flag this, because the lines are the same: merge three
of those branches and the tree still says `0.6.1` for three changes. The bump carries no
information and silently stops being true after the first merge.

Bump once, on `main`, when cutting a release, and tag it. The repository currently has no
tags, which is why there is no floor to compare a branch's version against.

Both claims above are reproducible against a throwaway config dir, with no account:

```bash
export CLAUDE_CONFIG_DIR=$(mktemp -d)
claude plugin marketplace add ./                    # a local path works; bare `.` is rejected
claude plugin install anantys-team-agents@anantys-oss
# edit a SKILL.md, commit, leave the version alone:
claude plugin marketplace update anantys-oss && claude plugin update anantys-team-agents@anantys-oss
#   -> "already at the latest version (0.6.0)"; the cached tree still holds the old text
# now bump plugin.json only, and repeat:
#   -> "updated from 0.6.0 to 0.6.1"; a new cache dir appears, carrying the edit
```

This conflicts, deliberately, with the open `check_version_bump.py` gate, which demands a
bump on every content pull request. The gate's premise is sound — nothing ships unbumped —
but it enforces it at the wrong commit. Gate the release, not the change.

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
