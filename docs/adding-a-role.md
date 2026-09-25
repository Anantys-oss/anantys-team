# Adding a role


`marketplace.json` duplicates the plugin's name, version and description, and this README
enumerates every role — three places that silently go stale when a role is added or a
version bumped. Run the checker before pushing (stdlib only, no install):

```bash
python3 scripts/check_plugins.py
```

It fails on: a version/name/description mismatch between the two manifests, a skill whose
frontmatter `name` doesn't match its directory, an agent missing `name`/`description`/
`tools`/`model`, a role count in the description that the tree contradicts, and a role the
README never mentions. A `SKILL.md` over 200 lines is a *warning*, not an error: a skill
file is loaded in full on every invocation, so past that size the per-action detail belongs
in a `reference/` page the actions table links to. CI runs it on every push and pull request.
