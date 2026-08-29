from app.features.consulta.ejecucion import ejecutar


def _fake(por_producto, **extra):
    base = {"encontrada": True, "aplica_diario": True, "sin_cierre": False,
            "mes": {"anio": 2026, "mes": 5, "nombre": "Mayo",
                    "dias_con_data": 17, "dias_del_mes": 31, "completo": False},
            "por_producto": por_producto, "curva": {"fechas": [], "series": {}}}
    base.update(extra)
    def _fn(entidad=None, segmento="ecp", **_):   # F3: acepta segmento (ejecutar lo pasa explícito)
        return base
    return _fn


_PP = [{"producto": "CRUDO", "real": 88857284.0, "ppto": 93790748.0, "cumplimiento": 94.7},
       {"producto": "GAS", "real": 72259391.0, "ppto": 83072749.0, "cumplimiento": 87.0},
       {"producto": "BLANCOS", "real": 500.0, "ppto": 900.0, "cumplimiento": 55.2}]
_A = {"nivel": "campo", "rama": "A", "valor": "RUBIALES"}


def test_un_producto():
    r = ejecutar(_A, "aceite", None, _desempeno_fn=_fake(_PP))
    assert r["aplica"] is True and len(r["lineas"]) == 1
    assert r["lineas"][0]["producto"] == "CRUDO" and r["lineas"][0]["estado"] == "Alineado"
    assert "94.7%" in r["lineas"][0]["texto"]

def test_sin_producto_devuelve_tres():
    r = ejecutar(_A, None, None, _desempeno_fn=_fake(_PP))
    assert r["aplica"] is True and len(r["lineas"]) == 3
    assert r["lineas"][2]["estado"] == "Foco"      # BLANCOS 55.2 -> Foco

def test_agua_rechazada():
    r = ejecutar(_A, "agua", None, _desempeno_fn=_fake(_PP))
    assert r["aplica"] is False and "agua" in r["texto"].lower()

def test_rama_b_filial():
    # Rama B ahora RESPONDE por tendencia (proyección vs promedio 2026), no rechaza. La cifra la
    # calcula tendencia_filial (inyectado aquí para no tocar la BD). Detalle en test_consulta_filial.py.
    _tend = lambda empresa, periodo=None: {
        "entidad": empresa, "encontrada": True, "periodo": "Mayo 2026", "y": 2026, "mo": 5,
        "dim": 31, "ndias": 17, "completo": False, "n_base": 3,
        "por_producto": [{"producto": "CRUDO", "proyeccion": 2227220, "mtd": 1221000,
                          "promedio_2026": 2370338, "variacion_pct": -6.0, "direccion": "por debajo",
                          "reporta": True}]}
    r = ejecutar({"nivel": "filial", "rama": "B", "valor": "Hocol"}, "aceite", None, _tendencia_fn=_tend)
    assert r["aplica"] is True and r["modo"] == "tendencia_filial"
    assert "vs su promedio 2026" in r["lineas"][0]["texto"]

def test_periodo_no_soportado_avisa():
    # periodo_ok=False = lo que desempeno() devuelve cuando _parse_periodo no reconoce el texto
    # (año/semana/trimestre, D-C1) -> ejecutar() debe avisar. Un mes explícito ("marzo") SÍ se
    # parsea (D-C1) y ya no dispara este aviso -- ver test_periodo_explicito_no_avisa.
    r = ejecutar(_A, "aceite", "trimestre 2", _desempeno_fn=_fake(_PP, periodo_ok=False))
    assert r["aplica"] is True and r["avisos"]

def test_periodo_explicito_no_avisa():
    r = ejecutar(_A, "aceite", "marzo", _desempeno_fn=_fake(_PP, periodo_ok=True))
    assert r["aplica"] is True and not r["avisos"]

def test_agregacion_promedio_avisa():
    r = ejecutar(_A, "aceite", None, agregacion="promedio_diario", _desempeno_fn=_fake(_PP))
    assert r["aplica"] is True and any("promedio" in a.lower() for a in r["avisos"])

def test_producto_no_reportado():
    pp = [{"producto": "GAS", "real": 0.0, "ppto": 0.0, "cumplimiento": None}]
    r = ejecutar(_A, "gas", None, _desempeno_fn=_fake(pp))
    assert r["aplica"] is False and "no reporta" in r["texto"].lower()

def test_sin_cierre():
    r = ejecutar(_A, "aceite", None, _desempeno_fn=_fake(_PP, sin_cierre=True))
    assert r["aplica"] is False
