#!/usr/bin/env python3
"""fix_ops_database_url.py — Configura OPS_DATABASE_URL en .env (BD ROBUSTEZ/ops).

Aplica en la máquina productiva el mismo fix hecho en local el 2026-08-21: sin
OPS_DATABASE_URL, /analisis/ejecutivo economia y el EBITDA Inspector degradan con
"BD de rentabilidad (robustez) no disponible" — economia.py:75, ebitda/api.py:98,
core/db.py:23 (RuntimeError si la variable está vacía).

NO adivina ni escribe nada a ciegas: primero CONECTA con las credenciales dadas,
confirma que el schema `ops` existe en esa BD y cuenta filas en las 4 tablas que
usa unificado_waterfall. Si algo falla, el .env queda intacto.

Uso (con el Python del venv del backend, que ya trae psycopg):
    backend\\.venv\\Scripts\\python.exe fix_ops_database_url.py [--dry-run] [--force]

Credenciales por variable de entorno (NUNCA como argumento en texto plano — quedaría
en el historial de shell):
    OPS_PG_HOST      default: localhost   (mismo criterio que DATABASE_URL: si el
                                            backend corre EN el servidor de BD, localhost;
                                            si corre en otra máquina, la IP real)
    OPS_PG_PORT      default: 5432
    OPS_PG_USER      default: robustez
    OPS_PG_DBNAME    default: robustez_v02  (verificado en local 2026-08-21: la BD
                                              hermana 'robustez' NO tiene schema ops)
    OPS_PG_PASSWORD  si no se define, se pide de forma oculta (getpass) — nunca se
                     imprime ni se guarda en ningún log de este script.

Ejemplos:
    # Solo verificar, sin tocar el .env:
    set OPS_PG_PASSWORD=...  &&  python fix_ops_database_url.py --dry-run

    # Aplicar de verdad (pide la contraseña de forma oculta si no se exportó):
    python fix_ops_database_url.py

Idempotente: si OPS_DATABASE_URL ya existe en el .env, no la toca — hace falta
--force para sobreescribirla. Antes de escribir, hace backup del .env
(.env.bak-YYYYMMDDHHMMSS) en el mismo directorio.

Fuera de alcance de este script: "Diferidas"/"Mantenimientos" siguen sin datos —
esa falta es un archivo SQLite aparte (data/ECP_DIFERIDAS/ECP_DIFERIDAS.db, ~954 MB,
no versionado), no una variable de entorno. Ver diferidas.py.
"""
import argparse
import getpass
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

TABLAS_REQUERIDAS = ("financial_results", "operating_costs", "flow_rates", "wells_attributes")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true", help="Sobreescribe OPS_DATABASE_URL si ya existe en el .env.")
    ap.add_argument("--dry-run", action="store_true", help="Solo conecta y verifica; no modifica el .env.")
    args = ap.parse_args()

    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        sys.exit(f"ERROR: no existe {env_path}. Copia .env.example a .env primero y completalo.")

    host = os.environ.get("OPS_PG_HOST", "localhost")
    port = os.environ.get("OPS_PG_PORT", "5432")
    user = os.environ.get("OPS_PG_USER", "robustez")
    dbname = os.environ.get("OPS_PG_DBNAME", "robustez_v02")
    password = os.environ.get("OPS_PG_PASSWORD")
    if not password:
        password = getpass.getpass(f"Password de Postgres para {user}@{host}:{port} (no se muestra en pantalla): ")
    if not password:
        sys.exit("ERROR: password vacio.")

    try:
        import psycopg
    except ImportError:
        sys.exit(
            "ERROR: falta el paquete 'psycopg' en este intérprete.\n"
            "Ejecuta el script con el Python del venv del backend, por ejemplo:\n"
            "  backend\\.venv\\Scripts\\python.exe fix_ops_database_url.py"
        )

    print(f"Conectando a {user}@{host}:{port}/{dbname} ...")
    try:
        conn = psycopg.connect(
            host=host, port=int(port), dbname=dbname, user=user, password=password, connect_timeout=10
        )
    except Exception as e:
        sys.exit(f"ERROR de conexion: {e}")

    try:
        cur = conn.cursor()
        cur.execute("SELECT schema_name FROM information_schema.schemata ORDER BY schema_name")
        schemas = [r[0] for r in cur.fetchall()]
        if "ops" not in schemas:
            sys.exit(
                f"ERROR: la BD '{dbname}' NO tiene el schema 'ops' (schemas encontrados: {schemas}).\n"
                "Verifica OPS_PG_DBNAME -- puede que en este servidor la BD correcta tenga otro nombre."
            )
        print("  schema 'ops' encontrado. Verificando tablas...")

        faltantes = []
        for t in TABLAS_REQUERIDAS:
            try:
                cur.execute(f"SELECT COUNT(*) FROM ops.{t}")
                n = cur.fetchone()[0]
                print(f"  ops.{t:<20} -> {n:>10} filas")
            except Exception as e:
                faltantes.append(t)
                print(f"  ops.{t:<20} -> ERROR: {e}")
                conn.rollback()
    finally:
        conn.close()

    if faltantes:
        sys.exit(f"\nERROR: faltan/fallan tablas en 'ops': {faltantes}. No se modifica el .env.")

    encoded_pw = quote(password, safe="")
    url = f"postgresql+psycopg://{user}:{encoded_pw}@{host}:{port}/{dbname}?sslmode=disable"

    content = env_path.read_text(encoding="utf-8")
    existe = re.search(r"^OPS_DATABASE_URL=.*$", content, flags=re.MULTILINE)

    if existe and not args.force:
        print("\nOPS_DATABASE_URL ya existe en el .env -- no se modifica (usa --force para sobreescribirla).")
        return

    if args.dry_run:
        print("\n[--dry-run] Verificacion OK. Se escribiria OPS_DATABASE_URL (valor no mostrado). Nada modificado.")
        return

    backup = env_path.with_name(f".env.bak-{datetime.now().strftime('%Y%m%d%H%M%S')}")
    shutil.copy2(env_path, backup)
    print(f"\nBackup creado: {backup.name}")

    linea = f"OPS_DATABASE_URL={url}"
    if existe:
        new_content = re.sub(r"^OPS_DATABASE_URL=.*$", linea, content, flags=re.MULTILINE)
    else:
        sep = "" if content.endswith("\n") else "\n"
        new_content = (
            content + sep +
            "\n# BD operacional ROBUSTEZ (schema ops) -- EBITDA Inspector / Analizar economia.\n" +
            linea + "\n"
        )

    env_path.write_text(new_content, encoding="utf-8", newline="\n")
    print(f"OPS_DATABASE_URL escrita en {env_path}.")
    print("El backend NO necesita reiniciarse: get_settings() relee el .env en cada llamada,")
    print("y el engine de 'ops' nunca llego a cachearse (fallaba antes de guardarse).")


if __name__ == "__main__":
    main()
