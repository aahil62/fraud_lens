# FraudLens

Multi-channel fraud investigation with reversible protective actions and one consistent operational ledger.

FraudLens connects payment attempts, detection evidence, bank acknowledgements and analyst decisions for **UPI, net banking, card payments and ATM withdrawals**. This is a self-contained local showcase: transactions are synthetic and a separate bank simulator enforces restrictions on test accounts/instruments. No external bank integration or regulatory certification is claimed.

## Implemented workflow

- Continuous synthetic transactions and on-demand scenarios across all four channels.
- History-aware rule, velocity, behavioral, graph and reference-ML signals, plus versioned channel controls. Risk scores prioritize review; they are not calibrated fraud probabilities.
- Automatic protective requests for supported high-risk patterns; moderate scores create review cases without automatic restriction.
- A persistent bank simulator that posts permitted payments, declines restricted payments, and acknowledges restriction/release requests.
- Authenticated analyst investigation, escalation, fraud confirmation, and false-positive reversal, with rationale and optimistic case versions.
- Durable delivery and reconciliation after rejection, uncertain acknowledgement, retry, or restart. Restrictions belong to cases; reversing one preserves other cases' protection.
- One live snapshot powers dashboard counts, channel totals, investigations, evidence/network, bank actions, reports and audit history. Disconnects are visible; reconnect retrieves current persisted state.
- Timestamped JSON, Markdown and PDF reports. JSON/Markdown retain Unicode; PDF represents characters unsupported by its portable built-in font as reversible Unicode escapes.
- Source-linked guidance mapping, independent controlled scenario evaluation, a local launcher, pinned Python dependencies and CI.

## Run locally

Requires Python **3.12** and Node.js **24+**. From this checkout's root:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
npm --prefix frontend ci
.venv/bin/python scripts/dev.py
```

Open **http://127.0.0.1:3000**. Local demo accounts: `asharma` or `riyer`, password `fraudlens123`.

The launcher starts bank **8002**, API **8001**, and console **3000**, waits for readiness, and stops its own children on Ctrl-C. Occupied/conflicting ports produce an error; other processes are never killed. Copy `.env.example` to `.env` to change ports, storage or the internal simulator key. The launcher uses demo mode and disables the historical API.

SQLite databases and a random persistent session signing key live under ignored `var/`. Initial fixtures are seeded once into an empty operational database; interrupted seeding resumes stable IDs. Playback starts automatically on the first showcase launch. Pausing playback persists across restart; existing activity is retained.

## Demonstrate an incident

1. Open **Transactions**, select a channel and run a fraud scenario.
2. Open its investigation. Inspect reasons, signals, connections and the payment/action timeline.
3. Confirm fraud to retain protection, or mark a false positive with a rationale. Resolution of a false positive follows release acknowledgement.
4. Inspect **Bank actions**, **Audit trail** and **Overview**. All views reflect the same operational records.
5. Exercise bank rejection or timeout-after-commit. Failed/uncertain requests remain visible; retries reconcile the original action ID.

With the application running in another terminal, verify actual effects over HTTP:

```bash
.venv/bin/python scripts/verify_live.py
```

This proof restricts execution to loopback simulator services. It creates labelled test activity, proves that a later payment is declined while restricted, reverses the case, and proves that a later payment posts.

## Verify

```bash
# Stop Next dev before building into the same .next directory.
.venv/bin/python scripts/check.py

# Include the historical backend regression suite.
.venv/bin/python scripts/check.py --full

# Safe while the console is running.
.venv/bin/python scripts/check.py --skip-frontend

# Reproduce independent scenario evaluation.
.venv/bin/python -m fraudlens.evaluation.operations
```

See [verification](docs/VERIFICATION.md), [evaluation](docs/OPERATIONS_EVALUATION.md), and machine-readable evidence under [docs/verification](docs/verification/). Constructed scenarios establish behavior only within their stated boundaries, not real-bank detection accuracy or losses prevented.

## Structure

```text
fraudlens/operations/       Strict inputs, detector, SQLite, lifecycle/outbox, scenarios, reports
fraudlens/bank_simulator/   Separate FastAPI application and durable bank ledger
fraudlens/api/routes/operations.py
fraudlens/core/             Existing scoring, graph, authentication and historical components
fraudlens/evaluation/operations.py
frontend/components/operations/   Shared live state, investigations, controls and evidence
frontend/lib/operations.ts        Typed authenticated operational client
scripts/dev.py             Three-service local lifecycle
scripts/check.py           Verification and launcher checks
scripts/verify_live.py      Actual HTTP proof against the local simulator
tests/                     Operational tests and historical regressions
docs/                      Architecture, contracts, guidance, evaluation and evidence
```

## Boundaries

- Investigation status, analyst verdict and bank-action status are separate. Requested protection is never displayed as confirmed protection.
- Payment attempts, cases, delivery jobs and audit events commit transactionally. Duplicate IDs with different payloads return conflict.
- Operational reads, writes, streams and exports require verified analyst authentication. The bank requires its separate key. Supported deployment: one API worker for one local analyst team, not a multi-tenant service.
- Public demo credentials are local-only. Non-demo mode requires a strong explicit session key, rejects stored public demo accounts and default/weak bank keys, and disables public analyst signup. These guards do not establish production banking readiness.
- Use fictional references only. Never enter real account numbers, PANs, PINs, CVVs, credentials or customer data.
- Card restrictions affect a specific linked test instrument; account restrictions affect linked simulated debits. The simulator does not represent actual credit-card accounts or guarantee real-bank restriction scope.
- Formal customer notices, statutory fraud classification, settlement reconciliation, regulatory reporting and member-only certification are outside this implementation. Read [guidance applicability](docs/GUIDANCE.md).
- Scope, delivery ordering and restart behavior are explained in [architecture](docs/ARCHITECTURE.md).

## Dependencies

Next.js and its ESLint configuration were updated from 16.3.4 to **16.4.2**. The checked npm production dependency audit reports no advisories. Five high development-only advisory paths remain through the Next ESLint plugin's `fast-glob` → `micromatch` → `braces` chain ([GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm)). The checked dependency set has no safe same-major upstream fix; npm's suggested Next 14 configuration downgrade is incompatible. This limitation is recorded, not suppressed. Recheck before publishing.

## Historical implementation

The original benchmark, separate ULB model validation, Fraud DNA library, Copilot and legacy API remain in source for reference/regression. Their results are **not** evaluation results for this operational pipeline. Historical endpoints can be enabled explicitly using `FRAUDLENS_LEGACY_API=1` outside the launcher; their separate fixture dataset never supplies the new console's metrics. Historical team contributions remain in Git history.
