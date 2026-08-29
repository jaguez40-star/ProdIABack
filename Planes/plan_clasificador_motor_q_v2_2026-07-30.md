# Plan · Motor Q v2 — Fase 1: Clasificador de grupo (Etapa A de motor_Q.md)

> **v2 del plan (2026-07-30):** incorpora las precisiones de `audit_motor_clas.md`
> (libreta de clasificación con veredicto, 3 controles, ciclo de crecimiento, patrones
> a YAML, ajustes A1-A6) con 4 precisiones de implementación (P1-P4, ver §Aprendizaje).
> **v3 del plan (2026-07-30) — AUDITADO (flujo §0.2 de CLAUDE.md, verificado contra código):**
> 6 incoherencias corregidas (H1-H6) + 4 menores (H7-H10) + 1 oportunidad (O1). Los fixes
> están integrados en las secciones; el registro completo al final (§Auditoría v3).

## Contexto

Hoy el chat de Consulta **no sabe la naturaleza de la pregunta**: solo distingue "pregunta de catálogo" (regex en `meta.py`) vs "todo lo demás", y todo lo demás recibe siempre la misma respuesta (cifra REAL vs PPTO del mes). "¿Por qué está mal Castilla?" y "¿cuánto produjo Castilla?" devuelven respuestas idénticas.

`motor_Q.md` define la pieza que falta: un **clasificador de grupo** (Jerarquizar / Cuantificar / Analizar) delante de todo. Decisiones ya cerradas con el usuario:

- **Edificio v2 separado e independiente** (`consulta_v2/`): ningún componente de código compartido con la v1. La v1 queda **congelada** (solo se toca si entrega una cifra incorrecta).
- **Selector visible en el chat** ("Motor v1 | v2"): switch en caliente, por pregunta, sin reiniciar nada.
- **Alcance de ESTA fase = solo el clasificador** (Etapa A). No toca lectura de datos — la decisión "Anillo 2" (si v2 comparte las calculadoras del tablero) queda **diferida** a la fase de los grupos.
- El prompt del LLM vive en el `.py` de la feature, **no** en `master_prompts.yaml` (ese yaml lo lee solo el chatbot legacy de Flask — decisión H7 del 30-jul).

Gate de salida (motor_Q.md Fase 1): golden set de ≥30 preguntas (10 por grupo) clasificadas ≥90% correcto. Paridad gemma4 se verifica en 139 después (patrón ya usado en la extracción v1).

## Qué se construye

### 1. Backend — feature nueva `INGESTA/Rep_Prod/backend/app/features/consulta_v2/`

**`patrones.py`** — Capa 1: regex/keywords, Python puro, sin LLM.
- Los patrones viven en **`consulta_v2/config/patrones_grupo.yaml`** (audit §4): secciones `precedencia_maxima` (huella), `grupos` (los 3), `precedencia_colision: [analizar, cuantificar, jerarquizar]`. `patrones.py` es solo el **cargador**: lee el YAML al arrancar, compila los regex una vez, expone `clasificar_capa1()`. Cero lógica en el YAML, cero datos en el `.py`. (Ruta feature-local, NO el `config/` de Flask — ese es del chatbot legacy.)
- Patrones sobre texto **normalizado** con `norm()`-equivalente propio de v2 — v2 no importa `consulta.normaliza`; se copia la función con marca de fork (A6: `# FORK de consulta/normaliza.py @ 2026-07-30 — razón: aislamiento v2`).
- Incluir en `jerarquizar` los patrones de **huella/disponibilidad** (`QUE INFORMACION`, `DESDE CUANDO`, `CUANTOS DIAS CON REPORTE`, `COBERTURA`…) con **precedencia máxima** (se evalúan antes que todo): es la trampa conocida — "¿cuántos días con reporte hay de X?" trae "cuántos" pero no pide cifra.
- `clasificar_capa1(texto) -> str | None`:
  - 1 solo grupo atrapa → ese grupo.
  - 2+ grupos atrapan → precedencia `analizar > cuantificar > jerarquizar` (motor_Q.md §1.1).
  - 0 grupos → `None` (baja a Capa 2).
- Devuelve también qué patrones atraparon (para trazabilidad en la respuesta y en el golden runner).

**`clasificador_llm.py`** — Capa 2: LLM clasificador cerrado (fallback).
- Prompt inline **como constante separada al tope del módulo** (A5 — corte limpio para migración futura): 3 grupos + `desconocido`, salida `{"grupo": "...", "entidad": "..."|null}`.
- Llamada a Ollama copiando el patrón de `extraccion._llm` (urllib, `temperature: 0`, **`format: "json"`** — gotcha conocido: gemma4@139 devuelve vacío en texto plano). **H5: `options.num_predict: 64` y timeout corto (30s)** — la clasificación son ~10 tokens; sin el tope, el arranque en frío de gemma en 139 (load 342s, hallazgo 29-jul) colgaría cada primera pregunta. Lee `CONSULTA_OLLAMA_URL` / `CONSULTA_LLM_MODEL` de `app.core.config.get_settings()` (config = infraestructura, no componente del edificio v1).
- Parseo defensivo: JSON malformado, grupo fuera del enum, timeout o conexión caída → `{"grupo": "desconocido", "entidad": None, "diag": "<motivo>"}`. Jamás adivinar, jamás reintentar un JSON malo. **H5: el `diag` se persiste en `clasificacion_log.llm_diag`** — sin él, un timeout por frío parecería error del clasificador al revisar el lote.

**`maquina_q.py`** — orquestador de la Fase 1.
- `clasificar(texto, log=True) -> dict` — **H3: el parámetro `log` existe para que el golden runner y los pytest NO contaminen la libreta** (`log=False`); solo el tráfico real del API registra. Contrato de salida de motor_Q.md §1.3 **+ `log_id`** (sin él los botones ✓/✗ no saben qué fila votar; `null` si `log=False`):
  ```json
  {"log_id": 123, "texto_original": "...", "grupo": "jerarquizar|cuantificar|analizar|desconocido",
   "capa_resolutora": "regex|llm", "entidad_cruda": "...|null",
   "patrones": ["..."], "timestamp": "ISO"}
  ```
- Al clasificar, **inserta el registro en `clasificacion_log`** con `veredicto='pendiente'` (audit §1).
- `entidad_cruda`: en Capa 1 (regex) no hay LLM, así que se extrae con un backstop de n-gramas propio de v2 contra el catálogo (fork del patrón `buscar_en_texto` — **copiado**, no importado, con marca A6; lee las mismas tablas `dim_*`/`map_campo_activo` vía `get_engine()`, que es Anillo 3/infraestructura). **A1: best-effort con presupuesto acotado** — si el fork se complica, `entidad_cruda = null` no bloquea el gate (la resolución formal es de la Etapa B).
- Respuesta al usuario en esta fase (los grupos aún no responden): mensaje transparente rotulado como motor en construcción, p. ej.:
  - grupo detectado → "**[Motor v2]** Clasifiqué tu pregunta como **Cuantificar** (vía regex). Entidad detectada: «Castilla». Los módulos de respuesta del v2 están en construcción — cambia a Motor v1 para obtener la cifra."
  - `desconocido` → menú de capacidades **declarativo, sin contrapregunta** (A2): "Puedo responder sobre estructura organizacional, cifras de producción o análisis de desempeño." — los tres como chips clickeables si la UI lo permite.

**`api.py`** — router `/consulta2`, registrado en `backend/app/main.py` (mismo patrón que `consulta`):
- `POST /consulta2/preguntar` (body igual al de v1: `{texto, conversation_id, usuario}`) → contrato de clasificación (con `log_id`) + `mensaje` renderizable. Sin slot-filling en v2 todavía.
- `POST /consulta2/veredicto` `{log_id, veredicto, grupo_correcto|null}` → actualiza la fila (Control 1).
- `POST /consulta2/senal` `{texto, conversation_id, usuario, tipo:"cambio_v1"}` → **P2**: la señal "repitió la pregunta en v1" la empuja el FRONTEND (fire-and-forget), porque v1 está congelada y no puede observarse desde su propio código. `senales.py` compara similitud contra la última clasificación v2 de esa conversación y marca `sospecha` si procede.
- `GET /consulta2/log?limit=100&filtro=todas|pendientes|sospecha|corregidas` → lista de la libreta para la tabla de la pestaña «Test Clas» (más recientes primero). Al servir, invoca `senales.escanear()` (acotado, H7) para que las sospechas lleguen ya marcadas. **O1:** la respuesta incluye `resumen` (conteos por veredicto + **% resuelto por Capa 1**) — la cabecera de la tabla pinta gratis el KPI del ciclo de crecimiento.

### 1b. Aprendizaje — libreta, controles y ciclo (audit_motor_clas.md, con precisiones P1-P4)

**`log.py`** — escritura/actualización de **`core.clasificacion_log`**.
- **P1: la tabla vive en Postgres** (`daily_report_prod`), migración **`010_clasificacion_log.sql`** idempotente (patrón 008/009: encabezado con el porqué, `BEGIN/COMMIT`, `IF NOT EXISTS`). Ni SQLite ni JSONL: los controles 2 y 3 la consultan con filtros y ventanas de tiempo, y `get_engine()` ya existe.
- **H4: el DDL del audit era dialecto SQLite — la migración va en PG:**
  ```sql
  CREATE TABLE IF NOT EXISTS core.clasificacion_log (
      id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      ts TIMESTAMPTZ NOT NULL DEFAULT now(),
      usuario TEXT, conversation_id TEXT,
      texto_pregunta TEXT NOT NULL,
      grupo_asignado TEXT NOT NULL,          -- jerarquizar|cuantificar|analizar|desconocido
      capa_resolutora TEXT NOT NULL,         -- regex|llm
      patrones_atrapados JSONB,              -- solo si capa=regex
      entidad_cruda TEXT,
      llm_diag TEXT,                         -- H5: timeout|aborto|json_invalido|null
      veredicto TEXT NOT NULL DEFAULT 'pendiente',
      grupo_correcto TEXT, fuente_veredicto TEXT,
      ts_veredicto TIMESTAMPTZ, nota_revision TEXT
  );
  CREATE INDEX IF NOT EXISTS idx_clas_log_veredicto ON core.clasificacion_log(veredicto, ts);
  ```
- La 010 NO toca caches del resolver → no exige el reinicio especial de la 008/009 (aunque `desplegar_version.bat` reinicia igual).

**`senales.py`** — Control 2 (señal indirecta → `sospecha`; jamás corrige sola).
- **H2: el matching es por `usuario` + ventana, NO por `conversation_id`** — el flujo real cruza chats con IDs distintos (pruebas en Test Clas, repite en Consulta): por conversación la señal jamás dispararía.
- Reformulación: mismo usuario, ≤120s, similitud alta. **P3: similitud por ratio de tokens compartidos (Jaccard sobre texto normalizado), NO pg_trgm** — la migración 007 sigue sin aplicar y una señal débil no justifica la dependencia. Umbral 0.70 en `consulta_v2/config/clasificacion_feedback.yaml`.
- Cambio a v1: vía `POST /consulta2/senal` empujada por el frontend (P2), con `usuario` en el payload.
- Abandono tras `desconocido`: sin filas posteriores del usuario en ≥600s.
- **P4: sin scheduler.** `escanear()` corre al servir `GET /log` y al arrancar `revisar_lote.py`. **H7: escaneo acotado** a filas `pendiente` de los últimos 7 días (no table-scan de toda la libreta).

**`golden/revisar_lote.py`** — Control 3 (el juez final). CLI: corre `escanear()`, muestra la cola ordenada (sospecha → pendiente-LLM → resto), teclas 1/2/3/4 + Enter, escribe `confirmado_revision`/`corregido_revision` + `grupo_correcto` + `nota_revision`. Sin UI web (decisión del audit).

**Ciclo de crecimiento** (audit §3, es proceso, no código de esta fase): solo casos `confirmado_*`/`corregido_*` alimentan patrones y golden; toda corrección entra al golden (regresión permanente); KPI = % resuelto por Capa 1, reportado por el runner; cadencia deliberada tras cada lote, nunca automática, siempre con el golden ampliado en verde antes de dar por bueno un patrón nuevo.

**`golden/clasificacion_golden.yaml` + `golden/run_golden.py`** — el gate.
- ≥30 preguntas: 10 jerarquizar, 10 cuantificar, 10 analizar + un bloque extra de **casos trampa** con etiqueta esperada explícita:
  - "¿cuánto nos falta para la meta?" → analizar (precedencia)
  - "¿cuántos días con reporte hay de Rubiales?" → jerarquizar (huella)
  - "¿cuál es la producción de Castilla?" → cuantificar
  - "¿qué es la producción de Castilla?" → cuantificar (no meta)
  - "¿cuántos pozos tiene Apiay?" → cuantificar (contar ≠ listar)
  - "¿qué campos pesan en el gap?" → analizar
  - **A3 · casos sin verbo clasificable:** "Castilla" · "y Cajúa?" · "dame Rubiales" → `desconocido` (blindaje contra patrones agresivos futuros)
- Runner con el patrón de `consulta/golden/run_golden.py`: reporta % por capa (cuántas resolvió la regex sin LLM) y % de acierto total. Meta ≥90%.
- **A4 · umbral blando de Capa 1:** si la regex resuelve <50% del golden, engordar patrones antes de cerrar la fase (señal registrada, no bloqueante).

**Tests** — `backend/tests/test_consulta_v2_clasificador.py`: Capa 1 pura (sin BD, sin LLM): precedencia, huella gana a "cuántos", colisiones, texto sin señales → None. Parseo defensivo de Capa 2 con respuestas simuladas (JSON bueno / malformado / grupo inválido).

### 2. Proxy Flask — `routes/api.py`

`POST /api/consulta2/preguntar` → `{INGESTA_API_URL}/consulta2/preguntar`, timeout 90. Copia exacta del proxy de v1 (líneas 477-483).

### 3. Frontend — selector + despacho (`static/js/multitab_shell.js`)

- **Selector "Motor: v1 | v2"** en la cabecera del panel de chat de Consulta (junto al título). Variable `__cnMotor` (default `"v1"`, persistida en `localStorage` para sobrevivir remount). Estilo mínimo en `colapsable.css` (par de pills, reusa tokens `--rb-*`).
- **H1 · `__cnRenderV2` es una función PURA que DEVUELVE el HTML de la burbuja** (badge "Motor v2", grupo con color azul/verde/naranja como el diagrama, capa resolutora, entidad, mensaje, botones ✓/✗). NO appendea: `__cnBubble`/`__cnAppendRaw` están clavados a `#cn-messages` + `__cnHistory` (L3113/3127) — cada chat inserta el HTML con su propio mecanismo (Consulta con `__cnBubble`, Test Clas con `__tcBubble` sobre su `#tc-messages` + `__tcHistory` propios). Al votar ✓/✗, la franja se reemplaza por el veredicto Y se reescribe la entrada del historial correspondiente (patrón `__cnSaludoRefresh`) para que no reviva al cambiar de pestaña.
- `__cnPreguntar`: si `__cnMotor === "v2"` → `fetch("/api/consulta2/preguntar", …)` → `__cnBubble("assistant", __cnRenderV2(d))`.
- **Control 1 en la burbuja v2:** botones ✓/✗ discretos junto al badge del grupo, **sin pregunta** (microcopy declarativo, patrón del proyecto). ✓ → `POST /api/consulta2/veredicto {log_id, veredicto:"confirmado_usuario"}`. ✗ → despliega los otros dos grupos + "ninguno" como chips → `corregido_usuario` + `grupo_correcto`. Opcional, un tap, la conversación sigue igual si no marca nada.
- **Señal P2 (cambio a v1):** cuando `__cnMotor === "v1"` y existe una clasificación v2 de hace <2 min en esta conversación, `__cnPreguntar` dispara fire-and-forget `POST /api/consulta2/senal` con el texto — v1 no se entera; la señal viaja por fuera de su edificio.

### 3b. Pestaña «Test Clas» — laboratorio del clasificador (ADICIÓN, decisión del usuario 2026-07-30)

Quinta pestaña del riel del MultiTab Shell (tras Consulta), mismo patrón de montaje que las 4 existentes. **No reemplaza nada**: el selector v1|v2 de Consulta se mantiene tal cual; esta pestaña es el banco de pruebas dedicado del motor v2.

- **Panel izquierdo — chat de prueba.** Input + burbujas con funciones PROPIAS (`__tc*`: `__tcBubble`, `__tcHistory`, contenedor `#tc-messages` — no toca `__cnPreguntar` ni el chat de Consulta). Cada pregunta va a `POST /api/consulta2/preguntar` y la burbuja inserta el HTML de `__cnRenderV2(d)` (función pura, H1: el render se comparte, el mecanismo de inserción no). La pestaña se agrega al array `TABS` (L10-15) + una rama en `renderPanelBody`/`renderViewer` — el `else → renderEmptyBody` y la navegación por teclado (L418-425) la absorben sin cambios.
- **Panel derecho — la libreta tabulada.** Tabla desde `GET /api/consulta2/log`: columnas **Pregunta · Decisión del motor (grupo+capa) · Veredicto · Fecha**. Al preguntar desde el chat, la fila nueva aparece arriba sin recargar (el POST ya devuelve `log_id` + clasificación). Chips de filtro: todas / pendientes / sospecha / corregidas.
- **Columna Veredicto:**
  - Con veredicto → texto plano con su fuente: `✓ usuario` · `✗→analizar (usuario)` · `✓ revisión` · `✗→cuantificar (revisión)`.
  - `pendiente` y `pendiente (sospecha)` → **franja de calificación inline** estilo barra de feedback (label discreto a la izquierda + botones a la derecha, como la barra "How is Claude doing?"): `[✓ Correcta] [Jerarquizar] [Cuantificar] [Analizar] [Ninguno]` (se ocultan el grupo ya asignado). Clic → `POST /api/consulta2/veredicto` con `confirmado_revision`/`corregido_revision`, `fuente_veredicto='revision'`; la celda pasa a mostrar el veredicto.
  - **`sospecha` NO es un veredicto** — es bandera de prioridad: se pinta como `pendiente (sospecha)` y esas filas suben al tope de la lista.
- El CLI `revisar_lote.py` se mantiene (plan tal cual): la tabla es la vía cómoda, el CLI la vía sin navegador.
- Con v2 activo **no** se dispara el dashboard del panel derecho (no hay intent resuelto en esta fase); el panel conserva lo último que mostraba.
- v1 intacta: con el selector en v1, cero cambios de comportamiento (misma URL, mismo `__cnRender`).
- `templates/main.html`: bump del cache-buster `?v=`.

## Archivos

| Archivo | Acción |
|---|---|
| `INGESTA/Rep_Prod/backend/app/features/consulta_v2/{__init__,patrones,clasificador_llm,maquina_q,api,log,senales}.py` | NUEVOS |
| `INGESTA/Rep_Prod/backend/app/features/consulta_v2/config/{patrones_grupo.yaml,clasificacion_feedback.yaml}` | NUEVOS |
| `INGESTA/Rep_Prod/backend/app/features/consulta_v2/golden/{clasificacion_golden.yaml,run_golden.py,revisar_lote.py}` | NUEVOS |
| `INGESTA/Rep_Prod/db/migrations/010_clasificacion_log.sql` | NUEVO (idempotente, patrón 008/009) |
| `INGESTA/Rep_Prod/backend/tests/test_consulta_v2_clasificador.py` | NUEVO (+ tests de log y señales) |
| `INGESTA/Rep_Prod/backend/app/main.py` | +1 router |
| `routes/api.py` | +4 proxies (`preguntar`, `veredicto`, `senal`, `log`) |
| `static/js/multitab_shell.js` | selector + `__cnRenderV2` (con ✓/✗) + despacho + señal P2 + **pestaña «Test Clas»** (chat `__tc*` + tabla de la libreta con calificación inline) |
| `static/css/colapsable.css` | estilos del selector, botones de veredicto, tabla y franja de calificación de Test Clas |
| `templates/main.html` | cache-buster |

**No se toca:** nada de `features/consulta/` (v1 congelada), nada de `features/analisis/` (Anillo 2 diferido), `master_prompts.yaml`, el `config/` de Flask.

## Verificación

1. `py_compile` de los módulos nuevos + `node --check static/js/multitab_shell.js`.
2. `pytest backend/tests/test_consulta_v2_clasificador.py` — Capa 1 y parseo defensivo verdes (sin BD ni Ollama). + Test del log (clasificar → fila `pendiente`; veredicto → actualización) y del Control 2 con casos simulados (reformulación dentro/fuera de ventana, señal cambio-v1, abandono tras `desconocido`).
3. Aplicar migración 010: `uv run python apply_migration.py ../db/migrations/010_clasificacion_log.sql`.
4. Golden: `uv run python app/features/consulta_v2/golden/run_golden.py` con qwen2.5:3b local → ≥90% (correr en lote con backends abajo, por la RAM — lección del 8-jul). Reporta % resuelto por regex vs LLM (A4: si regex <50%, engordar patrones antes de cerrar).
5. Curl al endpoint: `POST /consulta2/preguntar` con los 3 ejemplos del diagrama ("¿A qué activo pertenece Cajúa?" → jerarquizar · "¿Cuánto crudo produjo?" → cuantificar · "¿Por qué está mal?" → analizar). Verificar que cada uno dejó su fila en `clasificacion_log`.
6. `revisar_lote.py` sobre 5 casos sembrados a mano: etiquetas bien escritas, cola priorizada (sospecha primero).
7. Navegador (usuario): selector visible, pregunta en v2 → burbuja con grupo+capa+entidad+botones ✓/✗; tap en ✗ → elegir grupo → fila `corregido_usuario` en BD; volver a v1 → comportamiento idéntico al actual (regresión cero).
8. Navegador — pestaña «Test Clas»: preguntar en el chat → burbuja clasificada Y fila nueva arriba en la tabla; calificar una fila `pendiente` con la franja inline → la celda muestra el veredicto y la BD queda `confirmado_revision`/`corregido_revision`; filtros funcionan; las `sospecha` aparecen al tope.
9. Paridad gemma4: pendiente en 139 (post-deploy, como se hizo con la extracción v1).

## Auditoría v3 — registro de hallazgos (flujo §0.2, verificados contra código)

| # | Hallazgo | Fix (integrado arriba) |
|---|---|---|
| H1 🔴 | `__cnBubble`/`__cnAppendRaw` clavados a `#cn-messages`+`__cnHistory` → `__cnRenderV2` no era reusable entre chats | Render = función pura que devuelve HTML; cada chat inserta con su mecanismo (`__cn*` / `__tc*`) |
| H2 🔴 | Señal P2 casaba por `conversation_id`, pero Test Clas y Consulta tienen IDs distintos → jamás dispararía | Matching por `usuario` + ventana 120s |
| H3 🔴 | El golden runner metería 30+ filas basura a la libreta por corrida | `clasificar(texto, log=False)` para runner/tests |
| H4 🟡 | DDL del audit en dialecto SQLite | DDL PG (IDENTITY, TIMESTAMPTZ, JSONB) patrón 008/009, incluido arriba |
| H5 🟡 | Frío de gemma@139 (load 342s) → timeout silencioso parecería error del clasificador al revisar | `num_predict:64` + timeout 30s + columna `llm_diag` persistida |
| H6 🟡 | Router debe ir antes del mount StaticFiles (`main.py` L41) | Registrado junto a los otros 7 (L25-31) |
| H7 🟢 | `escanear()` por request = table-scan creciente | Acotado a `pendiente` últimos 7 días |
| H8 🟢 | YAML de patrones se carga al arranque | Documentado: patrón nuevo ⇒ reiniciar backends (como `_INDEX`; `desplegar_version.bat` ya lo hace) |
| H9 🟢 | Texto de pregunta en tabla = input de usuario | `esc()` siempre (patrón existente) |
| H10 🟢 | Proxies existentes son POST; `GET /log` reenvía `request.args` | Explícito en el proxy nuevo |
| O1 ✨ | — | `GET /log` devuelve `resumen` (conteos + % Capa 1) → KPI del clasificador en la cabecera de la tabla |

Verificados sin problema: numeración 010 libre · `TABS` array plano + fallback `renderEmptyBody` (5ª pestaña no rompe nada, L410-425) · `INGESTA_API_URL` existe · `apply_migration.py` existe · la 010 no toca caches del resolver.

## Fuera de alcance (fases siguientes)

- Los 3 grupos respondiendo de verdad (Jerarquizar J1-J5, motor Cuantificar N1-N4, Analizar/Quest).
- Decisión Anillo 2 (calculadoras compartidas vs propias) — se retoma al construir el primer grupo.
- Etapa B formal (colisiones/trgm), persistencia de sesión v2, panel derecho dirigido por intent.
