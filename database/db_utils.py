"""
Database Utility Functions for connection management, session handling, and pandas query helpers.
"""

import os
from pathlib import Path
from typing import Generator
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from database.schema import Base

# Determine absolute path to data/clinic.db
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "clinic.db"

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

# SQLAlchemy engine & session factory
DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"
engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db(reset: bool = False) -> None:
    """
    Creates tables if they don't exist. If reset is True, drops all tables first.
    """
    if reset:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def get_db_session() -> Generator[Session, None, None]:
    """
    Yields a SQLAlchemy database session and ensures clean closure.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def run_raw_query(sql_query: str, params: dict = None) -> pd.DataFrame:
    """
    Executes a raw SQL SELECT query using SQLAlchemy engine and returns a pandas DataFrame.
    """
    with engine.connect() as conn:
        df = pd.read_sql_query(text(sql_query), conn, params=params)
    return df
