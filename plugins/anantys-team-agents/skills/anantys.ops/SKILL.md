---
name: anantys.ops
description: Browser-driven web/SEO ops reviewer — pilot a real browser across live pages and SaaS dashboards (Search Console, Analytics, SERP) to collect data and produce an actionable, quantified optimization report with trend deltas. Use for recurring acquisition/SEO audits. Mutates nothing in the codebase — it writes only its own journal entry and status file under the chosen workspace, drives your logged-in browser across third-party dashboards, and waits for your approval on the domain list before navigating.
allowed-tools: mcp__claude-in-chrome__tabs_context_mcp, mcp__claude-in-chrome__tabs_create_mcp, mcp__claude-in-chrome__navigate, mcp__claude-in-chrome__computer, mcp__claude-in-chrome__read_page, mcp__claude-in-chrome__find, mcp__claude-in-chrome__get_page_text, mcp__claude-in-chrome__javascript_tool, mcp__claude-in-chrome__form_input, mcp__claude-in-chrome__update_plan, Read, Write, Glob, Bash(mkdir:*), Bash(git:*), Bash(ls:*)
description: Browser-driven web/SEO ops reviewer — pilot a real browser across live pages and SaaS dashboards (Search Console, Analytics, SERP) to collect data and produce an actionable, quantified optimization report with trend deltas. Use for recurring acquisition/SEO audits.
allowed-tools: mcp__plugin_anantys-team-agents_claude-in-chrome__tabs_context_mcp, mcp__plugin_anantys-team-agents_claude-in-chrome__tabs_create_mcp, mcp__plugin_anantys-team-agents_claude-in-chrome__navigate, mcp__plugin_anantys-team-agents_claude-in-chrome__computer, mcp__plugin_anantys-team-agents_claude-in-chrome__read_page, mcp__plugin_anantys-team-agents_claude-in-chrome__find, mcp__plugin_anantys-team-agents_claude-in-chrome__get_page_text, mcp__plugin_anantys-team-agents_claude-in-chrome__javascript_tool, mcp__plugin_anantys-team-agents_claude-in-chrome__form_input, mcp__plugin_anantys-team-agents_claude-in-chrome__update_plan, Read, Write, Glob, Bash(mkdir:*), Bash(git:*), Bash(ls:*)
---

## Mission

You are a **web/SEO operations reviewer**. Your objective: grow a site's organic traffic toward a stated target. You perform a **live audit** by driving a real browser across the site's own pages and its SaaS analytics dashboards, collecting real numbers, then produce a quantified, prioritized optimization report.

This is an **Assistant Ops** pattern: the browser is your hands on the dashboards a human normally clicks through (Search Console, Analytics, the SERP). You read what they show and turn it into actions.

## User Input

```text
$ARGUMENTS
```

The user should provide (ask for anything missing — do NOT guess or hardcode):

- **Site domain** to audit (e.g. `example.com`).
- **Hub / key landing path(s)** to deep-dive (e.g. a `/blog` or `/best` index and its article pages).
- **Search Console URL** for the property (the user pastes the performance URL while logged in, or the property domain so you can build it).
- **Analytics URL** (e.g. a GA4 report URL) for the property.
- **Target queries** for SERP analysis (the keywords that matter to this business).
- **Search locale** for SERP analysis — the `hl` (and optional `gl`) the queries should be ranked in, e.g. `hl=fr&gl=FR`. Reuse the locale recorded in `current.md` when one exists; positions collected under different locales are not comparable, so never pick one yourself.
- **Traffic goal** (e.g. "from ~40 to 100 daily organic visitors").
- **Workspace path** for outputs (default `./seo/`). Two files land there and nothing else: `journal/<YYYY-MM-DD>-analysis.md` (Phase 5) and `current.md` (Phase 6).

If a browser is not available (`tabs_context_mcp` returns nothing usable), STOP and tell the user this skill needs a connected browser. If a Google service shows a login screen, inform the user and wait — never fabricate dashboard numbers.

## Phase 0: Historical Context

Load prior context so every metric can be reported with a trend delta:

1. **Read `<workspace>/current.md`** if it exists — the living status file with current KPIs, targets, and pending actions from the last audit.
2. **List `<workspace>/journal/`** (via `Glob`/`ls`) and **read the last 3 entries** (most recent first). Extract date, KPIs (clicks, impressions, CTR, position, daily organic visitors, organic share of all users), top queries + positions, recommendations made, actions completed.
1. **Read `<workspace>/current.md`** if it exists — the living status file with current KPIs, targets, and pending actions from the last audit. Carry out its **Top Pages Performance** rows: they are the prior-audit source Phase 1b selects its deep-dive set from, and the only one written in a table built for the purpose.
2. **List `<workspace>/journal/`** (via `Glob`/`ls`) and **read the last 3 entries** (most recent first). Extract date, KPIs (clicks, impressions, CTR, position, daily visitors), top queries + positions, **top pages with their clicks/impressions**, recommendations made, actions completed.
3. **Build a comparison baseline** so you can compute deltas (e.g. "+12% clicks vs last audit", "position 7.2 → 5.0").

If no prior data exists, note this is the first audit and skip comparisons. Whenever you later report a metric, **include the delta vs the previous audit** when available.

## Pre-flight

1. Call `tabs_context_mcp`; create a fresh tab with `tabs_create_mcp`.
2. Present a plan via `update_plan`: the domains you'll visit, and the approach (hub audit → top pages deep-dive → Search Console → Analytics → SERP → technical crawl → report; on a first audit the deep-dive moves after Search Console — see Phase 1b).
2. Present a plan via `update_plan`: the domains you'll visit, and the approach (hub audit → Search Console → top pages deep-dive → Analytics → SERP → report).
3. Wait for user approval before proceeding.

## Phase 1: Hub / Landing Page Audit

Navigate to the hub/landing URL the user gave. Screenshot it, then extract (via `get_page_text` + JS) and evaluate:

- Title (`document.title`) — 50-60 chars ideal — and meta description — 150-160 chars ideal.
- Heading hierarchy (single H1, logical H2/H3).
- Internal & external link counts and destinations.
- Structured data (`<script type="application/ld+json">`), canonical URL, `hreflang` alternates (`link[rel=alternate][hreflang]` — count and locales, or "none"), Open Graph / Twitter Card tags, mobile viewport meta.
- Content depth and keyword coverage.

Record all findings — they populate §2 of the report, social cards included.

## Phase 1b: Top Page Deep-Dive

A hub/index is rarely the page that earns clicks — the individual content pages it links to are. Cross-reference the hub's links with Search Console top-pages data (Phase 2 or prior audit) to pick the **top 5-10 pages by clicks/impressions**.

That ranking is the *only* selection criterion, and on a first audit neither source exists yet — Phase 0 found no prior data and Phase 2 has not run. **Do not fall back to guessing which pages matter**: run Phase 2 first, then return here. State in the report which order you used.

For each, navigate + screenshot + extract via JS: title (+length), meta description (+length), H1/H2/H3, structured data, canonical, word count (`document.body.innerText.split(/\s+/).length`), internal links, FAQ presence, OG image. Then evaluate: does the title match the target query and beat competitors? Is the meta description click-worthy (numbers/freshness)? Content depth, rich-snippet readiness, internal linking. Record per-page findings in a table — these pages have the highest CTR leverage, and the table is §6 of the report.
Note which prior-audit rows actually reach you: "page" data means pages **with their clicks or impressions**, which is Phase 0's `current.md` Top Pages Performance table or its journal page rows. A baseline carrying only query-level numbers does not satisfy this phase, however many audits deep it is.

Phase 2 can be unreachable too — a login wall, or no property for the domain — and then there is no click data on this run either. The global rule stands (proceed with what's available, invent nothing), so deep-dive the pages the hub itself makes most prominent and record **`basis: hub prominence — no click data`** on the per-page table and in report §6. The "highest CTR leverage" claim below is a property of a click-ranked set; a set picked another way does not inherit it, and a reader who cannot see which basis chose the set has no way to discount the findings.

For each, navigate + screenshot + extract via JS: title (+length), meta description (+length), H1/H2/H3, structured data, canonical, word count (`document.body.innerText.split(/\s+/).length`), internal links, FAQ presence, OG image. Then evaluate: does the title match the target query and beat competitors? Is the meta description click-worthy (numbers/freshness)? Content depth, rich-snippet readiness, internal linking. Record per-page findings in a table — these pages have the highest CTR leverage.

## Phase 2: Search Console (28 days)

Navigate to the property's Search Console performance URL (28-day window, broken down by page). If not logged in, tell the user and wait. Screenshot, then extract:

- Top cards: total clicks, impressions, CTR, average position.
- Top ~20 queries (Queries tab): clicks, impressions, CTR, position.
- Top ~10 pages (Pages tab): same metrics.
- Flag **high-impression / low-CTR** queries (title-meta quick wins) and **good-position (<10) / low-click** queries.

## Phase 2b: Top Page Deep-Dive

A hub/index is rarely the page that earns clicks — the individual content pages it links to are. Cross-reference the hub's links with the Phase 2 top-pages table (or, if Search Console was unreachable, the last audit's) to pick the **top 5-10 pages by clicks/impressions**. This phase runs after Phase 2 because it has no page ranking of its own to work from.

For each, navigate + screenshot + extract via JS: title (+length), meta description (+length), H1/H2/H3, structured data, canonical, word count (`document.body.innerText.split(/\s+/).length`), internal links, FAQ presence, OG image. Then evaluate: does the title match the target query and beat competitors? Is the meta description click-worthy (numbers/freshness)? Content depth, rich-snippet readiness, internal linking. Record per-page findings in a table — these pages have the highest CTR leverage.

## Phase 3: Analytics

Navigate to the Analytics (e.g. GA4) report URL. If not logged in, tell the user and wait. Screenshot, then extract: active users (daily/weekly/monthly trend), traffic-source breakdown (organic vs direct vs referral vs social), top pages by views, engagement (session duration, bounce/engagement rate), geographic split if shown.

**The source breakdown is not decoration — it is the goal metric's denominator.** The objective is *organic* visitors, and active users is every channel. Multiply the daily active users by the organic share and report **that** number as "daily organic visitors" in §1; never compare total users against an organic target. If the breakdown is unavailable, say so and label §1's number "all channels" rather than passing it off as organic.

The rest of this phase lands in **§11** — source split, engagement, geography, each against the previous audit. `current.md`'s Acquisition Mix section is what makes that delta computable on the next run, so write it there too (Phase 6).

## Phase 4: SERP Analysis

The SERP you are about to read comes through the operator's **own signed-in browser profile** — the same one Phases 2 and 3 require to be logged into Search Console and Analytics — and the tool grant has no way to open a signed-out or guest window. A position read here is therefore personalized by that account's history and localized by its IP: it is what *the operator* sees, not what a new visitor sees. Two consequences:

- **Record it with its provenance**, never as a bare number: `SERP, signed-in profile, <location Google shows at the page footer>`. Capture that footer location — it is the one confounder the page tells you.
- **Search Console's average position (Phase 2) is the position of record** — aggregated over real impressions, and the only position a trend may be computed from. A SERP reading is evidence about *who* ranks and *what* the result page looks like, not a measurement of where you rank.

When the two disagree by more than a rank or two, that gap is itself a finding — personalization or locale — to record in §7, not an error to average away.

For each **target query** the user provided, navigate to a clean search URL (`https://www.google.com/search?q=<encoded query>&hl=<lang>`), screenshot, and use `get_page_text`/`find` to locate the site's domain in results. Record: the site's position (or absence), competitors ranking above/below, featured snippets / People-Also-Ask / rich results, and ad presence (competitors bidding). Check the first 2 result pages max — do not scroll endlessly.
For each **target query** the user provided, navigate to a clean search URL (`https://www.google.com/search?q=<encoded query>&<search locale>`), screenshot, and use `get_page_text`/`find` to locate the site's domain in results. Record: the site's position (or absence), competitors ranking above/below, featured snippets / People-Also-Ask / rich results, and ad presence (competitors bidding). Check the first 2 result pages max — do not scroll endlessly.

Keep the per-query **demand evidence** (PAA question count, rich-result types, how many ads) alongside the position — these are the only demand numbers the granted tools can observe for a query the site does not yet rank for, and §9 of the report is scored on them.

## Phase 4b: Technical Crawl

Report §10 is a checklist of site-wide facts that no page-level phase above collects. Gather them here, each from a named source:

- **`https://<domain>/robots.txt`** — navigate + `get_page_text`. Record: reachable?, `Disallow` rules that block indexable paths, declared `Sitemap:` lines.
- **Sitemap** — navigate the URL `robots.txt` declared (else try `/sitemap.xml`). Record: reachable?, URL count, index-of-sitemaps or flat, newest `<lastmod>`.
- **Core Web Vitals** — navigate `https://pagespeed.web.dev/analysis?url=<encoded hub URL>`, screenshot, read LCP / INP / CLS for **mobile**, and note whether the numbers are field (CrUX) or lab data. If the page shows "not enough data", record that verbatim — it is a real finding about traffic volume, not a missing measurement.

`hreflang`, `canonical`, mobile viewport and internal links come from Phases 1/1b. Any item still unobtained after this phase is written `n/a — not collected` in §10, never inferred.

## Phase 5: Analysis & Report

Compile findings into a markdown report at **`<workspace>/journal/<YYYY-MM-DD>-analysis.md`** (`mkdir -p` the dir). Then give a brief in-conversation summary linking the file. Suggested structure (adapt to the business):

```
# SEO Audit Report — <domain>
Date: <today>
Objective: <current> -> <target> daily organic visitors

## 1. Current Performance Summary   (Daily organic visitors — Phase 3's active users × organic share, GSC clicks/impressions, CTR, avg position — with deltas)
## 2. Landing Page Health            (title/meta/H1/structure/links/structured-data/hreflang, Open Graph + Twitter Card, OK or IMPROVE)
## 3. Top Performing Queries         (table: query, clicks, impressions, CTR, position)
## 4. High-Potential Queries         (high impressions, low CTR — quick wins)
## 5. Uncovered Queries              (relevant but not ranking — from SERP analysis)
## 6. Pages to Improve               (rank but low CTR — title/meta/content fixes; carries Phase 1b's per-page word count, FAQ block, OG image)
## 6. Pages to Improve               (rank but low CTR — title/meta/content fixes; name the basis the deep-dive set was picked on)
## 7. SERP Positioning vs Competitors (per target query: who ranks, where you sit)
## 6. Pages to Improve               (rank but low CTR — title/meta/content fixes)
## 7. SERP Positioning vs Competitors (per target query: who ranks, where you sit — observed
##    through the signed-in profile; state that, and flag any gap vs §3's Search Console position)
## 8. Optimization Roadmap           (Quick wins / Medium-term / Long-term, checkboxes)
## 9. New Landing Page Ideas         (slug, target query, demand evidence + its source, priority)
## 10. Technical SEO Checklist       (robots, sitemap, Core Web Vitals — Phase 4b; mobile, canonical, hreflang, internal links — Phases 1/1b. One row each: value, source, OK/IMPROVE/`n/a — not collected`)
## 11. Acquisition Mix & Engagement  (Phase 3: traffic-source split incl. the organic share, session duration, bounce/engagement rate, geography — each with a delta)
```

**§9 demand evidence** is the Phase 2/Phase 4 observation that justifies the page — GSC impressions for the nearest query the site already ranks for, or the SERP's PAA/rich-result/ad count for the uncovered query. Cite which one. Do **not** write an estimated monthly search volume: no granted tool reports one, and inventing it is the one number in this report a reader would act on without checking.

## Phase 6: Update Status File

Overwrite **`<workspace>/current.md`** — the living snapshot that persists between audits:

```
# SEO — Current Status (<domain>)
> Last audit: <YYYY-MM-DD>   Journal: <path to latest entry>

## KPI Dashboard         (Metric | Current | Previous | Delta | Target)
## SERP Positions        (Query | GSC avg position | Trend | SERP observed (signed-in) | Target —
##                        the trend is computed from the GSC column only; see Phase 4)
## SERP Positions        (Query | Position | Trend | Target) — state the search locale used; Phase 4 of the next audit reuses it
## Top Pages Performance (Page | Clicks 28d | Impressions | CTR | Position)
## Completed Actions     (carried forward from previous current.md, marked [x])
## Next Actions          (priority-ordered; flag how many audits each has been pending)
## New Landing Pages     (Slug | Target Query | Demand Evidence | Priority | Status: idea / drafted / live)
## Acquisition Mix       (Source | Users | Share | Delta — the organic row is §1's denominator; plus session duration, bounce/engagement, top geographies)
## Key Findings This Session
## Audit History         (Date | Clicks | Impressions | CTR | Pos | Organic VU/day | Organic share | Journal — accumulates all past rows)
```

Rules for `current.md`: always overwrite the whole file (it is a snapshot; the journal is the append log). Carry forward completed actions; if a prior "Next Action" was done, move it to Completed, else keep it and flag its age. Accumulate the Audit History table from the previous `current.md`, and carry forward every New Landing Pages row with its demand evidence — an idea whose justification is dropped at the next audit gets re-proposed or silently abandoned on no evidence either way.

## Rules

- **Read-only on the codebase.** Modify NO application/code files. The only files you write are the journal entry and `current.md` under the workspace.
- **Be specific** — never "improve content"; say exactly what to add/change.
- **Quantify everything** with real numbers from the dashboards; include trend deltas when prior audits exist.
- **Prioritize by impact** toward the stated traffic goal — compute the gap against the *organic* number, not total users (e.g. "+60 daily organic visitors needed — where do they come from?").
- If a service requires login and you can't access data, note it clearly and proceed with what's available. Never invent metrics.
- Take screenshots at each phase to document the audit trail.
- If the user provided extra queries/focus areas in $ARGUMENTS, fold them into the relevant phases.
- **Every field the report declares needs a phase that collects it.** "Quantify everything" and "never invent metrics" are only compatible if each column in §1-§11 traces to an observation above — so write the source next to the value. If a field has no collecting phase, write `n/a — not collected` rather than an estimate, and say so in the summary. Adding a column to the report template means adding its collection step too; a field that is always blank or always guessed is worse than an absent one, because the roadmap built on it reads as measured.
- **And every field a phase collects needs a section that consumes it.** The same trace, read backwards: before a phase extracts something, know which numbered section or `current.md` row it lands in. A field with no sink is a dashboard the reader never sees — it costs a login wait and a screenshot and then evaporates, and because `current.md` has no row for it, it can never acquire the trend delta this skill exists to report. If you cannot name its sink, stop collecting it.
- **Every position carries its provenance.** Search Console's average position and a SERP reading from the operator's signed-in profile are two different measurements of two different things; they never share a column, and only the first one carries a trend.
- **A claim about a set names the basis the set was picked on.** "The highest-leverage pages" is a measurement, not a label: if the set came from anything other than click data, say which basis chose it, in the report, beside the findings drawn from it.
- **Anything a later phase needs, an earlier phase has to carry.** When a phase reads prior context, the list of what it extracts is a contract with whoever consumes it downstream — a field no phase collects is a source that does not exist, however confidently a later phase names it.
- **Every field the report declares needs a phase that collects it.** "Quantify everything" and "never invent metrics" are only compatible if each column in §1-§10 traces to an observation above — so write the source next to the value. If a field has no collecting phase, write `n/a — not collected` rather than an estimate, and say so in the summary. Adding a column to the report template means adding its collection step too; a field that is always blank or always guessed is worse than an absent one, because the roadmap built on it reads as measured.
- If the user provided extra queries/focus areas in the **User Input** block above, fold them into the relevant phases.
