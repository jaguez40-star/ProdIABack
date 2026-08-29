# Plan · Identidad de color por producto (Crudo / Gas / Blancos) en el panel de Consulta

**Fecha:** 2026-08-11 · **Estado:** **v2 auditado** (2ª ronda contra el código real; 5 hallazgos
nuevos, 3 de ellos invalidan pasos de la v1). Contraste WCAG **calculado**, no estimado.
Sin LLM, sin backend levantado, sin BD — solo lectura de archivos.
**Tipo:** frontend puro (`multitab_shell.js` + `colapsable.css` + bump). Sin backend, sin contrato.
**Cobertura: vistas con producto — entrada 6 → salida 6.** Curva diaria, gráfico de filiales,
tarjetas de foco, tarjetas KPI/Cuantificar, pestañas del ejecutivo, y brecha por campo (esta última
**se declara intacta a propósito**, §6). Ninguna se omite en silencio.

---

## 1. Contexto

Especificación aportada por el usuario:

| Producto | Color | Hex | Icono |
|---|---|---|---|
| Crudo | verde petróleo | `#004236` | gota |
| Gas | rojo llama | `#EF4444` | llama |
| Blancos | amarillo tubería | `#EAB308` (texto: ámbar oscurecido) | surtidor |

*"El color entra por 4 vías: filete superior de la tarjeta, badge con icono, barras/puntos del
gráfico y el énfasis del porcentaje de concentración."*

### El punto de partida real (auditado)

No hay identidad que "cambiar": hay **ausencia de identidad**, con contradicciones medibles.

| Producto | Colores distintos hoy |
|---|---|
| **CRUDO** | 4 — `#1f6b4a` (filiales) · `#E8912B` (icono focos) · `#1f4e79` (backend) · `#004236` (mapa) |
| **GAS** | 3 — `#e0902a` · `#C5311E` · `#ff5f00` |
| **BLANCOS** | 4 — `#0d6efd` · `#D9503B` · `#999999` · sin regla en backend |

Dos defectos de fondo que este plan corrige de paso:
- **La curva diaria de GAS y BLANCOS se pinta con el verde de CRUDO** (`:1688`, color fijo).
- **`__CP_PROD.color` nunca fue identidad**: `CRUDO`=`#E8912B` es el MISMO hex que
  `__CP_STATUS.ajustado`; `GAS`=`#C5311E`, el mismo que `actuar` (`:2289-2297`).

### Decisiones del usuario (cerradas)

| # | Decisión |
|---|---|
| D1 | **El color identifica al PRODUCTO.** El estado deja de codificarse por color de fondo y se lee en el chip textual + icono, que **ya existen**. |
| D2 | **Alcance: solo el panel de Consulta (Motor Q v2).** El backend de gráficos queda fuera. |

---

## 2. Auditoría — hallazgos

Los 🔴 **invalidan** pasos de la v1 de este plan.

| # | Hallazgo | Evidencia | Efecto |
|---|---|---|---|
| **H1** | `__CP_PROD` ya es "producto → {icon, color}", con 3 consumidores y fallback (`circle`/`#6E7C75`). | `:2295`, usado en `:2376`, `:2449`, `:3106` | **Punto natural de cambio.** El fallback se **conserva**. |
| **H2** | Objeto `COL` **duplicado y contradictorio** dentro de `__cnFilSeriePlot`. | `:1216` | Se elimina; pasa a leer `__CP_PROD`. |
| 🔴 **H3** | **`__cnDailyPlot` NO recibe `prod`** — recibe `esGas` (booleano), y ya tiene **7 parámetros posicionales**. La v1 afirmaba que recibía el producto. | `:1661` (firma), `:1640` (call site) | Añadir un 8º posicional es frágil. **Se pasa el color ya resuelto** (`esGas` sigue gobernando la conversión a MSCF, que es lógica aparte). |
| 🔴 **H4** | **`S.color` no solo pinta el borde: alimenta `__cnRing`**, el anillo de % de cumplimiento. | `:2470` (token) y `:2477` (anillo) | Cambiar `--cp-st` a color de producto **recolorearía el anillo de estado**. El anillo **conserva el color de estado**; el producto entra por filete + badge. La v1 no lo advirtió. |
| 🔴 **H5** | **El producto llega en DOS convenciones**: `"GAS"` en el análisis v1 (`:2046`, `:2371`) y `"gas"` en los paneles del Motor Q v2 (`:2509`, `:2638`, `:2661`, `:2682`). `__CP_PROD` tiene claves en MAYÚSCULAS. | grep de `.producto` | `__CP_PROD["gas"]` → `undefined` → **fallback gris silencioso**. Obliga a un accessor `__cnProdId(p)` que normalice. **Sin esto, las tarjetas de Cuantificar saldrían grises sin lanzar error.** |
| **H6** | `__cnCuantCardHtml` **no usa `__CP_STATUS`**: tiene paleta inline propia con un 4º tono (`#D64545` "Foco" ≠ `#C5311E` "actuar"). | `:2500-2501` | Otra fuente duplicada. Queda **fuera de alcance** (es color de estado, no de producto) pero se anota. |
| 🔴 **H7** | Las pestañas del ejecutivo usan `__cnSemColor` en **2 sitios** (pestaña `:3366` y sub-encabezado `.cn-ejec__prod-hd` `:3383`), y el CSS solo colorea **cuando está activa** (`.is-active.is-warn/.is-bad`); las inactivas son neutras. La activa usa **`--rb-green`** (verde de marca). | `:3363-3369`, `:3383`, `colapsable.css:1452-1455` | La v1 mencionaba solo un sitio y no vio la colisión con el verde de marca. |
| **H8** | **Contraste WCAG calculado** sobre blanco: Crudo `11.46` ✓ · **Gas `3.76`** ⚠ · Blancos `1.92` ✗ · ámbar de texto `5.32` ✓ | fórmula WCAG 2.x | La spec resolvió Blancos **pero no vio que Gas falla texto normal** (umbral 4.5). **Gas necesita su propia variante oscurecida.** |
| **H9** | Patrón «texto oscurecido + fondo suave» **ya es el estándar**. | `colapsable.css:1162-1164` | La variante de texto encaja; no se inventa nada. |
| **H10** | **El icono de Gas ya es `fire`** (coincide). Crudo `droplet-fill` (coincide). **Blancos usa `droplet`** — casi idéntico al de Crudo. | `:2295-2297` | Cambiar Blancos a `fuel-pump` **corrige un defecto preexistente**. |
| **H11** | Crudo (verde) vs Gas (rojo): confusión rojo-verde (~8% de hombres). | — | Mitigado: el verde es casi negro (luminancia muy distinta) **y** el icono siempre acompaña. Se documenta; no bloquea. |
| **H12** | El verde de marca `--rb-green` (`#0e5c3a`) es el de todo el chrome. | `colapsable.css:85` | El verde de Crudo (`#004236`) se usa **solo en contexto de dato**, nunca en navegación. |

---

## 3. Especificación

### 3.1 Token único — `__CP_PROD` + accessor normalizador (H5)

```js
var __CP_PROD = {
  CRUDO:   { icon: "droplet-fill", color: "#004236", texto: "#004236", soft: "#E6EFEC" },
  GAS:     { icon: "fire",         color: "#EF4444", texto: "#B91C1C", soft: "#FDECEC" },
  BLANCOS: { icon: "fuel-pump",    color: "#EAB308", texto: "#A65E08", soft: "#FBF3DC" }
};
// H5: el producto llega como "GAS" (análisis v1) o "gas" (Motor Q v2) → SIEMPRE por este accessor.
// Sin él, __CP_PROD["gas"] es undefined y la tarjeta cae al gris SIN lanzar error (fallo mudo).
function __cnProdId(p) { return __CP_PROD[String(p || "").toUpperCase()] || null; }
function __cnProdCol(p) { return (__cnProdId(p) || { color: "#6E7C75" }).color; }
```

- `color` → relleno (series, filete, punto del badge).
- `texto` → **solo texto sobre blanco** (H8). Crudo no necesita variante (11.46 ✓); **Gas sí**
  (`#B91C1C`, ≥4.5 — corrección al vacío de la spec); Blancos usa el ámbar de la spec
  (`#A65E08`; el `#A6508` del mockup tiene 5 dígitos, se asume dígito perdido).
- `soft` → fondo del badge (patrón H9).
- El fallback de H1 (`circle`/`#6E7C75`) se conserva dentro del accessor.

### 3.2 Las 4 vías de la spec

| Vía | Cómo | Nota |
|---|---|---|
| **Filete superior** | `border-top: 3px solid var(--cp-prod)` | vía nueva |
| **Badge con icono** | icono `color` + fondo `soft` | reemplaza el chip que hoy solo lleva icono |
| **Barras/puntos del gráfico** | `color` en línea/marcador/relleno | corrige H3 |
| **Énfasis del %** | `texto` | **nunca `color` puro** (H8) |

### 3.3 Cambios por vista

| # | Vista | Hoy | Después |
|---|---|---|---|
| 1 | **Curva diaria** (`__cnDailyPlot` :1688) | verde fijo para los 3 | **nuevo parámetro `col`** (color ya resuelto, no el producto — H3); `esGas` intacto |
| 2 | **Gráfico de filiales** (`__cnFilSeriePlot` :1216) | `COL` propio contradictorio | lee `__CP_PROD` vía accessor; `COL` se elimina (H2) |
| 3 | **Tarjetas de foco** (`:3106`) | icono con color de estado disfrazado | icono + filete con la identidad; chip de estado aparte |
| 4 | **Tarjetas KPI / Cuantificar** (`:2470`, `:2500`) | `--cp-st` gobierna borde **y anillo** | **el anillo conserva el color de ESTADO** (H4); el producto entra por **filete + badge**; el estado se sigue leyendo en el chip textual (D1) |
| 5 | **Pestañas del ejecutivo** (`:3366` y `:3383`) | color por `__cnSemColor`, solo si activa; activa = verde de marca | color de producto en **ambos** sitios (H7); la activa usa el color del producto, no `--rb-green` |
| 6 | **Brecha por campo** (`__cnGapCampoInto`) | verde/ámbar por banda de cumplimiento | **SIN CAMBIO** — su color codifica cumplimiento por campo (§6) |

### 3.4 CSS

Tokens `--cp-prod` / `--cp-prod-soft` / `--cp-prod-text` inyectados inline por el JS (mismo
mecanismo que `--cp-st` hoy, `:2470`). Clases nuevas `.cp-prod__filete`, `.cp-prod__badge`.
En las pestañas, añadir la variante activa por producto sin borrar `.is-active` genérica.
**Sin `overflow` propio.**

---

## 4. Orden de ejecución

1. `:2295` — ampliar `__CP_PROD` + añadir `__cnProdId` / `__cnProdCol` (**H5 primero**: todo lo
   demás depende del accessor).
2. `:1661`/`:1640` — `__cnDailyPlot` acepta `col` y colorea línea/marcador/relleno con él (H3).
3. `:1216` — eliminar `COL`; `__cnFilSeriePlot` usa el accessor (H2).
4. `:3106` — tarjetas de foco: filete + badge.
5. `:2470`, `:2449` — tarjeta P50/KPI: filete + badge de producto; **`__cnRing` conserva `S.color`** (H4).
6. `:2500` — tarjeta Cuantificar: ídem, con el accessor (aquí llega `"gas"` en minúsculas — H5).
7. `:3366`, `:3383` — pestañas y sub-encabezado del ejecutivo (H7).
8. `colapsable.css` — `.cp-prod__*` + variante activa de pestaña.
9. `templates/main.html` — bump `?v=` (2 líneas).
10. Validación estática (§7).

---

## 5. Reglas no negociables

- **Toda lectura de `__CP_PROD` pasa por `__cnProdId`/`__cnProdCol`** (H5). Prohibido
  `__CP_PROD[x]` directo: con `"gas"` da gris sin error.
- **Una sola fuente de color de producto.** Prohibido reintroducir un objeto paralelo (defecto H2).
- **`__cnRing` sigue recibiendo el color de ESTADO** (H4). El anillo mide cumplimiento.
- **`texto` para texto sobre blanco, `color` para relleno** (H8). Nunca `#EAB308`/`#EF4444` como
  texto pequeño sobre blanco.
- **El estado no se codifica por color de fondo** en las vistas tocadas (D1): chip textual + icono.
  **`__CP_STATUS` NO se borra** — lo usan el chip, el anillo y vistas no tocadas.
- **El verde de Crudo nunca se usa en chrome/navegación** — eso es `--rb-green` (H12).
- **`__cnGapCampoInto` no se toca** (§6).
- **El color nunca es la única señal**: siempre con icono o etiqueta (H11).
- No se toca: backend Python, contrato del panel, Test Clas, `.ct-*`, `.cn-jer*`, scroll único.

---

## 6. Fuera de alcance (declarado, no enterrado)

- **Backend de gráficos** (D2): `utils/colors.py` seguirá coloreando por substring y dejando
  BLANCOS sin regla. **Es un bug real; queda como deuda documentada.**
- **`__cnGapCampoInto`**: su verde/ámbar codifica **cumplimiento por campo**, no producto.
  Recolorearlo destruiría esa lectura. Intacto a propósito.
- **Paleta inline duplicada de `__cnCuantCardHtml`** (H6, con su 4º tono `#D64545`): es color de
  estado, no de producto. Unificarla con `__CP_STATUS` es deuda aparte.
- **`#004236` sobrecargado en el backend** (significa "crudo", "rentable" y "costos variables" en
  tres gráficos distintos): deuda documentada, fuera por D2.

---

## 7. Validaciones (100 % estáticas — sin LLM, sin backend, sin BD)

- `node --check static/js/multitab_shell.js`.
- Balance de llaves CSS + presencia de `.cp-prod*` + **ausencia de `overflow`** en ellas.
- **Contraste recalculado** con la fórmula WCAG para los 3 `texto` sobre blanco (umbral ≥ 4.5).
- grep de no-regresión:
  - `COL = {` ya **no existe** en `__cnFilSeriePlot`.
  - **Cero accesos directos** `__CP_PROD[` fuera del accessor (H5).
  - `__CP_STATUS` **sigue existiendo** y `__cnRing(` sigue recibiendo el color de estado (H4).
  - `__cnGapCampoInto` con **diff vacío**.
  - Los 4 tipos `cuant_*` y los 3 `jerarq_*` siguen en el dispatcher.

**Verificación en el servidor de pruebas (usuario):**

| # | Qué mirar | Esperado |
|---|---|---|
| 1 | Curva diaria de **GAS** | Roja — hoy sale verde como la de crudo |
| 2 | Curva diaria de **BLANCOS** | Amarilla — hoy sale verde |
| 3 | **Tarjeta de Cuantificar** (Motor v2) | Con color de producto — **no gris** (prueba de H5) |
| 4 | Las 3 tarjetas de foco juntas | Tres identidades distinguibles de un vistazo |
| 5 | Un producto **en alerta** | Color = producto; el **anillo** y el chip siguen marcando el estado |
| 6 | Gráfico de filiales (3 series) | Las 3 distinguibles entre sí |
| 7 | Texto de % sobre blanco | Legible en los 3 (sobre todo Blancos y Gas) |
| 8 | Brecha por campo | **Sin cambios** |
| 9 | Header/botones | Verde de marca, no confundible con «dato de Crudo» |
