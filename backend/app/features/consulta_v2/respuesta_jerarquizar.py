"""respuesta_jerarquizar.py — respuesta del grupo JERARQUIZAR (Motor Q v2).

Fuente de verdad de la jerarquía = core.map_campo_robustez (reconciliación robustez ↔ reporte
diario, bitácora S28). Robustez manda:  vicepresidencia → gerencia (management) → activo → campo.

OPCIÓN A (decisión del usuario 2026-08-02) para el LEVEL-SHIFT: el usuario, con la cabeza en el
reporte diario, dice "gerencia GOR"; pero en la estructura oficial GOR es una Vicepresidencia (la
gerencia real es POE/PPC…). Se responde con la verdad de robustez RECONOCIENDO su término — educa
sin negar la pregunta. 🔑 El término del usuario = SOLO la palabra inmediatamente anterior a la
entidad ("la gerencia GOR"); un nivel que aparezca en otra parte ("¿a qué ACTIVO pertenece Cajúa?")
se refiere al PADRE buscado, no a la entidad → no dispara el puente.

DETERMINISTA, SIN LLM (mismo principio que meta.py de v1): la respuesta ES la lista de hechos del
catálogo. No hay nada que "redactar"; un modelo pequeño solo podría inventar relaciones falsas.
Reusa solo la capa de datos (get_engine, norm). Texto plano para la burbuja (como respuesta_out).

Alcance: campo/activo/gerencia/vicepresidencia (+ operador para terceros). El CONTEO de pozos SÍ vive
aquí (R3, 2026-08-03): COUNT(DISTINCT uwi) sobre robustez_v02.ops.wells_attributes por los rob_field
del nivel (get_ops_engine, cross-DB). Degrada con gracia: si ops no está (p.ej. 139 sin robustez_v02),
se omite la línea de pozos y la estructura sigue intacta.
"""
import sqlalchemy as sa

from app.core.config import get_settings
from app.core.db import get_engine, get_ops_engine
from app.features.consulta_v2 import respuesta_base
from app.features.consulta_v2.normaliza import norm

# --- Envoltorio cordial (B): el LLM escribe SOLO el marco (intro + cierre); los hechos van
# verbatim desde Python → no puede corromper el catálogo (la lección de meta.py de v1). Delega en
# respuesta_base (compartido con cuantificar) — ver _intro_llm/_envolver más abajo. -----------------
_s = get_settings()

# El LLM escribe SOLO el intro (calidez dinámica). El CIERRE lo arma Python (Python decide la
# acción → nunca inventa, y coincide EXACTO con lo que la memoria sabe resolver). qwen, con libertad
# en el cierre, inventó "producción de GNL" — por eso el cierre no es del LLM.
PROMPT_ENV = """Eres el asistente de producción de hidrocarburos de Ecopetrol: cordial, cercano y natural.
Voy a mostrar unos HECHOS sobre la entidad {entidad} ({nivel}) — se muestran aparte, NO los repitas.
Escribe UNA sola frase de presentación, cálida y BREVE, en español, del tipo "Claro, aquí tienes…".
Usa a veces el nombre del usuario ({usuario}). Varía el fraseo.
NO describas la entidad ni digas qué hace o de qué se encarga; NO des ningún dato; NO prometas nada. Solo saluda y anuncia que aquí están los datos.
Responde SOLO con JSON válido: {{"intro": "..."}}"""

# Palabras funcionales que NO son entidades (evitan falsos positivos del escaneo por n-gramas).
_STOP = {"QUE", "ES", "DE", "DEL", "LA", "EL", "LO", "LOS", "LAS", "UN", "UNA", "EN", "Y", "O",
         "A", "AL", "POR", "PARA", "CON", "SIN", "SU", "SUS", "SE", "CUAL", "CUALES", "CUANTOS",
         "CUANTAS", "TIENE", "TIENEN", "CONFORMAN", "PERTENECE", "PERTENECEN", "COMPONE",
         "COMPONEN", "AGRUPA", "DAME", "MUESTRAME", "ESTRUCTURA", "COMPLETA", "INFORMACION",
         "TIPO", "ENTIDAD", "CAMPO", "CAMPOS", "ACTIVO", "ACTIVOS", "GERENCIA", "GERENCIAS",
         "POZO", "POZOS", "VICEPRESIDENCIA", "VP", "VICE", "FILIAL"}

_ORDEN = {"campo": 0, "activo": 1, "gerencia": 2, "vicepresidencia": 3, "operador": 4}
_ART = {"campo": "el Campo", "activo": "el Activo", "gerencia": "la Gerencia",
        "vicepresidencia": "la Vicepresidencia", "operador": "el operador"}

# Palabra que precede a la entidad -> nivel con que el usuario la etiquetó (para el puente A).
_PAL_NIVEL = {"VICEPRESIDENCIA": "vicepresidencia", "VICE": "vicepresidencia", "VP": "vicepresidencia",
              "GERENCIA": "gerencia", "GERENCIAS": "gerencia", "ACTIVO": "activo", "ACTIVOS": "activo",
              "CAMPO": "campo", "CAMPOS": "campo", "POZO": "pozo", "POZOS": "pozo"}

_DATA = None   # cache por proceso (como _INDEX del resolver)


def _cargar():
    """Carga core.map_campo_robustez y arma los índices. Lanza si la tabla no existe
    (el llamador lo captura y deja el mensaje 'en construcción')."""
    global _DATA
    if _DATA is not None:
        return _DATA
    idx = {}            # norm(nombre) -> set((nivel, canonico))
    campo_row = {}      # norm(campo)  -> {campo, operador, es_ecp, activo, gerencia, vp}
    act_campos, ger_campos, vp_campos, op_campos = {}, {}, {}, {}
    ger_activos, vp_ger, vp_activos = {}, {}, {}
    # R3: rob_field por nivel (para COUNT(DISTINCT uwi) en robustez_v02). El rob_field es la clave de
    # join con ops.wells_attributes.field (verificado: rob_field==field).
    act_fields, ger_fields, vp_fields = {}, {}, {}
    eng = get_engine()
    with eng.connect() as c:
        rows = c.execute(sa.text("""
            SELECT campo, operador, es_ecp, rob_field, rob_activo, rob_gerencia, rob_vicepresidencia
            FROM core.map_campo_robustez""")).mappings().all()

    def _add(d, k, v):
        d.setdefault(k, []).append(v)

    for r in rows:
        campo = (r["campo"] or "").strip()
        op = (r["operador"] or "").strip()
        rf = (r["rob_field"] or "").strip()
        act = (r["rob_activo"] or "").strip()
        ger = (r["rob_gerencia"] or "").strip()
        vp = (r["rob_vicepresidencia"] or "").strip()
        kc = norm(campo)
        campo_row[kc] = {"campo": campo, "operador": op, "es_ecp": bool(r["es_ecp"]),
                         "rob_field": rf or None,
                         "activo": act or None, "gerencia": ger or None, "vp": vp or None}
        idx.setdefault(kc, set()).add(("campo", campo))
        if op:
            idx.setdefault(norm(op), set()).add(("operador", op))
            _add(op_campos, norm(op), campo)
        if act:
            idx.setdefault(norm(act), set()).add(("activo", act))
            _add(act_campos, norm(act), campo)
            if rf:
                act_fields.setdefault(norm(act), set()).add(rf)
        if ger:
            idx.setdefault(norm(ger), set()).add(("gerencia", ger))
            _add(ger_campos, norm(ger), campo)
            if act:
                ger_activos.setdefault(norm(ger), set()).add(act)
            if rf:
                ger_fields.setdefault(norm(ger), set()).add(rf)
        if vp:
            idx.setdefault(norm(vp), set()).add(("vicepresidencia", vp))
            _add(vp_campos, norm(vp), campo)
            if ger:
                vp_ger.setdefault(norm(vp), set()).add(ger)
            if act:
                vp_activos.setdefault(norm(vp), set()).add(act)
            if rf:
                vp_fields.setdefault(norm(vp), set()).add(rf)

    _DATA = {"idx": idx, "campo_row": campo_row, "act_campos": act_campos,
             "ger_campos": ger_campos, "vp_campos": vp_campos, "op_campos": op_campos,
             "ger_activos": ger_activos, "vp_ger": vp_ger, "vp_activos": vp_activos,
             "act_fields": act_fields, "ger_fields": ger_fields, "vp_fields": vp_fields}
    return _DATA


def _y(items):
    """Enumeración natural: 'A', 'A y B', 'A, B y C'."""
    items = sorted(set(items))
    if len(items) <= 1:
        return items[0] if items else ""
    return ", ".join(items[:-1]) + " y " + items[-1]


def _lista(items, tope=14):
    """Enumera si son pocos; si son muchos, cuenta + muestra los primeros."""
    items = sorted(set(items))
    if len(items) <= tope:
        return _y(items)
    return "%d en total (%s…)" % (len(items), ", ".join(items[:tope]))


def _detectar(texto):
    """Entidad de la jerarquía en el texto (n-gramas, más largos primero).
    Devuelve (key, niveles, palabra_previa) o None. palabra_previa = token justo antes de la
    entidad (para saber cómo la etiquetó el usuario)."""
    data = _cargar()
    idx = data["idx"]
    palabras = [p for p in (w.strip("¿?¡!.,;:()[]{}\"'`") for w in norm(texto).split()) if p]
    n = len(palabras)
    for size in range(min(n, 4), 0, -1):
        for start in range(0, n - size + 1):
            gram = " ".join(palabras[start:start + size])
            if size == 1 and gram in _STOP:
                continue
            if gram in idx:
                prev = palabras[start - 1] if start > 0 else None
                return gram, idx[gram], prev
    return None


def _label_previo(prev):
    """Nivel con que el usuario ETIQUETÓ la entidad = SOLO la palabra inmediatamente anterior."""
    return _PAL_NIVEL.get(prev) if prev else None


def _elegir(niveles, palabra):
    """Escoge el nivel a responder. Devuelve (nivel_real, canonico, palabra_puente|None).
    Si el usuario etiquetó un nivel distinto al real (level-shift) → palabra_puente activa la copia A."""
    d = {niv: canon for niv, canon in niveles}
    if palabra and palabra in d:
        return palabra, d[palabra], None
    niv = min(d, key=lambda x: _ORDEN[x])         # el más específico disponible
    puente = palabra if (palabra and palabra not in d and palabra != "pozo") else None
    return niv, d[niv], puente


def _padres(campos, data):
    """Gerencias y VPs de un conjunto de campos (un activo puede colgar de >1 gerencia)."""
    gers, vps = set(), set()
    for cc in campos:
        row = data["campo_row"].get(norm(cc), {})
        if row.get("gerencia"):
            gers.add(row["gerencia"])
        if row.get("vp"):
            vps.add(row["vp"])
    return gers, vps


def _bloque(header, lineas):
    """Bloque multilínea: encabezado + viñetas (una por relación). '\\n' → salto de línea en la
    burbuja (la CSS de .v2-msg usa white-space: pre-line)."""
    body = "\n".join("• " + l for l in lineas if l)
    return header + "\n" + body if body else header


def _uno_o_varios(sing, plu, conj):
    """'Gerencia: X' si hay uno; 'Gerencias: X y Y' si hay varios; '' si no hay."""
    conj = sorted(set(conj))
    if not conj:
        return None
    return f"{sing}: {conj[0]}" if len(conj) == 1 else f"{plu}: {_y(conj)}"


def _contar_pozos(rob_fields):
    """COUNT(DISTINCT uwi) en robustez_v02.ops.wells_attributes para los rob_field dados, o None.
    None = no hay fields (terceros sin robustez) o `ops` no está disponible (p.ej. 139 sin
    robustez_v02) → el llamador OMITE la línea de pozos (degradación con gracia). NUNCA lanza.
    🔑 COUNT(DISTINCT uwi) dedup automático → nunca suma subconteos (747 uwi en >1 campo). Se cuenta
    por rob_field (jerarquía canónica de map_campo_robustez), NO por las columnas aliaseadas de
    wells_attributes (verificado: difieren)."""
    fields = sorted({f for f in (rob_fields or set()) if f})
    if not fields:
        return None
    try:
        with get_ops_engine().connect() as c:
            return c.execute(sa.text(
                "SELECT COUNT(DISTINCT uwi) FROM ops.wells_attributes WHERE field = ANY(:fs)"),
                {"fs": fields}).scalar()
    except Exception:
        return None


def rob_fields_de(nivel, canonical):
    """Conjunto de rob_field (campos ECP) que cuelgan de `canonical` en ese `nivel`.

    [2026-08-25] QV2-MAPA. Extraído para que el endpoint del mapa resuelva la MISMA
    jerarquía que el árbol — sin esto tendría que reconstruirla y las dos vistas podrían
    divergir. Reusa los índices que _cargar() ya construye (act_fields/ger_fields/vp_fields,
    :76-126), los mismos que consume _contar_pozos.

    set() vacío si el nivel no aplica o la tabla no está: el llamador omite el mapa.
    """
    try:
        data = _cargar()
    except Exception:
        return set()
    k = norm(canonical or "")
    if nivel == "campo":
        row = data["campo_row"].get(k) or {}
        rf = row.get("rob_field")
        return {rf} if rf else set()
    if nivel == "activo":
        return set(data["act_fields"].get(k, set()))
    if nivel == "gerencia":
        return set(data["ger_fields"].get(k, set()))
    if nivel == "vicepresidencia":
        return set(data["vp_fields"].get(k, set()))
    return set()          # operador y otros: sin mapa


# ═══════════════════════════════════════════════════════════════════════════════════════════════
# RANKING ESTRUCTURAL (2026-08-04, plan_jerarquizar_ranking_2026-08-04.md)
# Ordena entidades por conteo (pozos/gerencias/activos/campos). Eje ORTOGONAL al N5 de Cuantificar
# (que rankea por producción). DETERMINISTA salvo el intro cordial. Reusa los mapas de _cargar().
# ═══════════════════════════════════════════════════════════════════════════════════════════════
# 🔑 Vocabulario SIMÉTRICO (defecto del v1: tenía GRANDE/GRANDES pero ningún antónimo → "los campos
# más pequeños" devolvía None y moría en "¿sobre cuál?").
# ⚠️ VERIFICADO 2026-08-04: norm() PLIEGA la ñ → N ('pequeños' -> 'PEQUENOS', 'Caño' -> 'CANO').
# Por eso aquí SOLO van las formas con N. Escribir "PEQUEÑOS" sería código muerto (nunca matchea).
_RANK_SUP = ("MAS", "MAYOR", "MENOS", "MENOR", "GRANDE", "GRANDES",
             "PEQUENO", "PEQUENOS", "PEQUENA", "PEQUENAS", "CHICO", "CHICOS")
# Dirección ASCENDENTE (el "menos"). Incluye los antónimos de tamaño: "los campos más pequeños" =
# los de MENOS pozos. Si el texto trae "MAS" y "PEQUENOS", manda el antónimo (ver _rank_detectar).
_RANK_ASC = ("MENOS", "MENOR", "PEQUENO", "PEQUENOS", "PEQUENA", "PEQUENAS", "CHICO", "CHICOS")
_RANK_NIVEL = {"CAMPO": "campo", "CAMPOS": "campo", "ACTIVO": "activo", "ACTIVOS": "activo",
               "GERENCIA": "gerencia", "GERENCIAS": "gerencia", "VP": "vicepresidencia",
               "VICE": "vicepresidencia", "VICEPRESIDENCIA": "vicepresidencia",
               "VICEPRESIDENCIAS": "vicepresidencia"}
_RANK_CONTEO = {"POZO": "pozos", "POZOS": "pozos", "CAMPO": "campos", "CAMPOS": "campos",
                "ACTIVO": "activos", "ACTIVOS": "activos", "GERENCIA": "gerencias",
                "GERENCIAS": "gerencias"}
# subject -> (conteo por defecto para "grande", conteos SOPORTADOS en v1)
_RANK_MATRIZ = {
    "campo": ("pozos", {"pozos"}),
    "activo": ("campos", {"campos"}),                       # pozos DIFERIDO (doble conteo)
    "gerencia": ("campos", {"campos", "activos"}),          # pozos DIFERIDO
    "vicepresidencia": ("gerencias", {"gerencias", "activos", "campos"}),   # pozos DIFERIDO
}
# (subject, conteo) -> clave del mapa en memoria (data[...]). Solo conteos estructurales.
_RANK_MAP = {
    ("activo", "campos"): "act_campos",
    ("gerencia", "campos"): "ger_campos",
    ("gerencia", "activos"): "ger_activos",
    ("vicepresidencia", "gerencias"): "vp_ger",
    ("vicepresidencia", "activos"): "vp_activos",
    ("vicepresidencia", "campos"): "vp_campos",
}
_RANK_PLURAL = {"campo": "campos", "activo": "activos", "gerencia": "gerencias",
                "vicepresidencia": "vicepresidencias"}
# Contracción correcta para el mensaje de combo inválido ("de el campo" ✗ / "del campo" ✓).
_RANK_DE = {"campo": "del campo", "activo": "del activo", "gerencia": "de la gerencia",
            "vicepresidencia": "de la vicepresidencia"}
_RANK_POZOS_DIFERIDO = ("El conteo de pozos por activo/gerencia/vicepresidencia llega en una próxima "
                        "fase: un mismo pozo puede estar asignado a más de un campo, así que sumar los "
                        "conteos por campo daría un número inflado. Sí puedo rankear campos por pozos, o "
                        "activos/gerencias/vicepresidencias por número de campos, activos o gerencias.")


def _rank_detectar(texto):
    """Reconoce la FORMA de un ranking estructural (determinista, sin BD). dict o None.
    dict = {subject, conteo, asc, top_n, soportados, default}. Exige un SUPERLATIVO y un sustantivo
    de NIVEL antes de él (el sujeto). El conteo = sustantivo tras el superlativo, o el default del
    nivel ("campos más grandes" -> pozos)."""
    palabras = [p for p in (w.strip("¿?¡!.,;:()[]{}\"'`") for w in norm(texto or "").split()) if p]
    sup_i = next((i for i, w in enumerate(palabras) if w in _RANK_SUP), None)
    if sup_i is None:
        return None
    # SUJETO = sustantivo de nivel MÁS CERCANO antes del superlativo.
    subj, subj_tok = None, None
    for i in range(sup_i - 1, -1, -1):
        if palabras[i] in _RANK_NIVEL:
            subj, subj_tok = _RANK_NIVEL[palabras[i]], palabras[i]
            break
    if subj is None:
        return None
    # CONTEO = primer sustantivo de conteo tras el superlativo; si no hay -> default del nivel.
    conteo = next((_RANK_CONTEO[palabras[i]] for i in range(sup_i + 1, len(palabras))
                   if palabras[i] in _RANK_CONTEO), None)
    default, soportados = _RANK_MATRIZ[subj]
    if conteo is None:
        conteo = default
    # 🔑 asc = CUALQUIER palabra ascendente del texto, no solo la del índice sup_i. "los campos más
    # pequeños" trae MAS (sup_i, descendente) y PEQUENOS (ascendente): manda el antónimo, si no
    # devolvería los MÁS grandes ante una pregunta por los más pequeños (fallo silencioso).
    asc = any(w in _RANK_ASC for w in palabras)
    top_n = 1 if (subj_tok and not subj_tok.endswith("S")) else 5   # singular -> 1, plural -> 5
    return {"subject": subj, "conteo": conteo, "asc": asc, "top_n": top_n,
            "soportados": soportados, "default": default}


def _rank_canon(data, knorm, nivel):
    """Nombre canónico de una entidad a partir de su clave normalizada + nivel (via idx)."""
    for niv, canon in data["idx"].get(knorm, ()):
        if niv == nivel:
            return canon
    return knorm


def _rank_pozos_por_campo(data):
    """{rob_field: nº de pozos} desde ops.wells_attributes, sobre los rob_field de map_campo_robustez
    (universo ECP reconciliado). None si ops no está disponible (degradación con gracia, como
    _contar_pozos). El rob_field == field == nombre del campo ECP (verificado)."""
    fields = sorted({r["rob_field"] for r in data["campo_row"].values() if r.get("rob_field")})
    if not fields:
        return None
    try:
        with get_ops_engine().connect() as c:
            rows = c.execute(sa.text(
                "SELECT field, COUNT(DISTINCT uwi) FROM ops.wells_attributes "
                "WHERE field = ANY(:fs) GROUP BY field"), {"fs": fields}).all()
    except Exception:
        return None
    return {(f or "").strip(): int(n) for f, n in rows if f}


def _rank_conteo_estructural(subject, conteo, data):
    """{nombre_canónico: nº de hijos} desde los mapas ya en memoria (act_campos/ger_*/vp_*).
    Sin BD, sin doble conteo (los hijos son distintos por construcción del mapa)."""
    key = _RANK_MAP.get((subject, conteo))
    src = data.get(key) or {}
    return {_rank_canon(data, knorm, subject): len(set(children)) for knorm, children in src.items()}


def _rank_calcular(rk, data):
    """Contrato de ranking (aplica=True) o {aplica:False, texto}."""
    subj, conteo = rk["subject"], rk["conteo"]
    if conteo not in rk["soportados"]:
        if conteo == "pozos" and subj != "campo":
            return {"aplica": False, "texto": _RANK_POZOS_DIFERIDO}
        # Gramática: _ART da "el Campo" → "de el campo" es incorrecto. _RANK_DE da la contracción.
        return {"aplica": False, "texto": (
            f"No puedo rankear {_RANK_PLURAL[subj]} por número de {conteo}: {conteo} no es una "
            f"subdivisión {_RANK_DE[subj]}.")}
    if subj == "campo":                          # conteo == "pozos"
        conteos = _rank_pozos_por_campo(data)
        if conteos is None:
            return {"aplica": False, "texto": (
                "El conteo de pozos requiere la base de robustez (robustez_v02), que no está "
                "disponible ahora; no puedo construir ese ranking.")}
    else:
        conteos = _rank_conteo_estructural(subj, conteo, data)
    conteos = {k: v for k, v in conteos.items() if k}
    if not conteos:
        return {"aplica": False, "texto": f"No tengo datos para rankear {_RANK_PLURAL[subj]} por {conteo}."}
    items = sorted(conteos.items(), key=lambda kv: (kv[1], kv[0]), reverse=not rk["asc"])
    top = items[:rk["top_n"]]
    return {"aplica": True, "subject": subj, "conteo": conteo, "asc": rk["asc"],
            "items": [{"pos": i + 1, "entidad": k, "n": v} for i, (k, v) in enumerate(top)],
            "total": len(conteos)}


def _rank_cuerpo(res):
    """Cuerpo VERBATIM del ranking (el LLM no lo toca)."""
    subj_pl = _RANK_PLURAL[res["subject"]]
    n = len(res["items"])
    encab = "El" if n == 1 else "Los"
    subj_txt = subj_pl[:-1] if n == 1 else subj_pl        # campos->campo, vicepresidencias->vicepresidencia
    dir_txt = "menos" if res["asc"] else "más"
    piezas = "\n".join(f"{it['pos']}) {it['entidad']} ({it['n']})" for it in res["items"])
    linea = f"{encab} {subj_txt} con {dir_txt} {res['conteo']}:\n{piezas}"
    linea += f"\nSobre {res['total']} {subj_pl} ECP-operados con datos en la fuente oficial (robustez)."
    if res["conteo"] == "pozos":
        linea += " El conteo de pozos es de REGISTRO (atemporal), no de producción del mes."
    return linea


def _rank_oferta(res):
    top1 = res["items"][0]["entidad"] if res["items"] else None
    return (f"ver la estructura de {top1} o rankear por otra medida" if top1
            else "rankear por otra medida")


def _cuerpo(niv, canonical, data):
    """→ (texto, hechos). `texto` es EXACTAMENTE el mismo string que antes (nadie lo reordena ni
    lo recorta) — `hechos` es la MISMA información ya estructurada, para que el panel (1e) no
    tenga que recalcular nada (en particular, JAMÁS vuelve a llamar _contar_pozos: no tiene caché
    y consulta otra BD, robustez_v02, cross-DB — ver regla no negociable en maquina_q).
    `hechos["padres"]`: lista ASCENDENTE (vicepresidencia → … → el nivel justo encima de la
    entidad) de {"nivel","items"} — un nivel puede tener VARIOS padres (un activo puede colgar de
    >1 gerencia, docstring de _padres), de ahí `items` en plural.
    `hechos["hijos_grupos"]`: lista de {"nivel","items","es_hermanos"} — gerencia y vicepresidencia
    muestran MÁS DE UN grupo de hijos a la vez en el texto (p.ej. una VP lista Gerencias, Activos Y
    Campos simultáneamente), así que es una LISTA, no un único grupo."""
    cr = data["campo_row"]
    if niv == "campo":
        row = cr[norm(canonical)]
        if not row["es_ecp"] and not row["activo"]:
            texto = _bloque(f"«{canonical}» · Campo", [
                f"Operador: {row['operador']} (tercero)",
                "Fuera de la estructura económica de ECP: sin activo, gerencia ni "
                "vicepresidencia en la fuente oficial.",
            ])
            hechos = {"padres": [], "hijos_grupos": [], "pozos": None,
                      "operador": row["operador"], "fuera_estructura": True}
            return texto, hechos
        act = row["activo"]
        hermanos = [c for c in data["act_campos"].get(norm(act or ""), [])
                    if norm(c) != norm(canonical)]
        lineas = []
        if act:
            lineas.append(f"Activo: {act}")
        if row["gerencia"]:
            lineas.append(f"Gerencia: {row['gerencia']}")
        if row["vp"]:
            lineas.append(f"Vicepresidencia: {row['vp']}")
        if act:
            lineas.append(f"Otros campos del Activo {act}: "
                          f"{_lista(hermanos) if hermanos else 'ninguno (es el único)'}")
        npz = _contar_pozos({row.get("rob_field")})
        if npz is not None:
            lineas.append(f"Pozos: {npz}")
        texto = _bloque(f"«{canonical}» · Campo", lineas)
        # hechos en orden ASCENDENTE (vp->gerencia->activo) — el texto de arriba NO cambia de orden.
        padres = []
        if row["vp"]:
            padres.append({"nivel": "vicepresidencia", "items": [row["vp"]]})
        if row["gerencia"]:
            padres.append({"nivel": "gerencia", "items": [row["gerencia"]]})
        if act:
            padres.append({"nivel": "activo", "items": [act]})
        hijos_grupos = [{"nivel": "campo", "items": hermanos, "es_hermanos": True}] if act else []
        hechos = {"padres": padres, "hijos_grupos": hijos_grupos, "pozos": npz,
                  "operador": row["operador"] or None, "fuera_estructura": False}
        return texto, hechos

    if niv == "activo":
        campos = data["act_campos"][norm(canonical)]
        gers, vps = _padres(campos, data)
        npz = _contar_pozos(data["act_fields"].get(norm(canonical), set()))
        lineas = [
            _uno_o_varios("Gerencia", "Gerencias", gers),
            _uno_o_varios("Vicepresidencia", "Vicepresidencias", vps),
            f"Campos ({len(set(campos))}): {_lista(campos)}",
            f"Pozos: {npz}" if npz is not None else None,
        ]
        texto = _bloque(f"«{canonical}» · Activo", lineas)
        padres = []
        if vps:
            padres.append({"nivel": "vicepresidencia", "items": sorted(vps)})
        if gers:
            padres.append({"nivel": "gerencia", "items": sorted(gers)})
        hijos_grupos = [{"nivel": "campo", "items": list(set(campos)), "es_hermanos": False}]
        hechos = {"padres": padres, "hijos_grupos": hijos_grupos, "pozos": npz,
                  "operador": None, "fuera_estructura": False}
        return texto, hechos

    if niv == "gerencia":
        campos = data["ger_campos"][norm(canonical)]
        activos = data["ger_activos"].get(norm(canonical), set())
        _g, vps = _padres(campos, data)
        npz = _contar_pozos(data["ger_fields"].get(norm(canonical), set()))
        lineas = [
            _uno_o_varios("Vicepresidencia", "Vicepresidencias", vps),
            f"Activos ({len(activos)}): {_lista(activos)}" if activos else None,
            f"Campos ({len(set(campos))}): {_lista(campos)}",
            f"Pozos: {npz}" if npz is not None else None,
        ]
        texto = _bloque(f"«{canonical}» · Gerencia", lineas)
        padres = [{"nivel": "vicepresidencia", "items": sorted(vps)}] if vps else []
        # Activos Y Campos son grupos DISTINTOS que el texto muestra a la vez (Activos solo si
        # existen; Campos siempre) — dos entradas en hijos_grupos, no una.
        hijos_grupos = []
        if activos:
            hijos_grupos.append({"nivel": "activo", "items": list(set(activos)), "es_hermanos": False})
        hijos_grupos.append({"nivel": "campo", "items": list(set(campos)), "es_hermanos": False})
        hechos = {"padres": padres, "hijos_grupos": hijos_grupos, "pozos": npz,
                  "operador": None, "fuera_estructura": False}
        return texto, hechos

    if niv == "vicepresidencia":
        gers = data["vp_ger"].get(norm(canonical), set())
        activos = data["vp_activos"].get(norm(canonical), set())
        campos = data["vp_campos"][norm(canonical)]
        npz = _contar_pozos(data["vp_fields"].get(norm(canonical), set()))
        lineas = [
            f"Gerencias ({len(gers)}): {_lista(gers)}" if gers else "Gerencias: 0",
            f"Activos ({len(activos)}): {_lista(activos)}" if activos else None,
            f"Campos ({len(set(campos))}): {_lista(campos)}",
            f"Pozos: {npz}" if npz is not None else None,
        ]
        texto = _bloque(f"«{canonical}» · Vicepresidencia", lineas)
        # Gerencias SIEMPRE (incl. vacío, como el texto: "Gerencias: 0"); Activos solo si hay;
        # Campos SIEMPRE. Tres grupos simultáneos — es la razón por la que hijos_grupos es lista.
        hijos_grupos = [{"nivel": "gerencia", "items": list(set(gers)), "es_hermanos": False}]
        if activos:
            hijos_grupos.append({"nivel": "activo", "items": list(set(activos)), "es_hermanos": False})
        hijos_grupos.append({"nivel": "campo", "items": list(set(campos)), "es_hermanos": False})
        hechos = {"padres": [], "hijos_grupos": hijos_grupos, "pozos": npz,
                  "operador": None, "fuera_estructura": False}
        return texto, hechos

    if niv == "operador":
        campos = data["op_campos"][norm(canonical)]
        texto = _bloque(f"«{canonical}» · Operador (empresa, no un nivel de la jerarquía)", [
            f"Opera {len(set(campos))} campo(s) del reporte diario: {_lista(campos)}",
        ])
        hechos = {"padres": [], "hijos_grupos": [{"nivel": "campo", "items": list(set(campos)),
                  "es_hermanos": False}], "pozos": None, "operador": None, "fuera_estructura": False}
        return texto, hechos

    return f"«{canonical}»", {"padres": [], "hijos_grupos": [], "pozos": None,
                              "operador": None, "fuera_estructura": False}


def _tope_panel(items, tope=14):
    """Mismo tope que _lista() (:138) pero para el panel: declara el resto (`total`+`truncado`) en
    vez de recortarlo en silencio."""
    items = sorted(set(items))
    if len(items) <= tope:
        return items, len(items), False
    return items[:tope], len(items), True


def _panel_desde_hechos(niv, canonical, puente, hechos):
    """Arma el `panel` del árbol jerárquico (o de operador) desde los HECHOS que _cuerpo ya
    calculó — NUNCA recalcula pozos (regla no negociable: _contar_pozos no tiene caché y consulta
    robustez_v02, otra BD). El panel jamás pasa por el LLM (Python calcula, el LLM solo redacta
    el intro/cierre del mensaje, en _envolver)."""
    if niv == "operador":
        grupo = hechos["hijos_grupos"][0] if hechos.get("hijos_grupos") else {"items": []}
        items, total, truncado = _tope_panel(grupo["items"])
        return {"tipo": "jerarq_operador", "datos": {
            "entidad": canonical, "campos": items, "total": total, "truncado": truncado,
        }}
    if hechos.get("fuera_estructura"):
        return {"tipo": "jerarq_arbol", "datos": {
            "entidad": canonical, "nivel": niv, "puente": puente,
            "padres": [], "hijos_grupos": [], "pozos": None,
            "operador": hechos.get("operador"), "fuera_estructura": True,
        }}
    hijos_grupos = []
    for g in hechos.get("hijos_grupos") or []:
        items, total, truncado = _tope_panel(g["items"])
        hijos_grupos.append({"nivel": g["nivel"], "items": items, "total": total,
                              "truncado": truncado, "es_hermanos": g.get("es_hermanos", False)})
    return {"tipo": "jerarq_arbol", "datos": {
        "entidad": canonical, "nivel": niv, "puente": puente,
        "padres": hechos.get("padres") or [],
        "hijos_grupos": hijos_grupos,
        "pozos": hechos.get("pozos"),
        "operador": hechos.get("operador"),
        "fuera_estructura": False,
    }}


_NOENT = ("Para responderte sobre la estructura necesito una entidad concreta — un campo, "
          "activo, gerencia o vicepresidencia. ¿Sobre cuál quieres saber?")


def _resolver(texto):
    """→ (niv, canonical, puente, data). niv='__noent__' si no hay entidad; None si no hay tabla."""
    try:
        data = _cargar()
    except Exception:
        return None
    hit = _detectar(texto)
    if not hit:
        return ("__noent__", None, None, None)
    _key, niveles, prev = hit
    niv, canonical, puente = _elegir(niveles, _label_previo(prev))
    return (niv, canonical, puente, data)


def _con_puente(niv, canonical, puente, cuerpo):
    if puente and niv in _ART:
        art_user = {"gerencia": "la gerencia", "vicepresidencia": "la vicepresidencia",
                    "activo": "el activo", "campo": "el campo"}.get(puente, puente)
        return (f"Lo que en el reporte diario llamas «{art_user} {canonical}» es, en la estructura "
                f"oficial, {_ART[niv]} {canonical}.\n\n" + cuerpo)
    return cuerpo


def _ofertas(niv, canonical, data):
    """Acción(es) del siguiente paso, en frase apta para una pregunta. DETERMINISTA — es lo que el
    cierre ofrece y lo que la memoria (parte 2) sabrá resolver."""
    if niv == "vicepresidencia":
        gers = sorted(data["vp_ger"].get(norm(canonical), set()))
        return (f"bajar a una de sus gerencias ({_y(gers)}) o ver la producción de {canonical}"
                if gers else f"ver la producción de {canonical}")
    if niv in ("gerencia", "activo"):
        return f"ver la producción de {canonical} o el detalle de uno de sus campos"
    if niv == "campo":
        return f"ver la producción de {canonical} o consultar otro campo o activo"
    if niv == "operador":
        return "ver su participación de ECP o consultar otro campo o activo"
    return "consultar otra entidad"


def _intro_llm(canonical, niv, usuario):
    """Solo el saludo/lead-in cálido y dinámico. '' si el LLM falla o está off (sin intro)."""
    prompt = PROMPT_ENV.format(entidad=canonical, nivel=niv, usuario=usuario or "el usuario")
    return respuesta_base.intro_llm(prompt, _s.consulta_jerarq_llm)


def _envolver(canonical, niv, body, ofertas, usuario):
    """intro (LLM, dinámico) + body (hechos VERBATIM) + cierre (Python, exacto)."""
    intro = _intro_llm(canonical, niv, usuario)
    cierre = f"¿Quieres {ofertas}?"
    return respuesta_base.envolver(intro, body, cierre)


def responder(texto: str):
    """Determinista (hechos), SIN LLM — para tests y como fallback. None si no hay tabla."""
    rk = _rank_detectar(texto)
    if rk is not None:
        try:
            data = _cargar()
        except Exception:
            return None
        res = _rank_calcular(rk, data)
        return res["texto"] if not res.get("aplica") else _rank_cuerpo(res)
    r = _resolver(texto)
    if r is None:
        return None
    niv, canonical, puente, data = r
    if niv == "__noent__":
        return _NOENT
    return _con_puente(niv, canonical, puente, _cuerpo(niv, canonical, data)[0])


def responder_cordial(texto: str, usuario=None):
    """B: envuelve los hechos con marco cordial dinámico (LLM). Hechos VERBATIM. None si no hay
    tabla (maquina_q deja 'en construcción'); si no hay entidad, pide una sin envolver.
    [2026-08-11] Devuelve {mensaje, panel} — mismo contrato que respuesta_cuantificar.responder
    (maquina_q ya sabe consumirlo). panel:None cuando no aplica (sin entidad, ranking que declina,
    sin tabla) para no pintar un bloque vacío en el visor; en esos 3 casos se sigue devolviendo un
    str plano, como antes, y maquina_q lo toma tal cual (rama `elif r: mensaje = r`)."""
    # ── RANKING ESTRUCTURAL (eje ortogonal) ──────────────────────────────────────────────────
    # Antes del resolver de entidad única: "los campos con más pozos" no nombra UNA entidad (los
    # sustantivos de nivel están en _STOP) → moriría en __noent__ ("¿sobre cuál?").
    rk = _rank_detectar(texto)
    if rk is not None:
        try:
            data = _cargar()
        except Exception:
            return None                          # sin tabla → 'en construcción' (igual que _resolver)
        res = _rank_calcular(rk, data)
        if not res.get("aplica"):
            return res["texto"]                  # declina honesto, sin envolver (como _NOENT)
        body = _rank_cuerpo(res)
        mensaje = _envolver(f"un ranking de {_RANK_PLURAL[res['subject']]} por número de {res['conteo']}",
                            "ranking", body, _rank_oferta(res), usuario)
        # `res` YA es el contrato estructurado (aplica/subject/conteo/asc/items/total) — se pasa
        # TAL CUAL como datos del panel, sin construir un dict intermedio.
        return {"mensaje": mensaje, "panel": {"tipo": "jerarq_rank", "datos": res}}
    r = _resolver(texto)
    if r is None:
        return None
    niv, canonical, puente, data = r
    if niv == "__noent__":
        return _NOENT
    texto_hechos, hechos = _cuerpo(niv, canonical, data)
    body = _con_puente(niv, canonical, puente, texto_hechos)
    mensaje = _envolver(canonical, niv, body, _ofertas(niv, canonical, data), usuario)
    panel = _panel_desde_hechos(niv, canonical, puente, hechos)
    return {"mensaje": mensaje, "panel": panel}


# ---------------------------------------------------------------------------
# Soporte para la MEMORIA conversacional (parte 2, en maquina_q): tras resolver una entidad,
# exponemos su contexto (nivel + hijos por nombre) para que una respuesta corta la continúe.
# ---------------------------------------------------------------------------
def _hijos(niv, canonical, data):
    """Nombres de los hijos por los que el usuario podría navegar tras esta respuesta."""
    k = norm(canonical)
    if niv == "vicepresidencia":
        return set(data["vp_ger"].get(k, set())) | set(data["vp_activos"].get(k, set()))
    if niv == "gerencia":
        return set(data["ger_activos"].get(k, set())) | set(data["ger_campos"].get(k, []))
    if niv == "activo":
        return set(data["act_campos"].get(k, []))
    return set()


def contexto(texto):
    """{entidad, nivel, hijos, ofrece_produccion} tras resolver la entidad de `texto`. None si no
    hay tabla o no hay entidad. Lo consume la memoria de maquina_q."""
    r = _resolver(texto)
    if r is None:
        return None
    niv, canonical, _puente, data = r
    if niv == "__noent__":
        return None
    return {"entidad": canonical, "nivel": niv,
            "hijos": {norm(h) for h in _hijos(niv, canonical, data)},
            "ofrece_produccion": True}


def entidad_en(texto):
    """Canónico de la entidad de jerarquía hallada en `texto` (nivel más específico), o None."""
    try:
        _cargar()
    except Exception:
        return None
    hit = _detectar(texto)
    if not hit:
        return None
    _k, niveles, _p = hit
    d = {niv: canon for niv, canon in niveles}
    return d[min(d, key=lambda x: _ORDEN[x])]
