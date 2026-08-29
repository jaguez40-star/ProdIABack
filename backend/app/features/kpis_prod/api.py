from fastapi import APIRouter
import sqlalchemy as sa
from app.core.db import get_engine

router = APIRouter(prefix="/kpis-prod", tags=["kpis_prod"])

@router.get("/produccion-dia")
def produccion_dia(fecha: str):
    with get_engine().connect() as c:
        rows = c.execute(sa.text("""
            SELECT tp.nombre AS tipo_producto, SUM(e.vol_estimado) AS vol_estimado
            FROM core.fact_produccion_dia_ecp e
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = e.tipo_producto_id
            WHERE e.fecha = :f AND e.grupo_prod = 'ECOPETROL'
            GROUP BY tp.nombre ORDER BY tp.nombre"""), {"f": fecha}).mappings().all()
    return [dict(r) for r in rows]
