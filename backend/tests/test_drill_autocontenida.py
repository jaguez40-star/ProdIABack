"""El drill no secuestra preguntas autocontenidas (2026-09-08 · DRILL-AUTOCONTENIDA).

Bug real visto en la app: tras «¿cuánto produjo Rubiales hoy?», las dos preguntas siguientes
—que NO nombraban a Rubiales— se respondieron sobre Rubiales. `_continuacion` las reescribía
heredando la entidad del contexto, por DOS caminos distintos según el ctx vigente.

Estos tests fijan las dos mitades del contrato:
  · las frases autocontenidas que deben romper el hilo (devolver None), con los DOS ctx reales
  · las continuaciones legítimas de los 4 drills, que deben seguir heredando intactas

`_continuacion` es PURA (sin BD ni LLM): recibe el ctx como argumento.
"""
from app.features.consulta_v2.maquina_q import _continuacion

# ctx que deja «¿cuánto produjo Rubiales hoy?» (cuantificar con entidad).
_CTX_CUANT = {"grupo": "cuantificar", "entidad": "RUBIALES", "producto": "crudo", "periodo_ctx": None}
# ctx que deja una ficha jerárquica («que es RUBIALES»): SIN clave "grupo". Es el que estaba
# vigente cuando el usuario preguntó «¿cuánto produjimos en abril?» y recibió Rubiales/septiembre.
_CTX_JERAR = {"entidad": "RUBIALES", "nivel": "campo", "hijos": [], "ofrece_produccion": True}
# ctx de una conversación de Analizar.
_CTX_ANALIZ = {"grupo": "analizar", "entidad": "CASTILLA", "sub": "proyeccion", "producto": None}


def test_sujeto_propio_rompe_el_hilo_con_ctx_cuantificar():
    for frase in ("Cuanto produjimos en abril?", "Cuanto producimos hoy?",
                  "cuanto producimos este mes?"):
        rw = _continuacion(frase, _CTX_CUANT)
        assert rw is None, f"{frase!r} heredó la entidad: {rw!r}"


def test_sujeto_propio_rompe_el_hilo_con_ctx_jerarquizar():
    """El camino REAL de la sesión del usuario: la rama ofrece_produccion SUSTITUÍA el texto."""
    for frase in ("Cuanto produjimos en abril?", "Cuanto producimos hoy?"):
        rw = _continuacion(frase, _CTX_JERAR)
        assert rw is None, f"{frase!r} se reescribió a {rw!r} y perdió su propio mes"


def test_ranking_no_se_convierte_en_ficha_jerarquica():
    for ctx in (_CTX_CUANT, _CTX_JERAR):
        for frase in ("Cuales campos produjeron mas hoy?", "cuales campos produjeron mas?",
                      "cuales activos produjeron menos?"):
            rw = _continuacion(frase, ctx)
            assert rw is None, f"{frase!r} se reescribió a {rw!r} en vez de viajar entera"


def test_ranking_con_mes_sigue_igual():
    """Ya funcionaba (por el corte de 5 tokens). No debe cambiar."""
    assert _continuacion("Cuales campos produjeron mas en agosto?", _CTX_CUANT) is None


def test_continuacion_temporal_sigue_heredando():
    """REGRESIÓN (test_cuantificar_dia.py:705): lo que el drill hace bien no puede romperse."""
    for frase in ("y en mayo?", "y en junio", "y mayo?"):
        rw = _continuacion(frase, _CTX_CUANT)
        assert rw is not None and "RUBIALES" in rw, f"{frase!r} perdió el hilo"


def test_continuacion_acumulado_y_referencia_siguen_heredando():
    assert _continuacion("y el acumulado?", _CTX_CUANT) == "acumulado de RUBIALES"
    rw = _continuacion("vs operativo", _CTX_CUANT)
    assert rw is not None and "RUBIALES" in rw


def test_continuacion_estructural_sigue_heredando():
    """«¿a qué activo pertenece?» SÍ es una continuación con pronombre elidido."""
    assert _continuacion("a que activo pertenece?", _CTX_CUANT) == "que es RUBIALES"
    assert _continuacion("sus campos?", _CTX_CUANT) == "que es RUBIALES"


def test_produccion_que_menciona_campo_sigue_heredando():
    """REGRESIÓN CRÍTICA (test_cuantificar_dia.py:735): «campo» genérico NO es un ranking."""
    rw = _continuacion("produjo el campo en mayo", _CTX_CUANT)
    assert rw is not None and rw.startswith("produccion de"), \
        f"regresión: producción real bloqueada por la guarda de ranking: {rw!r}"


def test_drill_de_ranking_sigue_funcionando():
    """Las continuaciones de un ranking («y gas?», «los que menos») no deben cortarse."""
    ctx_rank = {"grupo": "cuantificar", "subgrupo": "ranking", "producto": "crudo",
                "direccion": "top", "nivel_ranking": "campo", "metrica": "real"}
    assert _continuacion("y gas?", ctx_rank) == "cuales campos son los mayores productores de gas"
    assert _continuacion("los que menos", ctx_rank) == "cuales campos son los menores productores de crudo"


def test_oferta_de_analizar_sigue_heredando():
    """V-01: el cierre de Analizar ofrece «¿qué campos explican el faltante?». Responder con esa
    frase NO es un ranking aunque el detector lo crea: debe seguir al drill de analizar."""
    esperado = "por que la produccion de CASTILLA esta corta"
    assert _continuacion("que campos explican el faltante", _CTX_ANALIZ) == esperado
    assert _continuacion("si", _CTX_ANALIZ) == esperado
