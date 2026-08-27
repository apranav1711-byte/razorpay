#!/usr/bin/env python3
"""Reproducible ChargebackShield synthetic-data and model-training workflow.

The generator creates synthetic merchant activity only. It never accepts card data,
and no evaluation value should be represented as performance on real merchant data.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier


MODEL_VERSION = "cbs-xgb-calibrated-1.0.0"
FEATURES = [
    "amount_log",
    "amount_zscore",
    "velocity_1h",
    "velocity_24h",
    "velocity_7d",
    "geo_mismatch",
    "customer_is_first_time",
    "odd_hour",
    "new_device",
    "payment_method_risk",
    "merchant_category_risk",
    "velocity_spike",
    "high_amount",
]


@dataclass(frozen=True)
class CostAssumptions:
    currency: str
    false_positive_cost_cents: int
    false_negative_cost_cents: int
    rationale: str


def sigmoid(values: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-values))


def generate_transactions(
    rows: int,
    seed: int,
    first_time_rate: float = 0.12,
    velocity_spike_rate: float = 0.12,
    geo_mismatch_rate: float = 0.14,
    high_amount_anomaly_rate: float = 0.12,
    new_device_base_rate: float = 0.10,
) -> pd.DataFrame:
    """Create Razorpay-shaped synthetic transactions with controlled noisy anomalies."""
    rng = np.random.default_rng(seed)
    customer_count = max(2_000, rows // 5)
    merchant_ids = np.array(["m_aurora", "m_cedar", "m_kite"])
    categories = np.array(["apparel", "electronics", "wellness", "home"])
    payment_methods = np.array(["upi", "card", "netbanking", "wallet"])
    countries = np.array(["IN", "IN", "IN", "AE", "SG", "GB"])
    start = pd.Timestamp("2026-01-01T00:00:00Z")

    occurred_offsets = np.sort(rng.integers(0, 180 * 24 * 60, size=rows))
    occurred_at = start + pd.to_timedelta(occurred_offsets, unit="m")
    customer_index = rng.integers(0, customer_count, size=rows)
    customer_ids = np.array([f"cus_{value:05d}" for value in customer_index])
    merchant_id = rng.choice(merchant_ids, size=rows, p=[0.48, 0.32, 0.20])
    merchant_category = rng.choice(categories, size=rows, p=[0.34, 0.28, 0.22, 0.16])
    payment_method = rng.choice(payment_methods, size=rows, p=[0.42, 0.31, 0.17, 0.10])

    customer_baseline = rng.lognormal(mean=7.1, sigma=0.7, size=customer_count)
    amount_cents = np.maximum(
        1_500,
        np.round(customer_baseline[customer_index] * rng.lognormal(mean=0.0, sigma=0.55, size=rows)),
    ).astype(int)

    historical_tx_count = rng.poisson(lam=5.2, size=rows)
    customer_is_first_time = rng.random(rows) < first_time_rate
    velocity_spike = rng.random(rows) < velocity_spike_rate
    velocity_1h = rng.poisson(0.35, rows) + velocity_spike * rng.integers(5, 13, rows)
    velocity_24h = velocity_1h + rng.poisson(1.8, rows)
    velocity_7d = velocity_24h + rng.poisson(7.5, rows)
    high_amount_anomaly = rng.random(rows) < high_amount_anomaly_rate
    amount_zscore = np.clip(rng.normal(0.0, 1.0, rows) + (amount_cents > np.quantile(amount_cents, 0.9)) * 1.8 + high_amount_anomaly * 2.6, -3.5, 6.0)

    billing_geo_country = rng.choice(countries, size=rows, p=[0.83, 0.03, 0.03, 0.05, 0.04, 0.02])
    geo_mismatch = rng.random(rows) < geo_mismatch_rate
    ip_geo_country = billing_geo_country.copy()
    alternative_country = rng.choice(np.array(["IN", "AE", "SG", "GB", "US"]), size=rows)
    ip_geo_country[geo_mismatch] = alternative_country[geo_mismatch]
    ip_geo_country[(ip_geo_country == billing_geo_country) & geo_mismatch] = "US"

    new_device = (rng.random(rows) < (new_device_base_rate + 0.56 * customer_is_first_time))
    device_fingerprint = np.array([f"dev_{customer_index[i]:05d}_{int(new_device[i])}_{i % 7}" for i in range(rows)])
    hours = pd.DatetimeIndex(occurred_at).hour.to_numpy()
    odd_hour = ((hours < 5) | (hours > 23)).astype(int)
    payment_method_risk = pd.Series(payment_method).map({"upi": 0.10, "netbanking": 0.22, "wallet": 0.36, "card": 0.58}).to_numpy()
    merchant_category_risk = pd.Series(merchant_category).map({"apparel": 0.16, "wellness": 0.22, "home": 0.31, "electronics": 0.51}).to_numpy()

    high_amount = (amount_zscore > 2.0).astype(int)
    risk_logit = (
        -6.25
        + 2.95 * geo_mismatch
        + 2.55 * velocity_spike
        + 1.65 * customer_is_first_time
        + 1.75 * high_amount
        + 0.78 * odd_hour
        + 1.22 * new_device
        + 0.84 * payment_method_risk
        + 0.66 * merchant_category_risk
        + rng.normal(0, 0.34, rows)
    )
    dispute_probability = np.clip(sigmoid(risk_logit), 0.001, 0.92)
    dispute_flag = rng.binomial(1, dispute_probability, rows).astype(bool)
    dispute_reason_choices = np.array(["fraudulent", "product_not_received", "product_not_as_described", "duplicate"])
    dispute_reason = np.where(
        dispute_flag,
        rng.choice(dispute_reason_choices, size=rows, p=[0.49, 0.25, 0.17, 0.09]),
        None,
    )

    delivery_status = np.where(rng.random(rows) < 0.77, "delivered", np.where(rng.random(rows) < 0.45, "shipped", "pending"))
    delivery_status[dispute_flag & (rng.random(rows) < 0.35)] = "not_available"
    communication_count = rng.poisson(1.3, rows)

    return pd.DataFrame(
        {
            "transaction_id": [f"txn_{i:07d}" for i in range(rows)],
            "order_id": [f"ord_{i:07d}" for i in range(rows)],
            "merchant_id": merchant_id,
            "merchant_category": merchant_category,
            "customer_id": customer_ids,
            "amount_cents": amount_cents,
            "currency": "INR",
            "payment_method": payment_method,
            "customer_is_first_time": customer_is_first_time,
            "device_fingerprint": device_fingerprint,
            "ip_geo_country": ip_geo_country,
            "billing_geo_country": billing_geo_country,
            "timestamp": occurred_at.astype(str),
            "delivery_status": delivery_status,
            "communication_count": communication_count,
            "amount_log": np.log1p(amount_cents),
            "amount_zscore": amount_zscore,
            "velocity_1h": velocity_1h,
            "velocity_24h": velocity_24h,
            "velocity_7d": velocity_7d,
            "geo_mismatch": geo_mismatch.astype(int),
            "odd_hour": odd_hour,
            "new_device": new_device.astype(int),
            "payment_method_risk": payment_method_risk,
            "merchant_category_risk": merchant_category_risk,
            "velocity_spike": velocity_spike.astype(int),
            "high_amount": high_amount,
            "dispute_flag": dispute_flag.astype(int),
            "dispute_reason": dispute_reason,
        }
    )


def split_data(frame: pd.DataFrame, seed: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train, temporary = train_test_split(frame, test_size=0.30, random_state=seed, stratify=frame["dispute_flag"])
    validation, test = train_test_split(temporary, test_size=0.50, random_state=seed + 1, stratify=temporary["dispute_flag"])
    return train.copy(), validation.copy(), test.copy()


def build_model(train: pd.DataFrame, validation: pd.DataFrame, seed: int) -> tuple[XGBClassifier, CalibratedClassifierCV]:
    positive = int(train["dispute_flag"].sum())
    negative = int(len(train) - positive)
    imbalance_weight = max(1.0, negative / max(positive, 1))
    model = XGBClassifier(
        n_estimators=260,
        learning_rate=0.045,
        max_depth=4,
        min_child_weight=3,
        subsample=0.86,
        colsample_bytree=0.90,
        reg_lambda=1.2,
        scale_pos_weight=imbalance_weight,
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=seed,
        n_jobs=2,
    )
    model.fit(train[FEATURES], train["dispute_flag"])
    calibrator = CalibratedClassifierCV(model, method="sigmoid", cv="prefit")
    calibrator.fit(validation[FEATURES], validation["dispute_flag"])
    return model, calibrator


def threshold_report(
    y_true: np.ndarray,
    probabilities: np.ndarray,
    assumptions: CostAssumptions,
    thresholds: tuple[float, ...] = (0.01, 0.03, 0.05, 0.10, 0.20, 0.35),
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for threshold in thresholds:
        predictions = (probabilities >= threshold).astype(int)
        tn, fp, fn, tp = confusion_matrix(y_true, predictions, labels=[0, 1]).ravel()
        precision, recall, f1, _ = precision_recall_fscore_support(y_true, predictions, average="binary", zero_division=0)
        rows.append(
            {
                "threshold": threshold,
                "true_positive": int(tp),
                "false_positive": int(fp),
                "true_negative": int(tn),
                "false_negative": int(fn),
                "precision": round(float(precision), 4),
                "recall": round(float(recall), 4),
                "f1": round(float(f1), 4),
                "false_positive_rate": round(float(fp / max(fp + tn, 1)), 4),
                "false_positive_cost_cents": int(fp * assumptions.false_positive_cost_cents),
                "false_negative_cost_cents": int(fn * assumptions.false_negative_cost_cents),
                "total_expected_cost_cents": int(fp * assumptions.false_positive_cost_cents + fn * assumptions.false_negative_cost_cents),
            }
        )
    return rows


def plot_confusion_matrix(matrix: dict[str, int], decision_threshold: float, output_path: Path) -> None:
    figure, axis = plt.subplots(figsize=(5.5, 4.5))
    values = np.array([[matrix["true_negative"], matrix["false_positive"]], [matrix["false_negative"], matrix["true_positive"]]])
    image = axis.imshow(values, cmap="Blues")
    figure.colorbar(image, ax=axis, shrink=0.8)
    axis.set_xticks([0, 1], labels=["Predicted legitimate", "Predicted dispute"])
    axis.set_yticks([0, 1], labels=["Actual legitimate", "Actual dispute"])
    axis.set_title(f"Held-out confusion matrix (validation-selected threshold {decision_threshold:.3f})")
    for row in range(2):
        for col in range(2):
            axis.text(col, row, f"{values[row, col]:,}", ha="center", va="center", color="#132033", fontsize=14, fontweight="bold")
    figure.tight_layout()
    figure.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(figure)


def plot_costs(rows: list[dict[str, Any]], output_path: Path) -> None:
    figure, axis = plt.subplots(figsize=(7, 4.5))
    labels = [f"{row['threshold']:.2f}" for row in rows]
    values = [row["total_expected_cost_cents"] / 100 for row in rows]
    bars = axis.bar(labels, values, color="#3395FF")
    axis.bar_label(bars, labels=[f"₹{value:,.0f}" for value in values], padding=3)
    axis.set_xlabel("Decision threshold")
    axis.set_ylabel("Expected held-out loss (₹)")
    axis.set_title("False-positive / false-negative cost trade-off")
    figure.tight_layout()
    figure.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(figure)


def save_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.sort_values("timestamp").to_csv(path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the ChargebackShield demonstrator risk model.")
    parser.add_argument("--rows", type=int, default=20_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/chargebackshield-artifacts"))
    parser.add_argument("--false-positive-cost-cents", type=int, default=18_000)
    parser.add_argument("--false-negative-cost-cents", type=int, default=260_000)
    parser.add_argument("--first-time-rate", type=float, default=0.12)
    parser.add_argument("--velocity-spike-rate", type=float, default=0.12)
    parser.add_argument("--geo-mismatch-rate", type=float, default=0.14)
    parser.add_argument("--high-amount-anomaly-rate", type=float, default=0.12)
    parser.add_argument("--new-device-base-rate", type=float, default=0.10)
    arguments = parser.parse_args()
    if arguments.rows < 20_000:
        raise ValueError("At least 20,000 rows are required for this demonstrator.")

    output_dir = arguments.output_dir.resolve()
    splits_dir = output_dir / "splits"
    artifacts_dir = output_dir / "model"
    charts_dir = output_dir / "charts"
    for directory in (splits_dir, artifacts_dir, charts_dir):
        directory.mkdir(parents=True, exist_ok=True)

    assumptions = CostAssumptions(
        currency="INR",
        false_positive_cost_cents=arguments.false_positive_cost_cents,
        false_negative_cost_cents=arguments.false_negative_cost_cents,
        rationale="False-positive cost represents review friction and lost conversion; false-negative cost represents chargeback principal, fee, and operations burden. Both values are configurable scenario assumptions, not measured merchant loss.",
    )
    rates = {
        "first_time_rate": arguments.first_time_rate,
        "velocity_spike_rate": arguments.velocity_spike_rate,
        "geo_mismatch_rate": arguments.geo_mismatch_rate,
        "high_amount_anomaly_rate": arguments.high_amount_anomaly_rate,
        "new_device_base_rate": arguments.new_device_base_rate,
    }
    if any(rate < 0 or rate > 1 for rate in rates.values()):
        raise ValueError("All synthetic anomaly rates must be between 0 and 1.")
    frame = generate_transactions(arguments.rows, arguments.seed, **rates)
    train, validation, test = split_data(frame, arguments.seed)
    save_csv(train, splits_dir / "train.csv")
    save_csv(validation, splits_dir / "validation.csv")
    save_csv(test, splits_dir / "held_out_test.csv")

    model, calibrator = build_model(train, validation, arguments.seed)
    validation_probabilities = calibrator.predict_proba(validation[FEATURES])[:, 1]
    validation_candidates = threshold_report(
        validation["dispute_flag"].to_numpy(),
        validation_probabilities,
        assumptions,
        thresholds=tuple(np.round(np.linspace(0.005, 0.35, 70), 4)),
    )
    selected_threshold = min(validation_candidates, key=lambda row: row["total_expected_cost_cents"])["threshold"]
    probabilities = calibrator.predict_proba(test[FEATURES])[:, 1]
    predictions = (probabilities >= selected_threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(test["dispute_flag"], predictions, labels=[0, 1]).ravel()
    precision, recall, f1, _ = precision_recall_fscore_support(test["dispute_flag"], predictions, average="binary", zero_division=0)
    report = threshold_report(test["dispute_flag"].to_numpy(), probabilities, assumptions)
    matrix = {"true_positive": int(tp), "false_positive": int(fp), "true_negative": int(tn), "false_negative": int(fn)}
    metrics: dict[str, Any] = {
        "model_version": MODEL_VERSION,
        "dataset": {"rows": int(arguments.rows), "seed": arguments.seed, "synthetic_anomaly_rates": rates, "dispute_rate": round(float(frame["dispute_flag"].mean()), 4), "split": {"train": len(train), "validation": len(validation), "held_out_test": len(test)}},
        "imbalance_strategy": {"method": "scale_pos_weight", "training_ratio": round((len(train) - int(train["dispute_flag"].sum())) / max(int(train["dispute_flag"].sum()), 1), 2), "calibration": "Platt-style sigmoid calibration fitted only on validation split"},
        "held_out_metrics": {"precision": round(float(precision), 4), "recall": round(float(recall), 4), "f1": round(float(f1), 4), "roc_auc": round(float(roc_auc_score(test["dispute_flag"], probabilities)), 4), "average_precision": round(float(average_precision_score(test["dispute_flag"], probabilities)), 4), "decision_threshold": selected_threshold, "confusion_matrix": matrix},
        "cost_assumptions": asdict(assumptions),
        "threshold_analysis": report,
        "notes": [
            "Held-out test metrics are calculated after training and calibration. The decision threshold is chosen by expected cost on validation data only; the held-out test split is not used to tune model parameters or thresholds.",
            "All data is synthetic and intended solely to demonstrate reproducibility, traceability, calibration, and false-positive-cost reporting.",
        ],
    }
    joblib.dump(model, artifacts_dir / "risk_model.joblib")
    joblib.dump(calibrator, artifacts_dir / "risk_calibrator.joblib")
    explainer = shap.TreeExplainer(model)
    joblib.dump(explainer, artifacts_dir / "shap_tree_explainer.joblib")
    joblib.dump(FEATURES, artifacts_dir / "feature_order.joblib")
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    plot_confusion_matrix(matrix, selected_threshold, charts_dir / "confusion_matrix.png")
    plot_costs(report, charts_dir / "threshold_costs.png")
    print(json.dumps({"output_dir": str(output_dir), "metrics": metrics["held_out_metrics"], "dispute_rate": metrics["dataset"]["dispute_rate"]}, indent=2))


if __name__ == "__main__":
    main()
