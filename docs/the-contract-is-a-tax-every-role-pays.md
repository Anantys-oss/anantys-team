# The contract is a tax every role pays

`TEAM-CONTRACT.md` (#27) is 99 lines, loaded in full before every action of every role.
`check_plugins.py`'s load ceiling (#20, #50) counts it into each role's load, because it is
loaded. Neither branch is wrong on its own. Together, six of seven roles go over 200 lines —
and the ceiling calls a *crossing* an error, not a warning, because the remedy is inside the
crossing branch's own diff.

Measured on the assembled queue (`koan/the-whole-queue-lands`, 25 of 26 remaining heads folded):

| role | load at `main` | load folded | over by |
|---|---|---|---|
| `anantys.ops` | 131 | **490** | +290 |
| `anantys.design` | 115 | **374** | +174 |
| `anantys.review` | 84 | **327** | +127 |
| `anantys.debug` | 66 | **273** | +73 |
| `anantys.spec-tester` | 53 | **250** | +50 |
| `anantys.code-auditor` | 61 | **206** | +6 |
| `anantys.qa` | 648 | 922 | already over at the base — **warning** |

`anantys.qa` is the one role that escapes the error, and only because #5 already split it:
its 274-line growth lands on a file the base had already pushed over, so the gate reads it as
inherited debt. The split is what turns an error into a warning — which is the convention
working exactly as #5 wrote it.

## Why no branch could see this

The 99 lines exist only in the union. #27 measures its own roles against a `main` with no
contract; #20 and #50 measure a tree with no `TEAM-CONTRACT.md` to count. Each gate run on
its own author's branch exits 0. The error is a property of the assembled tree.

## What the gate itself rules out

The message is explicit about two non-remedies:

- **Do not shrink the contract.** `check_contract_clauses` holds its clause labels *and* their
  bodies in place; gutting it is the failure that check was written to catch.
- **Do not relocate the prose into a `reference/` or `templates/` file the role names.** The
  largest of each is counted too, so moving lines there moves the load without lowering it.

## The remedy, and whose call it is

Split the six roles the way #5 split `anantys.qa`: per-action detail into `reference/` topic
files the actions table links to, so no single action loads what it does not need. That is six
role files' worth of restructuring and a product decision about what each action needs — not a
merge resolution. It is recorded here rather than guessed at.

Until it lands, `check_plugins.py` is the one red gate on the folded tree:
**6 errors, 2 warnings, exit 1.** The other six gates and all 399 tests pass.
