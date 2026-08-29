"""Carga las preguntas del golden set en la libreta (core.clasificacion_log).

POR QUE EXISTE (2026-08-02)
  El golden set es el EXAMEN del clasificador y vive en un YAML; por diseno (H3) el runner
  llama clasificar(log=False) para no ensuciar la cola de revision. Pero el usuario necesita
  VER esos casos en la pestana «Test Clas» junto al trafico real.

  Este script los clasifica con log=True y usuario='golden' para que queden distinguibles
  del trafico real (que va con el nombre del usuario de la sesion).

IDEMPOTENTE: borra las filas 'golden' previas antes de insertar. Solo toca filas que el
  propio script creo (usuario='golden'); jamas roza el trafico real.

VEREDICTO: como el golden ya trae la respuesta correcta escrita a mano, cada fila se marca
  como confirmada/corregida segun coincida o no con lo esperado -> NO entran a la cola de
  pendientes (que debe seguir mostrando solo lo que de verdad falta revisar).

USO (desde la carpeta backend/):
    uv run python cargar_golden_libreta.py

  Apunta a la BD del .env vigente (dev local o 139) y lo dice antes de escribir.
"""
import sys
from pathlib import Path

import sqlalchemy as sa
import yaml

from app.core.db import get_engine
from app.features.consulta_v2.maquina_q import clasificar
from app.features.consulta_v2 import log as _log

GOLDEN = Path(__file__).parent / "app" / "features" / "consulta_v2" / "golden" / "clasificacion_golden.yaml"
USUARIO = "golden"


def main():
    eng = get_engine()
    print(f"BD objetivo: {eng.url.host}  db={eng.url.database}")

    casos = yaml.safe_load(GOLDEN.read_text(encoding="utf-8"))
    if isinstance(casos, dict):                 # tolera {casos: [...]} o lista suelta
        casos = casos.get("casos") or next(v for v in casos.values() if isinstance(v, list))
    print(f"Casos en el golden: {len(casos)}")

    with eng.begin() as c:
        n = c.execute(sa.text("DELETE FROM core.clasificacion_log WHERE usuario=:u"),
                      {"u": USUARIO}).rowcount
    if n:
        print(f"Limpieza: {n} filas 'golden' previas borradas.")

    ok = fallo = 0
    for i, caso in enumerate(casos, 1):
        texto = caso["pregunta"]
        esperado = caso["esperado"]
        d = clasificar(texto, usuario=USUARIO, conversation_id="golden", log=True)
        acierta = d["grupo"] == esperado
        ok, fallo = (ok + 1, fallo) if acierta else (ok, fallo + 1)

        if d["log_id"]:
            _log.poner_veredicto(
                d["log_id"],
                "confirmado_revision" if acierta else "corregido_revision",
                grupo_correcto=None if acierta else esperado,
                fuente="revision",
                nota="golden set — respuesta esperada escrita a mano",
            )
        marca = "OK " if acierta else "!! "
        print(f"  [{i:2}/{len(casos)}] {marca}{d['grupo']:<12} (esperado {esperado:<12}) "
              f"via {d['capa_resolutora']:<5} · {texto[:55]}")

    print(f"\nResumen: {ok} aciertos · {fallo} fallos de {len(casos)}")
    print("Listo. Recarga «Test Clas» en el navegador (Ctrl+F5).")
    return 0 if fallo == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
