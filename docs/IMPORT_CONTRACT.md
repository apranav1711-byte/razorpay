# Merchant CSV Import Contract

The CSV import is intended for **pseudonymous merchant transaction metadata**, not raw payment credentials or unnecessary personal data. ChargebackShield processes an accepted file in memory, persists only validated transaction records, import metadata, and a content hash, and records an append-only import audit event. The original CSV body is deliberately not stored by the application.

| Requirement | Rule |
|---|---|
| File type and size | UTF-8 CSV only, with a maximum body size of 5 MB and a maximum of 5,000 data rows. |
| Required headers | `transaction_id` and `amount_cents`. |
| Supported risk columns | `amount_zscore`, `velocity_1h`, `velocity_24h`, `velocity_7d`, `geo_mismatch`, `customer_is_first_time`, `odd_hour`, `new_device`, `payment_method_risk`, `merchant_category_risk`, `velocity_spike`, and `high_amount`. |
| Optional merchant context | `customer_id`, `merchant_id`, `payment_method`, `currency`, `occurred_at`, `dispute_flag`, `dispute_reason`, `delivery_status`, and `communication_count`. |
| Explicitly rejected data | Full payment-account numbers, PAN, CVV/CVC, expiry data, UPI PIN, customer email, phone number, physical address, and any header containing those fields. |
| Failure behavior | Header violations or invalid rows reject the entire file. The system does not partially score an ambiguous import. |
| Processing behavior | Each valid transaction is scored using the saved risk artifact. The resulting score and bounded explanation are retained; the original CSV is not retained. |
| Auditability | Every accepted or rejected import records file-name metadata, SHA-256 body hash, outcome summary, actor, and UTC timestamp. |

> Upload only data that your organization is authorized to process. Do not upload card data, secret authentication data, or direct customer identifiers. This demonstrator is not a substitute for a production data-processing agreement, retention policy, or compliance assessment.

## Minimal example

```csv
transaction_id,amount_cents,amount_zscore,velocity_1h,velocity_24h,velocity_7d,geo_mismatch,customer_is_first_time,new_device,payment_method_risk,merchant_category_risk
txn_2026_0001,184500,3.1,8,11,17,true,true,true,0.58,0.51
txn_2026_0002,92000,1.8,1,3,10,false,false,false,0.10,0.16
```

The UI provides a downloadable template matching this contract, previews header validation before upload, and displays row-level errors without exposing the CSV contents in the audit log.
