"""Orquestador del Motor Q v2 · Fase 1 — clasificador de grupo (Etapa A de motor_Q.md).

Flujo: Capa 1 (regex, patrones.py) → si no atrapa, Capa 2 (LLM cerrado, clasificador_llm.py).
En esta fase los grupos NO responden todavía: la salida es la clasificación transparente
+ un mensaje rotulado "[Motor v2] … en construcción".

H3: clasificar(log=True) — el golden runner y los pytest pasan log=False para NO contaminar
la libreta (core.clasificacion_log registra solo tráfico real del API).
"""
from datetime import datetime, timezone
from datetime import date as _date

import sqlalchemy as sa

from app.core.db import get_engine
from app.features.consulta_v2.normaliza import norm
from app.features.consulta_v2.patrones import clasificar_capa1, es_anclado
from app.features.consulta_v2.dominio import nivel_dominio
from app.features.consulta_v2.clasificador_llm import clasificar_capa2
from app.features.consulta_v2 import log as _log
from app.features.consulta_v2 import respuesta_out
from app.features.consulta_v2 import respuesta_jerarquizar
from app.features.consulta_v2 import respuesta_cuantificar
from app.features.consulta_v2 import respuesta_analizar
from app.features.consulta_v2.analizar import subrouter as _subrouter_analizar
from app.features.consulta_v2 import no_soportado
from app.features.consulta_v2 import incompleta
from app.features.consulta_v2 import capacidades
from app.features.consulta_v2.cuantificar import slots as _slots_dia

GRUPO_LABEL = {"jerarquizar": "Jerarquizar", "cuantificar": "Cuantificar",
               "analizar": "Analizar", "desconocido": "Desconocido"}

# ---------------------------------------------------------------------------
# MEMORIA conversacional ligera (parte 2): recuerda la última entidad resuelta por conversación,
# para que una respuesta CORTA ("POE", "sí", "producción") continúe la charla en vez de morir en
# desconocido. Por proceso, sin TTL (una conversación es efímera; el reinicio la limpia).
# ---------------------------------------------------------------------------
_CTX = {}   # conversation_id -> jerarquizar: {entidad, nivel, hijos, ofrece_produccion}
            #                 -> cuantificar: {grupo, entidad, producto}  (HE2 1e + AF9 Fase 2)
_AFIRM = {"SI", "DALE", "OK", "OKEY", "CLARO", "BUENO", "LISTO", "SIP", "VALE", "ESO", "ESA"}
_PROD_KW = ("PRODUCCION", "PRODUJO", "PRODUCE", "PRODUCIDO",
            "CUANTO", "CUANTA", "CUANTOS", "CUANTAS")
# [2026-08-25 · QV2-HILO-DIA C6] Subconjunto de _PROD_KW SIN AMBIGÜEDAD: nombran el verbo de
# producción en sí. "CUANTO"/"CUANTOS"/"CUANTA"/"CUANTAS" son AMBIGUOS — "cuánto produjo" es
# producción, pero "cuántos pozos" es un CONTEO estructural. La distinción la usa el Drill N1
# GENÉRICO de abajo (:~261) para no confundir un conteo con una consulta de producción.
_PROD_EXPLICITO = ("PRODUCCION", "PRODUJO", "PRODUCE", "PRODUCIDO")
# Pistas de que una respuesta corta es una pregunta ESTRUCTURAL con pronombre elidido ("¿a qué
# activo pertenece?", "¿sus campos?") → se refiere a la entidad del contexto.
_ESTRUCT_KW = ("PERTENECE", "ACTIVO", "ACTIVOS", "GERENCIA", "GERENCIAS", "VICEPRESIDENCIA",
               "CAMPO", "CAMPOS", "ESTRUCTURA", "CONFORMAN", "COMPONE", "TIPO", "POZO", "POZOS",
               "QUE ES", "DE QUE", "A QUE", "CUAL")
# Pistas de que la frase pide un ACUMULADO (N2). Se usan en dos sitios: para detectar intención
# propia (frase autocontenida) y para el drill N1->N2 sobre la entidad del contexto.
_ACUM_KW = ("ACUMULADO", "EN EL ANO", "DEL ANO", "EN TOTAL", "YTD")
# Fase 4: pistas de que la frase corta cambia la REFERENCIA ("...contra el contable", "...frente
# al promedio del año"). DEBE revisarse ANTES que _ACUM_KW: "promedio del año" contiene "DEL ANO"
# y sin este orden _ACUM_KW la capturaría primero (bug real 2026-08-02, ver _continuacion).
_REF_CONTINUA_KW = ("OPERATIVO", "CONTABLE", "P50", "PROMEDIO")
# Pistas de continuación TEMPORAL de cuantificar (serie N3 / variación N4). Habilitan heredar la
# entidad del contexto aunque la frase pase de 5 tokens ("muéstrame la producción mes a mes" = 6),
# SIEMPRE que la frase NO nombre una entidad propia.
# [2026-08-25 · QV2-HILO-DIA F4] Los NOMBRES DE MES entran aquí. Medido: tras responder la cifra
# de junio de CASTILLA, «y en mayo?» devolvía None en _continuacion -> la frase viajaba DESNUDA
# al clasificador -> capa1 no la reconoce -> el LLM, viendo solo «y en mayo?», contestaba que
# «los periodos de tiempo» no son su dominio. No negaba saber de mayo: reaccionaba a un
# fragmento sin contexto. El hueco gemelo del acumulado (:90-109), que sí se cubrió el 24-ago:
# cambiar de MES es la continuación más natural tras leer una cifra mensual.
# 🔑 En MAYÚSCULA sin tilde: se comparan contra norm(), que pliega acentos y sube a mayúsculas.
_MESES_CONT = ("ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO",
               "SEPTIEMBRE", "SETIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE")
_TEMP_CONT_KW = ("MES A MES", "VARIACION", "COMO VARIO", "SERIE", "EVOLUCION") + _MESES_CONT

# [2026-08-25 · QV2-HILO-DIA F2] Fecha ARBITRARIA para preguntarle a detectar_dia si sabe
# resolver una forma. NO se usa el valor resultante — solo si devuelve None o no. Se elige una
# fecha con día 15 para que ninguna forma («el 30», «el 31») quede fuera por el calendario.
_TECHO_CENTINELA = _date(2000, 1, 15)

# [2026-08-26 · QV2-MES-CTX] Nombres en minúscula, en el MISMO formato que busca
# slots._periodo_texto (nombre de mes + año, p.ej. "mayo 2026") — así el mes inyectado se lee
# igual que si el usuario lo hubiera escrito. Índice 1..12; la posición 0 no se usa.
_MESES_NOMBRE = ("", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                 "septiembre", "octubre", "noviembre", "diciembre")
# Marcadores de "mes EN CURSO" explícito: si el usuario los dice, quiere HOY, no el mes de la
# conversación — no se le debe imponer el mes heredado encima de una petición explícita.
_MES_ACTUAL_KW = ("ESTE MES", "MES ACTUAL", "MES EN CURSO", "PASADO", "ANTERIOR")


def _periodo_ctx_de(datos: dict):
    """Mes de la última respuesta de cuantificar, en formato "nombre año" (p.ej. "mayo 2026"),
    o None si esa respuesta no fija un único mes sin ambigüedad.

    [2026-08-26 · QV2-MES-CTX] Bug real: tras "el día 15 de mayo, ¿cuánto produjo Castilla?"
    (N1D), preguntar "muéstrame la producción del mes" —sin nombrar mes— caía en el Drill N1
    GENÉRICO (abajo), que hereda la ENTIDAD pero deja el texto "...del mes" intacto; slots.py
    no encuentra un nombre de mes ahí y asume el mes ACTUAL (hoy), no mayo — aunque la
    conversación entera giraba en torno a mayo. Se resuelve UNA VEZ aquí, al guardar el
    contexto, y se inyecta en el Drill N1 GENÉRICO (ver más abajo) cuando aplica.

    Solo N1D/N1DSEL (fecha puntual) y N1 (mes puntual) fijan un mes sin ambigüedad — N2
    (acumulado, multi-mes), N3 (serie del año) y N4 (variación entre 2 meses) NO lo hacen."""
    fecha = datos.get("fecha")           # N1D / N1DSEL: "YYYY-MM-DD"
    if fecha:
        anio, mes = int(fecha[0:4]), int(fecha[5:7])
        return f"{_MESES_NOMBRE[mes]} {anio}"
    mes_n1 = datos.get("mes")            # N1: {"anio":int, "mes":int, ...}
    if isinstance(mes_n1, dict) and mes_n1.get("mes") and mes_n1.get("anio"):
        return f"{_MESES_NOMBRE[mes_n1['mes']]} {mes_n1['anio']}"
    return None


def _continuacion(texto, ctx):
    """Reescribe una respuesta CORTA de continuación en una pregunta autocontenida, o None.
    Solo frases de ≤5 tokens: una pregunta larga es intención propia, no continuación (excepción:
    continuación temporal de cuantificar sin entidad nombrada, ver _TEMP_CONT_KW)."""
    toks = norm(texto).split()
    if not toks:
        return None
    t = " ".join(toks)
    # [2026-08-25] QV2-META · GUARDA DE PREGUNTA META. Una pregunta sobre EL ASISTENTE
    # («¿cuál es tu finalidad?», «para qué sirves») NO es una continuación de la charla:
    # no se reescribe, se deja pasar entera para que la rama OUT la reconozca.
    # 🔑 SIN esta guarda el módulo capacidades NUNCA se ejecutaría a mitad de conversación.
    # Medido 2026-08-25 con ctx vivo: «¿cuál es tu finalidad?» (4 toks) y «cuáles son tus
    # capacidades» (4 toks) hacen hit en _ESTRUCT_KW por "CUAL", y «para qué sirves» (3
    # toks) por "A QUE" (substring de «pARA QUÉ») -> las tres caían en la rama estructural
    # de abajo y se reescribían a "que es {entidad}": el usuario pedía saber qué sabe hacer
    # el bot y recibía la ficha jerárquica de CASTILLA.
    # Va ANTES de TODAS las ramas (incluida la de ranking y la de analizar, que cortan con
    # return propio) porque ninguna debe verlas primero.
    if capacidades.detectar(texto, False) is not None:
        return None
    ent = respuesta_jerarquizar.entidad_en(texto)      # ¿nombra una entidad (hijo o cualquiera)?
    # Excepción de longitud: una continuación de serie/variación que NO nombra entidad hereda la del
    # contexto de cuantificar aunque supere 5 tokens. Exige ctx de cuantificar CON entidad (el ctx de
    # ranking no tiene 'entidad') y que la frase NO nombre una entidad nueva (esa sería autocontenida).
    # [2026-08-25 · QV2-HILO-DIA F4] `not any(_ESTRUCT_KW)` es NUEVO y no es opcional. Al entrar
    # los meses en _TEMP_CONT_KW (arriba), esta rama —que corre ANTES que la estructural de
    # abajo— capturaba también las preguntas de ESTRUCTURA que mencionan un mes: medido,
    # «cuántos pozos en mayo» se reescribía a «produccion de CASTILLA cuantos pozos en mayo» y
    # el usuario recibía una cifra de producción en vez del número de pozos. La guarda devuelve
    # esas frases a la rama estructural, que es la suya.
    # [2026-09-03 · VENTANA-CONT] La VENTANA se consulta al DETECTOR REAL, no a una lista de
    # palabras paralela. Medido: «¿en los últimos 6 meses?» tras un N2 de CASTILLA devolvía None
    # y caía a Desconocido («No logré entender tu pregunta») — el usuario estaba a mitad de una
    # conversación de Cuantificar y el motor perdía el hilo por una forma temporal que él MISMO
    # sabe resolver desde `detectar_ventana`. Añadir "ULTIMOS"/"ULTIMAS" a _TEMP_CONT_KW habría
    # creado un segundo criterio de ventana que se desincroniza del primero — el fallo que
    # `_forma_no_soportada_ranking` (respuesta_cuantificar.py) ya documenta haber sufrido. Un
    # detector, dos consumidores.
    # 🔑 Techo CENTINELA: solo se pregunta «¿es esto una ventana?»; la fecha que salga se descarta.
    _es_ventana = _slots_dia.detectar_ventana(texto, _slots_dia.TECHO_CENTINELA) is not None
    if (ctx.get("grupo") == "cuantificar" and ctx.get("entidad") and not ent
            and (any(k in t for k in _TEMP_CONT_KW) or _es_ventana)
            and not any(k in t for k in _ESTRUCT_KW)):
        prod_t = ctx.get("producto", "crudo")
        pieza_t = "" if prod_t == "crudo" else f"{prod_t} de "
        return f"produccion de {pieza_t}{ctx['entidad']} {texto.strip()}"
    # [2026-08-24] Excepción de longitud para el ACUMULADO. El cierre de cuantificar OFRECE
    # justo eso ("¿Quieres el acumulado del año?") y aceptarlo con la frase natural —"Sí
    # muéstrame el acumulado del año", 6 tokens— se pasaba de este corte y caía desnuda a la
    # Capa 2 → Desconocido: el motor no reconocía su propia oferta. La pista de que era un
    # problema de LONGITUD y no de sentido: con coma ("sí, el acumulado del año", 5 tokens)
    # funcionaba y sin coma no.
    # Condiciones deliberadamente estrechas, para no abrir el corte a cualquier frase larga:
    #   · ctx de cuantificar CON entidad — es la única rama que sabe reescribir el acumulado
    #     (abajo, "acumulado de {entidad}"); sin entidad no hay nada que heredar.
    #   · la frase NO nombra entidad propia (not ent) — "el acumulado del año de CASTILLA" es
    #     autocontenida y debe procesarse entera, no heredar la del contexto.
    #   · NO trae pista de REFERENCIA — "promedio del año" contiene "DEL ANO" y su rama va
    #     antes por el mismo motivo documentado en _REF_CONTINUA_KW.
    # Tope de 8 tokens: cubre las cortesías reales ("sí dame el acumulado del año por favor")
    # sin convertir el corte en papel mojado.
    if (len(toks) > 5 and len(toks) <= 8
            and ctx.get("grupo") == "cuantificar" and ctx.get("entidad") and not ent
            and any(k in t for k in _ACUM_KW)
            and not any(k in t for k in _REF_CONTINUA_KW)):
        pass          # sigue hacia la rama del acumulado, que reescribe bien
    elif len(toks) > 5:
        return None
    prod = any(w in t for w in _PROD_KW)
    if ent:
        # 🔑 Si ADEMÁS trae intención propia (verbo de producción o "acumulado"), la frase es
        # AUTOCONTENIDA y NO se reescribe: la plantilla "produccion de {ent}" borra todo slot que
        # el texto ya traía. Bug real (2026-08-02): "cuántos blancos produjo Cupiagua" (4 tokens,
        # entra al reescritor) -> "produccion de CUPIAGUA" -> slots re-detecta crudo -> respondía
        # CRUDO a una pregunta de BLANCOS. Igual borraba el mes ("cuánto produjo Castilla en abril"
        # = 5 tokens) y convertía "cuántos pozos tiene X" en una consulta de producción.
        # El texto original ya clasifica solo: PRODUCCION/PRODUJO/CUANTO son disparadores de
        # cuantificar, y detectar_entidad encuentra la entidad igual.
        if prod or any(k in t for k in _ACUM_KW):
            return None
        return f"que es {ent}"
    # Drill de RANKING (N5): tras "te lo doy por otro producto o cambiando el orden", una respuesta
    # corta que cambia el PRODUCTO ("para crudo", "y gas?", "blancos") o el ORDEN ("al revés",
    # "cambiando el orden", "los que menos") re-lanza el MISMO ranking. Corta SIEMPRE para un ctx de
    # ranking (return propio) — así no cae en los drills N1/N2 de abajo, que harían KeyError
    # (ctx de ranking no lleva "entidad"). Bug real: "para crudo?" tras un ranking caía a Desconocido.
    if ctx.get("subgrupo") == "ranking":
        nuevo_prod = ("gas" if "GAS" in t else
                      "blancos" if ("BLANCOS" in t or "BLANCO" in t) else
                      "crudo" if "CRUDO" in t else None)
        flip = any(k in t for k in ("REVES", "INVIERTE", "INVERTIR", "ASCENDENTE", "CAMBIA",
                                    "CAMBIANDO", "ORDEN", "MENOS", "MENOR", "MENORES", "ABAJO",
                                    "ULTIMOS", "PEORES"))
        if not (nuevo_prod or flip):
            return None
        prod_r = nuevo_prod or ctx.get("producto", "crudo")
        direccion = ctx.get("direccion", "top")
        if flip:
            direccion = "bottom" if direccion == "top" else "top"
        nivel_pl = "activos" if ctx.get("nivel_ranking") == "activo" else "campos"
        if ctx.get("metrica") == "gap":
            que = "con mayor excedente" if direccion == "top" else "que quedaron mas cortos"
            return f"cuales {nivel_pl} {que} frente al presupuesto de {prod_r}"
        dirw = "mayores" if direccion == "top" else "menores"
        return f"cuales {nivel_pl} son los {dirw} productores de {prod_r}"
    # Drill de ANALIZAR: los cierres de este grupo OFRECEN un siguiente paso ("¿Quieres el detalle
    # por campo, o la proyección de cierre?" / "¿Quieres ver qué campos explican el faltante?") →
    # un "sí" pelado tiene que ir a ese siguiente paso. Sin esta rama (bug real 2026-08-04) el "sí"
    # viajaba DESNUDO a la Capa 2 y el LLM respondía sobre la conjunción "si" → Desconocido.
    # Corta SIEMPRE para un ctx de analizar (return propio): su ctx puede NO llevar "entidad"
    # (análisis global ECP) y los drills N1/N2 de abajo harían KeyError.
    if ctx.get("grupo") == "analizar":
        ent_a = ctx.get("entidad")
        prod_a = ctx.get("producto")
        pieza_a = f"de {prod_a} " if prod_a else ""
        cola_a = f"de {ent_a} " if ent_a else ""
        # Palabra explícita en la respuesta corta > opción por defecto del cierre ofrecido.
        if any(k in t for k in ("EBITDA", "NOPAT", "MARGEN", "RENTABILIDAD")):
            destino = "economia"
        elif any(k in t for k in ("DIFERIDAS", "MANTENIMIENTO", "MANTENIMIENTOS")):
            destino = "diferidas"
        elif any(k in t for k in ("PROYECCION", "PROYECTA", "CIERRE", "CERRAR")):
            destino = "proyeccion"
        elif any(k in t for k in ("CAMPO", "CAMPOS", "DETALLE", "DETRACTORES", "FALTANTE",
                                  "EXPLICA", "EXPLICAN", "CAUSA", "CAUSAS")):
            destino = "causal"
        # [2026-08-13] Palabras del cierre del declinar de REFERENCIA (M9 del plan
        # plan_p50_referencia_analizar_2026-08-13.md: "Dime cuál te sirve: el presupuesto o la
        # vicepresidencia."). Sin esto, ninguna de las 2 opciones del declinar tenía continuación
        # reconocida por el drill -> la respuesta del usuario habría caído a Desconocido (H3).
        elif any(k in t for k in ("PRESUPUESTO", "PPTO")):
            destino = "causal"          # el análisis vs PPTO es la ruta causal existente
        elif any(k in t for k in ("VICEPRESIDENCIA", "VP")):
            destino = "referencia"
        elif t in _AFIRM:
            # "sí" a secas: se toma la opción que el cierre de ESA sub-intención ofrecía.
            # Tras proyección se ofreció "qué campos explican el faltante" (= causal); tras causal
            # se ofreció "el detalle por campo, o la proyección" → proyección (el detalle por campo
            # ya viene dentro del bloque CAUSA que el usuario acaba de leer). [2026-08-13] Tras
            # 'referencia' (H4): el "else" de abajo daría "proyeccion", que no es lo que se ofreció
            # (el declinar SIEMPRE cierra nombrando 2 opciones, nunca en sí/no — M5 — así que este
            # caso es defensivo, no la ruta principal).
            destino = "causal" if ctx.get("sub") in ("proyeccion", "referencia") else "proyeccion"
        else:
            return None
        # Las reescrituras llevan SIEMPRE "produccion" (vocabulario FUERTE del filtro de dominio)
        # → enrutan directo por regex, sin escalar a la Capa 2.
        if destino == "economia":
            return f"ebitda de la produccion {cola_a}".strip()
        if destino == "diferidas":
            return f"diferidas de la produccion {pieza_a}{cola_a}".strip()
        if destino == "proyeccion":
            return f"cual es la proyeccion de cierre de la produccion {pieza_a}{cola_a}".strip()
        if destino == "referencia":
            # 🔑 Si el turno anterior fue un declinar que OFRECIÓ una vicepresidencia, "la
            # vicepresidencia" se refiere a ESA (ctx['vp']), no al campo del ctx. Sin esto la
            # reescritura repetía el nombre del CAMPO -> volvía a resolver como campo -> el mismo
            # declinar, en BUCLE (bug real reproducido en la verificación 2026-08-13: el usuario
            # elegía "la vicepresidencia" y recibía otra vez la oferta de vicepresidencia).
            vp_a = ctx.get("vp")
            if vp_a:
                return f"cual es el p50 de la produccion {pieza_a}de {vp_a}".strip()
            return f"cual es el p50 de la produccion {pieza_a}{cola_a}".strip()
        return f"por que la produccion {pieza_a}{cola_a}esta corta".strip()
    # Fase 4: drill de REFERENCIA sobre la MISMA pregunta puntual ("vs operativo" -> "...contra el
    # contable" / "...frente al promedio del año"). Va ANTES del check de _ACUM_KW (abajo): sin este
    # orden, "promedio del año" (contiene "DEL ANO") caía en el drill de ACUMULADO y daba el
    # acumulado vs PPTO — una cifra DISTINTA a la pedida, servida con la misma confianza. Bug real
    # hallado en pruebas de navegador (2026-08-02). Preserva el producto (criterio AF9); la
    # referencia queda VERBATIM en el texto reescrito y la detecta slots._referencia() aguas abajo
    # (incl. el override AF-4.9: "promedio del año" fuerza N1, no N2, en extraer_slots).
    if ctx.get("grupo") == "cuantificar" and any(k in t for k in _REF_CONTINUA_KW):
        prod_ref = ctx.get("producto", "crudo")
        pieza_ref = "" if prod_ref == "crudo" else f"{prod_ref} de "
        return f"produccion de {pieza_ref}{ctx['entidad']} {texto.strip()}"
    # 1e (HE5): drill de cuantificar N1 -> N2. Va ANTES del check de ofrece_produccion (abajo) —
    # el ctx de cuantificar NUNCA lleva esa clave (solo la puebla jerarquizar), pero el orden importa
    # si en el futuro se unifican: un "sí"/"acumulado" tras N1 debe ir a N2, no repetir N1.
    if ctx.get("grupo") == "cuantificar" and \
       (any(k in t for k in _ACUM_KW) or t in _AFIRM):
        # AF9: preservar el producto del N1 (si no, "acumulado" tras un N1 de gas volvería a crudo).
        prod = ctx.get("producto", "crudo")
        pieza = "" if prod == "crudo" else f"{prod} de "
        return f"acumulado de {pieza}{ctx['entidad']}"
    # Drill N1 GENÉRICO: el texto trae intención de producción (verbo/"cuánto") pero NO nombra la
    # entidad ni pide acumulado/referencia (ya descartados arriba) — p.ej. "Mayo, ¿cuánto ha
    # producido?" o "¿cuánto en abril?" tras hablar de Rubiales. Bug real hallado en pruebas de
    # navegador (2026-08-02): sin esta rama, la memoria de conversación perdía el hilo apenas el
    # usuario cambiaba de mes sin repetir el nombre de la entidad — caía a Desconocido pese a estar
    # a mitad de una conversación de Cuantificar. Misma entidad, mismo producto (AF9); el texto
    # ORIGINAL viaja completo — es ahí donde `slots._periodo_texto` encuentra "mayo"/"abril".
    # [2026-08-25 · QV2-HILO-DIA C6] `ambiguo_estructural` es NUEVO. Esta rama disparaba también
    # para preguntas de ESTRUCTURA que solo comparten con "producción" la palabra ambigua
    # CUANTO/CUANTOS: medido, «cuántos pozos en mayo» se reescribía a «produccion de CASTILLA
    # cuantos pozos en mayo» y el usuario recibía una cifra en vez del número de pozos — un bug
    # PREEXISTENTE (2026-08-02), no introducido hoy, descubierto al verificar C4.b (H-10).
    # Un guarda simétrico a C4.b (`not any(_ESTRUCT_KW)`) ROMPERÍA "cuánto produjo el CAMPO en
    # mayo": esa frase SÍ es producción y menciona "campo" solo de forma genérica. El
    # discriminador correcto no es "¿hay palabra estructural?" sino "¿el ÚNICO indicio de
    # producción es el CUANTO/CUANTOS ambiguo, sin verbo explícito?" — verificado contra 8 casos,
    # incluida esta frase con verbo explícito, antes de aplicarlo.
    ambiguo_estructural = (any(k in t for k in _ESTRUCT_KW)
                           and not any(k in t for k in _PROD_EXPLICITO))
    if ctx.get("grupo") == "cuantificar" and prod and not ambiguo_estructural:
        prod_gen = ctx.get("producto", "crudo")
        pieza_gen = "" if prod_gen == "crudo" else f"{prod_gen} de "
        # [2026-08-26 · QV2-MES-CTX] La frase NO nombra su propio mes → hereda el de la ÚLTIMA
        # respuesta, para no perder el hilo de "el día 15 de mayo" a "la producción del mes"
        # (que sin esto asumía HOY, no mayo). Se retira si la frase YA trae un mes propio (caso
        # límite: nombra un mes Y una palabra estructural con verbo explícito, p.ej. "cuánto
        # produjo el campo en junio" — ahí "junio" debe ganar, no sumarse a lo heredado) o si
        # pide explícitamente el mes EN CURSO (_MES_ACTUAL_KW) — eso SÍ es HOY, no lo heredado.
        periodo_ctx = ctx.get("periodo_ctx")
        sufijo_periodo = (f" en {periodo_ctx}"
                          if periodo_ctx and not any(k in t for k in _MES_ACTUAL_KW)
                             and not any(k in t for k in _MESES_CONT)
                          else "")
        return f"produccion de {pieza_gen}{ctx['entidad']} {texto.strip()}{sufijo_periodo}"
    if ctx.get("ofrece_produccion") and (prod or t in _AFIRM):
        return f"produccion de {ctx['entidad']}"
    # Pregunta estructural con pronombre elidido ("a qué activo pertenece?", "y sus campos?"): se
    # refiere a la entidad del contexto. Se reescribe a "que es {entidad}" (SIEMPRE clasifica
    # jerarquizar; el árbol completo ya trae activo/gerencia/VP/campos → responde lo que preguntan).
    # Añadir la entidad al texto tal cual era frágil: "y sus campos CHICHIMENE" no matchea patrón.
    if any(k in t for k in _ESTRUCT_KW):
        return f"que es {ctx['entidad']}"
    return None

# ---------------------------------------------------------------------------
# Backstop de entidad (A1: best-effort, informativo, NUNCA bloquea).
# FORK de consulta/resolver.py (buscar_en_texto/_STOP) @ 2026-07-30 — razón: aislamiento v2.
# Versión acotada: solo un SET de nombres normalizados (no identidades por nivel — eso es
# Etapa B). Lee las mismas tablas vía get_engine() (Anillo 3 / infraestructura).
# ---------------------------------------------------------------------------
_STOP = {"QUE", "ES", "DE", "DEL", "LA", "EL", "LO", "LOS", "LAS", "UN", "UNA", "EN", "Y", "O",
         "A", "AL", "POR", "PARA", "CON", "SIN", "SU", "SUS", "ME", "MI", "SE", "ESO", "AHI",
         "PRODUCCION", "PRODUJO", "PRODUCE", "CUANTO", "CUANTA", "COMO", "CUAL", "CUALES",
         "DAME", "MUESTRAME", "INFORMACION", "INFO", "DATOS", "REPORTE", "REPORTES", "TAL",
         "META", "GAP", "MES", "DIA", "DIAS", "ANO", "CRUDO", "GAS", "BLANCOS", "AGUA"}

# [2026-08-25] Visto en la app: "¿Mejor día de Castilla ESTE MES?" resolvía la entidad a
# «CASTILLA ESTE» —un campo REAL del catálogo— en vez de CASTILLA, y contestaba sobre el campo
# equivocado. Causa: detectar_entidad prueba n-gramas de MAYOR a menor, así que el bigrama
# "CASTILLA ESTE" le gana al unigrama "CASTILLA"; el demostrativo de "este mes" quedaba pegado
# al nombre. Medido contra el catálogo (273 nombres): 5 campos terminan en ESTE y su base también
# es una entidad → APIAY, CAÑO SUR, CASTILLA, REDONDO y TISQUIRAMA quedaban expuestos.
# NORTE y SUR también cierran nombres (9 campos más) pero NUNCA son demostrativos en español
# —"Castilla norte mes" no es una frase— así que quedan fuera de la guarda a propósito.
_DEMOSTRATIVOS = {"ESTE", "ESTA", "ESTOS", "ESTAS"}
_TEMPORAL_TRAS_DEMOSTRATIVO = {"MES", "MESES", "ANO", "ANOS", "DIA", "DIAS", "SEMANA", "SEMANAS",
                               "TRIMESTRE", "SEMESTRE", "BIMESTRE", "PERIODO", "CORTE"}

_NOMBRES = None   # set de nombres normalizados del catálogo

_QUERIES_CATALOGO = [
    "SELECT DISTINCT nombre   FROM core.dim_fuente          WHERE NULLIF(TRIM(nombre),'')   IS NOT NULL",
    "SELECT DISTINCT campo    FROM core.dim_fuente          WHERE NULLIF(TRIM(campo),'')    IS NOT NULL",
    "SELECT DISTINCT gerencia FROM core.dim_fuente          WHERE NULLIF(TRIM(gerencia),'') IS NOT NULL",
    "SELECT DISTINCT operador FROM core.dim_fuente          WHERE NULLIF(TRIM(operador),'') IS NOT NULL",
    "SELECT DISTINCT activo   FROM core.map_campo_activo    WHERE NULLIF(TRIM(activo),'')   IS NOT NULL",
    "SELECT DISTINCT codigo   FROM core.dim_vicepresidencia WHERE NULLIF(TRIM(codigo),'')   IS NOT NULL",
    "SELECT DISTINCT nombre   FROM core.dim_empresa         WHERE NULLIF(TRIM(nombre),'')   IS NOT NULL",
    # Jerarquía de ROBUSTEZ (fuente de verdad, S28): sus gerencias (POE/PPÑ…), activos y VPs NO están
    # en dim_fuente → sin esto, "que es POE" caería a OUT. Tolerante: si la tabla no está (139 sin
    # cargar), esa consulta se salta y el resto del catálogo sigue.
    "SELECT DISTINCT rob_gerencia       FROM core.map_campo_robustez WHERE NULLIF(TRIM(rob_gerencia),'')       IS NOT NULL",
    "SELECT DISTINCT rob_activo         FROM core.map_campo_robustez WHERE NULLIF(TRIM(rob_activo),'')         IS NOT NULL",
    "SELECT DISTINCT rob_vicepresidencia FROM core.map_campo_robustez WHERE NULLIF(TRIM(rob_vicepresidencia),'') IS NOT NULL",
]


def _nombres():
    """Carga perezosa del set de nombres. Si la BD no está disponible, set vacío
    (A1: la entidad es informativa — no puede tumbar la clasificación)."""
    global _NOMBRES
    if _NOMBRES is not None:
        return _NOMBRES
    nombres = set()
    ok = False
    try:
        eng = get_engine()
        # AUTOCOMMIT: una consulta que falle (tabla ausente) NO envenena las siguientes.
        with eng.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
            for q in _QUERIES_CATALOGO:
                try:
                    for (val,) in c.execute(sa.text(q)):
                        k = norm(val)
                        if k:
                            nombres.add(k)
                    ok = True
                except Exception:
                    continue   # p.ej. map_campo_robustez sin cargar en 139 → se salta esa consulta
    except Exception:
        return set()   # sin cachear: reintenta en la próxima llamada
    if not ok:
        return set()
    _NOMBRES = nombres
    return nombres


def detectar_entidad(texto: str):
    """N-gramas (largos primero) contra el catálogo cerrado. Devuelve el match o None."""
    nombres = _nombres()
    if not nombres:
        return None
    palabras = [p for p in (w.strip("¿?¡!.,;:()[]{}\"'`") for w in norm(texto).split()) if p]
    n = len(palabras)
    for size in range(min(n, 4), 0, -1):
        for start in range(0, n - size + 1):
            gram = " ".join(palabras[start:start + size])
            if size == 1 and gram in _STOP:
                continue
            # El n-grama termina en demostrativo Y lo que sigue es un sustantivo de tiempo:
            # el demostrativo es de la frase temporal, no del nombre ("Castilla | este mes").
            # Se descarta ESTE candidato y el bucle sigue con n-gramas más cortos → CASTILLA.
            # La entidad real se conserva: en "Castilla Este este mes" el bigrama va seguido de
            # ESTE (no temporal) y pasa; en "¿cuánto produjo Castilla Este?" no hay nada detrás.
            if size > 1 and palabras[start + size - 1] in _DEMOSTRATIVOS:
                sig = palabras[start + size] if start + size < n else None
                if sig in _TEMPORAL_TRAS_DEMOSTRATIVO:
                    continue
            if gram in nombres:
                return gram
    return None


# ---------------------------------------------------------------------------
# Mensajes de la fase (los grupos aún no responden)
# ---------------------------------------------------------------------------
# H-I: el rótulo debe decir la verdad de QUIÉN decidió. Sin este mapa, 'regex+llm_fallo'
# (el LLM no respondió y mandó la regex) se anunciaba como "vía LLM" — mentira al usuario y
# al revisor de la libreta.
_VIA_TXT = {"regex": "vía regex", "regex+filtro": "vía regex", "llm": "vía LLM",
            "regex+llm": "vía regex + LLM", "regex+llm_fallo": "vía regex"}


def _mensaje(grupo: str, capa: str, entidad):
    if grupo == "desconocido":
        # OUT: floor estático. Es la respuesta en log=False (golden/pytest) y el fallback si el
        # LLM falla. El texto VIVO lo redacta respuesta_out.redactar_out en tráfico real.
        return respuesta_out.TEXTO_FALLBACK
    via = _VIA_TXT.get(capa, "vía LLM")
    ent = f" Entidad detectada: «{entidad}»." if entidad else ""
    return (f"Clasifiqué tu pregunta como {GRUPO_LABEL[grupo]} ({via}).{ent} "
            f"Los módulos de respuesta del Motor v2 están en construcción — "
            f"usa el Motor v1 para obtener la respuesta.")


def _clasificar_core(texto: str, usuario=None, conversation_id=None, log: bool = True) -> dict:
    """Contrato de motor_Q.md §1.3 + log_id + mensaje renderizable. Núcleo SIN memoria (lo
    envuelve `clasificar`); los golden/pytest lo llaman a través de `clasificar` con log=False."""
    grupo, patrones = clasificar_capa1(texto)
    capa, entidad, diag = "regex", None, None
    if grupo is not None:
        # FILTRO DE DOMINIO (motor_Q.md §1.2 · D2/D3): la regex atrapó la FORMA; confirmar el TEMA.
        # Solo sobre patrones GENÉRICOS — los anclados ya son señal de dominio y se saltan.
        if not es_anclado(patrones):
            entidad = detectar_entidad(texto)
            if not entidad:
                nivel = nivel_dominio(texto)
                if nivel is None:
                    # Ni entidad del catálogo ni palabra de producción → fuera de dominio (OUT).
                    # D1 del plan del filtro: el token OUT es 'desconocido'. Se conservan los
                    # patrones para trazar en la libreta POR QUÉ disparó la regex.
                    grupo, capa = "desconocido", "regex+filtro"
                elif nivel == "estructural":
                    # CERTEZA DÉBIL: la única evidencia es CAMPOS/POZOS/ACTIVOS, que también son
                    # español común. La regex no ve el contexto gramatical ("campos de la dieta
                    # mediterránea" vs "campos por debajo de la meta" traen la MISMA palabra) →
                    # lo confirma la Capa 2, que sí entiende contexto.
                    r = clasificar_capa2(texto)
                    if r.get("diag"):
                        # D4 · FALLBACK OBLIGATORIO: el LLM falló (timeout/conexión/JSON malo) →
                        # se CONSERVA el grupo de la regex. Una caída del LLM degrada al
                        # comportamiento previo; jamás se traga una pregunta legítima.
                        capa, diag = "regex+llm_fallo", r["diag"]
                    else:
                        # El LLM respondió: su veredicto manda. D6: su 'entidad' se IGNORA — se
                        # escaló porque el catálogo no halló ninguna; si la inventa, mentiría.
                        grupo, capa = r["grupo"], "regex+llm"
    else:
        r = clasificar_capa2(texto)
        grupo, entidad, diag, capa = r["grupo"], r.get("entidad"), r.get("diag"), "llm"
        patrones = []
    if not entidad:
        entidad = detectar_entidad(texto)   # backstop (también aporta en Capa 1)

    log_id = None
    if log:
        try:
            log_id = _log.registrar(texto, grupo, capa, patrones=patrones or None,
                                    entidad=entidad, usuario=usuario,
                                    conversation_id=conversation_id, llm_diag=diag)
        except Exception:
            log_id = None   # la libreta nunca tumba la respuesta (regla madre)

    mensaje = _mensaje(grupo, capa, entidad)
    # 1d (HD4), ampliado 2026-08-11: cuantificar Y jerarquizar lo pueblan (árbol/ranking
    # estructural); OUT lo deja None (aditivo).
    panel = None
    vp_ofrecida = None   # solo lo puebla el declinar de `referencia` (ANALIZAR) — ver más abajo
    if grupo == "desconocido" and log:
        # OUT — dos caminos. Solo en tráfico real (log=True): el golden/pytest (log=False) no entran
        # aquí (no gastan generación ni tocan _CTX).
        # (B) Si el hilo YA resolvió una entidad (contexto ⇒ dominio confirmado) y la pregunta tiene
        #     la FORMA de una capacidad no construida (rango de días/trimestre/año/semana), se
        #     responde un rechazo HONESTO determinista que nombra la entidad y dice qué SÍ puede,
        #     SIN gastar el LLM. Es el molde de rechazo de cuantificar/ejecutor, por la ruta OUT.
        #     Sin entidad en contexto NO se afirma "no soportado": en frío, "¿cuántos días tiene un
        #     trimestre?" y "del primer trimestre ¿cuánto?" son indistinguibles sin LLM.
        # (A) En cualquier otro caso lo redacta el LLM, ahora CON el contexto reciente para
        #     reconocer el hilo y no inventar periodos. Si el LLM falla o el flag está off,
        #     redactar_out devuelve el floor estático → mismo texto que _mensaje.
        # 🔑 _CTX aquí refleja el turno ANTERIOR (se actualiza al final de `clasificar`) — es
        #    exactamente el "hilo reciente" que se quiere reconocer.
        ctx = _CTX.get(conversation_id) if conversation_id else None
        ent_ctx = (ctx or {}).get("entidad")
        # (META) [2026-08-25] QV2-META. La pregunta es sobre EL ASISTENTE, no sobre
        #     producción («¿cuál es tu finalidad?», «hola»). Va PRIMERA de las cuatro: es
        #     la única que NO depende del contexto — es típicamente el PRIMER turno, cuando
        #     _CTX está vacío y (B) ni siquiera se consulta. Sin ella, el prompt de
        #     respuesta_out respondía que preguntar qué sabe hacer es un tema "fuera de
        #     contexto": el motor despedía al usuario en su primera frase.
        #     `entidad` ya está calculada arriba: no se recalcula (criterio de (C)).
        forma_meta = capacidades.detectar(texto, bool(entidad))
        # [2026-08-25 · QV2-HILO-DIA F2] La rama OUT llamaba a `detectar` CRUDO, sin el filtro
        # que la ruta de cuantificar ya aplica (respuesta_cuantificar._FORMAS_RECHAZO, donde
        # 'dia' y 'selector_dia' salieron al implementarse N1D). Resultado medido: a «el 15 de
        # mayo?» se le respondía "solo puedo darte el mes completo" MIENTRAS el motor mostraba
        # la curva diaria con ese día resaltado — negaba una capacidad que tiene.
        forma = no_soportado.detectar(texto) if (ent_ctx and not forma_meta) else None
        # 🔑 Se filtra por lo que N1D SABE RESOLVER, no por el código de la forma. El código
        #    'dia' agrupa cosas muy distintas: "el 15 de mayo" y "ayer" los responde N1D, pero
        #    "el lunes", "este día" y "el último día" NO —y para esas el rechazo honesto sigue
        #    siendo la respuesta correcta—. Filtrar por código las dejaría mudas: el motor
        #    degradaría al mes entero en silencio, que es el bug #5 que no_soportado existe
        #    para impedir.
        # 🔑 El techo es un CENTINELA fijo, no el real: aquí solo se pregunta "¿sabes resolver
        #    esta FORMA?", y la fecha que salga se descarta. Con techo=None NO sirve —medido:
        #    "el 15 de mayo?" daría None y seguiría rechazándose, sin arreglar nada— porque las
        #    ramas de fecha necesitan un año de referencia. Usar el techo REAL exigiría una
        #    consulta a BD en la rama OUT, que es justo lo que el pre-check `menciona_dia` de
        #    respuesta_cuantificar existe para evitar.
        if forma in ("dia", "selector_dia") and \
                _slots_dia.detectar_dia(texto, _TECHO_CENTINELA) is not None:
            forma = None
        if forma_meta:
            mensaje = capacidades.mensaje(forma_meta, usuario=usuario)
        elif forma:
            mensaje = no_soportado.mensaje(forma, ent_ctx)
        # (C) [2026-08-21] La frase invoca una ACCIÓN sin nada sobre lo que recaiga ("sí
        #     muéstrame"): en dominio, con capacidad construida, pero MAL FORMADA. Va DESPUÉS
        #     de (B) — "muéstrame el trimestre" es primero una capacidad no construida y solo
        #     después una frase incompleta; el rechazo honesto de (B) es más informativo. Y va
        #     ANTES de (A) — el LLM respondería "fuera de mi ámbito" a una pregunta que SÍ es
        #     del tema, solo que le falta el complemento (era el bug reportado).
        #     `entidad` y nivel_dominio(texto) ya están calculados arriba: no se recalculan.
        elif incompleta.detectar(texto, bool(entidad), nivel_dominio(texto)):
            mensaje = incompleta.mensaje("accion_sin_objeto", ent_ctx)
        else:
            mensaje = respuesta_out.redactar_out(texto, usuario=usuario, contexto=ctx)["texto"]
    elif grupo == "jerarquizar" and log:
        # JERARQUIZAR responde la estructura (identidad + pertenencia + composición) desde la
        # fuente de verdad robustez (core.map_campo_robustez). Los HECHOS son deterministas; el LLM
        # solo los ENVUELVE con marco cordial dinámico (intro + cierre), sin tocarlos (B). Solo en
        # tráfico real; si la tabla no está (139 sin deploy) devuelve None → queda 'en construcción'.
        # [2026-08-11] responder_cordial devuelve {mensaje, panel} (mismo contrato que cuantificar,
        # :378-381) cuando resuelve una entidad o un ranking estructural; en los demás casos (sin
        # entidad, ranking que declina) sigue devolviendo un str plano y panel se queda en None.
        r = respuesta_jerarquizar.responder_cordial(texto, usuario=usuario)
        if isinstance(r, dict):
            mensaje = r.get("mensaje") or mensaje
            panel = r.get("panel")
        elif r:
            mensaje = r
    elif grupo == "cuantificar" and log:
        # CUANTIFICAR — Fase 1 (plan_cuantificar_fase1_2026-08-02.md + cierre). `entidad` = lo que el
        # backstop de catálogo ya detectó arriba (detectar_entidad); el resolver propio de cuantificar
        # (D-D5) es quien decide de verdad. `responder()` devuelve SIEMPRE {mensaje, panel} (1d, HD4).
        r = respuesta_cuantificar.responder(texto, entidad=entidad, usuario=usuario,
                                            conversation_id=conversation_id)
        if isinstance(r, dict):
            mensaje = r.get("mensaje") or mensaje
            panel = r.get("panel")
        elif r:
            mensaje = r
    elif grupo == "analizar" and log:
        # ANALIZAR — envuelve analisis.ejecutivo (motor ya existente) → narrativa causal (dónde está
        # el faltante + por qué) o proyección de cierre. Los HECHOS son deterministas; el LLM solo el
        # intro cordial. responder_con_panel() devuelve {mensaje, panel} (mismo contrato que
        # jerarquizar/cuantificar, :374-389). [2026-08-13, H5 del plan_panel_p50_vp] SOLO 2
        # sub-intenciones producen panel: causal (tipo "analiza_foco", el acordeón de foco apilado)
        # y referencia — pero SOLO en su rama de vicepresidencia afirmativa (tipo "p50_vp"); el
        # resto (proyección/diferidas/economía/referencia-global/referencia-declinar) va con
        # panel=None, cada una con su propia forma de respuesta. Solo tráfico real.
        r = respuesta_analizar.responder_con_panel(texto, entidad=entidad, usuario=usuario,
                                                    conversation_id=conversation_id)
        if isinstance(r, dict):
            mensaje = r.get("mensaje") or mensaje
            panel = r.get("panel")
            # [2026-08-13] Solo la rama `referencia` que DECLINA lo puebla: el código de la VP que
            # se ofreció, para que el drill "la vicepresidencia" reescriba con ELLA y no con el
            # campo (o repetiría el mismo declinar, en bucle).
            vp_ofrecida = r.get("vp_ofrecida")
        elif r:
            mensaje = r

    return {
        "log_id": log_id,
        "texto_original": texto,
        "grupo": grupo,
        "grupo_label": GRUPO_LABEL[grupo],
        "capa_resolutora": capa,
        "entidad_cruda": entidad,
        "patrones": patrones or [],
        "llm_diag": diag,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mensaje": mensaje,
        "panel": panel,   # 1d: aditivo — OUT = None; cuantificar/jerarquizar = {tipo, datos} o None
        "vp_ofrecida": vp_ofrecida,   # solo el declinar de `referencia`; None en todo lo demás
    }


def clasificar(texto: str, usuario=None, conversation_id=None, log: bool = True) -> dict:
    """Envoltura con MEMORIA conversacional. Si el mensaje es una continuación corta de lo último
    que se habló (hay contexto y ≤5 tokens), se reescribe a una pregunta autocontenida ANTES de
    clasificar → así "POE"/"sí"/"producción" siguen la charla. Solo en tráfico real (log=True); el
    golden/pytest pasan log=False y NO tocan la memoria (comportamiento idéntico al núcleo)."""
    efectivo, continuacion = texto, False
    if log and conversation_id and conversation_id in _CTX:
        rw = _continuacion(texto, _CTX[conversation_id])
        if rw:
            efectivo, continuacion = rw, True

    res = _clasificar_core(efectivo, usuario=usuario, conversation_id=conversation_id, log=log)

    if continuacion:
        res["texto_original"] = texto        # se muestra lo que el usuario escribió, no lo reescrito
        res["continuacion"] = True

    # Actualiza la memoria tras resolver una entidad de jerarquía → permite navegar en cadena
    # (GOR → «POE» → «sus campos» …).
    if res["grupo"] == "jerarquizar" and log and conversation_id:
        try:
            ctx = respuesta_jerarquizar.contexto(efectivo)
            if ctx:
                _CTX[conversation_id] = ctx
        except Exception:
            pass
    # 1e (HE2): cuantificar también deja memoria — habilita el drill N1 -> N2 ("¿acumulado del año?").
    # 🔑 HE5: SIN `ofrece_produccion` — esa clave dispara la rama de jerarquizar en _continuacion y
    # repetiría N1 en vez de subir a N2 (ver el check nuevo en _continuacion, ANTES de ese check).
    elif res["grupo"] == "cuantificar" and log and conversation_id:
        panel = res.get("panel") or {}
        datos = panel.get("datos") or {}
        if panel.get("tipo") == "cuant_rank":
            # N5 ranking: memoria para el drill "para crudo?" / "cambiando el orden". NO lleva
            # "entidad" (es global) → el drill de ranking en _continuacion corta antes de los N1/N2.
            _CTX[conversation_id] = {"grupo": "cuantificar", "subgrupo": "ranking",
                                     "nivel_ranking": datos.get("nivel_ranking", "campo"),
                                     "metrica": datos.get("metrica", "real"),
                                     "direccion": datos.get("direccion", "top"),
                                     "producto": datos.get("producto", "crudo")}
        elif res.get("entidad_cruda"):
            # AF9: guardar el producto respondido (del panel) para que el drill N1->N2 lo preserve.
            # QV2-MES-CTX: + el mes de ESTA respuesta (si lo fija sin ambigüedad), para que un
            # "la producción del mes" posterior sin mes propio herede este y no el de HOY.
            _CTX[conversation_id] = {"grupo": "cuantificar", "entidad": res["entidad_cruda"],
                                     "producto": datos.get("producto", "crudo"),
                                     "periodo_ctx": _periodo_ctx_de(datos)}
    # ANALIZAR también deja memoria (2026-08-04): sus cierres OFRECEN un siguiente paso, así que un
    # "sí" del usuario necesita saber QUÉ se ofreció. Se guarda la sub-intención respondida y, si el
    # usuario acotó el producto, ese producto (para preservarlo en el drill, criterio AF9).
    # 🔑 La entidad puede ser None (análisis GLOBAL ECP): el drill lo contempla — NO se exige
    # entidad_cruda como en cuantificar, o el caso global (el más común) quedaría sin memoria.
    elif res["grupo"] == "analizar" and log and conversation_id:
        try:
            ent_a = res.get("entidad_cruda")
            _CTX[conversation_id] = {
                "grupo": "analizar",
                "entidad": ent_a,
                "sub": _subrouter_analizar.sub_intencion(efectivo),
                "producto": respuesta_analizar._producto_explicito(efectivo, ent_a),
                # Código de la VP que el declinar de `referencia` OFRECIÓ (None en el resto de
                # sub-intenciones): sin esto, "la vicepresidencia" reescribía con el nombre del
                # CAMPO y el declinar se repetía en bucle.
                "vp": res.get("vp_ofrecida"),
            }
        except Exception:
            pass   # la memoria nunca tumba la respuesta (regla madre)

    return res
