import stripe
import uuid
import secrets
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Query, HTTPException, status, Request, Body
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_, update
from pydantic import BaseModel

from database import get_db
from models import User, AuditLog, Investor, FundFlow, FundValuation, InvestmentTransaction, Order, Fund, Role, Manager, InvestmentAccount, FundBalanceEntry, InviteRequest, FeedbackTicket, Invite
from schemas.auth_schema import StandardResponse
from schemas.portfolio_schema import FundFlowActionRequest
from dependencies import get_current_user, require_claim, require_any_claim
from services.alpaca_service import get_orders
from services.auth_service import hash_password
from services.audit_service import log_event, AUDIT_ACTIONS, get_system_user
from services.email_service import send_fund_flow_approved_email, send_fund_flow_completed_email, send_fund_flow_rejected_email, send_invite_email
from services.fund_accounting_service import settle_fund_flow
from services.fund_targeting_service import expose_fund_to_active_investors
from services.paynow_demo_service import paynow_qr_data_url
from config import settings
import appconstants as AppConstants

router = APIRouter(prefix="/api/admin", tags=["Admin"])
logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY


@router.get("/valuations", response_model=StandardResponse)
def list_all_valuations(
    fund_id: int | None = Query(None),
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["readAuditLogs"])),
    db: Session = Depends(get_db),
):
    query = db.query(FundValuation)
    if fund_id is not None:
        query = query.filter(FundValuation.fund_id == fund_id)
    rows = query.order_by(FundValuation.valuation_date.desc()).limit(200).all()
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
        "finalized_by_email": row.finalized_by.email if row.finalized_by else None,
        "finalized_at": row.finalized_at.isoformat() if row.finalized_at else None,
        "notes": row.notes,
    } for row in rows]}, error=None)


# ──────────────────────────────────────────────
# Stats
# ──────────────────────────────────────────────

@router.get("/stats", response_model=StandardResponse)
def get_stats(current_user: User = Depends(require_claim(AppConstants.CLAIMS["readSystemStats"])), db: Session = Depends(get_db)):
    total_users = db.query(func.count(User.id)).scalar()
    active_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar()

    return StandardResponse(
        success=True,
        data={
            "total_users": total_users,
            "active_users": active_users,
        },
        error=None,
    )


class FundReviewRequest(BaseModel):
    decision: str
    notes: str | None = None


@router.get("/fund-reviews", response_model=StandardResponse)
def list_fund_reviews(
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["reviewFunds"])),
    db: Session = Depends(get_db),
):
    funds = db.query(Fund).filter(Fund.review_status == "pending_ops_review").order_by(Fund.submitted_at.asc()).all()
    return StandardResponse(success=True, data={"funds": [
        {
            "id": fund.id,
            "name": fund.name,
            "description": fund.description,
            "strategy": fund.strategy,
            "risk_level": fund.risk_level,
            "creator_manager_id": fund.creator_manager_id,
            "portfolio_composition": fund.portfolio_composition or [],
            "submitted_at": fund.submitted_at.isoformat() if fund.submitted_at else None,
        }
        for fund in funds
    ]}, error=None)


@router.post("/fund-reviews/{fund_id}", response_model=StandardResponse)
def review_fund(
    fund_id: int,
    body: FundReviewRequest,
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["reviewFunds"])),
    db: Session = Depends(get_db),
):
    if body.decision not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="Decision must be approve or reject")
    fund = db.query(Fund).filter(Fund.id == fund_id, Fund.review_status == "pending_ops_review").first()
    if not fund:
        raise HTTPException(status_code=404, detail="Pending fund review not found")
    fund.review_status = "approved" if body.decision == "approve" else "rejected"
    fund.is_active = body.decision == "approve"
    fund.reviewed_by_user_id = current_user.id
    fund.reviewed_at = datetime.now(timezone.utc)
    fund.review_notes = body.notes
    targeted_count = 0
    eligible_investor_count = 0
    if body.decision == "approve":
        targeted_count, eligible_investor_count = expose_fund_to_active_investors(db, fund.id)
    log_event(
        db=db,
        user_id=current_user.id,
        action=AUDIT_ACTIONS["FUND_UPDATED"],
        details=f"Fund '{fund.name}' {fund.review_status} by operations",
        entity_type="fund",
        entity_id=fund.id,
        changes={
            "review_status": fund.review_status,
            "notes": body.notes,
            "auto_targeted_investors": targeted_count,
            "eligible_investors": eligible_investor_count,
        },
        status="success",
        commit=False,
    )
    db.commit()
    return StandardResponse(success=True, data={
        "id": fund.id,
        "review_status": fund.review_status,
        "auto_targeted_investors": targeted_count,
        "eligible_investors": eligible_investor_count,
    }, error=None)


# ──────────────────────────────────────────────
# Audit Logs
# ──────────────────────────────────────────────

@router.get("/audit-logs", response_model=StandardResponse)
def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["readAuditLogs"])),
    db: Session = Depends(get_db),
):
    total = db.query(func.count(AuditLog.id)).scalar()

    logs = (
        db.query(AuditLog)
        .options(joinedload(AuditLog.user))
        .order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    log_list = []
    for log in logs:
        log_list.append({
            "id": log.id,
            "user_id": log.user_id,
            "email": log.user.email if log.user else None,
            "full_name": log.user.full_name if log.user else None,
            "action": log.action,
            "details": log.details,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "changes": log.changes,
            "status": log.status,
            "ip_address": log.ip_address,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        })

    return StandardResponse(
        success=True,
        data={
            "logs": log_list,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        },
        error=None,
    )


@router.get("/invite-requests", response_model=StandardResponse)
def list_invite_requests(
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["readInvites"])),
    db: Session = Depends(get_db),
):
    requests = db.query(InviteRequest).order_by(InviteRequest.created_at.desc()).all()
    return StandardResponse(success=True, data={"requests": [
        {
            "id": item.id,
            "email": item.email,
            "full_name": item.full_name,
            "role": item.role.name if item.role else None,
            "status": item.status,
            "requested_by": item.requested_by.email if item.requested_by else None,
            "review_notes": item.review_notes,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }
        for item in requests
    ]}, error=None)


class InviteRequestDecision(BaseModel):
    decision: str
    notes: str | None = None


@router.post("/invite-requests/{request_id}/review", response_model=StandardResponse)
def review_invite_request(
    request_id: int,
    body: InviteRequestDecision,
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["createInvites"])),
    db: Session = Depends(get_db),
):
    if body.decision not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="Decision must be approve or reject")
    item = db.query(InviteRequest).filter(InviteRequest.id == request_id, InviteRequest.status == "pending_admin_review").first()
    if not item:
        raise HTTPException(status_code=404, detail="Pending invite request not found")
    item.reviewed_by_user_id = current_user.id
    item.reviewed_at = datetime.now(timezone.utc)
    item.review_notes = body.notes
    if body.decision == "reject":
        item.status = "rejected"
        db.commit()
        return StandardResponse(success=True, data={"id": item.id, "status": item.status}, error=None)

    token = secrets.token_urlsafe(32)
    invite = Invite(
        email=item.email,
        full_name=item.full_name,
        role_id=item.role_id,
        token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        created_by_id=current_user.id,
    )
    db.add(invite)
    db.flush()
    item.invite_id = invite.id
    item.status = "approved"
    db.commit()
    email_sent = send_invite_email(
        to_email=item.email,
        full_name=item.full_name,
        token=token,
        expires_at=invite.expires_at.isoformat(),
        role=item.role.name if item.role else "investor",
    )
    log_event(db=db, user_id=current_user.id, action=AUDIT_ACTIONS["INVITE_SENT"],
              details=f"Invite request {item.id} approved and invitation sent", entity_type="invite",
              entity_id=invite.id, status="success")
    return StandardResponse(success=True, data={"id": item.id, "status": item.status, "invite_id": invite.id, "email_sent": email_sent}, error=None)


# ──────────────────────────────────────────────
# Fund Flows (read — Admin + Ops can read all)
# ──────────────────────────────────────────────

@router.get("/fund-flows", response_model=StandardResponse)
def list_fund_flows(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query("", max_length=100),
    flow_type: str = Query("", max_length=20),
    status: str = Query("", max_length=30),
    current_user: User = Depends(require_any_claim([AppConstants.CLAIMS["readAllFundFlows"], AppConstants.CLAIMS["readOwnFundFlows"]])),
    db: Session = Depends(get_db),
):
    query = db.query(FundFlow).join(Investor, FundFlow.investor_id == Investor.id)

    owns_read_all = current_user.role and AppConstants.CLAIMS["readAllFundFlows"] in AppConstants.ROLE_CLAIMS.get(current_user.role.name, [])
    if not owns_read_all:
        investor = db.query(Investor).filter(Investor.email == current_user.email).first()
        if investor:
            query = query.filter(FundFlow.investor_id == investor.id)

    if search:
        term = f"%{search}%"
        query = query.filter(
            or_(
                Investor.email.ilike(term),
                Investor.full_name.ilike(term),
                FundFlow.request_id.ilike(term),
            )
        )

    if flow_type:
        query = query.filter(FundFlow.flow_type == flow_type)

    if status:
        query = query.filter(FundFlow.status == status)

    total = query.count()

    flows = (
        query
        .order_by(FundFlow.requested_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    status_guidance = {
        "awaiting_investor_payment": ("Demo PayNow payment required", "investor_payment"),
        "pending_ops_team": ("Operations review required", "operations_review"),
        "approved_pending_payment": ("Approved — investor payment required before units are issued", "investor_payment"),
        "awaiting_payout_setup": ("Approved — investor payout setup required", "payout_setup"),
        "pending_fund_transfer": ("Payment confirmed — operations completion required", "operations_completion"),
        "completed": ("Completed — units and account value have been updated", "none"),
        "failed": ("Provider processing failed — operations attention required", "operations_attention"),
        "rejected": ("Request rejected", "none"),
    }

    flow_list = []
    for f in flows:
        status_message, next_action = status_guidance.get(
            f.status, (f.status.replace("_", " ").title(), "none")
        )
        flow_list.append({
            "id": f.id,
            "investor_email": f.investor.email if f.investor else None,
            "investor_name": f.investor.full_name if f.investor else None,
            "flow_type": f.flow_type,
            "fund_id": f.fund_id,
            "fund_name": f.fund.name if f.fund else None,
            "amount": float(f.amount) if f.amount else 0,
            "paid_amount": float(f.paid_amount) if f.paid_amount is not None else None,
            "currency": f.currency,
            "status": f.status,
            "request_id": f.request_id,
            "requested_at": f.requested_at.isoformat() if f.requested_at else None,
            "processed_at": f.processed_at.isoformat() if f.processed_at else None,
            "payment_received_at": f.payment_received_at.isoformat() if f.payment_received_at else None,
            "processed_by_email": f.processed_by.email if f.processed_by else None,
            "processed_by_name": f.processed_by.full_name if f.processed_by else None,
            "notes": f.notes,
            "status_message": status_message,
            "next_action": next_action,
            "provider": f.provider,
            "provider_reference": f.provider_reference,
            # Provider URLs contain flow-specific identifiers. Only the owner
            # receives the link; admins/operations never need it in this list.
            "payment_url": f.payment_url if not owns_read_all else None,
            "paynow_qr_data_url": (
                paynow_qr_data_url(f.payment_url)
                if not owns_read_all and f.provider == "paynow_demo" and f.payment_url
                and f.status == "awaiting_investor_payment" else None
            ),
        })

    return StandardResponse(
        success=True,
        data={
            "flows": flow_list,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        },
        error=None,
    )


# ──────────────────────────────────────────────
# Investment Transactions (Admin read)
# ──────────────────────────────────────────────

@router.get("/transactions", response_model=StandardResponse)
def list_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query("", max_length=100),
    trade_type: str = Query("", max_length=20),
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["readTransactions"])),
    db: Session = Depends(get_db),
):
    query = db.query(InvestmentTransaction).outerjoin(Investor, InvestmentTransaction.investor_id == Investor.id)

    if search:
        term = f"%{search}%"
        query = query.filter(
            or_(
                InvestmentTransaction.ticket.ilike(term),
                InvestmentTransaction.symbol.ilike(term),
                Investor.email.ilike(term),
                Investor.full_name.ilike(term),
            )
        )

    if trade_type:
        query = query.filter(InvestmentTransaction.trade_type == trade_type)

    total = query.count()

    txns = (
        query
        .order_by(InvestmentTransaction.trade_time.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    txn_list = []
    for t in txns:
        txn_list.append({
            "id": t.id,
            "ticket": t.ticket,
            "investor_email": t.investor.email if t.investor else None,
            "investor_name": t.investor.full_name if t.investor else None,
            "trade_type": t.trade_type,
            "symbol": t.symbol,
            "volume": float(t.volume) if t.volume else 0,
            "price": float(t.price) if t.price else 0,
            "profit": float(t.profit) if t.profit else 0,
            "commission": float(t.commission) if t.commission else 0,
            "swap": float(t.swap) if t.swap else 0,
            "fee": float(t.fee) if t.fee else 0,
            "net_pnl": float(t.net_pnl) if t.net_pnl else 0,
            "trade_time": t.trade_time.isoformat() if t.trade_time else None,
        })

    return StandardResponse(
        success=True,
        data={
            "transactions": txn_list,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        },
        error=None,
    )


# ──────────────────────────────────────────────
# Orders (Admin read)
# ──────────────────────────────────────────────

@router.get("/orders", response_model=StandardResponse)
def list_all_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["readOrders"])),
    db: Session = Depends(get_db),
):
    query = db.query(Order).options(joinedload(Order.investor))

    total = query.count()

    orders = (
        query
        .order_by(Order.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    order_list = []
    for o in orders:
        inv = o.investor
        order_list.append({
            "id": o.id,
            "alpaca_order_id": o.alpaca_order_id,
            "symbol": o.symbol,
            "side": o.side,
            "amount": float(o.amount),
            "filled_qty": float(o.filled_qty) if o.filled_qty else None,
            "filled_price": float(o.filled_price) if o.filled_price else None,
            "status": o.status,
            "investor_name": inv.full_name if inv else None,
            "investor_email": inv.email if inv else None,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        })

    return StandardResponse(
        success=True,
        data={
            "orders": order_list,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        },
        error=None,
    )


# ──────────────────────────────────────────────
# Reconciliation
# ──────────────────────────────────────────────

@router.get("/reconcile", response_model=StandardResponse)
def reconcile(
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["readSystemStats"])),
    db: Session = Depends(get_db),
):
    discrepancies = []

    db_orders = db.query(Order).all()
    db_order_ids = set(o.alpaca_order_id for o in db_orders if o.alpaca_order_id)

    try:
        alpaca_orders = get_orders(status="all", limit=100)
        alpaca_order_ids = set(o.get("id") for o in alpaca_orders if o.get("id"))

        in_db_not_alpaca = db_order_ids - alpaca_order_ids
        in_alpaca_not_db = alpaca_order_ids - db_order_ids

        if in_db_not_alpaca:
            discrepancies.append({
                "source": "db-only",
                "type": "orders",
                "count": len(in_db_not_alpaca),
                "ids": list(in_db_not_alpaca)[:10],
                "detail": "Orders exist in DB but not found in Alpaca",
            })

        if in_alpaca_not_db:
            discrepancies.append({
                "source": "alpaca-only",
                "type": "orders",
                "count": len(in_alpaca_not_db),
                "ids": list(in_alpaca_not_db)[:10],
                "detail": "Orders exist in Alpaca but not recorded in DB",
            })
    except Exception as e:
        discrepancies.append({
            "source": "error",
            "type": "alpaca",
            "detail": f"Failed to fetch Alpaca orders: {str(e)}",
        })

    try:
        if settings.STRIPE_SECRET_KEY:
            stripe_sessions = stripe.checkout.Session.list(limit=50)
            stripe_ids = set()
            for s in stripe_sessions.auto_paging_iter():
                stripe_ids.add(s.id)

            fund_flows = db.query(FundFlow).all()
            db_stripe_refs = set()
            for f in fund_flows:
                if f.provider == "stripe_checkout" and f.provider_reference:
                    db_stripe_refs.add(f.provider_reference)

            in_db_not_stripe = db_stripe_refs - stripe_ids
            in_stripe_not_db = stripe_ids - db_stripe_refs

            if in_db_not_stripe:
                discrepancies.append({
                    "source": "db-only",
                    "type": "stripe-sessions",
                    "count": len(in_db_not_stripe),
                    "ids": list(in_db_not_stripe)[:10],
                    "detail": "Stripe session referenced in DB but not found in Stripe",
                })

            if in_stripe_not_db:
                discrepancies.append({
                    "source": "stripe-only",
                    "type": "stripe-sessions",
                    "count": len(in_stripe_not_db),
                    "ids": list(in_stripe_not_db)[:10],
                    "detail": "Stripe sessions exist but not recorded in DB fund flows",
                })
    except Exception as e:
        discrepancies.append({
            "source": "error",
            "type": "stripe",
            "detail": f"Failed to fetch Stripe sessions: {str(e)}",
        })

    is_healthy = len([d for d in discrepancies if d.get("source") != "error"]) == 0

    return StandardResponse(
        success=True,
        data={
            "healthy": is_healthy,
            "discrepancies": discrepancies,
            "total_orders_db": len(db_order_ids),
        },
        error=None,
    )


# ──────────────────────────────────────────────
# User Management (Admin only)
# ──────────────────────────────────────────────

@router.get("/users", response_model=StandardResponse)
def list_users(
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["readUsers"])),
    db: Session = Depends(get_db),
):
    users = db.query(User).order_by(User.created_at.desc()).all()

    user_list = []
    for u in users:
        user_list.append({
            "id": u.id,
            "user_id": str(u.user_id),
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role.name if u.role else "unknown",
            "role_id": u.role_id,
            "is_active": u.is_active,
            "mfa_enabled": u.mfa_enabled,
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        })

    roles = db.query(Role).all()
    role_list = [{"id": r.id, "name": r.name} for r in roles]

    return StandardResponse(
        success=True,
        data={"users": user_list, "roles": role_list},
        error=None,
    )


@router.put("/users/{user_id}", response_model=StandardResponse)
def update_user(
    user_id: int,
    email: str = Body(None),
    full_name: str = Body(None),
    role_id: int = Body(None),
    new_password: str = Body(None),
    is_active: bool = Body(None),
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["writeUsers"])),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    before = {
        "email": user.email,
        "full_name": user.full_name,
        "role_id": user.role_id,
        "is_active": user.is_active,
    }

    if email is not None and email != user.email:
        existing = db.query(User).filter(User.email == email).first()
        if existing and existing.id != user.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already in use")
        user.email = email

    if full_name is not None:
        user.full_name = full_name

    if role_id is not None:
        role = db.query(Role).filter(Role.id == role_id).first()
        if not role:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role_id")
        user.role_id = role_id

    if new_password is not None:
        user.hashed_password = hash_password(new_password)

    if is_active is not None:
        user.is_active = is_active

    db.commit()
    db.refresh(user)

    after = {
        "email": user.email,
        "full_name": user.full_name,
        "role_id": user.role_id,
        "is_active": user.is_active,
    }

    action = AUDIT_ACTIONS["USER_DEACTIVATED"] if (before.get("is_active") and not user.is_active) else AUDIT_ACTIONS["USER_UPDATED"]
    log_event(
        db=db,
        user_id=current_user.id,
        action=action,
        details=f"User {user.email} updated by {current_user.email}",
        entity_type="user",
        entity_id=user.id,
        changes={"before": before, "after": after},
        status="success",
    )

    return StandardResponse(
        success=True,
        data={
            "id": user.id,
            "user_id": str(user.user_id),
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.name if user.role else "unknown",
            "is_active": user.is_active,
        },
        error=None,
    )


@router.get("/investors", response_model=StandardResponse)
def list_all_investors(
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["readUsers"])),
    db: Session = Depends(get_db),
):
    investors = db.query(Investor).order_by(Investor.onboarded_at.desc()).all()
    managers = db.query(Manager).all()
    manager_map = {m.id: {"id": m.id, "full_name": m.full_name, "email": m.email} for m in managers}

    inv_list = []
    for inv in investors:
        mgr = manager_map.get(inv.manager_id) if inv.manager_id else None
        inv_list.append({
            "id": inv.id,
            "email": inv.email,
            "full_name": inv.full_name,
            "is_active": inv.is_active,
            "manager_id": inv.manager_id,
            "manager_name": mgr["full_name"] if mgr else None,
            "manager_email": mgr["email"] if mgr else None,
            "initial_capital": float(inv.initial_capital) if inv.initial_capital else 0,
            "onboarded_at": inv.onboarded_at.isoformat() if inv.onboarded_at else None,
        })

    return StandardResponse(
        success=True,
        data={
            "investors": inv_list,
            "managers": [{"id": m.id, "full_name": m.full_name, "email": m.email} for m in managers],
        },
        error=None,
    )


@router.put("/investors/{investor_id}", response_model=StandardResponse)
def update_investor_manager(
    investor_id: int,
    manager_id: int = Query(None),
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["writeUsers"])),
    db: Session = Depends(get_db),
):
    investor = db.query(Investor).filter(Investor.id == investor_id).first()
    if not investor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investor not found")

    if manager_id is not None:
        if manager_id > 0:
            manager = db.query(Manager).filter(Manager.id == manager_id).first()
            if not manager:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Manager not found")
            investor.manager_id = manager_id
        else:
            investor.manager_id = None

    db.commit()
    db.refresh(investor)

    log_event(
        db=db,
        user_id=current_user.id,
        action=AUDIT_ACTIONS["USER_UPDATED"],
        details=f"Investor {investor.email} manager updated to {investor.manager_id}",
        entity_type="investor",
        entity_id=investor.id,
        status="success",
    )

    return StandardResponse(
        success=True,
        data={
            "id": investor.id,
            "email": investor.email,
            "full_name": investor.full_name,
            "manager_id": investor.manager_id,
        },
        error=None,
    )


# ──────────────────────────────────────────────
# Fund Flow Actions (Operations)
# ──────────────────────────────────────────────

def _get_flow(db: Session, flow_id: int) -> FundFlow:
    flow = db.query(FundFlow).filter(FundFlow.id == flow_id).with_for_update().first()
    if not flow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fund flow not found")
    return flow


def _set_processor(flow: FundFlow, user: User) -> None:
    flow.processed_by_user_id = user.id
    flow.processed_at = datetime.now(timezone.utc)


def _settle_flow(db: Session, flow: FundFlow, provider_reference: str | None = None) -> bool:
    """Compatibility wrapper around the authoritative unit-accounting service."""
    try:
        return settle_fund_flow(db, flow, provider_reference).applied
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _stripe_object_dict(value) -> dict:
    """Normalize StripeObject payloads without relying on Mapping methods."""
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, dict):
        return value
    raise ValueError("Stripe event object was not a dictionary")


@router.post("/fund-flows/{flow_id}/approve", response_model=StandardResponse)
def approve_fund_flow(
    flow_id: int,
    body: FundFlowActionRequest = FundFlowActionRequest(),
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["approveFundFlows"])),
    db: Session = Depends(get_db),
):
    flow = _get_flow(db, flow_id)

    if flow.status != "pending_ops_team":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve a flow with status '{flow.status}'. Must be 'pending_ops_team'.",
        )

    _set_processor(flow, current_user)
    if body.notes:
        flow.notes = f"{flow.notes or ''}\n[Ops: {body.notes}]".strip()

    checkout_url = None
    provider_mode = settings.FUND_FLOW_PROVIDER.strip().lower()
    if provider_mode not in {"paynow_demo", "manual", "stripe"}:
        raise HTTPException(status_code=500, detail="FUND_FLOW_PROVIDER must be 'paynow_demo', 'manual', or 'stripe'")

    if flow.flow_type not in {"deposit", "withdrawal"}:
        raise HTTPException(status_code=400, detail=f"Unsupported fund flow type '{flow.flow_type}'")

    if provider_mode == "paynow_demo" and flow.flow_type == "deposit":
        raise HTTPException(
            status_code=400,
            detail="Demo PayNow subscriptions must use Verify & Complete after the fixed payment is recorded.",
        )
    if provider_mode in {"paynow_demo", "manual"}:
        flow.provider = "manual_transfer"
        flow.payment_url = None
        flow.status = "pending_fund_transfer"
    elif flow.flow_type == "deposit":
        account = flow.investment_account

        try:
            session = stripe.checkout.Session.create(
                line_items=[{
                    "price_data": {
                        "currency": settings.STRIPE_CONNECT_CURRENCY,
                        "product_data": {
                            "name": f"FundInv Deposit — {account.account_name}" if account else "FundInv Deposit",
                        },
                        "unit_amount": int(float(flow.amount) * 100),
                    },
                    "quantity": 1,
                }],
                mode="payment",
                payment_method_types=["card", "paynow"],
                success_url=settings.STRIPE_SUCCESS_URL + "&session_id={CHECKOUT_SESSION_ID}",
                cancel_url=settings.STRIPE_CANCEL_URL,
                metadata={
                    "fund_flow_id": str(flow.id),
                    "investor_id": str(flow.investor_id),
                    "investment_account_id": str(flow.investment_account_id),
                    "fund_id": str(flow.fund_id),
                    "fund_flow_request_id": flow.request_id,
                },
            )
            checkout_url = session.url
            flow.provider = "stripe_checkout"
            flow.provider_reference = session.id
            flow.payment_url = checkout_url
            flow.status = "approved_pending_payment"
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create payment session: {str(e)}",
            )
    else:
        flow.provider = "stripe_connect"
        connect_id = flow.investor.stripe_connect_account_id if flow.investor else None
        if not connect_id:
            account_obj = stripe.Account.create(
                type="express",
                email=flow.investor.email,
                capabilities={"transfers": {"requested": True}},
                metadata={"investor_id": str(flow.investor_id)},
            )
            connect_id = account_obj.id
            flow.investor.stripe_connect_account_id = connect_id
        account_link = stripe.AccountLink.create(
            account=connect_id,
            refresh_url=settings.STRIPE_CONNECT_REFRESH_URL,
            return_url=settings.STRIPE_CONNECT_RETURN_URL,
            type="account_onboarding",
        )
        flow.payment_url = account_link.url
        flow.status = "awaiting_payout_setup"

    audit_action = AUDIT_ACTIONS["FUND_FLOW_DEPOSIT_APPROVED"] if flow.flow_type == "deposit" else AUDIT_ACTIONS["FUND_FLOW_WITHDRAWAL_APPROVED"]
    log_event(
        db=db,
        user_id=current_user.id,
        action=audit_action,
        details=f"Fund flow {flow.id} ({flow.flow_type}) approved",
        entity_type="fund_flow",
        entity_id=flow.id,
        changes={"amount": float(flow.amount), "status": flow.status, "checkout_url": checkout_url},
        status="success",
        commit=False,
    )
    db.commit()
    db.refresh(flow)

    try:
        send_fund_flow_approved_email(
            to_email=flow.investor.email,
            investor_name=flow.investor.full_name,
            flow_type=flow.flow_type,
            amount=float(flow.amount),
            request_id=flow.request_id,
            account_name=flow.investment_account.account_name if flow.investment_account else None,
            checkout_url=checkout_url or flow.payment_url,
        )
    except Exception:
        logger.exception("Approved-flow email failed for flow %s", flow.id)

    return StandardResponse(
        success=True,
        data={
            "id": flow.id,
            "status": flow.status,
            "checkout_url": checkout_url,
            "message": (
                "Approved; Operations must verify the external transfer before completing settlement."
                if flow.provider == "manual_transfer"
                else "Approved; investor payment is still required before units are issued."
                if checkout_url
                else "Approved; investor payout setup is still required."
            ),
        },
        error=None,
    )


@router.post("/fund-flows/{flow_id}/verify-complete", response_model=StandardResponse)
def verify_paynow_and_complete(
    flow_id: int,
    body: FundFlowActionRequest = FundFlowActionRequest(),
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["completeFundFlows"])),
    db: Session = Depends(get_db),
):
    """Verify an exact fixed-amount demo PayNow receipt and issue units once."""
    flow = _get_flow(db, flow_id)
    if flow.provider != "paynow_demo" or flow.flow_type != "deposit":
        raise HTTPException(status_code=400, detail="This action is only for demo PayNow subscriptions")
    if flow.status == "completed":
        return StandardResponse(
            success=True,
            data={
                "id": flow.id,
                "status": flow.status,
                "requested_amount": float(flow.amount),
                "paid_amount": float(flow.paid_amount) if flow.paid_amount is not None else None,
                "message": "Subscription was already verified and completed.",
            },
            error=None,
        )
    if flow.status != "pending_ops_team":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot verify a flow with status '{flow.status}'. Payment must be recorded first.",
        )
    if flow.paid_amount is None or flow.payment_received_at is None:
        raise HTTPException(status_code=409, detail="No demo PayNow receipt has been recorded")
    if flow.paid_amount != flow.amount:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Payment mismatch: requested ${float(flow.amount):,.2f}, "
                f"received ${float(flow.paid_amount):,.2f}. Settlement is blocked."
            ),
        )

    _set_processor(flow, current_user)
    if body.notes:
        flow.notes = f"{flow.notes or ''}\n[Ops: {body.notes}]".strip()
    _settle_flow(db, flow, provider_reference=flow.provider_reference)
    log_event(
        db=db,
        user_id=current_user.id,
        action=AUDIT_ACTIONS["FUND_FLOW_DEPOSIT_COMPLETED"],
        details=f"Demo PayNow subscription {flow.id} verified and completed",
        entity_type="fund_flow",
        entity_id=flow.id,
        changes={
            "requested_amount": float(flow.amount),
            "paid_amount": float(flow.paid_amount),
            "provider_reference": flow.provider_reference,
            "payment_received_at": flow.payment_received_at.isoformat(),
            "status": "completed",
        },
        status="success",
        commit=False,
    )
    db.commit()
    db.refresh(flow)

    try:
        send_fund_flow_completed_email(
            to_email=flow.investor.email,
            investor_name=flow.investor.full_name,
            flow_type=flow.flow_type,
            amount=float(flow.amount),
            request_id=flow.request_id,
        )
    except Exception:
        logger.exception("Completed-flow email failed for flow %s", flow.id)

    return StandardResponse(
        success=True,
        data={
            "id": flow.id,
            "status": flow.status,
            "requested_amount": float(flow.amount),
            "paid_amount": float(flow.paid_amount),
            "message": "Payment matched the request; subscription completed and units issued.",
        },
        error=None,
    )


@router.post("/fund-flows/{flow_id}/complete", response_model=StandardResponse)
def complete_fund_flow(
    flow_id: int,
    body: FundFlowActionRequest = FundFlowActionRequest(),
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["completeFundFlows"])),
    db: Session = Depends(get_db),
):
    flow = _get_flow(db, flow_id)

    if flow.status != "pending_fund_transfer":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot complete a flow with status '{flow.status}'. Must be 'pending_fund_transfer'.",
        )

    if flow.provider == "stripe_connect":
        raise HTTPException(status_code=400, detail="Stripe payout completion is confirmed by webhook")

    _set_processor(flow, current_user)
    if body.notes:
        flow.notes = f"{flow.notes or ''}\n[Ops: {body.notes}]".strip()

    _settle_flow(db, flow)

    audit_action = AUDIT_ACTIONS["FUND_FLOW_DEPOSIT_COMPLETED"] if flow.flow_type == "deposit" else AUDIT_ACTIONS["FUND_FLOW_WITHDRAWAL_COMPLETED"]
    log_event(
        db=db,
        user_id=current_user.id,
        action=audit_action,
        details=f"Fund flow {flow.id} ({flow.flow_type}) completed",
        entity_type="fund_flow",
        entity_id=flow.id,
        changes={"amount": float(flow.amount), "status": "completed"},
        status="success",
        commit=False,
    )
    db.commit()
    db.refresh(flow)

    try:
        send_fund_flow_completed_email(
            to_email=flow.investor.email,
            investor_name=flow.investor.full_name,
            flow_type=flow.flow_type,
            amount=float(flow.amount),
            request_id=flow.request_id,
        )
    except Exception:
        logger.exception("Completed-flow email failed for flow %s", flow.id)

    return StandardResponse(
        success=True,
        data={
            "id": flow.id,
            "status": flow.status,
            "message": "Fund flow completed successfully.",
        },
        error=None,
    )


@router.post("/fund-flows/{flow_id}/reject", response_model=StandardResponse)
def reject_fund_flow(
    flow_id: int,
    body: FundFlowActionRequest = FundFlowActionRequest(),
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["rejectFundFlows"])),
    db: Session = Depends(get_db),
):
    flow = _get_flow(db, flow_id)

    if flow.status not in ("awaiting_investor_payment", "pending_ops_team", "approved_pending_payment", "awaiting_payout_setup", "pending_fund_transfer", "pending"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject a flow with status '{flow.status}'. Must be pending.",
        )

    _set_processor(flow, current_user)
    flow.status = "rejected"
    if body.notes:
        flow.notes = f"{flow.notes or ''}\n[Ops: {body.notes}]".strip()

    audit_action = AUDIT_ACTIONS["FUND_FLOW_DEPOSIT_REJECTED"] if flow.flow_type == "deposit" else AUDIT_ACTIONS["FUND_FLOW_WITHDRAWAL_REJECTED"]
    log_event(
        db=db,
        user_id=current_user.id,
        action=audit_action,
        details=f"Fund flow {flow.id} ({flow.flow_type}) rejected",
        entity_type="fund_flow",
        entity_id=flow.id,
        changes={"amount": float(flow.amount), "status": "rejected", "notes": body.notes},
        status="success",
        commit=False,
    )
    db.commit()
    db.refresh(flow)

    try:
        notes_for_email = None
        if body.notes:
            notes_for_email = body.notes
        elif flow.notes:
            notes_for_email = flow.notes.replace("[Ops: ", "").replace("]", "")
        send_fund_flow_rejected_email(
            to_email=flow.investor.email,
            investor_name=flow.investor.full_name,
            flow_type=flow.flow_type,
            amount=float(flow.amount),
            request_id=flow.request_id,
            notes=notes_for_email,
        )
    except Exception:
        logger.exception("Rejected-flow email failed for flow %s", flow.id)

    return StandardResponse(
        success=True,
        data={
            "id": flow.id,
            "status": flow.status,
            "message": "Fund flow rejected.",
        },
        error=None,
    )


# ──────────────────────────────────────────────
# Stripe Webhook
# ──────────────────────────────────────────────

def _start_connect_payout(flow: FundFlow) -> str:
    connect_id = flow.investor.stripe_connect_account_id if flow.investor else None
    if not connect_id:
        raise HTTPException(status_code=400, detail="Investor has not completed payout setup")
    payout = stripe.Payout.create(
        amount=int(float(flow.amount) * 100),
        currency=settings.STRIPE_CONNECT_CURRENCY,
        metadata={"fund_flow_id": str(flow.id), "request_id": flow.request_id},
        stripe_account=connect_id,
    )
    return payout.id


@router.post("/fund-flows/{flow_id}/start-payout", response_model=StandardResponse)
def start_payout(
    flow_id: int,
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["approveFundFlows"])),
    db: Session = Depends(get_db),
):
    flow = _get_flow(db, flow_id)
    if flow.flow_type != "withdrawal" or flow.status not in ("awaiting_payout_setup", "pending_fund_transfer", "failed"):
        raise HTTPException(status_code=400, detail="Withdrawal is not ready for payout")
    if flow.provider_reference and flow.status == "pending_fund_transfer":
        raise HTTPException(status_code=400, detail="Payout has already been submitted")
    try:
        payout_id = _start_connect_payout(flow)
    except stripe.error.StripeError as exc:
        flow.status = "failed"
        flow.failure_reason = str(exc)
        db.commit()
        raise HTTPException(status_code=502, detail="Payout provider rejected the withdrawal")
    flow.provider = "stripe_connect"
    flow.provider_reference = payout_id
    flow.status = "pending_fund_transfer"
    flow.failure_reason = None
    _set_processor(flow, current_user)
    db.commit()
    return StandardResponse(success=True, data={"id": flow.id, "status": flow.status, "provider_reference": payout_id}, error=None)

@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing stripe-signature header")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")

    system_user = get_system_user(db)

    if event["type"] == "checkout.session.completed":
        session_obj = _stripe_object_dict(event["data"]["object"])
        session_id = session_obj["id"]

        flow = db.query(FundFlow).filter(FundFlow.provider_reference == session_id).first()
        if flow and flow.status == "approved_pending_payment":
            expected_amount = int(float(flow.amount) * 100)
            if session_obj.get("amount_total") != expected_amount or session_obj.get("currency") != settings.STRIPE_CONNECT_CURRENCY:
                flow.status = "failed"
                flow.failure_reason = "Payment amount or currency did not match the approved flow"
                db.commit()
            else:
                _settle_flow(db, flow, session_id)
                db.commit()
                log_event(
                    db=db,
                    user_id=system_user.id if system_user else None,
                    action=AUDIT_ACTIONS["FUND_FLOW_DEPOSIT_COMPLETED"],
                    details=f"Stripe webhook: deposit completed for flow {flow.id}",
                    entity_type="fund_flow",
                    entity_id=flow.id,
                    changes={"amount": float(flow.amount), "status": "completed", "stripe_session_id": session_id},
                    status="success",
                )

    elif event["type"] == "checkout.session.expired":
        session_obj = _stripe_object_dict(event["data"]["object"])
        session_id = session_obj["id"]

        now = datetime.now(timezone.utc)
        db.query(FundFlow).filter(
            FundFlow.provider_reference == session_id,
            FundFlow.status == "approved_pending_payment",
        ).update({"status": "failed", "processed_at": now, "failure_reason": "Checkout session expired"})
        db.commit()

    elif event["type"] == "account.updated":
        account_obj = _stripe_object_dict(event["data"]["object"])
        investor = db.query(Investor).filter(Investor.stripe_connect_account_id == account_obj.get("id")).first()
        if investor and account_obj.get("payouts_enabled"):
            pending = db.query(FundFlow).filter(
                FundFlow.investor_id == investor.id,
                FundFlow.flow_type == "withdrawal",
                FundFlow.status == "awaiting_payout_setup",
            ).order_by(FundFlow.requested_at).first()
            if pending:
                try:
                    payout_id = _start_connect_payout(pending)
                    pending.provider_reference = payout_id
                    pending.provider = "stripe_connect"
                    pending.status = "pending_fund_transfer"
                    db.commit()
                except stripe.error.StripeError as exc:
                    pending.status = "failed"
                    pending.failure_reason = str(exc)
                    db.commit()

    elif event["type"] in ("payout.paid", "payout.failed"):
        payout = _stripe_object_dict(event["data"]["object"])
        flow_id = (payout.get("metadata") or {}).get("fund_flow_id")
        flow = db.query(FundFlow).filter(FundFlow.id == int(flow_id)).first() if flow_id else db.query(FundFlow).filter(FundFlow.provider_reference == payout.get("id")).first()
        if flow and flow.status == "pending_fund_transfer":
            if event["type"] == "payout.paid":
                _settle_flow(db, flow, payout.get("id"))
                log_event(db=db, user_id=system_user.id if system_user else None,
                          action=AUDIT_ACTIONS["FUND_FLOW_WITHDRAWAL_COMPLETED"],
                          details=f"Stripe payout completed for flow {flow.id}", entity_type="fund_flow",
                          entity_id=flow.id, status="success")
            else:
                flow.status = "failed"
                flow.failure_reason = payout.get("failure_message") or "Stripe payout failed"
                flow.processed_at = datetime.now(timezone.utc)
            db.commit()

    return {"received": True}
