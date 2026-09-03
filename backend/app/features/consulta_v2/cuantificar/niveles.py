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
    # [2026-09-03 · ACUM-MES-CERRADO] Meses PASADOS que se caen de la suma (sin cierre mensual o
    # sin fila del producto). Antes se descartaban en silencio; ahora se devuelven para que el
    # ejecutor los declare — un mes que falta en un acumulado cambia la cifra y el usuario no
    # tenía forma de saberlo.
    omitidos = []
    for m in range(max(1, desde_mes), ultimo + 1):
        dm = fn(entidad=resuelta["valor"], segmento="ecp", nivel=resuelta.get("nivel"), periodo=_MESES[m])
        if not dm.get("encontrada") or dm.get("sin_datos") or dm.get("sin_cierre"):
            if m < ultimo:
                omitidos.append(_MESES[m])
            continue
        fila = next((p for p in dm["por_producto"] if p["producto"] == dim_producto), None)
        if not fila or (fila["real"] == 0 and fila["ppto"] == 0):
            if m < ultimo:
                omitidos.append(_MESES[m])
            continue
        # [2026-09-03 · ACUM-MES-CERRADO] 🔴 Un mes ANTERIOR al del techo está cerrado, punto: su
        # REAL MENSUAL es la autoridad. Antes la condición era solo `dm["mes"]["completo"]`, que
        # NO mide eso — mide la COBERTURA DEL REPORTE DIARIO (`dias_con_data >= dias_del_mes`).
        #
        # Medido en Pruebas (CASTILLA, 2026): mayo (17/31 días) y junio (14/30) tienen cierre
        # mensual y REAL cargado, pero `completo=False` los sacaba de la suma Y los mandaba a la
        # rama `en_curso`, donde el mes siguiente los pisaba. Resultado: el acumulado decía
        # «enero–julio 2026 (5 meses cerrados) = 33.214.148 bbl» cuando el real de esos 7 meses
        # es 46.147.140 — un 28% por debajo, sin un solo aviso y con el rótulo del rango completo.
        #
        # 🔑 Es el cruce de granos que `desempeno()` prohíbe expresamente (api.py, Módulo 2):
        #    «los KPIs (REAL/cumplimiento) salen 100% de `mes`, y `día` se usa SOLO para la
        #    curva». Gatear una suma MENSUAL con un flag DIARIO viola esa regla. `completo`
        #    se conserva solo para el mes del techo, que es el único que puede estar en curso.
        if m < ultimo or dm["mes"]["completo"]:
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
            "en_curso": en_curso, "anio": anio, "serie_acum": serie_acum,
            "omitidos": omitidos}


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


def comparacion(resuelta: dict, dim_producto: str, cmp_: dict, _desempeno_fn=None) -> dict:
    """Los DOS periodos de una comparación, con su REAL y su PPTO. [2026-09-03 · COMPARACION]

    Dos llamadas a `desempeno`, una por periodo — el mismo patrón de `acumulado` (:44), que
    llama una vez por mes. Cero SQL nuevo: `_parse_periodo` ya entiende «julio 2025» (P2).

    🔑 Los 4 argumentos van EXPLÍCITOS. `desempeno` es un endpoint FastAPI y sus defaults son
       objetos Query(...); uno sobreviviente llegó al SQL y reventó con "cannot adapt type
       'Query'" (analisis/api.py:504-511). Mismo criterio que :25 y ejecutor.py:111.
    """
    fn = _desempeno_fn or _desempeno_ep
    out = {}
    for lado, periodo in (("a", cmp_["a"]), ("b", cmp_["b"])):
        d = fn(entidad=resuelta["valor"], segmento="ecp",
               nivel=resuelta.get("nivel"), periodo=periodo)
        if not d.get("encontrada") or d.get("sin_datos") or d.get("sin_cierre"):
            return {"aplica": False,
                    "texto": (f"No tengo cierre mensual de «{resuelta['valor']}» para "
                              f"{periodo}; sin ese dato la comparación sería media verdad.")}
        fila = next((p for p in d["por_producto"] if p["producto"] == dim_producto), None)
        if not fila or (fila["real"] == 0 and fila["ppto"] == 0):
            return {"aplica": False,
                    "texto": f"«{resuelta['valor']}» no reporta {dim_producto.lower()} en {periodo}."}
        mes = d["mes"]
        out[lado] = {
            "periodo": periodo, "real": fila["real"], "ppto": fila["ppto"] or 0,
            # [MES-CERRADO, 2026-09-03] `cerrado` ≠ `completo`. `completo` mide la cobertura del
            # reporte DIARIO; un mes ya cerrado puede tenerla incompleta (medido: CASTILLA mayo
            # 2026, 17/31) y seguir siendo definitivo. Aquí importa si la cifra es final.
            "cerrado": mes.get("cerrado", mes["completo"]),
            "dias_con_data": mes.get("dias_con_data"), "dias_del_mes": mes.get("dias_del_mes"),
            # 🔴 V2 — ¿hay reporte DIARIO de este mes? Para un periodo del año anterior el cierre
            # mensual puede existir sin que exista la tabla diaria: ahí `dias_con_data` vale 0 y
            # describir el mes como «0 de 31 días» sería falso sobre una cifra definitiva. Es la
            # misma familia del bug `completo` vs `cerrado` que costó una sesión el 2026-09-03.
            # `aplica_diario` lo dice `desempeno` desde `_ambito` (api.py:438); sin la clave se
            # asume que NO hay, que es el lado seguro (no se afirma nada sobre días).
            "diario_disponible": bool(d.get("aplica_diario")) and bool(mes.get("dias_con_data")),
            "nombre": mes.get("nombre"), "anio": mes.get("anio"),
        }
    a, b = out["a"], out["b"]
    delta = a["real"] - b["real"]
    return {"aplica": True, "a": a, "b": b, "delta": delta,
            "pct": (round(delta / b["real"] * 100.0, 1) if b["real"] else None),
            # Cumplimiento de cada lado contra SU propio presupuesto: comparar el REAL de julio
            # contra el PPTO de mayo no significa nada, y es el error fácil de esta pantalla.
            "cumpl_a": (round(a["real"] / a["ppto"] * 100.0, 1) if a["ppto"] else None),
            "cumpl_b": (round(b["real"] / b["ppto"] * 100.0, 1) if b["ppto"] else None)}


def serie_programa(resuelta: dict, dim_producto: str, _desempeno_fn=None) -> dict:
    """Serie mensual REAL **y PPTO** del año. [2026-09-03 · COMPARACION-PERIODOS, tipo 3]

    🔴 P7 — `ritmo_mensual` trae SOLO el REAL (`WHERE es.nombre = 'REAL'`, api.py:614) y todas
    las consultas de PPTO son de un solo mes (`WHERE m.fecha = :fin`). No existe una serie
    mensual de presupuesto en ninguna parte, así que se construye llamando a `desempeno` una
    vez por mes — el bucle de `acumulado` (:44-54), clonado, que lleva meses en producción.

    🔑 HE4: el mes EN CURSO entra en la serie pero marcado `cerrado: False`. A diferencia del
       acumulado —donde sumarlo falsearía un total— aquí es un punto de una curva y ocultarlo
       dejaría un hueco al final que el usuario leería como una caída.
    """
    fn = _desempeno_fn or _desempeno_ep
    d0 = fn(entidad=resuelta["valor"], segmento="ecp", nivel=resuelta.get("nivel"), periodo=None)
    if not d0.get("encontrada") or d0.get("sin_datos") or d0.get("sin_cierre"):
        return {"aplica": False,
                "texto": f"No tengo serie mensual de producción para «{resuelta['valor']}»."}
    anio, ultimo = d0["mes"]["anio"], d0["mes"]["mes"]
    puntos, omitidos = [], []
    for m in range(1, ultimo + 1):
        # 🔑 [2026-09-03 · fix] El AÑO va explícito, como en `comparacion` (:+30). Con el mes a
        #    secas («enero») el periodo queda a merced del año por defecto de `_parse_periodo`,
        #    y en una serie que rotula «real vs programa 2026» eso es justo lo que no puede
        #    quedar implícito. `acumulado` (:45) lo pasa sin año por herencia, no como patrón
        #    a imitar: allí el año ya viene fijado por el propio `desempeno` sin periodo.
        dm = fn(entidad=resuelta["valor"], segmento="ecp",
                nivel=resuelta.get("nivel"), periodo=f"{_MESES[m]} {anio}")
        if not dm.get("encontrada") or dm.get("sin_datos") or dm.get("sin_cierre"):
            omitidos.append(_MESES[m]); continue
        fila = next((p for p in dm["por_producto"] if p["producto"] == dim_producto), None)
        if not fila or (fila["real"] == 0 and fila["ppto"] == 0):
            omitidos.append(_MESES[m]); continue
        puntos.append({
            "mes": _MESES[m][:3].capitalize(), "num": m,
            "real": fila["real"], "ppto": (fila["ppto"] or None),
            "cumpl": (round(fila["real"] / fila["ppto"] * 100.0, 1) if fila["ppto"] else None),
            "cerrado": (m < ultimo or dm["mes"].get("cerrado", dm["mes"]["completo"])),
        })
    if not puntos:
        return {"aplica": False,
                "texto": f"«{resuelta['valor']}» no tiene meses con cierre en {anio}."}
    con_meta = [p for p in puntos if p["cumpl"] is not None]
    return {"aplica": True, "puntos": puntos, "anio": anio, "omitidos": omitidos,
            "cumpl_medio": (round(sum(p["cumpl"] for p in con_meta) / len(con_meta), 1)
                            if con_meta else None),
            "meses_bajo_meta": sum(1 for p in con_meta if p["cumpl"] < 100)}
