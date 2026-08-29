#!/usr/bin/env python
"""
clean_bd.py — Vacía las tablas de DATOS de la BD de INGESTA para empezar a cargar
reportes desde cero.

Qué hace:
  - TRUNCATE ... RESTART IDENTITY CASCADE de TODAS las tablas de los esquemas
    `bronze` y `core`, EXCEPTO `core.dim_fecha` (calendario de referencia 2019–2030;
    no es dato de reporte). Con --incluir-fecha también la vacía.
  - Reinicia las secuencias IDENTITY → `reporte_id` (y demás IDs) vuelven a empezar en 1.

Salvaguardas (es una operación DESTRUCTIVA):
  - Por DEFECTO solo opera contra la BD LOCAL (host localhost/127.0.0.1). Si el .env
    apunta a otro host (p.ej. el servidor 139 de producción), ABORTA sin tocar nada.
  - Para vaciar un host REMOTO (139) hay que pedirlo A PROPÓSITO con --permitir-remoto
    y confirmar tecleando el host EXACTO (interactivo) o pasándolo en --confirmar-host.
    Así nunca se toca producción por accidente.
  - Muestra las tablas y sus filas ANTES de borrar.
  - Pide confirmación explícita (escribir SI) salvo que se pase --yes.
  - Verifica al final que todo quedó en 0 (y que dim_fecha se preservó, si aplica).

Uso (desde INGESTA/Rep_Prod/backend):
    uv run python clean_bd.py                 # LOCAL: muestra conteos y pide confirmación
    uv run python clean_bd.py --yes           # LOCAL sin preguntar (para scripts)
    uv run python clean_bd.py --incluir-fecha # también vacía core.dim_fecha

    # REMOTO / servidor 139 (requiere que el .env apunte a 139 y respaldo previo):
    uv run python clean_bd.py --permitir-remoto                       # pide teclear el host + SI
    uv run python clean_bd.py --permitir-remoto --confirmar-host 10.100.26.139 --yes  # no interactivo
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# La consola de Windows suele ser cp1252 y revienta con símbolos no-latin1.
# Forzamos UTF-8 (y errors=replace como red de seguridad) para no crashear al imprimir.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Permitir ejecutar el script desde cualquier directorio de trabajo.
BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

import sqlalchemy as sa  # noqa: E402
from app.core.db import get_engine  # noqa: E402

# Tablas de referencia que NO son dato de reporte y se preservan por defecto.
PRESERVAR_POR_DEFECTO = {"core.dim_fecha"}
HOSTS_LOCALES = {"", "localhost", "127.0.0.1", "::1"}


def _listar_tablas(conn) -> list[str]:
    """Todas las tablas base de los esquemas bronze y core (no vistas)."""
    rows = conn.execute(sa.text(
        "SELECT schemaname, tablename FROM pg_tables "
        "WHERE schemaname IN ('bronze','core') "
        "ORDER BY schemaname, tablename")).all()
    return [f"{s}.{t}" for s, t in rows]


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Vacía las tablas de datos de la BD de INGESTA (solo dev local).")
    ap.add_argument("--yes", action="store_true", help="No pedir la confirmación final (SI).")
    ap.add_argument("--incluir-fecha", action="store_true",
                    help="También vaciar core.dim_fecha (por defecto se preserva).")
    ap.add_argument("--permitir-remoto", action="store_true",
                    help="Permite operar contra un host NO local (p.ej. servidor 139). "
                         "Exige confirmar el host exacto.")
    ap.add_argument("--confirmar-host", default=None,
                    help="Host exacto que se autoriza a vaciar en modo remoto (evita el prompt interactivo).")
    args = ap.parse_args()

    eng = get_engine()
    host = (eng.url.host or "").lower()
    db = eng.url.database

    # ---- SALVAGUARDA: por defecto solo BD local; 139/remoto requiere opt-in deliberado ----
    if host not in HOSTS_LOCALES:
        if not args.permitir_remoto:
            print(f"ABORTADO: la BD apunta a host '{host}', que NO es local.\n"
                  f"Por seguridad este script solo vacía la BD local por defecto. Si REALMENTE quieres\n"
                  f"vaciar este host (p.ej. el servidor 139 de producción, con respaldo previo), vuelve a\n"
                  f"ejecutar con:  --permitir-remoto  y confirma el host exacto.")
            sys.exit(2)
        print(f"\n[!] ATENCION: la BD objetivo es un host REMOTO: '{host}' (db={db}).")
        print("   Esto NO es la BD local de desarrollo. Asegúrate de tener respaldo.")
        esperado = host
        tecleado = (args.confirmar_host or "").strip().lower()
        if not tecleado:
            try:
                tecleado = input(f'   Escribe exactamente el host "{esperado}" para autorizar el borrado: ').strip().lower()
            except EOFError:
                tecleado = ""
        if tecleado != esperado:
            print(f"   El host no coincide (recibido: '{tecleado or ""}'). Cancelado. No se borró nada.")
            sys.exit(1)
        print(f"   Host remoto '{esperado}' confirmado.")

    preservar = set() if args.incluir_fecha else set(PRESERVAR_POR_DEFECTO)

    print(f"BD objetivo: host={host or 'localhost'}  db={db}  user={eng.url.username}")

    # ---- Inventario + conteos (fuera de transacción) ----
    with eng.connect() as conn:
        todas = _listar_tablas(conn)
        if not todas:
            print("No se encontraron tablas en los esquemas bronze/core. Nada que hacer.")
            return
        objetivo = [t for t in todas if t not in preservar]

        print("\nTablas y filas actuales:")
        total_a_borrar = 0
        for t in todas:
            n = conn.execute(sa.text(f"SELECT count(*) FROM {t}")).scalar() or 0
            if t in preservar:
                print(f"  {t:<42} {n:>12,}   (SE PRESERVA)")
            else:
                total_a_borrar += n
                print(f"  {t:<42} {n:>12,}")

    print(f"\nSe VACIARÁN {len(objetivo)} tablas (~{total_a_borrar:,} filas).")
    print(f"Preservadas: {', '.join(sorted(preservar)) if preservar else 'ninguna'}")

    # ---- Confirmación ----
    if not args.yes:
        try:
            resp = input('\nEscribe "SI" (mayúsculas) para confirmar el borrado: ').strip()
        except EOFError:
            resp = ""
        if resp != "SI":
            print("Cancelado. No se borró nada.")
            sys.exit(1)

    # ---- TRUNCATE atómico con reinicio de IDENTITY ----
    lista = ", ".join(objetivo)
    with eng.begin() as conn:
        conn.execute(sa.text(f"TRUNCATE TABLE {lista} RESTART IDENTITY CASCADE"))
    print(f"\n[OK] TRUNCATE ejecutado sobre {len(objetivo)} tablas (RESTART IDENTITY).")

    # ---- Verificación post-borrado ----
    with eng.connect() as conn:
        print("\nVerificación (filas tras el borrado):")
        restantes = 0
        for t in _listar_tablas(conn):
            n = conn.execute(sa.text(f"SELECT count(*) FROM {t}")).scalar() or 0
            if t not in preservar:
                restantes += n
            marca = "   (preservada)" if t in preservar else ""
            print(f"  {t:<42} {n:>12,}{marca}")

    if restantes == 0:
        print("\nListo. La BD quedó lista para cargar reportes desde cero "
              "(reporte_id empezará en 1).")
    else:
        print(f"\n[!] Quedaron {restantes:,} filas en tablas que debían vaciarse. Revisa el detalle de arriba.")
        sys.exit(3)


if __name__ == "__main__":
    main()
