from datetime import datetime, timezone
import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.auth import CurrentUser, get_current_user
from backend.app.database import Base, get_session
from backend.app.journal import create_note
from backend.app.main import app
from backend.app.parser import parse_note


class ReasoningLedgerTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine); self.session = sessionmaker(bind=engine)()
        self.note = create_note(self.session, user_id="u1", parsed=parse_note("$AAPL Initial observation", "observation"), title="Initial", status="published", quotes={})
        self.session.commit()
        def override(): yield self.session
        app.dependency_overrides[get_session] = override
        app.dependency_overrides[get_current_user] = lambda: CurrentUser("u1", "u1@example.test", "U1")
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close(); app.dependency_overrides.clear(); self.session.close()

    def test_followup_is_atomic_and_appears_as_backlink(self):
        response = self.client.post(f"/api/notes/{self.note.id}/follow-ups", json={"body":"$AAPL Demand evidence improved", "relationship_type":"supports", "pending_questions":[{"question":"Can demand persist?", "ticker":"AAPL"}]})
        self.assertEqual(response.status_code, 200)
        links = self.client.get(f"/api/notes/{self.note.id}/relationships").json()
        self.assertEqual(links[0]["relationship_type"], "supports")
        self.assertEqual(len(self.client.get("/api/questions?ticker=AAPL").json()), 1)

    def test_ledger_is_user_scoped_and_forecast_resolution_is_audit_safe(self):
        assumption = self.client.post("/api/assumptions", json={"statement":"Units grow", "ticker":"AAPL", "importance":"high"})
        self.assertEqual(assumption.status_code, 200)
        evidence = self.client.post("/api/evidence", json={"statement":"Orders accelerated", "ticker":"AAPL", "direction":"supports", "assumption_ids":[assumption.json()["id"]]})
        self.assertEqual(evidence.status_code, 200)
        forecast = self.client.post("/api/forecasts", json={"metric_name":"Revenue", "ticker":"AAPL", "target_value":100, "target_period_start":datetime.now(timezone.utc).isoformat()})
        self.assertEqual(forecast.status_code, 200)
        resolved = self.client.post(f"/api/forecasts/{forecast.json()['id']}/resolve", json={"resolution_value":110, "outcome":"correct"})
        self.assertEqual(resolved.status_code, 200)
        self.assertEqual(resolved.json()["error_value"], 10.0)

    def test_conversion_challenge_events_saved_views_and_review(self):
        thesis = self.client.post(f"/api/notes/{self.note.id}/convert", json={"target_type":"thesis", "body":"$AAPL Durable growth"})
        self.assertEqual(thesis.status_code, 200)
        thesis_note = thesis.json()["note"]
        challenge = self.client.post(f"/api/notes/{thesis_note['id']}/challenge", json={"opposing_case":"Margins could contract."})
        self.assertEqual(challenge.status_code, 200)
        question = self.client.post("/api/questions", json={"statement":"What changes margins?", "ticker":"AAPL"}).json()
        answered = self.client.post(f"/api/questions/{question['id']}/answer", json={"status":"answered", "answer_summary":"Pricing is stable.", "answered_by_note_id":thesis_note["id"]})
        self.assertEqual(answered.status_code, 200)
        self.assertEqual(self.client.get(f"/api/questions/{question['id']}/events").status_code, 200)
        view = self.client.post("/api/saved-views", json={"name":"Open critical questions", "resource":"questions", "filters":{"status":"open","priority":"critical"}})
        self.assertEqual(view.status_code, 200)
        self.assertEqual(self.client.get("/api/research-reviews/weekly").status_code, 200)


if __name__ == "__main__": unittest.main()
