import type { EvidenceDraft } from "@shared/types";

type ApiClaim = { claim_id: string; type: "supported" | "insufficient_evidence"; claim: string; source_links: Array<{ source_entity: "transaction" | "order" | "delivery" | "communication" | "customer_history"; source_record_id: string; source_field: string; source_value: string }> };
type ApiDraft = { draft_id: string; dispute_id: string; model_name: string; retrieval_snapshot: Record<string, unknown>; claims: ApiClaim[]; narrative: string; has_sufficient_evidence: boolean; insufficient_evidence: string[]; created_at: string };

function toDraft(value: ApiDraft): EvidenceDraft {
  return {
    draftId: value.draft_id,
    disputeId: value.dispute_id,
    narrative: value.narrative,
    claims: value.claims.map(claim => ({
      claimId: claim.claim_id,
      type: claim.type,
      claim: claim.claim,
      sourceLinks: claim.source_links.map(link => ({ sourceEntity: link.source_entity, sourceRecordId: link.source_record_id, sourceField: link.source_field, sourceValue: link.source_value })),
    })),
    hasSufficientEvidence: value.has_sufficient_evidence,
    insufficientEvidence: value.insufficient_evidence,
    retrievalSnapshot: value.retrieval_snapshot,
    createdAt: value.created_at,
  };
}

export async function generateEvidence(disputeId: string): Promise<EvidenceDraft> {
  const response = await fetch(`/risk-api/evidence/generate/${disputeId}`, { method: "POST" });
  if (!response.ok) throw new Error("The evidence service is unavailable. Start the FastAPI service before generating a live draft.");
  return toDraft(await response.json() as ApiDraft);
}

export async function approveEvidence(disputeId: string): Promise<string> {
  const response = await fetch(`/risk-api/evidence/approve/${disputeId}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ actor: "merchant.reviewer@demo", reason: "Reviewed in merchant dashboard" }) });
  if (!response.ok) throw new Error("Approval could not be recorded. Generate a draft first.");
  const data = await response.json() as { message: string };
  return data.message;
}

export async function rejectEvidence(disputeId: string, reason: string): Promise<void> {
  const response = await fetch(`/risk-api/evidence/reject/${disputeId}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ actor: "merchant.reviewer@demo", reason }) });
  if (!response.ok) throw new Error("A recorded rejection reason is required.");
}

export type CsvImportOutcome = { import_id: string; status: "accepted"; row_count: number; content_hash_prefix: string; high_risk_count: number; stored_original_csv: false; message: string };

export async function importMerchantCsv(file: File): Promise<CsvImportOutcome> {
  const form = new FormData();
  form.append("file", file);
  form.append("actor", "merchant.importer");
  const response = await fetch("/risk-api/imports/csv", { method: "POST", body: form });
  const payload = await response.json().catch(() => null) as CsvImportOutcome | { detail?: { errors?: string[] } } | null;
  if (!response.ok) {
    const errors = payload && "detail" in payload ? payload.detail?.errors : undefined;
    throw new Error(errors?.join(" ") || "The import service is unavailable. No transaction records were retained.");
  }
  return payload as CsvImportOutcome;
}

export async function downloadEvidencePdf(disputeId: string): Promise<void> {
  const response = await fetch(`/risk-api/evidence/export/${disputeId}.pdf?actor=merchant.reviewer%40demo`);
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(payload?.detail || "Generate a source-linked draft before exporting it.");
  }
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = `chargebackshield-${disputeId}-evidence.pdf`;
  link.click();
  URL.revokeObjectURL(url);
}
