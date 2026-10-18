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
Bank support for liens/closure follows in Task 3; queued requests are not confirmed protection.

Insufficient role: **403** `{detail:string,required_role:"l2_analyst"|"supervisor"}`.
Stale version or competing claim: **409** `{detail:string,version:number,assignee:string|null}`.
Other conflicts (e.g. a pending approval) return `{detail:string}`. Rejecting or approving your own
request is forbidden. Rejected/failed approval execution leaves the case and outbox unchanged.

Cases add `assignee` (username), `assigned_at`, `pending_approval` (or null) and ordered distinct
`handled_by` usernames from human case audit events. `assigned_to` remains the display label.
Snapshots add `team` (role label, online, last seen, current case, open assigned, resolved today)
and `approvals` (pending request fields plus case_id). All events use the existing live cursor.
