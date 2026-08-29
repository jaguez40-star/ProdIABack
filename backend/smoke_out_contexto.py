"""smoke_out_contexto.py — humo end-to-end de OUT con contexto + rechazo honesto (commit 3bbae0f).

Prueba el flujo CONVERSACIONAL de dos turnos que los tests unitarios NO cubren: que `_CTX` se pobló
en el turno anterior y que la rama OUT de maquina_q enruta a la Pieza B (determinista) o a la A (LLM).

CÓMO CORRERLO (en el servidor de pruebas, con el backend FastAPI arriba):
    uv run python smoke_out_contexto.py
    uv run python smoke_out_contexto.py --base-url http://localhost:5029/api   # vía proxy Flask
    uv run python smoke_out_contexto.py --base-url http://10.100.26.139:8000   # backend remoto

Solo hace HTTP (urllib, stdlib) → no importa el paquete `app`, corre con cualquier Python.

⚠️ /consulta2/preguntar registra en core.clasificacion_log (log=True, como todo tráfico real). Este
script usa el usuario "smoke_out" para poder limpiar después:
    DELETE FROM core.clasificacion_log WHERE usuario = 'smoke_out';

Salida: un check por línea (PASS/FAIL/INFO) + resumen. Exit 0 solo si TODOS los asserts DUROS pasan.
Los checks de la Pieza A son INFORMATIVOS: dependen de Ollama caliente (si está frío, cae al
TEXTO_FALLBACK estático y A no es verificable — el script lo detecta y lo dice, sin marcar FAIL).
"""
import argparse
import json
import os
import sys
import urllib.request

# El floor estático de respuesta_out.TEXTO_FALLBACK (copiado verbatim para detectar "Ollama frío").
TEXTO_FALLBACK = ("Esa pregunta está fuera del contexto de este asistente. Puedo ayudarte con "
                  "estructura organizacional, cifras de producción o análisis de desempeño. "
                  "¿Cuál de esos temas te interesa?")

_OK, _FAIL, _INFO = "PASS", "FAIL", "INFO"
_fallos = 0


def _log(estado, msg):
    global _fallos
    if estado == _FAIL:
        _fallos += 1
    print(f"[{estado}] {msg}")


def preguntar(base_url, texto, cid, usuario="smoke_out", timeout=180):
    """POST {base}/consulta2/preguntar → dict de clasificar(). Lanza si la red/HTTP falla."""
    url = base_url.rstrip("/") + "/consulta2/preguntar"
    body = json.dumps({"texto": texto, "conversation_id": cid, "usuario": usuario}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def firma_de_B(msg):
    """Heurística de que un mensaje vino de la Pieza B (no_soportado.mensaje): plantilla fija."""
    return msg.startswith("Sobre ") and "solo puedo darte" in msg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=os.environ.get("SMOKE_BASE_URL", "http://localhost:8000"),
                    help="Base del API (sin /consulta2). Para el proxy Flask: http://localhost:5029/api")
    args = ap.parse_args()
    base = args.base_url
    suf = os.urandom(3).hex()                 # sufijo único: evita colisión de _CTX entre corridas
    cid_hilo = f"smoke-hilo-{suf}"            # conversación CON contexto (turnos 1→2→3)
    cid_frio = f"smoke-frio-{suf}"            # conversación NUEVA, sin turno previo

    print(f"== Humo OUT-contexto ==  base={base}  cid_hilo={cid_hilo}\n")

    # --- Turno 1: resolver una entidad → puebla _CTX --------------------------------------------
    try:
        t1 = preguntar(base, "produccion de Rubiales", cid_hilo)
    except Exception as e:
        _log(_FAIL, f"Turno 1 no respondió ({type(e).__name__}: {e}). ¿Backend arriba en {base}?")
        print("\nAbortado: sin turno 1 no hay contexto que probar.")
        sys.exit(1)
    _log(_INFO, f"T1 'produccion de Rubiales' → grupo={t1.get('grupo')} "
                f"entidad={t1.get('entidad_cruda')}")
    if (t1.get("entidad_cruda") or "").upper() != "RUBIALES":
        _log(_INFO, "  (T1 no resolvió RUBIALES; los turnos siguientes pueden no tener contexto)")

    # --- Turno 2 (MISMO cid): PIEZA B — rango de días → rechazo honesto determinista ------------
    t2 = preguntar(base, "en mayo, los 17 dias cuanto ha producido?", cid_hilo)
    m2 = t2.get("mensaje") or ""
    _log(_INFO, f"T2 → grupo={t2.get('grupo')} capa={t2.get('capa_resolutora')}")
    _log(_INFO, f"T2 mensaje: {m2}")
    ok = t2.get("grupo") == "desconocido"
    _log(_OK if ok else _FAIL, "T2 grupo == 'desconocido'")
    ok = t2.get("capa_resolutora") == "regex+filtro"
    _log(_OK if ok else _FAIL, "T2 capa == 'regex+filtro' (aisla B sin depender del LLM)")
    for needle in ("RUBIALES", "rango de días", "mes completo"):
        ok = needle in m2
        _log(_OK if ok else _FAIL, f"T2 mensaje contiene «{needle}»")
    ok = "¿Quieres" not in m2
    _log(_OK if ok else _FAIL, "T2 NO termina en pregunta sí/no (H1: evita el drill _AFIRM)")
    ok = not any(c.isdigit() for c in m2)
    _log(_OK if ok else _FAIL, "T2 mensaje sin dígitos (plantilla determinista)")

    # --- Turno 3 (MISMO cid): PIEZA A — off-topic reconoce el hilo (INFORMATIVO, requiere Ollama) -
    t3 = preguntar(base, "y como esta el clima hoy?", cid_hilo)
    m3 = t3.get("mensaje") or ""
    _log(_INFO, f"T3 'clima' → grupo={t3.get('grupo')}")
    _log(_INFO, f"T3 mensaje: {m3}")
    if t3.get("grupo") != "desconocido":
        _log(_FAIL, "T3 grupo == 'desconocido'")
    elif m3.strip() == TEXTO_FALLBACK:
        _log(_INFO, "T3 devolvió el TEXTO_FALLBACK estático → Ollama frío/off; Pieza A NO verificable "
                    "aquí (calienta gemma4 + CONSULTA_OUT_LLM=true y reintenta).")
    else:
        _log(_INFO, "T3 lo redactó el LLM. Revisa a OJO que reconozca el hilo (Rubiales) y NO invente "
                    "periodos ('el mes pasado'). No hay assert automático sobre prosa libre.")

    # --- Turno negativo (cid NUEVO, SIN contexto): B NO debe afirmar 'no soportado' --------------
    # La frase lleva "cuanto" para forzar la ruta OUT determinista (CUANT[OA]S? genérico + sin
    # entidad + sin vocabulario → desconocido/regex+filtro), que es JUSTO el camino que B guarda.
    # Sin ese disparador, la Capa 2 (LLM) puede enrutarla a cuantificar y no probaríamos el gate.
    tn = preguntar(base, "cuanto en el primer trimestre?", cid_frio)
    mn = tn.get("mensaje") or ""
    _log(_INFO, f"T-neg (sin contexto) → grupo={tn.get('grupo')} capa={tn.get('capa_resolutora')}")
    _log(_INFO, f"T-neg mensaje: {mn}")
    ok = tn.get("grupo") == "desconocido"
    _log(_OK if ok else _FAIL, "T-neg grupo == 'desconocido' (llega a la ruta OUT)")
    ok = not firma_de_B(mn)
    _log(_OK if ok else _FAIL, "T-neg NO usa el rechazo honesto de B (sin entidad en contexto no se "
                               "afirma 'no soportado' — limitación aceptada)")

    # --- Resumen --------------------------------------------------------------------------------
    print()
    if _fallos:
        print(f"RESULTADO: {_fallos} check(s) DUROS fallaron.  ✗")
        sys.exit(1)
    print("RESULTADO: todos los checks duros PASARON.  ✓")
    print("Recuerda limpiar la libreta:  DELETE FROM core.clasificacion_log WHERE usuario='smoke_out';")


if __name__ == "__main__":
    main()
