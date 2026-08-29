# Plan · Tarjeta de ranking con dot plot (Cuantificar N5)

**Fecha:** 2026-08-11 · **Estado:** **v2 auditado** (2ª ronda contra el código real; 5 hallazgos
nuevos, 3 corrigen el diseño de la v1). Sin LLM, sin backend levantado, sin BD.
**Tipo:** **frontend puro** — `multitab_shell.js` + `colapsable.css` + bump. Sin Python, sin
contrato nuevo, sin migración.
**Cobertura: variantes de ranking — entrada 4 → salida 4.** `real·top` y `real·bottom` pasan al dot
plot; `gap·top` y `gap·bottom` **conservan la lista actual** (D1). Ninguna se omite en silencio.

---

## 1. Contexto

Hoy el ranking se pinta como lista numerada plana (`__cnCuantRankHtml`): posición, nombre, valor.
Sin comparación visual de magnitudes ni lectura de la concentración. El usuario aportó una
especificación completa (`cuant.md`) + mockup de las 3 variantes de producto.

### Decisiones del usuario (cerradas)

| # | Decisión |
|---|---|
| D1 | **Dot plot solo cuando `metrica === "real"`.** Las 2 variantes por `gap` (faltante/excedente) conservan la lista actual — la propia spec §6 prohíbe el dot plot con negativos. |
| D2 | **`es_ecp: null` → punto sólido + leyenda oculta.** Nunca se afirma "es de un tercero" sin saberlo. |

---

## 2. Auditoría — hallazgos

Los 🔴 **invalidan** decisiones de la v1 de este plan.

| # | Hallazgo | Evidencia | Efecto |
|---|---|---|---|
| **H1** | **El backend ya entrega los 11 campos** que la spec necesita; cada ítem trae `pos, entidad, valor, ppto, gap, operador, es_ecp`. | `respuesta_cuantificar.py:202-206`; `ranking.py:251-253` | **Cero cambios de backend.** |
| **H2** | **`es_ecp` tiene TRES estados**: `true`, `false` y **`null`** (operador desconocido). Sistemático: si `nivel_ranking == "activo"`, **todos** llegan `null` (`_op` solo se evalúa si `nivel == "campo"`). | `ranking.py:243-251` | Mapear `null`→hueco afirmaría "tercero" sin saberlo. Resuelto por D2. |
| **H3** | **`gap` produce negativos** y es 1 de las 4 variantes (`gap·bottom` es el DEFAULT del "mayor faltante"). | `ranking.py:13-17`, `:216` | Spec §6 lo prohíbe. Resuelto por D1. |
| **H4** | **`concentracion_pct` llega `null` si `direccion == "bottom"`** — deliberado: *"en bottom sería una cifra engañosa"*. | `ranking.py:234-239` | Banda + pie de banda **se ocultan**. La spec lo contempla; hay que implementarlo, no asumirlo. |
| **H5** | Existe `sin_registro`: entidades sin REAL este mes que el backend **excluye** y declara. | `ranking.py:296-298` | **Se conserva** o la tarjeta afirmaría un universo que no es. |
| **H6** | `__CP_PROD` ya es el sistema de color, con `color`/`texto`/`soft` = `--pc`/`--pct`/`--pcbg`, y accessor `__cnProdId()` que **normaliza el caso**. | `multitab_shell.js:2300-2316` | **No se crea un cuarto sistema.** |
| 🔴 **H7** | **El filete NO puede ir en el `body`.** `.cn-stk` tiene `padding:10px 12px 12px` y `border-radius:10px` propios → un filete dentro del cuerpo quedaría flotando con margen, no pegado al borde. Pero `blk.className` es fijo (`"cn-stk"`) y el dispatcher **no conoce el producto**. | `colapsable.css:1381-1382`; `__cnPintarPanelCuant` | La v1 decía "filete en el bloque" sin resolver **cómo** llega el color. **Solución: el constructor emite un `data-prod` en su raíz y el dispatcher lo lee para inyectar los tokens en `blk`** (§3.2). |
| 🔴 **H8** | **La v1 omitió un requisito de la spec §2**: `--pc` es también *"fondo del badge de nº de pregunta"*. Hoy `.cn-stk__n` tiene **verde fijo** (`--rb-green-soft`) en todas las tarjetas. | `colapsable.css:1386`; `cuant.md §2` | El badge del turno debe teñirse con el producto. Refuerza H7: el color debe llegar al **bloque**. |
| 🔴 **H9** | **`valor == 0` y `valor == null` son IMPOSIBLES** con `metrica == "real"`: el backend filtra `con_real = [d for d in datos if d[1] > 0]` (comentario literal: *"CERO TRAICIONERO: 0 no es poca producción"*) y si queda vacío devuelve `aplica:False` (no llega al panel). | `ranking.py:208-215` | La v1 especificaba 2 casos borde que **nunca ocurren**. Se retiran; en su lugar, un guard defensivo de `max<=0` para no dividir por cero. |
| **H10** | **`top_n` llega hasta 20**, no 15 (`max(1, min(20, ...))`), y puede ser **1** (pregunta en singular). | `ranking.py:123`, `:127` | La spec dice "hasta 15 sin cambios de layout". Hay que verificar que 20 filas no rompan, y `top_n==1` va a la rama de cifra grande (spec §6). |
| **H11** | La tarjeta vive en `.cn-stk`, que **ya aporta** cabecera con nº + pregunta + hora — justo lo que la spec §3.2 pide. | `__cnPintarPanelCuant` | **No se duplica la cabecera.** |
| **H12** | Namespace `.cn-dot*` **libre** en todo el repo. Formateadores `__cnGasM` / `__cnMilesEC` disponibles. | grep repo; `:1701`, `:2286` | Sin colisiones. |
| **H13** | Desajuste menor de hex en `--pct`: spec Gas `#C22B2B` / Blancos `#8A6508`; código `#B91C1C` / `#A65E08`. **Los 4 pasan AA.** | `cuant.md §2` vs `:2300-2302` | **Se conserva el del código** (desplegado y verificado). Anotado. |
| **H14** | El icono de Blancos de la spec (`bi-fuel-pump-fill`) es la variante rellena del actual. BI 1.11.3 tiene ambas. | `templates/base.html:18` | Se adopta el `-fill`: coherente con `droplet-fill` de Crudo. |

---

## 3. Especificación

### 3.1 Bifurcación (D1/H3)

```
metrica === "real"  →  __cnRankDotHtml(d)    (tarjeta nueva)
metrica === "gap"   →  __cnCuantRankHtml(d)  (lista actual, INTACTA)
```
`__cnCuantRankHtml` **no se borra ni se modifica**: sigue sirviendo a las 2 variantes de gap.

### 3.2 Cómo llega el color al bloque (H7/H8) — la pieza que faltaba

El constructor devuelve su raíz con un atributo de producto:
```html
<div class="cn-dot" data-prod="gas"> … </div>
```
Y el dispatcher, **después** de asignar `blk.innerHTML`, lee ese atributo y tiñe el bloque:
```js
var pr = blk.querySelector("[data-prod]");
if (pr) {
  var pid = __cnProdId(pr.getAttribute("data-prod"));
  if (pid) { blk.style.setProperty("--cp-prod", pid.color);
             blk.style.setProperty("--cp-prod-soft", pid.soft);
             blk.style.setProperty("--cp-prod-text", pid.texto);
             blk.classList.add("cn-stk--prod"); }
}
```
Es **aditivo y genérico**: cualquier panel futuro que emita `data-prod` hereda filete + badge sin
tocar el dispatcher otra vez. Los constructores siguen siendo **funciones puras** (devuelven string).

CSS asociado:
```css
.cn-stk--prod { border-top: 3px solid var(--cp-prod); }
.cn-stk--prod .cn-stk__n { background: var(--cp-prod-soft); color: var(--cp-prod-text); }
```

### 3.3 Anatomía (spec §3)

| # | Elemento | Fuente | Nota |
|---|---|---|---|
| 1 | Filete 3px | `data-prod` → `__CP_PROD` | §3.2 |
| 2 | Cabecera nº · pregunta · hora | **ya existe** (H11) | no se duplica; el nº se tiñe (H8) |
| 3 | Contexto: badge producto + `Campos · mayo 2026` + chip `cierre proyectado` + **unidad** a la derecha | `producto`, `nivel_ranking`, `periodo_label`, `es_proyeccion`, `unidad` | unidad en grande: evita leer MSCF como bbl |
| 4 | Dot plot | `items` | §3.4 |
| 5 | Banda de concentración 9px | `concentracion_pct` | **oculta si `null`** (H4) |
| 6 | Pie de banda: `Top N concentra <b>X%</b>` · `M campos restantes` | `concentracion_pct`, `total_universo` | idem |
| 7 | Leyenda propio/tercero | `es_ecp` | **oculta si ningún ítem es booleano** (D2/H2) |
| 8 | Pie: `N campos con producción registrada` · `Motor V2 · Cuantificar` + aviso `sin_registro` | `total_universo`, `sin_registro` | H5 |

### 3.4 Fila del dot plot

Grid `150px 1fr 78px`:
- **Nombre** a la derecha, 11.5px/600. Si `es_ecp === false` → subtítulo `<em>` 9px `{operador} · tercero`. Truncado con elipsis + `title` si >18 chars.
- **Track**: guía 1px `#efefe6`; tallo 2px `--pc`; punto 11px al extremo.
- **Valor** a la derecha, `tabular-nums`, con `__cnGasM` (gas) o `__cnMilesEC`.

**Escala (spec §4):** `ancho% = valor / max(valores de ESTA tarjeta) * 100`. Normalizada por tarjeta,
nunca compartida (bbl y MSCF no son comparables). **Guard `max<=0` → sin tallos** (H9: defensivo,
no debería ocurrir).

**Punto según `es_ecp`:** `true`→sólido · `false`→hueco · **`null`→sólido** (D2).

### 3.5 Casos borde (revisados con H9/H10)

| Caso | Comportamiento |
|---|---|
| `top_n == 1` | **Cifra grande con badge de producto, sin dot plot** (spec §6, H10) |
| 2-4 resultados | Renderiza los que haya, sin rellenar |
| `top_n` hasta **20** (H10) | Debe caber sin romper: filas de alto fijo, sin `overflow` propio |
| **`concentracion_pct == null`** (H4) | Oculta banda + pie de banda; conserva el resto |
| **Todos `es_ecp: null`** (H2) | Puntos sólidos, **sin leyenda** |
| Empate en el máximo | Ambos al 100% |
| `sin_registro` presente (H5) | Aviso conservado bajo el pie |
| **`metrica == "gap"`** (H3) | **No entra aquí** — lista actual |
| ~~`valor == 0` / `null`~~ (H9) | **Imposible**: el backend los filtra. Solo queda el guard `max<=0`. |

### 3.6 CSS

Prefijo `.cn-dot*` (H12: libre). Tokens inyectados vía §3.2. **Sin `overflow` propio** (scroll único).
Accesibilidad (spec §8): `role="img"` + `aria-label` resumen en el dot plot; `aria-label` por punto
(`"CUPIAGUA: 211.345 bbl"`).

---

## 4. Orden de ejecución

1. `multitab_shell.js` — `__cnRankDotHtml(d)` (función **pura**, emite `data-prod` en su raíz).
2. `multitab_shell.js` — bifurcación por `metrica` en el dispatcher (§3.1).
3. `multitab_shell.js` — en el dispatcher, tras `blk.innerHTML`: leer `data-prod` e inyectar
   tokens + `cn-stk--prod` (§3.2 — **el paso que la v1 no resolvía**).
4. `multitab_shell.js:2302` — icono Blancos `fuel-pump` → `fuel-pump-fill` (H14).
5. `colapsable.css` — `.cn-dot*` + `.cn-stk--prod` (filete + badge del turno, H8).
6. `templates/main.html` — bump `?v=` (2 líneas).
7. Validación estática (§6).

---

## 5. Reglas no negociables

- **`__cnCuantRankHtml` NO se toca**: sirve a las 2 variantes de `gap` (D1/H3).
- **Los constructores siguen siendo funciones PURAS** (devuelven string). El teñido del bloque lo
  hace el dispatcher leyendo `data-prod` (§3.2) — nunca el constructor tocando el DOM.
- **Toda lectura de color por `__cnProdId`/`__cnProdCol`**; nunca `__CP_PROD[x]` directo (aquí el
  producto llega en minúsculas).
- **`concentracion_pct == null` → sin banda ni pie de banda.** Prohibido calcular un denominador
  propio (H4).
- **`es_ecp: null` → sólido + leyenda oculta.** Prohibido pintarlo como tercero (H2).
- **`sin_registro` se conserva** (H5).
- **Escala normalizada por tarjeta**, nunca eje compartido (spec §4).
- **`--pc` nunca como texto pequeño**; para texto, `--pct` (spec §2).
- **No se duplica la cabecera** del bloque (H11).
- **`.cn-dot*` sin `overflow`** — único scroller: `.cn-col`.
- No se toca: backend Python, contrato, los otros 3 tipos `cuant_*`, los 3 `jerarq_*`, Test Clas,
  `__cnGapCampoInto`, `__cnGasM`/`__cnMilesEC`.

---

## 6. Validaciones (100 % estáticas — sin LLM, sin backend, sin BD)

- `node --check static/js/multitab_shell.js`.
- Balance de llaves CSS + presencia de `.cn-dot*`/`.cn-stk--prod` + **ausencia de `overflow`**.
- **Prueba de la función pura en Node** con payloads sintéticos que cubran los casos de §3.5:
  `top_n=1`, 3 ítems, **20 ítems** (H10), `concentracion_pct:null`, todos `es_ecp:null`, mezcla
  true/false/null, empate en el máximo, `sin_registro>0`. Verificar que **ninguno** produce `NaN`,
  `undefined` ni `%` fuera de `[0,100]`.
- grep de no-regresión:
  - `__cnCuantRankHtml` **existe y sin diff**.
  - Cero accesos directos `__CP_PROD[` fuera del accessor.
  - Los 4 tipos `cuant_*` y los 3 `jerarq_*` siguen en el dispatcher.
  - `.cn-stk__n` conserva su regla base (el teñido es aditivo, no la reemplaza).

**Verificación en el servidor de pruebas (usuario):**

| # | Pregunta | Esperado |
|---|---|---|
| 1 | `¿cuáles campos son los mayores productores de gas?` | Dot plot rojo; Chuchupa hueco (`Hocol · tercero`); filete y **nº de turno rojos** |
| 2 | `…de blancos?` | Dot plot amarillo, valores en bbl |
| 3 | `…de crudo?` | Dot plot verde |
| 4 | `¿qué campos tienen la más baja producción de crudo?` | **Sin banda de concentración** (H4) + aviso de sin-registro si aplica |
| 5 | `¿qué campos quedaron más cortos frente al presupuesto?` | **Lista actual** con signo negativo (D1) |
| 6 | Ranking por **activo** | Puntos sólidos, **sin leyenda** (D2) |
| 7 | `dame el top 20 de campos por crudo` | 20 filas sin romper el layout (H10) |
| 8 | Las 3 tarjetas apiladas | Cada una con su color; escalas independientes |

---

## 7. Fuera de alcance (declarado)

- **Ranking por `gap`**: conserva la lista (D1). Un eje bidireccional es otro componente.
- **Backend**: no se toca (H1).
- **Hex de la spec para `--pct`** (H13): se conserva el del código; ambos pasan AA.
- **Los otros paneles** (KPI, serie, variación) y los de Jerarquizar: sin cambios. Nótese que
  §3.2 los deja preparados para heredar el filete el día que emitan `data-prod`.
