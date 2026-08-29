"""Tests PUROS (sin BD/LLM) de R1 (enrutamiento de conteo) y R3 (línea de pozos con degradación)."""
import app.features.consulta_v2.respuesta_jerarquizar as RJ
from app.features.consulta_v2.patrones import clasificar_capa1


# --- R1: el conteo de jerarquía se clasifica jerarquizar por Capa 1 (precedencia_maxima) ----------
def test_r1_conteo_va_a_jerarquizar():
    for q in ["¿cuántos pozos tiene Castilla?",
              "¿cuántas gerencias tiene la vicepresidencia GOR?",
              "¿cuántos campos tiene la gerencia GOR?",
              "¿cuántos activos tiene Rubiales?"]:
        grupo, _pat = clasificar_capa1(q)
        assert grupo == "jerarquizar", f"{q!r} → {grupo}"


def test_r1_no_rompe_produccion():
    # Una pregunta de producción SIGUE siendo cuantificar (no la captura el patrón de conteo).
    grupo, _ = clasificar_capa1("cuanto produjo Rubiales en mayo")
    assert grupo == "cuantificar"
    grupo, _ = clasificar_capa1("cuanto crudo acumulo Castilla")
    assert grupo == "cuantificar"


# --- GUARDAS DE REGRESIÓN (H1): "cuántos <sustantivo>" SIN verbo estructural conserva su grupo ------
# El patrón de conteo vive en precedencia_maxima (gana sobre TODO). Sin exigir el verbo, se tragaba
# estas 5 preguntas de analizar/cuantificar. Verificado en vivo 2026-08-03 — regresión permanente.
def test_r1_no_secuestra_analizar():
    for q in ["¿Cuántos campos están por debajo de la meta?",
              "¿Cuántos campos pesan más en el gap?"]:
        grupo, _ = clasificar_capa1(q)
        assert grupo == "analizar", f"{q!r} → {grupo} (el patrón de conteo lo secuestró)"


def test_r1_no_secuestra_cuantificar():
    for q in ["¿Cuántos pozos produjeron en mayo?",
              "¿Cuántos campos incumplieron el presupuesto?",
              "¿Cuántos activos están en foco?"]:
        grupo, _ = clasificar_capa1(q)
        assert grupo == "cuantificar", f"{q!r} → {grupo} (el patrón de conteo lo secuestró)"


# --- R3: _cuerpo pinta "Pozos: N" cuando hay conteo, y lo OMITE si ops no está (degradación) -------
_FAKE_DATA = {
    "campo_row": {"CASTILLA": {"campo": "CASTILLA", "operador": "ECOPETROL", "es_ecp": True,
                               "rob_field": "CASTILLA", "activo": "CASTILLA",
                               "gerencia": "PPC", "vp": "GAA"}},
    "act_campos": {"CASTILLA": ["CASTILLA"]},
    "act_fields": {"CASTILLA": {"CASTILLA"}},
}


def test_r3_cuerpo_pinta_pozos(monkeypatch):
    monkeypatch.setattr(RJ, "_contar_pozos", lambda fields: 437)
    body = RJ._cuerpo("campo", "CASTILLA", _FAKE_DATA)
    assert "Pozos: 437" in body


def test_r3_degrada_si_ops_no_esta(monkeypatch):
    monkeypatch.setattr(RJ, "_contar_pozos", lambda fields: None)   # ops caído → None
    body = RJ._cuerpo("campo", "CASTILLA", _FAKE_DATA)
    assert "Pozos" not in body            # línea OMITIDA, sin romper
    assert "«CASTILLA» · Campo" in body   # la estructura sigue intacta


def test_r3_contar_pozos_sin_fields_devuelve_None():
    # Puro: sin rob_fields (p.ej. tercero) → None sin tocar la BD.
    assert RJ._contar_pozos(set()) is None
    assert RJ._contar_pozos({None}) is None
