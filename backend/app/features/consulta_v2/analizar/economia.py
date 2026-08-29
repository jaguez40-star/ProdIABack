"""analizar/economia.py — EBITDA/NOPAT por entidad (universo robustez), Analizar Fase 3.

Envuelve el EBITDA Inspector (feature `ebitda`, MISMO backend FastAPI) por import directo de
unificado_waterfall con args explícitos — patrón de Fase 1 con `ejecutivo`, NO HTTP (H1). El lector de
robustez ya existe y corre; aquí solo se TRADUCE la entidad INGESTA a nombres robustez (rob_field) y
se degrada con honestidad.

Level-shift (H3): rob_field != campo INGESTA en general -> se mapea vía core.map_campo_robustez. Solo
ECP-operado (H4): 80/139 campos reconcilian; terceros (es_ecp=false) y 1 ECP sin robustez -> se
declaran, no se inventan. El waterfall es CRUDO/aceite (H5); período = mes vigente del tablero (H6).
"""
import sqlalchemy as sa

from app.core.db import get_engine
from app.features.ebitda.api import unificado_waterfall as _waterfall_ep

_NIVELES_OK = (None, "campo", "activo")   # None = global (sin filtro)


def nivel_soportado(nivel: str | None) -> bool:
    """El waterfall solo filtra por campo/activo (o global). gerencia/VP/operador/fuente -> False
    (mismo criterio que diferidas.nivel_soportado; gerencia/VP = extensión futura, EC-5)."""
    return nivel in _NIVELES_OK


def rob_fields_de(nivel: str | None, valor: str | None) -> tuple[list[str], int]:
    """Traduce la entidad INGESTA a nombres de robustez (rob_field). Devuelve (rob_fields, total):
      - rob_fields: los rob_field NOT NULL del alcance (campos ECP que reconcilian con robustez).
      - total:      cuántos campos tiene el alcance en INGESTA (para declarar la cobertura, EC-7).
    El llamador calcula `omitidos = total - len(rob_fields)`.

    🔑 EC-7: `total` NO es cosmético. Hay activos donde la cobertura es brutalmente parcial (NARE 1 de
    8 campos, LISAMA 1/6, SURIA 5/10 — medido). Servir el EBITDA de 1 campo como «el EBITDA de NARE»
    sería el bug clase-APIAY de S23; por eso la cobertura viaja y se declara EN CABECERA.

    valor None (global) -> ([], 0): sin filtro, el waterfall agrega todo el universo robustez.
    EC-10: un campo sin FILA en map_campo_robustez da ([], 0) igual que un tercero -> misma declinación.
    Solo lee la BD de ProdIA (no toca ops)."""
    if not valor:
        return [], 0
    eng = get_engine()
    with eng.connect() as c:
        if nivel == "activo":
            # activo INGESTA -> sus campos (map_campo_activo) -> rob_field (map_campo_robustez).
            # Se traduce campo por campo (no se usa `rob_activo`): el activo del usuario es el de
            # INGESTA, y S28 documentó que los conjuntos de robustez pueden diferir.
            rows = c.execute(sa.text(
                "SELECT mcr.rob_field FROM core.map_campo_activo mca "
                "LEFT JOIN core.map_campo_robustez mcr ON mcr.campo_norm = mca.campo_norm "
                "WHERE UPPER(TRIM(mca.activo)) = UPPER(TRIM(:v))"), {"v": valor}).all()
        else:   # campo (otros niveles ya los filtró nivel_soportado aguas arriba)
            rows = c.execute(sa.text(
                "SELECT rob_field FROM core.map_campo_robustez "
                "WHERE UPPER(TRIM(campo)) = UPPER(TRIM(:v))"), {"v": valor}).all()
    rob_fields = [r[0] for r in rows if r[0]]      # rob_field NOT NULL = reconcilia con robustez
    return rob_fields, len(rows)


def impacto_economico(rob_fields: list[str] | None) -> dict:
    """Llama el EBITDA Inspector (mismo backend). rob_fields=[] o None -> global. year/month=None ->
    el inspector usa el ULTIMO mes REAL de ProdIA (H6, alineado con el tablero).

    Retorno (mismo contrato que diferidas.impacto_historico):
      {"sin_datos": True, "motivo": "..."}                 -- ops no disponible o error (H7)
      {"sin_datos": False, "waterfall": {...}}             -- con datos (dict de unificado_waterfall)

    SIEMPRE degrada (nunca lanza): captura la HTTPException(503) que unificado_waterfall relanza
    cuando OPS_DATABASE_URL falta (EC-2)."""
    entidad = "|".join(rob_fields) if rob_fields else None
    nivel = "campo" if rob_fields else None
    try:
        w = _waterfall_ep(year=None, month=None, nivel=nivel, entidad=entidad)
        return {"sin_datos": False, "waterfall": w}
    except Exception as e:
        return {"sin_datos": True, "motivo": f"BD de rentabilidad (robustez) no disponible: {e}"}
