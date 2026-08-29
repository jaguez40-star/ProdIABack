"""analizar/p50_referencia.py — P50 pedido como REFERENCIA (cifra), Analizar sub-intención
'referencia' (2026-08-13, plan plan_p50_referencia_analizar_2026-08-13.md).

El P50 es un compromiso corporativo: se pacta en kbpe para Ecopetrol como un todo (fuente
REPORTE_PRESIDENT) y, como desglose más fino, por VICEPRESIDENCIA (fuente NEW MES-AÑO t8 «P50 ECP»,
en bbl/MSCF). NO se define por campo/activo/gerencia en NINGUNA de las 16 hojas del reporte (A1 del
plan) — a esos niveles se DECLINA, honesto, y se ofrecen las vecinas que EXISTAN.

🔑 `core.dim_vicepresidencia` (GGN/GPU/GOX/GGS/VAS/VFS/VEX/VRC/VAO/VRO/VPI) y los códigos `vice` de
t8 (GOR/GAA/GLH/GNS/GRM/GPA/GTA/GCT/DFL/GAN/PRP/CPV/GXO) son taxonomías DISTINTAS, sin un solo
código en común (A6 del plan) — por eso `vp_de_campo()` traduce por `core.map_campo_robustez.
rob_vicepresidencia`, NUNCA por `dim_vicepresidencia`.
"""
import sqlalchemy as sa

from app.core.db import get_engine
from app.features.consulta_v2.cuantificar.validador import fmt_valor

_NIVELES_OK = (None, "vicepresidencia")   # None = global ECP. Mismo criterio que diferidas.py /
                                          # economia.py (FC-3/H8): la regla de nivel vive en el módulo.

# Unidades del FACT OPERATIVO (fact_produccion_mes_ecp) — las usa el DECLINAR, cuyas cifras vienen
# de `analisis.ejecutivo`. Ahí el gas va en volumen crudo y se muestra en MSCF (÷1e6, vía _fmt).
_UNIDAD = {"CRUDO": "bbl", "GAS": "MSCF", "BLANCOS": "bbl"}   # mismo dict que analizar/plantilla.py
_PROD_L = {"CRUDO": "crudo", "GAS": "gas", "BLANCOS": "blancos"}

# 🔑 [2026-08-13] La hoja del P50 (`NEW MES-AÑO` t8 «P50 ECP» / t2 «REAL PROMEDIO MES») está en
# PROMEDIO DIARIO — el propio nombre de la tabla lo dice—, NO en total mensual como el fact
# operativo. Medido contra la BD (abril-2026, suma de las 12 VP):
#     CRUDO  t8 = 509.804,5  ·  REPORTE_PRESIDENT base_p50 Crudo = 521,8 kbpe  ⇒ t8 son BPD
#     CRUDO  t2 = 492.932    ·  fact_produccion_mes_ecp = 85.417.841 (mes)     ⇒ ratio ≠ 1e6
#     GAS    t2 =  75.974,7  ·  fact = 66.663.907 (mes)                        ⇒ ratio ≠ 1e6
# Ningún ratio es 1e6 ⇒ el ÷1e6 de MSCF/__cnGasM **NO aplica a esta hoja**. Aplicarlo mostraba el
# gas de PRP como «0,03 MSCF» en vez de «33.453,2» — mil veces menor, sin error visible. 🔑 El
# defecto vivía YA en el mensaje del chat desde dd8ffa2 y NO se detectó porque las verificaciones
# en navegador solo usaron GOR y Rubiales, ambos CRUDO, que no se divide.
# Por eso la ruta VP tiene su propia unidad (bpd) y su propio formateador: cifra TAL CUAL.
_UNIDAD_VP = {"CRUDO": "bpd", "GAS": "bpd", "BLANCOS": "bpd"}


def _fmt_vp(valor) -> str:
    """Formato de la hoja P50 (t8/t2): la cifra va TAL CUAL, SIN conversión de escala (ver la nota
    de arriba). Miles es-CO con 1 decimal — los valores son del orden de 10³-10⁵ (promedio diario),
    no de 10⁷ como el total mensual del fact operativo."""
    try:
        return f"{float(valor):,.1f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    except Exception:
        return str(valor)
_NIVEL_TXT = {"campo": "el Campo", "activo": "el Activo"}     # mismo criterio que plantilla.py (D-A5)
_MES = ("", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
        "septiembre", "octubre", "noviembre", "diciembre")


def nivel_soportado(nivel: str | None, resuelta: dict | None = None) -> bool:
    """El P50 solo se define global (ECP, REPORTE_PRESIDENT) o por vicepresidencia (NEW MES-AÑO
    t8). campo/activo/operador/fuente -> False.

    🔑 `gerencia` con `puente=True` SÍ se soporta: el resolver marca así (S32/R2) los códigos que
    INGESTA llama "gerencia" pero que en robustez son VICEPRESIDENCIAS reales (GOR, GAA…), que es
    justo la taxonomía de t8. Sin esta rama, "el P50 de GOR" declinaba pese a EXISTIR — y el drill
    de "la vicepresidencia" caía en un declinar tras otro (verificado 2026-08-13).
    `resuelta` = el dict de resolver_unico (opcional: sin él, solo se mira el nivel)."""
    if nivel in _NIVELES_OK:
        return True
    return nivel == "gerencia" and bool((resuelta or {}).get("puente"))


def _mes_de(fecha) -> str:
    try:
        return _MES[fecha.month]
    except Exception:
        return str(fecha)


def _fmt(valor, producto: str) -> str:
    return fmt_valor(valor, _PROD_L.get(producto, "crudo"))


# --- vp_de_campo: campo INGESTA -> código de vicepresidencia t8-compatible -------------------
_VP_DE_CAMPO_CACHE: dict = {}


def vp_de_campo(campo: str) -> str | None:
    """core.map_campo_robustez -> rob_vicepresidencia (⚠️ NUNCA rob_gerencia — level-shift ya
    documentado: lo que INGESTA llama "gerencia" puede ser una VP real en robustez). None si el
    campo no está en el mapeo o no tiene VP (59 de 139 campos, terceros — A5 del plan).
    Cacheado en proceso; los errores de conexión NO se cachean (pueden ser transitorios)."""
    key = (campo or "").strip().upper()
    if not key:
        return None
    if key in _VP_DE_CAMPO_CACHE:
        return _VP_DE_CAMPO_CACHE[key]
    try:
        eng = get_engine()
        with eng.connect() as c:
            val = c.execute(sa.text(
                "SELECT rob_vicepresidencia FROM core.map_campo_robustez "
                "WHERE UPPER(TRIM(campo)) = UPPER(TRIM(:v))"), {"v": campo}).scalar()
    except Exception:
        return None   # transitorio: no se cachea
    _VP_DE_CAMPO_CACHE[key] = val
    return val


# --- p50_por_vp: cifra P50 vs REAL de una vicepresidencia --------------------------------------
# R-A del plan: caché en proceso OBLIGATORIA (mismo criterio que analizar/diferidas.py::
# _SPLIT_CACHE) — acotar SIEMPRE por reporte_id, o un `dims->>'x'` escanea 62M filas (medido:
# timeout >120s). R-B: los errores no se cachean; "sin datos" (None) sí.
_P50_VP_CACHE: dict = {}


def p50_por_vp(vice: str, producto: str = "CRUDO") -> dict | None:
    """Join NEW MES-AÑO t8 (P50) ⟕ t2 (REAL) por (reporte_id, fecha, dims), del reporte MÁS
    RECIENTE. Devuelve {'vice','producto','fecha','real','p50','pct'} de la ÚLTIMA fecha con AMBOS
    valores (A3 del plan: t2 hoy termina en abril aunque t8 llegue a diciembre — la fecha se LEE
    del dato, JAMÁS se hardcodea), o None si la VP no está en t8 (GLH/GNS no están en robustez, pero
    SÍ en t8 — el caso inverso, una VP de t8 sin REAL, también da None aquí) o no hay REAL."""
    key = (vice or "").strip().upper(), (producto or "CRUDO").strip().upper()
    if key in _P50_VP_CACHE:
        return _P50_VP_CACHE[key]
    if not key[0]:
        return None
    try:
        eng = get_engine()
        with eng.connect() as c:
            # 🔑 El reporte MÁS RECIENTE puede NO traer la hoja «NEW MES-AÑO» (no todos los .xlsm
            # la incluyen — §4/§4c: la cobertura por archivo es heterogénea). Anclarse al último
            # reporte a secas hacía que la respuesta fuera "no tengo P50" aunque el dato SÍ
            # existiera en un reporte anterior — defecto real visto en el servidor de pruebas
            # (2026-08-13), invisible en dev porque ahí los 18 reportes traen la hoja.
            # Se toma el reporte más reciente QUE TENGA el dato, y se declara cuál fue.
            row = c.execute(sa.text("""
                SELECT p.fecha, p.valor, r.valor, cr.fecha_reporte
                FROM core.fact_tabla_hoja p
                JOIN core.fact_tabla_hoja r
                  ON r.reporte_id = p.reporte_id AND r.hoja = p.hoja AND r.tabla_idx = 2
                 AND r.fecha = p.fecha AND r.dims = p.dims
                JOIN core.config_reporte cr ON cr.reporte_id = p.reporte_id
                WHERE p.hoja = 'NEW MES-AÑO' AND p.tabla_idx = 8
                  AND p.dims->>'vice' = :vice AND p.dims->>'producto' = :prod
                  AND r.valor IS NOT NULL
                ORDER BY cr.fecha_reporte DESC, p.fecha DESC LIMIT 1
            """), {"vice": key[0], "prod": key[1]}).first()
    except Exception:
        return None   # transitorio: no se cachea
    if row is None:
        _P50_VP_CACHE[key] = None
        return None
    fecha, p50, real, corte = row
    p50, real = float(p50), float(real)
    info = {"vice": key[0], "producto": key[1], "fecha": fecha, "real": real, "p50": p50,
            "pct": round(real / p50 * 100, 1) if p50 else None, "corte": corte}
    _P50_VP_CACHE[key] = info
    return info


# --- serie_por_vp: serie mensual completa P50+REAL de una vicepresidencia ----------------------
# Panel derecho (2026-08-13, plan_panel_p50_vp_2026-08-13.md). MISMO criterio de reporte_id que
# p50_por_vp tras dd8ffa2 (el más reciente que TENGA la hoja, no el más reciente a secas) — pero
# aquí se resuelve UNA vez y se reusa para las 12 filas, en vez de repetir el JOIN por fecha.
_SERIE_VP_CACHE: dict = {}


def serie_por_vp(vice: str, producto: str = "CRUDO") -> dict | None:
    """Serie mensual completa (P50 + REAL) de una vicepresidencia/producto, del reporte más
    reciente que tenga la hoja «NEW MES-AÑO». None si esa VP no reporta ese producto (A1 del plan:
    BLANCOS no existe para ninguna, GAS solo para 6 de 12).

    🔑 FRONTERA DE CONVENCIÓN (H4): `producto` ENTRA en MAYÚSCULAS (como el resto de este módulo,
    _UNIDAD/_PROD_L/_fmt están indexados así) y el dict de SALIDA lleva `producto` en minúsculas
    — es lo que consumen los 6 tipos de panel existentes del Motor Q v2 (`d.producto === "gas"` en
    __cnRankDotHtml/__cnCuantCardHtml). Mezclar las convenciones ROMPE EL GAS EN SILENCIO: medido,
    `_fmt(1e7, "gas")` da "10.000.000" en vez de "10,0" (la conversión a MSCF depende de la clave
    en MAYÚSCULAS). Por eso la key de caché y las consultas SQL usan `producto.upper()`, y SOLO al
    construir el dict de retorno se hace `.lower()`.

    Los valores (`real`/`p50`/`serie[].*`) viajan CRUDOS, SIN convertir — el ÷1e6 del gas lo hace
    el frontend (__cnGasM), igual que en cuant_kpi/cuant_serie/cuant_rank. Pre-dividir aquí
    dividiría dos veces en el panel.

    `real` es None en los meses sin dato (A2: el REAL por VP termina en abril) — el trazo se corta
    ahí, NUNCA se interpola ni se rellena con 0."""
    prod_up = (producto or "CRUDO").strip().upper()
    key = ((vice or "").strip().upper(), prod_up)
    if key in _SERIE_VP_CACHE:
        return _SERIE_VP_CACHE[key]
    if not key[0]:
        return None
    try:
        eng = get_engine()
        with eng.connect() as c:
            # Mismo criterio que p50_por_vp (dd8ffa2): el reporte más reciente puede NO traer la
            # hoja -> se toma el más reciente QUE SÍ la tenga.
            rid = c.execute(sa.text("""
                SELECT cr.reporte_id FROM core.config_reporte cr
                WHERE EXISTS (SELECT 1 FROM core.fact_tabla_hoja f
                              WHERE f.reporte_id = cr.reporte_id AND f.hoja = 'NEW MES-AÑO'
                                AND f.tabla_idx = 8)
                ORDER BY cr.fecha_reporte DESC LIMIT 1
            """)).first()
            if rid is None:
                _SERIE_VP_CACHE[key] = None
                return None
            rid, corte = rid[0], None
            corte = c.execute(sa.text(
                "SELECT fecha_reporte FROM core.config_reporte WHERE reporte_id=:r"),
                {"r": rid}).scalar()
            # ⚠️ SIEMPRE con p.reporte_id = :rid FIJO (A3 del plan): sin esa cláusula el mismo
            # query pasa de 0,00s a 2,61s (medido) por escanear los 62M de fact_tabla_hoja.
            rows = c.execute(sa.text("""
                SELECT p.fecha, p.valor, r.valor
                FROM core.fact_tabla_hoja p
                LEFT JOIN core.fact_tabla_hoja r
                  ON r.reporte_id = p.reporte_id AND r.hoja = p.hoja AND r.tabla_idx = 2
                 AND r.fecha = p.fecha AND r.dims = p.dims
                WHERE p.reporte_id = :rid AND p.hoja = 'NEW MES-AÑO' AND p.tabla_idx = 8
                  AND p.dims->>'vice' = :vice AND p.dims->>'producto' = :prod
                ORDER BY p.fecha
            """), {"rid": rid, "vice": key[0], "prod": key[1]}).fetchall()
    except Exception:
        return None   # transitorio: no se cachea

    if not rows:
        _SERIE_VP_CACHE[key] = None
        return None

    serie = [{"fecha": f.isoformat(), "p50": float(p50), "real": (float(r) if r is not None else None)}
              for f, p50, r in rows]
    con_real = [p for p in serie if p["real"] is not None]
    if not con_real:
        _SERIE_VP_CACHE[key] = None
        return None
    ultimo = con_real[-1]   # el más reciente CON real (A2: puede no ser el último de la serie)
    p50_u, real_u = ultimo["p50"], ultimo["real"]

    info = {
        # Unidad de la HOJA P50 (_UNIDAD_VP), no la del fact operativo: esta serie NO se divide
        # por 1e6 (ver la nota de escala arriba). `fmt: "vp"` le dice al frontend que muestre la
        # cifra tal cual — sin él, __cnGasM la dividiría y el gas saldría 1e6 veces menor.
        "vice": key[0], "producto": prod_up.lower(), "unidad": _UNIDAD_VP.get(prod_up, "bpd"),
        "fmt": "vp",
        "corte": corte.isoformat() if corte else None, "mes_real": ultimo["fecha"],
        "real": real_u, "p50": p50_u,
        "pct": round(real_u / p50_u * 100, 1) if p50_u else None,
        "gap": round(real_u - p50_u, 1) if p50_u else None,
        "serie": serie,
    }
    _SERIE_VP_CACHE[key] = info
    return info


def _kbpe(n) -> str:
    """Miles es-CO con 1 decimal: 501716.53 -> '501.716,5'. ⚠️ NO basta `.replace(",", ".")` sobre
    un `{:,.1f}`: eso deja el separador decimal como punto y produce '501.716.5', un número
    ambiguo/inválido en es-CO (bug real corregido 2026-08-13, encontrado en verificación)."""
    try:
        return f"{float(n):,.1f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    except Exception:
        return str(n)


def formatear_cifra_global(card: dict, unidad: str, producto: str, corte: str | None) -> str:
    """Cuerpo cuando el P50 SÍ existe a nivel Ecopetrol (REPORTE_PRESIDENT). `card` = el dict de
    analisis.president() para la entidad elegida ({'entidad','real_mes','base_p50','compromiso',
    'cumpl_p50',...}). PURA: no toca BD ni LLM."""
    ent = card.get("entidad", "Ecopetrol")
    real, p50 = card.get("real_mes"), card.get("base_p50")
    pct = card.get("cumpl_p50")
    if real is None or p50 is None:
        return f"No tengo el P50 de {ent} disponible en este momento."
    linea = (f"📊 {ent} · compromiso P50" + (f" (corte {corte})" if corte else "") + "\n\n"
             f"Real del mes: {_kbpe(real)} {unidad} · Base P50: {_kbpe(p50)} {unidad}")
    if pct is not None:
        linea += f" · {pct}% del P50"
    comp = card.get("compromiso")
    if comp is not None and card.get("compromiso_difiere"):
        linea += f"\nCompromiso (RETO): {_kbpe(comp)} {unidad}"
    return linea


def formatear_cifra_vp(vice: str, info: dict, producto: str) -> str:
    """Cuerpo cuando el P50 existe por VICEPRESIDENCIA (NEW MES-AÑO t8+t2). `info` = el dict de
    `p50_por_vp`. ⚠️ Rotula unidad (bbl/MSCF, R6 — NO kbpe, esa es la escala corporativa) y el
    periodo (R5 — el REAL por VP se congela en abril; se dice el mes explícitamente)."""
    # ⚠️ Escala de la HOJA P50, no la del fact: `_UNIDAD_VP` + `_fmt_vp` (sin ÷1e6). Con la unidad
    # del fact ("MSCF") y `_fmt`, el gas de PRP salía «0,03» en vez de «33.453,2» — mil veces
    # menor, sin error visible. Ver la nota de escala en la cabecera del módulo.
    u = _UNIDAD_VP.get(producto, "bpd")
    mes = _mes_de(info["fecha"])
    pl = _PROD_L.get(producto, producto.lower())
    linea = (f"📊 Vicepresidencia {vice} · P50 de {pl}\n\n"
             f"En {mes}, el último mes con real por vicepresidencia (promedio diario): "
             f"{_fmt_vp(info['real'])} {u} vs P50 {_fmt_vp(info['p50'])} {u}")
    if info.get("pct") is not None:
        linea += f" ({info['pct']}%)."
    else:
        linea += "."
    return linea


def _de(quien: str) -> str:
    """Contracción es-CO: 'de el Campo X' -> 'del Campo X'. Sin nivel_txt, 'de X' tal cual."""
    return f"del {quien[3:]}" if quien.startswith("el ") else f"de {quien}"


def formatear_declinar(entidad: str, nivel: str | None, ppto_pct, ppto_gap, producto,
                        vp_info: dict | None) -> str:
    """PURA. El P50 NO existe para `entidad` a este nivel — mensaje de §4.4 del plan (M1-M4, M6-M8).
    `ppto_pct`/`ppto_gap`/`producto` = cifra vs presupuesto YA calculada por el llamador (puede ser
    None si el campo no tiene meta en el periodo). `vp_info` = dict de p50_por_vp, o None si no hay
    VP ofrecible (M6: campo de tercero, o VP huérfana de t8). NO incluye el cierre (ver
    `cierre_declinar`) — cuerpo y cierre son piezas separadas, como el resto de sub-intenciones."""
    nivel_txt = _NIVEL_TXT.get(nivel, "")
    quien = f"{nivel_txt} {entidad}".strip() if nivel_txt else (entidad or "esa entidad")

    lineas = [
        f"No tengo un P50 para {entidad}. El P50 es un compromiso corporativo: se pacta para "
        "Ecopetrol como un todo y el desglose más fino que existe es por vicepresidencia — "
        "nunca por campo.",
        "",
        f"Lo que sí tengo {_de(quien)}:",
        "",
    ]

    if ppto_pct is not None:
        u = _UNIDAD.get(producto, "bbl")
        pl = _PROD_L.get(producto, "crudo")
        if ppto_gap is not None and ppto_gap < 0:
            gap_txt = f", con un faltante de {_fmt(abs(ppto_gap), producto)} {u} frente a la meta del mes"
        elif ppto_gap is not None and ppto_gap > 0:
            gap_txt = f", con un excedente de {_fmt(abs(ppto_gap), producto)} {u} sobre la meta del mes"
        else:
            gap_txt = ""
        lineas.append(f"  · Contra el presupuesto de {pl} — cerró al {ppto_pct}%{gap_txt}.")
    else:
        lineas.append("  · No tiene meta de presupuesto definida en el periodo.")

    if vp_info:
        mes = _mes_de(vp_info["fecha"])
        pct_txt = f" quedó en {vp_info['pct']}%" if vp_info.get("pct") is not None else " no tiene cifra comparable"
        lineas += ["", f"  · El P50 de su vicepresidencia ({vp_info['vice']}) — en {mes}, el "
                        f"último mes con real por vicepresidencia,{pct_txt}."]

    return "\n".join(lineas)


def cierre_declinar(vp_info: dict | None) -> str:
    """Cierre DINÁMICO del declinar (M9): usa palabras que el drill de ANALIZAR reconoce
    (PRESUPUESTO/VICEPRESIDENCIA) y M5, nunca termina en pregunta sí/no."""
    if vp_info:
        return "Dime cuál te sirve: el presupuesto o la vicepresidencia."
    return "Si quieres el detalle contra el presupuesto, dímelo."
