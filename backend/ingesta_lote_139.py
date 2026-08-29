"""Carga por lote NO INTERACTIVA, apta para correr en el servidor 139.

A diferencia de `app.cli batch` (que pide la ruta por `input()` y no puede
correr desatendido), este script:

  1. recibe la carpeta como ARGUMENTO,
  2. DESCARTA por firma de bytes los .xlsm cifrados con IRM/RMS corporativo
     (firma OLE2 `D0CF11E0`) — openpyxl los rechaza con "File is not a zip
     file" y tumbarían una fila del lote por cada uno,
  3. ingiere el resto reusando `ingerir_archivo()` — exactamente la misma
     lógica que la carga manual y que el batch de la CLI,
  4. es resiliente: un archivo con error no tumba el lote (criterio de
     `procesar_job` y de `cli.batch`).

La ingesta es IDEMPOTENTE (upsert "última gana" por clave natural), así que
volver a correrlo sobre archivos ya cargados no duplica nada.

Uso (desde INGESTA/Rep_Prod/backend/):

    uv run python ingesta_lote_139.py <carpeta>
    uv run python ingesta_lote_139.py <carpeta> --dry-run
    uv run python ingesta_lote_139.py <carpeta> --desde 20260723 --hasta 20260813

`--dry-run` solo clasifica LIBRE/CIFRADO y no toca la base de datos.
"""
import argparse
import sys
import time
from pathlib import Path

from app.core.logging import log
from app.features.ingesta.services import ingerir_archivo, _archivos_ordenados

# Firma de un .xlsm sano = ZIP ("PK\x03\x04"). Un archivo protegido con IRM/RMS
# es un contenedor OLE2 y empieza por D0CF11E0. No es contraseña: la clave la
# custodia el servidor RMS -> no hay descifrado offline posible.
FIRMA_ZIP = b"PK\x03\x04"


def _es_ingerible(ruta: Path) -> bool:
    """True si el archivo es un ZIP real (openpyxl podrá abrirlo)."""
    try:
        with open(ruta, "rb") as fh:
            return fh.read(4) == FIRMA_ZIP
    except OSError:
        return False


def _fecha_del_nombre(ruta: Path) -> str:
    """'20260813_Reporte....xlsm' -> '20260813'. Cadena vacía si no calza."""
    tope = ruta.name[:8]
    return tope if tope.isdigit() else ""


def main() -> int:
    ap = argparse.ArgumentParser(description="Ingesta por lote sin interacción.")
    ap.add_argument("carpeta", help="Carpeta con los .xlsm a cargar")
    ap.add_argument("--dry-run", action="store_true",
                    help="Solo clasifica LIBRE/CIFRADO; no escribe en la BD")
    ap.add_argument("--desde", default="", metavar="YYYYMMDD",
                    help="Ignora archivos con fecha de nombre anterior")
    ap.add_argument("--hasta", default="", metavar="YYYYMMDD",
                    help="Ignora archivos con fecha de nombre posterior")
    args = ap.parse_args()

    carpeta = Path(args.carpeta)
    if not carpeta.is_dir():
        print(f"ERROR: '{carpeta}' no es una carpeta valida")
        return 2

    archivos = _archivos_ordenados(carpeta)  # cronológico, mismo criterio que la CLI
    if not archivos:
        print(f"No se encontraron archivos .xlsm en '{carpeta}'")
        return 1

    # Filtro por rango de fechas del NOMBRE (opcional).
    if args.desde or args.hasta:
        recorte = []
        for a in archivos:
            f = _fecha_del_nombre(a)
            if not f:
                continue
            if args.desde and f < args.desde:
                continue
            if args.hasta and f > args.hasta:
                continue
            recorte.append(a)
        archivos = recorte

    # Clasificación por firma ANTES de tocar la BD.
    libres, cifrados = [], []
    for a in archivos:
        (libres if _es_ingerible(a) else cifrados).append(a)

    print(f"\nCarpeta: {carpeta}")
    print(f"Encontrados: {len(archivos)} | INGERIBLES: {len(libres)} | "
          f"CIFRADOS (IRM, se omiten): {len(cifrados)}\n")

    if cifrados:
        print("Omitidos por cifrado IRM/RMS (requieren liberacion por un usuario autorizado):")
        for a in cifrados:
            print(f"  - {a.name}")
        print()

    if not libres:
        print("No hay ningun archivo ingerible. Nada que hacer.")
        return 1

    if args.dry_run:
        print("Se cargarian (--dry-run, no se toco la BD):")
        for a in libres:
            print(f"  + {a.name}")
        return 0

    total = len(libres)
    print(f"Iniciando carga de {total} archivo(s)...\n")

    new = std = errores = 0
    fallidos: list[str] = []
    t0 = time.perf_counter()

    for i, a in enumerate(libres, start=1):
        ti = time.perf_counter()
        try:
            r = ingerir_archivo(a)
        except Exception as e:  # un archivo no debe tumbar el lote
            errores += 1
            fallidos.append(a.name)
            log.error("lote139.archivo.error", archivo=a.name, error=str(e))
            print(f"[{i}/{total}] ERROR en {a.name}: {e}", flush=True)
            continue
        new += r.tiene_raw
        std += (not r.tiene_raw)
        dt = time.perf_counter() - ti
        log.info("lote139.archivo.ok", archivo=a.name, reporte_id=r.reporte_id,
                 tipo=r.tipo_archivo, filas_por_tabla=r.filas_por_tabla)
        print(f"[{i}/{total}] {a.name} ({r.tipo_archivo}, {dt:.1f}s)", flush=True)

    mins = (time.perf_counter() - t0) / 60
    print(f"\nTOTAL: {total} archivos | NEW={new} STD={std} | "
          f"errores={errores} | tiempo={mins:.1f} min")
    print(f"Omitidos por cifrado: {len(cifrados)}")
    if fallidos:
        print(f"Archivos con error: {fallidos}")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
