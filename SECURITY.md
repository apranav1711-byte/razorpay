# ChargebackShield Security and Safety Controls

ChargebackShield is a demonstrator for **defensive merchant decision support**. It is intentionally narrower than a payment-management system: it analyzes structured synthetic transaction data and drafts reviewable evidence, but cannot debit, credit, capture, refund, transfer, dispute externally, or otherwise move money.

## Enforced controls

| Control | Implementation | Verification |
|---|---|---|
| No autonomous payment action | Neither FastAPI nor the React dashboard implements a payment, refund, transfer, or payment-platform client. | API inventory in `README.md` and the endpoint tests. |
| Explicit human gate | Approval requires an existing evidence draft in `drafted` or `awaiting_approval` state and records a named actor. | `test_approval_requires_a_draft_and_only_records_local_state`. |
| No external submission | The approval response includes `external_submission: false`; it updates only a local demo state. | FastAPI approval test and Evidence Studio copy. |
| Rejection accountability | Rejection requires a non-empty reason and appends a decision/audit record. | `test_rejection_requires_a_reason`. |
| Grounded evidence | Supported claims need allowed, retrieved source links; unknown source keys cause fallback. | `test_insufficient_evidence_is_explicit_and_not_fabricated` and TypeScript guardrail tests. |
| Graceful insufficiency | Missing delivery, communication, or trusted-device proof produces explicit evidence-gap claims. | `dsp_demo_002` scenario and API test. |
| Auditability | Model version, SHA-256 input hash, output summary, actor, and UTC timestamp are recorded for actions. | Approval/rejection audit assertions. |
| Append-only API surface | Audit records are inserted internally and the API provides only `GET /audit-log`. | Update and delete route tests return 405. |
| Controlled CSV intake | CSV headers, file size, row count, encoding, schema, formula-style transaction IDs, numeric bounds, and duplicate IDs are validated before data is retained. | Accepted and sensitive-column rejection tests. |
| Data minimization | Merchant import accepts pseudonymous transaction metadata only. Sensitive identifiers are rejected and original file bytes are never persisted. | `docs/IMPORT_CONTRACT.md` and import result response. |
| Export restraint | PDFs are generated on demand from a persisted draft, served as attachment with `Cache-Control: no-store`, and logged. | PDF export regression test. |

## Threat-model boundaries

The system does not claim to prevent all fraud or guarantee chargeback outcomes. It does not validate the truthfulness of the source systems feeding it, perform identity verification, make legal conclusions, or provide a production-grade immutable ledger. Its source-link mechanism shows what structured records informed a claim; it does not turn those records into independent proof.

> **Operational requirement:** do not connect this demonstrator to a live payment account or treat its outputs as an automatic allow/hold/block policy. A production integration should require real access controls, data-retention decisions, sensitive-data minimization, alerting, vendor review, legal/compliance assessment, and an external audit-storage design.

## Reporting a concern

For buildathon evaluation, document the scenario, endpoint, expected behavior, observed behavior, and whether any output was ungrounded or actioned without explicit review. Do not include real payment credentials, card data, or customer personal information in an issue report.
