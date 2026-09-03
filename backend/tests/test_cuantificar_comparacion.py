"""test_cuantificar_comparacion.py — ejecutores NCMP y N3P con `desempeno` inyectado.
Ningún test toca BD: `_desempeno_fn` es un doble.
"""
import datetime

import pytest

from app.features.consulta_v2.cuantificar import ejecutor as _ej
from app.features.consulta_v2.cuantificar.slots import extraer_slots
# 🔴 V1 — `validador` vive DENTRO de `cuantificar/`. El import por `consulta_v2.validador` no
# resuelve: es el mismo camino que usa respuesta_cuantificar.py:26.
from app.features.consulta_v2.cuantificar import validador as _val

_TECHO = datetime.date(2026, 8, 30)
_RESUELTA = {"valor": "CASTILLA", "nivel": "campo", "rama": "A"}
_MESN = {1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
         7: "Julio", 8: "Agosto"}


def _fake(por_periodo, ultimo=8, aplica_diario=True):
    """`por_periodo` = {"julio 2026": (real, ppto, cerrado), ...}. Un periodo ausente devuelve
    sin_cierre, que es como se comporta `desempeno` cuando no hay fila mensual.

    `aplica_diario` replica lo que `_ambito` (api.py:438) pone en la respuesta: False cuando la
    entidad no tiene filas en la tabla DIARIA — el caso de un mes histórico con cierre mensual
    pero sin reporte día a día (V2)."""
    def _fn(entidad=None, segmento="ecp", nivel=None, periodo=None):
        if periodo is None:
            return {"encontrada": True, "aplica_diario": aplica_diario,
                    "por_producto": [{"producto": "CRUDO", "real": 1, "ppto": 1}],
                    "mes": {"anio": 2026, "mes": ultimo, "nombre": _MESN[ultimo],
                            "completo": False, "cerrado": False,
                            "dias_con_data": 30, "dias_del_mes": 31}}
        key = periodo.lower()
        if key not in por_periodo:
            return {"encontrada": True, "sin_cierre": True}
        real, ppto, cerrado = por_periodo[key]
        num = next((n for n, s in _MESN.items() if s.lower() in key), 1)
        return {"encontrada": True, "aplica_diario": aplica_diario,
                "por_producto": [{"producto": "CRUDO", "real": real, "ppto": ppto}],
                "mes": {"anio": 2026, "mes": num, "nombre": _MESN[num],
                        "completo": cerrado, "cerrado": cerrado,
                        "dias_con_data": (30 if cerrado else 17) if aplica_diario else 0,
                        "dias_del_mes": 31}}
    return _fn


# ---------------- NCMP ----------------

def test_ncmp_calcula_delta_y_pct():
    s = extraer_slots("produccion de Castilla en julio vs mayo", techo=_TECHO)
    r = _ej.ejecutar(_RESUELTA, s, _desempeno_fn=_fake(
        {"julio 2026": (1100.0, 1000.0, True), "mayo 2026": (1000.0, 1000.0, True)}))
    assert r["aplica"] and r["nivel"] == "NCMP"
    assert r["delta"] == pytest.approx(100.0)
    assert r["pct"] == pytest.approx(10.0)
    assert r["cumpl_a"] == pytest.approx(110.0) and r["cumpl_b"] == pytest.approx(100.0)


def test_ncmp_declara_el_mes_en_curso():
    """HE4: comparar un mes en curso contra uno cerrado no es ilegítimo, pero callarlo sí."""
    s = extraer_slots("produccion de Castilla en agosto vs mayo", techo=_TECHO)
    r = _ej.ejecutar(_RESUELTA, s, _desempeno_fn=_fake(
        {"agosto 2026": (900.0, 1000.0, False), "mayo 2026": (1000.0, 1000.0, True)}))
    assert any("sigue en curso" in a for a in r["avisos"])


def test_ncmp_sin_reporte_diario_no_habla_de_dias():
    """🔴 V2 — un mes con cierre mensual pero SIN tabla diaria tiene dias_con_data=0. El aviso
    NO puede decir «0 de 31 días» sobre una cifra definitiva: ese es el bug `completo` vs
    `cerrado` entrando por otra puerta."""
    s = extraer_slots("produccion de Castilla en agosto vs mayo", techo=_TECHO)
    r = _ej.ejecutar(_RESUELTA, s, _desempeno_fn=_fake(
        {"agosto 2026": (900.0, 1000.0, False), "mayo 2026": (1000.0, 1000.0, True)},
        aplica_diario=False))
    assert any("provisional" in a for a in r["avisos"])
    assert not any("0/31" in a or "0 de 31" in a for a in r["avisos"])


def test_ncmp_sin_cierre_en_un_lado_declina():
    s = extraer_slots("produccion de Castilla en julio vs marzo", techo=_TECHO)
    r = _ej.ejecutar(_RESUELTA, s, _desempeno_fn=_fake({"julio 2026": (1100.0, 1000.0, True)}))
    assert r["aplica"] is False and "marzo" in r["texto"]


def test_ncmp_con_ventana_declina_honesto():
    """P9: comparación + ventana a la vez no está soportada; se declina, no se resuelve a medias."""
    s = extraer_slots("produccion de Castilla en julio vs mayo", techo=_TECHO)
    s["ventana"] = {"unidad": "mes", "cantidad": 3, "ini": "2026-06-01", "fin": "2026-08-30"}
    r = _ej.ejecutar(_RESUELTA, s, _desempeno_fn=_fake({}))
    assert r["aplica"] is False and "las dos cosas a la vez" in r["texto"]


def test_ncmp_cuerpo_no_revienta_sin_resultado_ni_mes():
    """HE6: el contrato de NCMP no trae `resultado` ni `mes`. Si el validador los leyera antes
    de ramificar, esto sería un KeyError."""
    s = extraer_slots("produccion de Castilla en julio vs mayo", techo=_TECHO)
    r = _ej.ejecutar(_RESUELTA, s, _desempeno_fn=_fake(
        {"julio 2026": (1100.0, 1000.0, True), "mayo 2026": (1000.0, 1000.0, True)}))
    cuerpo = _val.formatear_cuerpo(r)
    assert "julio 2026" in cuerpo and "mayo 2026" in cuerpo and "subió" in cuerpo


# ---------------- N3P ----------------

def test_n3p_serie_con_programa():
    s = extraer_slots("produccion de Castilla mes a mes vs el presupuesto", techo=_TECHO)
    r = _ej.ejecutar(_RESUELTA, s, _desempeno_fn=_fake(
        {f"{_MESN[m].lower()} 2026": (900.0 + m, 1000.0, m < 8) for m in range(1, 9)}))
    assert r["aplica"] and r["nivel"] == "N3P"
    assert len(r["puntos"]) == 8
    assert all(p["ppto"] == 1000.0 for p in r["puntos"])
    assert r["meses_bajo_meta"] == 8


def test_n3p_declara_los_meses_omitidos():
    s = extraer_slots("produccion de Castilla mes a mes vs el presupuesto", techo=_TECHO)
    r = _ej.ejecutar(_RESUELTA, s, _desempeno_fn=_fake(
        {f"{_MESN[m].lower()} 2026": (900.0, 1000.0, True) for m in (1, 2, 7, 8)}))
    assert any("marzo" in a for a in r["avisos"])


def test_n3p_cuerpo_no_revienta_sin_resultado_ni_mes():
    s = extraer_slots("produccion de Castilla mes a mes vs el presupuesto", techo=_TECHO)
    r = _ej.ejecutar(_RESUELTA, s, _desempeno_fn=_fake(
        {f"{_MESN[m].lower()} 2026": (900.0, 1000.0, True) for m in range(1, 9)}))
    cuerpo = _val.formatear_cuerpo(r)
    assert "programa" in cuerpo.lower() and "2026" in cuerpo
