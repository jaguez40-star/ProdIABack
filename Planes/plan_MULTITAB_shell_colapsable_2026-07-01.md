# Plan de ejecución — Shell MultiTab (pestañas verticales) en el sandbox `/layout/colapsable`

> **Para agente EXECUTOR sin acceso previo al repositorio ni a esta conversación.**
> Ejecutar AL PIE DE LA LETRA, en orden, sin decidir nada por cuenta propia. Si algo falla, DETENERSE y reportar.

**Tablas: entrada 0 → salida 0** — N/A: este plan es 100% shell de UI (HTML/CSS/JS estáticos con datos mock). No ingiere, transforma ni omite ninguna tabla de ninguna fuente.

---

## 1 · Contexto

**ProdIA / ECP Insights** es una app Flask (Python 3.13, puerto `:8020`) en
`C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\` con frontend **vanilla JS + Bootstrap 5.3 (CDN) + Bootstrap Icons 1.11.3 (CDN)** — SIN React, SIN build step, SIN Sass. Los archivos JS son clases/funciones globales (`window.*`) cargados por `<script>` desde templates Jinja2.

Hoy la funcionalidad de **Ingesta del Reporte Diario** (card "Cargar Reporte Diario" + árbol "Hojas del archivo" + visor de tablas) vive **inyectada dentro del panel de chat** (`chat-panel`, 30% del ancho) por `static/js/chat.js` (~4.800 líneas, archivo compartido con el chat LLM — **NO tocar**).

Existe una **ruta sandbox ya cableada y vacía** pensada exactamente para esto (su docstring dice *"Keeps logic separated so current pipelines remain untouched"*):

- Ruta: `GET /layout/colapsable` (requiere login) — blueprint `colapsable_bp` ya registrado en `app.py` líneas 77-83.
- Template: `Colapsable/templates/colapsable_layout.html` — extiende `templates/base.html`, hoy renderiza un panel vacío ("Panel intencionalmente vacío para pruebas de layout").
- CSS: `Colapsable/static/css/colapsable.css` — servido vía `url_for('colapsable.static', ...)` con `static_url_path="/colapsable-static"`.
- Carpeta `Colapsable/static/js/` — **ya existe, está vacía**.

`base.html` (heredado por el template sandbox) ya carga: Bootstrap 5.3.0 CSS/JS (CDN), Font Awesome 6 (CDN), **Bootstrap Icons 1.11.3 (CDN)**, `style.css`, `enhanced-tables.css`, `ingesta.css`, Socket.IO y Plotly (vendor local), y `static/js/main.js`. El template sandbox **NO** carga `chat.js` ni `panels.js` — no hay conflicto con `PanelManager` ni `ChatManager`.

**Objetivo de negocio:** implementar el **shell de panel de control con pestañas verticales** (diseño aprobado "variante A · Pastillas rotadas" del documento `multitap.md`) como **prototipo aislado en el sandbox**, para validar la interacción de 3 zonas (riel vertical 60px → panel de contenido 372px → visualizador fluido) SIN tocar el pipeline real de chat/ingesta. La pestaña Ingesta muestra una **maqueta estática** (mock) de la card de carga + árbol de hojas; Control y Análisis son placeholders "en construcción". La conexión a la API real de ingesta es una fase POSTERIOR, fuera de este plan.

### Decisiones ya cerradas (NO reabrir)

1. **Stack: vanilla JS + CSS plano** (el `multitap.md` original pedía React/TS/Zustand/Sass/react-bootstrap — eso NO aplica; se adapta todo su diseño visual y de interacción a vanilla, siguiendo el patrón de clases/IIFE ya usado en `static/js/panels.js`).
2. **Dónde:** exclusivamente el sandbox `/layout/colapsable`. CERO cambios en `chat.js`, `panels.js`, `main.html`, `app.py`, o cualquier `.py`.
3. **Pestañas Control y Análisis:** contenedores vacíos "en construcción" (sin lógica).
4. **Pestaña Ingesta:** maqueta visual estática con datos mock hardcodeados (card + árbol + selección de tabla que alimenta un visor con tabla mock). Sin fetch, sin Socket.IO, sin API.
5. **Estilos autocontenidos** bajo el prefijo `rb-cp` (verificado: no existe en ningún CSS/JS del proyecto — cero colisión). NO se reutilizan las clases `ig-*` de `ingesta.css` para no acoplar el sandbox a la evolución del pipeline real.
6. **Tipografía:** el proyecto no carga Inter; el stack de fuente declara `'Inter', -apple-system, 'Segoe UI', system-ui, Arial, sans-serif` y cae limpiamente a Segoe UI. NO agregar ningún `<link>` de Google Fonts.
7. **Colapso del panel:** el sandbox es dueño de su propio booleano de colapso (no existe host que lo controle en esta página). El botón `−` del header oculta el panel de contenido; el riel queda visible; clic en cualquier pestaña del riel lo reabre.

---

## 2 · Objetivo

Transformar el contenido de `/layout/colapsable` en un shell de 3 zonas, de izquierda a derecha:

1. **Riel de pestañas vertical** (60px, fondo verde `#0E5C3A`): logo arriba + 3 pestañas con etiqueta rotada. La activa se "conecta" al panel (fondo blanco, radio izquierdo, desplazada 8px, barra dorada).
2. **Panel de contenido** (372px, blanco): header (icono + título de pestaña + marca PRODIA + botón colapsar) + cuerpo según pestaña activa.
3. **Visualizador** (fluido, `flex:1`): reacciona a la pestaña activa Y a la selección interna (tabla del árbol de Ingesta).

| id | Etiqueta | Icono (Bootstrap Icons) | Contenido |
|---|---|---|---|
| `ingesta` | Ingesta | `bi-cloud-arrow-up-fill` | Mock: card "Cargar Reporte Diario" + árbol de hojas |
| `control` | Control | `bi-sliders2` | Placeholder "en construcción" |
| `analisis` | Análisis | `bi-graph-up-arrow` | Placeholder "en construcción" |

Pestaña por defecto: `ingesta`. Selección por defecto: ninguna (visualizador en estado vacío). La selección **persiste** al cambiar de pestaña y volver (estado en memoria — sin `localStorage`).

---

## 3 · Prerequisitos

Raíz del proyecto: `C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\`. Las rutas relativas de este plan son relativas a esa raíz — por eso P0 es obligatorio ANTES de cualquier otro comando (el plan vive en `INGESTA\Rep_Prod\Planes\`, 2 niveles abajo de sus targets: NO asumir cwd).

| # | Verificación | Cómo comprobar | Esperado |
|---|---|---|---|
| P0 | Posicionarse en la raíz del proyecto | `cd /d C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA` y luego `cd` | Imprime exactamente esa ruta. TODOS los comandos de este plan (P1-P6, pasos §6, V1-V4) se ejecutan desde ahí |
| P1 | El sandbox existe y está cableado | `grep -n "colapsable" app.py` | Líneas ~77 (`from routes.colapsable import colapsable_bp`) y ~83 (`app.register_blueprint(colapsable_bp)`) |
| P2 | Template y CSS actuales existen | `ls Colapsable/templates/colapsable_layout.html Colapsable/static/css/colapsable.css` | Ambos presentes |
| P3 | Carpeta JS del blueprint existe | `ls Colapsable/static/` | Contiene `css` y `js` |
| P4 | Bootstrap Icons cargado globalmente | `grep -n "bootstrap-icons" templates/base.html` | 1 línea (CDN 1.11.3) |
| P5 | Sin colisión del prefijo de clases | `grep -rn "rb-cp" static/css/ static/js/ Colapsable/` | Sin resultados |
| P6 | Node disponible para el check de sintaxis JS (opcional) | `node --version` | v20+ (si no existe, V1 se sustituye por revisión en consola del navegador) |

Si P1-P5 falla, DETENERSE y reportar — no improvisar.

---

## 4 · Inventario de archivos

### 4.1 Se MODIFICAN

| Archivo (ruta absoluta) | Cambio |
|---|---|
| `C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\Colapsable\templates\colapsable_layout.html` | Reemplazar el bloque `content` por el shell de 3 zonas + agregar `<script>` en el bloque `scripts` (código completo en §5.1) |
| `C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\Colapsable\static\css\colapsable.css` | **APPEND** de la sección `rb-cp` al final (código completo en §5.2). NO borrar las reglas existentes (`.colapsable-layout` se sigue usando como contenedor exterior; el resto queda huérfano inofensivo en el sandbox) |

### 4.2 Se CREAN

| Archivo (ruta absoluta) |
|---|
| `C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\Colapsable\static\js\colapsable.js` (código completo en §5.3) |

### 4.3 PROHIBIDO tocar (lista explícita)

`app.py` · `routes/**` (incluido `routes/colapsable.py`) · `static/js/chat.js` · `static/js/panels.js` · `static/js/main.js` · `static/css/style.css` · `static/css/ingesta.css` · `static/css/enhanced-tables.css` · `templates/main.html` · `templates/base.html` · `templates/components/**` · cualquier `.py` · cualquier archivo bajo `INGESTA/` (salvo guardar este plan en `Planes/`).

---

## 5 · Especificación

### 5.1 — `C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\Colapsable\templates\colapsable_layout.html` (REEMPLAZAR el archivo completo por esto)

```html
{% extends "base.html" %}

{% block head %}
    {{ super() }}
    <link rel="stylesheet" href="{{ url_for('colapsable.static', filename='css/colapsable.css') }}?v=20260701">
{% endblock %}

{% block sidebar %}
    <!-- Sidebar intencionalmente vacío en vista alterna -->
{% endblock %}

{% block content %}
<div class="colapsable-layout">
    <!-- Shell MultiTab · variante A (pastillas rotadas) · prototipo aislado -->
    <div class="rb-cp" id="rb-cp">

        <!-- Zona 1 · Riel de pestañas vertical -->
        <div class="rb-cp__rail" role="tablist" aria-orientation="vertical" aria-label="Secciones del panel">
            <div class="rb-cp__rail-logo" aria-hidden="true">
                <span><i class="bi bi-hexagon-fill"></i></span>
            </div>
            <button type="button" role="tab" id="cp-tab-ingesta" data-tab="ingesta"
                    class="rb-cp__tab is-active" aria-selected="true"
                    aria-controls="rb-cp-panel-body" tabindex="0" title="Ingesta">
                <i class="bi bi-cloud-arrow-up-fill rb-cp__tab-icon" aria-hidden="true"></i>
                <span class="rb-cp__tab-label">Ingesta</span>
            </button>
            <button type="button" role="tab" id="cp-tab-control" data-tab="control"
                    class="rb-cp__tab" aria-selected="false"
                    aria-controls="rb-cp-panel-body" tabindex="-1" title="Control">
                <i class="bi bi-sliders2 rb-cp__tab-icon" aria-hidden="true"></i>
                <span class="rb-cp__tab-label">Control</span>
            </button>
            <button type="button" role="tab" id="cp-tab-analisis" data-tab="analisis"
                    class="rb-cp__tab" aria-selected="false"
                    aria-controls="rb-cp-panel-body" tabindex="-1" title="Análisis">
                <i class="bi bi-graph-up-arrow rb-cp__tab-icon" aria-hidden="true"></i>
                <span class="rb-cp__tab-label">Análisis</span>
            </button>
        </div>

        <!-- Zona 2 · Panel de contenido -->
        <section class="rb-cp__panel" id="rb-cp-panel" aria-label="Panel Ingesta">
            <header class="rb-cp__panel-head">
                <i class="bi bi-cloud-arrow-up-fill rb-cp__panel-head-icon" id="rb-cp-head-icon" aria-hidden="true"></i>
                <span class="rb-cp__panel-head-title" id="rb-cp-head-title">INGESTA</span>
                <span class="rb-cp__panel-head-brand">PRODIA</span>
                <button type="button" class="rb-cp__panel-head-collapse" id="rb-cp-collapse" aria-label="Colapsar panel">
                    <i class="bi bi-dash-lg" aria-hidden="true"></i>
                </button>
            </header>
            <div class="rb-cp__panel-body" role="tabpanel" id="rb-cp-panel-body" aria-labelledby="cp-tab-ingesta">
                <!-- Contenido inyectado por colapsable.js según la pestaña activa -->
            </div>
        </section>

        <!-- Zona 3 · Visualizador.
             NOTA: <section>, NO <main> — base.html ya envuelve el bloque content
             en <main class="main-content"> y anidar dos <main> es HTML inválido
             (landmark duplicado para lectores de pantalla). -->
        <section class="rb-cp__viewer" id="rb-cp-viewer" aria-label="Visualizador">
            <!-- Contenido inyectado por colapsable.js -->
        </section>

    </div>
</div>

<!-- Footer reutilizado -->
<div class="app-footer">
    <div class="text-caption">
        <strong>Copyright - Ecopetrol S.A Copyright todos los derechos reservados. INFORMACION CONFIDENCIAL. Prohibido su uso sin la debida autorizacion.</strong> | All rights reserved.
    </div>
</div>
{% endblock %}

{% block scripts %}
    {{ super() }}
    <script src="{{ url_for('colapsable.static', filename='js/colapsable.js') }}?v=20260701"></script>
{% endblock %}
```

### 5.2 — `C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\Colapsable\static\css\colapsable.css` (APPEND al final del archivo — conservar TODO lo existente)

```css
/* ==================================================================
   Shell MultiTab · pestañas verticales (variante A · pastillas rotadas)
   Prototipo aislado — solo vive en /layout/colapsable.
   Prefijo rb-cp (verificado sin colisiones en el proyecto).
   ================================================================== */

/* Override del contenedor exterior: el .app-footer global de style.css es
   position:fixed; bottom:0 (~30px de alto) y tapaba la base del shell
   (riel verde + fila .rb-cp-vfoot + scrollbar horizontal del visor).
   Esta regla va DESPUÉS de la original en el mismo archivo → gana en cascada. */
.colapsable-layout {
  height: calc(100vh - 2rem - 32px);
}

.rb-cp {
  /* Paleta verde PRODIA (del documento de diseño multitap.md §4) */
  --rb-green: #0e5c3a;
  --rb-green-mid: #15794c;
  --rb-green-ok: #1e9e5a;
  --rb-green-soft: #e6f4ec;
  --rb-green-softer: #f1f9f4;
  --rb-gold: #f2c94c;
  --rb-amber-text: #c77f00; /* ámbar legible sobre fondo claro (eyebrows) */
  --rb-ink: #1b2a33;
  --rb-body: #3d4d58;
  --rb-muted: #74838e;
  --rb-faint: #9aa8b0;
  --rb-line: #e2e8ec;
  --rb-line-soft: #eef2f5;
  --rb-off: #f6f9fb;
  --rb-white: #ffffff;
  --rb-font-sans: 'Inter', -apple-system, 'Segoe UI', system-ui, Arial, sans-serif;
  --rb-font-mono: ui-monospace, 'SF Mono', 'Cascadia Mono', Menlo, Consolas, monospace;

  display: flex;
  flex: 1 1 auto;
  min-width: 0;
  height: 100%;
  background: var(--rb-white);
  border-radius: 12px;
  border: 1px solid rgba(0, 66, 54, 0.15);
  box-shadow: 0 18px 36px -28px rgba(0, 0, 0, 0.4);
  overflow: hidden;
  font-family: var(--rb-font-sans);
}

/* ---------- Zona 1 · Riel vertical ---------- */
.rb-cp__rail {
  width: 60px;
  flex: 0 0 auto;
  background: var(--rb-green);
  display: flex;
  flex-direction: column;
  align-items: stretch;
  padding-top: 8px;
}

.rb-cp__rail-logo {
  height: 44px;
  display: grid;
  place-items: center;
  margin-bottom: 6px;
}

.rb-cp__rail-logo span {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.12);
  display: grid;
  place-items: center;
}

.rb-cp__rail-logo i {
  font-size: 15px;
  color: var(--rb-gold);
}

.rb-cp__tab {
  position: relative;
  height: 118px;
  margin-bottom: 4px;
  border: 0;
  cursor: pointer;
  background: transparent;
  color: rgba(255, 255, 255, 0.7);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 9px;
  transition: background 0.18s ease, color 0.18s ease, margin 0.18s ease;
}

.rb-cp__tab-icon {
  font-size: 17px;
  color: rgba(255, 255, 255, 0.75);
}

.rb-cp__tab-label {
  writing-mode: vertical-rl;
  transform: rotate(180deg);
  font-family: var(--rb-font-sans);
  font-weight: 800;
  font-size: 12px;
  line-height: 1;
  letter-spacing: 0.4px;
}

.rb-cp__tab.is-active {
  background: var(--rb-white);
  color: var(--rb-green);
  border-radius: 10px 0 0 10px;
  margin-left: 8px;
}

.rb-cp__tab.is-active .rb-cp__tab-icon {
  color: var(--rb-green-mid);
}

.rb-cp__tab.is-active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 12px;
  bottom: 12px;
  width: 3px;
  border-radius: 3px;
  background: var(--rb-gold);
}

.rb-cp__tab:focus-visible {
  outline: none;
  box-shadow: inset 0 0 0 2px rgba(242, 201, 76, 0.8);
}

/* ---------- Zona 2 · Panel de contenido ---------- */
.rb-cp__panel {
  width: 372px;
  flex: 0 0 auto;
  border-right: 1px solid var(--rb-line);
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--rb-white);
}

.rb-cp.is-collapsed .rb-cp__panel {
  display: none;
}

.rb-cp__panel-head {
  height: 48px;
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 14px;
  background: var(--rb-off);
  border-bottom: 1px solid var(--rb-line);
}

.rb-cp__panel-head-icon {
  font-size: 15px;
  color: var(--rb-green-mid);
}

.rb-cp__panel-head-title {
  font-weight: 800;
  font-size: 13px;
  letter-spacing: 0.3px;
  color: var(--rb-green);
}

.rb-cp__panel-head-brand {
  font-size: 11px;
  color: var(--rb-muted);
  padding-left: 8px;
  border-left: 1px solid var(--rb-line);
}

.rb-cp__panel-head-collapse {
  margin-left: auto;
  width: 26px;
  height: 26px;
  border-radius: 6px;
  border: 1px solid var(--rb-line);
  background: var(--rb-white);
  display: grid;
  place-items: center;
  cursor: pointer;
  color: var(--rb-muted);
}

.rb-cp__panel-head-collapse:hover {
  background: var(--rb-off);
}

.rb-cp__panel-body {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
  padding: 12px;
}

/* ---------- Zona 3 · Visualizador ---------- */
.rb-cp__viewer {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--rb-off);
}

/* Cabecera verde del visualizador */
.rb-cp-vhead {
  height: 44px;
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 0 14px;
  background: var(--rb-green);
  color: var(--rb-white);
}

.rb-cp-vhead i {
  color: var(--rb-gold);
  font-size: 14px;
}

.rb-cp-vhead__title {
  font-weight: 800;
  font-size: 13px;
}

.rb-cp-vhead__title.is-gold {
  color: var(--rb-gold);
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.rb-cp-vhead__meta {
  margin-left: auto;
  font-family: var(--rb-font-mono);
  font-size: 11px;
  color: rgba(255, 255, 255, 0.85);
}

/* Estado vacío del visualizador */
.rb-cp-vempty {
  flex: 1;
  display: grid;
  place-items: center;
  padding: 24px;
}

.rb-cp-vempty__inner {
  text-align: center;
  max-width: 420px;
}

.rb-cp-vempty__chip {
  width: 64px;
  height: 64px;
  border-radius: 16px;
  background: var(--rb-green-softer);
  display: grid;
  place-items: center;
  margin: 0 auto 12px;
}

.rb-cp-vempty__chip i {
  font-size: 28px;
  color: var(--rb-green-ok);
}

.rb-cp-vempty__eyebrow {
  font-family: var(--rb-font-mono);
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--rb-amber-text);
  margin-bottom: 4px;
}

.rb-cp-vempty__hint {
  font-size: 15px;
  font-weight: 700;
  color: var(--rb-ink);
  margin: 0;
}

/* Tabla mock del visualizador */
.rb-cp-vtable {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 12px 14px;
}

.rb-cp-vtable table {
  border-collapse: separate;
  border-spacing: 0;
  width: max-content;
  min-width: 100%;
  background: var(--rb-white);
  border: 1px solid var(--rb-line);
  border-radius: 8px;
  font-size: 12.5px;
}

.rb-cp-vtable th,
.rb-cp-vtable td {
  padding: 7px 12px;
  border-bottom: 1px solid var(--rb-line-soft);
  white-space: nowrap;
}

.rb-cp-vtable thead th {
  position: sticky;
  top: 0;
  background: var(--rb-green);
  color: var(--rb-white);
  font-weight: 700;
  z-index: 2;
  text-align: right;
}

.rb-cp-vtable thead th:first-child,
.rb-cp-vtable thead th:nth-child(2) {
  text-align: left;
}

.rb-cp-vtable tbody th {
  position: sticky;
  left: 0;
  background: var(--rb-white);
  font-weight: 600;
  color: var(--rb-ink);
  z-index: 1;
  text-align: left;
}

.rb-cp-vtable thead th:first-child {
  left: 0;
  z-index: 3;
}

.rb-cp-vtable td {
  font-family: var(--rb-font-mono);
  font-variant-numeric: tabular-nums;
  text-align: right;
  color: var(--rb-body);
}

.rb-cp-vtable td.is-dim {
  font-family: var(--rb-font-sans);
  text-align: left;
  color: var(--rb-ink);
  font-weight: 600;
}

.rb-cp-vfoot {
  flex: 0 0 auto;
  padding: 8px 14px;
  border-top: 1px solid var(--rb-line);
  font-family: var(--rb-font-mono);
  font-size: 10.5px;
  color: var(--rb-muted);
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

/* ---------- Contenido pestaña Ingesta (mock) ---------- */
.rb-cp-upcard {
  border: 1px solid var(--rb-line);
  border-radius: 10px;
  overflow: hidden;
  margin-bottom: 14px;
  background: var(--rb-white);
}

.rb-cp-upcard__head {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 10px 12px;
  background: var(--rb-green);
  color: var(--rb-white);
}

.rb-cp-upcard__head i {
  color: var(--rb-gold);
  font-size: 15px;
}

.rb-cp-upcard__head strong {
  font-size: 12.5px;
  display: block;
  line-height: 1.2;
}

.rb-cp-upcard__head small {
  font-family: var(--rb-font-mono);
  font-size: 9.5px;
  color: rgba(255, 255, 255, 0.75);
}

.rb-cp-upcard__new {
  margin-left: auto;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.08em;
  background: var(--rb-gold);
  color: var(--rb-ink);
  border-radius: 4px;
  padding: 2px 6px;
}

.rb-cp-upcard__file {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 10px 12px;
  background: var(--rb-off);
}

.rb-cp-upcard__file > i {
  font-size: 20px;
  color: var(--rb-green-ok);
}

.rb-cp-upcard__file strong {
  font-size: 12px;
  color: var(--rb-ink);
  display: block;
  line-height: 1.25;
}

.rb-cp-upcard__file small {
  font-size: 10.5px;
  color: var(--rb-green-ok);
}

.rb-cp-upcard__change {
  margin-left: auto;
  border: 1px solid var(--rb-line);
  background: var(--rb-white);
  border-radius: 6px;
  font-size: 11px;
  padding: 4px 10px;
  color: var(--rb-body);
}

.rb-cp-upcard__submit {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: calc(100% - 24px);
  margin: 10px 12px 12px;
  padding: 9px 0;
  border: 0;
  border-radius: 8px;
  background: var(--rb-green);
  color: var(--rb-white);
  font-weight: 800;
  font-size: 12px;
  letter-spacing: 0.4px;
}

.rb-cp-upcard__submit:disabled,
.rb-cp-upcard__change:disabled {
  opacity: 0.75;
  cursor: not-allowed;
}

.rb-cp-treehd {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 2px 2px 8px;
  font-size: 12.5px;
  color: var(--rb-ink);
}

.rb-cp-badge {
  font-family: var(--rb-font-mono);
  font-size: 10px;
  background: var(--rb-green-soft);
  color: var(--rb-green-mid);
  border-radius: 5px;
  padding: 2px 7px;
}

.rb-cp-badge--blue {
  background: #eaf1fe;
  color: #2563eb;
}

.rb-cp-tree {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.rb-cp-tree__sheet {
  border: 1px solid var(--rb-line);
  border-radius: 9px;
  background: var(--rb-white);
  overflow: hidden;
}

.rb-cp-tree__sheethd {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  border: 0;
  background: transparent;
  padding: 9px 10px;
  cursor: pointer;
  font-size: 12.5px;
  font-weight: 700;
  color: var(--rb-ink);
  text-align: left;
}

.rb-cp-tree__sheethd .rb-cp-chev {
  font-size: 11px;
  color: var(--rb-faint);
  transition: transform 0.15s ease;
}

.rb-cp-tree__sheet.is-open .rb-cp-chev {
  transform: rotate(90deg);
}

.rb-cp-tree__sheethd .rb-cp-ok {
  color: var(--rb-green-ok);
  font-size: 13px;
}

.rb-cp-tree__sheethd .rb-cp-badge {
  margin-left: auto;
}

.rb-cp-tree__kids {
  display: none;
  padding: 2px 10px 10px 26px;
}

.rb-cp-tree__sheet.is-open .rb-cp-tree__kids {
  display: block;
}

.rb-cp-tree__meta {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 11.5px;
  color: var(--rb-muted);
  padding: 4px 2px;
}

.rb-cp-tree__meta i {
  font-size: 12px;
  color: var(--rb-faint);
}

.rb-cp-tree__meta code {
  font-family: var(--rb-font-mono);
  font-size: 10.5px;
  background: var(--rb-green-soft);
  color: var(--rb-green-mid);
  border-radius: 4px;
  padding: 1px 6px;
}

.rb-cp-tree__grouphd {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 11.5px;
  font-weight: 700;
  color: var(--rb-body);
  padding: 6px 2px 4px;
}

.rb-cp-tree__grouphd i {
  color: var(--rb-faint);
}

.rb-cp-tree__row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  border: 0;
  border-left: 3px solid transparent;
  background: transparent;
  border-radius: 7px;
  padding: 6px 8px;
  cursor: pointer;
  font-size: 12px;
  color: var(--rb-body);
  text-align: left;
}

.rb-cp-tree__row i {
  font-size: 12px;
  color: var(--rb-faint);
}

.rb-cp-tree__row .rb-cp-badge {
  margin-left: auto;
}

.rb-cp-tree__row:hover {
  background: var(--rb-off);
}

.rb-cp-tree__row.is-active {
  background: var(--rb-green-soft);
  border-left-color: var(--rb-green-ok);
  color: var(--rb-ink);
  font-weight: 700;
}

.rb-cp-tree__row.is-active i {
  color: var(--rb-green-mid);
}

.rb-cp-tree__rowtag {
  font-family: var(--rb-font-mono);
  font-size: 10px;
  color: var(--rb-faint);
}

/* ---------- Placeholders Control / Análisis ---------- */
.rb-cp-empty {
  padding: 10px 6px;
}

.rb-cp-empty__eyebrow {
  font-family: var(--rb-font-mono);
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--rb-amber-text);
  margin-bottom: 6px;
}

.rb-cp-empty__title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 800;
  color: var(--rb-ink);
  margin: 0 0 4px;
}

.rb-cp-empty__title i {
  color: var(--rb-green-mid);
}

.rb-cp-empty__sub {
  font-size: 12px;
  color: var(--rb-muted);
  margin: 0 0 14px;
}

.rb-cp-empty__drop {
  min-height: 200px;
  border: 1.5px dashed var(--rb-line);
  border-radius: 10px;
  display: grid;
  place-items: center;
  text-align: center;
  color: var(--rb-faint);
  padding: 18px;
}

.rb-cp-empty__drop i {
  font-size: 26px;
  display: block;
  margin-bottom: 8px;
}

.rb-cp-empty__drop span {
  font-family: var(--rb-font-mono);
  font-size: 11px;
  display: block;
}

/* ---------- Accesibilidad · movimiento ---------- */
@media (prefers-reduced-motion: reduce) {
  .rb-cp,
  .rb-cp * {
    transition: none !important;
    animation: none !important;
  }
}
```

### 5.3 — `C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\Colapsable\static\js\colapsable.js` (CREAR — archivo completo)

```javascript
// =====================================================================
// Shell MultiTab · pestañas verticales (variante A · pastillas rotadas)
// Prototipo aislado — solo se carga en /layout/colapsable.
// Vanilla JS (patrón del proyecto: clase + estado en memoria, sin deps).
// Fase actual: datos MOCK hardcodeados. La conexión a la API real de
// ingesta (/ingesta/*, /tablas/*) es una fase posterior.
// =====================================================================

(function () {
  "use strict";

  // ---------- Definición declarativa de pestañas ----------
  var TABS = [
    { id: "ingesta", label: "Ingesta", icon: "cloud-arrow-up-fill", sub: "Cargar y mapear reporte" },
    { id: "control", label: "Control", icon: "sliders2", sub: "Parámetros y reglas" },
    { id: "analisis", label: "Análisis", icon: "graph-up-arrow", sub: "Vistas avanzadas" },
  ];

  // ---------- Datos MOCK (espejo visual de la ingesta real) ----------
  var MOCK_SHEETS = [
    {
      id: "s-p50",
      name: "P50 Quemado 2024 ECP y Fili",
      tablas: 2,
      open: false,
      tables: [
        { id: "t-p50-1", name: "Tabla 1", tag: "P50 ECP", filas: 54 },
        { id: "t-p50-2", name: "Tabla 2", tag: "P50 Filiales", filas: 54 },
      ],
    },
    {
      id: "s-fili",
      name: "Producción filiales",
      tablas: 8,
      open: true,
      respaldoFilas: 69,
      raw: { destino: "fact_produccion_diaria", filas: 434 },
      tables: [
        { id: "t1", name: "Tabla 1", tag: "REAL", filas: 217 },
        { id: "t2", name: "Tabla 2", tag: "PROGRAMA", filas: 217 },
        { id: "t3", name: "Tabla 3", tag: "PROYECCIÓN", filas: 217 },
        { id: "t4", name: "Tabla 4", tag: "FILIALES mes/semana", filas: 52 },
        { id: "t5", name: "Tabla 5", tag: "Seguimiento semanal", filas: 20 },
        { id: "t6", name: "Tabla 6", tag: "REAL total empresa", filas: 90 },
        { id: "t7", name: "Tabla 7", tag: "PROGRAMA total empresa", filas: 93 },
        { id: "t8", name: "Tabla 8", tag: "Desempeño P50", filas: 16 },
      ],
    },
    {
      id: "s-bit",
      name: "(Bitacora)",
      tablas: 3,
      open: false,
      tables: [
        { id: "t-bit-1", name: "Tabla 1", tag: "Bitácora", filas: 12 },
        { id: "t-bit-2", name: "Tabla 2", tag: "Eventos", filas: 8 },
        { id: "t-bit-3", name: "Tabla 3", tag: "Notas", filas: 5 },
      ],
    },
  ];

  // Tabla mock del visualizador (mismos datos para cualquier selección — es solo shell)
  var MOCK_TABLE = {
    columns: ["EMPRESA", "PRODUCTO", "30/11", "01/12", "02/12", "03/12", "04/12", "05/12", "06/12", "07/12"],
    rows: [
      ["Hocol", "CRUDO", "16.885,6", "17.910,7", "17.590,9", "17.341,3", "17.668,2", "17.635,7", "17.599,4", "17.797,8"],
      ["Hocol", "GAS", "17.589,2", "18.622,3", "16.337", "20.730,1", "18.027,3", "18.070,6", "18.276,6", "18.198,3"],
      ["America", "CRUDO", "3.877,6", "5.112", "7.279", "8.397", "7.392", "7.352", "8.167", "9.155"],
      ["America", "GAS", "855,2", "1.049", "1.210", "1.332", "1.212", "1.190", "1.272", "1.319"],
      ["Permian", "CRUDO", "54.304", "58.804,6", "57.885,9", "59.215,5", "61.494,2", "61.219,3", "60.708,3", "60.457,4"],
      ["Permian", "GAS", "16.580,3", "17.796,7", "17.105,2", "17.672,9", "18.075", "18.377,1", "18.210,9", "18.577,6"],
      ["Permian", "BLANCOS", "19.276,3", "21.158", "20.387,3", "21.139,6", "21.588", "22.013,2", "21.810,1", "22.201,1"],
    ],
  };

  // ---------- Estado en memoria (sin localStorage) ----------
  var state = {
    activeTab: "ingesta",
    selection: null, // { tableId, sheetName, name, tag, filas }
    collapsed: false,
    openSheets: {}, // sheetId -> bool
  };

  MOCK_SHEETS.forEach(function (s) {
    state.openSheets[s.id] = !!s.open;
  });

  // ---------- Utilidades ----------
  // Escape explícito (incluye comillas — seguro también en contexto de atributo)
  function esc(t) {
    return String(t)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function el(id) {
    return document.getElementById(id);
  }

  function tabDef(id) {
    for (var i = 0; i < TABS.length; i++) if (TABS[i].id === id) return TABS[i];
    return TABS[0];
  }

  // ---------- Render · pestaña Ingesta (mock card + árbol) ----------
  function renderIngestaBody() {
    var html =
      '<div class="rb-cp-upcard">' +
      '  <div class="rb-cp-upcard__head">' +
      '    <i class="bi bi-cloud-arrow-up-fill" aria-hidden="true"></i>' +
      '    <div><strong>Cargar Reporte Diario</strong>' +
      '    <small>nombre con fecha YYYYMMDD</small></div>' +
      '    <span class="rb-cp-upcard__new">NEW</span>' +
      "  </div>" +
      '  <div class="rb-cp-upcard__file">' +
      '    <i class="bi bi-filetype-xlsx" aria-hidden="true"></i>' +
      "    <div><strong>20241004_Repor…TEST.xlsm</strong>" +
      '    <small><i class="bi bi-check-circle-fill"></i> Fecha 04/10/2024 · destino CPF</small></div>' +
      '    <button type="button" class="rb-cp-upcard__change" disabled title="Mock — sin conexión en esta fase">Cambiar</button>' +
      "  </div>" +
      '  <button type="button" class="rb-cp-upcard__submit" disabled title="Mock — sin conexión en esta fase">' +
      '    <i class="bi bi-box-arrow-in-down" aria-hidden="true"></i> CARGAR E INGERIR</button>' +
      "</div>" +
      '<div class="rb-cp-treehd"><strong>Hojas del archivo</strong>' +
      '  <span class="rb-cp-badge">' + MOCK_SHEETS.length + " / " + MOCK_SHEETS.length + "</span></div>" +
      '<ul class="rb-cp-tree" id="rb-cp-tree">';

    MOCK_SHEETS.forEach(function (sheet) {
      var open = state.openSheets[sheet.id];
      html +=
        '<li class="rb-cp-tree__sheet' + (open ? " is-open" : "") + '" data-sheet="' + sheet.id + '">' +
        '  <button type="button" class="rb-cp-tree__sheethd" data-action="toggle-sheet" data-sheet="' + sheet.id + '"' +
        '          aria-expanded="' + (open ? "true" : "false") + '">' +
        '    <i class="bi bi-chevron-right rb-cp-chev" aria-hidden="true"></i>' +
        '    <i class="bi bi-check-circle-fill rb-cp-ok" aria-hidden="true"></i>' +
        "    <span>" + esc(sheet.name) + "</span>" +
        '    <span class="rb-cp-badge">' + sheet.tablas + " tablas</span>" +
        "  </button>" +
        '  <div class="rb-cp-tree__kids">';

      if (sheet.respaldoFilas) {
        html +=
          '<div class="rb-cp-tree__meta"><i class="bi bi-archive" aria-hidden="true"></i>' +
          "<span>Respaldo</span><span class=\"rb-cp-badge\">" + sheet.respaldoFilas + " filas</span></div>";
      }
      if (sheet.raw) {
        html +=
          '<div class="rb-cp-tree__meta"><i class="bi bi-database" aria-hidden="true"></i>' +
          "<span>RAW →</span><code>" + esc(sheet.raw.destino) + "</code>" +
          '<span class="rb-cp-badge rb-cp-badge--blue">' + sheet.raw.filas + " filas</span></div>";
      }
      html +=
        '<div class="rb-cp-tree__grouphd"><i class="bi bi-diagram-3" aria-hidden="true"></i>' +
        "<span>Para análisis</span><span class=\"rb-cp-badge\">" + sheet.tables.length + " tablas</span></div>";

      sheet.tables.forEach(function (t) {
        var active = state.selection && state.selection.tableId === t.id;
        html +=
          '<button type="button" class="rb-cp-tree__row' + (active ? " is-active" : "") + '"' +
          '        data-action="pick-table" data-table="' + t.id + '" data-sheet="' + sheet.id + '">' +
          '  <i class="bi bi-table" aria-hidden="true"></i>' +
          "  <span>" + esc(t.name) + "</span>" +
          '  <span class="rb-cp-tree__rowtag">· ' + esc(t.tag) + "</span>" +
          '  <span class="rb-cp-badge">' + t.filas + " filas</span>" +
          "</button>";
      });

      html += "</div></li>";
    });

    html += "</ul>";
    return html;
  }

  // ---------- Render · placeholders Control / Análisis ----------
  function renderEmptyBody(tab) {
    return (
      '<div class="rb-cp-empty">' +
      '  <div class="rb-cp-empty__eyebrow">' + esc(tab.label) + "</div>" +
      '  <h6 class="rb-cp-empty__title"><i class="bi bi-' + tab.icon + '" aria-hidden="true"></i> ' + esc(tab.label) + "</h6>" +
      '  <p class="rb-cp-empty__sub">Contenedor reservado — sin contenido aún</p>' +
      '  <div class="rb-cp-empty__drop">' +
      '    <div><i class="bi bi-plus-square-dotted" aria-hidden="true"></i>' +
      "    <span>" + esc(tab.sub) + "</span></div>" +
      "  </div>" +
      "</div>"
    );
  }

  // ---------- Render · panel de contenido ----------
  function renderPanelBody() {
    var body = el("rb-cp-panel-body");
    if (!body) return;
    if (state.activeTab === "ingesta") {
      body.innerHTML = renderIngestaBody();
    } else {
      body.innerHTML = renderEmptyBody(tabDef(state.activeTab));
    }
  }

  // ---------- Render · visualizador (router por pestaña + selección) ----------
  function viewerEmpty(icon, eyebrow, hint, gold, headIcon, headTitle) {
    return (
      '<div class="rb-cp-vhead">' +
      '  <i class="bi bi-' + headIcon + '" aria-hidden="true"></i>' +
      '  <span class="rb-cp-vhead__title' + (gold ? " is-gold" : "") + '">' + esc(headTitle) + "</span>" +
      "</div>" +
      '<div class="rb-cp-vempty"><div class="rb-cp-vempty__inner">' +
      '  <div class="rb-cp-vempty__chip"><i class="bi bi-' + icon + '" aria-hidden="true"></i></div>' +
      '  <div class="rb-cp-vempty__eyebrow">' + esc(eyebrow) + "</div>" +
      '  <p class="rb-cp-vempty__hint">' + esc(hint) + "</p>" +
      "</div></div>"
    );
  }

  function viewerTable(sel) {
    var title = sel.sheetName + " — " + sel.name + (sel.tag ? " (" + sel.tag + ")" : "");
    var html =
      '<div class="rb-cp-vhead">' +
      '  <i class="bi bi-table" aria-hidden="true"></i>' +
      '  <span class="rb-cp-vhead__title">' + esc(title) + "</span>" +
      '  <span class="rb-cp-vhead__meta">' + MOCK_TABLE.rows.length + " filas × " +
      (MOCK_TABLE.columns.length - 2) + " días (mock)</span>" +
      "</div>" +
      '<div class="rb-cp-vtable"><table><thead><tr>';

    MOCK_TABLE.columns.forEach(function (c) {
      html += "<th>" + esc(c) + "</th>";
    });
    html += "</tr></thead><tbody>";

    MOCK_TABLE.rows.forEach(function (r) {
      html += '<tr><th scope="row">' + esc(r[0]) + '</th><td class="is-dim">' + esc(r[1]) + "</td>";
      for (var i = 2; i < r.length; i++) html += "<td>" + esc(r[i]) + "</td>";
      html += "</tr>";
    });

    html +=
      "</tbody></table></div>" +
      '<div class="rb-cp-vfoot"><span>' + MOCK_TABLE.rows.length + " filas visibles · datos MOCK (shell sin conexión)</span>" +
      '<span><i class="bi bi-arrow-left-right" aria-hidden="true"></i> Desplaza para ver todas las columnas · 1ª columna fija</span></div>';
    return html;
  }

  function renderViewer() {
    var viewer = el("rb-cp-viewer");
    if (!viewer) return;
    if (state.activeTab === "ingesta") {
      viewer.innerHTML = state.selection
        ? viewerTable(state.selection)
        : viewerEmpty("hand-index-thumb", "Visualizador",
            "Selecciona una tabla del árbol para inspeccionarla", false,
            "clipboard2-data", "Visualizador");
    } else if (state.activeTab === "control") {
      viewer.innerHTML = viewerEmpty("sliders2", "Panel de control",
        "Configura parámetros y reglas de negocio", false,
        "clipboard2-data", "Panel de Control");
    } else {
      viewer.innerHTML = viewerEmpty("graph-up-arrow", "Análisis",
        "Vistas y KPIs avanzados de producción", true,
        "clipboard2-data", "Análisis Avanzado de Producción Diaria");
    }
  }

  // ---------- Navegación de pestañas ----------
  function setActiveTab(tabId) {
    var reopening = state.collapsed;
    if (reopening) {
      // Clic en el riel con panel colapsado → reabrir (contrato adaptado al sandbox)
      state.collapsed = false;
      var root0 = el("rb-cp");
      if (root0) root0.classList.remove("is-collapsed");
    }
    // Clic/Enter en la pestaña ya activa sin colapso: no re-renderizar
    // (evita reconstruir el árbol y perder la posición de scroll del panel)
    if (!reopening && state.activeTab === tabId) return;
    state.activeTab = tabId;
    var def = tabDef(tabId);

    document.querySelectorAll("#rb-cp .rb-cp__tab").forEach(function (btn) {
      var active = btn.dataset.tab === tabId;
      btn.classList.toggle("is-active", active);
      btn.setAttribute("aria-selected", active ? "true" : "false");
      btn.tabIndex = active ? 0 : -1;
    });

    var headIcon = el("rb-cp-head-icon");
    var headTitle = el("rb-cp-head-title");
    var panel = el("rb-cp-panel");
    var body = el("rb-cp-panel-body");
    if (headIcon) headIcon.className = "bi bi-" + def.icon + " rb-cp__panel-head-icon";
    if (headTitle) headTitle.textContent = def.label.toUpperCase();
    if (panel) panel.setAttribute("aria-label", "Panel " + def.label);
    if (body) body.setAttribute("aria-labelledby", "cp-tab-" + tabId);

    renderPanelBody();
    renderViewer();
  }

  function onRailKeydown(e) {
    var keys = ["ArrowDown", "ArrowUp", "Home", "End"];
    if (keys.indexOf(e.key) === -1) return;
    e.preventDefault();
    var idx = TABS.findIndex(function (t) { return t.id === state.activeTab; });
    var next = idx;
    if (e.key === "ArrowDown") next = (idx + 1) % TABS.length;
    else if (e.key === "ArrowUp") next = (idx - 1 + TABS.length) % TABS.length;
    else if (e.key === "Home") next = 0;
    else next = TABS.length - 1;
    setActiveTab(TABS[next].id);
    var btn = document.querySelector('#rb-cp .rb-cp__tab[data-tab="' + TABS[next].id + '"]');
    if (btn) btn.focus();
  }

  // ---------- Selección de tabla (solo Ingesta) ----------
  function pickTable(tableId, sheetId) {
    var sheet = null, table = null;
    MOCK_SHEETS.forEach(function (s) {
      if (s.id === sheetId) {
        sheet = s;
        s.tables.forEach(function (t) { if (t.id === tableId) table = t; });
      }
    });
    if (!sheet || !table) return;
    state.selection = {
      tableId: table.id,
      sheetName: sheet.name,
      name: table.name,
      tag: table.tag,
      filas: table.filas,
    };
    // Marcar fila activa sin re-render completo del árbol
    document.querySelectorAll("#rb-cp-tree .rb-cp-tree__row").forEach(function (row) {
      row.classList.toggle("is-active", row.dataset.table === tableId);
    });
    renderViewer();
  }

  function toggleSheet(sheetId) {
    state.openSheets[sheetId] = !state.openSheets[sheetId];
    var li = document.querySelector('#rb-cp-tree .rb-cp-tree__sheet[data-sheet="' + sheetId + '"]');
    if (!li) return;
    li.classList.toggle("is-open", state.openSheets[sheetId]);
    var hd = li.querySelector(".rb-cp-tree__sheethd");
    if (hd) hd.setAttribute("aria-expanded", state.openSheets[sheetId] ? "true" : "false");
  }

  // ---------- Colapso del panel ----------
  function toggleCollapse() {
    state.collapsed = !state.collapsed;
    var root = el("rb-cp");
    if (root) root.classList.toggle("is-collapsed", state.collapsed);
    if (state.collapsed) {
      // El botón "−" desaparece con el panel: mover el foco a la pestaña activa
      // del riel para que el usuario de teclado conserve el punto de retorno.
      var activeBtn = document.querySelector("#rb-cp .rb-cp__tab.is-active");
      if (activeBtn) activeBtn.focus();
    }
  }

  // ---------- Init ----------
  function init() {
    var root = el("rb-cp");
    if (!root) return; // defensivo: este JS solo actúa en /layout/colapsable

    // Riel: clic + teclado
    root.querySelectorAll(".rb-cp__tab").forEach(function (btn) {
      btn.addEventListener("click", function () { setActiveTab(btn.dataset.tab); });
      btn.addEventListener("keydown", onRailKeydown);
    });

    // Botón colapsar
    var collapseBtn = el("rb-cp-collapse");
    if (collapseBtn) collapseBtn.addEventListener("click", toggleCollapse);

    // Delegación de eventos en el cuerpo del panel (árbol mock)
    var body = el("rb-cp-panel-body");
    if (body) {
      body.addEventListener("click", function (e) {
        var target = e.target.closest("[data-action]");
        if (!target) return;
        if (target.dataset.action === "toggle-sheet") toggleSheet(target.dataset.sheet);
        else if (target.dataset.action === "pick-table") pickTable(target.dataset.table, target.dataset.sheet);
      });
    }

    renderPanelBody();
    renderViewer();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
```

---

## 6 · Orden de ejecución

0. `cd /d C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA` (P0 — todos los comandos siguientes se ejecutan desde esta raíz).
1. Verificar prerequisitos P1-P6 (§3). Si P1-P5 falla, DETENERSE.
2. Crear `Colapsable/static/js/colapsable.js` con el contenido exacto de §5.3.
3. Hacer APPEND del bloque CSS de §5.2 al final de `Colapsable/static/css/colapsable.css` (sin tocar lo existente).
4. Reemplazar `Colapsable/templates/colapsable_layout.html` por el contenido exacto de §5.1.
5. Correr las validaciones V1-V4 (§8) en orden. Si alguna falla, DETENERSE y reportar cuál.
6. Reportar: ✅/❌ por paso + archivos tocados + "¿Hago commit?". NO commitear sin autorización.

> Nota post-ejecución: la fila correspondiente en la **bitácora §10 del `CLAUDE.md` raíz** (fecha, descripción, archivos, commit) la registra el **PLANNER después de la validación humana V5** — NO es tarea del executor (tocar `CLAUDE.md` violaría §4.3).

---

## 7 · Reglas no negociables

- CERO cambios fuera de los 3 archivos de §4.1/§4.2. En particular: NO tocar `chat.js`, `panels.js`, `main.html`, `base.html`, `app.py` ni ningún `.py` (lista completa en §4.3).
- CERO dependencias nuevas: sin npm, sin CDN adicionales, sin Google Fonts. Solo lo que `base.html` ya carga.
- CERO llamadas de red en `colapsable.js`: sin `fetch`, sin Socket.IO, sin `localStorage`. Todo el estado vive en memoria (decisión cerrada #4 y #7 de §1).
- Los botones "Cambiar" y "CARGAR E INGERIR" del mock van `disabled` con `title="Mock — sin conexión en esta fase"` — NO cablearles ningún comportamiento.
- Iconos EXCLUSIVAMENTE de Bootstrap Icons (`bi bi-*`) — no Font Awesome (aunque esté cargado) para mantener consistencia con la UI de ingesta real.
- Mantener los atributos ARIA tal como están en §5 (tablist vertical, roving tabindex, aria-expanded en el árbol): son parte del contrato del diseño (multitap.md §11).
- Si el archivo CSS o el template actual difieren de lo descrito en §1 (por ejemplo, ya no está vacío el panel), DETENERSE y reportar antes de sobreescribir.

---

## 8 · Validaciones

| # | Validación | Comando / procedimiento | Resultado esperado |
|---|---|---|---|
| V1 | Sintaxis JS válida | `node --check Colapsable/static/js/colapsable.js` (si no hay Node: abrir la página y verificar 0 errores en consola F12) | Sin salida / exit 0 |
| V2 | Solo 3 archivos tocados dentro de `Colapsable/` | `git status --porcelain -uall Colapsable/` (el flag `-uall` es necesario: sin él git colapsa la carpeta untracked `static/js/` y no muestra el archivo). **Ignorar** untracked pre-existentes FUERA de `Colapsable/` (ej. `INGESTA/Rep_Prod/backend/clean_bd.py` y este plan — ya estaban antes) | Exactamente 3 líneas: `M Colapsable/static/css/colapsable.css`, `M Colapsable/templates/colapsable_layout.html`, `?? Colapsable/static/js/colapsable.js` |
| V3 | La app arranca y la ruta responde | Arrancar con `C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\iniciar_backends.bat` (lanzador **canónico**: usa el intérprete base + `PYTHONPATH` para evitar el bloqueo WDAC "os error 4551" del python del venv, documentado en el `CLAUDE.md` raíz §10 — `run.bat` puede fallar por eso en esta máquina). Para este plan solo se necesita el Flask `:8020`; la ventana del backend INGESTA `:8000` puede ignorarse. Luego, en **cmd interactivo**: `curl.exe -s -o NUL -w "%{http_code}" http://localhost:8020/layout/colapsable` (un solo `%`; usar `%%` SOLO dentro de un `.bat`; en PowerShell usar también `curl.exe`; en Git Bash usar `-o /dev/null`) | `200` (con sesión) o `302` (redirect a login). ⚠️ El `302` prueba SOLO que la app arranca y la ruta existe — `@login_required` redirige ANTES de renderizar, así que NO valida el template. El render lo valida V3b (o, en su defecto, queda 100% en V5) |
| V3b (opcional) | El template renderiza sin error Jinja | Con el bypass dev activo en `.env` (`DEVELOPMENT_MODE=true` + `LOGIN_BYPASS_EMAILS`): `curl.exe -s -c cookies.txt -H "Content-Type: application/json" -d "{\"username\":\"javier.guerrero@ecopetrol.com.co\",\"password\":\"x\"}" http://localhost:8020/auth/login` y luego `curl.exe -s -b cookies.txt -o NUL -w "%{http_code}" http://localhost:8020/layout/colapsable`. Si el bypass no está activo, saltar V3b y reportarlo (el render queda cubierto por V5) | `200` en la segunda llamada |
| V4 | El resto de la app intacta | Abrir `http://localhost:8020/` (vista principal) — chat + analytics operan igual que antes | Sin cambios; **0 errores de consola NUEVOS respecto a la línea base** (se acepta únicamente el `404` pre-existente de `/favicon.ico`, que es app-wide y ajeno a este plan) |
| V5 ⏳ | Validación humana en navegador | Login → `http://localhost:8020/layout/colapsable` | Riel verde con 3 pestañas (etiquetas rotadas, activa "conectada" con barra dorada); pestaña Ingesta muestra card mock + árbol; clic en "Tabla 1 (REAL)" → visor muestra la tabla mock con título "Producción filiales — Tabla 1 (REAL)" y 1ª columna fija; la fila inferior del visor (`.rb-cp-vfoot`) y la scrollbar horizontal se ven COMPLETAS, sin quedar bajo el footer fijo de la app; cambiar a Control y volver → la selección persiste; Control/Análisis muestran placeholder + visor contextual (Análisis con título dorado); botón `−` colapsa el panel (riel visible, visor se ensancha) y clic en una pestaña lo reabre; teclado ↑/↓/Home/End navega el riel con foco visible dorado; **0 errores de consola NUEVOS** respecto a la línea base (se acepta únicamente el `404` pre-existente de `/favicon.ico`) |

**V5 queda SIEMPRE como "⏳ PENDIENTE de validación humana"** — el executor no debe marcarla como completada bajo ninguna circunstancia. Solo el usuario cierra una feature visual.

---

## 9 · Fuera de alcance (fases posteriores, NO hacer ahora)

- Conectar la pestaña Ingesta a la API real (`/ingesta/disponibles`, `POST /ingesta/archivo`, Socket.IO `ingesta_progress`, visor `/tablas/datos`). **Regla para esa fase:** los ids usados en `data-sheet`/`data-table` deben ser slugs generados (`[a-z0-9-]`), NUNCA el nombre crudo de la hoja Excel (puede traer comillas/caracteres que rompen atributos y selectores).
- Migrar/retirar la ingesta actual embebida en `chat.js` / `chat-panel`.
- Enlazar `/layout/colapsable` desde la navegación de la app (hoy se accede por URL directa — correcto para un prototipo).
- Contenido real de las pestañas Control y Análisis.
- Buscador, densidad Cómoda/Compacta y export del visor de tabla (existen en la UI real; el mock no los incluye).
- Persistencia de pestaña/selección en `localStorage`.
- Tests automatizados (el proyecto no tiene suite formal de frontend).
- Favicon de la app: el `404` de `/favicon.ico` es pre-existente y app-wide (base.html no declara `<link rel=icon>` y no existe `static/favicon.*`) — deuda separada, NO arreglarla aquí (base.html está en la lista PROHIBIDO §4.3).
