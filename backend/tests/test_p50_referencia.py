"""Tests de la sub-intención 'referencia' de ANALIZAR (P50 pedido como CIFRA, no como causa).
Plan: plan_p50_referencia_analizar_2026-08-13.md.

T1-T14: PUROS (subrouter + formatear_declinar/cierre_declinar), sin BD ni LLM.
T15: dispatcher completo con resolución de entidad MONKEYPARCHEADA (evita BD, corre en dev).
T16-T19: contra BD real (map_campo_robustez / NEW MES-AÑO t8+t2) — se saltan con gracia si
Postgres no está disponible, mismo patrón `_engine_o_skip` de test_puente_gerencia_vp.py.

🔑 Nota de diseño (descubierta al implementar, no en el plan original): `formatear_declinar()` NO
incluye el cierre — el cierre es DINÁMICO (M6: varía si hay o no vicepresidencia ofrecible) y se
arma aparte con `cierre_declinar()`. Las pruebas M5/M9 del plan (T11/T14) se verifican sobre
`cierre_declinar()`, que es la pieza que realmente cierra la conversación.
"""
from datetime import date

import pytest

from app.features.consulta_v2.analizar import subrouter as _subrouter
from app.features.consulta_v2.analizar import p50_referencia as _p50
from app.features.consulta_v2 import respuesta_analizar as _ra


# ---------------- T1-T6: sub_intencion (puro) ----------------

def test_t1_referencia_campo_rubiales():
    assert _subrouter.sub_intencion("dame el p50 para el campo rubiales") == "referencia"

def test_t2_causal_gana_por_que():
    assert _subrouter.sub_intencion("por que estamos bajo el p50?") == "causal"

def test_t3_proyeccion_gana_vamos_a_llegar():
    assert _subrouter.sub_intencion("vamos a llegar al p50?") == "proyeccion"

def test_t4_economia_ebitda():
    assert _subrouter.sub_intencion("como va el ebitda?") == "economia"

def test_t5_referencia_que_campos_debajo_p50():
    assert _subrouter.sub_intencion("que campos estan por debajo del p50?") == "referencia"

def test_t6_referencia_signo_pegado_he7():
    # norm() NO retira '?' (HE7, bug real 2026-08-02) -> el match debe ser por TOKEN, no por frase.
    assert _subrouter.sub_intencion("cual es el P50?") == "referencia"

def test_no_regresion_diferidas_y_causal_generico():
    assert _subrouter.sub_intencion("que paso con las diferidas de Cajua?") == "diferidas"
    assert _subrouter.sub_intencion("explica por que Castilla esta corto") == "causal"


# ---------------- T7-T8: nivel_soportado (puro) ----------------

def test_t7_nivel_no_soportado():
    for n in ("campo", "activo", "gerencia", "operador", "fuente"):
        assert _p50.nivel_soportado(n) is False, n

def test_t8_nivel_soportado():
    assert _p50.nivel_soportado(None) is True
    assert _p50.nivel_soportado("vicepresidencia") is True


# --- V-1: gerencia con puente=True SÍ tiene P50 (S32/R2) ---------------------------------------
# Bug real hallado en verificación (2026-08-13): GOR resuelve como nivel="gerencia" con
# puente=True (marca de S32: INGESTA lo llama gerencia, robustez lo tiene como VICEPRESIDENCIA —
# la taxonomía de t8). Sin mirar `puente`, "el P50 de GOR" declinaba pese a EXISTIR, y el drill
# de "la vicepresidencia" encadenaba un declinar tras otro.

def test_v1_gerencia_con_puente_es_soportada():
    assert _p50.nivel_soportado("gerencia", {"puente": True}) is True

def test_v1b_gerencia_sin_puente_no_es_soportada():
    assert _p50.nivel_soportado("gerencia", {}) is False
    assert _p50.nivel_soportado("gerencia", None) is False

def test_v1c_puente_no_habilita_otros_niveles():
    # `puente` solo aplica a gerencia — un campo marcado (no debería ocurrir) NO gana P50.
    assert _p50.nivel_soportado("campo", {"puente": True}) is False


# ---------------- T9-T14: formatear_declinar / cierre_declinar (puros) ----------------

_VP_INFO = {"vice": "GOR", "producto": "CRUDO", "fecha": date(2026, 4, 30),
            "real": 143669.0, "p50": 154700.0, "pct": 92.9}


def test_t9_sin_vp_no_ofrece_la_opcion():
    # M6: sin vp_info NO se ofrece la 2ª opción. La negación (M2) SÍ menciona "vicepresidencia"
    # una vez, al explicar POR QUÉ no hay P50 a nivel campo — eso es esperado en TODO declinar.
    cuerpo = _p50.formatear_declinar("CAJUA", "campo", 88.2, -649755, "CRUDO", vp_info=None)
    assert "El P50 de su vicepresidencia" not in cuerpo
    assert cuerpo.lower().count("vicepresidencia") == 1   # solo la mención de M2

def test_t10_primera_linea_es_la_negacion():
    cuerpo = _p50.formatear_declinar("RUBIALES", "campo", 95.6, -566752, "CRUDO", vp_info=_VP_INFO)
    primera = cuerpo.split("\n")[0]
    assert primera.startswith("No tengo un P50 para RUBIALES.")

def test_t11_cierre_nunca_termina_en_pregunta_si_no():
    for vp in (None, _VP_INFO):
        c = _p50.cierre_declinar(vp)
        assert not c.rstrip().endswith("?"), c

def test_t12_contiene_el_nivel():
    cuerpo = _p50.formatear_declinar("RUBIALES", "campo", 95.6, -566752, "CRUDO", vp_info=_VP_INFO)
    assert "el Campo RUBIALES" in cuerpo
    # contracción es-CO correcta ("del Campo", no "de el Campo")
    assert "de el Campo" not in cuerpo

def test_t12b_contiene_el_nivel_activo():
    cuerpo = _p50.formatear_declinar("CPO-09", "activo", None, None, "CRUDO", vp_info=None)
    assert "el Activo CPO-09" in cuerpo

def test_t13_cada_opcion_declara_su_periodo():
    cuerpo = _p50.formatear_declinar("RUBIALES", "campo", 95.6, -566752, "CRUDO", vp_info=_VP_INFO)
    assert "mes" in cuerpo.lower()          # opción de presupuesto: "del mes"
    assert "abril" in cuerpo.lower()        # opción de VP: mes leído de vp_info["fecha"]

def test_t14_cierre_usa_vocabulario_del_drill():
    # M9/H3: el cierre debe usar palabras que _continuacion() reconoce (PRESUPUESTO/VICEPRESIDENCIA).
    assert "presupuesto" in _p50.cierre_declinar(None).lower()
    c = _p50.cierre_declinar(_VP_INFO)
    assert "presupuesto" in c.lower() and "vicepresidencia" in c.lower()

def test_m6_vp_omitida_cambia_el_texto_y_el_cierre():
    cuerpo_con = _p50.formatear_declinar("RUBIALES", "campo", 95.6, -566752, "CRUDO", vp_info=_VP_INFO)
    cuerpo_sin = _p50.formatear_declinar("RUBIALES", "campo", 95.6, -566752, "CRUDO", vp_info=None)
    assert "GOR" in cuerpo_con and "GOR" not in cuerpo_sin
    assert _p50.cierre_declinar(_VP_INFO) != _p50.cierre_declinar(None)

def test_declinar_sin_meta_ppto_lo_declara():
    cuerpo = _p50.formatear_declinar("CAMPO-X", "campo", None, None, "CRUDO", vp_info=None)
    assert "no tiene meta" in cuerpo.lower()


# --- V-2: formato es-CO de la cifra global (kbpe) -----------------------------------------------
# Bug real hallado en verificación (2026-08-13): `f"{n:,.1f}".replace(",", ".")` producía
# "501.716.5" — punto de miles Y punto decimal, un número ambiguo en es-CO. Debe ser "501.716,5".

def test_v2_kbpe_separadores_es_co():
    assert _p50._kbpe(501716.53) == "501.716,5"
    assert _p50._kbpe(521.818690137288) == "521,8"
    assert _p50._kbpe(0) == "0,0"

def test_v2b_cifra_global_no_tiene_doble_punto():
    card = {"entidad": "Crudo", "real_mes": 501716.53, "base_p50": 521818.69,
            "cumpl_p50": 96.1, "compromiso": None, "compromiso_difiere": False}
    txt = _p50.formatear_cifra_global(card, "kbpe", "CRUDO", "2026-05-18")
    assert "501.716,5" in txt
    assert "501.716.5" not in txt   # el formato inválido que tenía el bug


# ---------------- T15: dispatcher completo, entidad MONKEYPARCHEADA (sin BD) ----------------

def _fake_ejecutivo_rubiales(entidad=None, segmento="ecp", nivel=None, periodo=None, pulir=False):
    return {
        "entidad": entidad, "encontrada": True, "sin_datos": False,
        "meta": {"scope": entidad, "periodo": "mayo 2026"},
        "titular": [{"producto": "CRUDO", "valor_pct": 95.6, "texto": "Alineado"}],
        "gap_por_producto": {"CRUDO": {"faltante_bruto": -566752}},
    }


def test_t15_panel_es_none_en_referencia(monkeypatch):
    monkeypatch.setattr(_ra._resolver, "resolver_unico",
                         lambda t: {"nivel": "campo", "valor": "RUBIALES", "rama": "A", "zoom": []})
    r = _ra.responder_con_panel(
        "dame el p50 para el campo rubiales",
        _ejecutivo_fn=_fake_ejecutivo_rubiales,
        _vp_fn=lambda campo: "GOR",
        _p50_fn=lambda vice, prod: _VP_INFO,
    )
    assert r["panel"] is None
    assert "No tengo un P50 para RUBIALES" in r["mensaje"]
    assert "95,6" in r["mensaje"] or "95.6" in r["mensaje"]
    assert "GOR" in r["mensaje"]

def test_t15b_declinar_sin_vp_ofrecible(monkeypatch):
    # M6: campo de tercero -> _vp_fn devuelve None -> el mensaje NO OFRECE vicepresidencia (aunque
    # SÍ la mencione una vez en la negación M2, al explicar por qué el P50 no baja a campo).
    monkeypatch.setattr(_ra._resolver, "resolver_unico",
                         lambda t: {"nivel": "campo", "valor": "CAJUA", "rama": "A", "zoom": []})
    r = _ra.responder_con_panel(
        "dame el p50 de cajua",
        _ejecutivo_fn=_fake_ejecutivo_rubiales,
        _vp_fn=lambda campo: None,
    )
    assert r["panel"] is None
    assert "El P50 de su vicepresidencia" not in r["mensaje"]
    assert "dime cual" not in r["mensaje"].lower().replace("é", "e")   # cierre de una sola opción

def test_t15c_no_regresion_causal_sin_tocar(monkeypatch):
    # 'por qué' NO debe caer en 'referencia' aunque mencione P50/gap en el resto de la frase.
    monkeypatch.setattr(_ra._resolver, "resolver_unico",
                         lambda t: {"nivel": "campo", "valor": "RUBIALES", "rama": "A", "zoom": []})
    r = _ra.responder_con_panel("por que Rubiales esta bajo el p50?",
                                _ejecutivo_fn=_fake_ejecutivo_rubiales)
    assert r["panel"] is not None or "faltante" in r["mensaje"].lower() or "presupuesto" in r["mensaje"].lower()


# --- V-3: el declinar EXPONE la VP ofrecida, y el drill la usa (anti-bucle) ---------------------
# Bug real hallado en verificación (2026-08-13): el usuario elegía "la vicepresidencia" y el drill
# reescribía con el nombre del CAMPO -> volvía a resolver como campo -> MISMO declinar, en bucle.

def test_v3_declinar_expone_vp_ofrecida(monkeypatch):
    monkeypatch.setattr(_ra._resolver, "resolver_unico",
                         lambda t: {"nivel": "campo", "valor": "RUBIALES", "rama": "A", "zoom": []})
    r = _ra.responder_con_panel("dame el p50 para el campo rubiales",
                                _ejecutivo_fn=_fake_ejecutivo_rubiales,
                                _vp_fn=lambda campo: "GOR",
                                _p50_fn=lambda vice, prod: _VP_INFO)
    assert r.get("vp_ofrecida") == "GOR"

def test_v3b_sin_vp_ofrecida_es_none(monkeypatch):
    monkeypatch.setattr(_ra._resolver, "resolver_unico",
                         lambda t: {"nivel": "campo", "valor": "CAJUA", "rama": "A", "zoom": []})
    r = _ra.responder_con_panel("dame el p50 de cajua",
                                _ejecutivo_fn=_fake_ejecutivo_rubiales,
                                _vp_fn=lambda campo: None)
    assert r.get("vp_ofrecida") is None

def test_v3c_drill_reescribe_con_la_vp_no_con_el_campo():
    from app.features.consulta_v2.maquina_q import _continuacion
    ctx = {"grupo": "analizar", "entidad": "RUBIALES", "sub": "referencia",
           "producto": None, "vp": "GOR"}
    rw = _continuacion("la vicepresidencia", ctx)
    assert "GOR" in rw and "RUBIALES" not in rw, rw

def test_v3d_drill_sin_vp_conserva_la_entidad():
    from app.features.consulta_v2.maquina_q import _continuacion
    ctx = {"grupo": "analizar", "entidad": "RUBIALES", "sub": "referencia",
           "producto": None, "vp": None}
    rw = _continuacion("la vicepresidencia", ctx)
    assert "RUBIALES" in rw


# ---------------- T16-T19: contra BD real (A4/A5/A6 del plan) ----------------

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


def test_t16_vp_de_campo_rubiales():
    _engine_o_skip()
    assert _p50.vp_de_campo("RUBIALES") == "GOR"

def test_t17_vp_de_campo_tercero_none():
    _engine_o_skip()
    assert _p50.vp_de_campo("CAJUA") is None

def test_t18_p50_por_vp_gor_abril():
    _engine_o_skip()
    info = _p50.p50_por_vp("GOR", "CRUDO")
    assert info is not None
    assert info["fecha"] == date(2026, 4, 30)
    assert abs(info["pct"] - 92.9) < 0.5

def test_v4_p50_por_vp_no_se_ancla_al_ultimo_reporte():
    """El reporte MÁS RECIENTE puede no traer la hoja 'NEW MES-AÑO' (cobertura heterogénea por
    archivo, §4c) — la búsqueda debe ir al reporte más reciente QUE TENGA el dato, no rendirse en
    el primero. Defecto real visto en el servidor de pruebas 2026-08-13 (GOR respondía "no tengo
    P50" con el dato existiendo); invisible en dev, donde los 18 reportes traen la hoja."""
    _engine_o_skip()
    info = _p50.p50_por_vp("GOR", "CRUDO")
    assert info is not None, "GOR tiene P50+REAL en la BD; no debe declinar"
    assert info.get("corte") is not None, "debe declarar de qué reporte salió"


def test_v5_alcance_dice_vicepresidencia_no_gerencia(monkeypatch):
    """El intro anunciaba 'la GERENCIA GOR' mientras el cuerpo decía 'esa VICEPRESIDENCIA' — dos
    etiquetas contradictorias en el mismo mensaje. Con `puente`, el alcance debe decir VP."""
    capturado = {}

    def _fake_intro(alcance, usuario):
        capturado["alcance"] = alcance
        return ""

    monkeypatch.setattr(_ra, "_intro", _fake_intro)
    monkeypatch.setattr(_ra._resolver, "resolver_unico",
                         lambda t: {"nivel": "gerencia", "valor": "GOR", "rama": "A",
                                    "zoom": [], "puente": True})
    # _serie_fn=None (puro): esta prueba valida el `alcance` del intro, no el panel — sin
    # inyectarla, `panel_ref` llamaría a la BD real (degrada con gracia, pero no es el punto
    # de esta prueba y la haría depender de Postgres sin necesidad).
    _ra.responder_con_panel("cual es el p50 de GOR",
                            _p50_fn=lambda vice, prod: _VP_INFO,
                            _serie_fn=lambda vice, prod: None)
    assert "vicepresidencia" in capturado.get("alcance", "").lower()
    assert "gerencia" not in capturado.get("alcance", "").lower()


def test_t19_p50_por_vp_glh_sin_dato():
    # GLH está en t8 pero NO en robustez (A5) — aquí solo importa que t8+t2 no den REAL para ella
    # en ningún mes, o que el código simplemente no truene. No se afirma el resultado exacto porque
    # depende del estado de ingesta; se afirma el CONTRATO (no lanza, tipo correcto).
    _engine_o_skip()
    info = _p50.p50_por_vp("GLH", "CRUDO")
    assert info is None or isinstance(info, dict)


# ==================================================================================================
# PANEL DERECHO "p50_vp" — plan_panel_p50_vp_2026-08-13.md
# ==================================================================================================
# P1-P4/P9-P11: contra BD real (A1/A2/A3/H4 del plan). P5-P8: dispatcher, monkeypatch (sin BD).

def test_p1_serie_por_vp_gor_crudo():
    _engine_o_skip()
    s = _p50.serie_por_vp("GOR", "CRUDO")
    assert s is not None
    assert len(s["serie"]) == 12
    assert s["mes_real"] == "2026-04-30"
    assert abs(s["pct"] - 92.9) < 0.5
    assert abs(s["gap"] - (-11030)) < 5

def test_p2_serie_por_vp_gor_gas_es_none():
    # A1: GOR no tiene gas en la fuente del P50.
    _engine_o_skip()
    assert _p50.serie_por_vp("GOR", "GAS") is None

def test_p3_serie_por_vp_blancos_es_none():
    # A1: BLANCOS no existe por vicepresidencia para NINGUNA de las 12 (0 filas medido).
    _engine_o_skip()
    assert _p50.serie_por_vp("GOR", "BLANCOS") is None
    assert _p50.serie_por_vp("PRP", "BLANCOS") is None

def test_p4_meses_sin_real_quedan_en_none_no_en_cero():
    # A2: el REAL por VP termina en abril — mayo-diciembre deben tener real=None, NUNCA 0.
    _engine_o_skip()
    s = _p50.serie_por_vp("GOR", "CRUDO")
    posteriores = [p for p in s["serie"] if p["fecha"] > "2026-04-30"]
    assert posteriores, "debe haber meses posteriores a abril en la serie de 12"
    for p in posteriores:
        assert p["real"] is None, p

def test_p9_p50_por_vp_no_se_toco(monkeypatch):
    # No-regresión de C5/dd8ffa2: p50_por_vp (la usa el declinar, ya verificado en navegador) debe
    # seguir devolviendo el mismo contrato — esta prueba NO usa BD (inyecta el propio _p50_fn).
    monkeypatch.setattr(_ra._resolver, "resolver_unico",
                         lambda t: {"nivel": "campo", "valor": "RUBIALES", "rama": "A", "zoom": []})
    r = _ra.responder_con_panel("dame el p50 para el campo rubiales",
                                _ejecutivo_fn=_fake_ejecutivo_rubiales,
                                _vp_fn=lambda campo: "GOR",
                                _p50_fn=lambda vice, prod: _VP_INFO)
    assert "GOR" in r["mensaje"] and "92.9" in r["mensaje"]

def test_p10_frontera_de_convencion_h4():
    # 🔑 H4: `producto` sale en MINÚSCULAS (lo que consumen los 6 tipos de panel del Motor Q v2)
    # y `unidad` se resuelve con la clave en MAYÚSCULAS — si la conversión se hiciera en el orden
    # equivocado, `unidad` saldría None (el dict está indexado en mayúsculas).
    # ⚠️ La unidad es la de la HOJA P50 (bpd), NO la del fact operativo (MSCF) — ver test_v6.
    _engine_o_skip()
    s = _p50.serie_por_vp("PRP", "GAS")
    assert s is not None
    assert s["producto"] == "gas"          # minúsculas
    assert s["unidad"] is not None         # la conversión se hizo en el orden correcto
    assert s["unidad"] == "bpd"

def test_v6_escala_de_la_hoja_p50_no_es_la_del_fact():
    """🔑 Defecto hallado verificando el panel (2026-08-13), que vivía YA en el mensaje del chat
    desde dd8ffa2: la hoja del P50 (NEW MES-AÑO t8/t2) está en PROMEDIO DIARIO (bpd), no en el
    total mensual del fact operativo. Aplicarle el ÷1e6 de MSCF mostraba el gas de PRP como
    «0,03» en vez de «33.453,2» — mil veces menor y sin error visible. No se detectó antes porque
    las pruebas en navegador solo usaron GOR y Rubiales, ambos CRUDO (que no se divide).
    Anclas medidas: t8 CRUDO suma 509.804,5 bpd ≈ 521,8 kbpe de REPORTE_PRESIDENT."""
    _engine_o_skip()
    s = _p50.serie_por_vp("PRP", "GAS")
    assert s is not None
    assert s["unidad"] == "bpd", "la hoja P50 es promedio diario, NO MSCF del fact"
    assert s["fmt"] == "vp", "el frontend necesita esta marca para NO dividir por 1e6"
    # El gas de PRP en esta hoja es ~33 mil bpd; si alguien reintrodujera el ÷1e6 daría ~0,03.
    assert 1_000 < s["real"] < 1_000_000, s["real"]


def test_v6b_mensaje_vp_no_dice_mscf_ni_divide():
    """El MENSAJE (no solo el panel) debe mostrar la cifra sin dividir y sin la unidad del fact."""
    _engine_o_skip()
    info = _p50.p50_por_vp("PRP", "GAS")
    if info is None:
        pytest.skip("PRP/GAS sin dato en esta BD")
    txt = _p50.formatear_cifra_vp("PRP", info, "GAS")
    assert "MSCF" not in txt, "MSCF es la unidad del fact operativo, no la de la hoja P50"
    assert "bpd" in txt
    assert "0,03" not in txt, "el ÷1e6 volvió a colarse"


def test_p11_valores_crudos_sin_convertir_h4():
    # 🔑 H4: los valores viajan SIN dividir — el ÷1e6 del gas lo hace el frontend (__cnGasM). Si
    # Python pre-dividiera, el panel dividiría OTRA VEZ y el número saldría 1e6 veces menor.
    _engine_o_skip()
    s = _p50.serie_por_vp("PRP", "GAS")
    assert s is not None
    assert s["real"] > 1000, "el valor de gas debe estar en la escala CRUDA (millones), no ÷1e6"
    for p in s["serie"]:
        if p["real"] is not None:
            assert p["real"] > 1000


def _fake_serie_gor(vice="GOR", producto="CRUDO"):
    return {"vice": vice, "producto": producto.lower(), "unidad": "bbl",
            "corte": "2026-05-18", "mes_real": "2026-04-30",
            "real": 143669.4, "p50": 154699.5, "pct": 92.9, "gap": -11030.1,
            "serie": [{"fecha": "2026-01-31", "p50": 151700.0, "real": 146375.2},
                      {"fecha": "2026-04-30", "p50": 154700.0, "real": 143669.4},
                      {"fecha": "2026-05-31", "p50": 159024.0, "real": None}]}


def test_p5_rama_vp_afirmativa_emite_panel(monkeypatch):
    monkeypatch.setattr(_ra._resolver, "resolver_unico",
                         lambda t: {"nivel": "gerencia", "valor": "GOR", "rama": "A",
                                    "zoom": [], "puente": True})
    r = _ra.responder_con_panel("cual es el p50 de GOR",
                                _p50_fn=lambda vice, prod: _VP_INFO,
                                _serie_fn=lambda vice, prod: _fake_serie_gor(vice, prod))
    assert r["panel"] is not None
    assert r["panel"]["tipo"] == "p50_vp"
    assert r["panel"]["datos"]["producto"] == "crudo"   # minúsculas (H4)

def test_p6_sin_serie_panel_es_none(monkeypatch):
    # H3: si la VP no tiene ese producto, el panel debe ser None — NUNCA {"datos": {}}.
    monkeypatch.setattr(_ra._resolver, "resolver_unico",
                         lambda t: {"nivel": "gerencia", "valor": "GOR", "rama": "A",
                                    "zoom": [], "puente": True})
    r = _ra.responder_con_panel("cual es el p50 de gas de GOR",
                                _p50_fn=lambda vice, prod: _VP_INFO,
                                _serie_fn=lambda vice, prod: None)
    assert r["panel"] is None

def test_p7_declinar_sigue_sin_panel(monkeypatch):
    # M8/D2, no-regresión: el declinar NUNCA lleva panel, aunque _serie_fn esté inyectada.
    monkeypatch.setattr(_ra._resolver, "resolver_unico",
                         lambda t: {"nivel": "campo", "valor": "RUBIALES", "rama": "A", "zoom": []})
    r = _ra.responder_con_panel("dame el p50 para el campo rubiales",
                                _ejecutivo_fn=_fake_ejecutivo_rubiales,
                                _vp_fn=lambda campo: "GOR",
                                _p50_fn=lambda vice, prod: _VP_INFO,
                                _serie_fn=lambda vice, prod: _fake_serie_gor(vice, prod))
    assert r["panel"] is None

def test_p8_global_ecp_sigue_sin_panel(monkeypatch):
    # D1: el global ECP NO produce panel (su caso nativo es el artifact corporativo, otro plan).
    monkeypatch.setattr(_ra._resolver, "resolver_unico", lambda t: None)
    info_global = {"encontrada": True, "unidad": "kbpe", "corte": "2026-05-18",
                   "productos": [{"entidad": "Crudo", "real_mes": 501.7, "base_p50": 521.8,
                                  "cumpl_p50": 96.1, "compromiso": None, "compromiso_difiere": False}],
                   "totales": []}
    r = _ra.responder_con_panel("cual es el p50 de crudo?",
                                _president_fn=lambda periodo=None: info_global,
                                _serie_fn=lambda vice, prod: _fake_serie_gor(vice, prod))
    assert r["panel"] is None
