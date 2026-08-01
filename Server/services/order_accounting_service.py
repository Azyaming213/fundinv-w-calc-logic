"""Idempotent accounting for asynchronously filled external orders."""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from models import InvestmentAccount, InvestmentTransaction, Order
from services.pnl_service import record_buy_transaction, record_sell_transaction


def _decimal(value) -> Decimal:
    return Decimal(str(value or 0))


def apply_filled_order(db: Session, order: Order, provider_order: dict) -> bool:
    """Apply a confirmed fill once; return False when already accounted."""
    order = db.query(Order).filter(Order.id == order.id).with_for_update().one()
    if order.accounting_recorded_at is not None:
        return False

    status = str(provider_order.get("status") or order.status or "new")
    order.status = status
    filled_qty = _decimal(provider_order.get("filled_qty"))
    filled_price = _decimal(provider_order.get("filled_avg_price"))
    if status != "filled" or filled_qty <= 0 or filled_price <= 0:
        return False

    # The external ID is also an idempotency boundary for the deal ledger.
    existing = db.query(InvestmentTransaction).filter(
        InvestmentTransaction.external_id == order.alpaca_order_id
    ).first()
    if existing is None:
        if order.side == "buy":
            record_buy_transaction(
                db, order.investor_id, order.symbol, filled_qty, filled_price,
                fund_id=order.fund_id,
                investment_account_id=order.investment_account_id,
                external_id=order.alpaca_order_id,
                comment="Manager underlying-fund trade",
            )
        else:
            record_sell_transaction(
                db, order.investor_id, order.symbol, filled_qty, filled_price,
                fund_id=order.fund_id,
                investment_account_id=order.investment_account_id,
                external_id=order.alpaca_order_id,
                comment="Manager underlying-fund trade",
            )

    account = db.query(InvestmentAccount).filter(
        InvestmentAccount.id == order.investment_account_id
    ).with_for_update().one()
    allocations = dict(account.fund_allocations or {})
    filled_value = (filled_qty * filled_price).quantize(Decimal("0.0001"))
    if order.side == "buy":
        allocations[order.symbol] = float(_decimal(allocations.get(order.symbol)) + filled_value)
    else:
        allocations[order.symbol] = float(max(Decimal("0"), _decimal(allocations.get(order.symbol)) - filled_value))
    account.fund_allocations = allocations
    flag_modified(account, "fund_allocations")

    order.filled_qty = filled_qty
    order.filled_price = filled_price
    order.status = "filled"
    order.accounting_recorded_at = datetime.now(timezone.utc)
    db.flush()
    return True
