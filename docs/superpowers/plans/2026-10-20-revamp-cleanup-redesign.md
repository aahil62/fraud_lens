# FraudLens: code revamp, repository cleanup and visual redesign

**Status:** Ready to implement in the stage order below. Part 3's direction is set by the user (2026-10-19); the palette is chosen from mockups at the start of Part 3, before any redesign code is written.

**Ground rules (all parts):**
- No new features. Behaviour, routes, API contracts, roles, copy and numbers stay the same unless a step says otherwise.
- Work on `feature/fraudlens-v3`; one commit per numbered step; conventional messages with the Co-Authored-By line.
- After every step: `.venv/bin/python -m unittest discover -s tests`, `npm --prefix frontend run test`, `npm --prefix frontend run lint`, `(cd frontend && npx tsc --noEmit)`. All green before committing.
- Pushing to `main` redeploys the live site (Render): ask the user before every push.
- **Order (agreed with the user, 2026-10-19):**
  1. **Stage A — dead-code removal:** Part 2 steps 1–2 only (legacy pipeline, dead frontend files, redirect-only pages, stray tool/agent files). No refactoring or reorganising. Removing first means the redesign never restyles code that is about to be deleted.
  2. **Stage B — visual redesign:** Part 3. Large components touched by the redesign (`OperationsViews.tsx`, `ConsoleShell.tsx`, `CaseWorkspace.tsx`, `LandingExperience.tsx`) are split into readable pieces as they are restyled (Part 1 step 6 happens here).
  3. **Stage C — whole-codebase review and rewrite:** Part 1 (all remaining steps), after the redesign so the new UI code is reviewed too.
  4. **Stage D — final stage:** Part 2 steps 3–5 (docs folder, deploy leftovers, final tidy), README structure, new screenshots, `docs/VERIFICATION.md` and test counts, every check, then push to `main` with the user's approval.

---

## Part 1: Make the weak code readable

**Problem (measured 2026-10-19):** much of the code Codex wrote packs logic into very long lines and large single classes. Lines over 120 characters:

| File | Lines | >120 chars |
| --- | ---: | ---: |
| `fraudlens/operations/service.py` | 736 | 75 |
| `fraudlens/operations/guidance.py` | 159 | 49 |
| `frontend/components/operations/OperationsViews.tsx` | 487 | 48 |
| `frontend/components/landing/LandingExperience.tsx` | 166 | 38 |
| `frontend/components/operations/CaseWorkspace.tsx` | 482 | 23 |
| `frontend/components/ConsoleShell.tsx` | 105 | 21 |
| `fraudlens/operations/detector.py` | 131 | 16 |
| `fraudlens/bank_simulator/app.py` | 310 | 15 |
| `frontend/components/operations/TeamView.tsx` | 70 | 15 |
| `frontend/app/attack/page.tsx` | 124 | 13 |
| `fraudlens/operations/attacks.py`, `agent.py` | 126, 121 | 11 each |

**Goal:** a reviewer can open any core file and follow it. Pure refactors: no behaviour change, tests unchanged except imports.

**Scope (user, 2026-10-19):** the user does not trust the Codex-written code, so review *all* code — Codex's and Claude's — against how experienced engineers write it, not only the long-line files above. Start with a whole-repo review (`code-review` at high effort, `improve-codebase-architecture`, `simplify`, `vercel-react-best-practices` for the frontend, `vibesec-skill` for the auth/public routes) and add its findings as numbered steps below before refactoring. Review checklist for every module: clear names, one responsibility, no hidden side effects, early returns over nesting, no duplicated logic, comments only where the *why* is not obvious, consistent error handling, types on public functions, and tests that read as specifications.

1. **Formatting baseline.** Add `ruff` (dev only, pinned) with `line-length = 110` and a `ruff format` pass on `fraudlens/` and `scripts/` and `tests/`. Add `prettier` (pinned) for `frontend/` and run it. Commit formatting alone so later diffs stay readable. Verify: all checks green; `ruff check` clean.
2. **Split `OperationsService` (`service.py`).** Keep the public methods on the class (routes and tests call them), but move bodies into focused modules under `fraudlens/operations/`:
   - `ingest.py` (transaction ingest + case creation),
   - `decisions.py` (decide, approvals, protection targets),
   - `delivery.py` (job worker, bank action delivery, reconciliation),
   - `complaints.py` (complaint intake + trace preparation),
   - `snapshot.py` (snapshot/listing read models).
   Name the dense one-line expressions (e.g. agent counters, team snapshot) as small helpers with docstrings. Target: no module over ~250 lines.
3. **`guidance.py` → data file.** Move the reference and requirement records into `fraudlens/operations/guidance_data.py` (or JSON) with one field per line; `guidance_response()` just assembles them.
4. **Detector and agent.** One function per rule in `detector.py` (`_mule_pass_through`, `_card_testing`, …) called from `detect`; in `agent.py` split `build_brief` into `_typology`, `_recommendation`, `_narrative`. Same outputs (existing tests are the safety net).
5. **Bank simulator and attacks.** Break long expressions in `bank_simulator/app.py` and `attacks.py` into named steps; no API change.
6. **Frontend components.** Split by responsibility, keeping exports used by tests:
   - `OperationsViews.tsx` → `DashboardView.tsx`, `LedgerView.tsx`, `BankView.tsx`, `AuditView.tsx`, `ReportsView.tsx`, `GuidanceView.tsx` (+ an index re-export).
   - `CaseWorkspace.tsx` → `CaseHeader.tsx` (owner row, meta), `DecisionPanel.tsx`, `CaseWorkspace.tsx` (layout).
   - `ConsoleShell.tsx` → `Sidebar.tsx`, `Topbar.tsx`, `SearchDialog.tsx`.
   - `LandingExperience.tsx` → one component per section.
   Replace one-line JSX chains with readable multi-line JSX.
7. **Types and constants.** Remove duplicated role/action tables where possible: the frontend `ACTION_MIN_ROLE` mirrors `roles.py`; add a backend test that compares them (read the TS file) so they cannot drift.

Done when: no Python or TSX file in `fraudlens/operations`, `fraudlens/api`, `fraudlens/bank_simulator`, `scripts`, `frontend/components`, `frontend/app` has a line over 110 characters (except URLs/strings), no module over ~300 lines except tests, and all checks pass with the same test counts.

### Stage C review findings (20 October 2026)

Whole-repo review of `fraudlens/`, `scripts/` and `frontend/{app,components,lib,proxy.ts}` with `code-review` (high), `improve-codebase-architecture`, `simplify`, `vercel-react-best-practices` and `vibesec-skill`. Every file was read in full. "Fix" means it is done in the step named; "Keep" means recorded only, with the reason.

**Correctness and security (fixed with a test each, in step C2):**
- R1. Open redirect on sign-in: `/login?next=/%09/evil.com` passes the `//` check, and the URL parser drops the tab, so `router.push` leaves the site. Fix: accept `next` only when `new URL(next, origin)` keeps our origin.
- R2. A live update can be lost: `refresh()` hands back the request already in flight, so an event that arrives during it never triggers a newer fetch (stale until the 10 s poll). Fix: mark a follow-up refresh and run it when the current one ends.
- R3. A corrupt `analysts.json` is silently replaced by the seeded accounts, wiping every signed-up analyst. Fix: stop startup with a clear error instead of overwriting.
- R4. Login timing shows which usernames exist: unknown names skip the 200k-iteration hash. Fix: verify against a fixed dummy hash when the name is unknown.
- R5. The fund trail offers the per-hop "Close account" control on every hop, including the victim's own account if money was routed back to it (the API refuses it; the user's rule is never to act on the victim's account). Fix: never render the action for the victim hop.
- R6. A failed approval request still closes the request panel and drops the typed justification. Fix: close it only on success.
- R7. Session cookie is written without `Secure` on HTTPS. Fix: add `secure` when the page is served over HTTPS.
- R8. "Resolved today" on the Team page uses the UTC day; for an Indian team it rolls over at 05:30 IST. Fix: compare the IST date.

**Efficiency (fixed in the step named):**
- E1. Every presence heartbeat (15 s per open console) writes an `analyst_presence` audit event. Each one moves the event cursor, so every console refetches the full snapshot, the open case and the ledger page, and the audit trail fills with noise. Presence is already stored in its own table. Fix (C2): heartbeats update presence only; sign-in/sign-out events stay.
- E2. `snapshot()` rebuilds 200 cases through `_case()`, each re-reading every action, every transaction and its events. Fix (C3): `snapshot.py` loads the tables once and builds case views from the preloaded rows; `store.case_actions()` uses the existing `case_actions` index.
- E3. `heartbeat()` builds a full case only to check that the id exists. Fix (C3): an existence query.
- E4. Provider context value is a new object each render; `money()`, `rupees()` and `dateTime()` build a new `Intl` formatter per call (per table cell). Fix (C8): `useMemo` the value; hoist the formatters.
- E5. The landing's GPU probe creates up to two WebGL contexts and never releases them. Fix (C8): release with `WEBGL_lose_context`.

**Reuse and simplification (fixed in the step named):**
- S1. The operation-to-permission maps (`restrict→restrict`, `lien→place_lien`, `close→close_account`, …) are written out four times in `service.py`; the victim check is duplicated in `decide`; the new-case dict is written twice (ingest and complaint); the set of non-human actors is duplicated in `service.py` and `attacks.py`; the cursor query is duplicated. Fix (C3): one constant or helper each.
- S2. `PublicAttacks.limit` re-implements `LoginLimiter`'s sliding window and borrows the service's private lock. Fix (C4): one `SlidingWindowLimiter` in `api/limits.py` used by both, each with its own lock.
- S3. `initials()` exists three times (useAnalyst, Topbar, Primitives); `ConsoleShell` re-implements `useAnalyst`; `decideCase` duplicates `runCaseAction`; Cmd+K re-implements `openSearch` (and so keeps the old query). Fix (C8).
- S4. `agent.build_brief`: a branch that re-assigns the default and a `[:4]` slice of a three-item list. Fix (C6).
- S5. The sign-out presence offset (46 s) and the online window (45 s) are unrelated literals. Fix (C3): one `ONLINE_SECONDS` constant in `team.py`.
- S6. `cytoscape` and `@types/cytoscape` are dependencies nothing imports. Fix (C8): remove them.
- S7. Stale comments: `auth.py` names two demo accounts (there are four); `security.py` mentions teammates and a deadline; `lib/auth.ts` and `proxy.ts` refer to `middleware.ts`; `schemas.py` refers to branches and a team prototype; `requirements.txt` says "Grand Finale build". Fix (C10).

**Architecture (deepening, `improve-codebase-architecture`):** there is no `CONTEXT.md` or ADR folder, so module names follow the plan's Part 1 step 2. Candidates, strongest first: (A1, strong) one case read model in `snapshot.py`, replacing the four places that compute traced/held totals; (A2, strong) one protection-target policy in `decisions.py` (S1); (A3, strong) `_deliver_action` split into fetch/post and one function per outcome in `delivery.py`; (A4, worth exploring) the shared limiter (S2); (A5, speculative) a `useCaseAction` hook for the busy/error/message pattern repeated in six console components. A1–A4 are done in C3–C4; A5 is left out (it would touch every console component for little gain).

**Recorded, not changed (with reason):**
- K1. `process_jobs` holds the service lock while calling the bank (2 s timeout per job). Releasing it changes the concurrency model the delivery tests rely on; not a refactor.
- K2. Audit `actor` is the display name on the ingest, scenario and control routes and the username elsewhere. Changing it changes visible audit copy.
- K3. The token sits in `localStorage` and a non-httpOnly cookie, and logout does not revoke it (24 h expiry). Documented trade-off of the demo; moving to an httpOnly cookie is an auth redesign.
- K4. Any signed-in analyst (including the public demo's L1 button) can switch bank mode or pause the stream for everyone. This is the simulation desk's purpose; restricting it is a role change.
- K5. `EnsembleScorer`, `core/scoring/base.py`, the `Decision`/`ScoringResult`/`GraphEvidence` schemas and `AccountRestrictionStore` are reachable only from tests. Removing them deletes tests, which this stage does not do; candidate for a later cleanup.
- K7. Detection cost grows with the ledger: every simulated payment uses IP 127.0.0.1, so the graph agent's Louvain pass sees one clique of every simulated account (6–10 s per payment at 836 payments). Fixing it changes detector scores; separate task.
- K6. `GET /public/attacks/{id}` is unauthenticated and unthrottled and builds full case views. Attack ids are 48 random bits; E2 makes each call cheap.

**Stage C steps (one commit each, all checks after each):**
- C1. Formatting baseline (Part 1 step 1): `requirements-dev.txt` pins `ruff`; `pyproject.toml` sets `line-length = 110`; `ruff format` + `ruff check --fix` on `fraudlens/ scripts/ tests/`; `prettier` pinned in `frontend/package.json` with `printWidth: 110`, run on `app/ components/ lib/ proxy.ts`. Formatting only.
- C2. Review fixes R1–R8 and E1, each with a test first.
- C3. Split `service.py` (Part 1 step 2) into `ingest.py`, `decisions.py`, `delivery.py`, `complaints.py`, `snapshot.py`, with S1, S5, E2, E3.
- C4. Shared sliding-window limiter (S2).
- C5. `guidance.py` → `guidance_data.py` (Part 1 step 3).
- C6. Detector: one function per rule; agent: `_typology`, `_recommendation`, `_narrative` (Part 1 step 4, S4).
- C7. Bank simulator and attacks: named steps for the long expressions (Part 1 step 5).
- C8. Frontend: split the remaining large or one-line components (`Primitives.tsx`, `EvidenceGraph.tsx`/`NetworkView`, `login`, `signup`, `attack`), S3, S6, E4, E5 (Part 1 step 6).
- C9. Backend test that keeps `frontend/lib/operations.ts` `ACTION_MIN_ROLE` equal to `roles.py` (Part 1 step 7).
- C10. Stale comments (S7) and a final line-length/module-size check.

---

## Part 2: Repository cleanup

**Problem:** v3 code sits next to the older hackathon pipeline and several tool/agent files, so the repo reads as two projects.

**Legacy code not used by v3** (verified by imports on 2026-10-19; recheck before deleting):
- Backend routes mounted only when `FRAUDLENS_LEGACY_API=1`: `fraudlens/api/routes/{transactions,cases,reports,decisions,copilot,stats,console,live}.py`, plus `fraudlens/api/case_cache.py`.
- Core modules only those routes use: `fraudlens/core/{cases,compliance,copilot,dna,graph,reports}`, `fraudlens/core/privacy.py`; `fraudlens/evaluation/{benchmark,validate_ulb}.py`; `fraudlens/data/{fraud_dna_library.json,ulb_validation.json}` if unused after removal.
- **Keep:** `fraudlens/core/auth`, `fraudlens/core/scoring` (detector signals) and `fraudlens/data/synthetic_generator.py` (reference ML training data).
- Frontend dead code: `components/{CopilotChat,DecisionForm,CaseListItem,FraudRingGraph,DecisionBadge?,SignalBar?,StatCard?,CountUp?,Reveal?,MaskedId?,Panel?}.tsx` and `lib/{api,agents,types?,reasons,risk,severity,tier}.ts` — check each with a grep before removing; redirect-only pages `app/(console)/{feed,fraud-dna,network/explore}`.
- Tests that only cover removed code.

Steps:
1. **Decide legacy (user decision, recommended: remove).** Remove the legacy pipeline from the tree; git history and a `legacy-hackathon` tag keep it. Update README "Credits" with one line pointing at the tag. Recount tests (expect a lower number) and update `frontend/components/landing/proof.ts` and `docs/VERIFICATION.md` with the new counts.
2. **Root and frontend clutter.**
   - Move `scrollcraft/` (design-skill build notes) to `docs/design/scrollcraft/` or delete if nothing imports it (the landing imports `components/landing/scrollcraft.js`, a copy).
   - Delete `frontend/AGENTS.md` and `frontend/CLAUDE.md` (Next.js tooling stubs, re-created by `next dev`; add both to `frontend/.gitignore`).
   - Move `frontend/DESIGN-AUDIT.md` and `docs/UI-REDESIGN.md` to `docs/history/`; `frontend/work-report.md` is already ignored — delete the local copy.
   - Keep `DESIGN.md`, `PRODUCT.md`, `AGENTS.md` at the root (they are current).
3. **Docs folder.** `docs/` keeps: `ARCHITECTURE.md`, `OPERATIONS_API.md`, `OPERATIONS_EVALUATION.md`, `GUIDANCE.md`, `VERIFICATION.md`, `screenshots/v3/`, `verification/`, `history/`, `superpowers/`. Remove old screenshots not referenced (`screenshots/{overview,mobile,case-reversal}.png` once the old VERIFICATION section links are updated). Add `docs/README.md`: a 10-line index of what each doc is for.
4. **Deploy leftovers.** Keep `deploy/hf-space/` + `scripts/deploy_hf.sh` (paid-Space option) but say so in `deploy/README.md`; or remove them if the user prefers Render only.
5. **Final tidy.** `git ls-files` review; `.gitignore` covers `.claude/`, `var/`, `frontend/.next`, build outputs; README "Structure" section rewritten to match the new tree.

Done when: the root holds only project files (app code, tests, docs, deploy, config); no dead imports (`ruff` + `eslint` unused-import checks clean); README structure matches `git ls-files`; all checks green.

---

## Part 3: Visual redesign

**User's direction (2026-10-19, authoritative):**
- Look and feel of **premium fintech SaaS** sites: it should feel premium when opened, touched and interacted with, and still read as a **fraud / risk** product.
- **Not** fancy or bright colours, and **not** the typical AI-template palette: no purple, indigo or dark-blue themes. Colour pairings must be deliberate, with real contrast.
- **One standardised core visual** across landing, console and attack pages. Pages may have their own mood, but they must complement each other; no jumps like one area light red and another dark green.
- **Landing page as beautiful as possible.**
- Must not look "vibe-coded" (generic AI-generated UI). (The user wrote "white-coded"; read as vibe-coded, and also as: not a plain all-white page. Confirm when Part 3 starts.)
- Use the best of the installed design skills.

**Current state:** light workbench console (canvas `#f5f7fb`, cobalt `#4058d5` — which falls in the colour family the user rejected), a light landing with a Three.js lens, and a separate dark charcoal/red attack page. Tokens are spread over `frontend/app/globals.css`, `landing.css`, `attack/attack.css`, `workspace-views.css`.

**Palette concepts to mock up (pick one; all avoid blue/indigo/purple):**
1. **Graphite + brass.** Warm graphite (`~#16171a`) chrome, warm off-white work surfaces (`~#f3f1ec`, not pure white), a muted brass/amber accent for primary actions and the brand mark. Feels like a bank vault / control room.
2. **Graphite + deep emerald.** Same neutrals, a desaturated deep green accent. Calm, money-coded; green must stay distinct from the "funds held" status colour.
3. **Graphite + signal vermilion.** Same neutrals, a muted vermilion accent tied to "risk", with green kept for "held/safe". Most "fraud" in feel; needs care so red does not read as error everywhere.

In every concept: one accent colour only; semantic colours (risk, frozen, held, closed, pending approval) are a fixed, tested set used only for meaning; WCAG AA contrast on every text pair; tabular numerals for money and scores; a monospace for IDs. The attack page keeps its "attacker" mood by sitting fully on the dark graphite side of the same palette, not by using new colours.

**Skill map (use in this order):**
| Need | Skill |
| --- | --- |
| Audit the current UI and score it | `unslop:audit`, `anti-slop` |
| Art direction, critique, polish | `impeccable`, `frontend-design` |
| Palette and type exploration | `ui-ux-pro-max`, `unslop:retheme` |
| Token architecture (primitive → semantic → component) | `ckm-design-system` |
| Brand mark and voice consistency | `ckm-brand` |
| Landing scroll storytelling | `nateherk-design:scroll-craft` |
| 3D hero (lens restyle, materials, lighting, post-processing) | `threejs-fundamentals`, `threejs-materials`, `threejs-lighting`, `threejs-shaders`, `threejs-postprocessing`, `threejs-animation` |
| Charts on dashboard and evaluation | `dataviz` |
| Accessibility and interface rules | `web-design-guidelines` |
| React/Next performance after the redesign | `vercel-react-best-practices` |
| Browser checks and screenshots | built-in browser, `playwright` |

**Process:**
1. Run the audit skills on today's landing, dashboard, case page and attack page; save the findings to `docs/design/audit-before.md`.
2. Build the three palette concepts as static mockups (landing hero, case page, attack page side by side) and let the user pick one; confirm the "white-coded" reading.
3. Write `frontend/app/tokens.css` (primitive → semantic → component tokens) as the only colour/type/spacing source; every other stylesheet uses tokens only (a test fails on hex colours outside `tokens.css`).
4. Restyle shared components (buttons, chips, tables, panels, inputs, empty/loading states, focus rings) once.
5. Landing: redesign every section with the new tokens; keep the 3D lens but restyle it to the palette (materials, lighting, post-processing), with a static fallback and reduced-motion support; scroll-craft only for meaningful motion.
6. Console pages, then the attack page, then login/sign-up.
7. Checks: WCAG AA contrast table, keyboard focus, reduced motion, 390px and 1280px on every page, no horizontal overflow, Lighthouse performance on the landing; screenshots to `docs/screenshots/v4/`; re-run the audit skills and save `docs/design/audit-after.md`.
8. User review in the browser before any push to `main`.

Done when: one token file drives every page, the chosen palette has no blue/indigo/purple, the before/after audit shows the generic-UI findings resolved, all checks pass, and the user approves the look.
