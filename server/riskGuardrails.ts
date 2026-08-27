export type EvidenceClaimPolicyInput = {
  type: "supported" | "insufficient_evidence";
  claim: string;
  sourceLinks: Array<{ sourceEntity: string; sourceRecordId: string; sourceField: string; sourceValue: string }>;
};

/**
 * Mirrors the server policy applied by the FastAPI evidence service. A claim is
 * usable evidence only when a named source record supports it; uncertainty must
 * be expressed, never smoothed over with a fabricated assertion.
 */
export function hasSafeEvidenceClaims(claims: EvidenceClaimPolicyInput[]): boolean {
  return claims.length > 0 && claims.every(claim => {
    if (claim.type === "supported") return claim.sourceLinks.length > 0;
    return claim.claim.toLowerCase().includes("insufficient evidence");
  });
}

/** Human approval creates only a local review transition, never an external action. */
export function canRecordApproval(status: string, draftExists: boolean): boolean {
  return draftExists && (status === "drafted" || status === "awaiting_approval");
}

export function hasValidRejectionReason(reason: string | undefined | null): boolean {
  return typeof reason === "string" && reason.trim().length >= 3;
}
