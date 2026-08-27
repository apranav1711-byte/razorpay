# Configuration Guide

ChargebackShield is configured primarily by the managed platform environment. **Never commit a populated `.env` file, API key, access token, database password, payment credential, or merchant dataset to the repository.**

## Runtime variables

| Variable | Required in local development | Purpose | Safe value guidance |
|---|---|---|---|
| `START_RISK_API` | Optional | Starts the bundled FastAPI reference service when the Node app runs in a combined container. | Use `true` only in the combined container deployment. |
| `CHARGEBACKSHIELD_API_DB` | Optional | Selects the local SQLite demonstrator database path. | Use a local disposable path; do not use as a production datastore. |
| `CHARGEBACKSHIELD_SKIP_LLM` | Recommended for tests | Replaces live language-model calls with the deterministic conservative fallback. | Use `1` for automated testing and CI. |
| `BUILT_IN_FORGE_API_URL` | Managed runtime only | Platform-provided server-side model gateway base URL. | Never hard-code it. |
| `BUILT_IN_FORGE_API_KEY` | Managed runtime only | Platform-provided server-side model gateway credential. | Never expose it in client code or commit it. |

## Local setup

For the dashboard-only interface, use `pnpm dev`. For the interactive evidence and CSV workflow, also run the FastAPI reference service on `127.0.0.1:8001` as described in [`CONTRIBUTING.md`](../CONTRIBUTING.md). The Vite/Express proxy forwards browser calls under `/risk-api` to that local service.

When you run tests, use the following command so that test cases are deterministic and do not make model requests:

```bash
CHARGEBACKSHIELD_SKIP_LLM=1 python3 -m unittest ml.test_api
```

## Production boundary

The included environment variables and SQLite store support a buildathon demonstration, not a production data deployment. Before using merchant data operationally, configure managed encrypted storage, least-privilege access, monitored secret management, retention enforcement, production database backups, tenant isolation, and a reviewed incident-response process.
