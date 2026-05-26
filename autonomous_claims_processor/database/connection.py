"""
Database Configuration and Session Management
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/insurance_claims_db"
)

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,
    echo=os.getenv("APP_ENV", "development") == "development"
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for FastAPI to get database session.
    Ensures proper cleanup after request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database - create all tables.
    Run this once on application startup.
    """
    from .models import Claim, Policy, ClaimDocument, AuditLog, FraudRecord, Reserve
    
    Base.metadata.create_all(bind=engine)
    
    print("✅ Database initialized successfully")


def create_database():
    """
    Create the database if it doesn't exist (PostgreSQL specific).
    """
    from psycopg2 import connect
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    
    # Connect to default postgres database
    conn = connect(
        host=os.getenv("DATABASE_HOST", "localhost"),
        port=os.getenv("DATABASE_PORT", "5432"),
        user=os.getenv("DATABASE_USER", "postgres"),
        password=os.getenv("DATABASE_PASSWORD", "postgres")
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    
    cur = conn.cursor()
    
    # Check if database exists
    db_name = os.getenv("DATABASE_NAME", "insurance_claims_db")
    cur.execute(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'")
    
    if not cur.fetchone():
        cur.execute(f'CREATE DATABASE "{db_name}"')
        print(f"✅ Database '{db_name}' created successfully")
    else:
        print(f"ℹ️  Database '{db_name}' already exists")
    
    cur.close()
    conn.close()
