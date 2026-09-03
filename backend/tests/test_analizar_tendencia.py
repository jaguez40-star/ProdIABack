"""test_analizar_tendencia.py — sub-intención `tendencia` de Analizar (punto 2 de
inteligencia de tiempo: tipos 4 evolución, 5 declinación, 6 media móvil).

Ningún test toca BD: `_desempeno_fn` se inyecta y el resolver se neutraliza con la fixture
`sin_entidad` (mismo recurso que los 13 tests de test_p50_referencia.py).
"""
import pytest

from app.features.consulta_v2 import respuesta_analizar as _ra
from app.features.consulta_v2.analizar import subrouter as _sr
from app.features.consulta_v2.analizar import tendencia as _t

_MS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def _pts(vals):
    return [{"mes": _MS[i], "num": i + 1, "valor": v} for i, v in enumerate(vals)]


def _fake_desempeno(vals, mes_actual=None, anio=2026):
    """Doble de `desempeno`: devuelve un `ritmo_mensual` con la serie pedida. GAS = ×2 para
    comprobar que el producto explícito elige la serie correcta."""
    n = len(vals)
    def _fn(entidad=None, segmento="ecp", nivel=None, periodo=None):
        return {"encontrada": True, "mes": {"anio": anio}, "ritmo_mensual": {
            "meses": _MS[:n], "meses_num": list(range(1, n + 1)),
            "series": {"CRUDO": list(vals), "GAS": [v * 2 for v in vals]},
            "mes_actual": mes_actual}}
    return _fn


@pytest.fixture
def sin_entidad(monkeypatch):
    """Neutraliza el catálogo → rama GLOBAL (V6/V10). Sin esto los tests pedirían BD."""
    monkeypatch.setattr(_ra._resolver, "resolver_unico", lambda *a, **k: None)


# ---------------- el sub-router ----------------

@pytest.mark.parametrize("frase", [
    "cual es la tendencia de Castilla",
    "a que ritmo esta declinando Castilla",
    "cual es la declinacion de Castilla",
    "muestrame la media movil de Castilla",
    "como viene la produccion de Castilla",
    "Castilla viene cayendo?",
    "la produccion va subiendo o bajando en Castilla",
])
def test_subrouter_manda_a_tendencia(frase):
    assert _sr.sub_intencion(frase) == "tendencia", frase


@pytest.mark.parametrize("frase", [
    "como vamos este mes",
    "vamos a cerrar en meta",
    "cual es la proyeccion de cierre",
])
def test_los_3_casos_del_golden_de_proyeccion_no_se_mueven(frase):
    """Sacar TENDENCIA de _PROY no debe robarle a proyeccion ninguno de sus casos (H2)."""
    assert _sr.sub_intencion(frase) == "proyeccion", frase


def test_tendencia_gana_a_proyeccion_cuando_estan_las_dos():
    assert _sr.sub_intencion("como viene Castilla, vamos a cerrar en meta") == "tendencia"


def test_economia_y_diferidas_siguen_ganando():
    assert _sr.sub_intencion("cual es la tendencia del EBITDA") == "economia"
    assert _sr.sub_intencion("tendencia de las diferidas") == "diferidas"


# ---------------- la lectura ----------------

def test_serie_a_la_baja_sostenida():
    r = _t.leer(_pts([1000, 950, 900, 850, 800]))
    assert r["aplica"] and r["direccion"] == "a la baja"
    assert r["pct_mensual"] < 0 and r["sostenida"] is True


def test_serie_al_alza():
    r = _t.leer(_pts([800, 850, 900, 950, 1000]))
    assert r["direccion"] == "al alza" and r["pct_mensual"] > 0


def test_serie_plana_es_estable():
    r = _t.leer(_pts([1000, 1000, 1000, 1000]))
    assert r["direccion"] == "estable"
    assert r["r2"] == 1.0          # una recta plana la explica perfectamente


def test_ruido_bajo_el_umbral_es_estable():
    """±0.06% mensual es ruido de operación, no una tendencia."""
    assert _t.leer(_pts([1000, 1004, 998, 1006, 1002]))["direccion"] == "estable"


def test_serie_erratica_no_se_declara_sostenida():
    r = _t.leer(_pts([1000, 600, 1100, 500, 900, 400]))
    assert r["direccion"] == "a la baja" and r["sostenida"] is False


def test_anualizado_compone_no_multiplica():
    """-2% mensual son -21.5% anuales, NO -24%. El ×12 exagera la declinación."""
    r = _t.leer(_pts([1000, 980, 960.4, 941.19, 922.37]))
    assert r["pct_mensual"] == pytest.approx(-2.0, abs=0.2)
    assert r["pct_anualizado"] == pytest.approx(-21.5, abs=1.0)


def test_menos_de_3_meses_declina_honesto():
    r = _t.leer(_pts([1000, 900]))
    assert r["aplica"] is False and "variación" in r["texto"]


def test_media_movil_alineada_al_final_con_huecos():
    mm = _t.media_movil([3, 6, 9, 12], 3)
    assert mm[0] is None and mm[1] is None
    assert mm[2] == pytest.approx(6.0)     # (3+6+9)/3
    assert mm[3] == pytest.approx(9.0)     # (6+9+12)/3


def test_media_movil_no_se_calcula_con_3_puntos():
    """Con 3 meses daría UN solo valor: un punto suelto que no es una curva."""
    assert all(v is None for v in _t.leer(_pts([1000, 950, 900]))["serie_mm"])


# ---------------- integración (sin BD) ----------------

def test_he4_el_mes_en_curso_no_entra(sin_entidad):
    """8 meses de serie con mes_actual=8: solo entran los 7 cerrados. El 8º vale 10 y, si
    entrara, hundiría la pendiente y el texto diría 8 meses."""
    r = _ra.responder_con_panel(
        "cual es la tendencia de la produccion",
        _desempeno_fn=_fake_desempeno([1000] * 7 + [10], mes_actual=8))
    assert "7 meses cerrados" in r["mensaje"]
    assert r["panel"]["datos"]["valores"] == [1000.0] * 7


def test_producto_explicito_elige_la_serie_de_gas(sin_entidad):
    """«la tendencia del gas» debe leer la serie GAS (×2 en el fake) y rotular MSCF (V5)."""
    r = _ra.responder_con_panel(
        "cual es la tendencia del gas",
        _desempeno_fn=_fake_desempeno([1000, 950, 900, 850], mes_actual=5))
    assert r["panel"]["datos"]["producto"] == "gas"
    assert r["panel"]["datos"]["unidad"] == "MSCF"
    assert r["panel"]["datos"]["valores"] == [2000.0, 1900.0, 1800.0, 1700.0]


def test_sin_serie_suficiente_no_emite_panel(sin_entidad):
    """Con 2 meses cerrados se declina en texto y NO se abre un bloque en la pila."""
    r = _ra.responder_con_panel(
        "cual es la tendencia de la produccion",
        _desempeno_fn=_fake_desempeno([1000, 900], mes_actual=3))
    assert r["panel"] is None
    assert "variación" in r["mensaje"]


def test_el_fake_se_inyecta_por_el_wrapper_publico(sin_entidad):
    """🔴 V1: `responder` y `responder_con_panel` deben PROPAGAR `_desempeno_fn`. Si solo se
    añadió a `_responder_core`, este test pega contra la BD real y falla."""
    msg = _ra.responder(
        "cual es la tendencia de la produccion",
        _desempeno_fn=_fake_desempeno([1000, 950, 900, 850, 800], mes_actual=6))
    assert "TENDENCIA" in msg and "a la baja".upper() in msg.upper()
