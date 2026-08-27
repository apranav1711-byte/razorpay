import { describe, expect, it } from "vitest";
import { canRecordApproval, hasSafeEvidenceClaims, hasValidRejectionReason } from "./riskGuardrails";

describe("ChargebackShield guardrail policy", () => {
  it("accepts source-linked claims and explicit evidence gaps", () => {
    expect(hasSafeEvidenceClaims([
      { type: "supported", claim: "A delivery record is available.", sourceLinks: [{ sourceEntity: "delivery", sourceRecordId: "dlv_1", sourceField: "status", sourceValue: "delivered" }] },
      { type: "insufficient_evidence", claim: "Insufficient evidence for customer communication.", sourceLinks: [] },
    ])).toBe(true);
  });

  it("rejects a supported claim without a source link", () => {
    expect(hasSafeEvidenceClaims([{ type: "supported", claim: "The order was delivered.", sourceLinks: [] }])).toBe(false);
  });

  it("requires an existing pending draft before local approval can be recorded", () => {
    expect(canRecordApproval("new", true)).toBe(false);
    expect(canRecordApproval("awaiting_approval", false)).toBe(false);
    expect(canRecordApproval("awaiting_approval", true)).toBe(true);
    expect(canRecordApproval("submitted", true)).toBe(false);
  });

  it("requires a meaningful rejection reason", () => {
    expect(hasValidRejectionReason(undefined)).toBe(false);
    expect(hasValidRejectionReason(" ")).toBe(false);
    expect(hasValidRejectionReason("Need delivery proof before proceeding")).toBe(true);
  });
});
