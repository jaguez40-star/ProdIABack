"""Tests de la tesis del Análisis Ejecutivo: que el prompt NUNCA le pida a Gemma un rezago
que los datos no muestran (2026-07-16).

Origen: CASTILLA como Campo (Mayo 2026, corte 17/31) tiene CRUDO al 102.7% y GAS/BLANCOS sin meta
→ `sintesis` y `detalle_por_producto` vacíos. El prompt igual exigía "la historia del mes" y
"contrasta lo transitorio con lo estructural", así que Gemma fabricó un "déficit significativo" y
luego descarriló el JSON. El JSON roto era el síntoma; la alucinación, la enfermedad.

Funciones puras: no tocan BD ni LLM.
"""
import pytest

from app.features.analisis import api
from app.features.analisis.api import _situacion_general, _reglas_tesis


def _t(producto, pct):
    return {"producto": producto, "valor_pct": pct}


# --- CASTILLA campo: el caso real que rompió (CRUDO 102.7%, GAS/BLANCOS sin meta) ---
CASTILLA = [_t("CRUDO", 102.7), _t("GAS", None), _t("BLANCOS", None)]


def test_castilla_campo_no_tiene_rezago():
    """Todo en meta o sin meta ⇒ hay_rezago False. Es el gate de toda la rama."""
    sit = _situacion_general(CASTILLA, sintesis=[])
    assert sit["hay_rezago"] is False
    assert sit["productos_rezagados"] == []
    assert sit["productos_sin_meta"] == ["GAS", "BLANCOS"]


def test_sin_meta_se_declara_como_no_faltante():
    """Un producto sin meta NO es un faltante: el resumen debe decirlo explícitamente, porque el
    modelo tendía a leer 'REAL 0 / PPTO 0' como producción caída."""
    sit = _situacion_general(CASTILLA, sintesis=[])
    assert "NO es un faltante" in sit["resumen"]
    assert "GAS, BLANCOS" in sit["resumen"]


def test_resumen_sin_rezago_lleva_el_pct_exacto():
    sit = _situacion_general(CASTILLA, sintesis=[])
    assert "NO hay rezago" in sit["resumen"]
    assert "CRUDO 102.7%" in sit["resumen"]


def test_prompt_sin_rezago_prohibe_inventarlo():
    """El corazón del fix: sin rezago, la instrucción debe PROHIBIR fabricar uno."""
    reglas = _reglas_tesis(_situacion_general(CASTILLA, sintesis=[]))
    assert "REGLA CERO" in reglas
    assert "PROHIBIDO inventar" in reglas
    assert "NO HAY REZAGO" in reglas


def test_prompt_sin_rezago_no_pide_narrar_la_sintesis_vacia():
    """Regresión directa del bug: 'sintesis' llegaba vacía y el prompt decía 'es tu tesis, nárrala'.
    Tampoco debe pedir contrastar transitorio vs estructural ni mencionar campos (no hay)."""
    reglas = _reglas_tesis(_situacion_general(CASTILLA, sintesis=[]))
    assert "es tu tesis, nárrala" not in reglas
    assert "contrasta lo transitorio" not in reglas
    assert "NO menciones campos" in reglas


def test_prompt_sin_rezago_explica_como_leer_el_pace():
    """Gemma leyó el pace al revés (dijo 'déficit' con requerido < promedio, o sea ritmo sobrado)."""
    reglas = _reglas_tesis(_situacion_general(CASTILLA, sintesis=[]))
    assert "SOBRA" in reglas


# --- Rama con rezago: no debe cambiar (el brief global de ECP la usa) ---
CON_REZAGO = [_t("CRUDO", 94.7), _t("GAS", 87.0), _t("BLANCOS", 58.5)]
SINTESIS = [{"producto": "CRUDO", "pct_presupuesto": 94.7},
            {"producto": "BLANCOS", "pct_presupuesto": 58.5}]


def test_con_rezago_conserva_la_tesis_original():
    sit = _situacion_general(CON_REZAGO, SINTESIS)
    assert sit["hay_rezago"] is True
    assert sit["productos_rezagados"] == ["CRUDO", "BLANCOS"]
    reglas = _reglas_tesis(sit)
    assert "es tu tesis, nárrala" in reglas
    assert "REGLA CERO" not in reglas


def test_las_dos_ramas_son_excluyentes():
    """Ninguna combinación debe emitir las dos tesis a la vez (se contradicen)."""
    for titular, sint in ((CASTILLA, []), (CON_REZAGO, SINTESIS)):
        reglas = _reglas_tesis(_situacion_general(titular, sint))
        assert ("REGLA CERO" in reglas) != ("es tu tesis, nárrala" in reglas)


def test_sin_ninguna_meta_no_hay_cumplimiento_que_evaluar():
    """Entidad sin PPTO en ningún producto: ni rezago ni logro; el prompt no debe evaluar meta."""
    sit = _situacion_general([_t("CRUDO", None), _t("GAS", None), _t("BLANCOS", None)], sintesis=[])
    assert sit["hay_rezago"] is False
    assert "no hay cumplimiento que evaluar" in sit["resumen"]


# --- Política de reintento del LLM (2026-07-16): un aborto de Ollama se reintenta, un JSON malo no ---

def _fake_once(secuencia):
    """Fábrica de _llm_insight_once que devuelve la secuencia dada (retorno, status) por llamada."""
    llamadas = {"n": 0}

    def stub(prompt, timeout=60, diag=None):
        i = llamadas["n"]; llamadas["n"] += 1
        ret, status = secuencia[min(i, len(secuencia) - 1)]
        if diag is not None:
            diag["status"] = status
        return ret

    stub.llamadas = llamadas
    return stub


def test_reintenta_solo_tras_aborto(monkeypatch):
    """generacion_abortada es transitorio → se reintenta; a la 2ª llega un dict válido."""
    stub = _fake_once([(None, "generacion_abortada"), ({"insights": ["ok"]}, "ok")])
    monkeypatch.setattr(api, "_llm_insight_once", stub)
    diag = {"status": "?"}
    r = api._llm_insight("p", diag=diag, intentos=2)
    assert r == {"insights": ["ok"]}
    assert stub.llamadas["n"] == 2
    assert diag["intentos"] == 1          # reintentó una vez antes del éxito


def test_no_reintenta_json_invalido(monkeypatch):
    """json_invalido = el modelo respondió entero; a temperature=0 repetir daría lo mismo."""
    stub = _fake_once([(None, "json_invalido")])
    monkeypatch.setattr(api, "_llm_insight_once", stub)
    r = api._llm_insight("p", diag={"status": "?"}, intentos=3)
    assert r is None
    assert stub.llamadas["n"] == 1        # una sola llamada, sin reintentos


def test_aborto_persistente_agota_intentos(monkeypatch):
    stub = _fake_once([(None, "generacion_abortada")])
    monkeypatch.setattr(api, "_llm_insight_once", stub)
    diag = {"status": "?"}
    r = api._llm_insight("p", diag=diag, intentos=2)
    assert r is None
    assert stub.llamadas["n"] == 2
    assert diag["status"] == "generacion_abortada"


def test_exito_a_la_primera_no_reintenta(monkeypatch):
    stub = _fake_once([({"insights": ["ok"]}, "ok")])
    monkeypatch.setattr(api, "_llm_insight_once", stub)
    r = api._llm_insight("p", diag={"status": "?"}, intentos=2)
    assert r == {"insights": ["ok"]}
    assert stub.llamadas["n"] == 1
