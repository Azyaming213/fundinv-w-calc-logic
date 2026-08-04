import unittest
import uuid
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from database import engine
from models import Fund, FundBalanceEntry, FundComponent, FundFlow, FundPosition, FundTargeting, FundValuation, InvestmentAccount, InvestmentTransaction, Investor, Manager, Order, PortfolioHolding, User
from routers.admin_routers import approve_fund_flow, complete_fund_flow, verify_paynow_and_complete
from routers.funds_routers import simulate_paynow_payment
from schemas.portfolio_schema import FundFlowActionRequest
from config import settings
from services.fund_accounting_service import settle_fund_flow
from services.order_accounting_service import apply_filled_order
from services.valuation_service import finalize_valuation, preview_valuation, suggest_daily_pnl
from services.pnl_service import (
    compute_fund_return,
    compute_investor_pnl,
    compute_realized_pnl_fifo,
    record_buy_transaction,
    record_sell_transaction,
    snapshot_daily_holdings,
)
from routers.manager_routers import manager_trade_for_investor


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

    def _new_fund(self, price: str = "2.00") -> Fund:
        suffix = uuid.uuid4().hex[:10].upper()
        fund = Fund(
            name=f"Accounting Test Fund {suffix}",
            ticker=f"AT{suffix[:6]}",
            fund_type="managed",
            current_price=Decimal(price),
            is_active=True,
            review_status="approved",
        )
        self.db.add(fund)
        self.db.flush()
        return fund

    def test_deposit_is_idempotent_and_return_excludes_cash_flow(self):
        account = self.db.query(InvestmentAccount).first()
        fund = self._new_fund()
        self.assertIsNotNone(account)

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

    def test_async_external_fill_is_recorded_exactly_once(self):
        account = self.db.query(InvestmentAccount).first()
        fund = self._new_fund()
        order = Order(
            investor_id=account.investor_id,
            investment_account_id=account.id,
            fund_id=fund.id,
            alpaca_order_id=f"PAPER-{uuid.uuid4().hex}",
            symbol="AAPL",
            side="buy",
            amount=Decimal("10.00"),
            status="accepted",
        )
        self.db.add(order)
        self.db.flush()
        starting_aapl = Decimal(str((account.fund_allocations or {}).get("AAPL", 0)))

        provider_fill = {
            "status": "filled",
            "filled_qty": "0.05",
            "filled_avg_price": "200.00",
        }
        self.assertTrue(apply_filled_order(self.db, order, provider_fill))
        self.assertFalse(apply_filled_order(self.db, order, provider_fill))

        deals = self.db.query(InvestmentTransaction).filter_by(
            external_id=order.alpaca_order_id
        ).all()
        self.assertEqual(len(deals), 1)
        self.assertEqual(Decimal(deals[0].volume), Decimal("0.0500"))
        self.assertEqual(Decimal(deals[0].price), Decimal("200.00000000"))
        self.assertEqual(
            Decimal(str(account.fund_allocations["AAPL"])), starting_aapl + Decimal("10.0")
        )

    def test_manager_route_persists_then_accounts_async_fill(self):
        manager_user = self.db.query(User).filter(User.email == "manager@fundinv.com").one()
        manager = self.db.query(Manager).filter(Manager.email == manager_user.email).one()
        account = self.db.query(InvestmentAccount).first()
        investor = self.db.query(Investor).filter(Investor.id == account.investor_id).one()
        investor.manager_id = manager.id
        fund = self._new_fund()
        fund.creator_manager_id = manager.id
        balances = dict(account.manager_fund_balance or {})
        balances[str(fund.id)] = "100.00"
        account.manager_fund_balance = balances
        self.db.flush()

        external_id = f"PAPER-{uuid.uuid4().hex}"
        submitted = {"id": external_id, "status": "accepted", "symbol": "AAPL", "side": "buy"}
        filled = {
            "id": external_id, "status": "filled", "symbol": "AAPL", "side": "buy",
            "filled_qty": "0.05", "filled_avg_price": "200.00",
        }
        with patch("routers.manager_routers.place_order", return_value=submitted), \
             patch("routers.manager_routers.get_order", return_value=filled):
            response = manager_trade_for_investor(
                investor_id=investor.id,
                symbol="AAPL",
                side="buy",
                amount=10.0,
                investment_account_id=account.id,
                fund_id=fund.id,
                current_user=manager_user,
                db=self.db,
            )

        self.assertTrue(response.success)
        self.assertEqual(response.data["status"], "filled")
        self.assertEqual(response.data["accounting_status"], "recorded")
        order = self.db.query(Order).filter_by(alpaca_order_id=external_id).one()
        self.assertIsNotNone(order.accounting_recorded_at)
        self.assertEqual(
            self.db.query(InvestmentTransaction).filter_by(external_id=external_id).count(), 1
        )

    def test_manual_transfer_requires_approval_then_explicit_completion(self):
        account = self.db.query(InvestmentAccount).first()
        operator = self.db.query(User).first()
        fund = self._new_fund("2.00")
        flow = FundFlow(
            investor_id=account.investor_id,
            investment_account_id=account.id,
            fund_id=fund.id,
            flow_type="deposit",
            amount=Decimal("100.00"),
            status="pending_ops_team",
            request_id=f"TEST-MANUAL-{uuid.uuid4().hex}",
        )
        self.db.add(flow)
        self.db.flush()

        with patch.object(settings, "FUND_FLOW_PROVIDER", "manual"), \
             patch("routers.admin_routers.send_fund_flow_approved_email"), \
             patch("routers.admin_routers.send_fund_flow_completed_email"):
            approved = approve_fund_flow(
                flow.id, FundFlowActionRequest(), current_user=operator, db=self.db,
            )
            self.assertEqual(approved.data["status"], "pending_fund_transfer")
            self.assertEqual(flow.provider, "manual_transfer")
            self.assertIsNone(self.db.query(FundBalanceEntry).filter_by(fund_flow_id=flow.id).first())

            completed = complete_fund_flow(
                flow.id, FundFlowActionRequest(), current_user=operator, db=self.db,
            )
            self.assertEqual(completed.data["status"], "completed")
            entry = self.db.query(FundBalanceEntry).filter_by(fund_flow_id=flow.id).one()
            position = self.db.query(FundPosition).filter_by(
                investment_account_id=account.id, fund_id=fund.id,
            ).one()
            self.assertEqual(Decimal(entry.units), Decimal("50.0000000000"))
            self.assertEqual(Decimal(position.units), Decimal("50.0000000000"))

    def test_demo_paynow_locks_amount_then_operations_verifies_and_completes_once(self):
        account = self.db.query(InvestmentAccount).first()
        investor = self.db.query(Investor).filter(Investor.id == account.investor_id).one()
        investor_user = self.db.query(User).filter(User.email == investor.email).one()
        operations_user = self.db.query(User).filter(User.email == "operations@fundinv.com").one()
        fund = self._new_fund(price="2.00")
        self.db.add(FundTargeting(investor_id=investor.id, fund_id=fund.id, is_visible=True))
        flow = FundFlow(
            investor_id=investor.id,
            investment_account_id=account.id,
            fund_id=fund.id,
            flow_type="deposit",
            amount=Decimal("250.00"),
            currency=account.currency,
            status="awaiting_investor_payment",
            request_id=f"PAYNOW-{uuid.uuid4().hex}",
            provider="paynow_demo",
            provider_reference=f"PAYNOW-DEMO-{uuid.uuid4().hex}",
            payment_url="paynow-demo://pay?amount=250.00",
        )
        self.db.add(flow)
        self.db.flush()

        paid = simulate_paynow_payment(flow.id, db=self.db, current_user=investor_user)
        self.assertEqual(paid["data"]["paid_amount"], 250.0)
        self.assertEqual(flow.paid_amount, flow.amount)
        self.assertEqual(flow.status, "pending_ops_team")

        with patch("routers.admin_routers.send_fund_flow_completed_email", return_value=None):
            completed = verify_paynow_and_complete(
                flow.id,
                FundFlowActionRequest(notes="Matched demo receipt"),
                current_user=operations_user,
                db=self.db,
            )
            repeated = verify_paynow_and_complete(
                flow.id,
                FundFlowActionRequest(),
                current_user=operations_user,
                db=self.db,
            )

        self.assertEqual(completed.data["status"], "completed")
        self.assertEqual(repeated.data["status"], "completed")
        position = self.db.query(FundPosition).filter_by(
            investment_account_id=account.id,
            fund_id=fund.id,
        ).one()
        self.assertEqual(Decimal(position.units), Decimal("125.0000000000"))

    def test_demo_paynow_blocks_mismatched_receipt(self):
        account = self.db.query(InvestmentAccount).first()
        operations_user = self.db.query(User).filter(User.email == "operations@fundinv.com").one()
        fund = self._new_fund()
        flow = FundFlow(
            investor_id=account.investor_id,
            investment_account_id=account.id,
            fund_id=fund.id,
            flow_type="deposit",
            amount=Decimal("500.00"),
            paid_amount=Decimal("500.01"),
            payment_received_at=datetime.now(timezone.utc),
            status="pending_ops_team",
            request_id=f"PAYNOW-MISMATCH-{uuid.uuid4().hex}",
            provider="paynow_demo",
            provider_reference=f"PAYNOW-DEMO-{uuid.uuid4().hex}",
        )
        self.db.add(flow)
        self.db.flush()

        with self.assertRaisesRegex(Exception, "Payment mismatch"):
            verify_paynow_and_complete(
                flow.id,
                FundFlowActionRequest(),
                current_user=operations_user,
                db=self.db,
            )
        self.assertEqual(flow.status, "pending_ops_team")

    def test_deposit_then_withdrawal_preserves_units_and_proportional_cost_basis(self):
        account = self.db.query(InvestmentAccount).first()
        fund = self._new_fund("2.00")

        deposit = FundFlow(
            investor_id=account.investor_id,
            investment_account_id=account.id,
            fund_id=fund.id,
            flow_type="deposit",
            amount=Decimal("100.00"),
            status="pending_fund_transfer",
            request_id=f"TEST-DEP-{uuid.uuid4().hex}",
        )
        self.db.add(deposit)
        self.db.flush()
        deposited = settle_fund_flow(self.db, deposit)

        withdrawal = FundFlow(
            investor_id=account.investor_id,
            investment_account_id=account.id,
            fund_id=fund.id,
            flow_type="withdrawal",
            amount=Decimal("40.00"),
            status="pending_fund_transfer",
            request_id=f"TEST-WTH-{uuid.uuid4().hex}",
        )
        self.db.add(withdrawal)
        self.db.flush()
        withdrawn = settle_fund_flow(self.db, withdrawal)
        duplicate = settle_fund_flow(self.db, withdrawal)

        position = self.db.query(FundPosition).filter(
            FundPosition.investment_account_id == account.id,
            FundPosition.fund_id == fund.id,
        ).one()
        self.assertEqual(deposited.units_delta, Decimal("50.0000000000"))
        self.assertEqual(withdrawn.units_delta, Decimal("-20.0000000000"))
        self.assertEqual(Decimal(position.units), Decimal("30.0000000000"))
        self.assertEqual(Decimal(position.cost_basis), Decimal("60.0000"))
        self.assertEqual(withdrawn.resulting_value, Decimal("60.0000"))
        self.assertFalse(duplicate.applied)

    def test_withdrawal_rejects_units_overdraw(self):
        account = self.db.query(InvestmentAccount).first()
        fund = self._new_fund("5.00")
        flow = FundFlow(
            investor_id=account.investor_id,
            investment_account_id=account.id,
            fund_id=fund.id,
            flow_type="withdrawal",
            amount=Decimal("5.00"),
            status="pending_fund_transfer",
            request_id=f"TEST-WTH-{uuid.uuid4().hex}",
        )
        self.db.add(flow)
        self.db.flush()
        with self.assertRaisesRegex(ValueError, "insufficient units"):
            settle_fund_flow(self.db, flow)

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

    def test_fifo_partial_lots_and_costs_reduce_realized_pnl_once(self):
        account = self.db.query(InvestmentAccount).first()
        fund = self._new_fund()
        symbol = f"F{uuid.uuid4().hex[:7].upper()}"
        record_buy_transaction(
            self.db, account.investor_id, symbol, Decimal("4"), Decimal("10"),
            fund_id=fund.id, investment_account_id=account.id,
        )
        record_buy_transaction(
            self.db, account.investor_id, symbol, Decimal("6"), Decimal("20"),
            fund_id=fund.id, investment_account_id=account.id,
        )

        first_txn, first = record_sell_transaction(
            self.db, account.investor_id, symbol, Decimal("5"), Decimal("30"),
            fund_id=fund.id, investment_account_id=account.id,
            commission=Decimal("2"), fee=Decimal("1"), swap=Decimal("0.50"),
        )
        second_txn, second = record_sell_transaction(
            self.db, account.investor_id, symbol, Decimal("5"), Decimal("25"),
            fund_id=fund.id, investment_account_id=account.id,
        )

        self.assertEqual(first.matched_qty, Decimal("5"))
        self.assertEqual(first.avg_buy_price, Decimal("12"))
        self.assertEqual(first.realized_profit, Decimal("86.50"))
        self.assertEqual(Decimal(first_txn.net_pnl), Decimal("86.5000"))
        self.assertEqual(second.matched_qty, Decimal("5"))
        self.assertEqual(second.avg_buy_price, Decimal("20"))
        self.assertEqual(second.realized_profit, Decimal("25"))
        self.assertEqual(Decimal(second_txn.net_pnl), Decimal("25.0000"))

    def test_fund_return_compounds_daily_returns_instead_of_adding_them(self):
        fund = self._new_fund("1.00")
        day_one = datetime(2099, 1, 1, 12, tzinfo=timezone.utc)
        rows = [
            FundValuation(
                fund_id=fund.id, valuation_date=day_one.date(),
                opening_assets=Decimal("100.00"), daily_pnl=Decimal("10.00"),
                closing_assets_before_flows=Decimal("110.00"), net_flow=Decimal("50.00"),
                closing_assets=Decimal("160.00"), units_outstanding=Decimal("160"),
                nav_per_unit=Decimal("1.00"),
            ),
            FundValuation(
                fund_id=fund.id, valuation_date=(day_one + timedelta(days=1)).date(),
                opening_assets=Decimal("160.00"), daily_pnl=Decimal("-16.00"),
                closing_assets_before_flows=Decimal("144.00"), net_flow=Decimal("-20.00"),
                closing_assets=Decimal("124.00"), units_outstanding=Decimal("124"),
                nav_per_unit=Decimal("1.00"),
            ),
        ]
        self.db.add_all(rows)
        self.db.flush()

        report = compute_fund_return(
            self.db, fund.id, day_one, day_one + timedelta(days=2),
        )

        # +10% followed by -10% compounds to -1%; the +50/-20 cash flows do
        # not enter either day's return numerator.
        self.assertAlmostEqual(report["fund_return_pct"], -1.0)
        self.assertAlmostEqual(report["total_pnl"], -6.0)
        self.assertEqual([row["net_flow"] for row in report["daily_returns"]], [50.0, -20.0])

    def test_current_day_snapshot_is_included_before_nominal_holding_time(self):
        suffix = uuid.uuid4().hex[:8]
        investor = Investor(
            email=f"date-boundary-{suffix}@example.test",
            full_name="Date Boundary Investor",
            is_active=True,
        )
        self.db.add(investor)
        self.db.flush()
        account = InvestmentAccount(
            investor_id=investor.id,
            account_name="Date Boundary",
            account_number=f"DATE-{suffix}",
            currency="USD",
            status="active",
            total_invested=Decimal("100"),
            current_value=Decimal("107.50"),
            manager_fund_balance={},
            fund_allocations={},
            investment_strategy="balanced",
        )
        self.db.add(account)
        self.db.flush()
        fund = self._new_fund("1.00")
        start = datetime(2097, 5, 1, 0, tzinfo=timezone.utc)
        query_end = start.replace(hour=12)
        nominal_holding_time = start.replace(hour=22)
        self.db.add(PortfolioHolding(
            investor_id=account.investor_id,
            fund_id=fund.id,
            holding_date=nominal_holding_time,
            snapshot_date=start.date(),
            account_value=Decimal("107.50"),
            shareholding_pct=Decimal("100"),
            daily_pnl=Decimal("7.50"),
            fund_nav=Decimal("107.50"),
            units=Decimal("100"),
            nav_per_unit=Decimal("1.075"),
            opening_value=Decimal("100"),
            opening_shareholding_pct=Decimal("100"),
            closing_value_before_flows=Decimal("107.50"),
            net_flow=Decimal("0"),
        ))
        self.db.flush()

        report = compute_investor_pnl(
            self.db, account.investor_id, start_date=start, end_date=query_end,
        )

        self.assertEqual(report["total_pnl"], 7.5)
        self.assertAlmostEqual(report["portfolio_return_pct"], 7.5)

    def test_portfolio_return_carries_unvalued_funds_in_daily_denominator(self):
        suffix = uuid.uuid4().hex[:8]
        investor = Investor(
            email=f"sparse-valuations-{suffix}@example.test",
            full_name="Sparse Valuation Investor",
            is_active=True,
        )
        self.db.add(investor)
        self.db.flush()
        account = InvestmentAccount(
            investor_id=investor.id,
            account_name="Sparse Valuations",
            account_number=f"SPARSE-{suffix}",
            currency="USD",
            status="active",
            total_invested=Decimal("3500"),
            current_value=Decimal("3568"),
            manager_fund_balance={},
            fund_allocations={},
            investment_strategy="balanced",
        )
        first_fund = self._new_fund("1.021")
        second_fund = self._new_fund("1.01733334")
        self.db.add(account)
        self.db.flush()

        start = datetime(2096, 7, 28, 22, tzinfo=timezone.utc)
        rows = [
            # The second fund exists throughout the period, but its first
            # valuation is two days later.  It must still be carried in the
            # opening denominator on July 28 and 29.
            (first_fund, 0, "2000", "0", "2000"),
            (first_fund, 1, "2000", "10", "2010"),
            (first_fund, 2, "2010", "15", "2025"),
            (second_fund, 2, "1500", "0", "1500"),
            (first_fund, 3, "2025", "5", "2030"),
            (second_fund, 3, "1500", "15", "1515"),
            (first_fund, 4, "2030", "12", "2042"),
            (second_fund, 4, "1515", "5", "1520"),
            # Only the second fund is valued on the final day; the first fund
            # carries forward unchanged at 2042.
            (second_fund, 5, "1520", "6", "1526"),
        ]
        for fund, day_offset, opening, pnl, closing in rows:
            when = start + timedelta(days=day_offset)
            self.db.add(PortfolioHolding(
                investor_id=investor.id,
                fund_id=fund.id,
                holding_date=when,
                snapshot_date=when.date(),
                account_value=Decimal(closing),
                shareholding_pct=Decimal("30"),
                daily_pnl=Decimal(pnl),
                opening_value=Decimal(opening),
                closing_value_before_flows=Decimal(closing),
                net_flow=Decimal("0"),
            ))
        self.db.flush()

        full_report = compute_investor_pnl(
            self.db,
            investor.id,
            start_date=start.replace(hour=0),
            end_date=(start + timedelta(days=5)).replace(hour=23),
        )
        monthly_report = compute_investor_pnl(
            self.db,
            investor.id,
            start_date=(start + timedelta(days=4)).replace(hour=0),
            end_date=(start + timedelta(days=5)).replace(hour=23),
        )

        self.assertEqual(full_report["total_pnl"], 68.0)
        self.assertAlmostEqual(full_report["portfolio_return_pct"], 68 / 3500 * 100)
        self.assertEqual(full_report["start_value"], 3500.0)
        self.assertEqual(full_report["end_value"], 3568.0)
        self.assertEqual(monthly_report["total_pnl"], 23.0)
        self.assertAlmostEqual(monthly_report["portfolio_return_pct"], 23 / 3545 * 100)

    def test_existing_fund_requires_today_valuation_before_settlement(self):
        account = self.db.query(InvestmentAccount).first()
        manager_user = self.db.query(User).filter_by(email="manager@fundinv.com").one()
        fund = self._new_fund("1.00")
        today = datetime.now(timezone.utc).date()
        self.db.add(FundPosition(
            investment_account_id=account.id,
            investor_id=account.investor_id,
            fund_id=fund.id,
            units=Decimal("100"),
            cost_basis=Decimal("100"),
        ))
        self.db.add(FundValuation(
            fund_id=fund.id,
            valuation_date=today - timedelta(days=1),
            opening_assets=Decimal("100"),
            daily_pnl=Decimal("0"),
            closing_assets_before_flows=Decimal("100"),
            net_flow=Decimal("0"),
            closing_assets=Decimal("100"),
            units_outstanding=Decimal("100"),
            nav_per_unit=Decimal("1"),
            status="finalized",
            source="manager_entry",
        ))
        flow = FundFlow(
            investor_id=account.investor_id,
            investment_account_id=account.id,
            fund_id=fund.id,
            flow_type="deposit",
            amount=Decimal("11"),
            status="pending_fund_transfer",
            request_id=f"VALUATION-GATE-{uuid.uuid4().hex}",
        )
        self.db.add(flow)
        self.db.flush()

        with self.assertRaisesRegex(ValueError, "Manager must finalize"):
            settle_fund_flow(self.db, flow)
        self.assertIsNone(
            self.db.query(FundBalanceEntry).filter_by(fund_flow_id=flow.id).first()
        )

        valuation, preview = finalize_valuation(
            self.db, fund, today, Decimal("10"), manager_user.id,
            "Settlement gate regression test",
        )
        settled = settle_fund_flow(self.db, flow)

        self.assertEqual(Decimal(str(preview["allocated_pnl_total"])), Decimal("10.0"))
        self.assertEqual(Decimal(valuation.nav_per_unit), Decimal("1.10000000"))
        self.assertEqual(settled.units_delta, Decimal("10.0000000000"))
        self.assertEqual(flow.status, "completed")

    def test_complete_two_investor_shareholding_and_pnl_lifecycle(self):
        suffix = uuid.uuid4().hex[:10]
        investors = [
            Investor(email=f"pnl-a-{suffix}@example.test", full_name="PNL Investor A", is_active=True),
            Investor(email=f"pnl-b-{suffix}@example.test", full_name="PNL Investor B", is_active=True),
        ]
        self.db.add_all(investors)
        self.db.flush()
        first = InvestmentAccount(
            investor_id=investors[0].id, account_name="PNL A", account_number=f"PNL-A-{suffix}",
            currency="USD", status="active", total_invested=0, current_value=0,
            manager_fund_balance={}, fund_allocations={}, investment_strategy="balanced",
        )
        second = InvestmentAccount(
            investor_id=investors[1].id, account_name="PNL B", account_number=f"PNL-B-{suffix}",
            currency="USD", status="active", total_invested=0, current_value=0,
            manager_fund_balance={}, fund_allocations={}, investment_strategy="balanced",
        )
        self.db.add_all([first, second])
        self.db.flush()
        fund = self._new_fund("1.00")
        day_one = datetime(2098, 6, 1, 22, tzinfo=timezone.utc)

        def settle(account, flow_type: str, amount: str, when: datetime):
            flow = FundFlow(
                investor_id=account.investor_id,
                investment_account_id=account.id,
                fund_id=fund.id,
                flow_type=flow_type,
                amount=Decimal(amount),
                status="pending_fund_transfer",
                request_id=f"E2E-{uuid.uuid4().hex}",
            )
            self.db.add(flow)
            self.db.flush()
            result = settle_fund_flow(self.db, flow)
            entry = self.db.query(FundBalanceEntry).filter(
                FundBalanceEntry.fund_flow_id == flow.id,
            ).one()
            entry.created_at = when
            self.db.flush()
            return result

        # Day 1: A subscribes $100 and B subscribes $300 at NAV 1.00.
        settle(first, "deposit", "100.00", day_one.replace(hour=12))
        settle(second, "deposit", "300.00", day_one.replace(hour=12))
        snapshot_daily_holdings(self.db, day_one)

        day_one_holdings = self.db.query(PortfolioHolding).filter(
            PortfolioHolding.fund_id == fund.id,
            PortfolioHolding.snapshot_date == day_one.date(),
        ).order_by(PortfolioHolding.investor_id).all()
        self.assertEqual([Decimal(h.daily_pnl) for h in day_one_holdings], [Decimal("0.0000"), Decimal("0.0000")])
        self.assertEqual([Decimal(h.shareholding_pct) for h in day_one_holdings], [Decimal("25.00000000"), Decimal("75.00000000")])
        self.assertEqual([Decimal(h.units) for h in day_one_holdings], [Decimal("100.0000000000"), Decimal("300.0000000000")])

        # Day 2: NAV rises 10%. Opening owners receive $10/$30 P&L, then A's
        # new $110 subscription buys 100 units and changes closing ownership.
        day_two = day_one + timedelta(days=1)
        fund.current_price = Decimal("1.10")
        settle(first, "deposit", "110.00", day_two.replace(hour=12))
        snapshot_daily_holdings(self.db, day_two)

        day_two_holdings = self.db.query(PortfolioHolding).filter(
            PortfolioHolding.fund_id == fund.id,
            PortfolioHolding.snapshot_date == day_two.date(),
        ).order_by(PortfolioHolding.investor_id).all()
        self.assertEqual([Decimal(h.daily_pnl) for h in day_two_holdings], [Decimal("10.0000"), Decimal("30.0000")])
        self.assertEqual([Decimal(h.net_flow) for h in day_two_holdings], [Decimal("110.0000"), Decimal("0.0000")])
        self.assertEqual([Decimal(h.shareholding_pct) for h in day_two_holdings], [Decimal("40.00000000"), Decimal("60.00000000")])
        self.assertEqual([Decimal(h.units) for h in day_two_holdings], [Decimal("200.0000000000"), Decimal("300.0000000000")])

        # Day 3: NAV falls 10%. P&L is allocated using opening 40/60
        # ownership; A then redeems $99 (100 units), returning ownership to 25/75.
        day_three = day_two + timedelta(days=1)
        fund.current_price = Decimal("0.99")
        settle(first, "withdrawal", "99.00", day_three.replace(hour=12))
        snapshot_daily_holdings(self.db, day_three)

        day_three_holdings = self.db.query(PortfolioHolding).filter(
            PortfolioHolding.fund_id == fund.id,
            PortfolioHolding.snapshot_date == day_three.date(),
        ).order_by(PortfolioHolding.investor_id).all()
        self.assertEqual([Decimal(h.daily_pnl) for h in day_three_holdings], [Decimal("-22.0000"), Decimal("-33.0000")])
        self.assertEqual([Decimal(h.net_flow) for h in day_three_holdings], [Decimal("-99.0000"), Decimal("0.0000")])
        self.assertEqual([Decimal(h.shareholding_pct) for h in day_three_holdings], [Decimal("25.00000000"), Decimal("75.00000000")])
        self.assertEqual([Decimal(h.units) for h in day_three_holdings], [Decimal("100.0000000000"), Decimal("300.0000000000")])

        valuations = self.db.query(FundValuation).filter(
            FundValuation.fund_id == fund.id,
        ).order_by(FundValuation.valuation_date).all()
        self.assertEqual([Decimal(v.units_outstanding) for v in valuations], [
            Decimal("400.0000000000"), Decimal("500.0000000000"), Decimal("400.0000000000"),
        ])
        self.assertEqual([Decimal(v.nav_per_unit) for v in valuations], [
            Decimal("1.00000000"), Decimal("1.10000000"), Decimal("0.99000000"),
        ])

        fund_report = compute_fund_return(self.db, fund.id, day_one, day_three + timedelta(days=1))
        first_report = compute_investor_pnl(self.db, first.investor_id, day_one, day_three + timedelta(days=1))
        second_report = compute_investor_pnl(self.db, second.investor_id, day_one, day_three + timedelta(days=1))
        self.assertAlmostEqual(fund_report["fund_return_pct"], -1.0)
        self.assertAlmostEqual(fund_report["total_pnl"], -15.0)
        self.assertAlmostEqual(first_report["total_pnl"], -12.0)
        self.assertAlmostEqual(second_report["total_pnl"], -3.0)
        self.assertAlmostEqual(first_report["portfolio_return_pct"], -1.0)
        self.assertAlmostEqual(second_report["portfolio_return_pct"], -1.0)

    def test_manager_finalization_allocates_fund_pnl_without_creating_units(self):
        suffix = uuid.uuid4().hex[:8]
        manager_user = self.db.query(User).filter_by(email="manager@fundinv.com").one()
        fund = self._new_fund("1.00")
        investors = [
            Investor(email=f"valuation-a-{suffix}@example.test", full_name="Valuation A", is_active=True),
            Investor(email=f"valuation-b-{suffix}@example.test", full_name="Valuation B", is_active=True),
        ]
        self.db.add_all(investors)
        self.db.flush()
        accounts = []
        for index, investor in enumerate((investors[0], investors[0], investors[1])):
            account = InvestmentAccount(
                investor_id=investor.id, account_name=f"Valuation {index}",
                account_number=f"VAL-{suffix}-{index}", currency="USD", status="active",
                total_invested=0, current_value=0, manager_fund_balance={},
                fund_allocations={}, investment_strategy="balanced",
            )
            self.db.add(account)
            accounts.append(account)
        self.db.flush()
        self.db.add_all([
            FundPosition(investment_account_id=accounts[0].id, investor_id=investors[0].id, fund_id=fund.id, units=4000, cost_basis=4000),
            FundPosition(investment_account_id=accounts[1].id, investor_id=investors[0].id, fund_id=fund.id, units=2000, cost_basis=2000),
            FundPosition(investment_account_id=accounts[2].id, investor_id=investors[1].id, fund_id=fund.id, units=4000, cost_basis=4000),
        ])
        self.db.flush()
        valuation_date = datetime.now(timezone.utc).date()

        preview = preview_valuation(self.db, fund, valuation_date, Decimal("500"))
        self.assertEqual(Decimal(str(preview["opening_assets"])), Decimal("10000.0"))
        self.assertEqual(Decimal(str(preview["closing_units"])), Decimal("10000.0"))
        self.assertEqual(Decimal(str(preview["nav_per_unit"])), Decimal("1.05"))
        self.assertEqual(len(preview["allocations"]), 2)
        self.assertEqual(
            sorted(Decimal(str(row["allocated_pnl"])) for row in preview["allocations"]),
            [Decimal("200.0"), Decimal("300.0")],
        )

        valuation, _ = finalize_valuation(
            self.db, fund, valuation_date, Decimal("500"), manager_user.id, "Daily administrator valuation",
        )
        self.assertEqual(Decimal(valuation.units_outstanding), Decimal("10000.0"))
        self.assertEqual(Decimal(valuation.nav_per_unit), Decimal("1.05"))
        self.assertEqual(valuation.source, "manager_entry")
        holdings = self.db.query(PortfolioHolding).filter_by(
            fund_id=fund.id, snapshot_date=valuation_date,
        ).all()
        self.assertEqual(len(holdings), 2)
        with self.assertRaisesRegex(ValueError, "already have a finalized valuation"):
            finalize_valuation(self.db, fund, valuation_date, Decimal("500"), manager_user.id)

    def test_manager_daily_pnl_is_suggested_from_single_fund_ticker(self):
        account = self.db.query(InvestmentAccount).first()
        fund = self._new_fund("1.00")
        self.db.add(FundPosition(
            investment_account_id=account.id,
            investor_id=account.investor_id,
            fund_id=fund.id,
            units=Decimal("10000"),
            cost_basis=Decimal("10000"),
        ))
        self.db.flush()

        snapshot = {
            fund.ticker: {
                "latestTrade": {"p": 110, "t": "2026-08-04T15:30:00Z"},
                "dailyBar": {"c": 110, "t": "2026-08-04T00:00:00Z"},
                "prevDailyBar": {"c": 100, "t": "2026-08-03T00:00:00Z"},
            }
        }
        with patch("services.valuation_service.get_snapshots", return_value=snapshot):
            suggestion = suggest_daily_pnl(self.db, fund, datetime.now(timezone.utc).date())

        self.assertTrue(suggestion["available"])
        self.assertEqual(Decimal(str(suggestion["suggested_return_pct"])), Decimal("10.0"))
        self.assertEqual(Decimal(str(suggestion["suggested_daily_pnl"])), Decimal("1000.0"))
        self.assertEqual(suggestion["source"], "alpaca_snapshot")
        self.assertEqual(suggestion["components"][0]["symbol"], fund.ticker)

    def test_manager_daily_pnl_uses_weighted_managed_fund_components(self):
        account = self.db.query(InvestmentAccount).first()
        fund = self._new_fund("1.00")
        fund.ticker = None
        self.db.add_all([
            FundPosition(
                investment_account_id=account.id,
                investor_id=account.investor_id,
                fund_id=fund.id,
                units=Decimal("10000"),
                cost_basis=Decimal("10000"),
            ),
            FundComponent(fund_id=fund.id, symbol="AAPL", component_name="Apple", asset_type="stock", target_pct=Decimal("60")),
            FundComponent(fund_id=fund.id, symbol="MSFT", component_name="Microsoft", asset_type="stock", target_pct=Decimal("40")),
        ])
        self.db.flush()

        snapshots = {
            "AAPL": {"latestTrade": {"p": 110}, "prevDailyBar": {"c": 100}},
            "MSFT": {"latestTrade": {"p": 190}, "prevDailyBar": {"c": 200}},
        }
        with patch("services.valuation_service.get_snapshots", return_value=snapshots):
            suggestion = suggest_daily_pnl(self.db, fund, datetime.now(timezone.utc).date())

        self.assertTrue(suggestion["available"])
        self.assertEqual(Decimal(str(suggestion["suggested_return_pct"])), Decimal("4.0"))
        self.assertEqual(Decimal(str(suggestion["suggested_daily_pnl"])), Decimal("400.0"))
        self.assertEqual(len(suggestion["components"]), 2)

    def test_market_suggestion_source_is_preserved_when_finalized(self):
        account = self.db.query(InvestmentAccount).first()
        manager_user = self.db.query(User).filter_by(email="manager@fundinv.com").one()
        fund = self._new_fund("1.00")
        self.db.add(FundPosition(
            investment_account_id=account.id,
            investor_id=account.investor_id,
            fund_id=fund.id,
            units=Decimal("10000"),
            cost_basis=Decimal("10000"),
        ))
        self.db.flush()

        valuation, _ = finalize_valuation(
            self.db,
            fund,
            datetime.now(timezone.utc).date(),
            Decimal("125"),
            manager_user.id,
            "Accepted automatic market calculation",
            "market_data_suggestion",
        )
        self.assertEqual(valuation.source, "market_data_suggestion")
        with self.assertRaisesRegex(ValueError, "already have a finalized valuation"):
            finalize_valuation(
                self.db,
                fund,
                datetime.now(timezone.utc).date(),
                Decimal("125"),
                manager_user.id,
            )

    def test_post_valuation_subscription_uses_finalized_nav_and_updates_all_ownership(self):
        suffix = uuid.uuid4().hex[:8]
        manager_user = self.db.query(User).filter_by(email="manager@fundinv.com").one()
        existing = Investor(email=f"opening-{suffix}@example.test", full_name="Opening Owner", is_active=True)
        newcomer = Investor(email=f"new-{suffix}@example.test", full_name="New Owner", is_active=True)
        self.db.add_all([existing, newcomer])
        self.db.flush()
        opening_account = InvestmentAccount(
            investor_id=existing.id, account_name="Opening", account_number=f"OPEN-{suffix}",
            currency="USD", status="active", total_invested=0, current_value=0,
            manager_fund_balance={}, fund_allocations={}, investment_strategy="balanced",
        )
        new_account = InvestmentAccount(
            investor_id=newcomer.id, account_name="New", account_number=f"NEW-{suffix}",
            currency="USD", status="active", total_invested=0, current_value=0,
            manager_fund_balance={}, fund_allocations={}, investment_strategy="balanced",
        )
        fund = self._new_fund("1.00")
        self.db.add_all([opening_account, new_account])
        self.db.flush()
        self.db.add(FundPosition(
            investment_account_id=opening_account.id, investor_id=existing.id,
            fund_id=fund.id, units=10000, cost_basis=10000,
        ))
        self.db.flush()
        today = datetime.now(timezone.utc).date()
        valuation, _ = finalize_valuation(self.db, fund, today, Decimal("500"), manager_user.id)

        flow = FundFlow(
            investor_id=newcomer.id, investment_account_id=new_account.id, fund_id=fund.id,
            flow_type="deposit", amount=Decimal("1050"), status="pending_fund_transfer",
            request_id=f"POST-VAL-{uuid.uuid4().hex}",
        )
        self.db.add(flow)
        self.db.flush()
        settled = settle_fund_flow(self.db, flow)
        self.assertEqual(settled.units_delta, Decimal("1000.0000000000"))
        self.assertEqual(Decimal(valuation.daily_pnl), Decimal("500.0000"))
        self.assertEqual(Decimal(valuation.net_flow), Decimal("1050.0000"))
        self.assertEqual(Decimal(valuation.closing_assets), Decimal("11550.0000"))
        self.assertEqual(Decimal(valuation.units_outstanding), Decimal("11000.0000000000"))
        self.assertEqual(Decimal(valuation.nav_per_unit), Decimal("1.05000000"))
        holdings = self.db.query(PortfolioHolding).filter_by(
            fund_id=fund.id, snapshot_date=today,
        ).order_by(PortfolioHolding.investor_id).all()
        self.assertEqual(len(holdings), 2)
        self.assertAlmostEqual(sum(float(row.shareholding_pct) for row in holdings), 100.0)
        new_holding = next(row for row in holdings if row.investor_id == newcomer.id)
        self.assertEqual(Decimal(new_holding.daily_pnl), Decimal("0.0000"))
        self.assertEqual(Decimal(new_holding.net_flow), Decimal("1050.0000"))
        self.assertEqual(Decimal(new_holding.account_value), Decimal("1050.0000"))


if __name__ == "__main__":
    unittest.main()
