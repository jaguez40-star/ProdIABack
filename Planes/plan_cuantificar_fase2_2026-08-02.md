# Plan de ejecución — Cuantificar · FASE 2 (dimensión PRODUCTO: gas + blancos, N1+N2, mes, PPTO)

> **Tablas: N/A** — no toca ingesta ni tablas fuente (capa de respuesta sobre cifras ya calculadas).
>
> **Para:** un agente Executor SIN contexto del repo. Rutas absolutas, código de referencia completo,
> decisiones cerradas, criterios verificables (comando → resultado esperado).
>
> **Precede:** Fase 1 completa — 1a+1b (`f157a40`), 1c (`b8c3d46`), 1d+1e (pendiente de commit).
> Fase 1 respondía SOLO **crudo**, N1 (puntual) + N2 (acumulado), grano **mes**, referencia **PPTO**.
> Esta Fase 2 añade **gas** y **blancos** a esos mismos N1+N2/mes/PPTO. Nada más (ver Fuera de alcance).
>
> **⚠️ RESTRICCIÓN DE ENTORNO (regla del usuario):** NO usar el LLM local de dev ni levantar la app en
> dev. En dev: solo `py_compile`, `node --check` y pruebas de DATOS contra Postgres (sin LLM). pytest,
> golden con LLM y navegador → **servidor de pruebas**.
>
> **Fecha:** 2026-08-02 · **Estado:** v2 AUDITADO (§0.2) — listo para aprobación.

---

## 0. Hallazgos de auditoría del código real (§0.2 — verificados 2026-08-02)

| # | Hallazgo (verificado en el código) | Efecto en el plan |
|---|-----------------------------------|-------------------|
| **AF1** | El catálogo `config/variables_cuantificables.yaml` **YA define** `produccion_gas` (`unidad: MSCF`, `granos.mes.confianza: alta`) y `produccion_blancos` (`unidad: bbl`, `granos.mes.confianza: media` + `descargo: "mensual = agregado 'GAS CONVERTIDO MME'"`). `catalogo._validar` solo exige `produccion_crudo`. | **Fase 2 NO edita el catálogo.** `slots.py` LO LEE (aterrizaje catálogo, como promete su docstring): unidad + confianza + descargo salen del YAML. |
| **AF2** | `analisis.api.desempeno` devuelve `por_producto = [{producto, real, ppto, cumplimiento}]` para `["CRUDO","GAS","BLANCOS"]` (`api.py:560-566`). | `ejecutor.ejecutar_n1` YA hace `next(p for p in por_producto if p["producto"]==quiero)`. Basta cambiar `quiero` y quitar el rechazo "solo crudo". CERO cambios a `desempeno`. |
| **AF3 · unidades** | El valor de GAS es **crudo/raw**; el tablero lo muestra como `raw/1e6` con etiqueta **MSCF** (`__cnGasM`, `multitab_shell.js:2140-2144`); CRUDO/BLANCOS como raw + **bbl** (`__cnMilesEC`). Mapa canónico: `_UNIDADES_PRODUCTO = {CRUDO:bbl, BLANCOS:bbl, GAS:MSCF}` (`api.py:648`). | **Coherencia chat↔tablero:** el cuerpo (Python `validador.fmt_valor`) y la tarjeta (frontend) deben formatear GAS con `÷1e6` + "MSCF" y CRUDO/BLANCOS raw + "bbl". Se replica `__cnGasM` EXACTO (`1 decimal si ≥1, si no 2`, coma decimal, sin separador de miles). |
| **AF4 · aviso campos_sin_meta** | El aviso "campo sin meta" de `ejecutor_n1` hardcodea `bbl` y `int(x['real']):,` (`ejecutor.py:71-72`). | El aviso pasa a `fmt_valor(x['real'], producto)` + `unidad` (correcto para gas). |
| **AF5 · blancos honesto** | `produccion_blancos.granos.mes.confianza = media` con `descargo` obligatorio (la regla del catálogo `reglas` exige declarar). | Cuando `producto==blancos`, el ejecutor **añade el descargo del catálogo a `avisos`** (verbatim). Se pinta como ⚠️ en burbuja y tarjeta. |
| **AF6 · default producto** | La regla `reglas` del catálogo dice "DEFAULT producto por VOLUMEN dominante"; implementarlo exige calcular los 3 productos antes de decidir. | **Fuera de Fase 2** (se documenta como diferido). Default determinista = **crudo** cuando el texto no nombra producto (igual que Fase 1). Grounding literal por token normalizado, SIN LLM. |
| **AF7 · blancos N2** | El problema ×4 de BLANCOS es de **grano día** (`HALLAZGO_concepto_multiplicidad.md`); a grano MES el KPI es el agregado autoritativo. N2 = mes. | `niveles.acumulado` de blancos = Σ meses cerrados del KPI mensual (seguro) + el descargo de AF5. El grano día de blancos SIGUE fuera de alcance. |
| **AF8 · resolver intacto** | Los productos NO son entidades; `resolver.py` resuelve entidades por nombre. | **`resolver.py` y `catalogo.py` NO se tocan.** |
| **AF9 · el drill pierde el producto** 🔴 | En Fase 1e el drill N1→N2 reescribe `"acumulado de {entidad}"`. Con productos: si el N1 fue GAS y el usuario dice "acumulado del año", la reescritura **no lleva el producto** → `slots` re-detecta crudo → N2 saldría de CRUDO, no gas. **Incoherencia silenciosa.** | `_CTX` de cuantificar guarda también `producto` (leído de `panel.datos.producto`); el `_continuacion` reescribe `"acumulado de {producto} de {entidad}"` cuando el producto ≠ crudo. Así el drill preserva el producto. |

### 0.1 Segunda ronda de auditoría (adversarial · reformulación 2026-08-02)

| # | Incoherencia detectada (podría romper el pipeline) | Reformulación |
|---|---------------------------------------------------|---------------|
| **AF10 · colisión producto ↔ nombre de entidad** 🔴 | El grounding de producto por TOKEN (`"BLANCO"/"BLANCOS"/"GAS"`) matchea también cuando esa palabra es **parte del nombre de la entidad**. Un campo tipo *«Caño Blanco»* / *«Río Blanco»* → `"cuánto produjo Río Blanco"` daría `producto=blancos` (¡el usuario quería el crudo/total del campo!). Falla silenciosa → cifra equivocada. | `slots._producto(texto, entidad_valor)` **descarta los tokens del nombre de la entidad** antes de buscar el producto. `responder` ya tiene la entidad resuelta (`resuelta["valor"]`) → la pasa a `slots.extraer_slots(texto, entidad_valor=...)`. Sin entidad (golden/runner) no descarta nada (retro-compatible). El producto EXPLÍCITO gana: «cuánto **gas** produjo Río Blanco» → gas. |
| **AF11 · test de Fase 1 queda obsoleto** 🟠 | `test_ejecutar_n2_gas_rechaza_como_n1` (creado en 1e) asume que **gas se rechaza**. En Fase 2 gas YA NO se rechaza por producto → el test sigue en verde pero **por la razón equivocada** (el fake no trae GAS ⇒ sin datos), y su nombre/intención mienten. | El plan **reemplaza** ese test por `test_ejecutar_n2_gas_sin_datos_en_fuente_no_aplica` (misma aserción, intención correcta: gas admitido, pero sin fila GAS en el fake ⇒ no acumula ⇒ no aplica). |
| **AF12 · robustez del golden por datos** 🟡 | Los `resultado: aplica` de gas/blancos dependen de que la entidad SÍ reporte ese producto ese mes; elegir entidades distintas por producto multiplica el riesgo de un golden rojo por DATOS (no por lógica). | Consolidar en entidades **Piedemonte** (reportan gas Y blancos): **CUSIANA/CUPIAGUA**. Se mantiene `CASTILLA/gas = rechazo` (confirmado por `api.py:637`). `nivel_temporal`+`producto` (deterministas) deben acertar 100%; el `resultado` lo ajusta el Executor contra la BD. |

---

## 1. Contexto

Motor Q v2 · Grupo 2 (Cuantificar). Edificio SEPARADO en
`INGESTA/Rep_Prod/backend/app/features/consulta_v2/cuantificar/` (cero imports de `consulta/` v1).
Regla madre: **Python calcula, el LLM solo redacta el intro**. El número es VERBATIM de Python; la
referencia/unidad/grano las decide el **catálogo**, no el LLM. La cifra sale de `analisis.desempeno`
(mismo cálculo del tablero → coherencia chat↔tablero).

## 2. Objetivo

Que "¿cuánto **gas** produjo Cusiana en abril?" y "¿cuántos **blancos** produjo Cupiagua?" (N1) y sus
acumulados del año (N2) respondan con: intro cálido (LLM) + cuerpo VERBATIM (Python, unidad correcta) +
cierre + **panel KPI** con la misma cifra — igual que crudo hoy, con **gas en MSCF** y **blancos con su
descargo de honestidad**. El drill N1→N2 preserva el producto (AF9).

## 3. Prerequisitos

- Fase 1 (1a–1e) presente y verificada estáticamente. Backend en
  `C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend` (`uv run python` desde `backend/`).
- App padre en `C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA` (frontend `static/js/multitab_shell.js`).
- BD dev `daily_report_prod` arriba (solo para las pruebas de datos; NUNCA LLM en dev).
- El catálogo `config/variables_cuantificables.yaml` ya trae gas/blancos (AF1) — **no se toca**.

## 4. Inventario de archivos

Base backend: `C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend\app\features\consulta_v2`
Base app padre: `C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA`

| Acción | Ruta |
|--------|------|
| REEMPLAZAR | `...\consulta_v2\cuantificar\slots.py` — grounding de producto + aterrizaje catálogo (unidad/variable/descargo) |
| REEMPLAZAR | `...\consulta_v2\cuantificar\validador.py` — `fmt_valor(n, producto)` + cuerpo por producto (N1/N2) |
| REEMPLAZAR | `...\consulta_v2\cuantificar\niveles.py` — `acumulado(resuelta, dim_producto, ...)` genérico |
| REEMPLAZAR | `...\consulta_v2\cuantificar\ejecutor.py` — admite gas/blancos; unidad de slots; aviso por producto; descargo |
| EDITAR | `...\consulta_v2\respuesta_cuantificar.py` — **1 línea (AF10):** pasa `entidad_valor=resuelta["valor"]` a `slots.extraer_slots` |
| EDITAR | `...\consulta_v2\maquina_q.py` — `_CTX` guarda `producto`; `_continuacion` preserva producto (AF9) |
| EDITAR | `...\static\js\multitab_shell.js` — `__cnCuantCardHtml` formatea gas con `__cnGasM` |
| EDITAR | `...\consulta_v2\golden\cuantificar_golden.yaml` — +casos gas/blancos + no-reporta (AF12: Piedemonte) |
| EDITAR | `...\consulta_v2\golden\run_golden_cuantificar.py` — verifica también `producto` |
| EDITAR | `...\backend\tests\test_cuantificar.py` — +tests producto/unidad/descargo/drill/AF10; **reemplaza** el test obsoleto (AF11) |
| EDITAR | `...\templates\main.html` — subir cache-buster `?v=` |
| NO TOCAR | `resolver.py`, `catalogo.py`, `config/variables_cuantificables.yaml`, flujo v1 |

> `respuesta_cuantificar.py` cambia SOLO en la llamada a `slots` (AF10). `_panel_datos` ya expone
> `producto`/`unidad`, el cierre ya ramifica por nivel y `responder` ya llama `_ejecutor.ejecutar(...)` —
> eso NO se toca.

## 5. Especificación (código completo de referencia)

### 5.1 — `cuantificar\slots.py` (REEMPLAZO COMPLETO)

Grounding determinista del producto + aterrizaje contra el catálogo (unidad/variable/descargo). Sin LLM.

```python
"""cuantificar/slots.py — aterrizaje de slots contra el catálogo (Motor Q v2, Grupo 2).

Fase 1-2 es 100% DETERMINISTA: no hace falta el LLM para los slots. Los grados de libertad del
usuario son EL MES, N1/N2 (puntual/acumulado) y EL PRODUCTO (crudo/gas/blancos), los tres por
diccionario de palabras normalizado. Lo demás es default del catálogo (referencia=PPTO).

El PRODUCTO se aterriza contra `config/variables_cuantificables.yaml` (catalogo.get()): de ahí sale
la UNIDAD (gas=MSCF, crudo/blancos=bbl) y, si el grano-mes es de confianza MEDIA (blancos), el DESCARGO
de honestidad que el ejecutor añadirá a los avisos. Default de producto = crudo (Fase 2: el "producto
por volumen dominante" queda para una fase posterior — exige calcular los 3 productos antes de decidir).
"""
import re

from app.features.consulta_v2.normaliza import norm
from app.features.consulta_v2.cuantificar import catalogo as _catalogo

# HE7: en forma NORMALIZADA (norm = MAYÚSCULAS sin tildes: "año"->"ANO").
_ACUM_KW = ("ACUMULADO", "ACUMULADA", "EN EL ANO", "EN LO QUE VA", "DEL ANO", "YTD",
            "HASTA AHORA", "EN TOTAL", "TOTAL DEL ANO")

# Grounding de producto por TOKEN (no substring: "GAS" suelto, no dentro de "GASOLINA"/un nombre).
_PROD_TOKENS = {"GAS": "gas", "BLANCOS": "blancos", "BLANCO": "blancos"}

_MESES = ("enero febrero marzo abril mayo junio julio agosto septiembre setiembre "
          "octubre noviembre diciembre").split()


def _nivel_temporal(texto: str) -> str:
    t = norm(texto or "")
    return "N2" if any(k in t for k in _ACUM_KW) else "N1"


def _producto(texto: str, entidad_valor: str | None = None) -> str:
    """crudo (default) | gas | blancos. Token exacto sobre texto normalizado, EXCLUYENDO los tokens
    del nombre de la entidad (AF10: un campo tipo 'CAÑO BLANCO' no debe leerse como producto blancos;
    'cuánto gas produjo Caño Blanco' SÍ da gas porque 'GAS' no es token del nombre)."""
    toks = set(norm(texto or "").split())
    if entidad_valor:
        toks -= set(norm(entidad_valor).split())
    for tok, prod in _PROD_TOKENS.items():
        if tok in toks:
            return prod
    return "crudo"


def _periodo_texto(texto: str) -> str | None:
    """Nombre de mes hallado (para pasárselo a desempeno), o None = mes actual.
    'mes pasado'/'anterior' se pasan literales (desempeno._parse_periodo también los entiende)."""
    t = (texto or "").lower()
    if "pasado" in t or "anterior" in t:
        return "mes pasado"
    mo = next((m for m in _MESES if m in t), None)
    if mo is None:
        return None
    ym = re.search(r"20\d\d", t)                 # año opcional ("abril 2026")
    return f"{mo} {ym.group(0)}" if ym else mo


def extraer_slots(texto: str, entidad_valor: str | None = None) -> dict:
    """Slots aterrizados. `entidad_valor` (nombre canónico ya resuelto) permite excluir sus tokens del
    grounding de producto (AF10). `periodo_texto`=None → desempeno usa el mes por defecto (último).
    `nivel_temporal`=N2 si pide acumulado/año/YTD. `producto`/`unidad`/`descargo` del catálogo."""
    prod = _producto(texto, entidad_valor)
    variable = f"produccion_{prod}"
    pcfg = (_catalogo.get().get("productos") or {}).get(variable, {})
    unidad = pcfg.get("unidad", "bbl")
    mes_cfg = (pcfg.get("granos") or {}).get("mes", {})
    descargo = mes_cfg.get("descargo") if mes_cfg.get("confianza") == "media" else None

    per = _periodo_texto(texto)
    defaults = [f"producto={prod}", "referencia=PPTO"]
    if per is None:
        defaults.append("periodo=mes actual")
    return {
        "variable": variable,
        "producto": prod,
        "unidad": unidad,
        "descargo": descargo,
        "nivel_temporal": _nivel_temporal(texto),
        "referencia": "PPTO",
        "periodo_texto": per,
        "defaults_asumidos": defaults,
    }
```

### 5.2 — `cuantificar\validador.py` (REEMPLAZO COMPLETO)

`fmt_valor(n, producto)` (gas ÷1e6 MSCF mirror de `__cnGasM`; resto bbl es-CO). Cuerpo por producto.

```python
"""cuantificar/validador.py — garantía mecánica de la regla madre + formato del cuerpo (Motor Q v2).

  (a) fmt_valor(n, producto) — literal por producto. CRUDO/BLANCOS: miles es-CO, 0 dec ('10.966.768').
      GAS: ÷1e6 + "MSCF", replicando __cnGasM del frontend (1 decimal si |m|>=1, si no 2; coma decimal,
      SIN separador de miles) → coherencia chat↔tablero. El LLM NUNCA toca esto (D-N5).
  (b) formatear_cuerpo(res) — cuerpo VERBATIM, ramifica por nivel (N1 mes / N2 acumulado) y usa
      fmt_valor+unidad del contrato (producto-aware).
  (c) intro_valido(intro) — el intro es SOLO saludo: sin dígitos ni unidades. Red mecánica de la regla.
"""
import re

_TIENE_DIGITO = re.compile(r"\d")
_UNIDADES = ("barril", "bbl", "mscf", "%", "porcentaje", "presupuesto", "millones", "millón")


def fmt_valor(n, producto) -> str:
    """Literal es-CO por producto. GAS = ÷1e6 'MSCF' (mirror __cnGasM); CRUDO/BLANCOS = bbl raw."""
    try:
        if producto == "gas":
            m = float(n) / 1e6
            d = 1 if abs(m) >= 1 else 2
            return f"{m:.{d}f}".replace(".", ",")
        return f"{float(n):,.0f}".replace(",", ".")
    except Exception:
        return str(n)


def formatear_cuerpo(res: dict) -> str:
    """Cuerpo VERBATIM desde el contrato §7 (dict de ejecutor). Ramifica por nivel (HE6) y por
    producto (Fase 2: fmt_valor + unidad del contrato)."""
    prod = res.get("producto", "crudo")
    unidad = res.get("unidad", "bbl")
    real = fmt_valor(res["resultado"]["valor"], prod)
    pct = f"{res['cumplimiento_pct']}%" if res.get("cumplimiento_pct") is not None else "s/d"
    ppto = fmt_valor(res["referencia_valor"], prod) if res.get("referencia_valor") else None

    if res.get("nivel") == "N2":                       # ACUMULADO (meses cerrados)
        n = res["meses_cerrados"]
        linea = (f"{res['entidad_cualificada']} acumuló {real} {unidad} de {prod} en "
                 f"{res['periodo_label']} ({n} mes{'es' if n != 1 else ''} cerrado"
                 f"{'s' if n != 1 else ''}) — {pct} del presupuesto ({res['estado']}).")
        if ppto:
            linea += f" Presupuesto acumulado: {ppto} {unidad}."
        for a in res.get("avisos", []):
            linea += f" ⚠️ {a}"
        return linea

    # N1: mes puntual. Regla de proyección: si el mes no está completo, DICE 'proyección · N/total días'.
    mes = res["mes"]
    corte = ("mes cerrado" if mes["completo"]
             else f"proyección · {mes['dias_con_data']}/{mes['dias_del_mes']} días")
    linea = (f"{res['entidad_cualificada']} produjo {real} {unidad} de {prod} en {mes['nombre']} "
             f"{mes['anio']} — {pct} del presupuesto ({res['estado']}) · {corte}.")
    if ppto:
        linea += f" Presupuesto del mes: {ppto} {unidad}."
    for a in res.get("avisos", []):
        linea += f" ⚠️ {a}"
    return linea


def intro_valido(intro: str) -> bool:
    """El intro es SOLO saludo: sin dígitos (D-N5) y sin unidades/lexicón de presupuesto."""
    if not intro:
        return False
    low = intro.lower()
    if _TIENE_DIGITO.search(intro):
        return False
    if any(u in low for u in _UNIDADES):
        return False
    return True
```

### 5.3 — `cuantificar\niveles.py` (REEMPLAZO COMPLETO)

Generaliza `acumulado_crudo` → `acumulado(resuelta, dim_producto, ...)`.

```python
"""cuantificar/niveles.py — N2 acumulado (Σ REAL de meses CERRADOS del año) para cualquier producto.
Reusa analisis.desempeno por mes → coherencia con el tablero (mismo patrón que ejecutor: 4 args
explícitos, sin factorizar un `_desempeno_core`).

HE4: el mes EN CURSO es PROYECCIÓN (T-1) — no se suma; se declara aparte (`en_curso`).
AF7: BLANCOS a grano MES es el agregado autoritativo (el ×4 es de grano DÍA, fuera de alcance)."""
from app.features.analisis.api import desempeno as _desempeno_ep

_MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre"]


def acumulado(resuelta: dict, dim_producto: str, _desempeno_fn=None) -> dict:
    """dim_producto ∈ {"CRUDO","GAS","BLANCOS"} (nombre del producto en por_producto). Devuelve
    {aplica:True, real, ppto, meses:[nombres cerrados], en_curso:{nombre,real}|None, anio} o
    {aplica:False, texto}. Solo rama A; la rama B la rechaza el ejecutor."""
    fn = _desempeno_fn or _desempeno_ep
    d0 = fn(entidad=resuelta["valor"], segmento="ecp", nivel=resuelta.get("nivel"), periodo=None)
    if not d0.get("encontrada") or d0.get("sin_datos") or d0.get("sin_cierre"):
        return {"aplica": False, "texto": f"No tengo datos de producción para «{resuelta['valor']}»."}
    anio, ultimo = d0["mes"]["anio"], d0["mes"]["mes"]
    total_real = total_ppto = 0.0
    meses, en_curso = [], None
    for m in range(1, ultimo + 1):
        dm = fn(entidad=resuelta["valor"], segmento="ecp", nivel=resuelta.get("nivel"), periodo=_MESES[m])
        if not dm.get("encontrada") or dm.get("sin_datos") or dm.get("sin_cierre"):
            continue
        fila = next((p for p in dm["por_producto"] if p["producto"] == dim_producto), None)
        if not fila or (fila["real"] == 0 and fila["ppto"] == 0):
            continue
        if dm["mes"]["completo"]:
            total_real += fila["real"]
            total_ppto += (fila["ppto"] or 0)
            meses.append(_MESES[m])
        else:
            en_curso = {"nombre": _MESES[m], "real": fila["real"]}   # proyección; NO se suma (HE4)
    if not meses:
        return {"aplica": False,
                "texto": f"«{resuelta['valor']}» aún no tiene meses cerrados en {anio} para acumular."}
    return {"aplica": True, "real": total_real, "ppto": total_ppto, "meses": meses,
            "en_curso": en_curso, "anio": anio}
```

### 5.4 — `cuantificar\ejecutor.py` (REEMPLAZO COMPLETO)

Admite gas/blancos; unidad de slots; aviso por producto (AF4); descargo del catálogo (AF5); N2 usa `niveles.acumulado`.

```python
"""cuantificar/ejecutor.py — la cifra REAL vs PPTO (Motor Q v2, Grupo 2, Fase 1-2).

Fase 1: solo crudo. Fase 2: + gas y blancos (N1 puntual + N2 acumulado, grano mes, referencia PPTO).

🔑 COHERENCIA chat↔tablero: reusa `analisis.api.desempeno` con los 4 args explícitos (patrón probado
por v1 desde 2026-07-15). La UNIDAD y el DESCARGO de honestidad los aterriza `slots` desde el catálogo
(variables_cuantificables.yaml) — el ejecutor NO decide unidades; solo arma el contrato §7.

Frontera: NO SQL propio, NO LLM. La prosa (intro) es de 1c; el formato del número es de validador."""
from app.features.analisis.api import desempeno as _desempeno_ep, _estado
from app.features.consulta_v2.cuantificar import niveles as _niveles
from app.features.consulta_v2.cuantificar.validador import fmt_valor as _fmt_valor

_ESTADO_LABEL = {"ok": "Alineado", "warn": "Rezagado", "alert": "Foco", "": "sin meta"}
_NIVEL_TEXTO = {"campo": "el Campo", "activo": "el Activo", "gerencia": "la Gerencia",
                "vicepresidencia": "la Vicepresidencia", "fuente": "la fuente", "pozo": "la fuente",
                "operador": "la operación de"}
_PROD_MAP = {"crudo": "CRUDO", "gas": "GAS", "blancos": "BLANCOS"}


def ejecutar(resuelta: dict, slots: dict, _desempeno_fn=None) -> dict:
    """Despacho por `slots["nivel_temporal"]`. N1 = puntual (mes); N2 = acumulado (meses cerrados)."""
    if slots.get("nivel_temporal") == "N2":
        return ejecutar_n2(resuelta, slots, _desempeno_fn=_desempeno_fn)
    return ejecutar_n1(resuelta, slots, _desempeno_fn=_desempeno_fn)


def _rechazo_comun(resuelta, slots):
    """Validaciones compartidas N1/N2. Devuelve {aplica:False, texto} o None si pasa."""
    if resuelta.get("rama") == "B":
        return {"aplica": False,
                "texto": f"«{resuelta['valor']}» es una filial; su cuantificación llega en una próxima fase."}
    if slots.get("producto") not in _PROD_MAP:
        return {"aplica": False,
                "texto": f"No sé cuantificar «{slots.get('producto')}»; puedo con crudo, gas o blancos."}
    return None


def ejecutar_n1(resuelta: dict, slots: dict, _desempeno_fn=None) -> dict:
    """Devuelve el contrato §7 (dict) o {aplica:False, texto}. Fase 2: crudo/gas/blancos, rama A."""
    fn = _desempeno_fn or _desempeno_ep
    rech = _rechazo_comun(resuelta, slots)
    if rech:
        return rech
    producto = slots["producto"]
    unidad = slots.get("unidad", "bbl")
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

    real, ppto, cumpl = fila["real"], fila.get("ppto"), fila.get("cumplimiento")
    estado = _ESTADO_LABEL.get(_estado(cumpl), "")
    nivel = resuelta.get("nivel")
    etiqueta = _NIVEL_TEXTO.get(nivel, "")
    proyeccion = (not mes["completo"]) and bool(mes["dias_con_data"])

    avisos = []
    if slots.get("descargo"):                                   # AF5: blancos-mes = confianza media
        avisos.append(slots["descargo"])
    for x in (d.get("campos_sin_meta") or []):                  # AF4: aviso por producto/unidad
        if x["producto"] == quiero:
            avisos.append(f"El campo {x['campo']} produce sin meta asignada "
                          f"({_fmt_valor(x['real'], producto)} {unidad} fuera del presupuesto).")

    return {
        "aplica": True, "grupo": "cuantificar", "variable": slots.get("variable", "produccion_crudo"),
        "nivel": "N1",
        "entidad": {"nombre": resuelta["valor"], "nivel": nivel, "fue_asumida": False},
        "entidad_cualificada": f"{etiqueta} {resuelta['valor']}".strip(),
        "producto": producto, "referencia": "PPTO", "unidad": unidad, "grano": "mes",
        "universo": "reporte_diario",
        "huella": {
            "registros": mes.get("dias_con_data"),
            "rango_disponible": [f"{mes['anio']}-{mes['mes']:02d}-01",
                                 f"{mes['anio']}-{mes['mes']:02d}-{mes['dias_del_mes']:02d}"],
            "dias_del_mes": mes.get("dias_del_mes"), "es_proyeccion": proyeccion,
        },
        "resultado": {"valor": real}, "referencia_valor": ppto,
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

    ac = _niveles.acumulado(resuelta, _PROD_MAP[producto], _desempeno_fn=_desempeno_fn)
    if not ac.get("aplica"):
        return {"aplica": False, "texto": ac["texto"]}

    real, ppto = ac["real"], ac["ppto"]
    cumpl = round(real / ppto * 100.0, 1) if ppto else None
    estado = _ESTADO_LABEL.get(_estado(cumpl), "")
    nivel_ent = resuelta.get("nivel")
    etiqueta = _NIVEL_TEXTO.get(nivel_ent, "")
    ms = ac["meses"]
    periodo_label = (ms[0] if len(ms) == 1 else f"{ms[0]}–{ms[-1]}") + f" {ac['anio']}"

    avisos = []
    if slots.get("descargo"):
        avisos.append(slots["descargo"])
    if ac.get("en_curso"):
        avisos.append(f"El mes de {ac['en_curso']['nombre']} sigue en curso; su proyección NO está "
                      f"incluida en el acumulado.")

    return {
        "aplica": True, "grupo": "cuantificar", "variable": slots.get("variable", "produccion_crudo"),
        "nivel": "N2",
        "entidad": {"nombre": resuelta["valor"], "nivel": nivel_ent, "fue_asumida": False},
        "entidad_cualificada": f"{etiqueta} {resuelta['valor']}".strip(),
        "producto": producto, "referencia": "PPTO", "unidad": unidad, "grano": "mes",
        "universo": "reporte_diario",
        "resultado": {"valor": real}, "referencia_valor": ppto,
        "cumplimiento_pct": cumpl, "estado": estado,
        "periodo_label": periodo_label, "meses_cerrados": len(ms), "en_curso": ac.get("en_curso"),
        "huella": {"registros": len(ms), "es_proyeccion": False},
        "defaults_asumidos": slots.get("defaults_asumidos", []), "avisos": avisos,
        "zoom": resuelta.get("zoom", []),
    }
```

> ⚠️ Nota (AF4): `_campos_sin_meta` puede ser crudo-céntrico; si no devuelve filas para gas/blancos,
> el aviso simplemente no aparece (inofensivo). Verificar en servidor; no bloquea.

### 5.4b — `respuesta_cuantificar.py` (1 LÍNEA — AF10: pasar la entidad a slots)

En `responder`, localizar (`respuesta_cuantificar.py:89`):

```python
    res = _ejecutor.ejecutar(resuelta, _slots.extraer_slots(texto))
```
y reemplazar por:
```python
    # AF10: la entidad YA está resuelta (D-D5) → se le pasa a slots para que su nombre no contamine
    # el grounding de producto (p.ej. un campo 'CAÑO BLANCO' no debe leerse como producto blancos).
    res = _ejecutor.ejecutar(resuelta, _slots.extraer_slots(texto, entidad_valor=resuelta["valor"]))
```
> Nada más cambia en este archivo. En este punto `resuelta` ya pasó los `return` de None/ambiguo, así
> que `resuelta["valor"]` siempre existe.

### 5.5 — `maquina_q.py` (2 EDICIONES — AF9: el drill preserva el producto)

**Edición A** — en `_continuacion` (la rama cuantificar, `maquina_q.py:58-60`). Reemplazar EXACTAMENTE:

```python
    if ctx.get("grupo") == "cuantificar" and \
       (any(k in t for k in ("ACUMULADO", "EN EL ANO", "DEL ANO", "EN TOTAL", "YTD")) or t in _AFIRM):
        return f"acumulado de {ctx['entidad']}"
```
por:
```python
    if ctx.get("grupo") == "cuantificar" and \
       (any(k in t for k in ("ACUMULADO", "EN EL ANO", "DEL ANO", "EN TOTAL", "YTD")) or t in _AFIRM):
        # AF9: preservar el producto del N1 (si no, "acumulado" tras un N1 de gas volvería a crudo).
        prod = ctx.get("producto", "crudo")
        pieza = "" if prod == "crudo" else f"{prod} de "
        return f"acumulado de {pieza}{ctx['entidad']}"
```

**Edición B** — en `clasificar`, el bloque que puebla `_CTX` para cuantificar
(`maquina_q.py:290-291`). Reemplazar EXACTAMENTE:

```python
    elif res["grupo"] == "cuantificar" and log and conversation_id and res.get("entidad_cruda"):
        _CTX[conversation_id] = {"grupo": "cuantificar", "entidad": res["entidad_cruda"]}
```
por:
```python
    elif res["grupo"] == "cuantificar" and log and conversation_id and res.get("entidad_cruda"):
        # AF9: guardar también el producto respondido (del panel) para que el drill N1->N2 lo preserve.
        prod = ((res.get("panel") or {}).get("datos") or {}).get("producto", "crudo")
        _CTX[conversation_id] = {"grupo": "cuantificar", "entidad": res["entidad_cruda"], "producto": prod}
```

> El comentario del `_CTX` (`maquina_q.py:33`) puede actualizarse a
> `# -> cuantificar: {grupo, entidad, producto}` (opcional, no funcional).

### 5.6 — `static\js\multitab_shell.js` (1 EDICIÓN — tarjeta gas en MSCF)

En `__cnCuantCardHtml` (`multitab_shell.js:2359`). Reemplazar el bloque de formateo/valores. Localizar:

```javascript
    var pct = (dat.cumplimiento_pct != null) ? dat.cumplimiento_pct : 0;
    var unidad = dat.unidad || "bbl";
```
y añadir JUSTO DEBAJO:
```javascript
    // Fase 2: GAS se muestra en MSCF (÷1e6, mirror del panel __cnGasM); CRUDO/BLANCOS raw + bbl.
    var esGas = (dat.producto === "gas");
    var fmtV = esGas ? function (v) { return __cnGasM(v); }
                     : function (v) { return __cnMilesEC(Math.round(v)); };
```
Luego, en el MISMO cuerpo del return, reemplazar las 2 apariciones de valor:

- `'<div class="cp-p50__realval">' + __cnMilesEC(dat.real) + ' <span class="cp-mes__kpi-unit">' + unidad + '</span></div>' +`
  → `'<div class="cp-p50__realval">' + fmtV(dat.real) + ' <span class="cp-mes__kpi-unit">' + unidad + '</span></div>' +`
- `'...Presupuesto...' + __cnMilesEC(dat.ppto) + ' ' + unidad + '...'`
  → `'...Presupuesto...' + fmtV(dat.ppto) + ' ' + unidad + '...'`

(El resto de la tarjeta — anillo, chip, corte, avisos — NO cambia. `__cnGasM` ya existe en `:2140`.)

### 5.7 — `golden\cuantificar_golden.yaml` (AÑADIR casos al final)

```yaml

# ---- Fase 2: GAS (2) — Cusiana/Cupiagua son focos de gas (Piedemonte) ----
- pregunta: "¿cuánto gas produjo Cusiana en abril?"
  entidad: "CUSIANA"
  nivel_temporal: N1
  producto: gas
  resultado: aplica
- pregunta: "¿acumulado de gas de Cusiana?"
  entidad: "CUSIANA"
  nivel_temporal: N2
  producto: gas
  resultado: aplica

# ---- Fase 2: BLANCOS (2) — AF12: misma familia Piedemonte (Cupiagua reporta gas Y blancos) ----
- pregunta: "¿cuántos blancos produjo Cupiagua en abril?"
  entidad: "CUPIAGUA"
  nivel_temporal: N1
  producto: blancos
  resultado: aplica
- pregunta: "¿cuál es el acumulado de blancos de Cupiagua?"
  entidad: "CUPIAGUA"
  nivel_temporal: N2
  producto: blancos
  resultado: aplica

# ---- Fase 2: producto que la entidad NO reporta (Castilla no produce gas — api.py:637) ----
- pregunta: "¿cuánto gas produjo Castilla en abril?"
  entidad: "CASTILLA"
  nivel_temporal: N1
  producto: gas
  resultado: rechazo_otro
```

> ⚠️ Los `resultado: aplica`/`rechazo_otro` dependen de la BD. AF12: Cusiana/Cupiagua (Piedemonte)
> reportan gas Y blancos → menos riesgo de rojo por datos; Castilla/gas = "no reporta" está CONFIRMADO
> por el comentario de `api.py:637`. Si en el servidor una entidad no calza, el Executor **solo** ajusta
> el `entidad`/`resultado`; el `nivel_temporal`+`producto` (deterministas) SÍ deben pasar siempre.

### 5.8 — `golden\run_golden_cuantificar.py` (1 EDICIÓN — verificar producto)

En `main()`, tras `nivel_ok = ...`, añadir la verificación de producto y sumarla al acierto:

```python
        slots = _slots.extraer_slots(c["pregunta"])
        nivel_ok = slots["nivel_temporal"] == c["nivel_temporal"]
        prod_ok = slots["producto"] == c.get("producto", "crudo")   # <-- NUEVO (default crudo)
```
y cambiar:
```python
        acierto = nivel_ok and resultado_ok
```
por:
```python
        acierto = nivel_ok and prod_ok and resultado_ok
```
y en la traza del fallo, incluir el producto:
```python
            extra = f"  -> nivel={slots['nivel_temporal']} producto={slots['producto']} resultado={resultado}"
```

### 5.9 — `tests\test_cuantificar.py` (AÑADIR al final)

```python

# ================= Fase 2: producto (gas/blancos) =================

def test_slots_producto_gas():
    assert _slots.extraer_slots("cuanto gas produjo Cusiana")["producto"] == "gas"


def test_slots_producto_blancos():
    assert _slots.extraer_slots("cuantos blancos produjo Cupiagua")["producto"] == "blancos"


def test_slots_producto_crudo_default():
    assert _slots.extraer_slots("cuanto produjo Rubiales")["producto"] == "crudo"


def test_slots_unidad_gas_mscf():
    s = _slots.extraer_slots("cuanto gas produjo Cusiana")
    assert s["unidad"] == "MSCF" and s["variable"] == "produccion_gas"


def test_slots_unidad_crudo_bbl():
    assert _slots.extraer_slots("cuanto produjo Rubiales")["unidad"] == "bbl"


def test_slots_blancos_descargo_media():
    # confianza media en el catálogo -> hay descargo de honestidad
    assert _slots.extraer_slots("cuantos blancos produjo Cupiagua")["descargo"]


def test_slots_crudo_sin_descargo():
    assert _slots.extraer_slots("cuanto produjo Rubiales")["descargo"] is None


# ---- validador: formato por producto ----

def test_fmt_valor_gas_mscf():
    # __cnGasM: 82_000_000/1e6 = 82.0 -> "82,0" (1 decimal si |m|>=1)
    assert _validador.fmt_valor(82_000_000.0, "gas") == "82,0"


def test_fmt_valor_gas_menor_a_uno():
    # 500_000/1e6 = 0.5 -> "0,50" (2 decimales si |m|<1)
    assert _validador.fmt_valor(500_000.0, "gas") == "0,50"


def test_fmt_valor_crudo_bbl():
    assert _validador.fmt_valor(10_966_768.0, "crudo") == "10.966.768"


def test_formatear_cuerpo_gas_dice_mscf():
    res = {"nivel": "N1", "producto": "gas", "unidad": "MSCF",
           "resultado": {"valor": 82_000_000.0}, "referencia_valor": 80_000_000.0,
           "cumplimiento_pct": 102.5, "estado": "Alineado",
           "mes": {"nombre": "Abril", "anio": 2026, "completo": True,
                   "dias_con_data": 30, "dias_del_mes": 30}, "avisos": []}
    cuerpo = _validador.formatear_cuerpo(res)
    assert "MSCF" in cuerpo and "82,0" in cuerpo and "de gas" in cuerpo


# ---- ejecutor: gas/blancos con _desempeno_fn FAKE (sin BD, sin LLM) ----

def _fake_gas_cerrado(entidad="X", segmento="ecp", nivel="campo", periodo=None):
    return {"encontrada": True, "sin_datos": False, "sin_cierre": False,
            "mes": {"anio": 2026, "mes": 4, "nombre": "Abril", "completo": True,
                    "dias_con_data": 30, "dias_del_mes": 30},
            "por_producto": [{"producto": "GAS", "real": 82_000_000.0, "ppto": 80_000_000.0,
                              "cumplimiento": 102.5}],
            "campos_sin_meta": []}


def _fake_blancos_cerrado(entidad="X", segmento="ecp", nivel="campo", periodo=None):
    return {"encontrada": True, "sin_datos": False, "sin_cierre": False,
            "mes": {"anio": 2026, "mes": 4, "nombre": "Abril", "completo": True,
                    "dias_con_data": 30, "dias_del_mes": 30},
            "por_producto": [{"producto": "BLANCOS", "real": 500_000.0, "ppto": 600_000.0,
                              "cumplimiento": 83.3}],
            "campos_sin_meta": []}


def test_ejecutar_n1_gas_unidad_y_valor_raw():
    resuelta = {"nivel": "campo", "rama": "A", "valor": "CUSIANA", "zoom": []}
    slots = _slots.extraer_slots("cuanto gas produjo Cusiana en abril")
    res = _ejecutor.ejecutar_n1(resuelta, slots, _desempeno_fn=_fake_gas_cerrado)
    assert res["aplica"] is True and res["producto"] == "gas" and res["unidad"] == "MSCF"
    assert res["resultado"]["valor"] == 82_000_000.0   # RAW; el ÷1e6 es SOLO de formato


def test_ejecutar_n2_gas_suma_meses_cerrados():
    resuelta = {"nivel": "campo", "rama": "A", "valor": "CUSIANA", "zoom": []}
    slots = _slots.extraer_slots("acumulado de gas de Cusiana")
    assert slots["nivel_temporal"] == "N2" and slots["producto"] == "gas"
    res = _ejecutor.ejecutar(resuelta, slots, _desempeno_fn=_fake_gas_cerrado)
    assert res["nivel"] == "N2" and res["producto"] == "gas"
    assert res["meses_cerrados"] == 4 and res["resultado"]["valor"] == 82_000_000.0 * 4


def test_ejecutar_n1_blancos_tiene_descargo():
    resuelta = {"nivel": "campo", "rama": "A", "valor": "CUPIAGUA", "zoom": []}
    slots = _slots.extraer_slots("cuantos blancos produjo Cupiagua en abril")
    res = _ejecutor.ejecutar_n1(resuelta, slots, _desempeno_fn=_fake_blancos_cerrado)
    assert res["producto"] == "blancos" and res["unidad"] == "bbl"
    assert any("MME" in a or "mensual" in a.lower() for a in res["avisos"])   # descargo AF5


# ---- drill AF9: el producto se preserva N1 -> N2 ----

def test_continuacion_cuantificar_preserva_gas():
    ctx = {"grupo": "cuantificar", "entidad": "CUSIANA", "producto": "gas"}
    assert _continuacion("acumulado del año", ctx) == "acumulado de gas de CUSIANA"


def test_continuacion_cuantificar_crudo_sin_pieza():
    ctx = {"grupo": "cuantificar", "entidad": "RUBIALES", "producto": "crudo"}
    assert _continuacion("si", ctx) == "acumulado de RUBIALES"


# ---- AF10: el nombre de la entidad NO contamina el grounding de producto ----

def test_slots_producto_no_colisiona_con_nombre_entidad():
    # entidad "CAÑO BLANCO" -> el token BLANCO se descarta -> producto crudo (default)
    s = _slots.extraer_slots("cuanto produjo Caño Blanco", entidad_valor="CAÑO BLANCO")
    assert s["producto"] == "crudo"


def test_slots_producto_explicito_gana_pese_al_nombre():
    # el usuario nombra gas explícito -> gas, aunque la entidad tenga 'BLANCO'
    s = _slots.extraer_slots("cuanto gas produjo Caño Blanco", entidad_valor="CAÑO BLANCO")
    assert s["producto"] == "gas"


def test_slots_producto_sin_entidad_detecta_token():
    # sin entidad (golden/runner) el token se detecta normal (retro-compatible)
    assert _slots.extraer_slots("cuantos blancos produjo Cupiagua")["producto"] == "blancos"
```

> **Requisitos sobre `test_cuantificar.py`:**
> 1. Añadir al encabezado `from app.features.consulta_v2.cuantificar import validador as _validador`
>    (ya importa ejecutor/resolver/slots + `_continuacion`).
> 2. **AF11 — reemplazar el test obsoleto de Fase 1e.** ELIMINAR `test_ejecutar_n2_gas_rechaza_como_n1`
>    (asumía que gas se rechazaba) y AÑADIR en su lugar:
> ```python
> def test_ejecutar_n2_gas_sin_datos_en_fuente_no_aplica():
>     # Fase 2: gas YA NO se rechaza por producto; si el fake no trae fila GAS, N2 no acumula -> no aplica.
>     resuelta = {"nivel": "campo", "rama": "A", "valor": "RUBIALES", "zoom": []}
>     slots = _slots.extraer_slots("acumulado de gas de Rubiales")
>     assert slots["producto"] == "gas"
>     res = _ejecutor.ejecutar(resuelta, slots, _desempeno_fn=_fake_mes_cerrado)  # el fake solo trae CRUDO
>     assert res["aplica"] is False
> ```

### 5.10 — `templates\main.html` (cache-buster)

Subir el `?v=` del `<script ... multitab_shell.js>` (`main.html:82`), p.ej. `?v=20260802h1`.

## 6. Orden de ejecución

1. `slots.py` (5.1) → `validador.py` (5.2) → `niveles.py` (5.3) → `ejecutor.py` (5.4) → `respuesta_cuantificar.py` (5.4b, 1 línea AF10). **`py_compile` de los 5.**
2. `maquina_q.py` (5.5, 2 ediciones). `py_compile`.
3. Frontend (5.6) + `main.html` (5.10). `node --check multitab_shell.js`.
4. golden (5.7) + runner (5.8) + tests (5.9, incl. **borrar** el test obsoleto AF11 y añadir su reemplazo).
5. Correr la **COMPUERTA** (§8). Reportar y ESPERAR aprobación.

## 7. Reglas no negociables

1. **El número es VERBATIM de Python** (N1 y N2, los 3 productos). El LLM solo redacta el intro (1c).
2. **Unidades del catálogo:** GAS=MSCF (÷1e6 para mostrar), CRUDO/BLANCOS=bbl (raw). La `slots` las
   aterriza; el ejecutor NO decide unidades.
3. **BLANCOS declara su descargo** (AF5, confianza media) — siempre, verbatim del catálogo.
4. **N2 solo suma meses CERRADOS** (HE4); el mes en curso se declara, no se suma.
5. **Coherencia:** todo sale de `analisis.desempeno` (mismo cálculo del tablero). NO SQL propio.
6. **Edificio separado:** cero imports de `consulta/` (v1). `niveles.py` importa `analisis` (permitido);
   `ejecutor.py` importa `validador.fmt_valor` (mismo edificio, sin ciclo).
7. **NO tocar:** `resolver.py`, `catalogo.py`, `variables_cuantificables.yaml`, el flujo v1.
8. **NO usar el LLM local de dev** para pruebas; runtime/navegador/pytest → servidor de pruebas.

## 8. Validaciones (comando → resultado; TODAS sin LLM; en dev salvo las marcadas «servidor»)

- **V1** (estático) `py_compile` de slots/validador/niveles/ejecutor/maquina_q → OK.
- **V2** (estático) `node --check static/js/multitab_shell.js` → sin errores.
- **V3** (datos, dev, SIN LLM) desde `backend/`, con `_desempeno_fn` NO — usar la BD:
  `slots.extraer_slots("cuanto gas produjo Cusiana")` → `producto=="gas"`, `unidad=="MSCF"`,
  `variable=="produccion_gas"`; `extraer_slots("cuantos blancos produjo Cupiagua")["descargo"]` no vacío;
  `extraer_slots("cuanto produjo Rubiales")` → `producto=="crudo"`, `descargo is None`.
- **V3b** (estático, AF10) `slots.extraer_slots("cuanto produjo Caño Blanco", entidad_valor="CAÑO BLANCO")["producto"]=="crudo"`
  (el nombre no contamina) y `slots.extraer_slots("cuantos blancos produjo Cusiana")["producto"]=="blancos"`
  (sin entidad, token normal).
- **V4** (datos, dev, SIN LLM) `validador.fmt_valor(82_000_000,"gas")=="82,0"` y
  `fmt_valor(10_966_768,"crudo")=="10.966.768"`.
- **V5** (servidor) `run_golden_cuantificar.py` → EXACTITUD ≥90% (gate); `nivel_temporal`+`producto`
  aciertan en el 100% de los casos (son deterministas); ajustar entidades gas/blancos si la BD lo pide.
- **V6** (servidor) pytest `tests/test_cuantificar.py` verde (los nuevos + los de Fase 1).
- **V7** (servidor, navegador) Motor v2 → "cuánto gas produjo Cusiana en abril" → burbuja **en MSCF** +
  tarjeta KPI en MSCF; "cuántos blancos produjo Cupiagua" → **con ⚠️ descargo**; drill: tras el N1 de
  gas, "acumulado del año" → N2 **de gas** (no crudo). Crudo sin regresión.

## 9. Fuera de alcance (NO hacer)

- **N3 (serie mensual)** y **N4 (variación mes a mes)** — Fase 3.
- **Referencias ≠ PPTO** (REAL, OPERATIVO, CONTABLE, P50, promedio_anio) — Fase 3+.
- **Grano DÍA** (incluye blancos-día, irreconciliable) y **periodos año/trimestre/semana**.
- **Agua**, **derivadas** (gap/cumplimiento como variables propias), **conteos/jerarquía**,
  **robustez especialista** (ebitda/breakeven/pozos), **diferidas**.
- **Default de producto por volumen dominante** (AF6) — queda para una fase posterior; Fase 2 usa
  default = crudo cuando el texto no nombra producto.
- **Editar el catálogo** `variables_cuantificables.yaml` (ya trae gas/blancos — AF1) o `resolver.py`.
```
