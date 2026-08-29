"""Control 2 — señales indirectas de clasificación fallida → 'sospecha'.

La sospecha NO corrige nada por sí sola (señal débil): su único efecto es priorizar la
cola de revisión (Control 3). Tres señales:
  1. Reformulación inmediata: el MISMO USUARIO envía otra pregunta muy similar en ≤120s.
     H2: matching por usuario, NO por conversation_id — el flujo real cruza chats con IDs
     distintos (prueba en Test Clas, repite en Consulta) y por conversación jamás casaría.
  2. Cambio a motor v1: el frontend la empuja vía POST /consulta2/senal (P2 — v1 está
     congelada y no puede observarse desde su propio código).
  3. Abandono tras 'desconocido': sin filas posteriores del usuario en ≥600s.

P3: similitud por ratio de tokens compartidos (Jaccard sobre texto normalizado) — NO
pg_trgm (la migración 007 sigue sin aplicar; una señal débil no justifica la dependencia).
P4: sin scheduler — escanear() corre al servir GET /log y al arrancar revisar_lote.py.
H7: escaneo acotado a 'pendiente' de los últimos N días (config), no toda la libreta.
"""
import pathlib

import sqlalchemy as sa
import yaml

from app.core.db import get_engine
from app.features.consulta_v2.normaliza import norm
from app.features.consulta_v2.log import marcar_sospecha

_CFG_PATH = pathlib.Path(__file__).parent / "config" / "clasificacion_feedback.yaml"
_CFG = None


def _cfg():
    global _CFG
    if _CFG is None:
        _CFG = yaml.safe_load(_CFG_PATH.read_text(encoding="utf-8"))
    return _CFG


def similitud(a: str, b: str) -> float:
    """Jaccard sobre tokens normalizados. 0.0-1.0. Puro (testeable sin BD)."""
    ta, tb = set(norm(a).split()), set(norm(b).split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def registrar_senal_v1(texto: str, usuario=None) -> bool:
    """Señal 2 (P2, empujada por el frontend): el usuario repitió la pregunta en el motor v1.
    Marca 'sospecha' en la última clasificación v2 RECIENTE y SIMILAR de ese usuario."""
    c = _cfg()
    eng = get_engine()
    with eng.connect() as conn:
        fila = conn.execute(sa.text("""
            SELECT id, texto_pregunta FROM core.clasificacion_log
             WHERE veredicto='pendiente'
               AND (usuario = :u OR (:u IS NULL AND usuario IS NULL))
               AND ts >= now() - make_interval(secs => :win)
             ORDER BY ts DESC LIMIT 1
        """), {"u": usuario, "win": c["ventana_reformulacion_seg"]}).first()
    if not fila:
        return False
    if similitud(texto, fila.texto_pregunta) < c["similitud_reformulacion"]:
        return False
    return marcar_sospecha(fila.id, "señal indirecta: repitió la pregunta en el motor v1")


def escanear() -> int:
    """Señales 1 y 3 sobre la libreta (acotado H7). Devuelve nº de sospechas nuevas."""
    c = _cfg()
    win_ref = c["ventana_reformulacion_seg"]
    win_aband = c["ventana_abandono_seg"]
    umbral = c["similitud_reformulacion"]
    dias = c.get("escaneo_dias", 7)
    nuevos = 0
    eng = get_engine()
    with eng.connect() as conn:
        pend = conn.execute(sa.text("""
            SELECT id, ts, usuario, texto_pregunta, grupo_asignado, capa_resolutora
              FROM core.clasificacion_log
             WHERE veredicto='pendiente' AND ts >= now() - make_interval(days => :d)
             ORDER BY ts
        """), {"d": dias}).mappings().all()

        for f in pend:
            # Señal 1 — reformulación: la SIGUIENTE pregunta del mismo usuario, ≤ventana, similar
            sig = conn.execute(sa.text("""
                SELECT texto_pregunta FROM core.clasificacion_log
                 WHERE id <> :id
                   AND (usuario = :u OR (:u IS NULL AND usuario IS NULL))
                   AND ts > :ts AND ts <= :ts + make_interval(secs => :win)
                 ORDER BY ts LIMIT 1
            """), {"id": f["id"], "u": f["usuario"], "ts": f["ts"], "win": win_ref}).first()
            if sig and similitud(f["texto_pregunta"], sig.texto_pregunta) >= umbral:
                nuevos += marcar_sospecha(f["id"], "señal indirecta: reformulación inmediata")
                continue

            # Señal 3 — abandono tras 'desconocido' del LLM (H-B): el OUT-por-filtro (regex+filtro)
            # es una salida CONFIADA — abandonar tras un off-topic es esperado, no señal de fallo.
            if (f["grupo_asignado"] == "desconocido"
                    and f["capa_resolutora"] in ("llm", "regex+llm")):
                hay_post = conn.execute(sa.text("""
                    SELECT 1 FROM core.clasificacion_log
                     WHERE id <> :id
                       AND (usuario = :u OR (:u IS NULL AND usuario IS NULL))
                       AND ts > :ts LIMIT 1
                """), {"id": f["id"], "u": f["usuario"], "ts": f["ts"]}).first()
                vencida = conn.execute(sa.text(
                    "SELECT now() > :ts + make_interval(secs => :w)"),
                    {"ts": f["ts"], "w": win_aband}).scalar()
                if not hay_post and vencida:
                    nuevos += marcar_sospecha(f["id"], "señal indirecta: abandono tras desconocido")
    return nuevos
