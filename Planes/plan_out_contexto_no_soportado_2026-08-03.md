# Plan v2 (auditado) — OUT con contexto + detector determinista de "no soportado" (Motor Q v2)

> **Modo:** ejecutable por un Executor externo (sin contexto previo ni conocimiento del repo).
> Todo lo necesario está aquí. Rutas ABSOLUTAS. Código de referencia COMPLETO. Decisiones CERRADAS.
> **Fecha:** 2026-08-03 · **Planner:** Claude · **Auditado v2** según §0.2 del CLAUDE.md de INGESTA.

**Cobertura de piezas: entrada 2 → salida 2** (A: OUT con contexto · B: detector determinista). Sin recortes.

---

## 0. Qué corrigió la auditoría (delta v1 → v2)

La v1 de este plan se auditó contra el código real. **8 hallazgos, todos incorporados abajo.** Se listan
porque explican por qué el código de §5 es como es (no "mejorable a ojo"):

| # | Hallazgo | Efecto si no se corrige | Corrección aplicada |
|---|---|---|---|
| **H1** 🔴 | **Colisión de UX con el drill de afirmación.** La v1 cerraba el mensaje de B con *"¿Quieres que te dé el mes completo?"*. Si el usuario responde **"sí"**, `maquina_q._continuacion` (línea ~87) matchea `t in _AFIRM` con `ctx["grupo"]=="cuantificar"` y reescribe a **`"acumulado de {entidad}"`** → el motor devolvería el **ACUMULADO**, no el mes ofrecido. | El bot ofrece A y entrega B. Bug NUEVO introducido por este plan. | El mensaje de B **nunca termina en pregunta sí/no**. Cierra invitando a una frase explícita ("Si me nombras el mes…"). |
| **H2** 🔴 | **`ANUAL` colisiona con una referencia SOPORTADA.** `cuantificar/slots.py::_REF_MATCH` reconoce `PROMEDIO ANUAL`/`PROMEDIO DEL AÑO` como la referencia **`promedio_anio`**, que Cuantificar SÍ soporta (Fase 4). | B respondería *"me pediste un año completo, no puedo"* ante algo que el motor **sí** calcula. | La forma `anio` se descarta si el texto trae `PROMEDIO` (guarda explícita en el detector). |
| **H3** 🟠 | Regex de trimestre `\b[1-4]\s*[TQ]\b` / `\b[TQ][1-4]\b` (abreviaturas "4T", "Q1"): valor marginal, riesgo real de falso positivo contra códigos/nombres del catálogo. | Falsos "no soportado" impredecibles. | **Eliminadas** ambas alternativas. Solo `TRIMESTRE`/`TRIMESTRAL`. |
| **H4** 🟠 | La validación V6 de la v1 recargaba settings por variable de entorno (`reload(config)`). `respuesta_out` evalúa `_s = get_settings()` **en el import** y `get_settings` cachea → el reload no aplica de forma fiable. | Validación que "pasa" sin probar nada, o falla por motivos ajenos. | Sustituida por un **pytest con `monkeypatch.setattr(R._s, ...)`** — el patrón que los tests existentes YA usan (`test_consulta_v2_clasificador.py:338/348/358`). |
| **H5** 🟡 | `test_consulta_v2_clasificador.py::test_out_solo_en_trafico_real` (línea 371) define el doble como `def _boom(t, usuario=None)`. Tras el cambio la firma real lleva `contexto`. **Hoy no rompe** (ese test usa `log=False` y nunca entra a la rama OUT), pero queda una trampa: si alguien lo pasa a `log=True`, fallaría con `TypeError` en vez del `AssertionError` claro. | Trampa latente para el próximo que toque el test. | Se amplía la firma del doble a `(t, usuario=None, contexto=None)`. Cambio de 1 línea, conserva la intención. |
| **H6** 🟡 | Conteo de tests mal declarado en la v1 ("7 passed" con 5 funciones). | Criterio de aceptación no verificable. | Conteo exacto: **6 funciones → `6 passed`**. |
| **H7** 🟡 | **Colisión de nombre (conceptual, no técnica):** `config/variables_cuantificables.yaml` ya tiene una sección `no_soportado:` (y `cuantificar/catalogo.py:19` la valida como obligatoria), que declara en PROSA "año / trimestre / semana". El módulo nuevo se llama igual y lo declara en REGEX. Namespaces distintos → no hay conflicto de import, pero sí riesgo de **deriva** entre ambos. | Dos fuentes de verdad divergiendo en silencio. | Se conserva el nombre (alineación conceptual deseable) + **docstring que cruza referencia explícita** al YAML como fuente declarativa. |
| **H8** 🟡 | **Control 2 (libreta):** `senales.escanear()` Señal 3 marca `sospecha` por abandono tras `desconocido` cuando `capa in ('llm','regex+llm')`. Si B responde bien y el usuario se va satisfecho, esa fila puede marcarse "sospechosa". (No aplica al camino mayoritario `regex+filtro`, que ya está excluido.) | Ruido menor en la cola de revisión. | **Limitación aceptada y documentada** (§9). Trazarlo exigiría una columna nueva = migración = fuera de alcance. |

**Verificado además (sin cambios necesarios):** el frontend pinta `d.mensaje` con `esc()` dentro de
`<p class="v2-msg">` (`multitab_shell.js:3481`) → texto plano, **cero cambios de JS**; los 3 tests
existentes de `redactar_out` usan `(texto)` y `(texto, usuario=…)` → el default `contexto=None`
los mantiene verdes; `_CTX` en el punto de lectura refleja el turno ANTERIOR (se actualiza al final de
`clasificar`), que es justo el "hilo reciente" buscado.

---

## 1. Contexto

El Motor Q v2 (`consulta_v2/`) clasifica cada pregunta libre en 4 grupos: `jerarquizar`,
`cuantificar`, `analizar`, `desconocido`. Cuando cae en **`desconocido` (grupo OUT)**, el chat responde
un texto redactado por el LLM (`respuesta_out.redactar_out`) o un fallback estático.

**Deuda de calidad identificada** (documentada en
`c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\HALLAZGO_out_pipeline_sin_contexto.md`):

1. **OUT redacta SIN contexto conversacional.** El prompt solo recibe la última frase aislada
   (`{texto}`), nunca la entidad de la última resolución. Resultado real observado: tres preguntas
   seguidas de una charla sobre Rubiales cayeron en OUT y el bot solo pudo parafrasear en abstracto
   ("el último periodo", "el mes pasado" — esto último **objetivamente falso**, mayo era el mes en curso).
2. **OUT no distingue "fuera de dominio" de "en dominio pero no soportado".** `"¿capital de Francia?"`
   y `"los 17 días ¿cuánto ha producido?"` reciben el mismo rechazo genérico.

**Caso de referencia (trazado contra el código, sirve de prueba de aceptación conceptual):**
`"En mayo, los 17 días ¿cuánto ha producido?"` con el hilo ya resuelto en RUBIALES →
Capa 1 atrapa `CUANT[OA]S?` (patrón genérico) → filtro de dominio: `detectar_entidad` no halla entidad
y `nivel_dominio` es `None` (el vocabulario tiene `PRODUCCION`, no `PRODUCIDO`) → **`desconocido`,
capa `regex+filtro`** → hoy: disculpa genérica; **con este plan:** *"Sobre RUBIALES: me pediste un rango
de días y por ahora solo puedo darte el mes completo. Si me nombras el mes, te doy esa cifra."*

**Decisiones de alcance del usuario (2026-08-03, cerradas):**
- Se implementan **Pieza A** y **Pieza B**, **ambas solo por la ruta OUT**.
- **NO** se toca Cuantificar (el downgrade silencioso de rango-de-días *con* entidad queda como deuda
  aparte, fuera de este plan).
- B es **determinista enumerado** (sin LLM) y **solo afirma "no soportado" cuando hay contexto de
  entidad** (el hilo confirma dominio). En arranque frío sin entidad, la pregunta sigue cayendo al OUT
  genérico — limitación aceptada.

**Molde de referencia (ya existe en el repo; se replica su ESTILO, no se copia código):** el "rechazo
honesto" está en `cuantificar/ejecutor.py:75-79` (P50) y `respuesta_analizar.py:53-57` (diferidas/economía):
decir QUÉ no se puede, POR QUÉ, y QUÉ sí.

---

## 2. Objetivo

- **A:** que la respuesta OUT del LLM reciba el contexto reciente (`_CTX`) para reconocer el hilo y
  **no inventar periodos ni cifras**.
- **B:** que, con entidad ya resuelta en el hilo y una pregunta con FORMA de capacidad no construida
  (rango de días, trimestre, año completo, semana), el chat responda un **rechazo honesto determinista**
  que nombra la entidad y dice qué SÍ puede — **sin gastar el LLM**.

**Regla madre respetada:** Python decide (B es 100% determinista); el LLM solo redacta el saludo de OUT (A).

---

## 3. Prerequisitos (verificar ANTES de tocar nada)

Ejecutar desde `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend`:

```
uv run python -c "import app.features.consulta_v2.maquina_q, app.features.consulta_v2.respuesta_out, app.features.consulta_v2.dominio, app.features.consulta_v2.normaliza; print('IMPORTS OK')"
```
**Esperado:** `IMPORTS OK`. Si falla → detenerse y reportar (el árbol de módulos no es el que asume este plan).

**Baseline de no-regresión (capturar ANTES de editar, se compara en V4):**
```
uv run pytest tests/test_consulta_v2_clasificador.py -q
```
Anotar la línea de resumen (p. ej. `47 passed`). Ese es el número a igualar después.

**Regla de entorno (NO negociable):** en dev NO se levanta el backend ni el LLM (RAM 8 GB). Toda la
validación es **estática**: `py_compile` + tests PUROS (sin BD, sin LLM) + pytest existente. La
verificación en navegador / LLM en vivo la hace el usuario en el servidor de pruebas — **no** es parte
de este plan.

---

## 4. Inventario de archivos

(`...` = `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA`)

| Archivo (ruta absoluta) | Acción |
|---|---|
| `...\INGESTA\Rep_Prod\backend\app\features\consulta_v2\no_soportado.py` | **CREAR** (Pieza B) |
| `...\INGESTA\Rep_Prod\backend\app\features\consulta_v2\respuesta_out.py` | **EDITAR** (Pieza A) |
| `...\INGESTA\Rep_Prod\backend\app\features\consulta_v2\maquina_q.py` | **EDITAR** (integrar A + B en la rama OUT) |
| `...\INGESTA\Rep_Prod\backend\tests\test_no_soportado.py` | **CREAR** (tests puros A + B) |
| `...\INGESTA\Rep_Prod\backend\tests\test_consulta_v2_clasificador.py` | **EDITAR** (1 línea, H5) |

**NO se toca:** `dominio.py`, `patrones.py`, `clasificador_llm.py`, `cuantificar/`, `config/*.yaml`,
migración 010, `log.py`, `senales.py`, el golden, ni `static/` (frontend). El grupo sigue siendo
`desconocido` — **sin 5º grupo, sin cambios de enum, sin JS**.

---

## 5. Especificación (código literal)

### 5.1 — CREAR `no_soportado.py`

Ruta: `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend\app\features\consulta_v2\no_soportado.py`

Crear el archivo con este contenido EXACTO:

```python
"""no_soportado.py — detector determinista de FORMAS de pregunta EN dominio pero fuera de capacidad.

Espejo conceptual de dominio.py: módulo PURO (sin BD, sin LLM), testeable igual que patrones.py.
NO decide dominio — eso ya lo hizo el filtro de dominio. Solo reconoce, entre las preguntas que YA
cayeron en 'desconocido', las que tienen la FORMA de una capacidad que el motor todavía no construye.

FUENTE DECLARATIVA (H7): la lista de capacidades ausentes vive en prosa en
`config/variables_cuantificables.yaml` → sección `no_soportado:` ("año / trimestre / semana",
motivo "v1 solo parsea MES"). Ese YAML NO se puede usar para hacer matching (es prosa, no patrones),
así que aquí viven los REGEX equivalentes. Si el YAML gana o pierde una capacidad, ACTUALIZAR AMBOS.

🔑 Este detector solo se CONSULTA cuando hay contexto de entidad (el hilo confirma dominio). Razón
(verificada 2026-08-03): en arranque frío "¿cuántos días tiene un trimestre?" (ajena) y "del primer
trimestre ¿cuánto?" (dominio) traen la MISMA palabra — sin LLM no se puede afirmar "no soportado" con
honestidad. Con contexto sí. El gate vive en maquina_q._clasificar_core, no aquí.

🔑 El mensaje NUNCA termina en una pregunta sí/no (H1): un "sí" del usuario cae en el drill de
afirmación de maquina_q._continuacion (`t in _AFIRM` + ctx cuantificar) y se reescribe a
"acumulado de {entidad}" — es decir, entregaría el ACUMULADO en vez de lo ofrecido. Por eso el cierre
invita a una frase explícita.

Regex con \\b sobre texto NORMALIZADO (norm(): UPPER, sin acentos, espacios colapsados). norm() NO
retira signos ¿?, pero \\b los maneja (frontera entre '¿' y letra). Compilados en el import.
"""
import re

from app.features.consulta_v2.normaliza import norm

# H2: "promedio anual"/"promedio del año" es la referencia SOPORTADA `promedio_anio`
# (cuantificar/slots.py::_REF_MATCH, Fase 4) → si el texto trae PROMEDIO, la forma `anio` NO aplica.
_RX_PROMEDIO = re.compile(r"\bPROMEDIO\b")

# (codigo, regex, que_pidio, que_si_puedo, sugerencia_de_reformulacion)
# H3: sin abreviaturas de trimestre ("4T"/"Q1"): valor marginal y falsos positivos contra el catálogo.
_FORMAS = [
    ("rango_dias",
     re.compile(r"\bENTRE\s+EL\s+\d+\s+Y\s+EL\s+\d+|\bDEL\s+\d+\s+AL\s+\d+|"
                r"\bLOS\s+\d+\s+DIAS|\b\d+\s+DIAS\s+DE\b|\bPRIMEROS\s+\d+\s+DIAS"),
     "un rango de días", "el mes completo",
     "Si me nombras el mes, te doy esa cifra."),
    ("trimestre",
     re.compile(r"\bTRIMESTRE|\bTRIMESTRAL"),
     "un trimestre", "un mes puntual o el acumulado del año",
     "Dime el mes que te interesa, o pídeme el acumulado del año."),
    ("anio",
     re.compile(r"\bTODO\s+EL\s+ANO|\bEN\s+EL\s+ANO\s+20\d\d|\bDURANTE\s+20\d\d|\bANUAL\b"),
     "un año completo", "un mes puntual o el acumulado del año",
     "Dime el mes que te interesa, o pídeme el acumulado del año."),
    ("semana",
     re.compile(r"\bSEMANA|\bSEMANAL"),
     "una semana", "el mes completo",
     "Si me nombras el mes, te doy esa cifra."),
]


def detectar(texto: str):
    """Código de la 1ª forma no-soportada que calza, o None. Determinista y puro."""
    t = norm(texto or "")
    for cod, rx, _pidio, _puedo, _sug in _FORMAS:
        if cod == "anio" and _RX_PROMEDIO.search(t):
            continue                      # H2: es la referencia promedio_anio, que SÍ se soporta
        if rx.search(t):
            return cod
    return None


def mensaje(codigo: str, entidad: str) -> str:
    """Rechazo honesto (molde de cuantificar/ejecutor): nombra la entidad, dice qué pidió, qué SÍ
    puede y cómo reformular. Determinista — jamás pasa por el LLM. Sin pregunta sí/no (H1)."""
    tabla = {c: (pidio, puedo, sug) for c, _rx, pidio, puedo, sug in _FORMAS}
    pidio, puedo, sug = tabla.get(
        codigo, ("ese periodo", "el mes completo", "Si me nombras el mes, te doy esa cifra."))
    return (f"Sobre {entidad}: me pediste {pidio} y por ahora solo puedo darte {puedo}. {sug}")
```

### 5.2 — EDITAR `respuesta_out.py` (Pieza A)

Ruta: `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend\app\features\consulta_v2\respuesta_out.py`

**A1 — reemplazar la constante `PROMPT_OUT`.**

Texto ACTUAL a reemplazar (desde `PROMPT_OUT = """Eres` hasta `JSON:"""` inclusive):

```python
PROMPT_OUT = """Eres el asistente conversacional de producción de hidrocarburos de Ecopetrol.
El usuario hizo una pregunta que está FUERA de tu dominio (no es sobre producción petrolera de Ecopetrol).

Escribe una respuesta breve, cordial y NATURAL (2 o 3 oraciones, en español) que:
1. Mencione con tacto EL TEMA CONCRETO que preguntó, para reconocer su mensaje (ej.: "sobre el clima…", "el precio del dólar…") — pero SIN responderlo.
2. Le explique con amabilidad que ese tema se sale del contexto de este asistente.
3. Le ofrezca los tres temas que SÍ manejas: estructura organizacional, cifras de producción y análisis de desempeño.
4. Le pregunte en cuál de esos temas quiere que lo ayudes.

REGLA ABSOLUTA: NUNCA respondas la pregunta del usuario. NO des cifras, definiciones, cálculos ni explicaciones sobre su tema.
Cada respuesta debe sonar distinta y humana, NO una plantilla fija. Adapta las palabras al tema que preguntó.
{saludo}
Responde SOLO con JSON válido, sin markdown: {{"respuesta": "<el texto>"}}

Pregunta del usuario: {texto}
JSON:"""
```

Texto NUEVO (reemplazo EXACTO — añade `{contexto}` y la regla anti-invención):

```python
PROMPT_OUT = """Eres el asistente conversacional de producción de hidrocarburos de Ecopetrol.
El usuario hizo una pregunta que está FUERA de tu dominio (no es sobre producción petrolera de Ecopetrol).

Escribe una respuesta breve, cordial y NATURAL (2 o 3 oraciones, en español) que:
1. Mencione con tacto EL TEMA CONCRETO que preguntó, para reconocer su mensaje (ej.: "sobre el clima…", "el precio del dólar…") — pero SIN responderlo.
2. Le explique con amabilidad que ese tema se sale del contexto de este asistente.
3. Le ofrezca los tres temas que SÍ manejas: estructura organizacional, cifras de producción y análisis de desempeño.
4. Le pregunte en cuál de esos temas quiere que lo ayudes.

REGLA ABSOLUTA: NUNCA respondas la pregunta del usuario. NO des cifras, definiciones, cálculos ni explicaciones sobre su tema.
REGLA ABSOLUTA: NO inventes fechas, periodos ("el mes pasado") ni datos que el usuario no haya escrito.
Cada respuesta debe sonar distinta y humana, NO una plantilla fija. Adapta las palabras al tema que preguntó.
{contexto}{saludo}
Responde SOLO con JSON válido, sin markdown: {{"respuesta": "<el texto>"}}

Pregunta del usuario: {texto}
JSON:"""
```

**A2 — insertar el helper `_linea_contexto` INMEDIATAMENTE ANTES de la línea
`def redactar_out(texto: str, usuario: str | None = None) -> dict:`:**

```python
def _linea_contexto(contexto) -> str:
    """Una línea de CONTEXTO para el prompt, o "" si no hay entidad reciente. `contexto` es el dict
    que maquina_q._CTX guarda por conversación (jerarquizar: {entidad,nivel,hijos,ofrece_produccion};
    cuantificar: {grupo,entidad,producto}). Lee SOLO entidad/producto — jamás cifras, y nunca la
    clave `hijos` (un set grande que no aporta al saludo)."""
    ent = (contexto or {}).get("entidad")
    if not ent:
        return ""
    prod = (contexto or {}).get("producto")
    extra = f" (producto {prod})" if prod and prod != "crudo" else ""
    return (f"CONTEXTO: la conversación reciente trató sobre «{ent}»{extra}. Si la nueva pregunta "
            f"parece continuar ese hilo, reconócelo con naturalidad; si es otro tema, ignora este "
            f"contexto. NO uses el contexto para inventar cifras.\n")
```

**A3 — cambiar la firma y el `.format` de `redactar_out`.**

Texto ACTUAL a reemplazar:

```python
def redactar_out(texto: str, usuario: str | None = None) -> dict:
    """Redacta la respuesta al grupo OUT. NUNCA lanza.
    Devuelve {"texto": str, "fuente": "llm"|"fallback", "diag": None|motivo}."""
    if not _s.consulta_out_llm:
        return {"texto": TEXTO_FALLBACK, "fuente": "fallback", "diag": "flag_off"}
    saludo = f"Dirígete al usuario por su nombre: {usuario}." if usuario else ""
    prompt = PROMPT_OUT.format(texto=texto, saludo=saludo)
```

Texto NUEVO (reemplazo EXACTO):

```python
def redactar_out(texto: str, usuario: str | None = None, contexto=None) -> dict:
    """Redacta la respuesta al grupo OUT. NUNCA lanza. `contexto` = dict de maquina_q._CTX (o None):
    su entidad se inyecta en el prompt para reconocer el hilo SIN romper la frontera dura (el LLM
    sigue teniendo prohibido responder la pregunta ajena).
    Devuelve {"texto": str, "fuente": "llm"|"fallback", "diag": None|motivo}."""
    if not _s.consulta_out_llm:
        return {"texto": TEXTO_FALLBACK, "fuente": "fallback", "diag": "flag_off"}
    saludo = f"Dirígete al usuario por su nombre: {usuario}." if usuario else ""
    prompt = PROMPT_OUT.format(texto=texto, saludo=saludo, contexto=_linea_contexto(contexto))
```

El resto de `redactar_out` (`try/except`, parseo defensivo, `return`) **NO se toca**.

### 5.3 — EDITAR `maquina_q.py`

Ruta: `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend\app\features\consulta_v2\maquina_q.py`

**M1 — añadir el import** justo DEBAJO de la línea
`from app.features.consulta_v2 import respuesta_analizar`:

```python
from app.features.consulta_v2 import no_soportado
```

**M2 — reemplazar la rama OUT de `_clasificar_core`.**

Texto ACTUAL a reemplazar:

```python
    if grupo == "desconocido" and log:
        # OUT responde UN texto redactado por el LLM (recalca "fuera de contexto" + ofrece los 3
        # temas + pregunta cuál interesa). Solo en tráfico real (log=True): así el golden/pytest
        # (log=False) no gastan una llamada generativa por cada desconocido. Si el LLM falla o el
        # flag está off, redactar_out devuelve el floor estático → mismo texto que _mensaje.
        mensaje = respuesta_out.redactar_out(texto, usuario=usuario)["texto"]
```

Texto NUEVO (reemplazo EXACTO):

```python
    if grupo == "desconocido" and log:
        # OUT — dos caminos. Solo en tráfico real (log=True): el golden/pytest (log=False) no entran
        # aquí (no gastan generación ni tocan _CTX).
        # (B) Si el hilo YA resolvió una entidad (contexto ⇒ dominio confirmado) y la pregunta tiene
        #     la FORMA de una capacidad no construida (rango de días/trimestre/año/semana), se
        #     responde un rechazo HONESTO determinista que nombra la entidad y dice qué SÍ puede,
        #     SIN gastar el LLM. Es el molde de rechazo de cuantificar/ejecutor, por la ruta OUT.
        #     Sin entidad en contexto NO se afirma "no soportado": en frío, "¿cuántos días tiene un
        #     trimestre?" y "del primer trimestre ¿cuánto?" son indistinguibles sin LLM.
        # (A) En cualquier otro caso lo redacta el LLM, ahora CON el contexto reciente para
        #     reconocer el hilo y no inventar periodos. Si el LLM falla o el flag está off,
        #     redactar_out devuelve el floor estático → mismo texto que _mensaje.
        # 🔑 _CTX aquí refleja el turno ANTERIOR (se actualiza al final de `clasificar`) — es
        #    exactamente el "hilo reciente" que se quiere reconocer.
        ctx = _CTX.get(conversation_id) if conversation_id else None
        ent_ctx = (ctx or {}).get("entidad")
        forma = no_soportado.detectar(texto) if ent_ctx else None
        if forma:
            mensaje = no_soportado.mensaje(forma, ent_ctx)
        else:
            mensaje = respuesta_out.redactar_out(texto, usuario=usuario, contexto=ctx)["texto"]
```

**NADA más de `maquina_q.py` cambia.** Las ramas `elif grupo == "jerarquizar"` / `cuantificar` /
`analizar` quedan intactas.

### 5.4 — EDITAR `test_consulta_v2_clasificador.py` (H5, 1 línea)

Ruta: `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend\tests\test_consulta_v2_clasificador.py`

Dentro de `test_out_solo_en_trafico_real` (~línea 371), reemplazar:

```python
    def _boom(t, usuario=None):
```
por:
```python
    def _boom(t, usuario=None, contexto=None):
```

(El cuerpo `raise AssertionError(...)` y el resto del test NO se tocan.)

### 5.5 — CREAR `test_no_soportado.py`

Ruta: `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend\tests\test_no_soportado.py`

Crear el archivo con este contenido EXACTO (**6 funciones de test**):

```python
"""Tests PUROS (sin BD, sin LLM) de la Pieza B (no_soportado) y de la Pieza A (contexto en OUT)."""
from app.features.consulta_v2 import no_soportado
from app.features.consulta_v2.respuesta_out import _linea_contexto


# --- Pieza B: detectar() reconoce las formas no soportadas -------------------------------------
def test_detecta_rango_de_dias():
    assert no_soportado.detectar("entre el 5 y el 10 de mayo") == "rango_dias"
    assert no_soportado.detectar("del 5 al 10") == "rango_dias"
    # Caso REAL del HALLAZGO (con el hilo ya resuelto en una entidad):
    assert no_soportado.detectar("En mayo, los 17 días ¿cuánto ha producido?") == "rango_dias"
    assert no_soportado.detectar("primeros 10 dias") == "rango_dias"


def test_detecta_trimestre_anio_semana():
    assert no_soportado.detectar("cuanto en el primer trimestre") == "trimestre"
    assert no_soportado.detectar("produccion anual") == "anio"
    assert no_soportado.detectar("todo el año") == "anio"
    assert no_soportado.detectar("y la semana pasada?") == "semana"


def test_negativos_no_soportado():
    # Lo que Cuantificar SÍ soporta no debe marcarse como no-soportado.
    assert no_soportado.detectar("cuanto produjo en mayo") is None          # N1 mes
    assert no_soportado.detectar("acumulado del año") is None               # N2 acumulado
    assert no_soportado.detectar("") is None
    assert no_soportado.detectar("hola") is None


def test_h2_promedio_anual_es_referencia_soportada():
    # H2: 'promedio anual'/'promedio del año' es la referencia promedio_anio (Fase 4) → NO es 'anio'.
    assert no_soportado.detectar("contra el promedio anual") is None
    assert no_soportado.detectar("vs el promedio del año") is None


# --- Pieza B: mensaje() honesto, sin pregunta sí/no (H1) --------------------------------------
def test_mensaje_nombra_entidad_y_no_termina_en_si_no():
    m = no_soportado.mensaje("rango_dias", "RUBIALES")
    assert "RUBIALES" in m
    assert "rango de días" in m and "mes completo" in m
    # H1: un "¿Quieres…?" haría que un "sí" caiga en el drill de acumulado de _continuacion.
    assert "¿Quieres" not in m
    # Determinista: la plantilla no inventa cifras (la entidad de prueba no tiene dígitos).
    assert not any(ch.isdigit() for ch in m)


# --- Pieza A: la línea de contexto solo aparece si hay entidad --------------------------------
def test_linea_contexto():
    assert _linea_contexto(None) == ""
    assert _linea_contexto({}) == ""
    assert _linea_contexto({"nivel": "campo"}) == ""            # sin 'entidad' → vacío
    linea = _linea_contexto({"entidad": "RUBIALES", "producto": "gas"})
    assert "RUBIALES" in linea and "gas" in linea
    # crudo es el default → no se explicita el producto (ruido innecesario en el prompt).
    assert "(producto" not in _linea_contexto({"entidad": "CASTILLA", "producto": "crudo"})
```

---

## 6. Orden de ejecución

1. Verificar prerequisitos y **capturar el baseline** de pytest (§3).
2. Crear `no_soportado.py` (§5.1).
3. Editar `respuesta_out.py` (§5.2 — A1, A2, A3 en ese orden).
4. Editar `maquina_q.py` (§5.3 — M1, luego M2).
5. Editar `test_consulta_v2_clasificador.py` (§5.4 — 1 línea).
6. Crear `test_no_soportado.py` (§5.5).
7. Ejecutar todas las validaciones (§8) en orden.

---

## 7. Reglas no negociables

- **NO** crear un 5º grupo ni tocar `log.GRUPOS`, la migración 010, el enum, `senales.py`, el golden ni
  `static/` (frontend). El grupo sigue siendo `desconocido`.
- **NO** tocar `cuantificar/`, `dominio.py`, `patrones.py`, `clasificador_llm.py` ni los `.yaml` de `config/`.
- **B solo se consulta con contexto de entidad**: la llamada está gated por `if ent_ctx else None`. No
  mover ese gate.
- **B es determinista y jamás llama al LLM**: `no_soportado.py` importa solo `re` y `normaliza`.
- **El mensaje de B nunca termina en pregunta sí/no** (H1) — colisiona con el drill `_AFIRM` de
  `_continuacion`, que devolvería el acumulado.
- **Frontera dura de OUT intacta:** el prompt sigue prohibiendo responder la pregunta ajena; el contexto
  solo sirve para reconocer el hilo.
- **Backward-compat:** `redactar_out(texto, usuario)` debe seguir funcionando sin el 3.º argumento
  (`contexto=None` por defecto). No cambiar más call-sites que el de §5.3.
- **Regla de entorno:** NO levantar backend ni LLM en dev. Solo validación estática (§8).
- Estilo del repo: comentarios/docstrings en español, sin dependencias nuevas.

---

## 8. Validaciones (comando → resultado esperado)

Todas desde `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend`.

**V1 — compilación:**
```
uv run python -m py_compile app/features/consulta_v2/no_soportado.py app/features/consulta_v2/respuesta_out.py app/features/consulta_v2/maquina_q.py
```
Esperado: sin salida, exit 0.

**V2 — imports (sin BD/LLM):**
```
uv run python -c "from app.features.consulta_v2 import no_soportado, maquina_q; from app.features.consulta_v2.respuesta_out import _linea_contexto, redactar_out; print('OK')"
```
Esperado: `OK`.

**V3 — tests puros nuevos (Piezas A+B):**
```
uv run pytest tests/test_no_soportado.py -q
```
Esperado: **`6 passed`**, 0 fallos, sin conexión a BD ni LLM.

**V4 — no regresión del clasificador v2:**
```
uv run pytest tests/test_consulta_v2_clasificador.py -q
```
Esperado: **exactamente el mismo resumen capturado en el baseline de §3** (referencia histórica:
`47 passed`). No deben aparecer fallos NUEVOS ni cambiar el número de skips.

**V5 — humo determinista de B (el caso real del HALLAZGO, sin backend):**
```
uv run python -c "from app.features.consulta_v2 import no_soportado as n; f=n.detectar('En mayo, los 17 dias cuanto ha producido?'); print(f); print(n.mensaje(f,'RUBIALES'))"
```
Esperado: primera línea `rango_dias`; segunda línea una frase que contiene `RUBIALES`, `rango de días`
y `mes completo`, **sin dígitos** y **sin "¿Quieres"**.

**V6 — la nueva firma funciona en el camino fallback (sin red, con monkeypatch — H4):**
```
uv run pytest tests/test_consulta_v2_clasificador.py -q -k "out_"
```
Esperado: los 4 tests de OUT (`test_out_llm_redacta`, `test_out_llm_falla_cae_al_estatico`,
`test_out_flag_off_no_llama_llm`, `test_out_solo_en_trafico_real`) **pasan** — confirma
retrocompatibilidad de la firma y que el doble ampliado de §5.4 sigue siendo válido.

Si **cualquier** validación falla: **detenerse** y reportar comando + salida completa. No "arreglar
sobre la marcha" cambiando el alcance ni relajando una aserción.

---

## 9. Fuera de alcance (explícito)

- **Downgrade silencioso en Cuantificar** (pregunta CON entidad + rango de días → se degrada al mes
  completo y entrega otra cifra con la misma confianza). Deuda aparte, decisión del usuario 2026-08-03.
  **NO** se toca `cuantificar/`.
- **Separar off-topic de no-soportado en arranque frío SIN entidad.** No es determinable sin LLM
  (auditoría 2026-08-03); esas preguntas siguen cayendo al OUT genérico. Aceptado.
- **Trazar en la libreta que la respuesta fue "rechazo honesto" (H8).** Exigiría columna nueva =
  migración. Consecuencia conocida y aceptada: si la capa fue `llm`/`regex+llm`, `senales` Señal 3
  puede marcar `sospecha` por abandono aunque la respuesta haya sido buena. (El camino mayoritario
  `regex+filtro` ya está excluido de esa señal.)
- **5º grupo / enum / migración / frontend / escalar a Capa 2.** Nada de eso se toca.
- **Verificación en navegador, LLM en vivo y deploy 139.** Las hace el usuario en el servidor de
  pruebas tras el commit.

---

## 10. Cierre (commit + documentación)

Mensaje de commit sugerido:
```
feat(consulta_v2): OUT con contexto reciente + rechazo honesto de formas no soportadas

Pieza A: respuesta_out inyecta la entidad del hilo (_CTX) en el prompt y prohíbe inventar periodos
("el mes pasado"). Pieza B: no_soportado.py (determinista, sin LLM) — con entidad en contexto, un
rango de días/trimestre/año/semana recibe un rechazo honesto que nombra la entidad y dice qué SI
puede, en vez del OUT generico. Sin 5o grupo; sin tocar cuantificar/dominio/frontend/migracion.

Auditoria: el mensaje NO termina en pregunta si/no (colisionaba con el drill _AFIRM que devuelve el
acumulado) y 'promedio anual' se excluye de la forma 'anio' (es la referencia soportada promedio_anio).
```

Tras el commit, actualizar:
- `INGESTA/Rep_Prod/CLAUDE.md` §12 — fila nueva de bitácora (siguiente ID de sesión disponible).
- `INGESTA/Rep_Prod/HALLAZGO_out_pipeline_sin_contexto.md` — marcar §2.1 **resuelta** (Pieza A) y §2.2
  **parcialmente resuelta** (Pieza B: solo con entidad en contexto; en frío sigue abierta).
