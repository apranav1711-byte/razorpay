import type { EvidenceDraft, FeatureContribution, HeldOutMetrics } from "@shared/types";

export type DemoTransaction = {
  transactionId: string;
  customer: string;
  amount: number;
  method: string;
  occurredAt: string;
  tier: "low" | "medium" | "high";
  riskScore: number;
  action: string;
  factors: FeatureContribution[];
};

export const riskSeries = [
  { label: "Mon", low: 142, medium: 31, high: 11 },
  { label: "Tue", low: 168, medium: 43, high: 16 },
  { label: "Wed", low: 149, medium: 38, high: 13 },
  { label: "Thu", low: 183, medium: 35, high: 10 },
  { label: "Fri", low: 204, medium: 52, high: 19 },
  { label: "Sat", low: 194, medium: 45, high: 14 },
  { label: "Sun", low: 160, medium: 29, high: 9 },
];

const factors = (items: Array<[string, string, number, "raises_risk" | "lowers_risk", string]>): FeatureContribution[] => items.map(([feature, displayName, contribution, direction, evidence]) => ({ feature, displayName, contribution, direction, evidence }));

export const transactions: DemoTransaction[] = [
  { transactionId: "txn_demo_001", customer: "N. Sharma", amount: 184500, method: "Card", occurredAt: "27 Aug, 09:14", tier: "high", riskScore: 0.533, action: "Hold for review", factors: factors([["geo_mismatch", "Geo mismatch", 1.02, "raises_risk", "IP geography differs from billing country."], ["velocity_spike", "Velocity spike", 0.78, "raises_risk", "Eight transactions observed in one hour."], ["new_device", "New device", 0.44, "raises_risk", "No trusted device match."], ["amount_zscore", "Amount anomaly", 0.31, "raises_risk", "Amount is 3.1σ above prior pattern."]]) },
  { transactionId: "txn_demo_003", customer: "R. Mehta", amount: 136000, method: "Card", occurredAt: "27 Aug, 08:02", tier: "high", riskScore: 0.424, action: "Hold for review", factors: factors([["high_amount", "High amount", 0.94, "raises_risk", "Controlled high-amount indicator."], ["customer_is_first_time", "First-time customer", 0.61, "raises_risk", "No prior customer history."], ["geo_mismatch", "Geo mismatch", 0.55, "raises_risk", "IP and billing country differ."], ["odd_hour", "Normal transaction time", -0.13, "lowers_risk", "The transaction did not occur overnight."]]) },
  { transactionId: "txn_2h1a7", customer: "A. Iyer", amount: 59600, method: "Wallet", occurredAt: "27 Aug, 07:38", tier: "medium", riskScore: 0.181, action: "Verify", factors: factors([["new_device", "New device", 0.36, "raises_risk", "First observed device for customer."], ["payment_method_risk", "Payment-method baseline", 0.18, "raises_risk", "Synthetic wallet baseline."], ["velocity_24h", "24-hour velocity", 0.15, "raises_risk", "Three transactions in last 24 hours."], ["customer_is_first_time", "Known customer", -0.21, "lowers_risk", "Prior customer history exists."]]) },
  { transactionId: "txn_7pz54", customer: "K. Bose", amount: 92000, method: "UPI", occurredAt: "27 Aug, 06:50", tier: "low", riskScore: 0.071, action: "Allow", factors: factors([["customer_is_first_time", "Known customer", -0.32, "lowers_risk", "Seven prior legitimate transactions."], ["new_device", "Trusted device", -0.28, "lowers_risk", "Device matches prior activity."], ["geo_mismatch", "Geo matched", -0.24, "lowers_risk", "IP matches billing country."], ["amount_zscore", "Expected amount", -0.16, "lowers_risk", "Amount is within customer range."]]) },
];

export type DemoDispute = { disputeId: string; transactionId: string; customer: string; reason: string; amount: number; status: "new" | "awaiting_approval" | "submitted" | "rejected"; dueText: string; dueTone: "urgent" | "soon" | "safe"; };
export const disputes: DemoDispute[] = [
  { disputeId: "dsp_demo_002", transactionId: "txn_demo_003", customer: "R. Mehta", reason: "Product not received", amount: 136000, status: "new", dueText: "1 day remaining", dueTone: "urgent" },
  { disputeId: "dsp_demo_001", transactionId: "txn_demo_001", customer: "N. Sharma", reason: "Fraudulent", amount: 184500, status: "awaiting_approval", dueText: "5 days remaining", dueTone: "soon" },
  { disputeId: "dsp_29b0", transactionId: "txn_9mv8q", customer: "T. Das", reason: "Duplicate", amount: 41300, status: "submitted", dueText: "Submitted today", dueTone: "safe" },
];

export const heldOutMetrics: HeldOutMetrics = {
  precision: 0.324, recall: 0.642, f1: 0.4306, rocAuc: 0.9086,
  confusionMatrix: { truePositive: 104, falsePositive: 217, trueNegative: 2621, falseNegative: 58 },
  thresholdAnalysis: [
    { threshold: 0.01, precision: 0.1222, recall: 0.9451, falsePositiveRate: 0.3925, falsePositiveCost: 20034000, falseNegativeCost: 2340000, totalExpectedCost: 22374000 },
    { threshold: 0.03, precision: 0.1728, recall: 0.8354, falsePositiveRate: 0.2313, falsePositiveCost: 11808000, falseNegativeCost: 7020000, totalExpectedCost: 18828000 },
    { threshold: 0.05, precision: 0.2073, recall: 0.7927, falsePositiveRate: 0.1752, falsePositiveCost: 8946000, falseNegativeCost: 8840000, totalExpectedCost: 17786000 },
    { threshold: 0.10, precision: 0.2929, recall: 0.7073, falsePositiveRate: 0.0987, falsePositiveCost: 5040000, falseNegativeCost: 12480000, totalExpectedCost: 17520000 },
    { threshold: 0.20, precision: 0.3852, recall: 0.6037, falsePositiveRate: 0.0557, falsePositiveCost: 2844000, falseNegativeCost: 16900000, totalExpectedCost: 19744000 },
    { threshold: 0.35, precision: 0.5168, recall: 0.4695, falsePositiveRate: 0.0254, falsePositiveCost: 1296000, falseNegativeCost: 22620000, totalExpectedCost: 23916000 },
  ],
};

export const evidenceDraft: EvidenceDraft = {
  draftId: "draft_7a3f", disputeId: "dsp_demo_001", hasSufficientEvidence: true, insufficientEvidence: [], createdAt: "2026-08-27T07:56:11Z",
  narrative: "The disputed transaction amount was ₹1,845.00. The available delivery record indicates that the order was delivered and has a tracking reference. Customer communication records are available for the transaction. The current device matches a device recorded on prior legitimate customer activity.",
  retrievalSnapshot: { transaction: "txn_demo_001", delivery: "delivered", communications: 1, customerHistory: "2 prior legitimate transactions" },
  claims: [
    { claimId: "c1", type: "supported", claim: "The disputed transaction amount was ₹1,845.00.", sourceLinks: [{ sourceEntity: "transaction", sourceRecordId: "txn_demo_001", sourceField: "amount_cents", sourceValue: "184500" }] },
    { claimId: "c2", type: "supported", claim: "The available delivery record indicates that the order was delivered and has a tracking reference.", sourceLinks: [{ sourceEntity: "delivery", sourceRecordId: "dlv_90122", sourceField: "status", sourceValue: "delivered" }, { sourceEntity: "delivery", sourceRecordId: "dlv_90122", sourceField: "tracking_reference", sourceValue: "TRK-90122" }] },
    { claimId: "c3", type: "supported", claim: "Customer communication records are available for the transaction.", sourceLinks: [{ sourceEntity: "communication", sourceRecordId: "msg_001", sourceField: "summary", sourceValue: "Order confirmation sent to customer." }] },
    { claimId: "c4", type: "supported", claim: "The current device matches a device recorded on prior legitimate customer activity.", sourceLinks: [{ sourceEntity: "customer_history", sourceRecordId: "txn_demo_001", sourceField: "device_match", sourceValue: "true" }] },
  ],
};

export const auditEntries = [
  { action: "evidence_approved", entity: "dsp_demo_001", actor: "merchant.reviewer@demo", time: "2026-08-27 07:56:11 UTC", model: "cbs-xgb-calibrated-1.0.0", result: "Local review state set to submitted; no external submission." },
  { action: "evidence_draft_generated", entity: "dsp_demo_001", actor: "evidence_agent", time: "2026-08-27 07:56:10 UTC", model: "cbs-xgb-calibrated-1.0.0", result: "4 source-linked claims; no insufficient-evidence flags." },
  { action: "transaction_scored", entity: "txn_demo_001", actor: "risk_model", time: "2026-08-27 07:55:32 UTC", model: "cbs-xgb-calibrated-1.0.0", result: "0.533 high-risk score; hold-for-review recommendation." },
  { action: "evidence_draft_generated", entity: "dsp_demo_002", actor: "evidence_agent", time: "2026-08-27 07:44:06 UTC", model: "cbs-xgb-calibrated-1.0.0", result: "Explicitly recorded missing delivery, communication, and trusted-device evidence." },
];
