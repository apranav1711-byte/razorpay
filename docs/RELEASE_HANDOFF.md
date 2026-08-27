# Repository Handoff Checklist

This repository is prepared as a **buildathon-ready demonstrator**. It includes the full source code, synthetic risk-model pipeline and artifacts, FastAPI reference service, React dashboard, automated safety tests, architecture, evaluation report, data-import contract, and a five-minute walkthrough.

| Handoff item | Location | Status |
|---|---|---|
| Product overview and setup | [`README.md`](../README.md) | Complete |
| Architecture and data accountability boundary | [`ARCHITECTURE.md`](../ARCHITECTURE.md), [`DATA_MODEL.md`](DATA_MODEL.md) | Complete |
| API routes and error behavior | [`API_REFERENCE.md`](API_REFERENCE.md) | Complete |
| Metrics and model limitations | [`METRICS.md`](../METRICS.md) | Complete |
| Security and human-review controls | [`SECURITY.md`](../SECURITY.md) | Complete |
| CSV fields and minimization contract | [`IMPORT_CONTRACT.md`](IMPORT_CONTRACT.md) | Complete |
| Walkthrough run sheet | [`WALKTHROUGH.md`](WALKTHROUGH.md) | Complete |
| Validation observations | [`VERIFICATION_NOTES.md`](VERIFICATION_NOTES.md) | Complete |
| Local contribution/testing guide | [`CONTRIBUTING.md`](../CONTRIBUTING.md) | Complete |

## What reviewers should run

```bash
pnpm install
pnpm check
pnpm test
pnpm build
CHARGEBACKSHIELD_SKIP_LLM=1 python3 -m unittest ml.test_api
```

For the UI walkthrough, start `uvicorn ml.api:app --host 127.0.0.1 --port 8001` alongside `pnpm dev`, then open the dashboard. Use the Import Data screen to inspect CSV restrictions, `dsp_demo_001` for a supported evidence draft/PDF, and `dsp_demo_002` for the explicit insufficient-evidence path.

> This is not production-ready payment infrastructure. Before connecting any real payment account or operational merchant data, complete an appropriate security, privacy, compliance, access-control, retention, data-quality, model-validation, and incident-response review.
