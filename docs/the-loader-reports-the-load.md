# The loader reports the load, and the manifest is the chokepoint

Two sweeps over every ref this repo has — `main` plus 68 branch heads — using only
the loader, no credential. `apiKeySource` on the session's own `init` event reads
`none` with `ANTHROPIC_*` unset, which is why both commands below belong in CI.

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

- **69 of 69 refs pass `claude plugin validate --strict`** on the marketplace
  manifest, every local `source:`'s plugin manifest, and every component directory —
  modulo the two warnings `main` already carries (`author`, fixed here; marketplace
  `description`, fixed on `koan/the-loader-names-what-it-exposes`).
- **All 69 expose the identical set of names**: 5 skills, 2 agents, no role in any
  tree that loads as nothing.
- **Not one of the 68 branches adds a role.** The whole queue is prose refinement of
  the same seven.
