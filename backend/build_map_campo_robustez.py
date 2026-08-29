"""Construye la reconciliación campo (reporte diario / INGESTA) ↔ jerarquía de ROBUSTEZ.

FUENTE DE VERDAD = robustez_v02.ops.wells_attributes (VP → management → active → field → uwi).
ANCLA = el campo (field): nivel más fino común a los dos mundos.

Reglas (decisiones del usuario, 2026-08-02):
  1. Sectores (CUPIAGUA SUR, PACHAQUIARO NORTE…): se dejan como campos PROPIOS → sin jerarquía
     robustez (no se pliegan al campo padre). Salen con rob_* = NULL.
  2. Terceros (SierraCol, Cepcolsa, Gran Tierra, Hocol, Parex…): se marcan es_ecp=false. Robustez
     NO los modela (solo cubre el universo ECP-operado) → rob_* = NULL, pero NO se pierden.
  3. Match = exacto sobre norm() + un override manual limpio (ACAE, solo cambia el sufijo).

Este script SOLO computa y escribe el CSV (dev, necesita robustez_v02). La creación+carga de la
tabla la hace cargar_map_campo_robustez.py (portable: local y servidor 139, solo necesita el CSV).

Uso:  uv run python build_map_campo_robustez.py
"""
import csv
import os

import sqlalchemy as sa

from app.core.config import get_settings
from app.core.db import get_engine
from app.features.consulta.normaliza import norm

CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "data", "map_campo_robustez.csv")

# Override manual: mismo campo, robustez omite el sufijo de ubicación "(PTO COLON)".
# Es substring inequívoco y mismo operador (ECOPETROL) — no es fuzzy de riesgo.
_OVERRIDES = {norm("ACAE-SAN MIGUEL (PTO COLON)"): norm("ACAE-SAN MIGUEL")}


def _robustez_dominante():
    """{norm(field): (field, active, management, vice_presidency)} — la combinación jerárquica
    DOMINANTE por field (la que más pozos tiene). Un field puede colgar de >1 active (8 casos);
    se toma el representante mayoritario."""
    s = get_settings()
    eng = sa.create_engine(s.ops_database_url)
    dom = {}   # norm(field) -> (n, field, active, management, vice)
    with eng.connect() as c:
        rows = c.execute(sa.text("""
            SELECT TRIM(field) f, TRIM(active) a, TRIM(management) m, TRIM(vice_presidency) v,
                   COUNT(*) n
            FROM ops.wells_attributes
            WHERE NULLIF(TRIM(field),'') IS NOT NULL
            GROUP BY TRIM(field), TRIM(active), TRIM(management), TRIM(vice_presidency)
        """)).all()
    for f, a, m, v, n in rows:
        k = norm(f)
        if k not in dom or n > dom[k][0]:
            dom[k] = (n, f, a, m, v)
    return {k: (f, a, m, v) for k, (n, f, a, m, v) in dom.items()}


def _ingesta_campos():
    """{norm(campo): (campo_canonico, operador_dominante)} desde el reporte diario."""
    eng = get_engine()
    with eng.connect() as c:
        rows = c.execute(sa.text("""
            SELECT TRIM(campo) campo, COALESCE(TRIM(operador),'') op, COUNT(*) n
            FROM core.dim_fuente
            WHERE NULLIF(TRIM(campo),'') IS NOT NULL
            GROUP BY TRIM(campo), COALESCE(TRIM(operador),'')
        """)).all()
    tmp = {}   # norm(campo) -> {op: n, _campo: canonico}
    for campo, op, n in rows:
        k = norm(campo)
        d = tmp.setdefault(k, {"_campo": campo, "_ops": {}})
        d["_ops"][op] = d["_ops"].get(op, 0) + n
    out = {}
    for k, d in tmp.items():
        op = max(d["_ops"].items(), key=lambda x: x[1])[0] if d["_ops"] else ""
        out[k] = (d["_campo"], op)
    return out


def construir():
    rob = _robustez_dominante()
    ing = _ingesta_campos()
    filas = []
    for k, (campo, operador) in sorted(ing.items(), key=lambda x: x[1][0]):
        es_ecp = operador.strip().upper() == "ECOPETROL"
        rob_key = _OVERRIDES.get(k, k)
        r = rob.get(rob_key)
        if r:
            rob_field, rob_activo, rob_gerencia, rob_vice = r
        else:
            rob_field = rob_activo = rob_gerencia = rob_vice = ""
        filas.append({
            "campo": campo, "campo_norm": k, "operador": operador, "es_ecp": es_ecp,
            "rob_field": rob_field, "rob_activo": rob_activo,
            "rob_gerencia": rob_gerencia, "rob_vicepresidencia": rob_vice,
        })
    return filas


def main():
    filas = construir()
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    cols = ["campo", "campo_norm", "operador", "es_ecp", "rob_field",
            "rob_activo", "rob_gerencia", "rob_vicepresidencia"]
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for row in filas:
            r = dict(row)
            r["es_ecp"] = "true" if row["es_ecp"] else "false"
            w.writerow(r)

    con_jerarquia = sum(1 for r in filas if r["rob_field"])
    ecp = sum(1 for r in filas if r["es_ecp"])
    ecp_sin = sum(1 for r in filas if r["es_ecp"] and not r["rob_field"])
    print("CSV escrito: %s" % os.path.abspath(CSV_PATH))
    print("  Total campos (reporte diario): %d" % len(filas))
    print("  Con jerarquía robustez:        %d" % con_jerarquia)
    print("  ECP-operados:                  %d  (de esos, sin match robustez: %d)" % (ecp, ecp_sin))
    print("  No-ECP (terceros):             %d" % (len(filas) - ecp))


if __name__ == "__main__":
    main()
