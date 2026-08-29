"""Tests puros de las tarjetas KPI de cierre (plan_tarjetas_kpi_cierre_2026-07-21).
No tocan BD ni LLM."""
from app.features.analisis.api import _tarjetas_kpi, _estado_cierre, _UNIDADES_PRODUCTO, _focos


def _t(producto, real, ppto):
    return {"producto": producto, "real": real, "ppto": ppto, "valor_pct": None, "estado": "", "texto": ""}


def test_alineado_cuando_supera_meta():
    assert _estado_cierre(120, 100) == "alineado"


def test_ajustado_en_la_banda_ambar():
    assert _estado_cierre(95, 100) == "ajustado"   # 95% >= umbral 93%
    assert _estado_cierre(93, 100) == "ajustado"


def test_actuar_bajo_el_umbral_ambar():
    assert _estado_cierre(92.9, 100) == "actuar"
    assert _estado_cierre(50.7, 100) == "actuar"    # caso real APIAY


def test_sin_meta_no_es_actuar():
    """Meta 0 (producto sin PPTO/PROGRAMA) NO debe leerse como 'actuar' (rojo) -- neutral."""
    assert _estado_cierre(500, 0) == ""


def test_no_divergencia_proyectado_cierre_es_titular_real():
    titular = [_t("CRUDO", 12357703, 12928000)]
    tarjetas = _tarjetas_kpi(titular)
    assert tarjetas[0]["proyectado_cierre"] == titular[0]["real"]
    assert tarjetas[0]["meta_mes"] == titular[0]["ppto"]


def test_relleno_topa_en_100_sin_desbordar():
    titular = [_t("CRUDO", 150, 100)]
    t = _tarjetas_kpi(titular)[0]
    assert t["relleno_pct"] == 100.0
    assert t["alcanza"] is True
    assert t["brecha_abs"] == -50   # meta - proy, negativo = excedente


def test_unidad_por_producto():
    titular = [_t("CRUDO", 1, 1), _t("GAS", 1, 1), _t("BLANCOS", 1, 1)]
    tarjetas = _tarjetas_kpi(titular)
    by = {t["producto"]: t for t in tarjetas}
    assert by["CRUDO"]["unidad"] == "bbl"
    assert by["BLANCOS"]["unidad"] == "bbl"
    assert by["GAS"]["unidad"] == "MSCF"   # decisión usuario 2026-07-21; NUNCA "bbl" para Gas


def test_producto_sin_meta_no_fabrica_cumplimiento():
    titular = [_t("GAS", 500, 0)]
    t = _tarjetas_kpi(titular)[0]
    assert t["alcanza"] is False
    assert t["estado"] == ""
    assert t["relleno_pct"] == 0.0


def test_bopd_por_producto_reconcilia():
    """El ritmo diario (bopd) se adjunta a los productos que traen pace (curva diaria que
    reconcilia con el mensual: Crudo, Gas); el que no lo trae (Blancos, diario ~2x el mes) = None."""
    titular = [_t("CRUDO", 100, 120), _t("GAS", 50, 60), _t("BLANCOS", 10, 20)]
    pace = {"CRUDO": {"promedio_dia": 2850000, "requerido_dia": 3230000, "delta_pct": 13.4},
            "GAS": {"promedio_dia": 2340000, "requerido_dia": 3080000, "delta_pct": 31.6}}
    by = {t["producto"]: t for t in _tarjetas_kpi(titular, pace)}
    assert by["CRUDO"]["bopd"] == {"real": 2850000, "requerido": 3230000, "delta_pct": 13.4}
    assert by["GAS"]["bopd"] == {"real": 2340000, "requerido": 3080000, "delta_pct": 31.6}
    assert by["BLANCOS"]["bopd"] is None   # sin pace -> no reconcilia -> sin ritmo diario


def test_bopd_none_sin_pace():
    """Sin pace (mes cerrado o sin curva) -> la tarjeta cae solo a la proyección mensual."""
    assert _tarjetas_kpi([_t("CRUDO", 100, 120)])[0]["bopd"] is None
    assert _tarjetas_kpi([_t("CRUDO", 100, 120)], None)[0]["bopd"] is None


def test_hist_prom_se_adjunta():
    """El promedio del año (meses previos con REAL) se adjunta por producto (para Blancos)."""
    by = {t["producto"]: t for t in _tarjetas_kpi([_t("BLANCOS", 618914, 1057263)],
                                                   None, {"BLANCOS": 828212})}
    assert by["BLANCOS"]["hist_prom"] == 828212


def test_hist_prom_none_sin_historico():
    assert _tarjetas_kpi([_t("BLANCOS", 1, 1)])[0]["hist_prom"] is None


def test_fallback_sin_ppto_usa_promedio_del_anio():
    """Entidad SIN PPTO (meta=0) pero con promedio del año -> ese promedio pasa a ser la meta de
    cierre (evita 'Sin meta definida'). Caso real: campo CUSIANA sin presupuesto propio."""
    t = _tarjetas_kpi([_t("CRUDO", 6300, 0)], None, {"CRUDO": 6000})[0]
    assert t["meta_de_promedio"] is True
    assert t["meta_mes"] == 6000.0
    assert t["alcanza"] is True                 # 6300 proyectado >= 6000 promedio
    assert t["estado"] == "alineado"
    assert t["relleno_pct"] == 100.0


def test_sin_ppto_y_sin_promedio_sigue_sin_meta():
    """Sin PPTO y sin histórico -> NO se inventa meta (sigue neutral, 'Sin meta definida')."""
    t = _tarjetas_kpi([_t("GAS", 500, 0)], None, None)[0]
    assert t["meta_de_promedio"] is False
    assert t["meta_mes"] == 0.0
    assert t["estado"] == ""


def test_foco_por_promedio_cuando_no_hay_ppto():
    """Entidad SIN PPTO: si un producto proyecta por debajo de su promedio del año, ES un foco
    (caso real: GAS de CUSIANA al 80% de su promedio). El producto por encima NO genera foco."""
    titular = [{"producto": "GAS", "real": 2631705, "ppto": 0, "valor_pct": None},
               {"producto": "CRUDO", "real": 6000, "ppto": 0, "valor_pct": None}]
    tarjetas = _tarjetas_kpi(titular, None, {"GAS": 3305551, "CRUDO": 5676})
    focos = _focos(titular, {}, None, [], tarjetas)
    gas = [f for f in focos if f["producto"] == "GAS"]
    assert gas and gas[0]["tipo"] == "promedio"
    assert "por debajo de su promedio" in gas[0]["titulo"]
    assert not [f for f in focos if f["producto"] == "CRUDO"]   # crudo por encima -> sin foco


def test_sin_tarjetas_no_genera_focos_de_promedio():
    """Compatibilidad: sin el argumento tarjetas, _focos se comporta como antes (solo gap/valle)."""
    titular = [{"producto": "GAS", "real": 100, "ppto": 0, "valor_pct": None}]
    assert _focos(titular, {}, None, []) == []
