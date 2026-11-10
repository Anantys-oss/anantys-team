# Standing rulings template — `rulings.md`

Lives at `<workspace>/rulings.md`, beside `current.md` and `journal/`. **Append-only**, and read
in full at the start of Phase 5b — never summarised, never rewritten.

Why its own file rather than a section of `current.md`: `current.md` is overwritten whole on every
audit and rebuilt from the previous copy. That is a lossy channel — fine for a KPI table, which the
next run re-measures anyway, and wrong for a decision nobody re-measures. A ruling has to survive an
unbounded number of rewrites by a context that has never seen the conversation it came from.

---

```markdown
# Standing rulings — <domain>

A finding the operator has ruled on. `anantys.ops` reads this file before compiling a report and
does not re-raise a finding a live ruling covers. One entry per ruling; never edit an entry in
place — supersede it with a new one and strike the old.

## R<n> — <finding in one line>

- **Ruled**: <YYYY-MM-DD>, operator
- **Scope**: `https://example.com/pricing` | query `cheap widgets` | `site`
- **Observed then**: <the exact value the ruling was made against — the title string, the
  position, the CTR, the absent tag>
- **Ruling**: won't fix | by design | accepted cost | revisit after <named event>
- **Revisit when**: <the condition that ends this ruling, in a form a later audit can observe> |
  ask the operator — required when **Ruling** is `revisit after`, omitted otherwise
- **Reason**: <why — the sentence that stops this being re-argued next audit>
- **Still covers**: <the narrowed condition that is still a real finding, if any>

## ~~R<k>~~ — superseded by R<m> on <YYYY-MM-DD>
```

---

## Reading an entry

- **Observed then** is the pin. Re-raise the finding when the current observation differs from it,
  and say in the report that the ruling lapsed and on what. A ruling is a judgement about a value,
  not about a page — rewrite the page and the judgement has no subject.
- **Revisit when** is the second pin, and `revisit after` is the one ruling the first pin cannot
  expire. The operator ruled on a value *and* on a deadline; a redesign that leaves the word count
  alone moves the event without moving the value, so the pin still matches and the entry reads as
  live long after the deadline passed. Test both conditions — either one expires the ruling.
- **Scope** is literal. A ruling on one URL says nothing about the same finding on another, and
  `site` is a claim the operator makes explicitly, never a default you widen it to.
- An entry with no **Observed then** (written before this file had one) is scoped to its target and
  never lapses on its own. Re-confirm it with the operator instead of treating it as permanent.
- A `revisit after` entry with no **Revisit when** (same reason) has an event only the operator can
  read. Ask, and record the answer as a new entry. A temporary ruling the audit cannot expire is a
  permanent one, which is the opposite of what the operator said.
