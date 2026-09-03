# plan_TOPN-CONTENEDOR_20260903 — El sustantivo del CONTENEDOR no debe decidir cuántos elementos se rankean

> Plan **v2** auditado (flujo profesional §10 de `CLAUDE.md`). Mapeo + auditoría + diagnóstico
> ejecutados ANTES de escribir esta especificación. **La corrección está verificada contra el
> código real en 8 casos** (§1 H4).
>
> **Cambios de v1 → v2** (segunda pasada contra el código):
> 1. 🔴 **Referencias de línea corregidas.** El `else` a reemplazar está en **`ranking.py:166-169`**,
>    no en `:159-161` (el v1 se desfasó por los comentarios del fix del 3-sep). El `old_string`
>    de §3.1 SÍ era correcto en contenido; solo las citas de línea estaban mal.
> 2. ➕ **Un cuarto caso del bug, descubierto midiendo:** «ranking de **campos** del **activo**
>    castilla» también da `top_n=1` hoy. Añadido a los tests y a la tabla de alcance (H3).
> 3. ✅ **6 casos de control anti-regresión medidos** (no solo los 3 del bug): la corrección
>    los deja todos correctos, incluido «el activo con más producción» → 1 (H4).
>
> **Origen (medido en Pruebas, 2026-09-03):** con el panel scoped ya publicado (`0939de9`), la
> pregunta *«¿Cuáles campos del activo APIAY producen más crudo?»* devolvió **una cifra única
> (APIAY 279.825 bbl)** en vez del panel. La pregunta hermana *«¿Cómo se distribuye… entre los
> campos del activo Castilla?»* **sí funcionó** (panel con 2 campos, 58,9% / 41,1%, total
> 11.433.151 = exactamente la cifra del activo). El panel scoped NO está roto: el problema es
> anterior, en cuántos elementos pide el ranking.

---

## 0. Contexto para el agente EXECUTOR

**Proyecto:** ProdIA — asistente conversacional de producción (Ecopetrol). Este plan toca
**un solo archivo de producción y un bloque de ~6 líneas**.

**Raíz del repo:** `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\`
⚠️ Doble anidamiento: el paquete Python vive en `backend\backend\app\...`.

**Archivo de producción:**
`...\backend\backend\app\features\consulta_v2\cuantificar\ranking.py` — función `detectar()`.

**Archivo de tests:** `...\backend\backend\tests\test_cuantificar_ranking.py`

### Cómo correr los tests

```powershell
cd 'C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend'
.venv\Scripts\python.exe -m pytest tests/test_cuantificar_ranking.py -q
```

Los tests de este plan son **puros** (`detectar()` no toca BD). Corren en local sin problema.

---

## 1. Hallazgos de la auditoría (determinan la §3)

### 🔴 H1 — Causa raíz: el contenedor del scope se cuenta como si fuera lo pedido

`ranking.py:166-169`, dentro de `detectar()`:

```python
    singular = (("CAMPO" in toks and "CAMPOS" not in toks)
                or ("ACTIVO" in toks and "ACTIVOS" not in toks))
    top_n = 1 if singular else 5
```

Medido sobre la pregunta que falló:

```
"Cuales campos del activo APIAY producen mas crudo"
  CAMPOS in toks  : True    -> la 1ª mitad da False  ✅
  ACTIVO in toks  : True    -> la 2ª mitad da True   ❌
  => singular = True  =>  top_n = 1
```

⇒ La palabra **«activo» ahí NO es lo que se pide contar**: es el **contenedor** que acota el
scope. La heurística la lee como si el usuario pidiera *un* activo, y devuelve un ranking de un
solo elemento — que el chat pinta como cifra única, sin panel.

**El `or` es el defecto**: mezcla dos niveles en una sola decisión, sin mirar cuál es el que se
está rankeando.

### 🟠 H2 — Es la MISMA familia del bug de «cada campo» (2026-09-03), por el otro operando

El 3-sep se corrigió esta misma heurística porque *«¿qué participación tiene **cada campo**?»*
daba `top_n=1` (singular gramatical con intención de todos). Aquella corrección añadió:

```python
    elif es_distribucion:
        top_n = 5
```

**No cubre este caso**: «cuáles campos… producen **más**» es un **superlativo**, no una
distribución, así que `es_distribucion` es `False` (medido) y cae en la heurística vieja.

⇒ Mismo defecto, segunda manifestación. Este plan lo ataca en la raíz (qué nivel se rankea) en
vez de añadir una tercera excepción.

### 🔴 H3 — Alcance medido: 3 de 7 formas fallan, y son la forma natural de pedir el panel

| Pregunta | `top_n` hoy | Correcto |
|---|---:|---:|
| «Cuáles **campos** del **activo** APIAY producen más crudo» | **1** ❌ | 5 |
| «Cuáles son los **campos** del **activo** Castilla con mayor producción» | **1** ❌ | 5 |
| «Qué **campos** del **activo** APIAY tienen más crudo» | **1** ❌ | 5 |
| «ranking de **campos** del **activo** castilla» | **1** ❌ | 5 |
| «top 3 campos del activo APIAY» | 3 ✅ | 3 |
| «qué **campo** produce la mayor cantidad de crudo» | 1 ✅ | 1 |
| «cuál es el **activo** que más crudo produce» | 1 ✅ | 1 |
| «cuáles son los 5 campos que más crudo producen» | 5 ✅ | 5 |

⇒ **Las 4 que fallan son exactamente las que combinan nivel plural + contenedor singular**, que
es la forma natural de pedir el panel scoped que se acaba de publicar. El bug hace que la
feature nueva parezca rota en su caso de uso principal.

### 🟢 H4 — La corrección está VERIFICADA en 8 casos antes de escribir este plan

Regla: **manda el nivel que se rankea** (`nivel_ranking`, que `detectar()` ya calculó unas
líneas antes, `ranking.py:139`). Si se rankean campos, solo `CAMPO`/`CAMPOS` deciden el
singular; `ACTIVO` es contenedor y se ignora. Y viceversa.

Probada contra el código real (los 4 del bug + 4 controles anti-regresión):

```
  ok top_n=5 | cuales campos del activo apiay producen mas crudo       <- BUG, ahora 5
  ok top_n=5 | ranking de campos del activo castilla                   <- BUG (nuevo v2), ahora 5
  ok top_n=1 | que campo del activo castilla produce mas crudo         <- CASO FINO: singular real -> 1
  ok top_n=1 | el activo con mas produccion                            <- rankea activos, singular -> 1
  ok top_n=1 | cual es el activo que mas crudo produce                 <- rankea activos, singular -> 1
  ok top_n=5 | los activos con mayor produccion                        <- activos plural -> 5
  ok top_n=1 | que campo produce la mayor cantidad de crudo            <- campo singular real -> 1
  ok top_n=5 | cuales son los 5 campos que mas crudo producen          <- global, sin contenedor
```

**8 de 8**, incluidos los 4 controles anti-regresión. Los casos fino son «qué **campo** del
activo Castilla» y «el **activo** con más producción»: el primero rankea campos y pide uno; el
segundo rankea activos y pide uno. Ambos siguen en 1 — la corrección mira `nivel`, no la
presencia bruta del sustantivo.

### 🟢 H5 — `nivel_ranking` ya está disponible en ese punto de `detectar()`

`ranking.py:139` — `nivel = next((_NIVEL_TOK[k] for k in _NIVEL_TOK if k in toks), None)`, y el
`return` con `top_n` está en `:173`. La variable `nivel` está en scope, ya validada (los
niveles diferidos retornan antes, `:142-143`).

⇒ **No hay que calcular nada nuevo ni reordenar el flujo.** Solo usar lo que ya está.

### 🟢 H6 — El panel scoped NO está roto: la pregunta 1 funcionó y CUADRA

Verificado en Pruebas por el usuario:

```
Panel «campos del activo Castilla»:  CASTILLA 6.738.232 (58,9%) + CASTILLA NORTE 4.694.919 (41,1%)
                                     = 11.433.151
Cifra del activo CASTILLA (N1)     :   11.433.151  ✅ COINCIDE EXACTO
```

⇒ El plan `plan_PANEL-SCOPED-ACTIVO_20260903.md` está bien. **Este plan NO lo toca**: corrige
un defecto anterior en `detectar()` que impide que el panel se active en una de sus formas.

### 🟢 H7 — La otra pregunta «fallida» no es un fallo

*«¿Cuál es la producción del activo Castilla?»* devolvió la tarjeta del activo (11.433.151,
101,2% del PPTO) **sin** panel de campos. Es correcto: esa pregunta es N1 (una cifra de una
entidad), no un ranking. `detectar()` devuelve `None` porque no hay sustantivo de nivel plural
ni superlativo. **Fuera de alcance** — si se quisiera el panel ahí, sería otro plan (§7).

### 🟡 H8 — Un test existente fija el comportamiento singular y debe seguir verde

`tests/test_cuantificar_ranking.py:24-27`:

```python
def test_singular_top1():
    r = RK.detectar("que campo produce la mayor cantidad de crudo")
    assert r is not None
    assert r["top_n"] == 1
```

Y el del 3-sep, `test_superlativo_singular_sigue_dando_top_1`, con la misma frase.

⇒ Ambos siguen verdes con la corrección (H4, casos 5 y 8). **No se tocan.**

---

## 2. Estado actual

`ranking.py`, dentro de `detectar()`:

- `:139` — `nivel = ...` (el nivel que se rankea; ya calculado).
- `:156` — `m = re.search(r"\bTOP\s+(\d+)\b", t) or re.search(r"\b(\d+)\s+(?:CAMPOS?|ACTIVOS?)\b", t)`
- `:157-158` — si hay número explícito, `top_n = max(1, min(20, int(m.group(1))))`.
- `:159-165` — la rama `elif es_distribucion: top_n = 5` (fix del 3-sep).
- `:166-169` — el `else` con la heurística `singular` de H1 (**el bloque a reemplazar**).

Tests: `test_cuantificar_ranking.py`, 43 tests (40 pasan, 3 fallos preexistentes de BD).

---

## 3. Especificación

### 3.1 MODIFICAR la heurística de `singular` en `detectar()`

Sustituir **solo** el bloque `else` final (`ranking.py:159-161`). El `if m:` (número explícito)
y el `elif es_distribucion:` **no se tocan**.

**Texto exacto a reemplazar:**

```python
    else:
        singular = (("CAMPO" in toks and "CAMPOS" not in toks)
                    or ("ACTIVO" in toks and "ACTIVOS" not in toks))
        top_n = 1 if singular else 5
```

**Texto nuevo:**

```python
    else:
        # [2026-09-03] MANDA EL NIVEL QUE SE RANKEA, no cualquier sustantivo de nivel presente.
        # Medido en Pruebas: «¿cuáles CAMPOS del ACTIVO Apiay producen más crudo?» daba top_n=1
        # —el `or` leía el ACTIVO singular como si se pidiera UN activo— y el chat respondía una
        # cifra única en vez del panel. Pero ahí «activo» es el CONTENEDOR del scope, no lo que
        # se cuenta: `nivel` (ya resuelto en :139) dice qué se rankea, y solo ese sustantivo
        # decide el singular. Es la misma familia del bug de «cada campo» (mismo día), por el
        # otro operando del `or`; se corrige en la raíz en vez de añadir otra excepción.
        # 🔑 Sigue dando 1 en el singular REAL: «¿qué campo del activo Castilla produce más?»
        # rankea campos y dice CAMPO en singular -> 1. Verificado en 8 casos.
        if nivel == "activo":
            singular = "ACTIVO" in toks and "ACTIVOS" not in toks
        else:
            singular = "CAMPO" in toks and "CAMPOS" not in toks
        top_n = 1 if singular else 5
```

⚠️ **`nivel` es la variable local de `detectar()`** (`:139`), no `slots["nivel_ranking"]`. En
ese punto ya está resuelta y los niveles diferidos (gerencia/VP/pozo) retornaron antes
(`:142-143`), así que solo puede valer `"campo"` o `"activo"`.

### 3.2 AÑADIR tests en `tests/test_cuantificar_ranking.py`

Sección al final. Todos **puros** (`detectar()` no toca BD).

```python
# --- V-DETECT · el CONTENEDOR no decide el top_n (2026-09-03) -------------------------------

def test_contenedor_singular_no_colapsa_el_ranking():
    """🔴 EL BUG (medido en Pruebas 2026-09-03): «¿cuáles CAMPOS del ACTIVO Apiay producen
    más crudo?» daba top_n=1 y el chat respondía «APIAY 279.825 bbl» —una cifra única— en
    vez del panel de campos. El ACTIVO singular es el CONTENEDOR del scope, no lo que se
    cuenta."""
    r = RK.detectar("cuales campos del activo APIAY producen mas crudo")
    assert r is not None
    assert r["nivel_ranking"] == "campo"
    assert r["top_n"] == 5


def test_contenedor_singular_otras_formas():
    """Las otras formas medidas que fallaban, mismo patrón (incluye «ranking de campos del
    activo», descubierta en la 2ª pasada del plan)."""
    a = RK.detectar("cuales son los campos del activo Castilla con mayor produccion")
    b = RK.detectar("que campos del activo APIAY tienen mas crudo")
    c = RK.detectar("ranking de campos del activo castilla")
    assert a is not None and a["top_n"] == 5
    assert b is not None and b["top_n"] == 5
    assert c is not None and c["top_n"] == 5


def test_ranking_de_activos_plural_da_5():
    """🔒 REGRESIÓN complementaria: activos en plural, sin contenedor -> 5."""
    r = RK.detectar("los activos con mayor produccion")
    assert r is not None and r["nivel_ranking"] == "activo" and r["top_n"] == 5


def test_singular_real_dentro_de_un_activo_sigue_dando_1():
    """🔒 REGRESIÓN, el caso fino: aquí el singular SÍ es real —se pide UN campo dentro de un
    activo— y debe seguir dando 1. Es el guardián de que la corrección no se pasó de ancho."""
    r = RK.detectar("que campo del activo Castilla produce mas crudo")
    assert r is not None and r["nivel_ranking"] == "campo" and r["top_n"] == 1


def test_ranking_de_activos_singular_sigue_dando_1():
    """🔒 REGRESIÓN: cuando lo que se rankea SON activos, el ACTIVO singular sí manda."""
    r = RK.detectar("cual es el activo que mas crudo produce")
    assert r is not None and r["nivel_ranking"] == "activo" and r["top_n"] == 1


def test_top_n_explicito_gana_sobre_el_contenedor():
    """🔒 Un número escrito por el usuario manda sobre toda heurística."""
    r = RK.detectar("top 3 campos del activo APIAY")
    assert r is not None and r["top_n"] == 3
```

---

## 4. Orden de ejecución

| # | Paso | Verificación | Si falla |
|---|---|---|---|
| 0 | Baseline: `pytest tests/ -q` | anotar (esperado **654 pasan, 10 fallan, 2 skip**) | DETENTE |
| 0-bis | Golden **ANTES** (§6.1) | anotar `pct`/`aciertos` (92 / 85 en local) | DETENTE |
| 1 | §3.1 — la heurística | `py_compile` OK | revisar sintaxis |
| 2 | `pytest tests/test_cuantificar_ranking.py -q` | **sin fallos nuevos** (siguen los 3 de BD) | ⚠️ ver nota |
| 3 | §3.2 — los 5 tests nuevos | los 5 pasan | ajustar al `detectar()` real |
| 4 | Suite completa | **exactamente 10 fallos**, ninguno nuevo | comparar con paso 0 |
| 5 | Golden **DESPUÉS** | **sin cambio** respecto al 0-bis | si baja: revertir |

⚠️ **Cómo leer un fallo nuevo en el paso 2.** Los candidatos son `test_singular_top1` (`:24`) y
`test_superlativo_singular_sigue_dando_top_1`: ambos fijan que «qué campo produce la mayor
cantidad» dé 1. Si alguno cae, **la corrección se pasó de ancho** — revisar que la rama
`nivel == "campo"` siga mirando `CAMPO`/`CAMPOS`. **NUNCA tocar el test.**

---

## 5. Reglas no negociables

1. **NO tocar el `if m:`** (número explícito) ni el `elif es_distribucion:` (fix del 3-sep):
   solo se reemplaza el `else` final.
2. **NO tocar ningún test existente.** Si uno cae, el que está mal es el código.
3. **NO tocar el panel scoped** (`campos_de_activo`, `campos_scope`, la guarda (3)): está
   verificado y cuadra (H6). Este plan es anterior en el flujo.
4. **NO tocar `_DISTRIBUCION`, `_SUPERLATIVO`, `_BOTTOM_TOK`** ni el gate de `detectar()`.
5. **NO tocar `nivel` ni el orden de resolución**: la variable ya existe donde hace falta (H5).
6. **NO convertir esto en un caso especial más**: la corrección va en la raíz (qué nivel se
   rankea), no como una tercera excepción encadenada.
7. `top_n` sigue acotado a `[1, 20]` cuando el usuario escribe un número.

---

## 6. Validación

### 6.1 Estática (executor)

```powershell
cd 'C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend'
.venv\Scripts\python.exe -m py_compile app\features\consulta_v2\cuantificar\ranking.py
.venv\Scripts\python.exe -m pytest tests/test_cuantificar_ranking.py -q
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\python.exe -c "from app.features.consulta_v2.golden.run_golden import ejecutar; r=ejecutar(); print('pct:', r['pct'], '· aciertos:', r['aciertos'])"
```

Comprobación directa (pura, sin BD) — **la que zanja el plan**:

```powershell
.venv\Scripts\python.exe -c "import app.features.consulta_v2.cuantificar.ranking as RK; [print(RK.detectar(q)['top_n'], '|', q) for q in ['cuales campos del activo APIAY producen mas crudo','que campo del activo Castilla produce mas crudo','cual es el activo que mas crudo produce']]"
```

Esperado, en este orden: **`5`**, **`1`**, **`1`**.

### 6.2 Humana (usuario) — en PRUEBAS

Tras `git pull` + **reiniciar INGESTA**:

| # | Pregunta | Esperado |
|---|---|---|
| 1 | **¿Cuáles campos del activo APIAY producen más crudo?** | **Panel con los campos de APIAY** (era una cifra única — el bug) |
| 2 | ¿Cómo se distribuye la producción de crudo entre los campos del activo Castilla? | Sigue igual: panel con CASTILLA y CASTILLA NORTE ← regresión |
| 3 | ¿Qué campo del activo Castilla produce más crudo? | **UNA sola entidad** (singular real) ← regresión clave |
| 4 | ¿Cuál es el activo que más crudo produce? | UNA sola entidad |
| 5 | ¿Cuáles son los 5 campos que más crudo producen? | Ranking global de 5 ← regresión |
| 6 | ¿Cuál es la producción del activo Castilla? | Tarjeta del activo, 11.433.151 bbl, sin panel de campos (H7) |

🔑 **La que zanja el plan:** la #1 debe pasar de una cifra a un panel. Y la #3 es su
contrapeso: si también se convierte en panel, la corrección se pasó de ancho.

**El único que marca ✅ es el usuario.**

### 6.3 Medición de valor

Binaria: hoy la pregunta #1 devuelve una cifra única; después, el panel. No necesita
`clasificacion_log`.

### 6.4 Despliegue

Backend solamente → commit a GitHub `main` → `git pull` en Pruebas → **reiniciar INGESTA** →
validar §6.2 → `migrar-a-azure` (3 tiempos, default `prodiav2`) → en el 139: `git pull` +
reiniciar INGESTA. Flask no necesita reinicio.

---

## 7. Fuera de alcance

- **Panel de campos en la pregunta N1** («¿cuál es la producción del activo Castilla?»): hoy
  devuelve la tarjeta del activo sin desglose (H7). Ofrecerlo ahí es una decisión de producto,
  no un bug — merece su propio plan si se quiere.
- **El panel scoped en sí** (`plan_PANEL-SCOPED-ACTIVO_20260903.md`): verificado y cuadrando.
- **Entidad ambigua en pregunta de ranking**: observación abierta del plan anterior (ya no
  declina explícito, cae al global). Sin decidir.
- **Gerencia y VP como contenedor** («los campos de la gerencia PPC»): declinan por
  `_NIVEL_DIFERIDO` y dependen del bug 1 de `jerarquias_sup_error.md`.
- Cualquier cambio en el cálculo, el SQL, el panel o el frontend.
