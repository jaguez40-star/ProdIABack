"""EBITDA Inspector — waterfall unificado (Ingresos → EBITDA → EBIT → NOPAT).

Lee la BD operacional ROBUSTEZ (schema ops) vía get_ops_engine() y reproduce la agregación del
proyecto fuente (Des_robustez_2.0): cada componente = SUM(columna_kusd) saneado; USD/BI = kusd*1000
/ Σbarriles. Variante Crudo·Activos·Real (revenue_oil_real, sufijo _a). Período por defecto = último
mes con REAL en la BD de producción de ProdIA (alineado con el Desempeño). Global | activo | campo
(pozo pendiente). Solo lectura.
"""
from fastapi import APIRouter, Query, HTTPException
import sqlalchemy as sa
from app.core.db import get_engine, get_ops_engine

router = APIRouter(prefix="/ebitda")

# (label, key, tabla, columna, tipo, signo). Orden = orden del waterfall.
#   signo: pos = tal cual (totales) · negabs = -abs (costos op) · neg = -v (cargos fr guardados +) ·
#          asis = tal cual (fr ya trae signo negativo: renta/financieros/dif_cambio)
_COMP = [
    ("Ingresos", "ingresos", "fr", "revenue_oil_real_kusd", "total", "pos"),
    ("M. Subsuelo", "subsuelo", "oc", "maintenance_subsurface_a_kusd", "delta", "negabs"),
    ("Dilución", "dilucion", "oc", "dilution_real_a_kusd", "delta", "negabs"),
    ("Tratamiento", "tratamiento", "oc", "treatment_a_kusd", "delta", "negabs"),
    ("Energía", "energia", "oc", "energy_a_kusd", "delta", "negabs"),
    ("Transporte", "transporte", "oc", "transport_real_a_kusd", "delta", "negabs"),
    ("Costos Fijos", "costos_fijos", "oc", "costs_fixed_a_kusd", "delta", "negabs"),
    ("Gasto", "gasto", "oc", "expenses_a_kusd", "delta", "negabs"),
    ("EBITDA", "ebitda", "fr", "ebitda_a_kusd", "total", "pos"),
    ("Amortización", "amortiz", "fr", "amortiz_a_kusd", "delta", "neg"),
    ("Depreciación", "deprec", "fr", "deprec_a_kusd", "delta", "neg"),
    ("Impuestos Costos y Gastos", "imp_cosgas", "fr", "imp_cosgas_a_kusd", "delta", "neg"),
    ("Impairment", "impair", "fr", "impair_a_kusd", "delta", "neg"),
    ("UTILID. OPERATIVA (EBIT)", "util_oper", "fr", "util_oper_a_kusd", "total", "pos"),
    ("Impuesto de renta", "imp_renta", "fr", "imp_renta_a_kusd", "delta", "asis"),
    ("Financieros netos", "finan_netos", "fr", "finan_netos_a_kusd", "delta", "asis"),
    ("Diferencia en cambio", "dif_en_cambio", "fr", "dif_en_cambio_a_kusd", "delta", "asis"),
    ("UTILID. NETA (NOPAT)", "util_neta", "fr", "util_neta_a_kusd", "total", "pos"),
]


def _san(expr: str) -> str:
    return f"NULLIF(NULLIF(NULLIF({expr},'Infinity'),'-Infinity'),'NaN')"


def _ultimo_mes_prodia():
    """(year, month) del último mes con REAL en la BD de producción de ProdIA. Alinea el período."""
    try:
        with get_engine().connect() as c:
            d = c.execute(sa.text(
                "SELECT MAX(m.fecha) FROM core.fact_produccion_mes_ecp m "
                "JOIN core.dim_escenario es ON es.escenario_id=m.escenario_id WHERE es.nombre='REAL'"
            )).scalar()
        return (d.year, d.month) if d else (None, None)
    except Exception:
        return (None, None)


def _ultimo_mes_economia():
    """(year, month) del último mes con datos en la BD ECONÓMICA (ops), o (None, None).

    [2026-08-26] Las dos fuentes van a ritmos distintos: el período lo fija
    `_ultimo_mes_prodia()` sobre la BD de PRODUCCIÓN, pero las cifras salen de `ops.*`. Medido:
    producción iba por agosto 2026 y la economía terminaba en julio, así que la consulta devolvía
    las 18 filas con SUM=0 — un waterfall en blanco, sin una palabra que dijera por qué.
    Devolverlo permite al frontend decir HASTA DÓNDE llega la economía en vez de callar.
    """
    try:
        with get_ops_engine().connect() as c:
            row = c.execute(sa.text(
                "SELECT year, month FROM ops.financial_results "
                "GROUP BY year, month ORDER BY year DESC, month DESC LIMIT 1"
            )).first()
        return (int(row[0]), int(row[1])) if row else (None, None)
    except Exception:
        return (None, None)


@router.get("/unificado-waterfall")
def unificado_waterfall(
    year: int | None = Query(None), month: int | None = Query(None),
    nivel: str | None = Query(None), entidad: str | None = Query(None),
):
    if not year or not month:
        year, month = _ultimo_mes_prodia()
    if not year or not month:
        raise HTTPException(503, "No se pudo resolver el período (BD de producción no disponible)")

    sums = ", ".join(f"SUM({_san(t + '.' + col)}) AS {key}" for (_, key, t, col, _, _) in _COMP)
    sums += f", SUM({_san('flr.total_bbl_blend')}) AS total_bls"

    params: dict = {"y": year, "m": month}
    wa_join, wa_where = "", ""
    niv = (nivel or "").strip().lower()
    if niv in ("activo", "campo") and entidad:
        col = "active" if niv == "activo" else "field"
        # `entidad` puede traer varios valores separados por "|" (un foco tiene N campos, igual que Diferidas).
        vals = [v.strip().upper() for v in str(entidad).split("|") if v.strip()]
        wa_join = ("JOIN (SELECT DISTINCT ON (uwi) uwi, active, field FROM ops.wells_attributes "
                   "ORDER BY uwi, well_status, pend_id_cc, zone) wa ON wa.uwi = fr.uwi")
        ph = ",".join(f":e{i}" for i in range(len(vals)))
        wa_where = f" AND UPPER(TRIM(wa.{col})) IN ({ph})"
        for i, v in enumerate(vals):
            params[f"e{i}"] = v

    sql = f"""
        SELECT {sums}
        FROM ops.financial_results fr
        JOIN ops.operating_costs oc ON (oc.uwi,oc.year,oc.month,oc.well_status,oc.pend_id_cc,oc.zone)
             = (fr.uwi,fr.year,fr.month,fr.well_status,fr.pend_id_cc,fr.zone)
        JOIN ops.flow_rates flr ON (flr.uwi,flr.year,flr.month,flr.well_status,flr.pend_id_cc,flr.zone)
             = (fr.uwi,fr.year,fr.month,fr.well_status,fr.pend_id_cc,fr.zone)
        {wa_join}
        WHERE fr.year = :y AND fr.month = :m{wa_where}"""

    try:
        with get_ops_engine().connect() as c:
            row = c.execute(sa.text(sql), params).mappings().first()
    except Exception as e:
        raise HTTPException(503, f"BD ROBUSTEZ/ops no disponible: {e}")

    r = dict(row) if row else {}
    bls = float(r.get("total_bls") or 0)

    def _signed(key: str, mode: str) -> float:
        v = float(r.get(key) or 0)
        if mode == "negabs":
            return -abs(v)
        if mode == "neg":
            return -v
        return v  # pos / asis

    comps = []
    for (label, key, _t, _col, tipo, mode) in _COMP:
        v = _signed(key, mode)
        comps.append({
            "key": key, "label": label, "value_kusd": round(v),
            "value_usd_bl": round(v * 1000 / bls, 2) if bls else 0.0, "type": tipo,
        })

    # [2026-08-26] Si el mes pedido no tiene economía, el SQL devuelve ceros y el waterfall salía
    # VACÍO sin explicación. Se declara hasta dónde llega la fuente para que el cliente lo diga.
    # Solo se consulta cuando de verdad no hay datos: es una query más, y en el camino feliz sobra.
    eco_y = eco_m = None
    if not bls:
        eco_y, eco_m = _ultimo_mes_economia()

    return {
        "components": comps, "total_bls": round(bls),
        "meta": {"year": year, "month": month, "nivel": niv or "global",
                 "entidad": entidad or None, "producto": "CRUDO", "unidad_default": "USD/BI",
                 "sin_economia": not bls,
                 "economia_hasta": {"year": eco_y, "month": eco_m} if eco_y else None},
    }
