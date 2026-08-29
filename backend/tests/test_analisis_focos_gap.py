"""Focos tipo `gap`: coherencia entre lo que el titular dice y lo que el detalle lista.

Caso real que motivó estos tests (GAS, mayo-2026, global ECP — verificado contra la BD):

    titular  : -10.813.358        <- gap NETO (faltantes menos excedentes)
    detalle  : CUSIANA -16.667.554 · CUPIAGUA -2.616.860 · ARAUCA -530.282
    titulo   : "CUSIANA + CUPIAGUA · 90.6% del faltante en 2 campos"

Dos incoherencias: (1) el 90.6% era la concentración del top-3 (incluía ARAUCA) mientras el
texto nombraba 2 campos — con 2 el valor real es 88.2%; (2) el titular era neto y el detalle
bruto, sin nada que explicara por qué los campos listados suman casi el doble.
"""
from app.features.analisis.api import _focos


def _g(detr, comp, bruto, exced, conc_top3):
    """Simula la salida de _gap_campo para un producto."""
    return {
        "detractores": [{"campo": c, "gap": g, "real": 0, "meta": 0} for c, g in detr],
        "compensadores": [{"campo": c, "gap": g, "real": 0, "meta": 0} for c, g in comp],
        "faltante_bruto": bruto, "excedente_bruto": exced,
        "concentracion_pct": conc_top3,
    }


# Cifras reales de GAS · mayo-2026 · global ECP
_GAS = _g(
    detr=[("CUSIANA", -16667554), ("CUPIAGUA", -2616859), ("ARAUCA", -530282)],
    comp=[("PAUTO SUR", 5756510), ("CHUCHUPA", 2282052)],
    bruto=-21862963, exced=11049613, conc_top3=90.6,
)
_TITULAR = [{"producto": "GAS", "real": 9868311, "ppto": 20681661, "valor_pct": 47.7}]


def _foco_gas():
    return [f for f in _focos(_TITULAR, {"GAS": _GAS}, None, []) if f["tipo"] == "gap"][0]


def test_concentracion_corresponde_a_los_campos_nombrados():
    """El % del título se calcula sobre los campos que el título NOMBRA (2), no sobre el top-3."""
    f = _foco_gas()
    assert f["entidades"] == ["CUSIANA", "CUPIAGUA"]
    assert "88.2% del faltante en 2 campos" in f["titulo"]
    assert "90.6%" not in f["titulo"]            # el top-3 ya no se muestra junto a 2 campos
    assert f["peso_relativo_pct"] == 88.2


def test_titulo_no_repite_las_entidades():
    """El frontend antepone f.entidades; si el título también las trae sale duplicado
    ("GAS · CUSIANA + CUPIAGUA CUSIANA + CUPIAGUA · 88.2%…"). Misma convención que filiales."""
    f = _foco_gas()
    for ent in f["entidades"]:
        assert ent not in f["titulo"]


def test_detalle_cierra_la_aritmetica_bruto_neto():
    """El detalle explica por qué los faltantes listados no suman el titular."""
    f = _foco_gas()
    assert f["faltante_abs"] == -10813350       # neto = real - ppto
    cierre = f["causa"]["detalle"][-1]
    assert "Faltante bruto 21.862.963" in cierre
    assert "excedentes 11.049.613" in cierre
    assert "neto 10.813.350" in cierre
    # invariante auditable: bruto + excedentes == neto
    assert f["faltante_bruto"] + f["excedente_bruto"] == -10813350


def test_un_solo_detractor_no_usa_plantilla_de_concentracion():
    """Con un único campo el título no habla de concentración (no hay nada que concentrar)."""
    g = _g(detr=[("CUPIAGUA", -2616859)], comp=[], bruto=-2616859, exced=0, conc_top3=100.0)
    titular = [{"producto": "GAS", "real": 9868311, "ppto": 12485170, "valor_pct": 79.0}]
    f = [x for x in _focos(titular, {"GAS": g}, None, []) if x["tipo"] == "gap"][0]
    assert f["titulo"] == "concentra el rezago del producto"     # el campo lo antepone el frontend
    assert f["entidades"] == ["CUPIAGUA"]
    # sin excedentes no se agrega la línea de cierre (no habría diferencia que explicar)
    assert all("Faltante bruto" not in d for d in f["causa"]["detalle"])
