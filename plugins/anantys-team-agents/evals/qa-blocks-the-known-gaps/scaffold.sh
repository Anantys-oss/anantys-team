#!/usr/bin/env bash
# The trap: R3's surface renders an empty state because the endpoint behind it
# is not deployed, and the brief says so. An empty state looks exactly like a
# bug, so the tempting plan asserts R3 and lets the run file it. The role's
# rule is that a declared gap is BLOCKED by construction, never a FAIL — "the
# case this whole section exists to prevent".
#
# No app and no browser: `plan` only reads the source and writes the campaign.
set -euo pipefail

mkdir -p .anantys

cat > .anantys/qa.md <<'CFG'
# QA environment — subscribe-funnel

_Last updated: 2026-09-30 — maintained by `/anantys.qa init`._

Environments below. `run --env <name>` selects one; default is the one marked default.

## Environment: local (`kind: local`, default)

Driven by: the operator's connected browser

### Surfaces
| What | URL |
|---|---|
| app | http://localhost:3000 |

### Preflight — stop the campaign if any fail
| # | Check | How | If it fails |
|---|---|---|---|
| P1 | checkout present | `test -f product-brief.md` exits 0 | Ask the operator for the project root |

### Build identity — how this environment reports the code it is serving
```bash
cat ./run/deployed-sha
```

### Reset — how to get a fresh test subject
```bash
rm -rf ./run/fixtures
```

### Credentials
| What | How to obtain |
|---|---|
| test operator | `grep -oE 'QA_USER=.*' .env` |

### Known drift — never file these as defects
- none recorded
CFG

cat > product-brief.md <<'BRIEF'
# Subscribe funnel

_Source: hand-written. Assembled 2026-09-30._

## Requirements

- **R1** A visitor can choose a plan and a billing period before paying.
- **R2** Checkout is priced for the selected plan and period. (money)
- **R3** A subscriber sees their next invoice date and amount on the billing page.

## What shipped

- app#211 — plan + period selector on the pricing page, serves R1.
- app#212 — checkout reads the selection and prices it, serves R2.
- app#213 — the billing page's "Next invoice" panel, serves R3.

## Not shipped / known gaps

- The `/billing/next-invoice` endpoint app#213 calls is **not deployed**. The panel renders its
  empty state ("No upcoming invoice") instead of a date and amount. That is EXPECTED until the
  endpoint ships — it is not a defect in the funnel.
BRIEF
