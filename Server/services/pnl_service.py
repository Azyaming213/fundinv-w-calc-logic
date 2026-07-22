"""PNL calculation service.

Implements the methodology described in the challenge statement:

  Section 8.1 — Investor fund shareholding tracking
  Section 8.2 — Performance measurement (total dollar PNL + fund return)
  Section 5.4 — Investment transactions dataset (FIFO realized PNL)

Daily fund accounting (Section 8.1):
  1. Fund begins day with total assets x; each investor owns a share of x.
  2. Day-end balance = x + PNL generated during the day.
  3. PNL is split among investors in proportion to their start-of-day share %.
  4. Deposit/withdrawal requests processed: investor dollar share changes.
  5. % shareholding recomputed -> next day's starting balance.

Realized PNL on trades (Section 5.4): FIFO cost-basis matching.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from models import (
    InvestmentTransaction,
    PortfolioHolding,
    InvestmentAccount,
    Fund,
    FundFlow,
)
from services.alpaca_service import get_positions, get_account


TWO_PLACES = Decimal("0.01")


@dataclass
class FifoResult:
    realized_profit: Decimal
    remaining_qty: Decimal
    matched_qty: Decimal
    avg_buy_price: Decimal


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_ticket(prefix: str = "T") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"


def _position_key(investor_id: int, symbol: str, fund_id: Optional[int]) -> str:
    fund_part = str(fund_id) if fund_id else "none"
    return f"{investor_id}:{symbol}:{fund_part}"


# ──────────────────────────────────────────────────────────
# FIFO realized PNL matching (Section 5.4)
# ──────────────────────────────────────────────────────────

def compute_realized_pnl_fifo(
    db: Session,
    investor_id: int,
    symbol: str,
    sell_qty: Decimal,
    sell_price: Decimal,
    fund_id: Optional[int] = None,
    commission: Decimal = Decimal("0"),
    fee: Decimal = Decimal("0"),
    swap: Decimal = Decimal("0"),
) -> FifoResult:
    """Match sell_qty against open buy deals in FIFO order.

    Open buys are InvestmentTransaction rows with entry='in' (or trade_type='buy')
    whose position_id still has unmatched volume. We track matching via the
    position_id -> lots of (remaining_qty, buy_price).
    """
    sells = (
        db.query(InvestmentTransaction)
        .filter(
            InvestmentTransaction.investor_id == investor_id,
            InvestmentTransaction.symbol == symbol,
            InvestmentTransaction.entry == "out",
        )
        .order_by(InvestmentTransaction.trade_time.asc())
        .all()
    )

    buys = (
        db.query(InvestmentTransaction)
        .filter(
            InvestmentTransaction.investor_id == investor_id,
            InvestmentTransaction.symbol == symbol,
            InvestmentTransaction.entry == "in",
        )
        .order_by(InvestmentTransaction.trade_time.asc())
        .all()
    )

    open_buys: list[tuple[InvestmentTransaction, Decimal]] = []
    for buy in buys:
        pos_key = buy.position_id or _position_key(investor_id, symbol, fund_id)
        consumed = Decimal("0")
        for sell in sells:
            if sell.position_id and sell.position_id == pos_key:
                consumed += Decimal(sell.volume)
        remaining = Decimal(buy.volume) - consumed
        if remaining > 0:
            open_buys.append((buy, remaining))

    remaining_to_match = Decimal(sell_qty)
    realized_profit = Decimal("0")
    matched_qty = Decimal("0")
    weighted_price_sum = Decimal("0")

    for buy, available in open_buys:
        if remaining_to_match <= 0:
            break
        qty = min(available, remaining_to_match)
        buy_price = Decimal(buy.price)
        gross_profit = (Decimal(sell_price) - buy_price) * qty
        realized_profit += gross_profit
        matched_qty += qty
        weighted_price_sum += buy_price * qty
        remaining_to_match -= qty

    avg_buy_price = (
        weighted_price_sum / matched_qty
        if matched_qty > 0 else Decimal("0")
    )

    realized_profit -= Decimal(commission) + Decimal(fee) + Decimal(swap)

    return FifoResult(
        realized_profit=realized_profit,
        remaining_qty=remaining_to_match,
        matched_qty=matched_qty,
        avg_buy_price=avg_buy_price,
    )


def record_buy_transaction(
    db: Session,
    investor_id: int,
    symbol: str,
    volume: Decimal,
    price: Decimal,
    trade_time: Optional[datetime] = None,
    fund_id: Optional[int] = None,
    investment_account_id: Optional[int] = None,
    external_id: Optional[str] = None,
    commission: Decimal = Decimal("0"),
    fee: Decimal = Decimal("0"),
    comment: Optional[str] = None,
) -> InvestmentTransaction:
    """Record a buy deal as an InvestmentTransaction (entry='in')."""
    pos_key = _position_key(investor_id, symbol, fund_id)
    ticket = _new_ticket("BUY")

    txn = InvestmentTransaction(
        ticket=ticket,
        order_ticket=ticket,
        investor_id=investor_id,
        fund_id=fund_id,
        investment_account_id=investment_account_id,
        position_id=pos_key,
        trade_time=trade_time or _utcnow(),
        time_msc=int((trade_time or _utcnow()).timestamp() * 1000),
        trade_type="buy",
        entry="in",
        symbol=symbol,
        volume=volume,
        price=price,
        profit=Decimal("0"),
        commission=-abs(Decimal(commission)),
        fee=-abs(Decimal(fee)),
        swap=Decimal("0"),
        net_pnl=-abs(Decimal(commission)) - abs(Decimal(fee)),
        external_id=external_id,
        comment=comment,
    )
    db.add(txn)
    db.flush()
    return txn


def record_sell_transaction(
    db: Session,
    investor_id: int,
    symbol: str,
    volume: Decimal,
    price: Decimal,
    trade_time: Optional[datetime] = None,
    fund_id: Optional[int] = None,
    investment_account_id: Optional[int] = None,
    external_id: Optional[str] = None,
    commission: Decimal = Decimal("0"),
    fee: Decimal = Decimal("0"),
    swap: Decimal = Decimal("0"),
    comment: Optional[str] = None,
) -> tuple[InvestmentTransaction, FifoResult]:
    """Record a sell deal, computing realized PNL via FIFO (Section 5.4)."""
    fifo = compute_realized_pnl_fifo(
        db=db,
        investor_id=investor_id,
        symbol=symbol,
        sell_qty=volume,
        sell_price=price,
        fund_id=fund_id,
        commission=commission,
        fee=fee,
        swap=swap,
    )

    matched_qty = fifo.matched_qty
    pos_key = _position_key(investor_id, symbol, fund_id)
    ticket = _new_ticket("SELL")

    profit = fifo.realized_profit

    txn = InvestmentTransaction(
        ticket=ticket,
        order_ticket=ticket,
        investor_id=investor_id,
        fund_id=fund_id,
        investment_account_id=investment_account_id,
        position_id=pos_key,
        trade_time=trade_time or _utcnow(),
        time_msc=int((trade_time or _utcnow()).timestamp() * 1000),
        trade_type="sell",
        entry="out",
        symbol=symbol,
        volume=matched_qty,
        price=price,
        profit=profit,
        commission=-abs(Decimal(commission)),
        fee=-abs(Decimal(fee)),
        swap=-abs(Decimal(swap)),
        net_pnl=profit,
        external_id=external_id,
        comment=comment or f"FIFO matched {matched_qty} @ avg {fifo.avg_buy_price}",
    )
    db.add(txn)
    db.flush()
    return txn, fifo


# ──────────────────────────────────────────────────────────
# Fund-level daily PNL snapshot (Sections 8.1 and 8.2)
# ──────────────────────────────────────────────────────────

def get_fund_nav(db: Session, fund: Fund) -> Decimal:
    """Compute a fund's current net asset value.

    For managed funds we sum the manager_fund_balance[fund_id] across all
    accounts (cash allocated to the fund) plus the market value of any
    Alpaca positions held in the fund's symbol (when fund.ticker is set we
    treat positions in that ticker as fund holdings).

    For ETF / stock funds the NAV is the market value of the symbol position.
    """
    if fund.fund_type in ("etf", "stock", "bond", "crypto") and fund.ticker:
        positions = get_positions()
        if isinstance(positions, list):
            for p in positions:
                if p.get("symbol") == fund.ticker:
                    return Decimal(str(p.get("market_value", "0")))
        return Decimal("0")

    total = Decimal("0")
    accounts = (
        db.query(InvestmentAccount)
        .filter(InvestmentAccount.deleted_at.is_(None), InvestmentAccount.status == "active")
        .all()
    )
    for acc in accounts:
        mfb = acc.manager_fund_balance or {}
        total += Decimal(str(mfb.get(str(fund.id), "0")))
    return total


def get_investor_fund_dollar_share(account: InvestmentAccount, fund_id: int) -> Decimal:
    """Return the investor's dollar share of a fund from manager_fund_balance."""
    mfb = account.manager_fund_balance or {}
    return Decimal(str(mfb.get(str(fund_id), "0")))


def snapshot_daily_holdings(db: Session, as_of: Optional[datetime] = None) -> int:
    """Snapshot each investor's holdings per fund for a given day.

    Implements Section 8.1:
      1. Compute fund NAV (total assets).
      2. For each investor: dollar share = manager_fund_balance[fund_id].
      3. shareholding_pct = dollar_share / fund_nav * 100.
      4. daily_pnl = (today_nav - yesterday_nav) * investor_share_pct.
      5. Insert PortfolioHolding row.

    Returns number of rows inserted.
    """
    as_of = as_of or _utcnow()
    day_start = as_of.replace(hour=0, minute=0, second=0, microsecond=0)
    inserted = 0

    funds = db.query(Fund).filter(Fund.is_active.is_(True), Fund.review_status == "approved").all()

    for fund in funds:
        nav_today = get_fund_nav(db, fund)
        if nav_today <= 0:
            continue

        yesterday = (
            db.query(PortfolioHolding)
            .filter(
                PortfolioHolding.fund_id == fund.id,
                PortfolioHolding.holding_date < day_start,
            )
            .order_by(PortfolioHolding.holding_date.desc())
            .first()
        )
        nav_yesterday = Decimal(yesterday.fund_nav) if yesterday and yesterday.fund_nav else nav_today
        fund_daily_pnl = nav_today - nav_yesterday

        accounts = (
            db.query(InvestmentAccount)
            .filter(
                InvestmentAccount.deleted_at.is_(None),
                InvestmentAccount.status == "active",
            )
            .all()
        )

        for account in accounts:
            dollar_share = get_investor_fund_dollar_share(account, fund.id)
            if dollar_share <= 0:
                continue
            share_pct = (dollar_share / nav_today * Decimal("100")) if nav_today > 0 else Decimal("0")
            investor_daily_pnl = fund_daily_pnl * share_pct / Decimal("100")

            existing = (
                db.query(PortfolioHolding)
                .filter(
                    PortfolioHolding.investor_id == account.investor_id,
                    PortfolioHolding.fund_id == fund.id,
                    PortfolioHolding.holding_date >= day_start,
                    PortfolioHolding.holding_date < day_start + timedelta(days=1),
                )
                .first()
            )
            if existing:
                existing.account_value = dollar_share
                existing.shareholding_pct = share_pct
                existing.daily_pnl = investor_daily_pnl
                existing.fund_nav = nav_today
            else:
                db.add(PortfolioHolding(
                    investor_id=account.investor_id,
                    fund_id=fund.id,
                    holding_date=as_of,
                    account_value=dollar_share,
                    shareholding_pct=share_pct,
                    daily_pnl=investor_daily_pnl,
                    fund_nav=nav_today,
                ))
                inserted += 1

    db.commit()
    return inserted


def process_fund_flows_for_day(db: Session, as_of: Optional[datetime] = None) -> int:
    """Process completed deposit/withdrawal flows for a fund on a given day.

    Section 8.1 step 4: deposits increase an investor's dollar share,
    withdrawals decrease it. This updates manager_fund_balance so the next
    snapshot reflects the new share.
    """
    from sqlalchemy.orm.attributes import flag_modified

    as_of = as_of or _utcnow()
    day_start = as_of.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    flows = (
        db.query(FundFlow)
        .filter(
            FundFlow.status.in_(["completed", "completed_provider_confirmed"]),
            FundFlow.processed_at >= day_start,
            FundFlow.processed_at < day_end,
            FundFlow.fund_id.isnot(None),
        )
        .all()
    )

    processed = 0
    for flow in flows:
        if not flow.fund_id or not flow.investment_account_id:
            continue
        account = (
            db.query(InvestmentAccount)
            .filter(InvestmentAccount.id == flow.investment_account_id)
            .first()
        )
        if not account:
            continue

        mfb = dict(account.manager_fund_balance or {})
        key = str(flow.fund_id)
        current = Decimal(str(mfb.get(key, "0")))

        if flow.flow_type == "deposit":
            mfb[key] = float(current + Decimal(flow.amount))
        elif flow.flow_type == "withdrawal":
            mfb[key] = float(max(Decimal("0"), current - Decimal(flow.amount)))

        account.manager_fund_balance = mfb
        flag_modified(account, "manager_fund_balance")
        processed += 1

    db.commit()
    return processed


# ──────────────────────────────────────────────────────────
# Performance measurement (Section 8.2)
# ──────────────────────────────────────────────────────────

def compute_investor_pnl(
    db: Session,
    investor_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> dict:
    """Compute total dollar PNL and fund return for an investor.

    Total dollar PNL (Section 8.2(i)) = sum of daily_pnl across the period.
    Fund return (Section 8.2(ii)) = compounded daily fund return over the period.
    """
    end_date = end_date or _utcnow()
    start_date = start_date or (end_date - timedelta(days=365))

    holdings = (
        db.query(PortfolioHolding)
        .filter(
            PortfolioHolding.investor_id == investor_id,
            PortfolioHolding.holding_date >= start_date,
            PortfolioHolding.holding_date <= end_date,
        )
        .order_by(PortfolioHolding.holding_date.asc())
        .all()
    )

    total_pnl = sum((Decimal(h.daily_pnl) for h in holdings), Decimal("0"))

    fund_ids = {h.fund_id for h in holdings if h.fund_id}
    fund_returns: dict[int, Decimal] = {}
    for fid in fund_ids:
        fund_holdings = [h for h in holdings if h.fund_id == fid]
        if not fund_holdings:
            continue
        compounded = Decimal("1")
        prev_nav = Decimal(fund_holdings[0].fund_nav) if fund_holdings[0].fund_nav else None
        for h in fund_holdings:
            if h.fund_nav and prev_nav and prev_nav > 0:
                daily_ret = Decimal(h.daily_pnl) / prev_nav
                compounded *= (Decimal("1") + daily_ret)
            if h.fund_nav:
                prev_nav = Decimal(h.fund_nav)
        fund_returns[fid] = (compounded - Decimal("1")) * Decimal("100")

    realized_pnl = (
        db.query(func.sum(InvestmentTransaction.net_pnl))
        .filter(
            InvestmentTransaction.investor_id == investor_id,
            InvestmentTransaction.entry == "out",
            InvestmentTransaction.trade_time >= start_date,
            InvestmentTransaction.trade_time <= end_date,
        )
        .scalar()
    ) or Decimal("0")

    start_value = Decimal(holdings[0].account_value) if holdings else Decimal("0")
    end_value = Decimal(holdings[-1].account_value) if holdings else Decimal("0")
    portfolio_return = (
        ((end_value - start_value) / start_value * Decimal("100"))
        if start_value > 0 else Decimal("0")
    )

    return {
        "total_pnl": float(total_pnl),
        "realized_pnl": float(realized_pnl),
        "unrealized_pnl": float(total_pnl - Decimal(realized_pnl)),
        "portfolio_return_pct": float(portfolio_return),
        "fund_returns_pct": {fid: float(ret) for fid, ret in fund_returns.items()},
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "start_value": float(start_value),
        "end_value": float(end_value),
    }


def compute_fund_return(
    db: Session,
    fund_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> dict:
    """Compute compounded fund return over a period (Section 8.2(ii))."""
    end_date = end_date or _utcnow()
    start_date = start_date or (end_date - timedelta(days=365))

    holdings = (
        db.query(PortfolioHolding)
        .filter(
            PortfolioHolding.fund_id == fund_id,
            PortfolioHolding.holding_date >= start_date,
            PortfolioHolding.holding_date <= end_date,
        )
        .order_by(PortfolioHolding.holding_date.asc())
        .all()
    )

    if not holdings:
        return {
            "fund_id": fund_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "fund_return_pct": 0.0,
            "total_pnl": 0.0,
            "daily_returns": [],
        }

    compounded = Decimal("1")
    daily_returns = []
    prev_nav = Decimal(holdings[0].fund_nav) if holdings[0].fund_nav else None
    total_pnl = Decimal("0")

    for h in holdings:
        total_pnl += Decimal(h.daily_pnl)
        if h.fund_nav and prev_nav and prev_nav > 0:
            daily_ret = Decimal(h.daily_pnl) / prev_nav
            compounded *= (Decimal("1") + daily_ret)
            daily_returns.append({
                "date": h.holding_date.isoformat(),
                "daily_pnl": float(h.daily_pnl),
                "fund_nav": float(h.fund_nav),
                "daily_return_pct": float(daily_ret * Decimal("100")),
            })
        if h.fund_nav:
            prev_nav = Decimal(h.fund_nav)

    return {
        "fund_id": fund_id,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "fund_return_pct": float((compounded - Decimal("1")) * Decimal("100")),
        "total_pnl": float(total_pnl),
        "daily_returns": daily_returns,
    }


# ──────────────────────────────────────────────────────────
# Current unrealized PNL via Alpaca positions
# ──────────────────────────────────────────────────────────

def compute_unrealized_pnl(db: Session, investor_id: int) -> dict:
    """Return current unrealized PNL broken down by symbol from Alpaca."""
    positions = get_positions()
    if not isinstance(positions, list):
        return {"total_unrealized_pnl": 0.0, "positions": []}

    total = Decimal("0")
    rows = []
    for p in positions:
        upl = Decimal(str(p.get("unrealized_pl", "0")))
        total += upl
        rows.append({
            "symbol": p.get("symbol"),
            "qty": float(p.get("qty", 0)),
            "avg_entry_price": float(p.get("avg_entry_price", 0)),
            "current_price": float(p.get("current_price", 0)),
            "market_value": float(p.get("market_value", 0)),
            "unrealized_pl": float(upl),
            "unrealized_plpc": float(p.get("unrealized_plpc", 0)),
        })

    account = get_account()
    return {
        "total_unrealized_pnl": float(total),
        "portfolio_value": float(account.get("portfolio_value", 0)) if account else 0,
        "cash": float(account.get("cash", 0)) if account else 0,
        "positions": rows,
    }
