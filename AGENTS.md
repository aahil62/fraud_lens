# FraudLens — instructions for coding agents (Codex)

This folder (`~/Projects/portfolio/fraudlens`) is the **only** FraudLens checkout to work in. The old folder under `~/Documents/Codex/2026-10-17/...` is superseded; do not edit it.

## Start here

1. Read `docs/superpowers/plans/2026-10-18-fraudlens-v3-operations-centre.md`. That plan is the job.
2. Background only: `docs/history/2026-10-17-codex-ui-handoff.md` (what the previous session did; its paths point at the old folder), `DESIGN.md`, `PRODUCT.md`, `docs/ARCHITECTURE.md`, `docs/OPERATIONS_API.md`.
3. All plan tasks are done; new work goes on `feature/fraudlens-v3` (see Current state).

## Current state (2026-10-19)

- **The plan is complete (Tasks 0–16).** `main` is pushed to `aahil62/fraud_lens` and deployed as a free Render web service from the Dockerfile: https://fraud-lens-r3t0.onrender.com (Hugging Face Docker Spaces now need a paid plan; `deploy/hf-space/` and `scripts/deploy_hf.sh` are kept for that option but unused). Render redeploys on every push to `main`.
- Day-to-day branch: `feature/fraudlens-v3`; merge into `main` with `--no-ff`. Pushing to `main` changes the public site, so it needs the user's explicit approval.
- Checks, live results and known limits are in `docs/VERIFICATION.md`.
- User decision (1930 complaints): never restrict, lien or close the complainant's (victim's) account; "Close account" targets a traced mule account chosen per hop (default: first-hop recipient), requires a confirmed-fraud verdict, and only accounts in the trace are allowed.
- User decision (credits): the project is the author's; it began as a hackathon project. Do not list teammates.
- Live-demo specifics: limits key on `CF-Connecting-IP` (Render is behind Cloudflare; `FRAUDLENS_CLIENT_IP_HEADER`), uvicorn runs with `--no-proxy-headers`, and Next compression is off so `/ops/events` streams.

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
- No push, deploy, publish or merge to `main` without the user's explicit approval (a push to `main` redeploys the live site).
- Finish by reporting checks with exact counts, screenshots, the live URL (if deployed) and anything not verified.
