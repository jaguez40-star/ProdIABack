# Plan · Cuantificar N5 — el chat LEE, el panel DESGLOSA (2026-08-12) · **v2 AUDITADO**

**Objetivo:** que el mensaje del chat en el ranking de producción deje de repetir la
tabla que ya pinta el panel derecho y entregue en su lugar la **lectura** del
ranking: 3 bullets analíticos derivados en Python.

**Alcance:** SOLO el ranking **N5**, rama `metrica == "real"`. N1-N4 no se tocan. La
rama `gap` no se toca. El panel derecho no se toca.

**Baseline:** HEAD `5710e7e`. `node --check static/js/multitab_shell.js` pasa limpio
antes de tocar nada.

---

## 0. AUDITORÍA — 7 hallazgos que cambian el diseño inicial

> **Dos de estos hallazgos habrían roto funcionalidad existente** (A1 y A2) y
> **tres invalidan los umbrales que yo mismo propuse** (A4, A5, A6), medidos contra
> la BD real. Léela antes de codificar.

### A1 · 🔑 Mover la frase de terceros ROMPE el ranking por `gap`

El pie de `formatear_cuerpo` (`ranking.py:290-301`) es **común a las dos métricas**.
La línea `:299-300` («Los campos entre corchetes son operados por terceros») está
guardada **solo por nivel**, sin filtro de métrica.

Verificado en vivo — la rama `gap` la usa:

```
Los 5 campos con mayor faltante de crudo … (en bbl):
1) AKACIAS −1.021.211
3) CAJUA [Frontera Energy] −649.755
Sobre 128 campos con producción registrada. Los campos entre corchetes son
operados por terceros.
```

Si el bullet C (terceros) absorbe esa frase, un ranking por faltante queda con
corchetes `[Frontera Energy]` **sin glosar**. Igual con la línea del universo
(`:292`), que gap también emite.

**Corrección:** el pie común se conserva **intacto**. Los bullets de la rama `real`
se construyen ANTES y **no duplican** lo que el pie ya dice — o el pie se emite solo
para gap. Ver §2.3, es la decisión de estructura más delicada del plan.

### A2 · 🔑 Interpretar markdown genérico afectaría a los 4 grupos y al LLM

El plan v1 decía «convertir `**…**` en `<strong>`». Tres problemas:

1. **`__cnRenderV2` pinta los 4 grupos** (jerarquizar/cuantificar/analizar/OUT) y lo
   comparten **dos chats**: Consulta (`:4089`) y Test Clas (`:4304`).
2. **El intro lo escribe un LLM con `temperature: 0.8`**, y `intro_valido`
   (`validador.py:96`) bloquea dígitos y unidades pero **NO asteriscos** → un intro
   con markdown espontáneo (`**Claro, Javier**`) se renderizaría en negrita sin
   control.
3. Hay evidencia de que el equipo ya se topó con esto: dos prompts piden
   explícitamente «sin markdown» (`clasificador_llm.py:19`, `respuesta_out.py:44`).

**Corrección:** NO interpretar markdown genérico. Usar un **marcador propio y
acotado** que solo emite este generador (§2.4), aplicado **después** de `esc()`.
Verificado que ningún mensaje del Motor v2 usa hoy `**` ni los marcadores
candidatos.

### A3 · La libreta NO guarda la respuesta — sin impacto en BD

`core.clasificacion_log` guarda `texto_pregunta`, nunca el mensaje
(`log.py:28-36`). Además `maquina_q.py:334` llama a `registrar()` **antes** de que el
mensaje exista (se construye en `:340`). Los marcadores no llegan a la base de
datos, y `senales.py` (similitud Jaccard) opera **pregunta contra pregunta**
(`senales.py:37-42, 84-92`). **Cero impacto en la libreta y en el Control 2.**

Tampoco hay logging del mensaje: cero `logger`/`print` en todo `consulta_v2`. El
proxy Flask es passthrough (`routes/api.py:572-578`). **El texto tiene un único
consumidor: la burbuja del chat.**

### A3b · El texto de OUT llega SIN filtro de contenido — refuerza A2

`respuesta_out.py:114-121`: si el JSON parsea y `respuesta` es un string no vacío,
el texto del LLM se devuelve **íntegro**. No hay validador de contenido (a
diferencia del intro, que al menos filtra dígitos). Con `temperature: 0.8` sobre un
modelo pequeño, un `**énfasis**` espontáneo es plausible.

Hoy se vería como `**` literal (feo pero inocuo). Con interpretación de markdown
genérico, se renderizaría como negrita en una respuesta OUT. **Es la superficie de
mayor riesgo de A2** y la razón principal del marcador propio.

### A3c · `.v2-msg` usa `white-space: pre-line` — sin sangría por espacios

`colapsable.css:1793-1794`. Los **saltos de línea se respetan** (por eso funciona el
árbol de jerarquizar), pero los **espacios múltiples COLAPSAN**.

**Corrección:** los bullets se separan con **líneas en blanco**, nunca con sangría de
espacios — se perdería silenciosamente.

⚠️ Nota adicional: `multitab_shell.js:4352-4356` y `:4377-4381` construyen HTML con
la clase `.v2-msg` **a mano**, fuera de `__cnRenderV2` (calificación por lote de Test
Clas). No los afecta el marcador, pero **sí les afectaría cualquier cambio de CSS**
en `.v2-msg`. Por eso §2.4 no toca esa regla.

### A4 · ⚠️ El umbral de concentración estaba mal calibrado

El plan v1 decía `conc < 50 → "no extrema"`. Medido contra la BD, 6 casos reales:

| Producto | Nivel | conc | v1/v2 | peso #1 | spread #2→#5 |
|---|---|---|---|---|---|
| crudo | campo | **41,2%** | 1,80 | 34% | 23% |
| crudo | activo | 72,7% | 1,05 | 30% | 68% |
| gas | campo | 80,5% | 1,62 | 38% | 57% |
| gas | activo | 93,3% | 2,22 | 51% | 91% |
| blancos | campo | 77,9% | 2,19 | 44% | 55% |
| blancos | activo | 88,2% | 2,19 | 58% | 84% |

**5 de 6 superan el 70%.** Con el umbral de 50 el bullet diría «alta» casi siempre
→ constante, y por tanto inútil. El caso de la captura del usuario (41,2%) es **el
más bajo de los seis**.

**Corrección:** tres tramos — `< 50` moderada · `50-75` alta · `> 75` muy alta. El
universo también varía mucho (crudo 128 campos, gas 39, blancos 37), así que el
bullet debe decir siempre `n de N`, no solo el porcentaje.

### A5 · ⚠️ `v1/v2` es mal indicador de dominancia — y el umbral caía en el filo

El plan v1 usaba `v1/v2 ≥ 1.8`. **Crudo-campo da exactamente 1,80** — un umbral que
cae en el filo de un caso real es frágil: cualquier variación del dato lo cruza y el
bullet aparece/desaparece sin motivo visible.

Peor: **crudo-activo da 1,05** (sin outlier por esa regla) pero el #1 pesa el 30%
del top. El ratio contra el #2 no captura la forma de la distribución.

**Corrección:** decidir por el **peso del #1 dentro del top** (`v1 / Σvalores`), que
es estable y no depende del segundo. Umbral `≥ 40%` → «destaca». `v1/v2` puede
usarse como color («casi duplica al segundo») **solo si `≥ 1.5`**, nunca como gate.

### A6 · ⚠️ El «pelotón apretado» es específico del crudo por campo

`spread(#2→#último)` da 23% en crudo-campo, pero **55-91% en los otros cinco casos**
— son distribuciones en escalera, no pelotones. Afirmar «apretados» sería falso en 5
de 6 casos.

**Corrección:** el matiz es **condicional** (`spread < 30%`), y si no se cumple no se
emite (no se afirma lo contrario).

### A7 · Casos borde que revientan si no se guardan

| Caso | Qué pasa | Guarda |
|---|---|---|
| `top_n == 1` | `items[1]` → **IndexError**. Es frecuente: cualquier pregunta en singular da `top_n=1` (`ranking.py:125-127`), y `top = ordenado[:top_n]` puede devolver menos de lo pedido | `len(items) >= 2` |
| `items[1]["valor"] == 0` | **ZeroDivisionError**. `con_real` filtra el float `> 0` (`:208`) pero el item guarda `round()` (`:252`) → un campo de 0,4 bbl queda en 0, y en `bottom` cae en las primeras posiciones. *No se materializa este mes (verificado: bottom-5 crudo va de 1.176 a 4.368), pero el mecanismo existe* | `items[1]["valor"] > 0` |
| `len(items) == 2` | `items[1] is items[-1]` → spread = 0 → diría «plana» absurdamente | `len(items) >= 3` para el spread |
| `concentracion_pct is None` | f-string imprimiría `"None%"`. Ocurre en **real+bottom** (verificado) y en toda la métrica gap | `is not None` |
| nivel `activo` | `es_ecp` es **siempre `None`** por diseño (`:174` SQL `NULL AS operador` + `:251`) | bullet C solo si `nivel_ranking == "campo"` |
| `es_ecp` tri-estado | `None` = operador desconocido. `not it["es_ecp"]` contaría los `None` como terceros = **afirmación falsa** | contar con `is False` estricto |

### A8 · Descargos honestos que NO se pueden perder

1. **`sin_registro`** (`:296-298`) — «hay N campos sin registro REAL este mes (paro o
   dato faltante — a grano mes no son distinguibles); no se listan». Verificado:
   **15 campos** en bottom-5 crudo. Es lo único que confiesa el filtro «cero
   traicionero» (`:208`); sin él, `bottom` miente por omisión.
2. **Terceros** (`:299-300`) — glosa los corchetes. Ver A1.
3. **Universo** (`:292`) — huella «no silent caps».
4. **`es_proyeccion`** (`:270`) — «(cierre proyectado del mes en curso)», hoy dentro
   de la cabecera de la rama real (`:284`).

---

## 1. El entregable

Para «¿cuáles campos son los mayores productores de crudo?»:

> ⟦Concentración fuerte pero no extrema⟧ 5 de 128 campos generan el 41,2% de los
> barriles — el grueso sigue viniendo de la cola larga.
>
> ⟦RUBIALES destaca dentro del propio Top 5⟧ Concentra un tercio del grupo y casi
> duplica al segundo, mientras que del #2 al #5 las cifras están tan apretadas que
> cambios modestos pueden reordenarlas.
>
> ⟦Dependencia de terceros⟧ QUIFA y CAÑO LIMÓN son operados por Frontera Energy y
> Sierracol Energy Arauca, fuera del control operacional directo.
>
> Sobre 128 campos con producción registrada. Cierre proyectado del mes en curso.

(`⟦…⟧` es el marcador interno que el frontend convierte en negrita; ver §2.4.)

Reglas de contenido fijadas con el usuario:
- **Máximo 3 bullets**, título + explicación.
- **Cifras livianas**: una por bullet como máximo.
- Los cinco nombres con sus volúmenes quedan **solo en el panel**.

---

## 2. Cambios

### 2.1 `cuantificar/ranking.py` — helpers de derivación [NUEVOS]

Funciones **puras** (reciben el dict, no tocan BD ni LLM), testeables aisladas:

```python
def _b_concentracion(res) -> str | None:
    """Bullet A. None si concentracion_pct no aplica (real+bottom, gap)."""
    # tramos: <50 "fuerte pero no extrema" · 50-75 "alta" · >75 "muy alta"
    # SIEMPRE dice "n de N", no solo el %  (A4: el universo varía 37..128)

def _b_dominancia(res) -> str | None:
    """Bullet B. None si len(items)<2 o items[1]['valor']<=0 (A7)."""
    # gate = peso del #1 en el top (>=40%), NO v1/v2 (A5)
    # "casi duplica al segundo" solo como color, si v1/v2 >= 1.5
    # matiz de pelotón solo si len(items)>=3 y spread<30% (A6)

def _b_terceros(res) -> str | None:
    """Bullet C. None si nivel_ranking != 'campo' o no hay es_ecp is False (A7)."""
    # contar con `is False` estricto (tri-estado)
    # NO incluir la glosa de corchetes: esa vive en el pie común (A1)
```

Cada helper devuelve `None` cuando su regla no se cumple: **el bullet no se emite,
nunca se afirma lo contrario**.

### 2.2 `cuantificar/ranking.py` — `formatear_cuerpo`, rama `real`

Sustituir la construcción de `cab` + `piezas` (`:281-288`) por el ensamblado de los
bullets no nulos. **La rama `gap` (`:272-280`) no se toca.**

La cabecera actual («Los 5 campos de mayor producción de crudo en mayo 2026…») se
retira de la rama real: su información (producto, periodo, nivel) **ya está en el
chip de cabecera del panel**, y los bullets la llevan implícita. El
`(cierre proyectado…)` **NO se pierde**: baja al pie (§2.3).

### 2.3 🔑 El pie común — la decisión estructural

Estado actual (`:290-301`), con su alcance real por métrica:

| Pieza | gap | real |
|---|---|---|
| `Sobre N … con producción registrada` | **sí** | sí |
| `; concentran el X% del total` | nunca (`conc` es None) | solo `top` |
| aviso `sin_registro` | nunca | solo `bottom` |
| glosa de terceros | **sí** | sí |

**Regla de la reescritura:**
- Las piezas **universo** y **glosa de terceros** se conservan en el pie común, sin
  tocar (A1 — gap depende de ellas).
- La pieza **concentración** del pie se retira **solo de la rama real** (la absorbe
  el bullet A). Para gap es código muerto (`conc` siempre `None`) → no-op.
- El aviso **`sin_registro`** se conserva íntegro (A8).
- El `(cierre proyectado…)` pasa al pie de la rama real.

Resultado: el bullet A dice el % y el pie dice el universo — **sin duplicarse**.

### 2.4 `static/js/multitab_shell.js` — negrita acotada

En `__cnRenderV2` (`:4165`), hoy:
```js
h += '<p class="v2-msg">' + esc(d.mensaje || "") + '</p>';
```

Cambiar a: `esc()` **primero** (sigue escapando todo — el mensaje incluye el intro
del LLM, que no es fuente confiable), y **después** convertir el marcador acotado en
`<strong>`.

**Requisitos no negociables:**
- El marcador es **propio** (p.ej. `⟦…⟧`), NO `**` markdown (A2/A3b). Verificado que
  ningún mensaje del Motor v2 lo usa hoy — el único `**` del código está en un
  docstring (`ranking.py:92`), que nunca llega al usuario.
- La conversión se aplica sobre el **texto ya escapado**; nunca se inyecta HTML
  desde el backend.
- La regex debe ser **no codiciosa** y de una sola línea, para que un marcador sin
  cerrar no se coma el resto del mensaje.
- Se emite `<strong>` dentro del `<p class="v2-msg">` existente. **No envolver el
  mensaje en `<div>`**: `__v2MarcarVotado` (`:4181-4194`) reescribe el historial con
  un regex no-codicioso hasta el primer `</div>`, y hay un aviso explícito de no
  anidar divs (`:4148-4149`, `colapsable.css:1796`).
- `.v2-msg` ya tiene `white-space: pre-line` (`colapsable.css:1794`) → **los saltos
  de línea ya funcionan**; **no se toca el CSS** (esa clase la comparten los bloques
  de calificación por lote, A3c).

⚠️ Este cambio afecta a **los 4 grupos y a los 2 chats** (Consulta `:4089` y Test
Clas `:4304`). Por eso el marcador acotado: hoy nadie más lo emite, así que el
comportamiento de jerarquizar/analizar/OUT queda **byte-idéntico**.

### 2.5 `templates/main.html` — cache-busters

Ambos: `colapsable.css` (L5) solo si se toca CSS, y **`multitab_shell.js` (L82)
obligatorio**. Hoy los dos están en `20260812b1`.

---

## 3. Lo que NO se toca

- `_panel_rank` y el contrato del panel (`respuesta_cuantificar.py:202-206`).
- El dot plot, la dona y su CSS (plan aparte, en ejecución).
- `ranking.calcular`, `ranking.detectar`, `_SQL`.
- La rama `metrica == "gap"` de `formatear_cuerpo`.
- `validador.formatear_cuerpo` (N1-N4) y sus tests.
- `_intro_ranking`, `PROMPT_RANK` y el envoltorio del LLM.
- `_CIERRE_RANK` — ⚠️ **no puede terminar en pregunta sí/no**: un «sí» cae en el
  drill `_AFIRM` de `maquina_q._continuacion` y devolvería un acumulado
  (`respuesta_cuantificar.py:55`).

---

## 4. Validación

### V1 · Estático (dev)
```
node --check static/js/multitab_shell.js
cd INGESTA/Rep_Prod/backend && uv run python -m pytest tests/test_cuantificar_ranking.py -q
cd INGESTA/Rep_Prod/backend && uv run python -m pytest tests/test_cuantificar.py -q
```
**No hay ningún test sobre el texto del ranking** (validan `detectar()` y el
contrato de datos) → deben pasar sin cambios. Si fallan, se rompió algo fuera de
alcance. Los de `test_cuantificar.py` (`:253`, `:456`, `:467`) cubren N1/N3/N4 y
deben seguir verdes.

⚠️ La suite V-CALC hace **skip si Postgres no está disponible** → en un entorno sin
BD la cobertura de estos casos es cero. No confiar solo en el verde.

### V2 · Tests nuevos de los helpers (puros, sin BD)
Uno por guarda de A7, más los tramos de A4:

| # | Caso | Esperado |
|---|---|---|
| 1 | `len(items) == 1` | bullet B es `None`, sin IndexError |
| 2 | `items[1]["valor"] == 0` | bullet B es `None`, sin ZeroDivisionError |
| 3 | `len(items) == 2` | sin matiz de pelotón |
| 4 | `concentracion_pct is None` | bullet A es `None`; nunca aparece «None%» |
| 5 | `nivel_ranking == "activo"` | bullet C es `None` |
| 6 | items con `es_ecp is None` | NO se cuentan como terceros |
| 7 | conc 41 / 60 / 85 | «no extrema» / «alta» / «muy alta» |
| 8 | peso #1 = 25% | bullet B es `None` (no destaca) |

### V3 · Cuerpo completo contra la BD real (dev, script de humo)
Imprimir `formatear_cuerpo` de los 6 casos de A4 + los 3 borde ya medidos
(`top_n=1`, `bottom`, `gap`) y revisar a ojo que **ninguno afirme algo falso**.
Redirigir a archivo con UTF-8: la consola de Windows revienta con el `−` U+2212 de
la rama gap (cp1252) — es de la consola, no del código.

### V4 · Navegador (servidor de pruebas, lo corre el usuario)

| # | Caso | Esperado |
|---|---|---|
| 1 | «cuáles campos son los mayores productores de crudo» | 3 bullets con título en negrita; **sin lista enumerada**; pie con universo y proyección |
| 2 | El panel derecho | **Sin cambios**: dot plot + dona con los 5 nombres y cifras |
| 3 | «mayores productores de gas» | Bullet A dice «muy alta» (80,5%); coherente |
| 4 | Ranking por **activo** | **Sin** bullet de terceros |
| 5 | «cuál es el mayor productor de crudo» (top_n=1) | Sin bullet B; sin error |
| 6 | «menores productores de crudo» | Sin bullet A; **con** el aviso de `sin_registro` |
| 7 | «mayor faltante de crudo» (gap) | **Sin regresión**: lista enumerada + glosa de corchetes intactas |
| 8 | Jerarquizar («qué campos tiene Castilla») | **Byte-idéntico** — el marcador no lo afecta |
| 9 | Analizar y OUT | **Byte-idénticos** |
| 10 | Pestaña **Test Clas** | Renderiza igual que Consulta |
| 11 | Drill «¿y para gas?» tras un ranking | La memoria conversacional sigue funcionando |
| 12 | Marcador sin cerrar (si ocurre) | No se come el resto del mensaje |

⚠️ **Antes de verificar, RECARGAR la página.** `__cnHistory` guarda **HTML ya
renderizado** y `__cnReplay` (`:4063-4072`) lo repinta tal cual, sin volver a llamar
`__cnRenderV2` — las burbujas pintadas antes del cambio conservan su HTML viejo
dentro de la misma sesión. No es un bug (no hay persistencia: el historial muere al
recargar, `localStorage` solo guarda la preferencia de motor), pero sin recargar se
vería una inconsistencia que parece un fallo.

---

## 5. Riesgos residuales

| Riesgo | Prob. | Mitigación |
|---|---|---|
| Se mueve la glosa de terceros al bullet → gap sin explicar corchetes | **Media** si se ignora A1 | V4 #7; §2.3 lo prescribe |
| Se usa `**` markdown → el intro del LLM se pinta en negrita | Media si se copia el v1 | A2; marcador propio; V4 #8/#9 |
| Un umbral emite un bullet falso | Media | Umbrales recalibrados con 6 casos reales (A4-A6); V3 revisa a ojo |
| `IndexError`/`ZeroDivisionError` en producción | Baja | Guardas de A7 + tests V2 #1/#2 |
| Se pierde el aviso de `sin_registro` | Baja | A8; V4 #6 |
| El bullet queda constante y por tanto inútil | Baja | Tramos de A4; V3 sobre 6 casos |

---

## 6. Fuera de alcance

- N1/N2/N3/N4 (duplicación menor; N3/N4 tienen tests de texto).
- El bullet de cumplimiento vs presupuesto — **`ppto`/`gap` ya vienen por item al
  100% de cobertura** y hoy no se usan en métrica real (medido: solo 2 de 5 cumplen,
  Top 5 a −1,9 M bbl). Decisión del usuario: la pregunta era *quién produce más*, no
  *quién cumple*. **Candidato fuerte para la siguiente fase.**
- El bullet geográfico/jerárquico — **descartado**: `map_campo_robustez` cubre solo
  80 de 139 campos (58%) y en el Top 5 los nulos son justo los terceros (QUIFA,
  CAÑO LIMÓN), que en un ranking de mayores productores están siempre arriba.
- Jerarquizar y Analizar.

---

## 7. Resumen de archivos

| Archivo | Ediciones |
|---|---|
| `consulta_v2/cuantificar/ranking.py` | 3 helpers nuevos + rama `real` de `formatear_cuerpo` + reparto del pie |
| `backend/tests/test_cuantificar_ranking.py` | +8 tests de helpers (puros, sin BD) |
| `static/js/multitab_shell.js` | `__cnRenderV2`: negrita acotada tras `esc()` |
| `templates/main.html` | Cache-buster del JS (L82) |

**Commit sugerido:**
```
feat(chat): el ranking N5 responde con la lectura, no con la tabla

El mensaje del chat repetia exactamente lo que ya pinta el panel derecho: los 5
campos, sus volumenes, el universo y la concentracion salian del MISMO dict `res`.
Ahora el chat entrega 3 bullets analiticos (concentracion, dominancia, terceros)
derivados en Python, y el detalle campo por campo queda solo en el panel.

Los umbrales se calibraron contra 6 casos reales de la BD, no de memoria: la
concentracion va de 41% a 93% segun producto y nivel, asi que un corte unico en 50
habria dicho "alta" casi siempre; y el ratio #1/#2 daba exactamente 1,80 en el caso
de referencia -- demasiado en el filo -- por lo que la dominancia se decide por el
peso del #1 dentro del top.

Dos cosas que NO se tocan, por auditoria:
- El pie comun (universo + glosa de corchetes) lo usa TAMBIEN la rama gap: moverlo
  al bullet habria dejado los rankings por faltante con "[Frontera Energy]" sin
  explicar.
- El frontend no interpreta markdown generico sino un marcador propio: el intro lo
  escribe un LLM con temperature 0.8 e intro_valido no bloquea asteriscos, asi que
  "**Claro, Javier**" se habria renderizado en negrita en los 4 grupos.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
```
