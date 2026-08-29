"""Gate del grupo CUANTIFICAR (Motor Q v2 · Fase 1 · N1 puntual + N2 acumulado).

SIN LLM (fuerza CONSULTA_CUANT_LLM=false antes de importar — el intro cordial se prueba aparte,
en el servidor de pruebas). Corre contra la BD real (resolver + ejecutor, coherencia con el
tablero vía analisis.desempeno): NO fija cifras en bbl (mutables, un mes que cierra las cambiaría)
— valida ESTRUCTURA: nivel_temporal detectado + tipo de resultado. Patrón de golden/run_golden.py
(el del clasificador de grupo).

⚠️ NO correr en dev (regla de RAM): abre conexión a Postgres varias veces (una por caso ejecutado
con nivel N2, varias más por N1). Uso, desde backend/, en el SERVIDOR DE PRUEBAS:
    PYTHONPATH=. uv run python app/features/consulta_v2/golden/run_golden_cuantificar.py
"""
import os
os.environ.setdefault("CONSULTA_CUANT_LLM", "false")

import pathlib

import yaml

from app.features.consulta_v2.cuantificar import ejecutor as _ejecutor
from app.features.consulta_v2.cuantificar import resolver as _resolver
from app.features.consulta_v2.cuantificar import slots as _slots


def _clasificar_resultado(resuelta, res):
    if resuelta is None:
        return "sin_entidad"
    if resuelta.get("ambiguo"):
        return "ambiguo"
    if not res.get("aplica"):
        texto = (res.get("texto") or "").lower()
        if "filial" in texto:
            return "rechazo_filial"
        if "solo cuantifico crudo" in texto:
            return "rechazo_producto"
        return "rechazo_otro"
    return "aplica"


def main():
    p = pathlib.Path(__file__).with_name("cuantificar_golden.yaml")
    casos = yaml.safe_load(p.read_text(encoding="utf-8"))
    ok = 0
    fallos = []
    for c in casos:
        slots = _slots.extraer_slots(c["pregunta"])
        nivel_ok = slots["nivel_temporal"] == c["nivel_temporal"]
        prod_ok = slots["producto"] == c.get("producto", "crudo")
        ref_ok = slots.get("referencia", "PPTO") == c.get("referencia", "PPTO")

        resuelta = _resolver.resolver_unico(c["entidad"] or c["pregunta"])
        if resuelta is None or resuelta.get("ambiguo"):
            res = {"aplica": False, "texto": ""}
        else:
            res = _ejecutor.ejecutar(resuelta, slots)
        resultado = _clasificar_resultado(resuelta, res)
        resultado_ok = resultado == c["resultado"]

        acierto = nivel_ok and prod_ok and ref_ok and resultado_ok
        ok += acierto
        marca = "OK " if acierto else "XX "
        extra = ""
        if not acierto:
            extra = (f"  -> nivel={slots['nivel_temporal']} producto={slots['producto']} "
                     f"ref={slots.get('referencia')} resultado={resultado}")
        print(f"{marca}[{c['resultado']:<16}] {c['pregunta']}{extra}")
        if not acierto:
            fallos.append(c["pregunta"])

    n = len(casos)
    pct = 100 * ok // n if n else 0
    print(f"\nEXACTITUD: {ok}/{n} = {pct}%   (gate: >=90%)")
    if fallos:
        print("\nFALLOS:")
        for f in fallos:
            print(f"  - {f}")


if __name__ == "__main__":
    main()
