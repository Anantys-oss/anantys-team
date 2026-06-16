---
name: web-ops-reviewer
description: Browser-driven web/SEO ops reviewer — pilot a real browser across live pages and SaaS dashboards (Search Console, Analytics, SERP) to collect data and produce an actionable, quantified optimization report with trend deltas. Use for recurring acquisition/SEO audits.
allowed-tools: mcp__claude-in-chrome__tabs_context_mcp, mcp__claude-in-chrome__tabs_create_mcp, mcp__claude-in-chrome__navigate, mcp__claude-in-chrome__computer, mcp__claude-in-chrome__read_page, mcp__claude-in-chrome__find, mcp__claude-in-chrome__get_page_text, mcp__claude-in-chrome__javascript_tool, mcp__claude-in-chrome__form_input, mcp__claude-in-chrome__update_plan, Read, Write, Glob, Bash(mkdir:*), Bash(git:*), Bash(ls:*)
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
- **Traffic goal** (e.g. "from ~40 to 100 daily organic visitors").
- **Workspace path** for outputs (default `./seo/` — see "Outputs").

If a browser is not available (`tabs_context_mcp` returns nothing usable), STOP and tell the user this skill needs a connected browser. If a Google service shows a login screen, inform the user and wait — never fabricate dashboard numbers.

## Phase 0: Historical Context

Load prior context so every metric can be reported with a trend delta:

1. **Read `<workspace>/current.md`** if it exists — the living status file with current KPIs, targets, and pending actions from the last audit.
2. **List `<workspace>/journal/`** (via `Glob`/`ls`) and **read the last 3 entries** (most recent first). Extract date, KPIs (clicks, impressions, CTR, position, daily visitors), top queries + positions, recommendations made, actions completed.
3. **Build a comparison baseline** so you can compute deltas (e.g. "+12% clicks vs last audit", "position 7.2 → 5.0").

If no prior data exists, note this is the first audit and skip comparisons. Whenever you later report a metric, **include the delta vs the previous audit** when available.

## Pre-flight

1. Call `tabs_context_mcp`; create a fresh tab with `tabs_create_mcp`.
2. Present a plan via `update_plan`: the domains you'll visit, and the approach (hub audit → top pages deep-dive → Search Console → Analytics → SERP → report).
3. Wait for user approval before proceeding.

## Phase 1: Hub / Landing Page Audit

Navigate to the hub/landing URL the user gave. Screenshot it, then extract (via `get_page_text` + JS) and evaluate:

- Title (`document.title`) — 50-60 chars ideal — and meta description — 150-160 chars ideal.
- Heading hierarchy (single H1, logical H2/H3).
- Internal & external link counts and destinations.
- Structured data (`<script type="application/ld+json">`), canonical URL, Open Graph / Twitter Card tags, mobile viewport meta.
- Content depth and keyword coverage.

Record all findings.

## Phase 1b: Top Page Deep-Dive

A hub/index is rarely the page that earns clicks — the individual content pages it links to are. Cross-reference the hub's links with Search Console top-pages data (Phase 2 or prior audit) to pick the **top 5-10 pages by clicks/impressions**.

For each, navigate + screenshot + extract via JS: title (+length), meta description (+length), H1/H2/H3, structured data, canonical, word count (`document.body.innerText.split(/\s+/).length`), internal links, FAQ presence, OG image. Then evaluate: does the title match the target query and beat competitors? Is the meta description click-worthy (numbers/freshness)? Content depth, rich-snippet readiness, internal linking. Record per-page findings in a table — these pages have the highest CTR leverage.

## Phase 2: Search Console (28 days)

Navigate to the property's Search Console performance URL (28-day window, broken down by page). If not logged in, tell the user and wait. Screenshot, then extract:

- Top cards: total clicks, impressions, CTR, average position.
- Top ~20 queries (Queries tab): clicks, impressions, CTR, position.
- Top ~10 pages (Pages tab): same metrics.
- Flag **high-impression / low-CTR** queries (title-meta quick wins) and **good-position (<10) / low-click** queries.

## Phase 3: Analytics

Navigate to the Analytics (e.g. GA4) report URL. If not logged in, tell the user and wait. Screenshot, then extract: active users (daily/weekly/monthly trend), traffic-source breakdown (organic vs direct vs referral vs social), top pages by views, engagement (session duration, bounce/engagement rate), geographic split if shown.

## Phase 4: SERP Analysis

For each **target query** the user provided, navigate to a clean search URL (`https://www.google.com/search?q=<encoded query>&hl=<lang>`), screenshot, and use `get_page_text`/`find` to locate the site's domain in results. Record: the site's position (or absence), competitors ranking above/below, featured snippets / People-Also-Ask / rich results, and ad presence (competitors bidding). Check the first 2 result pages max — do not scroll endlessly.

## Phase 5: Analysis & Report

Compile findings into a markdown report at **`<workspace>/journal/<YYYY-MM-DD>-analysis.md`** (`mkdir -p` the dir). Then give a brief in-conversation summary linking the file. Suggested structure (adapt to the business):

```
# SEO Audit Report — <domain>
Date: <today>
Objective: <current> -> <target> daily visitors

## 1. Current Performance Summary   (Daily visitors, GSC clicks/impressions, CTR, avg position — with deltas)
## 2. Landing Page Health            (title/meta/H1/structure/links/structured-data, OK or IMPROVE)
## 3. Top Performing Queries         (table: query, clicks, impressions, CTR, position)
## 4. High-Potential Queries         (high impressions, low CTR — quick wins)
## 5. Uncovered Queries              (relevant but not ranking — from SERP analysis)
## 6. Pages to Improve               (rank but low CTR — title/meta/content fixes)
## 7. SERP Positioning vs Competitors (per target query: who ranks, where you sit)
## 8. Optimization Roadmap           (Quick wins / Medium-term / Long-term, checkboxes)
## 9. New Landing Page Ideas         (slug, target query, est. monthly searches, priority)
## 10. Technical SEO Checklist       (sitemap, robots, Core Web Vitals, mobile, canonical, hreflang, internal links)
```

## Phase 6: Update Status File

Overwrite **`<workspace>/current.md`** — the living snapshot that persists between audits:

```
# SEO — Current Status (<domain>)
> Last audit: <YYYY-MM-DD>   Journal: <path to latest entry>

## KPI Dashboard         (Metric | Current | Previous | Delta | Target)
## SERP Positions        (Query | Position | Trend | Target)
## Top Pages Performance (Page | Clicks 28d | Impressions | CTR | Position)
## Completed Actions     (carried forward from previous current.md, marked [x])
## Next Actions          (priority-ordered; flag how many audits each has been pending)
## New Landing Pages     (Slug | Target Query | Priority | Status)
## Key Findings This Session
## Audit History         (Date | Clicks | Impressions | CTR | Pos | VU/day | Journal — accumulates all past rows)
```

Rules for `current.md`: always overwrite the whole file (it is a snapshot; the journal is the append log). Carry forward completed actions; if a prior "Next Action" was done, move it to Completed, else keep it and flag its age. Accumulate the Audit History table from the previous `current.md`.

## Rules

- **Read-only on the codebase.** Modify NO application/code files. The only files you write are the journal entry and `current.md` under the workspace.
- **Be specific** — never "improve content"; say exactly what to add/change.
- **Quantify everything** with real numbers from the dashboards; include trend deltas when prior audits exist.
- **Prioritize by impact** toward the stated traffic goal — compute the gap (e.g. "+60 daily visitors needed — where do they come from?").
- If a service requires login and you can't access data, note it clearly and proceed with what's available. Never invent metrics.
- Take screenshots at each phase to document the audit trail.
- If the user provided extra queries/focus areas in $ARGUMENTS, fold them into the relevant phases.
