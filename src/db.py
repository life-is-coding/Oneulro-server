import os
from urllib.parse import quote_plus

from sqlalchemy import create_engine

DB_HOST = os.getenv("DB_HOST", "postgres")
DB_NAME = os.getenv("DB_NAME", "oneulro")

_DATABASE_URL = "postgresql://{user}:{password}@{host}:{port}/{name}".format(
    user=os.getenv("DB_USER", "oneulro"),
    password=quote_plus(os.getenv("DB_PASSWORD", "")),
    host=DB_HOST,
    port=os.getenv("DB_PORT", "5432"),
    name=DB_NAME,
)

try:
    engine = create_engine(_DATABASE_URL, pool_pre_ping=True)
except Exception:
    engine = None
