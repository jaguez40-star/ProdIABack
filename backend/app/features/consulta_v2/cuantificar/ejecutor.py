"""cuantificar/ejecutor.py — la cifra REAL vs PPTO (Motor Q v2, Grupo 2, Fase 1-4).

Fase 1: solo crudo. Fase 2: + gas y blancos. Fase 3: + N3 serie mensual y N4 variación mes a mes.
Fase 4: + referencia seleccionable en N1 (PPTO/OPERATIVO/CONTABLE/promedio_anio/P50-rechazo).

🔑 COHERENCIA chat↔tablero: reusa `analisis.api.desempeno` con los 4 args explícitos (patrón probado
por v1 desde 2026-07-15). La UNIDAD y el DESCARGO de honestidad los aterriza `slots` desde el catálogo
(variables_cuantificables.yaml) — el ejecutor NO decide unidades; solo arma el contrato §7. OPERATIVO/
CONTABLE salen de `analisis.escenario_mes` (helper aislado, NO toca `desempeno` — AF-4.2).

Frontera: NO SQL propio, NO LLM. La prosa (intro) es de 1c; el formato del número es de validador."""
from app.features.analisis.api import (desempeno as _desempeno_ep, _estado, escenario_mes as _escenario_ep,
                                       produccion_dia as _prod_dia_ep, curva_dia_mes as _curva_ep,
                                       curva_dia_rango as _curva_rango_ep)
from app.features.consulta_v2.cuantificar import niveles as _niveles
from app.features.consulta_v2.cuantificar.validador import fmt_valor as _fmt_valor

_ESTADO_LABEL = {"ok": "Alineado", "warn": "Rezagado", "alert": "Foco", "": "sin meta"}
_NIVEL_TEXTO = {"campo": "el Campo", "activo": "el Activo", "gerencia": "la Gerencia",
                "vicepresidencia": "la Vicepresidencia", "fuente": "la fuente", "pozo": "la fuente",
                "operador": "la operación de"}
_PROD_MAP = {"crudo": "CRUDO", "gas": "GAS", "blancos": "BLANCOS"}
_REF_LABEL = {"PPTO": "presupuesto", "OPERATIVO": "presupuesto operativo",
              "CONTABLE": "cierre contable", "promedio_anio": "promedio mensual del año"}
_REF_ESC = {"OPERATIVO": "OPERATIVO", "CONTABLE": "CONTABLE"}   # AF-4.6: nombres en dim_escenario


def _cualificar(resuelta: dict) -> str:
    """Cómo se nombra la entidad en la respuesta. [2026-08-26 · QV2-GLOBAL]

    Con la pseudo-entidad GLOBAL no hay nombre de catálogo que poner: `resuelta['valor']` es
    None y la f-string de siempre habría escrito «None». Se centraliza aquí para que los 7
    ejecutores no tengan cada uno su versión del rótulo.
    """
    if resuelta.get("global"):
        return "toda la producción de Ecopetrol"
    return f"{_etiqueta_nivel(resuelta.get('nivel'), resuelta)} {resuelta['valor']}".strip()


def _etiqueta_nivel(nivel, resuelta):
    """R2: si el resolver marcó 'puente' (gerencia que en robustez es vicepresidencia, sin
    ambigüedad), usa la etiqueta REAL en el texto. `nivel` (la columna que ya usó la query) NO
    cambia — esto es solo el rótulo mostrado al usuario en entidad_cualificada."""
    if resuelta.get("puente"):
        return _NIVEL_TEXTO.get("vicepresidencia", "")
    return _NIVEL_TEXTO.get(nivel, "")


def _valor_referencia(ref, fila, d, quiero, resuelta, slots, escenario_fn):
    """(valor, etiqueta) de la referencia elegida. PPTO/promedio salen del `d` que N1 ya trae;
    OPERATIVO/CONTABLE del helper `escenario_mes` (AF-4.2, no toca desempeno)."""
    label = _REF_LABEL.get(ref, "presupuesto")
    if ref == "PPTO":
        return fila.get("ppto"), label
    if ref == "promedio_anio":
        val = ((d.get("ritmo_mensual") or {}).get("promedio_mes") or {}).get(quiero)
        return val, label
    esc_name = _REF_ESC.get(ref)
    fn = escenario_fn or _escenario_ep
    esc = fn(resuelta["valor"], nivel=resuelta.get("nivel"),
             periodo=slots.get("periodo_texto"), escenarios=(esc_name,))
    return (esc.get(quiero) or {}).get(esc_name), label


def ejecutar(resuelta: dict, slots: dict, _desempeno_fn=None, _escenario_fn=None) -> dict:
    """Despacho por `slots["nivel_temporal"]`. N1 puntual · N2 acumulado · N3 serie · N4 variación ·
    N1D fecha puntual · N1DSEL selector de día (mejor/peor)."""
    nt = slots.get("nivel_temporal")
    if nt == "N1DSER":
        return ejecutar_n1dser(resuelta, slots)
    if nt == "N1DSEL":
        return ejecutar_n1dsel(resuelta, slots)
    if nt == "N1D":
        return ejecutar_n1d(resuelta, slots)
    if nt == "N4":
        return ejecutar_n4(resuelta, slots, _desempeno_fn=_desempeno_fn)
    if nt == "N3":
        return ejecutar_n3(resuelta, slots, _desempeno_fn=_desempeno_fn)
    if nt == "N2":
        return ejecutar_n2(resuelta, slots, _desempeno_fn=_desempeno_fn)
    return ejecutar_n1(resuelta, slots, _desempeno_fn=_desempeno_fn, _escenario_fn=_escenario_fn)


def _rechazo_comun(resuelta, slots):
    """Validaciones compartidas N1/N2. Devuelve {aplica:False, texto} o None si pasa."""
    if resuelta.get("rama") == "B":
        return {"aplica": False,
                "texto": f"«{resuelta['valor']}» es una filial; su cuantificación llega en una próxima fase."}
    if slots.get("producto") not in _PROD_MAP:
        return {"aplica": False,
                "texto": f"No sé cuantificar «{slots.get('producto')}»; puedo con crudo, gas o blancos."}
    return None


def ejecutar_n1(resuelta: dict, slots: dict, _desempeno_fn=None, _escenario_fn=None) -> dict:
    """Devuelve el contrato §7 (dict) o {aplica:False, texto}. Fase 4: crudo/gas/blancos, rama A,
    referencia seleccionable (PPTO/OPERATIVO/CONTABLE/promedio_anio; P50 se rechaza honesto)."""
    fn = _desempeno_fn or _desempeno_ep
    rech = _rechazo_comun(resuelta, slots)
    if rech:
        return rech
    producto = slots["producto"]
    unidad = slots.get("unidad", "bbl")
    ref = slots.get("referencia", "PPTO")
    if ref == "P50":
        return {"aplica": False, "texto": (
            "El P50 (compromiso) solo existe a nivel corporativo ECP-global, en kbpe, y no reconcilia "
            f"con el reporte a nivel campo/activo/gerencia; no puedo comparar «{resuelta['valor']}» "
            "contra P50. Puedo con el presupuesto (PPTO), el operativo, el contable o el promedio del año.")}
    quiero = _PROD_MAP[producto]

    d = fn(entidad=resuelta["valor"], segmento="ecp", nivel=resuelta.get("nivel"),
           periodo=slots.get("periodo_texto"))
    if not d.get("encontrada") or d.get("sin_datos"):
        return {"aplica": False, "texto": f"No tengo datos de producción para «{resuelta['valor']}»."}
    if d.get("sin_cierre"):
        return {"aplica": False,
                "texto": f"«{resuelta['valor']}» aún no tiene cierre mensual (REAL/PPTO) para ese mes."}

    mes = d["mes"]
    fila = next((p for p in d["por_producto"] if p["producto"] == quiero), None)
    if fila is None or (fila["real"] == 0 and fila["ppto"] == 0):
        return {"aplica": False, "texto": f"«{resuelta['valor']}» no reporta {producto} en ese periodo."}

    real = fila["real"]
    ref_valor, ref_label = _valor_referencia(ref, fila, d, quiero, resuelta, slots, _escenario_fn)
    cumpl = round(real / ref_valor * 100.0, 1) if ref_valor else None   # AF-4.8: recomputar vs la ref
    if ref == "promedio_anio" and cumpl is not None:      # AF-4.10: NO chip de cumplimiento en promedio
        estado = "sobre el promedio" if cumpl >= 100 else "bajo el promedio"
    else:
        estado = _ESTADO_LABEL.get(_estado(cumpl), "")
    nivel = resuelta.get("nivel")
    etiqueta = _etiqueta_nivel(nivel, resuelta)
    # [2026-09-03 · MES-CERRADO] `cerrado`, no `completo` — ver validador.py. Un mes pasado con
    # el reporte diario incompleto NO es una proyección: su REAL mensual ya es definitivo.
    proyeccion = (not mes.get("cerrado", mes["completo"])) and bool(mes["dias_con_data"])

    avisos = []
    if slots.get("descargo"):                                   # AF5: blancos-mes = confianza media
        avisos.append(slots["descargo"])
    # [2026-09-03 · MTD] «en lo que va del mes» sin decir CUÁL: el motor elige el del techo y lo
    # declara. Antes esta forma caía en N2 y devolvía el acumulado del AÑO sin avisar de nada.
    # El texto dice qué mes es y hasta dónde llega el dato — el usuario no tiene que deducirlo.
    if slots.get("mtd"):
        avisos.append(f"«En lo que va del mes» = {mes['nombre']} {mes['anio']}, con "
                      f"{mes['dias_con_data']} de {mes['dias_del_mes']} días reportados. "
                      f"Para el acumulado del AÑO, pregunta por el acumulado del año.")
    if ref != "PPTO" and not ref_valor:                       # AF-4.5: sin referencia registrada
        avisos.append(f"No hay {ref_label} registrado para {mes['nombre']} {mes['anio']}; muestro lo producido.")
    for x in (d.get("campos_sin_meta") or []):                  # AF4: aviso por producto/unidad
        if x["producto"] == quiero:
            avisos.append(f"El campo {x['campo']} produce sin meta asignada "
                          f"({_fmt_valor(x['real'], producto)} {unidad} fuera del presupuesto).")

    return {
        "aplica": True, "grupo": "cuantificar", "variable": slots.get("variable", "produccion_crudo"),
        "nivel": "N1",
        "entidad": {"nombre": resuelta["valor"], "nivel": nivel, "fue_asumida": False},
        "entidad_cualificada": _cualificar(resuelta),
        "producto": producto, "referencia": ref, "referencia_label": ref_label, "unidad": unidad, "grano": "mes",
        "universo": "reporte_diario",
        "huella": {
            "registros": mes.get("dias_con_data"),
            "rango_disponible": [f"{mes['anio']}-{mes['mes']:02d}-01",
                                 f"{mes['anio']}-{mes['mes']:02d}-{mes['dias_del_mes']:02d}"],
            "dias_del_mes": mes.get("dias_del_mes"), "es_proyeccion": proyeccion,
        },
        "resultado": {"valor": real}, "referencia_valor": ref_valor,
        "cumplimiento_pct": cumpl, "estado": estado, "mes": mes,
        "defaults_asumidos": slots.get("defaults_asumidos", []), "avisos": avisos,
        "zoom": resuelta.get("zoom", []),
    }


def ejecutar_n2(resuelta: dict, slots: dict, _desempeno_fn=None) -> dict:
    """N2 acumulado: Σ REAL de meses CERRADOS del año (HE4). Fase 2: crudo/gas/blancos, rama A.
    HE6: NO fabrica un `mes` sintético — trae `periodo_label`/`meses_cerrados`/`en_curso` propios."""
    rech = _rechazo_comun(resuelta, slots)
    if rech:
        return rech
    producto = slots["producto"]
    unidad = slots.get("unidad", "bbl")

    # [2026-09-03 · VENTANA-MESES] «los últimos N meses» acota DÓNDE EMPIEZA el acumulado.
    # Sin ventana, `desde_mes=1` = el YTD de siempre (byte a byte el comportamiento anterior).
    #
    # 🔑 GUARDA DE AÑO: `acumulado` trabaja dentro de UN año (su bucle es range(...,ultimo+1)
    #    sobre los meses de `anio`). Una ventana que cruza diciembre —«los últimos 3 meses» con
    #    techo en febrero → ini 2025-12-01— no cabe: si la aceptáramos, sumaríamos solo el tramo
    #    del año en curso (ene-feb) y llamaríamos a eso «los últimos 3 meses». Sería responder
    #    otra cosa en silencio, justo el fallo que esta rama existe para cerrar. Se declina.
    ven = slots.get("ventana") or {}
    desde_mes = 1
    if ven.get("unidad") == "mes" and ven.get("cantidad", 0) > 1:
        if str(ven["ini"])[:4] != str(ven["fin"])[:4]:
            return {"aplica": False, "texto": (
                f"«Los últimos {ven['cantidad']} meses» cruzan el cambio de año "
                f"({ven['ini'][:7]} a {ven['fin'][:7]}) y el acumulado que sé calcular va dentro "
                f"de un mismo año. Puedo darte el acumulado de {ven['fin'][:4]}, o el de un mes "
                f"concreto.")}
        desde_mes = int(str(ven["ini"])[5:7])

    ac = _niveles.acumulado(resuelta, _PROD_MAP[producto], _desempeno_fn=_desempeno_fn,
                            desde_mes=desde_mes)
    if not ac.get("aplica"):
        return {"aplica": False, "texto": ac["texto"]}

    real, ppto = ac["real"], ac["ppto"]
    cumpl = round(real / ppto * 100.0, 1) if ppto else None
    estado = _ESTADO_LABEL.get(_estado(cumpl), "")
    nivel_ent = resuelta.get("nivel")
    etiqueta = _etiqueta_nivel(nivel_ent, resuelta)
    ms = ac["meses"]
    periodo_label = (ms[0] if len(ms) == 1 else f"{ms[0]}–{ms[-1]}") + f" {ac['anio']}"

    avisos = []
    if slots.get("descargo"):
        avisos.append(slots["descargo"])
    # [2026-09-03 · VENTANA-MESES] La ventana se DECLARA. El usuario pidió «los últimos 3 meses»
    # y el rótulo dirá «junio–julio»: sin esta línea tendría que deducir por qué. Además el ancla
    # es el último día CON REPORTE (~100 días detrás del reloj), no hoy.
    if desde_mes > 1:
        avisos.append(f"«Los últimos {ven['cantidad']} meses» cuentan hacia atrás desde "
                      f"{ven['fin']}, el último día con reporte; el acumulado suma los meses "
                      f"CERRADOS dentro de esa ventana.")
    if ac.get("en_curso"):
        avisos.append(f"El mes de {ac['en_curso']['nombre']} sigue en curso; su proyección NO está "
                      f"incluida en el acumulado.")
    # [2026-09-03 · ACUM-MES-CERRADO] Un mes que falta cambia la cifra: se declara. Antes se
    # descartaba en silencio y el rótulo seguía diciendo el rango completo.
    if ac.get("omitidos"):
        _om = ", ".join(ac["omitidos"])
        avisos.append(f"No tengo cierre mensual de {_om}; {'esos meses' if len(ac['omitidos']) > 1 else 'ese mes'} "
                      f"NO está{'n' if len(ac['omitidos']) > 1 else ''} en el acumulado.")
    if slots.get("referencia", "PPTO") != "PPTO":                      # AF-4.7: solo N1 honra la referencia
        avisos.append("Las referencias alternas (operativo/contable/promedio) por ahora solo aplican al "
                      "dato puntual de un mes; el acumulado se compara con el presupuesto (PPTO).")

    return {
        "aplica": True, "grupo": "cuantificar", "variable": slots.get("variable", "produccion_crudo"),
        "nivel": "N2",
        "entidad": {"nombre": resuelta["valor"], "nivel": nivel_ent, "fue_asumida": False},
        "entidad_cualificada": _cualificar(resuelta),
        "producto": producto, "referencia": "PPTO", "unidad": unidad, "grano": "mes",
        "universo": "reporte_diario",
        "resultado": {"valor": real}, "referencia_valor": ppto,
        "cumplimiento_pct": cumpl, "estado": estado,
        "periodo_label": periodo_label, "meses_cerrados": len(ms), "en_curso": ac.get("en_curso"),
        # [2026-09-03 · CURVA-ACUMULADA] La curva creciente del acumulado. Aditiva: quien no la
        # lea (la burbuja de texto, validador.formatear_cuerpo) sigue funcionando igual.
        # 🔑 `anio` se propaga EXPLÍCITAMENTE (v2/H15). `niveles.acumulado` lo devuelve desde
        #    siempre pero este contrato no lo llevaba, y N2 NO tiene la clave `mes` (HE6 lo
        #    prohíbe: nada de meses sintéticos), así que el panel no tenía de dónde sacar el año
        #    para el título del gráfico y salía un hueco.
        "anio": ac.get("anio"),
        "serie_acum": ac.get("serie_acum") or [],
        "huella": {"registros": len(ms), "es_proyeccion": False},
        "defaults_asumidos": slots.get("defaults_asumidos", []), "avisos": avisos,
        "zoom": resuelta.get("zoom", []),
    }


def ejecutar_n3(resuelta: dict, slots: dict, _desempeno_fn=None) -> dict:
    """N3 serie mensual. HE6: contrato propio (lleva `serie`/`promedio`/`proyeccion_mes`)."""
    rech = _rechazo_comun(resuelta, slots)
    if rech:
        return rech
    producto = slots["producto"]
    unidad = slots.get("unidad", "bbl")
    s = _niveles.serie(resuelta, _PROD_MAP[producto], _desempeno_fn=_desempeno_fn)
    if not s.get("aplica"):
        return {"aplica": False, "texto": s["texto"]}
    nivel_ent = resuelta.get("nivel")
    etiqueta = _etiqueta_nivel(nivel_ent, resuelta)
    avisos = []
    if slots.get("descargo"):
        avisos.append(slots["descargo"])
    if s.get("proyeccion_mes"):
        avisos.append(f"El último mes ({s['proyeccion_mes']}) es proyección de cierre; aún no es un mes cerrado.")
    return {
        "aplica": True, "grupo": "cuantificar", "variable": slots.get("variable", "produccion_crudo"),
        "nivel": "N3",
        "entidad": {"nombre": resuelta["valor"], "nivel": nivel_ent, "fue_asumida": False},
        "entidad_cualificada": _cualificar(resuelta),
        "producto": producto, "referencia": "PPTO", "unidad": unidad, "grano": "mes",
        "universo": "reporte_diario",
        "serie": s["puntos"], "promedio": s.get("promedio"), "anio": s["anio"],
        "proyeccion_mes": s.get("proyeccion_mes"), "mes_actual": s.get("mes_actual"),
        "huella": {"registros": len(s["puntos"]), "es_proyeccion": bool(s.get("proyeccion_mes"))},
        "defaults_asumidos": slots.get("defaults_asumidos", []), "avisos": avisos,
        "zoom": resuelta.get("zoom", []),
    }


def ejecutar_n4(resuelta: dict, slots: dict, _desempeno_fn=None) -> dict:
    """N4 variación mes-a-mes. Contrato con `deltas`/`ultimo`/`proyeccion_mes`.
    [2026-08-25] QV2-PANEL-MES: publica la serie de niveles como `serie`, con el MISMO nombre
    que N3 (:222) — el waterfall la necesita para las barras `total` de partida y cierre.
    🔑 `serie` y no `puntos`: son el mismo dato y un solo nombre público evita que el panel
    tenga dos rutas para una serie mensual idéntica."""
    rech = _rechazo_comun(resuelta, slots)
    if rech:
        return rech
    producto = slots["producto"]
    unidad = slots.get("unidad", "bbl")
    v = _niveles.variacion(resuelta, _PROD_MAP[producto], _desempeno_fn=_desempeno_fn)
    if not v.get("aplica"):
        return {"aplica": False, "texto": v["texto"]}
    nivel_ent = resuelta.get("nivel")
    etiqueta = _etiqueta_nivel(nivel_ent, resuelta)
    avisos = []
    if slots.get("descargo"):
        avisos.append(slots["descargo"])
    if v.get("proyeccion_mes"):
        avisos.append(f"El último mes ({v['proyeccion_mes']}) es proyección; el último cambio puede moverse al cerrar.")
    return {
        "aplica": True, "grupo": "cuantificar", "variable": slots.get("variable", "produccion_crudo"),
        "nivel": "N4",
        "entidad": {"nombre": resuelta["valor"], "nivel": nivel_ent, "fue_asumida": False},
        "entidad_cualificada": _cualificar(resuelta),
        "producto": producto, "referencia": "PPTO", "unidad": unidad, "grano": "mes",
        "universo": "reporte_diario",
        "serie": v["puntos"], "deltas": v["deltas"], "ultimo": v["ultimo"], "anio": v["anio"],
        "proyeccion_mes": v.get("proyeccion_mes"), "mes_actual": v.get("mes_actual"),
        "huella": {"registros": len(v["deltas"]) + 1, "es_proyeccion": bool(v.get("proyeccion_mes"))},
        "defaults_asumidos": slots.get("defaults_asumidos", []), "avisos": avisos,
        "zoom": resuelta.get("zoom", []),
    }


# [2026-08-25] GRANO DÍA. Contrato propio (NO trae `mes`): validador ramifica antes de N1.
_DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_MESES_ES_L = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
               "septiembre", "octubre", "noviembre", "diciembre"]


def fecha_es(d) -> str:
    """'viernes 15 de mayo de 2026'. Tablas manuales: strftime devuelve INGLÉS en esta máquina
    (verificado 2026-08-25) y locale.setlocale es global y frágil."""
    return f"{_DIAS_ES[d.weekday()]} {d.day} de {_MESES_ES_L[d.month]} de {d.year}"


def _rechazo_dia(resuelta, slots, techo, que="ese día"):
    """Rechazo HONESTO: cita el techo REAL consultado, nunca una constante."""
    if slots.get("producto") == "blancos":       # catálogo: granos.dia confianza=no (×2)
        return {"aplica": False, "texto": (
            f"Los blancos a grano día no reconcilian con el mes (el reporte los mide por corrientes "
            f"físicas), así que no puedo darte {que} de blancos para «{resuelta['valor']}». "
            f"A grano mes sí puedo.")}
    if techo is None:
        return {"aplica": False,
                "texto": f"No tengo reporte diario para «{resuelta['valor']}»."}
    return {"aplica": False, "texto": (
        f"No tengo reporte diario de «{resuelta['valor']}» para {que}: el dato diario llega hasta "
        f"el {fecha_es(techo)}. Si me nombras un día dentro de ese rango, o el mes, te doy la cifra.")}


def ejecutar_n1d(resuelta: dict, slots: dict, _dia_fn=None) -> dict:
    """N1D: producción REAL de UNA fecha. Sin PPTO (no existe a grano día) → sin cumplimiento."""
    import datetime as _dt
    fn = _dia_fn or _prod_dia_ep
    rech = _rechazo_comun(resuelta, slots)
    if rech:
        return rech
    dia = slots.get("dia") or {}
    if dia.get("clase") == "relativo":
        f = _dt.date.today() + _dt.timedelta(days=dia["delta"])
    else:
        f = _dt.date.fromisoformat(dia["fecha"])
    producto = slots["producto"]
    r = fn(resuelta["valor"], f, nivel=resuelta.get("nivel"))
    if producto == "blancos" or not r.get("hay_dato"):
        return _rechazo_dia(resuelta, slots, r.get("techo"), f"el {fecha_es(f)}")
    val = (r["por_producto"] or {}).get(_PROD_MAP[producto], 0.0)
    if not val:
        return {"aplica": False, "texto":
                f"«{resuelta['valor']}» no reporta {producto} el {fecha_es(f)}."}
    # [2026-08-25] Sin aviso de "no hay presupuesto diario": el cuerpo de N1D nunca ofrece
    # cumplimiento (ver formatear_cuerpo), así que anunciar su ausencia respondía algo que
    # nadie preguntó. No se destaca lo que falta.
    avisos = []
    if slots.get("descargo"):
        avisos.append(slots["descargo"])
    return {
        "aplica": True, "grupo": "cuantificar", "variable": slots.get("variable"),
        "nivel": "N1D", "grano": "dia", "universo": "reporte_diario",
        "entidad": {"nombre": resuelta["valor"], "nivel": resuelta.get("nivel"), "fue_asumida": False},
        "entidad_cualificada": _cualificar(resuelta),
        "producto": producto, "unidad": slots.get("unidad", "bbl"),
        "fecha": f.isoformat(), "fecha_label": fecha_es(f),
        "resultado": {"valor": val},
        "referencia": None, "referencia_valor": None, "cumplimiento_pct": None, "estado": "",
        "techo_dia": r["techo"].isoformat() if r.get("techo") else None,
        "defaults_asumidos": slots.get("defaults_asumidos", []), "avisos": avisos,
        "zoom": resuelta.get("zoom", []),
    }


def ejecutar_n1dser(resuelta: dict, slots: dict, _curva_fn=None, _curva_rango_fn=None) -> dict:
    """N1DSER: la CURVA DIARIA de un mes («la producción día a día de Akacias en junio»).

    [2026-08-26 · QV2-SERIE-DIA] La curva ya la dibujaba `cuant_dia_panel`; lo que faltaba era la
    puerta de entrada. Hasta ahora las únicas dos formas de llegar al panel diario eran nombrar un
    día concreto o pedir el mejor/peor, así que «día a día» caía a N1 y respondía el KPI del mes.

    El texto NO da una sola cifra —son 30— sino el marco que la curva no puede decir por sí sola:
    total del mes, promedio por día y cuántos días llevan reporte. El detalle lo pone el panel.
    """
    fn = _curva_fn or _curva_ep
    rech = _rechazo_comun(resuelta, slots)
    if rech:
        return rech
    ser = slots.get("serie_dia") or {}
    ven = slots.get("ventana") or {}
    producto = slots["producto"]
    # [2026-09-03 · CURVA-VENTANA] Dos orígenes para la MISMA curva: un mes calendario
    # (`serie_dia`, «día a día en junio») o una ventana móvil (`ventana`, «los últimos 30 días»).
    # 🔑 La ventana solo se usa si NO hay `serie_dia`: si el usuario nombró un mes, ese mes manda.
    if ven and not ser:
        pts_all = (_curva_rango_fn or _curva_rango_ep)(
            resuelta["valor"], ven["ini"], ven["fin"], _PROD_MAP[producto],
            nivel=resuelta.get("nivel"))
        pts = [(f, v) for f, v in pts_all if v > 0]
        if not pts:
            return {"aplica": False, "texto": (
                f"No tengo curva diaria de {producto} para «{resuelta['valor']}» "
                f"entre {ven['ini']} y {ven['fin']}.")}
    else:
        pts = [(f, v) for f, v in fn(resuelta["valor"], ser["anio"], ser["mes"],
                                     _PROD_MAP[producto], nivel=resuelta.get("nivel")) if v > 0]
        if not pts:
            return {"aplica": False, "texto": (
                f"No tengo curva diaria de {producto} para «{resuelta['valor']}» en "
                f"{_MESES_ES_L[ser['mes']]} {ser['anio']}.")}
    total = sum(v for _f, v in pts)
    avisos = []
    if slots.get("descargo"):
        avisos.append(slots["descargo"])
    if producto == "blancos":
        # [2026-08-26] BLANCOS a grano día SÍ se muestra — decisión del usuario, reafirmada.
        # La curva existe; lo que no reconcilia es su MAGNITUD: el reporte diario suma varios
        # conceptos-copia del mismo volumen, así que sale inflada frente al mensual (medido en
        # mayo: KPI 619k bbl/mes = 72% vs curva 66.871 bbl/día = ~134%; ver
        # HALLAZGO_concepto_multiplicidad.md, arreglo de fondo pendiente en el ETL).
        # Se muestra CON el aviso: la FORMA de la curva —dónde sube y dónde cae— es válida y es
        # lo que se pide; ocultarla entera por un factor de escala era negarle un dato que existe.
        avisos.append("La curva diaria de blancos NO reconcilia con la cifra mensual: el reporte "
                      "diario suma conceptos repetidos y los valores salen inflados. Sirve para ver "
                      "la FORMA (qué días suben y cuáles caen), no para tomar la magnitud.")
    if any(str(a).startswith("periodo=") for a in (ser.get("asumido") or [])):
        avisos.append(f"No me dijiste el mes, así que tomé {_MESES_ES_L[ser['mes']]} "
                      f"{ser['anio']} (el último con reporte diario).")
    # [2026-09-03 · CURVA-VENTANA] La ventana se ancla al último día CON REPORTE, no al reloj.
    # Se declara siempre: el usuario dijo «últimos 30 días» pensando en hoy, y el dato va ~100
    # días atrás. Callarlo sería dejarle creer que la curva llega hasta ayer.
    if ven and not ser:
        avisos.append(f"«Últimos {ven['cantidad']} {ven['unidad']}s» cuenta hacia atrás desde "
                      f"{ven['fin']}, el último día con reporte diario.")
    # NO se avisa de que a grano día no hay PPTO: ese aviso se retiró de N1D/N1DSEL a propósito
    # (commit 3bb4108) y esta rama es su hermana — reponerlo aquí lo devolvería por la puerta de atrás.
    return {
        "aplica": True, "grupo": "cuantificar", "variable": slots.get("variable"),
        "nivel": "N1DSER", "grano": "dia", "universo": "reporte_diario",
        "entidad": {"nombre": resuelta["valor"], "nivel": resuelta.get("nivel"), "fue_asumida": False},
        "entidad_cualificada": _cualificar(resuelta),
        "producto": producto, "unidad": slots.get("unidad", "bbl"),
        "resultado": {"valor": total},
        "promedio_dia": total / len(pts),
        # [2026-09-03 · CURVA-VENTANA] Con ventana no hay UN mes que rotular: la curva puede ir
        # de julio a agosto. Se rotula el RANGO REAL con dato, que es lo que el gráfico muestra.
        "mes_label": (f"{pts[0][0].isoformat()} a {pts[-1][0].isoformat()}"
                      if (ven and not ser) else f"{_MESES_ES_L[ser['mes']]} {ser['anio']}"),
        "ventana": ({"unidad": ven["unidad"], "cantidad": ven["cantidad"],
                     "ini": ven["ini"], "fin": ven["fin"]} if (ven and not ser) else None),
        "dias_con_dato": len(pts),
        "rango": [pts[0][0].isoformat(), pts[-1][0].isoformat()],
        "referencia": None, "referencia_valor": None, "cumplimiento_pct": None, "estado": "",
        "defaults_asumidos": slots.get("defaults_asumidos", []), "avisos": avisos,
        "zoom": resuelta.get("zoom", []),
    }


def ejecutar_n1dsel(resuelta: dict, slots: dict, _curva_fn=None) -> dict:
    """N1DSEL: día de MAYOR/MENOR producción dentro de un mes (argmax sobre la curva diaria).
    NO es el ranking N5: allí se ordenan ENTIDADES; aquí la entidad es fija y se ordena el TIEMPO."""
    fn = _curva_fn or _curva_ep
    rech = _rechazo_comun(resuelta, slots)
    if rech:
        return rech
    dia = slots.get("dia") or {}
    producto = slots["producto"]
    if producto == "blancos":
        return _rechazo_dia(resuelta, slots, None, "el mejor día")
    pts = [(f, v) for f, v in fn(resuelta["valor"], dia["anio"], dia["mes"],
                                 _PROD_MAP[producto], nivel=resuelta.get("nivel")) if v > 0]
    if not pts:
        return {"aplica": False, "texto": (
            f"No tengo curva diaria de {producto} para «{resuelta['valor']}» en "
            f"{_MESES_ES_L[dia['mes']]} {dia['anio']}.")}
    elegido = (max if dia.get("orden") == "max" else min)(pts, key=lambda r: r[1])
    # [2026-08-26 · QV2-DIA-SEL] El mes ASUMIDO se declara. `detectar_dia` ya marcaba
    # `asumido=['periodo=MM/AAAA']` cuando la pregunta no nombra mes, pero aquí se emitía
    # `avisos: []` fijo y el dato moría en el camino: la respuesta afirmaba «el mejor día de
    # agosto» a quien no había dicho agosto, sin señalar que era una suposición. Es la regla de
    # no degradar en silencio (slots.py:66-69) aplicada al último tramo.
    avisos_sel = []
    if any(str(a).startswith("periodo=") for a in (dia.get("asumido") or [])):
        avisos_sel.append(f"No me dijiste el mes, así que tomé {_MESES_ES_L[dia['mes']]} "
                          f"{dia['anio']} (el último con reporte diario).")
    return {
        "aplica": True, "grupo": "cuantificar", "variable": slots.get("variable"),
        "nivel": "N1DSEL", "grano": "dia", "universo": "reporte_diario",
        "entidad": {"nombre": resuelta["valor"], "nivel": resuelta.get("nivel"), "fue_asumida": False},
        "entidad_cualificada": _cualificar(resuelta),
        "producto": producto, "unidad": slots.get("unidad", "bbl"),
        "orden": dia.get("orden", "max"),
        "fecha": elegido[0].isoformat(), "fecha_label": fecha_es(elegido[0]),
        "resultado": {"valor": elegido[1]},
        "mes_label": f"{_MESES_ES_L[dia['mes']]} {dia['anio']}",
        "dias_con_dato": len(pts),
        "rango": [pts[0][0].isoformat(), pts[-1][0].isoformat()],
        "referencia": None, "referencia_valor": None, "cumplimiento_pct": None, "estado": "",
        "defaults_asumidos": slots.get("defaults_asumidos", []), "avisos": avisos_sel,
        "zoom": resuelta.get("zoom", []),
    }
