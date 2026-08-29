# Plan · CN-HILO-D — Hilo con timeline en el chat de Consulta

> **Versión:** v2 auditada (`CLAUDE_muestra.md` §0.2: el plan entregado ya debe ser equivalente a un v2).
> **Flujo profesional §15 ejecutado:** pasos 1-3 (Mapeo · Auditoría · Diagnóstico) en dos pasadas.
> La 2ª pasada corrigió un hallazgo de la 1ª (H-03) y descubrió tres nuevos (H-09, H-10, H-11).
> **Fecha:** 2026-08-25 · **ID:** CN-HILO-D
> **Origen del diseño:** `chat_n.md` — artboard «D · Hilo con timeline».
>
> **Aplicabilidad de `CLAUDE_muestra.md`:** describe *Robustez V2.0* (FastAPI + React 19 + pnpm).
> ProdIA 2.0 es **Flask + JS vanilla ES5 sin build step**: DT-9, DT-11, DT-13, DT-17, DT-18 y las
> reglas R1/R2 **no aplican**. Sí aplican y se han aplicado: **§0.2** (auditoría previa), **§0.3**
> (formato Planner + prompt executor), **§15**, **DT-15/R3** (build verde ≠ feature verificada — aquí
> no hay build siquiera, así que la validación es 100 % humana) y **DT-16** (grep exhaustivo antes de
> tocar algo compartido).
>
> **`chat_n.md` está escrito para otro stack** (React 19 + TS strict + react-bootstrap + Sass +
> Vitest/RTL). Este plan lo traduce. Quedan fuera por no aplicables: §3 (árbol `.tsx`), §5
> (`React.ReactNode`), §6 en JSX, §11 (Vitest/RTL) y el «≥80 % de cobertura» del §12.

---

## 1. CONTEXTO

**Proyecto:** ProdIA 2.0 — chat de analítica de producción de hidrocarburos (Ecopetrol).
**Raíz absoluta:** `c:\APLICACIONES\ProdIA\12112025_prodIA\ProdIA-2.0\ProdIA-2.0`
**Stack:** Flask `:8020` (`app.py`) + FastAPI INGESTA `:8088`. Frontend en JS vanilla servido por
Flask. **No hay bundler, ni `package.json`, ni tests de frontend.** El versionado de assets es
manual con `?v=` en las plantillas.

El chat de Consulta se pinta íntegramente por concatenación de `innerHTML` desde
`static\js\multitab_shell.js`. Piezas implicadas:

| Pieza | Ubicación (absoluta) | Papel |
|---|---|---|
| Markup del panel | `static\js\multitab_shell.js:1021-1030` | `#cn-messages` + composer Bootstrap |
| `__cnAppendRaw(role, html)` | `static\js\multitab_shell.js:4730-4745` | Crea la fila DOM y hace scroll |
| `__cnBubble(role, html)` | `static\js\multitab_shell.js:4746-4763` | Retira portada, empuja a `__cnHistory`, appendea |
| `__cnTyping()` | `static\js\multitab_shell.js:4764-4778` | Indicador efímero (NO va al historial) |
| `__cnEnableLastOpts()` | `static\js\multitab_shell.js:4788-4800` | Reactiva la desambiguación viva |
| `__cnSaludoRefresh()` | `static\js\multitab_shell.js:4915-4923` | Repinta el saludo enriquecido |
| `__cnReplay()` | `static\js\multitab_shell.js:4946-4966` | Repinta el historial al cambiar de pestaña |
| `__V2_GRUPO` | `static\js\multitab_shell.js:5063-5068` | Color/icono/label por grupo del clasificador |
| `__cnRevelar()` | `static\js\multitab_shell.js:5150-5203` | Revelado palabra a palabra sobre `<p class="v2-msg">` |
| `__cnRenderV2(d, mostrarVia)` | `static\js\multitab_shell.js:5227-5256` | **Función pura compartida por Consulta y Test Clas** |
| `__v2MarcarVotado()` | `static\js\multitab_shell.js:5260-5273` | Sustituye la franja de veredicto por regex |
| `__tcAppendRaw()` | `static\js\multitab_shell.js:5343-5355` | Fila de Test Clas — **no se toca** |
| `window.ConsultaHist` | `static\js\multitab_shell.js:6123-6140` | `snapshot` / `cargar` / `nueva` |
| Panel de Insights | `static\js\multitab_shell.js:3236-3253` | Consume `__cnRevelarDur` para entrar sincronizado |
| CSS del hilo | `static\css\colapsable.css:883-949` (`.rb-chat__*`) y `1845-1883` (`.v2-*`) | Burbujas y franja |
| Portada / estado vacío | `MainChat\static\css\acordeon.css:221-325` | Ya resuelve el «hilo vacío» del §9 del doc |
| Persistencia | `MainChat\static\js\historial.js` | Guarda `__cnHistory` en localStorage |

---

## 2. OBJETIVO

Sustituir el formato de burbujas asimétricas del chat de Consulta por un **hilo tipo timeline**:
una columna, riel vertical, avatar + nombre + hora por turno, burbujas de ancho uniforme, y el ruido
de diagnóstico fuera de la vista del usuario — **sin tocar el NLP, el enrutado ni los endpoints**, y
sin alterar Test Clas.

---

## 3. DECISIONES CERRADAS (2026-08-25)

El executor **no decide nada**. Estas respuestas del usuario **mandan sobre `chat_n.md`**:

| # | Decisión | Qué corrige del documento de origen |
|---|---|---|
| **D-1** | **El ✓/✗ se conserva**, funcional | `chat_n.md` §1 y §12 lo daban por eliminado. Es el ciclo que alimenta `/api/consulta2/veredicto` |
| **D-2** | **El badge de grupo se oculta**, pero su **color sobrevive en el globo** como traza muy suave | El doc lo mandaba entero a modo debug, sin traza |
| **D-3** | **Test Clas NO cambia** | El doc no distingue los dos chats que comparten el render |

---

## 4. HALLAZGOS DE LA AUDITORÍA (§15 pasos 2-3)

Once hallazgos. **H-09 es un bug que ya existe en producción**, descubierto al auditar C6.

### 🔴 H-01 — `__cnRenderV2` la comparten los dos chats, y el 2º parámetro ya los distingue

Solo hay dos llamadas:

- `multitab_shell.js:5025` → `__cnRenderV2(d)` — **Consulta**
- `multitab_shell.js:5396` → `__cnRenderV2(d, true)` — **Test Clas** («laboratorio: la traza SÍ se muestra»)

`mostrarVia` **ya es** el discriminador de laboratorio. D-3 se cumple sin bifurcar la función: se
renombra a `lab` y la rama `lab` devuelve **exactamente el HTML de hoy**. Todo lo nuevo cuelga del `else`.

### 🔴 H-02 — El soft de `cuantificar` es idéntico al fondo de la burbuja del usuario

`__V2_GRUPO.cuantificar.soft` = `#E9F3EC` (`multitab_shell.js:5065`).
`--rb-user-bg` = `#E9F3EC` (`colapsable.css:100`). **El mismo hex.**

La traza de D-2 **no puede ser el fondo de la burbuja**: una respuesta *cuantificar* quedaría con el
color exacto de las preguntas del usuario y el hilo perdería la distinción autor/asistente — justo
lo que el rediseño va a reforzar. → Traza = **filete lateral** (C4), nunca relleno.

### 🔴 H-09 — `__cnSaludoRefresh` puede machacar la primera pregunta del usuario *(bug preexistente)*

`multitab_shell.js:4915-4923`:

```js
function __cnSaludoRefresh() {
  if (__cnHistory.length !== 1) return;
  __cnHistory[0].html = __cnSaludoHtml();                              // ← machaca el turno 0
  var bub = mm.querySelector(".rb-chat__bot .rb-chat__bot-bubble");
  if (bub) bub.innerHTML = html;
}
```

La guarda `length !== 1` se escribió cuando **el saludo era el turno 0 del historial**. Desde
2026-08-24 el saludo **ya no se siembra** (`__cnReplay:4957` pinta la portada y retorna sin `push`).
Hoy `__cnHistory.length === 1` significa otra cosa: **el usuario acaba de enviar su primera pregunta
y la respuesta todavía no ha llegado**.

Se llama desde tres callbacks asíncronos: `:4933` (`/api/analisis/president`), `:4936` y `:4943`
(`/api/analisis/ejecutivo`). Si cualquiera resuelve dentro de esa ventana:

1. `__cnHistory[0]` —**la pregunta del usuario**— se sobrescribe con el HTML del saludo. Al cambiar
   de pestaña, `__cnReplay` repinta la pregunta convertida en saludo.
2. `historial.js:81-91` (`tituloDe`) toma el título de la conversación del primer turno `role==='user'`
   → **la conversación se guarda en localStorage con el saludo como título**.
3. El `querySelector` encuentra la burbuja de «escribiendo» (`__cnTyping` también crea
   `.rb-chat__bot > .rb-chat__bot-bubble`) e inyecta el saludo dentro del indicador de carga.

**No lo introduce este rediseño**, pero C6 iba a actualizar precisamente ese selector, lo que habría
dejado el bug vivo y más difícil de ver. Arreglo mínimo de una línea en **C0**, antes que nada.

> Nota: con el saludo fuera del historial, esta función **ya no tiene ningún caso de uso útil**; su
> única acción posible es la dañina. Eliminar el circuito completo del saludo enriquecido
> (`__cnSalDes` / `__cnSalP50` / `__cnSalEje`, `:4802-4944`) es una limpieza mayor que exige su
> propio grep DT-16 → **fuera de alcance** (§9). Aquí solo se neutraliza.

### 🟠 H-03 *(corregido en la 2ª pasada)* — Dos selectores JS dependen de las clases de la fila

`grep` de `rb-chat__(bot|user|avatar)` en `static\js` — 9 coincidencias:

| Línea | Función | Acción |
|---|---|---|
| `4735-4742` | `__cnAppendRaw` — las escribe | Se reescriben (C2) |
| `4789` | **`__cnEnableLastOpts`** → `#cn-messages .rb-chat__bot` | **Actualizar a `.cn-row--bot`** |
| `4921` | `__cnSaludoRefresh` → `.rb-chat__bot .rb-chat__bot-bubble` | **Actualizar a `.cn-row--bot .cn-bubble`** |
| `5350` | `__tcAppendRaw` (`#tc-messages`) | **No se toca** — D-3 |

> **Corrección respecto a la 1ª pasada:** la función de `:4789` es `__cnEnableLastOpts`, no
> `__cnDisableOpts`. `__cnDisableOpts` (`:4782`) busca `.cn-opt-btn`, que **no cambia**. La
> diferencia importa: lo que se rompe si se olvida no es «deshabilitar opciones viejas» sino
> **reactivar la desambiguación viva** tras un `__cnReplay` (`:4964`).

Ninguno de los dos lanza excepción: dejan de encontrar nodos en silencio.
`.rb-chat__*` **no se borra** del CSS: lo sigue usando Test Clas.

### 🟠 H-04 — Mover el check a la cabecera rompería `__v2MarcarVotado`

`multitab_shell.js:5260-5273` sustituye la franja con un regex **no-greedy hasta el primer `</div>`**,
aplicado al DOM *y* al HTML guardado en `__cnHistory`/`__tcHistory`. El aviso está en el código
(`:5207-5208`) y en el CSS (`:1869`).

`chat_n.md` §6 Paso 3 coloca el check en `.cn-row__head`, **fuera** de la burbuja: eso lo saca del
HTML que guarda el historial y deja el regex sin objetivo. → La franja `.v2-verdict` **se queda
dentro de la burbuja y sin `<div>` anidados**. Solo cambia su piel (C5).

### 🟠 H-10 — `aria-live="polite"` + revelado palabra a palabra = verborrea en lector de pantalla

`chat_n.md` §10 pide `role="log"` con `aria-live="polite"` sobre el hilo. El documento **no sabe** que
`__cnRevelar` (`:5189-5201`) reescribe `p.innerHTML` cada 12-28 ms mientras revela. Con `aria-live`
activo, un lector de pantalla anunciaría la misma respuesta decenas de veces, palabra a palabra.

→ Se implementa `role="log"` + `aria-live="polite"`, **y** `aria-busy="true"` sobre el `<p class="v2-msg">`
mientras dura el revelado, retirado en `completar()`. Sin esto, el §10 empeora la accesibilidad en
lugar de mejorarla.

### 🟡 H-05 — La hora no existe en ningún sitio

`/api/consulta2/preguntar` no devuelve hora y `__cnHistory` guarda `{role, html}` sin sello. Como
`__cnReplay` repinta desde el historial, una hora calculada al pintar mostraría la del *repintado*, y
una conversación restaurada de localStorage mostraría horas inventadas. Hay que **sellarla al crear
el turno y persistirla**.

`historial.js` serializa el item entero con `JSON.stringify` y solo lee `.role` y `.html`
(`:81-91`) → añadir campos es compatible. Lo que **no** es compatible es lo contrario: las
conversaciones ya guardadas **no tienen** `time` → el render omite el `<time>` cuando falta,
**nunca fabrica uno**.

### 🟡 H-06 — `toLocaleTimeString('es-CO')` no garantiza 24 h

`chat_n.md` §2 pide `HH:mm` 24 h en `es-CO`, pero ese locale es de 12 horas por defecto
(«8:31 p. m.»). → Formateo manual con `getHours()/getMinutes()`; el patrón ya existe en
`historial.js:93`.

### 🟡 H-11 — Con los badges fuera, `.v2-msg` deja un hueco superior

`colapsable.css:1861` → `.v2-msg { margin:8px 0 0; }`. Ese margen existía para separar el párrafo de
la fila de badges. Al eliminarlos en Consulta (C6), `.v2-msg` pasa a ser el **primer** hijo de la
burbuja y su `margin-top` se suma al `padding:10px` → 18px de aire arriba contra 10px abajo.
→ Regla `:first-child { margin-top:0 }` en el bloque nuevo (C8). No se toca `.v2-msg` global: Test
Clas la sigue necesitando con su margen.

### 🟡 H-07 — El header y el composer están acoplados a la portada

`chat_n.md` §6 Paso 1 los rediseña. En ProdIA el composer es `.chat-input-container > .input-group`
(Bootstrap, `multitab_shell.js:1022-1030`) y `acordeon.css:265-286` lo alinea con `.cn-portada`
mediante un `max-width:520px` **medido en la app** tras un intento fallido documentado
(`acordeon.css:224-233`). → **Fuera de alcance** (§9).

### 🟡 H-08 — El proyecto ya tiene sus tokens; el doc propone un juego casi idéntico

`--rb-ink #1b2a33` vs `$cn-ink #1A2A24`; `--rb-body #3d4d58` vs `$cn-body #3C4A44`;
`--rb-user-bg #E9F3EC` = `$cn-green-soft`; `--rb-chat-gold #C9962E` = `$cn-gold`.
→ Se usan **las variables vivas de `colapsable.css`**. Un segundo juego de hex a un dígito de
distancia es deuda pura. El espíritu del §2 del doc (contraste, mínimo 10.5 px, nada en `--rb-faint`
para texto) sí se respeta.

### 🟢 H-12 — `__V2_GRUPO` se declara después de `__cnAppendRaw`, y da igual

`__V2_GRUPO` está en `:5063`; `__cnAppendRaw` en `:4730` pasará a leerla. Con `var`, el
identificador está hoisteado y la **asignación** ocurre al cargar el módulo, mucho antes de que
`__cnAppendRaw` se ejecute (siempre en respuesta a un evento).
**No mover la declaración.** Se documenta para que el executor no «arregle» lo que funciona.

---

## 5. PREREQUISITOS

| # | Check | Cómo se comprueba |
|---|---|---|
| P-1 | Flask en `:8020` e INGESTA en `:8088` arrancados | `SETUP_LOCAL.md` |
| P-2 | El chat de Consulta responde hoy (línea base) | Preguntar «producción de Castilla en julio» y ver burbuja con badge de grupo |
| P-3 | Test Clas responde hoy (línea base para el diff visual) | Pestaña Test Clas → una pregunta → captura de pantalla **antes** de tocar nada |
| P-4 | Copia de seguridad de los 2 archivos a modificar | `static\js\multitab_shell.js` y `static\css\colapsable.css` |

---

## 6. INVENTARIO DE ARCHIVOS

| Archivo | Acción |
|---|---|
| `static\js\multitab_shell.js` | **Modificar** — C0, C1, C2, C3, C6, C7 |
| `static\css\colapsable.css` | **Modificar** — C8 (bloque nuevo al final; nada se borra) |
| `MainChat\static\css\acordeon.css` | **No tocar** |
| `MainChat\static\js\historial.js` | **No tocar** |
| `templates\*.html` | **No tocar** (no hay `?v=` que subir: los assets del shell se sirven sin hash) |

---

## 7. ESPECIFICACIÓN

### C0 · Neutralizar H-09 *(primero, y verificable por separado)*

`static\js\multitab_shell.js:4917`. Sustituir:

```js
    if (__cnHistory.length !== 1) return;
```

por:

```js
    // [2026-08-25 · H-09] La guarda original se escribió cuando el saludo ERA el turno 0 del
    // historial. Desde 2026-08-24 el saludo no se siembra (__cnReplay pinta la portada y retorna),
    // así que length===1 significa "el usuario ya preguntó y aún no hay respuesta": sin comprobar
    // el rol, este refresco machacaba la PREGUNTA del usuario —y con ella el título con el que
    // historial.js guarda la conversación—.
    if (__cnHistory.length !== 1 || __cnHistory[0].role !== "assistant") return;
```

### C1 · Hora sellada por turno (H-05, H-06)

Añadir junto a `__cnNombre` (`static\js\multitab_shell.js:1064`):

```js
  // [2026-08-25] Hora del turno, 24h determinista. NO se usa toLocaleTimeString('es-CO'):
  // ese locale es de 12 horas por defecto ("8:31 p. m."). Mismo patrón que historial.js:93.
  function __cnHora() {
    var f = new Date(), dd = function (n) { return (n < 10 ? "0" : "") + n; };
    return dd(f.getHours()) + ":" + dd(f.getMinutes());
  }
```

### C2 · `__cnAppendRaw` → fila de timeline

Reemplazar **íntegro** `static\js\multitab_shell.js:4729-4745` por:

```js
  // --- Hilo tipo timeline (2026-08-25): riel + avatar + cabecera de autor + burbuja ---
  // `time` y `grupo` son OPCIONALES y van al final: las 4 llamadas existentes siguen siendo
  // válidas sin tocarlas. Si `time` falta NO se pinta hora (historiales guardados antes de este
  // cambio, e indicador de "escribiendo"): jamás se fabrica una hora que no es la del turno.
  // El riel que une los turnos es un ::after del rail anulado en :last-child — se resuelve en CSS
  // y no obliga a repintar la fila anterior en cada append (chat_n.md §6 lo pasaba como prop).
  function __cnAppendRaw(role, html, time, grupo) {
    var m = el("cn-messages"); if (!m) return null;
    var esUser = (role === "user");
    var nom = esUser ? (__cnNombre() || "Tú") : "Asistente";
    var avatar = esUser
      ? '<div class="cn-avatar cn-avatar--user" aria-hidden="true">' +
        esc(nom.charAt(0).toUpperCase()) + '</div>'
      : '<div class="cn-avatar cn-avatar--bot" aria-hidden="true">' +
        '<img src="/static/img/chatbot-for-conversations.png" alt=""></div>';
    // Traza del clasificador (D-2): el color del grupo entra como variable inline y el CSS lo
    // pinta como filete lateral. NUNCA como fondo — el soft de "cuantificar" (#E9F3EC) es el
    // MISMO hex que --rb-user-bg y la burbuja del bot se confundiría con la del usuario (H-02).
    // __V2_GRUPO se declara más abajo (:5063): con `var` ya está asignada cuando esto se ejecuta (H-12).
    var g = (!esUser && grupo && __V2_GRUPO[grupo]) ? __V2_GRUPO[grupo] : null;
    var attrG = g ? ' data-g="' + esc(grupo) + '" style="--v2c:' + g.color + ';"' +
      ' title="Motor v2 · ' + esc(g.label) + '"' : "";
    var d = document.createElement("div");
    d.className = "cn-row " + (esUser ? "cn-row--user" : "cn-row--bot");
    d.innerHTML =
      '<div class="cn-row__rail">' + avatar + '</div>' +
      '<div class="cn-row__main">' +
        '<div class="cn-row__head">' +
          '<span class="cn-row__author">' + esc(nom) + '</span>' +
          (time ? '<time class="cn-row__time">' + esc(time) + '</time>' : '') +
        '</div>' +
        '<div class="cn-bubble ' + (esUser ? 'is-user' : 'is-bot') + '"' + attrG + '>' + html + '</div>' +
      '</div>';
    m.appendChild(d); m.scrollTop = m.scrollHeight; return d;
  }
```

> `m.scrollTop = m.scrollHeight` se conserva **literal**. Prohibido `scrollIntoView` (`chat_n.md`
> §6 Paso 2, y el motivo está en `multitab_shell.js:2860`).

### C3 · `__cnBubble` propaga hora y grupo al historial

En `static\js\multitab_shell.js:4746`, firma → `function __cnBubble(role, html, grupo) {`.
Sustituir las dos líneas del cuerpo (`:4757-4758`):

```js
    // [2026-08-25] El sello de hora y el grupo viajan EN el historial: __cnReplay repinta desde
    // aquí, así que calcularlos al pintar daría la hora del repintado y perdería la traza de color.
    var hora = __cnHora();
    __cnHistory.push({role: role, html: html, time: hora, grupo: grupo || null});
    var d = __cnAppendRaw(role, html, hora, grupo);
```

En `__cnReplay` (`:4962`):

```js
    __cnHistory.forEach(function (b) { __cnAppendRaw(b.role, b.html, b.time, b.grupo); });
```

En la llamada del motor v2 (`:5025`), pasar el grupo:

```js
          __cnRevelar(__cnBubble("assistant", __cnRenderV2(d), d.grupo), d.mensaje);
```

> Las otras 11 llamadas a `__cnBubble` (`:4993`, `:5015`, `:5028`, `:5046`, `:5050`, `:5057`,
> `:5992`, `:5998`, `:6017`, `:6089`) **no se tocan**: sin 3er argumento, `grupo` es `undefined`,
> la burbuja sale sin traza y eso es lo correcto — no vienen del clasificador.
> `__cnTyping` (`:4768`) tampoco se toca: sin `time`, la fila de «escribiendo» sale sin hora,
> tal como pide `chat_n.md` §9.

### C4 · Traza de color del grupo (D-2)

Ya cableada en C2 + C3. Forma visual, en el CSS de C8:

```css
.cn-bubble.is-bot[data-g]               { border-left:3px solid var(--v2c); }
.cn-bubble.is-bot[data-g="desconocido"] { border-left-color:var(--rb-line); }
```

- Fondo blanco intacto (H-02).
- `desconocido` queda en gris de línea, **sin señal de color**: coherente con `chat_n.md` §8.4
  («cuando la intención sea desconocido, no mostrárselo al usuario»).
- El `title="Motor v2 · <Grupo>"` de C2 es la traza textual del §8.2, sin ocupar un píxel.
- **Único ajuste permitido si al medirlo resulta fuerte: bajar a 2px.** Prohibido convertirlo en
  fondo (H-02) o en badge (D-2).

### C5 · Franja ✓/✗ conservada (D-1)

`__cnRenderV2` (bloque `if (d.log_id)`, `:5245-5254`), `__v2Votar`, `__v2No`, `__v2MarcarVotado` y el
`id="v2v-<log_id>"`: **sin ningún cambio estructural**. La franja sigue **dentro** de la burbuja y
**sin `<div>` anidados** (H-04). Solo se reviste en C8.

### C6 · `__cnRenderV2` en modo Consulta

`static\js\multitab_shell.js:5227` → firma `function __cnRenderV2(d, lab) {`.
**La rama `lab` (Test Clas) devuelve exactamente el HTML actual, carácter por carácter.**
La rama de Consulta omite `.v2-badge`, `.v2-grupo` y `.v2-capa`:

```js
    var h = "";
    if (lab) {   // Test Clas — laboratorio: la traza SÍ se muestra (render histórico, intacto)
      h = '<span class="v2-badge"><i class="bi bi-cpu"></i> Motor v2</span> ' +
        '<span class="v2-grupo" style="--v2c:' + g.color + ';--v2s:' + g.soft + ';">' +
        '<i class="bi bi-' + g.icon + '"></i> ' + g.label + '</span> ' +
        '<span class="v2-capa">vía ' + via + '</span>';
    }
    // Consulta: motor, grupo y capa son DIAGNÓSTICO y salen de la vista (chat_n.md §8). El grupo
    // sobrevive como filete de color en la burbuja + title (D-2, ver __cnAppendRaw).
```

El resto del cuerpo sigue igual. Tabla de lo que emite cada rama:

| Elemento | Test Clas (`lab`) | Consulta |
|---|---|---|
| `.v2-badge` «Motor v2» | ✅ | ❌ → `title` (C2) |
| `.v2-grupo` color + icono | ✅ | ❌ → filete (C4) |
| `.v2-capa` «vía regex/LLM» | ✅ | ❌ |
| `.v2-ent` entidad detectada | ✅ | ✅ **se conserva** — no es diagnóstico: dice **qué entidad entendió** el motor, y el usuario la necesita para detectar un malentendido antes de leer las cifras |
| `<p class="v2-msg">` | ✅ | ✅ **intacto** — `__cnRevelar` escribe sobre él y `white-space:pre-line` sostiene los saltos del árbol de jerarquizar |
| `.v2-verdict` ✓/✗ | ✅ | ✅ (D-1) |

`__cnErrorV2` (`:5215-5225`) **no se toca**: su `.v2-badge--err` es deliberado — un fallo debe verse
como fallo (`:1864-1865`).

### C7 · Accesibilidad: `role="log"` sin verborrea (H-10)

1. `static\js\multitab_shell.js:1021` — añadir los atributos al contenedor:

```js
      '<div class="rb-chat" id="cn-messages" style="flex:1;min-height:0;" ' +
      'role="log" aria-live="polite" aria-label="Conversación"></div>' +
```

2. `static\js\multitab_shell.js` — en `__cnRevelar`, tras `var p = nodo.querySelector(".v2-msg"); if (!p) return;`:

```js
    // [2026-08-25 · H-10] El hilo es aria-live="polite" y aquí se reescribe innerHTML cada 12-28ms:
    // sin aria-busy, un lector de pantalla anunciaría la respuesta entera decenas de veces,
    // palabra a palabra. Se retira en completar(), que SIEMPRE corre (fin normal o interrupción).
    p.setAttribute("aria-busy", "true");
```

3. Dentro de `completar()` (`:5184-5187`), como primera línea del cuerpo:

```js
      p.removeAttribute("aria-busy");
```

### C8 · CSS — bloque nuevo en `static\css\colapsable.css`

Añadir **después de la línea 949** (fin del bloque `.rb-chat`), sin borrar nada:

```css
/* ===== Hilo timeline · Chat de Consulta (2026-08-25 · CN-HILO-D) =====================
   Convive con .rb-chat__* : esas clases NO se borran porque Test Clas las sigue usando
   (#tc-messages, __tcAppendRaw). #cn-messages conserva su clase .rb-chat, así que el
   contenedor (padding 16/14/22, fondo --rb-off) y las reglas de acordeon.css sobre
   .cn-inicio > #cn-messages siguen valiendo sin tocarse. */

.cn-row { display:flex; gap:11px; margin-bottom:14px; }
.cn-row__rail { width:28px; flex:0 0 auto; display:flex; flex-direction:column; align-items:center; }
/* El riel que une turnos: nace bajo el avatar y muere en el siguiente. En :last-child NO se pinta
   (chat_n.md §6). Resuelto en CSS y no en JS: así ningún append tiene que repintar la fila previa. */
.cn-row__rail::after { content:""; flex:1; width:1.5px; background:var(--rb-line-soft); margin-top:5px; }
.cn-row:last-child .cn-row__rail::after { display:none; }
.cn-row__main { min-width:0; flex:1; padding-bottom:2px; }
.cn-row__head { display:flex; align-items:center; gap:7px; margin-bottom:4px; }
.cn-row__author { font-size:11.5px; font-weight:800; color:var(--rb-ink); }
/* Mono SOLO para la hora. --rb-body y no --rb-faint: regla de contraste dura (chat_n.md §2). */
.cn-row__time { font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace;
  font-size:10.5px; color:var(--rb-body); }

.cn-avatar { width:26px; height:26px; border-radius:50%; display:grid; place-items:center; flex:0 0 auto; }
/* Disco BLANCO con borde, no verde: el PNG del bot lleva su propio color y un fondo verde lo ensucia. */
.cn-avatar--bot { background:var(--rb-white); border:1px solid var(--rb-line); overflow:hidden; }
.cn-avatar--bot img { width:100%; height:100%; object-fit:contain; display:block; }
.cn-avatar--user { background:var(--rb-user-bg); color:var(--rb-green-mid);
  font-size:11.5px; font-weight:800; }

.cn-bubble { border-radius:11px; padding:10px 12px; font-size:12.5px; line-height:1.55; }
.cn-bubble.is-user { background:var(--rb-user-bg); border:1px solid transparent;
  color:var(--rb-ink); font-weight:500; }
.cn-bubble.is-bot  { background:var(--rb-white); border:1px solid var(--rb-line); color:var(--rb-body); }
.cn-bubble.is-bot strong { font-weight:700; color:var(--rb-ink); }
.cn-bubble.is-bot em { font-style:italic; color:var(--rb-muted); }
/* Traza del clasificador (D-2). Filete lateral y NUNCA fondo: el soft de "cuantificar" es el
   mismo #E9F3EC que --rb-user-bg. "desconocido" queda gris: no se le muestra al usuario (§8.4). */
.cn-bubble.is-bot[data-g]               { border-left:3px solid var(--v2c); }
.cn-bubble.is-bot[data-g="desconocido"] { border-left-color:var(--rb-line); }
/* .v2-msg lleva margin-top:8px para separarse de la fila de badges; en Consulta ya no hay badges
   y quedaba con 18px de aire arriba contra 10px abajo. Solo aquí: Test Clas la necesita como está. */
.cn-bubble.is-bot > .v2-msg:first-child { margin-top:0; }

@media (max-width:340px) {
  .cn-row__rail { width:22px; }
  .cn-bubble { padding:9px 11px; }
}
```

### C9 · Copy (`chat_n.md` §7) — **NO se ejecuta aquí**

El §7 pide `<strong>` en los tres temas del dominio y recortar la enumeración duplicada. El texto lo
componen plantillas Python (`respuesta_*.py`) y el marcador de negrita del chat es `⟦…⟧` → `<strong>`,
**nunca markdown `**`** (`multitab_shell.js:5087-5091`). Es un cambio de **backend** y de contenido:
tarea independiente, no se mezcla con este rediseño.

---

## 8. ORDEN DE EJECUCIÓN

| Paso | Cambio | Verificación inmediata |
|---|---|---|
| 1 | **C0** (H-09) | Preguntar y cambiar de pestaña: la pregunta sigue siendo la pregunta |
| 2 | **C8** (CSS) | Sin efecto visible todavía — el JS aún no emite las clases nuevas |
| 3 | **C1 + C2 + C3** | El hilo se ve en timeline, con hora y traza de color |
| 4 | **C6** (los 2 selectores de H-03) | Desambiguación viva reactivable tras cambio de pestaña |
| 5 | **C6** (`__cnRenderV2`) + **C4** | Consulta sin badges; **Test Clas idéntico a P-3** |
| 6 | **C5** (piel del ✓/✗) | Voto de punta a punta contra `/api/consulta2/veredicto` |
| 7 | **C7** (accesibilidad) | `aria-busy` aparece y desaparece durante el revelado |

> Los pasos 1 y 2 son independientes y reversibles por separado. **Si un paso falla, DETENERSE**:
> no seguir al siguiente ni «arreglar sobre la marcha».

---

## 9. REGLAS NO NEGOCIABLES

| # | Regla | Por qué |
|---|---|---|
| R-1 | **No borrar ninguna clase `.rb-chat__*` del CSS** | Test Clas las usa (H-03, D-3) |
| R-2 | **No tocar `__tcAppendRaw`, `__tcBubble`, `__tcReplay` ni `#tc-messages`** | D-3 |
| R-3 | **No mover `.v2-verdict` fuera de la burbuja ni anidarle `<div>`** | Rompe el regex de `__v2MarcarVotado` (H-04) |
| R-4 | **No renombrar ni envolver `<p class="v2-msg">`** | `__cnRevelar` escribe sobre él y el panel de Insights se sincroniza con `__cnRevelarDur` |
| R-5 | **No sustituir `scrollTop = scrollHeight` por `scrollIntoView`** | `multitab_shell.js:2860` explica el motivo |
| R-6 | **No mover la declaración de `__V2_GRUPO`** | Funciona por hoisting de `var` (H-12) |
| R-7 | **La traza de grupo es filete lateral, jamás fondo** | H-02 |
| R-8 | **Si falta `time`, no se pinta hora** | Nunca inventar el sello de un turno antiguo (H-05) |
| R-9 | **No tocar header ni composer** | H-07 |
| R-10 | **No declarar «completado»: esto es una feature visual** | `CLAUDE_muestra.md` DT-15 / R3 — solo el usuario la marca ✅ |

---

## 10. VALIDACIONES

**No hay tests de frontend en ProdIA 2.0.** Toda la verificación es manual, medida en Chrome sobre la
app corriendo (DT-15/R3: aquí no existe siquiera un «build verde» que dé falsa confianza).

| # | Comprobación | Resultado esperado | Origen |
|---|---|---|---|
| V-1 | Cuatro turnos seguidos | Cada uno con avatar, nombre y hora | `chat_n.md` §11.1 |
| V-2 | Burbuja de usuario / de bot | `.cn-bubble.is-user` / `.is-bot` | §11.2 |
| V-3 | Avatares | Bot = imagen en disco blanco; usuario = inicial de `USER_FIRST_NAME` | §11.3 |
| V-4 | Franja ✓/✗ presente; votar ✓ | `.v2-vdone` con «Confirmada (usuario)»; el POST a `/api/consulta2/veredicto` responde `ok` | D-1 |
| V-5 | Votar ✗ y reclasificar | Chips de los otros grupos; el voto se registra | D-1 |
| V-6 | `document.querySelectorAll('#cn-messages .v2-badge, #cn-messages .v2-grupo').length` | **`0`** | D-2 |
| V-7 | Lo mismo en `#tc-messages` | **`> 0`** — Test Clas intacto | D-3 |
| V-8 | Diff visual de Test Clas contra la captura P-3 | **Idéntico** | D-3 / R-2 |
| V-9 | `getComputedStyle($('.cn-row:last-child .cn-row__rail'), '::after').display` | `"none"`; en las demás filas, `"block"` | §11.6 |
| V-10 | Scroll tras un turno nuevo | `m.scrollTop === m.scrollHeight - m.clientHeight`. **`chat_n.md` §11.8 está mal escrito**: `scrollTop === scrollHeight` no se cumple en ningún contenedor con altura; el invariante correcto es el de `multitab_shell.js:2970` | §11.8 corregido |
| V-11 | Contraste | Ningún texto en `--rb-faint`; ningún metadato < 10.5 px | §11.9 |
| V-12 | Cambiar de pestaña y volver | Horas y traza de color **idénticas**, no recalculadas | H-05 |
| V-13 | Restaurar del historial una conversación guardada **antes** del cambio | Se pinta sin hora y sin traza, sin romperse | H-05 |
| V-14 | Respuesta larga | `__cnRevelar` anima y el bloque de Insights entra sincronizado | R-4 |
| V-15 | Durante el revelado | `.v2-msg` tiene `aria-busy="true"`; al terminar, no lo tiene | H-10 |
| V-16 | Desambiguación: preguntar algo ambiguo, cambiar de pestaña, volver | Los botones de la **última** opción siguen activos; los anteriores, deshabilitados | H-03 |
| V-17 | **H-09:** preguntar y cambiar de pestaña antes de que llegue la respuesta | La primera burbuja sigue siendo la pregunta del usuario, no el saludo | H-09 |
| V-18 | **H-09:** el historial lateral guarda esa conversación | El título es la pregunta del usuario | H-09 |
| V-19 | Consola F12 durante todo lo anterior | 0 errores | R3 |
| V-20 | Panel estrecho (< 340 px) | Riel a 22 px, burbuja a 9/11 px, estructura sin cambios | `chat_n.md` §9 |

---

## 11. FUERA DE ALCANCE

| Qué | Por qué |
|---|---|
| Header verde y composer (`chat_n.md` §6 Paso 1) | H-07: alineación con la portada medida en la app tras un fallo documentado. Alto riesgo, nulo beneficio para el problema que resuelve este rediseño |
| Test Clas | D-3 |
| Eliminar el circuito del saludo enriquecido (`:4802-4944`) | H-09 nota: limpieza mayor, exige su propio grep DT-16. Aquí solo se neutraliza el daño |
| Modo debug `?debug=1` (`chat_n.md` §8.3) | Innecesario: **Test Clas ya es el modo debug**. Si algún día se quiere, la vía barata es `localStorage.cn_debug`, con el patrón de `cn_motor` (`:5069-5072`) |
| Copy del §7 | C9: vive en el backend (`respuesta_*.py`), tarea independiente |
| React / TypeScript / Vitest / cobertura ≥ 80 % | No aplica al stack |
| Estados «error» y «vacío» del `chat_n.md` §9 | Ya existen: `__cnErrorV2` y `.cn-portada`. Rediseñarlos es otra tarea |

---

## 12. DEFINITION OF DONE

- [ ] C0 aplicado y V-17/V-18 pasan.
- [ ] Hilo en una columna con riel de 1.5 px, ausente en la última fila (resuelto en CSS).
- [ ] Cabecera por turno: nombre 11.5 px/800 + hora mono 10.5 px, sellada al crear el turno y
      persistida; ausente —sin fabricarse— en historiales antiguos.
- [ ] Avatares: imagen del bot en disco blanco; inicial del usuario derivada de la sesión.
- [ ] Burbujas radio 11 px: usuario `--rb-user-bg`, asistente blanco con borde fino.
- [ ] «Motor v2», grupo y vía **fuera** de la UI de Consulta; grupo presente solo como filete de
      color + `title`; `desconocido` sin color.
- [ ] ✓/✗ intactos y funcionando; `__v2MarcarVotado` sigue encontrando su franja.
- [ ] `.v2-msg` y `__cnRevelar` intactos; Insights sincronizado; `aria-busy` correcto.
- [ ] Test Clas con diff visual **nulo** contra P-3.
- [ ] `.rb-chat__*` conservado en el CSS.
- [ ] Las 20 validaciones del §10, medidas en la app.
- [ ] **Estado final = «PENDIENTE de validación humana» hasta que el usuario lo marque ✅** (R-10).

---

## 13. PROMPT PARA EL AGENTE EXECUTOR

```
Eres un agente EXECUTOR. Lee completo el plan
c:\APLICACIONES\ProdIA\12112025_prodIA\ProdIA-2.0\ProdIA-2.0\INGESTA\Rep_Prod\Planes\plan_hilo_timeline_chat_consulta_2026-08-25.md
y ejecútalo AL PIE DE LA LETRA.

Reglas:
- CERO modificaciones al plan. No decides nada: las decisiones están cerradas en §3.
- Respeta las 10 reglas no negociables del §9. R-1, R-2 y R-3 son las que rompen
  funcionalidad viva si se ignoran.
- Orden secuencial del §8, paso a paso. Si un paso falla, DETENTE y reporta.
- Solo se tocan 2 archivos (§6): static\js\multitab_shell.js y static\css\colapsable.css.
  Nada más. No toques MainChat\, ni templates\, ni el backend.
- No borres código: el bloque CSS del C8 se AÑADE, y las clases .rb-chat__* se quedan.
- Comentarios en español, en el estilo del archivo (explican el porqué, no el qué).
- No hay build ni tests: no reportes "build verde". Esta es una feature VISUAL, así que
  tu reporte final es "PENDIENTE de validación humana", nunca "verificada".

Reporta: ✅/❌ Paso N por cada paso del §8, con la verificación inmediata de su fila.
Al final: lista de archivos tocados + tabla de las 20 validaciones del §10 que SÍ pudiste
comprobar (y cuáles requieren navegador) + "¿Hago commit?".
```

---

## 14. REFERENCIAS

- Diseño de origen: `chat_n.md` — artboard **D · Hilo con timeline**.
- Marco de trabajo: `INGESTA\Rep_Prod\clmd\CLAUDE_muestra.md` §0.2, §0.3, §15, §17 (DT-15, DT-16), §17.5 R3.
- Antecedentes: `INGESTA\Rep_Prod\Planes\plan_chat_asimetrico_esencial_2026-07-09.md` (formato actual),
  `INGESTA\Rep_Prod\Planes\plan_clasificador_motor_q_v2_2026-07-30.md` (Motor v2, grupos, veredicto).
