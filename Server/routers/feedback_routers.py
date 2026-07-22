from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from dependencies import require_claim
from models import FeedbackTicket, User
from schemas.auth_schema import StandardResponse
from services.audit_service import log_event
import appconstants as AppConstants


router = APIRouter(prefix="/api/feedback", tags=["Feedback"])


class FeedbackCreateRequest(BaseModel):
    category: str = Field(default="general", max_length=50)
    subject: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1, max_length=5000)
    priority: str = Field(default="normal", max_length=20)


class FeedbackUpdateRequest(BaseModel):
    status: str | None = None
    response: str | None = Field(default=None, max_length=5000)
    assigned_to_user_id: int | None = None
    priority: str | None = None


def _serialize(ticket: FeedbackTicket) -> dict:
    return {
        "id": ticket.id,
        "user_id": ticket.user_id,
        "email": ticket.user.email if ticket.user else None,
        "category": ticket.category,
        "subject": ticket.subject,
        "message": ticket.message,
        "status": ticket.status,
        "priority": ticket.priority,
        "assigned_to_user_id": ticket.assigned_to_user_id,
        "response": ticket.response,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
        "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
    }


@router.post("", response_model=StandardResponse)
def create_feedback(
    body: FeedbackCreateRequest,
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["createFeedback"])),
    db: Session = Depends(get_db),
):
    ticket = FeedbackTicket(user_id=current_user.id, **body.model_dump())
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    log_event(db=db, user_id=current_user.id, action="feedback.created", details=ticket.subject,
              entity_type="feedback", entity_id=ticket.id, status="success")
    return StandardResponse(success=True, data=_serialize(ticket), error=None)


@router.get("/mine", response_model=StandardResponse)
def list_my_feedback(
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["readOwnFeedback"])),
    db: Session = Depends(get_db),
):
    tickets = db.query(FeedbackTicket).filter(FeedbackTicket.user_id == current_user.id).order_by(FeedbackTicket.created_at.desc()).all()
    return StandardResponse(success=True, data={"tickets": [_serialize(ticket) for ticket in tickets]}, error=None)


@router.get("", response_model=StandardResponse)
def list_feedback(
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["readFeedback"])),
    db: Session = Depends(get_db),
):
    tickets = db.query(FeedbackTicket).order_by(FeedbackTicket.created_at.desc()).all()
    return StandardResponse(success=True, data={"tickets": [_serialize(ticket) for ticket in tickets]}, error=None)


@router.patch("/{ticket_id}", response_model=StandardResponse)
def update_feedback(
    ticket_id: int,
    body: FeedbackUpdateRequest,
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["manageFeedback"])),
    db: Session = Depends(get_db),
):
    ticket = db.query(FeedbackTicket).filter(FeedbackTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Feedback ticket not found")
    changes = body.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(ticket, key, value)
    if body.status == "resolved":
        ticket.resolved_at = datetime.now(timezone.utc)
    elif body.status and body.status != "resolved":
        ticket.resolved_at = None
    db.commit()
    db.refresh(ticket)
    log_event(db=db, user_id=current_user.id, action="feedback.updated", details=ticket.subject,
              entity_type="feedback", entity_id=ticket.id, changes=changes, status="success")
    return StandardResponse(success=True, data=_serialize(ticket), error=None)
