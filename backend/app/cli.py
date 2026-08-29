"""CLI de ingesta. Uso: uv run python -m app.cli archivo <ruta> | batch"""
import sys, time
from pathlib import Path
from app.core.config import get_settings
from app.core.logging import log
from app.features.ingesta.services import ingerir_archivo, _archivos_ordenados

def _pedir_carpeta() -> Path:
    """Solicitud 1: ruta de la carpeta con los archivos. Enter vacío usa el data_dir configurado."""
    default = get_settings().data_dir
    resp = input(f"Ruta de la carpeta con los archivos a cargar [{default}]: ").strip()
    return Path(resp) if resp else Path(default)

def main():
    if len(sys.argv) < 2:
        print("uso: python -m app.cli {archivo <ruta>|batch}"); return
    if sys.argv[1] == "archivo":
        print(ingerir_archivo(Path(sys.argv[2])).model_dump())
    elif sys.argv[1] == "batch":
        carpeta = _pedir_carpeta()
        if not carpeta.is_dir():
            print(f"ERROR: '{carpeta}' no es una carpeta válida"); return
        archivos = _archivos_ordenados(carpeta)  # H8: cronológico
        if not archivos:
            print(f"No se encontraron archivos .xlsm en '{carpeta}'"); return
        total = len(archivos)
        print(f"\n{total} archivo(s) encontrado(s) en '{carpeta}'. Iniciando carga...\n")

        # Solicitud 2: cargar todos los archivos mostrando la evolución de la carga en pantalla.
        new = std = errores = 0
        fallidos = []
        t0 = time.perf_counter()
        for i, a in enumerate(archivos, start=1):
            ti = time.perf_counter()
            try:
                r = ingerir_archivo(a)
            except Exception as e:   # un archivo no debe tumbar el lote (mismo criterio que procesar_job)
                errores += 1
                fallidos.append(a.name)
                log.error("cli.batch.archivo.error", archivo=a.name, error=str(e))
                print(f"[{i}/{total}] archivos cargados - ERROR en {a.name}: {e}")
                continue
            new += r.tiene_raw; std += (not r.tiene_raw)
            dt = time.perf_counter() - ti
            log.info("cli.batch.archivo.ok", archivo=a.name, reporte_id=r.reporte_id,
                      tipo=r.tipo_archivo, filas_por_tabla=r.filas_por_tabla)
            print(f"[{i}/{total}] archivos cargados - {a.name} ({r.tipo_archivo}, {dt:.1f}s)")
        total_min = (time.perf_counter() - t0) / 60
        print(f"\nTOTAL: {total} archivos | NEW={new} STD={std} | "
              f"errores={errores} | tiempo={total_min:.1f} min")  # H11: resumen de cobertura
        if fallidos:
            print(f"Archivos con error: {fallidos}")

if __name__ == "__main__":
    main()
