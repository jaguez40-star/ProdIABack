"""Tests de CUANTIFICAR (Motor Q v2 · Fase 1 · N1 puntual + N2 acumulado).

Resolver D-D5 vía sus funciones puras (_rep/_resolver_colision/_prioridad_campo — sin BD) + slots
N1/N2 (sin BD, sin LLM) + ejecutor con `_desempeno_fn` FAKE (sin BD real, sin LLM) + memoria de
`_continuacion` para el drill N1->N2 (HE5, sin BD para las frases cortas de este archivo).

⚠️ Este archivo importa `ejecutor.py` (-> analisis.api -> sqlalchemy) y `maquina_q.py` (-> get_engine)
al cargar el módulo, aunque ninguna prueba individual toque Postgres de verdad (los datos de
`desempeno` vienen inyectados vía `_desempeno_fn`). Por la regla de RAM del proyecto: se corre en el
SERVIDOR DE PRUEBAS, no en la máquina de desarrollo.
"""
from app.features.consulta_v2.cuantificar import ejecutor as _ejecutor
from app.features.consulta_v2.cuantificar import niveles as _niveles
from app.features.consulta_v2.cuantificar import resolver as _resolver
from app.features.consulta_v2.cuantificar import slots as _slots
from app.features.consulta_v2.cuantificar import validador as _validador
from app.features.consulta_v2.maquina_q import _continuacion, _periodo_ctx_de


# ---------------- Resolver D-D5 (funciones puras, sin BD) ----------------

def test_prioridad_campo_campo_mas_activo_da_zoom():
    # colisión ya separada en grupos físicos distintos (campo vs activo, caso APIAY real)
    reps = [
        {"nivel": "campo", "rama": "A", "valor": "APIAY"},
        {"nivel": "activo", "rama": "A", "valor": "APIAY"},
    ]
    rep_campo, zoom = _resolver._prioridad_campo(reps)
    assert rep_campo is not None and rep_campo["nivel"] == "campo"
    assert len(zoom) == 1 and zoom[0]["nivel"] == "activo"


def test_prioridad_campo_con_filial_no_decide():
    # D-D5 no decide si hay una rama B (filial) en la colisión -> queda ambiguo (caso Hocol real)
    reps = [
        {"nivel": "operador", "rama": "A", "valor": "HOCOL"},
        {"nivel": "filial", "rama": "B", "valor": "HOCOL"},
    ]
    rep_campo, zoom = _resolver._prioridad_campo(reps)
    assert rep_campo is None and zoom == []


def test_prioridad_campo_dos_campos_distintos_no_decide():
    reps = [
        {"nivel": "campo", "rama": "A", "valor": "CAMPO1"},
        {"nivel": "campo", "rama": "A", "valor": "CAMPO2"},
    ]
    rep_campo, _ = _resolver._prioridad_campo(reps)
    assert rep_campo is None


def test_rep_prioriza_campo_sobre_activo_y_gerencia():
    grupo = [
        {"nivel": "gerencia", "rama": "A", "valor": "X"},
        {"nivel": "activo", "rama": "A", "valor": "X"},
        {"nivel": "campo", "rama": "A", "valor": "X"},
    ]
    assert _resolver._rep(grupo)["nivel"] == "campo"


def test_resolver_colision_auto_si_un_solo_grupo_fisico():
    ids = [{"nivel": "fuente", "rama": "A", "valor": "X"},
           {"nivel": "campo", "rama": "A", "valor": "X"}]
    modo, rep, _ = _resolver._resolver_colision(ids, lambda i: ("MISMO",))
    assert modo == "auto" and rep["nivel"] == "campo"


def test_resolver_colision_ask_si_dos_grupos_fisicos():
    ids = [{"nivel": "campo", "rama": "A", "valor": "X"},
           {"nivel": "campo", "rama": "A", "valor": "Y"}]
    modo, _, reps = _resolver._resolver_colision(ids, lambda i: (i["valor"],))
    assert modo == "ask" and len(reps) == 2


# ---------------- slots: N1/N2 (sin BD, sin LLM) ----------------

def test_slots_n1_por_defecto():
    assert _slots.extraer_slots("cuanto crudo produjo Rubiales")["nivel_temporal"] == "N1"


def test_slots_n2_acumulado():
    assert _slots.extraer_slots("acumulado de Rubiales")["nivel_temporal"] == "N2"


def test_slots_n2_en_el_ano_con_tilde():
    # HE7: norm pliega tildes -> "en el año" y "en el ano" deben matchear igual
    assert _slots.extraer_slots("cuanto ha producido Rubiales en el año")["nivel_temporal"] == "N2"


def test_slots_n2_ytd():
    assert _slots.extraer_slots("dame el YTD de Rubiales")["nivel_temporal"] == "N2"


# ---------------- ejecutor con _desempeno_fn FAKE (sin BD real, sin LLM) ----------------

def _fake_mes_cerrado(entidad="X", segmento="ecp", nivel="campo", periodo=None):
    return {"encontrada": True, "sin_datos": False, "sin_cierre": False,
            "mes": {"anio": 2026, "mes": 4, "nombre": "Abril", "completo": True,
                    "dias_con_data": 30, "dias_del_mes": 30},
            "por_producto": [{"producto": "CRUDO", "real": 1000.0, "ppto": 1250.0, "cumplimiento": 80.0}],
            "campos_sin_meta": []}


def _fake_mes_en_curso(entidad="X", segmento="ecp", nivel="campo", periodo=None):
    return {"encontrada": True, "sin_datos": False, "sin_cierre": False,
            "mes": {"anio": 2026, "mes": 5, "nombre": "Mayo", "completo": False,
                    "dias_con_data": 17, "dias_del_mes": 31},
            "por_producto": [{"producto": "CRUDO", "real": 500.0, "ppto": 620.0, "cumplimiento": 80.6}],
            "campos_sin_meta": []}


def _fake_parametrizado(entidad="X", segmento="ecp", nivel="campo", periodo=None):
    # periodo=None o "mayo" -> mes en curso (proyección). "enero".."abril" -> cerrados.
    # Simula un año con 4 meses cerrados + mayo en curso, para probar HE4 (N2 no suma el en curso).
    cerrados = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4}
    if periodo is None or periodo == "mayo":
        return _fake_mes_en_curso(entidad, segmento, nivel, periodo)
    if periodo in cerrados:
        d = _fake_mes_cerrado(entidad, segmento, nivel, periodo)
        d["mes"]["mes"] = cerrados[periodo]
        return d
    return {"encontrada": False}


def test_ejecutar_n1_mes_cerrado():
    resuelta = {"nivel": "campo", "rama": "A", "valor": "RUBIALES", "zoom": []}
    slots = _slots.extraer_slots("cuanto crudo produjo Rubiales en abril")
    res = _ejecutor.ejecutar_n1(resuelta, slots, _desempeno_fn=_fake_mes_cerrado)
    assert res["aplica"] is True
    assert res["nivel"] == "N1"
    assert res["resultado"]["valor"] == 1000.0
    assert res["mes"]["completo"] is True


def test_ejecutar_n1_mes_en_curso_es_proyeccion():
    resuelta = {"nivel": "campo", "rama": "A", "valor": "RUBIALES", "zoom": []}
    slots = _slots.extraer_slots("cuanto crudo produjo Rubiales")
    res = _ejecutor.ejecutar_n1(resuelta, slots, _desempeno_fn=_fake_mes_en_curso)
    assert res["aplica"] is True
    assert res["mes"]["completo"] is False


def test_ejecutar_n1_filial_rechaza():
    resuelta = {"nivel": "filial", "rama": "B", "valor": "HOCOL", "zoom": []}
    slots = _slots.extraer_slots("cuanto produjo Hocol")
    res = _ejecutor.ejecutar_n1(resuelta, slots, _desempeno_fn=_fake_mes_cerrado)
    assert res["aplica"] is False
    assert "filial" in res["texto"]


def test_ejecutar_dispatch_n2_suma_meses_cerrados():
    resuelta = {"nivel": "campo", "rama": "A", "valor": "RUBIALES", "zoom": []}
    slots = _slots.extraer_slots("acumulado de Rubiales")
    assert slots["nivel_temporal"] == "N2"
    res = _ejecutor.ejecutar(resuelta, slots, _desempeno_fn=_fake_mes_cerrado)
    assert res["aplica"] is True
    assert res["nivel"] == "N2"
    assert res["meses_cerrados"] == 4          # d0 (periodo=None) dice mes=4 -> suma ene..abr
    assert res["resultado"]["valor"] == 4000.0  # 4 x 1000 (el fake siempre devuelve real=1000)
    assert res["referencia_valor"] == 5000.0    # 4 x 1250


def test_ejecutar_n2_mes_en_curso_no_se_suma():
    # HE4: el mes en curso (mayo) es proyección -> se DECLARA en avisos, no se suma al acumulado.
    resuelta = {"nivel": "campo", "rama": "A", "valor": "RUBIALES", "zoom": []}
    slots = _slots.extraer_slots("acumulado de Rubiales")
    res = _ejecutor.ejecutar(resuelta, slots, _desempeno_fn=_fake_parametrizado)
    assert res["aplica"] is True
    assert res["meses_cerrados"] == 4
    assert res["resultado"]["valor"] == 4000.0
    assert res["en_curso"]["nombre"] == "mayo"
    assert res["en_curso"]["real"] == 500.0
    assert any("mayo" in a and "curso" in a for a in res["avisos"])


def test_ejecutar_n2_gas_sin_datos_en_fuente_no_aplica():
    # Fase 2: gas YA NO se rechaza por producto; si el fake no trae fila GAS, N2 no acumula -> no aplica.
    resuelta = {"nivel": "campo", "rama": "A", "valor": "RUBIALES", "zoom": []}
    slots = _slots.extraer_slots("acumulado de gas de Rubiales")
    assert slots["producto"] == "gas"
    res = _ejecutor.ejecutar(resuelta, slots, _desempeno_fn=_fake_mes_cerrado)  # el fake solo trae CRUDO
    assert res["aplica"] is False


# ---------------- maquina_q: memoria de cuantificar, drill N1 -> N2 (HE5) ----------------

def test_continuacion_cuantificar_pide_acumulado_tras_n1():
    ctx = {"grupo": "cuantificar", "entidad": "RUBIALES"}
    assert _continuacion("acumulado del año", ctx) == "acumulado de RUBIALES"


def test_continuacion_cuantificar_si_afirmativo_va_a_acumulado():
    ctx = {"grupo": "cuantificar", "entidad": "RUBIALES"}
    assert _continuacion("si", ctx) == "acumulado de RUBIALES"


def test_continuacion_cuantificar_no_lleva_ofrece_produccion():
    # HE5: el ctx de cuantificar NO tiene "ofrece_produccion" -> un "sí" tras N1 SIEMPRE cae en la
    # rama de acumulado (nueva, arriba), nunca en la rama vieja de jerarquizar.
    ctx = {"grupo": "cuantificar", "entidad": "RUBIALES"}
    assert "ofrece_produccion" not in ctx
    assert _continuacion("si", ctx) == "acumulado de RUBIALES"


# ================= Fase 2: producto (gas/blancos) =================

def test_slots_producto_gas():
    assert _slots.extraer_slots("cuanto gas produjo Cusiana")["producto"] == "gas"


def test_slots_producto_blancos():
    assert _slots.extraer_slots("cuantos blancos produjo Cupiagua")["producto"] == "blancos"


def test_slots_producto_crudo_default():
    assert _slots.extraer_slots("cuanto produjo Rubiales")["producto"] == "crudo"


def test_slots_unidad_gas_mscf():
    s = _slots.extraer_slots("cuanto gas produjo Cusiana")
    assert s["unidad"] == "MSCF" and s["variable"] == "produccion_gas"


def test_slots_unidad_crudo_bbl():
    assert _slots.extraer_slots("cuanto produjo Rubiales")["unidad"] == "bbl"


def test_slots_blancos_descargo_media():
    # confianza media en el catálogo -> hay descargo de honestidad
    assert _slots.extraer_slots("cuantos blancos produjo Cupiagua")["descargo"]


def test_slots_crudo_sin_descargo():
    assert _slots.extraer_slots("cuanto produjo Rubiales")["descargo"] is None


# ---- validador: formato por producto ----

def test_fmt_valor_gas_mscf():
    # __cnGasM: 82_000_000/1e6 = 82.0 -> "82,0" (1 decimal si |m|>=1)
    assert _validador.fmt_valor(82_000_000.0, "gas") == "82,0"


def test_fmt_valor_gas_menor_a_uno():
    # 500_000/1e6 = 0.5 -> "0,50" (2 decimales si |m|<1)
    assert _validador.fmt_valor(500_000.0, "gas") == "0,50"


def test_fmt_valor_crudo_bbl():
    assert _validador.fmt_valor(10_966_768.0, "crudo") == "10.966.768"


def test_formatear_cuerpo_gas_dice_mscf():
    # `entidad_cualificada` es OBLIGATORIA en el contrato §7 (todo res de ejecutar_n1/n2 la trae);
    # el fixture debe reflejarlo o el test falla por KeyError, no por la lógica que quiere probar.
    res = {"nivel": "N1", "producto": "gas", "unidad": "MSCF",
           "entidad_cualificada": "el Campo CUSIANA",
           "resultado": {"valor": 82_000_000.0}, "referencia_valor": 80_000_000.0,
           "cumplimiento_pct": 102.5, "estado": "Alineado",
           "mes": {"nombre": "Abril", "anio": 2026, "completo": True,
                   "dias_con_data": 30, "dias_del_mes": 30}, "avisos": []}
    cuerpo = _validador.formatear_cuerpo(res)
    assert "MSCF" in cuerpo and "82,0" in cuerpo and "de gas" in cuerpo


# ---- ejecutor: gas/blancos con _desempeno_fn FAKE (sin BD, sin LLM) ----

def _fake_gas_cerrado(entidad="X", segmento="ecp", nivel="campo", periodo=None):
    return {"encontrada": True, "sin_datos": False, "sin_cierre": False,
            "mes": {"anio": 2026, "mes": 4, "nombre": "Abril", "completo": True,
                    "dias_con_data": 30, "dias_del_mes": 30},
            "por_producto": [{"producto": "GAS", "real": 82_000_000.0, "ppto": 80_000_000.0,
                              "cumplimiento": 102.5}],
            "campos_sin_meta": []}


def _fake_blancos_cerrado(entidad="X", segmento="ecp", nivel="campo", periodo=None):
    return {"encontrada": True, "sin_datos": False, "sin_cierre": False,
            "mes": {"anio": 2026, "mes": 4, "nombre": "Abril", "completo": True,
                    "dias_con_data": 30, "dias_del_mes": 30},
            "por_producto": [{"producto": "BLANCOS", "real": 500_000.0, "ppto": 600_000.0,
                              "cumplimiento": 83.3}],
            "campos_sin_meta": []}


def test_ejecutar_n1_gas_unidad_y_valor_raw():
    resuelta = {"nivel": "campo", "rama": "A", "valor": "CUSIANA", "zoom": []}
    slots = _slots.extraer_slots("cuanto gas produjo Cusiana en abril")
    res = _ejecutor.ejecutar_n1(resuelta, slots, _desempeno_fn=_fake_gas_cerrado)
    assert res["aplica"] is True and res["producto"] == "gas" and res["unidad"] == "MSCF"
    assert res["resultado"]["valor"] == 82_000_000.0   # RAW; el ÷1e6 es SOLO de formato


def test_ejecutar_n2_gas_suma_meses_cerrados():
    resuelta = {"nivel": "campo", "rama": "A", "valor": "CUSIANA", "zoom": []}
    slots = _slots.extraer_slots("acumulado de gas de Cusiana")
    assert slots["nivel_temporal"] == "N2" and slots["producto"] == "gas"
    res = _ejecutor.ejecutar(resuelta, slots, _desempeno_fn=_fake_gas_cerrado)
    assert res["nivel"] == "N2" and res["producto"] == "gas"
    assert res["meses_cerrados"] == 4 and res["resultado"]["valor"] == 82_000_000.0 * 4


def test_ejecutar_n1_blancos_tiene_descargo():
    resuelta = {"nivel": "campo", "rama": "A", "valor": "CUPIAGUA", "zoom": []}
    slots = _slots.extraer_slots("cuantos blancos produjo Cupiagua en abril")
    res = _ejecutor.ejecutar_n1(resuelta, slots, _desempeno_fn=_fake_blancos_cerrado)
    assert res["producto"] == "blancos" and res["unidad"] == "bbl"
    assert any("MME" in a or "mensual" in a.lower() for a in res["avisos"])   # descargo AF5


# ---- drill AF9: el producto se preserva N1 -> N2 ----

def test_continuacion_cuantificar_preserva_gas():
    ctx = {"grupo": "cuantificar", "entidad": "CUSIANA", "producto": "gas"}
    assert _continuacion("acumulado del año", ctx) == "acumulado de gas de CUSIANA"


def test_continuacion_cuantificar_crudo_sin_pieza():
    ctx = {"grupo": "cuantificar", "entidad": "RUBIALES", "producto": "crudo"}
    assert _continuacion("si", ctx) == "acumulado de RUBIALES"


# ---- AF10: el nombre de la entidad NO contamina el grounding de producto ----

def test_slots_producto_no_colisiona_con_nombre_entidad():
    # entidad "CAÑO BLANCO" -> el token BLANCO se descarta -> producto crudo (default)
    s = _slots.extraer_slots("cuanto produjo Caño Blanco", entidad_valor="CAÑO BLANCO")
    assert s["producto"] == "crudo"


def test_slots_producto_explicito_gana_pese_al_nombre():
    # el usuario nombra gas explícito -> gas, aunque la entidad tenga 'BLANCO'
    s = _slots.extraer_slots("cuanto gas produjo Caño Blanco", entidad_valor="CAÑO BLANCO")
    assert s["producto"] == "gas"


def test_slots_producto_sin_entidad_detecta_token():
    # sin entidad (golden/runner) el token se detecta normal (retro-compatible)
    assert _slots.extraer_slots("cuantos blancos produjo Cupiagua")["producto"] == "blancos"


# ==== REGRESIÓN: la memoria NO debe reescribir una pregunta autocontenida (bug 2026-08-02) ====
# "cuántos blancos produjo Cupiagua" son 4 tokens -> entraba al reescritor de _continuacion y salía
# como "produccion de CUPIAGUA": se perdía el PRODUCTO y respondía crudo. Mismo mecanismo borraba
# el MES ("cuánto produjo Castilla en abril" = 5 tokens) y convertía preguntas estructurales
# ("cuántos pozos tiene X") en consultas de producción.
# `entidad_en` se stubbea -> lógica pura, sin BD y sin depender de qué campos existan.

def _stub_entidad(monkeypatch, valor):
    from app.features.consulta_v2 import respuesta_jerarquizar as _rj
    monkeypatch.setattr(_rj, "entidad_en", lambda _t: valor)


def test_continuacion_no_reescribe_pregunta_con_producto(monkeypatch):
    _stub_entidad(monkeypatch, "CUPIAGUA")
    ctx = {"grupo": "cuantificar", "entidad": "CUSIANA", "producto": "gas"}
    assert _continuacion("cuantos blancos produjo Cupiagua", ctx) is None


def test_continuacion_no_reescribe_pregunta_con_mes(monkeypatch):
    _stub_entidad(monkeypatch, "CASTILLA")
    ctx = {"grupo": "cuantificar", "entidad": "RUBIALES", "producto": "crudo"}
    assert _continuacion("cuanto produjo Castilla en abril", ctx) is None


def test_continuacion_no_reescribe_acumulado_de_otra_entidad(monkeypatch):
    # el usuario nombra OTRA entidad: ni "que es X" ni el drill sobre la entidad del ctx sirven.
    _stub_entidad(monkeypatch, "CASTILLA")
    ctx = {"grupo": "cuantificar", "entidad": "RUBIALES", "producto": "crudo"}
    assert _continuacion("acumulado de Castilla", ctx) is None


def test_continuacion_entidad_sola_sigue_reescribiendo(monkeypatch):
    # NO regresión: una entidad suelta ("POE") sí es continuación -> se vuelve autocontenida.
    _stub_entidad(monkeypatch, "POE")
    ctx = {"entidad": "GOR", "nivel": "vicepresidencia"}
    assert _continuacion("POE", ctx) == "que es POE"


def test_continuacion_drill_intacto_sin_entidad_nombrada(monkeypatch):
    # NO regresión (AF9): sin entidad en el texto, "acumulado del año" sigue yendo al drill N1->N2.
    _stub_entidad(monkeypatch, None)
    ctx = {"grupo": "cuantificar", "entidad": "CUSIANA", "producto": "gas"}
    assert _continuacion("acumulado del año", ctx) == "acumulado de gas de CUSIANA"


# ================= Fase 3: N3 serie + N4 variación =================

def test_slots_n3_mes_a_mes():
    assert _slots.extraer_slots("produccion de Rubiales mes a mes")["nivel_temporal"] == "N3"


def test_slots_n3_serie_palabra():
    assert _slots.extraer_slots("serie mensual de Rubiales")["nivel_temporal"] == "N3"


def test_slots_n4_como_vario():
    assert _slots.extraer_slots("como vario Rubiales mes a mes")["nivel_temporal"] == "N4"


def test_slots_n4_gana_sobre_n3():
    # variación + mes a mes -> N4 (más específico)
    assert _slots.extraer_slots("variacion mes a mes de Rubiales")["nivel_temporal"] == "N4"


def test_slots_n1_no_falso_por_token_bajo():
    # AF-3.7: 'BAJO' es token de _VAR_WORDS, pero 'trabajo'/'debajo' NO lo contienen como TOKEN
    assert _slots.extraer_slots("produccion por debajo de Rubiales")["nivel_temporal"] != "N4"


def _fake_ritmo(entidad="X", segmento="ecp", nivel="campo", periodo=None):
    # 4 meses cerrados + mayo en curso (proyección). GAS/BLANCOS vacíos para probar "no aplica".
    return {"encontrada": True, "sin_datos": False, "sin_cierre": False,
            "mes": {"anio": 2026, "mes": 5, "nombre": "Mayo", "completo": False,
                    "dias_con_data": 17, "dias_del_mes": 31},
            "por_producto": [{"producto": "CRUDO", "real": 0, "ppto": 0, "cumplimiento": None}],
            "ritmo_mensual": {"meses": ["Ene", "Feb", "Mar", "Abr", "May"], "meses_num": [1, 2, 3, 4, 5],
                              "series": {"CRUDO": [100, 110, 105, 120, 60],
                                         "GAS": [None, None, None, None, None],
                                         "BLANCOS": [None, None, None, None, None]},
                              "promedio_mes": {"CRUDO": 109}, "promedio_dia": {}, "mes_actual": 5}}


def test_niveles_serie_crudo_con_proyeccion():
    s = _niveles.serie({"nivel": "campo", "valor": "RUBIALES"}, "CRUDO", _desempeno_fn=_fake_ritmo)
    assert s["aplica"] and len(s["puntos"]) == 5
    assert s["proyeccion_mes"] == "May" and s["promedio"] == 109


def test_niveles_variacion_deltas():
    v = _niveles.variacion({"nivel": "campo", "valor": "RUBIALES"}, "CRUDO", _desempeno_fn=_fake_ritmo)
    assert v["aplica"] and len(v["deltas"]) == 4
    assert v["deltas"][0]["delta"] == 10 and v["deltas"][0]["pct"] == 10.0
    assert v["ultimo"]["de"] == "Abr" and v["ultimo"]["a"] == "May" and v["ultimo"]["delta"] == -60


# [2026-08-25] QV2-PANEL-MES: N3/N4 pintan gráfico, y para eso el payload necesita la serie de
# NIVELES (no solo los deltas) y el nº de mes que marca el corte sólido/punteado.
def test_niveles_serie_lleva_num_de_mes_y_mes_actual():
    s = _niveles.serie({"nivel": "campo", "valor": "RUBIALES"}, "CRUDO", _desempeno_fn=_fake_ritmo)
    assert [p["num"] for p in s["puntos"]] == [1, 2, 3, 4, 5]
    assert s["mes_actual"] == 5


def test_niveles_variacion_devuelve_puntos_ademas_de_deltas():
    # El waterfall necesita los niveles absolutos: las barras de partida y cierre son `total`.
    v = _niveles.variacion({"nivel": "campo", "valor": "RUBIALES"}, "CRUDO", _desempeno_fn=_fake_ritmo)
    assert len(v["puntos"]) == len(v["deltas"]) + 1
    assert v["puntos"][0]["valor"] == 100 and v["puntos"][-1]["valor"] == 60
    assert v["mes_actual"] == 5


def test_ejecutar_n4_publica_la_serie_con_el_mismo_nombre_que_n3():
    # 🔑 Un solo nombre público para el mismo dato: `serie` en ambos niveles, nunca `puntos`.
    slots = _slots.extraer_slots("como vario Rubiales mes a mes")
    res = _ejecutor.ejecutar({"nivel": "campo", "rama": "A", "valor": "RUBIALES", "zoom": []},
                             slots, _desempeno_fn=_fake_ritmo)
    assert len(res["serie"]) == 5 and "puntos" not in res
    assert res["mes_actual"] == 5


def test_niveles_variacion_gas_sin_datos_no_aplica():
    v = _niveles.variacion({"nivel": "campo", "valor": "RUBIALES"}, "GAS", _desempeno_fn=_fake_ritmo)
    assert v["aplica"] is False


def test_ejecutar_n3_dispatch():
    slots = _slots.extraer_slots("produccion de Rubiales mes a mes")
    res = _ejecutor.ejecutar({"nivel": "campo", "rama": "A", "valor": "RUBIALES", "zoom": []},
                             slots, _desempeno_fn=_fake_ritmo)
    assert res["nivel"] == "N3" and len(res["serie"]) == 5 and res["proyeccion_mes"] == "May"


def test_ejecutar_n4_dispatch():
    slots = _slots.extraer_slots("como vario Rubiales mes a mes")
    res = _ejecutor.ejecutar({"nivel": "campo", "rama": "A", "valor": "RUBIALES", "zoom": []},
                             slots, _desempeno_fn=_fake_ritmo)
    assert res["nivel"] == "N4" and res["ultimo"]["delta"] == -60


def test_formatear_cuerpo_n3():
    # `entidad_cualificada` es OBLIGATORIA en el contrato §7 (mismo hallazgo que Fase 2:
    # test_formatear_cuerpo_gas_dice_mscf) — el fixture debe reflejarlo o falla por KeyError.
    res = {"nivel": "N3", "producto": "crudo", "unidad": "bbl", "anio": 2026,
           "entidad_cualificada": "el Campo RUBIALES",
           "serie": [{"mes": "Ene", "valor": 100}, {"mes": "Feb", "valor": 110}],
           "promedio": 105, "avisos": []}
    c = _validador.formatear_cuerpo(res)
    assert "mes a mes" in c and "Ene 100" in c and "Promedio" in c


def test_formatear_cuerpo_n4():
    res = {"nivel": "N4", "producto": "crudo", "unidad": "bbl", "anio": 2026,
           "entidad_cualificada": "el Campo RUBIALES",
           "deltas": [{"de": "Ene", "a": "Feb", "delta": 10, "pct": 10.0}],
           "ultimo": {"de": "Ene", "a": "Feb", "delta": 10, "pct": 10.0}, "avisos": []}
    c = _validador.formatear_cuerpo(res)
    assert "subió" in c and "Feb" in c


# ==== REGRESIÓN: norm() no retira ¿/? — un token pegado al signo no debe fallar el match ====
# Bug real (golden runner, 2026-08-02): "¿serie mensual de gas de Cusiana?" clasificaba N1 en vez
# de N3, porque el primer token quedaba "¿SERIE" (no "SERIE") y el match por token fallaba. Mismo
# defecto latente en _producto (Fase 2) para el ÚLTIMO token de la frase.

def test_slots_n3_signo_apertura_no_rompe_el_token():
    assert _slots.extraer_slots("¿serie mensual de gas de Cusiana?")["nivel_temporal"] == "N3"


def test_slots_producto_signo_cierre_no_rompe_el_token():
    assert _slots.extraer_slots("¿cuánto produjo de gas?")["producto"] == "gas"


def test_slots_n4_signo_apertura_no_rompe_el_token():
    assert _slots.extraer_slots("¿cómo varió Rubiales mes a mes?")["nivel_temporal"] == "N4"


# ================= Fase 4: referencias != PPTO (N1) =================

def test_slots_ref_operativo():
    assert _slots.extraer_slots("cuanto produjo Rubiales vs el operativo")["referencia"] == "OPERATIVO"


def test_slots_ref_contable():
    assert _slots.extraer_slots("cuanto produjo Rubiales contra el contable")["referencia"] == "CONTABLE"


def test_slots_ref_p50():
    assert _slots.extraer_slots("cuanto produjo Rubiales vs el P50")["referencia"] == "P50"


def test_slots_ref_default_ppto():
    assert _slots.extraer_slots("cuanto produjo Rubiales en abril")["referencia"] == "PPTO"


def test_slots_ref_promedio_fuerza_n1():
    # AF-4.9: "promedio del año" es la referencia -> N1, NO N2 (aunque contenga "del año")
    s = _slots.extraer_slots("cuanto produjo Rubiales frente al promedio del año")
    assert s["referencia"] == "promedio_anio" and s["nivel_temporal"] == "N1"


def _fake_n1_ritmo(entidad="X", segmento="ecp", nivel="campo", periodo=None):
    return {"encontrada": True, "sin_datos": False, "sin_cierre": False,
            "mes": {"anio": 2026, "mes": 4, "nombre": "Abril", "completo": True,
                    "dias_con_data": 30, "dias_del_mes": 30},
            "por_producto": [{"producto": "CRUDO", "real": 1200.0, "ppto": 1250.0, "cumplimiento": 96.0}],
            "campos_sin_meta": [],
            "ritmo_mensual": {"meses": ["Ene", "Feb", "Mar", "Abr"], "meses_num": [1, 2, 3, 4],
                              "series": {"CRUDO": [100, 110, 105, 120]},
                              "promedio_mes": {"CRUDO": 109}, "promedio_dia": {}}}


def test_ejecutar_n1_p50_rechaza():
    slots = _slots.extraer_slots("cuanto produjo Rubiales vs el P50")
    res = _ejecutor.ejecutar_n1({"nivel": "campo", "rama": "A", "valor": "RUBIALES", "zoom": []},
                                slots, _desempeno_fn=_fake_n1_ritmo)
    assert res["aplica"] is False and "P50" in res["texto"]


def test_ejecutar_n1_promedio_usa_ritmo():
    slots = _slots.extraer_slots("cuanto produjo Rubiales frente al promedio del año")
    res = _ejecutor.ejecutar_n1({"nivel": "campo", "rama": "A", "valor": "RUBIALES", "zoom": []},
                                slots, _desempeno_fn=_fake_n1_ritmo)
    assert res["aplica"] and res["referencia"] == "promedio_anio"
    assert res["referencia_valor"] == 109 and res["referencia_label"] == "promedio mensual del año"
    assert res["estado"] == "sobre el promedio"      # AF-4.10: direccional, NO "Alineado" (1200 > 109)


def test_ejecutar_n1_operativo_usa_helper():
    slots = _slots.extraer_slots("cuanto produjo Rubiales vs el operativo")

    def _fake_esc(entidad, nivel=None, periodo=None, escenarios=()):
        return {"CRUDO": {"OPERATIVO": 1300.0}}

    res = _ejecutor.ejecutar_n1({"nivel": "campo", "rama": "A", "valor": "RUBIALES", "zoom": []},
                                slots, _desempeno_fn=_fake_n1_ritmo, _escenario_fn=_fake_esc)
    assert res["referencia"] == "OPERATIVO" and res["referencia_valor"] == 1300.0
    assert res["cumplimiento_pct"] == round(1200 / 1300 * 100, 1)


def test_ejecutar_n1_ppto_sin_regresion():
    # PPTO recomputado = real/ppto = fila["cumplimiento"] -> idéntico a Fase 1-3
    slots = _slots.extraer_slots("cuanto produjo Rubiales en abril")
    res = _ejecutor.ejecutar_n1({"nivel": "campo", "rama": "A", "valor": "RUBIALES", "zoom": []},
                                slots, _desempeno_fn=_fake_n1_ritmo)
    assert res["referencia"] == "PPTO" and res["referencia_valor"] == 1250.0
    assert res["cumplimiento_pct"] == round(1200 / 1250 * 100, 1)


# ==== REGRESIÓN: drill de REFERENCIA tras un N1 (bug real, pruebas de navegador 2026-08-02) ====
# Tras "vs el operativo", el usuario sigue con "...contra el contable" o "...frente al promedio
# del año". Sin la rama _REF_CONTINUA_KW (que va ANTES de _ACUM_KW en _continuacion), la 2ª frase
# caía en el drill de ACUMULADO (por el substring "DEL ANO") y daba el acumulado vs PPTO — una
# cifra DISTINTA a la pedida, con la MISMA confianza visual. La 1ª frase, sin ninguna rama que la
# atrapara, caía a OUT (Desconocido).

def test_continuacion_referencia_contable_no_cae_a_out():
    ctx = {"grupo": "cuantificar", "entidad": "RUBIALES", "producto": "crudo"}
    assert _continuacion("contra el contable", ctx) == "produccion de RUBIALES contra el contable"


def test_continuacion_referencia_promedio_no_colisiona_con_acumulado():
    # "promedio del año" contiene "DEL ANO" -> sin el orden correcto, _ACUM_KW la atrapaba primero
    ctx = {"grupo": "cuantificar", "entidad": "RUBIALES", "producto": "crudo"}
    r = _continuacion("frente al promedio del año", ctx)
    assert r == "produccion de RUBIALES frente al promedio del año"
    s = _slots.extraer_slots(r, entidad_valor="RUBIALES")
    assert s["nivel_temporal"] == "N1" and s["referencia"] == "promedio_anio"   # NO "acumulado de..."


def test_continuacion_referencia_preserva_producto():
    # AF9 también aplica en el drill de referencia: un N1 de gas + "contra el contable" no debe
    # volver a crudo.
    ctx = {"grupo": "cuantificar", "entidad": "CUSIANA", "producto": "gas"}
    r = _continuacion("contra el contable", ctx)
    assert r == "produccion de gas de CUSIANA contra el contable"
    s = _slots.extraer_slots(r, entidad_valor="CUSIANA")
    assert s["producto"] == "gas" and s["referencia"] == "CONTABLE"


def test_continuacion_acumulado_sin_regresion_tras_fix_referencia():
    # Ninguna palabra de _REF_CONTINUA_KW en "acumulado del año"/"si" -> sigue yendo al drill N1->N2.
    ctx = {"grupo": "cuantificar", "entidad": "RUBIALES", "producto": "crudo"}
    assert _continuacion("acumulado del año", ctx) == "acumulado de RUBIALES"
    assert _continuacion("si", ctx) == "acumulado de RUBIALES"


# ==== REGRESIÓN: drill N1 GENÉRICO — cambiar de mes sin repetir la entidad (bug real, 2026-08-02) ====
# "Mayo, ¿cuánto ha producido?" tras hablar de Rubiales perdía el hilo -> Desconocido. Ninguna rama
# existente lo cubría: no nombra la entidad (no es el caso `ent`), no pide acumulado ni referencia.
# El texto SÍ trae intención de producción ("cuánto"/"ha producido") -> debe entenderse como el
# mismo N1 de siempre, con el mes que traiga el texto.

def test_continuacion_mes_sin_nombrar_entidad():
    ctx = {"grupo": "cuantificar", "entidad": "RUBIALES", "producto": "crudo"}
    r = _continuacion("Mayo cuánto ha producido?", ctx)
    assert r == "produccion de RUBIALES Mayo cuánto ha producido?"
    s = _slots.extraer_slots(r, entidad_valor="RUBIALES")
    assert s["nivel_temporal"] == "N1" and s["periodo_texto"] == "mayo"


def test_continuacion_mes_generico_preserva_producto():
    ctx = {"grupo": "cuantificar", "entidad": "CUSIANA", "producto": "gas"}
    r = _continuacion("cuánto en abril?", ctx)
    s = _slots.extraer_slots(r, entidad_valor="CUSIANA")
    assert s["producto"] == "gas" and s["periodo_texto"] == "abril"


# ==== REGRESIÓN: QV2-MES-CTX — "la producción del mes" hereda el mes de la charla, no el de HOY
# (2026-08-26). Bug real: tras "el día 15 de mayo, ¿cuánto produjo Castilla?" (N1D), preguntar
# "muéstrame la producción del mes" —sin nombrar mes— entraba al Drill N1 GENÉRICO, que sí heredaba
# la ENTIDAD pero dejaba el texto intacto; slots.py no encontraba un mes ahí y asumía HOY (agosto en
# vez de mayo), aunque toda la charla giraba en torno a mayo. ====

def test_periodo_ctx_de_desde_fecha_n1d():
    assert _periodo_ctx_de({"fecha": "2026-05-15"}) == "mayo 2026"


def test_periodo_ctx_de_desde_mes_n1():
    assert _periodo_ctx_de({"mes": {"anio": 2026, "mes": 8, "nombre": "Agosto"}}) == "agosto 2026"


def test_periodo_ctx_de_none_si_no_hay_mes_unico():
    """N2/N3/N4 no fijan un único mes (acumulado/serie/variación) — no hay nada que heredar."""
    assert _periodo_ctx_de({"periodo_label": "enero-agosto 2026"}) is None
    assert _periodo_ctx_de({}) is None


def test_continuacion_mes_generico_hereda_periodo_de_contexto():
    ctx = {"grupo": "cuantificar", "entidad": "CASTILLA", "producto": "crudo",
           "periodo_ctx": "mayo 2026"}
    r = _continuacion("muestrame la produccion del mes", ctx)
    assert r == "produccion de CASTILLA muestrame la produccion del mes en mayo 2026"
    s = _slots.extraer_slots(r, entidad_valor="CASTILLA")
    assert s["nivel_temporal"] == "N1" and s["periodo_texto"] == "mayo 2026"


def test_continuacion_mes_generico_sin_periodo_ctx_no_inyecta_nada():
    """Tras un N2/ranking (sin mes único que heredar), el comportamiento es el de siempre."""
    ctx = {"grupo": "cuantificar", "entidad": "CASTILLA", "producto": "crudo"}
    r = _continuacion("muestrame la produccion del mes", ctx)
    assert r == "produccion de CASTILLA muestrame la produccion del mes"


def test_continuacion_mes_actual_explicito_no_hereda():
    """"este mes"/"mes actual" son un pedido EXPLÍCITO de HOY: no se le impone el mes heredado."""
    ctx = {"grupo": "cuantificar", "entidad": "CASTILLA", "producto": "crudo",
           "periodo_ctx": "mayo 2026"}
    assert _continuacion("la produccion de este mes", ctx) == \
        "produccion de CASTILLA la produccion de este mes"
    assert _continuacion("la produccion del mes actual", ctx) == \
        "produccion de CASTILLA la produccion del mes actual"


def test_continuacion_mes_propio_gana_sobre_el_heredado():
    """Caso límite: la frase YA trae su propio mes (y una palabra estructural genérica, "campo",
    con verbo explícito) -> ese mes debe ganar, no sumarse al heredado (evita "en junio en mayo
    2026" en el mismo texto). <=5 tokens para no topar con el corte de longitud (ajeno a esto,
    ver H-13 en test_cuantificar_dia.py)."""
    ctx = {"grupo": "cuantificar", "entidad": "CASTILLA", "producto": "crudo",
           "periodo_ctx": "mayo 2026"}
    r = _continuacion("produjo el campo en junio", ctx)
    assert r == "produccion de CASTILLA produjo el campo en junio"
    s = _slots.extraer_slots(r, entidad_valor="CASTILLA")
    assert s["periodo_texto"] == "junio"


def test_continuacion_acumulado_explicito_gana_sobre_drill_generico():
    # "cuanto" (prod=True) Y "acumulado" (_ACUM_KW) a la vez -> gana acumulado (chequeado primero).
    ctx = {"grupo": "cuantificar", "entidad": "RUBIALES", "producto": "crudo"}
    assert _continuacion("cuanto acumulado?", ctx) == "acumulado de RUBIALES"


def test_continuacion_mes_sin_verbo_hereda_entidad():
    # [2026-08-25 · QV2-HILO-DIA F4] Este test aseveraba `is None`: "y en abril?" sin verbo de
    # producción se quedaba sin resolver. Eso ERA el bug reportado por el usuario ("y en mayo?"
    # tras ver la cifra de un mes perdía el hilo — el LLM, viendo la frase desnuda, respondía que
    # "los periodos de tiempo" no son su dominio). _TEMP_CONT_KW ahora incluye los nombres de mes
    # (maquina_q.py), así que esta frase SÍ hereda la entidad del contexto — el comportamiento
    # correcto, no una sobre-extensión: "abril" es la única señal y viene de _TEMP_CONT_KW, no de
    # un verbo de producción inventado.
    ctx = {"grupo": "cuantificar", "entidad": "RUBIALES", "producto": "crudo"}
    assert _continuacion("y en abril?", ctx) == "produccion de RUBIALES y en abril?"


# ==== REGRESIÓN: AF-4.9 perdía un "acumulado" explícito si además pedía una referencia (2026-08-02) ====
# "La producción ACUMULADA de Rubiales... por debajo de su promedio anual?" es un pedido legítimo:
# acumulado (N2), comparado contra el promedio. El override viejo forzaba N1 SIEMPRE que
# referencia==promedio_anio, sin mirar si el N2 era genuino o solo un artefacto de "promedio DEL
# AÑO". _nivel_temporal(texto) sola SÍ decía N2 (correcto) — el bug estaba en el override.

def test_slots_acumulado_explicito_no_se_pierde_con_referencia_promedio():
    texto = "La producción acumulada de Rubiales cuánto está por debajo de su promedio anual?"
    s = _slots.extraer_slots(texto, entidad_valor="RUBIALES")
    assert s["nivel_temporal"] == "N2" and s["referencia"] == "promedio_anio"


def test_slots_promedio_del_ano_sigue_forzando_n1_sin_acumulado_explicito():
    # NO regresión: el caso ORIGINAL de AF-4.9 — solo la señal débil "DEL ANO" -> sigue en N1.
    texto = "cuanto produjo Rubiales frente al promedio del año"
    s = _slots.extraer_slots(texto, entidad_valor="RUBIALES")
    assert s["nivel_temporal"] == "N1" and s["referencia"] == "promedio_anio"


def test_ejecutar_n2_promedio_anio_avisa_que_no_aplica():
    # El N2 recuperado por el fix igual debe declarar que la referencia alterna no se aplicó (AF-4.7)
    # — nunca la pierde en silencio ni finge comparar el acumulado contra el promedio.
    texto = "La producción acumulada de Rubiales cuánto está por debajo de su promedio anual?"
    slots = _slots.extraer_slots(texto, entidad_valor="RUBIALES")
    resuelta = {"nivel": "campo", "rama": "A", "valor": "RUBIALES", "zoom": []}
    res = _ejecutor.ejecutar(resuelta, slots, _desempeno_fn=_fake_mes_cerrado)
    assert res["nivel"] == "N2"
    assert any("referencias alternas" in a for a in res["avisos"])


# --- Nivel EXPLÍCITO (bug 2 de jerarquias_sup_error.md, 2026-09-03) ------------------------

def test_nivel_explicito_detecta_activo_y_campo():
    """Puro: solo lee el texto. Exige adyacencia nivel+nombre (H9 del plan)."""
    assert _resolver._nivel_explicito("el activo CASTILLA") == "activo"
    assert _resolver._nivel_explicito("la produccion del activo APIAY mes a mes") == "activo"
    assert _resolver._nivel_explicito("el campo CASTILLA") == "campo"


def test_nivel_explicito_none_sin_senal():
    """Sin sustantivo de nivel pegado al nombre, no hay señal -> D-D5 decide como siempre."""
    assert _resolver._nivel_explicito("CASTILLA") is None
    assert _resolver._nivel_explicito("cuanto crudo produjo Rubiales") is None


def test_activo_explicito_gana_a_dd5():
    """🔑 EL BUG: con «activo» explícito, el activo gana y el campo baja a zoom.
    Es el inverso exacto de test_prioridad_campo_campo_mas_activo_da_zoom (mismo caso APIAY)."""
    reps = [
        {"nivel": "campo", "rama": "A", "valor": "APIAY"},
        {"nivel": "activo", "rama": "A", "valor": "APIAY"},
    ]
    elegido = [r for r in reps if r["nivel"] == _resolver._nivel_explicito("el activo APIAY")]
    assert len(elegido) == 1 and elegido[0]["nivel"] == "activo"


def test_dd5_sigue_intacta_sin_senal():
    """🔒 REGRESIÓN: sin señal explícita, D-D5 manda (decisión del usuario 2026-07-15).
    Este test es el guardián de que la corrección no se pasó de ancho."""
    reps = [
        {"nivel": "campo", "rama": "A", "valor": "APIAY"},
        {"nivel": "activo", "rama": "A", "valor": "APIAY"},
    ]
    rep_campo, zoom = _resolver._prioridad_campo(reps)
    assert rep_campo is not None and rep_campo["nivel"] == "campo"
    assert len(zoom) == 1 and zoom[0]["nivel"] == "activo"


def test_contexto_llega_al_resolver_cuando_la_entidad_ya_fue_extraida():
    """🔴 EL FALLO QUE SE ESCAPÓ (medido en Pruebas 2026-09-03): el arreglo del nivel
    explícito funcionaba en aislamiento pero estaba DESCONECTADO en la app real.

    `responder()` llama `resolver_unico(entidad or texto)` y maquina_q.detectar_entidad ya
    redujo «¿Producción del Activo CASTILLA?» a «CASTILLA» — la palabra «activo» se perdía
    antes de llegar al detector, y el chat seguía respondiendo «el Campo CASTILLA».

    Este test fija el CONTRATO del contexto sin tocar BD: con `contexto`, el detector ve la
    frase completa; sin él, solo el nombre."""
    texto = "Cual es la Produccion del Activo CASTILLA"
    # lo que la app le pasa como `texto` es solo el nombre ya extraído:
    assert _resolver._nivel_explicito("CASTILLA") is None
    # ...y el contexto es lo que salva la señal:
    assert _resolver._nivel_explicito(texto) == "activo"


def test_resolver_con_contexto_tolera_un_resolver_sustituido(monkeypatch):
    """🔒 REGRESIÓN: 13 tests de test_p50_referencia.py monkeypatchean `resolver_unico` con
    lambdas de UN argumento. El helper debe degradar en vez de reventar con TypeError —
    pasó al implementar esto y rompió esos 13 de golpe."""
    import app.features.consulta_v2.respuesta_cuantificar as _rc
    monkeypatch.setattr(_rc._resolver, "resolver_unico",
                        lambda x: {"valor": "RUBIALES", "rama": "A", "nivel": "campo"})
    r = _rc._resolver_con_contexto("RUBIALES", "cuanto produjo el activo RUBIALES")
    assert r["nivel"] == "campo"        # el doble manda; no se rompe la llamada
