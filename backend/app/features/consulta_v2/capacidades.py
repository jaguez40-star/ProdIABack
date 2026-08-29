"""capacidades.py — detector determinista de preguntas sobre EL ASISTENTE MISMO.

Cuarto hermano de dominio.py (¿es del tema?), no_soportado.py (¿está construido?) e
incompleta.py (¿está completa la frase?). Este responde: ¿la pregunta es sobre MÍ?

Caso de origen (2026-08-25): «¿cuál es tu finalidad?» y «hola» caían en la rama OUT y
las redactaba respuesta_out.py, cuyo prompt tiene la orden literal de decir que el tema
«se sale del contexto de este asistente». El motor respondía que preguntarle qué sabe
hacer es un tema ajeno. Mismo bug de TRATO que originó incompleta.py: la clasificación
'desconocido' es CORRECTA, lo que estaba mal era la respuesta.

🔑 NO reclasifica. El grupo sigue siendo 'desconocido' — solo cambia el mensaje. Por eso
el golden (que solo asevera el grupo, run_golden.py) no puede romperse por este módulo.

🔑 Determinista, JAMÁS por el LLM. La respuesta a «qué sabes hacer» es un INVENTARIO de
capacidades: si lo redacta qwen2.5:3b promete lo que no existe (rangos de días,
trimestres, años) y no_soportado.py se lo niega al turno siguiente — el motor se
contradiría. Mismo argumento que consulta/meta.py:9-16.

🔑 El mensaje NUNCA termina en pregunta sí/no (regla H1, igual que no_soportado.py e
incompleta.py): un "sí" cae en el drill _AFIRM de maquina_q._continuacion y se
reescribe a "acumulado de {entidad}". El cierre pide un SUSTANTIVO.

⚠️ norm() NO retira signos de puntuación (solo pliega acentos y colapsa espacios):
«¡Hola!» normaliza a «¡HOLA!» con el signo PEGADO. Por eso _RX_SALUDO tolera signos de
apertura al inicio — verificado 2026-08-25: sin esa tolerancia «¡Hola!» NO matcheaba.
En _RX_CAPACIDADES no hace falta: \\b sí maneja la frontera entre '¿' y letra.
"""
import re

from app.features.consulta_v2.normaliza import norm

# --- Forma 'capacidades' -----------------------------------------------------------------
# ⚠️ SOLO «QUE ERES»/«QUIEN ERES» — jamás «QUE ES»/«QUIEN ES»: son patrones jerarquizar
# VIVOS (config/patrones_grupo.yaml → grupos.jerarquizar) y además maquina_q._continuacion
# reescribe a f"que es {ent}" en TRES ramas distintas. Capturarlos aquí rompería todo el
# drill estructural del motor. Es el falso positivo más caro posible.
_RX_CAPACIDADES = re.compile(
    r"\b(TU|TUS|SU|SUS)\s+(FINALIDAD|PROPOSITO|FUNCION|FUNCIONES|OBJETIVO|UTILIDAD|"
    r"CAPACIDADES|ALCANCE)\b|"
    r"\bPARA\s+QUE\s+(SIRVES|SIRVE|ESTAS|ERES)\b|"
    # [2026-08-25] `(MAS\s+)?` — «¿qué MÁS puedes hacer?» rompía la secuencia y caía al LLM.
    # Los verbos van con \w* para cubrir la conjugación (HACER/HACES, RESPONDER/RESPONDES).
    r"\bQUE\s+(MAS\s+)?(PUEDES|SABES)\s+(HACER|HACES|RESPONDER|DECIRME|CONTARME|OFRECER)\b|"
    r"\bQUE\s+HACES\b|"
    r"\b(EN|CON)\s+QUE\s+(ME\s+)?(PUEDES\s+)?AYUD\w+\b|"
    r"\bCOMO\s+(ME\s+)?(PUEDES\s+)?AYUD\w+\b|"
    r"\bQUIEN\s+ERES\b|\bQUE\s+ERES\b|"
    r"\bQUE\s+(PREGUNTAS|COSAS)\s+.{0,20}\b(HACER|RESPONDER|PREGUNTAR)\b|"
    r"\bDE\s+QUE\s+(ME\s+)?PUEDES\s+HABLAR\b|"
    # [2026-08-25] Familia TEMAS. Medido en la app: «¿Sobre qué temas puedo preguntarte?» y
    # «¿qué temas manejas?» caían al LLM, que respondía con el molde de "fuera de contexto"
    # a una pregunta que es exactamente la que este módulo existe para responder.
    # Se exige el verbo de interlocución (PREGUNTAR/HABLAR/CONSULTAR/MANEJAR/TRATAR/CUBRIR)
    # o el posesivo: «temas» a secas es sustantivo común y sin esa guarda capturaría
    # cualquier frase que lo mencione.
    r"\bQUE\s+TEMAS\b.{0,24}\b(PUEDO|PUEDES|MANEJAS|TRATAS|CUBRES|DOMINAS|SABES)\b|"
    r"\b(SOBRE|DE|EN)\s+QUE\s+(TEMAS?|ASUNTOS?)\b|"
    r"\b(TUS|SUS)\s+TEMAS\b|"
    # [2026-08-25] AYUDA/HELP a secas: es el reflejo universal del usuario perdido. Anclado
    # ^…$ como el saludo — «ayuda» sola es la petición; «ayuda con el gap de Castilla» es
    # una pregunta de dominio y NO debe caer aquí (por eso el ancla, no un \b suelto).
    r"^[¡¿\s]*(AYUDA|AYUDAME|HELP|SOCORRO|NO\s+SE\s+QUE\s+PREGUNTAR|"
    r"QUE\s+LE\s+PREGUNTO|QUE\s+TE\s+PREGUNTO)[\s,\.!¡¿\?]*$")

# --- Forma 'saludo' ----------------------------------------------------------------------
# ANCLADO ^...$ a propósito: «hola» es un saludo; «hola, ¿cuánto produjo Castilla?» NO —
# lleva una pregunta real detrás y debe seguir su curso normal. El ancla lo resuelve sin
# excepciones. El prefijo [¡¿\s]* es el fix del hallazgo sobre norm() (ver docstring).
_RX_SALUDO = re.compile(
    r"^[¡¿\s]*(HOLA|BUENAS|BUEN\s+DIA|BUENOS\s+DIAS|BUENAS\s+TARDES|BUENAS\s+NOCHES|"
    r"QUE\s+TAL|QUE\s+HUBO|QUIUBO|SALUDOS|HEY|EPA)"
    r"[\s,\.!¡¿\?]*$")


def detectar(texto, hay_entidad):
    """'capacidades' | 'saludo' | None. Determinista y puro.

    `hay_entidad` la calcula el LLAMADOR (maquina_q._clasificar_core ya la tiene de
    detectar_entidad) — mismo criterio que incompleta.detectar, que recibe `hay_entidad`
    y `nivel` ya calculados en vez de recalcularlos.

    GUARDA DE ENTIDAD: si el texto nombra una entidad del catálogo NO es meta-bot.
    «¿qué puedes decirme de Castilla?» es una pregunta de dominio, no sobre el asistente.

    Orden: capacidades ANTES que saludo. El ancla ^...$ del saludo ya descarta
    «hola, ¿qué puedes hacer?», pero el orden lo deja explícito.
    """
    if hay_entidad:
        return None
    t = norm(texto or "")
    if not t:
        return None
    if _RX_CAPACIDADES.search(t):
        return "capacidades"
    if _RX_SALUDO.match(t):
        return "saludo"
    return None


# --- Mensajes ----------------------------------------------------------------------------
# Cuatro decisiones dentro del texto:
#   1. EJEMPLOS COPIABLES, no categorías abstractas. "cifras de producción" no enseña a
#      preguntar; «¿Cuánto crudo produjo Rubiales?» sí. Los ejemplos se eligieron entre
#      formas que el motor HOY resuelve (verificadas contra patrones_grupo.yaml y el
#      golden), no entre formas plausibles.
#   2. REGLA H1: cierra SIN pregunta sí/no. «¿por dónde arrancamos?» es una pregunta
#      ABIERTA — no cae en el drill _AFIRM de maquina_q._continuacion, que solo reacciona
#      a "sí"/"dale"/"ok" y devolvería un acumulado.
#   3. NO PROMETE lo que no hay: sin rangos de días, sin trimestres, sin semanas, sin
#      comparar años — no_soportado.py los rechaza, y ofrecerlos aquí sería contradecirse
#      un turno después.
#   4. FORMATO (2026-08-25, decisión del usuario): una línea por frente, con el nombre en
#      NEGRITA. El realce usa el marcador ⟦…⟧ del propio motor, que el frontend convierte
#      en <strong> (multitab_shell.js::__cnMarcador). NO se usa markdown ni HTML: el
#      mensaje pasa por esc() antes de pintarse y saldría literal. Los \n se respetan
#      porque .v2-msg lleva white-space:pre-line (colapsable.css:1917).
#      ⚠️ Cada ⟦…⟧ debe caber en UNA línea: el regex de __cnMarcador es [^⟦⟧\n]* — si el
#      marcador cruzara un \n, el símbolo crudo quedaría a la vista.
#   Ambas formas comparten el cuerpo (_LINEAS_FRENTES): el saludo solo cambia la cabecera.
_LINEAS_FRENTES = (
    "⟦Estructura⟧ — cómo se organiza la operación: campos, activos, gerencias, pozos. "
    "(«¿Qué campos tiene Castilla?»)\n"
    "⟦Cifras⟧ — crudo, gas y blancos: del mes, acumulado, variación, rankings y vs "
    "presupuesto. («¿Cuánto crudo produjo Rubiales?»)\n"
    "⟦Análisis⟧ — brechas, causas, diferidas y mantenimientos, proyección de cierre y "
    "economía (EBITDA/NOPAT). («¿A qué se debe el gap de crudo?» · «¿Qué mantenimientos "
    "hubo en Castilla?»)\n\n"
    "Pregúntame en lenguaje natural, ¿por dónde arrancamos?")

_MSG_CAPACIDADES = (
    "Soy el asistente de producción de Ecopetrol y trabajo sobre los reportes diarios. "
    "Te sirvo en tres frentes:\n\n" + _LINEAS_FRENTES)

_MSG_SALUDO = (
    "Hola. Soy el asistente de producción de Ecopetrol y trabajo sobre los reportes "
    "diarios. Te sirvo en tres frentes:\n\n" + _LINEAS_FRENTES)

_MENSAJES = {"capacidades": _MSG_CAPACIDADES, "saludo": _MSG_SALUDO}


def mensaje(codigo, usuario=None):
    """Texto determinista de la forma detectada. Jamás pasa por el LLM.

    `usuario` es el nombre que llega en el body del POST (api.py::Preguntar.usuario). Si
    viene, se antepone como vocativo EN PYTHON.
    ⚠️ NO aplica la advertencia de consulta/meta.py:18-20 sobre __cnConNombre y el
    guillemot inicial: ese riel es del motor v1 (status 'pendiente'). En v2 el mensaje se
    sirve tal cual.
    """
    txt = _MENSAJES.get(codigo, _MSG_CAPACIDADES)
    if usuario:
        # El saludo ya arranca con "Hola." → se funde el nombre en él en vez de duplicarlo.
        if codigo == "saludo":
            return txt.replace("Hola.", f"Hola, {usuario}.", 1)
        return f"{usuario}, {txt[0].lower()}{txt[1:]}"
    return txt
