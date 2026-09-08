# Plan — P50 por MES: cumplimiento con panel de 5 tarjetas

| | |
|---|---|
| **ID tarea** | `P50-CUMPLIMIENTO-MES` |
| **Fecha** | 2026-09-08 |
| **Versión** | **v2** — verificada contra el código con el flujo profesional (`CLAUDE.md` §10). La v1 tenía 5 incoherencias que habrían producido bugs; están documentadas en §0.0 y corregidas aquí. |
| **Repos** | `ProdIABack` (backend) y `ProdIAWebFront` (frontend) |
| **Alcance** | Que «¿Cuál es el cumplimiento del P50 para el mes de Agosto?» y sus 10 variantes respondan **la cifra del mes pedido** y pinten **el panel de 5 tarjetas** que hoy solo existe en el panorama. |
| **NO se toca** | **El clasificador de grupos (`patrones_grupo.yaml`) — CERO cambios** (ver V-01). Nada de Cuantificar ni Jerarquizar. La rama VP (`p50_vp`). El endpoint `president()`. El proxy Flask. |

### Decisiones cerradas del usuario (el executor NO las revisa, las implementa)

1. Las 10 variantes de la pregunta deben tener respuesta.
2. Todas pertenecen a la categoría **«Cumplimiento vs metas»** del catálogo de plantillas. Al catálogo entran **2** fraseos (no las 10: son formas de escribir la misma pregunta y su sitio es el golden).
3. La respuesta debe ser **la del mes pedido**, no la serie anual ni el mes vigente.
4. El panel a devolver es el de **5 tarjetas** (Crudo · Gas · Blancos · Filiales · Total del mes), el mismo del panorama.
5. Las 3 «trampas» que el usuario identificó son **casos negativos** del golden y conservan el comportamiento que ya tienen.

---

## §0.0 Qué cambió de la v1 a la v2 (para quien compare)

La v1 se auditó contra el código antes de escribirse, pero la **verificación** (segundo paso del flujo) encontró 5 incoherencias reales:

| # | Incoherencia de la v1 | Consecuencia si se hubiera ejecutado | Corrección en v2 |
|---|---|---|---|
| 1 | Añadía `CUMPLIMIENTO\w*` y `COMPROMISO\w*` como **anclas** del clasificador | **No lograba su objetivo** (sin «P50» el sub-router devuelve `causal`, nunca el panel) **y sí robaba preguntas**: «cumplimiento del presupuesto de Castilla» pasaba de Cuantificar a Analizar, y al ser ancla saltaba el filtro de dominio («cumplimiento de mi meta de ahorro» entraba al sistema). | **§3.1 eliminada.** Cero cambios al YAML. Las 10 variantes y las 2 plantillas llevan «P50» literal. |
| 2 | La bifurcación del sub-router disparaba con `"META" in t` | «¿cuánto cumplimos de la **meta** en agosto?» (sin P50) pasaba de `causal` (vs PPTO, correcto: en este sistema *meta* = presupuesto) a `referencia` (P50). **Cambiaba el significado.** | Condición solo con `"P50" in t`. |
| 3 | La bifurcación no excluía las señales causales | «¿**por qué** no cumplimos el P50 en agosto?» caía en `referencia` (una cifra) en vez de `causal` (la explicación). | Se añade `and not any(k in t for k in _CAUSAL_EXPL)` + caso negativo en el golden. |
| 4 | El panel `p50_cards` se inyectaba **sin el envoltorio `.cn-kpi__row`** | Las 5 tarjetas se apilaban en bloque, sin la rejilla de 5 columnas (`colapsable.css:1220`): el panel del chat no se parecía al del panorama. | El dispatcher envuelve la composición en `<div class="cn-kpi__row">`. |
| 5 | **No subía el cache-buster** `?v=` del JS | El navegador sirve el `multitab_shell.js` viejo, el tipo `p50_cards` cae al fallback y pinta una tarjeta KPI corrupta — **con la consola limpia**. Ya pasó en este proyecto. | Nuevo paso: `?v=20260908a` en `main.html:88` y `mainchat_layout.html:323`. |

Además: un comentario de la v1 afirmaba algo falso (que `"CUMPLI"` no atrapa `"INCUMPLI…"`; sí lo atrapa, es substring), 3 frases de la tupla eran redundantes, y el caso «mes pasado» se descartaba en silencio. Todo corregido.

---

## §0. Contexto para el agente EXECUTOR

> El executor no tiene la conversación previa, ni el historial de git, ni memoria. Todo lo necesario está aquí.

### 0.1 Qué es ProdIA

Aplicación de producción de hidrocarburos de Ecopetrol. **Son dos procesos separados:**

| | Frontend | Backend |
|---|---|---|
| Repo | `ProdIAWebFront` | `ProdIABack` |
| Raíz | `c:\APLICACIONES\ProdIA\Repo ProdIA\frontend\` | `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\` |
| Stack | Flask + Jinja2 + JS vanilla | FastAPI (gestionado con `uv`) |
| Puerto | **5029** | **5030** |

**El navegador nunca habla con el 5030.** Flask hace de proxy en `frontend\routes\api.py`. Las dos rutas de P50 **ya están expuestas** y **ya propagan `periodo`** (`routes\api.py:254` y `:266-274`) — el proxy NO se toca.

### 0.2 El «Motor Q v2» (el que responde el chat)

Vive en `backend\backend\app\features\consulta_v2\`. Una pregunta pasa por dos etapas:

```
Etapa A — clasificador de GRUPO      config\patrones_grupo.yaml  +  patrones.py    ← NO SE TOCA
          → cuantificar | jerarquizar | analizar | out

Etapa B — sub-router (solo si grupo=analizar)   analizar\subrouter.py
          → causal | proyeccion | diferidas | economia | referencia | tendencia
                                                          ↑ AQUÍ vive el P50
```

Después, `respuesta_analizar.py::_responder_core()` construye `{"mensaje": str, "panel": dict|None}`. `maquina_q.py:610-611` es **agnóstico al tipo de panel** («hace `panel = r.get("panel")` y lo devuelve tal cual, sin validar ni enumerar. Un tipo nuevo NO requiere tocar nada aquí»). El `panel` viaja al navegador y `multitab_shell.js` decide qué pintar según `panel.tipo`.

### 0.3 Archivos que este plan toca (rutas ABSOLUTAS)

| # | Archivo | Repo | Qué se hace |
|---|---|---|---|
| A1 | `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\analizar\subrouter.py` | Back | Añadir `_CUMPLIMIENTO`; `referencia` gana a `proyeccion` cuando hay cumplimiento + P50 sin señal causal |
| A2 | `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\analizar\p50_referencia.py` | Back | AÑADIR `periodo_yyyymm()` y `formatear_cumplimiento_mes()` |
| A3 | `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\respuesta_analizar.py` | Back | Propagar el periodo en la rama `referencia` global + emitir panel `p50_cards` + aviso cuando el periodo no es resoluble |
| A4 | `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\golden\analizar_golden.yaml` | Back | +14 casos (10 positivos + 4 negativos) |
| A5 | `c:\APLICACIONES\ProdIA\Repo ProdIA\frontend\static\js\multitab_shell.js` | Front | Extraer `__cnP50CardsHtml()`; registrar `p50_cards` con envoltorio; +2 plantillas |
| A6 | `c:\APLICACIONES\ProdIA\Repo ProdIA\frontend\templates\main.html` | Front | Cache-buster `?v=20260908a` |
| A7 | `c:\APLICACIONES\ProdIA\Repo ProdIA\frontend\MainChat\templates\mainchat_layout.html` | Front | Cache-buster `?v=20260908a` |

**Siete archivos, dos repos.** Contrato entre ambos: el panel `{"tipo": "p50_cards", "datos": <respuesta cruda de /analisis/president>}` (§3.3 lo emite, §3.6 lo consume).

### 0.4 Convenciones OBLIGATORIAS

- **JavaScript: ES5 clásico.** `var` y `function`. **Prohibido**: arrow functions (`=>`), template literals (backticks), `const`, `let`, `class`, spread, destructuring, `Array.includes`, `Object.assign`, `async/await`. (`.map()` y `.join()` sí se usan ya en el archivo.)
- **Python: 3.12.** Se permiten f-strings y `str | None`.
- **Todo el código, los comentarios y los mensajes al usuario: en ESPAÑOL.**
- Los comentarios explican **por qué**, no qué. Cada bloque nuevo lleva `[2026-09-08 · P50-CUMPLIMIENTO-MES]` y la razón.
- **Nunca `MAX(reporte_id)`** para elegir un reporte: es un serial por orden de ingesta, no cronológico.

### 0.5 Cómo correr las cosas (PowerShell, línea por línea)

```powershell
# Golden de ANALIZAR — determinista, SIN BD, corre en local sin VPN
cd 'c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend'
$env:PYTHONPATH='.'; uv run python app/features/consulta_v2/golden/run_golden_analizar.py
```

```powershell
# Sintaxis JS (Node en el PATH)
cd 'c:\APLICACIONES\ProdIA\Repo ProdIA\frontend'
node --check static/js/multitab_shell.js
```

⚠️ **`node --check` NO detecta `ReferenceError`.** Solo sintaxis. Ya pasó aquí: una función usó una variable inexistente, `node --check` dio verde y la app quedó en blanco. Por eso §6.1 exige un grep de definición por cada función nueva invocada.

---

## §1. Hallazgos de la auditoría (v1) — los que siguen vigentes

### 🔴 H-01 — La rama `referencia` NUNCA lee el periodo. Es un fallo silencioso.

`respuesta_analizar.py:264-348` es la rama `referencia`. En sus 85 líneas **no aparece** `_slots.periodo_texto`. Las llamadas son ciegas al mes:

```
:295   anual = serie_anual_fn()             ← sin argumentos
:300   info = president_fn(periodo=None)    ← None HARDCODEADO
```

El periodo sí se extrae, pero **fuera** de esta rama — en `:358`, para la rama causal, arreglada el 2026-08-26. Se arregló el paso 4 y no la rama 3c. «¿…el P50 para el mes de **agosto**?» entra por `:264` y **jamás alcanza `:358`**. Es la familia de bug que `CLAUDE.md` §7 marca como la más peligrosa. **→ §3.3.**

### 🔴 H-02 — `president()` espera `YYYY-MM`; `periodo_texto()` devuelve `"agosto"`. Hay que convertir.

`analisis\api.py:2734`: `def president(periodo: str | None = Query(None))`, y su SQL (`:2739-2745`) hace `to_char(cr.fecha_reporte,'YYYY-MM') = :p`. **Exige `"2026-08"`.**
`cuantificar\slots.py:478-494`: devuelve `"agosto"` | `"agosto 2026"` | `"mes pasado"` | `None`.

Pasar `"agosto"` directo → `rid = None` → `encontrada: False` → el chat diría «No tengo el compromiso P50». Un fallo mudo disfrazado de dato faltante. No se reutiliza `_parse_periodo` (`api.py:379`): es privada, devuelve tupla y exige `ref_y/ref_mo` que un módulo puro no tiene. **→ §3.2.**

### 🟡 H-03 — El diccionario de meses ya existe. NO duplicarlo.

`slots.py:95-97` `_MESES_NUM` incluye `"setiembre": 9`. `respuesta_analizar.py:25-27` y `slots.py:501-503` documentan por qué no se duplica: «el mismo bug de substring existía en dos gemelos a la vez, y ese es el precio de duplicar». **→ §3.2 lo importa.**

### 🟢 H-05 — La colisión CUANTO + P50 ya se resuelve bien.

`patrones.py:51-54` evalúa `precedencia_maxima` primero; el patrón `:71` de cuantificar exige sustantivo de nivel (`CAMPOS|POZOS|ACTIVOS`), que las 10 variantes no tienen. Luego colisión CUANTO (`:131`) vs P50 (`:244`) → `precedencia_colision: [analizar, …]` (`:276`) → **analizar**. «¿cuántos **campos** cumplieron…?» sí va a Cuantificar por `:71`, y es correcto (pide un conteo). **No se toca.**

### 🔴 H-06 — La variante #2 cae en `proyeccion`.

`subrouter.py:53` evalúa `_PROY` (que contiene `"COMO VAMOS"`, `:15`) **antes** de `_REFERENCIA` (`:58`). «¿Cómo vamos contra el compromiso P50 de agosto?» → `proyeccion` → responde el ritmo diario del mes en curso. El orden es intencional y defendido en `:55-56` («"¿vamos a llegar al P50?" sigue siendo proyección») y `analizar_golden.yaml:15-17` fija «¿cómo vamos este mes?» → `proyeccion`. **No se invierte el orden: se añade una condición estrecha (§3.1).**

### 🟢 H-07 — Las 3 trampas ya se comportan bien. Solo hay que fijarlas.

| Trampa | Medido | Correcto |
|---|---|---|
| «…contra el P50 **este mes**» | `periodo_texto` → `None` (`slots.py:491`, «mes» no está en `_MESES`) = mes actual | ✅ |
| «el **crudo** frente al P50 en agosto» | `_producto_explicito` (`respuesta_analizar.py:88-95`) ya filtra en `:265`/`:304` | ✅ |
| «**proyección de cierre** del P50» | `_PROY` contiene `"PROYECCION"` y se evalúa antes | ✅ — §3.1 lo preserva |

### 🟡 H-08 — El panel de 5 tarjetas está atrapado en un callback de fetch.

`multitab_shell.js:6018-6019`, dentro de `__cnPaintP50Header`. Sus 3 constructoras ya son puras y devuelven `""` sin dato: `__cnP50CardHtml(p)` `:3734`, `__cnP50FilialesHtml(emp)` `:5890`, `__cnP50TotalHtml(emp)` `:5922`. `__cnP50CardHtml` es **HTML puro** (sin Plotly, sin SVG diferido) — no necesita hook post-inserción, a diferencia de `p50_anual`. Call sites de `__cnPaintP50Header`: `:2198`, `:3493`, `:5996`. **→ §3.5.**

### 🔴 H-10 — El fallback del dispatcher NO valida el tipo.

`multitab_shell.js:4386` `: __cnCuantCardHtml(d);` pinta una tarjeta KPI con campos ajenos ante cualquier tipo desconocido. Advertido 4 veces en el código (`:4358-4362`, `:4370-4371`, `:4377-4379`, `:4382-4385`). `p50_cards` va entre `p50_anual` (`:4385`) y el fallback. **→ §3.6.**

### 🟡 H-11 — Panel PURO, no lazy.

`_responder_core` ya llama a `president_fn()` (`:300`): el dato está en la mano. Con lazy, el navegador repetiría el fetch y **chat y panel podrían servir meses distintos**. `p50_anual` (`:298`) ya es puro. **→ §3.3.**

### 🟢 H-12 — El golden de `analizar` no tiene NI UN caso de `referencia`.

14 casos; grep de `referencia` y `P50`: **cero**. El runner valida solo la sub-intención, sin BD. Gate ≥90%. Con 14 + 14 = **28 casos**, admite máx. 2 fallos. **→ §3.4.**

### 🟢 H-13 — Catálogo de plantillas: estructura medida.

`multitab_shell.js:1090-1188`, array `__cnHistSeed`. Un item es `{ t, slot, t2, … }` sin `id`. El total **se calcula** (`:1278-1283`). El comentario `:1278` («30 hoy») está desactualizado y **no se corrige** (fuera de alcance). **→ §3.7.**

### 🟡 H-14 — La rama global tiene DOS caminos. Solo se bifurca, no se borra.

`:295-298` serie anual (correcto sin mes: «¿cómo va el P50 en 2026?») y `:299-311` cifra del corte. **Con mes nombrado** manda el mes; **sin mes**, comportamiento intacto. **→ §3.3.**

### 🟡 H-15 — `formatear_cifra_global` no dice el mes. No se modifica: se añade una hermana.

`p50_referencia.py:415` dice «Real del mes» sin nombrarlo. 3 tests fijan su salida. **→ §3.2 `formatear_cumplimiento_mes`.**

### 🔴 H-16 — `president` es endpoint FastAPI: `periodo=` siempre explícito.

`respuesta_analizar.py:369-371`: un default `Query(...)` sobreviviente llega al SQL y revienta con «cannot adapt type 'Query'».

### 🟢 H-17 — La inyección existe y se respeta.

`_responder_core(..., _president_fn=None, ...)` (`:147-150`), `:165 president_fn = _president_fn or _president_ep`. Los fakes de `tests/test_p50_referencia.py:493,512` son `lambda periodo=None: …` → aceptan `periodo=per_ym`. **Ningún test global usa un nombre de mes en el texto** (medido: «cual es el p50 de crudo?», «dame el p50 de cajua», …) → la bifurcación no los desvía.

---

## §1-bis. Hallazgos de la VERIFICACIÓN (v2)

### 🔴 V-01 — Las anclas del clasificador no logran el objetivo y sí hacen daño. Se eliminan.

Objetivo declarado en v1: que una pregunta **sin** «P50» llegara a `analizar`. Pero aunque llegara, `subrouter.py:58` exige el token `P50` para `referencia`: sin él devuelve `causal` → **nunca el panel P50**. La ancla no servía para lo que se puso.

Y sí hacía daño, medido contra `clasificacion_golden.yaml`:
- `CUMPLIMIENTO\w*` en `analizar` + `precedencia_colision: [analizar, …]` → «¿cuál es el **cumplimiento** del presupuesto de Castilla?» pasaba de Cuantificar (cifra + tarjeta) a Analizar/`causal`. Cambio de comportamiento no pedido.
- Como **ancla**, `es_anclado()` (`patrones.py:76-82`) salta el filtro de dominio. El golden `:126` fija «¿cuál es la meta de ahorro…?» → `desconocido`, por la regla del usuario (`:75-76`: «Meta debería estar acompañado del término producción»). Un «cumplimiento de mi meta de ahorro» habría entrado al sistema.
- `run_golden.py` (92 casos) importa `maquina_q.clasificar` y su cabecera pide «backends ABAJO por la RAM» — no es un gate barato de correr en cada cambio.

**Decisión: cero cambios a `patrones_grupo.yaml`.** Las 10 variantes (§2.2) y las 2 plantillas (§3.7) llevan «P50» literal, que ya es ancla (`:324`). Se gana robustez donde importa (sub-router) sin tocar la etapa A.

### 🔴 V-02 — `"META" in t` cambiaba el significado de «meta».

En este sistema *meta* sin P50 = presupuesto (`slots.py::_referencia` devuelve `"PPTO"` por defecto; `clasificacion_golden.yaml:146,251`). «¿cuánto cumplimos de la **meta** de crudo en agosto?» hoy → `causal` (análisis vs PPTO). Con la v1 → `referencia` → **cifra P50**. Respuesta a otra pregunta. **La condición queda solo con `"P50" in t`.**

### 🔴 V-03 — La bifurcación temprana no excluía las señales causales.

`:58` sí las excluye (`and not any(k in t for k in _CAUSAL_EXPL)`); la v1 no. «¿**por qué** no cumplimos el P50 en agosto?» → `CUMPLI` + `P50` → `referencia` (una cifra) en vez de `causal` (la explicación que se pidió). **Se añade la misma exclusión y un caso negativo al golden.**

### 🟡 V-04 — Un comentario de la v1 era falso, y 3 frases sobraban.

- «`"CUMPLI"` NO atrapa `"INCUMPLI…"`» — **falso**: es substring. Funcionalmente da igual (¿«incumplimos el P50»? también pide el cumplimiento → `referencia` es correcto), pero un comentario falso en el código es deuda. Corregido.
- `"QUE TAN CERCA"`, `"CUANTO LE DIMOS"`, `"COMO QUEDO EL REAL"`: las variantes 4, 7 y 9 **no matchean `_PROY`** y ya llegan a `referencia` por `:58`. Añadirlas solo ensancha la superficie de falsos positivos. Y `"CUMPLIMIENTO"` contiene `"CUMPLI"`. **Tupla mínima: `("CUMPLI", "COMPROMISO")`.**

### 🔴 V-05 — Sin `.cn-kpi__row`, las 5 tarjetas no forman fila.

En el panorama viven dentro de `<div class="cn-kpi__row" id="cn-p50-row">` (`multitab_shell.js:2195` y `:6557` — el header se monta en **dos** sitios, ambos con ese div). `colapsable.css:1220`: `.cn-kpi__row { display:grid; grid-template-columns: repeat(5,1fr); … }`. En la pila del chat, `body` se inyecta en un `section.cn-stk` **sin** ese grid → 5 bloques apilados. **El dispatcher envuelve; el header no (ya tiene el div).** Las media queries (`:1221-1222`: 3 columnas <1400px, 1 <900px) son por viewport, no por contenedor: en la pila, más angosta, las tarjetas pueden quedar apretadas. **Es validación humana (H-2b), no se ajusta a ciegas.**

### 🔴 V-06 — Cache-buster. Sin subirlo, el bug es invisible.

`templates/main.html:88` y `MainChat/templates/mainchat_layout.html:323` cargan `multitab_shell.js?v=20260907b`. Con el JS viejo en caché, `p50_cards` cae al fallback y pinta una tarjeta KPI corrupta **con la consola limpia** — indistinguible de un bug de datos. `20260908a` está libre (grep: 0 resultados). `login.html:43` es un `prefetch` ya desincronizado (`20260903i`) y no es lo que se ejecuta: **fuera de alcance.** `colapsable.css` no cambia: su `?v=` no se toca.

### 🟡 V-07 — «mes pasado» se descartaba en silencio por otra puerta.

`periodo_texto` devuelve `"mes pasado"`; `periodo_yyyymm` devuelve `None` (no puede resolverlo sin saber el mes en curso); la v1 caía a la serie anual **sin decirlo**. Mismo defecto que H-01, más pequeño. **Se añade un aviso de una línea**: se dice qué se pidió y qué se sirve. Resolverlo de verdad queda fuera de alcance (§7.2).

### 🟢 V-08 — `COMO QUEDO` (variante 9) no está en precedencia máxima.

`patrones_grupo.yaml:148` `'COMO\s+(CERR[OA]|CERRARON|QUEDO|QUEDARON)\b'` vive en `patrones_grupo.cuantificar` (bloque `:130`), no en `precedencia_maxima` (`:18-73`). Colisiona con `P50\b` y gana `analizar`. ✅

### 🟢 V-09 — `tests/test_analizar.py` no se ve afectado.

5 asserts de `sub_intencion` (`:24-37`): causal, proyeccion ×2, diferidas, economia. Ninguno con P50 + cumplimiento.

### 🟢 V-10 — `maquina_q.py` no requiere cambios.

`:610-611`: «agnóstico al tipo … Un tipo nuevo NO requiere tocar nada aquí».

---

## §2. Estado actual — qué está mirando el executor

### 2.1 Qué pasa HOY con la pregunta objetivo

```
"¿Cuál es el cumplimiento del P50 para el mes de Agosto?"
1. patrones.py           → grupo "analizar"   (ancla 'P50\b', patrones_grupo.yaml:324)    ✅
2. subrouter.py:58       → sub "referencia"                                               ✅
3. respuesta_analizar.py:264  rama referencia; nivel None → global (:290)
4. :295  serie_anual_fn()     ← SIN el mes
5. → responde LA SERIE ANUAL 2026, panel "p50_anual". "Agosto" nunca se leyó.             ❌
```

### 2.2 Las 10 variantes y su estado medido

| # | Pregunta | Grupo hoy | Sub hoy | ¿OK? |
|---|---|---|---|---|
| 1 | ¿Qué cumplimiento tuvimos frente al P50 en agosto? | analizar | referencia | mes ❌ |
| 2 | ¿Cómo vamos contra el compromiso P50 de agosto? | analizar | **proyeccion** | ❌ H-06 |
| 3 | cumplimiento p50 agosto | analizar | referencia | mes ❌ |
| 4 | ¿Cuánto le dimos al P50 en agosto? | analizar | referencia | mes ❌ |
| 5 | ¿Cuánto cumplimos de la meta P50 en agosto? | analizar | referencia | mes ❌ |
| 6 | ¿Estamos cumpliendo el P50 en agosto? | analizar | referencia | mes ❌ |
| 7 | ¿Qué tan cerca quedamos del P50 en agosto? | analizar | referencia | mes ❌ |
| 8 | ¿Cuál es el nivel de cumplimiento del compromiso P50 para agosto? | analizar | referencia | mes ❌ |
| 9 | ¿Cómo quedó el real contra el P50 en agosto? | analizar | referencia | mes ❌ |
| 10 | Muéstrame el cumplimiento del P50 del mes de agosto. | analizar | referencia | mes ❌ |

**Las 10 clasifican al grupo correcto. 9 a la sub-intención correcta. Las 10 pierden el mes.**

### 2.3 El panel objetivo

El del panorama (`__cnPaintP50Header`): 5 tarjetas en una fila de `.cn-kpi__row`.

```
┌──────────┬──────────┬──────────┬──────────┬──────────────┐
│  CRUDO   │   GAS    │ BLANCOS  │ FILIALES │ TOTAL DEL MES│
│  dónut   │  dónut   │  dónut   │ (sin     │  dónut +     │
│ % del P50│ % del P50│ % del P50│  dónut)  │  semáforo    │
│ widget   │ widget   │ widget   │          │  widget gap  │
└──────────┴──────────┴──────────┴──────────┴──────────────┘
```

---

## §3. Especificación

> **LOCALIZAR** es texto literal que debe existir en el archivo tal cual (verificado con grep al escribir este plan); **SUSTITUIR POR** es lo que va en su lugar. Si un ancla no aparece exactamente, **DETENERSE y reportar** (§5.1).

---

### §3.1 — MODIFICAR `subrouter.py`

**Archivo:** `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\analizar\subrouter.py`
Justificación: H-06, H-07, V-02, V-03, V-04.

#### 3.1.a — Añadir la tupla `_CUMPLIMIENTO`

**LOCALIZAR:**
```python
_PUNCT = "¿?¡!.,;:()[]{}\"'`"
_REFERENCIA = ("P50",)
_CAUSAL_EXPL = ("POR QUE", "A QUE SE DEBE", "EXPLICA", "CAUSAS DE",
                "DETRACTORES", "QUE PASO CON", "PESAN", "PESA")
```

**SUSTITUIR POR:**
```python
_PUNCT = "¿?¡!.,;:()[]{}\"'`"
_REFERENCIA = ("P50",)
_CAUSAL_EXPL = ("POR QUE", "A QUE SE DEBE", "EXPLICA", "CAUSAS DE",
                "DETRACTORES", "QUE PASO CON", "PESAN", "PESA")

# [2026-09-08 · P50-CUMPLIMIENTO-MES] Señal de que se pide EL CUMPLIMIENTO (una cifra cerrada
# de un mes), no la proyección de a dónde vamos a llegar. Medido: «¿cómo vamos contra el
# compromiso P50 de agosto?» matcheaba "COMO VAMOS" en _PROY y respondía el ritmo diario del
# mes EN CURSO — otra pregunta, contestada con seguridad, ignorando "agosto".
# 🔑 Match por SUBSTRING sobre la frase normalizada: "CUMPLI" cubre CUMPLIMIENTO, CUMPLIMOS,
#    CUMPLIENDO, CUMPLIO e INCUMPLIMOS (también es substring de esta — y está bien: quien
#    pregunta si incumplimos el P50 pide la misma cifra). Tupla MÍNIMA a propósito: las
#    variantes «qué tan cerca», «cuánto le dimos», «cómo quedó el real» NO matchean _PROY y ya
#    llegan a `referencia` por la puerta normal de abajo; listarlas aquí solo ensancharía la
#    superficie de falsos positivos sin ganar nada.
_CUMPLIMIENTO = ("CUMPLI", "COMPROMISO")
```

#### 3.1.b — Insertar la bifurcación ANTES de `_PROY`

**LOCALIZAR:**
```python
    if any(k in t for k in _TEND):
        return "tendencia"
    if any(k in t for k in _PROY):
        return "proyeccion"
```

**SUSTITUIR POR:**
```python
    if any(k in t for k in _TEND):
        return "tendencia"
    # [2026-09-08 · P50-CUMPLIMIENTO-MES] ANTES de proyeccion, y SOLO con las TRES condiciones:
    # señal de cumplimiento, "P50" nombrado, y NINGUNA señal causal. Preguntar «cuánto
    # CUMPLIMOS del P50» es pedir una cifra ya cerrada; «cómo VAMOS» a secas es pedir una
    # proyección. Con las dos señales gana el cumplimiento: es lo más específico que se dijo.
    # 🔑 Deliberadamente estrecha, para no romper lo que ya funciona (cada línea tiene golden):
    #    · «¿cómo vamos este mes?»               → sin P50 → sigue en proyeccion (golden :15)
    #    · «¿vamos a llegar al P50?»             → sin cumplimiento → proyeccion (comentario :55)
    #    · «¿proyección de cierre del P50?»      → sin cumplimiento → proyeccion
    #    · «¿por qué no cumplimos el P50?»       → señal CAUSAL → causal, no una cifra
    #    · «¿cuánto cumplimos de la META?» (sin P50) → causal vs PPTO: en este sistema "meta"
    #      sin P50 es presupuesto (slots._referencia -> "PPTO"), y responder el P50 sería
    #      contestar otra pregunta. Por eso NO se mira "META" aquí, solo "P50".
    # 🔑 P50 se busca en `t` (substring) y no en `toks`: basta saber que la referencia está
    #    nombrada, y «…del P50?» pegado al signo debe contar igual. La puerta normal de
    #    `referencia` (más abajo, por token) no se toca.
    if (any(k in t for k in _CUMPLIMIENTO) and "P50" in t
            and not any(k in t for k in _CAUSAL_EXPL)):
        return "referencia"
    if any(k in t for k in _PROY):
        return "proyeccion"
```

#### 3.1.c — Docstring

**LOCALIZAR:**
```python
    """causal (default) | proyeccion | diferidas | economia | referencia | tendencia.
    Precedencia: economia/diferidas ganan (son fuentes distintas), luego TENDENCIA, luego
    proyeccion, luego referencia (P50 sin señal causal explícita), luego causal."""
```

**SUSTITUIR POR:**
```python
    """causal (default) | proyeccion | diferidas | economia | referencia | tendencia.
    Precedencia: economia/diferidas ganan (son fuentes distintas), luego TENDENCIA, luego
    CUMPLIMIENTO+P50 sin señal causal (referencia temprana, 2026-09-08), luego proyeccion,
    luego referencia (P50 sin señal causal explícita), luego causal."""
```

---

### §3.2 — AÑADIR a `p50_referencia.py`: convertidor de periodo y formateador del mes

**Archivo:** `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\analizar\p50_referencia.py`
Justificación: H-02, H-03, H-15.

**LOCALIZAR** (cierre de `formatear_cifra_global`, `:419-422`; `comp = card.get` aparece **una sola vez** en el archivo — verificado):
```python
    comp = card.get("compromiso")
    if comp is not None and card.get("compromiso_difiere"):
        linea += f"\nCompromiso (RETO): {_kbpe(comp)} {unidad}"
    return linea
```

**SUSTITUIR POR** (el ancla se conserva íntegra; se añaden las dos funciones detrás):
```python
    comp = card.get("compromiso")
    if comp is not None and card.get("compromiso_difiere"):
        linea += f"\nCompromiso (RETO): {_kbpe(comp)} {unidad}"
    return linea


# [2026-09-08 · P50-CUMPLIMIENTO-MES] Puente entre DOS contratos que no encajaban:
#   · cuantificar/slots.periodo_texto() devuelve   "agosto" | "agosto 2026" | "mes pasado" | None
#   · analisis.api.president(periodo=...) exige     "2026-08"  (su SQL hace to_char(...,'YYYY-MM'))
# Sin esta conversión, pasar "agosto" produce to_char(...) = 'agosto', que no casa con NINGUNA
# fila -> encontrada:False -> el chat diría «no tengo el P50 disponible». Un fallo mudo
# disfrazado de dato faltante, que es peor que un error visible.
# 🔑 _MESES_NUM se IMPORTA de slots, no se copia. El proyecto ya pagó el precio de duplicar el
#    detector de meses: el mismo bug de substring ("mayo" dentro de "mayor") vivía en dos
#    gemelos a la vez (ver slots.py:501-503 y respuesta_analizar.py:25-27). Un solo diccionario.
# 🔑 Función PURA: no toca BD, no importa nada de analisis.api. Testeable sin entorno.
_ANIO_P50 = 2026


def periodo_yyyymm(per: str | None, anio_defecto: int = _ANIO_P50) -> str | None:
    """"agosto" -> "2026-08". None si no hay un MES CONCRETO que resolver.

    Devuelve None a propósito en tres casos; el llamador decide qué hacer, y lo DICE:
      · per is None            -> el usuario no nombró mes ("¿cómo va el P50?")
      · per == "mes pasado"    -> RELATIVO: resolverlo exigiría saber el mes en curso, y este
                                  módulo es puro. Adivinarlo aquí arriesgaría servir un mes
                                  distinto al que el texto anuncia.
      · mes no reconocido      -> nunca inventar un periodo.
    """
    if not per:
        return None
    p = str(per).strip().lower()
    if p.startswith("mes "):                 # "mes pasado" / "mes anterior"
        return None
    from app.features.consulta_v2.cuantificar.slots import _MESES_NUM
    partes = p.split()
    mes = _MESES_NUM.get(partes[0])
    if not mes:
        return None
    anio = anio_defecto
    for tk in partes[1:]:                    # el año viaja como 2º token ("agosto 2026")
        if len(tk) == 4 and tk.isdigit():
            anio = int(tk)
            break
    return f"{anio:04d}-{mes:02d}"


# Nombres para rotular el mes en el texto. NO se derivan invirtiendo _MESES_NUM: ese
# diccionario tiene DOS claves para el 9 ("septiembre" y "setiembre") y la inversión daría
# una u otra según el orden de iteración — no determinista de cara al usuario.
_MES_NOMBRE = {1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
               7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre",
               12: "diciembre"}


def etiqueta_periodo(periodo: str) -> str:
    """"2026-08" -> "agosto de 2026". Si el formato no es YYYY-MM, devuelve el texto tal cual."""
    try:
        a, m = str(periodo).split("-")
        return f"{_MES_NOMBRE.get(int(m), periodo)} de {a}"
    except (ValueError, AttributeError, TypeError):
        return str(periodo)


def formatear_cumplimiento_mes(card: dict, unidad: str, producto: str, periodo: str,
                               corte: str | None = None) -> str:
    """Cuerpo del cumplimiento P50 de UN MES CONCRETO. `card` = dict de analisis.president().

    Hermana de `formatear_cifra_global` (:406), NO su reemplazo: aquella la sigue usando la
    rama sin periodo y 3 tests fijan su salida exacta. La diferencia es una sola y es la razón
    de existir de esta función: ROTULA EL MES. Decir "Real del mes" cuando el mes es elegible
    es el mismo fallo silencioso que este plan corrige — si un día se sirviera otro periodo,
    nada en la respuesta lo delataría. PURA: no toca BD ni LLM.
    """
    ent = card.get("entidad", "Ecopetrol")
    real, p50 = card.get("real_mes"), card.get("base_p50")
    pct = card.get("cumpl_p50")
    etiqueta = etiqueta_periodo(periodo)
    if real is None or p50 is None:
        return (f"No tengo el cumplimiento del P50 de {ent} para {etiqueta} — ese mes no tiene "
                "real y P50 a la vez en la fuente.")
    linea = (f"📊 {ent} · cumplimiento del P50 · {etiqueta}"
             + (f" (corte {corte})" if corte else "") + "\n\n"
             f"Real: {_kbpe(real)} {unidad} · Base P50: {_kbpe(p50)} {unidad}")
    if pct is not None:
        linea += f" · {pct}% del P50"
    gap = card.get("delta_p50")
    if gap is None:
        gap = round(float(real) - float(p50), 1)
    signo = "+" if gap >= 0 else ""
    linea += f"\nGap vs P50: {signo}{_kbpe(gap)} {unidad}"
    comp = card.get("compromiso")
    if comp is not None and card.get("compromiso_difiere"):
        linea += f"\nCompromiso (RETO): {_kbpe(comp)} {unidad}"
    return linea
```

---

### §3.3 — MODIFICAR `respuesta_analizar.py`: propagar el mes, emitir el panel, avisar lo no resoluble

**Archivo:** `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\respuesta_analizar.py`
Justificación: H-01, H-11, H-14, H-16, H-17, V-07.

**LOCALIZAR** (bloque completo de la rama global, `:290-311`):
```python
            else:   # nivel is None -> global ECP (REPORTE_PRESIDENT, escala kbpe)
                # [2026-09-07 · PANEL-P50-ANUAL] El P50 corporativo se pacta por AÑO y la pregunta
                # natural («¿cómo va el P50 en 2026?») es por la SERIE, no por un mes suelto. Si
                # core.p50_2026 tiene los 12 meses se responde la serie + panel; si no (tabla sin
                # migrar en este entorno), se cae al comportamiento anterior: la cifra del corte.
                anual = serie_anual_fn()
                if anual and anual.get("serie"):
                    cuerpo = _p50.formatear_serie_anual(anual)
                    panel_ref = {"tipo": "p50_anual", "datos": anual}
                else:
                    info = president_fn(periodo=None)
                    if not info.get("encontrada"):
                        cuerpo = "No tengo el compromiso P50 disponible en este momento."
                    else:
                        card = next((p for p in info.get("productos", [])
                                    if p.get("entidad", "").upper() == producto), None)
                        if card is None:
                            card = next((t for t in info.get("totales", [])
                                        if t.get("entidad") == "Ecopetrol"), None)
                        cuerpo = (_p50.formatear_cifra_global(card, info.get("unidad", "kbpe"),
                                                              producto, info.get("corte"))
                                  if card else "No tengo el compromiso P50 disponible en este momento.")
```

**SUSTITUIR POR:**
```python
            else:   # nivel is None -> global ECP (REPORTE_PRESIDENT, escala kbpe)
                # [2026-09-08 · P50-CUMPLIMIENTO-MES] El PERIODO deja de descartarse. Hasta hoy
                # esta rama era CIEGA al mes: «¿cuál es el cumplimiento del P50 para el mes de
                # AGOSTO?» respondía la serie anual completa y la palabra "agosto" no se leía en
                # ningún punto de las 85 líneas de la rama `referencia` — medido. El detector YA
                # existía (cuantificar/slots.periodo_texto, reusado en :358 para la rama causal
                # desde el 2026-08-26) y el endpoint YA aceptaba `periodo`. Solo faltaba
                # conectarlos, más el puente de formato (slots dice "agosto", president exige
                # "2026-08": p50_referencia.periodo_yyyymm).
                # 🔑 `periodo=` va EXPLÍCITO siempre: `president` es un endpoint FastAPI y su
                #    default es un objeto Query(...) que, si sobrevive, llega al SQL y revienta
                #    con "cannot adapt type 'Query'" (mismo patrón advertido en :369-371).
                per_txt = _slots.periodo_texto(texto)
                per_ym = _p50.periodo_yyyymm(per_txt)
                if per_ym:
                    # MES CONCRETO pedido -> la tarjeta de ESE mes, con el panel de 5 tarjetas
                    # (el mismo del panorama). No la serie anual: el usuario acotó, se respeta.
                    info = president_fn(periodo=per_ym)
                    if not info.get("encontrada") or not info.get("productos"):
                        # Honesto y explícito: se nombra el mes que NO se pudo servir. Callarlo
                        # y devolver otro periodo es el fallo que este bloque viene a corregir.
                        cuerpo = (f"No tengo el compromiso P50 para {_p50.etiqueta_periodo(per_ym)}"
                                  " — ese mes no tiene REPORTE_PRESIDENT cargado en este entorno.")
                    else:
                        card = next((p for p in info.get("productos", [])
                                    if p.get("entidad", "").upper() == producto), None)
                        if card is None:
                            card = next((t for t in info.get("totales", [])
                                        if t.get("entidad") == "Ecopetrol"), None)
                        cuerpo = (_p50.formatear_cumplimiento_mes(
                                      card, info.get("unidad", "kbpe"), producto, per_ym,
                                      info.get("corte"))
                                  if card else
                                  f"No tengo el compromiso P50 para {_p50.etiqueta_periodo(per_ym)}.")
                        # Panel PURO: los datos ya están en `info`, se mandan tal cual. Con un
                        # panel lazy el navegador repetiría el fetch y podría servir un mes
                        # distinto al del texto si entre ambas llamadas entra una ingesta — un
                        # panel que contradice su propio mensaje es peor que no tener panel.
                        # Mismo patrón puro que "p50_anual" (abajo) y "analiza_tend".
                        panel_ref = {"tipo": "p50_cards", "datos": info}
                else:
                    # SIN mes concreto. Si el usuario SÍ escribió un periodo pero no es
                    # resoluble aquí («mes pasado»), se DICE: servir la serie anual callando lo
                    # que se pidió sería el mismo bug de arriba entrando por una puerta más
                    # estrecha. Resolver "mes pasado" de verdad exige el mes en curso (BD) y
                    # queda fuera de este plan — pero nunca en silencio.
                    aviso = ""
                    if per_txt:
                        aviso = (f"⚠️ Pediste «{per_txt}» y esta referencia resuelve meses por su "
                                 "nombre (p. ej. «agosto»); te muestro la vista anual, que lo "
                                 "incluye.\n\n")
                    # [2026-09-07 · PANEL-P50-ANUAL] Comportamiento anterior, INTACTO: el P50
                    # corporativo se pacta por AÑO y la pregunta natural («¿cómo va el P50 en
                    # 2026?») es por la SERIE, no por un mes suelto. Si core.p50_2026 tiene los
                    # 12 meses se responde la serie + panel; si no (tabla sin migrar en este
                    # entorno), se cae al comportamiento anterior: la cifra del corte.
                    anual = serie_anual_fn()
                    if anual and anual.get("serie"):
                        cuerpo = aviso + _p50.formatear_serie_anual(anual)
                        panel_ref = {"tipo": "p50_anual", "datos": anual}
                    else:
                        info = president_fn(periodo=None)
                        if not info.get("encontrada"):
                            cuerpo = "No tengo el compromiso P50 disponible en este momento."
                        else:
                            card = next((p for p in info.get("productos", [])
                                        if p.get("entidad", "").upper() == producto), None)
                            if card is None:
                                card = next((t for t in info.get("totales", [])
                                            if t.get("entidad") == "Ecopetrol"), None)
                            cuerpo = aviso + (
                                _p50.formatear_cifra_global(card, info.get("unidad", "kbpe"),
                                                            producto, info.get("corte"))
                                if card else "No tengo el compromiso P50 disponible en este momento.")
```

⚠️ **Indentación:** el `else:` exterior está a 12 espacios; su contenido a 16; el contenido de `if per_ym:` / `else:` interiores a 20. El bloque antiguo se reproduce **desplazado 4 espacios a la derecha**. Python es sensible a esto — V-6 lo comprueba.

---

### §3.4 — MODIFICAR `analizar_golden.yaml`: +14 casos

**Archivo:** `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\golden\analizar_golden.yaml`
Justificación: H-12, H-07, V-03.

**LOCALIZAR** (últimas 3 líneas del archivo):
```yaml
- pregunta: "muéstrame la media móvil de Cusiana"
  entidad: "CUSIANA"
  sub: tendencia
```

**SUSTITUIR POR:**
```yaml
- pregunta: "muéstrame la media móvil de Cusiana"
  entidad: "CUSIANA"
  sub: tendencia

# --- referencia / cumplimiento P50 por mes (2026-09-08 · P50-CUMPLIMIENTO-MES) ---
# Antes de este bloque el golden NO tenía NI UN caso de `referencia` (medido: cero
# coincidencias de "referencia" y de "P50" en el archivo). La sub-intención que responde el
# compromiso corporativo no estaba protegida por ninguna regresión. Son las 10 formas reales
# en que un usuario pide lo mismo — variaciones de registro, no sinónimos de laboratorio.
- pregunta: "¿Qué cumplimiento tuvimos frente al P50 en agosto?"
  entidad: null
  sub: referencia
- pregunta: "¿Cómo vamos contra el compromiso P50 de agosto?"
  entidad: null
  sub: referencia
- pregunta: "cumplimiento p50 agosto"
  entidad: null
  sub: referencia
- pregunta: "¿Cuánto le dimos al P50 en agosto?"
  entidad: null
  sub: referencia
- pregunta: "¿Cuánto cumplimos de la meta P50 en agosto?"
  entidad: null
  sub: referencia
- pregunta: "¿Estamos cumpliendo el P50 en agosto?"
  entidad: null
  sub: referencia
- pregunta: "¿Qué tan cerca quedamos del P50 en agosto?"
  entidad: null
  sub: referencia
- pregunta: "¿Cuál es el nivel de cumplimiento del compromiso P50 para agosto?"
  entidad: null
  sub: referencia
- pregunta: "¿Cómo quedó el real contra el P50 en agosto?"
  entidad: null
  sub: referencia
- pregunta: "Muéstrame el cumplimiento del P50 del mes de agosto."
  entidad: null
  sub: referencia

# --- casos NEGATIVOS: parecidas pero NO equivalentes (2026-09-08) ---
# Están aquí para que un futuro ensanchamiento del vocabulario de cumplimiento no se las lleve
# por delante: el día que alguien meta "PROYECCION" o "COMO VAMOS" en _CUMPLIMIENTO, o quite
# la exclusión causal, el gate cae.
# 1) Deíctico sin P50: sigue en proyeccion (ya lo fijaba :15-17; el cambio no debe alterarlo).
- pregunta: "¿Cómo vamos este mes?"
  entidad: null
  sub: proyeccion
# 2) Proyección CON P50 pero sin cumplimiento: se pide a dónde vamos a llegar, no qué cumplimos.
- pregunta: "¿Cuál es la proyección de cierre del P50 en agosto?"
  entidad: null
  sub: proyeccion
# 3) Meta sin cumplimiento: proyección pura (subrouter.py:55-56, desde el 2026-08-13).
- pregunta: "¿Vamos a llegar al P50 este mes?"
  entidad: null
  sub: proyeccion
# 4) Cumplimiento + P50 pero CAUSAL: se pide la explicación, no la cifra. Si esto cayera en
#    `referencia`, quien pregunta "por qué" recibiría un número.
- pregunta: "¿Por qué no cumplimos el P50 en agosto?"
  entidad: null
  sub: causal
```

---

### §3.5 — MODIFICAR `multitab_shell.js`: extraer el compositor de las 5 tarjetas

**Archivo:** `c:\APLICACIONES\ProdIA\Repo ProdIA\frontend\static\js\multitab_shell.js`
Justificación: H-08.

**LOCALIZAR** (`:6013-6019`, dentro de `__cnPaintP50Header`):
```javascript
        // [2026-09-08] Cuarta tarjeta: FILIALES. La lámina apila REAL NACIONAL (Ecopetrol) y
        // REAL FILIALES; el panel solo mostraba los tres productos y ese corte faltaba.
        // Va DESPUÉS de los productos y con su propia clase: no es un producto físico, es una
        // empresa, así que no lleva anillo Real/P50 por producto sino la comparación contra su
        // propio P50. Si el backend no manda `empresas` (versión anterior), no se pinta nada.
        row2.innerHTML = d.productos.map(__cnP50CardHtml).join("") +
                         __cnP50FilialesHtml(d.empresas) + __cnP50TotalHtml(d.empresas);
```

**SUSTITUIR POR:**
```javascript
        // [2026-09-08] Cuarta tarjeta: FILIALES. La lámina apila REAL NACIONAL (Ecopetrol) y
        // REAL FILIALES; el panel solo mostraba los tres productos y ese corte faltaba.
        // Va DESPUÉS de los productos y con su propia clase: no es un producto físico, es una
        // empresa, así que no lleva anillo Real/P50 por producto sino la comparación contra su
        // propio P50. Si el backend no manda `empresas` (versión anterior), no se pinta nada.
        // [P50-CUMPLIMIENTO-MES] La composición vive en __cnP50CardsHtml, compartida con el
        // panel "p50_cards" del chat. Aquí NO se envuelve: `row2` YA es el .cn-kpi__row.
        row2.innerHTML = __cnP50CardsHtml(d);
```

**LOCALIZAR** (`:5993-5995`):
```javascript
  // Handler del <select>. Repinta SOLO el panel P50 (decisión del usuario 2026-09-08): el resto
  // del tablero sigue en su mes, y cada bloque declara el suyo en su encabezado.
  window.__cnP50CambiarMes = function (v) {
```

**SUSTITUIR POR:**
```javascript
  // [2026-09-08 · P50-CUMPLIMIENTO-MES] La fila de 5 tarjetas, extraída a función PURA.
  // Estaba incrustada dentro del callback de fetch de __cnPaintP50Header y por eso solo existía
  // en el panorama: el chat no tenía forma de pintarla. Ahora la comparten los dos consumidores
  // (el encabezado del tablero y el panel "p50_cards" del Motor Q), y así no pueden divergir.
  // 🔑 `d` es la respuesta CRUDA de /api/analisis/president. Las tres constructoras que compone
  //    ya devuelven "" cuando les falta su dato (__cnP50CardHtml, __cnP50FilialesHtml,
  //    __cnP50TotalHtml), así que componer nunca puede reventar: en el peor caso salen menos
  //    tarjetas, no una excepción.
  // 🔑 Devuelve SOLO las tarjetas, sin el .cn-kpi__row: el header ya lo tiene en el DOM y el
  //    dispatcher lo añade él mismo. Envolver aquí duplicaría la rejilla en el header.
  function __cnP50CardsHtml(d) {
    if (!d || !d.productos || !d.productos.length) { return ""; }
    return d.productos.map(__cnP50CardHtml).join("") +
           __cnP50FilialesHtml(d.empresas) + __cnP50TotalHtml(d.empresas);
  }

  // Handler del <select>. Repinta SOLO el panel P50 (decisión del usuario 2026-09-08): el resto
  // del tablero sigue en su mes, y cada bloque declara el suyo en su encabezado.
  window.__cnP50CambiarMes = function (v) {
```

---

### §3.6 — MODIFICAR `multitab_shell.js`: registrar `p50_cards` en el dispatcher, CON envoltorio

**Archivo:** el mismo.
Justificación: H-10, V-05.

**LOCALIZAR** (`:4381-4386`):
```javascript
             // [2026-09-07 · PANEL-P50-ANUAL] "p50_anual" (Analizar/referencia, rama GLOBAL):
             // serie mensual del P50 corporativo. Registrado ANTES del fallback por la misma
             // razón que "p50_vp": __cnCuantCardHtml NO valida el tipo y pintaría una tarjeta
             // KPI leyendo campos (estado/cumplimiento_pct/nivel) que este contrato no tiene.
             : (panel.tipo === "p50_anual")        ? __cnP50AnualHtml(d)
             : __cnCuantCardHtml(d);
```

**SUSTITUIR POR:**
```javascript
             // [2026-09-07 · PANEL-P50-ANUAL] "p50_anual" (Analizar/referencia, rama GLOBAL):
             // serie mensual del P50 corporativo. Registrado ANTES del fallback por la misma
             // razón que "p50_vp": __cnCuantCardHtml NO valida el tipo y pintaría una tarjeta
             // KPI leyendo campos (estado/cumplimiento_pct/nivel) que este contrato no tiene.
             : (panel.tipo === "p50_anual")        ? __cnP50AnualHtml(d)
             // [2026-09-08 · P50-CUMPLIMIENTO-MES] "p50_cards" (Analizar/referencia, rama GLOBAL
             // CON MES): las 5 tarjetas del panorama (Crudo · Gas · Blancos · Filiales · Total),
             // ahora también en el chat cuando la pregunta acota un mes. `d` es la respuesta
             // cruda de /analisis/president, que el backend ya tenía en la mano — panel PURO,
             // sin fetch ni hook post-inserción (las tarjetas son HTML plano, no Plotly).
             // 🔑 Se ENVUELVE en .cn-kpi__row: es la rejilla de 5 columnas (colapsable.css:1220)
             //    que en el panorama ya existe en el DOM (#cn-p50-row) y aquí no. Sin ella las
             //    tarjetas se apilan en bloque. Registrado ANTES del fallback por la razón de
             //    siempre: __cnCuantCardHtml NO valida el tipo y pintaría campos ajenos.
             : (panel.tipo === "p50_cards")        ? '<div class="cn-kpi__row">' + __cnP50CardsHtml(d) + '</div>'
             : __cnCuantCardHtml(d);
```

---

### §3.7 — MODIFICAR `multitab_shell.js`: +2 plantillas en «Cumplimiento vs metas»

**Archivo:** el mismo.
Justificación: H-13. Ambas llevan «P50» literal (V-01) y el hueco `mes` (H-07: sin él, «este mes» resolvería al mes en curso).

**LOCALIZAR** (`:1119-1126`):
```javascript
      items: [
        { t: "¿Cómo vamos este mes?" },
        { t: "¿Vamos a cerrar en meta?" },
        { t: "¿Cómo va ", slot: "entidad", t2: " frente al presupuesto este mes?" },
        { t: "¿Cuánto produjo ", slot: "entidad", t2: " en ", slot2: "mes", t3: " vs el operativo?" },
        { t: "¿Cuánto produjo ", slot: "entidad", t2: " en ", slot2: "mes", t3: " contra el contable?" },
        { t: "¿Cómo va ", slot: "entidad", t2: " frente al promedio del año?" }
      ]
```

**SUSTITUIR POR:**
```javascript
      items: [
        { t: "¿Cómo vamos este mes?" },
        { t: "¿Vamos a cerrar en meta?" },
        // [2026-09-08 · P50-CUMPLIMIENTO-MES] El cumplimiento del P50 por MES no estaba
        // ofrecido en ninguna plantilla, aunque es la pregunta que más se hace sobre la lámina
        // gerencial. Lleva el hueco `mes` para que el usuario lo elija: sin él, "este mes"
        // resolvería al mes en curso y la respuesta sería de otro periodo. Las dos dicen "P50"
        // literal a propósito: es el ancla que las lleva a Analizar/referencia.
        { t: "¿Cuál es el cumplimiento del P50 para el mes de ", slot: "mes", t2: "?" },
        { t: "¿Cómo quedó el real contra el P50 en ", slot: "mes", t2: "?" },
        { t: "¿Cómo va ", slot: "entidad", t2: " frente al presupuesto este mes?" },
        { t: "¿Cuánto produjo ", slot: "entidad", t2: " en ", slot2: "mes", t3: " vs el operativo?" },
        { t: "¿Cuánto produjo ", slot: "entidad", t2: " en ", slot2: "mes", t3: " contra el contable?" },
        { t: "¿Cómo va ", slot: "entidad", t2: " frente al promedio del año?" }
      ]
```

La categoría pasa de 6 a 8 y el total de 41 a 43, ambos calculados (`:1278-1283`).

---

### §3.8 — MODIFICAR los dos templates: cache-buster

Justificación: V-06.

**Archivo A6:** `c:\APLICACIONES\ProdIA\Repo ProdIA\frontend\templates\main.html`

**LOCALIZAR** (`:88`, una sola ocurrencia):
```html
<script src="{{ url_for('static', filename='js/multitab_shell.js') }}?v=20260907b"></script>
```
**SUSTITUIR POR:**
```html
<script src="{{ url_for('static', filename='js/multitab_shell.js') }}?v=20260908a"></script>
```

**Archivo A7:** `c:\APLICACIONES\ProdIA\Repo ProdIA\frontend\MainChat\templates\mainchat_layout.html`

**LOCALIZAR** (`:323`, una sola ocurrencia):
```html
<script defer src="{{ url_for('static', filename='js/multitab_shell.js') }}?v=20260907b"></script>
```
**SUSTITUIR POR:**
```html
<script defer src="{{ url_for('static', filename='js/multitab_shell.js') }}?v=20260908a"></script>
```

⚠️ En esos mismos archivos hay `colapsable.css?v=20260907b`. **No se toca**: el CSS no cambia en este plan.

---

## §4. Orden de ejecución

Las funciones nuevas van **antes** que sus call sites.

| Paso | § | Repo | Archivo | Acción | Verificación inmediata |
|---|---|---|---|---|---|
| 0 | — | Back | — | **Línea base:** correr V-7 y V-8 y anotar los números | — |
| 1 | 3.1.a | Back | `subrouter.py` | AÑADIR `_CUMPLIMIENTO` | grep: 1 definición |
| 2 | 3.1.b | Back | `subrouter.py` | INSERTAR bifurcación entre `_TEND` y `_PROY` | el `if` nuevo está **antes** de `_PROY` |
| 3 | 3.1.c | Back | `subrouter.py` | Docstring | — |
| 4 | 3.2 | Back | `p50_referencia.py` | AÑADIR `periodo_yyyymm`, `etiqueta_periodo`, `formatear_cumplimiento_mes` | grep: 3 definiciones |
| 5 | 3.3 | Back | `respuesta_analizar.py` | Bifurcación por `per_ym` + aviso | V-6 (compila) |
| 6 | 3.4 | Back | `analizar_golden.yaml` | +14 casos | V-3: 28 casos |
| 7 | — | Back | — | **V-1 golden** + V-4 + V-5 + V-7 | todo verde |
| 8 | 3.5 | Front | `multitab_shell.js` | AÑADIR `__cnP50CardsHtml` + usarla en el header | `node --check` |
| 9 | 3.6 | Front | `multitab_shell.js` | Registrar `p50_cards` con envoltorio | V-11: antes del fallback |
| 10 | 3.7 | Front | `multitab_shell.js` | +2 plantillas | `node --check` |
| 11 | 3.8 | Front | `main.html`, `mainchat_layout.html` | `?v=20260908a` | V-13: 2 resultados |
| 12 | — | — | — | **§6.1 completa** | todos los checks |

**Dos commits, uno por repo.** Backend: pasos 1-7. Frontend: pasos 8-11.

---

## §5. Reglas no negociables

1. **Si un ancla LOCALIZAR no aparece exactamente, DETENTE.** No improvises variantes. Reporta ancla, archivo y lo que encontraste. Una edición «aproximada» dejó un paréntesis huérfano en `multitab_shell.js` y la app quedó en blanco en producción.
2. **JS en ES5 clásico.** `var` + `function`. Nada de `=>`, backticks, `const`, `let`, `class`, spread, destructuring, `includes`, `Object.assign`, `async`.
3. **Español** en código, comentarios, mensajes y en tu reporte.
4. **CERO cambios fuera de lo especificado.** No refactorices, no corrijas comentarios viejos (`:1278` «30 hoy» se queda), no reordenes imports, no formatees.
5. **`patrones_grupo.yaml` NO se toca.** Si crees que hace falta, has malinterpretado el plan (V-01).
6. **`routes/api.py` NO se toca** (ya expone y propaga `periodo`).
7. **No invertir `_PROY` / `_REFERENCIA`.** El `if` de `_PROY` queda exactamente donde está. El cambio es un `if` **añadido** antes.
8. **`periodo=` siempre explícito** en `president_fn` (H-16).
9. **No tocar `formatear_cifra_global`** ni `formatear_serie_anual` (H-15).
10. **`__cnP50CardsHtml` NO envuelve; el dispatcher SÍ.** Al revés, el header tendría la rejilla duplicada (V-05).
11. **El estado final que reportas es «implementado, PENDIENTE de validación humana».** Nunca «verificado» ni «completado» (`CLAUDE.md` §10.4, R3).

---

## §6. Validación

### 6.1 Estática — la ejecuta el EXECUTOR

PowerShell, **línea por línea**, sin consola de administrador. Si un bloque queda en `>>`, Enter.

| # | Qué | Carpeta y comando | Esperado |
|---|---|---|---|
| **V-1** | Golden de analizar | `cd 'c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend'` <br> `$env:PYTHONPATH='.'; uv run python app/features/consulta_v2/golden/run_golden_analizar.py` | `EXACTITUD (sub-intención): 28/28 = 100%`. Gate ≥90% (máx. 2 fallos). **Si falla uno de los 4 negativos, la bifurcación de §3.1 es demasiado ancha → DETENTE** |
| **V-3** | Golden YAML válido, 28 casos, 10 de referencia | misma carpeta <br> `uv run python -c "import yaml;c=yaml.safe_load(open('app/features/consulta_v2/golden/analizar_golden.yaml',encoding='utf-8'));print(len(c),'casos');print(sum(1 for x in c if x['sub']=='referencia'),'referencia')"` | `28 casos` / `10 referencia` |
| **V-4** | Convertidor de periodo | misma carpeta <br> `$env:PYTHONPATH='.'; uv run python -c "from app.features.consulta_v2.analizar.p50_referencia import periodo_yyyymm as f, etiqueta_periodo as e;print([f('agosto'),f('agosto 2026'),f('setiembre'),f('mes pasado'),f(None),f('trimestre')], e('2026-08'))"` | `['2026-08', '2026-08', '2026-09', None, None, None] agosto de 2026` |
| **V-5** | Sub-intención: 2 positivas + 4 negativas | misma carpeta <br> `$env:PYTHONPATH='.'; uv run python -c "from app.features.consulta_v2.analizar.subrouter import sub_intencion as s;print(s('¿Cómo vamos contra el compromiso P50 de agosto?'), s('¿Estamos cumpliendo el P50 en agosto?'), s('¿Cómo vamos este mes?'), s('¿Cuál es la proyección de cierre del P50 en agosto?'), s('¿Por qué no cumplimos el P50 en agosto?'), s('¿cuánto cumplimos de la meta de crudo en agosto?'))"` | `referencia referencia proyeccion proyeccion causal causal` |
| **V-6** | Los 3 .py compilan | misma carpeta <br> `uv run python -m py_compile app/features/consulta_v2/respuesta_analizar.py app/features/consulta_v2/analizar/p50_referencia.py app/features/consulta_v2/analizar/subrouter.py` | Sin salida |
| **V-7** | Tests de referencia y analizar, sin regresión | misma carpeta <br> `uv run python -m pytest tests/test_p50_referencia.py tests/test_analizar.py -q` | **El mismo número de pasados que en el paso 0.** Más fallos que la línea base → DETENTE |
| **V-8** | `patrones_grupo.yaml` sin cambios | misma carpeta <br> `git diff --stat -- app/features/consulta_v2/config/patrones_grupo.yaml` | **Sin salida** (0 cambios) |
| **V-9** | Sintaxis JS | `cd 'c:\APLICACIONES\ProdIA\Repo ProdIA\frontend'` <br> `node --check static/js/multitab_shell.js` | Sin salida |
| **V-10** | 🔴 La función nueva EXISTE y se usa en 2 sitios | misma carpeta <br> `Select-String -Path static\js\multitab_shell.js -Pattern "__cnP50CardsHtml" -SimpleMatch \| Select-Object LineNumber` | **3** líneas: definición + header + dispatcher. `node --check` NO detecta un `ReferenceError` |
| **V-11** | Registrado ANTES del fallback y con envoltorio | misma carpeta <br> `Select-String -Path static\js\multitab_shell.js -Pattern 'p50_cards"\)\|__cnCuantCardHtml\(d\);' \| Select-Object LineNumber,Line` | La línea de `p50_cards` (que contiene `cn-kpi__row`) tiene **menor** número que la de `__cnCuantCardHtml(d);` |
| **V-12** | Sin ES6 en lo añadido | misma carpeta <br> `Select-String -Path static\js\multitab_shell.js -Pattern "function __cnP50CardsHtml" -Context 0,4` | Ni `=>`, ni backtick, ni `const`, ni `let` |
| **V-13** | Cache-buster en los 2 templates | misma carpeta <br> `Select-String -Path templates\main.html,MainChat\templates\mainchat_layout.html -Pattern "multitab_shell.js') }}?v=20260908a" -SimpleMatch \| Select-Object Filename,LineNumber` | **2** resultados (`main.html:88`, `mainchat_layout.html:323`) |
| **V-14** | Plantillas | misma carpeta <br> `Select-String -Path static\js\multitab_shell.js -Pattern "cumplimiento del P50 para el mes de" -SimpleMatch` | 1 resultado |

### 6.2 Humana — la valida el USUARIO, en el servidor de PRUEBAS

> 🔴 **R3: «build verde» NO es «feature verificada».** El executor no tiene navegador. Solo el usuario marca ✅.

Requiere la BD de pruebas con REPORTE_PRESIDENT de agosto (la local está congelada en mayo). En `http://localhost:5029`, **con Ctrl+F5 la primera vez** (V-06):

| # | Acción | Esperado |
|---|---|---|
| H-1 | «¿Cuál es el cumplimiento del P50 para el mes de Agosto?» | El texto dice **«agosto de 2026»** y lleva la línea «Gap vs P50» |
| H-2 | Misma pregunta | Debajo, el panel de **5 tarjetas en fila** (Crudo, Gas, Blancos, Filiales, Total) |
| H-2b | Observar la fila en la pila del chat | Si las 5 tarjetas quedan apretadas o desbordan, **anotarlo**: la rejilla es por viewport (`colapsable.css:1221`) y un ajuste por contenedor sería un plan aparte |
| H-3 | Comparar con el panorama con agosto seleccionado | Cifras **idénticas** |
| H-4 | «cumplimiento p50 agosto» | Misma respuesta que H-1 |
| H-5 | «¿Cómo vamos contra el compromiso P50 de agosto?» | Cumplimiento de agosto, **no** el ritmo diario del mes en curso |
| H-6 | «¿Cómo va el crudo frente al P50 en agosto?» | Texto de **Crudo**; el panel muestra igualmente las 5 tarjetas |
| H-7 | «¿Cómo va el P50?» (sin mes) | La **serie anual** de siempre, sin aviso |
| H-8 | «¿Cómo quedó el P50 el mes pasado?» | Serie anual **con el aviso** «Pediste «mes pasado»…» al inicio |
| H-9 | «¿Cuál es la proyección de cierre del P50 en agosto?» | Proyección, **no** cumplimiento |
| H-10 | «¿Por qué no cumplimos el P50 en agosto?» | Análisis **causal**, no una cifra |
| H-11 | Un mes sin reporte cargado (p. ej. «diciembre») | «No tengo el compromiso P50 para **diciembre de 2026**…» — nombra el mes, no sirve otro |
| H-12 | Modal «Preguntas» → «Cumplimiento vs metas» | **8** plantillas (antes 6), total **43**, las 2 nuevas con el hueco `mes` en ámbar |
| H-13 | F12 → Console durante todo lo anterior | **0 errores** |

---

## §7. Fuera de alcance — explícito

1. **`patrones_grupo.yaml`.** Cero cambios (V-01). `precedencia_maxima:71` sigue mandando «¿cuántos campos cumplieron…?» a Cuantificar, y es correcto.
2. **Resolver «mes pasado» en la rama `referencia`.** Se **avisa** (V-07), no se resuelve: exige el mes en curso desde BD y `p50_referencia` es puro.
3. **Rama VP** (`p50_vp`, `:277-289`) y **rama DECLINAR** (`:318-348`): intactas.
4. **Endpoint `president()`** y **proxy Flask**: se consumen tal cual.
5. **`formatear_cifra_global` / `formatear_serie_anual`**: intactas.
6. **Comentario `multitab_shell.js:1278`** («30 hoy»): se queda.
7. **`login.html:43`** (prefetch con `?v=20260903i`, ya desincronizado): se queda.
8. **Ajuste de la rejilla por contenedor** en la pila del chat: solo si H-2b lo pide, y sería otro plan.
9. **Selector de mes en el panel del chat**: no. El selector vive solo en el panorama (decisión del 2026-09-08). En el chat, el mes lo fija la pregunta.
10. **`clasificacion_golden.yaml` / `run_golden.py`**: no se tocan ni se corren — la etapa A no cambia.
11. **PPTO por campo**: pendiente, ajeno.
12. **Migración `012_p50_2026_desglose.sql`** en pruebas: prerrequisito **operativo** de los datos (sin ella Filiales lee del reporte: −26,1 en vez de −25,9). **El executor NO la aplica.**

---

## Prompt para el agente EXECUTOR

```
Eres un agente EXECUTOR. Lee COMPLETO el plan
c:\APLICACIONES\ProdIA\Repo ProdIA\backend\Planes\plan_P50-CUMPLIMIENTO-MES_20260908.md
(versión v2) y ejecútalo AL PIE DE LA LETRA.

Reglas:
- CERO modificaciones fuera de lo especificado. patrones_grupo.yaml y routes/api.py NO se tocan.
- Orden secuencial de §4, empezando por el paso 0 (línea base de V-7 y V-8).
- Si un texto de LOCALIZAR no aparece EXACTAMENTE, DETENTE y reporta ancla, archivo y lo hallado.
- JS en ES5 clásico. Todo en español.
- __cnP50CardsHtml NO envuelve en .cn-kpi__row; el dispatcher SÍ (§5.10).

Reporta: ✅/❌ por cada Paso N de §4, y la tabla §6.1 completa con la salida REAL de cada
comando (no «OK»: la salida).

Al final: archivos tocados agrupados por repo (son DOS repos → dos commits) + "¿Hago commit?".
El estado que reportas es «implementado, PENDIENTE de validación humana (§6.2)» — NUNCA
«verificado» ni «completado».
```
