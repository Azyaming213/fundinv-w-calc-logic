"""Transactional unit accounting for approved fund cash flows."""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from models import (
    Fund,
    FundBalanceEntry,
    FundFlow,
    FundPosition,
    FundValuation,
    InvestmentAccount,
)


MONEY = Decimal("0.0001")
UNITS = Decimal("0.0000000001")
NAV = Decimal("0.00000001")


@dataclass(frozen=True)
class SettlementResult:
    applied: bool
    units_delta: Decimal
    nav_per_unit: Decimal
    resulting_units: Decimal
    resulting_value: Decimal


def _decimal(value, default: str = "0") -> Decimal:
    if value is None:
        return Decimal(default)
    return Decimal(str(value))


def current_nav_per_unit(db: Session, fund: Fund) -> Decimal:
    latest = (
        db.query(FundValuation)
        .filter(FundValuation.fund_id == fund.id)
        .order_by(FundValuation.valuation_date.desc())
        .first()
    )
    if latest and _decimal(latest.nav_per_unit) > 0:
        return _decimal(latest.nav_per_unit).quantize(NAV)
    if fund.current_price and _decimal(fund.current_price) > 0:
        return _decimal(fund.current_price).quantize(NAV)
    return Decimal("1.00000000")


def settle_fund_flow(
    db: Session,
    flow: FundFlow,
    provider_reference: str | None = None,
) -> SettlementResult:
    """Settle one provider-confirmed flow exactly once.

    The unique fund-flow ledger entry is the idempotency boundary. Rows are
    locked so concurrent webhook and operations requests cannot both apply it.
    """
    flow = (
        db.query(FundFlow)
        .filter(FundFlow.id == flow.id)
        .with_for_update()
        .one()
    )
    existing = (
        db.query(FundBalanceEntry)
        .filter(FundBalanceEntry.fund_flow_id == flow.id)
        .first()
    )
    if existing:
        position = (
            db.query(FundPosition)
            .filter(
                FundPosition.investment_account_id == flow.investment_account_id,
                FundPosition.fund_id == flow.fund_id,
            )
            .first()
        )
        resulting_units = _decimal(position.units) if position else Decimal("0")
        nav = _decimal(existing.nav_per_unit, "1")
        return SettlementResult(False, Decimal("0"), nav, resulting_units, resulting_units * nav)

    if flow.status == "completed":
        raise ValueError("Completed fund flow has no accounting ledger entry")
    if flow.flow_type not in {"deposit", "withdrawal"}:
        raise ValueError(f"Unsupported fund flow type: {flow.flow_type}")
    if not flow.investment_account_id or not flow.fund_id:
        raise ValueError("Fund flow is missing its account or fund")

    account = (
        db.query(InvestmentAccount)
        .filter(InvestmentAccount.id == flow.investment_account_id)
        .with_for_update()
        .one()
    )
    fund = db.query(Fund).filter(Fund.id == flow.fund_id).with_for_update().one()
    position = (
        db.query(FundPosition)
        .filter(
            FundPosition.investment_account_id == account.id,
            FundPosition.fund_id == fund.id,
        )
        .with_for_update()
        .first()
    )
    if position is None:
        position = FundPosition(
            investment_account_id=account.id,
            investor_id=flow.investor_id,
            fund_id=fund.id,
            units=Decimal("0"),
            cost_basis=Decimal("0"),
        )
        db.add(position)
        db.flush()

    amount = _decimal(flow.amount).quantize(MONEY, rounding=ROUND_HALF_UP)
    nav = current_nav_per_unit(db, fund)
    units = (amount / nav).quantize(UNITS, rounding=ROUND_HALF_UP)
    current_units = _decimal(position.units)
    current_cost = _decimal(position.cost_basis)

    if flow.flow_type == "deposit":
        units_delta = units
        position.units = current_units + units
        position.cost_basis = current_cost + amount
        signed_amount = amount
        entry_type = "deposit_subscribed"
        account.total_invested = _decimal(account.total_invested) + amount
    else:
        if units > current_units:
            raise ValueError("Fund position has insufficient units for this withdrawal")
        units_delta = -units
        remaining_units = current_units - units
        cost_reduction = (
            current_cost * units / current_units if current_units > 0 else Decimal("0")
        )
        position.units = max(Decimal("0"), remaining_units)
        position.cost_basis = max(Decimal("0"), current_cost - cost_reduction)
        signed_amount = -amount
        entry_type = "withdrawal_redeemed"

    resulting_units = _decimal(position.units)
    resulting_value = (resulting_units * nav).quantize(MONEY, rounding=ROUND_HALF_UP)

    # Compatibility mirror for existing screens; normalized FundPosition is authoritative.
    balances = dict(account.manager_fund_balance or {})
    balances[str(fund.id)] = str(resulting_value)
    account.manager_fund_balance = balances
    flag_modified(account, "manager_fund_balance")

    flow.status = "completed"
    flow.processed_at = datetime.now(timezone.utc)
    if provider_reference:
        flow.provider_reference = provider_reference

    db.add(FundBalanceEntry(
        investment_account_id=account.id,
        fund_id=fund.id,
        fund_flow_id=flow.id,
        entry_type=entry_type,
        amount=signed_amount,
        units=units_delta,
        nav_per_unit=nav,
        provider_reference=provider_reference,
    ))
    db.flush()

    return SettlementResult(True, units_delta, nav, resulting_units, resulting_value)
