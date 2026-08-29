"""Preguntas META sobre el catálogo ("¿qué tipo de entidad es X?", "¿qué campos tiene el activo Y?",
"¿a qué activo pertenece Z?").

POR QUÉ EXISTE (2026-07-16): la cifra DEPENDE de si el nombre se lee como Campo o como Activo —
APIAY da 269.035 bl (50.7%, Foco) como Campo y 577.362 bl (108.8%, Alineado) como Activo. Si el
usuario no puede preguntar QUÉ es algo, no puede saber qué cifra está pidiendo. Antes, "¿qué tipo de
entidad es CPO-09?" devolvía una cifra de producción: contestaba otra cosa.

SIN LLM — y esto es una DECISIÓN, no una omisión (usuario, 2026-07-16):
La regla del proyecto es «Python calcula, el LLM redacta». En la CIFRA el LLM aporta: hay un número,
un contexto y un juicio que merecen prosa. Aquí NO hay nada que redactar: la respuesta ES la lista de
hechos del catálogo (CPO-09 -> Activo -> campos: AKACIAS). El LLM solo podía aportar cosmética, y la
pagaba con falsedades: al pulir la frase, qwen2.5:3b afirmó "hay otro Activo llamado CHICHIMENE SW"
(es un campo del Activo CHICHIMENE). La salvaguarda verifica que los nombres aparezcan LITERALES, pero
NO puede verificar que las RELACIONES entre ellos sean ciertas -> el chat podía mentir sobre el
catálogo sin que saltara nada. Se probó y se descartó; no reintroducir sin resolver esa verificación.

El saludo por nombre lo pone el frontend (__cnConNombre) como en el resto de mensajes `pendiente`.
⚠️ Por eso TODA plantilla debe empezar con «NOMBRE»: __cnConNombre minusculiza la inicial, y con un
nombre propio al arranque produciría "cPO-09". El guillemot la deja intacta.

REUSA EL RIEL EXISTENTE: la respuesta sale como `pendiente` (pregunta + opciones), así que el clic cae
en responder()/S3 y entrega la cifra del nivel elegido con su narración y su panel: explica QUÉ es y,
en el mismo paso, lleva AL número.
"""
import re as _re
from app.features.consulta.normaliza import norm
from app.features.consulta.resolver import (resolver, buscar_en_texto, termino_candidato,
                                            clave_fisica, campos_de_activo, activo_de_campo)

# Intenciones meta. Patrones sobre el texto NORMALIZADO (sin acentos, mayúsculas).
_TIPO = [r"\bQUE TIPO DE ENTIDAD ES\b", r"\bQUE TIPO ES\b", r"\bQUE ENTIDAD ES\b",
         r"\bQUE TIPO DE ENTIDAD\b", r"\bQUE ES\b", r"\bQUIEN ES\b"]
_CAMPOS = [r"\bQUE CAMPOS\b", r"\bCUALES CAMPOS\b", r"\bCAMPOS TIENE\b", r"\bCAMPOS DEL ACTIVO\b",
           r"\bQUE CAMPOS TIENE\b", r"\bSE COMPONE\b", r"\bCOMPUESTO POR\b", r"\bAGRUPA\b"]
_PERTENENCIA = [r"\bA QUE ACTIVO\b", r"\bDE QUE ACTIVO\b", r"\bPERTENECE\b"]

# HUELLA (2026-07-16): "¿qué información hay de X?" → abre el panel de Densidad + Cobertura. Es la
# puerta de entrada de ese panel: antes solo se llegaba por "Volver al panorama", que ahora devuelve
# al Desempeño global. Pregunta por la DISPONIBILIDAD del dato, no por el dato.
_HUELLA = [r"\bQUE INFORMACION\b", r"\bQUE DATOS\b", r"\bQUE REPORTES\b", r"\bQUE HOJAS\b",
           r"\bDESDE CUANDO\b", r"\bHASTA CUANDO\b", r"\bCOBERTURA\b", r"\bDISPONIBILIDAD\b",
           r"\bDISPONIBLE\b", r"\bHUELLA\b", r"\bDENSIDAD\b", r"\bCUANTOS DIAS\b",
           r"\bQUE SE SABE\b",
           # "cuál es el reporte de X" / "los reportes de X": preguntan por el reporte que respalda a
           # la entidad, no por su cifra.
           r"\bCUAL ES EL REPORTE\b", r"\bCUALES SON LOS REPORTES\b",
           r"\bEL REPORTE DE\b", r"\bLOS REPORTES DE\b"]

# Guarda: si el texto pide un número, NO es meta (ej. "cuál es la producción de X").
# Sin esto, "que es la produccion de X" se colaría como pregunta de catálogo.
_PIDE_CIFRA = _re.compile(r"\bPRODUC|\bCUANT|\bVOLUMEN\b|\bBARRILES\b|\bCIFRA\b|\bPRESUPUESTO\b")


def detectar(texto: str) -> str | None:
    """Intención meta del texto: 'huella' | 'pertenencia' | 'campos' | 'tipo' | None. Determinista."""
    t = norm(texto or "")
    # La huella va ANTES del guard de cifra a propósito: "cuántos días con reporte hay de X" y
    # "desde cuándo hay datos de producción de X" preguntan por la DISPONIBILIDAD, pero traen
    # CUANT/PRODUC — el guard las habría descartado y habrían acabado devolviendo una cifra.
    if any(_re.search(p, t) for p in _HUELLA):
        return "huella"
    if _PIDE_CIFRA.search(t):
        return None
    for pats, nombre in ((_PERTENENCIA, "pertenencia"), (_CAMPOS, "campos"), (_TIPO, "tipo")):
        if any(_re.search(p, t) for p in pats):
            return nombre
    return None


_ARTICULO = {"campo": "el Campo", "activo": "el Activo", "gerencia": "la Gerencia",
             "vicepresidencia": "la Vicepresidencia", "fuente": "la fuente", "pozo": "la fuente",
             "operador": "la operación de", "filial": "la filial"}
_NOMBRE_TIPO = {"campo": "Campo", "activo": "Activo", "gerencia": "Gerencia",
                "vicepresidencia": "Vicepresidencia", "fuente": "Fuente (pozo)",
                "pozo": "Fuente (pozo)", "operador": "Operador", "filial": "Filial (empresa)"}


def _plural(n, sing, plu):
    return f"{n} {sing if n == 1 else plu}"


def _describir(rep: dict) -> str:
    """Rol de una lectura EN EL CATÁLOGO (no cifras): de qué se compone o dónde encaja.

    Devuelve la inicial en MINÚSCULA para poder incrustarla dentro de una frase, y los NOMBRES
    PROPIOS intactos. Nunca aplicar .lower() al resultado: minusculizaría los nombres y entonces la
    salvaguarda de narracion (que exige los nombres literales) dejaría de protegerlos — pasó con
    "CHICHIMENE SW", que el LLM omitió sin que saltara nada. Usar _cap() para mostrarlo suelto."""
    nivel, valor = rep["nivel"], rep["valor"]
    if nivel == "activo":
        cs = campos_de_activo(valor)
        if not cs:
            return "un activo del catálogo (sin campos con datos)"
        return f"agrupa {_plural(len(cs), 'campo', 'campos')}: " + ", ".join(cs)
    if nivel == "campo":
        act = activo_de_campo(valor)
        return (f"un campo del Activo {act}" if act
                else "un campo que no pertenece a ningún Activo del catálogo")
    if nivel == "filial":
        return "una empresa filial (cifra consolidada)"
    if nivel == "operador":
        return "el operador de varios campos"
    if nivel in ("fuente", "pozo"):
        return "una fuente del reporte (el máximo detalle disponible)"
    if nivel == "gerencia":
        return "una gerencia operativa"
    if nivel == "vicepresidencia":
        return "una vicepresidencia"
    return _NOMBRE_TIPO.get(nivel, nivel)


def _cap(s: str) -> str:
    """Primera letra en mayúscula SIN tocar el resto (str.capitalize() minusculizaría los nombres)."""
    return (s[0].upper() + s[1:]) if s else s


def _y(items: list[str]) -> str:
    """Enumeración natural: 'A', 'A y B', 'A, B y C' (no 'A y B y C')."""
    if len(items) <= 1:
        return items[0] if items else ""
    return ", ".join(items[:-1]) + " y " + items[-1]


def _reps(entidad: str) -> list[dict]:
    """Lecturas del nombre, con la MISMA política que la ruta de las cifras — si divergieran, el chat
    diría que algo es un Campo y luego te daría la cifra de otra cosa:
      1. colapso por conjunto físico (RUBIALES = campo=activo=fuente -> UNA sola cosa, no tres);
      2. prioridad Campo (D-D5): si el nombre es un campo, la lectura de 'fuente' se descarta.
         Importa: fuente CHICHIMENE son 5 fuentes (incluye 3 con campo NULL = ruido de ingesta, D-A3)
         frente a las 2 del campo. Ofrecerla sería ofrecer una cifra contaminada.
    """
    from app.features.consulta.maquina import _resolver_colision, _prioridad_campo
    ids = resolver(entidad)
    if not ids:
        return []
    _modo, _rep, reps = _resolver_colision(ids, clave_fisica)
    rep_campo, zoom = _prioridad_campo(reps)
    if rep_campo is not None:
        return [rep_campo] + zoom
    return reps


def responder_meta(texto: str, intencion: str) -> dict | None:
    """Respuesta determinista a una pregunta de catálogo. Devuelve una salida con forma `pendiente`
    (pregunta + opciones) para que el clic reuse responder()/S3 y entregue la cifra. None si no se
    puede resolver la entidad (el llamador sigue con el flujo normal)."""
    hit = buscar_en_texto(texto)                 # catálogo cerrado, sin LLM
    if not hit:
        cand = termino_candidato(texto)
        return {"status": "reformular",
                "mensaje": (f"No identifiqué «{cand}» como una entidad incluida en los reportes diarios. "
                            "¿Puedes reformular?" if cand else
                            "No identifiqué ninguna entidad en tu pregunta. ¿De cuál quieres saber?")}
    termino, _ = hit
    reps = _reps(termino)
    if not reps:
        return None
    ent = reps[0]["valor"]

    # "¿qué información hay de X?" -> abre el panel de huella (Densidad + Cobertura).
    if intencion == "huella":
        return _salida_huella(reps, ent)

    # "¿a qué activo pertenece X?" -> respuesta directa, sin rodeos.
    if intencion == "pertenencia":
        campo = next((r for r in reps if r["nivel"] == "campo"), None)
        if campo:
            act = activo_de_campo(campo["valor"])
            txt = (f"«{campo['valor']}» es un Campo, y pertenece al Activo {act}." if act else
                   f"«{campo['valor']}» es un Campo, y no pertenece a ningún Activo del catálogo.")
            return _salida_meta(txt, reps, ent)

    # "¿qué campos tiene el activo X?" -> composición.
    if intencion == "campos":
        act = next((r for r in reps if r["nivel"] == "activo"), None)
        if act:
            cs = campos_de_activo(act["valor"])
            txt = (f"«{act['valor']}» es un Activo, y agrupa {_plural(len(cs), 'campo', 'campos')}: "
                   + ", ".join(cs) + "." if cs else
                   f"«{act['valor']}» es un Activo, y no tiene campos registrados en el catálogo.")
            return _salida_meta(txt, reps, ent)

    # "¿qué tipo de entidad es X?" (y fallback de las otras dos si el nivel pedido no aplica).
    if len(reps) == 1:
        r = reps[0]
        txt = f"«{ent}» es {_ARTICULO.get(r['nivel'], 'el')} {ent}: {_describir(r)}."
    else:
        # La composición va DENTRO de la frase (no solo en el `desc` de los botones): es la respuesta
        # a "qué es", y además es lo que el LLM debe poder repetir sin inventar (la salvaguarda exige
        # los nombres propios literales; si la frase no los trae, el LLM no puede incluirlos).
        # Enumerada y plana a propósito: con la frase compuesta, un modelo pequeño inventaba
        # relaciones entre los nombres ("hay otro Activo llamado CHICHIMENE SW" — es un campo del
        # Activo CHICHIMENE). La salvaguarda solo verifica presencia de nombres, no la verdad de las
        # relaciones, así que la defensa es no darle nada que reinterpretar.
        partes = "; ".join(f"({i}) {_ARTICULO.get(r['nivel'], 'el')} {r['valor']} — {_describir(r)}"
                           for i, r in enumerate(reps, 1))
        txt = (f"«{ent}» nombra {_plural(len(reps), 'entidad distinta', 'entidades distintas')} "
               f"en los reportes: {partes}. Cada una tiene su propia cifra.")
    return _salida_meta(txt, reps, ent)


def _intent_huella(reps: list[dict], ent: str) -> dict:
    """Intent mínimo que el frontend necesita para pintar Densidad + Cobertura de `ent`.

    Se arma con reps[0] (la lectura prioritaria) y el nivel va SOLO informativo: el panel resuelve
    por nombre. Por eso vale igual aunque el nivel siga sin elegirse."""
    r = reps[0]
    return {"entidad": ent, "valor": r["valor"], "nivel": r["nivel"], "rama": r["rama"]}


def _salida_huella(reps: list[dict], ent: str) -> dict:
    """Status propio 'huella': el frontend pinta el mensaje y abre Densidad + Cobertura de `ent`.

    NO desambigua a propósito. Los endpoints /analisis/densidad y /analisis/cobertura reciben SOLO
    `entidad` (resuelven por nombre, no por nivel), así que la huella de «CHICHIMENE» es la misma se
    lea como Campo o como Activo: preguntar «¿de cuál?» sería teatro — daría dos veces el mismo panel.
    Distinto de la CIFRA, donde el nivel lo cambia todo (APIAY: 269.035 bl vs 577.362 bl).

    ⚠️ Consecuencia honesta de lo mismo: al resolver por nombre, la huella de un Activo NO agrega la
    de sus otros campos (la del Activo CHICHIMENE no incluye CHICHIMENE SW). Por eso el mensaje habla
    del NOMBRE en los reportes, no del Activo. Hacerla nivel-aware = llevar _ambito a esos dos
    endpoints; queda pendiente."""
    return {
        "status": "huella", "meta": True,
        # arranca con «NOMBRE»: __cnConNombre minusculiza la inicial (ver docstring del módulo)
        "mensaje": (f"«{ent}» sí aparece en los reportes diarios. Te muestro a la derecha su huella "
                    "de datos: en qué días hay reporte y en qué hojas aparece el nombre."),
        "intent": _intent_huella(reps, ent),
    }


def _salida_meta(texto: str, reps: list[dict], ent: str) -> dict:
    """Forma `pendiente`: el frontend ya la pinta (pregunta + opciones) y el clic cae en responder()/S3.
    `pregunta` lleva la respuesta meta; las opciones llevan a la cifra de cada lectura.

    Determinista: `texto` ya trae los hechos del catálogo (ver el porqué en el docstring del módulo)."""
    cierre = ("¿De cuál quieres las cifras?" if len(reps) > 1 else "¿Quieres ver sus cifras?")
    out = {"status": "pendiente", "meta": True, "pregunta": f"{texto} {cierre}"}
    # La entidad YA está resuelta (solo falta el nivel), y la huella no depende del nivel → el panel
    # derecho puede pintarla mientras se elige, en vez del aviso vacío de siempre. "Qué es X" queda
    # así: QUÉ es (burbuja) + QUÉ datos hay (panel) → clic → la cifra. Huella primero, número después.
    out["huella_intent"] = _intent_huella(reps, ent)
    # status 'pendiente' A PROPÓSITO: es literalmente una pregunta con opciones, así el frontend la
    # pinta con el riel que ya existe (__cnRender) y el clic cae en responder()/S3.
    out["opciones"] = [{"id": f"{r['nivel']}::{r['valor']}",
                        "label": f"{_NOMBRE_TIPO.get(r['nivel'], r['nivel'])} {r['valor']}",
                        "desc": _cap(_describir(r))} for r in reps]
    out["_pendiente"] = {"slot": "nivel",
                         "opciones": [{"id": f"{r['nivel']}::{r['valor']}",
                                       "label": _NOMBRE_TIPO.get(r["nivel"], r["nivel"]),
                                       "nivel": r["nivel"], "rama": r["rama"],
                                       "valor": r["valor"]} for r in reps]}
    return out
