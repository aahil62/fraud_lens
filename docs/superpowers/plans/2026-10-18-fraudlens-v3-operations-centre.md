# FraudLens v3: Multi-Analyst Fraud Operations Centre — Implementation Plan

> **For agentic workers (Codex):** Implement task-by-task, in order. Each task ends with tests passing and a commit. Steps use checkbox (`- [ ]`) syntax. Do not skip the test steps. When a step names an exact value (threshold, role, label, copy), use it verbatim.

**Execution override (user, 2026-10-18):** All backend tests use stdlib `unittest`; adapt any remaining pytest commands accordingly. Approval gates remain mandatory.

**Goal:** Turn FraudLens into a real-time, multi-analyst fraud operations centre for an Indian bank: role hierarchy (L1 → L2 → Supervisor), case ownership and approvals, an enforcing bank server that can lien, freeze and close accounts, a 1930/NCRP complaint "golden hour" fund-trace workflow, a public attack console that injects realistic fraud live, and an AI agent that triages, drafts and acts within policy.

**Architecture:** Keep the existing three services (bank simulator :8002, FastAPI operations API :8001, Next.js console :3000) and the existing transactional SQLite ledger + outbox. Extend, do not rewrite. All new state lives in the existing operations/bank SQLite stores and is exposed through the existing `/ops/snapshot` + `/ops/events` live channel so every analyst sees the same state.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLite, stdlib unittest; Next.js 16 (webpack), React 19, TypeScript, vitest, @phosphor-icons/react, Mona Sans (already bundled); optional Ollama for LLM wording.

**Spec:** Agreed in conversation on 2026-10-18 (summarised in "Design decisions" below). Existing context: `CLAUDE-HANDOFF.md` (parent folder), `DESIGN.md`, `PRODUCT.md`, `docs/ARCHITECTURE.md`, `docs/OPERATIONS_API.md`, `docs/GUIDANCE.md`.

---

## Design decisions (fixed — do not re-decide)

1. **"Real time" = live, realistic attacks hitting a real, separately running bank service.** No real bank data. Fraud arrives from (a) the existing synthetic stream and (b) a public **Attack console** where anyone (e.g. a recruiter on their phone) launches a scam typology and watches the analysts' console react. Every screen keeps the existing "Simulation mode · fictional data" disclosure.
2. **Real-world anchor = India's cyber-fraud reporting flow.** A victim reports to the **1930 helpline / NCRP portal (cybercrime.gov.in, I4C's CFCFRMS)**; the bank must trace the money through mule accounts and **put a lien (hold) on the remaining funds quickly ("golden hour")**. FraudLens is the bank-side tool for that. Guidance claims must cite a source URL verified during implementation (Task 13); if a fact cannot be verified, write "modelled on" rather than asserting it.
3. **Enforcement ladder (bank actions):** `lien` (hold a specific amount) → `restrict` (debit freeze; existing) → `close` (account closed; supervisor only, after confirmed fraud). Releases exist for lien and restrict. Closure is final in the simulator.
4. **Role hierarchy:** `l1_analyst` (L1 Analyst), `l2_analyst` (L2 Senior Analyst), `supervisor` (Fraud Supervisor). Permission table in Task 1 is authoritative. Lower roles can **request approval** for actions above their level; a higher role approves or rejects.
5. **AI agent ("FraudLens Agent") reduces workload but never makes final verdicts.** It triages and prioritises, drafts case briefs and the NCRP/regulatory narrative, auto-assigns cases to online L1s, and auto-places liens during a 1930 trace (policy-permitted). It never confirms fraud, never releases, never closes. Every agent action is an audit event with actor `agent`.
6. **Deterministic first, LLM optional.** Briefs are produced by deterministic templates from case facts. If `FRAUDLENS_LLM=ollama` is set and Ollama responds within 6 s, the LLM may rewrite only the `summary` sentence. The demo must work fully without any LLM.
7. **Credit:** README states the project began as a team project and lists teammates from git history; this version is the author's solo rebuild.

## Global Constraints

- Currency is integer paise (`amount_minor`) everywhere. Never use floats for money. Display with `₹` and `en-IN` grouping.
- All new identifiers match the existing `Identifier` pattern `^[A-Za-z0-9_.:@-]+$`, max 80 chars.
- All write endpoints require `get_current_analyst` except the public attack endpoints in Task 6 (demo mode only, rate-limited).
- Investigation status, analyst verdict and bank-action status stay separate fields. A requested bank action is never shown as confirmed.
- Every state change writes an audit event via `store.event(...)` in the same transaction as the change.
- Backend tests: `.venv/bin/python -m unittest discover -s tests -v`. Frontend: `npm --prefix frontend run test`, `npm --prefix frontend run lint`, `cd frontend && npx tsc --noEmit`. All must pass at the end of every task.
- Never kill processes you did not start. Stop the owned Next dev server before `npm run build`.
- UI follows `DESIGN.md` tokens (canvas `#f5f7fb`, surface `#fff`, ink `#202635`, accent `#4058d5`, good `#207657`, bad `#b33e42`, warning `#976314`, panel radius 16px, control radius 9px). No new colour families except role chips defined in Task 9.
- Never enter or store real account numbers, card numbers, PINs, names of real customers. Demo people are fictional.
- No push, no deploy, no publishing without the user's explicit approval. Commit locally only until Task 16, where each push/deploy step asks first. Never handle the user's Hugging Face/GitHub tokens.
- Commit message style: conventional (`feat:`, `fix:`, `test:`, `docs:`), ending with the attribution line the user's tooling requires.

## Review Focus

1. **Concurrent analysts acting on one case** — two analysts claim or decide the same case at once. Expected: exactly one wins; the other gets HTTP 409 with the current owner/version. Test in Task 2.
2. **Role escalation via crafted requests** — an L1 posts `close_account` directly to the API. Expected: 403 with `required_role`, no bank job queued. Test in Task 2.
3. **Lien larger than available balance / funds already moved** — trace finds ₹50,000 but only ₹12,000 remains. Expected: lien for ₹12,000, hop marked `partially_recovered`, no negative balances. Test in Task 4.
4. **Payment to a closed or liened account** (credit side) — money sent *into* a closed mule account. Expected: declined `account_closed`; credits into a liened account still post (liens only block debits). Test in Task 3.
5. **Public attack endpoint abuse** — 50 rapid launches from one IP. Expected: 429 after 10 per 5 minutes; endpoint disabled (404) when `FRAUDLENS_MODE` is not `demo`. Test in Task 6.

---

## File map

Backend (create):
- `fraudlens/core/auth/roles.py` — roles, labels, permission table, `can()`.
- `fraudlens/operations/team.py` — presence, claim/assign, approvals.
- `fraudlens/operations/trace.py` — 1930 complaint intake + fund trace.
- `fraudlens/operations/agent.py` — triage priority, case brief, auto-assign, policy actions.
- `fraudlens/operations/attacks.py` — public attack typologies and status.
- `fraudlens/api/routes/public.py` — public attack routes.
- Tests: `tests/test_roles.py`, `tests/test_team.py`, `tests/test_bank_ladder.py`, `tests/test_trace.py`, `tests/test_attacks.py`, `tests/test_agent.py`, `tests/test_detector_typologies.py`.

Backend (modify): `fraudlens/models/schemas.py`, `fraudlens/core/auth/store.py`, `fraudlens/api/deps.py`, `fraudlens/api/main.py`, `fraudlens/api/routes/operations.py`, `fraudlens/operations/models.py`, `fraudlens/operations/service.py`, `fraudlens/operations/store.py`, `fraudlens/operations/scenarios.py`, `fraudlens/operations/detector.py`, `fraudlens/bank_simulator/app.py`, `fraudlens/evaluation/operations.py`, `fraudlens/operations/guidance.py`.

Frontend (create):
- `frontend/app/(console)/team/page.tsx` — team & approvals view.
- `frontend/app/attack/page.tsx` + `frontend/app/attack/attack.css` — public attack console.
- `frontend/components/operations/AgentBrief.tsx`, `FundTrail.tsx`, `TeamPresence.tsx`, `RoleChip.tsx`, `ApprovalPanel.tsx`.
- `frontend/components/landing/ArchitectureDiagram.tsx`, `GoldenHour.tsx`, `proof.ts`.
- Tests next to each component (`*.test.tsx`).

Frontend (modify): `frontend/lib/operations.ts`, `frontend/lib/auth.ts`, `frontend/components/ConsoleShell.tsx`, `frontend/components/operations/OperationsViews.tsx`, `CaseWorkspace.tsx`, `OperationsProvider.tsx`, `frontend/app/login/page.tsx`, `frontend/components/landing/LandingExperience.tsx`, `frontend/app/landing.css`, `frontend/app/workspace-views.css`, `frontend/next.config.ts`.

Deploy (create): `Dockerfile`, `.dockerignore`, `scripts/serve.py`, `deploy/hf-space/README.md`, `scripts/deploy_hf.sh`. Replace stale `render.yaml` (delete it).

---

### Task 0: Land the existing redesign as the baseline

**Files:** none new. Delete `frontend/public/qa-responsive.html`.

- [x] **Step 1:** Run all checks listed in Global Constraints. Expected: backend 330 tests run / 1 skipped; frontend 30 tests pass; lint and tsc clean. If anything fails, fix only that failure.
- [x] **Step 2:** Delete `frontend/public/qa-responsive.html`.
- [x] **Step 3:** Commit everything currently modified/untracked (the Codex UI overhaul, `docs/UI-REDESIGN.md`, `scrollcraft/`, screenshots) as `feat(ui): light workbench redesign and Three.js landing`.
- [x] **Step 4:** Create branch `feature/fraudlens-v3` from this commit. All later tasks commit here.

---

### Task 1: Analyst roles and permission table

**Files:**
- Create: `fraudlens/core/auth/roles.py`
- Modify: `fraudlens/models/schemas.py` (`AnalystAccount`, `AnalystProfile`, `SignupRequest` unchanged), `fraudlens/core/auth/store.py` (`_seed_accounts`, load migration, `create`)
- Test: `tests/test_roles.py`

**Interfaces:**
- Produces:
  - `Role = Literal["l1_analyst", "l2_analyst", "supervisor"]`
  - `ROLE_RANK: dict[Role, int] = {"l1_analyst": 1, "l2_analyst": 2, "supervisor": 3}`
  - `ROLE_LABEL: dict[Role, str] = {"l1_analyst": "L1 Analyst", "l2_analyst": "L2 Senior Analyst", "supervisor": "Fraud Supervisor"}`
  - `ACTION_MIN_ROLE: dict[str, Role]` (exact table below)
  - `def can(role: Role, action: str) -> bool`
  - `def required_role(action: str) -> Role`
  - `AnalystAccount.role: Role = "l1_analyst"`; `AnalystProfile.role: Role`

**Permission table (`ACTION_MIN_ROLE`):**

| action | min role |
|---|---|
| `claim` | l1_analyst |
| `investigate` | l1_analyst |
| `escalate` | l1_analyst |
| `place_lien` | l1_analyst |
| `release_lien` | l2_analyst |
| `restrict` | l2_analyst |
| `confirm_fraud` | l2_analyst |
| `false_positive` | l2_analyst |
| `assign` | l2_analyst |
| `approve_l2` | l2_analyst |
| `close_account` | supervisor |
| `file_ncrp_report` | supervisor |
| `approve_supervisor` | supervisor |
| `agent_settings` | supervisor |

**Seed accounts (demo mode only, password `fraudlens123`, all fictional):**

| username | display_name | role |
|---|---|---|
| `asharma` | A. Sharma | supervisor |
| `riyer` | R. Iyer | l2_analyst |
| `kmehta` | K. Mehta | l1_analyst |
| `pnair` | P. Nair | l1_analyst |

- [x] **Step 1: Write failing tests** in `tests/test_roles.py`:
  - `test_can_respects_rank`: `can("l1_analyst","place_lien") is True`; `can("l1_analyst","restrict") is False`; `can("l2_analyst","close_account") is False`; `can("supervisor","close_account") is True`.
  - `test_unknown_action_is_denied`: `can("supervisor","drop_tables") is False`.
  - `test_seed_roles`: with `FRAUDLENS_MODE=demo` and a temp store path, `store.get("asharma").role == "supervisor"`, `store.get("kmehta").role == "l1_analyst"`.
  - `test_legacy_json_without_role_loads_as_l1`: write a JSON file containing one account without `role`, load store, assert role `l1_analyst` (except seeded usernames, which keep the table role).
  - `test_signup_creates_l1`: `store.create("newbie","N. Ewbie","pw12345678").role == "l1_analyst"`.
- [x] **Step 2:** Run `.venv/bin/python -m pytest tests/test_roles.py -v`. Expected: FAIL (module missing).
- [x] **Step 3:** Implement `roles.py`; add `role` to the schemas; in the store, add missing seed accounts on load (do not duplicate existing ones) and set seeded accounts' roles from the table.
- [x] **Step 4:** Make `/auth/login`, `/auth/me` (or whichever endpoint returns the profile) include `role`. Update `frontend/lib/auth.ts` `AnalystProfile` type with `role: "l1_analyst" | "l2_analyst" | "supervisor"`.
- [x] **Step 5:** Run the full backend suite. Expected: all pass.
- [x] **Step 6:** Commit `feat(auth): analyst role hierarchy and permission table`.

---

### Task 2: Case ownership, presence and approvals

**Files:**
- Create: `fraudlens/operations/team.py`
- Modify: `fraudlens/operations/store.py` (new table), `fraudlens/operations/service.py` (`decide`, `snapshot`), `fraudlens/operations/models.py`, `fraudlens/api/routes/operations.py`
- Test: `tests/test_team.py`

**Interfaces:**
- Consumes: `can`, `required_role`, `Role`, `ROLE_LABEL` (Task 1); `AnalystProfile.role`.
- Produces:
  - New SQLite table: `CREATE TABLE IF NOT EXISTS presence (username TEXT PRIMARY KEY, display_name TEXT NOT NULL, role TEXT NOT NULL, last_seen TEXT NOT NULL, current_case_id TEXT)`.
  - Case JSON gains: `assignee: str | None`, `assigned_at: str | None`, `pending_approval: dict | None` with keys `{approval_id, action, requested_by, required_role, notes, requested_at}`, and derived `handled_by: list[str]` (distinct non-system actors from that case's events, in order).
  - Models: `ClaimInput{expected_version:int}`, `AssignInput{username:Identifier, expected_version:int}`, `ApprovalRequestInput{action: Literal["restrict","confirm_fraud","false_positive","close_account","file_ncrp_report","release_lien"], expected_version:int, notes:str (required, 1..3000)}`, `ApprovalDecisionInput{approve: bool, notes: str (required when approve is False)}`.
  - `OperationsService.claim(case_id, request, actor: AnalystProfile) -> dict`
  - `OperationsService.assign(case_id, request, actor) -> dict`
  - `OperationsService.request_approval(case_id, request, actor) -> dict`
  - `OperationsService.decide_approval(case_id, request, actor) -> dict`
  - `OperationsService.heartbeat(actor, current_case_id: str | None) -> None`
  - Snapshot gains `team: list[{username, display_name, role, role_label, online: bool, last_seen, current_case_id, open_assigned: int, resolved_today: int}]` (online = `last_seen` within 45 s) and `approvals: list[pending approvals across cases]`.
  - Routes (all authenticated): `POST /ops/cases/{id}/claim`, `POST /ops/cases/{id}/assign`, `POST /ops/cases/{id}/approval-request`, `POST /ops/cases/{id}/approval`, `POST /ops/presence/heartbeat` body `{current_case_id: str | null}`.
- Rules:
  - `decide()` now checks `can(actor.role, action)`; if false → HTTP 403 `{"detail": "...", "required_role": "<role>"}`. Map existing decision actions: `investigate`→`investigate`, `escalate`→`escalate`, `confirm_fraud`→`confirm_fraud`, `false_positive`→`false_positive`.
  - Claim: allowed if unassigned or already yours. If assigned to someone else → 409 `{"detail":"Case is assigned to <display_name>", "assignee": ...}`. Version check uses existing optimistic `expected_version` → 409 on mismatch.
  - Assign requires `assign` permission and the target user must exist.
  - Approval request: only one pending approval per case (409 otherwise). Requester must NOT already have permission (400 "You can perform this action directly").
  - Approval decision: approver needs `can(approver.role, action)` and must not be the requester (403). Approve executes the action as the approver, audit message names both: "Approved by R. Iyer (requested by K. Mehta)". Reject clears `pending_approval` and records notes.
  - Login and logout record audit events `analyst_signed_in` / `analyst_signed_out` (add a `POST /auth/logout` that records the event; frontend calls it from the account menu).

- [x] **Step 1: Write failing tests** in `tests/test_team.py` (use the existing service fixtures/pattern from `tests/test_operations.py`):
  - `test_l1_cannot_confirm_fraud_directly` → 403 with `required_role == "l2_analyst"`, no action job queued, case version unchanged.
  - `test_l1_requests_approval_l2_approves`: L1 requests `confirm_fraud` with notes; L2 approves; case verdict `fraud`; audit contains requester and approver names.
  - `test_requester_cannot_approve_own_request` → 403.
  - `test_close_account_requires_supervisor`: L2 approval of a `close_account` request → 403; supervisor approval → bank `close` job queued.
  - `test_concurrent_claims_one_wins`: two claims with the same `expected_version` → first 200, second 409.
  - `test_claim_assigned_to_other_is_409`.
  - `test_presence_online_window`: heartbeat at t, snapshot at t+44 s online True, at t+46 s False (inject clock).
  - `test_handled_by_lists_distinct_actors_in_order`.
- [x] **Step 2:** Run tests → FAIL.
- [x] **Step 3:** Implement `team.py` helpers and the service methods; add routes; extend snapshot.
- [x] **Step 4:** Run full suite → PASS. Update `docs/OPERATIONS_API.md` with the five routes and the 403/409 shapes.
- [x] **Step 5:** Commit `feat(ops): case ownership, presence and approval workflow`.

---

### Task 3: Bank enforcement ladder — lien, credit posting, close

**Files:**
- Modify: `fraudlens/bank_simulator/app.py`, `fraudlens/operations/service.py` (`_queue_action`, `_deliver_action`, `_refresh_bank`), `frontend/lib/operations.ts` (`BankAction` type)
- Test: `tests/test_bank_ladder.py`

**Interfaces:**
- Bank DB additions:
  - `CREATE TABLE IF NOT EXISTS liens (lien_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, account_id TEXT NOT NULL, amount_minor INTEGER NOT NULL CHECK (amount_minor > 0), created_at TEXT NOT NULL)`
  - `ALTER`-safe: `accounts.status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','closed'))` (add via `PRAGMA table_info` check + `ALTER TABLE` for existing DBs).
- `ActionInput.operation: Literal["restrict", "release", "lien", "lien_release", "close"]`; new optional `amount_minor: int | None` (required and > 0 when `operation == "lien"`; forbidden otherwise; `target_type` must be `account` for lien/lien_release/close).
- Payment rules (in this order):
  1. Debit account `status == 'closed'` → declined `account_closed`.
  2. Account restricted → `account_restricted` (existing). Card restricted → `card_restricted` (existing).
  3. `available = balance - sum(liens on account)`; `amount > available` → declined `lien_hold` if liens exist and `amount <= balance`, else `insufficient_funds`.
  4. Post debit. **Then credit:** if `beneficiary_id` is an existing account in `accounts` with status `active`, add `amount_minor` to its balance. If the beneficiary account is `closed`, the whole payment is declined `beneficiary_closed` (no debit).
- `GET /accounts` returns per account: `account_id, balance_minor, available_minor, status ('active'|'frozen'|'closed'), liens: [{lien_id, case_id, amount_minor}]` (`frozen` = active with a restriction).
- Ops service: `BankAction.operation` widened to the same five values; `amount_minor` carried on lien actions; snapshot `accounts` view includes `available_minor`, `status`, `liens`.

- [x] **Step 1: Write failing tests** in `tests/test_bank_ladder.py` using `create_app(tmp_path/...)` + FastAPI `TestClient`:
  - `test_lien_blocks_debit_above_available` (balance ₹10,000, lien ₹8,000, debit ₹3,000 → declined `lien_hold`; debit ₹1,500 → posted).
  - `test_lien_release_restores_available`.
  - `test_credit_posts_to_known_beneficiary` (A→B ₹2,000; B balance +200000 paise).
  - `test_credit_into_liened_account_posts`.
  - `test_close_blocks_debits_and_incoming` (debit → `account_closed`; payment into it → `beneficiary_closed`, sender not debited).
  - `test_lien_requires_amount` (422) and `test_close_requires_account_target` (422).
  - `test_action_idempotent_same_id` (existing guarantee preserved for new operations).
- [x] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run full suite → PASS.
- [x] **Step 5:** Update `docs/ARCHITECTURE.md` "bank" section with the ladder table: lien (L1, reversible by L2) → debit freeze (L2) → close (Supervisor, final).
- [x] **Step 6:** Commit `feat(bank): lien, credit posting and account closure`.

---

### Task 4: 1930 / NCRP complaint intake and golden-hour fund trace

**Files:**
- Create: `fraudlens/operations/trace.py`
- Modify: `fraudlens/operations/models.py`, `fraudlens/operations/service.py`, `fraudlens/api/routes/operations.py`, `fraudlens/operations/reports.py`
- Test: `tests/test_trace.py`

**Interfaces:**
- `ComplaintInput{complaint_id: str pattern r"^NCRP-[0-9]{6,14}$", source: Literal["1930_helpline","ncrp_portal","branch"], victim_account_id: Identifier, reported_txn_id: Identifier, reported_at: datetime (tz required)}`.
- `TraceHop` dict: `{hop: int (1-based), account_id, inbound_txn_ids: list[str], traced_minor: int, available_minor: int, lien_minor: int, outcome: Literal["held","partially_recovered","funds_moved","account_closed"]}`.
- `def trace_funds(transactions: list[dict], reported_txn: dict, *, max_hops: int = 4, window_hours: int = 24) -> list[TraceHop-without-bank-fields]` — **pure function**, algorithm:
  1. Start: `frontier = {reported_txn.beneficiary_id: reported_txn.amount_minor}`, `t0 = reported_txn.timestamp`.
  2. For hop in 1..max_hops: for each account in frontier, take that account's *posted* outgoing transactions with `timestamp >= t0` and `< t0 + window_hours`, in time order; attribute traced money FIFO (each outgoing txn takes `min(remaining_traced, txn.amount)`); attributed amounts go to the next frontier keyed by that txn's `beneficiary_id`. Money not moved out stays as `traced_minor` at this hop. ATM/card cash-outs have no beneficiary: mark that portion `funds_moved`.
  3. Stop when frontier empty. Accounts reached by multiple paths are merged (sum).
- `OperationsService.file_complaint(request, actor) -> dict`:
  - 404 if `reported_txn_id` unknown; 409 if complaint_id exists with a different payload; idempotent for identical payload.
  - Creates a case with `case_type: "complaint"`, `complaint: {...}`, `trace: [TraceHop...]`, linked to the reported transaction.
  - For each hop where the bank reports `available_minor > 0`: queue `lien` for `min(traced_minor, available_minor)` with actor `agent` (policy: "Golden-hour lien on traced funds"). Outcome `held` if lien == traced, `partially_recovered` if 0 < lien < traced, `funds_moved` if 0.
  - Snapshot/case detail expose `trace` and totals: `traced_total_minor`, `held_total_minor`.
- Routes: `POST /ops/complaints` (any analyst role), `GET /ops/cases/{id}` already returns trace.
- Report: case report (JSON/Markdown/PDF) gains a "Fund trail" section listing hops and amounts held.

- [x] **Step 1: Write failing tests** in `tests/test_trace.py`:
  - `test_single_hop_full_hold`: victim → M1 ₹50,000, M1 untouched → hop1 traced 5_000_000, lien 5_000_000, outcome `held`.
  - `test_fan_out_two_hops_fifo`: victim → M1 ₹50,000; M1 → M2 ₹30,000; M1 → M3 ₹15,000 → hop1 M1 traced 500_000 (remaining), hop2 M2 3_000_000, M3 1_500_000.
  - `test_atm_cashout_marks_funds_moved`: M1 withdraws ₹20,000 at ATM → that portion counted as `funds_moved`, not a hop.
  - `test_partial_recovery_when_balance_spent` (bank available lower than traced).
  - `test_window_excludes_old_transactions` (outgoing 25 h later ignored).
  - `test_complaint_idempotent_and_conflict`.
  - `test_agent_liens_are_audited_with_actor_agent`.
- [x] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Full suite → PASS.
- [x] **Step 5:** Commit `feat(ops): 1930/NCRP complaint intake and golden-hour fund trace`.

---


**User clarification (2026-10-18, authoritative):** On complaint cases, the victim's account can never be a close, restrict or lien target; return HTTP 400 `"This is the complainant's account."`. Decision and approval inputs carry optional `target_account_id`, retained through approval and the outbox. Only traced non-victim accounts may be targeted; default to the first-hop recipient. Supervisor closure is offered per hop with its account reference explicit and audited per account, still requiring confirmed fraud. Multiple different traced mule accounts can close independently. Add tests for victim rejection, hop-2 closure leaving hop 1 untouched, and untraced-target rejection. Traced money returned to the victim is never liened.

### Task 5: Realistic fraud typologies in detector and scenarios

**Files:**
- Modify: `fraudlens/operations/scenarios.py`, `fraudlens/operations/detector.py`, `fraudlens/operations/models.py` (`ScenarioInput.scenario`)
- Test: `tests/test_detector_typologies.py`

**Interfaces:**
- `ScenarioInput.scenario` adds: `"mule_layering"`, `"sim_swap_takeover"`, `"card_testing"`, `"atm_cashout"`. `channel` stays required but is ignored for typologies that define their own channels (document in docstring).
- `scenario_transactions(channel, scenario) -> list[TransactionInput-compatible dict]` returns, per typology (all IDs fictional, prefix `SIM-`; timestamps spaced as stated from "now"):
  - `mule_layering`: victim UPI ₹48,000 to new beneficiary M1 (t0); M1 → M2 ₹30,000 (t0+3 min, net banking, new beneficiary); M1 → M3 ₹15,000 (t0+4 min, UPI); M2 ATM withdrawal ₹20,000 (t0+9 min, instrument linked to M2). Seed balances so all post unless blocked.
  - `sim_swap_takeover`: 3 failed auth attempts then net-banking transfer ₹1,85,000 from new device to new beneficiary.
  - `card_testing`: 6 card payments ₹49–₹199 at 6 different merchants within 6 min, then ₹18,500 card payment.
  - `atm_cashout`: 4 ATM withdrawals ₹10,000 each across 3 terminal device_ids within 12 min.
- Detector new reason rules (add to `detect`, keep existing ones; each returns a human reason string and a score):
  - **Mule pass-through:** account received a credit and sends ≥ 80% of it out within 15 min to a new beneficiary → score 0.86, reason "Pass-through: received ₹X and moved Y% out within 15 minutes to a new beneficiary."
  - **Card testing:** ≥ 5 card payments < ₹200 (20,000 paise) on the same instrument within 10 min, then any payment > ₹5,000 → 0.91.
  - **SIM-swap takeover:** `new_device` and `failed_auth_attempts >= 3` and `new_beneficiary` → 0.92.
  - **ATM burst across terminals:** ≥ 3 ATM withdrawals on one instrument across ≥ 2 device_ids within 15 min → 0.88.
- Thresholds stay: review ≥ 0.5, automatic protection ≥ 0.8 (existing `showcase-policy`); bump policy version string to `showcase-policy-1.2`.

- [x] **Step 1: Write failing tests**: one test per typology asserting (a) the final fraudulent attempt scores ≥ 0.8, (b) the reason text contains the rule's key phrase, (c) a benign control (same shape, known beneficiary / known device / single small card payment) scores < 0.5.
- [x] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Full suite → PASS (update any old test whose expected policy string changed).
- [x] **Step 5:** Commit `feat(detector): mule, SIM-swap, card-testing and ATM cash-out typologies`.

---


**Execution clarification:** The fixed mule sequence's final ATM leg moves only 66.7% of M2's incoming credit. Assert the pass-through signal on M1's last outgoing attempt (93.75%), preserving the specified amounts and later cash-out. Provision fictional recipients with zero balances through authenticated demo-only bank seeding before sequential ingestion; seed replay must not reset balances.

### Task 6: Public attack console API

**Files:**
- Create: `fraudlens/operations/attacks.py`, `fraudlens/api/routes/public.py`
- Modify: `fraudlens/api/main.py` (include router only when `FRAUDLENS_MODE == "demo"`)
- Test: `tests/test_attacks.py`

**Interfaces:**
- `POST /public/attacks` body `{typology: Literal["mule_layering","sim_swap_takeover","card_testing","atm_cashout"], victim_amount_minor: int (100_000..20_000_000, only used by mule_layering; others use fixed amounts)}` → `{attack_id: "ATK-<12 hex>", status_url}`. Runs the scenario through `run_scenario` with actor `attack-simulator`.
- `GET /public/attacks/{attack_id}` → `{attack_id, typology, steps: [{label, status: "pending"|"done"|"blocked", at}], outcome: "in_progress"|"caught"|"partially_caught"|"missed", case_id_masked}` where steps are, in order: "Scam payment sent", "FraudLens flagged it", "Bank protection requested", "Bank confirmed protection", "Analyst picked it up", "Verdict recorded". Derived from the real ledger. `case_id_masked` shows last 4 chars only. No balances, no analyst names.
- `POST /public/attacks/{attack_id}/report-1930` → files a complaint (Task 4) with `source: "1930_helpline"`, complaint id `NCRP-<14 digits from time>`; only valid for `mule_layering`; idempotent.
- Rate limit: in-memory per client IP, 10 POSTs per rolling 5 minutes → 429 `{"detail":"Too many simulated attacks. Try again in a few minutes."}`.
- Router not mounted outside demo mode (requests → 404).

- [x] **Step 1: Write failing tests**: launch each typology → 200 and `GET` eventually shows "FraudLens flagged it" `done` after `service.process_jobs()`; 11th launch from same IP → 429; non-demo app → 404; response JSON contains no key named `display_name`, `balance_minor` or full `case_id`.
- [x] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** PASS. **Step 5:** Commit `feat(api): public attack console endpoints (demo only)`.

---

### Task 7: FraudLens Agent — triage, briefs, auto-assign

**Files:**
- Create: `fraudlens/operations/agent.py`
- Modify: `fraudlens/operations/service.py` (call agent after case creation; snapshot fields), `fraudlens/api/routes/operations.py`
- Test: `tests/test_agent.py`

**Interfaces:**
- `def priority(case: dict, now: datetime) -> tuple[int, str]` → `(0..100, reason)`. Formula (round to int, cap 100): `55*score + 15*min(1, amount_minor/10_000_000) + 10*min(1, age_minutes/60) + 20*(case_type == "complaint")`. Reason lists the top two contributing terms, e.g. "High risk score (0.92) · 1930 complaint".
- `def build_brief(case: dict, transactions: list[dict], actions: list[dict]) -> dict` → `{typology: str, summary: str, evidence: list[str] (max 5), recommended_action: Literal["place_lien","restrict","confirm_fraud","false_positive","close_account","investigate"], required_role: Role, required_role_label: str, confidence: Literal["low","medium","high"], next_steps: list[str] (max 4), ncrp_narrative: str, generated_by: "template"|"llm"}`.
  - Typology label map from detector reasons: "Mule pass-through", "Card testing", "SIM-swap account takeover", "ATM cash-out burst", "Velocity", "High-value new device", else "Unusual activity".
  - Recommendation rules (first match wins): complaint with untraced funds → `place_lien`; score ≥ 0.8 and no confirmed protection → `restrict`; confirmed protection and score ≥ 0.85 → `confirm_fraud`; verdict fraud and supervisor not yet acted → `close_account`; score < 0.5 → `false_positive`; else `investigate`.
  - Confidence: high if score ≥ 0.85, medium if ≥ 0.6, else low.
  - `ncrp_narrative`: fixed template: "On {date IST} at {time IST}, a {channel} payment of ₹{amount} from account {masked} to {masked beneficiary} was reported via {source}. FraudLens traced ₹{traced} across {n} account(s) and placed holds on ₹{held}. Case {case_id}." Non-complaint cases use the same template minus trace sentence.
- Optional LLM: `def polish_summary(summary: str, facts: dict) -> str` — only if `FRAUDLENS_LLM == "ollama"`; POST `http://127.0.0.1:11434/api/generate` with model `FRAUDLENS_LLM_MODEL` (default `qwen2.5:7b-instruct`), timeout 6 s; reject the LLM output if any rupee figure in it differs from figures in `facts`; on any failure return the template summary.
- `def auto_assign(cases: list[dict], team: list[dict]) -> list[tuple[case_id, username]]`: unassigned open cases, sorted by priority desc, to **online L1s** with the fewest open assigned cases (ties by username). Disabled unless setting `agent_auto_assign` is true (supervisor toggles it via `POST /ops/agent/settings {auto_assign: bool}`, requires `agent_settings`).
- Service: brief stored on the case and refreshed when the case changes; snapshot cases include `priority`, `priority_reason`; snapshot gains `agent: {auto_assign: bool, briefs_drafted: int, liens_placed: int, cases_auto_assigned: int, cases_triaged: int}` (real counts from events).
- Routes: `GET /ops/cases/{id}/brief`, `POST /ops/agent/settings`.

- [x] **Step 1: Write failing tests**: priority formula exact values for two hand-computed cases; recommendation table (one test per rule); narrative contains masked IDs only (no full account id); `polish_summary` with a fake LLM that changes "₹48,000" to "₹84,000" → template returned; `auto_assign` skips offline analysts and balances load; agent counters equal number of agent events.
- [x] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** PASS. **Step 5:** Commit `feat(agent): triage priority, case briefs and auto-assignment`.

---


**Complaint target rule (user clarification, Task 4):** The agent defaults recommendations to the first-hop recipient and includes `target_account_id` explicitly. It never recommends close/restrict/lien against the victim. Per-hop close controls in Task 9 let a supervisor select another traced mule; approval must retain that target. A confirmed-fraud verdict is still required for closure. Agent never executes closure itself.


**Execution clarification:** Check existing final verdicts before score recommendations, so confirmed fraud can reach per-account closure and an already-cleared alert is not offered a second verdict. A low detector score never by itself recommends clearing a victim complaint; use investigation after trace preparation. Optional wording is applied on authenticated brief read outside write locks, version-checked before storage; snapshots otherwise work fully from templates. `liens_placed` counts confirmed bank actions linked to agent request events, never unacknowledged requests. Default complaint target is the first eligible non-victim trace hop, skipping already-requested/closed targets.

### Task 8: Evaluation update for new typologies

**Files:** Modify `fraudlens/evaluation/operations.py`, regenerate `docs/verification/operations-evaluation.json`, update `docs/OPERATIONS_EVALUATION.md`.

- [x] **Step 1:** Add the four typologies (fraud + matching benign controls, 8 seeds each, same construction rules as existing corpus) to the evaluation corpus.
- [x] **Step 2:** Run `.venv/bin/python -m fraudlens.evaluation.operations`. Record new TP/FP/TN/FN, precision, recall at both thresholds.
- [x] **Step 3:** Rewrite the results table in `docs/OPERATIONS_EVALUATION.md` with the new numbers. Keep the "Evidence boundary" section. Do not round in a flattering direction; use 4 decimals as before.
- [x] **Step 4:** Add test `tests/test_evaluation_snapshot.py::test_docs_match_json` asserting the precision/recall numbers in the markdown table equal the JSON.
- [x] **Step 5:** Commit `test(eval): evaluate new typologies`.

**Execution note:** Each typology adds one fraud and one same-shape benign control per seed under its terminal channel (64 incidents; corpus 312 → 376). New fixtures are appended after the existing ones so existing incidents keep their random draws. Families are `typology_fraud` / `typology_control`.

---

### Task 9: Console — roles, presence, ownership, approvals, agent brief, fund trail

**Files:**
- Create: `frontend/components/operations/RoleChip.tsx`, `TeamPresence.tsx`, `AgentBrief.tsx`, `FundTrail.tsx`, `ApprovalPanel.tsx`, `frontend/app/(console)/team/page.tsx` + tests
- Modify: `frontend/lib/operations.ts` (types for every new snapshot/case field from Tasks 2–7 and client functions `claimCase`, `assignCase`, `requestApproval`, `decideApproval`, `heartbeat`, `fileComplaint`, `setAgentSettings`, `getBrief`), `ConsoleShell.tsx`, `OperationsViews.tsx`, `CaseWorkspace.tsx`, `OperationsProvider.tsx`, `workspace-views.css`, `globals.css`

**UI spec (exact):**
- **RoleChip:** pill, 5px radius, 11px/600 text. Colours: L1 `#edf0ff` bg / `#3046b8` text; L2 `#e8f4ee` / `#1d6a4e`; Supervisor `#fbf1e2` / `#7a4f0f`. Text = `ROLE_LABEL` short form: "L1", "L2", "Supervisor".
- **Header (ConsoleShell):** right side shows `TeamPresence` = up to 5 overlapping 28px initials avatars of online analysts (green 8px dot), tooltip "Name · Role · on CASE-…"; "+N" overflow. The account menu shows your RoleChip and a "Sign out" item that calls `POST /auth/logout` then clears session.
- **Heartbeat:** `OperationsProvider` sends `heartbeat(currentCaseId)` every 15 s while the tab is visible (use `document.visibilityState`), and immediately on case page mount/unmount.
- **Navigation:** add "Team" item (icon `UsersThree`) after "Investigations"; show a count badge of pending approvals the current user can decide.
- **Investigations list:** new columns "Priority" (number + 4px bar) and "Owner" (avatar + name or "Unassigned"); filters: All · Mine · Unassigned · Awaiting approval · Complaints. Default sort: priority desc. Row action "Claim" button for unassigned rows.
- **Case page (top to bottom in the main column):** (1) header with case id, typology, priority, RoleChip of required role, owner row "Assigned to K. Mehta · handled by K. Mehta, R. Iyer" with Claim/Reassign buttons; (2) **AgentBrief** card: label "FraudLens Agent", summary, evidence bullets, "Recommended: Place lien (L1)" with a primary button that runs that action (or "Request approval from L2" if the user lacks the role), confidence chip, next steps checklist, collapsible "Draft NCRP narrative" with a Copy button; (3) **FundTrail** (complaint cases only): horizontal chain of account nodes (victim → hops) connected by arrows labelled with amounts; each node shows traced/held amounts and an outcome badge (held = good, partially_recovered = warning, funds_moved = bad, account_closed = ink). On mobile it becomes a vertical list. (4) existing decision panel, but action buttons the user cannot perform are replaced by "Request approval" which opens **ApprovalPanel** (required notes textarea). (5) existing bank actions + timeline.
- **ApprovalPanel on case page for approvers:** when `pending_approval` exists and the user can decide it: banner "K. Mehta requests: Confirm fraud — <notes>" with Approve / Reject (reject requires notes).
- **Team page `/team`:** table of all analysts: avatar, name, RoleChip, online state, current case link, open assigned, resolved today. Below: "Approvals waiting for you" list. Supervisor-only card "Agent policy" with an Auto-assign switch (calls `setAgentSettings`) and the agent counters from the snapshot ("Briefs drafted", "Liens placed", "Cases auto-assigned", "Cases triaged").
- **Bank page:** account rows show status chip (Active/Frozen/Closed), available vs balance, liens list.
- **Errors:** 403 shows inline "This needs an L2 Senior Analyst. Request approval instead." 409 shows "K. Mehta already claimed this case." with Refresh.

- [x] **Step 1: Write failing vitest tests**: `RoleChip` renders correct label per role; `TeamPresence` shows only online analysts and "+2" overflow for 7; `AgentBrief` shows "Request approval from L2" for an L1 user when recommended action is `restrict`; `FundTrail` renders hops with amounts formatted `₹48,000` and outcome badge text; Investigations "Unassigned" filter hides assigned cases; `ApprovalPanel` reject button disabled until notes entered.
- [x] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run tests, lint, tsc → PASS.
- [x] **Step 5: Browser check** with all services running: open two browser profiles (or one normal + one private window), sign in as `kmehta` (L1) and `riyer` (L2). Launch a mule_layering scenario. Verify: both see the new case within 5 s; kmehta claims it; riyer sees "Assigned to K. Mehta"; kmehta requests confirm-fraud approval; riyer approves; both see verdict and audit. Save screenshots to `docs/screenshots/v3/` (`team.png`, `case-agent-brief.png`, `fund-trail.png`, `approval.png`).
- [x] **Step 6:** Commit `feat(console): team presence, ownership, approvals, agent brief and fund trail`.

**Execution notes:** (1) Queue filters and priority sort run server-side (`GET /ops/cases?view=…`, sorted by fresh priority) so paging stays correct; the client re-applies the same filter as a guard. (2) Two sessions were checked with two origins (`127.0.0.1:3000` as K. Mehta, `localhost:3000` as R. Iyer) because session storage is per origin. (3) Fund trail shows each hop's inbound payment total as a "Received" row inside the node instead of a text label on the arrow, which did not fit three hops in the main column. (4) Complaint briefs use the typology label "1930 victim complaint" instead of "Unusual activity". (5) The scenario picker gained the four Task 5 typologies so analysts can launch mule layering from the console. (6) Recommended actions that record a verdict or closure require a rationale field before the brief's button submits.

---

### Task 10: Login — one-click demo roles

**Files:** Modify `frontend/app/login/page.tsx`, `frontend/components/AuthFrame.tsx` (if needed). Test: `frontend/app/login/login.test.tsx`.

- [x] **Step 1: Failing test:** when `process.env.NEXT_PUBLIC_DEMO_MODE === "1"`, three buttons render: "Continue as L1 Analyst (K. Mehta)", "Continue as L2 Senior Analyst (R. Iyer)", "Continue as Fraud Supervisor (A. Sharma)"; clicking one calls `login("kmehta","fraudlens123")` (mock) and routes to `next`. When not demo, buttons absent.
- [x] **Step 2:** Implement; replace the "Explore the local demo" aside with these buttons plus one line: "Open two windows with different roles to see the hand-off live."
- [x] **Step 3:** Tests/lint/tsc pass. Commit `feat(auth): one-click demo role sign-in`.

**Execution note:** `scripts/dev.py` now sets `NEXT_PUBLIC_DEMO_MODE=1` (it already runs the API with `FRAUDLENS_MODE=demo`), so the local demo shows the role buttons. Outside demo mode the old credential hint is removed, not just hidden.

---

### Task 11: Public attack console page `/attack`

**Files:** Create `frontend/app/attack/page.tsx`, `frontend/app/attack/attack.css`, `frontend/lib/attacks.ts`, test `frontend/app/attack/attack.test.tsx`.

**UI spec:**
- Mobile-first single column (max-width 480px centred on desktop), dark charcoal page (`#171b24`) to read as "the attacker's side", white text, red accent `#e0565b` for the attacker, cobalt for FraudLens reactions.
- Header: "FraudLens · Attack console" + chip "Fictional money only".
- Step 1 "Pick a scam": four cards with icon, name, one-line real-world description:
  - Mule layering — "A victim is tricked into a UPI payment; the money hops through mule accounts and is withdrawn at an ATM."
  - SIM-swap takeover — "An attacker ports the victim's number, fails a few logins, then moves a large sum from a new device."
  - Card testing — "Small charges probe a stolen card before one big purchase."
  - ATM cash-out — "Rapid withdrawals across several ATMs on one card."
- Mule layering shows an amount slider ₹1,000–₹2,00,000 (step ₹1,000, default ₹48,000).
- Button "Launch attack". Then a live vertical timeline of the six steps from Task 6, polling `GET /public/attacks/{id}` every 1.5 s until outcome ≠ `in_progress` or 2 minutes. Each step animates from pending (grey) to done (cobalt check) or blocked (red shield). Respect `prefers-reduced-motion`.
- After mule layering completes: button "Report it to 1930 as the victim" → calls report endpoint → shows "Complaint NCRP-… filed. FraudLens traced ₹X and held ₹Y." (values from the status endpoint; extend Task 6 status payload with `traced_total_minor`, `held_total_minor` when a complaint exists).
- Footer: "Analysts are watching this live at /dashboard" with link to `/login`.
- 429 → friendly message from API.

- [x] **Step 1:** Failing tests: renders four typologies; slider only for mule layering; after mocked launch, timeline renders six steps; 429 message shown.
- [x] **Step 2:** Implement. **Step 3:** Tests/lint/tsc pass. Browser check at 390×844 and 1280×720; screenshot `docs/screenshots/v3/attack-mobile.png`.
- [x] **Step 4:** Commit `feat(attack): public attack console`.

**Execution notes:** The status payload already carried `traced_total_minor`/`held_total_minor` from Task 6, so no backend change was needed. An attack stays `in_progress` until an analyst records a verdict, so "Report it to 1930" appears once FraudLens has flagged the mule-layering attack (or polling has stopped) rather than waiting for a final outcome; polling restarts after the report so the held amount updates as bank liens confirm. `/attack` was added to the public paths in `frontend/proxy.ts`. Checked at 390×844 and 1280×720 (no horizontal overflow).

---

### Task 12: Landing page update

**Files:** Modify `LandingExperience.tsx`, `landing.css`; create `GoldenHour.tsx`, `ArchitectureDiagram.tsx`, `proof.ts`, test `frontend/components/landing/proof.test.ts`.

- [x] **Step 1:** Remove the `.fl-hero-imprint` "A clearer picture." element and its CSS (it overlaps the lens and reads as a rendering bug). Verify no section is blank after scrolling (screenshot every section at 1280×720; if any is blank because of a scroll-reveal start state, make content visible by default).
- [x] **Step 2:** Add section **"The golden hour"** (`GoldenHour.tsx`) after the hero: left copy — H2 "When a victim calls 1930, the clock starts." Body: "Money moves through mule accounts in minutes. FraudLens traces every hop and places holds on what's left — automatically — then hands the case to the right analyst." Right: an SVG animation of a payment travelling victim → M1 → M2 → ATM, with lock icons appearing on M1 and M2 (CSS animation, static under reduced motion). Label "Illustrative example · fictional accounts".
- [x] **Step 3:** Add section **"One team, clear authority"**: three columns L1 / L2 / Supervisor with RoleChips and what each can do (from the permission table, in plain words), plus a fourth column "FraudLens Agent — triages, drafts, holds funds within policy. Never decides."
- [x] **Step 4:** Add section **"How it's built"** with `ArchitectureDiagram.tsx` (inline SVG, responsive): Synthetic stream + Attack console → Detector (rules · velocity · behaviour · graph · reference ML) → Case ledger + outbox (SQLite, transactional) → Bank server (separate service: lien · freeze · close) → Live console (multi-analyst). Arrows labelled. Below it a proof strip from `proof.ts`: four numbers — channels covered (4), fraud typologies (count from scenarios), evaluation precision and recall at the automatic-protection threshold, backend test count. `proof.test.ts` reads `docs/verification/operations-evaluation.json` and asserts the precision/recall constants equal the JSON values (honesty guard). Test count is a constant updated in Task 15.
- [x] **Step 5:** Hero/close CTAs: primary "Open the operations centre" → `/login`; secondary "Launch a live attack" → `/attack`.
- [x] **Step 6:** Tests/lint/tsc pass; screenshots desktop + 390px. Commit `feat(landing): golden hour, team authority and architecture sections`.

**Execution notes:** No section was blank at 1280×720 or 390px (scroll-reveal is only used for decorative parallax). "Fraud typologies" in the proof strip counts the four named typologies a visitor can launch from `/attack`. Precision/recall are shown with four decimals (0.8462 / 0.8148), matching the evaluation, because two-decimal rounding would round precision up. The architecture diagram switches to a stacked list below 760px so its labels stay readable. The golden-hour loop also stops when the hero's "Pause 3D motion" control is pressed. Fixed a missing space in the hero note on mobile ("paymentto").

---

### Task 13: Guidance alignment (NPCI / RBI / I4C)

**Files:** Modify `fraudlens/operations/guidance.py`, `docs/GUIDANCE.md`; test existing guidance tests updated.

- [x] **Step 1:** Using a browser/web search, verify and record source URLs for: I4C Citizen Financial Cyber Fraud Reporting and Management System and the 1930 helpline; NCRP portal (cybercrime.gov.in); RBI Master Directions on Fraud Risk Management (2024) for commercial banks; NPCI UPI fraud/dispute handling circulars relevant to lien/hold or reporting; RBI guidance on customer liability for unauthorised electronic transactions (2017 circular). Record the exact title, issuer, date and URL for each.
- [x] **Step 2:** For each, add a guidance entry: `{source, url, what_it_requires (one sentence, paraphrased), how_fraudlens_models_it, not_covered}`. Only claim what the source says. If a URL could not be verified, label the entry "modelled on (unverified)".
- [x] **Step 3:** The "Controls & guidance" page lists these entries grouped by issuer. Tests pass. Commit `docs(guidance): map 1930/NCRP, RBI and NPCI requirements`.

**Verification record (2026-10-19):**
- I4C CFCFRMS + 1930 and NCRP: PIB (Ministry of Home Affairs), "Strengthening the mechanism to deal with cyber frauds", 6 Aug 2024, https://www.pib.gov.in/PressReleasePage.aspx?PRID=2042130 — read in the browser (WebFetch got 403). cybercrime.gov.in itself loaded but its landing text does not describe the system.
- RBI Master Directions on Fraud Risk Management in Commercial Banks (incl. RRBs) and AIFIs, RBI/DOS/2024-25/118, 15 Jul 2024, https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=12702. Note: RBI (Commercial Banks – Fraud Risk Management) Directions, 2026 (31 Jul 2026, id=13641) repeal existing FRM directions for commercial banks per its para 67; both are listed.
- RBI Customer Protection – Limiting Liability of Customers in Unauthorised Electronic Banking Transactions, RBI/2017-18/15, 6 Jul 2017, https://www.rbi.org.in/scripts/BS_CircularIndexDisplay.aspx?Id=11040.
- NPCI UPI lien/hold on fraud complaints: **not verified** (npci.org.in circular pages returned an error page; search found only secondary sources). Labelled "modelled on (unverified)".
- New entries live in `requirements` (new field) alongside the existing `references`; tested by `tests/test_guidance.py`.

---

### Task 14: Production container and hosted demo

**Files:** Create `Dockerfile`, `.dockerignore`, `scripts/serve.py`, `deploy/hf-space/README.md`, `scripts/deploy_hf.sh`; modify `frontend/next.config.ts`; delete `render.yaml`.

**Interfaces:**
- `next.config.ts`: `output: "standalone"`; `rewrites()` → `[{ source: "/backend/:path*", destination: "http://127.0.0.1:8001/:path*" }]`.
- Build-time env for the frontend in Docker: `NEXT_PUBLIC_API_BASE=/backend`, `NEXT_PUBLIC_DEMO_MODE=1`. Local dev keeps current defaults.
- `scripts/serve.py`: starts bank (127.0.0.1:8002), API (127.0.0.1:8001) and `node frontend/.next/standalone/server.js` on `0.0.0.0:$PORT` (default 7860), using the **same uvicorn commands and env vars as `scripts/dev.py`** with `FRAUDLENS_MODE=demo`, `FRAUDLENS_SEED_DEMO=1`, DBs under `/tmp/fraudlens`; waits for each health check; forwards SIGTERM to children; exits non-zero if any child dies.
- `Dockerfile`: stage 1 `node:24-slim` builds frontend (`npm ci && npm run build`, copy `public` and `.next/static` into standalone); stage 2 `python:3.12-slim`, `COPY --from=node:24-slim /usr/local/bin/node /usr/local/bin/node`, `pip install -r requirements.lock`, copy app + standalone build, `EXPOSE 7860`, `CMD ["python","scripts/serve.py"]`. Run as non-root user `app` (uid 1000; HF Spaces requirement).
- `deploy/hf-space/README.md` frontmatter: `title: FraudLens`, `sdk: docker`, `app_port: 7860`, `pinned: false`.
- `scripts/deploy_hf.sh SPACE_ID`: `git archive HEAD` into a temp dir, overwrite README with the HF one, push to `https://huggingface.co/spaces/$SPACE_ID`. The user creates the Space and runs `huggingface-cli login` themselves; the script never handles tokens.

- [x] **Step 1:** Implement. **Step 2:** If Docker is available: `docker build -t fraudlens .` then `docker run -p 7860:7860 fraudlens`; verify `curl -s localhost:7860/` returns 200, `curl -s localhost:7860/backend/health` returns 200, demo login works in a browser, `/attack` launches an attack. If Docker is not available, say so in the verification doc; do not claim it works.
- [x] **Step 3:** Commit `build: single-container production image and HF Spaces deploy script`. Deployment itself happens in Task 16.

**Execution notes (2026-10-19):** Docker Desktop was started locally; `docker build -t fraudlens .` succeeded (image 994 MB). In `docker run -p 7860:7860 fraudlens`: `/` 200, `/backend/health` 200 `{"status":"ok"}`, `/attack` 200; one-click L2 sign-in reached the dashboard with "System live" (event stream works through the `/backend` rewrite); a mule-layering attack via `/backend/public/attacks` reached "Bank confirmed protection", and its 1930 report traced ₹28,000 and held ₹28,000 after the liens confirmed. The container runs as uid 1000 (`app`). `docker kill -s TERM` exits 0 after stopping all three services; one `docker stop` while a browser held an open event stream exited 137. Fixes found while testing: `frontend/proxy.ts` must not gate `/backend/*` (the API authenticates itself), and `.dockerignore` excludes local-only `fraudlens/data/*.json` so the image matches a `git archive` build. `serve.py` also points the session key and analyst store at `/tmp/fraudlens`. `deploy_hf.sh` force-pushes a fresh one-commit repo built from `git archive HEAD`; HF git authentication must come from the user's own `huggingface-cli login`.

---

### Task 15: Final verification, docs, README, archives

- [x] **Step 1:** Run every check (backend full suite, frontend tests, lint, tsc, production build with dev server stopped). Record exact counts.
- [x] **Step 2:** Finish the open QA items from `CLAUDE-HANDOFF.md` (mobile drawer by keyboard, auth pages, dense tables scroll internally, contrast audit, reduced motion). Fix what fails.
- [x] **Step 3:** Capture final screenshots into `docs/screenshots/v3/` (landing hero, golden hour, dashboard, investigations, case with agent brief, fund trail, team, bank, attack mobile, login roles). Delete superseded `docs/screenshots/redesign/` images that are no longer referenced.
- [x] **Step 4:** Rewrite `README.md` in this order: one-line pitch; hero screenshot; "Why it matters" (1930/golden-hour problem in 3 sentences, with the verified source links from Task 13); "Try it" (hosted link placeholder + local run commands + demo roles table); "What it does" (bullets: multi-analyst roles & approvals, enforcing bank ladder, 1930 fund trace, attack console, agent, reports/audit); architecture diagram (mermaid mirroring Task 12); evaluation table (from JSON); "Engineering notes" (transactional outbox, idempotency, optimistic versions, reconciliation); "Limits" (collapsed `<details>`; keep honesty, shorter than before); "Credits" (team-project origin, teammates from git history, this version rebuilt solo).
- [x] **Step 5:** Update `docs/VERIFICATION.md` with a v3 section: actual commands, counts, what was browser-checked, what was not. Update the proof constant in `proof.ts` with the real backend test count.
- [x] **Step 6:** Commit `docs: v3 README, verification and screenshots`. Regenerate `../FraudLens-source.zip` (exclude `.venv`, `node_modules`, `.next`, `var/`, `work/`, `.env`) and `../FraudLens-implementation.patch` (from `2acb4d5`). Update `../START-HERE.md`.

**Execution notes:** `CLAUDE-HANDOFF.md` is not in this folder; its QA items were taken from the plan text (drawer keyboard, auth pages, internal table scroll, contrast, reduced motion) and results are in `docs/VERIFICATION.md`. Git history contains only the author's commits, so the README credits the team-project origin without naming teammates. The source zip and patch were written to `~/Projects/portfolio/`; `../START-HERE.md` does not exist there and was not created. The bank page now lists frozen, closed and liened accounts first.
- [ ] **Step 7:** Report to the user: what changed, check results, screenshots, and the exact commands for merge to `main`, push and HF deploy. Wait for their approval before any of those.

---

### Task 16: Deploy FraudLens publicly — needs the user's approval at each marked step

**Current state (verified 2026-10-18):** FraudLens is **not deployed anywhere**. The GitHub repo `aahil62/fraud_lens` has no homepage and no deployment records; `origin/main` is still the old commit `2acb4d5`. The stale `render.yaml` pointed CORS at `https://fraud-lens.vercel.app`, but that domain serves an **unrelated site** ("Traffic Checks & Actions") — it is not ours and must not be referenced anywhere. `https://fraudlens.vercel.app` also exists but ownership is unconfirmed; do not use or link it unless the user confirms it is theirs.

**Target:** one public URL (Hugging Face Space, Docker SDK, free CPU tier: 2 vCPU / 16 GB RAM, sleeps after ~48 h idle) serving landing, console, attack console and API from the Task 14 container, plus the GitHub repo pointing at it. Data is ephemeral and reseeded on every boot — state this on the landing footer and README ("Demo data resets when the server restarts").

- [x] **Step 1 (repo, no approval):** Make cold starts safe: `scripts/serve.py` seeds demo data on boot, starts the synthetic stream **paused at 1 transaction / 8 s** (not faster, to keep the public demo readable), and exposes `/backend/health` only after all three services are ready. Add `GET /backend/ops/public-status` (no auth) returning `{"ready": true, "mode": "demo", "started_at": ...}` for uptime checks. Test with `docker run` as in Task 14.
- [x] **Step 2 (repo, no approval):** Public-hardening for demo mode: rate-limit `/auth/login` to 20 attempts / 5 min per IP; disable `/auth/signup` when `FRAUDLENS_PUBLIC_DEMO=1` (set in the Dockerfile) so strangers cannot create accounts; demo accounts' passwords cannot be changed in demo mode; the bank simulator stays bound to `127.0.0.1` inside the container (never exposed). Tests for each.

**Execution notes (Steps 1–2, 2026-10-19):** `scripts/serve.py` deletes the previous boot's `bank.sqlite3*`, `operations.sqlite3*`, `analysts.json` and `session.key` in the data dir, so every boot (including `docker restart`) reseeds; it passes `FRAUDLENS_SIMULATION_RUNNING=0` and `FRAUDLENS_SIMULATION_INTERVAL=8`, which the API applies on first seed (`initial_simulation_config()`; local dev keeps running at 5 s). The stream runs one scenario per tick, so "1 transaction / 8 s" is one scenario every 8 s. `/backend/health` is served by the console proxy, which starts only after the bank and the API (whose lifespan seeds before serving) have passed their health checks, so a 200 implies all three are up. `GET /ops/public-status` lives on its own router (`public_status_router` in `routes/health.py`) because the `/ops` router has a router-level auth dependency; `ready` is true once the API lifespan has finished. Login is limited per client by `LoginLimiter` (20 attempts, successful or not, per 300 s; reset on API start). Behind the bundled Next proxy every request arrives from 127.0.0.1, so `client_ip()` uses the right-most `X-Forwarded-For` entry when the peer is loopback (Next keeps an incoming header and otherwise sets it to the socket peer); the same helper now keys the `/public/attacks` limit, which was otherwise one shared bucket for all visitors. On a directly exposed container a client can still pick its own `X-Forwarded-For`; on HF the platform proxy's appended address is expected to be right-most (not verified until Step 6). There is no password-change route, and signup cannot overwrite a demo account (409); a test pins both. The store still keeps an existing hash when it upgrades roles on load (Task 1 test), and the container wipes `analysts.json` on every boot. `FRAUDLENS_PUBLIC_DEMO=1` is set in the Dockerfile; signup then returns 403 "Sign-up is turned off on the public demo. Use a demo role on the sign-in page." (the signup page shows this message; the link on the login page is unchanged). Tests: `tests/test_public_demo.py` (12) and one in `tests/test_attacks.py`. Checks: backend **438 tests, OK, 1 skipped** (269 s); frontend 55 passed, lint and `tsc --noEmit` clean, production build passed. Container (`docker build -t fraudlens:task16 .`, `docker run -p 7861:7860`): health 200 after 6 s; public-status `{"ready":true,"mode":"demo",...}`; seeded 21 transactions / 4 cases with the stream paused at 8 s; signup 403; the 21st login attempt from one address 429 while another forwarded address got 401; the browser showed the 429 message, then after `docker restart` (data reset, back to 21/4) demo L2 sign-in reached "System live" and an `/attack` launch reached "Bank confirmed protection"; ports 8001/8002 accept connections on 127.0.0.1 only and only 7860 is published; uid 1000; `docker stop` exited 0. After reverting a store change (see above) the image was rebuilt and re-smoke-tested: health 200 after 5 s, public-status ready, signup 403, demo login 200, attack 200, `docker stop` exit 0.
**Combined-branch notes (2026-10-19):** Steps 1–2 were merged into `feature/fraudlens-v3` (merge commit `a98a028`) together with the open-stream shutdown fixes (`35a1834`, `0111f21`: uvicorn `--timeout-graceful-shutdown 1`; `72c6f8d`: stream cancellation at shutdown is not logged as an error, and the launcher's port probe tolerates TIME_WAIT and waits up to 5 s). Re-verified: 442 backend tests OK (1 skipped), 55 frontend tests, build, and the container (see `docs/VERIFICATION.md`). README credits: the author's project, begun as a hackathon project; teammates are not listed (user decision).

- [ ] **Step 3 (user approval — merge and push):** Ask: merge `feature/fraudlens-v3` into `main` and push to `origin`? Only after a clear yes: `git checkout main && git merge --no-ff feature/fraudlens-v3 && git push origin main`. Also push `codex/fraudlens-live-operations` only if the user wants that history on GitHub.
- [ ] **Step 4 (user does this):** Create a Hugging Face account if needed, create a new Space → SDK **Docker** → name `fraudlens` → visibility Public. Run `huggingface-cli login` locally (the user pastes their own token; Codex never sees or stores it).
- [ ] **Step 5 (user approval — deploy):** `scripts/deploy_hf.sh <hf-username>/fraudlens`. Watch the Space build logs until "Running". If the build fails, fix in the repo, commit, and redeploy (each redeploy needs the user's go-ahead).
- [ ] **Step 6 (verify live, no approval):** On `https://<hf-username>-fraudlens.hf.space`: landing loads with the 3D lens; `/backend/health` 200; sign in with each demo role button; open a second browser window as another role; launch a mule-layering attack from `/attack` on a 390px viewport; confirm both analyst windows show the case within 5 s, claim/approval hand-off works, the bank declines a later debit from the frozen account, and "Report it to 1930" produces a fund trail with liens. Screenshots to `docs/screenshots/v3/live-*.png`. Record cold-start time.
- [ ] **Step 7 (user approval — GitHub metadata):** `gh repo edit aahil62/fraud_lens --description "Real-time multi-analyst fraud operations centre for UPI, cards, net banking and ATMs — 1930 golden-hour fund tracing, enforcing bank simulator, AI triage" --homepage https://<hf-username>-fraudlens.hf.space --add-topic fraud-detection,upi,fintech,fastapi,nextjs,india`.
- [ ] **Step 8:** Update README "Try it" with the live URL and the demo roles table; note the ~1 minute cold start after idle. Commit `docs: live demo link` and push (approval required).
