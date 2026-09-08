"""El drill no responde por OTRA entidad cuando el sujeto no está en el catálogo.

Bug real medido en el servidor de pruebas (2026-09-08): tras preguntar por CASTILLA, la
pregunta «¿Cuánto produjo VRO en el mes de Agosto?» se respondía con «el Campo CASTILLA
produjo 53,8 kbopd…» — mismas cifras, sin un solo aviso. Dos entidades distintas confundidas.

Causa: `_continuacion` no reconocía «VRO» (no está en el catálogo del resolutor), concluía que
la frase no nombraba entidad y le anteponía la del turno anterior. El clasificador veía
entonces CASTILLA, que SÍ existe, e ignoraba VRO.

`respuesta_cuantificar.py:566-577` ya tiene la respuesta honesta para este caso («No reconocí
«X» en el catálogo»); el drill se la estaba saltando. Basta con devolver None.

`_continuacion` es PURA (sin BD ni LLM): recibe el ctx como argumento.
"""
from app.features.consulta_v2.maquina_q import _continuacion

_CUANT = {"grupo": "cuantificar", "entidad": "CASTILLA", "producto": "crudo",
          "periodo_ctx": "agosto 2026"}
_FICHA = {"entidad": "CASTILLA", "nivel": "campo", "hijos": [], "ofrece_produccion": True}


# --- el bug que se arregla --------------------------------------------------------------

def test_sujeto_fuera_del_catalogo_no_hereda():
    """🔴 El caso exacto de la app: preguntar por VRO no puede responder por CASTILLA."""
    for frase in ("Cuanto produjo VRO en el mes de Agosto?",
                  "Cuanto produjo la VRO en agosto?",
                  "cuanto produjo GOR en julio?"):
        assert _continuacion(frase, _CUANT) is None, \
            f"{frase!r} heredó CASTILLA: el usuario recibiría cifras de OTRA entidad"


def test_sujeto_desconocido_tambien_con_ficha():
    assert _continuacion("Cuanto produjo VRO en agosto?", _FICHA) is None


# --- lo que NO debe cambiar --------------------------------------------------------------

def test_sustantivo_generico_sigue_heredando():
    """REGRESIÓN (test_cuantificar_dia.py:735): «el campo» no nombra a nadie — es la entidad
    del contexto con el sustantivo elidido, y SÍ debe heredar."""
    rw = _continuacion("produjo el campo en mayo", _CUANT)
    assert rw is not None and "CASTILLA" in rw


def test_continuaciones_normales_siguen_heredando():
    assert "CASTILLA" in (_continuacion("y en mayo?", _CUANT) or "")
    assert _continuacion("y el acumulado?", _CUANT) == "acumulado de CASTILLA"
    assert _continuacion("a que activo pertenece?", _CUANT) == "que es CASTILLA"
    assert "CASTILLA" in (_continuacion("vs operativo", _CUANT) or "")


def test_entidad_conocida_sigue_siendo_autocontenida():
    """Un sujeto que SÍ está en el catálogo ya cortaba antes (la frase viaja entera) y debe
    seguir haciéndolo — por la rama de `ent`, no por esta guarda."""
    assert _continuacion("cuanto produjo CHICHIMENE en agosto?", _CUANT) is None
