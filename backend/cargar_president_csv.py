"""Carga la hoja REPORTE_PRESIDENT a core.fact_tabla_hoja desde un CSV.

PARA QUE SIRVE
--------------
`reingesta_hojas_nuevas.py` re-extrae la hoja desde los .xlsm, pero el corpus (~464 MB) no esta
en todos los entornos -- el servidor de pruebas no lo tiene. Este script deja la MISMA informacion
en la BD partiendo de un CSV exportado de un entorno donde si se ingirio, para desbloquear
`GET /analisis/president` (las tarjetas de compromiso P50 del encabezado del analisis).

Usa `app.core.db.get_engine()` -- la misma conexion que la app -- para no depender de psql, que
falla con contrasenas que llevan caracteres especiales (mismo motivo que apply_migration.py).

POR QUE EL CSV NO LLEVA reporte_id
----------------------------------
`reporte_id` es un serial: depende del ORDEN de ingesta y difiere entre entornos. Ademas
fact_tabla_hoja tiene FK a core.config_reporte, asi que un id inventado falla. El CSV lleva
`fecha_reporte` y este script lo resuelve contra la config_reporte de la BD DESTINO. Las fechas
que no tengan reporte en destino se OMITEN y se listan (no se inventan encabezados).

IDEMPOTENTE
-----------
Por cada reporte afectado hace DELETE de (reporte_id, hoja) y luego INSERT -- el mismo criterio
"DELETE+INSERT por hoja" del loader de la ingesta. Correrlo dos veces deja el mismo estado.
Todo va en UNA transaccion: si algo falla, no queda a medias.

USO
---
    cd INGESTA/Rep_Prod/backend
    uv run python cargar_president_csv.py --dry-run     # que haria, sin escribir
    uv run python cargar_president_csv.py               # aplica
    uv run python cargar_president_csv.py ../db/seeds/otro.csv
"""
import csv
import os
import sys
from collections import defaultdict

import sqlalchemy as sa

from app.core.db import get_engine

HOJA = "REPORTE_PRESIDENT"
_AQUI = os.path.dirname(os.path.abspath(__file__))
CSV_DEFAULT = os.path.join(_AQUI, "..", "db", "seeds", "reporte_president.csv")
COLUMNAS = ["fecha_reporte", "hoja", "tabla_idx", "tabla_label", "dims", "fecha", "valor"]


def leer_csv(ruta):
    """Devuelve {fecha_reporte: [fila, ...]}. Valida el encabezado antes de nada."""
    porfecha = defaultdict(list)
    with open(ruta, newline="", encoding="utf-8") as fh:
        r = csv.DictReader(fh)
        faltan = [c for c in COLUMNAS if c not in (r.fieldnames or [])]
        if faltan:
            raise SystemExit(f"ERROR: al CSV le faltan columnas: {', '.join(faltan)}")
        for i, fila in enumerate(r, start=2):
            if (fila.get("hoja") or "").strip() != HOJA:
                raise SystemExit(f"ERROR linea {i}: hoja='{fila.get('hoja')}', se esperaba '{HOJA}'. "
                                 f"Este script solo carga {HOJA}.")
            porfecha[fila["fecha_reporte"].strip()].append(fila)
    return porfecha


def preflight(c):
    """Verifica que los objetos DESTINO existan y tengan las columnas esperadas, ANTES de tocar nada.

    Sin esto el fallo llegaria como un ProgrammingError crudo de SQLAlchemy a mitad del proceso.
    Y no se puede deducir desde la UI: si el endpoint revienta por tabla inexistente, el frontend
    pinta el MISMO "Compromiso P50 no disponible" que cuando la tabla existe pero esta vacia.
    """
    for obj in ("core.config_reporte", "core.fact_tabla_hoja"):
        # to_regclass devuelve NULL si no existe (no lanza excepcion) -> sirve para preguntar.
        if c.execute(sa.text("SELECT to_regclass(:o)"), {"o": obj}).scalar() is None:
            raise SystemExit(
                f"ERROR: no existe {obj} en esta BD.\n"
                f"       La BD no tiene el esquema de INGESTA. Creala con el DDL antes de cargar:\n"
                f"       INGESTA/Rep_Prod/db/ddl_v2_postgres.sql")
    cols = {r[0] for r in c.execute(sa.text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema='core' AND table_name='fact_tabla_hoja'"""))}
    faltan = sorted({"reporte_id", "hoja", "tabla_idx", "tabla_label", "dims", "fecha", "valor"} - cols)
    if faltan:
        raise SystemExit(f"ERROR: a core.fact_tabla_hoja le faltan columnas: {', '.join(faltan)}\n"
                         f"       El esquema no coincide con el esperado; revisa las migraciones.")
    n_rep = c.execute(sa.text("SELECT count(*) FROM core.config_reporte")).scalar()
    print(f"Destino  : core.fact_tabla_hoja OK | core.config_reporte OK ({n_rep} reportes)")
    if not n_rep:
        raise SystemExit("ERROR: core.config_reporte esta vacia -- esta BD no tiene reportes "
                         "ingeridos, asi que no hay a que asociar las filas (hay FK).")


def main():
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    dry = "--dry-run" in sys.argv
    ruta = os.path.abspath(args[0] if args else CSV_DEFAULT)
    if not os.path.isfile(ruta):
        raise SystemExit(f"ERROR: no existe el CSV {ruta}")

    porfecha = leer_csv(ruta)
    total_csv = sum(len(v) for v in porfecha.values())
    print(f"CSV      : {ruta}")
    print(f"Contenido: {total_csv} filas en {len(porfecha)} fechas "
          f"({min(porfecha)} -> {max(porfecha)})")
    print(f"Modo     : {'DRY-RUN (no escribe)' if dry else 'APLICAR'}\n")

    eng = get_engine()
    with eng.begin() as c:
        preflight(c)
        # fecha_reporte -> reporte_id en la BD DESTINO
        mapa = {str(r[0]): r[1] for r in c.execute(sa.text(
            "SELECT fecha_reporte, reporte_id FROM core.config_reporte"))}
        hay = {f: mapa[f] for f in porfecha if f in mapa}
        faltan = sorted(f for f in porfecha if f not in mapa)

        print(f"Fechas con reporte en destino : {len(hay)}")
        if faltan:
            print(f"Fechas SIN reporte (se omiten): {len(faltan)}")
            for f in faltan[:10]:
                print(f"   - {f}")
            if len(faltan) > 10:
                print(f"   ... y {len(faltan) - 10} mas")
            print("   (no se inventan encabezados: primero hay que ingerir esos reportes)")
        if not hay:
            raise SystemExit("\nNada que cargar: ninguna fecha del CSV existe en core.config_reporte.")

        borradas = insertadas = 0
        for fecha in sorted(hay):
            rid = hay[fecha]
            filas = porfecha[fecha]
            n_prev = c.execute(sa.text(
                "SELECT count(*) FROM core.fact_tabla_hoja WHERE reporte_id=:r AND hoja=:h"),
                {"r": rid, "h": HOJA}).scalar()
            if dry:
                print(f"   {fecha} (reporte_id={rid}): borraria {n_prev}, insertaria {len(filas)}")
                borradas += n_prev
                insertadas += len(filas)
                continue
            c.execute(sa.text("DELETE FROM core.fact_tabla_hoja WHERE reporte_id=:r AND hoja=:h"),
                      {"r": rid, "h": HOJA})
            borradas += n_prev
            c.execute(sa.text("""
                INSERT INTO core.fact_tabla_hoja (reporte_id, hoja, tabla_idx, tabla_label, dims, fecha, valor)
                VALUES (:reporte_id, :hoja, :tabla_idx, :tabla_label, CAST(:dims AS jsonb), :fecha, :valor)"""),
                [{"reporte_id": rid, "hoja": HOJA,
                  "tabla_idx": int(f["tabla_idx"]), "tabla_label": f["tabla_label"],
                  "dims": f["dims"],
                  "fecha": (f["fecha"].strip() or None),
                  "valor": (None if not f["valor"].strip() else f["valor"].strip())} for f in filas])
            insertadas += len(filas)

        # Solo ASCII en los prints: la consola de Windows (cp1252) convierte los signos raros en "?".
        print(f"\n{'[DRY-RUN] ' if dry else ''}Filas borradas: {borradas} | insertadas: {insertadas}")
        if dry:
            raise SystemExit("\nDRY-RUN: se descarta la transaccion. Corre sin --dry-run para aplicar.")

    # Verificacion posterior, en conexion nueva (ya commiteado)
    with eng.connect() as c:
        rid = c.execute(sa.text(
            "SELECT MAX(reporte_id) FROM core.fact_tabla_hoja WHERE hoja=:h"), {"h": HOJA}).scalar()
        fr = c.execute(sa.text("SELECT fecha_reporte FROM core.config_reporte WHERE reporte_id=:r"),
                       {"r": rid}).scalar()
        print(f"\nVerificacion: /analisis/president servira el reporte_id={rid} (corte {fr}).")
        for r in c.execute(sa.text("""
            SELECT dims->>'entidad' ent, dims->>'medida' med, valor
            FROM core.fact_tabla_hoja
            WHERE hoja=:h AND reporte_id=:r AND dims->>'medida' IN ('real_mes','base_p50')
              AND dims->>'entidad' IN ('Crudo','Gas','Blancos')
            ORDER BY ent, med"""), {"h": HOJA, "r": rid}):
            print(f"   {r[0]:9} {r[1]:9} {float(r[2]):>10.3f}")
        print("\nListo. Recarga el panel de analisis (Ctrl+F5) y el encabezado debe pintar las 3 tarjetas.")


if __name__ == "__main__":
    main()
