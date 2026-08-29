# Plan de ejecución — Cuantificar · FASE 1 (núcleo 🟢 crudo)

> **Objetivo:** implementar la rebanada más delgada de Cuantificar que responde de punta a
> punta, honestamente y con doble entregable, **una** pregunta real: *"¿cuánto produjo {campo}
> de crudo en {mes}?"* (N1) y *"¿cuánto acumuló {campo} ene-may?"* (N2), vs PPTO.
>
> **Documento de diseño:** `cuant.md` · **Catálogo:** `catalogo_cuantificar_DRAFT.yaml` ·
> **Evidencia:** `AUDITORIA_VIABILIDAD_CUANTIFICAR.md`
>
> **Estrategia:** *walking skeleton* — 5 sub-compuertas verificables (1a→1e). Cada una termina
> en un estado que FUNCIONA y se verifica contra la BD antes de escribir la siguiente. No se
> construye todo y se depura al final.
>
> **Fecha:** 2026-08-02 · **Estado:** DRAFT para revisión antes de ejecutar.

---

## 🔴 Hallazgos de auditoría del código real (§0.2 — verificados 2026-08-02)

El plan v1 asumía cosas que el código desmiente. Corregidos ANTES de ejecutar:

| # | Hallazgo (verificado) | Impacto en el plan |
|---|----------------------|--------------------|
| **H1** | **`analisis.desempeno` NO es una función limpia — es un ENDPOINT FastAPI** (`entidad=Query(None)`, `segmento=Query("ecp")`…). Llamarlo directo hace que las Query() se filtren como default (segmento quedaría objeto, no "ecp"). | El ejecutor **NO llama al endpoint**. Reusa el helper plano **`_ambito(c, entidad, nivel, periodo)`** (que `desempeno_insight` ya reusa, `api.py:1130`) + **factoriza `_desempeno_core(c, …)`** desde el endpoint. Coherencia por compartir el MISMO cómputo, no por llamar la ruta. |
| **H2** | **`_parse_periodo`/`_ambito` son de UN mes** (`api.py:372/391` → un `(año, mes)`). "acumuló ene-may" (N2) NO está soportado. | N2 = **Σ del cómputo coherente por mes** sobre el rango (loop mensual), NO SQL independiente. Preserva coherencia mes a mes. |
| **H3** | **El return de `maquina_q` solo tiene `mensaje`** (string, `:226-237`). No hay campo para el panel. | El doble entregable exige **añadir un campo `panel` al return** (aditivo → jerarquizar/out no se rompen) **+ que el frontend lo pinte** en el visor (`__cnPaintDesemp`/`__cnP50CardHtml`). No es gratis: toca el contrato de salida y `multitab_shell.js`. |
| **H4** | **El ensamblador ya existe: `_envolver` (`respuesta_jerarquizar.py:333`)** = intro(LLM)+body+cierre. Pero el **prompt del intro, el flag `consulta_jerarq_llm` y `_ofertas` (cierre) son de jerarquizar**. | `respuesta_base.py` generaliza `_envolver` recibiendo **intro-prompt, flag y texto-de-cierre como parámetros** (no se levantan tal cual). Refactor de jerarquizar a usarlo → **verificar no-regresión**. |
| **H5** | **`_CTX`/`_continuacion` están moldeados a jerarquizar** (`_continuacion` usa `respuesta_jerarquizar.entidad_en`, `:42-60`; `_CTX` se puebla solo en `:259`). El comentario `:259` YA dice *"producción cae en Cuantificar (otro agente)"*. | El drill N1→N2 ("¿acumulado?") exige **extender `_continuacion` + la estructura de `_CTX`** para el contexto de cuantificar. Es más que "guardar {entidad,nivel}" — toca la máquina de memoria. Va en 1e. |
| **H6** | Cuantificar necesita su **propio flag de LLM** (jerarquizar usa `consulta_jerarq_llm` en `config.py`). | Añadir `consulta_cuant_llm` (o equivalente) en `config.py`, patrón `CONSULTA_*`. |

🔑 **Regla de cobertura (§0.2):** este plan NO reduce alcance en silencio. Fase 1 = crudo/PPTO/N1-N2/mes
es un **recorte de FASE explícito** (no de datos): el catálogo completo se preserva; las demás celdas
entran en Fase 2-4, no se descartan.

---

## Anclajes NO negociables (de las 3 revisiones de `cuant.md` + auditoría del código)

1. **Coherencia chat↔tablero (reformulado por H1):** `ejecutor.py` reusa el helper plano
   **`_ambito()`** + una función **`_desempeno_core(c, entidad, nivel, periodo)`** que se factoriza
   desde el endpoint `desempeno` (el mismo cómputo que pinta el tablero). **NO llama al endpoint**
   ni escribe SQL propio para el núcleo → chat y panel comparten el mismo cálculo. El refactor de
   `analisis` (extraer `_desempeno_core`) es mínimo y **requiere no-regresión del tablero**.
2. **Sin endpoint nuevo:** se cablea dentro de `maquina_q.clasificar()`
   (`elif grupo == "cuantificar" and log:`), como jerarquizar (`maquina_q.py:217`). NO se toca
   el frontend para enrutar.
3. **El número es VERBATIM de Python:** el LLM escribe SOLO el intro; el cuerpo (cifra ya
   formateada) lo arma Python. `respuesta_base.py` compartido (extraído de `respuesta_jerarquizar`).
4. **`_CTX` simétrico:** al resolver, guardar `{entidad, nivel}` en `_CTX` (`maquina_q.py:259-263`)
   para que el follow-up funcione.
5. **`format:"json"` en el LLM del intro** (gemma@139 devuelve vacío en texto plano — fix `bde9524`).
6. **Golden con `log=False`** (patrón H3 — no meter filas basura a la libreta).

---

## SUB-FASE 1a — Esqueleto que camina (la ruta prende)

**Construir:**
1. Renombrar `catalogo_cuantificar_DRAFT.yaml` → `consulta_v2/config/variables_cuantificables.yaml`.
2. `cuantificar/catalogo.py`: carga + valida el YAML 1 vez al arranque (patrón de `patrones.py`).
   Falla ruidoso si el YAML está mal.
3. `respuesta_cuantificar.py` con `responder(texto, usuario, conversation_id)` = **STUB**
   (devuelve una burbuja "«Cuantificar» — en construcción" + eco de la entidad detectada).
4. Wiring en `maquina_q.clasificar()`: `elif grupo == "cuantificar" and log:` →
   `respuesta_cuantificar.responder(...)`.

**✅ COMPUERTA 1a:** en el navegador (Motor v2), "cuánto produjo Rubiales" → el clasificador dice
`cuantificar` → aparece la burbuja stub. `py_compile` + `node --check` OK. La ruta existe.

---

## SUB-FASE 1b — El número real (crudo N1, vs PPTO, un mes)

**Construir:**
1. `cuantificar/resolver.py` (FORK de `consulta/resolver`): nombre → `{fuente_id, nivel, canónico}`
   con prioridad **D-D5 (Campo gana)**. Guardar en `_CTX`.
2. `cuantificar/slots.py`: el LLM extrae `{variable, nivel, rango, referencia}`; Python los aterriza
   contra el catálogo. Defaults Fase 1: variable=crudo, nivel=N1, referencia=PPTO, rango=mes actual.
   Producto por **volumen dominante** (no fijo).
3. **Refactor mínimo en `analisis/api.py` (H1):** extraer de `desempeno` una función plana
   `_desempeno_core(c, entidad, nivel, periodo) -> {crudo:{real,ppto,estado,…}, …}`; el endpoint
   `desempeno` pasa a llamarla (sin cambiar su salida). **No-regresión:** el endpoint debe devolver
   lo mismo que antes (probar Rubiales/abril antes y después).
4. `cuantificar/ejecutor.py`: reusa `_ambito()` + `_desempeno_core()`; extrae REAL + PPTO del crudo.
   Arma el JSON del contrato (§7) con `huella` y `es_proyeccion`. NO SQL propio.

**✅ COMPUERTA 1b:** "cuánto produjo Rubiales en abril" → cifra REAL de crudo **idéntica a la del panel
Desempeño** (mismo `_desempeno_core`); verificar a mano contra la BD (Rubiales crudo abril). El endpoint
`desempeno` **sigue devolviendo lo mismo** (no-regresión). Rechaza agua/blancos-día. Coherente.

---

## SUB-FASE 1c — La prosa honesta (respuesta_base + validador)

**Construir:**
1. `respuesta_base.py` (NUEVO, compartido): generalizar **`_envolver`** de `respuesta_jerarquizar.py:333`
   como `envolver(body, intro_prompt, flag, cierre_text, usuario)` — el intro-prompt, el **flag propio
   (`consulta_cuant_llm`, H6, añadir en `config.py`)** y el texto-de-cierre entran como **parámetros**
   (H4: no se levantan los de jerarquizar). El intro pide `format:"json"` `{"intro":"…"}`. **Refactor:
   `respuesta_jerarquizar` pasa a llamar `respuesta_base.envolver(...)` con SUS params → verificar
   no-regresión de jerarquizar (harness antes/después: mismo texto).**
2. `cuantificar/validador.py`: (a) el cuerpo se pre-formatea al literal (`__cnMilesEC`-equivalente en
   Python, es-CO); (b) el intro se valida — ningún número/entidad ausente del JSON; falla 2× → sin intro.
3. Regla de proyección: si `es_proyeccion=true`, el cuerpo DICE "proyección" o "al corte del día N/total".

**✅ COMPUERTA 1c:** la respuesta sale con intro cálido + cuerpo verbatim + cierre "¿Quieres verlo mes
a mes?"; un mes en curso se narra como proyección; el validador tumba un intro con número inventado y
cae a solo-cuerpo. Fallback determinista si el LLM falla.

---

## SUB-FASE 1d — El panel derecho (doble entregable N1)

**Construir:**
1. Backend (H3): **añadir el campo `panel` al return de `maquina_q`** (`:226-237`) — **aditivo**, jerarquizar/
   out lo dejan `null` (no se rompen). `respuesta_cuantificar.responder()` devuelve `{mensaje, panel}`;
   el `elif` de cuantificar en `_clasificar_core` setea ambos. `panel` = `{tipo:"kpi", widget:"cnP50CardHtml",
   datos: los YA calculados}`.
2. Frontend (`multitab_shell.js`): la función que pinta la respuesta de Consulta lee `res.panel` (si
   viene) y pinta el visor derecho reusando `__cnP50CardHtml`/`__cnKpiStatus`; si `panel` es `null`
   (jerarquizar/out) no toca el visor. Formateadores `__cnMilesEC`/`__cnGasM` (los mismos del chat, H sobre coherencia visual).

**✅ COMPUERTA 1d:** al responder N1, el panel derecho pinta la tarjeta KPI con la **misma cifra** del
chat. **Jerarquizar y OUT siguen igual** (panel null, no-regresión del visor). `node --check` OK; navegador.

---

## SUB-FASE 1e — N2 acumulado + golden + tests

**Construir:**
1. `niveles.py`: N2 = **Σ del cómputo coherente por mes** (`_desempeno_core` en loop sobre el rango,
   H2) — NO SQL independiente. Un rango se parsea a lista de (año,mes).
2. **Extender `_continuacion` + `_CTX` para cuantificar (H5):** guardar `{entidad, nivel, variable}` al
   resolver, y que `_continuacion` reconozca los follow-ups de cifra ("¿acumulado?", "¿mes a mes?") →
   el drill N1→N2 mueve chat y panel. Verificar no-regresión del drill de jerarquizar.
3. Panel N2: barra acumulado vs meta (`__cnGapCampoInto`).
3. `golden/cuantificar_golden.yaml` (**≥10 casos** crudo, uno por N1/N2, + 1 proyección + 1 que exceda
   el techo → recorte) + `run_golden.py` (gate ≥90%, `log=False`). Tests pytest.

**✅ COMPUERTA 1e (cierre de Fase 1):** golden ≥90% con **paridad qwen2.5/gemma4**; N1 y N2 verificados
a mano; el drill N1→N2 mueve chat y panel juntos. pytest verde.

---

## Fuera de la Fase 1 (explícito)
Gas, blancos, N3 serie, N4 variación, referencias OPERATIVO/CONTABLE/promedio, gap/cumplimiento,
diferidas, conteos de jerarquía, vías satélite (robustez/filiales/nivel-org). Todo eso es Fase 2-4.
Fase 1 = **crudo, INGESTA, PPTO, N1/N2, mes** — la celda 🟢 sin caveats.

---

## Riesgos anticipados
| # | Riesgo | Mitigación |
|---|--------|-----------|
| A1 | ~~firma de `desempeno`~~ → **RESUELTO (H1):** es endpoint; reusar `_ambito` + factorizar `_desempeno_core` | El único riesgo residual es la no-regresión del endpoint tras el factor → probar Rubiales/abril antes/después |
| A2 | El refactor de `respuesta_jerarquizar`→`respuesta_base` rompe jerarquizar | Harness de no-regresión sobre jerarquizar antes/después |
| A3 | El resolver de cuantificar (dim_fuente) diverge del de jerarquizar (map_campo_robustez) | Reusar D-D5; documentar; unificar en Fase 3 (R11) |
| A4 | gemma@139 frío revienta el intro | Warm-up ya existe (`warmup.py`); fallback determinista si falla |
| A5 | El pre-formato Python del número no coincide con el JS del panel | Un solo criterio es-CO; test que compare ambos |

---

## Criterio de "listo para Fase 2"
Las 5 compuertas verdes + verificación en navegador por el usuario + commit. Recién ahí se abre gas/blancos/N3/N4.
