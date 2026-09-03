"""cuantificar/ranking.py — N5 RANKING (Motor Q v2, Grupo 2).

Eje ORTOGONAL a N1-N4: N1-N4 miden UNA entidad a lo largo del tiempo; N5 ordena VARIAS entidades por
magnitud dentro de un mes. FB-1 (patrón de Analizar Fase 2): PORTA su propia query sobre
core.fact_produccion_mes_ecp. NO importa `analisis.api._gap_campo` (es una closure dentro de
`ejecutivo()`, no reutilizable) ni reusa `desempeno` (que es por-entidad).

v1: SOLO ranking GLOBAL ECP; niveles rankeables campo y activo. Scoped-a-entidad y niveles
gerencia/VP/pozo DECLINAN honesto (el dispatcher los corta antes de llegar aquí).

🔑 SEMÁNTICA DE ORDEN (bug real del plan v1, corregido). NO se modela como (eje, asc/desc): esa
combinación devolvía lo CONTRARIO a lo pedido en "qué campos se quedaron más cortos vs presupuesto"
(daba los que SUPERARON el presupuesto). Se modela como (metrica, direccion) con reglas explícitas:
  metrica=real · direccion=top     -> REAL descendente          ("los que más producen")
  metrica=real · direccion=bottom  -> REAL ascendente, real>0    ("la más baja producción")
  metrica=gap  · direccion=bottom  -> gap ASCENDENTE (más negativo primero) = MAYOR FALTANTE  [DEFAULT]
  metrica=gap  · direccion=top     -> gap DESCENDENTE (más positivo primero) = MAYOR EXCEDENTE
En metrica=gap el DEFAULT es `bottom` (faltante): es la intención dominante. "mayor faltante" debe dar
faltante aunque diga "mayor" -> por eso las palabras de faltante MANDAN sobre "MAYOR".

Terceros: el reporte incluye campos operados por terceros (QUIFA/Frontera es #3 en crudo-mayo,
verificado contra BD 2026-08-04). Se INCLUYEN y se ROTULA el operador cuando no es Ecopetrol.

Regla madre: Python calcula y ordena; el LLM solo el intro. La lista es VERBATIM.
"""
import calendar
import re

import sqlalchemy as sa

from app.core.db import get_engine, get_ops_engine
from app.features.consulta_v2.normaliza import norm
from app.features.consulta_v2.cuantificar.validador import fmt_valor

# --- Vocabulario de detección (sobre texto NORMALIZADO: MAYÚSCULAS sin tildes) ---------------
# [2026-08-04] +MAYORES/MENORES (plural): "los mayores productores de crudo" no calzaba con el
# singular MAYOR (comparación EXACTA de tokens, no substring) y devolvía None.
_SUPERLATIVO = ("MAYOR", "MAYORES", "MENOR", "MENORES", "MAS", "MENOS", "TOP", "RANKING",
                "MAXIMA", "MAXIMO", "MINIMA", "MINIMO", "MEJORES", "PEORES", "MEJOR", "PEOR",
                "PRIMEROS", "ULTIMOS")
_NIVEL_TOK = {"CAMPO": "campo", "CAMPOS": "campo", "ACTIVO": "activo", "ACTIVOS": "activo",
              "GERENCIA": "gerencia", "GERENCIAS": "gerencia",
              "VICEPRESIDENCIA": "vicepresidencia", "VICEPRESIDENCIAS": "vicepresidencia",
              "POZO": "pozo", "POZOS": "pozo"}

# Dirección BOTTOM. Token exacto (AF-3.7: nunca substring — "BAJO" ∈ "trabajo").
# [2026-08-04] +MENORES (plural, mismo motivo que _SUPERLATIVO arriba).
_BOTTOM_TOK = ("MENOR", "MENORES", "MENOS", "PEOR", "PEORES", "MINIMA", "MINIMO", "BAJA", "BAJO",
               "BAJAS", "CORTO", "CORTOS", "CORTAS", "FALTANTE", "FALTANTES", "REZAGADOS",
               "REZAGADO", "INCUMPLIERON", "ULTIMOS")
_BOTTOM_PHRASE = ("LOS QUE MENOS", "POR DEBAJO", "QUEDARON CORTOS", "DE ABAJO")
# Dirección TOP explícita en métrica gap (excedente). Sin esto, gap = faltante por defecto.
_TOP_GAP_TOK = ("SUPERARON", "SUPERO", "EXCEDIERON", "EXCEDENTE", "EXCEDIO", "SOBRECUMPLIERON")
_TOP_GAP_PHRASE = ("POR ENCIMA",)

# [2026-09-01] DISTRIBUCIÓN — familia ORTOGONAL al superlativo. Una distribución no pide el
# extremo, pide el reparto: no tiene dirección (las lista todas), así que NO entra en
# _SUPERLATIVO ni en _BOTTOM_TOK. Cae en el default metrica=real · direccion=top, que es
# exactamente el panel de participación que el motor ya sabe pintar (dona + % individual +
# cola declarada) — ver ranking.py:303 y el bullet _b_concentracion.
# Medido: 13 de 25 formas de pedir la distribución no activaban el ranking (ver
# vocabulario_distribucion_error.md).
# ⚠️ NO incluir PESA/PESAN: 'QUE CAMPOS PESAN' es patrón de ANALIZAR (patrones_grupo.yaml:206)
# y la exclusión de :66-71 es una decisión explícita del usuario del 2026-08-24. Se respeta.
# ⚠️ PORCENTAJE / PORCENTUAL / PORCENTUALMENTE / % son 4 TOKENS distintos (match exacto,
# AF-3.7): hay que listarlos todos. `_PUNCT` (:68) no incluye '%', así que "en %," tokeniza
# a '%' limpio.
# ⚠️ DESGLOS*: cobertura PARCIAL a propósito. "desglósame la producción por campo" llega aquí;
# "desglósame el activo Castilla por campo" lo atrapa antes jerarquizar (patrones_grupo.yaml:93)
# y "desglose por campo" del gap lo usa el panel de Analizar (respuesta_analizar.py:57).
_DISTRIBUCION = ("DISTRIBUYE", "DISTRIBUYEN", "DISTRIBUCION", "DISTRIBUIDA", "DISTRIBUIDO",
                 "REPARTE", "REPARTEN", "REPARTO", "REPARTEME", "REPARTIDA", "REPARTIDO",
                 "PARTICIPACION", "PARTICIPA", "PARTICIPAN",
                 "PORCENTAJE", "PORCENTUAL", "PORCENTUALMENTE", "%",
                 "CONTRIBUCION", "CONTRIBUYE", "CONTRIBUYEN",
                 "PROPORCION", "FRACCION", "SHARE",
                 "DESGLOSE", "DESGLOSA", "DESGLOSAME",
                 "REPRESENTA", "REPRESENTAN")

# [2026-09-01] DOMINANCIA — verbos de liderazgo. SÍ son superlativos semánticos (piden el
# extremo), pero se agrupan aparte para que el diff diga de dónde salió cada palabra.
# ⚠️ NO incluir DOMINAS: 'QUE TEMAS ... DOMINAS' es el detector de capacidades
# (capacidades.py:57), el primer guard del motor. DOMINA/DOMINAN no colisionan (aquel exige
# 'QUE TEMAS' a ≤24 chars).
_DOMINANCIA = ("ENCABEZA", "ENCABEZAN", "LIDERA", "LIDERAN", "LIDERO", "LIDERARON",
               "PUNTEROS", "PUNTERAS", "DOMINA", "DOMINAN")

# Métrica gap. 🔑 SIN "META": 'META\b' es patrón del grupo ANALIZAR y gana por precedencia_colision
# (analizar > cuantificar) → una pregunta con "meta" nunca llega aquí. Incluirla crearía la ilusión
# de soporte. Ver §11 · D6.
_METRICA_GAP = ("PPTO", "PRESUPUESTO", "FALTANTE", "FALTANTES", "CORTO", "CORTOS", "CORTAS",
                "EXCEDENTE", "INCUMPLIERON", "SUPERARON")

_PROD_TOK = {"GAS": "gas", "BLANCOS": "blancos", "BLANCO": "blancos"}   # crudo = default
_MESES = ("enero febrero marzo abril mayo junio julio agosto septiembre setiembre "
          "octubre noviembre diciembre").split()
_MES_NUM = {m: i + 1 for i, m in enumerate(_MESES)}
_MES_NUM["setiembre"] = 9
_PROD_MAP = {"crudo": "CRUDO", "gas": "GAS", "blancos": "BLANCOS"}
_PUNCT = "¿?¡!.,;:()[]{}\"'`"

_NIVEL_DIFERIDO = {
    "gerencia": ("El ranking por gerencia llega en una próxima fase: en la jerarquía oficial "
                 "(robustez) varias «gerencias» del reporte son en realidad vicepresidencias, y "
                 "compararlas sin reconciliar mezclaría niveles distintos. Puedo rankear campos o "
                 "activos."),
    "vicepresidencia": ("El ranking por vicepresidencia llega en una próxima fase. Puedo rankear "
                        "campos o activos."),
    "pozo": ("No puedo rankear pozos: el grano de pozo no está en el reporte diario, que llega "
             "hasta el detalle por campo. Puedo rankear campos o activos."),
}
_NIVEL_PLURAL = {"campo": "campos", "activo": "activos"}


def _tokens(t: str) -> set:
    return {p for p in (w.strip(_PUNCT) for w in t.split()) if p}


def detectar(texto: str):
    """Reconoce la FORMA N5 (determinista, sin LLM y sin BD). Devuelve dict o None.

    dict = {nivel_ranking, metrica, direccion, top_n, producto, periodo_texto}
           o {nivel_ranking, diferido: str} si el nivel pedido no se rankea en v1.
    Exige SUPERLATIVO **y** sustantivo de NIVEL: sin ambos no es N5 y la pregunta sigue su curso
    normal por N1-N4 (p.ej. "¿cuál es la mayor producción de Rubiales?" -> N1 de Rubiales).
    """
    t = norm(texto or "")
    toks = _tokens(t)
    # DESVIACIÓN puntual del código §5.1 (documentada, ver reporte del Executor 2026-08-04): el gate
    # original solo miraba _SUPERLATIVO/TOP/RANKING, pero _TOP_GAP_TOK/_BOTTOM_TOK ya definen
    # palabras (SUPERARON/INCUMPLIERON/EXCEDIERON/FALTANTE…) que por sí solas también implican
    # comparación entre entidades cuando van con un sustantivo de nivel — sin esto, "qué campos
    # superaron el presupuesto" (caso exigido en V-DETECT/§8 del plan) daba None.
    if not (any(s in toks for s in _SUPERLATIVO) or any(s in toks for s in _BOTTOM_TOK)
            or any(s in toks for s in _TOP_GAP_TOK)
            or any(s in toks for s in _DISTRIBUCION) or any(s in toks for s in _DOMINANCIA)
            or "TOP" in t or "RANKING" in t):
        return None
    nivel = next((_NIVEL_TOK[k] for k in _NIVEL_TOK if k in toks), None)
    if nivel is None:
        return None
    if nivel in _NIVEL_DIFERIDO:
        return {"nivel_ranking": nivel, "diferido": _NIVEL_DIFERIDO[nivel]}

    metrica = "gap" if any(k in toks for k in _METRICA_GAP) else "real"
    es_distribucion = any(k in toks for k in _DISTRIBUCION)
    es_bottom = any(k in toks for k in _BOTTOM_TOK) or any(p in t for p in _BOTTOM_PHRASE)
    if metrica == "gap":
        # DEFAULT bottom (faltante). Solo palabras explícitas de excedente lo suben a top.
        es_top_gap = (any(k in toks for k in _TOP_GAP_TOK)
                      or any(p in t for p in _TOP_GAP_PHRASE))
        direccion = "top" if (es_top_gap and not es_bottom) else "bottom"
    else:
        direccion = "bottom" if es_bottom else "top"

    m = re.search(r"\bTOP\s+(\d+)\b", t) or re.search(r"\b(\d+)\s+(?:CAMPOS?|ACTIVOS?)\b", t)
    if m:
        top_n = max(1, min(20, int(m.group(1))))
    elif es_distribucion:
        # [2026-09-03] Una DISTRIBUCIÓN nunca pide un solo elemento: pide el reparto entre
        # todos. El singular gramatical de "¿qué participación tiene CADA CAMPO?" engañaba a
        # la heurística de abajo y devolvía top_n=1 -> el redactor imprimía "1 de 128 campos
        # genera el 13,7%" (medido en Pruebas 2026-09-03). El singular solo significa "uno"
        # cuando la señal es un SUPERLATIVO ("¿qué campo produce MÁS crudo?" -> 1).
        top_n = 5
    else:
        # [2026-09-03] MANDA EL NIVEL QUE SE RANKEA, no cualquier sustantivo de nivel presente.
        # Medido en Pruebas: «¿cuáles CAMPOS del ACTIVO Apiay producen más crudo?» daba top_n=1
        # —el `or` leía el ACTIVO singular como si se pidiera UN activo— y el chat respondía una
        # cifra única en vez del panel. Pero ahí «activo» es el CONTENEDOR del scope, no lo que
        # se cuenta: `nivel` (ya resuelto en :139) dice qué se rankea, y solo ese sustantivo
        # decide el singular. Es la misma familia del bug de «cada campo» (mismo día), por el
        # otro operando del `or`; se corrige en la raíz en vez de añadir otra excepción.
        # 🔑 Sigue dando 1 en el singular REAL: «¿qué campo del activo Castilla produce más?»
        # rankea campos y dice CAMPO en singular -> 1. Verificado en 8 casos.
        if nivel == "activo":
            # [2026-09-03 · regla C] Un ACTIVO es un agregado (agrupa campos): «¿cuál es el
            # activo que más produce?» pide ver el REPARTO entre los grandes, no un nombre
            # suelto. Medido en Pruebas: devolvía «RUBIALES 12.176.071» como cifra única. Sin
            # número explícito (ese caso ya salió por `if m:` arriba, :157), el ranking de
            # activos muestra el Top 5. El singular gramatical («cuál ES EL activo») no lo
            # colapsa a 1 — a diferencia del CAMPO suelto, que sí quiere un nombre.
            top_n = 5
        else:
            # CAMPO suelto sin contenedor: «¿cuál es el campo que más produce?» SÍ quiere un
            # nombre. El singular real manda. (El contenedor «del activo X» no llega hasta aquí
            # como singular: lo resuelve la guarda del scope en respuesta_cuantificar.py.)
            singular = "CAMPO" in toks and "CAMPOS" not in toks
            top_n = 1 if singular else 5

    producto = next((_PROD_TOK[k] for k in _PROD_TOK if k in toks), "crudo")
    per = next((mm for mm in _MESES if mm in (texto or "").lower()), None)
    return {"nivel_ranking": nivel, "metrica": metrica, "direccion": direccion,
            "top_n": top_n, "producto": producto, "periodo_texto": per,
            # [2026-09-03 · H9] ¿El top_n lo escribió el usuario («top 3 campos») o salió de la
            # heurística gramatical? La guarda del scope necesita distinguirlo: solo puede
            # ampliar el top_n al activo completo cuando NO fue pedido a mano. `m` es el match
            # del número explícito de :156; si casó, el top_n vino de ahí.
            "top_n_explicito": m is not None}


def _fin_mes(c, periodo_texto):
    """(fin, anio, mes, nombre_mes, es_proyeccion) del mes a rankear, o None si no hay datos.
    Default = último mes con REAL. es_proyeccion: el mes elegido es el del último dato diario y ese
    corte no llega a fin de mes (S22: el REAL del mes en curso es un cierre PROYECTADO)."""
    maxreal = c.execute(sa.text("""
        SELECT MAX(m.fecha) FROM core.fact_produccion_mes_ecp m
        JOIN core.dim_escenario es ON es.escenario_id = m.escenario_id
        WHERE es.nombre = 'REAL'""")).scalar()
    if maxreal is None:
        return None
    anio, mes = maxreal.year, maxreal.month
    if periodo_texto and periodo_texto in _MES_NUM:
        mes = _MES_NUM[periodo_texto]
    dim = calendar.monthrange(anio, mes)[1]
    fin = f"{anio:04d}-{mes:02d}-{dim:02d}"
    maxdia = c.execute(sa.text("SELECT MAX(fecha) FROM core.fact_produccion_dia_ecp")).scalar()
    es_proy = bool(maxdia and maxdia.year == anio and maxdia.month == mes and maxdia.day < dim)
    return fin, anio, mes, _MESES[mes - 1], es_proy


# nivel_ranking -> SQL. Mismo fact que el resto de Cuantificar. Solo campo/activo en v1.
# 🔑 El nivel `activo` NO inventa operador (el v1 hardcodeaba 'ECOPETROL' sin verificarlo): devuelve
# NULL y el formateador simplemente no rotula operador a nivel activo. Ver §11 · D5.
_SQL = {
    "campo": """
        SELECT COALESCE(NULLIF(TRIM(f.campo),''), f.nombre) AS ent,
               SUM(CASE WHEN es.nombre='REAL' THEN m.volumen ELSE 0 END) AS vreal,
               SUM(CASE WHEN es.nombre='PPTO' THEN m.volumen ELSE 0 END) AS vppto,
               MAX(f.operador) AS operador
        FROM core.fact_produccion_mes_ecp m
        JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = m.tipo_producto_id
        JOIN core.dim_escenario es     ON es.escenario_id     = m.escenario_id
        JOIN core.dim_fuente f         ON f.fuente_id         = m.fuente_id
        WHERE m.fecha = :fin AND tp.nombre = :prod AND es.nombre IN ('REAL','PPTO')
        GROUP BY 1""",
    "activo": """
        SELECT a.activo AS ent,
               SUM(CASE WHEN es.nombre='REAL' THEN m.volumen ELSE 0 END) AS vreal,
               SUM(CASE WHEN es.nombre='PPTO' THEN m.volumen ELSE 0 END) AS vppto,
               NULL AS operador
        FROM core.fact_produccion_mes_ecp m
        JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = m.tipo_producto_id
        JOIN core.dim_escenario es     ON es.escenario_id     = m.escenario_id
        JOIN core.dim_fuente f         ON f.fuente_id         = m.fuente_id
        JOIN core.map_campo_activo a
             ON a.campo_norm = UPPER(COALESCE(NULLIF(TRIM(f.campo),''), f.nombre))
        WHERE m.fecha = :fin AND tp.nombre = :prod AND es.nombre IN ('REAL','PPTO')
        GROUP BY 1""",
}


# [2026-09-03] JERARQUÍA: ops.wells_attributes es la FUENTE ÚNICA DE VERDAD y está al día
# (regla del usuario, 2026-09-03): lo que no esté ahí, NO EXISTE. Vive en OTRA BD
# (get_ops_engine), así que NO se puede JOIN-ear con core.* — se lee aparte y se cruza en
# Python.
# ⚠️ DOS FILTROS OBLIGATORIOS, medidos el 2026-09-03:
#   1. `vice_presidency NOT LIKE 'V%'` — conviven DOS jerarquías. La rama V* es la VIEJA
#      (435 pozos activos y 6.219 abandonados, contra 15.438 activos de la G*). Sin este
#      filtro CASTILLA sale con dos activos distintos y el panel es incorrecto.
#   2. `vice_presidency <> '0'` — filas basura (vp/ger/act = '0') que duplican 5 campos.
# Quedan 2 ambigüedades reales (AULLADOR, SARDINATA): un campo en dos activos. Se respetan
# como dice la fuente — aparecerá en el panel de ambos. Fuera de alcance de este plan.
_SQL_CAMPOS_DE_ACTIVO = """
    SELECT DISTINCT UPPER(TRIM(field)) AS campo
    FROM ops.wells_attributes
    WHERE field IS NOT NULL
      AND vice_presidency NOT LIKE 'V%'
      AND vice_presidency <> '0'
      AND UPPER(TRIM(active)) = :activo
"""


def campos_de_activo(activo: str) -> set:
    """Campos que pertenecen al activo, según la fuente única (ops.wells_attributes).

    Devuelve un set de nombres NORMALIZADOS (UPPER, sin espacios extremos) o `set()` si la
    BD de robustez no está disponible o el activo no existe. Nunca lanza: sin jerarquía el
    llamador degrada al ranking global, que es el comportamiento de hoy.
    """
    if not activo:
        return set()
    try:
        eng = get_ops_engine()
        with eng.connect() as c:
            rows = c.execute(sa.text(_SQL_CAMPOS_DE_ACTIVO), {"activo": norm(activo)}).all()
        return {(r[0] or "").strip() for r in rows if r[0]}
    except Exception:
        return set()   # degradación con gracia (mismo criterio que _cargar_vp_robustez)


def calcular(slots: dict, _engine=None, campos_scope: set | None = None) -> dict:
    """Ejecuta el ranking. Devuelve el contrato N5 (aplica=True) o {aplica:False, texto}."""
    nivel = slots.get("nivel_ranking")
    if nivel not in _SQL:
        return {"aplica": False, "texto": slots.get("diferido", "Ese ranking no está soportado.")}
    prod = slots.get("producto", "crudo")
    prod_es = _PROD_MAP.get(prod, "CRUDO")
    unidad = "MSCF" if prod == "gas" else "bbl"
    metrica, direccion, top_n = slots["metrica"], slots["direccion"], slots["top_n"]
    plural = _NIVEL_PLURAL[nivel]
    scope_label = slots.get("scope_label")   # p.ej. "el Activo CASTILLA"; None = ranking global

    eng = _engine or get_engine()
    with eng.connect() as c:
        info = _fin_mes(c, slots.get("periodo_texto"))
        if info is None:
            return {"aplica": False, "texto": "No hay datos de producción cargados para rankear."}
        fin, anio, mes, nombre_mes, es_proy = info
        rows = c.execute(sa.text(_SQL[nivel]), {"fin": fin, "prod": prod_es}).all()

    datos = [((r[0] or "").strip(), float(r[1] or 0), float(r[2] or 0),
              (r[3] or "").strip() if r[3] else "")
             for r in rows if (r[1] or r[2])]
    # [2026-09-03] SCOPE por activo: se filtra en PYTHON, no en SQL — la jerarquía vive en
    # otra BD (ops.wells_attributes) y no se puede JOIN-ear. `None` = ranking global (el
    # comportamiento de siempre); un set vacío NO llega aquí (el llamador degrada antes).
    if campos_scope:
        datos = [d for d in datos if d[0].upper() in campos_scope]
    con_real = [d for d in datos if d[1] > 0]          # CERO TRAICIONERO: 0 no es "poca producción"
    sin_registro = len(datos) - len(con_real)

    # GUARDA de resultado vacío (el v1 no la tenía → habría dicho "Los 0 campos…"). Ver §11 · D3.
    if not con_real:
        return {"aplica": False, "texto": (
            f"No hay producción de {prod} registrada en {nombre_mes} {anio} para rankear {plural}.")}

    if metrica == "gap":
        pool = [d for d in con_real if (d[1] - d[2]) != 0]
        clave = lambda d: d[1] - d[2]
        # bottom = gap ascendente (más negativo primero = mayor faltante); top = descendente.
        reverse = (direccion == "top")
    else:
        pool = con_real
        clave = lambda d: d[1]
        reverse = (direccion == "top")
    if not pool:
        return {"aplica": False, "texto": (
            f"Todos los {plural} con producción de {prod} en {nombre_mes} {anio} coinciden con su "
            f"presupuesto; no hay faltantes ni excedentes que rankear.")}

    ordenado = sorted(pool, key=clave, reverse=reverse)
    top = ordenado[:top_n]

    # Concentración: SOLO tiene sentido en métrica real + dirección top ("los que más producen
    # concentran X%"). En bottom sería una cifra engañosa. Ver §11 · D7.
    conc = None
    if metrica == "real" and direccion == "top":
        total_real = sum(d[1] for d in con_real)
        if total_real:
            conc = round(sum(d[1] for d in top) / total_real * 100, 1)

    def _op(operador):
        o = (operador or "").upper()
        if not o:
            return {"txt": None, "es_ecp": None}          # operador desconocido: no se afirma nada
        if "ECOPETROL" in o or o == "ECP":
            return {"txt": None, "es_ecp": True}          # ECP = lo normal, sin rótulo
        return {"txt": operador.title(), "es_ecp": False}

    items = []
    for i, d in enumerate(top, 1):
        ol = _op(d[3]) if nivel == "campo" else {"txt": None, "es_ecp": None}
        items.append({"pos": i, "entidad": d[0], "valor": round(d[1]), "ppto": round(d[2]),
                      "gap": round(d[1] - d[2]), "operador": ol["txt"], "es_ecp": ol["es_ecp"]})

    return {
        "aplica": True, "grupo": "cuantificar", "nivel": "N5",
        "nivel_ranking": nivel, "metrica": metrica, "direccion": direccion, "top_n": top_n,
        "producto": prod, "unidad": unidad,
        "periodo_label": f"{nombre_mes} {anio}", "es_proyeccion": es_proy,
        "items": items, "total_universo": len(pool), "sin_registro": sin_registro,
        "concentracion_pct": conc, "scope_label": scope_label,
    }


def _join_y(nombres) -> str:
    """['A'] -> 'A' · ['A','B'] -> 'A y B' · ['A','B','C'] -> 'A, B y C'."""
    nombres = list(nombres)
    if not nombres:
        return ""
    if len(nombres) == 1:
        return nombres[0]
    return ", ".join(nombres[:-1]) + " y " + nombres[-1]


# --- Bullets analíticos de la rama `metrica == "real"` (plan_ranking_lectura_chat_2026-08-12) -----
# El chat LEE, el panel DESGLOSA: los 5 nombres + volúmenes ya viven en el panel derecho (mismo dict
# `res` que aquí). Estos 3 helpers son PUROS (no tocan BD ni LLM) y cada uno devuelve None cuando su
# regla no se cumple — el bullet correspondiente simplemente no se emite, nunca se afirma lo
# contrario ("no hay outlier", "distribución plana"). Máximo 1 cifra liviana por bullet.

def _b_concentracion(res) -> str | None:
    """Bullet A. None si concentracion_pct no aplica (real+bottom, gap)."""
    conc = res.get("concentracion_pct")
    if conc is None:
        return None
    n, total = len(res["items"]), res["total_universo"]
    plural = _NIVEL_PLURAL[res["nivel_ranking"]]
    conc_txt = str(conc).replace(".", ",")
    # A4: tramos calibrados contra 6 casos reales medidos en la BD (41,2% a 93,3% según producto y
    # nivel — 5 de 6 superaron el 70%). Un corte único en 50 diría "alta" casi siempre y el bullet
    # sería constante, por tanto inútil.
    if conc < 50:
        etiqueta, cola = "Concentración fuerte pero no extrema", "el grueso sigue viniendo de la cola larga"
    elif conc <= 75:
        etiqueta, cola = "Concentración alta", "el resto queda repartido entre bastantes más"
    else:
        etiqueta, cola = "Concentración muy alta", f"muy pocos {plural} explican casi todo el volumen"
    # Concordancia con top_n=1 (caso frecuente: cualquier pregunta en singular, ranking.py:125-127).
    # 🔑 El número que rige es el 1, NO los 128: el sustantivo va en PLURAL porque cuenta el universo
    # ("1 de 128 campos"), pero el verbo va en SINGULAR porque el sujeto es "1". Pluralizar el
    # sustantivo ("1 de 128 campo") es el error opuesto y suena peor que el original.
    verbo = "generan" if n != 1 else "genera"
    return f"⟦{etiqueta}⟧ {n} de {total} {plural} {verbo} el {conc_txt}% del total producido — {cola}."


def _b_dominancia(res) -> str | None:
    """Bullet B. None si len(items)<2 o items[1]['valor']<=0 (A7)."""
    items = res["items"]
    if len(items) < 2 or items[1]["valor"] <= 0:
        return None
    top_sum = sum(it["valor"] for it in items)
    if not top_sum:
        return None
    v1, v2 = items[0]["valor"], items[1]["valor"]
    # A5: el gate es el PESO del #1 dentro del top (estable), no v1/v2 (frágil — crudo-campo daba
    # exactamente 1,80, en el filo; crudo-activo daba 1,05 sin marcar outlier pese a que el #1 pesa
    # el 30% del top).
    peso1 = v1 / top_sum * 100
    # Umbral 30 (no 40): con un top de 5 el reparto uniforme es 20%, así que 30% ya es dominancia
    # clara. Medido sobre los 6 casos reales, 40 dejaba fuera 3 — incluido crudo/campo (34%), que es
    # justamente el caso de referencia donde RUBIALES SÍ destaca. A 30 emite en 5 de 6 y sigue
    # excluyendo el bottom (10%: ahí el #1 es el MENOR y destacarlo sería absurdo).
    if peso1 < 30:
        return None
    n = len(items)
    frase = f"⟦{items[0]['entidad']} destaca dentro del propio Top {n}⟧ Concentra el {round(peso1)}% del grupo"
    ratio = v1 / v2
    if ratio >= 1.5:
        frase += " y más que duplica al segundo" if ratio >= 2 else " y casi duplica al segundo"
    # A6: matiz de "pelotón apretado" — condicional, y solo si hay al menos 3 ítems (A7: con 2,
    # #2 es también el último y el spread daría 0 = "plana" absurda). El spread real varía de 23%
    # (crudo-campo) a 91% (gas-activo): 5 de 6 casos NO son pelotones, así que nunca se afirma lo
    # contrario si el umbral no se cumple.
    if n >= 3:
        vlast = items[-1]["valor"]
        spread = (v2 - vlast) / v2 * 100
        if spread < 30:
            frase += (f", mientras que del #2 al #{n} las cifras están tan apretadas que cambios "
                      "modestos pueden reordenarlas")
    return frase + "."


def _b_terceros(res) -> str | None:
    """Bullet C. None si nivel_ranking != 'campo' o no hay es_ecp is False (A7).

    NO incluye la glosa de corchetes ("Los campos entre corchetes...") — esa vive en el pie común
    (A1): la rama gap depende de ella y moverla aquí la dejaría sin glosar en un ranking por
    faltante.
    """
    if res["nivel_ranking"] != "campo":
        return None
    # Tri-estado (A7): es_ecp puede ser True/False/None (operador desconocido). Solo False cuenta
    # como tercero — `not it["es_ecp"]` habría contado los None como terceros, afirmación falsa.
    terceros = [it for it in res["items"] if it["es_ecp"] is False]
    if not terceros:
        return None
    campos_txt = _join_y(it["entidad"] for it in terceros)
    operadores, vistos = [], set()
    for it in terceros:
        if it["operador"] and it["operador"] not in vistos:
            vistos.add(it["operador"])
            operadores.append(it["operador"])
    ops_txt = _join_y(operadores) if operadores else "terceros"
    verbo = "es operado" if len(terceros) == 1 else "son operados"
    return (f"⟦Dependencia de terceros⟧ {campos_txt} {verbo} por {ops_txt}, "
            "fuera del control operacional directo.")


def formatear_cuerpo(res: dict) -> str:
    """Cuerpo VERBATIM (Python; el LLM no lo toca)."""
    plural = _NIVEL_PLURAL[res["nivel_ranking"]]
    prod, unidad = res["producto"], res["unidad"]
    n = len(res["items"])
    proy = " (cierre proyectado del mes en curso)" if res["es_proyeccion"] else ""

    if res["metrica"] == "gap":
        que = "mayor faltante" if res["direccion"] == "bottom" else "mayor excedente"
        cab = (f"{'El' if n == 1 else 'Los'} {n if n > 1 else ''} {plural if n > 1 else plural[:-1]} "
               f"con {que} de {prod} frente al presupuesto en {res['periodo_label']}{proy}").replace("  ", " ")
        piezas = []
        for it in res["items"]:
            signo = "−" if it["gap"] < 0 else "+"
            op = f" [{it['operador']}]" if it["operador"] else ""
            piezas.append(f"{it['pos']}) {it['entidad']}{op} {signo}{fmt_valor(abs(it['gap']), prod)}")
        linea = f"{cab} (en {unidad}):\n" + "\n".join(piezas)
    else:
        # [2026-08-12] El chat LEE, el panel DESGLOSA (plan_ranking_lectura_chat_2026-08-12): los 5
        # nombres + volúmenes ya viven en el panel derecho (mismo dict `res`) — el mensaje entrega
        # hasta 3 bullets analíticos derivados en Python en vez de repetir la tabla. Cabecera+lista
        # retiradas: el chip de cabecera del panel ya dice producto/periodo/nivel.
        bullets = [b for b in (_b_concentracion(res), _b_dominancia(res), _b_terceros(res)) if b]
        linea = "\n\n".join(bullets)

    # Pie común (A1: la rama gap depende de él TAL CUAL — universo y glosa de terceros no se tocan,
    # o un ranking por faltante quedaría con "[Frontera Energy]" sin explicar).
    pie = f"Sobre {res['total_universo']} {plural} con producción registrada"
    if res["concentracion_pct"] is not None and res["metrica"] != "real":
        # Código muerto hoy (conc siempre None en gap — ver "Concentración" en calcular()); se
        # conserva el guard por si esa regla cambia. Para real, la cifra ya vive en el bullet A:
        # repetirla aquí duplicaría justo lo que este plan existe para eliminar.
        pie += f"; {'concentra' if n == 1 else 'concentran'} el {res['concentracion_pct']}% del total"
    pie += "."
    if res["metrica"] == "real" and proy:
        pie += " Cierre proyectado del mes en curso."
    sep = "\n" if res["metrica"] == "gap" else ("\n\n" if linea else "")
    linea += sep + pie

    if res["direccion"] == "bottom" and res["metrica"] == "real" and res["sin_registro"]:
        linea += (f" ⚠️ Además hay {res['sin_registro']} {plural} sin registro REAL este mes "
                  f"(paro o dato faltante — a grano mes no son distinguibles); no se listan.")
    # La glosa explica los CORCHETES, y solo la rama gap los imprime (ver `op` arriba). En la rama
    # real ya no hay corchetes que glosar y el bullet C nombra a los operadores en prosa, así que
    # añadirla duplicaba con la MISMA condición de disparo — el patrón AI1 documentado el 2026-07-30
    # (dos textos con idéntica condición = duplicación garantizada, no ocasional).
    if (res["metrica"] == "gap" and res["nivel_ranking"] == "campo"
            and any(it["es_ecp"] is False for it in res["items"])):
        linea += " Los campos entre corchetes son operados por terceros."
    return linea
