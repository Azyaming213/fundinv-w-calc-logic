from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import auth_routers, funds_routers, portfolio_routers, admin_routers, articles_routers, trading_routers, manager_routers, feedback_routers
from jobs.scheduler import start_scheduler, stop_scheduler
from database import SessionLocal
from models import Role, RoleClaim
import appconstants as AppConstants


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
    start_scheduler()
    try:
        sync_role_claims()
    except Exception:
        pass
    yield
    stop_scheduler()


app = FastAPI(
    title="FundInv Solo API",
    description="FundInv API Server",
    version="0.2.2",
    ports={"http": 8000},
    lifespan=lifespan,
)

# Replace with your frontend URLs in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
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
