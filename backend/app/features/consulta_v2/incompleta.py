"""incompleta.py — detector determinista de preguntas EN dominio y CON capacidad, pero MAL
FORMADAS por falta de complemento.

Tercer hermano de dominio.py (¿es del tema?) y no_soportado.py (¿está construido?). Este
responde una pregunta distinta: ¿la frase está completa?

Caso de origen (real, 2026-08-21): tras ofrecer "¿Quieres ver la producción de CASTILLA o
consultar otro campo o activo?", el usuario escribió "sí muéstrame". El verbo queda SIN
OBJETO: no dice qué mostrar. Resolverlo por contexto sería adivinar el sujeto — decisión
del usuario: eso es peor que preguntar. La clasificación 'desconocido' es CORRECTA; lo que
estaba mal era el TRATO (se respondía "fuera de mi ámbito" a una pregunta del tema).

🔑 NO reclasifica. El grupo sigue siendo 'desconocido' — solo cambia el mensaje. Por eso el
golden (que solo asevera el grupo, run_golden.py) no puede romperse por este módulo.

🔑 Verbo ⇒ COMPLEMENTO, no verbo ⇒ entidad. "muéstrame el desempeño del mes" es global y
válida: no tiene entidad pero sí objeto de dominio. Sin la tercera condición (nivel_dominio
is None) esta regla rechazaría todo el tráfico global.

🔑 El mensaje NUNCA termina en una pregunta sí/no (H1, misma regla que no_soportado.py): un
"sí" cae en el drill de afirmación de maquina_q._continuacion. El cierre pide un SUSTANTIVO.

Regex con \\b sobre texto NORMALIZADO (norm(): UPPER, sin acentos). Compilados en el import.
"""
import re

from app.features.consulta_v2.normaliza import norm

# Verbos de acción, en tres familias: mostrar/entregar, graficar/calcular y NARRAR. La tercera
# (PRESENTAME/CUENTAME/EXPLICAME) la añadió el usuario y es la que más se parece a la frase que
# originó el módulo: son los verbos que más invitan a una respuesta larga, y por tanto los que
# más se benefician de que el motor pida el sujeto ANTES de arrancar.
#
# EXCLUIDOS a propósito (no añadir sin releer estas razones):
#   DALE, LISTO  -> viven en maquina_q._AFIRM; capturarlos aquí se los robaría al drill de
#                   afirmación de _continuacion, que es quien SÍ sabe resolverlos por contexto.
#   CONSULTA     -> colisiona con el nombre de la pestaña y con el lenguaje común del producto.
#   LISTA (sola) -> sustantivo frecuente ("la lista de campos"); solo se acepta LISTAME.
#   CUENTA (sola)-> sustantivo DEL PROPIO DOMINIO ("cuenta contable", "cuenta de resultados").
#                   Falso positivo garantizado; solo se acepta CUENTAME.
#   ABRE, SACA   -> valor marginal frente al riesgo de falso positivo.
_RX_VERBO_ACCION = re.compile(
    r"\b(MUESTRA|MUESTRAME|MOSTRAR|MOSTRARME|ENSENAME|ENSENAR|"
    r"VER|VEAMOS|VERLO|VERLA|DAME|DAMELO|DAMELA|TRAEME|TRAER|"
    r"GRAFICA|GRAFICAME|GRAFIQUEME|COMPARA|COMPARAME|"
    r"CALCULA|CALCULAME|LISTAME|SACAME|PONME|DESPLIEGA|"
    r"PRESENTA|PRESENTAME|CUENTAME|EXPLICA|EXPLICAME)\b")

_COD = "accion_sin_objeto"


def detectar(texto, hay_entidad, nivel):
    """'accion_sin_objeto' si la frase invoca una acción sin nada sobre lo que recaiga.

    Las tres condiciones son conjuntivas; la TERCERA es la que evita el falso positivo del
    tráfico GLOBAL, que es el riesgo real de esta regla:
      1. hay verbo de acción
      2. hay_entidad is False   -> no nombra una entidad del catálogo
      3. nivel is None          -> tampoco trae objeto de dominio (ni fuerte ni estructural)

    "muéstrame el desempeño del mes" (sin entidad, nivel='fuerte') NO dispara: tiene objeto.
    "muéstrame Castilla" (hay_entidad=True) NO dispara: tiene instancia.
    "sí muéstrame" (ninguna de las dos) SÍ dispara.

    Recibe `hay_entidad` y `nivel` YA CALCULADOS por el llamador en vez de llamar a
    detectar_entidad()/nivel_dominio() aquí: maquina_q._clasificar_core ya los tiene, y
    repetirlos sería trabajo doble además de acoplar este módulo puro al catálogo.
    """
    if hay_entidad or nivel is not None:
        return None
    return _COD if _RX_VERBO_ACCION.search(norm(texto or "")) else None


def mensaje(codigo, entidad_ctx=None):
    """Pide el complemento que falta. Determinista — jamás pasa por el LLM.

    Con entidad en el hilo se NOMBRA como candidata, pero como candidata y no como
    resolución: la decisión vuelve al usuario. Esa es justamente la diferencia entre
    repreguntar y adivinar, y es lo que se pidió.

    H1: el cierre pide un SUSTANTIVO, nunca un sí/no. (Si aun así el usuario responde "sí",
    el drill `ofrece_produccion` de maquina_q._continuacion sigue vivo: un turno 'desconocido'
    NO reescribe _CTX, así que el contexto anterior sobrevive y lo resuelve.)
    """
    del codigo   # una sola forma por ahora; el parámetro mantiene la firma de no_soportado
    cabeza = "Me pediste que te muestre algo, pero no dijiste sobre qué."
    if entidad_ctx:
        return (f"{cabeza} Puedo darte la producción de {entidad_ctx}, "
                "o nómbrame otro campo, activo o gerencia.")
    return (f"{cabeza} Nómbrame un campo, activo o gerencia, "
            "o dime si quieres producción, estructura o análisis.")
