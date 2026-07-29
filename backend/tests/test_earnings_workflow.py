import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.auth import CurrentUser, get_current_user
from backend.app.database import Base, get_session
from backend.app.main import app
from backend.app.models import Note


class EarningsWorkflowTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.session = sessionmaker(bind=engine)()

        def session_override():
            yield self.session

        app.dependency_overrides[get_session] = session_override
        app.dependency_overrides[get_current_user] = lambda: CurrentUser("user-1", "user@example.com", "User")
        self.client = TestClient(app)
        self.client.post("/api/company-workspaces", json={"symbol": "MSFT", "company_name": "Microsoft"})

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.session.close()

    def test_partial_earnings_workflow_is_archived_and_links_notes(self):
        note = self.client.post("/api/notes", json={"body": "Pre-earnings view", "active_ticker": "MSFT"}).json()
        created = self.client.post("/api/company-workspaces/MSFT/earnings", json={
            "fiscal_period": "FY26 Q4",
            "reporting_date": "2026-07-29T00:00:00Z",
            "pre_expectations": "Cloud growth accelerates.",
            "note_ids": [note["id"]],
        })
        self.assertEqual(created.status_code, 200)
        event = created.json()
        self.assertIsNotNone(event["pre_recorded_at"])
        self.assertEqual(event["notes"][0]["id"], note["id"])
        self.assertIsNone(event["earnings_results"])

        updated = self.client.put(f"/api/company-workspaces/MSFT/earnings/{event['id']}", json={
            "post_expected_vs_actual": "Cloud growth beat the expectation.",
            "post_decision_action": "Maintain the position.",
        })
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["pre_expectations"], "Cloud growth accelerates.")
        self.assertEqual(updated.json()["post_decision_action"], "Maintain the position.")

        archive = self.client.get("/api/company-workspaces/MSFT/earnings")
        self.assertEqual(archive.status_code, 200)
        self.assertEqual(archive.json()[0]["fiscal_period"], "FY26 Q4")

    def test_event_shell_and_link_authorization_are_safe(self):
        shell = self.client.post("/api/company-workspaces/MSFT/earnings", json={})
        self.assertEqual(shell.status_code, 200)
        self.assertEqual(shell.json()["fiscal_period"], "Unscheduled")

        foreign_note = Note(user_id="other-user", body="private")
        self.session.add(foreign_note)
        self.session.commit()
        denied = self.client.post("/api/company-workspaces/MSFT/earnings", json={"fiscal_period": "FY27 Q1", "note_ids": [foreign_note.id]})
        self.assertEqual(denied.status_code, 404)


if __name__ == "__main__":
    unittest.main()
