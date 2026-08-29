# HALLAZGO — El pipeline de OUT (desconocido) redacta sin contexto real

**Fecha:** 2026-08-02 · **Estado (2026-08-03):** causa **2.1 RESUELTA**; causa **2.2 PARCIALMENTE
resuelta** (solo con contexto de entidad). Ver §5.
**Severidad:** media — no da datos incorrectos (frontera dura respetada), pero la respuesta es
evasiva y no ayuda al usuario a entender POR QUÉ su pregunta no se resolvió.

---

## 1. Síntoma observado

En una sesión de prueba de Cuantificar (Motor Q v2, `consulta_v2`), tres preguntas seguidas
cayeron en el grupo `desconocido` (OUT) y el chat respondió tres textos **redactados por el LLM**
(`respuesta_out.redactar_out`, no el fallback estático) que se leen casi intercambiables entre sí:

| Pregunta real del usuario | Respuesta del bot (resumida) |
|---|---|
| «Los 17 días de Enero, ¿cuánto ha producido?» | "...tu interés en la producción durante el último periodo de enero... mi enfoque está limitado a temas de Ecopetrol..." |
| «En mayo, los 17 días ¿cuánto ha producido?» | "...te interesa saber sobre la producción de los últimos días... mi conocimiento se enfoca en tres áreas..." |
| «Mayo ¿cuánto ha producido?» | "...te interesa saber cuánta ha producido **el mes pasado**... mi enfoque está en la producción de hidrocarburos..." ⚠️ *"el mes pasado" es además INCORRECTO — mayo era el mes en curso, no el pasado* |

Las tres comparten la misma estructura de 4 pasos (reconocer vagamente el tema → decir que está
fuera de contexto → ofrecer 3 temas fijos → preguntar cuál). Ninguna dice la razón REAL de por qué
la pregunta no se resolvió, y la tercera incluso afirma algo objetivamente falso sobre el periodo.

🔑 **Importante:** las tres preguntas eran, en realidad, preguntas de producción **legítimas** —
no "¿cuál es la capital de Francia?". Dos pedían un **rango de días dentro de un mes** (grano día
con rango explícito, que Cuantificar no calcula en ninguna de sus 4 fases — fuera de alcance
documentado desde el primer plan). La tercera («Mayo ¿cuánto ha producido?», sin nombrar la
entidad) ya se corrigió aparte (commit `dc25ee0`, drill de continuación N1 genérico) y hoy resuelve
directo en Cuantificar — queda aquí solo como evidencia de que el síntoma de fondo también las
afectaba a ellas mientras el bug de memoria estuvo vivo.

---

## 2. Causa raíz (dos causas distintas, no una)

### 2.1 — El prompt de OUT nunca recibe el historial de la conversación

`respuesta_out.py` construye el prompt así (`PROMPT_OUT`, línea 28):

```python
Pregunta del usuario: {texto}
```

Solo la ÚLTIMA frase, aislada. El LLM nunca ve que las 3 preguntas eran continuación de una
conversación sobre Rubiales — por eso solo puede parafrasear en abstracto ("el último periodo",
"los últimos días", "el mes pasado") en vez de decir algo concreto: no tiene con qué.

El prompt SÍ le pide especificidad (línea 32: *"Mencione con tacto EL TEMA CONCRETO que
preguntó"*) y variedad (`temperature=0.8`, línea 38: *"Cada respuesta debe sonar distinta... NO
una plantilla fija"*) — y en efecto el texto varía palabra por palabra entre las tres (no es el
`TEXTO_FALLBACK` estático, que no coincide con ninguna). El problema no es que el LLM ignore la
instrucción; es que la instrucción le pide algo que la información que recibe no le permite
cumplir.

### 2.2 — El clasificador no distingue "fuera de dominio" de "en dominio pero no resuelto"

`maquina_q._clasificar_core` (filtro de dominio, `motor_Q.md §1.2`) es binario: si no hay entidad
del catálogo NI palabra de vocabulario, es `desconocido`. No existe una categoría intermedia para
"esto suena a producción, pero no lo puedo resolver" (entidad no nombrada, rango de días no
soportado, mes ambiguo, etc.). Preguntas como «¿cuál es la capital de Francia?» y «los 17 días de
enero, ¿cuánto ha producido?» caen en el MISMO balde — pese a que la segunda es, en espíritu,
exactamente el tipo de pregunta que este chatbot existe para responder.

Por eso el LLM de OUT, aunque quisiera, no tiene forma de decir la verdad concreta ("pido un rango
de días, eso no lo calculo todavía") — esa información nunca llega hasta él; el pipeline solo le
pasa el texto y una etiqueta genérica de "fuera de dominio".

---

## 3. Camino (mejoras propuestas, NINGUNA implementada — requieren decisión del usuario)

1. **Pasar contexto reciente al prompt de OUT.** `maquina_q._CTX` ya guarda `{grupo, entidad,
   producto}` de la última resolución en Cuantificar (y su equivalente en Jerarquizar). Inyectar
   ese contexto en `PROMPT_OUT` (p. ej. *"La conversación reciente fue sobre {entidad}..."*)
   permitiría respuestas que sí reconozcan el hilo, sin romper la frontera dura (el LLM sigue sin
   poder responder la pregunta ajena, solo tendría más con qué reconocerla).

2. **Separar "fuera de dominio" de "en dominio, no soportado".** Cuando `detectar_entidad` o el
   vocabulario SÍ encuentran evidencia de producción pero el patrón/slot no calza con ninguna
   capacidad construida (p. ej. rango de días, periodo año/trimestre), enrutar a un mensaje
   DISTINTO y más honesto ("eso es un rango de días — hoy solo calculo el mes completo") en vez de
   mezclarlo con el rechazo genérico de OUT. Esto es más una decisión de diseño del clasificador
   (`motor_Q.md`) que un parche de prompt.

3. **Fix menor, bajo riesgo:** la mención "el mes pasado" en el ejemplo 3 es un error factual del
   LLM (mayo era el mes EN CURSO). Es un síntoma más de 2.1 — con contexto real, ese tipo de
   invención por falta de información deja de tener terreno para ocurrir.

**Ninguna de estas tres se ha implementado.** Es una nota de mejora, no un plan ejecutable — si se
decide seguir alguna, requiere su propio plan auditado (mismo criterio que el resto de
`consulta_v2`) antes de tocar código.

---

## 4. Cómo reproducir el diagnóstico (read-only)

```python
# desde INGESTA/Rep_Prod/backend, sin tocar la BD ni el LLM:
from app.features.consulta_v2 import respuesta_out
print(respuesta_out.PROMPT_OUT)          # confirma: solo {texto}, sin historial
print(respuesta_out.TEXTO_FALLBACK)      # compárese contra las respuestas reales servidas —
                                          # si no coinciden, vinieron del LLM, no del fallback
```

Y en `maquina_q._clasificar_core` (`maquina_q.py:262`): el bloque `if grupo == "desconocido" and
log:` es el único punto donde se llama `respuesta_out.redactar_out(texto, usuario=usuario)`
(línea 267) — confirma que el pipeline entero pasa por ahí, sin acceso a `_CTX`.

> ⚠️ Las referencias de línea de §2 y §4 son del estado PREVIO a la resolución (2026-08-02).
> Tras el commit `3bbae0f` (§5) la rama OUT de `_clasificar_core` cambió: `redactar_out` ya recibe
> `contexto` y hay un camino determinista antes. El diagnóstico se conserva como registro histórico.

---

## 5. Resolución (commit `3bbae0f`, 2026-08-03) — plan auditado v2

Alcance cerrado con el usuario: **solo por la ruta OUT**, sin tocar Cuantificar. Plan:
`Planes/plan_out_contexto_no_soportado_2026-08-03.md`.

### 5.1 — Causa 2.1 (OUT sin contexto): **RESUELTA** (Pieza A)

`respuesta_out.redactar_out` ahora acepta `contexto` (el dict de `maquina_q._CTX`) e inyecta una
línea de contexto en `PROMPT_OUT` con la entidad del hilo reciente (`_linea_contexto`). Además se
añadió una regla dura al prompt: *"NO inventes fechas, periodos («el mes pasado») ni datos que el
usuario no haya escrito"* — ataca directo la invención factual del ejemplo 3. La frontera dura se
conserva intacta (el contexto solo sirve para reconocer el hilo, no para responder la pregunta ajena).

### 5.2 — Causa 2.2 (no distingue off-topic de en-dominio-no-soportado): **PARCIALMENTE resuelta** (Pieza B)

Nuevo módulo determinista `no_soportado.py` (sin LLM): reconoce las FORMAS de capacidad no
construida enumeradas en `config/variables_cuantificables.yaml` → `no_soportado:` (rango de días,
trimestre, año completo, semana). Cuando el hilo YA tiene una entidad resuelta (`_CTX` con entidad
⇒ dominio confirmado) y la pregunta calza una de esas formas, OUT responde un **rechazo honesto
determinista** que nombra la entidad y dice qué SÍ puede — el molde de `cuantificar/ejecutor` por la
ruta OUT. Ejemplo real del §1: *"Sobre RUBIALES: me pediste un rango de días y por ahora solo puedo
darte el mes completo. Si me nombras el mes, te doy esa cifra."*

**Por qué PARCIAL (limitación aceptada, honesta):** en arranque frío **sin** entidad en contexto,
`"¿cuántos días tiene un trimestre?"` (ajena) y `"del primer trimestre ¿cuánto?"` (dominio) son
indistinguibles sin LLM — no se puede afirmar "no soportado" con honestidad. Esas preguntas siguen
cayendo al OUT genérico (ahora con contexto si lo hay). Separar ambas en frío exigiría escalar a la
Capa 2 (LLM), descartado por el usuario. Los 3 síntomas del §1 eran mid-conversación → cubiertos.

### 5.3 — Detalles de auditoría que moldearon la solución (2 correcciones reales)

- **El mensaje de B NUNCA termina en pregunta sí/no:** un *"¿Quieres…?"* haría que un *"sí"* del
  usuario caiga en el drill `_AFIRM` de `maquina_q._continuacion` (ctx cuantificar) y se reescriba a
  `"acumulado de {entidad}"` → habría OFRECIDO el mes y ENTREGADO el acumulado. Bug evitado.
- **`ANUAL` se excluye si el texto trae `PROMEDIO`:** `"promedio anual"` es la referencia
  `promedio_anio` que Cuantificar SÍ soporta (Fase 4) — no un "año completo no soportado".

### 5.4 — Fuera de esta resolución (deuda anotada)

- **Downgrade silencioso en Cuantificar:** una pregunta CON entidad + rango de días NO cae en OUT —
  entra a Cuantificar y `slots.py` la degrada al mes completo, entregando otra cifra con la misma
  confianza. Es un defecto de MAYOR impacto (da un número equivocado, no una disculpa) y vive en la
  ruta con entidad, no en OUT. Queda como plan futuro propio.
- **Trazar en la libreta que la respuesta fue "rechazo honesto":** exigiría columna nueva =
  migración. Consecuencia: `senales` Señal 3 puede marcar `sospecha` por abandono tras un
  `desconocido` de capa `llm`/`regex+llm` aunque la respuesta B haya sido buena (el camino
  mayoritario `regex+filtro` ya está excluido).

### 5.5 — Validación

**Estática (dev, regla de RAM):** `py_compile` + imports OK; `test_no_soportado.py` **6/6**;
no-regresión `test_consulta_v2_clasificador` **60/60** (baseline idéntico); retrocompat de los 4
tests OUT existentes.

**En vivo (servidor de pruebas, backend :8088, Ollama gemma4 CALIENTE) — 2026-08-03:** script de
humo `backend/smoke_out_contexto.py` (2 turnos con `conversation_id` compartido, solo `urllib`) →
**TODOS los checks duros PASARON**:
- **Pieza B:** T1 «producción de Rubiales» → cuantificar, pobló `_CTX` con RUBIALES. T2 «en mayo,
  los 17 días ¿cuánto ha producido?» → `desconocido/regex+filtro`, mensaje *«Sobre RUBIALES: me
  pediste un rango de días y por ahora solo puedo darte el mes completo. Si me nombras el mes, te
  doy esa cifra.»* (nombra la entidad, sin dígitos, sin «¿Quieres»).
- **Pieza A:** T3 off-topic (clima) → el LLM reconoció el tema, NO lo respondió, NO inventó
  periodos, ofreció los 3 temas.
- **Gate de B sin contexto:** T-neg «cuanto en el primer trimestre?» (conversación nueva) → OUT
  genérico, B NO disparó (confirmado que sin entidad en contexto no se afirma «no soportado»).

El único rojo inicial fue un supuesto de enrutamiento DEL SCRIPT de humo (la frase negativa se
enrutaba a cuantificar en vez de OUT), corregido en el commit `2d54f2d` — el código de la
implementación no cambió.

**Pendiente:** corrida formal de paridad gemma4 (ya verificado con gemma4 caliente en :8088) y
deploy en 139.
