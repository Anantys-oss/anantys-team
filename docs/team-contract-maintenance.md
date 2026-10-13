# Team contract — maintenance

Addressed to whoever edits `plugins/anantys-team-agents/TEAM-CONTRACT.md`. No role file
links this page, so nothing loads it at invocation time.

The contract applies one test to its own content: **who does the text bind?** Content
that binds every role stays in the contract. Content addressed to whoever *maintains*
it — the admission threshold, an argument for promoting a rule, a measurement that dates
a citation — binds no role and lives here.

The distinction is not cosmetic, because a role cannot act on non-binding text by
choosing not to. The contract is loaded in full before every action of every role, so a
line that binds nobody is charged seven times per invocation and removed from nowhere.

## What belongs in the contract

A rule belongs there when it binds **three or more roles** and is not specific to any of
them. Below that threshold it stays inline, in the role that needs it.

Amending a shared rule is then one edit to one file — not one edit per role, in N
phrasings, each free to land at a different strength.

**This is not enforced by CI, deliberately.** A gate whose only remedy is "edit this
file" puts every concurrent change on the same few lines and turns a parallel queue into
a serial one. The threshold is a review question: when a change would add the same rule
to a third role, it belongs in the contract instead.

## What does not

The same test, run the other way. The contract once carried 459 non-binding lines against
43 binding ones: eleven candidate rules, each a finding written in the imperative (*"make
the work durable, then ask"*), several stating the opposite of the role file they
described, under a heading saying *"a candidate does not bind"* — and, at the end,
instructions for a human resolving a rebase.

A disclaimer in the middle of a file is not a boundary; the file a role is told to read
is. **So: nothing enters the contract that a role is not required to do.** Where a
candidate and a role file disagree, the role file governs — a role blocked by that
disagreement has found the argument for promoting the candidate, which is a note for the
operator, not a side to pick.

## Where a candidate goes

Not here, and not into the contract. A candidate's evidence is a quotation from a file on
another branch, and a count measured in a tree that moves without the candidate changing.
Both stop being true when the queue lands, which is also when a reader first sees them.
That makes the pull-request conversation the candidate's home: the argument for promoting
a rule belongs where the branch carrying the rule is reviewed.

What survives into this repository is the rule and its reasoning — one file per rule under
[`docs/`](./). What does not is the queue state that produced it: a pull-request number, a
branch name, a conflict to resolve at landing.
