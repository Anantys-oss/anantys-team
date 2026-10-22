# The invocation is part of the contract

Every role in this plugin writes its *input* contract in prose and its *tool* contract in
frontmatter. Until this change, none of them declared its **invocation** contract — who is
allowed to start the role, and what the arguments look like. Both are loader-readable fields.
Neither was set on any of the five skills.

## What the loader reads

From the skill frontmatter schema in the `claude` 2.1.278 binary:

| field | the loader's own description |
|---|---|
| `argument-hint` | "Placeholder text shown after the slash command name." |
| `disable-model-invocation` | "If true, the model cannot invoke this via the `Skill` tool; only users can type the slash command." |
| `user-invocable` | "If false, hides the slash command from users; only the model can invoke it via the `Skill` tool." |

And the skill-authoring guidance the same binary ships:

> Both the user (`/<skill-name>`) and Claude can invoke skills by default. For workflows with
> side effects (e.g., `/deploy`, `/fix-issue 123`), add `disable-model-invocation: true` so only
> the user can trigger it, and use `$ARGUMENTS` to accept input.

## Why the default is wrong for two of the five roles

Default is model-invocable. Two roles cannot survive that default, because their prose is
written for a human who typed the command:

- **`anantys.review`** — Step A is unconditional and mandatory: `git checkout <branch>` then
  `git merge <base> --no-edit`. A model-invoked review therefore moves the operator's working
  tree onto another branch and writes a merge commit *before* Step E asks anyone anything.
  Acting on **Merge**/**Close** then runs `gh pr close --delete-branch` and `git branch -D`.
- **`anantys.ops`** — it drives a real browser through the operator's **logged-in** Search
  Console and Analytics sessions, and its Pre-flight says "Wait for user approval before
  proceeding." There is no user turn to approve a plan nobody asked for.

The loader's refusal path routes correctly and closes the obvious loophole:

> `<name>` cannot be used with `Skill` tool due to disable-model-invocation. … Ask the user to
> run `/<name>` themselves. … **Do not replicate this skill's workflow by other means** — it is
> reserved for explicit user invocation.

`anantys.qa`, `anantys.debug` and `anantys.design` keep model invocation: their effects land in
the project workspace, are visible to `git status`, and their hard preconditions make them stop
rather than guess.

## Why `argument-hint` on all five

Each role's prose defines a grammar the `/`-menu never showed. `anantys.qa` is the extreme case
— line 19 says "Invoked as `/anantys.qa <action> [args]`" and the body then defines seven
actions and five flags (`--brief`, `--from linear:`, `--from pr:`, `--env`, `--mode`). None of
that was reachable without opening a 513-line file. The README's own claim is that "Skills are
invoked directly (`/anantys.design …`) — type `/anantys` to see the whole team"; the hint is
what makes that sentence true.

## Why `$ARGUMENTS` where the grammar is, not at the end

`anantys.design` and `anantys.ops` already carried the placeholder. `qa`, `review` and `debug`
did not — and their arguments were **not** dropped. The loader's substitution function appends
them instead:

```js
e = e.replaceAll("$ARGUMENTS", () => (O = !0, h(n)));
if (!O && r && n) e = e + `\n\nARGUMENTS: ${h(n)}`;
```

So `/anantys.qa run --env staging` reached the model as a line appended *after* all 513 lines of
`anantys.qa` — 476 lines below the sentence that defines what an action is. The placeholder now
sits next to the grammar that reads it. This is a placement fix, not a dropped-input fix.

## One trap worth recording

`argument-hint` is typed as a string, and a plain YAML scalar **cannot begin with `[`**. Against
a strict YAML 1.2 parser:

| written | parses as |
|---|---|
| `argument-hint: [branch \| PR number]` | the **list** `['branch \| PR number']` — not a string |
| `argument-hint: [init\|plan\|run] [--env <name>] [args]` | **parse error** on the whole frontmatter block |
| `argument-hint: "[init\|plan\|run] [--env <name>] [args]"` | the intended string |

Nothing in the toolchain reports either failure. With the unquoted `qa` hint the plugin still
installs, `claude plugin details` still reports five skills at unchanged token cost, and
`claude plugin validate --strict` still emits only the pre-existing `author` warning — it reads
`plugin.json`, never a SKILL.md. The loader's own parser is more permissive than the strict one,
so *how* a bad hint fails is parser-dependent; that is the argument for quoting, not for relying
on either. The binary's frontmatter serializer quotes on exactly this character class —
``/[{}[\]*&#!|>%@`]|: /`` — which is where the rule came from. Every hint here is quoted.

## Measurement

| | |
|---|---|
| open remote heads swept | 128 |
| heads setting `argument-hint` | **0** |
| heads setting `disable-model-invocation` | **0** |
| heads setting `user-invocable` | **0** |
| heads with any of the three in *prose* | 0 |
| skills whose prose defines an argument grammar | 5 of 5 |
| skills carrying `$ARGUMENTS` before this change | 2 of 5 (`design`, `ops`) |

The queue is not blind to these fields: `scripts/check_platform.py` (on 20 heads) lists all three
in `SKILL_KEYS`. It asks "does the loader read this key?" — a permissive vocabulary check. It
never asks whether a role with irreversible side effects *declares* one. That is the gap this
change fills, and the clause belongs in that gate; it is proposed on the gate chain's live
descendant rather than shipped as a 129th branch.

## Verification

Sealed install (`CLAUDE_CONFIG_DIR` in a throwaway dir, marketplace added from an archive of this
tree, plugin installed from it):

- `claude plugin details anantys-team-agents@anantys-oss` → 5 skills, 2 agents, unchanged
  per-component token costs.
- `claude plugin validate plugins/anantys-team-agents --strict` → one warning, `author`, which is
  pre-existing on `main` and owned elsewhere in the queue. Byte-identical to the same command on
  `main`; "exit 0" was never available here.
- A third sealed tree with the `qa` hint deliberately unquoted → same inventory, same costs, same
  single warning. That is the measurement behind "nothing in the toolchain reports it".

## Landing cost

`merge-tree` against all 127 open heads, `main` vs this tree:

| tree | conflicting heads |
|---|---|
| `origin/main` (each head alone) | 0 |
| first draft of this change | 34 |
| as shipped | **17** |

The 17 marginal edges are not inherited — `main` conflicts with nothing. Half the first draft's
cost was pure placement. The new frontmatter keys sat after `allowed-tools:`, the one line
tool-grant work edits, which cost 18 edges on `anantys.design` and 12 on `anantys.debug` for a
single added line; moving them above `description:` (YAML is unordered) dropped those to 3 and 3.
Moving the two Rules lines to the end of their lists instead of beside the first bullet took
`anantys.ops` from 13 to 3. What is left is the irreducible part: 11 on `anantys.qa`'s Actions
section, 7 on `anantys.review`'s Rules, and 15 on the two manifests for the version field. Those
are the lines the change is actually about.
