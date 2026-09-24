# Feature brief — the `--brief` / `--from linear:` / `--from pr:` source for `/anantys.qa testplan`

The universal, non-spec-kit input to `testplan`. It plays the two roles a spec-kit dir plays —
**requirements** (what each assertion cites) and **what shipped** (what was actually built) — in
one file. Write it by hand for a feature built any way (a bot-loop epic, a hotfix, a design doc),
or let `--from linear:SKU-…` / `--from pr:<url>` assemble one for you to confirm.

> Same discipline as spec-kit: assertions cite **requirement ids**, never the diff. Give every
> requirement a stable id here; `testplan` will assign `R1`, `R2`, … to any that lack one and write
> them back, and runs / notes / reports reference those ids for the life of the feature.

---

```markdown
# <Feature> — QA feature brief

_Source: <hand-written | linear:SKU-… | pr:owner/repo#42>. Assembled <YYYY-MM-DD>._

_Under test: <the branch/commit the campaign must run against, and the environment serving it>._
A brief assembled from an unmerged PR is worthless if the stack is serving `main` — state the
precondition here so a run stops instead of QA-ing the wrong code.

## Requirements

What the feature must do, from the user's side — one line per checkable requirement, each with a
stable id. These are what assertions cite (the `FR-030` / `US4` role). Write **intent, not
implementation**: "an owner can renew a pending invitation", not "POST /invitations/:id/renew".

- **R1** <a user-observable behaviour — with its money / legal / data weight if any>
- **R2** …
- **R3** …

Mark the ones that touch **money / legal / data** — they become the blocker list.

## What shipped

What was actually built, so the campaign tests the real surface rather than the wish. One line per
PR / change, enough to know which requirement it serves and where in the UI it lives.

- <repo#PR — one line: what it added, which requirement(s) it serves>
- …

## Not shipped / known gaps

Anything a requirement implies that is NOT in yet — a backend endpoint a UI calls, a deferred
follow-up. These are `BLOCKED`-by-construction cases, **not FAILs**: say so here so a run does not
file the missing half as a defect.

- <e.g. the cost-tasks endpoint is not deployed → its tab renders an empty state, which is EXPECTED>
```
