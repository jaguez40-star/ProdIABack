# Plan · Reformato de la tarjeta de ranking N5 (Cuantificar) — 2026-08-12 · **v2 AUDITADO**

**Objetivo:** llevar la tarjeta del ranking de producción al formato validado con el usuario:
dona a tamaño pleno con su leyenda compacta al costado, canal ancho entre las dos mitades,
filas del dot plot más aireadas, y sin la banda de concentración (redundante con el centro
de la dona).

**Maqueta aprobada:** https://claude.ai/code/artifact/ef9dea9f-f9b2-42c3-939c-65f341a17083
(muestra 2 variantes; **este plan implementa la VARIANTE B** — conserva el pie. Ver §0.4.)

**Alcance:** SOLO presentación. Cero backend, cero contrato del panel, cero recálculo de
cifras.

**Baseline:** HEAD `5710e7e`. `node --check static/js/multitab_shell.js` pasa limpio ANTES
de tocar nada (verificado al auditar).

---

## 0. AUDITORÍA — 6 hallazgos que cambian el plan v1

> Esta sección existe porque la v1 de este plan tenía **dos errores que habrían roto la
> tarjeta en producción** (A2 y A3) y cuatro imprecisiones. Léela antes de editar: los
> §1-§3 ya vienen corregidos, pero el *porqué* de las decisiones raras está aquí.

### A1 · `multitab_shell.js` tiene cache-buster PROPIO — la v1 lo dejó como "verificar"

`templates/main.html` tiene **tres** `?v=` distintos:

| Línea | Recurso | Valor actual |
|---|---|---|
| 5 | `css/colapsable.css` | `20260812a1` |
| **82** | **`js/multitab_shell.js`** | **`20260811s9`** |
| 89 | `js/panels.js` | `20250828001` |

Este cambio toca **CSS y JS**. Si solo se sube el del CSS, el navegador sirve el JS viejo
(dona de 130px) contra el CSS nuevo (grid de 180px) → **el círculo queda descentrado en su
celda y la maqueta no se reproduce**. Hay que subir **los dos** (§3).

### A2 · 🔑 `max-content` DESBORDA — el error más grave de la v1

La v1 prescribía `grid-template-columns: 180px max-content` para la leyenda. Medido contra
el ancho real disponible (rail + chat + paddings de `.cn-stack`/`.cn-stk`):

| Viewport | Ancho de la mitad derecha | ¿Alcanza? |
|---|---|---|
| 1280px | ~323 px | **NO** |
| 1366px | ~366 px | **NO** |
| 1440px | ~403 px | Sí (justo) |
| 1600px | ~483 px | Sí |
| 1920px | ~643 px | Sí |

La mitad derecha necesita **~380px** con los nombres de la captura, y **~451px** con el
nombre de campo más largo del catálogo real (`PALERMO-SANTA CLARA UNIFICADO`, 29 chars,
verificado en `data/Activo_campo.csv`; el ranking soporta nivel **campo Y activo**, así que
esos nombres SÍ pueden aparecer).

🔑 **`max-content` no cede: empuja.** No se recorta con ellipsis — desborda la celda del
grid. Y como el panel es una **pila acumulativa** (`__cnPintarPanelCuant`, varias tarjetas
apiladas en `.cn-col`), un desbordamiento no queda contenido en una tarjeta: ensancha la
columna entera y mete scroll horizontal donde hoy no lo hay.

**Corrección:** `minmax(0, max-content)` — compacta cuando hay espacio, **cede cuando no**,
y ahí sí entra a trabajar el `text-overflow: ellipsis` que `.cn-dona__leg-name` ya tiene.
Los nombres de entidad ya llevan `title=` (`multitab_shell.js:2922`) → al recortarse se leen
con el cursor encima. **Ninguna cifra se pierde nunca**: `.cn-dona__leg-pct` es `flex:0 0 auto`.

### A3 · El umbral responsive de 1280px queda MAL con el nuevo tamaño

La v1 decía "verificar, probablemente ajustar". La medición de A2 lo convierte en un hecho:
**la franja 1281-1439px es exactamente donde el layout de 2 columnas sigue activo pero ya no
cabe** — y 1366px es una resolución de portátil corporativo muy común.

Además, 1280 es un **outlier**: todos los demás breakpoints del panel están en 720/900/980
(`colapsable.css`: L1044, 1098, 1138, 1294, 1311, 1421, 1448, 1696).

**Corrección:** subir el umbral a **1440px** (§2.3). Por debajo, la dona baja bajo el dot
plot y dispone del ancho completo, que es el comportamiento sano.

### A4 · Qué se elimina y qué NO — la decisión de honestidad del dato

Se retira la **banda de concentración** (`.cn-dot__bandwrap`), que dice
«Top 5 concentra **41,2%**» + «123 campos restantes».

- El **41,2%** ya está en el centro de la dona → la banda lo repetía. Quitarlo no pierde nada.
- El **conteo del universo** es lo que sostiene que «los 5 mayores» diga *sobre cuántos*.
  **Por eso `.cn-dot__foot` SE CONSERVA** («N campos con producción registrada»).

⚠️ **NO retirar también el pie.** Es la diferencia entre la variante A y la B de la maqueta;
la decisión tomada es **B**. V3 lo verifica con grep.

### A5 · El `margin: 0 auto` del SVG cambia de semántica al volverse grid item

`.cn-dona__svg` hoy es `display:block; margin: 0 auto` — así se centra en el flujo de bloque.
Dentro de un grid, `margin:auto` **centra el elemento en su celda**, y además un `<svg>` con
atributos `width`/`height` puede estirarse con `justify-self:stretch` (el default).

**Corrección:** retirar `margin:0 auto` y fijar `justify-self: start` (§2.2). Sin esto, el
círculo flota descentrado respecto de la leyenda.

### A6 · Aislamiento verificado — lo que este cambio NO puede romper

Auditado en todo el repo:

- **Cero colisiones de selector**: las 11 reglas `.cn-dona*` existen una sola vez
  (`colapsable.css:1967-1978`). `Colapsable/static/css/colapsable.css` es un sandbox viejo
  que **no se sirve** (`main.html:5` solo carga `static/css/`).
- **Cero reglas ancestro** sobre hijos de `.cn-dot__cols`/`.cn-stk`/`.cn-col` que toquen
  `display/width/margin/flex/grid`.
- **Cero selectores de tipo `svg {}`** globales en el proyecto.
- `__cnDonaHtml` se llama **en un solo sitio** (`multitab_shell.js:2871`).
- Las clases de la banda (`cn-dot__band*`) y el pie (`cn-dot__foot`) las emite **solo**
  `__cnRankDotHtml`.
- **Las otras 3 ramas de ranking no se tocan** y no comparten clases:

  | Rama del dispatcher (L2633-2639) | Función | Familia CSS | ¿Dona? |
  |---|---|---|---|
  | `cuant_rank` + `metrica=="real"` | `__cnRankDotHtml` | `.cn-dot*` | **Sí ← la que cambia** |
  | `cuant_rank` + `metrica=="gap"` | `__cnCuantRankHtml` | `.cn-rank*` | No |
  | `jerarq_rank` | `__cnJerRankHtml` | `.cn-rank*` | No |

- **No hay harness versionado que actualizar** (no existe `package.json` en la raíz, ni un
  solo `.js` de test comiteado). La convención del proyecto es crear el harness **efímero en
  el scratchpad** por tarea — ver §4/V4.
- Los tests Python de ranking (`backend/tests/test_cuantificar_ranking.py`) validan el
  **backend** y **no requieren cambios**.

### A7 · Regla de oro del scroll (vigente, no romper)

El **único scroller del panel derecho es `.cn-col`** (`colapsable.css:1372`). Ni `.cn-dot`,
ni `.cn-dot__cols`, ni `.cn-dona` pueden ganar `overflow` propio. Esto es justamente lo que
hace que A2 fuera grave: sin overflow que lo absorba, un desbordamiento se propaga.

---

## 1. Cambios en `static/js/multitab_shell.js`

### 1.1 Geometría de la dona — `__cnDonaHtml`, L2907

**Buscar:**
```js
    var size = 130, r = 52, cx = size / 2, cy = size / 2, circ = 2 * Math.PI * r, sw = 20;
```

**Reemplazar por:**
```js
    // [2026-08-12] Dona a tamaño pleno (130→180): al repartirse la tarjeta 50-50, el círculo
    // de 130 flotaba en una columna que le sobraba. A 180 ocupa su mitad y los arcos de los
    // campos chicos (≈6%) se distinguen como segmentos propios. r y sw crecen en proporción
    // (sw/r pasa de 0,385 a 0,389 — mismo grosor relativo). circ se DERIVA de r, así que los
    // dasharray del bucle de arcos siguen cerrando en 100% exacto sin tocar una sola línea.
    var size = 180, r = 72, cx = size / 2, cy = size / 2, circ = 2 * Math.PI * r, sw = 28;
```

**Por qué es seguro (auditado):** todos los valores geométricos del SVG se derivan de
`size/r/cx/cy/circ/sw`. Los **únicos 5 hardcodeados** están en los dos `<text>` del centro y
se corrigen en §1.2. Verificado que a `r=72` los arcos suman `452,39` = circunferencia
exacta, en tres escenarios (captura real, top-5 concentrado, y el borde con «Otros» al 0%).
Holgura del anillo: borde exterior a `72+14=86` sobre un radio de caja de `90` → 4px de
margen (hoy son 3px, o sea mejora).

### 1.2 Tipografía del centro de la dona — L2948-2951

Los dos `<text>` tienen `font-size` y desplazamientos calibrados para 130px; a 180 quedarían
diminutos dentro del hueco.

**Buscar:**
```js
        '<text x="' + cx + '" y="' + (cy - 4) + '" text-anchor="middle" dominant-baseline="central" ' +
          'font-size="20" font-weight="800" fill="#17241E">' + centroTxt + '%</text>' +
        '<text x="' + cx + '" y="' + (cy + 14) + '" text-anchor="middle" dominant-baseline="central" ' +
          'font-size="9" font-weight="700" letter-spacing="0.6" fill="#98A69E">TOP ' + items.length + '</text>' +
```

**Reemplazar por:**
```js
        '<text x="' + cx + '" y="' + (cy - 5) + '" text-anchor="middle" dominant-baseline="central" ' +
          'font-size="27" font-weight="800" fill="#17241E">' + centroTxt + '%</text>' +
        '<text x="' + cx + '" y="' + (cy + 19) + '" text-anchor="middle" dominant-baseline="central" ' +
          'font-size="11" font-weight="700" letter-spacing="0.8" fill="#98A69E">TOP ' + items.length + '</text>' +
```

⚠️ Los desplazamientos siguen siendo **relativos a `cy`** (`cy - 5`, `cy + 19`), nunca
absolutos: si mañana cambia `size`, el texto sigue centrado solo.

### 1.3 Retirar la banda del render — `__cnRankDotHtml`

**(a) Comentar la variable.** Buscar (L2847, la línea que abre el bloque):
```js
    var banda = "";
```
**Reemplazar por:**
```js
    // [2026-08-12] `banda` queda CONSTRUIDA pero FUERA del render (ver el return, abajo): su
    // cifra duplica el centro de la dona. Se conserva el cálculo para poder reactivarla sin
    // rehacerlo. `restantes` (dentro) queda igualmente sin consumir — código muerto deliberado.
    // No hay linter sobre static/js/ (el único eslint.config.js es del frontend React de
    // INGESTA, otro proyecto), así que no rompe ningún gate.
    var banda = "";
```

**(b) Sacarla del return.** Buscar (L2880-2881):
```js
    return '<div class="cn-dot" data-prod="' + esc(d.producto || "") + '">' +
      ctx + rowsBlock + banda + leyenda +
```
**Reemplazar por:**
```js
    // [2026-08-12] Sin `banda`: decía "Top 5 concentra 41,2%", el MISMO número que ya ocupa el
    // centro de la dona. El conteo del universo NO se pierde — sigue declarado en .cn-dot__foot
    // ("N campos con producción registrada"), que es lo que sostiene sobre cuántos se rankea.
    return '<div class="cn-dot" data-prod="' + esc(d.producto || "") + '">' +
      ctx + rowsBlock + leyenda +
```

⚠️ **NO borrar el bloque que construye `banda`** (L2848-2855). Dejarlo vivo es deliberado
(documenta el dato disponible y permite reactivarlo con una palabra).

⚠️ **NO tocar `.cn-dot__foot`** en la línea siguiente del mismo `return` (L2882-2883).

### 1.4 Lo que NO se toca en el JS

- El bucle de arcos y el cálculo de participaciones (L2909-2939) — **ni una línea**.
- `.cn-dona__legend` y su contenido: se sigue emitiendo igual. Su nueva posición es 100% CSS.
- La rama `items.length === 1` (L2794-2802): no pinta dona.
- `__cnCuantRankHtml` y `__cnJerRankHtml`: otras familias CSS (A6). **Fuera de alcance.**

---

## 2. Cambios en `static/css/colapsable.css`

### 2.1 Canal entre mitades y aire entre filas

**Buscar (L1963):**
```css
.cn-dot__cols { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 14px; align-items: start; }
```
**Reemplazar por:**
```css
/* [2026-08-12] gap 14→46: el canal ancho es lo que hace que el dot plot (magnitud en bbl) y la
   dona (participación en %) se lean como DOS bloques y no como un continuo. El espacio sale de
   compactar la leyenda de la dona (ver .cn-dona), no de estrechar el dot plot. */
.cn-dot__cols { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 46px; align-items: start; }
```

**Buscar (L1926-1927):**
```css
.cn-dot__row { display: grid; grid-template-columns: 150px 1fr 78px; align-items: center; gap: 10px;
  padding: 5px 0; }
```
**Reemplazar por:**
```css
/* [2026-08-12] padding vertical 5→10: deja respirar el subtítulo de operador (.cn-dot__op) de
   los campos de terceros, que antes quedaba pegado a la fila siguiente. */
.cn-dot__row { display: grid; grid-template-columns: 150px 1fr 78px; align-items: center; gap: 10px;
  padding: 10px 0; }
```

### 2.2 🔑 Dona y leyenda lado a lado (el cambio central)

**Buscar (L1967-1978), el bloque COMPLETO:**
```css
.cn-dona { min-width: 0; }
.cn-dona__hd { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .03em;
  color: #8A968E; margin-bottom: 8px; text-align: center; }
.cn-dona__svg { display: block; margin: 0 auto; }
.cn-dona__legend { margin-top: 10px; display: flex; flex-direction: column; gap: 4px; }
.cn-dona__leg-row { display: flex; align-items: center; gap: 6px; font-size: 10.5px; color: #3C4A44; }
.cn-dona__sw { flex: 0 0 auto; width: 8px; height: 8px; border-radius: 2px; }
.cn-dona__sw--otros { background: #D8DCD9; }
.cn-dona__leg-name { flex: 1 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap; }
.cn-dona__leg-pct { flex: 0 0 auto; font-weight: 700; font-variant-numeric: tabular-nums;
  color: #2f3d37; }
```

**Reemplazar por:**
```css
/* [2026-08-12] Dona (izq) + leyenda (der) LADO A LADO, antes apiladas verticalmente.
   🔑 Va con grid-template-areas y NO con grid-template-columns a secas: __cnDonaHtml emite TRES
   hijos HERMANOS (__hd, <svg>, __legend) sin envoltorio, así que una rejilla de 2 columnas
   metería el encabezado como primera celda, al lado del círculo. Con áreas, __hd ocupa una fila
   entera y svg+legend comparten la segunda → layout resuelto SIN tocar el DOM del JS.
   🔑 La 2ª columna es minmax(0, max-content), NUNCA max-content a secas: max-content no cede,
   EMPUJA. Medido, la mitad derecha necesita ~380px (y ~451px con "PALERMO-SANTA CLARA
   UNIFICADO", el campo de nombre más largo del catálogo) mientras que entre 1280 y 1440px de
   viewport solo dispone de ~323-403px. Como el panel es una pila acumulativa sin overflow
   propio (regla de oro: el único scroller es .cn-col), ese desbordamiento ensancharía la
   COLUMNA ENTERA. Con minmax, la leyenda compacta cuando cabe y cede cuando no, dejando
   trabajar al text-overflow:ellipsis de .cn-dona__leg-name (los nombres llevan title= → se leen
   con el cursor encima). El % nunca se recorta: .cn-dona__leg-pct es flex:0 0 auto. */
.cn-dona { min-width: 0; display: grid; grid-template-columns: 180px minmax(0, max-content);
  grid-template-areas: "hd hd" "svg legend"; gap: 0 18px; align-items: center;
  justify-content: start; }
.cn-dona__hd { grid-area: hd; font-size: 10px; font-weight: 700; text-transform: uppercase;
  letter-spacing: .03em; color: #8A968E; margin-bottom: 10px; text-align: left; }
/* justify-self:start + sin margin:auto — como grid item, el margin auto de antes lo centraría
   en su celda y el atributo width del <svg> podría estirarse con el justify-self:stretch
   por defecto. */
.cn-dona__svg { grid-area: svg; display: block; justify-self: start; }
.cn-dona__legend { grid-area: legend; display: flex; flex-direction: column; gap: 7px;
  min-width: 0; }
.cn-dona__leg-row { display: flex; align-items: center; gap: 9px; font-size: 11.5px; color: #3C4A44; }
.cn-dona__sw { flex: 0 0 auto; width: 10px; height: 10px; border-radius: 2px; }
.cn-dona__sw--otros { background: #D8DCD9; }
.cn-dona__leg-name { flex: 1 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap; }
.cn-dona__leg-pct { flex: 0 0 auto; margin-left: 14px; font-weight: 700;
  font-variant-numeric: tabular-nums; color: #2f3d37; }
```

**Declaraciones que NO son cosméticas — deben quedar literales:**

| Declaración | Por qué | Si falta |
|---|---|---|
| `grid-template-areas: "hd hd" "svg legend"` | Único modo sin envoltorio nuevo (§0/A6) | El encabezado se va al lado del círculo |
| `minmax(0, max-content)` | Compacta pero cede (A2) | **Desborda la columna entera** en 1280-1440px |
| `justify-content: start` | El grid no se estira | Reaparece el vacío que se quiso quitar |
| `justify-self: start` en `__svg` | Sustituye al `margin:0 auto` (A5) | Círculo descentrado o estirado |
| `gap: 0 18px` | Fila 0 (`__hd` ya tiene `margin-bottom`), columna 18 | Doble separación bajo el encabezado |
| `align-items: center` | Alinea la leyenda con el centro del círculo | Leyenda pegada arriba |

### 2.3 Umbral responsive: 1280 → 1440px

**Buscar (L1965):**
```css
@media (max-width: 1280px) { .cn-dot__cols { grid-template-columns: 1fr; } }
```
**Reemplazar por:**
```css
/* [2026-08-12] Umbral 1280→1440: con la dona a 180px la mitad derecha pide ~380px (dona 180 +
   gap 18 + leyenda ~182), y entre 1280 y 1440px de viewport solo dispone de ~323-403px una vez
   descontados el rail, el chat y los paddings de .cn-stack/.cn-stk. La franja 1281-1439 era
   justo donde las 2 columnas seguían activas SIN caber — y 1366px es un portátil corporativo
   típico. Por debajo del umbral la dona baja bajo el dot plot y usa el ancho completo. */
@media (max-width: 1440px) { .cn-dot__cols { grid-template-columns: 1fr; } }
```

Además actualizar el comentario del bloque **L1957-1962**, que sigue diciendo «1280px»:
sustituir esa cifra por **1440px** en el texto.

### 2.4 Lo que NO se toca en el CSS

- `.cn-dot__bandwrap/__band/__bandfoot` (L1943-1947): se dejan aunque el HTML ya no las
  emita — son el par de la variable `banda` conservada (§1.3).
- `.cn-dot__foot` (L1953-1954): **se conserva y se sigue pintando** (A4).
- `.cn-rank*` (L1899-1910): las otras dos ramas de ranking (A6).
- `.cn-dot--single` (L1980-1983): la rama de un solo ítem. Sin dona.

---

## 3. Cache-busters — **LOS DOS** (A1)

`templates/main.html`:

| Línea | Recurso | De | A |
|---|---|---|---|
| 5 | `colapsable.css` | `20260812a1` | **`20260812b1`** |
| 82 | `multitab_shell.js` | `20260811s9` | **`20260812b1`** |

⚠️ Subir **ambos**. Con solo uno, el navegador mezcla JS viejo con CSS nuevo (o al revés) y
la tarjeta sale rota de un modo que parece un bug del código.

`panels.js` (L89) no se toca.

---

## 4. Validación

### V1 · Sintaxis (dev, obligatorio)
```
node --check static/js/multitab_shell.js
```
Sin salida = OK. (Baseline ya verificado limpio antes del cambio.)

### V2 · Aritmética de la dona (dev, obligatorio)
```
python -c "import math; c=2*math.pi*72; print(round(c,2)); print(sum([13.9,7.7,7.0,6.6,6.0,58.8]))"
```
Esperado: `452.39` y `100.0`.

### V3 · Grep de no-regresión (dev, obligatorio)
```
grep -n "banda" static/js/multitab_shell.js
grep -n "cn-dot__foot" static/js/multitab_shell.js
grep -n "max-content" static/css/colapsable.css
grep -n "?v=" templates/main.html
```
- `banda`: **construida** sí; **ausente** de la línea `return`.
- `cn-dot__foot`: **presente** en el return (si no, se implementó la variante A por error).
- `max-content`: debe aparecer como **`minmax(0, max-content)`**, nunca suelto (A2).
- `?v=`: las líneas 5 y 82 deben tener el **mismo valor nuevo** (A1).

### V4 · Harness efímero en scratchpad (dev, recomendado)
Convención del proyecto (no hay harness versionado, A6): crear en el scratchpad un
`test_rank_dot.js` que **extraiga del archivo REAL** `__cnRankDotHtml` y `__cnDonaHtml` y
asegure sobre el HTML devuelto, con un `d` de prueba calcado de la captura:

| # | Aserción |
|---|---|
| 1 | El HTML **no** contiene `cn-dot__bandwrap` |
| 2 | El HTML **sí** contiene `cn-dot__foot` y el texto del conteo |
| 3 | El `<svg>` trae `width="180"` y `viewBox="0 0 180 180"` |
| 4 | Hay 7 `<circle>` (fondo + 5 ítems + Otros) y el `%` central dice `41,2%` |
| 5 | Con `concentracion_pct: null` **no** se emite `cn-dona` (degrada a 1 columna) |
| 6 | Con `items.length === 1` sale la rama `cn-dot--single`, sin dona |

### V5 · Navegador (lo corre el usuario en el servidor de pruebas)

Pregunta de referencia: **«cuáles campos son los mayores productores de crudo?»**

| # | Qué mirar | Esperado |
|---|---|---|
| 1 | Dona | Notablemente más grande; «41,2% / TOP 5» centrado y legible |
| 2 | Leyenda | A la **derecha** del círculo, no debajo; nombre y % juntos |
| 3 | Arcos chicos | Caño Limón (6,0%) se distingue como segmento propio |
| 4 | Canal central | Las dos mitades se leen como bloques separados |
| 5 | Filas del dot plot | Más aireadas; «Frontera Energy · tercero» respira |
| 6 | Banda | **Ausente** |
| 7 | Pie | **Presente**: «128 campos con producción registrada · Motor V2 · Cuantificar» |
| 8 | Leyenda propia/tercero | Sigue al pie a la izquierda |

**No regresión (misma sesión):**

| # | Caso | Cómo | Esperado |
|---|---|---|---|
| 9 | Gas | «mayores productores de gas» | Igual formato; MSCF; color del producto |
| 10 | Ranking por `gap` | «qué campos tienen el mayor faltante» | **Sin dona**, formato `.cn-rank` intacto |
| 11 | `bottom` | «menores productores de crudo» | **Sin dona**; dot plot a ancho completo |
| 12 | Un solo ítem | «cuál es el mayor productor de crudo» | Cifra grande, sin dot plot ni dona |
| 13 | Ranking estructural | «cuántos pozos tiene cada campo» | `.cn-rank*` intacto (otra rama) |
| 14 | **Pila acumulativa** | Hacer 3 preguntas de ranking seguidas | Las 3 tarjetas apiladas, **ninguna** ensancha la columna |
| 15 | **🔑 Scroll horizontal** | Con la tarjeta visible, mirar el borde inferior de `.cn-col` | **NO** debe aparecer barra horizontal (A2/A7) |
| 16 | **🔑 Nombres largos** | Un ranking por **activo** (nombres más largos) | La leyenda recorta con «…» y el `%` sigue visible; sin desbordar |
| 17 | Panel angosto | Retraer/expandir el chat; ventana a ~1300px | Bajo 1440px la dona baja bajo el dot plot, sin recortarse |

---

## 5. Riesgos residuales

| Riesgo | Prob. | Mitigación |
|---|---|---|
| Se usa `max-content` suelto en vez de `minmax` | Media si se copia del v1 | V3 lo verifica con grep; A2 lo explica |
| Se sube un solo cache-buster | Media | V3 + §3 con tabla explícita |
| El encabezado se coloca al lado del círculo | Baja | `grid-template-areas` prescrito literal |
| Se retira el pie con la banda | Baja | V3 lo verifica; A4 lo prohíbe |
| A 1440px justos la leyenda recorta antes de lo ideal | Baja | Aceptado: recorta con `…` + `title`, nunca desborda |
| Se rompe una variante sin dona | Muy baja | Ramas distintas (A6); V5 #10/#11/#12/#13 |

---

## 6. Fuera de alcance

- Mover el conteo de campos a la cabecera (descartado: el pie se conserva).
- Borrar el CSS huérfano de la banda (limpieza aparte).
- Tocar backend, `ranking.py` o el contrato del panel.
- Rediseñar las variantes por `gap`, la estructural o la de un solo ítem.

---

## 7. Resumen de archivos

| Archivo | Ediciones |
|---|---|
| `static/js/multitab_shell.js` | 4: geometría (L2907), textos del centro (L2948-2951), comentario de `banda` (L2847), return sin `banda` (L2881) |
| `static/css/colapsable.css` | 4: `.cn-dot__cols` gap, `.cn-dot__row` padding, bloque `.cn-dona*` completo, media query 1280→1440 (+ su comentario) |
| `templates/main.html` | 2: cache-buster de CSS (L5) **y** de JS (L82) |

**Commit sugerido:**
```
style(chat): dona a tamano pleno con leyenda al costado en el ranking N5

La dona pasa de 130 a 180px (r 52->72, anillo 20->28) y su leyenda deja de
apilarse debajo para sentarse a la derecha. El espacio liberado se invierte en el
canal entre el dot plot y la dona (14->46px), que es lo que las hace leer como dos
bloques. Las filas del dot plot ganan aire (padding 5->10px).

Se retira la banda de concentracion: repetia el 41,2% que ya ocupa el centro de la
dona. El conteo del universo NO se pierde -- sigue declarado en el pie.

Dos decisiones que no son cosmeticas:

- El layout usa grid-template-areas porque __cnDonaHtml emite el encabezado, el svg
  y la leyenda como hermanos sin envoltorio: una rejilla de 2 columnas a secas
  pondria el encabezado al lado del circulo. Asi se resuelve sin tocar el DOM.
- La columna de la leyenda es minmax(0,max-content) y no max-content: max-content no
  cede, empuja. Medido, la mitad derecha pide ~380px (451 con el campo de nombre mas
  largo del catalogo) y entre 1280 y 1440px de viewport solo dispone de ~323-403.
  Como el panel es una pila acumulativa sin overflow propio, eso habria ensanchado la
  columna entera. Por lo mismo el umbral responsive sube de 1280 a 1440px.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
```
