from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import auth_routers, funds_routers, portfolio_routers, admin_routers, articles_routers, trading_routers, manager_routers, feedback_routers
from jobs.scheduler import start_scheduler, stop_scheduler
from database import SessionLocal
from models import Role, RoleClaim
import appconstants as AppConstants
from config import settings


logger = logging.getLogger(__name__)


def sync_role_claims():
    """Ensure all claims defined in CLAIMS_BY_ROLE exist in the role_claims table."""
    db = SessionLocal()
    try:
        for role_name, claim_keys in AppConstants.CLAIMS_BY_ROLE.items():
            role = db.query(Role).filter(Role.name == role_name).first()
            if not role:
                continue
            for claim_key in claim_keys:
                existing = db.query(RoleClaim).filter(
                    RoleClaim.role_id == role.id,
                    RoleClaim.claim_key == claim_key,
                ).first()
                if not existing:
                    db.add(RoleClaim(role_id=role.id, claim_key=claim_key))
        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.ENVIRONMENT.lower() == "production" and settings.COOKIE_SECURE.lower() != "true":
        raise RuntimeError("COOKIE_SECURE must be true in production")
    scheduler_enabled = settings.ENABLE_SCHEDULER.lower() == "true"
    if scheduler_enabled:
        start_scheduler()
    try:
        sync_role_claims()
    except Exception:
        logger.exception("Role-claim synchronization failed")
        raise
    yield
    if scheduler_enabled:
        stop_scheduler()


app = FastAPI(
    title="FundInv Solo API",
    description="FundInv API Server",
    version="0.2.2",
    ports={"http": 8000},
    lifespan=lifespan,
)

allowed_origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/test", tags=["Health"])
def health_check():
    """Health check endpoint used by Docker, ALB, and bin/run.sh."""
    return {"status": "ok", "service": "fundinv-api", "version": "0.2.2"}


#Routes
app.include_router(auth_routers.router)
app.include_router(funds_routers.router)
app.include_router(portfolio_routers.router)
app.include_router(admin_routers.router)
app.include_router(articles_routers.router)
app.include_router(trading_routers.router)
app.include_router(manager_routers.router)
app.include_router(feedback_routers.router)
