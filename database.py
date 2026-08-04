"""
Shared database setup — imported by models.py and every router in every section.
Do not duplicate this file per-section; there is exactly one engine for the app.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Copy .env.example to .env and fill in your "
        "Supabase connection string (Project Settings -> Database -> Connection string -> URI)."
    )

# We use the psycopg3 driver (better wheel support on newer Python versions than
# psycopg2). SQLAlchemy needs the driver named explicitly in the URL scheme, but
# connection strings are often handed out as "postgresql://" or sometimes just
# "postgres://" — rewrite either form rather than asking everyone to edit their .env.
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)

# Supabase's pooled connection string (port 6543, pgbouncer / transaction mode)
# does not support server-side prepared statements the way SQLAlchemy uses them
# by default. This is handled below via prepare_threshold=None — no special
# query parameter needed on the URL itself.
connect_args = {}
if "sslmode" not in DATABASE_URL:
    connect_args["sslmode"] = "require"

# Disable psycopg3's automatic server-side prepared statements. When connecting
# through Supabase's transaction-mode pooler (pgbouncer), each query can land on
# a different underlying Postgres connection, so a prepared statement created on
# one physical connection may not exist on the next — causing errors like the
# introspection queries SQLAlchemy runs on startup to fail. Setting
# prepare_threshold=None turns prepared statements off entirely, which is safe
# for both pooled and direct connections.
connect_args["prepare_threshold"] = None

engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency — use this in route signatures: db: Session = Depends(get_db)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()