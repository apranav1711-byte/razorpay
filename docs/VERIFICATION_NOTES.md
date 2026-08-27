# Verification Notes

## Desktop dashboard review

The six-screen merchant dashboard was visually reviewed at a 1280 × 720 desktop viewport. The overview, risk feed, dispute queue, evidence studio, model transparency, and audit-log routes rendered with the intended dark charcoal sidebar, warm-cream canvas, hand-drawn marker typography, dashed drafting borders, and Razorpay-blue accents.

The risk-distribution stacked area chart and threshold-loss bar chart were confirmed visible after disabling chart entrance animations. The evidence studio visibly separates supported source-linked claims from insufficient-evidence states, while the dispute queue and audit-log copy consistently describe the lack of external submission capability.

## Responsive dashboard review

The overview, evidence studio, and model-transparency routes were reviewed at a 375 × 812 mobile viewport. KPI cards, analytics cards, evidence claims, action controls, and the audit narrative reflow into readable single-column layouts. The transaction table preserves its data column width behind horizontal scrolling rather than silently dropping financial context. The compact navigation header remains visible with a keyboard-accessible sidebar trigger.

Keyboard-focused checks remain part of the final verification pass.

## Architecture artifact

The Mermaid architecture source was rendered successfully to a 3,120 × 724 PNG and uploaded as a project static asset. The repository retains the Mermaid source so reviewers can regenerate the diagram without relying on a binary file.

## Enhancement verification

The Import Data screen was reviewed on desktop. It provides a downloadable schema template, a clear CSV pick area, client-side header preflight, file/row-limit guidance, visible sensitive-data exclusions, and an explicit source-file non-retention notice. The dashboard proxy was exercised with a valid import and returned an accepted result with `stored_original_csv: false`.

The Evidence Studio export route was exercised with a generated draft. The proxy returned a one-page PDF with an attachment filename, `application/pdf` content type, and `Cache-Control: no-store`. The enhanced Audit Intelligence screen was reviewed with live filter data, interactive audit activity and chargeback-trend charts, and a filtered-log export control.

The Import Data, Evidence Studio, and Audit Intelligence routes were also reviewed at a 375 × 812 mobile viewport. Their controls reflow without hiding the data-minimization banner, CSV schema guidance, source-linked claims, reviewer note, evidence-PDF control, advanced filter set, or trend charts.
