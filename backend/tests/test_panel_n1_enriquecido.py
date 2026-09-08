"""N1 pasa al panel de dos columnas con curva diaria (2026-09-08 · PANEL-N1).

Sin BD ni LLM: se sustituyen el resolver, el ejecutor y `p50_referencia` por dobles, igual que
en test_cuantificar_panorama.py. Lo que se fija:
  · N1 emite `cuant_dia_panel` con las 6 claves del contrato y `dia_marcado` en None
  · el P50 solo viaja en los niveles que lo tienen, y YA CONVERTIDO de BPD a kbopd
  · los demás niveles (N2/N3/N1D) NO cambian de panel
"""
import pytest

from app.features.consulta_v2 import respuesta_cuantificar as _rc


def _res_n1(nivel_ent="campo", entidad="CASTILLA"):
    """El dict que devuelve el ejecutor para un N1, con lo mínimo que usa _panel_datos."""
    return {
        "aplica": True, "nivel": "N1",
        "entidad": {"nombre": entidad, "nivel": nivel_ent, "fue_asumida": False},
        "entidad_cualificada": "el Campo " + entidad,
        "producto": "crudo", "unidad": "kbopd",
        "resultado": {"valor": 55.0}, "referencia_valor": 52.1,
        "cumplimiento_pct": 105.5, "estado": "Alineado",
        "referencia": "PPTO", "referencia_label": "presupuesto",
        "mes": {"anio": 2026, "mes": 4, "nombre": "abril", "dias_del_mes": 30,
                "dias_con_data": 30, "completo": True, "cerrado": True},
        "huella": {"registros": 30, "dias_del_mes": 30, "es_proyeccion": False},
        "avisos": [], "zoom": [],
    }


# --- el contrato del panel --------------------------------------------------------------

def test_n1_emite_el_panel_de_curva_diaria():
    d = _rc._panel_datos(_res_n1())
    for clave in ("entidad", "segmento", "periodo", "productos", "dia_marcado"):
        assert clave in d, f"falta la clave {clave!r} del contrato de cuant_dia_panel"
    assert d["dia_marcado"] is None       # mensual: no hay día que resaltar
    assert d["periodo"] == "abril 2026"   # el mes de la PREGUNTA, no el del corte — minúscula,
                                           # misma convención que N1D (_MESES_PANEL:61-62)
    assert d["productos"] == ["CRUDO"]
    assert d["nivel"] == "N1"             # el nivel TEMPORAL no se pisa
    assert d["nivel_entidad"] == "campo"  # el de la entidad viaja en su propia clave


def test_n1_lleva_la_huella_que_antes_se_descartaba():
    d = _rc._panel_datos(_res_n1())
    assert d["dias_con_dato"] == 30 and d["dias_del_mes"] == 30
    assert d["es_proyeccion"] is False
    assert d["referencia_label"] == "presupuesto"


def test_los_demas_niveles_no_cambian():
    """N2 sigue siendo KPI acumulado: este plan solo toca N1."""
    res = _res_n1(); res["nivel"] = "N2"
    res.update({"periodo_label": "enero-agosto 2026", "meses_cerrados": 8,
                "serie_acum": [], "anio": 2026})
    d = _rc._panel_datos(res)
    assert "dia_marcado" not in d
    assert d["periodo_label"] == "enero-agosto 2026"


# --- el P50: escala y nivel (H-04, H-05) ------------------------------------------------

_SERIE_VP = {"vice": "VRO", "producto": "crudo", "unidad": "bpd", "fmt": "vp",
             "serie": [{"fecha": "2026-03-01", "p50": 54000.0, "real": 53000.0},
                       {"fecha": "2026-04-01", "p50": 55400.0, "real": 52300.0}]}


@pytest.fixture
def p50_vp(monkeypatch):
    monkeypatch.setattr(_rc._p50, "nivel_soportado", lambda n, r=None: n == "vicepresidencia")
    monkeypatch.setattr(_rc._p50, "serie_por_vp", lambda v, p="CRUDO": _SERIE_VP)


def test_p50_se_convierte_de_bpd_a_la_escala_del_panel(p50_vp):
    """🔴 H-04: la hoja P50 está en BPD y el panel dibuja en kbopd. Sin el ÷1000 la línea sale
    mil veces fuera de escala — el bug dd8ffa2, invisible en crudo."""
    res = _res_n1(nivel_ent="vicepresidencia", entidad="VRO")
    p50 = _rc._p50_del_mes({"nivel": "vicepresidencia", "valor": "VRO"}, res)
    assert p50 is not None
    assert p50["valor"] == pytest.approx(55.4)     # 55.400 bpd -> 55,4 kbopd
    assert p50["valor"] < 100                      # jamás en el orden de 10⁴


def test_p50_toma_el_mes_de_la_pregunta_no_el_ultimo(p50_vp):
    """H-06: la serie trae 12 meses. Abril debe compararse contra el P50 de ABRIL."""
    res = _res_n1(nivel_ent="vicepresidencia", entidad="VRO")
    res["mes"] = {"anio": 2026, "mes": 3, "nombre": "marzo", "dias_del_mes": 31,
                  "dias_con_data": 31, "completo": True, "cerrado": True}
    p50 = _rc._p50_del_mes({"nivel": "vicepresidencia", "valor": "VRO"}, res)
    assert p50["valor"] == pytest.approx(54.0)     # el de marzo, no el de abril


def test_un_campo_no_tiene_p50(p50_vp):
    """🔴 H-05: el P50 NO se define por campo. Inventarlo sería el fallo silencioso que el
    proyecto persigue: una cifra creíble comparada contra un compromiso que no existe."""
    res = _res_n1(nivel_ent="campo", entidad="CASTILLA")
    assert _rc._p50_del_mes({"nivel": "campo", "valor": "CASTILLA"}, res) is None


def test_sin_p50_el_panel_sale_igual_sin_la_clave(p50_vp):
    """Best-effort: sin P50 el panel se pinta con sus 3 líneas de siempre."""
    res = _res_n1(nivel_ent="campo")
    res["p50"] = None
    d = _rc._panel_datos(res)
    assert d["p50"] is None
