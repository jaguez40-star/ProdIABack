# Plan · Pila histórica de resultados en el panel derecho de Consulta (Motor Q v2)

**Fecha:** 2026-08-11 · **Estado:** v2 auditado (2 rondas adversariales, 7 supuestos falsos corregidos)
**Tipo:** frontend puro. Sin backend, sin contrato, sin BD, sin migración.
**Cobertura: entregables de entrada 4 → salida 4** (los 4 tipos de `panel` del Motor v2 se apilan; ninguno se omite).

---

## 1. Contexto

El panel derecho de la pestaña **Consulta** es hoy un slot de una sola vista: cada pregunta
lo reemplaza. Verificado — **el 100% de los renders de la zona 3 usan `innerHTML =`; no hay
un solo `append`**. El único historial del sistema es el del chat (`__cnHistory` +
`__cnReplay()`, zona 2). El panel derecho no guarda nada: al cambiar de pestaña se
**re-ejecuta** la última vista desde `__cnLastIntent` + cachés.

Consecuencia: el entregable de cada pregunta (tarjeta KPI, serie, variación, ranking) se
pierde en cuanto se hace la siguiente. No se pueden comparar dos resultados.

**Objetivo:** que los resultados del Motor Q v2 se **acumulen** en el panel derecho, en
orden cronológico, sobreviviendo al cambio de pestaña.

### Decisiones del usuario (requisitos cerrados, no opciones)

| # | Decisión |
|---|---|
| D1 | **Alcance**: solo los `panel` del Motor v2 (`d.panel`). El análisis v1 (Desempeño/focos/Plotly) **no** se apila. |
| D2 | **Orden**: cronológico, el nuevo **abajo**, con autoscroll al bloque nuevo. |
| D3 | **Persistencia**: sobrevive al cambio de pestaña conservando **nodos DOM**. |
| D4 | **Convivencia**: al abrir Consulta se ve el Desempeño del mes como hoy; al llegar el primer panel v2 el visor pasa a modo pila. La vuelta al análisis es por la tarjeta **"Desempeño del mes" del riel**, ya existente — sin botones nuevos. |
| D5 | **Controles**: ninguno. Solo acumula. |
| D6 | **Motor v1**: una pregunta v1 **esconde** la pila (nunca la borra) para que ningún resultado quede invisible. |
| D7 | **Tope**: silencioso, 100 bloques; al superarlo se descarta el más antiguo, sin UI. |

---

## 2. Auditoría previa — hallazgos que definieron el diseño

Verificados contra el código real (no de memoria). Los 7 primeros **invalidaron** el
borrador inicial.

| # | Hallazgo | Evidencia | Efecto en el plan |
|---|---|---|---|
| **H1** | **No existe hoy ningún contenedor del panel derecho que sobreviva a los dos destructores.** Una pila en `#cn-canvas` la borra `renderViewer()`; una en `#cn-viewer-area` la borra `__cnPintarPanelCuant`. | `multitab_shell.js:383-390` y `:2486` | La persistencia por `DocumentFragment` es **obligatoria**, no un extra. |
| **H2** | **Re-abrir el panel colapsado destruye el visor.** `toggleCollapse` es inocuo, pero `setActiveTab` trata el reabrir como caso especial y **se salta el early-return**, re-renderizando la misma pestaña. | `:419-425` → `:446-447` | Hay que guardar la pila **también** en esa ruta. |
| **H3** | **`unmount()` ("Volver") pierde la pila y deja fragmentos zombies.** No llama a `saveIngestaDOM()`, no limpia cachés, y `state` es del módulo (sobrevive entre montajes). | `:560-594`, `:592-593`, `:19-26` | Guardar en `unmount()` y **limpiar la caché en `mount()`** (evita heredar el bug de Ingesta). |
| **H4** | **El arranque del usuario restringido renderiza dos veces.** `mount()` fija `activeTab="ingesta"`, renderiza Ingesta entera y **luego** llama `setActiveTab("consulta")`. Las 5 pestañas existen en el DOM; solo se ocultan por CSS, y `onRailKeydown` permite alcanzarlas por teclado. | `:535-546`, `:542-545`, `:450-463` | `setActiveTab` **sí** se ejecuta para todos → el hook de guardado es válido. Nada colgado de `mount()` puede asumir que `#cn-canvas` existe. |
| **H5** | **No hay ningún campo común a los 4 tipos.** El ranking **no usa `entidad_cualificada`**; `anio` solo existe en serie/variación; `periodo_label` en el KPI es condicional (solo N2). | `:2459`, `:2514-2515`, `:2533-2534`, `:2544/:2564` | Un título derivado dejaría el ranking sin título. **Se elimina la idea de título derivado.** |
| **H6** | **Los 4 constructores ya se auto-titulan**: `.cq-hd`, `.cn-rank__hd`, `.cp-mes__kpi-name`. | `:2514`, `:2533`, `:2563`, `:2459` | Un título por bloque **duplicaría texto** — mismo defecto AI1 corregido el 2026-07-30. La cabecera lleva **nº + hora + la PREGUNTA del usuario**, que es el dato que no está en el contenido. |
| **H7** | `.cn-p50-hd` / `.cn-p50-row` (clases) **no existen en el CSS** (el real es `.cn-p50hd__*`); además `cn-p50-row` es un **id** usado por el análisis v1. | `:2488-2490` vs `colapsable.css:1139-1144`, `multitab_shell.js:2571` | Clases muertas + colisión de nombre: se eliminan al reescribir. |
| H8 | `__cnRing` genera SVG **sin `<defs>` ni gradientes** (stroke con color literal). | `:2273-2294` | **Riesgo de colisión de ids SVG descartado.** |
| H9 | `.cq-*`, `.cn-rank*`, `.cp-p50__*` **no dependen de ancestro**. La única regla con ancestro sobre `.cp-mes__kpi` es `.cp-foco__kpicol .cp-mes__kpi{height:100%}` — precisamente la que **no** queremos en una pila. | `colapsable.css:1830-1856`, `:1529-1577`, `:1112` | Los 4 tipos se ven correctos dentro de la pila sin tocar su CSS. |
| H10 | Sin `nth-child`/`>`/`first-child` sobre `.cn-shell`; ninguna media query lo reorienta a `column`. | `colapsable.css:1356-1359`, `:1382-1385` | Añadir un tercer hijo es estructuralmente inocuo. |
| H11 | Namespace `cn-stack` / `cn-stk` **libre en todo el repo**. Vecino cercano: `.cn-desemp__stack` (`:1380`) — no colisiona con selectores de clase exactos. | grep repo completo | Nombres adoptados. |
| H12 | **6 puntos escriben en el lienzo**, no 3: `__cnDashHint` :994, `__cnDashboard` :1006, `__cnVerReporteDia` :1076, `__cnTendenciaFilial` :1195, `__cnAnalisisTab` :1430, `__cnAnalizar` :1453. | grep `__cnViewerArea()` | D6 exige cubrir **los 6**, no 3 (el borrador dejaba 3 huecos → resultado invisible). |
| H13 | `__cnCid` y `__cnHistory` **nunca se resetean** en todo el repo; no existe "nueva conversación" que toque el shell. | `:912`, `:913` | No hay dónde enganchar un reset de la pila. Coherente con D5 (sin controles). |

---

## 3. Decisión arquitectónica

La pila es un **tercer hijo hermano** de `.cn-canvas` dentro de `.cn-shell`, con la
visibilidad conmutada por la clase `is-stack` en el shell:

```
#cn-viewer-area                  (overflow:hidden inline, :386)
  └── .cn-shell                  ← clase de modo: .is-stack
        ├── .cn-rail#cn-rail     (siempre vivo y clicable = vía de retorno D4)
        ├── .cn-canvas#cn-canvas (análisis v1)
        └── .cn-stack#cn-stack   (pila v2 — NUEVO, display:none por defecto)
```

**Por qué hermano y no dentro.** El `__cnPintarPanelCuant` actual escribe en
`#cn-viewer-area` (`:2486`) **destruyendo `#cn-rail` y `#cn-canvas`** — con persistencia,
eso dejaría el riel muerto, y el riel es la vía de retorno de D4. Tampoco puede ser el
contenido de `#cn-canvas`: `__cnAnalizar` lo reescribe con `innerHTML =`.

**Por qué la persistencia es obligatoria (H1).** `renderViewer()` reconstruye
`#cn-viewer-area` entero, así que la pila **no puede sobrevivir en el DOM**. Sobrevive como
`DocumentFragment` en `state`, y se reinserta tras cada reconstrucción.

Beneficio colateral: **neutraliza el bug latente** de `__cnViewerArea()` (`:989`), que hoy
cambia de significado en cuanto un panel v2 destruye el canvas.

---

## 4. Especificación

### 4.1 Estado

En `state` (`multitab_shell.js:25`, junto a `ingestaViewerCache`):
```js
consultaStackCache: null,   // DocumentFragment con los hijos de #cn-stack fuera de pantalla
```

Junto al resto de `__cn*` (~`:989`):
```js
var __cnStackOn  = false;   // true = visor en modo pila
var __cnStackSeq = 0;       // nº incremental de bloque
var __CN_STACK_MAX = 100;   // tope silencioso (D7)
```

### 4.2 Guardado y restauración (D3 · H1 · H2 · H3)

**`saveConsultaStackDOM()`** — nueva, tras `saveIngestaDOM()` (`:283`). Calcada salvo un
detalle: **sin** la guarda `&& !state.consultaStackCache` (en Ingesta el cache se consume
una vez; aquí cada salida debe reflejar el estado más reciente). El `if (stack.firstChild)`
impide machacar un cache bueno con uno vacío.

**Tres puntos de invocación** — el borrador solo tenía el primero:

| Ruta | Dónde | Motivo |
|---|---|---|
| Cambio de pestaña | `setActiveTab` `:426`, junto a la línea de ingesta | D3 |
| **Re-abrir colapsado** | `setActiveTab`, en la rama `reopening` (antes de `:446`) | **H2** — se salta el early-return y destruye el visor |
| **Botón "Volver"** | `unmount()` `:562`, antes de `container.innerHTML = ""` | **H3** — hoy se perdería |

**Limpieza en `mount()`** (`:534`, antes del render inicial): `state.consultaStackCache = null`
y `__cnStackOn = false`, `__cnStackSeq = 0`. **No se hereda el bug de Ingesta** (H3): un
montaje nuevo arranca con la pila limpia, sin fragmentos zombies de la sesión anterior.

**Restauración** — en la rama consulta de `renderViewer()` (`:381-396`):
1. El HTML gana `<div class="cn-stack" id="cn-stack"></div>` y la clase condicional
   `is-stack`, aplicada solo si `__cnStackOn && state.consultaStackCache` (evita un panel
   en blanco si el flag quedara desincronizado).
2. Las tres llamadas de repintado del análisis (`__cnDashboard`/`__cnReanalizar`/
   `__cnAnalizar(null)`) se **conservan sin cambios**: con hermanos ya no pisan la pila.
3. **Después** de ellas, reinsertar el fragmento en `#cn-stack`, `scrollTop = scrollHeight`,
   y poner el cache a `null`.
   *El orden es obligatorio*: `__cnAnalizar` reescribe `#cn-rail` (`:1463-1464`) y borraría
   el paso siguiente.
4. Si `__cnStackOn`, **desmarcar** las `.cn-railcard` (`is-active`): se ve la pila, no el
   análisis, aunque `__cnAnalizar` marcara su tarjeta al repintar el canvas oculto.

### 4.3 `__cnPintarPanelCuant` — apilar en vez de reemplazar

Reescribir `:2475-2492` (incluido el comentario "HD5 / transitorio", que deja de aplicar).

- **`__cnStackEnsure()`** — localiza `#cn-viewer-area .cn-shell`, crea `#cn-stack` si falta,
  añade `is-stack`, marca `__cnStackOn = true`. Devuelve el nodo o `null`.
- **`__cnPintarPanelCuant(panel, pregunta)`** — **el guard `if (!panel || !panel.datos)
  return;` va PRIMERO**, antes de `__cnStackEnsure()`: si no, un panel vacío activaría el
  modo pila mostrando un contenedor en blanco.
  Cuerpo con los constructores puros ya existentes (`__cnCuantSerieHtml` / `__cnCuantVarHtml` /
  `__cnCuantRankHtml` / `__cnCuantCardHtml`), envuelto en
  `<section class="cn-stk" id="cn-stk-N">`, y **`stack.appendChild(blk)`** —
  `createElement`+`appendChild`, nunca `innerHTML +=` (destruiría y recrearía los bloques
  previos, perdiendo scroll y coste O(n)).
  Antes de appendear, aplicar D7:
  `while (stack.children.length >= __CN_STACK_MAX) stack.removeChild(stack.firstChild);`
- Se eliminan los wrappers `.cn-p50-hd` / `.cn-p50-row` (**H7**: clases muertas + colisión
  de nombre con un id real).

**Cabecera del bloque (H5 + H6).** No se deriva ningún título del contenido — los 4 tipos ya
se auto-titulan y no comparten campos. La cabecera lleva lo que **no** está en el contenido:

```
[ nº ]  «pregunta del usuario»                                    HH:MM
```

La pregunta se pasa desde `__cnPreguntar` (`:3576`), donde `texto` ya está en ámbito:
`if (d.panel) __cnPintarPanelCuant(d.panel, texto);`
Esto además **ancla cada resultado a su pregunta**, que es justo lo que da valor al
histórico. `esc()` obligatorio sobre `texto`.

### 4.4 Autoscroll (D2)

`__cnStackScroll(blk)` dentro de `requestAnimationFrame`:
`stack.scrollTop = blk.offsetTop - stack.offsetTop - 8`.
**No usar `scrollIntoView()`**: sube por la cadena de ancestros y puede desplazar el shell.

### 4.5 Salir del modo pila (D4 · D6 · H12)

`__cnStackHide()` — quita `is-stack` y pone `__cnStackOn = false`. **Nunca vacía
`#cn-stack`**: los bloques siguen vivos y reaparecen con el próximo panel v2, sumándose a
los anteriores (D5 "solo acumula").

Se invoca desde **los 6 escritores del lienzo** (H12) — el borrador cubría 3 y dejaba
huecos por los que un resultado quedaba invisible:

| Función | Línea |
|---|---|
| `__cnDashHint` | `:994` |
| `__cnDashboard` | `:1006` |
| `__cnVerReporteDia` | `:1076` |
| `__cnTendenciaFilial` | `:1195` |
| `__cnAnalisisTab` | `:1430` (tras el guard de `filiales`, para no reaccionar a un clic inerte) |
| `__cnAnalizar` | `:1453` |

Con esto, D6 queda cubierto por construcción: cualquier render v1 (pregunta en v1, clic en
el riel, huella, "Volver al panorama") descubre el lienzo automáticamente.

### 4.6 CSS

En `colapsable.css`, tras `.cn-shell/.cn-rail/.cn-canvas` (`:1356-1359`):

- `.cn-stack` — `display:none; flex:1 1 auto; min-width:0; min-height:0; position:relative;
  overflow:auto; padding:14px`. El `overflow:auto` propio es **obligatorio**: el padre
  `#cn-viewer-area` lleva `overflow:hidden` inline (`:386`).
- `.cn-shell.is-stack > .cn-canvas { display:none }` y
  `.cn-shell.is-stack > .cn-stack { display:block }` (especificidad 0,2,1 > 0,1,0).
- `.cn-stk` — tarjeta del bloque (borde, radio 10px, fondo blanco, `margin-bottom:14px`).
- `.cn-stk__hd` / `__n` / `__q` / `__ts` — cabecera flex: badge numérico, pregunta con
  elipsis, hora en `tabular-nums`. Tokens existentes (`--rb-border`, `--rb-chat-gold`).

Las clases del contenido se reusan **sin tocar** (H9).

### 4.7 Cache-buster

Bump del `?v=` en `templates/main.html:5` (CSS) **y** `:82` (JS) — hoy ambas
`20260804q1`. Bumpear solo una desincroniza CSS y JS en caché.

---

## 5. Orden de ejecución

1. `state` `:25` — `consultaStackCache: null`.
2. `~:989` — `__cnStackOn`, `__cnStackSeq`, `__CN_STACK_MAX` + comentario sobre `__cnViewerArea` (H1).
3. `~:283` — `saveConsultaStackDOM()`.
4. `setActiveTab` `:426` + rama `reopening` (H2) — invocaciones.
5. `unmount()` `:562` (H3) — invocación.
6. `mount()` `:534` (H3) — limpieza de caché y flags.
7. `renderViewer()` `:381-396` — `#cn-stack`, clase condicional, restauración **después** del repintado, desmarcado del riel.
8. `:2475-2492` — reescritura de `__cnPintarPanelCuant` + `__cnStackEnsure`/`__cnStackScroll`/`__cnStackHora`.
9. `:3576` — pasar `texto` como 2º argumento.
10. Los 6 puntos de `__cnStackHide()` (§4.5).
11. `colapsable.css ~:1359` — bloque CSS.
12. `templates/main.html:5` y `:82` — bump.
13. `node --check static/js/multitab_shell.js`.

---

## 6. Reglas no negociables

- **El guard `!panel.datos` va ANTES de `__cnStackEnsure()`** — o el modo pila se activa vacío.
- **`appendChild`, jamás `innerHTML +=`** al apilar.
- **La restauración va DESPUÉS del repintado del análisis** en `renderViewer` — `__cnAnalizar` reescribe el riel.
- **`__cnStackHide()` nunca vacía la pila** — esconder ≠ borrar (D5/D6).
- **No se deriva título del contenido** (H5/H6): la cabecera lleva la pregunta del usuario.
- **No se toca**: backend, contrato del `panel`, los 4 constructores, el CSS del contenido, la pestaña Test Clas.

---

## 7. Validaciones

**En dev (único posible — la app no se levanta con 8 GB, ver memoria del proyecto):**
- `node --check static/js/multitab_shell.js` → sin errores.
- grep de no-regresión: `__cnPintarPanelCuant` sigue con **1 sola** llamada (`:3576`).
- grep: `cn-stack|cn-stk` no colisiona (verificado hoy: 0 coincidencias).

**En el servidor de pruebas (usuario), tras commit+push:**

| # | Acción | Resultado esperado |
|---|---|---|
| 1 | Abrir Consulta | Desempeño del mes, **sin cambios** |
| 2 | Pregunta v2 #1 | Visor pasa a pila; bloque **1** con la pregunta y la hora |
| 3 | Preguntas #2, #3 | Se apilan **debajo**, autoscroll al nuevo, los anteriores accesibles subiendo |
| 4 | Ir a Ingesta → volver a Consulta | Los **3 bloques siguen ahí**, en orden, scroll al final |
| 5 | **Colapsar el panel y re-abrir** (H2) | Los 3 bloques siguen ahí |
| 6 | Clic en "Desempeño del mes" del riel | Vuelve el análisis; tarjeta marcada activa |
| 7 | Pregunta v2 #4 | La pila reaparece con **4** bloques (no 1) → esconder ≠ borrar |
| 8 | Motor **v1** + preguntar (solo Javier) | Se ve el análisis v1 — ningún resultado invisible (D6) |
| 9 | Botón "Volver" → reentrar al shell | Arranca **limpio**, sin bloques de la sesión anterior (H3) |
| 10 | Pestaña Test Clas | **Sin cambios** (ignora `d.panel`) |

---

## 8. Fuera de alcance (declarado, no enterrado)

- **Apilar el análisis v1** (Desempeño/focos/Plotly/diferidas/EBITDA) — decisión D1 del
  usuario. Exigiría namespacing de ids por turno, `Plotly.purge` y reescritura del CSS de
  alturas fijas.
- **Panel recibido con la pestaña ya cambiada**: si se pregunta y se salta a otra pestaña
  antes de que responda el fetch, `__cnStackEnsure` devuelve `null` y el panel se pierde
  (la burbuja sí queda en el chat). **Idéntico al comportamiento actual**, no es regresión.
  Resolverlo exigiría una cola de pendientes.
- **Reset de la pila por "nueva conversación"**: no existe tal hook (H13) — `__cnCid` y
  `__cnHistory` nunca se resetean. Coherente con D5.
- **Fuga de `ingestaViewerCache` en `unmount()`** (H3): bug preexistente de Ingesta. Se
  **evita heredarlo** limpiando la caché de Consulta en `mount()`, pero no se corrige el de
  Ingesta (fuera de alcance; anotado como deuda).
- **`onRailKeydown` alcanza pestañas ocultas** por teclado para usuarios restringidos (H4):
  bug preexistente del gate, ajeno a esta tarea. Anotado como deuda.
