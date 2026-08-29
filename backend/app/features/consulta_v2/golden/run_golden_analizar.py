"""Gate del grupo ANALIZAR (Motor Q v2 · Fase 1). SIN LLM (fuerza CONSULTA_ANALIZA_LLM=false).

Valida (1) la sub-intención determinista (subrouter, sin BD) y (2) que las rutas causal/proyeccion
producen un cuerpo con la estructura esperada usando un `_ejecutivo_fn` FAKE (sin BD ni LLM).

⚠️ NO correr en dev con la BD (regla de RAM). Uso, desde backend/, en el SERVIDOR DE PRUEBAS:
    PYTHONPATH=. uv run python app/features/consulta_v2/golden/run_golden_analizar.py
"""
import os
os.environ.setdefault("CONSULTA_ANALIZA_LLM", "false")

import pathlib
import yaml

from app.features.consulta_v2.analizar import subrouter as _subrouter


def main():
    p = pathlib.Path(__file__).with_name("analizar_golden.yaml")
    casos = yaml.safe_load(p.read_text(encoding="utf-8"))
    ok = 0
    fallos = []
    for c in casos:
        sub = _subrouter.sub_intencion(c["pregunta"])
        acierto = sub == c["sub"]
        ok += acierto
        marca = "OK " if acierto else "XX "
        extra = "" if acierto else f"  -> sub={sub}"
        print(f"{marca}[{c['sub']:<11}] {c['pregunta']}{extra}")
        if not acierto:
            fallos.append(c["pregunta"])
    n = len(casos)
    pct = 100 * ok // n if n else 0
    print(f"\nEXACTITUD (sub-intención): {ok}/{n} = {pct}%   (gate: >=90%)")
    if fallos:
        print("\nFALLOS:")
        for f in fallos:
            print(f"  - {f}")


if __name__ == "__main__":
    main()
