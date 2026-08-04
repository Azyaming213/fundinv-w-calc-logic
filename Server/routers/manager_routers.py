import csv
from io import StringIO
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from database import get_db
from models import User, Investor, InvestmentAccount, Manager, Fund, FundPosition, FundValuation, Order, FundInvestment, FundTargeting, FundComponent
from schemas.auth_schema import StandardResponse
from dependencies import get_current_user, require_claim
from services.alpaca_service import place_order, get_order, get_positions, search_assets, get_snapshots
from services.audit_service import log_event, AUDIT_ACTIONS
from services.pnl_service import compute_fund_return
from services.order_accounting_service import apply_filled_order
from services.valuation_service import finalize_valuation, preview_valuation, suggest_daily_pnl
import appconstants as AppConstants

from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/manager", tags=["Manager"])


class WhatIfAllocation(BaseModel):
    fund_id: int
    weight_pct: float = Field(..., ge=0, le=100)


class WhatIfRequest(BaseModel):
    start_date: datetime
    end_date: datetime
    allocations: list[WhatIfAllocation]


class DailyValuationRequest(BaseModel):
    fund_id: int
    valuation_date: date
    daily_pnl: float
    notes: str | None = Field(default=None, max_length=1000)
    calculation_source: Literal["manager_entry", "market_data_suggestion"] = "manager_entry"


def _managed_funds(db: Session, manager: Manager) -> list[Fund]:
    return db.query(Fund).filter(Fund.creator_manager_id == manager.id).order_by(Fund.name).all()


def _managed_approved_fund(db: Session, manager: Manager, fund_id: int) -> Fund:
    fund = db.query(Fund).filter(
        Fund.id == fund_id,
        Fund.creator_manager_id == manager.id,
        Fund.fund_type != "stock",
        Fund.is_active == True,
        Fund.review_status == "approved",
    ).first()
    if not fund:
        raise HTTPException(status_code=404, detail="Active approved managed fund not found")
    return fund


def _enrich_allocations(db: Session, preview: dict) -> dict:
    investor_ids = {row["investor_id"] for row in preview["allocations"]}
    investors = {
        investor.id: investor
        for investor in db.query(Investor).filter(Investor.id.in_(investor_ids)).all()
    } if investor_ids else {}
    for row in preview["allocations"]:
        investor = investors.get(row["investor_id"])
        row["investor_name"] = investor.full_name if investor else "Unknown"
        row["investor_email"] = investor.email if investor else None
    return preview


@router.post("/valuations/preview", response_model=StandardResponse)
def preview_daily_valuation(
    request: DailyValuationRequest,
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["updateFunds"])),
    db: Session = Depends(get_db),
):
    manager = _get_manager(db, current_user.email)
    if manager is None:
        raise HTTPException(status_code=404, detail="Manager profile not found")
    fund = _managed_approved_fund(db, manager, request.fund_id)
    try:
        result = preview_valuation(db, fund, request.valuation_date, request.daily_pnl)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return StandardResponse(success=True, data=_enrich_allocations(db, result), error=None)


@router.get("/valuations/suggestion", response_model=StandardResponse)
def suggest_daily_valuation(
    fund_id: int = Query(..., gt=0),
    valuation_date: date = Query(...),
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["updateFunds"])),
    db: Session = Depends(get_db),
):
    manager = _get_manager(db, current_user.email)
    if manager is None:
        raise HTTPException(status_code=404, detail="Manager profile not found")
    fund = _managed_approved_fund(db, manager, fund_id)
    try:
        result = suggest_daily_pnl(db, fund, valuation_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return StandardResponse(success=True, data=result, error=None)


@router.post("/valuations/finalize", response_model=StandardResponse)
def finalize_daily_valuation(
    request: DailyValuationRequest,
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["updateFunds"])),
    db: Session = Depends(get_db),
):
    manager = _get_manager(db, current_user.email)
    if manager is None:
        raise HTTPException(status_code=404, detail="Manager profile not found")
    fund = _managed_approved_fund(db, manager, request.fund_id)
    try:
        valuation, result = finalize_valuation(
            db,
            fund,
            request.valuation_date,
            request.daily_pnl,
            current_user.id,
            request.notes,
            request.calculation_source,
        )
        log_event(
            db=db,
            user_id=current_user.id,
            action=AUDIT_ACTIONS["FUND_VALUATION_FINALIZED"],
            details=f"Finalized {fund.name} valuation for {request.valuation_date}",
            entity_type="fund_valuation",
            entity_id=valuation.id,
            changes={
                "fund_id": fund.id,
                "valuation_date": request.valuation_date.isoformat(),
                "daily_pnl": result["daily_pnl"],
                "nav_per_unit": result["nav_per_unit"],
                "calculation_source": request.calculation_source,
            },
            status="success",
            commit=False,
        )
        db.commit()
        db.refresh(valuation)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    result = _enrich_allocations(db, result)
    result["valuation_id"] = valuation.id
    result["status"] = valuation.status
    result["source"] = valuation.source
    result["finalized_at"] = valuation.finalized_at.isoformat()
    return StandardResponse(success=True, data=result, error=None)


@router.get("/valuations", response_model=StandardResponse)
def list_manager_valuations(
    fund_id: int | None = Query(None),
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["readAssignedInvestors"])),
    db: Session = Depends(get_db),
):
    manager = _get_manager(db, current_user.email)
    if manager is None:
        raise HTTPException(status_code=404, detail="Manager profile not found")
    fund_ids = [fund.id for fund in _managed_funds(db, manager)]
    query = db.query(FundValuation).filter(FundValuation.fund_id.in_(fund_ids)) if fund_ids else db.query(FundValuation).filter(False)
    if fund_id is not None:
        if fund_id not in fund_ids:
            raise HTTPException(status_code=404, detail="Managed fund not found")
        query = query.filter(FundValuation.fund_id == fund_id)
    rows = query.order_by(FundValuation.valuation_date.desc()).limit(100).all()
    return StandardResponse(success=True, data={"valuations": [{
        "id": row.id,
        "fund_id": row.fund_id,
        "fund_name": row.fund.name,
        "valuation_date": row.valuation_date.isoformat(),
        "opening_assets": float(row.opening_assets),
        "daily_pnl": float(row.daily_pnl),
        "closing_assets_before_flows": float(row.closing_assets_before_flows),
        "net_flow": float(row.net_flow),
        "closing_assets": float(row.closing_assets),
        "units_outstanding": float(row.units_outstanding),
        "nav_per_unit": float(row.nav_per_unit),
        "status": row.status,
        "source": row.source,
        "finalized_by_name": row.finalized_by.full_name if row.finalized_by else "System",
        "finalized_at": row.finalized_at.isoformat() if row.finalized_at else None,
        "notes": row.notes,
    } for row in rows]}, error=None)


@router.get("/performance-analysis", response_model=StandardResponse)
def performance_analysis(
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["readAssignedInvestors"])),
    db: Session = Depends(get_db),
):
    manager = _get_manager(db, current_user.email)
    if manager is None:
        raise HTTPException(status_code=404, detail="Manager profile not found")
    end_date = end_date or datetime.now(timezone.utc)
    start_date = start_date or (end_date - timedelta(days=30))
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must not be after end_date")
    funds = _managed_funds(db, manager)
    fund_ids = [fund.id for fund in funds]
    values = {fund_id: 0.0 for fund_id in fund_ids}
    for position in db.query(FundPosition).filter(FundPosition.fund_id.in_(fund_ids)).all() if fund_ids else []:
        latest = db.query(FundValuation).filter(FundValuation.fund_id == position.fund_id).order_by(FundValuation.valuation_date.desc()).first()
        nav = float(latest.nav_per_unit) if latest else float(position.fund.current_price or 1)
        values[position.fund_id] += float(position.units) * nav
    total_value = sum(values.values())
    drivers = []
    for fund in funds:
        report = compute_fund_return(db, fund.id, start_date, end_date)
        weight = values[fund.id] / total_value * 100 if total_value else 0.0
        fund_return = float(report["fund_return_pct"])
        drivers.append({
            "fund_id": fund.id, "fund_name": fund.name, "ticker": fund.ticker,
            "market_value": values[fund.id], "weight_pct": weight,
            "return_pct": fund_return, "contribution_pct": weight * fund_return / 100,
        })
    return StandardResponse(success=True, data={
        "start_date": start_date.isoformat(), "end_date": end_date.isoformat(),
        "portfolio_value": total_value, "portfolio_return_pct": sum(row["contribution_pct"] for row in drivers),
        "drivers": drivers,
    }, error=None)


@router.post("/performance-analysis/what-if", response_model=StandardResponse)
def performance_what_if(
    request: WhatIfRequest,
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["readAssignedInvestors"])),
    db: Session = Depends(get_db),
):
    manager = _get_manager(db, current_user.email)
    if manager is None:
        raise HTTPException(status_code=404, detail="Manager profile not found")
    if request.start_date > request.end_date:
        raise HTTPException(status_code=400, detail="start_date must not be after end_date")
    total_weight = sum(item.weight_pct for item in request.allocations)
    if abs(total_weight - 100) > 0.01:
        raise HTTPException(status_code=400, detail="What-if allocation weights must total 100%")
    allowed = {fund.id: fund for fund in _managed_funds(db, manager)}
    if len({item.fund_id for item in request.allocations}) != len(request.allocations):
        raise HTTPException(status_code=400, detail="Each fund may appear only once")
    rows = []
    for item in request.allocations:
        fund = allowed.get(item.fund_id)
        if not fund:
            raise HTTPException(status_code=404, detail=f"Managed fund {item.fund_id} not found")
        report = compute_fund_return(db, fund.id, request.start_date, request.end_date)
        fund_return = float(report["fund_return_pct"])
        rows.append({
            "fund_id": fund.id, "fund_name": fund.name, "weight_pct": item.weight_pct,
            "return_pct": fund_return, "contribution_pct": item.weight_pct * fund_return / 100,
        })
    return StandardResponse(success=True, data={
        "start_date": request.start_date.isoformat(), "end_date": request.end_date.isoformat(),
        "hypothetical_return_pct": sum(row["contribution_pct"] for row in rows), "drivers": rows,
    }, error=None)


def _get_manager(db: Session, email: str) -> Manager | None:
    mgr = db.query(Manager).filter(Manager.email == email).first()
    if mgr is None:
        user = db.query(User).filter(User.email == email).first()
        if user and user.role and user.role.name == AppConstants.ROLES["MANAGER"]:
            mgr = Manager(email=email, full_name=user.full_name, is_active=True)
            db.add(mgr)
            db.commit()
            db.refresh(mgr)
    return mgr


@router.get("/investors", response_model=StandardResponse)
def list_managed_investors(
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["readAssignedInvestors"])),
    db: Session = Depends(get_db),
):
    manager = _get_manager(db, current_user.email)
    if manager is None:
        return StandardResponse(success=True, data={"investors": []}, error=None)

    investors = db.query(Investor).filter(Investor.manager_id == manager.id).all()

    investor_list = []
    for inv in investors:
        accounts = db.query(InvestmentAccount).filter(
            InvestmentAccount.investor_id == inv.id,
            InvestmentAccount.deleted_at.is_(None),
        ).all()
        total_mfb = sum(float(mfb_val) for a in accounts for mfb_val in (a.manager_fund_balance or {}).values())
        total_invested_stocks = sum(float(val) for a in accounts for val in (a.fund_allocations or {}).values())

        investor_list.append({
            "id": inv.id,
            "email": inv.email,
            "full_name": inv.full_name,
            "is_active": inv.is_active,
            "account_count": len(accounts),
            "total_in_funds": total_mfb,
            "total_in_stocks": total_invested_stocks,
            "onboarded_at": inv.onboarded_at.isoformat() if inv.onboarded_at else None,
        })

    return StandardResponse(success=True, data={"investors": investor_list, "manager_id": manager.id}, error=None)


@router.get("/investors/{investor_id}", response_model=StandardResponse)
def get_investor_detail(
    investor_id: int,
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["readAssignedInvestors"])),
    db: Session = Depends(get_db),
):
    manager = _get_manager(db, current_user.email)
    if manager is None:
        raise HTTPException(status_code=404, detail="Manager profile not found")

    investor = db.query(Investor).filter(
        Investor.id == investor_id, Investor.manager_id == manager.id
    ).first()
    if not investor:
        raise HTTPException(status_code=404, detail="Investor not found under your management")

    accounts = db.query(InvestmentAccount).filter(
        InvestmentAccount.investor_id == investor_id,
        InvestmentAccount.deleted_at.is_(None),
    ).all()

    account_list = []
    for a in accounts:
        account_list.append({
            "id": a.id,
            "account_name": a.account_name,
            "account_number": a.account_number,
            "manager_fund_balance": a.manager_fund_balance or {},
            "fund_allocations": a.fund_allocations or {},
            "investment_strategy": a.investment_strategy,
            "status": a.status,
        })

    orders = db.query(Order).filter(Order.investor_id == investor_id).order_by(Order.created_at.desc()).limit(20).all()
    order_list = []
    for o in orders:
        order_list.append({
            "id": o.id,
            "symbol": o.symbol,
            "side": o.side,
            "amount": float(o.amount),
            "status": o.status,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        })

    fund_investments = db.query(FundInvestment).filter(
        FundInvestment.investor_id == investor_id
    ).order_by(FundInvestment.invested_at.desc()).limit(20).all()
    fi_list = []
    for fi in fund_investments:
        fund = db.query(Fund).filter(Fund.id == fi.fund_id).first()
        fi_list.append({
            "id": fi.id,
            "fund_id": fi.fund_id,
            "fund_name": fund.name if fund else "Unknown",
            "amount": float(fi.amount),
            "status": fi.status,
            "invested_at": fi.invested_at.isoformat() if fi.invested_at else None,
        })

    return StandardResponse(success=True, data={
        "investor": {
            "id": investor.id,
            "email": investor.email,
            "full_name": investor.full_name,
            "is_active": investor.is_active,
        },
        "accounts": account_list,
        "orders": order_list,
        "fund_investments": fi_list,
    }, error=None)


@router.post("/investors/{investor_id}/trade", response_model=StandardResponse)
def manager_trade_for_investor(
    investor_id: int,
    symbol: str,
    side: str,
    amount: float = Query(..., gt=0),
    investment_account_id: int = Query(...),
    fund_id: int | None = None,
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["executeTrades"])),
    db: Session = Depends(get_db),
):
    manager = _get_manager(db, current_user.email)
    if manager is None:
        raise HTTPException(status_code=404, detail="Manager profile not found")

    investor = db.query(Investor).filter(
        Investor.id == investor_id, Investor.manager_id == manager.id
    ).first()
    if not investor:
        raise HTTPException(status_code=404, detail="Investor not found under your management")

    if side not in ("buy", "sell"):
        raise HTTPException(status_code=400, detail="Side must be 'buy' or 'sell'")
    if fund_id is None:
        raise HTTPException(status_code=400, detail="A managed fund is required for every underlying trade")
    fund = db.query(Fund).filter(
        Fund.id == fund_id,
        Fund.creator_manager_id == manager.id,
        Fund.is_active == True,
        Fund.review_status == "approved",
    ).first()
    if not fund:
        raise HTTPException(status_code=404, detail="Managed fund not found")

    account = db.query(InvestmentAccount).filter(
        InvestmentAccount.id == investment_account_id,
        InvestmentAccount.investor_id == investor_id,
        InvestmentAccount.deleted_at.is_(None),
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    if side == "buy":
        mfb = dict(account.manager_fund_balance or {})
        fund_value = float(mfb.get(str(fund_id), 0))
        allocs = dict(account.fund_allocations or {})
        allocated = sum(float(value) for value in allocs.values())
        available = max(0.0, fund_value - allocated)
        if available < amount:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient unallocated capital in {fund.name}. Available: ${available:,.2f}, requested: ${amount:,.2f}",
            )
    else:
        position = get_positions()
        pos_data = next((p for p in position if p.get("symbol") == symbol), None) if isinstance(position, list) else None
        market_value = float(pos_data.get("market_value", 0)) if pos_data else 0
        sell_amount = min(amount, market_value)
        if sell_amount <= 0:
            raise HTTPException(status_code=400, detail=f"No position to sell for {symbol}")

        amount = sell_amount

    alpaca_result = place_order(symbol=symbol, notional=amount, side=side)
    if alpaca_result.get("error"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Alpaca order failed: {alpaca_result.get('message', 'Unknown error')}",
        )

    external_id = alpaca_result.get("id")
    if not external_id:
        raise HTTPException(status_code=502, detail="Alpaca accepted no identifiable order")
    filled_qty = float(alpaca_result.get("filled_qty") or 0) or None
    filled_price = float(alpaca_result.get("filled_avg_price") or 0) or None
    order = Order(
        investor_id=investor_id,
        investment_account_id=account.id,
        fund_id=fund_id,
        alpaca_order_id=external_id,
        symbol=symbol,
        side=side,
        amount=amount,
        filled_qty=filled_qty,
        filled_price=filled_price,
        status=alpaca_result.get("status", "accepted"),
        performed_by_user_id=current_user.id,
    )
    db.add(order)
    # Persist the external order first. A later fill-accounting failure must
    # never create an untraceable order that exists only at Alpaca.
    db.commit()
    db.refresh(order)

    provider_order = alpaca_result
    if alpaca_result.get("status") != "filled":
        provider_order = get_order(external_id) or alpaca_result
    accounting_applied = False
    try:
        accounting_applied = apply_filled_order(db, order, provider_order)
        db.commit()
        db.refresh(order)
    except Exception:
        db.rollback()
        # The durable Order remains pending and the reconciliation worker will
        # retry. Return success because the external submission did succeed.

    log_event(
        db=db,
        user_id=current_user.id,
        action=AUDIT_ACTIONS["TRADE_EXECUTED"],
        details=f"Manager executed {side} {symbol} for {investor.email}",
        entity_type="order",
        entity_id=order.id,
        changes={
            "symbol": symbol,
            "side": side,
            "amount": amount,
            "fund_id": fund_id,
            "investor_id": investor_id,
            "alpaca_order_id": alpaca_result.get("id"),
        },
        status="success",
    )

    return StandardResponse(success=True, data={
        "order_id": order.id,
        "alpaca_order_id": alpaca_result.get("id"),
        "symbol": symbol,
        "side": side,
        "amount": amount,
        "status": order.status,
        "accounting_status": "recorded" if order.accounting_recorded_at else "pending_fill_reconciliation",
    }, error=None)


@router.get("/funds", response_model=StandardResponse)
def list_funds_for_assignment(
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["readFunds"])),
    db: Session = Depends(get_db),
):
    manager = _get_manager(db, current_user.email)
    if not manager:
        raise HTTPException(status_code=404, detail="Manager profile not found")
    funds = db.query(Fund).filter(Fund.creator_manager_id == manager.id).order_by(Fund.name).all()
    fund_list = []
    for f in funds:
        fund_list.append({
            "id": f.id,
            "name": f.name,
            "ticker": f.ticker,
            "description": f.description,
            "fund_type": f.fund_type,
            "strategy": f.strategy,
            "risk_level": f.risk_level,
            "current_price": float(f.current_price) if f.current_price else None,
            "is_active": f.is_active,
            "review_status": f.review_status,
            "creator_manager_id": f.creator_manager_id,
            "manager_name": f.created_by.full_name if f.created_by else None,
            "portfolio_composition": f.portfolio_composition or [],
        })
    return StandardResponse(success=True, data={"funds": fund_list}, error=None)


@router.get("/search-stocks", response_model=StandardResponse)
def search_stocks(
    q: str = Query("", min_length=1),
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["createFunds"])),
    db: Session = Depends(get_db),
):
    results = search_assets(query=q, limit=10)
    stocks = []
    for r in results:
        if r.get("tradable") and r.get("asset_class") in ("us_equity",):
            stocks.append({
                "symbol": r.get("symbol"),
                "name": r.get("name"),
                "asset_type": "stock",
            })
    term = f"%{q}%"
    existing_funds = db.query(Fund).filter(
        Fund.is_active == True,
        Fund.review_status == "approved",
        (Fund.name.ilike(term) | Fund.ticker.ilike(term)),
    ).limit(10).all()
    stocks.extend({
        "symbol": fund.ticker or f"FUND-{fund.id}",
        "name": fund.name,
        "asset_type": "fund",
        "fund_id": fund.id,
    } for fund in existing_funds if not any(item.get("symbol") == fund.ticker for item in stocks))
    return StandardResponse(success=True, data={"stocks": stocks}, error=None)


class CreateManagedFundRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="", max_length=1000)
    strategy: str = Field(default="balanced")
    risk_level: str = Field(default="medium")
    holdings: list[dict] = Field(default_factory=list)


class UpdateWeightsRequest(BaseModel):
    holdings: list[dict] = Field(default_factory=list)


@router.post("/funds", response_model=StandardResponse)
def create_managed_fund(
    request: CreateManagedFundRequest,
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["createFunds"])),
    db: Session = Depends(get_db),
):
    manager = _get_manager(db, current_user.email)
    if manager is None:
        raise HTTPException(status_code=404, detail="Manager profile not found")

    if request.strategy not in ("aggressive", "growth", "balanced", "conservative", "income"):
        raise HTTPException(status_code=400, detail="Invalid strategy")

    holdings = request.holdings
    total_allocation = sum(float(item.get("allocation", 0)) for item in holdings)
    if not holdings:
        raise HTTPException(status_code=400, detail="Add at least one stock, ETF, or fund to the portfolio")
    if abs(total_allocation - 100) > 0.01:
        raise HTTPException(status_code=400, detail="Portfolio allocations must total 100%")
    if any(float(item.get("allocation", 0)) <= 0 or not item.get("symbol") for item in holdings):
        raise HTTPException(status_code=400, detail="Each fund holding needs a symbol and positive allocation")
    if len({item["symbol"].upper() for item in holdings}) != len(holdings):
        raise HTTPException(status_code=400, detail="Fund holdings cannot contain duplicate symbols")

    fund = Fund(
        name=request.name,
        description=request.description,
        fund_type="managed",
        strategy=request.strategy,
        risk_level=request.risk_level,
        is_active=False,
        creator_manager_id=manager.id,
        review_status="pending_ops_review",
        submitted_at=datetime.now(timezone.utc),
        portfolio_composition=[
            {"symbol": item["symbol"].upper(), "name": item.get("name", item["symbol"]), "allocation": float(item["allocation"])}
            for item in holdings
        ],
    )
    try:
        db.add(fund)
        db.flush()

        for item in holdings:
            db.add(FundComponent(
                fund_id=fund.id,
                component_fund_id=item.get("fund_id"),
                symbol=item["symbol"].upper(),
                component_name=item.get("name", item["symbol"]),
                asset_type=item.get("asset_type", "stock"),
                target_pct=float(item["allocation"]),
            ))

        log_event(
            db=db,
            user_id=current_user.id,
            action=AUDIT_ACTIONS["FUND_CREATED"],
            details=f"Fund '{fund.name}' created by {current_user.email}",
            entity_type="fund",
            entity_id=fund.id,
            changes={"name": fund.name, "strategy": fund.strategy, "risk_level": fund.risk_level},
            status="success",
            commit=False,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(fund)

    return StandardResponse(success=True, data={
        "id": fund.id,
        "name": fund.name,
        "fund_type": fund.fund_type,
        "strategy": fund.strategy,
        "review_status": fund.review_status,
    }, error=None)


@router.put("/funds/{fund_id}/weights", response_model=StandardResponse)
def update_fund_weights(
    fund_id: int,
    request: UpdateWeightsRequest,
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["manageFundWeights"])),
    db: Session = Depends(get_db),
):
    manager = _get_manager(db, current_user.email)
    if manager is None:
        raise HTTPException(status_code=404, detail="Manager profile not found")

    fund = db.query(Fund).filter(Fund.id == fund_id, Fund.creator_manager_id == manager.id).first()
    if not fund:
        raise HTTPException(status_code=404, detail="Fund not found or not created by you")

    before = fund.portfolio_composition or []
    total_allocation = sum(float(item.get("allocation", 0)) for item in request.holdings)
    if not request.holdings or abs(total_allocation - 100) > 0.01:
        raise HTTPException(status_code=400, detail="Portfolio allocations must total 100%")
    if any(float(item.get("allocation", 0)) <= 0 or not item.get("symbol") for item in request.holdings):
        raise HTTPException(status_code=400, detail="Each fund holding needs a symbol and positive allocation")
    symbols = [item["symbol"].upper() for item in request.holdings]
    if len(set(symbols)) != len(symbols):
        raise HTTPException(status_code=400, detail="Fund holdings cannot contain duplicate symbols")

    fund.portfolio_composition = [
        {"symbol": symbol, "name": item.get("name", symbol), "allocation": float(item["allocation"])}
        for symbol, item in zip(symbols, request.holdings)
    ]
    db.query(FundComponent).filter(FundComponent.fund_id == fund.id).delete()
    for item in fund.portfolio_composition:
        db.add(FundComponent(
            fund_id=fund.id,
            component_fund_id=item.get("fund_id"),
            symbol=item["symbol"],
            component_name=item["name"],
            asset_type=item.get("asset_type", "stock"),
            target_pct=item["allocation"],
        ))
    if fund.review_status in ("approved", "rejected"):
        fund.review_status = "pending_ops_review"
        fund.submitted_at = datetime.now(timezone.utc)
        fund.review_notes = None
        fund.is_active = False
    db.commit()

    log_event(
        db=db,
        user_id=current_user.id,
        action=AUDIT_ACTIONS["FUND_UPDATED"],
        details=f"Fund weights updated for '{fund.name}'",
        entity_type="fund",
        entity_id=fund.id,
        changes={"before": before, "after": fund.portfolio_composition},
        status="success",
    )

    return StandardResponse(success=True, data={
        "fund_id": fund.id,
        "holdings": fund.portfolio_composition,
    }, error=None)


@router.post("/funds/{fund_id}/submit", response_model=StandardResponse)
def submit_fund_for_review(
    fund_id: int,
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["submitFundsForReview"])),
    db: Session = Depends(get_db),
):
    manager = _get_manager(db, current_user.email)
    fund = db.query(Fund).filter(Fund.id == fund_id, Fund.creator_manager_id == manager.id).first() if manager else None
    if not fund:
        raise HTTPException(status_code=404, detail="Fund not found")
    if not fund.portfolio_composition:
        raise HTTPException(status_code=400, detail="Add fund holdings before submitting for review")
    if fund.review_status == "approved":
        raise HTTPException(status_code=400, detail="Fund is already approved")
    fund.review_status = "pending_ops_review"
    fund.submitted_at = datetime.now(timezone.utc)
    fund.review_notes = None
    fund.is_active = False
    db.commit()
    log_event(db=db, user_id=current_user.id, action=AUDIT_ACTIONS["FUND_UPDATED"],
              details=f"Fund '{fund.name}' submitted for operations review", entity_type="fund",
              entity_id=fund.id, changes={"review_status": fund.review_status}, status="success")
    return StandardResponse(success=True, data={"fund_id": fund.id, "review_status": fund.review_status}, error=None)


@router.get("/funds/{fund_id}/investors", response_model=StandardResponse)
def get_fund_investors(
    fund_id: int,
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["readFunds"])),
    db: Session = Depends(get_db),
):
    manager = _get_manager(db, current_user.email)
    if manager is None:
        raise HTTPException(status_code=404, detail="Manager profile not found")

    fund = db.query(Fund).filter(Fund.id == fund_id, Fund.creator_manager_id == manager.id).first()
    if not fund:
        raise HTTPException(status_code=404, detail="Fund not found or not created by you")

    investments = (
        db.query(FundInvestment)
        .filter(FundInvestment.fund_id == fund_id, FundInvestment.status == "completed")
        .all()
    )

    inv_list = []
    for fi in investments:
        inv = fi.investor
        inv_list.append({
            "investor_id": inv.id,
            "full_name": inv.full_name,
            "email": inv.email,
            "amount": float(fi.amount),
            "status": fi.status,
            "invested_at": fi.invested_at.isoformat() if fi.invested_at else None,
        })

    total_invested = sum(float(fi.amount) for fi in investments)

    return StandardResponse(success=True, data={
        "fund_id": fund.id,
        "fund_name": fund.name,
        "investors": inv_list,
        "total_invested": total_invested,
        "investor_count": len(inv_list),
    }, error=None)


@router.post("/fund-assign", response_model=StandardResponse)
def assign_investor_to_fund(
    investor_id: int,
    fund_id: int,
    amount: float = 0,
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["manageFundTargeting"])),
    db: Session = Depends(get_db),
):
    manager = _get_manager(db, current_user.email)
    if manager is None:
        raise HTTPException(status_code=404, detail="Manager profile not found")

    investor = db.query(Investor).filter(Investor.id == investor_id, Investor.manager_id == manager.id).first()
    if not investor:
        raise HTTPException(status_code=404, detail="Investor not found under your management")

    fund = db.query(Fund).filter(Fund.id == fund_id).first()
    if not fund:
        raise HTTPException(status_code=404, detail="Fund not found")

    existing = db.query(FundTargeting).filter(
        FundTargeting.investor_id == investor_id,
        FundTargeting.fund_id == fund_id,
    ).first()

    if not existing:
        ft = FundTargeting(investor_id=investor_id, fund_id=fund_id, is_visible=True)
        db.add(ft)

    if amount > 0:
        from sqlalchemy.orm.attributes import flag_modified
        account = db.query(InvestmentAccount).filter(
            InvestmentAccount.investor_id == investor_id,
            InvestmentAccount.deleted_at.is_(None),
        ).first()
        if not account:
            raise HTTPException(status_code=404, detail="No active investment account found for this investor")

        mfb = dict(account.manager_fund_balance or {})
        unallocated = float(mfb.get("_unallocated", 0))
        if unallocated < amount:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient unallocated funds. Available: ${unallocated:,.2f}, requested: ${amount:,.2f}",
            )
        mfb["_unallocated"] = unallocated - amount
        mfb[str(fund_id)] = float(mfb.get(str(fund_id), 0)) + amount
        account.manager_fund_balance = mfb
        flag_modified(account, "manager_fund_balance")

        investment = FundInvestment(
            investor_id=investor_id,
            fund_id=fund_id,
            amount=amount,
            status="allocated",
        )
        db.add(investment)

    db.commit()

    log_event(
        db=db,
        user_id=current_user.id,
        action=AUDIT_ACTIONS["FUND_TARGETING_UPDATED"],
        details=f"Investor {investor.full_name} assigned to fund {fund.name}",
        entity_type="fund_targeting",
        entity_id=existing.id if existing else None,
        changes={"investor_id": investor_id, "fund_id": fund_id, "is_visible": True, "amount_invested": amount if amount > 0 else None},
        status="success",
    )

    return StandardResponse(success=True, data={
        "message": f"Investor {investor.full_name} assigned to fund {fund.name}",
        "investor_id": investor_id,
        "fund_id": fund_id,
        "amount_invested": amount if amount > 0 else None,
    }, error=None)


@router.get("/transactions", response_model=StandardResponse)
def manager_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query(""),
    side: str = Query(""),
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["readTransactions"])),
    db: Session = Depends(get_db),
):
    query = db.query(Order).filter(Order.performed_by_user_id == current_user.id)

    if search:
        term = f"%{search}%"
        query = query.filter(Order.symbol.ilike(term))
    if side:
        query = query.filter(Order.side == side)

    total = query.count()
    orders = query.options(joinedload(Order.investor)).order_by(Order.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    order_list = []
    for o in orders:
        inv = o.investor
        order_list.append({
            "id": o.id,
            "symbol": o.symbol,
            "side": o.side,
            "amount": float(o.amount),
            "filled_qty": float(o.filled_qty) if o.filled_qty else None,
            "filled_price": float(o.filled_price) if o.filled_price else None,
            "status": o.status,
            "investor_name": inv.full_name if inv else "Unknown",
            "investor_email": inv.email if inv else "Unknown",
            "created_at": o.created_at.isoformat() if o.created_at else None,
        })

    return StandardResponse(success=True, data={
        "orders": order_list,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }, error=None)


@router.get("/transactions/export", response_class=StreamingResponse)
def export_transactions_csv(
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["readTransactions"])),
    db: Session = Depends(get_db),
):
    orders = db.query(Order).options(joinedload(Order.investor)).filter(
        Order.performed_by_user_id == current_user.id
    ).order_by(Order.created_at.desc()).all()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Order ID", "Date", "Symbol", "Side", "Amount", "Filled Qty", "Filled Price", "Status", "Investor", "Email"])

    for o in orders:
        inv = o.investor
        writer.writerow([
            o.id,
            o.created_at.isoformat() if o.created_at else "",
            o.symbol,
            o.side,
            float(o.amount),
            float(o.filled_qty) if o.filled_qty else "",
            float(o.filled_price) if o.filled_price else "",
            o.status,
            inv.full_name if inv else "",
            inv.email if inv else "",
        ])

    output.seek(0)
    filename = f"manager_transactions_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ──────────────────────────────────────────────
# Articles (News Feed for Manager)
# ──────────────────────────────────────────────

import requests as req_lib

YAHOO_SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"
YAHOO_HEADERS = {"User-Agent": "Mozilla/5.0"}

SEARCH_QUERIES = {
    "market": "S&P 500 stock market",
    "tech": "technology stocks AAPL MSFT NVDA",
    "finance": "banking finance stocks JPM GS",
    "etf": "ETF index fund SPY QQQ",
}


def _fetch_yahoo_news(query: str, category: str) -> list[dict]:
    try:
        resp = req_lib.get(
            YAHOO_SEARCH_URL,
            params={"q": query, "quotesCount": 0, "newsCount": 15},
            headers=YAHOO_HEADERS,
            timeout=10,
        )
        data = resp.json()
    except Exception:
        return []

    articles = []
    for item in data.get("news", []):
        tickers = item.get("relatedTickers", [])
        pub_date = item.get("providerPublishTime")

        published_iso = None
        if pub_date:
            try:
                published_iso = datetime.fromtimestamp(pub_date, tz=timezone.utc).isoformat()
            except Exception:
                pass

        articles.append({
            "title": item.get("title", ""),
            "summary": item.get("summary", ""),
            "url": item.get("link", ""),
            "source": item.get("publisher", "Yahoo Finance"),
            "category": category,
            "tickers": [t for t in tickers if t and t != "NULL"],
            "published_at": published_iso,
        })

    return articles


@router.get("/articles", response_model=StandardResponse)
def manager_articles(
    category: str = Query("", max_length=50),
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["readArticles"])),
):
    all_articles = []

    queries = (
        SEARCH_QUERIES.items() if not category else
        [(cat, q) for cat, q in SEARCH_QUERIES.items() if cat == category]
    )

    seen_urls = set()
    seen_titles = set()
    for cat, query in queries:
        articles = _fetch_yahoo_news(query, cat)
        for article in articles:
            url = article.get("url", "")
            title = article.get("title", "")
            if url and url in seen_urls:
                continue
            if title and title in seen_titles:
                continue
            if url:
                seen_urls.add(url)
            seen_titles.add(title)
            all_articles.append(article)

    all_articles.sort(key=lambda a: a.get("published_at") or "", reverse=True)

    return StandardResponse(
        success=True,
        data={"articles": all_articles},
        error=None,
    )
