"""Libreta de clasificación (core.clasificacion_log, migración 010).

Escritura al clasificar + actualización de veredicto por los tres jueces:
  - Control 1 (usuario, ✓/✗ en la burbuja)  → confirmado_usuario | corregido_usuario
  - Control 2 (señal indirecta, senales.py)  → sospecha (bandera de prioridad, NO veredicto)
  - Control 3 (revisión por lotes)           → confirmado_revision | corregido_revision

Principio (audit_motor_clas.md): solo los casos VERIFICADOS alimentan el crecimiento de
patrones y del golden. La libreta registra únicamente TRÁFICO REAL del API — el golden
runner y los pytest llaman clasificar(log=False) (H3).
"""
import json

import sqlalchemy as sa

from app.core.db import get_engine

VEREDICTOS_VALIDOS = {"confirmado_usuario", "corregido_usuario",
                      "confirmado_revision", "corregido_revision"}
GRUPOS = {"jerarquizar", "cuantificar", "analizar", "desconocido"}


def registrar(texto: str, grupo: str, capa: str, patrones=None, entidad=None,
              usuario=None, conversation_id=None, llm_diag=None):
    """Inserta el registro de una clasificación (veredicto='pendiente'). Devuelve id."""
    eng = get_engine()
    with eng.begin() as c:
        return c.execute(sa.text("""
            INSERT INTO core.clasificacion_log
                (usuario, conversation_id, texto_pregunta, grupo_asignado,
                 capa_resolutora, patrones_atrapados, entidad_cruda, llm_diag)
            VALUES (:u, :cid, :txt, :g, :capa, CAST(:pat AS JSONB), :ent, :diag)
            RETURNING id
        """), {"u": usuario, "cid": conversation_id, "txt": texto, "g": grupo,
               "capa": capa, "pat": json.dumps(patrones) if patrones else None,
               "ent": entidad, "diag": llm_diag}).scalar()


def poner_veredicto(log_id: int, veredicto: str, grupo_correcto=None,
                    fuente: str = "usuario", nota=None) -> bool:
    """Veredicto de un juez humano (Controles 1 y 3). La etiqueta de revisión es la verdad
    final: sobreescribe cualquier señal previa. False si log_id no existe o datos inválidos."""
    if veredicto not in VEREDICTOS_VALIDOS:
        return False
    if veredicto.startswith("corregido") and grupo_correcto not in GRUPOS:
        return False
    if veredicto.startswith("confirmado"):
        grupo_correcto = None
    eng = get_engine()
    with eng.begin() as c:
        n = c.execute(sa.text("""
            UPDATE core.clasificacion_log
               SET veredicto=:v, grupo_correcto=:gc, fuente_veredicto=:f,
                   ts_veredicto=now(), nota_revision=COALESCE(:nota, nota_revision)
             WHERE id=:id
        """), {"v": veredicto, "gc": grupo_correcto, "f": fuente,
               "nota": nota, "id": log_id}).rowcount
    return bool(n)


def marcar_sospecha(log_id: int, motivo: str) -> bool:
    """Control 2: sospecha. SOLO sobre filas 'pendiente' (jamás pisa un veredicto humano)."""
    eng = get_engine()
    with eng.begin() as c:
        n = c.execute(sa.text("""
            UPDATE core.clasificacion_log
               SET veredicto='sospecha', fuente_veredicto='indirecta',
                   ts_veredicto=now(), nota_revision=:m
             WHERE id=:id AND veredicto='pendiente'
        """), {"m": motivo, "id": log_id}).rowcount
    return bool(n)


_FILTROS = {
    "pendientes": "veredicto IN ('pendiente','sospecha')",
    "sospecha":   "veredicto = 'sospecha'",
    "corregidas": "veredicto IN ('corregido_usuario','corregido_revision')",
    "todas":      "TRUE",
}


def listar(limit: int = 100, filtro: str = "todas") -> dict:
    """Lista para la tabla de «Test Clas» (recientes primero; sospechas al tope) + resumen
    O1: conteos por veredicto y % resuelto por Capa 1 (el KPI del ciclo de crecimiento)."""
    cond = _FILTROS.get(filtro, "TRUE")
    eng = get_engine()
    with eng.connect() as c:
        filas = c.execute(sa.text(f"""
            SELECT id, ts, usuario, conversation_id, texto_pregunta, grupo_asignado,
                   capa_resolutora, patrones_atrapados, entidad_cruda, llm_diag,
                   veredicto, grupo_correcto, fuente_veredicto, ts_veredicto
              FROM core.clasificacion_log
             WHERE {cond}
             ORDER BY (veredicto='sospecha') DESC, ts DESC
             LIMIT :lim
        """), {"lim": max(1, min(int(limit), 500))}).mappings().all()
        res = c.execute(sa.text("""
            SELECT veredicto, COUNT(*) n,
                   COUNT(*) FILTER (WHERE capa_resolutora='regex') n_regex
              FROM core.clasificacion_log GROUP BY veredicto
        """)).mappings().all()
    total = sum(r["n"] for r in res)
    regex = sum(r["n_regex"] for r in res)
    resumen = {"total": total,
               "por_veredicto": {r["veredicto"]: r["n"] for r in res},
               "pct_capa1": round(100 * regex / total, 1) if total else None}
    out = []
    for f in filas:
        d = dict(f)
        d["ts"] = d["ts"].isoformat() if d["ts"] else None
        d["ts_veredicto"] = d["ts_veredicto"].isoformat() if d["ts_veredicto"] else None
        out.append(d)
    return {"filas": out, "resumen": resumen}
