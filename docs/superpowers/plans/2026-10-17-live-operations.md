# FraudLens live operations implementation plan

> Agentic workers: execute task-by-task with test-driven development and independent review. The user explicitly requested planning and complete implementation in this session.

**Goal:** A runnable four-channel fraud operations showcase with durable state, bank-enforced simulated protection, analyst decisions, and synchronized UI.

**Architecture:** Existing FastAPI/Next.js application, transactional SQLite operational store and outbox, separate SQLite-backed bank simulator, shared authenticated live snapshot. Keep legacy engine isolated from operational metrics.

**Tech stack:** Python 3.12+, FastAPI, Pydantic, sqlite3, httpx, existing scoring libraries; Next.js 16, React 19, TypeScript, Tailwind, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-17-live-operations.md`.

## Global constraints

- Four channels: `upi`, `net_banking`, `card`, `atm`; integer `amount_minor` in paise.
- Simulated banking clearly labelled; external bank API access deferred.
- One authoritative operational database and unique transaction/action identifiers.
- Authenticated operational reads/writes; no client-supplied analyst identities.
- Pending requests never displayed as confirmed restrictions; decisions survive restart.
- Restriction ownership is per case; one reversal cannot release other cases' protection.
- Preserve existing functionality as documented legacy; new UI uses only operational state.

## Review focus

- Duplicate input with changed payload returns conflict, without duplicate debit/case.
- Delayed or uncertain bank acknowledgement reconciles after restart.
- Concurrent analysts cannot overwrite decisions with stale versions.
- Two cases restricting one account remain protected when only one is reversed.
- Expired authentication, malformed money/timestamps, and disconnected UI fail clearly.

## Task 1: Baseline and shared interfaces

- [x] Install isolated Python and Node dependencies; run existing tests/lint/build and record baseline.
- [x] Freeze shared API contracts in `docs/OPERATIONS_API.md` before independent work.
- [x] Keep the isolated review clone as the deliverable on `codex/fraudlens-live-operations`.

## Task 2: Independent bank simulator

Files: create `fraudlens/bank_simulator/{__init__,main,app}.py`, `tests/test_bank_simulator.py`.

- [x] Write failing tests for transaction debit, restriction enforcement for four channels, case-owned release, duplicate/conflicting requests, persistence, failures, and key authentication.
- [x] Implement the documented `/bank` HTTP contract and separate SQLite ledger.
- [x] Run simulator tests and prove two-process HTTP integration.

## Task 3: Durable operational backend

Files: create `fraudlens/operations/{models,store,detector,service,scenarios}.py`, `fraudlens/api/routes/operations.py`; modify API lifespan/state and signing configuration; create `tests/test_operations*.py`.

- [x] Write failing lifecycle tests, including the five review-focus failures.
- [x] Implement ingestion, history-aware scoring, case creation, atomic events/outbox, bank delivery/reconciliation, optimistic decisions, snapshots, event streaming, reports, and scenario controls.
- [x] Run lifecycle tests plus existing backend regression suite; verify restart and count reconciliation.

## Task 4: Independent operational frontend

Files: create shared operations client/provider/components and replace console page implementations; update shell, landing, tokens, and responsive styles.

- [x] Build against `docs/OPERATIONS_API.md`; route every console view through the shared operational snapshot.
- [x] Add meaningful interaction tests for decisions, version conflicts, filter counts, disconnect recovery, and API errors.
- [x] Run frontend tests, lint, and production build; inspect desktop and mobile rendering.

## Task 5: Evaluation and reproducibility

Files: create scenario evaluation and local launch scripts, environment examples, CI, guidance matrix, and updated README.

- [x] Verify every channel's supported fraud scenario and matched benign controls; publish reproducible synthetic results with limitations.
- [x] Validate guidance sources and map each implemented control to tests; mark inaccessible/unverified requirements explicitly.
- [x] Exercise full incident through the rendered UI and two running backend services.
- [x] Independent review, fix material findings, rerun affected checks, and package source/patch plus verification record.
