# plan_FIX-NIVEL-N1 — 2026-09-08 · v2 (auditado y corregido)

**ID tarea:** FIX-NIVEL-N1
**Fecha:** 2026-09-08
**Repo:** `ProdIABack` — `C:\APLICACIONES\ProdIA\Repo ProdIA\backend`
**Tipo:** corrección de un defecto **ya desplegado en el servidor de pruebas** (commits
`558e0a9` backend y `3f1e02c` frontend, del plan PANEL-N1-ENRIQUECIDO).

**Alcance:** UNA línea de código + UNA línea de test. Nada más.

**Qué NO se toca:** el frontend (**cero cambios**, ni JS ni plantillas ni cache-buster), el
clasificador, el drill, los demás niveles temporales, `p50_referencia.py`, `analisis/api.py`,
los goldens, la BD, el ETL.

---

## §0.-1 · Changelog v1 → v2

El v1 se auditó **ejecutando** el código, no leyéndolo. La corrección en sí resultó correcta y
no cambia; lo que salió fueron **una validación inútil y cuatro comprobaciones que faltaban**:

| # | Qué decía el v1 | Qué se midió | Efecto |
|---|---|---|---|
| C-1 | V-3 contaba `res["entidad"]["nivel"]` y esperaba **3 líneas** | 🟡 Hoy **ya hay 3** (las dos correctas + la del `nivel_entidad` que se renombra). Antes y después da lo mismo | La validación **no distinguía nada**. Corregida al patrón `"nivel": res[...]`, que va de **2 a 3** |
| C-2 | No comprobaba si los **demás niveles** también se arreglan | 🟢 El resolutor emite 4 (`campo`, `activo`, `gerencia`, `vicepresidencia`) y **los cuatro tienen rama propia** en `_ambito` | El arreglo es **completo**, no parcial. Ahora está documentado (H-07) |
| C-3 | No decía nada de las **cachés** | 🟢 Las dos (navegador `:4202` y proxy Flask `:228`) **incluyen `nivel` en la clave**; los TTL son 45s y 200s | No hay que purgar nada, pero había que verificarlo antes de afirmarlo (H-08) |
| C-4 | No acotaba **para qué se usa** `nivel` en el frontend | 🟢 Exactamente dos usos: clave de caché (`:4319`) y parámetro HTTP (`:4323`). Ninguno más | Confirma que corregir el origen basta y el frontend no se toca (H-09) |

Ninguno cambia la especificación de la §3. El v2 añade el porqué medido y arregla V-3.

---

## §0.0 · El defecto, en una frase

El panel de N1 emite `"nivel": "N1"` (el nivel **temporal**) donde el frontend espera el nivel
**de entidad** (`"campo"`, `"vicepresidencia"`…), y ese valor viaja como parámetro HTTP a dos
endpoints que no lo reconocen.

### Síntomas medidos en el servidor de pruebas (capturas del usuario, 2026-09-08)

| Pregunta | Lo que dice el texto | Lo que muestra el panel |
|---|---|---|
| «¿Cuánto produjo Castilla en abril?» | CASTILLA · **55,0 kbopd** · PPTO **52,1** | tarjeta con **94,7** · meta **90,0** |
| ídem | — | curva: **«Sin curva diaria para este producto»** |

Son **dos síntomas de una sola causa**. No son dos defectos.

### La cadena, medida

```
respuesta_cuantificar.py:263   "nivel_entidad": "campo"   ← clave NUEVA (inventada)
respuesta_cuantificar.py:175   "nivel": "N1"              ← lo que queda en `nivel`
                                    │
multitab_shell.js:4309         var nivel = datos.nivel;   → "N1"
multitab_shell.js:4317         _qp.push("nivel=" + …)     → &nivel=N1
                                    │
analisis/api.py:405-421        nv = "n1"
                               ├ nv == "vicepresidencia"?  no
                               ├ nv == "activo"?           no
                               ├ _NIVEL_COL_AMB.get("n1")? None   ← :368-369
                               └ ELSE: rama de compatibilidad «sin nivel»
                                       OR sobre nombre, campo, gerencia, operador
                                       + fuentes_de_activo(E) + vice_id
```

La rama de compatibilidad resuelve un **conjunto de fuentes distinto** al del nivel real. De
ahí las dos cifras que no cuadran y la curva vacía.

### Reproducido en local, sin BD (2026-09-08)

`_panel_datos` es una función pura sobre el dict del ejecutor. Con un N1 de CASTILLA/abril:

```
nivel         = 'N1'      <- esto es lo que viaja como &nivel= al backend
nivel_entidad = 'campo'   <- el valor correcto, en una clave que nadie lee
entidad       = 'CASTILLA' | periodo: 'abril 2026'
```

**El defecto no depende de datos ni del servidor**: está en el payload que arma el backend, y
se ve importando el módulo en un proceso nuevo. Por eso el arreglo se puede verificar entero
en local, aunque su efecto visible solo se confirme en pruebas (§6.2).

---

## §0 · Contexto para el agente EXECUTOR

**Proyecto ProdIA** (Ecopetrol). Dos repos hermanos: `frontend\` (Flask, :5029) y `backend\`
(FastAPI con `uv`, :5030). **Este plan toca SOLO el backend, y dentro de él un solo archivo.**

El **Motor Q v2** responde preguntas de producción. En el grupo Cuantificar hay *niveles
temporales*: **N1** (un mes puntual), N2 (acumulado), N3 (serie), N1D (un día), N1DSER (la
curva de un mes), etc. Cada nivel arma un *payload de panel* que el frontend usa para pintar.

**Convención del proyecto, ya establecida:** en el payload del panel, la clave `nivel`
contiene el **nivel de ENTIDAD** (`campo`, `activo`, `vicepresidencia`…), porque el frontend
la reenvía a los endpoints `/analisis/desempeno` y `/analisis/ejecutivo`, que la usan para
resolver a qué fuentes de datos corresponde la entidad.

**Archivos que se tocan (rutas absolutas):**

| # | Acción | Ruta |
|---|---|---|
| 1 | MODIFICAR | `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\respuesta_cuantificar.py` |
| 2 | MODIFICAR | `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\tests\test_panel_n1_enriquecido.py` |

**Convenciones obligatorias:**

- Todo el código y **todos los comentarios en español**.
- Python: se ejecuta con `uv run` desde `...\backend\backend`.
- Los comentarios explican **por qué**, citando la evidencia (archivo:línea). El bloque nuevo
  lleva la marca `[2026-09-08 · FIX-NIVEL-N1]`.
- **Si algo del plan no calza con el código real, DETENERSE y reportar. No improvisar.**

---

## §1 · Hallazgos de la auditoría

### 🔴 H-01 (bloqueante) — Los tres niveles que SÍ funcionan usan `nivel` = nivel de entidad

`grep -n '"nivel"' respuesta_cuantificar.py`:

| Línea | Nivel | Qué emite |
|---|---|---|
| `:175` | *todos* | `d = {"nivel": nivel, …}` — el nivel **TEMPORAL**, valor inicial |
| `:187` | **N1DSER** | `"nivel": res["entidad"]["nivel"]` — lo **pisa** con el de entidad |
| `:214` | **N1D / N1DSEL** | `"nivel": res["entidad"]["nivel"]` — lo **pisa** con el de entidad |
| `:263` | **N1** (nuevo) | `"nivel_entidad": …` — **NO lo pisa**. Aquí está el defecto |

Los tres paneles que hoy funcionan en la app **pisan** `nivel` con el nivel de entidad. Es la
convención, no una casualidad: los tres alimentan el mismo panel (`cuant_dia_panel`) y el
mismo consumidor (`__cnCompProdCargar`).

La captura del usuario con **CHICHIMENE · agosto** (un N1DSER) muestra la tarjeta y la curva
correctas — con el mismo código de dibujo, la misma entidad de tipo campo y un mes que no es
el del corte. **Esa captura es la prueba de que el defecto está en lo que N1 emite, no en el
dibujo ni en los datos.**

### 🔴 H-02 (bloqueante) — `nivel_entidad` es una clave huérfana: nadie la lee

`grep -rn "nivel_entidad" app/ tests/`:

```
app/features/consulta_v2/respuesta_cuantificar.py:263    ← la escribe (mi código)
tests/test_panel_n1_enriquecido.py:42                    ← la lee un test (mío)
```

**Cero lectores en el frontend.** `multitab_shell.js` no la menciona ni una vez. Se introdujo
para «no pisar `d['nivel']`» y se prometió que el frontend la leería (plan
PANEL-N1-ENRIQUECIDO, H-02: *«El frontend leerá `nivel_entidad` (§3.2, Cambio 6)»*), pero ese
cambio **nunca se especificó** — la referencia quedó huérfana al reescribir aquel plan de v1 a
v2.

**Consecuencia para el diseño:** eliminar la clave no rompe nada. La corrección es volver a la
convención, no añadir un lector nuevo en el frontend.

### 🟢 H-03 (confirmación) — Nadie lee `d["nivel"]` esperando el nivel TEMPORAL en este panel

Los dos únicos lectores del frontend que comparan `nivel` contra un nivel temporal son:

| Línea | Función | Panel que la usa |
|---|---|---|
| `:3864` | `__cnCuantCardHtml` — `dat.nivel === "N2"` | `cuant_kpi` (el fallback del dispatcher) |
| `:3909` | `__cnCuantDiaHtml` — `dat.nivel === "N1DSEL"` | `cuant_dia` |

**Ninguno de los dos recibe el payload de N1**: desde el commit `558e0a9`, N1 se despacha por
la rama `cuant_dia_panel` (`multitab_shell.js:4421`), que va a `__cnCompProdCargar`. La rama
`cuant_kpi` es el `else` final del dispatcher (`:4464`) y su propio comentario advierte que
*«NO valida el tipo y pintaría campos ajenos»* — razón de más para que N1 no vuelva a caer
ahí, y no lo hace.

⚠️ **N2 sigue usando `cuant_acum`** y su rama en `_panel_datos` (`:266` en adelante) **no se
toca**: este plan solo entra en el `if nivel == "N1"`.

### 🟢 H-04 (confirmación) — El dato diario de meses anteriores SÍ existe

Durante el diagnóstico se afirmó que la curva solo existía para el mes del corte, deduciéndolo
del filtro `SQL_ULTIMO_REPORTE_D` (`app/core/unidades.py:54-57`). **Esa afirmación era falsa** y
la desmiente la captura del usuario: CHICHIMENE, **agosto 2026**, «31 días con reporte», curva
completa — con el corte en septiembre.

Se deja constancia porque condiciona la validación: **no hay que arreglar nada de la curva**.
Con el `nivel` correcto, la curva de un mes cerrado se pinta.

### 🟡 H-05 (relevante) — El test hay que corregirlo, no borrarlo

`tests/test_panel_n1_enriquecido.py:42` afirma hoy:

```python
assert d["nivel_entidad"] == "campo"  # el de la entidad viaja en su propia clave
```

Esa aserción **fija el defecto**: si se cambia el código sin tocarla, el test falla y el
executor se detiene. Debe pasar a comprobar el contrato correcto —`nivel` es el de entidad— y
que la clave huérfana ya no existe.

### 🟢 H-07 (confirmación) — 🆕 v2 · El arreglo cubre los CUATRO niveles, no solo `campo`

No basta con que funcione para CASTILLA. Se enumeró lo que el resolutor puede emitir y se
contrastó contra las ramas de `_ambito` (`analisis/api.py:405-423`):

| Nivel que emite el resolutor | Rama de `_ambito` | ¿Resuelve bien? |
|---|---|---|
| `campo` | `_NIVEL_COL_AMB["campo"]` → columna `campo` | ✅ |
| `activo` | rama propia → `fuentes_de_activo(E)` | ✅ |
| `gerencia` | `_NIVEL_COL_AMB["gerencia"]` → columna `gerencia` | ✅ |
| `vicepresidencia` | rama propia → `vice_id` | ✅ |

**Los cuatro tienen rama propia.** Ninguno cae al `else` de compatibilidad. El arreglo es
completo: no deja niveles a medias que haya que atender en otra entrega.

### 🟢 H-08 (confirmación) — 🆕 v2 · Las cachés se invalidan solas: no hay que purgar nada

Son dos, y **ambas incluyen `nivel` en la clave**:

| Caché | Dónde | Clave |
|---|---|---|
| Navegador | `multitab_shell.js:4201-4203` | `"ecp\|" + entidad + "\|" + nivel + "\|" + periodo` |
| Proxy Flask | `routes/api.py:226-229` | `ruta + "?" + params ordenados` (TTL 45s `/desempeno`, 200s `/ejecutivo`) |

Al pasar `nivel` de `"N1"` a `"campo"`, **la clave cambia**: las entradas envenenadas quedan
huérfanas y la siguiente petición va al backend. Además los TTL las vencen solos.

⚠️ Se comprueba porque una caché con clave incompleta habría dejado el defecto vivo tras el
arreglo — el fallo que `:4312-4315` documenta haber sufrido ya con la ventana móvil.

### 🟢 H-09 (confirmación) — 🆕 v2 · `nivel` se usa en exactamente dos sitios del frontend

`__cnCompProdCargar` (`:4309-4325`):

```javascript
var entidad = datos.entidad, nivel = datos.nivel, periodo = datos.periodo;
…
var key = __cnAnzCacheKey(entidad, nivel, periodo) + …          // :4319  uso 1
if (nivel) _qp.push("nivel=" + encodeURIComponent(nivel));      // :4323  uso 2
```

No hay un tercer uso. **Corregir el valor en origen arregla los dos a la vez**, y por eso el
frontend no se toca — que es además lo que mantiene esta entrega en un solo repo y un solo
commit.

### 🟡 H-06 (relevante) — El P50 no depende de esto y no se toca

`_p50_del_mes` (`:140-…`) recibe `resuelta` (el dict del **resolutor**, no el payload) y lee
`resuelta.get("nivel")`, que siempre ha sido el nivel de entidad. **No le afecta este cambio.**

Nota: la línea del P50 **sigue sin haberse podido validar en la app**, porque «la VRO» no se
resuelve como vicepresidencia (brecha de `CLAUDE.md §6`). Eso es **otra tarea**, fuera de este
plan (§7).

---

## §2 · Estado actual

`respuesta_cuantificar.py`, dentro de `_panel_datos`:

```python
:174    nivel = res.get("nivel")                    # nivel TEMPORAL: "N1", "N2", "N3"…
:175    d = {"nivel": nivel, "entidad_cualificada": …, "producto": …, "unidad": …, "avisos": …}
        …
:187        "nivel": res["entidad"]["nivel"],       # N1DSER  → PISA con el de entidad ✅
:214        "nivel": res["entidad"]["nivel"],       # N1D/SEL → PISA con el de entidad ✅
        …
:258    if nivel == "N1":
:259        _m = res.get("mes") or {}
:260        d.update({
:261            "entidad": res["entidad"]["nombre"],
:263            "nivel_entidad": res["entidad"]["nivel"],   # ❌ NO pisa `nivel`
:264            "segmento": "ecp",
                …
```

---

## §3 · Especificación

### 3.1 · MODIFICAR `respuesta_cuantificar.py`

#### Cambio 1 de 2 — `nivel` vuelve a ser el nivel de entidad

**LOCALIZAR** (es la línea `:263`; el fragmento de tres líneas la hace única):

```python
                "entidad": res["entidad"]["nombre"],
                "nivel_entidad": res["entidad"]["nivel"],
                "segmento": "ecp",
```

**SUSTITUIR POR:**

```python
                "entidad": res["entidad"]["nombre"],
                # [2026-09-08 · FIX-NIVEL-N1] `nivel` PISA al nivel temporal con el de ENTIDAD,
                # igual que hacen N1DSER (:187) y N1D/N1DSEL (:214). No es un detalle de estilo:
                # el frontend reenvía esta clave como parámetro HTTP a /analisis/desempeno y
                # /analisis/ejecutivo (multitab_shell.js:4309,4317), y allí `_ambito()` la usa
                # para resolver a qué fuentes corresponde la entidad.
                # 🔑 Medido en el servidor de pruebas (2026-09-08): con "N1" en esta clave,
                #    `_ambito` no reconoce el valor (analisis/api.py:368-369 solo admite
                #    fuente/pozo/campo/gerencia/operador) y cae a su rama de compatibilidad
                #    «sin nivel», que hace un OR sobre nombre+campo+gerencia+operador. El
                #    resultado fue una tarjeta con 94,7 kbopd donde el texto decía 55,0, y la
                #    curva vacía. Un fallo SILENCIOSO: no avisa, responde otra cosa con
                #    seguridad — la familia de bugs que CLAUDE.md §6 marca como la más grave.
                # 🔑 La clave `nivel_entidad` que estuvo aquí era huérfana: la escribía solo este
                #    bloque y no la leía NADIE (verificado con grep sobre app/ y el frontend).
                "nivel": res["entidad"]["nivel"],
                "segmento": "ecp",
```

### 3.2 · MODIFICAR `tests/test_panel_n1_enriquecido.py`

#### Cambio 2 de 2 — El test fija el contrato correcto

**LOCALIZAR:**

```python
    assert d["nivel"] == "N1"             # el nivel TEMPORAL no se pisa
    assert d["nivel_entidad"] == "campo"  # el de la entidad viaja en su propia clave
```

**SUSTITUIR POR:**

```python
    # [2026-09-08 · FIX-NIVEL-N1] `nivel` es el de ENTIDAD, no el temporal. El frontend lo
    # reenvía a /desempeno y /ejecutivo, que resuelven las fuentes con él; con "N1" caía en la
    # rama de compatibilidad de `_ambito` y devolvía otras cifras, sin avisar.
    assert d["nivel"] == "campo"          # el de la entidad, igual que N1D/N1DSER
    assert "nivel_entidad" not in d       # la clave huérfana no vuelve
```

---

## §4 · Orden de ejecución

Secuencial. Si un paso falla, **DETENERSE** y reportar.

| # | Paso | Detalle |
|---|---|---|
| 1 | Situarse | `cd 'C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend'` |
| 2 | Árbol limpio | `git status --short` desde `...\backend` — no debe haber nada sin commitear salvo, si acaso, el plan de esta tarea |
| 3 | **Línea base** | `uv run pytest tests\ -q` → **anotar** passed/failed ANTES de tocar nada |
| 4 | Cambio 1 (`respuesta_cuantificar.py`) | §3.1 |
| 5 | Cambio 2 (el test) | §3.2 |
| 6 | Validación | §6.1, V-1 → V-6, en orden |

---

## §5 · Reglas no negociables

1. **CERO cambios en el frontend.** Ni JS, ni plantillas, ni cache-buster. El frontend ya lee
   `datos.nivel`, que es justo lo que este plan arregla en origen.
2. **CERO cambios fuera de los 2 archivos de la §0.**
3. **No tocar** las ramas de N1DSER (`:187`), N1D/N1DSEL (`:214`), N2, N3, N4, NCMP ni N3P.
4. **No tocar** `_p50_del_mes` ni nada del P50 (H-06).
5. Código y comentarios **en español**, con la marca `[2026-09-08 · FIX-NIVEL-N1]`.
6. Copiar los bloques de la §3 **literalmente**, comentarios incluidos.
7. **Si algo no calza con el código real, DETENERSE y reportar.** Las 2 anclas se verificaron
   contra el archivo el 2026-09-08 y ambas son únicas.
8. **No hacer commit.** Al terminar, reportar archivos tocados y preguntar «¿Hago commit?».

---

## §6 · Validación

### 6.1 · Estática (la ejecuta el EXECUTOR)

Desde `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend`, línea por línea, PowerShell normal.

| # | Comando | Resultado esperado |
|---|---|---|
| V-1 | `uv run python -c "import app.features.consulta_v2.respuesta_cuantificar"` | Sin salida |
| V-2 | `Select-String -Path app\features\consulta_v2\respuesta_cuantificar.py -Pattern 'nivel_entidad' -CaseSensitive` | **0 líneas** — la clave huérfana desapareció del código |
| V-3 | `Select-String -Path app\features\consulta_v2\respuesta_cuantificar.py -Pattern '"nivel": res\["entidad"\]\["nivel"\]' -CaseSensitive` | **3 líneas** — N1DSER (`:187`), N1D/N1DSEL (`:214`) y ahora N1. **Antes del cambio son 2**: ese es el único conteo que distingue si el Cambio 1 se aplicó |
| V-4 | `uv run pytest tests\test_panel_n1_enriquecido.py -q` | **7 passed** |
| V-5 | `uv run pytest tests\ -q` | La **misma cifra** anotada en el paso 3 |
| V-6 | El comando de abajo (una línea) | `nivel = 'campo'` y `nivel_entidad = None`. Es la prueba de que el payload que sale hacia el frontend ya es el correcto — V-2 y V-3 solo cuentan líneas de texto |

**V-6**, desde `...\backend\backend`, en una sola línea:

```powershell
uv run python -c "from app.features.consulta_v2 import respuesta_cuantificar as rc; d = rc._panel_datos({'aplica':True,'nivel':'N1','entidad':{'nombre':'CASTILLA','nivel':'campo','fue_asumida':False},'entidad_cualificada':'el Campo CASTILLA','producto':'crudo','unidad':'kbopd','resultado':{'valor':55.0},'referencia_valor':52.1,'cumplimiento_pct':105.5,'estado':'Alineado','referencia':'PPTO','referencia_label':'presupuesto','mes':{'anio':2026,'mes':4,'nombre':'abril','dias_del_mes':30,'dias_con_data':30,'completo':True,'cerrado':True},'huella':{'registros':30,'dias_del_mes':30,'es_proyeccion':False},'avisos':[],'zoom':[]}); print('nivel =', repr(d.get('nivel'))); print('nivel_entidad =', repr(d.get('nivel_entidad')))"
```

⚠️ **Sobre V-5:** el repo tiene fallos **preexistentes** por datos que la BD local (congelada
en 2026-05-18) no tiene — la última línea base medida fue **55 failed, 850 passed, 1 skipped**.
Un fallo ahí no es necesariamente una regresión. Para distinguirlo: `git stash`, volver a
correr, comparar, `git stash pop` — desde `C:\APLICACIONES\ProdIA\Repo ProdIA\backend`, **no**
desde `Repo ProdIA`.

### 6.2 · Humana (la ejecuta el USUARIO, en el servidor de pruebas)

⚠️ **R3 · El executor NO puede marcar esto como verificado.** El estado correcto al terminar la
§6.1 es **«implementado, PENDIENTE de validación humana»**.

En `C:\APLICACIONES\ProdIA\Repo ProdIA\backend`:

```powershell
git pull origin main
```

Luego **reiniciar SOLO el backend** (`iniciar_backend.bat`). **No hace falta Ctrl+F5 ni tocar
el frontend**: no se cambió ni una línea de JS.

| # | Prueba | Resultado esperado |
|---|---|---|
| H-1 | «¿Cuánto produjo Castilla en abril?» | La tarjeta dice **55,0 kbopd** — la **misma cifra** que el texto de la respuesta. Hoy dice 94,7 |
| H-2 | La fila de referencia de esa tarjeta | Coherente con el PPTO del texto (**52,1**), no 90,0 |
| H-3 | La curva de esa respuesta | **Se pinta**, con los días de abril. Hoy dice «Sin curva diaria para este producto» |
| H-4 | «Muéstrame la producción de CRUDO día a día en CAMPO CHICHIMENE en AGOSTO 2026» | Igual que hoy — es un N1DSER y **no se tocó**. Es el control de no-regresión |
| H-5 | «¿Cuánto produjo Castilla el 15 de agosto?» | Igual que hoy — es un N1D, tampoco se tocó |
| H-6 | F12 → Console | **0 errores** |

**H-1 y H-3 son la corrección.** **H-4 y H-5 son el control**: si alguno cambia respecto a hoy,
el cambio se salió de su sitio.

---

## §7 · Fuera de alcance

- **«La VRO» no se resuelve como vicepresidencia.** Es la brecha de `jerarquias_sup_error.md` /
  `CLAUDE.md §6`, preexistente y ajena a este defecto. Mantiene **sin validar** la línea del
  P50 en la app. Tarea aparte.
- **La maqueta del artifact** (reproduce una tarjeta que no existe: fusionó
  `__cnTarjetasKpiHtml` con `__cnP50CardHtml`). Es trabajo de diseño, no de código.
- **El rótulo REAL/P50 del anillo**, el desglose de hijos y la curva del acumulado (N2): siguen
  fuera, como en el plan anterior.
- Cualquier cambio en el frontend, el clasificador, el drill, los goldens, la BD o el ETL.
