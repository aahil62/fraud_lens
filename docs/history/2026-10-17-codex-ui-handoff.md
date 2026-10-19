# FraudLens: handoff to Claude Code

## Open this checkout

`/Users/aahil/Documents/Codex/2026-10-17/have-to-improve-both-of-these/outputs/fraudlens`

This is the actual local Git checkout containing the implementation. Branch: `codex/fraudlens-live-operations`. Last commit: `fea8f28c727c6a842625ddbc9d04735d79467f01` (completed operational implementation). The subsequent UI overhaul is **uncommitted**, including new untracked files. Preserve it. Nothing has been pushed or deployed. RepoPilot has not been changed.

The user explicitly wants Claude Code to continue from this point. Stop further Codex implementation; this document is the transfer of context.

## User intent

The initial goal was resume-quality, socially useful projects. The conversation then focused on FraudLens: UPI, net banking, card and ATM detection; automatic protective bank requests with analyst review/reversal; consistent live counts, cases, actions and reports. The user deferred external-bank API access. The approved implementation uses a separate enforcing local bank simulator.

The user rejected the initial UI as “absolute shit” and requested an overhaul of **the landing page, every console page and everything**, explicitly invoking Scrollcraft, design skills and Three.js animation. They want a substantial visual improvement, not another small recolor. Build and verify autonomously; do not restart a design interview or request another approval checkpoint for this authorized work.

## Read the existing artifacts instead of rebuilding context

- `docs/UI-REDESIGN.md`: design direction, ownership boundaries and verification plan.
- `DESIGN.md` and `PRODUCT.md`: updated current visual system and product scope.
- `scrollcraft/builds/fraudlens/BRIEF.md`: authored landing brief, journey, optical mechanics, grammar and pending visual evidence.
- `README.md`, `docs/ARCHITECTURE.md`, `docs/OPERATIONS_API.md`: running architecture, API and supported workflow.
- `docs/VERIFICATION.md`, `docs/OPERATIONS_EVALUATION.md`, `docs/GUIDANCE.md`: operational evidence and limits. These describe the previous completed implementation; the new UI needs its own final verification addendum.

## Current redesign

The old green-black UI has been replaced with a light mineral workbench, white reading surfaces, charcoal navigation, cobalt selection/actions, semantic red/amber/green outcomes, locally bundled Mona Sans and Phosphor icons.

Important file groups:

- Shared shell/tokens: `frontend/app/globals.css`, `frontend/components/ConsoleShell.tsx`, `frontend/app/layout.tsx`.
- Landing: `frontend/app/page.tsx`, `frontend/app/landing.css`, `frontend/components/landing/*`.
- Console pages: `frontend/components/operations/OperationsViews.tsx`, `ScenarioControls.tsx`, `frontend/app/workspace-views.css`.
- Case, graph and shared controls: `CaseWorkspace.tsx`, `EvidenceGraph.tsx`, `Primitives.tsx` in the same operations directory.
- Auth: `frontend/components/AuthFrame.tsx`, login and signup pages.
- New tests: shell mobile focus, graph selection/layout, report/audit filters, bounded activity chart, reduced-motion/static lens.
- Dependencies/config: package + lock, `next.config.ts`, `eslint.config.mjs`.

Landing has an actual procedural Three.js optical assembly with layered metal/glass rings, instanced ticks, four payment paths, traveling packets and a review branch. It reacts to pointer/scroll and selected channels. It pauses when offscreen/hidden and disposes resources. Static SVG remains for reduced motion, unavailable WebGL, context loss or the new “Pause 3D motion” control. The user can choose a channel, inspect sample evidence, view simulated protection, record a sample verdict and replay. These are explicitly labelled illustrative sample data, separate from the operational ledger.

The dashboard now contains real channel counts, a bounded recent-transaction activity chart, investigation priority and audit activity. Other views have status filtering, a compact scenario desk with expandable failure controls, a bank status board, searchable reports/audit and expandable guidance. The shell has working recent-case search, account menu and responsive navigation drawer.

## Checks already performed

Last recorded frontend run: **30 tests passing**, **lint clean**. Logs are in ignored `work/ui-tests.log` and `work/ui-lint.log`. `work/ui-types.log` was empty on the last TypeScript check. Final production build for the redesign has **not** been run. Rerun final checks after finishing QA; do not reuse the old build success as evidence for this redesign.

The previous committed backend implementation passed 330 tests with one optional dataset skip and separate-process HTTP proof. No backend implementation was changed in this UI turn.

Rendered desktop checks used a 1280×720 hidden browser tab. Inspected landing, dashboard, queue, case, transactions, bank, reports, audit, guidance and graph. Verified through actual rendered controls:

- Paused the synthetic stream and generated a UPI scenario.
- Filtered resolved cases and used header search to find the new case.
- Confirmed fictional case `CASE-736BE807B6E0` with a test rationale; the UI displayed resolved/fraud and retained restriction confirmation.
- Filtered the report library and clicked its PDF export without a displayed error.
- Searched the audit trail for the attributed test decision.
- Expanded guidance coverage and selected a graph account node, seeing its reference and link count.
- Selected Cards in the landing example and progressed evidence → protection → sample verdict.
- Verified actual WebGL readiness/canvas presence; paused 3D and then observed canvas count zero and the visible SVG poster.

Screenshots under `docs/screenshots/redesign/` are **intermediate QA evidence**, not a fully finalized set. `mobile-landing.png` was accidentally captured immediately after an iframe reload and may be blank: replace it. Other screenshots can precede the last minor contrast/layout changes.

## Review fixes already applied

- Graph beneficiary/instrument reference rows shared a column but computed separate peer groups, causing overlap. They now share one reference group; viewBox height scales with peer count.
- Interactive SVG nodes now use group semantics instead of being inside an image role; keyboard inspection and visible focus were added.
- Mobile drawer now transfers/contains focus, makes the main content inert, supports Escape and restores trigger focus. A regression test passes. Actual mobile browser verification was interrupted before completing this final check.
- Evidence/actor/date text had inadequate contrast. Root colors were darkened. A DOM/computed-color audit then found several landing annotations plus breadcrumb/environment labels; these were also darkened. Rerun the audit to verify the final state. One reported sidebar-count contrast failure was an audit false positive from not alpha-compositing its translucent badge over charcoal.
- Canvas layering initially intercepted the new pause control. `.fl-hero-baseline { z-index: 3; }` fixes it, and the control subsequently worked in the browser.
- Initial connection loading no longer flashes the reconnect-warning banner before any snapshot exists.
- Compact-height/mobile hero overrides were added to fit headline, optic and CTA within a 360×640 viewport, but their final rendered result still needs inspection.
- Landing protected-scope text was corrected to account debit restriction or linked test instrument/card, matching the model rather than implying UPI-only account enforcement.

## Remaining work: finish, verify, package

1. Finish mobile checks. There is a **temporary, untracked** `frontend/public/qa-responsive.html` wrapper serving a 360×640 iframe. It is for QA only. Remove it before committing/packaging. Previously tested 390px rendering looked coherent; final compact-height override needs inspection. A direct user browser preview was around 319px wide, another useful compact check.
2. Verify the final mobile drawer by actual pointer/keyboard, including focus and Escape. Check mobile landing intermediate stages, auth pages and representative dense ledgers. Tables should scroll internally, never the whole viewport.
3. Inspect login/signup layouts. Their submission logic and redirect sanitization are preserved; both forms use POST semantics. Do not create a new real account or change credentials just for visual QA.
4. Recheck final contrast, responsive overflow, focus, browser errors and motion-off behavior. OS-level reduced-motion is covered by a unit test and code review; it has not been explicitly emulated in the browser. Static fallback was tested through the real pause control. Do not claim a full WCAG or device-matrix audit.
5. Run final frontend tests, lint, TypeScript and production build. **Stop the owned Next dev process before building into its `.next` directory.** Do not kill unrelated port listeners. Consider running the built production server for the last browser pass, which also removes dev-tool overlays.
6. Update `docs/VERIFICATION.md` (or a linked redesign verification addendum) with actual results and limits. Update the Scrollcraft brief's pending visual section and append its fingerprint registry row only after final review. Keep the vendor engine unchanged; its live copy is intentionally ignored by ESLint because it is verbatim upstream, not because first-party lint failures are suppressed.
7. Commit the verified redesign locally if appropriate. Regenerate `../FraudLens-source.zip` and `../FraudLens-implementation.patch`, plus the parent `../START-HERE.md`. **Those existing archives/notes currently represent the old committed UI**, not this uncommitted redesign. Exclude runtime state, secrets, dependencies and temporary QA files.
8. Show the user the actual result with final screenshots and a local preview. No push, deployment or external publication was requested.

## Runtime

The existing launcher was started from this checkout with `.venv/bin/python scripts/dev.py`. Bank 8002, API 8001, Next 3000, all loopback. It appeared active at handoff; check before starting another instance. `work/dev.log` contains combined service output. The stream was paused during UI QA and remains paused intentionally; resume via the Transactions UI when ready to demonstrate live activity.

Useful commands, from this checkout:

```bash
npm --prefix frontend run test
npm --prefix frontend run lint
cd frontend && npx tsc --noEmit
# Stop owned Next dev before this command:
npm --prefix frontend run build
# If the entire launcher has stopped:
.venv/bin/python scripts/dev.py
```

Find local demo access instructions in the existing README; no credentials or keys are reproduced here. Five previously documented high development-only dependency advisory paths remain; do not apply npm's incompatible force-downgrade. Production audit previously reported zero, but recheck if making dependency changes.

## Suggested skills

Use relevant skills rather than loading every design skill:

- Scrollcraft: `/Users/aahil/.codex/plugins/cache/nateherk/nateherk-design/0.3.1/skills/scroll-craft/SKILL.md`
- Impeccable: `/Users/aahil/.agents/skills/impeccable/SKILL.md`
- Anti-slop: `/Users/aahil/.agents/skills/anti-slop/SKILL.md`
- Three.js animation and fundamentals: `/Users/aahil/.agents/skills/threejs-animation/SKILL.md`, `/Users/aahil/.agents/skills/threejs-fundamentals/SKILL.md`
- Verification before completion and systematic debugging, if needed.

The prior agents already read these for implementation. Use the current documents and actual pixels as evidence; do not restart the project or discard the new design simply to follow a new planning ceremony.
