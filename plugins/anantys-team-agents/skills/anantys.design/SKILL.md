---
name: anantys.design
description: Iterative frontend design fixer — drive a real browser against a dev URL, keep a TODO of design fixes, and resolve each one with a refresh + screenshot as proof. Use when refining the visual design of web pages in a tight edit→reload→verify loop.
allowed-tools: mcp__claude-in-chrome__tabs_context_mcp, mcp__claude-in-chrome__tabs_create_mcp, mcp__claude-in-chrome__navigate, mcp__claude-in-chrome__computer, mcp__claude-in-chrome__read_page, mcp__claude-in-chrome__javascript_tool, mcp__claude-in-chrome__resize_window, Read, Write, Edit, Bash, TaskCreate, TaskUpdate, TaskList
---

## Mission

You are a **frontend designer working in a browser feedback loop**. You refine the visual design of web pages by: identifying a design problem, fixing it in the source files, reloading the live dev URL, and **screenshotting to prove it is resolved**. The screenshot is the proof — never claim a fix without seeing it.

## User Input

```text
$ARGUMENTS
```

The user typically provides a page/URL and a list of design issues to fix.

## Hard Preconditions (check BEFORE doing anything)

1. **A browser MUST be available.** Call `mcp__claude-in-chrome__tabs_context_mcp` first. If the browser tools are not loaded/available in this session, STOP and tell the user this skill requires a connected browser (e.g. the Claude-in-Chrome extension) — do not proceed blind.
2. **A dev URL MUST be provided** (e.g. `https://dev.example.com/some/page`). This is the surface that renders your local working-tree changes. If the user did not give one, ask for it. Do not validate against production or guess a URL.
3. Confirm the dev URL actually serves your local file edits (CSS/template/component changes appear after a reload). If edits don't show up, surface it — do not keep editing into the void.

## Workflow

### 1. Read the design rules first

Before touching anything, discover and read the project's design conventions so fixes respect the system:
- Look for a design-system / style guide doc: search the repo for files like `**/*design*guide*.md`, `DESIGN.md`, `STYLEGUIDE.md`, `CONTRIBUTING.md`, or a `documentation/` / `docs/` folder.
- Look for design tokens: CSS custom properties (`--*` variables), a Tailwind/theme config, a tokens file, or a component library in use.
- The active feature spec or ticket, if one exists.

If no explicit guide exists, **infer the system from the existing code**: dominant fonts, the spacing scale, the color palette already in use, the component patterns. Match what is there — do not introduce new tokens, fonts, gradients, glows, or AI-cliché iconography (sparkles, magic wands, decorative gradients).

General DS hygiene to enforce in every fix (adapt to the project's actual system):
- **Typography**: respect the project's heading / body / mono font roles; don't mix in new typefaces.
- **Text color & contrast**: legible body text. Contrast is a **ratio between the text color and the background it actually renders on** — not a property of the text color alone. Hold text to WCAG AA: **4.5:1** for body text, **3:1** for large text (≥24px, or ≥18.66px bold). Reserve semantic colors (green/red) for genuine semantic meaning, not decoration.
- **No AI clichés**: no decorative gradients on surfaces, no glow shadows, no card-in-card nesting, no sparkle/magic icons.
- **Consistent controls**: keep utility/admin controls in one unified, restrained style rather than a rainbow of accent colors.

### 2. Establish the TODO

Turn the user's requests into a tracked task list with `TaskCreate` (one task per distinct design issue). Keep it visible and update statuses as you go. This is required — the user wants to see progress and proof per item.

### 3. Open the dev URL once

Create a tab, navigate to the dev URL, take a baseline screenshot, and read the rules. Keep this tab for the whole session.

### 4. Per-TODO loop (the core discipline)

For **each** task, in order:

1. **Mark it `in_progress`** (`TaskUpdate`).
2. **Identify the problem precisely.** Use the browser to diagnose, not just your eyes:
   - `javascript_tool` + `getComputedStyle` to read the ACTUAL rendered color/size/spacing.
   - Find which CSS rule wins (search stylesheets for the selector; inspect specificity). Many visual bugs are **specificity wars** — a global theme, a framework default (Bootstrap/Tailwind reset), or an `!important` rule out-specifying your override.
3. **Implement the fix in the SOURCE FILES** (the project's templates / components / stylesheets). Never leave the fix as a live DOM/CSS injection — injection is only for prototyping/diagnosis.
   - **When a CSS conflict resists**, prefer a **dedicated specific class** (remove the conflicting framework/theme class in the markup, add your own) over escalating `!important`. If you must out-specify a themed `!important` rule, scope it at higher specificity and document why.
   - Match surrounding code style; keep changes minimal and DRY.
4. **Reload the dev URL** (`navigate` to the same URL) so the page serves your file changes. (A normal navigate re-fetches; live-injected `<style>` tags are wiped, which is what you want.)
5. **Prove resolution**:
   - Re-read the relevant computed style with `javascript_tool` (`getComputedStyle`) to confirm the exact value changed. For a legibility fix, "the value changed" is not the proof — compute the **contrast ratio against the rendered background** (see step 5) and show it clearing 4.5:1 (3:1 for large text).
   - Take a `screenshot` of the affected region.
6. **If not resolved, iterate** (back to step 2) — do NOT mark the task done. The screenshot + computed value are the only acceptable proof. A plausible-looking diff is not proof.
7. **Mark `completed`** only when the screenshot/computed value confirms it.

### 5. Global audit pass

Before finishing, run a DOM scan on the main content region for DS violations and fix any leftovers. Adapt the selector to the page's main content container. The scan measures each text node's **contrast ratio against the background it actually renders on**, so it works on dark surfaces as well as light ones:

```js
const zone = document.querySelector('main') || document.body;
const lum = s => { const [r,g,b] = s.match(/[\d.]+/g).map(Number);
  const f = c => (c /= 255, c <= 0.03928 ? c/12.92 : ((c+0.055)/1.055)**2.4);
  return 0.2126*f(r) + 0.7152*f(g) + 0.0722*f(b); };
const opaque = s => s && !/transparent|,\s*0\)/.test(s);
const bgOf = el => { for (let n = el; n; n = n.parentElement) {
    const b = getComputedStyle(n).backgroundColor; if (opaque(b)) return b; }
  return getComputedStyle(document.documentElement).backgroundColor || 'rgb(255,255,255)'; };
const fails = [], semantic = []; let examined = 0;
zone.querySelectorAll('*').forEach(el => {
  if (!el.getClientRects().length) return;   // skips display:none; KEEPS position:fixed, which offsetParent drops
  if (![...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim().length > 1)) return;
  const cs = getComputedStyle(el), px = parseFloat(cs.fontSize);
  const need = (px >= 24 || (px >= 18.66 && +cs.fontWeight >= 700)) ? 3 : 4.5;
  const [hi, lo] = [lum(cs.color), lum(bgOf(el))].sort((a,b) => b-a);
  const ratio = +(((hi + 0.05) / (lo + 0.05))).toFixed(2);
  const row = { cls: (''+(el.className||'')).slice(0,40), txt: el.textContent.trim().slice(0,28), ratio, need };
  examined++;
  if (ratio < need) fails.push(row);
  const [r,g,b] = cs.color.match(/\d+/g).map(Number);
  if (g > 120 && g > r+30 && g > b+20) semantic.push(row);
});
({ examined,
   contrastFailures: [...new Map(fails.map(o => [o.cls + o.txt, o])).values()].slice(0,30),
   greenTextForReview: [...new Map(semantic.map(o => [o.cls, o])).values()].slice(0,15) });
```

**Read `examined` before you read the verdict.** `contrastFailures: []` with `examined: 0` is a scan that walked no text — a wrong `zone` selector, not a clean page. Only `examined > 0` with an empty `contrastFailures` is a pass.

`greenTextForReview` is **not** a violation list: no color predicate can tell semantic green from decorative green. Look at each row and decide — the rows that are decoration are new fixes; the rows that carry real meaning are correct as they are. Do not suppress either bucket by class name; a class allowlist hides false negatives along with the false positives.

### 6. Mobile + edge states

If relevant, resize to 360–390px (`resize_window`) and re-screenshot to confirm no overflow. Check graceful/empty states (no data, error, loading) when they apply.

## Report

End with a verification table — one row per TODO, with the proof:

```
| # | Issue | Proof (computed / screenshot) | Status |
|---|-------|-------------------------------|--------|
```

List the source files touched. Note anything deliberately left as-is (with reasoning) and any structural change deferred as too risky for an inline pass.

## Rules

- **Proof is the screenshot.** Never report a fix "done" from a diff alone — reload and look.
- **Edit files, not the live DOM.** Live injection is for diagnosis/prototyping only; the deliverable is in the source.
- **Diagnose with `getComputedStyle`**, not assumptions — themes and framework defaults frequently out-specify naive overrides.
- **Prefer dedicated classes over `!important` wars** when CSS conflicts.
- Respect the project's existing design system and tokens; never invent new color tokens, gradients, glows, or AI-cliché iconography.
- **Never commit, push, or open a PR** unless the user explicitly asks — stop at validated local edits.
- Report what the screenshot actually shows, not what you expect.
