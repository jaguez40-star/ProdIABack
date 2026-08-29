"""Gate del clasificador de grupo (Motor Q v2 · Fase 1).

Uso (desde backend/, con backends ABAJO por la RAM — lección 8-jul):
    PYTHONPATH=. uv run python app/features/consulta_v2/golden/run_golden.py

Reporta: acierto total (gate >=90%) + % resuelto por Capa 1 (A4: si regex <50%,
engordar patrones antes de cerrar la fase — señal, no bloqueante).
H3: clasificar(log=False) — el runner NO escribe en la libreta.
"""
import pathlib

import yaml

from app.features.consulta_v2.maquina_q import clasificar


def ejecutar():
    """Corre el golden y devuelve el resultado como dict — sin imprimir nada.

    Extraído de main() para que el botón «Correr golden» de Test Clas
    (GET /consulta2/golden) reuse EXACTAMENTE este cálculo: un solo gate, una sola
    verdad. main() se limita a formatear esto para la consola.
    H3 se conserva: clasificar(log=False), el runner no escribe en la libreta.
    """
    p = pathlib.Path(__file__).with_name("clasificacion_golden.yaml")
    casos = yaml.safe_load(p.read_text(encoding="utf-8"))
    ok, por_capa = 0, {}
    fallos = []
    for c in casos:
        got = clasificar(c["pregunta"], log=False)
        acierto = got["grupo"] == c["esperado"]
        ok += acierto
        capa = got["capa_resolutora"]
        por_capa[capa] = por_capa.get(capa, 0) + 1
        if not acierto:
            fallos.append({
                "pregunta": c["pregunta"],
                "esperado": c["esperado"],
                "obtenido": got["grupo"],
                "capa": capa,
                "llm_diag": got.get("llm_diag"),
            })

    n = len(casos)
    n_regex = por_capa.get("regex", 0)
    return {
        "total": n,
        "aciertos": ok,
        "pct": 100 * ok // n if n else 0,
        "gate": 90,
        "pasa": (100 * ok // n if n else 0) >= 90,
        "n_regex": n_regex,
        "pct_regex": 100 * n_regex // n if n else 0,
        "n_filtro": por_capa.get("regex+filtro", 0),
        "n_llm": por_capa.get("llm", 0),
        "por_capa": por_capa,
        "fallos": fallos,
    }


def main():
    r = ejecutar()
    for f in r["fallos"]:
        print(f"XX [{f['esperado']:<12}] {f['pregunta']}"
              f"  -> {f['obtenido']} ({f['capa']}, diag={f['llm_diag']})")

    n = r["total"]
    print(f"\nEXACTITUD: {r['aciertos']}/{n} = {r['pct']}%   (gate: >=90%)")
    print(f"CAPA 1 dominio (regex):   {r['n_regex']}/{n} = {r['pct_regex']}%   "
          f"(A4: si <50%, engordar patrones — señal, no bloqueante)")
    print(f"CAPA 1 fuera de dominio (regex+filtro): {r['n_filtro']}/{n}")
    print(f"CAPA 2 (LLM):             {r['n_llm']}/{n}")


if __name__ == "__main__":
    main()
