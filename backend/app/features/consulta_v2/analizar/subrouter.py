"""analizar/subrouter.py — separa las sub-intenciones de "analizar" (Python, sin LLM).

El clasificador (Etapa A) mete 5 preguntas bajo "analizar"; el sub-router elige la ruta. Fase 1
responde causal + proyeccion; diferidas/economia devuelven mensaje honesto de fase (el dispatcher
las intercepta); referencia [2026-08-13] responde/declina el P50 como CIFRA (no como causa) — ver
plan_p50_referencia_analizar_2026-08-13.md. Match por TOKEN/FRASE sobre texto normalizado (mismo
criterio que slots, AF-3.7)."""
from app.features.consulta_v2.normaliza import norm

# [2026-09-03 · TENDENCIA] "TENDENCIA" SALE de _PROY. Estaba aquí desde el inicio y mandaba
# «¿cuál es la tendencia de Castilla?» a `proyeccion`, que responde el ritmo DIARIO del mes en
# curso («requiere 218.400 bbl/día en los días restantes») — otra cosa, dicha con seguridad.
# Verificado contra golden/analizar_golden.yaml: sus 3 casos de proyeccion casan con
# COMO VAMOS / VAMOS A CERRAR / PROYECCION. Ninguno depende de TENDENCIA.
_PROY = ("COMO VAMOS", "VAMOS A LLEGAR", "VAMOS A CERRAR", "VAMOS A ALCANZAR",
         "PROYECCION", "SE VE RECUPERACION", "VA A CERRAR", "COMO VA A CERRAR",
         "PROYECTA", "CAMINO DE")
# [2026-09-03 · TENDENCIA] La LECTURA de la serie mensual: dirección, ritmo, suavizado.
# 🔑 SIN "EVOLUCION" ni "MES A MES": son disparadores de N3 en cuantificar/slots.py:35-36 y
#    hoy responden la curva mensual correctamente. Robárselos cambiaría una respuesta buena.
# 🔑 SIN "SUBIO"/"BAJO"/"VARIO": son de N4 (waterfall de deltas, slots.py:32). N3/N4 dan la
#    serie; esta sub-intención la INTERPRETA. Son complementarias, no rivales.
_TEND = ("TENDENCIA", "DECLINACION", "DECLINANDO", "DECLINA", "MEDIA MOVIL",
         "PROMEDIO MOVIL", "SUAVIZAD", "RITMO DE CAIDA", "RITMO DE DECLIN",
         "COMO VIENE", "VIENE SUBIENDO", "VIENE BAJANDO", "VIENE CAYENDO",
         "VA SUBIENDO", "VA BAJANDO", "VA CAYENDO", "SIGUE CAYENDO", "SIGUE SUBIENDO")
_DIFERIDAS = ("DIFERIDAS", "MANTENIMIENTO", "MANTENIMIENTOS")
_ECON = ("EBITDA", "NOPAT", "MARGEN", "RENTABILIDAD", "PLATA")
# [2026-08-13] P50 pedido como REFERENCIA (una cifra), no como tema causal. "P50" en el texto NO
# significa "análisis causal" — significa que el usuario eligió una referencia. Token exacto sobre
# `toks` (norm() NO retira '?'/'¿', HE7 — "…del P50?" no calzaría con un `in` de frase a secas).
_PUNCT = "¿?¡!.,;:()[]{}\"'`"
_REFERENCIA = ("P50",)
_CAUSAL_EXPL = ("POR QUE", "A QUE SE DEBE", "EXPLICA", "CAUSAS DE",
                "DETRACTORES", "QUE PASO CON", "PESAN", "PESA")

# [2026-09-08 · P50-CUMPLIMIENTO-MES] Señal de que se pide EL CUMPLIMIENTO (una cifra cerrada
# de un mes), no la proyección de a dónde vamos a llegar. Medido: «¿cómo vamos contra el
# compromiso P50 de agosto?» matcheaba "COMO VAMOS" en _PROY y respondía el ritmo diario del
# mes EN CURSO — otra pregunta, contestada con seguridad, ignorando "agosto".
# 🔑 Match por SUBSTRING sobre la frase normalizada: "CUMPLI" cubre CUMPLIMIENTO, CUMPLIMOS,
#    CUMPLIENDO, CUMPLIO e INCUMPLIMOS (también es substring de esta — y está bien: quien
#    pregunta si incumplimos el P50 pide la misma cifra). Tupla MÍNIMA a propósito: las
#    variantes «qué tan cerca», «cuánto le dimos», «cómo quedó el real» NO matchean _PROY y ya
#    llegan a `referencia` por la puerta normal de abajo; listarlas aquí solo ensancharía la
#    superficie de falsos positivos sin ganar nada.
_CUMPLIMIENTO = ("CUMPLI", "COMPROMISO")


def sub_intencion(texto: str) -> str:
    """causal (default) | proyeccion | diferidas | economia | referencia | tendencia.
    Precedencia: economia/diferidas ganan (son fuentes distintas), luego TENDENCIA, luego
    CUMPLIMIENTO+P50 sin señal causal (referencia temprana, 2026-09-08), luego proyeccion,
    luego referencia (P50 sin señal causal explícita), luego causal."""
    t = norm(texto or "")
    if any(k in t for k in _ECON):
        return "economia"
    if any(k in t for k in _DIFERIDAS):
        return "diferidas"
    # [2026-09-03 · TENDENCIA] ANTES de proyeccion, no después. «¿cómo viene Castilla, vamos a
    # cerrar en meta?» trae las dos señales; la tendencia es la que el usuario nombró primero y
    # la que `proyeccion` no sabe responder. Al revés, `_PROY` volvería a capturarla y este
    # bloque no se alcanzaría nunca — que es exactamente el bug que este plan corrige.
    if any(k in t for k in _TEND):
        return "tendencia"
    # [2026-09-08 · P50-CUMPLIMIENTO-MES] ANTES de proyeccion, y SOLO con las TRES condiciones:
    # señal de cumplimiento, "P50" nombrado, y NINGUNA señal causal. Preguntar «cuánto
    # CUMPLIMOS del P50» es pedir una cifra ya cerrada; «cómo VAMOS» a secas es pedir una
    # proyección. Con las dos señales gana el cumplimiento: es lo más específico que se dijo.
    # 🔑 Deliberadamente estrecha, para no romper lo que ya funciona (cada línea tiene golden):
    #    · «¿cómo vamos este mes?»               → sin P50 → sigue en proyeccion (golden :15)
    #    · «¿vamos a llegar al P50?»             → sin cumplimiento → proyeccion (comentario :55)
    #    · «¿proyección de cierre del P50?»      → sin cumplimiento → proyeccion
    #    · «¿por qué no cumplimos el P50?»       → señal CAUSAL → causal, no una cifra
    #    · «¿cuánto cumplimos de la META?» (sin P50) → causal vs PPTO: en este sistema "meta"
    #      sin P50 es presupuesto (slots._referencia -> "PPTO"), y responder el P50 sería
    #      contestar otra pregunta. Por eso NO se mira "META" aquí, solo "P50".
    # 🔑 P50 se busca en `t` (substring) y no en `toks`: basta saber que la referencia está
    #    nombrada, y «…del P50?» pegado al signo debe contar igual. La puerta normal de
    #    `referencia` (más abajo, por token) no se toca.
    if (any(k in t for k in _CUMPLIMIENTO) and "P50" in t
            and not any(k in t for k in _CAUSAL_EXPL)):
        return "referencia"
    if any(k in t for k in _PROY):
        return "proyeccion"
    # Debajo de proyeccion a propósito: "¿vamos a llegar al P50?" sigue siendo proyección — solo
    # las preguntas que piden LA CIFRA caen aquí.
    toks = {w.strip(_PUNCT) for w in t.split()}
    if any(k in toks for k in _REFERENCIA) and not any(k in t for k in _CAUSAL_EXPL):
        return "referencia"
    return "causal"
