"""respuesta_base.py — envoltorio cordial COMPARTIDO (Motor Q v2).

intro (LLM, saludo dinámico) + cuerpo (hechos VERBATIM de Python) + cierre (Python, exacto).
Extraído de respuesta_jerarquizar.py para que jerarquizar y cuantificar compartan la misma máquina.
El LLM escribe SOLO el intro; jamás toca hechos/números. Si el flag está off o el LLM falla → intro "".
"""
import json
import urllib.error
import urllib.request

from app.core.config import get_settings

_s = get_settings()
_OLLAMA_URL = _s.consulta_ollama_url
_MODELO = _s.consulta_llm_model
_KEEP_ALIVE = _s.keep_alive_ollama   # reafirma la residencia del warm-up (sin esto vuelve el frío)
_ENV_TIMEOUT = 30


def _llm(prompt: str) -> str:
    body = json.dumps({
        "model": _MODELO, "prompt": prompt, "stream": False, "format": "json",
        "keep_alive": _KEEP_ALIVE,
        "options": {"temperature": 0.8, "num_predict": 160},
    }).encode()
    req = urllib.request.Request(_OLLAMA_URL, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=_ENV_TIMEOUT) as r:
        return json.load(r).get("response", "")


def intro_llm(prompt: str, activo: bool) -> str:
    """Intro cálido (una frase). '' si el flag está off o el LLM falla. El prompt debe pedir
    {"intro":"..."} con format:json. NUNCA lanza: cualquier fallo → '' (fallback determinista)."""
    if not activo:
        return ""
    try:
        data = json.loads((_llm(prompt) or "").strip())
        return (data.get("intro") or "").strip() if isinstance(data, dict) else ""
    except (json.JSONDecodeError, TypeError, urllib.error.URLError, OSError, TimeoutError):
        return ""
    except Exception:
        return ""


def envolver(intro: str, body: str, cierre: str) -> str:
    """intro (si hay) + body VERBATIM + cierre. Idéntico al _envolver de jerarquizar."""
    return f"{intro}\n\n{body}\n\n{cierre}" if intro else f"{body}\n\n{cierre}"
