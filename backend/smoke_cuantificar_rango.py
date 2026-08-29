"""smoke_cuantificar_rango.py — humo end-to-end del fix bug #5 (commit 2524259).

Verifica que Cuantificar RECHAZA honesto un rango de días/trimestre/semana (en vez de degradar en
silencio al mes completo) y que NO sobre-rechaza lo que sí soporta (N2 acumulado del año, N1 mes).

A diferencia del humo de OUT, aquí NO hace falta contexto multi-turno: la entidad va DENTRO del texto,
así que cada caso es una sola petición. Igual comparte conversation_id por prolijidad.

CÓMO CORRERLO (servidor de pruebas, backend FastAPI arriba):
    uv run python smoke_cuantificar_rango.py --base-url http://localhost:5030
    uv run python smoke_cuantificar_rango.py --base-url http://localhost:5029/api   # vía proxy Flask

Solo urllib (stdlib). ⚠️ /consulta2/preguntar registra en core.clasificacion_log (usuario 'smoke_cuant'):
    DELETE FROM core.clasificacion_log WHERE usuario = 'smoke_cuant';

Salida: un check por caso (PASS/FAIL/INFO) + resumen. Exit 0 solo si TODOS los duros pasan.
"""
import argparse
import json
import os
import sys
import urllib.request

_OK, _FAIL, _INFO = "PASS", "FAIL", "INFO"
_fallos = 0


def _log(estado, msg):
    global _fallos
    if estado == _FAIL:
        _fallos += 1
    print(f"[{estado}] {msg}")


def preguntar(base_url, texto, cid, usuario="smoke_cuant", timeout=180):
    url = base_url.rstrip("/") + "/consulta2/preguntar"
    body = json.dumps({"texto": texto, "conversation_id": cid, "usuario": usuario}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def firma_rechazo(msg):
    """Firma del rechazo honesto de no_soportado.mensaje (rango/trimestre/semana)."""
    return msg.startswith("Sobre ") and "solo puedo darte" in msg


# (texto, espera_rechazo, etiqueta)
CASOS = [
    ("cuanto produjo Rubiales entre el 5 y el 10 de mayo", True,  "rango de días"),
    ("cuanto en el primer trimestre de Rubiales",          True,  "trimestre"),
    ("cuanto produjo Rubiales esta semana",                True,  "semana"),
    ("cuanto acumulo Rubiales en el ano 2026",             False, "año → N2 acumulado (NO rechazar)"),
    ("cuanto produjo Rubiales en mayo",                    False, "mes puntual N1 (NO rechazar)"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=os.environ.get("SMOKE_BASE_URL", "http://localhost:8000"),
                    help="Base del API (sin /consulta2). Directa FastAPI o proxy Flask (.../api)")
    args = ap.parse_args()
    base = args.base_url
    cid = "smoke-cuant-" + os.urandom(3).hex()
    print(f"== Humo Cuantificar bug #5 ==  base={base}  cid={cid}\n")

    for texto, espera_rechazo, etiqueta in CASOS:
        try:
            d = preguntar(base, texto, cid)
        except Exception as e:
            _log(_FAIL, f"«{texto}» no respondió ({type(e).__name__}: {e}). ¿Backend en {base}?")
            continue
        grupo = d.get("grupo")
        panel = d.get("panel")
        msg = d.get("mensaje") or ""
        _log(_INFO, f"[{etiqueta}] grupo={grupo} panel={'None' if panel is None else panel.get('tipo')}")
        _log(_INFO, f"    «{texto}»")
        _log(_INFO, f"    → {msg[:110]}{'…' if len(msg) > 110 else ''}")

        if espera_rechazo:
            ok = grupo == "cuantificar"
            _log(_OK if ok else _FAIL, f"    [{etiqueta}] grupo == 'cuantificar'")
            ok = panel is None
            _log(_OK if ok else _FAIL, f"    [{etiqueta}] panel is None (no pinta una cifra falsa)")
            ok = firma_rechazo(msg)
            _log(_OK if ok else _FAIL, f"    [{etiqueta}] mensaje = rechazo honesto (no un número)")
            ok = "RUBIALES" in msg
            _log(_OK if ok else _FAIL, f"    [{etiqueta}] nombra la entidad (RUBIALES)")
        else:
            # Regresión: NO debe sobre-rechazar. Lo importante es que NO salga la firma de rechazo.
            ok = not firma_rechazo(msg)
            _log(_OK if ok else _FAIL, f"    [{etiqueta}] NO se rechazó por forma (fix no regresó lo soportado)")
            if panel is None:
                _log(_INFO, "    (panel None: probable falta de datos para esa entidad/mes en este entorno; "
                            "el check duro es 'no rechazó', que sí pasó)")
        print()

    if _fallos:
        print(f"RESULTADO: {_fallos} check(s) DUROS fallaron.  ✗")
        sys.exit(1)
    print("RESULTADO: todos los checks duros PASARON.  ✓")
    print("Limpieza:  DELETE FROM core.clasificacion_log WHERE usuario='smoke_cuant';")


if __name__ == "__main__":
    main()
