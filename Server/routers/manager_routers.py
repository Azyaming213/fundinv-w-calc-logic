import csv
from io import StringIO
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from database import get_db
from models import User, Investor, InvestmentAccount, Manager, Fund, Order, FundInvestment, FundTargeting, FundComponent
from schemas.auth_schema import StandardResponse
from dependencies import get_current_user, require_claim
from services.alpaca_service import place_order, get_positions, search_assets, get_snapshots
from services.audit_service import log_event, AUDIT_ACTIONS
import appconstants as AppConstants

from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/manager", tags=["Manager"])


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
    amount: float,
    investment_account_id: int,
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

    account = db.query(InvestmentAccount).filter(
        InvestmentAccount.id == investment_account_id,
        InvestmentAccount.investor_id == investor_id,
        InvestmentAccount.deleted_at.is_(None),
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    from sqlalchemy.orm.attributes import flag_modified

    if side == "buy":
        if fund_id:
            mfb = dict(account.manager_fund_balance or {})
            available = float(mfb.get(str(fund_id), 0))
            if available < amount:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient fund balance. Available in fund: ${available:,.2f}, requested: ${amount:,.2f}",
                )
            mfb[str(fund_id)] = available - amount
            account.manager_fund_balance = mfb
            flag_modified(account, "manager_fund_balance")

            allocs = dict(account.fund_allocations or {})
            allocs[symbol] = float(allocs.get(symbol, 0)) + amount
            account.fund_allocations = allocs
            flag_modified(account, "fund_allocations")
        else:
            mfb = dict(account.manager_fund_balance or {})
            available = float(mfb.get("_unallocated", 0))
            if available < amount:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient unallocated balance. Available: ${available:,.2f}, needed: ${amount:,.2f}",
                )
            mfb["_unallocated"] = available - amount
            account.manager_fund_balance = mfb
            flag_modified(account, "manager_fund_balance")

            allocs = dict(account.fund_allocations or {})
            allocs[symbol] = float(allocs.get(symbol, 0)) + amount
            account.fund_allocations = allocs
            flag_modified(account, "fund_allocations")
    else:
        position = get_positions()
        pos_data = next((p for p in position if p.get("symbol") == symbol), None) if isinstance(position, list) else None
        market_value = float(pos_data.get("market_value", 0)) if pos_data else 0
        sell_amount = min(amount, market_value)
        if sell_amount <= 0:
            raise HTTPException(status_code=400, detail=f"No position to sell for {symbol}")

        allocs = dict(account.fund_allocations or {})
        allocs[symbol] = max(0, float(allocs.get(symbol, 0)) - sell_amount)
        account.fund_allocations = allocs
        flag_modified(account, "fund_allocations")

        mfb = dict(account.manager_fund_balance or {})
        mfb["_unallocated"] = float(mfb.get("_unallocated", 0)) + sell_amount
        account.manager_fund_balance = mfb
        flag_modified(account, "manager_fund_balance")
        amount = sell_amount

    alpaca_result = place_order(symbol=symbol, notional=amount, side=side)
    if alpaca_result.get("error"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Alpaca order failed: {alpaca_result.get('message', 'Unknown error')}",
        )

    order = Order(
        investor_id=investor_id,
        investment_account_id=account.id,
        fund_id=fund_id,
        alpaca_order_id=alpaca_result.get("id", ""),
        symbol=symbol,
        side=side,
        amount=amount,
        status=alpaca_result.get("status", "accepted"),
        performed_by_user_id=current_user.id,
    )
    db.add(order)
    db.commit()
    db.refresh(order)

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
        "status": alpaca_result.get("status"),
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
    db.add(fund)
    db.commit()
    db.refresh(fund)

    for item in holdings:
        db.add(FundComponent(
            fund_id=fund.id,
            component_fund_id=item.get("fund_id"),
            symbol=item["symbol"].upper(),
            component_name=item.get("name", item["symbol"]),
            asset_type=item.get("asset_type", "stock"),
            target_pct=float(item["allocation"]),
        ))
    db.commit()

    log_event(
        db=db,
        user_id=current_user.id,
        action=AUDIT_ACTIONS["FUND_CREATED"],
        details=f"Fund '{fund.name}' created by {current_user.email}",
        entity_type="fund",
        entity_id=fund.id,
        changes={"name": fund.name, "strategy": fund.strategy, "risk_level": fund.risk_level},
        status="success",
    )

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
