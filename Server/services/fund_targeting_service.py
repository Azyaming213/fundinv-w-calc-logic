"""Idempotent investor visibility for approved fund products."""

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from models import Fund, FundTargeting, Investor


INVESTOR_FUND_TYPES = ("etf", "bond", "managed", "mutual_fund", "hedge_fund")


def expose_fund_to_active_investors(db: Session, fund_id: int) -> tuple[int, int]:
    """Create missing visibility rows without overriding an explicit opt-out.

    Returns ``(created_count, eligible_count)``. The database unique constraint
    makes this safe when an approval request is retried or processed concurrently.
    """
    investor_ids = [
        row[0]
        for row in db.query(Investor.id).filter(Investor.is_active.is_(True)).all()
    ]
    if not investor_ids:
        return 0, 0

    statement = insert(FundTargeting).values([
        {
            "investor_id": investor_id,
            "fund_id": fund_id,
            "is_visible": True,
            "risk_tolerance": "balanced",
        }
        for investor_id in investor_ids
    ]).on_conflict_do_nothing(
        constraint="uq_fund_targeting_investor_fund",
    )
    result = db.execute(statement)
    return max(0, result.rowcount or 0), len(investor_ids)


def expose_active_funds_to_investor(db: Session, investor_id: int) -> tuple[int, int]:
    """Give a newly active investor access to all approved fund products."""
    fund_ids = [
        row[0]
        for row in db.query(Fund.id).filter(
            Fund.is_active.is_(True),
            Fund.review_status == "approved",
            Fund.fund_type.in_(INVESTOR_FUND_TYPES),
        ).all()
    ]
    if not fund_ids:
        return 0, 0

    statement = insert(FundTargeting).values([
        {
            "investor_id": investor_id,
            "fund_id": fund_id,
            "is_visible": True,
            "risk_tolerance": "balanced",
        }
        for fund_id in fund_ids
    ]).on_conflict_do_nothing(
        constraint="uq_fund_targeting_investor_fund",
    )
    result = db.execute(statement)
    return max(0, result.rowcount or 0), len(fund_ids)
