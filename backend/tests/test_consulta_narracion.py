"""Tests de la narración en 2 etapas: Python borronea, el LLM reescribe (2026-07-16).

Antes el LLM componía la prosa desde el JSON del payload con temperature=0. Resultado: siempre el
mismo esqueleto, con las CLAVES del esquema filtradas a la frase ("el producto CRUDO reportó un
volumen de", "su clasificación es Alineado"). Ahora Python escribe un borrador correcto —con la
DIRECCIÓN ya resuelta— y el LLM solo lo reescribe con temperature>0.

Todo aquí es función pura: no toca LLM ni BD.
"""
import pytest

from app.features.consulta.narracion import (
    _borrador, _direccion, _payload, _cumple_direccion, _cumple_regla_numerica, _cumple_nivel,
    _cumple_proyeccion,
)

CASTILLA = {
    "aplica": True, "entidad": "CASTILLA", "nivel": "campo",
    "entidad_cualificada": "el Campo CASTILLA",
    "mes": {"nombre": "Mayo", "anio": 2026, "dias_con_data": 17, "dias_del_mes": 31, "completo": False},
    "lineas": [
        {"producto": "CRUDO", "real": 6860389.4572, "cumplimiento": 102.7, "estado": "Alineado"},
        {"producto": "GAS", "real": 0.0, "cumplimiento": None, "estado": ""},
        {"producto": "BLANCOS", "real": 0.0, "cumplimiento": None, "estado": ""},
    ],
    "pie": "Calculado sobre 17 días con reporte.",
}

APIAY_CAMPO = {
    "aplica": True, "entidad": "APIAY", "nivel": "campo",
    "entidad_cualificada": "el Campo APIAY",
    "mes": {"nombre": "Mayo", "anio": 2026, "dias_con_data": 17, "dias_del_mes": 31, "completo": False},
    "lineas": [{"producto": "CRUDO", "real": 269035.0, "cumplimiento": 50.7, "estado": "Foco"}],
    "pie": "Calculado sobre 17 días con reporte.",
}

# Direcciones MIXTAS (CRUDO por encima, BLANCOS por debajo): el chequeo direccional debe abstenerse.
APIAY_ACTIVO = {
    "aplica": True, "entidad": "APIAY", "nivel": "activo",
    "entidad_cualificada": "el Activo APIAY",
    "mes": {"nombre": "Mayo", "anio": 2026, "dias_con_data": 17, "dias_del_mes": 31, "completo": False},
    "lineas": [
        {"producto": "CRUDO", "real": 577361.89, "cumplimiento": 108.8, "estado": "Alineado"},
        {"producto": "BLANCOS", "real": 6501.94, "cumplimiento": 85.2, "estado": "Rezagado"},
    ],
    "pie": "Calculado sobre 17 días con reporte.",
}


# ---------- _direccion: Python resuelve el sentido, el LLM no lo infiere ----------

@pytest.mark.parametrize("pct, esperado", [
    (102.7, "por encima de la meta"),
    (100.0, "por encima de la meta"),   # 100% exacto = en meta, no es rezago
    (99.9, "por debajo de la meta"),
    (50.7, "por debajo de la meta"),
    (None, None),
])
def test_direccion(pct, esperado):
    assert _direccion(pct) == esperado


# ---------- El borrador: correcto, completo y sin lenguaje de formulario ----------

def test_borrador_lleva_las_cifras_exactas():
    b = _borrador(CASTILLA, "Javier")
    assert "6.860.389" in b and "102.7%" in b


def test_borrador_lleva_la_direccion_escrita():
    """El punto del rediseño: el modelo NO tiene que deducir si 102.7% supera la meta."""
    assert "por encima de la meta" in _borrador(CASTILLA, "Javier")
    assert "por debajo de la meta" in _borrador(APIAY_CAMPO, "Javier")


def test_borrador_cualifica_el_nivel():
    """D-A5: APIAY como Campo y como Activo son cifras distintas; el nivel debe ir en la prosa."""
    assert "el Campo APIAY" in _borrador(APIAY_CAMPO, "Javier")
    assert "el Activo APIAY" in _borrador(APIAY_ACTIVO, "Javier")


def test_borrador_declara_productos_sin_meta_agrupados():
    b = _borrador(CASTILLA, "Javier")
    assert "GAS y BLANCOS no tienen meta definida" in b
    b2 = _borrador(APIAY_ACTIVO, "Javier")   # aquí solo BLANCOS tiene meta y GAS no viene
    assert "no tiene meta" not in b2 or "GAS" not in b2


def test_borrador_saluda_y_capitaliza_sin_usuario():
    assert _borrador(CASTILLA, "Javier").startswith("Javier, la producción del Campo CASTILLA")
    assert _borrador(CASTILLA, None).startswith("La producción del Campo CASTILLA")


def test_borrador_multiproducto_incluye_todos():
    b = _borrador(APIAY_ACTIVO, "Javier")
    assert "577.362" in b and "108.8%" in b
    assert "6.502" in b and "85.2%" in b


def test_borrador_pasa_sus_propias_salvaguardas():
    """El borrador es el FALLBACK: si él mismo violara D-N5/D-N6 el fallback sería inválido."""
    for r in (CASTILLA, APIAY_CAMPO, APIAY_ACTIVO):
        p = _payload(r, "Javier")
        b = _borrador(r, "Javier")
        ok_num, motivo = _cumple_regla_numerica(b, p)
        assert ok_num, motivo
        ok_dir, motivo = _cumple_direccion(b, p)
        assert ok_dir, motivo


# ---------- D-N6: el chequeo direccional ----------

def test_direccion_atrapa_la_inversion():
    """El error que D-N5 dejaba pasar: cifras correctas, sentido invertido."""
    p = _payload(CASTILLA, "Javier")
    malo = ("Javier, el Campo CASTILLA lleva 6.860.389 barriles de CRUDO, un 102.7% del "
            "presupuesto, con un déficit frente a la meta.")
    ok, motivo = _cumple_regla_numerica(malo, p)
    assert ok, "las cifras están bien: D-N5 no puede atrapar esto"
    ok, motivo = _cumple_direccion(malo, p)
    assert not ok and "por encima" in motivo


def test_direccion_atrapa_la_inversion_contraria():
    p = _payload(APIAY_CAMPO, "Javier")
    malo = ("Javier, el Campo APIAY lleva 269.035 barriles de CRUDO, un 50.7% del presupuesto, "
            "superando la meta.")
    ok, _ = _cumple_direccion(malo, p)
    assert not ok


def test_direccion_acepta_la_prosa_correcta():
    p = _payload(CASTILLA, "Javier")
    bueno = ("Javier, el Campo CASTILLA acumula 6.860.389 barriles de CRUDO: 102.7% del "
             "presupuesto, por encima de la meta y clasificado como Alineado.")
    ok, _ = _cumple_direccion(bueno, p)
    assert ok


def test_direccion_se_abstiene_con_productos_mixtos():
    """CRUDO arriba y BLANCOS abajo: no se puede atribuir la palabra a un producto sin parsear.
    Abstenerse es deliberado — un falso positivo costaría una narración buena."""
    p = _payload(APIAY_ACTIVO, "Javier")
    mixto = ("El Activo APIAY va por encima de la meta en CRUDO con 577.362 barriles (108.8%), "
             "pero BLANCOS queda por debajo con 6.502 (85.2%).")
    ok, _ = _cumple_direccion(mixto, p)
    assert ok


def test_direccion_sin_productos_con_meta_no_bloquea():
    sin = {"lineas": [{"producto": "GAS", "real": 0.0, "cumplimiento": None, "estado": ""}],
           "entidad": "X", "mes": {}}
    ok, _ = _cumple_direccion("cualquier cosa por debajo y por encima", _payload(sin, None))
    assert ok


# ---------- D-A5: la prosa debe cualificar el nivel, también bajo temperatura ----------

def test_nivel_atrapa_al_modelo_que_se_come_el_cualificador():
    """Caso REAL observado con qwen a 0.7. Sin 'el Campo', APIAY-Campo (269.035, Foco) y
    APIAY-Activo (577.362, Alineado) son indistinguibles en la burbuja."""
    p = _payload(CASTILLA, "Javier")
    malo = "Javier, CASTILLA lleva 6.860.389 barriles de CRUDO, un 102.7% del presupuesto."
    ok, motivo = _cumple_regla_numerica(malo, p)
    assert ok, "las cifras están bien: D-N5 no lo atrapa"
    ok, motivo = _cumple_nivel(malo, p)
    assert not ok and "el Campo CASTILLA" in motivo


def test_nivel_acepta_cualquier_capitalizacion():
    p = _payload(APIAY_ACTIVO, "Javier")
    ok, _ = _cumple_nivel("El activo apiay acumula 577.362 barriles.", p)
    assert ok


def test_nivel_distingue_campo_de_activo():
    """Decir 'el Campo APIAY' cuando la cifra es la del Activo debe rechazarse."""
    p = _payload(APIAY_ACTIVO, "Javier")
    ok, _ = _cumple_nivel("Javier, el Campo APIAY produjo 577.362 barriles.", p)
    assert not ok


def test_nivel_sin_cualificador_no_bloquea():
    """Si ejecutar() no pudo cualificar el nivel, no hay nada que exigir."""
    r = dict(APIAY_CAMPO, entidad_cualificada="APIAY")
    ok, _ = _cumple_nivel("APIAY va en 50.7%.", _payload(r, None))
    assert ok


# ---------- D-N7: una proyección no puede narrarse como cifra cerrada (2026-07-16) ----------
#
# La cifra REAL del mes en curso es de MES COMPLETO (estimado de cierre), no el acumulado. AKACIAS
# "va camino de" 3.720.510 pero lleva 1.916.317 reales en 17 de 31 días. Narrarlo como "cerró con
# 3.720.510" es falso, y D-N5 no lo atrapa: la cifra estaría literal.

AKACIAS_PROY = {
    "aplica": True, "entidad": "AKACIAS", "nivel": "campo",
    "entidad_cualificada": "el Campo AKACIAS", "proyeccion": True,
    "mes": {"nombre": "Mayo", "anio": 2026, "dias_con_data": 17, "dias_del_mes": 31, "completo": False},
    "lineas": [{"producto": "CRUDO", "real": 3720510.0, "cumplimiento": 78.5, "estado": "Rezagado"}],
    "pie": "Proyección del cierre del mes: la cifra es del mes completo y el reporte lleva 17 de 31 días con curva diaria.",
}
AKACIAS_CERRADO = dict(AKACIAS_PROY, proyeccion=False,
                       mes=dict(AKACIAS_PROY["mes"], dias_con_data=31, completo=True))


def test_borrador_de_proyeccion_no_la_narra_como_cerrada():
    """El verbo lo pone Python: con la cifra estimada, 'produjo'/'cerró con' serían falsos.
    Sin `mtd` (p. ej. sin curva diaria) cae a la forma corta 'va camino de cerrar'."""
    b = _borrador(AKACIAS_PROY, "Javier")
    assert "va camino de cerrar" in b
    assert "produjo" not in b and "cerró con" not in b


def test_borrador_de_mes_cerrado_no_proyecta():
    """Mes cerrado: la cifra ES lo producido → ni proyección ni acotación a días parciales."""
    b = _borrador(AKACIAS_CERRADO, "Javier")
    assert "fue de 3.720.510 barriles" in b
    assert "va camino de cerrar" not in b and "proyecta al mes" not in b


@pytest.mark.parametrize("malo", [
    "Javier, el Campo AKACIAS cerró con 3.720.510 barriles de CRUDO, un 78.5% del presupuesto.",
    "Javier, el Campo AKACIAS produjo 3.720.510 barriles de CRUDO: 78.5% del presupuesto.",
    "El Campo AKACIAS ha producido 3.720.510 barriles (78.5%).",
])
def test_proyeccion_atrapa_la_cifra_vendida_como_cerrada(malo):
    p = _payload(AKACIAS_PROY, "Javier")
    ok, _ = _cumple_regla_numerica(malo, p)
    assert ok, "la cifra está literal: D-N5 no puede atrapar esto"
    ok, motivo = _cumple_proyeccion(malo, AKACIAS_PROY)
    assert not ok and "proyección" in motivo


def test_proyeccion_acepta_el_futuro():
    bueno = ("Javier, el Campo AKACIAS va camino de cerrar Mayo 2026 en 3.720.510 barriles de CRUDO: "
             "un 78.5% del presupuesto, por debajo de la meta.")
    ok, _ = _cumple_proyeccion(bueno, AKACIAS_PROY)
    assert ok


def test_mes_cerrado_puede_decir_produjo():
    """La salvaguarda SOLO aplica a proyecciones: con el mes cerrado, 'produjo' es correcto."""
    ok, _ = _cumple_proyeccion("El Campo AKACIAS produjo 3.720.510 barriles.", AKACIAS_CERRADO)
    assert ok


def test_el_borrador_de_proyeccion_pasa_su_propia_salvaguarda():
    """El borrador es el fallback: si él mismo violara D-N7, el fallback sería inválido."""
    ok, motivo = _cumple_proyeccion(_borrador(AKACIAS_PROY, "Javier"), AKACIAS_PROY)
    assert ok, motivo


# ---------- Estructura observado → proyección → % de la meta (2026-07-16) ----------
#
# Pedida por el usuario: "La producción del Campo Akacias, para los 17 días de operación del mes
# reporta X (Y BOPD-avg), proyectado al mes serían Z BLS, lo que lo ubicaría en un W% de la meta
# propuesta (M BLS)". Lidera con lo OBSERVADO; antes se abría con la cifra proyectada y lo realmente
# producido no aparecía, así que el lector no tenía con qué juzgarla.

from app.features.consulta.ejecucion import _mtd_bopd

AKACIAS_BOPD = dict(AKACIAS_PROY, lineas=[
    dict(AKACIAS_PROY["lineas"][0], ppto=4741721.0, mtd=1916317, bopd_avg=112725)])


def test_mtd_bopd_es_suma_y_media_de_la_curva():
    """Verificado contra la BD: AKACIAS mayo 2026 = 1.916.317 / 17 días = 112.725."""
    vals = [115527.24, 119710.4, 123617.92]
    mtd, bopd = _mtd_bopd({"series": {"CRUDO": vals}}, "CRUDO")
    assert mtd == round(sum(vals)) and bopd == round(sum(vals) / 3)


def test_mtd_bopd_solo_para_crudo():
    """🔑 Para BLANCOS la curva diaria y el hecho mensual NO reconcilian (APIAY-activo: MTD 13.965 >
    REAL del mes 6.502 — imposible). Mientras no se explique, no se ponen en la misma frase."""
    curva = {"series": {"BLANCOS": [554.7, 594.2], "GAS": [10.0, 12.0]}}
    assert _mtd_bopd(curva, "BLANCOS") == (None, None)
    assert _mtd_bopd(curva, "GAS") == (None, None)


def test_mtd_bopd_sin_curva_es_none():
    """Filiales y vicepresidencias no tienen grano diario → no se inventa un ritmo."""
    assert _mtd_bopd(None, "CRUDO") == (None, None)
    assert _mtd_bopd({"series": {"CRUDO": []}}, "CRUDO") == (None, None)


def test_borrador_lidera_con_lo_observado():
    b = _borrador(AKACIAS_BOPD, "Javier")
    assert "para los 17 días de operación del mes, reporta 1.916.317 barriles" in b
    assert "112.725 BOPD-avg" in b
    # el observado va ANTES que la proyección
    assert b.index("1.916.317") < b.index("3.720.510")


def test_borrador_atribuye_la_proyeccion_al_reporte():
    """No la calcula Python: 112.725 x 31 = 3.494.460 ≠ 3.720.510. Decir 'el reporte la proyecta'
    evita que el lector crea que las dos cifras deberían cuadrar entre sí."""
    b = _borrador(AKACIAS_BOPD, "Javier")
    assert "El reporte la proyecta al mes en 3.720.510 barriles" in b


def test_borrador_nombra_la_meta_en_barriles():
    """'78.5%' a secas no dice de qué; con la meta se ve el tamaño del hueco."""
    assert "un 78.5% de la meta propuesta (4.741.721 barriles)" in _borrador(AKACIAS_BOPD, "Javier")


def test_borrador_contrae_de_el_a_del():
    assert "la producción del Campo AKACIAS" in _borrador(AKACIAS_BOPD, "Javier")
    assert "de el Campo" not in _borrador(AKACIAS_BOPD, "Javier")


def test_borrador_no_repite_el_pie():
    """Con la estructura completa, el pie diría otra vez los 17/31 días y la proyección."""
    b = _borrador(AKACIAS_BOPD, "Javier")
    assert "Proyección del cierre del mes:" not in b


def test_cifras_nuevas_protegidas_por_la_regla_numerica():
    """Acumulado, ritmo y meta: el lector no puede verificarlos de cabeza → D-N5 los trata como
    cifras, igual que el volumen."""
    p = _payload(AKACIAS_BOPD, "Javier")
    pr = p["productos"][0]
    assert (pr["acumulado_dias_con_reporte"], pr["ritmo_diario"], pr["meta"]) == \
           ("1.916.317", "112.725", "4.741.721")
    base = ("Javier, la producción del Campo AKACIAS, para los 17 días, reporta {mtd} barriles "
            "({bopd} BOPD-avg). El reporte la proyecta al mes en 3.720.510 barriles: un 78.5% de la "
            "meta propuesta ({meta} barriles).")
    ok, _ = _cumple_regla_numerica(
        base.format(mtd="1.916.317", bopd="112.725", meta="4.741.721"), p)
    assert ok
    for campo, alterado in (("mtd", "1.900.000"), ("bopd", "113.000"), ("meta", "4.700.000")):
        kw = {"mtd": "1.916.317", "bopd": "112.725", "meta": "4.741.721", campo: alterado}
        ok, motivo = _cumple_regla_numerica(base.format(**kw), p)
        assert not ok, f"D-N5 dejó pasar {campo} alterado"
