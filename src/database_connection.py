"""
Database connection helper.
Reads credentials from a .env file (never committed to git) so
no password lives in source code.
"""

import os
from sqlalchemy import create_engine
from dotenv import load_dotenv
from urllib.parse import quote_plus

# Load variables from .env at project root into environment
_ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
load_dotenv(_ENV_PATH)

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "healthcare_etl")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")


def get_engine():
    """Create and return a SQLAlchemy engine for the healthcare_etl database."""
    if not DB_PASSWORD:
        raise RuntimeError(
            "DB_PASSWORD not set. Create a .env file at the project root "
            "with DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD."
        )
    # URL-encode user/password in case they contain special characters
    # (@, :, /, #, % etc.) that would otherwise break the connection string.
    safe_user = quote_plus(DB_USER)
    safe_password = quote_plus(DB_PASSWORD)
    url = f"postgresql+psycopg2://{safe_user}:{safe_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    return create_engine(
        url,
        pool_size=5,
        max_overflow=5,
        pool_timeout=10,      # fail fast instead of hanging indefinitely
        pool_pre_ping=True,   # detect and discard dead connections automatically
    )


if __name__ == "__main__":
    from sqlalchemy import text

    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version();"))
        print("Connected successfully:")
        print(result.fetchone()[0])