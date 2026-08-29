# Plan v2 · Panel derecho para el P50 por VICEPRESIDENCIA (tarjeta de cierre de brechas)

**Fecha:** 2026-08-13 · **Planner:** Claude · **Ejecuta:** Executor
**Estado:** **v2 AUDITADO** — 5 hallazgos de la ronda adversarial corregidos ANTES de codificar (§3)
**Depende de:** `plan_p50_referencia_analizar_2026-08-13.md` (commits `1872779`/`ed1cb20`/`dd8ffa2`, en `main`)
**Mockup aprobado:** https://claude.ai/code/artifact/e1d6eab3-f770-43c0-9d1f-415f3f5aa978

**Cobertura: tipos de panel entrada 6 → salida 7** (se AÑADE `p50_vp`; ninguno se retira ni se modifica).

---

## 1. CONTEXTO

La sub-intención `referencia` ya responde el P50 con cifras correctas, pero **siempre con
`panel=None`**. Para el DECLINAR eso es correcto y se conserva (M8 del plan anterior: un gráfico
de P50 junto a un texto que dice «no tengo P50 para este campo» pondría dos verdades opuestas en
pantalla). Para la respuesta AFIRMATIVA por vicepresidencia, no: el usuario recibe una cifra real
y el panel derecho no la acompaña.

**Este plan da panel SOLO a la rama afirmativa de vicepresidencia.**

---

## 2. AUDITORÍA DE DATOS — medido contra la BD (NO re-verificar, SÍ respetar)

Postgres local `daily_report_prod`, reporte 18 (2026-05-18), hoja `NEW MES-AÑO` t8 (P50) + t2 (REAL).

### A1 · Productos por VP — el nº de tarjetas VARÍA

```
CPV -> CRUDO, GAS    GAA -> CRUDO         GLH -> CRUDO         GPA -> CRUDO, GAS
DFL -> CRUDO, GAS    GAN -> CRUDO, GAS    GNS -> CRUDO, GAS    GRM -> CRUDO
GCT -> CRUDO         GOR -> CRUDO         GTA -> CRUDO         PRP -> CRUDO, GAS
```
**CRUDO:** las 12 · **GAS:** solo 6 · **BLANCOS: 0 filas para NINGUNA VP** (medido).

### A2 · Serie GOR/CRUDO (12 meses del reporte 18)

```
ene 151.700 / 146.375   abr 154.700 / 143.669   jul 155.846 / —   oct 155.521 / —
feb 149.114 / 145.923   may 159.024 / —         ago 156.090 / —   nov 155.066 / —
mar 150.094 / 145.130   jun 156.985 / —         sep 154.262 / —   dic 151.672 / —
```
🔑 **El P50 por VP NO es plano** (a diferencia del corporativo): sube y baja ⇒ **POLILÍNEA**, no recta.
🔑 **El REAL termina en abril**; las 12 VP comparten ese corte ⇒ el hueco may-dic es real, **no se rellena**.

### A3 · Costo del query

Serie de 12 meses con `p.reporte_id = :rid` fijo: **0,00 s** (medido).
⚠️ El MISMO query sin `reporte_id`: **2,61 s** (medido en el plan anterior). La cláusula **no es opcional**.

### A4 · Lo que NO existe (y por tanto NO se dibuja)

| Elemento del artifact corporativo | ¿Por VP? |
|---|---|
| Línea de **compromiso** + banda ámbar | ❌ el RETO no está por VP; donde está, **es idéntico al P50** ⇒ banda de altura 0 |
| **Proyección de cierre** (punteada) | ❌ `pace_crudo` es global |
| Tarjeta de **BLANCOS** | ❌ 0 filas |

⇒ La tarjeta es **P50 (gris, polilínea) + REAL (verde, hasta abril)**. Dos series, no cuatro.

### A5 · Escala

**bbl** (crudo) / **MSCF** (gas) — NO kbpe (esa es la corporativa del encabezado). Rotular siempre.

---

## 3. HALLAZGOS DE LA AUDITORÍA ADVERSARIAL (§0.2) — corrigen el plan v1

🔴 **Estos 5 puntos invalidaron supuestos del v1. Son la razón de esta v2.**

| # | Hallazgo (verificado en el código) | Corrección |
|---|---|---|
| **H1** | 🔴 **El v1 pedía iterar CRUDO+GAS en el panel, pero el MENSAJE se acota a UN producto** (`respuesta_analizar.py:174`: `_producto_explicito(texto, ent_valor) or "CRUDO"`). Un panel de 2 tarjetas junto a un texto que solo habla de crudo son **dos verdades distintas en pantalla** — exactamente el defecto que M8 evita en el declinar. | §4.1: el panel muestra **el MISMO producto que el mensaje**. Una tarjeta por respuesta. Ver §8 D5 para el futuro multi-producto. |
| **H2** | 🔴 **La cadena del dispatcher termina en un FALLBACK sin guard** (`multitab_shell.js:2800`: `: __cnCuantCardHtml(d)`), no en un `else if`. Un `tipo` no registrado **NO falla: pinta una tarjeta KPI con campos ajenos** (`estado`, `cumplimiento_pct`, `nivel`) → basura silenciosa. | §5 Paso 3: la rama `p50_vp` se registra **ANTES** del fallback. Test JS que lo verifica (§6 J1). |
| **H3** | ⚠️ **El guard del panel es `if (!panel || !panel.datos) return`** (`:2785`) — un `datos:{productos:[]}` o `datos:{}` **pasa el guard** y crea un bloque vacío en la pila. | §5 Paso 2: si no hay serie, el backend devuelve **`panel=None`**, nunca `datos` con lista vacía. |
| **H4** | 🔴 **DOS convenciones de caso conviven, y mezclarlas ROMPE EL GAS EN SILENCIO.** El `producto` que circula por la rama 3c es **MAYÚSCULAS** (`_producto_explicito` → `"GAS"`), pero mi contrato v1 pedía minúsculas. Medido: `p50_referencia._fmt(1e7, "gas")` → **`"10.000.000"`** en vez de `"10,0"` — la conversión a MSCF se pierde y el número sale **1e6 veces mayor**, sin error. Igual con `_UNIDAD["gas"]` → `None`. Y en el frontend **también conviven**: `"GAS"` en `:2133`/`:2472` (análisis v1) vs `"gas"` en `:2618`-`:2940` (Motor Q v2). Es el bug ya documentado («con claves en MAYÚSCULAS el fallback gris salía EN SILENCIO»). | §4.2 + §5 Paso 1: **la frontera de conversión es ÚNICA y explícita** — `serie_por_vp` recibe MAYÚSCULAS (como todo el módulo) y emite el contrato con `"producto"` en **minúsculas** (`.lower()`), que es lo que consumen los 6 tipos del Motor Q v2. **Dentro** del módulo Python todo sigue en MAYÚSCULAS (`_UNIDAD`/`_PROD_L`/`_fmt` NO se tocan). Test P10 lo blinda. |
| **H5** | ⚠️ **El comentario de `maquina_q.py:416-418` quedará FALSO**: dice «SOLO la rama causal produce panel; proyección/diferidas/economía van con panel=None» — tras este plan, `referencia` también produce. | §5 Paso 5: actualizar ese comentario (documentación viva, no decorativa). |

**Oportunidad detectada (no defecto):** `__cnRankDotHtml` (`:2939`) es el patrón EXACTO a imitar —
constructor puro, SVG nativo, `fmtV` por producto (`__cnGasM`/`__cnMilesEC`), sin `overflow` propio.
**Reusar sus helpers, no escribir formateadores nuevos.**

---

## 4. DISEÑO

### 4.1 Alcance exacto (corregido por H1)

| Rama de `referencia` | Panel |
|---|---|
| VP afirmativa (`vicepresidencia`, o `gerencia` con `puente=True`) **con serie** | ✅ **`p50_vp`** — 1 tarjeta, el MISMO producto del mensaje |
| VP afirmativa **sin serie** (la VP no tiene ese producto) | ❌ `None` (H3) |
| Global ECP (`nivel=None`) | ❌ `None` — fuera de alcance (D1) |
| **Declinar** (campo/activo/…) | ❌ `None` — **M8 se conserva** (D2) |

### 4.2 Contrato del panel (corregido por H3/H4)

```json
{"tipo": "p50_vp", "datos": {
  "vice": "GOR",
  "producto": "crudo",            // MINÚSCULAS (H4) — lo que consumen los 6 tipos del Motor Q v2
  "unidad": "bbl",                // "MSCF" si gas (A5) — resuelta en Python, NO en el JS
  "corte": "2026-05-18",          // fecha_reporte de origen
  "mes_real": "2026-04-30",       // último mes con AMBAS cifras (A2) — se ROTULA (R1)
  "real": 143669.4, "p50": 154699.5, "pct": 92.9, "gap": -11030.1,
  "serie": [{"fecha":"2026-01-31","p50":151700.0,"real":146375.2}, … 12 puntos …]
}}
```
- `serie[].real` puede ser `null` (may-dic): el trazo verde **se corta ahí** — ni se interpola ni
  se sustituye por 0.
- `pct`/`gap` se calculan sobre `mes_real`, **no** sobre el último mes de la serie.

🔑 **FRONTERA DE CONVENCIÓN (H4) — la regla más delicada de este plan.** Los valores numéricos
(`real`/`p50`/`gap`/`serie[].*`) viajan **CRUDOS, sin convertir**: el `÷1e6` del gas lo hace el
**frontend** con `__cnGasM`, igual que los 6 tipos existentes. Python NO pre-formatea. Y la clave
`"producto"` se emite en **minúsculas** (`.lower()`) **solo al construir el dict de salida** —
dentro del módulo Python el producto sigue en MAYÚSCULAS, porque `_UNIDAD`/`_PROD_L`/`_fmt` están
indexados así (medido: `_fmt(1e7,"gas")` → `"10.000.000"`, mil veces mayor, **sin error**).

### 4.3 Forma visual (mockup aprobado)

Encabezado (producto + chip de estado + cifra grande con unidad) → SVG (polilínea gris P50 sobre
12 meses + polilínea verde REAL hasta el corte + punto en el corte + vertical punteada del corte)
→ pie de 4 filas (Real / Base P50 / Cumplimiento / Brecha).

**Chip:** `pct<100` → «▼ Bajo el P50» · `pct>100` → «▲ Sobre el P50» · `|pct−100|<0.05` → «≈ En el P50».

---

## 5. IMPLEMENTACIÓN

### Paso 1 · `analizar/p50_referencia.py` — función NUEVA

```python
def serie_por_vp(vice: str, producto: str = "CRUDO") -> dict | None:
    """Serie mensual completa (P50 + REAL) de una VP/producto, del reporte más reciente que tenga
    la hoja. `producto` ENTRA en MAYÚSCULAS (como todo este módulo) y SALE en minúsculas dentro
    del dict (H4: frontera única de conversión). None si esa VP no reporta ese producto (A1).
    `real` es None en los meses sin dato — el trazo se corta ahí, NO se interpola ni se rellena
    con 0. Los valores van CRUDOS: el ÷1e6 del gas lo hace el frontend (__cnGasM)."""
```
- ⚠️ Resolver el `reporte_id` PRIMERO (el más reciente con `NEW MES-AÑO` t8 — mismo criterio que
  `p50_por_vp` tras `dd8ffa2`) y consultar la serie **con `p.reporte_id = :rid` fijo** (A3).
- ⚠️ La `unidad` sale de `_UNIDAD[producto.upper()]` — **nunca** de la clave ya minusculizada
  (`_UNIDAD["gas"]` → `None`, medido).
- Caché en proceso por `(vice, producto)`, patrón `_P50_VP_CACHE`; **errores NO se cachean**.
- 🔑 **`p50_por_vp` NO se modifica** — la usa el declinar, ya verificado en navegador.

### Paso 2 · `respuesta_analizar.py` — emitir el panel (H1 + H3)

En el bloque «3c», rama `if es_vp:` (la afirmativa). **Solo el producto del mensaje** (H1):
```python
panel_ref = None
if info:                                  # ya hay cifra en el mensaje
    s = serie_fn(ent_valor, producto)     # MISMO `producto` que usó el mensaje
    if s and s.get("serie"):              # H3: sin serie -> panel None, nunca datos vacíos
        panel_ref = {"tipo": "p50_vp", "datos": s}
```
- El **texto del mensaje NO cambia** (sigue saliendo de `formatear_cifra_vp`). Este plan solo AÑADE panel.
- Inyección para tests: nuevo param `_serie_fn=None`, propagado en los **DOS wrappers**.
- ⚠️ **Devolver el panel SOLO en esta rama.** Global y declinar conservan `panel=None`.

### Paso 3 · `static/js/multitab_shell.js` — constructor + dispatcher (H2 + H4)

- `__cnP50VpHtml(d)`: función **PURA** que devuelve HTML, patrón de `__cnRankDotHtml` (`:2939`).
- Registrarla en la cadena de `__cnPintarPanelCuant` (`:2791-2800`) **ANTES del fallback**
  `: __cnCuantCardHtml(d)` — H2: el fallback no valida el tipo y pintaría una tarjeta KPI basura.
- Reusar: `__cnProdId`/`__cnProdCol` (accessor obligatorio, H4), `__cnGasM`/`__cnMilesEC` (formato),
  `__CP_PROD` solo vía accessor.
- ⚠️ **Sin `overflow` propio** (regla de oro del scroll, `colapsable.css:1367-1372`).
- ⚠️ Escala Y del `min/max` de `p50 ∪ real` de ESA serie; `tabular-nums` en las cifras.

### Paso 4 · `static/css/colapsable.css` — clases `.cn-p50vp*`

**Solo clases NUEVAS** (cero colisión). Tokens de producto `--cp-prod` y de estado `--cp-st` ya existen.

### Paso 5 · Documentación viva (H5)

Actualizar el comentario de `maquina_q.py:416-418` — ya no es cierto que solo `causal` produce panel.

### Paso 6 · cache-buster en `templates/main.html`.

---

## 6. TESTS

Ampliar `backend/tests/test_p50_referencia.py` (no crear archivo nuevo).

| # | Caso | Espera |
|---|---|---|
| P1 | `serie_por_vp("GOR","CRUDO")` (BD) | 12 puntos; `mes_real=2026-04-30`; `pct≈92.9`; `gap≈−11030` |
| P2 | `serie_por_vp("GOR","GAS")` (BD) | `None` — GOR no tiene gas (A1) |
| P3 | `serie_por_vp("GOR","BLANCOS")` (BD) | `None` (A1: 0 filas) |
| P4 | serie con meses sin real | esos puntos tienen `real=None`, **no 0** |
| P5 | rama VP afirmativa, `_serie_fn` inyectado | `panel["tipo"]=="p50_vp"`; `datos["producto"]` en **minúsculas** (H4) |
| P6 | VP afirmativa, `_serie_fn` → `None` | **`panel is None`** (H3: nunca `datos` vacío) |
| P7 | **DECLINAR** (campo) | `panel is None` — M8 vigente (no-regresión) |
| P8 | Global ECP (`nivel=None`) | `panel is None` (D1) |
| P9 | `p50_por_vp` intacta | no-regresión (el declinar depende de ella) |
| **P10** | 🔑 **Frontera de convención (H4)**: `serie_por_vp("PRP","GAS")` | `datos["producto"] == "gas"` (minúsculas) **Y** `datos["unidad"] == "MSCF"` (resuelta con la clave en MAYÚSCULAS). Ambas a la vez — si `unidad` sale `None`, la conversión se hizo en el orden equivocado. |
| **P11** | 🔑 **Valores CRUDOS (H4)**: gas en `serie_por_vp` | `datos["real"]` es del orden de **millones** (crudo, sin ÷1e6). Si viniera en unidades, el frontend lo dividiría OTRA VEZ → cifra 1e6 veces menor. |
| **J1** | **JS:** el tipo `p50_vp` NO cae en el fallback | `__cnP50VpHtml` registrado antes de `__cnCuantCardHtml` (H2) — verificar por lectura + `node --check` |

**No-regresión OBLIGATORIA:** suite completa, baseline **433 passed** + **4 fallos PREEXISTENTES**
(`test_analisis_tarjetas_kpi` ×2, `test_conteo_jerarquia` ×2 — confirmar que siguen siendo
**exactamente esos 4**); `test_analizar.py` **27/27**; golden analizar **10/10**; `node --check`.

---

## 7. VERIFICACIÓN

### Dev (SOLO estático — cero LLM, cero backend)
`py_compile` ×2 · `node --check` · `pytest` · `git diff --stat` confirmando que NO se tocaron
`patrones_grupo.yaml`, `respuesta_cuantificar.py`, `respuesta_jerarquizar.py`.

### Servidor de pruebas (usuario) — ⚠️ **recargar la página primero**

| # | Pregunta | Espera |
|---|---|---|
| W1 | «cuál es el P50 de GOR» | 1 tarjeta (crudo), curva gris **NO plana**, real cortado en abril, unidad **bbl** |
| W2 | «cuál es el P50 de gas de PRP» | 1 tarjeta de **gas**, unidad **MSCF**, escala propia |
| W3 | «cuál es el P50 de gas de GOR» | Mensaje honesto **sin panel** (GOR no tiene gas) |
| W4 | «dame el P50 para el campo Rubiales» | Declinar **sin panel** (M8) |
| W5 | «cuál es el P50 de crudo?» | Cifra global **sin panel** (D1) |
| W6 | «por qué estamos bajo el P50?» | Causal con su `analiza_foco` — sin regresión |
| W7 | Tras W4, «la vicepresidencia» | Cifra de GOR **con** panel; no entra en bucle (no-regresión `dd8ffa2`) |

---

## 8. DECISIONES Y RIESGOS

| # | Decisión | Razón |
|---|---|---|
| **D1** | **Global ECP SIN panel** | Su caso nativo es el artifact corporativo (3 productos, kbpe, con compromiso) — otra tarjeta y otra fuente (`REPORTE_PRESIDENT`). Plan aparte. |
| **D2** | **El declinar conserva `panel=None`** | M8: el gráfico contradiría el texto. **No es olvido — es la regla.** |
| **D3** | Sin banda de compromiso ni proyección | A4: no existen por VP. Dibujarlas exigiría inventar el dato. |
| **D4** | Datos EMBEBIDOS, no fetch async | Son 12 puntos. `analiza_foco` es el único async y por un motivo que aquí no aplica. |
| **D5** | **1 tarjeta (el producto del mensaje), no 2** | H1: el mensaje se acota a un producto; un panel con 2 diría algo distinto al texto. Multi-producto exigiría cambiar TAMBIÉN el mensaje → plan aparte. |
| **R1** | ⚠️ **Dos periodos en pantalla** | El panel dice **abril**; el resto del tablero, mayo. **Rotular «último mes con real por vicepresidencia»** o parecerá dato desfasado. |
| **R2** | ⚠️ Escala bbl/MSCF ≠ kbpe del encabezado | A5. Rotular la unidad SIEMPRE. |
| **R3** | ⚠️ El P50 por VP no es plano | A2. Dibujar POLILÍNEA; una recta sería falsa. |

---

## 9. FUERA DE ALCANCE

- Panel para el **global ECP** (D1) y para el **declinar** (D2).
- Panel **multi-producto** (D5) — exigiría cambiar el mensaje, no solo el panel.
- Línea de compromiso / banda ámbar (A4) — bloqueada por **dato**, no por código.
