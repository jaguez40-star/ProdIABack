"""Preguntas META sobre el catálogo (2026-07-16).

Existen porque la CIFRA depende del nivel: APIAY da 269.035 bl (50.7%, Foco) como Campo y
577.362 bl (108.8%, Alineado) como Activo. Sin poder preguntar QUÉ es algo, el usuario no sabe
qué cifra está pidiendo. Antes, "¿qué tipo de entidad es CPO-09?" devolvía producción.
"""
import pytest
from app.features.consulta.meta import detectar, _y


# --- detección de intención (pura, sin BD ni LLM) ---

@pytest.mark.parametrize("texto,esperado", [
    ("Que tipo de entidad es CPO-09", "tipo"),
    ("qué tipo es Chichimene", "tipo"),
    ("Que es Cano Limon", "tipo"),
    ("Que campos tiene el activo Apiay", "campos"),
    ("de qué campos se compone Castilla", "campos"),
    ("A que activo pertenece Lorito", "pertenencia"),
    ("de qué activo es Gavan", "pertenencia"),
])
def test_detecta_intencion_meta(texto, esperado):
    assert detectar(texto) == esperado


@pytest.mark.parametrize("texto", [
    "Cual es la produccion de Apiay",
    "cuanto crudo produjo Chichimene",
    "produccion de Rubiales",
    "qué volumen reportó Castilla",
    "cuál es el presupuesto de Apiay",
])
def test_pregunta_de_cifra_no_es_meta(texto):
    """Guarda: si el texto pide un número, NO es meta. Sin esto, 'que es la produccion de X' se
    colaría como pregunta de catálogo y el usuario no vería su cifra."""
    assert detectar(texto) is None


def test_y_enumera_natural():
    assert _y(["A"]) == "A"
    assert _y(["A", "B"]) == "A y B"
    assert _y(["A", "B", "C"]) == "A, B y C"      # no "A y B y C"


# --- huella: "¿qué información hay de X?" -> panel de Densidad + Cobertura (2026-07-16) ---

@pytest.mark.parametrize("texto", [
    "Que informacion hay de Apiay",
    "qué datos hay de Rubiales",
    "desde cuándo hay datos de Castilla",
    "cobertura de Chichimene",
    "qué reportes tiene Apiay",
    "disponibilidad de Rubiales",
    # formas pedidas por el usuario (2026-07-16)
    "Que informacion esta disponible de Apiay",
    "cual es el reporte de Apiay",
    "cuales son los reportes de Rubiales",
])
def test_detecta_huella(texto):
    assert detectar(texto) == "huella"


@pytest.mark.parametrize("texto", [
    "cuántos días con reporte hay de Apiay",              # CUANT
    "desde cuándo hay datos de producción de Rubiales",   # PRODUC
])
def test_huella_gana_al_guard_de_cifra(texto):
    """Estas preguntan por la DISPONIBILIDAD pero traen CUANT/PRODUC: si el guard corriera primero,
    _PIDE_CIFRA las descartaría como meta y acabarían devolviendo una cifra — otra pregunta."""
    assert detectar(texto) == "huella"


@pytest.mark.parametrize("texto", [
    "Cual es la produccion de Apiay",
    "cuanto crudo produjo Chichimene",
    "qué campos tiene el activo Apiay",
    "Que tipo de entidad es CPO-09",
    "Que es CPO-09",                      # sigue siendo catálogo: responde QUÉ es, no qué datos hay
    "cual es el volumen de Castilla",     # 'CUAL ES EL...' no debe arrastrar a huella
])
def test_huella_no_se_come_las_otras_preguntas(texto):
    """La huella se evalúa PRIMERO: hay que probar que no absorbe cifras ni catálogo."""
    assert detectar(texto) != "huella"


def test_catalogo_trae_huella_para_el_panel():
    """"Qué es X" → catálogo en la burbuja Y huella en el panel derecho (antes: aviso vacío).
    El intent va aunque el nivel siga pendiente: la huella resuelve por nombre, no por nivel."""
    from app.features.consulta.meta import responder_meta
    d = responder_meta("Que es Chichimene", "tipo")
    assert d["status"] == "pendiente"
    hi = d.get("huella_intent")
    assert hi and hi["entidad"] == "CHICHIMENE" and hi["rama"] in ("A", "B")


# --- respuesta (toca BD: catálogo + índice del resolver) ---

def test_tipo_de_un_nombre_dual_ofrece_campo_y_activo():
    """Chichimene es Campo y Activo -> se explican los dos y cada botón lleva a SU cifra."""
    from app.features.consulta.meta import responder_meta
    d = responder_meta("Que tipo de entidad es Chichimene", "tipo")
    assert d["status"] == "pendiente" and d["meta"] is True
    niveles = [o["id"].split("::")[0] for o in d["opciones"]]
    assert niveles == ["campo", "activo"]
    # D-D5: la lectura 'fuente' se descarta (son 5 fuentes, 3 con campo NULL = ruido de ingesta)
    assert "fuente" not in niveles
    assert "CHICHIMENE SW" in d["opciones"][1]["desc"]


def test_tipo_de_un_campo_de_tercero_dice_que_no_tiene_activo():
    from app.features.consulta.meta import responder_meta
    d = responder_meta("Que es Cano Limon", "tipo")
    assert "no pertenece a ningún Activo" in d["pregunta"]
    assert [o["id"].split("::")[0] for o in d["opciones"]] == ["campo"]


def test_pertenencia_de_lorito_responde_akacias():
    """Cierra el caso que motivó el veredicto D-A2 (LORITO estaba en 2 activos del CSV)."""
    from app.features.consulta.meta import responder_meta
    d = responder_meta("A que activo pertenece Lorito", "pertenencia")
    assert "pertenece al Activo AKACIAS" in d["pregunta"]


def test_campos_del_activo_apiay_los_lista():
    from app.features.consulta.meta import responder_meta
    d = responder_meta("Que campos tiene el activo Apiay", "campos")
    for campo in ("APIAY", "APIAY ESTE", "GAVAN", "GUATIQUIA"):
        assert campo in d["pregunta"]


def test_meta_no_reconocida_pide_reformular():
    from app.features.consulta.meta import responder_meta
    d = responder_meta("Que tipo de entidad es Xyzzy", "tipo")
    assert d["status"] == "reformular"
