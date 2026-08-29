from app.features.consulta.maquina import _resolver_colision, _rep, _prioridad_campo, _prioridad_filial


def _id(nivel, valor, rama="A"):
    return {"nivel": nivel, "rama": rama, "valor": valor}


def test_redundante_colapsa_a_campo():
    ids = [_id("fuente", "RUBIALES"), _id("campo", "RUBIALES"), _id("activo", "RUBIALES")]
    clave = lambda i: ("F", frozenset({1}))            # todos el mismo fuente_id
    modo, rep, reps = _resolver_colision(ids, clave)
    assert modo == "auto" and rep["nivel"] == "campo" and len(reps) == 1


def test_genuino_anidado_pregunta():
    ids = [_id("campo", "CHICHIMENE"), _id("activo", "CHICHIMENE"), _id("fuente", "CHICHIMENE")]
    sets = {"campo": frozenset({1, 2}), "activo": frozenset({1, 2, 3, 4}), "fuente": frozenset({7})}
    clave = lambda i: ("F", sets[i["nivel"]])
    modo, rep, reps = _resolver_colision(ids, clave)
    assert modo == "ask" and rep is None and len(reps) == 3


def test_niveles_con_mismo_set_se_fusionan_reduce_botones():
    # Caso real (CASTILLA): fuente y campo comparten el mismo conjunto físico -> 1 grupo;
    # el activo agrega más campos -> grupo aparte. Quedan 2 opciones, no 3.
    ids = [_id("fuente", "CASTILLA"), _id("campo", "CASTILLA"), _id("activo", "CASTILLA")]
    sets = {"fuente": frozenset({1, 2}), "campo": frozenset({1, 2}), "activo": frozenset({1, 2, 3, 4})}
    clave = lambda i: ("F", sets[i["nivel"]])
    modo, rep, reps = _resolver_colision(ids, clave)
    assert modo == "ask" and len(reps) == 2


def test_dual_ab_pregunta():
    ids = [_id("operador", "HOCOL", "A"), _id("filial", "HOCOL", "B")]
    clave = lambda i: ("F", frozenset({9})) if i["rama"] == "A" else ("B", "hocol")
    modo, rep, reps = _resolver_colision(ids, clave)
    assert modo == "ask" and rep is None and len(reps) == 2


def test_rep_prioriza_campo():
    # 2026-07-16: 'area' (grupo1) dejó de ser un nivel — no es el Activo ni existe en el negocio.
    assert _rep([_id("fuente", "X"), _id("campo", "X"), _id("activo", "X")])["nivel"] == "campo"
    assert _rep([_id("activo", "Y"), _id("fuente", "Y")])["nivel"] == "activo"  # sin campo -> activo


# --- D-D5: prioridad Campo en colisiones genuinas (decisión del usuario, 2026-07-15) ---

def test_prioridad_campo_auto_sin_activo():
    # Caño Limón-like: pozo+campo físicamente distintos y SIN activo (operado por un tercero, no está
    # en core.map_campo_activo) -> responde Campo, sin zoom.
    reps = [_id("fuente", "CANO LIMON"), _id("campo", "CANO LIMON")]
    rep, zoom = _prioridad_campo(reps)
    assert rep is not None and rep["nivel"] == "campo" and zoom == []


def test_prioridad_campo_con_zoom_activo():
    # campo + activo con conjuntos distintos -> responde Campo y OFRECE "Ver como Activo"
    reps = [_id("campo", "X"), _id("activo", "X")]
    rep, zoom = _prioridad_campo(reps)
    assert rep["nivel"] == "campo" and len(zoom) == 1 and zoom[0]["nivel"] == "activo"


def test_prioridad_campo_no_aplica_dual_b():
    # dual A/B (ej. un nombre que también es filial) -> universos distintos -> sigue preguntando
    assert _prioridad_campo([_id("campo", "X", "A"), _id("filial", "X", "B")]) == (None, [])


def test_prioridad_campo_no_aplica_dos_campos():
    # 2 campos FÍSICAMENTE distintos con el mismo nombre -> no hay un único campo -> sigue preguntando
    assert _prioridad_campo([_id("campo", "X"), _id("campo", "X")]) == (None, [])


def test_prioridad_campo_sin_campo_pregunta():
    # colisión sin lectura de campo (pozo/activo) -> la regla no aplica -> sigue preguntando
    assert _prioridad_campo([_id("fuente", "Y"), _id("activo", "Y")]) == (None, [])


# --- D-D6: prioridad Filial — Hocol (dual A/B) se resuelve como filial, con zoom al ECP (2026-07-21) ---

def test_prioridad_filial_hocol_resuelve_a_filial():
    # Hocol dual: operador ECP (A) + filial (B) -> responde FILIAL directo. Solo filial, SIN zoom al
    # operador (decisión del usuario 2026-07-21: las 3 filiales se analizan solo como filial).
    reps = [_id("operador", "HOCOL", "A"), _id("filial", "HOCOL", "B")]
    rep, zoom = _prioridad_filial(reps)
    assert rep is not None and rep["nivel"] == "filial" and rep["rama"] == "B"
    assert zoom == []


def test_prioridad_filial_no_aplica_sin_filial():
    # colisión sin identidad rama B (p.ej. campo+activo) -> la regla no aplica (la maneja _prioridad_campo)
    assert _prioridad_filial([_id("campo", "X"), _id("activo", "X")]) == (None, [])


def test_prioridad_filial_no_aplica_dos_filiales():
    # 2 identidades rama B con el mismo nombre (no debería pasar) -> sigue preguntando
    assert _prioridad_filial([_id("filial", "X", "B"), _id("filial", "X", "B")]) == (None, [])


# --- Activo desde el catálogo + rollup honesto (2026-07-16) ---
# Contexto: NINGUNA columna de dim_fuente es el Activo. `activos` es un bucket de portafolio
# (OPERADOS/NO OPERADOS/MENORES) y `grupo1` una taxonomía previa. El Activo vive en
# core.map_campo_activo (migración 008, 52 activos sembrados desde data/Activo_campo.csv).

def test_area_ya_no_es_un_nivel():
    """Regresión: 'area' (grupo1) fue eliminada. Era la causa de que Chichimene y Castilla NO
    ofrecieran el zoom a Activo: al colapsar area+activo (mismo conjunto), area(4) le ganaba a
    activo(3) y el representante 'activo' desaparecía antes de llegar a _prioridad_campo."""
    from app.features.consulta.maquina import _PRIORIDAD, _NIVEL_COL, _NIVEL_INFO
    from app.features.consulta.resolver import _LEVELS, _FUENTE_COL
    assert "area" not in _PRIORIDAD and "area" not in _NIVEL_COL and "area" not in _NIVEL_INFO
    niveles = {n for n, _, _ in _LEVELS}
    assert "area" not in niveles
    assert "activos" not in _FUENTE_COL.values()   # el bucket de portafolio ya no resuelve nada


def test_activo_no_sale_de_dim_fuente():
    """El nivel 'activo' se alimenta de core.map_campo_activo, no de dim_fuente.activos."""
    from app.features.consulta.resolver import _LEVELS
    sql_activo = next(sql for n, sql, _ in _LEVELS if n == "activo")
    assert "map_campo_activo" in sql_activo and "dim_fuente" not in sql_activo


def test_campos_sin_meta_solo_aplica_a_activo():
    """D-A4: solo el activo agrega varios campos -> es el único nivel donde el REAL sumado puede
    quedar contra un PPTO que no cubre a todos. Para campo/gerencia devuelve [] sin tocar la BD."""
    from app.features.analisis.api import _campos_sin_meta
    for nivel in ("campo", "gerencia", "fuente", None):
        assert _campos_sin_meta(None, "APIAY", "2026-05-31", nivel) == []


def test_regla_numerica_atrapa_porcentaje_alterado():
    """D-N5 ampliada: un % mal copiado ya NO pasa silencioso (caso real en 139: volumen correcto
    de BLANCOS -4.544- narrado con 56.7% cuando el dato daba 59.6%)."""
    from app.features.consulta.narracion import _cumple_regla_numerica
    payload = {"productos": [{"producto": "BLANCOS", "volumen": "4.544",
                              "porcentaje_presupuesto": "59.6%"}]}
    ok, _ = _cumple_regla_numerica("BLANCOS reportó 4.544 barriles (59.6% del presupuesto)", payload)
    assert ok
    ok, motivo = _cumple_regla_numerica("BLANCOS reportó 4.544 barriles (56.7% del presupuesto)", payload)
    assert not ok and "porcentaje" in motivo


def test_regla_numerica_no_exige_literal_el_sin_meta():
    """'sin meta definida' es prosa, no cifra: el LLM puede reformularla sin caer al fallback."""
    from app.features.consulta.narracion import _cumple_regla_numerica
    payload = {"productos": [{"producto": "GAS", "volumen": "1.000",
                              "porcentaje_presupuesto": "sin meta definida"}]}
    ok, _ = _cumple_regla_numerica("GAS produjo 1.000 y no tiene meta asignada", payload)
    assert ok


def test_lorito_pertenece_a_akacias_y_no_a_cpo09():
    """D-A2 (veredicto del usuario, 2026-07-16): el CSV lista LORITO en AKACIAS y en CPO-09. Un campo
    en 2 activos se contaría doble al sumar, así que la migración 008 lo asigna SOLO a AKACIAS.
    Mientras estuvo omitido, sus 121.301 bl no sumaban en NINGÚN activo."""
    from app.features.consulta.resolver import campos_de_activo
    assert "LORITO" in campos_de_activo("AKACIAS")
    assert "LORITO" not in campos_de_activo("CPO-09")


def test_aullador_resuelto_a_lisama():
    """AULLADOR era el ambiguo que quedó SIN activo en la 008 (LISAMA vs LISAMA UNIFICADO).
    La migración 009 lo resuelve a LISAMA: la BD de DIFERIDAS lo asigna así de forma consistente
    (columna AREA), que es justo el dato que a dim_fuente le faltaba. Sigue en UN solo activo."""
    from app.features.consulta.resolver import campos_de_activo
    assert "AULLADOR" in campos_de_activo("LISAMA")
    assert "AULLADOR" not in campos_de_activo("LISAMA UNIFICADO")   # nunca en dos activos


def test_area_es_sinonimo_de_activo_en_la_extraccion():
    """'area' dejó de ser un NIVEL (grupo1 no era el Activo), pero sigue siendo la PALABRA que usa el
    negocio para decir activo. "el área Chichimene" debe groundear nivel='activo'; sin la palabra,
    ningún nivel se acepta (el grounding no deja que el LLM lo rellene por prior)."""
    from app.features.consulta.extraccion import _grounded, _NIVEL_KW
    from app.features.consulta.normaliza import norm
    assert "area" not in _NIVEL_KW                       # ya no es un nivel propio
    assert _grounded(norm("cómo está el área Chichimene"), "activo", _NIVEL_KW) == "activo"
    assert _grounded(norm("producción del activo Apiay"), "activo", _NIVEL_KW) == "activo"
    assert _grounded(norm("producción de Chichimene"), "activo", _NIVEL_KW) is None
