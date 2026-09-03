"""test_slots_ventana.py — ventana temporal móvil (plan VENTANAS-TEMPORALES, 2026-09-03).

Módulo PURO: ningún test de este archivo toca BD. El `techo` se pasa a mano salvo en
`test_ruta_real_pide_techo`, que reproduce lo que hace producción.
"""
import datetime

import pytest

from app.features.consulta_v2.cuantificar.slots import (
    detectar_ventana, extraer_slots, menciona_dia, TECHO_CENTINELA,
)

_TECHO = datetime.date(2026, 8, 23)      # último día con dato en Pruebas al escribir el plan


# ---------------- formas que SÍ resuelven ----------------

@pytest.mark.parametrize("frase,unidad,cant", [
    ("produccion de Castilla en los ultimos 30 dias", "dia", 30),
    ("produccion de Castilla los ultimos 7 dias", "dia", 7),
    ("como viene Castilla en las ultimas 6 semanas", "semana", 6),
    ("produccion de Castilla en los ultimos 3 meses", "mes", 3),
    ("produccion de Castilla en los ultimos tres meses", "mes", 3),
    ("produccion de Castilla el ultimo mes", "mes", 1),
    ("produccion de Castilla la ultima semana", "semana", 1),
    ("produccion de Castilla los 15 dias anteriores", "dia", 15),
    # [2026-09-03] Forma (d): la cantidad ANTEPUESTA a «últimos». Medida en Pruebas — la frase
    # real del usuario caía al mes del techo y respondía agosto sin avisar.
    ("Muestra la produccion de crudo de los 3 ultimos meses para Castilla", "mes", 3),
    ("produccion de Castilla los tres ultimos meses", "mes", 3),
    ("produccion de Castilla en los 30 ultimos dias", "dia", 30),
    ("como viene Castilla en las 6 ultimas semanas", "semana", 6),
])
def test_ventana_resuelve(frase, unidad, cant):
    r = detectar_ventana(frase, _TECHO)
    assert r is not None, frase
    assert r["unidad"] == unidad and r["cantidad"] == cant


@pytest.mark.parametrize("antepuesta,pospuesta", [
    ("los ultimos 3 meses", "los 3 ultimos meses"),
    ("los ultimos 30 dias", "los 30 ultimos dias"),
    ("las ultimas 6 semanas", "las 6 ultimas semanas"),
    ("los ultimos tres meses", "los tres ultimos meses"),
])
def test_ventana_orden_libre_da_lo_mismo(antepuesta, pospuesta):
    """En español el orden es libre; las dos formas deben aterrizar en la MISMA ventana.
    Sin esto, una de las dos responde el mes por defecto en silencio."""
    a = detectar_ventana("produccion de Castilla en " + antepuesta, _TECHO)
    b = detectar_ventana("produccion de Castilla en " + pospuesta, _TECHO)
    assert a is not None and b is not None
    assert a == b


def test_ultimos_meses_sin_cantidad_sigue_sin_resolver():
    """«los últimos meses» no dice CUÁNTOS: la forma (d) captura "LOS", que no es cardinal.
    Debe seguir devolviendo None (rechazo honesto), como antes de añadir (d)."""
    assert detectar_ventana("produccion de Castilla en los ultimos meses", _TECHO) is None


def test_ventana_dias_es_inclusiva():
    """30 días contados hacia atrás desde el techo, ambos extremos incluidos."""
    r = detectar_ventana("los ultimos 30 dias", _TECHO)
    assert r["fin"] == "2026-08-23"
    assert r["ini"] == "2026-07-25"
    d0 = datetime.date.fromisoformat(r["ini"])
    d1 = datetime.date.fromisoformat(r["fin"])
    assert (d1 - d0).days + 1 == 30


def test_ventana_meses_retrocede_por_calendario():
    """3 meses desde agosto = junio, julio, agosto. Empieza el día 1 de junio."""
    r = detectar_ventana("los ultimos 3 meses", _TECHO)
    assert r["ini"] == "2026-06-01" and r["fin"] == "2026-08-23"


def test_ventana_meses_cruza_anio():
    r = detectar_ventana("los ultimos 3 meses", datetime.date(2026, 2, 10))
    assert r["ini"] == "2025-12-01"


def test_ventana_declara_el_supuesto():
    """Nada se asume en silencio: la ventana aterrizada se declara."""
    r = detectar_ventana("los ultimos 30 dias", _TECHO)
    assert r["asumido"] and "ventana=" in r["asumido"][0]


# ---------------- formas que NO deben resolver ----------------

@pytest.mark.parametrize("frase", [
    "cuanto produjo Castilla en abril",
    "cuanto produjo Castilla el 15 de mayo",
    "cuanto produjo Castilla ayer",
    "acumulado de Castilla hasta hoy",
    "produccion acumulada de Castilla en lo que va del año",
    "cuanto produjo Castilla",
])
def test_ventana_no_captura_lo_ajeno(frase):
    assert detectar_ventana(frase, _TECHO) is None, frase


def test_ventana_sin_marcador_explicito_no_resuelve():
    """«los 30 días» sin «últimos» ya lo captura _RX_RANGO_GUARDA y cae al rechazo honesto.
    Ampliar la ventana a esa forma le robaría ese rechazo."""
    assert detectar_ventana("produccion de Castilla en los 30 dias", _TECHO) is None


def test_ventana_sin_techo_no_inventa_ancla():
    assert detectar_ventana("los ultimos 30 dias", None) is None


@pytest.mark.parametrize("frase", [
    "los ultimos 9999 dias",
    "los ultimos 400 dias",
    "los ultimos 60 meses",
    "las ultimas 200 semanas",
])
def test_ventana_fuera_de_rango_se_rechaza(frase):
    assert detectar_ventana(frase, _TECHO) is None, frase


def test_ventana_cardinal_desconocido_no_adivina():
    assert detectar_ventana("los ultimos muchos dias", _TECHO) is None


# ---------------- integración con extraer_slots ----------------

def test_slots_expone_la_ventana():
    s = extraer_slots("produccion de Castilla en los ultimos 30 dias",
                      entidad_valor="CASTILLA", techo=_TECHO)
    assert s["ventana"] is not None and s["ventana"]["cantidad"] == 30


def test_slots_ventana_es_none_cuando_no_se_pide():
    s = extraer_slots("cuanto produjo Castilla en abril", entidad_valor="CASTILLA",
                      techo=_TECHO)
    assert s["ventana"] is None


@pytest.mark.parametrize("frase,nivel", [
    ("cuanto produjo Castilla", "N1"),
    ("acumulado de Castilla", "N2"),
    ("produccion de Castilla mes a mes", "N3"),
    ("como vario Castilla mes a mes", "N4"),
    ("produccion dia a dia de Castilla en junio", "N1DSER"),
])
def test_ventana_no_altera_ningun_nivel_existente(frase, nivel):
    """🔑 REGRESIÓN CENTRAL. La ventana es ADITIVA: si algún nivel cambiara de valor por
    culpa de esta capa, el plan habría roto Cuantificar en silencio."""
    assert extraer_slots(frase, techo=_TECHO)["nivel_temporal"] == nivel


def test_ventana_no_pisa_el_selector_de_dia():
    """«el mejor día de los últimos 30 días» sigue siendo un selector de día (N1DSEL).
    La ventana convive con él; no lo sustituye."""
    s = extraer_slots("el mejor dia de castilla de los ultimos 30 dias", techo=_TECHO)
    assert s["nivel_temporal"] == "N1DSEL"
    assert s["ventana"] is not None


def test_ventana_no_declara_mes_actual_como_default():
    """Declarar a la vez «periodo=mes actual» y una ventana es una contradicción."""
    s = extraer_slots("produccion de Castilla en los ultimos 30 dias", techo=_TECHO)
    assert not any("periodo=mes actual" in d for d in s["defaults_asumidos"])
    assert any("ventana=" in d for d in s["defaults_asumidos"])


def test_periodo_texto_no_se_contamina():
    """🔑 `periodo_texto` alimenta ranking.py:199 y analisis/api.py:390, que esperan un mes
    o None. Una ventana filtrándose ahí haría que el motor respondiera el mes por defecto
    sin avisar — el bug del periodo ignorado."""
    s = extraer_slots("produccion de Castilla en los ultimos 30 dias", techo=_TECHO)
    assert s["periodo_texto"] is None


def test_mes_pasado_sigue_funcionando():
    """H1: «mes pasado» YA estaba soportado antes de este plan. Test de no-regresión."""
    s = extraer_slots("cuanto produjo Castilla el mes pasado", techo=_TECHO)
    assert s["periodo_texto"] == "mes pasado"


# ---------------- la ruta real ----------------

@pytest.mark.parametrize("frase", [
    "produccion de Castilla en los ultimos 30 dias",
    "como viene Castilla en las ultimas 6 semanas",
    "produccion de Castilla el ultimo mes",
])
def test_ruta_real_pide_techo(frase):
    """🔑 El techo NO se pasa a mano: producción lo pide solo si `menciona_dia` dice que sí
    (respuesta_cuantificar.py:321). Sin la rama de ventana en `menciona_dia`, la ventana
    funcionaría en los tests y NO en producción."""
    assert menciona_dia(frase) is True
    techo = _TECHO if menciona_dia(frase) else None
    assert extraer_slots(frase, techo=techo)["ventana"] is not None


@pytest.mark.parametrize("frase", [
    "cuanto produjo Castilla en abril",
    "acumulado hasta hoy",
])
def test_menciona_dia_no_pide_techo_de_mas(frase):
    """La rama nueva no debe hacer que se pague una consulta de techo en preguntas mensuales."""
    assert menciona_dia(frase) is False


def test_centinela_no_se_filtra_al_resultado():
    """`menciona_dia` usa TECHO_CENTINELA (año 2000). Esa fecha es un artefacto interno y
    jamás debe aparecer en una ventana devuelta por la ruta real."""
    r = detectar_ventana("los ultimos 30 dias", TECHO_CENTINELA)
    assert r is not None and r["fin"].startswith("2000")   # solo aquí, por construcción
    s = extraer_slots("los ultimos 30 dias", techo=_TECHO)
    assert s["ventana"]["fin"] == "2026-08-23"
