"""Warm-up del LLM de Consulta al arrancar el backend.

En 139 gemma tarda ~342 s en cargar en frío (medido). Sin esto, la 1ª petición real (el intro
cordial de jerarquizar, la respuesta OUT) cae dentro de esa ventana de carga y expira su timeout
→ fallback (sin cordialidad). Este ping de carga absorbe el frío FUERA de una petición de usuario;
con keep_alive=-1 el modelo queda residente. Corre en un HILO daemon → no bloquea el arranque del
backend, y jamás lo rompe (best-effort, traga toda excepción).

🔑 keep_alive=-1 es deliberado: un ping SIN keep_alive resetearía el keep-alive de gemma@139 al
default (5 min) → se descargaría y volvería el frío. Con -1 se mantiene el residente-infinito.
"""
import json
import threading
import urllib.request

from app.core.config import get_settings


def _ping():
    s = get_settings()
    try:
        body = json.dumps({
            "model": s.consulta_llm_model,
            "prompt": "ok",
            "stream": False,
            "options": {"num_predict": 1},
            "keep_alive": -1,          # residente indefinido (no resetear el keep-alive de 139)
        }).encode()
        req = urllib.request.Request(s.consulta_ollama_url, data=body,
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=600).read()   # tolera el frío (~342s); está en su hilo
    except Exception:
        pass   # best-effort: el warm-up nunca rompe el arranque ni una petición


def warmup_llm():
    """Dispara el ping de carga en 2º plano. No bloquea el arranque. Gated por CONSULTA_WARMUP."""
    if not get_settings().consulta_warmup:
        return
    threading.Thread(target=_ping, name="consulta-warmup", daemon=True).start()


# --- Warm-up de las cachés de DIFERIDAS [2026-08-26] --------------------------------------------
# Mismo problema que el LLM, otra fuente. `causal` es la sub-intención DEFAULT de Analizar y llama
# SIEMPRE a split_planeado() + impacto_historico() (respuesta_analizar.py:288-292). Sin entidad
# nombrada el filtro queda en `WHERE 1=1` → DOS scans completos de AVM_DATADIF (1,14 M filas, BD de
# ~954 MB, sin índice que cubra CAUSE_NIVEL3/4 ni GAS_PERDIDO) dentro de la petición del usuario.
# El proxy Flask corta a los 90 s (routes/api.py:743) y el chat pinta "SIN RESPUESTA".
#
# 🔑 Por qué SOLO la primera: las dos funciones cachean en proceso y el histórico es INMUTABLE, así
# que la 2ª pregunta es cache-HIT y responde al instante. Cada reinicio del backend vacía la caché
# y el ciclo vuelve a empezar — de ahí que se sienta como "siempre la primera pregunta".
#
# Este warm-up paga esos scans en un hilo daemon al arrancar, cuando nadie está esperando. Se
# calienta el ámbito GLOBAL (campos=[]) porque es el que dispara la pregunta sin entidad, que es
# justo el caso más caro (sin filtro = la tabla entera).
def _cachear_diferidas():
    # Import LOCAL, no de módulo: warmup.py lo importa main.py al arrancar, y `diferidas` resuelve
    # rutas a nivel de módulo. Mantener el import aquí deja el arranque sin dependencia nueva.
    try:
        from app.features.consulta_v2.analizar import diferidas as _dif
        _dif.split_planeado([])
        _dif.impacto_historico([])
    except Exception:
        pass   # best-effort, igual que _ping: un warm-up JAMÁS rompe el arranque


def warmup_diferidas():
    """Precalienta _SPLIT_CACHE/_IMPACTO_CACHE en 2º plano. Mismo interruptor que el LLM
    (CONSULTA_WARMUP): un solo flag para "precalentar al arrancar".

    Sin BD (dev) las dos funciones retornan "no disponible" al instante — el hilo muere en
    milisegundos y no deja nada envenenado: impacto_historico NO cachea ese caso a propósito."""
    if not get_settings().consulta_warmup:
        return
    threading.Thread(target=_cachear_diferidas, name="consulta-warmup-dif", daemon=True).start()
