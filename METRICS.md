# ChargebackShield Evaluation Report

## Scope and evaluation discipline

This report documents the results of the reproducible **synthetic** benchmark committed with the project. It evaluates a calibrated XGBoost classifier under a controlled generator; it does **not** estimate production fraud, chargeback, revenue-recovery, or operational performance. The generator uses a fixed seed, configurable anomaly prevalence, and a stratified 70/15/15 split. Model fitting occurs on 14,000 training records, sigmoid calibration and threshold selection occur on 3,000 validation records, and the final report is calculated on a separate 3,000-row held-out test partition.

| Configuration | Value |
|---|---:|
| Dataset size | 20,000 synthetic transactions |
| Random seed | 42 |
| Synthetic dispute rate | 5.42% |
| Train / validation / held-out rows | 14,000 / 3,000 / 3,000 |
| Imbalance approach | `scale_pos_weight` = 17.45 on training data |
| Calibration | Validation-only Platt-style sigmoid calibration |
| Operating threshold | 0.120, selected on validation expected cost |

## Held-out classification results

| Measure | Result | Interpretation |
|---|---:|---|
| Precision | 0.3240 | Of transactions classified positive at the selected point, 32.4% carried the synthetic dispute label. |
| Recall | 0.6420 | The classifier surfaced 64.2% of held-out synthetic disputes. |
| F1 | 0.4306 | Harmonic balance of precision and recall. |
| ROC–AUC | 0.9086 | Ranking separation on the held-out synthetic labels. |
| Average precision | 0.4630 | Precision-recall summary on the held-out synthetic labels. |
| True positive / false positive | 104 / 217 | Correctly flagged and over-flagged positive decisions. |
| True negative / false negative | 2,621 / 58 | Correctly allowed and missed positive decisions. |

The figures are intentionally left without any claim that they transfer to a real merchant. The synthetic data-generator design creates labels from observable anomaly patterns plus noise. A real deployment would require time-based splits, feature-drift monitoring, merchant-specific calibration, group fairness review, and evaluation against ground-truth dispute outcomes before operational use.

## Cost scenario analysis

The benchmark assumes a false positive costs ₹180 in review friction or lost conversion and a false negative costs ₹2,600 in principal, fee, and operational burden. These are explicit scenario levers exposed by CLI arguments, not business facts. The values below show how the assumed costs respond to threshold changes on the held-out test data.

| Threshold | Precision | Recall | False-positive rate | FP scenario cost | FN scenario cost | Total scenario cost |
|---:|---:|---:|---:|---:|---:|---:|
| 0.01 | 12.85% | 95.68% | 37.03% | ₹189,180 | ₹18,200 | ₹207,380 |
| 0.03 | 19.50% | 87.04% | 20.51% | ₹104,760 | ₹54,600 | ₹159,360 |
| 0.05 | 22.63% | 76.54% | 14.94% | ₹76,320 | ₹98,800 | ₹175,120 |
| 0.10 | 29.28% | 65.43% | 9.02% | ₹46,080 | ₹145,600 | ₹191,680 |
| 0.20 | 39.60% | 61.11% | 5.32% | ₹27,180 | ₹163,800 | ₹190,980 |
| 0.35 | 50.34% | 45.68% | 2.57% | ₹13,140 | ₹228,800 | ₹241,940 |

The scenario-cost minimum at 0.03 should not be read as a production-policy recommendation. A merchant’s real review cost, chargeback fee, amount distribution, customer-experience goals, and risk tolerance determine the appropriate decision policy. The dashboard exposes a cost multiplier to make that sensitivity visible instead of presenting a single “correct” threshold.

## Evidence-agent grounding evaluation

The implementation validates each `supported` claim programmatically: it must have one or more source links, and each claimed source key must come from the retrieved structured snapshot. Required evidence gaps are added as `insufficient_evidence` claims when delivery completion, communication, or trusted-device support is unavailable. The FastAPI test suite covers both a fully sourced draft and the required insufficient-evidence path.

No 20-example manual grounding percentage is reported in this repository because such a review was not performed during the build. Reporting a fabricated sample size or rate would conflict with the project’s transparency objective. For the recorded demo, show the `dsp_demo_002` failure scenario: it returns three explicit insufficiency statements for unavailable delivery confirmation, communication, and prior trusted-device evidence.

## Reproduction command

```bash
python3 ml/train.py --rows 20000 --seed 42 --output-dir /tmp/chargebackshield-artifacts \
  --geo-mismatch-rate 0.14 --velocity-spike-rate 0.12 \
  --first-time-rate 0.12 --high-amount-anomaly-rate 0.12 \
  --new-device-base-rate 0.10 \
  --false-positive-cost-cents 18000 --false-negative-cost-cents 260000
```

The expected committed outputs are stored at `ml/metrics.example.json` and `ml/artifacts/`. The command regenerates a comparable artifact set under the same library versions and seed.
