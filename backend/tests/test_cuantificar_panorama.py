"""Panorama del mes en curso (2026-09-08 · PRODUCCION-HOY-PANEL-MES).

«¿Cuánto producimos hoy?» -> las cifras del MES por producto + panel "p50_cards". Sin BD ni LLM:
el resolver y `president` se sustituyen por dobles, igual que en test_p50_referencia.py.
Fija también lo que NO debe cambiar: con entidad, con ranking y con mes nombrado, la rama
nueva no se activa.
"""
import pytest

from app.features.consulta_v2 import respuesta_cuantificar as _rc

_INFO = {
    "encontrada": True, "unidad": "kbepd", "corte": "2026-09-05",
    "productos": [{"entidad": "Crudo", "real_mes": 502.3, "cumpl_p50": 96.5},
                  {"entidad": "Gas", "real_mes": 80.5, "cumpl_p50": 106.6},
                  {"entidad": "Blancos", "real_mes": 8.4, "cumpl_p50": 55.4}],
    "totales": [{"entidad": "Ecopetrol", "real_mes": 591.3}],
    "empresas": {"nacional": 717.8, "p50": 735.0, "filiales": 126.5},
}


@pytest.fixture
def sin_entidad(monkeypatch):
    """El resolver no encuentra nada (la pregunta no nombra entidad)."""
    monkeypatch.setattr(_rc._resolver, "resolver_unico", lambda *a, **k: None)


def test_detector_positivos():
    assert _rc._pide_mes_en_curso("¿cuánto producimos hoy?")
    assert _rc._pide_mes_en_curso("¿cuánto produjimos este mes?")
    assert _rc._pide_mes_en_curso("¿cuál es la producción del mes?")
    assert _rc._pide_mes_en_curso("¿cuánto llevamos de producción este mes?")


def test_detector_negativos():
    assert not _rc._pide_mes_en_curso("¿cuáles campos produjeron más hoy?")   # ranking
    assert not _rc._pide_mes_en_curso("¿cuánto produjeron los campos este mes?")  # por entidades
    assert not _rc._pide_mes_en_curso("¿cuánto produjimos en abril?")          # mes nombrado
    assert not _rc._pide_mes_en_curso("¿cuánto llevamos este mes?")            # sin producción
    assert not _rc._pide_mes_en_curso("¿cuántos días con reporte llevamos de producción este mes?")


def test_panorama_texto_y_panel(sin_entidad):
    llamadas = []

    def fake(periodo=None):
        llamadas.append(periodo)
        return _INFO

    r = _rc.responder("¿cuánto producimos hoy?", _president_fn=fake)
    assert llamadas == [None]                       # periodo explícito, nunca Query(...)
    assert r["panel"]["tipo"] == "p50_cards"
    assert r["panel"]["datos"] is _INFO             # respuesta cruda, sin transformar
    m = r["mensaje"]
    assert "producción del mes en curso" in m       # rotula que es del MES
    assert "corte 2026-09-05" in m
    assert "Crudo: 502,3 kbopd" in m
    assert "Gas: 80,5 kbepd" in m
    assert "Blancos: 8,4 kblpd" in m
    assert "Total nacional: 717,8 kbepd" in m


def test_panorama_sin_reporte(sin_entidad):
    r = _rc.responder("¿cuánto producimos hoy?",
                      _president_fn=lambda periodo=None: {"encontrada": False})
    assert r["panel"] is None
    assert "REPORTE_PRESIDENT" in r["mensaje"]      # honesto: dice qué falta, no otra cifra


class _Cortado(Exception):
    """Centinela: se lanza desde el ranking para probar que la rama nueva se SALTÓ sin seguir
    hacia el ejecutor (que desde ahí tocaría BD por el techo del día)."""


@pytest.fixture
def corta_en_ranking(monkeypatch):
    def _boom(texto):
        raise _Cortado()
    monkeypatch.setattr(_rc._ranking, "detectar", _boom)


def test_resolver_ve_entidad_aunque_backstop_no(monkeypatch, corta_en_ranking):
    """Guarda doble (V-03): `entidad` viene None del backstop, pero el resolver SÍ la ve -> NO es
    el panorama global. Debe seguir al flujo normal (aquí, cortado en el ranking) sin llamar a
    president."""
    monkeypatch.setattr(_rc._resolver, "resolver_unico",
                        lambda *a, **k: {"valor": "RUBIALES", "nivel": "campo", "rama": "A", "zoom": []})
    llamado = []
    with pytest.raises(_Cortado):
        _rc.responder("¿cuánto produjo Rubiales hoy?",
                      _president_fn=lambda periodo=None: llamado.append(1) or _INFO)
    assert llamado == []


def test_entidad_del_backstop_no_entra(sin_entidad, corta_en_ranking):
    """Con `entidad` informada por maquina_q la rama ni se evalúa: sigue al flujo normal."""
    llamado = []
    with pytest.raises(_Cortado):
        _rc.responder("¿cuánto produjo Castilla hoy?", entidad="CASTILLA",
                      _president_fn=lambda periodo=None: llamado.append(1) or _INFO)
    assert llamado == []
