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
4. **A known tree state — because a `blocked` task must be reverted.** Step 4.8 obliges you to undo
   a task's edits, and you cannot undo to a state you never recorded. Before the first edit, run
   `git status --porcelain` and `git branch --show-current`, and **report both**:
   - **Modified tracked files** (` M`, `M `, `A `) — those changes are the user's. STOP and ask them
     to commit or stash. Do not stash for them: once your overrides sit in the same stylesheet,
     reverting a file reverts their work too, and you never saw what it was.
   - **Untracked files** (`??`) — not the same risk, and not a reason to stop: `git checkout --`
     cannot touch a path git does not know. **List them by path** and continue; they are the entries
     that must still be there when you finish.
   - **Unexpected branch** — the checkout is ambient state you did not set; a prior session may have
     left it on a review or feature branch. Name it and confirm before editing.

   Then record, per task, what you **edited** and what you **created** — two lists, because the undo
   is two commands. `git checkout -- <those files>` restores tracked files only; a new stylesheet or
   partial is untracked, so it fails on that path (`did not match any file(s) known to git`) and the
   file survives the revert. Creations are undone with `rm`, by path. **Never `git clean`** — it
   cannot tell your `??` entries from the ones you listed above.

## Workflow

### 1. Read the design rules first

Before touching anything, discover and read the project's design conventions so fixes respect the system:
- Look for a design-system / style guide doc: search the repo for files like `**/*design*guide*.md`, `DESIGN.md`, `STYLEGUIDE.md`, `CONTRIBUTING.md`, or a `documentation/` / `docs/` folder.
- Look for design tokens: CSS custom properties (`--*` variables), a Tailwind/theme config, a tokens file, or a component library in use.
- The active feature spec or ticket, if one exists.

If no explicit guide exists, **infer the system from the existing code**: dominant fonts, the spacing scale, the color palette already in use, the component patterns. Match what is there — do not introduce new tokens, fonts, gradients, glows, or AI-cliché iconography (sparkles, magic wands, decorative gradients).

General DS hygiene to enforce in every fix (adapt to the project's actual system):
- **Typography**: respect the project's heading / body / mono font roles; don't mix in new typefaces.
- **Text color & contrast**: legible body text, sufficient contrast; no illegible low-contrast greys. Reserve semantic colors (green/red) for genuine semantic meaning, not decoration.
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
   - Re-read the relevant computed style with `javascript_tool` (`getComputedStyle`) to confirm the exact value changed.
   - Take a `screenshot` of the affected region.
6. **If not resolved, iterate** (back to step 2) — do NOT mark the task done. The screenshot + computed value are the only acceptable proof. A plausible-looking diff is not proof.
7. **Mark `completed`** only when the screenshot/computed value confirms it.
8. **Or mark it `blocked`** — the loop's third exit, and a real one. A task that can only be
   `completed` or `in_progress` has no way out except calling an unproven fix done, which is exactly
   the rule this skill is built on. Stop and mark `blocked` when **either**:
   - **Three attempts rejected by the screenshot / computed value** with nothing new learned — you
     are no longer diagnosing, and a fourth CSS guess is not a diagnosis.
   - **The fix is structural** — the markup, the component boundary or the design token itself is
     wrong, and no inline override reaches it. That is a deliberate deferral, not a stuck loop.

   Revert that task's edits before moving to the next one — `git checkout -- <the files that task
   edited>` plus `rm <the files that task created>`, scoped to that task alone, never a whole-tree
   reset that would also discard the tasks you completed. A `blocked` task that leaves three dead
   overrides in the stylesheet hands the next person a worse page than it found — and a file no
   `checkout` removes is the same debt, invisible in the diff.

### 5. Scope the proof to the edit, before marking anything done

A screenshot is a fact about **one rendered page**. A change to a stylesheet, a design token, or a
shared component is a fact about **every page that renders it**. CSS has no local scope and neither
does a component, so those two scopes coincide only when you have checked that they do — and this
skill points you at the shared ones by design: step 4.3 prefers *removing the framework class from
the markup*, and the DS rules send you to the project's tokens.

You already hold both halves. The per-task file list from the preconditions says what you changed;
one `grep` per touched file says who else consumes it. Run it before you mark the task `completed`:

```bash
# a template / component — who renders or imports it?
grep -rn 'ComponentName\|path/to/component' --include='*.tsx' --include='*.jsx' --include='*.vue' \
  --include='*.html' --include='*.erb' --include='*.py' .
# a class you removed from markup, or a token whose value you retuned
grep -rn 'the-class-you-removed\|--the-token-you-changed' .
```

Classify each touched file and **say which it was**:

- **Page-local** — the only consumer is the route behind your dev URL. The screenshot is the whole
  proof. Done.
- **Shared** — there are other consumers, and your screenshot proves the fix *on one of them*. The
  pages most at risk are exactly the ones you never loaded: retuning `--space-md` fixes the page you
  are watching and moves every page you are not.

A shared edit ends one of two ways, never silently as the first:

1. **Ask for the other surfaces.** Name the other consumers and ask the operator for a dev URL for
   each one you should check — a second surface is a URL you are given, not a tab you go open.
   Re-verify there and the proof is complete.
2. **Report the reach.** With no second URL available the row can still be `completed` — the issue
   *is* fixed — but the Proof column must name what went unverified: "verified on `/checkout`;
   `--space-md` is also read by 11 other templates, unchecked."

An unqualified `completed` on a shared edit is a claim about pages you never opened. It is the same
error as calling a fix done from a diff, one level up: the diff you did not read is the page you did
not load.

### 6. Global audit pass

Before finishing, run a DOM scan on the main content region for DS violations and fix any leftovers. Adapt the selector to the page's main content container, and adapt the "allowed" exceptions to the project's legitimate semantic classes. Example scan (flags low-contrast grey text and stray green text):

```js
const zone = document.querySelector('main') || document.body;
const isLightGrey=(r,g,b)=>(r>150&&g>150&&b>150)&&Math.abs(r-g)<40&&Math.abs(g-b)<40&&r<210;
const isGreen=(r,g,b)=>g>120&&g>r+30&&g>b+20;
const ALLOWED=/perf|value|variation|semantic|badge/; // adapt to the project's legit semantic classes
const out=[];
zone.querySelectorAll('*').forEach(el=>{
  if(!el.offsetParent) return;
  if(![...el.childNodes].some(n=>n.nodeType===3&&n.textContent.trim().length>1)) return;
  const m=getComputedStyle(el).color.match(/\d+/g); if(!m) return; const [r,g,b]=m.map(Number);
  const cls=''+(el.className||'');
  if(ALLOWED.test(cls)) return;
  if(isLightGrey(r,g,b)) out.push({t:'grey',cls:cls.slice(0,40),txt:el.textContent.trim().slice(0,28)});
  else if(isGreen(r,g,b)) out.push({t:'green',cls:cls.slice(0,40),txt:el.textContent.trim().slice(0,28)});
});
[...new Map(out.map(o=>[o.t+o.cls,o])).values()].slice(0,30);
```

An empty result (`[]`) is the goal. Anything returned is a new fix.

### 7. Mobile + edge states

If relevant, resize to 360–390px (`resize_window`) and re-screenshot to confirm no overflow. Check graceful/empty states (no data, error, loading) when they apply.

## Report

End with a verification table — one row per TODO, with the proof:

```
| # | Issue | Proof (computed / screenshot) | Status |
|---|-------|-------------------------------|--------|
```

`Status` is `completed` or `blocked` — never `in_progress`. For a `blocked` row, the Proof column
carries what the last attempt *actually rendered* and why it was rejected, plus what the fix needs
(a markup change, a token, a decision). Report it as loudly as a completed one: an unfixed issue the
reader knows about is worth more than a green table that quietly dropped it.

List the source files touched. Note anything deliberately left as-is (with reasoning) and any structural change deferred as too risky for an inline pass.

## Rules

- **Proof is the screenshot.** Never report a fix "done" from a diff alone — reload and look.
- **Edit files, not the live DOM.** Live injection is for diagnosis/prototyping only; the deliverable is in the source.
- **Diagnose with `getComputedStyle`**, not assumptions — themes and framework defaults frequently out-specify naive overrides.
- **Prefer dedicated classes over `!important` wars** when CSS conflicts.
- **`blocked` is a valid ending for a task** — three rejected attempts, or a structural fix an
  inline pass cannot reach. Revert that task's edits and say what it needs. Never buy a `completed`
  by lowering what counts as proof.
- **Record the tree before you edit it, and say where you are.** Clean tree, named branch, both
  reported, and a per-task list split into edits and creations — the undo is `git checkout --` for
  one and `rm` for the other. "Dirty" means modified *tracked* files; untracked ones you list and
  leave alone. Never `git clean`: it cannot spare the user's.
- **The screenshot's scope is one page; the edit's scope is every consumer.** Grep each touched file
  for its other consumers before `completed`. Page-local, and the screenshot is the whole proof;
  shared, and you either get a dev URL per surface or name the unverified ones in the Proof column.
- Respect the project's existing design system and tokens; never invent new color tokens, gradients, glows, or AI-cliché iconography.
- **Never commit, push, or open a PR** unless the user explicitly asks — stop at validated local edits.
- Report what the screenshot actually shows, not what you expect.
