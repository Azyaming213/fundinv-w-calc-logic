import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_

from database import get_db
from models import Fund, FundInvestment, Investor, InvestmentAccount, FundFlow, FundTargeting, Manager
from schemas.fund_schema import FundResponse, FundListResponse, InvestRequest, InvestResponse
from dependencies import get_current_user, require_claim
from services.alpaca_service import (
    get_positions,
    get_orders,
    get_asset,
    get_snapshots,
    get_bars,
    search_assets,
    STRATEGY_QUERIES,
    STRATEGY_META,
)
from services.audit_service import log_event, AUDIT_ACTIONS
import appconstants as AppConstants

router = APIRouter(prefix="/api/funds", tags=["Funds"])


@router.get("/strategies")
def list_strategies():
    return {"success": True, "data": {"strategies": STRATEGY_META}, "error": None}


@router.get("/", response_model=FundListResponse)
def list_funds(
    strategy: str = Query("", description="Filter by strategy: aggressive, growth, balanced, conservative, income"),
    fund_type: str = Query("", description="Filter by type: etf, stock, crypto, bond"),
    search: str = Query("", description="Search by name or ticker"),
    sort_by: str = Query("name", description="Sort by: name, ytd_return, expense_ratio"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(Fund).filter(Fund.is_active == True, Fund.review_status == "approved")

    if current_user.role and current_user.role.name == "investor":
        investor = db.query(Investor).filter(Investor.email == current_user.email).first()
        if investor:
            query = query.join(FundTargeting, FundTargeting.fund_id == Fund.id)\
                         .filter(FundTargeting.investor_id == investor.id)\
                         .filter(FundTargeting.is_visible == True)
        else:
            query = query.filter(Fund.fund_type.in_(["etf", "bond", "managed"]))

    if strategy:
        query = query.filter(Fund.strategy == strategy)
    if fund_type:
        query = query.filter(Fund.fund_type == fund_type)
    if search:
        term = f"%{search}%"
        query = query.filter(
            or_(Fund.name.ilike(term), Fund.ticker.ilike(term))
        )

    if sort_by == "ytd_return":
        query = query.order_by(Fund.ytd_return.desc().nullslast())
    elif sort_by == "expense_ratio":
        query = query.order_by(Fund.expense_ratio.asc().nullslast())
    else:
        query = query.order_by(Fund.name.asc())

    funds = query.all()

    tickers = [f.ticker for f in funds if f.ticker]
    live_prices: dict[str, dict] = {}
    if tickers:
        try:
            snaps = get_snapshots(tickers)
            for ticker in tickers:
                snap = snaps.get(ticker, {})
                if snap:
                    lt = snap.get("latestTrade", {})
                    pd = snap.get("prevDailyBar", {})
                    p = lt.get("p", 0)
                    pc = pd.get("c", 0) if pd else 0
                    live_prices[ticker] = {
                        "price": p,
                        "change_pct": round(((p - pc) / pc * 100), 2) if pc > 0 else 0,
                    }
        except Exception:
            pass

    fund_list = []
    for f in funds:
        fd = FundResponse.model_validate(f).model_dump()
        if f.created_by:
            fd["manager_name"] = f.created_by.full_name
        if f.ticker and f.ticker in live_prices:
            fd["current_price"] = live_prices[f.ticker]["price"]
            fd["change_pct"] = live_prices[f.ticker]["change_pct"]
        fund_list.append(fd)

    return FundListResponse(
        success=True,
        data={"funds": fund_list},
        error=None,
    )


@router.get("/discover")
def discover_funds(
    strategy: str = Query(..., description="Strategy to discover: aggressive, growth, balanced, conservative, income"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if strategy not in STRATEGY_QUERIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid strategy. Choose from: {', '.join(STRATEGY_QUERIES.keys())}",
        )

    symbols = STRATEGY_QUERIES[strategy]
    snapshots = get_snapshots(symbols)

    results = []
    for symbol in symbols:
        snap = snapshots.get(symbol, {})
        if not snap:
            continue

        latest_trade = snap.get("latestTrade", {})
        prev_daily = snap.get("prevDailyBar", {})
        daily_bar = snap.get("dailyBar", {})

        price = latest_trade.get("p", 0)
        prev_close = prev_daily.get("c", 0) if prev_daily else 0
        change_pct = ((price - prev_close) / prev_close * 100) if prev_close > 0 else 0

        existing = db.query(Fund).filter(Fund.ticker == symbol).first()

        results.append({
            "symbol": symbol,
            "price": price,
            "change_pct": round(change_pct, 2),
            "daily_volume": daily_bar.get("v", 0),
            "existing_fund_id": existing.id if existing else None,
        })

    meta = STRATEGY_META[strategy]

    return FundListResponse(
        success=True,
        data={
            "strategy": strategy,
            "meta": meta,
            "assets": results,
        },
        error=None,
    )


@router.post("/seed")
def seed_funds_from_alpaca(
    strategy: str = Query(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_claim(AppConstants.CLAIMS["createFunds"])),
):
    if strategy not in STRATEGY_QUERIES:
        raise HTTPException(status_code=400, detail="Invalid strategy")

    manager = db.query(Manager).filter(Manager.email == current_user.email).first()
    if not manager:
        raise HTTPException(status_code=404, detail="Manager profile not found")

    symbols = STRATEGY_QUERIES[strategy]
    snapshots = get_snapshots(symbols)

    seeded = []
    for symbol in symbols:
        existing = db.query(Fund).filter(Fund.ticker == symbol).first()
        if existing:
            continue

        snap = snapshots.get(symbol, {})
        latest_trade = snap.get("latestTrade", {})
        prev_daily = snap.get("prevDailyBar", {})
        price = latest_trade.get("p", 0)
        prev_close = prev_daily.get("c", 0) if prev_daily else 0
        change_pct = round(((price - prev_close) / prev_close * 100), 2) if prev_close > 0 else 0

        asset_class = "stock"
        fund_type = "etf"
        if symbol in ("BND", "AGG", "TLT", "VGSH", "SHY", "IEF", "LQD", "VCSH", "SCHR", "GOVT", "BLV", "VTEB", "MUB"):
            asset_class = "bond"
            fund_type = "bond"

        meta = STRATEGY_META.get(strategy, {})

        fund = Fund(
            name=f"{symbol} Fund",
            ticker=symbol,
            description=f"{meta.get('label', strategy)} strategy fund tracking {symbol}",
            fund_type=fund_type,
            strategy=strategy,
            asset_class=asset_class,
            risk_level=meta.get("risk_level", "medium"),
            current_price=price,
            change_pct=change_pct,
            creator_manager_id=manager.id,
            is_active=False,
            review_status="pending_ops_review",
            submitted_at=datetime.now(timezone.utc),
        )
        db.add(fund)
        seeded.append(symbol)

    db.commit()

    return {"seeded": seeded, "count": len(seeded)}


@router.get("/stock/{symbol}")
def get_stock_details(
    symbol: str,
    current_user=Depends(get_current_user),
):
    symbol = symbol.upper().strip()
    asset = get_asset(symbol)
    snaps = get_snapshots([symbol])
    snap = snaps.get(symbol, {})

    latest_trade = snap.get("latestTrade", {})
    prev_daily = snap.get("prevDailyBar", {})
    daily_bar = snap.get("dailyBar", {})
    price = latest_trade.get("p", 0)
    prev_close = prev_daily.get("c", 0) if prev_daily else 0
    change_pct = round(((price - prev_close) / prev_close * 100), 2) if prev_close > 0 else 0

    bars_data = get_bars(symbol, timeframe="1Day", limit=90)
    if bars_data is None:
        bars_data = []

    bars = []
    for b in bars_data:
        bars.append({
            "t": b.get("t", ""),
            "o": b.get("o", 0),
            "h": b.get("h", 0),
            "l": b.get("l", 0),
            "c": b.get("c", 0),
            "v": b.get("v", 0),
        })

    if not bars:
        import random
        diff = price * (abs(change_pct) / 100) if change_pct != 0 else price * 0.02
        direction = 1 if change_pct >= 0 else -1
        base = price - (diff * direction)
        random.seed(symbol)
        for i in range(90):
            d = i + 1
            change = diff * (d / 90) * direction
            noise = random.uniform(-diff * 0.3, diff * 0.3)
            p = base + change + noise
            bars.append({
                "t": f"Day {d}",
                "o": round(p - random.uniform(-noise, noise), 2),
                "h": round(p + abs(noise) * 1.5, 2),
                "l": round(p - abs(noise) * 1.5, 2),
                "c": round(p, 2),
                "v": int(random.uniform(1000, 50000)),
            })

    return {
        "success": True,
        "data": {
            "symbol": symbol,
            "name": asset.get("name", symbol),
            "asset_class": asset.get("asset_class", ""),
            "exchange": asset.get("exchange", ""),
            "price": price,
            "change_pct": change_pct,
            "change_amt": round(price - prev_close, 2) if prev_close else 0,
            "daily_high": daily_bar.get("h", 0),
            "daily_low": daily_bar.get("l", 0),
            "daily_volume": daily_bar.get("v", 0),
            "daily_open": daily_bar.get("o", 0),
            "prev_close": prev_close,
            "bars": bars,
        },
        "error": None,
    }


@router.get("/positions")
def list_positions(
    current_user=Depends(require_claim(AppConstants.CLAIMS["readOwnPortfolio"])),
    db: Session = Depends(get_db),
):
    investor = db.query(Investor).filter(Investor.email == current_user.email).first()
    if not investor:
        raise HTTPException(status_code=404, detail="Investor not found")

    positions = get_positions()

    enriched = []
    for pos in positions:
        symbol = pos.get("symbol", "")
        fund = db.query(Fund).filter(Fund.ticker == symbol).first()
        enriched.append({
            "symbol": symbol,
            "qty": pos.get("qty", "0"),
            "avg_entry_price": pos.get("avg_entry_price", "0"),
            "current_price": pos.get("current_price", "0"),
            "market_value": pos.get("market_value", "0"),
            "unrealized_pl": pos.get("unrealized_pl", "0"),
            "unrealized_plpc": pos.get("unrealized_plpc", "0"),
            "side": pos.get("side", "long"),
            "fund_name": fund.name if fund else symbol,
            "fund_id": fund.id if fund else None,
            "strategy": fund.strategy if fund else None,
        })

    fund_investments = (
        db.query(FundInvestment)
        .filter(FundInvestment.investor_id == investor.id)
        .order_by(FundInvestment.invested_at.desc())
        .all()
    )
    fi_list = []
    for fi in fund_investments:
        fund = db.query(Fund).filter(Fund.id == fi.fund_id).first()
        fi_list.append({
            "id": fi.id,
            "fund_id": fi.fund_id,
            "fund_name": fund.name if fund else f"Fund #{fi.fund_id}",
            "fund_type": fund.fund_type if fund else "unknown",
            "amount": float(fi.amount),
            "status": fi.status,
            "invested_at": fi.invested_at.isoformat() if fi.invested_at else None,
        })

    return {"success": True, "data": {"positions": enriched, "fund_investments": fi_list}, "error": None}


@router.get("/orders")
def list_orders(
    current_user=Depends(require_claim(AppConstants.CLAIMS["readOwnPortfolio"])),
):
    orders = get_orders(limit=30)

    enriched = []
    for o in orders:
        enriched.append({
            "id": o.get("id"),
            "symbol": o.get("symbol"),
            "side": o.get("side"),
            "type": o.get("type"),
            "notional": o.get("notional"),
            "filled_avg_price": o.get("filled_avg_price"),
            "filled_qty": o.get("filled_qty"),
            "status": o.get("status"),
            "submitted_at": o.get("submitted_at"),
            "filled_at": o.get("filled_at"),
        })

    return {"success": True, "data": {"orders": enriched}, "error": None}


@router.get("/portfolio")
def get_portfolio(
    current_user=Depends(require_claim(AppConstants.CLAIMS["readOwnPortfolio"])),
):
    from services.alpaca_service import get_account as alpaca_get_account

    account_info = alpaca_get_account()
    positions = get_positions()

    total_market_value = sum(float(p.get("market_value", 0)) for p in positions)
    total_unrealized_pl = sum(float(p.get("unrealized_pl", 0)) for p in positions)

    return {
        "success": True,
        "data": {
            "account_id": account_info.get("id"),
            "status": account_info.get("status"),
            "cash": account_info.get("cash"),
            "portfolio_value": account_info.get("portfolio_value"),
            "buying_power": account_info.get("buying_power"),
            "equity": account_info.get("equity"),
            "positions_count": len(positions),
            "total_market_value": total_market_value,
            "total_unrealized_pl": total_unrealized_pl,
        },
        "error": None,
    }


@router.get("/{fund_id}")
def get_fund(fund_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    fund = db.query(Fund).filter(Fund.id == fund_id).first()
    if not fund:
        raise HTTPException(status_code=404, detail="Fund not found")
    if not fund.is_active or fund.review_status != "approved":
        raise HTTPException(status_code=400, detail="Fund is not approved for investment")

    if current_user.role and current_user.role.name == "investor":
        investor = db.query(Investor).filter(Investor.email == current_user.email).first()
        if investor:
            targeting = db.query(FundTargeting).filter(
                FundTargeting.investor_id == investor.id,
                FundTargeting.fund_id == fund_id,
                FundTargeting.is_visible == True
            ).first()
            if not targeting:
                raise HTTPException(status_code=404, detail="Fund not found")

    live_data = {}
    if fund.ticker:
        snaps = get_snapshots([fund.ticker])
        snap = snaps.get(fund.ticker, {})
        if snap:
            latest_trade = snap.get("latestTrade", {})
            prev_daily = snap.get("prevDailyBar", {})
            daily_bar = snap.get("dailyBar", {})
            price = latest_trade.get("p", 0)
            prev_close = prev_daily.get("c", 0) if prev_daily else 0

            live_data = {
                "price": price,
                "change_pct": round(((price - prev_close) / prev_close * 100), 2) if prev_close > 0 else 0,
                "daily_high": daily_bar.get("h", 0),
                "daily_low": daily_bar.get("l", 0),
                "daily_volume": daily_bar.get("v", 0),
                "daily_open": daily_bar.get("o", 0),
            }

    fund_data = FundResponse.model_validate(fund).model_dump()
    if fund.created_by:
        fund_data["manager_name"] = fund.created_by.full_name
    fund_data["live"] = live_data

    return {"success": True, "data": fund_data, "error": None}


class UpdateFundRequest(BaseModel):
    is_active: bool | str | None = None
    is_featured: bool | str | None = None
    name: str | None = None
    description: str | None = None
    strategy: str | None = None
    risk_level: str | None = None


@router.put("/{fund_id}")
def update_fund(
    fund_id: int,
    request: UpdateFundRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_claim(AppConstants.CLAIMS["updateFunds"])),
):
    fund = db.query(Fund).filter(Fund.id == fund_id).first()
    if not fund:
        raise HTTPException(status_code=404, detail="Fund not found")
    if current_user.role and current_user.role.name == "manager":
        manager = db.query(Manager).filter(Manager.email == current_user.email).first()
        if not manager or fund.creator_manager_id != manager.id:
            raise HTTPException(status_code=404, detail="Fund not found")

    before = {
        "name": fund.name,
        "strategy": fund.strategy,
        "risk_level": fund.risk_level,
        "is_active": fund.is_active,
    }

    if request.is_active is not None:
        fund.is_active = bool(request.is_active)
    if request.is_featured is not None:
        fund.is_featured = bool(request.is_featured)
    if request.name is not None:
        fund.name = request.name
    if request.description is not None:
        fund.description = request.description
    if request.strategy is not None:
        fund.strategy = request.strategy
    if request.risk_level is not None:
        fund.risk_level = request.risk_level

    if current_user.role and current_user.role.name == "manager":
        fund.review_status = "pending_ops_review"
        fund.submitted_at = datetime.now(timezone.utc)
        fund.reviewed_at = None
        fund.reviewed_by_user_id = None
        fund.review_notes = None
        fund.is_active = False

    db.commit()
    db.refresh(fund)

    after = {
        "name": fund.name,
        "strategy": fund.strategy,
        "risk_level": fund.risk_level,
        "is_active": fund.is_active,
    }

    log_event(
        db=db,
        user_id=current_user.id,
        action=AUDIT_ACTIONS["FUND_UPDATED"],
        details=f"Fund '{fund.name}' updated",
        entity_type="fund",
        entity_id=fund.id,
        changes={"before": before, "after": after},
        status="success",
    )

    return {"success": True, "data": {"id": fund.id, "name": fund.name, "ticker": fund.ticker, "is_active": fund.is_active}, "error": None}


@router.post("/invest", response_model=InvestResponse)
def invest_fund(
    request: InvestRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_claim(AppConstants.CLAIMS["readFunds"])),
):
    fund = db.query(Fund).filter(Fund.id == request.fund_id).first()
    if not fund:
        raise HTTPException(status_code=404, detail="Fund not found")
    if not fund.is_active or fund.review_status != "approved":
        raise HTTPException(status_code=400, detail="Fund is not approved for investment")

    investor = db.query(Investor).filter(Investor.email == current_user.email).first()
    if not investor:
        raise HTTPException(status_code=404, detail="Investor profile not found")

    if current_user.role and current_user.role.name == "investor":
        targeting = db.query(FundTargeting).filter(
            FundTargeting.investor_id == investor.id,
            FundTargeting.fund_id == request.fund_id,
            FundTargeting.is_visible == True
        ).first()
        if not targeting:
            raise HTTPException(status_code=404, detail="Fund not found")

    account = (
        db.query(InvestmentAccount)
        .filter(
            InvestmentAccount.id == request.investment_account_id,
            InvestmentAccount.investor_id == investor.id,
            InvestmentAccount.deleted_at.is_(None),
        )
        .with_for_update()
        .first()
    )
    if not account:
        raise HTTPException(status_code=404, detail="Investment account not found")

    from sqlalchemy.orm.attributes import flag_modified

    invest_status = "pending_ops_team"
    flow_status = "pending_ops_team"

    mfb = dict(account.manager_fund_balance or {})
    unallocated = float(mfb.get("_unallocated", 0))
    if unallocated < request.amount:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient available balance. Available: ${unallocated:,.2f}, requested: ${request.amount:,.2f}. "
                   f"Please top up your account first.",
        )

    mfb["_unallocated"] = unallocated - request.amount
    account.manager_fund_balance = mfb
    flag_modified(account, "manager_fund_balance")

    investment = FundInvestment(
        investor_id=investor.id,
        fund_id=fund.id,
        amount=request.amount,
        status=invest_status,
    )
    db.add(investment)

    flow = FundFlow(
        investor_id=investor.id,
        investment_account_id=account.id,
        flow_type="investment",
        amount=request.amount,
        status=flow_status,
        request_id=f"fund_invest_{fund.id}_{investor.id}_{int(request.amount)}_{uuid.uuid4().hex[:8]}",
    )
    db.add(flow)

    db.commit()
    db.refresh(investment)

    log_event(
        db=db,
        user_id=current_user.id,
        action=AUDIT_ACTIONS["FUND_INVESTED"],
        details=f"Investor {investor.email} invested ${request.amount:,.2f} in {fund.name}",
        entity_type="fund_investment",
        entity_id=investment.id,
        changes={"fund_id": fund.id, "fund_name": fund.name, "amount": request.amount, "investor_id": investor.id},
        status="success",
    )

    is_managed = fund.fund_type == "managed"

    return InvestResponse(
        success=True,
        data={
            "investment_id": investment.id,
            "fund_id": fund.id,
            "fund_name": fund.name,
            "amount": request.amount,
            "status": invest_status,
            "message": f"${request.amount:,.2f} allocated to {fund.name}. Your fund manager will invest this for you." if is_managed else f"${request.amount:,.2f} investment request for {fund.name} submitted. Your fund manager will review and execute.",
        },
        error=None,
    )


@router.post("/deposit")
def request_fund_deposit(
    fund_id: int = Query(...),
    amount: float = Query(..., gt=0),
    investment_account_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_claim(AppConstants.CLAIMS["depositToFunds"])),
):
    fund = db.query(Fund).filter(
        Fund.id == fund_id,
        Fund.is_active == True,
        Fund.review_status == "approved",
    ).first()
    if not fund:
        raise HTTPException(status_code=404, detail="Fund not found or not approved")
    fund_name = fund.name

    investor = db.query(Investor).filter(Investor.email == current_user.email).first()
    if not investor:
        raise HTTPException(status_code=404, detail="Investor profile not found")

    account = (
        db.query(InvestmentAccount)
        .filter(
            InvestmentAccount.id == investment_account_id,
            InvestmentAccount.investor_id == investor.id,
            InvestmentAccount.deleted_at.is_(None),
        )
        .with_for_update()
        .first()
    )
    if not account:
        raise HTTPException(status_code=404, detail="Investment account not found")

    targeting = db.query(FundTargeting).filter(
        FundTargeting.investor_id == investor.id,
        FundTargeting.fund_id == fund_id,
        FundTargeting.is_visible == True,
    ).first()
    if not targeting:
        raise HTTPException(status_code=404, detail="Fund is not available to this investor")

    request_id = f"REQ-DEP-{uuid.uuid4().hex[:12].upper()}"

    note = f"Deposit to fund: {fund_name}"

    flow = FundFlow(
        investor_id=investor.id,
        investment_account_id=account.id,
        fund_id=fund.id,
        flow_type="deposit",
        amount=amount,
        status="pending_ops_team",
        request_id=request_id,
        notes=note,
    )
    db.add(flow)
    db.commit()
    db.refresh(flow)

    log_event(
        db=db,
        user_id=current_user.id,
        action=AUDIT_ACTIONS["FUND_FLOW_DEPOSIT_REQUESTED"],
        details=f"Deposit request ${amount:,.2f} into {fund_name} by {current_user.email}",
        entity_type="fund_flow",
        entity_id=flow.id,
        changes={"fund_id": fund_id, "fund_name": fund_name, "amount": amount, "status": "pending_ops_team"},
        status="success",
    )

    return {
        "success": True,
        "data": {
            "id": flow.id,
            "request_id": request_id,
            "fund_id": fund_id,
            "fund_name": fund_name,
            "amount": float(flow.amount),
            "status": flow.status,
            "message": f"Deposit request for ${amount:,.2f} into {fund_name} submitted. Operations team will review.",
        },
        "error": None,
    }


@router.post("/withdraw")
def request_fund_withdrawal(
    fund_id: int = Query(...),
    amount: float = Query(..., gt=0),
    investment_account_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_claim(AppConstants.CLAIMS["withdrawFromFunds"])),
):
    fund = db.query(Fund).filter(
        Fund.id == fund_id,
        Fund.is_active == True,
        Fund.review_status == "approved",
    ).first()
    if not fund:
        raise HTTPException(status_code=404, detail="Fund not found or not approved")
    fund_name = fund.name

    investor = db.query(Investor).filter(Investor.email == current_user.email).first()
    if not investor:
        raise HTTPException(status_code=404, detail="Investor profile not found")

    account = (
        db.query(InvestmentAccount)
        .filter(
            InvestmentAccount.id == investment_account_id,
            InvestmentAccount.investor_id == investor.id,
            InvestmentAccount.deleted_at.is_(None),
        )
        .with_for_update()
        .first()
    )
    if not account:
        raise HTTPException(status_code=404, detail="Investment account not found")

    targeting = db.query(FundTargeting).filter(
        FundTargeting.investor_id == investor.id,
        FundTargeting.fund_id == fund_id,
        FundTargeting.is_visible == True,
    ).first()
    if not targeting:
        raise HTTPException(status_code=404, detail="Fund is not available to this investor")

    mfb = dict(account.manager_fund_balance or {})
    available = float(mfb.get(str(fund_id), 0))
    outstanding = db.query(FundFlow).filter(
        FundFlow.investment_account_id == account.id,
        FundFlow.fund_id == fund_id,
        FundFlow.flow_type == "withdrawal",
        FundFlow.status.in_(["pending_ops_team", "awaiting_payout_setup", "pending_fund_transfer"]),
    ).all()
    reserved = sum(float(flow.amount) for flow in outstanding)
    if available - reserved < amount:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient available fund balance. Available: ${max(0, available - reserved):,.2f}, requested: ${amount:,.2f}",
        )

    request_id = f"REQ-WTH-{uuid.uuid4().hex[:12].upper()}"

    note = f"Withdrawal from fund: {fund_name}"

    flow = FundFlow(
        investor_id=investor.id,
        investment_account_id=account.id,
        fund_id=fund.id,
        flow_type="withdrawal",
        amount=amount,
        status="pending_ops_team",
        request_id=request_id,
        notes=note,
    )
    db.add(flow)
    db.commit()
    db.refresh(flow)

    log_event(
        db=db,
        user_id=current_user.id,
        action=AUDIT_ACTIONS["FUND_FLOW_WITHDRAWAL_REQUESTED"],
        details=f"Withdrawal request ${amount:,.2f} from {fund_name} by {current_user.email}",
        entity_type="fund_flow",
        entity_id=flow.id,
        changes={"fund_id": fund_id, "fund_name": fund_name, "amount": amount, "status": "pending_ops_team"},
        status="success",
    )

    return {
        "success": True,
        "data": {
            "id": flow.id,
            "request_id": request_id,
            "fund_id": fund_id,
            "fund_name": fund_name,
            "amount": float(flow.amount),
            "status": flow.status,
            "message": f"Withdrawal request for ${amount:,.2f} from {fund_name} submitted. Operations team will review.",
        },
        "error": None,
    }
