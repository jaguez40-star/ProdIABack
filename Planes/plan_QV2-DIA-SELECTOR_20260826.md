# QV2-DIA-SEL — El selector de día entiende «la producción más baja»

**Fecha:** 2026-08-26
**Alias:** `QV2-DIA-SEL`
**Antecedente:** `QV2-GRANO-DIA` (que introdujo `_RX_SELECTOR`) y `plan_panel_comportamiento_dia_2026-08-25.md`.
**Origen:** prueba en vivo del usuario. Preguntó por el día de producción **más baja** y el
sistema respondió, con toda seguridad, el día de producción **más alta**.

**Rev. 2** — reescrito tras auditoría adversarial doble (regex/lingüística + integración), toda
ella con ejecución real del módulo. La rev. 1 acertaba el diagnóstico pero **su solución tenía
cuatro defectos y su alcance estaba incompleto**. El §11 detalla qué se descartó y por qué.

---

## 1. El problema

`detectar_dia()` decide entre máximo y mínimo mirando **solo el cuantificador** (`MAS`/`MENOS`)
e ignorando el **adjetivo**. En español el sentido vive en el adjetivo: «más **baja**» es un
superlativo de mínimo.

El sistema **afirma el valor opuesto al preguntado**. No falla, no avisa, no degrada — responde
otra cosa con la misma confianza. Es el modo de fallo que `slots.py:66-69` ya declara
inaceptable para el mes: *«se pidió MAYO y se respondió AGOSTO, afirmándolo sin avisar»*.

---

## 2. Evidencia medida

`slots.detectar_dia(frase, techo=2026-08-18)`, módulo puro, sin BD. **8 correctos de 16:**

| Frase | Espera | Da | |
|---|---|---|---|
| que dia fue el de produccion **mas baja** | min | **max** | ❌ invertido |
| que dia tuvo la produccion **mas bajo** | min | **max** | ❌ invertido |
| en que dia **bajo mas** la produccion | min | **max** | ❌ invertido |
| que **dias** fue la produccion mas baja | min | **None** | ❌ no detecta |
| que dia fue el de **menor** produccion | min | **None** | ❌ no detecta |
| que **dias** fue la produccion mas alta | max | **None** | ❌ no detecta |
| que dia fue el de **mayor** produccion | max | **None** | ❌ no detecta |
| el dia de **mas produccion** | max | **None** | ❌ no detecta |
| «peor día», «día de menor», «mejor día», «día de mayor», «se produjo más/menos» (8) | — | — | ✅ |

---

## 3. Los cinco fallos (tres del código, dos que destapó la auditoría)

### 3.1 El adjetivo no se mira → los 3 invertidos

`slots.py:122-123`:
```python
g = m.group(0)
orden = "min" if ("PEOR" in g or "MENOS" in g or "MENOR" in g) else "max"
```
`g` es solo el fragmento que casó, y para `QUE DIA … (MAS|MENOS)` **termina en «MAS»**: la
palabra «baja» nunca entra. Y aunque entrara, la lógica no la conoce. El `else "max"` convierte
en máximo todo lo no reconocido, en silencio.

### 3.2 El plural no entra → 2 no detectados

`\bQUE\s+DIA\s+` no casa con «días». La pregunta se sale del grano día y cae a **N1**: responde
el KPI del mes. Es el bloque 5 de la captura del usuario.

### 3.3 `MAYOR`/`MENOR` solo pegados a «DÍA DE» → 3 no detectados

La alternativa `\bDIA\s+DE\s+(MAYOR|MENOR)\b` exige las tres palabras seguidas. «qué día fue el
de menor producción» intercala «fue el» y cae entre dos sillas.

### 3.4 🔴 «MAYO» es substring de «MAYOR» — bug PREEXISTENTE, silencioso

`slots.py:124` busca el mes por **substring**:
```python
mo = next((num for nom, num in _MESES_NUM.items() if nom.upper() in t), None)
```
`"MAYO" in "MAYOR"` es `True`. **Medido:**

| Frase | mes | asumido |
|---|---|---|
| «dia de **mayor** produccion de castilla» | **5 (mayo)** | **`[]`** ← cree que el usuario dijo mayo |
| «dia de **menor** produccion de castilla» | 8 (techo) | `['periodo=08/2026']` ← correcto |

La asimetría lo delata: solo «mayor» se envenena. Con `asumido=[]` el sistema **no avisa de
nada**. Ya ocurre hoy con `DIA DE MAYOR`; la rev. 1 metía `MAYOR` en dos alternativas más,
**multiplicando el radio de un bug que no había visto**.

### 3.5 🔴 La lógica está en TRES sitios, no en dos

La rev. 1 declaraba dos gemelos. Hay un tercero, con la misma regex más una alternativa:

| Archivo | Decide | Línea |
|---|---|---|
| `cuantificar/slots.py` | el NIVEL (`N1DSEL`) y el orden | `:72-73` |
| `config/patrones_grupo.yaml` | el GRUPO (`cuantificar`) | `:169-170`, `:189` |
| **`consulta_v2/no_soportado.py`** | **el rechazo del fork de RANKING** | **`:92-93`** |

Y el tercero es el crítico (§4).

---

## 4. 🔑 El fork de RANKING va PRIMERO — y su único guardián es el gemelo olvidado

`respuesta_cuantificar.py:171-178`: el ranking se evalúa **antes** del resolver y antes de
`slots`. Su única salida hacia el grano día es `_forma_no_soportada_ranking` (`:159-162`), que
consulta `no_soportado.detectar` — el regex de `no_soportado.py:92-93`.

**Consecuencia:** si una pregunta nombra un nivel (`campo`/`activo`) y un superlativo, **el
ranking gana siempre**, y solo ese regex puede devolverla al selector de día. Medido:

| Pregunta | guarda | Qué pasa hoy |
|---|---|---|
| «cual campo tuvo el **mejor dia**» | `selector_dia` | ✅ rechazo honesto |
| «cuales campos tuvieron los **peores dias**» | **None** | ❌ ranking mensual, ignora «días» |
| «cual campo tuvo los **dias de mayor** produccion» | **None** | ❌ ídem |
| «los 5 campos con los **dias de mas** produccion» | **None** | ❌ ídem |

Las tres últimas son **exactamente las formas que este plan añade**. Sin tocar
`no_soportado.py`, `slots` sabría reconocerlas pero **nunca las vería**.

La rev. 1 planteaba el riesgo al revés («el selector le roba al ranking») y marcaba como
«ambiguo» un caso —«qué campo produjo más el día 15»— que **ya está resuelto** hoy.

---

## 5. Reglas del proyecto que gobiernan el diseño

| Regla | Origen | Consecuencia |
|---|---|---|
| **Nunca degradar en silencio** | `slots.py:66-69`, `:145-150` | Si la dirección o el mes son ambiguos: avisar o no responder. **Nunca asumir** |
| Módulo puro, sin BD | `slots.py:56` | Arreglo y tests sin tocar la base de datos |
| El techo centinela permite preguntar «¿sabes resolver esta forma?» sin BD | `maquina_q.py:78`, `:500-506` | Es la técnica que elimina el gemelo de `no_soportado` (§6.5) |
| `menciona_dia` comparte `_RX_SELECTOR` | `slots.py:98-105` | Se vuelve más permisivo. **Medido: delta cero** en el corpus real (§8.4) |
| Precedencia de grupo: `analizar` gana | `patrones.py:69-72` | «por qué bajó… el día 15» sigue en `analizar`. Verificado |

---

## 6. Diseño

### 6.1 Léxico de dirección — un solo sitio, exportable

En `slots.py`, junto a `_RX_SELECTOR`. **Se exporta** para que `no_soportado.py` lo importe
(§6.5) y no nazca un cuarto gemelo.

```python
# [2026-08-26] QV2-DIA-SEL. El ADJETIVO manda sobre el cuantificador: "más BAJA" es un MÍNIMO
# aunque lleve "más". Incluye los VERBOS de dirección: la rev.1 metió CAYO en el detector y se
# olvidó de meterlo aquí, así que "¿en qué día cayó más?" detectaba... y respondía el máximo.
_DIR_MIN = (r"(?:BAJ[AO]S?|MENOR(?:ES)?|MENOS|PEOR(?:ES)?|MINIM[AO]S?|"
            r"CAY[OÓ]|CAIDAS?|DESPLOM\w*|DESCENDI\w*|FLOJ[AO]S?)")
_DIR_MAX = (r"(?:ALT[AO]S?|MAYOR(?:ES)?|MAS|MEJOR(?:ES)?|MAXIM[AO]S?|"
            r"SUBI[OÓ]|CRECI\w*|AUMENT\w*|DISPAR\w*|PICOS?|RECORD)")
```

⚠️ Corren **después de `norm()`**, que pliega acentos: `PEQUEN`, no `PEQUEÑ`. Verificar contra
`normaliza.py:6`.

**Fuera del léxico a propósito** (medido como léxico muerto o superficie de ataque):
`PEQUEN[AO]S?` — «producción pequeña» no se dice; y `GRANDES?` — aparece referido a pozos y
campos, no a producción («el pozo más grande»), y sería un falso positivo esperando a ocurrir.

### 6.2 `_orden_selector` — por PROXIMIDAD, con caso explícito para máximo y salida ambigua

**Este es el corazón de la rev. 2.** La rev. 1 leía el texto completo y tenía tres casos para
`min` y **cero para `max`** (el máximo salía de un `else`). Medido, eso invierte:

| Frase | rev. 1 daba | Correcto |
|---|---|---|
| «cual fue el **mejor** dia del **peor** mes» | min | max |
| «cual fue el **mejor** dia de mayo y el **peor**» | min | max |
| «que dia tuvo **mayor** produccion en el campo con **menos** pozos» | min | max |

Un `MENOR`/`PEOR` en cualquier parte —aunque califique a otro sustantivo— volteaba la respuesta.
Es el `else "max"` del §3.1 reinstalado por la puerta de al lado.

Diseño correcto: **ventana alrededor del `DIA` que casó**, casos simétricos, y un tercer valor
para lo ambiguo.

```python
def _orden_selector(t: str, ini: int, fin: int):
    """"min" | "max" | None (ambiguo). `ini`/`fin` acotan el match del selector: la dirección se
    busca en su VECINDAD, no en toda la frase — "el mejor día del peor mes" habla de un máximo,
    y un PEOR a diez palabras no puede voltearlo.
    🔑 Simétrico: hay caso explícito para max. Un `else "max"` es justo el bug que este plan
    existe para eliminar.
    🔑 Devuelve None si aparecen AMBAS direcciones en la ventana ("el día de más producción y el
    de menos"): la regla del §5 exige avisar, no elegir en silencio."""
    v = t[max(0, ini - 30):min(len(t), fin + 60)]
    v = _RX_EXCLUIR.sub(" ", v)          # §6.4
    hay_min = re.search(r"\bMAS\s+" + _DIR_MIN, v) or re.search(r"\b" + _DIR_MIN + r"\b", v)
    hay_max = re.search(r"\bMAS\s+" + _DIR_MAX, v) or re.search(r"\b" + _DIR_MAX + r"\b", v)
    if hay_min and hay_max:
        # "MAS BAJA" cuenta como min aunque MAS esté en _DIR_MAX: la combinación manda.
        if re.search(r"\bMAS\s+" + _DIR_MIN, v):
            return "min"
        if re.search(r"\bMAS\s+" + _DIR_MAX, v):
            return "max"
        return None                       # dos direcciones reales → ambiguo
    if hay_min:
        return "min"
    if hay_max:
        return "max"
    return None                           # sin dirección reconocible → ambiguo, NO "max"
```

**Qué hace `detectar_dia` con `None`:** devolver `None` (la pregunta no se resuelve como
selector) y dejar que caiga a la ruta de rechazo honesto, que ya existe. **No** asumir máximo.

### 6.3 `_RX_SELECTOR` — cuatro construcciones, ventana de 60

```python
_RX_SELECTOR = re.compile(
    r"\b(?:MEJOR|PEOR)(?:ES)?\s+DIAS?\b"
    r"|\bDIAS?\s+(?:DE|CON)\s+(?:" + _DIR_MIN + "|" + _DIR_MAX + r")\b"
    r"|\b(?:QUE|CUAL(?:ES)?)\s+DIAS?\b.{0,60}?\b(?:" + _DIR_MIN + "|" + _DIR_MAX + r")\b"
    r"|\bEN\s+QUE\s+DIAS?\b.{0,60}?\b(?:" + _DIR_MIN + "|" + _DIR_MAX + r")\b"
)
```

Cambios frente al actual, cada uno atacando un fallo del §3:

1. `DIAS?` en todas → entra el plural (§3.2).
2. `_DIR_MIN|_DIR_MAX` completos en las cuatro → `MAYOR`/`MENOR`/`MAS`/`MENOS` disponibles en
   todas las construcciones (§3.3).
3. `DIAS?\s+(?:DE|CON)` → cubre «el día **con** mayor producción», forma muy frecuente.
4. `CUAL(?:ES)?\s+DIAS?` → «**cuál día** tuvo…», muy usado en Latinoamérica.
5. Ventana **60**, no 40. Medido el hueco real entre «QUE DIA» y el adjetivo: 19-22 en las
   preguntas del usuario, pero **46-49** en cuanto se intercalan entidad y mes («que dia del
   mes de julio tuvo castilla la produccion mas baja»), que es igual de natural. La rev. 1
   justificaba el 40 con un solo ejemplo de 32.
6. **Se elimina la alternativa de verbos sueltos** (`SUBIO|BAJO|CAYO`) de la rev. 1: los verbos
   ya viven en el léxico (§6.1) y entran por la construcción 4. Además evita el secuestro de N4
   (§7.2).

> El `.{0,60}?` **no codicioso es cosmético**: no cambia el lenguaje aceptado, solo el
> `group(0)`. La rev. 1 afirmaba que «evita comerse un segundo cuantificador», lo cual es falso
> —verificado sobre 2000 frases: cero discrepancias con la versión codiciosa—. Se conserva
> porque acota el `group(0)` que ahora sí importa: es la ventana de §6.2.

### 6.4 Exclusiones — falsos positivos medidos

```python
# [2026-08-26] Formas donde el token de dirección NO expresa un superlativo de producción.
_RX_EXCLUIR = re.compile(
    r"\bMAS\s+DE\s+\d"                    # "mas de 5000 barriles" → umbral, no superlativo
    r"|\bMANTENIMIENTO\s+MAYOR\b"         # terminología de industria (major overhaul)
    r"|\bBAJO\s+(?:EL|LA|LOS|LAS)\b"      # "bajo el presupuesto" → preposición, no adjetivo
)
```

Se aplican **dentro de la ventana** de `_orden_selector` (§6.2) y como guarda previa en
`detectar_dia`: si tras excluir no queda dirección, la pregunta no es selector.

Falsos positivos medidos que esto cierra: «que dia se hizo el mantenimiento **mayor**», «en que
dias hubo **mas de** 5000 barriles», «en que dias la produccion estuvo **bajo el** presupuesto».

Verificado limpio **sin** necesidad de exclusión: «cuantos dias con reporte», «produccion dia a
dia», «promedio diario», «por que bajo la produccion el dia 15», y las tres de ranking del §8.3.

### 6.5 🔑 Eliminar el tercer gemelo en vez de sincronizarlo

`no_soportado.py:92-93` no se reescribe: **se sustituye por una llamada al detector real**,
igual que ya hace la rama OUT en `maquina_q.py:504-505`:

```python
# en respuesta_cuantificar.py, _forma_no_soportada_ranking
if _slots.detectar_dia(texto, _TECHO_CENTINELA) is not None:
    return "selector_dia"
```

`_TECHO_CENTINELA` (`maquina_q.py:78`, `_date(2000, 1, 15)`) permite preguntar «¿sabes resolver
esta forma?» sin tocar BD; la fecha que salga se descarta.

**Por qué es mejor que sincronizar:** hay un solo detector, el §3.5 deja de poder repetirse, y
el §4 desaparece estructuralmente. Es la diferencia entre documentar una clase de bug y
eliminarla.

⚠️ Si el executor encuentra que `no_soportado.detectar` se usa desde más sitios con expectativas
distintas, **que pare y lo reporte** antes de tocar la entrada `selector_dia`.

### 6.6 `slots.py:124` — el mes por TOKEN, no por substring

Arregla el §3.4. Es prerequisito: sin esto, habilitar `MAYOR` en más alternativas propaga el
mes falso.

```python
mo = next((num for nom, num in _MESES_NUM.items()
           if re.search(r"\b" + nom.upper() + r"\b", t)), None)
```

⚠️ Es un arreglo **preexistente** que este plan absorbe por necesidad. Verificar que no rompe
`_periodo_texto`, que usa `_MESES` (otra lista) por otra vía.

### 6.7 `patrones_grupo.yaml` — generado del mismo léxico

```yaml
    - '(MEJOR|PEOR)(ES)?\s+DIAS?\b'
    - '(QUE|CUAL(ES)?)\s+DIAS?\b.{0,60}?\b(MAS|MENOS|MAYOR|MENOR|ALTA|BAJA|MEJOR|PEOR|MAXIM\w*|MINIM\w*)\b'
    - 'DIAS?\s+(DE|CON)\s+(MAYOR|MENOR|MAS|MENOS|ALTA|BAJA|MAXIM\w*|MINIM\w*)'
```
Conservar `:189` (`MAS (ALTA|BAJA) PRODUCCION`), que ya existía y acertaba.

La rev. 1 dejaba **5 desincronizaciones** medidas entre este YAML y `slots.py` (le faltaban
`ALTA|BAJA|MEJOR|PEOR|MAXIM|MINIM` y la cuarta alternativa entera) — reintroduciendo el mismo día
el desfase que el plan diagnostica como causa del bug.

> **Atenuante medido:** `patrones_grupo.yaml:155` es `\bPRODUCCION\b` a secas, así que casi
> cualquier pregunta con esa palabra llega a `cuantificar` igualmente. Lo que el YAML salva son
> las formas telegráficas sin «producción» («el día de máxima», «en qué días cayó el crudo»).

---

## 7. Decisiones de alcance

### 7.1 Cobertura sintáctica: qué entra y qué no

La auditoría midió **24 formas naturales; 18 no se detectan hoy**. El §6.3 cubre las tres
construcciones más frecuentes (`DIA DE/CON`, `QUE/CUAL DIA`, plural). **Quedan fuera,
declaradas:**

| Forma | Por qué queda fuera |
|---|---|
| «el día **más bajo** de producción» (`DIA <adj>` sin `DE`) | Colisiona con «el día 15 más…»; necesita su propio análisis |
| «**cuándo** fue la producción más baja» | `CUANDO` no implica grano día; puede ser mes o año |
| «qué **fecha**/**jornada**…» | Sinónimos de día; ampliación mecánica, fase B |
| «el **pico**/**récord**/**top** de producción» | En el léxico (§6.1) pero sin construcción propia |

**Criterio:** este plan elimina la **inversión** (responder lo contrario), que es un fallo de
corrección. La no-detección es un fallo de cobertura: cae a N1 y responde el KPI del mes —
también silencioso, pero menos dañino. La cobertura restante es una fase B con su propio plan.

### 7.2 «En qué días subió la producción» — se queda en N4

`SUBIO`/`BAJO`/`CAYO` están en `_VAR_WORDS` (`slots.py:31-32`) y hoy resuelven a **N4**
(variación mes a mes). `slots.py:249-251` da precedencia a `detectar_dia` sobre el nivel, así
que la alternativa de verbos sueltos de la rev. 1 **habría secuestrado N4** sin declararlo.

Al eliminarla (§6.3 punto 6), «en qué días subió la producción» sigue en N4. Los verbos solo
actúan cuando ya hay una construcción de día explícita («en qué **día** cayó **más** la
producción»).

### 7.3 Ambigüedad → se avisa, no se elige

Nuevo comportamiento (§6.2): «el día de más producción **y el de menos**» devuelve `None` y cae
al rechazo honesto. Antes elegía `min` en silencio. Es la regla del §5 aplicada literalmente.

---

## 8. Validación

### 8.1 Batería unitaria — asertar `orden` **Y** `mes`

⚠️ **La rev. 1 habría pasado en verde con la respuesta equivocada.** Sus 16 asertos comparaban
solo `orden`; «que dia fue el de mayor produccion» da `orden="max"` ✅ y `mes=5` ❌ (§3.4) en la
misma llamada. **Cada caso debe asertar la tupla `(orden, mes, asumido)`.**

En `tests/test_cuantificar_dia.py`, junto a los de selector (`:55-69`). Cuatro bloques:

1. **Los 16 del §2** — con `orden` y `mes`.
2. **Las 3 inversiones por contexto** del §6.2 («mejor día del peor mes», etc.) → `max`.
3. **Los verbos** — «en qué día cayó más» → `min`; «en qué día subió más» → `max`.
4. **Ambigüedad** — «el día de más producción y el de menos» → `None`.

### 8.2 Falsos positivos — deben seguir dando `None`

«que dia se hizo el mantenimiento mayor» · «en que dias hubo mas de 5000 barriles» · «en que
dias la produccion estuvo bajo el presupuesto» · «cuantos dias con reporte» · «produccion dia a
dia» · «promedio diario» · «por que bajo la produccion el dia 15» (debe seguir en `analizar`).

### 8.3 Ranking — el riesgo real es el OPUESTO al que creía la rev. 1

Que sigan en **ranking**: «los 5 campos que más crudo producen», «qué campo produjo más crudo en
mayo», «campos con menor producción». *(Verificado: ninguna casa el regex nuevo.)*

Que pasen a **rechazo honesto** gracias a §6.5 — hoy dan ranking mensual en silencio:
«cuáles campos tuvieron los **peores días**» · «cuál campo tuvo los **días de mayor**
producción» · «los 5 campos con los **días de más** producción».

Y el agujero que el plural abre (§6.3): «los **días** de mayor producción **del año**» y «**top
3 días** de mayor producción» piden **varios** días —es ranking a grano día, fuera de alcance—
y el selector respondería **uno solo**. Deben caer en el rechazo honesto, no responder un día.
**Si el executor no logra que caigan ahí, que pare y lo reporte.**

### 8.4 Los goldens NO pueden validar esto — no fingir que sí

Medido:
- `golden/clasificacion_golden.yaml` y `golden/cuantificar_golden.yaml`: **cero casos** de
  selector de día.
- `run_golden_cuantificar.py:46` llama `extraer_slots(pregunta)` **sin `techo`**. Con
  `techo=None`, `detectar_dia` corta en `slots.py:126-127` y devuelve `None` para todo selector
  sin mes explícito. **El runner es estructuralmente incapaz de ejercitar el selector.**

Por tanto la validación de este plan es **unitaria (§8.1-8.3)**. Los goldens se corren solo
como no-regresión de lo demás:
`PYTHONPATH=. uv run python app/features/consulta_v2/golden/run_golden.py` (gate ≥90%).

**Oportunidad, no obligación:** añadir `techo:` opcional por caso en `cuantificar_golden.yaml` y
pasarlo en `run_golden_cuantificar.py:46` haría el gate capaz de vigilar N1D/N1DSEL. Sin eso,
cualquier caso de día que se añada al golden **pasa vacuamente**.

### 8.5 `menciona_dia` — ya medido, no hay que medirlo otra vez

Delta **cero** sobre los 116 casos de ambos goldens (2 disparos antes, 2 después). Razón
estructural: solo se invoca en `respuesta_cuantificar.py:227-230`, después de resolver entidad y
del fork de ranking. `techo_dia` es un único `SELECT MAX(fecha)`. **El paso de medición que
pedía la rev. 1 se elimina del plan.**

### 8.6 En vivo

Las dos preguntas de la captura, con el mes **bien escrito**:
1. «Que dias fue la produccion mas baja en castilla durante el mes de Julio?» → día **mínimo**
   de julio, no el KPI de agosto.
2. «Que dia fue el de produccion mas baja en castilla durante el mes de Julio?» → **peor** día,
   no «el mejor día».

---

## 9. Orden de trabajo

| # | Paso | Entregable |
|---|---|---|
| **1** | Batería del §8.1 **antes de tocar código**, asertando `(orden, mes)` | Rojo salvo los 8 que ya pasan. Reportar conteo |
| **2** | §6.6 — mes por token (`\bMAYO\b`) | «día de mayor producción» deja de creer que es mayo |
| **3** | §6.1 léxico + §6.4 exclusiones + §6.2 `_orden_selector` | Los 3 invertidos y las 3 inversiones por contexto, en verde |
| **4** | §6.3 `_RX_SELECTOR` | Los 5 no detectados, en verde |
| **5** | §6.5 — eliminar el gemelo de `no_soportado` vía centinela | §8.3 en verde |
| **6** | §6.7 YAML + no-regresión completa (§8.2-8.4) | Suite y goldens verdes |

El paso 2 va **antes** que el 4 a propósito: habilitar `MAYOR` en más alternativas sin arreglar
el substring propaga el mes falso a más preguntas.

---

## 10. Riesgos

| Riesgo | Mitigación |
|---|---|
| Tocar `no_soportado.py` afecta a otros consumidores | §6.5: si aparecen, parar y reportar antes de seguir |
| El plural abre ranking a grano día sin querer | §8.3: deben caer en rechazo honesto; si no, parar |
| `MAS` es palabra muy común | Solo se evalúa dentro de una construcción que ya exige `DIA`, y tras `_RX_EXCLUIR` |
| Ventana de 60 aún corta para frases muy largas | Medido hasta 49 en formas naturales; 65 en una rebuscada. Si aparece, subir con medición, no a ojo |
| `\bMAYO\b` rompe `_periodo_texto` | §6.6: verificar; usa `_MESES`, otra lista |
| Cuarto gemelo en el futuro | §6.5 elimina uno; el YAML no puede importar → test de sincronía sobre el mismo lote de frases |

---

## 11. Qué se descartó de la rev. 1 y por qué

| Propuesta rev. 1 | Veredicto | Evidencia |
|---|---|---|
| «La lógica está en DOS sitios» (§4, «esto gobierna todo el plan») | **Incompleto** | Hay un tercero: `no_soportado.py:92-93`, y es el guardián del ranking |
| Riesgo: «el selector le roba preguntas al ranking» | **Al revés** | El ranking va primero (`respuesta_cuantificar.py:171`) y gana siempre |
| «qué campo produjo más el día 15» como riesgo abierto | **Ya resuelto hoy** | La guarda devuelve `dia` → rechazo honesto |
| `_orden_selector` sobre el texto completo | **Invierte** | «mejor día del **peor** mes» → min. Reinstala el `else "max"` que el plan condena |
| Alternativa `EN QUE DIA … SUBIO\|BAJO\|CAYO` | **Crea una inversión nueva** | `CAYO` entra al regex pero no al léxico → «¿en qué día cayó más?» → max |
| … y secuestra N4 | **No declarado** | `SUBIO`/`BAJO` están en `_VAR_WORDS`; `slots.py:249` da precedencia al día |
| Ventana `.{0,40}` | **Corta** | Gap real 46-49 con entidad y mes intercalados |
| «El `?` evita comerse un cuantificador lejano» | **Falso** | El no-codicioso no cambia el lenguaje aceptado. Cero discrepancias en 2000 frases |
| `PEQUEN[AO]S?`, `GRANDES?` en el léxico | **Léxico muerto / superficie de ataque** | «producción pequeña» no se dice; «grande» califica pozos y campos |
| Sin exclusiones | **3 falsos positivos** | «mantenimiento mayor», «más de 5000 barriles», «bajo el presupuesto» |
| §6.4 YAML como «gemelo» | **5 desincronizaciones** | Le faltaban `ALTA\|BAJA\|MEJOR\|PEOR\|MAXIM\|MINIM` y la 4.ª alternativa |
| Validar con goldens (§8.3) | **Imposible** | Cero casos de día y el runner llama sin `techo` |
| Medir el coste de `menciona_dia` (§8.4) | **Ya respondido** | Delta cero en el corpus real |
| Asertar solo `orden` en los tests | **Pasaría en verde con la respuesta mal** | `mes=5` por el substring de «MAYOR» |
| No contemplaba el substring «MAYO» ⊂ «MAYOR» | **Bug preexistente que amplificaba** | `asumido=[]`: cree que el usuario dijo mayo |

---

## 12. Fuera de alcance

- **El typo del mes.** «Juio» cae al mes del techo sin avisar. Mismo pecado, otra puerta (el
  reconocimiento del nombre, no la dirección). ⚠️ Con este plan se vuelve **más visible**: se
  detectan más selectores, y todos los que traigan un mes mal escrito responderán el del techo.
- **Cobertura sintáctica restante** (§7.1): 18 formas naturales, de las que este plan cubre las
  más frecuentes. Fase B.
- **Ranking a grano día** («los días de mayor producción del año», «top 3 días»). Debe caer en
  rechazo honesto (§8.3); implementarlo es funcionalidad nueva.
- **Dar `techo` al runner de goldens** (§8.4). Mejora del arnés, no de este bug.
