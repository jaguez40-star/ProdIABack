from fastapi import APIRouter
import sqlalchemy as sa
from app.core.db import get_engine

router = APIRouter(prefix="/reportes", tags=["reportes"])

@router.get("")
def listar_reportes():
    with get_engine().connect() as c:
        rows = c.execute(sa.text(
            "SELECT reporte_id, fecha_reporte, tipo_archivo, tiene_raw, nivel_detalle "
            "FROM core.config_reporte ORDER BY fecha_reporte")).mappings().all()
    return [dict(r) for r in rows]

@router.get("/ultimo")
def ultimo_reporte():
    """Fecha del reporte MÁS RECIENTE cargado (MAX(fecha_reporte), no el de mayor reporte_id: un
    reporte puede ingerirse fuera de orden). None si la tabla está vacía (arranque sin datos)."""
    with get_engine().connect() as c:
        fecha = c.execute(sa.text(
            "SELECT MAX(fecha_reporte) FROM core.config_reporte")).scalar()
    return {"fecha_reporte": fecha.isoformat() if fecha else None}

@router.get("/cobertura")
def cobertura():
    with get_engine().connect() as c:
        rows = c.execute(sa.text("""
            SELECT r.reporte_id, r.tipo_archivo,
              (SELECT count(*) FROM core.fact_produccion_mes_ecp f WHERE f.reporte_id=r.reporte_id) AS ecp_mes,
              (SELECT count(*) FROM core.fact_produccion_dia_ecp f WHERE f.reporte_id=r.reporte_id) AS ecp_dia,
              (SELECT count(*) FROM core.fact_produccion_diaria f WHERE f.reporte_id=r.reporte_id) AS filiales
            FROM core.config_reporte r ORDER BY r.reporte_id""")).mappings().all()
    return [dict(r) for r in rows]
