# The description is the router, the body is the manual

Measured on Claude Code **2.1.278**, `claude plugin details anantys-team-agents`, throwaway
`CLAUDE_CONFIG_DIR`, no account needed.

A component is charged on two separate axes:

| axis | what is charged | when |
|---|---|---|
| **always-on** | the frontmatter `description`, and nothing else | every session, whether or not the role fires |
| **on-invoke** | the `SKILL.md` body | each time the role fires |

The two numbers are independent. `anantys.qa`'s body is ~8.6k on-invoke and contributes
**zero** always-on; its 709-character description contributed ~190.

## The rule

A `description` is read by the router that decides *which* role to load. The router never
reads a flag, a file path, or an internal invariant — it matches intent. So anything in a
description that cannot change a routing decision is paid by 100% of sessions and used by
none of them.

Keep in a description:

- what the role does, and the nouns a user would say when they want it
- the sources it accepts (a spec-kit `tasks.md`, a brief, tracker issues, a PR)
- a `Use to …` / `Use when …` clause

Move to the body:

- flag and argument syntax (`--brief`, `--from pr:<url>`, `--env <name>`)
- invariants about where files live
- anything a reader needs only *after* the role has already been chosen

## What this cost here

`anantys.qa` carried its whole flag table and the `.anantys/qa.md` invariant in its
description. Both are already stated in the body — the invariant verbatim, at the bottom of
the file. Rewriting the description as a router, losing no trigger noun:

| | before | after |
|---|---|---|
| `anantys.qa` description | 709 chars | 480 chars |
| `anantys.qa` always-on | ~190 tok | ~130 tok |
| plugin always-on | **~716 tok** | **~659 tok** |

Small in absolute terms. It is also the only axis every session pays.

A ceiling on `SKILL.md` line count does not constrain this axis — body length and always-on
cost are unrelated. A ceiling that means to protect every session has to be a ceiling on
`description`.

## Two hypotheses this work falsified

Recorded so they are not re-derived.

**1. The slash name is *not* broken by the plugin namespace.** A plugin skill's canonical
name is `<plugin>:<skill>` — here `anantys-team-agents:anantys.qa`, which is what the Skill
tool's listing shows the model. `README.md` tells users to type `/anantys.qa`, and that
works: the loader registers an *unqualified alias* for any frontmatter `name` that contains
no colon, and the completion matcher additionally tries the substring after the last colon.
Both are in 2.1.278. The dot in `anantys.qa` is not a colon, so the alias exists. No fix
needed — and typing `/anantys` does list the team, because the plugin name also starts with
`anantys`.

**2. Always-on cost is not spread across the roles.** The plugin's ~716 always-on tokens are
exactly the sum of the seven descriptions, and six of the seven are 246–404 characters. There
is no general bloat to trim; there was one outlier.

## Not installed, not charged

`claude plugin install` copies only `plugins/anantys-team-agents/` — the install root is
`agents/`, `skills/`, `.claude-plugin/`. Repo-root `README.md` and this `docs/` directory are
never delivered, so they cost a user nothing. Notes like this one belong here, not in a role.
