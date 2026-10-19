# Operational API contract

All `/ops` routes require the existing `Authorization: Bearer <token>` session. `GET /ops/events?after=N` is a fetch-consumed SSE stream using the same header. JSON errors use FastAPI `detail`. Version conflict is HTTP 409. The new UI uses these endpoints exclusively; historical routes are not operational data.

## Shared shapes

Channel: `upi | net_banking | card | atm`. Currency is INR; integer `amount_minor` is paise. API timestamps are UTC ISO 8601.

Transaction: `{txn_id, account_id, channel, amount_minor, timestamp, instrument_id: string|null, beneficiary_id: string|null, merchant_id, device_id, ip_address, location, new_device: boolean, new_beneficiary: boolean, failed_auth_attempts: number, score: number, payment_status: "pending"|"posted"|"declined"|"failed", bank_reason: string|null, case_id: string|null}`.

Case: `{case_id, txn_id, account_id, channel, amount_minor, score, severity:"medium"|"high"|"critical", status:"new"|"investigating"|"escalated"|"resolved", verdict:"unreviewed"|"fraud"|"false_positive", version:number, created_at, updated_at, assigned_to:string|null, notes:string, signals:[{name,score,reasons:string[]}], reasons:string[], related_transactions:Transaction[], related_accounts:string[], actions:BankAction[], timeline:AuditEvent[]}`.

BankAction: `{action_id,case_id,operation:"restrict"|"release",target_type:"account"|"card",target_id,status:"pending"|"confirmed"|"failed"|"superseded",attempts:number,bank_reference:string|null,last_error:string|null,created_at,updated_at}`.

AuditEvent: `{id:number,event_type,case_id:string|null,txn_id:string|null,actor,message,occurred_at,metadata:object}`.

Snapshot: `{cursor:number,as_of:string,simulation:true,counts:{transactions:number,pending_payments:number,posted:number,declined:number,cases:number,pending_review:number,investigating:number,escalated:number,resolved:number,confirmed_fraud:number,false_positives:number,restricted_accounts:number,restricted_cards:number,pending_actions:number,failed_actions:number},channels:[{channel,transactions,cases,pending_review,confirmed_fraud,resolved,declined}],transactions:Transaction[],cases:Case[],actions:BankAction[],events:AuditEvent[],bank:{connected:boolean,mode:string,accounts:object[],last_error:string|null},simulation_state:{running:boolean,interval_seconds:number},detection:{version:string,coverage:object[]}}`.

`GET /ops/snapshot` returns snapshot. Bounded recent arrays (200 transactions/cases/actions/events); aggregate counts cover the entire database. `GET /ops/cases/{case_id}` returns full Case. `GET /ops/transactions?limit=50&offset=0&channel=upi` and `GET /ops/cases?limit=50&offset=0&status=new&channel=upi` return `{items:[],total:number}` for paging. `GET /ops/events?after=N` yields SSE `data: {cursor:N}` on change and periodic comments; fetch a fresh snapshot on connection/reconnection/cursor change. Cursor is monotonically increasing persisted audit id; server snapshots are consistent in one SQLite transaction.

`POST /ops/transactions` accepts Transaction input fields through `failed_auth_attempts` (all identity fields bounded). Required: txn_id,account_id,channel,amount_minor,timestamp. Defaults: merchant_id=`merchant-demo`, device_id=`device-known`, ip_address=`127.0.0.1`, location=`Pune`, new_device=false,new_beneficiary=false,failed_auth_attempts=0. Card/ATM require instrument_id. Returns `{transaction:Transaction,case:Case|null,duplicate:boolean}` (201 new / 200 exact replay / 409 conflicting id).

`POST /ops/cases/{case_id}/decision` body `{action:"investigate"|"escalate"|"confirm_fraud"|"false_positive",expected_version:number,notes:string}` returns updated Case. Notes required for confirm_fraud/false_positive. Actor from token. Conflict: fetch fresh case/snapshot. `POST /ops/actions/{action_id}/retry` returns BankAction. `GET /ops/cases/{case_id}/report?format=json|markdown|pdf` returns timestamped structured report / downloadable Markdown / PDF. `GET /ops/guidance` returns `{references:[{id,title,source_url,source_date,applicability,control,status,test_evidence:string[]}],disclaimer:string}`.

`POST /ops/simulation/scenario` body `{channel,scenario:"normal"|"fraud"|"false_positive"|"cross_channel"}` returns `{transactions:Transaction[],case_ids:string[]}`. A cross-channel scenario spans all four channels. Scenario labels are never detector features. `POST /ops/simulation/control` body `{running?:boolean,interval_seconds?:number,bank_mode?:"normal"|"reject"|"timeout_after_commit"}` returns Snapshot. `POST /ops/process` retries due durable jobs and returns Snapshot. Synthetic baseline is seeded once on an empty operations database; it is not re-created on restart.

## Separate bank simulator

Simulator runs on port 8002 by default. All `/bank` endpoints require `X-Bank-Key`; default local-only key `fraudlens-local-simulator`. `GET /health` public returns `{status:"ok",simulation:true}`. Default SQLite path comes from `FRAUDLENS_BANK_DB`; default data directory `var/`. No outbound banking calls.

`POST /bank/transactions` input `{txn_id,account_id,channel,amount_minor,instrument_id?:string|null}`. Test accounts are created lazily with 100000000 paise; return `{txn_id,status:"posted"|"declined",reason:string,balance_minor:number,bank_reference:string}`. Declines are persisted/idempotent too. Reuse of id with different payload returns 409. Account restrictions cover all linked test-account debits; card restrictions cover matching instrument only. Do not imply this models real credit-card accounts.

`POST /bank/actions` input `{action_id,case_id,operation:"restrict"|"release",target_type:"account"|"card",target_id}`; return `{action_id,status:"confirmed",restriction_active:boolean,bank_reference:string}`. `GET /bank/actions/{action_id}` same response or 404. Restrictions keyed by `(case_id,target_type,target_id)`; release removes only this case's restriction. Idempotent action ids, conflicting reuse returns 409.

`GET /bank/accounts` returns `{accounts:[{account_id,balance_minor,restricted:boolean,active_restrictions:number}],restrictions:[{case_id,target_type,target_id}]}`. `POST /bank/control` body `{mode:"normal"|"reject"|"timeout_after_commit"}` returns `{mode}`. `GET /bank/status` returns `{simulation:true,mode}`. Reject mode returns 503 for new mutating operations. Timeout-after-commit commits a new action then responds 504; retrieving/retrying the same id returns the committed acknowledgement. Existing idempotent results are returned even in failure mode.


## Roles, ownership and approvals (v3)

Profiles from `/auth/login`, `/auth/signup` and `/auth/me` include persisted `role`:
`l1_analyst`, `l2_analyst` or `supervisor`. Signup always creates L1; request bodies cannot elevate it.
Login/signup and authenticated `POST /auth/logout` record session audit events. Logout clears the
browser session; it does not revoke other browser sessions using the same demo account.

All routes below require a bearer token. Case mutations share one SQLite write transaction with
version updates, bank outbox jobs and audit records:

| Route | Body | Behavior |
|---|---|---|
| `POST /ops/cases/{id}/claim` | `{expected_version}` | Claim an unassigned case or retain your own claim |
| `POST /ops/cases/{id}/assign` | `{username,expected_version}` | L2+ assigns an existing analyst |
| `POST /ops/cases/{id}/approval-request` | `{action,expected_version,notes}` | Request a higher role; one pending request per case |
| `POST /ops/cases/{id}/approval` | `{approve,notes?}` | Authorized different analyst approves atomically or rejects with mandatory notes |
| `POST /ops/presence/heartbeat` | `{current_case_id:null|string}` | Presence is online for 45 seconds after the last heartbeat |

The decision endpoint also accepts `restrict`, `release_lien`, `close_account` and
`file_ncrp_report`; the central permission table is enforced before any mutation. Closure requires
an existing fraud verdict. Report recording is simulated and never files anything externally.
Bank liens and closure are enforced by the separate simulator; queued requests are not confirmed protection.

Insufficient role: **403** `{detail:string,required_role:"l2_analyst"|"supervisor"}`.
Stale version or competing claim: **409** `{detail:string,version:number,assignee:string|null}`.
Other conflicts (e.g. a pending approval) return `{detail:string}`. Rejecting or approving your own
request is forbidden. Rejected/failed approval execution leaves the case and outbox unchanged.

Cases add `assignee` (username), `assigned_at`, `pending_approval` (or null) and ordered distinct
`handled_by` usernames from human case audit events. `assigned_to` remains the display label.
Snapshots add `team` (role label, online, last seen, current case, open assigned, resolved today)
and `approvals` (pending request fields plus case_id). All events use the existing live cursor.


### Bank ladder payloads (v3)

`POST /bank/actions` accepts `restrict|release|lien|lien_release|close`. Lien requires a strict
positive integer `amount_minor`; other actions forbid that field. Lien/release-lien/close require
an account target. Liens are owned by case; replaying an action id cannot add another hold.
`GET /bank/accounts` adds `available_minor`, `status:active|frozen|closed`, and
`liens:[{lien_id,case_id,amount_minor}]`. Existing restriction fields remain available.
Payments accept optional `beneficiary_id`; known beneficiaries are credited atomically.
Closed-debit reason is `account_closed`; closed-beneficiary reason is `beneficiary_closed`.

Operational `place_lien` decisions require `amount_minor`; other decisions reject an amount.
Bank actions carry that amount through the durable outbox. Closure requests require supervisor
permission and a fraud verdict, target the account even for card/ATM cases, and remain pending
until the bank acknowledges them. Report recording remains simulation-only.


### Complaint intake, tracing and selected account targets (v3)

`POST /ops/complaints` accepts `{complaint_id:"NCRP-<6..14 digits>",source:"1930_helpline"|"ncrp_portal"|"branch",victim_account_id,reported_txn_id,reported_at}` (timezone required). The reported payment must be posted and belong to the victim. Identical complaint replay returns the same case; changed payload or another complaint for that payment returns 409. A prior detection case is reused to avoid duplicate investigations or holds.

Case detail adds `case_type:"complaint"`, `complaint`, `trace`, `default_target_account_id`, `traced_total_minor`, `held_total_minor`, `funds_moved_total_minor`. Each trace row has hop, account_id, inbound_txn_ids, traced_minor, moved_minor, available_minor, lien_minor, lien_status and outcome. A chronological FIFO pass attributes each posted outgoing payment once, after funds arrive, within 24 hours and at most four hops; cycles and converging paths cannot duplicate funds. Only confirmed, unreleased bank liens count as held. Pending/failed acknowledgements show outcome `pending` and their actual lien_status; returned funds show `returned_to_victim`, and released holds show `released`. Cash-outs are moved amounts on the sending hop, not invented bank accounts. Bank outages leave a durable complaint awaiting balance reconciliation; the worker prepares holds after reconnection.

Decision and approval-request bodies accept optional `target_account_id`. On complaint cases, close/restrict/place_lien must target a traced non-victim account. An explicit victim target returns **400** `{"detail":"This is the complainant's account."}`. Untraced targets return **400**. Omitting the target selects the first-hop recipient. The chosen target persists through approval into the bank action and its audit event. Close requires supervisor role and an existing fraud verdict; different traced accounts can close independently. The UI offers closure per fund-trail hop, shows its account reference explicitly, and the agent defaults its recommendation to the first-hop mule. The complainant is never automatically liened, including when traced money returns to their account. No external complaint is filed by this endpoint.


### Telemetry typologies (showcase-policy-1.2)

Scenario input also accepts `mule_layering`, `sim_swap_takeover`, `card_testing`, and `atm_cashout`.
These define their own channels; the required `channel` field is ignored for them. The detector
sees transaction/device/authentication/beneficiary telemetry, never the scenario name.
Mule scoring uses posted prior credits and cumulative posted outgoing transfers plus the current
attempt. Detection remains a suspicion signal; the current attempt may subsequently be declined.
The mule sequence flags M1's second outgoing transfer (93.75% attempted pass-through), before M2's
later ATM cash-out (66.7% of M2's incoming credit). It does not falsely label that ATM leg an 80% pass-through.

The API provisions fictional `SIM-` accounts through private, demo-only
`POST /bank/accounts/seed {accounts:[{account_id,balance_minor}]}` before executing new typologies.
The bank key is required; non-demo requests return 404. Existing account balances are never reset
by seed replay. Recipients start at zero so credits, freezes and cash-outs reconcile to bank balances.
Payments are ingested and reconciled sequentially so prior posted credits are visible to detection.


## Public simulation API (demo mode only)

These routes are absent outside `FRAUDLENS_MODE=demo`, including OpenAPI. They never grant analyst access.
`POST /public/attacks` accepts `{typology:mule_layering|sim_swap_takeover|card_testing|atm_cashout,victim_amount_minor?:100000..20000000}` and returns `{attack_id:"ATK-<12 hex>",status_url}`. Only mule layering uses the amount (default 4800000); its legs scale proportionally in integer paise. Other typologies keep their fixed amounts. The simulation runs through the same detector, outbox and bank service as authenticated scenario launches.

`GET /public/attacks/{attack_id}` returns six ledger-derived steps (Scam payment sent; FraudLens flagged it; Bank protection requested; Bank confirmed protection; Analyst picked it up; Verdict recorded), each `{label,status:pending|done|blocked,at}`. Outcomes are `in_progress|caught|partially_caught|missed`; a confirmed bank action alone never fabricates human pickup or verdict. Progress remains in progress awaiting the analyst. Case reference is masked to its last four characters. Recovery totals and redacted trace rows belong only to this fictional attack; no full case/account IDs, account balances or analyst identities are returned.

`POST /public/attacks/{attack_id}/report-1930` is valid only for mule layering. It persists a time-derived fictional complaint reference before intake, so retry/restart reuse the same report. The response is the same redacted status shape, including complaint_id and held_total_minor. Only acknowledged, unreleased liens count as held.

Both POST routes share a per-client-IP rolling quota of ten requests per five minutes. Excess returns **429** `{"detail":"Too many simulated attacks. Try again in a few minutes."}`. GET polling does not consume that quota. The limit is process-local; attack and complaint records are durable SQLite state. No real helpline, police, bank or external portal is contacted.


## FraudLens Agent

`GET /ops/cases/{id}/brief` returns a stored deterministic draft with typology, summary, up to five evidence points, recommended_action, target_account_id, amount_minor (for a lien), required_role/label, confidence, up to four next steps, ncrp_narrative and generated_by. Narratives use IST, Indian currency grouping and masked account references. They are drafts, never an external filing. Complaint recommendations select the first eligible traced mule and never protect the complainant; low detector score alone does not dismiss a victim report. Already-recorded verdicts take precedence so confirmed fraud may recommend supervisor closure without repeating the verdict.

Priority is a bounded integer: `round(55*score + 15*min(1,amount_minor/10000000) + 10*min(1,age_minutes/60) + 20*is_complaint)`, capped at 100 with nonnegative age. The top two contributors form priority_reason. Scores are prioritisation signals, not calibrated fraud probabilities.

`POST /ops/agent/settings {auto_assign:boolean}` requires supervisor role; default is off. When enabled, the worker assigns unassigned open cases by priority to online L1 analysts with the least assigned workload, breaking ties by username. Every assignment and brief draft is an agent audit event. Snapshot `agent` counters are derived from the full event ledger; liens_placed requires a bank-confirmed action linked to an agent request, including later released holds in the cumulative count.

Optional `FRAUDLENS_LLM=ollama` enables only summary wording on authenticated brief read. The local request has a six-second timeout and default model `qwen2.5:7b-instruct` (`FRAUDLENS_LLM_MODEL` overrides). Amounts must match the template and known facts; failure returns the deterministic sentence. Model I/O runs outside case locks; stale case versions cannot overwrite a newer brief. It never changes recommendations, roles, narratives, case state or bank actions. The agent never confirms fraud, releases funds, or closes an account.

`GET /ops/cases` also accepts `view=all|mine|unassigned|awaiting_approval|complaints` (default `all`; `mine` uses the signed-in analyst) and returns cases sorted by current agent priority, highest first, each with `priority` and `priority_reason`.
