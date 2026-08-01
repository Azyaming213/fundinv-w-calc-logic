from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.orm.attributes import flag_modified

from database import get_db
from models import PortfolioHolding, Investor, InvestmentAccount, InvestmentTransaction, User, FundFlow, Fund, FundPosition, FundValuation
from dependencies import require_claim
from schemas.auth_schema import StandardResponse
from schemas.portfolio_schema import CreateAccountRequest, UpdateAccountRequest
from services.audit_service import log_event
from services.pnl_service import compute_investor_pnl, compute_fund_return, compute_unrealized_pnl, snapshot_daily_holdings
from services.portfolio_pdf_service import build_portfolio_pdf
from config import settings
import appconstants as AppConstants

import yagmail

router = APIRouter(prefix="/api/portfolio", tags=["Portfolio"])


def _get_investor(db: Session, email: str) -> Investor:
    investor = db.query(Investor).filter(Investor.email == email).first()
    if not investor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investor not found")
    return investor


@router.get("/valuation-history", response_model=StandardResponse)
def investor_valuation_history(
    fund_id: int | None = Query(None),
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["readOwnPortfolio"])),
    db: Session = Depends(get_db),
):
    investor = _get_investor(db, current_user.email)
    query = db.query(PortfolioHolding).filter(PortfolioHolding.investor_id == investor.id)
    if fund_id is not None:
        query = query.filter(PortfolioHolding.fund_id == fund_id)
    holdings = query.order_by(PortfolioHolding.snapshot_date.desc()).limit(200).all()
    rows = []
    for holding in holdings:
        valuation = db.query(FundValuation).filter_by(
            fund_id=holding.fund_id, valuation_date=holding.snapshot_date
        ).first()
        rows.append({
            "id": holding.id,
            "fund_id": holding.fund_id,
            "fund_name": holding.fund.name if holding.fund else "Unknown",
            "valuation_date": holding.snapshot_date.isoformat(),
            "opening_value": float(holding.opening_value or 0),
            "opening_share_pct": float(holding.opening_shareholding_pct or 0),
            "allocated_pnl": float(holding.daily_pnl or 0),
            "closing_value_before_flows": float(holding.closing_value_before_flows or 0),
            "net_flow": float(holding.net_flow or 0),
            "closing_value": float(holding.account_value or 0),
            "closing_units": float(holding.units or 0),
            "nav_per_unit": float(holding.nav_per_unit or 0),
            "closing_share_pct": float(holding.shareholding_pct or 0),
            "valuation_status": valuation.status if valuation else "legacy",
            "valuation_source": valuation.source if valuation else "legacy",
        })
    return StandardResponse(success=True, data={"valuations": rows}, error=None)


@router.get("/chart-data", response_model=dict)
def get_chart_data(current_user=Depends(require_claim(AppConstants.CLAIMS["readOwnPortfolio"])), db: Session = Depends(get_db)):
    investor = _get_investor(db, current_user.email)
    holdings = (
        db.query(PortfolioHolding)
        .filter(PortfolioHolding.investor_id == investor.id)
        .order_by(PortfolioHolding.holding_date)
        .all()
    )
    by_date: dict[str, dict] = {}
    for holding in holdings:
        day = (holding.snapshot_date or holding.holding_date.date()).isoformat()
        row = by_date.setdefault(day, {
            "holding_date": day,
            "account_value": 0.0,
            "opening_value": 0.0,
            "daily_pnl": 0.0,
            "net_flow": 0.0,
        })
        row["account_value"] += float(holding.account_value or 0)
        row["opening_value"] += float(holding.opening_value or 0)
        row["daily_pnl"] += float(holding.daily_pnl or 0)
        row["net_flow"] += float(holding.net_flow or 0)
    data = [by_date[key] for key in sorted(by_date)]
    return {"success": True, "data": data, "error": None}


@router.get("/summary", response_model=StandardResponse)
def get_summary(current_user: User = Depends(require_claim(AppConstants.CLAIMS["readOwnPortfolio"])), db: Session = Depends(get_db)):
    investor = _get_investor(db, current_user.email)

    accounts = (
        db.query(InvestmentAccount)
        .filter(InvestmentAccount.investor_id == investor.id, InvestmentAccount.deleted_at.is_(None))
        .all()
    )

    total_invested = sum(float(a.total_invested) for a in accounts)
    total_current_value = sum(float(a.current_value) for a in accounts)
    total_fund_balance = sum(float(mfb_val) for a in accounts for mfb_val in (a.manager_fund_balance or {}).values())

    now = datetime.now(timezone.utc)
    pnl_report = compute_investor_pnl(
        db,
        investor.id,
        start_date=datetime(now.year, 1, 1, tzinfo=timezone.utc),
        end_date=now,
    )
    latest_snapshot_date = (
        db.query(func.max(PortfolioHolding.snapshot_date))
        .filter(PortfolioHolding.investor_id == investor.id)
        .scalar()
    )
    today_pnl = Decimal("0")
    if latest_snapshot_date:
        today_pnl = sum((
            Decimal(row.daily_pnl or 0)
            for row in db.query(PortfolioHolding).filter(
                PortfolioHolding.investor_id == investor.id,
                PortfolioHolding.snapshot_date == latest_snapshot_date,
            ).all()
        ), Decimal("0"))
    unrealized = compute_unrealized_pnl(db, investor.id)

    positions = db.query(FundPosition).filter(FundPosition.investor_id == investor.id).all()
    position_rows = []
    normalized_breakdown: dict[int, dict] = {}
    normalized_account_values: dict[int, float] = {}
    normalized_account_balances: dict[int, dict[str, float]] = {}
    for position in positions:
        valuation = (
            db.query(FundValuation)
            .filter(FundValuation.fund_id == position.fund_id)
            .order_by(FundValuation.valuation_date.desc())
            .first()
        )
        nav = float(valuation.nav_per_unit) if valuation else float(position.fund.current_price or 1)
        value = float(position.units) * nav
        row = normalized_breakdown.setdefault(position.fund_id, {
            "fund": position.fund.name,
            "fund_id": position.fund_id,
            "amount": 0.0,
            "units": 0.0,
            "nav_per_unit": nav,
        })
        row["amount"] += value
        row["units"] += float(position.units)
        normalized_account_values[position.investment_account_id] = normalized_account_values.get(position.investment_account_id, 0.0) + value
        normalized_account_balances.setdefault(position.investment_account_id, {})[str(position.fund_id)] = value
        position_rows.append({
            "investment_account_id": position.investment_account_id,
            "fund_id": position.fund_id,
            "fund": position.fund.name,
            "units": float(position.units),
            "nav_per_unit": nav,
            "market_value": value,
            "cost_basis": float(position.cost_basis),
        })
    if positions:
        total_fund_balance = sum(normalized_account_values.values())

    fund_totals: dict[str, float] = {}
    fund_ids_seen: set[int] = set()
    for a in accounts:
        mfb = a.manager_fund_balance or {}
        for key, amount in mfb.items():
            if key == "_unallocated" or key.startswith("_"):
                continue
            try:
                fund_id = int(key)
            except (ValueError, TypeError):
                continue
            fund_ids_seen.add(fund_id)
            fund_name = str(fund_id)
            fund_totals[fund_name] = fund_totals.get(fund_name, 0) + float(amount)

    if normalized_breakdown:
        fund_breakdown = sorted(normalized_breakdown.values(), key=lambda item: -item["amount"])
    elif fund_ids_seen:
        funds_map = {}
        for f in db.query(Fund).filter(Fund.id.in_(fund_ids_seen)).all():
            funds_map[str(f.id)] = f.name

        resolved_breakdown = []
        for fund_name_key, amount in fund_totals.items():
            resolved_breakdown.append({
                "fund": funds_map.get(fund_name_key, f"Fund #{fund_name_key}"),
                "amount": amount,
            })
        fund_breakdown = sorted(resolved_breakdown, key=lambda x: -x[1])
    else:
        fund_breakdown = []

    account_list = []
    for a in accounts:
        mfb_total = normalized_account_values.get(a.id, sum(float(v) for v in (a.manager_fund_balance or {}).values()))
        unallocated = float((a.manager_fund_balance or {}).get("_unallocated", 0))
        display_balances = dict(a.manager_fund_balance or {})
        display_balances.update(normalized_account_balances.get(a.id, {}))
        account_list.append({
            "id": a.id,
            "account_name": a.account_name,
            "account_number": a.account_number,
            "status": a.status,
            "total_invested": float(a.total_invested),
            "current_value": float(a.current_value),
            "fund_balance": mfb_total,
            "unallocated_balance": unallocated,
            "manager_fund_balance": display_balances,
            "fund_allocations": a.fund_allocations or {},
            "investment_strategy": a.investment_strategy,
        })

    return StandardResponse(
        success=True,
        data={
            "total_invested": total_invested,
            "total_current_value": total_current_value,
            "total_fund_balance": total_fund_balance,
            "total_account_value": total_current_value + total_fund_balance,
            "fund_breakdown": fund_breakdown,
            "fund_positions": position_rows,
            "accounts": account_list,
            "pnl": pnl_report,
            "today_pnl": float(today_pnl),
            "pnl_as_of_date": latest_snapshot_date.isoformat() if latest_snapshot_date else None,
            "unrealized": unrealized,
        },
        error=None,
    )


@router.post("/accounts", response_model=StandardResponse)
def create_account(
    request: CreateAccountRequest,
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["readOwnPortfolio"])),
    db: Session = Depends(get_db),
):
    investor = _get_investor(db, current_user.email)

    account_count = (
        db.query(func.count(InvestmentAccount.id))
        .filter(InvestmentAccount.investor_id == investor.id, InvestmentAccount.deleted_at.is_(None))
        .scalar()
    )

    account_number = f"ACC-{investor.id:04d}-{account_count + 1:03d}"

    account = InvestmentAccount(
        investor_id=investor.id,
        account_name=request.account_name,
        account_number=account_number,
        currency=request.currency,
        investment_strategy=request.investment_strategy,
        status="active",
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    return StandardResponse(
        success=True,
        data={
            "id": account.id,
            "account_name": account.account_name,
            "account_number": account.account_number,
            "investment_strategy": account.investment_strategy,
        },
        error=None,
    )


@router.put("/accounts/{account_id}", response_model=StandardResponse)
def update_account(
    account_id: int,
    request: UpdateAccountRequest,
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["readOwnPortfolio"])),
    db: Session = Depends(get_db),
):
    investor = _get_investor(db, current_user.email)

    account = (
        db.query(InvestmentAccount)
        .filter(
            InvestmentAccount.id == account_id,
            InvestmentAccount.investor_id == investor.id,
            InvestmentAccount.deleted_at.is_(None),
        )
        .first()
    )
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    if request.account_name is not None:
        account.account_name = request.account_name
    if request.investment_strategy is not None:
        account.investment_strategy = request.investment_strategy

    db.commit()
    db.refresh(account)

    return StandardResponse(
        success=True,
        data={
            "id": account.id,
            "account_name": account.account_name,
            "account_number": account.account_number,
            "investment_strategy": account.investment_strategy,
        },
        error=None,
    )


@router.get("/recent-transactions", response_model=StandardResponse)
def get_recent_transactions(
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["readOwnPortfolio"])),
    db: Session = Depends(get_db),
):
    investor = _get_investor(db, current_user.email)

    txns = (
        db.query(InvestmentTransaction)
        .filter(InvestmentTransaction.investor_id == investor.id)
        .order_by(InvestmentTransaction.trade_time.desc())
        .limit(10)
        .all()
    )

    txn_list = [
        {
            "id": t.id,
            "ticket": t.ticket,
            "trade_type": t.trade_type,
            "symbol": t.symbol,
            "volume": float(t.volume),
            "price": float(t.price),
            "net_pnl": float(t.net_pnl),
            "trade_time": t.trade_time.isoformat() if t.trade_time else None,
        }
        for t in txns
    ]

    return StandardResponse(
        success=True,
        data={"transactions": txn_list},
        error=None,
    )


@router.post("/accounts/{account_id}/close", response_model=StandardResponse)
def close_account(
    account_id: int,
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["readOwnPortfolio"])),
    db: Session = Depends(get_db),
):
    investor = _get_investor(db, current_user.email)

    account = (
        db.query(InvestmentAccount)
        .filter(
            InvestmentAccount.id == account_id,
            InvestmentAccount.investor_id == investor.id,
            InvestmentAccount.deleted_at.is_(None),
        )
        .first()
    )
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    if account.status == "closed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account is already closed")

    open_position = db.query(FundPosition).filter(
        FundPosition.investment_account_id == account.id,
        FundPosition.units > 0,
    ).first()
    pending_flow = db.query(FundFlow).filter(
        FundFlow.investment_account_id == account.id,
        FundFlow.status.in_([
            "pending_ops_team",
            "approved_pending_payment",
            "awaiting_payout_setup",
            "pending_fund_transfer",
        ]),
    ).first()
    mfb_total = sum(float(v) for v in (account.manager_fund_balance or {}).values())
    if open_position or pending_flow or abs(mfb_total) > 0.005:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account cannot be closed while it has fund units, a pending fund flow, or a non-zero fund balance. Withdraw or transfer the balance first.",
        )

    account.status = "closed"
    account.deleted_at = datetime.now(timezone.utc)
    db.commit()

    log_event(
        db=db,
        user_id=current_user.id,
        action="account_closed",
        details=f"Account {account.account_name} ({account.account_number}) closed with zero balance",
        entity_type="account",
        entity_id=account.id,
        status="success",
    )

    return StandardResponse(
        success=True,
        data={
            "account_id": account.id,
            "account_name": account.account_name,
            "status": "closed",
            "liquidated_positions": [],
            "remaining_fund_balance": mfb_total,
        },
        error=None,
    )


@router.post("/send-summary-email", response_model=StandardResponse)
def send_summary_email(
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["exportPortfolio"])),
    db: Session = Depends(get_db),
):
    investor = _get_investor(db, current_user.email)

    accounts = (
        db.query(InvestmentAccount)
        .filter(InvestmentAccount.investor_id == investor.id, InvestmentAccount.deleted_at.is_(None))
        .all()
    )

    total_invested = sum(float(a.total_invested) for a in accounts)
    total_current_value = sum(float(a.current_value) for a in accounts)
    total_fund_balance = sum(float(v) for a in accounts for v in (a.manager_fund_balance or {}).values())
    total_account_value = total_current_value + total_fund_balance

    fund_totals: dict[str, float] = {}
    for a in accounts:
        allocs = a.fund_allocations or {}
        for fund, amount in allocs.items():
            fund_totals[fund] = fund_totals.get(fund, 0) + float(amount)

    txns = (
        db.query(InvestmentTransaction)
        .filter(InvestmentTransaction.investor_id == investor.id)
        .order_by(InvestmentTransaction.trade_time.desc())
        .limit(10)
        .all()
    )

    account_rows = ""
    for a in accounts:
        mfb_total = sum(float(v) for v in (a.manager_fund_balance or {}).values())
        allocs = a.fund_allocations or {}
        alloc_str = ", ".join(f"{k}: ${v:,.2f}" for k, v in allocs.items()) if allocs else "None"
        account_rows += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;font-weight:500">{a.account_name}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;color:#64748b">{a.account_number}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0">{a.investment_strategy or 'N/A'}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;text-align:right">${float(a.total_invested):,.2f}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;text-align:right">${float(a.current_value):,.2f}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;text-align:right">${mfb_total:,.2f}</td>
        </tr>"""

    alloc_rows = ""
    for fund, amount in sorted(fund_totals.items(), key=lambda x: -x[1]):
        pct = (amount / total_current_value * 100) if total_current_value > 0 else 0
        alloc_rows += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;font-weight:500">{fund}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;text-align:right">${amount:,.2f}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;text-align:right">{pct:.1f}%</td>
        </tr>"""

    txn_rows = ""
    for t in txns:
        color = "#10b981" if t.net_pnl >= 0 else "#ef4444"
        txn_rows += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;font-weight:500">{t.symbol}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;text-transform:uppercase;font-size:11px;font-weight:700;color:{'#10b981' if t.trade_type == 'buy' else '#ef4444'}">{t.trade_type}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;text-align:right">{t.volume}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;text-align:right">${float(t.price):,.2f}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;text-align:right;color:{color};font-weight:600">${float(t.net_pnl):,.2f}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;text-align:right">{t.trade_time.strftime('%b %d, %Y %H:%M') if t.trade_time else 'N/A'}</td>
        </tr>"""

    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:680px;margin:0 auto;color:#1e293b">
      <div style="background:linear-gradient(135deg,#2563eb,#1d4ed8);padding:32px;border-radius:12px 12px 0 0">
        <h1 style="color:#fff;margin:0;font-size:22px">FundInv Portfolio Summary</h1>
        <p style="color:#bfdbfe;margin:6px 0 0;font-size:13px">Report for {current_user.full_name}</p>
      </div>

      <div style="background:#f8fafc;padding:24px;border:1px solid #e2e8f0;border-top:none">
        <h2 style="margin:0 0 16px;font-size:16px;color:#1e293b">Account Overview</h2>
        <div style="display:flex;gap:16px;flex-wrap:wrap">
          <div style="flex:1;min-width:140px;background:#fff;padding:16px;border-radius:8px;border:1px solid #e2e8f0">
            <p style="margin:0;font-size:11px;color:#64748b;text-transform:uppercase">Total Account Value</p>
            <p style="margin:4px 0 0;font-size:22px;font-weight:700;color:#2563eb">${total_account_value:,.2f}</p>
          </div>
          <div style="flex:1;min-width:140px;background:#fff;padding:16px;border-radius:8px;border:1px solid #e2e8f0">
            <p style="margin:0;font-size:11px;color:#64748b;text-transform:uppercase">Invested</p>
            <p style="margin:4px 0 0;font-size:22px;font-weight:700;color:#1e293b">${total_current_value:,.2f}</p>
          </div>
          <div style="flex:1;min-width:140px;background:#fff;padding:16px;border-radius:8px;border:1px solid #e2e8f0">
            <p style="margin:0;font-size:11px;color:#64748b;text-transform:uppercase">Fund Balance</p>
            <p style="margin:4px 0 0;font-size:22px;font-weight:700;color:#1e293b">${total_fund_balance:,.2f}</p>
          </div>
        </div>
      </div>

      <div style="background:#fff;padding:24px;border:1px solid #e2e8f0;border-top:none">
        <h2 style="margin:0 0 12px;font-size:16px;color:#1e293b">Investment Accounts</h2>
        <table style="width:100%;border-collapse:collapse;font-size:13px">
          <thead>
            <tr style="background:#f1f5f9">
              <th style="padding:8px 12px;text-align:left;font-weight:600;color:#475569">Account</th>
              <th style="padding:8px 12px;text-align:left;font-weight:600;color:#475569">Number</th>
              <th style="padding:8px 12px;text-align:left;font-weight:600;color:#475569">Strategy</th>
              <th style="padding:8px 12px;text-align:right;font-weight:600;color:#475569">Invested</th>
              <th style="padding:8px 12px;text-align:right;font-weight:600;color:#475569">Value</th>
              <th style="padding:8px 12px;text-align:right;font-weight:600;color:#475569">Fund Balance</th>
            </tr>
          </thead>
          <tbody>{account_rows if account_rows else '<tr><td colspan="6" style="padding:16px;text-align:center;color:#94a3b8">No accounts</td></tr>'}</tbody>
        </table>
      </div>

      <div style="background:#fff;padding:24px;border:1px solid #e2e8f0;border-top:none">
        <h2 style="margin:0 0 12px;font-size:16px;color:#1e293b">Fund Allocation</h2>
        <table style="width:100%;border-collapse:collapse;font-size:13px">
          <thead>
            <tr style="background:#f1f5f9">
              <th style="padding:8px 12px;text-align:left;font-weight:600;color:#475569">Fund</th>
              <th style="padding:8px 12px;text-align:right;font-weight:600;color:#475569">Amount</th>
              <th style="padding:8px 12px;text-align:right;font-weight:600;color:#475569">% of Portfolio</th>
            </tr>
          </thead>
          <tbody>{alloc_rows if alloc_rows else '<tr><td colspan="3" style="padding:16px;text-align:center;color:#94a3b8">No allocations</td></tr>'}</tbody>
        </table>
      </div>

      <div style="background:#fff;padding:24px;border:1px solid #e2e8f0;border-top:none">
        <h2 style="margin:0 0 12px;font-size:16px;color:#1e293b">Recent Transactions</h2>
        <table style="width:100%;border-collapse:collapse;font-size:13px">
          <thead>
            <tr style="background:#f1f5f9">
              <th style="padding:8px 12px;text-align:left;font-weight:600;color:#475569">Symbol</th>
              <th style="padding:8px 12px;text-align:left;font-weight:600;color:#475569">Type</th>
              <th style="padding:8px 12px;text-align:right;font-weight:600;color:#475569">Qty</th>
              <th style="padding:8px 12px;text-align:right;font-weight:600;color:#475569">Price</th>
              <th style="padding:8px 12px;text-align:right;font-weight:600;color:#475569">P&L</th>
              <th style="padding:8px 12px;text-align:right;font-weight:600;color:#475569">Date</th>
            </tr>
          </thead>
          <tbody>{txn_rows if txn_rows else '<tr><td colspan="6" style="padding:16px;text-align:center;color:#94a3b8">No transactions</td></tr>'}</tbody>
        </table>
      </div>

      <div style="padding:20px 24px;background:#f8fafc;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 12px 12px;text-align:center">
        <p style="margin:0;font-size:12px;color:#94a3b8">This report was generated automatically by FundInv. Do not reply to this email.</p>
      </div>
    </div>
    """

    if not settings.SMTP_EMAIL or not settings.SMTP_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email service not configured. Please set SMTP_EMAIL and SMTP_PASSWORD.",
        )

    try:
        yag = yagmail.SMTP(user=settings.SMTP_EMAIL, password=settings.SMTP_PASSWORD)
        yag.send(
            to=current_user.email,
            subject=f"FundInv Portfolio Summary — {current_user.full_name}",
            contents=html_body,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send email: {str(e)}",
        )

    return StandardResponse(
        success=True,
        data={"message": f"Portfolio summary sent to {current_user.email}"},
        error=None,
    )


@router.get("/export-pdf", response_class=StreamingResponse)
def export_portfolio_pdf(
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["exportPortfolio"])),
    db: Session = Depends(get_db),
):
    investor = _get_investor(db, current_user.email)

    accounts = (
        db.query(InvestmentAccount)
        .filter(InvestmentAccount.investor_id == investor.id, InvestmentAccount.deleted_at.is_(None))
        .all()
    )

    txns = (
        db.query(InvestmentTransaction)
        .filter(InvestmentTransaction.investor_id == investor.id)
        .order_by(InvestmentTransaction.trade_time.desc())
        .limit(20)
        .all()
    )

    pdf_bytes = build_portfolio_pdf(investor, accounts, txns)

    filename = f"FundInv_Portfolio_{investor.full_name.replace(' ', '_')}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.pdf"

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ──────────────────────────────────────────────────────────
# P&L Reporting (Challenge Statement Sections 3.2, 8.1, 8.2)
# ──────────────────────────────────────────────────────────

@router.get("/pnl", response_model=StandardResponse)
def get_pnl_report(
    start_date: datetime = Query(None, description="Start date (ISO 8601)"),
    end_date: datetime = Query(None, description="End date (ISO 8601)"),
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["readOwnPortfolio"])),
    db: Session = Depends(get_db),
):
    """Return total dollar PNL, realized/unrealized PNL and fund returns.

    Implements Section 8.2: total dollar PNL = sum(daily PNL * investor share),
    fund return = compounded daily % fund return over the period.
    """
    investor = _get_investor(db, current_user.email)
    report = compute_investor_pnl(db, investor.id, start_date=start_date, end_date=end_date)
    unrealized = compute_unrealized_pnl(db, investor.id)
    return StandardResponse(success=True, data={"pnl": report, "unrealized": unrealized}, error=None)


@router.get("/pnl/fund/{fund_id}", response_model=StandardResponse)
def get_fund_pnl(
    fund_id: int,
    start_date: datetime = Query(None),
    end_date: datetime = Query(None),
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["readOwnPortfolio"])),
    db: Session = Depends(get_db),
):
    """Return compounded fund return and daily PNL breakdown for a fund."""
    fund = db.query(Fund).filter(Fund.id == fund_id).first()
    if not fund:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fund not found")
    report = compute_fund_return(db, fund_id, start_date=start_date, end_date=end_date)
    return StandardResponse(success=True, data={"fund": {"id": fund.id, "name": fund.name, "ticker": fund.ticker}, "report": report}, error=None)


@router.get("/holdings", response_model=StandardResponse)
def get_holdings(
    fund_id: int = Query(None, description="Filter by fund"),
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["readOwnPortfolio"])),
    db: Session = Depends(get_db),
):
    """Return portfolio holdings (Section 5.3) for the current investor."""
    investor = _get_investor(db, current_user.email)
    q = db.query(PortfolioHolding).filter(PortfolioHolding.investor_id == investor.id)
    if fund_id:
        q = q.filter(PortfolioHolding.fund_id == fund_id)
    holdings = q.order_by(PortfolioHolding.holding_date.asc()).all()
    data = [
        {
            "id": h.id,
            "fund_id": h.fund_id,
            "holding_date": h.holding_date.isoformat(),
            "account_value": float(h.account_value),
            "shareholding_pct": float(h.shareholding_pct),
            "daily_pnl": float(h.daily_pnl),
            "fund_nav": float(h.fund_nav) if h.fund_nav else None,
            "snapshot_date": h.snapshot_date.isoformat() if h.snapshot_date else h.holding_date.date().isoformat(),
            "units": float(h.units or 0),
            "nav_per_unit": float(h.nav_per_unit or 0),
            "opening_value": float(h.opening_value or 0),
            "opening_shareholding_pct": float(h.opening_shareholding_pct or 0),
            "closing_value_before_flows": float(h.closing_value_before_flows or 0),
            "net_flow": float(h.net_flow or 0),
        }
        for h in holdings
    ]
    return StandardResponse(success=True, data={"holdings": data}, error=None)


@router.post("/pnl/snapshot", response_model=StandardResponse)
def trigger_pnl_snapshot(
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["exportPortfolio"])),
    db: Session = Depends(get_db),
):
    """Manually trigger the daily PNL snapshot (Section 8.1)."""
    inserted = snapshot_daily_holdings(db)
    return StandardResponse(
        success=True,
        data={"message": "PNL snapshot complete", "holdings_recorded": inserted},
        error=None,
    )
