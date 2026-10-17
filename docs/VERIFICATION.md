# Verification record

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

The responsive overview was also inspected inside a 390-pixel-wide browser iframe. Navigation scrolls horizontally and metrics stack into two columns. This checks responsive CSS, not a physical-device or browser-matrix certification. Screenshots: [desktop overview](screenshots/overview.png), [resolved case](screenshots/case-reversal.png), [mobile viewport](screenshots/mobile.png). The temporary QA wrapper was removed from the deliverable.

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
