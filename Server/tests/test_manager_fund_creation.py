import unittest
import uuid
from unittest.mock import Mock, patch

from fastapi import HTTPException
from sqlalchemy.orm import Session

from database import engine
from models import AuditLog, Fund, FundComponent, FundTargeting, InvestmentAccount, Investor, User
from routers.admin_routers import FundReviewRequest, review_fund
from routers.funds_routers import invest_fund, list_funds
from routers.manager_routers import CreateManagedFundRequest, create_managed_fund
from schemas.fund_schema import InvestRequest
from services.alpaca_service import _ASSET_CACHE, search_assets
from services.fund_targeting_service import expose_active_funds_to_investor, expose_fund_to_active_investors


class AlpacaAssetSearchTests(unittest.TestCase):
    def setUp(self):
        _ASSET_CACHE.clear()

    @patch("services.alpaca_service.requests.get")
    def test_search_normalizes_class_and_filters_by_symbol_or_name(self, mock_get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = [
            {"symbol": "MSFT", "name": "Microsoft Corp", "class": "us_equity", "status": "active", "tradable": True},
            {"symbol": "AAPL", "name": "Apple Inc.", "class": "us_equity", "status": "active", "tradable": True},
            {"symbol": "APP", "name": "Applovin Corp", "class": "us_equity", "status": "active", "tradable": True},
        ]
        mock_get.return_value = response

        results = search_assets(query="apple", limit=10)

        self.assertEqual([item["symbol"] for item in results], ["AAPL"])
        self.assertEqual(results[0]["asset_class"], "us_equity")
        params = mock_get.call_args.kwargs["params"]
        self.assertEqual(params, {"status": "active", "asset_class": "us_equity"})
        self.assertNotIn("q", params)
        self.assertNotIn("limit", params)

        search_assets(query="Microsoft", limit=10)
        self.assertEqual(mock_get.call_count, 1)


class ManagerFundCreationTests(unittest.TestCase):
    def setUp(self):
        self.connection = engine.connect()
        self.outer_transaction = self.connection.begin()
        self.db = Session(
            bind=self.connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        self.manager_user = self.db.query(User).filter(User.email == "manager@fundinv.com").one()

    def tearDown(self):
        self.db.close()
        self.outer_transaction.rollback()
        self.connection.close()

    def test_create_fund_persists_fund_component_and_audit_atomically(self):
        suffix = uuid.uuid4().hex[:10]
        request = CreateManagedFundRequest(
            name=f"Creation Test Fund {suffix}",
            description="Rollback-only integration test",
            strategy="growth",
            risk_level="medium-high",
            holdings=[{
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "asset_type": "stock",
                "allocation": 100,
            }],
        )

        response = create_managed_fund(request, current_user=self.manager_user, db=self.db)
        fund_id = response.data["id"]
        fund = self.db.query(Fund).filter(Fund.id == fund_id).one()
        component = self.db.query(FundComponent).filter(FundComponent.fund_id == fund_id).one()
        audit = self.db.query(AuditLog).filter(
            AuditLog.entity_type == "fund",
            AuditLog.entity_id == fund_id,
            AuditLog.action == "fund.created",
        ).one()

        self.assertEqual(fund.review_status, "pending_ops_review")
        self.assertFalse(fund.is_active)
        self.assertEqual(fund.portfolio_composition[0]["symbol"], "AAPL")
        self.assertEqual(component.symbol, "AAPL")
        self.assertEqual(float(component.target_pct), 100.0)
        self.assertEqual(audit.status, "success")

    def test_create_fund_rejects_empty_portfolio(self):
        request = CreateManagedFundRequest(name="Empty Fund", holdings=[])

        with self.assertRaises(HTTPException) as context:
            create_managed_fund(request, current_user=self.manager_user, db=self.db)

        self.assertEqual(context.exception.status_code, 400)

    @patch("routers.funds_routers.get_snapshots", return_value={})
    def test_operations_approval_makes_fund_visible_to_active_investors(self, _mock_snapshots):
        suffix = uuid.uuid4().hex[:10]
        created = create_managed_fund(
            CreateManagedFundRequest(
                name=f"Visible Fund {suffix}",
                holdings=[{
                    "symbol": "AAPL",
                    "name": "Apple Inc.",
                    "asset_type": "stock",
                    "allocation": 100,
                }],
            ),
            current_user=self.manager_user,
            db=self.db,
        )
        fund_id = created.data["id"]
        operations_user = self.db.query(User).filter(User.email == "operations@fundinv.com").one()

        approval = review_fund(
            fund_id,
            FundReviewRequest(decision="approve", notes="Automated visibility test"),
            current_user=operations_user,
            db=self.db,
        )

        active_investors = self.db.query(Investor).filter(Investor.is_active.is_(True)).all()
        targets = self.db.query(FundTargeting).filter(FundTargeting.fund_id == fund_id).all()
        self.assertEqual(approval.data["eligible_investors"], len(active_investors))
        self.assertEqual(len(targets), len(active_investors))
        self.assertTrue(all(target.is_visible for target in targets))

        investor_user = self.db.query(User).filter(User.email == "investor@fundinv.com").one()
        catalogue = list_funds(
            strategy="",
            fund_type="",
            search="",
            sort_by="name",
            db=self.db,
            current_user=investor_user,
        )
        self.assertIn(fund_id, [fund["id"] for fund in catalogue.data["funds"]])

        investor = self.db.query(Investor).filter(Investor.email == investor_user.email).one()
        account = self.db.query(InvestmentAccount).filter(
            InvestmentAccount.investor_id == investor.id,
            InvestmentAccount.deleted_at.is_(None),
        ).first()
        subscription = invest_fund(
            InvestRequest(fund_id=fund_id, amount=100, investment_account_id=account.id),
            db=self.db,
            current_user=investor_user,
        )
        self.assertEqual(subscription.data["fund_id"], fund_id)
        self.assertEqual(subscription.data["amount"], 100.0)
        self.assertIn(subscription.data["status"], {"awaiting_investor_payment", "pending_ops_team"})

        created_again, eligible_again = expose_fund_to_active_investors(self.db, fund_id)
        self.assertEqual(created_again, 0)
        self.assertEqual(eligible_again, len(active_investors))

    def test_automatic_visibility_preserves_existing_investor_opt_out(self):
        fund = Fund(
            name=f"Opt-out Test Fund {uuid.uuid4().hex[:10]}",
            fund_type="managed",
            is_active=True,
            review_status="approved",
        )
        self.db.add(fund)
        self.db.flush()
        investor = self.db.query(Investor).filter(Investor.is_active.is_(True)).first()
        self.db.add(FundTargeting(
            investor_id=investor.id,
            fund_id=fund.id,
            is_visible=False,
            risk_tolerance="conservative",
        ))
        self.db.flush()

        expose_fund_to_active_investors(self.db, fund.id)
        self.db.flush()
        target = self.db.query(FundTargeting).filter(
            FundTargeting.investor_id == investor.id,
            FundTargeting.fund_id == fund.id,
        ).one()

        self.assertFalse(target.is_visible)
        self.assertEqual(target.risk_tolerance, "conservative")

    def test_new_active_investor_receives_existing_approved_funds_idempotently(self):
        investor = Investor(
            email=f"visibility-{uuid.uuid4().hex}@example.com",
            full_name="Visibility Test Investor",
            is_active=True,
        )
        self.db.add(investor)
        self.db.flush()

        created, eligible = expose_active_funds_to_investor(self.db, investor.id)
        created_again, eligible_again = expose_active_funds_to_investor(self.db, investor.id)
        targets = self.db.query(FundTargeting).filter(
            FundTargeting.investor_id == investor.id,
        ).all()

        self.assertEqual(created, eligible)
        self.assertGreater(eligible, 0)
        self.assertEqual(len(targets), eligible)
        self.assertTrue(all(target.is_visible for target in targets))
        self.assertEqual(created_again, 0)
        self.assertEqual(eligible_again, eligible)


if __name__ == "__main__":
    unittest.main()
