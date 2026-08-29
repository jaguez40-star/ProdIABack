"""Control 3 — revisión por lotes (el juez final). CLI, sin UI web (decisión del audit).

Uso (desde backend/):
    PYTHONPATH=. uv run python app/features/consulta_v2/golden/revisar_lote.py [--lote 30]

Corre senales.escanear() primero (P4: la cola queda priorizada justo cuando se va a
revisar), muestra la cola ordenada (sospecha → pendiente-LLM → resto) y por cada caso:
    1/2/3/4 = jerarquizar/cuantificar/analizar/desconocido (corrige)
    Enter   = confirmar la clasificación del motor
    n       = nota libre y luego veredicto · s = saltar · q = salir
La etiqueta de revisión es la VERDAD FINAL (cierra el caso aunque hubiera señales previas).
"""
import sys

import sqlalchemy as sa

from app.core.db import get_engine
from app.features.consulta_v2 import senales
from app.features.consulta_v2.log import poner_veredicto

GRUPOS = {"1": "jerarquizar", "2": "cuantificar", "3": "analizar", "4": "desconocido"}


def cola(lote: int):
    eng = get_engine()
    with eng.connect() as c:
        return c.execute(sa.text("""
            SELECT id, ts, texto_pregunta, grupo_asignado, capa_resolutora, veredicto, llm_diag
              FROM core.clasificacion_log
             WHERE veredicto IN ('pendiente', 'sospecha')
             ORDER BY (veredicto='sospecha') DESC,
                      (capa_resolutora IN ('llm','regex+llm')) DESC, ts
             LIMIT :n
        """), {"n": lote}).mappings().all()


def main():
    lote = 30
    if "--lote" in sys.argv:
        try:
            lote = int(sys.argv[sys.argv.index("--lote") + 1])
        except (IndexError, ValueError):
            pass

    nuevas = senales.escanear()
    print(f"Señales: {nuevas} sospecha(s) nueva(s) marcadas.\n")
    filas = cola(lote)
    if not filas:
        print("Cola vacía: no hay casos pendientes de veredicto.")
        return

    print(f"{len(filas)} caso(s) en cola. 1=jerarquizar 2=cuantificar 3=analizar "
          f"4=desconocido · Enter=confirmar · n=nota · s=saltar · q=salir\n")
    for f in filas:
        extra = f" · diag={f['llm_diag']}" if f["llm_diag"] else ""
        print(f"[{f['id']}] ({f['veredicto']} · {f['capa_resolutora']}{extra})")
        print(f"    «{f['texto_pregunta']}»  →  motor: {f['grupo_asignado']}")
        nota = None
        while True:
            r = input("    veredicto> ").strip().lower()
            if r == "q":
                print("Fin de la sesión de revisión.")
                return
            if r == "s":
                break
            if r == "n":
                nota = input("    nota> ").strip() or None
                continue
            if r == "":
                ok = poner_veredicto(f["id"], "confirmado_revision",
                                     fuente="revision", nota=nota)
                print("    ✓ confirmado_revision" if ok else "    ⚠ no se pudo escribir")
                break
            if r in GRUPOS:
                if GRUPOS[r] == f["grupo_asignado"]:
                    ok = poner_veredicto(f["id"], "confirmado_revision",
                                         fuente="revision", nota=nota)
                    print("    ✓ confirmado_revision (mismo grupo)" if ok else "    ⚠ error")
                else:
                    ok = poner_veredicto(f["id"], "corregido_revision",
                                         grupo_correcto=GRUPOS[r],
                                         fuente="revision", nota=nota)
                    print(f"    ✓ corregido_revision → {GRUPOS[r]}" if ok else "    ⚠ error")
                break
            print("    (1/2/3/4, Enter, n, s o q)")
        print()


if __name__ == "__main__":
    main()
