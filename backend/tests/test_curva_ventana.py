"""test_curva_ventana.py — la ventana móvil llega hasta la curva (plan CURVA-VENTANA, 2026-09-03).

Sin BD: la curva se inyecta con `_curva_rango_fn`, igual que test_cuantificar_dia.py hace con
`_curva_fn`. Lo que se mide es el CABLEADO, no el dato.
"""
import datetime

import pytest

from app.features.consulta_v2.cuantificar.slots import extraer_slots
from app.features.consulta_v2.cuantificar.ejecutor import ejecutar_n1dser

_TECHO = datetime.date(2026, 8, 23)
_ENT = {"valor": "CASTILLA", "nivel": "campo", "rama": "A", "zoom": []}


def _curva_falsa(_ent, ini, fin, _prod, nivel=None):
    """30 días con valor, del 2026-07-25 al 2026-08-23."""
    d0 = datetime.date.fromisoformat(str(ini))
    d1 = datetime.date.fromisoformat(str(fin))
    out, d = [], d0
    while d <= d1:
        out.append((d, 215000.0))
        d += datetime.timedelta(days=1)
    return out


# ---------------- el nivel se eleva (y solo cuando debe) ----------------

@pytest.mark.parametrize("frase", [
    "cuanto produjo Castilla en los ultimos 30 dias",
    "produccion de Castilla los ultimos 7 dias",
    "como viene Castilla en las ultimas 6 semanas",
])
def test_ventana_dias_semanas_eleva_a_n1dser(frase):
    assert extraer_slots(frase, techo=_TECHO)["nivel_temporal"] == "N1DSER"


@pytest.mark.parametrize("frase", [
    "cuanto produjo Castilla el ultimo mes",
    "cuanto produjo Castilla en los ultimos 3 meses",
])
def test_ventana_en_meses_NO_eleva(frase):
    """H5: «el último mes» pide volumen mensual; el KPI que responde hoy es correcto."""
    s = extraer_slots(frase, techo=_TECHO)
    assert s["nivel_temporal"] == "N1"
    assert s["ventana"] is not None          # se detecta, pero no manda


@pytest.mark.parametrize("frase,nivel", [
    ("acumulado de Castilla en los ultimos 30 dias", "N2"),
    ("produccion de Castilla mes a mes en los ultimos 30 dias", "N3"),
    ("como vario Castilla mes a mes en los ultimos 30 dias", "N4"),
    ("el mejor dia de Castilla de los ultimos 30 dias", "N1DSEL"),
])
def test_ventana_no_le_roba_a_los_niveles_con_dueno(frase, nivel):
    """🔑 REGRESIÓN CENTRAL. La ventana solo reclama lo que NADIE reclamó (H4)."""
    assert extraer_slots(frase, techo=_TECHO)["nivel_temporal"] == nivel


def test_dia_a_dia_con_mes_sigue_siendo_del_mes():
    s = extraer_slots("produccion dia a dia de Castilla en junio", techo=_TECHO)
    assert s["nivel_temporal"] == "N1DSER" and s["serie_dia"] is not None


# ---------------- el ejecutor usa la ventana ----------------

def test_ejecutor_usa_la_curva_por_rango():
    s = extraer_slots("cuanto produjo Castilla en los ultimos 30 dias", techo=_TECHO)
    r = ejecutar_n1dser(_ENT, s, _curva_rango_fn=_curva_falsa)
    assert r["aplica"] is True
    assert r["dias_con_dato"] == 30
    assert r["rango"] == ["2026-07-25", "2026-08-23"]


def test_ejecutor_emite_la_ventana_para_el_panel():
    s = extraer_slots("cuanto produjo Castilla en los ultimos 30 dias", techo=_TECHO)
    r = ejecutar_n1dser(_ENT, s, _curva_rango_fn=_curva_falsa)
    assert r["ventana"] == {"unidad": "dia", "cantidad": 30,
                            "ini": "2026-07-25", "fin": "2026-08-23"}


def test_label_no_miente_sobre_el_mes():
    """Con ventana NO se rotula un mes: la curva cruza julio y agosto."""
    s = extraer_slots("cuanto produjo Castilla en los ultimos 30 dias", techo=_TECHO)
    r = ejecutar_n1dser(_ENT, s, _curva_rango_fn=_curva_falsa)
    assert r["mes_label"] == "2026-07-25 a 2026-08-23"
    assert "agosto" not in r["mes_label"]


def test_avisa_que_cuenta_desde_el_ultimo_reporte():
    """El usuario dice «últimos 30 días» pensando en hoy; el dato va ~100 días atrás."""
    s = extraer_slots("cuanto produjo Castilla en los ultimos 30 dias", techo=_TECHO)
    r = ejecutar_n1dser(_ENT, s, _curva_rango_fn=_curva_falsa)
    assert any("2026-08-23" in a for a in r["avisos"])


def test_sin_datos_en_la_ventana_declina_honesto():
    s = extraer_slots("cuanto produjo Castilla en los ultimos 30 dias", techo=_TECHO)
    r = ejecutar_n1dser(_ENT, s, _curva_rango_fn=lambda *a, **k: [])
    assert r["aplica"] is False and "2026-07-25" in r["texto"]


def test_mes_nombrado_gana_a_la_ventana():
    """Si hay `serie_dia`, manda el mes: no se usa la ventana."""
    s = extraer_slots("produccion dia a dia de Castilla en junio", techo=_TECHO)
    llamadas = []
    def _rango_espia(*a, **k):
        llamadas.append(a)
        return []
    ejecutar_n1dser(_ENT, s, _curva_fn=lambda *a, **k: [(datetime.date(2026, 6, 1), 1.0)],
                    _curva_rango_fn=_rango_espia)
    assert llamadas == []


# ---------------- el panel transporta la ventana ----------------

def test_panel_datos_lleva_la_ventana():
    from app.features.consulta_v2.respuesta_cuantificar import _panel_datos
    s = extraer_slots("cuanto produjo Castilla en los ultimos 30 dias", techo=_TECHO)
    r = ejecutar_n1dser(_ENT, s, _curva_rango_fn=_curva_falsa)
    p = _panel_datos(r)
    assert p["ventana"]["ini"] == "2026-07-25" and p["ventana"]["fin"] == "2026-08-23"


def test_panel_de_mes_no_lleva_ventana():
    from app.features.consulta_v2.respuesta_cuantificar import _panel_datos
    s = extraer_slots("produccion dia a dia de Castilla en junio", techo=_TECHO)
    r = ejecutar_n1dser(_ENT, s,
                        _curva_fn=lambda *a, **k: [(datetime.date(2026, 6, d), 1000.0)
                                                   for d in range(1, 31)])
    assert _panel_datos(r)["ventana"] is None
