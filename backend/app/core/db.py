"""Engine SQLAlchemy Core compartido."""
import sqlalchemy as sa
from app.core.config import get_settings

_engine: sa.Engine | None = None

def get_engine() -> sa.Engine:
    global _engine
    if _engine is None:
        _engine = sa.create_engine(get_settings().database_url, future=True, pool_pre_ping=True)
    return _engine


_ops_engine: sa.Engine | None = None

def get_ops_engine() -> sa.Engine:
    """Engine a la BD operacional ROBUSTEZ (schema ops), fuente del EBITDA Inspector. Solo lectura."""
    global _ops_engine
    if _ops_engine is None:
        url = get_settings().ops_database_url
        if not url:
            raise RuntimeError("OPS_DATABASE_URL no configurada (BD ROBUSTEZ/ops)")
        _ops_engine = sa.create_engine(url, future=True, pool_pre_ping=True)
    return _ops_engine
