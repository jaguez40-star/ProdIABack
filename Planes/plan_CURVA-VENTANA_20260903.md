# plan_CURVA-VENTANA_20260903

**ID_TAREA:** `CURVA-VENTANA`
**Fecha:** 2026-09-03
**Rol del lector:** agente EXECUTOR
**Depende de:** `plan_VENTANAS-TEMPORALES_20260903.md` (ya ejecutado, commit `9161b79`).
**Alcance:** **6** archivos de producción en **DOS repos** (backend y frontend) + 1 de tests.

> ## ⚠️ Verificación v2 (2026-09-03, segunda pasada) — el plan v1 ESTABA ROTO
>
> La v1 se auditó contra el código real y **no habría funcionado**. Dos fallos bloqueantes y
> tres correcciones, todos medidos leyendo el fuente, no razonados:
>
> | # | Hallazgo v2 | Efecto en la v1 |
> |---|---|---|
> | 🔴 **H9** | El navegador **no llama a INGESTA**: llama al **proxy Flask** (`frontend\routes\api.py:267`), que **copia solo `entidad/segmento/nivel/periodo`** a INGESTA. `v_ini`/`v_fin` se **descartaban en el proxy** | La curva habría seguido saliendo del mes. **La v1 no cambiaba nada.** +1 archivo |
> | 🔴 **H10** | Ese proxy tiene **caché TTL de 45 s con clave propia** (`_analisis_proxy_cacheado`, `api.py:226-229`) construida **solo con los params reenviados**. Sin propagar la ventana, ventana y mes **comparten entrada de caché** | Preguntar ventana y luego mes (o al revés) devolvía **la curva de la otra**, hasta 45 s |
> | 🟠 **H11** | `qs` en la v1 concatenaba mal cuando `__cnAnzQS` devuelve `""` (entidad global): salía `"&v_ini=…"` sin `?` | URL inválida en el caso global |
> | 🟡 **H12** | `periodo="2026-07-25 a"` (§3.5 v1) hace `periodo_ok=False` en `_ambito` (`api.py:450`) — un flag que el payload expone | Ruido evitable: se manda `periodo` limpio |
> | 🟢 **H13** | `_CLAVE_IGNORAR=("pulir",)` confirma que el proxy YA tiene el idiom de excluir claves de la caché; y `_analisis_es_cacheable` protege de cachear errores | El patrón a clonar existe |
>
> **Todo lo demás de la v1 se confirmó midiendo:** H1 (el panel repinta con su propio fetch),
> H2 (`_ambito` deriva del mes), H3 (KPI mensual), H6 (2 ejecutores usan `curva_dia_mes`),
> H7 (el techo ya llega), H8 (eje X = día del mes como categoría).

---

## 0. Contexto para el agente EXECUTOR

### 0.1 Qué se pide

Hoy, «¿cuánto produjo Castilla en los últimos 30 días?» responde el **KPI del mes de agosto
completo** (gauge 104,9% REAL/PPTO) más la curva diaria del **mes calendario**. El usuario pide
que esa pregunta despliegue **la curva diaria acotada a la ventana real** — del último día con
reporte hacia atrás, N días — en vez del mes.

El plan anterior (`VENTANAS-TEMPORALES`) ya dejó resuelto y disponible el slot
`slots["ventana"] = {unidad, cantidad, ini, fin, asumido}`. **Nadie lo consume todavía.** Este
plan lo conecta de punta a punta.

### 0.2 Rutas absolutas

| Qué | Ruta |
|---|---|
| Repo BACKEND (git) | `C:\APLICACIONES\ProdIA\Repo ProdIA\backend` |
| Repo FRONTEND (git) | `C:\APLICACIONES\ProdIA\Repo ProdIA\frontend` |
| MODIFICAR 1 | `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\analisis\api.py` |
| MODIFICAR 2 | `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\cuantificar\slots.py` |
| MODIFICAR 3 | `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\cuantificar\ejecutor.py` |
| MODIFICAR 4 | `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\respuesta_cuantificar.py` |
| MODIFICAR 5 | `C:\APLICACIONES\ProdIA\Repo ProdIA\frontend\routes\api.py` ← **nuevo en v2 (H9)** |
| MODIFICAR 6 | `C:\APLICACIONES\ProdIA\Repo ProdIA\frontend\static\js\multitab_shell.js` |
| CREAR | `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\tests\test_curva_ventana.py` |

⚠️ Los repos son **hermanos, no anidados**. Un cambio en `frontend\` NO entra en el commit de
`backend\`. Son dos commits, en dos repos distintos (ver §4.2).

### 0.3 Cómo se corren los comandos

Backend, desde `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend`, PowerShell normal, sin
administrador, **línea por línea**. Todo con `uv run`. El frontend no compila nada: es JS
servido tal cual por Flask, basta recargar el navegador con Ctrl+F5.

### 0.4 Convenciones que DEBES respetar

1. **`slots.py` es PURO**: sin BD, sin `date.today()`. El `techo` entra como parámetro.
2. **Match por TOKEN (`\b`), nunca substring** (regla AF-3.7 del módulo).
3. **Nada se asume en silencio**: todo relleno se declara en `asumido`/`defaults_asumidos`.
4. **`analisis/api.py` NO es solo del chat**: lo usa también el tablero. Cualquier función nueva
   es **aditiva**; no se cambia la firma de ninguna existente.

---

## 1. Hallazgos de la auditoría

Auditoría del 2026-09-03: lectura completa de `desempeno()` (`api.py:493-632`), `_ambito()`
(`api.py:397-450`), `curva_dia_mes()` (`api.py:2710-2733`), `ejecutar_n1dser()`
(`ejecutor.py:348-405`), `_panel_datos()` (`respuesta_cuantificar.py:105-130`),
`__cnCompProdCargar()` y `__cnDailyInto()` (`multitab_shell.js:3891` y `:1985`), más conteo de
call sites con grep sobre `app/` y `tests/`.

### 🔴 H1 — BLOQUEANTE: el panel NO se pinta con los datos que manda el ejecutor.

Este es el hallazgo que determina todo el plan. El flujo real, medido:

```
backend  ejecutar_n1dser() → res  → _panel_datos(res) → {"tipo":"cuant_dia_panel", "datos":{...}}
frontend recibe panel.datos        → __cnCompProdCargar(blk, datos, sufijo)   (:4050)
         └─ NO pinta con `datos`. Usa datos.entidad/nivel/PERIODO para lanzar
            DOS FETCH NUEVOS a INGESTA: /desempeno y /ejecutivo               (:3894-3899)
         └─ pinta con `dd` (= payload de /desempeno), vía __cnDailyInto(prod, host, dd, ...)
```

`__cnDailyInto` (`:1986-1987`) lee **`d.curva.series` y `d.curva.fechas`** — es decir, la curva
que `desempeno()` calculó **para el MES**, no la que trae el ejecutor. El campo `rango` que
`ejecutar_n1dser` emite (`ejecutor.py:400`) **no lo consume nadie en el pintado**.

**Consecuencia:** aunque el backend calcule perfectamente la ventana, el gráfico seguiría
mostrando el mes completo. **Cualquier plan que solo toque el ejecutor no cambia un solo pixel.**
Por eso este plan modifica `desempeno()` — es el único punto donde el eje X se decide de verdad.

### 🔴 H2 — `_ambito()` deriva `ini`/`fin` SIEMPRE de un mes calendario.

`api.py:446-450`: resuelve `maxd` (último día con dato), luego `per = _parse_periodo(...)` y
`y, mo = per if per else (maxd.year, maxd.month)`. De ahí salen `ini`/`fin` como los bordes del
**mes**. No existe forma de pedirle un rango arbitrario.

`desempeno()` usa esos `ini`/`fin` en el Módulo 2 (`api.py:551-563`):
```sql
WHERE d.fecha BETWEEN :ini AND :fin AND ...
```
**La consulta ya es por rango.** Solo hay que dejarle entrar unas fechas distintas. El cambio es
de plomería, no de SQL.

### 🔴 H3 — El KPI (gauge REAL/PPTO) es mensual por definición: NO puede acompañar una ventana.

`desempeno()` Módulo 1 (`api.py:530-544`) lee `core.fact_produccion_mes_ecp WHERE m.fecha = :fin`
— una fila **mensual**. El PPTO se carga por mes. Una ventana de 30 días que cruza julio-agosto
no tiene un PPTO único contra el cual compararse.

**Decisión cerrada:** la respuesta de ventana NO lleva gauge. Se reusa el nivel **N1DSER**, cuyo
panel (`cuant_dia_panel`) es **solo curva, sin gauge** — verificado en `_PANEL_TIPO`
(`respuesta_cuantificar.py:51-53`): N1/N2→`cuant_kpi` (con gauge), N1D/N1DSEL/N1DSER→
`cuant_dia_panel` (sin gauge). Esto elimina el problema de raíz sin escribir una línea.

### 🔴 H4 — La ventana debe cambiar `nivel_temporal`, y eso viola la NN-4 del plan anterior.

El plan `VENTANAS-TEMPORALES` fijó: *«Ningún nivel_temporal existente puede cambiar de valor»*.
Para que la pregunta llegue al panel de curva, la ventana **tiene** que elevar el nivel a N1DSER
(hoy cae a N1, por eso responde el gauge del mes).

**Esto NO contradice aquel plan: lo continúa.** Aquella regla protegía una entrega de cimiento
que debía ser invisible. Ahora se levanta **de forma acotada y medida**:

- La ventana eleva a N1DSER **solo si el nivel calculado era N1** (el default, «nadie reclamó
  esta pregunta»).
- Si el nivel es N2/N3/N4/N1D/N1DSEL/N1DSER, **NO se toca**: esos ya tienen dueño.

Esto se fija con tests explícitos (§3.6) y es la razón de que la especificación §3.2 vaya donde va.

### 🟡 H5 — «el último mes» es ambiguo y hoy resuelve como ventana de 1 mes.

`detectar_ventana("el ultimo mes", techo)` devuelve `{unidad:"mes", cantidad:1}`, con `ini` = día
1 del mes del techo. Con este plan, esa pregunta pasaría de responder el KPI mensual (hoy) a
responder una curva diaria — **un cambio de comportamiento visible** para una forma muy común.

**Decisión cerrada: `unidad == "mes"` NO eleva el nivel.** Solo `dia` y `semana` lo hacen. Razón:
«el último mes» / «los últimos 3 meses» son peticiones de **volumen mensual**, y el KPI/N1 que
responden hoy es la respuesta correcta. La ventana en meses queda declarada en el slot (por si
un plan futuro la usa) pero no cambia la respuesta. Esto acota el cambio a lo que el usuario
pidió: «los últimos 30 días».

### 🟡 H6 — `curva_dia_mes` tiene 1 solo call site real de producción, pero DOS ejecutores.

`grep` medido: `ejecutor.py:13` la importa como `_curva_ep`, y la usan **`ejecutar_n1dser`
(`:358`) y `ejecutar_n1dsel` (`:410`)**. Ambos vía el parámetro inyectable `_curva_fn`, que los
tests monkeypatchean (`test_cuantificar_dia.py:216, 271, 285`).

**No se toca `curva_dia_mes` ni su firma.** Se añade una función hermana (`curva_dia_rango`) y
`ejecutar_n1dser` elige entre las dos. `ejecutar_n1dsel` queda intacto.

### 🟢 H7 — El techo ya llega a producción para estas preguntas.

`respuesta_cuantificar.py:319-321` pide `techo_dia()` **solo si `menciona_dia(texto)`** es True.
El plan anterior añadió la rama de ventana a `menciona_dia`, así que «los últimos 30 días» **ya
consulta el techo real hoy**, y `slots["ventana"]` ya trae `ini`/`fin` verdaderos en producción.
No hay que tocar esa cadena: ya funciona.

### 🟢 H8 — El eje X del gráfico es el DÍA DEL MES como string, no la fecha ISO.

`multitab_shell.js:3867-3869` lo documenta: `__cnDailyPlot` mapea cada fecha a `"1"`,`"15"` con
`xaxis.type="category"`. Con una ventana que cruza meses (jul-25 → ago-23) el eje mostraría
`25,26,...,31,1,2,...,23` — **dos días «1» no, pero sí un salto confuso sin decir de qué mes es
cada tramo**. Por eso §3.6 cambia la etiqueta del eje a `DD/MM` cuando hay ventana.

---

## 1-BIS. Hallazgos de la SEGUNDA pasada (v2) — los que salvan el plan

### 🔴 H9 — BLOQUEANTE: el navegador no habla con INGESTA. Habla con un proxy Flask que FILTRA.

CLAUDE.md §2 lo dice y la v1 lo ignoró: *«El navegador nunca habla con el 5030»*. Medido en
`frontend\routes\api.py:267-283`:

```python
@api_bp.route("/analisis/desempeno")
def analisis_desempeno():
    params = {}
    ent = request.args.get("entidad")
    if ent: params["entidad"] = ent
    seg = request.args.get("segmento")
    if seg: params["segmento"] = seg
    for _k in ("nivel", "periodo"):        # ← LISTA BLANCA CERRADA
        _v = request.args.get(_k)
        if _v: params[_k] = _v
    return _analisis_proxy_cacheado("/analisis/desempeno", params, 45)
```

El proxy **reconstruye** los parámetros desde una lista blanca. `v_ini`/`v_fin` enviados por el
JS **nunca llegarían a FastAPI**: se caen en silencio y `desempeno()` respondería el mes.

**La v1 habría pasado todos sus tests de Python y no habría cambiado un solo pixel.** Es
exactamente el escenario de la R3 de CLAUDE.md §10.4: build verde, feature rota.

### 🔴 H10 — BLOQUEANTE: la caché del proxy mezcla la ventana con el mes.

`_analisis_proxy_cacheado` (`routes/api.py:226-250`) cachea 45 s con esta clave:

```python
clave = ruta + "?" + "&".join(f"{k}={params[k]}" for k in sorted(params) if k not in _CLAVE_IGNORAR)
```

La clave se arma con **los params ya filtrados**. Si la ventana no viaja como parámetro, la
pregunta «últimos 30 días» y la pregunta «día a día en agosto» sobre CASTILLA producen **la misma
clave** → la segunda recibe la curva de la primera durante 45 s.

Y hay una segunda capa de caché **en el navegador** (`__cnDesempCache`, keyed por
`__cnAnzCacheKey`), con el mismo defecto.

**Por eso la ventana debe entrar en las DOS claves de caché**, no solo en la query.

### 🟠 H11 — La construcción de `qs` de la v1 producía una URL inválida en el caso global.

`__cnAnzQS` (`multitab_shell.js:3779-3785`) devuelve `""` cuando no hay entidad/nivel/periodo.
La v1 hacía `qs + vqs` con `vqs = "&v_ini=..."` → `"&v_ini=..."` **sin `?`**. La §3.6 v2 lo
resuelve construyendo la query con un array, no con concatenación condicional.

### 🟡 H12 — `periodo` contaminado apagaba `periodo_ok`.

`_ambito:450` calcula `periodo_ok = bool(per) or _periodo_es_default(periodo)`. La v1 mandaba
`periodo="2026-07-25 a"` (por el `split()` sobre el `mes_label` nuevo), que no es default ni
parseable → `periodo_ok=False` viaja en el payload. No rompe el pintado, pero es un flag que
significa «no supe honrar el periodo pedido» y quedaría encendido sin motivo real.

**Corrección v2:** con ventana, `_panel_datos` emite `periodo: None`. El mes del KPI lo resuelve
`_ambito` por defecto (el del techo), que es lo correcto — y `periodo_ok` queda `True`.

### 🟢 H13 — El proxy ya tiene el idiom para esto: `_CLAVE_IGNORAR`.

`routes/api.py:223` → `_CLAVE_IGNORAR = ("pulir",)`, y `_analisis_es_cacheable` evita cachear
errores. La v2 **no inventa mecanismo**: añade `v_ini`/`v_fin` a la lista blanca y los deja
entrar en la clave (a diferencia de `pulir`, aquí SÍ deben distinguir la entrada).

---

## 2. Estado actual

| Pregunta | Nivel hoy | Panel hoy | Eje X |
|---|---|---|---|
| «cuánto produjo Castilla» | N1 | `cuant_kpi` (gauge + curva) | mes completo |
| «...en los últimos 30 días» | **N1** ← el problema | `cuant_kpi` (gauge + curva) | **mes completo** |
| «...día a día en junio» | N1DSER | `cuant_dia_panel` (solo curva) | mes de junio |
| «el mejor día» | N1DSEL | `cuant_dia_panel` | mes del techo |

**Objetivo:** que la fila 2 pase a `N1DSER` con `cuant_dia_panel` y eje X = `[ini, fin]` de la
ventana.

---

## 3. Especificación

### 3.1 MODIFICAR `api.py` — función nueva `curva_dia_rango`

**Ubicación:** inmediatamente **después** del final de `curva_dia_mes` (la línea
`        return [(f, float(v or 0)) for f, v in c.execute(t, p)]`, `api.py:2733`) y antes de lo
que siga.

```python
def curva_dia_rango(entidad: str, ini, fin, producto: str,
                    nivel: str | None = None) -> list:
    """Serie diaria [(date, float)] de UN producto entre dos fechas ARBITRARIAS.

    [2026-09-03 · CURVA-VENTANA] Gemela de `curva_dia_mes` (:2710), que solo sabe de meses
    calendario. Una ventana móvil («los últimos 30 días») cruza el borde del mes, así que
    necesita bordes explícitos. La QUERY es la misma —ya era `BETWEEN :ini AND :fin`—; lo
    único que cambia es de dónde salen esas dos fechas.

    `ini`/`fin` son `date` o 'YYYY-MM-DD'. `producto` en MAYÚSCULAS.
    🔑 No se toca `curva_dia_mes`: la usan `ejecutar_n1dser` Y `ejecutar_n1dsel`, y cambiarle
       la firma obligaría a tocar los dos y sus tests. Una hermana cuesta menos y no arriesga.
    """
    eng = get_engine()
    with eng.connect() as c:
        r = _amb_dia(c, entidad, nivel)
        if r is None:
            return []
        whr, params, ids = r
        p = dict(params)
        p.update({"ini": str(ini), "fin": str(fin), "p": producto.upper()})
        t = sa.text(f"""
            SELECT d.fecha, SUM(d.volumen) vol
            FROM core.fact_produccion_dia_ecp d
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = d.tipo_producto_id
            WHERE d.fecha BETWEEN :ini AND :fin AND UPPER(tp.nombre) = :p AND {whr}
            GROUP BY d.fecha ORDER BY d.fecha""")
        if ids:
            t = t.bindparams(sa.bindparam("ids", expanding=True))
        return [(f, float(v or 0)) for f, v in c.execute(t, p)]
```

### 3.2 MODIFICAR `api.py` — `desempeno()` acepta `ini`/`fin` explícitos

Este es el cambio de H1: sin él, el gráfico no cambia.

**Edición A.** Localiza la firma (`api.py:493-494`):

```python
def desempeno(entidad: str | None = Query(None), segmento: str = Query("ecp"),
              nivel: str | None = Query(None), periodo: str | None = Query(None)):
```

Reemplázala por:

```python
def desempeno(entidad: str | None = Query(None), segmento: str = Query("ecp"),
              nivel: str | None = Query(None), periodo: str | None = Query(None),
              # [2026-09-03 · CURVA-VENTANA] Ventana móvil explícita para la CURVA DIARIA.
              # Cuando llegan, la curva (Módulo 2) se acota a [v_ini, v_fin] en vez de al mes.
              # 🔑 Los KPIs mensuales (Módulo 1) y el ritmo del año (Módulo 3) NO cambian: el
              #    PPTO se carga por MES y una ventana que cruza meses no tiene un PPTO único
              #    contra el cual compararse (H3). Se acota SOLO lo que es de grano día.
              v_ini: str | None = Query(None), v_fin: str | None = Query(None)):
```

**Edición B.** Localiza (`api.py:513`):

```python
        y, mo, dim, ini, fin = amb["y"], amb["mo"], amb["dim"], amb["ini"], amb["fin"]
```

Reemplázala por:

```python
        y, mo, dim, ini, fin = amb["y"], amb["mo"], amb["dim"], amb["ini"], amb["fin"]
        # [2026-09-03 · CURVA-VENTANA] Bordes de la CURVA. Por defecto son los del mes (`ini`/
        # `fin` de _ambito); con ventana, los que mandó el llamador. Se usan SOLO en el Módulo 2.
        # Variables aparte a propósito: si se reasignara `ini`/`fin` se contaminaría el Módulo 1
        # (`pm["fin"] = fin` en :531 elige la FILA MENSUAL) y el KPI pasaría a leer el mes
        # equivocado — un bug silencioso de la familia del periodo ignorado.
        c_ini, c_fin = (v_ini or ini), (v_fin or fin)
        ventana_activa = bool(v_ini and v_fin)
```

**Edición C.** Localiza el bloque del Módulo 2 (`api.py:556-558`):

```python
            pd = dict(base); pd["ini"] = ini; pd["fin"] = fin
```

Reemplázala por:

```python
            pd = dict(base); pd["ini"] = c_ini; pd["fin"] = c_fin
```

**Edición D.** Localiza el `return` final de `desempeno()` (`api.py:620-632`) y añade **una sola
clave**, justo después de la línea `"curva": {"fechas": curva_fechas, "series": series},`:

```python
            "curva": {"fechas": curva_fechas, "series": series},
            # [2026-09-03 · CURVA-VENTANA] Declara al frontend que la curva NO es la del mes.
            # Sin esto el pintor titularía "del mes de agosto" sobre una curva de 30 días a
            # caballo entre dos meses — exactamente el tipo de afirmación falsa que el proyecto
            # persigue. `None` cuando no hay ventana: el comportamiento de siempre.
            "curva_ventana": ({"ini": str(c_ini), "fin": str(c_fin)} if ventana_activa else None),
```

⚠️ **NO toques** `pm["fin"] = fin` (Módulo 1), ni `pr["yy"] = y` (Módulo 3), ni el bloque
`ritmo` completo. El KPI y el promedio del año siguen siendo mensuales, a propósito (H3).

### 3.3 MODIFICAR `slots.py` — la ventana en DÍAS/SEMANAS eleva el nivel

**Ubicación:** dentro de `extraer_slots`, en el bloque que el plan anterior insertó. Localiza:

```python
    ventana = detectar_ventana(texto, techo)

    per = _periodo_texto(texto)
```

Reemplázalo por:

```python
    ventana = detectar_ventana(texto, techo)

    # [2026-09-03 · CURVA-VENTANA] La ventana en DÍAS/SEMANAS eleva N1 → N1DSER: la respuesta
    # correcta a «los últimos 30 días» es la CURVA de esos 30 días, no el KPI del mes (que es lo
    # que se respondía, con el rótulo del mes, sin declarar que ignoraba la ventana).
    #
    # 🔑 Solo desde N1, el default. N2/N3/N4/N1D/N1DSEL/N1DSER ya tienen dueño y NO se tocan:
    #    «el acumulado del año en los últimos 30 días» sigue siendo N2. La ventana solo reclama
    #    las preguntas que NADIE reclamó.
    # 🔑 Solo unidad `dia`/`semana` (H5). «el último mes» / «los últimos 3 meses» piden VOLUMEN
    #    mensual y el KPI que hoy responden es correcto; convertirlos en curva sería cambiarle
    #    la respuesta a una forma muy común sin que nadie lo haya pedido.
    if ventana is not None and nivel == "N1" and ventana["unidad"] in ("dia", "semana"):
        nivel = "N1DSER"

    per = _periodo_texto(texto)
```

⚠️ Este bloque va **después** de `detectar_dia` y del bloque `sdia` (ya lo está por construcción
del plan anterior), de modo que un día concreto o un selector siguen ganando.

### 3.4 MODIFICAR `ejecutor.py` — `ejecutar_n1dser` acepta la ventana

**Edición A.** Localiza el import (`ejecutor.py:12-13`):

```python
from app.features.analisis.api import (desempeno as _desempeno_ep, _estado, escenario_mes as _escenario_ep,
                                       produccion_dia as _prod_dia_ep, curva_dia_mes as _curva_ep)
```

Reemplázalo por:

```python
from app.features.analisis.api import (desempeno as _desempeno_ep, _estado, escenario_mes as _escenario_ep,
                                       produccion_dia as _prod_dia_ep, curva_dia_mes as _curva_ep,
                                       curva_dia_rango as _curva_rango_ep)
```

**Edición B.** Localiza en `ejecutar_n1dser` (`ejecutor.py:357-364`):

```python
    fn = _curva_fn or _curva_ep
    rech = _rechazo_comun(resuelta, slots)
    if rech:
        return rech
    ser = slots.get("serie_dia") or {}
    producto = slots["producto"]
    pts = [(f, v) for f, v in fn(resuelta["valor"], ser["anio"], ser["mes"],
                                 _PROD_MAP[producto], nivel=resuelta.get("nivel")) if v > 0]
    if not pts:
        return {"aplica": False, "texto": (
            f"No tengo curva diaria de {producto} para «{resuelta['valor']}» en "
            f"{_MESES_ES_L[ser['mes']]} {ser['anio']}.")}
```

Reemplázalo por:

```python
    fn = _curva_fn or _curva_ep
    rech = _rechazo_comun(resuelta, slots)
    if rech:
        return rech
    ser = slots.get("serie_dia") or {}
    ven = slots.get("ventana") or {}
    producto = slots["producto"]
    # [2026-09-03 · CURVA-VENTANA] Dos orígenes para la MISMA curva: un mes calendario
    # (`serie_dia`, «día a día en junio») o una ventana móvil (`ventana`, «los últimos 30 días»).
    # 🔑 La ventana solo se usa si NO hay `serie_dia`: si el usuario nombró un mes, ese mes manda.
    if ven and not ser:
        pts_all = (_curva_rango_fn or _curva_rango_ep)(
            resuelta["valor"], ven["ini"], ven["fin"], _PROD_MAP[producto],
            nivel=resuelta.get("nivel"))
        pts = [(f, v) for f, v in pts_all if v > 0]
        if not pts:
            return {"aplica": False, "texto": (
                f"No tengo curva diaria de {producto} para «{resuelta['valor']}» "
                f"entre {ven['ini']} y {ven['fin']}.")}
    else:
        pts = [(f, v) for f, v in fn(resuelta["valor"], ser["anio"], ser["mes"],
                                     _PROD_MAP[producto], nivel=resuelta.get("nivel")) if v > 0]
        if not pts:
            return {"aplica": False, "texto": (
                f"No tengo curva diaria de {producto} para «{resuelta['valor']}» en "
                f"{_MESES_ES_L[ser['mes']]} {ser['anio']}.")}
```

**Edición C.** Cambia la firma de `ejecutar_n1dser` (`ejecutor.py:348`):

```python
def ejecutar_n1dser(resuelta: dict, slots: dict, _curva_fn=None) -> dict:
```

por:

```python
def ejecutar_n1dser(resuelta: dict, slots: dict, _curva_fn=None, _curva_rango_fn=None) -> dict:
```

**Edición D.** Localiza en el `return` de `ejecutar_n1dser` (`ejecutor.py:396-399`):

```python
        "mes_label": f"{_MESES_ES_L[ser['mes']]} {ser['anio']}",
        "dias_con_dato": len(pts),
        "rango": [pts[0][0].isoformat(), pts[-1][0].isoformat()],
```

Reemplázalo por:

```python
        # [2026-09-03 · CURVA-VENTANA] Con ventana no hay UN mes que rotular: la curva puede ir
        # de julio a agosto. Se rotula el RANGO REAL con dato, que es lo que el gráfico muestra.
        "mes_label": (f"{pts[0][0].isoformat()} a {pts[-1][0].isoformat()}"
                      if (ven and not ser) else f"{_MESES_ES_L[ser['mes']]} {ser['anio']}"),
        "ventana": ({"unidad": ven["unidad"], "cantidad": ven["cantidad"],
                     "ini": ven["ini"], "fin": ven["fin"]} if (ven and not ser) else None),
        "dias_con_dato": len(pts),
        "rango": [pts[0][0].isoformat(), pts[-1][0].isoformat()],
```

**Edición E.** En el mismo `ejecutar_n1dser`, localiza el aviso del periodo asumido
(`ejecutor.py:388-390`):

```python
    if any(str(a).startswith("periodo=") for a in (ser.get("asumido") or [])):
        avisos.append(f"No me dijiste el mes, así que tomé {_MESES_ES_L[ser['mes']]} "
                      f"{ser['anio']} (el último con reporte diario).")
```

Reemplázalo por:

```python
    if any(str(a).startswith("periodo=") for a in (ser.get("asumido") or [])):
        avisos.append(f"No me dijiste el mes, así que tomé {_MESES_ES_L[ser['mes']]} "
                      f"{ser['anio']} (el último con reporte diario).")
    # [2026-09-03 · CURVA-VENTANA] La ventana se ancla al último día CON REPORTE, no al reloj.
    # Se declara siempre: el usuario dijo «últimos 30 días» pensando en hoy, y el dato va ~100
    # días atrás. Callarlo sería dejarle creer que la curva llega hasta ayer.
    if ven and not ser:
        avisos.append(f"«Últimos {ven['cantidad']} {ven['unidad']}s» cuenta hacia atrás desde "
                      f"{ven['fin']}, el último día con reporte diario.")
```

### 3.5 MODIFICAR `respuesta_cuantificar.py` — pasar la ventana al panel

Localiza el bloque N1DSER de `_panel_datos` (`respuesta_cuantificar.py:114-126`) y sustituye
**solo** estas dos líneas:

```python
            "periodo": f"{_s[0]} {_s[1]}" if len(_s) > 1 else res["mes_label"],
            "productos": [_PROD_DIM.get(res["producto"], "CRUDO")],
            "dia_marcado": None,
```

por:

```python
            "periodo": f"{_s[0]} {_s[1]}" if len(_s) > 1 else res["mes_label"],
            "productos": [_PROD_DIM.get(res["producto"], "CRUDO")],
            "dia_marcado": None,
            # [2026-09-03 · CURVA-VENTANA] El frontend NO pinta con estos datos: los usa para
            # lanzar su propio fetch a /desempeno (multitab_shell.js:3891). Por eso la ventana
            # tiene que viajar hasta aquí — es lo que el JS convertirá en &v_ini=&v_fin=.
            "ventana": res.get("ventana"),
```

**Edición 2 (v2, H12).** En ese mismo bloque, localiza la línea del `periodo`:

```python
            "periodo": f"{_s[0]} {_s[1]}" if len(_s) > 1 else res["mes_label"],
```

Reemplázala por:

```python
            # [2026-09-03 · CURVA-VENTANA v2, H12] Con ventana NO se manda `periodo`. `mes_label`
            # pasa a ser "2026-07-25 a 2026-08-23" y el split de arriba daría "2026-07-25 a",
            # una cadena que `_parse_periodo` no reconoce → `periodo_ok=False` viajaría en el
            # payload significando «no supe honrar el periodo», que sería falso: el KPI mensual
            # DEBE resolverse por defecto al mes del techo (H3). Con None, `_ambito` hace
            # exactamente eso y `periodo_ok` queda True.
            "periodo": (None if res.get("ventana")
                        else (f"{_s[0]} {_s[1]}" if len(_s) > 1 else res["mes_label"])),
```

⚠️ `_s = res["mes_label"].split()` (línea 115) **no se toca**: sigue calculándose y simplemente
no se usa en la rama de ventana.

### 3.6 MODIFICAR `frontend\routes\api.py` — el proxy debe DEJAR PASAR la ventana

🔴 **Sin esta sección el plan no hace nada (H9).** El navegador llama a Flask, no a INGESTA, y
Flask reconstruye los parámetros desde una lista blanca cerrada.

Localiza (`frontend\routes\api.py:277-282`):

```python
        for _k in ("nivel", "periodo"):
            _v = request.args.get(_k)
            if _v:
                params[_k] = _v
        return _analisis_proxy_cacheado("/analisis/desempeno", params, 45)
```

Reemplázalo por:

```python
        # [2026-09-03 · CURVA-VENTANA] +v_ini/v_fin: la ventana móvil de la curva diaria
        # («los últimos 30 días»). Esta lista es una LISTA BLANCA CERRADA: un parámetro que no
        # esté aquí NO llega a INGESTA y se pierde en silencio — el navegador nunca habla con
        # el 5030 (CLAUDE.md §2), así que este es el único punto por donde puede pasar.
        # 🔑 Entran TAMBIÉN en la clave de caché de `_analisis_proxy_cacheado` (se arma con
        #    estos `params`), y eso es DELIBERADO: sin ellos, «los últimos 30 días» y «día a
        #    día en agosto» sobre la misma entidad compartirían entrada y la segunda pregunta
        #    recibiría la curva de la primera durante los 45 s del TTL.
        for _k in ("nivel", "periodo", "v_ini", "v_fin"):
            _v = request.args.get(_k)
            if _v:
                params[_k] = _v
        return _analisis_proxy_cacheado("/analisis/desempeno", params, 45)
```

⚠️ **No añadas `v_ini`/`v_fin` a `_CLAVE_IGNORAR`** (`routes/api.py:223`). Ahí vive `pulir`,
que se excluye de la clave a propósito; la ventana es lo contrario: **debe** distinguir la
entrada de caché (H10).

⚠️ **No toques** la ruta `/analisis/ejecutivo`: es mensual y no entiende la ventana.

### 3.7 MODIFICAR `multitab_shell.js` — propagar la ventana y rotular el eje

**Edición A.** Localiza `__cnCompProdCargar` (`multitab_shell.js:3891-3897`):

```javascript
  function __cnCompProdCargar(blk, datos, sufijo) {
    var host = blk.querySelector(".cn-stk__body");
    if (!host) return;
    var entidad = datos.entidad, nivel = datos.nivel, periodo = datos.periodo;
    var key = __cnAnzCacheKey(entidad, nivel, periodo);
    var qs = __cnAnzQS(entidad, nivel, periodo);
    var qsEj = qs + (qs ? "&" : "?") + "pulir=false";
```

Reemplázalo por:

```javascript
  function __cnCompProdCargar(blk, datos, sufijo) {
    var host = blk.querySelector(".cn-stk__body");
    if (!host) return;
    var entidad = datos.entidad, nivel = datos.nivel, periodo = datos.periodo;
    // [2026-09-03 · CURVA-VENTANA] Ventana móvil («los últimos 30 días»): la curva se pide
    // acotada a [ini,fin] en vez de al mes.
    // 🔑 v2/H10: va TAMBIÉN en la clave de caché del navegador. `__cnDesempCache` es
    //    compartida con el tablero y con las demás preguntas; sin distinguir la ventana, una
    //    pregunta por ventana y otra por el mes de la misma entidad comparten entrada y la
    //    segunda pinta la curva de la primera.
    // 🔑 v2/H11: la query se arma con un ARRAY, no concatenando. `__cnAnzQS` devuelve "" en
    //    el caso global (sin entidad/nivel/periodo) y un `qs + "&v_ini=…"` habría producido
    //    una URL sin "?" — inválida, y solo en ese caso.
    var ven = datos.ventana || null;
    var key = __cnAnzCacheKey(entidad, nivel, periodo) + (ven ? ("|v:" + ven.ini + ".." + ven.fin) : "");
    var _qp = [];
    if (entidad) _qp.push("entidad=" + encodeURIComponent(entidad));
    if (nivel) _qp.push("nivel=" + encodeURIComponent(nivel));
    if (periodo) _qp.push("periodo=" + encodeURIComponent(periodo));
    if (ven) {
      _qp.push("v_ini=" + encodeURIComponent(ven.ini));
      _qp.push("v_fin=" + encodeURIComponent(ven.fin));
    }
    var qs = _qp.length ? ("?" + _qp.join("&")) : "";
    // El fetch a /ejecutivo va SIN la ventana a propósito: ese endpoint es mensual y no la
    // entiende. Conserva la query de siempre (__cnAnzQS), no la de arriba.
    var _qsBase = __cnAnzQS(entidad, nivel, periodo);
    var qsEj = _qsBase + (_qsBase ? "&" : "?") + "pulir=false";
```

**Edición B.** Localiza en `__cnDailyInto` (`multitab_shell.js:1993`):

```javascript
    var mesNom = (d.mes && d.mes.nombre) || "";   // mes dinámico = último mes de datos cargados
```

Reemplázala por:

```javascript
    var mesNom = (d.mes && d.mes.nombre) || "";   // mes dinámico = último mes de datos cargados
    // [2026-09-03 · CURVA-VENTANA] `curva_ventana` lo emite /desempeno cuando la curva NO es la
    // del mes. Rotular "del mes de agosto" sobre 30 días a caballo entre julio y agosto sería
    // afirmar algo falso sobre lo que el usuario está viendo.
    var cvVen = d.curva_ventana || null;
```

**Edición C.** Localiza (`multitab_shell.js:2020-2021`):

```javascript
    var delMes = mesNom ? (' del mes de ' + esc(mesNom)) : ' del mes';
    var hd = esc(nombre) + ' · producción diaria' + delMes + (prom2026 != null ? ' vs promedio diario 2026' : '');
```

Reemplázalo por:

```javascript
    var delMes = cvVen
      ? (' · ' + __cnFechaCorta(cvVen.ini) + ' a ' + __cnFechaCorta(cvVen.fin))
      : (mesNom ? (' del mes de ' + esc(mesNom)) : ' del mes');
    var hd = esc(nombre) + ' · producción diaria' + delMes + (prom2026 != null ? ' vs promedio diario 2026' : '');
```

**Edición D.** Añade el helper `__cnFechaCorta` **inmediatamente antes** de
`function __cnDailyInto` (`multitab_shell.js:1985`):

```javascript
  // [2026-09-03 · CURVA-VENTANA] "2026-07-25" -> "25/07". Sin Date: `new Date("2026-07-25")`
  // parsea como UTC y en un navegador al oeste de Greenwich devuelve el día ANTERIOR — el
  // clásico off-by-one de zona horaria, que aquí correría la etiqueta del rango un día.
  function __cnFechaCorta(iso) {
    var s = String(iso || "");
    return (s.length >= 10) ? (s.slice(8, 10) + "/" + s.slice(5, 7)) : s;
  }
```

**Edición E.** El eje X con ventana debe decir de qué mes es cada día (H8). Localiza en
`__cnDailyInto` la llamada a `__cnDailyPlot` — está tras `var promMes = ...`
(`multitab_shell.js:2029`) — y **NO la modifiques**. En su lugar, localiza:

```javascript
    var vd = serie.filter(function (v) { return v != null && v > 0; });
```

y añade **justo antes**:

```javascript
    // [2026-09-03 · CURVA-VENTANA] Con ventana el eje X pasa a DD/MM. `__cnDailyPlot` mapea la
    // fecha al día del mes como categoría (:3867), así que en una ventana jul→ago saldría
    // "25,26,...,31,1,2,...,23" sin decir de qué mes es cada tramo. Se reescriben las etiquetas
    // ANTES de pintar; la serie de valores no se toca.
    if (cvVen && fechas.length) {
      fechas = fechas.map(function (f) { return __cnFechaCorta(f); });
    }
```

⚠️ `fechas` se declara con `var` en `:1987`, así que reasignarla aquí es legal y local a la
función. **No cambies `__cnDailyPlot`**: la comparte el panel de Focos.

### 3.8 CREAR `tests/test_curva_ventana.py`

```python
"""test_curva_ventana.py — la ventana móvil llega hasta la curva (plan CURVA-VENTANA, 2026-09-03).

Sin BD: la curva se inyecta con `_curva_rango_fn`, igual que test_cuantificar_dia.py hace con
`_curva_fn`. Lo que se mide es el CABLEADO, no el dato.
"""
import datetime

import pytest

from app.features.consulta_v2.cuantificar.slots import extraer_slots
from app.features.consulta_v2.cuantificar.ejecutor import ejecutar_n1dser

_TECHO = datetime.date(2026, 8, 23)
_ENT = {"valor": "CASTILLA", "nivel": "campo", "rama": "A", "zoom": []}


def _curva_falsa(_ent, ini, fin, _prod, nivel=None):
    """30 días con valor, del 2026-07-25 al 2026-08-23."""
    d0 = datetime.date.fromisoformat(str(ini))
    d1 = datetime.date.fromisoformat(str(fin))
    out, d = [], d0
    while d <= d1:
        out.append((d, 215000.0))
        d += datetime.timedelta(days=1)
    return out


# ---------------- el nivel se eleva (y solo cuando debe) ----------------

@pytest.mark.parametrize("frase", [
    "cuanto produjo Castilla en los ultimos 30 dias",
    "produccion de Castilla los ultimos 7 dias",
    "como viene Castilla en las ultimas 6 semanas",
])
def test_ventana_dias_semanas_eleva_a_n1dser(frase):
    assert extraer_slots(frase, techo=_TECHO)["nivel_temporal"] == "N1DSER"


@pytest.mark.parametrize("frase", [
    "cuanto produjo Castilla el ultimo mes",
    "cuanto produjo Castilla en los ultimos 3 meses",
])
def test_ventana_en_meses_NO_eleva(frase):
    """H5: «el último mes» pide volumen mensual; el KPI que responde hoy es correcto."""
    s = extraer_slots(frase, techo=_TECHO)
    assert s["nivel_temporal"] == "N1"
    assert s["ventana"] is not None          # se detecta, pero no manda


@pytest.mark.parametrize("frase,nivel", [
    ("acumulado de Castilla en los ultimos 30 dias", "N2"),
    ("produccion de Castilla mes a mes en los ultimos 30 dias", "N3"),
    ("como vario Castilla mes a mes en los ultimos 30 dias", "N4"),
    ("el mejor dia de Castilla de los ultimos 30 dias", "N1DSEL"),
])
def test_ventana_no_le_roba_a_los_niveles_con_dueno(frase, nivel):
    """🔑 REGRESIÓN CENTRAL. La ventana solo reclama lo que NADIE reclamó (H4)."""
    assert extraer_slots(frase, techo=_TECHO)["nivel_temporal"] == nivel


def test_dia_a_dia_con_mes_sigue_siendo_del_mes():
    s = extraer_slots("produccion dia a dia de Castilla en junio", techo=_TECHO)
    assert s["nivel_temporal"] == "N1DSER" and s["serie_dia"] is not None


# ---------------- el ejecutor usa la ventana ----------------

def test_ejecutor_usa_la_curva_por_rango():
    s = extraer_slots("cuanto produjo Castilla en los ultimos 30 dias", techo=_TECHO)
    r = ejecutar_n1dser(_ENT, s, _curva_rango_fn=_curva_falsa)
    assert r["aplica"] is True
    assert r["dias_con_dato"] == 30
    assert r["rango"] == ["2026-07-25", "2026-08-23"]


def test_ejecutor_emite_la_ventana_para_el_panel():
    s = extraer_slots("cuanto produjo Castilla en los ultimos 30 dias", techo=_TECHO)
    r = ejecutar_n1dser(_ENT, s, _curva_rango_fn=_curva_falsa)
    assert r["ventana"] == {"unidad": "dia", "cantidad": 30,
                            "ini": "2026-07-25", "fin": "2026-08-23"}


def test_label_no_miente_sobre_el_mes():
    """Con ventana NO se rotula un mes: la curva cruza julio y agosto."""
    s = extraer_slots("cuanto produjo Castilla en los ultimos 30 dias", techo=_TECHO)
    r = ejecutar_n1dser(_ENT, s, _curva_rango_fn=_curva_falsa)
    assert r["mes_label"] == "2026-07-25 a 2026-08-23"
    assert "agosto" not in r["mes_label"]


def test_avisa_que_cuenta_desde_el_ultimo_reporte():
    """El usuario dice «últimos 30 días» pensando en hoy; el dato va ~100 días atrás."""
    s = extraer_slots("cuanto produjo Castilla en los ultimos 30 dias", techo=_TECHO)
    r = ejecutar_n1dser(_ENT, s, _curva_rango_fn=_curva_falsa)
    assert any("2026-08-23" in a for a in r["avisos"])


def test_sin_datos_en_la_ventana_declina_honesto():
    s = extraer_slots("cuanto produjo Castilla en los ultimos 30 dias", techo=_TECHO)
    r = ejecutar_n1dser(_ENT, s, _curva_rango_fn=lambda *a, **k: [])
    assert r["aplica"] is False and "2026-07-25" in r["texto"]


def test_mes_nombrado_gana_a_la_ventana():
    """Si hay `serie_dia`, manda el mes: no se usa la ventana."""
    s = extraer_slots("produccion dia a dia de Castilla en junio", techo=_TECHO)
    llamadas = []
    def _rango_espia(*a, **k):
        llamadas.append(a)
        return []
    ejecutar_n1dser(_ENT, s, _curva_fn=lambda *a, **k: [(datetime.date(2026, 6, 1), 1.0)],
                    _curva_rango_fn=_rango_espia)
    assert llamadas == []


# ---------------- el panel transporta la ventana ----------------

def test_panel_datos_lleva_la_ventana():
    from app.features.consulta_v2.respuesta_cuantificar import _panel_datos
    s = extraer_slots("cuanto produjo Castilla en los ultimos 30 dias", techo=_TECHO)
    r = ejecutar_n1dser(_ENT, s, _curva_rango_fn=_curva_falsa)
    p = _panel_datos(r)
    assert p["ventana"]["ini"] == "2026-07-25" and p["ventana"]["fin"] == "2026-08-23"


def test_panel_de_mes_no_lleva_ventana():
    from app.features.consulta_v2.respuesta_cuantificar import _panel_datos
    s = extraer_slots("produccion dia a dia de Castilla en junio", techo=_TECHO)
    r = ejecutar_n1dser(_ENT, s,
                        _curva_fn=lambda *a, **k: [(datetime.date(2026, 6, d), 1000.0)
                                                   for d in range(1, 31)])
    assert _panel_datos(r)["ventana"] is None
```

---

## 4. Orden de ejecución

| # | Acción | Archivo | Ref |
|---|---|---|---|
| 0 | **Línea base** (§6.1, comandos 2 y 3) ANTES de editar | — | §6.1 |
| 1 | `curva_dia_rango` | `analisis/api.py` | §3.1 |
| 2 | `desempeno()` acepta `v_ini`/`v_fin` (4 ediciones) | `analisis/api.py` | §3.2 |
| 3 | La ventana eleva el nivel | `cuantificar/slots.py` | §3.3 |
| 4 | `ejecutar_n1dser` usa la ventana (5 ediciones) | `cuantificar/ejecutor.py` | §3.4 |
| 5 | La ventana viaja al panel (2 ediciones) | `respuesta_cuantificar.py` | §3.5 |
| 6 | 🔴 **El proxy deja pasar `v_ini`/`v_fin`** | `frontend\routes\api.py` | §3.6 |
| 7 | Propagar y rotular (5 ediciones) | `frontend\...\multitab_shell.js` | §3.7 |
| 8 | Crear los tests | `tests/test_curva_ventana.py` | §3.8 |
| 9 | Validación estática | — | §6.1 |

⚠️ **El paso 6 no es opcional ni cosmético.** Es el único punto por el que la ventana puede
llegar a FastAPI. Sin él, los pasos 1-5 pasan todos los tests y **el gráfico no cambia** (H9).

### 4.2 Los commits son DOS

Los pasos 1-5 y 8 son del repo `backend`; los pasos **6 y 7** son del repo `frontend`. **No se
pueden commitear juntos.** Al terminar, pregunta al usuario antes de commitear nada.

⚠️ **Los dos repos deben desplegarse juntos.** Si sube solo el backend, `desempeno()` acepta
`v_ini`/`v_fin` pero nadie se los manda → comportamiento de hoy (inocuo). Si sube solo el
frontend, el JS manda parámetros que FastAPI ignora → también el de hoy (inocuo). **Ninguna
mitad rompe nada por sí sola**, pero la feature solo existe con las dos.

---

## 5. Reglas no negociables

- **NN-1.** No cambies la firma de `curva_dia_mes` ni de `_ambito`. Añade, no modifiques (H6).
- **NN-2.** En `desempeno()`, **NO reasignes `ini`/`fin`**. Usa `c_ini`/`c_fin` solo en el
  Módulo 2. Reasignarlas contamina el KPI mensual (H3) — bug silencioso.
- **NN-3.** El gauge REAL/PPTO NO acompaña a una ventana. No intentes "arreglar" el KPI para
  que cuadre con la ventana: no existe PPTO para un rango arbitrario.
- **NN-4.** La ventana eleva el nivel **solo desde N1** y **solo en `dia`/`semana`** (H4, H5).
- **NN-5.** `slots.py` sigue puro: sin BD, sin `date.today()`.
- **NN-6.** No toques `__cnDailyPlot` ni `__cnPaintFocoStk`: los comparte el panel de Focos.
- **NN-7.** Si una línea del plan no calza con el código real, **DETENTE y repórtalo.**
- **NN-8 (v2/H9).** El paso 6 (proxy Flask) es **obligatorio**. No lo declares "opcional" ni lo
  saltes porque los tests de Python ya pasan: los tests no cruzan el proxy.
- **NN-9 (v2/H10).** La ventana entra en las **dos** claves de caché (proxy Flask y
  `__cnDesempCache` del navegador). No la metas en `_CLAVE_IGNORAR`.
- **NN-10 (v2).** No toques la ruta `/analisis/ejecutivo` ni su query (`qsEj`): es mensual.

---

## 6. Validación

### 6.1 Estática — la ejecuta el EXECUTOR

Desde `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend`, línea por línea:

```powershell
uv run pytest tests/test_curva_ventana.py -q
```
→ Esperado: **todos PASAN** (~18 casos).

```powershell
uv run pytest tests/test_cuantificar.py tests/test_cuantificar_dia.py tests/test_cuantificar_ranking.py tests/test_analizar.py tests/test_slots_ventana.py -q
```
→ Esperado: **el mismo resultado que la línea base del paso 0**. La línea base conocida al
escribir este plan era `3 failed, 289 passed, 1 skipped` (+42 de `test_slots_ventana.py`), con
los 3 fallos en `test_cuantificar_ranking.py::test_bd_real_*` (BD local congelada, ajenos).
⚠️ **Un test de `test_slots_ventana.py` PUEDE fallar legítimamente**: el que fija
`test_ventana_no_altera_ningun_nivel_existente`. Si falla **solo** por el caso de ventana,
actualízalo — este plan levanta esa regla a propósito (H4) — y **repórtalo explícitamente**.
Cualquier OTRO fallo nuevo: DETENTE.

```powershell
uv run python -m app.features.consulta_v2.golden.run_golden_cuantificar
```
→ Esperado: **el mismo porcentaje que en el paso 0** (era `5/24 = 20%` en local, por la BD
congelada; en Pruebas es ≥90%).

```powershell
uv run python -c "from app.features.analisis.api import curva_dia_rango; print('import OK')"
```
→ Esperado: `import OK`. Verifica que no rompiste `api.py` (2700+ líneas).

**Comprobaciones v2 — las que detectan H9/H11.** Ningún test de Python las cubre porque no
cruzan el proxy ni el navegador. Desde `C:\APLICACIONES\ProdIA\Repo ProdIA\frontend`:

```powershell
python -c "import ast,sys; src=open('routes/api.py',encoding='utf-8').read(); print('v_ini OK' if 'v_ini' in src and 'v_fin' in src else 'FALTA v_ini/v_fin'); ast.parse(src); print('sintaxis OK')"
```
→ Esperado: `v_ini OK` y `sintaxis OK`. Si dice `FALTA`, el paso 6 no se aplicó (NN-8).

```powershell
node --check static/js/multitab_shell.js
```
→ Esperado: sin salida (sintaxis válida). Si `node` no está instalado, ábrelo en el navegador y
mira la consola: un error de sintaxis deja el chat entero muerto, no solo este panel.

### 6.2 Humana — la ejecuta el USUARIO, en Pruebas

Tras `git pull` en Pruebas y **reiniciar los DOS procesos** (Flask cachea el proxy; el JS exige
Ctrl+F5):

| # | Pregunta en `http://localhost:5029` | Esperado |
|---|---|---|
| 1 | «¿Cuánto produjo Castilla en los últimos 30 días?» | **Curva diaria acotada**, eje X en `DD/MM` desde ~25/07 hasta el último día con reporte. Título: `Crudo · producción diaria · 25/07 a 23/08`. **Sin gauge.** Aviso de que cuenta desde el último reporte |
| 2 | «¿Cuánto produjo Castilla el mes pasado?» | **Sin cambios** (KPI mensual) |
| 3 | «¿Cuánto produjo Castilla el último mes?» | **Sin cambios** (KPI mensual, H5) |
| 4 | «Producción día a día de Castilla en junio» | **Sin cambios**: curva de junio, eje X `1..30` |
| 5 | «¿Cuál fue el mejor día de Castilla?» | **Sin cambios** |
| 6 | «Acumulado de Castilla» | **Sin cambios** |
| 7 | F12 → Console en las 6 anteriores | **0 errores** |
| 8 | 🔴 **Caché (H10).** Preguntar 1, y **en menos de 45 s** preguntar «producción día a día de Castilla en agosto» | La 2ª muestra **agosto completo (1..31)**, NO la ventana. Si muestra la ventana, la ventana no entró en la clave de caché |
| 9 | 🔴 **Caché inversa.** Preguntar «día a día de Castilla en agosto» y, en <45 s, la pregunta 1 | La 2ª muestra la **ventana**, no el mes |
| 10 | 🔴 **Proxy (H9).** Con F12 → pestaña Network, lanzar la pregunta 1 | La petición a `/api/analisis/desempeno` debe llevar **`v_ini=` y `v_fin=`** en la URL, y su respuesta debe traer `curva_ventana` no nulo |
| 11 | **El tablero no se contamina.** Abrir el tablero de análisis para CASTILLA tras la pregunta 1 | Muestra el **mes**, como siempre |

⚠️ **R3 (§10.4 de CLAUDE.md):** el executor NO marca esto. Su estado tras §6.1 es
**«implementado, PENDIENTE de validación humana»**.

---

## 7. Fuera de alcance

- La sub-intención `tendencia` de Analizar (narrar «viene subiendo», ritmo de declinación). Este
  plan entrega el **gráfico**, no la interpretación.
- Ventanas en MESES elevando el nivel (H5, decisión cerrada).
- Ventanas que no terminan en el techo («los 30 días de mayo»). Siguen en el rechazo honesto.
- El KPI/gauge para ventanas (H3: no existe PPTO de rango arbitrario).
- `ejecutar_n1dsel` (el selector mejor/peor día) sobre una ventana. Hoy opera sobre un mes y así
  se queda.
- Los puntos 2, 3, 5, 6, 8 y 9 de la lista de «inteligencia de tiempo» (MoM/YoY, real vs
  programa en el tiempo, declinación, promedio móvil, quiebre, racha).
- `frontend\` React (`backend\frontend\`): este panel es del Flask de `frontend\`.

---

## 8. Prompt para el agente EXECUTOR

```
Eres un agente EXECUTOR. Lee completo el plan
C:\APLICACIONES\ProdIA\Repo ProdIA\backend\Planes\plan_CURVA-VENTANA_20260903.md
y ejecútalo AL PIE DE LA LETRA.

Reglas: CERO modificaciones al plan. Orden secuencial (§4). Si un paso falla, DETENTE
y reporta. NN-7: si una línea del plan no calza con el código real, DETENTE, no
improvises ubicación.

Paso 0 OBLIGATORIO: corre la línea base de §6.1 (comandos 2 y 3) ANTES de editar nada.
Sin ella no puedes distinguir un fallo tuyo de los 3 preexistentes de BD.

🔴 El PASO 6 (frontend\routes\api.py, §3.6) NO es opcional. El navegador nunca habla con
FastAPI: pasa por el proxy Flask, que reconstruye los parámetros desde una lista blanca
cerrada. Sin ese paso, los pasos 1-5 pasan TODOS los tests y el gráfico no cambia (H9).
No lo saltes porque pytest esté verde.

🔴 La ventana entra en las DOS claves de caché (proxy Flask 45s + __cnDesempCache del
navegador), NUNCA en _CLAVE_IGNORAR (H10, NN-9).

Ojo: son DOS repos (backend y frontend) → DOS commits (§4.2). No los mezcles.
Un test de test_slots_ventana.py PUEDE fallar legítimamente (§6.1): este plan levanta a
propósito la NN-4 del plan anterior. Actualízalo y repórtalo explícitamente. Cualquier
OTRO fallo nuevo: DETENTE.

Al terminar §6.1, tu estado es "implementado, PENDIENTE de validación humana" (R3,
CLAUDE.md §10.4) — NO marques la feature como verificada: no tienes navegador.

Reporta: ✅/❌ Paso N con la salida de los comandos.
Al final: archivos tocados por repo + baseline vs final + "¿Hago commit?"
```
