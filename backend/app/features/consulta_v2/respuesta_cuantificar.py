"""respuesta_cuantificar.py — respuesta del grupo CUANTIFICAR (Motor Q v2, Fase 1).

Sub-fase 1c (plan_cuantificar_fase1c): la PROSA HONESTA. La cifra (1b) sale con envoltorio cordial —
intro cálido (LLM, respuesta_base) + cuerpo VERBATIM (Python, validador) + cierre (Python). El
validador garantiza que el LLM no filtró números en el intro; si falla/está off → solo cuerpo+cierre.

Sub-fase 1d (plan_cuantificar_fase1_cierre): `responder()` devuelve SIEMPRE un dict {mensaje, panel}.
`panel` es el doble entregable — el visor derecho pinta la MISMA cifra de la burbuja (HD4, aditivo:
jerarquizar/OUT siguen con panel=None). `panel=None` cuando no aplica (sin entidad/ambiguo/rechazo).

Sub-fase 1e: `_ejecutor.ejecutar()` despacha N1/N2 según `slots["nivel_temporal"]` (detectado en
`slots.py` por palabra clave, HE7). El guardado de memoria (_CTX) vive en `maquina_q` — es quien
tiene `conversation_id`, no este módulo (E.5 del plan).

`catalogo.get()` al importar → arranque ruidoso si el YAML está mal.
"""
from app.core.config import get_settings
from app.features.consulta_v2 import respuesta_base
from app.features.consulta_v2.cuantificar import catalogo as _catalogo
from app.features.consulta_v2.cuantificar import resolver as _resolver
from app.features.consulta_v2.cuantificar import slots as _slots
# [2026-08-26] Import a nivel de módulo: `menciona_dia` ya no se usa solo para el techo —
# decide también si una pregunta SIN entidad puede resolverse como global (el grano día no).
from app.features.consulta_v2.cuantificar.slots import menciona_dia as _menciona_dia
from app.features.consulta_v2.cuantificar import ejecutor as _ejecutor
from app.features.consulta_v2.cuantificar import validador as _validador
from app.features.consulta_v2.cuantificar import ranking as _ranking
from app.features.consulta_v2 import no_soportado as _no_soportado

_catalogo.get()   # fuerza carga+validación del catálogo al importar (arranque del backend)
_s = get_settings()

# El LLM escribe SOLO el intro (calidez). Prohibido dar cifras — el cuerpo (aparte) las lleva; si el
# LLM las repite, el validador descarta el intro. Pide {"intro":"..."} con format:json (obligatorio
# en gemma@139, que en texto plano devuelve vacío).
PROMPT_CUANT = """Eres el asistente de producción de hidrocarburos de Ecopetrol: cordial, cercano y natural.
Voy a mostrar una CIFRA de producción de {entidad} — se muestra aparte, NO la repitas, NO inventes números.
Escribe UNA sola frase de presentación, cálida y BREVE, en español, del tipo "Claro, aquí tienes la cifra…".
Usa a veces el nombre del usuario ({usuario}). Varía el fraseo.
NO des ninguna cifra, NO menciones barriles ni porcentajes ni presupuesto, NO prometas nada. Solo saluda y anuncia que aquí está el dato.
Responde SOLO con JSON válido: {{"intro": "..."}}"""

_CIERRE = "¿Quieres el acumulado del año?"   # HE3: ofrece N2 (lo que 1e construye), no N3/N4 (Fase 2)
# [2026-08-25] QV2-PANEL-DIA. `periodo` en el formato que entiende analisis._parse_periodo
# (nombre de mes + año); `_PROD_DIM` traduce al nombre de dim_tipo_producto que filtra los focos.
_MESES_PANEL = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                "septiembre", "octubre", "noviembre", "diciembre"]
_PROD_DIM = {"crudo": "CRUDO", "gas": "GAS", "blancos": "BLANCOS"}
# [2026-08-26 · QV2-SERIE-DIA] N1DSER usa el MISMO panel que el grano día: la curva del mes ya la
# dibujaba entera y solo marcaba un punto encima. Aquí no hay punto que marcar — es la curva sola.
_PANEL_TIPO = {"N3": "cuant_serie", "N4": "cuant_var",
              "N1D": "cuant_dia_panel", "N1DSEL": "cuant_dia_panel",
              "N1DSER": "cuant_dia_panel"}   # N1/N2 -> "cuant_kpi" (Fase 3)
_CIERRE_RANK = "Si quieres, te lo doy por otro producto o cambiando el orden."
# [2026-08-25] Grano día: NO es pregunta sí/no (regla H1) — un "sí" caería en el drill _AFIRM de
# maquina_q._continuacion y devolvería un acumulado en vez de lo ofrecido aquí.
_CIERRE_DIA = "Si quieres, te doy el total del mes o el de otro día."


def _resolver_con_contexto(nombre, texto):
    """resolver_unico(nombre, contexto=texto), degradando si el resolver fue sustituido.

    [2026-09-03] Varios tests monkeypatchean `resolver_unico` con lambdas de UN argumento
    para inyectar la entidad resuelta. Llamarla siempre con dos las rompería, y esos tests
    fijan el contrato de este módulo — el que se adapta es el código, no ellos. Con el
    resolver real el contexto llega y el nivel explícito funciona; con un doble de test, se
    comporta como antes.
    """
    try:
        return _resolver.resolver_unico(nombre, contexto=texto)
    except TypeError:
        return _resolver.resolver_unico(nombre)

# [2026-08-04] Intro PROPIO del ranking (N5). Reusar PROMPT_CUANT enmarcaba mal: dice "una CIFRA de
# producción de {entidad}", así que con entidad="un ranking de campos" el LLM colapsaba a lo singular
# ("aquí tienes la cifra del campo") ante una LISTA de 5. Este prompt le dice explícitamente que es un
# RANKING de VARIOS {entidad} y le pide hablar en PLURAL. Mismo contrato mecánico (sin dígitos/unidades,
# format:json). Verificado en vivo 2026-08-04: 4 de 5 intros decían "del campo"/"esa cifra".
PROMPT_RANK = """Eres el asistente de producción de hidrocarburos de Ecopetrol: cordial, cercano y natural.
Voy a mostrar un RANKING: una LISTA ordenada de VARIOS {entidad} — se muestra aparte, NO lo repitas, NO inventes nombres ni números.
Escribe UNA sola frase de presentación, cálida y BREVE, en español, del tipo "Claro, aquí tienes el ranking…" o "Perfecto, estos son los que buscas…".
Habla en PLURAL (son varios, no uno solo). Usa a veces el nombre del usuario ({usuario}). Varía el fraseo.
NO des ninguna cifra, NO menciones barriles ni porcentajes ni presupuesto, NO prometas nada. Solo saluda y anuncia que aquí está la lista.
Responde SOLO con JSON válido: {{"intro": "..."}}"""
# No termina en pregunta sí/no: un "sí" caería en el drill _AFIRM de maquina_q._continuacion y
# devolvería un acumulado. Misma regla H1 que no_soportado.mensaje.


def _intro(res: dict, usuario) -> str:
    """Intro validado. '' si el flag está off, el LLM falla/timeout o el intro no pasa la validación.
    H4: corta en el 1er retorno vacío (timeout/off → reintentar sería otro timeout de 30s = 60s de
    espera en gemma frío). Solo reintenta 1 vez si el LLM SÍ devolvió texto pero traía un número."""
    if not _s.consulta_cuant_llm:
        return ""
    prompt = PROMPT_CUANT.format(entidad=res["entidad_cualificada"], usuario=usuario or "el usuario")
    for _ in range(2):
        cand = respuesta_base.intro_llm(prompt, True)
        if not cand:                        # timeout/off/fallo → no tiene sentido reintentar
            return ""
        if _validador.intro_valido(cand):
            return cand
    return ""                               # devolvió texto 2 veces pero con número → sin intro


def _panel_datos(res: dict) -> dict:
    """Datos del panel derecho, por nivel (HE6: cada nivel trae campos propios, sin fabricar
    campos sintéticos — N1/N2 KPI · N3 serie · N4 variación, Fase 3)."""
    nivel = res.get("nivel")
    d = {"nivel": nivel, "entidad_cualificada": res["entidad_cualificada"],
         "producto": res["producto"], "unidad": res["unidad"], "avisos": res.get("avisos", [])}
    # [2026-08-26 · QV2-SERIE-DIA] La curva de un mes SIN día marcado. Mismo contexto que el grano
    # día (entidad + periodo + producto) porque el panel es el mismo; lo único que no se emite es
    # `dia_marcado` — no hay un día que resaltar, la respuesta ES la curva completa.
    if nivel == "N1DSER":
        _s = res["mes_label"].split()          # "junio 2026"
        d.update({
            "valor": res["resultado"]["valor"], "promedio_dia": res.get("promedio_dia"),
            "mes_label": res["mes_label"], "dias_con_dato": res["dias_con_dato"],
            "rango": res["rango"],
            "entidad": res["entidad"]["nombre"],
            "nivel": res["entidad"]["nivel"],
            "segmento": "ecp",
            "periodo": f"{_s[0]} {_s[1]}" if len(_s) > 1 else res["mes_label"],
            "productos": [_PROD_DIM.get(res["producto"], "CRUDO")],
            "dia_marcado": None,
        })
    elif nivel in ("N1D", "N1DSEL"):
        d.update({"fecha": res["fecha"], "fecha_label": res["fecha_label"],
                  "valor": res["resultado"]["valor"]})
        # [2026-08-25] QV2-PANEL-DIA: contexto para el panel «Comportamiento {Producto}».
        # 🔑 El periodo sale de la FECHA DE LA PREGUNTA, no del último mes con datos: si preguntan
        # por marzo, gauge y curva muestran marzo (decisión del usuario, 2026-08-25).
        _f = res["fecha"]                      # "YYYY-MM-DD"
        _anio, _mes = int(_f[0:4]), int(_f[5:7])
        d.update({
            "entidad": res["entidad"]["nombre"],
            "nivel": res["entidad"]["nivel"],
            "segmento": "ecp",
            "periodo": f"{_MESES_PANEL[_mes]} {_anio}",
            "productos": [_PROD_DIM.get(res["producto"], "CRUDO")],
            "dia_marcado": _f,
        })
        if nivel == "N1DSEL":
            d.update({"orden": res["orden"], "mes_label": res["mes_label"],
                      "dias_con_dato": res["dias_con_dato"], "rango": res["rango"]})
    # [2026-08-25] QV2-PANEL-MES: N3 y N4 pintan GRÁFICO (línea mensual / waterfall) en vez de
    # filas de texto. `mes_actual` marca dónde corta el tramo sólido y empieza el punteado de
    # proyección; N4 lleva además `serie` (niveles) porque el waterfall necesita el nivel de
    # partida y el de cierre, que desde los deltas solos no se reconstruyen.
    # NO se emite `productos`: el filete del bloque lo pone el dispatcher leyendo [data-prod] del
    # HTML (multitab_shell.js:3375) y `producto` ya viaja arriba — duplicarlo sería peso muerto.
    elif nivel == "N3":
        d.update({"serie": res["serie"], "promedio": res.get("promedio"),
                  "anio": res["anio"], "proyeccion_mes": res.get("proyeccion_mes"),
                  "mes_actual": res.get("mes_actual")})
    elif nivel == "N4":
        d.update({"serie": res["serie"], "deltas": res["deltas"], "ultimo": res["ultimo"],
                  "anio": res["anio"], "proyeccion_mes": res.get("proyeccion_mes"),
                  "mes_actual": res.get("mes_actual")})
    else:                                   # N1/N2 (KPI)
        d.update({"real": res["resultado"]["valor"], "ppto": res["referencia_valor"],
                  "cumplimiento_pct": res["cumplimiento_pct"], "estado": res["estado"]})
        if nivel == "N2":
            d["periodo_label"] = res["periodo_label"]
            d["meses_cerrados"] = res["meses_cerrados"]
        else:                               # N1: referencia seleccionable (Fase 4)
            d["mes"] = res["mes"]
            d["referencia"] = res.get("referencia", "PPTO")
            d["referencia_label"] = res.get("referencia_label", "presupuesto")
    return d


# Bug #5: formas de periodo que el usuario pide pero Cuantificar aún NO calcula → rechazo honesto en
# vez de degradar en silencio al mes completo (verificado 2026-08-03: rango de días/trimestre/semana
# dan N1+mes/None → responderían el mes entero). Se REUSA no_soportado.detectar (el mismo detector
# determinista de la ruta OUT, commit 3bbae0f). 🔑 'anio' NO está en el set: N2 (acumulado) SÍ
# responde el año — "en el año 2026" da N2 — y rechazarlo regresaría el acumulado.
#
# [2026-08-25] DOS sets, no uno (plan QV2-GRANO-DIA). El fork de RANKING (N5) y la ruta de ENTIDAD
# ya no rechazan lo mismo:
#   · La ruta de ENTIDAD sí construye el grano día (N1D/N1DSEL) → 'dia'/'selector_dia' salen del set.
#   · El RANKING N5 es MENSUAL por construcción (ranking.py::_fin_mes sobre fact_produccion_mes_ecp):
#     si le quitáramos 'dia', "top 5 campos el 15 de mayo" devolvería el ranking del MES ENTERO en
#     silencio — exactamente la degradación del bug #5 que este check existe para impedir.
_FORMAS_RECHAZO = ("rango_dias", "trimestre", "semana")                      # ruta ENTIDAD
_FORMAS_RECHAZO_RANKING = ("rango_dias", "trimestre", "semana", "dia", "selector_dia")


def _forma_no_soportada(texto: str):
    """Forma NO soportada por la ruta de ENTIDAD, o None. (Nombre y firma estables: los usa
    tests/test_cuantificar_rango.py)."""
    f = _no_soportado.detectar(texto)
    return f if f in _FORMAS_RECHAZO else None


def _forma_no_soportada_ranking(texto: str):
    """Idem para el fork N5, que NO tiene grano día.

    [2026-08-26 · QV2-DIA-SEL] El grano día se consulta al DETECTOR REAL (`slots.detectar_dia`),
    no al regex de no_soportado.py:92-93, que era una COPIA del mismo criterio y llevaba tiempo
    desincronizada. 🔑 Aquí no es cosmético: el fork de ranking se evalúa ANTES del resolver y de
    slots (:171), así que si la pregunta nombra un campo y un superlativo el RANKING GANA
    SIEMPRE, y esta guarda es lo único que puede devolverla al grano día. Medido antes del
    cambio: «cuáles campos tuvieron los PEORES DÍAS» y «cuál campo tuvo los DÍAS DE MAYOR
    producción» daban un ranking MENSUAL en silencio — la degradación del bug #5 otra vez.
    Con el detector real hay UN solo criterio y esa clase de desfase deja de ser posible.
    El techo es un CENTINELA: solo se pregunta «¿sabes resolver esta forma?»; la fecha se descarta.
    """
    r = _slots.detectar_dia(texto, _slots.TECHO_CENTINELA)
    if r is not None:
        # [2026-08-26] Dos rechazos distintos, porque son dos preguntas distintas:
        #   · selector  → «qué campos tuvieron los peores DÍAS»: ordenar entidades por su
        #     mejor/peor día. Código propio `ranking_dia`; el texto de `selector_dia` está
        #     escrito para una entidad FIJA y aquí sonaba a otra pregunta.
        #   · fecha/rel → «top 5 campos el 15 de mayo»: el ranking de UN día concreto, que es
        #     lo que el código `dia` ya explicaba bien.
        return "ranking_dia" if r.get("clase") == "selector" else "dia"
    f = _no_soportado.detectar(texto)
    return f if f in _FORMAS_RECHAZO_RANKING else None


def responder(texto: str, entidad: str | None = None, usuario=None, conversation_id=None):
    """1c/1d: resuelve → cifra (ejecutor) → intro cálido + cuerpo VERBATIM + cierre (mensaje) + panel
    KPI (o None). Devuelve SIEMPRE {mensaje, panel} — nunca None."""
    # ── N5 RANKING (eje ortogonal) ────────────────────────────────────────────────────────────
    # Va ANTES del resolver: el ranking global NO tiene entidad de entrada (la entidad es la
    # RESPUESTA) y moriría en la guarda "no identifiqué una entidad".
    rk = _ranking.detectar(texto)
    if rk is not None:
        # (1) Formas de periodo no soportadas ANTES de calcular: si este check quedara después del
        #     fork, "top campos del primer trimestre" se degradaría al mes en silencio (bug #5,
        #     cerrado el 2026-08-03 — no puede reabrirse por esta ruta).
        forma = _forma_no_soportada_ranking(texto)
        if forma:
            return {"mensaje": _no_soportado.mensaje(forma, "ese ranking"), "panel": None}
        # (2) Nivel no rankeable en v1 (gerencia/vicepresidencia/pozo) → declina honesto.
        if rk.get("diferido"):
            return {"mensaje": rk["diferido"], "panel": None}
        # (3) v1 = SOLO global. Si el texto nombra una entidad-contenedor, se declina el scoped:
        #     D-D5 colapsa nombres duales a Campo (Castilla → Campo, no Activo) y "los campos de un
        #     campo" no existe. Verificado 2026-08-04: detectar_entidad da None en las preguntas
        #     globales y CASTILLA en las scoped → este gate no produce falsos positivos.
        _hit = _resolver.buscar_en_texto(texto)
        ent_det = entidad or (_hit[0] if _hit else None)
        if ent_det and _resolver.resolver_unico(ent_det) is not None:
            return {"mensaje": (
                f"El ranking DENTRO de «{ent_det}» llega en una próxima fase. Por ahora puedo "
                f"rankear sobre toda la operación —por ejemplo, «los 5 campos que más "
                f"{rk['producto']} producen»."), "panel": None}
        # (4) Calcular → cuerpo VERBATIM + intro cordial + cierre.
        res = _ranking.calcular(rk)
        if not res.get("aplica"):
            return {"mensaje": res.get("texto", "No pude construir ese ranking."), "panel": None}
        cuerpo = _ranking.formatear_cuerpo(res)
        mensaje = respuesta_base.envolver(_intro_ranking(res, usuario), cuerpo, _CIERRE_RANK)
        return {"mensaje": mensaje, "panel": {"tipo": "cuant_rank", "datos": _panel_rank(res)}}

    # La entidad ya la detectó maquina_q (detectar_entidad); el resolver aplica D-D5 sobre ella.
    # Fallback: si no vino, resolver_unico escanea el texto por n-gramas.
    # [2026-09-03] `contexto`: cuando `entidad` viene, es solo el NOMBRE ya extraído
    # («CASTILLA») y el nivel que el usuario escribió («el ACTIVO Castilla») se perdería. El
    # resolver lo necesita para el desempate de nivel explícito — ver resolver._nivel_explicito.
    # 🔑 Vía helper con guarda: varios tests monkeypatchean `resolver_unico` con lambdas de UN
    # argumento; llamarla siempre con dos las rompe. Ver _resolver_con_contexto.
    resuelta = _resolver_con_contexto(entidad or texto, texto)
    # [2026-08-26 · QV2-GLOBAL] Sin entidad NOMBRADA → toda la producción de Ecopetrol, en vez de
    # declinar. «cómo ha sido la producción de crudo este mes» es una pregunta legítima y el dato
    # existe: `desempeno(entidad=None)` devuelve el global (verificado). Hasta ahora el catálogo de
    # cuantificar era cerrado (campo/activo/gerencia/operador) y no tenía forma de expresar «todo».
    # Dos límites deliberados:
    #  🔑 Si el usuario SÍ nombró algo y no está en el catálogo, se sigue declinando con el eco: un
    #     «Castiya» mal escrito no puede convertirse en «toda Ecopetrol» sin avisar.
    #  🔑 El grano DÍA sigue exigiendo entidad. Medido: produccion_dia(None) da `hay_dato: False` y
    #     curva_dia_mes(None) devuelve 0 puntos — el global no está soportado ahí, y pedir el campo
    #     es más honesto que responder «no tengo curva» por un motivo que no es el real.
    if resuelta is None and not entidad and not _menciona_dia(texto):
        resuelta = {"valor": None, "nivel": None, "rama": "A", "zoom": [], "global": True}
    if resuelta is None:
        eco = f" No reconocí «{entidad}» en el catálogo." if entidad else ""
        return {"mensaje": ("No identifiqué una entidad en tu pregunta para cuantificar." + eco
                            + " ¿Puedes nombrar un campo, activo o gerencia?"), "panel": None}
    if resuelta.get("ambiguo"):
        nombres = ", ".join(sorted({r["valor"] for r in resuelta["ambiguo"]}))
        return {"mensaje": (f"«{entidad or texto}» coincide con más de una entidad ({nombres}). "
                            "La desambiguación llega en una próxima fase; por ahora prueba con un nombre único."),
                "panel": None}

    # Bug #5: no degradar en silencio un rango de días/trimestre/semana al mes completo. La entidad ya
    # está resuelta → se puede nombrar en el rechazo honesto (molde de OUT, no_soportado.mensaje).
    # Solo rama A (ECP): la rama B (filial) ya la corta ejecutar (_rechazo_comun) con su propio mensaje.
    if resuelta.get("rama") != "B":
        _forma = _forma_no_soportada(texto)
        if _forma:
            return {"mensaje": _no_soportado.mensaje(_forma, resuelta["valor"]), "panel": None}

    # AF10: la entidad YA está resuelta (D-D5) → se le pasa a slots para que su nombre no contamine
    # el grounding de producto (p.ej. un campo 'CAÑO BLANCO' no debe leerse como producto blancos).
    # [2026-08-25] GRANO DÍA: el techo (último día con reporte diario) solo se consulta si la
    # pregunta MENCIONA un día (menciona_dia, pre-check puro) — evita un round-trip a BD en toda
    # pregunta mensual, que es la inmensa mayoría del tráfico.
    from app.features.analisis.api import techo_dia as _techo_ep
    _techo = (_techo_ep(resuelta["valor"], nivel=resuelta.get("nivel"))
              if _menciona_dia(texto) else None)
    res = _ejecutor.ejecutar(resuelta,
                             _slots.extraer_slots(texto, entidad_valor=resuelta["valor"],
                                                  techo=_techo))
    if not res.get("aplica"):
        return {"mensaje": res.get("texto", "No pude cuantificar esa pregunta."), "panel": None}

    cuerpo = _validador.formatear_cuerpo(res)
    intro = _intro(res, usuario)
    if res.get("nivel") == "N1DSER":
        # Ya se dio el mes entero: lo que queda por ofrecer es el detalle DENTRO de la curva.
        cierre = "Si quieres, te digo el mejor o el peor día de ese mes."
    elif res.get("nivel") in ("N1D", "N1DSEL"):
        cierre = _CIERRE_DIA
    elif res.get("nivel") == "N2":
        cierre = "¿Quieres el detalle de un mes puntual?"
    else:
        cierre = _CIERRE   # HE3
    mensaje = respuesta_base.envolver(intro, cuerpo, cierre)
    tipo = _PANEL_TIPO.get(res.get("nivel"), "cuant_kpi")
    return {"mensaje": mensaje, "panel": {"tipo": tipo, "datos": _panel_datos(res)}}


def _intro_ranking(res: dict, usuario) -> str:
    """Intro cálido validado. Mismo contrato mecánico que _intro (sin dígitos ni unidades)."""
    if not _s.consulta_cuant_llm:
        return ""
    plural = {"campo": "campos", "activo": "activos"}[res["nivel_ranking"]]
    prompt = PROMPT_RANK.format(entidad=f"{plural} por producción de {res['producto']}",
                                usuario=usuario or "el usuario")
    for _ in range(2):
        cand = respuesta_base.intro_llm(prompt, True)
        if not cand:
            return ""
        if _validador.intro_valido(cand):
            return cand
    return ""


def _panel_rank(res: dict) -> dict:
    """Datos del panel derecho del ranking (doble entregable HD4)."""
    return {k: res[k] for k in ("nivel_ranking", "metrica", "direccion", "producto", "unidad",
                                "periodo_label", "es_proyeccion", "items", "total_universo",
                                "sin_registro", "concentracion_pct")}
