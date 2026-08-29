# Plan · QV2-HILO-DIA — Cuatro fallos de grano día y de hilo conversacional

> **Versión:** v4 — auditada en **tres pasadas** (`CLAUDE_muestra.md` §0.2), la última **durante la
> propia ejecución** (el plan se detuvo ante un fallo de validación, se auditó el hallazgo con el
> mismo rigor, y se retomó).
> **Flujo profesional §15 ejecutado:** pasos 1-3 (Mapeo · Auditoría · Diagnóstico) **reproduciendo cada
> fallo en el intérprete** antes de escribir. La 1ª pasada **corrigió el diagnóstico inicial de F2**
> (ver H-02). La 2ª pasada encontró **dos defectos en los propios cambios propuestos** y los corrigió:
> **H-09** (C2 filtraba por código y dejaba 3 formas sin rechazo) y **H-10** (C4 secuestraba preguntas
> estructurales). La 3ª pasada, ya ejecutando el plan, encontró que **H-10 estaba incompleto**: una
> **tercera rama preexistente** (`maquina_q.py`, "Drill N1 GENÉRICO", 2026-08-02) reproducía el mismo
> secuestro por una vía que ni C4.b ni la verificación de H-10 cubrían — ver **H-13** y **C6**.
> **Fecha:** 2026-08-25 · **ID:** QV2-HILO-DIA
> **Origen:** cuatro comportamientos reportados por el usuario en sesión del 2026-08-25 (21:05-21:08).
>
> **Aplicabilidad de `CLAUDE_muestra.md`:** describe *Robustez V2.0* (React 19 + pnpm). Aquí se toca
> **solo backend Python (FastAPI en INGESTA :8088)**: DT-9/DT-11/DT-13/DT-17 y R1/R2 no aplican.
> Sí aplican: **§0.2**, **§0.3** (formato Planner), **§15**, **DT-16** (grep exhaustivo antes de tocar
> algo compartido) y **DT-15/R3** (verde en pytest ≠ verificado en la app).

---

## 1. CONTEXTO

**Proyecto:** ProdIA 2.0 — chat de analítica de producción de hidrocarburos (Ecopetrol).
**Raíz absoluta:** `c:\APLICACIONES\ProdIA\12112025_prodIA\ProdIA-2.0\ProdIA-2.0`
**Backend afectado:** `INGESTA\Rep_Prod\backend` (FastAPI, `:8088`).
**Intérprete:** `INGESTA\Rep_Prod\backend\.venv\Scripts\python.exe`
⚠️ El `python` del PATH **no** tiene fastapi instalado: usar siempre el del `.venv`.

### Los cuatro fallos, tal como los vivió el usuario

| # | Lo que pidió | Lo que recibió |
|---|---|---|
| **F1** | «el **día** 15 de mayo cuanto produjo campo Castilla?» | La cifra del **15 de agosto**, afirmando «el sábado 15 de agosto de 2026» sin avisar del cambio de mes |
| **F2** | «el 15 de mayo?» (repregunta) | «me pediste un día puntual y por ahora solo puedo darte el mes completo» — **falso**: el motor sí da días |
| **F3** | *(latente, aún no visto)* | `octubre`→11, `noviembre`→12, `diciembre`→**13** (mes inexistente) |
| **F4** | «y en mayo?» tras ver la cifra de junio | «los periodos de tiempo no están dentro de mi dominio» — perdió el hilo |

### Piezas implicadas

| Pieza | Ubicación (absoluta desde la raíz) | Papel |
|---|---|---|
| `_MESES_NUM`, `_RX_DIA_MES`, `detectar_dia` | `INGESTA\Rep_Prod\backend\app\features\consulta_v2\cuantificar\slots.py` | Ranura de DÍA (módulo **puro**, sin BD) |
| `_FORMAS`, `detectar`, `mensaje` | `INGESTA\Rep_Prod\backend\app\features\consulta_v2\no_soportado.py` | Rechazo honesto de formas no construidas |
| `_TEMP_CONT_KW`, `_continuacion`, `_CTX` | `INGESTA\Rep_Prod\backend\app\features\consulta_v2\maquina_q.py` | Memoria conversacional + reescritor de frases cortas |
| `_FORMAS_RECHAZO` | `INGESTA\Rep_Prod\backend\app\features\consulta_v2\respuesta_cuantificar.py` | **Ya excluye `dia`** — no se toca (H-02) |
| Tests | `INGESTA\Rep_Prod\backend\tests\test_no_soportado.py`, `test_cuantificar_dia.py` | **Aseveran el comportamiento actual** — hay que actualizarlos (H-05) |

---

## 2. OBJETIVO

Que el motor responda el día que el usuario pidió, no otro; que no niegue una capacidad que tiene; y
que no pierda el hilo al cambiar de mes en una repregunta. **Sin tocar arquitectura**: los cuatro son
listas o expresiones regulares incompletas.

---

## 3. DECISIONES CERRADAS

El executor **no decide nada**.

| # | Decisión | Motivo |
|---|---|---|
| **D-1** | En F1, cuando el texto nombra un mes explícito, **manda ese mes**. Nunca se sustituye en silencio | Es la regla que el propio `slots.py:134-139` ya declara para la otra rama |
| **D-2** | En F2 **no se retira** la forma `dia` de `no_soportado._FORMAS` | Sigue siendo el rechazo correcto para el fork de RANKING y para 3 formas que N1D no cubre (H-03) |
| **D-3** | En F4 se amplía `_TEMP_CONT_KW` con los **nombres de mes**, no con una regla genérica | Mínimo cambio que cubre el caso real sin abrir el reescritor a cualquier frase |
| **D-4** | `_MESES` (la tupla) **no se toca**; solo se corrige el mapa `_MESES_NUM` | `_MESES` lo usa además `_periodo_texto`; alterarla tendría alcance no auditado |

---

## 4. HALLAZGOS DE LA AUDITORÍA (§15 pasos 2-3)

Todos reproducidos en el intérprete. Los comandos están en §10 para que el executor los repita.

### 🔴 H-01 — F1: el regex exige que el número siga a «EL», y «día» lo rompe

`slots.py:59` → `_RX_DIA_MES = re.compile(r"\bEL\s+(\d{1,2})\s+DE\s+([A-Z]+)")`

Medido:

```
'EL DIA 15 DE MAYO CUANTO PRODUJO CAMPO CASTILLA?'  -> _RX_DIA_MES: None   ❌
'EL 15 DE MAYO?'                                    -> _RX_DIA_MES: match  ✅
```

Sin match, el flujo cae a `_RX_DIA_SOLO` (`:60`), que **sí** reconoce «EL DIA 15» pero descarta el mes
escrito y usa el del techo:

```
detectar_dia('el dia 15 de mayo …', techo=2026-08-18)
  -> {'fecha': '2026-08-15', 'asumido': ['mes=08/2026']}     ← agosto, no mayo
```

**Lo grave:** `slots.py:134-139` documenta esta misma degradación y la declara inaceptable
(«cambiar el mes que el usuario dijo por otro es exactamente la degradación silenciosa que este plan
existe para impedir»). La guarda existe, pero **solo dentro de la rama `_RX_DIA_MES`**; si esa rama no
engancha, nadie comprueba que el texto traía un mes.

### 🔴 H-02 — F2: el rechazo NO viene de donde parecía *(corrige el diagnóstico inicial)*

La ruta de ENTIDAD de cuantificar **ya está bien**: `respuesta_cuantificar.py:140` define
`_FORMAS_RECHAZO = ("rango_dias", "trimestre", "semana")` — `dia` ya salió de ahí el 2026-08-25.
Verificado:

```
_forma_no_soportada('el 15 de mayo?')          -> None   ✅ (no rechaza; N1D responde)
_forma_no_soportada_ranking('el 15 de mayo?')  -> 'dia'  ✅ (correcto: el ranking es mensual)
```

El rechazo que vio el usuario sale de **`maquina_q.py:446`**, en la rama **OUT** (`grupo ==
'desconocido'`):

```python
forma = no_soportado.detectar(texto) if (ent_ctx and not forma_meta) else None
```

Ahí se llama a `no_soportado.detectar` **crudo**, sin el filtro `_FORMAS_RECHAZO` que sí aplica la ruta
de cuantificar. Es decir: la pregunta ni siquiera llegó a cuantificar — se clasificó como
`desconocido` (por ser elíptica, ver H-04), y la rama OUT le aplicó un rechazo que la ruta buena ya
había retirado.

→ El arreglo **no** es tocar `no_soportado._FORMAS` (eso rompería el ranking, D-2), sino **filtrar en
la rama OUT las formas que el motor ya sabe responder**.

### 🔴 H-03 — Retirar `dia` del catálogo dejaría 3 formas huérfanas

Si alguien «simplificara» borrando la forma `dia` de `no_soportado._FORMAS`, estas dejarían de tener
respuesta **y** de tener rechazo (medido con `detectar_dia`, techo = 2026-05-17):

| Forma | `detectar_dia` | Qué pasaría sin rechazo |
|---|---|---|
| «el **lunes** cuanto produjo Castilla» | `None` | Silencio: respondería el MES entero |
| «**este día** cuanto produjo» | `None` | Ídem |
| «el **último día**» | `None` | Ídem |

Por eso D-2: la forma `dia` **se queda** en el catálogo. Solo se filtra en la rama OUT (C2).

### 🟠 H-04 — F4: `_TEMP_CONT_KW` no conoce los meses

`maquina_q.py:57` → `_TEMP_CONT_KW = ("MES A MES", "VARIACION", "COMO VARIO", "SERIE", "EVOLUCION")`

Esa tupla decide si una frase corta sin entidad es «continuación temporal» y se reescribe heredando la
entidad del contexto. Medido con `ctx = {grupo:'cuantificar', entidad:'CASTILLA', producto:'crudo'}`:

```
'y el acumulado?'  -> 'acumulado de CASTILLA'                    ✅
'y la variacion?'  -> 'produccion de CASTILLA y la variacion?'   ✅
'y en mayo?'       -> None                                       ❌
'y en junio'       -> None                                       ❌
```

Con `None`, la frase viaja **desnuda** al clasificador. `clasificar_capa1('y en mayo?')` devuelve
`(None, [])` → escala al LLM → el LLM, viendo solo «y en mayo?» sin contexto, responde que «los
periodos de tiempo» no son su dominio. **No está negando saber de mayo: está reaccionando a un
fragmento sin sentido.**

Confirmación en la captura del usuario: la respuesta lleva `→ Cuantificar (usuario)` al pie — el
propio sistema registró que su clasificación fue corregida.

Ironía estructural: el turno anterior cerró ofreciendo «¿Quieres el acumulado del año?». Aceptar esa
oferta **sí** funciona (rama añadida el 2026-08-24 tras un bug idéntico, `maquina_q.py:90-109`).
Cambiar de mes —lo más natural tras ver una cifra mensual— es el hueco gemelo que quedó sin cubrir.

### 🟡 H-05 — Los tests aseveran el comportamiento que vamos a cambiar

`tests\test_no_soportado.py:38` → `assert no_soportado.detectar("cuanto produjo el 15 de mayo") == "dia"`

Ese assert **debe seguir pasando** (D-2: el catálogo no cambia). Pero C2 cambia lo que hace la rama
OUT, y C1 cambia lo que devuelve `detectar_dia`. Hay que **añadir** cobertura, no reescribir la
existente.

**Línea base medida antes de tocar nada:**
`test_no_soportado.py` + `test_cuantificar_dia.py` + `test_capacidades.py` + `test_incompleta.py`
→ **78 passed in 0.80s**.

### 🟡 H-06 — F3: `_MESES_NUM` numera por índice sobre una lista con dos septiembres

`slots.py:51-57`:

```python
_MESES = ("enero … septiembre setiembre octubre noviembre diciembre").split()
_MESES_NUM = {m: i + 1 for i, m in enumerate(_MESES)}
```

`setiembre` (variante sin «p») ocupa la posición 10 → desde ahí todo corre un mes:

```
septiembre -> 9     setiembre -> 10 ❌     octubre -> 11 ❌
noviembre  -> 12 ❌  diciembre -> 13 ❌ (mes inexistente)
```

Hoy no se manifiesta porque el dato va por agosto, pero «el 5 de octubre» daría **noviembre**, y
diciembre haría fallar `_fecha_valida` (`1 <= mes <= 12`) devolviendo `None` — la pregunta se caería
sin explicación.

### 🟢 H-07 — El regex candidato de C1 no rompe las guardas existentes

Medido contra el candidato `r"\bEL\s+(?:DIA\s+)?(\d{1,2})\s+DE\s+([A-Z]+)"`:

| Texto | Viejo | Nuevo | Correcto |
|---|---|---|---|
| «EL DIA 15 DE MAYO …» | ✗ | ✓ | ✓ es el fix |
| «EL 15 DE MAYO?» | ✓ | ✓ | ✓ sin regresión |
| «EL 31 DE FEBRERO» | ✓ | ✓ | ✓ lo corta `_fecha_valida` |
| «DEL 1 AL 15 DE MAYO» | ✗ | ✗ | ✓ es rango, lo coge `_RX_RANGO_GUARDA` |
| «EL DIA 15» (sin mes) | ✗ | ✗ | ✓ debe caer a `_RX_DIA_SOLO` |

### 🔴 H-09 *(2ª pasada)* — C2 filtraba por CÓDIGO y dejaba 3 formas sin rechazo

El C2 de la v2 filtraba `if forma in ("dia", "selector_dia"): forma = None`. **Está mal.** El código
`dia` de `no_soportado` agrupa formas que N1D **sí** resuelve y formas que **no**, y el filtro por
código no las distingue. Medido:

| Texto | código | ¿N1D lo resuelve? | Con el filtro por código |
|---|---|---|---|
| «el 15 de mayo?» | `dia` | ✅ sí | Filtrado → correcto |
| «cuánto produjo Castilla ayer» | `dia` | ✅ sí | Filtrado → correcto |
| «el mejor día del mes» | `selector_dia` | ✅ sí | Filtrado → correcto |
| «cuánto produjo Castilla **el lunes**» | `dia` | ❌ **no** | Filtrado → **queda MUDO** |
| «**este día** cuánto produjo» | `dia` | ❌ **no** | Filtrado → **queda MUDO** |
| «**el último día**» | `dia` | ❌ **no** | Filtrado → **queda MUDO** |

Es decir: la v2 arreglaba F2 pero reintroducía el **bug #5** (degradación silenciosa) en las tres
formas de H-03 — justo las que el plan decía proteger. Se pierde el rechazo honesto y el usuario
recibiría el mes entero, o una respuesta del LLM, sin aviso.

**Discriminador correcto:** no el código, sino **si `detectar_dia()` sabe resolver ese texto**. Es la
única fuente de verdad sobre qué cubre N1D, y es pura (sin BD), así que la rama OUT puede llamarla.
Ver C2 reescrito.

### 🔴 H-10 *(2ª pasada)* — C4 secuestraba las preguntas ESTRUCTURALES

La rama que consume `_TEMP_CONT_KW` está en `maquina_q.py:85`, **antes** de la rama estructural que
usa `_ESTRUCT_KW` (`:44-46`). Al meter los meses en `_TEMP_CONT_KW`, toda frase corta con un mes se
reescribía a *producción*, incluidas las que preguntan por ESTRUCTURA. Medido con la v2:

```
'cuantos pozos en mayo'   -> 'produccion de CASTILLA cuantos pozos en mayo'   ❌
'cuales campos en mayo'   -> 'produccion de CASTILLA cuales campos en mayo'   ❌
```

El usuario preguntaba cuántos pozos y habría recibido una cifra de producción. Es exactamente el bug
que `_ESTRUCT_KW` existe para evitar, entrando por una puerta que se abre antes.

**Corrección:** la rama temporal exige además que la frase **no** traiga pista estructural. Verificado:

```
'y en mayo?'             mes=True  estruct=False -> reescribe ✅
'cuantos pozos en mayo'  mes=True  estruct=True  -> NO reescribe ✅
'cuales campos en mayo'  mes=True  estruct=True  -> NO reescribe ✅
```

### 🟢 H-11 *(2ª pasada)* — La «y» residual de la reescritura no estorba

`_continuacion` devuelve `f"produccion de {ent} {texto}"`, así que «y en mayo?» produce
`'produccion de CASTILLA y en mayo?'` — con la conjunción dentro. Verificado que el pipeline lo
procesa igual que la forma canónica:

```
'produccion de CASTILLA y en mayo?'  -> nivel_temporal=N1  periodo_texto='mayo'  ✅
'produccion de CASTILLA en mayo'     -> nivel_temporal=N1  periodo_texto='mayo'  ✅
```

No hace falta limpiar el texto: `_periodo_texto` busca el nombre del mes en cualquier posición.
**No “arreglar” esto**: tocar la plantilla afectaría a las otras ramas que la comparten.

### 🟢 H-12 *(2ª pasada)* — C4 y el grano día no chocan

«y el 15 de mayo?» (5 tokens, sin entidad) entra por la rama temporal con C4 y se reescribe a
`'produccion de CASTILLA y el 15 de mayo?'`. Verificado que sigue dando **N1D** con la fecha correcta:

```
nivel_temporal=N1D  dia={'clase':'fecha','fecha':'2026-05-15'}   ✅
```

La reescritura hereda la entidad sin pisar la ranura de día. Es el comportamiento deseado: antes esa
frase perdía el hilo igual que «y en mayo?».

### 🔴 H-13 *(3ª pasada, durante la ejecución)* — Una tercera rama secuestraba lo mismo que H-10, por otra vía

C4.b se verificó y funciona: la rama `_TEMP_CONT_KW` ya no dispara para «cuántos pozos en mayo». Pero
al ejecutar V-4b sobre el código real, la frase **seguía** reformulándose a producción. Causa: una
rama distinta, más abajo (`maquina_q.py`, comentada *"Drill N1 GENÉRICO"*, **fechada 2026-08-02 —
preexistente, no introducida por este plan**):

```python
if ctx.get("grupo") == "cuantificar" and prod:      # prod = any(_PROD_KW) — incluye "CUANTO"/"CUANTOS"
    return f"produccion de {pieza_gen}{ctx['entidad']} {texto.strip()}"
```

No consulta `_ESTRUCT_KW` en absoluto. Verificado que es **independiente de C4** y preexistente:

```
'cuantos pozos tiene'   (SIN mes, SIN ningún cambio de hoy)
   -> _PROD_KW hit: CUANTO, CUANTOS   -> SIEMPRE se habría reformulado a producción
```

**Por qué las dos auditorías anteriores no lo vieron:** la verificación de H-10 durante el diseño
simuló la condición `mes and not estruct` de forma aislada — nunca ejecutó `_continuacion()` completa
contra el código real. Esta rama no depende de meses ni de `_TEMP_CONT_KW`; solo se hizo visible al
correr V-4b de punta a punta durante la ejecución.

**Por qué el guarda simétrico de C4.b (`not any(_ESTRUCT_KW)`) NO sirve aquí** — rompería un caso
legítimo. Medido:

| Frase | `_PROD_KW` | `_ESTRUCT_KW` | Con guarda simétrica |
|---|---|---|---|
| «cuántos pozos en mayo» | CUANTO, CUANTOS | POZO, POZOS | Correcto: debe ir a estructura |
| «cuánto **produjo** el **campo** en mayo» | PRODUJO, CUANTO | CAMPO | **Falso rechazo**: es producción real, «campo» es genérico |

El discriminador correcto no es «¿hay palabra estructural?», sino «¿el ÚNICO indicio de producción es
el CUANTO/CUANTOS ambiguo, sin verbo explícito?». Verificado contra 8 casos (incluida la frase con
verbo explícito) antes de aplicarlo:

```
ambiguo_estructural = any(_ESTRUCT_KW) and not any(_PROD_EXPLICITO)
# _PROD_EXPLICITO = ("PRODUCCION", "PRODUJO", "PRODUCE", "PRODUCIDO")  — subconjunto SIN ambigüedad
```

| Frase | `ambiguo_estructural` | Resultado |
|---|---|---|
| «cuántos pozos en mayo» | `True` | → estructural («que es CASTILLA») ✅ |
| «cuántas gerencias tiene» | `True` | → estructural ✅ |
| «produjo el campo en mayo» (con verbo) | `False` | → producción, sin regresión ✅ |
| «cuánto produjo en mayo» | `False` | → producción, sin regresión ✅ |
| «y en mayo?» | `False` (sin `_ESTRUCT_KW`) | → producción, es el fallo F4 ✅ |

> **Nota sobre «cuánto produjo el campo en mayo» (6 tokens):** con `ctx` puro esa frase da `None` — no
> es una regresión de C6: tiene 6 tokens y ya topaba con el corte preexistente `elif len(toks) > 5:
> return None` (línea ~133) **antes de cualquier cambio de hoy**, porque ni las palabras de mes de
> C4.a ni el guarda de C6 alteran ese corte. Verificado con la forma corta equivalente («produjo el
> campo en mayo», 5 tokens) que el discriminador sí funciona cuando el corte de longitud no estorba.

### 🟢 H-08 — `capacidades.py` promete justo lo que la rama OUT niega

`capacidades.py:110-112` documenta que el inventario de capacidades **no** promete rangos de días ni
trimestres «porque `no_soportado.py` los rechaza, y ofrecerlos aquí sería contradecirse un turno
después». Con C2, los días puntuales **dejan de ser** una capacidad negada. No hay que tocar
`capacidades.py` en este plan (su texto no promete días), pero queda anotado: si algún día se añade
«te doy un día puntual» al inventario, ya será cierto.

---

## 5. PREREQUISITOS

| # | Check | Comando / criterio |
|---|---|---|
| P-1 | Estar en la raíz del backend | `cd c:\APLICACIONES\ProdIA\12112025_prodIA\ProdIA-2.0\ProdIA-2.0\INGESTA\Rep_Prod\backend` |
| P-2 | El `.venv` existe y tiene fastapi | `.\.venv\Scripts\python.exe -c "import fastapi; print('ok')"` → `ok` |
| P-3 | Línea base de tests en verde | `.\.venv\Scripts\python.exe -m pytest tests\test_no_soportado.py tests\test_cuantificar_dia.py tests\test_capacidades.py tests\test_incompleta.py -q` → **78 passed** |
| P-4 | Reproducir los 4 fallos ANTES de tocar | Ejecutar el bloque de §10.0 y confirmar que falla como se describe |

---

## 6. INVENTARIO DE ARCHIVOS

| Archivo (ruta absoluta) | Acción |
|---|---|
| `INGESTA\Rep_Prod\backend\app\features\consulta_v2\cuantificar\slots.py` | **Modificar** — C1, C3 |
| `INGESTA\Rep_Prod\backend\app\features\consulta_v2\maquina_q.py` | **Modificar** — C2, C4, C6 |
| `INGESTA\Rep_Prod\backend\tests\test_cuantificar_dia.py` | **Modificar** — C5 (añadir casos) |
| `INGESTA\Rep_Prod\backend\tests\test_cuantificar.py` | **Modificar** — C7 *(añadido durante la ejecución, ver H-14)* |
| `INGESTA\Rep_Prod\backend\app\features\consulta_v2\no_soportado.py` | **NO tocar** (D-2, H-03) |
| `INGESTA\Rep_Prod\backend\app\features\consulta_v2\respuesta_cuantificar.py` | **NO tocar** (H-02: ya correcto) |
| `INGESTA\Rep_Prod\backend\tests\test_no_soportado.py` | **NO tocar** (H-05: sus asserts siguen siendo válidos) |
| Frontend, `static\`, `MainChat\` | **NO tocar** |

---

## 7. ESPECIFICACIÓN

### C1 · F1 — `_RX_DIA_MES` admite «el día 15 de mayo»

**Archivo:** `…\consulta_v2\cuantificar\slots.py`, línea 59.

Sustituir:

```python
_RX_DIA_MES = re.compile(r"\bEL\s+(\d{1,2})\s+DE\s+([A-Z]+)")
```

por:

```python
# [2026-08-25 · QV2-HILO-DIA F1] «DIA» OPCIONAL. Medido: "el día 15 de mayo" NO matcheaba
# (el regex exigía el número pegado a EL) y el flujo caía a _RX_DIA_SOLO, que ignora el mes
# escrito y usa el del techo -> se pidió MAYO y se respondió AGOSTO, afirmándolo sin avisar.
# Es la misma degradación que la guarda de :134 declara inaceptable, por la puerta de al lado.
_RX_DIA_MES = re.compile(r"\bEL\s+(?:DIA\s+)?(\d{1,2})\s+DE\s+([A-Z]+)")
```

### C2 · F2 — La rama OUT no rechaza lo que el motor sí sabe responder

> ⚠️ **Reescrito en la 2ª pasada (H-09).** La versión anterior filtraba por CÓDIGO
> (`if forma in ("dia","selector_dia")`) y dejaba «el lunes», «este día» y «el último día» **sin
> rechazo y sin respuesta**. El discriminador correcto es `detectar_dia()`: la única fuente de
> verdad sobre qué cubre N1D. **No sustituyas esto por la versión por código.**

**Archivo:** `…\consulta_v2\maquina_q.py`, línea 446.

Sustituir:

```python
        forma = no_soportado.detectar(texto) if (ent_ctx and not forma_meta) else None
```

por:

```python
        # [2026-08-25 · QV2-HILO-DIA F2] La rama OUT llamaba a `detectar` CRUDO, sin el filtro
        # que la ruta de cuantificar ya aplica (respuesta_cuantificar._FORMAS_RECHAZO, donde
        # 'dia' y 'selector_dia' salieron al implementarse N1D). Resultado medido: a «el 15 de
        # mayo?» se le respondía "solo puedo darte el mes completo" MIENTRAS el motor mostraba
        # la curva diaria con ese día resaltado — negaba una capacidad que tiene.
        forma = no_soportado.detectar(texto) if (ent_ctx and not forma_meta) else None
        # 🔑 Se filtra por lo que N1D SABE RESOLVER, no por el código de la forma. El código
        #    'dia' agrupa cosas muy distintas: "el 15 de mayo" y "ayer" los responde N1D, pero
        #    "el lunes", "este día" y "el último día" NO —y para esas el rechazo honesto sigue
        #    siendo la respuesta correcta—. Filtrar por código las dejaría mudas: el motor
        #    degradaría al mes entero en silencio, que es el bug #5 que no_soportado existe
        #    para impedir.
        # 🔑 El techo es un CENTINELA fijo, no el real: aquí solo se pregunta "¿sabes resolver
        #    esta FORMA?", y la fecha que salga se descarta. Con techo=None NO sirve —medido:
        #    "el 15 de mayo?" daría None y seguiría rechazándose, sin arreglar nada— porque las
        #    ramas de fecha necesitan un año de referencia. Usar el techo REAL exigiría una
        #    consulta a BD en la rama OUT, que es justo lo que el pre-check `menciona_dia` de
        #    respuesta_cuantificar existe para evitar.
        if forma in ("dia", "selector_dia") and \
                _slots_dia.detectar_dia(texto, _TECHO_CENTINELA) is not None:
            forma = None
```

Y añadir, junto a los imports del módulo (bloque de `:15-27`):

```python
from app.features.consulta_v2.cuantificar import slots as _slots_dia
```

y junto a las constantes del módulo (después de `_TEMP_CONT_KW`):

```python
# [2026-08-25 · QV2-HILO-DIA F2] Fecha ARBITRARIA para preguntarle a detectar_dia si sabe
# resolver una forma. NO se usa el valor resultante — solo si devuelve None o no. Se elige una
# fecha con día 15 para que ninguna forma («el 30», «el 31») quede fuera por el calendario.
_TECHO_CENTINELA = _date(2000, 1, 15)
```

con el import `from datetime import date as _date` (el módulo ya importa `datetime`; añadir solo
lo que falte).

> **Verificación del import (medida):** `slots.py` es PURO —no importa BD ni FastAPI—, así que no
> introduce ciclo ni coste de arranque. Además `maquina_q.py` ya importa `respuesta_cuantificar`, que
> a su vez importa `slots`: la dependencia ya existía de forma indirecta. Import probado en el
> intérprete: **OK, sin ciclo**.
>
> **Discriminación verificada con el centinela:**
>
> | Texto | ¿filtra? | Correcto |
> |---|---|---|
> | «el 15 de mayo?» | sí | ✅ N1D responde |
> | «el día 15 de mayo …» | sí | ✅ N1D responde |
> | «… ayer» | sí | ✅ N1D responde |
> | «el mejor día del mes» | sí | ✅ N1DSEL responde |
> | «… el lunes» | **no** | ✅ conserva rechazo |
> | «este día cuánto produjo» | **no** | ✅ conserva rechazo |
> | «el último día» | **no** | ✅ conserva rechazo |
> | «del 1 al 15 de mayo» | **no** | ✅ es `rango_dias` |

### C3 · F3 — Mapa de meses explícito

**Archivo:** `…\consulta_v2\cuantificar\slots.py`, línea 57.

Sustituir:

```python
_MESES_NUM = {m: i + 1 for i, m in enumerate(_MESES)}
```

por:

```python
# [2026-08-25 · QV2-HILO-DIA F3] Mapa EXPLÍCITO, no por índice. `_MESES` lleva DOS variantes de
# septiembre («septiembre» y «setiembre»), así que enumerate() corría todo un mes desde ahí:
# octubre->11, noviembre->12 y diciembre->13, un mes que no existe (habría hecho fallar
# _fecha_valida y la pregunta se caía sin explicación). No se toca `_MESES`: la usa además
# _periodo_texto y su orden importa allí.
_MESES_NUM = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
              "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
              "noviembre": 11, "diciembre": 12}
```

### C4 · F4 — La continuación temporal reconoce los meses

> ⚠️ **Reescrito en la 2ª pasada (H-10).** Añadir los meses a `_TEMP_CONT_KW` **no basta**: esa rama
> (`:85`) corre ANTES que la estructural, y sin guarda «cuántos pozos en mayo» se convertía en una
> consulta de producción. Son **dos** ediciones, no una.

**Archivo:** `…\consulta_v2\maquina_q.py`.

**C4.a — línea 57.** Sustituir:

```python
_TEMP_CONT_KW = ("MES A MES", "VARIACION", "COMO VARIO", "SERIE", "EVOLUCION")
```

por:

```python
# [2026-08-25 · QV2-HILO-DIA F4] Los NOMBRES DE MES entran aquí. Medido: tras responder la cifra
# de junio de CASTILLA, «y en mayo?» devolvía None en _continuacion -> la frase viajaba DESNUDA
# al clasificador -> capa1 no la reconoce -> el LLM, viendo solo «y en mayo?», contestaba que
# «los periodos de tiempo» no son su dominio. No negaba saber de mayo: reaccionaba a un
# fragmento sin contexto. El hueco gemelo del acumulado (:90-109), que sí se cubrió el 24-ago:
# cambiar de MES es la continuación más natural tras leer una cifra mensual.
# 🔑 En MAYÚSCULA sin tilde: se comparan contra norm(), que pliega acentos y sube a mayúsculas.
_MESES_CONT = ("ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO",
               "SEPTIEMBRE", "SETIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE")
_TEMP_CONT_KW = ("MES A MES", "VARIACION", "COMO VARIO", "SERIE", "EVOLUCION") + _MESES_CONT
```

**C4.b — línea 85-86 (la guarda, OBLIGATORIA).** Sustituir:

```python
    if (ctx.get("grupo") == "cuantificar" and ctx.get("entidad") and not ent
            and any(k in t for k in _TEMP_CONT_KW)):
```

por:

```python
    # [2026-08-25 · QV2-HILO-DIA F4] `not any(_ESTRUCT_KW)` es NUEVO y no es opcional. Al entrar
    # los meses en _TEMP_CONT_KW (arriba), esta rama —que corre ANTES que la estructural de
    # abajo— capturaba también las preguntas de ESTRUCTURA que mencionan un mes: medido,
    # «cuántos pozos en mayo» se reescribía a «produccion de CASTILLA cuantos pozos en mayo» y
    # el usuario recibía una cifra de producción en vez del número de pozos. La guarda devuelve
    # esas frases a la rama estructural, que es la suya.
    if (ctx.get("grupo") == "cuantificar" and ctx.get("entidad") and not ent
            and any(k in t for k in _TEMP_CONT_KW)
            and not any(k in t for k in _ESTRUCT_KW)):
```

> **Comportamiento verificado tras las dos ediciones:**
>
> | Frase corta (ctx = CASTILLA, cuantificar) | ¿reescribe? | Correcto |
> |---|---|---|
> | «y en mayo?» | sí | ✅ es el fallo F4 |
> | «y mayo?» / «y en junio» | sí | ✅ |
> | «y el 15 de mayo?» | sí → **N1D**, fecha `2026-05-15` | ✅ (H-12) |
> | «cuántos pozos en mayo» | **no** | ✅ va a la rama estructural |
> | «cuáles campos en mayo» | **no** | ✅ ídem |
> | «producción de RUBIALES en mayo» | **no** | ✅ trae entidad propia |
>
> La «y» residual («produccion de CASTILLA y en mayo?») **no molesta**: verificado que da
> `nivel_temporal=N1`, `periodo_texto='mayo'`, igual que la forma canónica (H-11). No limpiar el
> texto: la plantilla la comparten otras ramas.

### C6 · F4 (continuación) — la rama "Drill N1 GENÉRICO" tampoco secuestra lo estructural

> ⚠️ **Añadido en la 3ª pasada (H-13), durante la ejecución.** C4.b arregla la rama `_TEMP_CONT_KW`;
> esta rama es OTRA, más abajo, y preexistente (2026-08-02). **No usar el guarda simétrico de C4.b
> aquí** (`not any(_ESTRUCT_KW)`): rompería «cuánto produjo el campo en mayo», que sí es producción.

**Archivo:** `…\consulta_v2\maquina_q.py`.

**C6.a — junto a `_PROD_KW`** (bloque de constantes, cerca de la línea 42). Añadir:

```python
# [2026-08-25 · QV2-HILO-DIA C6] Subconjunto de _PROD_KW SIN AMBIGÜEDAD: nombran el verbo de
# producción en sí. "CUANTO"/"CUANTOS"/"CUANTA"/"CUANTAS" son AMBIGUOS — "cuánto produjo" es
# producción, pero "cuántos pozos" es un CONTEO estructural. La distinción la usa el Drill N1
# GENÉRICO de abajo para no confundir un conteo con una consulta de producción.
_PROD_EXPLICITO = ("PRODUCCION", "PRODUJO", "PRODUCE", "PRODUCIDO")
```

**C6.b — la rama "Drill N1 GENÉRICO"** (buscar el comentario `# Drill N1 GENÉRICO:`). Sustituir:

```python
    if ctx.get("grupo") == "cuantificar" and prod:
        prod_gen = ctx.get("producto", "crudo")
        pieza_gen = "" if prod_gen == "crudo" else f"{prod_gen} de "
        return f"produccion de {pieza_gen}{ctx['entidad']} {texto.strip()}"
```

por:

```python
    # [2026-08-25 · QV2-HILO-DIA C6] `ambiguo_estructural` es NUEVO. Esta rama disparaba también
    # para preguntas de ESTRUCTURA que solo comparten con "producción" la palabra ambigua
    # CUANTO/CUANTOS: medido, «cuántos pozos en mayo» se reescribía a «produccion de CASTILLA
    # cuantos pozos en mayo» y el usuario recibía una cifra en vez del número de pozos — un bug
    # PREEXISTENTE (2026-08-02), no introducido hoy, descubierto al verificar C4.b (H-10/H-13).
    # Un guarda simétrico a C4.b (`not any(_ESTRUCT_KW)`) ROMPERÍA "cuánto produjo el CAMPO en
    # mayo": esa frase SÍ es producción y menciona "campo" solo de forma genérica. El
    # discriminador correcto no es "¿hay palabra estructural?" sino "¿el ÚNICO indicio de
    # producción es el CUANTO/CUANTOS ambiguo, sin verbo explícito?" — verificado contra 8 casos,
    # incluida esta frase con verbo explícito, antes de aplicarlo.
    ambiguo_estructural = (any(k in t for k in _ESTRUCT_KW)
                           and not any(k in t for k in _PROD_EXPLICITO))
    if ctx.get("grupo") == "cuantificar" and prod and not ambiguo_estructural:
        prod_gen = ctx.get("producto", "crudo")
        pieza_gen = "" if prod_gen == "crudo" else f"{prod_gen} de "
        return f"produccion de {pieza_gen}{ctx['entidad']} {texto.strip()}"
```

> **Comportamiento verificado (8 casos, con `ctx = {grupo:'cuantificar', entidad:'CASTILLA'}`):**
>
> | Frase | ¿reformula a producción? | Correcto |
> |---|---|---|
> | «cuántos pozos en mayo» | no → `'que es CASTILLA'` | ✅ H-13 |
> | «cuáles campos en mayo» | no → `'que es CASTILLA'` | ✅ |
> | «qué activo en mayo» | no → `'que es CASTILLA'` | ✅ |
> | «cuántas gerencias tiene» | no → `'que es CASTILLA'` | ✅ |
> | «produjo el campo en mayo» (≤5 tok, verbo explícito) | **sí** | ✅ sin regresión |
> | «cuánto produjo en mayo» | **sí** | ✅ sin regresión |
> | «y en mayo?» | **sí** (es el fallo F4, vía C4) | ✅ |
> | «mayo cuánto ha producido» | **sí** | ✅ |

### H-14 *(4ª pasada, durante la ejecución)* — un test existente aseveraba el bug de F4

Al correr V-8 (suite completa), un test **fuera** del inventario original pasó a fallar:
`tests\test_cuantificar.py::test_continuacion_sin_verbo_de_produccion_no_se_sobreextiende`, que
aseveraba `_continuacion("y en abril?", ctx) is None`.

Verificado con `git stash` que es el **único** cambio entre el código original y el parcheado (los
otros 10 fallos de la suite completa son preexistentes, ajenos a este plan — datos de BD que
cambiaron con el tiempo, y módulos no tocados). El test codificaba el síntoma exacto de F4: una
frase de mes sin verbo de producción explícito debía quedarse sin resolver. Es lo que el usuario
reportó como bug con «y en mayo?», y lo que C4 corrige a propósito.

→ **C7**: se actualiza el assert para reflejar el comportamiento correcto, con el mismo rigor que el
resto del plan — verificado el valor exacto antes de escribirlo, no supuesto.

### C7 · Actualiza el test que aseveraba el bug de F4

**Archivo:** `INGESTA\Rep_Prod\backend\tests\test_cuantificar.py`.

Sustituir:

```python
def test_continuacion_sin_verbo_de_produccion_no_se_sobreextiende():
    # "y en abril?" no trae ningún verbo de producción -> sigue sin resolverse (no se amplía de más).
    ctx = {"grupo": "cuantificar", "entidad": "RUBIALES", "producto": "crudo"}
    assert _continuacion("y en abril?", ctx) is None
```

por:

```python
def test_continuacion_mes_sin_verbo_hereda_entidad():
    # [2026-08-25 · QV2-HILO-DIA F4] Este test aseveraba `is None`: "y en abril?" sin verbo de
    # producción se quedaba sin resolver. Eso ERA el bug reportado por el usuario ("y en mayo?"
    # tras ver la cifra de un mes perdía el hilo — el LLM, viendo la frase desnuda, respondía que
    # "los periodos de tiempo" no son su dominio). _TEMP_CONT_KW ahora incluye los nombres de mes
    # (maquina_q.py), así que esta frase SÍ hereda la entidad del contexto — el comportamiento
    # correcto, no una sobre-extensión: "abril" es la única señal y viene de _TEMP_CONT_KW, no de
    # un verbo de producción inventado.
    ctx = {"grupo": "cuantificar", "entidad": "RUBIALES", "producto": "crudo"}
    assert _continuacion("y en abril?", ctx) == "produccion de RUBIALES y en abril?"
```

### C5 · Tests nuevos

**Archivo:** `…\backend\tests\test_cuantificar_dia.py` — **añadir al final**, sin tocar lo existente:

```python
# ── [2026-08-25 · QV2-HILO-DIA] Regresión de los cuatro fallos reportados ──────────────────

def test_f1_dia_explicito_respeta_el_mes_escrito():
    """«el día 15 de mayo» debe dar MAYO, no el mes del techo (F1)."""
    import datetime
    from app.features.consulta_v2.cuantificar.slots import detectar_dia
    techo = datetime.date(2026, 8, 18)
    r = detectar_dia("el dia 15 de mayo cuanto produjo campo Castilla?", techo)
    assert r is not None and r["clase"] == "fecha"
    assert r["fecha"] == "2026-05-15", f"cambió el mes que el usuario dijo: {r['fecha']}"
    # La forma sin «día» ya funcionaba: no puede romperse.
    assert detectar_dia("el 15 de mayo?", techo)["fecha"] == "2026-05-15"


def test_f3_meses_mapean_a_su_numero_real():
    """setiembre/octubre/noviembre/diciembre estaban corridos un mes (F3)."""
    from app.features.consulta_v2.cuantificar.slots import _MESES_NUM
    assert _MESES_NUM["septiembre"] == 9
    assert _MESES_NUM["setiembre"] == 9
    assert _MESES_NUM["octubre"] == 10
    assert _MESES_NUM["noviembre"] == 11
    assert _MESES_NUM["diciembre"] == 12


def test_f3_fecha_de_octubre_y_diciembre_son_correctas():
    """Consecuencia de F3 en la ruta real."""
    import datetime
    from app.features.consulta_v2.cuantificar.slots import detectar_dia
    techo = datetime.date(2026, 8, 18)
    assert detectar_dia("el 5 de octubre", techo)["fecha"] == "2026-10-05"
    assert detectar_dia("el 3 de diciembre", techo)["fecha"] == "2026-12-03"


def test_f2_out_filtra_solo_lo_que_n1d_resuelve():
    """La rama OUT ignora el rechazo SOLO si N1D sabe resolver la forma (F2 + H-09)."""
    from app.features.consulta_v2.maquina_q import _TECHO_CENTINELA
    from app.features.consulta_v2.cuantificar import slots as _sd
    from app.features.consulta_v2 import no_soportado
    # El catálogo NO cambia: sigue clasificando la forma (lo necesita el ranking).
    assert no_soportado.detectar("el 15 de mayo?") == "dia"
    # Lo que N1D SÍ resuelve -> la rama OUT lo deja pasar.
    for t in ("el 15 de mayo?", "el dia 15 de mayo cuanto produjo Castilla",
              "cuanto produjo Castilla ayer", "el mejor dia del mes"):
        assert _sd.detectar_dia(t, _TECHO_CENTINELA) is not None, t
    # 🔑 H-09: lo que N1D NO resuelve conserva su rechazo honesto. Filtrar por CÓDIGO
    #    (en vez de por detectar_dia) dejaría estas tres mudas — regresión del bug #5.
    for t in ("cuanto produjo Castilla el lunes", "este dia cuanto produjo", "el ultimo dia"):
        assert no_soportado.detectar(t) == "dia", t
        assert _sd.detectar_dia(t, _TECHO_CENTINELA) is None, t


def test_f4_cambio_de_mes_hereda_la_entidad_del_contexto():
    """«y en mayo?» tras una cifra mensual continúa el hilo (F4)."""
    from app.features.consulta_v2.maquina_q import _continuacion
    ctx = {"grupo": "cuantificar", "entidad": "CASTILLA", "producto": "crudo"}
    for frase in ("y en mayo?", "y en junio", "y mayo?"):
        rw = _continuacion(frase, ctx)
        assert rw is not None, f"{frase!r} sigue perdiendo el hilo"
        assert "CASTILLA" in rw
    # Lo que ya funcionaba no se rompe.
    assert _continuacion("y el acumulado?", ctx) == "acumulado de CASTILLA"
    # Una frase que nombra entidad propia es autocontenida: NO se reescribe por esta puerta.
    assert "CASTILLA" not in (_continuacion("produccion de RUBIALES en mayo", ctx) or "")


def test_f4_no_secuestra_preguntas_estructurales():
    """🔑 H-10/H-13: una pregunta de ESTRUCTURA que menciona un mes NO se vuelve producción,
    ni por la rama _TEMP_CONT_KW (C4.b) ni por la rama "Drill N1 GENÉRICO" (C6)."""
    from app.features.consulta_v2.maquina_q import _continuacion
    ctx = {"grupo": "cuantificar", "entidad": "CASTILLA", "producto": "crudo"}
    for frase in ("cuantos pozos en mayo", "cuales campos en mayo", "que activo en mayo",
                  "cuantas gerencias tiene"):
        rw = _continuacion(frase, ctx)
        assert rw is None or not rw.startswith("produccion de"), \
            f"{frase!r} se convirtió en consulta de producción: {rw!r}"


def test_f4_c6_no_rompe_produccion_con_palabra_estructural_generica():
    """🔑 H-13: el guarda de C6 NO debe bloquear producción real que menciona "campo"/"pozo"
    de forma genérica, siempre que traiga un verbo de producción EXPLÍCITO."""
    from app.features.consulta_v2.maquina_q import _continuacion
    ctx = {"grupo": "cuantificar", "entidad": "CASTILLA", "producto": "crudo"}
    # <=5 tokens para no topar con el corte de longitud (ajeno a C6, ver nota de H-13).
    rw = _continuacion("produjo el campo en mayo", ctx)
    assert rw is not None and rw.startswith("produccion de"), \
        f"regresión: producción real bloqueada por mencionar 'campo': {rw!r}"


def test_f4_dia_puntual_elidido_sigue_dando_n1d():
    """H-12: «y el 15 de mayo?» hereda entidad y conserva el grano día."""
    import datetime
    from app.features.consulta_v2.maquina_q import _continuacion
    from app.features.consulta_v2.cuantificar import slots as _sd
    ctx = {"grupo": "cuantificar", "entidad": "CASTILLA", "producto": "crudo"}
    rw = _continuacion("y el 15 de mayo?", ctx)
    assert rw is not None and "CASTILLA" in rw
    sl = _sd.extraer_slots(rw, entidad_valor="CASTILLA", techo=datetime.date(2026, 5, 17))
    assert sl.get("nivel_temporal") == "N1D"
    assert sl["dia"]["fecha"] == "2026-05-15"
```

---

## 8. ORDEN DE EJECUCIÓN

| Paso | Cambio | Verificación inmediata |
|---|---|---|
| 1 | **C3** (mapa de meses) | `V-3`: octubre→10, diciembre→12 |
| 2 | **C1** (regex del día) | `V-1`: «el día 15 de mayo» → `2026-05-15` |
| 3 | **C2** (rama OUT + import + centinela) | `V-2` **y** `V-2b`: filtra «el 15 de mayo», **conserva** el rechazo de «el lunes» |
| 4 | **C4.a + C4.b** (meses **y** guarda estructural) | `V-4`: «y en mayo?» hereda CASTILLA |
| **4b** | **C6.a + C6.b** (`_PROD_EXPLICITO` + guarda en "Drill N1 GENÉRICO") | `V-4b`: «cuántos pozos en mayo» **no** se vuelve producción; «produjo el campo en mayo» **sigue** siéndolo |
| 5 | **C5** (tests) | `V-5`: los 8 tests nuevos pasan |
| 6 | Suite completa | `V-6`: **78 + 8 = 86 passed**, 0 failed |

> ⚠️ **C2, C4 y C6 son cambios de DOS piezas cada uno.** C2 = filtro + import + constante centinela.
> C4 = ampliar la tupla (C4.a) **y** añadir la guarda estructural en `_TEMP_CONT_KW` (C4.b). **C6** =
> `_PROD_EXPLICITO` (C6.a) **y** su guarda en la rama "Drill N1 GENÉRICO" (C6.b) — **necesario porque
> C4.b, por sí solo, NO basta**: hay una tercera rama preexistente que reproduce el mismo secuestro
> por otra vía (H-13). Aplicar solo la primera mitad de cualquiera de los tres **introduce una
> regresión** (H-09, H-10, H-13).

> C3 va **primero** a propósito: C1 hace que más textos lleguen al mapa de meses, así que corregir el
> mapa antes evita que un fallo tape al otro.
> **Si un paso falla, DETENERSE** y reportar. No «arreglar sobre la marcha».

---

## 9. REGLAS NO NEGOCIABLES

| # | Regla | Por qué |
|---|---|---|
| R-0 | **C2 filtra por `detectar_dia()`, NUNCA por el código de la forma** | Filtrar por código deja «el lunes», «este día» y «el último día» sin rechazo → reintroduce el bug #5 (H-09) |
| R-0b | **C4 lleva SIEMPRE su guarda `_ESTRUCT_KW` (C4.b)** | Sin ella, «cuántos pozos en mayo» devuelve una cifra de producción (H-10) |
| R-0c | **C6 lleva SIEMPRE su guarda `ambiguo_estructural`, y usa `_PROD_EXPLICITO`, NUNCA `not any(_ESTRUCT_KW)` a secas** | Sin C6, la rama "Drill N1 GENÉRICO" reproduce el bug de H-10 por otra vía. Un guarda simétrico al de C4.b ROMPE «cuánto produjo el campo en mayo» (H-13) |
| R-1 | **No retirar `dia` ni `selector_dia` de `no_soportado._FORMAS`** | Rompe el ranking N5 y deja 3 formas sin respuesta ni rechazo (H-03, D-2) |
| R-2 | **No tocar `respuesta_cuantificar._FORMAS_RECHAZO`** | Ya es correcto (H-02); el bug estaba en la rama OUT |
| R-3 | **No modificar los asserts existentes de `test_no_soportado.py`** | Siguen siendo válidos: el catálogo no cambia (H-05) |
| R-4 | **No tocar la tupla `_MESES`** | La usa `_periodo_texto`; su orden importa allí (D-4) |
| R-5 | **`slots.py` sigue siendo PURO** (sin imports de BD) | Su cabecera lo declara: el `techo` entra como parámetro |
| R-6 | **Comentarios en español**, explicando el porqué | Estilo del repo |
| R-7 | **Usar `.\.venv\Scripts\python.exe`**, nunca el `python` del PATH | El del PATH no tiene fastapi (P-2) |
| R-8 | **No declarar «verificado» sin probar en la app** | DT-15/R3: pytest verde ≠ el chat responde bien |

---

## 10. VALIDACIONES

### 10.0 · Reproducir los fallos ANTES de tocar nada (P-4)

```bash
cd c:\APLICACIONES\ProdIA\12112025_prodIA\ProdIA-2.0\ProdIA-2.0\INGESTA\Rep_Prod\backend
.\.venv\Scripts\python.exe -c "
import sys; sys.path.insert(0,'.')
import datetime
from app.features.consulta_v2.cuantificar.slots import detectar_dia, _MESES_NUM
from app.features.consulta_v2.maquina_q import _continuacion
techo = datetime.date(2026,8,18)
print('F1:', detectar_dia('el dia 15 de mayo cuanto produjo campo Castilla?', techo))
print('F3: diciembre ->', _MESES_NUM['diciembre'])
print('F4:', _continuacion('y en mayo?', {'grupo':'cuantificar','entidad':'CASTILLA','producto':'crudo'}))
"
```

**Debe imprimir (el estado ROTO):** `fecha 2026-08-15` · `diciembre -> 13` · `None`.

### 10.1 · Criterios de aceptación

| # | Comprobación | Comando | Esperado |
|---|---|---|---|
| V-1 | F1 respeta el mes | `detectar_dia('el dia 15 de mayo …', date(2026,8,18))` | `fecha == '2026-05-15'` |
| V-2 | F2: OUT deja pasar lo resoluble | `detectar_dia('el 15 de mayo?', _TECHO_CENTINELA)` | **no** `None` |
| **V-2b** | **F2: OUT CONSERVA el rechazo huérfano** (H-09) | `detectar_dia('cuanto produjo Castilla el lunes', _TECHO_CENTINELA)` | **`None`** → sigue rechazándose |
| V-3 | F3 meses correctos | `_MESES_NUM['diciembre']` | `12` |
| V-4 | F4 hereda entidad | `_continuacion('y en mayo?', ctx)` | contiene `CASTILLA` |
| **V-4b** | **F4 NO secuestra lo estructural** (H-10 + H-13, requiere C4.b **y** C6) | `_continuacion('cuantos pozos en mayo', ctx)` | `None` o **sin** `produccion de` |
| **V-4c** | **C6 no rompe producción real** (H-13) | `_continuacion('produjo el campo en mayo', ctx)` | **sí** empieza con `produccion de` |
| V-5 | Tests nuevos | `pytest tests\test_cuantificar_dia.py -q` | todos pasan |
| V-6 | **Sin regresión** | `pytest tests\test_no_soportado.py tests\test_cuantificar_dia.py tests\test_capacidades.py tests\test_incompleta.py -q` | **86 passed**, 0 failed |
| V-7 | Golden del clasificador | `PYTHONPATH=. .\.venv\Scripts\python.exe app\features\consulta_v2\golden\run_golden.py` | gate ≥90% (medido: 92%; los 7 fallos son por LLM inalcanzable en este entorno, ajenos a F1-F4) |
| V-8 | Suite completa | `pytest tests\ -q` | **10 fallos preexistentes** (verificados con `git stash` contra el código original — BD real con conteos que cambiaron, y módulos no tocados), **0 nuevos** tras C7 |

### 10.2 · Validación en la app (DT-15 / R3) — **la que manda**

Con Flask `:8020` e INGESTA `:8088` arrancados, en el chat de Consulta:

| # | Escribir | Esperado |
|---|---|---|
| V-9 | «el día 15 de mayo cuánto produjo campo Castilla?» | Cifra del **15 de mayo**; el texto dice mayo, no agosto |
| V-10 | Luego: «el 15 de junio?» | Responde ese día; **no** dice «solo puedo darte el mes completo» |
| V-11 | «Muéstrame la producción de Castilla en junio» → «y en mayo?» | Da la cifra de **mayo de CASTILLA**; no habla de «periodos de tiempo» |
| V-12 | «cuánto produjo Castilla el lunes» | **Sigue** rechazando honestamente (H-03: N1D no cubre días de semana) |
| V-13 | «top 5 campos el 15 de mayo» | **Sigue** rechazando (el ranking es mensual, R-1) |

---

## 11. FUERA DE ALCANCE

| Qué | Por qué |
|---|---|
| Días de la semana («el lunes»), «este día», «el último día» | N1D no los resuelve; hoy tienen rechazo honesto, que es el comportamiento correcto (H-03). Ampliarlos es otro plan |
| Añadir «te doy un día puntual» al inventario de `capacidades.py` | H-08: cierto tras este plan, pero es cambio de copy con su propia regla (no prometer lo no construido) |
| PPTO diario / comparación de cumplimiento a grano día | No existe el dato: `fact_produccion_dia_ecp` no tiene `escenario_id` (`no_soportado.py:66-68`) |
| El desfase de ~100 días del dato diario | Es de ingesta, no del clasificador |
| Frontend / `static\` / `MainChat\` | Estos cuatro fallos son 100 % backend |

---

## 12. DEFINITION OF DONE

- [ ] Los 4 fallos reproducidos ANTES (§10.0) y no reproducibles DESPUÉS.
- [ ] C1, C2 (**filtro + import + centinela**), C3, C4 (**C4.a + C4.b**), C6 (**C6.a + C6.b**) aplicados, con comentarios en español.
- [ ] **C2 filtra por `detectar_dia()`, no por código** (R-0); **C4.b** está puesta (R-0b); **C6.b usa
      `ambiguo_estructural`/`_PROD_EXPLICITO`, no un guarda simétrico a secas** (R-0c).
- [ ] C5: 8 tests nuevos añadidos, sin tocar los existentes.
- [ ] C7: el assert obsoleto de `test_cuantificar.py` actualizado (H-14) — único archivo de test fuera
      del §6 original, incorporado con su propia justificación.
- [ ] V-1 a V-6 en verde (**86 passed** en la suite acotada); V-7 gate ≥90%; **V-8: 10 fallos
      preexistentes (verificados con `git stash`), 0 nuevos**.
- [ ] `no_soportado._FORMAS` y `respuesta_cuantificar._FORMAS_RECHAZO` **sin modificar** (R-1, R-2).
- [ ] «el lunes» y «top 5 campos el 15 de mayo» siguen rechazándose (V-12, V-13).
- [ ] V-9 a V-13 medidos **en la app**, no solo en pytest.
- [ ] **Estado = «PENDIENTE de validación humana» hasta que el usuario lo confirme** (R-8).

---

## 13. PROMPT PARA EL AGENTE EXECUTOR

```
Eres un agente EXECUTOR. Lee completo el plan
c:\APLICACIONES\ProdIA\12112025_prodIA\ProdIA-2.0\ProdIA-2.0\INGESTA\Rep_Prod\Planes\plan_QV2-HILO-DIA_20260825.md
y ejecútalo AL PIE DE LA LETRA.

Reglas:
- CERO modificaciones al plan. No decides nada: las decisiones están cerradas en §3.
- Respeta las 10 reglas no negociables del §9. Las TRES que rompen funcionalidad
  viva si se ignoran:
    · R-0  C2 filtra por detectar_dia(), NUNCA por el código de la forma. Filtrar
           por código deja "el lunes"/"este día"/"el último día" sin rechazo Y sin
           respuesta (H-09). Parecerá más simple y es una regresión.
    · R-0b C4 son DOS ediciones: ampliar la tupla (C4.a) Y añadir la guarda
           _ESTRUCT_KW (C4.b). Con solo C4.a, "cuántos pozos en mayo" devuelve una
           cifra de producción (H-10).
    · R-1  NO retires 'dia' de no_soportado._FORMAS (parecerá la solución obvia y
           NO lo es — el plan explica por qué en H-03).
- ANTES de tocar nada, ejecuta §10.0 y confirma que los 4 fallos se reproducen.
  Si NO se reproducen, DETENTE: el código no está en el estado que el plan asume.
- Orden secuencial del §8. C3 va primero a propósito. Si un paso falla, DETENTE.
- Usa SIEMPRE .\.venv\Scripts\python.exe — el python del PATH no tiene fastapi.
- Solo se tocan 3 archivos (§6): slots.py, maquina_q.py y test_cuantificar_dia.py.
  NO toques no_soportado.py, respuesta_cuantificar.py ni test_no_soportado.py.
- Comentarios en español, explicando el PORQUÉ (estilo del repo).
- pytest verde NO es "verificado": V-9 a V-13 exigen la app corriendo. Si no
  puedes abrirla, tu reporte final es "PENDIENTE de validación humana".

Reporta: ✅/❌ Paso N por cada paso del §8 con su verificación inmediata.
Presta atención especial a V-2b y V-4b: son las que detectan si aplicaste solo la
mitad de C2 o de C4.
Al final: archivos tocados + tabla de V-1 a V-13 (cuáles comprobaste y cuáles
requieren la app) + el conteo de pytest (esperado: 85 passed) + "¿Hago commit?".
```

---

## 14. REFERENCIAS

- Marco: `INGESTA\Rep_Prod\clmd\CLAUDE_muestra.md` §0.2, §0.3, §15, §17 (DT-15, DT-16), §17.5 R3.
- Antecedentes: `INGESTA\Rep_Prod\Planes\plan_clasificador_motor_q_v2_2026-07-30.md` (Motor v2),
  el plan **QV2-GRANO-DIA** (N1D/N1DSEL, 2026-08-25) citado en `slots.py:54` y
  `respuesta_cuantificar.py:134`.
- Sesión de origen: capturas del usuario del 2026-08-25, 21:05-21:08.
