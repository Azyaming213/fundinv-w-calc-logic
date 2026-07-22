import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure the Server package can be imported
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from models import User
from services.auth_service import hash_password

# Use the same connection parameters as the Docker container (admin/admin)
engine = create_engine("postgresql://admin:admin@localhost:5432/fundinv")
Session = sessionmaker(bind=engine)

# All seeded users use "admin123" as password (see v0.2.0_dml.sql)
DEFAULT_PASSWORD = "admin123"

with Session() as db:
    users = db.query(User).all()
    for user in users:
        user.hashed_password = hash_password(DEFAULT_PASSWORD)
    db.commit()
    print(f"Re‑hashed {len(users)} user(s) with deterministic bcrypt salt.")
