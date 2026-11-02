# Feature brief — the `--brief` / `--from linear:` / `--from pr:` source for `/anantys.qa plan`

The universal, non-spec-kit input to `plan`. It plays the two roles a spec-kit dir plays —
**requirements** (what each assertion cites) and **what shipped** (what was actually built) — in
one file. Write it by hand for a feature built any way (a bot-loop epic, a hotfix, a design doc),
or let `--from linear:SKU-…` / `--from pr:<url>` assemble one for you to confirm.

> Same discipline as spec-kit: assertions cite **requirement ids**, never the diff. Give every
> requirement a stable id here; `plan` will assign `R1`, `R2`, … to any that lack one and write
> them back, and runs / notes / reports reference those ids for the life of the feature.

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

Mark the ones that touch **money / legal / data** — they become the blocker list.

## What shipped

What was actually built, so the campaign tests the real surface rather than the wish. One line per
PR / change, enough to know which requirement it serves and where in the UI it lives. **Every line
names the requirement ids it serves** — this list is keyed by PR, and the ids are the only thing
that joins it back to the requirements above.

- <repo#PR — one line: what it added> — serves R1, R3
- …

## Not shipped / known gaps

Anything a requirement implies that is NOT in yet — a backend endpoint a UI calls, a deferred
follow-up. These are `BLOCKED`-by-construction cases, **not FAILs**: say so here so a run does not
file the missing half as a defect. Tag each item with the requirement ids it leaves unreachable.

- <e.g. the cost-tasks endpoint is not deployed → its tab renders an empty state, which is EXPECTED> — R4

## Requirements covered

**<n> of <m> accounted for.** Every id in Requirements appears in **What shipped** or in **Not
shipped / known gaps** — never both, never neither. List any that appear in neither:

- **Unaccounted: <none | R5, R7>**

An unaccounted requirement is not a shipped one. It reads as shipped to everyone downstream:
`plan` derives assertions for it, `run` walks them, and the FAIL on a surface that was never
built gets filed as a defect — the exact outcome **Not shipped** exists to prevent, except that
section only covers the gaps whoever wrote this brief happened to remember. A spec-kit campaign
cannot make this mistake, because `tasks.md` *is* the what-shipped list and `plan` counts it.
A brief has no such list unless this section is filled in, so `plan` stops on a non-empty
Unaccounted line rather than guessing which side the id belongs on.
```
