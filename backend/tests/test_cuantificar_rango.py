"""Tests PUROS (sin BD, sin LLM) del rechazo honesto de rango/trimestre/semana en Cuantificar (bug #5).

La policy (_forma_no_soportada) es pura. La integración (responder) se prueba con monkeypatch sobre el
resolver → NO toca la BD: el rechazo retorna ANTES de ejecutar (que sí necesitaría datos)."""
import app.features.consulta_v2.respuesta_cuantificar as RC
from app.features.consulta_v2.respuesta_cuantificar import _forma_no_soportada


# --- Policy pura: qué se rechaza y qué NO -----------------------------------------------------
def test_rechaza_rango_trimestre_semana():
    assert _forma_no_soportada("entre el 5 y el 10 de mayo cuanto produjo Rubiales") == "rango_dias"
    assert _forma_no_soportada("los primeros 10 dias de mayo cuanto") == "rango_dias"
    assert _forma_no_soportada("cuanto en el primer trimestre de Rubiales") == "trimestre"
    assert _forma_no_soportada("produccion trimestral de Castilla") == "trimestre"
    assert _forma_no_soportada("cuanto produjo esta semana Rubiales") == "semana"


def test_NO_rechaza_anio_porque_N2_lo_soporta():
    # 🔑 Guarda de regresión: 'anio' NO se rechaza — N2 (acumulado) responde el año.
    assert _forma_no_soportada("cuanto acumulo Rubiales en el ano 2026") is None
    assert _forma_no_soportada("acumulado del año de Rubiales") is None
    assert _forma_no_soportada("produccion anual de Rubiales") is None      # anio → excluido del set


def test_NO_rechaza_lo_soportado():
    assert _forma_no_soportada("cuanto produjo Rubiales en mayo") is None   # N1
    assert _forma_no_soportada("serie mensual de Castilla") is None         # N3
    assert _forma_no_soportada("como vario mes a mes Rubiales") is None     # N4
    assert _forma_no_soportada("cuanto produjo Rubiales") is None           # N1 default


# --- Integración: responder() devuelve el rechazo honesto SIN tocar la BD ----------------------
def test_responder_rechaza_rango_sin_ejecutar(monkeypatch):
    # Resolver fake (rama A) → responder NO debe llegar al ejecutor (que necesitaría datos).
    monkeypatch.setattr(RC._resolver, "resolver_unico",
                        lambda x: {"valor": "RUBIALES", "rama": "A", "nivel": "campo"})
    def _boom(*a, **k):
        raise AssertionError("ejecutar NO debe llamarse en un rechazo de forma no soportada")
    monkeypatch.setattr(RC._ejecutor, "ejecutar", _boom)
    r = RC.responder("entre el 5 y el 10 de mayo cuanto produjo Rubiales", entidad="RUBIALES")
    assert r["panel"] is None
    assert "RUBIALES" in r["mensaje"]
    assert "rango de días" in r["mensaje"] and "mes completo" in r["mensaje"]
    assert "¿Quieres" not in r["mensaje"]   # H1: no invita a un "sí" (drill _AFIRM → acumulado)


def test_responder_deja_pasar_lo_soportado(monkeypatch):
    # Una pregunta soportada NO se rechaza: responder llega al ejecutor (aquí lo interceptamos).
    monkeypatch.setattr(RC._resolver, "resolver_unico",
                        lambda x: {"valor": "RUBIALES", "rama": "A", "nivel": "campo"})
    marca = {"llamado": False}
    def _fake_ejecutar(resuelta, slots):
        marca["llamado"] = True
        return {"aplica": False, "texto": "stub"}      # corta antes del validador/BD
    monkeypatch.setattr(RC._ejecutor, "ejecutar", _fake_ejecutar)
    r = RC.responder("cuanto produjo Rubiales en mayo", entidad="RUBIALES")
    assert marca["llamado"] is True                     # NO se rechazó por forma → siguió el flujo
    assert r["panel"] is None                           # (el stub devuelve aplica:False)
