"""Fase 3 · Ejecución conversacional (DETERMINISTA, sin LLM).

Toma el intent resuelto (entidad rama A + producto/periodo/agregacion opcionales) y devuelve la cifra
REAL vs PPTO del mes, REUSANDO el mismo cálculo que alimenta el tablero 'Desempeño del mes'
(analisis.api.desempeno) -> coherencia chat<->tablero por construcción.

Frontera: aquí NO interviene el LLM. La prosa es 100% plantilla. El pulido con Gemma es iteración
posterior (irá detrás de un flag, igual que EJECUTIVO_USAR_LLM).
"""
from app.features.analisis.api import desempeno as _desempeno_ep, _estado

# intent.producto (extraído+groundeado por el LLM, minúsculas) -> producto del cálculo mensual.
# 'agua' NO existe a grano ECP (dim_tipo_producto solo CRUDO/GAS/BLANCOS) -> se rechaza.
_PROD_MAP = {"aceite": "CRUDO", "gas": "GAS", "blancos": "BLANCOS"}
_ESTADO_LABEL = {"ok": "Alineado", "warn": "Rezagado", "alert": "Foco", "": "sin meta"}

# D-A5 (2026-07-16): la respuesta DEBE decir el nivel. Un mismo nombre puede ser Campo y Activo con
# cifras muy distintas (APIAY: 269.035 bl como Campo vs 577.362 bl como Activo). Decir "en APIAY"
# a secas hacía indistinguibles las dos respuestas y volvía invisible la desambiguación.
_NIVEL_TEXTO = {"campo": "el Campo", "activo": "el Activo", "gerencia": "la Gerencia",
                "vicepresidencia": "la Vicepresidencia", "fuente": "la fuente", "pozo": "la fuente",
                "operador": "la operación de"}
_PERIODO_DEFAULT = {"este mes", "mes actual", "el mes", "este mes en curso", "mes en curso"}


def _fmt(n):
    try:
        return f"{float(n):,.0f}".replace(",", ".")
    except Exception:
        return str(n)


def _mtd_bopd(curva, producto):
    """(acumulado, promedio/día) del producto sobre los días CON reporte, desde la curva diaria.

    SOLO CRUDO (🔑 2026-07-16). Para BLANCOS la curva diaria y el hecho mensual NO reconcilian:
    APIAY-activo acumula 13.965 en 17 días contra un REAL de mes de 6.502 — el acumulado no puede
    superar al mes. Por campo: APIAY ~554/día (×17 ≈ 9.350) vs 4.543,9 del mes; GUATIQUIA ~95/día vs
    787,1; GAVAN ~70/día vs 821,2 — y las razones (3.8 / 3.7 / 2.6) no son constantes, así que no es
    un cambio de unidad. Sin explicación de dominio, ponerlos en la misma frase mostraría una
    contradicción. GAS queda fuera por lo mismo de siempre (unidad sin confirmar, ver _UNIDAD).
    En CRUDO sí reconcilian (MTD/REAL 52-55%; el 23% de TINAMU es real: paró el 5 de mayo).

    El promedio es el MISMO cálculo que `pace.promedio_dia` del tablero → no pueden divergir.
    (None, None) si no hay grano diario (filiales, vicepresidencias)."""
    if producto != "CRUDO":
        return None, None
    vals = [float(v or 0) for v in ((curva or {}).get("series") or {}).get(producto) or []]
    if not vals:
        return None, None
    return round(sum(vals)), round(sum(vals) / len(vals))


def _linea(p):
    est_key = _estado(p["cumplimiento"])          # MISMA umbralización del tablero (ok/warn/alert/"")
    est = _ESTADO_LABEL.get(est_key, "")
    pct = f"{p['cumplimiento']}%" if p["cumplimiento"] is not None else "s/d"
    return {
        "producto": p["producto"],
        "real": p["real"],
        "ppto": p.get("ppto"),          # la META en barriles: la respuesta la nombra, no solo el %
        "cumplimiento": p["cumplimiento"],
        "estado": est,
        "texto": f"{p['producto']}: {_fmt(p['real'])} · {pct} del presupuesto ({est})",
    }


def _linea_filial(p):
    """Línea de una filial: proyección de cierre vs su promedio 2026 (SIN presupuesto/meta)."""
    var = p.get("variacion_pct")
    pct = (f"{'+' if var >= 0 else ''}{var}%" if var is not None else "s/d")
    direc = p.get("direccion") or ""
    return {
        "producto": p["producto"],
        "real": p["proyeccion"],
        "ppto": p.get("promedio_2026"),
        "cumplimiento": None,                  # sin meta -> no narra con lexicón de presupuesto
        "estado": direc,
        "texto": (f"{p['producto']}: {_fmt(p['proyeccion'])} proyectado · {pct} vs su promedio 2026 "
                  f"({_fmt(p.get('promedio_2026'))}) · {direc}"),
    }


def _ejecutar_filial(resuelta: dict, producto: str | None, periodo: str | None,
                     _tendencia_fn=None) -> dict:
    """Rama B: tendencia de la filial (proyección de cierre vs su promedio 2026). Sin PPTO.
    _tendencia_fn: inyección para tests (evita la BD)."""
    if producto == "agua":
        return {"aplica": False,
                "texto": "El agua no se reporta a grano ECP (solo crudo, gas y blancos)."}
    if _tendencia_fn is None:
        from app.features.analisis.api import tendencia_filial as _tendencia_fn
    d = _tendencia_fn(empresa=resuelta["valor"], periodo=periodo)
    if not d.get("encontrada"):
        return {"aplica": False, "texto": f"No identifiqué la filial «{resuelta['valor']}»."}
    if d.get("sin_datos"):
        return {"aplica": False, "texto": f"«{resuelta['valor']}» no tiene producción registrada."}
    if d.get("sin_tendencia"):
        return {"aplica": False,
                "texto": (f"«{resuelta['valor']}» aún no tiene meses completos previos en 2026 para "
                          f"comparar su tendencia. Cuando cierre al menos un mes, te la muestro.")}
    quiero = _PROD_MAP.get(producto)
    filas = [p for p in d["por_producto"]
             if p.get("reporta") and (quiero is None or p["producto"] == quiero)]
    if quiero and not filas:
        return {"aplica": False, "texto": f"«{resuelta['valor']}» no reporta {producto} en el mes en curso."}
    if not filas:
        return {"aplica": False, "texto": f"«{resuelta['valor']}» no reporta crudo, gas ni blancos en el mes en curso."}

    lineas = [_linea_filial(p) for p in filas]
    avisos = []
    if d.get("n_base", 0) < 3:
        avisos.append(f"La tendencia se basa en {d['n_base']} mes{'es' if d['n_base'] != 1 else ''} "
                      f"completo{'s' if d['n_base'] != 1 else ''} de 2026 (poca historia todavía).")
    proyeccion = not d["completo"] and bool(d["ndias"])
    corte = ("mes cerrado" if d["completo"] else f"proyección · {d['ndias']}/{d['dim']} días")
    return {
        "aplica": True,
        "entidad": resuelta["valor"],
        "nivel": "filial",
        "nivel_texto": "la filial",
        "entidad_cualificada": f"la filial {resuelta['valor']}",
        "modo": "tendencia_filial",            # el gate de narración lo usa (Fase 1 = plantilla)
        "proyeccion": proyeccion,
        "encabezado": f"La filial {resuelta['valor']} · {d['periodo']} · {corte}",
        "lineas": lineas,
        "avisos": avisos,
        "pie": ("Comparo la proyección de cierre contra el promedio mensual de 2026. Las filiales no "
                "manejan presupuesto: la referencia es su propia historia del año."),
    }


def ejecutar(resuelta: dict, producto: str | None, periodo: str | None,
             agregacion: str | None = None, _desempeno_fn=None, _tendencia_fn=None) -> dict:
    """resuelta = {nivel, rama, valor}. Devuelve {aplica, texto|(encabezado,lineas,pie,avisos)}.
    _desempeno_fn/_tendencia_fn: inyección para tests (evita la BD)."""
    fn = _desempeno_fn or _desempeno_ep

    # 1) Rama B (filial): no hay PPTO -> se responde por TENDENCIA (proyección de cierre vs su
    #    promedio 2026), misma base que el panel de filiales. Python calcula, plantilla determinista.
    if resuelta.get("rama") == "B":
        return _ejecutar_filial(resuelta, producto, periodo, _tendencia_fn=_tendencia_fn)

    # 2) agua explícita -> rechazo honesto
    if producto == "agua":
        return {"aplica": False,
                "texto": "El agua no se reporta a grano diario ECP (solo crudo, gas y blancos). "
                         "¿Quieres crudo, gas o blancos?"}

    # 3) cálculo REUSANDO el del tablero. segmento='ecp' EXPLÍCITO (F1: desempeno es un route handler;
    #    sin pasarlo, 'segmento' sería un objeto Query, no la cadena "ecp").
    d = fn(entidad=resuelta["valor"], segmento="ecp", nivel=resuelta.get("nivel"), periodo=periodo)
    if not d.get("encontrada") or d.get("sin_datos"):
        return {"aplica": False, "texto": f"No tengo datos de producción para «{resuelta['valor']}»."}
    if d.get("sin_cierre"):
        return {"aplica": False,
                "texto": f"«{resuelta['valor']}» aún no tiene cierre mensual (REAL/PPTO) para el mes en curso."}

    mes = d["mes"]
    quiero = _PROD_MAP.get(producto)                       # None si no se pidió producto -> los 3
    filas = [p for p in d["por_producto"] if (quiero is None or p["producto"] == quiero)]

    # F4: producto pedido que la entidad NO reporta (real y ppto en 0) -> honesto, no "0 · s/d".
    if quiero and filas and filas[0]["real"] == 0 and filas[0]["ppto"] == 0:
        return {"aplica": False,
                "texto": f"«{resuelta['valor']}» no reporta {producto} en el mes en curso."}

    lineas = [_linea(p) for p in filas]

    # Ritmo diario REAL observado: media simple de la curva de `desempeno` (fact_produccion_dia_ecp).
    # NO sale del reporte: lo calcula Python. Y NO explica la proyección — AKACIAS lleva 112.725
    # BOPD-avg pero el reporte proyecta cerrar a 120.016 (asume que remonta el valle del 8-13 de
    # mayo). Por eso la frase lo acota SIEMPRE a "los N días con reporte": si se leyera como el ritmo
    # del mes, 112.725 x 31 = 3.494.460 no cuadraría con los 3.720.510 del titular y parecería un
    # error nuestro, cuando la diferencia es real.
    for l in lineas:
        l["mtd"], l["bopd_avg"] = _mtd_bopd(d.get("curva"), l["producto"])

    avisos = []
    if periodo and d.get("periodo_ok") is False:
        avisos.append("Aún no manejo periodos como año o semana; te muestro el mes en curso.")
    if agregacion == "promedio_diario":                    # F6: honesto si pidieron promedio
        avisos.append("Te doy el volumen del mes; el promedio diario llega en una próxima iteración.")

    # D-A4: campos del activo que producen SIN meta -> se DECLARAN (nunca se les inventa PPTO).
    # Sin esto, el % del activo compara un REAL que los incluye contra un PPTO que no los cubre.
    sin_meta = [x for x in (d.get("campos_sin_meta") or [])
                if quiero is None or x["producto"] == quiero]
    if sin_meta:
        nombres = ", ".join(sorted({x["campo"] for x in sin_meta}))
        vol = _fmt(sum(x["real"] for x in sin_meta))
        n = len({x["campo"] for x in sin_meta})
        avisos.append(
            f"Ojo con el cumplimiento: {n} campo{'s' if n > 1 else ''} de este activo "
            f"({nombres}) produce{'n' if n > 1 else ''} sin meta asignada, y aporta"
            f"{'n' if n > 1 else ''} {vol} barriles que no están en el presupuesto.")

    # 🔑 2026-07-16 · La cifra REAL del mes EN CURSO es de MES COMPLETO (una proyección de cierre),
    # NO el acumulado a la fecha. Probado contra la BD: en meses CERRADOS el REAL mensual coincide con
    # la suma de la curva diaria (feb/mar/abr 2026), pero en mayo (17/31 días) el REAL es ~1,8x la
    # suma diaria — y MTD/REAL da ~55% (=17/31) en TODAS las entidades, incluido el global ECP.
    # Decirlo "calculado sobre 17 días con reporte" hacía leer una proyección como acumulado:
    # CASTILLA lleva 3.767.374 barriles en 17 días, no los 6.860.389 que anunciaba la frase.
    # El % NO cambia (mes completo vs mes completo sigue siendo la comparación correcta); cambia lo
    # que la respuesta DICE que es la cifra.
    proyeccion = not mes["completo"] and bool(mes["dias_con_data"])
    corte = ("mes cerrado" if mes["completo"]
             else f"proyección · {mes['dias_con_data']}/{mes['dias_del_mes']} días")
    nivel = resuelta.get("nivel")
    etiqueta = _NIVEL_TEXTO.get(nivel, "")
    return {
        "aplica": True,
        "entidad": resuelta["valor"],
        "nivel": nivel,
        "nivel_texto": etiqueta,                           # "el Campo X" / "el Activo X" (D-A5)
        "entidad_cualificada": f"{etiqueta} {resuelta['valor']}".strip(),
        "mes": mes,
        "campos_sin_meta": sin_meta,
        "proyeccion": proyeccion,          # la cifra es estimada, no cerrada → cambia el verbo (narración)
        "encabezado": f"{etiqueta} {resuelta['valor']} · {mes['nombre']} {mes['anio']} · {corte}".strip(),
        "lineas": lineas,
        "avisos": avisos,
        "pie": (f"Proyección del cierre del mes: la cifra es del mes completo y el reporte lleva "
                f"{mes['dias_con_data']} de {mes['dias_del_mes']} días con curva diaria."
                if proyeccion else
                ("Cifra de cierre del mes." if mes["dias_con_data"]
                 else "Cifra de cierre mensual (sin curva diaria).")),
    }
