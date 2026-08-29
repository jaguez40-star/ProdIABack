import time, sqlalchemy as sa
from app.core.db import get_engine
from app.features.consulta.extraccion import extraer
from app.features.consulta.resolver import (resolver, buscar_en_texto, termino_candidato,
                                            clave_fisica, fuentes_de_activo)
import logging
from app.features.consulta.ejecucion import ejecutar
from app.features.consulta.narracion import narrar
from app.features.consulta.meta import detectar as meta_detectar, responder_meta as meta_responder

_NIVEL_LABEL = {"vicepresidencia":"Vicepresidencia","gerencia":"Gerencia","activo":"Activo",
                "campo":"Campo","fuente":"Fuente (pozo)","operador":"Operador",
                "filial":"Filial (empresa)","pozo":"Fuente (pozo)"}

# Copy humano por nivel (V2: el botón describe LO QUE OBTIENES, no el nombre técnico de la tabla).
# Plantilla rellenada por Python — el LLM no interviene aquí (bookending D4/§7.6). titulo = capitalización
# normal (nada de MAYÚSCULAS sostenidas); desc = el "para qué"; emoji con significado y moderación.
_NIVEL_INFO = {
    "fuente":          {"titulo": "Un pozo",             "desc": "Un pozo específico (máximo detalle)",   "emoji": "📈"},
    "campo":           {"titulo": "Un campo",            "desc": "Un campo (agrupa sus pozos)",           "emoji": "🛢️"},
    "activo":          {"titulo": "Un activo",           "desc": "Un activo (agrupa varios campos)",      "emoji": "📦"},
    "gerencia":        {"titulo": "Una gerencia",        "desc": "Una gerencia operativa",                "emoji": "🏛️"},
    "vicepresidencia": {"titulo": "Una vicepresidencia", "desc": "Una vicepresidencia (nivel alto)",      "emoji": "🏢"},
    "operador":        {"titulo": "Operación (ECP)",     "desc": "El detalle de sus campos y pozos",      "emoji": "📋"},
    "filial":          {"titulo": "Empresa / filial",    "desc": "La cifra consolidada de la filial",     "emoji": "🏢"},
    "pozo":            {"titulo": "Un pozo",             "desc": "Un pozo específico (máximo detalle)",   "emoji": "📈"},
}

# --- persistencia del intent parcial (v1: memoria por conversation_id + TTL) ---
_PARCIAL = {}       # conversation_id -> (intent, ts)
_TTL = 900          # 15 min

def _guardar(cid, intent): _PARCIAL[cid] = (intent, time.time())
def _leer(cid):
    v = _PARCIAL.get(cid)
    if not v: return None
    intent, ts = v
    if time.time() - ts > _TTL:
        _PARCIAL.pop(cid, None); return None
    return intent

def _nuevo_intent(slots):
    return {"status": "pendiente",
            "entidad": {"texto": slots.get("entidad"), "resuelta": None},
            "producto": slots.get("producto"), "periodo": slots.get("periodo"),
            "agregacion": slots.get("agregacion"),
            "pendiente": None, "avisos": [], "_slots": slots}

def _fijar_resuelta(intent, ident):
    intent["entidad"]["resuelta"] = {"nivel": ident["nivel"], "rama": ident["rama"], "valor": ident["valor"]}
    intent["pendiente"] = None
    intent.pop("zoom", None)   # un zoom previo no sobrevive a una nueva resolución (evita nota duplicada)
    intent["status"] = "completo"
    return intent

# --- Desambiguación por colapso (política determinista, D-D1..D-D4) ---
# Prioridad canónica para elegir el representante de un grupo colapsado (campo gana).
# Solo desempata ENTRE NIVELES CON EL MISMO CONJUNTO FÍSICO (ej. RUBIALES = fuente=campo=activo),
# donde la elección es de ETIQUETA, no de alcance: se muestra la que el negocio entiende.
# 2026-07-16: se eliminó "area" (grupo1) — no es un nivel del negocio (ver resolver._LEVELS).
# Era la causa de que Chichimene y Castilla NO ofrecieran el zoom a Activo: area(4) le ganaba a
# activo(3) al colapsar y el representante 'activo' desaparecía antes de llegar a _prioridad_campo.
_PRIORIDAD = {"campo": 5, "activo": 3, "gerencia": 2, "fuente": 1, "pozo": 1}


def _rep(grupo):
    """Representante canónico de un grupo colapsado (mayor prioridad; campo gana)."""
    return max(grupo, key=lambda i: _PRIORIDAD.get(i["nivel"], 0))


def _resolver_colision(ids, clave_fn):
    """Política determinista. Devuelve (modo, rep, reps):
      ("auto", rep, reps)  -> 1 solo conjunto físico (redundante) -> auto-resolver.
      ("ask", None, reps)  -> >=2 conjuntos físicos -> preguntar (deduplicado por grupo).
    reps = un representante por grupo físico (deduplicado)."""
    grupos = {}
    for i in ids:
        grupos.setdefault(clave_fn(i), []).append(i)
    reps = [_rep(g) for g in grupos.values()]
    if len(reps) == 1:
        return ("auto", reps[0], reps)
    return ("ask", None, reps)


def _prioridad_campo(reps):
    """D-D5 (decisión del usuario, 2026-07-15): prioridad Campo en colisiones genuinas.
    Si entre los grupos físicos hay EXACTAMENTE un campo y ninguna identidad de filial (rama B),
    se responde directo como Campo (las lecturas de pozo se descartan) y SOLO se ofrece el
    zoom a Activo (si existe como conjunto físico distinto). Devuelve (rep_campo|None, zoom_activos).
    - dual A/B (ej. Hocol): universos de datos distintos -> None (sigue preguntando).
    - 0 campos o 2+ campos físicos distintos con el mismo nombre -> None (sigue preguntando)."""
    if any(r.get("rama") == "B" for r in reps):
        return None, []
    campos = [r for r in reps if r["nivel"] == "campo"]
    if len(campos) != 1:
        return None, []
    return campos[0], [r for r in reps if r["nivel"] == "activo"]


def _prioridad_filial(reps):
    """D-D6 (decisión del usuario, 2026-07-21): prioridad Filial. Las 3 filiales (Hocol/America/Permian)
    son UN solo tipo de entidad; al preguntar por su nombre se responde directo como FILIAL (rama B,
    cifra consolidada) — igual que America/Permian, que no son duales. Se analizan SOLO como filial,
    nada más (decisión del usuario 2026-07-21): el sentido ECP (rama A: Hocol como operador de campos)
    NO se ofrece — a grano de campo/operador no hay datos útiles de filial que mostrar. Devuelve
    (rep_filial|None, []). Solo aplica con EXACTAMENTE una identidad rama B; con 0 o 2+ sigue preguntando."""
    filiales = [r for r in reps if r.get("rama") == "B"]
    if len(filiales) != 1:
        return None, []
    return filiales[0], []   # sin zoom: filial y nada más

def preguntar(texto: str, cid: str, usuario=None) -> dict:
    """S0 EXTRAER → S1 RESOLVER → (completo | pendiente con botones). usuario: nombre para la narración."""
    # S-META (2026-07-16): pregunta de CATÁLOGO ("¿qué tipo de entidad es X?", "¿qué campos tiene el
    # activo Y?", "¿a qué activo pertenece Z?"). Va ANTES de extraer(): no necesita LLM (es un lookup)
    # y la pregunta es legítima porque la cifra DEPENDE del nivel (APIAY: 269.035 bl como Campo vs
    # 577.362 bl como Activo). La respuesta sale con forma `pendiente` -> el clic reusa responder()/S3
    # y entrega la cifra del nivel elegido. Si no se resuelve, cae al flujo normal.
    intencion_meta = meta_detectar(texto)
    if intencion_meta:
        out_meta = meta_responder(texto, intencion_meta)
        if out_meta:
            pend = out_meta.pop("_pendiente", None)
            if pend:                       # guardar para que responder()/S3 acepte el clic
                intent = _nuevo_intent({"entidad": out_meta["opciones"][0]["label"]})
                intent["entidad"]["texto"] = pend["opciones"][0]["valor"]
                intent["pendiente"] = pend
                _guardar(cid, intent)
            return out_meta

    slots = extraer(texto)
    if not slots.get("entidad"):
        # Red de seguridad: qwen2.5:3b a veces omite la entidad aunque esté literal en el texto
        # (no-determinismo incluso con temperature=0). Python la rescata del catálogo cerrado.
        hit = buscar_en_texto(texto)
        if hit:
            slots["entidad"] = hit[0]
        else:
            cand = termino_candidato(texto)
            msg = (f"No identifiqué «{cand}» como una entidad incluida en los reportes diarios. ¿Puedes reformular?"
                   if cand else
                   "No identifiqué ninguna entidad en tu pregunta. ¿Puedes nombrar un campo, pozo, gerencia o filial?")
            return {"status": "reformular", "mensaje": msg}
    intent = _nuevo_intent(slots)
    ids = resolver(slots["entidad"])
    if not ids:
        return {"status": "reformular", "intent": intent,
                "mensaje": f"No identifiqué «{slots['entidad']}» como una entidad incluida en los reportes diarios. ¿Puedes reformular?"}
    # pista de nivel del LLM: desempata SOLO si coincide con una identidad real
    pista = (slots.get("nivel") or "").lower()
    match_pista = [i for i in ids if i["nivel"] == pista or (pista == "pozo" and i["nivel"] == "fuente")]
    if len(ids) == 1:
        _fijar_resuelta(intent, ids[0])
    elif len(match_pista) == 1:
        intent["avisos"].append(f"Interpreté «{slots['entidad']}» como {match_pista[0]['nivel']} (por tu texto).")
        _fijar_resuelta(intent, match_pista[0])
    else:
        # colisión → política de colapso (D-D1..D-D4). Redundante -> auto-resolver; genuina/dual -> preguntar (dedup).
        modo, rep, reps = _resolver_colision(ids, clave_fisica)
        zoom = []
        if modo == "ask":
            # D-D5: prioridad Campo — si el nombre figura como campo, responde directo como Campo.
            rep_campo, zoom = _prioridad_campo(reps)
            if rep_campo is not None:
                modo, rep = "auto", rep_campo
            else:
                # D-D6: prioridad Filial — Hocol (dual A/B) se resuelve como filial, con zoom al ECP.
                rep_fil, zoom = _prioridad_filial(reps)
                if rep_fil is not None:
                    modo, rep = "auto", rep_fil
        if modo == "auto":
            intent["avisos"].append(
                f"Interpreté «{slots['entidad']}» como {_NIVEL_LABEL.get(rep['nivel'], rep['nivel'])}.")
            _fijar_resuelta(intent, rep)
            if zoom:
                # Oferta "Ver como Activo": nota determinista (Python, no LLM) + botones. El clic
                # reusa responder() (S3): la opción se guarda como pendiente aunque el status sea
                # completo — _salida solo pinta pregunta con status "pendiente", así que no hay
                # doble pregunta, pero el zoom fluye por el mismo riel (cifra+narración+panel).
                cats = " y ".join(sorted({_NIVEL_LABEL.get(z["nivel"], z["nivel"]) for z in zoom}))
                intent["zoom"] = {
                    "nota": f"«{slots['entidad']}» también se reconoce como {cats}. ¿Deseas ver ese análisis?",
                    "opciones": [{"id": f"{z['nivel']}::{z['valor']}",
                                  "label": f"Ver análisis como {_NIVEL_LABEL.get(z['nivel'], z['nivel'])}",
                                  "desc": _NIVEL_INFO.get(z["nivel"], {}).get("desc", "")} for z in zoom]}
                intent["pendiente"] = {"slot": "nivel",
                    "opciones": [{"id": f"{z['nivel']}::{z['valor']}", "label": _NIVEL_LABEL.get(z['nivel'], z['nivel']),
                                  "nivel": z["nivel"], "rama": z["rama"], "valor": z["valor"]} for z in zoom]}
                _guardar(cid, intent)
        else:  # ask (genuina sin campo, dual A/B, o 2+ campos) → preguntar por GRUPO (deduplicado)
            intent["pendiente"] = {"slot": "nivel",
                "opciones": [{"id": f"{r['nivel']}::{r['valor']}", "label": _NIVEL_LABEL.get(r['nivel'], r['nivel']),
                              "nivel": r["nivel"], "rama": r["rama"], "valor": r["valor"]} for r in reps]}
            _guardar(cid, intent)
    return _salida(intent, usuario)

def responder(cid: str, opcion_id: str, usuario=None) -> dict:
    """S3 REANUDAR: aplica la opción elegida → intent completo. usuario: nombre para la narración."""
    intent = _leer(cid)
    if not intent or not intent.get("pendiente"):
        return {"status": "expirado", "mensaje": "No hay una pregunta pendiente (o expiró). Escribe de nuevo."}
    op = next((o for o in intent["pendiente"]["opciones"] if o["id"] == opcion_id), None)
    if not op:
        return {"status": "error", "mensaje": "Opción no válida."}
    _fijar_resuelta(intent, op)
    _PARCIAL.pop(cid, None)
    return _salida(intent, usuario)

def _salida(intent: dict, usuario=None) -> dict:
    out = {"status": intent["status"]}
    if intent["status"] == "pendiente":
        ent = intent["entidad"]["texto"]
        ops = intent["pendiente"]["opciones"]
        # Conector humano + situación en lenguaje llano + pregunta corta (plantilla reusable).
        out["pregunta"] = f"Encontré «{ent}» de {len(ops)} formas distintas en los reportes disponibles. ¿Cuál necesitas?"
        out["opciones"] = []
        for o in ops:
            info = _NIVEL_INFO.get(o["nivel"], {"titulo": o.get("label", o["nivel"]), "desc": "", "emoji": "•"})
            out["opciones"].append({"id": o["id"], "label": info["titulo"],
                                    "desc": info["desc"], "emoji": info["emoji"]})
    if intent["status"] == "completo":
        r = intent["entidad"]["resuelta"]
        out["intent"] = {"entidad": intent["entidad"]["texto"], "nivel": r["nivel"], "rama": r["rama"],
                         "valor": r["valor"], "avisos": intent["avisos"], "periodo": intent.get("periodo")}
        if intent.get("zoom"):
            out["zoom"] = intent["zoom"]   # D-D5: oferta "Ver como Activo" (nota + botones)
        out["huella"] = _huella(r)   # huella básica (rango temporal) de la entidad resuelta
        # Fase 3 (determinista): cifra REAL vs PPTO reusando el motor del tablero. Regla madre: ningún
        # error interno llega feo al usuario; F7: se loguea el traceback para no depurar a ciegas.
        try:
            out["respuesta"] = ejecutar(r, intent.get("producto"), intent.get("periodo"),
                                        intent.get("agregacion"))
        except Exception:
            logging.getLogger("consulta.ejecucion").exception("ejecutar() falló")
            out["respuesta"] = {"aplica": False,
                                "texto": "No pude calcular la cifra en este momento. Intenta de nuevo."}
        # Fase 3.1 (opcional, flag CONSULTA_NARRA_LLM): el LLM redacta la cifra ya calculada. La
        # determinista sigue siendo la fuente de verdad + fallback; la narración es capa encima (D-N1).
        try:
            nar = narrar(out.get("respuesta"), usuario)
            if nar:
                out["respuesta"]["narracion"] = nar
        except Exception:
            logging.getLogger("consulta.narracion").exception("narrar() falló")
    return out

# Columna de dim_fuente que corresponde EXACTAMENTE a cada nivel de rama A. Resolver por la columna
# específica (no por las 6 a la vez) evita contaminación cruzada: p.ej. la filial "Hocol" ya no calza
# por accidente con operador='HOCOL' y devuelve la huella de la operación ECP (bug de identidad dual).
# 2026-07-16: 'activo' YA NO es una columna — se compone desde core.map_campo_activo
# (resolver.fuentes_de_activo). 'area'/'activos' eliminados (no son niveles del negocio).
_NIVEL_COL = {"fuente": "nombre", "campo": "campo",
              "gerencia": "gerencia", "operador": "operador"}

def _huella(resuelta: dict) -> dict:
    """Huella temporal básica de la entidad resuelta. Distingue por rama y por nivel:
    - Rama B (filial): cifra consolidada, SIN grano diario ECP → {aplica:false} (vive en las hojas).
    - Rama A, nivel vicepresidencia: por vice_id en fact_produccion_dia_ecp.
    - Rama A, resto: por la columna de dim_fuente propia del nivel (no las 6 a la vez)."""
    nivel, rama, E = resuelta["nivel"], resuelta.get("rama"), resuelta["valor"].upper()
    if rama == "B":
        return {"aplica": False}   # filial → cifra consolidada; no hay grano diario ECP en v1
    eng = get_engine()
    with eng.connect() as c:
        if nivel == "vicepresidencia":
            vid = c.execute(sa.text("SELECT vice_id FROM core.dim_vicepresidencia WHERE UPPER(TRIM(codigo))=:e"),
                            {"e": E}).scalar()
            if vid is None:
                return {"aplica": False}
            cond, params, expand = "vice_id = :vid", {"vid": vid}, False
        else:
            if nivel == "activo":
                ids = fuentes_de_activo(E)      # composición del activo = core.map_campo_activo
            else:
                col = _NIVEL_COL.get(nivel)
                if not col:
                    return {"aplica": False}
                ids = [x[0] for x in c.execute(
                    sa.text(f"SELECT fuente_id FROM core.dim_fuente WHERE UPPER(TRIM({col}))=:e"), {"e": E})]
            if not ids:
                return {"aplica": False}
            cond, params, expand = "fuente_id IN :ids", {"ids": ids}, True
        q = sa.text("SELECT MIN(fecha), MAX(fecha), COUNT(DISTINCT fecha) "
                    "FROM core.fact_produccion_dia_ecp WHERE " + cond)
        if expand:
            q = q.bindparams(sa.bindparam("ids", expanding=True))
        lo, hi, n = c.execute(q, params).one()
        return {"aplica": bool(n), "desde": lo.isoformat() if lo else None,
                "hasta": hi.isoformat() if hi else None, "dias": n or 0}
