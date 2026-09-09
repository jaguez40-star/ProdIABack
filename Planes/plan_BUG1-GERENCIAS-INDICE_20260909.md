# plan_BUG1-GERENCIAS-INDICE_20260909 — Que las gerencias reales se puedan cuantificar

> **Versión v3 — auditada y SIMULADA end-to-end** (flujo profesional §10 de `CLAUDE.md`).
> Cada cambio de §3 se aplicó en memoria sobre el código real y se midió contra la BD local y
> contra `robustez_v02` el 2026-09-09. Ninguna cifra de este plan es razonada: todas están medidas.
>
> **Es el bug 1 de `jerarquias_sup_error.md`**, el segundo del orden acordado 2 → 1 → 3. El bug 2
> (nivel explícito) ya está cerrado (`plan_BUG2-NIVEL-EXPLICITO_20260903.md`) y era su prerrequisito.
>
> **🔴 REGLA QUE GOBIERNA ESTE PLAN — decisión del usuario, 2026-09-09:**
> **La ÚNICA fuente de verdad de jerarquías es `robustez_v02`, esquema `ops`, tabla
> `wells_attributes`** (`vice_presidency > management > active > field > zone`).
> `core.map_campo_robustez` (CSV) y `core.dim_fuente` son **copias** y **no mandan**.
>
> **🎯 OBJETIVO, medido contra la fuente de verdad el 2026-09-09** (no la cifra del hallazgo, que
> se midió contra la copia):
>
> ```
> Gerencias VIGENTES en robustez_v02 (con los 2 filtros) : 20
>   resuelven HOY : 4    CPV · GAN · GNS · GXO          (las que están en dim_fuente)
>   NO resuelven  : 16   CPI · CUF · CUP · PCI · PCN · PCS · PDB · PDH · POE ·
>                        PPA · PPC · PPH · PPÑ · PPU · PTN · PUC
> ```
>
> **El plan debe llevar esas 16 de `None` a una cifra correcta, sin tocar las 4 que ya funcionan.**
> El «20 de 24» de `jerarquias_sup_error.md` contaba sobre la copia, que incluye 6 códigos de la
> jerarquía vieja y omite 2 vigentes (H4).

### Qué cambió respecto a v1/v2 (trazabilidad, una línea cada uno)

| Versión | Proponía | Por qué se descartó |
|---|---|---|
| v1 | Nivel nuevo `gerencia_rob` | Rótulo vacío al usuario (`_NIVEL_TEXTO.get→''`) y `gerencia_rob` crudo en el navegador (`multitab_shell.js:1555`) |
| v2 | Reusar `"gerencia"`, leyendo la copia `core.map_campo_robustez` | La copia **diverge** de la fuente de verdad en 8 códigos y pierde un campo de PPC (H4) |
| v2 | Regenerar el CSV con `build_map_campo_robustez.py` en local | **Empeora el CSV** (134 filas en vez de 139): cruza con la BD local congelada. Probado y revertido |
| **v3** | **Reusar `"gerencia"`, leyendo `ops.wells_attributes` con los 2 filtros oficiales** | Simulado end-to-end: PPC = Σ campos al centésimo (H14) |

---

## 0. Contexto para el agente EXECUTOR

**Proyecto:** ProdIA — asistente conversacional de producción (Ecopetrol). **Solo backend.** Cero
cambios de frontend, JS o CSS.

**Raíz del repo:** `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\`
⚠️ **Doble anidamiento**: el paquete Python vive en `backend\backend\app\...`. Todas las rutas de
este plan son absolutas.

**Archivos de producción a modificar (4):**

| # | Ruta absoluta |
|---|---|
| A | `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\cuantificar\resolver.py` |
| B | `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\analisis\api.py` |
| C | `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\respuesta_cuantificar.py` |
| D | `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\maquina_q.py` |

**Tests y golden (3):**

| # | Ruta absoluta | Acción |
|---|---|---|
| E | `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\tests\test_gerencia_robustez.py` | **CREAR** |
| F | `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\golden\cuantificar_golden.yaml` | MODIFICAR |
| G | `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\golden\run_golden_cuantificar.py` | MODIFICAR |

### Cómo correr las cosas

Todo desde `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend`, **PowerShell normal, sin
consola de administrador, línea por línea**. Si un bloque deja `>>`, pulsar **Enter**.

```powershell
cd 'C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend'
.venv\Scripts\python.exe -m pytest tests/test_gerencia_robustez.py -q
```

⚠️ **El golden de Cuantificar NO se corre en local** (`run_golden_cuantificar.py:9-11`, regla de
RAM). Va en Pruebas (§6.2).

### Estado de la BD local — medido el 2026-09-09

- **Esta máquina SÍ alcanza `robustez_v02`** (`OPS_DATABASE_URL` configurada). Por eso V6-V8 de
  §6.1 pueden verificar el arreglo con datos reales en local.
- La BD principal está **congelada en 2026-05-18**: el último mes con cifras es **mayo 2026**.
  Cualquier prueba con cifra usa `periodo="mayo 2026"`; septiembre da 0,0 con 1/30 días.
- `core.map_campo_robustez` tiene 139 filas (se cargó hoy para diagnosticar). **Este plan ya no la
  lee**; es indiferente que esté cargada o vacía.

### Convenciones que este plan respeta

- Español en comentarios y en todo texto de cara al usuario.
- Los `except Exception:` de BD **degradan y nunca lanzan**; los errores **no se cachean**.
- Aditivo: lo que hoy funciona sigue funcionando byte a byte.
- Los dos filtros de `ranking.py:277-279` sobre `ops.wells_attributes` son **obligatorios**.

---

## 1. Hallazgos de la auditoría (determinan la §3)

### 🔴 H1 — El resolutor lee el catálogo más pobre y NO mira la fuente de verdad

`resolver.py:26`, en `_LEVELS`:

```python
("gerencia", "SELECT DISTINCT gerencia FROM core.dim_fuente WHERE NULLIF(TRIM(gerencia),'') IS NOT NULL", "A"),
```

`core.dim_fuente.gerencia` tiene **13 valores** que son, en la jerarquía oficial, vicepresidencias
mal-nombradas (level-shift S28). **Verificado ejecutando el código real el 2026-09-09:**

```
PPC → None   PPH → None   POE → None   PUC → None   PPA → None   PCN → None
GOR → ('gerencia','GOR')                                          ← solo las de dim_fuente
```

Y la contradicción del hallazgo, medida en el mismo instante: el **clasificador** detecta `PPC`,
el **panel jerárquico** conoce `('gerencia','PPC')` con sus campos, y el **resolutor** devuelve
`None`. Dos de tres componentes lo reconocen. El usuario lee *«No reconocí «PPC» en el catálogo»*.

### 🔴 H2 — Cuantificar NO escribe SQL: el filtro por nivel vive en `analisis/api.py`

`ejecutor.py:11`: *«Frontera: NO SQL propio, NO LLM»*. Todo pasa por `desempeno(entidad, nivel)`
(`ejecutor.py:60,117,376,427,435,500`; `niveles.py:27,47,109,170,220,232`). La traducción está en
`_ambito`, `api.py:412-414`:

```python
        elif col:                                   # nivel específico → columna exacta (D-C2)
            ids = [r[0] for r in c.execute(sa.text(
                f"SELECT fuente_id FROM core.dim_fuente WHERE UPPER(TRIM({col}))=:e"), {"e": E})]
```

Meter gerencias en el índice sin tocar esto cambiaría *«no reconocí PPC»* por *«no tengo datos de
PPC»*. Por eso se tocan resolutor **y** `_ambito`.

### 🟢 H3 — El precedente exacto existe: así se resolvió `activo`

`api.py:363-366` documenta que `activo` tampoco es columna de `dim_fuente` y se compone desde un
catálogo (`fuentes_de_activo`), aplicado en `api.py:410-411`. Gerencia admite la misma solución.

### 🔴 H4 — 🔑 La copia DIVERGE de la fuente de verdad (medido)

Aplicando los dos filtros oficiales de `ranking.py:277-279`:

```
ops.wells_attributes (filtrado)   : 20 gerencias vigentes
core.map_campo_robustez / CSV     : 24
SOBRAN en la copia : ANDINA · CATENARE · DE MARES · DEL RIO · PIEDEMONTE · PUTUMAYO  (rama VIEJA V*)
FALTAN en la copia : CPI · GNS                                                       (vigentes)
```

**Causa:** `build_map_campo_robustez.py` es del **2026-08-02** y no aplica los filtros que
`ranking.py:268-273` declaró obligatorios el **2026-09-03** — son posteriores al script. En
`robustez_v02` conviven **dos jerarquías** sobre los mismos campos (LA CIRA: `PCI`/GCT con 1.943
pozos frente a `LA CIRA INFANTAS`/VRC con 1.199); la rama `V*` es la vieja.

Además, **la copia pierde un campo de PPC**: la fuente da `CASTILLA, CASTILLA ESTE, CASTILLA
NORTE`; el CSV solo dos.

### 🔴 H5 — El argumento de «portabilidad» para leer la copia está descartado

La v2 no quería depender de `OPS_DATABASE_URL` (se pierde en despliegues, `BITACORA.md:502,667`).
**Pero el motor ya depende de `ops` en runtime desde 7 módulos**, dos de ellos del propio
Cuantificar: `cuantificar\ranking.py`, `respuesta_cuantificar.py` (más `respuesta_jerarquizar.py`,
`pozos_geo.py`, `analizar\p50_referencia.py`, `ebitda\api.py`). Este plan no añade una dependencia
nueva. Donde `ops` no esté (el 139), las gerencias **no resuelven** — el comportamiento de hoy, sin
regresión y declarado.

### 🟢 H6 — Con la fuente de verdad, las colisiones gerencia↔campo/activo DESAPARECEN

Medido con las 20 vigentes contra `dim_fuente.campo` y `map_campo_activo`:

```
gerencia ∩ campo  : []      gerencia ∩ activo : []
gerencia ∩ dim_fuente.gerencia : CPV · GAN · GNS · GXO   (mismo código en ambos; tienen fuentes propias)
```

`ANDINA` y `PIEDEMONTE` —las colisiones estelares de v1/v2— eran de la rama vieja. Los 4 códigos
compartidos se resuelven por **precedencia** (§3.2.a) sin cambio de conducta.

### 🔴 H7 — `clave_fisica` colapsa una colisión y DESACTIVA el nivel explícito

`resolver.py:127-130`: para `gerencia`, busca fuentes en `dim_fuente.gerencia`. Una gerencia de la
fuente de verdad no está ahí → `frozenset()`. Un campo homónimo de un tercero → también
`frozenset()`. **Misma clave `('F', frozenset())` → 1 grupo → modo `"auto"`** → gana Campo por
`_PRIORIDAD`, y **el bloque de nivel explícito (`:265-271`) solo corre en modo `"ask"`**: nunca se
ejecutaría. Hoy no hay colisión real (H6), pero la política debe quedar correcta: §3.1.d.

### 🔴 H8 — El detector de nivel explícito no conoce «gerencia»

`resolver.py:217-220` solo tiene ACTIVO y CAMPO. Sin GERENCIA, el usuario no puede desambiguar
un código presente en dos niveles.

### 🔴 H9 — Bug latente que este plan activaría: `puente` leído como dict

`respuesta_cuantificar.py:151-152`:

```python
    if nivel == "gerencia":
        vice = (resuelta.get("puente") or {}).get("vp") or None
```

`resolver.py:201` escribe `puente = True` (booleano). `(True or {})` es `True` → **reproducido:**
`AttributeError: 'bool' object has no attribute 'get'`. Ruta: `respuesta_cuantificar.py:641` →
`_p50_del_mes`. Latente porque casi ninguna gerencia llegaba ahí. §3.3.

### 🔴 H10 — `_campos_sin_meta` ocultaría el aviso de PPTO faltante

`api.py:469`: `if nivel != "activo": return []`. Su docstring: *«el único que agrega varios
campos»*. Con gerencias deja de ser cierto (PPH agrega 20). **Simulado con la extensión de §3.2.b:
PPH (mayo 2026) devuelve `ARRAYAN (GAS)` sin meta** — el aviso que se perdería en silencio.

### 🔴 H11 — El CLASIFICADOR sigue leyendo la copia (incoherencia de pipeline, NUEVA en v3)

`maquina_q.py:513-515` (`_QUERIES_CATALOGO`) carga `rob_gerencia` de `core.map_campo_robustez`.
Con el resolutor en la fuente de verdad quedarían **dos catálogos distintos en la misma ruta**.
**Medido:** `detectar_entidad("cuanto produjo la gerencia CPI") → None` (la copia no trae CPI); la
pregunta solo se salva por el backstop de n-gramas de `respuesta_cuantificar.py:523`. §3.4 alinea
el clasificador con la misma función `gerencias_vigentes()`, así hay **un** catálogo.

### 🔴 H12 — El golden no protege esta regresión y su runner es ciego al contexto

`cuantificar_golden.yaml` tiene 24 casos y **uno** de gerencia (`:30`, GOR — que ya funcionaba).
`run_golden_cuantificar.py:51` llama `resolver_unico(...)` **sin `contexto`**: el nivel explícito
no se ejercita en el arnés. §3.6 y §3.7.

### 🔴 H13 — Requisitos de los tests (aprendidos auditando los de v1)

1. Con **una sola identidad**, `resolver_unico` retorna en `:260` y **nunca** llama a
   `_resolver_colision`: los tests de colisión necesitan ≥2 identidades.
2. `_cargar_vp_robustez()` **cachea `set()`** y contamina los tests siguientes → monkeypatch
   obligatorio (patrón `test_puente_gerencia_vp.py:12`).
3. `norm("PPÑ") == "PPN"` (NFKD pliega la ñ): las claves del índice van normalizadas y el valor
   guarda el nombre canónico.
4. El import de `get_ops_engine` es **diferido** (dentro de la función) → se monkeypatchea
   `app.core.db.get_ops_engine`. **Verificado**: el parche surte efecto y el `except` lo captura.

### 🟢 H14 — 🔑 SIMULACIÓN END-TO-END: LAS 20 DE 20, CON CIFRA (la evidencia principal)

Se aplicaron en memoria §3.1 + §3.2 sobre el código real y se recorrieron **las 20 gerencias
vigentes**, resolviendo y pidiendo la cifra de crudo de mayo 2026:

```
CPV  2,83   CUF 14,06   CUP  5,02   GAN 18,22   GNS 35,61   GXO  0,14   PCI 13,38
PCN 18,08   PCS 15,58   PDB  1,15   PDH 55,28   POE 99,86   PPA 10,49   PPC 93,71
PPH 16,55   PPU  6,59   PPÑ 49,80   PTN 14,05   PUC 26,72          (kbopd)

resuelven: 20/20        con dato: 20/20
NO-REGRESIÓN: ANDINA → campo · CASTILLA → campo · GOR → puente=True
```

**El objetivo se cumple al 100%**: las 16 que hoy dan `None` pasan a dar una cifra, y las 4 que ya
funcionaban no cambian. Detalle de la ruta completa:

```
resolver_unico:  PPC→gerencia  CPI→gerencia  GNS→gerencia  GAN→gerencia  PPÑ→gerencia (canónico)
                 GOR→gerencia+puente (INTACTO)   ANDINA→campo (INTACTO)
                 «la gerencia GAN» → gerencia (nivel explícito operativo)

desempeno(PPC, gerencia, "mayo 2026"):  encontrada=True  real=93,71  ppto=89,46 kbopd
   CASTILLA        54,46 / 53,87
   CASTILLA NORTE  39,25 / 35,59
   CASTILLA ESTE   (no está en INGESTA → 0)
   SUMA            93,71 / 89,46   ← COINCIDE AL CENTÉSIMO

respuesta_cuantificar.responder("cuanto produjo PPC", entidad="PPC"):
   «la Gerencia PPC produjo … »                       ← rótulo correcto, sin tocar el frontend
responder("cuanto produjo GOR", entidad="GOR"):
   «la Vicepresidencia GOR produjo … »                ← no-regresión del puente
```

### 🟢 H15 — Verificado y NO es problema

- `= ANY(:cs)` con lista Python y psycopg3: precedentes en `pozos_geo.py:41,48,54`,
  `respuesta_jerarquizar.py:221,354`; probado contra la BD.
- Ciclo de imports: `resolver.py` importa solo `re`, `sqlalchemy`, `get_engine`, `norm`. `maquina_q`
  ya importa `respuesta_cuantificar` → `resolver`: importar `resolver` en `maquina_q` es seguro.
- `ranking.py:306` usa `nivel_ranking` (no el de entidad). `diferidas.py:39` declina gerencias y es
  correcto. `_PRIORIDAD` ya tiene `"gerencia": 2`. `_NIVEL_TEXTO` ya tiene `"gerencia"`.
  `_NIVEL_COL_AMB` ya tiene `"gerencia"`. **Ninguno se toca.**
- **Reintentos contra `ops` caído:** `_GER_CAMPOS` se puebla en `build_index()` (una vez por
  proceso). Si esa carga falla, **ninguna gerencia de la fuente entra al índice**, y las de
  `dim_fuente` tienen `ids` propios → la rama de composición de `_ambito` **nunca se alcanza** → no
  hay reintentos por pregunta.

---

## 2. Estado actual → estado tras el plan

```
HOY     «¿cuánto produjo PPC?» → detectar_entidad="PPC" → resolver_unico → None
        → «No identifiqué una entidad… No reconocí «PPC» en el catálogo.»

DESPUÉS «¿cuánto produjo PPC?» → resolver_unico → {"nivel":"gerencia","valor":"PPC"}
        → desempeno(PPC, gerencia) → _ambito: dim_fuente.gerencia=PPC → nada
                                              → campos_de_gerencia("PPC") [ops] → 3 campos → fuente_id
        → «la Gerencia PPC produjo 93,71 kbopd …»   (= CASTILLA + CASTILLA NORTE)
```

---

## 3. Especificación

### 3.1 — MODIFICAR archivo A: `resolver.py`

#### 3.1.a Comentario en `_LEVELS` (documenta dónde entran las gerencias reales)

**LOCALIZAR** (`resolver.py:26`):

```python
    ("gerencia",        "SELECT DISTINCT gerencia FROM core.dim_fuente          WHERE NULLIF(TRIM(gerencia),'') IS NOT NULL", "A"),
```

**REEMPLAZAR POR** (la línea se conserva; se añade el comentario debajo):

```python
    ("gerencia",        "SELECT DISTINCT gerencia FROM core.dim_fuente          WHERE NULLIF(TRIM(gerencia),'') IS NOT NULL", "A"),
    # [2026-09-09 · BUG1-GERENCIAS] Las gerencias REALES NO salen de aquí: `dim_fuente.gerencia`
    # tiene 13 valores que son vicepresidencias mal-nombradas (level-shift S28). Vienen de la FUENTE
    # ÚNICA DE VERDAD (robustez_v02.ops.wells_attributes), que vive en OTRA BD y no se puede
    # JOIN-ear con core.* — se añaden al índice APARTE, en build_index(), con `gerencias_vigentes()`.
    # Mismo nivel "gerencia": el frontend ya lo rotula y los 4 consumidores de `puente` no cambian.
```

#### 3.1.b `build_index` tolerante + gerencias desde la fuente de verdad

**LOCALIZAR** (`resolver.py:35-47`, la función completa):

```python
def build_index():
    global _INDEX
    idx = {}
    eng = get_engine()
    with eng.connect() as c:
        for nivel, sql, rama in _LEVELS:
            for (val,) in c.execute(sa.text(sql)):
                k = norm(val)
                if not k:
                    continue
                idx.setdefault(k, []).append({"nivel": nivel, "rama": rama, "valor": (val or "").strip()})
    _INDEX = idx
    return idx
```

**REEMPLAZAR POR:**

```python
def build_index():
    global _INDEX
    idx = {}
    eng = get_engine()
    # [2026-09-09 · BUG1-GERENCIAS] AUTOCOMMIT + try por consulta: una tabla ausente NO tumba el
    # índice entero (mismo patrón que maquina_q._nombres():519-545).
    with eng.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
        for nivel, sql, rama in _LEVELS:
            try:
                filas = list(c.execute(sa.text(sql)))
            except Exception:
                continue
            for (val,) in filas:
                k = norm(val)
                if not k:
                    continue
                ident = {"nivel": nivel, "rama": rama, "valor": (val or "").strip()}
                if ident not in idx.setdefault(k, []):   # idempotente: no duplicar identidades
                    idx[k].append(ident)
    # [2026-09-09 · BUG1-GERENCIAS] Gerencias REALES desde la FUENTE ÚNICA DE VERDAD. Van APARTE
    # del bucle porque viven en OTRA BD (robustez_v02) — mismo motivo y patrón que ranking.py:266.
    # Medido: 20 vigentes, todas con campos en INGESTA. Si ops no está, `gerencias_vigentes()`
    # devuelve [] y el índice queda como hoy.
    # 🔑 Mismo nivel "gerencia": un código presente en los dos catálogos (CPV/GAN/GNS/GXO) produce
    #    la MISMA identidad y el `if ident not in` la deduplica. No hay ambigüedad.
    for g in gerencias_vigentes():
        k = norm(g)
        if not k:
            continue
        ident = {"nivel": "gerencia", "rama": "A", "valor": g}
        if ident not in idx.setdefault(k, []):
            idx[k].append(ident)
    _INDEX = idx
    return idx
```

#### 3.1.c «gerencia» en el detector de nivel explícito

**LOCALIZAR** (`resolver.py:217-220`):

```python
_NIVEL_EXPLICITO_RX = (
    (re.compile(r"\b(?:EL|LA|LOS|LAS)?\s*ACTIVOS?\s+", re.I), "activo"),
    (re.compile(r"\b(?:EL|LA|LOS|LAS)?\s*CAMPOS?\s+", re.I), "campo"),
)
```

**REEMPLAZAR POR:**

```python
# [2026-09-09 · BUG1-GERENCIAS] Se añade GERENCIA con la MISMA adyacencia (nivel + nombre) del
# diseño del 2026-09-03: sin ella, «¿cuántas gerencias tiene la VP GOR?» (JERARQUIZAR) se
# etiquetaría por error. El orden se conserva: ACTIVO primero; `_nivel_explicito` devuelve en el
# primer match.
_NIVEL_EXPLICITO_RX = (
    (re.compile(r"\b(?:EL|LA|LOS|LAS)?\s*ACTIVOS?\s+", re.I), "activo"),
    (re.compile(r"\b(?:EL|LA|LOS|LAS)?\s*CAMPOS?\s+", re.I), "campo"),
    (re.compile(r"\b(?:EL|LA|LOS|LAS)?\s*GERENCIAS?\s+", re.I), "gerencia"),
)
```

#### 3.1.d `clave_fisica`: una gerencia sin fuentes propias no colapsa con un homónimo (H7)

**LOCALIZAR** (`resolver.py:127-130`, final de `clave_fisica`):

```python
    col = _FUENTE_COL.get(nivel)
    if not col:
        return (nivel, k)
    return ("F", _get_fuente_sets()[col].get(k, frozenset()))
```

**REEMPLAZAR POR:**

```python
    col = _FUENTE_COL.get(nivel)
    if not col:
        return (nivel, k)
    fset = _get_fuente_sets()[col].get(k, frozenset())
    # [2026-09-09 · BUG1-GERENCIAS] Una gerencia de la FUENTE DE VERDAD no está en dim_fuente →
    # conjunto físico VACÍO. Un campo homónimo de un tercero también → ambos caían en la misma
    # clave ('F', frozenset()), `_resolver_colision` veía UN grupo y devolvía "auto" ganando Campo.
    # El bloque de NIVEL EXPLÍCITO (resolver_unico, modo "ask") nunca se ejecutaba. Con clave
    # propia son 2 grupos → "ask" → el nivel explícito decide. Hoy no hay colisión real (medido),
    # pero la política queda correcta. GOR y las de dim_fuente conservan su ('F', {ids}).
    if nivel == "gerencia" and not fset:
        return ("GER_ROB", k)
    return ("F", fset)
```

#### 3.1.e Gerencias y composición desde la FUENTE ÚNICA DE VERDAD

**LOCALIZAR** (`resolver.py:192-193`, las dos líneas finales de `_cargar_vp_robustez`):

```python
    _VP_ROBUSTEZ = {norm(v) for v in (vps - gers) if v}   # excluye ambiguos (CPV/GAN/GXO hoy)
    return _VP_ROBUSTEZ
```

**REEMPLAZAR POR** (se conservan ambas líneas; se AÑADE lo que sigue):

```python
    _VP_ROBUSTEZ = {norm(v) for v in (vps - gers) if v}   # excluye ambiguos (CPV/GAN/GXO hoy)
    return _VP_ROBUSTEZ


# --- GERENCIAS REALES desde la FUENTE ÚNICA DE VERDAD (BUG1-GERENCIAS, 2026-09-09) ------------
# 🔴 FUENTE: robustez_v02, esquema ops, tabla wells_attributes. NO `core.map_campo_robustez`
#    (COPIA que diverge: le sobran 6 de la rama vieja V*, le faltan CPI y GNS, y pierde
#    CASTILLA ESTE en PPC — medido el 2026-09-09).
# ⚠️ LOS DOS FILTROS SON OBLIGATORIOS, copiados de ranking.py:277-279 (medidos el 2026-09-03):
#      1. `vice_presidency NOT LIKE 'V%'` — conviven DOS jerarquías; la rama V* es la VIEJA.
#      2. `vice_presidency <> '0'`        — filas basura que duplican campos.
#    Con ellos: 20 gerencias vigentes, las 20 con campos en INGESTA.
# 🔑 Vive en OTRA BD (get_ops_engine): se lee aparte y se cruza en Python (ranking.py:264-267).
# 🔑 Degradación con gracia: sin ops (p.ej. el 139) devuelve vacío y las gerencias no resuelven —
#    el comportamiento de HOY. Nunca lanza. Los errores NO se cachean; un resultado legítimo SÍ.
_GER_CAMPOS = None   # cache por proceso: {norm(gerencia): [campo, ...]}
_GER_CANON = None    # cache por proceso: {norm(gerencia): nombre canónico}  (norm pliega la ñ:
                     # PPÑ -> PPN, y el usuario debe leer «PPÑ», no «PPN»)

_SQL_GER_CAMPOS = """
    SELECT TRIM(management) AS ger, TRIM(field) AS campo
    FROM ops.wells_attributes
    WHERE NULLIF(TRIM(management),'') IS NOT NULL
      AND NULLIF(TRIM(field),'') IS NOT NULL
      AND vice_presidency NOT LIKE 'V%'
      AND vice_presidency <> '0'
    GROUP BY 1, 2
"""


def _cargar_ger_campos():
    global _GER_CAMPOS, _GER_CANON
    if _GER_CAMPOS is not None:
        return _GER_CAMPOS
    try:
        from app.core.db import get_ops_engine
        with get_ops_engine().connect() as c:
            filas = c.execute(sa.text(_SQL_GER_CAMPOS)).all()
    except Exception:
        return {}   # ops no disponible → sin cachear: el fallo puede ser transitorio
    d, canon = {}, {}
    for ger, campo in filas:
        k = norm(ger)
        d.setdefault(k, []).append((campo or "").strip())
        canon.setdefault(k, (ger or "").strip())   # el nombre TAL COMO lo escribe la fuente
    _GER_CAMPOS = {k: sorted(set(v)) for k, v in d.items()}
    _GER_CANON = canon
    return _GER_CAMPOS


def gerencias_vigentes() -> list[str]:
    """Nombres CANÓNICOS de las gerencias vigentes en la fuente de verdad. [] si ops no está.

    Lo consumen `build_index()` y `maquina_q._nombres()` — UN solo catálogo para el motor.
    """
    _cargar_ger_campos()
    return sorted((_GER_CANON or {}).values())


def campos_de_gerencia(gerencia: str) -> list[str]:
    """Campos que componen una GERENCIA REAL, según ops.wells_attributes. [] si no existe.

    Fuente única de la composición: la usa también `analisis._ambito`, para que el tablero y la
    conversación no puedan divergir (mismo criterio que `fuentes_de_activo`).
    """
    return list(_cargar_ger_campos().get(norm(gerencia or ""), []))
```

⚠️ `gerencias_vigentes` se usa en `build_index` (§3.1.b) y queda definida más abajo en el módulo:
en Python es válido porque se resuelve en tiempo de llamada, no de definición.

### 3.2 — MODIFICAR archivo B: `analisis/api.py`

#### 3.2.a Precedencia en `_ambito`: `dim_fuente` primero, composición después

**LOCALIZAR** (`api.py:412-414`):

```python
        elif col:                                   # nivel específico → columna exacta (D-C2)
            ids = [r[0] for r in c.execute(sa.text(
                f"SELECT fuente_id FROM core.dim_fuente WHERE UPPER(TRIM({col}))=:e"), {"e": E})]
```

**REEMPLAZAR POR:**

```python
        elif col:                                   # nivel específico → columna exacta (D-C2)
            ids = [r[0] for r in c.execute(sa.text(
                f"SELECT fuente_id FROM core.dim_fuente WHERE UPPER(TRIM({col}))=:e"), {"e": E})]
            # [2026-09-09 · BUG1-GERENCIAS] Gerencia REAL, desde la FUENTE ÚNICA DE VERDAD
            # (robustez_v02.ops.wells_attributes). `dim_fuente.gerencia` tiene 13 valores que son
            # vicepresidencias mal-nombradas; 16 de las 20 gerencias vigentes NO están ahí (las 4
            # que sí —CPV/GAN/GNS/GXO— resuelven por la columna y no llegan a esta rama).
            # 🔑 PRECEDENCIA, no reemplazo: solo se compone si la columna NO dio nada. Las 4 que ya
            #    funcionaban (GOR, GAA…) y los 4 códigos presentes en ambos catálogos (CPV/GAN/GNS/
            #    GXO) siguen byte a byte por la columna.
            # 🔑 Mismo patrón que 'activo' (:410-411). Verificado: PPC (mayo 2026) = 93,71 kbopd =
            #    CASTILLA 54,46 + CASTILLA NORTE 39,25 (CASTILLA ESTE no está en INGESTA → 0).
            if not ids and nv == "gerencia":
                from app.features.consulta_v2.cuantificar.resolver import campos_de_gerencia
                campos = campos_de_gerencia(E)
                if campos:
                    ids = [r[0] for r in c.execute(sa.text(
                        "SELECT fuente_id FROM core.dim_fuente "
                        "WHERE UPPER(TRIM(campo)) = ANY(:cs)"),
                        {"cs": [x.upper() for x in campos]})]
```

⚠️ El import va **dentro** de la rama a propósito: `analisis.api` es importado *por* `consulta_v2`
(`ejecutor.py:12`, `niveles.py:9`); a nivel de módulo crearía un ciclo. Criterio de `api.py:105`.

#### 3.2.b `_campos_sin_meta` también para gerencias (H10)

**LOCALIZAR** (`api.py:462-471`):

```python
def _campos_sin_meta(c, entidad, fin, nivel):
    """Campos de un ACTIVO que PRODUCEN pero no tienen PPTO en el mes (por producto).

    Solo aplica al nivel 'activo': es el único que agrega varios campos, y por tanto el único
    donde el REAL sumado puede quedar comparado contra un PPTO que no cubre a todos.
    Devuelve [] para cualquier otro nivel. Nunca inventa presupuesto (ver D-A4).
    """
    if (nivel or "").lower() != "activo":
        return []
    ids = fuentes_de_activo(entidad)
```

**REEMPLAZAR POR:**

```python
def _campos_sin_meta(c, entidad, fin, nivel):
    """Campos de un ACTIVO o de una GERENCIA que PRODUCEN pero no tienen PPTO en el mes.

    Aplica a los niveles que AGREGAN varios campos —'activo' y, desde 2026-09-09, 'gerencia'—:
    donde el REAL sumado puede quedar comparado contra un PPTO que no cubre a todos.
    Devuelve [] para cualquier otro nivel. Nunca inventa presupuesto (ver D-A4).

    [2026-09-09 · BUG1-GERENCIAS] Antes exigía `== "activo"`. Con las gerencias reales resolviendo,
    ese filtro habría ocultado el aviso justo donde más importa: PPH agrega 20 campos. Verificado
    con la extensión: PPH (mayo 2026) devuelve ARRAYAN (GAS) sin meta.
    """
    nv = (nivel or "").lower()
    if nv not in ("activo", "gerencia"):
        return []
    if nv == "gerencia":
        from app.features.consulta_v2.cuantificar.resolver import campos_de_gerencia
        campos = campos_de_gerencia(entidad)
        if not campos:
            return []      # gerencia de dim_fuente (no compone campos) → sin cambio de conducta
        ids = [r[0] for r in c.execute(sa.text(
            "SELECT fuente_id FROM core.dim_fuente WHERE UPPER(TRIM(campo)) = ANY(:cs)"),
            {"cs": [x.upper() for x in campos]})]
    else:
        ids = fuentes_de_activo(entidad)
```

El resto de la función (`if not ids: return []` y la query) **no se toca**: ya trabaja con `ids`.

### 3.3 — MODIFICAR archivo C: `respuesta_cuantificar.py` (bug latente H9)

**LOCALIZAR** (`respuesta_cuantificar.py:149-152`):

```python
    nivel = resuelta.get("nivel")
    vice = resuelta.get("valor") if nivel == "vicepresidencia" else None
    if nivel == "gerencia":
        vice = (resuelta.get("puente") or {}).get("vp") or None
```

**REEMPLAZAR POR:**

```python
    nivel = resuelta.get("nivel")
    vice = resuelta.get("valor") if nivel == "vicepresidencia" else None
    if nivel == "gerencia":
        # [2026-09-09 · BUG1-GERENCIAS] `puente` es un BOOLEANO (`resolver.py:201` escribe True),
        # no un dict. `(True or {}).get("vp")` reventaba con
        #     AttributeError: 'bool' object has no attribute 'get'
        # (reproducido). Latente porque casi ninguna gerencia llegaba aquí. Semántica correcta: si
        # el resolver marcó puente, ese código ES la vicepresidencia. Una gerencia REAL nunca lleva
        # la marca → None → el panel omite el bloque P50 (el P50 solo existe global y por VP).
        vice = resuelta.get("valor") if resuelta.get("puente") else None
```

### 3.4 — MODIFICAR archivo D: `maquina_q.py` — el clasificador lee el MISMO catálogo (H11)

#### 3.4.a Import

**LOCALIZAR** (`maquina_q.py:34`):

```python
from app.features.consulta_v2.cuantificar import slots as _slots_dia
```

**REEMPLAZAR POR:**

```python
from app.features.consulta_v2.cuantificar import slots as _slots_dia
from app.features.consulta_v2.cuantificar import resolver as _resolver_q   # gerencias_vigentes (BUG1)
```

#### 3.4.b Añadir las gerencias vigentes al catálogo de `detectar_entidad`

**LOCALIZAR** (`maquina_q.py:540-545`, final de `_nombres`):

```python
    except Exception:
        return set()   # sin cachear: reintenta en la próxima llamada
    if not ok:
        return set()
    _NOMBRES = nombres
    return nombres
```

**REEMPLAZAR POR:**

```python
    except Exception:
        return set()   # sin cachear: reintenta en la próxima llamada
    if not ok:
        return set()
    # [2026-09-09 · BUG1-GERENCIAS] Las gerencias REALES desde la FUENTE ÚNICA DE VERDAD, con la
    # MISMA función que usa el resolver de Cuantificar → un solo catálogo en la ruta. Medido antes:
    # «la gerencia CPI» daba detectar_entidad=None (la copia no trae CPI) y solo se salvaba por el
    # backstop de n-gramas. `gerencias_vigentes()` nunca lanza: sin ops devuelve [].
    for g in _resolver_q.gerencias_vigentes():
        k = norm(g)
        if k:
            nombres.add(k)
    _NOMBRES = nombres
    return nombres
```

⚠️ `_QUERIES_CATALOGO` (`maquina_q.py:513-515`) **no se toca**: sigue leyendo también la copia para
activos y VPs, que este plan no cubre (§7).

### 3.5 — CREAR archivo E: `tests\test_gerencia_robustez.py`

Tests **puros, sin BD**. Contenido completo:

```python
"""BUG1-GERENCIAS (2026-09-09) — las gerencias REALES (fuente única de verdad) son consultables.

PUROS: monkeypatch, sin Postgres ni robustez_v02. La verificación con cifras es humana, en
Pruebas (§6.2 del plan), y V6-V8 en local.

🔑 Higiene obligatoria: todo test que llegue a `resolver_unico` monkeypatchea
   `_cargar_vp_robustez` — si no, toca BD y CACHEA `set()` en `_VP_ROBUSTEZ`, contaminando los
   tests siguientes (mismo motivo por el que test_puente_gerencia_vp.py:38,43 lo resetea).
"""
import pytest

import app.core.db as _db
import app.features.consulta_v2.cuantificar.resolver as R
import app.features.consulta_v2.respuesta_cuantificar as RC


@pytest.fixture(autouse=True)
def _sin_bd(monkeypatch):
    """Aísla de Postgres/ops y limpia los caches de proceso antes y después de CADA test."""
    monkeypatch.setattr(R, "_cargar_vp_robustez", lambda: set())
    R._VP_ROBUSTEZ = None
    R._GER_CAMPOS = None
    R._GER_CANON = None
    yield
    R._VP_ROBUSTEZ = None
    R._GER_CAMPOS = None
    R._GER_CANON = None


def _idx(monkeypatch, mapa):
    """Fija el índice del resolver sin BD. Las claves DEBEN ir normalizadas (norm())."""
    monkeypatch.setattr(R, "_INDEX", mapa)


def _fuente_sets(monkeypatch, gerencias=None, campos=None, activos=None):
    """Fija los conjuntos físicos sin BD. Vacío = la entidad no está en dim_fuente."""
    monkeypatch.setattr(R, "_FUENTE_SETS", {
        "nombre": {}, "campo": campos or {}, "gerencia": gerencias or {},
        "operador": {}, R._ACTIVO_KEY: activos or {},
    })


# --- La gerencia real resuelve, con el nivel "gerencia" de siempre --------------------------
def test_gerencia_real_resuelve(monkeypatch):
    _idx(monkeypatch, {"PPC": [{"nivel": "gerencia", "rama": "A", "valor": "PPC"}]})
    r = R.resolver_unico("PPC")
    assert r is not None
    assert r["nivel"] == "gerencia"          # el nivel de SIEMPRE: el frontend ya sabe rotularlo
    assert r["valor"] == "PPC"


def test_gerencia_real_no_marca_puente(monkeypatch):
    """Ninguna gerencia vigente está en _VP_ROBUSTEZ (medido) → sin puente."""
    _idx(monkeypatch, {"PPC": [{"nivel": "gerencia", "rama": "A", "valor": "PPC"}]})
    assert "puente" not in R.resolver_unico("PPC")


def test_gerencia_de_dim_fuente_sigue_marcando_puente(monkeypatch):
    """No-regresión: GOR es VP en robustez y DEBE seguir llevando la marca."""
    monkeypatch.setattr(R, "_cargar_vp_robustez", lambda: {"GOR"})
    _idx(monkeypatch, {"GOR": [{"nivel": "gerencia", "rama": "A", "valor": "GOR"}]})
    assert R.resolver_unico("GOR").get("puente") is True


def test_clave_con_enie_se_normaliza(monkeypatch):
    """norm('PPÑ') == 'PPN' (NFKD pliega la ñ): la clave va plegada, el valor es el canónico."""
    assert R.norm("PPÑ") == "PPN"
    _idx(monkeypatch, {"PPN": [{"nivel": "gerencia", "rama": "A", "valor": "PPÑ"}]})
    assert R.resolver_unico("PPÑ")["valor"] == "PPÑ"


# --- clave_fisica: la gerencia sin fuentes propias NO colapsa con un homónimo (H7) ----------
def test_clave_fisica_gerencia_sin_fuentes_va_aparte(monkeypatch):
    """Sin esto, campo y gerencia colapsaban en ('F', frozenset()) → 'auto'."""
    _fuente_sets(monkeypatch)
    k_ger = R.clave_fisica({"nivel": "gerencia", "rama": "A", "valor": "XCOL"})
    k_cmp = R.clave_fisica({"nivel": "campo", "rama": "A", "valor": "XCOL"})
    assert k_ger != k_cmp
    assert k_ger[0] == "GER_ROB"


def test_clave_fisica_gerencia_de_dim_fuente_no_cambia(monkeypatch):
    """No-regresión: GOR sí tiene fuentes → conserva su clave ('F', {...}) de siempre."""
    _fuente_sets(monkeypatch, gerencias={"GOR": frozenset({1, 2})})
    assert R.clave_fisica({"nivel": "gerencia", "rama": "A", "valor": "GOR"}) == ("F", frozenset({1, 2}))


# --- Política de desempate (nombres SINTÉTICOS: hoy no hay colisión real, H6) ---------------
# >=2 identidades: con una sola, resolver_unico retorna en :260 y no colapsa nada.
def test_colision_campo_gerencia_sin_senal_gana_campo(monkeypatch):
    """D-D5 intacta: sin señal explícita gana Campo (decisión del usuario, 2026-07-15)."""
    _idx(monkeypatch, {"XCOL": [
        {"nivel": "campo", "rama": "A", "valor": "XCOL"},
        {"nivel": "gerencia", "rama": "A", "valor": "XCOL"},
    ]})
    _fuente_sets(monkeypatch)            # ninguno tiene fuentes → 2 grupos → "ask"
    r = R.resolver_unico("XCOL")
    assert "ambiguo" not in r            # D-D5 resuelve: hay exactamente 1 campo
    assert r["nivel"] == "campo"


def test_colision_campo_gerencia_con_senal_gana_gerencia(monkeypatch):
    """Nivel explícito gana sobre D-D5: el usuario ya desambiguó al escribirlo."""
    _idx(monkeypatch, {"XCOL": [
        {"nivel": "campo", "rama": "A", "valor": "XCOL"},
        {"nivel": "gerencia", "rama": "A", "valor": "XCOL"},
    ]})
    _fuente_sets(monkeypatch)
    r = R.resolver_unico("XCOL", contexto="¿cuánto produjo la gerencia XCOL?")
    assert "ambiguo" not in r
    assert r["nivel"] == "gerencia"


def test_codigo_en_ambos_catalogos_es_una_sola_identidad(monkeypatch):
    """CPV/GAN/GNS/GXO están en dim_fuente Y en la fuente de verdad: build_index deduplica y el
    resolver responde sin ambigüedad, como hoy."""
    _idx(monkeypatch, {"GAN": [{"nivel": "gerencia", "rama": "A", "valor": "GAN"}]})
    _fuente_sets(monkeypatch, gerencias={"GAN": frozenset({1, 2, 3})})
    r = R.resolver_unico("GAN")
    assert r["nivel"] == "gerencia" and r["valor"] == "GAN" and "ambiguo" not in r


# --- Detector de nivel explícito ------------------------------------------------------------
def test_nivel_explicito_gerencia():
    assert R._nivel_explicito("cuanto produjo la gerencia PPC") == "gerencia"
    assert R._nivel_explicito("produccion de las gerencias PPC") == "gerencia"


def test_nivel_explicito_sin_adyacencia_no_dispara():
    """Sin nombre detrás no etiqueta a nadie (misma guarda que ACTIVO/CAMPO)."""
    assert R._nivel_explicito("que es una gerencia") is None


def test_nivel_explicito_activo_y_campo_intactos():
    assert R._nivel_explicito("el activo CASTILLA") == "activo"
    assert R._nivel_explicito("el campo CASTILLA") == "campo"


# --- Composición gerencia -> campos (fuente de verdad) --------------------------------------
def test_campos_de_gerencia(monkeypatch):
    """PPC = 3 campos en la fuente de verdad (la copia solo traía 2: perdía CASTILLA ESTE)."""
    monkeypatch.setattr(R, "_GER_CAMPOS",
                        {"PPC": ["CASTILLA", "CASTILLA ESTE", "CASTILLA NORTE"]})
    assert R.campos_de_gerencia("PPC") == ["CASTILLA", "CASTILLA ESTE", "CASTILLA NORTE"]
    assert R.campos_de_gerencia("ppc") == ["CASTILLA", "CASTILLA ESTE", "CASTILLA NORTE"]


def test_campos_de_gerencia_inexistente(monkeypatch):
    monkeypatch.setattr(R, "_GER_CAMPOS", {"PPC": ["CASTILLA"]})
    assert R.campos_de_gerencia("NO_EXISTE") == []
    assert R.campos_de_gerencia("") == []
    assert R.campos_de_gerencia(None) == []


def test_gerencias_vigentes_devuelve_el_nombre_canonico(monkeypatch):
    """norm() pliega la ñ (PPÑ -> PPN): el índice debe guardar «PPÑ», no «PPN»."""
    monkeypatch.setattr(R, "_GER_CAMPOS", {"PPN": ["MITO"], "PPC": ["CASTILLA"]})
    monkeypatch.setattr(R, "_GER_CANON", {"PPN": "PPÑ", "PPC": "PPC"})
    assert R.gerencias_vigentes() == ["PPC", "PPÑ"]


def test_sin_ops_no_lanza_ni_cachea(monkeypatch):
    """Si robustez_v02 no está (p.ej. el 139): vacío, sin excepción y sin cachear el fallo."""
    def _boom():
        raise RuntimeError("OPS_DATABASE_URL no configurada")
    monkeypatch.setattr(_db, "get_ops_engine", _boom)   # el import es diferido: parchear el módulo
    assert R.campos_de_gerencia("PPC") == []
    assert R.gerencias_vigentes() == []
    assert R._GER_CAMPOS is None          # no se cacheó el error


def test_build_index_dedup_y_tolerante(monkeypatch):
    """Un mismo código en dim_fuente y en la fuente de verdad → UNA identidad. Una consulta que
    falle no tumba el índice."""
    class _Res:
        def __init__(self, rows): self._r = rows
        def __iter__(self): return iter(self._r)
    class _Conn:
        def execution_options(self, **k): return self
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, stmt):
            s = str(stmt)
            if "dim_fuente" in s and "gerencia" in s:
                return _Res([("GAN",), ("GOR",)])
            if "dim_empresa" in s:
                raise RuntimeError("tabla ausente")
            return _Res([])
    class _Eng:
        def connect(self): return _Conn()
    monkeypatch.setattr(R, "get_engine", lambda: _Eng())
    monkeypatch.setattr(R, "gerencias_vigentes", lambda: ["GAN", "PPC"])
    idx = R.build_index()
    assert idx["GAN"] == [{"nivel": "gerencia", "rama": "A", "valor": "GAN"}]   # dedup
    assert idx["PPC"] == [{"nivel": "gerencia", "rama": "A", "valor": "PPC"}]
    assert idx["GOR"][0]["valor"] == "GOR"                                       # la tabla ausente no tumbó nada


# --- H9: el bug latente del panel P50 -------------------------------------------------------
def test_p50_gerencia_puente_no_revienta(monkeypatch):
    """Antes lanzaba: AttributeError: 'bool' object has no attribute 'get'."""
    monkeypatch.setattr(RC._p50, "serie_por_vp", lambda *a, **k: None)
    res = {"producto": "crudo", "mes": {"anio": 2026, "mes": 8}}
    assert RC._p50_del_mes({"nivel": "gerencia", "valor": "GOR", "puente": True}, res) is None


def test_p50_gerencia_real_sin_puente_devuelve_none(monkeypatch):
    """Una gerencia REAL no tiene P50 propio: se omite el bloque, sin error."""
    monkeypatch.setattr(RC._p50, "serie_por_vp", lambda *a, **k: None)
    res = {"producto": "crudo", "mes": {"anio": 2026, "mes": 8}}
    assert RC._p50_del_mes({"nivel": "gerencia", "valor": "PPC"}, res) is None
```

(`RC._p50` existe: `respuesta_cuantificar.py:37` importa `p50_referencia as _p50`. `R.norm` y
`R._ACTIVO_KEY` existen: `resolver.py:18` y `:85`.)

### 3.6 — MODIFICAR archivo F: `cuantificar_golden.yaml`

**LOCALIZAR** (líneas 30-33):

```yaml
- pregunta: "¿cuánto produjo la gerencia GOR?"
  entidad: "GOR"
  nivel_temporal: N1
  resultado: aplica          # nivel gerencia (dim_fuente.gerencia, catálogo propio de cuantificar)
```

**REEMPLAZAR POR** (el caso original se conserva):

```yaml
- pregunta: "¿cuánto produjo la gerencia GOR?"
  entidad: "GOR"
  nivel_temporal: N1
  resultado: aplica          # nivel gerencia (dim_fuente.gerencia, catálogo propio de cuantificar)
# [2026-09-09 · BUG1-GERENCIAS] Gerencias REALES desde la FUENTE ÚNICA DE VERDAD
# (robustez_v02.ops.wells_attributes). Antes daban "sin_entidad". GOR (arriba) seguía funcionando
# porque está en dim_fuente — por eso el golden no detectaba nada.
# ⚠️ Estos 3 casos EXIGEN robustez_v02: en un entorno sin ops (el 139) darán "sin_entidad".
- pregunta: "¿cuánto produjo la gerencia PPC?"
  entidad: "PPC"
  nivel_temporal: N1
  resultado: aplica          # PPC = {CASTILLA, CASTILLA ESTE, CASTILLA NORTE}
- pregunta: "¿cuánto ha producido la gerencia PPH en lo que va del año?"
  entidad: "PPH"
  nivel_temporal: N2
  resultado: aplica          # la gerencia con más campos (20 en la fuente, 18 en INGESTA)
- pregunta: "¿cuánto produjo la gerencia CPI?"
  entidad: "CPI"
  nivel_temporal: N1
  resultado: aplica          # vigente en la fuente de verdad y AUSENTE en la copia (H4)
```

### 3.7 — MODIFICAR archivo G: `run_golden_cuantificar.py` (H12)

**LOCALIZAR** (línea 51):

```python
        resuelta = _resolver.resolver_unico(c["entidad"] or c["pregunta"])
```

**REEMPLAZAR POR:**

```python
        # [2026-09-09 · BUG1-GERENCIAS] `contexto` = la pregunta ORIGINAL. Sin él, el detector de
        # nivel explícito (resolver.py:236-259) queda CIEGO en el arnés: `entidad` ya viene reducida
        # y la palabra «gerencia» se pierde. Es lo mismo que hace respuesta_cuantificar.py:93.
        resuelta = _resolver.resolver_unico(c["entidad"] or c["pregunta"], contexto=c["pregunta"])
```

---

## 4. Orden de ejecución

| # | Archivo | Cambio | Depende de |
|---|---|---|---|
| **0** | — | **V0 de §6.1: línea base de pytest ANTES de tocar nada** | — |
| 1 | A `resolver.py` | §3.1.e — `gerencias_vigentes` / `campos_de_gerencia` (primero: los demás las usan) | 0 |
| 2 | A `resolver.py` | §3.1.a — comentario en `_LEVELS` | 1 |
| 3 | A `resolver.py` | §3.1.b — `build_index` tolerante + fuente de verdad | 1 |
| 4 | A `resolver.py` | §3.1.c — «gerencia» en el detector explícito | 1 |
| 5 | A `resolver.py` | §3.1.d — `clave_fisica` no colapsa la gerencia | 4 |
| 6 | B `analisis/api.py` | §3.2.a — precedencia en `_ambito` | 1 |
| 7 | B `analisis/api.py` | §3.2.b — `_campos_sin_meta` con gerencias | 1 |
| 8 | C `respuesta_cuantificar.py` | §3.3 — bug latente H9 | — |
| 9 | D `maquina_q.py` | §3.4 — clasificador con el mismo catálogo | 1 |
| 10 | E `tests\test_gerencia_robustez.py` | §3.5 — CREAR | 1-9 |
| 11 | F `cuantificar_golden.yaml` | §3.6 | 1-9 |
| 12 | G `run_golden_cuantificar.py` | §3.7 | — |

**Secuencial. Si un paso falla, DETENERSE y reportar.** Si un ancla `LOCALIZAR` no aparece
**exacta**, DETENERSE: no adaptar.

---

## 5. Reglas no negociables

1. **La fuente es `robustez_v02.ops.wells_attributes`**, con los DOS filtros de
   `ranking.py:277-279`. **Prohibido** leer `core.map_campo_robustez` o el CSV en este plan.
2. **No borrar la línea `("gerencia", … dim_fuente …)`** de `_LEVELS`: las 4 gerencias que hoy
   funcionan y la marca `puente` dependen de ella.
3. **No crear un nivel nuevo.** Se reusa `"gerencia"`.
4. **Precedencia, no reemplazo**, en `_ambito` y `_campos_sin_meta`: la composición solo actúa si
   `dim_fuente` no devolvió nada.
5. **No tocar** `NIVELES_SQL`, `_NIVEL_COL_AMB`, `_PRIORIDAD`, `_NIVEL_TEXTO` ni
   `_QUERIES_CATALOGO`.
6. **Ningún `except` nuevo puede lanzar.** Devolver el neutro y **no cachear el fallo**.
7. **No tocar el edificio v1** (`app\features\consulta\`).
8. **No correr `build_map_campo_robustez.py` en local** (empeora el CSV) ni el golden de
   Cuantificar en local (regla de RAM).
9. **Todos los tests nuevos son PUROS.** Prohibido un test que dependa de Postgres u ops.
10. **No hacer commit.** Al terminar, preguntar.

---

## 6. Validación

### 6.1 Estática — la corre el EXECUTOR

Desde `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend`, PowerShell normal, sin admin, **línea
por línea**.

🔴 **V0 — LÍNEA BASE, ANTES DE TOCAR NADA (paso 0 de §4).** No existe archivo con los fallos
preexistentes (verificado); el número depende de la BD local. El executor mide el suyo:

```powershell
cd 'C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend'
.venv\Scripts\python.exe -m pytest tests/ -q > "$env:TEMP\baseline_antes.txt" 2>&1
```

| # | Comando | Resultado esperado |
|---|---|---|
| V1 | `.venv\Scripts\python.exe -m py_compile app\features\consulta_v2\cuantificar\resolver.py app\features\analisis\api.py app\features\consulta_v2\respuesta_cuantificar.py app\features\consulta_v2\maquina_q.py` | Sin salida |
| V2 | `.venv\Scripts\python.exe -m pytest tests/test_gerencia_robustez.py -q` | **19 passed** |
| V3 | `.venv\Scripts\python.exe -m pytest tests/test_puente_gerencia_vp.py tests/test_cuantificar.py tests/test_consulta_desambiguacion.py tests/test_p50_referencia.py tests/test_consulta_v2_clasificador.py -q` | 0 fallos nuevos respecto a V0 |
| V4 | `.venv\Scripts\python.exe -m pytest tests/ -q > "$env:TEMP\baseline_despues.txt" 2>&1` | Los mismos fallos que V0; `passed` sube exactamente en **19** |
| V5 | `.venv\Scripts\python.exe -c "import yaml,pathlib; c=yaml.safe_load(pathlib.Path('app/features/consulta_v2/golden/cuantificar_golden.yaml').read_text(encoding='utf-8')); print(len(c))"` | `27` |
| V6 | `.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'.'); from app.features.consulta_v2.cuantificar import resolver as R; g=R.gerencias_vigentes(); print(len(g), g)"` | `20 ['CPI', 'CPV', 'CUF', 'CUP', 'GAN', 'GNS', 'GXO', 'PCI', 'PCN', 'PCS', 'PDB', 'PDH', 'POE', 'PPA', 'PPC', 'PPH', 'PPU', 'PPÑ', 'PTN', 'PUC']` |
| **V7** | `.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'.'); from app.features.consulta_v2.cuantificar import resolver as R; print([ (e, (R.resolver_unico(e) or {}).get('nivel')) for e in ['PPC','CPI','GOR','ANDINA']])"` | `[('PPC','gerencia'), ('CPI','gerencia'), ('GOR','gerencia'), ('ANDINA','campo')]` |
| **V8** | `.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'.'); from app.features.analisis.api import desempeno as d; r=d(entidad='PPC',segmento='ecp',nivel='gerencia',periodo='mayo 2026'); p=[x for x in r['por_producto'] if x['producto']=='CRUDO'][0]; print(r['encontrada'], round(p['real'],2), round(p['ppto'],2))"` | `True 93.71 89.46` |
| **V9** | El barrido de las 20 (bloque de abajo) | `resuelven: 20/20` · `con dato: 20/20` · `ANDINA=campo` |

**V9 — prueba del objetivo.** Pegar completo en PowerShell (una sola línea lógica; si queda en
`>>`, pulsar Enter):

```powershell
cd 'C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend'
.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'.'); from app.features.consulta_v2.cuantificar import resolver as R; from app.features.analisis.api import desempeno as d; V=R.gerencias_vigentes(); ok=sum(1 for g in V if (R.resolver_unico(g) or {}).get('nivel')=='gerencia'); dat=sum(1 for g in V if d(entidad=g,segmento='ecp',nivel='gerencia',periodo='mayo 2026').get('encontrada')); print('resuelven: %d/%d' % (ok,len(V))); print('con dato: %d/%d' % (dat,len(V))); print('ANDINA=%s' % (R.resolver_unico('ANDINA') or {}).get('nivel'))"
```

⚠️ **V4 se juzga por DIFERENCIA contra V0.** Un test fallando que no esté en `baseline_antes.txt`
→ **DETENERSE**. Un `skipped` que crece significa que la BD no está, no que el cambio esté bien.

⚠️ V6-V8 exigen `OPS_DATABASE_URL` (esta máquina la tiene). Si fallan con `RuntimeError:
OPS_DATABASE_URL no configurada`, reponerla con `backend\fix_ops_database_url.py` y repetir.
V8 depende de la BD local congelada en mayo 2026: **93,71 = CASTILLA 54,46 + CASTILLA NORTE
39,25**, medido el 2026-09-09.

### 6.2 Humana — la corre el USUARIO, en el SERVIDOR DE PRUEBAS

**R3 del `CLAUDE.md` §10.4: «build verde» NO es «feature verificada».**

Golden (desde `backend\backend`, con VPN y `OPS_DATABASE_URL`):

```powershell
cd 'C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend'
$env:PYTHONPATH="."; uv run python app/features/consulta_v2/golden/run_golden_cuantificar.py
```

Esperado: `EXACTITUD: >=25/27 = >=92%` **(gate ≥90%)**.

En el chat, `http://localhost:5029`:

| # | Pregunta | Qué debe pasar |
|---|---|---|
| H1 | «¿cuánto produjo la gerencia PPC?» | Cifra, y el texto dice **«la Gerencia PPC»**. Ya no «No reconocí PPC» |
| H2 | «¿qué es castilla?» y luego H1 | Coherencia: el panel pinta `GER PPC` y la cifra existe |
| H3 | «¿cuánto produjo PPC?» (sin decir «gerencia») | También responde |
| H4 | «¿cuánto produjo la gerencia CPI?» | Responde (vigente en la fuente; ausente en la copia) |
| H5 | «¿cuánto produjo GAN?» | Igual que antes: está en dim_fuente y manda la precedencia |
| H6 | «¿cuánto produjo la gerencia GOR?» | Igual que antes: «la Vicepresidencia GOR» (puente) |
| H7 | «¿cuánto produjo el activo CASTILLA?» | El activo (bug 2, no-regresión) |
| H8 | «¿cuánto produjo la VRO en agosto?» | El panel P50 **no revienta** (H9) |
| H9 | «¿cuánto produjo la gerencia PPH?» | Si algún campo no tiene PPTO, aparece **«produce sin meta asignada»** (H10) |

**🔴 Contraste obligatorio de cifra.** PPC del mes ≈ CASTILLA + CASTILLA NORTE (+ CASTILLA ESTE si
INGESTA lo trae). Si PPC = CASTILLA a secas, el join toma un solo campo: **DETENERSE**.

**El único que marca ✅ una feature es el usuario.** Sin §6.2 el estado es «implementado,
PENDIENTE de validación humana».

---

## 7. Fuera de alcance y oportunidades de mejora detectadas

**Fuera de alcance (no se toca en este plan):**
- **Bug 3** (`jerarquias_sup_error.md` §5): barrido 17 códigos × 3 productos. 3º del orden.
- **Fase 3 / R11** (un solo resolver para todo el motor).
- **Frontend**: cero cambios (consecuencia de reusar `"gerencia"`).
- **`NIVELES_SQL`** y el explorador del tablero.
- **Activos y VPs del catálogo del clasificador** (`_QUERIES_CATALOGO`) siguen en la copia.
- **El panel jerárquico** (`respuesta_jerarquizar._cargar`) sigue leyendo la copia.
- **`analizar\diferidas.py`**: sigue declinando gerencias, y es correcto.

**Oportunidades de mejora (detectadas, NO implementadas — decisión del usuario):**
1. 🔴 **Mover el catálogo de jerarquías a la BD** (pendiente ya acordado): migración versionada de
   `core.map_campo_robustez` + refresco desde `ops` con marca de fecha, con los dos filtros. Cerraría
   de raíz la divergencia (H4), el panel jerárquico y el caso del 139 sin `ops`.
2. `build_map_campo_robustez.py` **debe aplicar los dos filtros** de `ranking.py:277-279` — hoy
   genera la rama vieja. Mientras exista, está mal.
3. **P50 de la VP para gerencias**: el commit del 8-sep dio a los campos el P50 de su VP con
   `alcance`; una gerencia podría recibirlo igual (`management → vice_presidency` en `ops`).
4. `respuesta_jerarquizar.py:248` y `p50_referencia.nivel_soportado` podrían reconocer las
   gerencias vigentes de la fuente, hoy solo la copia/`puente`.

---

## 8. Decisiones cerradas

| Decisión | Valor | Por qué |
|---|---|---|
| Fuente de datos | **`robustez_v02.ops.wells_attributes`** con los 2 filtros oficiales | Regla del proyecto; la copia diverge en 8 códigos y pierde CASTILLA ESTE (H4) |
| Nivel | **Reusar `"gerencia"`** | Frontend y 4 consumidores de `puente` intactos; ningún rótulo vacío |
| `dim_fuente` vs composición | **Precedencia: `dim_fuente` primero** | Conserva byte a byte lo que ya funcionaba (GOR, GAA, y CPV/GAN/GNS/GXO) |
| Clasificador | **Mismo catálogo (`gerencias_vigentes`)** | Un solo catálogo en la ruta de Cuantificar (H11) |
| Colisiones | **Nivel explícito + clave propia** | Hoy no hay colisión real (H6), pero la política queda correcta (H7) |
| Aviso PPTO faltante | **Se extiende a gerencia** | PPH agrega 20 campos; simulado: ARRAYAN (GAS) sin meta (H10) |
| Bug latente `puente` | **Se arregla aquí** | Este plan es justo lo que lo activaría (H9) |
| Sin `ops` (el 139) | **Degrada al comportamiento de hoy** | Sin regresión; la mejora llega con el pendiente de mover el catálogo a la BD |
| Tests | **19, puros** | Sin Postgres ni ops; los caches se limpian por fixture |
