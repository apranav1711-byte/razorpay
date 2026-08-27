"""Executable regression tests for the FastAPI ChargebackShield reference service."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path


class ChargebackShieldApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_directory = tempfile.TemporaryDirectory()
        os.environ["CHARGEBACKSHIELD_API_DB"] = str(Path(cls.temp_directory.name) / "test.sqlite")
        os.environ["CHARGEBACKSHIELD_SKIP_LLM"] = "1"
        from fastapi.testclient import TestClient
        from ml import api

        cls.api = api
        api.load_artifacts()
        api.initialise_database()
        cls.client = TestClient(api.app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        cls.temp_directory.cleanup()

    def test_score_returns_a_bounded_explanation(self) -> None:
        response = self.client.post("/score", json={
            "transaction_id": "txn_test_score",
            "amount_cents": 175000,
            "amount_zscore": 2.7,
            "velocity_1h": 7,
            "velocity_24h": 11,
            "velocity_7d": 15,
            "geo_mismatch": True,
            "customer_is_first_time": True,
            "new_device": True,
            "payment_method_risk": 0.58,
            "merchant_category_risk": 0.51,
            "velocity_spike": True,
            "high_amount": True,
        })
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn(payload["tier"], {"low", "medium", "high"})
        self.assertEqual(payload["model_version"], "cbs-xgb-calibrated-1.0.0")
        self.assertGreaterEqual(len(payload["top_features"]), 1)
        self.assertLessEqual(len(payload["top_features"]), 5)

    def test_insufficient_evidence_is_explicit_and_not_fabricated(self) -> None:
        response = self.client.post("/evidence/generate/dsp_demo_002")
        self.assertEqual(response.status_code, 200)
        draft = response.json()
        self.assertFalse(draft["has_sufficient_evidence"])
        self.assertGreaterEqual(len(draft["insufficient_evidence"]), 3)
        self.assertTrue(any("delivery completion" in item.lower() for item in draft["insufficient_evidence"]))
        for claim in draft["claims"]:
            if claim["type"] == "supported":
                self.assertGreater(len(claim["source_links"]), 0)

    def test_approval_requires_a_draft_and_only_records_local_state(self) -> None:
        blocked = self.client.post("/evidence/approve/dsp_demo_001", json={"actor": "test.reviewer", "reason": "Reviewed"})
        self.assertEqual(blocked.status_code, 409)
        self.client.post("/evidence/generate/dsp_demo_001")
        approved = self.client.post("/evidence/approve/dsp_demo_001", json={"actor": "test.reviewer", "reason": "Reviewed source links"})
        self.assertEqual(approved.status_code, 200)
        self.assertFalse(approved.json()["external_submission"])
        log = self.client.get("/audit-log").json()
        event = next(item for item in log if item["action"] == "evidence_approved")
        self.assertEqual(event["model_version"], "cbs-xgb-calibrated-1.0.0")
        self.assertTrue(event["input_hash"])
        self.assertEqual(event["actor"], "test.reviewer")
        self.assertIn("+00:00", event["occurred_at"])

    def test_rejection_requires_a_reason(self) -> None:
        self.client.post("/evidence/generate/dsp_demo_002")
        response = self.client.post("/evidence/reject/dsp_demo_002", json={"actor": "test.reviewer"})
        self.assertEqual(response.status_code, 422)
        before = self.client.get("/audit-log").json()
        rejected = self.client.post("/evidence/reject/dsp_demo_002", json={"actor": "test.reviewer", "reason": "Delivery confirmation is not available."})
        self.assertEqual(rejected.status_code, 200)
        dispute = next(item for item in self.client.get("/disputes").json() if item["dispute_id"] == "dsp_demo_002")
        self.assertEqual(dispute["status"], "rejected")
        after = self.client.get("/audit-log").json()
        self.assertEqual(len(after), len(before) + 1)
        event = after[0]
        self.assertEqual(event["action"], "evidence_rejected")
        self.assertEqual(event["model_version"], "cbs-xgb-calibrated-1.0.0")
        self.assertTrue(event["input_hash"])
        self.assertEqual(event["actor"], "test.reviewer")
        self.assertIn("+00:00", event["occurred_at"])

    def test_audit_log_has_no_update_or_delete_route(self) -> None:
        self.assertEqual(self.client.put("/audit-log", json={"action": "alter"}).status_code, 405)
        self.assertEqual(self.client.delete("/audit-log").status_code, 405)

    def test_valid_csv_import_scores_records_without_storing_original_file(self) -> None:
        csv_body = (
            "transaction_id,amount_cents,amount_zscore,velocity_1h,velocity_24h,velocity_7d,geo_mismatch,customer_is_first_time,new_device,payment_method_risk,merchant_category_risk\n"
            "txn_import_001,184500,3.1,8,11,17,true,true,true,0.58,0.51\n"
            "txn_import_002,92000,1.8,1,3,10,false,false,false,0.10,0.16\n"
        )
        response = self.client.post("/imports/csv", files={"file": ("merchant-august.csv", csv_body, "text/csv")}, data={"actor": "merchant.importer"})
        self.assertEqual(response.status_code, 200)
        outcome = response.json()
        self.assertEqual(outcome["status"], "accepted")
        self.assertEqual(outcome["row_count"], 2)
        self.assertFalse(outcome["stored_original_csv"])
        imported = next(item for item in self.client.get("/imports").json() if item["import_id"] == outcome["import_id"])
        self.assertEqual(imported["file_name"], "merchant-august.csv")
        self.assertEqual(imported["status"], "accepted")
        transaction = next(item for item in self.client.get("/transactions").json() if item["transaction_id"] == "txn_import_001")
        self.assertEqual(transaction["model_version"], "cbs-xgb-calibrated-1.0.0")
        audit = next(item for item in self.client.get("/audit-log").json() if item["action"] == "csv_import_accepted" and item["entity_id"] == outcome["import_id"])
        self.assertEqual(audit["actor"], "merchant.importer")
        self.assertIn("+00:00", audit["occurred_at"])

    def test_sensitive_csv_column_is_rejected_and_audited_without_file_retention(self) -> None:
        response = self.client.post("/imports/csv", files={"file": ("unsafe.csv", "transaction_id,amount_cents,card_number\ntxn_unsafe,1000,4111111111111111\n", "text/csv")}, data={"actor": "merchant.importer"})
        self.assertEqual(response.status_code, 422)
        detail = response.json()["detail"]
        self.assertTrue(any("Sensitive field" in error for error in detail["errors"]))
        imported = next(item for item in self.client.get("/imports").json() if item["import_id"] == detail["import_id"])
        self.assertEqual(imported["status"], "rejected")
        self.assertEqual(imported["row_count"], 0)
        self.assertTrue(any("Sensitive field" in error for error in imported["errors"]))
        audit = next(item for item in self.client.get("/audit-log").json() if item["action"] == "csv_import_rejected" and item["entity_id"] == detail["import_id"])
        self.assertEqual(audit["actor"], "merchant.importer")

    def test_audit_filters_and_chargeback_analytics_are_available(self) -> None:
        self.client.post("/score", json={"transaction_id": "txn_audit_analytics", "amount_cents": 25000})
        filters = self.client.get("/audit-filters")
        self.assertEqual(filters.status_code, 200)
        self.assertIn("transaction_scored", filters.json()["actions"])
        filtered = self.client.get("/audit-log", params={"action": "transaction_scored", "entity_type": "transaction"})
        self.assertEqual(filtered.status_code, 200)
        self.assertTrue(all(item["action"] == "transaction_scored" for item in filtered.json()))
        analytics = self.client.get("/audit-analytics", params={"days": "7"})
        self.assertEqual(analytics.status_code, 200)
        self.assertEqual(analytics.json()["period_days"], 7)
        self.assertEqual(len(analytics.json()["timeline"]), 7)
        self.assertEqual(len(analytics.json()["chargeback_trends"]), 7)

    def test_source_linked_evidence_pdf_is_downloadable_and_audited(self) -> None:
        self.client.post("/evidence/generate/dsp_demo_001")
        response = self.client.get("/evidence/export/dsp_demo_001.pdf", params={"actor": "test.reviewer"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertIn("attachment", response.headers["content-disposition"])
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertTrue(response.content.startswith(b"%PDF"))
        audit = next(item for item in self.client.get("/audit-log").json() if item["action"] == "evidence_draft_exported")
        self.assertEqual(audit["actor"], "test.reviewer")
        self.assertEqual(audit["model_version"], "cbs-xgb-calibrated-1.0.0")
        self.assertFalse(audit["output"]["external_submission"])


if __name__ == "__main__":
    unittest.main()
