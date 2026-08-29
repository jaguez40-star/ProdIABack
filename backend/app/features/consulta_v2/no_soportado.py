"""no_soportado.py — detector determinista de FORMAS de pregunta EN dominio pero fuera de capacidad.

Espejo conceptual de dominio.py: módulo PURO (sin BD, sin LLM), testeable igual que patrones.py.
NO decide dominio — eso ya lo hizo el filtro de dominio. Solo reconoce, entre las preguntas que YA
cayeron en 'desconocido', las que tienen la FORMA de una capacidad que el motor todavía no construye.

FUENTE DECLARATIVA (H7): la lista de capacidades ausentes vive en prosa en
`config/variables_cuantificables.yaml` → sección `no_soportado:` ("año / trimestre / semana",
motivo "v1 solo parsea MES"). Ese YAML NO se puede usar para hacer matching (es prosa, no patrones),
así que aquí viven los REGEX equivalentes. Si el YAML gana o pierde una capacidad, ACTUALIZAR AMBOS.

🔑 Este detector solo se CONSULTA cuando hay contexto de entidad (el hilo confirma dominio). Razón
(verificada 2026-08-03): en arranque frío "¿cuántos días tiene un trimestre?" (ajena) y "del primer
trimestre ¿cuánto?" (dominio) traen la MISMA palabra — sin LLM no se puede afirmar "no soportado" con
honestidad. Con contexto sí. El gate vive en maquina_q._clasificar_core, no aquí.

🔑 El mensaje NUNCA termina en una pregunta sí/no (H1): un "sí" del usuario cae en el drill de
afirmación de maquina_q._continuacion (`t in _AFIRM` + ctx cuantificar) y se reescribe a
"acumulado de {entidad}" — es decir, entregaría el ACUMULADO en vez de lo ofrecido. Por eso el cierre
invita a una frase explícita.

Regex con \\b sobre texto NORMALIZADO (norm(): UPPER, sin acentos, espacios colapsados). norm() NO
retira signos ¿?, pero \\b los maneja (frontera entre '¿' y letra). Compilados en el import.
"""
import re

from app.features.consulta_v2.normaliza import norm

# H2: "promedio anual"/"promedio del año" es la referencia SOPORTADA `promedio_anio`
# (cuantificar/slots.py::_REF_MATCH, Fase 4) → si el texto trae PROMEDIO, la forma `anio` NO aplica.
_RX_PROMEDIO = re.compile(r"\bPROMEDIO\b")

# [2026-08-24] H4 — gemelo de H2 para la forma `dia`: "hasta hoy"/"acumulado a hoy" traen HOY pero
# piden el ACUMULADO (N2), que SÍ se soporta. Sin esta guarda, "el acumulado hasta hoy" se
# rechazaría como si fuera un día puntual. Mismas palabras que cuantificar/slots.py::_ACUM_KW.
_RX_ACUMULADO = re.compile(r"\bACUMULAD[OA]\b|\bEN\s+LO\s+QUE\s+VA\b|\bYTD\b|"
                           r"\bHASTA\s+(AHORA|HOY|LA\s+FECHA)\b|\bEN\s+TOTAL\b")

# (codigo, regex, que_pidio, que_si_puedo, sugerencia_de_reformulacion)
# H3: sin abreviaturas de trimestre ("4T"/"Q1"): valor marginal y falsos positivos contra el catálogo.
_FORMAS = [
    ("rango_dias",
     re.compile(r"\bENTRE\s+EL\s+\d+\s+Y\s+EL\s+\d+|\bDEL\s+\d+\s+AL\s+\d+|"
                r"\bLOS\s+\d+\s+DIAS|\b\d+\s+DIAS\s+DE\b|\bPRIMEROS\s+\d+\s+DIAS"),
     "un rango de días", "el mes completo",
     "Si me nombras el mes, te doy esa cifra."),
    ("trimestre",
     re.compile(r"\bTRIMESTRE|\bTRIMESTRAL"),
     "un trimestre", "un mes puntual o el acumulado del año",
     "Dime el mes que te interesa, o pídeme el acumulado del año."),
    ("anio",
     re.compile(r"\bTODO\s+EL\s+ANO|\bEN\s+EL\s+ANO\s+20\d\d|\bDURANTE\s+20\d\d|\bANUAL\b"),
     "un año completo", "un mes puntual o el acumulado del año",
     "Dime el mes que te interesa, o pídeme el acumulado del año."),
    ("semana",
     re.compile(r"\bSEMANA|\bSEMANAL"),
     "una semana", "el mes completo",
     "Si me nombras el mes, te doy esa cifra."),
    # [2026-08-24] DÍA PUNTUAL — el hueco gemelo de rango_dias/semana, y el más común de todos:
    # "¿cuánto produjo Castilla AYER?". Medido antes del fix: slots._periodo_texto no reconoce
    # ninguna forma de día → devolvía None → el motor respondía EL MES ENTERO como si fuera lo
    # pedido (bug #5 en su forma más silenciosa: no dice "no puedo", da otra cifra). "el 15 de
    # mayo" era peor todavía: devolvía «mayo» y contestaba el mes completo.
    #
    # Se RECHAZA, no se calcula, por tres hechos verificados contra la BD (2026-08-24):
    #   1. core.fact_produccion_dia_ecp NO tiene columna escenario_id → a grano día solo hay REAL,
    #      sin PPTO. Toda respuesta de cuantificar se construye sobre "X% del presupuesto"; a nivel
    #      día esa comparación no existe.
    #   2. El dato diario termina el 2026-05-17 y la fecha de hoy es 2026-08-24 → 99 días de
    #      desfase. "ayer"/"hoy" NO tienen dato: calcularlos daría vacío, no una cifra.
    #   3. El catálogo marca produccion_blancos.granos.dia con confianza:no ("×2 irreconciliable").
    # Si algún día entra el PPTO diario y el dato se pone al día, esta forma sale de aquí y pasa a
    # ser un nivel propio del ejecutor — igual que hizo N2 con el acumulado.
    #
    # Va LAST a propósito: `detectar` devuelve la PRIMERA forma que calza, así que las 4 de arriba
    # conservan su prioridad intacta ("del 1 al 15" sigue siendo rango_dias, no dia).
    ("dia",
     re.compile(r"\bAYER\b|\bANTEAYER\b|\bANTIER\b|\bANOCHE\b|\bHOY\b|"
                r"\bEL\s+DIA\s+\d{1,2}\b|\b(ESTE|ULTIMO)\s+DIA\b|"
                r"\bEL\s+\d{1,2}\s+DE\s+(ENERO|FEBRERO|MARZO|ABRIL|MAYO|JUNIO|JULIO|AGOSTO|"
                r"SEPTIEMBRE|SETIEMBRE|OCTUBRE|NOVIEMBRE|DICIEMBRE)\b|"
                r"\bEL\s+(LUNES|MARTES|MIERCOLES|JUEVES|VIERNES|SABADO|DOMINGO)\b|"
                r"\bEL\s+\d{1,2}\b"),
     "un día puntual", "el mes completo",
     "Si me nombras el mes, te doy esa cifra."),
    # [2026-08-24] SELECTOR TEMPORAL — "¿qué día produjo más Castilla?" / "el mejor día del mes".
    # Es un argmax sobre la curva diaria: la RESPUESTA es una fecha, así que hereda las mismas
    # tres limitaciones del grano día (ver la nota de `dia` arriba). NO es el ranking N5, que
    # ordena ENTIDADES por producción — aquí la entidad está fija y lo que se ordena es el tiempo.
    # Forma propia (no se mete en el regex de `dia`) para que el mensaje diga qué se pidió.
    # ⚠️ [2026-08-26 · QV2-DIA-SEL] Este regex NO es el criterio autoritativo del selector de
    # día: lo es `cuantificar.slots.detectar_dia`, que además resuelve la DIRECCIÓN (mín/máx).
    # Era una copia del mismo criterio y quedó desincronizada —«qué DÍAS fue la producción más
    # baja» no casa aquí—, lo que en el fork de RANKING devolvía un ranking mensual en silencio.
    # Esa guarda (respuesta_cuantificar._forma_no_soportada_ranking) ya consulta al detector real.
    # Aquí queda solo para la rama OUT, donde maquina_q.py:504-505 neutraliza el resultado con el
    # mismo detector: verificado que ambos caminos convergen. NO ampliar este regex — si hace
    # falta más cobertura, se amplía `slots._RX_SELECTOR` y esta entrada seguirá siendo correcta.
    ("selector_dia",
     re.compile(r"\b(MEJOR|PEOR)\s+DIA\b|\bQUE\s+DIA\s+.{0,24}\b(MAS|MENOS)\b|"
                r"\bDIA\s+DE\s+(MAYOR|MENOR)\b|\b(MAS|MENOS)\s+PRODUJO\s+EN\s+EL\s+MES\b"),
     "el día de mayor o menor producción", "el total del mes",
     "Si me nombras el mes, te doy esa cifra."),
]


# [2026-08-26 · QV2-DIA-SEL] Formas que NO nacen de un regex de este módulo: las reconoce el
# resolutor real (`cuantificar.slots.detectar_dia`) y se nombran aquí solo para que el rechazo
# diga QUÉ se pidió. `ranking_dia` es «qué campos tuvieron los peores días»: ordenar ENTIDADES
# por su mejor/peor día. Antes heredaba el texto de `selector_dia`, escrito para una entidad FIJA
# («¿el mejor día de Castilla?»), y respondía «me pediste el día de mayor o menor producción y
# solo puedo darte el total del mes» — ni se pidió un día suelto, ni el total del mes sirve de
# nada a quien pregunta por campos. Rechazar estaba bien; explicarlo así, no.
_FORMAS_SIN_REGEX = {
    "ranking_dia": ("los campos ordenados por su mejor o peor día",
                    "el ranking del mes completo",
                    "Si quieres, te doy el mejor o peor día de un campo en concreto."),
}


def detectar(texto: str):
    """Código de la 1ª forma no-soportada que calza, o None. Determinista y puro."""
    t = norm(texto or "")
    for cod, rx, _pidio, _puedo, _sug in _FORMAS:
        if cod == "anio" and _RX_PROMEDIO.search(t):
            continue                      # H2: es la referencia promedio_anio, que SÍ se soporta
        if cod == "dia" and _RX_ACUMULADO.search(t):
            continue                      # H4: "acumulado hasta hoy" pide N2, no un día puntual
        if rx.search(t):
            return cod
    return None


def mensaje(codigo: str, entidad: str) -> str:
    """Rechazo honesto (molde de cuantificar/ejecutor): nombra la entidad, dice qué pidió, qué SÍ
    puede y cómo reformular. Determinista — jamás pasa por el LLM. Sin pregunta sí/no (H1)."""
    tabla = {c: (pidio, puedo, sug) for c, _rx, pidio, puedo, sug in _FORMAS}
    tabla.update(_FORMAS_SIN_REGEX)
    pidio, puedo, sug = tabla.get(
        codigo, ("ese periodo", "el mes completo", "Si me nombras el mes, te doy esa cifra."))
    return (f"Sobre {entidad}: me pediste {pidio} y por ahora solo puedo darte {puedo}. {sug}")
