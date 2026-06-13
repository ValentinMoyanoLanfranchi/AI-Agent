"""
database/session.py — Configuración de sesiones SQLAlchemy async y sync.
"""
import ssl

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from config import settings


def _is_remote(url: str) -> bool:
    """True si la DB no es local (ej: Supabase, RDS). Requiere SSL."""
    return not any(host in url for host in ("@db:", "@localhost", "@127.0.0.1"))


# Contexto SSL que cifra sin verificar la cadena: el pooler de Supabase
# presenta un certificado con CA propia, equivalente a sslmode=require.
_ssl_no_verify = ssl.create_default_context()
_ssl_no_verify.check_hostname = False
_ssl_no_verify.verify_mode = ssl.CERT_NONE

# Connect args específicos por driver cuando la DB es remota (Supabase exige SSL).
# statement_cache_size=0 hace que asyncpg sea compatible con el pooler de Supabase.
_async_connect_args = {}
_sync_connect_args = {}
if _is_remote(settings.database_url):
    _async_connect_args = {"ssl": _ssl_no_verify, "statement_cache_size": 0}
if _is_remote(settings.database_url_sync):
    _sync_connect_args = {"sslmode": "require"}


# ─── Async Engine (FastAPI) ───────────────────────────────────
async_engine = create_async_engine(
    settings.database_url,
    echo=settings.app_debug,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,
    connect_args=_async_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

# ─── Sync Engine (Celery / Alembic) ──────────────────────────
sync_engine = create_engine(
    settings.database_url_sync,
    echo=settings.app_debug,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    connect_args=_sync_connect_args,
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    """Base declarativa para todos los modelos SQLAlchemy."""
    pass


# ─── Dependency para FastAPI ──────────────────────────────────
async def get_db() -> AsyncSession:
    """Dependency de FastAPI que provee una sesión async de DB."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_sync_db():
    """Context manager para Celery tasks (sync)."""
    db = SyncSessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
