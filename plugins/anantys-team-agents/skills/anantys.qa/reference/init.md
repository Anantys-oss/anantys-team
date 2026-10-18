# `init` — write the environment contract

Read `reference/environments.md` first: it defines the two kinds an environment can be, and `init`
is where that choice is recorded.

The skill knows *how* to QA. It must know nothing about *this* project's stack. Everything
environment-specific goes into `.anantys/qa.md` at the repo root.

Read `templates/qa-config.md` for the shape. Fill it by **interviewing the operator**, but do the
legwork first so the questions are few and precise:

- Read `README.md`, `CLAUDE.md`/`AGENTS.md`, `Makefile`, `docker-compose*.yml`, `.env.example`, `package.json` scripts.
- Detect running services: `docker ps`, and probe likely dev hostnames.
- Reading `.env` is reading secrets — `SKILL.md`'s redaction rule applies here in full.

Then ask the operator only what you could not infer, in one batch:

- **Which environments exist** — the local stack, and any deployed ones worth testing against
  (staging, a PR preview). Give each a name and a `kind:` (`local` / `shared`), and mark exactly
  one as **default** — the `local` one when there is one; a project with no local stack marks a
  `shared` env default instead.
- **Per environment:** the real base URLs (a dev stack behind a reverse proxy is rarely on
  `localhost:<port>`), **what drives the browser** (`Driven by:` — the operator's connected
  browser, or a named local command such as a screenshot script or headless runner), the preflight
  checks whose failure would waste a whole campaign, **how that environment reports the code it is
  serving** (a `/version` or `/healthz` endpoint, a deployed-SHA banner, a `docker inspect` — the
  build-identity check `run` uses to enforce a plan's `**Under test:**` line; it is per environment,
  since staging lags `main` between deploys), test credentials, and any known drift that must not
  be filed as a defect.
- **`local` only:** the reset procedure for a fresh test subject, and a payment sandbox instrument
  (test card / token) if any journey touches money — without one, every checkout case is BLOCKED.
- **`shared` only:** how the operator's signed-in browser session is made available to you, whether
  a real record exhibiting the behaviour under test exists there (a shared env has no fixtures), and
  how deploy lag shows up (a fix merged but not yet deployed), and **whether it is production**
  (`Production: yes | no`). A `shared` block is always written with `Reset — NONE`, never a reset
  command — do not ask for one.

Write only the environments the operator named, with real values — never copy a template block
full of `<placeholders>` into the contract. Re-running `init` on an existing file adds or updates
environment blocks and leaves the others untouched.

**Re-running `init` on a flat file migrates it first.** If the existing `.anantys/qa.md` has no
`## Environment:` blocks (the legacy layout, see `reference/environments.md`), rewrite its flat
`## Surfaces` / `## Preflight` / `## Reset` / `## Credentials` / … sections as one
`## Environment: local (kind: local, default)` block **before** adding any new one, and show the
converted file in the confirmation below. Appending a `shared` block to a flat file leaves the local
sections read by nothing and no environment marked default — the local campaign stops resolving.

Confirm the file back to the operator before writing. `.anantys/qa.md` is committed — so it must
contain **no secrets**, only the commands that retrieve them.

`init` is the one action that does **not** end its reply with the progress table: there is no plan
yet.
