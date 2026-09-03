"""test_slots_comparacion.py — comparación de periodos (punto 3, tipo 2) y serie vs programa
(tipo 3). Módulo PURO: ningún test toca BD; el techo se pasa a mano.
"""
import datetime

import pytest

from app.features.consulta_v2.cuantificar.slots import (
    detectar_comparacion, extraer_slots, menciona_dia, TECHO_CENTINELA,
)

_TECHO = datetime.date(2026, 8, 30)      # último día con reporte en Pruebas


# ---------------- formas que SÍ resuelven ----------------

@pytest.mark.parametrize("frase,ma,aa,mb,ab,clase", [
    ("produccion de Castilla en julio vs mayo", 7, 2026, 5, 2026, "meses"),
    ("compara julio con mayo en Castilla", 7, 2026, 5, 2026, "meses"),
    ("Castilla julio contra mayo", 7, 2026, 5, 2026, "meses"),
    ("Castilla julio frente a mayo", 7, 2026, 5, 2026, "meses"),
    ("Castilla julio 2026 vs julio 2025", 7, 2026, 7, 2025, "yoy"),
    ("produccion de Castilla en julio vs el ano pasado", 7, 2026, 7, 2025, "yoy"),
    ("produccion de Castilla en julio vs el mes pasado", 7, 2026, 6, 2026, "mom"),
])
def test_comparacion_resuelve(frase, ma, aa, mb, ab, clase):
    r = detectar_comparacion(frase, _TECHO)
    assert r is not None, frase
    assert (r["mes_a"], r["anio_a"]) == (ma, aa)
    assert (r["mes_b"], r["anio_b"]) == (mb, ab)
    assert r["clase"] == clase


def test_sin_mes_a_la_izquierda_ancla_en_el_techo_y_lo_declara():
    """«¿cómo vamos vs el año pasado?» = el mes del techo contra su gemelo. Se DECLARA."""
    r = detectar_comparacion("como vamos vs el ano pasado", _TECHO)
    assert (r["mes_a"], r["anio_a"]) == (8, 2026)
    assert (r["mes_b"], r["anio_b"]) == (8, 2025)
    assert any("mes del ultimo reporte" in a or "último reporte" in a for a in r["asumido"])


def test_enero_vs_mes_pasado_cruza_a_diciembre_del_ano_anterior():
    r = detectar_comparacion("produccion en enero vs el mes pasado", _TECHO)
    assert (r["mes_b"], r["anio_b"]) == (12, 2025)


# ---------------- 🔴 P4: la REFERENCIA no se toca ----------------

@pytest.mark.parametrize("frase", [
    "como va Castilla vs el promedio",
    "como va Castilla contra el promedio",
    "produccion de Castilla respecto al promedio",
    "como va Castilla vs el presupuesto",
    "Castilla frente a la meta",
    "Castilla vs el P50",
])
def test_referencia_no_es_comparacion_de_periodos(frase):
    """Estas ya resuelven a N1 con su referencia y hoy responden bien. Robárselas sería una
    regresión introducida por este plan."""
    assert detectar_comparacion(frase, _TECHO) is None, frase


def test_dos_meses_mas_referencia_si_es_comparacion():
    """«julio vs junio contra el presupuesto» tiene las dos cosas: la guarda mira lo que sigue
    al conector, no si la palabra aparece suelta en la frase."""
    r = detectar_comparacion("Castilla julio vs junio contra el presupuesto", _TECHO)
    assert r is not None and r["mes_a"] == 7 and r["mes_b"] == 6


# ---------------- formas que NO resuelven ----------------

def test_sin_conector_no_hay_comparacion():
    assert detectar_comparacion("produccion de Castilla en julio", _TECHO) is None


def test_conector_sin_segundo_periodo_no_resuelve():
    assert detectar_comparacion("Castilla julio vs Rubiales", _TECHO) is None


def test_mismo_periodo_no_se_compara():
    assert detectar_comparacion("Castilla julio 2026 vs julio 2026", _TECHO) is None


def test_sin_techo_no_hay_comparacion():
    """Sin ancla no se inventa el año: rechazo honesto (misma regla que detectar_ventana)."""
    assert detectar_comparacion("Castilla julio vs mayo", None) is None


# ---------------- integración con extraer_slots ----------------

def test_extraer_slots_eleva_a_ncmp():
    s = extraer_slots("produccion de Castilla en julio vs mayo", techo=_TECHO)
    assert s["nivel_temporal"] == "NCMP"
    assert s["comparacion"]["mes_a"] == 7 and s["comparacion"]["mes_b"] == 5


def test_la_ruta_real_pide_el_techo():
    """🔴 Sin esta rama en menciona_dia, detectar_comparacion recibiría techo=None en
    producción y devolvería None SIEMPRE: funcionaría en los tests y no en la app."""
    assert menciona_dia("produccion de Castilla en julio vs mayo") is True


def test_un_mes_solo_sigue_en_n1():
    s = extraer_slots("produccion de Castilla en julio", techo=_TECHO)
    assert s["nivel_temporal"] == "N1"
    assert s["comparacion"] is None


# ---------------- 🔴 P8: N3P exige LAS DOS señales ----------------

def test_serie_sola_sigue_siendo_n3():
    s = extraer_slots("produccion de Castilla mes a mes", techo=_TECHO)
    assert s["nivel_temporal"] == "N3"


def test_serie_mas_programa_es_n3p():
    s = extraer_slots("produccion de Castilla mes a mes vs el presupuesto", techo=_TECHO)
    assert s["nivel_temporal"] == "N3P"


def test_programa_solo_sigue_en_n1():
    """«vs el presupuesto» sin señal de serie es la pregunta N1 de siempre."""
    s = extraer_slots("como va Castilla vs el presupuesto", techo=_TECHO)
    assert s["nivel_temporal"] == "N1"


def test_ventana_sola_no_se_convierte_en_comparacion():
    """No-regresión del punto 1: la ventana móvil sigue elevando a N2."""
    s = extraer_slots("produccion de Castilla en los ultimos 3 meses", techo=_TECHO)
    assert s["nivel_temporal"] == "N2"
