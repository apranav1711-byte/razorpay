export type RiskTier = "low" | "medium" | "high";
export type RecommendedAction = "allow" | "verify" | "hold_for_review";
export type DisputeStatus = "new" | "drafted" | "awaiting_approval" | "submitted" | "rejected";

export type FeatureContribution = {
  feature: string;
  displayName: string;
  contribution: number;
  direction: "raises_risk" | "lowers_risk";
  evidence: string;
};

export type SourceLink = {
  sourceEntity: "transaction" | "order" | "delivery" | "communication" | "customer_history";
  sourceRecordId: string;
  sourceField: string;
  sourceValue: string;
};

export type EvidenceClaim = {
  claimId: string;
  type: "supported" | "insufficient_evidence";
  claim: string;
  sourceLinks: SourceLink[];
};

export type EvidenceDraft = {
  draftId: string;
  disputeId: string;
  narrative: string;
  claims: EvidenceClaim[];
  hasSufficientEvidence: boolean;
  insufficientEvidence: string[];
  retrievalSnapshot: Record<string, unknown>;
  createdAt: string;
};

export type HeldOutMetrics = {
  precision: number;
  recall: number;
  f1: number;
  rocAuc: number;
  confusionMatrix: { truePositive: number; falsePositive: number; trueNegative: number; falseNegative: number };
  thresholdAnalysis: Array<{
    threshold: number;
    precision: number;
    recall: number;
    falsePositiveRate: number;
    falsePositiveCost: number;
    falseNegativeCost: number;
    totalExpectedCost: number;
  }>;
};
