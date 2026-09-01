from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .core.config import get_settings

url = get_settings().database_url
engine = create_engine(
    url,
    connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
    pool_pre_ping=True,
    # Neon can close idle pooled connections; recycling prevents stale workers.
    pool_recycle=300 if not url.startswith("sqlite") else -1,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
class Base(DeclarativeBase): pass
def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()
