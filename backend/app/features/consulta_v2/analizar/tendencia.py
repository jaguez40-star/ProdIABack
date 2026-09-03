"""analizar/tendencia.py — la LECTURA de la serie mensual: dirección, ritmo y suavizado.

Punto 2 de «inteligencia de tiempo» (tipos 4, 5 y 6). Cubre lo que la serie sola no dice:
si sube o baja, a qué ritmo, y si esa dirección es sostenida o ruido.

🔑 PURO. Los puntos entran como parámetro — quien los saca de `desempeno()["ritmo_mensual"]`
   es `respuesta_analizar`. Sin BD aquí, ni `date.today()`, ni imports de `analisis`.
🔑 HE4: solo entran meses CERRADOS. El mes en curso es una proyección y meterlo en la
   regresión inclinaría la recta con un dato incompleto — el error clásico de leer una
   tendencia sobre un mes a medio reportar. El filtro lo aplica el llamador, que es quien
   conoce `mes_actual`; este módulo confía en recibir la serie ya limpia.
"""

# Umbral bajo el cual la pendiente se lee como ESTABLE en vez de subida/bajada. 1% mensual
# sobre la media: por debajo de eso, la "tendencia" es ruido de operación, no una señal.
_UMBRAL_ESTABLE_PCT = 1.0
# R² mínimo para llamar SOSTENIDA a una dirección. Por debajo, la recta explica tan poco de
# la nube de puntos que afirmar "viene cayendo sostenidamente" sería una afirmación falsa:
# se rotula IRREGULAR y se dice el promedio, que sí es cierto.
_R2_SOSTENIDA = 0.5
# Ventana de la media móvil. 3 meses: suaviza el ruido mensual sin borrar un cambio real
# de nivel. Necesita 4 puntos para dar al menos 2 valores y que la curva se vea.
_VENTANA_MM = 3
_MIN_PUNTOS = 3          # con 2 puntos "la tendencia" es un delta, y eso ya lo da N4
_MIN_PUNTOS_MM = 4


def _regresion(valores: list) -> tuple:
    """Mínimos cuadrados sobre (i, valor) con i = 0..n-1. Devuelve (pendiente, intercepto, r2).

    La x es el ÍNDICE del punto, no el número de mes: así una serie con huecos (un mes sin
    dato) no distorsiona la escala — los meses presentes se tratan como pasos consecutivos,
    que es como los lee quien mira la curva.
    """
    n = len(valores)
    mx = (n - 1) / 2.0
    my = sum(valores) / n
    sxy = sum((i - mx) * (v - my) for i, v in enumerate(valores))
    sxx = sum((i - mx) ** 2 for i in range(n))
    if sxx == 0:
        return 0.0, my, 0.0
    b = sxy / sxx
    a = my - b * mx
    syy = sum((v - my) ** 2 for v in valores)
    # syy == 0 es una serie PLANA: la recta la explica perfectamente, r2 = 1.0. Devolver 0.0
    # la rotularía "irregular" cuando es lo más regular que existe.
    r2 = 1.0 if syy == 0 else max(0.0, min(1.0, 1 - sum(
        (v - (a + b * i)) ** 2 for i, v in enumerate(valores)) / syy))
    return b, a, r2


def media_movil(valores: list, ventana: int = _VENTANA_MM) -> list:
    """Media móvil simple, alineada al final. Los primeros `ventana-1` huecos van a None:
    Plotly con `connectgaps:false` no los dibuja, que es lo correcto — no hay media móvil
    de 3 meses en el primer mes, y rellenarla con el valor crudo sería inventar."""
    if len(valores) < ventana:
        return [None] * len(valores)
    out = [None] * (ventana - 1)
    for i in range(ventana - 1, len(valores)):
        out.append(sum(valores[i - ventana + 1:i + 1]) / ventana)
    return out


def leer(puntos: list) -> dict:
    """`puntos` = [{"mes": "Ene", "num": 1, "valor": 123.0}, ...] SOLO de meses cerrados.

    Devuelve {"aplica": True, direccion, pendiente, pct_mensual, pct_anualizado, r2,
              sostenida, media, primero, ultimo, n, serie_mm, valores, meses}
    o {"aplica": False, "texto": "..."} cuando no hay serie suficiente.
    """
    vals = [float(p["valor"]) for p in puntos if p.get("valor") is not None]
    meses = [p["mes"] for p in puntos if p.get("valor") is not None]
    if len(vals) < _MIN_PUNTOS:
        return {"aplica": False,
                "texto": (f"Solo tengo {len(vals)} mes{'es' if len(vals) != 1 else ''} cerrado"
                          f"{'s' if len(vals) != 1 else ''} con dato: hacen falta al menos "
                          f"{_MIN_PUNTOS} para leer una tendencia. Con dos meses lo que hay es "
                          f"una variación, y esa sí te la puedo dar.")}

    b, _a, r2 = _regresion(vals)
    media = sum(vals) / len(vals)
    pct_mensual = round(b / media * 100.0, 2) if media else 0.0
    # Anualizada por COMPOSICIÓN, no por ×12: una caída del 2% mensual NO es 24% anual sino
    # 21.5%. El ×12 exagera, y esta cifra se usa para hablar de declinación de campo.
    pct_anual = round(((1 + pct_mensual / 100.0) ** 12 - 1) * 100.0, 1)

    if abs(pct_mensual) < _UMBRAL_ESTABLE_PCT:
        direccion = "estable"
    elif b > 0:
        direccion = "al alza"
    else:
        direccion = "a la baja"

    mm = media_movil(vals) if len(vals) >= _MIN_PUNTOS_MM else [None] * len(vals)
    return {"aplica": True, "direccion": direccion, "pendiente": b,
            "pct_mensual": pct_mensual, "pct_anualizado": pct_anual, "r2": round(r2, 2),
            "sostenida": r2 >= _R2_SOSTENIDA, "media": media,
            "primero": meses[0], "ultimo": meses[-1], "n": len(vals),
            "serie_mm": mm, "valores": vals, "meses": meses}
