"""Tests PUROS (sin BD, sin LLM) de la Pieza B (no_soportado) y de la Pieza A (contexto en OUT)."""
from app.features.consulta_v2 import no_soportado
from app.features.consulta_v2.respuesta_out import _linea_contexto


# --- Pieza B: detectar() reconoce las formas no soportadas -------------------------------------
def test_detecta_rango_de_dias():
    assert no_soportado.detectar("entre el 5 y el 10 de mayo") == "rango_dias"
    assert no_soportado.detectar("del 5 al 10") == "rango_dias"
    # Caso REAL del HALLAZGO (con el hilo ya resuelto en una entidad):
    assert no_soportado.detectar("En mayo, los 17 días ¿cuánto ha producido?") == "rango_dias"
    assert no_soportado.detectar("primeros 10 dias") == "rango_dias"


def test_detecta_trimestre_anio_semana():
    assert no_soportado.detectar("cuanto en el primer trimestre") == "trimestre"
    assert no_soportado.detectar("produccion anual") == "anio"
    assert no_soportado.detectar("todo el año") == "anio"
    assert no_soportado.detectar("y la semana pasada?") == "semana"


def test_negativos_no_soportado():
    # Lo que Cuantificar SÍ soporta no debe marcarse como no-soportado.
    assert no_soportado.detectar("cuanto produjo en mayo") is None          # N1 mes
    assert no_soportado.detectar("acumulado del año") is None               # N2 acumulado
    assert no_soportado.detectar("") is None
    assert no_soportado.detectar("hola") is None


def test_detecta_dia_puntual():
    """[2026-08-24] El hueco más silencioso: sin esta forma, «¿cuánto produjo Castilla ayer?»
    NO decía "no puedo" — devolvía la cifra del MES COMPLETO como si fuera lo pedido."""
    assert no_soportado.detectar("¿cuánto crudo produjo Castilla ayer?") == "dia"
    assert no_soportado.detectar("cuanto produjo hoy") == "dia"
    assert no_soportado.detectar("y anteayer?") == "dia"
    assert no_soportado.detectar("¿cuál fue el volumen el 15?") == "dia"
    # El peor de todos: devolvía «mayo» y contestaba el mes entero.
    assert no_soportado.detectar("cuanto produjo el 15 de mayo") == "dia"
    assert no_soportado.detectar("cuanto produjo el lunes") == "dia"
    assert no_soportado.detectar("el día 3") == "dia"


def test_dia_no_le_quita_prioridad_a_las_formas_previas():
    """`dia` va LAST en _FORMAS a propósito: las 4 formas anteriores conservan su código.
    'del 1 al 15' y 'entre el 5 y el 10' contienen texto que el regex de `dia` también
    atraparía — deben seguir siendo rango_dias."""
    assert no_soportado.detectar("del 1 al 15") == "rango_dias"
    assert no_soportado.detectar("entre el 5 y el 10 de mayo") == "rango_dias"
    assert no_soportado.detectar("En mayo, los 17 días ¿cuánto ha producido?") == "rango_dias"


def test_h4_acumulado_hasta_hoy_no_es_dia_puntual():
    """H4 (gemelo de H2): 'hasta hoy' trae HOY pero pide el ACUMULADO (N2), que SÍ se soporta.
    Sin la guarda, «el acumulado hasta hoy» se rechazaría como si fuera un día suelto."""
    assert no_soportado.detectar("¿cuál es el acumulado hasta hoy?") is None
    assert no_soportado.detectar("producción acumulada hasta hoy") is None
    assert no_soportado.detectar("en lo que va del año hasta hoy") is None


def test_dia_no_dispara_con_digitos_ajenos():
    """El regex exige EL + 1-2 dígitos (o una palabra de día). Los números de un ranking, un
    año de 4 cifras o 'mes a mes' no son un día puntual."""
    assert no_soportado.detectar("los 5 campos que más crudo producen") is None
    assert no_soportado.detectar("top 5 campos") is None
    assert no_soportado.detectar("cuanto produjo en abril 2026") is None
    assert no_soportado.detectar("dame la producción mes a mes") is None
    assert no_soportado.detectar("¿cómo varió día a día?") is None
    assert no_soportado.detectar("¿cómo vamos contra el P50?") is None


def test_detecta_selector_temporal():
    """[2026-08-24] "¿qué día produjo más?" es un argmax sobre la curva diaria: la RESPUESTA
    es una fecha, así que hereda las limitaciones del grano día. NO es el ranking N5, donde
    se ordenan ENTIDADES por producción — aquí la entidad está fija y se ordena el TIEMPO."""
    assert no_soportado.detectar("¿el mejor día de Castilla este mes?") == "selector_dia"
    assert no_soportado.detectar("el peor día del mes") == "selector_dia"
    assert no_soportado.detectar("¿qué día produjo más Castilla?") == "selector_dia"
    assert no_soportado.detectar("el día de mayor producción") == "selector_dia"
    # El ranking de ENTIDADES (N5) SÍ se soporta y no debe caer aquí.
    assert no_soportado.detectar("los 5 campos que más crudo producen") is None
    assert no_soportado.detectar("¿qué campo produjo más en mayo?") is None


def test_h2_promedio_anual_es_referencia_soportada():
    # H2: 'promedio anual'/'promedio del año' es la referencia promedio_anio (Fase 4) → NO es 'anio'.
    assert no_soportado.detectar("contra el promedio anual") is None
    assert no_soportado.detectar("vs el promedio del año") is None


# --- Pieza B: mensaje() honesto, sin pregunta sí/no (H1) --------------------------------------
def test_mensaje_nombra_entidad_y_no_termina_en_si_no():
    m = no_soportado.mensaje("rango_dias", "RUBIALES")
    assert "RUBIALES" in m
    assert "rango de días" in m and "mes completo" in m
    # H1: un "¿Quieres…?" haría que un "sí" caiga en el drill de acumulado de _continuacion.
    assert "¿Quieres" not in m
    # Determinista: la plantilla no inventa cifras (la entidad de prueba no tiene dígitos).
    assert not any(ch.isdigit() for ch in m)


# --- Pieza A: la línea de contexto solo aparece si hay entidad --------------------------------
def test_linea_contexto():
    assert _linea_contexto(None) == ""
    assert _linea_contexto({}) == ""
    assert _linea_contexto({"nivel": "campo"}) == ""            # sin 'entidad' → vacío
    linea = _linea_contexto({"entidad": "RUBIALES", "producto": "gas"})
    assert "RUBIALES" in linea and "gas" in linea
    # crudo es el default → no se explicita el producto (ruido innecesario en el prompt).
    assert "(producto" not in _linea_contexto({"entidad": "CASTILLA", "producto": "crudo"})
