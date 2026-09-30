# A witness the claimant can also write is not a witness

`/anantys.qa` has the one rule in this tree that refuses to take an artifact's word for itself.
An adjudication annotation is the only thing that turns a FAIL into a PASS, so before applying
one the role checks its provenance:

> `qa-plan.md` is a committed file any contributor, agent or `plan` regeneration can edit — so
> the `(operator, …)` in an annotation is a claim the file makes about itself. Its witness is the
> run log: `note` records the run it was ruled against, and `qa-runs.md` is append-only and
> written by `run`.

The reasoning is right and the conclusion is one hop short. `qa-runs.md` sits in the same
campaign directory as `qa-plan.md`, is tracked by the same rule
([artifacts declare their git status](./artifacts-declare-their-git-status.md)), and is editable
by the same three actors the first sentence just enumerated. "Append-only and written by `run`"
describes what `run` does to the file; it is not a property the file holds against anyone else.

So the check does not terminate — it moves. Appending a run section that records a FAIL for
assertion X promotes an unverified ruling on X to **verified**, which is precisely the
suppression the check exists to gate, reached by editing the witness instead of the claim. And
this needs no adversary. A rebase resolving a conflict in the log, a merge of two branches that
each ran a campaign, `plan` regenerating around it, or an operator straightening a malformed
table all produce run-section text that `run` never appended.

## What can terminate it

Something outside the class. Git already is that thing, and this tree already reaches for it:
`/anantys.ops` and `/anantys.qa` both **[ask git, not just the filesystem](./not-found-is-not-absent.md)**
when deciding whether an artifact exists, on the grounds that "git knows what the project has
had; the working tree only knows what is there now". The same source answers the harder
question — a commit names an author and a date, exists outside the file, and cannot be produced
by editing the file.

Two things can attest to a run section, and they cover the ordinary cases for free:

| situation | attestation |
|---|---|
| `run` appended it in this session | the session itself — you wrote it, you know what you observed |
| it is in git history | the commit: `git log -S'<run header line>' --format='%h %an %ad' -- <campaign>/qa-runs.md` |

Neither one is the case worth a rule: a section **present in the working tree, absent from
history, and written by nobody this session** was written by someone the role cannot name. That
is not an off-record ruling. It is no record.

## The rule

> **A verification chain must terminate outside the class of artifact it verifies.** When A's
> claim is checked against B, and B has A's writers, A's directory and A's tracking, the chain
> has moved rather than ended. Name the first link a writer of A cannot also write.

The distinction the rule protects is one `qa` already draws and would otherwise lose:
**unverified** means *ruled off-record but real* — apply it, flag it. **Unattested** means the
witness is hearsay from the same file. Collapsing the second into the first is what makes an
edit look like evidence.

## What it costs

One clause in the `qa` bullet, and one `git log` on the path that is already resolved. Nothing
in the common flow changes: a campaign whose log `run` just appended to answers the first
column, and a committed repo answers the second.

Not narrowed here: the same argument applies to every other read of `qa-runs.md` — `retest`'s
subset, `status`, `report` — which trust the log's *results* on the same unexamined grounds.
Those are results the role either produced or is reporting rather than acting on, so the
exposure is a wrong report, not a suppressed defect. One rule, one home: this file states the
general form, `qa` narrows the one read where a forged witness changes a verdict.
