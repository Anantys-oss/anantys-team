# One field, two names, two meanings

A skill declares `allowed-tools`. An agent declares `tools`. Both are read by
`scripts/check_tool_grants.py` through one parser, and until now by one set of
checks. The loader does not treat them as one field, and the difference is not
cosmetic: in an agent, a `Tool(scope)` entry keeps the tool and throws the
scope away.

Measured against Claude Code **2.1.278** (`claude --version`), the version this
repo's other platform docs are measured against.

## What the loader does

Both fields accept the same two spellings. The frontmatter schema types
`allowed-tools` and `tools` identically — *"Comma-separated string or YAML
list"* — so `tools: ["Bash", "Read"]` and `tools: Bash, Read` are the same
list. That is where the similarity ends.

`allowed-tools` is a **permission** list. Its entries become allow rules, and a
rule body is what a rule is for: `Bash(mkdir:*)` permits `mkdir` and nothing
else `Bash`.

`tools` is a **toolset** list. The schema's own one-liner says so — *"Tools
available to this agent. **Replaces the default set**."* Resolving it walks the
declared entries, splits each into `{toolName, ruleContent}`, and looks the
**tool** up by the bare name:

```js
for (let N of h) {                         //  h = the agent's `tools` list
  let { toolName: q, ruleContent: Q } = Jn(N);
  if (q === ht) {                          //  ht = the Task tool
    if (Q) { /* Q is the allowed subagent-type list */ }
  }
  let Le = W.get(q);                       //  W is keyed by bare tool name
  if (Le /* … */) { se.push(N); te.push(Le) }   //  te = resolvedTools
}
```

`te` holds whole tools. `Q` is read for exactly one tool — `Task`, where it is
the comma-separated list of subagent types this agent may spawn — and is
discarded for every other. Nothing downstream re-adds it: an agent's `tools`
never reaches the allow-rule table that a skill's `allowed-tools` feeds. The
sibling field `disallowedTools` is parsed the same way and loses its scopes
too, by a helper that keeps only `toolName`.

## What that means for this tree

| frontmatter | on a skill | on an agent |
|---|---|---|
| `Bash(git diff:*)` | `git diff …` only | **all of `Bash`** |
| `Bash(mkdir:*)` | `mkdir …` only | **all of `Bash`** |
| `Task(anantys.code-auditor)` | that agent only | that agent only |
| `Read` | `Read` | `Read` |

Row 1 is live in two open branches. `koan/auditor-independent-yardstick` (#13)
narrowed `anantys.code-auditor` from `tools: ["Bash", …]` to
`tools: ["Bash(git diff:*)", "Bash(git show:*)", "Bash(gh pr view:*)",
"Bash(gh issue view:*)", …]`, and `koan/the-product-without-the-scaffolding`
(#63) carries that forward with `Bash(git log:*)` added. Both read as a
read-only grant for an agent whose whole contract is *"Reports gaps only;
writes no code."* Neither is one. The auditor holds `rm -rf` and `git push`,
exactly as it did before the narrowing, and the diff that looks like a
tightening changes nothing the runtime can see.

This is the failure the module docstring of `check_tool_grants.py` already
names in the abstract — *"a grant that reads as a narrowing but bounds
nothing"* — reached by a second road the file did not know about. `UNBOUNDED`
catches a prefix whose **command** runs other commands. This catches a prefix
the **loader** never applies, which is every prefix, on every tool, on every
agent.

Worse, it was silent in the other direction too. Before this change the gate
measured those branches' auditor against `{"git diff", "git show", "gh pr
view", "gh issue view"}` and would have rejected any other command its prose
ran — enforcing, in CI, a restriction that does not exist at runtime, on a tree
where that is backwards.

## The rule

`agent_scopes` in `check_tool_grants.py` reports every scoped entry in an
agent's `tools` as an error, exempting `Task`, and rewrites the rest to their
bare tool name before any other check runs. Downstream the role is measured
against what it actually holds.

The remedy is never "write a tighter scope", because no scope is kept. Either:

- grant the bare tool and state the bound in the prose — an agent is a prompt,
  and the prompt is the only place that restriction can live; or
- drop the tool.

For `anantys.code-auditor` the first is the right one. "Reports gaps only" is
already in its description, and its body already names the four commands it
runs. That sentence is the restriction. It always was.
