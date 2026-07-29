import unittest
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.auth import CurrentUser, get_current_user
from backend.app.database import Base, get_session
from backend.app.main import app


class PhaseFiveReviewExportTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.session = sessionmaker(bind=engine)()

        def session_override():
            yield self.session

        app.dependency_overrides[get_session] = session_override
        app.dependency_overrides[get_current_user] = lambda: CurrentUser("user-1", "user@example.com", "User")
        self.client = TestClient(app)
        self.client.post("/api/company-workspaces", json={"symbol": "AAPL", "company_name": "Apple"})

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.session.close()

    def test_company_review_queue_analytics_and_exports_use_durable_records(self):
        note = self.client.post("/api/notes", json={"body": "Research note", "active_ticker": "AAPL", "source_url": "https://example.com/article"}).json()
        self.client.post("/api/questions", json={"statement": "Can services sustain growth?", "ticker": "AAPL", "priority": "high"})
        self.client.post("/api/forecasts", json={"metric_name": "Revenue", "ticker": "AAPL", "target_value": 100, "target_period_start": datetime.now(timezone.utc).isoformat()})
        event = self.client.post("/api/company-workspaces/AAPL/earnings", json={"fiscal_period": "FY27 Q1", "reporting_date": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(), "earnings_results": "Reported results"})
        self.assertEqual(event.status_code, 200)
        kpi = self.client.post("/api/company-workspaces/AAPL/kpis", json={"name": "Services revenue", "value_unit": "$m"}).json()
        self.assertEqual(self.client.post("/api/company-workspaces/AAPL/kpis/observations", json={"kpi_definition_id": kpi["id"], "period": "FY27 Q1", "value": 25}).status_code, 200)

        prompts = self.client.get("/api/company-review-queue").json()
        prompt_types = {prompt["type"] for prompt in prompts}
        self.assertIn("company_profile", prompt_types)
        self.assertIn("unresolved_question", prompt_types)
        self.assertIn("unresolved_forecast", prompt_types)
        self.assertIn("missing_post_earnings_review", prompt_types)

        self.assertEqual(self.client.get("/api/analytics/kpis?name=Services").json()[0]["ticker"], "AAPL")
        self.assertEqual(self.client.get("/api/analytics/earnings").json()[0]["fiscal_period"], "FY27 Q1")
        calibration = self.client.get("/api/analytics/forecast-calibration")
        self.assertEqual(calibration.status_code, 200)
        exported = self.client.get("/api/company-workspaces/AAPL/export?kind=memo")
        self.assertEqual(exported.status_code, 200)
        self.assertIn("## Sources", exported.text)
        self.assertIn(note["id"], exported.text)
        self.assertIn("example.com/article", exported.text)

    def test_invalid_export_kind_is_rejected(self):
        self.assertEqual(self.client.get("/api/company-workspaces/AAPL/export?kind=unknown").status_code, 422)


if __name__ == "__main__":
    unittest.main()
