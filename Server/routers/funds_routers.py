import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_

from database import get_db
from models import Fund, FundInvestment, Investor, InvestmentAccount, FundFlow, FundPosition, FundTargeting, Manager
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
from services.fund_accounting_service import current_nav_per_unit
from services.paynow_demo_service import build_paynow_demo_payload, paynow_qr_data_url
from config import settings
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
    investor = None

    if current_user.role and current_user.role.name == "investor":
        # Investors subscribe to fund products. Individual stocks are
        # underlying instruments managed by portfolio managers, not products
        # that an investor can trade directly from the client portal.
        query = query.filter(Fund.fund_type.in_(["etf", "bond", "managed", "mutual_fund", "hedge_fund"]))
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

    risk_by_fund = {}
    if investor:
        risk_by_fund = {
            row.fund_id: row.risk_tolerance
            for row in db.query(FundTargeting).filter(FundTargeting.investor_id == investor.id).all()
        }
    fund_list = []
    for f in funds:
        fd = FundResponse.model_validate(f).model_dump()
        if f.created_by:
            fd["manager_name"] = f.created_by.full_name
        if f.ticker and f.ticker in live_prices:
            fd["current_price"] = live_prices[f.ticker]["price"]
            fd["change_pct"] = live_prices[f.ticker]["change_pct"]
        fd["investor_risk_tolerance"] = risk_by_fund.get(f.id, "balanced")
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

    # Alpaca is a shared paper-trading account, not an investor-level book of
    # record. Do not expose its global positions as though they belonged to the
    # signed-in investor. The FundInv records below are investor scoped.
    enriched = []

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


class RiskToleranceRequest(BaseModel):
    risk_tolerance: str


@router.put("/{fund_id}/risk-tolerance")
def update_risk_tolerance(
    fund_id: int,
    request: RiskToleranceRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_claim(AppConstants.CLAIMS["readFunds"])),
):
    allowed = {"conservative", "balanced", "growth", "aggressive"}
    if request.risk_tolerance not in allowed:
        raise HTTPException(status_code=400, detail=f"Risk tolerance must be one of: {', '.join(sorted(allowed))}")
    investor = db.query(Investor).filter(Investor.email == current_user.email).first()
    if not investor:
        raise HTTPException(status_code=404, detail="Investor profile not found")
    targeting = db.query(FundTargeting).filter(
        FundTargeting.investor_id == investor.id,
        FundTargeting.fund_id == fund_id,
        FundTargeting.is_visible.is_(True),
    ).with_for_update().first()
    if not targeting:
        raise HTTPException(status_code=404, detail="Fund is not available to this investor")
    targeting.risk_tolerance = request.risk_tolerance
    log_event(
        db=db, user_id=current_user.id, action="fund.risk_tolerance.updated",
        details=f"Risk tolerance set to {request.risk_tolerance}", entity_type="fund_targeting",
        entity_id=targeting.id, changes={"fund_id": fund_id, "risk_tolerance": request.risk_tolerance},
        status="success", commit=False,
    )
    db.commit()
    return {"success": True, "data": {"fund_id": fund_id, "risk_tolerance": targeting.risk_tolerance}, "error": None}


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


def _create_subscription_request(
    *, db: Session, current_user, fund_id: int, amount: float, investment_account_id: int
) -> FundFlow:
    """Create the single authoritative investor subscription workflow."""
    fund = db.query(Fund).filter(
        Fund.id == fund_id,
        Fund.is_active == True,
        Fund.review_status == "approved",
        Fund.fund_type.in_(["etf", "bond", "managed", "mutual_fund", "hedge_fund"]),
    ).first()
    if not fund:
        raise HTTPException(status_code=404, detail="Fund product not found or not approved")

    investor = db.query(Investor).filter(Investor.email == current_user.email).first()
    if not investor:
        raise HTTPException(status_code=404, detail="Investor profile not found")
    account = db.query(InvestmentAccount).filter(
        InvestmentAccount.id == investment_account_id,
        InvestmentAccount.investor_id == investor.id,
        InvestmentAccount.deleted_at.is_(None),
    ).with_for_update().first()
    if not account:
        raise HTTPException(status_code=404, detail="Investment account not found")
    targeting = db.query(FundTargeting).filter(
        FundTargeting.investor_id == investor.id,
        FundTargeting.fund_id == fund.id,
        FundTargeting.is_visible == True,
    ).first()
    if not targeting:
        raise HTTPException(status_code=404, detail="Fund is not available to this investor")

    requested_amount = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if requested_amount <= 0:
        raise HTTPException(status_code=400, detail="Subscription amount must be greater than zero")
    if requested_amount > Decimal(str(settings.MAX_SUBSCRIPTION_AMOUNT)):
        raise HTTPException(
            status_code=400,
            detail=f"Subscription amount cannot exceed ${settings.MAX_SUBSCRIPTION_AMOUNT:,.2f}",
        )

    provider_mode = settings.FUND_FLOW_PROVIDER.strip().lower()
    if provider_mode not in {"paynow_demo", "manual", "stripe"}:
        raise HTTPException(
            status_code=500,
            detail="FUND_FLOW_PROVIDER must be 'paynow_demo', 'manual', or 'stripe'",
        )

    request_id = f"REQ-DEP-{uuid.uuid4().hex[:12].upper()}"
    payment_payload = None
    initial_status = "pending_ops_team"
    provider = None
    provider_reference = None
    if provider_mode == "paynow_demo":
        initial_status = "awaiting_investor_payment"
        provider = "paynow_demo"
        provider_reference = f"PAYNOW-DEMO-{request_id}"
        payment_payload = build_paynow_demo_payload(
            request_id=request_id,
            amount=requested_amount,
            currency=account.currency,
            fund_name=fund.name,
            recipient_name=settings.PAYNOW_DEMO_RECIPIENT_NAME,
            recipient_uen=settings.PAYNOW_DEMO_UEN,
        )

    flow = FundFlow(
        investor_id=investor.id,
        investment_account_id=account.id,
        fund_id=fund.id,
        flow_type="deposit",
        amount=requested_amount,
        currency=account.currency,
        status=initial_status,
        request_id=request_id,
        notes=f"Subscription to fund: {fund.name}",
        provider=provider,
        provider_reference=provider_reference,
        payment_url=payment_payload,
    )
    db.add(flow)
    db.commit()
    db.refresh(flow)
    log_event(
        db=db,
        user_id=current_user.id,
        action=AUDIT_ACTIONS["FUND_FLOW_DEPOSIT_REQUESTED"],
        details=f"Subscription request ${requested_amount:,.2f} into {fund.name} by {current_user.email}",
        entity_type="fund_flow",
        entity_id=flow.id,
        changes={"fund_id": fund.id, "fund_name": fund.name, "amount": float(requested_amount), "status": flow.status, "provider": provider},
        status="success",
    )
    return flow


def _subscription_response_data(flow: FundFlow) -> dict:
    data = {
        "id": flow.id,
        "request_id": flow.request_id,
        "fund_id": flow.fund_id,
        "fund_name": flow.fund.name,
        "amount": float(flow.amount),
        "currency": flow.currency,
        "status": flow.status,
        "provider": flow.provider,
        "payment_payload": flow.payment_url if flow.provider == "paynow_demo" else None,
        "paynow_qr_data_url": (
            paynow_qr_data_url(flow.payment_url)
            if flow.provider == "paynow_demo" and flow.payment_url else None
        ),
    }
    return data


@router.post("/invest", response_model=InvestResponse)
def invest_fund(
    request: InvestRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_claim(AppConstants.CLAIMS["depositToFunds"])),
):
    """Compatibility alias: investing in a fund is a subscription request."""
    flow = _create_subscription_request(
        db=db,
        current_user=current_user,
        fund_id=request.fund_id,
        amount=request.amount,
        investment_account_id=request.investment_account_id,
    )
    data = _subscription_response_data(flow)
    data["investment_id"] = flow.id
    data["message"] = (
        "Scan the fixed-amount demo PayNow QR and confirm the simulated payment. "
        "Units are issued only after Operations verifies the matching receipt."
        if flow.provider == "paynow_demo"
        else "Subscription submitted. Operations must approve it and verify receipt before units are issued."
    )
    return InvestResponse(success=True, data=data, error=None)


@router.post("/deposit")
def request_fund_deposit(
    fund_id: int = Query(...),
    amount: float = Query(..., gt=0),
    investment_account_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_claim(AppConstants.CLAIMS["depositToFunds"])),
):
    flow = _create_subscription_request(
        db=db, current_user=current_user, fund_id=fund_id,
        amount=amount, investment_account_id=investment_account_id,
    )

    data = _subscription_response_data(flow)
    data["message"] = (
        f"Demo PayNow QR created for ${float(flow.amount):,.2f}. The QR amount is fixed and cannot be edited."
        if flow.provider == "paynow_demo"
        else f"Subscription request for ${float(flow.amount):,.2f} into {flow.fund.name} submitted. Operations will review and verify receipt before issuing units."
    )
    return {
        "success": True,
        "data": data,
        "error": None,
    }


@router.post("/fund-flows/{flow_id}/simulate-paynow")
def simulate_paynow_payment(
    flow_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_claim(AppConstants.CLAIMS["depositToFunds"])),
):
    """Simulate a provider callback; the browser cannot supply or alter the paid amount."""
    investor = db.query(Investor).filter(Investor.email == current_user.email).first()
    if not investor:
        raise HTTPException(status_code=404, detail="Investor profile not found")
    flow = db.query(FundFlow).filter(
        FundFlow.id == flow_id,
        FundFlow.investor_id == investor.id,
        FundFlow.flow_type == "deposit",
    ).with_for_update().first()
    if not flow:
        raise HTTPException(status_code=404, detail="Subscription request not found")
    if flow.provider != "paynow_demo":
        raise HTTPException(status_code=400, detail="This subscription does not use demo PayNow")
    if flow.paid_amount is not None:
        return {
            "success": True,
            "data": {
                "id": flow.id,
                "status": flow.status,
                "requested_amount": float(flow.amount),
                "paid_amount": float(flow.paid_amount),
                "payment_received_at": flow.payment_received_at.isoformat() if flow.payment_received_at else None,
                "message": "Demo payment was already recorded.",
            },
            "error": None,
        }
    if flow.status != "awaiting_investor_payment":
        raise HTTPException(status_code=409, detail=f"Cannot pay a subscription with status '{flow.status}'")

    # The provider callback copies the immutable requested amount. There is no
    # client-controlled amount field, preventing accidental over/underpayment.
    flow.paid_amount = flow.amount
    flow.payment_received_at = datetime.now(timezone.utc)
    flow.status = "pending_ops_team"
    log_event(
        db=db,
        user_id=current_user.id,
        action=AUDIT_ACTIONS["FUND_FLOW_PAYNOW_PAYMENT_RECORDED"],
        details=f"Demo PayNow receipt ${float(flow.paid_amount):,.2f} recorded for {flow.request_id}",
        entity_type="fund_flow",
        entity_id=flow.id,
        changes={
            "requested_amount": float(flow.amount),
            "paid_amount": float(flow.paid_amount),
            "status": flow.status,
            "provider_reference": flow.provider_reference,
        },
        status="success",
        commit=False,
    )
    db.commit()
    db.refresh(flow)
    return {
        "success": True,
        "data": {
            "id": flow.id,
            "status": flow.status,
            "requested_amount": float(flow.amount),
            "paid_amount": float(flow.paid_amount),
            "payment_received_at": flow.payment_received_at.isoformat(),
            "message": "Demo PayNow payment recorded. Operations can now verify and complete the subscription.",
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

    position = db.query(FundPosition).filter(
        FundPosition.investment_account_id == account.id,
        FundPosition.fund_id == fund_id,
    ).with_for_update().first()
    available = (
        float(position.units) * float(current_nav_per_unit(db, fund))
        if position else 0.0
    )
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
        currency=account.currency,
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
