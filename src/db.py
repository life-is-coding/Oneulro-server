from urllib.parse import quote_plus

from sqlalchemy import create_engine

from src.core.config import get_settings

settings = get_settings()

DB_HOST = settings.DB_HOST
DB_NAME = settings.DB_NAME
DB_USER = settings.DB_USER
DB_PASSWORD = quote_plus(settings.DB_PASSWORD)
DB_PORT = settings.DB_PORT

if DB_HOST.startswith("/cloudsql/"):
    _DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@/{DB_NAME}?host={DB_HOST}"
else:
    _DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

try:
    engine = create_engine(_DATABASE_URL, pool_pre_ping=True)
except Exception:
    engine = None
