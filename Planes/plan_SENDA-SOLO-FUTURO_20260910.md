# Plan SENDA-SOLO-FUTURO — la proyección del chat muestra solo los meses futuros

| | |
|---|---|
| **ID tarea** | SENDA-SOLO-FUTURO |
| **Fecha** | 2026-09-10 |
| **Versión** | **v2** — auditado contra los pipelines de despliegue. Cambios vs v1: **6 archivos, no 5** (faltaba `mainchat_layout.html`, sin el cual el cambio NO se ve en `/mainchat`); **un solo filtro** en vez de dos duplicados; prohibición explícita de escribir `CLAUDE.md` en comentarios (aborta la migración a Azure); conteo de V8 corregido; anexo §8 con el bloqueo preexistente de Azure. |
| **Alcance** | `plantilla.senda()` (texto), `respuesta_analizar.py` (filtro único + panel), `multitab_shell.js` (rótulos de leyenda), cache-buster en **3** plantillas |
| **Qué NO se toca** | `analisis/api.py` (el endpoint sigue devolviendo los 12 meses), el **tablero** de Analizar (sigue pintando el año completo), `__cnPaintSenda`, `subrouter.py`, `patrones_grupo.yaml`, CSS, `verificar_deploy.ps1` |
| **Predecesor** | `plan_SENDA-CHAT_20260910.md` (commits `0a09915` backend / `f41caef` frontend). Este plan lo refina; NO lo revierte. |

### Decisiones cerradas del usuario

1. **Proyección = meses estrictamente futuros.** Estamos en septiembre: el chat muestra **oct, nov, dic**. Septiembre se excluye por ser el mes en curso. Textual: *«Por eso se llama proyección, muestra es lo futuro»*.
2. **Gráfico: solo oct-dic, limpio.** Sin meses reales de contexto ni atenuados. Eje desde cero (se mantiene la decisión del 2026-09-08).
3. **Texto y gráfico con el MISMO criterio.** Ambos oct-dic.
4. **El tablero de Analizar no cambia.** Sigue con los 12 meses.

---

## §0. Contexto para el agente EXECUTOR

**Proyecto:** ProdIA — chat de producción de Ecopetrol. Dos procesos y **dos repos git hermanos**:

| | Ruta | Stack | Puerto |
|---|---|---|---|
| Frontend | `c:\APLICACIONES\ProdIA\Repo ProdIA\frontend\` | Flask + Jinja2 + JS ES5 | 5029 |
| Backend | `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\` | FastAPI, gestionado con `uv` | 5030 |

**Archivos que se tocan — SON SEIS:**

| # | Archivo | Qué |
|---|---|---|
| A | `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\analizar\plantilla.py` | filtro del texto + guardián de la brecha |
| B | `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\respuesta_analizar.py` | filtro único + panel con la serie filtrada |
| C | `c:\APLICACIONES\ProdIA\Repo ProdIA\frontend\static\js\multitab_shell.js` | rótulos de leyenda auto-correctivos |
| D | `c:\APLICACIONES\ProdIA\Repo ProdIA\frontend\MainChat\templates\mainchat_layout.html` | **cache-buster — el de `/mainchat`, el que de verdad importa** |
| E | `c:\APLICACIONES\ProdIA\Repo ProdIA\frontend\templates\main.html` | cache-buster |
| F | `c:\APLICACIONES\ProdIA\Repo ProdIA\frontend\templates\login.html` | cache-buster (prefetch, sincronizar) |

**Convenciones obligatorias:**

- Python: comentarios en español, prefijo `[2026-09-10 · SENDA-SOLO-FUTURO]`.
- JS **ES5 clásico**: `var` + `function`. Prohibido `const`, `let`, arrow functions, template literals. El operador ternario **sí** es ES5 válido.
- 🔴 **PROHIBIDO escribir la cadena `CLAUDE.md` en cualquier comentario de código.** Ver H5 — aborta el despliegue a Azure. Para citar la guía del proyecto, escribir «la guía del proyecto §N».
- Las anclas «LOCALIZAR» están **copiadas del archivo real**. Si una no aparece literal, **DETENERSE y reportar**.
- Tras tocar los `.py`: **reiniciar el backend a mano**. `iniciar_backend.bat` lanza uvicorn **sin `--reload`**, así que sin reinicio se prueba el código viejo.

**Cómo funciona lo que se toca:**

1. `GET /analisis/president/senda` (`analisis/api.py:2903`) devuelve **siempre los 12 meses** más `ultimo_mes_real` (`api.py:3057-3059`), que hoy vale **8**. **Este endpoint NO se toca**: el tablero lo consume tal cual.
2. `es_real` significa *"tiene escenario REAL cerrado"*, **no** *"es pasado"*. Por eso septiembre (mes en curso, sin cerrar) sale hoy con `es_real=False` y aparece como proyectado. Ese es el matiz que este plan corrige.
3. `respuesta_analizar.py:474-489` (rama `senda`) llama a `plantilla.senda()` para el texto y manda `_s` **completo** al panel. El frontend pinta lo que reciba. El tablero llega por **otro camino** (`__cnPaintSenda` fetchea el endpoint por su cuenta), así que filtrar aquí no lo afecta.
4. `__cnSendaPlotInto` (`multitab_shell.js:6306`) está **compartida** por tablero y chat. Su comentario de cabecera (`:6301-6305`) declara: *"Una sola función = una sola paleta, un solo layout, un solo sitio donde arreglar"*.

---

## §1. Hallazgos de la auditoría

### 🔴 H1 — El filtro va en el BACKEND, no en el JS
`respuesta_analizar.py:489` manda `_s` completo (12 meses) al panel; el tablero usa `__cnPaintSenda` (`multitab_shell.js:6469`), que **fetchea por su cuenta**. Dos caminos de datos independientes. Filtrando en el backend, el chat recibe 3 meses y el tablero sigue con 12, **sin añadir un tercer parámetro** a una función que el propio archivo declara que debe tener un solo layout. Un flag en JS exigiría tocar 3 sitios del JS *más* el backend para el texto. **Determina §3.B.**

### 🔴 H2 — Falta `mainchat_layout.html`: sin él, el cambio NO se ve en `/mainchat`
**Este hallazgo invalidaba el plan v1.** Hay **tres** referencias a `multitab_shell.js` con `?v=`, no dos (verificado con grep sobre todo `frontend\`):

| Archivo:línea | Token hoy | Sirve |
|---|---|---|
| `MainChat\templates\mainchat_layout.html:323` | **`20260908a`** | **`/mainchat` — la interfaz que usa el usuario** |
| `templates\main.html:88` | `20260910a` | `/` (chat clásico) |
| `templates\login.html:43` | `20260910a` | solo prefetch |

El v1 subía main.html y login.html y **dejaba `/mainchat` en `20260908a`**: un navegador con esa URL cacheada sigue sirviendo el JS viejo indefinidamente, y la validación humana daría un falso negativo («no se ve el cambio») que se diagnosticaría como bug del dato. El propio `login.html:31-33` documenta el contrato que el v1 rompía:

```
⚠️ Los ?v= deben coincidir EXACTOS con los de mainchat_layout.html (:10, :13-15,
:317-323). Si allí se sube un token y aquí no, esto deja de servir EN SILENCIO
```

Ese contrato **ya está incumplido hoy** (`20260908a` vs `20260910a`), heredado del plan SENDA-CHAT. Este plan lo repara dejando los tres en el mismo token. **Determina §3.D, §3.E, §3.F.**

### 🔴 H3 — Dos filtros duplicados son una bomba de relojería; se deja UNO
En el v1, `plantilla.py` y `respuesta_analizar.py` filtraban por separado con criterio idéntico, y el plan lo blindaba con una regla («si cambias uno, cambia el otro»). Eso es una advertencia, no una garantía. **Mejora del v2**: `respuesta_analizar` construye la serie filtrada **una vez** (`_s_chat`) y se la pasa a los dos consumidores — `plantilla.senda(_s_chat, …)` para el texto y `panel.datos = _s_chat` para la gráfica. El filtro de `plantilla.py` se conserva como **defensa idempotente** (volver a filtrar una serie ya filtrada da lo mismo, verificado: con `umr=8`, oct/nov/dic siguen cumpliendo `mes > 9`), de modo que la función sigue siendo correcta si algún día se la llama con datos completos. **Determina §3.B.**

Precedente del propio archivo: la rama `tendencia` (`respuesta_analizar.py:447-465`) ya hace exactamente esto — calcula `_t` una vez y alimenta texto y panel desde ahí.

### 🔴 H4 — Con un solo mes futuro, la frase de la brecha queda absurda
`plantilla.py:360-361`: `b0 = futuros[0]`, `b1 = futuros[-1]`. En **noviembre** solo quedará diciembre → `b0 == b1` → ninguna rama de `<`/`>` se cumple → `verbo = "se mantiene"` y sale *«la brecha se mantiene de -12,3 a -12,3 kboepd»*. No lanza, pero es texto roto que **llegará solo con el calendario**, sin que nadie toque el código. **Determina §3.A.2.**

### 🔴 H5 — Escribir `CLAUDE.md` en un comentario ABORTA la migración a Azure
`migrar_a_azure.ps1:87` define `$TerminosProhibidos = @('claude', 'jaguez40')`; `:181` compara con `$texto -match [regex]::Escape($t)` y **PowerShell `-match` es case-insensitive**, así que `CLAUDE.md` casa con `claude`. Un solo hallazgo → `:375` `throw "Chequeo de trazas fallido"` y **no publica nada**.

El patrón `(CLAUDE.md §N)` es el estilo de comentario **dominante** en `consulta_v2/` — el executor lo imitará si nadie se lo prohíbe, y cada aparición nueva bloquea el despliegue. **Determina la regla 🔴 de §0, la regla 3 de §5 y la validación V14.** Los comentarios de este plan ya están redactados sin esa cadena.

### 🔴 H6 — La leyenda "Real Ecopetrol" / "Real filiales" miente en modo solo-futuro
`multitab_shell.js:6360` y `:6367` rotulan literalmente **"Real"**. Con solo oct-dic, todas las barras son proyección ámbar rayada y la leyenda las llama "Real". Es el mismo fallo silencioso que el backend documenta haber cometido ya (`analisis/api.py:2947-2949`: *«el panel enseñaba el plan disfrazado de real»*). **Determina §3.C.**

### 🟡 H7 — El rótulo se deriva del dato, sin bandera
`primerProyIdx` se calcula en el `forEach` (`:6347`), **antes** de construir las trazas (`:6359`). Con todos los meses proyectados vale **0**; en el tablero (empieza en enero real) vale **8**. `primerProyIdx === 0` distingue los dos modos **sin parámetro nuevo**, respetando el principio de `:6301-6305`.

### 🟡 H8 — `warmup.py` se traga los errores de este módulo
`consulta_v2\warmup.py` llama indirectamente a `respuesta_analizar` en un hilo daemon al arrancar, y **traga toda excepción**. Si el cambio introduce un error, el backend arranca limpio y el síntoma aparece como lentitud o «SIN RESPUESTA» en la primera pregunta, no como error visible. **Por eso §6.1 valida importando el módulo directamente**, sin fiarse de que el backend levante.

Relacionado: `frontend\routes\api.py:794` proxea `/consulta2/preguntar` con `timeout=90`. Si algo alarga la respuesta, el síntoma en pantalla será «SIN RESPUESTA», no un error del backend.

### 🟢 H9 — La línea "PROYECTADO" desaparece sola, y está bien
`:6418` exige `primerProyIdx > 0`. En modo solo-futuro vale 0 → `shapes` y `annotations` quedan vacíos → no se dibuja la línea punteada ni el rótulo. Plotly acepta arrays vacíos sin error. Es lo deseado: un separador sin nada que separar es ruido. **No hay que tocar nada.**

### 🟢 H10 — El eje Y se recalcula solo
`:6414-6415`: `maxVal` se acumula sobre los meses **realmente recorridos**. Con oct-dic (totales ~730-745) `hi` queda prácticamente igual, porque los meses altos están al final del año. No hay constantes de eje ni de número de meses.

### 🟢 H11 — `plantilla.senda()` tiene UN solo call site
`grep '\.senda('` en todo `backend\`: únicamente `respuesta_analizar.py:481`. Cambiar su filtro no propaga.

### 🟢 H12 — Cero tests que fijen este texto
`grep -i 'senda'` en `backend\backend\tests\` → **0 ocurrencias** (verificado). No hay asserts que romper… ni red de seguridad: por eso §6.1 incluye pruebas con datos sintéticos que simulan hoy, noviembre y diciembre.

### 🟢 H13 — `verificar_deploy.ps1` no se rompe (ni valida nada de esto)
Su chequeo de estáticos (`:105-106`) captura solo el `filename=` del `url_for`, **no la query string**, así que el cambio de cache-buster le es indiferente. Tampoco mira `main.html`, ni `mainchat_layout.html`, ni el backend: los 6 archivos del plan pasan sin que compruebe nada de ellos.

### 🟢 H14 — Sin hooks, CI ni pre-commit
`.git\hooks` vacío en ambos repos (solo `.sample`); no hay `.github/`, `azure-pipelines.yml` ni `.pre-commit-config.yaml`. Nada automático que romper ni en lo que apoyarse.

### 🟢 H15 — Sin caché de backend que invalidar
`plantilla.py` y `respuesta_analizar.py` no tienen `lru_cache`, ni leen ficheros, ni compilan YAML al arranque. El precedente de `patrones.py` (que sí cachea el YAML) **no aplica aquí**. Basta reiniciar el proceso.

### 🟡 H16 — El texto que hoy ve el usuario CAMBIARÁ, y es esperado
`b0` pasa de ser la brecha de **septiembre** a la de **octubre**. El verbo (`se estrecha`/`se amplía`/`se mantiene`) puede voltearse respecto de lo que se ve hoy. No es regresión: es el mismo cálculo sobre el punto de partida correcto. Se declara para que nadie lo reporte como bug.

---

## §2. Estado actual

**Texto** (`plantilla.py:347-351`, literal):
```python
    scope = entidad or "la producción ECP"
    serie = (d or {}).get("serie") or []
    futuros = [m for m in serie if not m.get("es_real") and m.get("total") is not None]
    if not futuros:
        return f"📊 {scope}\nNo tengo la senda proyectada para el resto del año."
```
→ hoy `futuros` = **sep, oct, nov, dic**.

**Panel** (`respuesta_analizar.py:477` y `:489`): `_fut` con el mismo filtro viejo, y `datos: _s` **completo** → el gráfico del chat pinta **los 12 meses**.

**Síntoma medido (captura del usuario, 2026-09-10):** el chat responde bien, pero el gráfico muestra ene-dic con sep-dic en ámbar. Y hay una incoherencia ya presente: el **texto** habla de sep-dic mientras el **gráfico** pinta los 12.

---

## §3. Especificación

### §3.A — MODIFICAR `plantilla.py` (archivo A)

#### A.1 — El filtro pasa a futuro estricto

**LOCALIZAR** (líneas 347-351, literal):
```python
    scope = entidad or "la producción ECP"
    serie = (d or {}).get("serie") or []
    futuros = [m for m in serie if not m.get("es_real") and m.get("total") is not None]
    if not futuros:
        return f"📊 {scope}\nNo tengo la senda proyectada para el resto del año."
```

**SUSTITUIR POR:**
```python
    scope = entidad or "la producción ECP"
    serie = (d or {}).get("serie") or []
    # [2026-09-10 · SENDA-SOLO-FUTURO] PROYECCIÓN = meses estrictamente FUTUROS, no «meses sin
    # cerrar». `es_real` significa "tiene escenario REAL", y el mes EN CURSO todavía no lo tiene:
    # con el filtro anterior (`not es_real`) septiembre entraba en la senda estando ya corriendo.
    # Su cifra es una proyección de CIERRE DE MES mezclada con lo ya producido — otra cosa que
    # oct/nov/dic, y presentarlas juntas las iguala. Decisión del usuario 2026-09-10: «por eso se
    # llama proyección, muestra es lo futuro».
    # 🔑 El corte sale del DATO (`ultimo_mes_real`, que el endpoint ya emite en
    #    analisis/api.py:3057-3059), NO del reloj del servidor: así el texto y la gráfica cortan
    #    por el mismo sitio aunque el proceso lleve días levantado o la ingesta vaya atrasada.
    # 🔑 IDEMPOTENTE a propósito: respuesta_analizar.py ya pasa la serie filtrada, y volver a
    #    aplicar el mismo corte sobre ella da lo mismo. Se conserva aquí para que la función siga
    #    siendo correcta si algún día se la llama con la respuesta completa del endpoint.
    # 🔑 Default 0 defensivo: sin el campo, `mes > 1` deja casi toda la serie — degradación suave,
    #    nunca una lista vacía silenciosa.
    umr = (d or {}).get("ultimo_mes_real") or 0
    futuros = [m for m in serie
               if (m.get("mes") or 0) > umr + 1 and m.get("total") is not None]
    if not futuros:
        return f"📊 {scope}\nNo tengo la senda proyectada para el resto del año."
```

#### A.2 — Guardián para el caso de un solo mes

**LOCALIZAR** (líneas 356-369, literal):
```python
    # Brecha contra el P50: SOLO si TODOS los meses futuros la tienen -- a medias sería peor
    # que callarla (regla madre: no inventar ni completar con huecos).
    if all(m.get("p50") is not None for m in futuros):
        p50s = " / ".join(_fmt(m["p50"], "CRUDO") for m in futuros)
        b0 = futuros[0]["total"] - futuros[0]["p50"]
        b1 = futuros[-1]["total"] - futuros[-1]["p50"]
        if abs(b1) < abs(b0) - 1e-6:
            verbo = "se estrecha"
        elif abs(b1) > abs(b0) + 1e-6:
            verbo = "se amplía"
        else:
            verbo = "se mantiene"
        linea += (f"\nContra el compromiso P50 ({p50s}) la brecha {verbo} de "
                  f"{_fmt(b0, 'CRUDO')} a {_fmt(b1, 'CRUDO')} {u}.")
```

**SUSTITUIR POR:**
```python
    # Brecha contra el P50: SOLO si TODOS los meses futuros la tienen -- a medias sería peor
    # que callarla (regla madre: no inventar ni completar con huecos).
    if all(m.get("p50") is not None for m in futuros):
        p50s = " / ".join(_fmt(m["p50"], "CRUDO") for m in futuros)
        b0 = futuros[0]["total"] - futuros[0]["p50"]
        b1 = futuros[-1]["total"] - futuros[-1]["p50"]
        # [2026-09-10 · SENDA-SOLO-FUTURO] Con UN SOLO mes futuro (pasará en noviembre, cuando
        # solo quede diciembre) b0 y b1 son el MISMO punto: ninguna comparación se cumple, el
        # verbo caía en "se mantiene" y la frase salía «la brecha se mantiene de -12,3 a -12,3».
        # Un mes no tiene trayectoria, tiene una cifra — y así se dice. Llega solo con el
        # calendario, sin que nadie toque el código; por eso se cierra ahora.
        if len(futuros) < 2:
            linea += (f"\nContra el compromiso P50 ({p50s}) la brecha es de "
                      f"{_fmt(b0, 'CRUDO')} {u}.")
        else:
            if abs(b1) < abs(b0) - 1e-6:
                verbo = "se estrecha"
            elif abs(b1) > abs(b0) + 1e-6:
                verbo = "se amplía"
            else:
                verbo = "se mantiene"
            linea += (f"\nContra el compromiso P50 ({p50s}) la brecha {verbo} de "
                      f"{_fmt(b0, 'CRUDO')} a {_fmt(b1, 'CRUDO')} {u}.")
```

### §3.B — MODIFICAR `respuesta_analizar.py` (archivo B)

Un solo reemplazo, que sustituye el bloque entero de la rama. **Filtro único**: se calcula una vez y alimenta texto y panel.

**LOCALIZAR** (líneas 474-489, literal):
```python
    if sub == "senda":
        _s = senda_fn(anio=2026)
        _serie = (_s or {}).get("serie") or []
        _fut = [m for m in _serie if not m.get("es_real") and m.get("total") is not None]
        if not _fut:
            return {"mensaje": "No tengo la senda proyectada para el resto del año.",
                    "panel": None}
        cuerpo = _plantilla.senda(_s, ent_valor)
        intro = _intro(alcance, usuario)
        mensaje = respuesta_base.envolver(
            intro, cuerpo, "¿Quieres el detalle de un mes, o la brecha contra el P50?")
        # [2026-09-10 · SENDA-CHAT] El panel viaja con la respuesta cruda del endpoint, igual que
        # `p50_cards` con /analisis/president: el frontend ya sabe pintarla (__cnSendaPlotInto) y
        # no hay que re-fetchear lo que ya está en la mano. Antes devolvía `panel: None` y la
        # senda salía solo como texto — la gráfica existía, pero solo en el tablero.
        return {"mensaje": mensaje, "panel": {"tipo": "analiza_senda", "datos": _s}}
```

**SUSTITUIR POR:**
```python
    if sub == "senda":
        _s = senda_fn(anio=2026)
        _serie = (_s or {}).get("serie") or []
        # [2026-09-10 · SENDA-SOLO-FUTURO] Futuro ESTRICTO (`mes > ultimo_mes_real + 1`), no
        # «meses sin cerrar»: el mes EN CURSO aún no tiene escenario REAL, así que el filtro
        # anterior (`not es_real`) lo metía en la senda estando ya corriendo. Decisión del
        # usuario: proyección es lo que no ha pasado.
        # 🔑 UN SOLO FILTRO para los dos consumidores. `_s_chat` alimenta el TEXTO
        #    (_plantilla.senda) y la GRÁFICA (panel.datos): así no pueden desincronizarse, que
        #    era el riesgo real — un texto hablando de cuatro meses sobre una gráfica de tres.
        #    Mismo patrón que la rama `tendencia` de arriba, que calcula `_t` una vez y de ahí
        #    salen mensaje y panel.
        # 🔑 dict(_s) es copia SUPERFICIAL: se reemplaza la lista `serie`, no se muta ningún mes
        #    ni el `_s` original. `ultimo_mes_real` viaja dentro, así que el filtro idempotente
        #    de plantilla.senda() sigue teniendo con qué cortar.
        _umr = (_s or {}).get("ultimo_mes_real") or 0
        _fut = [m for m in _serie
                if (m.get("mes") or 0) > _umr + 1 and m.get("total") is not None]
        if not _fut:
            return {"mensaje": "No tengo la senda proyectada para el resto del año.",
                    "panel": None}
        _s_chat = dict(_s or {})
        _s_chat["serie"] = _fut
        cuerpo = _plantilla.senda(_s_chat, ent_valor)
        intro = _intro(alcance, usuario)
        mensaje = respuesta_base.envolver(
            intro, cuerpo, "¿Quieres el detalle de un mes, o la brecha contra el P50?")
        # [2026-09-10 · SENDA-CHAT] El panel viaja con la respuesta del endpoint, igual que
        # `p50_cards` con /analisis/president: el frontend ya sabe pintarla (__cnSendaPlotInto) y
        # no hay que re-fetchear lo que ya está en la mano. Antes devolvía `panel: None` y la
        # senda salía solo como texto — la gráfica existía, pero solo en el tablero.
        # [2026-09-10 · SENDA-SOLO-FUTURO] Al CHAT viaja `_s_chat` (solo meses futuros). El filtro
        # vive aquí y no en el JS a propósito: __cnSendaPlotInto está COMPARTIDA con el tablero,
        # que llega por otro camino (__cnPaintSenda fetchea el endpoint por su cuenta) y debe
        # seguir pintando los 12 meses. Filtrando el dato en origen, el tablero ni se entera y no
        # hace falta meterle una bandera a una función que el propio archivo declara que debe
        # tener "un solo layout, un solo sitio donde arreglar" (multitab_shell.js:6301-6305).
        return {"mensaje": mensaje, "panel": {"tipo": "analiza_senda", "datos": _s_chat}}
```

### §3.C — MODIFICAR `multitab_shell.js` (archivo C)

#### C.1 — Derivar el modo del dato

**LOCALIZAR** (líneas 6352-6359, literal — el comentario «Ecopetrol ABAJO, Filiales ENCIMA» es único en el archivo, verificado):
```js
          });
        });

        // Ecopetrol ABAJO, Filiales ENCIMA. Con el eje recortado (ver yaxis) el apilado sigue
        // siendo fiel: lo que se recorta es el zócalo común de TODAS las barras, no una sola.
        // El bug original era otro -- se dibujaba la franja de Ecopetrol desde el piso del eje
        // en vez de desde cero, y por eso salía más corta que filiales.
        var trazaEcp = {
```

**SUSTITUIR POR:**
```js
          });
        });

        // [2026-09-10 · SENDA-SOLO-FUTURO] ¿TODAS las barras son proyección? Se deriva del dato,
        // sin parámetro nuevo: primerProyIdx vale 0 cuando el primer mes ya es proyectado (el
        // chat, que recibe solo los meses futuros) y 8 en el tablero, que empieza en enero real.
        // Sirve para rotular la leyenda con la verdad — ver trazaEcp/trazaFil.
        // 🔑 En este modo NO se dibuja la línea punteada "PROYECTADO" (:6418 exige
        //    primerProyIdx > 0): correcto, un separador sin nada que separar es ruido.
        var todoProy = (primerProyIdx === 0);

        // Ecopetrol ABAJO, Filiales ENCIMA. Con el eje recortado (ver yaxis) el apilado sigue
        // siendo fiel: lo que se recorta es el zócalo común de TODAS las barras, no una sola.
        // El bug original era otro -- se dibujaba la franja de Ecopetrol desde el piso del eje
        // en vez de desde cero, y por eso salía más corta que filiales.
        var trazaEcp = {
```

#### C.2 — Rótulos condicionales

**LOCALIZAR** (líneas 6360-6367, literal):
```js
          x: meses, y: ecp, name: "Real Ecopetrol", type: "bar",
          marker: { color: colEcp, pattern: { shape: patEcp, fgcolor: C.ecpProy, size: 4 } },
          text: ecpTxt, textposition: "inside", insidetextanchor: "middle",
          textfont: { size: 10, color: ecpTxtCol },
          hovertemplate: "Ecopetrol %{y:.1f}<extra></extra>"
        };
        var trazaFil = {
          x: meses, y: fil, name: "Real filiales", type: "bar",
```

**SUSTITUIR POR:**
```js
          // [2026-09-10 · SENDA-SOLO-FUTURO] El rótulo dice lo que la barra ES. Con solo meses
          // futuros, llamar "Real" a una proyección repetiría el fallo que el backend ya documenta
          // haber cometido (analisis/api.py:2947-2949: «el panel enseñaba el plan disfrazado de
          // real»). En el tablero el modo es false y la leyenda queda exactamente como estaba.
          x: meses, y: ecp, name: todoProy ? "Proyección Ecopetrol" : "Real Ecopetrol", type: "bar",
          marker: { color: colEcp, pattern: { shape: patEcp, fgcolor: C.ecpProy, size: 4 } },
          text: ecpTxt, textposition: "inside", insidetextanchor: "middle",
          textfont: { size: 10, color: ecpTxtCol },
          hovertemplate: "Ecopetrol %{y:.1f}<extra></extra>"
        };
        var trazaFil = {
          x: meses, y: fil, name: todoProy ? "Proyección filiales" : "Real filiales", type: "bar",
```

### §3.D — MODIFICAR `mainchat_layout.html` (archivo D) 🔴 EL CRÍTICO

**LOCALIZAR** (línea 323, literal):
```html
<script defer src="{{ url_for('static', filename='js/multitab_shell.js') }}?v=20260908a"></script>
```
**SUSTITUIR POR:**
```html
<script defer src="{{ url_for('static', filename='js/multitab_shell.js') }}?v=20260910b"></script>
```

> Sin este cambio, `/mainchat` sigue pidiendo `?v=20260908a` y un navegador que ya tenga esa URL en caché **nunca verá el JS nuevo**. Es la ruta que usa el usuario para validar.

### §3.E — MODIFICAR `main.html` (archivo E)

**LOCALIZAR** (línea 88, literal):
```html
<script src="{{ url_for('static', filename='js/multitab_shell.js') }}?v=20260910a"></script>
```
**SUSTITUIR POR:**
```html
<script src="{{ url_for('static', filename='js/multitab_shell.js') }}?v=20260910b"></script>
```

### §3.F — MODIFICAR `login.html` (archivo F)

**LOCALIZAR** (línea 43, literal):
```html
    <link rel="prefetch" href="{{ url_for('static', filename='js/multitab_shell.js') }}?v=20260910a">
```
**SUSTITUIR POR:**
```html
    <link rel="prefetch" href="{{ url_for('static', filename='js/multitab_shell.js') }}?v=20260910b">
```

---

## §4. Orden de ejecución

| Paso | Archivo | Acción | Verificación inmediata |
|---|---|---|---|
| 1 | A `plantilla.py` | §3.A.1 y §3.A.2 | V1-V4 de §6.1 |
| 2 | B `respuesta_analizar.py` | §3.B | V5 de §6.1 |
| 3 | C `multitab_shell.js` | C.1 → C.2 | V9-V11 |
| 4 | D `mainchat_layout.html` | §3.D | V12 |
| 5 | E `main.html` | §3.E | V12 |
| 6 | F `login.html` | §3.F | V12 |
| 7 | — | §6.1 completa | todo verde |

Pasos 1-2 en el repo `backend\`; 3-6 en `frontend\`. **Dos commits**, uno por repo.

---

## §5. Reglas no negociables

1. **CERO cambios fuera de §3.** No tocar `analisis/api.py`, ni `__cnPaintSenda`, ni el resto de `__cnSendaPlotInto`, ni `verificar_deploy.ps1`.
2. **Los tres cache-busters al MISMO valor** `20260910b`. Dejar uno atrás reintroduce el bug de H2.
3. 🔴 **PROHIBIDO escribir la cadena `CLAUDE.md` en comentarios de código.** `migrar_a_azure.ps1:87,181` la detecta (case-insensitive) y aborta el despliegue entero. Escribir «la guía del proyecto §N».
4. **JS ES5 clásico**: `var` + `function`. Sin `const`/`let`/arrow/template literals. El ternario sí vale.
5. **Anclas literales.** Si un «LOCALIZAR» no aparece exacto, DETENERSE y reportar.
6. **No medir `president_senda` importándolo en proceso** (regla del proyecto: los defaults `Query(...)` falsean el resultado). Las pruebas de §6.1 usan diccionarios sintéticos, que miden la lógica pura.
7. **Validar importando el módulo**, no dando por bueno que el backend arranque: `warmup.py` se traga las excepciones de este paquete (H8).
8. Comentarios nuevos **en español** con prefijo `[2026-09-10 · SENDA-SOLO-FUTURO]`.

---

## §6. Validación

### §6.1 Estática (la hace el executor, en local, sin BD)

Carpeta: `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\`. Línea por línea, PowerShell normal.

**V1 — el texto corta en oct-dic (escenario de HOY: `ultimo_mes_real=8`)**
```powershell
uv run python -c "from app.features.consulta_v2.analizar import plantilla as p; d={'anio':2026,'unidad':'kboepd','ultimo_mes_real':8,'serie':[{'mes':m,'mes_nombre':n,'total':t,'p50':q,'es_real':r} for m,n,t,q,r in [(8,'Agosto',714.5,740.4,True),(9,'Septiembre',726.4,735.0,False),(10,'Octubre',733.6,741.8,False),(11,'Noviembre',731.8,738.3,False),(12,'Diciembre',729.9,733.3,False)]]}; print(p.senda(d,None))"
```
Esperado: menciona **octubre, noviembre y diciembre**; **NO** septiembre ni agosto.

**V2 — un solo mes futuro no produce «se mantiene de X a X» (escenario NOVIEMBRE)**
```powershell
uv run python -c "from app.features.consulta_v2.analizar import plantilla as p; d={'anio':2026,'unidad':'kboepd','ultimo_mes_real':10,'serie':[{'mes':11,'mes_nombre':'Noviembre','total':731.8,'p50':738.3,'es_real':False},{'mes':12,'mes_nombre':'Diciembre','total':729.9,'p50':733.3,'es_real':False}]}; print(p.senda(d,None))"
```
Esperado: solo **diciembre**, y la frase dice **«la brecha es de …»**.

**V3 — sin meses futuros no revienta (escenario DICIEMBRE)**
```powershell
uv run python -c "from app.features.consulta_v2.analizar import plantilla as p; d={'anio':2026,'unidad':'kboepd','ultimo_mes_real':11,'serie':[{'mes':12,'mes_nombre':'Diciembre','total':729.9,'p50':733.3,'es_real':False}]}; print(repr(p.senda(d,None)))"
```
Esperado: `'📊 la producción ECP\nNo tengo la senda proyectada para el resto del año.'`

**V4 — `ultimo_mes_real` ausente degrada suave, no vacía**
```powershell
uv run python -c "from app.features.consulta_v2.analizar import plantilla as p; d={'anio':2026,'unidad':'kboepd','serie':[{'mes':m,'mes_nombre':str(m),'total':700.0,'p50':720.0,'es_real':False} for m in range(1,13)]}; r=p.senda(d,None); print('OK' if 'No tengo' not in r else 'MAL: se vacio')"
```
Esperado: `OK`.

**V5 — el filtro es IDEMPOTENTE (la mejora de H3 no cambia el texto)**
```powershell
uv run python -c "from app.features.consulta_v2.analizar import plantilla as p; base=[{'mes':m,'mes_nombre':n,'total':t,'p50':q,'es_real':r} for m,n,t,q,r in [(8,'Agosto',714.5,740.4,True),(9,'Septiembre',726.4,735.0,False),(10,'Octubre',733.6,741.8,False),(11,'Noviembre',731.8,738.3,False),(12,'Diciembre',729.9,733.3,False)]]; full={'anio':2026,'unidad':'kboepd','ultimo_mes_real':8,'serie':base}; chat=dict(full); chat['serie']=[m for m in base if m['mes']>9]; print('IDEMPOTENTE OK' if p.senda(full,None)==p.senda(chat,None) else 'MAL: difieren')"
```
Esperado: `IDEMPOTENTE OK` — el texto es idéntico se le pase la serie completa o la ya filtrada.

**V6 — importaciones (no fiarse del arranque, H8)**
```powershell
uv run python -c "import app.features.consulta_v2.analizar.plantilla, app.features.consulta_v2.respuesta_analizar; print('IMPORT OK')"
```

**V7 — suite, sin fallos NUEVOS**
```powershell
uv run pytest tests/test_analizar.py tests/test_analizar_tendencia.py tests/test_consulta_v2_clasificador.py -q
```
Esperado: **exactamente 2 fallos preexistentes** (`test_escalada_fallback_conserva_regex` y `test_producto_explicito_elige_la_serie_de_gas`), los mismos medidos el 2026-09-10. ⚠️ Cualquier fallo distinto es regresión → DETENERSE.

**V8 — goldens sin regresión**
```powershell
$env:PYTHONPATH='.'; uv run python app/features/consulta_v2/golden/run_golden.py
```
```powershell
$env:PYTHONPATH='.'; $env:CONSULTA_ANALIZA_LLM='false'; uv run python app/features/consulta_v2/golden/run_golden_analizar.py
```
Esperado: `93/100 = 93%` y `36/36 = 100%`, idénticos a la medición del 2026-09-10.

Carpeta: `c:\APLICACIONES\ProdIA\Repo ProdIA\frontend\`.

| # | Comando | Esperado |
|---|---|---|
| V9 | `node -e "new Function(require('fs').readFileSync('static/js/multitab_shell.js','utf8'));console.log('JS OK')"` | `JS OK` |
| V10 | `(Select-String -Path static\js\multitab_shell.js -Pattern 'todoProy').Count` | **4** (declaración + 1 mención en comentario + 2 ternarios) |
| V11 | `(Select-String -Path static\js\multitab_shell.js -Pattern 'name: "Real Ecopetrol"').Count` | **0** (ahora es ternario) |
| V12 | `(Select-String -Path templates\main.html,templates\login.html,MainChat\templates\mainchat_layout.html -Pattern '20260910b').Count` | **3** ← los TRES |
| V13 | `(Select-String -Path templates\main.html,templates\login.html,MainChat\templates\mainchat_layout.html -Pattern 'multitab_shell.js.*20260910a\|multitab_shell.js.*20260908a').Count` | **0** (ningún token viejo sobrevive) |
| V14 | `(Select-String -Path static\js\multitab_shell.js -Pattern 'CLAUDE\.md').Count` | **1** — el preexistente de `:2208`. Si sale 2+, el executor añadió uno y bloquea Azure (H5) → DETENERSE |

Fallo en cualquiera → DETENERSE y reportar.

### §6.2 Humana (la hace el usuario, en el **servidor de pruebas**)

Tras `git pull` en ambos repos y **reiniciar ambos backends** (uvicorn corre sin `--reload`). Abrir `http://localhost:5029/mainchat`, **Ctrl+F5**, F12 → Console.

| # | Acción | Esperado |
|---|---|---|
| H-1 | `Cuánto vamos a producir en los próximos meses hasta diciembre?` | Gráfico con **3 barras: Oct, Nov, Dic**. Sin ene-sep. Leyenda: **«Proyección Ecopetrol» / «Proyección filiales»**. Sin línea punteada "PROYECTADO". Console: 0 errores |
| H-2 | Leer el texto de esa misma respuesta | Menciona **octubre, noviembre, diciembre** — **no** septiembre. Coincide mes a mes con las barras |
| H-3 | `¿Cómo se ve el cierre de año?` | Igual que H-1 |
| H-4 | **Tablero de Analizar** (Insights, vista global) | **Sin cambios**: 12 meses, ene-ago verde, sep-dic ámbar, línea punteada "PROYECTADO", leyenda «Real Ecopetrol» / «Real filiales» |
| H-5 | `Cómo vamos a cerrar el mes?` | Sigue respondiendo el pace del mes en curso (no la senda) |
| H-6 | Preguntar H-1 dos veces seguidas | Dos bloques, ambos pintados |
| H-7 | En Network (F12), mirar qué JS cargó `/mainchat` | `multitab_shell.js?v=20260910b` — **no** `20260908a` |

⚠️ **H-4 es el control crítico**: si el tablero también perdiera los meses reales, el filtro se aplicó en el sitio equivocado.
⚠️ **H-7 valida H2**: si sale `20260908a`, el paso §3.D no se aplicó y todo lo demás es un falso negativo.

**Estado al terminar el executor: «implementado, PENDIENTE de validación humana».** Solo el usuario marca ✅.

---

## §7. Fuera de alcance

- **Rotular septiembre como «mes en curso» en el gráfico**: el usuario decidió excluirlo del todo. El pace del mes en curso ya lo responde `¿cómo vamos a cerrar el mes?` por otra ruta (`sub == "proyeccion"`).
- **Meses reales atenuados de contexto**: descartado por el usuario (opción «solo oct-dic, limpio»).
- **Recortar el eje Y**: descartado — ya se probó el 2026-09-08 y hace que la franja de Ecopetrol (5× mayor) parezca menor que la de filiales.
- **Cambiar el endpoint `president_senda`**: sigue devolviendo los 12 meses; el tablero depende de eso.
- **Tests automáticos de `plantilla.senda()`**: no existen (H12) y este plan no los crea. Las pruebas V1-V5 cubren la lógica con datos sintéticos pero no quedan en la suite. Candidato a plan aparte.
- **Prefetch desfasado de `colapsable.css`** (`login.html:39` = `20260831a` contra `mainchat_layout.html:13` = `20260907b`): incumple el mismo contrato de H2, es ajeno a esta tarea y no se toca aquí para no mezclar. Anotado para un plan de higiene.
- **`verificar_deploy.ps1` no valida ninguno de estos 6 archivos** (H13). Ampliarlo sería útil pero es otro plan.

---

## §8. ANEXO — 🔴 La migración a Azure está bloqueada HOY (preexistente, decide el usuario)

**No lo causa este plan, pero impide desplegarlo.** `migrar_a_azure.ps1` aborta si encuentra la cadena `claude` (case-insensitive) en cualquier archivo versionado no exento. Hay **6 apariciones** de `CLAUDE.md` en comentarios de código:

| Repo | Archivo:línea |
|---|---|
| frontend | `static\js\multitab_shell.js:2208` |
| backend | `app\features\consulta_v2\analizar\subrouter.py:52` |
| backend | `app\features\consulta_v2\respuesta_cuantificar.py:35, 146, 292, 487` |

El propio `SKILL.md` fija la solución: *«Si el chequeo falla, la solución nunca es añadir el archivo a los exentos: es limpiar el texto en el repositorio de origen»*.

**Arreglo:** sustituir `CLAUDE.md §N` por `la guía del proyecto §N` en esas 6 líneas. Es puramente textual, en comentarios, sin efecto funcional.

⚠️ **El executor NO debe hacer esto por su cuenta**: toca `respuesta_cuantificar.py`, fuera del alcance de §3. Requiere que el usuario lo apruebe, como plan aparte o como paso extra explícito de este. Si no se hace, este cambio se puede probar en Pruebas pero **no se podrá publicar en Azure**.

Dos notas más del mismo script, sin acción pero conviene saberlas:
- Cubre **los dos repos** en una sola invocación (`-Repo ambos` es el default). No hay que migrar el backend aparte.
- Su rama por defecto es **`prodiav2`**, no `dev` como dice la documentación del pipeline.
