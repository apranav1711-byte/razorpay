import { AlertTriangle, CheckCircle2, FileSpreadsheet, FileUp, LockKeyhole, ShieldCheck, Sparkles, XCircle } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { ScreenHeader } from "@/components/ScreenHeader";
import { importMerchantCsv, type CsvImportOutcome } from "@/lib/riskApi";

const REQUIRED = ["transaction_id", "amount_cents"];
const SENSITIVE = ["card_number", "card number", "pan", "cvv", "cvc", "expiry", "expiration", "upi_pin", "upi pin", "email", "phone", "mobile", "address", "postal", "pin_code"];
type Preflight = { headers: string[]; errors: string[]; estimatedRows: number };

function inspectFile(file: File): Promise<Preflight> {
  return file.text().then(text => {
    const lines = text.split(/\r?\n/).filter(Boolean);
    const headers = (lines[0] ?? "").split(",").map(header => header.trim().toLowerCase().replace(/[- ]/g, "_"));
    const errors: string[] = [];
    if (file.size > 5 * 1024 * 1024) errors.push("This file is larger than the 5 MB import limit.");
    if (!file.name.toLowerCase().endsWith(".csv")) errors.push("Select a CSV file.");
    REQUIRED.filter(header => !headers.includes(header)).forEach(header => errors.push(`Required column missing: ${header}.`));
    headers.filter(header => SENSITIVE.some(marker => header.includes(marker.replace(/[- ]/g, "_")))).forEach(header => errors.push(`Sensitive column blocked: ${header}.`));
    if (lines.length - 1 > 5000) errors.push("This file has more than 5,000 data rows.");
    return { headers, errors, estimatedRows: Math.max(0, lines.length - 1) };
  });
}

function downloadTemplate() {
  const csv = "transaction_id,amount_cents,amount_zscore,velocity_1h,velocity_24h,velocity_7d,geo_mismatch,customer_is_first_time,new_device,payment_method_risk,merchant_category_risk\ntxn_2026_0001,184500,3.1,8,11,17,true,true,true,0.58,0.51\ntxn_2026_0002,92000,1.8,1,3,10,false,false,false,0.10,0.16\n";
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  const link = document.createElement("a"); link.href = url; link.download = "chargebackshield-import-template.csv"; link.click(); URL.revokeObjectURL(url);
}

export default function ImportData() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null); const [preflight, setPreflight] = useState<Preflight | null>(null); const [working, setWorking] = useState(false); const [outcome, setOutcome] = useState<CsvImportOutcome | null>(null); const [apiError, setApiError] = useState<string | null>(null);
  const accepted = !!file && !!preflight && preflight.errors.length === 0;
  const fileLabel = useMemo(() => file ? `${file.name} · ${(file.size / 1024).toFixed(1)} KB` : "No file selected", [file]);
  const choose = async (selected: File | null) => { setOutcome(null); setApiError(null); setFile(selected); setPreflight(selected ? await inspectFile(selected) : null); };
  const process = async () => { if (!file || !accepted) return; setWorking(true); setApiError(null); try { setOutcome(await importMerchantCsv(file)); } catch (error) { setApiError(error instanceof Error ? error.message : "Import failed."); } finally { setWorking(false); } };
  return <div className="screen-shell import-screen"><ScreenHeader eyebrow="Data workspace / controlled intake" title="Bring signals, not secrets."><button className="outline-button" onClick={downloadTemplate}><FileSpreadsheet size={16} />Download template</button></ScreenHeader>
    <section className="import-hero"><div><span className="stamp"><ShieldCheck size={16} />Data minimization on</span><h2>Score your merchant transactions<br />without uploading payment data.</h2><p>The CSV is validated in memory, scored with model version 1.0.0, and reduced to structured transaction records. The original file body is not stored.</p></div><div className="import-flow"><span>CSV headers</span><i /><span>Validation</span><i /><span>Scored records</span><i /><span>UTC audit event</span></div></section>
    <div className="import-layout"><section className="sketch-card upload-card"><div className="upload-heading"><div><p className="eyebrow">Step 01 / pick a clean file</p><h2>CSV intake</h2></div><LockKeyhole size={19} /></div><input ref={inputRef} className="file-input-hidden" type="file" accept=".csv,text/csv" onChange={event => choose(event.target.files?.[0] ?? null)} /><button className="dropzone" onClick={() => inputRef.current?.click()}><span className="drop-icon"><FileUp size={24} /></span><strong>{file ? "Choose another CSV" : "Choose a merchant CSV"}</strong><small>UTF-8 CSV · up to 5 MB · 5,000 rows</small><em>{fileLabel}</em></button>{file && <button className="clear-file" onClick={() => choose(null)}>Clear selected file</button>}
      {preflight && <div className={accepted ? "preflight preflight-ok" : "preflight preflight-error"}>{accepted ? <CheckCircle2 size={18} /> : <AlertTriangle size={18} />}<div><strong>{accepted ? "Header check passed" : "Import needs attention"}</strong>{accepted ? <span>{preflight.estimatedRows.toLocaleString()} data rows detected. Processing will score rows and create one import audit event.</span> : preflight.errors.map(error => <span key={error}>{error}</span>)}</div></div>}
      <button className="solid-button process-button" disabled={!accepted || working} onClick={process}>{working ? <Sparkles className="animate-spin" size={16} /> : <ShieldCheck size={16} />}{working ? "Validating and scoring…" : "Validate & process CSV"}</button>{apiError && <div className="import-result result-error"><XCircle size={18} /><div><strong>Import was not processed</strong><p>{apiError}</p></div></div>}{outcome && <div className="import-result result-ok"><CheckCircle2 size={18} /><div><strong>{outcome.row_count.toLocaleString()} transactions processed safely</strong><p>{outcome.high_risk_count} high-tier transactions surfaced. Original CSV retained: <b>No</b>. Audit reference: <code>{outcome.import_id.slice(0, 8)}</code>.</p></div></div>}</section>
      <aside className="import-policy sketch-card"><p className="eyebrow">Intake guardrails</p><h2>What we accept</h2><div className="policy-rows"><div><span className="policy-number">01</span><p><strong>Minimal transaction signals</strong><small>Transaction ID, amount, risk features, and optional pseudonymous context.</small></p></div><div><span className="policy-number">02</span><p><strong>All-or-nothing validation</strong><small>Invalid or ambiguous rows reject the full file. Nothing is partially scored.</small></p></div><div><span className="policy-number">03</span><p><strong>Accountability retained</strong><small>File metadata, content hash, outcome, actor, and UTC time are appended to the audit trail.</small></p></div></div><div className="blocked-fields"><AlertTriangle size={15} /><div><strong>Never upload</strong><span>Card numbers, PAN, CVV/CVC, UPI PIN, customer contact data, or addresses.</span></div></div></aside>
    </div>
    <section className="sketch-card column-guide"><div className="card-heading"><div><p className="eyebrow">Schema guide / minimum viable columns</p><h2>Make the model legible from day one</h2></div><span className="schema-chip">2 required · 12 supported signals</span></div><div className="column-grid"><div><code>transaction_id</code><p>Unique pseudonymous transaction reference.</p><b>Required</b></div><div><code>amount_cents</code><p>Integer amount in the smallest currency unit.</p><b>Required</b></div><div><code>velocity_1h</code><p>Observed transaction count in the last hour.</p><b>Recommended</b></div><div><code>geo_mismatch</code><p>Whether stored IP and billing geographies differ.</p><b>Recommended</b></div><div><code>new_device</code><p>Whether the device is absent from prior customer history.</p><b>Recommended</b></div><div><code>merchant_category_risk</code><p>Approved 0–1 merchant category baseline.</p><b>Optional</b></div></div></section>
  </div>;
}
