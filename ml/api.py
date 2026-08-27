#!/usr/bin/env python3
"""FastAPI reference service for the ChargebackShield demonstrator.

This service is intentionally defense-only. It can score transactions and draft
evidence for a human reviewer, but it cannot move money or contact a payment
network. `approve` records a local reviewed state only; it never submits outward.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from html import escape
from io import BytesIO
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import joblib
import numpy as np
import pandas as pd
import requests
import shap
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ml.imports import CsvValidationError, MAX_CSV_BYTES, validate_csv_bytes


ROOT = Path(__file__).resolve().parent
ARTIFACTS = ROOT / "artifacts"
METRICS_PATH = ROOT / "metrics.example.json"
DATABASE_PATH = Path(os.getenv("CHARGEBACKSHIELD_API_DB", ROOT / "chargebackshield_demo.sqlite"))
MODEL_VERSION = "cbs-xgb-calibrated-1.0.0"


class ScoreInput(BaseModel):
    transaction_id: str = Field(min_length=3)
    amount_cents: int = Field(gt=0)
    amount_zscore: float = 0.0
    velocity_1h: int = Field(ge=0, default=0)
    velocity_24h: int = Field(ge=0, default=0)
    velocity_7d: int = Field(ge=0, default=0)
    geo_mismatch: bool = False
    customer_is_first_time: bool = False
    odd_hour: bool = False
    new_device: bool = False
    payment_method_risk: float = Field(ge=0, le=1, default=0.1)
    merchant_category_risk: float = Field(ge=0, le=1, default=0.1)
    velocity_spike: bool = False
    high_amount: bool = False


class DecisionInput(BaseModel):
    actor: str = Field(min_length=2, max_length=128)
    reason: str | None = Field(default=None, max_length=1000)


class AppState:
    model: Any
    calibrator: Any
    explainer: Any
    features: list[str]


state = AppState()
app = FastAPI(title="ChargebackShield API", version="1.0.0", docs_url="/docs")


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def canonical_hash(value: Any) -> str:
    serialised = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()


@contextmanager
def database() -> Any:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def append_audit(connection: sqlite3.Connection, action: str, entity_type: str, entity_id: str, input_value: Any, output: dict[str, Any], actor: str, model_version: str | None = None) -> None:
    connection.execute(
        "INSERT INTO audit_events (event_id, action, entity_type, entity_id, model_version, input_hash, output_json, actor, occurred_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), action, entity_type, entity_id, model_version, canonical_hash(input_value), json.dumps(output), actor, utc_now()),
    )


def initialise_database() -> None:
    with database() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS transactions (transaction_id TEXT PRIMARY KEY, payload_json TEXT NOT NULL, risk_json TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS disputes (dispute_id TEXT PRIMARY KEY, transaction_id TEXT NOT NULL, reason TEXT NOT NULL, amount_cents INTEGER NOT NULL, status TEXT NOT NULL, filed_at TEXT NOT NULL, due_at TEXT NOT NULL, evidence_json TEXT);
            CREATE TABLE IF NOT EXISTS evidence_drafts (draft_id TEXT PRIMARY KEY, dispute_id TEXT NOT NULL, model_name TEXT NOT NULL, model_version TEXT NOT NULL, retrieval_json TEXT NOT NULL, claims_json TEXT NOT NULL, narrative TEXT NOT NULL, has_sufficient_evidence INTEGER NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS human_decisions (decision_id TEXT PRIMARY KEY, dispute_id TEXT NOT NULL, draft_id TEXT NOT NULL, decision TEXT NOT NULL, reason TEXT, actor TEXT NOT NULL, decided_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS evaluation_metrics (model_version TEXT PRIMARY KEY, metrics_json TEXT NOT NULL, evaluated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS imports (import_id TEXT PRIMARY KEY, file_name TEXT NOT NULL, content_hash TEXT NOT NULL, row_count INTEGER NOT NULL, status TEXT NOT NULL, error_count INTEGER NOT NULL, errors_json TEXT NOT NULL, actor TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS audit_events (event_id TEXT PRIMARY KEY, action TEXT NOT NULL, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, model_version TEXT, input_hash TEXT NOT NULL, output_json TEXT NOT NULL, actor TEXT NOT NULL, occurred_at TEXT NOT NULL);
            """
        )
        metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
        connection.execute("INSERT OR REPLACE INTO evaluation_metrics VALUES (?, ?, ?)", (MODEL_VERSION, json.dumps(metrics), utc_now()))
        count = connection.execute("SELECT COUNT(*) AS count FROM transactions").fetchone()["count"]
        if count:
            return
        now = datetime.now(UTC)
        seeded: list[tuple[ScoreInput, dict[str, Any]]] = [
            (ScoreInput(transaction_id="txn_demo_001", amount_cents=184_500, amount_zscore=3.1, velocity_1h=8, velocity_24h=11, velocity_7d=17, geo_mismatch=True, customer_is_first_time=True, odd_hour=True, new_device=True, payment_method_risk=0.58, merchant_category_risk=0.51, velocity_spike=True, high_amount=True), {"order_items": [{"name": "Wireless noise cancelling headphones", "quantity": 1}], "delivery": {"status": "delivered", "tracking_reference": "TRK-90122", "proof_summary": "Carrier scan recorded at the customer delivery location."}, "communications": [{"id": "msg_001", "channel": "email", "sent_at": (now - timedelta(days=6)).isoformat(), "summary": "Order confirmation sent to customer."}], "customer_history": {"prior_legitimate_transactions": 2, "device_match": False}}),
            (ScoreInput(transaction_id="txn_demo_002", amount_cents=92_000, amount_zscore=1.8, velocity_1h=1, velocity_24h=3, velocity_7d=10, geo_mismatch=False, customer_is_first_time=False, odd_hour=False, new_device=False, payment_method_risk=0.10, merchant_category_risk=0.16, velocity_spike=False, high_amount=False), {"order_items": [{"name": "Everyday cotton shirt", "quantity": 2}], "delivery": {"status": "delivered", "tracking_reference": "TRK-90137", "proof_summary": "Delivery scan available."}, "communications": [{"id": "msg_002", "channel": "sms", "sent_at": (now - timedelta(days=9)).isoformat(), "summary": "Shipment notification sent."}], "customer_history": {"prior_legitimate_transactions": 7, "device_match": True}}),
            (ScoreInput(transaction_id="txn_demo_003", amount_cents=136_000, amount_zscore=2.7, velocity_1h=5, velocity_24h=9, velocity_7d=15, geo_mismatch=True, customer_is_first_time=True, odd_hour=False, new_device=True, payment_method_risk=0.58, merchant_category_risk=0.51, velocity_spike=True, high_amount=True), {"order_items": [{"name": "Portable audio interface", "quantity": 1}], "delivery": {"status": "not_available", "tracking_reference": None, "proof_summary": None}, "communications": [], "customer_history": {"prior_legitimate_transactions": 0, "device_match": False}}),
        ]
        for payload, evidence in seeded:
            risk = score(payload)
            record = {**payload.model_dump(), **evidence, "occurred_at": now.isoformat()}
            connection.execute("INSERT INTO transactions VALUES (?, ?, ?, ?)", (payload.transaction_id, json.dumps(record), json.dumps(risk), utc_now()))
        disputes = [
            ("dsp_demo_001", "txn_demo_001", "fraudulent", 184_500, "new", now - timedelta(days=2), now + timedelta(days=5)),
            ("dsp_demo_002", "txn_demo_003", "product_not_received", 136_000, "new", now - timedelta(days=5), now + timedelta(days=1)),
        ]
        for dispute_id, transaction_id, reason, amount, status, filed_at, due_at in disputes:
            connection.execute("INSERT INTO disputes VALUES (?, ?, ?, ?, ?, ?, ?, NULL)", (dispute_id, transaction_id, reason, amount, status, filed_at.isoformat(), due_at.isoformat()))


def load_artifacts() -> None:
    state.model = joblib.load(ARTIFACTS / "risk_model.joblib")
    state.calibrator = joblib.load(ARTIFACTS / "risk_calibrator.joblib")
    state.explainer = joblib.load(ARTIFACTS / "shap_tree_explainer.joblib")
    state.features = joblib.load(ARTIFACTS / "feature_order.joblib")


def contribution_label(feature: str) -> tuple[str, str]:
    labels = {
        "amount_log": ("Transaction amount", "Amount transformed for model stability."),
        "amount_zscore": ("Amount anomaly", "Transaction amount compared with customer history."),
        "velocity_1h": ("One-hour velocity", "Number of transactions observed in one hour."),
        "velocity_24h": ("24-hour velocity", "Number of transactions observed in 24 hours."),
        "velocity_7d": ("Seven-day velocity", "Number of transactions observed in seven days."),
        "geo_mismatch": ("Geo mismatch", "IP geography differs from the billing geography."),
        "customer_is_first_time": ("First-time customer", "No prior customer transaction history is available."),
        "odd_hour": ("Unusual transaction time", "Transaction occurred in the configured overnight window."),
        "new_device": ("New device", "The device is not known from prior activity."),
        "payment_method_risk": ("Payment-method baseline", "Synthetic payment-method risk encoding."),
        "merchant_category_risk": ("Category baseline", "Synthetic merchant-category risk encoding."),
        "velocity_spike": ("Velocity spike", "Controlled high-velocity anomaly indicator."),
        "high_amount": ("High amount", "Controlled high-amount anomaly indicator."),
    }
    return labels[feature]


def score(payload: ScoreInput) -> dict[str, Any]:
    values = payload.model_dump()
    values["amount_log"] = float(np.log1p(payload.amount_cents))
    matrix = pd.DataFrame([{feature: values[feature] for feature in state.features}])
    probability = float(state.calibrator.predict_proba(matrix)[0, 1])
    shap_values = state.explainer.shap_values(matrix)
    raw_values = np.asarray(shap_values)[0]
    contributions = []
    for feature, raw_value in sorted(zip(state.features, raw_values, strict=True), key=lambda item: abs(float(item[1])), reverse=True)[:5]:
        display_name, evidence = contribution_label(feature)
        contributions.append({"feature": feature, "display_name": display_name, "contribution": round(float(raw_value), 4), "direction": "raises_risk" if raw_value >= 0 else "lowers_risk", "evidence": evidence})
    if probability >= 0.35:
        tier, recommended_action = "high", "hold_for_review"
    elif probability >= 0.12:
        tier, recommended_action = "medium", "verify"
    else:
        tier, recommended_action = "low", "allow"
    return {"risk_score": round(probability, 4), "tier": tier, "recommended_action": recommended_action, "model_version": MODEL_VERSION, "top_features": contributions}


def record_import_result(file_name: str, content_hash: str, row_count: int, status: str, errors: list[str], actor: str, *, import_id: str | None = None) -> str:
    event_id = import_id or str(uuid.uuid4())
    with database() as connection:
        connection.execute(
            "INSERT INTO imports VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (event_id, file_name[:255], content_hash, row_count, status, len(errors), json.dumps(errors[:50]), actor, utc_now()),
        )
        append_audit(connection, f"csv_import_{status}", "import", event_id, {"file_name": file_name, "content_hash": content_hash}, {"rows": row_count, "error_count": len(errors), "errors": errors[:10]}, actor, MODEL_VERSION)
    return event_id


def source_catalog(snapshot: dict[str, Any]) -> dict[str, dict[str, str]]:
    catalog: dict[str, dict[str, str]] = {}
    transaction = snapshot["transaction"]
    catalog["transaction.amount_cents"] = {"source_entity": "transaction", "source_record_id": transaction["transaction_id"], "source_field": "amount_cents", "source_value": str(transaction["amount_cents"])}
    delivery = snapshot["delivery"]
    if delivery.get("status"):
        catalog["delivery.status"] = {"source_entity": "delivery", "source_record_id": transaction["transaction_id"], "source_field": "status", "source_value": str(delivery["status"])}
    if delivery.get("tracking_reference"):
        catalog["delivery.tracking_reference"] = {"source_entity": "delivery", "source_record_id": transaction["transaction_id"], "source_field": "tracking_reference", "source_value": str(delivery["tracking_reference"])}
    if delivery.get("proof_summary"):
        catalog["delivery.proof_summary"] = {"source_entity": "delivery", "source_record_id": transaction["transaction_id"], "source_field": "proof_summary", "source_value": str(delivery["proof_summary"])}
    for message in snapshot.get("communications", []):
        catalog[f"communication.{message['id']}"] = {"source_entity": "communication", "source_record_id": message["id"], "source_field": "summary", "source_value": message["summary"]}
    history = snapshot.get("customer_history", {})
    catalog["customer_history.prior_legitimate_transactions"] = {"source_entity": "customer_history", "source_record_id": transaction["transaction_id"], "source_field": "prior_legitimate_transactions", "source_value": str(history.get("prior_legitimate_transactions", 0))}
    catalog["customer_history.device_match"] = {"source_entity": "customer_history", "source_record_id": transaction["transaction_id"], "source_field": "device_match", "source_value": str(history.get("device_match", False))}
    return catalog


def deterministic_claims(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    sources = source_catalog(snapshot)
    claims: list[dict[str, Any]] = [{"claim_id": "claim_transaction", "type": "supported", "claim": f"The disputed transaction amount was ₹{snapshot['transaction']['amount_cents'] / 100:,.2f}.", "source_keys": ["transaction.amount_cents"]}]
    if snapshot["delivery"].get("status") == "delivered" and snapshot["delivery"].get("tracking_reference"):
        claims.append({"claim_id": "claim_delivery", "type": "supported", "claim": "The available delivery record indicates that the order was delivered and has a tracking reference.", "source_keys": ["delivery.status", "delivery.tracking_reference"]})
    else:
        claims.append({"claim_id": "claim_delivery_insufficient", "type": "insufficient_evidence", "claim": "Insufficient evidence for delivery completion: a delivered status and tracking reference were not both available in the retrieved records.", "source_keys": [key for key in ("delivery.status", "delivery.tracking_reference") if key in sources]})
    communication_keys = [key for key in sources if key.startswith("communication.")]
    if communication_keys:
        claims.append({"claim_id": "claim_communication", "type": "supported", "claim": "Customer communication records are available for the transaction.", "source_keys": communication_keys})
    else:
        claims.append({"claim_id": "claim_communication_insufficient", "type": "insufficient_evidence", "claim": "Insufficient evidence for customer communication: no communication record was retrieved for this transaction.", "source_keys": []})
    if snapshot["customer_history"].get("device_match"):
        claims.append({"claim_id": "claim_device", "type": "supported", "claim": "The current device matches a device recorded on prior legitimate customer activity.", "source_keys": ["customer_history.device_match", "customer_history.prior_legitimate_transactions"]})
    else:
        claims.append({"claim_id": "claim_device_insufficient", "type": "insufficient_evidence", "claim": "Insufficient evidence to establish a prior legitimate-device match.", "source_keys": ["customer_history.device_match"]})
    return claims


def claude_claims(snapshot: dict[str, Any], fallback: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    api_url = os.getenv("BUILT_IN_FORGE_API_URL")
    api_key = os.getenv("BUILT_IN_FORGE_API_KEY")
    if os.getenv("CHARGEBACKSHIELD_SKIP_LLM") == "1" or not api_url or not api_key:
        return fallback, "deterministic-safety-fallback"
    catalog = source_catalog(snapshot)
    schema = {
        "name": "grounded_evidence_claims",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {"claims": {"type": "array", "items": {"type": "object", "properties": {"claim_id": {"type": "string"}, "type": {"type": "string", "enum": ["supported", "insufficient_evidence"]}, "claim": {"type": "string"}, "source_keys": {"type": "array", "items": {"type": "string"}}}, "required": ["claim_id", "type", "claim", "source_keys"], "additionalProperties": False}}},
            "required": ["claims"],
            "additionalProperties": False,
        },
    }
    prompt = json.dumps({"retrieved_snapshot": snapshot, "allowed_source_keys": catalog, "required_behavior": "Return only claims that can be linked to allowed_source_keys. If support is absent, return an insufficient_evidence claim. Do not invent facts, delivery events, identities, or legal conclusions."})
    try:
        response = requests.post(f"{api_url.rstrip('/')}/v1/chat/completions", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json={"model": "claude-sonnet-4-6", "max_tokens": 1400, "messages": [{"role": "system", "content": "You draft bounded, factual evidence claims for a merchant. You may use only the supplied JSON."}, {"role": "user", "content": prompt}], "response_format": {"type": "json_schema", "json_schema": schema}}, timeout=35)
        response.raise_for_status()
        output = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(output)
        claims = parsed["claims"]
        if not claims or any(not set(claim["source_keys"]).issubset(catalog) or (claim["type"] == "supported" and not claim["source_keys"]) for claim in claims):
            return fallback, "deterministic-safety-fallback"
        return claims, "claude-sonnet-4-6"
    except Exception:
        return fallback, "deterministic-safety-fallback"


def render_claims(snapshot: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    fallback = deterministic_claims(snapshot)
    claims, model_name = claude_claims(snapshot, fallback)
    required_insufficiency_claims = [claim for claim in fallback if claim["type"] == "insufficient_evidence"]
    existing_claim_ids = {claim["claim_id"] for claim in claims}
    claims.extend(claim for claim in required_insufficiency_claims if claim["claim_id"] not in existing_claim_ids)
    catalog = source_catalog(snapshot)
    rendered = []
    for claim in claims:
        rendered.append({"claim_id": claim["claim_id"], "type": claim["type"], "claim": claim["claim"], "source_links": [catalog[key] for key in claim["source_keys"]]})
    return rendered, model_name


@app.on_event("startup")
def startup() -> None:
    load_artifacts()
    initialise_database()


@app.post("/score")
def score_route(payload: ScoreInput) -> dict[str, Any]:
    result = score(payload)
    with database() as connection:
        record = payload.model_dump()
        connection.execute("INSERT OR REPLACE INTO transactions VALUES (?, ?, ?, ?)", (payload.transaction_id, json.dumps(record), json.dumps(result), utc_now()))
        append_audit(connection, "transaction_scored", "transaction", payload.transaction_id, record, result, "risk_model", MODEL_VERSION)
    return result


@app.post("/imports/csv")
async def import_csv(file: UploadFile = File(...), actor: str = Form("merchant.importer")) -> dict[str, Any]:
    file_name = file.filename or "merchant-import.csv"
    content = await file.read(MAX_CSV_BYTES + 1)
    content_hash = hashlib.sha256(content).hexdigest()
    if not file_name.lower().endswith(".csv") or file.content_type not in {None, "text/csv", "application/csv", "application/vnd.ms-excel"}:
        import_id = record_import_result(file_name, content_hash, 0, "rejected", ["Only CSV files are accepted."], actor)
        raise HTTPException(status_code=415, detail={"import_id": import_id, "errors": ["Only CSV files are accepted."]})
    try:
        records = validate_csv_bytes(content)
    except CsvValidationError as error:
        import_id = record_import_result(file_name, content_hash, 0, "rejected", error.messages, actor)
        raise HTTPException(status_code=422, detail={"import_id": import_id, "errors": error.messages}) from error
    with database() as connection:
        existing = [record["transaction_id"] for record in records if connection.execute("SELECT 1 FROM transactions WHERE transaction_id = ?", (record["transaction_id"],)).fetchone()]
    if existing:
        errors = [f"Transaction ID already exists and was not overwritten: {transaction_id}." for transaction_id in existing[:50]]
        import_id = record_import_result(file_name, content_hash, len(records), "rejected", errors, actor)
        raise HTTPException(status_code=409, detail={"import_id": import_id, "errors": errors})
    import_id = str(uuid.uuid4())
    try:
        with database() as connection:
            for record in records:
                score_payload = ScoreInput(**record)
                risk = score(score_payload)
                stored_payload = {**record, "import_id": import_id, "ingested_at": utc_now()}
                connection.execute("INSERT INTO transactions VALUES (?, ?, ?, ?)", (record["transaction_id"], json.dumps(stored_payload), json.dumps(risk), utc_now()))
                append_audit(connection, "transaction_scored", "transaction", record["transaction_id"], stored_payload, risk, actor, MODEL_VERSION)
            connection.execute(
                "INSERT INTO imports VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (import_id, file_name[:255], content_hash, len(records), "accepted", 0, "[]", actor, utc_now()),
            )
            summary = {"row_count": len(records), "model_version": MODEL_VERSION, "stored_original_csv": False, "high_risk_count": sum(score(ScoreInput(**record))["tier"] == "high" for record in records)}
            append_audit(connection, "csv_import_accepted", "import", import_id, {"file_name": file_name, "content_hash": content_hash, "rows": len(records)}, summary, actor, MODEL_VERSION)
    except Exception as error:
        import_id = record_import_result(file_name, content_hash, len(records), "rejected", ["The file could not be processed safely; no rows were retained."], actor)
        raise HTTPException(status_code=500, detail={"import_id": import_id, "errors": ["The file could not be processed safely; no rows were retained."]}) from error
    return {"import_id": import_id, "status": "accepted", "row_count": len(records), "content_hash_prefix": content_hash[:12], "high_risk_count": summary["high_risk_count"], "stored_original_csv": False, "message": "Validated rows were scored and retained. The original CSV was not stored."}


@app.get("/imports")
def imports() -> list[dict[str, Any]]:
    with database() as connection:
        return [{**dict(row), "errors": json.loads(row["errors_json"])} for row in connection.execute("SELECT * FROM imports ORDER BY created_at DESC").fetchall()]


@app.get("/transactions")
def transactions(tier: Literal["low", "medium", "high"] | None = None) -> list[dict[str, Any]]:
    with database() as connection:
        records = [dict(row) for row in connection.execute("SELECT * FROM transactions ORDER BY created_at DESC").fetchall()]
    parsed = [{**json.loads(record["payload_json"]), **json.loads(record["risk_json"])} for record in records]
    return [record for record in parsed if tier is None or record["tier"] == tier]


@app.get("/disputes")
def disputes() -> list[dict[str, Any]]:
    with database() as connection:
        return [{**dict(row), "evidence": json.loads(row["evidence_json"]) if row["evidence_json"] else None} for row in connection.execute("SELECT * FROM disputes ORDER BY due_at ASC").fetchall()]


@app.post("/evidence/generate/{dispute_id}")
def generate_evidence(dispute_id: str) -> dict[str, Any]:
    with database() as connection:
        dispute = connection.execute("SELECT * FROM disputes WHERE dispute_id = ?", (dispute_id,)).fetchone()
        if not dispute:
            raise HTTPException(status_code=404, detail="Dispute not found")
        transaction = connection.execute("SELECT payload_json FROM transactions WHERE transaction_id = ?", (dispute["transaction_id"],)).fetchone()
        if not transaction:
            raise HTTPException(status_code=404, detail="Linked transaction not found")
        snapshot = {"transaction": json.loads(transaction["payload_json"]), "dispute": {"dispute_id": dispute["dispute_id"], "reason": dispute["reason"], "amount_cents": dispute["amount_cents"]}}
        snapshot["delivery"] = snapshot["transaction"].pop("delivery", {})
        snapshot["communications"] = snapshot["transaction"].pop("communications", [])
        snapshot["customer_history"] = snapshot["transaction"].pop("customer_history", {})
        claims, model_name = render_claims(snapshot)
        insufficient = [claim["claim"] for claim in claims if claim["type"] == "insufficient_evidence"]
        draft = {"draft_id": str(uuid.uuid4()), "dispute_id": dispute_id, "model_name": model_name, "model_version": MODEL_VERSION, "retrieval_snapshot": snapshot, "claims": claims, "narrative": " ".join(claim["claim"] for claim in claims), "has_sufficient_evidence": len(insufficient) == 0, "insufficient_evidence": insufficient, "created_at": utc_now(), "submission_note": "Draft only — an explicit human approval is required. No external submission occurs in this system."}
        connection.execute("INSERT INTO evidence_drafts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (draft["draft_id"], dispute_id, model_name, MODEL_VERSION, json.dumps(snapshot), json.dumps(claims), draft["narrative"], int(draft["has_sufficient_evidence"]), draft["created_at"]))
        connection.execute("UPDATE disputes SET evidence_json = ?, status = ? WHERE dispute_id = ?", (json.dumps(draft), "awaiting_approval", dispute_id))
        append_audit(connection, "evidence_draft_generated", "dispute", dispute_id, snapshot, {"draft_id": draft["draft_id"], "model_name": model_name, "insufficient_claims": len(insufficient)}, "evidence_agent", MODEL_VERSION)
    return draft


@app.post("/evidence/approve/{dispute_id}")
def approve_evidence(dispute_id: str, decision: DecisionInput) -> dict[str, Any]:
    with database() as connection:
        dispute = connection.execute("SELECT * FROM disputes WHERE dispute_id = ?", (dispute_id,)).fetchone()
        if not dispute or not dispute["evidence_json"]:
            raise HTTPException(status_code=409, detail="A generated evidence draft is required before approval")
        if dispute["status"] not in ("drafted", "awaiting_approval"):
            raise HTTPException(status_code=409, detail="Only an awaiting-approval draft can be approved")
        draft = json.loads(dispute["evidence_json"])
        decision_id = str(uuid.uuid4())
        decided_at = utc_now()
        connection.execute("INSERT INTO human_decisions VALUES (?, ?, ?, ?, ?, ?, ?)", (decision_id, dispute_id, draft["draft_id"], "approved", decision.reason, decision.actor, decided_at))
        connection.execute("UPDATE disputes SET status = ? WHERE dispute_id = ?", ("submitted", dispute_id))
        outcome = {"status": "submitted", "external_submission": False, "message": "Human approval recorded. No payment-network submission was attempted."}
        append_audit(connection, "evidence_approved", "dispute", dispute_id, decision.model_dump(), {**outcome, "decision_id": decision_id}, decision.actor, draft["model_version"])
    return outcome


@app.post("/evidence/reject/{dispute_id}")
def reject_evidence(dispute_id: str, decision: DecisionInput) -> dict[str, Any]:
    if not decision.reason:
        raise HTTPException(status_code=422, detail="A rejection reason is required")
    with database() as connection:
        dispute = connection.execute("SELECT * FROM disputes WHERE dispute_id = ?", (dispute_id,)).fetchone()
        if not dispute or not dispute["evidence_json"]:
            raise HTTPException(status_code=409, detail="A generated evidence draft is required before rejection")
        draft = json.loads(dispute["evidence_json"])
        decision_id = str(uuid.uuid4())
        decided_at = utc_now()
        connection.execute("INSERT INTO human_decisions VALUES (?, ?, ?, ?, ?, ?, ?)", (decision_id, dispute_id, draft["draft_id"], "rejected", decision.reason, decision.actor, decided_at))
        connection.execute("UPDATE disputes SET status = ? WHERE dispute_id = ?", ("rejected", dispute_id))
        outcome = {"status": "rejected", "reason_recorded": True}
        append_audit(connection, "evidence_rejected", "dispute", dispute_id, decision.model_dump(), {**outcome, "decision_id": decision_id}, decision.actor, draft["model_version"])
    return outcome


@app.get("/evidence/export/{dispute_id}.pdf")
def export_evidence_pdf(dispute_id: str, actor: str = "merchant.reviewer") -> Response:
    with database() as connection:
        dispute = connection.execute("SELECT * FROM disputes WHERE dispute_id = ?", (dispute_id,)).fetchone()
        if not dispute or not dispute["evidence_json"]:
            raise HTTPException(status_code=409, detail="Generate and review an evidence draft before exporting it.")
        draft = json.loads(dispute["evidence_json"])
        buffer = BytesIO()
        document = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm)
        styles = getSampleStyleSheet()
        title = ParagraphStyle("EvidenceTitle", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=19, leading=23, textColor=colors.HexColor("#1F2937"), spaceAfter=5)
        eyebrow = ParagraphStyle("EvidenceEyebrow", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=colors.HexColor("#2877B8"), spaceAfter=7)
        body = ParagraphStyle("EvidenceBody", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.2, leading=13, textColor=colors.HexColor("#343A40"))
        claim_style = ParagraphStyle("Claim", parent=body, leftIndent=6, borderWidth=0, spaceAfter=4)
        story = [Paragraph("CHARGEBACKSHIELD · SOURCE-LINKED EVIDENCE", eyebrow), Paragraph("Evidence response draft", title), Paragraph("This document is a reviewer aid generated from retrieved structured records. It is not an external dispute submission and it contains no automatic payment action.", body), Spacer(1, 8)]
        metadata = [
            ["Dispute", escape(dispute_id), "Draft", escape(draft["draft_id"])],
            ["Review status", escape(dispute["status"].replace("_", " ").title()), "Model", escape(draft["model_name"])],
            ["Model version", escape(draft["model_version"]), "Created (UTC)", escape(draft["created_at"])],
        ]
        table = Table(metadata, colWidths=[30 * mm, 55 * mm, 30 * mm, 55 * mm])
        table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F8FC")), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B6D8EF")), ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 8), ("FONT", (2, 0), (2, -1), "Helvetica-Bold", 8), ("FONT", (1, 0), (-1, -1), "Helvetica", 8), ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#2F4556")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        story.extend([table, Spacer(1, 14), Paragraph("Claims and retrieved sources", styles["Heading2"])])
        for index, claim in enumerate(draft["claims"], start=1):
            label = "SUPPORTED" if claim["type"] == "supported" else "INSUFFICIENT EVIDENCE"
            color = "#2877B8" if claim["type"] == "supported" else "#A06A18"
            story.append(Paragraph(f"<b><font color='{color}'>{index:02d} · {label}</font></b><br/>{escape(claim['claim'])}", claim_style))
            sources = claim.get("source_links", [])
            if sources:
                source_rows = [["Source", "Record", "Field", "Retrieved value"]] + [[escape(source["source_entity"]), escape(source["source_record_id"]), escape(source["source_field"]), escape(source["source_value"])] for source in sources]
                source_table = Table(source_rows, colWidths=[28 * mm, 36 * mm, 36 * mm, 67 * mm])
                source_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF6FF")), ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C8D9E5")), ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 7), ("FONT", (0, 1), (-1, -1), "Helvetica", 7), ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#3C4E5B")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
                story.append(source_table)
            else:
                story.append(Paragraph("No source supports this statement; the evidence gap is intentionally disclosed.", body))
            story.append(Spacer(1, 8))
        if draft.get("insufficient_evidence"):
            gaps = "<br/>".join(f"• {escape(item)}" for item in draft["insufficient_evidence"])
            story.extend([Paragraph("Evidence gaps requiring human attention", styles["Heading2"]), Paragraph(gaps, body), Spacer(1, 8)])
        story.append(Paragraph("Safety record: generated evidence remains subject to explicit human review. No payment-network submission, payment action, or fund movement was attempted by ChargebackShield.", body))
        document.build(story)
        payload = buffer.getvalue()
        append_audit(connection, "evidence_draft_exported", "dispute", dispute_id, {"draft_id": draft["draft_id"], "format": "pdf"}, {"bytes": len(payload), "review_status": dispute["status"], "external_submission": False}, actor, draft["model_version"])
    safe_name = "".join(character for character in dispute_id if character.isalnum() or character in {"_", "-"})
    return Response(content=payload, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="chargebackshield-{safe_name}-evidence.pdf"', "Cache-Control": "no-store"})


@app.get("/metrics")
def metrics() -> dict[str, Any]:
    with database() as connection:
        record = connection.execute("SELECT metrics_json FROM evaluation_metrics WHERE model_version = ?", (MODEL_VERSION,)).fetchone()
    if not record:
        raise HTTPException(status_code=404, detail="Evaluation metrics not found")
    return json.loads(record["metrics_json"])


@app.get("/audit-log")
def audit_log(action: str | None = None, actor: str | None = None, entity_type: str | None = None, outcome: str | None = None, start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
    conditions: list[str] = []
    values: list[str] = []
    for field, value in (("action", action), ("actor", actor), ("entity_type", entity_type)):
        if value and value != "all":
            conditions.append(f"{field} = ?")
            values.append(value)
    if start:
        conditions.append("occurred_at >= ?")
        values.append(start)
    if end:
        conditions.append("occurred_at <= ?")
        values.append(end)
    if outcome == "review":
        conditions.append("action IN ('evidence_approved', 'evidence_rejected')")
    elif outcome == "model":
        conditions.append("action = 'transaction_scored'")
    elif outcome == "import":
        conditions.append("action LIKE 'csv_import_%'")
    where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    with database() as connection:
        return [{**dict(row), "output": json.loads(row["output_json"])} for row in connection.execute(f"SELECT * FROM audit_events{where_clause} ORDER BY occurred_at DESC", values).fetchall()]


@app.get("/audit-filters")
def audit_filters() -> dict[str, list[str]]:
    with database() as connection:
        return {
            "actions": [row["action"] for row in connection.execute("SELECT DISTINCT action FROM audit_events ORDER BY action").fetchall()],
            "actors": [row["actor"] for row in connection.execute("SELECT DISTINCT actor FROM audit_events ORDER BY actor").fetchall()],
            "entity_types": [row["entity_type"] for row in connection.execute("SELECT DISTINCT entity_type FROM audit_events ORDER BY entity_type").fetchall()],
        }


@app.get("/audit-analytics")
def audit_analytics(days: Literal["7", "30", "90"] = "30") -> dict[str, Any]:
    period_days = int(days)
    start_day = (datetime.now(UTC) - timedelta(days=period_days - 1)).date()
    day_keys = [(start_day + timedelta(days=index)).isoformat() for index in range(period_days)]
    timeline = {key: {"date": key, "scored": 0, "drafts": 0, "reviews": 0, "imports": 0} for key in day_keys}
    disputes = {key: {"date": key, "opened": 0, "awaiting_review": 0, "reviewed": 0} for key in day_keys}
    with database() as connection:
        events = connection.execute("SELECT action, occurred_at FROM audit_events WHERE occurred_at >= ?", (f"{start_day.isoformat()}T00:00:00+00:00",)).fetchall()
        for event in events:
            key = event["occurred_at"][:10]
            if key not in timeline:
                continue
            if event["action"] == "transaction_scored":
                timeline[key]["scored"] += 1
            elif event["action"] == "evidence_draft_generated":
                timeline[key]["drafts"] += 1
            elif event["action"] in {"evidence_approved", "evidence_rejected"}:
                timeline[key]["reviews"] += 1
            elif event["action"].startswith("csv_import_"):
                timeline[key]["imports"] += 1
                if event["action"] == "csv_import_accepted":
                    timeline[key]["scored"] += int(json.loads(connection.execute("SELECT output_json FROM audit_events WHERE action = ? AND occurred_at = ? LIMIT 1", (event["action"], event["occurred_at"])).fetchone()["output_json"]).get("row_count", 0))
        dispute_rows = connection.execute("SELECT filed_at, status FROM disputes WHERE filed_at >= ?", (f"{start_day.isoformat()}T00:00:00+00:00",)).fetchall()
        for dispute in dispute_rows:
            key = dispute["filed_at"][:10]
            if key not in disputes:
                continue
            disputes[key]["opened"] += 1
            if dispute["status"] == "awaiting_approval":
                disputes[key]["awaiting_review"] += 1
            if dispute["status"] in {"submitted", "rejected"}:
                disputes[key]["reviewed"] += 1
    return {"timeline": list(timeline.values()), "chargeback_trends": list(disputes.values()), "period_days": period_days}
