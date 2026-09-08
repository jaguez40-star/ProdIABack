# Plan — «¿Cuánto producimos hoy?» devuelve el panel del mes en curso

| | |
|---|---|
| **ID tarea** | `PRODUCCION-HOY-PANEL-MES` |
| **Fecha** | 2026-09-08 |
| **Versión** | **v2** — verificada contra el código con el flujo profesional (`CLAUDE.md` §10). La v1 tenía **una incoherencia que la dejaba sin efecto** y cinco más; están en §0.0 y corregidas aquí. |
| **Repos** | `ProdIABack` (backend). **El frontend NO se toca**: el panel `p50_cards` ya existe y ya está registrado (commit `ProdIAWebFront 9a97e8d`). |
| **Alcance** | Que «¿Cuánto producimos hoy?» y las formas que piden el mes en curso, **sin nombrar entidad**, respondan las cifras del mes por producto y pinten el panel de 5 tarjetas. |
| **NO se toca** | `patrones_grupo.yaml`. `slots.py`. El grano día con entidad. El ranking. `president()`. El runner `run_golden_cuantificar.py` ni su YAML. El frontend, entero. |

### Decisiones cerradas del usuario (el executor NO las revisa, las implementa)

1. **La respuesta es del MES, y el texto lo dice.** No se finge un dato diario: el reporte va ~100 días detrás del reloj (`slots.py:161-162`).
2. **El panel es el de 5 tarjetas** (Crudo · Gas · Blancos · Filiales · Total), el mismo del panorama y el que ya devuelve Analizar para el P50.
3. **Variantes: solo «hoy» y las que piden el mes explícitamente.** «¿Cómo vamos hoy?» y «¿cómo va la producción?» quedan FUERA: van a Analizar/`proyeccion` y no cambian.
4. **Solo sin entidad.** Con entidad («¿cuánto produjo Rubiales hoy?») todo sigue igual.

### ⚠️ Una desviación de lo aprobado, que el usuario decide (ver V-02)

El usuario aprobó «¿cuánto llevamos este mes?». Medido: esa frase **no lleva ninguna palabra de producción** y el filtro de dominio la manda a `desconocido` **por la regla del propio usuario** (`clasificacion_golden.yaml:75-76`: *«Meta debería estar acompañado del término producción»*). Meter «llevamos» en el vocabulario abriría la puerta a «¿cuántos pasos llevamos?». **Este plan no lo hace.** Las formas soportadas son las que nombran la producción: «¿cuánto producimos hoy?», «¿cuánto producimos este mes?», «¿cuánto llevamos **de producción** este mes?», «¿cuál es la producción del mes?». Si el usuario quiere «llevamos» a secas, es un cambio aparte y consciente.

---

## §0.0 Qué cambió de la v1 a la v2

| # | Incoherencia de la v1 | Consecuencia si se hubiera ejecutado | Corrección en v2 |
|---|---|---|---|
| 1 | 🔴 Daba por hecho que «¿cuánto producimos hoy?» llegaba a `responder()` | **No llega.** No está anclada, `detectar_entidad` da None y `nivel_dominio` da **None** (el vocabulario tiene `PRODUCCION` pero no `producimos`) → `maquina_q:478` la marca `desconocido`. **La rama nueva jamás se habría ejecutado.** Todo el plan sin efecto. | §3.1: se añaden las **formas verbales** de producir al vocabulario fuerte. Cero impacto medido en los 30 casos `desconocido` del golden. |
| 2 | 🔴 «¿cuánto llevamos este mes?» como caso positivo | Misma causa: sin palabra de producción → `desconocido`. Y arreglarlo exigiría un término genérico en el vocabulario. | Se declara la desviación (arriba) y se sustituye por «¿cuánto producimos este mes?». |
| 3 | 🔴 La guarda `not entidad` confiaba en `detectar_entidad` de `maquina_q` | Ese detector lee el catálogo cerrado (`_nombres()`); **el resolver de cuantificar es «quien decide de verdad»** (`maquina_q:591-592`) y consulta BD. Un campo que el detector no ve pero el resolver sí → «¿cuánto produjo <ese campo> hoy?» habría devuelto el **panorama global en silencio**. La familia de bug más peligrosa (`CLAUDE.md` §6). | §3.3: la rama también corre el resolver y exige `None`. Una consulta a BD, **solo** cuando el detector puro ya matcheó. |
| 4 | 🔴 Etiquetas `panorama_mes`/`ranking` en `cuantificar_golden.yaml` | El runner no las conoce: 5 de 32 fallan → **84%, rompe el gate ≥90%** para todos. | `cuantificar_golden.yaml` **no se toca**. La regresión va a un test pytest nuevo (corre en local, con dobles) y al golden de **clasificación** (que es donde vive el arreglo real). |
| 5 | 🟡 Duplicaba `_UNIDAD_PROD` y `_num_es` | `core/unidades.py` ya tiene `unidad_de()` y `fmt()` (con redondeo comercial). Dos gemelos que se desincronizan — la misma lección de H-03 del plan anterior. | Se importa `app.core.unidades`. |
| 6 | 🟡 Vocabulario más ancho que lo aprobado (`AHORA`, `ACTUALMENTE`, `VAMOS`, `VA`) | El usuario eligió solo «hoy» + formas del mes. `VAMOS`/`VA` además rozan «cómo vamos», que dejó fuera a propósito. | Solo `HOY` y las formas explícitas del mes. Verbo: `PRODUC\w*` y `LLEVAMOS DE PRODUCCION`. |
| 7 | 🟡 `_intro_global_mes` trataba `usuario` como objeto/dict | `usuario` es un **string** con el nombre (`_intro`, `:103`: `usuario or "el usuario"`). | Se clona ese uso. |

---

## §0. Contexto para el agente EXECUTOR

> El executor no tiene la conversación previa, ni el historial de git, ni memoria. Todo lo necesario está aquí.

### 0.1 Qué es ProdIA

Aplicación de producción de hidrocarburos de Ecopetrol. Dos procesos separados:

| | Frontend | Backend |
|---|---|---|
| Repo | `ProdIAWebFront` | `ProdIABack` |
| Raíz | `c:\APLICACIONES\ProdIA\Repo ProdIA\frontend\` | `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\` |
| Puerto | **5029** (Flask) | **5030** (FastAPI con `uv`) |

**Este plan toca SOLO el backend.**

### 0.2 El «Motor Q v2» — las tres puertas que una pregunta cruza

```
1. clasificar_capa1(texto)          patrones.py:44        regex → grupo
2. FILTRO DE DOMINIO                maquina_q.py:470-478  si el patrón NO es anclado:
      detectar_entidad(texto)  ──o──  nivel_dominio(texto)   ← vocabulario_dominio.yaml
      si ninguno → grupo = "desconocido"  (la pregunta MUERE aquí)
3. respuesta_cuantificar.responder() maquina_q.py:593     ← aquí se trabaja
```

**La puerta 2 es la que la v1 no vio.** `dominio.py:44-58` compila `config/vocabulario_dominio.yaml` en un regex `\b(a|b|…)\b` y devuelve `fuerte` | `estructural` | `None`. Es un módulo **puro** (sin BD ni LLM).

`maquina_q.py:593` llama `respuesta_cuantificar.responder(texto, entidad=…, usuario=…, conversation_id=…)`. `entidad` viene de `detectar_entidad` (catálogo cerrado, `:414`); `usuario` es un **string** con el nombre. `maquina_q` es agnóstico al tipo de panel.

### 0.3 Archivos que se tocan (rutas ABSOLUTAS)

| # | Archivo | Qué |
|---|---|---|
| A1 | `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\config\vocabulario_dominio.yaml` | +formas verbales de producir (fuerte) |
| A2 | `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\respuesta_cuantificar.py` | imports + detector + rama + formateador |
| A3 | `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\golden\clasificacion_golden.yaml` | +3 casos |
| A4 | `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\tests\test_cuantificar_panorama.py` | **NUEVO**, 6 tests con dobles |

**Cuatro archivos, un repo, un commit.**

### 0.4 Convenciones OBLIGATORIAS

- Python 3.12. Todo en **español**. Comentarios que explican **por qué**, con `[2026-09-08 · PRODUCCION-HOY-PANEL-MES]`.
- **No se toca el frontend.** Si crees que hace falta, has malinterpretado el plan (H-04).
- **No se toca `cuantificar_golden.yaml` ni su runner** (§0.0 #4).

### 0.5 Cómo correr las cosas (PowerShell, línea por línea, desde `backend\backend`)

```powershell
cd 'c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend'
$env:PYTHONPATH='.'; uv run python -m pytest tests/test_cuantificar_panorama.py -q
```

⚠️ Ni `run_golden_cuantificar.py` ni `run_golden.py` se corren en local (abren Postgres / pueden llamar al LLM). Sus casos se validan en pruebas (§6.2). En local se validan con las funciones **puras** (V-4, V-5).

---

## §1. Hallazgos de la auditoría (v1) — vigentes

### 🔴 H-01 — Hoy la pregunta falla en dos puntos distintos

Traza de `CUANTO PRODUCIMOS HOY`:
- Puerta 1: `clasificar_capa1` → `cuantificar` por `'CUANT[OA]S?\b'` (`patrones_grupo.yaml:131`). ✅
- Puerta 2: no anclado → `detectar_entidad` None → `nivel_dominio` **None** → **`desconocido`**. ❌ *(V-01)*
- Y si llegara a la puerta 3: `HOY` ∈ `_DIA_REL` (`slots.py:98`) → `menciona_dia` True → la pseudo-entidad GLOBAL (`respuesta_cuantificar.py:340`) **no se activa** → «No identifiqué una entidad». ❌

**→ Hay que abrir la puerta 2 (§3.1) Y añadir la rama en la 3 (§3.3).**

### 🔴 H-02 — «hoy» sin entidad NO es grano día. Es del mes.

El dato diario para «hoy» no existe (reporte ~100 días atrás). El dato que sí existe y responde la pregunta es el del **mes en curso**, el mismo del panorama. Por eso **no se tocan `_DIA_REL` ni `menciona_dia`**: «¿cuánto produjo Rubiales ayer?» sigue funcionando.

### 🟢 H-03 — `/analisis/president` es la fuente correcta

`analisis/api.py:2733`. Con `periodo=None` toma el **último reporte con REPORTE_PRESIDENT** por `fecha_reporte DESC` (`:2760-2764`). Sin `date.today()`: «hoy» = lo más reciente que hay, no el calendario. Devuelve los 3 productos + `totales` + `empresas`. Misma fuente del panorama → chat y tablero no pueden contradecirse.

### 🔴 H-04 — El frontend YA está listo

`multitab_shell.js:4402` registra `p50_cards` antes del fallback; `__cnP50CardsHtml` (`:6020`) compone las 5 tarjetas desde la respuesta cruda de `president`. **Se reutiliza el tipo. Cero cambios en el front, sin cache-buster.**

### 🔴 H-05 — `president` es endpoint FastAPI: `periodo=` SIEMPRE explícito

`respuesta_analizar.py:369-371`: un default `Query(...)` sobreviviente llega al SQL y revienta.

### 🟡 H-06 — La rama va ANTES del ranking, con guarda explícita

`_ranking.detectar` (`:264`) no matchea «cuánto producimos hoy», así que el orden inverso también funcionaría — por casualidad. `_RX_NO_GLOBAL` deja «¿cuáles campos produjeron más hoy?» fuera **por contrato**.

---

## §1-bis. Hallazgos de la VERIFICACIÓN (v2)

### 🔴 V-01 — La pregunta principal muere en el filtro de dominio. La v1 no lo vio.

Medido con las funciones puras:

| Frase | `clasificar_capa1` | anclado | `nivel_dominio` | Llega a `responder()` |
|---|---|---|---|---|
| ¿cuánto producimos hoy? | cuantificar | No | **None** | ❌ `desconocido` |
| ¿cuánto llevamos este mes? | cuantificar | No | **None** | ❌ `desconocido` |
| ¿cuál es la producción del mes? | cuantificar | **Sí** (`PRODUCCION\s+DE`) | fuerte | ✅ |
| ¿cuánto produjimos este mes? | cuantificar | No | **None** | ❌ |

`vocabulario_dominio.yaml:26-50` tiene `PRODUCCION`, `CRUDO`, `BARRILES?`… **pero ninguna forma verbal de producir.** En un sistema cuyo único tema es la producción, «producimos» es tan inequívoco como «producción».

Impacto medido de añadirlas: de los **30** casos `esperado: desconocido` del golden de clasificación, **ninguno** contiene `produc*` (grep). Los dos con «hoy» (`:138` «¿cuánto vale un barril de petróleo hoy?», `:205` «…cierre de la bolsa hoy?») no cambian: no llevan el verbo. **Cero regresiones por construcción.**

**→ §3.1.**

### 🔴 V-02 — «llevamos» a secas es fuera de dominio por la regla del usuario

`clasificacion_golden.yaml:73-78` fija «¿Cuánto nos falta para la meta?» → `desconocido`, con la regla del usuario escrita: *«Meta debería estar acompañado del término producción»*. «¿Cuánto llevamos este mes?» es el mismo caso: ¿llevamos de qué? Añadir `LLEVAMOS` al vocabulario dejaría entrar «¿cuántos pasos llevamos?» (`:203` fija esa familia como `desconocido`).

**→ No se añade. Se documenta como caso negativo en el golden (§3.4) y se declara la desviación arriba.**

### 🔴 V-03 — La guarda `not entidad` era insuficiente

`maquina_q.py:589-592`: *«`entidad` = lo que el backstop de catálogo ya detectó (`detectar_entidad`); el resolver propio de cuantificar (D-D5) es quien decide de verdad.»* `detectar_entidad` (`:414`) lee `_nombres()` (catálogo cerrado); el resolver (`resolver.py:38`) consulta **BD**. `CLAUDE.md` §6 documenta que conviven tres catálogos y el más pobre falla en 20 de 24 gerencias.

Escenario: «¿cuánto produjo <entidad que el backstop no ve> hoy?» → `entidad=None` → detector puro True → **panorama global**, respondiendo otra cosa con seguridad.

**→ §3.3: la rama corre `_resolver_con_contexto(texto, texto)` y exige `None`.** Es exactamente lo que hace la ruta GLOBAL existente (`:329` + `:340`). Cuesta una consulta, **solo** cuando el detector puro ya dio True.

### 🔴 V-04 — Las etiquetas nuevas rompían el gate del golden de cuantificar

`run_golden_cuantificar.py:11-24` `_clasificar_resultado` solo produce `sin_entidad | ambiguo | rechazo_* | aplica`. `panorama_mes` y `ranking` nunca igualarían → 5 fallos de 32 → **84% < 90%**. Y ese runner ni siquiera pasa por `responder()`: no puede medir el panorama.

**→ `cuantificar_golden.yaml` no se toca.** La regresión del panorama va a **pytest con dobles** (§3.5, corre en local). La del filtro de dominio va al **golden de clasificación** (§3.4), que es donde vive el arreglo real.

### 🟡 V-05 — `core/unidades.py` ya tiene lo que la v1 duplicaba

`unidades.py:36 unidad_de(producto)` y `:79 fmt(n, dec=1)` (redondeo comercial `ROUND_HALF_UP`, es-CO). Precedente de import en `p50_referencia.py:25`. **→ §3.2.**

### 🟡 V-06 — `usuario` es un string

`respuesta_cuantificar.py:103` y `respuesta_analizar.py:141`: `usuario or "el usuario"` dentro de un prompt. **→ §3.2 `_intro_global_mes`.**

### 🟢 V-07 — Ningún test llama a `responder()` de cuantificar directamente

Grep en `tests/`: cero. Añadir `_president_fn=None` a la firma no rompe nada. Los dobles del resolver se hacen como en `test_p50_referencia.py:162` (`monkeypatch.setattr(_ra._resolver, "resolver_unico", …)`), y `_resolver_con_contexto` (`:68-76`) ya tolera lambdas de un argumento.

### 🟢 V-08 — El clasificador de grupos no se toca

`'CUANT[OA]S?\b'` ya la manda a cuantificar. El vocabulario de dominio es **otro archivo** con otro contrato: no altera la etapa A.

---

## §2. Estado actual

| Pregunta | Puerta 2 | Puerta 3 | Resultado hoy |
|---|---|---|---|
| ¿Cuánto producimos hoy? | ❌ desconocido | — | «No logré entender tu pregunta» |
| ¿Cuánto llevamos este mes? | ❌ desconocido | — | ídem — **y así se queda** (V-02) |
| ¿Cuál es la producción del mes? | ✅ | GLOBAL, N1 | KPI de **crudo solo**, panel `cuant_kpi` |
| ¿Cuánto produjo Rubiales hoy? | ✅ (entidad) | N1D | Rechazo honesto por techo — **no se toca** |
| ¿Cuáles campos produjeron más hoy? | ✅ | ranking | Ranking — **no se toca** |

---

## §3. Especificación

> **LOCALIZAR** es texto literal verificado con grep. Si no aparece **exactamente**, **DETENERSE y reportar**.

### §3.1 — MODIFICAR `vocabulario_dominio.yaml`: formas verbales de producir

**Archivo A1.** Justificación: V-01.

**LOCALIZAR** (`:52-56`, cierre de la lista `vocabulario` — verificado con `grep -F`):
```yaml
  - PETROLEO
  - FALTANTE

# --- ESTRUCTURAL: entidades del modelo, pero también español común -> exigen Capa 2 ---------
estructural:
```

**SUSTITUIR POR:**
```yaml
  - PETROLEO
  - FALTANTE
  # [2026-09-08 · PRODUCCION-HOY-PANEL-MES] La lista tenía el SUSTANTIVO (PRODUCCION) pero
  # ninguna forma del VERBO. Medido: «¿cuánto producimos hoy?» —la pregunta más natural del
  # sistema— atrapaba por CUANTO (no anclado), no traía entidad, nivel_dominio daba None y
  # maquina_q la marcaba desconocido: «No logré entender tu pregunta». En un sistema cuyo
  # único tema es la producción, "producimos" es tan inequívoco como "producción".
  # 🔑 Conjugaciones EXPLÍCITAS, no PRODUC\w*: PRODUCTO/PRODUCTOR entrarían y esos sí tienen
  #    español común fuera del dominio. Verificado: ninguno de los 30 casos `desconocido` del
  #    golden de clasificación contiene una forma verbal de producir.
  - PRODUC(?:E|EN|IMOS|IENDO|ID[OA]S?|IR|IA|IAN)
  - PRODUJ(?:O|ERON|IMOS)

# --- ESTRUCTURAL: entidades del modelo, pero también español común -> exigen Capa 2 ---------
estructural:
```

⚠️ Las entradas son **fragmentos de regex** que `dominio.py:28` une con `|` dentro de `\b(…)\b` (`BARRILES?` ya usa esa sintaxis). Los grupos van con `(?:…)` para no crear grupos de captura.

---

### §3.2 — MODIFICAR `respuesta_cuantificar.py`: imports, detector, formateador

**Archivo A2.** Justificación: V-05, V-06, H-06.

🔴 **Medido: ni `re` ni `norm` están importados en este archivo.** Se añaden clonando `ranking.py:27,32` y `respuesta_analizar.py:18,23`.

**LOCALIZAR** (`:17-28`):
```python
from app.core.config import get_settings
from app.features.consulta_v2 import respuesta_base
from app.features.consulta_v2.cuantificar import catalogo as _catalogo
from app.features.consulta_v2.cuantificar import resolver as _resolver
from app.features.consulta_v2.cuantificar import slots as _slots
# [2026-08-26] Import a nivel de módulo: `menciona_dia` ya no se usa solo para el techo —
# decide también si una pregunta SIN entidad puede resolverse como global (el grano día no).
from app.features.consulta_v2.cuantificar.slots import menciona_dia as _menciona_dia
from app.features.consulta_v2.cuantificar import ejecutor as _ejecutor
from app.features.consulta_v2.cuantificar import validador as _validador
from app.features.consulta_v2.cuantificar import ranking as _ranking
from app.features.consulta_v2 import no_soportado as _no_soportado
```

**SUSTITUIR POR:**
```python
import re

from app.core.config import get_settings
from app.core import unidades as _u
from app.features.consulta_v2 import respuesta_base
from app.features.consulta_v2.normaliza import norm
from app.features.consulta_v2.cuantificar import catalogo as _catalogo
from app.features.consulta_v2.cuantificar import resolver as _resolver
from app.features.consulta_v2.cuantificar import slots as _slots
# [2026-08-26] Import a nivel de módulo: `menciona_dia` ya no se usa solo para el techo —
# decide también si una pregunta SIN entidad puede resolverse como global (el grano día no).
from app.features.consulta_v2.cuantificar.slots import menciona_dia as _menciona_dia
from app.features.consulta_v2.cuantificar import ejecutor as _ejecutor
from app.features.consulta_v2.cuantificar import validador as _validador
from app.features.consulta_v2.cuantificar import ranking as _ranking
from app.features.consulta_v2 import no_soportado as _no_soportado
# [2026-09-08 · PRODUCCION-HOY-PANEL-MES] El panorama corporativo por producto sale de
# REPORTE_PRESIDENT, no del fact diario: es la MISMA fuente que pinta el tablero, así que el
# chat y el panorama no pueden contradecirse. Se importa el endpoint, igual que
# respuesta_analizar.py:35 — no se replica su SQL.
from app.features.analisis.api import president as _president_ep
```

**LOCALIZAR** (`:255-258`):
```python
    return f if f in _FORMAS_RECHAZO_RANKING else None


def responder(texto: str, entidad: str | None = None, usuario=None, conversation_id=None):
```

**SUSTITUIR POR:**
```python
    return f if f in _FORMAS_RECHAZO_RANKING else None


# ── [2026-09-08 · PRODUCCION-HOY-PANEL-MES] Panorama corporativo del mes en curso ─────────────
# «¿Cuánto producimos hoy?» moría dos veces: (1) en el filtro de dominio, porque el vocabulario
# no tenía el verbo (arreglado en vocabulario_dominio.yaml); (2) aquí, porque "hoy" dispara
# _DIA_REL (slots.py:98) -> menciona_dia True -> la pseudo-entidad GLOBAL de :340 NO se activa
# -> «No identifiqué una entidad». Y aunque se activara no habría dato: el reporte diario va
# ~100 días detrás del reloj (slots.py:161-162).
# 🔑 La respuesta correcta es la del MES EN CURSO, y el texto lo DICE. No se finge un dato
#    diario: se sirve el que existe y se rotula. Es lo mismo que muestra el panorama.
# 🔑 NO se tocan _DIA_REL ni menciona_dia: «¿cuánto produjo Rubiales ayer?» sigue siendo grano
#    día y sigue funcionando. Esta rama solo actúa SIN entidad (guarda doble en `responder`).
_RX_HOY = re.compile(r"\bHOY\b")
# Formas EXPLÍCITAS del mes en curso. El mes NOMBRADO ("en abril") no entra: tiene su ruta.
_RX_MES_CURSO = re.compile(
    r"\b(?:ESTE\s+MES|DEL\s+MES|EN\s+EL\s+MES|MES\s+EN\s+CURSO|MES\s+ACTUAL|EN\s+LO\s+QUE\s+VA\s+DEL\s+MES)\b")
# Debe nombrar la PRODUCCIÓN. «¿cuánto llevamos este mes?» a secas no la nombra y es fuera de
# dominio por la regla del usuario (clasificacion_golden.yaml:75-76: "meta debería estar
# acompañado del término producción") — aquí se aplica el mismo criterio. Sin VAMOS/VA:
# «cómo vamos» es de Analizar/proyeccion y el usuario la dejó fuera a propósito.
# 🔑 PRODU[CJ]: el pretérito cambia la raíz (produJimos, produJo). Medido: con PRODUC\w* a
#    secas, «¿cuánto produjimos este mes?» daba False.
_RX_VERBO_PROD = re.compile(r"\bPRODU[CJ]\w*\b|\bLLEVAMOS\s+DE\s+PRODUCCION\b")
# 🔑 GUARDA: lo que NUNCA cae aquí aunque traiga "hoy".
#    · sustantivo de nivel  -> la pregunta es POR ENTIDADES (ranking o grano día), no global
#    · superlativo          -> RANKING (N5), su fork vive justo debajo
#    · reporte/cobertura    -> huella de datos, otra pregunta
_RX_NO_GLOBAL = re.compile(
    r"\b(?:CAMPOS?|POZOS?|ACTIVOS?|GERENCIAS?|VICEPRESIDENCIAS?|VP|FILIALES?|OPERADORES?)\b"
    r"|\b(?:MAS|MENOS|MAYOR|MENOR|MAYORES|MENORES|TOP|RANKING|MEJOR|PEOR|PRIMEROS?|ULTIMOS?)\b"
    r"|\b(?:DIAS?|REPORTES?|COBERTURA|HUELLA)\b")


def _pide_mes_en_curso(texto: str) -> bool:
    """¿Pide el panorama corporativo del mes en curso? PURA: sin BD, sin LLM.

    True solo si: (nombra la producción) Y ("hoy" O forma explícita del mes) Y NINGUNA señal de
    entidad/ranking/cobertura. Estricta a propósito: corta ANTES del ranking y del resolver, así
    que un falso positivo se lleva por delante una pregunta que hoy se responde bien.
    """
    t = norm(texto or "")
    if _RX_NO_GLOBAL.search(t):
        return False
    if not _RX_VERBO_PROD.search(t):
        return False
    return bool(_RX_HOY.search(t) or _RX_MES_CURSO.search(t))


_CIERRE_MES_CURSO = "¿Quieres el detalle de un producto, o la comparación contra el P50?"


def _cuerpo_mes_en_curso(info: dict) -> str:
    """Cifras del MES EN CURSO por producto, desde /analisis/president. PURA.

    🔑 Rotula el periodo y el corte SIEMPRE. La pregunta dice "hoy" y la respuesta es del mes:
    callar esa diferencia sería el fallo silencioso que este plan corrige.
    🔑 Unidades y formato salen de core/unidades (unidad_de, fmt): el gas va en barriles
    equivalentes y los blancos en líquidos; duplicar ese mapa aquí sería un gemelo más.
    """
    corte = info.get("corte")
    lineas = ["📊 Ecopetrol · producción del mes en curso" + (f" · corte {corte}" if corte else ""),
              ""]
    for p in info.get("productos", []):
        nombre = str(p.get("entidad", ""))
        real = p.get("real_mes")
        if real is None:
            continue
        linea = f"{nombre}: {_u.fmt(real)} {_u.unidad_de(nombre)}"
        if p.get("cumpl_p50") is not None:
            linea += f" · {_u.fmt(p['cumpl_p50'])}% del P50"
        lineas.append(linea)
    # El total nacional (Ecopetrol + filiales) cierra el cuadro: es la cifra de arriba de la
    # lámina gerencial y la primera que el usuario compara.
    emp = info.get("empresas") or {}
    if emp.get("nacional") is not None:
        tot = f"\nTotal nacional: {_u.fmt(emp['nacional'])} {_u.UNIDAD}"
        try:
            if emp.get("p50"):
                tot += f" · {_u.fmt(100.0 * float(emp['nacional']) / float(emp['p50']))}% del P50"
        except (TypeError, ValueError, ZeroDivisionError):
            pass
        lineas.append(tot)
    return "\n".join(lineas)


def _intro_global_mes(usuario) -> str:
    """Intro fijo, sin LLM y sin cifras (REGLA CERO: el cuerpo las lleva todas).

    `usuario` es el NOMBRE (string), igual que en _intro (:103, `usuario or "el usuario"`). Esta
    rama corta antes del ejecutor y no tiene un `res` que describir; un intro fijo evita un
    round-trip de LLM en la pregunta más frecuente del sistema.
    """
    nombre = str(usuario).strip() if usuario else ""
    return (f"Con gusto, {nombre}: " if nombre else "Con gusto: ") + "así va la producción del mes en curso."


def responder(texto: str, entidad: str | None = None, usuario=None, conversation_id=None,
              _president_fn=None):
```

---

### §3.3 — MODIFICAR `responder()`: la rama, ANTES del ranking, con guarda doble

**Archivo A2.** Justificación: H-01, V-03, H-05, H-06.

**LOCALIZAR** (`:259-264` tras el paso anterior — el docstring y el arranque del ranking):
```python
    """1c/1d: resuelve → cifra (ejecutor) → intro cálido + cuerpo VERBATIM + cierre (mensaje) + panel
    KPI (o None). Devuelve SIEMPRE {mensaje, panel} — nunca None."""
    # ── N5 RANKING (eje ortogonal) ────────────────────────────────────────────────────────────
    # Va ANTES del resolver: el ranking global NO tiene entidad de entrada (la entidad es la
    # RESPUESTA) y moriría en la guarda "no identifiqué una entidad".
    rk = _ranking.detectar(texto)
```

**SUSTITUIR POR:**
```python
    """1c/1d: resuelve → cifra (ejecutor) → intro cálido + cuerpo VERBATIM + cierre (mensaje) + panel
    KPI (o None). Devuelve SIEMPRE {mensaje, panel} — nunca None.

    `_president_fn`: inyección para pruebas (mismo patrón que respuesta_analizar._responder_core).
    Ningún llamador de producción lo pasa.
    """
    # ── [2026-09-08 · PRODUCCION-HOY-PANEL-MES] PANORAMA DEL MES EN CURSO ─────────────────────
    # Va ANTES del ranking y del resolver, y por ese orden exacto:
    #  🔑 Antes del RESOLVER porque la pregunta no nombra entidad — moriría en la guarda «no
    #     identifiqué una entidad» de :342, que es justo el bug que esto corrige.
    #  🔑 Antes del RANKING por diseño, no por necesidad: _ranking.detectar no matchea «cuánto
    #     producimos hoy», así que el orden inverso también andaría — por casualidad. La guarda
    #     _RX_NO_GLOBAL deja «¿cuáles campos produjeron más hoy?» fuera por contrato.
    #  🔑 GUARDA DOBLE. `entidad` viene del backstop de maquina_q (detectar_entidad, catálogo
    #     cerrado) y NO es quien decide: «el resolver propio de cuantificar (D-D5) es quien
    #     decide de verdad» (maquina_q.py:591). Conviven tres catálogos (CLAUDE.md §6) y el del
    #     backstop es el más pobre: un campo que él no ve y el resolver sí habría convertido
    #     «¿cuánto produjo <ese campo> hoy?» en el panorama GLOBAL, respondiendo otra cosa con
    #     seguridad. Por eso se consulta también el resolver — una llamada a BD, SOLO cuando el
    #     detector puro ya dio True (nunca en la ruta caliente). Es lo mismo que hace la ruta
    #     GLOBAL existente (:329 + :340).
    if not entidad and _pide_mes_en_curso(texto) and _resolver_con_contexto(texto, texto) is None:
        president_fn = _president_fn or _president_ep
        # `periodo=` EXPLÍCITO: president es un endpoint FastAPI y su default es un objeto
        # Query(...) que, si sobrevive, llega al SQL y revienta con "cannot adapt type 'Query'"
        # (mismo patrón advertido en respuesta_analizar.py:369-371).
        info = president_fn(periodo=None)
        if info.get("encontrada") and info.get("productos"):
            mensaje = respuesta_base.envolver(_intro_global_mes(usuario),
                                              _cuerpo_mes_en_curso(info), _CIERRE_MES_CURSO)
            # Panel PURO: `info` es la respuesta cruda de /analisis/president, exactamente el
            # contrato que el front ya consume para "p50_cards" (multitab_shell.js:4402, commit
            # ProdIAWebFront 9a97e8d). Se REUSA el tipo: cero cambios en el frontend.
            return {"mensaje": mensaje, "panel": {"tipo": "p50_cards", "datos": info}}
        # Sin reporte cargado no se inventa nada ni se cae al flujo normal (que respondería
        # otra cosa): se dice lo que pasa.
        return {"mensaje": ("No tengo el panorama de producción del mes en curso: falta ingerir "
                            "el REPORTE_PRESIDENT en este entorno."), "panel": None}

    # ── N5 RANKING (eje ortogonal) ────────────────────────────────────────────────────────────
    # Va ANTES del resolver: el ranking global NO tiene entidad de entrada (la entidad es la
    # RESPUESTA) y moriría en la guarda "no identifiqué una entidad".
    rk = _ranking.detectar(texto)
```

---

### §3.4 — MODIFICAR `clasificacion_golden.yaml`: +3 casos

**Archivo A3.** Justificación: V-01, V-02. Es donde vive el arreglo real (vocabulario).

**AÑADIR AL FINAL del archivo** (no se sustituye nada; confirma antes las últimas 3 líneas con `Get-Content … -Tail 3` y repórtalas):
```yaml

# ---- Panorama del mes en curso (2026-09-08 · PRODUCCION-HOY-PANEL-MES) ----
# «¿Cuánto producimos hoy?» caía en desconocido por 'regex+filtro': CUANTO la atrapaba, no
# traía entidad y el vocabulario tenía PRODUCCION pero ninguna forma del VERBO. Se añadieron
# las conjugaciones a vocabulario_dominio.yaml. Estos dos fijan que el verbo basta.
- pregunta: "¿Cuánto producimos hoy?"
  esperado: cuantificar
- pregunta: "¿Cuánto produjimos este mes?"
  esperado: cuantificar
# NEGATIVO — y regla del usuario (ver «meta» en :75-76): sin nombrar la producción, "llevamos"
# no dice de qué. Meterlo al vocabulario abriría «¿cuántos pasos llevamos?». Sigue fuera.
- pregunta: "¿Cuánto llevamos este mes?"
  esperado: desconocido
```

---

### §3.5 — CREAR `tests/test_cuantificar_panorama.py`

**Archivo A4, NUEVO.** Justificación: V-04 (el runner del golden no puede medir el panorama; pytest sí, en local, con dobles). Clona el patrón de `test_p50_referencia.py:162` para el resolver.

**CONTENIDO COMPLETO:**
```python
"""Panorama del mes en curso (2026-09-08 · PRODUCCION-HOY-PANEL-MES).

«¿Cuánto producimos hoy?» -> las cifras del MES por producto + panel "p50_cards". Sin BD ni LLM:
el resolver y `president` se sustituyen por dobles, igual que en test_p50_referencia.py.
Fija también lo que NO debe cambiar: con entidad, con ranking y con mes nombrado, la rama
nueva no se activa.
"""
import pytest

from app.features.consulta_v2 import respuesta_cuantificar as _rc

_INFO = {
    "encontrada": True, "unidad": "kbepd", "corte": "2026-09-05",
    "productos": [{"entidad": "Crudo", "real_mes": 502.3, "cumpl_p50": 96.5},
                  {"entidad": "Gas", "real_mes": 80.5, "cumpl_p50": 106.6},
                  {"entidad": "Blancos", "real_mes": 8.4, "cumpl_p50": 55.4}],
    "totales": [{"entidad": "Ecopetrol", "real_mes": 591.3}],
    "empresas": {"nacional": 717.8, "p50": 735.0, "filiales": 126.5},
}


@pytest.fixture
def sin_entidad(monkeypatch):
    """El resolver no encuentra nada (la pregunta no nombra entidad)."""
    monkeypatch.setattr(_rc._resolver, "resolver_unico", lambda *a, **k: None)


def test_detector_positivos():
    assert _rc._pide_mes_en_curso("¿cuánto producimos hoy?")
    assert _rc._pide_mes_en_curso("¿cuánto produjimos este mes?")
    assert _rc._pide_mes_en_curso("¿cuál es la producción del mes?")
    assert _rc._pide_mes_en_curso("¿cuánto llevamos de producción este mes?")


def test_detector_negativos():
    assert not _rc._pide_mes_en_curso("¿cuáles campos produjeron más hoy?")   # ranking
    assert not _rc._pide_mes_en_curso("¿cuánto produjeron los campos este mes?")  # por entidades
    assert not _rc._pide_mes_en_curso("¿cuánto produjimos en abril?")          # mes nombrado
    assert not _rc._pide_mes_en_curso("¿cuánto llevamos este mes?")            # sin producción
    assert not _rc._pide_mes_en_curso("¿cuántos días con reporte llevamos de producción este mes?")


def test_panorama_texto_y_panel(sin_entidad):
    llamadas = []

    def fake(periodo=None):
        llamadas.append(periodo)
        return _INFO

    r = _rc.responder("¿cuánto producimos hoy?", _president_fn=fake)
    assert llamadas == [None]                       # periodo explícito, nunca Query(...)
    assert r["panel"]["tipo"] == "p50_cards"
    assert r["panel"]["datos"] is _INFO             # respuesta cruda, sin transformar
    m = r["mensaje"]
    assert "producción del mes en curso" in m       # rotula que es del MES
    assert "corte 2026-09-05" in m
    assert "Crudo: 502,3 kbopd" in m
    assert "Gas: 80,5 kbepd" in m
    assert "Blancos: 8,4 kblpd" in m
    assert "Total nacional: 717,8 kbepd" in m


def test_panorama_sin_reporte(sin_entidad):
    r = _rc.responder("¿cuánto producimos hoy?",
                      _president_fn=lambda periodo=None: {"encontrada": False})
    assert r["panel"] is None
    assert "REPORTE_PRESIDENT" in r["mensaje"]      # honesto: dice qué falta, no otra cifra


class _Cortado(Exception):
    """Centinela: se lanza desde el ranking para probar que la rama nueva se SALTÓ sin seguir
    hacia el ejecutor (que desde ahí tocaría BD por el techo del día)."""


@pytest.fixture
def corta_en_ranking(monkeypatch):
    def _boom(texto):
        raise _Cortado()
    monkeypatch.setattr(_rc._ranking, "detectar", _boom)


def test_resolver_ve_entidad_aunque_backstop_no(monkeypatch, corta_en_ranking):
    """Guarda doble (V-03): `entidad` viene None del backstop, pero el resolver SÍ la ve -> NO es
    el panorama global. Debe seguir al flujo normal (aquí, cortado en el ranking) sin llamar a
    president."""
    monkeypatch.setattr(_rc._resolver, "resolver_unico",
                        lambda *a, **k: {"valor": "RUBIALES", "nivel": "campo", "rama": "A", "zoom": []})
    llamado = []
    with pytest.raises(_Cortado):
        _rc.responder("¿cuánto produjo Rubiales hoy?",
                      _president_fn=lambda periodo=None: llamado.append(1) or _INFO)
    assert llamado == []


def test_entidad_del_backstop_no_entra(sin_entidad, corta_en_ranking):
    """Con `entidad` informada por maquina_q la rama ni se evalúa: sigue al flujo normal."""
    llamado = []
    with pytest.raises(_Cortado):
        _rc.responder("¿cuánto produjo Castilla hoy?", entidad="CASTILLA",
                      _president_fn=lambda periodo=None: llamado.append(1) or _INFO)
    assert llamado == []
```

---

## §4. Orden de ejecución

| Paso | § | Archivo | Acción | Verificación inmediata |
|---|---|---|---|---|
| 0 | — | — | **Línea base** V-1 | anotar passed/failed |
| 1 | 3.1 | `vocabulario_dominio.yaml` | +2 fragmentos | V-4 |
| 2 | 3.2 | `respuesta_cuantificar.py` | imports | V-2, V-3 |
| 3 | 3.2 | `respuesta_cuantificar.py` | detector + formateador + intro + firma nueva de `responder` | V-5 |
| 4 | 3.3 | `respuesta_cuantificar.py` | rama con guarda doble, ANTES del ranking | V-6 |
| 5 | 3.4 | `clasificacion_golden.yaml` | +3 casos al final | V-7 |
| 6 | 3.5 | `tests/test_cuantificar_panorama.py` | crear | V-8 |
| 7 | — | — | **§6.1 completa** | todo verde |

**Un repo (`ProdIABack`), un commit.**

---

## §5. Reglas no negociables

1. **Ancla que no aparece exactamente → DETENTE** y reporta ancla, archivo y lo hallado.
2. **Español** en todo.
3. **CERO cambios fuera de lo especificado.**
4. **Frontend, `patrones_grupo.yaml`, `slots.py`, `cuantificar_golden.yaml` y su runner: NO se tocan.**
5. **La rama va ANTES de `rk = _ranking.detectar(texto)`** y con las **tres** condiciones (`not entidad`, detector, resolver `None`).
6. **`periodo=` explícito** en `president_fn`.
7. **Unidades y formato solo de `app.core.unidades`.** Nada de diccionarios ni formateadores propios.
8. **No corras `run_golden.py` ni `run_golden_cuantificar.py` en local.**
9. **Estado final: «implementado, PENDIENTE de validación humana».** Nunca «verificado».

---

## §6. Validación

### 6.1 Estática — la ejecuta el EXECUTOR (desde `backend\backend`, línea por línea)

| # | Qué | Comando | Esperado |
|---|---|---|---|
| **V-1** | Línea base | `uv run python -m pytest tests/test_cuantificar.py tests/test_cuantificar_dia.py tests/test_cuantificar_ranking.py -q` | Anotar passed/failed |
| **V-2** | `re` importado | `Select-String -Path app\features\consulta_v2\respuesta_cuantificar.py -Pattern "^import re$"` | 1 resultado |
| **V-3** | `norm` y `unidades` importados | `Select-String -Path app\features\consulta_v2\respuesta_cuantificar.py -Pattern "normaliza import norm\|from app.core import unidades as _u"` | 2 resultados |
| **V-4** | 🔴 El filtro de dominio deja pasar el verbo, y solo el verbo | `$env:PYTHONPATH='.'; uv run python -c "from app.features.consulta_v2.dominio import nivel_dominio as f; print([f(x) for x in ['cuanto producimos hoy','cuanto produjimos este mes','cuanto llevamos este mes','cual es el producto mas vendido','cuantos pasos llevamos']])"` | `['fuerte', 'fuerte', None, None, None]` |
| **V-5** | 🔴 Detector puro, 9 casos | `$env:PYTHONPATH='.'; uv run python -c "from app.features.consulta_v2.respuesta_cuantificar import _pide_mes_en_curso as f; print([f(x) for x in ['cuanto producimos hoy','cuanto produjimos este mes','cual es la produccion del mes','cuanto llevamos de produccion este mes','cuales campos produjeron mas hoy','cuanto produjeron los campos este mes','cuanto produjimos en abril','cuanto llevamos este mes','como vamos hoy']])"` | `[True, True, True, True, False, False, False, False, False]` |
| **V-6** | Rama antes del ranking | `Select-String -Path app\features\consulta_v2\respuesta_cuantificar.py -Pattern "_pide_mes_en_curso\(texto\)\|rk = _ranking.detectar" \| Select-Object LineNumber` | La primera línea es menor que la segunda |
| **V-7** | Golden de clasificación válido y con los 3 casos | `uv run python -c "import yaml;c=yaml.safe_load(open('app/features/consulta_v2/golden/clasificacion_golden.yaml',encoding='utf-8'));print(len(c),'casos');print([x['esperado'] for x in c[-3:]])"` | N+3 casos y `['cuantificar', 'cuantificar', 'desconocido']` |
| **V-8** | 🔴 Los tests nuevos | `$env:PYTHONPATH='.'; uv run python -m pytest tests/test_cuantificar_panorama.py -q` | **6 passed** |
| **V-9** | Sin regresión | mismo comando de V-1 | Mismo número de passed que V-1 |
| **V-10** | 🔴 Golden de clasificación NO regresa, medido en puro | Ver bloque abajo | `desconocido antes: 30 · después: 30 · cambiados: []` |
| **V-11** | Frontend intacto | `git -C ..\..\frontend status --short` | Sin salida |

**Comando de V-10** (una línea): recorre los casos `desconocido` del golden y comprueba que `nivel_dominio` sigue siendo `None` para todos tras el cambio de vocabulario.
```powershell
$env:PYTHONPATH='.'; uv run python -c "import yaml;from app.features.consulta_v2.dominio import nivel_dominio as f;c=yaml.safe_load(open('app/features/consulta_v2/golden/clasificacion_golden.yaml',encoding='utf-8'));d=[x for x in c if x.get('esperado')=='desconocido'];cam=[x['pregunta'] for x in d if f(x['pregunta']) is not None];print('desconocido:',len(d),'· con dominio ahora:',cam)"
```
Esperado: la lista `con dominio ahora` contiene **solo** casos que ya tenían palabra de dominio antes (petróleo, cierre, meta de producción…) — es decir, **ninguno con una forma verbal de producir**. Si aparece uno con `produc*`, DETENTE.

### 6.2 Humana — la valida el USUARIO, en el servidor de PRUEBAS

En `http://localhost:5029`. Sin Ctrl+F5: el JS no cambió. **Reiniciar el backend** (el vocabulario se compila una vez, `dominio.py:5`).

| # | Acción | Esperado |
|---|---|---|
| H-1 | «¿Cuánto producimos hoy?» | Texto **«producción del mes en curso»** con corte, cifras de Crudo/Gas/Blancos con sus unidades |
| H-2 | Misma pregunta | Panel de **5 tarjetas**, idéntico al del panorama |
| H-3 | Comparar con el panorama (mes en curso) | Cifras **idénticas** |
| H-4 | «¿Cuánto produjimos este mes?» | Igual que H-1 |
| H-5 | «¿Cuál es la producción del mes?» | Igual que H-1 (antes: solo crudo) |
| H-6 | «¿Cuánto llevamos este mes?» | **«No logré entender…»**, como hasta ahora (V-02). Si el usuario lo quiere distinto, es otra decisión |
| H-7 | «¿Cuánto produjo Rubiales hoy?» | Rechazo honesto por techo, como hasta ahora |
| H-8 | «¿Cuáles campos produjeron más hoy?» | Ranking, como hasta ahora |
| H-9 | «¿Cuánto produjimos en abril?» | Cifra de abril, como hasta ahora |
| H-10 | F12 → Console | 0 errores |
| H-11 | Golden de clasificación | `$env:PYTHONPATH='.'; uv run python app/features/consulta_v2/golden/run_golden.py` — ≥90% y los 3 casos nuevos OK |

---

## §7. Fuera de alcance

1. **«¿Cuánto llevamos este mes?» a secas** sigue fuera de dominio (V-02). Decisión del usuario si cambia.
2. **Grano día con entidad**: intacto.
3. **«¿Cómo vamos hoy?»**: Analizar/`proyeccion`, intacto.
4. **`slots.py`, `patrones_grupo.yaml`, frontend, `cuantificar_golden.yaml` y su runner**: intactos.
5. **Intro por LLM** para esta rama: fijo, sin round-trip.
6. **Panel propio de Cuantificar**: se reutiliza `p50_cards`.
7. **Migración `012_p50_2026_desglose.sql`**: operativa, ajena. El executor NO la aplica.

---

## Prompt para el agente EXECUTOR

```
Eres un agente EXECUTOR. Lee COMPLETO el plan
c:\APLICACIONES\ProdIA\Repo ProdIA\backend\Planes\plan_PRODUCCION-HOY-PANEL-MES_20260908.md
(versión v2) y ejecútalo AL PIE DE LA LETRA.

Reglas:
- CERO modificaciones fuera de lo especificado. NO se tocan: frontend, patrones_grupo.yaml,
  slots.py, cuantificar_golden.yaml ni run_golden_cuantificar.py.
- Orden secuencial de §4, empezando por el paso 0 (línea base V-1).
- `import re`, `norm` y `unidades` NO están en respuesta_cuantificar.py: los añade §3.2, y solo ese.
- La rama de §3.3 va ANTES de `rk = _ranking.detectar(texto)` y exige las TRES condiciones.
- Los bloques de §3.4 se AÑADEN AL FINAL del golden; el archivo de §3.5 se CREA completo.
- Si un texto de LOCALIZAR no aparece EXACTAMENTE, DETENTE y reporta ancla, archivo y lo hallado.
- NO corras run_golden.py ni run_golden_cuantificar.py en local.
- Todo en español.

Reporta: ✅/❌ por cada Paso N de §4, y la tabla §6.1 completa con la salida REAL de cada
comando (no «OK»: la salida literal). V-4, V-5, V-8 y V-10 son los decisivos.

Al final: archivos tocados + "¿Hago commit?". Es UN repo (ProdIABack), un commit.
El estado que reportas es «implementado, PENDIENTE de validación humana (§6.2)» — NUNCA
«verificado» ni «completado».
```
