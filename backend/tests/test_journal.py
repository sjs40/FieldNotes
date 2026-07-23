from datetime import datetime, timezone
import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.journal import create_note, serialize_note
from backend.app.market_data import Quote
from backend.app.models import CallBenchmarkSnapshot, NoteRevision, TrackedCall, TrackedCallLeg
from backend.app.parser import parse_note


class JournalPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def test_publish_creates_normalized_call_records_and_browser_shape(self):
        parsed = parse_note("Durable distribution.\n$AAPL @bull #AI", "thesis")
        at = datetime(2026, 7, 23, 14, 0, tzinfo=timezone.utc)
        quotes = {symbol: Quote(symbol=symbol, price=price, timestamp=at, provider="test") for symbol, price in {"AAPL": 200, "SPY": 500}.items()}
        note = create_note(self.session, user_id="user-1", parsed=parsed, title="Apple", status="published", quotes=quotes)
        self.session.commit()

        self.assertEqual(len(self.session.scalars(select(TrackedCall)).all()), 1)
        self.assertEqual(len(self.session.scalars(select(TrackedCallLeg)).all()), 1)
        self.assertEqual(len(self.session.scalars(select(CallBenchmarkSnapshot)).all()), 1)
        self.assertEqual(len(self.session.scalars(select(NoteRevision)).all()), 1)

        payload = serialize_note(self.session, note)
        self.assertEqual(payload["calls"][0]["symbol"], "AAPL")
        self.assertEqual(payload["calls"][0]["entry"], 200.0)
        self.assertEqual(payload["tags"], ["AI"])
        self.assertEqual(payload["tickers"], ["AAPL"])

    def test_draft_never_creates_a_tracked_call(self):
        note = create_note(self.session, user_id="user-1", parsed=parse_note("$AAPL @bull", "note"), title="", status="draft")
        self.session.commit()
        self.assertEqual(note.status, "draft")
        self.assertEqual(len(self.session.scalars(select(TrackedCall)).all()), 0)


if __name__ == "__main__":
    unittest.main()
