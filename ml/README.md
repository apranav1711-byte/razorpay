# Reproducible Risk-Model Workflow

Run the synthetic workflow with Python 3.11 or later from the repository root:

```bash
python3 -m pip install -r ml/requirements.txt
python3 ml/train.py --rows 20000 --seed 42 --output-dir /tmp/chargebackshield-artifacts \
  --geo-mismatch-rate 0.14 --velocity-spike-rate 0.12 \
  --first-time-rate 0.12 --high-amount-anomaly-rate 0.12 \
  --new-device-base-rate 0.10
```

The job writes `train.csv`, `validation.csv`, and `held_out_test.csv` separately, along with a trained XGBoost model, sigmoid probability calibrator, SHAP TreeExplainer, held-out metrics, and two evaluation charts. Features include transaction velocity, transaction-relative amount, geo mismatch, new-device and first-time-customer indicators, payment/category risk encodings, and explicit engineered velocity-spike and high-amount flags. The rate flags make controlled anomaly prevalence visible, adjustable, and recorded in `metrics.json`; the `--false-positive-cost-cents` and `--false-negative-cost-cents` flags do the same for loss assumptions.

> The generated data is fully synthetic. The metrics demonstrate the reproducibility and evaluation discipline of the system; they must not be presented as production performance on Razorpay or merchant data.

## FastAPI reference endpoints

The reference API loads the saved XGBoost, calibration, and SHAP artifacts and exposes the requested local API contract. Its state-changing approval endpoint records a human-reviewed state only and deliberately has no external submission integration.

```bash
python3 -m pip install -r ml/requirements.txt
uvicorn ml.api:app --reload --port 8000
```

Open `http://127.0.0.1:8000/docs` to inspect and exercise `POST /score`, `GET /transactions`, `GET /disputes`, `POST /evidence/generate/{dispute_id}`, explicit approval/rejection endpoints, `GET /metrics`, and `GET /audit-log`.
