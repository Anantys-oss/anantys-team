# A stop is a result — the evidence for C2

Maintenance note for `plugins/anantys-team-agents/TEAM-CONTRACT.md`. Nothing loads this
file; it records what was measured, and what C2 deliberately leaves to each role.

## The measurement

Across all 28 open heads, added lines only:

| phrasing | hits |
|---|---|
| `record(s)? that it stopped\|leaves? a (record\|note\|trace) (that\|of)\|why it stopped\|stopped early` | **0** |
| `ambiguous (answer\|reply)\|cannot (tell\|determine) what the operator` | **0** |
| control — `screenshot` | 662 |
| control — a string that does not exist | 0 |

Every role gates, and several gates were hardened in this queue — `#8` gave `qa` the
browser gate it never had, `#18` gave the editing loops a third exit, `#9` made the
durable write happen before the destructive step. All of them decide *whether to
continue*. None says what the run leaves behind when the answer is no.

## Where it bites, per role

| role | the gate | on disk after the stop | what a later reader concludes |
|---|---|---|---|
| `ops` | browser unavailable ⇒ STOP, before Phase 0 | Phase 6 never overwrites `current.md`; no `Audit History` row; no journal entry | `current.md` is "the living snapshot that persists between audits" — unchanged, it reads as **current**. Indistinguishable from an audit that ran and found nothing to change. |
| `qa` | `shared` env pre-write confirmation — *"No go, no run"* | nothing appended to `qa-runs.md`; no per-environment status suffix added | `status` / `report` on that environment report no results — indistinguishable from **never attempted**. |
| `review` | Step E recommends, then STOPs pending confirmation | the analysis report exists (`#9` made it durable first) | the report states a recommendation and nothing states that it was never acted on. |
| `debug`, `design` | dirty tree, no browser, `UNRESOLVED`/`blocked` | nothing — the deliverable is the reply | clause 2 is vacuous here; clause 1 is not, and `#18` already implements it for the *exhaustion* exit, not for the gates above it. |

The compounding case is `ops`. Phase 0 step 1 reads `current.md` as its starting truth,
and `#42` has the next audit **score the advice the last one gave**. Three gated-out
attempts in a row, and the fourth grades recommendations from an audit weeks older than
it believes, from a snapshot that never said so.

## Why the contract, not three inline copies

Inline is cheaper on load: `ops`, `qa` and `review` pay the same lines either way, and
`debug` and `design` pay nothing instead of ~20. The contract buys the two things that
cost more than 40 lines of context:

- **One phrasing.** C1 exists because seven roles had each derived the same invariant at
  its own strength. Clause 2 is exactly the kind of rule that lands at three different
  strengths if written three times.
- **Three fewer contended files.** `anantys.ops/SKILL.md` is edited by five open heads,
  `anantys.review/SKILL.md` by four, `anantys.qa/SKILL.md` by three. This file is edited
  by one.

**Stated, not hidden — this costs a fourth warning.** C2 adds 20 lines to this file, so it
adds 20 to every role's load. Measured with `scripts/check_plugins.py` on the wave-1 union,
before and after:

| role | before | after |
|---|---|---|
| `ops` | 306 | 326 |
| `review` | 242 | 262 |
| `qa` | 230 | 250 |
| `design` | 192 | **212** — newly over |
| `debug` | 161 | 181 |

The three roles C2 binds were already over the 200-line ceiling *because of this file*, and
`design` — which C2's second clause does not reach, since it writes no durable artifact —
crosses it. That is a real cost, not a rounding error, and it is the one C2 pays knowingly:
the ceiling is a warning (`check_plugins.py` exits 0), and the defect it buys off is a
stopped run handing wrong state to the operator's repo with nothing to notice it by.

It also fixes the headroom: this file has **8 lines** before `design` crosses, and C2 spends
them. The next shared rule cannot be paid for out of this file — it lands inline, or one of
the five role files moves per-action detail into `reference/` first, which is the remedy the
checker already names and is a change to those files, not to this one.

## Deliberately not here

- **The exact shape of a stopped entry.** A dated no-run line in `current.md` and a
  stopped section in `qa-runs.md` are different artifacts with different schemas; C2
  requires the record and leaves the shape to the role that owns the file. Writing the
  schemas here would put this file back in the business of binding two roles out of seven.
- **A gate on it.** Same reason the 3-role threshold is unenforced: a check whose only
  remedy is "edit this file" serialises the queue.
