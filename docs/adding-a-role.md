# Adding a role


`marketplace.json` duplicates the plugin's name, version and description, and this README
enumerates every role — three places that silently go stale when a role is added or a
version bumped. Run the checker before pushing (stdlib only, no install):

```bash
python3 scripts/check_plugins.py
```

It fails on: a version/name/description mismatch between the two manifests, a skill whose
frontmatter `name` doesn't match its directory, an agent missing `name`/`description`/
`tools`/`model`, a role count in the description that the tree contradicts, a role the
README never mentions, and a role whose preamble does not link `TEAM-CONTRACT.md`. CI runs
it on every push and pull request.

## Linking the contract is not optional

`TEAM-CONTRACT.md` opens *"Rules that bind **every** role in this plugin"* and *"Every role
file points here"*. Those were assertions about the tree that nothing verified — true only
because every author had so far remembered. A new role that simply never mentions the
contract was a complete, installable, green role bound by nothing.

The incentive ran the wrong way, too. The contract counts toward the ceiling below, so the
five roles that point at it load 207–733 against a limit of 200. Deleting the one line that
binds each of them takes three under the ceiling and leaves the run green: the cheapest way
to satisfy the ceiling was to stop being bound. The ceiling may make a role shorter; it may
not make it unbound, so the link is now an error to omit and the warning's remedy says so.

The link must sit in the **preamble** — above the role's first `## ` heading. A link below
one is read when the reader reaches it, which is after the role has already acted; the check
measures the same region `check_load` does, for the same reason.

A plugin with no `TEAM-CONTRACT.md` at all is a **warning**, not an error: the contract is a
file some other change lands, and a gate that reddens every branch until it arrives forces
an order on changes that have none. It is not silent either — a check whose input is absent
must say so rather than print the output of a healthy run.

A role over 200 lines is a *warning*, not an error: a role file is loaded in full on every
invocation, so past that size the per-action detail belongs in a `reference/` page the
actions table links to.

**The 200 is a ceiling on the load, not on the file.** A role's preamble — everything above
its first `## ` heading — is where it names what binds it before it acts, so every local
`.md` it links there is read on the same invocation and counts toward the total. The checker
discovers those from the links, never from a filename: a role that points somewhere else is
measured against what it actually points at, and one that points nowhere is measured on
itself alone, exactly as before. The warning prints the breakdown, so the file to shrink is
visible without reopening any of them.

That distinction is not hypothetical. All seven roles open by linking a shared contract and
saying *"read it before acting"*; at 502 lines it made every one of them — including two
under 100 lines of their own — invoke at between 578 and 733 against a ceiling of 200, while
the checker reported one warning, for the one file that was individually long. A ceiling
measured on the wrong unit reads as compliance.
