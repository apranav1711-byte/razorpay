# ChargebackShield Data Model and Accountability Boundary

ChargebackShield handles **synthetic demo data only**. Its records are deliberately separated so the system can trace a risk score or evidence claim back to the exact source field that supported it. Monetary values are stored as integer minor units, while system timestamps are stored and processed in UTC.

| Area | Primary records | Accountability purpose |
|---|---|---|
| Commerce history | `merchants`, `customers`, `orders`, `transactions` | Reconstructs a transaction context and customer history without real card data. |
| Evidence sources | `deliveries`, `communicationLogs` | Allows every drafted claim to link to a specific delivery, message, transaction, order, or prior-customer-history record. |
| Risk intelligence | `riskScores`, `modelEvaluations` | Preserves the calibrated score, explanation contributions, model version, input hash, and held-out evaluation. |
| Human review | `disputes`, `evidenceDrafts`, `humanDecisions` | Separates a generated draft from a reviewer approval or rejection, including the rejection rationale. |
| Auditability | `auditEvents` | An insert-only application audit stream recording the action, actor, input hash, output summary, model version, and UTC time. |

> **Safety boundary:** scoring returns a recommendation only. Evidence generation creates a review draft only. A dispute becomes `submitted` only after an explicit human approval operation produces a `humanDecisions` record and an associated audit event. The application intentionally includes no money-movement or external payment-platform submission capability.

The dashboard reads the records above through typed server procedures. The backend owns access to the model artifact and to the evidence-drafting model. Browser code never receives model credentials and never writes audit events directly.

## Evidence-claim contract

Each generated claim is a structured object with a `type`, claim text, and one or more `sourceLinks`. A supported claim must have at least one source link. If the retrieved snapshot cannot prove a requested fact, the response instead carries `type: "insufficient_evidence"` and a plain statement of what was missing. The user interface renders that distinction visually rather than treating uncertain claims as merchant evidence.

## Audit invariants

The service owns all audit-event writes. It exposes read access only; it does not expose an update or delete procedure for audit records. Event inputs are represented by a SHA-256 hash of the relevant structured record, which makes records comparable while avoiding needless duplication of source data in the event stream.
