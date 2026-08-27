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

export type CsvImportIssue = { code: string; message: string; row?: number | null; field?: string | null };
export type CsvImportPreview = { preview_token: string; file_name: string; row_count: number; headers: string[]; sample_rows: Array<Record<string, string | number | boolean>>; content_hash_prefix: string; expires_at: string; stored_original_csv: false; message: string };
export type CsvImportOutcome = { import_id: string; status: "accepted"; row_count: number; content_hash_prefix: string; high_risk_count: number; stored_original_csv: false; message: string };

export class CsvImportError extends Error {
  constructor(message: string, public readonly status: number, public readonly issues: CsvImportIssue[] = []) { super(message); }
}

function fromApiError(status: number, payload: { detail?: string | { errors?: string[]; issues?: CsvImportIssue[] } } | null): CsvImportError {
  const detail = payload?.detail;
  if (typeof detail === "string") return new CsvImportError(detail, status);
  const errors = detail?.errors ?? [];
  return new CsvImportError(errors[0] || "The CSV could not be processed. No transaction records were retained.", status, detail?.issues ?? errors.map(message => ({ code: "invalid_csv", message })));
}

export function previewMerchantCsv(file: File, onProgress: (percent: number) => void): Promise<CsvImportPreview> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append("file", file);
    const request = new XMLHttpRequest();
    request.open("POST", "/risk-api/imports/preview");
    request.responseType = "json";
    request.upload.onprogress = event => { if (event.lengthComputable) onProgress(Math.max(8, Math.min(62, Math.round((event.loaded / event.total) * 62)))); };
    request.onerror = () => reject(new CsvImportError("The import service is unavailable. No transaction records were retained.", 503));
    request.onload = () => {
      const payload = request.response as CsvImportPreview | { detail?: string | { errors?: string[]; issues?: CsvImportIssue[] } } | null;
      if (request.status >= 200 && request.status < 300) resolve(payload as CsvImportPreview);
      else reject(fromApiError(request.status, payload as { detail?: string | { errors?: string[]; issues?: CsvImportIssue[] } } | null));
    };
    request.send(form);
  });
}

export async function confirmMerchantCsv(previewToken: string): Promise<CsvImportOutcome> {
  const response = await fetch("/risk-api/imports/confirm", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ preview_token: previewToken }) });
  const payload = await response.json().catch(() => null) as CsvImportOutcome | { detail?: string | { errors?: string[]; issues?: CsvImportIssue[] } } | null;
  if (!response.ok) throw fromApiError(response.status, payload as { detail?: string | { errors?: string[]; issues?: CsvImportIssue[] } } | null);
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
