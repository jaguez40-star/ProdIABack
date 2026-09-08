"""Tras una FICHA jerárquica, las continuaciones de cuantificar funcionan (2026-09-08 · DRILL-FICHA).

Bug real visto en la app: ficha de CASTILLA («¿a qué activo pertenece?») y luego «¿y el
acumulado?» -> «No logré entender bien tu pregunta». Las 5 ramas de `_continuacion` que saben
heredar la entidad exigían `ctx["grupo"] == "cuantificar"`, y el ctx de una ficha no lleva esa
clave: con ese ctx morían TODAS las continuaciones, no solo el acumulado.

El punto delicado (H-03 del plan) es el «sí»: acepta la oferta que se le hizo, y cada cierre
ofrece algo distinto. Tras cuantificar, el acumulado; tras una ficha, la producción. Los dos
tests espejo de la sección "lo que NO debe cambiar" fijan esa asimetría.

`_continuacion` es PURA (sin BD ni LLM): recibe el ctx como argumento.
"""
from app.features.consulta_v2.maquina_q import _continuacion

# ctx que deja una ficha jerárquica (respuesta_jerarquizar.py:720-730). SIN clave "grupo",
# SIN "producto" y SIN "periodo_ctx": por eso las ramas heredan "crudo" y ningún mes.
_FICHA = {"entidad": "CASTILLA", "nivel": "campo", "hijos": ["CASTILLA NORTE"],
          "ofrece_produccion": True}
# ctx de cuantificar, para comprobar que lo que ya funcionaba no cambia.
_CUANT = {"grupo": "cuantificar", "entidad": "CASTILLA", "producto": "crudo",
          "periodo_ctx": None}
# ctx de analizar: sus continuaciones son suyas (rama :284, que corta siempre).
_ANALIZ = {"grupo": "analizar", "entidad": "CASTILLA", "sub": "proyeccion", "producto": None}


# --- El bug que se arregla -------------------------------------------------------------

def test_acumulado_tras_ficha():
    """El caso exacto que falló en la app."""
    for frase in ("y el acumulado?", "el acumulado", "y el acumulado del ano?"):
        assert _continuacion(frase, _FICHA) == "acumulado de CASTILLA", \
            f"{frase!r} no heredó la entidad de la ficha"


def test_otro_mes_tras_ficha():
    """No era solo el acumulado: la continuación temporal también moría."""
    for frase in ("y en junio?", "y en mayo?", "y mayo?"):
        rw = _continuacion(frase, _FICHA)
        assert rw is not None and "CASTILLA" in rw, f"{frase!r} perdió el hilo: {rw!r}"


def test_referencia_tras_ficha():
    rw = _continuacion("vs operativo", _FICHA)
    assert rw is not None and "CASTILLA" in rw


def test_acumulado_largo_tras_ficha():
    """Excepción de longitud (>5 y <=8 tokens) con el ctx de ficha."""
    assert _continuacion("si dame el acumulado del ano por favor", _FICHA) == \
        "acumulado de CASTILLA"


# --- Lo que NO debe cambiar (H-03: la asimetría del «sí») -------------------------------

def test_si_tras_ficha_sigue_dando_produccion():
    """🔴 REGRESIÓN. Medido ANTES del cambio: «claro» con ctx de ficha ya devolvía
    «produccion de CASTILLA». La ficha ofreció la PRODUCCIÓN, no el acumulado. Si el
    `t in _AFIRM` de la rama del acumulado se hubiera ampliado, este test fallaría."""
    for frase in ("si", "claro", "dale", "ok"):
        assert _continuacion(frase, _FICHA) == "produccion de CASTILLA", \
            f"{frase!r} tras una ficha debe dar la producción, no el acumulado"


def test_si_tras_cuantificar_sigue_dando_acumulado():
    """El espejo: tras un N1 de cuantificar, la oferta abierta ES el acumulado del año."""
    for frase in ("si", "claro", "dale"):
        assert _continuacion(frase, _CUANT) == "acumulado de CASTILLA"


def test_estructural_tras_ficha_sigue_igual():
    """«¿y sus campos?» sigue siendo estructural, no una consulta de producción."""
    assert _continuacion("sus campos?", _FICHA) == "que es CASTILLA"


def test_analizar_conserva_sus_continuaciones():
    """Su rama (:284) corta siempre con return propio y va ANTES que las ampliadas."""
    esperado = "por que la produccion de CASTILLA esta corta"
    assert _continuacion("si", _ANALIZ) == esperado
    assert _continuacion("que campos explican el faltante", _ANALIZ) == esperado


def test_guardas_siguen_activas_con_ficha():
    """H-06: las guardas de 37ac31f corren ANTES y no se debilitan al ampliar las ramas."""
    assert _continuacion("Cuanto produjimos en abril?", _FICHA) is None    # sujeto propio
    assert _continuacion("Cuales campos produjeron mas hoy?", _FICHA) is None  # ranking


def test_ranking_no_rompe_por_falta_de_entidad():
    """H-07: el ctx de ranking NO lleva "entidad". `_drill_cuant` debe darlo por False y dejar
    que su propia rama lo atienda, sin KeyError."""
    ctx_rank = {"grupo": "cuantificar", "subgrupo": "ranking", "producto": "crudo",
                "direccion": "top", "nivel_ranking": "campo", "metrica": "real"}
    assert _continuacion("y gas?", ctx_rank) == "cuales campos son los mayores productores de gas"
    assert _continuacion("los que menos", ctx_rank) == \
        "cuales campos son los menores productores de crudo"
