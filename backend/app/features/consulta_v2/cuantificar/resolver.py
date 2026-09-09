"""cuantificar/resolver.py — nombre de entidad → identidad resuelta (nivel + valor + rama), D-D5.

# FORK de consulta/resolver.py @ 2026-08-02  (índice invertido + colapso físico + fuentes_de_activo)
# FORK de consulta/maquina.py  @ 2026-08-02  (_PRIORIDAD / _rep / _resolver_colision / _prioridad_campo)

Edificio SEPARADO (Motor Q v2): cero imports de consulta/ (v1 congelada). Se copia lo necesario y
se marca el fork. La política de resolución es DETERMINISTA y idéntica a v1 para no divergir en las
cifras: mismo índice, mismo colapso por conjunto físico de fuente_id, misma prioridad Campo (D-D5).

Frontera: aquí NO interviene el LLM. `resolver_unico()` devuelve UNA identidad para el caso limpio
o de colisión redundante/Campo; en colisión genuina (Hocol dual, 2 campos distintos) devuelve
`{"ambiguo": [...]}` — la UX de desambiguación es de una sub-fase posterior (Fase 1e/2).
"""
import re

import sqlalchemy as sa
from app.core.db import get_engine
from app.features.consulta_v2.normaliza import norm

# nivel -> (query de valores distintos, rama) · rama A = ECP, B = filial.  Idéntico a v1 (activo desde
# core.map_campo_activo, migración 008; NO de dim_fuente — ver encabezado de consulta/resolver.py).
_LEVELS = [
    ("fuente",          "SELECT DISTINCT nombre   FROM core.dim_fuente          WHERE NULLIF(TRIM(nombre),'')   IS NOT NULL", "A"),
    ("campo",           "SELECT DISTINCT campo    FROM core.dim_fuente          WHERE NULLIF(TRIM(campo),'')    IS NOT NULL", "A"),
    ("activo",          "SELECT DISTINCT activo   FROM core.map_campo_activo    WHERE NULLIF(TRIM(activo),'')   IS NOT NULL", "A"),
    ("gerencia",        "SELECT DISTINCT gerencia FROM core.dim_fuente          WHERE NULLIF(TRIM(gerencia),'') IS NOT NULL", "A"),
    # [2026-09-09 · BUG1-GERENCIAS] Las gerencias REALES NO salen de aquí: `dim_fuente.gerencia`
    # tiene 13 valores que son vicepresidencias mal-nombradas (level-shift S28). Vienen de la FUENTE
    # ÚNICA DE VERDAD (robustez_v02.ops.wells_attributes), que vive en OTRA BD y no se puede
    # JOIN-ear con core.* — se añaden al índice APARTE, en build_index(), con `gerencias_vigentes()`.
    # Mismo nivel "gerencia": el frontend ya lo rotula y los 4 consumidores de `puente` no cambian.
    ("operador",        "SELECT DISTINCT operador FROM core.dim_fuente          WHERE NULLIF(TRIM(operador),'') IS NOT NULL", "A"),
    ("vicepresidencia", "SELECT DISTINCT codigo   FROM core.dim_vicepresidencia WHERE NULLIF(TRIM(codigo),'')   IS NOT NULL", "A"),
    ("filial",          "SELECT DISTINCT nombre   FROM core.dim_empresa         WHERE NULLIF(TRIM(nombre),'')   IS NOT NULL", "B"),
]

_INDEX = None   # {nombre_norm: [ {nivel, rama, valor} ]}  · cache por proceso (reiniciar backend para refrescar)


def build_index():
    global _INDEX
    idx = {}
    eng = get_engine()
    # [2026-09-09 · BUG1-GERENCIAS] AUTOCOMMIT + try por consulta: una tabla ausente NO tumba el
    # índice entero (mismo patrón que maquina_q._nombres():519-545).
    with eng.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
        for nivel, sql, rama in _LEVELS:
            try:
                filas = list(c.execute(sa.text(sql)))
            except Exception:
                continue
            for (val,) in filas:
                k = norm(val)
                if not k:
                    continue
                ident = {"nivel": nivel, "rama": rama, "valor": (val or "").strip()}
                if ident not in idx.setdefault(k, []):   # idempotente: no duplicar identidades
                    idx[k].append(ident)
    # [2026-09-09 · BUG1-GERENCIAS] Gerencias REALES desde la FUENTE ÚNICA DE VERDAD. Van APARTE
    # del bucle porque viven en OTRA BD (robustez_v02) — mismo motivo y patrón que ranking.py:266.
    # Medido: 20 vigentes, todas con campos en INGESTA. Si ops no está, `gerencias_vigentes()`
    # devuelve [] y el índice queda como hoy.
    # 🔑 Mismo nivel "gerencia": un código presente en los dos catálogos (CPV/GAN/GNS/GXO) produce
    #    la MISMA identidad y el `if ident not in` la deduplica. No hay ambigüedad.
    for g in gerencias_vigentes():
        k = norm(g)
        if not k:
            continue
        ident = {"nivel": "gerencia", "rama": "A", "valor": g}
        if ident not in idx.setdefault(k, []):
            idx[k].append(ident)
    _INDEX = idx
    return idx


def get_index():
    return _INDEX if _INDEX is not None else build_index()


def resolver(texto: str) -> list[dict]:
    """Capa 1 exacta: identidades para el texto normalizado. [] si no hay match."""
    return list(get_index().get(norm(texto), []))


# Palabras funcionales que NO son entidades (evitan falsos positivos del backstop de n-gramas).
_STOP = {"QUE", "ES", "DE", "DEL", "LA", "EL", "LO", "LOS", "LAS", "UN", "UNA", "EN", "Y", "O",
         "A", "AL", "POR", "PARA", "CON", "SIN", "SU", "SUS", "PRODUCCION", "PRODUJO", "PRODUCE",
         "CUANTO", "CUANTA", "CUANTOS", "COMO", "CUAL", "CUALES", "DAME", "MUESTRAME", "MES",
         "CRUDO", "GAS", "BLANCOS", "BARRILES", "ABRIL", "MAYO", "MARZO", "ENERO", "FEBRERO"}


def buscar_en_texto(texto: str):
    """Backstop: escanea el texto por n-gramas (largos primero) contra el catálogo cerrado. Devuelve
    (gram, identidades) o None. Solo red de seguridad cuando no se recibió la entidad ya detectada."""
    idx = get_index()
    palabras = [p for p in (w.strip("¿?¡!.,;:()[]{}\"'`") for w in norm(texto).split()) if p]
    n = len(palabras)
    for size in range(min(n, 4), 0, -1):
        for start in range(0, n - size + 1):
            gram = " ".join(palabras[start:start + size])
            if size == 1 and gram in _STOP:
                continue
            hit = idx.get(gram)
            if hit:
                return gram, list(hit)
    return None


# --- Colapso por conjunto FÍSICO de fuente_id (fusiona colisiones redundantes: RUBIALES = campo=activo=fuente) ---
_FUENTE_COL = {"fuente": "nombre", "campo": "campo", "gerencia": "gerencia", "operador": "operador"}
_ACTIVO_KEY = "__activo__"
_FUENTE_SETS = None   # {col|__activo__: {nombre_norm: frozenset(fuente_id)}}


def _build_fuente_sets():
    global _FUENTE_SETS
    fs = {col: {} for col in _FUENTE_COL.values()}
    fs[_ACTIVO_KEY] = {}
    eng = get_engine()
    with eng.connect() as c:
        rows = c.execute(sa.text(
            "SELECT fuente_id, nombre, campo, gerencia, operador FROM core.dim_fuente")).all()
        campo2activo = {r[0]: r[1] for r in c.execute(sa.text(
            "SELECT campo_norm, activo FROM core.map_campo_activo"))}
    for r in rows:
        fid = r[0]
        for col, val in zip(_FUENTE_COL.values(), r[1:]):
            if val and str(val).strip():
                fs[col].setdefault(norm(val), set()).add(fid)
        campo = r[2]
        if campo and str(campo).strip():
            activo = campo2activo.get(norm(campo))
            if activo:
                fs[_ACTIVO_KEY].setdefault(norm(activo), set()).add(fid)
    _FUENTE_SETS = {col: {k: frozenset(v) for k, v in d.items()} for col, d in fs.items()}
    return _FUENTE_SETS


def _get_fuente_sets():
    return _FUENTE_SETS if _FUENTE_SETS is not None else _build_fuente_sets()


def clave_fisica(ident: dict):
    """Clave de identidad física para agrupar candidatos de una misma colisión (idéntica a v1)."""
    nivel, rama, valor = ident["nivel"], ident.get("rama"), ident["valor"]
    k = norm(valor)
    if rama == "B":
        return ("B", k)
    if nivel == "vicepresidencia":
        return ("VICE", k)
    if nivel == "activo":
        return ("F", _get_fuente_sets()[_ACTIVO_KEY].get(k, frozenset()))
    col = _FUENTE_COL.get(nivel)
    if not col:
        return (nivel, k)
    fset = _get_fuente_sets()[col].get(k, frozenset())
    # [2026-09-09 · BUG1-GERENCIAS] Una gerencia de la FUENTE DE VERDAD no está en dim_fuente →
    # conjunto físico VACÍO. Un campo homónimo de un tercero también → ambos caían en la misma
    # clave ('F', frozenset()), `_resolver_colision` veía UN grupo y devolvía "auto" ganando Campo.
    # El bloque de NIVEL EXPLÍCITO (resolver_unico, modo "ask") nunca se ejecutaba. Con clave
    # propia son 2 grupos → "ask" → el nivel explícito decide. Hoy no hay colisión real (medido),
    # pero la política queda correcta. GOR y las de dim_fuente conservan su ('F', {ids}).
    if nivel == "gerencia" and not fset:
        return ("GER_ROB", k)
    return ("F", fset)


# --- Prioridad de nivel al colapsar (Campo gana) — FORK de consulta/maquina.py ---
_PRIORIDAD = {"campo": 5, "activo": 3, "gerencia": 2, "fuente": 1, "pozo": 1}


def _rep(grupo):
    return max(grupo, key=lambda i: _PRIORIDAD.get(i["nivel"], 0))


def _resolver_colision(ids, clave_fn):
    """(modo, rep, reps): 'auto' = 1 conjunto físico (redundante); 'ask' = ≥2 (genuina)."""
    grupos = {}
    for i in ids:
        grupos.setdefault(clave_fn(i), []).append(i)
    reps = [_rep(g) for g in grupos.values()]
    if len(reps) == 1:
        return ("auto", reps[0], reps)
    return ("ask", None, reps)


def _prioridad_campo(reps):
    """D-D5: si entre los grupos físicos hay EXACTAMENTE un campo y ninguna filial (rama B), se
    responde directo como Campo. Devuelve (rep_campo|None, zoom_activos)."""
    if any(r.get("rama") == "B" for r in reps):
        return None, []
    campos = [r for r in reps if r["nivel"] == "campo"]
    if len(campos) != 1:
        return None, []
    return campos[0], [r for r in reps if r["nivel"] == "activo"]


# R2 (2026-08-03, HALLAZGO_clasificador_conteo_jerarquia.md §2.3): core.dim_fuente.gerencia NO es una
# lista pura de "gerencias reales" — varios de sus valores son, en la jerarquía oficial de robustez
# (core.map_campo_robustez), VICEPRESIDENCIAS mal-nombradas "gerencia" en el esquema fuente de INGESTA
# (mismo level-shift que respuesta_jerarquizar.py ya puentea — sesión S28). Verificado contra BD:
# de 17 valores, 8 son VP-robustez SIN ambigüedad (DFL/GAA/GCT/GOR/GPA/GRM/GTA/PRP); 3 (CPV/GAN/GXO)
# son AMBIGUOS (existen como VP *y* como gerencia real distinta en robustez — `rob_vicepresidencia ∩
# rob_gerencia`; NO se relabelean, mismo criterio de desempate "nivel más específico gana" que ya usa
# respuesta_jerarquizar._elegir); 6 no tienen match en robustez (terceros fuera de su universo
# ECP-operado, sin evidencia para corregir). La resta de conjuntos (vps - gers, abajo) calcula esto en
# VIVO — NO hardcodear la lista: si robustez cambia, el cálculo se actualiza solo.
_VP_ROBUSTEZ = None   # cache por proceso: {norm(codigo)} — SOLO los exclusivamente vicepresidencia


def _cargar_vp_robustez():
    global _VP_ROBUSTEZ
    if _VP_ROBUSTEZ is not None:
        return _VP_ROBUSTEZ
    try:
        eng = get_engine()
        with eng.connect() as c:
            vps = set(v for (v,) in c.execute(sa.text(
                "SELECT DISTINCT rob_vicepresidencia FROM core.map_campo_robustez "
                "WHERE rob_vicepresidencia IS NOT NULL")))
            gers = set(v for (v,) in c.execute(sa.text(
                "SELECT DISTINCT rob_gerencia FROM core.map_campo_robustez "
                "WHERE rob_gerencia IS NOT NULL")))
    except Exception:
        _VP_ROBUSTEZ = set()   # degradación con gracia: sin evidencia -> no relabel (nunca lanza)
        return _VP_ROBUSTEZ
    _VP_ROBUSTEZ = {norm(v) for v in (vps - gers) if v}   # excluye ambiguos (CPV/GAN/GXO hoy)
    return _VP_ROBUSTEZ


# --- GERENCIAS REALES desde la FUENTE ÚNICA DE VERDAD (BUG1-GERENCIAS, 2026-09-09) ------------
# 🔴 FUENTE: robustez_v02, esquema ops, tabla wells_attributes. NO `core.map_campo_robustez`
#    (COPIA que diverge: le sobran 6 de la rama vieja V*, le faltan CPI y GNS, y pierde
#    CASTILLA ESTE en PPC — medido el 2026-09-09).
# ⚠️ LOS DOS FILTROS SON OBLIGATORIOS, copiados de ranking.py:277-279 (medidos el 2026-09-03):
#      1. `vice_presidency NOT LIKE 'V%'` — conviven DOS jerarquías; la rama V* es la VIEJA.
#      2. `vice_presidency <> '0'`        — filas basura que duplican campos.
#    Con ellos: 20 gerencias vigentes, las 20 con campos en INGESTA.
# 🔑 Vive en OTRA BD (get_ops_engine): se lee aparte y se cruza en Python (ranking.py:264-267).
# 🔑 Degradación con gracia: sin ops (p.ej. el 139) devuelve vacío y las gerencias no resuelven —
#    el comportamiento de HOY. Nunca lanza. Los errores NO se cachean; un resultado legítimo SÍ.
_GER_CAMPOS = None   # cache por proceso: {norm(gerencia): [campo, ...]}
_GER_CANON = None    # cache por proceso: {norm(gerencia): nombre canónico}  (norm pliega la ñ:
                     # PPÑ -> PPN, y el usuario debe leer «PPÑ», no «PPN»)

_SQL_GER_CAMPOS = """
    SELECT TRIM(management) AS ger, TRIM(field) AS campo
    FROM ops.wells_attributes
    WHERE NULLIF(TRIM(management),'') IS NOT NULL
      AND NULLIF(TRIM(field),'') IS NOT NULL
      AND vice_presidency NOT LIKE 'V%'
      AND vice_presidency <> '0'
    GROUP BY 1, 2
"""


def _cargar_ger_campos():
    global _GER_CAMPOS, _GER_CANON
    if _GER_CAMPOS is not None:
        return _GER_CAMPOS
    try:
        from app.core.db import get_ops_engine
        with get_ops_engine().connect() as c:
            filas = c.execute(sa.text(_SQL_GER_CAMPOS)).all()
    except Exception:
        return {}   # ops no disponible → sin cachear: el fallo puede ser transitorio
    d, canon = {}, {}
    for ger, campo in filas:
        k = norm(ger)
        d.setdefault(k, []).append((campo or "").strip())
        canon.setdefault(k, (ger or "").strip())   # el nombre TAL COMO lo escribe la fuente
    _GER_CAMPOS = {k: sorted(set(v)) for k, v in d.items()}
    _GER_CANON = canon
    return _GER_CAMPOS


def gerencias_vigentes() -> list[str]:
    """Nombres CANÓNICOS de las gerencias vigentes en la fuente de verdad. [] si ops no está.

    Lo consumen `build_index()` y `maquina_q._nombres()` — UN solo catálogo para el motor.
    """
    _cargar_ger_campos()
    return sorted((_GER_CANON or {}).values())


def campos_de_gerencia(gerencia: str) -> list[str]:
    """Campos que componen una GERENCIA REAL, según ops.wells_attributes. [] si no existe.

    Fuente única de la composición: la usa también `analisis._ambito`, para que el tablero y la
    conversación no puedan divergir (mismo criterio que `fuentes_de_activo`).
    """
    return list(_cargar_ger_campos().get(norm(gerencia or ""), []))


def _marcar_puente(r: dict) -> dict:
    """R2: si el nivel resuelto es 'gerencia' pero el valor es EXCLUSIVAMENTE una vicepresidencia en
    robustez, marca r['puente']=True. El nivel de QUERY (r['nivel']) NO se toca — solo afecta cómo se
    ROTULA la entidad en el texto (ver ejecutor._etiqueta_nivel). Muta y devuelve `r`."""
    if r.get("nivel") == "gerencia" and norm(r["valor"]) in _cargar_vp_robustez():
        r["puente"] = True
    return r


# --- Nivel EXPLÍCITO en el texto (bug 2 de jerarquias_sup_error.md, 2026-09-03) --------------
# El usuario que escribe «el activo CASTILLA» YA desambiguó: pedirle que lo repita sería no
# escucharlo (decisión del usuario, 2026-09-03). Hasta hoy esa palabra no entraba en la
# decisión —grep: cero `nivel_pedido` en todo consulta_v2— y D-D5 respondía el campo homónimo.
# Medido: el activo APIAY agrupa 13 campos y la respuesta entregaba 1.
#
# 🔑 EXIGE ADYACENCIA (nivel + nombre), no la mera presencia de la palabra: 'ACTIVO' es
# vocabulario estructural y adjetivo común. Sin esto se tragaría «¿qué campos tiene el activo
# Castilla?» (que es JERARQUIZAR) y «el pozo activo».
# 🔑 NO altera D-D5 (_prioridad_campo): actúa ANTES y solo cuando hay señal explícita. Sin
# señal, el default sigue siendo Campo — que es la decisión del usuario del 2026-07-15,
# vigilada por tests/test_cuantificar.py:22 y tests/test_consulta_desambiguacion.py:46.
# [2026-09-09 · BUG1-GERENCIAS] Se añade GERENCIA con la MISMA adyacencia (nivel + nombre) del
# diseño del 2026-09-03: sin ella, «¿cuántas gerencias tiene la VP GOR?» (JERARQUIZAR) se
# etiquetaría por error. El orden se conserva: ACTIVO primero; `_nivel_explicito` devuelve en el
# primer match.
_NIVEL_EXPLICITO_RX = (
    (re.compile(r"\b(?:EL|LA|LOS|LAS)?\s*ACTIVOS?\s+", re.I), "activo"),
    (re.compile(r"\b(?:EL|LA|LOS|LAS)?\s*CAMPOS?\s+", re.I), "campo"),
    (re.compile(r"\b(?:EL|LA|LOS|LAS)?\s*GERENCIAS?\s+", re.I), "gerencia"),
)


def _nivel_explicito(texto: str):
    """Nivel que el usuario nombró justo antes de la entidad, o None.

    Devuelve 'activo' | 'campo' | None. Solo mira el TEXTO; que ese nivel exista de verdad
    para la entidad lo comprueba quien llama (no se fuerza un nivel inexistente).
    """
    t = norm(texto or "")
    for rx, nivel in _NIVEL_EXPLICITO_RX:
        if rx.search(t):
            return nivel
    return None


def resolver_unico(texto: str, contexto: str | None = None) -> dict | None:
    """Resuelve el texto a UNA identidad {nivel, valor, rama, zoom?} aplicando la política de v1:
      - sin match            -> None
      - 1 identidad          -> esa
      - colisión redundante  -> auto (representante Campo)
      - colisión con Campo    -> D-D5 Campo directo (+ zoom a Activo si existe)
      - colisión genuina/dual -> {"ambiguo": [reps]} (desambiguación = sub-fase posterior)

    `contexto` = la PREGUNTA ORIGINAL, cuando `texto` es solo el nombre ya extraído.
    [2026-09-03] Sin esto el detector de nivel explícito quedaba CIEGO en la app real: los
    llamadores hacen `resolver_unico(entidad or texto)` y `maquina_q.detectar_entidad` ya
    redujo «¿Producción del Activo CASTILLA?» a «CASTILLA» — la palabra «activo» se perdía
    antes de llegar aquí (medido en Pruebas: respondía «el Campo CASTILLA»). OPCIONAL a
    propósito: sin él el comportamiento es idéntico al anterior, así que ningún llamador ni
    test que pase un solo argumento se rompe.
    """
    ids = resolver(texto)
    if not ids:                       # no fue match exacto (¿vino el texto entero?) → escanear n-gramas
        hit = buscar_en_texto(texto)
        if hit:
            ids = hit[1]
    if not ids:
        return None
    nivel_pedido = _nivel_explicito(contexto or texto)
    if len(ids) == 1:
        r = dict(ids[0]); r["zoom"] = []
        return _marcar_puente(r)
    modo, rep, reps = _resolver_colision(ids, clave_fisica)
    zoom = []
    if modo == "ask":
        # (1) NIVEL EXPLÍCITO gana sobre D-D5: el usuario ya dijo cuál quiere. Solo si ese
        #     nivel existe de verdad entre los candidatos (H9) — nunca se fuerza uno ausente.
        elegido = ([r for r in reps if r["nivel"] == nivel_pedido] if nivel_pedido else [])
        if len(elegido) == 1:
            modo, rep = "auto", elegido[0]
            zoom = [r for r in reps if r is not elegido[0]]
        else:
            # (2) sin señal explícita -> D-D5 intacta (default Campo, decisión 2026-07-15)
            rep_campo, zoom = _prioridad_campo(reps)
            if rep_campo is not None:
                modo, rep = "auto", rep_campo
    if modo == "auto":
        r = dict(rep); r["zoom"] = zoom
        return _marcar_puente(r)
    return {"ambiguo": reps}
