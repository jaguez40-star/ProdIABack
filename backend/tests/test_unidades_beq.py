"""tests/test_unidades_beq.py — blinda el contrato de unidades (plan v2).

Cifras de referencia medidas contra la BD local (reporte 148) y la lamina
"Produccion Equivalente G.E. 2026" (§1 H1-H6 del plan).
"""
import pytest

from app.core import unidades as u


def test_factor_gas_es_5_7():
    assert u.FACTOR_GAS_BEQ == 5.7


def test_bpd_m_entre_bpdeq_m_es_el_factor():
    """Medido en fact_produccion_mes_ecp abril 2026: bpd_m 516,9 / bpdeq_m 90,7."""
    assert 516.9 / 90.7 == pytest.approx(5.7, abs=0.01)


def test_a_beq_gas_si_crudo_blancos_no():
    assert u.a_beq(570.0, "GAS") == pytest.approx(100.0)
    assert u.a_beq(570.0, "gas") == pytest.approx(100.0)
    assert u.a_beq(570.0, "CRUDO") == pytest.approx(570.0)
    assert u.a_beq(570.0, "BLANCOS") == pytest.approx(570.0)
    assert u.a_beq(None, "GAS") is None


def test_kboepd_mes_solo_escala():
    """bpdeq_m ya es equivalente: solo /1000."""
    assert u.kboepd_mes(492_450.0) == pytest.approx(492.45)
    assert u.kboepd_mes(None) is None


def test_kboepd_dia_convierte_y_escala():
    # gas: 459_420 bpd brutos de un dia -> /5.7 /1000 = 80.6
    assert u.kboepd_dia(459_420.0, "GAS") == pytest.approx(80.6, abs=0.01)
    assert u.kboepd_dia(498_900.0, "CRUDO") == pytest.approx(498.9)


def test_unidad_por_producto_no_mscf():
    """Liquidos en kbopd, gas en kbepd. Revierte la decision del 2026-07-21 (D3).

    Los liquidos NO son "equivalentes": solo el gas se convierte con el 5,7.
    """
    assert u.UNIDADES_PRODUCTO == {"CRUDO": "kbopd", "GAS": "kbepd", "BLANCOS": "kbopd"}
    assert u.unidad_de("CRUDO") == "kbopd"
    assert u.unidad_de("BLANCOS") == "kbopd"
    assert u.unidad_de("GAS") == "kbepd"
    assert u.unidad_de("gas") == "kbepd"          # acepta minuscula
    assert "MSCF" not in u.UNIDADES_PRODUCTO.values()
    assert u.UNIDAD_ACUM == "kbbl-eq"
    assert u.UNIDAD_DIF == "bbl-eq"


def test_conceptos_y_proceso():
    assert u.CONCEPTOS_SUMABLES == ("DERECO", "PROPIEDAD", "REGALIADISP")
    assert "MONETIZACION" not in u.CONCEPTOS_SUMABLES
    assert u.PROCESO_GAS == "VENTA-GRAVABLE"
    assert "VENTA-GRAVABLE" in u.SQL_PROCESO_GAS and "<> 'GAS'" in u.SQL_PROCESO_GAS


def test_formato_es_co():
    assert u.fmt(492.45) == "492,5"
    assert u.fmt(80.6) == "80,6"
    assert u.fmt(0.2) == "0,2"
    assert u.fmt(52430.9) == "52.430,9"
    assert u.fmt(-17.8) == "-17,8"


def test_acumulado_feb_abr_2026():
    """calendar.md §4: kboepd x dias. Medido: 52.430,9 kbbl-eq."""
    meses = [(591.0, 28), (593.4, 31), (582.9, 30)]
    assert sum(v * d for v, d in meses) == pytest.approx(52430.9, rel=1e-4)


def test_lamina_abril_2026():
    """Oraculo: DATOS_MES REAL abril = lamina = 582,9 kboepd."""
    assert 492.4 + 76.7 + 13.8 == pytest.approx(582.9, abs=0.05)


# ---------------------------------------------------------------------------------------------
# Oraculo contra la BD: la formula del plan reproduce DATOS_MES. Se salta si no hay conexion.
# ---------------------------------------------------------------------------------------------
def _bd():
    try:
        import sqlalchemy as sa
        from app.core.db import get_engine
        c = get_engine().connect()
        c.execute(sa.text("select 1"))
        return c
    except Exception:
        return None


@pytest.mark.skipif(_bd() is None, reason="sin BD")
def test_oraculo_fact_mes_vs_datos_mes():
    import sqlalchemy as sa
    c = _bd()
    rid = c.execute(sa.text("select max(reporte_id) from core.fact_tabla_hoja where hoja='DATOS_MES'")).scalar()
    if rid is None:
        pytest.skip("sin DATOS_MES cargada")
    ref = {r[0]: float(r[1]) / 1000 for r in c.execute(sa.text("""
        select dims->>'producto', sum(valor) from core.fact_tabla_hoja
        where hoja='DATOS_MES' and reporte_id=:r and dims->>'escenario'='REAL'
          and fecha=(select max(fecha) from core.fact_tabla_hoja
                     where hoja='DATOS_MES' and reporte_id=:r and dims->>'escenario'='REAL')
        group by 1"""), {"r": rid})}
    fact = {r[0]: float(r[1]) / 1000 for r in c.execute(sa.text(f"""
        select tp.nombre, sum(m.bpdeq_m) from core.fact_produccion_mes_ecp m
        join core.dim_tipo_producto tp on tp.tipo_producto_id=m.tipo_producto_id
        join core.dim_escenario es on es.escenario_id=m.escenario_id
        join core.dim_concepto co on co.concepto_id=m.concepto_id
        join core.dim_proceso pr on pr.proceso_id=m.proceso_id
        where m.reporte_id=:r and es.nombre='REAL' and m.grupo_prod='ECOPETROL'
          and {u.SQL_CONCEPTOS} and {u.SQL_PROCESO_GAS}
          and m.fecha=(select max(m2.fecha) from core.fact_produccion_mes_ecp m2
                       join core.dim_escenario e2 on e2.escenario_id=m2.escenario_id
                       where m2.reporte_id=:r and e2.nombre='REAL')
        group by 1"""), {"r": rid})}
    for p in ("CRUDO", "GAS"):
        assert fact[p] == pytest.approx(ref[p], abs=0.15), f"{p}: fact={fact[p]} DATOS_MES={ref[p]}"
