# Plan de ejecución — Cuantificar · FASE 4 (referencias ≠ PPTO en N1)

> **Tablas: N/A** — no toca ingesta ni tablas fuente (capa de respuesta sobre cifras ya calculadas).
>
> **Para:** un agente Executor SIN contexto del repo. Rutas absolutas, código de referencia completo,
> decisiones cerradas, criterios verificables (comando → resultado esperado).
>
> **Precede:** Fases 1-3 (crudo/gas/blancos · N1-N4 · mes · **PPTO**). Esta Fase 4 añade el **slot de
> referencia** al **dato puntual de un mes (N1)**: PPTO (default), **OPERATIVO**, **CONTABLE**,
> **promedio_anio**, y **P50 (rechazo honesto)**. N2/N3/N4 siguen contra PPTO (ver Fuera de alcance).
>
> **⚠️ RESTRICCIÓN DE ENTORNO (regla del usuario):** NO usar el LLM local de dev ni levantar la app en
> dev. En dev: solo `py_compile`, `node --check` y pruebas de DATOS contra Postgres (sin LLM). pytest,
> golden y navegador → **servidor de pruebas**.
>
> **Fecha:** 2026-08-02 · **Estado:** v2 AUDITADO (§0.2) — listo para aprobación.

---

## 0. Hallazgos de auditoría del código real (§0.2 — verificados 2026-08-02)

| # | Hallazgo (verificado) | Efecto en el plan |
|---|----------------------|-------------------|
| **AF-4.1** | La query de KPIs de `desempeno` filtra `es.nombre IN ('REAL','PPTO')` (`api.py:537`). **NO expone OPERATIVO/CONTABLE.** | Para esas dos referencias hace falta leer otro escenario del mismo `fact_produccion_mes_ecp`. |
| **AF-4.2 · NO extender `desempeno`** 🔴 | Añadir OPERATIVO/CONTABLE al `IN` de esa query **cambiaría `sin_cierre`** (`api.py:568` = `not any(kpi.get(p) ...)`): un producto con fila OPERATIVO pero sin REAL/PPTO crearía `kpi[p]` y **volvería `sin_cierre` False** cuando debía ser True → regresión del tablero. | **NO se toca `desempeno`.** Se añade un helper **nuevo y read-only `escenario_mes`** en `analisis/api.py` (reusa `_ambito`), que la Fase 4 llama solo cuando la referencia es OPERATIVO/CONTABLE. `desempeno` queda byte-idéntico (cero riesgo tablero). |
| **AF-4.3** | `promedio_anio` YA está calculado: `desempeno.ritmo_mensual.promedio_mes[PRODUCTO]` (media de meses cerrados, Fase 3). | La referencia `promedio_anio` sale del MISMO `desempeno` que ya llama N1 → cero query extra. |
| **AF-4.4 · P50 = rechazo honesto** | P50 vive en `president()` (`api.py:2513`, hoja `REPORTE_PRESIDENT`, **kbpe**, ECP-global). El catálogo (`variables_cuantificables.yaml → referencias.P50`) dice: "SOLO ECP-global; NO reconcilia con el fact (~5,8×); no existe a campo/activo/gerencia". En cuantificar no hay entidad "ECP-global" resoluble. | "vs P50" ⇒ **rechazo con explicación** (no se integra `president()` en Fase 4). Ofrece PPTO/operativo/contable/promedio como alternativas. |
| **AF-4.5 · CONTABLE solo cerrado** | El catálogo: "CONTABLE: cierre contable; SOLO meses cerrados". En el mes en curso puede no existir. | Si el valor de la referencia es None/0, la respuesta **degrada honesta**: muestra lo producido y avisa "No hay {referencia} para {mes}". |
| **AF-4.6 · nombres de escenario** | La query usa literales `'REAL'`/`'PPTO'`. Los nombres exactos de OPERATIVO/CONTABLE en `core.dim_escenario` deben confirmarse. | El Executor confirma en dev (`SELECT DISTINCT nombre FROM core.dim_escenario`) y ajusta las constantes si difieren (data-check, sin LLM). |
| **AF-4.7 · solo N1** | La referencia por punto es natural en N1. N2 (acumulado vs acumulado) exige sumar el escenario por mes; N3/N4 son trayectorias. | Fase 4 = **N1**. `ejecutar_n2` **avisa** si la referencia ≠ PPTO ("alternas solo en el dato de un mes; el acumulado va vs PPTO"). N3/N4 la ignoran. Documentado. |
| **AF-4.8 · recomputar cumplimiento** | `desempeno` da `fila["cumplimiento"] = real/ppto`. Para referencias ≠ PPTO ese % está mal. | N1 **recalcula** `cumplimiento = real/referencia_valor` para TODA referencia (para PPTO da idéntico → sin regresión). |
| **AF-4.9 · colisión "del año"** | `_nivel_temporal` marca N2 si ve `DEL ANO` (`_ACUM_KW`). "promedio **del año**" lo dispararía. | `extraer_slots`: si `referencia == promedio_anio`, **fuerza `nivel=N1`** ("promedio del año" es la REFERENCIA, no un acumulado). |

### 0.1 Segunda ronda de auditoría (adversarial · reformulación 2026-08-02)

| # | Incoherencia detectada (podría romper el pipeline / engañar) | Reformulación |
|---|-------------------------------------------------------------|---------------|
| **AF-4.10 · el chip de estado engaña en promedio_anio** 🟠 | El vocabulario `Alineado/Rezagado/Foco` (`_ESTADO_LABEL`, umbrales 90/75) es de **cumplimiento de presupuesto**. Aplicado a "vs el promedio del año", un mes al 95% del promedio saldría **"Rezagado"** (ámbar), como si incumpliera una meta, cuando solo está algo por debajo de su propia media. Verdicto falso. | Para `promedio_anio`, el `estado` NO reusa el chip de cumplimiento: es **direccional** — `"sobre el promedio"` (cumpl≥100) / `"bajo el promedio"` (cumpl<100). PPTO/OPERATIVO/CONTABLE (presupuestos reales) SÍ conservan `Alineado/Rezagado/Foco`. El frontend pinta el badge direccional en color neutro. |
| **AF-4.11 · `escenario_mes` es función, NO endpoint** | `desempeno` es `@router.get("/desempeno")`. Si el Executor le pone el decorador a `escenario_mes`, sus params se volverían `Query(...)` y llamarla como función normal filtraría objetos `Query` (el mismo bug que el docstring de `ejecutor.py` advierte para `desempeno`). | `escenario_mes` es un **`def` PLANO, SIN `@router.get`** (no se expone como ruta; solo la importa cuantificar). Se coloca fuera del bloque de rutas o simplemente sin decorador. |
| **AF-4.12 · anclas exactas de edición** | El plan describía las ediciones de `ejecutar_n1` (línea 68 `real, ppto, cumpl = …`; línea 87 `"referencia": "PPTO"`; línea 95 `"referencia_valor": ppto`) y la fila "Presupuesto" del frontend de forma aproximada. | §5.3 y §5.6 dan ahora el **texto viejo EXACTO → nuevo** (verificado contra el código: `ejecutor.py:68/87/95`, y la fila `>Presupuesto<` de `__cnCuantCardHtml`). |

---

## 1. Contexto

Motor Q v2 · Grupo 2 (Cuantificar). Edificio SEPARADO
(`consulta_v2/cuantificar/`, cero imports de `consulta/` v1). Regla madre: **Python calcula, el LLM solo
redacta el intro**. La cifra y ahora las referencias salen de `analisis` (mismo cálculo del tablero) →
coherencia. `escenario_mes` reusa el `_ambito` de `desempeno` para no divergir en la resolución.

## 2. Objetivo

Que "¿cuánto produjo Rubiales en abril **vs el operativo**?" · "**…contra el contable**" · "**…vs el
promedio del año**" respondan el mismo REAL con la **referencia elegida** (cumplimiento/estado vs esa
referencia, etiqueta correcta en burbuja y panel), y que "**vs P50**" se rechace con explicación honesta.

## 3. Prerequisitos

- Fases 1-3 presentes y verificadas. Backend en
  `C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend` (`uv run python` desde `backend/`).
- App padre en `C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA`.
- BD dev `daily_report_prod` arriba (solo para pruebas de datos; NUNCA LLM en dev).

## 4. Inventario de archivos

Base backend feature: `C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend\app\features`
Base app padre: `C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA`

| Acción | Ruta |
|--------|------|
| EDITAR | `...\analisis\api.py` — **AÑADIR** `escenario_mes(...)` (helper read-only; NO tocar `desempeno`) |
| EDITAR | `...\consulta_v2\cuantificar\slots.py` — `_referencia(...)` + `referencia` en `extraer_slots` + override promedio⇒N1 |
| EDITAR | `...\consulta_v2\cuantificar\ejecutor.py` — N1 honra la referencia (valor/label/guard P50/recompute); N2 avisa |
| EDITAR | `...\consulta_v2\cuantificar\validador.py` — cuerpo N1 usa `referencia_label` |
| EDITAR | `...\consulta_v2\respuesta_cuantificar.py` — `_panel_datos` N1 lleva `referencia`/`referencia_label` |
| EDITAR | `...\static\js\multitab_shell.js` — `__cnCuantCardHtml`: etiqueta de fila + anillo por referencia |
| EDITAR | `...\consulta_v2\golden\cuantificar_golden.yaml` — +4 casos (operativo, contable, promedio, P50-rechazo) |
| EDITAR | `...\consulta_v2\golden\run_golden_cuantificar.py` — verifica también `referencia` |
| EDITAR | `...\backend\tests\test_cuantificar.py` — +tests referencia (slots, ejecutor, P50, promedio⇒N1) |
| EDITAR | `...\templates\main.html` — subir cache-buster `?v=` |
| NO TOCAR | `desempeno` (AF-4.2), `niveles.py`, `resolver.py`, `catalogo.py`, `variables_cuantificables.yaml`, `patrones_grupo.yaml`, `maquina_q.py`, flujo v1 |

## 5. Especificación (código de referencia)

### 5.1 — `analisis\api.py` (AÑADIR helper `escenario_mes`, NO tocar `desempeno`)

Añadir esta función como **`def` PLANO — SIN `@router.get` (AF-4.11): NO es un endpoint**, solo la importa
cuantificar. Colócala DESPUÉS del cuerpo de `def desempeno(...)` (fuera de su `with`). Reusa `_ambito`,
`get_engine`, `sa` (ya importados en el módulo). **NO modificar `desempeno` ni su query de KPIs (AF-4.2).**

```python
def escenario_mes(entidad: str, nivel: str | None = None, periodo: str | None = None,
                  escenarios=("OPERATIVO", "CONTABLE")) -> dict:
    """Valor por producto de escenarios de presupuesto (OPERATIVO/CONTABLE) en el MES resuelto, con el
    MISMO ámbito que `desempeno` (reusa `_ambito`). Read-only y AISLADO: no toca `desempeno` ni su
    `sin_cierre` (AF-4.2). Devuelve {PRODUCTO: {ESCENARIO: valor}} (vacío si no hay ámbito/datos)."""
    eng = get_engine()
    with eng.connect() as c:
        amb = _ambito(c, entidad, nivel=nivel, periodo=periodo)
        if not amb or amb.get("sin_datos"):
            return {}
        ids, vid, fin = amb.get("ids"), amb.get("vid"), amb.get("fin")
        if not ids and vid is None:
            return {}
        cond, params = [], {"fin": fin, "escs": list(escenarios)}
        if ids:
            cond.append("m.fuente_id IN :ids"); params["ids"] = ids
        if vid is not None:
            cond.append("m.vice_id = :vid"); params["vid"] = vid
        whr = "(" + " OR ".join(cond) + ")" if cond else "TRUE"
        t = sa.text(f"""
            SELECT tp.nombre prod, es.nombre esc, SUM(m.volumen) vol
            FROM core.fact_produccion_mes_ecp m
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = m.tipo_producto_id
            JOIN core.dim_escenario es ON es.escenario_id = m.escenario_id
            WHERE m.fecha = :fin AND es.nombre IN :escs AND {whr}
            GROUP BY 1, 2""").bindparams(sa.bindparam("escs", expanding=True))
        if ids:
            t = t.bindparams(sa.bindparam("ids", expanding=True))
        out = {}
        for prod, esc, vol in c.execute(t, params):
            out.setdefault(prod, {})[esc] = float(vol or 0)
        return out
```
> ⚠️ AF-4.6: confirmar en dev que `core.dim_escenario` contiene EXACTAMENTE `OPERATIVO` y `CONTABLE`
> (`SELECT DISTINCT nombre FROM core.dim_escenario`). Si difieren (p. ej. `PRESUPUESTO OPERATIVO`),
> ajustar las constantes `_REF_ESC` de §5.3 y el default de `escenarios`.

### 5.2 — `slots.py` (EDITAR: detección de referencia)

Añadir constantes + `_referencia`, y usarlas en `extraer_slots`.

```python
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


def _referencia(texto: str) -> str:
    t = norm(texto or "")
    for code, kws in _REF_MATCH:
        if any(k in t for k in kws):
            return code
    return "PPTO"
```
En `extraer_slots`, reemplazar la construcción del dict para computar `ref` y el override de nivel:

```python
def extraer_slots(texto: str, entidad_valor: str | None = None) -> dict:
    prod = _producto(texto, entidad_valor)
    variable = f"produccion_{prod}"
    pcfg = (_catalogo.get().get("productos") or {}).get(variable, {})
    unidad = pcfg.get("unidad", "bbl")
    mes_cfg = (pcfg.get("granos") or {}).get("mes", {})
    descargo = mes_cfg.get("descargo") if mes_cfg.get("confianza") == "media" else None

    ref = _referencia(texto)
    nivel = _nivel_temporal(texto)
    if ref == "promedio_anio":
        nivel = "N1"   # AF-4.9: "promedio del año" es la REFERENCIA (compara un mes), no un acumulado

    per = _periodo_texto(texto)
    defaults = [f"producto={prod}", f"referencia={ref}"]
    if per is None:
        defaults.append("periodo=mes actual")
    return {
        "variable": variable, "producto": prod, "unidad": unidad, "descargo": descargo,
        "nivel_temporal": nivel, "referencia": ref, "periodo_texto": per,
        "defaults_asumidos": defaults,
    }
```
> El grounding de producto (AF10), `_nivel_temporal` (Fase 3) y `_periodo_texto` NO cambian.

### 5.3 — `ejecutor.py` (EDITAR: N1 honra la referencia; N2 avisa)

**(a)** En los imports (arriba), añadir `escenario_mes`:
```python
from app.features.analisis.api import desempeno as _desempeno_ep, _estado, escenario_mes as _escenario_ep
```
**(b)** Añadir el mapa de etiquetas + helper de valor de referencia (junto a `_PROD_MAP`):
```python
_REF_LABEL = {"PPTO": "presupuesto", "OPERATIVO": "presupuesto operativo",
              "CONTABLE": "cierre contable", "promedio_anio": "promedio mensual del año"}
_REF_ESC = {"OPERATIVO": "OPERATIVO", "CONTABLE": "CONTABLE"}   # AF-4.6: nombres en dim_escenario


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
```
**(c)** Cambiar la firma de `ejecutar`/`ejecutar_n1` para propagar `_escenario_fn`, y meter la lógica de
referencia. En `ejecutar` (`ejecutor.py:22`):
```python
def ejecutar(resuelta: dict, slots: dict, _desempeno_fn=None, _escenario_fn=None) -> dict:
    nt = slots.get("nivel_temporal")
    if nt == "N4":
        return ejecutar_n4(resuelta, slots, _desempeno_fn=_desempeno_fn)
    if nt == "N3":
        return ejecutar_n3(resuelta, slots, _desempeno_fn=_desempeno_fn)
    if nt == "N2":
        return ejecutar_n2(resuelta, slots, _desempeno_fn=_desempeno_fn)
    return ejecutar_n1(resuelta, slots, _desempeno_fn=_desempeno_fn, _escenario_fn=_escenario_fn)
```
En `ejecutar_n1`, firma `def ejecutar_n1(resuelta, slots, _desempeno_fn=None, _escenario_fn=None)`. Tras
`_rechazo_comun`, **rechazar P50 antes de tocar la BD** (AF-4.4):
```python
    producto = slots["producto"]
    unidad = slots.get("unidad", "bbl")
    ref = slots.get("referencia", "PPTO")
    if ref == "P50":
        return {"aplica": False, "texto": (
            "El P50 (compromiso) solo existe a nivel corporativo ECP-global, en kbpe, y no reconcilia "
            f"con el reporte a nivel campo/activo/gerencia; no puedo comparar «{resuelta['valor']}» "
            "contra P50. Puedo con el presupuesto (PPTO), el operativo, el contable o el promedio del año.")}
    quiero = _PROD_MAP[producto]
```
Luego, sustituir **EXACTAMENTE** la línea (`ejecutor.py:68`)
`    real, ppto, cumpl = fila["real"], fila.get("ppto"), fila.get("cumplimiento")`
y la siguiente (`    estado = _ESTADO_LABEL.get(_estado(cumpl), "")`) por:
```python
    real = fila["real"]
    ref_valor, ref_label = _valor_referencia(ref, fila, d, quiero, resuelta, slots, _escenario_fn)
    cumpl = round(real / ref_valor * 100.0, 1) if ref_valor else None   # AF-4.8: recomputar vs la ref
    if ref == "promedio_anio" and cumpl is not None:      # AF-4.10: NO chip de cumplimiento en promedio
        estado = "sobre el promedio" if cumpl >= 100 else "bajo el promedio"
    else:
        estado = _ESTADO_LABEL.get(_estado(cumpl), "")
    nivel = resuelta.get("nivel")
    etiqueta = _NIVEL_TEXTO.get(nivel, "")
    proyeccion = (not mes["completo"]) and bool(mes["dias_con_data"])

    avisos = []
    if slots.get("descargo"):
        avisos.append(slots["descargo"])
    if ref != "PPTO" and not ref_valor:                       # AF-4.5: sin referencia registrada
        avisos.append(f"No hay {ref_label} registrado para {mes['nombre']} {mes['anio']}; muestro lo producido.")
    for x in (d.get("campos_sin_meta") or []):
        if x["producto"] == quiero:
            avisos.append(f"El campo {x['campo']} produce sin meta asignada "
                          f"({_fmt_valor(x['real'], producto)} {unidad} fuera del presupuesto).")
```
Y en el `return` de `ejecutar_n1`, dos cambios EXACTOS:
- línea 87 — de
  `        "producto": producto, "referencia": "PPTO", "unidad": unidad, "grano": "mes",`
  a
  `        "producto": producto, "referencia": ref, "referencia_label": ref_label, "unidad": unidad, "grano": "mes",`
- línea 95 — de `        "resultado": {"valor": real}, "referencia_valor": ppto,`
  a `        "resultado": {"valor": real}, "referencia_valor": ref_valor,`
> Ya no queda ninguna variable llamada `ppto` en `ejecutar_n1` (la reemplazó `ref_valor`); verificar que
> no se referencia en ningún otro sitio de la función.

**(d)** En `ejecutar_n2`, tras construir `avisos`, añadir (AF-4.7):
```python
    if slots.get("referencia", "PPTO") != "PPTO":
        avisos.append("Las referencias alternas (operativo/contable/promedio) por ahora solo aplican al "
                      "dato puntual de un mes; el acumulado se compara con el presupuesto (PPTO).")
```

### 5.4 — `validador.py` (EDITAR: cuerpo N1 usa `referencia_label`)

En `formatear_cuerpo`, rama **N1** (la última), reemplazar la construcción de `linea` para usar la
etiqueta de referencia (en vez de "presupuesto" fijo). El bloque N1 queda:

```python
    # N1: mes puntual. Regla de proyección + referencia elegida (Fase 4).
    mes = res["mes"]
    ref_label = res.get("referencia_label", "presupuesto")
    corte = ("mes cerrado" if mes["completo"]
             else f"proyección · {mes['dias_con_data']}/{mes['dias_del_mes']} días")
    linea = (f"{res['entidad_cualificada']} produjo {real} {unidad} de {prod} en {mes['nombre']} "
             f"{mes['anio']} — {pct} del {ref_label} ({res['estado']}) · {corte}.")
    if ppto:
        linea += f" {ref_label.capitalize()} del mes: {ppto} {unidad}."
    for a in res.get("avisos", []):
        linea += f" ⚠️ {a}"
    return linea
```
> `ppto` aquí es la variable ya calculada arriba en `formatear_cuerpo`
> (`ppto = fmt_valor(res["referencia_valor"], prod) if res.get("referencia_valor") else None`) — es el
> VALOR de la referencia, no necesariamente PPTO. La rama N2 (siempre PPTO en Fase 4) NO cambia.

### 5.5 — `respuesta_cuantificar.py` (EDITAR: `_panel_datos` N1 lleva la referencia)

En `_panel_datos`, en el bloque `else` (N1/N2), añadir la etiqueta/código de referencia SOLO para N1:

```python
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
```

### 5.6 — `static\js\multitab_shell.js` (EDITAR `__cnCuantCardHtml`: etiqueta por referencia)

En `__cnCuantCardHtml`, tras `var unidad = dat.unidad || "bbl";`, añadir:
```javascript
    // Fase 4: la referencia puede no ser PPTO (operativo/contable/promedio) — etiqueta dinámica.
    var refLbl = dat.referencia_label
      ? (dat.referencia_label.charAt(0).toUpperCase() + dat.referencia_label.slice(1)) : "Presupuesto";
    var refCorta = ({ PPTO: "PPTO", OPERATIVO: "OPER", CONTABLE: "CONT", promedio_anio: "PROM" })[dat.referencia] || "PPTO";
```
Cambiar la etiqueta del anillo:
- `__cnRing(pct, col, 96, "REAL / PPTO", 1)` → `__cnRing(pct, col, 96, "REAL / " + refCorta, 1)`

Cambiar la fila "Presupuesto" (EXACTO — es la línea del `return` de `__cnCuantCardHtml` que hoy dice):
- de:
  `        '<div class="cp-p50__r"><span class="cp-p50__k">Presupuesto</span><span class="cp-p50__v">' + fmtV(dat.ppto) + ' ' + unidad + '</span></div>' +`
- a:
  `        '<div class="cp-p50__r"><span class="cp-p50__k">' + esc(refLbl) + '</span><span class="cp-p50__v">' + fmtV(dat.ppto) + ' ' + unidad + '</span></div>' +`
> N2 no trae `referencia`/`referencia_label` → `refLbl="Presupuesto"`, `refCorta="PPTO"` (retro-compatible).
> N3/N4 usan sus propios renderizadores (no pasan por aquí).

### 5.7 — `golden\cuantificar_golden.yaml` (AÑADIR al final)

```yaml

# ---- Fase 4: referencias ≠ PPTO en N1 ----
- pregunta: "¿cuánto crudo produjo Rubiales en abril vs el operativo?"
  entidad: "RUBIALES"
  nivel_temporal: N1
  producto: crudo
  referencia: OPERATIVO
  resultado: aplica
- pregunta: "¿cuánto produjo Rubiales en abril contra el contable?"
  entidad: "RUBIALES"
  nivel_temporal: N1
  producto: crudo
  referencia: CONTABLE
  resultado: aplica
- pregunta: "¿cómo va Rubiales en abril frente al promedio del año?"
  entidad: "RUBIALES"
  nivel_temporal: N1
  producto: crudo
  referencia: promedio_anio
  resultado: aplica
- pregunta: "¿cuánto produjo Rubiales vs el P50?"
  entidad: "RUBIALES"
  nivel_temporal: N1
  producto: crudo
  referencia: P50
  resultado: rechazo_otro
```
> `nivel_temporal`+`producto`+`referencia` son deterministas (100%). `resultado` depende de datos:
> OPERATIVO/CONTABLE de Rubiales/abril deben existir → `aplica`; si CONTABLE no está registrado el runner
> lo verá como `aplica` con aviso (sigue siendo `aplica`). P50 → `rechazo_otro` (determinista).

### 5.8 — `golden\run_golden_cuantificar.py` (EDITAR: verificar `referencia`)

Tras `prod_ok = ...`, añadir `ref_ok` y sumarlo al acierto:
```python
        ref_ok = slots.get("referencia", "PPTO") == c.get("referencia", "PPTO")
```
```python
        acierto = nivel_ok and prod_ok and ref_ok and resultado_ok
```
y en la traza del fallo incluir la referencia:
```python
            extra = (f"  -> nivel={slots['nivel_temporal']} producto={slots['producto']} "
                     f"ref={slots.get('referencia')} resultado={resultado}")
```

### 5.9 — `tests\test_cuantificar.py` (AÑADIR al final)

```python
# ================= Fase 4: referencias ≠ PPTO (N1) =================

def test_slots_ref_operativo():
    assert _slots.extraer_slots("cuanto produjo Rubiales vs el operativo")["referencia"] == "OPERATIVO"


def test_slots_ref_contable():
    assert _slots.extraer_slots("cuanto produjo Rubiales contra el contable")["referencia"] == "CONTABLE"


def test_slots_ref_p50():
    assert _slots.extraer_slots("cuanto produjo Rubiales vs el P50")["referencia"] == "P50"


def test_slots_ref_default_ppto():
    assert _slots.extraer_slots("cuanto produjo Rubiales en abril")["referencia"] == "PPTO"


def test_slots_ref_promedio_fuerza_n1():
    # AF-4.9: "promedio del año" es la referencia -> N1, NO N2 (aunque contenga "del año")
    s = _slots.extraer_slots("cuanto produjo Rubiales frente al promedio del año")
    assert s["referencia"] == "promedio_anio" and s["nivel_temporal"] == "N1"


def _fake_n1_ritmo(entidad="X", segmento="ecp", nivel="campo", periodo=None):
    return {"encontrada": True, "sin_datos": False, "sin_cierre": False,
            "mes": {"anio": 2026, "mes": 4, "nombre": "Abril", "completo": True,
                    "dias_con_data": 30, "dias_del_mes": 30},
            "por_producto": [{"producto": "CRUDO", "real": 1200.0, "ppto": 1250.0, "cumplimiento": 96.0}],
            "campos_sin_meta": [],
            "ritmo_mensual": {"meses": ["Ene", "Feb", "Mar", "Abr"], "meses_num": [1, 2, 3, 4],
                              "series": {"CRUDO": [100, 110, 105, 120]},
                              "promedio_mes": {"CRUDO": 109}, "promedio_dia": {}}}


def test_ejecutar_n1_p50_rechaza():
    slots = _slots.extraer_slots("cuanto produjo Rubiales vs el P50")
    res = _ejecutor.ejecutar_n1({"nivel": "campo", "rama": "A", "valor": "RUBIALES", "zoom": []},
                                slots, _desempeno_fn=_fake_n1_ritmo)
    assert res["aplica"] is False and "P50" in res["texto"]


def test_ejecutar_n1_promedio_usa_ritmo():
    slots = _slots.extraer_slots("cuanto produjo Rubiales frente al promedio del año")
    res = _ejecutor.ejecutar_n1({"nivel": "campo", "rama": "A", "valor": "RUBIALES", "zoom": []},
                                slots, _desempeno_fn=_fake_n1_ritmo)
    assert res["aplica"] and res["referencia"] == "promedio_anio"
    assert res["referencia_valor"] == 109 and res["referencia_label"] == "promedio mensual del año"
    assert res["estado"] == "sobre el promedio"      # AF-4.10: direccional, NO "Alineado" (1200 > 109)


def test_ejecutar_n1_operativo_usa_helper():
    slots = _slots.extraer_slots("cuanto produjo Rubiales vs el operativo")

    def _fake_esc(entidad, nivel=None, periodo=None, escenarios=()):
        return {"CRUDO": {"OPERATIVO": 1300.0}}

    res = _ejecutor.ejecutar_n1({"nivel": "campo", "rama": "A", "valor": "RUBIALES", "zoom": []},
                                slots, _desempeno_fn=_fake_n1_ritmo, _escenario_fn=_fake_esc)
    assert res["referencia"] == "OPERATIVO" and res["referencia_valor"] == 1300.0
    assert res["cumplimiento_pct"] == round(1200 / 1300 * 100, 1)


def test_ejecutar_n1_ppto_sin_regresion():
    # PPTO recomputado = real/ppto = fila["cumplimiento"] -> idéntico a Fase 1-3
    slots = _slots.extraer_slots("cuanto produjo Rubiales en abril")
    res = _ejecutor.ejecutar_n1({"nivel": "campo", "rama": "A", "valor": "RUBIALES", "zoom": []},
                                slots, _desempeno_fn=_fake_n1_ritmo)
    assert res["referencia"] == "PPTO" and res["referencia_valor"] == 1250.0
    assert res["cumplimiento_pct"] == round(1200 / 1250 * 100, 1)
```

### 5.10 — `templates\main.html` (cache-buster)

Subir el `?v=` del `<script ... multitab_shell.js>` (`main.html:82`), p.ej. `?v=20260802j1`.

## 6. Orden de ejecución

1. `analisis/api.py` (5.1, helper `escenario_mes`; **NO tocar `desempeno`**). `py_compile`.
2. `slots.py` (5.2) → `ejecutor.py` (5.3) → `validador.py` (5.4) → `respuesta_cuantificar.py` (5.5).
   **`py_compile` de los 4.**
3. Frontend `multitab_shell.js` (5.6) + `main.html` (5.10). **`node --check multitab_shell.js`.**
4. golden (5.7) + runner (5.8) + tests (5.9).
5. Confirmar `dim_escenario` (AF-4.6, data-check dev, sin LLM) y ajustar `_REF_ESC` si aplica.
6. Correr la **COMPUERTA** (§8). Reportar y ESPERAR aprobación.

## 7. Reglas no negociables

1. **El número es VERBATIM de Python**; el LLM solo redacta el intro (1c).
2. **NO tocar `desempeno`** (AF-4.2): OPERATIVO/CONTABLE salen del helper `escenario_mes`; promedio de
   `ritmo_mensual`; PPTO de `fila["ppto"]`.
3. **Recomputar el cumplimiento vs la referencia elegida** (AF-4.8); para PPTO da idéntico.
4. **P50 = rechazo honesto** (AF-4.4). **CONTABLE ausente = degradar honesto** (AF-4.5).
5. **Solo N1** (AF-4.7): N2 avisa si la referencia ≠ PPTO; N3/N4 la ignoran.
6. **Edificio separado**; NO tocar `resolver.py`, `catalogo.py`, `variables_cuantificables.yaml`,
   `patrones_grupo.yaml`, `niveles.py`, `maquina_q.py`, el flujo v1.
7. **NO usar el LLM local de dev**; runtime/navegador/pytest → servidor de pruebas.

## 8. Validaciones (comando → resultado; TODAS sin LLM; en dev salvo «servidor»)

- **V1** (estático) `py_compile` de analisis/api, slots, ejecutor, validador, respuesta_cuantificar → OK.
- **V2** (estático) `node --check static/js/multitab_shell.js` → sin errores.
- **V3** (datos) `slots.extraer_slots("... vs el operativo")["referencia"]=="OPERATIVO"`;
  `...("... contable")=="CONTABLE"`; `...("... vs el P50")=="P50"`; `...("cuanto produjo Rubiales")=="PPTO"`;
  `...("... promedio del año")` → `referencia=="promedio_anio"` y `nivel_temporal=="N1"` (AF-4.9).
- **V4** (datos, AF-4.6) `SELECT DISTINCT nombre FROM core.dim_escenario` incluye los nombres usados en
  `_REF_ESC`; `escenario_mes("RUBIALES", nivel="campo", periodo="abril")` devuelve valores por producto.
- **V5** (datos, AF-4.2, no-regresión) `desempeno(entidad="RUBIALES", segmento="ecp", nivel="campo",
  periodo="abril")` → `por_producto` CRUDO `real==10966768.1332`, `cumplimiento==90.8` (idéntico a antes;
  el helper NO tocó `desempeno`).
- **V6** (servidor) `run_golden_cuantificar.py` ≥90% (`referencia` acierta 100%); pytest verde (Fases 1-4).
- **V7** (servidor, navegador) Motor v2: "cuánto crudo produjo Rubiales en abril **vs el operativo**" →
  burbuja "…del presupuesto operativo…" + panel con fila "Presupuesto operativo" y anillo "REAL / OPER";
  "**vs el P50**" → rechazo con explicación. N1-PPTO/N2/N3/N4 sin regresión.

## 9. Fuera de alcance (NO hacer)

- **Referencias en N2/N3/N4** (acumulado/serie/variación vs referencia alterna) — fase posterior.
- **Integrar `president()` / P50 real** (kbpe, ECP-global) en cuantificar — se rechaza con explicación.
- **REAL como "referencia"** (es el valor, no una comparación) — no se añade al slot.
- **Extender `desempeno`** (AF-4.2, rompería `sin_cierre`).
- Grano DÍA, periodos año/trimestre/semana, agua, derivadas, conteos, robustez, diferidas.
