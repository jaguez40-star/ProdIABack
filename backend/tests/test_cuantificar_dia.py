"""tests/test_cuantificar_dia.py — Grano DÍA (plan QV2-GRANO-DIA, 2026-08-25).

Cubre: parseo puro de fecha/selector (slots.py), la separación de sets de rechazo entre la
ruta de ENTIDAD y el fork de RANKING (A-1), los ejecutores N1D/N1DSEL con dependencias
inyectadas (sin BD) y que `formatear_cuerpo` no reviente con KeyError (A-4).
"""
import datetime as dt

import pytest

from app.features.consulta_v2.cuantificar.slots import detectar_dia, menciona_dia
from app.features.consulta_v2.cuantificar.ejecutor import (
    ejecutar_n1d, ejecutar_n1dsel, fecha_es,
)
from app.features.consulta_v2.cuantificar.validador import formatear_cuerpo
from app.features.consulta_v2.respuesta_cuantificar import (
    _forma_no_soportada, _forma_no_soportada_ranking,
)

_TECHO = dt.date(2026, 5, 17)


# ---------------- slots.detectar_dia / menciona_dia (módulo PURO, sin BD) ----------------

def test_detecta_fecha_explicita_con_mes():
    """Sin año explícito en el texto: se asume el del techo (DD-6) y se declara en 'asumido'."""
    r = detectar_dia("cuanto produjo Castilla el 15 de mayo", _TECHO)
    assert r == {"clase": "fecha", "fecha": "2026-05-15", "asumido": ["año=2026"]}


def test_detecta_fecha_con_anio_explicito_no_asume():
    r = detectar_dia("cuanto produjo Castilla el 15 de mayo de 2025", _TECHO)
    assert r["fecha"] == "2025-05-15"
    assert r["asumido"] == []


def test_detecta_dia_solo_usa_el_techo_para_mes_y_anio():
    r = detectar_dia("cuanto produjo Castilla el 15", _TECHO)
    assert r["clase"] == "fecha"
    assert r["fecha"] == "2026-05-15"
    assert r["asumido"] == ["mes=05/2026"]


def test_dia_solo_sin_techo_no_resuelve():
    assert detectar_dia("cuanto produjo Castilla el 15", None) is None


def test_detecta_relativos():
    assert detectar_dia("cuanto produjo Castilla ayer", _TECHO) == {"clase": "relativo", "delta": -1}
    assert detectar_dia("cuanto produjo Castilla hoy", _TECHO) == {"clase": "relativo", "delta": 0}
    assert detectar_dia("cuanto produjo Castilla anteayer", _TECHO) == {"clase": "relativo", "delta": -2}
    assert detectar_dia("cuanto produjo Castilla antier", _TECHO) == {"clase": "relativo", "delta": -2}


def test_detecta_selector_con_mes_explicito():
    r = detectar_dia("peor dia de Castilla en mayo", _TECHO)
    assert r == {"clase": "selector", "orden": "min", "anio": 2026, "mes": 5, "asumido": []}


def test_detecta_selector_sin_mes_asume_el_del_techo():
    r = detectar_dia("mejor dia de Castilla este mes", _TECHO)
    assert r["clase"] == "selector"
    assert r["orden"] == "max"
    assert r["anio"] == 2026 and r["mes"] == 5
    assert r["asumido"] == ["periodo=05/2026"]


def test_selector_sin_mes_ni_techo_no_resuelve():
    assert detectar_dia("mejor dia de Castilla", None) is None


# ---------------- QV2-DIA-SEL (2026-08-26): la DIRECCIÓN del selector ----------------
# El bug: se preguntaba por el día de producción MÁS BAJA y se respondía el de producción MÁS
# ALTA, afirmándolo sin avisar. El detector miraba el CUANTIFICADOR (mas/menos) e ignoraba el
# ADJETIVO (alta/baja), que es donde vive el sentido en español.
#
# 🔑 Cada caso asserta la TUPLA (orden, mes), no solo el orden. Con solo el orden, «que dia fue
#    el de MAYOR produccion» pasa en verde con mes=5: "MAYO" es substring de "MAYOR" y
#    slots.py:124 buscaba el mes con `in t`. El test habría cerrado en verde con la respuesta
#    equivocada.
_TECHO_AGO = dt.date(2026, 8, 18)


def _sel(frase, techo=_TECHO_AGO):
    """(orden, mes) del selector, o (None, None) si la pregunta no se resuelve como tal."""
    r = detectar_dia(frase, techo)
    if not r or r.get("clase") != "selector":
        return (None, None)
    return (r.get("orden"), r.get("mes"))


# --- Bloque 1: las 16 formas medidas (8 fallaban: 3 invertidas + 5 sin detectar) ---
@pytest.mark.parametrize("frase, orden", [
    # MÍNIMO — el adjetivo manda sobre el cuantificador
    ("que dia fue el de produccion mas baja en castilla", "min"),
    ("que dia tuvo la produccion mas bajo castilla", "min"),
    ("en que dia bajo mas la produccion de castilla", "min"),
    ("que dias fue la produccion mas baja en castilla", "min"),
    ("que dia fue el de menor produccion en castilla", "min"),
    ("que dia se produjo menos crudo en castilla", "min"),
    ("cual fue el peor dia de castilla", "min"),
    ("dia de menor produccion de castilla", "min"),
    # MÁXIMO
    ("que dia fue el de produccion mas alta en castilla", "max"),
    ("que dia tuvo la produccion mas alto castilla", "max"),
    ("que dias fue la produccion mas alta en castilla", "max"),
    ("que dia fue el de mayor produccion en castilla", "max"),
    ("que dia se produjo mas crudo en castilla", "max"),
    ("cual fue el mejor dia de castilla", "max"),
    ("dia de mayor produccion de castilla", "max"),
    ("el dia de mas produccion de castilla", "max"),
])
def test_selector_direccion(frase, orden):
    """El mes debe ser el del TECHO (8): ninguna frase nombra un mes."""
    assert _sel(frase) == (orden, 8)


# --- Bloque 2: la dirección se lee en la VECINDAD del día, no en toda la frase ---
# "el mejor día del PEOR mes" es un máximo: un PEOR a diez palabras no puede voltearlo.
@pytest.mark.parametrize("frase, orden", [
    ("cual fue el mejor dia del peor mes", "max"),
    ("que dia tuvo mayor produccion en el campo con menos pozos", "max"),
    ("que dia tuvo la produccion mas baja en el mejor campo", "min"),
])
def test_selector_direccion_por_proximidad(frase, orden):
    assert _sel(frase)[0] == orden


# --- Bloque 3: verbos de dirección ---
# La rev.1 metió CAYO en el detector y se olvidó de meterlo en el léxico: detectaba... y
# respondía el máximo. Una inversión NUEVA, creada por el propio arreglo.
@pytest.mark.parametrize("frase, orden", [
    ("en que dia cayo mas la produccion de castilla", "min"),
    ("en que dia se desplomo la produccion de castilla", "min"),
    ("en que dia subio mas la produccion de castilla", "max"),
])
def test_selector_verbos_de_direccion(frase, orden):
    assert _sel(frase)[0] == orden


# --- Bloque 4: ambigüedad -> NO se elige en silencio ---
def test_selector_dos_direcciones_no_resuelve():
    """Regla del proyecto: si la dirección no se puede determinar, no se responde. Antes elegía
    `min` en silencio porque la primera coincidencia ganaba."""
    assert detectar_dia("el dia de mas produccion y el de menos", _TECHO_AGO) is None


# --- Bloque 5: falsos positivos (el token de dirección NO es un superlativo de producción) ---
@pytest.mark.parametrize("frase", [
    "que dia se hizo el mantenimiento mayor",           # terminología de industria
    "en que dias hubo mas de 5000 barriles",            # umbral, no superlativo
    "en que dias la produccion estuvo bajo el presupuesto",   # BAJO preposición, no adjetivo
    "cuantos dias con reporte tiene castilla",
    "produccion dia a dia de castilla",
    "promedio diario de castilla",
])
def test_selector_falsos_positivos(frase):
    assert detectar_dia(frase, _TECHO_AGO) is None


# --- Bloque 6: el mes por TOKEN, no por substring ---
def test_mayor_no_se_confunde_con_mayo():
    """[2026-08-26] "MAYO" es substring de "MAYOR". Con `in t`, «día de MAYOR producción» daba
    mes=5 y `asumido=[]`: el sistema creía que el usuario había dicho mayo, y no avisaba."""
    r = detectar_dia("dia de mayor produccion de castilla", _TECHO_AGO)
    assert r["mes"] == 8                       # el del techo, no mayo
    assert r["asumido"] == ["periodo=08/2026"]  # y se DECLARA que se asumió


def test_mes_explicito_sigue_ganando_al_techo():
    r = detectar_dia("que dia fue el de produccion mas baja en julio", _TECHO_AGO)
    assert (r["orden"], r["mes"], r["asumido"]) == ("min", 7, [])


# ---------------- QV2-SERIE-DIA (2026-08-26): la curva diaria de un mes ----------------
# No existía nivel para «la producción día a día de Akacias en junio»: las únicas dos puertas al
# panel diario eran nombrar un día concreto o pedir el mejor/peor, así que todas estas formas
# caían a N1 y respondían el KPI del mes. La curva ya se dibujaba; faltaba la entrada.

@pytest.mark.parametrize("frase, mes", [
    ("Muestrame la produccion dia a dia de campo Akacias el mes de Junio", 6),
    ("produccion diaria de Akacias en junio", 6),
    ("curva diaria de Akacias en junio", 6),
    ("como se comporto Akacias dia a dia en junio", 6),
    ("produccion de Akacias por dia", 8),          # sin mes → el del techo
])
def test_serie_dia_detecta_nivel_y_mes(frase, mes):
    from app.features.consulta_v2.cuantificar.slots import extraer_slots
    sl = extraer_slots(frase, techo=_TECHO_AGO)
    assert sl["nivel_temporal"] == "N1DSER"
    assert sl["serie_dia"]["mes"] == mes


@pytest.mark.parametrize("frase, nivel", [
    ("cuanto produjo Akacias el 15 de junio", "N1D"),        # el día CONCRETO gana
    ("cual fue el mejor dia de Akacias en junio", "N1DSEL"),  # el selector gana
    ("produccion de Akacias mes a mes", "N3"),                # serie MENSUAL, sin cambio
    ("como va Akacias contra el promedio diario", "N1"),      # referencia, no pedido de curva
    ("cuanto produjo Akacias en junio", "N1"),                # el mes puntual, sin cambio
])
def test_serie_dia_no_secuestra_otros_niveles(frase, nivel):
    from app.features.consulta_v2.cuantificar.slots import extraer_slots
    assert extraer_slots(frase, techo=_TECHO_AGO)["nivel_temporal"] == nivel


def test_serie_dia_panel_sin_dia_marcado():
    """Reusa `cuant_dia_panel`: la curva del mes ya se dibujaba entera y solo llevaba un punto
    encima. Aquí no hay punto que marcar — la respuesta ES la curva."""
    from app.features.consulta_v2.cuantificar.slots import extraer_slots
    from app.features.consulta_v2.cuantificar.ejecutor import ejecutar_n1dser

    def _curva(ent, anio, mes, prod, nivel=None):
        return [(dt.date(anio, mes, d), 70000 + d * 300) for d in range(1, 15)]

    ent = {"valor": "AKACIAS", "nivel": "campo", "rama": "A", "zoom": []}
    res = ejecutar_n1dser(ent, extraer_slots("produccion dia a dia de Akacias en junio",
                                             techo=_TECHO_AGO), _curva_fn=_curva)
    assert res["nivel"] == "N1DSER" and res["dias_con_dato"] == 14
    assert _PANEL_TIPO["N1DSER"] == "cuant_dia_panel"
    d = _panel_datos(res)
    assert d["dia_marcado"] is None
    assert d["periodo"] == "junio 2026" and d["entidad"] == "AKACIAS"


@pytest.mark.parametrize("frase", [
    "Muestrame dia a dia la produccion de crudo del campo Pauto Sur",
    "Muestrame dia a dia la produccion de blancos del campo Pauto Sur",
    "Muestrame dia a dia la produccion de Pauto Sur este mes",
    "produccion diaria de Akacias",
    "curva diaria de Castilla",
])
def test_serie_dia_POR_LA_RUTA_REAL(frase):
    """🔑 El techo NO se pasa a mano: se pide solo si `menciona_dia` dice que sí
    (respuesta_cuantificar:268-272). Este test reproduce ESA cadena.

    Sin él, el bug pasó desapercibido: `menciona_dia` delegaba solo en `detectar_dia`, que no
    conoce la serie diaria, así que devolvía False → no se consultaba el techo → sin mes que
    resolver, la pregunta se degradaba a N1 y respondía el KPI del mes. Todas las pruebas
    anteriores pasaban el techo explícito y por eso salían en verde con el bug vivo.
    """
    from app.features.consulta_v2.cuantificar.slots import extraer_slots, menciona_dia
    techo = _TECHO_AGO if menciona_dia(frase) else None      # exactamente lo que hace producción
    assert extraer_slots(frase, techo=techo)["nivel_temporal"] == "N1DSER"


@pytest.mark.parametrize("frase", [
    "cuanto produjo Castilla en junio",
    "produccion de Castilla mes a mes",
    "acumulado del ano de Castilla",
])
def test_menciona_dia_no_pide_techo_de_mas(frase):
    """El pre-check existe para AHORRAR un round-trip a BD en el tráfico mensual, que es la
    inmensa mayoría. Ampliarlo a la serie diaria no puede costarle eso."""
    from app.features.consulta_v2.cuantificar.slots import menciona_dia
    assert menciona_dia(frase) is False


def test_serie_dia_blancos_se_muestra_con_aviso():
    """[2026-08-26] Decisión del usuario, reafirmada: la curva diaria de BLANCOS SÍ se muestra.
    Lo que no reconcilia es su MAGNITUD (el reporte diario suma conceptos repetidos), no su forma
    — y la forma es lo que se pide. Se responde CON el aviso, en vez de negar un dato que existe.
    A grano día PUNTUAL (N1D/N1DSEL) el rechazo sigue en pie: ahí la respuesta ES una cifra."""
    from app.features.consulta_v2.cuantificar.slots import extraer_slots
    from app.features.consulta_v2.cuantificar.ejecutor import ejecutar_n1dser

    def _curva(ent, anio, mes, prod, nivel=None):
        return [(dt.date(anio, mes, d), 60000) for d in range(1, 19)]

    sl = extraer_slots("dia a dia de blancos de Pauto Sur en junio", techo=_TECHO_AGO)
    assert sl["producto"] == "blancos" and sl["nivel_temporal"] == "N1DSER"
    r = ejecutar_n1dser({"valor": "PAUTO SUR", "nivel": "campo", "rama": "A", "zoom": []},
                        sl, _curva_fn=_curva)
    assert r["aplica"] is True
    assert any("no reconcilia" in a.lower() for a in r["avisos"])


def test_serie_dia_declara_el_mes_asumido():
    from app.features.consulta_v2.cuantificar.slots import extraer_slots
    from app.features.consulta_v2.cuantificar.ejecutor import ejecutar_n1dser

    def _curva(ent, anio, mes, prod, nivel=None):
        return [(dt.date(anio, mes, d), 70000) for d in range(1, 15)]

    ent = {"valor": "AKACIAS", "nivel": "campo", "rama": "A", "zoom": []}
    r = ejecutar_n1dser(ent, extraer_slots("produccion dia a dia de Akacias", techo=_TECHO_AGO),
                        _curva_fn=_curva)
    assert any("no me dijiste el mes" in a.lower() for a in r["avisos"])
    # El aviso de «sin presupuesto diario» se retiró de N1D/N1DSEL a propósito (3bb4108):
    # esta rama es su hermana y no puede devolverlo por la puerta de atrás.
    assert not any("presupuesto" in a.lower() for a in r["avisos"])


def test_n1dsel_declara_el_mes_asumido():
    """[2026-08-26] `detectar_dia` ya marcaba el periodo asumido, pero el ejecutor emitía
    `avisos: []` fijo: la respuesta afirmaba «el mejor día de agosto» a quien no había nombrado
    agosto, sin decir que lo suponía."""
    from app.features.consulta_v2.cuantificar.slots import extraer_slots

    def _curva(ent, anio, mes, prod, nivel=None):
        return [(dt.date(anio, mes, d), 200000 + d * 100) for d in range(1, 19)]

    ent = {"valor": "CASTILLA", "nivel": "campo", "rama": "A", "zoom": []}
    sin_mes = ejecutar_n1dsel(ent, extraer_slots("el mejor dia de castilla", techo=_TECHO_AGO),
                              _curva_fn=_curva)
    assert any("no me dijiste el mes" in a.lower() for a in sin_mes["avisos"])
    assert "agosto 2026" in sin_mes["avisos"][0]
    # Con el mes en la pregunta no se asume nada, así que no hay aviso que dar.
    con_mes = ejecutar_n1dsel(ent, extraer_slots("el mejor dia de castilla en julio", techo=_TECHO_AGO),
                              _curva_fn=_curva)
    assert con_mes["avisos"] == []


# --- negativos: NO deben detectarse como grano día ---

def test_negativo_acumulado_hasta_hoy():
    assert detectar_dia("acumulado hasta hoy", _TECHO) is None
    assert detectar_dia("produccion acumulada hasta hoy", _TECHO) is None
    assert detectar_dia("en lo que va del año hasta hoy", _TECHO) is None


def test_negativo_mes_normal():
    assert detectar_dia("cuanto produjo Castilla en abril", _TECHO) is None


def test_fecha_inexistente_no_se_construye():
    """[2026-08-25] Hallazgo de la verificación posterior al plan. Validar solo `1 <= d <= 31`
    dejaba pasar "el 31 de febrero" → la cadena '2026-02-31' llegaba a `ejecutar_n1d` y
    `date.fromisoformat` lanzaba `ValueError: day is out of range for month`, una excepción NO
    capturada que tumbaba la respuesta entera. Ahora la combinación se valida contra el
    calendario real y la pregunta cae a la ruta mensual normal."""
    assert detectar_dia("cuanto produjo Castilla el 31 de febrero", _TECHO) is None
    assert detectar_dia("cuanto produjo Castilla el 30 de febrero de 2026", _TECHO) is None
    assert detectar_dia("cuanto produjo Castilla el 31 de abril", _TECHO) is None
    # 2026 NO es bisiesto: el 29 de febrero tampoco existe.
    assert detectar_dia("cuanto produjo Castilla el 29 de febrero de 2026", _TECHO) is None
    # ...pero 2024 SÍ lo fue: la guarda no puede pasarse de estricta.
    assert detectar_dia("cuanto produjo Castilla el 29 de febrero de 2024", _TECHO) is not None
    # Días válidos de meses de 30 y 31 días siguen pasando.
    assert detectar_dia("cuanto produjo Castilla el 30 de abril", _TECHO) is not None
    assert detectar_dia("cuanto produjo Castilla el 31 de mayo", _TECHO) is not None


def test_negativo_rango_y_semana_y_trimestre():
    assert detectar_dia("del 1 al 15", _TECHO) is None
    assert detectar_dia("esta semana", _TECHO) is None
    assert detectar_dia("cuanto en el primer trimestre", _TECHO) is None


def test_menciona_dia_pre_check():
    assert menciona_dia("cuanto produjo Castilla el 15 de mayo") is True
    assert menciona_dia("mejor dia de Castilla este mes") is True
    assert menciona_dia("ayer") is True
    assert menciona_dia("cuanto produjo en abril") is False
    assert menciona_dia("acumulado hasta hoy") is False
    assert menciona_dia("del 1 al 15") is False


# ---------------- Separación de sets (A-1): ruta ENTIDAD vs fork RANKING ----------------

def test_dia_no_se_rechaza_en_ruta_entidad():
    """'dia'/'selector_dia' SALEN del set de la ruta de entidad: ahora los construye N1D/N1DSEL."""
    assert _forma_no_soportada("cuanto produjo Castilla el 15 de mayo") is None
    assert _forma_no_soportada("mejor dia de Castilla este mes") is None


def test_dia_sigue_rechazado_en_el_ranking():
    """El ranking N5 es MENSUAL por construcción (ranking.py::_fin_mes). Si 'dia' saliera de
    este set, "top 5 campos el 15 de mayo" degradaría en silencio al ranking del MES ENTERO —
    exactamente el bug #5 que este check existe para impedir."""
    assert _forma_no_soportada_ranking("top 5 campos el 15 de mayo") == "dia"
    # [2026-08-26 · QV2-DIA-SEL] Ordenar CAMPOS por su mejor/peor día ya no se rechaza con el
    # código `selector_dia`, cuyo texto está escrito para una entidad FIJA («¿el mejor día de
    # Castilla?») y respondía «me pediste el día de mayor o menor producción… puedo darte el
    # total del mes» a quien preguntaba por campos. Sigue siendo un rechazo — la capacidad no
    # existe — pero con un código y un texto que nombran lo que de verdad se pidió.
    assert _forma_no_soportada_ranking("cual campo tuvo el mejor dia") == "ranking_dia"
    assert _forma_no_soportada_ranking("cuales campos tuvieron los peores dias") == "ranking_dia"


def test_rango_trimestre_semana_siguen_rechazados_en_ambas_rutas():
    assert _forma_no_soportada("del 1 al 15") == "rango_dias"
    assert _forma_no_soportada_ranking("del 1 al 15") == "rango_dias"
    assert _forma_no_soportada("cuanto en el primer trimestre") == "trimestre"
    assert _forma_no_soportada_ranking("esta semana") == "semana"


# ---------------- ejecutar_n1d (dependencia inyectada, SIN BD) ----------------

def _resuelta(valor="CASTILLA", nivel="campo", rama="A"):
    return {"valor": valor, "nivel": nivel, "rama": rama, "zoom": []}


def _slots_n1d(fecha_iso, producto="crudo"):
    return {"producto": producto, "unidad": "bbl", "dia": {"clase": "fecha", "fecha": fecha_iso},
            "defaults_asumidos": [], "variable": "produccion_crudo"}


def test_ejecutar_n1d_con_dato():
    def _fn(entidad, fecha, nivel=None):
        assert entidad == "CASTILLA" and str(fecha) == "2026-05-15"
        return {"por_producto": {"CRUDO": 223752.36}, "techo": _TECHO, "hay_dato": True}

    res = ejecutar_n1d(_resuelta(), _slots_n1d("2026-05-15"), _dia_fn=_fn)
    assert res["aplica"] is True
    assert res["nivel"] == "N1D"
    assert res["resultado"]["valor"] == 223752.36
    assert res["fecha"] == "2026-05-15"
    assert res["fecha_label"] == "viernes 15 de mayo de 2026"
    assert res["referencia_valor"] is None and res["cumplimiento_pct"] is None
    # [2026-08-25] No se destaca lo que falta: el cuerpo de N1D nunca ofrece cumplimiento,
    # así que ya no se anuncia la ausencia de presupuesto diario.
    assert res["avisos"] == []


def test_ejecutar_n1d_sin_dato_cita_el_techo_real():
    def _fn(entidad, fecha, nivel=None):
        return {"por_producto": {}, "techo": _TECHO, "hay_dato": False}

    res = ejecutar_n1d(_resuelta(), _slots_n1d("2026-08-24"), _dia_fn=_fn)
    assert res["aplica"] is False
    assert "17 de mayo de 2026" in res["texto"]           # cita el techo CONSULTADO, no una constante
    assert "CASTILLA" in res["texto"]


def test_ejecutar_n1d_relativo_no_llama_bd_con_fecha_de_hoy():
    llamado = {}

    def _fn(entidad, fecha, nivel=None):
        llamado["fecha"] = fecha
        return {"por_producto": {}, "techo": _TECHO, "hay_dato": False}

    ejecutar_n1d(_resuelta(), {"producto": "crudo", "unidad": "bbl",
                              "dia": {"clase": "relativo", "delta": -1},
                              "defaults_asumidos": []}, _dia_fn=_fn)
    assert llamado["fecha"] == dt.date.today() - dt.timedelta(days=1)


def test_ejecutar_n1d_blancos_siempre_rechaza():
    """DD-5: produccion_blancos.granos.dia = confianza:no. No debe consultarse la BD siquiera
    con hay_dato=True — el rechazo es por catálogo, no por ausencia de datos."""
    def _fn(entidad, fecha, nivel=None):
        return {"por_producto": {"BLANCOS": 999.0}, "techo": _TECHO, "hay_dato": True}

    res = ejecutar_n1d(_resuelta(), _slots_n1d("2026-05-15", producto="blancos"), _dia_fn=_fn)
    assert res["aplica"] is False
    assert "blancos" in res["texto"].lower()


def test_ejecutar_n1d_filial_rechaza_por_rechazo_comun():
    res = ejecutar_n1d(_resuelta(rama="B"), _slots_n1d("2026-05-15"))
    assert res["aplica"] is False
    assert "filial" in res["texto"].lower()


# ---------------- ejecutar_n1dsel (dependencia inyectada, SIN BD) ----------------

def _slots_sel(anio=2026, mes=5, orden="max", producto="crudo"):
    return {"producto": producto, "unidad": "bbl",
            "dia": {"clase": "selector", "orden": orden, "anio": anio, "mes": mes, "asumido": []},
            "defaults_asumidos": [], "variable": "produccion_crudo"}


def test_ejecutar_n1dsel_mejor_dia():
    curva = [(dt.date(2026, 5, 1), 221541.76), (dt.date(2026, 5, 2), 226644.28),
            (dt.date(2026, 5, 8), 227090.28), (dt.date(2026, 5, 17), 221031.40)]

    def _fn(entidad, anio, mes, producto, nivel=None):
        return curva

    res = ejecutar_n1dsel(_resuelta(), _slots_sel(orden="max"), _curva_fn=_fn)
    assert res["aplica"] is True
    assert res["nivel"] == "N1DSEL"
    assert res["fecha"] == "2026-05-08"
    assert res["resultado"]["valor"] == 227090.28
    assert res["dias_con_dato"] == 4
    assert res["rango"] == ["2026-05-01", "2026-05-17"]


def test_ejecutar_n1dsel_peor_dia():
    curva = [(dt.date(2026, 5, 1), 221541.76), (dt.date(2026, 5, 3), 215209.00),
            (dt.date(2026, 5, 8), 227090.28)]

    def _fn(entidad, anio, mes, producto, nivel=None):
        return curva

    res = ejecutar_n1dsel(_resuelta(), _slots_sel(orden="min"), _curva_fn=_fn)
    assert res["fecha"] == "2026-05-03"
    assert res["resultado"]["valor"] == 215209.00


def test_ejecutar_n1dsel_sin_curva():
    res = ejecutar_n1dsel(_resuelta(), _slots_sel(), _curva_fn=lambda *a, **k: [])
    assert res["aplica"] is False


def test_ejecutar_n1dsel_blancos_rechaza():
    res = ejecutar_n1dsel(_resuelta(), _slots_sel(producto="blancos"),
                          _curva_fn=lambda *a, **k: [(dt.date(2026, 5, 1), 999.0)])
    assert res["aplica"] is False
    assert "blancos" in res["texto"].lower()


# ---------------- validador.formatear_cuerpo — no debe reventar con KeyError (A-4) ----------------

def test_formatear_cuerpo_n1d_no_lanza_keyerror():
    res = {
        "nivel": "N1D", "producto": "crudo", "unidad": "bbl",
        "entidad_cualificada": "el Campo CASTILLA", "fecha_label": "viernes 15 de mayo de 2026",
        "resultado": {"valor": 223752.36},
        "avisos": ["aviso de prueba"],   # el mecanismo de render, no un aviso real de ejecutor
    }
    txt = formatear_cuerpo(res)
    assert "223.752" in txt
    assert "viernes 15 de mayo de 2026" in txt
    assert "⚠️" in txt


def test_formatear_cuerpo_n1dsel_no_lanza_keyerror():
    res = {
        "nivel": "N1DSEL", "producto": "crudo", "unidad": "bbl",
        "entidad_cualificada": "el Campo CASTILLA", "orden": "max",
        "mes_label": "mayo 2026", "fecha_label": "viernes 8 de mayo de 2026",
        "resultado": {"valor": 227090.28}, "dias_con_dato": 17,
        "avisos": [],
    }
    txt = formatear_cuerpo(res)
    assert "mejor" in txt.lower()
    assert "227.090" in txt
    assert "17 días" in txt


def test_fecha_es_tabla_manual_no_usa_ingles():
    """A-5: strftime('%A') devuelve inglés en esta máquina. fecha_es debe usar SIEMPRE las
    tablas manuales, nunca locale."""
    assert fecha_es(dt.date(2026, 5, 15)) == "viernes 15 de mayo de 2026"
    assert "Friday" not in fecha_es(dt.date(2026, 5, 15))


# ---------------- QV2-PANEL-DIA (2026-08-25): contrato del panel «Comportamiento {Producto}» ----------------

from app.features.consulta_v2.respuesta_cuantificar import _panel_datos, _PANEL_TIPO


def _res_n1d(fecha="2026-05-15", producto="crudo", nivel="campo", valor=223752.36):
    return {
        "nivel": "N1D", "grano": "dia", "producto": producto, "unidad": "bbl",
        "entidad": {"nombre": "CASTILLA", "nivel": nivel, "fue_asumida": False},
        "entidad_cualificada": "el Campo CASTILLA",
        "fecha": fecha, "fecha_label": "viernes 15 de mayo de 2026",
        "resultado": {"valor": valor}, "avisos": [],
    }


def _res_n1dsel(fecha="2026-05-08", orden="max"):
    r = _res_n1d(fecha=fecha, valor=227090.28)
    r.update({"nivel": "N1DSEL", "orden": orden, "mes_label": "mayo 2026",
             "dias_con_dato": 17, "rango": ["2026-05-01", "2026-05-17"]})
    return r


def test_panel_datos_n1d_lleva_periodo_y_dia_marcado():
    d = _panel_datos(_res_n1d())
    assert d["periodo"] == "mayo 2026"
    assert d["productos"] == ["CRUDO"]
    assert d["dia_marcado"] == "2026-05-15"
    assert d["entidad"] == "CASTILLA"
    assert d["segmento"] == "ecp"


def test_panel_datos_n1dsel_lleva_periodo_y_campos_del_selector():
    d = _panel_datos(_res_n1dsel())
    assert d["periodo"] == "mayo 2026"
    assert d["dia_marcado"] == "2026-05-08"
    assert d["orden"] == "max"
    assert d["mes_label"] == "mayo 2026"
    assert d["dias_con_dato"] == 17
    assert d["rango"] == ["2026-05-01", "2026-05-17"]


def test_panel_datos_el_periodo_sigue_a_la_pregunta_no_al_techo():
    """[2026-08-25] Decisión del usuario: si preguntan por marzo, el panel muestra marzo — no el
    último mes con dato diario (mayo). `periodo` sale de `res["fecha"]`, nunca de un techo externo."""
    d = _panel_datos(_res_n1d(fecha="2026-03-15"))
    assert d["periodo"] == "marzo 2026"
    assert d["dia_marcado"] == "2026-03-15"


def test_panel_tipo_n1d_y_n1dsel_son_cuant_dia_panel():
    assert _PANEL_TIPO["N1D"] == "cuant_dia_panel"
    assert _PANEL_TIPO["N1DSEL"] == "cuant_dia_panel"


def test_panel_datos_producto_gas():
    d = _panel_datos(_res_n1d(producto="gas"))
    assert d["productos"] == ["GAS"]
    assert "May" not in fecha_es(dt.date(2026, 5, 15))


# ---------------- QV2-PANEL-MES (2026-08-25): contrato del panel MENSUAL (N3 serie / N4 waterfall) ----------------

_SERIE = [{"mes": "Ene", "valor": 100, "num": 1}, {"mes": "Feb", "valor": 110, "num": 2},
          {"mes": "Mar", "valor": 60, "num": 3}]


def _res_n3():
    return {"nivel": "N3", "grano": "mes", "producto": "crudo", "unidad": "bbl",
            "entidad": {"nombre": "CASTILLA", "nivel": "campo", "fue_asumida": False},
            "entidad_cualificada": "el Campo CASTILLA", "avisos": [],
            "serie": _SERIE, "promedio": 105, "anio": 2026,
            "proyeccion_mes": "Mar", "mes_actual": 3}


def _res_n4():
    r = _res_n3()
    r.update({"nivel": "N4",
              "deltas": [{"de": "Ene", "a": "Feb", "delta": 10, "pct": 10.0},
                         {"de": "Feb", "a": "Mar", "delta": -50, "pct": -45.5}],
              "ultimo": {"de": "Feb", "a": "Mar", "delta": -50, "pct": -45.5}})
    r.pop("promedio")
    return r


def test_panel_datos_n3_lleva_la_serie_y_el_corte_de_proyeccion():
    d = _panel_datos(_res_n3())
    assert d["serie"] == _SERIE and d["promedio"] == 105
    assert d["mes_actual"] == 3 and d["proyeccion_mes"] == "Mar"


def test_panel_datos_n4_lleva_serie_ademas_de_deltas():
    """El waterfall necesita los NIVELES (barras `total` de partida y cierre), no solo los saltos."""
    d = _panel_datos(_res_n4())
    assert d["serie"] == _SERIE
    assert len(d["deltas"]) == len(d["serie"]) - 1
    assert d["mes_actual"] == 3


def test_panel_datos_n3_n4_no_emiten_productos():
    """El filete del bloque sale de [data-prod] en el HTML (multitab_shell.js:3375) y `producto` ya
    viaja: `productos` (la lista de N1D) aquí sería peso muerto en el contrato."""
    for res in (_res_n3(), _res_n4()):
        d = _panel_datos(res)
        assert "productos" not in d and d["producto"] == "crudo"


def test_panel_tipo_n3_y_n4_no_cambian():
    """QV2-PANEL-MES cambia el PINTOR, no el tipo de panel: la ruta incremental no toca el
    dispatcher de los demás niveles."""
    assert _PANEL_TIPO["N3"] == "cuant_serie"
    assert _PANEL_TIPO["N4"] == "cuant_var"


# ── [2026-08-25 · QV2-HILO-DIA] Regresión de los cuatro fallos reportados ──────────────────

def test_f1_dia_explicito_respeta_el_mes_escrito():
    """«el día 15 de mayo» debe dar MAYO, no el mes del techo (F1)."""
    import datetime
    from app.features.consulta_v2.cuantificar.slots import detectar_dia
    techo = datetime.date(2026, 8, 18)
    r = detectar_dia("el dia 15 de mayo cuanto produjo campo Castilla?", techo)
    assert r is not None and r["clase"] == "fecha"
    assert r["fecha"] == "2026-05-15", f"cambió el mes que el usuario dijo: {r['fecha']}"
    # La forma sin «día» ya funcionaba: no puede romperse.
    assert detectar_dia("el 15 de mayo?", techo)["fecha"] == "2026-05-15"


def test_f3_meses_mapean_a_su_numero_real():
    """setiembre/octubre/noviembre/diciembre estaban corridos un mes (F3)."""
    from app.features.consulta_v2.cuantificar.slots import _MESES_NUM
    assert _MESES_NUM["septiembre"] == 9
    assert _MESES_NUM["setiembre"] == 9
    assert _MESES_NUM["octubre"] == 10
    assert _MESES_NUM["noviembre"] == 11
    assert _MESES_NUM["diciembre"] == 12


def test_f3_fecha_de_octubre_y_diciembre_son_correctas():
    """Consecuencia de F3 en la ruta real."""
    import datetime
    from app.features.consulta_v2.cuantificar.slots import detectar_dia
    techo = datetime.date(2026, 8, 18)
    assert detectar_dia("el 5 de octubre", techo)["fecha"] == "2026-10-05"
    assert detectar_dia("el 3 de diciembre", techo)["fecha"] == "2026-12-03"


def test_f2_out_filtra_solo_lo_que_n1d_resuelve():
    """La rama OUT ignora el rechazo SOLO si N1D sabe resolver la forma (F2 + H-09)."""
    from app.features.consulta_v2.maquina_q import _TECHO_CENTINELA
    from app.features.consulta_v2.cuantificar import slots as _sd
    from app.features.consulta_v2 import no_soportado
    # El catálogo NO cambia: sigue clasificando la forma (lo necesita el ranking).
    assert no_soportado.detectar("el 15 de mayo?") == "dia"
    # Lo que N1D SÍ resuelve -> la rama OUT lo deja pasar.
    for t in ("el 15 de mayo?", "el dia 15 de mayo cuanto produjo Castilla",
              "cuanto produjo Castilla ayer", "el mejor dia del mes"):
        assert _sd.detectar_dia(t, _TECHO_CENTINELA) is not None, t
    # 🔑 H-09: lo que N1D NO resuelve conserva su rechazo honesto. Filtrar por CÓDIGO
    #    (en vez de por detectar_dia) dejaría estas tres mudas — regresión del bug #5.
    for t in ("cuanto produjo Castilla el lunes", "este dia cuanto produjo", "el ultimo dia"):
        assert no_soportado.detectar(t) == "dia", t
        assert _sd.detectar_dia(t, _TECHO_CENTINELA) is None, t


def test_f4_cambio_de_mes_hereda_la_entidad_del_contexto():
    """«y en mayo?» tras una cifra mensual continúa el hilo (F4)."""
    from app.features.consulta_v2.maquina_q import _continuacion
    ctx = {"grupo": "cuantificar", "entidad": "CASTILLA", "producto": "crudo"}
    for frase in ("y en mayo?", "y en junio", "y mayo?"):
        rw = _continuacion(frase, ctx)
        assert rw is not None, f"{frase!r} sigue perdiendo el hilo"
        assert "CASTILLA" in rw
    # Lo que ya funcionaba no se rompe.
    assert _continuacion("y el acumulado?", ctx) == "acumulado de CASTILLA"
    # Una frase que nombra entidad propia es autocontenida: NO se reescribe por esta puerta.
    assert "CASTILLA" not in (_continuacion("produccion de RUBIALES en mayo", ctx) or "")


def test_f4_no_secuestra_preguntas_estructurales():
    """🔑 H-10/H-13: una pregunta de ESTRUCTURA que menciona un mes NO se vuelve producción,
    ni por la rama _TEMP_CONT_KW (C4.b) ni por la rama "Drill N1 GENÉRICO" (C6)."""
    from app.features.consulta_v2.maquina_q import _continuacion
    ctx = {"grupo": "cuantificar", "entidad": "CASTILLA", "producto": "crudo"}
    for frase in ("cuantos pozos en mayo", "cuales campos en mayo", "que activo en mayo",
                  "cuantas gerencias tiene"):
        rw = _continuacion(frase, ctx)
        assert rw is None or not rw.startswith("produccion de"), \
            f"{frase!r} se convirtió en consulta de producción: {rw!r}"


def test_f4_c6_no_rompe_produccion_con_palabra_estructural_generica():
    """🔑 H-13: el guarda de C6 NO debe bloquear producción real que menciona "campo"/"pozo"
    de forma genérica, siempre que traiga un verbo de producción EXPLÍCITO."""
    from app.features.consulta_v2.maquina_q import _continuacion
    ctx = {"grupo": "cuantificar", "entidad": "CASTILLA", "producto": "crudo"}
    # <=5 tokens para no topar con el corte de longitud (ajeno a C6, ver nota de H-13).
    rw = _continuacion("produjo el campo en mayo", ctx)
    assert rw is not None and rw.startswith("produccion de"), \
        f"regresión: producción real bloqueada por mencionar 'campo': {rw!r}"


def test_f4_dia_puntual_elidido_sigue_dando_n1d():
    """H-12: «y el 15 de mayo?» hereda entidad y conserva el grano día."""
    import datetime
    from app.features.consulta_v2.maquina_q import _continuacion
    from app.features.consulta_v2.cuantificar import slots as _sd
    ctx = {"grupo": "cuantificar", "entidad": "CASTILLA", "producto": "crudo"}
    rw = _continuacion("y el 15 de mayo?", ctx)
    assert rw is not None and "CASTILLA" in rw
    sl = _sd.extraer_slots(rw, entidad_valor="CASTILLA", techo=datetime.date(2026, 5, 17))
    assert sl.get("nivel_temporal") == "N1D"
    assert sl["dia"]["fecha"] == "2026-05-15"


# ---------------- QV2-GLOBAL (2026-08-26): cuantificar sin entidad = toda ECP ----------------
# «cómo ha sido la producción de crudo este mes» declinaba con «no identifiqué una entidad»: el
# catálogo de cuantificar es cerrado (campo/activo/gerencia/operador) y no tenía forma de decir
# «todo». El dato sí existe — desempeno(entidad=None) devuelve el global.

def test_global_sin_entidad_responde_toda_ecp():
    from app.features.consulta_v2.cuantificar.ejecutor import _cualificar
    glob = {"valor": None, "nivel": None, "rama": "A", "zoom": [], "global": True}
    assert _cualificar(glob) == "toda la producción de Ecopetrol"


def test_global_no_pisa_el_rotulo_de_una_entidad_real():
    from app.features.consulta_v2.cuantificar.ejecutor import _cualificar
    assert _cualificar({"valor": "CASTILLA", "nivel": "campo"}) == "el Campo CASTILLA"


@pytest.mark.parametrize("frase", [
    "cuanto se produjo el 15 de mayo",
    "cual fue el mejor dia",
    "dia a dia de crudo",
])
def test_global_no_aplica_a_grano_dia(frase):
    """El grano día sigue exigiendo entidad. Medido: produccion_dia(None) da hay_dato=False y
    curva_dia_mes(None) devuelve 0 puntos — el global no está soportado ahí, y pedir el campo es
    más honesto que responder «no tengo curva» por un motivo que no es el real."""
    from app.features.consulta_v2.respuesta_cuantificar import responder
    r = responder(frase)
    assert "no identifiqué una entidad" in r["mensaje"].lower()


def test_global_no_tapa_una_entidad_mal_escrita():
    """Un «Castiya» no puede convertirse en «toda Ecopetrol» sin avisar: si el usuario NOMBRÓ
    algo, se declina con el eco de lo que no se reconoció."""
    from app.features.consulta_v2.respuesta_cuantificar import responder
    r = responder("cuanto crudo produjo Castiya", entidad="CASTIYA")
    assert "castiya" in r["mensaje"].lower()
    assert "toda la producción" not in r["mensaje"]
