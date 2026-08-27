# Five-Minute Walkthrough Checklist

The walkthrough should demonstrate the product’s **decision-support and accountability** qualities, not imply a promise to win disputes or prevent all losses. Record with the FastAPI service and the dashboard both running. Keep the safety language visible whenever you show a decision point.

| Time | Screen / action | Talking point |
|---:|---|---|
| 0:00–0:30 | Overview dashboard | “Small merchants lose margin and time to disputes. ChargebackShield makes risk and evidence review more explainable; it does not move money or submit disputes.” |
| 0:30–0:55 | Import Data | Show the CSV template, the explicit “never upload” list, and the all-or-nothing validation statement. Explain that accepted data is processed in memory, scored, and retained as structured records while the source CSV is not stored. |
| 0:55–1:20 | `docs/architecture.mmd` or README diagram | “A seeded synthetic pipeline feeds a calibrated XGBoost model with SHAP explanations. A separate evidence workflow retrieves only structured records and validates source-linked claims.” |
| 1:20–1:50 | Transaction Risk Feed | Expand `txn_demo_001`. Point to the high score, geo mismatch, velocity spike, new device, and the **recommendation** label. State that it is a reviewer aid, not an automated block. |
| 1:50–2:15 | Dispute Queue | Show the three queue stages. Highlight the deadline and the human-in-the-loop banner. |
| 2:15–2:55 | Evidence Studio, `dsp_demo_001` | Generate evidence, point to source badges under each claim, and export the PDF. State that the PDF is a reviewer copy with source links and no external submission. Click approval only after saying it records a local review state. |
| 2:55–3:25 | Evidence Studio, `dsp_demo_002` | Generate the missing-evidence case. Show the delivery, communication, and trusted-device insufficiency statements. Explain that the system refuses to fill gaps with plausible language. |
| 3:25–4:00 | Model Transparency | Read the held-out synthetic metrics: precision 32.4%, recall 64.2%, F1 0.431, and ROC–AUC 0.909. Move the cost slider and explain the threshold trade-off. |
| 4:00–4:35 | Audit Intelligence | Change the action and outcome filters, inspect the event and chargeback-trend charts, then export the visible audit rows. Point to actor, model version, UTC time, and append-only policy. |
| 4:35–5:00 | README / closing shot | Be explicit: all benchmark data is synthetic, the manual 20-example grounding rate is not claimed, and production work would include real-data validation, merchant calibration, stronger audit storage, and approved payment-provider integration. |

## Recording preparation

Before recording, run the reproducibility command once, start the FastAPI service on port 8001, start the dashboard, and confirm the app loads the Overview screen. Use `dsp_demo_001` for a fully source-linked response and `dsp_demo_002` for the required graceful failure case. A reviewer should be able to see source links, the human gate, the model-metric caveat, and audit accountability without relying on narration alone.
