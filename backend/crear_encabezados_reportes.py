"""
crear_encabezados_reportes.py — Crea SOLO el encabezado (fila en core.config_reporte)
de los reportes de un mes que falten, para que el árbol de la pestaña Control muestre
el mes completo mientras se resuelve la ingesta por red.

QUÉ HACE (y qué NO):
  - Inserta 1 fila por día en core.config_reporte (fecha_reporte, archivo_nombre,
    tipo_archivo='NEW', tiene_raw, nivel_detalle='FULL'). El árbol año→mes→día se arma
    SOLO desde config_reporte, así que el día aparece de inmediato.
  - NO carga datos: los días creados así aparecen en el árbol pero al expandirlos NO
    tendrán hojas/tablas (no hay filas en fact_tabla_hoja). Es un encabezado "de vitrina".
  - NO toca reportes ya existentes: usa ON CONFLICT (fecha_reporte) DO NOTHING, así que
    los días con datos reales quedan intactos.

DÓNDE CORRE:
  Usa la MISMA conexión que la app (app.core.db.get_engine → lee el .env).
  En el servidor 139, el .env apunta a daily_report_prod (producción) → crea los
  encabezados en la BD que ve la presentación. Ejecutar EN 139.

USO:
    cd INGESTA/Rep_Prod/backend
    uv run python crear_encabezados_reportes.py
"""

import sys
from calendar import monthrange
from datetime import date

import sqlalchemy as sa
from app.core.db import get_engine

# --- Configuración: qué mes rellenar -----------------------------------------
ANIO = 2026
MES = 6  # Junio
NOMBRE_ARCHIVO = "{fecha}_Reporte Diario de Producción.xlsm"  # {fecha} = YYYYMMDD
TIPO_ARCHIVO = "NEW"      # badge que se ve en el árbol (NEW | STD)
TIENE_RAW = True
NIVEL_DETALLE = "FULL"    # FULL | AGREGADO | SIN_ECP

MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
    7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

INSERT = sa.text("""
    INSERT INTO core.config_reporte
        (fecha_reporte, archivo_nombre, tipo_archivo, tiene_raw, nivel_detalle)
    VALUES (:fr, :an, :tp, :raw, :nv)
    ON CONFLICT (fecha_reporte) DO NOTHING
    RETURNING reporte_id
""")


def main():
    dias_mes = monthrange(ANIO, MES)[1]
    print("=" * 66)
    print(f"  Crear encabezados faltantes — {MESES_ES[MES]} {ANIO} ({dias_mes} días)")
    print("=" * 66)

    engine = get_engine()

    # 1) Qué días ya existen (no se tocan)
    with engine.connect() as conn:
        existentes = {
            r[0].day
            for r in conn.execute(
                sa.text("SELECT fecha_reporte FROM core.config_reporte "
                        "WHERE EXTRACT(YEAR FROM fecha_reporte)=:a "
                        "AND EXTRACT(MONTH FROM fecha_reporte)=:m"),
                {"a": ANIO, "m": MES},
            )
        }

    faltantes = [d for d in range(1, dias_mes + 1) if d not in existentes]

    print(f"\nBase de datos: {engine.url.render_as_string(hide_password=True)}")
    print(f"Ya existen (no se tocan): {sorted(existentes) or '—'}")
    print(f"Se crearán encabezados para: {faltantes or '—'}")

    if not faltantes:
        print("\nNada que crear: el mes ya está completo. Saliendo.")
        return

    resp = input(f"\n¿Confirmas crear {len(faltantes)} encabezado(s) en "
                 f"{MESES_ES[MES]} {ANIO}? [s/N]: ").strip().lower()
    if resp not in ("s", "si", "sí", "y", "yes"):
        print("Cancelado. No se modificó nada.")
        return

    creados = 0
    with engine.begin() as conn:
        for d in faltantes:
            fr = date(ANIO, MES, d)
            yyyymmdd = fr.strftime("%Y%m%d")
            rid = conn.execute(INSERT, {
                "fr": fr,
                "an": NOMBRE_ARCHIVO.format(fecha=yyyymmdd),
                "tp": TIPO_ARCHIVO,
                "raw": TIENE_RAW,
                "nv": NIVEL_DETALLE,
            }).scalar()
            if rid is not None:
                creados += 1

    print(f"\nListo. {creados} encabezado(s) creado(s) en {MESES_ES[MES]} {ANIO}.")
    print("Refresca la pestaña Control para ver el mes completo.")
    print("NOTA: estos días no tienen datos (fact_tabla_hoja) — al expandirlos saldrán vacíos.")


if __name__ == "__main__":
    main()
