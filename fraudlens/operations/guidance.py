"""Source-linked design references, explicitly separate from certification."""


PIB_CYBER_FRAUDS = "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2042130"
VERIFIED = "Verified 2026-10-19 on the issuer's domain"
# 1930 / NCRP and bank-side requirements, paraphrased. Only what the cited
# source says is claimed; anything not read on a primary domain is labelled.
REQUIREMENTS = [
    {
        "issuer": "I4C (Ministry of Home Affairs)",
        "source": "Citizen Financial Cyber Fraud Reporting and Management System (CFCFRMS) and helpline 1930 — PIB release 'Strengthening the mechanism to deal with cyber frauds'",
        "url": PIB_CYBER_FRAUDS,
        "date": "2024-08-06",
        "status": VERIFIED,
        "what_it_requires": "CFCFRMS, launched under I4C in 2021, exists for immediate reporting of financial frauds and to stop fraudsters siphoning off funds; the toll-free helpline 1930 assists citizens in lodging complaints.",
        "how_fraudlens_models_it": "A simulated complaint (source 1930_helpline, ncrp_portal or branch) opens a complaint case, traces the reported payment through mule accounts and asks the bank simulator to hold what is still there.",
        "not_covered": "No connection to CFCFRMS or the police; complaints and IDs are fictional. 'Golden hour' is FraudLens's framing, not a term from this source, and the release does not prescribe our lien-placement rules.",
    },
    {
        "issuer": "I4C (Ministry of Home Affairs)",
        "source": "National Cyber Crime Reporting Portal (cybercrime.gov.in) — same PIB release",
        "url": PIB_CYBER_FRAUDS,
        "date": "2024-08-06",
        "status": VERIFIED,
        "what_it_requires": "The portal lets the public report all types of cyber crime; reported incidents, their conversion into FIRs and further action are handled by the State/UT law enforcement agencies concerned.",
        "how_fraudlens_models_it": "Complaint references use an NCRP-style number and the agent drafts an NCRP narrative with masked account references for an analyst to review.",
        "not_covered": "Nothing is filed on the portal or sent to police; the narrative is a draft and 'Record NCRP report' only marks the simulated case.",
    },
    {
        "issuer": "Reserve Bank of India",
        "source": "Master Directions on Fraud Risk Management in Commercial Banks (including Regional Rural Banks) and All India Financial Institutions — RBI/DOS/2024-25/118",
        "url": "https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=12702",
        "date": "2024-07-15",
        "status": VERIFIED,
        "what_it_requires": "A principle-based framework for prevention, early detection and timely reporting of fraud to law enforcement and RBI, with board oversight, an early-warning framework and natural justice before an account is classified as fraud.",
        "how_fraudlens_models_it": "Detection, protection, analyst verdict and case resolution stay separate; L1 → L2 → Supervisor approvals and a complete actor/time audit trail back every verdict and account closure.",
        "not_covered": "No board policy, early-warning committee, show-cause/hearing process or reporting to RBI or police. For commercial banks, RBI's Fraud Risk Management Directions, 2026 (31 July 2026, listed in the references above) state that existing fraud-risk directions stand repealed; check which instrument governs a given bank.",
    },
    {
        "issuer": "Reserve Bank of India",
        "source": "Customer Protection – Limiting Liability of Customers in Unauthorised Electronic Banking Transactions — RBI/2017-18/15, DBR.No.Leg.BC.78/09.07.005/2017-18",
        "url": "https://www.rbi.org.in/scripts/BS_CircularIndexDisplay.aspx?Id=11040",
        "date": "2017-07-06",
        "status": VERIFIED,
        "what_it_requires": "Zero or limited customer liability depending on fault and how quickly the customer reports; the bank must credit (shadow-reverse) the disputed amount within 10 working days of notification and resolve the complaint within 90 days, and bears the burden of proving customer liability.",
        "how_fraudlens_models_it": "The complainant's account is never restricted, liened or closed; holds and closures target traced mule accounts only.",
        "not_covered": "No shadow reversal, liability determination, 10-day or 90-day clocks, or compensation; these customer-protection duties sit outside this simulator.",
    },
    {
        "issuer": "NPCI",
        "source": "UPI handling of cyber-fraud complaints: hold (lien) on the disputed amount in the receiving account",
        "url": None,
        "date": "not verified",
        "status": "modelled on (unverified)",
        "what_it_requires": "Secondary sources describe receiving banks placing a hold on the disputed amount after a CFCFRMS/1930 complaint while credits still post; no NPCI circular confirming this was read (NPCI's circular pages returned an error on 2026-10-19).",
        "how_fraudlens_models_it": "A lien holds a specific amount: debits above the available balance are declined, credits into a liened account still post, and an L2 can release it.",
        "not_covered": "No NPCI rule, timeline or message format is claimed. Real lien semantics depend on the bank and its member circulars.",
    },
]


def guidance_response() -> dict:
    """Return the public guidance contract without implying legal compliance."""
    digital = "https://www.rbi.org.in/scripts/BS_ViewMasDirections.aspx?id=13642"
    fraud = "https://www.rbi.org.in/scripts/BS_ViewMasDirections.aspx?id=13641"
    return {
        "references": [
            {
                "id": "npci-operational-controls",
                "title": "NPCI guidance note: operational lapses and fraud controls",
                "source_url": "https://www.npci.org.in/PDF/npci/risk-management/Best-Practices.pdf",
                "source_date": "2024-01-19",
                "applicability": "Generic banking guidance, not a universal NPCI certification for all four channels. Indexed pages 1–2 verified; full PDF retrieval incomplete.",
                "control": "Compare bank acknowledgements with local payment/action state; monitor source accounts and related beneficiaries. Full beneficiary credit-ledger and settlement reconciliation remain outside this simulator.",
                "status": "Partial source verification; showcase mapping; bank applicability review pending",
                "test_evidence": [
                    "Passed 2026-10-17: tests.test_operations.OperationsTests.test_idempotent_ingest_and_conflicting_reuse.",
                    "Passed 2026-10-17: tests.test_operations.OperationsTests.test_timeout_reconciles_and_state_survives_restart.",
                ],
            },
            {
                "id": "rbi-payment-monitoring",
                "title": "RBI Commercial Banks Digital Payment Security Controls 2026: paragraphs 26, 52–56",
                "source_url": digital,
                "source_date": "2026-07-31; updated 2026-10-01",
                "applicability": "Commercial banks as defined in the Directions; not every bank category. Other entities have separate instruments. Rules and thresholds are showcase policy choices, not RBI-prescribed freeze thresholds.",
                "control": "Versioned channel rules record velocity, device, beneficiary and authentication signals; analysts review evidence and false positives.",
                "status": "Primary source verified 2026-10-17; controlled synthetic checks only",
                "test_evidence": [
                    "Passed 2026-10-17: tests.test_operations.OperationsTests.test_all_channels_detect_protect_and_decline.",
                    "Passed 2026-10-17: tests.test_operations.OperationsTests.test_future_history_does_not_influence_past_transaction.",
                    "Measured controlled synthetic results: docs/verification/operations-evaluation.json; includes false positives and false negatives, not real-bank validation.",
                ],
            },
            {
                "id": "rbi-operational-consistency",
                "title": "RBI Commercial Banks Digital Payment Security Controls 2026: paragraphs 20, 57",
                "source_url": digital,
                "source_date": "2026-07-31; updated 2026-10-01",
                "applicability": "Recovery and stakeholder reconciliation are broader than this local application. Shared dashboard counters are not settlement reconciliation.",
                "control": "Persist payment attempts, case versions, durable bank jobs and audit events; derive all console counters from one database snapshot. Preserve pending and failed actions until acknowledged.",
                "status": "Primary source verified 2026-10-17; limited simulator implementation scope",
                "test_evidence": [
                    "Passed 2026-10-17: tests.test_operations.OperationsTests.test_timeout_reconciles_and_state_survives_restart.",
                    "Passed 2026-10-17: tests.test_operations.OperationsTests.test_optimistic_decisions_reject_stale_version.",
                    "Passed 2026-10-17: tests.test_operations_api.OperationsApiTests.test_scenario_decision_report_and_all_channel_counts.",
                ],
            },
            {
                "id": "rbi-fraud-investigation",
                "title": "RBI Commercial Banks Fraud Risk Management 2026: paragraphs 6, 23–25",
                "source_url": fraud,
                "source_date": "2026-07-31",
                "applicability": "Bank-level fraud governance and formal classification have additional procedural obligations. An analyst's local verdict is not a regulatory fraud declaration, account caution-listing, or report to RBI, NPCI or law enforcement.",
                "control": "Keep automated suspicion, reversible protection, analyst verdict and case resolution separate; require decision reasons and retain actor/time evidence. Formal notices, hearings and regulatory reporting are not implemented.",
                "status": "Primary source verified 2026-10-17; partial design mapping only",
                "test_evidence": [
                    "Passed 2026-10-17: tests.test_operations.OperationsTests.test_false_positive_release_and_fraud_resolution (actor timeline and acknowledged release).",
                    "Passed 2026-10-17: tests.test_operations.OperationsTests.test_one_reversal_does_not_release_other_case.",
                    "Passed 2026-10-17: tests.test_operations_api.OperationsApiTests.test_authentication_required_for_reads_writes_and_stream.",
                ],
            },
            {
                "id": "rbi-card-atm-controls",
                "title": "RBI Commercial Banks Digital Payment Security Controls 2026: paragraph 69",
                "source_url": digital,
                "source_date": "2026-07-31; updated 2026-10-01",
                "applicability": "Card-issuer/acquirer and ATM controls extend to network switches, devices and cryptography. This project does not certify terminals, implement HSM/PIN processing, or connect to RuPay/NFS/Visa/Mastercard.",
                "control": "Demonstrate instrument-scoped card restrictions and account-scoped debit restrictions, explicit bank acknowledgements and subsequent simulated declines. Actual restriction scope must be negotiated with each bank.",
                "status": "Primary source verified 2026-10-17; simulator behaviour only",
                "test_evidence": [
                    "Passed 2026-10-17: tests.test_bank_simulator.BankSimulatorTests.test_card_restrictions_only_affect_matching_instrument.",
                    "Passed 2026-10-17: tests.test_bank_simulator.BankSimulatorTests.test_case_owned_releases_preserve_other_case_and_persist_declines.",
                    "Passed 2026-10-17: tests.test_operations.OperationsTests.test_false_positive_release_and_fraud_resolution.",
                ],
            },
            {
                "id": "pci-minimal-card-data",
                "title": "PCI SSC FAQ 1071: display masking of payment card numbers",
                "source_url": "https://www.pcisecuritystandards.org/faqs/1071/",
                "source_date": "2025-07 (day not stated)",
                "applicability": "PCI guidance concerns environments handling payment-card data; a PCI assessment is separate. Fictional instrument references are not PANs or evidence of PCI compliance.",
                "control": "Use fictional account/card references in scenarios and exports. Never enter real PAN, PIN, CVV, passwords or banking credentials into the demonstration.",
                "status": "Primary source verified 2026-10-17; synthetic identifiers only",
                "test_evidence": [
                    "Planned verification: seeded scenarios and report fixtures use fictional identifiers without payment authentication secrets.",
                ],
            },
        ],
        "requirements": REQUIREMENTS,
        "disclaimer": (
            "FraudLens is a local simulated showcase, not an NPCI-approved, RBI-certified or PCI-validated banking product. "
            "Sources were reviewed on 17 October 2026 and the 1930/NCRP, RBI and NPCI mapping on 19 October 2026. Source verification and software test results are separate: "
            "named passing checks validate only their tested simulator behaviour; planned checks remain unverified. Automatic restrictions are demonstration policy, "
            "not a universal regulatory mandate. Bank-specific legal applicability, current member circulars, reporting, "
            "customer safeguards, security assessment and production integration require further review. "
            "No real accounts are blocked and no reports are sent to banks or authorities."
        ),
    }
