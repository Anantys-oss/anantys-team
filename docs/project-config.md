# Project configuration — `.anantys/<skill>.md`

A skill knows *how* to do its job. It must know nothing about *this* project. Everything
project-specific lives in `.anantys/<skill>.md` at the repo root, written once and read on
every run. `anantys.qa` established this — `.anantys/qa.md`, an `init` action, a template.

Today it is the only role that has it. The others ask the operator for the same facts every
run: `ops` for the site domain, the hub paths, the Search Console and Analytics URLs and the
target queries; `design` for the dev URL; `debug` for how to exercise the app. Those are
properties of the project, not of the run, and re-asking them has a cost the attended case
hides — **a dispatched role has nobody to ask.** The question is simply the last thing it
emits, and a recurring audit scheduled unattended halts on input it could have read.

## What may persist, and what may not

The test is **what the fact is a property of**:

| property of | example | persists |
|---|---|---|
| the project | site domain, hub paths, dashboard URL, dev URL, test-run command | yes |
| the run | this audit's traffic goal, the scope the operator approved today, the bug being chased | no |

The second row is the one that matters, because it looks like configuration and is not.
`ops` Pre-flight asks the operator to approve **the exact list of domains this run will
visit**. That approval is consent for one run. Written into `.anantys/ops.md` it becomes a
standing grant, renewed by nobody, and the gate that produced it never fires again. A
per-run approval may be *informed* by the file — the file may say which domains are usually
in scope — but the approval itself is asked every time.

**Never a credential.** The file names *which* property, dashboard or environment; never how
to authenticate to it. The browser is the operator's own and is already signed in. Where a
secret is genuinely needed, the file names where it lives, and the value never enters the
transcript.

## A written fact is a claim with a date

Dashboard URLs rot: a property gets renamed, a GA4 view is replaced, a dev port moves. So
every fact carries **when it was last confirmed**, and confirmation is part of using it — a
URL that 404s, or lands on the wrong property, is a fact that has expired. Re-ask it, rewrite
the line with today's date, and say in the report that it changed. Never route around a stale
fact by guessing the new one; a silently corrected dashboard URL is a metric attributed to the
wrong property.

An absent file means **not configured yet**, never *nothing to configure*. Interview, write,
then run.

## Adding it to a role

1. A `templates/<skill>-config.md` next to the skill, giving the shape.
2. A step at the top of the role: read `.anantys/<skill>.md`; do the legwork (read the repo,
   probe what is probeable); ask the operator only the remainder, in one batch; write the file.
3. Nothing in the skill that names a project. If a project string is in `SKILL.md`, it is in
   the wrong file.
