from fastapi import APIRouter, Query
import sqlalchemy as sa
from app.core.db import get_engine
from app.features.consulta.resolver import fuentes_de_activo, campos_de_activo

router = APIRouter(prefix="/analisis", tags=["analisis"])

MESES_ES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

# [2026-08-31] Cuántos campos bajo meta se listan en el desglose del faltante. Era 3 fijo,
# repetido en los dos bloques que construyen `detractores`; el usuario pidió 5 para todos los
# casos. Alimenta el panel "Producción vs Producción esperada" y la frase "Los N mayores
# concentran ~X%" del chat, que lee len(detractores) — cambiar aquí mueve ambos a la vez.
TOP_DETRACTORES = 5

# Mapeo dim_tipo_producto -> término de negocio del conversacional.
# 'agua' NO existe en dim_tipo_producto (solo CRUDO/GAS/BLANCOS) -> se rechazará en el slot-filling.
PRODUCTOS_VALIDOS = [
    {"termino": "aceite", "dim": "CRUDO"},
    {"termino": "gas", "dim": "GAS"},
    {"termino": "blancos", "dim": "BLANCOS"},
]


def _severidad(niveles):
    """Regla de contrapregunta: dura/media = contrapreguntar; blanda = default 'campo' + aviso.
    'gerencia' se trata como DURA (agrega muchos campos/pozos, misma magnitud que 'activo')."""
    if "activo" in niveles or "gerencia" in niveles:
        return "dura"     # colisiona en nivel de gran agregación (cientos de pozos vs uno)
    if "area" in niveles:
        return "media"    # colisiona area+campo
    return "blanda"       # típicamente campo<->fuente


@router.get("/catalogo")
def catalogo():
    """Catálogo de entidades para el Objetivo Primario (visible) y el Secundario (slot-filling).
    Fuente: core.dim_fuente (jerarquía ECP) + dim_vicepresidencia + dim_empresa (filiales)."""
    eng = get_engine()
    with eng.connect() as c:
        card_rows = c.execute(sa.text("""
            SELECT 'gerencia' nivel, COUNT(DISTINCT NULLIF(TRIM(gerencia),'')) n FROM core.dim_fuente
            UNION ALL SELECT 'activo', COUNT(DISTINCT NULLIF(TRIM(activos),'')) FROM core.dim_fuente
            UNION ALL SELECT 'area',   COUNT(DISTINCT NULLIF(TRIM(grupo1),''))  FROM core.dim_fuente
            UNION ALL SELECT 'campo',  COUNT(DISTINCT NULLIF(TRIM(campo),''))   FROM core.dim_fuente
            UNION ALL SELECT 'fuente', COUNT(DISTINCT NULLIF(TRIM(nombre),''))  FROM core.dim_fuente
        """)).mappings().all()
        card = {r["nivel"]: r["n"] for r in card_rows}
        card["vicepresidencia"] = c.execute(
            sa.text("SELECT COUNT(*) FROM core.dim_vicepresidencia")).scalar() or 0

        col_rows = c.execute(sa.text("""
            WITH niveles AS (
                SELECT DISTINCT UPPER(TRIM(gerencia)) v, 'gerencia' niv FROM core.dim_fuente WHERE NULLIF(TRIM(gerencia),'') IS NOT NULL
                UNION SELECT DISTINCT UPPER(TRIM(activos)), 'activo' FROM core.dim_fuente WHERE NULLIF(TRIM(activos),'') IS NOT NULL
                UNION SELECT DISTINCT UPPER(TRIM(grupo1)),  'area'   FROM core.dim_fuente WHERE NULLIF(TRIM(grupo1),'')  IS NOT NULL
                UNION SELECT DISTINCT UPPER(TRIM(campo)),   'campo'  FROM core.dim_fuente WHERE NULLIF(TRIM(campo),'')   IS NOT NULL
                UNION SELECT DISTINCT UPPER(TRIM(nombre)),  'fuente' FROM core.dim_fuente WHERE NULLIF(TRIM(nombre),'')  IS NOT NULL
            )
            SELECT v AS nombre, COUNT(*) n_niveles, array_agg(niv ORDER BY niv) niveles
            FROM niveles GROUP BY v HAVING COUNT(*) > 1 ORDER BY COUNT(*) DESC, v
        """)).mappings().all()

        colisiones = []
        resumen = {"dura": 0, "media": 0, "blanda": 0}
        for r in col_rows:
            nivs = list(r["niveles"])
            sev = _severidad(nivs)
            resumen[sev] += 1
            colisiones.append({"nombre": r["nombre"], "niveles": nivs,
                               "n_niveles": r["n_niveles"], "severidad": sev})
        resumen["total"] = len(colisiones)

        filiales = [x[0] for x in c.execute(
            sa.text("SELECT nombre FROM core.dim_empresa ORDER BY nombre")).all()]

        # Lista COMPLETA de entidades por nivel (para el explorador "ver todas" al clicar una tarjeta).
        NIVELES_SQL = {
            "vicepresidencia": "SELECT DISTINCT TRIM(codigo)   FROM core.dim_vicepresidencia WHERE NULLIF(TRIM(codigo),'') IS NOT NULL",
            "gerencia":        "SELECT DISTINCT TRIM(gerencia) FROM core.dim_fuente WHERE NULLIF(TRIM(gerencia),'') IS NOT NULL",
            "activo":          "SELECT DISTINCT TRIM(activos)  FROM core.dim_fuente WHERE NULLIF(TRIM(activos),'')  IS NOT NULL",
            "area":            "SELECT DISTINCT TRIM(grupo1)   FROM core.dim_fuente WHERE NULLIF(TRIM(grupo1),'')   IS NOT NULL",
            "campo":           "SELECT DISTINCT TRIM(campo)    FROM core.dim_fuente WHERE NULLIF(TRIM(campo),'')    IS NOT NULL",
            "fuente":          "SELECT DISTINCT TRIM(nombre)   FROM core.dim_fuente WHERE NULLIF(TRIM(nombre),'')   IS NOT NULL",
        }
        entidades_por_nivel = {
            niv: sorted(x[0] for x in c.execute(sa.text(q)).all())
            for niv, q in NIVELES_SQL.items()
        }

    cardinalidad = [{"nivel": k, "n": card.get(k, 0)} for k in
                    ["vicepresidencia", "gerencia", "activo", "area", "campo", "fuente"]]
    return {"cardinalidad": cardinalidad, "productos_validos": PRODUCTOS_VALIDOS,
            "colisiones": colisiones, "resumen_colisiones": resumen, "filiales": filiales,
            "entidades_por_nivel": entidades_por_nivel}


@router.get("/densidad")
def densidad(entidad: str | None = Query(None)):
    """Auditoría de densidad temporal sobre core.fact_produccion_dia_ecp (usa idx_dia_fecha).
    Con 'entidad' → filtra por las fuentes ECP que correspondan (fuente/campo/área/activo/gerencia).
    Vicepresidencias y filiales NO tienen grano diario ECP → aplica_ecp=False y serie vacía."""
    import calendar
    from collections import OrderedDict

    eng = get_engine()
    aplica_ecp = True
    with eng.connect() as c:
        if entidad:
            E = entidad.strip().upper()
            # Resolver por 2 caminos: (a) fuentes de dim_fuente (incl. operador → filiales como Hocol);
            # (b) vice_id (el fact tiene columna vicepresidencia → códigos VAS/VEX/… sí filtran).
            ids = [r[0] for r in c.execute(sa.text("""
                SELECT fuente_id FROM core.dim_fuente
                WHERE UPPER(TRIM(nombre))=:e OR UPPER(TRIM(campo))=:e
                   OR UPPER(TRIM(grupo1))=:e OR UPPER(TRIM(activos))=:e
                   OR UPPER(TRIM(gerencia))=:e OR UPPER(TRIM(operador))=:e
            """), {"e": E}).all()]
            vid = c.execute(sa.text(
                "SELECT vice_id FROM core.dim_vicepresidencia WHERE UPPER(TRIM(codigo))=:e"
            ), {"e": E}).scalar()
            if ids or vid is not None:
                conds, params = [], {}
                if ids:
                    conds.append("fuente_id IN :ids")
                    params["ids"] = ids
                if vid is not None:
                    conds.append("vice_id = :vid")
                    params["vid"] = vid
                q = sa.text("""
                    SELECT fecha, COUNT(*) AS filas, COUNT(DISTINCT fuente_id) AS fuentes
                    FROM core.fact_produccion_dia_ecp
                    WHERE """ + " OR ".join(conds) + """
                    GROUP BY fecha ORDER BY fecha""")
                if ids:
                    q = q.bindparams(sa.bindparam("ids", expanding=True))
                rows = c.execute(q, params).mappings().all()
                if not rows:            # entidad reconocida pero sin filas a grano diario ECP
                    aplica_ecp = False
            else:
                aplica_ecp = False
                rows = []
        else:
            rows = c.execute(sa.text("""
                SELECT fecha, COUNT(*) AS filas, COUNT(DISTINCT fuente_id) AS fuentes
                FROM core.fact_produccion_dia_ecp
                GROUP BY fecha ORDER BY fecha
            """)).mappings().all()

    dias = [{"fecha": r["fecha"].isoformat(), "filas": r["filas"], "fuentes": r["fuentes"]} for r in rows]
    fechas = [r["fecha"] for r in rows]

    por_mes_map = OrderedDict()
    for f in fechas:
        por_mes_map.setdefault((f.year, f.month), set()).add(f.day)
    por_mes = []
    huecos_totales = 0
    for (a, m), dset in por_mes_map.items():
        dim = calendar.monthrange(a, m)[1]
        huecos = dim - len(dset)
        huecos_totales += huecos
        por_mes.append({
            "anio": a, "mes": m, "mes_nombre": MESES_ES[m],
            "dias_con_data": len(dset), "dias_del_mes": dim, "huecos": huecos,
            "rango": ["%04d-%02d-%02d" % (a, m, min(dset)), "%04d-%02d-%02d" % (a, m, max(dset))],
        })

    max_racha = 0
    cur = 0
    prev = None
    for f in fechas:
        cur = cur + 1 if (prev is not None and (f - prev).days == 1) else 1
        max_racha = max(max_racha, cur)
        prev = f

    nivel = "verde" if max_racha >= 20 else ("amarillo" if max_racha >= 7 else "rojo")
    # Semáforo como LISTA ordenada por las 5 familias estadísticas (orden canónico). Movimiento y
    # Anomalías dependen de la racha de días CONTINUOS; las otras 3 funcionan con cualquier data.
    semaforo = [
        {"familia": "La foto (totales/promedios/rankings)", "nivel": "verde", "necesita_continuidad": False},
        {"familia": "El movimiento (Δ%, tendencias, rachas)", "nivel": nivel, "necesita_continuidad": True},
        {"familia": "Concentración / Pareto", "nivel": "verde", "necesita_continuidad": False},
        {"familia": "Anomalías (z-scores, cierres, outliers)", "nivel": nivel, "necesita_continuidad": True},
        {"familia": "Descomposición del cambio (waterfall)", "nivel": "verde", "necesita_continuidad": False},
    ]
    resumen = {
        "total_dias": len(fechas),
        "rango": [fechas[0].isoformat(), fechas[-1].isoformat()] if fechas else [None, None],
        "huecos_totales": huecos_totales, "racha_maxima": max_racha,
    }
    return {"entidad": entidad, "aplica_ecp": aplica_ecp,
            "dias": dias, "por_mes": por_mes, "resumen": resumen, "semaforo": semaforo}


@router.get("/huella")
def huella(entidad: str | None = Query(None)):
    """Huella de datos de producción por fact/escenario. Es METADATA (conteo de FILAS, no barriles):
    muestra en qué facts estructurados vive una entidad y con qué escenarios.
    - Sin 'entidad'  → panorama GLOBAL (todo el dataset).
    - Con 'entidad'  → solo esa entidad (match por nombre/campo/area/activo en dim_fuente).
    NO consulta fact_tabla_hoja (P50/DPP/Whatsapp) — esas son hojas derivadas, fuera del alcance."""
    eng = get_engine()
    series = []
    with eng.connect() as c:
        c.execute(sa.text("SET statement_timeout='40s'"))

        if entidad:
            E = entidad.strip().upper()
            ids = [r[0] for r in c.execute(sa.text("""
                SELECT fuente_id FROM core.dim_fuente
                WHERE UPPER(TRIM(nombre))=:e OR UPPER(TRIM(campo))=:e
                   OR UPPER(TRIM(grupo1))=:e OR UPPER(TRIM(activos))=:e
            """), {"e": E}).all()]
            if not ids:
                return {"entidad": entidad, "encontrada": False, "series": []}
            in_ids = sa.bindparam("ids", expanding=True)

            n = c.execute(sa.text(
                "SELECT COUNT(*) FROM core.fact_produccion_dia_ecp WHERE fuente_id IN :ids"
            ).bindparams(in_ids), {"ids": ids}).scalar()
            series.append({"fuente": "REAL diario", "grupo": "dia", "filas": n or 0, "hoja": "BDP_datos_dia"})

            for r in c.execute(sa.text("""
                SELECT es.nombre, COUNT(*) FROM core.fact_produccion_mes_ecp m
                JOIN core.dim_escenario es ON es.escenario_id = m.escenario_id
                WHERE m.fuente_id IN :ids GROUP BY es.nombre ORDER BY es.nombre
            """).bindparams(in_ids), {"ids": ids}):
                series.append({"fuente": f"Mes {r[0]}", "grupo": "mes", "filas": r[1], "hoja": "BDP_datos_mes"})

            n = c.execute(sa.text("""
                SELECT COUNT(*) FROM core.fact_programa_ecp
                WHERE fuente_id IN :ids OR UPPER(TRIM(campo))=:e OR UPPER(TRIM(area))=:e
            """).bindparams(in_ids), {"ids": ids, "e": E}).scalar()
            series.append({"fuente": "Programa", "grupo": "programa", "filas": n or 0, "hoja": "BDP_Programa"})
            return {"entidad": entidad, "encontrada": True, "series": series}

        # --- panorama global ---
        n = c.execute(sa.text("SELECT COUNT(*) FROM core.fact_produccion_dia_ecp")).scalar()
        series.append({"fuente": "REAL diario", "grupo": "dia", "filas": n or 0, "hoja": "BDP_datos_dia"})
        for r in c.execute(sa.text("""
            SELECT es.nombre, COUNT(*) FROM core.fact_produccion_mes_ecp m
            JOIN core.dim_escenario es ON es.escenario_id = m.escenario_id
            GROUP BY es.nombre ORDER BY es.nombre""")):
            series.append({"fuente": f"Mes {r[0]}", "grupo": "mes", "filas": r[1], "hoja": "BDP_datos_mes"})
        n = c.execute(sa.text("SELECT COUNT(*) FROM core.fact_programa_ecp")).scalar()
        series.append({"fuente": "Programa", "grupo": "programa", "filas": n or 0, "hoja": "BDP_Programa"})
        return {"entidad": None, "encontrada": True, "series": series}


def _presencia_entidad(c, entidad):
    """{hoja: nº de reportes donde aparece la entidad}.
    RAW (BDP_datos_dia/mes/Programa) vía facts ECP, resolviendo la entidad por fuente (incl. `operador`
    → filiales como Hocol) y por `vice_id` (vicepresidencias) — MISMO criterio que /densidad, para que
    ambos módulos coincidan. El resto vía bronze.hoja_landing (ILIKE sobre payload JSONB, sin tocar los 62M)."""
    E = (entidad or "").strip().upper()
    pres = {}
    ids = [r[0] for r in c.execute(sa.text("""
        SELECT fuente_id FROM core.dim_fuente
        WHERE UPPER(TRIM(nombre))=:e OR UPPER(TRIM(campo))=:e
           OR UPPER(TRIM(grupo1))=:e OR UPPER(TRIM(activos))=:e
           OR UPPER(TRIM(gerencia))=:e OR UPPER(TRIM(operador))=:e
    """), {"e": E}).all()]
    vid = c.execute(sa.text(
        "SELECT vice_id FROM core.dim_vicepresidencia WHERE UPPER(TRIM(codigo))=:e"
    ), {"e": E}).scalar()

    def _reps(tabla, extra_cond=""):
        conds, params = [], {}
        if ids:
            conds.append("fuente_id IN :ids"); params["ids"] = ids
        if vid is not None:
            conds.append("vice_id = :vid"); params["vid"] = vid
        if extra_cond:
            conds.append(extra_cond); params["e"] = E
        if not conds:
            return 0
        q = sa.text("SELECT COUNT(DISTINCT reporte_id) FROM core." + tabla +
                    " WHERE " + " OR ".join(conds))
        if ids:
            q = q.bindparams(sa.bindparam("ids", expanding=True))
        return c.execute(q, params).scalar() or 0

    pres["BDP_datos_dia"] = _reps("fact_produccion_dia_ecp")
    pres["BDP_datos_mes"] = _reps("fact_produccion_mes_ecp")
    pres["BDP_Programa"] = _reps("fact_programa_ecp", "UPPER(TRIM(campo))=:e OR UPPER(TRIM(area))=:e")

    # resto: bronze.hoja_landing (payload::text ILIKE, con escape de comodines)
    patt = "%" + E.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    for r in c.execute(sa.text("""
        SELECT hoja, COUNT(DISTINCT reporte_id) FROM bronze.hoja_landing
        WHERE payload::text ILIKE :pat ESCAPE '\\' GROUP BY hoja
    """), {"pat": patt}):
        pres[r[0]] = r[1]
    return pres


@router.get("/cobertura")
def cobertura(entidad: str | None = Query(None)):
    """Mapa de cobertura del reporte: TODAS las hojas por categoría (fuente: core.ingesta_log).
    Métrica = nº de REPORTES (COUNT DISTINCT reporte_id). Sin 'entidad' → en cuántos reportes está cada hoja.
    Con 'entidad' → en cuántos reportes APARECE la entidad por hoja (PRESENCIA): RAW vía facts ECP; resto vía
    bronze.hoja_landing. NO toca fact_tabla_hoja (62M). NO usa SUM(filas_insertadas) (sobre-cuenta ~26x)."""
    from collections import OrderedDict
    CATS = ["Producción ECP", "Filiales", "Comentarios",
            "Hojas modeladas (visor)", "Preservada en crudo (Bronze)"]
    PRIOR = {c: i for i, c in enumerate(CATS)}

    def cat_of(dest):
        d = (dest or "").lower()
        if d in ("core.fact_produccion_dia_ecp", "core.fact_produccion_mes_ecp", "core.fact_programa_ecp"):
            return "Producción ECP"
        if d in ("core.fact_produccion_diaria", "core.fact_plan_mensual", "core.fact_promedio_validado"):
            return "Filiales"
        if d == "core.fact_comentarios_produccion":
            return "Comentarios"
        if d == "core.fact_tabla_hoja":
            return "Hojas modeladas (visor)"
        return "Preservada en crudo (Bronze)"

    eng = get_engine()
    with eng.connect() as c:
        c.execute(sa.text("SET statement_timeout='60s'"))
        rows = c.execute(sa.text("""
            SELECT hoja, tabla_destino, COUNT(DISTINCT reporte_id) reps
            FROM core.ingesta_log
            GROUP BY hoja, tabla_destino
        """)).mappings().all()

        # F1: la métrica es 'reportes' (COUNT DISTINCT reporte_id), NO SUM(filas_insertadas) — esta última
        # sobre-cuenta ~26x por los upserts idempotentes acumulados en 138 reportes (11.2M vs 435K reales).
        por_hoja = {}
        for r in rows:
            hoja = r["hoja"] or "(sin nombre)"
            cat = cat_of(r["tabla_destino"])
            cur = por_hoja.get(hoja)
            if cur is None or PRIOR[cat] < PRIOR[cur["categoria"]]:
                por_hoja[hoja] = {"hoja": hoja, "categoria": cat, "reportes_total": r["reps"]}

        if entidad:
            pres = _presencia_entidad(c, entidad)
            for h in por_hoja.values():
                h["reportes_entidad"] = int(pres.get(h["hoja"], 0))

    def _ordkey(x):
        return -(x.get("reportes_entidad", x["reportes_total"]))
    cats = OrderedDict((k, []) for k in CATS)
    for h in sorted(por_hoja.values(), key=_ordkey):
        cats[h["categoria"]].append(h)
    categorias = [{"categoria": k, "hojas": v} for k, v in cats.items() if v]
    out = {"entidad": entidad, "total_hojas": len(por_hoja), "categorias": categorias}
    if entidad:
        out["hojas_con_entidad"] = sum(1 for h in por_hoja.values() if h.get("reportes_entidad", 0) > 0)
    return out


# ============================================================================
# Cimiento nivel+periodo aware (compartido por desempeno / desempeno_insight / ejecutivo).
# nivel-aware: resuelve por la COLUMNA del nivel (campo≠área); sin nivel → OR-unión (compat).
# periodo-aware (v1 = solo MES): default último-con-dato · mes explícito · mes+año · "mes pasado".
# ============================================================================
# 2026-07-16: 'activo' NO es una columna de dim_fuente. Se compone desde core.map_campo_activo
# (migración 008) vía resolver.fuentes_de_activo — MISMA fuente que usa el chat, para que el
# tablero y la conversación no puedan divergir. `activos`/`grupo1` quedaron fuera: la primera es
# un bucket de portafolio (OPERADOS/NO OPERADOS/MENORES), la segunda una taxonomía previa.
# ⚠️ 'pozo' sigue siendo un ALIAS de 'fuente': el grano de pozo NO existe en esta BD (deuda).
_NIVEL_COL_AMB = {"fuente": "nombre", "pozo": "nombre", "campo": "campo",
                  "gerencia": "gerencia", "operador": "operador"}
_MESES_NUM = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
              "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}
_PERIODO_DEFAULT_TXT = {"este mes", "mes actual", "el mes", "mes en curso", "este mes en curso"}


def _periodo_es_default(texto):
    return (not texto) or (texto.strip().lower() in _PERIODO_DEFAULT_TXT)


def _parse_periodo(texto, ref_y, ref_mo):
    """Texto libre de periodo → (año, mes) para el KPI mensual, o None si no se reconoce/es default.
    v1 (D-C1): default, mes por nombre (+año opcional), 'mes pasado'. Año/semana/trimestre → None."""
    if _periodo_es_default(texto):
        return None
    import re as _re_p
    t = texto.strip().lower()
    if "pasado" in t or "anterior" in t:            # 'mes pasado' / 'mes anterior'
        y, m = ref_y, ref_mo - 1
        if m < 1:
            y, m = y - 1, 12
        return (y, m)
    mo = next((num for nombre, num in _MESES_NUM.items() if nombre in t), None)
    if mo is None:
        return None                                 # año/semana/trimestre no soportados en v1
    ym = _re_p.search(r"(20\d\d)", t)
    return (int(ym.group(1)) if ym else ref_y, mo)


def _ambito(c, entidad, nivel=None, periodo=None):
    """Ámbito ECP nivel+periodo aware. Devuelve:
      {ids, vid, y, mo, dim, ini, fin, aplica_diario, periodo_ok} | None (no encontrada) | {'sin_datos':True}."""
    import calendar
    ids, vid = [], None
    if entidad:
        E = entidad.strip().upper()
        nv = (nivel or "").lower()
        col = _NIVEL_COL_AMB.get(nv)
        if nv == "vicepresidencia":
            vid = c.execute(sa.text(
                "SELECT vice_id FROM core.dim_vicepresidencia WHERE UPPER(TRIM(codigo))=:e"), {"e": E}).scalar()
        elif nv == "activo":                        # activo → composición del catálogo (mig. 008)
            ids = fuentes_de_activo(E)
        elif col:                                   # nivel específico → columna exacta (D-C2)
            ids = [r[0] for r in c.execute(sa.text(
                f"SELECT fuente_id FROM core.dim_fuente WHERE UPPER(TRIM({col}))=:e"), {"e": E})]
        else:                                       # sin nivel → OR-unión + activo + vice (compat, D-C3)
            ids = [r[0] for r in c.execute(sa.text("""
                SELECT fuente_id FROM core.dim_fuente
                WHERE UPPER(TRIM(nombre))=:e OR UPPER(TRIM(campo))=:e
                   OR UPPER(TRIM(gerencia))=:e OR UPPER(TRIM(operador))=:e
            """), {"e": E})]
            ids = sorted(set(ids) | set(fuentes_de_activo(E)))
            vid = c.execute(sa.text(
                "SELECT vice_id FROM core.dim_vicepresidencia WHERE UPPER(TRIM(codigo))=:e"), {"e": E}).scalar()
        if not ids and vid is None:
            return None

    condd, condm, b0 = [], [], {}
    if ids:
        condd.append("fuente_id IN :ids"); condm.append("m.fuente_id IN :ids"); b0["ids"] = ids
    if vid is not None:
        condd.append("vice_id = :vid"); condm.append("m.vice_id = :vid"); b0["vid"] = vid
    wd = "(" + " OR ".join(condd) + ")" if condd else "TRUE"
    wm = "(" + " OR ".join(condm) + ")" if condm else "TRUE"

    def _mx(sql):
        t = sa.text(sql)
        return t.bindparams(sa.bindparam("ids", expanding=True)) if ids else t

    maxd = c.execute(_mx(f"SELECT MAX(fecha) FROM core.fact_produccion_dia_ecp WHERE {wd}"), b0).scalar()
    aplica_diario = maxd is not None
    if maxd is None:                                # fallback: último mes con REAL mensual
        maxd = c.execute(_mx(f"""
            SELECT MAX(m.fecha) FROM core.fact_produccion_mes_ecp m
            JOIN core.dim_escenario es ON es.escenario_id = m.escenario_id
            WHERE es.nombre='REAL' AND {wm}"""), b0).scalar()
    if maxd is None:
        return {"sin_datos": True}

    per = _parse_periodo(periodo, maxd.year, maxd.month)
    y, mo = per if per else (maxd.year, maxd.month)
    periodo_ok = bool(per) or _periodo_es_default(periodo)   # honrado, o default explícito; False = no soportado
    dim = calendar.monthrange(y, mo)[1]
    return {"ids": ids, "vid": vid, "y": y, "mo": mo, "dim": dim,
            "ini": f"{y:04d}-{mo:02d}-01", "fin": f"{y:04d}-{mo:02d}-{dim:02d}",
            "aplica_diario": aplica_diario, "periodo_ok": periodo_ok}


def _campos_sin_meta(c, entidad, fin, nivel):
    """Campos de un ACTIVO que PRODUCEN pero no tienen PPTO en el mes (por producto).

    Solo aplica al nivel 'activo': es el único que agrega varios campos, y por tanto el único
    donde el REAL sumado puede quedar comparado contra un PPTO que no cubre a todos.
    Devuelve [] para cualquier otro nivel. Nunca inventa presupuesto (ver D-A4).
    """
    if (nivel or "").lower() != "activo":
        return []
    ids = fuentes_de_activo(entidad)
    if not ids:
        return []
    q = sa.text("""
        SELECT COALESCE(NULLIF(TRIM(f.campo),''), TRIM(f.nombre)) campo, tp.nombre producto,
               SUM(CASE WHEN es.nombre='REAL' THEN m.volumen ELSE 0 END) real,
               SUM(CASE WHEN es.nombre='PPTO' THEN m.volumen ELSE 0 END) ppto
        FROM core.fact_produccion_mes_ecp m
        JOIN core.dim_fuente f        ON f.fuente_id        = m.fuente_id
        JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = m.tipo_producto_id
        JOIN core.dim_escenario es     ON es.escenario_id     = m.escenario_id
        WHERE m.fecha = :fin AND es.nombre IN ('REAL','PPTO') AND m.fuente_id IN :ids
        GROUP BY 1, 2
        HAVING SUM(CASE WHEN es.nombre='REAL' THEN m.volumen ELSE 0 END) > 0
           AND SUM(CASE WHEN es.nombre='PPTO' THEN m.volumen ELSE 0 END) = 0
        ORDER BY 3 DESC
    """).bindparams(sa.bindparam("ids", expanding=True))
    return [{"campo": r[0], "producto": r[1], "real": float(r[2] or 0)}
            for r in c.execute(q, {"fin": fin, "ids": ids})]


# ============================================================================
# Desempeño del mes (MVP · segmento Producción ECP). Solo lectura, sin LLM.
# Módulos: (1) KPIs REAL vs PPTO por producto (mes) + (2) curva diaria REAL (día).
# Resolución de entidad = MISMO criterio que /densidad (fuente_id 6 cols + vice_id).
# ============================================================================
@router.get("/desempeno")
def desempeno(entidad: str | None = Query(None), segmento: str = Query("ecp"),
              nivel: str | None = Query(None), periodo: str | None = Query(None)):
    if segmento == "filiales":
        return _desempeno_filiales()
    import calendar

    def _bind(sql, params):
        t = sa.text(sql)
        if "ids" in params:
            t = t.bindparams(sa.bindparam("ids", expanding=True))
        return t

    eng = get_engine()
    with eng.connect() as c:
        amb = _ambito(c, entidad, nivel, periodo)
        if amb is None:
            return {"entidad": entidad, "encontrada": False}
        if amb.get("sin_datos"):
            return {"entidad": entidad, "encontrada": True, "sin_datos": True}
        ids, vid = amb["ids"], amb["vid"]
        aplica_diario = amb["aplica_diario"]
        y, mo, dim, ini, fin = amb["y"], amb["mo"], amb["dim"], amb["ini"], amb["fin"]

        base = {}
        if ids:
            base["ids"] = ids
        if vid is not None:
            base["vid"] = vid

        def where(alias):
            p = (alias + ".") if alias else ""
            cs = []
            if ids:
                cs.append(f"{p}fuente_id IN :ids")
            if vid is not None:
                cs.append(f"{p}vice_id = :vid")
            return ("(" + " OR ".join(cs) + ")") if cs else "TRUE"

        # --- Módulo 1: REAL vs PPTO por producto (SOLO mensual — VERIFICADO H1) ---
        # H1: el `volumen` de cada producto vive en UN SOLO proceso (CRUDO→PROD_TOTAL,
        # GAS→VENTA-GRAVABLE, BLANCOS→GAS CONVERTIDO MME); los demás procesos van en NULL.
        # Por eso SUM(m.volumen) sobre TODOS los procesos NO doble-cuenta y es ROBUSTO al mapeo
        # (no hay que hard-codear el proceso por producto). NO filtrar por proceso.
        pm = dict(base); pm["fin"] = fin
        kpi = {}
        for r in c.execute(_bind(f"""
            SELECT tp.nombre prod, es.nombre esc, SUM(m.volumen) vol
            FROM core.fact_produccion_mes_ecp m
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = m.tipo_producto_id
            JOIN core.dim_escenario es ON es.escenario_id = m.escenario_id
            WHERE m.fecha = :fin AND es.nombre IN ('REAL','PPTO') AND {where('m')}
            GROUP BY 1, 2""", pm), pm):
            kpi.setdefault(r[0], {})[r[1]] = float(r[2] or 0)

        # --- Módulo 2: curva diaria REAL (SOLO forma/tendencia — NO alimenta los KPIs, H2) ---
        # H2: día y mes usan MEDIDAS distintas para algunos productos (BLANCOS: día≈1.9M vs mes≈0.9M).
        # Por eso los KPIs (REAL/cumplimiento) salen 100% de `mes`, y `día` se usa SOLO para la curva.
        curva = {}
        curva_fechas, dias_rep = [], 0
        if aplica_diario:
            pd = dict(base); pd["ini"] = ini; pd["fin"] = fin
            rows = c.execute(_bind(f"""
                SELECT d.fecha, tp.nombre prod, SUM(d.volumen) vol
                FROM core.fact_produccion_dia_ecp d
                JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = d.tipo_producto_id
                WHERE d.fecha BETWEEN :ini AND :fin AND {where('d')}
                GROUP BY 1, 2 ORDER BY 1""", pd), pd).all()
            for f, prod, vol in rows:
                iso = f.isoformat()
                curva.setdefault(iso, {})[prod] = float(vol or 0)
            curva_fechas = sorted(curva.keys())
            dias_rep = len(curva_fechas)

        productos = ["CRUDO", "GAS", "BLANCOS"]
        por_producto = []
        for p in productos:
            real = kpi.get(p, {}).get("REAL", 0.0)
            ppto = kpi.get(p, {}).get("PPTO", 0.0)
            cumpl = round(real / ppto * 100.0, 1) if ppto else None
            por_producto.append({"producto": p, "real": real, "ppto": ppto, "cumplimiento": cumpl})
        series = {p: [curva.get(f, {}).get(p, 0.0) for f in curva_fechas] for p in productos}
        sin_cierre = not any(kpi.get(p) for p in productos)   # H5: sin fila mensual REAL/PPTO para el mes

        # --- Módulo 3: PRODUCCIÓN MENSUAL del año (2026-07-23) ---
        # Barras = REAL mensual de cada mes (mayo = proyección de cierre, fila fecha=fin). Línea =
        # promedio mensual de los meses CERRADOS (= hist_prom, el "3,3M" de la tarjeta). 🔑 Sale del
        # MISMO fact MENSUAL que la tarjeta, así que mayo = 2,6M y el promedio = 3,3M reconcilian
        # EXACTO. NO se usa el fact diario (para GAS/BLANCOS usa otra medida — H2). La curva DIARIA
        # (gráfico izquierdo) es la que muestra el ritmo por día y su promedio diario real.
        ritmo = {"meses": [], "meses_num": [], "series": {}, "promedio_mes": {}, "promedio_dia": {}, "mes_actual": mo}
        pr = dict(base); pr["yy"] = y
        mrows = c.execute(_bind(f"""
            SELECT EXTRACT(month FROM m.fecha)::int AS mes, tp.nombre AS prod, SUM(m.volumen) AS vol
            FROM core.fact_produccion_mes_ecp m
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = m.tipo_producto_id
            JOIN core.dim_escenario es ON es.escenario_id = m.escenario_id
            WHERE es.nombre = 'REAL' AND EXTRACT(year FROM m.fecha) = :yy AND {where('m')}
            GROUP BY 1, 2 ORDER BY 1""", pr), pr).all()
        real_mes = {}      # {mes: {prod: vol}}
        for _mes, _prod, _vol in mrows:
            real_mes.setdefault(int(_mes), {})[_prod] = float(_vol or 0)
        meses_ord = sorted(real_mes.keys())
        ritmo["meses"] = [MESES_ES[m][:3] for m in meses_ord]
        ritmo["meses_num"] = meses_ord
        for p in productos:
            ritmo["series"][p] = [round(real_mes[m][p]) if real_mes.get(m, {}).get(p) else None
                                  for m in meses_ord]
            # promedio mensual = media de los meses CERRADOS (anteriores al actual) = hist_prom
            cerr = [(m, real_mes[m][p]) for m in meses_ord if m < mo and real_mes.get(m, {}).get(p)]
            ritmo["promedio_mes"][p] = round(sum(v for _m, v in cerr) / len(cerr)) if cerr else None
            # promedio DIARIO del año = Σ REAL meses cerrados ÷ Σ días. Es la referencia "vs 2026" de la
            # curva diaria; sale del REAL mensual (fuente de verdad). SOLO se entrega si la curva diaria de
            # ESTE producto RECONCILIA con el mensual (GAS/CRUDO sí; BLANCOS no — su curva diaria suma 4
            # conceptos-copia → ×4 vs el mensual, ver INGESTA/Rep_Prod/HALLAZGO_concepto_multiplicidad.md).
            # Cuando no reconcilia, el frontend cae a la media del mes y su título NO dice "vs 2026".
            _dd = sum(calendar.monthrange(y, _m)[1] for _m, _ in cerr)
            _mtd_dia = sum(v for v in series.get(p, []) if v)                    # acumulado de la curva del mes
            _esp = (kpi.get(p, {}).get("REAL", 0.0) * (dias_rep / dim)) if dim else 0.0  # MTD esperado (mensual)
            _reconc = _esp > 0 and _mtd_dia <= _esp * 1.15
            ritmo["promedio_dia"][p] = round(sum(v for _m, v in cerr) / _dd) if (_dd and _reconc) else None

        # D-A4 (2026-07-16): rollup honesto del ACTIVO. El PPTO se carga POR CAMPO, y hay campos que
        # producen SIN meta asignada (15 de 128 en crudo/may-2026 = 1.4% del volumen; en el activo
        # APIAY son 3 de 4). Sumar sus REAL contra un PPTO que no los cubre infla el cumplimiento,
        # así que se DECLARAN en vez de inventarles meta (se descartó PPTO=1.25*REAL: da 80% constante
        # y hundía APIAY de 108.8% a 63.0% con 385.409 bl de presupuesto fabricado).
        campos_sin_meta = _campos_sin_meta(c, entidad, fin, nivel) if ids else []

        return {
            "entidad": entidad, "encontrada": True, "aplica_diario": aplica_diario,
            "sin_cierre": sin_cierre,
            "periodo_ok": amb["periodo_ok"],
            "mes": {"anio": y, "mes": mo, "nombre": MESES_ES[mo],
                    "dias_con_data": dias_rep, "dias_del_mes": dim, "completo": dias_rep >= dim},
            "por_producto": por_producto,
            "campos_sin_meta": campos_sin_meta,
            "curva": {"fechas": curva_fechas, "series": series},
            "ritmo_mensual": ritmo,
        }


# ============================================================================
# Cuantificar Fase 4 (referencias != PPTO en N1): helper READ-ONLY, NO endpoint (AF-4.11 — sin
# @router.get, para que llamarlo como función normal no filtre objetos Query). Reusa `_ambito` para
# resolver el MISMO ámbito que `desempeno`. NO se toca `desempeno` ni su query de KPIs (AF-4.2):
# meter OPERATIVO/CONTABLE en ese IN cambiaría `sin_cierre` (un producto con fila OPERATIVO pero sin
# REAL/PPTO crearía kpi[p] y volvería sin_cierre=False cuando debía ser True → regresión del tablero).
# ============================================================================
def escenario_mes(entidad: str, nivel: str | None = None, periodo: str | None = None,
                  escenarios=("OPERATIVO", "CONTABLE")) -> dict:
    """Valor por producto de escenarios de presupuesto (OPERATIVO/CONTABLE) en el MES resuelto, con el
    MISMO ámbito que `desempeno` (reusa `_ambito`). Read-only y AISLADO: no toca `desempeno` ni su
    `sin_cierre` (AF-4.2). Devuelve {PRODUCTO: {ESCENARIO: valor}} (vacío si no hay ámbito/datos)."""
    eng = get_engine()
    with eng.connect() as c:
        amb = _ambito(c, entidad, nivel=nivel, periodo=periodo)
        if not amb or amb.get("sin_datos"):
            return {}
        ids, vid, fin = amb.get("ids"), amb.get("vid"), amb.get("fin")
        if not ids and vid is None:
            return {}
        cond, params = [], {"fin": fin, "escs": list(escenarios)}
        if ids:
            cond.append("m.fuente_id IN :ids"); params["ids"] = ids
        if vid is not None:
            cond.append("m.vice_id = :vid"); params["vid"] = vid
        whr = "(" + " OR ".join(cond) + ")" if cond else "TRUE"
        t = sa.text(f"""
            SELECT tp.nombre prod, es.nombre esc, SUM(m.volumen) vol
            FROM core.fact_produccion_mes_ecp m
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = m.tipo_producto_id
            JOIN core.dim_escenario es ON es.escenario_id = m.escenario_id
            WHERE m.fecha = :fin AND es.nombre IN :escs AND {whr}
            GROUP BY 1, 2""").bindparams(sa.bindparam("escs", expanding=True))
        if ids:
            t = t.bindparams(sa.bindparam("ids", expanding=True))
        out = {}
        for prod, esc, vol in c.execute(t, params):
            out.setdefault(prod, {})[esc] = float(vol or 0)
        return out


# ============================================================================
# Titular ejecutivo (IA) — contrato JSON. Python calcula números/fechas/eventos;
# el LLM (CONSULTA_OLLAMA_URL) SOLO redacta prosa. Fallback estático con la misma forma.
# ============================================================================
import json as _json, re as _re, urllib.request as _urlreq
from app.core.config import get_settings   # INS-C: se llama LAZY dentro de _llm_insight (no a nivel módulo)

def _estado(pct):
    if pct is None:
        return ""   # INS-B: producto inexistente (ej. Castilla no produce gas) -> chip neutral, NO rojo
    return "ok" if pct >= 90 else ("warn" if pct >= 75 else "alert")

# ============================================================================
# Tarjetas KPI de cierre (Nivel 1 del panel ejecutivo) — plan_tarjetas_kpi_cierre_2026-07-21.
# Eje de estado PROPIO (alineado/ajustado/actuar), independiente de _estado() de arriba (que
# sigue sirviendo los chips/tabs existentes con sus propios umbrales 90/75 — NO SE TOCA).
# Unidad: dim_tipo_producto NO tiene columna de unidad (solo `nombre`, ver ddl_v2_postgres.sql
# L127-130) — se declara en código. GAS = MSCF (miles de pies cúbicos estándar, decisión del
# usuario 2026-07-21); CRUDO/BLANCOS en barriles.
# ============================================================================
_UNIDADES_PRODUCTO = {"CRUDO": "bbl", "BLANCOS": "bbl", "GAS": "MSCF"}

def _estado_cierre(proyectado, meta):
    """alineado (>=meta) / ajustado (>=meta*umbral_ambar) / actuar (por debajo) / "" (sin meta)."""
    if not meta:
        return ""
    pct = proyectado / meta
    umbral = get_settings().kpi_cierre_ambar_pct
    if pct >= 1.0:
        return "alineado"
    if pct >= umbral:
        return "ajustado"
    return "actuar"

def _tarjetas_kpi(titular, pace_por_prod=None, hist_por_prod=None):
    """Tarjeta por producto para el Nivel 1. proyectado_cierre = t['real'] SIN recalcular:
    titular.real YA es la proyección de cierre del mes completo (ejecucion.py L134-142,
    commit 7c47480) -- sumarle días de más lo infla. Meta = t['ppto'] (PPTO en ECP, PROGRAMA
    en filiales -- mismo campo, ver _fil_intermedios). No redondea aquí: meta_mes/proyectado_cierre
    quedan crudos para que el frontend pueda verificar igualdad byte a byte contra titular.real
    (gate de no-divergencia); relleno_pct sí se redondea (es solo para el ancho de la barra).

    `pace_por_prod` = {producto: {promedio_dia, requerido_dia, delta_pct}} — SOLO los productos cuya
    curva diaria reconcilia con el mensual (ver ejecutivo(): guarda mtd<=real*1.05). Adjunta bopd a
    esas tarjetas; el resto (p.ej. BLANCOS, cuyo diario no cuadra) queda sin ritmo diario -> el
    frontend les muestra solo la proyección mensual, sin inventar una tasa diaria."""
    pace_por_prod = pace_por_prod or {}
    hist_por_prod = hist_por_prod or {}
    out = []
    for t in titular:
        producto = t["producto"]; meta = t.get("ppto") or 0.0; proy = t.get("real") or 0.0
        hist = hist_por_prod.get(producto)   # promedio del año (meses previos con REAL)
        # Fallback "sin meta formal": si la entidad/producto NO tiene PPTO/PROGRAMA (meta=0) pero sí
        # hay promedio del año, se usa ese promedio como META de cierre (mismo criterio que las
        # filiales sin PPTO). Evita la tarjeta muerta "Sin meta definida"; el frontend ya compara
        # arriba "mes vs promedio del año", así el % y la proyección quedan coherentes con esa base.
        meta_de_promedio = bool(not meta and hist)
        if meta_de_promedio:
            meta = float(hist)
        relleno = round(min(proy / meta, 1.0) * 100, 1) if meta else 0.0
        p = pace_por_prod.get(producto)
        bopd = None
        if p and p.get("promedio_dia") and p.get("requerido_dia"):
            bopd = {"real": p["promedio_dia"], "requerido": p["requerido_dia"],
                    "delta_pct": p.get("delta_pct")}
        out.append({
            "producto": producto,
            "unidad": _UNIDADES_PRODUCTO.get(producto),
            "meta_mes": meta,
            "proyectado_cierre": proy,
            "brecha_abs": meta - proy,
            "relleno_pct": relleno,
            "alcanza": meta > 0 and proy >= meta,
            "estado": _estado_cierre(proy, meta),
            "metodo": "proyeccion_de_cierre_del_reporte",
            "meta_de_promedio": meta_de_promedio,   # True = la meta es el promedio del año (sin PPTO/PROGRAMA)
            "bopd": bopd,
            "hist_prom": hist,
        })
    return out

def _detectar_valle(serie):
    """serie = [(iso, valor)] ordenada. Valle = run contiguo más largo de >=3 días bajo media*0.997."""
    if len(serie) < 5:
        return None
    vals = [v for _, v in serie]
    umbral = (sum(vals) / len(vals)) * 0.997
    runs, cur = [], []
    for f, v in serie:
        if v < umbral:
            cur.append((f, v))
        else:
            if len(cur) >= 3:
                runs.append(cur)
            cur = []
    if len(cur) >= 3:
        runs.append(cur)
    if not runs:
        return None
    valle = max(runs, key=len)
    mn = min(valle, key=lambda x: x[1])
    return {"desde": valle[0][0], "hasta": valle[-1][0], "min_fecha": mn[0], "min_valor": mn[1]}

def _nombres_entidad(c, ids, vid):
    """Nombres (UPPER) con los que la entidad aparece en `dim_fuente`, para cruzar contra las
    columnas de texto de `fact_comentarios_produccion` (que NO tiene fuente_id). Devuelve set()
    cuando no hay ids/vid → el llamador debe interpretarlo como alcance GLOBAL."""
    if ids:
        rows = c.execute(sa.text(
            "SELECT nombre, campo, grupo1, activos FROM core.dim_fuente WHERE fuente_id IN :ids"
        ).bindparams(sa.bindparam("ids", expanding=True)), {"ids": ids}).all()
    elif vid is not None:
        rows = c.execute(sa.text(
            "SELECT nombre, campo, grupo1, activos FROM core.dim_fuente WHERE vice_id = :vid"),
            {"vid": vid}).all()
    else:
        rows = []
    names = set()
    for r in rows:
        for x in r:
            if x and str(x).strip():
                names.add(str(x).strip().upper())
    return names


# 🔑 2026-07-23: en `fact_comentarios_produccion` el área a veces trae el producto como sufijo
# —`CUPIAGUA (CRUDO)`, `CUSIANA (BLANCOS)`— porque el reporte separa el comentario por producto.
# 144 de 648 comentarios de mayo-2026 tienen ese formato. Con el match EXACTO contra `CUPIAGUA`
# ninguno calzaba: el panel decía "sin evento asociado en comentarios" mientras el reporte traía
# 18 comentarios de ese campo. SPLIT_PART deja la base del nombre y es inocuo si no hay paréntesis.
_AREA_BASE = "UPPER(TRIM(SPLIT_PART(fc.area, '(', 1)))"
_ACTIVOS_BASE = "UPPER(TRIM(SPLIT_PART(fc.activos, '(', 1)))"


def _eventos_valle(c, onset, names=None):
    """Top eventos (campo, evento, pozos) del DÍA DE INICIO del valle.
    INS-A (verificado en BD): consultar TODO el rango 09-14 duplica el mismo evento (se repite
    'en estabilización' cada día) → ranking basura. Solo el onset (09-may) da los 10 eventos limpios.
    INS-A2: el nombre del campo va en `area` (Tibú/Caracará), no en `activos` (CATENARE/NO OPERADOS).

    `names` (de _nombres_entidad): ACOTA los eventos a la entidad. Sin names → alcance global (brief
    de ECP, comportamiento original). 🔑 2026-07-16: sin acotar, el brief de CASTILLA recibía los
    eventos de QUIFA/TIBU/CARACARA y Gemma explicaba el mes de Castilla con fallas eléctricas ajenas
    — mismo defecto que ya se corrigió en _valle_diagnostico_entidad."""
    filtro, params = "", {"d": onset}
    if names:
        filtro = f" AND ({_AREA_BASE} IN :names OR {_ACTIVOS_BASE} IN :names)"
        params["names"] = list(names)
    q = sa.text(f"""
        SELECT COALESCE(NULLIF(TRIM(fc.area),''), fc.activos) AS campo, fc.comentario
        FROM core.fact_comentarios_produccion fc
        JOIN core.config_reporte cr ON cr.reporte_id = fc.reporte_id
        WHERE cr.fecha_reporte = :d
          AND fc.comentario IS NOT NULL AND LENGTH(TRIM(fc.comentario)) > 5{filtro}
    """)
    if names:
        q = q.bindparams(sa.bindparam("names", expanding=True))
    rows = c.execute(q, params).all()
    items = []
    for campo, com in rows:
        pozos = sum(int(x) for x in _re.findall(r"(\d+)\s*pozos", com or ""))
        if pozos <= 0:
            continue
        evento = (com or "").strip().split(".")[0][:70]
        items.append({"campo": (campo or "").strip(), "evento": evento, "pozos": pozos})
    items.sort(key=lambda x: x["pozos"], reverse=True)
    TOP_N = 12   # antes 3 (maqueta compacta). Ahora col1 llena el alto → mostramos hasta 12 (el onset ~10)
    top, resto = items[:TOP_N], items[TOP_N:]
    extra = {"campos": len(resto), "pozos_aprox": sum(i["pozos"] for i in resto),
             "fecha": onset.isoformat()}
    return top, extra


def _comentarios_campo_mes(c, campo, ini, fin, limit=2):
    """Comentario(s) reales del reporte para `campo` en el mes del gap (ini..fin) — fuente/soporte
    de una atribución de causa (Épica 1, criterio 2: 'cada causa debe tener fuente/soporte... para
    validez'). Mismo matching por BASE (SPLIT_PART) que _eventos_valle/_valle_diagnostico_entidad,
    pero a diferencia de esas NO se acota a un día (onset) sino a TODO el mes, porque el gap es una
    comparación mensual (PPTO vs REAL), no un evento puntual. Sin match real -> [] (nunca se inventa
    una causa; ver `_focos` para el fallback textual)."""
    if not campo:
        return []
    q = sa.text(f"""
        SELECT cr.fecha_reporte, fc.comentario
        FROM core.fact_comentarios_produccion fc
        JOIN core.config_reporte cr ON cr.reporte_id = fc.reporte_id
        WHERE cr.fecha_reporte BETWEEN :ini AND :fin
          AND fc.comentario IS NOT NULL AND LENGTH(TRIM(fc.comentario)) > 5
          AND ({_AREA_BASE} = :campo OR {_ACTIVOS_BASE} = :campo)
        ORDER BY cr.fecha_reporte DESC
        LIMIT :lim
    """)
    rows = c.execute(q, {"ini": ini, "fin": fin, "campo": campo.strip().upper(), "lim": limit}).all()
    return [{"fecha": r[0].isoformat(), "texto": (r[1] or "").strip()[:220]} for r in rows]


def _valle_diagnostico_entidad(c, entidad, ids, vid, valle, y, mo, dim, onset):
    """Valle explicado POR la entidad (ECP). Determinista (sin LLM): (A) el/los comentario(s) que la
    entidad reportó el día de inicio del valle (motivo documentado real) y (B) si tiene >1 pozo, qué
    pozos cayeron (avg en días del valle vs avg en el resto del mes). Análogo ECP de
    _valle_diagnostico_filiales. NUNCA inventa causas: el comentario ES la causa (cuando existe)."""
    desde, hasta = valle["desde"], valle["hasta"]
    ini = f"{y:04d}-{mo:02d}-01"; fin = f"{y:04d}-{mo:02d}-{dim:02d}"

    # where sobre fact_produccion_dia_ecp (mismo criterio que el resto del insight)
    conds, params = [], {"ini": ini, "fin": fin, "desde": desde, "hasta": hasta}
    if ids: conds.append("d.fuente_id IN :ids"); params["ids"] = ids
    if vid is not None: conds.append("d.vice_id = :vid"); params["vid"] = vid
    where_d = "(" + " OR ".join(conds) + ")" if conds else "TRUE"

    # (B) descomposición por POZO: avg en días del valle vs avg en el resto del mes
    q = sa.text(f"""
        WITH dd AS (
          SELECT f.nombre pozo, d.fecha, SUM(d.volumen) v
          FROM core.fact_produccion_dia_ecp d
          JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = d.tipo_producto_id
          JOIN core.dim_fuente f ON f.fuente_id = d.fuente_id
          WHERE tp.nombre='CRUDO' AND d.fecha BETWEEN :ini AND :fin AND {where_d}
          GROUP BY 1, 2)
        SELECT pozo,
          AVG(v) FILTER (WHERE fecha BETWEEN :desde AND :hasta)     AS avg_valle,
          AVG(v) FILTER (WHERE fecha NOT BETWEEN :desde AND :hasta) AS avg_ref
        FROM dd GROUP BY 1""")
    if ids: q = q.bindparams(sa.bindparam("ids", expanding=True))
    rows = c.execute(q, params).all()
    drivers = []
    if len(rows) > 1:   # 1 pozo => el pozo ES la entidad (redundante) => sin descomposición
        for pozo, av, ar in rows:
            av = float(av or 0); ar = float(ar or 0)
            pct = round((av - ar) / ar * 100, 1) if ar else None
            if pct is not None and pct <= -3:
                drivers.append({"pozo": (pozo or "").strip(), "prod_valle": round(av),
                                "prod_ref": round(ar), "caida": round(av - ar), "caida_pct": pct})
        drivers.sort(key=lambda x: x["caida"])   # más negativo primero

    # (A) comentario(s) que la entidad reportó el día de inicio del valle
    names = _nombres_entidad(c, ids, vid)
    comentarios = []
    if names:
        cq = sa.text(f"""
            SELECT COALESCE(NULLIF(TRIM(fc.area),''), fc.activos) AS campo, fc.comentario
            FROM core.fact_comentarios_produccion fc
            JOIN core.config_reporte cr ON cr.reporte_id = fc.reporte_id
            WHERE cr.fecha_reporte = :onset
              AND fc.comentario IS NOT NULL AND LENGTH(TRIM(fc.comentario)) > 5
              AND ({_AREA_BASE} IN :names OR {_ACTIVOS_BASE} IN :names)
        """).bindparams(sa.bindparam("names", expanding=True))
        for campo, com in c.execute(cq, {"onset": onset, "names": list(names)}):
            comentarios.append({"campo": (campo or "").strip(), "texto": (com or "").strip()[:220]})

    # 🔑 2026-07-16: prioriza el comentario PROPIO de la entidad. `names` incluye grupo1/activos de
    # dim_fuente (el grupo/área con que el reporte la agrupa), así que un comentario del GRUPO también
    # calza: LORITO trae names={LORITO, CPO-09} y el comentario está registrado bajo area='CPO-09'.
    # Si el propio existe, es el diagnóstico verdadero; el del grupo es el respaldo.
    from app.features.consulta.normaliza import norm as _norm
    # El campo puede venir como `CUPIAGUA (CRUDO)`: se compara la BASE, si no el comentario propio
    # se degradaba a "del grupo" y el diagnóstico lo presentaba como ajeno a la entidad.
    _base = lambda s: _norm((s or "").split("(")[0].strip())
    comentarios.sort(key=lambda x: 0 if _base(x.get("campo")) == _norm(entidad) else 1)

    # composición determinista
    pozos_txt = ", ".join(f"{d['pozo']} ({d['caida_pct']}%)" for d in drivers[:3])
    if comentarios:
        quien = (comentarios[0].get("campo") or "").strip()
        # ATRIBUCIÓN HONESTA: antes se componía con `entidad` (lo que el usuario pidió) e ignoraba
        # `quien` (quien lo reportó de verdad, que la consulta ya traía). Resultado: "Lo que reportó
        # LORITO: «...descargas atmosféricas... apagado de los pozos AK107...»" — AK107 es de AKACIAS;
        # el evento es del área CPO-09, y LORITO no reportó nada. El dato es relevante (el evento
        # afecta al área que lo contiene), la atribución no lo era.
        # `quien` puede venir como `CUPIAGUA (CRUDO)`: es la MISMA entidad, con el producto como
        # sufijo. Comparar en crudo la declaraba ajena ("el grupo con el que el reporte agrupa a
        # CUPIAGUA") cuando es su propio comentario; se compara la base y se conserva el producto
        # como contexto útil en el texto.
        propio = bool(quien) and _base(quien) == _norm(entidad)
        if quien and not propio:
            diag = (f"El reporte del {desde} no trae un comentario propio de {entidad}. Lo más cercano "
                    f"es lo que reportó {quien}, el grupo con el que el reporte agrupa a {entidad}: "
                    f"«{comentarios[0]['texto']}»")
        else:
            quien_txt = quien if (quien and quien != entidad) else entidad
            diag = f"Lo que reportó {quien_txt} el {desde}: «{comentarios[0]['texto']}»"
        if drivers:
            diag += f" La caída se reflejó en {pozos_txt}."
        reco = None
    elif drivers:
        diag = (f"El valle de crudo ({desde} a {hasta}) de {entidad} se concentró en {pozos_txt}. "
                "El reporte diario no documenta un motivo operativo específico.")
        reco = f"Se recomienda revisar con operaciones de {entidad} la causa raíz de la caída."
    else:
        diag = (f"El valle de crudo ({desde} a {hasta}) de {entidad} no tiene un motivo documentado "
                "en el reporte diario ni se concentra en un pozo en particular.")
        reco = f"Se recomienda revisar con operaciones de {entidad} la causa de la caída."

    return {"valle": {"desde": desde, "hasta": hasta}, "drivers": drivers, "comentarios": comentarios,
            "generado_por": "base", "diagnostico": diag, "recomendacion": reco}


def _extraer_json(texto, diag=None):
    """Extrae y parsea el primer objeto JSON de la salida del LLM, tolerante a los defectos
    típicos de Gemma: fences ```json, prosa antes/después, comas finales (,] / ,}) y comillas
    tipográficas (“ ” ‘ ’) que rompen json.loads. Si falla, registra el error exacto en diag."""
    if not texto:
        return None
    t = texto.strip()
    t = _re.sub(r"^```(?:json)?\s*", "", t)   # quitar fence de apertura
    t = _re.sub(r"\s*```$", "", t)            # quitar fence de cierre
    # normalizar comillas tipográficas -> rectas (causa típica de json_invalido con acentos/ES)
    t = t.translate({0x201C: 0x22, 0x201D: 0x22, 0x2018: 0x27, 0x2019: 0x27})
    ini = t.find("{")
    if ini < 0:
        return None
    # Localizar el '}' que balancea el primer '{' (respetando strings y escapes)
    prof, fin, en_str, esc = 0, -1, False, False
    for i in range(ini, len(t)):
        ch = t[i]
        if en_str:
            if esc: esc = False
            elif ch == "\\": esc = True
            elif ch == '"': en_str = False
        elif ch == '"': en_str = True
        elif ch == "{": prof += 1
        elif ch == "}":
            prof -= 1
            if prof == 0:
                fin = i + 1
                break
    if fin < 0:
        if diag is not None: diag["parse_err"] = "objeto sin cierre (llaves no balanceadas)"
        return None
    cand = t[ini:fin]
    cand_sin_comas = _re.sub(r",(\s*[}\]])", r"\1", cand)   # reparar comas finales
    err = None
    for c in (cand, cand_sin_comas):
        try:
            return _json.loads(c)
        except Exception as e:
            err = e
    if diag is not None and err is not None:
        diag["parse_err"] = str(err)
    return None


def _situacion_general(titular, sintesis):
    """SITUACIÓN GENERAL declarada por Python (2026-07-16): ¿hay rezago este mes, o no?

    Cuando NINGÚN producto va por debajo de su meta, `sintesis` y `detalle_por_producto` quedan
    VACÍOS: no hay rezago que analizar. Sin decírselo, el prompt igual le exigía a Gemma "la historia
    del mes" y "contrasta lo transitorio con lo estructural" → se inventaba el rezago. Caso
    verificado: CASTILLA campo, CRUDO al 102.7% y pace sobrado, y Gemma narró "déficit significativo
    respecto al promedio histórico" antes de descarrilar. La alucinación era lo grave: con el JSON
    bien formado, ese brief falso se habría pintado como válido. Python declara la verdad y
    _reglas_tesis ramifica el prompt sobre ella."""
    rezagados = [s["producto"] for s in sintesis]
    sin_meta = [t["producto"] for t in titular if t["valor_pct"] is None]
    con_meta = [t for t in titular if t["valor_pct"] is not None]
    if rezagados:
        resumen = "Hay rezago en: " + ", ".join(rezagados) + "."
    elif con_meta:
        resumen = ("NO hay rezago: ningún producto con meta está por debajo de ella ("
                   + ", ".join(f"{t['producto']} {t['valor_pct']}%" for t in con_meta) + ").")
    else:
        resumen = "Ningún producto tiene meta definida en el periodo: no hay cumplimiento que evaluar."
    if sin_meta:
        resumen += (" Sin meta definida (NO es un faltante, no hay con qué compararlos): "
                    + ", ".join(sin_meta) + ".")
    return {"hay_rezago": bool(rezagados), "productos_rezagados": rezagados,
            "productos_sin_meta": sin_meta, "resumen": resumen}


def _reglas_tesis(sit):
    """Reglas de análisis del Ejecutivo, RAMIFICADAS según haya rezago o no (2026-07-16).

    El prompt original asumía que siempre hay un rezago que explicar. Cuando no lo hay, `sintesis` y
    `detalle_por_producto` llegan vacíos y esas mismas reglas ('nárrala', 'contrasta lo transitorio
    con lo estructural', 'menciona campos') empujan al modelo a fabricar el problema que le piden.
    Aquí la instrucción se adapta a la verdad que Python ya calculó."""
    if sit["hay_rezago"]:
        return (
            "TU TAREA NO ES DESCRIBIR, ES ANALIZAR. No recites producto por producto de forma "
            "mecánica: identifica LA historia del mes, lo NO obvio, y prioriza. Apóyate en el bloque "
            "'sintesis' (ya trae la interpretación: qué rezago es transitorio y cuál estructural, y si "
            "el faltante está focalizado en pocos campos o es sistémico) — es tu tesis, nárrala.\n"
            "2. El PRIMER insight es LA historia del mes en 1-2 frases: contrasta lo transitorio (ya "
            "superado, no preocupa) con lo estructural (persiste, es el foco real). Ej. de forma: 'El "
            "mes tiene dos caras: X ya se recuperó de un bache puntual, pero Y arrastra un déficit que "
            "persiste'.\n"
            "3. Distingue SIEMPRE foco de problema sistémico: si el faltante está concentrado en pocos "
            "campos, dilo como una VENTAJA (el problema es localizado, se ataca en esos campos), no solo "
            "como un riesgo.\n"
            "4. Al mencionar campos, contrasta los dos lados (los que arrastran el faltante y los que "
            "lo amortiguan produciendo por encima de su meta). No repitas el mismo dato en dos secciones.\n"
            "SECCIONES: insights = la historia del mes (regla 2) + el hallazgo no obvio (foco) + pace de "
            "crudo. oportunidades = palancas reales (campos por encima de su meta que conviene sostener; "
            "un rezago focalizado que se puede cerrar atacando pocos campos). puntos_atencion = riesgos "
            "priorizados. decisiones = acciones concretas y priorizadas.\n"
        )
    # --- Sin rezago: la única falla posible aquí es inventarse uno ---
    return (
        "TU TAREA NO ES DESCRIBIR, ES ANALIZAR — pero lee primero 'situacion_general': " + sit["resumen"] + "\n"
        "REGLA CERO, INQUEBRANTABLE: ESTE MES NO HAY REZAGO. Está PROHIBIDO inventar un déficit, un "
        "faltante, una caída estructural o un problema que los datos no muestran. Sería FALSO y el "
        "directivo tomaría decisiones sobre un problema inexistente. Si te falta material para una "
        "sección, escribe UNA sola frase honesta (ej. 'Sin puntos de atención críticos en el periodo') "
        "en vez de rellenar.\n"
        "2. El PRIMER insight es que la entidad va en meta o por encima, con el porcentaje EXACTO. Lo "
        "analítico aquí no es buscar culpables: es decir QUÉ sostiene el resultado y qué lo pondría en "
        "riesgo de cara al cierre.\n"
        "3. 'detalle_por_producto' viene VACÍO porque no hay faltante que descomponer. NO menciones "
        "campos ni inventes nombres: no tienes ese dato.\n"
        "4. Si hubo un valle de crudo ya recuperado, es contexto de un bache puntual superado, NO un "
        "rezago del mes. Atribuye una causa SOLO si aparece en 'eventos_del_valle'. Si ese bloque "
        "viene vacío, no tienes la causa a la mano: NO la inventes, y tampoco afirmes que no existe "
        "(puede estar documentada en otra parte del reporte).\n"
        "5. Mira 'pace_crudo': si 'requerido_dia' es MENOR que 'promedio_dia' el ritmo actual SOBRA "
        "para cerrar en meta (buena noticia, delta_pct negativo); solo si es mayor hay exigencia. NO lo "
        "leas al revés.\n"
        "SECCIONES: insights = el resultado y con qué margen + qué lo sostiene + lectura del pace. "
        "oportunidades = qué conviene sostener o aprovechar. puntos_atencion = riesgos REALES de cara al "
        "cierre (si no los hay, dilo en una frase). decisiones = acciones concretas para sostener el "
        "desempeño (si no hay nada que corregir, basta con monitorear lo que corresponda).\n"
    )


def _llm_insight(prompt, timeout=60, diag=None, intentos=2):
    """Reusa el patrón de extraccion.py. Devuelve dict o None (fallback). get_settings() LAZY (INS-C).
    Si se pasa un dict `diag`, se rellena con el motivo del fallo (status + raw truncado) para
    diagnóstico — no cambia el tipo de retorno (dict|None), así desempeno_insight sigue igual.

    `intentos`: reintenta SOLO si Ollama abortó la generación (done=false). Ese fallo es transitorio
    y no determinista —el mismo prompt completa unas veces y aborta otras (verificado en dev)—, así
    que reintentar es el arreglo, no solo diagnosticarlo. NO se reintenta un json_invalido: ahí el
    modelo sí respondió entero y repetir daría lo mismo (temperature=0), solo latencia de más."""
    for intento in range(1, intentos + 1):
        r = _llm_insight_once(prompt, timeout=timeout, diag=diag)
        if r is not None or (diag or {}).get("status") != "generacion_abortada":
            return r
        if diag is not None:
            diag["intentos"] = intento
    return None


def _llm_insight_once(prompt, timeout=60, diag=None):
    """Una sola llamada a Ollama. Ver _llm_insight para la política de reintento."""
    try:
        s = get_settings()
        # Modelo + host efectivos en el diag → el frontend puede loguear "gemma4:latest @ 10.100.26.139"
        # y validar que la petición fue a la Gemma del servidor (aunque luego falle el parseo).
        if diag is not None:
            diag["model"] = s.consulta_llm_model
            diag["host"] = s.consulta_ollama_url
        # format=json obliga a Ollama a emitir JSON sintácticamente válido (elimina fences,
        # prosa y comas/comillas rotas de raíz). num_predict alto para que el objeto quepa entero.
        # num_ctx EXPLÍCITO (2026-07-16): el default de Ollama puede ser 2048; con un prompt de
        # ~1.200-1.700 tokens el objeto de 4 secciones no cabe y la generación se corta a media
        # llave (síntoma: json_invalido 'objeto sin cierre'). Fijarlo elimina la variable.
        body = _json.dumps({"model": s.consulta_llm_model, "prompt": prompt, "stream": False,
                            "format": "json", "keep_alive": s.keep_alive_ollama,
                            "options": {"temperature": 0, "num_predict": 2048,
                                        "num_ctx": 8192}}).encode()
        req = _urlreq.Request(s.consulta_ollama_url, data=body,
                              headers={"Content-Type": "application/json"})
        with _urlreq.urlopen(req, timeout=timeout) as r:
            resp = _json.load(r)
        salida = resp.get("response", "")
        if diag is not None:
            diag["raw"] = (salida or "")[:2000]
            diag["raw_len"] = len(salida or "")
            # POR QUÉ paró el modelo. Sin esto, un fragmento cortado y un JSON mal escrito son
            # indistinguibles: ambos caen en "json_invalido" y mandan a diagnosticar el prompt.
            diag["done_reason"] = resp.get("done_reason")
            diag["out_tok"] = resp.get("eval_count")
            diag["prompt_tok"] = resp.get("prompt_eval_count")
        # 🔑 2026-07-16: Ollama devuelve done=false cuando ABORTA la generación a mitad (runner
        # caído/evicted, presión de memoria...). El `response` que acompaña es un FRAGMENTO, no la
        # respuesta del modelo. Antes se parseaba igual y el panel acusaba "json_invalido · objeto
        # sin cierre" — culpando al JSON de algo que no era del JSON, y mandando a revisar prompt y
        # gramática. Verificado en dev: el MISMO prompt/modelo/opciones a veces completa
        # (done_reason='stop', JSON válido) y a veces aborta → es inestabilidad del runner, no el
        # prompt. Se declara como lo que es y NO se intenta parsear el fragmento.
        if resp.get("done") is False:
            if diag is not None:
                diag["status"] = "generacion_abortada"
            return None
        parsed = _extraer_json(salida, diag=diag)
        if parsed is None:
            if diag is not None: diag["status"] = "json_invalido"
            return None
        if diag is not None: diag["status"] = "ok"
        return parsed
    except Exception as e:
        if diag is not None: diag["status"] = "timeout_o_red:" + type(e).__name__
        return None


@router.get("/desempeno_insight")
def desempeno_insight(entidad: str | None = Query(None), segmento: str = Query("ecp"),
                      nivel: str | None = Query(None), periodo: str | None = Query(None)):
    if segmento == "filiales":
        return _desempeno_insight_filiales()
    import calendar
    eng = get_engine()
    with eng.connect() as c:
        amb = _ambito(c, entidad, nivel, periodo)
        if amb is None:
            return {"entidad": entidad, "encontrada": False}
        if amb.get("sin_datos"):
            return {"entidad": entidad, "encontrada": True, "sin_datos": True}
        ids, vid = amb["ids"], amb["vid"]
        y, mo, dim, ini, fin = amb["y"], amb["mo"], amb["dim"], amb["ini"], amb["fin"]
        base = {}
        if ids: base["ids"] = ids
        if vid is not None: base["vid"] = vid
        def _b(sql):
            t = sa.text(sql)
            return t.bindparams(sa.bindparam("ids", expanding=True)) if "ids" in base else t
        def where(a):
            p = (a + ".") if a else ""
            cs = []
            if ids: cs.append(f"{p}fuente_id IN :ids")
            if vid is not None: cs.append(f"{p}vice_id = :vid")
            return "(" + " OR ".join(cs) + ")" if cs else "TRUE"

        # KPIs REAL vs PPTO (mensual) — mismos que /desempeno (DI3, H2)
        pm = dict(base); pm["fin"] = fin
        kpi = {}
        for r in c.execute(_b(f"""
            SELECT tp.nombre, es.nombre, SUM(m.volumen)
            FROM core.fact_produccion_mes_ecp m
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = m.tipo_producto_id
            JOIN core.dim_escenario es ON es.escenario_id = m.escenario_id
            WHERE m.fecha = :fin AND es.nombre IN ('REAL','PPTO') AND {where('m')}
            GROUP BY 1,2"""), pm):
            kpi.setdefault(r[0], {})[r[1]] = float(r[2] or 0)
        titular = []
        for p in ["CRUDO", "GAS", "BLANCOS"]:
            real = kpi.get(p, {}).get("REAL", 0.0); ppto = kpi.get(p, {}).get("PPTO", 0.0)
            pct = round(real / ppto * 100.0, 1) if ppto else None
            titular.append({"producto": p, "valor_pct": pct, "estado": _estado(pct), "texto": ""})

        # serie crudo diaria → detección de valle
        pd = dict(base); pd["ini"] = ini; pd["fin"] = fin
        srows = c.execute(_b(f"""
            SELECT d.fecha, SUM(d.volumen)
            FROM core.fact_produccion_dia_ecp d
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = d.tipo_producto_id
            WHERE tp.nombre='CRUDO' AND d.fecha BETWEEN :ini AND :fin AND {where('d')}
            GROUP BY 1 ORDER BY 1"""), pd).all()
        serie = [(r[0].isoformat(), float(r[1] or 0)) for r in srows]
        valle = _detectar_valle(serie)
        curva_crudo = {"fechas": [f for f, _ in serie], "valores": [v for _, v in serie]}

        anotaciones, eventos, eventos_extra = None, [], {"campos": 0, "pozos_aprox": 0}
        valle_diag = None
        if valle:
            from datetime import date as _date
            dd = [int(x) for x in valle["desde"].split("-")]
            onset = _date(*dd)
            if entidad:   # panel filtrado → valle explicado POR la entidad (su comentario + sus pozos). D-V1
                valle_diag = _valle_diagnostico_entidad(c, entidad, ids, vid, valle, y, mo, dim, onset)
            else:         # panel GLOBAL → tabla de eventos global (comportamiento actual). D-V2
                eventos, eventos_extra = _eventos_valle(c, onset)
            anotaciones = {
                "banda": {"desde": valle["desde"], "hasta": valle["hasta"], "label": "valle"},
                "punto": {"fecha": valle["min_fecha"], "valor": valle["min_valor"], "label": ""},
            }

        # ---- Prosa: LLM (grounded) o fallback estático ----
        peor = min([t for t in titular if t["valor_pct"] is not None],
                   key=lambda t: t["valor_pct"], default=None)

        # Aporte al gap por campo (producto más rezagado) — BARRILES, no conteo de pozos.
        # Top detractores (gap<0) y compensadores (gap>0) desde fact_produccion_mes_ecp.
        gap_detr, gap_comp = [], []
        if peor:
            pg = dict(base); pg["fin"] = fin; pg["prod"] = peor["producto"]
            grows = c.execute(_b(f"""
                SELECT COALESCE(NULLIF(TRIM(f.campo),''), f.nombre) AS campo,
                       SUM(CASE WHEN es.nombre='REAL' THEN m.volumen ELSE 0 END) AS vreal,
                       SUM(CASE WHEN es.nombre='PPTO' THEN m.volumen ELSE 0 END) AS vppto
                FROM core.fact_produccion_mes_ecp m
                JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = m.tipo_producto_id
                JOIN core.dim_escenario es ON es.escenario_id = m.escenario_id
                JOIN core.dim_fuente f ON f.fuente_id = m.fuente_id
                WHERE m.fecha = :fin AND es.nombre IN ('REAL','PPTO') AND tp.nombre = :prod AND {where('m')}
                GROUP BY 1"""), pg).all()
            difs = [((r[0] or "").strip(), float(r[1] or 0) - float(r[2] or 0))
                    for r in grows if (r[1] or r[2])]
            gap_detr = [{"campo": k, "gap": round(v)} for k, v in sorted(difs, key=lambda x: x[1])[:3] if v < 0]
            gap_comp = [{"campo": k, "gap": round(v)} for k, v in sorted(difs, key=lambda x: -x[1])[:2] if v > 0]

        # Pace de cierre (CRUDO): realizado MTD vs ritmo requerido en los días restantes para cerrar en PPTO.
        pace = None
        if serie:
            mtd = sum(v for _, v in serie); ndias = len(serie); rest = dim - ndias
            ppto_crudo = kpi.get("CRUDO", {}).get("PPTO", 0.0)
            if rest > 0 and ppto_crudo and ndias:
                prom = mtd / ndias
                req = (ppto_crudo - mtd) / rest
                pace = {"mtd": round(mtd), "dias": ndias, "restantes": rest,
                        "promedio_dia": round(prom), "requerido_dia": round(req),
                        "delta_pct": (round((req / prom - 1) * 100, 1) if prom else None)}

        ctx = {"periodo": f"{MESES_ES[mo]} {y}", "corte": f"{len([1 for _ in serie])}/{dim}",
               "titular": [{"p": t["producto"], "pct": t["valor_pct"]} for t in titular],
               "valle": valle, "eventos": eventos,
               "gap_detractores": gap_detr, "gap_compensadores": gap_comp,
               "pace_crudo": pace}
        # El LLM SOLO redacta la lectura ejecutiva (prosa). Las etiquetas de estado del chip y el
        # label del valle son CLASIFICACIONES derivadas del número → las fija Python (contrato).
        prompt = (
            "Eres analista de producción. Con estos datos EXACTOS (no inventes ni calcules números, no "
            "agregues cifras nuevas), responde SOLO un JSON de una línea: "
            '{"lectura_ejecutiva":"..."}. '
            "lectura_ejecutiva: 3-5 frases ejecutivas que cubran: (1) el desempeño del mes por producto; "
            "(2) si hay valle, su causa; (3) qué campos explican el rezago del producto más bajo "
            "(gap_detractores, en volumen) y quién compensa (gap_compensadores); (4) el pace de cierre "
            "de crudo: con pace_crudo, indica si el ritmo requerido en los días restantes "
            "(requerido_dia, delta_pct) es alcanzable frente al promedio actual (promedio_dia). "
            "Datos: " + _json.dumps(ctx, ensure_ascii=False))
        prosa = _llm_insight(prompt)
        generado = "llm"
        if not isinstance(prosa, dict) or "lectura_ejecutiva" not in prosa:
            generado = "fallback"
            _fr = []
            if peor:
                _fr.append(f"El mayor rezago es {peor['producto'].lower()} ({peor['valor_pct']}%).")
            if gap_detr:
                _fr.append("El gap se concentra en " + ", ".join(
                    f"{g['campo']} ({g['gap']:,})".replace(",", ".") for g in gap_detr) + ".")
            if gap_comp:
                _fr.append("Compensa parcialmente " + ", ".join(
                    f"{g['campo']} (+{g['gap']:,})".replace(",", ".") for g in gap_comp) + ".")
            if pace and pace.get("delta_pct") is not None:
                _fr.append(f"Para cerrar crudo en presupuesto, los {pace['restantes']} días restantes "
                           f"exigen {pace['requerido_dia']:,} bls/día".replace(",", ".") +
                           f" ({pace['delta_pct']:+}% vs el ritmo actual).")
            _fr.append("La caída de crudo del valle está explicada por eventos operativos y ya se recuperó."
                       if valle else "Producción sin anomalías diarias relevantes en el periodo.")
            prosa = {"lectura_ejecutiva": " ".join(_fr)}
        # etiquetas de estado del chip (Python, coherentes con el color del semáforo; "" = producto inexistente)
        _et = {"ok": "Alineado", "warn": "Rezagado", "alert": "Foco", "": "—"}
        for t in titular:
            t["texto"] = _et.get(t["estado"], "—")
        if anotaciones:
            anotaciones["banda"]["label"] = "valle"   # label corto y fijo (no prosa del LLM → no se corta)
            mv = anotaciones["punto"]["valor"]
            anotaciones["punto"]["label"] = f"mín · {mv/1e6:.2f}M"

        # acciones (intents Python; label estático MVP)
        acciones = []
        if peor:
            acciones.append({"label": f"Diagnóstico de {peor['producto'].lower()}",
                             "intent": f"diagnostico_{peor['producto'].lower()}"})
        if valle:
            acciones.append({"label": "Monitorear estabilidad eléctrica", "intent": "monitor_electrico"})

        return {
            "entidad": entidad, "encontrada": True,
            "meta": {"scope": entidad or "Global (toda la producción ECP)",
                     "periodo": f"{MESES_ES[mo]} {y}", "corte": f"{len(serie)}/{dim}",
                     "generado_por": generado},
            "titular": titular, "curva_crudo": curva_crudo, "anotaciones": anotaciones,
            "eventos": eventos, "eventos_extra": eventos_extra,
            "valle_diagnostico": valle_diag,   # D-V1: valle explicado por la entidad (None en el panel global)
            "gap": {"producto": (peor or {}).get("producto"), "detractores": gap_detr,
                    "compensadores": gap_comp},   # trazabilidad: los números que sustentan la lectura
            "pace_crudo": pace,
            "lectura_ejecutiva": str(prosa.get("lectura_ejecutiva") or "")[:900],
            "accion_sugerida": acciones,
        }


# ============================================================================
# Análisis Ejecutivo multi-sección (insights/oportunidades/puntos_atencion/decisiones).
# Python calcula la estructura completa (gap RECONCILIADO por campo, flags); el LLM (Gemma,
# vía _llm_insight) SOLO pule la prosa -- es pulido OPCIONAL. El composer determinista
# (_ejec_fallback) es el entregable de default: nunca queda en blanco.
# Sandbox v1: se consume desde la tarjeta "Filiales" del conversacional (H6, "EN PRUEBAS");
# el dato analizado sigue siendo ECP (no filiales). NO toca desempeno_insight.
# ============================================================================
def _flags_ejecutivo(titular, gap_por_producto, valle, pace, ultimo_dia):
    """Flags Python (nunca del LLM): producto_critico(<60%), gap_concentrado(>=70%),
    valle_activo (el valle no se ha recuperado a la fecha de corte), pace_exigente(delta>=10%)."""
    flags = []
    for t in titular:
        if t["valor_pct"] is not None and t["valor_pct"] < 60:
            flags.append({"tipo": "producto_critico", "severidad": "alta",
                          "producto": t["producto"], "pct": t["valor_pct"]})
    for p, g in gap_por_producto.items():
        if g["concentracion_pct"] is not None and g["concentracion_pct"] >= 70:
            flags.append({"tipo": "gap_concentrado", "severidad": "media", "producto": p,
                          "concentracion_pct": g["concentracion_pct"],
                          "campos": [d["campo"] for d in g["detractores"]]})
    if valle:
        activo = bool(ultimo_dia) and valle["hasta"] == ultimo_dia
        flags.append({"tipo": "valle_activo", "severidad": "media" if activo else "baja",
                      "activo": activo, "desde": valle["desde"], "hasta": valle["hasta"]})
    if pace and pace.get("delta_pct") is not None and pace["delta_pct"] >= 10:
        flags.append({"tipo": "pace_exigente", "severidad": "media",
                      "delta_pct": pace["delta_pct"], "requerido_dia": pace["requerido_dia"],
                      "promedio_dia": pace["promedio_dia"], "restantes": pace["restantes"]})
    return flags


def _ejec_fallback(periodo, titular, gap_por_producto, valle, eventos, eventos_extra, pace, flags,
                   meta_nombre="presupuesto",
                   frase_dep="riesgo de dependencia de pocos campos",
                   frase_prio="los campos que más arrastran"):
    """Composer determinista: arma las 4 secciones desde las cifras ya reconciliadas.
    ES el entregable por defecto (H4) -- debe quedar completo y legible SIN el LLM.
    meta_nombre/frase_dep/frase_prio: por defecto = redacción ECP EXACTA; el segmento filiales
    los pasa distintos (programa / filiales). El guard 'peor >= 100' evita hablar de 'rezago'
    cuando todos los productos cerraron por encima de la meta (caso real de filiales)."""
    def _fmt(n):
        return f"{n:,.0f}".replace(",", ".")

    valle_activo = any(f["tipo"] == "valle_activo" and f["activo"] for f in flags)

    insights = []
    partes = [f"{t['producto'].capitalize()} {t['valor_pct']}%" for t in titular if t["valor_pct"] is not None]
    if partes:
        insights.append(f"Cierre de {periodo}: " + ", ".join(partes) + f" del {meta_nombre}.")
    peor = min([t for t in titular if t["valor_pct"] is not None], key=lambda t: t["valor_pct"], default=None)
    if peor:
        if peor["valor_pct"] >= 100:
            insights.append(f"Todos los productos cerraron por encima del {meta_nombre}; el más ajustado es "
                            f"{peor['producto'].lower()} ({peor['valor_pct']}%).")
        else:
            insights.append(f"El mayor rezago está en {peor['producto'].lower()} ({peor['valor_pct']}% del {meta_nombre}).")
    if valle:
        estado_valle = "y continúa sin recuperarse a la fecha de corte" if valle_activo else "y ya se recuperó"
        insights.append(f"La producción de crudo tuvo un valle entre el {valle['desde']} y el {valle['hasta']} "
                        f"(mínimo el {valle['min_fecha']}) {estado_valle}.")
    for p, g in gap_por_producto.items():
        if g["detractores"]:
            campos = ", ".join(f"{d['campo']} (faltante {_fmt(abs(d['gap']))})" for d in g["detractores"])
            conc = f" — concentración {g['concentracion_pct']}%" if g["concentracion_pct"] is not None else ""
            insights.append(f"El faltante de {p.lower()} se concentra en {campos}{conc}.")
    if pace and pace.get("delta_pct") is not None:
        insights.append(f"Para cerrar crudo en {meta_nombre} se requieren {_fmt(pace['requerido_dia'])} bls/día en "
                        f"los {pace['restantes']} días restantes ({pace['delta_pct']:+}% vs el promedio actual "
                        f"de {_fmt(pace['promedio_dia'])}).")
    if not insights:
        insights.append("Producción sin hallazgos relevantes en el periodo.")

    oportunidades = []
    for p, g in gap_por_producto.items():
        if g["compensadores"]:
            campos = ", ".join(f"{d['campo']} (excedente {_fmt(d['gap'])})" for d in g["compensadores"])
            oportunidades.append(f"{campos} produjeron por encima de su meta y amortiguan parte del faltante "
                                 f"de {p.lower()}; sostener su ritmo ayuda a cerrar la brecha.")
    if valle and not valle_activo:
        oportunidades.append("El valle de crudo fue transitorio (eventos operativos) — no hay evidencia de "
                             "una caída estructural.")
    if not oportunidades:
        oportunidades.append("Sin oportunidades adicionales identificadas en el periodo.")

    puntos_atencion = []
    for f in flags:
        if f["tipo"] == "producto_critico":
            puntos_atencion.append(f"{f['producto']} está en zona crítica: {f['pct']}% del {meta_nombre} (<60%).")
        elif f["tipo"] == "gap_concentrado":
            puntos_atencion.append(f"El faltante de {f['producto'].lower()} está muy concentrado (~{f['concentracion_pct']}% "
                                   f"en {', '.join(f['campos'])}) — {frase_dep}.")
        elif f["tipo"] == "pace_exigente":
            puntos_atencion.append(f"El ritmo requerido para crudo exige un +{f['delta_pct']}% sobre el promedio "
                                   f"actual — meta exigente para los días restantes.")
        elif f["tipo"] == "valle_activo" and f["activo"]:
            puntos_atencion.append(f"El valle de crudo iniciado el {f['desde']} continúa a la fecha de corte, "
                                   f"sin señales de recuperación.")
    for p, g in gap_por_producto.items():
        if g["reconciliado"] is False:
            puntos_atencion.append(f"La descomposición por campo de {p.lower()} presenta un desfase de "
                                   f"{g['desfase_pct']}% frente al KPI; cifras a validar.")
    if not puntos_atencion:
        puntos_atencion.append("Sin puntos de atención críticos en el periodo.")

    decisiones = []
    for p, g in gap_por_producto.items():
        if g["detractores"]:
            campos = " y ".join(d["campo"] for d in g["detractores"][:2])
            decisiones.append(f"Priorizar diagnóstico operativo en {campos} ({frase_prio} el faltante de {p.lower()}).")
    if valle:
        decisiones.append("Monitorear la estabilidad eléctrica/operativa en los campos afectados por el valle de crudo.")
    if pace and pace.get("delta_pct") is not None and pace["delta_pct"] >= 10:
        decisiones.append(f"Acordar con operaciones un ritmo de {_fmt(pace['requerido_dia'])} bls/día de crudo "
                          f"para los próximos {pace['restantes']} días.")
    if not decisiones:
        decisiones.append("Mantener el seguimiento habitual del cierre de mes; sin acciones adicionales urgentes.")

    return {"insights": insights[:5], "oportunidades": oportunidades[:4],
            "puntos_atencion": puntos_atencion[:4], "decisiones": decisiones[:4]}


def _focos(titular, gap_lag, valle, eventos, tarjetas=None, extremos=None):
    """Nivel 2: UNA tarjeta por producto, en orden FIJO Crudo→Gas→Blancos (decisión del usuario
    2026-07-26). Ya NO se rankea por impacto ni se filtra a los rezagados: los 3 productos salen
    SIEMPRE. Producto rezagado (vs PPTO con detractores, o vs su promedio del año sin PPTO) → sus
    campos que fallan + causa (lógica intacta). Producto que va bien → panorama con 2 mayores + 2
    menores por producción, que sí produzcan (`extremos` = {producto: [{campo,real,meta}]})."""
    def _fmt(n): return f"{abs(float(n)):,.0f}".replace(",", ".")
    extremos = extremos or {}
    _ORDEN = ["CRUDO", "GAS", "BLANCOS"]
    def _ok_lbl(tt, has_prod):
        # etiqueta honesta de un producto que NO va mal: alineado (≥meta) / ajustado (< pero sin
        # campo detractor claro) / sin meta (produce pero no hay PPTO) / sin producción (no produce).
        _p = tt.get("valor_pct")
        if _p is not None and _p >= 100: return "Alineado"
        if _p is not None: return "Ajustado"
        return "Sin meta" if has_prod else "Sin producción"

    def _sin_prod(tt, has_prod):
        """[2026-07-29] True SOLO cuando el producto no produce y no tiene meta -> no hay nada que
        mostrar y el frontend lo omite (un campo que solo da crudo no debe pintar bloques vacios de
        gas/blancos). Espeja la condicion de _ok_lbl para que el flag y la etiqueta no divergan.

        OJO: un producto que produce 0 TENIENDO meta NO entra aqui. Eso es una merma real -- el caso
        ARAUCA/gas verificado el 25-jul (paro de 30+17 dias) -- y tiene que seguir visible."""
        return (tt or {}).get("valor_pct") is None and not has_prod
    tby = {t["producto"]: t for t in titular}
    tarj_by = {k.get("producto"): k for k in (tarjetas or [])}
    focos = []
    for rank, p in enumerate(_ORDEN, 1):
        t = tby.get(p)
        if not t:
            continue
        pct = t["valor_pct"]
        g = gap_lag.get(p)
        k = tarj_by.get(p)
        rez_gap = pct is not None and pct < 100 and bool(g and g.get("detractores"))
        rez_prom = (not rez_gap and bool(k and k.get("meta_de_promedio"))
                    and (k.get("meta_mes") or 0) and (k.get("proyectado_cierre") or 0) < (k.get("meta_mes") or 0))
        if rez_gap:
            detr = g["detractores"][:2]
            ents = [d["campo"] for d in detr]
            faltante = float(t["real"]) - float(t["ppto"])
            # 🔑 2026-07-23: la concentración se calcula sobre LOS CAMPOS QUE SE NOMBRAN, no sobre el
            # top-3 fijo (con 2 campos el valor real de CUSIANA+CUPIAGUA es 88.2%, no 90.6%).
            bruto = abs(float(g.get("faltante_bruto") or 0))
            conc_ents = round(abs(sum(d["gap"] for d in detr)) / bruto * 100, 1) if bruto else None
            titulo = ("concentra el rezago del producto" if (len(ents) == 1 or conc_ents is None)
                      else f"{conc_ents}% del faltante en {len(ents)} campos")
            comp = g["compensadores"][0] if g.get("compensadores") else None
            accion = (f"sostener {comp['campo']} (+{_fmt(comp['gap'])}) como amortiguador"
                      if comp else "plan de recuperación específico")
            # El detalle lista faltantes BRUTOS; el titular es el NETO. Se cierra con la aritmética.
            detalle = [f"{d['campo']}: faltante {_fmt(d['gap'])}" for d in g["detractores"]]
            exced = float(g.get("excedente_bruto") or 0)
            if bruto and exced:
                detalle.append(f"Faltante bruto {_fmt(bruto)} − excedentes {_fmt(exced)} "
                               f"= neto {_fmt(faltante)}")
            # Fuente/soporte real (Épica 1 criterio 2): comentarios del reporte para los campos
            # NOMBRADOS. NUNCA se inventa: si no hay comentario que calce → texto genérico.
            eventos_causa = [{"campo": d["campo"], "fecha": ev["fecha"], "texto": ev["texto"]}
                              for d in detr for ev in (d.get("eventos") or [])]
            if eventos_causa:
                e0 = eventos_causa[0]
                causa_texto = f"{e0['campo']} ({e0['fecha']}): «{e0['texto']}»"
                causa_cobertura = "con_evento"
            else:
                causa_texto = "sin evento asociado en comentarios — requiere validación en campo"
                causa_cobertura = "sin_evento"
            focos.append({
                "producto": p, "entidades": ents, "faltante_abs": round(faltante),
                "faltante_bruto": g.get("faltante_bruto"), "excedente_bruto": g.get("excedente_bruto"),
                "magnitud_txt": None, "peso_relativo_pct": conc_ents, "es_ok": False,
                "estado_label": "Foco", "sin_produccion": False, "titulo": titulo,
                "causa": {"texto": causa_texto, "cobertura": causa_cobertura,
                          "detalle": detalle, "eventos": eventos_causa},
                "accion": accion, "tipo": "gap", "score": round(abs(faltante)), "rank": rank,
            })
        elif rez_prom:
            proy = k.get("proyectado_cierre") or 0.0
            meta = k.get("meta_mes") or 0.0
            dev = round((1 - proy / meta) * 100)
            focos.append({
                "producto": p, "entidades": [], "faltante_abs": round(proy - meta),
                "magnitud_txt": None, "peso_relativo_pct": None, "es_ok": False,
                "estado_label": "Foco", "sin_produccion": False,
                "titulo": f"{dev}% por debajo de su promedio 2026",
                "causa": {"texto": "produjo por debajo de su promedio del año — sin meta presupuestal en el periodo",
                          "cobertura": "sin_meta", "detalle": []},
                "accion": "revisar el comportamiento del producto frente a su histórico",
                "tipo": "promedio", "score": round(abs(proy - meta)), "rank": rank,
            })
        else:
            # Va bien → panorama: 2 mayores + 2 menores por producción (que sí produzcan).
            ext = extremos.get(p, [])
            ents = [e["campo"] for e in ext]
            focos.append({
                "producto": p, "entidades": ents, "faltante_abs": None,
                "faltante_bruto": None, "excedente_bruto": None,
                "magnitud_txt": None, "peso_relativo_pct": None, "es_ok": True,
                "estado_label": _ok_lbl(t, bool(ext)),
                "sin_produccion": _sin_prod(t, bool(ext)),
                "titulo": "", "extremos": ext,
                "causa": {"texto": "", "cobertura": "ok", "detalle": [], "eventos": []},
                "accion": "", "tipo": "ok", "score": 0, "rank": rank,
            })
    return focos


def _sin_foco(titular, gap_full, valle):
    def _fmt(n): return f"{abs(float(n)):,.0f}".replace(",", ".")
    pos = []
    for t in titular:
        g = gap_full.get(t["producto"])
        for comp in (g.get("compensadores") if g else []) or []:
            pos.append(f"{comp['campo']} en {t['producto'].lower()} (+{_fmt(comp['gap'])})")
    partes = []
    if pos: partes.append("con excedentes: " + ", ".join(pos[:3]))
    if valle: partes.append("Crudo recuperado del valle")
    return " · ".join(partes) if partes else "Sin elementos adicionales."


# ─────────────────────────────────────────────────────────────────────────────
# FOCOS de FILIALES sobre la MISMA base que las tarjetas: proyección de cierre vs
# PROMEDIO 2026 (NO vs programa, NO valle). El _focos/_sin_foco de ECP mide contra el
# PROGRAMA misma-ventana, así que en filiales contradecía a las tarjetas (p.ej. Permian
# aparecía como "excedente en crudo" mientras su tarjeta lo marca 146k POR DEBAJO de su
# promedio 2026). Estas funciones descomponen el faltante del GRUPO por filial usando la
# tendencia (proy vs promedio_2026), la misma fuente que el desglose por filial → coherencia.
# ─────────────────────────────────────────────────────────────────────────────
def _fil_difs_por_producto(producto, por_filial_raw):
    """[(empresa, proy, prom, faltante=proy-prom)] para un producto, desde la tendencia por filial."""
    difs = []
    for pf in por_filial_raw:
        for pp in (pf["t"].get("por_producto") or []):
            if pp.get("producto") == producto and pp.get("reporta") and pp.get("promedio_2026"):
                proy = float(pp["proyeccion"]); prom = float(pp["promedio_2026"])
                difs.append((pf["empresa"], proy, prom, proy - prom))
    return difs


def _focos_filiales(titular_cards, por_filial_raw):
    """Nivel 2 (filiales) coherente con las tarjetas. Un foco por producto cuyo GRUPO proyecta por
    debajo de su promedio 2026, atribuido a las filiales que quedan por debajo (base promedio 2026)."""
    def _fmt(n): return f"{abs(float(n)):,.0f}".replace(",", ".")
    focos = []
    for tc in titular_cards:
        p = tc["producto"]; proj = float(tc.get("real") or 0); meta = float(tc.get("ppto") or 0)
        if not meta or proj >= meta:                      # el grupo está en/por encima de su promedio
            continue
        faltante_grupo = proj - meta
        difs = _fil_difs_por_producto(p, por_filial_raw)
        detr = sorted([d for d in difs if d[3] < 0], key=lambda x: x[3])       # más negativo primero
        comp = sorted([d for d in difs if d[3] > 0], key=lambda x: -x[3])
        ents = [d[0] for d in detr[:2]]
        total_neg = sum(-d[3] for d in detr) or 1.0
        conc = round(sum(-d[3] for d in detr[:2]) / total_neg * 100) if detr else None
        n_fil = len(detr)
        # El frontend ya antepone f.entidades → el título NO las repite (evita "Permian + Hocol Permian…").
        if not ents:
            titulo = f"{round((1 - proj / meta) * 100)}% por debajo de su promedio 2026"
        elif len(ents) == 1 or conc is None:
            titulo = "concentra el rezago del producto"
        else:
            titulo = f"{conc}% del faltante en {min(n_fil, 2)} filiales"
        amort = comp[0] if comp else None
        accion = (f"sostener {amort[0]} (+{_fmt(amort[3])}) como amortiguador" if amort
                  else "plan de recuperación en las filiales rezagadas")
        focos.append({
            "producto": p, "entidades": ents, "faltante_abs": round(faltante_grupo),
            "magnitud_txt": None, "peso_relativo_pct": conc,
            "titulo": titulo,
            "causa": {"texto": "proyecta por debajo de su promedio 2026 — sin meta presupuestal en filiales",
                      "cobertura": "sin_meta",
                      "detalle": [f"{d[0]}: faltante {_fmt(d[3])} (proy {_fmt(d[1])} vs prom {_fmt(d[2])})"
                                  for d in detr]},
            "accion": accion, "tipo": "promedio", "score": round(abs(faltante_grupo)),
        })
    focos.sort(key=lambda f: f["score"], reverse=True)
    for i, f in enumerate(focos, 1):
        f["rank"] = i
    return focos[:5]


def _sin_foco_filiales(titular_cards, por_filial_raw):
    """Excedentes reales (base promedio 2026): solo filiales POR ENCIMA en cada producto — así Permian
    en crudo NUNCA aparece como excedente si su tarjeta lo marca por debajo (fin de la contradicción)."""
    def _fmt(n): return f"{abs(float(n)):,.0f}".replace(",", ".")
    pos = []
    for tc in titular_cards:
        p = tc["producto"]
        for emp, proy, prom, exc in _fil_difs_por_producto(p, por_filial_raw):
            if exc > 0:
                pos.append((exc, f"{emp} en {p.lower()} (+{_fmt(exc)})"))
    pos.sort(key=lambda x: -x[0])
    return "con excedentes: " + ", ".join(s for _, s in pos[:3]) if pos else "Sin elementos adicionales."


@router.get("/ejecutivo")
def ejecutivo(entidad: str | None = Query(None), segmento: str = Query("ecp"),
             nivel: str | None = Query(None), periodo: str | None = Query(None),
             pulir: bool = Query(True)):
    """Análisis Ejecutivo (IA) multi-sección: insights / oportunidades / puntos_atencion / decisiones.
    Reusa el patrón de /desempeno_insight (resolución de entidad, mes objetivo, KPIs REAL/PPTO,
    _detectar_valle, _eventos_valle, pace_crudo, _llm_insight) y agrega el gap RECONCILIADO por
    producto rezagado + flags Python. El composer determinista (_ejec_fallback) es el default
    entregable; el LLM (Gemma) es pulido opcional (timeout=120s, solo on-demand).
    segmento='filiales' → delega en _ejecutivo_filiales (fuente/reglas distintas).
    pulir=False (solo lo usa consulta_v2/Analizar): SALTA el pulido LLM de `secciones` (Gemma,
    timeout 180s) y sirve el fallback determinista. El endpoint/tablero no pasa `pulir` → True →
    comportamiento byte-idéntico. Evita que el chat de Analizar cuelgue esperando una prosa que
    de todas formas descarta (plan_analizar_fase1_2026-08-02.md, RA-1)."""
    if segmento == "filiales":
        return _ejecutivo_filiales()
    import calendar
    eng = get_engine()
    with eng.connect() as c:
        amb = _ambito(c, entidad, nivel, periodo)
        if amb is None:
            return {"entidad": entidad, "encontrada": False}
        if amb.get("sin_datos"):
            return {"entidad": entidad, "encontrada": True, "sin_datos": True}
        ids, vid = amb["ids"], amb["vid"]
        y, mo, dim, ini, fin = amb["y"], amb["mo"], amb["dim"], amb["ini"], amb["fin"]
        base = {}
        if ids: base["ids"] = ids
        if vid is not None: base["vid"] = vid
        def _b(sql):
            t = sa.text(sql)
            return t.bindparams(sa.bindparam("ids", expanding=True)) if "ids" in base else t
        def where(a):
            p = (a + ".") if a else ""
            cs = []
            if ids: cs.append(f"{p}fuente_id IN :ids")
            if vid is not None: cs.append(f"{p}vice_id = :vid")
            return "(" + " OR ".join(cs) + ")" if cs else "TRUE"

        # KPIs REAL vs PPTO (mensual)
        pm = dict(base); pm["fin"] = fin
        kpi = {}
        for r in c.execute(_b(f"""
            SELECT tp.nombre, es.nombre, SUM(m.volumen)
            FROM core.fact_produccion_mes_ecp m
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = m.tipo_producto_id
            JOIN core.dim_escenario es ON es.escenario_id = m.escenario_id
            WHERE m.fecha = :fin AND es.nombre IN ('REAL','PPTO') AND {where('m')}
            GROUP BY 1,2"""), pm):
            kpi.setdefault(r[0], {})[r[1]] = float(r[2] or 0)
        _et = {"ok": "Alineado", "warn": "Rezagado", "alert": "Foco", "": "—"}
        titular = []
        for p in ["CRUDO", "GAS", "BLANCOS"]:
            real = kpi.get(p, {}).get("REAL", 0.0); ppto = kpi.get(p, {}).get("PPTO", 0.0)
            pct = round(real / ppto * 100.0, 1) if ppto else None
            est = _estado(pct)
            titular.append({"producto": p, "real": real, "ppto": ppto, "valor_pct": pct,
                            "estado": est, "texto": _et.get(est, "—")})

        # serie crudo diaria -> valle (INS-A: solo el onset da eventos limpios)
        pd_ = dict(base); pd_["ini"] = ini; pd_["fin"] = fin
        srows = c.execute(_b(f"""
            SELECT d.fecha, SUM(d.volumen)
            FROM core.fact_produccion_dia_ecp d
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = d.tipo_producto_id
            WHERE tp.nombre='CRUDO' AND d.fecha BETWEEN :ini AND :fin AND {where('d')}
            GROUP BY 1 ORDER BY 1"""), pd_).all()
        serie = [(r[0].isoformat(), float(r[1] or 0)) for r in srows]
        valle = _detectar_valle(serie)
        eventos, eventos_extra = [], {"campos": 0, "pozos_aprox": 0}
        if valle:
            from datetime import date as _date
            dd = [int(x) for x in valle["desde"].split("-")]
            # Eventos ACOTADOS a la entidad (names vacío ⇒ brief global de ECP ⇒ alcance original).
            eventos, eventos_extra = _eventos_valle(c, _date(*dd), names=_nombres_entidad(c, ids, vid))
        if valle and serie:
            _pro = sum(v for _, v in serie) / len(serie)
            from datetime import date as _d
            _va = [int(x) for x in valle["desde"].split("-")]; _vh = [int(x) for x in valle["hasta"].split("-")]
            valle["magnitud_pct"] = round((valle["min_valor"] / _pro - 1) * 100, 1) if _pro else None
            valle["dias"] = (_d(*_vh) - _d(*_va)).days + 1

        # pace de cierre (CRUDO) -- MISMO cálculo que /desempeno_insight
        pace = None
        if serie:
            mtd = sum(v for _, v in serie); ndias = len(serie); rest = dim - ndias
            ppto_crudo = kpi.get("CRUDO", {}).get("PPTO", 0.0)
            if rest > 0 and ppto_crudo and ndias:
                prom = mtd / ndias
                req = (ppto_crudo - mtd) / rest
                pace = {"mtd": round(mtd), "dias": ndias, "restantes": rest,
                        "promedio_dia": round(prom), "requerido_dia": round(req),
                        "delta_pct": (round((req / prom - 1) * 100, 1) if prom else None)}

        # Ritmo diario POR PRODUCTO para las tarjetas KPI (bopd). Solo se expone si la curva diaria
        # RECONCILIA con el mensual (mtd <= real*1.05). Si el acumulado diario supera al mes es
        # físicamente imposible -> ese producto NO muestra ritmo diario. Verificado (mayo 2026,
        # global ECP): CRUDO 54.6% y GAS 55.2% (~17/31) reconcilian; BLANCOS 183.7% NO (diario ~2x
        # el mes) -> Blancos queda solo con la proyección mensual.
        pace_por_prod = {}
        for _nom, _nd, _mtd in c.execute(_b(f"""
                SELECT tp.nombre, COUNT(DISTINCT d.fecha), SUM(d.volumen)
                FROM core.fact_produccion_dia_ecp d
                JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = d.tipo_producto_id
                WHERE d.fecha BETWEEN :ini AND :fin AND {where('d')}
                GROUP BY 1"""), pd_).all():
            _nd = int(_nd or 0); _mtd = float(_mtd or 0)
            _real = kpi.get(_nom, {}).get("REAL", 0.0); _ppto = kpi.get(_nom, {}).get("PPTO", 0.0)
            _rest = dim - _nd
            if _nd and _rest > 0 and _ppto and _real and _mtd <= _real * 1.05:
                _prom = _mtd / _nd; _req = (_ppto - _mtd) / _rest
                pace_por_prod[_nom] = {"promedio_dia": round(_prom), "requerido_dia": round(_req),
                                       "delta_pct": (round((_req / _prom - 1) * 100, 1) if _prom else None)}

        # Histórico del AÑO en curso por producto: promedio de los meses ANTERIORES con REAL. Base
        # para "producción del mes vs promedio del año" (arriba/abajo) en tarjetas sin ritmo diario
        # fiable (p.ej. BLANCOS, cuyo diario no reconcilia). NO se usa para Crudo/Gas.
        hist_anio = {}
        _h = {}                                     # {prod: {mes:int -> vol:float}}
        for _nom, _mm, _v in c.execute(_b(f"""
                SELECT tp.nombre, EXTRACT(month FROM m.fecha)::int, SUM(m.volumen)
                FROM core.fact_produccion_mes_ecp m
                JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = m.tipo_producto_id
                JOIN core.dim_escenario es ON es.escenario_id = m.escenario_id
                WHERE es.nombre = 'REAL' AND EXTRACT(year FROM m.fecha) = :hy
                  AND EXTRACT(month FROM m.fecha) < :hmo AND {where('m')}
                GROUP BY 1, 2"""), {**base, "hy": y, "hmo": mo}).all():
            _v = float(_v or 0)
            if _v > 0:
                _h.setdefault(_nom, {})[int(_mm)] = _v
        for _nom, _vals in _h.items():
            if _vals:
                hist_anio[_nom] = round(sum(_vals.values()) / len(_vals))

        # Gap RECONCILIADO por producto rezagado (pct<100): descompone por campo y compara Σcampos
        # contra el gap del KPI (H2). concentracion_pct usa la MISMA base (Σcampos) que la descomposición.
        def _gap_campo(producto, gap_kpi):
            pg = dict(base); pg["fin"] = fin; pg["prod"] = producto
            grows = c.execute(_b(f"""
                SELECT COALESCE(NULLIF(TRIM(f.campo),''), f.nombre) AS campo,
                       SUM(CASE WHEN es.nombre='REAL' THEN m.volumen ELSE 0 END) AS vreal,
                       SUM(CASE WHEN es.nombre='PPTO' THEN m.volumen ELSE 0 END) AS vppto
                FROM core.fact_produccion_mes_ecp m
                JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = m.tipo_producto_id
                JOIN core.dim_escenario es ON es.escenario_id = m.escenario_id
                JOIN core.dim_fuente f ON f.fuente_id = m.fuente_id
                WHERE m.fecha = :fin AND es.nombre IN ('REAL','PPTO') AND tp.nombre = :prod AND {where('m')}
                GROUP BY 1"""), pg).all()
            # (campo, dif, real, ppto) — conservamos real y ppto por campo para el gráfico Meta vs Real
            difs = [((r[0] or "").strip(), float(r[1] or 0) - float(r[2] or 0),
                     float(r[1] or 0), float(r[2] or 0))
                    for r in grows if (r[1] or r[2])]
            gap_total_campos = sum(d[1] for d in difs)
            # [2026-08-31] El corte pasa de 3 a 5 (TOP_DETRACTORES) — decisión del usuario: el panel
            # "Producción vs Producción esperada" necesitaba más profundidad de lectura.
            # La narrativa del chat se adapta sola: _dl_bloque (consulta_v2/analizar/plantilla.py)
            # redacta "Los {n} mayores" con n = len(detractores), y la concentración se recalcula
            # abajo sobre esta misma lista, así que el texto y la cifra siguen cuadrando.
            detr = sorted([d for d in difs if d[1] < 0], key=lambda x: x[1])[:TOP_DETRACTORES]
            comp = sorted([d for d in difs if d[1] > 0], key=lambda x: -x[1])[:2]
            top_detr = sum(d[1] for d in detr)
            # Concentración = |top_detr| / |Σ TODOS los detractores (bruto)| → "del total del déficit,
            # X% está en N campos". Sobre el gap NETO daría >100% cuando hay compensadores grandes.
            gap_detr_total = sum(d[1] for d in difs if d[1] < 0)
            gap_comp_total = sum(d[1] for d in difs if d[1] > 0)
            concentracion_pct = round(abs(top_detr) / abs(gap_detr_total) * 100, 1) if gap_detr_total else None
            desfase_pct = round(abs(gap_total_campos - gap_kpi) / abs(gap_kpi) * 100, 1) if gap_kpi else None
            # Extremos por producción REAL: 2 mayores + 2 menores ENTRE los campos que sí producen
            # (real>0) — para la tarjeta de un producto que NO va mal. d = (campo, dif, real, ppto).
            _pos = sorted([d for d in difs if d[2] > 0], key=lambda x: -x[2])
            _ext = _pos if len(_pos) <= 4 else _pos[:2] + _pos[-2:]
            return {
                "producto": producto, "gap_kpi": round(gap_kpi),
                "gap_total_campos": round(gap_total_campos),
                "reconciliado": desfase_pct is not None and desfase_pct <= 2.0,
                "desfase_pct": desfase_pct, "concentracion_pct": concentracion_pct,
                # [2026-08-13] Denominador para Analizar/causal: "Repartido entre N campos bajo
                # meta" — TODOS los detractores (gap<0), no solo el top-3 truncado en `detr`.
                # Aditivo: no toca ningún consumidor existente de _gap_campo.
                "n_detractores": len([x for x in difs if x[1] < 0]),
                # BRUTOS (2026-07-23): el titular del foco es el gap NETO, pero los detractores que
                # lista el detalle son BRUTOS. Sin estos dos totales el panel mostraba "-10.813.358"
                # con un detalle que sumaba 19.814.696 y nada explicaba la diferencia. Con ellos,
                # faltante_bruto + excedente_bruto = gap_total_campos (aritmética auditable).
                "faltante_bruto": round(gap_detr_total),
                "excedente_bruto": round(gap_comp_total),
                # gap se conserva (lo usan ctx/fallback); real/meta se agregan para los gráficos.
                # eventos = fuente/soporte real (Épica 1 criterio 2) vía _comentarios_campo_mes.
                "detractores": [{"campo": d[0], "gap": round(d[1]), "real": round(d[2]), "meta": round(d[3]),
                                  "eventos": _comentarios_campo_mes(c, d[0], ini, fin)}
                                for d in detr],
                "compensadores": [{"campo": d[0], "gap": round(d[1]), "real": round(d[2]), "meta": round(d[3])}
                                  for d in comp],
                "extremos": [{"campo": d[0], "real": round(d[2]), "meta": round(d[3])} for d in _ext],
            }

        # F2 en ECP (2026-07-16, ya probado en _ejecutivo_filiales): el desglose por campo se calcula
        # para TODOS los productos con meta (gap_full → respuesta/gráficos) y la narrativa usa SOLO
        # los rezagados (gap_lag → brief/flags/ctx). Antes solo se consultaba con pct<100: con la
        # entidad en meta (CASTILLA 102.7%) el panel decía "Sin desglose por campo para graficar"
        # aunque el dato por campo SIEMPRE existe en fact_produccion_mes_ecp — nadie lo pedía.
        gap_full, gap_lag, extremos_prod = {}, {}, {}
        for t in titular:
            if t["valor_pct"] is None:
                # Sin PPTO: no entra a gap_full/gap_lag (no cambia gráficos/narrativa), pero igual
                # calculamos sus extremos para su tarjeta (los 3 productos salen siempre).
                g0 = _gap_campo(t["producto"], (t["real"] or 0))
                extremos_prod[t["producto"]] = g0.get("extremos", [])
                continue
            g = _gap_campo(t["producto"], t["real"] - t["ppto"])
            gap_full[t["producto"]] = g
            extremos_prod[t["producto"]] = g.get("extremos", [])
            if t["valor_pct"] < 100:
                gap_lag[t["producto"]] = g
        gap_por_producto = gap_lag        # narrativa (sintesis/ctx/fallback/flags): solo rezagados

        flags = _flags_ejecutivo(titular, gap_por_producto, valle, pace, serie[-1][0] if serie else None)
        periodo = f"{MESES_ES[mo]} {y}"
        corte = f"{len(serie)}/{dim}"

        # ---- Pulido LLM (opcional): prompt multi-sección -> JSON de 4 arrays ----
        def _situacion(pct):
            if pct is None: return "sin dato"
            return "por encima de la meta" if pct >= 100 else "por debajo de la meta"

        # SÍNTESIS pre-derivada por Python (la INTERPRETACIÓN, no solo los números): distingue
        # rezago transitorio (valle acotado ya recuperado) de estructural, y foco (concentrado en
        # pocos campos = problema localizado) de distribuido (sistémico). Gemma solo la narra.
        valle_activo = any(f["tipo"] == "valle_activo" and f.get("activo") for f in flags)
        sintesis = []
        for t in titular:
            p, pct = t["producto"], t["valor_pct"]
            if pct is None or pct >= 100:
                continue
            g = gap_por_producto.get(p, {})
            conc = g.get("concentracion_pct")
            ncampos = len(g.get("detractores", []))
            if p == "CRUDO" and valle:
                caracter = ("transitorio ya superado (fue un valle acotado que se recuperó)"
                            if not valle_activo else "transitorio pero aún en curso (el valle sigue activo)")
            elif conc is not None and conc >= 70:
                caracter = "estructural y focalizado (el faltante persiste, no fue un evento puntual)"
            else:
                caracter = "estructural y distribuido"
            foco = (f"focalizado: ~{conc}% del faltante está en {ncampos} campos → acción localizada"
                    if (conc is not None and conc >= 70)
                    else "distribuido en varios campos → problema más sistémico")
            sintesis.append({"producto": p, "pct_presupuesto": pct,
                             "caracter_del_rezago": caracter, "foco": foco})

        # SITUACIÓN GENERAL declarada por Python (2026-07-16). Cuando NINGÚN producto va por debajo
        # de su meta, `sintesis` y `detalle_por_producto` quedan VACÍOS: no hay rezago que analizar.
        # Sin decírselo, el prompt igual le exigía a Gemma "la historia del mes" y "contrasta lo
        # transitorio con lo estructural" → se inventaba el rezago. Caso verificado: CASTILLA campo,
        # CRUDO al 102.7% y pace sobrado, y Gemma narró "déficit significativo respecto al promedio
        # histórico" antes de descarrilar. La alucinación era lo grave: con el JSON bien formado, ese
        # brief falso se habría pintado como válido. Python declara la verdad; el prompt se ramifica.
        situacion_general = _situacion_general(titular, sintesis)

        ctx = {
            "periodo": periodo, "corte": corte,
            "situacion_general": situacion_general,   # la verdad del mes: ¿hay rezago o no?
            "productos": [{"producto": t["producto"], "pct_presupuesto": t["valor_pct"],
                           "situacion": _situacion(t["valor_pct"])} for t in titular],
            "sintesis": sintesis,   # la tesis del mes (transitorio vs estructural, foco vs sistémico)
            "valle_crudo": valle, "eventos_del_valle": eventos,
            "detalle_por_producto": {
                p: {
                    "campos_por_debajo": [{"campo": d["campo"], "faltante": abs(d["gap"])}
                                          for d in g["detractores"]],
                    "campos_por_encima": [{"campo": d["campo"], "excedente": d["gap"]}
                                          for d in g["compensadores"]],
                    "concentracion_del_faltante_pct": g["concentracion_pct"],
                } for p, g in gap_por_producto.items()
            },
            "pace_crudo": pace, "flags": flags,
        }
        prompt = (
            "Eres analista de producción petrolera y escribes para directivos NO técnicos. Con estos "
            "datos EXACTOS (no inventes ni recalcules cifras) devuelve SOLO un JSON con 4 "
            'arrays de frases: {"insights":[],"oportunidades":[],"puntos_atencion":[],"decisiones":[]}.\n'
            "FORMATO ESTRICTO: responde ÚNICAMENTE el objeto JSON, sin ``` ni texto antes o después; "
            "usa comillas dobles; NO pongas comas finales; NO uses comillas dobles dentro de las frases "
            "(si necesitas citar un campo, escríbelo sin comillas).\n"
            + _reglas_tesis(situacion_general)
            + "REGLAS DE REDACCIÓN (obligatorias):\n"
            "1. Español claro, sin jerga. PROHIBIDO la palabra 'gap'. Un número positivo es un "
            "'excedente' o 'produjo por encima de su meta'; un negativo es un 'faltante' o 'rezago'.\n"
            "5. decisiones: conecta causa->acción y PRIORIZA (primero lo estructural/crítico, luego lo "
            "transitorio); acciones concretas, no genéricas ('implementar planes' a secas no sirve).\n"
            "6. Longitud: insights 3-4 frases; oportunidades, puntos_atencion y decisiones 1-3 c/u. "
            "Frases BREVES y directas (~25 palabras máx); nada de párrafos largos.\n"
            "7. Un producto SIN meta definida no es un faltante ni un problema: no hay con qué "
            "compararlo. Menciónalo como tal o no lo menciones; NUNCA lo presentes como un rezago.\n"
            "Datos: " + _json.dumps(ctx, ensure_ascii=False))
        # El composer determinista es el default entregable (H4). El pulido LLM solo se intenta si
        # EJECUTIVO_USAR_LLM=true (prod/gemma4): en dev el qwen local produce prosa poco fiable
        # (confunde cifras) y el gate solo valida estructura, no grounding.
        secciones, generado = None, "fallback"
        llm_diag = {"status": "off"}
        if get_settings().ejecutivo_usar_llm:
            llm_diag = {"status": "?"}
            prosa = _llm_insight(prompt, timeout=180, diag=llm_diag)
            claves = ("insights", "oportunidades", "puntos_atencion", "decisiones")
            if isinstance(prosa, dict) and all(isinstance(prosa.get(k), list) and prosa.get(k) for k in claves):
                secciones = {k: [str(x)[:280] for x in prosa[k]][:5] for k in claves}
                generado = "llm"
            elif llm_diag.get("status") == "ok":
                # Gemma respondió JSON válido pero sin las 4 secciones no vacías
                faltan = [k for k in claves if not (isinstance(prosa, dict) and prosa.get(k))]
                llm_diag["status"] = "faltan_claves:" + ",".join(faltan)
        if secciones is None:
            # En pruebas (EJECUTIVO_FALLBACK=false) NO tapar el fallo de Gemma con el texto base:
            # devolver generado_por="error" + el diag (status + raw) para validar el comportamiento.
            _st = get_settings()
            if _st.ejecutivo_usar_llm and not _st.ejecutivo_fallback:
                generado = "error"
            else:
                secciones = _ejec_fallback(periodo, titular, gap_por_producto, valle, eventos,
                                            eventos_extra, pace, flags)

        _tarj = _tarjetas_kpi(titular, pace_por_prod, hist_anio)   # se reusa en el return y en _focos
        return {
            "entidad": entidad, "encontrada": True,
            "meta": {"scope": entidad or "Global (toda la producción ECP)",
                     "periodo": periodo, "corte": corte, "generado_por": generado,
                     "llm_diag": llm_diag},
            "titular": titular, "tarjetas": _tarj,
            "gap_por_producto": gap_full,   # gráficos: los 3 productos (F2)
            "valle": valle, "eventos": eventos, "eventos_extra": eventos_extra,
            "pace_crudo": pace, "flags": flags, "secciones": secciones,
            "focos": _focos(titular, gap_lag, valle, eventos, _tarj, extremos_prod),
            "sin_foco": _sin_foco(titular, gap_full, valle),
            # [2026-09-01] Comparativo vs mes anterior para el bloque de iniciativa del chat
            # (consulta_v2/analizar). Sale del desglose por mes que esta misma función ya
            # consultaba para hist_anio y descartaba. None en enero (la query filtra por año:
            # no se cruza a diciembre del año anterior — nunca inventar). `actual` es la fila
            # mensual REAL del mes en curso (proyección de cierre), la misma base que hist_prom.
            "comparativo_mes": ({
                "mes_anterior": f"{MESES_ES[mo - 1].lower()} {y}",
                "por_producto": {
                    t["producto"]: {"actual": t["real"], "anterior": _h.get(t["producto"], {}).get(mo - 1)}
                    for t in titular
                },
            } if mo > 1 else None),
        }


# ============================================================================
# SEGMENTO FILIALES — Desempeño/Ejecutivo sobre core.fact_produccion_diaria.
# Meta = PROGRAMA (tipo_id=2); REAL = tipo_id=1. Comparación MISMA-VENTANA (solo días con REAL, CTE rd).
# Descomposición por EMPRESA (Hocol/America/Permian). Sin PPTO, sin eventos (los comentarios son ECP).
# F2: gap_por_producto (respuesta/gráficos) = LOS 3 productos; el brief/flags usan gap_lag (pct<100).
# Reusa helpers compartidos: _estado, _detectar_valle, _flags_ejecutivo, _ejec_fallback, MESES_ES.
# v1: vista fija de las 3 filiales (NO entity-aware), sin LLM (composer determinista).
# ============================================================================
_FIL_SCOPE = "Filiales (Hocol · America · Permian)"

def _fil_intermedios(c):
    """Intermedios comunes de filiales. Devuelve None si no hay REAL diario.
    Forma idéntica a la que usan los composers ECP para poder reutilizarlos."""
    import calendar
    maxd = c.execute(sa.text(
        "SELECT MAX(fecha) FROM core.fact_produccion_diaria WHERE tipo_id=1")).scalar()
    if maxd is None:
        return None
    y, mo = maxd.year, maxd.month
    dim = calendar.monthrange(y, mo)[1]
    ini = f"{y:04d}-{mo:02d}-01"; fin = f"{y:04d}-{mo:02d}-{dim:02d}"
    P = {"ini": ini, "fin": fin}
    RD = ("WITH rd AS (SELECT DISTINCT fecha FROM core.fact_produccion_diaria "
          "WHERE tipo_id=1 AND fecha BETWEEN :ini AND :fin) ")

    ndias = c.execute(sa.text(
        "SELECT COUNT(DISTINCT fecha) FROM core.fact_produccion_diaria "
        "WHERE tipo_id=1 AND fecha BETWEEN :ini AND :fin"), P).scalar() or 0

    # KPI REAL vs PROGRAMA por producto (MISMA-VENTANA)
    kpi = {}
    for r in c.execute(sa.text(RD + """
        SELECT tp.nombre,
          SUM(CASE WHEN fp.tipo_id=1 THEN fp.valor_produccion END) real_mtd,
          SUM(CASE WHEN fp.tipo_id=2 THEN fp.valor_produccion END) prog_mtd
        FROM core.fact_produccion_diaria fp
        JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = fp.producto_id
        WHERE fp.fecha IN (SELECT fecha FROM rd)
        GROUP BY 1"""), P):
        kpi[r[0]] = {"REAL": float(r[1] or 0), "PROG": float(r[2] or 0)}

    _et = {"ok": "Alineado", "warn": "Rezagado", "alert": "Foco", "": "—"}
    titular = []
    for p in ["CRUDO", "GAS", "BLANCOS"]:
        real = kpi.get(p, {}).get("REAL", 0.0); prog = kpi.get(p, {}).get("PROG", 0.0)
        pct = round(real / prog * 100.0, 1) if prog else None
        est = _estado(pct)
        # 'ppto' guarda la META (=PROGRAMA misma-ventana) para reutilizar el frontend sin cambiar claves
        titular.append({"producto": p, "real": real, "ppto": prog, "valor_pct": pct,
                        "estado": est, "texto": _et.get(est, "—")})

    # Curva diaria REAL por producto
    curva = {}
    for f, prod, vol in c.execute(sa.text("""
            SELECT fp.fecha, tp.nombre prod, SUM(fp.valor_produccion) vol
            FROM core.fact_produccion_diaria fp
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = fp.producto_id
            WHERE fp.tipo_id=1 AND fp.fecha BETWEEN :ini AND :fin
            GROUP BY 1, 2 ORDER BY 1"""), P).all():
        curva.setdefault(f.isoformat(), {})[prod] = float(vol or 0)
    curva_fechas = sorted(curva.keys())
    productos = ["CRUDO", "GAS", "BLANCOS"]
    series = {p: [curva.get(f, {}).get(p, 0.0) for f in curva_fechas] for p in productos}

    # Serie crudo diaria -> valle
    serie = [(f, curva.get(f, {}).get("CRUDO", 0.0)) for f in curva_fechas]
    valle = _detectar_valle(serie)
    anotaciones = None
    if valle:
        anotaciones = {
            "banda": {"desde": valle["desde"], "hasta": valle["hasta"], "label": "valle"},
            "punto": {"fecha": valle["min_fecha"], "valor": valle["min_valor"],
                      "label": f"mín · {valle['min_valor']/1e6:.2f}M"},
        }

    # Descomposición del gap por EMPRESA (misma-ventana). F2: se calcula para TODOS los productos.
    def _gap_empresa(producto, gap_kpi):
        pe = dict(P); pe["prod"] = producto
        grows = c.execute(sa.text(RD + """
            SELECT e.nombre AS campo,
                   SUM(CASE WHEN fp.tipo_id=1 THEN fp.valor_produccion ELSE 0 END) AS vreal,
                   SUM(CASE WHEN fp.tipo_id=2 THEN fp.valor_produccion ELSE 0 END) AS vprog
            FROM core.fact_produccion_diaria fp
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = fp.producto_id
            JOIN core.dim_empresa e ON e.empresa_id = fp.empresa_id
            WHERE tp.nombre = :prod AND fp.fecha IN (SELECT fecha FROM rd)
            GROUP BY 1"""), pe).all()
        difs = [((r[0] or "").strip(), float(r[1] or 0) - float(r[2] or 0),
                 float(r[1] or 0), float(r[2] or 0)) for r in grows if (r[1] or r[2])]
        gap_total = sum(d[1] for d in difs)
        # [2026-08-31] Mismo corte a 5 que el bloque de _gap_campo: los dos alimentan el mismo panel.
        detr = sorted([d for d in difs if d[1] < 0], key=lambda x: x[1])[:TOP_DETRACTORES]
        comp = sorted([d for d in difs if d[1] > 0], key=lambda x: -x[1])[:2]
        top_detr = sum(d[1] for d in detr)
        gap_detr_total = sum(d[1] for d in difs if d[1] < 0)
        concentracion_pct = round(abs(top_detr) / abs(gap_detr_total) * 100, 1) if gap_detr_total else None
        desfase_pct = round(abs(gap_total - gap_kpi) / abs(gap_kpi) * 100, 1) if gap_kpi else None
        return {
            "producto": producto, "gap_kpi": round(gap_kpi), "gap_total_campos": round(gap_total),
            "reconciliado": desfase_pct is not None and desfase_pct <= 2.0,
            "desfase_pct": desfase_pct, "concentracion_pct": concentracion_pct,
            "detractores": [{"campo": d[0], "gap": round(d[1]), "real": round(d[2]), "meta": round(d[3])} for d in detr],
            "compensadores": [{"campo": d[0], "gap": round(d[1]), "real": round(d[2]), "meta": round(d[3])} for d in comp],
        }

    gap_full = {}
    for t in titular:
        if t["valor_pct"] is not None:
            gap_full[t["producto"]] = _gap_empresa(t["producto"], t["real"] - t["ppto"])
    # gap_lag = solo productos por debajo de la meta (para brief + flags honestos)
    gap_lag = {p: g for p, g in gap_full.items()
               if next(t["valor_pct"] for t in titular if t["producto"] == p) < 100}

    # Pace de crudo: MTD vs PROGRAMA del MES COMPLETO (target de cierre)
    pace = None
    if serie:
        mtd = sum(v for _, v in serie); rest = dim - ndias
        prog_full = c.execute(sa.text("""
            SELECT SUM(fp.valor_produccion) FROM core.fact_produccion_diaria fp
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = fp.producto_id
            WHERE tp.nombre='CRUDO' AND fp.tipo_id=2 AND fp.fecha BETWEEN :ini AND :fin"""), P).scalar()
        prog_full = float(prog_full or 0)
        if rest > 0 and prog_full and ndias:
            prom = mtd / ndias
            req = (prog_full - mtd) / rest
            pace = {"mtd": round(mtd), "dias": ndias, "restantes": rest,
                    "promedio_dia": round(prom), "requerido_dia": round(req),
                    "delta_pct": (round((req / prom - 1) * 100, 1) if prom else None)}

    # Promedio mensual 2026 del REAL por producto (meses COMPLETOS previos al mes en curso). Es la
    # base de comparación de las tarjetas de filiales: no hay PPTO -> se compara contra el promedio
    # del año (decisión usuario "Opción B", 2026-07-21). Vacío si no hay meses previos con REAL.
    avg2026 = {}
    for _p, _avg in c.execute(sa.text("""
        WITH mens AS (
          SELECT tp.nombre AS prod, date_trunc('month', fp.fecha) AS m,
                 SUM(fp.valor_produccion) AS tot
          FROM core.fact_produccion_diaria fp
          JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = fp.producto_id
          WHERE fp.tipo_id = 1 AND fp.fecha >= :y0 AND fp.fecha < :mes_ini
          GROUP BY 1, 2)
        SELECT prod, AVG(tot) FROM mens GROUP BY 1"""),
        {"y0": f"{y:04d}-01-01", "mes_ini": ini}).all():
        avg2026[(_p or "").strip()] = round(float(_avg or 0))

    flags = _flags_ejecutivo(titular, gap_lag, valle, pace, serie[-1][0] if serie else None)
    return {
        "y": y, "mo": mo, "dim": dim, "ndias": ndias, "avg2026": avg2026,
        "periodo": f"{MESES_ES[mo]} {y}", "corte": f"{ndias}/{dim}",
        "titular": titular, "kpi": kpi, "curva_fechas": curva_fechas, "series": series,
        "curva_crudo": {"fechas": [f for f, _ in serie], "valores": [v for _, v in serie]},
        "valle": valle, "anotaciones": anotaciones,
        "gap_por_producto": gap_full, "gap_lag": gap_lag, "pace": pace, "flags": flags,
    }


def _desempeno_filiales():
    eng = get_engine()
    with eng.connect() as c:
        I = _fil_intermedios(c)
    if I is None:
        return {"entidad": None, "encontrada": True, "sin_datos": True}
    sin_cierre = not any(I["kpi"].get(p) for p in ["CRUDO", "GAS", "BLANCOS"])
    por_producto = [{"producto": t["producto"], "real": t["real"], "ppto": t["ppto"],
                     "cumplimiento": t["valor_pct"]} for t in I["titular"]]
    return {
        "entidad": None, "encontrada": True, "aplica_diario": True, "sin_cierre": sin_cierre,
        "mes": {"anio": I["y"], "mes": I["mo"], "nombre": MESES_ES[I["mo"]],
                "dias_con_data": I["ndias"], "dias_del_mes": I["dim"], "completo": I["ndias"] >= I["dim"]},
        "por_producto": por_producto,
        "curva": {"fechas": I["curva_fechas"], "series": I["series"]},
    }


def _valle_diag_fallback(desde, hasta, drivers, estables):
    """Texto determinista del diagnóstico del valle a nivel filial (sin LLM). Solo cifras + recomendación
    de contactar a la filial — NUNCA una causa técnica inventada (no la tenemos para filiales)."""
    def _fmt(n):
        return f"{n:,.0f}".replace(",", ".")
    if not drivers:
        return {"diagnostico": f"El valle de crudo ({desde} a {hasta}) no se concentra en una filial en "
                               "particular; la caída se reparte de forma pareja entre las filiales.",
                "recomendacion": "Sin una filial claramente responsable, basta con monitorear la evolución."}
    partes = ", ".join(
        f"{d['filial']} ({d['caida_pct']}%: {_fmt(d['prod_valle'])} vs {_fmt(d['prod_ref'])} bls/día habituales)"
        for d in drivers)
    diagnostico = f"El valle de crudo ({desde} a {hasta}) se explica principalmente por {partes}."
    if estables:
        diagnostico += f" El resto de filiales ({', '.join(estables)}) se mantuvo estable."
    recomendacion = (f"Se recomienda contactar a {' y '.join(d['filial'] for d in drivers)} para conocer la "
                     "causa raíz operativa de la caída: el reporte diario no documenta el motivo para las filiales.")
    return {"diagnostico": diagnostico, "recomendacion": recomendacion}


def _valle_diagnostico_filiales(c, I):
    """Descompone el valle de crudo por filial (quién cayó vs su nivel habitual del mes) y redacta un
    diagnóstico. Con EJECUTIVO_USAR_LLM=true lo pule Gemma; si no, texto determinista. El LLM tiene PROHIBIDO
    inventar causas técnicas — solo describe la caída por cifras y recomienda contactar a la filial."""
    valle = I["valle"]
    if not valle:
        return None
    desde, hasta = valle["desde"], valle["hasta"]
    y, mo, dim = I["y"], I["mo"], I["dim"]
    ini = f"{y:04d}-{mo:02d}-01"; fin = f"{y:04d}-{mo:02d}-{dim:02d}"
    # prod CRUDO por filial: promedio en los días del valle vs promedio en el RESTO del mes (referencia).
    rows = c.execute(sa.text("""
        WITH d AS (
          SELECT e.nombre filial, fp.fecha, SUM(fp.valor_produccion) v
          FROM core.fact_produccion_diaria fp
          JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = fp.producto_id
          JOIN core.dim_empresa e ON e.empresa_id = fp.empresa_id
          WHERE tp.nombre='CRUDO' AND fp.tipo_id=1 AND fp.fecha BETWEEN :ini AND :fin
          GROUP BY 1, 2)
        SELECT filial,
          AVG(v) FILTER (WHERE fecha BETWEEN :desde AND :hasta)     AS avg_valle,
          AVG(v) FILTER (WHERE fecha NOT BETWEEN :desde AND :hasta) AS avg_ref
        FROM d GROUP BY 1"""),
        {"ini": ini, "fin": fin, "desde": desde, "hasta": hasta}).all()

    drivers, estables = [], []
    for filial, av, ar in rows:
        av = float(av or 0); ar = float(ar or 0)
        pct = round((av - ar) / ar * 100, 1) if ar else None
        item = {"filial": filial, "prod_valle": round(av), "prod_ref": round(ar),
                "caida": round(av - ar), "caida_pct": pct}
        (drivers if (pct is not None and pct <= -3) else estables).append(
            item if (pct is not None and pct <= -3) else filial)
    drivers.sort(key=lambda x: x["caida"])   # más negativo (mayor caída) primero

    gen, diag, texto = "fallback", {"status": "off"}, None
    if get_settings().ejecutivo_usar_llm and drivers:
        ctx = {"valle": {"desde": desde, "hasta": hasta, "producto": "CRUDO"},
               "filiales_que_cayeron": drivers, "filiales_estables": estables}
        prompt = (
            "Eres analista de producción de las FILIALES (Hocol, America, Permian). Hubo un valle (caída) "
            "en la producción diaria de crudo entre " + desde + " y " + hasta + ". Con estos datos EXACTOS, "
            "explica QUÉ filial(es) causaron la caída y recomienda contactarlas. Devuelve SOLO un JSON de una "
            'línea: {"diagnostico":"...","recomendacion":"..."}.\n'
            "REGLAS: (1) Español claro; comillas dobles; sin comas finales; sin ``` ni texto fuera del JSON.\n"
            "(2) PROHIBIDO inventar causas técnicas (fallas eléctricas, paradas de estación, etc.): NO tienes "
            "esa información, SOLO las cifras de producción. Describe la caída únicamente por los números "
            "(qué filial produjo menos y cuánto, con caida_pct y prod_valle vs prod_ref).\n"
            "(3) recomendacion: di EXPLÍCITAMENTE que se contacte a la(s) filial(es) que cayeron para conocer "
            "la causa raíz operativa, porque el reporte diario no la documenta.\n"
            "(4) Frases breves y directas (~25 palabras). "
            "Datos: " + _json.dumps(ctx, ensure_ascii=False))
        diag = {"status": "?"}
        prosa = _llm_insight(prompt, timeout=120, diag=diag)
        if isinstance(prosa, dict) and prosa.get("diagnostico") and prosa.get("recomendacion"):
            texto = {"diagnostico": str(prosa["diagnostico"])[:600],
                     "recomendacion": str(prosa["recomendacion"])[:500]}
            gen = "llm"
    if texto is None:
        texto = _valle_diag_fallback(desde, hasta, drivers, estables)

    return {"valle": {"desde": desde, "hasta": hasta}, "drivers": drivers, "estables": estables,
            "generado_por": gen, "llm_diag": diag,
            "diagnostico": texto["diagnostico"], "recomendacion": texto["recomendacion"]}


def _desempeno_insight_filiales():
    eng = get_engine()
    with eng.connect() as c:
        I = _fil_intermedios(c)
        if I is None:
            return {"entidad": None, "encontrada": True, "sin_datos": True}
        valle_diag = _valle_diagnostico_filiales(c, I) if I["valle"] else None
    peor = min([t for t in I["titular"] if t["valor_pct"] is not None],
               key=lambda t: t["valor_pct"], default=None)
    gpeor = I["gap_por_producto"].get((peor or {}).get("producto"), {}) or {}
    return {
        "entidad": None, "encontrada": True,
        "meta": {"scope": _FIL_SCOPE, "periodo": I["periodo"], "corte": I["corte"], "generado_por": "fallback"},
        "titular": I["titular"], "curva_crudo": I["curva_crudo"], "anotaciones": I["anotaciones"],
        "eventos": [], "eventos_extra": {"campos": 0, "pozos_aprox": 0, "fecha": ""},
        "valle_diagnostico": valle_diag,   # diagnóstico del valle a nivel filial (IA o fallback)
        "gap": {"producto": (peor or {}).get("producto"),
                "detractores": gpeor.get("detractores", []), "compensadores": gpeor.get("compensadores", [])},
        "pace_crudo": I["pace"], "lectura_ejecutiva": "", "accion_sugerida": [],
    }


def _ejecutivo_filiales():
    eng = get_engine()
    with eng.connect() as c:
        I = _fil_intermedios(c)
    if I is None:
        return {"entidad": None, "encontrada": True, "sin_datos": True}

    titular = I["titular"]; gap_full = I["gap_por_producto"]; gap_lag = I["gap_lag"]
    valle = I["valle"]; pace = I["pace"]; flags = I["flags"]
    periodo = I["periodo"]; corte = I["corte"]
    dim = I["dim"]; ndias = I["ndias"]; avg2026 = I.get("avg2026", {})

    # TARJETAS (Nivel 1) — Opción B (usuario 2026-07-21): las filiales NO tienen PPTO, así que la META
    # es el PROMEDIO MENSUAL 2026 del REAL y Mayo se lleva a PROYECCIÓN DE CIERRE (MTD/ndias*dim) para
    # comparar mes-completo vs mes-completo (comparar 17 días contra un mes entero daría ~55% siempre).
    # Mismo tratamiento que Blancos en ECP; sin ritmo diario (pace=None) -> las 3 usan la rama "mes vs
    # promedio del año" del frontend. Los FOCOS (Nivel 2) siguen midiendo vs PROGRAMA (camino a).
    titular_cards = []
    for t in titular:
        proj = (t["real"] / ndias * dim) if ndias else 0.0
        meta = avg2026.get(t["producto"], 0.0)
        pctc = round(proj / meta * 100.0, 1) if meta else None
        titular_cards.append({"producto": t["producto"], "real": proj, "ppto": meta,
                              "valor_pct": pctc, "estado": _estado(pctc), "texto": ""})

    # Composer determinista (default entregable): brief/flags con gap_lag; gráficos con gap_full (F2).
    def _fallback():
        return _ejec_fallback(periodo, titular, gap_lag, valle, [],
                              {"campos": 0, "pozos_aprox": 0}, pace, flags,
                              meta_nombre="programa",
                              frase_dep="riesgo de concentración en pocas filiales",
                              frase_prio="las filiales que más arrastran")

    # ---- Pulido LLM (opcional) — mismo gate que ECP (EJECUTIVO_USAR_LLM). Prompt adaptado a FILIALES:
    # meta = PROGRAMA (no presupuesto), unidad = filial, y maneja el caso "todas superan el programa". ----
    def _situacion(pct):
        if pct is None: return "sin dato"
        return "por encima del programa" if pct >= 100 else "por debajo del programa"

    sintesis = []
    for t in titular:
        p, pct = t["producto"], t["valor_pct"]
        if pct is None:
            continue
        ndet = len((gap_full.get(p) or {}).get("detractores", []))
        if pct >= 100:
            lectura = ("todas las filiales cumplieron o superaron su programa" if ndet == 0
                       else "el total supera el programa, aunque alguna filial quedó por debajo")
        else:
            lectura = "el total quedó por debajo del programa"
        sintesis.append({"producto": p, "pct_programa": pct, "lectura": lectura})

    ctx = {
        "periodo": periodo, "corte": corte,
        "productos": [{"producto": t["producto"], "pct_programa": t["valor_pct"],
                       "situacion": _situacion(t["valor_pct"])} for t in titular],
        "sintesis": sintesis, "valle_crudo": valle,
        "detalle_por_filial": {
            p: {
                "filiales_por_debajo": [{"filial": d["campo"], "faltante": abs(d["gap"])}
                                        for d in g["detractores"]],
                "filiales_por_encima": [{"filial": d["campo"], "excedente": d["gap"]}
                                        for d in g["compensadores"]],
            } for p, g in gap_full.items()
        },
        "pace_crudo": pace, "flags": flags,
    }
    prompt = (
        "Eres analista de producción petrolera de las FILIALES (Hocol, America, Permian) y escribes "
        "para directivos NO técnicos. La meta de referencia es el PROGRAMA (no hay presupuesto). Con "
        "estos datos EXACTOS (no inventes ni recalcules cifras) devuelve SOLO un JSON con 4 arrays de "
        'frases: {"insights":[],"oportunidades":[],"puntos_atencion":[],"decisiones":[]}.\n'
        "FORMATO ESTRICTO: responde ÚNICAMENTE el objeto JSON, sin ``` ni texto antes o después; usa "
        "comillas dobles; NO pongas comas finales; NO uses comillas dobles dentro de las frases.\n"
        "TU TAREA ES ANALIZAR, no recitar. Identifica LA historia del mes de las filiales y prioriza. "
        "Apóyate en el bloque 'sintesis' — es tu tesis, nárrala.\n"
        "REGLAS DE REDACCIÓN (obligatorias):\n"
        "1. Español claro, sin jerga. PROHIBIDO la palabra 'gap'. La meta es el 'programa'. Un número "
        "positivo es un 'excedente' (produjo por encima del programa); un negativo es un 'faltante'.\n"
        "2. El PRIMER insight es LA historia del mes: si TODOS los productos superan el programa, dilo "
        "como un logro y destaca qué filial aporta más; si alguno queda por debajo, contrástalo.\n"
        "3. Al mencionar filiales, contrasta las que superan su programa con las que quedan por debajo "
        "(usa detalle_por_filial). No repitas el mismo dato en dos secciones.\n"
        "4. decisiones: acciones concretas y priorizadas (sostener a las filiales líderes; atender a las "
        "rezagadas). Nada genérico.\n"
        "5. Longitud: insights 3-4 frases; oportunidades, puntos_atencion y decisiones 1-3 c/u. Frases "
        "BREVES y directas (~25 palabras máx).\n"
        "SECCIONES: insights = la historia del mes + el pace de crudo. oportunidades = filiales por "
        "encima de su programa que conviene sostener. puntos_atencion = riesgos (filiales por debajo, "
        "pace exigente). decisiones = acciones priorizadas. "
        "Datos: " + _json.dumps(ctx, ensure_ascii=False))

    secciones, generado = None, "fallback"
    llm_diag = {"status": "off"}
    if get_settings().ejecutivo_usar_llm:
        llm_diag = {"status": "?"}
        prosa = _llm_insight(prompt, timeout=180, diag=llm_diag)
        claves = ("insights", "oportunidades", "puntos_atencion", "decisiones")
        if isinstance(prosa, dict) and all(isinstance(prosa.get(k), list) and prosa.get(k) for k in claves):
            secciones = {k: [str(x)[:280] for x in prosa[k]][:5] for k in claves}
            generado = "llm"
        elif llm_diag.get("status") == "ok":
            faltan = [k for k in claves if not (isinstance(prosa, dict) and prosa.get(k))]
            llm_diag["status"] = "faltan_claves:" + ",".join(faltan)
    if secciones is None:
        _st = get_settings()
        if _st.ejecutivo_usar_llm and not _st.ejecutivo_fallback:
            generado = "error"   # en pruebas: no tapar el fallo de Gemma con el texto base
        else:
            secciones = _fallback()

    _tarj_fil = _tarjetas_kpi(titular_cards, None, avg2026)   # se reusa en el return y en _focos

    # Desglose POR FILIAL (además del agregado): cada filial con sus tarjetas Crudo/Gas/Blancos, contra
    # su PROPIO promedio 2026. Reusa _fil_tendencia (el mismo motor del chat) → chat y panel coinciden.
    # por_filial_raw guarda la tendencia CRUDA (proy vs promedio_2026) para alimentar los focos con la
    # MISMA base que las tarjetas — así el bloque central no puede contradecir a las tarjetas.
    por_filial = []; por_filial_raw = []
    with get_engine().connect() as _c:
        for _eid, _nom in _c.execute(sa.text(
                "SELECT empresa_id, nombre FROM core.dim_empresa "
                "WHERE NULLIF(TRIM(nombre),'') IS NOT NULL ORDER BY empresa_id")).all():
            _t = _fil_tendencia(_c, _eid)
            if _t is None:
                continue
            _cards_src = [{"producto": p["producto"], "real": p["proyeccion"],
                           "ppto": (p.get("promedio_2026") or 0), "valor_pct": p.get("variacion_pct"),
                           "estado": "", "texto": ""}
                          for p in _t["por_producto"] if p.get("reporta")]
            if not _cards_src:
                continue
            por_filial_raw.append({"empresa": _nom, "t": _t})
            _avg = {p["producto"]: (p.get("promedio_2026") or 0)
                    for p in _t["por_producto"] if p.get("reporta")}
            por_filial.append({"empresa": _nom, "periodo": _t["periodo"], "n_base": _t["n_base"],
                               "n_meses": _t.get("n_meses"),
                               "tarjetas": _tarjetas_kpi(_cards_src, None, _avg)})

    return {
        "entidad": None, "encontrada": True,
        "por_filial": por_filial,
        "meta": {"scope": _FIL_SCOPE, "periodo": periodo, "corte": corte,
                 "generado_por": generado, "llm_diag": llm_diag},
        "titular": titular, "tarjetas": _tarj_fil,
        "gap_por_producto": gap_full,
        "valle": valle, "eventos": [], "eventos_extra": {"campos": 0, "pozos_aprox": 0},
        "pace_crudo": pace, "flags": flags, "secciones": secciones,
        # Nivel 2 sobre la MISMA base que las tarjetas (proy vs promedio 2026), atribuido por filial.
        "focos": _focos_filiales(titular_cards, por_filial_raw),
        "sin_foco": _sin_foco_filiales(titular_cards, por_filial_raw),
    }


# ============================================================================
# TENDENCIA de UNA filial (para el chat de Consulta, rama B). MISMA base que las tarjetas de
# _ejecutivo_filiales (Opción B, 2026-07-21): proyección de cierre del mes vs su PROMEDIO MENSUAL 2026.
# NO hay PPTO en filiales -> la referencia es su propia historia del año (sin meta fabricada).
# ============================================================================
_FIL_BANDA_PCT = 5.0   # ±5% alrededor del promedio = "en línea" (ni por encima ni por debajo)

def _fil_tendencia(c, empresa_id):
    """Proyección de cierre del mes en curso vs promedio mensual 2026, por producto, para UNA filial.
    None si la filial no tiene REAL diario. Coherente con _ejecutivo_filiales (misma proyección y base)."""
    import calendar
    maxd = c.execute(sa.text(
        "SELECT MAX(fecha) FROM core.fact_produccion_diaria WHERE tipo_id=1 AND empresa_id=:eid"),
        {"eid": empresa_id}).scalar()
    if maxd is None:
        return None
    y, mo = maxd.year, maxd.month
    dim = calendar.monthrange(y, mo)[1]
    ini = f"{y:04d}-{mo:02d}-01"; fin = f"{y:04d}-{mo:02d}-{dim:02d}"
    P = {"eid": empresa_id, "ini": ini, "fin": fin}
    ndias = c.execute(sa.text(
        "SELECT COUNT(DISTINCT fecha) FROM core.fact_produccion_diaria "
        "WHERE tipo_id=1 AND empresa_id=:eid AND fecha BETWEEN :ini AND :fin"), P).scalar() or 0
    mtd = {}
    for prod, tot in c.execute(sa.text("""
        SELECT tp.nombre, SUM(fp.valor_produccion)
        FROM core.fact_produccion_diaria fp
        JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = fp.producto_id
        WHERE fp.tipo_id=1 AND fp.empresa_id=:eid AND fp.fecha BETWEEN :ini AND :fin
        GROUP BY 1"""), P):
        mtd[(prod or "").strip()] = float(tot or 0)
    # Promedio mensual 2026 del REAL (meses COMPLETOS previos al mes en curso) para ESTA filial.
    avg = {}
    for prod, a in c.execute(sa.text("""
        WITH mens AS (
          SELECT tp.nombre AS prod, date_trunc('month', fp.fecha) AS m, SUM(fp.valor_produccion) AS tot
          FROM core.fact_produccion_diaria fp
          JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = fp.producto_id
          WHERE fp.tipo_id=1 AND fp.empresa_id=:eid AND fp.fecha >= :y0 AND fp.fecha < :mes_ini
          GROUP BY 1,2)
        SELECT prod, AVG(tot) FROM mens GROUP BY 1"""),
        {"eid": empresa_id, "y0": f"{y:04d}-01-01", "mes_ini": ini}):
        avg[(prod or "").strip()] = round(float(a or 0))
    completo = ndias >= dim
    por_producto = []
    for p in ["CRUDO", "GAS", "BLANCOS"]:
        m = mtd.get(p, 0.0); base = avg.get(p, 0.0)
        if m == 0 and base == 0:
            por_producto.append({"producto": p, "reporta": False}); continue
        proy = m if completo else (m / ndias * dim if ndias else 0.0)
        var = round((proy / base - 1) * 100, 1) if base else None
        direc = (None if var is None else
                 ("en línea" if abs(var) <= _FIL_BANDA_PCT else ("por encima" if var > 0 else "por debajo")))
        por_producto.append({"producto": p, "proyeccion": round(proy), "mtd": round(m),
                             "promedio_2026": base, "variacion_pct": var, "direccion": direc,
                             "reporta": True})
    # n_meses = meses de 2026 (previos al mes en curso) con cobertura COMPLETA (>=20 días) que
    # sostienen el promedio. (n_base cuenta PRODUCTOS, no meses — se conserva por compatibilidad.)
    n_meses = c.execute(sa.text("""
        SELECT COUNT(*) FROM (
          SELECT date_trunc('month', fecha) m
          FROM core.fact_produccion_diaria
          WHERE tipo_id=1 AND empresa_id=:eid AND fecha >= :y0 AND fecha < :mes_ini
          GROUP BY 1 HAVING COUNT(DISTINCT fecha) >= 20) t"""),
        {"eid": empresa_id, "y0": f"{y:04d}-01-01", "mes_ini": ini}).scalar() or 0
    return {"empresa_id": empresa_id, "y": y, "mo": mo, "dim": dim, "ndias": ndias,
            "periodo": f"{MESES_ES[mo]} {y}", "completo": completo,
            "n_base": sum(1 for v in avg.values() if v), "n_meses": int(n_meses),
            "por_producto": por_producto}


@router.get("/tendencia_filial")
def tendencia_filial(empresa: str = Query(...), periodo: str | None = Query(None)):
    """Tendencia de una filial (chat rama B): proyección de cierre vs su promedio 2026. Sin PPTO."""
    eng = get_engine()
    with eng.connect() as c:
        eid = c.execute(sa.text(
            "SELECT empresa_id FROM core.dim_empresa WHERE UPPER(TRIM(nombre)) = UPPER(TRIM(:n))"),
            {"n": empresa}).scalar()
        if eid is None:
            return {"entidad": empresa, "encontrada": False}
        t = _fil_tendencia(c, eid)
        if t is None:
            return {"entidad": empresa, "encontrada": True, "sin_datos": True}
        if t["n_base"] == 0:   # sin meses completos previos -> no hay contra qué comparar la tendencia
            return {"entidad": empresa, "encontrada": True, "sin_tendencia": True, "periodo": t["periodo"]}
        # Tarjetas KPI (mismas del desglose por filial del panorama) para el panel EXCLUSIVO de la filial:
        # proyección de cierre vs su promedio 2026, por producto. Reusa _tarjetas_kpi → 0 divergencia.
        _cards = [{"producto": p["producto"], "real": p["proyeccion"], "ppto": (p.get("promedio_2026") or 0),
                   "valor_pct": p.get("variacion_pct"), "estado": "", "texto": ""}
                  for p in t["por_producto"] if p.get("reporta")]
        _avg = {p["producto"]: (p.get("promedio_2026") or 0) for p in t["por_producto"] if p.get("reporta")}
        tarjetas = _tarjetas_kpi(_cards, None, _avg)
        serie = _fil_serie_mensual(c, eid, t["y"], t["mo"])   # dentro del with (misma conexión abierta)
    return {"entidad": empresa, "encontrada": True, "tarjetas": tarjetas, "serie_mensual": serie, **t}


def _fil_serie_mensual(c, empresa_id, cur_y, cur_mo):
    """Serie mensual REAL por producto (para el gráfico de evolución del panel de una filial).
    - Meses COMPLETOS (>=60% de días): valor real del mes.
    - Mes EN CURSO: PROYECCIÓN de cierre (MTD/ndias*dim), marcado en proyectado_idx (coherente con las
      tarjetas, que ya proyectan el cierre).
    - Excluye meses casi vacíos (p.ej. 1 día) que distorsionan la tendencia (Nov 2025).
    Doble eje en el frontend: Crudo/Blancos en bbl (Y izq), Gas en MSCF (Y der)."""
    import calendar as _cal
    rows = c.execute(sa.text("""
        SELECT date_trunc('month', fp.fecha) m, tp.nombre prod,
               SUM(fp.valor_produccion) tot, COUNT(DISTINCT fp.fecha) dias
        FROM core.fact_produccion_diaria fp
        JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = fp.producto_id
        WHERE fp.tipo_id=1 AND fp.empresa_id=:e
        GROUP BY 1, 2 ORDER BY 1"""), {"e": empresa_id}).all()
    by_m = {}
    for m, prod, tot, dias in rows:
        by_m.setdefault(m, {})[(prod or "").strip()] = (float(tot or 0), int(dias or 0))
    meses, series = [], {"CRUDO": [], "GAS": [], "BLANCOS": []}
    proy_idx = None
    for m in sorted(by_m):
        dim_m = _cal.monthrange(m.year, m.month)[1]
        es_actual = (m.year == cur_y and m.month == cur_mo)
        dias_m = max((v[1] for v in by_m[m].values()), default=0)
        if not es_actual and dias_m < 0.6 * dim_m:
            continue                                   # mes casi vacío -> fuera (Nov 2025 = 1 día)
        meses.append(MESES_ES[m.month][:3] + " " + str(m.year))
        for p in ["CRUDO", "GAS", "BLANCOS"]:
            if p in by_m[m]:
                tot, dias = by_m[m][p]
                series[p].append(round(tot / dias * dim_m) if (es_actual and dias) else round(tot))
            else:
                series[p].append(None)                 # producto no reportado ese mes -> hueco
        if es_actual:
            proy_idx = len(meses) - 1
    series = {p: v for p, v in series.items() if any(x is not None for x in v)}   # quita productos sin dato
    return {"meses": meses, "series": series, "proyectado_idx": proy_idx,
            "unidades": {"CRUDO": "bbl", "GAS": "MSCF", "BLANCOS": "bbl"}}


@router.get("/president")
def president(periodo: str | None = Query(None)):
    """Tarjeta P50 por producto desde la hoja REPORTE_PRESIDENT (fact_tabla_hoja) — escala kbpe
    corporativa (mundo P50, NO la del fact diario). Fuente ÚNICA con BLANCOS Real/Proy/P50 + el
    'compromiso' (Reto). Sin `periodo` toma el reporte más reciente que tenga la hoja; con `periodo`
    (YYYY-MM) el más reciente de ese mes. Devuelve por entidad TODAS las medidas + cumplimiento vs P50;
    la referencia del semáforo (P50 vs PPTO) la decide el frontend — este endpoint es agnóstico."""
    eng = get_engine()
    with eng.connect() as c:
        if periodo:
            rid = c.execute(sa.text("""
                SELECT cr.reporte_id FROM core.config_reporte cr
                WHERE to_char(cr.fecha_reporte,'YYYY-MM') = :p
                  AND EXISTS (SELECT 1 FROM core.fact_tabla_hoja f
                              WHERE f.reporte_id = cr.reporte_id AND f.hoja = 'REPORTE_PRESIDENT')
                ORDER BY cr.fecha_reporte DESC LIMIT 1"""), {"p": periodo}).scalar()
        else:
            # [2026-07-29] Antes: MAX(reporte_id). Asumia que el id es cronologico y NO lo es --
            # reporte_id es un serial por ORDEN DE INGESTA. En dev mayo se ingirio primero
            # (ids 1-18) y marzo despues (ids 108-139), asi que MAX(id) devolvia MARZO aun teniendo
            # mayo cargado -> el encabezado del analisis mostraba un mes distinto al del resto del
            # panel y las tarjetas parecian contradecirse. Se ordena por FECHA, como la rama de
            # `periodo` (que si estaba bien) y como dice el docstring.
            rid = c.execute(sa.text("""
                SELECT cr.reporte_id FROM core.config_reporte cr
                WHERE EXISTS (SELECT 1 FROM core.fact_tabla_hoja f
                              WHERE f.reporte_id = cr.reporte_id AND f.hoja = 'REPORTE_PRESIDENT')
                ORDER BY cr.fecha_reporte DESC LIMIT 1""")).scalar()
        if not rid:
            return {"encontrada": False}
        fr = c.execute(sa.text("SELECT fecha_reporte FROM core.config_reporte WHERE reporte_id=:r"),
                       {"r": rid}).first()
        corte = fr[0].isoformat() if (fr and fr[0]) else None
        piv = {}
        for r in c.execute(sa.text("""
            SELECT dims->>'entidad' ent, dims->>'medida' med, valor
            FROM core.fact_tabla_hoja WHERE hoja='REPORTE_PRESIDENT' AND reporte_id=:r"""), {"r": rid}):
            piv.setdefault(r[0], {})[r[1]] = float(r[2])

    def _card(ent):
        d = piv.get(ent, {})
        real = d.get("real_mes"); p50 = d.get("base_p50"); comp = d.get("compromiso")
        cumpl = round(real / p50 * 100.0, 1) if (real and p50) else None
        return {
            "entidad": ent,
            "real_dia": d.get("real_dia"), "programa_dia": d.get("programa_dia"),
            "delta_dia": d.get("delta_dia"),
            "real_mes": real, "proy_mes": d.get("proy_mes"),
            "base_p50": p50, "compromiso": comp,
            "delta_p50": d.get("delta_p50"), "delta_compromiso": d.get("delta_compromiso"),
            "cumpl_p50": cumpl,
            "compromiso_difiere": (comp is not None and p50 is not None and abs(comp - p50) > 1e-6),
        }

    productos = [_card(e) for e in ["Crudo", "Gas", "Blancos"] if e in piv]
    totales = [_card(e) for e in ["Ecopetrol", "Filiales", "Upstream"] if e in piv]
    return {"encontrada": True, "reporte_id": rid, "corte": corte, "unidad": "kbpe",
            "productos": productos, "totales": totales}


# ---------------------------------------------------------------------------
# [2026-08-25] GRANO DÍA (plan QV2-GRANO-DIA). Helpers AISLADOS y read-only: mismo criterio que
# `escenario_mes` (AF-4.2) — reusan `_ambito` para el ámbito y NO tocan `desempeno`.
# 🔑 core.fact_produccion_dia_ecp NO tiene escenario_id: a grano día solo existe REAL, jamás PPTO.
# ---------------------------------------------------------------------------
def _amb_dia(c, entidad, nivel):
    """(cond_where, params_base, ids) del ámbito para las tablas de grano día. None si no aplica."""
    amb = _ambito(c, entidad, nivel=nivel)
    if not amb or amb.get("sin_datos"):
        return None
    ids, vid = amb.get("ids"), amb.get("vid")
    if not ids and vid is None:
        return None
    cond, params = [], {}
    if ids:
        cond.append("d.fuente_id IN :ids"); params["ids"] = ids
    if vid is not None:
        cond.append("d.vice_id = :vid"); params["vid"] = vid
    return "(" + " OR ".join(cond) + ")", params, ids


def techo_dia(entidad: str, nivel: str | None = None):
    """Última fecha con reporte DIARIO en el ámbito de la entidad, o None.
    Es la fuente del rechazo honesto: el mensaje cita esta fecha, jamás una constante."""
    eng = get_engine()
    with eng.connect() as c:
        r = _amb_dia(c, entidad, nivel)
        if r is None:
            return None
        whr, params, ids = r
        t = sa.text(f"SELECT MAX(d.fecha) FROM core.fact_produccion_dia_ecp d WHERE {whr}")
        if ids:
            t = t.bindparams(sa.bindparam("ids", expanding=True))
        return c.execute(t, params).scalar()


def produccion_dia(entidad: str, fecha, nivel: str | None = None) -> dict:
    """REAL por producto en UNA fecha, con el MISMO ámbito que `desempeno`.
    Devuelve {"por_producto": {PROD: float}, "techo": date|None, "hay_dato": bool}."""
    eng = get_engine()
    with eng.connect() as c:
        r = _amb_dia(c, entidad, nivel)
        if r is None:
            return {"por_producto": {}, "techo": None, "hay_dato": False}
        whr, params, ids = r

        def _b(sql):
            t = sa.text(sql)
            return t.bindparams(sa.bindparam("ids", expanding=True)) if ids else t

        p = dict(params); p["f"] = str(fecha)
        rows = c.execute(_b(f"""
            SELECT tp.nombre prod, SUM(d.volumen) vol
            FROM core.fact_produccion_dia_ecp d
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = d.tipo_producto_id
            WHERE d.fecha = :f AND {whr} GROUP BY 1"""), p)
        por = {k: float(v or 0) for k, v in rows}
        techo = c.execute(_b(
            f"SELECT MAX(d.fecha) FROM core.fact_produccion_dia_ecp d WHERE {whr}"), params).scalar()
        # hay_dato = hay alguna fila CON volumen > 0 (una fila en 0 no es "dato del día").
        return {"por_producto": por, "techo": techo,
                "hay_dato": any(v > 0 for v in por.values())}


def curva_dia_mes(entidad: str, anio: int, mes: int, producto: str,
                  nivel: str | None = None) -> list:
    """Serie diaria [(date, float)] de UN producto dentro de un mes. Base del selector
    (mejor/peor día). `producto` en MAYÚSCULAS ('CRUDO'|'GAS'|'BLANCOS')."""
    import calendar
    eng = get_engine()
    with eng.connect() as c:
        r = _amb_dia(c, entidad, nivel)
        if r is None:
            return []
        whr, params, ids = r
        dim = calendar.monthrange(anio, mes)[1]
        p = dict(params)
        p.update({"ini": f"{anio:04d}-{mes:02d}-01",
                  "fin": f"{anio:04d}-{mes:02d}-{dim:02d}", "p": producto.upper()})
        t = sa.text(f"""
            SELECT d.fecha, SUM(d.volumen) vol
            FROM core.fact_produccion_dia_ecp d
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = d.tipo_producto_id
            WHERE d.fecha BETWEEN :ini AND :fin AND UPPER(tp.nombre) = :p AND {whr}
            GROUP BY d.fecha ORDER BY d.fecha""")
        if ids:
            t = t.bindparams(sa.bindparam("ids", expanding=True))
        return [(f, float(v or 0)) for f, v in c.execute(t, p)]
