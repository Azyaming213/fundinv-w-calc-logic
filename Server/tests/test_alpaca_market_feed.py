import unittest
from unittest.mock import Mock, patch

from services.alpaca_service import get_bars, get_snapshots


class AlpacaMarketFeedTests(unittest.TestCase):
    @patch("services.alpaca_service.requests.get")
    def test_snapshots_explicitly_use_configured_feed(self, mock_get):
        response = Mock()
        response.json.return_value = {"VOO": {"latestTrade": {"p": 500}}}
        mock_get.return_value = response

        result = get_snapshots(["VOO"])

        self.assertIn("VOO", result)
        self.assertEqual(mock_get.call_args.kwargs["params"]["feed"], "iex")

    @patch("services.alpaca_service.requests.get")
    def test_historical_bars_explicitly_use_configured_feed(self, mock_get):
        response = Mock()
        response.json.return_value = {"bars": [{"c": 500}]}
        mock_get.return_value = response

        result = get_bars("VOO", start="2026-08-01", end="2026-08-04")

        self.assertEqual(result, [{"c": 500}])
        self.assertEqual(mock_get.call_args.kwargs["params"]["feed"], "iex")


if __name__ == "__main__":
    unittest.main()
