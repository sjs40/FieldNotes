from decimal import Decimal
import unittest
from backend.app.returns import ReturnCalculationError, pair_call_return, single_call_return


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


if __name__ == "__main__":
    unittest.main()
