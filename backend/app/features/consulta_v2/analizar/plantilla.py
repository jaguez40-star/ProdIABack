"""analizar/plantilla.py — arma la narrativa VERBATIM desde el JSON de `analisis.ejecutivo`.

TODO número sale de la data del motor (reconciliada por Python, coherente con el tablero). REGLA
CERO (AF-A5/A10): si NINGÚN producto va por debajo de su meta, se DECLARA "sin rezago" — NUNCA se
fabrica un faltante. La prosa del LLM (secciones) NO se usa aquí (Fase 1 es determinista).
"""
from app.features.consulta_v2.cuantificar.validador import fmt_valor

from app.core.unidades import UNIDADES_PRODUCTO as _UNIDAD, UNIDAD_DIF as _UNIDAD_DIF   # [BEQ-2026-09-08]
_PROD_L = {"CRUDO": "crudo", "GAS": "gas", "BLANCOS": "blancos"}
_MES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
        "septiembre", "octubre", "noviembre", "diciembre"]


def _fmt(valor, prod) -> str:
    """fmt producto-aware: 'crudo'→bbl es-CO; 'gas'→MSCF (÷1e6). fmt_valor espera el nombre en
    minúscula ('gas'), no el del titular ('GAS')."""
    return fmt_valor(valor, _PROD_L.get(prod, "crudo"))


def _dia_mes(iso) -> str:
    """'2026-05-06' -> '6 de mayo' (RA-6: legible). Devuelve el ISO crudo si no parsea."""
    try:
        _, m, d = str(iso).split("-")
        return f"{int(d)} de {_MES[int(m)]}"
    except Exception:
        return str(iso)


def _rezagados(d) -> list:
    """Productos con meta y por debajo de ella (valor_pct < 100). REGLA CERO se apoya en esto."""
    return [t for t in d.get("titular", []) if t.get("valor_pct") is not None and t["valor_pct"] < 100]


def _delta_texto(d, prod) -> str | None:
    """DELTA vs promedio del año (AF-A4): tarjetas[prod].proyectado_cierre − hist_prom. None si falta."""
    tar = next((x for x in d.get("tarjetas", []) if x.get("producto") == prod), None)
    if not tar or tar.get("hist_prom") in (None, 0) or tar.get("proyectado_cierre") is None:
        return None
    real = tar["proyectado_cierre"]; hist = tar["hist_prom"]
    dif = real - hist
    signo = "por encima de" if dif >= 0 else "por debajo de"
    u = _UNIDAD.get(prod, "bbl")
    return (f"va en {_fmt(real, prod)} {u} vs su promedio {2026} de {_fmt(hist, prod)} {u} "
            f"({'+' if dif >= 0 else '−'}{_fmt(abs(dif), prod)} {u}, {signo} su propia historia)")


def _split_lineas(split, prod):
    """(contexto_line, accion_clause) del split histórico Planeada/No planeada de `prod`, o (None, "").
    Solo CRUDO/GAS tienen columnas de volumen perdido (BLANCOS no) → para BLANCOS devuelve (None, "").
    ROTULA el histórico: la BD de diferidas termina 2025-07 y el análisis es del mes en curso."""
    s = ((split or {}).get("split") or {}).get(prod) if (split and not split.get("sin_datos")) else None
    if not s or not s.get("total_clasificado"):
        return None, ""
    pl = _PROD_L.get(prod, prod.lower())
    u = _UNIDAD_DIF          # [BEQ] diferidas = VOLUMEN perdido (bbl-eq), no caudal
    np_pct = s["pct_no_planeada"]
    p_pct = round(100 - np_pct, 1)
    ctx = (f"CONTEXTO · {pl} (histórico ene-2023 a jul-2025, NO el mes en curso): del volumen "
           f"diferido acumulado, {np_pct}% No planeado (diferidas · {_fmt(s['no_planeada'], prod)} {u}) "
           f"· {p_pct}% Planeado (mantenimiento · {_fmt(s['planeada'], prod)} {u}).")
    if s["dominante"] == "no_planeada":
        clause = ("; históricamente el diferido de este producto es mayormente NO planeado (falla), "
                  "foco en confiabilidad")
    else:
        clause = ("; históricamente el diferido de este producto es mayormente Planeado "
                  "(mantenimiento previsto)")
    return ctx, clause


def _dl_bloque(p, g) -> list:
    """«Dónde está el faltante»: campo por campo, una cifra por línea. [] si no hay detractores —
    nunca se fabrica un desglose (regla N5: si no se cumple, el bloque no se emite).
    Concordancia con n=1 (mismo criterio que el ranking N5, plan_ranking_lectura_chat): el sujeto
    manda el número del verbo — "El campo… concentra", no "Los 1 mayores… concentran"."""
    detr = g.get("detractores") or []
    if not detr:
        return []
    n = len(detr)
    conc = g.get("concentracion_pct")
    n_det = g.get("n_detractores")
    cab, verbo = (f"Los {n} mayores", "concentran") if n > 1 else ("El campo con mayor faltante", "concentra")
    if conc is not None and conc >= 70:
        intro = f"{cab} {verbo} el {conc}%:"
    elif conc is not None and n_det:
        intro = f"Repartido entre {n_det} campos bajo meta. {cab} {verbo} ~{conc}%:"
    elif conc is not None:
        intro = f"{cab} {verbo} ~{conc}%:"
    elif n_det:
        intro = f"Repartido entre {n_det} campos bajo meta:"
    else:
        intro = f"{cab}:"
    u = _UNIDAD.get(p, "bbl")
    lineas = ["⟦Dónde está el faltante⟧", intro]
    for x in detr:
        lineas.append(f"  · {x['campo']} −{_fmt(abs(x['gap']), p)} {u}")
    return lineas


def _causas_bloque(impacto, split, prod) -> list:
    """«Por qué»: top-3 causas en % (impacto_historico, CAUSE_NIVEL4) + el resumen No planeado/
    Planeado (split_planeado, CAUSE_NIVEL3). Ambos son del histórico ene-2023→jul-2025, NUNCA del
    mes en curso — decisión del usuario: sin marca temporal en el texto (el chat LEE; quien quiera
    el detalle del mes lo ve en el panel de Mantenimientos). Solo %, nunca bbl (decisión del
    usuario). [] si no hay nada — nunca se fabrica."""
    lineas = []
    imp_p = ((impacto or {}).get("impacto") or {}).get(prod) if (impacto and not impacto.get("sin_datos")) else None
    causas = (imp_p or {}).get("causas") or []
    if causas:
        lineas.append("⟦Por qué⟧")
        lineas.append("Volumen perdido por causa:")
        for c in causas[:3]:
            lineas.append(f"  · {c['causa']} — {c['pct']}%")
    s = ((split or {}).get("split") or {}).get(prod) if (split and not split.get("sin_datos")) else None
    if s and s.get("total_clasificado"):
        np_pct = s["pct_no_planeada"]; p_pct = round(100 - np_pct, 1)
        resumen = (f"De ese total, {np_pct}% corresponde a eventos no planeados y "
                  f"{p_pct}% a mantenimiento programado.")
        if not lineas:
            lineas.append("⟦Por qué⟧")
        lineas.append(resumen)
    return lineas


def _iniciativa_bloque(d, ya_dicho=None) -> list:
    """«Ojo con esto»: hallazgos que el motor ya calculó y la pregunta no pidió. [] si no hay
    nada — regla N5, como _dl_bloque/_causas_bloque. SOLO AFIRMA: ninguna línea termina en «?»
    (el cierre es un contrato con el drill de maquina_q; ofrecer algo que el motor no sabe
    responder es el fallo histórico documentado en respuesta_analizar.py:49-54).
    Vocabulario vigilado: jamás «faltante»/«déficit» (REGLA CERO, test_analizar.py:172) ni los
    tokens HECHO/CAUSA/ACCIÓN/DELTA/Pediste/CONTEXTO ·/ACCIÓN · que los tests prohíben.
    `ya_dicho`: set con lo que el cuerpo ya narró — {"valle_fechas"} y/o {"conc:CRUDO", ...} —
    para no repetir (el HECHO de crudo ya dice las fechas del valle; _dl_bloque ya dice la
    concentración). try/except integral: el contrato de cero riesgo es que un fallo aquí sea
    indistinguible de «sin hallazgos»."""
    try:
        ya = ya_dicho or set()
        flags = d.get("flags") or []
        lineas = []

        # 1) producto crítico (severidad alta — siempre primero)
        for f in flags:
            if isinstance(f, dict) and f.get("tipo") == "producto_critico" and f.get("pct") is not None:
                pl = _PROD_L.get(f.get("producto"), str(f.get("producto") or "").lower())
                lineas.append(f"  · {pl.capitalize()} está en zona crítica: {f['pct']}% del presupuesto, por debajo del 60%.")

        # 2) comparativo vs mes anterior (solo variaciones >= 5%; sin PPTO de por medio)
        cm = d.get("comparativo_mes") or {}
        mes_ant = cm.get("mes_anterior")
        for p, v in (cm.get("por_producto") or {}).items():
            act, ant = (v or {}).get("actual"), (v or {}).get("anterior")
            if not (mes_ant and act and ant):
                continue
            pct = round((act / ant - 1) * 100, 1)
            if abs(pct) < 5.0:
                continue
            pl = _PROD_L.get(p, p.lower())
            verbo = "subió" if pct > 0 else "bajó"
            u = _UNIDAD.get(p, "bbl")
            lineas.append(f"  · Frente a {mes_ant}, {pl} {verbo} {abs(pct)}% "
                          f"({_fmt(act, p)} vs {_fmt(ant, p)} {u}).")

        # 3) valle — el estado es lo crítico (¿sigue abierto?); si el cuerpo ya dijo las
        #    fechas (apertura de CRUDO rezagado), solo se emite el estado.
        for f in flags:
            if isinstance(f, dict) and f.get("tipo") == "valle_activo":
                if "valle_fechas" in ya:
                    lineas.append("  · Ese valle sigue abierto a la fecha de corte — todavía no se recupera."
                                  if f.get("activo") else
                                  "  · Ese valle ya se recuperó.")
                else:
                    rng = f"del {_dia_mes(f.get('desde'))} al {_dia_mes(f.get('hasta'))}"
                    lineas.append(f"  · El valle de crudo {rng} sigue abierto a la fecha de corte — todavía no se recupera."
                                  if f.get("activo") else
                                  f"  · El valle de crudo {rng} ya se recuperó.")

        # 4) ritmo de cierre exigente
        for f in flags:
            if isinstance(f, dict) and f.get("tipo") == "pace_exigente" and f.get("requerido_dia"):
                lineas.append(f"  · Para cerrar crudo en presupuesto se necesitan {_fmt(f['requerido_dia'], 'CRUDO')} kboepd "
                              f"en los {f.get('restantes')} días restantes — un {f.get('delta_pct')}% sobre el promedio "
                              f"actual de {_fmt(f.get('promedio_dia'), 'CRUDO')} kboepd.")

        # 5) brecha concentrada — solo si _dl_bloque NO la dijo ya para ese producto
        for f in flags:
            if isinstance(f, dict) and f.get("tipo") == "gap_concentrado":
                if f"conc:{f.get('producto')}" in ya:
                    continue
                pl = _PROD_L.get(f.get("producto"), str(f.get("producto") or "").lower())
                campos = ", ".join(f.get("campos") or [])
                sufijo = f": {campos}" if campos else ""
                lineas.append(f"  · La brecha de {pl} está concentrada: ~{f.get('concentracion_pct')}% en pocos campos{sufijo}.")

        if not lineas:
            return []
        return ["⟦Ojo con esto⟧"] + lineas[:3]      # tope duro: 3 hallazgos, por severidad
    except Exception:
        return []                                     # cero riesgo: fallo == sin hallazgos


def causal(d, entidad, producto=None, split=None, impacto=None) -> str:
    """Narrativa causal SIN rótulos de grupo (decisión del usuario, 2026-08-13): «dónde está el
    faltante» (campo por campo, en bbl) + «por qué» (causas históricas, SOLO %). Alcance = entidad
    o Global. REGLA CERO si no hay rezago — esa rama y la de producto-sin-rezago (abajo) NO se
    tocan: conservan su forma HECHO/DELTA original porque los tests las pinan literalmente.
    `producto` (CRUDO/GAS/BLANCOS) = si el usuario lo nombró explícitamente, el análisis se ACOTA a
    ese producto (antes analizaba los 3 rezagados aunque se pidiera solo uno). SIGUE SIENDO str|None
    — el panel derecho (D1, dinámico por producto) usa un detector PLURAL aparte
    (`respuesta_analizar._productos_explicitos`), no este texto.
    `split` = dict de diferidas.split_planeado(campos) o None. `impacto` = dict de
    diferidas.impacto_historico(campos) o None. Ambos degradan con gracia si faltan."""
    scope = (d.get("meta") or {}).get("scope") or (entidad or "la producción ECP")
    periodo = (d.get("meta") or {}).get("periodo") or "el periodo"
    rez = _rezagados(d)

    # Acotar al producto pedido. Si ese producto NO está rezagado, se declara focalizado (no se listan
    # los otros productos, que el usuario no pidió).
    if producto:
        rez = [t for t in rez if t.get("producto") == producto]
        if not rez:
            pl = _PROD_L.get(producto, producto.lower())
            t = next((x for x in d.get("titular", []) if x.get("producto") == producto), None)
            lineas = [f"📊 {scope} · {periodo}"]
            if t and t.get("valor_pct") is not None:
                lineas.append(f"HECHO · {pl}: no hay rezago — {pl} va al {t['valor_pct']}% del "
                              f"presupuesto ({t.get('texto', '—')}); no hay faltante que explicar.")
                dl = _delta_texto(d, producto)
                if dl:
                    lineas.append(f"DELTA · {pl}: {dl}.")
            else:
                lineas.append(f"HECHO · {pl}: no tiene meta definida en el periodo — no hay rezago "
                              "que explicar.")
            ctx_line, _ = _split_lineas(split, producto)   # contexto (sin cláusula: aquí no hay ACCIÓN)
            if ctx_line:
                lineas.append(ctx_line)
            ini = _iniciativa_bloque(d)
            if ini:
                lineas.append("")
                lineas.extend(ini)
            return "\n".join(lineas)

    # --- REGLA CERO: sin rezago, se DECLARA (no se inventa) — RA-4: ramificar por "hay meta o no" ---
    if not rez:
        con_meta = [t for t in d.get("titular", []) if t.get("valor_pct") is not None]
        lineas = [f"📊 {scope} · {periodo}"]
        if con_meta:
            estado = ", ".join(f"{_PROD_L.get(t['producto'], t['producto'])} {t['valor_pct']}%" for t in con_meta)
            lineas.append(f"HECHO: no hay rezago — todo producto con meta va en o sobre ella ({estado}).")
            # DELTA igual aporta contexto (vs su propia historia), aunque no haya rezago.
            for t in con_meta:
                dl = _delta_texto(d, t["producto"])
                if dl:
                    lineas.append(f"DELTA · {_PROD_L.get(t['producto'], t['producto'])}: {dl}.")
        else:
            lineas.append("HECHO: ningún producto tiene meta definida en el periodo — no hay "
                          "cumplimiento que evaluar ni rezago que explicar.")
        ini = _iniciativa_bloque(d)
        if ini:
            lineas.append("")
            lineas.extend(ini)
        return "\n".join(lineas)

    # --- Con rezago (2026-08-13, texto acordado con el usuario, SIN rótulos de grupo, SIN ACCIÓN,
    #     SIN DELTA, causas SOLO en %): un párrafo por producto rezagado, separados por línea en
    #     blanco si hay más de uno. Cada bloque abre nombrando el producto, así que 2+ productos NO
    #     necesitan un rótulo aparte para distinguirse. ---
    lineas = [f"📊 {scope} · {periodo}", ""]
    gap = d.get("gap_por_producto", {})
    bloques_prod = []
    for t in rez:
        p = t["producto"]; pl = _PROD_L.get(p, p)
        g = gap.get(p, {})
        bloque = []

        # Apertura — RA-7: etiqueta HUMANA (titular.texto), no el código crudo. Sin "{periodo}"
        # (ya está en el encabezado 📊) y sin paréntesis: "— {estado}" en línea con el texto acordado.
        hecho = f"{pl.capitalize()} cerró al {t['valor_pct']}% del presupuesto — {t.get('texto', '—')}"
        if p == "CRUDO" and d.get("valle"):
            v = d["valle"]
            hecho += f", con un valle del {_dia_mes(v.get('desde'))} al {_dia_mes(v.get('hasta'))}"
        bloque.append(hecho + ".")

        dl_lineas = _dl_bloque(p, g)
        if dl_lineas:
            bloque.append("")
            bloque.extend(dl_lineas)

        causas_lineas = _causas_bloque(impacto, split, p)
        if causas_lineas:
            bloque.append("")
            bloque.extend(causas_lineas)

        bloques_prod.append("\n".join(bloque))

    lineas.append("\n\n".join(bloques_prod))

    ya = set()
    if d.get("valle") and any(t["producto"] == "CRUDO" for t in rez):
        ya.add("valle_fechas")            # la apertura de CRUDO ya dijo «con un valle del X al Y»
    for t in rez:
        if gap.get(t["producto"], {}).get("detractores"):
            ya.add(f"conc:{t['producto']}")   # _dl_bloque ya dijo la concentración
    ini = _iniciativa_bloque(d, ya)
    if ini:
        lineas.append("")
        lineas.extend(ini)
    return "\n".join(lineas).rstrip()


def proyeccion(d, entidad) -> str:
    """Proyección de cierre de CRUDO desde pace_crudo. Si no hay pace fiable, lo declara."""
    scope = (d.get("meta") or {}).get("scope") or (entidad or "la producción ECP")
    periodo = (d.get("meta") or {}).get("periodo") or "el periodo"
    pace = d.get("pace_crudo")
    if not pace:
        return (f"📊 {scope} · {periodo}\nNo tengo una proyección diaria fiable de crudo para este "
                "periodo (puede ser un mes ya cerrado o sin curva diaria que reconcilie).")
    prom = pace.get("promedio_dia"); req = pace.get("requerido_dia"); dpc = pace.get("delta_pct")
    rest = pace.get("restantes")
    u = _UNIDAD["CRUDO"]                       # [BEQ] kboepd ya es caudal: sin "/dia"
    linea = (f"para cerrar {periodo}, el crudo requiere {_fmt(req, 'CRUDO')} {u} en los "
             f"{rest} días restantes; va a un ritmo de {_fmt(prom, 'CRUDO')} {u}")
    if dpc is not None:
        if dpc <= 0:
            veredicto = "va camino de cerrar en meta (el ritmo actual alcanza)"
        else:
            veredicto = f"necesita acelerar {dpc}% (el ritmo actual queda corto)"
        linea += f" → {veredicto}"
    return f"📊 {scope} · {periodo}\nPROYECCIÓN · crudo: {linea}."


def panorama(d, entidad) -> str:
    """Panorama del AÑO: lo cerrado, lo proyectado y cómo va contra la meta P50.

    [2026-09-10 · PANORAMA] Acompaña a la lámina de barras apiladas. A diferencia de `senda()`
    —que solo habla de los meses que faltan— aquí se resume el año entero, porque eso es lo que
    el gráfico muestra.
    🔑 Mismo contrato que `senda`: dos posicionales, devuelve str, nunca None, nunca lanza.
    🔑 La UNIDAD se lee de `d["unidad"]` (kboepd, equivalente), NUNCA de _UNIDAD["CRUDO"]: el
       total incluye gas y filiales convertidos.
    """
    scope = entidad or "la producción ECP"
    serie = (d or {}).get("serie") or []
    con_dato = [m for m in serie if m.get("total") is not None]
    if not con_dato:
        return f"📊 {scope}\nNo tengo la serie anual de producción."
    u = (d or {}).get("unidad") or "kboepd"
    anio = (d or {}).get("anio") or ""
    cerrados = [m for m in con_dato if m.get("es_real")]
    futuros = [m for m in con_dato if not m.get("es_real")]

    partes = []
    if cerrados:
        prom = sum(m["total"] for m in cerrados) / len(cerrados)
        ult = cerrados[-1]
        partes.append(
            f"CERRADO · {len(cerrados)} meses a un promedio de {_fmt(prom, 'CRUDO')} {u}; "
            f"el último, {(ult.get('mes_nombre') or '').lower()}, en {_fmt(ult['total'], 'CRUDO')}")
    if futuros:
        partes.append(
            "PROYECTADO · " + " · ".join(
                f"{(m.get('mes_nombre') or '').lower()} {_fmt(m['total'], 'CRUDO')}"
                for m in futuros) + f" {u}")

    # Cómo va el año contra la meta: solo si TODOS los meses con dato traen su P50 — a medias
    # sería peor que callarlo (regla madre: no completar con huecos).
    if all(m.get("p50") is not None for m in con_dato):
        meta = sum(m["p50"] for m in con_dato) / len(con_dato)
        real = sum(m["total"] for m in con_dato) / len(con_dato)
        brecha = real - meta
        verbo = "por encima de" if brecha > 0 else "por debajo de"
        partes.append(
            f"Contra la meta P50 ({_fmt(meta, 'CRUDO')} {u} de promedio) el año va {verbo} "
            f"la meta en {_fmt(abs(brecha), 'CRUDO')} {u}")

    return f"📊 {scope} · panorama {anio}\n" + ".\n".join(partes) + "."


def senda(d, entidad) -> str:
    """Senda mensual proyectada hasta diciembre, desde /president/senda.

    [2026-09-08 · SENDA-DIC] Distinto contrato que `proyeccion()` (serie anual real+proyectada,
    no pace intra-mes de un solo mes) pero MISMA forma de función: dos posicionales, devuelve
    str, nunca None, nunca lanza. Cubre el TOTAL equivalente (Ecopetrol + Filiales), a diferencia
    de `proyeccion()` que solo sabe de crudo.
    🔑 `_fmt(valor, "CRUDO")` formatea cualquier kboepd por igual desde [BEQ-2026-09-08]: el
       argumento producto ya no cambia la escala, se conserva solo por los ~20 call sites que
       lo pasan (validador.py:20-28). No hace falta un producto real para formatear un total.
    🔑 La UNIDAD se lee de `d["unidad"]`, NUNCA de `_UNIDAD["CRUDO"]` (= "kbopd", petróleo
       solo): el total de esta serie es EQUIVALENTE (crudo+gas+blancos+filiales), y el propio
       endpoint ya lo rotula "kboepd" (analisis/api.py, president_senda). Etiquetarlo "kbopd"
       sería el mismo error silencioso que este plan existe para evitar, solo que en la unidad.
    """
    scope = entidad or "la producción ECP"
    serie = (d or {}).get("serie") or []
    # [2026-09-10 · SENDA-SOLO-FUTURO] PROYECCIÓN = los meses que aún no han cerrado, es decir
    # `mes > ultimo_mes_real`. Decisión del usuario: «por eso se llama proyección, muestra es lo
    # futuro».
    # [2026-09-10 · SENDA-OCTUBRE] Antes decía `> umr + 1`. Ese `+1` excluía el mes EN CURSO
    # mientras el último cerrado era agosto y septiembre corría; en cuanto septiembre CERRÓ
    # (umr=9) la fórmula pasó a pedir `mes > 10` y se comió OCTUBRE, que ya es futuro. La
    # suposición falsa era «el mes en curso es siempre umr + 1»: al cerrar un mes, el siguiente
    # deja de estar por delante del corte. Este filtro y el de respuesta_analizar.py cambian
    # SIEMPRE a la vez, o el texto y el panel dejan de coincidir.
    # 🔑 El corte sale del DATO (`ultimo_mes_real`, que el endpoint ya emite en
    #    analisis/api.py:3057-3059), NO del reloj del servidor: así el texto y la gráfica cortan
    #    por el mismo sitio aunque el proceso lleve días levantado o la ingesta vaya atrasada.
    # 🔑 IDEMPOTENTE a propósito: respuesta_analizar.py ya pasa la serie filtrada, y volver a
    #    aplicar el mismo corte sobre ella da lo mismo. Se conserva aquí para que la función siga
    #    siendo correcta si algún día se la llama con la respuesta completa del endpoint.
    # 🔑 Default 0 defensivo: sin el campo, `mes > 0` deja toda la serie — degradación suave,
    #    nunca una lista vacía silenciosa.
    umr = (d or {}).get("ultimo_mes_real") or 0
    futuros = [m for m in serie
               if (m.get("mes") or 0) > umr and m.get("total") is not None]
    if not futuros:
        return f"📊 {scope}\nNo tengo la senda proyectada para el resto del año."
    u = (d or {}).get("unidad") or "kboepd"
    partes = " · ".join(f"{(m.get('mes_nombre') or '').lower()} {_fmt(m['total'], 'CRUDO')}"
                        for m in futuros)
    linea = f"SENDA PROYECTADA · {partes} {u}."
    # Brecha contra el P50: SOLO si TODOS los meses futuros la tienen -- a medias sería peor
    # que callarla (regla madre: no inventar ni completar con huecos).
    if all(m.get("p50") is not None for m in futuros):
        p50s = " / ".join(_fmt(m["p50"], "CRUDO") for m in futuros)
        b0 = futuros[0]["total"] - futuros[0]["p50"]
        b1 = futuros[-1]["total"] - futuros[-1]["p50"]
        # [2026-09-10 · SENDA-SOLO-FUTURO] Con UN SOLO mes futuro (pasará en noviembre, cuando
        # solo quede diciembre) b0 y b1 son el MISMO punto: ninguna comparación se cumple, el
        # verbo caía en "se mantiene" y la frase salía «la brecha se mantiene de -12,3 a -12,3».
        # Un mes no tiene trayectoria, tiene una cifra — y así se dice. Llega solo con el
        # calendario, sin que nadie toque el código; por eso se cierra ahora.
        if len(futuros) < 2:
            linea += (f"\nContra el compromiso P50 ({p50s}) la brecha es de "
                      f"{_fmt(b0, 'CRUDO')} {u}.")
        else:
            if abs(b1) < abs(b0) - 1e-6:
                verbo = "se estrecha"
            elif abs(b1) > abs(b0) + 1e-6:
                verbo = "se amplía"
            else:
                verbo = "se mantiene"
            linea += (f"\nContra el compromiso P50 ({p50s}) la brecha {verbo} de "
                      f"{_fmt(b0, 'CRUDO')} a {_fmt(b1, 'CRUDO')} {u}.")
    anio = (d or {}).get("anio") or ""
    return f"📊 {scope} · resto de {anio}\n{linea}"


def diferidas(d: dict, entidad: str | None) -> str:
    """Histórico de diferidas por causa (ene-2023 → jul-2025). ROTULADO como histórico (analiza.md
    §9.3, decisión A2): NUNCA se presenta como la causa del mes en curso."""
    # FC-4: MISMA frase que ya usan causal()/proyeccion() para "sin entidad" (viene literal de
    # ejecutivo(), analisis/api.py:1970) — una sola voz para "global" en todo el grupo Analizar.
    scope = entidad or "Global (toda la producción ECP)"
    etiqueta = f"📊 {scope} · Histórico de diferidas (ene-2023 a jul-2025) — no refleja el mes en curso"

    if d.get("sin_datos"):
        if d.get("motivo"):
            return f"{etiqueta}\nNo tengo la base de diferidas disponible en este entorno."
        return f"{etiqueta}\nNo encontré diferidas registradas para {scope} en ese rango histórico."

    imp = d["impacto"]
    lineas = [etiqueta]
    for prod in ("CRUDO", "GAS"):
        b = imp.get(prod, {})
        if not b.get("total"):
            continue
        u = _UNIDAD_DIF      # [BEQ] diferidas = VOLUMEN perdido (bbl-eq)
        top = "; ".join(f"{c['causa']} {c['pct']}%" for c in b["causas"])
        lineas.append(f"{_PROD_L[prod]}: las causas que más pesan históricamente son {top} "
                      f"(total histórico: {_fmt(b['total'], prod)} {u} perdidos).")
    return "\n".join(lineas)


def _kusd(n) -> str:
    """Miles de USD, es-CO (703669 -> '703.669'). Sin decimales."""
    try:
        return f"{float(n):,.0f}".replace(",", ".")
    except Exception:
        return str(n)


def _usdbl(n) -> str:
    """USD/BI con 2 decimales, coma es-CO (46.38 -> '46,38')."""
    try:
        return f"{float(n):,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")
    except Exception:
        return str(n)


# D-A5 (S23): decir el NIVEL. "el Campo APIAY" y "el Activo APIAY" son cifras DISTINTAS y sin el
# nivel son indistinguibles. Por D-D5 un nombre que es Campo y Activo resuelve a Campo (EC-8).
_NIVEL_TXT = {"campo": "el Campo", "activo": "el Activo"}


def economia(d: dict, entidad: str | None, nivel: str | None = None,
             incluidos: list | None = None, total: int = 0) -> str:
    """EBITDA/NOPAT/margen desde el waterfall del EBITDA Inspector (universo robustez, crudo ECP).

    ROTULA: nivel + entidad (D-A5/EC-8), alcance real (robustez · crudo ECP · mes) y —si la cobertura
    es parcial— lo DECLARA EN CABECERA nombrando los campos incluidos (EC-7: NARE es 1 de 8 campos;
    un footnote convertiría esa cifra en un engaño). Degrada honesto si no hay ops (H7)."""
    incluidos = incluidos or []
    omitidos = max(0, total - len(incluidos))
    # EC-9: el global de economía NO son los 139 campos de INGESTA, es el universo robustez.
    scope = f"{_NIVEL_TXT.get(nivel, '')} {entidad}".strip() if entidad else "Global · universo robustez"
    # scope ya dice "universo robustez" en el caso Global -- no repetirlo en el sufijo.
    sufijo = ("solo crudo operado por Ecopetrol" if entidad is None
              else "universo robustez, solo crudo operado por Ecopetrol")
    etiqueta = f"📊 {scope} · Rentabilidad (EBITDA/NOPAT) — {sufijo}"

    if d.get("sin_datos"):
        return f"{etiqueta}\nNo tengo la base de rentabilidad (robustez) disponible en este entorno."

    w = d["waterfall"]
    comps = {c["key"]: c for c in w["components"]}
    y = w["meta"]["year"]; mo = w["meta"]["month"]
    mes = f"{_MES[mo]} {y}" if (mo and 1 <= mo <= 12) else "el período"

    ing = comps.get("ingresos", {}).get("value_kusd")
    ebitda = comps.get("ebitda", {}).get("value_kusd")
    ebitda_bl = comps.get("ebitda", {}).get("value_usd_bl")
    nopat = comps.get("util_neta", {}).get("value_kusd")
    margen = round(ebitda / ing * 100, 1) if (ing and ebitda is not None and ing != 0) else None

    lineas = [f"{etiqueta} ({mes})"]

    # EC-7: cobertura parcial -> PRIMERA línea del cuerpo + campos nombrados (verificable).
    de_quien = "de esta entidad"
    if omitidos:
        lineas.append(f"⚠️ COBERTURA PARCIAL: {len(incluidos)} de {total} campos del alcance están en "
                      f"robustez. Las cifras cubren SOLO: {', '.join(incluidos)}. "
                      f"Los otros {omitidos} (terceros o sin reconciliar) NO están incluidos.")
        de_quien = f"de esos {len(incluidos)} campos"

    seg_margen = f", margen {margen}% de ingresos" if margen is not None else ""
    lineas.append(f"Ingresos {de_quien}: {_kusd(ing)} kUSD. EBITDA: {_kusd(ebitda)} kUSD "
                  f"({_usdbl(ebitda_bl)} USD/BI{seg_margen}).")
    lineas.append(f"Utilidad neta (NOPAT): {_kusd(nopat)} kUSD.")
    return "\n".join(lineas)


def tendencia(t: dict, entidad, producto: str = "CRUDO") -> str:
    """Lectura de la serie mensual: dirección, ritmo y suavizado. `t` = analizar.tendencia.leer().

    `producto` en MAYÚSCULA ("CRUDO"|"GAS"|"BLANCOS"), como lo devuelve
    respuesta_analizar._producto_explicito. La unidad sale de _UNIDAD, no se pasa por parámetro:
    duplicar esa tabla es como nacen las divergencias entre bbl y MSCF.

    🔑 El texto NO repite la serie mes a mes — son hasta 12 cifras y la curva ya está en el
       panel. Dice lo que la curva no puede decir sola: si sube o baja, a qué ritmo y si esa
       dirección es de fiar.
    """
    scope = entidad or "Global (toda la producción ECP)"
    pl = _PROD_L.get(producto, "crudo")
    if not t.get("aplica"):
        return f"📊 {scope}\n{t['texto']}"

    u = _UNIDAD.get(producto, "bbl")
    dirn, pm = t["direccion"], t["pct_mensual"]
    rango = f"{t['primero']}–{t['ultimo']}"
    cab = f"📊 {scope} · {pl} · {rango} ({t['n']} meses cerrados)\nTENDENCIA · "

    if dirn == "estable":
        cuerpo = (f"la producción está ESTABLE: el cambio medio es de {abs(pm)}% mensual, por "
                  f"debajo del 1% que separa una tendencia real del ruido de operación. "
                  f"Promedio del periodo: {_fmt(t['media'], producto)} {u}.")   # [BEQ] caudal, sin "/mes"
    else:
        # El signo va en la palabra, no en el número: "cae un -2.3%" es una doble negación que
        # se lee mal. abs() en la cifra y la dirección en el verbo.
        verbo = "sube" if dirn == "al alza" else "cae"
        firmeza = ("de forma sostenida" if t["sostenida"]
                   else "de forma irregular (los meses se dispersan mucho de la línea)")
        cuerpo = (f"la producción viene {dirn.upper()}: {verbo} {abs(pm)}% al mes {firmeza}, "
                  f"lo que a doce meses equivale a {abs(t['pct_anualizado'])}% "
                  f"{'de crecimiento' if dirn == 'al alza' else 'de declinación'}. "
                  f"Promedio del periodo: {_fmt(t['media'], producto)} {u}.")   # [BEQ] caudal, sin "/mes"

    if any(v is not None for v in t.get("serie_mm") or []):
        cuerpo += " La media móvil de 3 meses está en la gráfica."
    else:
        cuerpo += (f" No dibujo media móvil de 3 meses: hacen falta 4 meses cerrados y tengo "
                   f"{t['n']}.")
    # HE4 explícito: quien lee una tendencia necesita saber que el mes en curso no cuenta.
    cuerpo += " El mes en curso NO entra: su cifra todavía es una proyección."
    return cab + cuerpo
