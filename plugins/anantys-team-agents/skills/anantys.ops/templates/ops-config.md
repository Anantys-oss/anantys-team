# `.anantys/ops.md` — template

Copy to `.anantys/ops.md` at the repo root. Fill it by interviewing the operator once; read it
on every run thereafter. See `docs/project-config.md` for what belongs here and what does not.

Every fact carries the date it was last confirmed. Confirming is part of using it: a URL that
404s or lands on the wrong property has expired — re-ask, rewrite the line, and say so in the
report.

---

```markdown
# ops — project configuration

## Property

- **Site domain:** example.com                          <!-- confirmed 2026-09-26 -->
- **Hub / key landing paths:** /blog, /best             <!-- confirmed 2026-09-26 -->
- **Search Console:** https://search.google.com/search-console/performance/search-analytics?resource_id=sc-domain%3Aexample.com
  <!-- confirmed 2026-09-26 -->
- **Analytics:** https://analytics.google.com/analytics/web/#/pNNNNNNNNN/reports/...
  <!-- confirmed 2026-09-26 -->
- **Workspace:** ./seo/

No credentials here. The browser is the operator's own and is already signed in. If a secret
is unavoidable, name where it lives — never the value.

## Target queries

The keywords this business competes on. Stable between runs; revisited when the operator says so.

- <query>
- <query>

## Usually in scope

Domains a run typically visits, beyond the property itself — a named competitor, a second
property. **This is not an approval.** Pre-flight still presents the exact list for this run and
waits; this section only means the operator will not be surprised by the ask.

- <domain> — <why>

## Known and not a finding

Things a previous audit already adjudicated, so they are not re-filed every run.

- <observation> — <why it is expected>
```

---

**Not in this file:** the traffic goal for this audit, the scope approved today, and anything the
operator decides per run. Those are the run's, and asking for them is the point.
