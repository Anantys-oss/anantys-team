# QA environment contract — `.anantys/qa.md`

Written by `/anantys.qa init`, committed to the repo, read by every other action.
It holds everything that is true of **this project's dev environment** and nothing that is true
of the feature under test.

> **No secrets.** Record the *command* that retrieves a credential, never the credential.
> This file is committed.

---

```markdown
# QA environment — <project>

_Last updated: <YYYY-MM-DD> — maintained by `/anantys.qa init`._

## Surfaces

| What | URL |
|---|---|
| <app> | <url> |
| <marketing / secondary front> | <url> |
| <backend / API> | <url> |

⚠️ Note here any URL that *looks* right but is wrong (a closed port, a hostname that 404s).
A stale URL costs a whole run, and it is the single most common thing this file prevents.

## Preflight — stop the campaign if any of these fail

| # | Check | How | If it fails |
|---|---|---|---|
| P1 | <service> up | `<command>` returns <expected> | Ask the operator to start the stack. Never start it yourself |
| P2 | … | … | … |

⚠️ Call out the check whose *silent* failure is indistinguishable from slowness — e.g. a missing
webhook forwarder, an unseeded reference table. That is the one that wastes a campaign, because
nothing errors; the product just waits forever or quietly returns an empty state.

## Reset — how to get a fresh test subject

```bash
<command to delete / recreate the test account or fixture>
```

Client-side state to clear between runs:

- storage keys: `<keys>`
- cookies: `<names>`
- session: <how to genuinely sign out — note if the obvious way leaves a cookie alive>

Server-side leftovers that survive a client reset:

```bash
<commands to clear caches / queues / pending markers>
```

How to identify the test subject (ids, and how to find them when data is encrypted or hashed):

```bash
<query or command>
```

## Credentials

- <account>: `<identifier>` — password/secret: **ask the operator**, never stored here
- OAuth: the operator's account. Ask the operator for any emailed code; never read a mailbox
- Payment sandbox: `<test card / token>`

## Agent limits — steps a browser agent cannot perform

- <e.g. signup CAPTCHA> → hand the tab to the operator, resume after
- <e.g. viewports below the browser's clamp> → needs device emulation
- <e.g. emailed verification codes> → operator relays the code

## Known environment drift — never file these as defects

- <e.g. sandbox pricing differs from the configured grid> — <why, and what a *real* failure
  would look like instead>
```
