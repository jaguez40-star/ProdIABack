"""test_slots_mtd.py — acumulado del MES en curso (MTD) vs acumulado del AÑO (YTD).

Cierra el punto 1 de «inteligencia de tiempo»: el enunciado era «acumulados MTD/YTD» y solo
YTD estaba. «En lo que va DEL MES» casaba con la misma keyword fuerte que «en lo que va DEL
AÑO» (_ACUM_KW_FUERTE) y las dos resolvían a N2, que acumula SIEMPRE el año — o sea, se
preguntaba por el mes y se respondían siete meses, sin aviso.

Módulo PURO: ningún test toca BD.
"""
import datetime

import pytest

from app.features.consulta_v2.cuantificar.slots import extraer_slots

_TECHO = datetime.date(2026, 8, 30)      # último día con reporte en Pruebas


def _nivel(frase):
    return extraer_slots(frase, techo=_TECHO)["nivel_temporal"]


# ---------------- MTD: el MES en curso, no el año ----------------

@pytest.mark.parametrize("frase", [
    "cuanto lleva Castilla en lo que va del mes",
    "produccion de Castilla en lo que va de este mes",
    "cuanto llevamos del mes en Castilla",
    "cual es el acumulado del mes de Castilla",
    "acumulado mensual de Castilla",
    "cual es el total del mes para Castilla",
    "MTD de Castilla",
    "produccion de Castilla en lo corrido del mes",
])
def test_mtd_resuelve_a_n1(frase):
    """El mes en curso es N1 (el KPI del mes del techo), NO N2 (acumulado del año)."""
    assert _nivel(frase) == "N1", frase


def test_mtd_marca_el_flag_y_lo_declara():
    """Sin mes nombrado el motor elige el del techo: tiene que decirlo (aviso en ejecutar_n1)."""
    s = extraer_slots("cuanto lleva Castilla en lo que va del mes", techo=_TECHO)
    assert s["mtd"] is True
    assert s["periodo_texto"] is None


def test_mtd_con_mes_nombrado_no_avisa():
    """«el acumulado del mes de julio» aterriza julio: el rótulo del KPI ya lo dice, el aviso
    sobraría. Y antes de esto respondía el acumulado del AÑO."""
    s = extraer_slots("cual es el acumulado del mes de julio de Castilla", techo=_TECHO)
    assert s["nivel_temporal"] == "N1"
    assert s["periodo_texto"] == "julio"
    assert s["mtd"] is False


# ---------------- YTD: no se toca ----------------

@pytest.mark.parametrize("frase", [
    "cuanto ha producido Rubiales en lo que va del ano",
    "acumulado de Castilla",
    "cuanto lleva Castilla acumulado en el ano",
    "YTD de Castilla",
    "cuanto ha producido Castilla en total",
    "produccion de Castilla hasta ahora",
])
def test_ytd_sigue_en_n2(frase):
    """La guarda del MES exige la palabra MES: el acumulado del AÑO no debe perderse."""
    assert _nivel(frase) == "N2", frase


# ---------------- la guarda no le roba a N3/N4 ----------------

def test_serie_gana_a_la_guarda_mtd():
    """«la evolución mes a mes del acumulado» es una SERIE; la guarda va después de N3/N4
    justamente para no robársela."""
    assert _nivel("evolucion mes a mes del acumulado de Castilla") == "N3"


def test_variacion_gana_a_la_guarda_mtd():
    assert _nivel("como vario el acumulado del mes en Castilla") == "N4"


# ---------------- la ventana sigue mandando ----------------

def test_ventana_de_meses_no_la_pisa_la_guarda():
    """«los últimos 3 meses» eleva N1 → N2 al final de extraer_slots. La guarda MTD actúa
    ANTES, sobre `_nivel_temporal`, así que no interfiere."""
    s = extraer_slots("produccion de Castilla en los ultimos 3 meses", techo=_TECHO)
    assert s["nivel_temporal"] == "N2"
    assert s["ventana"]["cantidad"] == 3
