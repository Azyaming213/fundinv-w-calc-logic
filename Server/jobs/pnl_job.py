"""Daily PNL snapshot job.

Runs after market close to:
  1. Process completed deposit/withdrawal flows for the day (Section 8.1 step 4).
  2. Snapshot each investor's holdings per fund (Section 8.1).
  3. Persist PortfolioHolding rows so /api/portfolio/chart-data returns data.
"""
from sqlalchemy.orm import Session

from database import SessionLocal
from services.pnl_service import process_fund_flows_for_day, snapshot_daily_holdings
from services.audit_service import get_system_user, log_event


def run_daily_pnl_snapshot():
    db: Session = SessionLocal()
    try:
        flows = process_fund_flows_for_day(db)
        inserted = snapshot_daily_holdings(db)

        system_user = get_system_user(db)
        log_event(
            db=db,
            user_id=system_user.id if system_user else None,
            action="pnl.daily_snapshot",
            details=f"Daily PNL snapshot: {inserted} holdings rows, {flows} flows processed",
            entity_type="system",
            entity_id=None,
            changes={"holdings_inserted": inserted, "flows_processed": flows},
            status="success",
        )
        print(f"[PNL] Daily snapshot complete: {inserted} holdings, {flows} flows")
    except Exception as e:
        print(f"[PNL] Daily snapshot failed: {e}")
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()
