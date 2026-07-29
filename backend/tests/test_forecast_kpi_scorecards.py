import unittest
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.auth import CurrentUser, get_current_user
from backend.app.database import Base, get_session
from backend.app.main import app


class ForecastKpiScorecardTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.session = sessionmaker(bind=engine)()

        def session_override():
            yield self.session

        app.dependency_overrides[get_session] = session_override
        app.dependency_overrides[get_current_user] = lambda: CurrentUser("user-1", "user@example.com", "User")
        self.client = TestClient(app)
        self.client.post("/api/company-workspaces", json={"symbol": "NVDA"})

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.session.close()

    def test_revisions_kpis_and_scorecard_are_auditable(self):
        kpi = self.client.post("/api/company-workspaces/NVDA/kpis", json={"name": "Data center revenue", "definition": "Quarterly segment revenue", "value_unit": "$m"})
        self.assertEqual(kpi.status_code, 200)
        observation = self.client.post("/api/company-workspaces/NVDA/kpis/observations", json={"kpi_definition_id": kpi.json()["id"], "period": "FY27 Q1", "value": 120.0, "interpretation": "Above plan"})
        self.assertEqual(observation.status_code, 200)

        original = self.client.post("/api/forecasts", json={"metric_name": "Data center revenue", "ticker": "NVDA", "forecast_type": "point", "target_value": 100, "value_unit": "$m", "target_period_start": datetime.now(timezone.utc).isoformat()})
        self.assertEqual(original.status_code, 200)
        revision = self.client.post(f"/api/forecasts/{original.json()['id']}/revise", json={"metric_name": "Data center revenue", "ticker": "NVDA", "forecast_type": "point", "target_value": 110, "value_unit": "$m", "target_period_start": datetime.now(timezone.utc).isoformat()})
        self.assertEqual(revision.status_code, 200)
        self.assertEqual(revision.json()["revision_number"], 2)
        resolved = self.client.post(f"/api/forecasts/{revision.json()['id']}/resolve", json={"kpi_observation_id": observation.json()["id"], "outcome": "correct"})
        self.assertEqual(resolved.status_code, 200)
        self.assertEqual(resolved.json()["error_value"], 10.0)

        qualitative = self.client.post("/api/forecasts", json={"metric_name": "Pricing", "ticker": "NVDA", "forecast_type": "qualitative", "expected_outcome": "Pricing remains firm", "confidence": "high", "resolution_event": "FY27 Q1 results"})
        self.assertEqual(qualitative.status_code, 200)
        self.assertEqual(self.client.post(f"/api/forecasts/{qualitative.json()['id']}/resolve", json={"outcome": "correct", "resolution_note": "Pricing held."}).status_code, 200)

        scorecard = self.client.get("/api/company-workspaces/NVDA/forecast-scorecard")
        self.assertEqual(scorecard.status_code, 200)
        summary = scorecard.json()["summary"]
        self.assertEqual(summary["superseded_count"], 1)
        self.assertEqual(summary["point_count"], 1)
        self.assertEqual(summary["mean_absolute_error"], 10.0)
        self.assertEqual(summary["qualitative_accuracy"], 1.0)
        self.assertEqual(self.client.get("/api/company-workspaces/NVDA/kpis").json()[0]["observations"][0]["period"], "FY27 Q1")

    def test_qualitative_forecast_requires_an_expected_outcome(self):
        invalid = self.client.post("/api/forecasts", json={"metric_name": "Pricing", "ticker": "NVDA", "forecast_type": "qualitative"})
        self.assertEqual(invalid.status_code, 422)


if __name__ == "__main__":
    unittest.main()
