# FraudLens: code revamp, repository cleanup and visual redesign

**Status:** Parts 1–2 ready to implement. Part 3 is a proposal; its open decisions (end of Part 3) must be settled with the user before any redesign code is written.

**Ground rules (all parts):**
- No new features. Behaviour, routes, API contracts, roles, copy and numbers stay the same unless a step says otherwise.
- Work on `feature/fraudlens-v3`; one commit per numbered step; conventional messages with the Co-Authored-By line.
- After every step: `.venv/bin/python -m unittest discover -s tests`, `npm --prefix frontend run test`, `npm --prefix frontend run lint`, `(cd frontend && npx tsc --noEmit)`. All green before committing.
- Pushing to `main` redeploys the live site (Render): ask the user before every push.
- Order: Part 2 (cleanup) first, so Part 1 refactors less code; then Part 1; then Part 3.

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

## Part 3: Visual redesign (proposal — decisions pending)

**User's brief (2026-10-19):** more professional and bold, not "vibe coded"; landing, console and attack pages share one colour system and identity; strong but not bright or fancy colours; aligned with what the product does.

**Current state:** light workbench console (canvas `#f5f7fb`, cobalt `#4058d5`), a light landing with a Three.js lens, and a separate dark charcoal/red attack page. Tokens live in `frontend/app/globals.css`, `landing.css`, `attack/attack.css`, `workspace-views.css` — three partly separate palettes.

**Proposed direction (my recommendation, to confirm):** "operations control room".
- **One token source.** A single `frontend/app/tokens.css` imported by every page: ink/graphite neutrals, one restrained brand colour, and semantic colours used *only* for meaning (risk, held, frozen, closed, approval). Landing, console and attack all use it.
- **Brand colour.** A deep, desaturated colour instead of bright cobalt — e.g. deep indigo/ink-blue or deep teal — used for primary actions, focus and the brand mark only.
- **Structure.** Dark graphite chrome (sidebar, top bar, landing hero, attack page) with light, high-contrast working surfaces for dense data (tables, case pages), so it reads like a serious operations tool and stays readable.
- **Typography.** Keep Mona Sans; stronger hierarchy (heavier, tighter headlines; tabular numerals everywhere money or scores appear); a monospace for IDs and amounts.
- **Components.** Consistent status chips, tables, panels, buttons and empty states; fewer one-off styles; motion only where it explains state (live updates, fund trail), always respecting reduced motion.
- **Landing.** Same palette and type as the console; the 3D lens either restyled to the new palette or replaced by a calmer product-led hero (decision below).
- **Skills to use when implementing:** `impeccable` / `frontend-design` for direction and critique, `scroll-craft` only if the landing keeps scroll-driven motion, `anti-slop`/`unslop:audit` for a before/after audit, `web-design-guidelines` + WCAG AA contrast checks.

**Process when implementing:** audit current screens → two or three quick visual directions as static mockups (landing hero + case page + attack page) for the user to pick → token file + components → landing → console pages → attack page → contrast/keyboard/reduced-motion/390px checks → screenshots → user review before any push.

**Open decisions (settle these first):**
1. A reference product or site whose look FraudLens should feel closest to.
2. Console: dark chrome with light work surfaces (recommended), fully dark, or fully light.
3. Brand colour family: deep indigo/ink-blue, deep teal, or another restrained colour.
4. Landing hero: keep the 3D lens (restyled), or replace it with a product-led hero (a live console preview).
5. Attack page: keep its separate "attacker" mood within the shared palette, or make it match the console fully.
