"""respuesta_analizar.py — respuesta del grupo ANALIZAR (Motor Q v2, Grupo 3, Fase 1).

Envuelve `analisis.ejecutivo` (motor ya existente y afinado; corre en 139). Regla madre: Python
calcula y decide la tesis (REGLA CERO: NO inventar rezago); el LLM solo redacta el intro cordial.

Coherencia chat↔tablero: se llama `ejecutivo(...)` con los args EXPLÍCITOS (patrón probado por
Cuantificar y v1; NO se refactoriza `_ejecutivo_core` — AF-A2). 🔑 `pulir=False` (RA-1): salta el
pulido LLM de `secciones` (que Fase 1 descarta) → sin el hang de 180s de Gemma en 139.

GLOBAL vs FALLO (RA-2): sin entidad nombrada ⇒ análisis GLOBAL ECP; entidad nombrada que el catálogo
no resuelve (p.ej. una gerencia solo-robustez) ⇒ fallo honesto, NO global silencioso.

Fase 1: sub-intenciones `causal` y `proyeccion`. Fase 2: + `diferidas` (histórico por causa, lectura
DIRECTA de SQLite — ver `analizar/diferidas.py`). Fase 3: + `economia` (EBITDA/NOPAT vía robustez,
envuelve el EBITDA Inspector — ver `analizar/economia.py`; traduce entidad INGESTA→rob_field, declara
cobertura parcial en cabecera).
"""
import re

from app.core.config import get_settings
from app.features.analisis.api import ejecutivo as _ejecutivo_ep
from app.features.consulta_v2 import respuesta_base
from app.features.consulta_v2.normaliza import norm
from app.features.consulta_v2.cuantificar import resolver as _resolver
# [2026-08-26] El detector de periodo vive en cuantificar/slots y es PURO (sin BD). Se REUSA en
# vez de copiarlo: el mismo bug de substring ("mayo" dentro de "mayor") existía en dos gemelos a
# la vez, y ese es el precio de duplicar. Un solo detector, dos consumidores.
from app.features.consulta_v2.cuantificar import slots as _slots
from app.features.consulta_v2.analizar import subrouter as _subrouter
from app.features.consulta_v2.analizar import plantilla as _plantilla
from app.features.consulta_v2.analizar import diferidas as _diferidas
from app.features.consulta_v2.analizar import economia as _economia
from app.features.consulta_v2.analizar import p50_referencia as _p50
from app.features.analisis.api import president as _president_ep

_s = get_settings()

# El LLM escribe SOLO el intro (calidez). Prohibido cifras — los bloques (aparte) las llevan.
PROMPT_ANALIZA = """Eres el asistente de producción de hidrocarburos de Ecopetrol: cordial y natural.
Voy a mostrar un ANÁLISIS de {alcance} — se muestra aparte, NO lo repitas, NO inventes números ni causas.
Escribe UNA sola frase de presentación, cálida y BREVE, en español ("Con gusto, aquí tienes el análisis…").
Usa a veces el nombre del usuario ({usuario}). Varía el fraseo.
NO des cifras, NO menciones porcentajes ni campos, NO adelantes conclusiones. Solo saluda y anuncia el análisis.
Responde SOLO con JSON válido: {{"intro": "..."}}"""

_CIERRE = "¿Quieres el detalle por campo, o la proyección de cierre?"
_CIERRE_PROY = "¿Quieres ver qué campos explican el faltante?"


def _resolver_con_contexto(nombre, texto):
    """resolver_unico(nombre, contexto=texto), degradando si el resolver fue sustituido.

    [2026-09-03] 13 tests de test_p50_referencia.py monkeypatchean `resolver_unico` con
    lambdas de UN argumento para inyectar la entidad resuelta. Llamarla siempre con dos las
    rompería, y esos tests fijan el contrato de Analizar — el que se adapta es este módulo,
    no ellos. Con el resolver real, el contexto llega y el nivel explícito funciona; con un
    doble de test, se comporta como antes.
    """
    try:
        return _resolver.resolver_unico(nombre, contexto=texto)
    except TypeError:
        return _resolver.resolver_unico(nombre)

# [2026-08-26] Preguntas POR CAMPOS: el panel se abre en el desglose por campo, no en el
# acordeón entero. 🔑 Las dos frases de arriba OFRECEN exactamente esto («el detalle por campo»,
# «qué campos explican el faltante»), y hasta ahora aceptarlas devolvía el panorama completo —
# el sistema proponía una pregunta que no sabía responder de forma enfocada.
# Deliberadamente amplio en el VERBO (explican/pesan/aportan/faltan/están) y estricto en el
# SUJETO (campos/activos): lo que decide la vista es que se pregunte por ENTIDADES, no la causa.
_RX_POR_CAMPOS = re.compile(
    r"\b(?:QUE|CUALES?|CUAL)\s+(?:CAMPOS?|ACTIVOS?)\b"
    r"|\b(?:DETALLE|DESGLOSE|APERTURA)\s+POR\s+(?:CAMPO|ACTIVO)S?\b"
    r"|\b(?:CAMPOS?|ACTIVOS?)\s+(?:QUE|CON)\s+.{0,30}?\b(?:FALTANTE|GAP|BAJO\s+META|CORTOS?)\b"
)
# [2026-08-13] El cierre de 'referencia' es DINÁMICO (M9/M6 del plan p50_referencia_analizar):
# varía según si hay o no una vicepresidencia ofrecible -> lo arma p50_referencia.cierre_declinar,
# NO una constante fija como _CIERRE/_CIERRE_PROY.

# Producto EXPLÍCITO en el texto (crudo/gas/blancos), o None si no se nombró. Token exacto excluyendo
# el nombre de la entidad (AF10: 'Caño Blanco' no es producto blancos). Si el usuario pide "el gap de
# CRUDO", el análisis causal se acota a crudo (antes analizaba los 3 productos rezagados).
_PUNCT = "¿?¡!.,;:()[]{}\"'`"
_PROD_EXPL = (("CRUDO", "CRUDO"), ("GAS", "GAS"), ("BLANCOS", "BLANCOS"), ("BLANCO", "BLANCOS"))


def _producto_explicito(texto: str, entidad_valor: str | None) -> str | None:
    toks = {w.strip(_PUNCT) for w in norm(texto or "").split()}
    if entidad_valor:
        toks -= {w.strip(_PUNCT) for w in norm(entidad_valor).split()}
    for tok, p in _PROD_EXPL:
        if tok in toks:
            return p
    return None


def _aviso_periodo(per: str | None, d: dict) -> str:
    """'' salvo que se pidiera un mes concreto y el motor haya servido OTRO. [2026-08-26]

    `_parse_periodo` (analisis/api.py:372) solo entiende mes-por-nombre y 'mes pasado'. Un
    trimestre, una semana o un año caen a None y el ejecutivo sirve el mes VIGENTE — que es
    exactamente el fallo que se acaba de corregir, entrando por una puerta más estrecha.

    Se compara por NÚMERO de mes, no por cadena: el usuario puede escribir «setiembre» y el meta
    responder «Septiembre». Si el formato del meta no se reconoce NO se avisa nada: inventar una
    advertencia es tan malo como callar una real.
    """
    if not per or per.startswith("mes "):          # 'mes pasado' lo resuelve el backend
        return ""
    pedido = _slots._MESES_NUM.get(per.split()[0].lower())
    servido = ((d.get("meta") or {}).get("periodo") or "").strip()
    servido_num = _slots._MESES_NUM.get(servido.split()[0].lower()) if servido else None
    if not pedido or not servido_num or pedido == servido_num:
        return ""
    return (f"⚠️ Pediste {per} y este análisis es de {servido} — es el periodo que puedo "
            f"servir. Las cifras de abajo son de {servido}, no de {per}.")


def _productos_explicitos(texto: str, entidad_valor: str | None) -> list[str]:
    """TODOS los productos nombrados explícitamente (D1, 2026-08-13: el panel derecho es dinámico
    por producto — "de crudo" → 1 foco, "crudo y gas" → 2, sin nombrar ninguno → los 3).
    🔑 A diferencia de `_producto_explicito` (singular, retorna al PRIMER match — la usan
    `causal()`/texto y el drill de `_CTX` en maquina_q.py, y NO se tocan: con "crudo y gas" esa
    función solo devolvía "CRUDO", verificado en vivo antes de este cambio), esta recorre TODOS
    los tokens. [] = ninguno nombrado (el panel muestra los 3, sin filtrar)."""
    toks = {w.strip(_PUNCT) for w in norm(texto or "").split()}
    if entidad_valor:
        toks -= {w.strip(_PUNCT) for w in norm(entidad_valor).split()}
    vistos = []
    for tok, p in _PROD_EXPL:
        if tok in toks and p not in vistos:
            vistos.append(p)
    return vistos


def _intro(alcance: str, usuario) -> str:
    """Intro validado (sin dígitos). '' si el flag está off o el LLM falla/mete un número."""
    if not _s.consulta_analiza_llm:
        return ""
    prompt = PROMPT_ANALIZA.format(alcance=alcance, usuario=usuario or "el usuario")
    cand = respuesta_base.intro_llm(prompt, True)
    # Red mecánica: el intro es SOLO saludo. Si trae dígitos, se descarta (regla madre).
    return cand if (cand and not any(ch.isdigit() for ch in cand)) else ""


def _responder_core(texto: str, entidad: str | None = None, usuario=None, conversation_id=None,
                     _ejecutivo_fn=None, _diferidas_fn=None, _economia_fn=None, _split_fn=None,
                     _p50_fn=None, _vp_fn=None, _president_fn=None, _serie_fn=None) -> dict:
    """Devuelve SIEMPRE {"mensaje": str, "panel": dict|None} (contrato HD4, patrón jerarquizar/
    cuantificar). `_ejecutivo_fn`/`_diferidas_fn`/`_economia_fn`/`_split_fn`/`_p50_fn`/`_vp_fn`/
    `_president_fn`/`_serie_fn` = inyección para tests (evita BD/LLM). 3 sub-intenciones producen
    panel: causal (tipo "analiza_foco"), referencia SOLO en su rama de vicepresidencia (tipo
    "p50_vp", 2026-08-13) y diferidas CUANDO hay datos (tipo "analiza_dif", 2026-08-26) — el resto
    (proyección/economía/referencia-global/referencia-declinar) va con panel=None, cada una con su
    propia forma de respuesta."""
    fn = _ejecutivo_fn or _ejecutivo_ep
    dif_fn = _diferidas_fn or _diferidas.impacto_historico
    econ_fn = _economia_fn or _economia.impacto_economico
    split_fn = _split_fn or _diferidas.split_planeado
    p50_fn = _p50_fn or _p50.p50_por_vp
    vp_fn = _vp_fn or _p50.vp_de_campo
    president_fn = _president_fn or _president_ep
    serie_fn = _serie_fn or _p50.serie_por_vp

    # 1) Sub-intención (determinista). Fase 3: economia YA no es stub -> se resuelve tras la entidad.
    sub = _subrouter.sub_intencion(texto)

    # 2) Entidad (RA-2, Fase 1). Aplica por igual a causal/proyeccion/diferidas/economia (FB-5/H8:
    #    diferidas y economia necesitan la entidad para filtrar por campo/activo).
    # [2026-09-03] `contexto`: `entidad` es solo el NOMBRE ya extraído por maquina_q, sin el
    # nivel que el usuario escribió. Sin esto, «el activo Castilla» se analiza como el CAMPO
    # homónimo (mismo bug que en cuantificar) — ver resolver._nivel_explicito.
    # 🔑 Se pasa POSICIONAL y con guarda: 13 tests (test_p50_referencia.py) monkeypatchean
    # `resolver_unico` con lambdas de UN argumento; llamarla siempre con dos las rompe. La
    # guarda mantiene el contrato que esos tests fijan y no los obliga a cambiar.
    resuelta = _resolver_con_contexto(entidad or texto, texto)
    if resuelta and resuelta.get("ambiguo"):
        nombres = ", ".join(sorted({r["valor"] for r in resuelta["ambiguo"]}))
        return {"mensaje": (f"«{entidad or texto}» coincide con más de una entidad ({nombres}). "
                "Nómbrala de forma única para analizarla."), "panel": None}
    if resuelta and resuelta.get("rama") == "B":
        return {"mensaje": (f"«{resuelta['valor']}» es una filial; su análisis llega en una próxima fase. "
                "Por ahora analizo la producción ECP."), "panel": None}
    if resuelta is None:
        # RA-2: distinguir "no nombró entidad" (→ GLOBAL) de "nombró algo irresoluble" (→ fallo honesto).
        if entidad:
            return {"mensaje": (f"No pude ubicar «{entidad}» en el catálogo para analizarla. "
                    "¿Puedes nombrar un campo, activo o gerencia del reporte ECP?"), "panel": None}
        ent_valor, nivel, alcance = None, None, "la producción global ECP"   # GLOBAL
    else:
        ent_valor = resuelta["valor"]; nivel = resuelta.get("nivel")
        alcance = f"el {nivel} {ent_valor}".strip()

    # 3) DIFERIDAS (Fase 2): histórico por causa, NO usa `ejecutivo` (fuente propia). FC-3: la regla de
    #    qué nivel soporta el filtro SQL vive en diferidas.nivel_soportado() (no se repite la tupla acá).
    if sub == "diferidas":
        if not _diferidas.nivel_soportado(nivel):
            return {"mensaje": (f"El histórico de diferidas solo está disponible a nivel de campo o activo; "
                    f"«{ent_valor}» es {nivel}. ¿Quieres nombrar un campo o activo puntual?"), "panel": None}
        campos = _diferidas.campos_de_activo(ent_valor) if nivel == "activo" else (
            [ent_valor] if ent_valor else [])
        datos = dif_fn(campos)
        cuerpo = _plantilla.diferidas(datos, ent_valor)
        intro = _intro(alcance, usuario)
        mensaje = respuesta_base.envolver(
            intro, cuerpo, "¿Quieres el análisis de causas del mes en curso, o la proyección de cierre?")
        # [2026-08-26] Panel derecho. El acordeón de foco de `causal` YA trae una pestaña
        # "Diferidas" completa (pérdida por causa NV04 + comportamiento por tipo), pero preguntar
        # DIRECTO por las diferidas de un campo devolvía solo texto: el panel existía y nadie
        # llegaba a él por esta puerta. Se emite el MISMO scope que consume `__cnDiferidasInto`
        # (entidad/nivel/campos), no los datos: el frontend fetchea /api/diferidas/frecuencia con
        # su propia caché (A7, igual que analiza_foco) — y esa ruta trae además la tendencia
        # 2023/24/25, que `impacto_historico` no calcula.
        # Panel SOLO si hay datos (mismo criterio que p50_vp/H3): sin esto, "no tengo la BD" o
        # "0 diferidas" abriría un bloque en la pila para decir lo mismo dos veces.
        panel_dif = None
        if not datos.get("sin_datos"):
            panel_dif = {"tipo": "analiza_dif", "datos": {
                "entidad": ent_valor, "nivel": nivel, "campos": campos,
                # El panel muestra UN producto (elige la columna de volumen perdido: ACEITE vs GAS).
                # Sin producto nombrado, CRUDO — igual que `referencia` (:190).
                "producto": _producto_explicito(texto, ent_valor) or "CRUDO",
            }}
        return {"mensaje": mensaje, "panel": panel_dif}

    # 3b) ECONOMÍA (Fase 3): EBITDA/NOPAT vía robustez, NO usa `ejecutivo` (fuente propia: el waterfall
    #     del EBITDA Inspector). H3: traduce la entidad INGESTA a rob_field; H4: declina terceros /
    #     sin reconciliar; H8: la regla de nivel vive en economia.nivel_soportado().
    if sub == "economia":
        if not _economia.nivel_soportado(nivel):
            return {"mensaje": (f"La rentabilidad (EBITDA/NOPAT) solo está disponible a nivel de campo o activo; "
                    f"«{ent_valor}» es {nivel}. ¿Quieres nombrar un campo o activo puntual?"), "panel": None}
        rob_fields, total = _economia.rob_fields_de(nivel, ent_valor)
        # H4/EC-10: entidad nombrada que no reconcilia a NINGÚN campo robustez (tercero, sin fila, o
        # activo 100% de terceros) -> declinar honesto. NUNCA caer a global en silencio (RA-2).
        if ent_valor and not rob_fields:
            return {"mensaje": (f"«{ent_valor}» no está en el universo de rentabilidad (robustez), que solo cubre "
                    "los campos de crudo operados por Ecopetrol. ¿Quieres su producción o sus diferidas?"), "panel": None}
        datos = econ_fn(rob_fields)
        # EC-7/EC-8: la plantilla necesita el NIVEL (D-A5) y la COBERTURA (incluidos/total) para
        # declararla en cabecera — no como footnote.
        cuerpo = _plantilla.economia(datos, ent_valor, nivel, rob_fields, total)
        intro = _intro(alcance, usuario)
        mensaje = respuesta_base.envolver(
            intro, cuerpo, "¿Quieres el desglose de causas del mes, o la proyección de cierre?")
        return {"mensaje": mensaje, "panel": None}

    # 3c) REFERENCIA (2026-08-13, plan_p50_referencia_analizar_2026-08-13.md): el P50 pedido como
    #     CIFRA, no como tema causal — antes "P50" solo servía para ENRUTAR a `analizar` y la
    #     rama causal (default) respondía contra PPTO, sin avisar el cambio de vara (defecto real,
    #     verificado con "dame el P50 para el campo Rubiales" -> "95.6% del presupuesto"). El P50
    #     NO se define por campo/activo (A1 del plan, en NINGUNA de las 16 hojas del reporte) -> a
    #     esos niveles se DECLINA y se ofrecen las vecinas que EXISTAN (M6): presupuesto al mismo
    #     nivel, o el P50 de la vicepresidencia SI el campo tiene una en robustez.
    if sub == "referencia":
        producto = _producto_explicito(texto, ent_valor) or "CRUDO"
        # `resuelta` lleva la marca `puente` (S32): una "gerencia" que en robustez es una
        # VICEPRESIDENCIA real (GOR, GAA…) — la misma taxonomía de t8, así que SÍ tiene P50.
        es_vp = nivel == "vicepresidencia" or bool((resuelta or {}).get("puente"))
        if es_vp and nivel == "gerencia":
            # El intro cordial dice el `alcance`: sin esto anunciaba "el análisis de la GERENCIA
            # GOR" y el cuerpo respondía "esa VICEPRESIDENCIA" — dos etiquetas contradictorias en
            # el mismo mensaje (visto en el servidor de pruebas, 2026-08-13). Mismo criterio que
            # cuantificar/ejecutor._etiqueta_nivel con `puente` (S32/R2).
            alcance = f"la vicepresidencia {ent_valor}"
        panel_ref = None
        if _p50.nivel_soportado(nivel, resuelta):
            if es_vp:
                info = p50_fn(ent_valor, producto)
                cuerpo = (_p50.formatear_cifra_vp(ent_valor, info, producto) if info else
                          f"No tengo el P50 de «{ent_valor}» para {producto.lower()} — esa "
                          "vicepresidencia no tiene un mes con real y P50 a la vez en la fuente.")
                # Panel derecho (2026-08-13, plan_panel_p50_vp_2026-08-13.md). SOLO cuando el
                # mensaje YA dio una cifra (`info`) — H1: la tarjeta muestra el MISMO producto que
                # el texto, nunca una lista aparte, o texto y panel dirían cosas distintas. H3: sin
                # serie -> panel None, NUNCA {"datos": {}} (un bloque vacío en la pila).
                if info:
                    s = serie_fn(ent_valor, producto)
                    if s and s.get("serie"):
                        panel_ref = {"tipo": "p50_vp", "datos": s}
            else:   # nivel is None -> global ECP (REPORTE_PRESIDENT, escala kbpe)
                info = president_fn(periodo=None)
                if not info.get("encontrada"):
                    cuerpo = "No tengo el compromiso P50 disponible en este momento."
                else:
                    card = next((p for p in info.get("productos", [])
                                if p.get("entidad", "").upper() == producto), None)
                    if card is None:
                        card = next((t for t in info.get("totales", [])
                                    if t.get("entidad") == "Ecopetrol"), None)
                    cuerpo = (_p50.formatear_cifra_global(card, info.get("unidad", "kbpe"),
                                                          producto, info.get("corte"))
                              if card else "No tengo el compromiso P50 disponible en este momento.")
            intro = _intro(alcance, usuario)
            mensaje = respuesta_base.envolver(intro, cuerpo, _CIERRE_PROY)
            # D1: `panel_ref` solo se pobló en la rama `es_vp`; el global ECP sigue en None (su
            # caso nativo es el artifact corporativo, otra fuente/otro plan).
            return {"mensaje": mensaje, "panel": panel_ref}
        # nivel NO soportado (campo/activo/gerencia/operador/fuente) -> DECLINAR. Necesita el % vs
        # PPTO del campo (R8 del plan) -> SÍ llama a `fn`, mismo patrón pulir=False del paso 4 (o
        # se cuelga 180s con Gemma en 139, RA-1).
        ppto_pct = ppto_gap = None
        if ent_valor:
            d_ref = fn(entidad=ent_valor, segmento="ecp", nivel=nivel, periodo=None, pulir=False)
            if d_ref.get("encontrada") and not d_ref.get("sin_datos"):
                titular = next((t for t in d_ref.get("titular", [])
                                if t.get("valor_pct") is not None and t.get("producto") == producto), None)
                if titular:
                    ppto_pct = titular["valor_pct"]
                    g = d_ref.get("gap_por_producto", {}).get(producto, {})
                    ppto_gap = g.get("faltante_bruto")
        vp_info = None
        if ent_valor and nivel in ("campo", "activo"):
            campos_vp = [ent_valor] if nivel == "campo" else _diferidas.campos_de_activo(ent_valor)
            # M6: solo se ofrece si TODOS los campos del alcance comparten UNA vicepresidencia — un
            # activo con campos en 2 VPs distintas no tiene "su" vicepresidencia única que ofrecer.
            vps = {vp_fn(c) for c in campos_vp} - {None}
            if len(vps) == 1:
                vp_info = p50_fn(next(iter(vps)), producto)
        cuerpo = _p50.formatear_declinar(ent_valor or (entidad or texto), nivel, ppto_pct, ppto_gap,
                                         producto, vp_info)
        cierre = _p50.cierre_declinar(vp_info)
        intro = _intro(alcance, usuario)
        mensaje = respuesta_base.envolver(intro, cuerpo, cierre)
        # `vp_ofrecida` viaja para que maquina_q lo guarde en _CTX: si el usuario responde "la
        # vicepresidencia", el drill debe reescribir con ESE código, no con el nombre del campo
        # (o vuelve a resolver como campo y repite el declinar, en bucle — verificado 2026-08-13).
        return {"mensaje": mensaje, "panel": None,
                "vp_ofrecida": (vp_info or {}).get("vice")}

    # 4) Motor: ejecutivo con args explícitos + pulir=False (AF-A2 + RA-1).
    # [2026-08-26] El PERIODO deja de ser None fijo. Hasta hoy Analizar era CIEGO al mes: «analiza
    # el comportamiento del crudo para el mes de MAYO» respondía AGOSTO — el mes vigente — y lo
    # rotulaba como tal sin decir en ningún momento que había ignorado lo que se le pidió. Estaba
    # declarado en el código como fase pendiente (RA-3), pero para quien pregunta eso no es una
    # fase pendiente: es una respuesta equivocada presentada con total seguridad.
    # El endpoint YA aceptaba `periodo` (analisis/api.py:1662 -> _ambito -> _parse_periodo) y el
    # detector YA existía en cuantificar. Solo faltaba conectarlos.
    per = _slots.periodo_texto(texto)
    d = fn(entidad=ent_valor, segmento="ecp", nivel=nivel, periodo=per, pulir=False)
    if not d.get("encontrada"):
        return {"mensaje": f"No encontré datos de producción para «{entidad or texto}» para analizar.",
                "panel": None}
    if d.get("sin_datos"):
        return {"mensaje": f"«{ent_valor or 'ECP'}» no tiene datos suficientes en ese periodo para un análisis.",
                "panel": None}

    # 5) Cuerpo determinista por sub-intención (VERBATIM de la data del ejecutivo).
    panel = None
    if sub == "proyeccion":
        cuerpo = _plantilla.proyeccion(d, ent_valor)
        cierre = _CIERRE_PROY
    else:                                                    # causal (default)
        # Bloque «Por qué»: impacto por causa (CAUSE_NIVEL4, %) + resumen No planeado/Planeado
        # (CAUSE_NIVEL3). Solo en niveles donde el filtro SQL por CAMPO/AREA aplica (campo/activo/
        # global); gerencia/vice/operador/fuente -> ambos None (no se muestra un histórico global
        # engañoso bajo una entidad que no lo es). Mismo scoping de campos para las 2 llamadas —
        # reusa el de la sub-intención `diferidas`. Ambas funciones cachean (A1/A11).
        split = None
        impacto = None
        if _diferidas.nivel_soportado(nivel):
            campos_split = (_diferidas.campos_de_activo(ent_valor) if nivel == "activo"
                            else ([ent_valor] if ent_valor else []))
            split = split_fn(campos_split)
            impacto = dif_fn(campos_split)
        producto = _producto_explicito(texto, ent_valor)
        cuerpo = _plantilla.causal(d, ent_valor, producto, split, impacto)
        cierre = _CIERRE
        # Panel derecho (2026-08-13): el acordeón de foco del tablero, apilado. Solo el SCOPE — el
        # frontend fetchea desempeño/ejecutivo con sus propias cachés (A7: los datos del tablero no
        # viajan por esta ruta). D1: `productos` es la lista de TODOS los nombrados (plural, no
        # `producto` singular de arriba) — [] = ninguno nombrado, el panel muestra los 3.
        panel = {"tipo": "analiza_foco", "datos": {
            # [2026-08-26] El periodo viaja al panel TAMBIÉN. Sin esto el texto diría «Mayo 2026»
            # y el acordeón de al lado pintaría agosto: dos meses distintos en la misma respuesta,
            # peor que el fallo que se está corrigiendo. El frontend ya lo sabe pasar en el QS
            # (__cnAnzQS) y el endpoint ya lo parsea — no hace falta tocar nada más.
            "entidad": ent_valor, "nivel": nivel, "segmento": "ecp", "periodo": per,
            "productos": _productos_explicitos(texto, ent_valor),
            # [2026-08-26] `vista`: si la pregunta es POR CAMPOS («qué campos explican el
            # faltante»), el panel se abre en el desglose por campo en vez del acordeón entero.
            # Antes devolvía el panorama completo —comportamiento diario, ejecución vs PPTO y el
            # desglose— a quien solo había preguntado cuáles campos. La respuesta estaba dentro,
            # pero enterrada en dos bloques que nadie pidió.
            "vista": "campos" if _RX_POR_CAMPOS.search(norm(texto)) else None,
        }}

    # [2026-08-26] Si se pidió un mes que el motor no pudo honrar, se dice ANTES de las cifras —
    # no en un pie de página que nadie lee. La regla del proyecto es no degradar en silencio, y
    # servir otro periodo bajo la pregunta de uno distinto es la degradación más cara que hay.
    av = _aviso_periodo(per, d)
    if av:
        cuerpo = av + "\n\n" + cuerpo

    # 6) Envoltorio cordial (intro LLM opcional + cuerpo VERBATIM + cierre).
    intro = _intro(alcance, usuario)
    mensaje = respuesta_base.envolver(intro, cuerpo, cierre)
    return {"mensaje": mensaje, "panel": panel}


def responder(texto: str, entidad: str | None = None, usuario=None, conversation_id=None,
              _ejecutivo_fn=None, _diferidas_fn=None, _economia_fn=None, _split_fn=None,
              _p50_fn=None, _vp_fn=None, _president_fn=None, _serie_fn=None) -> str:
    """Wrapper compat: devuelve SIEMPRE un str (nunca None) — igual que antes de que `_responder_core`
    ganara panel. Los llamadores/tests existentes que esperan `str` no se tocan."""
    return _responder_core(texto, entidad=entidad, usuario=usuario, conversation_id=conversation_id,
                           _ejecutivo_fn=_ejecutivo_fn, _diferidas_fn=_diferidas_fn,
                           _economia_fn=_economia_fn, _split_fn=_split_fn,
                           _p50_fn=_p50_fn, _vp_fn=_vp_fn, _president_fn=_president_fn,
                           _serie_fn=_serie_fn)["mensaje"]


def responder_con_panel(texto: str, entidad: str | None = None, usuario=None, conversation_id=None,
                        _ejecutivo_fn=None, _diferidas_fn=None, _economia_fn=None, _split_fn=None,
                        _p50_fn=None, _vp_fn=None, _president_fn=None, _serie_fn=None) -> dict:
    """{"mensaje": str, "panel": dict|None} — la usa maquina_q.py (mismo contrato que
    respuesta_cuantificar.responder / respuesta_jerarquizar.responder_cordial)."""
    return _responder_core(texto, entidad=entidad, usuario=usuario, conversation_id=conversation_id,
                           _ejecutivo_fn=_ejecutivo_fn, _diferidas_fn=_diferidas_fn,
                           _economia_fn=_economia_fn, _split_fn=_split_fn,
                           _p50_fn=_p50_fn, _vp_fn=_vp_fn, _president_fn=_president_fn,
                           _serie_fn=_serie_fn)
