# Plan SENDA-CHAT — la senda a diciembre llega al chat (ruteo + panel)

| | |
|---|---|
| **ID tarea** | SENDA-CHAT |
| **Fecha** | 2026-09-10 |
| **Versión** | v2 (auditado: 3 auditorías internas + anclas verificadas contra el archivo + patrón medido en local, 9/9 casos) |
| **Alcance** | Capa 1 del clasificador (1 patrón nuevo), rama `senda` de Analizar (emite panel), `multitab_shell.js` (refactor del pintor + registro del panel), cache-buster |
| **Qué NO se toca** | `analizar/subrouter.py` (`_FUTURO`, `_PROY`), `patrones_anclados`, `vocabulario_dominio.yaml`, `analisis/api.py`, `routes/api.py` (Flask), CSS, el tablero de Analizar (sigue pintando la senda igual) |

### Decisiones cerradas del usuario / planner

1. **La senda existe y funciona en el tablero; el chat debe responder lo mismo con gráfica.** No se construye nada nuevo de dato: se cablea lo que hay.
2. **Patrón de Capa 1 mínimo y genérico** (NO anclado). Sin `VAMOS\s+A\s+PRODUCIR` suelto ni `HASTA\s+DICIEMBRE` suelto — ver H3 y H4.
3. **El panel viaja con los datos** (`panel.datos` = respuesta cruda de `president_senda`), sin fetch desde el chat. Precedente: `p50_cards`.
4. **Un solo pintor Plotly para tablero y chat.** Se extrae el cuerpo de `__cnPaintSenda` a `__cnSendaPlotInto(plotNode, d)`; el tablero no cambia de comportamiento.
5. **El plan vive en `backend\Planes\`** aunque toque el frontend (precedente: `plan_SENDA-PROYECTADA-DIC_20260908.md`).

---

## §0. Contexto para el agente EXECUTOR

**Proyecto:** ProdIA — chat de producción de Ecopetrol. Dos procesos:

| | Ruta | Stack | Puerto |
|---|---|---|---|
| Frontend | `c:\APLICACIONES\ProdIA\Repo ProdIA\frontend\` | Flask + Jinja2 + JS ES5 | 5029 |
| Backend | `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\` | FastAPI, gestionado con `uv` | 5030 |

Cada carpeta (`frontend\`, `backend\`) es **su propio repo git**. El navegador solo habla con Flask (5029), que hace proxy al 5030.

**Archivos que se tocan (rutas absolutas):**

| # | Archivo | Qué |
|---|---|---|
| A | `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\config\patrones_grupo.yaml` | +1 patrón en `grupos.analizar` |
| B | `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\golden\clasificacion_golden.yaml` | +3 casos golden |
| C | `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\respuesta_analizar.py` | rama `senda` emite panel |
| D | `c:\APLICACIONES\ProdIA\Repo ProdIA\frontend\static\js\multitab_shell.js` | refactor pintor + registro `analiza_senda` |
| E | `c:\APLICACIONES\ProdIA\Repo ProdIA\frontend\templates\main.html` | cache-buster |
| F | `c:\APLICACIONES\ProdIA\Repo ProdIA\frontend\templates\login.html` | cache-buster (sincronizar) |

**Convenciones obligatorias:**

- JS **ES5 clásico**: `var` + `function`. Prohibido `const`, `let`, arrow functions, template literals.
- Código y comentarios **en español**. Los comentarios nuevos llevan prefijo de fecha `[2026-09-10 · SENDA-CHAT]`, como el resto del proyecto.
- Las anclas «LOCALIZAR» de este plan están **copiadas del archivo real**. Si una no se encuentra literalmente, **DETENERSE y reportar**, no adaptar.
- El YAML de patrones se compila **una sola vez al arranque** (`patrones.py:22,40-41`): tras el paso A hay que **reiniciar el backend** para que aplique.

**Cómo funciona lo que se toca (lo mínimo para no romperlo):**

1. **Capa 1 del clasificador** (`patrones.py:44-73`): normaliza (MAYÚSCULAS, sin tildes, `Ñ→N`, puntuación intacta) y prueba **todos** los regex de **todos** los grupos. Si atrapa **un solo grupo**, retorna ese (línea 65-67) **sin mirar la precedencia**. Solo con 2+ grupos aplica `precedencia_colision: [analizar, cuantificar, jerarquizar]` (línea 70-72).
2. **Filtro de dominio** (`maquina_q.py:610-621`): si el patrón que ganó **no** está en `patrones_anclados`, la pregunta necesita entidad del catálogo **o** vocabulario de producción (`vocabulario_dominio.yaml`), si no → `desconocido`. Es la protección contra «fin de año» en una frase ajena a producción.
3. **Sub-router de Analizar** (`analizar/subrouter.py:60-64`, tupla `_FUTURO`) ya devuelve `senda` para las frases de horizonte futuro. **No se toca.**
4. **Pila de paneles del chat** (`multitab_shell.js`, `__cnPintarPanelCuant` :4539): un encadenado de ternarios por `panel.tipo` produce el HTML (constructor **puro**), se inserta el bloque, y un gancho post-inserción (`:4677` → `__cnPanelMesCargar` → `__cnPanelMesPintar` :5014) localiza el host **por clase con `blk.querySelector`** y pinta Plotly. Nunca por `id`: en la pila conviven varios bloques.

---

## §1. Hallazgos de la auditoría

### 🔴 H1 — La pregunta nunca llega a Analizar; el bug es de Capa 1, no del sub-router
Medido en local (`uv run python`, proceso nuevo): `clasificar_capa1("Cuánto vamos a producir en los próximos meses hasta diciembre?")` → `('cuantificar', ['CUANT[OA]S?\\b'])`. Un solo grupo atrapa → `patrones.py:65-67` retorna antes de evaluar `precedencia_colision`. Ningún patrón de `grupos.analizar` (`patrones_grupo.yaml:221-271`) cubre «vamos a **producir**» ni frases de horizonte futuro. En cambio `subrouter.sub_intencion(...)` con la misma frase → `senda` ✅. **Determina §3.A**: hay que provocar la colisión para que gane `analizar`.

### 🔴 H2 — El bug es más ancho: 3 de los 4 casos golden de senda no llegan a Analizar
`analizar_golden.yaml:116-127` fija 4 preguntas con `sub: senda`. Pasadas por Capa 1: «¿Cuánto vamos a producir hasta diciembre?» → cuantificar ❌; «¿Cómo se ve el cierre de año?» → `None` (LLM) ❌; «¿Qué producción esperamos los próximos meses?» → cuantificar ❌; solo «¿Cuál es la proyección para lo que queda del año?» → analizar (por `PROYECCION`). `run_golden_analizar.py` evalúa **solo el sub-router**, por eso está en verde con la Capa 1 rota. **Determina §3.B**: se añaden casos al golden de **clasificación** (`clasificacion_golden.yaml`), que sí mide Capa 1.

### 🔴 H3 — `VAMOS\s+A\s+PRODUCIR` suelto crea una regresión silenciosa
Medido: «cuánto vamos a producir **este mes**» matchea esa alternativa → pasaría de cuantificar a analizar/senda, y `senda` responde los meses futuros hasta diciembre, **no el mes en curso**. Es la familia del «periodo ignorado» al revés. **Decisión: no se incluye.** La pregunta del bug entra por `PROXIMOS\s+MESES`; el golden :116 («…hasta diciembre») entra por la alternativa acotada `PRODUCIR\s+HASTA\s+DICIEMBRE` (ver H4).

### 🔴 H4 — `HASTA\s+DICIEMBRE` suelto roba el acumulado pasado
«cuánto acumulamos hasta diciembre» (año cerrado) iría a senda. `HASTA\s+AHORA`/`HASTA\s+LA\s+FECHA` son acumulado de cuantificar (`slots.py:27`). **Decisión:** solo `PRODUCIR\s+HASTA\s+DICIEMBRE` (verbo en futuro perifrástico + horizonte), nunca `HASTA\s+DICIEMBRE` a secas.

### 🔴 H5 — `__cnSendaHtml` emite un `id` fijo y `__cnPaintSenda` hace su propio fetch
`multitab_shell.js:6274` → `'<div id="cn-p50-senda-plot"></div>'`; `:6294-6452` → `__cnPaintSenda()` sin argumentos, `fetch("/api/analisis/president/senda")` en `:6296`, y pinta buscando `el("cn-p50-senda-plot")` por `getElementById`. En la pila del chat pueden coexistir dos bloques de senda → el segundo pintaría sobre el primero. Y re-fetchear es absurdo cuando `panel.datos` ya trae la serie. **Determina §3.D.1-D.3**: id → clase; cuerpo Plotly → `__cnSendaPlotInto(plotNode, d)`; `__cnPaintSenda` queda como envoltorio fetch + delegación. Call sites de `__cnPaintSenda`: **2**, `:2213` y `:3557` (grep verificado) — ninguno cambia de firma.

### 🔴 H6 — Sin gancho post-inserción, el host queda vacío **sin error**
El constructor es puro y Plotly necesita un contenedor con ancho real. El comentario de `:4675-4676` documenta exactamente esto para `p50_anual`: «Sin esta linea el host queda vacio y no se pinta nada, sin error». **Determina §3.D.5-D.6.**

### 🔴 H7 — Cache-buster desincronizado; sin subirlo el panel no pinta con consola limpia
`main.html:88` → `?v=20260908k` (el que carga); `login.html:43` → `?v=20260903i` (prefetch, **distinta URL**: hoy el prefetch no sirve). **Determina §3.E-F**: ambos a `20260910a`.

### 🟡 H8 — El envoltorio mensual da la altura que la pila no tiene
`__cnPanelMesHtml` (`:4704-4718`) envuelve en `.cp-foco > .cp-foco__panel.is-active > .cn-compprod__grid--mes`: MEDIDO el 2026-08-25 (`:4694-4697`) que sin él Plotly monta un SVG de 10 px. Se reutiliza tal cual con host `cn-senda-mes`. Llama a `__cnProdId(d.producto)` — con `producto` ausente devuelve `null` y cae al gris neutro (`:3643`, `:4705`) ✅. Pinta `d.avisos` como strings — `president_senda` devuelve `avisos: list[str]` (`api.py:2940`) ✅. En el chat **no** se repite el título «Producción equivalente G.E.» del tablero: el texto de la respuesta ya lo dice.

### 🟡 H9 — El patrón nuevo NO se ancla
Regla del usuario del 2026-08-02 (`patrones_grupo.yaml:283-291`): la palabra sola no basta, necesita producción. «fin de año» / «cierre de año» son español común. Medido: `nivel_dominio("que hacemos en la fiesta de fin de ano")` → `None` → `desconocido` ✅. La pregunta del bug da `fuerte` por `PRODUC(?:…|IR|…)` (`vocabulario_dominio.yaml:62`) ✅. Los casos golden H2 dan `fuerte` por `CIERRE` y `PRODUCCION` ✅.

### 🟡 H10 — En colisión se pierde el ancla del grupo perdedor (H-H de `patrones.py:78-81`)
«producción de Castilla en los próximos meses» hoy: cuantificar por `'PRODUCCION\s+DE'` (anclado). Con el patrón nuevo: analizar/senda, y el ancla se pierde → filtro de dominio → `PRODUCCION` da `fuerte` → pasa. La senda es corporativa (ignora la entidad); `_plantilla.senda(_s, ent_valor)` ya recibe `ent_valor`. No se cambia; se declara.

### 🟢 H11 — Colisiones nuevas contra goldens y tests: cero
Grep de las frases del patrón sobre `tests\**` y los tres goldens: los únicos hits son los 4 casos `sub: senda` de `analizar_golden.yaml:116-127`. Ningún test asserta `panel is None` para senda (grep `senda` en `tests\` → 0 resultados).

### 🟢 H12 — Contrato de datos ya alineado
`president_senda` devuelve `{anio, unidad:"kboepd", serie:[12×{mes, mes_nombre, ecopetrol, filiales, total, p50, es_real}], ultimo_mes_real, avisos, fuentes}` (`api.py:2935-2937, 3056-3062`); `__cnPaintSenda` consume exactamente `d.anio, d.unidad, d.serie[i].{…}`. Ninguna transformación.

### 🟢 H13 — Namespace libre
Grep en todo el repo: `analiza_senda`, `__cnSendaPlotInto`, `__cnSendaMesInto`, `__cnAnzSendaHtml`, `cn-senda-mes` → 0 resultados. `cn-p50-senda-plot` solo aparece en el JS (`:6274`, `:6301`), **no en CSS**: cambiar id→clase no rompe estilos.

### 🟢 H14 — Proxy Flask ya existe
`frontend\routes\api.py:279-291` sirve `/api/analisis/president/senda`. No se toca; con `panel.datos` el chat ni lo usa.

---

## §2. Estado actual

**Backend — rama senda** (`respuesta_analizar.py:474-485`, literal):
```python
    if sub == "senda":
        _s = senda_fn(anio=2026)
        _serie = (_s or {}).get("serie") or []
        _fut = [m for m in _serie if not m.get("es_real") and m.get("total") is not None]
        if not _fut:
            return {"mensaje": "No tengo la senda proyectada para el resto del año.",
                    "panel": None}
        cuerpo = _plantilla.senda(_s, ent_valor)
        intro = _intro(alcance, usuario)
        mensaje = respuesta_base.envolver(
            intro, cuerpo, "¿Quieres el detalle de un mes, o la brecha contra el P50?")
        return {"mensaje": mensaje, "panel": None}
```

**Frontend — hoy:** `__cnSendaHtml(d)` (:6270-6275) puro, con `id` fijo. `__cnPaintSenda()` (:6294-6452) fetch + inyecta + Plotly, todo en una función. Ternario de despacho termina en `:4604-4605` (`p50_cards` → fallback). Gancho `:4677`. `__cnPanelMesPintar` termina con el ramal `p50_anual` (`:5038-5041`).

**Síntoma en Pruebas (captura del usuario, 2026-09-10):** «Cuánto vamos a producir en los próximos meses hasta diciembre?» → «toda la producción de Ecopetrol produjo 0,0 kbopd de crudo en Diciembre 2026 — 0.0% del presupuesto…» + panel de un solo mes con GAP −525,8. Responde con seguridad algo que no es.

---

## §3. Especificación

### §3.A — MODIFICAR `patrones_grupo.yaml` (archivo A)

**LOCALIZAR** (líneas 270-271, literal, únicas en el archivo):
```yaml
    - 'COMO\s+VIENE'
    - '(VIENE|VA)\s+(SUBIENDO|BAJANDO|CAYENDO)'
```

**SUSTITUIR POR** (se conservan las dos líneas y se añade el bloque debajo, misma indentación de 4 espacios):
```yaml
    - 'COMO\s+VIENE'
    - '(VIENE|VA)\s+(SUBIENDO|BAJANDO|CAYENDO)'
    # [2026-09-10 · SENDA-CHAT] HORIZONTE FUTURO. La capacidad `senda` existe desde el 2026-09-08
    # (analizar/subrouter.py:60-64 `_FUTURO`, respuesta_analizar.py:474-485) pero la Capa 1 nunca
    # le entregaba la pregunta: «¿cuánto vamos a producir en los próximos meses hasta diciembre?»
    # solo disparaba 'CUANT[OA]S?\b' de cuantificar; con UN solo grupo atrapando, patrones.py:65-67
    # retorna ANTES de mirar precedencia_colision. Medido 2026-09-10: 3 de los 4 casos `sub: senda`
    # del golden de analizar no llegaban a analizar (dos a cuantificar, uno al LLM). Con este patrón
    # hay colisión y analizar gana.
    # 🔑 Las alternativas son las de `_FUTURO` VERBATIM (mismo texto normalizado). Si `_FUTURO`
    #    cambia, cambiar aquí también.
    # 🔑 NO lleva 'VAMOS\s+A\s+PRODUCIR' suelto: «cuánto vamos a producir ESTE MES» es cuantificar
    #    (mes en curso) y senda respondería los meses futuros — el bug del periodo ignorado al revés.
    #    Y «vamos a cerrar/llegar/alcanzar» son de _PROY (pace del mes), fijados por 4 tests
    #    (test_analizar.py:30, test_analizar_tendencia.py:64, test_p50_referencia.py:32, y el
    #    golden :18/:131).
    # 🔑 NO lleva 'HASTA\s+DICIEMBRE' suelto: «cuánto acumulamos hasta diciembre» (año cerrado) es
    #    ACUMULADO de cuantificar (slots.py:27). Solo con el verbo delante: PRODUCIR HASTA DICIEMBRE.
    # NO se ancla (fuera de patrones_anclados): «cierre de año» y «fin de año» son español común
    # (la fiesta de fin de año, el cierre contable). Verificado 2026-09-10:
    # nivel_dominio("que hacemos en la fiesta de fin de ano") es None → el filtro de dominio de
    # maquina_q.py:613-621 la manda a desconocido, que es lo correcto. Anclarlo repetiría el error
    # del 2026-08-02 ('META\b', 'COMO VAMOS'). La pregunta del bug pasa el filtro por PRODUCIR
    # (vocabulario_dominio.yaml:62).
    - '(RESTO\s+DEL\s+ANO|LO\s+QUE\s+(QUEDA|RESTA)\s+DEL\s+ANO|PROXIMOS\s+MESES|SIGUIENTES\s+MESES|MESES\s+QUE\s+VIENEN|MESES\s+RESTANTES|CIERRE\s+DEL?\s+ANO|FIN(AL)?\s+DEL?\s+ANO|HASTA\s+FIN(AL)?\s+DE\s+ANO|DE\s+AQUI\s+A\s+(DICIEMBRE|FIN\s+DE\s+ANO)|PRODUCIR\s+HASTA\s+DICIEMBRE)'
```

**NO tocar** `patrones_anclados` (líneas 278-340) ni `precedencia_colision` (línea 276).

### §3.B — MODIFICAR `clasificacion_golden.yaml` (archivo B)

**LOCALIZAR** (líneas 295-296, literal, final del archivo):
```yaml
- pregunta: "¿Cuánto llevamos este mes?"
  esperado: desconocido
```

**SUSTITUIR POR** (se conservan las dos líneas y se añade debajo):
```yaml
- pregunta: "¿Cuánto llevamos este mes?"
  esperado: desconocido

# ---- Senda / horizonte futuro (2026-09-10 · SENDA-CHAT) ----
# CUANTO + horizonte futuro colisionan y gana analizar (precedencia_colision). Antes solo
# atrapaba cuantificar y la senda a diciembre nunca se respondía. Los negativos fijan que el
# mes en curso y el acumulado pasado siguen en cuantificar (H3/H4 del plan SENDA-CHAT).
- pregunta: "¿Cuánto vamos a producir en los próximos meses hasta diciembre?"
  esperado: analizar
- pregunta: "¿Cómo se ve el cierre de año?"
  esperado: analizar
- pregunta: "¿Qué producción esperamos los próximos meses?"
  esperado: analizar
# NEGATIVOS
- pregunta: "¿Cuánto vamos a producir este mes?"
  esperado: cuantificar
- pregunta: "¿Cuánto crudo acumulamos hasta diciembre?"
  esperado: cuantificar
```

> Nota del planner: el negativo lleva «crudo» a propósito. Sin vocabulario de producción, `run_golden.py` (que pasa por `clasificar` y el filtro de dominio) lo mandaría a `desconocido` con o sin este plan — mediría el filtro, no el patrón. Medido 2026-09-10.

### §3.C — MODIFICAR `respuesta_analizar.py` (archivo C)

**LOCALIZAR** (líneas 481-485, literal, únicas):
```python
        cuerpo = _plantilla.senda(_s, ent_valor)
        intro = _intro(alcance, usuario)
        mensaje = respuesta_base.envolver(
            intro, cuerpo, "¿Quieres el detalle de un mes, o la brecha contra el P50?")
        return {"mensaje": mensaje, "panel": None}
```

**SUSTITUIR POR:**
```python
        cuerpo = _plantilla.senda(_s, ent_valor)
        intro = _intro(alcance, usuario)
        mensaje = respuesta_base.envolver(
            intro, cuerpo, "¿Quieres el detalle de un mes, o la brecha contra el P50?")
        # [2026-09-10 · SENDA-CHAT] El panel viaja con la respuesta cruda del endpoint, igual que
        # `p50_cards` con /analisis/president: el frontend ya sabe pintarla (__cnSendaPlotInto) y
        # no hay que re-fetchear lo que ya está en la mano. Antes devolvía `panel: None` y la
        # senda salía solo como texto — la gráfica existía, pero solo en el tablero.
        return {"mensaje": mensaje, "panel": {"tipo": "analiza_senda", "datos": _s}}
```

### §3.D — MODIFICAR `multitab_shell.js` (archivo D)

Cinco ediciones, **en este orden** (las funciones nuevas antes que sus call sites).

#### D.1 — `__cnSendaHtml`: id → clase

**LOCALIZAR** (líneas 6270-6275, literal):
```js
  function __cnSendaHtml(d) {
    if (!d || !d.serie || !d.serie.length) { return ""; }
    return '<div class="cn-p50hd__lbl"><i class="bi bi-graph-up-arrow"></i> Producción equivalente G.E. ' +
           esc(String(d.anio || "")) + ' <span class="cn-p50hd__u">· real cerrado, proyectado y meta P50</span></div>' +
           '<div id="cn-p50-senda-plot"></div>';
  }
```

**SUSTITUIR POR:**
```js
  function __cnSendaHtml(d) {
    if (!d || !d.serie || !d.serie.length) { return ""; }
    // [2026-09-10 · SENDA-CHAT] CLASE, no id: la senda ahora también se pinta en la pila del chat,
    // donde pueden convivir dos bloques de senda — con id fijo el segundo pintaría sobre el primero.
    return '<div class="cn-p50hd__lbl"><i class="bi bi-graph-up-arrow"></i> Producción equivalente G.E. ' +
           esc(String(d.anio || "")) + ' <span class="cn-p50hd__u">· real cerrado, proyectado y meta P50</span></div>' +
           '<div class="cn-p50-senda-plot"></div>';
  }
```

#### D.2 — Extraer el pintor Plotly a `__cnSendaPlotInto(plotNode, d)`

**LOCALIZAR** (líneas 6294-6308, literal — cabecera de `__cnPaintSenda` hasta `var C = __CN_SENDA_COL;` inclusive):
```js
  function __cnPaintSenda() {
    var host = el("cn-p50-senda"); if (!host) return;
    fetch("/api/analisis/president/senda")
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var host2 = el("cn-p50-senda"); if (!host2) return;
        host2.innerHTML = __cnSendaHtml(d);
        var plotNode = el("cn-p50-senda-plot");
        if (!plotNode || !window.Plotly || !d || !d.serie || !d.serie.length) { return; }
        // Purga antes de dibujar: si el nodo ya tuvo un gráfico (dos montajes de la misma
        // vista), Plotly.newPlot sobre un nodo usado no libera el trazo anterior por sí solo —
        // es el mismo riesgo de fuga que el comentario del contenedor advierte.
        try { window.Plotly.purge(plotNode); } catch (e) { /* nodo nuevo: nada que purgar */ }

        var C = __CN_SENDA_COL;
```

**SUSTITUIR POR:**
```js
  // [2026-09-10 · SENDA-CHAT] Pintor PURO de Plotly sobre un nodo ya insertado en el DOM. Antes
  // este cuerpo vivía dentro del .then() de __cnPaintSenda, atado al fetch y al id fijo del
  // tablero; ahora lo comparten el tablero (__cnPaintSenda, que sigue haciendo el fetch) y la
  // pila del chat (__cnSendaMesInto, que recibe los datos en panel.datos y no fetchea nada).
  // Una sola función = una sola paleta, un solo layout, un solo sitio donde arreglar.
  function __cnSendaPlotInto(plotNode, d) {
        if (!plotNode || !window.Plotly || !d || !d.serie || !d.serie.length) { return; }
        // Purga antes de dibujar: si el nodo ya tuvo un gráfico (dos montajes de la misma
        // vista), Plotly.newPlot sobre un nodo usado no libera el trazo anterior por sí solo —
        // es el mismo riesgo de fuga que el comentario del contenedor advierte.
        try { window.Plotly.purge(plotNode); } catch (e) { /* nodo nuevo: nada que purgar */ }

        var C = __CN_SENDA_COL;
```

> ⚠️ El cuerpo que sigue (desde `var meses = [], ecp = [], …` en la línea 6309 hasta `{ displayModeBar: false, responsive: true });` en la 6446) **NO se toca ni se re-indenta**. Queda tal cual dentro de la nueva función.

#### D.3 — Cerrar `__cnSendaPlotInto` y reescribir `__cnPaintSenda` como envoltorio

**LOCALIZAR** (líneas 6445-6452, literal — cierre actual de `__cnPaintSenda`):
```js
        window.Plotly.newPlot(plotNode, [trazaEcp, trazaFil, trazaTot, trazaP50], layout,
          { displayModeBar: false, responsive: true });
      })
      .catch(function () {
        var host3 = el("cn-p50-senda");
        if (host3) host3.innerHTML = '<div class="cn-p50hd__na">No se pudo cargar la senda proyectada.</div>';
      });
  }
```

**SUSTITUIR POR:**
```js
        window.Plotly.newPlot(plotNode, [trazaEcp, trazaFil, trazaTot, trazaP50], layout,
          { displayModeBar: false, responsive: true });
  }

  // 🟢 Plotly YA está vendorizado y cargado global (base.html:33) — NUNCA descargar ni crear
  // otro <script>, H5/H12 del plan.
  // 🔴 NO se llama desde window.__cnP50CambiarMes: cambiar de mes solo repinta #cn-p50-row
  // (decisión ya vigente para el resto del tablero, comentario de :6026); la senda es la del
  // AÑO completo y no depende del mes elegido en el selector.
  // [2026-09-10 · SENDA-CHAT] Ahora es solo el ENVOLTORIO del tablero: fetch + inyectar el
  // markup + delegar el dibujo a __cnSendaPlotInto. Misma firma y mismos 2 call sites que
  // antes (:2213, :3557); el tablero no cambia de comportamiento.
  function __cnPaintSenda() {
    var host = el("cn-p50-senda"); if (!host) return;
    fetch("/api/analisis/president/senda")
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var host2 = el("cn-p50-senda"); if (!host2) return;
        host2.innerHTML = __cnSendaHtml(d);
        __cnSendaPlotInto(host2.querySelector(".cn-p50-senda-plot"), d);
      })
      .catch(function () {
        var host3 = el("cn-p50-senda");
        if (host3) host3.innerHTML = '<div class="cn-p50hd__na">No se pudo cargar la senda proyectada.</div>';
      });
  }

  // [2026-09-10 · SENDA-CHAT] Constructor PURO del panel de senda en la PILA del chat. Reusa el
  // envoltorio mensual (__cnPanelMesHtml): es el que da altura al grid en la pila — MEDIDO el
  // 2026-08-25 (:4694-4697) que sin él Plotly monta un SVG de 10 px sin lanzar error. `producto`
  // no existe en la senda (es corporativa, con gas convertido): __cnProdId(undefined) devuelve
  // null y el envoltorio cae al gris neutro (:3643, :4705). Los `avisos` del endpoint son
  // strings y el envoltorio ya los pinta.
  function __cnAnzSendaHtml(d) {
    if (!d || !d.serie || !d.serie.length) return "";
    return __cnPanelMesHtml(d, "cn-senda-mes");
  }

  // Pintor diferido del panel de senda en la pila (se llama desde __cnPanelMesPintar, con el
  // bloque ya conectado). Sin el título del tablero: el texto de la respuesta ya lo dice.
  function __cnSendaMesInto(hostEl, d) {
    hostEl.innerHTML = '<div class="cn-p50-senda-plot"></div>';
    __cnSendaPlotInto(hostEl.querySelector(".cn-p50-senda-plot"), d);
  }
```

> ⚠️ El comentario de 5 líneas que hoy precede a `__cnPaintSenda` (líneas 6289-6293, «🟢 Plotly YA está vendorizado…» hasta «…elegido en el selector.») queda **duplicado** encima de `__cnSendaPlotInto` tras D.2. **Borrar esas 5 líneas originales** (6289-6293) — el bloque D.3 ya las reubica encima del envoltorio, que es a quien aplican.

#### D.4 — Registrar el tipo en el ternario de despacho

**LOCALIZAR** (líneas 4604-4605, literal):
```js
             : (panel.tipo === "p50_cards")        ? '<div class="cn-kpi__row">' + __cnP50CardsHtml(d) + '</div>'
             : __cnCuantCardHtml(d);
```

**SUSTITUIR POR:**
```js
             : (panel.tipo === "p50_cards")        ? '<div class="cn-kpi__row">' + __cnP50CardsHtml(d) + '</div>'
             // [2026-09-10 · SENDA-CHAT] "analiza_senda" (Analizar/senda): barra apilada ECP+Filiales
             // real+proyectado con línea P50, la misma del tablero. Constructor PURO; los datos
             // (respuesta cruda de /analisis/president/senda) ya viajan en panel.datos. Registrado
             // ANTES del fallback por la razón de siempre: __cnCuantCardHtml NO valida el tipo y
             // pintaría una tarjeta KPI leyendo campos que este contrato no tiene.
             : (panel.tipo === "analiza_senda")    ? __cnAnzSendaHtml(d)
             : __cnCuantCardHtml(d);
```

#### D.5 — Gancho post-inserción

**LOCALIZAR** (línea 4677, literal):
```js
    if (panel.tipo === "cuant_serie" || panel.tipo === "cuant_var" || panel.tipo === "cuant_acum" || panel.tipo === "analiza_tend" || panel.tipo === "cuant_cmp" || panel.tipo === "cuant_serie_ppto" || panel.tipo === "p50_anual") __cnPanelMesCargar(blk, d, panel.tipo);
```

**SUSTITUIR POR:**
```js
    // [2026-09-10 · SENDA-CHAT] +analiza_senda: Plotly, mismo pintor diferido.
    if (panel.tipo === "cuant_serie" || panel.tipo === "cuant_var" || panel.tipo === "cuant_acum" || panel.tipo === "analiza_tend" || panel.tipo === "cuant_cmp" || panel.tipo === "cuant_serie_ppto" || panel.tipo === "p50_anual" || panel.tipo === "analiza_senda") __cnPanelMesCargar(blk, d, panel.tipo);
```

#### D.6 — Ramal en `__cnPanelMesPintar`

**LOCALIZAR** (líneas 5038-5042, literal):
```js
    } else if (tipo === "p50_anual") {
      var hpa = blk.querySelector(".cn-p50an-mes");
      if (hpa) __cnP50AnualInto(hpa, d);
    }
  }
```

**SUSTITUIR POR:**
```js
    } else if (tipo === "p50_anual") {
      var hpa = blk.querySelector(".cn-p50an-mes");
      if (hpa) __cnP50AnualInto(hpa, d);
    } else if (tipo === "analiza_senda") {
      var hsd = blk.querySelector(".cn-senda-mes");
      if (hsd) __cnSendaMesInto(hsd, d);
    }
  }
```

### §3.E — MODIFICAR `main.html` (archivo E)

**LOCALIZAR** (línea 88, literal):
```html
<script src="{{ url_for('static', filename='js/multitab_shell.js') }}?v=20260908k"></script>
```
**SUSTITUIR POR:**
```html
<script src="{{ url_for('static', filename='js/multitab_shell.js') }}?v=20260910a"></script>
```

### §3.F — MODIFICAR `login.html` (archivo F)

**LOCALIZAR** (línea 43, literal):
```html
    <link rel="prefetch" href="{{ url_for('static', filename='js/multitab_shell.js') }}?v=20260903i">
```
**SUSTITUIR POR:**
```html
    <link rel="prefetch" href="{{ url_for('static', filename='js/multitab_shell.js') }}?v=20260910a">
```

---

## §4. Orden de ejecución

| Paso | Archivo | Acción | Verificación inmediata |
|---|---|---|---|
| 1 | A `patrones_grupo.yaml` | §3.A | `uv run python -c "import yaml,pathlib;yaml.safe_load(pathlib.Path('app/features/consulta_v2/config/patrones_grupo.yaml').read_text(encoding='utf-8'));print('YAML OK')"` → `YAML OK` |
| 2 | B `clasificacion_golden.yaml` | §3.B | mismo tipo de carga → sin error |
| 3 | C `respuesta_analizar.py` | §3.C | `uv run python -c "import app.features.consulta_v2.respuesta_analizar;print('IMPORT OK')"` → `IMPORT OK` |
| 4 | D `multitab_shell.js` | D.1 → D.2 → D.3 (incluye borrar 6289-6293) → D.4 → D.5 → D.6 | ver §6.1 (sintaxis) |
| 5 | E `main.html` | §3.E | grep `20260910a` → 1 hit |
| 6 | F `login.html` | §3.F | grep `20260910a` → 1 hit |
| 7 | — | Validación estática §6.1 completa | todo verde |
| 8 | — | Reiniciar **ambos** backends (el YAML se compila al arranque) | `/health` del 5030 responde |

Los pasos 1-3 son del repo `backend\`; 4-6 del repo `frontend\`. **Dos commits**, uno por repo.

---

## §5. Reglas no negociables

1. **CERO cambios fuera de §3.** En particular: no tocar `_FUTURO` ni `_PROY` en `subrouter.py`; no tocar `patrones_anclados`; no tocar `vocabulario_dominio.yaml`; no tocar el CSS.
2. **JS ES5 clásico**: `var` + `function`. Sin `const`/`let`/arrow/template literals.
3. **Anclas literales.** Si un «LOCALIZAR» no aparece exactamente, DETENERSE y reportar el archivo y la línea esperada. No adaptar.
4. **No re-indentar** el cuerpo Plotly (6309-6446) al moverlo a `__cnSendaPlotInto`. Queda con su indentación actual; es válido y minimiza el diff.
5. **Ambos cache-busters al mismo valor** `20260910a`.
6. **Nunca medir `president_senda` importándolo en proceso** (CLAUDE.md §7: los defaults `Query(...)` falsean). Lo que se mide en local es la Capa 1 y el sub-router, que son código puro.
7. Todo comentario nuevo **en español** con prefijo `[2026-09-10 · SENDA-CHAT]`.

---

## §6. Validación

### §6.1 Estática (la hace el executor, en local, sin BD)

Carpeta: `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\`. Línea por línea, PowerShell normal.

| # | Comando | Esperado |
|---|---|---|
| V1 | `uv run python -c "from app.features.consulta_v2.patrones import clasificar_capa1 as c; print(c('Cuánto vamos a producir en los próximos meses hasta diciembre?')[0]); print(c('¿Cuánto vamos a producir hasta diciembre?')[0]); print(c('¿Cómo se ve el cierre de año?')[0]); print(c('¿Qué producción esperamos los próximos meses?')[0])"` | 4 líneas: `analizar` |
| V2 | `uv run python -c "from app.features.consulta_v2.patrones import clasificar_capa1 as c; print(c('¿Cuánto vamos a producir este mes?')[0]); print(c('¿Cuánto acumulamos hasta diciembre?')[0]); print(c('¿Cuánto produjimos hasta diciembre del año pasado?')[0]); print(c('Cómo vamos a cerrar el mes?')[0])"` | `cuantificar`, `cuantificar`, `cuantificar`, `analizar` |
| V3 | `uv run python -c "from app.features.consulta_v2.maquina_q import clasificar; r=clasificar('Cuánto vamos a producir en los próximos meses hasta diciembre?', log=False); print(r)"` | contiene `analizar` (no `desconocido`) |
| V4 | `uv run python -c "from app.features.consulta_v2.maquina_q import clasificar; print(clasificar('qué hacemos en la fiesta de fin de año', log=False))"` | contiene `desconocido` (el filtro de dominio la rechaza) |
| V5 | `uv run python -c "from app.features.consulta_v2.analizar import subrouter as s; print(s.sub_intencion('Cuánto vamos a producir en los próximos meses hasta diciembre?')); print(s.sub_intencion('¿vamos a cerrar el crudo?'))"` | `senda`, `proyeccion` |
| V6 | `uv run pytest tests/test_consulta_v2_clasificador.py tests/test_analizar.py tests/test_analizar_tendencia.py tests/test_p50_referencia.py -q` | todo passed (los 10 fallos preexistentes documentados no están en estos archivos) |
| V7 | `$env:PYTHONPATH='.'; uv run python app/features/consulta_v2/golden/run_golden.py` | `EXACTITUD … (gate: >=90%)` ≥ 90 %, y los 5 casos nuevos en `OK` |
| V8 | `$env:PYTHONPATH='.'; $env:CONSULTA_ANALIZA_LLM='false'; uv run python app/features/consulta_v2/golden/run_golden_analizar.py` | ≥ 90 %, sin fallos nuevos |
| V9 | `$env:PYTHONPATH='.'; uv run python app/features/consulta_v2/golden/run_golden_cuantificar.py` | ≥ 90 %, sin fallos nuevos |

Carpeta: `c:\APLICACIONES\ProdIA\Repo ProdIA\frontend\`.

| # | Comando | Esperado |
|---|---|---|
| V10 | `node -e "new Function(require('fs').readFileSync('static/js/multitab_shell.js','utf8'));console.log('JS OK')"` | `JS OK` (sintaxis). Si `node` no existe, abrir el archivo en el navegador vía la app y F12 → Console sin `SyntaxError` |
| V11 | `Select-String -Path static\js\multitab_shell.js -Pattern 'id="cn-p50-senda-plot"'` | **0** resultados |
| V12 | `Select-String -Path static\js\multitab_shell.js -Pattern '__cnPaintSenda\(' \| Measure-Object` | **3** (definición + :2213 + :3557) |
| V13 | `Select-String -Path static\js\multitab_shell.js -Pattern 'analiza_senda' \| Measure-Object` | **4** (ternario D.4, gancho D.5, ramal D.6, y el comentario de D.4 cuenta 1 más → aceptar 4 o 5) |
| V14 | `Select-String -Path static\js\multitab_shell.js -Pattern 'Plotly YA está vendorizado' \| Measure-Object` | **1** (el duplicado de 6289-6293 se borró) |
| V15 | `Select-String -Path templates\main.html,templates\login.html -Pattern '20260910a' \| Measure-Object` | **2** |

Fallo en cualquiera → DETENERSE y reportar.

### §6.2 Humana (la hace el usuario, en el **servidor de pruebas**)

Tras `git pull` en ambos repos y reiniciar ambos backends. Abrir `http://localhost:5029/mainchat`, **Ctrl+F5**, F12 → Console.

| # | Acción | Esperado |
|---|---|---|
| H-1 | Preguntar: `Cuánto vamos a producir en los próximos meses hasta diciembre?` | Texto: intro + meses proyectados sep..dic con brecha contra el P50. **Panel**: barra apilada verde (real ene-ago) + ámbar rayado (sep-dic) con línea Meta P50, igual al del tablero. Console: 0 errores |
| H-2 | Preguntar: `¿Cómo se ve el cierre de año?` | Misma respuesta + mismo panel |
| H-3 | Preguntar dos veces seguidas H-1 | **Dos** bloques de senda en la pila, ambos pintados (no uno vacío) |
| H-4 | Preguntar: `Cómo vamos a cerrar el mes?` | Sigue respondiendo el **pace del mes en curso** (no la senda) |
| H-5 | Preguntar: `¿Cuánto vamos a producir este mes?` | Cuantificar, mes en curso (no la senda) |
| H-6 | Tablero de Analizar (Insights, vista global) | La senda del tablero se pinta igual que antes del cambio |
| H-7 | Cambiar de pestaña y volver | El panel de senda de la pila sigue pintado |

Si H-1 pinta el texto pero el panel sale en blanco con consola limpia: primero `Ctrl+F5` y comprobar en Network que `multitab_shell.js?v=20260910a` es el que cargó; después medir la altura del host `.cn-senda-mes` (H8).

**Estado al terminar el executor: «implementado, PENDIENTE de validación humana».** Solo el usuario marca ✅.

---

## §7. Fuera de alcance

- **«¿Cuál es la proyección para lo que queda del año?»** (golden analizar :119) sigue cayendo a `desconocido` por `regex+filtro`: `PROYECCION` no está en el vocabulario de dominio ni anclado, y la frase no nombra la producción. Hoy tampoco funciona; arreglarlo es añadir `PROYECCION` al vocabulario fuerte, decisión del usuario (regla 2026-08-02).
- **Senda por entidad** (una VP, un activo): `president_senda` es corporativa. La entidad solo llega a la plantilla de texto. No se cambia.
- **Ranking de cumplimiento % por activo** y **P50 por activo** (preguntas 3 y 6 de la lista del usuario): planes aparte.
- **Composición «MTD real + proyección de días restantes = cierre del mes vs P50»**: no existe y no se construye aquí.
- **Unificar `id="cn-p50-senda"` (host del tablero)**: sigue siendo id porque en el tablero hay un solo host; solo el nodo del plot pasa a clase.
- Migración a Azure: la hace el usuario con el skill `migrar-a-azure`, después de la validación humana.
