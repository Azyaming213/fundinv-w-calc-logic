import sys
from pathlib import Path

from alembic.config import Config
from alembic import command

from config import settings


def run_pending_migrations():
    if not getattr(settings, "AUTO_MIGRATE", "").lower() == "true":
        print("[MIGRATION] AUTO_MIGRATE not enabled, skipping")
        return

    try:
        alembic_cfg_path = str(Path(__file__).resolve().parent.parent / "alembic.ini")
        alembic_cfg = Config(alembic_cfg_path)
        alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
        command.upgrade(alembic_cfg, "head")
        print("[MIGRATION] Database migrations applied successfully")
    except Exception as e:
        print(f"[MIGRATION] Error running migrations: {e}")
