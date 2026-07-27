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
from datetime import date, datetime, timedelta, timezone
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
    FundBalanceEntry,
    FundPosition,
    FundValuation,
)
from services.alpaca_service import get_positions


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
            InvestmentTransaction.fund_id == fund_id,
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
            InvestmentTransaction.fund_id == fund_id,
        )
        .order_by(InvestmentTransaction.trade_time.asc())
        .all()
    )

    # Reconstruct remaining lots by consuming historical sales once, in FIFO
    # order. The former implementation subtracted every sale from every buy.
    historical_sold = sum((Decimal(s.volume) for s in sells), Decimal("0"))
    open_buys: list[tuple[InvestmentTransaction, Decimal]] = []
    for buy in buys:
        buy_volume = Decimal(buy.volume)
        consumed = min(buy_volume, historical_sold)
        historical_sold -= consumed
        remaining = buy_volume - consumed
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
    snapshot_date = as_of.date()
    day_start = as_of.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    inserted = 0

    funds = db.query(Fund).filter(Fund.is_active.is_(True), Fund.review_status == "approved").all()
    for fund in funds:
        positions = db.query(FundPosition).filter(FundPosition.fund_id == fund.id).all()
        if not positions:
            continue

        previous = (
            db.query(FundValuation)
            .filter(FundValuation.fund_id == fund.id, FundValuation.valuation_date < snapshot_date)
            .order_by(FundValuation.valuation_date.desc())
            .first()
        )
        previous_nav = Decimal(previous.nav_per_unit) if previous else None
        market_nav = Decimal(fund.current_price) if fund.current_price and Decimal(fund.current_price) > 0 else None
        if market_nav is None:
            market_nav = previous_nav or Decimal("1")

        entries = (
            db.query(FundBalanceEntry)
            .filter(
                FundBalanceEntry.fund_id == fund.id,
                FundBalanceEntry.created_at >= day_start,
                FundBalanceEntry.created_at < day_end,
            )
            .all()
        )
        net_flow = sum((Decimal(e.amount) for e in entries), Decimal("0"))
        flow_units = sum((Decimal(e.units or 0) for e in entries), Decimal("0"))
        closing_units = sum((Decimal(p.units) for p in positions), Decimal("0"))
        opening_units = max(Decimal("0"), closing_units - flow_units)
        opening_nav = previous_nav or market_nav
        opening_assets = opening_units * opening_nav
        daily_pnl = opening_units * (market_nav - opening_nav)
        closing_before_flows = opening_assets + daily_pnl
        closing_assets = closing_before_flows + net_flow

        valuation = (
            db.query(FundValuation)
            .filter(FundValuation.fund_id == fund.id, FundValuation.valuation_date == snapshot_date)
            .first()
        )
        if valuation is None:
            valuation = FundValuation(fund_id=fund.id, valuation_date=snapshot_date)
            db.add(valuation)
        valuation.opening_assets = opening_assets
        valuation.daily_pnl = daily_pnl
        valuation.closing_assets_before_flows = closing_before_flows
        valuation.net_flow = net_flow
        valuation.closing_assets = closing_assets
        valuation.units_outstanding = closing_units
        valuation.nav_per_unit = market_nav

        investor_ids = {p.investor_id for p in positions}
        for investor_id in investor_ids:
            investor_positions = [p for p in positions if p.investor_id == investor_id]
            investor_closing_units = sum((Decimal(p.units) for p in investor_positions), Decimal("0"))
            account_ids = {p.investment_account_id for p in investor_positions}
            investor_entries = [e for e in entries if e.investment_account_id in account_ids]
            investor_flow = sum((Decimal(e.amount) for e in investor_entries), Decimal("0"))
            investor_flow_units = sum((Decimal(e.units or 0) for e in investor_entries), Decimal("0"))
            investor_opening_units = max(Decimal("0"), investor_closing_units - investor_flow_units)
            opening_value = investor_opening_units * opening_nav
            investor_pnl = investor_opening_units * (market_nav - opening_nav)
            closing_value_before_flows = opening_value + investor_pnl
            closing_value = investor_closing_units * market_nav
            opening_share_pct = (
                investor_opening_units / opening_units * Decimal("100")
                if opening_units > 0 else Decimal("0")
            )
            closing_share_pct = (
                investor_closing_units / closing_units * Decimal("100")
                if closing_units > 0 else Decimal("0")
            )

            holding = (
                db.query(PortfolioHolding)
                .filter(
                    PortfolioHolding.investor_id == investor_id,
                    PortfolioHolding.fund_id == fund.id,
                    PortfolioHolding.snapshot_date == snapshot_date,
                )
                .first()
            )
            if holding is None:
                holding = PortfolioHolding(
                    investor_id=investor_id,
                    fund_id=fund.id,
                    holding_date=as_of,
                    snapshot_date=snapshot_date,
                    account_value=closing_value,
                    shareholding_pct=closing_share_pct,
                )
                db.add(holding)
                inserted += 1
            holding.account_value = closing_value
            holding.shareholding_pct = closing_share_pct
            holding.daily_pnl = investor_pnl
            holding.fund_nav = closing_assets
            holding.units = investor_closing_units
            holding.nav_per_unit = market_nav
            holding.opening_value = opening_value
            holding.opening_shareholding_pct = opening_share_pct
            holding.closing_value_before_flows = closing_value_before_flows
            holding.net_flow = investor_flow

    db.commit()
    return inserted


def process_fund_flows_for_day(db: Session, as_of: Optional[datetime] = None) -> int:
    """Process completed deposit/withdrawal flows for a fund on a given day.

    Section 8.1 step 4: deposits increase an investor's dollar share,
    withdrawals decrease it. This updates manager_fund_balance so the next
    snapshot reflects the new share.
    """
    # Cash flows are applied transactionally when their payment/payout is
    # confirmed. The old nightly replay double-counted every completed flow
    # each time the job ran. Keep this compatibility hook as a read-only
    # count for job reporting.
    from models import FundBalanceEntry

    as_of = as_of or _utcnow()
    day_start = as_of.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    return (
        db.query(FundBalanceEntry)
        .filter(
            FundBalanceEntry.created_at >= day_start,
            FundBalanceEntry.created_at < day_end,
        )
        .count()
    )


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
        valuations = (
            db.query(FundValuation)
            .filter(
                FundValuation.fund_id == fid,
                FundValuation.valuation_date >= start_date.date(),
                FundValuation.valuation_date <= end_date.date(),
            )
            .order_by(FundValuation.valuation_date.asc())
            .all()
        )
        compounded = Decimal("1")
        for valuation in valuations:
            opening_assets = Decimal(valuation.opening_assets)
            if opening_assets > 0:
                daily_ret = Decimal(valuation.daily_pnl) / opening_assets
                compounded *= (Decimal("1") + daily_ret)
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

    holdings_by_date: dict[date, list[PortfolioHolding]] = {}
    for holding in holdings:
        holding_day = holding.snapshot_date or holding.holding_date.date()
        holdings_by_date.setdefault(holding_day, []).append(holding)

    portfolio_growth = Decimal("1")
    for day_holdings in holdings_by_date.values():
        opening = sum((Decimal(h.opening_value or 0) for h in day_holdings), Decimal("0"))
        pnl = sum((Decimal(h.daily_pnl or 0) for h in day_holdings), Decimal("0"))
        if opening > 0:
            portfolio_growth *= Decimal("1") + pnl / opening
    portfolio_return = (portfolio_growth - Decimal("1")) * Decimal("100")

    ordered_days = sorted(holdings_by_date)
    start_value = (
        sum((Decimal(h.opening_value or h.account_value) for h in holdings_by_date[ordered_days[0]]), Decimal("0"))
        if ordered_days else Decimal("0")
    )
    end_value = (
        sum((Decimal(h.account_value) for h in holdings_by_date[ordered_days[-1]]), Decimal("0"))
        if ordered_days else Decimal("0")
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

    valuations = (
        db.query(FundValuation)
        .filter(
            FundValuation.fund_id == fund_id,
            FundValuation.valuation_date >= start_date.date(),
            FundValuation.valuation_date <= end_date.date(),
        )
        .order_by(FundValuation.valuation_date.asc())
        .all()
    )

    if not valuations:
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
    total_pnl = Decimal("0")

    for valuation in valuations:
        pnl = Decimal(valuation.daily_pnl)
        opening_assets = Decimal(valuation.opening_assets)
        total_pnl += pnl
        if opening_assets > 0:
            daily_ret = pnl / opening_assets
            compounded *= (Decimal("1") + daily_ret)
            daily_returns.append({
                "date": valuation.valuation_date.isoformat(),
                "daily_pnl": float(pnl),
                "opening_assets": float(opening_assets),
                "net_flow": float(valuation.net_flow),
                "closing_assets": float(valuation.closing_assets),
                "nav_per_unit": float(valuation.nav_per_unit),
                "daily_return_pct": float(daily_ret * Decimal("100")),
            })

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
    """Return only this investor's locally attributable Alpaca positions.

    Alpaca is configured as one omnibus paper account. Quantities and cost
    basis therefore come from the investor's own transaction ledger; Alpaca
    supplies current market prices only.
    """
    positions = get_positions()
    if not isinstance(positions, list):
        return {"total_unrealized_pnl": 0.0, "positions": []}

    market_by_symbol = {p.get("symbol"): p for p in positions if p.get("symbol")}
    transactions = (
        db.query(InvestmentTransaction)
        .filter(InvestmentTransaction.investor_id == investor_id)
        .order_by(InvestmentTransaction.trade_time.asc(), InvestmentTransaction.id.asc())
        .all()
    )
    by_symbol: dict[str, list[InvestmentTransaction]] = {}
    for transaction in transactions:
        by_symbol.setdefault(transaction.symbol, []).append(transaction)

    total = Decimal("0")
    rows = []
    for symbol, symbol_transactions in by_symbol.items():
        lots: list[list[Decimal]] = []
        for transaction in symbol_transactions:
            quantity = Decimal(transaction.volume)
            if transaction.entry == "in" or transaction.trade_type == "buy":
                lots.append([quantity, Decimal(transaction.price)])
                continue
            remaining_sale = quantity
            for lot in lots:
                if remaining_sale <= 0:
                    break
                consumed = min(lot[0], remaining_sale)
                lot[0] -= consumed
                remaining_sale -= consumed

        open_lots = [lot for lot in lots if lot[0] > 0]
        local_qty = sum((lot[0] for lot in open_lots), Decimal("0"))
        if local_qty <= 0 or symbol not in market_by_symbol:
            continue
        local_cost = sum((lot[0] * lot[1] for lot in open_lots), Decimal("0"))
        avg_entry = local_cost / local_qty
        current_price = Decimal(str(market_by_symbol[symbol].get("current_price", "0")))
        market_value = local_qty * current_price
        upl = market_value - local_cost
        total += upl
        rows.append({
            "symbol": symbol,
            "qty": float(local_qty),
            "avg_entry_price": float(avg_entry),
            "current_price": float(current_price),
            "market_value": float(market_value),
            "unrealized_pl": float(upl),
            "unrealized_plpc": float(upl / local_cost) if local_cost > 0 else 0.0,
        })

    return {
        "total_unrealized_pnl": float(total),
        "portfolio_value": float(sum((Decimal(str(row["market_value"])) for row in rows), Decimal("0"))),
        "cash": 0.0,
        "positions": rows,
    }
