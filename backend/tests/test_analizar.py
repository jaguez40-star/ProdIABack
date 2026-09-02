"""Tests de ANALIZAR (Motor Q v2 · Grupo 3 · Fases 1-3). Sub-router (puro) + plantilla con ejecutivo
FAKE (Fase 1) + diferidas con lector FAKE (Fase 2) + economia con waterfall FAKE (Fase 3) +
nivel_soportado (puro, ×2 módulos).

⚠️ Los datos de negocio (KPIs/gap/valle, impacto de diferidas, waterfall EBITDA) vienen SIEMPRE
inyectados vía _ejecutivo_fn/_diferidas_fn/_economia_fn — ninguna prueba lee Postgres/ops/SQLite para
esos datos. PERO la resolución de entidad (`resolver_unico`) y `economia.rob_fields_de` (para los
casos con `entidad=...` sin inyección de datos) sí consultan la BD de ProdIA — por eso, y por la regla
de RAM, se corre en el SERVIDOR DE PRUEBAS, no en dev.
"""
import os
os.environ.setdefault("CONSULTA_ANALIZA_LLM", "false")   # sin intro LLM en tests

from app.features.consulta_v2.analizar import subrouter as _subrouter
from app.features.consulta_v2.analizar import plantilla as _plantilla
from app.features.consulta_v2.analizar import diferidas as _diferidas_mod
from app.features.consulta_v2.analizar import economia as _economia_mod
from app.features.consulta_v2 import respuesta_analizar as _ra


# ---------------- sub-router (determinista, sin BD) ----------------

def test_sub_causal_por_que():
    assert _subrouter.sub_intencion("¿por qué está corto Cajúa?") == "causal"

def test_sub_proyeccion_como_vamos():
    assert _subrouter.sub_intencion("¿cómo vamos este mes?") == "proyeccion"

def test_sub_proyeccion_gana_a_causal():
    assert _subrouter.sub_intencion("¿vamos a cerrar el crudo?") == "proyeccion"

def test_sub_diferidas():
    assert _subrouter.sub_intencion("¿qué pasó con las diferidas?") == "diferidas"

def test_sub_economia():
    assert _subrouter.sub_intencion("¿cuál es el EBITDA de Castilla?") == "economia"


# ---------------- fakes de ejecutivo ----------------
# ⚠️ RA-1: la firma DEBE aceptar `pulir` (respuesta_analizar llama fn(..., pulir=False)).

def _fake_con_rezago(entidad=None, segmento="ecp", nivel=None, periodo=None, pulir=False):
    return {
        "entidad": entidad, "encontrada": True,
        "meta": {"scope": entidad or "Global (toda la producción ECP)", "periodo": "mayo 2026"},
        "titular": [
            {"producto": "CRUDO", "real": 8000.0, "ppto": 10000.0, "valor_pct": 80.0,
             "estado": "alert", "texto": "Foco"},
            {"producto": "GAS", "real": 5000.0, "ppto": 4900.0, "valor_pct": 102.0,
             "estado": "ok", "texto": "Alineado"},
            {"producto": "BLANCOS", "real": 300.0, "ppto": None, "valor_pct": None,
             "estado": "", "texto": "—"},
        ],
        "tarjetas": [
            {"producto": "CRUDO", "proyectado_cierre": 8000.0, "hist_prom": 7500.0},
            {"producto": "GAS", "proyectado_cierre": 5000.0, "hist_prom": 4800.0},
        ],
        "gap_por_producto": {
            "CRUDO": {"gap_kpi": -2000, "concentracion_pct": 75.0,
                      "detractores": [{"campo": "CAJUA", "gap": -1200, "real": 1000, "meta": 2200,
                                       "eventos": ["Paro por falla de equipo del 6 al 12"]},
                                      {"campo": "CPO-09", "gap": -800, "real": 500, "meta": 1300,
                                       "eventos": []}],
                      "compensadores": [], "faltante_bruto": -2000, "excedente_bruto": 0, "extremos": []},
        },
        "valle": {"desde": "2026-05-06", "hasta": "2026-05-12"},
        "pace_crudo": {"mtd": 4000, "dias": 17, "restantes": 14, "promedio_dia": 235,
                       "requerido_dia": 428, "delta_pct": 82.0},
        "flags": [
            {"tipo": "valle_activo", "severidad": "media", "activo": True,
             "desde": "2026-05-06", "hasta": "2026-05-12"},
            {"tipo": "pace_exigente", "severidad": "media", "delta_pct": 82.0,
             "requerido_dia": 428, "promedio_dia": 235, "restantes": 14},
        ],
        "comparativo_mes": {"mes_anterior": "abril 2026", "por_producto": {
            "CRUDO": {"actual": 8000.0, "anterior": 9000.0},
            "GAS": {"actual": 5000.0, "anterior": 4950.0}}},
        "secciones": None, "focos": [], "sin_foco": False,
    }


def _fake_en_meta(entidad=None, segmento="ecp", nivel=None, periodo=None, pulir=False):
    d = _fake_con_rezago(entidad, segmento, nivel, periodo)
    d["titular"][0]["valor_pct"] = 102.7; d["titular"][0]["estado"] = "ok"; d["titular"][0]["real"] = 10270.0
    d["tarjetas"][0]["proyectado_cierre"] = 10270.0
    d["gap_por_producto"] = {}       # sin rezagados
    d["valle"] = None
    return d


# ---------------- causal ----------------

def _fake_split_vacio(campos=None):
    return {"sin_datos": True, "motivo": None}


# 2026-08-13: causal() ahora TAMBIÉN llama a dif_fn (impacto_historico) para el bloque «Por qué»
# — sin inyectarlo, el default real tocaría SQLite (violaría el docstring del archivo: "ninguna
# prueba lee Postgres/ops/SQLite"). Mismo patrón que _fake_split_vacio, para impacto_historico.
def _fake_impacto_vacio(campos=None):
    return {"sin_datos": True, "motivo": None}


def test_causal_hecho_causa_accion_delta():
    # 2026-08-13: texto SIN rótulos de grupo (decisión del usuario) — HECHO/CAUSA/ACCIÓN/DELTA se
    # retiraron; el "Reporte: «evento»" también (la evidencia ahora es impacto_historico/split,
    # inyectados aparte). Se conserva el contenido que SÍ sigue en el texto nuevo.
    r = _ra.responder("¿por qué está corto Cajúa?", entidad="CAJUA",
                      _ejecutivo_fn=lambda **k: _fake_con_rezago(**k), _split_fn=_fake_split_vacio,
                      _diferidas_fn=_fake_impacto_vacio)
    assert "HECHO" not in r and "CAUSA" not in r and "ACCIÓN" not in r and "DELTA" not in r
    assert "⟦Dónde está el faltante⟧" in r
    assert "CAJUA" in r and "75" in r          # concentración

def test_causal_sin_evento_declara():
    # el 2º detractor (CPO-09) no tiene eventos; el 1º sí — el desglose por campo lista AMBOS
    # igual (ya no cita comentarios; el detalle vive en el panel derecho, no en el texto)
    r = _ra.responder("¿qué campos pesan?", entidad=None,
                      _ejecutivo_fn=lambda **k: _fake_con_rezago(**k), _split_fn=_fake_split_vacio,
                      _diferidas_fn=_fake_impacto_vacio)
    assert "CPO-09" in r


# ---------------- PERIODO (2026-08-26) ----------------
# Analizar era CIEGO al mes: pasaba periodo=None SIEMPRE, así que «analiza el crudo para el mes
# de mayo» respondía agosto (el mes vigente) y lo rotulaba como tal, sin decir que había ignorado
# lo que se le pidió. Estaba declarado en el código como fase pendiente; para quien pregunta era
# una respuesta equivocada dada con seguridad.

from app.features.consulta_v2.cuantificar import slots as _slots_mod


def test_periodo_por_token_no_por_substring():
    # "mayo" es substring de "mayor": el detector NO puede morder ahí.
    assert _slots_mod.periodo_texto("la producción de mayor volumen") is None
    assert _slots_mod.periodo_texto("el día de mayor producción") is None
    assert _slots_mod.periodo_texto("para el mes de mayo") == "mayo"

def test_periodo_llega_al_ejecutivo():
    visto = {}
    def _fake(entidad=None, segmento="ecp", nivel=None, periodo=None, pulir=False):
        visto["periodo"] = periodo
        return _fake_con_rezago(entidad=entidad, segmento=segmento, nivel=nivel,
                                periodo=periodo, pulir=pulir)
    _ra.responder("analiza el comportamiento del crudo para el mes de mayo", entidad=None,
                  _ejecutivo_fn=_fake, _split_fn=_fake_split_vacio,
                  _diferidas_fn=_fake_impacto_vacio)
    assert visto["periodo"] == "mayo"

def test_periodo_viaja_al_panel():
    # Sin esto el texto diría «Mayo» y el acordeón de al lado pintaría agosto: dos meses en la
    # misma respuesta, peor que el fallo que se corrige.
    r = _ra.responder_con_panel("analiza el crudo para el mes de mayo", entidad=None,
                                _ejecutivo_fn=lambda **k: _fake_con_rezago(**k),
                                _split_fn=_fake_split_vacio, _diferidas_fn=_fake_impacto_vacio)
    assert r["panel"]["datos"]["periodo"] == "mayo"

def test_periodo_no_honrado_se_declara():
    # El fake responde SIEMPRE "mayo 2026" en su meta (ver _fake_con_rezago); se pide un mes
    # distinto -> el aviso debe salir ANTES de las cifras, no en un pie de página.
    r = _ra.responder("analiza el crudo en diciembre", entidad=None,
                      _ejecutivo_fn=lambda **k: _fake_con_rezago(**k),
                      _split_fn=_fake_split_vacio, _diferidas_fn=_fake_impacto_vacio)
    assert "diciembre" in r.lower() and "mayo 2026" in r.lower()

def test_sin_mes_nombrado_no_avisa_nada():
    r = _ra.responder("¿por qué está corto el crudo?", entidad=None,
                      _ejecutivo_fn=lambda **k: _fake_con_rezago(**k),
                      _split_fn=_fake_split_vacio, _diferidas_fn=_fake_impacto_vacio)
    assert "Pediste" not in r


# ---------------- REGLA CERO (la prueba crítica) ----------------

def test_regla_cero_no_inventa_rezago():
    r = _ra.responder("¿por qué está corto Castilla?", entidad="CASTILLA",
                      _ejecutivo_fn=lambda **k: _fake_en_meta(**k), _split_fn=_fake_split_vacio,
                      _diferidas_fn=_fake_impacto_vacio)
    assert "no hay rezago" in r.lower()
    # nunca debe hablar de faltante/déficit cuando va en meta
    assert "faltante" not in r.lower() and "déficit" not in r.lower()


# ---------------- proyección ----------------

def test_proyeccion_pace():
    r = _ra.responder("¿cómo vamos?", entidad=None,
                      _ejecutivo_fn=lambda **k: _fake_con_rezago(**k))
    assert "PROYECCIÓN" in r and "día" in r
    assert "acelerar" in r.lower()             # delta_pct 82 > 0 → necesita acelerar


# ---------------- diferidas (Fase 2) ----------------

def _fake_diferidas_con_datos(campos=None):
    return {"sin_datos": False, "impacto": {
        "CRUDO": {"total": 5_000_000, "causas": [
            {"causa": "Formación", "vol": 1_140_000, "pct": 22.8},
            {"causa": "Falla de equipo", "vol": 945_000, "pct": 18.9},
            {"causa": "Reacondicionamiento", "vol": 700_000, "pct": 14.0}]},
        "GAS": {"total": 2_000_000, "causas": [
            {"causa": "Formación", "vol": 900_000, "pct": 45.0},
            {"causa": "Falla infraestructura", "vol": 400_000, "pct": 20.0}]},
    }}

def _fake_diferidas_sin_bd(campos=None):
    return {"sin_datos": True, "motivo": "BD de diferidas no disponible en este entorno"}

def _fake_diferidas_vacio(campos=None):
    return {"sin_datos": True, "motivo": None}


def test_diferidas_con_datos_historico_rotulado():
    r = _ra.responder("¿qué pasó con las diferidas de Cajúa?", entidad="CAJUA",
                      _diferidas_fn=_fake_diferidas_con_datos)
    assert "histórico" in r.lower() and "2023" in r and "no refleja el mes en curso" in r.lower()
    assert "Formación" in r and "22.8%" in r

def test_diferidas_sin_bd_declara_honesto():
    r = _ra.responder("¿qué pasó con las diferidas de Cajúa?", entidad="CAJUA",
                      _diferidas_fn=_fake_diferidas_sin_bd)
    assert "no tengo la base de diferidas disponible" in r.lower()
    assert "Formación" not in r   # nunca inventa causas si no hay datos

def test_diferidas_sin_resultados_declara_honesto():
    r = _ra.responder("¿qué pasó con las diferidas de Cajúa?", entidad="CAJUA",
                      _diferidas_fn=_fake_diferidas_vacio)
    assert "no encontré diferidas registradas" in r.lower()

def test_diferidas_global_sin_entidad():
    r = _ra.responder("¿qué pasó con las diferidas?", entidad=None,
                      _diferidas_fn=_fake_diferidas_con_datos)
    assert "Global (toda la producción ECP)" in r and "Formación" in r


# ---------------- diferidas · PANEL (2026-08-26) ----------------
# El panel de Diferidas existía SOLO como pestaña del acordeón de foco (sub-intención `causal`):
# preguntar directo por las diferidas de un campo devolvía texto y nada más. Estas 4 pruebas fijan
# el contrato del panel nuevo — el frontend lo consume tal cual en __cnDifPanelHtml.

def test_diferidas_emite_panel_con_scope():
    r = _ra.responder_con_panel("¿cuáles son las causas de las diferidas de Cajúa?", entidad="CAJUA",
                                _diferidas_fn=_fake_diferidas_con_datos)
    p = r["panel"]
    assert p is not None and p["tipo"] == "analiza_dif"
    # El scope viaja, NO los datos: el frontend fetchea /api/diferidas/frecuencia con su caché (A7).
    assert p["datos"]["entidad"] == "CAJUA" and p["datos"]["nivel"] == "campo"
    assert "impacto" not in p["datos"]

def test_diferidas_sin_producto_nombrado_asume_crudo():
    r = _ra.responder_con_panel("¿qué pasó con las diferidas de Cajúa?", entidad="CAJUA",
                                _diferidas_fn=_fake_diferidas_con_datos)
    assert r["panel"]["datos"]["producto"] == "CRUDO"

def test_diferidas_producto_explicito_manda():
    r = _ra.responder_con_panel("¿qué diferidas de gas hubo en Cajúa?", entidad="CAJUA",
                                _diferidas_fn=_fake_diferidas_con_datos)
    assert r["panel"]["datos"]["producto"] == "GAS"

def test_diferidas_sin_datos_no_abre_panel_vacio():
    # Mismo criterio que p50_vp (H3): sin cifra en el texto, NO se abre un bloque en la pila para
    # repetir "no tengo la base". Cubre los 2 caminos de sin_datos (BD ausente y 0 registros).
    for fake in (_fake_diferidas_sin_bd, _fake_diferidas_vacio):
        r = _ra.responder_con_panel("¿qué pasó con las diferidas de Cajúa?", entidad="CAJUA",
                                    _diferidas_fn=fake)
        assert r["panel"] is None


# ---------------- nivel_soportado (Fase 2, FC-3: puro, sin BD ni resolver) ----------------

def test_nivel_soportado_campo_activo_y_global():
    assert _diferidas_mod.nivel_soportado("campo") is True
    assert _diferidas_mod.nivel_soportado("activo") is True
    assert _diferidas_mod.nivel_soportado(None) is True          # global

def test_nivel_soportado_rechaza_gerencia_vicepresidencia():
    assert _diferidas_mod.nivel_soportado("vicepresidencia") is False
    assert _diferidas_mod.nivel_soportado("gerencia") is False
    assert _diferidas_mod.nivel_soportado("operador") is False


# ---------------- economia (Fase 3) ----------------

def _fake_waterfall(rob_fields=None):
    return {"sin_datos": False, "waterfall": {
        "components": [
            {"key": "ingresos",  "label": "Ingresos", "value_kusd": 1_196_006, "value_usd_bl": 87.3, "type": "total"},
            {"key": "ebitda",    "label": "EBITDA",   "value_kusd": 703_669,   "value_usd_bl": 51.4, "type": "total"},
            {"key": "util_oper", "label": "EBIT",     "value_kusd": 586_569,   "value_usd_bl": 42.8, "type": "total"},
            {"key": "util_neta", "label": "NOPAT",    "value_kusd": 334_325,   "value_usd_bl": 24.4, "type": "total"},
        ],
        "total_bls": 13_692_957,
        "meta": {"year": 2026, "month": 5, "nivel": "campo", "entidad": "CASTILLA", "producto": "CRUDO"},
    }}

def _fake_waterfall_sin_ops(rob_fields=None):
    return {"sin_datos": True, "motivo": "BD de rentabilidad (robustez) no disponible: ..."}


def test_economia_con_datos_rotulado_y_nivel():
    # CASTILLA resuelve a nivel='campo' (D-D5 prioridad Campo, verificado) -> debe decirlo (D-A5/EC-8).
    r = _ra.responder("¿cuál es el EBITDA de Castilla?", entidad="CASTILLA",
                      _economia_fn=_fake_waterfall)
    assert "robustez" in r.lower() and "crudo operado por ecopetrol" in r.lower()
    assert "el Campo CASTILLA" in r                 # D-A5: el NIVEL va explícito
    assert "EBITDA" in r and "703.669" in r         # kUSD es-CO
    assert "NOPAT" in r and "334.325" in r
    assert "margen" in r.lower() and "58" in r      # 703669/1196006 = 58.8%
    assert "COBERTURA PARCIAL" not in r             # campo 1:1 -> cobertura completa

def test_economia_sin_ops_declara_honesto():
    r = _ra.responder("¿cuál es el EBITDA de Castilla?", entidad="CASTILLA",
                      _economia_fn=_fake_waterfall_sin_ops)
    assert "no tengo la base de rentabilidad" in r.lower()
    assert "703" not in r     # nunca inventa cifras si no hay datos

def test_economia_tercero_declina():
    # CAÑO LIMON es tercero (es_ecp=false, rob_field NULL) -> rob_fields_de -> ([], 1) -> declina.
    # NO se inyecta _economia_fn: rob_fields_de consulta la BD real (map_campo_robustez).
    r = _ra.responder("¿cuál es el EBITDA de Caño Limón?", entidad="CAÑO LIMON")
    assert "no está en el universo de rentabilidad" in r.lower()

def test_economia_nivel_no_soportado_declina():
    # "GOR" resuelve a nivel='gerencia' (verificado contra la BD) -> declina.
    r = _ra.responder("¿cuál es el EBITDA de la vicepresidencia GOR?", entidad="GOR")
    assert "solo está disponible a nivel de campo o activo" in r.lower()


# ---------------- EC-7: cobertura parcial EN CABECERA (la prueba crítica de honestidad) ----------

def test_economia_cobertura_parcial_en_cabecera():
    """NARE (activo, verificado): 8 campos en INGESTA, solo 1 con rob_field. La cifra NO puede
    presentarse como «el EBITDA de NARE» -- debe declarar 1 de 8 y nombrar el campo incluido."""
    txt = _plantilla.economia(_fake_waterfall(), "NARE", "activo", ["NARE"], 8)
    assert "COBERTURA PARCIAL" in txt and "1 de 8" in txt
    assert "el Activo NARE" in txt                  # D-A5
    assert "de esos 1 campos" in txt                # el titular NO dice "de NARE" a secas
    # la advertencia va ANTES de las cifras (cabecera, no footnote)
    assert txt.index("COBERTURA PARCIAL") < txt.index("EBITDA:")

def test_economia_cobertura_completa_sin_aviso():
    txt = _plantilla.economia(_fake_waterfall(), "APIAY", "activo",
                              ["APIAY", "APIAY ESTE", "GAVAN", "GUATIQUIA"], 4)
    assert "COBERTURA PARCIAL" not in txt and "el Activo APIAY" in txt

def test_economia_global_rotula_universo_robustez():
    # EC-9: sin entidad, el alcance es el universo robustez, NO los 139 campos de INGESTA.
    txt = _plantilla.economia(_fake_waterfall(), None, None, [], 0)
    assert "Global · universo robustez" in txt


# ---------------- nivel_soportado economia (Fase 3, puro, sin BD) ----------------

def test_economia_nivel_soportado_puro():
    assert _economia_mod.nivel_soportado("campo") is True
    assert _economia_mod.nivel_soportado("activo") is True
    assert _economia_mod.nivel_soportado(None) is True
    assert _economia_mod.nivel_soportado("gerencia") is False
    assert _economia_mod.nivel_soportado("vicepresidencia") is False


# ---------------- 2026-08-04: split Diferidas/Mantenimiento (histórico) ----------------

def _fake_split_ok(campos=None):
    return {"sin_datos": False, "split": {
        "CRUDO": {"no_planeada": 19546432, "planeada": 6299195, "total_clasificado": 25845627,
                  "pct_no_planeada": 75.6, "dominante": "no_planeada"},
    }}

def _fake_split_planeada(campos=None):
    return {"sin_datos": False, "split": {
        "CRUDO": {"no_planeada": 2000000, "planeada": 8000000, "total_clasificado": 10000000,
                  "pct_no_planeada": 20.0, "dominante": "planeada"},
    }}


def test_plantilla_split_contexto_y_accion():
    # 2026-08-13: sin rótulo CONTEXTO ni ACCIÓN — el resumen No planeado/Planeado vive en
    # «⟦Por qué⟧», SIN marca temporal ni bbl (decisión del usuario: solo %).
    out = _plantilla.causal(_fake_con_rezago(), None, "CRUDO", _fake_split_ok())
    assert "⟦Por qué⟧" in out
    assert "75.6% corresponde a eventos no planeados" in out
    assert "24.4% a mantenimiento programado" in out
    assert "CONTEXTO ·" not in out and "ACCIÓN ·" not in out
    assert "histórico ene-2023" not in out          # la marca temporal se retiró del texto

def test_plantilla_split_dominante_planeada():
    # Con dominante=planeada el resumen sigue siendo el mismo par de porcentajes (ya no hay
    # cláusula "mantenimiento previsto" — esa vivía en la ACCIÓN, retirada).
    out = _plantilla.causal(_fake_con_rezago(), None, "CRUDO", _fake_split_planeada())
    assert "20.0% corresponde a eventos no planeados" in out
    assert "80.0% a mantenimiento programado" in out

def test_plantilla_split_ausente_no_rompe():
    """Sin split NI impacto: el bloque «⟦Por qué⟧» se OMITE entero (regla N5: nunca se fabrica)."""
    assert "⟦Por qué⟧" not in _plantilla.causal(_fake_con_rezago(), None, "CRUDO", None)
    assert "⟦Por qué⟧" not in _plantilla.causal(_fake_con_rezago(), None, "CRUDO", _fake_split_vacio())

def test_responder_causal_inyecta_split():
    """responder() con _split_fn FAKE -> el resumen histórico llega a la respuesta (sin rótulo)."""
    out = _ra.responder("cual es la causa del gap de crudo?", entidad=None,
                        _ejecutivo_fn=_fake_con_rezago, _split_fn=_fake_split_ok,
                        _diferidas_fn=_fake_impacto_vacio)
    assert "⟦Por qué⟧" in out
    assert "no planeados" in out


# ---------------- iniciativa (⟦Ojo con esto⟧, 2026-09-01) ----------------

def _fake_flags_todos():
    d = _fake_con_rezago()
    d["flags"] = [
        {"tipo": "producto_critico", "severidad": "alta", "producto": "CRUDO", "pct": 55.0},
        {"tipo": "gap_concentrado", "severidad": "media", "producto": "CRUDO",
         "concentracion_pct": 75.0, "campos": ["CAJUA", "CPO-09"]},
        {"tipo": "valle_activo", "severidad": "media", "activo": True,
         "desde": "2026-05-06", "hasta": "2026-05-12"},
        {"tipo": "pace_exigente", "severidad": "media", "delta_pct": 82.0,
         "requerido_dia": 428, "promedio_dia": 235, "restantes": 14},
    ]
    return d


def test_iniciativa_valle_activo_dice_estado():
    out = _plantilla.causal(_fake_con_rezago(), None, "CRUDO", _fake_split_vacio(), _fake_impacto_vacio())
    assert "⟦Ojo con esto⟧" in out
    assert "sigue abierto" in out
    # dedupe: la apertura ya dijo las fechas; el bloque no las repite
    assert out.count("6 de mayo") == 1


def test_iniciativa_valle_recuperado():
    d = _fake_con_rezago()
    d["flags"][0]["activo"] = False
    out = _plantilla.causal(d, None, "CRUDO", _fake_split_vacio(), _fake_impacto_vacio())
    assert "ya se recuperó" in out and "sigue abierto" not in out


def test_iniciativa_comparativo_mes_anterior():
    out = _plantilla.causal(_fake_con_rezago(), None, "CRUDO", _fake_split_vacio(), _fake_impacto_vacio())
    assert "abril 2026" in out and "bajó" in out          # 8000 vs 9000 = −11.1%
    assert "subió" not in out                              # GAS varía 1% < umbral 5%: no se emite


def test_iniciativa_regla_cero_emite_sin_contaminar():
    # _fake_en_meta HEREDA los flags de _fake_con_rezago: la REGLA CERO recibe el bloque y
    # el vocabulario sigue limpio. Complemento activo de test_regla_cero_no_inventa_rezago.
    r = _ra.responder("¿por qué está corto Castilla?", entidad="CASTILLA",
                      _ejecutivo_fn=lambda **k: _fake_en_meta(**k), _split_fn=_fake_split_vacio,
                      _diferidas_fn=_fake_impacto_vacio)
    assert "no hay rezago" in r.lower()
    assert "faltante" not in r.lower() and "déficit" not in r.lower()
    assert "⟦Ojo con esto⟧" in r


def test_iniciativa_sin_material_no_emite():
    d = _fake_con_rezago()
    d["flags"] = []; d["comparativo_mes"] = None
    out = _plantilla.causal(d, None, "CRUDO", _fake_split_vacio(), _fake_impacto_vacio())
    assert "⟦Ojo con esto⟧" not in out


def test_iniciativa_sin_tokens_prohibidos():
    out = _plantilla.causal(_fake_flags_todos(), None, "CRUDO", _fake_split_vacio(), _fake_impacto_vacio())
    ini = out[out.index("⟦Ojo con esto⟧"):]
    for tok in ("HECHO", "CAUSA", "ACCIÓN", "DELTA", "Pediste", "Formación",
                "COBERTURA PARCIAL", "CONTEXTO ·", "ACCIÓN ·", "histórico ene-2023"):
        assert tok not in ini
    for tok in ("faltante", "déficit"):
        assert tok not in ini.lower()
    assert "?" not in ini                                  # H6: el bloque solo afirma


def test_iniciativa_tope_tres_lineas():
    out = _plantilla.causal(_fake_flags_todos(), None, "CRUDO", _fake_split_vacio(), _fake_impacto_vacio())
    ini = out[out.index("⟦Ojo con esto⟧"):]
    assert sum(1 for l in ini.split("\n") if l.startswith("  · ")) <= 3


def test_iniciativa_flags_malformados_no_rompen():
    d = _fake_con_rezago()
    d["flags"] = [{"tipo": "producto_critico"}, {"tipo": "desconocido_futuro"}, None, "basura"]
    d["comparativo_mes"] = {"mes_anterior": "abril 2026", "por_producto": {"CRUDO": None}}
    out = _plantilla.causal(d, None, "CRUDO", _fake_split_vacio(), _fake_impacto_vacio())
    assert isinstance(out, str)                            # no lanza; degrada


def test_iniciativa_solo_en_causal():
    # "¿cómo vamos este mes?" -> sub_intencion "proyeccion" (mismo texto que
    # test_sub_proyeccion_como_vamos). plantilla.proyeccion() nunca llama a
    # _iniciativa_bloque — solo causal() lo hace — así que el bloque no debe aparecer.
    assert _subrouter.sub_intencion("¿cómo vamos este mes?") == "proyeccion"
    r = _ra.responder("¿cómo vamos este mes?", entidad=None,
                      _ejecutivo_fn=lambda **k: _fake_con_rezago(**k), _split_fn=_fake_split_vacio,
                      _diferidas_fn=_fake_impacto_vacio)
    assert "⟦Ojo con esto⟧" not in r
