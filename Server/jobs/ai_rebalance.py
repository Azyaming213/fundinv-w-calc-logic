from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from database import SessionLocal
from models import InvestmentAccount, Fund, FundComponent, Order
from services.alpaca_service import place_order
from services.audit_service import get_system_user, log_event


DRIFT_THRESHOLD = 0.05
MINIMUM_TRADE = 1.00


def run_auto_rebalance():
    """Move approved managed funds toward their stored percentage targets.

    The account JSON fields remain a compatibility cache. Each generated trade is
    recorded as an Order with its fund ID so reconciliation can audit the action.
    """
    db: Session = SessionLocal()
    trade_count = 0
    try:
        system_user = get_system_user(db)
        funds = db.query(Fund).filter(
            Fund.fund_type == "managed",
            Fund.is_active == True,
            Fund.review_status == "approved",
        ).all()

        for fund in funds:
            components = db.query(FundComponent).filter(FundComponent.fund_id == fund.id).all()
            if not components:
                continue
            accounts = db.query(InvestmentAccount).filter(
                InvestmentAccount.deleted_at.is_(None),
                InvestmentAccount.status == "active",
            ).all()

            for account in accounts:
                mfb = dict(account.manager_fund_balance or {})
                cash = float(mfb.get(str(fund.id), 0))
                allocations = dict(account.fund_allocations or {})
                current_value = cash + sum(float(allocations.get(component.symbol or "", 0)) for component in components)
                if current_value <= 0:
                    continue

                for component in components:
                    symbol = component.symbol
                    if not symbol:
                        continue
                    target = current_value * float(component.target_pct) / 100
                    current = float(allocations.get(symbol, 0))
                    delta = target - current
                    if abs(delta) < max(MINIMUM_TRADE, current_value * DRIFT_THRESHOLD):
                        continue
                    side = "buy" if delta > 0 else "sell"
                    amount = abs(delta)
                    if side == "sell":
                        amount = min(amount, current)
                    if amount < MINIMUM_TRADE:
                        continue

                    result = place_order(symbol=symbol, notional=amount, side=side)
                    if result.get("error"):
                        log_event(
                            db=db,
                            user_id=system_user.id if system_user else None,
                            action="rebalance.order.failed",
                            details=f"Automatic rebalance failed for {fund.name} / {symbol}",
                            entity_type="fund",
                            entity_id=fund.id,
                            changes={"account_id": account.id, "symbol": symbol, "amount": amount, "error": result.get("message")},
                            status="failure",
                        )
                        continue

                    if side == "buy":
                        mfb[str(fund.id)] = max(0, cash - amount)
                        allocations[symbol] = current + amount
                    else:
                        allocations[symbol] = max(0, current - amount)
                        mfb[str(fund.id)] = cash + amount
                    cash = float(mfb.get(str(fund.id), 0))
                    account.manager_fund_balance = mfb
                    account.fund_allocations = allocations
                    flag_modified(account, "manager_fund_balance")
                    flag_modified(account, "fund_allocations")
                    db.add(Order(
                        investor_id=account.investor_id,
                        investment_account_id=account.id,
                        fund_id=fund.id,
                        alpaca_order_id=result.get("id", ""),
                        symbol=symbol,
                        side=side,
                        amount=amount,
                        status=result.get("status", "accepted"),
                        performed_by_user_id=system_user.id if system_user else None,
                    ))
                    trade_count += 1

        db.commit()
        print(f"[REBALANCE] Generated {trade_count} automatic fund trades")
    finally:
        db.close()
