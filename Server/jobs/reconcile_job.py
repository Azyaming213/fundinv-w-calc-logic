from sqlalchemy.orm import Session

from database import SessionLocal
from models import Order, FundFlow
from services.alpaca_service import get_orders
from config import settings
import stripe as stripe_lib


def run_daily_reconciliation():
    db: Session = SessionLocal()
    try:
        discrepancies = []

        db_orders = db.query(Order).all()
        db_order_ids = [o.alpaca_order_id for o in db_orders if o.alpaca_order_id]

        if db_order_ids:
            try:
                alpaca_orders = get_orders(status="all", limit=100)
                alpaca_order_ids = [o.get("id") for o in alpaca_orders if o.get("id")]
                missing = set(db_order_ids) - set(alpaca_order_ids)
                if missing:
                    discrepancies.append(f"orders-in-db-not-alpaca: {len(missing)}")
                extra = set(alpaca_order_ids) - set(db_order_ids)
                if extra:
                    discrepancies.append(f"orders-in-alpaca-not-db: {len(extra)}")
            except Exception as e:
                discrepancies.append(f"alpaca-error: {str(e)}")

        if settings.STRIPE_SECRET_KEY:
            try:
                stripe_lib.api_key = settings.STRIPE_SECRET_KEY
                flows = db.query(FundFlow).all()
                db_stripe = [f.provider_reference for f in flows if f.provider == "stripe_checkout" and f.provider_reference]
                if db_stripe:
                    sessions = stripe_lib.checkout.Session.list(limit=50)
                    stripe_ids = [s.id for s in sessions.auto_paging_iter()]
                    missing = set(db_stripe) - set(stripe_ids)
                    if missing:
                        discrepancies.append(f"stripe-sessions-missing-in-api: {len(missing)}")
            except Exception as e:
                discrepancies.append(f"stripe-error: {str(e)}")

        if discrepancies:
            print(f"[RECONCILE] Discrepancies found: {', '.join(discrepancies)}")
        else:
            print("[RECONCILE] All systems in sync")

    finally:
        db.close()
