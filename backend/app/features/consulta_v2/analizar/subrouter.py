"""analizar/subrouter.py — separa las sub-intenciones de "analizar" (Python, sin LLM).

El clasificador (Etapa A) mete 5 preguntas bajo "analizar"; el sub-router elige la ruta. Fase 1
responde causal + proyeccion; diferidas/economia devuelven mensaje honesto de fase (el dispatcher
las intercepta); referencia [2026-08-13] responde/declina el P50 como CIFRA (no como causa) — ver
plan_p50_referencia_analizar_2026-08-13.md. Match por TOKEN/FRASE sobre texto normalizado (mismo
criterio que slots, AF-3.7)."""
from app.features.consulta_v2.normaliza import norm

_PROY = ("COMO VAMOS", "VAMOS A LLEGAR", "VAMOS A CERRAR", "VAMOS A ALCANZAR",
         "PROYECCION", "SE VE RECUPERACION", "VA A CERRAR", "COMO VA A CERRAR",
         "PROYECTA", "CAMINO DE", "TENDENCIA")
_DIFERIDAS = ("DIFERIDAS", "MANTENIMIENTO", "MANTENIMIENTOS")
_ECON = ("EBITDA", "NOPAT", "MARGEN", "RENTABILIDAD", "PLATA")
# [2026-08-13] P50 pedido como REFERENCIA (una cifra), no como tema causal. "P50" en el texto NO
# significa "análisis causal" — significa que el usuario eligió una referencia. Token exacto sobre
# `toks` (norm() NO retira '?'/'¿', HE7 — "…del P50?" no calzaría con un `in` de frase a secas).
_PUNCT = "¿?¡!.,;:()[]{}\"'`"
_REFERENCIA = ("P50",)
_CAUSAL_EXPL = ("POR QUE", "A QUE SE DEBE", "EXPLICA", "CAUSAS DE",
                "DETRACTORES", "QUE PASO CON", "PESAN", "PESA")


def sub_intencion(texto: str) -> str:
    """causal (default) | proyeccion | diferidas | economia | referencia. Precedencia:
    economia/diferidas ganan (son fuentes distintas), luego proyeccion, luego referencia
    (P50 sin señal causal explícita), luego causal."""
    t = norm(texto or "")
    if any(k in t for k in _ECON):
        return "economia"
    if any(k in t for k in _DIFERIDAS):
        return "diferidas"
    if any(k in t for k in _PROY):
        return "proyeccion"
    # Debajo de proyeccion a propósito: "¿vamos a llegar al P50?" sigue siendo proyección — solo
    # las preguntas que piden LA CIFRA caen aquí.
    toks = {w.strip(_PUNCT) for w in t.split()}
    if any(k in toks for k in _REFERENCIA) and not any(k in t for k in _CAUSAL_EXPL):
        return "referencia"
    return "causal"
