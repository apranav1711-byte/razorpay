# API Reference

ChargebackShield exposes a FastAPI reference service behind the dashboard’s `/risk-api` proxy. It is a **defense-only decision-support API**: all state changes remain local to the application and no endpoint moves money or submits a case to a payment network.

## Operating rules

| Rule | Behavior |
|---|---|
| Model outputs are recommendations | `POST /score` returns a score, tier, explanation, and recommended action. It never blocks or settles a payment. |
| Evidence is source constrained | `POST /evidence/generate/{dispute_id}` can return only source-linked claims or explicit insufficient-evidence statements. |
| Approval is human-only | An approval requires an existing evidence draft in an appropriate review state and logs a named actor. |
| Rejection carries accountability | A rejection requires a meaningful reason and logs a named actor. |
| Export is local and private | Evidence PDFs are generated from an existing draft, sent as an attachment with `Cache-Control: no-store`, and recorded as an audit event. |

## Endpoints

| Method and route | Request | Response | Notes |
|---|---|---|---|
| `POST /score` | Structured scoring features | `risk_score`, tier, recommendation, model version, top features | Returns a bounded explanation and persists a score audit event. |
| `POST /imports/csv` | Multipart `file` and optional `actor` | Import ID, count, hash prefix, high-risk count | UTF-8 CSV only, 5 MB / 5,000-row limit, all-or-nothing validation. |
| `GET /imports` | — | Import metadata, outcomes, and errors | Original CSV contents are never returned or retained. |
| `GET /transactions` | Optional risk tier | Stored/scored transaction list | Read-only. |
| `GET /disputes` | — | Local dispute queue | Read-only. |
| `POST /evidence/generate/{dispute_id}` | — | Source-linked evidence draft | Saves a local draft only. |
| `POST /evidence/approve/{dispute_id}` | `actor`, optional reason | Local review outcome | Returns `external_submission: false`. |
| `POST /evidence/reject/{dispute_id}` | `actor`, required reason | Local rejection outcome | Rejection reason is persisted. |
| `GET /evidence/export/{dispute_id}.pdf` | Optional actor query parameter | PDF attachment | Requires an existing draft and records the export. |
| `GET /metrics` | — | Held-out evaluation artifact | Read-only synthetic benchmark metrics. |
| `GET /audit-log` | Optional filters | Append-only application event stream | No update or delete route is implemented. |
| `GET /audit-filters` | — | Valid actions, actors, entities, and outcomes | Powers the Audit Intelligence filter controls. |
| `GET /audit-analytics` | Period and filter query parameters | Activity timeline and chargeback trends | Read-only aggregate data for dashboard charts. |

## CSV schema

At minimum, import `transaction_id` and `amount_cents`. Risk features such as velocity, amount deviation, location mismatch, first-time customer, and device novelty are supported. Files containing payment account data, PAN, CVV/CVC, UPI PIN, emails, phone numbers, or addresses are rejected. See [`IMPORT_CONTRACT.md`](IMPORT_CONTRACT.md) for the complete field specification and minimal example.

## Example score request

```json
{
  "transaction_id": "txn_2026_0001",
  "amount_cents": 184500,
  "amount_zscore": 3.1,
  "velocity_1h": 8,
  "velocity_24h": 11,
  "velocity_7d": 17,
  "geo_mismatch": true,
  "customer_is_first_time": true,
  "new_device": true,
  "payment_method_risk": 0.58,
  "merchant_category_risk": 0.51
}
```

## Error behavior

The service rejects unsafe or invalid requests with meaningful HTTP status codes. `409` indicates a business-state conflict, such as approving before a draft exists; `422` indicates a failed request contract such as an empty rejection reason or invalid CSV row; and `415` indicates an unsupported upload type. Invalid CSV files are rejected as a whole so that no ambiguous subset is silently processed.
