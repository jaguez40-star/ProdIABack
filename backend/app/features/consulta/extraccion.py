import json, re, urllib.request
from app.features.consulta.normaliza import norm
from app.core.config import get_settings

_s = get_settings()
OLLAMA_URL = _s.consulta_ollama_url   # .env: CONSULTA_OLLAMA_URL (ej. http://10.100.26.139:11434/api/generate)
MODELO = _s.consulta_llm_model        # .env: CONSULTA_LLM_MODEL (dev qwen2.5:3b · 139 gemma4:latest)

_PROMPT = """Eres un extractor de datos. SOLO devuelves JSON, nunca explicaciones ni texto adicional.

Campos — REGLA GENERAL: si el texto NO menciona el dato con esa palabra o una muy cercana, el campo es
null. Está PROHIBIDO adivinar, suponer un valor "típico" o usar lo que tú sepas del mundo real: la sola
palabra "producción" NUNCA implica un producto, un nivel, ni una agregación por sí sola.
- entidad: nombre propio o código de la entidad petrolera mencionada, copiado TAL CUAL aparece en el texto
  (conserva mayúsculas/minúsculas y errores de tipeo, NO corrijas la ortografía). null si el texto no nombra
  ninguna (p.ej. se refiere a "eso"/"ahí" sin decir el nombre).
- nivel: "vicepresidencia"|"gerencia"|"activo"|"campo"|"pozo"|"filial"|null — SOLO si el texto trae esa
  palabra EXACTA junto al nombre (ej. "el campo X", "la gerencia Y", "el pozo Z"). Si el texto solo da el
  nombre sin esa palabra (ej. "Hocol", "Rubiales", "America"), usa null aunque tú creas saber qué tipo de
  entidad es — eso lo decide otro sistema, no tú.
  "área" es SINÓNIMO de "activo" en este dominio: si el texto dice "el área X", el nivel es "activo".
- producto: "aceite"|"agua"|"gas"|"blancos"|null — SOLO si el texto menciona alguna de estas palabras (o
  "crudo"/"petróleo" = "aceite"). Las palabras "producción"/"produjo"/"produce" NO son un producto → null.
- periodo: el texto que describe el periodo de tiempo, SIN el artículo inicial ("el"/"la"), o null si no hay
  ninguna referencia temporal. Palabras de agregación (acumulado/total/promedio) NO son un periodo.
- agregacion: "promedio_diario" SOLO si el texto dice "promedio" o "tasa diaria"; "acumulado" SOLO si dice
  "acumulado(a)", "total" o "suma"; si ninguna de esas palabras aparece, usa null (NO asumas "acumulado" por
  defecto).

Ejemplos (fíjate en los null — son la mayoría de los campos en la mayoría de los casos):
Texto: producción de Rubiales
JSON: {{"entidad": "Rubiales", "nivel": null, "producto": null, "periodo": null, "agregacion": null}}

Texto: producción del campo Castilla
JSON: {{"entidad": "Castilla", "nivel": "campo", "producto": null, "periodo": null, "agregacion": null}}

Texto: producción de Hocol este mes
JSON: {{"entidad": "Hocol", "nivel": null, "producto": null, "periodo": "este mes", "agregacion": null}}

Texto: produccion de rubialess
JSON: {{"entidad": "rubialess", "nivel": null, "producto": null, "periodo": null, "agregacion": null}}

Texto: cuánto crudo produjo el pozo La Hocha el mes pasado
JSON: {{"entidad": "La Hocha", "nivel": "pozo", "producto": "aceite", "periodo": "mes pasado", "agregacion": null}}

Texto: y el gas ahí?
JSON: {{"entidad": null, "nivel": null, "producto": "gas", "periodo": null, "agregacion": null}}

Texto: promedio diario de crudo en Castilla en marzo
JSON: {{"entidad": "Castilla", "nivel": null, "producto": "aceite", "periodo": "marzo", "agregacion": "promedio_diario"}}

Texto: producción total de blancos en marzo 2026
JSON: {{"entidad": null, "nivel": null, "producto": "blancos", "periodo": "marzo 2026", "agregacion": "acumulado"}}

Texto: cómo está el área Chichimene
JSON: {{"entidad": "Chichimene", "nivel": "activo", "producto": null, "periodo": null, "agregacion": null}}

Texto: producción del pozo Rubiales 12
JSON: {{"entidad": "Rubiales 12", "nivel": "pozo", "producto": null, "periodo": null, "agregacion": null}}

Ahora el texto real. Responde ÚNICAMENTE el JSON de una línea, sin markdown, sin comillas triples, sin explicación.
Texto: {texto}
JSON:"""

# Grounding (Python, no LLM): un valor categórico solo se acepta si su palabra clave aparece
# literalmente en el texto del usuario — evita que el LLM "rellene" producto/nivel/agregación por
# prior del dominio (ej. "producción" -> "aceite") en vez de por lo que el texto realmente dice.
_PRODUCTO_KW = {"aceite": ["ACEITE", "CRUDO", "PETROLEO"], "gas": ["GAS"],
                "agua": ["AGUA"], "blancos": ["BLANCO"]}
# 2026-07-16: "area" dejó de ser un nivel propio (grupo1 no es el Activo ni existe en el negocio).
# La palabra "área" se conserva como SINÓNIMO de usuario de "activo" (así lo usa el negocio), así que
# "el área Chichimene" groundea nivel="activo" y resuelve por core.map_campo_activo.
_NIVEL_KW = {"vicepresidencia": ["VICEPRESIDENCIA"], "gerencia": ["GERENCIA"],
             "activo": ["ACTIVO", "AREA"], "campo": ["CAMPO"], "pozo": ["POZO"],
             "filial": ["FILIAL", "EMPRESA"]}
_AGREGACION_KW = {"promedio_diario": ["PROMEDIO", "TASA"], "acumulado": ["ACUMULAD", "TOTAL", "SUMA"]}

def _grounded(texto_norm: str, valor, kw_map: dict):
    if not valor:
        return None
    kws = kw_map.get(str(valor).lower())
    if not kws or not any(kw in texto_norm for kw in kws):
        return None
    return valor

def _llm(texto: str) -> str:
    body = json.dumps({"model": MODELO, "prompt": _PROMPT.format(texto=texto), "stream": False,
                        "options": {"temperature": 0}}).encode()
    req = urllib.request.Request(OLLAMA_URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r).get("response", "")

def extraer_json(salida: str) -> dict | None:
    m = re.search(r"\{.*\}", salida, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None

def extraer(texto: str) -> dict:
    """Devuelve slots crudos. Si el LLM falla, {entidad:null,...} → la máquina pedirá reformular.
    NUNCA lanza al usuario un error feo (regla madre). Los campos categóricos (producto/nivel/agregación)
    se descartan si su palabra clave no aparece literalmente en el texto (grounding, ver _grounded)."""
    base = {"entidad": None, "nivel": None, "producto": None, "periodo": None, "agregacion": None}
    got = extraer_json(_llm(texto)) or {}
    base.update({k: got.get(k) for k in base if k in got})
    texto_norm = norm(texto)
    base["producto"] = _grounded(texto_norm, base["producto"], _PRODUCTO_KW)
    base["nivel"] = _grounded(texto_norm, base["nivel"], _NIVEL_KW)
    base["agregacion"] = _grounded(texto_norm, base["agregacion"], _AGREGACION_KW)
    if base["periodo"] and norm(base["periodo"]) not in texto_norm:
        base["periodo"] = None
    return base
