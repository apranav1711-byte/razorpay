# Contributing to ChargebackShield

Contributions should preserve ChargebackShield’s core boundary: it is a human-reviewed, evidence-grounded chargeback-support demonstrator. Do not add features that autonomously submit disputes, alter payment states, move money, fabricate evidence, or bypass the explicit review gate.

## Local development

Install the JavaScript dependencies and start the dashboard:

```bash
pnpm install
pnpm dev
```

In a separate terminal, install the pinned Python dependencies and start the reference service:

```bash
python3 -m pip install -r ml/requirements.txt
uvicorn ml.api:app --host 127.0.0.1 --port 8001
```

The web application forwards `/risk-api` requests to the local FastAPI service. For deterministic safety tests, set `CHARGEBACKSHIELD_SKIP_LLM=1`; this intentionally uses the conservative structured fallback rather than making a language-model request.

## Required checks

| Check | Command | Purpose |
|---|---|---|
| Type safety | `pnpm check` | Verifies the TypeScript application. |
| UI/server unit tests | `pnpm test` | Verifies the TypeScript guardrail policy and auth behavior. |
| API safety tests | `CHARGEBACKSHIELD_SKIP_LLM=1 python3 -m unittest ml.test_api` | Verifies scoring, CSV validation, source grounding, evidence gaps, review gates, PDF export, and audit outcomes. |
| Production bundle | `pnpm build` | Verifies that the React/Node production bundle can be generated. |
| Reproducible ML artifacts | `python3 ml/train.py --rows 20000 --seed 42 --output-dir /tmp/chargebackshield-artifacts` | Rebuilds the synthetic model and held-out evaluation artifacts. |

## Pull request expectations

Every behavioral change should explain its safety impact and include suitable automated coverage. New input fields must be considered against the CSV minimization policy. New evidence claims must be source-linkable. New state transitions need an actor, UTC timestamp, input hash, output summary, and model version in the application audit stream.
