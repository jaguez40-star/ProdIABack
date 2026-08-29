"""tests/test_jerarquizar_ranking.py — RANKING ESTRUCTURAL en Jerarquizar
(plan_jerarquizar_ranking_2026-08-04.md, §8).

V-DETECT: puro, sin BD (_rank_detectar). Incluye la guarda de no-regresión OBLIGATORIA del §8:
_rank_detectar debe devolver None para las 10 preguntas jerarquizar del golden (si el detector
empieza a secuestrar la ruta de entidad única, este test lo caza).
V-CALC: contra Postgres real (responder()/_rank_calcular), con `_engine_o_skip` (mismo patrón que
tests/test_puente_gerencia_vp.py) para no reventar si la BD dev no está disponible.
"""
import pathlib

import pytest
import yaml

import app.features.consulta_v2.respuesta_jerarquizar as J


# --- V-DETECT (puro, sin BD) -----------------------------------------------------------------

def test_campos_con_mas_pozos():
    r = J._rank_detectar("cuales son los campos con mas pozos")
    assert r is not None
    assert r["subject"] == "campo"
    assert r["conteo"] == "pozos"
    assert r["asc"] is False
    assert r["top_n"] == 5


def test_vp_con_mas_gerencias():
    r = J._rank_detectar("que vicepresidencia tiene mas gerencias")
    assert r is not None
    assert r["subject"] == "vicepresidencia"
    assert r["conteo"] == "gerencias"
    assert r["top_n"] == 1


def test_campos_mas_grandes_default_pozos():
    r = J._rank_detectar("cuales son los campos mas grandes")
    assert r is not None
    assert r["subject"] == "campo"
    assert r["conteo"] == "pozos"


def test_campo_con_mas_pozos_singular():
    r = J._rank_detectar("que campo tiene mas pozos")
    assert r is not None
    assert r["subject"] == "campo"
    assert r["conteo"] == "pozos"
    assert r["top_n"] == 1


def test_activo_con_mas_campos():
    r = J._rank_detectar("que activo tiene mas campos")
    assert r is not None
    assert r["subject"] == "activo"
    assert r["conteo"] == "campos"
    assert r["top_n"] == 1


def test_gerencia_con_menos_activos_asc():
    r = J._rank_detectar("cual gerencia tiene menos activos")
    assert r is not None
    assert r["subject"] == "gerencia"
    assert r["conteo"] == "activos"
    assert r["asc"] is True


def test_conteo_r3_no_es_ranking():
    """'cuántos pozos tiene X' -> sin superlativo -> no es N5 estructural; lo maneja la ruta R3."""
    assert J._rank_detectar("cuantos pozos tiene Castilla") is None


def test_pertenece_no_es_ranking():
    assert J._rank_detectar("a que activo pertenece Cajua") is None


def test_campos_mas_pequenos_antonimo_manda():
    """D11: el antónimo (PEQUENOS) manda sobre 'MAS' -> asc=True, no False."""
    r = J._rank_detectar("cuales son los campos mas pequenos")
    assert r is not None
    assert r["subject"] == "campo"
    assert r["conteo"] == "pozos"
    assert r["asc"] is True


def test_campos_mayor_numero_de_pozos():
    r = J._rank_detectar("campos con mayor numero de pozos")
    assert r is not None
    assert r["subject"] == "campo"
    assert r["conteo"] == "pozos"
    assert r["asc"] is False


# --- Guarda de no-regresión OBLIGATORIA (§8): 0 falsos positivos del fork sobre jerarquizar ----

# Las 10 preguntas ORIGINALES de entidad-única del golden (bloque "---- jerarquizar (10) ----",
# anteriores a este plan). NO se leen dinámicamente del YAML: desde A4 ese archivo también contiene
# los 4 casos de RANKING (mismo `esperado: jerarquizar`, a propósito — SÍ deben disparar el fork).
# Leer "todo lo etiquetado jerarquizar" sería una guarda que se contradice a sí misma.
_JERARQUIA_ENTIDAD_UNICA = (
    "¿A qué activo pertenece Cajúa?",
    "¿Qué campos tiene el activo Castilla?",
    "¿Qué es CPO-09?",
    "¿Hocol es una filial o un activo de ECP?",
    "¿De qué gerencia es el campo Rubiales?",
    "¿Cuáles campos conforman el activo Apiay?",
    "Muéstrame la estructura completa del activo Chichimene",
    "¿Qué información hay de Rubiales?",
    "¿Desde cuándo hay datos de producción de Castilla?",
    "¿Cuántos días con reporte hay de Rubiales?",
)


def test_fork_no_secuestra_preguntas_jerarquizar_de_entidad_unica():
    """_rank_detectar debe dar None para las 10 preguntas ORIGINALES de entidad única (verificadas
    contra el golden real, no hardcodeadas a ciegas). Si el detector empieza a atrapar la ruta de
    entidad única, este test lo caza (D9/D10)."""
    p = (pathlib.Path(__file__).parent.parent
         / "app/features/consulta_v2/golden/clasificacion_golden.yaml")
    casos = yaml.safe_load(p.read_text(encoding="utf-8"))
    preguntas_golden = {c["pregunta"] for c in casos if c.get("esperado") == "jerarquizar"}
    faltantes = [q for q in _JERARQUIA_ENTIDAD_UNICA if q not in preguntas_golden]
    assert not faltantes, f"el golden ya no trae estos casos originales: {faltantes}"
    falsos_positivos = [q for q in _JERARQUIA_ENTIDAD_UNICA if J._rank_detectar(q) is not None]
    assert not falsos_positivos, f"_rank_detectar secuestró: {falsos_positivos}"


# --- V-CALC (contra BD real; se salta si Postgres no está disponible) --------------------------

def _engine_o_skip():
    try:
        from app.core.db import get_engine
        import sqlalchemy as sa
        eng = get_engine()
        with eng.connect() as c:
            c.execute(sa.text("SELECT 1"))
        return eng
    except Exception:
        pytest.skip("Postgres no disponible")


def test_bd_real_vp_con_mas_gerencias():
    _engine_o_skip()
    r = J.responder("¿qué vicepresidencia tiene más gerencias?")
    assert r.startswith("El vicepresidencia con más gerencias:")
    assert "VRC (3)" in r
    assert "1) VRC (3)" in r


def test_bd_real_campos_con_mas_pozos():
    _engine_o_skip()
    try:
        from app.core.db import get_ops_engine
        with get_ops_engine().connect():
            pass
    except Exception:
        pytest.skip("robustez_v02 (ops) no disponible")
    r = J.responder("¿cuáles son los campos con más pozos?")
    assert "1) RUBIALES (2131)" in r
    assert "ECP-operados" in r
    assert "REGISTRO (atemporal)" in r


def test_bd_real_activo_pozos_diferido():
    _engine_o_skip()
    r = J.responder("¿qué activo tiene más pozos?")
    assert "próxima fase" in r


def test_bd_real_combo_invalido_campo_gerencias():
    _engine_o_skip()
    r = J.responder("¿qué campo tiene más gerencias?")
    assert "no es una subdivisión" in r


def test_bd_real_orden_ascendente():
    _engine_o_skip()
    rk = {"subject": "activo", "conteo": "campos", "asc": True, "top_n": 5,
          "soportados": {"campos"}, "default": "campos"}
    data = J._cargar()
    res = J._rank_calcular(rk, data)
    assert res["aplica"] is True
    items = res["items"]
    assert items[0]["n"] <= items[-1]["n"]
