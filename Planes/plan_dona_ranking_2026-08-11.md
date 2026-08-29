# Plan · Dona de participación en la tarjeta de ranking (Cuantificar N5)

**Fecha:** 2026-08-11 · **Estado:** **v2 auditado** (2ª ronda contra el código real + aritmética
verificada; 4 hallazgos nuevos, 2 corrigen el diseño de la v1). Sin LLM, sin backend, sin BD.
**Tipo:** **frontend puro** — `multitab_shell.js` + `colapsable.css` + bump.
**Cobertura: variantes afectadas — entrada 4 → salida 4.** La dona se añade SOLO a `real·top`;
`real·bottom` conserva el dot plot sin dona; `gap·top`/`gap·bottom` siguen en la lista. Ninguna se
omite en silencio.

---

## 1. Contexto y decisiones

El usuario pide partir la tarjeta: **izquierda** el dot plot con valores en bbl (lo que ya existe),
**derecha** una gráfica de pastel con la misma información en %.

| # | Decisión del usuario |
|---|---|
| D1 | **Dona con top 5 + "Otros"** (no solo el top 5), conociendo la advertencia de §9 de su propia spec. |
| D2 | **El % vive SOLO en la dona.** El dot plot conserva únicamente los bbl — no se duplican cifras. |

**Sobre D1:** se advirtió que su spec §9 dice *"nada de dona ni pie chart — 5 categorías más otros
comparan mal"*, y se mostró el cálculo con sus datos reales: "Otros" ocupa el **58,8%** y las 5
porciones reales quedan entre 6,0% y 13,9%. **El usuario decidió proceder.** Queda registrado como
decisión informada, no como objeción pendiente.

**D2 resuelve la ambigüedad de denominador**: al no repetir porcentajes junto a los bbl, no hay dos
cifras compitiendo. La izquierda es magnitud; la derecha, participación.

---

## 2. Auditoría — hallazgos

Los 🔴 **invalidan** decisiones de la v1.

| # | Hallazgo | Evidencia | Efecto |
|---|---|---|---|
| **H1** | El total de producción es **derivable**: `Σtop / (concentracion_pct/100)`. Con los datos de la captura: top5 = 36.607.095 bbl y 41,2% → ≈ 88.852.172 bbl; "Otros" ≈ 52.245.077 (58,8%). | `ranking.py:236-239` + cálculo | **Cero backend.** |
| 🔴 **H2** | **Ese total es una ESTIMACIÓN, no un dato exacto.** `concentracion_pct` viene redondeado a 1 decimal → el total real está entre 88.765.992 y 88.960.134 (**±0,22%, ≈194.000 bbl**). | `round(..., 1)` en `ranking.py:239`; banda calculada | Los **porcentajes** se desvían ~0,03 pp (imperceptible, se pueden mostrar). **Prohibido mostrar el total o el volumen de "Otros" en bbl**: sería una cifra inventada con 6 dígitos de falsa precisión. |
| 🔴 **H3** | **`.cn-dot` ya tiene `role="img"` en su raíz** (`:2857`). Ese rol **oculta todo el contenido interno** a lectores de pantalla — de hecho ya está sepultando los `aria-label` por fila (`:2820`), defecto preexistente. | `multitab_shell.js:2857`, `:2820` | Envolver la dona ahí dentro la haría **invisible** para accesibilidad y su `aria-label` nunca se leería. **Hay que retirar el `role="img"` de la raíz** y dejar que cada pieza (filas, dona) exponga el suyo. Corrige de paso el defecto previo. |
| 🔴 **H4** | El plan v1 decía *"por debajo de ~620px de contenedor"*, pero **`@media` mide el VIEWPORT, no el contenedor**. Ancho real calculado del track: 496px hoy → **332px con la dona** en un portátil de 1366px. | cadena `.cn-rail 158px` + `.cn-stack/.cn-stk` paddings; cálculo | Sigue siendo legible (el riesgo era menor del temido), pero el umbral debe ser de **viewport** y realista: **`@media (max-width: 1280px)` → 1 columna**, alineado con los breakpoints ya existentes (720/900/980). |
| **H5** | **`concentracion_pct` es `null` salvo en `real·top`** — deliberado (*"en bottom sería una cifra engañosa"*). Sin él **no existe denominador**. | `ranking.py:234-236` | **La dona SOLO en `real·top`.** En el resto, dot plot a ancho completo. |
| **H6** | `total_universo` es un **CONTEO de campos** (`len(pool)` = 128), **no un volumen**. | `ranking.py:260` | El naming de la v1 era ambiguo. La leyenda dirá `Otros (123 campos)`, nunca un volumen. |
| **H7** | Precedente exacto de la técnica: `__cnRing` dibuja arco SVG con `stroke-dasharray` + `rotate(-90)`. | `multitab_shell.js:2371-2390` | **SVG nativo, sin librerías.** La dona = N arcos con offset acumulado. |
| **H8** | La spec §9 exige que los tonos sean **opacidades del mismo `--pc`**, no colores nuevos. Sin precedente aún en el CSS. | `cuant.md §9`; grep vacío | 5 porciones = color del producto a opacidad decreciente; "Otros" = gris neutro. Funciona en escala de grises. |
| **H9** | La banda inferior ya comunica el agregado (`Top 5 concentra 41,2%` · `123 campos restantes`). | `__cnRankDotHtml` | **Redundancia intencional aceptada**: la banda da el agregado, la dona lo desglosa. La banda **se conserva**. |
| **H10** | `items.length === 1` ya tiene rama propia (cifra grande, sin dot plot). | `__cnRankDotHtml` | **Sin dona ahí**: un pastel de una porción al 100% no informa. |

---

## 3. Especificación

### 3.1 Cuándo se pinta la dona

```
metrica === "real" && direccion === "top"
  && concentracion_pct != null && concentracion_pct > 0    (H5 — sin esto no hay denominador)
  && items.length >= 2                                     (H10)
```
En cualquier otro caso la tarjeta queda **exactamente como hoy** (dot plot a ancho completo).

### 3.2 Layout

`.cn-dot__cols` — grid `1fr 150px`, `gap: 14px`, `align-items: start`.
- **Izquierda:** el dot plot actual, **sin tocar** (D2: solo bbl).
- **Derecha:** dona + leyenda vertical con los %.

**Responsive (H4):** `@media (max-width: 1280px) { .cn-dot__cols { grid-template-columns: 1fr; } }`
— umbral de **viewport**, coherente con los breakpoints existentes. La dona pasa debajo.

### 3.3 Accesibilidad — corrección previa obligatoria (H3)

**Antes de envolver nada**, retirar `role="img"` + su `aria-label` del contenedor raíz `.cn-dot`
(`:2857`). Ese rol sepulta el contenido interno. Cada pieza expone el suyo:
- filas del dot plot → su `aria-label` ya existente (hoy inaccesible; queda arreglado);
- dona → `role="img"` + `aria-label` propio con las participaciones.

Es un cambio **aditivo en accesibilidad**: hoy el lector solo oye el resumen; después oirá el
resumen del contexto, cada fila y la dona.

### 3.4 La dona

SVG nativo (H7), ~130×130, agujero central ~58% del radio.

**Datos:** `total_est = Σtop / (concentracion_pct/100)`; `otros_pct = 100 − concentracion_pct`
(⚠️ **directo, no derivado del volumen** — evita arrastrar el error de H2).
Cada porción: `pct_i = valor_i / total_est * 100`.
**Guard:** si `concentracion_pct <= 0` o `total_est <= 0` → no se pinta la dona.

**Colores (H8, spec §9):** las 5 porciones usan `--cp-prod` con opacidad decreciente
(`1, 0.85, 0.70, 0.57, 0.45`); **"Otros" en gris neutro** (`#D8DCD9`).

**Centro:** `concentracion_pct` en grande (`41,2%`) + rótulo `TOP 5`. Reusa el patrón de `__cnRing`.
Es el ancla que fija el denominador.

**Leyenda vertical:** cuadrito + nombre truncado + `%` en `tabular-nums`. La fila final dice
**`Otros (123 campos)`** — conteo, nunca volumen (H6/H2).

**Prohibido (H2):** mostrar el total estimado o el volumen de "Otros" en bbl.

### 3.5 Rótulo del denominador (crítico)

Encabezado de la columna derecha: **`Participación · % de la producción total`**.
Sin él, un 13,9% junto al 41,2% del centro es ambiguo.

---

## 4. Orden de ejecución

1. `multitab_shell.js:2857` — **retirar `role="img"` + `aria-label` de la raíz `.cn-dot`** (H3).
   El texto del resumen pasa a la fila de contexto (`.cn-dot__ctx`) como `aria-label` de esa fila,
   para no perder información.
2. `multitab_shell.js` — helper `__cnDonaHtml(items, concPct, totalCampos, prodColor)`: **función
   pura**, devuelve SVG + leyenda. Guards de §3.4.
3. `multitab_shell.js` — en `__cnRankDotHtml`, envolver dot plot + dona en `.cn-dot__cols` **solo**
   si se cumple §3.1; si no, estructura actual sin cambios.
4. `colapsable.css` — `.cn-dot__cols`, `.cn-dona*` + media query de 1280px (H4).
5. `templates/main.html` — bump `?v=` (2 líneas).
6. Validación estática (§6).

---

## 5. Reglas no negociables

- **La dona SOLO en `real·top` con `concentracion_pct` válido** (H5). Prohibido derivar el
  denominador por otra vía.
- **Prohibido mostrar el total o el volumen de "Otros" en bbl** (H2): es una estimación con ±0,22%
  de banda. Solo porcentajes y **conteo** de campos.
- **`otros_pct = 100 − concentracion_pct`**, no calculado desde el volumen estimado (H2).
- **El dot plot NO cambia** (D2): solo bbl. Prohibido añadir % a sus filas.
- **"Otros" SIEMPRE presente** si hay más campos que ítems. Una dona solo del top 5 diría
  "Rubiales 33,8%" cuando es 13,9%.
- **Retirar el `role="img"` de la raíz ANTES de envolver** (H3), o la dona nace inaccesible.
- **Colores = opacidades de `--cp-prod`** (H8, spec §9). "Otros" en gris neutro.
- **Rótulo del denominador obligatorio** (§3.5).
- **`items.length === 1` → sin dona** (H10).
- **`.cn-dona*` sin `overflow: auto|scroll`** — el único scroller es `.cn-col`.
- No se toca: backend, contrato, `__cnCuantRankHtml` (variantes de `gap`), los otros paneles
  `cuant_*`/`jerarq_*`, Test Clas, `__cnRing`, la banda de concentración (H9).

---

## 6. Validaciones (100 % estáticas — sin LLM, sin backend, sin BD)

- `node --check static/js/multitab_shell.js`.
- Balance de llaves CSS + presencia de `.cn-dona*`/`.cn-dot__cols` + ausencia de `overflow:auto|scroll`.
- **Prueba de la función pura en Node**, con el código **extraído del archivo real** (patrón ya
  usado en el commit anterior), sobre:
  - datos reales de la captura (top 5 crudo, 41,2%) → los 6 porcentajes **suman 100 ± 0,3**;
    "Otros" = **58,8%** exacto (`100 − 41,2`, H2);
  - `concentracion_pct: null` → **sin dona**, HTML idéntico al de hoy;
  - `direccion: "bottom"` → **sin dona**;
  - `items.length === 1` → **sin dona**;
  - `concentracion_pct: 100` → "Otros" = 0 → **sin porción fantasma**;
  - 20 ítems → la leyenda no desborda;
  - **ningún `stroke-dasharray` con `NaN`**; offsets acumulados ≤ circunferencia.
- grep de no-regresión: `__cnCuantRankHtml` sin diff; cero accesos directos a `__CP_PROD`;
  el dot plot **sin `%`** en sus filas (D2); **cero `bbl` dentro del bloque de la dona** (H2).

**Verificación en el servidor de pruebas (usuario):**

| # | Acción | Esperado |
|---|---|---|
| 1 | `¿cuáles campos son los mayores productores de crudo?` | Dot plot a la izquierda (solo bbl) + dona a la derecha, `41,2%` al centro, 6 porciones |
| 2 | Ídem en gas y blancos | Dona en rojo / amarillo, opacidades del mismo tono |
| 3 | `¿qué campos tienen la más baja producción de crudo?` | **Sin dona** — dot plot a ancho completo (H5) |
| 4 | `¿qué campos quedaron más cortos frente al presupuesto?` | **Lista actual**, sin dot plot ni dona |
| 5 | Ventana < 1280px | La dona baja debajo del dot plot (H4) |
| 6 | Leer la leyenda de la dona | Dice `Otros (123 campos)` — **ningún bbl** (H2/H6) |
| 7 | Comparar Quifa (7,0%) y Caño Sur Este (6,6%) | Difíciles de distinguir — limitación aceptada en D1; los bbl exactos siguen a la izquierda |

---

## 7. Fuera de alcance (declarado)

- **Añadir % a las filas del dot plot**: excluido por D2.
- **Dona en `real·bottom` o en `gap`**: imposible sin denominador (H5) / sin sentido con negativos.
- **Mostrar el total de producción del universo**: el backend no lo expone y derivarlo tiene ±0,22%
  (H2). Si se quisiera exacto, habría que añadirlo a `_panel_rank` — **otro plan, toca backend**.
- **Interactividad** (hover/clic en las porciones): el panel es de lectura.
- **Reconsiderar el pastel**: decisión informada del usuario (D1), no deuda pendiente.
