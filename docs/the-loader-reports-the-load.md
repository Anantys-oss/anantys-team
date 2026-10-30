# The loader reports the load, and the manifest is the chokepoint

Two sweeps over every ref this repo has — `main` plus 68 branch heads — using only
the loader, no credential. `apiKeySource` on the session's own `init` event reads
`none` with `ANTHROPIC_*` unset, which is why both commands below belong in CI — the
first one unflagged, for the reason in §4.

```bash
claude plugin validate <manifest-or-component-dir> --strict
claude --plugin-dir <plugin> plugin details <plugin-name>   # projected token cost
```

## 1. Where a field sits in `plugin.json` is worth 38 hand resolutions

`claude plugin validate --strict` reports one finding on `main` that no branch in
the queue fixes: the plugin declares no `author`. The marketplace warning
(`plugins[0] plugin.json → author`) names the plugin manifest, not the marketplace
entry, so **one field in one file clears both**. The fix is a single line.

That line costs between nothing and almost the whole queue, depending only on where
it goes:

| `author` placed | heads conflicting with the change, of 68 |
|---|---|
| first key | **0** |
| after `name` | 38 |
| last key | 38 |

`main` itself conflicts with **0 of 68**. `plugin.json` holds four keys; 38 heads
rewrite its `version` or `description`. Any insertion that lands inside or beside
those two lines collides with every one of them. Above `name`, it does not.

So: in this repo's two manifests, a new key goes at the top. Not taste — 38 hand
resolutions, measured with `git merge-tree --write-tree` against each head before
and after.

This change carries no version bump. The gate's definition of content is "a path
under `plugins/`", which this is; the reason to skip it anyway is that the bump
lives in `plugin.json` *and* `marketplace.json`, and writing it is the 38-conflict
hunk above — charged twice, to add an attribution field that changes nothing a
user's installed copy does.

## 2. The loader projects tokens; the ceiling counts lines

`claude plugin details` reports per-component always-on and on-invoke cost. The
load ceiling the queue argues about is 200 *lines*. The two do not rank the same
tree, and only one of them is the loader's own number.

Per-component on-invoke cost, `main` against the assembled queue
(`koan/the-product-without-the-scaffolding`, the fold that claims to carry it):

| role | `main` | folded |
|---|---|---|
| `anantys.qa` | 8.6k | **3.8k** |
| `anantys.ops` | 2.1k | 7.2k |
| `anantys.review` | 1.3k | 5.1k |
| `anantys.design` | 1.9k | 5.2k |
| `anantys.debug` | 950 | 3.6k |
| `anantys.spec-tester` | 820 | 2.7k |
| `anantys.code-auditor` | 930 | 2.7k |
| **total** | **16.6k** | **30.3k** |

Always-on goes 716 → 760 tok. On-invoke rises 83%, and `anantys.qa` — the one role
a line count would flag, at 513 lines and 52% of `main`'s whole on-invoke budget —
is the only role the queue makes *cheaper*. A line-based gate reports the fold as a
qa regression. The loader reports the opposite.

Across the 68 heads individually: Δalways-on ranges −61 to +44 (median 0), Δon-invoke
−6.7k to +13.7k (median 0). The median branch is free; the cost is concentrated in
the few that assemble others.

## 3. What the sweep did not find

Worth recording because it removes a class of merge risk:

- **All 69 expose the identical set of names**: 5 skills, 2 agents, no role in any
  tree that loads as nothing.
- **Not one of the 68 branches adds a role.** The whole queue is prose refinement of
  the same seven.

## 4. `--strict` has no "modulo" — it is the flag that makes a warning fatal

An earlier draft of §3 reported "69 of 69 refs pass `claude plugin validate --strict`
… modulo the two warnings `main` already carries". There is no modulo to take. The
flag's whole effect is to promote those warnings, and the loader says so in the line
it exits on — `claude plugin validate . --strict` on `main`, message tails elided:

```
⚠ Found 2 warnings:
  ❯ description: No marketplace description provided. …
  ❯ plugins[0] plugin.json → author: No author information provided. …
✘ Validation failed (--strict treats warnings as errors)
```

`claude plugin validate .` exits **0** on `main`. The same command with `--strict`
exits **1**. Measured over every ref on `origin` — `main` plus 184 branch heads,
against 2.1.278, both the marketplace manifest and the plugin directory:

| `--strict` result | refs |
|---|---|
| green on both manifests | **2** |
| green on the plugin dir, red on the marketplace | 1 |
| red on both | 182 |

The two green refs are `koan/the-field-no-gate-dared-demand` (depth 109, PR #126)
and `koan/the-widest-grant-reads-as-the-narrowest` (depth 110, **no pull request**) —
the only trees in the queue that set `author` in `plugin.json` *and* `description` in
the marketplace. Setting either alone is not enough, and 174 refs set neither.
`main` is red. So is the branch this document is on: it adds `author`, which clears
the plugin directory, and leaves the marketplace missing its `description`.

So the header's "both commands below belong in CI" holds only for the unflagged form.
`.github/workflows/platform.yml` already made that call, and its reason is recorded
there: *"Not --strict: the marketplace has carried a missing-author warning since
before this gate existed, and reddening every PR over it would teach people to ignore
the gate."* That reason expires the moment either green ref lands — at which point the
flag becomes an enforceable ratchet instead of a permanent red, and the gate's comment
is the place to say so.

The general shape, since this repo keeps rediscovering it: a sentence that subtracts a
tool's findings from the tool's own verdict is not a measurement, it is a wish. Read the
exit code.
