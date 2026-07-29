import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.auth import CurrentUser, get_current_user
from backend.app.database import Base, get_session
from backend.app.main import app


class CompanyWorkspaceTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.session = sessionmaker(bind=engine)()

        def session_override():
            yield self.session

        app.dependency_overrides[get_session] = session_override
        app.dependency_overrides[get_current_user] = lambda: CurrentUser("user-1", "user@example.com", "User")
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.session.close()

    def test_company_profile_active_context_and_capture_scoping(self):
        created = self.client.post("/api/company-workspaces", json={
            "symbol": "AAPL", "company_name": "Apple Inc.",
            "company_description": "Consumer technology company.",
            "business_model": "Hardware, services and software ecosystem.",
        })
        self.assertEqual(created.status_code, 200)
        self.assertTrue(created.json()["is_active"])

        active = self.client.get("/api/company-workspaces/active")
        self.assertEqual(active.json()["symbol"], "AAPL")
        self.assertEqual(active.json()["business_model"], "Hardware, services and software ecosystem.")

        scoped = self.client.post("/api/notes", json={"body": "Company-specific research", "active_ticker": "AAPL"})
        self.assertEqual(scoped.status_code, 200)
        self.assertEqual(scoped.json()["tickers"], ["AAPL"])

        explicit = self.client.post("/api/notes", json={"body": "Competitor mention $MSFT", "active_ticker": "AAPL"})
        self.assertEqual(explicit.status_code, 200)
        self.assertEqual(explicit.json()["tickers"], ["MSFT"])

        updated = self.client.put("/api/company-workspaces/AAPL", json={"company_description": "Updated description."})
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["company_description"], "Updated description.")

    def test_active_company_can_be_cleared(self):
        self.client.post("/api/company-workspaces", json={"symbol": "AAPL"})
        cleared = self.client.delete("/api/company-workspaces/active")
        self.assertEqual(cleared.status_code, 200)
        self.assertIsNone(self.client.get("/api/company-workspaces/active").json())


if __name__ == "__main__":
    unittest.main()
