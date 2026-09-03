"""cuantificar/niveles.py — N2 acumulado (Σ REAL de meses CERRADOS del año) para cualquier producto.
Reusa analisis.desempeno por mes → coherencia con el tablero (mismo patrón que ejecutor: 4 args
explícitos, sin factorizar un `_desempeno_core`).

HE4: el mes EN CURSO es PROYECCIÓN (T-1) — no se suma; se declara aparte (`en_curso`).
AF7: BLANCOS a grano MES es el agregado autoritativo (el ×4 es de grano DÍA, fuera de alcance)."""
from app.features.analisis.api import desempeno as _desempeno_ep

_MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre"]


def acumulado(resuelta: dict, dim_producto: str, _desempeno_fn=None, desde_mes: int = 1) -> dict:
    """dim_producto ∈ {"CRUDO","GAS","BLANCOS"} (nombre del producto en por_producto). Devuelve
    {aplica:True, real, ppto, meses:[nombres cerrados], en_curso:{nombre,real}|None, anio} o
    {aplica:False, texto}. Solo rama A; la rama B la rechaza el ejecutor.

    `desde_mes` (1-12) acota el ARRANQUE del acumulado. [2026-09-03 · VENTANA-MESES]
    Default 1 = enero = el YTD de siempre, byte a byte. Con 6 sale el acumulado junio→último
    mes cerrado, que es lo que pide «los últimos 3 meses» con techo en agosto.
    🔑 No se toca el FINAL del rango: sigue siendo el último mes con dato, y el mes EN CURSO
       sigue quedando fuera (HE4). Acotar el inicio no relaja esa regla — solo la ventana.
    """
    fn = _desempeno_fn or _desempeno_ep
    d0 = fn(entidad=resuelta["valor"], segmento="ecp", nivel=resuelta.get("nivel"), periodo=None)
    if not d0.get("encontrada") or d0.get("sin_datos") or d0.get("sin_cierre"):
        return {"aplica": False, "texto": f"No tengo datos de producción para «{resuelta['valor']}»."}
    anio, ultimo = d0["mes"]["anio"], d0["mes"]["mes"]
    total_real = total_ppto = 0.0
    meses, en_curso = [], None
    # [2026-09-03 · CURVA-ACUMULADA] La SUMA CORRIDA, mes a mes. El bucle ya traía el valor
    # mensual de cada mes y solo lo sumaba al total: aquí se conserva además el estado del
    # acumulado en cada paso, que es exactamente la curva creciente que el panel dibuja.
    # 🔑 Coste CERO: ni una consulta más. Es el mismo patrón de `comparativo_mes` (1-sep) —
    #    el dato ya se calculaba y se descartaba.
    # 🔑 HE4: solo entran los meses CERRADOS. El mes en curso queda fuera de la serie igual que
    #    queda fuera del total; meterlo aquí contradiría la regla que gobierna todo N2.
    serie_acum = []
    for m in range(max(1, desde_mes), ultimo + 1):
        dm = fn(entidad=resuelta["valor"], segmento="ecp", nivel=resuelta.get("nivel"), periodo=_MESES[m])
        if not dm.get("encontrada") or dm.get("sin_datos") or dm.get("sin_cierre"):
            continue
        fila = next((p for p in dm["por_producto"] if p["producto"] == dim_producto), None)
        if not fila or (fila["real"] == 0 and fila["ppto"] == 0):
            continue
        if dm["mes"]["completo"]:
            total_real += fila["real"]
            total_ppto += (fila["ppto"] or 0)
            meses.append(_MESES[m])
            serie_acum.append({
                "mes": _MESES[m][:3].capitalize(),   # "Ene" — mismo formato corto que ritmo_mensual
                "num": m,
                "real_acum": total_real,
                # `ppto_acum` es None si NINGÚN mes trajo presupuesto: dibujar una curva de ceros
                # afirmaría que el PPTO es cero, que es distinto de "no hay PPTO cargado".
                "ppto_acum": (total_ppto if total_ppto else None),
            })
        else:
            en_curso = {"nombre": _MESES[m], "real": fila["real"]}   # proyección; NO se suma (HE4)
    if not meses:
        return {"aplica": False,
                "texto": f"«{resuelta['valor']}» aún no tiene meses cerrados en {anio} para acumular."}
    return {"aplica": True, "real": total_real, "ppto": total_ppto, "meses": meses,
            "en_curso": en_curso, "anio": anio, "serie_acum": serie_acum}


def _serie_puntos(resuelta: dict, dim_producto: str, fn):
    """(puntos:[{mes,valor,num}], promedio, anio, proyeccion_mes, mes_actual) o (None,)*5.
    Reusa desempeno.ritmo_mensual (AF-3.1): la MISMA serie REAL mensual del panel.
    [2026-08-25] QV2-PANEL-MES: cada punto lleva su `num` (nº de mes) y se devuelve
    `mes_actual`, ambos ya presentes en `ritmo` y hasta ahora descartados. El pintor decide el
    corte sólido/punteado por NÚMERO de mes; sin esto el frontend tendría que invertir el
    nombre abreviado ("Ago" → 8) con un mapa propio, frágil y duplicado."""
    d0 = fn(entidad=resuelta["valor"], segmento="ecp", nivel=resuelta.get("nivel"), periodo=None)
    if not d0.get("encontrada") or d0.get("sin_datos") or d0.get("sin_cierre"):
        return None, None, None, None, None
    ritmo = d0.get("ritmo_mensual") or {}
    meses = ritmo.get("meses") or []
    nums = ritmo.get("meses_num") or []
    vals = (ritmo.get("series") or {}).get(dim_producto) or []
    puntos = [{"mes": meses[i], "valor": vals[i],
               "num": nums[i] if i < len(nums) else None}
              for i in range(min(len(meses), len(vals))) if vals[i] is not None]
    promedio = (ritmo.get("promedio_mes") or {}).get(dim_producto)
    # AF-3.3: el último punto es PROYECCIÓN si el mes más reciente no está cerrado (T-1).
    proyeccion_mes = puntos[-1]["mes"] if (puntos and not d0["mes"]["completo"]) else None
    return puntos, promedio, d0["mes"]["anio"], proyeccion_mes, ritmo.get("mes_actual")


def serie(resuelta: dict, dim_producto: str, _desempeno_fn=None) -> dict:
    """N3: la serie REAL mensual del producto en el año. Solo rama A (la rama B la rechaza el ejecutor)."""
    fn = _desempeno_fn or _desempeno_ep
    puntos, promedio, anio, proy, mes_act = _serie_puntos(resuelta, dim_producto, fn)
    if not puntos:
        return {"aplica": False,
                "texto": f"No tengo serie mensual de {dim_producto.lower()} para «{resuelta['valor']}»."}
    return {"aplica": True, "puntos": puntos, "promedio": promedio, "anio": anio,
            "proyeccion_mes": proy, "mes_actual": mes_act}


def variacion(resuelta: dict, dim_producto: str, _desempeno_fn=None) -> dict:
    """N4: deltas mes-a-mes sobre la serie REAL. Exige ≥2 puntos (AF-3.6).
    [2026-08-25] QV2-PANEL-MES: devuelve TAMBIÉN `puntos` (la serie de niveles), que ya se
    calculaba aquí y se descartaba. El waterfall necesita los niveles absolutos —el de partida
    y el de cierre son barras `total`—, y desde los deltas solos no se reconstruyen."""
    fn = _desempeno_fn or _desempeno_ep
    puntos, _prom, anio, proy, mes_act = _serie_puntos(resuelta, dim_producto, fn)
    if not puntos or len(puntos) < 2:
        return {"aplica": False,
                "texto": f"«{resuelta['valor']}» no tiene suficientes meses de {dim_producto.lower()} "
                         f"para calcular variación."}
    deltas = []
    for i in range(1, len(puntos)):
        v0, v1 = puntos[i - 1]["valor"], puntos[i]["valor"]
        d = v1 - v0
        pct = round(d / v0 * 100.0, 1) if v0 else None
        deltas.append({"de": puntos[i - 1]["mes"], "a": puntos[i]["mes"], "delta": d, "pct": pct})
    return {"aplica": True, "puntos": puntos, "deltas": deltas, "ultimo": deltas[-1],
            "anio": anio, "proyeccion_mes": proy, "mes_actual": mes_act}
