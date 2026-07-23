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
from backend.app.market_data import Quote
from backend.app.parser import parse_note


class NormalizedReadApiTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.session = sessionmaker(bind=engine)()
        parsed = parse_note("Apple distribution. $AAPL @bull #AI", "thesis")
        at = datetime(2026, 7, 23, tzinfo=timezone.utc)
        quotes = {symbol: Quote(symbol=symbol, price=price, timestamp=at, provider="test") for symbol, price in {"AAPL": 200, "SPY": 500}.items()}
        self.note = create_note(self.session, user_id="user-1", parsed=parsed, title="Apple", status="published", quotes=quotes)
        self.session.commit()

        def session_override():
            yield self.session

        app.dependency_overrides[get_session] = session_override
        app.dependency_overrides[get_current_user] = lambda: CurrentUser(id="user-1", email="user@example.com", display_name="User")
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.session.close()

    def test_normalized_read_endpoints_are_user_scoped(self):
        calls = self.client.get("/api/calls")
        self.assertEqual(calls.status_code, 200)
        self.assertEqual(calls.json()[0]["call"]["symbol"], "AAPL")

        tickers = self.client.get("/api/tickers")
        self.assertEqual(tickers.status_code, 200)
        self.assertEqual(tickers.json()[0]["symbol"], "AAPL")
        self.assertEqual(tickers.json()[0]["open_calls"], 1)

        search = self.client.get("/api/notes/search?q=distribution")
        self.assertEqual(search.status_code, 200)
        self.assertEqual(search.json()[0]["id"], self.note.id)

        revisions = self.client.get(f"/api/notes/{self.note.id}/revisions")
        self.assertEqual(revisions.status_code, 200)
        self.assertEqual(revisions.json()[0]["revision_number"], 1)

    def test_edit_creates_revision_without_changing_call(self):
        response = self.client.put(f"/api/notes/{self.note.id}", json={"title": "Apple revised", "body": "Updated distribution view. $AAPL #AI", "note_type": "thesis"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Apple revised")
        self.assertEqual(response.json()["calls"][0]["symbol"], "AAPL")
        revisions = self.client.get(f"/api/notes/{self.note.id}/revisions").json()
        self.assertEqual([item["revision_number"] for item in revisions], [2, 1])


if __name__ == "__main__":
    unittest.main()
