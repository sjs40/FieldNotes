from datetime import datetime, timezone
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.app.auth import CurrentUser, get_current_user
from backend.app.database import Base, get_session
from backend.app.journal import create_note
from backend.app.main import app
from backend.app.market_data import Quote
from backend.app.models import CallEvent, PortfolioPosition
from backend.app.parser import parse_note

class SprintOneTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine); self.session = sessionmaker(bind=self.engine)()
        at = datetime(2026, 7, 23, tzinfo=timezone.utc)
        self.note = create_note(self.session, user_id="user-1", parsed=parse_note("$AAPL @bull $300 @target"), title="Apple", status="published", quotes={"AAPL": Quote("AAPL", 200, at, "test"), "SPY": Quote("SPY", 500, at, "test")}); self.session.commit()
        def session_override():
            yield self.session
        app.dependency_overrides[get_session] = session_override
        app.dependency_overrides[get_current_user] = lambda: CurrentUser("user-1", "user@example.com", "User")
        self.client = TestClient(app)
    def tearDown(self): self.client.close(); app.dependency_overrides.clear(); self.session.close()
    def test_target_parser_and_request_id(self):
        self.assertEqual(parse_note("$AAPL @bull @target $300")["tracked_calls"][0]["target"], 300)
        self.assertNotIn("300", parse_note("$AAPL @bull $300 @target")["ticker_mentions"])
        response = self.client.get("/api/health/live", headers={"X-Request-ID": "test-request-123"})
        self.assertEqual(response.headers["X-Request-ID"], "test-request-123")
    @patch("backend.app.main.YFinanceMarketDataProvider")
    def test_update_snapshot_and_fallback(self, provider_class):
        provider_class.return_value.get_latest_quote.side_effect = lambda symbol: Quote(symbol, {"AAPL": 220, "SPY": 510}[symbol], datetime(2026, 7, 24, tzinfo=timezone.utc), "test")
        call_id = self.client.get("/api/calls").json()[0]["call"]["id"]
        result = self.client.post(f"/api/calls/{call_id}/updated", json={"explanation":"Evidence improved", "body":"Demand is stronger.", "idempotency_key":"update-snapshot-001", "confidence_before":"medium", "confidence_after":"high", "thesis_state":"strengthening"})
        self.assertEqual(result.status_code, 200)
        event = self.session.scalar(select(CallEvent).where(CallEvent.event_type == "updated")); self.assertEqual(event.snapshot_json["snapshot_status"], "available")
    def test_portfolio_rejects_missing_credential(self):
        response = self.client.post("/api/integrations/ibkr/sync", json={"user_id":"user-1", "account_id":"U123", "snapshot_at":"2026-07-23T00:00:00Z", "positions":[]})
        self.assertEqual(response.status_code, 401)

if __name__ == "__main__": unittest.main()
