"""cuantificar/slots.py — aterrizaje de slots contra el catálogo (Motor Q v2, Grupo 2).

Fase 1-3 es 100% DETERMINISTA: no hace falta el LLM para los slots. Los grados de libertad del
usuario son EL MES, EL NIVEL TEMPORAL (N1 puntual/N2 acumulado/N3 serie/N4 variación) y EL PRODUCTO
(crudo/gas/blancos), todos por diccionario de palabras normalizado. Lo demás es default del catálogo
(referencia=PPTO).

El PRODUCTO se aterriza contra `config/variables_cuantificables.yaml` (catalogo.get()): de ahí sale
la UNIDAD (gas=MSCF, crudo/blancos=bbl) y, si el grano-mes es de confianza MEDIA (blancos), el DESCARGO
de honestidad que el ejecutor añadirá a los avisos. Default de producto = crudo (Fase 2: el "producto
por volumen dominante" queda para una fase posterior — exige calcular los 3 productos antes de decidir).
"""
import datetime as _dt
import re

from app.features.consulta_v2.normaliza import norm
from app.features.consulta_v2.cuantificar import catalogo as _catalogo

# HE7: en forma NORMALIZADA (norm = MAYÚSCULAS sin tildes: "año"->"ANO").
# AF-4.9 (revisado): "DEL ANO"/"EN EL ANO" son señales DÉBILES — pueden ser parte de una frase de
# REFERENCIA que también contiene "año" ("promedio del año", "promedio anual"), sin que el usuario
# pida un acumulado. El resto son señales FUERTES: inequívocas, incluso si el texto ADEMÁS nombra
# una referencia (bug real, 2026-08-02: "la producción ACUMULADA de Rubiales... por debajo de su
# promedio anual" SÍ pide el acumulado, con el promedio como referencia — el override de abajo
# forzaba N1 y lo perdía). Ver el uso de ambos conjuntos en extraer_slots.
_ACUM_KW_DEBIL = ("EN EL ANO", "DEL ANO")
_ACUM_KW_FUERTE = ("ACUMULADO", "ACUMULADA", "EN LO QUE VA", "YTD", "HASTA AHORA", "EN TOTAL", "TOTAL DEL ANO")
_ACUM_KW = _ACUM_KW_FUERTE + _ACUM_KW_DEBIL   # unión — la usa _nivel_temporal, sin distinguir origen

# Fase 3 — N3 (serie) y N4 (variación). AF-3.7: TOKEN para palabras sueltas (evita "BAJO"∈"trabajo",
# "VARIO"∈"varios"); FRASE (substring) para multi-palabra. Sin bare "MES"/"MENSUAL" (pisarían N1).
_VAR_WORDS = {"VARIACION", "VARIO", "VARIARON", "CAMBIO", "CAMBIARON",
              "SUBIO", "BAJO", "CRECIO", "CAYO", "DELTA"}
_VAR_PHRASES = ("DE UN MES A OTRO", "DIFERENCIA ENTRE MESES")
_SERIE_WORDS = {"SERIE", "EVOLUCION", "MENSUALES"}
_SERIE_PHRASES = ("MES A MES", "MES POR MES", "POR MES", "CADA MES")

# [2026-08-26 · QV2-SERIE-DIA] Serie DIARIA de un mes: «la producción día a día de Akacias en
# junio». No existía nivel para esto — las únicas dos puertas al panel diario eran nombrar un día
# concreto (N1D) o pedir el mejor/peor (N1DSEL), así que todas estas formas caían a N1 y
# respondían el KPI del mes. La curva ya la dibuja `cuant_dia_panel` entera; solo faltaba la
# puerta de entrada.
_SDIA_WORDS = {"DIARIA", "DIARIO", "DIARIAS", "DIARIOS"}
_SDIA_PHRASES = ("DIA A DIA", "DIA POR DIA", "CADA DIA", "POR DIA")
# «promedio diario» / «ppto diario» llevan DIARIO pero son REFERENCIAS o descargos, no un pedido
# de serie: sin esta guarda, «cómo va Akacias contra el promedio diario» se convertiría en curva.
_RX_SDIA_NO = re.compile(r"\b(?:PROMEDIO|PPTO|PRESUPUESTO|META)\s+DIARI[AO]S?\b")

# Grounding de producto por TOKEN (no substring: "GAS" suelto, no dentro de "GASOLINA"/un nombre).
_PROD_TOKENS = {"GAS": "gas", "BLANCOS": "blancos", "BLANCO": "blancos"}

# Fase 4 — REFERENCIA (contra qué se compara el REAL). Default PPTO. P50 se reconoce para rechazar.
# Substring sobre texto normalizado; palabras distintivas (no colisionan). "promedio del año" es
# una REFERENCIA, no un acumulado (ver override de nivel en extraer_slots, AF-4.9).
_REF_MATCH = [
    ("P50",           ("P50", "COMPROMISO", "BASE P50")),
    ("CONTABLE",      ("CONTABLE",)),
    ("OPERATIVO",     ("OPERATIVO",)),
    ("promedio_anio", ("PROMEDIO DEL ANO", "PROMEDIO ANUAL", "PROMEDIO MENSUAL",
                       "VS EL PROMEDIO", "CONTRA EL PROMEDIO", "RESPECTO AL PROMEDIO")),
]

_MESES = ("enero febrero marzo abril mayo junio julio agosto septiembre setiembre "
          "octubre noviembre diciembre").split()

# [2026-08-25] GRANO DÍA (plan QV2-GRANO-DIA). `_periodo_texto` solo conoce MESES: medido,
# "el 15 de mayo" devolvía «mayo» y el motor contestaba el MES ENTERO. Esto se resuelve ANTES.
# 🔑 Este módulo es PURO (sin BD): el `techo` entra como PARÁMETRO, no se consulta aquí.
# [2026-08-25 · QV2-HILO-DIA F3] Mapa EXPLÍCITO, no por índice. `_MESES` lleva DOS variantes de
# septiembre («septiembre» y «setiembre»), así que enumerate() corría todo un mes desde ahí:
# octubre->11, noviembre->12 y diciembre->13, un mes que no existe (habría hecho fallar
# _fecha_valida y la pregunta se caía sin explicación). No se toca `_MESES`: la usa además
# _periodo_texto y su orden importa allí.
_MESES_NUM = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
              "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
              "noviembre": 11, "diciembre": 12}
_DIA_REL = {"ANTEAYER": -2, "ANTIER": -2, "AYER": -1, "HOY": 0}   # orden: los largos primero
# [2026-08-25 · QV2-HILO-DIA F1] «DIA» OPCIONAL. Medido: "el día 15 de mayo" NO matcheaba
# (el regex exigía el número pegado a EL) y el flujo caía a _RX_DIA_SOLO, que ignora el mes
# escrito y usa el del techo -> se pidió MAYO y se respondió AGOSTO, afirmándolo sin avisar.
# Es la misma degradación que la guarda de :134 declara inaceptable, por la puerta de al lado.
_RX_DIA_MES = re.compile(r"\bEL\s+(?:DIA\s+)?(\d{1,2})\s+DE\s+([A-Z]+)")
_RX_DIA_SOLO = re.compile(r"\bEL\s+(?:DIA\s+)?(\d{1,2})\b")
# [2026-08-26 · QV2-DIA-SEL] Léxico de DIRECCIÓN. El ADJETIVO manda sobre el cuantificador:
# «más BAJA» es un MÍNIMO aunque lleve «más». El detector anterior solo miraba MAS/MENOS y
# respondía el día de producción MÁXIMA a quien preguntaba por la mínima, afirmándolo sin aviso.
# Incluye los VERBOS de dirección: si «cayó» dispara el detector pero no está aquí, la pregunta
# se reconoce y se responde al revés — una inversión nueva creada por el propio arreglo.
# Va tras norm(), que pliega acentos: se escribe CAY[OÓ] por si la normalización cambiara, pero
# lo que llega es CAYO. Verificado contra normaliza.py:6.
_DIR_MIN = (r"(?:BAJ[AO]S?|MENOR(?:ES)?|MENOS|PEOR(?:ES)?|MINIM[AO]S?|"
            r"CAY[OÓ]|CAIDAS?|DESPLOM\w*|DESCENDI\w*|FLOJ[AO]S?)")
_DIR_MAX = (r"(?:ALT[AO]S?|MAYOR(?:ES)?|MAS|MEJOR(?:ES)?|MAXIM[AO]S?|"
            r"SUBI[OÓ]|CRECI\w*|AUMENT\w*|DISPAR\w*|PICOS?|RECORD)")
# FUERA a propósito: PEQUEN[AO]S? («producción pequeña» no se dice) y GRANDES? (califica pozos y
# campos, no producción: «el pozo más grande»). Ambos serían superficie de ataque sin cubrir nada.

# Formas donde el token de dirección NO expresa un superlativo de producción. Medidas como
# falsos positivos: «mantenimiento MAYOR» (major overhaul, terminología de la industria),
# «MÁS DE 5000 barriles» (umbral, no superlativo) y «BAJO EL presupuesto» (preposición).
_RX_EXCLUIR = re.compile(r"\bMAS\s+DE\s+\d"
                         r"|\bMANTENIMIENTO(?:ES)?\s+MAYOR(?:ES)?\b"
                         r"|\bBAJO\s+(?:EL|LA|LOS|LAS)\b")

# Direcciones que califican a OTRO sustantivo y por tanto NO compiten por la del día. Sin esto,
# «el mejor día del PEOR mes» y «qué día tuvo mayor producción en el campo con MENOS pozos» se
# declaraban ambiguos: el adjetivo lejano hablaba del mes o de los pozos, no de la producción.
_RX_DIR_AJENA = re.compile(
    r"\b(?:MEJOR|PEOR|MAYOR|MENOR|MAS|MENOS)(?:ES)?\s+"
    r"(?:MES(?:ES)?|ANIOS?|SEMANAS?|TRIMESTRES?|CAMPOS?|POZOS?|ACTIVOS?|GERENCIAS?)\b")

# Cuatro construcciones. `DIAS?` en todas (el plural caía a N1 y respondía el KPI del mes);
# léxico COMPLETO en todas (antes MAYOR/MENOR solo valían pegados a «DIA DE»); `DE|CON` («el día
# CON mayor producción»); y `CUAL(ES)? DIA`, muy usado en Latinoamérica.
# Ventana de 60 y no 40: el hueco real entre «QUE DIA» y el adjetivo mide 19-22 en las preguntas
# directas, pero 46-49 en cuanto se intercalan entidad y mes («que dia del mes de julio tuvo
# castilla la produccion mas baja»), que es igual de natural.
# 🔑 NO hay alternativa de verbos SUELTOS: SUBIO/BAJO/CAYO están en _VAR_WORDS (:31-32) y hoy
#    resuelven a N4 (variación mes a mes). Como detectar_dia tiene precedencia sobre el nivel
#    (:249-251), una alternativa propia les habría robado N4 sin declararlo. Los verbos solo
#    actúan dentro de una construcción de día explícita.
_RX_SELECTOR = re.compile(
    r"\b(?:MEJOR|PEOR)(?:ES)?\s+DIAS?\b"
    r"|\bDIAS?\s+(?:DE|CON)\s+" + _DIR_MIN + r"\b"
    r"|\bDIAS?\s+(?:DE|CON)\s+" + _DIR_MAX + r"\b"
    r"|\b(?:QUE|CUAL(?:ES)?)\s+DIAS?\b.{0,60}?\b" + _DIR_MIN + r"\b"
    r"|\b(?:QUE|CUAL(?:ES)?)\s+DIAS?\b.{0,60}?\b" + _DIR_MAX + r"\b"
)
# Guarda H4 (gemela de la de no_soportado.py): "acumulado hasta hoy" trae HOY pero pide N2.
_RX_ACUM_GUARDA = re.compile(r"\bACUMULAD[OA]\b|\bEN\s+LO\s+QUE\s+VA\b|\bYTD\b|"
                             r"\bHASTA\s+(AHORA|HOY|LA\s+FECHA)\b|\bEN\s+TOTAL\b")
# Formas de RANGO que NO son un día puntual y ya tienen su propio rechazo (no_soportado.py).
# [2026-08-26 · QV2-DIA-SEL] +«LOS DÍAS DE …» y «TOP N DÍAS»: al admitir el plural, el selector
# empezaba a capturarlas y respondía UN SOLO día a quien pide VARIOS —y sobre un mes, aunque la
# pregunta dijera «del año»—. Eso es un ranking a grano día: funcionalidad que no existe, así que
# la forma cae al rechazo honesto en vez de fingir una respuesta.
# 🔑 Solo el plural con artículo definido o cardinal. «QUÉ DÍAS fue la producción más baja» NO
#    entra aquí: ahí el plural es laxo y se pregunta por el día, que sí sabemos responder.
_RX_RANGO_GUARDA = re.compile(r"\bENTRE\s+EL\s+\d+\s+Y\s+EL\s+\d+|\bDEL\s+\d+\s+AL\s+\d+|"
                              r"\bLOS\s+\d+\s+DIAS|\bPRIMEROS\s+\d+\s+DIAS|\bSEMANA|\bTRIMESTRE|"
                              r"\bL[OA]S\s+DIAS\s+(?:DE|CON)\b|\bTOP\s+\d+\s+DIAS\b")


# [2026-08-26 · QV2-DIA-SEL] Techo FICTICIO para preguntar «¿sabes resolver esta FORMA?» sin
# tocar BD. La fecha que salga se descarta; solo importa si `detectar_dia` devuelve None o no.
# Día 15 para que ninguna forma («el 30», «el 31») quede fuera por el calendario.
# Vive AQUÍ, junto al detector, y no en el llamador: maquina_q.py:78 tiene el suyo desde antes
# (no se toca — importarlo desde aquí sería circular: maquina_q ya importa respuesta_cuantificar).
TECHO_CENTINELA = _dt.date(2000, 1, 15)


def _orden_selector(t: str, ini: int, fin: int):
    """"min" | "max" | None (ambiguo o sin dirección). [2026-08-26 · QV2-DIA-SEL]

    `ini`/`fin` acotan el match del selector: la dirección se busca en su VECINDAD, no en toda
    la frase. «el mejor día del PEOR mes» habla de un máximo, y un PEOR a diez palabras no puede
    voltearlo — mirar el texto entero invertía esa frase y otras dos, medidas.

    🔑 Hay caso EXPLÍCITO para máximo. La versión anterior tenía tres ramas para «min» y ninguna
       para «max»: el máximo salía de un `else`, de modo que todo lo no reconocido se afirmaba
       como máximo en silencio. Ese `else` ES el bug que esta función existe para eliminar.
    🔑 Devuelve None si aparecen las DOS direcciones («el día de más producción y el de menos»):
       la regla del proyecto es avisar, no elegir. El llamador lo trata como «no resuelvo».
    """
    v = t[max(0, ini - 30):min(len(t), fin + 60)]
    v = _RX_EXCLUIR.sub(" ", v)          # «mantenimiento mayor», «mas de 5000», «bajo el ppto»
    v = _RX_DIR_AJENA.sub(" ", v)        # «del PEOR mes», «con MENOS pozos» — hablan de otra cosa
    # La COMBINACIÓN manda sobre el token suelto: "MAS BAJA" es mínimo aunque MAS sea de _DIR_MAX.
    # Se cubren los DOS órdenes del español: «producción más baja» y «bajó más» / «cayó más».
    comb_min = (re.search(r"\bMAS\s+" + _DIR_MIN + r"\b", v) or
                re.search(r"\b" + _DIR_MIN + r"\s+MAS\b", v))
    comb_max = re.search(r"\bMAS\s+" + _DIR_MAX + r"\b", v)
    if comb_min:
        return "min"
    if comb_max:
        return "max"
    hay_min = re.search(r"\b" + _DIR_MIN + r"\b", v)
    hay_max = re.search(r"\b" + _DIR_MAX + r"\b", v)
    if hay_min and hay_max:
        return None                      # dos direcciones reales → ambiguo, no se elige
    if hay_min:
        return "min"
    if hay_max:
        return "max"
    return None                          # sin dirección reconocible → NO se asume máximo


def _mes_nombrado(t: str):
    """Nº del mes NOMBRADO en el texto ya normalizado, o None. [2026-08-26 · QV2-DIA-SEL]

    🔑 Por TOKEN (`\\b`), no por substring. Antes era `nom.upper() in t`, y "MAYO" es substring
    de "MAYOR": «el día de MAYOR producción» resolvía a mes=5 con `asumido=[]` — el sistema
    creía que el usuario había dicho «mayo» y no lo declaraba. Medido: «menor» resolvía bien y
    solo «mayor» se envenenaba, que es la asimetría que delató el fallo.
    Es la misma degradación silenciosa que la guarda de :145-150 declara inaceptable, entrando
    por la puerta del nombre del mes en vez de la del día.
    """
    for nom, num in _MESES_NUM.items():
        if re.search(r"\b" + nom.upper() + r"\b", t):
            return num
    return None


def _fecha_valida(anio: int, mes: int, dia: int) -> bool:
    """¿La combinación existe en el calendario? [2026-08-25, post-auditoría del plan]

    El rango 1..31 NO basta: "el 31 de febrero" pasaba ese filtro y construía la cadena
    '2026-02-31', que reventaba en `ejecutar_n1d` con
    `ValueError: day is out of range for month` — excepción NO capturada que tumbaba la
    respuesta entera (medido en la ruta completa antes de este arreglo). Se valida aquí, en
    el módulo puro donde nace la fecha, y no en el ejecutor: así ninguna otra ruta futura
    puede construir un día inexistente. Sin BD — `calendar` es stdlib, la pureza se conserva.
    """
    import calendar
    if not (1 <= mes <= 12):
        return False
    return 1 <= dia <= calendar.monthrange(anio, mes)[1]


def menciona_dia(texto: str) -> bool:
    """PRE-CHECK barato y puro. Solo si devuelve True el llamador paga la consulta del techo
    (evita un round-trip a BD en TODA pregunta mensual).

    [2026-08-26 · QV2-DIA-SEL] Delega en `detectar_dia` con el CENTINELA en vez de repetir los
    regex. Sigue siendo puro y sin BD —el centinela es una fecha fija—, y a cambio es COHERENTE
    POR CONSTRUCCIÓN con el resolutor. Medido antes de esto: 4 formas («el día de más producción
    y el de menos», «mantenimiento mayor», «más de 5000 barriles», «bajo el presupuesto») daban
    True aquí y None allí, o sea se pagaba la consulta del techo para acabar no resolviendo.

    🔑 [2026-08-26] La SERIE diaria (N1DSER) cuenta como «menciona un día» aunque no pase por
    `detectar_dia` —esa función reconoce días CONCRETOS y selectores, no la serie—. Sin esta
    segunda rama, «muéstrame día a día la producción de crudo de Pauto Sur» devolvía False aquí,
    el llamador (respuesta_cuantificar:268) NO consultaba el techo, y `periodo_serie_dia` se
    quedaba sin mes que resolver: la pregunta se degradaba a N1 y respondía el KPI del mes.
    El bug NO se veía en las pruebas porque allí el techo se pasaba a mano; solo aparece por la
    ruta real, donde el techo depende de esta función.
    """
    if detectar_dia(texto, TECHO_CENTINELA) is not None:
        return True
    return _nivel_temporal(texto) == "N1DSER"


def detectar_dia(texto: str, techo=None) -> dict | None:
    """Ranura de DÍA, o None si la pregunta no es de grano día. `techo` (date) fija el mes/año
    implícitos: se asume el del DATO, no el del reloj (el reporte va ~100 días atrás).

    Devuelve uno de:
      {"clase":"fecha",    "fecha":"YYYY-MM-DD", "asumido":[...]}
      {"clase":"relativo", "delta":-1}
      {"clase":"selector", "orden":"max"|"min", "anio":int, "mes":int, "asumido":[...]}
    """
    t = norm(texto or "")
    if _RX_ACUM_GUARDA.search(t) or _RX_RANGO_GUARDA.search(t):
        return None
    m = _RX_SELECTOR.search(t)
    if m:
        orden = _orden_selector(t, m.start(), m.end())
        if orden is None:
            return None      # dirección ambigua o irreconocible: NO se asume una y se afirma
        mo = _mes_nombrado(t)
        ya = re.search(r"20\d\d", t)
        if mo is None and techo is None:
            return None                       # sin mes explícito ni techo no se puede resolver
        anio = int(ya.group(0)) if ya else (techo.year if techo else None)
        asum = []
        if mo is None:
            mo, anio = techo.month, techo.year
            asum.append(f"periodo={mo:02d}/{anio}")
        return {"clase": "selector", "orden": orden, "anio": anio, "mes": mo, "asumido": asum}
    for kw, delta in _DIA_REL.items():
        if re.search(r"\b" + kw + r"\b", t):
            return {"clase": "relativo", "delta": delta}
    m = _RX_DIA_MES.search(t)
    if m and m.group(2).lower() in _MESES_NUM:
        d, mo = int(m.group(1)), _MESES_NUM[m.group(2).lower()]
        ya = re.search(r"20\d\d", t)
        anio = int(ya.group(0)) if ya else (techo.year if techo else None)
        if anio and _fecha_valida(anio, mo, d):
            return {"clase": "fecha", "fecha": f"{anio:04d}-{mo:02d}-{d:02d}",
                    "asumido": [] if ya else [f"año={anio}"]}
        # El texto nombra un MES explícito: esta rama MANDA, válida o no. Sin este `return`
        # el flujo caía al regex de día suelto de abajo y "el 31 de febrero" respondía sobre
        # el 31 de MAYO (el mes del techo) — cambiar el mes que el usuario dijo por otro es
        # exactamente la degradación silenciosa que este plan existe para impedir.
        # [2026-08-25, hallazgo de la verificación posterior al plan]
        return None
    m = _RX_DIA_SOLO.search(t)
    if m and techo:
        d = int(m.group(1))
        if _fecha_valida(techo.year, techo.month, d):
            return {"clase": "fecha", "fecha": f"{techo.year:04d}-{techo.month:02d}-{d:02d}",
                    "asumido": [f"mes={techo.month:02d}/{techo.year}"]}
    return None


# Puntuación que `norm()` NO retira (solo pliega acentos/mayúsculas) y que SÍ hay que despegar de
# cada token antes de comparar por igualdad exacta — si no, "¿serie…" o "…gas?" nunca calzan contra
# "SERIE"/"GAS" (el ¿/? queda pegado al primer/último token). Mismo criterio que
# maquina_q.detectar_entidad (`w.strip("¿?¡!.,;:()[]{}\"'\`")`).
_PUNCT = "¿?¡!.,;:()[]{}\"'`"


def _tokens(t: str) -> set:
    """Tokens de un texto YA normalizado, sin puntuación de borde pegada."""
    return {p for p in (w.strip(_PUNCT) for w in t.split()) if p}


def _tiene(t: str, words: set, phrases: tuple) -> bool:
    return any(w in _tokens(t) for w in words) or any(p in t for p in phrases)


def _nivel_temporal(texto: str) -> str:
    t = norm(texto or "")
    # [2026-08-26] La serie DIARIA va PRIMERO: «día a día» es la señal de GRANO más específica que
    # existe, y gana incluso a variación/serie. «serie diaria» y «cómo varió día a día» piden el
    # detalle por día, no el mensual — devolver el mensual sería cambiar la pregunta en silencio.
    if _tiene(t, _SDIA_WORDS, _SDIA_PHRASES) and not _RX_SDIA_NO.search(t):
        return "N1DSER"
    if _tiene(t, _VAR_WORDS, _VAR_PHRASES):     # N4 gana (variación es más específica que serie)
        return "N4"
    if _tiene(t, _SERIE_WORDS, _SERIE_PHRASES):
        return "N3"
    if any(k in t for k in _ACUM_KW):
        return "N2"
    return "N1"


def _producto(texto: str, entidad_valor: str | None = None) -> str:
    """crudo (default) | gas | blancos. Token exacto sobre texto normalizado, EXCLUYENDO los tokens
    del nombre de la entidad (AF10: un campo tipo 'CAÑO BLANCO' no debe leerse como producto blancos;
    'cuánto gas produjo Caño Blanco' SÍ da gas porque 'GAS' no es token del nombre)."""
    toks = _tokens(norm(texto or ""))
    if entidad_valor:
        toks -= _tokens(norm(entidad_valor))
    for tok, prod in _PROD_TOKENS.items():
        if tok in toks:
            return prod
    return "crudo"


def _referencia(texto: str) -> str:
    t = norm(texto or "")
    for code, kws in _REF_MATCH:
        if any(k in t for k in kws):
            return code
    return "PPTO"


def _periodo_texto(texto: str) -> str | None:
    """Nombre de mes hallado (para pasárselo a desempeno), o None = mes actual.
    'mes pasado'/'anterior' se pasan literales (desempeno._parse_periodo también los entiende).

    🔑 [2026-08-26] Por TOKEN (`\\b`), no por substring — el MISMO arreglo que _mes_nombrado
    (:188) recibió y que aquí quedó pendiente y documentado. Con `m in t`, "mayo" es substring
    de "mayor": «la producción de MAYOR volumen» devolvía "mayo" y el motor consultaba ese mes
    sin avisar. La asimetría delata el fallo: «menor» resolvía bien y solo «mayor» se envenenaba.
    """
    t = (texto or "").lower()
    if "pasado" in t or "anterior" in t:
        return "mes pasado"
    mo = next((m for m in _MESES if re.search(r"\b" + m + r"\b", t)), None)
    if mo is None:
        return None
    ym = re.search(r"20\d\d", t)                 # año opcional ("abril 2026")
    return f"{mo} {ym.group(0)}" if ym else mo


# Punto de entrada PÚBLICO del detector de periodo. `analizar` también lo necesita (el mes
# nombrado se ignoraba allí, ver respuesta_analizar.py) y duplicarlo crearía dos gemelos que se
# desincronizan — que es justo lo que produjo el bug de substring de arriba, presente en DOS
# sitios a la vez. Un solo detector, dos consumidores.
def periodo_texto(texto: str) -> str | None:
    return _periodo_texto(texto)


def periodo_serie_dia(texto: str, techo=None) -> dict | None:
    """{anio, mes, asumido} del mes cuya curva DIARIA se pide, o None si no se puede resolver.
    [2026-08-26 · QV2-SERIE-DIA] Misma resolución que el selector (:120-133): el mes NOMBRADO
    manda; si no lo hay se toma el del techo y se DECLARA en `asumido`, nunca en silencio."""
    t = norm(texto or "")
    mo = _mes_nombrado(t)
    ya = re.search(r"20\d\d", t)
    if mo is None and techo is None:
        return None                            # sin mes ni techo no hay periodo que resolver
    anio = int(ya.group(0)) if ya else (techo.year if techo else None)
    asum = []
    if mo is None:
        mo, anio = techo.month, techo.year
        asum.append(f"periodo={mo:02d}/{anio}")
    return {"anio": anio, "mes": mo, "asumido": asum}


def extraer_slots(texto: str, entidad_valor: str | None = None, techo=None) -> dict:
    """Slots aterrizados. `entidad_valor` (nombre canónico ya resuelto) permite excluir sus tokens del
    grounding de producto (AF10). `periodo_texto`=None → desempeno usa el mes por defecto (último).
    `nivel_temporal`=N2 si pide acumulado/año/YTD (salvo override AF-4.9). `producto`/`unidad`/
    `descargo` del catálogo. `referencia` (Fase 4) = PPTO (default) | OPERATIVO | CONTABLE |
    promedio_anio | P50 (se reconoce para que el ejecutor la rechace honesto).
    `techo` (date, opcional) = último día con reporte DIARIO — fija el mes/año implícitos de una
    fecha suelta ("el 15") o de un selector sin mes ("mejor día... este mes"). [2026-08-25]"""
    prod = _producto(texto, entidad_valor)
    variable = f"produccion_{prod}"
    pcfg = (_catalogo.get().get("productos") or {}).get(variable, {})
    unidad = pcfg.get("unidad", "bbl")
    mes_cfg = (pcfg.get("granos") or {}).get("mes", {})
    descargo = mes_cfg.get("descargo") if mes_cfg.get("confianza") == "media" else None

    ref = _referencia(texto)
    nivel = _nivel_temporal(texto)
    if ref == "promedio_anio" and not any(k in norm(texto) for k in _ACUM_KW_FUERTE):
        # AF-4.9 (revisado): fuerza N1 SOLO si la única señal de N2 fue la DÉBIL ("del año"/"en el
        # año", que puede venir de la propia frase de referencia — "promedio DEL AÑO"). Si el texto
        # trae ADEMÁS una palabra FUERTE ("acumulada", "YTD"...), es un pedido real de acumulado con
        # una referencia distinta a PPTO; se deja N2 y el aviso de ejecutar_n2 (AF-4.7) explica que
        # esa referencia no aplica al acumulado — más honesto que perder el "acumulado" en silencio.
        nivel = "N1"

    # [2026-08-25] GRANO DÍA. Va ANTES de `_periodo_texto` (A-7): esa función solo conoce meses y
    # "el 15 de mayo" le devolvía «mayo» — el motor contestaba el mes entero. Si `detectar_dia`
    # reconoce la forma, GANA sobre el nivel de arriba (N1D/N1DSEL en vez de N1/N2/N3/N4).
    dia = detectar_dia(texto, techo)
    if dia is not None:
        nivel = "N1DSEL" if dia["clase"] == "selector" else "N1D"

    # [2026-08-26 · QV2-SERIE-DIA] El día CONCRETO gana a la serie diaria: «la producción día a
    # día del 15 de junio» pide ese día, no el mes entero. Por eso va DESPUÉS de detectar_dia.
    sdia = None
    if nivel == "N1DSER":
        sdia = periodo_serie_dia(texto, techo)
        if sdia is None:
            nivel = "N1"          # sin mes ni techo no hay curva que pedir: se degrada al mes

    per = _periodo_texto(texto)
    defaults = [f"producto={prod}", f"referencia={ref}"]
    if per is None:
        defaults.append("periodo=mes actual")
    if dia is not None:
        defaults.extend(dia.get("asumido", []))
    if sdia is not None:
        defaults.extend(sdia.get("asumido", []))
    return {
        "variable": variable,
        "producto": prod,
        "unidad": unidad,
        "descargo": descargo,
        "nivel_temporal": nivel,
        "referencia": ref,
        "periodo_texto": per,
        "dia": dia,
        "serie_dia": sdia,
        "defaults_asumidos": defaults,
    }
