"""Respuesta del chat al grupo OUT (desconocido) — Motor Q v2.

Cuando la clasificación cae en 'desconocido', el chat responde UN texto (no chips) que:
recalca que la pregunta está FUERA del contexto de este chatbot, ofrece los tres temas que sí
maneja (estructura organizacional, cifras de producción, análisis de desempeño) y pregunta en
cuál está interesado. Lo redacta el LLM; si falla o el flag está off, se sirve TEXTO_FALLBACK
(fallback D4 — OUT nunca se queda sin respuesta).

Frontera dura: NO responde la pregunta ajena. El prompt es cerrado y firme para que un modelo
débil (qwen2.5:3b) no se deslice a contestar "la inflación subió porque…" — eso convertiría al
bot en un chatbot general y tiraría abajo el filtro de dominio.

Reusa la plomería de Ollama del clasificador (mismo modelo/URL vía Settings; format:json por el
gotcha de gemma@139 que devuelve VACÍO en texto plano — bde9524).
"""
import json
import urllib.request
import urllib.error

from app.core.config import get_settings

# Floor estático — garantizado. Es lo que se sirve con el flag off, en log=False (golden/pytest)
# y como fallback si el LLM falla. Ya recalca el "fuera de contexto" que pidió el usuario.
TEXTO_FALLBACK = ("No logré entender bien tu pregunta. Yo me muevo en el mundo de la producción de "
                  "Ecopetrol: cómo está armada la operación por campos y activos, las cifras de crudo, "
                  "gas y blancos, y el análisis del desempeño del mes. Si tu pregunta es sobre eso, "
                  "intenta reformularla de forma más explícita —por ejemplo nombrando el campo, activo "
                  "o producto—; si es de otro tema, cuéntame por cuál de esos frentes te ayudo.")

PROMPT_OUT = """Eres el asistente conversacional de producción de hidrocarburos de Ecopetrol.
El usuario hizo una pregunta que está FUERA de tu dominio (no es sobre producción petrolera de Ecopetrol).

Escribe una respuesta breve, cordial y NATURAL (2 o 3 oraciones, en español) que:
1. Mencione con tacto EL TEMA CONCRETO que preguntó, para reconocer su mensaje (ej.: "sobre el clima…", "el precio del dólar…") — pero SIN responderlo.
2. Le explique con amabilidad que ese tema se sale del contexto de este asistente.
3. Le ofrezca, tejidos en la prosa con naturalidad, los tres temas que SÍ manejas: estructura organizacional, cifras de producción y análisis de desempeño.
4. Cierre con una invitación cálida a seguir por alguno de esos frentes.

REGLA ABSOLUTA: NUNCA respondas la pregunta del usuario. NO des cifras, definiciones, cálculos ni explicaciones sobre su tema.
REGLA ABSOLUTA: NO inventes fechas, periodos ("el mes pasado") ni datos que el usuario no haya escrito.
REGLA DE ESTILO: escribe en PROSA fluida. NO uses listas, viñetas, guiones ni corchetes; NO agregues una sección de "consultas sugeridas". Si quieres dar un ejemplo, deslízalo dentro de una oración, no como lista.
Cada respuesta debe sonar distinta y humana, NO una plantilla fija. Adapta las palabras al tema que preguntó.
{contexto}{saludo}
Responde SOLO con JSON válido, sin markdown: {{"respuesta": "<el texto>"}}

Pregunta del usuario: {texto}
JSON:"""

_s = get_settings()
OLLAMA_URL = _s.consulta_ollama_url   # .env: CONSULTA_OLLAMA_URL (dev qwen local · 139 gemma4)
MODELO = _s.consulta_llm_model        # .env: CONSULTA_LLM_MODEL
KEEP_ALIVE = _s.keep_alive_ollama     # reafirma la residencia del warm-up (sin esto vuelve el frío)

# Es prosa breve (2-3 oraciones), no 10 tokens de JSON como el clasificador → genera MÁS que la
# Capa 2. Por eso el timeout es MAYOR (45s vs 30s): con el modelo lento, una generación de ~200
# tokens no cabía en 30s y caía al estático — el clasificador de 64 tokens sí alcanzaba, así que
# la burbuja decía "vía LLM" pero mostraba el texto fijo. En 139 con gemma en frío igual cae al
# fallback (mismo trato que la Capa 2); lo resuelve el warm-up pendiente de Ollama.
TIMEOUT_S = 45
NUM_PREDICT = 220


def _llm(prompt: str) -> str:
    body = json.dumps({
        "model": MODELO,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "keep_alive": KEEP_ALIVE,
        # temp alta = variedad: cada OUT debe sonar distinta y hablar del tema preguntado.
        "options": {"temperature": 0.8, "num_predict": NUM_PREDICT},
    }).encode()
    req = urllib.request.Request(OLLAMA_URL, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
        return json.load(r).get("response", "")


def _linea_contexto(contexto) -> str:
    """Una línea de CONTEXTO para el prompt, o "" si no hay entidad reciente. `contexto` es el dict
    que maquina_q._CTX guarda por conversación (jerarquizar: {entidad,nivel,hijos,ofrece_produccion};
    cuantificar: {grupo,entidad,producto}). Lee SOLO entidad/producto — jamás cifras, y nunca la
    clave `hijos` (un set grande que no aporta al saludo)."""
    ent = (contexto or {}).get("entidad")
    if not ent:
        return ""
    prod = (contexto or {}).get("producto")
    extra = f" (producto {prod})" if prod and prod != "crudo" else ""
    return (f"CONTEXTO: la conversación reciente trató sobre «{ent}»{extra}. Si la nueva pregunta "
            f"parece continuar ese hilo, reconócelo con naturalidad; si es otro tema, ignora este "
            f"contexto. NO uses el contexto para inventar cifras.\n")


def redactar_out(texto: str, usuario: str | None = None, contexto=None) -> dict:
    """Redacta la respuesta al grupo OUT. NUNCA lanza. `contexto` = dict de maquina_q._CTX (o None):
    su entidad se inyecta en el prompt para reconocer el hilo SIN romper la frontera dura (el LLM
    sigue teniendo prohibido responder la pregunta ajena).
    Devuelve {"texto": str, "fuente": "llm"|"fallback", "diag": None|motivo}."""
    if not _s.consulta_out_llm:
        return {"texto": TEXTO_FALLBACK, "fuente": "fallback", "diag": "flag_off"}
    saludo = f"Dirígete al usuario por su nombre: {usuario}." if usuario else ""
    prompt = PROMPT_OUT.format(texto=texto, saludo=saludo, contexto=_linea_contexto(contexto))
    try:
        salida = _llm(prompt)
    except TimeoutError:
        return {"texto": TEXTO_FALLBACK, "fuente": "fallback", "diag": "timeout"}
    except (urllib.error.URLError, OSError) as e:
        motivo = "timeout" if "timed out" in str(e).lower() else "conexion"
        return {"texto": TEXTO_FALLBACK, "fuente": "fallback", "diag": motivo}
    except Exception:
        return {"texto": TEXTO_FALLBACK, "fuente": "fallback", "diag": "conexion"}
    # Parseo defensivo (mismo criterio que clasificador_llm.parsear): JSON malo → fallback, jamás
    # se muestra la salida cruda del modelo.
    try:
        data = json.loads((salida or "").strip())
        resp = data.get("respuesta") if isinstance(data, dict) else None
    except (json.JSONDecodeError, TypeError):
        resp = None
    if not isinstance(resp, str) or not resp.strip():
        return {"texto": TEXTO_FALLBACK, "fuente": "fallback", "diag": "json_invalido"}
    return {"texto": resp.strip(), "fuente": "llm", "diag": None}
