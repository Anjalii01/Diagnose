"""
Database connection setup.

Reads DATABASE_URL from config.py (which reads it from the environment / .env).
Defaults to a local SQLite file so the project runs with zero external setup.

To switch to PostgreSQL / Supabase, set DATABASE_URL in your .env file —
nothing else in the project needs to change.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from config import settings

DATABASE_URL = settings.DATABASE_URL

# SQLite needs this extra connect arg; Postgres does not.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session and closes it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
