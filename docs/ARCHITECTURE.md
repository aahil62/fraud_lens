# Operational architecture

```mermaid
flowchart LR
  UI[Next.js console] -->|Bearer session| API[FastAPI /ops]
  API --> DB[(Operations SQLite)]
  DB --> Jobs[Durable delivery jobs]
  Jobs -->|Key / HTTP| Bank[Separate bank simulator]
  Bank --> Ledger[(Bank SQLite)]
  Bank -->|Acknowledgement / reconciliation| API
  API -->|Persisted audit cursor / SSE| UI
  Input[Synthetic playback / validated input] --> API
  API --> Signals[History-aware signals + channel policy]
  Signals --> DB
```

## Payments and protection

Unique input IDs and canonical fingerprints enforce idempotency. Scoring receives previously observed events at or before the current timestamp, bounded to the latest 1,000 by event time. Ground-truth labels never enter inference. Serialized ingestion prevents concurrent requests from observing inconsistent histories.

Review score 0.5 opens a case; protective score 0.8 queues an account or instrument restriction. These are versioned showcase choices, not NPCI-prescribed limits. Attempts, cases, audit events and delivery jobs commit before bank calls.

Actions are delivered before payments. A case's payment cannot overtake unresolved protection. Stable action/payment IDs support retries and reconciliation after crash or uncertain acknowledgement. Failed requests back off; uncertainty remains pending until reconciled.

## Analyst decisions

Case status, verdict and bank-action state remain separate. Optimistic versions reject stale updates. Final verdicts require a rationale and record the authenticated actor.

A false positive supersedes retryable restriction jobs and requests case-owned release, including uncertain earlier delivery. Contradictory verdicts are blocked while release completes. Resolved fraud can be reversed to a false positive. One release never clears another case's restriction.

## Shared state and recovery

SQLite WAL and explicit transactions provide durable state. Counts and recent display windows are read in one transaction; overall counts include the whole database rather than only 200 displayed rows. Channel totals derive from the same records.

Authenticated fetch streaming publishes a monotonically increasing persisted audit cursor. The shared client rejects older snapshots and recovers after reconnect/focus. A 10-second reconciliation poll backs up the stream. Reports explicitly describe an as-of snapshot.

One API worker is supported. Application locking coordinates ingestion, decisions and delivery; production multi-worker leases, horizontal scale and bank-specific adapters require additional work.

## Separate bank ledger

The bank is a different process/database. It posts allowed payments once, durably declines restricted/insufficient-funds attempts, and owns per-case restrictions. Test modes reject requests or lose an acknowledgement after committing an action. Health identifies the service as simulated; banking endpoints require a key.

This does not implement genuine payment authentication, network authorization, credit-card settlement, KYC, statutory reporting or actual account freezes.


The simulator enforces this ladder; API permissions come from the shared analyst role table:

| Action | Requesting role | Reversal |
|---|---|---|
| Amount-specific lien | L1+ | L2+ may release this case's lien |
| Debit freeze | L2+ (or detector policy) | L2+ may record false positive and release this case's protection |
| Final account close | Supervisor, after confirmed fraud | Final in the simulator |

Balances and available balances are integer paise. Available = balance minus active liens.
Liens allow incoming credits, but block debits above available funds. Payments debit and credit
known active beneficiaries in one bank transaction; incoming payments to a closed beneficiary
are declined before any sender debit. Unknown beneficiaries represent external recipients.
Account status is persisted as active/closed; frozen is derived from restrictions. Existing
SQLite account tables migrate without resetting balances, and old payment payloads still replay.
Concurrent liens that exceed available funds return 409. Lien release preserves other cases'
holds. Closing a card-fraud case always targets its account; card restrictions remain distinct.
The operations outbox carries lien amounts and reconciles uncertain acknowledgements by action id.
A false-positive reversal releases both freezes and liens and resolves only after all releases
are confirmed. Once final closure is requested, contradictory verdicts are blocked pending reconciliation.
