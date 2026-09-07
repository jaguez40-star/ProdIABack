# Plan `PANEL-P50-ANUAL` — panel de serie mensual del P50 corporativo 2026

| | |
|---|---|
| **ID tarea** | `PANEL-P50-ANUAL` |
| **Fecha** | 2026-09-07 |
| **Versión** | **v3 — corregido tras fallo en ejecución.** La v2 se cayó en el paso 1: dos anclas `LOCALIZAR` no coincidían con el archivo. Ver §1.0-bis |
| **Repos** | `backend` (ProdIABack) **y** `frontend` (ProdIAWebFront) |
| **Alcance** | Que «¿cómo es el comportamiento del P50 para 2026?» responda con un panel de serie mensual de 12 puntos, leyendo `core.p50_2026` |
| **Qué NO se toca** | El panel `p50_vp` · el endpoint `/president` · el clasificador · los extractores de ingesta · `cuantificar/` · el CSS de otros componentes |
| **Archivos** | **6** — 3 backend, 2 frontend, 1 plantilla (cache-buster) |

### Decisiones cerradas del usuario

1. **Tipo de pregunta: Analizar → sub-intención `referencia`, rama global.** No se crea sub-intención nueva.
2. **Gráfico de línea, UNA sola línea (el P50), SIN área sombreada.** Ver H2: el área con eje maximizado ya se probó en este proyecto y se retiró por medición.
3. **Eje Y maximizado** — mismo cálculo que `p50_vp`: mínimo real de los datos con 8% de margen a cada lado, NO anclado en cero.
4. **SIN línea de meta anual** (735,3). Queda para un plan posterior.
5. Se clona el patrón **SVG a mano de `__cnP50VpHtml`**, no Plotly.

---

## §0 Contexto para el agente EXECUTOR

**Proyecto:** ProdIA — consulta conversacional de producción de petróleo y gas de Ecopetrol. Son **dos procesos**: Flask en el 5029 (UI, repo `frontend`) y FastAPI/INGESTA en el 5030 (datos, repo `backend`). El navegador nunca habla con el 5030: Flask hace de proxy.

**Este plan toca 4 archivos: 2 del backend, 2 del frontend.**

| Rol | Ruta absoluta |
|---|---|
| Datos (crear función) | `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\analizar\p50_referencia.py` |
| Enrutado (emitir panel) | `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\respuesta_analizar.py` |
| Pintor + dispatcher | `c:\APLICACIONES\ProdIA\Repo ProdIA\frontend\static\js\multitab_shell.js` |
| Estilos | `c:\APLICACIONES\ProdIA\Repo ProdIA\frontend\static\css\colapsable.css` |
| Test a actualizar | `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\tests\test_p50_referencia.py` |

| | |
|---|---|
| Carpeta de trabajo backend | `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend` |
| Intérprete | `uv run python` (NO `python` a secas) |

**Qué es el P50:** el compromiso corporativo de producción, pactado en `kboepd` (miles de barriles equivalentes por día). Se pacta para **Ecopetrol como un todo** — nunca por campo o activo.

**La tabla `core.p50_2026`** (ya existe y está poblada — no la toques):

```
mes        SMALLINT PRIMARY KEY   -- 1..12
mes_nombre VARCHAR(12)            -- 'Enero'...'Diciembre'
p50        NUMERIC(8,2)           -- 744.20, 741.20, ...
unidad     VARCHAR(10)            -- 'kboepd'
fuente     VARCHAR(60)            -- 'lamina Produccion Equivalente G.E. 2026'
```

Valores enero→diciembre: `744.2 741.2 732.8 714.9 726.7 728.0 747.0 740.4 735.0 741.8 738.3 733.3`.

**Convenciones obligatorias:**
- Python 3.12. **JavaScript ES5 clásico**: `var` + `function`, **sin** arrow functions, **sin** template literals, **sin** `const`/`let`. Todo `multitab_shell.js` está escrito así.
- Código y comentarios **en español**. Fecha los cambios con `[2026-09-07]`.
- SQL con `sa.text(...)` y parámetros nombrados, **nunca** interpolación de cadenas.
- **Si algo del plan no calza con el código real: DETENTE y reporta. No improvises.**

---

## §1 Hallazgos de la auditoría

### §1.0 🔴 Qué falló en la v1 de este plan (y por qué existe la v2)

La v1 tocaba 5 archivos y **no incluía el cache-buster**. `main.html:88` fija
`multitab_shell.js?v=20260831j`: sin subir ese sufijo, el navegador sirve el JS cacheado y
**el panel no aparece, con la consola limpia** — un fallo mudo, indistinguible de un bug de
datos. Es un incidente ya conocido de este proyecto, y la v1 lo mencionaba solo como
advertencia en la validación humana, nunca como paso de ejecución.

Los hallazgos **H13, H14 y H15** son nuevos de la v2. H13 añade un archivo (`main.html`);
H14 y H15 confirman que los pipelines no se rompen.

### §1.0-bis 🔴 Por qué existe la v3: la v2 se cayó en el paso 1

**La v2 se ejecutó y el executor se detuvo en el primer paso**, correctamente. El bloque
`LOCALIZAR` de §3.1 transcribía el cierre de `serie_por_vp` así:

```python
    _SERIE_VP_CACHE[key] = { ...14 líneas... }
    return _SERIE_VP_CACHE[key]
```

El archivo real (`p50_referencia.py:236-249`) usa una variable intermedia, otras variables y otro
redondeo:

```python
    info = { ...con un bloque de comentario sobre la escala... }
    _SERIE_VP_CACHE[key] = info
    return info
```

**Causa raíz:** ese bloque se transcribió del informe de un subagente auditor, **no de leer el
archivo**. El resto del plan sí se verificó contra el código (imports, `_kbpe`, `esc`,
`__cnMesAbr`, cache-buster, pipelines) — pero el único bloque que el paso 1 necesitaba literal, no.

**Segundo error del mismo tipo, encontrado al revisar:** §3.4.a afirmaba que tras `__cnP50VpHtml`
viene el comentario `// ===== [2026-08-02] Cuantificar`. Es falso: viene el de la dona de
participación (`:5066`). Habría tumbado el paso 6.

**Corregido en la v3:**

1. §3.1 usa ahora un ancla de **dos líneas** (`_SERIE_VP_CACHE[key] = info` / `return info`) en vez
   de transcribir el dict. Cuanto más corta el ancla, menos superficie de error.
2. §3.4.a apunta a la secuencia real, verificada.
3. **Las 12 anclas del plan se comprobaron una a una con `grep -F` contra los archivos.** Las 10
   restantes coinciden literalmente.

**Regla que deja este incidente:** un bloque `LOCALIZAR` se copia **del archivo**, nunca de un
informe intermedio, y se prefiere el ancla mínima que identifique el punto sin ambigüedad.

### §1.1 🔴 H1 — La tabla NO tiene columna `real`: el panel es de UNA línea

`p50_vp` pinta **dos** polilíneas (P50 gris + REAL verde) y de ahí derivan el chip de estado (`multitab_shell.js:4978-4983`), el `pct`, el `gap`, la línea vertical de corte (`:5032-5033`) y el punto del corte (`:5038-5039`).

`core.p50_2026` solo tiene `p50`. **Todo ese aparato queda sin dato que lo alimente.**

**Decisión derivada:** el panel nuevo NO clona el chip, ni el gap, ni la línea de corte, ni el punto. Es una serie limpia de 12 puntos con su eje. Clonar esos elementos obligaría a inventarles un valor — el fallo silencioso que este proyecto persigue (`CLAUDE.md` §6).

### §1.2 🔴 H2 — El área sombreada NO existe en el proyecto, y fue retirada a propósito

Búsqueda exhaustiva: **cero coincidencias** de `linearGradient` en todo `multitab_shell.js`. `__cnP50VpHtml` no emite ningún `<path>` de área; el CSS pone `fill: none` en ambas polilíneas (`colapsable.css:2424-2425`).

Y hay una decisión explícita en contra, con su medición, en `multitab_shell.js:2507-2509`:

> «Sin `fill: tozeroy`: con el eje ya no anclado en 0, el área rellenaba hasta el borde inferior del recorte, que no es un cero ni ninguna otra referencia — pintaba una masa de color que no significaba nada y tapaba las líneas de PPTO y promedio.»

Es exactamente la combinación pedida al inicio (área + eje maximizado). **Decisión 2 del usuario: sin área.** Este hallazgo es la razón.

### §1.3 🔴 H3 — `test_p8_global_ecp_sigue_sin_panel` VA A FALLAR, y hay que actualizarlo

`backend\backend\tests\test_p50_referencia.py:444-455` afirma hoy:

```python
def test_p8_global_ecp_sigue_sin_panel(monkeypatch):
    # D1: el global ECP NO produce panel (su caso nativo es el artifact corporativo, otro plan).
    ...
    assert r["panel"] is None
```

Ese test fija **justo lo contrario** de lo que este plan implementa. **NO se ignora ni se borra: se actualiza** con su razón, y se renombra para que el nombre no mienta. Especificado en §3.5.

### §1.4 🟡 H4 — Contrato de datos a clonar: `serie_por_vp`

`p50_referencia.py:164-249`. Devuelve `None` en 5 casos (vice vacío, excepción de BD, sin reporte, `rows` vacío, ningún real). Su dict lleva: `vice`, `producto`, `unidad`, `fmt`, `corte`, `mes_real`, `real`, `p50`, `pct`, `gap`, `serie`.

`serie` es una lista de `{"fecha": "YYYY-MM-DD", "p50": float, "real": float|None}` (`:227-228`).

Caché: `_SERIE_VP_CACHE` (`:161`) — cachea el éxito y el `None` de «sin datos», **no** los errores.

**Para el panel nuevo** el contrato se simplifica (no hay `real`, no hay VP, no hay producto): `{"anio", "unidad", "fmt", "fuente", "serie": [{"mes", "mes_nombre", "p50"}]}`.

### §1.5 🟡 H5 — Cálculo exacto del eje Y maximizado (a clonar literal)

`multitab_shell.js:4989-5001`:

```javascript
var vmin = vals.length ? Math.min.apply(null, vals) : 0;
var vmax = vals.length ? Math.max.apply(null, vals) : 1;
if (vmax === vmin) { vmax += 1; vmin -= 1; }   // guard: serie plana no divide por cero
var margen = (vmax - vmin) * 0.08;
vmin -= margen; vmax += margen;
```

Con los 12 valores reales: `vmin = 714.9`, `vmax = 747.0`, rango 32,1 → margen 2,568 → eje **712,3 a 749,6**. La variación se ve con claridad, que es justo lo pedido.

⚠️ `p50_vp` **no pinta etiquetas numéricas en el eje Y** pese a tener `padL = 46` — ese espacio queda sin usar. El panel nuevo **sí las pinta** (3 marcas: min, medio, max), porque sin línea REAL de contraste una serie sin referencia numérica no se puede leer. Es la única desviación deliberada respecto a `p50_vp`, y está aquí declarada.

### §1.6 🟡 H6 — Etiquetas del eje X: con 12 meses solo saldrían 5

`multitab_shell.js:5015-5021`: `pasoEje = Math.max(1, Math.round((n - 1) / 4))`. Para `n = 12` → `Math.round(11/4) = 3` → índices 0, 3, 6, 9 + 11 = **ene, abr, jul, oct, dic**.

**Decisión:** el panel nuevo pinta **los 12 meses**, con `font-size` reducido. Es una serie anual: los 12 rótulos son el eje natural y caben en 320px de ancho. Se usa `__cnMesAbr` (`multitab_shell.js:1479`), verificado: 12 entradas, índice 0 = `"ene"`.

### §1.7 🟡 H7 — Dónde insertar sin romper la rama VP

`respuesta_analizar.py:271-303`. Estructura actual:

```python
panel_ref = None                                          # :271
if _p50.nivel_soportado(nivel, resuelta):                 # :272
    if es_vp:                                             # :273  ← rama VP, NO tocar
        ...
        panel_ref = {"tipo": "p50_vp", "datos": s}        # :285
    else:   # nivel is None -> global ECP                 # :286  ← AQUÍ va el cambio
        ...
        cuerpo = (...)                                    # :296-298
    intro = _intro(alcance, usuario)                      # :299
```

Global se determina en `:194`: cuando `resuelta is None` **y** `entidad` es falsy → `ent_valor, nivel, alcance = None, None, "la producción global ECP"`.

`nivel_soportado(None, resuelta)` ya devuelve `True` (`_NIVELES_OK = (None, "vicepresidencia")`, `p50_referencia.py:19`). **La rama global ya pasa el gate; solo no emite panel.**

El `if/else` es mutuamente excluyente: tocar el `else` no puede afectar a la rama VP.

### §1.8 🟢 H8 — `maquina_q` es agnóstico al tipo de panel: no hay que tocarlo

`maquina_q.py:613` hace `panel = r.get("panel")` y lo devuelve tal cual — no valida ni enumera tipos. **Cero cambios funcionales ahí.**

⚠️ Pero su comentario `:604-608` («SOLO 2 sub-intenciones producen panel… el resto, incluida referencia-global, va con panel=None») **ya está desactualizado hoy**: son 3 desde el 2026-08-26 (`respuesta_analizar.py:153-155` lo confirma). Este plan lo deja en 4 y actualiza el comentario (§3.3).

### §1.9 🟢 H9 — El dispatcher exige registro ANTES del fallback

`multitab_shell.js:4322-4327`. El comentario es explícito:

> «H2: registrada ANTES del fallback `__cnCuantCardHtml` — ese fallback NO valida el tipo y pintaría una tarjeta KPI con campos ajenos (estado/cumplimiento_pct/nivel) ante cualquier tipo no reconocido; sin este `else if` explícito, "p50_vp" caería ahí.»

El fallback está en `:4344` (`: __cnCuantCardHtml(d);`). **El tipo nuevo debe registrarse antes de esa línea** o se pinta una tarjeta KPI con campos que no existen.

`p50_vp` **no** está en la lista de `:4415` (`__cnPanelMesCargar`) porque es función pura y síncrona. El panel nuevo tampoco debe estarlo.

### §1.10 🟢 H10 — Inyección para tests: patrón `_xxx_fn`

`respuesta_analizar.py:145-168`. Todas las dependencias externas entran por parámetro (`_p50_fn`, `_vp_fn`, `_president_fn`, `_serie_fn`, `_desempeno_fn`), resueltas con `x_fn = _param or _default`. Así los tests no tocan BD.

La función nueva **debe** seguir ese patrón, o los tests exigirán conexión.

### §1.11 🟢 H11 — La tabla tiene un solo consumidor hoy

`analisis\api.py:2683` (`SELECT p50 FROM core.p50_2026 WHERE mes = :mes`), del plan `P50-2026-FUENTE-VERDAD` implementado hoy mismo. Lee **un** mes como respaldo escalar.

Este panel será el **segundo** consumidor y leerá los 12. No hay conflicto: ambos son de solo lectura.

⚠️ De ese plan se hereda la escala ya verificada: `kboepd` ≡ la magnitud que `/president` rotula `kbpe`. **No hay conversión que hacer.**

### §1.12 🟡 H12 — La migración 011 es un paso manual por entorno

`CLAUDE.md` §9: el pipeline `migrar-a-azure` **copia archivos, no ejecuta SQL**. En Pruebas y en el 139 la tabla no existirá hasta correr `apply_migration.py`.

**Consecuencia para este plan:** la función nueva debe devolver `None` limpiamente si la tabla no existe (`try/except`), y la rama global debe seguir respondiendo su texto sin panel. Degrada, no rompe.

### §1.13 🔴 H13 — El cache-buster es OBLIGATORIO, no una advertencia

Medido: `frontend\templates\main.html:88`

```html
<script src="{{ url_for('static', filename='js/multitab_shell.js') }}?v=20260831j"></script>
```

Y el CSS, `main.html:5`:

```html
<link rel="stylesheet" href="{{ url_for('static', filename='css/colapsable.css') }}?v=20260831a">
```

**Este plan toca los dos archivos.** Sin subir ambos sufijos, el navegador sirve las versiones
cacheadas: la función `__cnP50AnualHtml` no existe en el JS que el navegador ejecuta, el
dispatcher cae al fallback `__cnCuantCardHtml` y pinta una tarjeta KPI con campos ajenos —
**o no pinta nada, con la consola limpia**.

⚠️ `login.html:39,43` también los referencia, pero con `rel="prefetch"` y **sufijos distintos**
(`20260903i` / `20260831a`). Es solo precarga: **no se tocan**. Tocarlos no aporta y el plan
no debe hacerlo.

**Consecuencia:** `main.html` entra como sexto archivo del plan, con paso propio en §4.

### §1.14 🟢 H14 — `verificar_deploy.ps1` no se ve afectado

Leído: valida el puerto, `login.css`/`login.js`, y **todos los estáticos que `login.html`
referencia** vía `url_for` (`verificar_deploy.ps1:101-112`).

`multitab_shell.js` y `colapsable.css` **sí** están referenciados por `login.html` (como
prefetch), pero el script solo comprueba que el archivo **exista**, no su contenido ni su
sufijo `?v=`. Ambos siguen existiendo. **El resultado del verificador no cambia.**

### §1.15 🟢 H15 — `migrar-a-azure` transporta todo lo de este plan, menos la BD

Leído `migrar_a_azure.ps1:65-68`: excluye `.git`, `venv`, `.venv`, `.uv`, `node_modules`,
`__pycache__`, `.env`, `*.bak`, `*.pyc`. **Ninguno de los 6 archivos del plan cae en esa lista**
— viajan todos, y el script verifica hash por hash.

⚠️ Pero, igual que en el plan `P50-2026-FUENTE-VERDAD`, **el pipeline copia archivos y no
ejecuta SQL**. La tabla `core.p50_2026` no llega sola a Pruebas ni al 139: hay que correr
`apply_migration.py` allí. Sin eso, `serie_anual_p50` devuelve `None` y la rama global cae al
comportamiento anterior — degrada, no rompe (por eso el `try/except` de §3.1 es obligatorio).

### §1.16 🟢 H16 — Dependencias del código nuevo: todas verificadas

Comprobado una por una, para que el executor no tenga que añadir imports:

| Símbolo | Dónde | Estado |
|---|---|---|
| `sa` (sqlalchemy) | `p50_referencia.py:14` | ✅ ya importado |
| `get_engine` | `p50_referencia.py:16` | ✅ ya importado |
| `_kbpe(n)` | `p50_referencia.py:252` | ✅ existe — miles es-CO con 1 decimal |
| `esc(t)` | `multitab_shell.js:29` | ✅ existe |
| `__cnMesAbr` | `multitab_shell.js:1479` | ✅ 12 entradas, índice 0 = `"ene"` |
| `_CIERRE_PROY` | `respuesta_analizar.py:49` | ✅ existe |

**El código de §3 no necesita ni un import nuevo.**

---

## §2 Estado actual

**Hoy**, ante «¿cómo es el comportamiento del P50 para 2026?»:

1. El clasificador enruta a **analizar** (`patrones_grupo.yaml:244`, patrón `P50\b`).
2. `subrouter.py:33` fija sub-intención **`referencia`** (`_REFERENCIA = ("P50",)`).
3. `respuesta_analizar.py:194` → sin entidad → `nivel = None` → **rama global**.
4. `:287` llama `president_fn(periodo=None)` → lee `REPORTE_PRESIDENT`.
5. `:291-295` busca la card del producto, o cae a `Ecopetrol`.
6. `formatear_cifra_global` (`p50_referencia.py:262-278`) devuelve **una cifra de un mes** (la del corte).
7. `:303` devuelve `{"mensaje": ..., "panel": None}`.

**El hueco:** responde la cifra de **un** mes, sin panel, cuando la pregunta es por el comportamiento **anual**. La serie de 12 meses existe en `core.p50_2026` y nadie la lee.

---

## §3 Especificación

### 3.1 AÑADIR — función `serie_anual_p50` en `p50_referencia.py`

**Archivo:** `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\analizar\p50_referencia.py`

**LOCALIZAR** el cierre de la función `serie_por_vp` — estas **dos líneas exactas** (`:248-249`),
seguidas de dos líneas en blanco y de `def _kbpe(n) -> str:` (`:252`):

```python
    _SERIE_VP_CACHE[key] = info
    return info
```

🔑 **Ancla deliberadamente corta.** Una v1 de este plan transcribió el dict completo de `info`
(14 líneas) y **no coincidía con el archivo**: el código real usa una variable intermedia `info`,
las variables `real_u`/`p50_u`, `* 100` en vez de `* 100.0`, y lleva un bloque de comentario sobre
la escala que la transcripción se había comido. El executor se detuvo en el paso 1, correctamente.
Estas dos líneas son estables y suficientes para situar el punto de inserción: **no transcribas
el dict, no lo toques.**

⚠️ **Si estas dos líneas no coinciden literalmente, DETENTE y reporta.**

**AÑADIR INMEDIATAMENTE DESPUÉS** de `return info` — es decir, entre esa línea y `def _kbpe`,
conservando la separación de dos líneas en blanco entre funciones:

```python


# ---------------------------------------------------------------------------
# [2026-09-07] SERIE ANUAL DEL P50 CORPORATIVO (plan PANEL-P50-ANUAL).
# ---------------------------------------------------------------------------
# POR QUE EXISTE: «¿como es el comportamiento del P50 para 2026?» es una pregunta por la SERIE,
# y hasta hoy la rama global respondia la cifra de UN mes (el del corte) sin panel. La serie de
# 12 meses vive en core.p50_2026 y nadie la leia.
#
# GRANO: Upstream global. La tabla NO tiene columna `real`, asi que esto es UNA sola linea --
# sin pct, sin gap, sin chip de cumplimiento. Inventar un real para poder calcularlos seria
# exactamente el fallo silencioso que persigue el proyecto.
#
# ESCALA: kboepd, la MISMA magnitud que /president rotula "kbpe" (verificado en el plan
# P50-2026-FUENTE-VERDAD: Upstream base_p50 = 726.73 en el reporte del 2026-05-18 y 726.7 en la
# tabla para mayo). No hay conversion.
_SERIE_ANUAL_CACHE: dict = {}


def serie_anual_p50(anio: int = 2026) -> dict | None:
    """Serie mensual del compromiso P50 corporativo, desde core.p50_2026. Devuelve None si no hay
    tabla o no hay filas — la rama global sigue respondiendo su texto, solo que sin panel.

    Contrato: {"anio": int, "unidad": str, "fmt": "anual", "fuente": str,
               "serie": [{"mes": int, "mes_nombre": str, "p50": float}, ...]}
    """
    if anio in _SERIE_ANUAL_CACHE:
        return _SERIE_ANUAL_CACHE[anio]
    # Hoy solo existe la tabla de 2026 (transcrita de la lamina). Otro anio no tiene fuente y se
    # declina en vez de devolver una serie vacia que el panel pintaria como una linea plana.
    if anio != 2026:
        return None
    try:
        eng = get_engine()
        with eng.connect() as c:
            rows = c.execute(sa.text(
                "SELECT mes, mes_nombre, p50, unidad, fuente "
                "FROM core.p50_2026 ORDER BY mes")).fetchall()
    except Exception:
        # 🔑 La migracion 011 es un paso MANUAL por entorno y el pipeline no ejecuta SQL, asi que
        # habra una ventana con el codigo desplegado y la tabla sin crear. Sin esta guarda, la
        # rama global entera se caeria y rompería una respuesta que hoy si funciona.
        return None
    if not rows:
        return None
    serie = [{"mes": int(r[0]), "mes_nombre": str(r[1]), "p50": float(r[2])} for r in rows]
    out = {
        "anio": anio,
        "unidad": str(rows[0][3]) if rows[0][3] else "kboepd",
        "fmt": "anual",
        "fuente": str(rows[0][4]) if rows[0][4] else "core.p50_2026",
        "serie": serie,
    }
    _SERIE_ANUAL_CACHE[anio] = out
    return out


def formatear_serie_anual(d: dict) -> str:
    """Cuerpo de texto para la serie anual. PURA: no toca BD ni LLM.

    Dice el rango (min/max con su mes) y el cierre, que es lo que se lee de un vistazo. NO
    calcula cumplimiento: sin real medido no hay contra que comparar.
    """
    serie = d.get("serie") or []
    if not serie:
        return "No tengo la serie del P50 disponible en este momento."
    u = d.get("unidad", "kboepd")
    lo = min(serie, key=lambda p: p["p50"])
    hi = max(serie, key=lambda p: p["p50"])
    ini, fin = serie[0], serie[-1]
    return (f"📊 Compromiso P50 {d.get('anio', 2026)} · serie mensual\n\n"
            f"Arranca en {_kbpe(ini['p50'])} {u} ({ini['mes_nombre'].lower()}) y cierra en "
            f"{_kbpe(fin['p50'])} {u} ({fin['mes_nombre'].lower()}). "
            f"El mínimo es {_kbpe(lo['p50'])} {u} en {lo['mes_nombre'].lower()} y el máximo "
            f"{_kbpe(hi['p50'])} {u} en {hi['mes_nombre'].lower()}.")
```

⚠️ **Verifica antes de escribir** que el módulo ya importa `sa` y `get_engine` (los usa `serie_por_vp`). Si no los importa, **DETENTE y reporta** — no añadas imports por tu cuenta.

### 3.2 MODIFICAR — `respuesta_analizar.py`: emitir el panel en la rama global

**Archivo:** `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\respuesta_analizar.py`

#### Cambio 3.2.a — añadir la inyección

**LOCALIZAR** (`:147-148`):

```python
                     _p50_fn=None, _vp_fn=None, _president_fn=None, _serie_fn=None,
                     _desempeno_fn=None) -> dict:
```

**SUSTITUIR POR:**

```python
                     _p50_fn=None, _vp_fn=None, _president_fn=None, _serie_fn=None,
                     _desempeno_fn=None, _serie_anual_fn=None) -> dict:
```

**LOCALIZAR** (`:168`, la línea que resuelve `desemp_fn`):

```python
    desemp_fn = _desempeno_fn or _desempeno_ep
```

**SUSTITUIR POR:**

```python
    desemp_fn = _desempeno_fn or _desempeno_ep
    # [2026-09-07 · PANEL-P50-ANUAL] Inyectable como los demás `_fn`: los tests pasan una serie
    # fija y este módulo no toca BD en pruebas.
    serie_anual_fn = _serie_anual_fn or _p50.serie_anual_p50
```

#### Cambio 3.2.b — emitir el panel

**LOCALIZAR** estas líneas exactas (`:286-303`):

```python
            else:   # nivel is None -> global ECP (REPORTE_PRESIDENT, escala kbpe)
                info = president_fn(periodo=None)
                if not info.get("encontrada"):
                    cuerpo = "No tengo el compromiso P50 disponible en este momento."
                else:
                    card = next((p for p in info.get("productos", [])
                                if p.get("entidad", "").upper() == producto), None)
                    if card is None:
                        card = next((t for t in info.get("totales", [])
                                    if t.get("entidad") == "Ecopetrol"), None)
                    cuerpo = (_p50.formatear_cifra_global(card, info.get("unidad", "kbpe"),
                                                          producto, info.get("corte"))
                              if card else "No tengo el compromiso P50 disponible en este momento.")
            intro = _intro(alcance, usuario)
            mensaje = respuesta_base.envolver(intro, cuerpo, _CIERRE_PROY)
            # D1: `panel_ref` solo se pobló en la rama `es_vp`; el global ECP sigue en None (su
            # caso nativo es el artifact corporativo, otra fuente/otro plan).
            return {"mensaje": mensaje, "panel": panel_ref}
```

**SUSTITUIR POR:**

```python
            else:   # nivel is None -> global ECP (REPORTE_PRESIDENT, escala kbpe)
                # [2026-09-07 · PANEL-P50-ANUAL] El P50 corporativo se pacta por AÑO y la pregunta
                # natural («¿cómo va el P50 en 2026?») es por la SERIE, no por un mes suelto. Si
                # core.p50_2026 tiene los 12 meses se responde la serie + panel; si no (tabla sin
                # migrar en este entorno), se cae al comportamiento anterior: la cifra del corte.
                anual = serie_anual_fn()
                if anual and anual.get("serie"):
                    cuerpo = _p50.formatear_serie_anual(anual)
                    panel_ref = {"tipo": "p50_anual", "datos": anual}
                else:
                    info = president_fn(periodo=None)
                    if not info.get("encontrada"):
                        cuerpo = "No tengo el compromiso P50 disponible en este momento."
                    else:
                        card = next((p for p in info.get("productos", [])
                                    if p.get("entidad", "").upper() == producto), None)
                        if card is None:
                            card = next((t for t in info.get("totales", [])
                                        if t.get("entidad") == "Ecopetrol"), None)
                        cuerpo = (_p50.formatear_cifra_global(card, info.get("unidad", "kbpe"),
                                                              producto, info.get("corte"))
                                  if card else "No tengo el compromiso P50 disponible en este momento.")
            intro = _intro(alcance, usuario)
            mensaje = respuesta_base.envolver(intro, cuerpo, _CIERRE_PROY)
            # [2026-09-07] Antes: «el global ECP sigue en None». Ya NO — la rama global emite
            # panel "p50_anual" cuando core.p50_2026 tiene la serie. La rama VP (p50_vp) no se
            # tocó: el if/else es mutuamente excluyente.
            return {"mensaje": mensaje, "panel": panel_ref}
```

#### Cambio 3.2.c — actualizar el docstring

**LOCALIZAR** (`:150-157`):

```python
    """Devuelve SIEMPRE {"mensaje": str, "panel": dict|None} (contrato HD4, patrón jerarquizar/
    cuantificar). `_ejecutivo_fn`/`_diferidas_fn`/`_economia_fn`/`_split_fn`/`_p50_fn`/`_vp_fn`/
    `_president_fn`/`_serie_fn` = inyección para tests (evita BD/LLM). 3 sub-intenciones producen
    panel: causal (tipo "analiza_foco"), referencia SOLO en su rama de vicepresidencia (tipo
    "p50_vp", 2026-08-13) y diferidas CUANDO hay datos (tipo "analiza_dif", 2026-08-26) — el resto
    (proyección/economía/referencia-global/referencia-declinar) va con panel=None, cada una con su
    propia forma de respuesta."""
```

**SUSTITUIR POR:**

```python
    """Devuelve SIEMPRE {"mensaje": str, "panel": dict|None} (contrato HD4, patrón jerarquizar/
    cuantificar). `_ejecutivo_fn`/`_diferidas_fn`/`_economia_fn`/`_split_fn`/`_p50_fn`/`_vp_fn`/
    `_president_fn`/`_serie_fn`/`_serie_anual_fn` = inyección para tests (evita BD/LLM).
    4 sub-intenciones producen panel: causal (tipo "analiza_foco"), referencia en su rama de
    vicepresidencia (tipo "p50_vp", 2026-08-13), diferidas CUANDO hay datos (tipo "analiza_dif",
    2026-08-26) y referencia-global CUANDO core.p50_2026 tiene la serie anual (tipo "p50_anual",
    2026-09-07) — el resto (proyección/economía/referencia-declinar) va con panel=None, cada una
    con su propia forma de respuesta."""
```

### 3.3 MODIFICAR — comentario desactualizado en `maquina_q.py`

**Archivo:** `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\maquina_q.py`

⚠️ **Cambio de comentario únicamente. NO hay cambio funcional aquí** (H8).

**LOCALIZAR** (`:604-608`):

```python
        # jerarquizar/cuantificar, :374-389). [2026-08-13, H5 del plan_panel_p50_vp] SOLO 2
        # sub-intenciones producen panel: causal (tipo "analiza_foco", el acordeón de foco apilado)
        # y referencia — pero SOLO en su rama de vicepresidencia afirmativa (tipo "p50_vp"); el
        # resto (proyección/diferidas/economía/referencia-global/referencia-declinar) va con
        # panel=None, cada una con su propia forma de respuesta. Solo tráfico real.
```

**SUSTITUIR POR:**

```python
        # jerarquizar/cuantificar, :374-389). [2026-09-07] 4 sub-intenciones producen panel:
        # causal (tipo "analiza_foco", el acordeón de foco apilado), referencia en su rama de
        # vicepresidencia (tipo "p50_vp", 2026-08-13), diferidas cuando hay datos (tipo
        # "analiza_dif", 2026-08-26) y referencia-global cuando core.p50_2026 tiene la serie
        # (tipo "p50_anual", 2026-09-07); el resto (proyección/economía/referencia-declinar) va
        # con panel=None, cada una con su propia forma de respuesta. Solo tráfico real.
        # 🔑 Este módulo es AGNÓSTICO al tipo: hace `panel = r.get("panel")` y lo devuelve tal
        # cual, sin validar ni enumerar. Un tipo nuevo NO requiere tocar nada aquí.
```

### 3.4 AÑADIR — pintor y registro en `multitab_shell.js`

**Archivo:** `c:\APLICACIONES\ProdIA\Repo ProdIA\frontend\static\js\multitab_shell.js`

#### Cambio 3.4.a — la función pintora

**LOCALIZAR** el final de `__cnP50VpHtml` y el comienzo del comentario de la función siguiente —
esta secuencia exacta (`:5063-5066`):

```javascript
    '</div>';
  }

  // [2026-08-11] Dona de PARTICIPACIÓN (top N + "Otros"), en % sobre la producción total. SVG
```

🔑 **Ancla corregida.** Una v1 de este plan decía que tras `__cnP50VpHtml` venía el comentario
`// ===== [2026-08-02] Cuantificar`. **Es falso**: lo que sigue es el comentario de la dona de
participación, arriba transcrito. Verificado leyendo el archivo. Es el mismo tipo de error que
tumbó el paso 1 en la primera ejecución.

⚠️ Si esa secuencia no aparece, **DETENTE y reporta**. No busques el comentario de Cuantificar.

**INSERTAR ENTRE** el `}` que cierra `__cnP50VpHtml` y el comentario `// [2026-08-11] Dona de
PARTICIPACIÓN`, dejando una línea en blanco a cada lado:

```javascript
  // [2026-09-07 · PANEL-P50-ANUAL] Serie mensual del compromiso P50 corporativo (12 meses).
  // Función PURA (devuelve string, no toca el DOM), igual que __cnP50VpHtml — sin fetch, sin
  // pintor diferido: los puntos ya viajan en panel.datos.
  //
  // 🔑 UNA sola línea: core.p50_2026 NO tiene columna `real`, así que aquí no hay chip de
  // cumplimiento, ni gap, ni línea de corte, ni punto — todo eso vive en __cnP50VpHtml porque
  // allí SÍ hay REAL contra el que comparar. Inventarlos sería mostrar un dato que no existe.
  //
  // 🔑 SIN área bajo la curva. Se retiró deliberadamente de las series el 2026-08-31 (ver
  // __cnSerieMesPlot): con el eje no anclado en 0 el relleno baja hasta un borde que no es cero
  // ni ninguna referencia, y pinta una masa de color que no significa nada.
  function __cnP50AnualHtml(d) {
    var serie = (d && d.serie) || [];
    if (!serie.length) return "";
    var u = (d && d.unidad) || "kboepd";
    var anio = (d && d.anio) || 2026;

    function fmtV(v) {
      return Number(v).toLocaleString("es-CO", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
    }

    // Geometría: mismas proporciones que __cnP50VpHtml (:4987), con padB mayor porque aquí se
    // pintan los 12 rótulos de mes en vez de 5.
    var W = 320, H = 158, padL = 46, padR = 10, padT = 12, padB = 30;
    var innerW = W - padL - padR, innerH = H - padT - padB;

    // Eje Y MAXIMIZADO — clonado literal de __cnP50VpHtml:4993-4999. Arranca en el MÍNIMO de los
    // datos (no en 0) + 8% de margen: con valores 714,9..747,0 el eje va de ~712 a ~750 y la
    // variación se lee con claridad. Anclado en cero, la curva sería casi una recta.
    var vals = [];
    var i;
    for (i = 0; i < serie.length; i++) {
      if (serie[i].p50 != null) vals.push(serie[i].p50);
    }
    var vmin = vals.length ? Math.min.apply(null, vals) : 0;
    var vmax = vals.length ? Math.max.apply(null, vals) : 1;
    if (vmax === vmin) { vmax += 1; vmin -= 1; }   // guard: serie plana no divide por cero
    var margen = (vmax - vmin) * 0.08;
    vmin -= margen; vmax += margen;

    var n = serie.length || 1;
    function xAt(k) { return padL + (n <= 1 ? 0 : (k / (n - 1)) * innerW); }
    function yAt(v) { return padT + innerH - ((v - vmin) / (vmax - vmin)) * innerH; }

    // Polilínea del P50.
    var pts = [];
    for (i = 0; i < serie.length; i++) {
      if (serie[i].p50 != null) pts.push(xAt(i).toFixed(1) + "," + yAt(serie[i].p50).toFixed(1));
    }
    var linea = '<polyline class="cn-p50an__linea" points="' + pts.join(" ") + '"></polyline>';

    // Puntos: 12 marcas pequeñas. Con una sola línea y sin REAL de contraste, los vértices son
    // lo que deja leer mes a mes en vez de una curva continua sin referencia.
    var puntos = "";
    for (i = 0; i < serie.length; i++) {
      if (serie[i].p50 == null) continue;
      puntos += '<circle class="cn-p50an__punto" cx="' + xAt(i).toFixed(1) +
        '" cy="' + yAt(serie[i].p50).toFixed(1) + '" r="2.4"></circle>';
    }

    // Eje Y: 3 marcas (min, medio, max) con su línea de guía. __cnP50VpHtml NO las pinta pese a
    // reservar padL=46 — aquí SÍ, porque sin la línea REAL de contraste una serie suelta no se
    // puede leer sin números.
    var ejeY = "";
    var marcas = [vmin + margen, (vmin + vmax) / 2, vmax - margen];
    for (i = 0; i < marcas.length; i++) {
      var yv = yAt(marcas[i]);
      ejeY += '<line class="cn-p50an__guia" x1="' + padL + '" y1="' + yv.toFixed(1) +
        '" x2="' + (W - padR) + '" y2="' + yv.toFixed(1) + '"></line>' +
        '<text class="cn-p50an__aytx" x="' + (padL - 6) + '" y="' + (yv + 3).toFixed(1) +
        '" text-anchor="end">' + fmtV(marcas[i]) + '</text>';
    }

    // Eje X: los 12 meses. __cnP50VpHtml solo pinta ~5 (pasoEje = round((n-1)/4)), pero en una
    // serie ANUAL los 12 rótulos son el eje natural y caben con font-size reducido.
    var ejeX = "";
    for (i = 0; i < serie.length; i++) {
      var mIdx = (serie[i].mes || 0) - 1;
      ejeX += '<text class="cn-p50an__axtx" x="' + xAt(i).toFixed(1) + '" y="' + (H - 9) +
        '" text-anchor="middle">' + (__cnMesAbr[mIdx] || "") + '</text>';
    }

    var lo = serie[0], hi = serie[0];
    for (i = 1; i < serie.length; i++) {
      if (serie[i].p50 < lo.p50) lo = serie[i];
      if (serie[i].p50 > hi.p50) hi = serie[i];
    }

    return '<div class="cn-p50an">' +
      '<div class="cn-p50an__hd">' +
        '<span class="cn-p50an__name">Compromiso P50 · ' + esc(String(anio)) + '</span>' +
      '</div>' +
      '<svg class="cn-p50an__svg" viewBox="0 0 ' + W + ' ' + H + '" role="img" ' +
        'aria-label="Serie mensual del compromiso P50 ' + esc(String(anio)) + ' en ' + esc(u) + '">' +
        ejeY + linea + puntos + ejeX +
      '</svg>' +
      '<div class="cn-p50an__foot">' +
        '<div class="cn-p50an__kv"><span>Máximo</span><b>' + fmtV(hi.p50) + ' ' + esc(u) +
          ' · ' + esc(hi.mes_nombre) + '</b></div>' +
        '<div class="cn-p50an__kv"><span>Mínimo</span><b>' + fmtV(lo.p50) + ' ' + esc(u) +
          ' · ' + esc(lo.mes_nombre) + '</b></div>' +
      '</div>' +
      '<div class="cn-p50an__note">Compromiso corporativo, nivel Upstream global. Sin real ' +
        'mensual asociado: la serie no lleva cumplimiento.</div>' +
    '</div>';
  }


#### Cambio 3.4.b — registrar el tipo en el dispatcher

**LOCALIZAR** estas líneas exactas (aprox. `:4341-4344`):

```javascript
             : (panel.tipo === "cuant_cmp")        ? __cnCuantCmpHtml(d)
             : (panel.tipo === "cuant_serie_ppto") ? __cnCuantSeriePptoHtml(d)
             : __cnCuantCardHtml(d);
```

**SUSTITUIR POR:**

```javascript
             : (panel.tipo === "cuant_cmp")        ? __cnCuantCmpHtml(d)
             : (panel.tipo === "cuant_serie_ppto") ? __cnCuantSeriePptoHtml(d)
             // [2026-09-07 · PANEL-P50-ANUAL] "p50_anual" (Analizar/referencia, rama GLOBAL):
             // serie mensual del P50 corporativo. Registrado ANTES del fallback por la misma
             // razón que "p50_vp": __cnCuantCardHtml NO valida el tipo y pintaría una tarjeta
             // KPI leyendo campos (estado/cumplimiento_pct/nivel) que este contrato no tiene.
             : (panel.tipo === "p50_anual")        ? __cnP50AnualHtml(d)
             : __cnCuantCardHtml(d);
```

⚠️ **NO añadir `"p50_anual"` a la lista de `__cnPanelMesCargar` (`:4415`)**: esa lista es para paneles con pintor diferido (Plotly). Este es puro y síncrono, como `p50_vp`.

### 3.5 AÑADIR — CSS en `colapsable.css`

**Archivo:** `c:\APLICACIONES\ProdIA\Repo ProdIA\frontend\static\css\colapsable.css`

**LOCALIZAR** el final del bloque `cn-p50vp` — esta línea exacta (aprox. `:2438`):

```css
.cn-p50vp__note { margin-top: 8px; font-size: 11px; color: #8A968E; font-style: italic; }
```

**AÑADIR INMEDIATAMENTE DESPUÉS:**

```css

/* [2026-09-07 · PANEL-P50-ANUAL] Serie mensual del compromiso P50 corporativo.
   Reusa la paleta ya establecida del bloque cn-p50vp de arriba (grises #8A968E/#6B7A74, verde
   #0F6B4C, texto #17241E). Sin overflow propio: el unico scroller del panel derecho es .cn-col
   (regla del scroll unico, ver :1367-1372).
   🔑 SIN regla de area/gradiente: la linea va con fill:none, igual que cn-p50vp__linea-p50. El
   relleno bajo la curva se retiro del proyecto el 2026-08-31 por no significar nada con el eje
   fuera de cero (ver multitab_shell.js, __cnSerieMesPlot). */
.cn-p50an { font-size: 13px; color: #3C4A44; }
.cn-p50an__hd { display: flex; align-items: center; justify-content: space-between; gap: 10px;
  margin-bottom: 6px; }
.cn-p50an__name { font-size: 11px; font-weight: 700; text-transform: uppercase;
  letter-spacing: .08em; color: #6B7A74; }
.cn-p50an__svg { display: block; width: 100%; height: auto; margin: 4px 0 8px; }
.cn-p50an__linea { fill: none; stroke: #0F6B4C; stroke-width: 2.6; stroke-linejoin: round;
  stroke-linecap: round; }
.cn-p50an__punto { fill: #0F6B4C; }
.cn-p50an__guia { stroke: #EEF1F0; stroke-width: 1; }
.cn-p50an__aytx { font-size: 8px; fill: #8A968E; font-variant-numeric: tabular-nums; }
.cn-p50an__axtx { font-size: 7.5px; fill: #8A968E; }
.cn-p50an__foot { display: flex; flex-direction: column; gap: 4px; padding-top: 8px;
  border-top: 1px solid #EEF1F0; }
.cn-p50an__kv { display: flex; justify-content: space-between; gap: 12px; font-size: 12.5px; }
.cn-p50an__kv span { color: #6B7A74; }
.cn-p50an__kv b { font-variant-numeric: tabular-nums; color: #17241E; }
.cn-p50an__note { margin-top: 8px; font-size: 11px; color: #8A968E; font-style: italic; }
```

### 3.6 MODIFICAR — actualizar `test_p8` (H3)

**Archivo:** `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\tests\test_p50_referencia.py`

⚠️ Este test afirma hoy lo contrario de lo que implementa el plan. **Se actualiza con su razón, NO se borra.**

**LOCALIZAR** estas líneas exactas (`:444-455`):

```python
def test_p8_global_ecp_sigue_sin_panel(monkeypatch):
    # D1: el global ECP NO produce panel (su caso nativo es el artifact corporativo, otro plan).
    monkeypatch.setattr(_ra._resolver, "resolver_unico", lambda t: None)
    info_global = {"encontrada": True, "unidad": "kbpe", "corte": "2026-05-18",
                   "productos": [{"entidad": "Crudo", "real_mes": 501.7, "base_p50": 521.8,
                                  "cumpl_p50": 96.1, "compromiso": None, "compromiso_difiere": False}],
                   "totales": []}
    r = _ra.responder_con_panel("cual es el p50 de crudo?",
                                _president_fn=lambda periodo=None: info_global,
                                _serie_fn=lambda vice, prod: _fake_serie_gor(vice, prod))
    assert r["panel"] is None
```

**SUSTITUIR POR:**

```python
_FAKE_SERIE_ANUAL = {
    "anio": 2026, "unidad": "kboepd", "fmt": "anual", "fuente": "core.p50_2026",
    "serie": [{"mes": 1, "mes_nombre": "Enero", "p50": 744.2},
              {"mes": 2, "mes_nombre": "Febrero", "p50": 741.2},
              {"mes": 3, "mes_nombre": "Marzo", "p50": 732.8},
              {"mes": 4, "mes_nombre": "Abril", "p50": 714.9}],
}


def test_p8_global_ecp_emite_panel_anual(monkeypatch):
    # [2026-09-07 · PANEL-P50-ANUAL] ANTES este test afirmaba `panel is None` para el global
    # ECP (D1: "su caso nativo es el artifact corporativo, otro plan"). Ese plan llego: la rama
    # global YA emite panel "p50_anual" cuando core.p50_2026 tiene la serie de 12 meses.
    monkeypatch.setattr(_ra._resolver, "resolver_unico", lambda t: None)
    r = _ra.responder_con_panel("cual es el p50 de crudo?",
                                _president_fn=lambda periodo=None: {"encontrada": False},
                                _serie_fn=lambda vice, prod: _fake_serie_gor(vice, prod),
                                _serie_anual_fn=lambda: _FAKE_SERIE_ANUAL)
    assert r["panel"] is not None
    assert r["panel"]["tipo"] == "p50_anual"
    assert len(r["panel"]["datos"]["serie"]) == 4
    assert r["panel"]["datos"]["unidad"] == "kboepd"


def test_p8b_global_sin_serie_anual_cae_a_la_cifra_del_corte(monkeypatch):
    # Degradacion (H12): sin la migracion 011 aplicada en este entorno, `serie_anual_p50` devuelve
    # None y la rama global debe seguir respondiendo la cifra del corte, SIN panel — el
    # comportamiento previo a este plan. No puede romperse una respuesta que hoy si funciona.
    monkeypatch.setattr(_ra._resolver, "resolver_unico", lambda t: None)
    info_global = {"encontrada": True, "unidad": "kbpe", "corte": "2026-05-18",
                   "productos": [{"entidad": "Crudo", "real_mes": 501.7, "base_p50": 521.8,
                                  "cumpl_p50": 96.1, "compromiso": None, "compromiso_difiere": False}],
                   "totales": []}
    r = _ra.responder_con_panel("cual es el p50 de crudo?",
                                _president_fn=lambda periodo=None: info_global,
                                _serie_fn=lambda vice, prod: _fake_serie_gor(vice, prod),
                                _serie_anual_fn=lambda: None)
    assert r["panel"] is None
    assert "521,8" in r["mensaje"] or "501,7" in r["mensaje"]
```

### 3.7 MODIFICAR — cache-buster en `main.html` (H13)

**Archivo:** `c:\APLICACIONES\ProdIA\Repo ProdIA\frontend\templates\main.html`

⚠️ **Paso obligatorio, no cosmético.** Sin él el navegador sirve el JS y el CSS cacheados y el
panel **no aparece, con la consola limpia** (H13).

#### Cambio 3.7.a — CSS

**LOCALIZAR** (`main.html:5`):

```html
    <link rel="stylesheet" href="{{ url_for('static', filename='css/colapsable.css') }}?v=20260831a">
```

**SUSTITUIR POR:**

```html
    <link rel="stylesheet" href="{{ url_for('static', filename='css/colapsable.css') }}?v=20260907a">
```

#### Cambio 3.7.b — JS

**LOCALIZAR** (`main.html:88`):

```html
<script src="{{ url_for('static', filename='js/multitab_shell.js') }}?v=20260831j"></script>
```

**SUSTITUIR POR:**

```html
<script src="{{ url_for('static', filename='js/multitab_shell.js') }}?v=20260907a"></script>
```

⚠️ **NO tocar `login.html`** (`:39` y `:43`). Son `rel="prefetch"` con sufijos distintos
(`20260903i` / `20260831a`): solo precargan, y cambiarlos no aporta nada a este plan.

---

## §4 Orden de ejecución

| # | Acción | Archivo | Verificación |
|---|---|---|---|
| 1 | §3.1 — `serie_anual_p50` + `formatear_serie_anual` | `p50_referencia.py` | Las funciones existen. `sa`, `get_engine` y `_kbpe` ya estaban (H16): **no añadas imports** |
| 2 | §3.2.a — parámetro `_serie_anual_fn` + resolución | `respuesta_analizar.py` | `serie_anual_fn` definida antes de usarse |
| 3 | §3.2.b — emitir el panel en la rama global | `respuesta_analizar.py` | La rama `es_vp` quedó **intacta** |
| 4 | §3.2.c — docstring | `respuesta_analizar.py` | — |
| 5 | §3.3 — comentario | `maquina_q.py` | **Solo comentario**, cero cambio funcional |
| 6 | §3.4.a — `__cnP50AnualHtml` | `multitab_shell.js` | La función existe antes del dispatcher |
| 7 | §3.4.b — registro en dispatcher | `multitab_shell.js` | **Antes** de `__cnCuantCardHtml(d);` |
| 8 | §3.5 — CSS | `colapsable.css` | Tras el bloque `cn-p50vp` |
| 9 | §3.6 — tests | `test_p50_referencia.py` | — |
| 10 | **§3.7 — cache-buster** | `main.html` | **Los dos sufijos** a `20260907a` |
| 11 | Validación §6.1 | — | V1→V9 en verde |

⚠️ **El orden 1→2→3 no es negociable:** `serie_anual_p50` debe existir antes de que `respuesta_analizar` la referencie, o el import falla.

⚠️ **El orden 6→7 tampoco:** el dispatcher no puede llamar a una función que aún no está declarada en el archivo.

⚠️ **El paso 10 va DESPUÉS de 6-8**, nunca antes: subir el sufijo con el JS a medio editar
publicaría una versión rota y la cachearía con el sufijo nuevo.

---

## §5 Reglas no negociables

1. **CERO modificaciones** fuera de §3. Si ves algo mejorable, anótalo y repórtalo al final.
2. **NO tocar la rama `es_vp`** de `respuesta_analizar.py:273-285` ni `__cnP50VpHtml`. El panel `p50_vp` debe seguir idéntico.
3. **NO añadir área bajo la curva, ni gradientes, ni `fill` distinto de `none`** en la línea. H2 lo prohíbe con medición.
4. **NO anclar el eje Y en cero.** El cálculo de §3.4.a es el de `p50_vp`, clonado literal.
5. **NO inventar `real`, `pct`, `gap` ni chip de cumplimiento.** La tabla no tiene real (H1).
6. **NO borrar `test_p8`**: se actualiza según §3.6, conservando la razón del cambio.
7. **NO añadir `"p50_anual"` a `__cnPanelMesCargar`** (`:4415`). Es panel puro, no diferido.
8. **NO quitar el `try/except`** de `serie_anual_p50`. Es lo que evita romper la rama global en entornos sin la migración 011 (H12).
9. **JavaScript ES5**: `var` + `function`. Nada de `const`, `let`, arrow functions ni template literals.
10. Código y comentarios **en español**. SQL con `sa.text(...)` y parámetros nombrados.
11. **NO añadir imports.** `sa`, `get_engine`, `_kbpe`, `esc`, `__cnMesAbr` y `_CIERRE_PROY` ya existen, verificados uno a uno (H16). Si alguno faltara: **DETENTE y reporta**.
12. **NO tocar `login.html`.** Sus referencias son `prefetch` y quedan fuera del alcance (H13).
13. **NO olvidar el paso 10** (cache-buster). Sin él, todo lo demás es invisible en el navegador y el fallo es mudo.
14. **Si algo no calza con el código real: DETENTE y reporta.**

---

## §6 Validación

### 6.1 Estática — la hace el EXECUTOR

Comandos desde `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend`, **uno por uno**, en PowerShell normal (sin administrador).

| # | Comando | Esperado |
|---|---|---|
| V1 | `uv run python -c "import ast; ast.parse(open(r'app/features/consulta_v2/analizar/p50_referencia.py',encoding='utf-8').read()); print('OK')"` | `OK` |
| V2 | `uv run python -c "from app.features.consulta_v2.analizar import p50_referencia as p; print(hasattr(p,'serie_anual_p50'), hasattr(p,'formatear_serie_anual'))"` | `True True` |
| V3 | `uv run python -c "from app.features.consulta_v2 import respuesta_analizar; print('import OK')"` | `import OK` |
| V4 | `uv run pytest tests/test_p50_referencia.py -q` | Todos pasan (incluidos `p8` y `p8b` nuevos) |
| V5 | `uv run pytest -q` | ⚠️ **10 fallos preexistentes y ajenos** documentados en `CLAUDE.md` §6 — esos no cuentan. Cero regresiones nuevas |

**V6 — la serie sale de la BD.** Bloque multilínea: en PowerShell puede quedarse en `>>`; pulsa Enter.

```powershell
uv run python -c "
from app.features.consulta_v2.analizar.p50_referencia import serie_anual_p50, formatear_serie_anual
d = serie_anual_p50()
print('puntos:', len(d['serie']), '| unidad:', d['unidad'], '| fmt:', d['fmt'])
print('ene:', d['serie'][0]['p50'], '| dic:', d['serie'][-1]['p50'])
print()
print(formatear_serie_anual(d))
"
```

Esperado: `puntos: 12`, `unidad: kboepd`, `fmt: anual`, `ene: 744.2`, `dic: 733.3`, y un texto que mencione el mínimo en abril y el máximo en julio.

**V7 — el panel se emite de punta a punta.**

```powershell
uv run python -c "
from app.features.consulta_v2 import respuesta_analizar as ra
r = ra.responder_con_panel('como es el comportamiento del P50 para 2026?')
p = r.get('panel')
print('panel tipo:', (p or {}).get('tipo'))
print('puntos:', len(((p or {}).get('datos') or {}).get('serie') or []))
"
```

Esperado: `panel tipo: p50_anual` y `puntos: 12`.

⚠️ **Si sale `panel tipo: None`, la rama global no está emitiendo. DETENTE y reporta.**

**V8 — sintaxis del JS y orden del registro** (desde `c:\APLICACIONES\ProdIA\Repo ProdIA\frontend`):

```powershell
node --check static\js\multitab_shell.js
```

Esperado: sin salida (sintaxis correcta). Si `node` no está disponible, reporta **V8 NO EJECUTADO** en vez de darlo por bueno.

Y el orden del registro (desde `backend\backend`):

```powershell
uv run python -c "
s = open(r'../../frontend/static/js/multitab_shell.js', encoding='utf-8').read()
i_reg = s.find('panel.tipo === \"p50_anual\"')
i_fb  = s.find(': __cnCuantCardHtml(d);')
i_fn  = s.find('function __cnP50AnualHtml')
print('funcion declarada:', i_fn > 0)
print('registro antes del fallback:', 0 < i_reg < i_fb)
print('funcion antes del registro:', 0 < i_fn < i_reg)
"
```

Esperado: las tres en `True`.

**V9 — 🔑 el cache-buster subió en los dos** (desde `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend`):

```powershell
uv run python -c "
import re
s = open(r'../../frontend/templates/main.html', encoding='utf-8').read()
js  = re.search(r\"multitab_shell\.js'\) \}\}\?v=([0-9a-z]+)\", s)
css = re.search(r\"colapsable\.css'\) \}\}\?v=([0-9a-z]+)\", s)
print('js :', js.group(1) if js else 'NO ENCONTRADO')
print('css:', css.group(1) if css else 'NO ENCONTRADO')
print('AMBOS ACTUALIZADOS:', bool(js and css and js.group(1)=='20260907a' and css.group(1)=='20260907a'))
"
```

Esperado: `js : 20260907a`, `css: 20260907a`, `AMBOS ACTUALIZADOS: True`.

⚠️ **Si sale `False`, el panel no se verá en el navegador aunque todo lo demás esté bien, y el
fallo será mudo (consola limpia). DETENTE y reporta.**

### 6.2 Humana — la hace el USUARIO

El executor **no puede** validar esto: no tiene navegador, y la app real corre en el **servidor de pruebas**.

| # | Qué mirar | Dónde |
|---|---|---|
| H-1 | Preguntar «¿cómo es el comportamiento del P50 para 2026?» → aparece el panel con la línea de 12 puntos | `http://localhost:5029` |
| H-2 | La curva **se ve con relieve** (baja a abril, pico en julio), no como una recta plana | El panel |
| H-3 | Los 12 rótulos de mes caben y se leen sin solaparse | El panel |
| H-4 | F12 → Console **sin errores** | Navegador |
| H-5 | **No-regresión:** preguntar por el P50 de una vicepresidencia (p. ej. «el P50 de GOR») sigue pintando el panel `p50_vp` de dos líneas, igual que antes | `http://localhost:5029` |
| H-6 | **En Pruebas:** aplicar la migración 011 antes del despliegue — `cd backend\backend` y `uv run python apply_migration.py ../db/migrations/011_p50_2026.sql`. Esperado: `[OK] Migracion aplicada: 011_p50_2026.sql` | Servidor de pruebas |
| H-7 | **Recarga forzada** (Ctrl+F5) la primera vez, para descartar caché del navegador anterior al cambio de sufijo | Navegador |

⚠️ **Si el panel no pinta y la consola está limpia:** el sospechoso número uno es el cache-buster
(H13), no el dato. Verificar V9 antes de auditar el backend — es un fallo recurrente conocido de
este proyecto y su síntoma es idéntico al de un bug de datos.

⚠️ **Orden del despliegue en Pruebas:** primero la migración (H-6), después la validación visual.
Al revés, `serie_anual_p50` devuelve `None`, la rama global cae a la cifra del corte y parecería
que el plan no funciona — cuando solo falta el SQL (H15).

**Estado al terminar el executor: «implementado, PENDIENTE de validación humana».** Nunca «completado» (regla R3, `CLAUDE.md` §10.4).

---

## §7 Fuera de alcance

| Qué | Por qué |
|---|---|
| **Área sombreada bajo la curva** | H2: no existe en el repo y se retiró a propósito el 2026-08-31 por no significar nada con el eje fuera de cero. Decisión 2 del usuario |
| **Línea de meta anual (735,3)** | Decisión 4 del usuario. Requiere además decidir de dónde sale: la lámina la da, pero `Reporte DPP` t5 la tiene ingerida y sería mejor fuente |
| **Serie del REAL mensual corporativo** | La tabla no lo tiene (H1). Habría que localizar una fuente mensual de real Upstream global — no auditada |
| **Cargar meta y proyección anual (735,3 / 719,4)** | Existen en `Reporte DPP` t4/t5, fila `TOTAL UPSTREAM`, y **ya se ingieren**. Conectarlas es un plan aparte, mejor que transcribir a mano |
| **Que Cuantificar responda el P50** | `ejecutor.py:110-114` rechaza a propósito. Tocar el Motor Q exige medir el golden de 92 casos (gate ≥90%) |
| **P50 de años distintos de 2026** | `serie_anual_p50` declina explícitamente: solo existe la tabla de 2026 |
| **Migrar a Azure / desplegar** | Skill `migrar-a-azure`, después de validar en Pruebas (`CLAUDE.md` §9) |

---

## Prompt para el agente EXECUTOR

```
Eres un agente EXECUTOR. Lee completo el plan
c:\APLICACIONES\ProdIA\Repo ProdIA\backend\Planes\plan_PANEL-P50-ANUAL_20260907.md
y ejecútalo AL PIE DE LA LETRA.
Reglas: CERO modificaciones. Orden secuencial. Si falla, DETENTE. Reporta: ✅/❌ Paso N.
Al final: archivos tocados + "¿Hago commit?"
```
