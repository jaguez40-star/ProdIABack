# plan_CAPA1-DISTRIBUCION-SIN-PRODUCCION_20260903 — Que la Capa 1 reclame las preguntas de distribución que no dicen «producción»

> Plan **v2** auditado (flujo profesional §10 de `CLAUDE.md`). Mapeo + auditoría + diagnóstico
> ejecutados ANTES de escribir esta especificación: **todas las cifras de §1 están medidas
> contra el código real**, ninguna es supuesta.
>
> **Origen:** el 2026-09-03, validando en Pruebas el plan `plan_VOCABULARIO-DISTRIBUCION_20260901.md`,
> la pregunta «¿Qué porcentaje del crudo aporta el campo Castilla?» respondió
> `Motor v2 · Desconocido` con el genérico «No logré entender bien tu pregunta». Se creyó
> un fallo del ranking. **No lo es**: la pregunta nunca llegó a `cuantificar`.
>
> **Cambios de v1 → v2** (segunda pasada: el patrón se aplicó de verdad y se midió, en vez de
> razonarlo):
> 1. 🔴 **`DESGLOS\w+` ROMPE un test y sale del patrón.** Aplicado el patrón de v1, la suite
>    daba **11 fallos en vez de 10**: `test_jerarquia_drill_down_verbos_alternos` se ponía rojo
>    porque «Desglósame la gerencia PDH por campo» pasaba de `jerarquizar` a `cuantificar`.
>    Es la única palabra cuya colisión cae del lado **peligroso** (H4-bis). Retirada, la suite
>    vuelve a 10/637 exactos.
> 2. 🔴 **El import de los tests de v1 era falso.** `test_consulta_v2_clasificador.py:10` ya
>    importa `clasificar_capa1` **directo**, no `as _PAT`. El código de v1 habría duplicado el
>    import y usado un alias inexistente.
> 3. ➕ **Golden medido contra el patrón, no supuesto:** **0 de los 92 casos** contienen el
>    vocabulario nuevo, y con el patrón aplicado el golden da 92/85, idéntico. Deja de ser un
>    riesgo a vigilar y pasa a ser un hecho.
> 4. ➕ **La precedencia verificada end-to-end** (H4): 5 colisiones reales con `analizar`
>    (`GAP`, `META`, `DIFERIDAS`, `P50`) medidas con el patrón cargado — las 5 se quedan en
>    `analizar`, como el plan afirmaba.

---

## 0. Contexto para el agente EXECUTOR

**Proyecto:** ProdIA — asistente conversacional de producción (Ecopetrol). Este plan toca
**solo el backend**, y dentro de él **un solo archivo de producción, que es un YAML**.

**Raíz del repo:** `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\`
⚠️ Doble anidamiento: el paquete Python vive en `backend\backend\app\...`.

**Ruta exacta del archivo a modificar:**
`C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\config\patrones_grupo.yaml`

⚠️ **Ojo con la ruta**: el archivo está en `consulta_v2\config\`, **no** en `consulta_v2\`.
Un `grep` en la carpeta padre no lo encuentra (le pasó al auditor de este plan).

**Ruta del archivo de tests:**
`C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\tests\test_consulta_v2_clasificador.py`

### Cómo correr las cosas

Todo desde `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend`, PowerShell normal, **sin
consola de administrador**:

```powershell
cd 'C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend'
.venv\Scripts\python.exe -m pytest tests/test_consulta_v2_clasificador.py -q
```

⚠️ **Este YAML se carga UNA vez al arranque** (lo declara su propia cabecera, línea 11-12).
En los tests no importa (cada proceso lo relee), pero **en Pruebas hay que reiniciar INGESTA**
o el cambio no aplica. Eso es validación humana (§6.2), no tarea del executor.

### Convenciones del archivo destino

Leer la cabecera del YAML (líneas 1-13) antes de tocarlo. Lo esencial:

- Los patrones son **regex sobre texto NORMALIZADO**: `norm()` → MAYÚSCULAS, sin acentos,
  espacios colapsados. Escribir `PORCENTAJE`, nunca `porcentaje` ni `Porcentaje`.
- `patrones.py` **no tiene lógica**: solo carga y compila. Todo el comportamiento está aquí.
- **Cada patrón lleva un comentario encima explicando qué NO debe tragarse.** Es la convención
  más fuerte del archivo y no es decorativa: es cómo se evitó tres veces una regresión. El
  patrón nuevo debe llevarlo igual.
- El archivo declara su propia regla de crecimiento (líneas 6-9): casos verificados + golden
  en verde **antes** de dar por bueno un patrón.

---

## 1. Hallazgos de la auditoría (determinan la §3)

### 🔴 H1 — La causa raíz: `cuantificar` depende de la palabra «PRODUCCIÓN»

**Medido** con `patrones.clasificar_capa1()`:

| Pregunta | Capa 1 |
|---|---|
| «¿Qué participación tiene cada campo en la **producción** total de crudo?» | `('cuantificar', ['\bPRODUCCION\b', 'TOTAL\s+DE'])` |
| «¿Qué porcentaje del **crudo** aporta el campo Castilla?» | **`(None, [])`** |

La segunda no dice «producción», dice «crudo». Ningún patrón de `cuantificar` la reclama →
cae a Capa 2 (LLM) → el LLM devolvió `Desconocido`.

**El alcance NO es la forma telegráfica** (que es lo que el plan anterior había anotado como
fuera de alcance en su H2). Medido sobre 8 formas con producto explícito y sin «producción»:

```
--  None | Que porcentaje del crudo aporta el campo Castilla?
--  None | Que participacion tiene cada campo en el crudo total?
--  None | Como se reparte el crudo entre los campos?
--  None | Dame el share de cada campo sobre el crudo
--  None | Que fraccion del crudo produce cada campo?
--  None | distribucion % crudo por campo
--  None | Que campos encabezan el crudo en agosto?
--  None | Que campos lideran el gas este mes?
```

**8 de 8 fallan.** No es un caso borde: es toda la familia.

### 🟢 H2 — El riesgo de anclaje NO aplica: las 8 dan dominio `fuerte`

Este era el riesgo mayor del plan. **Está descartado por medición.** `dominio.nivel_dominio()`
sobre las 8:

```
fuerte | (las 8, todas)
None   | "Como se distribuye la participacion en el equipo de futbol?"   ← control negativo
```

⇒ El patrón nuevo va como **genérico** (NO se añade a `patrones_anclados`), y aun así enruta
directo sin LLM porque el nombre del producto ya da `fuerte`. Es exactamente el criterio que
el propio archivo documenta para los patrones de N5 (líneas 184-187): *«GENÉRICOS a propósito
(NO van a patrones_anclados): así pasan por el filtro de dominio y exigen entidad O
vocabulario. Anclarlas repetiría el error del 2026-08-02 ("mejores campos de la dieta
mediterránea")»*.

⚠️ **Regla derivada, no negociable:** este plan **NO toca `patrones_anclados`**. Si el
executor siente la tentación de anclar el patrón nuevo, la respuesta es no — y el porqué está
escrito en las líneas 250-262 del YAML.

### 🟢 H3 — El patrón candidato: 10 de 10 correctos, incluidos 7 controles negativos

Regex probado en un proceso limpio contra los casos que **deben** y los que **no deben** calzar:

```
  ok  SI | Que porcentaje del crudo aporta el campo Castilla? | PORCENTAJE
  ok  SI | Como se reparte el crudo entre los campos?         | REPARTE
  ok  SI | Que campos encabezan el crudo en agosto?           | ENCABEZAN
  ok  NO | Por que bajo la produccion de crudo en Castilla?   |
  ok  NO | Que campos pesan en el gap?                        |
  ok  NO | Analiza el comportamiento del producto crudo       |
  ok  NO | Cuanto crudo produjo Rubiales?                     |
  ok  NO | Cuales campos tiene el activo Castilla?            |
  ok  NO | Como vamos este mes?                               |
  ok  NO | Que paso con la produccion ayer?                   |
```

Los 4 controles críticos son los de `analizar` (`PESAN`, `ANALIZA`, `POR QUE`, `QUE PASO CON`):
ninguno calza, así que el patrón **no le disputa nada** a ese grupo.

### 🟢 H4 — `analizar` gana por `precedencia_colision` — VERIFICADO end-to-end

`precedencia_colision: [analizar, cuantificar, jerarquizar]` (línea 246), aplicada en
`patrones.py:69-72` (paso 3 de `clasificar_capa1`: en colisión recorre la precedencia y
devuelve el primero que esté).

**No es teoría: se aplicó el patrón al YAML y se midió.** Hay 5 colisiones reales, y las 5
resuelven a favor de `analizar`:

| Pregunta (con el patrón cargado) | Grupo |
|---|---|
| «como se **distribuye** el **gap** de crudo entre los campos» | `analizar` |
| «que **porcentaje** de la **meta** de crudo llevamos» | `analizar` |
| «que **participacion** tienen las **diferidas** de crudo» | `analizar` |
| «cual es el **porcentaje** de cumplimiento del **P50** de crudo» | `analizar` |
| «que campos **pesan** en el gap» | `analizar` |

⇒ Frente a `analizar`, el modo de fallo es «se queda donde está hoy». Dirección segura.

### 🔴 H4-bis — Frente a `jerarquizar` la precedencia NO protege: `DESGLOS` sale del patrón

**El hallazgo que la v1 no vio.** `cuantificar` gana a `jerarquizar` en la precedencia, así que
ahí la colisión cae del lado **peligroso**.

Medido: con el patrón de v1 (que incluía `DESGLOS\w+`), la suite pasó de **10 a 11 fallos**:

```
FAILED tests/test_consulta_v2_clasificador.py::test_jerarquia_drill_down_verbos_alternos
E       AssertionError: assert 'cuantificar' == 'jerarquizar'
        clasificar("Desglósame la gerencia PDH por campo")
```

Ese test fija una corrección del 2026-08-24 (drill-down con verbos alternos: «cuelgan»,
«desglosa» caían a desconocido). **«Desglósame la gerencia PDH por campo» es drill-down
jerárquico, no una cifra.**

La ironía: el plan anterior ya lo había advertido en su propio H4 —*«desglósame el activo
Castilla por campo → jerarquizar, nunca llega»*— y aun así `DESGLOS` entró en el patrón de v1.

⇒ **`DESGLOS\w+` NO va en el patrón.** Retirada, la suite vuelve a **10 fallos / 637 pasan**,
exactos al baseline. La forma «desglósame el crudo por campo» seguirá sin llegar a
`cuantificar`, y es correcto: esa palabra pertenece a `jerarquizar` y al panel de Analizar
(`respuesta_analizar.py:57`).

### 🟠 H5 — `PESA`/`PESAN` sigue arbitrada: el patrón NO puede incluirla

Idéntico al H3 del plan anterior, y sigue vigente:

| Ubicación | Qué dice |
|---|---|
| `patrones_grupo.yaml:206` | `'QUE\s+CAMPOS?\s+PESA[N]?'` es patrón de **ANALIZAR** |
| `patrones_grupo.yaml:66-71` | Exclusión deliberada, comentada como *«decisión del usuario: ahí gana el gap»* |
| `analizar/subrouter.py:21` | `PESAN`/`PESA` en `_CAUSAL_EXPL` |

Vigilada por 4 casos del golden y 1 de `analizar_golden.yaml:9`. **Decisión cerrada del
2026-08-24. No se toca.**

### 🟡 H6 — `LIDERA?\w*` es el fragmento delicado del regex

`LIDER` como raíz suelta capturaría `LIDERAZGO`, `LIDERES`, `LIDERANDO`. En el dominio no hace
daño (no hay preguntas de liderazgo organizacional en el motor), pero el filtro de dominio es
el único guardián: «¿quién es el **líder** del equipo?» no tiene producto → `nivel_dominio`
None → OUT. **Verificado con el control negativo del fútbol en H2.**

⇒ Se acota a `LIDERA\w*` + `LIDERO` + `LIDERARON` (formas verbales), **no** `LIDER\w*`. Así
`LIDERAZGO` y `LIDERES` quedan fuera por construcción y no dependen solo del filtro.

### 🟡 H7 — Este patrón NO reemplaza al detector de `ranking.py`, lo alimenta

Son dos capas distintas y ambas hacen falta:

| Capa | Archivo | Qué decide |
|---|---|---|
| 1 · grupo | `patrones_grupo.yaml` (este plan) | ¿esta pregunta es de `cuantificar`? |
| 2 · forma | `cuantificar/ranking.py` (plan anterior, ya en `main`) | dentro de cuantificar, ¿es un ranking N5? |

El vocabulario se repite a propósito entre las dos. **No se unifican**: viven en niveles
distintos del motor y tienen guardianes distintos (aquí el filtro de dominio, allí el token de
nivel). El executor **no** debe intentar importar `_DISTRIBUCION` desde `ranking.py` al YAML:
el YAML no ejecuta Python.

### 🟢 H8 — El test de anclados obliga a sincronizar, pero aquí no aplica

`test_anclados_existen_en_patrones` compara **literalmente** las cadenas de
`patrones_anclados` contra las de `grupos`. Como este plan **no toca anclados** (H2), ese test
no se ve afectado. Se menciona para que el executor no se asuste si lo ve en la suite.

### 🟢 H10 — El golden NO puede moverse: 0 de 92 casos contienen este vocabulario

**Medido dos veces, por vías independientes:**

1. Barrido de `clasificacion_golden.yaml` con el regex del patrón: **0 de 92 casos calzan**.
2. Golden ejecutado **con el patrón aplicado al YAML**: `pct: 92 · aciertos: 85` — idéntico
   al baseline sin patrón.

⇒ El «riesgo del golden» que motivó separar este cambio en su propio plan **no existe por esta
vía**. Se sigue midiendo antes y después (§4), pero por higiene, no por riesgo.

⚠️ Esto vale para el golden de **clasificación**. La regresión real vivía en la suite de tests
(H4-bis), que es donde hay que mirar — otra razón para no confiar solo en el golden.

### 🔴 H11 — El import de los tests: `clasificar_capa1` ya está importado DIRECTO

`tests/test_consulta_v2_clasificador.py:10`:

```python
from app.features.consulta_v2.patrones import clasificar_capa1, es_anclado
from app.features.consulta_v2.dominio import hay_palabra_dominio, nivel_dominio
```

⇒ Los tests nuevos usan **`clasificar_capa1(...)` a secas**, sin alias ni import nuevo.
`nivel_dominio` también está ya importado: **no volver a importarlo dentro de la función**.
El archivo tiene 676 líneas; los tests nuevos van **al final**.

Los tests existentes devuelven la tupla y desempaquetan (`g, pats = clasificar_capa1(...)`) o
toman `[0]`. Seguir ese estilo, no inventar un helper `_grupo()` si con `[0]` basta.

### ⚪ H9 — Hallazgo colateral AJENO a este plan: `PRESUPUESTO` da dominio `fuerte`

Medido: *«¿Qué porcentaje del **presupuesto** familiar va a mercado?»* → `nivel_dominio` =
`fuerte`, porque `PRESUPUESTO` está en el vocabulario fuerte.

Con el patrón nuevo, esa pregunta pasaría a `cuantificar` y el motor intentaría responderla
(terminaría declinando por falta de entidad, sin dar cifras falsas).

⚠️ **Es un falso positivo PREEXISTENTE del vocabulario de dominio, no lo introduce este plan**
— hoy ya afecta a `'PRESUPUESTO'` en los patrones de N5 y de gap. **NO se corrige aquí**
(tocar `vocabulario_dominio.yaml` es otro cambio, con otro golden). Se registra para la
bitácora y como candidato a su propio análisis.

---

## 2. Estado actual

`app/features/consulta_v2/config/patrones_grupo.yaml`, sección `grupos.cuantificar`:

- Bloque N5 RANKING: líneas ~184-200 (`TOP \d+`, `RANKING\b`, `(MAYOR|MENOR|MAS|MENOS)\s+(CANTIDAD|PRODUCCION|VOLUMEN)`, …).
- La última línea del bloque, y de la sección, es
  `- '(MAYOR|MENOR)(ES)?\s+PRODUCTOR(ES)?\s+DE\s+(CRUDO|GAS|BLANCOS)'` (línea 200).
- Inmediatamente después empieza `  analizar:` (línea 201).

Tests del clasificador: `tests/test_consulta_v2_clasificador.py`.
⚠️ **Ese archivo tiene 1 fallo PREEXISTENTE** (`test_escalada_fallback_conserva_regex`), que es
uno de los 10 documentados en `CLAUDE.md` §6. **No es tuyo, no lo arregles, no lo cuentes como
regresión.**

---

## 3. Especificación

### 3.1 AÑADIR un patrón en `grupos.cuantificar`

**Ubicación exacta:** al final del bloque N5 RANKING, **después** de la línea
`- '(MAYOR|MENOR)(ES)?\s+PRODUCTOR(ES)?\s+DE\s+(CRUDO|GAS|BLANCOS)'` y **antes** de
`  analizar:`.

Respetar la indentación existente (4 espacios para el `- '...'`, 4 para los comentarios `#`).

```yaml
    # [2026-09-03] DISTRIBUCIÓN/DOMINANCIA CON PRODUCTO EXPLÍCITO. Medido en Pruebas: «¿qué
    # porcentaje del CRUDO aporta el campo Castilla?» caía en desconocido — 8 de 8 formas de
    # pedir el reparto fallaban por decir "crudo"/"gas" en vez de "producción", que es de lo
    # único que colgaba cuantificar. El detector N5 (cuantificar/ranking.py, _DISTRIBUCION) ya
    # sabía atenderlas; nunca le llegaban.
    # GENÉRICO a propósito (NO va a patrones_anclados): las 8 dan nivel_dominio='fuerte' por el
    # nombre del producto -> enrutan directo sin LLM igual. Anclarlo repetiría el error del
    # 2026-08-02 ("mejores campos de la dieta mediterránea"): sin producto, "¿cómo se distribuye
    # la participación en el equipo?" saltaría el filtro. Verificado: esa frase da dominio None.
    # ⚠️ SIN 'PESA|PESAN': 'QUE CAMPOS PESAN' es de ANALIZAR (línea ~206) por decisión del
    # usuario del 2026-08-24, vigilada por 5 casos del golden. Y aunque entrara, analizar gana
    # por precedencia_colision — pero la intención debe ser explícita, no accidental.
    # ⚠️ SIN 'DESGLOS': cuantificar GANA a jerarquizar en precedencia_colision, así que ahí la
    # colisión NO está protegida. Medido 2026-09-03: incluirla ponía roja a
    # test_jerarquia_drill_down_verbos_alternos — "desglósame la gerencia PDH por campo" es
    # drill-down JERÁRQUICO, no una cifra. La palabra ya es de jerarquizar (línea ~93) y del
    # panel de Analizar (respuesta_analizar.py:57). Se queda donde está.
    # ⚠️ LIDERA\w*|LIDERO|LIDERARON y NO 'LIDER\w*': la raíz suelta capturaría LIDERAZGO/LÍDERES,
    # que son organizacionales y no de producción.
    - '(DISTRIBU\w+|REPART\w+|PARTICIPACION|PORCENTA\w+|CONTRIBU\w+|FRACCION|SHARE|PROPORCION|ENCABEZ\w+|LIDERA\w*|LIDERO|LIDERARON|PUNTER\w+)\s'
```

**Este patrón exacto está VERIFICADO** (2026-09-03, aplicado al YAML real): 8/8 preguntas
objetivo → `cuantificar`; 5/5 colisiones con `analizar` → `analizar`; drill-down →
`jerarquizar`; suite **10 fallos / 637 pasan** (= baseline); golden **92 / 85** (= baseline).

⚠️ **El `\s` final es deliberado**: exige que la palabra no sea la última del texto, evitando
que un `PORCENTAJE` aislado dispare. No quitarlo.

⚠️ **Comillas simples**, como todos los demás patrones del archivo. En YAML, dentro de comillas
simples el `\` no se escapa: `\w`, `\s` y `\b` van literales. **No** usar comillas dobles.

### 3.2 AÑADIR tests en `tests/test_consulta_v2_clasificador.py`

Sección nueva **al final del archivo**. Antes de escribirlos, el executor debe **leer el
archivo completo** para copiar el estilo de import y de helper que ya use (no inventar uno
nuevo si ya hay un patrón establecido).

⚠️ **`clasificar_capa1` y `nivel_dominio` YA están importados** en la línea 10-11 (H11). **No
añadir ningún import**: usarlos directamente. Devuelven una tupla → `[0]` es el grupo.

```python
# --- Capa 1 · distribución con producto explícito (2026-09-03) -----------------------------
# Origen: medido en Pruebas — "¿qué porcentaje del CRUDO aporta el campo Castilla?" caía en
# desconocido porque cuantificar colgaba de la palabra "PRODUCCION". 8 de 8 formas con producto
# explícito fallaban. Ver Planes/plan_CAPA1-DISTRIBUCION-SIN-PRODUCCION_20260903.md


def test_distribucion_con_producto_sin_la_palabra_produccion():
    """Las formas que fallaban: dicen CRUDO/GAS, no PRODUCCION."""
    assert clasificar_capa1("que porcentaje del crudo aporta el campo Castilla")[0] == "cuantificar"
    assert clasificar_capa1("como se reparte el crudo entre los campos")[0] == "cuantificar"
    assert clasificar_capa1("dame el share de cada campo sobre el crudo")[0] == "cuantificar"
    assert clasificar_capa1("que fraccion del crudo produce cada campo")[0] == "cuantificar"


def test_dominancia_con_producto_sin_la_palabra_produccion():
    assert clasificar_capa1("que campos encabezan el crudo en agosto")[0] == "cuantificar"
    assert clasificar_capa1("que campos lideran el gas este mes")[0] == "cuantificar"


def test_pesan_sigue_siendo_analizar():
    """🔒 REGRESIÓN: decisión cerrada del usuario del 2026-08-24 (H5 del plan). El patrón
    nuevo NO incluye PESA/PESAN, y aunque las incluyera analizar ganaría por
    precedencia_colision. Este test fija la intención, no solo el resultado."""
    assert clasificar_capa1("que campos pesan en el gap")[0] == "analizar"


def test_causales_siguen_siendo_analizar():
    """El patrón nuevo no le disputa nada a analizar (H3: controles negativos)."""
    assert clasificar_capa1("por que bajo la produccion de crudo en Castilla")[0] == "analizar"
    assert clasificar_capa1("analiza el comportamiento del producto crudo")[0] == "analizar"


def test_colision_con_analizar_la_gana_analizar():
    """🔒 H4: 5 colisiones reales medidas. GAP/META/DIFERIDAS/P50 + vocabulario nuevo en la
    misma frase -> gana analizar por precedencia_colision. Es la dirección segura y este
    test la fija: si alguien reordena la precedencia, esto se pone rojo."""
    assert clasificar_capa1("como se distribuye el gap de crudo entre los campos")[0] == "analizar"
    assert clasificar_capa1("que porcentaje de la meta de crudo llevamos")[0] == "analizar"
    assert clasificar_capa1("que participacion tienen las diferidas de crudo")[0] == "analizar"


def test_desglose_jerarquico_no_lo_roba_cuantificar():
    """🔒 H4-bis, la regresión que este plan estuvo a punto de introducir: cuantificar GANA a
    jerarquizar en la precedencia, así que DESGLOS quedó FUERA del patrón a propósito.
    Complementa a test_jerarquia_drill_down_verbos_alternos, que fue el que la detectó."""
    assert clasificar_capa1("desglosame la gerencia PDH por campo")[0] == "jerarquizar"


def test_sin_producto_no_dispara_dominio():
    """🔒 La guarda real del patrón NO es el regex, es el filtro de dominio: el patrón es
    genérico a propósito (H2). Sin vocabulario de producción, la frase no tiene dominio y
    no puede enrutar a cuantificar aunque el regex calce."""
    assert nivel_dominio("como se distribuye la participacion en el equipo") is None
```

---

## 4. Orden de ejecución

| # | Paso | Verificación | Si falla |
|---|---|---|---|
| 0 | Baseline: `pytest tests/ -q` | anotar el conteo exacto (esperado: **637 pasan, 10 fallan**) | DETENTE: el árbol no está limpio |
| 0-bis | Golden **ANTES**: comando de §6.1 | anotar `pct` y `aciertos` (esperado: 92 / 85 en local) | DETENTE |
| 1 | §3.1 — el patrón en el YAML | validar YAML (§6.1, 1er comando) → `YAML OK` | mala indentación: el patrón queda ausente en silencio |
| 2 | §3.2 — los tests nuevos (7) | `pytest tests/test_consulta_v2_clasificador.py -q`: los 7 pasan y **sigue habiendo 1 solo fallo** (`test_escalada_fallback_conserva_regex`) | si sale un 2º fallo, es una colisión: ver qué grupo se movió |
| 3 | Suite completa: `pytest tests/ -q` | **exactamente 10 fallos / 637 pasan** | ⚠️ ver la nota de abajo |
| 4 | Golden **DESPUÉS** | **92 / 85, sin cambio** respecto al paso 0-bis | si baja: revertir el YAML y reportar |

⚠️ **Cómo leer un fallo nº 11 en el paso 3.** Ya pasó en la auditoría de este plan: con
`DESGLOS\w+` en el patrón, `test_jerarquia_drill_down_verbos_alternos` se ponía rojo. Si
aparece un fallo que no esté en los 10 documentados, **el patrón le está robando preguntas a
otro grupo**. La respuesta correcta es **retirar del patrón la palabra culpable**, nunca tocar
el test — ese test fija una decisión anterior. Reportar cuál se retiró y por qué.

⚠️ **El paso 3 es el que manda, no el 4.** La única regresión real que produjo este cambio la
detectó la suite, no el golden (H10). No dar por bueno el cambio solo porque el golden no se
movió.

⚠️ **El paso 0-bis no es opcional.** En el plan anterior se omitió el golden «antes» y hubo
que reconstruirlo después con `git stash`. Aquí se mide primero, siempre.

⚠️ El golden requiere BD. En local la BD está congelada (mayo 2026), así que **la cifra es
comparable consigo misma pero no representativa**. Se corre igual para detectar crashes y
movimientos relativos; **la cifra que vale es la de Pruebas**. Decirlo así en el reporte.

**Corte de fase:** no lo hay — un patrón, un archivo. Si el paso 1 rompe algo, se revierte el
YAML entero.

---

## 5. Reglas no negociables

1. **NO tocar `patrones_anclados`** (H2). Las 8 preguntas ya dan dominio `fuerte`; anclar no
   aporta nada y reintroduce el fallo del 2026-08-02.
2. **NO añadir `PESA`/`PESAN`** al patrón (H5) — decisión cerrada del usuario, 5 casos golden.
3. **NO añadir `DESGLOS`** al patrón (H4-bis) — medido: rompe
   `test_jerarquia_drill_down_verbos_alternos`. Es la palabra que la v1 de este plan incluía
   por error.
4. **NO usar `LIDER\w*`**; solo las formas verbales (H6).
5. **NO tocar ningún test existente para que pase.** Si el patrón pone rojo un test, el que
   está mal es el patrón: se retira la palabra culpable. Los tests del clasificador fijan
   decisiones tomadas y verificadas con el usuario (2026-08-02, 08-24).
6. **NO tocar `vocabulario_dominio.yaml`** — el falso positivo de `PRESUPUESTO` (H9) es
   preexistente y ajeno a este plan.
7. **NO tocar `cuantificar/ranking.py`** — ya está resuelto y publicado. Este plan es la capa
   de arriba (H7).
8. **NO tocar `precedencia_colision`** (H4): que `analizar` gane es lo que hace seguro este
   cambio.
9. **NO arreglar `test_escalada_fallback_conserva_regex`** — es 1 de los 10 fallos
   preexistentes documentados.
10. **NO añadir imports** al archivo de tests: `clasificar_capa1` y `nivel_dominio` ya están
    (H11).
11. Todo patrón nuevo lleva **comentario encima explicando qué NO debe tragarse**. Es la
    convención del archivo.

---

## 6. Validación

### 6.1 Estática (executor)

```powershell
cd 'C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend'
.venv\Scripts\python.exe -c "import yaml,pathlib; yaml.safe_load(pathlib.Path('app/features/consulta_v2/config/patrones_grupo.yaml').read_text(encoding='utf-8')); print('YAML OK')"
.venv\Scripts\python.exe -m pytest tests/test_consulta_v2_clasificador.py -q
.venv\Scripts\python.exe -m pytest tests/ -q
```

⚠️ El primer comando es **obligatorio antes de los tests**: un YAML mal indentado no da
`SyntaxError`, da un patrón silenciosamente ausente. Es el modo de fallo propio de este
archivo.

Golden (antes y después, §4 pasos 0-bis y 4):

```powershell
.venv\Scripts\python.exe -c "from app.features.consulta_v2.golden.run_golden import ejecutar; r=ejecutar(); print('pct:', r['pct'], '· aciertos:', r['aciertos'])"
```

⚠️ Claves reales: **`pct` y `aciertos`**. No existen `ok` ni `total` (verificado en
`run_golden.py:46-53`).

### 6.2 Humana (usuario) — en PRUEBAS

Tras `git pull` y **reiniciar INGESTA** (obligatorio: el YAML se lee al arranque):

| Pregunta | Esperado |
|---|---|
| ¿Qué porcentaje del crudo aporta el campo Castilla? | **Declinación honesta** del ranking scoped («el ranking DENTRO de «CASTILLA» llega en una próxima fase…»), NO «no entendí» y NUNCA el ranking global |
| ¿Cómo se reparte el crudo entre los campos? | Panel de distribución con **5 campos** |
| ¿Qué campos encabezan el crudo en agosto? | Ranking Top 5 |
| ¿Qué campos pesan en el gap? | Sigue en **ANALIZAR** ← regresión clave |
| ¿Por qué bajó la producción de crudo en Castilla? | Sigue en **ANALIZAR** |
| ¿Cómo se distribuye el **gap** de crudo entre los campos? | Sigue en **ANALIZAR** (H4: la colisión la gana analizar) |
| **Desglósame la gerencia PDH por campo** | Sigue en **JERARQUIZAR** ← H4-bis, la regresión que se evitó |
| ¿Cuánto crudo produjo Rubiales? | Cifra única, sin ranking |

Además: F12 → Console sin errores.

**El único que marca ✅ es el usuario.** Hasta entonces: «implementado, PENDIENTE de
validación humana».

### 6.3 Medición de valor

Igual que el plan anterior, contra `core.clasificacion_log` (`consulta_v2/log.py:23-39`):
cuántas preguntas reales con este vocabulario entran, en qué grupo terminan, y qué veredicto
✓/✗ les pone el usuario.

⚠️ **El baseline PRE de este vocabulario ya está contaminado**: las pruebas manuales del
2026-09-02 y 09-03 quedaron registradas en la tabla. Al medir, **excluir por fecha** las
preguntas de esos dos días, o el conteo mezclará tráfico real con pruebas nuestras.

**El criterio de éxito no es «pasan los tests»**: es que preguntas reales redactadas con
producto explícito dejen de caer en `desconocido`.

### 6.4 Despliegue

Backend solamente → commit a GitHub `main` → `git pull` en Pruebas → **reiniciar INGESTA**
(no opcional aquí) → validar §6.2 → `migrar-a-azure` en 3 tiempos (el default ya publica en
`prodiav2`) → en el 139: `git pull` + reiniciar INGESTA.

Flask **no** necesita reinicio: no cambia el contrato ni el frontend.

---

## 7. Fuera de alcance

- **`vocabulario_dominio.yaml` y el falso positivo de `PRESUPUESTO`** (H9): preexistente,
  merece su propio análisis y su propio golden.
- **Unificar el vocabulario de Capa 1 con `_DISTRIBUCION` de `ranking.py`** (H7): son capas
  distintas con guardianes distintos; el YAML no ejecuta Python.
- **`PESO`/`PESA`**: decisión del usuario, no un bug.
- **Temporales relativos** («mes pasado»): sin soporte en `slots.py`, responde el mes vigente
  en silencio. Sigue abierto y es más grave que esto.
- **Las brechas de `jerarquias_sup_error.md`** (orden 2→1→3): independientes de este cambio.
- Cualquier cambio en el cálculo, el SQL, el panel o el frontend.
