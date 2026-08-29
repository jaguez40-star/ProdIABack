# Plan · WAFFLE-NAV — Módulos en el waffle + navegación entre vistas

> **Versión:** v2 auditada (§0.2: el plan entregado ya debe ser equivalente a un v2).
> **Auditoría previa ejecutada:** §15 pasos 1-3 (Mapeo · Auditoría · Diagnóstico) ANTES de escribir.
> **Fecha:** 2026-08-25 · **ID:** WAFFLE-NAV
> **Nota de aplicabilidad:** `CLAUDE_muestra.md` describe *Robustez V2.0* (FastAPI + React 19 + pnpm).
> ProdIA 2.0 es **Flask + JS vanilla sin build step**: DT-9/DT-13/DT-17 y R1/R2 no aplican.
> Sí aplican, y se han aplicado: §15, §0.2, §0.3, **DT-15** (build verde ≠ feature verificada) y
> **DT-16** (grep exhaustivo antes de tocar algo compartido).

---

## 1. CONTEXTO

**Proyecto:** ProdIA 2.0 — chat de analítica de producción de Ecopetrol.
**Raíz absoluta:** `c:\APLICACIONES\ProdIA\12112025_prodIA\ProdIA-2.0\ProdIA-2.0`
**Stack:** Flask 8020 (`app.py`, `async_mode="threading"`) + FastAPI INGESTA 8088. Frontend en JS
vanilla servido por Flask; **no hay bundler, ni tests de frontend, ni `package.json`**. El versionado
de assets es manual vía `?v=` en las plantillas.

**El waffle ES el menú de usuario.** Un único popover `#mc-menu`
(`MainChat/templates/mainchat_layout.html:47-88`) contiene cabecera + rejilla de accesos +
"Cerrar sesión". No hay dos menús que unificar.

**Estado actual del waffle** (4 tarjetas, `mainchat_layout.html:61-80`):

| Tarjeta | Atributo | Comportamiento real hoy |
|---|---|---|
| Test Clas | `data-tab="testclas"` | ✅ Funciona: abre la pestaña in-situ |
| Admin | `data-ruta="/admin"` | ❌ Ruta **inexistente** → `console.info`, no navega |
| Configuración | `data-ruta="/settings"` | ❌ Ídem |
| Ayuda | `data-ruta="/help"` | ❌ Ídem |

**Módulos reales inalcanzables desde cualquier UI:**
- 4 de las 5 pestañas del shell (`ingesta`, `control`, `analisis`, `consulta`).
- `/layout/colapsable` — vista completa y funcional, **sin un solo enlace en toda la app**.
- `/` ↔ `/mainchat` — las dos interfaces no se enlazan entre sí.

---

## 2. OBJETIVO

1. **Fase 1:** exponer en el waffle las pestañas que hoy no son alcanzables, sin navegar (sin
   destruir estado del shell).
2. **Fase 2:** dar navegación entre las 3 vistas HTML, resolviendo primero el callejón sin salida.

---

## 3. HALLAZGOS DE LA AUDITORÍA (§15 pasos 1-3)

Cinco hallazgos. **H-01 invalida un paso del plan previo** y H-03 lo mejora.

### 🔴 H-01 — CRÍTICO · `tabDef` NO puede devolver `null`

El plan previo proponía cambiar `tabDef` (`static/js/multitab_shell.js:44-47`) para que devolviera
`null` en vez de `TABS[0]`, y así activar la guarda de `__rbAbrirTab:518`.

**Grep exhaustivo (DT-16) — 4 llamadores, 3 desreferencian sin guarda:**

| Línea | Uso | Rompe con `null` |
|---|---|---|
| `:342` | `renderEmptyBody(tabDef(state.activeTab))` → dentro hace `esc(tab.label)`, `tab.icon` | 🔴 Sí |
| `:493` | `var def = tabDef(tabId)` → `def.icon`, `def.label.toUpperCase()`, `def.label` (:506-508) | 🔴 Sí |
| `:518` | `if (!tabDef(tabId)) return false` — la guarda inalcanzable | — |
| `:624` | `var initialDef = tabDef(...)` → `initialDef.icon`, `.label.toUpperCase()` (:637-639) | 🔴 Sí |

**Consecuencia:** el cambio propuesto habría provocado `TypeError: Cannot read properties of null`
en runtime, con la app rota al arrancar. Es exactamente el fallo que **DT-15** advierte que no
detectan build ni tests — aquí ni siquiera hay build que lo tape.

**Corrección adoptada:** **NO tocar `tabDef`.** Se añade una función nueva `tabExiste(id)` que solo
comprueba existencia, y `__rbAbrirTab` la usa. Cero impacto en los otros 3 llamadores.

### 🟡 H-02 — Las 3 plantillas SÍ extienden `base.html`

`templates/main.html:1`, `MainChat/templates/mainchat_layout.html` y
`Colapsable/templates/colapsable_layout.html:1` hacen `{% extends "base.html" %}`. El plan previo
sugería "crear un control autónomo" en cada una: innecesario.

### 🟢 H-03 — OPORTUNIDAD · El bloque `sidebar` es el anclaje que ya comparten

`templates/base.html:61-67` define `{% block sidebar %}` con
`{% include 'components/sidebar.html' %}` por defecto. Y:

| Plantilla | Qué hace con el bloque |
|---|---|
| `main.html` | **Lo hereda** → renderiza `components/sidebar.html` (existe, 4.865 bytes) |
| `mainchat_layout.html:18-20` | Lo **anula vacío** — comentario obsoleto: *"la navegación vive en la navbar superior"*, navbar que se eliminó (`:28-29`) |
| `colapsable_layout.html:8` | Lo **anula** |

**Mejora sobre el plan previo:** en vez de inventar un control por plantilla, se crea **un único
parcial** `templates/components/nav_modulos.html` y cada plantilla lo incluye en su
`{% block sidebar %}`. Un solo sitio que mantener, coherente con el patrón Jinja ya existente.

⚠️ `components/sidebar.html` **no tiene navegación**: su único `href` es `#logout-btn` (:109). No
hay enlaces que reutilizar; el parcial es contenido nuevo.

### 🟡 H-04 — `templates/main.html` también carga `multitab_shell.js`

`templates/main.html:88` — `?v=20260825g`. Si el paso 1.1 toca ese archivo, **hay que subir el
cache-buster en las DOS plantillas**. Ya quedó rezagado antes (estuvo en `20260824k` mientras
MainChat iba en `20260825e`).

### 🟡 H-05 — `MARGEN = 8` en el posicionado del popover

`MainChat/static/js/mainchat.js:22`. `situar()` calcula `top = r.top - alto - MARGEN` y lo topa en
`if (top < MARGEN) top = MARGEN` (:40-41). `.mc-menu` (`mainchat.css:55-70`) **no tiene `max-height`
ni `overflow`**: al crecer la rejilla, el popover desborda el viewport sin scroll. El `max-height`
debe descontar `2 * MARGEN` = 16px.

---

## 4. RESTRICCIONES NO NEGOCIABLES

| # | Restricción | Evidencia |
|---|---|---|
| R-1 | **Toda tarjeta que pueda ser pestaña, debe serlo.** Navegar destruye el estado del shell (pila del Motor Q v2, análisis cargados): `mount()` la resetea | `multitab_shell.js:615-616`; es la razón por la que Test Clas usa `data-tab` |
| R-2 | **NO exponer `ingesta` ni `control`** en el waffle de `/mainchat` | `mainchat_layout.html:91-98`: esa vista no carga `chat.js` a propósito; esas pestañas se ven pero **no responden** |
| R-3 | **NO tocar `tabDef`** | H-01 |
| R-4 | El menú debe seguir montado en `.mc-shell`, **fuera** de `#mainchat-root` | `acordeon.js:329` hace `raiz.innerHTML=''` en cada colapsar/expandir |
| R-5 | **No declarar completada** ninguna fase sin validación visual en navegador | DT-15 |

---

## 5. FASE 1 — Pestañas al waffle

### Paso 1.1 · `tabExiste` + guarda real en `__rbAbrirTab`

**Archivo:** `c:\APLICACIONES\ProdIA\12112025_prodIA\ProdIA-2.0\ProdIA-2.0\static\js\multitab_shell.js`

**(a)** Justo DESPUÉS de `tabDef` (que termina en la línea 47), añadir:

```js
  // [2026-08-25] WAFFLE-NAV · tabDef() NUNCA devuelve falsy: cae a TABS[0] para que el rail y el
  // header del panel siempre tengan icono/label (sus 3 llamadores hacen def.icon / def.label sin
  // guarda). Por eso la comprobación de existencia va aparte: cambiar tabDef rompería :342, :493
  // y :624 con TypeError.
  function tabExiste(id) {
    for (var i = 0; i < TABS.length; i++) if (TABS[i].id === id) return true;
    return false;
  }
```

**(b)** En `__rbAbrirTab` (línea 518), sustituir la guarda inalcanzable:

```js
    if (!tabDef(tabId)) return false;      // pestaña inexistente → el llamador decide qué hacer
```
por:
```js
    if (!tabExiste(tabId)) return false;   // pestaña inexistente → el llamador decide qué hacer
```

⚠️ **NO modificar `tabDef`.** Es la conclusión de H-01.

### Paso 1.2 · Las dos tarjetas nuevas

**Archivo:** `MainChat\templates\mainchat_layout.html`

Insertar DESPUÉS del `</button>` de la tarjeta Test Clas (línea 68) y ANTES del
`<button ... data-ruta="/admin">` (línea 69):

```html
            <!-- [2026-08-25] WAFFLE-NAV · pestañas del shell, mismo mecanismo que Test Clas.
                 NO añadir aquí "ingesta" ni "control": esta vista no carga chat.js (ver el
                 comentario de :91-98), así que se abrirían visibles pero MUERTAS. -->
            <button type="button" class="mc-acceso" role="menuitem" data-tab="consulta">
                <i class="bi bi-chat-dots" style="color:#004236"></i>
                <span>Consulta</span>
            </button>
            <button type="button" class="mc-acceso" role="menuitem" data-tab="analisis">
                <i class="bi bi-graph-up-arrow" style="color:#15794C"></i>
                <span>Análisis</span>
            </button>
```

Los iconos son los que declara `TABS` (`multitab_shell.js:12-13`), para que waffle y rail no diverjan.

### Paso 1.3 · Rejilla y scroll del popover

**Archivo:** `MainChat\static\css\mainchat.css`

**(a)** Línea 131-136 — la rejilla está cableada a 4 columnas y con 6 tarjetas la 2ª fila queda coja.
Reemplazar el bloque `.mc-menu__accesos` por:

```css
/* Rejilla de accesos del waffle. [2026-08-25] auto-fit en vez de repeat(4,1fr) fijo: el número de
   tarjetas ya no es 4 y debe poder crecer sin dejar filas cojas. */
.mc-menu__accesos {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(66px, 1fr));
    gap: 7px;
}
```

**(b)** En `.mc-menu` (líneas 55-66), añadir antes del cierre de la regla:

```css
    /* [2026-08-25] situar() topa el popover en MARGEN=8 (mainchat.js:40-41) y .mc-menu no tenía
       límite de alto: al crecer la rejilla desbordaba el viewport SIN scroll. 2*MARGEN = 16px. */
    max-height: calc(100vh - 16px);
    overflow-y: auto;
```

### Paso 1.4 · Cache-busters

- `MainChat\templates\mainchat_layout.html` (líneas ~113-115): subir `?v=` de `mainchat.js` y de
  `mainchat.css`.
- **H-04:** el paso 1.1 toca `multitab_shell.js` → subir su `?v=` **en las DOS** plantillas:
  `MainChat\templates\mainchat_layout.html:113` y `templates\main.html:88`. Ambas deben quedar con
  **el mismo valor**.

### Validación Fase 1 (R-5: en navegador, no solo "no hay errores")

| # | Prueba | Resultado esperado |
|---|---|---|
| V1.1 | Abrir el menú de usuario en `/mainchat` | 6 tarjetas visibles y completas, sin desbordar ni cortarse |
| V1.2 | Clic en **Consulta** y en **Análisis** | Abre la pestaña correspondiente y el menú se cierra |
| V1.3 | **Estado:** cargar un análisis en Consulta → waffle → Análisis → waffle → Consulta | El trabajo previo **sigue ahí** (esto se perdería si fueran rutas) |
| V1.4 | **Guarda:** en consola, `document.querySelector('[data-tab="analisis"]').dataset.tab='noexiste'` y clic | Sale el `console.warn` de `mainchat.js:108` y **NO** se abre Ingesta |
| V1.5 | Regresión: Test Clas | Sigue funcionando; el rail del shell no cambió |
| V1.6 | Viewport 1366×768 y 1280×720 | El popover no desborda; aparece scroll si hace falta |
| V1.7 | Regresión `/`: cargar la vista y cambiar de pestaña | El shell arranca y el rail responde (valida que 1.1 no rompió nada) |
| V1.8 | F12 → Console en ambas vistas | 0 errores nuevos |

---

## 6. FASE 2 — Navegación entre vistas

⚠️ **El paso 2.1 va PRIMERO.** Hoy `/` y `/layout/colapsable` no tienen forma de volver: añadir
enlaces *hacia* ellas antes de darles salida convierte cada enlace en una trampa.

### Paso 2.1 · Parcial de navegación compartido (H-03)

**(a) Crear** `c:\APLICACIONES\ProdIA\12112025_prodIA\ProdIA-2.0\ProdIA-2.0\templates\components\nav_modulos.html`:

```html
{# [2026-08-25] WAFFLE-NAV · navegación entre las 3 vistas HTML de la app. Se incluye desde el
   {% block sidebar %} de cada plantilla, que las 3 heredan de base.html. Un solo parcial en vez de
   un control por plantilla: mismo patrón que components/sidebar.html.
   `request.path` marca la vista activa sin JS. #}
<nav class="nav-modulos" aria-label="Módulos">
    <a class="nav-modulos__item{% if request.path == '/mainchat' %} is-active{% endif %}"
       href="{{ url_for('mainchat.mainchat_view') }}">
        <i class="bi bi-chat-dots" aria-hidden="true"></i><span>Chat</span>
    </a>
    <a class="nav-modulos__item{% if request.path == '/' %} is-active{% endif %}"
       href="{{ url_for('main.index') }}">
        <i class="bi bi-columns-gap" aria-hidden="true"></i><span>Clásico</span>
    </a>
    <a class="nav-modulos__item{% if request.path.startswith('/layout') %} is-active{% endif %}"
       href="{{ url_for('colapsable.colapsable_view') }}">
        <i class="bi bi-layout-sidebar-inset" aria-hidden="true"></i><span>Colapsable</span>
    </a>
</nav>
```

⚠️ **Verificar los endpoints antes de escribir** (no de memoria):
```bash
grep -rn "def index\|def mainchat_view\|def colapsable_view" routes/
```
Los nombres esperados son `main.index`, `mainchat.mainchat_view`, `colapsable.colapsable_view`. Si
alguno difiere, usar el real: un `url_for` equivocado lanza `BuildError` y **rompe la página entera**.

**(b) Incluirlo** en las dos plantillas que anulan el bloque:

- `MainChat\templates\mainchat_layout.html:18-20` — sustituir el bloque vacío (y su comentario
  obsoleto sobre la navbar) por `{% block sidebar %}{% include 'components/nav_modulos.html' %}{% endblock %}`.
- `Colapsable\templates\colapsable_layout.html:8` — ídem.
- `templates\main.html` **no anula el bloque**: hereda `components/sidebar.html`. Añadir ahí el
  `{% include %}` al inicio de ese parcial, o anular el bloque en `main.html` incluyendo ambos.
  **Decisión:** incluirlo al inicio de `templates\components\sidebar.html`, para que la navegación
  quede en un solo sitio.

**(c) CSS** en `static\css\style.css` (o el que ya cargue `base.html`): estilos de
`.nav-modulos` / `.nav-modulos__item` / `.is-active`. Sobrio, coherente con el sidebar existente.
Verificar en qué hoja vive el sidebar actual antes de elegir archivo.

### Paso 2.2 · Retirar las tarjetas sin ruta

`grep -rn "route(\"/admin\"\|route(\"/settings\"\|route(\"/help\"" routes/ app.py` → **cero
coincidencias**. Las tres tarjetas apuntan a rutas inexistentes.

**Acción:** eliminar del waffle los tres `<button data-ruta="...">`
(`mainchat_layout.html:69-79`), dejando un comentario que registre por qué:

```html
            <!-- [2026-08-25] WAFFLE-NAV · retiradas Admin / Configuración / Ayuda: apuntaban a
                 /admin, /settings y /help, que NO EXISTEN (el JS hacía console.info en vez de
                 navegar). Reponerlas cuando las vistas existan. Admin necesitará además control de
                 roles, que hoy la app no tiene: @login_required es autenticación, no autorización,
                 y la insignia ADMIN de :53 es texto fijo que ve todo usuario. -->
```

Con esto **desaparece la rama `data-ruta`** del waffle. En `MainChat\static\js\mainchat.js:110-115`
el `else` con `console.info` queda sin uso: **dejarlo tal cual** (es el contrato documentado para
futuras tarjetas de ruta) y actualizar solo su comentario si procede. No convertirlo en
`window.location.href` — ya no hay ninguna tarjeta que lo use, y la navegación de la Fase 2 vive en
el parcial de 2.1, no en el waffle.

### Paso 2.3 · Cache-busters

Subir `?v=` de `mainchat.html` (si cambió su CSS) y del CSS nuevo de 2.1 en `base.html`.

### Validación Fase 2

| # | Prueba | Resultado esperado |
|---|---|---|
| V2.1 | Entrar por URL directa a `/`, `/mainchat` y `/layout/colapsable` | Las 3 cargan y las 3 muestran la navegación |
| V2.2 | Desde cada una, ir a las otras dos | Ninguna vista queda sin salida |
| V2.3 | La vista actual aparece marcada | `is-active` correcto en las 3 |
| V2.4 | El waffle ya no ofrece destinos muertos | Solo quedan tarjetas `data-tab` |
| V2.5 | Regresión Fase 1 | V1.1-V1.8 siguen pasando |
| V2.6 | F12 → Console en las 3 vistas | 0 errores; ningún `BuildError` de Jinja |

⚠️ **Nota de UX a reportar, no a resolver aquí:** navegar entre vistas **descarta el estado del
shell** (pila de Consulta, análisis cargados). Es inherente a que sean páginas distintas. Si en la
prueba resulta molesto, escalar al usuario antes de inventar una solución.

---

## 7. ORDEN DE EJECUCIÓN

1. Paso 1.1 (`tabExiste`) → **V1.7** (regresión de `/` antes de seguir).
2. Paso 1.2 (tarjetas) → 1.3 (CSS) → 1.4 (cache-busters) → **V1.1-V1.8**.
3. 🛑 **Parar y reportar.** La Fase 2 no arranca sin visto bueno.
4. Paso 2.1 (parcial + includes + CSS) → **V2.1-V2.3**.
5. Paso 2.2 (retirar tarjetas muertas) → 2.3 → **V2.4-V2.6**.

---

## 8. FUERA DE ALCANCE

- **Ingesta y Control en el waffle** (R-2) — requieren cargar `chat.js` en `/mainchat`.
- **Crear `/admin`, `/settings`, `/help`** — son vistas nuevas, no un cambio de menú.
- **Control de roles** — no existe ninguno. Deuda a registrar en la bitácora.
- **Portar `#mc-menu` completo a las otras vistas** — su disparador lo pinta `bloqueUsuario()`
  (`historial.js:343-355`), específico del acordeón de MainChat. Proyecto aparte.
- **Modificar `tabDef`** (R-3, H-01).

---

## 9. REGLAS NO NEGOCIABLES PARA EL EXECUTOR

1. **CERO modificaciones fuera de lo especificado.** Si algo no está en el plan, no se toca.
2. **Orden secuencial.** Si un paso falla, **DETENERSE** y reportar; no improvisar un arreglo.
3. **No tocar `tabDef`** bajo ninguna circunstancia (H-01).
4. **Verificar los endpoints de `url_for` con grep** antes de escribir el parcial (2.1a). Un
   `url_for` inválido rompe la página entera con `BuildError`.
5. **Cache-buster en las DOS plantillas** al tocar `multitab_shell.js` (H-04).
6. **Ninguna fase se declara completada sin abrir el navegador** (DT-15/R-5). "Sin errores en
   consola" no es validación: hay que ejecutar las pruebas V1.x / V2.x.
7. **No commitear sin autorización.** Al final: listar archivos tocados y preguntar.
