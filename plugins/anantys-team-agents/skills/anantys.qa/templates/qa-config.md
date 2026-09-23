# QA environment contract — `.anantys/qa.md`

Written by `/anantys.qa init`, committed to the repo, read by every other action.
It holds everything that is true of **this project's environments** and nothing that is true
of the feature under test.

It declares **one or more environments**. `run --env <name>` / `retest --env <name>` picks one; with
none, the environment marked **default** (a `local`) is used. Each is one **kind**:

- **`local`** — the developer's own stack. **Resettable**; driven by the project's local browser
  tooling. Has a Reset block.
- **`shared`** — a deployed env (staging / preview / prod). **Never reset**; test data is created
  additively; driven through the operator's already-signed-in browser. Has **no** Reset block — an
  explicit "Reset: NONE" instead.

> **No secrets.** Record the *command* that retrieves a credential, never the credential.
> This file is committed.

---

```markdown
# QA environment — <project>

_Last updated: <YYYY-MM-DD> — maintained by `/anantys.qa init`._

Environments below. `run --env <name>` selects one; default is the `local` marked default.

## Environment: local (`kind: local`, default)

### Surfaces
| What | URL |
|---|---|
| <app> | <url> |
| <backend / API> | <url> |

⚠️ Note any URL that *looks* right but is wrong (a closed port, a hostname that 404s). A stale URL
costs a whole run, and it is the single most common thing this file prevents.

### Preflight — stop the campaign if any fail
| # | Check | How | If it fails |
|---|---|---|---|
| P1 | <service> up | `<command>` returns <expected> | Ask the operator to start the stack. Never start it yourself |
| P2 | … | … | … |

⚠️ Call out the check whose *silent* failure is indistinguishable from slowness — a missing webhook
forwarder, an unseeded reference table. Nothing errors; the product just waits or returns empty.

### Reset — how to get a fresh test subject
```bash
<command to delete / recreate the test account or fixture>
```
Client-side state to clear between runs: storage keys `<keys>`, cookies `<names>`, session
`<how to genuinely sign out — note if the obvious way leaves a cookie alive>`.
Server-side leftovers that survive a client reset:
```bash
<commands to clear caches / queues / pending markers>
```
How to identify the test subject (ids, and how to find them when data is encrypted/hashed):
```bash
<query or command>
```

### Credentials
- <account>: `<identifier>` — secret: **ask the operator**, never stored here
- OAuth: the operator's account. Ask for any emailed code; never read a mailbox

### Agent limits — steps a browser agent cannot perform
- <signup CAPTCHA> → hand the tab to the operator, resume after
- <emailed verification code> → operator relays the code

### Known drift — never file these as defects
- <e.g. an endpoint not deployed locally> — <why, and what a *real* failure would look like instead>

## Environment: staging (`kind: shared`)

### Surfaces
| What | URL |
|---|---|
| <app> | https://app.staging.<domain> |
| <backend / API> | https://api.staging.<domain> |

### Preflight — stop the campaign if any fail
| # | Check | How |
|---|---|---|
| S1 | App reachable | `curl -sk -o /dev/null -w '%{http_code}' <app-url>` → 200/307, not 000 |
| S2 | Signed in | the operator's browser is signed in; the agent reuses that session and never signs in |
| S3 | The feature has real DATA | the behaviour under test exists on a real record — a shared env has no fixtures, so a campaign against one with no such data can only report BLOCKED |

### Reset — NONE
Shared, persistent environment — **never reset it** and never run a destructive command against it.
Create test data **additively** (a new record; a new PR → a real run). Drive it through the
operator's already-signed-in browser session.

### Credentials
- OAuth: the operator's live session — the agent never signs in.

### Agent limits — steps a browser agent cannot perform
- The same browser limits as local; plus **no reset** and **no destructive writes**.

### Known drift — never file these as defects
- A fix merged to `main` is not live until the next deploy — a defect a merged-but-undeployed PR
  already fixes is EXPECTED here; name the PR that closes it rather than filing it anew.
```
