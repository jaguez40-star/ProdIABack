"""Fase 3.1 · Narración conversacional (el LLM redacta lo que Python ya calculó).

Toma la respuesta DETERMINISTA de ejecucion.ejecutar() (cifra REAL vs PPTO ya calculada) y pide al LLM
que la redacte en 2-3 oraciones de lenguaje llano, personalizadas con el nombre del usuario y con la
invitación a seguir explorando. FRONTERA DURA: el LLM NO calcula, NO recalcula, NO inventa números —
solo teje en prosa los valores del JSON. Si el LLM falla, viola la regla numérica (D-N5) o el flag está
apagado → devuelve None y el frontend pinta la plantilla determinista.

Gobernado por CONSULTA_NARRA_LLM (default false: dev sirve la plantilla; prod/139 con gemma4 = true).
Mismo patrón que EJECUTIVO_USAR_LLM, incluido format=json: en gemma4@139 la generación de TEXTO PLANO
(/api/generate sin format) devuelve response vacío, así que se pide {"narracion": "..."} y se extrae
el texto (fix verificado 2026-07-15). Al fallar, devuelve el dict con texto=None + diag (no None) para
que el frontend caiga a la plantilla PERO pueda loguear el motivo → deja de ser caja negra.
"""
import json as _json, urllib.request as _urlreq
from app.core.config import get_settings
from app.features.consulta.ejecucion import _fmt

# Unidad por producto (dominio petrolero). Mapa SEGURO: crudo/blancos en barriles; gas sin unidad
# (KPC/KPCD ambiguo hasta confirmar por spot-check) → el prompt narra sin unidad si viene vacía.
_UNIDAD = {"CRUDO": "barriles", "BLANCOS": "barriles", "GAS": ""}

_SISTEMA = (
    "Eres el narrador de ProdIA, un asistente de produccion petrolera de Ecopetrol.\n"
    "TU TAREA: REESCRIBIR el borrador que te doy para que suene natural, como un colega tecnico que "
    "te resume el dato en el pasillo. NO estas componiendo desde cero: el borrador ya es correcto y "
    "completo, solo esta escrito de forma rigida. Cambia la FORMA, jamas el FONDO.\n"
    "REGLAS INQUEBRANTABLES:\n"
    "1. NUNCA inventes, redondees ni recalcules ningun numero. Copia cada volumen y cada porcentaje "
    "EXACTAMENTE con los mismos digitos y signos de puntuacion del borrador.\n"
    "2. NUNCA agregues informacion que no este en el borrador, ni quites nada de lo que dice.\n"
    "3. NUNCA cambies el sentido: si el borrador dice que algo esta por encima de la meta, tu texto "
    "tambien; si dice por debajo, tambien. Invertir eso es el peor error posible.\n"
    "3b. Si el borrador dice que la entidad VA CAMINO DE CERRAR en una cifra, esa cifra es la "
    "PROYECCION del mes en curso, NO lo ya producido: esta PROHIBIDO escribir que 'produjo', 'cerro "
    "con', 'acumulo' o 'ha producido' esa cifra. Usa futuro o proyeccion ('va camino de', 'proyecta "
    "cerrar', 'cerraria en'). Solo si el borrador dice 'produjo' la cifra esta cerrada.\n"
    "4. Conserva el nombre de la entidad tal cual ('el Campo APIAY', 'el Activo APIAY'): un mismo "
    "nombre puede ser un Campo y un Activo con cifras muy distintas y el lector debe saber cual ve.\n"
    "5. 'no tiene meta definida' significa que a ese producto no le asignaron presupuesto. NO lo "
    "cambies por 'no hay datos', 'no se reporto' ni 'no produce': son cosas distintas y confundirlas "
    "es un error de fondo.\n"
    "5b. El borrador maneja DOS cifras distintas del mismo producto y NO puedes fundirlas: (a) lo "
    "ACUMULADO en los dias con reporte, con su ritmo BOPD-avg, que es lo REALMENTE producido; (b) lo "
    "que el reporte PROYECTA al mes, que es sobre lo que se calcula el % de la meta. Manten cada una "
    "con su acotacion ('para los N dias de operacion', 'proyecta al mes'). NUNCA multipliques el BOPD "
    "por los dias del mes ni lo presentes como origen de la proyeccion: no lo es, y los dos numeros "
    "no coinciden.\n"
    "6. Se conciso: 2 a 4 oraciones (el limite alto solo si hay varios productos).\n"
    "VARIA LA FORMA (esto es lo que se te pide de verdad):\n"
    "a. NO sigas el orden del borrador de forma mecanica. Puedes abrir por el resultado, por la "
    "entidad o por el periodo; puedes fusionar o partir oraciones.\n"
    "b. PROHIBIDO el lenguaje de formulario. Nunca escribas 'el producto X reporto un volumen de', "
    "'su clasificacion es', 'con cobertura calculada sobre'. Escribe como habla una persona: 'lleva', "
    "'acumula', 'va en', 'cerro', 'suma'.\n"
    "c. Usa sinonimos y giros distintos cada vez. Dos respuestas seguidas NO deben tener la misma "
    "estructura.\n"
    "d. Si el borrador saluda por el nombre, mantenlo (puede ir al inicio o integrado en la frase).\n"
    "EJEMPLOS de formas DISTINTAS y validas para un mismo dato (los numeros son de ejemplo):\n"
    '- "Javier, el Campo TELLO acumula 1.234 barriles de CRUDO en Mayo 2026: 102.7% del presupuesto, '
    'por encima de la meta y clasificado como Alineado."\n'
    '- "El Campo TELLO va por encima de la meta en Mayo 2026, Javier: 1.234 barriles de CRUDO, un '
    '102.7% del presupuesto (Alineado)."\n'
    '- "En lo corrido de Mayo 2026 el Campo TELLO lleva 1.234 barriles de CRUDO y esta en 102.7% del '
    'presupuesto, o sea por encima de la meta (Alineado). Javier, ahi vas bien."\n'
    "FORMATO DE SALIDA: responde UNICAMENTE un objeto JSON con una sola clave \"narracion\" cuyo valor "
    "sea el texto reescrito. Sin markdown, sin nada fuera del JSON."
)


def _direccion(pct) -> str | None:
    """Palabra de dirección, escrita por PYTHON (no inferida por el LLM). Es la mitad del fix del
    error semántico: si el borrador ya dice 'por encima de la meta', el modelo solo la copia."""
    if pct is None:
        return None
    return "por encima de la meta" if pct >= 100 else "por debajo de la meta"


def _cap(s: str) -> str:
    return (s[:1].upper() + s[1:]) if s else s


def _de(ent: str) -> str:
    """Contracción: 'el Campo X' → 'del Campo X'. Sin esto salía "la producción de el Campo X"."""
    return ("del " + ent[3:]) if ent.startswith("el ") else ("de " + ent)


def _borrador(respuesta: dict, usuario=None) -> str:
    """ETAPA 1 (Python): el borrador en prosa, correcto y completo pero rígido. El LLM solo lo
    REESCRIBE (etapa 2). 2026-07-16.

    Antes el LLM componía la prosa desde el JSON del payload, y se notaba: transcribía las CLAVES del
    esquema ('el producto CRUDO reportó un volumen de', 'su clasificación es Alineado', 'con cobertura
    calculada sobre'), y como el prompt era una lista de chequeo, la recorría en orden → todas las
    respuestas con el mismo esqueleto. Componer desde un esquema es la parte difícil para un modelo de
    4B; reescribir una frase ya correcta es fácil. Además el borrador trae la DIRECCIÓN ya escrita
    (_direccion), así que el modelo no tiene que deducir si 102.7% supera o no la meta.

    Sirve doble: entrada del LLM y FALLBACK si el LLM falla (el frontend pinta prosa cuando
    narracion.texto viene con algo, y conserva los avisos) → nunca se muestra peor que hoy."""
    ent = respuesta.get("entidad_cualificada") or respuesta.get("entidad") or "la entidad"
    mes = respuesta.get("mes") or {}
    periodo = " ".join(str(x) for x in (mes.get("nombre"), mes.get("anio")) if x)
    u = (usuario or "").strip()

    con_meta = [l for l in respuesta.get("lineas", []) if l.get("cumplimiento") is not None]
    sin_meta = [l for l in respuesta.get("lineas", []) if l.get("cumplimiento") is None]

    frases = []
    dias = mes.get("dias_con_data")
    proy = bool(respuesta.get("proyeccion"))
    omitir_pie = False
    for i, l in enumerate(con_meta):
        pr = l.get("producto")
        uni = _UNIDAD.get(pr, "")
        vol = " ".join(x for x in (_fmt(l.get("real")), uni) if x)
        pct = l.get("cumplimiento")
        # La META en barriles, no solo el %: "78.5%" a secas no dice de qué. Con ella, el lector ve
        # el tamaño del hueco (3.720.510 contra 4.741.721) sin tener que despejarlo.
        meta = " ".join(x for x in (_fmt(l.get("ppto")), uni) if x) if l.get("ppto") else None
        det = (f"un {pct}% de la meta propuesta ({meta})" if meta else f"un {pct}% del presupuesto")
        det += f", {_direccion(pct)}"
        if l.get("estado"):
            det += f", clasificado como {l['estado']}"
        if i == 0:
            # Estructura pedida por el usuario (2026-07-16): primero lo OBSERVADO (acumulado + ritmo),
            # después la proyección, y el % contra la meta al final. Antes se abría con la cifra
            # proyectada y lo realmente producido no aparecía: el lector no tenía con qué juzgarla.
            cabeza = (f"{u}, la producción {_de(ent)}" if u else f"La producción {_de(ent)}")
            if proy and l.get("mtd") is not None and dias:
                mtd_txt = " ".join(x for x in (_fmt(l["mtd"]), uni) if x)
                ritmo = f" ({_fmt(l['bopd_avg'])} BOPD-avg)" if l.get("bopd_avg") else ""
                frases.append(f"{cabeza}, para los {dias} días de operación del mes, reporta "
                              f"{mtd_txt} de {pr}{ritmo}.")
                # "El reporte la proyecta": la proyección NO la calcula Python — es del reporte, y por
                # eso no sale de multiplicar el BOPD (AKACIAS: 112.725×31=3.494.460 ≠ 3.720.510).
                frases.append(f"El reporte la proyecta al mes en {vol}: {det}.")
                # el pie ("Proyección del cierre del mes: … lleva 17 de 31 días…") repetiría lo que
                # estas dos frases ya dicen, y con más rodeo
                omitir_pie = True
            elif proy:
                cierra = f" {periodo}" if periodo else ""
                frases.append(f"{cabeza} va camino de cerrar{cierra} en {vol} de {pr}: {det}.")
            else:
                en = f" en {periodo}" if periodo else ""
                frases.append(f"{cabeza}{en} fue de {vol} de {pr}: {det}.")
        else:
            frases.append(f"En {pr}: {vol}, {det}.")

    if sin_meta:
        nombres = " y ".join(l.get("producto") for l in sin_meta)
        verbo = "tienen" if len(sin_meta) > 1 else "tiene"
        frases.append(f"{nombres} no {verbo} meta definida en el periodo.")

    if not con_meta and not sin_meta:   # defensivo: ejecutar() no debería llegar aquí sin líneas
        frases.append(f"{_cap(ent)} no tiene cifras para {periodo or 'el periodo'}.")

    if respuesta.get("pie") and not omitir_pie:
        frases.append(str(respuesta["pie"]))

    acciones = _acciones(respuesta)
    if acciones:
        frases.append("Puedes seguir con: " + ", ".join(acciones) + ".")
    return " ".join(frases)


def _acciones(respuesta: dict) -> list:
    entidad = respuesta.get("entidad")
    acciones = [f"Analizar {entidad}" if entidad else "Analizar la entidad"]
    if (respuesta.get("mes") or {}).get("dias_con_data"):
        acciones.append("Ver el reporte de un dia")
    return acciones


def _payload(respuesta: dict, usuario) -> dict:
    """Arma el JSON de entrada al LLM SOLO con valores ya calculados por ejecutar()."""
    mes = respuesta.get("mes") or {}
    productos = []
    for l in respuesta.get("lineas", []):
        pr = l.get("producto")
        pct = l.get("cumplimiento")
        productos.append({
            "producto": pr,
            "volumen": _fmt(l.get("real")),                 # string ya formateado (fuente de la salvaguarda)
            "unidad": _UNIDAD.get(pr, ""),
            # string ya formateado: el LLM debe copiarlo literal (D-N5 lo verifica, igual que el volumen)
            "porcentaje_presupuesto": f"{pct}%" if pct is not None else "sin meta definida",
            "clasificacion": l.get("estado") or "sin meta",
            # Cifras protegidas por D-N5 igual que el volumen: el lector no puede verificarlas de
            # cabeza, así que no pueden quedar sueltas a lo que el LLM decida escribir.
            "acumulado_dias_con_reporte": _fmt(l["mtd"]) if l.get("mtd") is not None else None,
            "ritmo_diario": _fmt(l["bopd_avg"]) if l.get("bopd_avg") else None,
            "meta": _fmt(l["ppto"]) if l.get("ppto") else None,
        })
    entidad = respuesta.get("entidad")
    acciones = _acciones(respuesta)     # mismas que las del borrador (una sola fuente)
    u = (usuario or "").strip() or None
    return {
        "usuario": u,
        "entidad": entidad,
        "nivel": respuesta.get("nivel"),
        # D-A5: el nivel viaja explícito para que la prosa NUNCA diga solo "APIAY"
        "entidad_cualificada": respuesta.get("entidad_cualificada") or entidad,
        # dirección por producto: la fuente de verdad del chequeo direccional (D-N6)
        "direcciones": {l.get("producto"): _direccion(l.get("cumplimiento"))
                        for l in respuesta.get("lineas", [])},
        # NOTA: los `avisos` (D-A4: campos del activo sin meta) NO se le pasan al LLM a propósito.
        # Son salvedades sobre la VALIDEZ de la cifra: el frontend las pinta siempre, verbatim, bajo
        # la prosa (__cnRespuestaHtml renderiza `avisos` en las dos ramas). Delegarlas al LLM las
        # expondría a que las suavice, las omita o las duplique con la nota determinista.
        "periodo": {"mes": mes.get("nombre"), "anio": mes.get("anio"),
                    "dias_reportados": mes.get("dias_con_data"),
                    "dias_del_mes": mes.get("dias_del_mes"), "cerrado": mes.get("completo")},
        "cobertura": respuesta.get("pie"),   # frase determinista de cobertura (grano diario o cierre mensual)
        "productos": productos,
        "acciones_disponibles": acciones,
    }


def _cumple_regla_numerica(texto: str, payload: dict) -> tuple[bool, str]:
    """D-N5: cada volumen Y cada porcentaje del JSON debe aparecer LITERAL en la narración.

    Ampliada a porcentajes el 2026-07-16: la salvaguarda original solo validaba el volumen, así que
    un porcentaje mal copiado pasaba silencioso (caso observado en 139: volumen de BLANCOS correcto
    -4.544- con "56.7%" cuando el dato daba 59.6%). El % es lo que dispara la lectura de riesgo del
    gerente, así que se protege igual que el volumen. Devuelve (ok, motivo).
    """
    for p in payload["productos"]:
        v = p.get("volumen")
        if v and v not in texto:
            return False, f"volumen ausente: {p.get('producto')}={v}"
        pct = p.get("porcentaje_presupuesto")
        # "sin meta definida" es prosa, no cifra: no se exige literal (el LLM puede reformularla).
        if pct and pct.endswith("%") and pct not in texto:
            return False, f"porcentaje alterado u omitido: {p.get('producto')}={pct}"
        for clave in ("acumulado_dias_con_reporte", "ritmo_diario", "meta"):
            v = p.get(clave)
            if v and v not in texto:
                return False, f"{clave} ausente o alterado: {p.get('producto')}={v}"
    return True, ""


# D-N6 (2026-07-16): chequeo DIRECCIONAL. D-N5 verifica que las cifras aparezcan literales, pero NO
# que se usen bien: "por debajo de la meta" junto a un 102.7% correcto pasaba el filtro sin más. Ese
# hueco era tolerable con temperature=0 (salida determinista, ya validada en 139); al subir la
# temperatura para ganar variedad, deja de serlo. Solo se aplica cuando la dirección es INEQUÍVOCA
# (todos los productos con meta van al mismo lado): con productos mixtos no se puede atribuir una
# palabra a un producto sin parsear la frase, y un falso positivo costaría una narración buena.
_NEG = ("por debajo", "deficit", "déficit", "rezago", "rezagad", "faltante", "incumpl", "no alcanz")
_POS = ("por encima", "superando", "excedente", "sobrecumpl")


def _cumple_direccion(texto: str, payload: dict) -> tuple[bool, str]:
    dirs = [d for d in (payload.get("direcciones") or {}).values() if d]
    if not dirs:
        return True, ""
    t = texto.lower()
    if all(d == "por encima de la meta" for d in dirs):
        malas = [w for w in _NEG if w in t]
        if malas:
            return False, f"dice {malas} pero todo va por encima de la meta"
    elif all(d == "por debajo de la meta" for d in dirs):
        malas = [w for w in _POS if w in t]
        if malas:
            return False, f"dice {malas} pero todo va por debajo de la meta"
    return True, ""


# Temperatura de la REESCRITURA. Con 0 (greedy) la salida era byte-a-byte idéntica: por eso la
# narración se veía "quemada" aunque la escribiera un LLM. 0.7 da variedad real de forma; el fondo lo
# protegen las salvaguardas (D-N5 cifras literales + D-N6 dirección) y, si alguna salta, el borrador.
_TEMP = 0.7


# D-N7 (2026-07-16): una PROYECCIÓN no puede narrarse como cifra cerrada. La cifra REAL del mes en
# curso es de mes completo (estimado de cierre): AKACIAS "va camino de" 3.720.510, pero lleva
# 1.916.317 reales en 17 días. Si el LLM escribe "cerró con 3.720.510", el lector no tiene forma de
# notar que aún faltan 14 días — y las cifras estarían literales, así que D-N5 no lo atrapa.
_CERRADO = ("cerro con", "produjo", "acumulo", "ha producido", "reporto un volumen")


def _cumple_proyeccion(texto: str, respuesta: dict) -> tuple[bool, str]:
    if not respuesta.get("proyeccion"):
        return True, ""
    from app.features.consulta.normaliza import norm
    t = norm(texto or "").lower()
    malas = [w for w in _CERRADO if w in t]
    if malas:
        return False, f"narra como cerrado {malas} una cifra que es proyección del mes"
    return True, ""


def _cumple_nivel(texto: str, payload: dict) -> tuple[bool, str]:
    """D-A5 bajo temperatura: la prosa DEBE cualificar el nivel ('el Campo APIAY', no 'APIAY').

    Con temperature=0 la regla del prompt bastaba. Con 0.7 el modelo se toma libertades y se come el
    cualificador (verificado con qwen: «Javier, CASTILLA lleva 6.860.389 barriles…»). Sin el nivel,
    APIAY-Campo (269.035 bl, Foco) y APIAY-Activo (577.362 bl, Alineado) son indistinguibles en la
    burbuja: el lector no sabe cuál está viendo. El costo de exigirlo es bajo — al fallar cae al
    borrador, que también es prosa."""
    ec = (payload.get("entidad_cualificada") or "").strip()
    ent = (payload.get("entidad") or "").strip()
    if not ec or ec.upper() == ent.upper():
        return True, ""                      # no hay cualificador que proteger
    if ec.lower() in (texto or "").lower():
        return True, ""
    return False, f"no cualifica el nivel: falta «{ec}»"


def narrar(respuesta: dict, usuario=None) -> dict | None:
    """Devuelve {texto, generado_por, diag}.

    Dos etapas (2026-07-16): (1) Python escribe el borrador en prosa —correcto y completo, con la
    dirección ya resuelta—; (2) el LLM lo REESCRIBE para que suene natural y varíe de forma. Si el
    LLM falla o viola una salvaguarda, `texto` es el BORRADOR (generado_por='borrador'): el usuario
    igual lee prosa, no la tarjeta rígida, y el diag dice por qué. Nunca se muestra peor que antes.
    Devuelve None SOLO cuando NO corresponde narrar: flag off · respuesta no aplicable."""
    s = get_settings()
    if not getattr(s, "consulta_narra_llm", False):
        return None
    if not respuesta or not respuesta.get("aplica") or not respuesta.get("lineas"):
        return None
    if respuesta.get("modo") == "tendencia_filial":
        return None   # filiales: Fase 1 = plantilla determinista (el borrador/prompt asumen presupuesto)
    payload = _payload(respuesta, usuario)
    borrador = _borrador(respuesta, usuario)
    prompt = (_SISTEMA + "\n\nBORRADOR A REESCRIBIR:\n\"\"\"\n" + borrador + "\n\"\"\"\n\n"
              "Cifras que debes copiar EXACTAS (referencia, no las reescribas de otra forma):\n"
              "```json\n" + _json.dumps(payload, ensure_ascii=False) + "\n```")
    diag = {"status": "?", "model": s.consulta_llm_model, "host": s.consulta_ollama_url}

    def _cae(estado, **extra):
        """Fallback al borrador de Python: prosa correcta + el motivo visible en consola."""
        diag["status"] = estado
        diag.update(extra)
        return {"texto": borrador, "generado_por": "borrador", "diag": diag}

    # format=json: en gemma4@139 la generación de texto plano devuelve response vacío; pidiendo un
    # JSON {"narracion": "..."} sí responde (mismo patrón probado del Análisis Ejecutivo).
    try:
        body = _json.dumps({"model": s.consulta_llm_model, "prompt": prompt, "stream": False,
                            "format": "json",
                            "options": {"temperature": _TEMP, "num_predict": 400}}).encode()
        req = _urlreq.Request(s.consulta_ollama_url, data=body,
                              headers={"Content-Type": "application/json"})
        with _urlreq.urlopen(req, timeout=120) as r:
            raw = (_json.load(r).get("response", "") or "").strip()
    except Exception as e:
        return _cae("timeout_o_red:" + type(e).__name__)
    diag["raw"] = raw[:800]
    diag["raw_len"] = len(raw)
    texto = ""
    try:
        obj = _json.loads(raw)
        if isinstance(obj, dict):
            texto = str(obj.get("narracion") or "").strip()
    except Exception as e:
        diag["parse_err"] = type(e).__name__
    if not texto:
        return _cae("vacio")
    ok, motivo = _cumple_regla_numerica(texto, payload)
    if not ok:
        return _cae("regla_numerica", motivo=motivo)   # qué cifra falló → diagnosticable sin adivinar
    ok, motivo = _cumple_direccion(texto, payload)
    if not ok:
        return _cae("direccion", motivo=motivo)        # D-N6: invirtió el sentido
    ok, motivo = _cumple_nivel(texto, payload)
    if not ok:
        return _cae("nivel", motivo=motivo)            # D-A5: se comió "el Campo"/"el Activo"
    ok, motivo = _cumple_proyeccion(texto, respuesta)
    if not ok:
        return _cae("proyeccion", motivo=motivo)       # D-N7: vendió una proyección como cerrada
    diag["status"] = "ok"
    return {"texto": texto, "generado_por": "llm", "diag": diag}
