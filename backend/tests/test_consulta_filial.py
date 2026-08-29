"""Tests puros de la respuesta de TENDENCIA de filial (Consulta rama B). No tocan BD ni LLM.
El cálculo (proyección de cierre vs promedio 2026) se inyecta con _tendencia_fn."""
from app.features.consulta.ejecucion import _ejecutar_filial


def _fake(por_producto, n_base=3, completo=False, ndias=17, dim=31):
    def fn(empresa, periodo=None):
        return {"entidad": empresa, "encontrada": True, "periodo": "Mayo 2026",
                "y": 2026, "mo": 5, "dim": dim, "ndias": ndias, "completo": completo,
                "n_base": n_base, "por_producto": por_producto}
    return fn


_TRES = [
    {"producto": "CRUDO", "proyeccion": 2227220, "mtd": 1221000, "promedio_2026": 2370338,
     "variacion_pct": -6.0, "direccion": "por debajo", "reporta": True},
    {"producto": "GAS", "proyeccion": 1025027, "mtd": 562000, "promedio_2026": 1006772,
     "variacion_pct": 1.8, "direccion": "en línea", "reporta": True},
    {"producto": "BLANCOS", "reporta": False},
]


def test_filial_aplica_con_tendencia():
    r = _ejecutar_filial({"rama": "B", "nivel": "filial", "valor": "HOCOL"}, None, None,
                         _tendencia_fn=_fake(_TRES))
    assert r["aplica"] is True
    assert r["modo"] == "tendencia_filial"
    assert r["entidad_cualificada"] == "la filial HOCOL"
    assert "filial HOCOL" in r["encabezado"]
    txt = " ".join(l["texto"] for l in r["lineas"])
    assert "vs su promedio 2026" in txt
    assert "del presupuesto" not in txt                      # sin lexicón de meta en las líneas
    assert all(l["cumplimiento"] is None for l in r["lineas"])   # gatea la narración de meta
    assert not any(l["producto"] == "BLANCOS" for l in r["lineas"])   # no reporta -> omitido


def test_filial_sin_tendencia_honesto():
    def fn(empresa, periodo=None):
        return {"entidad": empresa, "encontrada": True, "sin_tendencia": True, "periodo": "Mayo 2026"}
    r = _ejecutar_filial({"rama": "B", "nivel": "filial", "valor": "AMERICA"}, None, None, _tendencia_fn=fn)
    assert r["aplica"] is False
    assert "tendencia" in r["texto"].lower()


def test_filial_producto_no_reportado():
    r = _ejecutar_filial({"rama": "B", "nivel": "filial", "valor": "HOCOL"}, "blancos", None,
                         _tendencia_fn=_fake(_TRES))
    assert r["aplica"] is False
    assert "no reporta blancos" in r["texto"]


def test_filial_producto_pedido_ok():
    r = _ejecutar_filial({"rama": "B", "nivel": "filial", "valor": "HOCOL"}, "gas", None,
                         _tendencia_fn=_fake(_TRES))
    assert r["aplica"] is True
    assert len(r["lineas"]) == 1 and r["lineas"][0]["producto"] == "GAS"
    assert "+1.8% vs su promedio 2026" in r["lineas"][0]["texto"]


def test_filial_aviso_pocos_meses():
    r = _ejecutar_filial({"rama": "B", "nivel": "filial", "valor": "PERMIAN"}, None, None,
                         _tendencia_fn=_fake([_TRES[0]], n_base=2))
    assert r["aplica"] is True
    assert any("2 meses" in a for a in r["avisos"])


def test_filial_agua_rechazo():
    r = _ejecutar_filial({"rama": "B", "nivel": "filial", "valor": "HOCOL"}, "agua", None,
                         _tendencia_fn=_fake(_TRES))
    assert r["aplica"] is False
    assert "agua" in r["texto"].lower()


def test_narracion_gate_filial():
    """narrar() no narra una respuesta de tendencia_filial (modo) -> Fase 1 plantilla."""
    from app.features.consulta.narracion import narrar
    r = _ejecutar_filial({"rama": "B", "nivel": "filial", "valor": "HOCOL"}, None, None,
                         _tendencia_fn=_fake(_TRES))
    assert r["modo"] == "tendencia_filial"
    assert narrar(r) is None
