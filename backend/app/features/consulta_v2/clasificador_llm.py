"""Capa 2 del clasificador — LLM clasificador CERRADO (fallback; solo si la regex no atrapó).

El LLM elige entre 4 salidas cerradas (3 grupos + desconocido) y extrae la entidad si la hay.
NO redacta, NO calcula, NO decide rutas. Parseo defensivo: JSON malformado, grupo fuera del
enum, timeout o conexión caída → 'desconocido' + diag (H5: el diag se persiste en
clasificacion_log.llm_diag — sin él, un timeout por arranque en frío de gemma@139 parecería
un error del clasificador al revisar el lote). Jamás adivinar, jamás reintentar un JSON malo.
"""
import json
import urllib.request
import urllib.error

from app.core.config import get_settings

# A5: prompt como constante separada al tope del módulo — corte limpio para una migración
# futura a un almacén de prompts de v2. NO va en master_prompts.yaml (lo lee solo el
# chatbot legacy de Flask — decisión H7 del 30-jul).
PROMPT_CLASIFICADOR = """Eres un clasificador de preguntas para un sistema de producción petrolera.
Responde SOLO con JSON válido. Sin explicaciones, sin markdown.

Grupos:
1. jerarquizar — estructura organizacional, pertenencia, identidad de entidades
   (qué campos tiene un activo, a qué pertenece algo, qué es algo)
2. cuantificar — magnitudes medibles: valores, conteos, acumulados, series
   temporales, variaciones (cuánto produjo, cuántos pozos, cómo varió)
3. analizar — causas, explicaciones, proyecciones, cumplimiento de metas,
   acciones recomendadas (por qué, cómo vamos, vamos a llegar, qué hacer)

Si la pregunta NO es de producción petrolera ni de la información del sistema (matemáticas,
geografía, cultura general, entretenimiento, finanzas no petroleras, saludos, texto suelto,
un nombre a secas): "desconocido".

CUIDADO con palabras que parecen del negocio pero NO lo son en ese contexto: los "campos" de
un formulario, los "pozos" de una casa o sépticos, los "activos" financieros de un banco, el
"cierre" de la bolsa. Si el tema real no es producción petrolera de Ecopetrol → "desconocido".

Formato de respuesta (SOLO esto):
{{"grupo": "<jerarquizar|cuantificar|analizar|desconocido>", "entidad": "<string|null>"}}

Pregunta: {texto}
JSON:"""

GRUPOS_VALIDOS = {"jerarquizar", "cuantificar", "analizar", "desconocido"}

_s = get_settings()
OLLAMA_URL = _s.consulta_ollama_url   # .env: CONSULTA_OLLAMA_URL (dev qwen local · 139 gemma4)
MODELO = _s.consulta_llm_model        # .env: CONSULTA_LLM_MODEL
KEEP_ALIVE = _s.keep_alive_ollama     # reafirma la residencia del warm-up (sin esto vuelve el frío)

# H5: la clasificación son ~10 tokens de salida — num_predict corto y timeout de 30s para
# que el arranque en frío de gemma en 139 (load ~342s medido el 29-jul) no cuelgue el chat:
# el timeout cae a 'desconocido' con diag='timeout' y la libreta lo deja trazado.
TIMEOUT_S = 30
NUM_PREDICT = 64


def _llm(texto: str) -> str:
    body = json.dumps({
        "model": MODELO,
        "prompt": PROMPT_CLASIFICADOR.format(texto=texto),
        "stream": False,
        # gotcha conocido (bde9524): gemma4@139 devuelve VACÍO en texto plano — format:json.
        "format": "json",
        "keep_alive": KEEP_ALIVE,
        "options": {"temperature": 0, "num_predict": NUM_PREDICT},
    }).encode()
    req = urllib.request.Request(OLLAMA_URL, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
        return json.load(r).get("response", "")


def parsear(salida: str) -> dict:
    """Parseo defensivo de la respuesta del LLM. NUNCA lanza; nunca adivina.
    Devuelve {"grupo": ..., "entidad": ..., "diag": None|motivo}."""
    try:
        data = json.loads((salida or "").strip())
    except (json.JSONDecodeError, TypeError):
        return {"grupo": "desconocido", "entidad": None, "diag": "json_invalido"}
    if not isinstance(data, dict) or data.get("grupo") not in GRUPOS_VALIDOS:
        return {"grupo": "desconocido", "entidad": None, "diag": "grupo_invalido"}
    ent = data.get("entidad")
    if ent is not None and not isinstance(ent, str):
        ent = None
    if isinstance(ent, str) and not ent.strip():
        ent = None
    return {"grupo": data["grupo"], "entidad": ent, "diag": None}


def clasificar_capa2(texto: str) -> dict:
    """Invoca al LLM y parsea. Timeout/conexión caída → desconocido + diag (sin reintentos:
    un JSON malo es determinista; un frío de gemma se resuelve solo en la siguiente pregunta)."""
    try:
        salida = _llm(texto)
    except TimeoutError:
        return {"grupo": "desconocido", "entidad": None, "diag": "timeout"}
    except (urllib.error.URLError, OSError) as e:
        # urllib envuelve el timeout de socket en URLError(reason=timeout) según la etapa
        motivo = "timeout" if "timed out" in str(e).lower() else "conexion"
        return {"grupo": "desconocido", "entidad": None, "diag": motivo}
    except Exception:
        return {"grupo": "desconocido", "entidad": None, "diag": "conexion"}
    return parsear(salida)
