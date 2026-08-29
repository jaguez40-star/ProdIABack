# QV2-PANEL-MES — Panel gráfico para N3 (serie mensual) y N4 (variación mes a mes)

**Fecha:** 2026-08-25
**Alias:** `QV2-PANEL-MES`
**Antecedente:** `plan_panel_comportamiento_dia_2026-08-25.md` (QV2-PANEL-DIA), que introdujo el
grid `cn-compprod__grid` (KPI 30 / gráfico 70) para el grano DÍA.
**Rev. 2** — reescrito tras auditoría adversarial (backend + frontend). Los hallazgos que
invalidaron la rev. 1 están en §9, con lo que se descartó y por qué.

---

## 1. Qué se pide

Hoy el panel derecho de una respuesta de Cuantificar depende del nivel, pero solo el grano
DÍA (`cuant_dia_panel`) dibuja un gráfico real. N3 («producción mes a mes») se renderiza como
barras de `div`, y N4 («variación mensual») como lista de texto `Ene → Feb ▼ -218.586 (-64.3%)`.

El objetivo es que **el contenido gráfico del panel sea dinámico y acotado a lo que se pregunta**:
mismo layout, pero con el pintor y la granularidad que corresponden al nivel.

| Pregunta | Nivel | Gráfico destino |
|---|---|---|
| «producción de Castilla mes a mes» | N3 | Línea mensual (cerrado sólido + proyección punteada) |
| «variación porcentual mensual de Pauto Sur» | N4 | **Waterfall** (cascada) de los saltos mes a mes |

Fuera de alcance: N1, N2, N5 y el grano día (que ya funciona). Ver §10.

---

## 2. Decisiones del usuario (2026-08-25)

1. **Tarjeta KPI izquierda: adaptada al periodo.** → **Diferida a la Fase B.** La auditoría
   demostró que el donut es imposible con la fuente actual (§9, B-2) y que arrancar sin KPI
   elimina tres riesgos de golpe. La decisión se respeta, pero después de que el gráfico exista.
2. **N4 se dibuja como waterfall (cascada)**, no como columnas ± sueltas. Se mantiene.
3. **El gráfico reemplaza la tabla de texto.** Se mantiene, con una corrección: las cifras
   exactas van al **hover** (§4.4), no a un `<title>` — el mecanismo prometido en la rev. 1
   no existía.

---

## 3. Reglas del proyecto que gobiernan este trabajo

Verificadas en código. **Ninguna se negocia**; el diseño de §4 se deriva de ellas.

| Regla | Origen | Consecuencia aquí |
|---|---|---|
| **AF-3.2** — `ritmo_mensual` es REAL-only; la query filtra `es.nombre='REAL'` | `plan_cuantificar_fase3_2026-08-02.md:25`, `api.py:583` | **No hay PPTO mensual.** Sin donut de cumplimiento en N3/N4. Comparar vs PPTO exige otra query → Fase 4 |
| **HE4 / AF-3.3** — el mes en curso es PROYECCIÓN, no se suma | `niveles.py:5`, `:56` | «meses cerrados», «mejor mes» y «variación acumulada» deben excluir el mes proyectado |
| **Doble convención de producto** — llega `"GAS"` (v1) o `"gas"` (Motor Q v2); *ningún sitio debe indexar por clave literal* | `multitab_shell.js:2628-2632` | Todo acceso por producto pasa por `__cnProdId`. Es la razón de fondo por la que `__cnMonthlyPlot` no se reactiva |
| **Regla de oro del scroll único** — el único scroller del panel derecho es `.cn-col` | `colapsable.css:1403-1405`, `1453-1457` | Prohibido `overflow:auto` en el host del gráfico. Si no cabe, se comprime o se crece hacia abajo |
| **La pila NO es `.cn-desemp__scroll`** — sus reglas se replican con `max-height` + `overflow:visible` | `colapsable.css:1446-1460` | La altura del panel no se hereda sola. Ver §4.1 |
| **Constructores puros** — los `*Html` no tocan el DOM | `multitab_shell.js:3368-3371`, `3506-3508` | El hover del waterfall se cablea en el despachador, no en el constructor |
| **IDs dentro de `blk`** — `querySelector`, nunca `getElementById` | `multitab_shell.js:1838`, `:4686-4688` | Evita colisión tablero ↔ bloques apilados |
| **Coherencia chat ↔ tablero** — misma cifra en ambos | `ejecutor.py:6-7` | Usar `datos.promedio` tal cual; no recalcular |

---

## 4. Diseño

### 4.1 Altura y envoltorio — se resuelve PRIMERO

La rev. 1 proponía emitir `<div class="cn-compprod__grid">` a secas. **Habría fallado en silencio:**
la regla de altura es `.cn-desemp__scroll .cp-foco__panel .cn-compprod__grid { height:375px }`
(`colapsable.css:2435`) y exige dos ancestros que la pila no tiene. Sin altura, Plotly monta sin
lienzo y `__cnPlotResize:1982` sale por `if (!elp.offsetWidth || !elp.offsetHeight) return;`
— sin excepción, sin pista.

**Solución (cero CSS nuevo):** emitir el mismo envoltorio que ya usa `__cnCompProdHtml:2954-2959`:

```
<div class="cp-foco" style="--cp-prod:{color};--cp-prod-soft:{soft}">
  <div class="cp-foco__panel is-active">
    <div class="cn-compprod__grid cn-compprod__grid--solo" data-prod="{producto}">
      <div id="cn-serie-mes-{seq}" class="cn-ins"></div>
    </div>
  </div>
</div>
```

`.cp-foco__panel .cn-ins { height:100% }` (`colapsable.css:1838-1840`) da la altura sin depender
de `.cn-desemp__scroll`. Se hereda además el color de producto por variable CSS.

Si al medir en vivo la altura no resulta correcta, la alternativa es replicar
`colapsable.css:1461-1465` con prefijo `.cn-stk__body` — el precedente exacto de `analiza_foco`,
con `max-height` y `overflow:visible`. **No `overflow:auto`** (regla de oro).

> **Arranque en `--solo`.** Sin tarjeta KPI, el gráfico ocupa el 100% del ancho en vez del 70%.
> Ya está soportado (`colapsable.css:2426`, `__cnCompProdHtml:2953`). Esto además da al waterfall
> ~40% más de ancho por barra, que es justo lo que necesita (§4.4).

### 4.2 Backend — cambios

**a) `niveles.py:85` — exponer la serie en `variacion()`**

Nombrarla **`puntos`** internamente, como ya hace `serie()` (`niveles.py:68`). La traducción al
nombre público ocurre en el ejecutor, igual que en N3.

```python
return {"aplica": True, "puntos": puntos, "deltas": deltas, "ultimo": deltas[-1],
        "anio": anio, "proyeccion_mes": proy}
```

`puntos` ya está calculado en `:74` y se descartaba. Coste cero.

**b) `ejecutor.py:254` — propagar como `serie`, NO como `puntos`**

🔑 `ejecutar_n3:222` ya renombra `s["puntos"]` → `"serie"` al salir. **N4 debe usar el mismo
nombre público** o el panel tendría dos nombres para la misma cosa (`datos.serie` en N3,
`datos.puntos` en N4) y el frontend necesitaría dos rutas de datos para una serie idéntica.

```python
"serie": r["puntos"], "deltas": r["deltas"], ...
```

**c) `_serie_puntos` (`niveles.py:44-58`) — exponer `meses_num` y `mes_actual`**

Ambos están en `ritmo` (`:50`) y se descartan. Sin ellos, el frontend tendría que invertir
`proyeccion_mes` (string `"Ago"`) a número con un mapa frágil. Devolverlos es coste cero y
elimina esa traducción. Propagar en las ramas N3 y N4 de `_panel_datos`.

**d) `respuesta_cuantificar.py:109-114` — payload de N3/N4**

- N3: añadir `meses_num`, `mes_actual`. `serie`, `promedio`, `anio`, `proyeccion_mes` ya viajan.
- N4: añadir `serie`, `meses_num`, `mes_actual`.
- **NO añadir `productos`.** Es redundante: el filete se inyecta leyendo `[data-prod]` del HTML
  (`multitab_shell.js:3375-3377`) y `d.producto` ya viaja (`:89`). `productos` solo existe en
  N1D/N1DSEL porque su placeholder lo consume (`:2967`).
- `_PANEL_TIPO` (:46): **sin cambios.** Se conservan `cuant_serie` y `cuant_var`. Cambia el
  pintor, no el tipo — ruta incremental, no se toca el dispatcher de los demás niveles.

**e) `_kpi_periodo` — NO en esta fase.** Ver §10, Fase B.

### 4.3 N3 — pintor nuevo sobre el molde de `__cnDailyPlot`

**`__cnMonthlyPlot` (:2362) NO se reactiva.** Tiene tres fallos mudos con el payload del Motor Q:

- `:2366`/`:2368` indexan `rm.series[producto]` por clave literal. El backend manda `"crudo"`
  (minúscula), `ritmo_mensual` tiene `"CRUDO"` → array vacío, **sin error**. Es la trampa que
  `multitab_shell.js:2628-2632` documenta y prohíbe.
- `:2371` `esGas = producto === "GAS"` → falso con `"gas"`; el gas se grafica sin escalar (V-3).
- `:2383` lee `d.mes.anio`, que `_panel_datos` no propaga.

Un adaptador tendría que normalizar el caso, sintetizar `meses_num`, invertir `proyeccion_mes` y
falsificar `d.mes` — cuatro traducciones sobre una función cuyos fallos son todos silenciosos.
**Se escribe `__cnSerieMesPlot` nuevo con `__cnDailyPlot` (:1909) como molde**, que está
totalmente desacoplado: recibe `(elp, labels, valores, ref, unidad, esGas, …)` — arrays y
escalares, `esGas` como booleano del caller, cero indexación por clave. Hereda gratis `holgura`
(:1932) y `ejes` (:1952), añadidos en el plan antecedente como aditivos.

- **Eje X:** categórico con los nombres de mes (`Ene`, `Feb`, …), como el diario usa el nº de día.
- **Tramo proyectado:** trace secundario punteado desde `mes_actual`, replicando `__cnMonthlyPlot:2389`
  pero con el índice que ahora llega del backend.
- **Referencia:** `datos.promedio` **tal cual** — ya es media de meses cerrados (`api.py:596`,
  excluye el mes en curso). Recalcular `sum/len` incluiría la proyección y daría un número
  distinto al del tablero, rompiendo la coherencia de `ejecutor.py:6-7`.
- **Color e identidad:** vía `__cnProdCol` / `__cnProdId` (:2634), nunca por clave literal.
- **Título:** en el tono real del molde — `__cnDailyInto:1856` hace Title Case y **minúsculas**
  en el resto (`"Crudo · producción diaria del mes de agosto…"`). No hay `text-transform` en
  `.cn-ins__card-hd`. Aquí: `"Crudo · producción mensual 2026 vs promedio"`.

### 4.4 N4 — `__cnVarWaterfallSVG` (nueva)

Gemela de `__cnWaterfallSVG` (:4481), no una llamada a ella: la original tiene el esquema EBITDA
cableado (bandas con índices fijos :4536-4538, formato `$`/KUSD :4520-4531, `H=480`).

- **Componentes:** `[{total, "ene", nivel}, {delta, "ene→feb", d}, …, {total, "ago", nivel}]`
  desde `serie` + `deltas`.
- **Se conserva:** acumulado (:4493-4504), dominio/escala (:4506-4511), conectores punteados, grid.
- **Se descarta:** bandas EBITDA, formato monetario, gradiente `lerpTotal`.
- **Colores:** hex literal inline, como ya hace `__cnWaterfallSVG:4577-4578`. ⚠️ `.cq-delta.is-up`
  es `color:` (texto); un `<rect>` necesita `fill:` — no se hereda por cascada, se copia el valor.
- **Alto:** `VMB=120` del original deja solo 215px útiles de 375. **Etiquetas horizontales
  cortas** (mes destino: `Feb`, `Mar`, …) en vez de rotadas −40°, lo que permite bajar `VMB` a
  ~40 y recuperar ~80px de gráfico. Sin `overflow-x` (regla de oro).
- **Etiqueta sobre la barra:** `+x%` / `−x%` — es lo que se pregunta.
- **Formato:** `__cnMilesEC(n)` (:1964) / `__cnGasM(v, dec)` (:2604), ambas puras, sin sufijo de
  unidad. ⚠️ `:3650-3652` documenta un bug de doble escalado con `__cnGasM`: si el backend ya
  escaló, no volver a pasar por ella.
- **Mes proyectado:** el último salto lleva trama o borde punteado, coherente con N3.

**Hover.** El waterfall SVG no tiene tooltip propio: `__cnWaterfallSVG` solo escribe
`data-label`/`data-val` en cada rect (:4581) y el tooltip lo cablea `__cnEbBindHover` (:4651-4667)
con `addEventListener`, sobre un `div.cn-wf__hover` fijo en la esquina (`colapsable.css:1720`).
Dos consecuencias:

1. El binding va **en el despachador**, no en el constructor (regla de constructores puros).
2. N3 (Plotly, hover flotante que sigue al cursor) y N4 (tarjeta fija en esquina) darían dos
   interacciones distintas a dos preguntas casi idénticas. **Decisión: reusar el patrón
   `cn-wf__hover` existente** — es el precedente del proyecto y no inventa mecanismo. Si en la
   validación resulta molesto en 375px, la alternativa es etiqueta permanente sobre cada barra
   (el `%` ya va ahí) y prescindir del hover.

### 4.5 Despacho — replicar el patrón completo, no una llamada suelta

El dispatcher (`:3403` `appendChild`, `:3409`/`:3411`/`:3414`) llama **síncronamente** tras
insertar. La asincronía de los tres casos actuales viene de su `fetch`, no de un diferimiento.
N3/N4 **no tienen fetch** — los datos ya están en `panel.datos` — así que el pintor corre
inmediatamente. Eso funciona salvo en un camino soportado: cuando `__cnStackEnsure()` devuelve un
`DocumentFragment` (`:2984-2986`, pestaña fuera de pantalla), `blk.isConnected === false`,
`offsetHeight` es 0 y Plotly monta un plot de tamaño cero.

**Hay que replicar el guardián de `__cnCompProdCargar:3300-3309`:** comprobar `blk.isConnected`;
si no, marcar `blk.dataset.pendPaint="1"` y dejar el payload en el nodo para el repintado.

⚠️ El repintado de `multitab_shell.js:454` llama a `__cnPaintFocoStk`, que solo conoce
`#cn-foco-day-` / `#cn-foco-mon-` (`:1844-1845`). **Un panel mensual nuevo no se restauraría por
ese camino** — hay que extender `:454` o darle su propia rama. La rev. 1 no lo contemplaba.

**IDs:** sufijo `"-stk" + __cnStackSeq` (el contador global de `:3353`), y búsqueda con
`blk.querySelector("#…")`, nunca `getElementById` (`:1838`).

**Colisión con `__cnCompProdMarcarDia` (:3245):** busca `.cn-ins .cn-ins__plot` **dentro de `blk`**,
así que no salta entre bloques de la pila. Y solo se invoca desde `__cnCompProdCargar:3302`, que
solo corre para `cuant_dia_panel`. **El riesgo real es nulo mientras N3/N4 no reusen
`__cnCompProdCargar`** — que es el diseño. La clase `cn-ins--mes` que proponía la rev. 1 no
protegía de nada: `class="cn-ins cn-ins--mes"` sigue casando con `.cn-ins`.

---

## 5. Orden de trabajo

El orden de la rev. 1 era inviable: ponía el CSS al final, y sin altura el paso de validación no
puede ejecutarse.

| # | Paso | Entregable |
|---|---|---|
| **1** | **Envoltorio y altura** (§4.1) | Un bloque N3 vacío en la pila con altura correcta, medida en el DOM |
| **2** | Backend: `puntos`→`serie` en N4, `meses_num`/`mes_actual`, payload (§4.2) | Payload completo, tests verdes |
| **3** | N3: `__cnSerieMesPlot` + despacho con guardián (§4.3, §4.5) | **Punto de control — validar en vivo** |
| **4** | N4: `__cnVarWaterfallSVG` + hover (§4.4) | |
| **5** | Limpieza CSS de `cq-*` huérfanas (§8) y tests | ✅ |

**Estado: los cinco pasos ejecutados (2026-08-25/26).** Resumen de lo que cambió respecto a lo
planificado, todo por medición y no por criterio:
- El envoltorio **no bastaba** para la altura: hizo falta una regla nueva con clase propia
  `--mes` (§6.1).
- Las etiquetas del waterfall pasaron de mes pelado a **`→Mes` en los deltas**: con el mes solo,
  el último salto y el nivel de cierre salían como dos «Ago» seguidos.
- El `%` se fuerza a **un decimal** (`+6,0%`, no `+6%`): JSON entrega `6.0` como `6`.
- La limpieza CSS retiró **12** reglas, no 7: la auditoría se equivocó sobre tres de ellas (§8).

**Punto de control tras el paso 3.** Se valida el gráfico mensual en `--solo` antes de escribir el
waterfall. Se mide en el DOM, no se supone — el paso 1 existe precisamente porque el fallo de
altura es mudo. Criterio de «medir, no suponer» ya establecido para el frontend de este proyecto.

---

## 6. Validación

### 6.1 Medición del paso 1 — HECHA (2026-08-25)

Chrome headless sobre la app local, midiendo variantes del envoltorio dentro de `#cn-stack`:

| Variante | grid | plot | SVG de Plotly | Scroller anidado |
|---|---|---|---|---|
| **Candidato §4.1 + clase `--mes`** | **375px** | **327px** | 663×327 | ninguno ✅ |
| Envoltorio §4.1 SIN `--mes` (= panel de día hoy) | 168px | 120px | 663×120 | ninguno |
| Grid pelado (propuesta rev. 1) | 20px | 8px | 717×**10** | — |

Dos correcciones sobre lo que decía la rev. 2 antes de medir:

1. **El criterio «≈375px» estaba mal derivado.** Los 375px son del TABLERO (`colapsable.css:2435`).
   El envoltorio por sí solo da 168px: el plot cae en el `min-height:120px` de `:1840`, que es
   suficiente para tener lienzo pero estrecho para 12 meses con ejes, y no le sirve al waterfall.
   Hizo falta **una regla nueva** — no bastaba con el envoltorio, como suponía §4.1.
2. **Se añadió la clase propia `.cn-compprod__grid--mes`** en vez de tocar el selector general:
   el panel de grano DÍA usa el mismo grid en la pila y **hoy mide 168/120**. Igualarlo sería
   una mejora, pero es otra decisión y este plan no la toma (ver §11).

La propuesta descartada de la rev. 1 queda confirmada como fallo mudo: 20px de grid y un SVG de
10px de alto, sin una sola excepción en consola.

### 6.1 bis — Estado de la validación (2026-08-25, tras el paso 3)

⚠️ **El entorno local no tiene datos para N3/N4 ni para el panel de día.** Medido:
`/api/analisis/desempeno` de CASTILLA devuelve `sin_cierre: true` y `ritmo_mensual` VACÍO
(`meses: []`, `series` a `[]`); `por_producto` trae `real: 0.0` en los tres productos, y los 3
focos de `/api/analisis/ejecutivo` llegan como «Sin producción». Consecuencia: N3/N4 rechazan
honestamente («No tengo serie mensual de crudo para CASTILLA») y el panel de día se queda en
«Sin datos de comportamiento». Es coherente con los 4 tests `test_bd_real_*` que ya fallaban
antes de tocar nada (verificado con `git stash`).

Por eso el pintado se validó **interceptando `/api/consulta2/preguntar`** con un payload fiel al
contrato de `_panel_datos`, dejando correr el resto del camino real (dispatcher → constructor →
guardián → pintor). Lo que eso NO cubre: la lectura de datos reales, que queda cubierta por los
tests unitarios con fixture.

### 6.2 Casos en vivo

| # | Pregunta | Esperado |
|---|---|---|
| V-1 | «producción de Castilla mes a mes» | Línea mensual a ancho completo; último mes punteado (proyección); línea de promedio = `datos.promedio` |
| V-2 | «para campo Pauto Sur muéstrame la variación porcentual mensual en la producción» | Waterfall; barras ± con `%`; totales a los extremos; etiquetas horizontales sin solape |
| V-3 | «producción de gas de Cusiana mes a mes» | Unidad MSCF, escala correcta (**no** ×1e6), filete GAS. Caso que rompía con `__cnMonthlyPlot` |
| V-4 | Entidad con <2 meses | N4 rechaza con `niveles.py:76-78`, sin panel |
| V-5 | «el 15 de mayo cuánto produjo Castilla» | **Sin regresión**: curva diaria con punto amarillo |
| V-6 | «acumulado del año» / ranking | **Sin regresión**: renderer actual |
| V-7 | Panel N3 en pestaña **fuera de pantalla**, luego volver | Se repinta (guardián de §4.5). Caso que la rev. 1 no contemplaba |
| V-8 | Dos bloques en la pila: uno de día, otro mensual | El punto amarillo va solo al de día |
| V-9 | Ancho <1024px | Grid a 1 columna; el waterfall no desborda ni crea scroller |

**Estado medido (2026-08-25, tras el paso 3):**

| # | Estado | Evidencia |
|---|---|---|
| V-1 | ✅ | grid 375 / plot 327 / SVG 663×327; 2 traces con `dash=dot` en el 2.º; sólido `Ene…Jul`, punteado `Jul→Ago` |
| V-3 | ✅ | `y[0][0] = 36.7` (no 36 700 000); ticks Y `0,10,20,30,40`; `--cp-prod=#EF4444`. Es el caso que rompía con `__cnMonthlyPlot` |
| V-4 | ✅ | por test unitario (`niveles.variacion` con <2 puntos) |
| V-5 | ⚠️ no pintable en local (§6.1 bis) | Verificado por tres vías indirectas: el backend devuelve `cuant_dia_panel` correcto (curl real); su CSS mide 168/120, **idéntico** a antes (la clase `--mes` no le aplica); y ningún cambio toca su camino (`__cnCompProdPlaceholderHtml`/`__cnCompProdCargar` intactos) |
| V-6 | ✅ | el backend devuelve `cuant_rank` íntegro (curl real); sus renderers no se tocaron |
| V-7 | ❌ **sin validar** | No se logró provocar el `DocumentFragment` en headless. El guardián y la rama de `:454` están escritos, pero **sin ejercitar** |
| V-8 | ✅ | el bloque mensual queda con 2 traces y **0 trazas de 1 punto**; `hosts .cn-serie-mes` = 0 dentro del bloque de día |
| V-2 | ✅ | 9 barras (2 totales + 7 deltas); etiquetas X **horizontales, 0 solapes**; SVG 663×327 sin desbordar; proyección marcada en 2 barras; hover activo; gas en MSCF (`36,7` / `24,3`, no 36 700 000) |
| V-9 | ⚠️ **preexistente, no es regresión** | A 900px **`.cn-stack` mide 0** y con él todos sus descendientes — y le pasa **idéntico al panel de día** (medido lado a lado). El shell colapsa la pila entera por debajo de 1024px. La regla `--mes` sigue aplicando (`computed.height: 375px`), pero su contenedor no tiene alto. Fuera de alcance: arreglar el responsive del shell es otro trabajo |

Comprobado además en V-1/V-3: el filete de producto se hereda solo (`data-prod` → `cn-stk--prod`),
los **avisos se conservan** bajo el gráfico, el título sale en el tono del molde
(«Crudo · producción mensual 2026 vs promedio», Title Case + minúsculas) y **no se crea ningún
scroller anidado**.

### 6.3 Tests

Archivos reales (la rev. 1 nombraba `test_cuantificar_niveles.py`, que **no existe**):

- `INGESTA\Rep_Prod\backend\tests\test_cuantificar.py:424-453` — cubre `serie()`/`variacion()` y
  el dispatch `ejecutar_n3/n4`. Añadir: `variacion()` devuelve `puntos`, y
  `len(puntos) == len(deltas) + 1`.
- `INGESTA\Rep_Prod\backend\tests\test_cuantificar_dia.py:293-347` — cubre `_panel_datos`.
  Añadir: N3/N4 traen `serie`, `meses_num`, `mes_actual`; N4 usa **`serie`**, no `puntos`.
- Fijar que `_PANEL_TIPO["N3"] == "cuant_serie"` y `["N4"] == "cuant_var"` siguen intactos.

**Riesgo de romper lo existente: bajo, verificado.** Ningún test assertea claves exactas
(`set(keys())`); ningún golden fija la forma del panel — `run_golden_cuantificar.py:46-57` llama a
`extraer_slots` + `ejecutar` y **nunca construye panel**; `log.py:23-36` no persiste `panel`; no hay
modelo Pydantic para `panel`. Añadir claves es seguro. Y `desempeno()` se llama **una sola vez**
en N3/N4 (`niveles.py:47`) — coste de la propuesta: cero.

---

## 7. Riesgos

| Riesgo | Estado | Mitigación |
|---|---|---|
| Host sin altura → Plotly sin lienzo, **fallo mudo** | **Alto** | Paso 1 aislado + medición obligatoria (§6.1) |
| Panel no se repinta al volver de una pestaña oculta | **Medio** | Guardián `isConnected` + extender `:454` (§4.5) |
| Waterfall ilegible en 375px con 14 barras | **Medio** | Etiquetas horizontales cortas, `VMB` reducido, `--solo` da +40% de ancho |
| Hover incoherente entre N3 (Plotly) y N4 (SVG) | **Medio** | Patrón `cn-wf__hover` existente; si molesta, etiqueta permanente |
| Doble escalado de gas con `__cnGasM` | Bajo | Documentado en `:3650-3652`; verificar en V-3 |
| Perder cifras exactas al quitar la tabla | Bajo | Siguen en el texto de la respuesta y en el hover |

---

## 8. Limpieza

**Corrección (2026-08-25, al ejecutar).** La auditoría afirmaba que `.cq-card`, `.cq-hd` y
`.cq-unit` seguían en uso por `__cnCuantRankHtml`/`__cnCuantCardHtml` y que no debían tocarse.
**Es falso**, verificado en todo el repo (js y html): `__cnCuantCardHtml` emite la familia
`cp-mes__`/`cp-p50__` y `__cnCuantRankHtml` la familia `cn-rank__`. Ninguno emite una sola clase
`cq-*`.

Retiradas, por tanto, las **12** reglas que quedaron sin emisor: `.cq-card`, `.cq-hd`, `.cq-unit`,
`.cq-row`, `.cq-mes` (+`em`), `.cq-bar` (+`__fill`), `.cq-val`, `.cq-foot` y `.cq-delta`
(+`is-up`/`is-down`). Estas dos últimas tampoco se podían reusar en el waterfall: son `color:`
(texto) y un `<rect>` necesita `fill:`, así que el pintor lleva los hex literales.

**Conservada** `.cq-aviso`, y añadida `.cq-avisos` como contenedor bajo el gráfico.

Los **avisos** (`d.avisos`, incluido el de proyección de `ejecutor.py:246`) deben seguir
mostrándose bajo el gráfico: el gráfico reemplaza la tabla de cifras, **no las advertencias**.

---

## 9. Qué se descartó de la rev. 1 y por qué

| Propuesta rev. 1 | Veredicto | Evidencia |
|---|---|---|
| Donut de cumplimiento en el KPI de N3 | **Imposible** | `ritmo_mensual` es REAL-only (`api.py:583`); viola **AF-3.2** (`plan_cuantificar_fase3_2026-08-02.md:25`). Exige otra query → Fase 4 |
| Emitir `cn-compprod__grid` a secas | **Fallo mudo** | La altura exige `.cn-desemp__scroll .cp-foco__panel` (`colapsable.css:2435`); la pila no los tiene |
| Adaptador sobre `__cnMonthlyPlot` | **Invertido a plan B** | 3 fallos silenciosos: clave de producto (viola `:2628-2632`), `esGas`, `d.mes.anio` |
| `productos` en el payload N3/N4 | **Redundante** | El filete lee `[data-prod]` (:3375) y `d.producto` ya viaja (:89) |
| `puntos` como nombre público en N4 | **Incoherente** | `ejecutar_n3:222` ya publica `serie`; habría dos nombres para lo mismo |
| «meses cerrados» = `len(serie)` | **Viola HE4** | La serie incluye el mes proyectado (`niveles.py:53-57`) |
| `overflow-x:auto` si el waterfall no cabe | **Prohibido** | Regla de oro del scroll único (`colapsable.css:1403-1405`) |
| Clase `cn-ins--mes` para evitar el marcador | **No protegía** | `class="cn-ins cn-ins--mes"` sigue casando `.cn-ins`. La protección real es no reusar `__cnCompProdCargar` |
| Cifras exactas «al tooltip / `<title>`» | **Sin mecanismo** | El SVG no tiene tooltip; hay que cablear `cn-wf__hover` (:4651) |
| Título en MAYÚSCULAS «por CSS» | **No existe tal CSS** | `__cnDailyInto:1856` usa Title Case + minúsculas |
| CSS en el paso 4 | **Orden inviable** | Sin altura no se puede validar el paso 2 |
| Tests en `test_cuantificar_niveles.py` | **Archivo inexistente** | Son `test_cuantificar.py:424-453` y `test_cuantificar_dia.py:293-347` |

---

## 10. Fases posteriores

**Fase B — tarjeta KPI adaptada al periodo.** Decisión 1 del §2, diferida. Sin donut (AF-3.2).
Contenido posible, todo derivable de `serie` sin fetch:
- N3: promedio mensual (`datos.promedio`, ya viaja), meses **cerrados** (`len(serie) − 1` si hay
  `proyeccion_mes`), mejor/peor mes **excluyendo la proyección** (HE4).
- N4: variación acumulada (nivel final − inicial, advirtiendo que el final es proyección), meses
  al alza / a la baja, último cambio.

**Fase C — N1 / N2 con gráfico.** El dato está a un paso: `ejecutor.py:97` ya recibe
`ritmo_mensual` completo en N1 y solo le extrae el promedio; `niveles.py:24-36` recorre los 12
meses en N2 con el valor en la mano y solo acumula el escalar. ⚠️ N2 **sí** hace N+1 llamadas a
`desempeno()` — a diferencia de N3/N4 — así que ahí el coste no es cero.

**Fase D — N1DSEL sin round-trip.** `ejecutor.py:340-346` calcula la curva diaria completa del mes
para sacar el argmax y la descarta; el frontend la vuelve a pedir por HTTP a otro endpoint.

**Fase E — unificar en `cuant_panel`** con `datos.grafico = "linea_dia" | "linea_mes" |
"waterfall_var"` y un dispatcher de pintores. Destino natural si las fases cuajan; toca los seis
tipos existentes. No se hace mientras la ruta incremental avance.
