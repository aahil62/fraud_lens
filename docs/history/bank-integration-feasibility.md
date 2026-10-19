# FraudLens: bank integration feasibility

Checked: 17 October 2026. Status: public access path verified; authenticated integration not yet tested.

## Agreed product direction

FraudLens covers UPI, net banking, cards, and ATMs. It should detect supported fraud patterns, automatically request protective bank action, track bank acknowledgement, and let an analyst confirm fraud or reverse the protection. Case views, account status, reports, audit history, and live counts must reflect the same persisted records.

## Axis: what was verified

The following pages were inspected in a live browser:

- [Developer signup](https://apiportal.axis.bank.in/portal/user/register) loads and requires username, email, first and last name, consumer organization, mobile number, segment, industry, company name, password and confirmation, terms acceptance, and CAPTCHA.
- Segment choices displayed: Retail, Corporate, and Corporate Payment Aggregator. These choices do not establish student eligibility.
- [Accounts product family](https://apiportal.axis.bank.in/portal/product-details/76) links to CASA APIs and other account-related products.
- [CASA APIs](https://apiportal.axis.bank.in/portal/product/36699) lists 24 APIs. While logged out, it displays a restricted-access notice, a disabled Subscribe button, and “This plan is not subscribable.” This observation does not establish what an approved user can subscribe to.
- [Account Freeze forum](https://apiportal.axis.bank.in/portal/forum/646) exists. It is a forum page, not an API specification or successful API call.
- [Onboarding guide](https://apiportal.axis.bank.in/portal/index.php/how-it-works) requires signup approval, creation of an application, and subscription to selected APIs.

No signup was submitted, personal details entered, credentials created, API subscriptions requested, or banking operations executed.

## Next access step

1. Complete the open developer-registration form using accurate details. Do not invent a company or bank partnership. If no field option fits a student project, clarify eligibility with Axis before submitting.
2. Complete email verification and wait for signup approval as required by Axis.
3. Sign in and inspect the available CASA API list and subscription conditions. Check fees and eligibility before accepting a plan.
4. Locate the actual freeze, unfreeze, and account-status specifications. Confirm their product, supported account types, test environment, authentication requirements, and approval requirements.
5. Create an application and obtain an approved test subscription if available. Store credentials locally in an ignored environment file; do not paste secrets into chat or commit them.

Password creation needs direct user input. Terms acceptance and CAPTCHA completion also require the user's action or the applicable browser confirmation before the agent can continue with those steps.

## Questions access must answer

- Are account freeze and unfreeze exposed to this approved developer account?
- Does the test environment maintain account state across requests, or return predetermined examples?
- Is there an independent way to read restriction status?
- Which transaction types does a restriction affect? A deposit-account freeze must not be assumed to block a separate credit-card account.
- Are transaction feeds or transaction queries available for each of the four channels? Are events delivered by webhook, polling, or another interface?
- Can we create controlled test transactions before and after a restriction?
- Are restriction/release callbacks, correlation IDs, duplicate handling, and error outcomes documented?
- What costs, quotas, certificates, IP restrictions, and bank approvals apply?

## Integration acceptance tests after access

| Test | Required evidence |
|---|---|
| Connection | An authenticated request succeeds against the designated test environment and test account. |
| Restriction | A request receives an identifiable response; an independent status check confirms the restriction. |
| Enforcement | A subsequent controlled test transaction is declined because of that restriction. Record the actual supported channel and scope. |
| Release | Analyst-authorized release receives confirmation; a subsequent controlled test transaction succeeds where supported. |
| Retry and timeout | A retry does not duplicate the action; timeout remains pending until reconciled. |
| Recovery | Restart and reconnect preserve pending actions and reconcile with the bank's latest status. |
| User-interface consistency | Case, account view, live counts, and audit history agree after each persisted event. |

Record provider, environment, operation, test timestamp, redacted request/response, correlation ID, and observed result. A successful example response alone does not establish enforcement or coverage across all channels.

## Design decisions that can proceed independently

- Track investigation state separately from bank-action state.
- Use explicit bank-action states: requested, confirmed, failed, and release requested/released; reconcile uncertain outcomes rather than showing success prematurely.
- Use stable transaction, case, account/instrument, and action identifiers. Duplicate delivery must not inflate counters.
- Persist decisions before publishing UI updates. Deliver bank actions reliably and reconcile them after interruption.
- Derive overall and channel-specific counters from the same stored records. Define resolved, confirmed fraud, false positive, and pending review precisely.
- Keep bank-specific request formats at the integration boundary. Final adapter details depend on the actual approved specifications.
- Maintain a separate requirements matrix for applicable NPCI, RBI, bank, and network guidance. Sandbox integration does not establish compliance.

## Decision

Continue with Axis as the first access candidate. The next dependent step is user registration and bank approval, not implementation against an assumed endpoint. All four fraud channels remain in product scope; external feed access, restriction scope, and enforcement evidence remain unverified.
