# Plan ejecutable v2 (auditado) — Saludo del chat anclado al panel (3 etapas)

> **v2 = v1 + auditoría del propio plan contra el código (§1.2).** El diseño se confirmó en 3 puntos
> críticos (orden de render, ancla del PASO 4, gate de E2) y se corrigió en 1: **la copia decía
> «corte al día 17» sobre un campo que es un CONTEO de días, no una fecha** (AS4).


> **Niveles del documento de referencia: entrada 3 → salida 3.** Ninguno se descarta: el Nivel 1 es
> la base que SIEMPRE se ve, y los Niveles 2 y 3 lo enriquecen cuando sus datos llegan. Ninguno
> bloquea el pintado del saludo.

---

## §1 · Contexto

Al abrir la pestaña **Consulta**, el panel derecho ya muestra el **Desempeño del mes global**
(`__cnAnalizar(null)`, `static/js/multitab_shell.js:373`), pero el saludo del chat habla del chat en
abstracto («Pregúntame por una entidad…»). El usuario está leyendo instrucciones de uso con un
tablero lleno de números al lado.

Este plan ancla el saludo a lo que el usuario está viendo.

### §1.1 · Auditoría — hallazgos con evidencia

| # | Hallazgo | Evidencia | Consecuencia |
|---|---|---|---|
| **S1** 🔴 | **Cuando el saludo se pinta NO hay ningún número.** `__cnReplay` lo compone de forma **síncrona** con el historial vacío; los datos llegan después, por dos fetches. | `multitab_shell.js:3156-3165` vs `:1389` (`__cnAnalisisEjecutivo`) y `:1393` (`fetch /api/analisis/desempeno`) | «Los números ya existen en el JSON del panel» es cierto **un segundo más tarde**. Obliga a **mejora progresiva**: pintar ya, enriquecer después. Nunca esperar. |
| **S2** 🔴 | **`focos` (y con ellos los nombres de los campos detractores) nacen dentro de `/analisis/ejecutivo`**, el endpoint del LLM. | `analisis/api.py:1936` (`"focos": _focos(...)` dentro de `ejecutivo`, línea 1619) | El Nivel 3 **no puede** ser la vía principal: quedaría rehén de Gemma (arranque en frío de ~342 s, el mismo camino que da 502). Se degrada a **tercera etapa opcional**. |
| **S3** 🔴 | **Dos vocabularios de estado con umbrales distintos.** El chat usa `Alineado/Rezagado/Foco` (`_estado`: ok≥90); el panel usa `En meta/Ajustado/Actuar` (`_estado_cierre`, umbral ámbar configurable). | `consulta/ejecucion.py:15`, `analisis/api.py:635` y `:650` | Un 96,8% es **«Alineado» para el chat** y **«Ajustado» para el panel**. Si el saludo dice «ajustado» y la tarjeta de respuesta dice «Alineado» del mismo número, es el defecto D5 otra vez. **DECISIÓN: el saludo dice el NÚMERO, nunca el veredicto.** Así no necesita umbral y no puede contradecir a nadie. Además evita duplicar el umbral en JS (dos implementaciones de la misma regla derivan). |
| **S4** 🟠 | **`__cnHistory` guarda HTML ya renderizado**; `__cnReplay` repinta desde ahí. | `:3125`, `:3166-3167` | Parchear solo el DOM haría que el saludo **revierta** al cambiar de pestaña y volver. Hay que reescribir también `__cnHistory[0].html`. |
| **S5** 🟠 | **«por qué Cajua está corto» no es una intención soportada.** `extraccion.py` extrae entidad/producto/periodo/nivel/agregación; no hay intención causal. | `consulta/extraccion.py` | Resolvería CAJUA y devolvería su producción, no un porqué. **DECISIÓN: el ejemplo dinámico conserva el nombre real del foco pero con forma contestable — «producción de CAJUA».** Mismo efecto («el chat ya vio tus datos») sin enseñar una forma que se responde mal. |
| **S6** 🟠 | El encabezado del panel va en **kbpe** (`/analisis/president`) y el resto en bbl/MSCF; ya divergen en pantalla (105,9 % del chat vs 114 % del anillo). | bitácora 2026-07-27 y 07-29 | **DECISIÓN: nada de kbpe en el saludo.** Sería estrenar una tercera unidad en los primeros 3 segundos, y exigiría un tercer fetch. |
| **S7** ✅ | El contrato del foco está cerrado: `{producto, entidades:[campo,…], es_ok, tipo, peso_relativo_pct, estado_label, …}`; `entidades` son los campos detractores nombrados. | `analisis/api.py:1491-1497`; consumido en `__cnFocosHtml` | El Nivel 3 tiene un camino exacto: primer foco con `!es_ok` y `entidades.length` → `entidades[0]`. |
| **S8** ✅ | `__cnDesempCache` guarda el payload por clave. | `:1392` | En la **segunda** visita de la sesión el Nivel 2 aparece de inmediato (sin esperar red). |
| **S9** ⚠️ | El ejemplo de la huella («qué información hay de X») está en el saludo **a propósito**: es su única puerta de entrada desde que se quitó el botón. | comentario en `:3159-3160` | **No se puede perder** al reescribir el saludo. |

### §1.2 · Auditoría v2 — verificaciones sobre el propio plan

| # | Verificación | Resultado | Consecuencia |
|---|---|---|---|
| **AS1** ✅ | **¿El saludo existe cuando E1/E2 pueden dispararse?** `renderPanelBody()` (que llama a `__cnReplay` → siembra el saludo) se invoca **antes** que `renderViewer()` (que llama a `__cnAnalizar` → dispara E1/E2), en los dos call sites. | `:410-411` y `:501-502` | El orden es favorable **incluso en la ruta de caché**, que es síncrona: cuando E1 corre, `__cnHistory.length` ya vale 1. El diseño se sostiene. **Se añade validación S-V13.** |
| **AS2** ✅ | **¿El ancla del PASO 4 existe y cubre las dos rutas?** `function __cnPaintEjec(d) {` en `:2071`, invocada desde la caché (`:2048`) y desde el fetch (`:2063`). | ídem | Enganchar dentro de la función cubre ambas. Confirmado. |
| **AS3** ✅ | **¿`__cnPanelEntidad` ya tiene su valor cuando corre el gate de E2?** Se asigna en `:1357` y `__cnAnalisisEjecutivo` se llama en `:1389`. | ídem | El gate lee el valor correcto. |
| **AS4** 🟠 | **`dias_con_data` NO es el día del corte**, es el **conteo de días con dato**. Coinciden solo si el mes no tiene huecos — y el módulo de Densidad documenta 38 huecos históricos. | `analisis/api.py:619-620`; `densidad` §1 | Decir «corte al día 17» sería **falso** en un mes con un hueco (16 días con dato, corte el 17). **Copia corregida a «17 de 31 días reportados»**, que además es el lenguaje que ya usa el pie de la tarjeta. |
| **AS5** ✅ | **`__cnHistory` no se limpia nunca** (`:857`, declarado una vez). | ídem | El saludo se siembra una sola vez por carga de página, y `__cnSaludoCtx`/`__cnSaludoEj` sobreviven al cambio de pestaña. Además el diseño **se autorrepara**: si por lo que sea E1 corriera antes del saludo, la asignación de `__cnSaludoCtx` persiste y `__cnSaludoHtml()` la recoge al sembrarlo. |
| **AS6** ⚠️ | En la **segunda** visita a la pestaña con conversación ya iniciada, `renderViewer` llama a `__cnReanalizar()` (entidad), no a `__cnAnalizar(null)`. | `:371-372` | E1 queda **correctamente bloqueado** por el gate `esGlobal` — el saludo no debe mostrar las cifras de una entidad. El `ctx` enriquecido de la primera carga se conserva. Sin acción. |

---

## §2 · Objetivo

Que el saludo del chat: (a) hable de lo que el usuario tiene delante, (b) aparezca **inmediatamente**
sin esperar ningún fetch, (c) se enriquezca con las cifras del mes cuando lleguen y con el nombre del
foco real si el ejecutivo resuelve, y (d) sobreviva al cambio de pestaña. **Máximo 3 líneas.**

---

## §3 · Prerequisitos

- Repo en `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA`, rama `main`.
- Commit `319514a` presente. Node para `node --check` y el harness.
- No se requieren backends ni base de datos para las validaciones automáticas.

---

## §4 · Inventario de archivos

| Ruta | Acción |
|---|---|
| `…\static\js\multitab_shell.js` | 4 ediciones (constructor del saludo + 3 enganches) |
| `…\templates\main.html` | cache-buster (líneas 5 y 82) |

**Cero backend. Cero CSS nuevo** (se reusa el markup de burbuja existente).

---

## §5 · Especificación

### 5.1 · Las 3 etapas

| Etapa | Cuándo | Fuente | Qué cambia |
|---|---|---|---|
| **E0** | síncrona, al pintar el saludo | — | Nivel 1: ancla al panel. **Siempre visible.** |
| **E1** | cuando resuelve `/analisis/desempeno` (sin LLM) | `d.mes`, `d.por_producto` | Sustituye la frase de contexto por el corte y los % del mes |
| **E2** | cuando resuelve `/analisis/ejecutivo` (con LLM) | `d.focos` | Sustituye el ejemplo por el nombre del campo detractor real |

Si E1 o E2 no llegan (red, Gemma caído, timeout), el saludo se queda en la etapa anterior y **sigue
siendo correcto**. Ninguna etapa bloquea a la anterior.

### 5.2 · Copia

**E0** (`ctx` y `ej` iniciales):
> ¡Hola Javier! A la derecha tienes el **desempeño del mes** de toda la producción ECP.
> Puedo profundizar en cualquier cosa que veas ahí: un producto, un campo, un activo o una fecha. Ej.: *«producción de Rubiales»*.
> También *«qué es CPO-09»* o *«qué información hay de Rubiales»*.

**E1** reemplaza la 1.ª línea (slot `ctx`):
> ¡Hola Javier! A la derecha tienes **mayo con 17 de 31 días reportados**: crudo 96,8 % · gas 101,9 % · blancos 100,1 %.

*(Solo números — S3. Los productos sin `cumplimiento` se omiten de la lista.)*
🔴 **AS4 · NO decir «corte al día 17»:** `dias_con_data` es el **conteo** de días con dato, no el día
del calendario. En un mes con un hueco serían 16 con dato y corte el 17 → la frase mentiría.
«17 de 31 días reportados» es exacto y es el lenguaje que ya usa el pie de la tarjeta de respuesta.

**E2** reemplaza el ejemplo (slot `ej`):
> …Ej.: *«producción de CAJUA»*.

### 5.3 · PASO 1 — Constructor + estado. Insertar **justo antes** de `function __cnReplay() {`:

```js
  // ===== [2026-07-30] Saludo anclado al panel (mejora progresiva, 3 etapas) =====
  // S1 · El saludo se pinta ANTES de que exista ningún número (los fetches del panel arrancan
  // después), así que sale ya en su forma base y se enriquece cuando los datos llegan. Ninguna
  // etapa bloquea a la anterior: si el fetch falla, el saludo anterior sigue siendo correcto.
  // S4 · __cnHistory guarda HTML renderizado -> cada etapa reescribe __cnHistory[0].html, o el
  // saludo revertiría al cambiar de pestaña y volver.
  var __cnSaludoCtx = null;   // null = frase base; string = frase con las cifras del mes (E1)
  var __cnSaludoEj  = null;   // null = ejemplo base; string = nombre del foco real (E2)

  function __cnSaludoHtml() {
    var n = __cnNombre();
    var hola = n ? ("¡Hola " + esc(n) + "! ") : "¡Hola! ";
    var ctx = __cnSaludoCtx ||
      'A la derecha tienes el <strong>desempeño del mes</strong> de toda la producción ECP.';
    var ej = __cnSaludoEj || "Rubiales";
    // S9 · el ejemplo de la huella NO se puede perder: es su única puerta de entrada (ya no hay botón).
    return hola + '<span id="cn-saludo-ctx">' + ctx + '</span>' +
      '<br>Puedo profundizar en cualquier cosa que veas ahí: un producto, un campo, un activo o una ' +
      'fecha. Ej.: <em>«producción de <span id="cn-saludo-ej">' + esc(ej) + '</span>»</em>.' +
      '<br>También <em>«qué es CPO-09»</em> o <em>«qué información hay de Rubiales»</em>.';
  }

  // Repinta el saludo in situ (DOM) y en el historial. Solo actúa si el saludo es la ÚNICA burbuja:
  // enriquecer retroactivamente un saludo con conversación encima sería ruido.
  function __cnSaludoRefresh() {
    if (__cnHistory.length !== 1) return;
    __cnHistory[0].html = __cnSaludoHtml();
    var c = el("cn-saludo-ctx"), e = el("cn-saludo-ej");
    if (c && __cnSaludoCtx) c.innerHTML = __cnSaludoCtx;
    if (e && __cnSaludoEj) e.textContent = __cnSaludoEj;
  }

  // E1 · cifras del mes desde el payload DETERMINISTA de /analisis/desempeno (sin LLM).
  // S3 · Se dice el NÚMERO, nunca el veredicto: "Alineado" (chat, ok>=90) y "Ajustado" (panel,
  // umbral ámbar) discrepan para el mismo 96,8%, y replicar el umbral en JS lo empeoraría.
  function __cnSaludoDesdeDesemp(d) {
    var m = (d || {}).mes || {}, pp = (d || {}).por_producto || [];
    if (!m.nombre) return;
    var partes = pp.filter(function (p) { return p.cumplimiento != null; })
                   .map(function (p) {
                     return String(p.producto).toLowerCase() + " " +
                            String(p.cumplimiento).replace(".", ",") + "%";
                   });
    // AS4 · "N de M días reportados", NUNCA "corte al día N": dias_con_data es un CONTEO, no el día
    // del calendario; con un hueco en el mes serían 16 con dato y corte el 17. Además es el mismo
    // lenguaje del pie de la tarjeta de respuesta ("lleva 17 de 31 días con curva diaria").
    var corte = m.completo
      ? ("<strong>" + esc(m.nombre) + " " + (m.anio || "") + "</strong>, mes cerrado")
      : ("<strong>" + esc(m.nombre) + " con " + (m.dias_con_data || "?") + " de " +
         (m.dias_del_mes || "?") + " días reportados</strong>");
    __cnSaludoCtx = "A la derecha tienes " + corte +
      (partes.length ? ": " + esc(partes.join(" · ")) + "." : ".");
    __cnSaludoRefresh();
  }

  // E2 · nombre del campo detractor REAL. S7: primer foco con !es_ok y entidades. S5: el ejemplo
  // conserva la forma «producción de X», que el chat SÍ sabe responder — "por qué X está corto"
  // no es una intención soportada (extraccion.py no tiene intención causal).
  function __cnSaludoDesdeEjec(d) {
    var f = ((d || {}).focos || []).filter(function (x) {
      return !x.es_ok && x.entidades && x.entidades.length;
    })[0];
    if (!f) return;                       // nada que nombrar → el saludo se queda como está
    __cnSaludoEj = f.entidades[0];
    __cnSaludoRefresh();
  }
```

### 5.4 · PASO 2 — E0. En `__cnReplay`, **reemplazar** el bloque del saludo actual
(desde el comentario `// El ejemplo de la huella…` hasta el cierre del `push`, hoy líneas 3157-3165) por:

```js
      __cnHistory.push({role: "assistant", html: __cnSaludoHtml()});
```

*(Las variables locales `n` y `saludo` de ese bloque quedan sin uso: eliminarlas.)*

### 5.5 · PASO 3 — E1. En `function __cnPaintDesemp(d, entidad, esGlobal, soloComp) {`, insertar
**inmediatamente después** de `__cnDesempData = d;`:

```js
    if (esGlobal) __cnSaludoDesdeDesemp(d);   // E1: el saludo se ancla a las cifras del mes
```

### 5.6 · PASO 4 — E2. En `function __cnPaintEjec(d) {`, insertar como **primera línea del cuerpo**:

```js
    if (!__cnPanelEntidad && !__cnEsFil()) __cnSaludoDesdeEjec(d);   // E2: solo el panel GLOBAL
```

*(Se engancha en `__cnPaintEjec` y no en el `.then` del fetch porque así cubre también la ruta de
caché, que no vuelve a pedir.)*

### 5.7 · PASO 5 — Cache-buster en `templates\main.html` (líneas 5 y 82):
`?v=20260730a1` → `?v=20260730b1`.

---

## §6 · Orden de ejecución

1. PASO 1 (constructor + 3 funciones). 2. PASO 2 (E0). 3. PASO 3 (E1). 4. PASO 4 (E2).
5. PASO 5 (cache-buster). 6. Validaciones §8. **No hacer commit.**

---

## §7 · Reglas no negociables

1. **El saludo se pinta SIN esperar ningún fetch** (S1). Prohibido volver `__cnReplay` asíncrono o
   condicionar el `push` a que haya datos.
2. **Cada etapa reescribe `__cnHistory[0].html`** (S4), no solo el DOM.
3. **El saludo NO dice palabras de estado** — ni «alineado», ni «ajustado», ni «en meta» (S3).
   Solo números. Prohibido replicar los umbrales de `_estado`/`_estado_cierre` en JS.
4. **Nada de kbpe** ni un tercer fetch a `/analisis/president` (S6).
5. **El ejemplo dinámico usa la forma «producción de X»** (S5). Prohibido «por qué X está corto».
6. **Se conservan los ejemplos de «qué es CPO-09» y «qué información hay de Rubiales»** (S9).
7. **Máximo 3 líneas** en cualquier etapa.
8. `__cnSaludoRefresh` solo actúa con `__cnHistory.length === 1`.
9. E1 solo con `esGlobal`; E2 solo con panel global (`!__cnPanelEntidad && !__cnEsFil()`).
10. Cero backend, cero LLM propio, cero CSS nuevo.

---

## §8 · Validaciones (ejecutar y reportar salida literal)

1. `node --check static/js/multitab_shell.js` → sin errores.
2. **Harness node** en el scratchpad (`test_saludo.js`), extrayendo del archivo REAL. Como
   `__cnSaludoRefresh` toca el DOM, el harness prueba el **constructor y los extractores** con
   `__cnHistory` y `el()` simulados (stub que devuelve `null`).

   | # | Caso | Esperado |
   |---|---|---|
   | S-V1 | `__cnSaludoHtml()` sin enriquecer | Contiene `desempeño del mes`, `producción de Rubiales`, `qué es CPO-09` y `qué información hay de Rubiales` |
   | S-V2 | 3 líneas | El HTML contiene exactamente **2** `<br>` |
   | S-V3 | E1 con mes en curso (17/31) y 3 productos | `ctx` contiene `mayo con 17 de 31 días reportados` y `crudo 96,8% · gas 101,9% · blancos 100,1%` |
   | **S-V3b** | **AS4 · antimentira** | El HTML **NO** contiene la cadena `corte al día` en ninguna etapa |
   | **S-V13** | **AS1 · orden** | Simulando la secuencia real (`__cnReplay()` y DESPUÉS `__cnSaludoDesdeDesemp(d)`), `__cnHistory[0].html` acaba con las cifras. Y en la secuencia invertida (E1 antes del saludo) el saludo **también** sale enriquecido (autorreparación, AS5) |
   | S-V4 | E1 con `mes.completo:true` | Dice `mes cerrado`, **no** «corte al día» |
   | S-V5 | E1 con un producto sin `cumplimiento` | Ese producto **no** aparece en la lista |
   | S-V6 | **S3 · sin veredictos** | El HTML resultante **no** contiene `alineado`, `ajustado`, `en meta`, `rezagado` ni `foco` (case-insensitive) |
   | S-V7 | E2 con `focos` que traen un `!es_ok` con `entidades` | El ejemplo pasa a `producción de CAJUA` |
   | S-V8 | E2 con `focos` todos `es_ok` | El ejemplo **no cambia** (sigue Rubiales) |
   | S-V9 | E2 con `focos: []` o payload de error | No lanza excepción y el saludo no cambia |
   | S-V10 | **S4 · historial** | Tras E1, `__cnHistory[0].html` **contiene** la frase nueva |
   | S-V11 | gate | Con `__cnHistory.length === 3`, E1 **no** modifica `__cnHistory[0].html` |
   | S-V12 | no regresión | `test_respuesta_datos.js` y `test_invitacion.js` siguen verdes |

   Si una aserción falla, **NO ajustarla para que pase**: reportar el fallo.
3. **Navegador (usuario)** — es lo único que verifica el parcheo real del DOM:
   (a) abrir Consulta y comprobar que el saludo aparece **de inmediato** en su forma base;
   (b) al segundo o dos, que la primera línea cambia a las cifras del mes;
   (c) cuando termine el análisis ejecutivo, que el ejemplo pasa a un campo real;
   (d) cambiar a otra pestaña del riel y volver: **el saludo enriquecido debe mantenerse**;
   (e) hacer una pregunta y comprobar que el saludo ya no se toca.

---

## §9 · Fuera de alcance

- La afirmación fuerte del Nivel 3 («X e Y explican el N % del faltante»). El dato existe
  (`foco.peso_relativo_pct`, `foco.entidades`), pero no cabe en 3 líneas. **Decisión declarada, no
  enterrada:** si se quiere, es una cuarta línea o sustituye a la de ejemplos.
- Intención causal en el chat («por qué X está corto») — `extraccion.py` + `maquina.py`, otro plan.
- La divergencia kbpe vs bbl del encabezado (S6).
- Warm-up de Ollama en 139: sigue pendiente y es lo que hace que E2 tarde en llegar.
