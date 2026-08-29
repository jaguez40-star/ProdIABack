"""Focos de FILIALES coherentes con las tarjetas (base promedio 2026, NO programa/valle).

Regresión del bug: el bloque central de "Desempeño Filiales" usaba el _focos de ECP (REAL vs
PROGRAMA misma-ventana) y contradecía a las tarjetas — Permian aparecía como "excedente en crudo"
mientras su tarjeta lo marca por debajo de su promedio 2026. Estas funciones descomponen el faltante
del grupo por filial sobre la MISMA base que las tarjetas y el desglose por filial.
"""
from app.features.analisis.api import _focos_filiales, _sin_foco_filiales


# titular_cards: real = proyección de cierre, ppto = promedio 2026 (así lo arma _ejecutivo_filiales).
_TITULAR = [
    {"producto": "CRUDO", "real": 2227220, "ppto": 2370338},   # 94% -> por debajo
    {"producto": "GAS", "real": 1025027, "ppto": 1006772},     # 102% -> por encima
    {"producto": "BLANCOS", "real": 648951, "ppto": 620628},   # 104% -> por encima
]

def _pf(empresa, prods):
    # prods: {producto: (proyeccion, promedio_2026)}
    pp = [{"producto": p, "proyeccion": v[0], "promedio_2026": v[1], "reporta": True}
          for p, v in prods.items()]
    return {"empresa": empresa, "t": {"por_producto": pp}}

_POR_FILIAL_RAW = [
    _pf("Hocol",   {"CRUDO": (601862, 619192), "GAS": (349201, 373666)}),
    _pf("America", {"CRUDO": (268238, 245963), "GAS": (65877, 60563)}),
    _pf("Permian", {"CRUDO": (1357121, 1505183), "GAS": (609950, 572544), "BLANCOS": (648951, 620628)}),
]


def test_foco_es_crudo_y_solo_crudo():
    focos = _focos_filiales(_TITULAR, _POR_FILIAL_RAW)
    # Solo Crudo proyecta por debajo de su promedio a nivel grupo -> único foco.
    assert [f["producto"] for f in focos] == ["CRUDO"]


def test_detractores_son_permian_y_hocol():
    focos = _focos_filiales(_TITULAR, _POR_FILIAL_RAW)
    crudo = focos[0]
    # Las dos filiales por debajo, más negativa primero (Permian -148k, Hocol -17k). America NO (está por encima).
    assert crudo["entidades"] == ["Permian", "Hocol"]
    assert "America" not in crudo["entidades"]


def test_faltante_grupo_reconcilia():
    focos = _focos_filiales(_TITULAR, _POR_FILIAL_RAW)
    # faltante del grupo = proy - meta = 2.227.220 - 2.370.338
    assert focos[0]["faltante_abs"] == 2227220 - 2370338


def test_permian_no_es_excedente_en_crudo():
    # El corazón del bug: Permian está por debajo en crudo -> NUNCA debe listarse como excedente en crudo.
    sf = _sin_foco_filiales(_TITULAR, _POR_FILIAL_RAW)
    assert "en crudo" in sf.lower()          # sí hay excedente de crudo... (America)
    assert "Permian en crudo" not in sf      # ...pero NO Permian
    assert "America en crudo" in sf


def test_titulo_no_repite_entidades():
    focos = _focos_filiales(_TITULAR, _POR_FILIAL_RAW)
    # El frontend antepone f.entidades; el título no debe volver a nombrarlas.
    assert "Permian" not in focos[0]["titulo"] and "Hocol" not in focos[0]["titulo"]


def test_sin_foco_cuando_todo_en_meta():
    titular_ok = [{"producto": "CRUDO", "real": 100, "ppto": 90}]   # por encima
    raw = [_pf("Hocol", {"CRUDO": (100, 90)})]
    assert _focos_filiales(titular_ok, raw) == []
