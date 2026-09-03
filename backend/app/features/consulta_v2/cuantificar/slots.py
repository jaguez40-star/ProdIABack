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

# [2026-09-03 · MTD] «en lo que va DEL MES» ≠ «en lo que va DEL AÑO». Las dos casan con la misma
# keyword fuerte ("EN LO QUE VA", :27) y hasta ahora las dos caían en N2 — que acumula SIEMPRE el
# AÑO, de enero al último mes cerrado. Preguntabas por el mes en curso y te respondían siete meses,
# sin un solo aviso: el fallo silencioso de §6, el que no falla sino que responde otra cosa.
#
# 🔑 La cifra del mes en curso YA existe: es exactamente lo que N1 devuelve para el mes del techo
#    («6.738.232 bbl · proyección · 30/31 días»). El hueco era de ENRUTADO, no de cálculo — por eso
#    esto es una GUARDA que desvía a N1, y no un nivel nuevo.
# 🔑 Exige la palabra MES. «en lo que va del año» sigue yendo a N2 (golden: cuantificar_golden.yaml
#    trae ese caso); una guarda sin esa exigencia se lo robaría.
# 🔑 Es ADITIVA sobre `_ACUM_KW`: quitar "EN LO QUE VA" de las keywords habría roto el golden.
# 🔑 Cubre de paso «el acumulado DEL MES DE JULIO», que hoy responde el acumulado del AÑO: con la
#    guarda cae a N1 y `_periodo_texto` aterriza julio. Mismo bug, misma familia.
_RX_MTD = re.compile(
    r"\bMTD\b"
    r"|\b(?:EN\s+LO\s+QUE\s+VA|EN\s+LO\s+CORRIDO|LO\s+QUE\s+LLEVAMOS|LO\s+QUE\s+VAMOS)"
    r"\s+(?:DEL?\s+)?(?:ESTE\s+|EL\s+)?MES\b"
    r"|\b(?:ACUMULAD[OA]|TOTAL)\s+(?:DEL?\s+)?(?:ESTE\s+|EL\s+)?MES\b"
    r"|\bACUMULAD[OA]\s+MENSUAL\b"
)

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

# [2026-09-03 · VENTANAS-TEMPORALES] Ventana MÓVIL hacia atrás: «los últimos 30 días», «las
# últimas 6 semanas», «los últimos 3 meses». Es un grano que no existía: hasta ahora la única
# forma de acotar el tiempo era nombrar un MES o un DÍA concreto, así que estas preguntas
# caían a `periodo_texto=None` y el motor respondía el mes por defecto SIN declarar que había
# ignorado la ventana — la misma degradación silenciosa que la guarda de :281-286 existe para
# impedir, entrando por la puerta del rango en vez de la del mes.
#
# 🔑 Exige marcador EXPLÍCITO (ULTIMO/ULTIMA + variantes). NO basta «los 30 días»: esa forma
#    ya la captura `_RX_RANGO_GUARDA` (:139) y cae al rechazo honesto de no_soportado.py.
#    Ampliar la ventana a esa forma le robaría el rechazo y respondería algo distinto de lo
#    que hoy responde, sin que ningún test lo detecte.
# 🔑 SIN "HASTA HOY"/"HASTA AHORA": están en `_ACUM_KW_FUERTE` (:27) y en `_RX_ACUM_GUARDA`
#    (:130) y hoy resuelven a N2 (acumulado). Un patrón de ventana que las incluyera le
#    robaría preguntas a N2, que funciona.
_UNIDAD_VENTANA = {"DIA": "dia", "DIAS": "dia",
                   "SEMANA": "semana", "SEMANAS": "semana",
                   "MES": "mes", "MESES": "mes"}

# Cardinales escritos con letra: «los últimos tres meses» es tan natural como «los últimos 3».
# Sin esto la forma con letra no matchea y cae al mes por defecto, en silencio.
_CARDINAL = {"UN": 1, "UNA": 1, "DOS": 2, "TRES": 3, "CUATRO": 4, "CINCO": 5, "SEIS": 6,
             "SIETE": 7, "OCHO": 8, "NUEVE": 9, "DIEZ": 10, "ONCE": 11, "DOCE": 12,
             "QUINCE": 15, "VEINTE": 20, "TREINTA": 30}

# Cuatro construcciones, todas con marcador explícito:
#   (a) «los últimos 30 días» / «las últimas 6 semanas»  → cantidad explícita
#   (b) «el último mes» / «la última semana»             → cantidad implícita = 1
#   (c) «los 30 días anteriores»                          → marcador POSPUESTO
#   (d) «los 3 últimos meses» / «los tres últimos meses»  → CANTIDAD ANTEPUESTA a «últimos»
# El cuantificador es opcional en (a) para admitir «últimos 30 días» sin artículo.
# 🔑 (d) [2026-09-03] Medido en Pruebas: «Muestra la producción de crudo de los 3 últimos meses
#    para Castilla» NO casaba con ninguna de las tres primeras y caía al mes del techo (agosto),
#    respondiendo otra cosa SIN avisar — la misma familia de fallo silencioso que el periodo
#    ignorado. En español el orden es libre («los últimos 3 meses» ≡ «los 3 últimos meses») y el
#    detector solo conocía uno de los dos.
#    Va la ÚLTIMA en la alternancia para no desplazar los grupos 1-5 que el dispatcher ya lee.
#    Con «los últimos meses» (sin cantidad) captura "LOS", que no es cardinal → None, exactamente
#    lo que devolvía antes: no hay regresión, solo una forma más reconocida.
_RX_VENTANA = re.compile(
    r"\bULTIM[OA]S?\s+(\d{1,3}|[A-Z]+)\s+(DIAS?|SEMANAS?|MESES|MES)\b"
    r"|\bULTIM[OA]\s+(DIAS?|SEMANA|MES)\b"
    r"|\b(\d{1,3})\s+(DIAS?|SEMANAS?|MESES|MES)\s+(?:ANTERIORES|ATRAS|PREVIOS)\b"
    r"|\b(\d{1,3}|[A-Z]+)\s+ULTIM[OA]S\s+(DIAS?|SEMANAS?|MESES|MES)\b"
)

# ============================================================================
# [2026-09-03 · COMPARACION-PERIODOS] Punto 3 de inteligencia de tiempo, tipo 2.
# ============================================================================
# Conectores de comparación. Todos exigen DOS periodos: sin el segundo no hay comparación,
# y adivinarlo sería justo el fallo que este bloque existe para cerrar (P1).
_CMP_CONECTOR = r"(?:VS|VERSUS|CONTRA|FRENTE\s+A|COMPARAD[OA]\s+CON|COMPARADO\s+A|RESPECTO\s+A)"

# [2026-09-03 · fix] «COMPARA julio CON mayo» / «compárame julio con mayo». Aquí el conector
# real es CON, no el verbo — pero CON suelto NO puede entrar en _CMP_CONECTOR: es de las
# preposiciones más comunes del español («producción CON corte a agosto», «campos CON meta»)
# y partiría por ahí frases que no comparan nada. Solo cuenta como conector cuando el texto
# trae delante el VERBO comparar, que es lo que convierte ese CON en «A contra B».
# 🔑 COMPARA\w* cubre compara / comparame / comparemos, y NO pisa a COMPARADO CON, que ya
#    tiene su propia entrada arriba y se resuelve antes de llegar aquí.
_RX_CMP_VERBO = re.compile(r"\bCOMPARA\w*\b")
_RX_CMP_CON = re.compile(r"\bCON\b")

# 🔴 P4 — GUARDA. "VS EL PROMEDIO" / "CONTRA EL PROMEDIO" / "RESPECTO AL PROMEDIO" ya son el
# detector de REFERENCIA (:81) y hoy resuelven bien a N1 con referencia=promedio_anio. Lo mismo
# vale para el presupuesto y sus escenarios: «¿cómo va Castilla vs el presupuesto?» es la
# pregunta N1 de toda la vida. Si el conector va seguido de una REFERENCIA en vez de un
# PERIODO, esto NO es una comparación de periodos y el detector se aparta.
# 🔑 Se mira lo que sigue al conector, no si la palabra aparece en la frase: «julio vs junio
#    contra el presupuesto» tiene las dos cosas y sí es una comparación de periodos.
_RX_CMP_NO = re.compile(
    _CMP_CONECTOR + r"\s+(?:EL\s+|LA\s+|AL\s+|LOS\s+|SU\s+)?"
    r"(?:PROMEDIO|PPTO|PRESUPUESTO|META|P50|OPERATIVO|CONTABLE|PROGRAMA|PLAN)\b")

# Periodo RELATIVO como segundo término: «julio vs el mes pasado», «vs el año pasado».
_RX_CMP_MES_PASADO = re.compile(r"\b(?:EL\s+)?MES\s+(?:PASADO|ANTERIOR)\b")
_RX_CMP_ANIO_PASADO = re.compile(
    r"\b(?:EL\s+)?(?:MISMO\s+MES\s+DEL\s+)?ANO\s+(?:PASADO|ANTERIOR)\b"
    r"|\bMISMO\s+MES\s+DE\s+20\d\d\b|\bINTERANUAL\b")

# 🔴 P13 — Número → nombre canónico, EXPLÍCITO. NO se puede indexar `_MESES` (:84) para esto:
# es una lista desde CERO y además trae "setiembre" como segunda grafía de septiembre, así que
# `_MESES[7]` es "agosto" (desplazado uno) y de septiembre en adelante todo queda corrido.
# `_MESES_NUM` tampoco vale invertido sin más: dos claves apuntan al 9.
_MES_NOMBRE = {1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
               7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre",
               12: "diciembre"}

# Techo de cordura. Una ventana de 4 dígitos («los últimos 9999 días») no es una pregunta
# real: es ruido o un intento de forzar una consulta gigante. Se rechaza devolviendo None
# (→ rechazo honesto) en vez de resolver una ventana absurda y consultar 27 años de serie.
_VENTANA_MAX = {"dia": 365, "semana": 52, "mes": 24}


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
    if _nivel_temporal(texto) == "N1DSER":
        return True
    # 🔑 [2026-09-03] La VENTANA también necesita techo. Sin esta rama, `detectar_ventana`
    #    recibiría techo=None por la ruta real (el llamador no lo pediría) y devolvería None
    #    siempre: la ventana funcionaría en los tests —donde el techo se pasa a mano— y NO en
    #    producción. Es literalmente el bug que :230-236 documenta para la serie diaria.
    #    Se usa el CENTINELA, igual que arriba: solo importa si resuelve o no, no qué fecha sale.
    if detectar_ventana(texto, TECHO_CENTINELA) is not None:
        return True
    # 🔑 [2026-09-03] La COMPARACIÓN también necesita techo (fija el año por defecto y el mes
    #    ancla de «vs el mes pasado»). Mismo motivo, misma solución que la ventana de arriba.
    return detectar_comparacion(texto, TECHO_CENTINELA) is not None


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
    # [2026-09-03 · MTD] La guarda del MES va JUSTO ANTES de N2 y no antes: «la evolución mes a mes
    # del acumulado» debe seguir siendo N3, y «cómo varió el acumulado del mes» N4. Adelantarla les
    # robaría preguntas que hoy resuelven bien.
    if _RX_MTD.search(t):
        return "N1"
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


def detectar_ventana(texto: str, techo=None) -> dict | None:
    """Ventana MÓVIL hacia atrás, o None si la pregunta no pide una. [2026-09-03 · VENTANAS-TEMPORALES]

    Devuelve:
      {"unidad": "dia"|"semana"|"mes", "cantidad": int,
       "ini": "YYYY-MM-DD", "fin": "YYYY-MM-DD", "asumido": [...]}

    `techo` (date) = último día CON DATO, no el reloj. Sin techo no se puede aterrizar la
    ventana en fechas y se devuelve None: es preferible el rechazo honesto a inventar un
    ancla. 🔑 Este módulo es PURO — el techo entra como PARÁMETRO, aquí no se consulta BD
    ni se llama a date.today(); el reporte va ~100 días atrás del reloj y anclar al reloj
    respondería sobre fechas sin dato.

    La ventana es INCLUSIVA en ambos extremos y termina en el techo: «los últimos 30 días»
    con techo=2026-08-23 es [2026-07-25, 2026-08-23], que son 30 días contados. Un `ini`
    calculado con `days=30` daría 31 días — el error de poste clásico, por eso va `- 1`.
    """
    t = norm(texto or "")
    m = _RX_VENTANA.search(t)
    if m is None:
        return None

    # Las 4 alternativas del regex dejan sus grupos en posiciones distintas; solo una casa.
    # La cantidad se resuelve UNA vez al final, común a todas: antes vivía dentro de la rama (a)
    # y al añadir (d) habría que duplicarla, que es como nacen las divergencias entre formas.
    if m.group(1) is not None:            # (a) «últimos 30 días» / «últimos tres meses»
        crudo, uni_txt = m.group(1), m.group(2)
    elif m.group(3) is not None:          # (b) «el último mes» → cantidad implícita 1
        crudo, uni_txt = "1", m.group(3)
    elif m.group(4) is not None:          # (c) «30 días anteriores»
        crudo, uni_txt = m.group(4), m.group(5)
    else:                                 # (d) «los 3 últimos meses» / «los tres últimos meses»
        crudo, uni_txt = m.group(6), m.group(7)

    if crudo.isdigit():
        cant = int(crudo)
    elif crudo in _CARDINAL:
        cant = _CARDINAL[crudo]
    else:
        return None                       # palabra no reconocida como cardinal: no se adivina

    uni = _UNIDAD_VENTANA.get(uni_txt)
    if uni is None or cant < 1:
        return None
    if cant > _VENTANA_MAX[uni]:
        return None                       # fuera de rango razonable → rechazo honesto

    if techo is None:
        return None                       # sin ancla no hay ventana que aterrizar

    fin = techo
    if uni == "dia":
        ini = fin - _dt.timedelta(days=cant - 1)
    elif uni == "semana":
        ini = fin - _dt.timedelta(weeks=cant) + _dt.timedelta(days=1)
    else:                                 # mes: se retrocede por calendario, no por 30 días
        y, mo = fin.year, fin.month - (cant - 1)
        while mo < 1:
            y, mo = y - 1, mo + 12
        ini = _dt.date(y, mo, 1)

    return {"unidad": uni, "cantidad": cant,
            "ini": ini.isoformat(), "fin": fin.isoformat(),
            "asumido": [f"ventana={cant} {uni}(s) hasta {fin.isoformat()}"]}


def _periodo_en(fragmento: str, anio_defecto: int):
    """('julio 2025', 7, 2025) del fragmento, o None. Fragmento = un lado de la comparación.

    Devuelve la cadena LISTA para `desempeno(periodo=...)`, que entiende «mes» y «mes año»
    (_parse_periodo, analisis/api.py:372). El año va SIEMPRE explícito: en una comparación,
    dejarlo implícito es como se cuela un YoY que en realidad compara el mismo año consigo
    mismo. Se declara, no se asume en silencio.
    """
    mes = _mes_nombrado(fragmento)
    if mes is None:
        return None
    ym = re.search(r"\b(20\d\d)\b", fragmento)
    anio = int(ym.group(1)) if ym else anio_defecto
    return f"{_MES_NOMBRE[mes]} {anio}", mes, anio


def detectar_comparacion(texto: str, techo=None) -> dict | None:
    """Comparación de DOS periodos mensuales, o None. [2026-09-03 · COMPARACION-PERIODOS]

    Devuelve:
      {"clase": "meses"|"mom"|"yoy",
       "a": "julio 2026", "mes_a": 7, "anio_a": 2026,
       "b": "mayo 2026",  "mes_b": 5, "anio_b": 2026,
       "asumido": [...]}

    `techo` (date) = último día CON DATO, no el reloj. Fija el año por defecto y el mes de
    referencia cuando el usuario dice «vs el mes pasado» sin nombrar el primero. Sin techo se
    devuelve None: es preferible el rechazo honesto a inventar un ancla (misma regla que
    `detectar_ventana`). 🔑 Módulo PURO: el techo entra por parámetro, aquí no hay BD.

    🔴 Guarda P4: si al conector le sigue una REFERENCIA (promedio/presupuesto/meta/P50/…),
       esto NO es una comparación de periodos sino la pregunta N1 de referencia, que hoy
       funciona. Se devuelve None y el flujo sigue como siempre.
    """
    t = norm(texto or "")
    if techo is None:
        return None
    m = re.search(_CMP_CONECTOR, t)
    if m is None:
        # [2026-09-03 · fix] Segundo camino: «compara julio CON mayo». El conector es el CON que
        # va DESPUÉS del verbo comparar; sin ese verbo delante, un CON suelto no parte nada.
        v = _RX_CMP_VERBO.search(t)
        m = _RX_CMP_CON.search(t, v.end()) if v else None
        if m is None:
            return None
    # 🔑 [2026-09-03 · fix] ANCLADA al conector encontrado (`m.start()`), no `search` sobre el
    #    texto entero. Con `search(t)` bastaba que la palabra de referencia apareciera en
    #    CUALQUIER parte para cancelar la comparación: «julio vs junio contra el presupuesto»
    #    partía por VS (correcto) y luego la guarda encontraba «CONTRA EL PRESUPUESTO» más
    #    adelante y devolvía None, matando una comparación legítima. `match` desde `m.start()`
    #    comprueba lo que el docstring dice: qué sigue a ESTE conector, no qué hay en la frase.
    if _RX_CMP_NO.match(t, m.start()):
        return None                       # es una REFERENCIA, no dos periodos (P4)

    izq, der = t[:m.start()], t[m.end():]
    anio_techo = techo.year

    # --- lado B (lo que va DESPUÉS del conector) -------------------------------------
    # Se resuelve primero: es el que admite formas relativas, y de él depende cómo se lee A.
    b_rel = None
    if _RX_CMP_ANIO_PASADO.search(der):
        b_rel = "yoy"
    elif _RX_CMP_MES_PASADO.search(der):
        b_rel = "mom"

    a = _periodo_en(izq, anio_techo)
    if a is None:
        # Sin mes a la izquierda, el ancla es el mes del TECHO: «¿cómo vamos vs el año
        # pasado?» = el mes del techo contra su gemelo del año anterior. Se DECLARA.
        a = (f"{_MES_NOMBRE[techo.month]} {anio_techo}", techo.month, anio_techo)
        a_asumido = [f"periodo A = {a[0]} (el mes del último reporte)"]
    else:
        a_asumido = []

    if b_rel == "yoy":
        b = (f"{_MES_NOMBRE[a[1]]} {a[2] - 1}", a[1], a[2] - 1)
        clase = "yoy"
    elif b_rel == "mom":
        _m, _y = (a[1] - 1, a[2]) if a[1] > 1 else (12, a[2] - 1)
        b = (f"{_MES_NOMBRE[_m]} {_y}", _m, _y)
        clase = "mom"
    else:
        b = _periodo_en(der, anio_techo)
        if b is None:
            return None                   # hay conector pero no un segundo periodo → no aplica
        clase = "yoy" if (b[1] == a[1] and b[2] != a[2]) else "meses"

    if (a[1], a[2]) == (b[1], b[2]):
        return None                       # «julio vs julio»: no hay nada que comparar

    asumido = a_asumido + [f"comparacion {clase}: {a[0]} contra {b[0]}"]
    return {"clase": clase,
            "a": a[0], "mes_a": a[1], "anio_a": a[2],
            "b": b[0], "mes_b": b[1], "anio_b": b[2],
            "asumido": asumido}


# [2026-09-03 · COMPARACION-PERIODOS] Tipo 3: la serie mensual REAL **contra el PROGRAMA**.
# 🔴 P8 — Exige LAS DOS señales: serie (_SERIE_WORDS/_SERIE_PHRASES, que ya dan N3) Y una
#    referencia explícita al programa. Con una sola, «la serie mensual de Castilla» dejaría de
#    ser N3 o «vs el presupuesto» dejaría de ser N1: dos respuestas correctas rotas de golpe.
_RX_PROGRAMA = re.compile(r"\b(?:PROGRAMA|PRESUPUESTO|PPTO|META|PLAN)\b")


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

    # [2026-09-03 · VENTANAS-TEMPORALES] La ventana se resuelve AL FINAL, después de que el
    # nivel ya quedó fijado. Es una capa ADITIVA: NO toca `nivel_temporal`. Resolverla antes
    # de `detectar_dia` habría convertido «el mejor día de los últimos 30 días» en algo que
    # ya no es un selector de día; resolverla dentro de `_nivel_temporal` le habría robado
    # preguntas a N4/N3/N2. Aquí no puede pisar a nadie.
    ventana = detectar_ventana(texto, techo)

    # [2026-09-03 · CURVA-VENTANA] La ventana en DÍAS/SEMANAS eleva N1 → N1DSER: la respuesta
    # correcta a «los últimos 30 días» es la CURVA de esos 30 días, no el KPI del mes (que es lo
    # que se respondía, con el rótulo del mes, sin declarar que ignoraba la ventana).
    #
    # 🔑 Solo desde N1, el default. N2/N3/N4/N1D/N1DSEL/N1DSER ya tienen dueño y NO se tocan:
    #    «el acumulado del año en los últimos 30 días» sigue siendo N2. La ventana solo reclama
    #    las preguntas que NADIE reclamó.
    # 🔑 Solo unidad `dia`/`semana` va a la CURVA. «el último mes» pide volumen mensual y el KPI
    #    que hoy responde es correcto; convertirlo en curva sería cambiarle la respuesta a una
    #    forma muy común sin que nadie lo haya pedido.
    if ventana is not None and nivel == "N1" and ventana["unidad"] in ("dia", "semana"):
        nivel = "N1DSER"
    # [2026-09-03 · VENTANA-MESES] La ventana de VARIOS meses va a N2 (acumulado ACOTADO).
    #
    # Medido antes de esto: «¿cuánto produjo Castilla en los últimos 3 meses?» resolvía la
    # ventana (jun-01 → ago-23), la declaraba en `defaults_asumidos`… y respondía el KPI de UN
    # mes, el del techo. El usuario pedía 3 meses y recibía 1, SIN aviso — `defaults_asumidos`
    # no se pinta en ninguna parte (verificado: 0 coincidencias en validador, _panel_datos y
    # multitab_shell.js). Es el bug del periodo ignorado, con el agravante de que el motor SÍ
    # sabía que eran 3 meses.
    # 🔑 N=1 se queda en N1 a propósito: «el último mes» ES el mes del techo, y el KPI mensual
    #    ya lo responde bien. Elevarlo a N2 lo rompería — ese mes está EN CURSO y `acumulado`
    #    solo suma meses CERRADOS (HE4), así que devolvería «no hay meses cerrados».
    elif (ventana is not None and nivel == "N1"
          and ventana["unidad"] == "mes" and ventana["cantidad"] > 1):
        nivel = "N2"

    # [2026-09-03 · COMPARACION-PERIODOS] Se resuelve AL FINAL, después de la ventana (P9): la
    # comparación es la intención más específica y gana a todas. Antes de `_periodo_texto`
    # porque ese detector solo ve UN mes y con dos nombrados devolvería el primero (P1).
    comparacion = detectar_comparacion(texto, techo)
    if comparacion is not None:
        # 🔑 Comparación + ventana a la vez («los últimos 3 meses vs los 3 anteriores») NO está
        #    soportada: se declina en el ejecutor con rechazo honesto, no se resuelve a medias.
        nivel = "NCMP"
    # [2026-09-03 · COMPARACION-PERIODOS] Tipo 3: serie REAL vs PROGRAMA. Exige LAS DOS señales
    # (P8) y solo eleva desde N3 — nunca desde N1/N2/N4, que responden otra cosa.
    elif nivel == "N3" and _RX_PROGRAMA.search(norm(texto or "")):
        nivel = "N3P"

    per = _periodo_texto(texto)
    defaults = [f"producto={prod}", f"referencia={ref}"]
    # 🔑 El default «periodo=mes actual» NO se declara si hay ventana: sería una contradicción
    #    en la propia declaración de supuestos (la ventana ES el periodo, y no es un mes).
    if per is None and ventana is None:
        defaults.append("periodo=mes actual")
    if dia is not None:
        defaults.extend(dia.get("asumido", []))
    if sdia is not None:
        defaults.extend(sdia.get("asumido", []))
    if ventana is not None:
        defaults.extend(ventana.get("asumido", []))
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
        "ventana": ventana,
        "comparacion": comparacion,
        # [2026-09-03 · MTD] Solo cuando el usuario pidió el acumulado DEL MES y NO nombró cuál:
        # ahí el motor elige el mes por él (el del techo) y tiene que decirlo. Si nombró el mes
        # («el acumulado del mes de julio»), el rótulo del KPI ya dice «Julio 2026» y un aviso
        # sobraría. Lo consume `ejecutar_n1`.
        "mtd": bool(_RX_MTD.search(norm(texto or ""))) and per is None and nivel == "N1",
        "defaults_asumidos": defaults,
    }
