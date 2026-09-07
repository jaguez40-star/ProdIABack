# Plan `PANEL-P50-ANUAL-V2` — rehacer el panel con Plotly + meta anual + texto con lectura

| | |
|---|---|
| **ID tarea** | `PANEL-P50-ANUAL-V2` |
| **Fecha** | 2026-09-07 |
| **Versión** | **v2 — re-auditado.** La v1 dejaba 8 reglas CSS huérfanas y usaba markdown que el chat no renderiza. Ver H10 y H10-bis |
| **Repos** | `backend` (ProdIABack) **y** `frontend` (ProdIAWebFront) |
| **Alcance** | Sustituir el SVG a mano del panel `p50_anual` por el molde **Plotly** del proyecto, añadir la **línea de meta anual** y reescribir el **texto** de la respuesta |
| **Qué NO se toca** | El panel `p50_vp` · `serie_anual_p50` (la consulta a BD no cambia) · el endpoint `/president` · el clasificador · el enrutado de `respuesta_analizar` |
| **Archivos** | **5** — 2 backend, 3 frontend |

### Decisiones cerradas del usuario

1. **Rehacer el gráfico con Plotly**, clonando el molde de «producción diaria vs promedio» que ya existe. El SVG a mano se retira.
2. **Añadir la meta anual 735,3** como línea de referencia horizontal. (Revierte la decisión 4 del plan anterior: el usuario la pidió al ver el resultado.)
3. **Reescribir el texto**: debe contar el comportamiento (caída, recuperación, pico, cierre) y el promedio vs meta — no solo mínimo y máximo.

---

## §0 Contexto para el agente EXECUTOR

**Proyecto:** ProdIA — consulta conversacional de producción de petróleo y gas de Ecopetrol. Dos procesos: Flask en el 5029 (UI, repo `frontend`) y FastAPI/INGESTA en el 5030 (datos, repo `backend`). El navegador nunca habla con el 5030: Flask hace de proxy.

| Rol | Ruta absoluta |
|---|---|
| Datos + texto | `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\analizar\p50_referencia.py` |
| Tests | `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\tests\test_p50_referencia.py` |
| Pintor + dispatcher | `c:\APLICACIONES\ProdIA\Repo ProdIA\frontend\static\js\multitab_shell.js` |
| Estilos | `c:\APLICACIONES\ProdIA\Repo ProdIA\frontend\static\css\colapsable.css` |
| Cache-buster | `c:\APLICACIONES\ProdIA\Repo ProdIA\frontend\MainChat\templates\mainchat_layout.html` **y** `c:\APLICACIONES\ProdIA\Repo ProdIA\frontend\templates\main.html` |

| | |
|---|---|
| Carpeta de trabajo backend | `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend` |
| Intérprete | `uv run python` (NO `python` a secas) |

**Estado de partida:** el panel `p50_anual` **ya existe y funciona** (plan `PANEL-P50-ANUAL`, commits `025aed8` + `58205a1` + `e17b9cd`). Lee `core.p50_2026` (12 meses, Upstream global, kboepd) y pinta un SVG a mano. Este plan **sustituye el pintor**, no crea el panel.

**Convenciones obligatorias:**
- **JavaScript ES5 clásico**: `var` + `function`. **Sin** arrow functions, **sin** template literals, **sin** `const`/`let`.
- Código y comentarios **en español**. Fecha los cambios con `[2026-09-07]`.
- **Si algo del plan no calza con el código real: DETENTE y reporta. No improvises.**

---

## §1 Hallazgos de la auditoría

### §1.1 🔴 H1 — Por qué el panel actual se ve mal: es una tarjeta de 320px estirada

`__cnP50AnualHtml` (`multitab_shell.js:5082`) emite un SVG con `viewBox="0 0 320 158"` y `width: 100%` en el CSS (`colapsable.css`, `.cn-p50an__svg`).

Se clonó de `__cnP50VpHtml`, que es una **tarjeta estrecha del panel lateral**. Pero `p50_anual` se pinta en el área ancha de Insights (~1000px): el SVG **escala x3**, y con él la tipografía. De ahí los `747,0` gigantes, los meses enormes y la línea basta que muestra la captura del usuario.

**El `font-size: 8px` del SVG se convierte en ~25px reales.** No es un problema de estilo, es de unidad: un SVG escalado agranda todo proporcionalmente.

**Decisión:** el molde correcto no es el SVG a mano, sino **Plotly**, que dibuja al tamaño real del contenedor y mantiene la tipografía en píxeles reales.

### §1.2 🔴 H2 — El molde a clonar: `analiza_tend` (`__cnAnzTendHtml` + `__cnTendMesInto`)

`multitab_shell.js:4562-4618`. Es **el caso más cercano** que existe: serie mensual, línea principal con `spline`, sin tarjeta KPI, y su comentario lo dice explícito (`:4560-4561`):

> «🔑 Sin tarjeta KPI: aquí no hay un número único que destacar — la respuesta ES la forma de la curva.»

Patrón en dos piezas:
1. **Constructor puro**: `__cnAnzTendHtml(d)` → `return __cnPanelMesHtml(d, "cn-tend-mes");` — emite envoltorio + host vacío.
2. **Pintor diferido**: `__cnTendMesInto(hostEl, d)` — monta el `Plotly.newPlot` **después** de insertar el bloque.

Layout canónico (`:4608-4617`), a clonar:

```javascript
margin: { l: 62, r: 18, t: 22, b: 30 }, height: 260, hovermode: "x unified",
showlegend: true, legend: { orientation: "h", y: -0.18, x: 0, font: { size: 11 } },
xaxis: { title: {...}, tickfont: { size: 11 }, showgrid: false },
yaxis: { title: {...}, tickfont: { size: 10 }, separatethousands: true,
         gridcolor: "#eef1ef", zeroline: false },
plot_bgcolor: "#fff", paper_bgcolor: "#fff"
```

### §1.3 🔴 H3 — El eje Y NO debe llevar `rangemode: "tozero"`

`analiza_tend` **no** fija `rangemode`, así que Plotly autoescala — y eso ya da un eje ajustado a los datos. Con la serie 714,9–747,0 la variación se ve.

⚠️ **Pero al añadir la meta (735,3, dentro del rango) el autoescalado sigue funcionando.** No hace falta `range` explícito. **NO copiar el `rangemode: "tozero"`** de `__cnAcumMesInto` (`:4539`): aplanaría la curva, que es justo lo que el usuario rechazó.

🔑 Si en el futuro se añade una referencia fuera del rango, habría que calcular `range` como hace `__cnDailyPlot` (`:2487-2497`). Hoy no aplica.

### §1.4 🔴 H4 — El envoltorio `.cp-foco > .cp-foco__panel.is-active` NO es decorativo

`__cnPanelMesHtml` (`multitab_shell.js:4447-4460`). Su comentario `:4437-4440` lo mide:

> «MEDIDO (2026-08-25): sin este envoltorio el grid queda en 20px y Plotly monta un SVG de **10px de alto — sin lanzar error**. Con él + la clase `--mes`: 375px de grid, 327px de plot.»

**Hay que usar `__cnPanelMesHtml`, no escribir el envoltorio a mano.** Un fallo aquí es mudo.

### §1.5 🟡 H5 — `__cnPanelMesHtml` colorea por PRODUCTO, y el P50 no es un producto

`:4448`: `var pI = __cnProdId(d.producto) || { color: "#6E7C75", soft: "#F1F4F1" };`

Y `__cnProdId` (`:3541`) devuelve `null` si el valor no está en `__CP_PROD` (CRUDO/GAS/BLANCOS). El P50 corporativo **no tiene producto**: caería al **gris neutro** `#6E7C75`.

**Decisión:** el backend envía `"producto": None` y el panel usa el **verde corporativo `#004236`** para la curva, pasado explícitamente al plot. El gris del envoltorio es correcto y no se fuerza: el P50 no es de ningún producto, y fingir que sí sería una identidad falsa.

🔑 `#004236` ya se usa en este archivo para el PPTO (`:2451`), es el verde institucional. La curva actual del SVG usa `#0F6B4C`, también válido; se mantiene ese para la curva y `#004236` queda para la meta.

### §1.6 🔴 H6 — La meta anual **se calcula de la serie**: es su promedio, exacto

**Medido contra la BD:**

```sql
SELECT ROUND(AVG(p50),1) FROM core.p50_2026;   -- → 735.3
```

**735,3 es exactamente la «Meta 2026» de la lámina gerencial.** No es coincidencia: el P50 anual se pacta como promedio diario del año, así que el promedio de los 12 meses ES la meta.

**Consecuencia de diseño, importante:** no hay que traer la meta de otra fuente (`Reporte DPP`), ni transcribirla a mano, ni añadir una columna. Se calcula en Python desde la serie que ya se lee. **Cero dependencias nuevas.**

⚠️ Se calcula en el **backend** (no en JS): el redondeo debe ser uno solo y trazable, y el texto de la respuesta también la usa.

### §1.7 🟡 H7 — El registro del pintor diferido: DOS sitios, no uno

Un panel Plotly necesita **dos** registros en el dispatcher, y `p50_anual` hoy solo tiene el primero:

1. **Constructor** (`:4349`, ya existe): `: (panel.tipo === "p50_anual") ? __cnP50AnualHtml(d)`
2. **Pintor diferido** (`:4420`, **FALTA**): la lista de tipos que llama a `__cnPanelMesCargar`:

```javascript
if (panel.tipo === "cuant_serie" || panel.tipo === "cuant_var" || panel.tipo === "cuant_acum" || panel.tipo === "analiza_tend" || panel.tipo === "cuant_cmp" || panel.tipo === "cuant_serie_ppto") __cnPanelMesCargar(blk, d, panel.tipo);
```

Y además el enrutado por tipo dentro de `__cnPanelMesPintar` (`:4762-4781`).

⚠️ **El plan anterior prohibía añadirlo a esa lista**, y era correcto entonces: el panel era SVG puro y síncrono. **Ahora es Plotly y SÍ debe estar.** Sin los tres registros, el host queda vacío y no se pinta nada, sin error.

### §1.8 🟢 H8 — El contrato de datos no cambia (salvo dos campos aditivos)

`serie_anual_p50` (`p50_referencia.py`) devuelve hoy `{anio, unidad, fmt, fuente, serie:[{mes, mes_nombre, p50}]}`.

`__cnTendMesInto` espera `d.meses` (etiquetas) y `d.valores`. **Se añaden esos dos campos derivados**, más `meta`, sin quitar `serie` — que los tests ya verifican y el texto usa.

Verificado: `_FAKE_SERIE_ANUAL` en `test_p50_referencia.py` comprueba `len(datos["serie"]) == 4` y `datos["unidad"]`. **Añadir campos no rompe esos asserts.**

### §1.9 🟢 H9 — Cache-buster: son DOS plantillas, y una se olvidó ayer

**El incidente del que sale este plan.** `multitab_shell.js` lo cargan **tres** plantillas:

| Plantilla | Sufijo hoy | ¿Se toca? |
|---|---|---|
| `templates/main.html:88` | `20260907a` | **SÍ** |
| `MainChat/templates/mainchat_layout.html:323` | `20260907a` | **SÍ** — es la de `/mainchat`, la que usa el usuario |
| `templates/login.html:43` | `20260903i` | **NO** — es `rel="prefetch"` |

`Colapsable/templates/colapsable_layout.html:5` usa otro blueprint (`url_for('colapsable.static', ...)`) y tampoco se toca.

⚠️ **Ayer solo se subió `main.html` y el panel no apareció**, con la consola limpia. Hora y media de diagnóstico. **Los dos sufijos suben a `20260907b`.**

### §1.10 🔴 H10 — El bloque CSS entero queda huérfano: se retiran las 14 reglas, no 6

**Corregido en la re-auditoría.** Una versión previa de este plan mandaba borrar solo las 6 reglas
del dibujo y **conservar** las del contenedor (`__hd`, `__name`, `__foot`, `__kv`, `__note`).
Era falso.

Medido: el molde Plotly (`__cnTendMesInto`, `:4573-4577`) emite **otras clases**, las del sistema
de tarjetas de Insights:

```javascript
'<div class="cn-ins__card"><div class="cn-ins__card-hd">…' +
'<div class="cn-ins__plot" data-p></div>' +
'<div class="cn-ins__cap" data-cap></div></div>'
```

Todas existen ya en `colapsable.css:1318-1352` y traen su propio borde, cabecera verde, padding y
pie. **El nuevo pintor no emite ni una sola clase `cn-p50an__*`**, así que las 14 reglas quedan
sin un solo consumidor.

**Decisión:** se borra el bloque completo, de `.cn-p50an {` hasta `.cn-p50an__note`, incluido su
comentario de cabecera. Dejar 8 reglas muertas sería deuda silenciosa: el próximo que lea el CSS
creería que el panel las usa.

🔑 Ganancia lateral: el panel pasa a heredar el estilo de tarjeta de Insights, así que se verá
**igual que el gráfico de producción diaria** — que es exactamente lo que pidió el usuario.

### §1.10-bis 🔴 H10-bis — La negrita del chat es `⟦…⟧`, **NUNCA** markdown `**`

**Encontrado en la re-auditoría.** Una versión previa de este plan escribía la meta con
`**{meta}**`. Habría salido con los asteriscos literales en pantalla.

`multitab_shell.js:7153-7160` lo prohíbe con su razón medida:

> «Marcador propio y ACOTADO (⟦…⟧ → `<strong>`), **NUNCA markdown genérico (`**`)**: […] el intro
> lo escribe un LLM a temperature 0.8 cuyo validador bloquea dígitos/unidades pero NO asteriscos
> […] Interpretar "**" habría renderizado en negrita un "**Claro, Javier**" espontáneo.»

```javascript
function __cnMarcador(t) {
  return String(t || "").replace(/⟦([^⟦⟧\n]*)⟧/g, "<strong>$1</strong>");
}
```

**Decisión:** la única negrita del texto usa `⟦…⟧`. El regex es de **una sola línea** y no
codicioso, así que el marcador debe abrirse y cerrarse en la misma línea — el de §3.1.b lo cumple.

### §1.11 🟢 H11 — Dependencias del código nuevo: verificadas una a una

| Símbolo | Dónde | Estado |
|---|---|---|
| `__cnPanelMesHtml` | `multitab_shell.js:4447` | ✅ existe |
| `__cnPanelMesCargar` | `:4420` (call site) | ✅ existe |
| `__cnPanelMesPintar` | `:4762` | ✅ existe |
| `__cnMilesEC` | `:2543` | ✅ existe |
| `esc` | `:29` | ✅ existe |
| `window.Plotly` | vendorizado, `plotly-2.26.0.min.js` | ✅ existe |
| `_kbpe` | `p50_referencia.py:252` (tras la inserción del plan previo) | ✅ existe |

**El código de §3 no necesita ni un import nuevo.**

### §1.11-bis 🟢 H11-bis — El golden de Analizar NO tiene casos de P50

Verificado, porque este plan cambia el **texto** de una respuesta de Analizar y eso podría romper
un golden:

- `app/features/consulta_v2/golden/analizar_golden.yaml` → **cero coincidencias** de `p50`/`P50`.
- Ningún test de `tests/` referencia `analizar_golden`.

**El cambio de texto no puede romper ningún golden.** Los 92 casos del golden de Cuantificar
(`CLAUDE.md` §6) tampoco se tocan: este plan no entra en `cuantificar/`.

⚠️ Los únicos tests que fijan el texto son los de §3.2, escritos en este plan.

### §1.12 🟢 H12 — Los pipelines no se ven afectados

`verificar_deploy.ps1` solo comprueba que los estáticos **existan**, no su contenido ni el sufijo (`:101-112`) → su resultado no cambia.

`migrar-a-azure` no excluye ninguno de los 5 archivos (`migrar_a_azure.ps1:65-68`) → viajan todos con verificación de hash.

⚠️ **Este plan NO toca la BD**: `core.p50_2026` ya está migrada en local y en el 139 (aplicada el 2026-09-07). **No hay migración nueva que correr.**

---

## §2 Estado actual

Ante «¿cómo es el comportamiento del P50 para 2026?» el sistema **ya responde** con panel `p50_anual`, verificado end-to-end en Pruebas contra la BD del 139.

**Los dos defectos, ambos visibles en la captura del usuario:**

1. **El gráfico**: SVG de 320px escalado a ~1000px → tipografía gigante, línea basta, tres números sueltos en el eje Y, sin rejilla, sin unidad, sin líneas de referencia. Al lado del gráfico de producción diaria del propio proyecto, desentona.
2. **El texto**: cinco líneas que solo dicen inicio, cierre, mínimo y máximo. No cuenta el comportamiento ni compara contra la meta.

---

## §3 Especificación

### 3.1 MODIFICAR — `p50_referencia.py`: campos para Plotly + meta anual

**Archivo:** `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\analizar\p50_referencia.py`

#### Cambio 3.1.a — enriquecer el contrato

**LOCALIZAR** estas líneas exactas (dentro de `serie_anual_p50`):

```python
    serie = [{"mes": int(r[0]), "mes_nombre": str(r[1]), "p50": float(r[2])} for r in rows]
    out = {
        "anio": anio,
        "unidad": str(rows[0][3]) if rows[0][3] else "kboepd",
        "fmt": "anual",
        "fuente": str(rows[0][4]) if rows[0][4] else "core.p50_2026",
        "serie": serie,
    }
```

**SUSTITUIR POR:**

```python
    serie = [{"mes": int(r[0]), "mes_nombre": str(r[1]), "p50": float(r[2])} for r in rows]
    # [2026-09-07 · PANEL-P50-ANUAL-V2] `meses`/`valores` son el contrato que espera el molde
    # Plotly del proyecto (ver __cnTendMesInto). `serie` se CONSERVA: la usan el texto y los tests.
    #
    # 🔑 META ANUAL = el promedio de los 12 meses. NO es un dato aparte que haya que traer de otra
    # fuente ni transcribir: el P50 anual se pacta como promedio diario del año, asi que sale de la
    # propia serie. MEDIDO contra la BD el 2026-09-07: AVG(p50) = 735.3, que es EXACTAMENTE la
    # "Meta 2026" de la lamina gerencial. Cero dependencias nuevas.
    #
    # Se redondea AQUI, una sola vez: el grafico y el texto deben decir la misma cifra.
    valores = [p["p50"] for p in serie]
    meta = round(sum(valores) / len(valores), 1) if valores else None
    out = {
        "anio": anio,
        "unidad": str(rows[0][3]) if rows[0][3] else "kboepd",
        "fmt": "anual",
        "fuente": str(rows[0][4]) if rows[0][4] else "core.p50_2026",
        "serie": serie,
        "meses": [p["mes_nombre"][:3] for p in serie],
        "valores": valores,
        "meta": meta,
        "producto": None,   # el P50 corporativo NO es de ningun producto (H5)
    }
```

#### Cambio 3.1.b — reescribir el texto

**LOCALIZAR** la función `formatear_serie_anual` **completa** — desde su `def` hasta su `return`, estas líneas exactas:

```python
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

**SUSTITUIR POR:**

```python
def formatear_serie_anual(d: dict) -> str:
    """Cuerpo de texto para la serie anual. PURA: no toca BD ni LLM.

    [2026-09-07 · PANEL-P50-ANUAL-V2] Antes decia solo inicio/cierre/min/max — cuatro cifras
    sueltas que no contaban NADA del comportamiento. Ahora narra la FORMA de la curva (el valle,
    el pico, el cierre) y la situa contra la meta anual, que es la pregunta de fondo cuando
    alguien pide "el comportamiento del P50".

    NO calcula cumplimiento contra el real: la tabla no tiene real mensual (ver la cabecera de
    serie_anual_p50). Comparar contra la meta SI es legitimo — ambas cifras salen de la misma
    serie.
    """
    serie = d.get("serie") or []
    if not serie:
        return "No tengo la serie del P50 disponible en este momento."
    u = d.get("unidad", "kboepd")
    anio = d.get("anio", 2026)
    lo = min(serie, key=lambda p: p["p50"])
    hi = max(serie, key=lambda p: p["p50"])
    ini, fin = serie[0], serie[-1]
    meta = d.get("meta")

    mes_l = lambda p: p["mes_nombre"].lower()
    partes = [f"📊 Compromiso P50 {anio} · serie mensual\n"]

    # 1) El encuadre: cuanto se compromete el año y contra que meta.
    if meta is not None:
        # ⟦…⟧ es el marcador de NEGRITA del chat (multitab_shell.js:7160, __cnMarcador). NO usar
        # markdown `**`: el shell lo prohibe explicitamente (:7153) y saldria literal en pantalla.
        partes.append(
            f"El compromiso promedia ⟦{_kbpe(meta)} {u}⟧ en el año, que es la meta {anio}. "
            f"No es una linea plana: oscila entre {_kbpe(lo['p50'])} y {_kbpe(hi['p50'])} {u} "
            f"segun el mes.\n")
    else:
        partes.append(
            f"El compromiso oscila entre {_kbpe(lo['p50'])} y {_kbpe(hi['p50'])} {u} "
            f"segun el mes.\n")

    # 2) La forma de la curva, que es lo que se pregunta. Se describe con los tres puntos que la
    #    definen (arranque, valle, pico) y el cierre, en su orden cronologico real.
    forma = (f"Arranca en {_kbpe(ini['p50'])} {u} ({mes_l(ini)}), "
             f"cae hasta el minimo de {_kbpe(lo['p50'])} {u} en {mes_l(lo)} "
             f"y remonta al maximo de {_kbpe(hi['p50'])} {u} en {mes_l(hi)}.")
    # El orden valle→pico solo es cierto si el minimo llega ANTES que el maximo. Si no, se dice al
    # reves en vez de afirmar una secuencia falsa.
    if lo["mes"] > hi["mes"]:
        forma = (f"Arranca en {_kbpe(ini['p50'])} {u} ({mes_l(ini)}), "
                 f"sube al maximo de {_kbpe(hi['p50'])} {u} en {mes_l(hi)} "
                 f"y baja al minimo de {_kbpe(lo['p50'])} {u} en {mes_l(lo)}.")
    partes.append(forma)

    # 3) El cierre, con su direccion respecto al arranque: dice si el año termina pidiendo mas o
    #    menos de lo que pedia al empezar.
    delta = fin["p50"] - ini["p50"]
    if abs(delta) < 0.05:
        cierre = f" Cierra en {_kbpe(fin['p50'])} {u} ({mes_l(fin)}), practicamente donde arranco."
    else:
        signo = "por debajo" if delta < 0 else "por encima"
        cierre = (f" Cierra en {_kbpe(fin['p50'])} {u} ({mes_l(fin)}), "
                  f"{_kbpe(abs(delta))} {u} {signo} del arranque.")
    partes.append(cierre)

    # 4) Cuantos meses piden por encima de la meta. Es la lectura operativa: donde aprieta el año.
    if meta is not None:
        sobre = [p for p in serie if p["p50"] > meta]
        if sobre:
            nombres = ", ".join(mes_l(p) for p in sobre)
            partes.append(f"\n\nPor encima de la meta: {len(sobre)} de {len(serie)} meses "
                          f"({nombres}).")

    return "".join(partes)
```

⚠️ **Verifica que `_kbpe` exista** en el módulo (lo añadió el plan anterior, `p50_referencia.py:252`). Si no está, **DETENTE y reporta**.

### 3.2 MODIFICAR — `test_p50_referencia.py`: fixture con los campos nuevos

**Archivo:** `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\tests\test_p50_referencia.py`

**LOCALIZAR** estas líneas exactas:

```python
_FAKE_SERIE_ANUAL = {
    "anio": 2026, "unidad": "kboepd", "fmt": "anual", "fuente": "core.p50_2026",
    "serie": [{"mes": 1, "mes_nombre": "Enero", "p50": 744.2},
              {"mes": 2, "mes_nombre": "Febrero", "p50": 741.2},
              {"mes": 3, "mes_nombre": "Marzo", "p50": 732.8},
              {"mes": 4, "mes_nombre": "Abril", "p50": 714.9}],
}
```

**SUSTITUIR POR:**

```python
_FAKE_SERIE_ANUAL = {
    "anio": 2026, "unidad": "kboepd", "fmt": "anual", "fuente": "core.p50_2026",
    "serie": [{"mes": 1, "mes_nombre": "Enero", "p50": 744.2},
              {"mes": 2, "mes_nombre": "Febrero", "p50": 741.2},
              {"mes": 3, "mes_nombre": "Marzo", "p50": 732.8},
              {"mes": 4, "mes_nombre": "Abril", "p50": 714.9}],
    # [2026-09-07 · PANEL-P50-ANUAL-V2] Campos del contrato Plotly. `meta` = promedio de los 4
    # valores de este fixture (733.275 -> 733.3), no la meta real del año: el fixture tiene 4
    # meses, no 12.
    "meses": ["Ene", "Feb", "Mar", "Abr"],
    "valores": [744.2, 741.2, 732.8, 714.9],
    "meta": 733.3,
    "producto": None,
}


def test_p12_serie_anual_trae_contrato_plotly():
    """[2026-09-07 · PANEL-P50-ANUAL-V2] El molde Plotly del proyecto (__cnTendMesInto) lee
    `meses`/`valores`, no `serie`. Este test fija ese contrato contra la BD real: si alguien
    quita esos campos, el panel deja de pintarse SIN error visible."""
    _engine_o_skip()
    d = _p50.serie_anual_p50()
    assert d is not None
    assert len(d["serie"]) == 12
    assert len(d["meses"]) == 12 and len(d["valores"]) == 12
    assert d["meses"][0] == "Ene" and d["meses"][-1] == "Dic"
    assert d["valores"][0] == 744.2 and d["valores"][-1] == 733.3
    # 🔑 La meta anual ES el promedio de los 12 meses — verificado contra la lamina gerencial
    # ("Meta 2026 = 735,3") y contra la BD (SELECT ROUND(AVG(p50),1) -> 735.3).
    assert d["meta"] == 735.3
    assert d["producto"] is None


def test_p13_texto_anual_narra_la_forma_y_la_meta():
    """El texto debe contar el comportamiento, no solo listar cifras: valle, pico, cierre y
    posicion frente a la meta. Antes decia solo min/max y el usuario lo rechazo por escueto."""
    _engine_o_skip()
    d = _p50.serie_anual_p50()
    txt = _p50.formatear_serie_anual(d)
    for esperado in ("735,3", "714,9", "747,0", "abril", "julio", "meta"):
        assert esperado in txt, f"falta «{esperado}» en el texto"
```

### 3.3 MODIFICAR — `multitab_shell.js`: sustituir el pintor por Plotly

**Archivo:** `c:\APLICACIONES\ProdIA\Repo ProdIA\frontend\static\js\multitab_shell.js`

#### Cambio 3.3.a — reemplazar `__cnP50AnualHtml`

**LOCALIZAR** el bloque completo que empieza con el comentario y la función. La primera línea a localizar es:

```javascript
  // [2026-09-07 · PANEL-P50-ANUAL] Serie mensual del compromiso P50 corporativo (12 meses).
```

y el bloque termina en la línea `  }` que cierra `__cnP50AnualHtml`, justo antes de:

```javascript
  // [2026-08-11] Dona de PARTICIPACIÓN (top N + "Otros"), en % sobre la producción total. SVG
```

⚠️ **Borra TODO ese bloque** (el comentario de cabecera, la función entera y sus funciones internas `fmtV`, `xAt`, `yAt`) y **sustitúyelo** por:

```javascript
  // [2026-09-07 · PANEL-P50-ANUAL-V2] Serie mensual del compromiso P50 corporativo (12 meses).
  //
  // 🔑 ANTES era un SVG a mano clonado de __cnP50VpHtml. Se retiro: aquel es una TARJETA de
  // 320px del panel lateral, y este panel se pinta en el area ancha de Insights (~1000px). El
  // SVG escalaba x3 y con el la tipografia — los numeros del eje salian gigantes y la linea
  // basta. Medido contra la captura del usuario, 2026-09-07.
  //
  // Molde = __cnAnzTendHtml/__cnTendMesInto (analiza_tend, :4562): serie mensual, una linea
  // principal, sin tarjeta KPI. Constructor PURO + pintor diferido, como el resto de paneles
  // mensuales del proyecto.
  function __cnP50AnualHtml(d) {
    if (!d || !d.valores || !d.valores.length) return "";
    return __cnPanelMesHtml(d, "cn-p50an-mes");
  }

  // Pintor diferido del panel anual del P50. Se llama DESPUES de insertar el bloque en el DOM
  // (via __cnPanelMesCargar), porque Plotly necesita un contenedor con ancho real.
  function __cnP50AnualInto(hostEl, d) {
    var meses = d.meses || [], vals = d.valores || [];
    var u = d.unidad || "kboepd";
    var anio = d.anio || 2026;
    var meta = (d.meta != null) ? d.meta : null;

    hostEl.innerHTML =
      '<div class="cn-ins__card"><div class="cn-ins__card-hd"><i class="bi bi-graph-up"></i> ' +
      'Compromiso P50 · ' + esc(String(anio)) +
      '</div><div class="cn-ins__plot" data-p></div>' +
      '<div class="cn-ins__cap" data-cap></div></div>';
    var elp = hostEl.querySelector("[data-p]");
    if (!vals.length) {
      elp.innerHTML = '<div class="p-2 text-muted small">Sin serie anual del P50.</div>';
      return;
    }
    if (!window.Plotly) { elp.innerHTML = '<div class="text-muted small p-2">(Plotly no disponible)</div>'; return; }

    // Verde corporativo. El P50 NO es de ningun producto, asi que no se usa __cnProdCol: ese
    // accessor colorea por CRUDO/GAS/BLANCOS y devolveria el gris neutro (H5).
    var col = "#0F6B4C";
    var fmtV = function (v) {
      return Number(v).toLocaleString("es-CO", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
    };

    var traces = [{
      x: meses, y: vals, name: "Compromiso P50",
      type: "scatter", mode: "lines+markers",
      line: { color: col, width: 2.5, shape: "spline", smoothing: 0.8 },
      marker: { color: col, size: 7 },
      customdata: vals.map(fmtV),
      hovertemplate: "%{x}<br>P50: %{customdata} " + u + "<extra></extra>"
    }];

    var shapes = [], anns = [];
    // Linea de META ANUAL. Es el promedio de los 12 meses, calculado en el backend — la misma
    // cifra que dice el texto de la respuesta (735,3 en 2026, la "Meta 2026" de la lamina).
    // Punteada y en verde institucional, igual que la referencia de PPTO de __cnDailyPlot:2451.
    if (meta != null) {
      shapes.push({ type: "line", xref: "paper", yref: "y", x0: 0, x1: 1, y0: meta, y1: meta,
        line: { color: "#004236", width: 1.5, dash: "dot" } });
      anns.push({ x: 1, y: meta, xref: "paper", yref: "y", xanchor: "right", yanchor: "bottom",
        text: "meta " + anio + " · " + fmtV(meta) + " " + u,
        showarrow: false, font: { size: 10, color: "#004236" } });
    }

    // 🔑 SIN `rangemode: "tozero"`: el autoescalado de Plotly ajusta el eje a la banda real de los
    // datos (714,9..747,0) y la variacion se lee. Anclado en cero la curva seria casi una recta —
    // que es justo lo que el usuario rechazo del primer intento.
    window.Plotly.newPlot(elp, traces, {
      margin: { l: 62, r: 18, t: 22, b: 30 }, height: 260, hovermode: "x unified",
      showlegend: false,
      shapes: shapes, annotations: anns,
      xaxis: { title: { text: "Mes", font: { size: 11 } }, tickfont: { size: 11 }, showgrid: false },
      yaxis: {
        title: { text: "Compromiso (" + u + ")", font: { size: 11 } },
        tickfont: { size: 10 }, separatethousands: true, gridcolor: "#eef1ef", zeroline: false
      },
      plot_bgcolor: "#fff", paper_bgcolor: "#fff"
    }, { displayModeBar: false, responsive: true });

    var cap = hostEl.querySelector("[data-cap]");
    if (cap) {
      cap.innerHTML = 'Compromiso corporativo, nivel Upstream global. Sin real mensual asociado: ' +
        'la serie no lleva cumplimiento.';
    }
  }

```

#### Cambio 3.3.b — registrar el pintor diferido (H7)

**LOCALIZAR** esta línea exacta (`:4420`):

```javascript
    if (panel.tipo === "cuant_serie" || panel.tipo === "cuant_var" || panel.tipo === "cuant_acum" || panel.tipo === "analiza_tend" || panel.tipo === "cuant_cmp" || panel.tipo === "cuant_serie_ppto") __cnPanelMesCargar(blk, d, panel.tipo);
```

**SUSTITUIR POR:**

```javascript
    // [2026-09-07 · PANEL-P50-ANUAL-V2] +p50_anual: paso de SVG puro a Plotly, asi que ahora SI
    // necesita pintor diferido. Sin esta linea el host queda vacio y no se pinta nada, sin error.
    if (panel.tipo === "cuant_serie" || panel.tipo === "cuant_var" || panel.tipo === "cuant_acum" || panel.tipo === "analiza_tend" || panel.tipo === "cuant_cmp" || panel.tipo === "cuant_serie_ppto" || panel.tipo === "p50_anual") __cnPanelMesCargar(blk, d, panel.tipo);
```

#### Cambio 3.3.c — enrutar el tipo dentro de `__cnPanelMesPintar`

**LOCALIZAR** estas líneas exactas:

```javascript
    } else if (tipo === "cuant_serie_ppto") {
      var hp = blk.querySelector(".cn-seriep-mes");
      if (hp) __cnSeriePptoInto(hp, d);
    }
  }
```

**SUSTITUIR POR:**

```javascript
    } else if (tipo === "cuant_serie_ppto") {
      var hp = blk.querySelector(".cn-seriep-mes");
      if (hp) __cnSeriePptoInto(hp, d);
    } else if (tipo === "p50_anual") {
      var hpa = blk.querySelector(".cn-p50an-mes");
      if (hpa) __cnP50AnualInto(hpa, d);
    }
  }
```

### 3.4 MODIFICAR — `colapsable.css`: retirar las reglas del SVG (H10)

**Archivo:** `c:\APLICACIONES\ProdIA\Repo ProdIA\frontend\static\css\colapsable.css`

⚠️ **Se borra el bloque ENTERO (14 reglas), no solo las del dibujo** (H10). El pintor nuevo emite
clases `cn-ins__*`, no `cn-p50an__*`: **ninguna** de estas 14 tiene ya consumidor.

**LOCALIZAR** desde el comentario de cabecera hasta la última regla — este bloque completo
(aprox. `:2440-2464`):

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

**SUSTITUIR POR:**

```css
/* [2026-09-07 · PANEL-P50-ANUAL-V2] El bloque .cn-p50an* se retiro ENTERO (14 reglas). El panel
   paso de un SVG a mano a Plotly, y el molde del proyecto (__cnTendMesInto) emite las clases del
   sistema de tarjetas de Insights — .cn-ins__card / __card-hd / __plot / __cap, definidas arriba
   en :1318-1352 — asi que ninguna de estas reglas tenia ya consumidor.
   El SVG de 320px se escalaba x3 en el area ancha de Insights y la tipografia salia gigante;
   Plotly dibuja al ancho real del contenedor. Ver el plan PANEL-P50-ANUAL-V2, H1 y H10. */
```

⚠️ **NO borres** el bloque `.cn-p50vp__*` que está justo encima: es del panel por vicepresidencia,
que sigue siendo SVG y sigue vivo. Solo se retira `.cn-p50an*`.

### 3.5 MODIFICAR — cache-buster en LAS DOS plantillas (H9)

⚠️ **Las dos. Ayer se olvidó una y costó hora y media de diagnóstico.**

**Archivo 1:** `c:\APLICACIONES\ProdIA\Repo ProdIA\frontend\templates\main.html`

**LOCALIZAR** (`:5`) → **SUSTITUIR** `?v=20260907a` por `?v=20260907b`:

```html
    <link rel="stylesheet" href="{{ url_for('static', filename='css/colapsable.css') }}?v=20260907a">
```

**LOCALIZAR** (`:88`) → **SUSTITUIR** `?v=20260907a` por `?v=20260907b`:

```html
<script src="{{ url_for('static', filename='js/multitab_shell.js') }}?v=20260907a"></script>
```

**Archivo 2:** `c:\APLICACIONES\ProdIA\Repo ProdIA\frontend\MainChat\templates\mainchat_layout.html`

**LOCALIZAR** (`:13`) → **SUSTITUIR** `?v=20260907a` por `?v=20260907b`:

```html
    <link rel="stylesheet" href="{{ url_for('static', filename='css/colapsable.css') }}?v=20260907a">
```

**LOCALIZAR** (`:323`) → **SUSTITUIR** `?v=20260907a` por `?v=20260907b`:

```html
<script defer src="{{ url_for('static', filename='js/multitab_shell.js') }}?v=20260907a"></script>
```

⚠️ **NO tocar** `templates/login.html` (es `prefetch`) ni `Colapsable/templates/colapsable_layout.html` (otro blueprint).

---

## §4 Orden de ejecución

| # | Acción | Archivo | Verificación |
|---|---|---|---|
| 1 | §3.1.a — campos `meses`/`valores`/`meta`/`producto` | `p50_referencia.py` | `meta` se calcula del promedio |
| 2 | §3.1.b — reescribir `formatear_serie_anual` | `p50_referencia.py` | `_kbpe` ya existe: **no añadas imports** |
| 3 | §3.2 — fixture + 2 tests nuevos | `test_p50_referencia.py` | — |
| 4 | §3.3.a — sustituir el pintor por Plotly | `multitab_shell.js` | El SVG viejo queda **borrado**, no comentado |
| 5 | §3.3.b — registrar en `__cnPanelMesCargar` | `multitab_shell.js` | — |
| 6 | §3.3.c — enrutar en `__cnPanelMesPintar` | `multitab_shell.js` | — |
| 7 | §3.4 — retirar CSS del SVG | `colapsable.css` | Las 6 del dibujo fuera; las del contenedor **se quedan** |
| 8 | §3.5 — cache-buster ×2 plantillas | `main.html` + `mainchat_layout.html` | **Los 4 sufijos** a `20260907b` |
| 9 | Validación §6.1 (V1→V8, con V7-bis) | — | Todo en verde |

⚠️ **El orden 4→5→6 no es negociable:** los registros apuntan a `__cnP50AnualInto`, que debe existir primero.

⚠️ **El paso 8 va al final**, nunca antes: subir el sufijo con el JS a medio editar cachearía una versión rota.

---

## §5 Reglas no negociables

1. **CERO modificaciones** fuera de §3. Si ves algo mejorable, anótalo y repórtalo al final.
2. **NO tocar** `serie_anual_p50` más allá del bloque de §3.1.a: la consulta SQL y el `try/except` se quedan como están.
3. **NO tocar** `__cnP50VpHtml` ni el panel `p50_vp`. Debe seguir idéntico.
4. **NO usar `rangemode: "tozero"`** en el eje Y (H3). Aplanaría la curva.
5. **NO usar `__cnProdCol`** para la curva: el P50 no es un producto y devolvería gris (H5). El color va literal, `#0F6B4C`.
6. **NO escribir el envoltorio a mano**: usa `__cnPanelMesHtml`. Sin él, Plotly monta un SVG de 10px sin lanzar error (H4).
7. **NO olvidar los TRES registros** del panel Plotly: constructor (ya existe), `__cnPanelMesCargar` y `__cnPanelMesPintar`.
8. **NO borrar `serie`** del contrato: la usan el texto y los tests existentes.
9. **NO añadir imports.** `_kbpe`, `esc`, `__cnPanelMesHtml`, `__cnMilesEC` y `window.Plotly` ya existen (H11).
10. **JavaScript ES5**: `var` + `function`. Nada de `const`, `let`, arrow functions ni template literals.
11. **NO tocar la BD.** `core.p50_2026` ya está migrada en local y en el 139. No hay migración nueva.
12. **NO olvidar el paso 8** en **las dos** plantillas (H9).
13. **La negrita del texto se escribe con el marcador `⟦…⟧`, NUNCA con markdown de asteriscos dobles** (H10-bis). `multitab_shell.js:7153` lo prohíbe explícitamente: los asteriscos saldrían literales en pantalla.
14. **Borra el bloque CSS `.cn-p50an*` ENTERO** — las 14 reglas, no 6 (H10). Pero **NO toques el bloque `.cn-p50vp*`** que está justo encima: es el panel por vicepresidencia, sigue siendo SVG y sigue vivo.
15. Código y comentarios **en español**.
16. **Si algo no calza con el código real: DETENTE y reporta.**

---

## §6 Validación

### 6.1 Estática — la hace el EXECUTOR

Desde `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend`, **uno por uno**, PowerShell normal (sin administrador).

| # | Comando | Esperado |
|---|---|---|
| V1 | `uv run python -c "import ast; ast.parse(open(r'app/features/consulta_v2/analizar/p50_referencia.py',encoding='utf-8').read()); print('OK')"` | `OK` |
| V2 | `uv run pytest tests/test_p50_referencia.py -q` | Todos pasan (incluidos `p12` y `p13` nuevos) |
| V3 | `uv run pytest -q` | ⚠️ **10 fallos preexistentes y ajenos** (`CLAUDE.md` §6). Cero regresiones nuevas |

**V4 — el contrato Plotly y la meta.** Bloque multilínea: en PowerShell puede quedarse en `>>`; pulsa Enter.

```powershell
$env:PYTHONIOENCODING='utf-8'; uv run python -c "
from app.features.consulta_v2.analizar.p50_referencia import serie_anual_p50, formatear_serie_anual
d = serie_anual_p50()
print('meses  :', d['meses'])
print('valores:', d['valores'])
print('meta   :', d['meta'], '| producto:', d['producto'])
print()
print(formatear_serie_anual(d))
"
```

Esperado: `meses` con las 12 abreviaturas (`Ene`…`Dic`), `meta: 735.3`, `producto: None`, y un texto que mencione la meta, el valle de abril, el pico de julio y cuántos meses van por encima de la meta.

**V5 — el panel se emite de punta a punta.**

```powershell
$env:PYTHONIOENCODING='utf-8'; uv run python -c "
from app.features.consulta_v2 import respuesta_analizar as ra
r = ra.responder_con_panel('como es el comportamiento del P50 para 2026?')
p = r.get('panel') or {}
d = p.get('datos') or {}
print('tipo:', p.get('tipo'), '| meses:', len(d.get('meses') or []), '| meta:', d.get('meta'))
"
```

Esperado: `tipo: p50_anual | meses: 12 | meta: 735.3`.

**V6 — sintaxis del JS** (desde `c:\APLICACIONES\ProdIA\Repo ProdIA\frontend`):

```powershell
node --check static\js\multitab_shell.js
```

Sin salida = correcto. Si `node` no está, reporta **V6 NO EJECUTADO**.

**V7 — 🔑 los TRES registros, el SVG retirado y el CSS limpio** (desde `backend\backend`):

```powershell
uv run python -c "
s = open(r'../../frontend/static/js/multitab_shell.js', encoding='utf-8').read()
c = open(r'../../frontend/static/css/colapsable.css', encoding='utf-8').read()
print('pintor __cnP50AnualInto  :', 'function __cnP50AnualInto' in s)
print('en __cnPanelMesCargar    :', 'cuant_serie_ppto\" || panel.tipo === \"p50_anual\"' in s)
print('en __cnPanelMesPintar    :', 'tipo === \"p50_anual\"' in s)
print('SVG viejo RETIRADO (js)  :', 'cn-p50an__linea' not in s and 'cn-p50an__axtx' not in s)
print('CSS cn-p50an RETIRADO    :', '.cn-p50an' not in c)
print('CSS cn-p50vp INTACTO     :', '.cn-p50vp__linea-p50' in c)
"
```

Las seis en `True`.

⚠️ **`CSS cn-p50an RETIRADO` en `False`** = quedaron reglas huérfanas (H10): las 14 se van, no 6.
⚠️ **`CSS cn-p50vp INTACTO` en `False`** = borraste el bloque del panel por vicepresidencia, que
sigue vivo y es SVG. **DETENTE y revierte.**

**V7-bis — la negrita usa el marcador del chat, no markdown** (desde `backend\backend`):

```powershell
uv run python -c "
s = open(r'app/features/consulta_v2/analizar/p50_referencia.py', encoding='utf-8').read()
i = s.find('def formatear_serie_anual')
cuerpo = s[i:i+4000]
print('usa marcador ⟦⟧ :', '⟦' in cuerpo and '⟧' in cuerpo)
print('SIN markdown ** :', '**' not in cuerpo)
"
```

Las dos en `True`. **`SIN markdown **` en `False`** = los asteriscos saldrán literales en pantalla
(H10-bis). **DETENTE.**

**V8 — 🔑 cache-buster en las DOS plantillas** (desde `backend\backend`):

```powershell
uv run python -c "
import re
tot = 0
for f in ['../../frontend/templates/main.html', '../../frontend/MainChat/templates/mainchat_layout.html']:
    s = open(f, encoding='utf-8').read()
    hits = re.findall(r'(?:multitab_shell\.js|colapsable\.css)\'\) \}\}\?v=([0-9a-z]+)', s)
    print(f.split('/')[-1], '->', hits)
    tot += sum(1 for h in hits if h == '20260907b')
print('SUFIJOS ACTUALIZADOS:', tot, 'de 4')
"
```

Esperado: `SUFIJOS ACTUALIZADOS: 4 de 4`.

⚠️ **Si sale menos de 4, el panel no se vera en el navegador y el fallo sera mudo. DETENTE.**

### 6.2 Humana — la hace el USUARIO

El executor **no puede** validar esto: no tiene navegador, y la app real corre en el **servidor de pruebas**.

| # | Qué mirar | Dónde |
|---|---|---|
| H-1 | El gráfico se ve **como el de «producción diaria vs promedio»**: rejilla, eje con unidad, línea fina con curva suave, tipografía normal | `/mainchat` |
| H-2 | La **línea punteada de meta** en 735,3, rotulada, y la curva cruzándola | El panel |
| H-3 | Los 12 meses en el eje X, legibles | El panel |
| H-4 | El **hover** sobre un punto muestra el mes y el valor en kboepd | El panel |
| H-5 | El texto cuenta el comportamiento: meta, valle de abril, pico de julio, cierre y meses sobre la meta | El chat |
| H-6 | F12 → Console **sin errores** | Navegador |
| H-7 | **No-regresión:** «el P50 de la vicepresidencia GOR» sigue pintando su panel de dos líneas | `/mainchat` |
| H-8 | **Ctrl+F5** la primera vez | Navegador |

⚠️ **Despliegue en Pruebas:** `git pull` en **ambos** repos y reiniciar **los dos** procesos. Python no recarga módulos en caliente: sin reiniciar el 5030, sigue sirviendo el código viejo.

**Estado al terminar el executor: «implementado, PENDIENTE de validación humana».** Nunca «completado» (regla R3, `CLAUDE.md` §10.4).

---

## §7 Fuera de alcance

| Qué | Por qué |
|---|---|
| **Serie del REAL mensual corporativo** | La tabla no lo tiene. Habría que localizar una fuente mensual de real Upstream global — no auditada |
| **Proyección anual (719,4)** | Existe en `Reporte DPP` t4, fila `TOTAL UPSTREAM`, y **ya se ingiere**. Añadirla al panel es un plan aparte (sería una tercera línea) |
| **Que Cuantificar responda el P50** | `ejecutor.py:110-114` rechaza a propósito. Exige medir el golden de 92 casos |
| **P50 por vicepresidencia** | Otra fuente (`NEW MES-AÑO` t8), otra escala (bpd). El panel `p50_vp` ya lo cubre |
| **P50 de años distintos de 2026** | `serie_anual_p50` declina explícitamente: solo existe la tabla de 2026 |
| **Migrar a Azure / desplegar** | Skill `migrar-a-azure`, después de validar en Pruebas |

---

## Prompt para el agente EXECUTOR

```
Eres un agente EXECUTOR. Lee completo el plan
c:\APLICACIONES\ProdIA\Repo ProdIA\backend\Planes\plan_PANEL-P50-ANUAL-V2_20260907.md
y ejecútalo AL PIE DE LA LETRA.
Reglas: CERO modificaciones. Orden secuencial. Si falla, DETENTE. Reporta: ✅/❌ Paso N.
Al final: archivos tocados + "¿Hago commit?"
```
