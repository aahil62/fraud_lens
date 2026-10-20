# Verification record

## Detection no longer slows as the ledger grows (20 October 2026)

Branch `feature/fraudlens-v3`, after Stages C and D. Fixes K7 from the section below. The graph agent treated `127.0.0.1`, the API's "no IP supplied" default that every simulated payment carries, as an identifier shared by every simulated account, so each payment ran Louvain over one clique of hundreds of accounts. Now loopback and unspecified addresses are not evidence, and an identifier shared by more than 50 accounts still counts as sharing but is left out of the ring projection (a group that size is infrastructure or a default value, and its edges grow with the square of its size).

| Check | Observed result |
| --- | --- |
| One `detect()` on a copy of the local ledger (836 payments) | **6.4–10.2 s → 16 ms** per payment. |
| New tests | `test_detector_scaling` (1,000 prior default-IP payments, under 2 s and no `127.0.0.1` ring reason); two graph-agent tests (loopback/unspecified IPs; a 60-account shared device is reported but is not a ring). They failed before the fix. |
| Backend suite | **241 tests, OK** (44.9 s). Frontend 64 passed; lint, types, ruff and prettier clean. |
| Evaluation | Re-run: same corpus hash, same overall metrics, and all 376 records have the same score and reasons (the fixtures use a test-net IP), so `operations-evaluation.json` and the README table are unchanged. |
| Simulated payments | Sampled ledger payments: the graph signal falls from 0.95 ("fraud ring of 662 accounts", which was never true) to 0.05, and final scores fall by about 0.09 (for example 0.2285 → 0.1385). All sampled payments were below the 0.5 review threshold before and after. |

## Code review, refactor and repository tidy, Stages C and D (20 October 2026)

Branch `feature/fraudlens-v3`, local machine. Not yet pushed or deployed (see the end of this section). Every Python, TypeScript and script file was reviewed with `code-review` (high), `improve-codebase-architecture`, `simplify`, `vercel-react-best-practices` and `vibesec-skill`; the findings and what happened to each are in the [revamp plan](superpowers/plans/2026-10-20-revamp-cleanup-redesign.md#stage-c-review-findings-20-october-2026) (R1–R8, E1–E5, S1–S7, K1–K7).

| Check | Command | Observed result |
| --- | --- | --- |
| Backend suite | `.venv/bin/python -m unittest discover -s tests` | **238 tests, OK** (53.8 s). Six new: four for review fixes (R3, R4, R8, E1) and two that keep the console's role table equal to `roles.py`. |
| Frontend tests | `npm --prefix frontend run test` | **64 passed** (22 files). Seven new: R1 open redirect, R7 Secure cookie, R5 victim hop, R6 approval panel, R2 lost update, and two for `robots.txt`. |
| Lint, types, format | `npm --prefix frontend run lint`, `npx tsc --noEmit`, `npm --prefix frontend run format:check`, `ruff check` / `ruff format --check` on `fraudlens scripts tests` | All clean. ruff 0.16.10 and prettier 3.9.9 are pinned; CI now runs both. |
| Production build | `npm --prefix frontend run build` (dev server stopped) | Passed; the same 15 routes plus `/robots.txt`. |
| Production npm audit | `npm --prefix frontend audit --omit=dev` | 0 vulnerabilities. `cytoscape` (unused) was removed. |
| Size and width | scripted check | No Python module outside `tests/` and no frontend module over 300 lines; no code line over 110 columns (long string literals, mostly UI copy and sources, excepted). `service.py` went from 1,228 formatted lines to 191, with seven focused modules. |

Behaviour was held fixed by comparison, not only by the test suite:
- **Operations read models.** A ledger with every scenario, a complaint, an approval, a fraud verdict and a reversal was built once; its snapshot, every case view and the case listing were byte-identical before and after the `service.py` split.
- **Detector and agent.** Scores, signals and reasons for all 376 evaluation incidents, and the agent brief for each of them under three verdicts plus every case in that ledger, were identical before and after the rule and brief refactor. Regenerating the evaluation gives the committed corpus hash, overall metrics and per-record scores.
- **Guidance.** `guidance_response()` returns the same JSON as before the move to `guidance_data.py`.
- **Snapshot cost.** On a copy of the local ledger (836 payments, 101 cases, 3,629 events), one `snapshot()` took 2,054 ms with the old code and 47 ms with the new.

### Checked in the browser

`scripts/dev.py` through the preview tool; Playwright with full Chromium on the Apple M4 GPU (ANGLE Metal), signed in as R. Iyer. Screenshots: [docs/screenshots/v4/](screenshots/v4/) (1280 px and 390 px; console pages full-page).
- **All 14 pages at 1280 × 800 and 390 × 844:** 0 px horizontal overflow and 0 console errors on every page.
- **Landing:** the 3D lens renders after its split into `lensModel.ts` (in-app browser and headless GPU Chromium); no console errors.
- **Case page and Connections:** the split case workspace, evidence column and evidence graph render as before.
- **Dashboard "Latest activity"** now shows payments and bank events instead of a stream of "analyst presence" rows (E1).
- **Public attack and 1930 report** (API): a mule-layering attack showed four of six steps done and waiting for an analyst; the report traced ₹28,000 across two hops with ₹20,000 cashed out, and both liens were held (₹28,000) once the bank acknowledged them.
- **`/robots.txt`** returns 200 `text/plain` with the allow/disallow rules (it returned the sign-in page before).

### Found and recorded, not fixed

- **Detection slows as the ledger grows (K7, since fixed; see the section above).** Every simulated payment uses IP 127.0.0.1, so the graph agent's Louvain pass sees one clique of every simulated account. On the 836-payment local ledger one `detect()` took 6–10 s, 99% of it in Louvain; a public attack launch took 43 s. The code is unchanged by this stage; fixing it changes scores, so it is a separate task. The live demo resets its ledger on every boot and starts with the stream paused, which keeps it small.
- **Occasional slow snapshot under load.** With the stream running every 5 s, snapshots took about 100 ms but spiked to about 3 s while a scenario was being scored (same cause as above).
- K1–K6 in the plan: the service lock is held across bank calls; audit actors are display names on three routes; the token sits in `localStorage` and logout does not revoke it; any analyst can change the shared simulation controls; test-only scoring modules remain; the attack status route is unthrottled.

### Not verified

- `docker build` (Docker was not running on this machine). The only container-relevant change is that `frontend/public/` now holds just the fetched fonts, which `fetch-fonts.mjs` creates before the Dockerfile copies it.
- Lighthouse was not re-run; the expected change is SEO now that `/robots.txt` is valid.
- The detector fix in the section above is not deployed yet (it came after the push).

### Live site (after the user approved the push)

`feature/fraudlens-v3` was merged into `main` with `--no-ff` (`bea4981`; the merge tree equals the branch tip, so nothing on `main` was dropped) and pushed; Render served the new build about 90 s later (`started_at` 2026-10-20T14:05:55Z). Checked at 1280 × 800 with GPU Chromium against https://fraud-lens-r3t0.onrender.com:
- Landing (3D lens rendered), `/attack`, `/login`, demo sign-in as R. Iyer, dashboard, investigation queue and a case page: **0 px overflow and 0 console errors** on each.
- `/robots.txt` returns the robots rules instead of the sign-in page.
- A mule-layering attack launched in 1 s and showed four of six steps done, waiting for an analyst. "Report it to 1930" (1 s) traced ₹28,000 across two hops with ₹20,000 cashed out, and both liens were held (₹28,000) after the bank acknowledged them.
- Not checked on the live site: a phone, a second analyst session, or Lighthouse.

## Same-origin display fonts (20 October 2026)

Branch `feature/fraudlens-v3`, local machine only. Nothing was pushed or deployed. Tanker and Erode are now served from the console's own origin. `frontend/scripts/fetch-fonts.mjs` reads the faces from `app/fonts.css` and downloads them from Fontshare into `frontend/public/fonts/` (npm `predev` and `prebuild` hooks, so both `scripts/dev.py` and the Docker build run it). That folder is in `.gitignore` and `.dockerignore`: the ITF Free Font License allows self-hosting but not redistributing the files from the repository. Every `@font-face` lists `/fonts/<file>.woff2` first and the Fontshare CDN copy second, so a failed fetch falls back to the CDN. The Fontshare `preconnect` was removed, and `proxy.ts` now skips `/fonts/`; before this change a logged-out request for a font would have been redirected to `/login`.

| Check | Command | Observed result |
| --- | --- | --- |
| Backend suite | `.venv/bin/python -m unittest discover -s tests` | **232 tests, OK** (63.8 s). |
| Frontend tests | `npm --prefix frontend run test` | **57 passed** (20 files), including the new `app/fonts.test.ts`: four faces, each local first with a Fontshare fallback, and the proxy matcher skips `/fonts/`. |
| Lint, types | `npm --prefix frontend run lint`, `cd frontend && npx tsc --noEmit` | Passed, no warnings. |
| Production build | `npm --prefix frontend run build` (dev server stopped) | Passed; same 15 routes. The built CSS has `src:url(/fonts/tanker-400.woff2) format("woff2"),url(https://cdn.fontshare.com/…)`. |
| Not tracked | `git check-ignore -v frontend/public/fonts/tanker-400.woff2` | Ignored by `.gitignore`; `git status` lists no font file. |
| Dev | `scripts/dev.py`, landing in the in-app browser | `predev` logged the four files; `/fonts/tanker-400.woff2` and `/fonts/erode-700.woff2` returned 200 and no request went to `cdn.fontshare.com`. |
| Fallback | Same, with `public/fonts/` renamed | `/fonts/*` returned 404 (not a redirect); the browser loaded both faces from `cdn.fontshare.com` and Tanker and Erode 700 reported `loaded`. |
| Offline fetch | `fetch-fonts.mjs` with `fetch` forced to reject | Warned for each file ("the CDN copy will be used"), exit 0. |
| Docker | `docker build .`, then `docker run -p 7861:7860` | The build logged `fonts: … fetched` for all four; the image has them in `frontend/.next/standalone/public/fonts/`, and `GET /fonts/tanker-400.woff2` returned 200 `font/woff2` (19 236 B). |

### Lighthouse on the landing

Same setup as Stage B: Lighthouse 12.8.2, Chrome for Testing 156 (headless), `next start`, default mobile settings. The first three runs after the change gave mobile **64 / 69 / 68** (Accessibility 100, Best Practices 100, SEO 91), FCP 2.6 s, LCP 5.5 s, TBT 310–470 ms. That looked like a large gain over Stage B's 38–47, so the previous commit (`b70f7ae`, CDN fonts) was built in a temporary worktree and both were run alternately in one session, six mobile and three desktop runs each:

| Landing | Mobile (6 runs) | Mobile median | Median FCP / LCP / TBT | Desktop (3 runs) | Tanker download finished (observed, median) |
| --- | --- | --- | --- | --- | --- |
| CDN fonts (`b70f7ae`) | 32–71 | 44.5 | 2.6 s / 8.6 s / 1.6 s | 69–98 | 721 ms, second origin `cdn.fontshare.com` |
| Same-origin fonts | 35–62 | 39 | 3.2 s / 11.6 s / 1.5 s | 81–99 | 246 ms, own origin only |

What this shows:
- **No measurable change to the mobile score.** Both builds are bimodal (LCP about 5.3 s or 11–12 s), and the spread between runs is larger than any difference between the builds. The score follows TBT, which is the 3D lens on a 4× throttled CPU, plus this machine's load. The 64–69 runs above happened to be quiet ones.
- **The font cost Stage B blamed was overstated.** The faces use `font-display: swap`, so they never held back first paint; FCP is about 2.6 s either way. The fonts now finish downloading earlier and from one origin, which shortens the swap from the fallback face, but Lighthouse does not score that.
- Recovering mobile performance needs work on the lens (deferring it, or a lighter path on slow CPUs), not more font work.

## Visual redesign, Stage B (20 October 2026)

Branch `feature/fraudlens-v3`, local machine only. Nothing was pushed or deployed. Graphite + brass palette with Tanker, Erode, Mona Sans and Courier Prime, chosen by the user from `docs/design/palette-concepts.html` and `docs/design/type-concepts.html`. Design record: [DESIGN.md](../DESIGN.md); audits: [before](design/audit-before.md), [after](design/audit-after.md).

| Check | Command | Observed result |
| --- | --- | --- |
| Backend suite | `.venv/bin/python -m unittest discover -s tests` | **232 tests, OK, 0 skipped** (61.6 s). |
| Frontend tests | `npm --prefix frontend run test` | **55 passed** (19 files), including `app/tokens.test.ts` (no raw colour outside `app/tokens.css`) and the software-WebGL fallback test in `LensScene.test.tsx`. |
| Lint, types | `npm --prefix frontend run lint`, `cd frontend && npx tsc --noEmit` | Passed, no warnings. |
| Production build | `npm --prefix frontend run build` (dev server stopped) | Passed; 15 routes (the redirect-only `/feed`, `/fraud-dna` and `/network/explore` were removed in Stage A). |
| Design audit | `unslop:audit` checklist + `anti-slop` law | **59 → 97** (17/29 → 28/29 applicable checks). The remaining partial item is the hero's kicker and button-plus-link copy, which this stage could not change. |

### Checked in the browser

Scripted Playwright (Chromium headless shell) against `scripts/dev.py`, signed in as R. Iyer (L2); landing screenshots retaken with Chrome for Testing so the GPU lens renders. Screenshots: [docs/screenshots/v4/](screenshots/v4/).

- **All 14 pages at 390 × 844 and 1280 × 800** (landing, login, signup, attack, dashboard, investigations, case, team, transactions, connections, bank, reports, audit, guidance): **0 px horizontal overflow and 0 console errors** on every page, rechecked after Erode started loading.
- **Contrast.** Every token text/background pair passes WCAG AA; the lowest is caution on caution tint, 5.26:1 (full table in [audit-after.md](design/audit-after.md)). `contrast-check.mjs` on rendered `/`, `/attack` and `/login`: all sampled pairs pass (the landing had 2 failures before).
- **Keyboard.** Tabbing landing, attack and dashboard at both widths: every focused element shows a 2 px ring (brass on graphite, dark brass on stone; two mobile top-bar items resolve to an ink ring, 15:1). The mobile drawer takes focus, traps Tab, closes on Escape and returns focus to the menu button.
- **Reduced motion** (emulated `prefers-reduced-motion: reduce`): the landing shows the SVG lens and creates no WebGL canvas; parallax is off; the golden-hour locks are static. With motion allowed and a GPU (in-app browser, ANGLE Metal on Apple M4), the 3D lens renders. With software WebGL (SwiftShader), the static lens is kept.

### Lighthouse on the landing

Lighthouse 12.8.2 with Chrome for Testing 156 (headless, hardware GPU), against `next start` serving the production build on this machine. Default mobile settings (simulated slow 4G, 4× CPU throttle) and `--preset=desktop`. Scores are Performance / Accessibility / Best Practices / SEO; the pre-redesign landing (`70a9877`, built the same way in a temporary worktree) ran alternately in the same session, three runs each, because this machine's load made single runs noisy.

| Landing | Mobile | Desktop | Mobile FCP / LCP | Mobile TBT |
| --- | --- | --- | --- | --- |
| Before Stage B (`70a9877`) | 38–57 / 97 / 100 / 91 | 83–95 / 97 / 100 / 91 | 1.7–2.9 s / 4.9–5.8 s | 1.1–4.1 s |
| After Stage B (final) | 38–47 / **100** / 100 / 91 | 75–86 / **100** / 100 / 91 | 2.5–2.7 s / 5.5–12.1 s | 2.1–11.9 s |

Fixes made after the first measurement (mobile 33, TBT 20 s, LCP 20 s):
- Tanker and Erode are declared in `app/fonts.css` against Fontshare's CDN instead of linking Fontshare's stylesheet. This removed a render-blocking request to a second origin, and it fixed a real bug: the combined stylesheet request returned only Tanker, so Erode had been falling back to the system serif.
- The lens skips WebGL when the browser reports a software renderer (no GPU) and keeps the complete SVG lens.
- The studio-reflection environment renders at 64 px instead of 256 px.
- Tried and reverted: starting the lens only once the browser was idle (it moved the work into the measured window and made desktop worse).

Recorded, not fixed:
- **Mobile performance is still below the old landing.** First paint is about 0.9 s later because the fonts come from a third-party origin, and the 3D lens costs main-thread time on a throttled CPU. Serving the two fonts from our own origin (downloaded during the Docker build, never committed, which the licence allows) would remove the first cost; it is a larger change than this stage allowed. (Done afterwards; it did not move the score. See "Same-origin display fonts" above.)
- **SEO 91 before and after:** `/robots.txt` returns the app's HTML because the console proxy does not exclude it.
- Accessibility rose from 97 to 100 (the old landing failed `color-contrast`).

### Not verified

- A real phone (performance of the 3D lens on a mobile GPU, touch scrolling), a screen-reader pass, and browsers other than Chromium.
- Lighthouse on the deployed Render site (only local production builds were measured).

## Legacy pipeline removed (20 October 2026)

Branch `feature/fraudlens-v3`. The hackathon pipeline is preserved at the local `legacy-hackathon` tag (not pushed). Removed: the legacy API routes (`/transactions`, `/cases`, `/reports`, `/decisions`, `/copilot`, `/stats`, `/console`, `/live`) and `case_cache.py`; `core/{compliance,copilot,dna,reports}`, `core/graph/builder.py`, `core/cases/{case_engine,decision_workflow,autonomous_action}.py`, `core/privacy.py`; `evaluation/{benchmark,validate_ulb}.py` and `data/ulb_validation.json`; `scripts/run_demo.py`, `scripts/setup_groq_key.sh`; dead frontend components and libraries; the redirect-only `/feed`, `/fraud-dna` and `/network/explore` pages; and the tests that covered only that code. Kept: `core/auth`, `core/scoring`, `core/graph/community.py` and `core/cases/account_restriction.py` (the detector's agents use them) and `data/synthetic_generator.py`.

| Check | Observed result |
| --- | --- |
| Backend suite | **232 tests, OK, 0 skipped** (15.5 s). The former skip was the removed ULB dataset check. |
| Frontend tests | **53 passed** (18 files); the 5 removed tests covered the deleted Copilot chat. |
| Lint, types | `npm --prefix frontend run lint` and `npx tsc --noEmit` passed. |
| Legacy route | With `scripts/dev.py` running, `GET :8001/transactions/recent` returns 404. |

## v3 operations centre (19 October 2026)

Branch `feature/fraudlens-v3`, local machine only. Nothing was pushed or deployed. No CI run is claimed.

| Check | Command | Observed result |
| --- | --- | --- |
| Backend suite | `.venv/bin/python -m unittest discover -s tests` | **425 tests, OK, 1 skipped** (199.9 s). The skip is the optional external ULB dataset. |
| Frontend tests | `npm --prefix frontend run test` | **55 passed** (19 files). |
| Lint | `npm --prefix frontend run lint` | Passed, no warnings. |
| Types | `cd frontend && npx tsc --noEmit` | Passed. |
| Production build | `npm --prefix frontend run build` (dev server stopped) | Passed; 20 routes including `/attack` and `/team`. |
| Production npm audit | `npm --prefix frontend audit --omit=dev` | 0 vulnerabilities. Development-only ESLint advisories remain (see Limits). |
| Evaluation | `.venv/bin/python -m fraudlens.evaluation.operations` | 376 incidents; protection precision 0.8462, recall 0.8148 ([details](OPERATIONS_EVALUATION.md)). `tests/test_evaluation_snapshot.py` checks the table matches the JSON. |
| Container | `docker build -t fraudlens .` then `docker run -p 7860:7860 fraudlens` | Built (994 MB). `/` 200, `/backend/health` 200, `/attack` 200; demo L2 sign-in reached a live dashboard; a mule-layering attack and its 1930 report traced and held ₹28,000. Runs as uid 1000. |

### Checked in the browser

Built-in browser against `scripts/dev.py` (bank :8002, API :8001, console :3000), at 1280×800/1280×720 and 390×844:

- **Two-analyst hand-off.** K. Mehta (L1) on `127.0.0.1:3000` and R. Iyer (L2) on `localhost:3000` (separate origins keep separate sessions). A mule-layering scenario appeared for both; K. Mehta claimed it; R. Iyer saw "Assigned to K. Mehta"; K. Mehta's agent brief offered "Request approval from L2"; R. Iyer saw the request banner and a Team badge of 1, approved; both saw verdict Fraud and "handled by K. Mehta, R. Iyer"; the timeline recorded "Approved by R. Iyer (requested by K. Mehta)".
- **1930 fund trail.** A complaint on the same chain traced ₹28,000 across two mule hops (₹20,000 already cashed out at an ATM) and showed both held after bank acknowledgement.
- **Team page** (supervisor): presence, approvals, Auto-assign switch and agent counters. **Bank page**: Frozen/Active/Closed chips, available vs balance, liens with case links.
- **Login** demo-role buttons route to `next`. **Attack console** at 390×844 and 1280×720: launch, live six-step timeline, "Report it to 1930" result.
- **Landing**: every section rendered at 1280×720 and 390px (no blank sections); golden-hour animation and lock positions; architecture diagram switches to a stacked list on mobile.
- **No horizontal page overflow** at 390px on landing, login, signup, attack, dashboard, investigations, case (detector and complaint), team, bank and guidance. Wide tables and the queue status strip scroll inside their panels.
- **Keyboard**: mobile drawer opens with Enter, traps Tab/Shift+Tab, closes with Escape and returns focus to the menu button; focus outlines are visible. Attack-console radio cards show a focus ring.
- **Contrast** (computed WCAG ratios): role chips 5.8–6.9:1, muted text on canvas 4.87:1, status chips ≥4.7:1. Two failures were fixed: white on the attack launch button (3.72 → 5.13:1 with `#c23f45`) and the pending-step icon (2.59 → 4.36:1).
- **Reduced motion**: global `prefers-reduced-motion` rule plus specific rules for the attack timeline and golden-hour loop (which shows locks statically). The emulated preference itself was not toggled in the browser tool.

Screenshots: [docs/screenshots/v3/](screenshots/v3/) — landing hero, golden hour, architecture, team section (mobile), dashboard, investigations, case with agent brief, approval, fund trail, team, bank, attack (mobile), login roles.

### Not verified

- Two physically separate devices or networks; the two-analyst checks used two origins in one browser (local) and browser + API client (live).
- A real `prefers-reduced-motion` toggle, screen-reader pass, or browser matrix beyond the built-in Chromium-based browser.
- The optional Ollama wording path against a running model (covered only by mocked tests).
- NPCI lien/hold rules (source unavailable; labelled "modelled on (unverified)").
- Shutdown on Render (its stop deadline is unknown; checked only with local Docker Desktop).

### Combined branch: Task 16 Steps 1–2 + shutdown fixes (19 October 2026)

`feature/fraudlens-v3` after merging `claude/fraudlens-task-16-9eeb86` (merge `a98a028`) and the shutdown fixes (`35a1834`, `0111f21`, `72c6f8d`):

| Check | Observed result |
| --- | --- |
| Backend suite | **442 tests, OK, 1 skipped** (209.2 s). |
| Frontend | **55 tests passed** (19 files); lint, `tsc --noEmit` and production build passed. |
| Container build | `docker build -t fraudlens .` passed. |
| Container behaviour | `/backend/health` 200 within 3 s of start; `/`, `/attack` 200; `/backend/ops/public-status` `{"ready":true,"mode":"demo",...}` without a token; signup 403; with one earlier successful login, failed logins returned 401 until the 20-attempt limit and 429 after; a mule-layering attack reached "Bank confirmed protection" and its 1930 report traced and held ₹28,000. |
| Shutdown | With an authenticated `/ops/events` stream open, `docker stop` exited **0 in 1.5 s** and the logs contained no traceback. `dev.py` port checks now tolerate sockets left in TIME_WAIT by a just-stopped launch and wait up to 5 s for a port to free. |

### Live demo on Render (19 October 2026)

Hugging Face now requires a paid plan for Docker Spaces, so the user deployed the same Dockerfile from `main` (`449a1af`) as a free Render web service: https://fraud-lens-r3t0.onrender.com. Locally, the image capped at 0.1 CPU / 512 MB (Render free tier) started in 82 s, used about 240 MB, and served signed-in snapshots in about 0.5 s.

Checked on the live site:
- `/`, `/login`, `/attack`, `/backend/health` 200; `/backend/ops/public-status` `{"ready":true,"mode":"demo",...}`.
- Demo L1 sign-in reached the queue with "System live". A scam launched from `/attack` at 375×812 appeared in the analyst's queue **1.9 s** later.
- Hand-off: K. Mehta claimed the case and requested confirm-fraud approval in the browser; R. Iyer approved as a separate client through the API; K. Mehta's page then showed "Approved by R. Iyer (requested by K. Mehta)".
- The bank declined mule M1's later ₹15,000 payment (`account_restricted`) after protection was confirmed; M2's ₹20,000 ATM cash-out had already posted.
- "Report it to 1930" filed a complaint that traced ₹28,000 across two hops and held ₹28,000 ([screenshot](screenshots/v3/live-fund-trail.png), [mobile](screenshots/v3/live-attack-mobile.png)).

Two live problems found and fixed in `781adbd` (verified locally in the container; **not yet live until `main` is pushed and Render redeploys**):
- **Rate limits did not trigger.** 21 failed logins all returned 401: behind Render's Cloudflare edge the right-most `X-Forwarded-For` entry changes per request. Limits now key on `CF-Connecting-IP`, which Cloudflare sets itself (`FRAUDLENS_CLIENT_IP_HEADER`, trusted only from the console proxy).
- **Live push was buffered.** Next.js gzipped `/ops/events` behind the `/backend` rewrite (Cloudflare always accepts gzip), so consoles updated only on the 10 s poll. Compression is now off in Next and left to the edge; the container stream now delivers its first event immediately with gzip accepted.

**Redeployed and rechecked live (19 October 2026, `main` at `a61859a`):**
- Live updates: after `babe951`, `/ops/events` delivered its first event immediately with `Accept-Encoding: gzip, br`.
- Rate limit: still did not trigger after `babe951`. Root cause: uvicorn's default proxy-header handling trusts 127.0.0.1 and replaced the request peer with the `X-Forwarded-For` value before `client_ip()` ran (unit tests use a test client that bypasses uvicorn). Fixed in `7bd4d67` by starting uvicorn with `--no-proxy-headers`, with a real-server regression test. Live after redeploy: 21 failed logins → 20 × 401 then **429**, and a forged `X-Forwarded-For` on the next attempt still got 429. Cloudflare rejects requests that forge `CF-Connecting-IP` (403).
- Backend suite at `7bd4d67`: 446 tests OK, 1 skipped.

**Final live checks (19 October 2026, `main` at `6c81da5`):**
- **Rate-limit key.** A temporary route (removed in `6c81da5`) reported, as salted hashes only, which address headers reach the API. `CF-Connecting-IP` and `True-Client-IP` were present and identical across requests; the middle `X-Forwarded-For` entries changed on every request (Cloudflare edge addresses), which explains the original failure. Requests sent over this machine's IPv4 and IPv6 had the same `CF-Connecting-IP`, so Cloudflare treats them as one visitor and they correctly share a limit (IPv4: 429 after 20 attempts; IPv6 then 429 too). A second, genuinely different visitor address was not available; the per-visitor split is covered by `tests/test_public_demo.py` and the real-server test in `tests/test_dev_launcher.py`.
- **Cold start.** After 17 idle minutes, the first request to `/` took **52 s** (Render wake-up plus boot), then 0.3 s warm.
- **Public-demo polish.** The live login page no longer links to the disabled sign-up page; the dashboard's "Next to investigate" follows agent priority.
- Backend suite at `6c81da5`: 446 tests OK, 1 skipped; frontend 58 tests, lint and types pass.

## Earlier record (17 October 2026)


Verified locally on **17 October 2026**, on the implementation branch `codex/fraudlens-live-operations`. Remote CI has been configured; a GitHub Actions run is not claimed.

| Check | Observed result |
| --- | --- |
| Complete Python regression suite | **330 tests, OK, 1 skipped**, 280.581 seconds. The optional external ULB dataset was unavailable. |
| Focused operational backend | **32 tests passed**, covering operations, API, bank simulator and session-key guards. Included in the full suite. |
| Launcher process-safety checks | **4 passed**: port collisions, duplicate ports, owned-child cleanup and dead-child readiness. |
| Frontend interaction/client tests | **23 passed**. |
| Frontend lint | Passed. |
| Next.js production build | Passed using the webpack build script. |
| Separate-process HTTP verification | **8 checks passed**; see [live-http.json](verification/live-http.json). |
| Independent constructed evaluation | **312 terminal incidents**, eight seeds, four channels; full false-positive and false-negative results in [evaluation](OPERATIONS_EVALUATION.md). |

## Live workflow

The launcher started three separate services on loopback: bank simulator 8002, operational API 8001 and Next.js console 3000. The HTTP verification authenticated with a local demo analyst, created a case, obtained an acknowledged restriction, proved a later payment declined, reversed the verdict, obtained an acknowledged release, and proved a later payment posted. It also checked all channels, exact-duplicate count stability, JSON/PDF verdict consistency, authenticated event streaming and channel/overall count reconciliation. The recorded counts are a point-in-time snapshot, not fixed expected totals during playback.

The rendered interface was checked at a 1280 × 720 desktop viewport. An analyst entered a rationale and confirmed simulated case `CASE-FB7B4407F436`, which became Resolved / Fraud with an attributed timeline event. The analyst then documented a false-positive reversal: the interface first showed Release pending / Investigating, then Release confirmed / Resolved after bank acknowledgement. This demonstrates the distinction between a request and its confirmed effect.

The responsive overview was also inspected inside a 390-pixel-wide browser iframe. Navigation scrolls horizontally and metrics stack into two columns. This checks responsive CSS, not a physical-device or browser-matrix certification. Screenshots: [desktop overview](history/screenshots/overview.png), [resolved case](history/screenshots/case-reversal.png), [mobile viewport](history/screenshots/mobile.png). The temporary QA wrapper was removed from the deliverable.

## Regression review

Independent integration review identified four material issues, each corrected and covered by regression checks:

- Contradictory verdict changes while a false-positive release was pending: decisions now lock during and after that release.
- Evidence edges attributed related payments to the wrong account: graph construction now uses each payment's actual account reference.
- Public defaults usable outside demo mode: non-demo startup now rejects public demo accounts and weak/default signing or bank keys; public signup is disabled.
- Interrupted initial seeding could duplicate generated fixtures: a durable baseline plan now preserves IDs and timestamps for idempotent resume.

## Reproduce

Use the installation and verification commands in [README.md](../README.md). Stop Next dev before running a production build into the same `.next` directory. The HTTP proof requires the launcher to be running; it only accepts loopback services identifying themselves as the simulator. Runtime databases, signing keys, dependencies and intermediate logs are excluded from the source package.

## Limits

The production npm dependency audit returned zero advisories. Five high development-only advisory paths remain in the ESLint dependency chain; the checked dependency set has no compatible safe upstream fix. See [dependency details](../README.md#dependencies). This is not a complete security assessment.

Constructed fixtures, green tests and local bank enforcement do not establish real-bank integration, arbitrary-fraud detection, regulatory certification, or production readiness. The NPCI source retrieval is explicitly partial. Applicability and outstanding external controls are documented in [GUIDANCE.md](GUIDANCE.md).
