# FraudLens — instructions for coding agents (Codex)

This folder (`~/Projects/portfolio/fraudlens`) is the **only** FraudLens checkout to work in. The old folder under `~/Documents/Codex/2026-10-17/...` is superseded; do not edit it.

## Start here

1. Read `docs/superpowers/plans/2026-10-18-fraudlens-v3-operations-centre.md`. That plan is the job.
2. Background only: `docs/history/2026-10-17-codex-ui-handoff.md` (what the previous session did; its paths point at the old folder), `DESIGN.md`, `PRODUCT.md`, `docs/ARCHITECTURE.md`, `docs/OPERATIONS_API.md`.
3. Tasks 0–15 are done; continue with the remaining Task 16 steps in order (see Current state).

## Current state (2026-10-19)

- Branch `feature/fraudlens-v3`. **Tasks 0–15 and Task 16 Steps 1–2 are committed** (roles, approvals, bank ladder, 1930 trace, typologies, attack API, agent, evaluation, console, demo-role login, `/attack`, landing, guidance, Docker image, docs, public-demo hardening), plus shutdown fixes for open event streams. Checks and limits are in `docs/VERIFICATION.md`.
- **Remaining: Task 16 Steps 3–8** (merge to `main` and push, Hugging Face Space, deploy, live checks, GitHub metadata, README live link). Steps 3, 5, 7 and the Step 8 push need the user's explicit approval; Step 4 is done by the user.
- User decision (1930 complaints): never restrict, lien or close the complainant's (victim's) account; "Close account" targets a traced mule account chosen per hop (default: first-hop recipient), requires a confirmed-fraud verdict, and only accounts in the trace are allowed.
- User decision (credits): the project is the author's; it began as a hackathon project. Do not list teammates.
- Nothing is deployed or pushed.

## Commands

```bash
.venv/bin/python -m unittest discover -s tests        # backend (stdlib unittest, not pytest)
npm --prefix frontend run test                         # frontend tests
npm --prefix frontend run lint
(cd frontend && npx tsc --noEmit)
.venv/bin/python scripts/dev.py                        # bank :8002, API :8001, console :3000
```

Stop the dev server you started before `npm --prefix frontend run build`. Never kill processes you did not start (an older copy may still be running from the old folder on the same ports; if ports 3000/8001/8002 are busy, tell the user instead of killing anything).

## Rules

- Write the plan's listed tests first, watch them fail, implement, run all checks, then commit with the plan's commit message.
- Use the exact names, roles, thresholds, amounts, routes and UI copy in the plan. If a step is impossible as written, stop and explain.
- Fictional data only. Money is integer paise.
- No push, deploy, publish or merge to `main` without the user's explicit approval.
- Task 16 (public deploy): at every step marked "user approval", stop, show the exact command and wait for a yes. Steps marked "user does this" belong to the user (Hugging Face account, tokens).
- Finish by reporting checks with exact counts, screenshots, the live URL (if deployed) and anything not verified.
