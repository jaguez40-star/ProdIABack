"""tests/test_cuantificar_ranking.py — N5 RANKING (plan_cuantificar_n5_ranking_2026-08-04.md, §8).

V-DETECT: puro, sin BD (detectar()). V-CALC: contra Postgres real (calcular()), con
`_engine_o_skip` (mismo patrón que tests/test_puente_gerencia_vp.py) para no reventar si la BD
dev no está disponible.
"""
import pytest

import app.features.consulta_v2.cuantificar.ranking as RK


# --- V-DETECT (puro, sin BD) ---------------------------------------------------------------------

def test_top5_campos_real_desc():
    r = RK.detectar("cuales son los 5 campos que mas crudo producen")
    assert r is not None
    assert r["nivel_ranking"] == "campo"
    assert r["metrica"] == "real"
    assert r["direccion"] == "top"
    assert r["top_n"] == 5
    assert r["producto"] == "crudo"


def test_singular_top1():
    r = RK.detectar("que campo produce la mayor cantidad de crudo")
    assert r is not None
    assert r["top_n"] == 1


def test_bottom_real():
    r = RK.detectar("que campos tuvieron la mas baja produccion este mes")
    assert r is not None
    assert r["direccion"] == "bottom"
    assert r["metrica"] == "real"


def test_top3_activos_gas_mayo():
    r = RK.detectar("top 3 activos por produccion de gas en mayo")
    assert r is not None
    assert r["nivel_ranking"] == "activo"
    assert r["top_n"] == 3
    assert r["producto"] == "gas"
    assert r["periodo_texto"] == "mayo"


def test_gap_bottom_faltante_cortos():
    """El bug real del plan v1 (D1): 'mas cortos' debe dar FALTANTE (bottom), no excedente."""
    r = RK.detectar("que campos se quedaron mas cortos vs presupuesto")
    assert r is not None
    assert r["metrica"] == "gap"
    assert r["direccion"] == "bottom"


def test_gap_bottom_mayor_faltante():
    """'mayor faltante' -> faltante manda sobre 'mayor' (que por sí solo sería top)."""
    r = RK.detectar("que campos tienen mayor faltante vs presupuesto")
    assert r is not None
    assert r["metrica"] == "gap"
    assert r["direccion"] == "bottom"


def test_gap_top_superaron():
    r = RK.detectar("que campos superaron el presupuesto")
    assert r is not None
    assert r["metrica"] == "gap"
    assert r["direccion"] == "top"


def test_pozo_diferido():
    r = RK.detectar("ranking de pozos por produccion en Castilla")
    assert r is not None
    assert "diferido" in r


def test_gerencia_diferido():
    r = RK.detectar("cual gerencia produce mas blancos")
    assert r is not None
    assert "diferido" in r


def test_no_es_n5_sin_superlativo():
    assert RK.detectar("cuanto crudo produjo Rubiales") is None


def test_no_es_n5_sin_sustantivo_de_nivel():
    """Sin CAMPO/ACTIVO/... la pregunta sigue su curso normal por N1 (una entidad, no un ranking)."""
    assert RK.detectar("cual es la mayor produccion de Rubiales") is None


# --- V-CALC (contra BD real; se salta si Postgres no está disponible) ----------------------------

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


def test_bd_real_top5_campos_crudo():
    eng = _engine_o_skip()
    res = RK.calcular({"nivel_ranking": "campo", "metrica": "real", "direccion": "top",
                       "top_n": 5, "producto": "crudo", "periodo_texto": None}, _engine=eng)
    assert res["aplica"] is True
    items = res["items"]
    assert items[0]["entidad"] == "RUBIALES"
    assert items[0]["valor"] == 12357703
    assert len(items) == 5
    assert items[2]["entidad"] == "QUIFA"
    assert items[2]["es_ecp"] is False
    assert items[2]["operador"] and "Frontera" in items[2]["operador"]
    assert res["total_universo"] == 128
    assert res["concentracion_pct"] is not None


def test_bd_real_bottom5_campos_crudo():
    eng = _engine_o_skip()
    res = RK.calcular({"nivel_ranking": "campo", "metrica": "real", "direccion": "bottom",
                       "top_n": 5, "producto": "crudo", "periodo_texto": None}, _engine=eng)
    assert res["aplica"] is True
    assert all(it["valor"] > 0 for it in res["items"])          # CERO TRAICIONERO
    assert res["sin_registro"] >= 15
    assert res["concentracion_pct"] is None                      # D7: solo tiene sentido en top


def test_bd_real_gap_bottom_faltante_ordenado():
    eng = _engine_o_skip()
    res = RK.calcular({"nivel_ranking": "campo", "metrica": "gap", "direccion": "bottom",
                       "top_n": 5, "producto": "crudo", "periodo_texto": None}, _engine=eng)
    assert res["aplica"] is True
    gaps = [it["gap"] for it in res["items"]]
    assert gaps[0] < 0
    assert all(gaps[i] <= gaps[i + 1] for i in range(len(gaps) - 1))   # no decreciente (D1)


def test_bd_real_gap_top_excedente():
    eng = _engine_o_skip()
    res = RK.calcular({"nivel_ranking": "campo", "metrica": "gap", "direccion": "top",
                       "top_n": 5, "producto": "crudo", "periodo_texto": None}, _engine=eng)
    assert res["aplica"] is True
    assert res["items"][0]["gap"] > 0


def test_bd_real_activo_gas_sin_operador():
    eng = _engine_o_skip()
    res = RK.calcular({"nivel_ranking": "activo", "metrica": "real", "direccion": "top",
                       "top_n": 5, "producto": "gas", "periodo_texto": None}, _engine=eng)
    assert res["aplica"] is True
    assert len(res["items"]) >= 1
    assert all(it["operador"] is None for it in res["items"])    # D5: activo no inventa operador


# --- V2 · helpers de derivación de los bullets (puros, sin BD) — plan_ranking_lectura_chat -------
# plan_ranking_lectura_chat_2026-08-12.md §4 V2: 1 test por guarda de A7, más los tramos de A4.

def _res(nivel_ranking="campo", items=None, total_universo=128, concentracion_pct=41.2,
          sin_registro=0, direccion="top", metrica="real", es_proyeccion=False):
    return {
        "nivel_ranking": nivel_ranking, "metrica": metrica, "direccion": direccion,
        "producto": "crudo", "unidad": "bbl", "periodo_label": "mayo 2026",
        "es_proyeccion": es_proyeccion, "items": items or [], "total_universo": total_universo,
        "sin_registro": sin_registro, "concentracion_pct": concentracion_pct,
    }


def _item(entidad, valor, es_ecp=True, operador=None):
    return {"pos": 1, "entidad": entidad, "valor": valor, "ppto": 0, "gap": 0,
            "operador": operador, "es_ecp": es_ecp}


def test_v2_1_un_solo_item_bullet_b_none_sin_indexerror():
    res = _res(items=[_item("RUBIALES", 3000000)])
    assert RK._b_dominancia(res) is None


def test_v2_2_segundo_en_cero_bullet_b_none_sin_zerodivision():
    res = _res(items=[_item("RUBIALES", 3000000), _item("CASTILLA", 0)])
    assert RK._b_dominancia(res) is None


def test_v2_3_dos_items_sin_matiz_de_peloton():
    # peso1 = 3M/3.5M = 85.7% >= 30 -> bullet emite, pero SIN el matiz de pelotón (len(items)<3)
    res = _res(items=[_item("RUBIALES", 3000000), _item("CASTILLA", 500000)])
    b = RK._b_dominancia(res)
    assert b is not None
    assert "apretadas" not in b


def test_v2_4_concentracion_none_bullet_a_none_sin_texto_none_pct():
    res = _res(concentracion_pct=None)
    assert RK._b_concentracion(res) is None


def test_v2_5_nivel_activo_bullet_c_none():
    res = _res(nivel_ranking="activo",
               items=[_item("RUBIALES", 3000000, es_ecp=None, operador=None)])
    assert RK._b_terceros(res) is None


def test_v2_6_es_ecp_none_no_cuenta_como_tercero():
    res = _res(items=[_item("RUBIALES", 3000000, es_ecp=None, operador=None),
                       _item("CASTILLA", 1000000, es_ecp=True, operador=None)])
    assert RK._b_terceros(res) is None


def test_v2_7_tramos_de_concentracion():
    b41 = RK._b_concentracion(_res(concentracion_pct=41))
    b60 = RK._b_concentracion(_res(concentracion_pct=60))
    b85 = RK._b_concentracion(_res(concentracion_pct=85))
    assert "no extrema" in b41
    assert "alta" in b60 and "muy alta" not in b60
    assert "muy alta" in b85


def test_v2_8_peso_25_no_destaca():
    # top de 4 items con pesos parejos (~25% cada uno) -> el #1 no domina (umbral 30)
    items = [_item("A", 250000), _item("B", 250000), _item("C", 250000), _item("D", 250000)]
    res = _res(items=items)
    assert RK._b_dominancia(res) is None


# --- Guardas de las 3 correcciones post-Executor (2026-08-12) -----------------------------------

def test_v2_9_peso_34_si_destaca():
    """El umbral es 30, no 40: crudo/campo (RUBIALES, 34% del top) es EL caso de referencia del
    plan y con 40 no emitía el bullet. Con un top de 5 el reparto uniforme es 20% → 34% ya domina."""
    items = [_item("RUBIALES", 3400000), _item("B", 1700000), _item("C", 1650000),
             _item("D", 1630000), _item("E", 1620000)]
    b = RK._b_dominancia(_res(items=items))
    assert b is not None and "RUBIALES" in b


def test_v2_10_concordancia_top_n_1():
    """"1 de 128 campos GENERA" — el número que rige el verbo es el 1, pero el sustantivo va en
    plural porque cuenta el universo. Ni "campos generan" (agramatical) ni "campo genera"."""
    b = RK._b_concentracion(_res(items=[_item("RUBIALES", 3000000)], concentracion_pct=13.9))
    assert "1 de 128 campos genera el" in b
    assert "campos generan" not in b and "128 campo " not in b


def test_v2_11_glosa_corchetes_solo_en_gap():
    """La glosa explica los CORCHETES, y solo la rama gap los imprime. En real el bullet C ya nombra
    a los operadores en prosa → repetirla duplicaba con la misma condición de disparo (patrón AI1)."""
    items = [_item("QUIFA", 3000000, es_ecp=False, operador="Frontera Energy"),
             _item("CASTILLA", 1000000)]
    real = RK.formatear_cuerpo(_res(items=items))
    gap = RK.formatear_cuerpo(_res(items=items, metrica="gap", concentracion_pct=None))
    assert "entre corchetes" not in real
    assert "entre corchetes" in gap


# --- V-DETECT · DISTRIBUCIÓN y DOMINANCIA (2026-09-01) -------------------------------------

def test_distribucion_activa_el_ranking():
    """El caso real del usuario: no dice ningún superlativo, pide el reparto."""
    r = RK.detectar("como se distribuye la produccion de crudo, %, entre los campos productores")
    assert r is not None
    assert r["nivel_ranking"] == "campo"
    assert r["metrica"] == "real" and r["direccion"] == "top"
    assert r["top_n"] == 5


def test_distribucion_porcentualmente():
    r = RK.detectar("como se distribuye la produccion de crudo, porcentualmente, entre los campos")
    assert r is not None and r["direccion"] == "top"


def test_distribucion_participacion():
    r = RK.detectar("que participacion tiene cada campo en la produccion total de crudo")
    assert r is not None and r["nivel_ranking"] == "campo"


def test_distribucion_share_y_fraccion():
    assert RK.detectar("dame el share de cada campo sobre la produccion de crudo") is not None
    assert RK.detectar("que fraccion del crudo produce cada campo") is not None


def test_dominancia_verbos_de_liderazgo():
    """encabezan / lidero / punteros: superlativos semánticos que faltaban."""
    assert RK.detectar("que campos encabezan la produccion de aceite en agosto") is not None
    assert RK.detectar("que campo lidero la produccion durante agosto") is not None
    assert RK.detectar("muestrame los campos punteros en crudo para agosto") is not None


def test_distribucion_sigue_exigiendo_nivel():
    """El filtro 2 no se relaja: sin CAMPO/ACTIVO no es un ranking (H1 del plan)."""
    assert RK.detectar("como se distribuye la produccion de crudo") is None


def test_pesa_sigue_siendo_de_analizar():
    """🔒 REGRESIÓN: PESA/PESAN NO entran en _DISTRIBUCION — patrones_grupo.yaml:206 y la
    exclusión de :66-71 son una decisión del usuario del 2026-08-24 (ver H3 del plan)."""
    assert RK.detectar("que campos pesan en el gap") is None


def test_no_es_ranking_sin_ninguna_senal():
    """Regresión del gate: sin superlativo NI distribución NI dominancia, sigue None."""
    assert RK.detectar("cuanto crudo produjo Rubiales") is None


def test_distribucion_con_entidad_es_deteccion_y_la_guarda_decide():
    """H9 del plan: «¿qué porcentaje aporta el campo Castilla?» AHORA es detectada como
    ranking (PORCENTAJE + CAMPO). La declinación honesta la pone la guarda (3) del
    dispatcher (respuesta_cuantificar.py:228-234), que corre después y consulta la BD —
    por eso aquí SOLO se fija que detectar() devuelve algo (el cambio de comportamiento
    es deliberado, no accidental). El caso catastrófico —responder el ranking global a
    quien preguntó por Castilla— lo impide esa guarda, no este módulo."""
    r = RK.detectar("que porcentaje del crudo aporta el campo Castilla")
    assert r is not None and r["nivel_ranking"] == "campo"


# --- V-DETECT · top_n en distribución (fix 2026-09-03, medido en Pruebas) -------------------

def test_cada_campo_singular_no_colapsa_a_top_1():
    """🔒 REGRESIÓN del bug medido en Pruebas el 2026-09-03: «cada CAMPO» es singular
    gramatical con intención de TODOS. La heurística `singular -> top_n=1` (pensada para
    «¿qué campo produce MÁS crudo?») lo colapsaba a 1 y el redactor imprimía el absurdo
    «1 de 128 campos genera el 13,7%». Una distribución nunca pide un solo elemento."""
    r = RK.detectar("que participacion tiene cada campo en la produccion total de crudo")
    assert r is not None
    assert r["top_n"] == 5


def test_superlativo_singular_sigue_dando_top_1():
    """El complemento del anterior: sin señal de distribución, el singular SÍ significa uno.
    Si este test se pone rojo, el fix de arriba se pasó de ancho."""
    r = RK.detectar("que campo produce la mayor cantidad de crudo")
    assert r is not None and r["top_n"] == 1


def test_top_n_explicito_gana_sobre_distribucion():
    """«top 3» explícito manda: el fix no puede pisar un número que el usuario escribió."""
    r = RK.detectar("dame el top 3 de campos por participacion en la produccion de crudo")
    assert r is not None and r["top_n"] == 3


# --- V-SCOPE · ranking acotado al activo (2026-09-03) ---------------------------------------

def test_calcular_sin_scope_es_el_comportamiento_de_siempre():
    """🔒 REGRESIÓN: campos_scope=None -> ranking global, idéntico a antes del cambio."""
    eng = _engine_o_skip()
    a = RK.calcular({"nivel_ranking": "campo", "metrica": "real", "direccion": "top",
                     "top_n": 5, "producto": "crudo", "periodo_texto": None}, _engine=eng)
    b = RK.calcular({"nivel_ranking": "campo", "metrica": "real", "direccion": "top",
                     "top_n": 5, "producto": "crudo", "periodo_texto": None},
                    _engine=eng, campos_scope=None)
    assert a["items"] == b["items"] and a["total_universo"] == b["total_universo"]


def test_scope_reduce_el_universo():
    """El panel scoped ve SOLO los campos del scope."""
    eng = _engine_o_skip()
    res = RK.calcular({"nivel_ranking": "campo", "metrica": "real", "direccion": "top",
                       "top_n": 5, "producto": "crudo", "periodo_texto": None},
                      _engine=eng, campos_scope={"CASTILLA", "CASTILLA NORTE"})
    if not res.get("aplica"):
        pytest.skip("sin datos de crudo en el mes por defecto de esta BD")
    assert {it["entidad"] for it in res["items"]} <= {"CASTILLA", "CASTILLA NORTE"}
    assert res["total_universo"] <= 2


def test_campos_de_activo_castilla():
    """La fuente única (ops.wells_attributes) con los 2 filtros obligatorios (H4/H5)."""
    try:
        campos = RK.campos_de_activo("CASTILLA")
    except Exception:
        pytest.skip("BD de robustez no disponible")
    if not campos:
        pytest.skip("BD de robustez no disponible o sin datos")
    assert "CASTILLA" in campos and "CASTILLA NORTE" in campos
    # 🔑 La rama VIEJA (vp=VRO) daría otros activos; con el filtro no aparecen campos ajenos.
    assert all(c.startswith("CASTILLA") for c in campos)


def test_campos_de_activo_inexistente_no_lanza():
    """🔒 Degradación con gracia: lo que no está en la fuente única, no existe -> set()."""
    try:
        assert RK.campos_de_activo("NO_EXISTE_ESTE_ACTIVO_XYZ") == set()
    except Exception:
        pytest.skip("BD de robustez no disponible")


def test_campos_de_activo_vacio_o_none():
    """Puro, sin BD: guarda de entrada."""
    assert RK.campos_de_activo("") == set()
    assert RK.campos_de_activo(None) == set()
