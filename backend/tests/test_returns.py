from decimal import Decimal
import unittest
from datetime import datetime, timedelta, timezone
from backend.app.returns import ReturnCalculationError, canonical_return_object, pair_call_return, single_call_return


class ReturnEngineTests(unittest.TestCase):
    def test_bull_and_relative_return(self):
        result = single_call_return("bull", 100, 110, 100, 105)
        self.assertEqual(result["directional_return"], Decimal("0.1"))
        self.assertEqual(result["relative_return"], Decimal("0.05"))

    def test_bear_and_relative_return(self):
        result = single_call_return("bear", 100, 90, 100, 105)
        self.assertEqual(result["directional_return"], Decimal("0.1"))
        self.assertEqual(result["relative_return"], Decimal("0.15"))

    def test_pair_return(self):
        result = pair_call_return(100, 110, 100, 95)
        self.assertEqual(result["pair_return"], Decimal("0.15"))

    def test_rejects_invalid_prices(self):
        with self.assertRaises(ReturnCalculationError):
            single_call_return("bull", 0, 100, 100, 100)

    def test_closed_call_uses_frozen_exit_not_later_quote(self):
        opened = datetime(2026, 1, 1, tzinfo=timezone.utc)
        result = canonical_return_object(
            call_id="call", status="closed", call_type="bull",
            legs=[{"symbol": "AAPL", "direction": "long", "entry": 100, "current": 150, "exit": 110}],
            benchmark={"entry": 100, "current": 150, "exit": 105, "exit_quote": {"provider": "test", "price_type": "close", "timestamp": opened + timedelta(days=3)}},
            opened_at=opened, as_of=opened + timedelta(days=3),
        )
        self.assertEqual(result["directional_return"], 0.1)
        self.assertEqual(result["relative_return"], 0.05)
        self.assertEqual(result["elapsed_days"], 3)

    def test_invalidated_bear_is_frozen_and_labeled(self):
        opened = datetime(2026, 1, 1, tzinfo=timezone.utc)
        result = canonical_return_object(
            call_id="call", status="invalidated", call_type="bear",
            legs=[{"symbol": "AAPL", "direction": "short", "entry": 100, "current": 50, "exit": 110}],
            benchmark={"entry": 100, "current": 80, "exit": 105, "exit_quote": {}}, opened_at=opened, as_of=opened,
        )
        self.assertEqual(result["directional_return"], -0.1)
        self.assertEqual(result["label"], "Bear directional return")


if __name__ == "__main__":
    unittest.main()
