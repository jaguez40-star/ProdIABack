"""
renombrar_mes_reportes.py — Cambia el MES en la fecha del nombre de los reportes diarios.

Los reportes se llaman: YYYYMMDD_Reporte Diario de Producción.xlsm
Este script cambia el mes (por defecto Enero -> Junio) de la fecha del NOMBRE,
dejando los archivos en la MISMA carpeta (renombrado in place).

Uso:
    uv run python renombrar_mes_reportes.py
    (interactivo: pide la ruta de la carpeta)

Seguridad:
    - Muestra el plan (viejo -> nuevo) y pide confirmación antes de renombrar.
    - Valida que la fecha resultante exista (ej: no permite 31 de junio).
    - Aborta si algún nombre destino ya existe (evita sobrescribir).
"""

import re
import sys
from datetime import date
from pathlib import Path

# --- Configuración: qué mes cambiar por cuál ----------------------------------
MES_ORIGEN = 1   # Enero
MES_DESTINO = 6  # Junio

MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
    7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

# El nombre debe EMPEZAR por 8 dígitos (YYYYMMDD)
PATRON = re.compile(r"^(\d{4})(\d{2})(\d{2})(.*)$")


def pedir_carpeta() -> Path:
    ruta = input("Ruta de la carpeta con los reportes: ").strip().strip('"').strip("'")
    if not ruta:
        print("No se indicó ninguna ruta. Saliendo.")
        sys.exit(1)
    carpeta = Path(ruta)
    if not carpeta.is_dir():
        print(f"ERROR: la ruta no es una carpeta válida: {carpeta}")
        sys.exit(1)
    return carpeta


def construir_plan(carpeta: Path):
    """Devuelve (renombrar, sin_cambio, invalidos) listas de tuplas."""
    renombrar = []   # (origen: Path, destino: Path)
    sin_cambio = []  # Path (no coincide con el mes origen o no matchea patrón)
    invalidos = []   # (origen: Path, motivo: str)

    for archivo in sorted(carpeta.glob("*.xlsm")):
        m = PATRON.match(archivo.name)
        if not m:
            sin_cambio.append(archivo)
            continue
        anio, mes, dia, resto = m.group(1), m.group(2), m.group(3), m.group(4)
        if int(mes) != MES_ORIGEN:
            sin_cambio.append(archivo)
            continue
        # Validar que la fecha destino exista (ej: 31 de junio no existe)
        try:
            date(int(anio), MES_DESTINO, int(dia))
        except ValueError:
            invalidos.append((archivo, f"{dia}/{MES_DESTINO:02d} no existe en el calendario"))
            continue
        nuevo_nombre = f"{anio}{MES_DESTINO:02d}{dia}{resto}"
        renombrar.append((archivo, archivo.with_name(nuevo_nombre)))

    return renombrar, sin_cambio, invalidos


def main():
    print("=" * 70)
    print(f"  Renombrar reportes: {MESES_ES[MES_ORIGEN]} -> {MESES_ES[MES_DESTINO]}")
    print("=" * 70)

    carpeta = pedir_carpeta()
    renombrar, sin_cambio, invalidos = construir_plan(carpeta)

    if not renombrar and not invalidos:
        print(f"\nNo hay archivos de {MESES_ES[MES_ORIGEN]} para renombrar en:\n  {carpeta}")
        if sin_cambio:
            print(f"({len(sin_cambio)} .xlsm no coinciden con el mes origen o el patrón.)")
        sys.exit(0)

    # Detección de colisiones (destino ya existe)
    colisiones = [dst for _, dst in renombrar if dst.exists()]

    print(f"\nCarpeta: {carpeta}")
    print(f"\nSe renombrarán {len(renombrar)} archivo(s):\n")
    for origen, destino in renombrar:
        print(f"  {origen.name}")
        print(f"    -> {destino.name}")

    if invalidos:
        print(f"\n[AVISO] {len(invalidos)} archivo(s) NO se pueden renombrar (fecha inválida):")
        for origen, motivo in invalidos:
            print(f"  {origen.name}  ({motivo})")

    if colisiones:
        print(f"\n[ERROR] {len(colisiones)} nombre(s) destino YA existen en la carpeta:")
        for dst in colisiones:
            print(f"  {dst.name}")
        print("\nAbortado para no sobrescribir. Resuelve las colisiones y vuelve a intentar.")
        sys.exit(1)

    resp = input(f"\n¿Confirmas el renombrado de {len(renombrar)} archivo(s)? [s/N]: ").strip().lower()
    if resp not in ("s", "si", "sí", "y", "yes"):
        print("Cancelado. No se modificó nada.")
        sys.exit(0)

    hechos = 0
    for origen, destino in renombrar:
        origen.rename(destino)
        hechos += 1
    print(f"\nListo. {hechos} archivo(s) renombrado(s) en:\n  {carpeta}")


if __name__ == "__main__":
    main()
