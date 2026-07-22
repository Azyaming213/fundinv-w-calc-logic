from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from database import get_db
from models import Investor, InvestmentAccount, Order, Fund, FundInvestment
from dependencies import require_claim
from schemas.auth_schema import StandardResponse
from services.alpaca_service import place_order, get_position
from services.pnl_service import record_buy_transaction, record_sell_transaction
import appconstants as AppConstants

router = APIRouter(prefix="/api/trading", tags=["Trading"])


class BuyRequest(BaseModel):
    investment_account_id: int
    symbol: str = Field(..., examples=["AMD"])
    amount: float = Field(..., gt=0, description="USD amount to invest")
    fund_id: int | None = None


@router.post("/buy", response_model=StandardResponse)
def buy_stock(
    request: BuyRequest,
    current_user=Depends(require_claim(AppConstants.CLAIMS["executeTrades"])),
    db: Session = Depends(get_db),
):
    investor = db.query(Investor).filter(Investor.email == current_user.email).first()
    if not investor:
        raise HTTPException(status_code=404, detail="Investor not found")

    account = (
        db.query(InvestmentAccount)
        .filter(
            InvestmentAccount.id == request.investment_account_id,
            InvestmentAccount.investor_id == investor.id,
            InvestmentAccount.deleted_at.is_(None),
        )
        .first()
    )
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    from sqlalchemy.orm.attributes import flag_modified

    if request.fund_id:
        mfb = dict(account.manager_fund_balance or {})
        available = float(mfb.get(str(request.fund_id), 0))
        if available < request.amount:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient fund balance. Available in fund: ${available:.2f}, need ${request.amount:.2f}",
            )
        mfb[str(request.fund_id)] = available - request.amount
    else:
        mfb = dict(account.manager_fund_balance or {})
        available = float(mfb.get("_unallocated", 0))
        if available < request.amount:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient unallocated balance. Available: ${available:.2f}, need ${request.amount:.2f}",
            )
        mfb["_unallocated"] = available - request.amount

    account.manager_fund_balance = mfb
    flag_modified(account, "manager_fund_balance")

    alpaca_result = place_order(
        symbol=request.symbol,
        notional=request.amount,
        side="buy",
    )

    if alpaca_result.get("error"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Alpaca order failed: {alpaca_result.get('message', 'Unknown error')}",
        )

    filled_qty = float(alpaca_result.get("filled_qty") or 0)
    filled_price = float(alpaca_result.get("filled_avg_price") or 0)
    if filled_qty <= 0 or filled_price <= 0:
        filled_qty = float(alpaca_result.get("qty") or 0)
        filled_price = float(alpaca_result.get("filled_price") or request.amount)

    if filled_qty <= 0 and filled_price > 0:
        filled_qty = request.amount / filled_price
    if filled_price <= 0 and filled_qty > 0:
        filled_price = request.amount / filled_qty

    try:
        record_buy_transaction(
            db=db,
            investor_id=investor.id,
            symbol=request.symbol,
            volume=filled_qty,
            price=filled_price,
            fund_id=request.fund_id,
            investment_account_id=account.id,
            external_id=alpaca_result.get("id"),
            comment=f"Buy order via Alpaca {alpaca_result.get('id', '')}",
        )
    except Exception as e:
        print(f"[PNL] Failed to record buy transaction: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Trade executed but PNL recording failed: {str(e)}",
        )

    allocs = dict(account.fund_allocations or {})
    allocs[request.symbol] = float(allocs.get(request.symbol, 0)) + request.amount
    account.fund_allocations = allocs
    flag_modified(account, "fund_allocations")

    order = Order(
        investor_id=investor.id,
        investment_account_id=account.id,
        fund_id=request.fund_id,
        alpaca_order_id=alpaca_result.get("id", ""),
        symbol=request.symbol,
        side="buy",
        amount=request.amount,
        filled_qty=filled_qty,
        filled_price=filled_price,
        status=alpaca_result.get("status", "accepted"),
    )
    db.add(order)

    fund = db.query(Fund).filter(Fund.ticker == request.symbol).first()
    if fund:
        investment = FundInvestment(
            investor_id=investor.id,
            fund_id=fund.id,
            amount=request.amount,
            status="completed",
        )
        db.add(investment)

    db.commit()
    db.refresh(order)

    return StandardResponse(
        success=True,
        data={
            "order_id": order.id,
            "alpaca_order_id": alpaca_result.get("id"),
            "symbol": request.symbol,
            "amount": request.amount,
            "filled_qty": filled_qty,
            "filled_price": filled_price,
            "status": alpaca_result.get("status"),
        },
        error=None,
    )


@router.post("/sell", response_model=StandardResponse)
def sell_stock(
    request: BuyRequest,
    current_user=Depends(require_claim(AppConstants.CLAIMS["executeTrades"])),
    db: Session = Depends(get_db),
):
    investor = db.query(Investor).filter(Investor.email == current_user.email).first()
    if not investor:
        raise HTTPException(status_code=404, detail="Investor not found")

    account = (
        db.query(InvestmentAccount)
        .filter(
            InvestmentAccount.id == request.investment_account_id,
            InvestmentAccount.investor_id == investor.id,
            InvestmentAccount.deleted_at.is_(None),
        )
        .first()
    )
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    position = get_position(request.symbol)
    if not position or position.get("error"):
        raise HTTPException(
            status_code=400,
            detail=f"No position found for {request.symbol}",
        )

    market_value = float(position.get("market_value", 0))
    if market_value <= 0:
        raise HTTPException(
            status_code=400,
            detail=f"No holdings to sell for {request.symbol}",
        )

    amount_to_sell = min(request.amount, market_value)

    alpaca_result = place_order(
        symbol=request.symbol,
        notional=amount_to_sell,
        side="sell",
    )

    if alpaca_result.get("error"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Alpaca sell order failed: {alpaca_result.get('message', 'Unknown error')}",
        )

    filled_qty = float(alpaca_result.get("filled_qty") or 0)
    filled_price = float(alpaca_result.get("filled_avg_price") or 0)
    if filled_qty <= 0 and filled_price > 0:
        filled_qty = amount_to_sell / filled_price
    if filled_price <= 0 and filled_qty > 0:
        filled_price = amount_to_sell / filled_qty
    if filled_qty <= 0:
        filled_qty = float(position.get("qty", 0))
    if filled_price <= 0:
        filled_price = float(position.get("current_price", 0))

    fifo_result = None
    try:
        _, fifo_result = record_sell_transaction(
            db=db,
            investor_id=investor.id,
            symbol=request.symbol,
            volume=filled_qty,
            price=filled_price,
            fund_id=request.fund_id,
            investment_account_id=account.id,
            external_id=alpaca_result.get("id"),
            comment=f"Sell order via Alpaca {alpaca_result.get('id', '')}",
        )
    except Exception as e:
        print(f"[PNL] Failed to record sell transaction: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Trade executed but PNL recording failed: {str(e)}",
        )

    from sqlalchemy.orm.attributes import flag_modified

    allocs = dict(account.fund_allocations or {})
    current_alloc = float(allocs.get(request.symbol, 0))
    allocs[request.symbol] = max(0, current_alloc - amount_to_sell)
    account.fund_allocations = allocs
    flag_modified(account, "fund_allocations")

    mfb = dict(account.manager_fund_balance or {})
    mfb["_unallocated"] = float(mfb.get("_unallocated", 0)) + amount_to_sell
    account.manager_fund_balance = mfb
    flag_modified(account, "manager_fund_balance")

    order = Order(
        investor_id=investor.id,
        investment_account_id=account.id,
        fund_id=request.fund_id,
        alpaca_order_id=alpaca_result.get("id", ""),
        symbol=request.symbol,
        side="sell",
        amount=amount_to_sell,
        filled_qty=filled_qty,
        filled_price=filled_price,
        status=alpaca_result.get("status", "accepted"),
    )
    db.add(order)

    fund = db.query(Fund).filter(Fund.ticker == request.symbol).first()
    if fund:
        investment = FundInvestment(
            investor_id=investor.id,
            fund_id=fund.id,
            amount=amount_to_sell,
            status="completed",
        )
        db.add(investment)

    db.commit()
    db.refresh(order)

    return StandardResponse(
        success=True,
        data={
            "order_id": order.id,
            "alpaca_order_id": alpaca_result.get("id"),
            "symbol": request.symbol,
            "amount": amount_to_sell,
            "filled_qty": filled_qty,
            "filled_price": filled_price,
            "status": alpaca_result.get("status"),
            "position_market_value": market_value,
            "sold_value": amount_to_sell,
            "remaining_position": market_value - amount_to_sell,
            "realized_pnl": float(fifo_result.realized_profit) if fifo_result else 0.0,
            "matched_qty": float(fifo_result.matched_qty) if fifo_result else 0.0,
            "avg_buy_price": float(fifo_result.avg_buy_price) if fifo_result else 0.0,
        },
        error=None,
    )


@router.get("/orders", response_model=StandardResponse)
def list_orders(
    current_user=Depends(require_claim(AppConstants.CLAIMS["readOwnPortfolio"])),
    db: Session = Depends(get_db),
):
    investor = db.query(Investor).filter(Investor.email == current_user.email).first()
    if not investor:
        raise HTTPException(status_code=404, detail="Investor not found")

    orders = (
        db.query(Order)
        .filter(Order.investor_id == investor.id)
        .order_by(Order.created_at.desc())
        .limit(50)
        .all()
    )

    order_list = []
    for o in orders:
        order_list.append({
            "id": o.id,
            "alpaca_order_id": o.alpaca_order_id,
            "symbol": o.symbol,
            "side": o.side,
            "amount": float(o.amount),
            "filled_qty": float(o.filled_qty) if o.filled_qty else None,
            "filled_price": float(o.filled_price) if o.filled_price else None,
            "status": o.status,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        })

    return StandardResponse(
        success=True,
        data={"orders": order_list},
        error=None,
    )
