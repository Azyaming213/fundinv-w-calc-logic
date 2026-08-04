"""Challenge-aligned Manager preview/finalisation for open-ended funds."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from models import Fund, FundBalanceEntry, FundComponent, FundPosition, FundValuation, PortfolioHolding
from services.alpaca_service import get_bars, get_snapshots


MONEY = Decimal("0.0001")
UNITS = Decimal("0.0000000001")
NAV = Decimal("0.00000001")
PCT = Decimal("0.00000001")


def dec(value) -> Decimal:
    return Decimal(str(value or 0))


def _day_bounds(value: date) -> tuple[datetime, datetime]:
    start = datetime.combine(value, time.min, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def _previous_valuation(db: Session, fund_id: int, valuation_date: date) -> FundValuation | None:
    return (
        db.query(FundValuation)
        .filter(FundValuation.fund_id == fund_id, FundValuation.valuation_date < valuation_date)
        .order_by(FundValuation.valuation_date.desc(), FundValuation.id.desc())
        .first()
    )


def _bar_date(bar: dict) -> date | None:
    timestamp = str(bar.get("t") or "")
    if not timestamp:
        return None
    try:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _historical_market_return(symbol: str, valuation_date: date) -> dict | None:
    bars = get_bars(
        symbol,
        timeframe="1Day",
        limit=20,
        start=(valuation_date - timedelta(days=14)).isoformat(),
        end=(valuation_date + timedelta(days=1)).isoformat(),
    )
    eligible = sorted(
        ((bar_date, bar) for bar in bars if (bar_date := _bar_date(bar)) and bar_date <= valuation_date),
        key=lambda item: item[0],
    )
    if len(eligible) < 2:
        return None
    current_date, current_bar = eligible[-1]
    previous_date, previous_bar = eligible[-2]
    current_price = dec(current_bar.get("c"))
    previous_price = dec(previous_bar.get("c"))
    if current_price <= 0 or previous_price <= 0:
        return None
    return {
        "symbol": symbol,
        "current_price": current_price,
        "previous_price": previous_price,
        "return": current_price / previous_price - Decimal("1"),
        "as_of": current_date.isoformat(),
        "previous_as_of": previous_date.isoformat(),
        "price_source": "alpaca_daily_bars",
    }


def _current_market_return(symbol: str, snapshot: dict) -> dict | None:
    latest_trade = snapshot.get("latestTrade") or {}
    daily_bar = snapshot.get("dailyBar") or {}
    previous_bar = snapshot.get("prevDailyBar") or {}
    current_price = dec(latest_trade.get("p") or daily_bar.get("c"))
    previous_price = dec(previous_bar.get("c"))
    if current_price <= 0 or previous_price <= 0:
        return None
    timestamp = latest_trade.get("t") or daily_bar.get("t")
    return {
        "symbol": symbol,
        "current_price": current_price,
        "previous_price": previous_price,
        "return": current_price / previous_price - Decimal("1"),
        "as_of": str(timestamp or datetime.now(timezone.utc).isoformat()),
        "previous_as_of": str(previous_bar.get("t") or ""),
        "price_source": "alpaca_snapshot",
    }


def suggest_daily_pnl(db: Session, fund: Fund, valuation_date: date) -> dict:
    """Calculate a manager-reviewable daily P&L from the fund's market exposure.

    A listed single-instrument fund uses its own ticker. A managed fund uses
    its configured component weights. The suggestion is deliberately not
    finalized automatically: the Manager remains responsible for reviewing
    the figures and any accounting adjustments before committing the NAV.
    """
    zero_preview = preview_valuation(db, fund, valuation_date, Decimal("0"))
    components = db.query(FundComponent).filter(FundComponent.fund_id == fund.id).all()
    exposure = []
    for component in components:
        symbol = (component.symbol or (component.component_fund.ticker if component.component_fund else None) or "").upper()
        if symbol:
            exposure.append({
                "symbol": symbol,
                "name": component.component_name,
                "weight": dec(component.target_pct),
            })
    if not exposure and fund.ticker:
        exposure = [{"symbol": fund.ticker.upper(), "name": fund.name, "weight": Decimal("100")}]

    base = {
        "fund_id": fund.id,
        "fund_name": fund.name,
        "valuation_date": valuation_date.isoformat(),
        "opening_assets": zero_preview["opening_assets"],
        "opening_nav_per_unit": zero_preview["opening_nav_per_unit"],
        "available": False,
        "suggested_daily_pnl": None,
        "suggested_return_pct": None,
        "source": None,
        "as_of": None,
        "components": [],
        "missing_symbols": [],
    }
    if not exposure:
        return {**base, "message": "This fund has no market-priced ticker or portfolio components. Enter P&L manually with an audit note."}

    symbols = list(dict.fromkeys(item["symbol"] for item in exposure))
    today = datetime.now(timezone.utc).date()
    snapshots = get_snapshots(symbols) if valuation_date >= today else {}
    market_moves: dict[str, dict] = {}
    for symbol in symbols:
        move = _current_market_return(symbol, snapshots.get(symbol, {})) if snapshots else None
        if move is None:
            move = _historical_market_return(symbol, valuation_date)
        if move is not None:
            market_moves[symbol] = move

    missing = [symbol for symbol in symbols if symbol not in market_moves]
    if missing:
        return {
            **base,
            "missing_symbols": missing,
            "message": "Automatic P&L is unavailable because market prices are missing for: " + ", ".join(missing) + ". Enter P&L manually with an audit note.",
        }

    total_weight = sum((item["weight"] for item in exposure), Decimal("0"))
    if total_weight <= 0:
        return {**base, "message": "The fund has no positive portfolio weights. Correct its composition before valuation."}

    weighted_return = Decimal("0")
    component_rows = []
    for item in exposure:
        move = market_moves[item["symbol"]]
        normalized_weight = item["weight"] / total_weight
        contribution = normalized_weight * move["return"]
        weighted_return += contribution
        component_rows.append({
            "symbol": item["symbol"],
            "name": item["name"],
            "weight_pct": float((normalized_weight * Decimal("100")).quantize(PCT)),
            "previous_price": float(move["previous_price"]),
            "current_price": float(move["current_price"]),
            "return_pct": float((move["return"] * Decimal("100")).quantize(PCT)),
            "contribution_pct": float((contribution * Decimal("100")).quantize(PCT)),
            "as_of": move["as_of"],
        })

    opening_assets = dec(zero_preview["opening_assets"])
    suggested_pnl = (opening_assets * weighted_return).quantize(MONEY, rounding=ROUND_HALF_UP)
    as_of_values = [row["as_of"] for row in component_rows if row["as_of"]]
    sources = {market_moves[symbol]["price_source"] for symbol in symbols}
    source = sources.pop() if len(sources) == 1 else "alpaca_market_data"
    return {
        **base,
        "available": True,
        "suggested_daily_pnl": float(suggested_pnl),
        "suggested_return_pct": float((weighted_return * Decimal("100")).quantize(PCT)),
        "source": source,
        "as_of": min(as_of_values) if as_of_values else None,
        "components": component_rows,
        "message": "Calculated from market price changes and the fund's configured exposure. Review before finalizing.",
    }


def settlement_valuation_status(
    db: Session,
    fund_id: int,
    settlement_date: date | None = None,
) -> tuple[bool, str | None]:
    """Return whether a unit-changing flow may settle on the given date.

    A brand-new fund with no valuation history may accept its first
    subscription. Once daily valuation has started, every later settlement
    must use that day's finalized NAV so subscriptions and redemptions cannot
    dilute the opening owners or make the Manager's P&L allocation impossible.
    """
    settlement_date = settlement_date or datetime.now(timezone.utc).date()
    prior_valuation = db.query(FundValuation.id).filter(
        FundValuation.fund_id == fund_id,
        FundValuation.status == "finalized",
        FundValuation.valuation_date < settlement_date,
    ).first()
    if prior_valuation is None:
        return True, None

    current_valuation = db.query(FundValuation.id).filter(
        FundValuation.fund_id == fund_id,
        FundValuation.status == "finalized",
        FundValuation.valuation_date == settlement_date,
    ).first()
    if current_valuation is not None:
        return True, None

    return False, (
        f"Manager must finalize {settlement_date.isoformat()} P&L/NAV for this fund "
        "before Operations can settle subscriptions or redemptions."
    )


def preview_valuation(db: Session, fund: Fund, valuation_date: date, daily_pnl: Decimal) -> dict:
    if valuation_date > datetime.now(timezone.utc).date():
        raise ValueError("A valuation cannot be finalized for a future date")
    existing = db.query(FundValuation).filter_by(
        fund_id=fund.id, valuation_date=valuation_date
    ).first()
    if existing and existing.status == "finalized" and existing.source in ("manager_entry", "market_data_suggestion"):
        raise ValueError("This fund and date already have a finalized valuation")

    previous = _previous_valuation(db, fund.id, valuation_date)
    positions = db.query(FundPosition).filter(FundPosition.fund_id == fund.id).all()
    tracked_units = sum((dec(position.units) for position in positions), Decimal("0"))
    opening_units = dec(previous.units_outstanding) if previous else tracked_units
    opening_nav = dec(previous.nav_per_unit) if previous else dec(fund.current_price or 1)
    opening_assets = dec(previous.closing_assets) if previous else opening_units * opening_nav
    if opening_units <= 0 or opening_assets <= 0:
        raise ValueError("The fund needs positive opening units and assets before valuation")

    start, end = _day_bounds(valuation_date)
    same_day_entries = db.query(FundBalanceEntry).filter(
        FundBalanceEntry.fund_id == fund.id,
        FundBalanceEntry.created_at >= start,
        FundBalanceEntry.created_at < end,
    ).all()
    if same_day_entries:
        raise ValueError("Finalize daily P&L before Operations settles subscriptions or redemptions for that date")

    daily_pnl = dec(daily_pnl).quantize(MONEY, rounding=ROUND_HALF_UP)
    closing_before_flows = opening_assets + daily_pnl
    if closing_before_flows <= 0:
        raise ValueError("Daily P&L would reduce fund assets to zero or below")
    nav = (closing_before_flows / opening_units).quantize(NAV, rounding=ROUND_HALF_UP)

    allocation_by_investor: dict[int, dict] = {}
    allocated_total = Decimal("0")
    for position in positions:
        units = dec(position.units)
        row = allocation_by_investor.setdefault(position.investor_id, {
            "investor_id": position.investor_id,
            "investment_account_ids": [],
            "units": Decimal("0"),
        })
        row["investment_account_ids"].append(position.investment_account_id)
        row["units"] += units

    allocations = []
    for row in allocation_by_investor.values():
        units = row["units"]
        share = units / opening_units if opening_units else Decimal("0")
        allocated = (daily_pnl * share).quantize(MONEY, rounding=ROUND_HALF_UP)
        allocated_total += allocated
        allocations.append({
            "investor_id": row["investor_id"],
            "investment_account_ids": row["investment_account_ids"],
            "units": float(units),
            "opening_share_pct": float((share * 100).quantize(PCT)),
            "allocated_pnl": float(allocated),
            "opening_value": float((units * opening_nav).quantize(MONEY)),
            "closing_value_before_flows": float((units * nav).quantize(MONEY)),
        })

    return {
        "fund_id": fund.id,
        "fund_name": fund.name,
        "valuation_date": valuation_date.isoformat(),
        "previous_valuation_date": previous.valuation_date.isoformat() if previous else None,
        "opening_assets": float(opening_assets.quantize(MONEY)),
        "opening_units": float(opening_units.quantize(UNITS)),
        "opening_nav_per_unit": float(opening_nav.quantize(NAV)),
        "daily_pnl": float(daily_pnl),
        "closing_assets_before_flows": float(closing_before_flows.quantize(MONEY)),
        "net_flow": 0.0,
        "closing_assets": float(closing_before_flows.quantize(MONEY)),
        "closing_units": float(opening_units.quantize(UNITS)),
        "nav_per_unit": float(nav),
        "allocated_pnl_total": float(allocated_total),
        "external_ownership_pnl": float(daily_pnl - allocated_total),
        "allocations": allocations,
    }


def finalize_valuation(
    db: Session,
    fund: Fund,
    valuation_date: date,
    daily_pnl: Decimal,
    user_id: int,
    notes: str | None = None,
    source: str = "manager_entry",
) -> tuple[FundValuation, dict]:
    preview = preview_valuation(db, fund, valuation_date, daily_pnl)
    valuation = db.query(FundValuation).filter_by(
        fund_id=fund.id, valuation_date=valuation_date
    ).first()
    if valuation is None:
        valuation = FundValuation(fund_id=fund.id, valuation_date=valuation_date)
        db.add(valuation)
    valuation.opening_assets = dec(preview["opening_assets"])
    valuation.daily_pnl = dec(preview["daily_pnl"])
    valuation.closing_assets_before_flows = dec(preview["closing_assets_before_flows"])
    valuation.net_flow = Decimal("0")
    valuation.closing_assets = dec(preview["closing_assets"])
    valuation.units_outstanding = dec(preview["closing_units"])
    valuation.nav_per_unit = dec(preview["nav_per_unit"])
    valuation.status = "finalized"
    valuation.source = source
    valuation.finalized_by_user_id = user_id
    valuation.finalized_at = datetime.now(timezone.utc)
    valuation.notes = notes
    fund.current_price = dec(preview["nav_per_unit"])

    as_of = datetime.combine(valuation_date, time(hour=22), tzinfo=timezone.utc)
    db.query(PortfolioHolding).filter(
        PortfolioHolding.fund_id == fund.id,
        PortfolioHolding.snapshot_date == valuation_date,
    ).delete(synchronize_session=False)
    for allocation in preview["allocations"]:
        holding = PortfolioHolding(
            investor_id=allocation["investor_id"],
            fund_id=fund.id,
            holding_date=as_of,
            snapshot_date=valuation_date,
            account_value=allocation["closing_value_before_flows"],
            shareholding_pct=allocation["opening_share_pct"],
            daily_pnl=allocation["allocated_pnl"],
            fund_nav=preview["closing_assets"],
            units=allocation["units"],
            nav_per_unit=preview["nav_per_unit"],
            opening_value=allocation["opening_value"],
            opening_shareholding_pct=allocation["opening_share_pct"],
            closing_value_before_flows=allocation["closing_value_before_flows"],
            net_flow=0,
        )
        db.add(holding)
    db.flush()
    return valuation, preview


def append_settled_flow_to_finalized_valuation(db: Session, entry: FundBalanceEntry) -> None:
    """Append post-P&L cash/unit effects without rewriting finalized P&L or NAV."""
    entry_date = entry.created_at.date() if entry.created_at else datetime.now(timezone.utc).date()
    valuation = db.query(FundValuation).filter_by(
        fund_id=entry.fund_id, valuation_date=entry_date, status="finalized"
    ).with_for_update().first()
    if valuation is None:
        return
    if abs(dec(entry.nav_per_unit) - dec(valuation.nav_per_unit)) > Decimal("0.00000001"):
        raise ValueError("Settled flow NAV does not match the finalized daily NAV")
    valuation.net_flow = dec(valuation.net_flow) + dec(entry.amount)
    valuation.closing_assets = dec(valuation.closing_assets_before_flows) + dec(valuation.net_flow)
    valuation.units_outstanding = dec(valuation.units_outstanding) + dec(entry.units)

    position = db.query(FundPosition).filter_by(
        investment_account_id=entry.investment_account_id, fund_id=entry.fund_id
    ).one()
    holding = db.query(PortfolioHolding).filter_by(
        investor_id=position.investor_id,
        fund_id=entry.fund_id,
        snapshot_date=entry_date,
    ).with_for_update().first()
    if holding is None:
        holding = PortfolioHolding(
            investor_id=position.investor_id,
            fund_id=entry.fund_id,
            holding_date=datetime.combine(entry_date, time(hour=22), tzinfo=timezone.utc),
            snapshot_date=entry_date,
            account_value=0,
            shareholding_pct=0,
            daily_pnl=0,
            fund_nav=valuation.closing_assets_before_flows,
            units=0,
            nav_per_unit=valuation.nav_per_unit,
            opening_value=0,
            opening_shareholding_pct=0,
            closing_value_before_flows=0,
            net_flow=0,
        )
        db.add(holding)
    holding.net_flow = dec(holding.net_flow) + dec(entry.amount)
    db.flush()

    # A settled flow changes closing ownership for every Investor, even though
    # only the affected Investor receives a net-flow amount on this ledger row.
    holdings = db.query(PortfolioHolding).filter_by(
        fund_id=entry.fund_id, snapshot_date=entry_date
    ).with_for_update().all()
    for daily_holding in holdings:
        investor_units = sum((
            dec(row.units) for row in db.query(FundPosition).filter_by(
                investor_id=daily_holding.investor_id, fund_id=entry.fund_id
            ).all()
        ), Decimal("0"))
        daily_holding.units = investor_units
        daily_holding.account_value = investor_units * dec(valuation.nav_per_unit)
        daily_holding.shareholding_pct = (
            investor_units / dec(valuation.units_outstanding) * Decimal("100")
            if dec(valuation.units_outstanding) > 0 else Decimal("0")
        )
        daily_holding.fund_nav = valuation.closing_assets
