from datetime import datetime, timezone
from types import SimpleNamespace
import unittest

from services.portfolio_pdf_service import build_portfolio_pdf


class PortfolioPdfTests(unittest.TestCase):
    def test_builds_cross_platform_pdf_with_accounts_and_transactions(self):
        investor = SimpleNamespace(full_name="Test & Investor", email="test@example.com")
        accounts = [SimpleNamespace(
            account_name="Growth <Portfolio>",
            account_number="ACC-001",
            investment_strategy="balanced",
            total_invested=10000,
            current_value=11250.50,
            manager_fund_balance={"1": 250.25},
        )]
        transactions = [SimpleNamespace(
            symbol="FUND-1",
            trade_type="subscription",
            volume=10,
            price=100,
            net_pnl=125.50,
            trade_time=datetime(2026, 7, 29, 1, 30, tzinfo=timezone.utc),
        )]

        result = build_portfolio_pdf(
            investor,
            accounts,
            transactions,
            generated_at=datetime(2026, 7, 29, tzinfo=timezone.utc),
        )

        self.assertTrue(result.startswith(b"%PDF-"))
        self.assertIn(b"%%EOF", result[-1024:])
        self.assertGreater(len(result), 2000)

    def test_builds_pdf_when_portfolio_is_empty(self):
        investor = SimpleNamespace(full_name="Empty Investor", email="empty@example.com")

        result = build_portfolio_pdf(investor, [], [])

        self.assertTrue(result.startswith(b"%PDF-"))
        self.assertIn(b"%%EOF", result[-1024:])


if __name__ == "__main__":
    unittest.main()
