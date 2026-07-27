import unittest
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from database import engine
from models import Fund, FundFlow, FundPosition, FundValuation, InvestmentAccount, PortfolioHolding
from services.fund_accounting_service import settle_fund_flow
from services.pnl_service import (
    compute_fund_return,
    compute_realized_pnl_fifo,
    record_buy_transaction,
    record_sell_transaction,
    snapshot_daily_holdings,
)


class AccountingIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.connection = engine.connect()
        self.outer_transaction = self.connection.begin()
        self.db = Session(
            bind=self.connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

    def tearDown(self):
        self.db.close()
        self.outer_transaction.rollback()
        self.connection.close()

    def test_deposit_is_idempotent_and_return_excludes_cash_flow(self):
        account = self.db.query(InvestmentAccount).first()
        fund = self.db.query(Fund).filter(Fund.is_active.is_(True)).first()
        self.assertIsNotNone(account)
        self.assertIsNotNone(fund)

        # The live development database may contain backfilled opening data.
        # This scenario intentionally starts with a clean account/fund pair.
        self.db.query(FundPosition).filter(
            FundPosition.investment_account_id == account.id,
            FundPosition.fund_id == fund.id,
        ).delete(synchronize_session=False)
        self.db.query(PortfolioHolding).filter(
            PortfolioHolding.investor_id == account.investor_id,
            PortfolioHolding.fund_id == fund.id,
        ).delete(synchronize_session=False)
        self.db.query(FundValuation).filter(
            FundValuation.fund_id == fund.id,
        ).delete(synchronize_session=False)

        fund.current_price = Decimal("2.00")
        flow = FundFlow(
            investor_id=account.investor_id,
            investment_account_id=account.id,
            fund_id=fund.id,
            flow_type="deposit",
            amount=Decimal("100.00"),
            status="pending_fund_transfer",
            request_id=f"TEST-{uuid.uuid4().hex}",
        )
        self.db.add(flow)
        self.db.flush()

        first = settle_fund_flow(self.db, flow)
        second = settle_fund_flow(self.db, flow)
        self.assertTrue(first.applied)
        self.assertFalse(second.applied)
        self.assertEqual(first.resulting_units, Decimal("50.0000000000"))

        day_one = datetime.now(timezone.utc).replace(hour=22, minute=0, second=0, microsecond=0)
        snapshot_daily_holdings(self.db, day_one)
        fund = self.db.query(Fund).filter(Fund.id == fund.id).one()
        fund.current_price = Decimal("2.20")
        self.db.flush()
        snapshot_daily_holdings(self.db, day_one + timedelta(days=1))

        valuation = (
            self.db.query(FundValuation)
            .filter(FundValuation.fund_id == fund.id)
            .order_by(FundValuation.valuation_date.desc())
            .first()
        )
        holding = (
            self.db.query(PortfolioHolding)
            .filter(
                PortfolioHolding.investor_id == account.investor_id,
                PortfolioHolding.fund_id == fund.id,
            )
            .order_by(PortfolioHolding.snapshot_date.desc())
            .first()
        )
        report = compute_fund_return(self.db, fund.id, day_one, day_one + timedelta(days=2))

        self.assertEqual(Decimal(valuation.daily_pnl), Decimal("10.0000"))
        self.assertEqual(Decimal(holding.daily_pnl), Decimal("10.0000"))
        self.assertAlmostEqual(report["fund_return_pct"], 10.0)

    def test_fifo_consumes_each_historical_sale_only_once(self):
        account = self.db.query(InvestmentAccount).first()
        fund = self.db.query(Fund).filter(Fund.is_active.is_(True)).first()
        symbol = f"T{uuid.uuid4().hex[:6].upper()}"
        record_buy_transaction(
            self.db, account.investor_id, symbol, Decimal("10"), Decimal("10"),
            fund_id=fund.id, investment_account_id=account.id,
        )
        record_buy_transaction(
            self.db, account.investor_id, symbol, Decimal("10"), Decimal("20"),
            fund_id=fund.id, investment_account_id=account.id,
        )
        record_sell_transaction(
            self.db, account.investor_id, symbol, Decimal("5"), Decimal("30"),
            fund_id=fund.id, investment_account_id=account.id,
        )
        result = compute_realized_pnl_fifo(
            self.db,
            account.investor_id,
            symbol,
            Decimal("10"),
            Decimal("30"),
            fund_id=fund.id,
        )
        self.assertEqual(result.matched_qty, Decimal("10"))
        self.assertEqual(result.avg_buy_price, Decimal("15"))
        self.assertEqual(result.realized_profit, Decimal("150"))


if __name__ == "__main__":
    unittest.main()
