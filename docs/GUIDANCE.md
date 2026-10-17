# Guidance applicability and evidence

Reviewed on **17 October 2026**. This is a source-linked engineering matrix for a local simulated showcase. It is not certification, legal advice, or a claim of complete regulatory coverage. `GET /ops/guidance` exposes the corresponding records from `fraudlens/operations/guidance.py`.

## Current references

| Reference | Source fact and scope | Showcase mapping | Verification boundary |
| --- | --- | --- | --- |
| [NPCI guidance note, 19 January 2024](https://www.npci.org.in/PDF/npci/risk-management/Best-Practices.pdf), pages 1–2 | Generic operational guidance includes matching switch/CBS status, reconciliation, remitter/beneficiary profiling and real-time/near-real-time monitoring. | Idempotent ingestion, acknowledged bank actions, related-beneficiary evidence. | **Partial retrieval:** official-domain indexed text verified; full PDF request returned a site shell. No full credit ledger, clearing system, settlement reconciliation, EFRM integration or NPCI reporting. |
| [RBI Commercial Banks Digital Payment Security Controls 2026](https://www.rbi.org.in/scripts/BS_ViewMasDirections.aspx?id=13642), paragraphs 26, 52–56 | Logging, parameterised fraud alerts and investigative review. | Versioned channel rules, evidence, analyst decisions. | Supported synthetic scenarios only; no assurance of detecting arbitrary or emerging fraud. |
| Same RBI source, paragraphs 20, 57 | Recovery without lost transactions/audit trails and stakeholder reconciliation. | Durable jobs, persistent state, consistent counters and timeout reconciliation. | Application-state consistency does not implement settlement reconciliation. |
| [RBI Commercial Banks Fraud Risk Management 2026](https://www.rbi.org.in/scripts/BS_ViewMasDirections.aspx?id=13641), paragraphs 6, 23–25 | Formal fraud classification requires procedural safeguards; non-credit transactions need validated early-warning monitoring. | Distinguish suspicion, protection, local verdict and resolution; retain reasons and actor identity. | No formal classification, notice/hearing process, caution listing, recovery, or regulatory reports. |
| Digital Payment Security Controls 2026, paragraph 69 | Cards/ATMs require monitoring, limits and broader infrastructure controls. | Simulated card/account restrictions, confirmed enforcement and reversible release. | No terminal hardening, HSM/PIN processing, switch-level limits or network certification. |
| [PCI SSC FAQ 1071](https://www.pcisecuritystandards.org/faqs/1071/), July 2025 | Displayed PANs require masking except for a specific business need. | Use fictional instrument references; keep actual card/authentication data out of demo inputs, logs and exports. | A synthetic-data design is not a PCI assessment. Masking display does not establish secure storage. |

The RBI digital-payments source was issued 31 July 2026 and updated 1 October 2026. The fraud-risk source was issued 31 July 2026. Their repeal provisions supersede earlier instructions for the defined commercial-bank category; the old 2021 and 2024 documents should not be presented as the current governing commercial-bank instruments. The [RBI official directions index](https://www.rbi.org.in/scripts/BS_ViewMasterDirections.aspx) independently lists the current documents. Other bank categories have separate Directions and need their own applicability review.

## Four-channel interpretation

UPI scenarios demonstrate payment bursts, beneficiary and device anomalies. Net-banking scenarios demonstrate combined authentication/beneficiary/transfer evidence. Card and ATM scenarios demonstrate instrument and withdrawal patterns. Cross-channel correlation uses the same fictional customer/account history. These are representative, defined patterns; a transaction's scenario label must never be a detector input.

NPCI guidance does not make every net-banking transfer, every card network or every ATM transaction one universal NPCI product. Real integration needs the bank's exact payment rails, member circulars, security obligations, operational policies, and authorised restriction semantics. RuPay/NFS/UPI membership or compliance is not implied.

Automatic restriction is the approved **showcase policy**. No source above establishes our numeric threshold or mandates freezing every alert. The simulator's account-wide debit restriction is an explicit model choice; a real bank may support materially different controls. An analyst confirming a local simulated incident does not complete the bank's formal fraud-classification duties. Case closure here is a workflow state, not statutory closure or recovery of funds.

## Verification evidence

API `test_evidence` entries cite actual named operational/simulator tests where verified, plus the reproducible synthetic evaluation. These checks validate software behavior within their fixtures, not regulatory applicability. A remaining planned identifier review is labelled as such. The implementation's [verification record](VERIFICATION.md) and machine-readable results distinguish completed checks from external requirements and approvals that remain outside scope.

## Retrieval record and remaining work

The RBI 2026 documents and PCI FAQ were read from primary-domain web pages. NPCI's four-page PDF could only be recovered through primary-domain indexed excerpts for pages 1–2, so that row is explicitly partial. Firecrawl CLI was authenticated but failed its request with DNS resolution failure for `api.firecrawl.dev`; the web tool supplied the primary-source fallback. No third-party interpretation is treated as an operative requirement.

Before production, obtain the relevant bank/member documentation; confirm amendments and entity/rail applicability with authorised reviewers; define customer notification, escalation, disputes, reporting, retention and recovery; validate real data and false positives; perform security and resilience assessments. None of these external approvals, notification services, reporting interfaces or real-bank capabilities is claimed by this showcase.
