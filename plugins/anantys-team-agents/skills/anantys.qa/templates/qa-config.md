# QA environment contract — `.anantys/qa.md`

Written by `/anantys.qa init`, committed to the repo, read by every other action.
It holds everything that is true of **this project's environments** and nothing that is true
of the feature under test.

It declares **one or more environments**. `run --env <name>` / `retest --env <name>` picks one; with
none, the environment marked **default** is used — the `local` one, or a `shared` one in a project
with no local stack. Each is one **kind**:

- **`local`** — the developer's own stack. **Resettable**. Has a Reset block.
- **`shared`** — a deployed env (staging / preview / prod). **Never reset**; test data is created
  additively; driven through the operator's already-signed-in browser. Has **no** Reset block — an
  explicit "Reset: NONE" instead. Says whether it is production (`Production: yes | no`); on
  production, scenarios that charge a card, record consent or notify a real person are BLOCKED.

Every environment says **what drives the browser** in its `Driven by:` line — the operator's
connected browser, or a named local command. A `shared` env is always the operator's browser.

A file with **no** `## Environment:` blocks (the flat layout an earlier `init` wrote) is read as a
single `local` environment named `local`, marked default — it keeps working unchanged. Re-run
`init` to add a `shared` one: it first rewrites the flat sections as the `local` block below.

> **No secrets.** Record the *command* that retrieves a credential, never the credential.
> This file is committed.

> **No ambient targets.** Every destructive command — anything in a Reset block — must name the
> host / database / namespace it acts on **literally, in this file**. A command that resolves its
> target from the surrounding environment (`$DATABASE_URL`, a dotenv, the current `kubectl`
> context, an AWS profile, `docker compose` in whatever directory the shell is in) is not a
> `local` command: it is a command that runs wherever the shell happens to point. Selecting
> `--env local` chooses which *block* to read; it does nothing to the command inside it. If the
> project's only reset path is ambient (`make db-reset`), record a **target probe** beside it and
> the rule is: probe, compare to the declared target, abort on mismatch. Never reset on a probe
> that fails or returns something unexpected.

---

```markdown
# QA environment — <project>

_Last updated: <YYYY-MM-DD> — maintained by `/anantys.qa init`._

Environments below. `run --env <name>` selects one; default is the one marked default.

## Environment: local (`kind: local`, default)

Driven by: <the operator's connected browser | `<local command — screenshot script / headless runner>`>

### Surfaces
| What | URL |
|---|---|
| <app> | <url> |
| <marketing / secondary front> | <url> |
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

### Build identity — how this environment reports the code it is serving
```bash
<command or URL that returns the branch/commit actually running — a /version or /healthz
endpoint, a deployed-SHA banner, `docker inspect <container>`, a `git -C <deploy path> rev-parse`>
```
Leave this blank only if the project genuinely has no way to tell. `run` needs it to enforce a
plan's `**Under test:**` line; with no probe it must ask the operator and stop, never infer from
the local checkout — a local branch says nothing about what a remote stack runs.

### Reset — how to get a fresh test subject

Target: `<the host / database / namespace this block is allowed to touch — e.g. localhost:5432/app_dev>`

```bash
<probe that prints the target the reset command will actually resolve — e.g.
`psql "$DATABASE_URL" -tAc 'select current_setting(''listen_addresses'')||inet_server_port()'`,
`kubectl config current-context`, `docker compose config --format json | jq -r '.name'`>
```
Run the probe first, every time. If its output is not the declared Target, **stop** — do not reset,
and tell the operator their shell is pointed elsewhere. Same if the probe errors or prints nothing.

```bash
<command to delete / recreate the test account or fixture — prefer the form that names the target
explicitly (`psql -h localhost -d app_dev …`) over the form that reads it from the environment>
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
- Payment sandbox: `<test card / token>`

### Agent limits — steps a browser agent cannot perform
- <signup CAPTCHA> → hand the tab to the operator, resume after
- <viewports below the browser's clamp> → needs device emulation
- <emailed verification code> → operator relays the code

### Known drift — never file these as defects
- <e.g. an endpoint not deployed locally> — <why, and what a *real* failure would look like instead>

## Environment: staging (`kind: shared`)

Driven by: the operator's connected browser (their signed-in session)
Production: no

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

### Build identity — how this environment reports the code it is serving
```bash
<the deployed-SHA endpoint or banner of THIS env — e.g. `curl -s https://api.staging.<domain>/version`>
```
Per environment, never shared with `local`: staging lags `main` between deploys, and a plan's
`**Under test:**` line is only enforceable against what *this* env actually serves.

### Reset — NONE
Shared, persistent environment — **never reset it** and never run a destructive command against it.
This block being empty is not the protection: the protection is that no `local` Reset command can
resolve to this environment's host. Check that when `init` writes both blocks — if the `local`
reset would hit `<this host>` under any dotenv or context the operator might have loaded, fix the
`local` block, not this sentence.
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
