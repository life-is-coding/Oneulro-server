import os
from urllib.parse import quote_plus

from sqlalchemy import create_engine

DB_HOST = os.getenv("DB_HOST", "postgres")
DB_NAME = os.getenv("DB_NAME", "oneulro")
DB_USER = os.getenv("DB_USER", "oneulro")
DB_PASSWORD = quote_plus(os.getenv("DB_PASSWORD", ""))
DB_PORT = os.getenv("DB_PORT", "5432")

if DB_HOST.startswith("/cloudsql/"):
    _DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@/{DB_NAME}?host={DB_HOST}"
else:
    _DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

try:
    engine = create_engine(_DATABASE_URL, pool_pre_ping=True)
except Exception:
    engine = None
