"""Crea core.map_campo_robustez y la carga desde el CSV. PORTABLE: sirve en la BD local y en el
servidor 139 — usa get_engine() (lee el .env del entorno), así que apunta a la BD que toque.

Para desplegar en 139: copiar ESTE script + db/data/map_campo_robustez.csv al repo de 139 y correr
   uv run python cargar_map_campo_robustez.py
(No necesita robustez_v02: el CSV ya trae la reconciliación calculada en dev por build_map_campo_robustez.py.)

Idempotente: CREATE IF NOT EXISTS + TRUNCATE + INSERT → re-ejecutar deja la tabla igual.

Uso:  uv run python cargar_map_campo_robustez.py [ruta_csv]
"""
import csv
import os
import sys

import sqlalchemy as sa

from app.core.db import get_engine

CSV_DEFAULT = os.path.join(os.path.dirname(__file__), "..", "db", "data", "map_campo_robustez.csv")

# Lista de sentencias (NO partir un DDL por ';': un ';' dentro de un comentario rompería el split).
DDL_STMTS = [
    "CREATE SCHEMA IF NOT EXISTS core",
    """
    CREATE TABLE IF NOT EXISTS core.map_campo_robustez (
        campo               text PRIMARY KEY,   -- campo del reporte diario (INGESTA), nombre canónico
        campo_norm          text NOT NULL,      -- normalizado (NFKD/upper) para joins, como map_campo_activo
        operador            text,               -- operador del campo (dim_fuente)
        es_ecp              boolean NOT NULL DEFAULT false,  -- operado por ECOPETROL (No-ECP = terceros)
        rob_field           text,               -- field en robustez (fuente de verdad), NULL si no reconcilia
        rob_activo          text,               -- active en robustez (= activo)
        rob_gerencia        text,               -- management en robustez (= gerencia real, fuente de verdad)
        rob_vicepresidencia text                -- vice_presidency en robustez
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_map_campo_robustez_norm ON core.map_campo_robustez (campo_norm)",
]

INSERT = sa.text("""
INSERT INTO core.map_campo_robustez
  (campo, campo_norm, operador, es_ecp, rob_field, rob_activo, rob_gerencia, rob_vicepresidencia)
VALUES
  (:campo, :campo_norm, :operador, :es_ecp, :rob_field, :rob_activo, :rob_gerencia, :rob_vicepresidencia)
""")


def _nn(v):
    """'' → None (NULL en la BD)."""
    v = (v or "").strip()
    return v if v else None


def cargar(csv_path):
    with open(csv_path, "r", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    eng = get_engine()
    with eng.begin() as c:
        for stmt in DDL_STMTS:
            c.execute(sa.text(stmt))
        c.execute(sa.text("TRUNCATE core.map_campo_robustez"))
        for r in filas:
            c.execute(INSERT, {
                "campo": r["campo"].strip(),
                "campo_norm": r["campo_norm"].strip(),
                "operador": _nn(r.get("operador")),
                "es_ecp": str(r.get("es_ecp", "")).strip().lower() == "true",
                "rob_field": _nn(r.get("rob_field")),
                "rob_activo": _nn(r.get("rob_activo")),
                "rob_gerencia": _nn(r.get("rob_gerencia")),
                "rob_vicepresidencia": _nn(r.get("rob_vicepresidencia")),
            })
        total = c.execute(sa.text("SELECT COUNT(*) FROM core.map_campo_robustez")).scalar()
        con = c.execute(sa.text(
            "SELECT COUNT(*) FROM core.map_campo_robustez WHERE rob_field IS NOT NULL")).scalar()
    print("core.map_campo_robustez cargada: %d filas (%d con jerarquía robustez)." % (total, con))


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else CSV_DEFAULT
    if not os.path.exists(path):
        print("ERROR: no existe el CSV: %s" % os.path.abspath(path))
        sys.exit(1)
    print("Cargando desde: %s" % os.path.abspath(path))
    cargar(path)
