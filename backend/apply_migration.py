#!/usr/bin/env python
"""
apply_migration.py -- Aplica un archivo .sql de migracion contra la BD de INGESTA.

Usa app.core.db.get_engine() (misma conexion que la app, leida del .env) en vez de invocar
psql, para evitar el problema de codificacion de contrasenas con caracteres especiales (p.ej.
el '£' de la clave local) que rompe la autenticacion al pasarla por la linea de comandos.

Uso (desde INGESTA/Rep_Prod/backend):
    uv run python apply_migration.py ../db/migrations/006_ix_tabla_hoja_covering.sql

Las migraciones deben ser IDEMPOTENTES (IF NOT EXISTS / ON CONFLICT): este script las ejecuta
tal cual, sin llevar registro de cuales ya se aplicaron. Reaplicar una migracion idempotente
es un no-op seguro.
"""
from __future__ import annotations

import sys
from pathlib import Path

# La consola de Windows suele ser cp1252 y revienta con simbolos no-latin1.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

import sqlalchemy as sa  # noqa: E402
from app.core.db import get_engine  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        print("uso: uv run python apply_migration.py <ruta_al_.sql>")
        sys.exit(2)

    ruta = Path(sys.argv[1])
    if not ruta.is_absolute():
        ruta = (Path.cwd() / ruta).resolve()
    if not ruta.is_file():
        print(f"ERROR: no existe el archivo de migracion: {ruta}")
        sys.exit(2)

    sql = ruta.read_text(encoding="utf-8")
    eng = get_engine()
    print(f"BD objetivo: host={eng.url.host or 'localhost'}  db={eng.url.database}  user={eng.url.username}")
    print(f"Aplicando migracion: {ruta.name}")

    # exec_driver_sql pasa el SQL crudo a psycopg (permite varias sentencias separadas por ';').
    # engine.begin() envuelve en transaccion; las migraciones aqui NO usan CREATE INDEX CONCURRENTLY,
    # asi que pueden correr dentro de una transaccion sin problema.
    with eng.begin() as conn:
        conn.exec_driver_sql(sql)

    print(f"[OK] Migracion aplicada: {ruta.name}")


if __name__ == "__main__":
    main()
