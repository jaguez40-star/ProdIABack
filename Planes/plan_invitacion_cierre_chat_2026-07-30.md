# Plan ejecutable v2 (auditado) — Invitación de cierre en la respuesta del chat (texto plano)

> **Variantes: entrada 3 → salida 3.** Ninguna se descarta. **La variante B cambia de redacción**
> respecto de la aprobada: la auditoría demostró que su primera cláusula duplica, palabra por palabra
> y en el 100 % de los casos, una frase que la tarjeta ya pinta (§1.1 AI1). **Requiere tu visto bueno.**
>
> **v2 = v1 + auditoría contra el código.** El v1 daba por buena la copia aprobada sin comprobar qué
> dice ya la tarjeta dos líneas más arriba.

---

## §1 · Contexto

La burbuja del chat de Consulta que responde una consulta de producción termina hoy en el pie
(«Proyección del cierre del mes…») y los avisos. No invita a seguir. El usuario pidió una oración
final que ofrezca **otro producto** (crudo/gas/blancos) o **otro tema** del panel derecho
(diferidas, mantenimientos, EBITDA-NOPAT).

El rediseño «Titular + métricas» de esa burbuja se entregó el 2026-07-29 (commit `8d971c2`,
`plan_respuesta_datos_chat_2026-07-29.md`). Este plan **añade un elemento al final de esa misma
tarjeta**; no rehace nada de lo anterior.

### §1.1 · Auditoría — hallazgos con evidencia

| # | Hallazgo | Evidencia | Consecuencia |
|---|---|---|---|
| **AI1** 🔴 | **La variante B duplica la tarjeta.** Su primera cláusula («CASTILLA solo reporta crudo este periodo») dice lo mismo que la frase que la tarjeta ya emite (`"No reporta " + mudos + " en el periodo."`). Y la duplicación es **inevitable**: ambas se disparan con la MISMA condición `mudos.length > 0`. | `static/js/multitab_shell.js:3343`. Render real de CASTILLA: `…Cerraría por encima de la meta (105,9%). **No reporta GAS ni BLANCOS en el periodo.** Proyección del cierre…` + invitación `**CASTILLA solo reporta crudo este periodo.** ¿Miramos…` | **B se reformula** (§5.1). Se descartó quitar la frase de la tarjeta: es una declaración de honestidad del dato y desaparecería cada vez que la rotación sirviera la variante C. |
| **AI2** 🟠 | La validación V3 del v1 («dos llamadas seguidas devuelven variantes distintas») **falla por diseño** cuando el conjunto tiene una sola variante (caso C solo). | §5.1, conjunto `[C]` | V3 se acota a los conjuntos de 2 (§8). |
| **AI3** 🟠 | `__daInvitaN` es **global a la sesión**, no por entidad: la variante que se ve depende de cuántas respuestas hubo antes. Es lo correcto para rotar, pero hace el render **no determinista respecto del payload**. | diseño del contador | El harness debe **resetear el contador** antes de cada aserción, o compara contra un estado que arrastra. Se documenta. |
| **AI4** 🟠 | Con B reformulada, cada tema necesita **su artículo** (`las` diferidas / `los` mantenimientos / `el` EBITDA-NOPAT), no solo el posesivo. La variante A sí sigue usando el posesivo (`sus diferidas`). | copia aprobada de A vs B reformulada | El registro lleva **dos** campos: `pos` (para A) y `art` (para B). |
| **AI5** ⚠️ | La cola de la tarjeta pasa a tener **4 párrafos** (cierre + pie + avisos + invitación). Con los avisos D-A4 —que son largos, p. ej. APIAY— la cola se vuelve densa. | `ejecucion.py:193-196` | Se respeta la posición pedida (última). Queda anotado como observación, no como cambio. |
| **AI6** ✅ | **La promesa de la variante A sí está respaldada hoy.** `intent.producto` existe y `ejecutar()` filtra por producto, así que «producción de gas de CUPIAGUA» devuelve el gas de verdad. | `consulta/ejecucion.py:160-166` | A es la única variante cuya oferta es real hoy. No hace falta matizarla. |
| **AI7** ✅ | `__cnRespuestaHtml` tiene **un solo** call site y el historial se repinta desde HTML ya generado (`__cnHistory`), no re-ejecutando la función. | `:3469` y `__cnBubble` `:3125` | La rotación avanza exactamente una vez por respuesta. El plan es válido. |
| **AI8** ✅ | El ancla del PASO 2 existe literal (2 líneas). | `:3350-3351` | — |
| **AI9** ✅ | `otros.length > 0` **junto con** `mudos.length > 0` (3 productos, 2 vivos, 1 mudo) dispara A, que **no** duplica nada. | lógica de §5.1 | Solo B necesitaba corrección. |

### §1.2 · Hallazgos heredados del análisis previo (siguen vigentes)

| # | Hallazgo | Evidencia | Consecuencia |
|---|---|---|---|
| **H1** 🔴 | **El chat NO arrastra la entidad entre preguntas.** `_PARCIAL` solo guarda un intent *parcial* mientras hay desambiguación abierta y se borra al resolver. | `consulta/maquina.py:30`, `:206` | Un seguimiento como «diferidas» o «gas» a secas muere con *«No identifiqué ninguna entidad»*. **La frase DEBE nombrar la entidad.** Es la regla que sostiene la redacción. |
| **H2** 🟠 | Los 4 módulos del panel **están en construcción**. | confirmado por el usuario | **Decisión del usuario (2026-07-30):** se ofrecen igual — *«no es mentir, estamos desarrollando y dejar el mock de respuesta completo es parte del desarrollo»*. Se implementa con un interruptor por tema. |
| **H3** 🟠 | No existe slot de «tema» en la extracción. | `consulta/extraccion.py` | Si el usuario toma la invitación, hoy recibe la respuesta de producción de siempre. No es error; falta la capa. **Fuera de alcance.** |
| **H4** 🟠 | «Comportamiento diario» es la pill que **ya está abierta** en el panel cuando el usuario lee la frase. | captura del usuario | Se **excluye** de la lista. Quedan 3 temas. |
| **H5** ✅ | El dato contextual ya está calculado: el array `mudos`. | `:3343` | Sin backend ni fetch nuevo. |
| **H6** ✅ | La rama B (filial) sale por su propia rama antes de la tarjeta (D4). | `__cnRespuestaHtml` | Las filiales **no** llevan invitación. |
| **H7** ⚠️ | `master_prompts.yaml` lo lee el chatbot legacy; Consulta no tiene yaml; y este texto **no es un prompt**. | `config/master_prompts.yaml` | La plantilla va en el frontend. |

---

## §2 · Objetivo

Añadir, como **último elemento dentro de la tarjeta de respuesta**, una oración en **texto plano**
(⚠️ **sin botones** — decisión explícita del usuario) que invite a continuar, con la entidad nombrada,
rotando entre 3 variantes y adaptándose a qué productos reporta la entidad.

---

## §3 · Prerequisitos

- Repo en `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA`, rama `main`.
- El commit `8d971c2` presente (`git log --oneline | grep 8d971c2`): se edita `__cnRespuestaHtml`
  **en su forma posterior a ese commit**.
- Node para `node --check` y el harness. No se requieren backends ni base de datos.

---

## §4 · Inventario de archivos

| Ruta absoluta | Acción |
|---|---|
| `…\static\js\multitab_shell.js` | 2 inserciones (helpers antes de `__cnRespuestaHtml` + 2 líneas y el `return`) |
| `…\static\css\colapsable.css` | 1 regla nueva al final |
| `…\templates\main.html` | cache-buster (líneas 5 y 82) |

**Cero backend.** No se toca `ejecucion.py`, `maquina.py`, `extraccion.py`, `narracion.py`,
`master_prompts.yaml` ni ningún endpoint.

---

## §5 · Especificación

### 5.1 · Las 3 variantes

**A · la entidad reporta otros productos además del titular** — *sin cambios, aprobada:*
> Puedo correr esto mismo para el gas o los blancos de CUPIAGUA, o entrar en sus diferidas, mantenimientos o EBITDA-NOPAT.

**B · 🔴 REFORMULADA (AI1)** — se dispara cuando `mudos` no está vacío:
> ~~CASTILLA solo reporta crudo este periodo.~~ ¿Miramos las diferidas, los mantenimientos o el EBITDA-NOPAT de CASTILLA?

*Se elimina la primera cláusula porque la tarjeta ya dice «No reporta GAS ni BLANCOS en el periodo»
dos líneas arriba, siempre. La entidad se traslada al final para no perder la regla H1.*

**C · genérica, siempre verdadera** — *sin cambios, aprobada:*
> ¿Seguimos con otro ángulo de CASTILLA? Diferidas, mantenimientos o EBITDA-NOPAT.

**Selección y rotación:**
- Otros productos vivos → conjunto `[A, C]`.
- Sin otros productos **y** `mudos` no vacío → conjunto `[B, C]`.
- Sin otros productos **y** `mudos` vacío → conjunto `[C]`.
  🔑 **Por qué:** `lineas` puede traer un solo producto porque el usuario pidió ese producto
  (`intent.producto`), no porque la entidad no reporte los demás. `mudos` no vacío es la única prueba
  de que los otros callan.
- Rotación con contador (`__daInvitaN++`), **no `Math.random()`**: no repite dos veces seguidas y el
  repintado del historial es estable. ⚠️ AI3: el contador es **de sesión**, no por entidad.

### 5.2 · PASO 1 — Helpers. Insertar en `static\js\multitab_shell.js` **justo antes** de
`function __cnRespuestaHtml(resp) {` (a continuación del bloque `__daTitular`, mismo IIFE):

```js
  // ===== [2026-07-30] Invitación de cierre de la respuesta (TEXTO PLANO, sin botones) =====
  // Registro declarativo de los temas del panel derecho. `disponible` es el interruptor: los módulos
  // están EN CONSTRUCCIÓN y se ofrecen igual (decisión del usuario 2026-07-30 — el mock completo es
  // parte del desarrollo); si alguna vez hay que esconder uno, se apaga aquí y la copia no se toca.
  // "comportamiento diario" NO está en la lista a propósito (H4): es la pill que YA está abierta en
  // el panel cuando el usuario lee la frase, y ofrecer lo que está en pantalla resta credibilidad.
  // Dos campos de concordancia (AI4): `pos` para la variante A ("sus diferidas") y `art` para la B
  // ("las diferidas, los mantenimientos o el EBITDA-NOPAT de X").
  var __DA_TEMAS = [
    { id: "diferidas", label: "diferidas",      pos: "sus", art: "las", disponible: true },
    { id: "manten",    label: "mantenimientos", pos: "sus", art: "los", disponible: true },
    { id: "ebitda",    label: "EBITDA-NOPAT",   pos: "su",  art: "el",  disponible: true }
  ];
  var __DA_PROD_ART = { CRUDO: "el crudo", GAS: "el gas", BLANCOS: "los blancos" };
  var __daInvitaN = 0;   // rotación DETERMINISTA de sesión (ver §5.1 y AI3)

  function __daLista(xs) {            // ["a","b","c"] -> "a, b o c"
    if (!xs.length) return "";
    if (xs.length === 1) return xs[0];
    return xs.slice(0, -1).join(", ") + " o " + xs[xs.length - 1];
  }
  function __daCap(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : s; }

  // 🔑 H1 · La entidad va NOMBRADA a propósito: el chat NO la arrastra entre preguntas
  // (maquina._PARCIAL se borra al resolver), así que un seguimiento como «diferidas» a secas moriría
  // en la extracción con "No identifiqué ninguna entidad". Nombrarla hace que el seguimiento natural
  // del usuario sí resuelva. NO se usan botones: decisión explícita del usuario (2026-07-30).
  // 🔑 AI1 · La variante B NO repite "solo reporta X este periodo": la tarjeta ya lo declara arriba
  // (linea "No reporta ... en el periodo"), y con la MISMA condición mudos.length -> era duplicación
  // garantizada, no ocasional.
  function __daInvitacion(resp, t, vivos, mudos) {
    var temas = __DA_TEMAS.filter(function (x) { return x.disponible; });
    var otros = vivos.filter(function (l) { return l !== t; })
                     .map(function (l) { return __DA_PROD_ART[String(l.producto).toUpperCase()]; })
                     .filter(Boolean);
    if (!temas.length && !otros.length) return "";
    var ent = esc(resp.entidad || "");
    var labels = temas.map(function (x) { return x.label; });
    var v = [];
    if (otros.length) {                                   // A
      v.push("Puedo correr esto mismo para " + __daLista(otros) + " de " + ent +
        (temas.length ? ", o entrar en " + temas[0].pos + " " + __daLista(labels) : "") + ".");
    } else if (mudos.length && temas.length) {            // B (solo si mudos lo respalda)
      v.push("¿Miramos " +
        __daLista(temas.map(function (x) { return x.art + " " + x.label; })) + " de " + ent + "?");
    }
    if (temas.length) {                                   // C
      v.push("¿Seguimos con otro ángulo de " + ent + "? " + __daCap(__daLista(labels)) + ".");
    }
    if (!v.length) return "";
    return v[(__daInvitaN++) % v.length];
  }
```

### 5.3 · PASO 2 — Pintarla. En `__cnRespuestaHtml`, **antes** del `return` final
(hoy líneas 3350-3351, empieza por `return '<div class="cn-answer da" style="--da-st:'`), insertar:

```js
    // Invitación de cierre: último elemento de la tarjeta, debajo del pie y los avisos.
    var invita = __daInvitacion(resp, t, L.filter(__daVivo), mudos);
    var invitaHtml = invita ? '<p class="da__invita">' + invita + '</p>' : "";
```

y **reemplazar esas dos líneas del `return`** por:

```js
    return '<div class="cn-answer da" style="--da-st:' + S.color + ';--da-st-soft:' + S.soft + '">' +
      head + headline + grid + bloqueOtros + pieCierre + pieNota + av + invitaHtml + '</div>';
```

> `mudos` y `L` ya están declarados más arriba en la misma función (`var`, alcance de función);
> no hay que recalcularlos ni moverlos.

### 5.4 · PASO 3 — CSS. Añadir **al final** de `static\css\colapsable.css`:

```css
/* [2026-07-30] Invitación de cierre de la respuesta del chat (texto plano, sin botones).
   Va debajo del pie y los avisos, y queda justo encima de la fila "Analizar el <Nivel> X" que
   __cnRender concatena después — adyacencia buscada. Cursiva y 11.5px para que se lea como
   invitación y no compita con las cifras. Respeta la regla de contraste del rediseño: nada
   <=12px por debajo de #3C4A44. */
.da__invita { margin:9px 0 0; padding-top:9px; border-top:1px dashed #E4EAE6; font-size:11.5px;
  font-style:italic; color:#3C4A44; line-height:1.45; }
```

### 5.5 · PASO 4 — Cache-buster en `templates\main.html` (líneas 5 y 82):
`?v=20260729q2` → `?v=20260730a1`.

---

## §6 · Orden de ejecución

1. PASO 1 (helpers). 2. PASO 2 (2 líneas + `return`). 3. PASO 3 (CSS). 4. PASO 4 (cache-buster).
5. Validaciones §8. **No hacer commit.**

---

## §7 · Reglas no negociables

1. **Texto plano.** Cero `<button>`, cero `cn-opt-btn`, cero `rb-chat__options` en la invitación.
   No tocar `__cnOptsOpen` ni `__cnDisableOpts`: son la maquinaria de la desambiguación viva y
   engancharse a ellas rompería el zoom D-D5.
2. **La entidad SIEMPRE nombrada** en la oración (H1). Una variante sin `ent` es un defecto.
3. **La variante B solo si `mudos.length > 0`**, y **sin** la cláusula «solo reporta X» (AI1).
4. **No se toca la línea 3343** (`"No reporta … en el periodo."`): es la declaración de honestidad
   del dato y debe seguir apareciendo aunque la rotación sirva otra variante.
5. **Sin LLM y sin fetch.** Coherente con la decisión D2 del plan anterior.
6. **Rama B (filial), `!resp.aplica` y el caso `!t` no llevan invitación.**
7. No inventar variantes nuevas ni reescribir A y C.

---

## §8 · Validaciones (ejecutar y reportar salida literal)

1. `node --check static/js/multitab_shell.js` → sin errores.
2. **Harness node** en el scratchpad, extendiendo `test_respuesta_datos.js` y extrayendo del archivo
   REAL. ⚠️ **Resetear `__daInvitaN` antes de cada aserción** (AI3), o el resultado arrastra estado.

   | # | Caso | Resultado esperado |
   |---|---|---|
   | V1 | CUPIAGUA (crudo titular, gas y blancos vivos) | Contiene `Puedo correr esto mismo para el gas o los blancos de CUPIAGUA` |
   | V2 | CASTILLA (solo crudo, `mudos`=[GAS,BLANCOS]) | Contiene `¿Miramos las diferidas, los mantenimientos o el EBITDA-NOPAT de CASTILLA?` |
   | **V2b** | **CASTILLA (AI1, antiduplicación)** | El HTML **NO** contiene `solo reporta`, y `No reporta` aparece **exactamente 1 vez** |
   | V3 | rotación, conjuntos de 2 (V1 y V2) | Dos llamadas seguidas al MISMO payload devuelven variantes **distintas** |
   | **V3b** | rotación, conjunto de 1 (V4) | Dos llamadas seguidas devuelven **lo mismo** — es lo correcto, no un fallo (AI2) |
   | V4 | `lineas` con 1 producto y `mudos` vacío | **NO** contiene `¿Miramos`; sí contiene `¿Seguimos con otro ángulo de` |
   | V5 | las 3 variantes | Contienen el nombre de la entidad (regla 2) |
   | V6 | las 3 variantes | **NO** contienen `<button`, `cn-opt-btn` ni `rb-chat__options` (regla 1) |
   | V7 | filial (`nivel:"filial"`) | **NO** contiene `da__invita` |
   | V8 | `!aplica` | **NO** contiene `da__invita` |
   | V9 | `__DA_TEMAS` todos `disponible:false` y sin otros productos | La invitación no se pinta |
   | V10 | no regresión | Las 22 aserciones de `test_respuesta_datos.js` siguen verdes |

   Si una aserción falla, **NO ajustarla para que pase**: reportar el fallo.
3. `grep -n "da__invita" static/css/colapsable.css` → 1 coincidencia.
4. **Navegador (usuario):** CASTILLA, CUPIAGUA y una filial; comprobar que la frase aparece al final
   de la tarjeta, en cursiva, que **no** repite «no reporta», y que rota al repetir la consulta.

---

## §9 · Fuera de alcance

- **El slot de «tema» en la extracción y su ruteo** (H3): sin él, tomar la invitación devuelve la
  respuesta de producción de siempre. Es la pieza que falta del lado del chat cuando se construya la
  capa de los 4 módulos; la frase ya quedará puesta y no habrá que tocarla.
- El contenido (mock o real) de diferidas / mantenimientos / EBITDA-NOPAT.
- «Comportamiento diario» como tema ofrecible (H4).
- Botones o chips de seguimiento: descartados explícitamente por el usuario.
- Arrastre de entidad entre preguntas (H1): se **mitiga** nombrando la entidad, no se resuelve.
- Densidad de la cola de 4 párrafos con avisos D-A4 largos (AI5): observación, no cambio.
