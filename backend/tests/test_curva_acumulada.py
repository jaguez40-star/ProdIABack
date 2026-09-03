"""test_curva_acumulada.py — la curva creciente del acumulado N2 (plan CURVA-ACUMULADA, 2026-09-03).

Sin BD: `niveles.acumulado` se prueba con un `_desempeno_fn` FAKE, igual que
`test_cuantificar.py` hace para N2 hoy. Lo que se mide es el CABLEADO (HE4, la suma corrida,
el contrato hacia el panel), no el dato real.
"""
import pytest

from app.features.consulta_v2.cuantificar import niveles as _niveles
from app.features.consulta_v2.cuantificar import ejecutor as _ejecutor
from app.features.consulta_v2.respuesta_cuantificar import _panel_datos, _PANEL_TIPO

_ENT = {"valor": "CASTILLA", "nivel": "campo", "rama": "A", "zoom": []}

# 4 meses cerrados (ene-abr) con REAL/PPTO crecientes + mayo EN CURSO (no debe sumarse, HE4).
_MESES_FAKE = {
    1: {"real": 1000.0, "ppto": 1200.0}, 2: {"real": 1100.0, "ppto": 1200.0},
    3: {"real": 900.0,  "ppto": 1200.0}, 4: {"real": 1200.0, "ppto": 1200.0},
}


def _fake_desempeno(entidad="X", segmento="ecp", nivel=None, periodo=None):
    if periodo is None:                         # d0: consulta "sin periodo" -> último mes/año
        return {"encontrada": True, "sin_datos": False, "sin_cierre": False,
                "mes": {"anio": 2026, "mes": 5, "nombre": "Mayo", "completo": False}}
    _MESES_NUM = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5}
    m = _MESES_NUM[periodo]
    if m == 5:                                   # mayo: EN CURSO, no cerrado
        return {"encontrada": True, "sin_datos": False, "sin_cierre": False,
                "mes": {"anio": 2026, "mes": 5, "nombre": "Mayo", "completo": False},
                "por_producto": [{"producto": "CRUDO", "real": 400.0, "ppto": 1200.0}]}
    fila = _MESES_FAKE[m]
    return {"encontrada": True, "sin_datos": False, "sin_cierre": False,
            "mes": {"anio": 2026, "mes": m, "nombre": "X", "completo": True},
            "por_producto": [{"producto": "CRUDO", "real": fila["real"], "ppto": fila["ppto"]}]}


def _fake_desempeno_sin_ppto(entidad="X", segmento="ecp", nivel=None, periodo=None):
    """Ningún mes trae presupuesto: ppto_acum debe quedar en None, no en 0 (H1 del ejecutor)."""
    if periodo is None:
        return {"encontrada": True, "sin_datos": False, "sin_cierre": False,
                "mes": {"anio": 2026, "mes": 3, "nombre": "Marzo", "completo": False}}
    _MESES_NUM = {"enero": 1, "febrero": 2, "marzo": 3}
    m = _MESES_NUM[periodo]
    if m == 3:
        return {"encontrada": True, "sin_datos": False, "sin_cierre": False,
                "mes": {"anio": 2026, "mes": 3, "nombre": "Marzo", "completo": False},
                "por_producto": [{"producto": "CRUDO", "real": 300.0, "ppto": 0.0}]}
    return {"encontrada": True, "sin_datos": False, "sin_cierre": False,
            "mes": {"anio": 2026, "mes": m, "nombre": "X", "completo": True},
            "por_producto": [{"producto": "CRUDO", "real": 500.0, "ppto": 0.0}]}


# ---------------- niveles.acumulado: la suma corrida ----------------

def test_serie_acum_crece_mes_a_mes():
    r = _niveles.acumulado(_ENT, "CRUDO", _desempeno_fn=_fake_desempeno)
    assert r["aplica"] is True
    vals = [p["real_acum"] for p in r["serie_acum"]]
    assert vals == sorted(vals)                  # nunca baja: es una suma acumulada


def test_serie_acum_valores_exactos():
    r = _niveles.acumulado(_ENT, "CRUDO", _desempeno_fn=_fake_desempeno)
    vals = [p["real_acum"] for p in r["serie_acum"]]
    assert vals == [1000.0, 2100.0, 3000.0, 4200.0]
    ppto = [p["ppto_acum"] for p in r["serie_acum"]]
    assert ppto == [1200.0, 2400.0, 3600.0, 4800.0]


def test_serie_acum_excluye_el_mes_en_curso():
    """🔑 REGRESIÓN CENTRAL — HE4. Mayo está en curso (completo=False): NO debe aparecer en la
    serie ni mover el último valor de real_acum."""
    r = _niveles.acumulado(_ENT, "CRUDO", _desempeno_fn=_fake_desempeno)
    assert len(r["serie_acum"]) == 4              # solo ene-abr
    assert all(p["num"] != 5 for p in r["serie_acum"])
    assert r["serie_acum"][-1]["real_acum"] == r["real"]   # coincide con el total del gauge
    assert r["en_curso"] == {"nombre": "mayo", "real": 400.0}


def test_serie_acum_meses_cortos_y_numeros():
    r = _niveles.acumulado(_ENT, "CRUDO", _desempeno_fn=_fake_desempeno)
    assert [p["mes"] for p in r["serie_acum"]] == ["Ene", "Feb", "Mar", "Abr"]
    assert [p["num"] for p in r["serie_acum"]] == [1, 2, 3, 4]


def test_ppto_acum_none_sin_presupuesto():
    """Si NINGÚN mes trae PPTO, ppto_acum es None (no 0): pintar ceros afirmaría PPTO=0."""
    r = _niveles.acumulado(_ENT, "CRUDO", _desempeno_fn=_fake_desempeno_sin_ppto)
    assert all(p["ppto_acum"] is None for p in r["serie_acum"])


def test_acumulado_sigue_devolviendo_el_contrato_de_siempre():
    """No regresión: real/ppto/meses/en_curso/anio del contrato ORIGINAL siguen ahí."""
    r = _niveles.acumulado(_ENT, "CRUDO", _desempeno_fn=_fake_desempeno)
    assert r["real"] == 4200.0 and r["ppto"] == 4800.0
    assert r["meses"] == ["enero", "febrero", "marzo", "abril"]
    assert r["anio"] == 2026


# ---------------- ejecutor.ejecutar_n2: el contrato hacia el panel ----------------

def test_ejecutar_n2_propaga_serie_acum():
    res = _ejecutor.ejecutar_n2(_ENT, {"producto": "crudo", "unidad": "bbl"},
                                _desempeno_fn=_fake_desempeno)
    assert res["aplica"] is True
    assert len(res["serie_acum"]) == 4
    assert res["serie_acum"][-1]["real_acum"] == res["resultado"]["valor"]


def test_ejecutar_n2_propaga_anio():
    """🔑 H15 — N2 no tiene clave `mes`; `anio` debe salir EXPLÍCITO en el contrato."""
    res = _ejecutor.ejecutar_n2(_ENT, {"producto": "crudo", "unidad": "bbl"},
                                _desempeno_fn=_fake_desempeno)
    assert res["anio"] == 2026
    assert "mes" not in res


def test_ejecutar_n2_gauge_no_cambia():
    """No regresión: el gauge (resultado/referencia_valor/cumplimiento_pct/estado) es el de
    siempre — este plan es aditivo sobre N2, no lo reemplaza."""
    res = _ejecutor.ejecutar_n2(_ENT, {"producto": "crudo", "unidad": "bbl"},
                                _desempeno_fn=_fake_desempeno)
    assert res["resultado"]["valor"] == 4200.0
    assert res["referencia_valor"] == 4800.0
    assert res["cumplimiento_pct"] == round(4200.0 / 4800.0 * 100.0, 1)


# ---------------- respuesta_cuantificar: tipo de panel + datos ----------------

def test_tipo_panel_n2_es_cuant_acum():
    assert _PANEL_TIPO.get("N2") == "cuant_acum"


def test_tipo_panel_n1_sigue_siendo_kpi_por_defecto():
    """N1 NO está en _PANEL_TIPO: cae al default 'cuant_kpi' de _panel_datos.get(...). No
    regresión — este plan solo añade la clave N2."""
    assert "N1" not in _PANEL_TIPO


def test_panel_datos_n2_lleva_serie_acum_y_anio():
    res = _ejecutor.ejecutar_n2(_ENT, {"producto": "crudo", "unidad": "bbl"},
                                _desempeno_fn=_fake_desempeno)
    d = _panel_datos(res)
    assert d["serie_acum"] == res["serie_acum"]
    assert d["anio"] == 2026


def test_panel_datos_n2_sin_serie_da_lista_vacia_no_error():
    """Un N2 con un solo mes (o sin `serie_acum` en el contrato) no debe romper _panel_datos."""
    res = _ejecutor.ejecutar_n2(_ENT, {"producto": "crudo", "unidad": "bbl"},
                                _desempeno_fn=_fake_desempeno)
    del res["serie_acum"]
    d = _panel_datos(res)
    assert d["serie_acum"] == []


# ---------------- [2026-09-03 · VENTANA-MESES] acumulado ACOTADO por ventana ----------------

def _slots_ven(cant, ini, fin):
    return {"producto": "crudo", "unidad": "bbl",
            "ventana": {"unidad": "mes", "cantidad": cant, "ini": ini, "fin": fin}}


def test_acumulado_acotado_desde_mes():
    """desde_mes=3 arranca en marzo: marzo+abril, no enero-abril."""
    r = _niveles.acumulado(_ENT, "CRUDO", _desempeno_fn=_fake_desempeno, desde_mes=3)
    assert [p["mes"] for p in r["serie_acum"]] == ["Mar", "Abr"]
    assert r["real"] == 900.0 + 1200.0
    assert r["meses"] == ["marzo", "abril"]


def test_acumulado_sin_desde_mes_es_el_ytd_de_siempre():
    """No regresión: el default (1) da byte a byte el acumulado de antes."""
    a = _niveles.acumulado(_ENT, "CRUDO", _desempeno_fn=_fake_desempeno)
    b = _niveles.acumulado(_ENT, "CRUDO", _desempeno_fn=_fake_desempeno, desde_mes=1)
    assert a == b and a["real"] == 4200.0


def test_ventana_de_meses_acota_el_acumulado():
    """🔑 EL HUECO QUE ESTO CIERRA. «Los últimos 3 meses» con techo en mayo (en curso) → la
    ventana arranca en marzo; se acumulan los meses CERRADOS de dentro (marzo, abril)."""
    res = _ejecutor.ejecutar_n2(_ENT, _slots_ven(3, "2026-03-01", "2026-05-15"),
                                _desempeno_fn=_fake_desempeno)
    assert res["aplica"] is True
    assert res["meses_cerrados"] == 2
    assert res["periodo_label"] == "marzo–abril 2026"
    assert res["resultado"]["valor"] == 900.0 + 1200.0


def test_ventana_de_meses_declara_la_ventana():
    """Nada en silencio: el usuario pidió 3 meses y el rótulo dice «marzo–abril». Hay que unirlos."""
    res = _ejecutor.ejecutar_n2(_ENT, _slots_ven(3, "2026-03-01", "2026-05-15"),
                                _desempeno_fn=_fake_desempeno)
    assert any("ltimos 3 meses" in a and "2026-05-15" in a for a in res["avisos"])


def test_ventana_que_cruza_el_anio_se_declina_honesto():
    """🔑 `acumulado` vive dentro de UN año. Aceptar una ventana dic→feb sumaría solo ene-feb y
    lo llamaría «los últimos 3 meses» — responder otra cosa en silencio."""
    res = _ejecutor.ejecutar_n2(_ENT, _slots_ven(3, "2025-12-01", "2026-02-10"),
                                _desempeno_fn=_fake_desempeno)
    assert res["aplica"] is False
    assert "cruzan el cambio de año" in res["texto"]


def test_sin_ventana_el_n2_no_declara_ventana():
    """No regresión: el acumulado del año de siempre no gana avisos nuevos."""
    res = _ejecutor.ejecutar_n2(_ENT, {"producto": "crudo", "unidad": "bbl"},
                                _desempeno_fn=_fake_desempeno)
    assert not any("cuentan hacia atr" in a for a in res["avisos"])
    assert res["periodo_label"] == "enero–abril 2026"


# ---------------- [2026-09-03 · VENTANA-CONT] la ventana como CONTINUACION ----------------

def test_continuacion_hereda_la_entidad_con_ventana():
    """🔑 Medido antes: «¿en los últimos 6 meses?» tras un N2 de CASTILLA devolvía None y caía a
    Desconocido, perdiendo el hilo a mitad de una conversación de Cuantificar."""
    from app.features.consulta_v2.maquina_q import _continuacion
    ctx = {"grupo": "cuantificar", "entidad": "CASTILLA", "producto": "crudo"}
    for frase in ("en los ultimos 6 meses?", "en los ultimos 30 dias?",
                  "y en las ultimas 6 semanas?"):
        r = _continuacion(frase, ctx)
        assert r is not None and "CASTILLA" in r, frase


def test_continuacion_ventana_preserva_el_producto():
    """AF9: tras un N1/N2 de gas, la continuación con ventana no vuelve a crudo."""
    from app.features.consulta_v2.maquina_q import _continuacion
    ctx = {"grupo": "cuantificar", "entidad": "CUSIANA", "producto": "gas"}
    assert "gas" in _continuacion("en los ultimos 6 meses?", ctx)


def test_continuacion_ventana_no_pisa_lo_estructural():
    """La guarda _ESTRUCT_KW sigue mandando: «cuántos pozos» no es una cifra de producción."""
    from app.features.consulta_v2.maquina_q import _continuacion
    ctx = {"grupo": "cuantificar", "entidad": "CASTILLA", "producto": "crudo"}
    r = _continuacion("cuantos pozos tiene?", ctx)
    assert r is None or "produccion de" not in r
