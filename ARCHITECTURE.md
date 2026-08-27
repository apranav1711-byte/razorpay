# ChargebackShield Architecture

ChargebackShield is designed as a **defense-only decision-support system**. It treats scoring, evidence drafting, human review, and audit logging as separate components so that a model inference cannot become an irreversible payment action. The web dashboard is intentionally an interface to recommendations and local review records, not a system capable of controlling funds or communicating with a payment network.

## Component responsibilities

| Component | Responsibility | Explicit non-responsibility |
|---|---|---|
| `ml/train.py` | Generates synthetic records, splits data, trains a weighted XGBoost classifier, calibrates it on validation data, saves SHAP/model artifacts, and writes held-out evaluation. | It does not ingest real merchant, cardholder, or payment-network data. |
| `ml/api.py` | Serves FastAPI scoring, retrieval, evidence generation, human review, metrics, and audit-log routes. | It does not expose a fund-transfer, refund, capture, payment, or external dispute-submission route. |
| Evidence retrieval | Builds a compact snapshot from a dispute, linked transaction, delivery facts, communications, order items, and customer-history facts. | It does not retrieve unstructured web data or invent evidence. |
| Evidence generator | Requests strict JSON claims from Claude Sonnet through a server-side proxy and then validates every requested source key. | It does not treat model text as valid if a claimed source key is absent or if a supported claim lacks a source link. |
| Deterministic fallback | Produces conservative supported claims and insufficiency notices when no model is available or model output fails validation. | It does not conceal a model failure or try to make a response sound complete. |
| React dashboard | Renders a six-screen merchant risk workspace and invokes bounded APIs. | It does not retain model credentials or bypass review checks in the browser. |

## Data and state model

The managed application schema represents transaction, customer, order, delivery, communication, model-output, dispute, evidence-draft, human-decision, model-evaluation, and audit-event records. The FastAPI reference service mirrors the demonstrator subset in SQLite to make local execution reproducible. `docs/DATA_MODEL.md` describes the entities and invariants in greater detail.

| State transition | Required precondition | Persisted consequence | External effect |
|---|---|---|---|
| Score transaction | Valid structured input | Transaction/risk record plus audit event containing model version and input hash. | None. |
| Generate evidence | Existing dispute with a linked transaction | First-class evidence draft, dispute state `awaiting_approval`, and audit event. | None. |
| Approve evidence | Existing generated draft in `drafted` or `awaiting_approval`. | First-class human decision, state `submitted`, and audit event. | None; “submitted” is a local review label only. |
| Reject evidence | Existing generated draft and a non-empty reason. | First-class human decision, state `rejected`, and audit event. | None. |

## Evidence grounding protocol

The evidence workflow intentionally uses **structured retrieval before generation**. The server creates a source catalog whose keys map to exact record identifiers, fields, and values. The language-model request receives both the compact source snapshot and the finite list of allowed source keys. It must return claims in JSON form containing `claim_id`, `type`, `claim`, and `source_keys`.

The server rejects model output if a requested source key is not in the catalog or if a `supported` claim has no source keys. For required evidence categories such as delivery completion, customer communication, and trusted-device match, the service appends an explicit insufficiency claim when the retrieved snapshot cannot meet the stated standard. This is a defense against omission: the model cannot simply avoid mentioning a missing proof element.

> **Failure mode handled:** if delivery status is not `delivered`, a tracking reference is absent, communications are absent, or prior trusted-device evidence is absent, the response contains a visible `insufficient_evidence` claim. It does not restate a plausible delivery or customer-contact event as fact.

## Model-evaluation protocol

The synthetic generator is seeded and the anomaly rates are command-line parameters. The code stratifies into 14,000 training rows, 3,000 validation rows, and 3,000 held-out test rows. Class imbalance is addressed with `scale_pos_weight`; calibration is fitted on the validation partition only. The operating threshold is chosen on validation expected cost, then the untouched test partition receives a final metric calculation. scikit-learn documents the distinction between probability calibration and classification decision thresholds. [1]

The saved artifacts are `risk_model.joblib`, `risk_calibrator.joblib`, `shap_tree_explainer.joblib`, and `feature_order.joblib`. The model is explainable with SHAP-style per-feature effects, which are converted to dashboard-safe labels and evidence descriptions. [2]

## Deployment topology

The project contains a custom `Dockerfile` because the FastAPI reference service needs a Python runtime in addition to the managed Node/React stack. The Node application remains the user-facing web process and proxies `/risk-api` calls to the local FastAPI process. In production, `START_RISK_API=true` starts the Python service within the container; the Node server continues to bind to the platform-provided `PORT`.

This topology is suitable for the buildathon demonstrator. A production deployment should replace the local SQLite demo store with a managed database, use restricted identities and encrypted secret management, implement a real append-only or write-once audit store, and integrate a payment provider only after a separate security and compliance review.

## References

[1]: https://scikit-learn.org/stable/modules/calibration.html "scikit-learn: Probability calibration"
[2]: https://shap.readthedocs.io/en/latest/ "SHAP documentation"
