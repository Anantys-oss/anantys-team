# Feature brief — the `--brief` / `--from linear:` / `--from pr:` source for `/anantys.qa plan`

The universal, non-spec-kit input to `plan`. It plays the two roles a spec-kit dir plays —
**requirements** (what each assertion cites) and **what shipped** (what was actually built) — in
one file. Write it by hand for a feature built any way (a bot-loop epic, a hotfix, a design doc),
or let `--from linear:SKU-…` / `--from pr:<url>` assemble one for you to confirm.

> Same discipline as spec-kit: assertions cite **requirement ids**, never the diff. Give every
> requirement a stable id here; `plan` will assign `R1`, `R2`, … to any that lack one and write
> them back, and runs / notes / reports reference those ids for the life of the feature.

> **After the first `plan`, the copy at `.anantys/qa/<slug>/brief.md` owns the ids** — this file
> stays yours to edit, and a later `plan` merges your changes into that copy instead of replacing
> it, so an id never moves to another requirement. Edit a requirement's wording freely; if you
> renumber or re-letter ids here, the run history still points at the old ones.

---

```markdown
# <Feature> — QA feature brief

_Source: <hand-written | linear:SKU-… | pr:owner/repo#42>. Assembled <YYYY-MM-DD>._

_Under test: <the branch and head commit the campaign must run against, and the environment serving it>._
A brief assembled from an unmerged PR is worthless if the stack is serving `main` — state the
precondition here so a run stops instead of QA-ing the wrong code.

## Requirements

What the feature must do, from the user's side — one line per checkable requirement, each with a
stable id. These are what assertions cite (the `FR-030` / `US4` role). Write **intent, not
implementation**: "an owner can renew a pending invitation", not "POST /invitations/:id/renew".

- **R1** <a user-observable behaviour — with its money / legal / data weight if any>
- **R2** …
- **R3** …

Mark the ones that touch **money / legal / data / journey** — they become the plan's blocker list
(`qa-plan.md` §3, four classes). The fourth is the one nobody writes down: a requirement the
product can *report as done* without having done it — a success screen, a confirmation badge, a
"saved" toast. Name it here, or the plan's `Journey` row ships empty.

## What shipped

What was actually built, so the campaign tests the real surface rather than the wish. One line per
PR / change, enough to know which requirement it serves and where in the UI it lives.

- <repo#PR — one line: what it added, which requirement(s) it serves>
- …

## Not shipped / known gaps

Anything a requirement implies that is NOT in yet — a backend endpoint a UI calls, a deferred
follow-up. These are `BLOCKED`-by-construction cases, **not FAILs**: say so here so a run does not
file the missing half as a defect.

**Lead each gap with the requirement id it blocks.** `plan` must mark *the assertions it covers*
`BLOCKED`; with no id it cannot tell which ones, and a gap pinned to the wrong assertion FAILs the
very case this section exists to excuse.

- **R2** <e.g. the cost-tasks endpoint is not deployed → its tab renders an empty state, which is EXPECTED>
```
