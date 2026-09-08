# Plan · SENDA-PROYECTADA-DIC — Proyección de producción hasta diciembre 2026

**Fecha:** 2026-09-08 · **Versión: v2 (auditada)**
**Repos tocados:** `ProdIABack` (backend) y `ProdIAWebFront` (frontend)

> **v2** corrige 7 hallazgos de la auditoría sobre v1. Los tres graves: la sub-intención nueva
> caía en el `else → causal` sin avisar (H1), Plotly **ya está vendorizado** y v1 mandaba
> duplicarlo (H5), y el proxy Flask **no es genérico** (H6).

---

## 0. Contexto para el agente EXECUTOR

Eres un agente EXECUTOR. No tienes la conversación previa ni memoria de este proyecto.
Todo lo que necesitas está aquí.

### 0.1 El proyecto

```
C:\APLICACIONES\ProdIA\Repo ProdIA\
├── frontend\      repo ProdIAWebFront — Flask + Jinja2 + JS  (puerto 5029)
└── backend\       repo ProdIABack     — FastAPI (uv)         (puerto 5030)
```

El navegador **nunca** habla con el 5030. Flask proxea vía `frontend\routes\api.py`.

### 0.2 Entornos — LEE ESTO ANTES DE MEDIR NADA

| Entorno | VPN | BD |
|---|---|---|
| Local | No | **Congelada en 2026-05-18**, con corrupción en `core.fact_tabla_hoja` |
| Servidor de pruebas | Sí | Real y al día |

🔴 **La BD local NO sirve para validar este plan.** No tiene septiembre a diciembre.
En local: solo tests que no tocan BD y verificación de que los módulos importan.

### 0.3 Convenciones

- Comentarios **en español**, con fecha y tag: `# [2026-09-08 · SENDA-DIC] ...`
- Explica el **porqué**, no el qué.
- Python se ejecuta con `uv run` desde `backend\backend\`.
- JS del shell: **ES5** — `var`, `function`, `.then` (nunca `async/await`), concatenación con `+`.
- No reformatees código que no estés modificando.

### 0.4 Datos verificados (NO los re-midas)

Medido el 2026-09-08 contra el servidor de pruebas:

| Mes | ECP (OPERATIVO) | Filiales (POP) | Total | P50 |
|---|---|---|---|---|
| Oct 2026 | 606,8 | 126,8 | **733,6** | 741,8 |
| Nov 2026 | 606,5 | 125,3 | **731,8** | 738,3 |
| Dic 2026 | 604,3 | 125,6 | **729,9** | 733,3 |

Los totales coinciden **al decimal** con la línea POP de la lámina "Producción Equivalente
G.E. 2026". La suma cierra desde dos tablas independientes.

---

## 1. Hallazgos de la auditoría

### 🔴 H1 — Una sub-intención nueva cae en `else → causal` SIN AVISAR (bloqueante · nuevo en v2)

`respuesta_analizar.py` **no tiene dict de despacho**: es una cadena de `if sub == "..."`.
Verificado textualmente en `respuesta_analizar.py:463-468`:

```python
    # 5) Cuerpo determinista por sub-intención (VERBATIM de la data del ejecutivo).
    panel = None
    if sub == "proyeccion":
        cuerpo = _plantilla.proyeccion(d, ent_valor)
        cierre = _CIERRE_PROY
    else:                                                    # causal (default)
```

🔴 Devolver `"senda"` desde el sub-router **no lanza ninguna excepción**: no matchea ningún
`if`, llega al `else` y responde el **análisis causal del mes en curso** con total seguridad.

Sin excepción, sin log, sin aviso. **Es exactamente el bug que este plan viene a cerrar**,
reintroducido por la puerta de atrás. Por eso §3.3 añade la rama de despacho, y hacerlo es
**tan obligatorio como el léxico**: uno sin el otro deja el sistema peor que antes.

### 🔴 H2 — No existe fuente de datos para la senda en el flujo de Analizar (bloqueante · nuevo en v2)

`respuesta_analizar.py:411` arma `d` llamando a `ejecutivo`:

```python
    d = fn(entidad=ent_valor, segmento="ecp", nivel=nivel, periodo=per, pulir=False)
```

`d` trae `pace_crudo` (mes en curso) y `tarjetas[].proyectado_cierre` (un solo mes).
**La serie mensual proyectada hasta diciembre NO está en `d`.**

No hay capa recolectora: cada sub-intención con fuente propia se trae sus datos y se inyecta
como `_xxx_fn`. El precedente exacto es `tendencia` (`respuesta_analizar.py:429-461`), que
llama a `desemp_fn(...)` con **todos los kwargs explícitos**.

🔴 **Los kwargs van explícitos SIEMPRE.** `president` es un endpoint FastAPI: un default
`Query(...)` sobreviviente llega al SQL y revienta con `cannot adapt type 'Query'`
(documentado en `respuesta_analizar.py:421-423` y `CLAUDE.md` §7).

### 🔴 H3 — Toda inyección nueva va en TRES sitios o revienta (bloqueante · nuevo en v2)

`responder_con_panel` (`:532-546`) y `responder` (`:516-529`) reenvían **cada `_xxx_fn` una
por una**. El docstring de `:538-540` lo dice con un incidente detrás:

> 🔑 Este wrapper reenvía CADA `_xxx_fn` a `_responder_core` una por una: al añadir una
> inyección nueva allí hay que añadirla AQUÍ TAMBIÉN, o los tests la pasan y revienta con
> `unexpected keyword argument` (pasó el 2026-09-07 con `_serie_anual_fn`).

🔴 `_senda_fn` va en `_responder_core` (firma :150 + resolución ~:172), `responder`
(:519 firma + :524 llamada) y `responder_con_panel` (:535 firma + :541 llamada).

**Medido:** `grep -c "_serie_anual_fn" respuesta_analizar.py` da **8** apariciones. Ese es el
patrón exacto a replicar, y el número que debe dar `_senda_fn` al terminar.

### 🟡 H4 — Léxico `_FUTURO` demasiado ancho rompe 4 archivos de test (define §3.2)

Casos que deben seguir donde están:

| Test | Pregunta | Debe seguir en |
|---|---|---|
| `test_analizar.py:27,30,492` | "¿cómo vamos este mes?", "¿vamos a cerrar el crudo?" | `proyeccion` |
| `test_analizar_tendencia.py:64` | "como viene Castilla, vamos a cerrar en meta" | `tendencia` |
| `test_p50_referencia.py:32` | "vamos a llegar al p50?" | `proyeccion` |

🔴 **Cualquier token con `VAMOS A` o `CERRAR` en `_FUTURO` rompe estos cuatro archivos.**
Por eso `_FUTURO` solo contiene frases con horizonte temporal explícito.

🔑 Y `HASTA` a secas es intocable: `HASTA AHORA` / `HASTA LA FECHA` son ACUMULADO
(`cuantificar\slots.py:27`); robárselos rompe el YTD, que hoy funciona.

### 🟡 H5 — Plotly YA está vendorizado y cargado global (v1 estaba equivocado)

Verificado con `ls`:

```
frontend\static\js\vendor\plotly-2.26.0.min.js   3.596.760 B (3,4 MB)
```

Y cargado en **todas** las páginas — `frontend\templates\base.html:33`:

```html
<script src="{{ url_for('static', filename='js/vendor/plotly-2.26.0.min.js') }}"></script>
```

🔴 **v1 ordenaba descargar `plotly-basic.min.js`. ESO ESTÁ ANULADO.** `window.Plotly` ya existe
cuando corre `multitab_shell.js`. Un segundo Plotly duplicaría 3 MB y pisaría la global.

🟢 Consecuencia: **cero archivos nuevos** en el frontend. Es el "conectar antes que construir"
de `CLAUDE.md` §7.

### 🟡 H6 — El proxy de Flask NO es genérico (v1 lo dejaba condicional)

`frontend\routes\api.py` declara **cada ruta a mano**. No hay `<path:>` ni catch-all.
Verificado: `/analisis/president/meses` (`:254`) y `/analisis/president` (`:266`) están
declaradas una por una.

🔴 **Hay que añadir `/analisis/president/senda` explícitamente**, reusando
`_analisis_proxy_cacheado(ruta, params, ttl)` (`:226-250`).

🔑 La lista de params es **cerrada**: el comentario de `api.py:290-293` avisa de que
"un parámetro que no esté aquí NO llega a INGESTA y se pierde en silencio".

### 🟡 H7 — `innerHTML = string` es incompatible con Plotly (define §3.7)

El shell pinta **todo** con `innerHTML = <string>`. Plotly necesita un nodo real y
`Plotly.newPlot(nodo, ...)`.

Y hay un peligro medido: `__cnPaintP50Header` (`multitab_shell.js:6032-6062`) hace
`row2.innerHTML = ...` **completo**. Si el gráfico vive dentro de `#cn-p50-row`, cada cambio
de mes destruye el nodo de Plotly y **filtra memoria**. Es literalmente el caso
"un panel que se destruye al repintar su contenedor" de `CLAUDE.md` §10.4.

🔑 **Decisión cerrada:** contenedor propio, **hermano** de `cn-p50-row`, con su propio ciclo
de vida y `Plotly.purge()` antes de cada repintado.

### 🟢 H8 — Precedencia del sub-router: recién tocada, respetarla

`subrouter.py:81-83` insertó el 2026-09-08 (plan `P50-CUMPLIMIENTO-MES`) el bloque
`_CUMPLIMIENTO` **antes** de `_PROY`, con golden que lo respalda.
`_FUTURO` va **después** de ese bloque y **antes** de `_PROY`.

### 🟢 H9 — Sin Enum, sin Literal, sin Pydantic sobre la sub-intención

`sub_intencion` está anotada `-> str` a secas. Cero validadores. Añadir un valor nuevo no
puede lanzar `KeyError`. **Ese es justamente el problema** (H1): falla en silencio.

### 🟢 H10 — Filiales: `POP Filiales`, no `DATOS_MES`

`DATOS_MES` tiene `GRUPOPROD` fijo = ECOPETROL y su eje contrario es **SOCIOS**, no filiales
(`ingesta\services.py:1251`, `:1274`; `plan_ingesta_datos_mes_2026-06-30.md:234-235`).

Verificado: `POP Filiales` da 134,2 en ene y feb — exactamente `core.p50_2026.real_filiales`.
Descartadas `Tabla 2 (P50 FILIALES)` y `Tabla 4 (RETO CORP FILIALES)`: son compromiso y reto.

### 🟢 H11 — `POP Filiales`: subtotales mezclados, bpd, un reporte por fila

- Conviven detalle (`Hocol`/`Permian`/`EAI` × `Crudo`/`Gas`/`Blancos`) y subtotales
  (`TOTAL HOCOL`, `Total Gas`, `Total general`). **Sumar sin filtrar triplica.**
- `Total general` ene-2026 = **134.263,5** contra 134,2 de la lámina → **factor 1000**.
- `count(distinct reporte_id) = count(*) = 201`: un reporte por fila, cero duplicados.
  Regla: **último `reporte_id`**.

🔴 El `/1000` va **SOLO** a `POP Filiales`. `DATOS_MES` ya viene en kboepd (`calendar.md:11`).

### 🟢 H12 — `verificar_deploy.ps1` solo cubre `login.html`

Su chequeo genérico de estáticos (`:101-115`) es solo sobre `login.html`.
`main.html` y `base.html` no están cubiertos. Refuerza H5: **no crear archivos nuevos**.

### 🟢 H13 — Cache-buster: un solo sitio, valor actual `?v=20260908a`

`frontend\templates\main.html:88`:

```html
<script src="{{ url_for('static', filename='js/multitab_shell.js') }}?v=20260908a"></script>
```

Convención `AAAAMMDD` + letra. 🔴 **Hay que pasar a `?v=20260908b`** o el navegador sirve el
cacheado y el gráfico no aparece con la consola limpia.

### 🟢 H14 — El selector de meses excluye oct-dic por diseño

`analisis\api.py:2707-2730` solo lista meses con `REPORTE_PRESIDENT` ingerida, y su docstring
lo justifica. **Correcto: no se toca.** La senda va como bloque aparte.

---

## 2. Estado actual

| Archivo | Líneas | Estado |
|---|---|---|
| `backend\...\analisis\api.py` | 2733-2869 `president()` | Solo el mes del reporte |
| `backend\...\analizar\subrouter.py` | 15-17, 50-91 | Sin léxico de futuro |
| `backend\...\respuesta_analizar.py` | 150, 411, 463-468, 516-546 | Sin rama `senda` |
| `backend\...\analizar\plantilla.py` | 310-329 `proyeccion()` | Pace intra-mes, solo crudo |
| `backend\...\golden\analizar_golden.yaml` | 29 casos | Sin casos de futuro |
| `frontend\routes\api.py` | 226-276 | Sin ruta `senda` |
| `frontend\static\js\multitab_shell.js` | 6032-6062 | Sin gráfico de senda |
| `frontend\templates\main.html` | 88 | `?v=20260908a` |

**Anclas verificadas el 2026-09-08 contra los archivos reales:**
`api.py:2869` fin de `president()` · `api.py:2873` comentario GRANO DÍA ·
`api.py:9` `MESES_ES` definido en el módulo (no requiere import) ·
`subrouter.py:47` `_CUMPLIMIENTO` · `subrouter.py:84` `if any(k in t for k in _PROY):` ·
`plantilla.py:310` `def proyeccion(d, entidad) -> str:`

---

## 3. Especificación

### 3.1 AÑADIR — endpoint de la senda anual

**Archivo:** `backend\backend\app\features\analisis\api.py`
**Dónde:** DESPUÉS de la línea 2869 (`if p50_respaldo is not None else None)}`, fin de
`president()`) y ANTES de la línea 2873 (`# [2026-08-25] GRANO DÍA (plan QV2-GRANO-DIA)...`).

**No modifiques `president()`.**

```python
@router.get("/president/senda")
def president_senda(anio: int = Query(2026)):
    """Senda mensual de producción del año: real cerrado + proyección hasta diciembre.

    [2026-09-08 · SENDA-DIC] Reproduce la lámina gerencial "Producción Equivalente G.E."
    (barra apilada Ecopetrol + Filiales, línea P50 encima). Responde lo que el panel hoy no
    sabe: «¿cuánta es la proyección de producción?» más allá del mes en curso.

    NADA se calcula aquí: las tres series ya están ingeridas y esto solo las une.
      · ECP  -> DATOS_MES, escenario OPERATIVO (el plan revisado). PPTO es el presupuesto
                congelado y NO cuadra con la lámina -- medido: 619,6 contra 733,6 en octubre.
      · FIL  -> 'POP Filiales', fila `Total general`. Verificado: enero y febrero dan 134,2,
                que es exactamente core.p50_2026.real_filiales de esos meses.
      · P50  -> core.p50_2026, los 12 meses del compromiso.

    🔑 UNIDADES: DATOS_MES ya viene en kboepd (calendar.md:11). 'POP Filiales' viene en bpd
       -> /1000. Sin convertir, la barra de filiales sale 1000x y el gráfico es ilegible.
    🔑 REPORTE: cada reporte reescribe la serie anual completa -> se toma el ÚLTIMO reporte_id,
       no un agregado. Medido: 201 reportes, 201 filas, cero duplicados reales.
    🔑 'POP Filiales' mezcla detalle y subtotales en la misma tabla (TOTAL HOCOL, Total Gas,
       Total general...). Se lee `Total general` directo: sumar el detalle sin filtrar
       contaría cada barril hasta tres veces.
    🔑 `es_real` NO se deduce del calendario: sale de si DATOS_MES trae escenario REAL con
       filas para ese mes. Un mes sin cerrar no tiene REAL, y el frontend lo pinta rayado.
    """
    eng = get_engine()
    meses = {m: {"mes": m, "mes_nombre": MESES_ES[m], "ecopetrol": None,
                 "filiales": None, "total": None, "p50": None, "es_real": False}
             for m in range(1, 13)}

    with eng.connect() as c:
        # --- ECP: DATOS_MES, un solo reporte para no mezclar versiones del plan.
        # REAL y OPERATIVO en la misma pasada: REAL marca los meses cerrados, OPERATIVO da la
        # senda completa incluidos los futuros.
        rid = c.execute(sa.text("""
            SELECT reporte_id FROM core.fact_tabla_hoja
            WHERE tabla_label = 'DATOS_MES (detalle mensual)'
            ORDER BY reporte_id DESC LIMIT 1""")).scalar()
        if rid:
            for r in c.execute(sa.text("""
                SELECT dims->>'escenario' esc,
                       EXTRACT(MONTH FROM fecha)::int mes,
                       SUM(valor) total
                FROM core.fact_tabla_hoja
                WHERE tabla_label = 'DATOS_MES (detalle mensual)'
                  AND reporte_id = :rid
                  AND EXTRACT(YEAR FROM fecha)::int = :anio
                  AND dims->>'escenario' IN ('REAL', 'OPERATIVO')
                GROUP BY 1, 2"""), {"rid": rid, "anio": anio}):
                esc, mes, total = r[0], int(r[1]), float(r[2])
                if mes not in meses:
                    continue
                if esc == "REAL":
                    meses[mes]["es_real"] = True          # el mes tiene cierre medido
                else:
                    meses[mes]["ecopetrol"] = round(total, 1)

        # --- FILIALES: 'POP Filiales', `Total general`, último reporte. En bpd -> /1000.
        rid_f = c.execute(sa.text("""
            SELECT reporte_id FROM core.fact_tabla_hoja
            WHERE tabla_label = 'POP Filiales'
            ORDER BY reporte_id DESC LIMIT 1""")).scalar()
        if rid_f:
            for r in c.execute(sa.text("""
                SELECT EXTRACT(MONTH FROM fecha)::int mes, valor
                FROM core.fact_tabla_hoja
                WHERE tabla_label = 'POP Filiales'
                  AND reporte_id = :rid
                  AND EXTRACT(YEAR FROM fecha)::int = :anio
                  AND dims->>'producto' = 'Total general'
                  AND dims->>'empresa' IS NULL"""), {"rid": rid_f, "anio": anio}):
                mes = int(r[0])
                if mes in meses:
                    meses[mes]["filiales"] = round(float(r[1]) / 1000.0, 1)

        # --- P50. try/except porque la migración 011 es un paso MANUAL por entorno (mismo
        # criterio que `p50_respaldo` en president()): habrá una ventana con el código
        # desplegado y la tabla sin crear, y sin la guarda se caería el endpoint entero.
        if anio == 2026:
            try:
                for r in c.execute(sa.text("SELECT mes, p50 FROM core.p50_2026")):
                    mes = int(r[0])
                    if mes in meses and r[1] is not None:
                        meses[mes]["p50"] = float(r[1])
            except Exception:
                pass                                       # sin P50 el gráfico pinta solo barras

    # Total apilado SOLO con las dos partes. Un total al que le falte filiales sería una barra
    # corta y creíble -- el fallo silencioso que este plan viene a cerrar.
    for m in meses.values():
        if m["ecopetrol"] is not None and m["filiales"] is not None:
            m["total"] = round(m["ecopetrol"] + m["filiales"], 1)

    serie = [meses[m] for m in range(1, 13)]
    ultimo_real = max((m["mes"] for m in serie if m["es_real"]), default=0)
    return {"anio": anio, "unidad": "kboepd", "serie": serie,
            "ultimo_mes_real": ultimo_real,
            "fuentes": {"ecopetrol": "DATOS_MES · escenario OPERATIVO",
                        "filiales": "POP Filiales · Total general",
                        "p50": "core.p50_2026"}}
```

**Dependencias ya disponibles (NO las importes):** `MESES_ES` (`api.py:9`), `Query`
(usado en `president()`), `sa` y `get_engine` (usados en todo el archivo).

### 3.2 MODIFICAR — léxico de horizonte futuro

**Archivo:** `backend\backend\app\features\consulta_v2\analizar\subrouter.py`

**Paso A.** Tras la línea 47 (`_CUMPLIMIENTO = ("CUMPLI", "COMPROMISO")`), añade:

```python

# [2026-09-08 · SENDA-DIC] Horizonte FUTURO explícito: se piden meses que aún no han ocurrido,
# no el cierre del mes en curso. Sin esto, «¿cuánto vamos a producir hasta diciembre?» entra
# por _PROY y se responde con el pace diario del mes actual -- ignorando "diciembre" y sonando
# seguro. Misma familia que el bug del periodo ignorado (CLAUDE.md §6).
# 🔑 NINGUNA entrada contiene "VAMOS A" ni "CERRAR" a secas: son de _PROY y de _TEND, y hay 4
#    archivos de test que lo fijan -- test_analizar.py:27,30,492 («¿cómo vamos este mes?»,
#    «¿vamos a cerrar el crudo?»), test_analizar_tendencia.py:64 («como viene Castilla, vamos
#    a cerrar en meta») y test_p50_referencia.py:32 («vamos a llegar al p50?»). Ensanchar esta
#    tupla con esas formas los rompe a los cuatro.
# 🔑 "HASTA" nunca va suelto: "HASTA AHORA"/"HASTA LA FECHA" son ACUMULADO (cuantificar/
#    slots.py:27) y robárselos rompería el YTD, que hoy funciona. Solo frases completas.
_FUTURO = ("RESTO DEL ANO", "LO QUE QUEDA DEL ANO", "LO QUE RESTA DEL ANO",
           "PROXIMOS MESES", "SIGUIENTES MESES", "MESES QUE VIENEN", "MESES RESTANTES",
           "CIERRE DE ANO", "CIERRE DEL ANO", "FIN DE ANO", "FINAL DEL ANO",
           "HASTA DICIEMBRE", "HASTA FIN DE ANO", "HASTA FINAL DE ANO",
           "DE AQUI A DICIEMBRE", "DE AQUI A FIN DE ANO")
```

**Paso B.** Localiza este bloque (líneas 81-85):

```python
    if (any(k in t for k in _CUMPLIMIENTO) and "P50" in t
            and not any(k in t for k in _CAUSAL_EXPL)):
        return "referencia"
    if any(k in t for k in _PROY):
        return "proyeccion"
```

Reemplázalo por:

```python
    if (any(k in t for k in _CUMPLIMIENTO) and "P50" in t
            and not any(k in t for k in _CAUSAL_EXPL)):
        return "referencia"
    # [2026-09-08 · SENDA-DIC] DESPUÉS de _CUMPLIMIENTO y ANTES de _PROY, a propósito:
    #   · «¿cuánto cumplimos del P50 en agosto?» -> cumplimiento, cifra ya cerrada (arriba)
    #   · «¿cuánto vamos a producir hasta diciembre?» -> senda, meses futuros (aquí)
    #   · «¿vamos a cerrar en meta?» -> pace del mes en curso (_PROY, abajo)
    # Sin este orden, _PROY captura "VAMOS A" y la senda no se alcanza nunca.
    if any(k in t for k in _FUTURO):
        return "senda"
    if any(k in t for k in _PROY):
        return "proyeccion"
```

**Paso C.** Reemplaza el docstring de `sub_intencion` (líneas 51-54) por:

```python
    """causal (default) | proyeccion | senda | diferidas | economia | referencia | tendencia.
    Precedencia: economia/diferidas ganan (son fuentes distintas), luego TENDENCIA, luego
    CUMPLIMIENTO+P50 sin señal causal (referencia temprana, 2026-09-08), luego SENDA
    (horizonte futuro explícito, 2026-09-08), luego proyeccion, luego referencia (P50 sin
    señal causal explícita), luego causal."""
```

### 3.3 🔴 MODIFICAR — rama de despacho para `senda` (LO MÁS IMPORTANTE DEL PLAN)

**Archivo:** `backend\backend\app\features\consulta_v2\respuesta_analizar.py`

Sin este paso, §3.2 **empeora el sistema**: `"senda"` cae en el `else` y responde el análisis
causal del mes en curso, con seguridad y sin avisar (H1).

🔴 **Antes de escribir, LEE el archivo completo.** Necesitas ver la rama `tendencia`
(`:429-461`) para clonar su forma exacta, y los wrappers (`:516-546`).

**Paso A — nueva inyección en `_responder_core`.** En la firma (termina en la línea 150):

```python
                     _desempeno_fn=None, _serie_anual_fn=None) -> dict:
```

pasa a:

```python
                     _desempeno_fn=None, _serie_anual_fn=None, _senda_fn=None) -> dict:
```

Y junto a las demás resoluciones de `fn` (después de `serie_anual_fn`, línea 172), añade:

```python
    # [2026-09-08 · SENDA-DIC] Inyectable como los demás `_fn`: los tests pasan una serie fija
    # y este módulo no toca BD en pruebas.
    senda_fn = _senda_fn or _president_senda_ep
```

🔴 **`_president_senda_ep` hay que importarlo.** Los imports existentes, verificados:

```python
35:from app.features.analisis.api import president as _president_ep
36:from app.features.analisis.api import desempeno as _desempeno_ep
```

Añade en la línea siguiente, con la misma forma:

```python
from app.features.analisis.api import president_senda as _president_senda_ep
```

**Paso B — la rama.** Insértala INMEDIATAMENTE ANTES del bloque `# 5) Cuerpo determinista por
sub-intención` (línea 463), es decir después del `return` de la rama `tendencia` (línea 461):

```python
    # [2026-09-08 · SENDA-DIC] Senda proyectada hasta diciembre. Va ANTES del bloque 5 y con
    # `return` propio, igual que `tendencia`: si cayera al if/else de abajo, `senda` no
    # matchearía "proyeccion" y aterrizaría en el `else` -> análisis causal del mes en curso,
    # respondido con seguridad. Ese es justo el fallo que este plan viene a cerrar.
    # 🔑 Los kwargs van EXPLÍCITOS: `president_senda` es un endpoint FastAPI y un default
    #    Query(...) sobreviviente revienta el SQL con "cannot adapt type 'Query'"
    #    (mismo motivo que la llamada a `desemp_fn` de arriba).
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
        return {"mensaje": mensaje, "panel": None}
```

🔑 `panel=None` a propósito: el gráfico vive en el panel P50 (§3.7), no en la pila de chat.

**Paso C — los dos wrappers.** 🔴 O revienta con `unexpected keyword argument`
(pasó el 2026-09-07 con `_serie_anual_fn`, ver `:538-540`):

1. `responder` firma (línea 519): añade `, _senda_fn=None`
2. `responder` llamada (línea 524-529): añade `_senda_fn=_senda_fn,`
3. `responder_con_panel` firma (línea 535): añade `, _senda_fn=None`
4. `responder_con_panel` llamada (línea 541-546): añade `_senda_fn=_senda_fn,`

Sumado al Paso A (firma :150 + resolución ~:172) y al import, **`grep -c "_senda_fn"` debe
dar 8** al terminar — el mismo número que `_serie_anual_fn` hoy.

### 3.4 AÑADIR — plantilla de respuesta

**Archivo:** `backend\backend\app\features\consulta_v2\analizar\plantilla.py`

🔴 **ANTES de escribir, LEE `proyeccion()` completa (línea 310).** Su contrato medido:

```python
def proyeccion(d, entidad) -> str:
    scope = (d.get("meta") or {}).get("scope") or (entidad or "la producción ECP")
    ...
    return f"📊 {scope} · {periodo}\nPROYECCIÓN · crudo: {linea}."
```

- Firma: dos posicionales, devuelve `str`. Nunca `None`, nunca lanza.
- Formato numérico: `_fmt(valor, "CRUDO")` → **coma decimal, 1 decimal** (`'492,4'`).
- Patrón tolerante: `(d.get("meta") or {}).get("X") or <default>`.

**Acción:** añade `senda(d, entidad) -> str` INMEDIATAMENTE DESPUÉS de `proyeccion()`.

🔑 `d` aquí **NO** es el dict del ejecutivo: es la respuesta de `/president/senda`
(claves `serie`, `unidad`, `ultimo_mes_real`). Distinto contrato, misma forma de función.

Comportamiento:

- Sin meses futuros con `total` → `"📊 {scope}\nNo tengo la senda proyectada para el resto del año."`
- Con datos:

```
📊 {scope} · resto de 2026
SENDA PROYECTADA · octubre 733,6 · noviembre 731,8 · diciembre 729,9 kboepd.
Contra el compromiso P50 (741,8 / 738,3 / 733,3) la brecha se estrecha de -8,2 a -3,4 kboepd.
```

- Números con **coma decimal**, un decimal, reusando el formateador del módulo.
- Si a algún mes futuro le falta `p50`, **omite la segunda frase completa** — no la escribas
  con huecos.
- Cubre **el total equivalente**, no solo crudo (a diferencia de `proyeccion()`).

### 3.5 AÑADIR — casos de golden

**Archivo:** `backend\backend\app\features\consulta_v2\golden\analizar_golden.yaml`

Formato exacto verificado (3 claves, 2 espacios, `entidad: null` cuando es global):

```yaml
- pregunta: "¿cómo vamos este mes?"
  entidad: null
  sub: proyeccion
```

Añade estos ocho casos al final:

| Pregunta | `sub` |
|---|---|
| ¿Cuánto vamos a producir hasta diciembre? | `senda` |
| ¿Cuál es la proyección para lo que queda del año? | `senda` |
| ¿Cómo se ve el cierre de año? | `senda` |
| ¿Qué producción esperamos los próximos meses? | `senda` |
| ¿Cómo vamos este mes? | `proyeccion` |
| ¿Vamos a cerrar en meta? | `proyeccion` |
| ¿Cuánto cumplimos del P50 en agosto? | `referencia` |
| ¿Por qué no cumplimos el P50? | `causal` |

🔴 Los **cuatro últimos son de no-regresión** (H4): verifican que `_FUTURO` no robó preguntas.
Son tan importantes como los cuatro primeros.

### 3.6 AÑADIR — proxy de Flask

**Archivo:** `frontend\routes\api.py`

El proxy es **ruta por ruta** (H6). Añade la ruta nueva junto a las otras dos de `president`
(alrededor de las líneas 254-276), clonando el patrón de `analisis_president_meses`:

```python
@api_bp.route("/analisis/president/senda")
def analisis_president_senda():
    """Proxy: senda mensual del año (real + proyección a diciembre) para el panel P50.

    [2026-09-08 · SENDA-DIC] Caché larga (600s), como el selector de meses: la senda solo
    cambia cuando se ingiere un reporte nuevo, no dentro del día.
    """
    try:
        params = {}
        anio = request.args.get("anio")
        if anio:
            params["anio"] = anio        # lista blanca: lo que no se copie aquí NO llega
        return _analisis_proxy_cacheado("/analisis/president/senda", params, 600)
    except requests.RequestException as e:
        return jsonify({"error": f"INGESTA no disponible: {e}"}), 502
```

🔑 `params` es lista blanca cerrada: un parámetro que no se copie se pierde en silencio
(`api.py:290-293`).

### 3.7 AÑADIR — gráfico de la senda en el panel

**Archivo:** `frontend\static\js\multitab_shell.js`

🔴 **ANTES de escribir, LEE `__cnPaintP50Header` (`:6032-6062`)** y clona su forma:
placeholder → `fetch` → **re-lookup del nodo dentro del `.then`** → pintar → `.catch` con
mensaje de fallo. **ES5**: `var`, `function`, `.then`. Nunca `async/await`.

🟢 **Plotly YA está disponible** como `window.Plotly` (`base.html:33`). **NO descargues nada,
NO crees archivos nuevos** (H5, H12).

**Estructura obligatoria — dos funciones, como el resto del shell:**

1. `__cnSendaHtml(d)` — **pura**, devuelve string, no toca el DOM. Solo el contenedor y el
   título; devuelve `""` si no hay serie.
2. `__cnPaintSenda()` — hace el `fetch`, inyecta el HTML y **después** llama a
   `Plotly.newPlot(nodo, data, layout, {displayModeBar: false, responsive: true})`.

🔴 **Contenedor propio, HERMANO de `#cn-p50-row`** (H7). No lo metas dentro: ese nodo se
reescribe entero en cada cambio de mes y destruiría el gráfico.

🔴 **Llama a `Plotly.purge(nodo)` antes de repintar.** Sin eso hay fuga de memoria —
es el caso "un panel que se destruye al repintar su contenedor" de `CLAUDE.md` §10.4.

**Especificación del gráfico:**

| Aspecto | Valor obligatorio |
|---|---|
| Tipo | `bar` apiladas (`barmode: 'stack'`) + `scatter` para el P50 |
| **Eje Y** | 🔴 **Base en CERO** — `yaxis: {rangemode: 'tozero'}` |
| Traza 1 | Ecopetrol, **abajo** en el apilado |
| Traza 2 | Filiales, **encima** |
| Traza 3 | P50, `mode: 'lines+markers'` |
| Meses proyectados | `marker.pattern.shape: '/'` donde `es_real === false` |
| Separador | `shapes` con línea vertical punteada antes del primer mes proyectado |
| Datos ausentes | Un mes con `total: null` se omite, no se pinta como cero |

🔴 **Por qué la base en cero es obligatoria — bug medido en la propuesta original:** con el eje
arrancando en 550, la barra de Ecopetrol solo dibuja lo que sobresale de ese piso (~43 de 593
kboepd) mientras la de filiales se dibuja entera. Ecopetrol se ve **más pequeño que filiales**
cuando en realidad es casi **5 veces mayor**. Un eje truncado en un apilado invierte la lectura
de la proporción. **Ecopetrol siempre debe verse mayor que filiales.**

### 3.8 MODIFICAR — cache-buster

**Archivo:** `frontend\templates\main.html`, línea 88.

```html
<script src="{{ url_for('static', filename='js/multitab_shell.js') }}?v=20260908a"></script>
```

→ cambia `?v=20260908a` por `?v=20260908b` (H13).

🔴 Sin esto el navegador sirve la versión cacheada: el gráfico no aparece **y la consola sale
limpia**, que es el peor diagnóstico posible.

---

## 4. Orden de ejecución

| # | Paso | Archivo | Depende de |
|---|---|---|---|
| 1 | Endpoint `/president/senda` | `backend\...\analisis\api.py` | — |
| 2 | Verificar import (§6.1-A) | — | 1 |
| 3 | Léxico `_FUTURO` + precedencia | `backend\...\analizar\subrouter.py` | — |
| 4 | 🔴 Rama `senda` + `_senda_fn` ×5 | `backend\...\respuesta_analizar.py` | 1, 3 |
| 5 | Plantilla `senda()` | `backend\...\analizar\plantilla.py` | 4 |
| 6 | Casos de golden | `backend\...\golden\analizar_golden.yaml` | 3 |
| 7 | Golden + suite (§6.1-B, §6.1-C) | — | 3, 4, 5, 6 |
| 8 | Proxy Flask | `frontend\routes\api.py` | 1 |
| 9 | Gráfico en el shell | `frontend\static\js\multitab_shell.js` | 8 |
| 10 | Cache-buster | `frontend\templates\main.html` | 9 |

🔴 **El paso 4 NO es opcional ni posponible.** Hacer el 3 sin el 4 deja el sistema peor que
antes: la pregunta se clasifica bien y se responde mal, en silencio.

🔴 **Si un paso falla, DETENTE.** No sigas ni improvises una alternativa.

---

## 5. Reglas no negociables

1. **CERO modificaciones fuera de lo especificado.** Si ves un bug en otro sitio, anótalo en
   el reporte — no lo arregles.
2. **No toques `president()` ni `president_meses()`.** El endpoint nuevo es aditivo (H14).
3. **No añadas tablas, migraciones ni escenarios.** Todo el dato existe ya.
4. **No cambies `_PROY`, `_TEND`, `_CUMPLIMIENTO` ni `_ECON`.** Solo se AÑADE `_FUTURO`.
5. **Ninguna entrada de `_FUTURO` puede contener `VAMOS A` ni `CERRAR`** (H4).
6. **El `/1000` va SOLO a `POP Filiales`**, nunca a `DATOS_MES` (H11).
7. **Eje Y con base en cero.** No negociable (§3.7).
8. **NO descargues Plotly ni crees archivos JS nuevos.** Ya está vendorizado (H5).
9. **Los kwargs a endpoints FastAPI van SIEMPRE explícitos** (H2).
10. **Si un parche reactivo se acumula más de 2 iteraciones sin resolver, DETENTE** y revierte
    al último estado bueno (`CLAUDE.md` §10.5).
11. **No hagas commit** sin preguntar.

---

## 6. Validación

### 6.1 Estática — la corre el EXECUTOR

🔴 Los pasos que tocan BD **solo valen en el servidor de pruebas**. En local (BD congelada en
2026-05-18) sáltatelos y **decláralo explícitamente** en tu reporte.

**A. Imports** — carpeta `backend\backend`, línea única. **Válido también en local:**

```powershell
uv run python -c "import app.features.analisis.api, app.features.consulta_v2.respuesta_analizar, app.features.consulta_v2.analizar.plantilla; print('import OK')"
```

Esperado: `import OK`, sin traza.

**B. Golden** — carpeta `backend\backend`:

```powershell
uv run pytest -k golden -q
```

Esperado: **≥90%** (hoy 96% con 92 casos). 🔴 Si baja, `_FUTURO` robó preguntas: DETENTE y
reporta cuáles.

**C. Suite completa** — carpeta `backend\backend`:

```powershell
uv run pytest -q
```

Esperado: 502+ pasando. Hay **10 fallos preexistentes y ajenos** documentados: si aparecen
esos diez y ninguno más, correcto. **Cualquier fallo nuevo: DETENTE.**

🔴 Presta atención especial a `test_analizar.py`, `test_analizar_tendencia.py` y
`test_p50_referencia.py` — son los que H4 identifica como frágiles ante `_FUTURO`.

**D. Endpoint** (solo servidor de pruebas, backend levantado con `.\backend\iniciar_backend.bat`):

```powershell
curl http://localhost:5030/api/analisis/president/senda
```

**E. Tabla de criterios**

| # | Comando / comprobación | Resultado esperado |
|---|---|---|
| 1 | Import de los 3 módulos | `import OK`, sin traza |
| 2 | `curl .../president/senda` | `serie` con 12 elementos |
| 3 | Meses 10-12 del JSON | `total` ≈ 733,6 / 731,8 / 729,9 |
| 4 | Meses 1-8 del JSON | `es_real: true` |
| 5 | Meses 10-12 del JSON | `es_real: false` |
| 6 | `curl http://localhost:5029/api/analisis/president/senda` | Mismo JSON vía proxy Flask |
| 7 | `uv run pytest -k golden -q` | ≥90% |
| 8 | `uv run pytest -q` | 502+ pasando, solo los 10 fallos conocidos |
| 9 | `grep -c "_senda_fn" respuesta_analizar.py` | **8** apariciones — igual que `_serie_anual_fn` (H3) |

### 6.2 Humana — la valida el USUARIO

🔴 **Regla R3 (`CLAUDE.md` §10.4): "build verde" NO es "feature verificada".** No tienes
navegador: no puedes ver si el gráfico se pinta ni si Plotly cargó. Tu estado final correcto
es **"implementado, PENDIENTE de validación humana"**, nunca "verificado".

En `http://localhost:5029`:

1. El gráfico de senda se pinta en el panel.
2. 🔴 **La barra de Ecopetrol se ve claramente MAYOR que la de filiales**, en todos los meses.
3. Oct-nov-dic salen rayados, con el separador de "proyectado".
4. La línea P50 pasa por encima de las barras.
5. **Cambiar de mes en el selector NO destruye el gráfico** (H7).
6. F12 → Console con **0 errores**.
7. En el chat, "¿cuánto vamos a producir hasta diciembre?" devuelve la senda —
   **no** el pace del mes en curso, **no** un análisis causal.
8. "¿cómo vamos este mes?" sigue devolviendo la proyección de siempre (no-regresión).

---

## 7. Fuera de alcance

- ❌ Modelos de forecast, extrapolación o pace multi-mes. Todo el dato está ingerido.
- ❌ Migraciones SQL. No se crea ni altera ninguna tabla.
- ❌ Tocar `president_meses()` (H14).
- ❌ Desglose por producto (Crudo/Gas/Blancos) de meses futuros: `core.p50_2026` los deja en
  NULL y la lámina no los publica.
- ❌ Proyección por vicepresidencia, activo o campo: el P50 no se pacta a esos niveles
  (`db\migrations\011_p50_2026.sql:19-20`).
- ❌ Las brechas de `jerarquias_sup_error.md` y `vocabulario_distribucion_error.md`.
- ❌ Corregir la mezcla de subtotales de `POP Filiales` en la ingesta. Aquí se esquiva leyendo
  `Total general`; arreglar la hoja es otro plan.
- ❌ `PPTO` como escenario seleccionable. Decisión cerrada del usuario: **OPERATIVO**.
- ❌ Ampliar `verificar_deploy.ps1` a `main.html` (H12). Deuda anotada, no de este plan.
- ❌ El fallback a CDN de Plotly en `base.html:35-39`, inútil en el 139. Deuda preexistente.

---

## 8. Reporte final esperado del EXECUTOR

```
✅/❌ Paso 1 ... Paso 10
Archivos tocados: <rutas absolutas>
Validación estática: <resultado de cada comando de §6.1-E>
Entorno donde se validó: <local | servidor de pruebas>
Estado: implementado, PENDIENTE de validación humana (§6.2)
¿Hago commit?
```
