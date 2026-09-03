# plan_CURVA-ACUMULADA_20260903

**ID_TAREA:** `CURVA-ACUMULADA`
**Fecha:** 2026-09-03
**Rol del lector:** agente EXECUTOR
**Alcance:** 4 archivos de producción en **DOS repos** + 1 archivo de tests.
**Independiente de:** `plan_CURVA-VENTANA_20260903.md`. **No comparten ni un archivo de los que
modifican de forma incompatible**; pueden ejecutarse en cualquier orden (ver H10).

> ## ⚠️ Verificación v2 (2026-09-03, segunda pasada)
>
> El plan v1 se auditó contra el código real. **Es viable y su diseño se confirma**, pero tenía
> un bug visual y una deuda que se saldan aquí. Todo medido leyendo el fuente:
>
> | # | Hallazgo v2 | Efecto en la v1 |
> |---|---|---|
> | 🟢 **H11** | El marcador `__CN_KPI_HTML_FN` **queda RESUELTO**: es `__cnCuantCardHtml` (`:3438`), el **fallback** de la cadena ternaria (`:3989`). Ya distingue N1 de N2 internamente (`:3454-3456`) y pinta «Acumulado ene–jul» + «5 meses cerrados» | Se elimina el marcador y el paso de "localizar". El executor ya no decide nada |
> | 🔴 **H12** | `__cnCuantCardHtml` **YA pinta los avisos** (`:3463-3465`) y `__cnPanelMesHtml` **también** (`:4088-4090`). Concatenarlos como hacía la v1 → **el aviso «⚠️ agosto sigue en curso» sale DOS VECES** | Bug visual introducido por el plan. Se corrige pasando al envoltorio un `d` sin avisos |
> | 🟠 **H13** | Registrar `cuant_acum` en la cadena ternaria es **innecesario**: `__cnCuantCardHtml` es el **fallback** (`: __cnCuantCardHtml(d)`), así que un tipo no listado ya cae ahí. Pero **hay que registrarlo igual**, porque si no el panel se pinta SIN la curva y sin aviso de nada | La v1 acertaba por el motivo equivocado. Se documenta el porqué real |
> | 🟢 **H14** | `__cnProdId` (`:3225`) normaliza con `.toUpperCase()` → acepta `"crudo"` en minúscula sin problema. `__cnHexRgb` valida y tiene fallback | El color por producto es seguro tal como estaba |
> | 🟡 **H15** | `acumulado()` **no emite `anio`**… sí lo emite (`niveles.py:40`). El fallback de la v1 (`res.get("anio") or res["mes"]["anio"]`) era innecesario **y peligroso**: `ejecutar_n2` NO propaga `anio` al contrato, así que `res.get("anio")` es None y `res["mes"]` **no existe en N2** | Se propaga `anio` explícitamente en `ejecutar_n2` (1 línea) en vez del fallback frágil |
>
> **Confirmado midiendo:** H1 (el dato ya se calcula y se tira), H2 (1 call site), H3 (el pintor de
> N3 no sirve), H4 (`__cnFilSeriePlot` es el molde), H5 (panel sin fetch → no toca proxy ni cachés),
> H8 (el texto de la burbuja no se toca).

---

## 0. Contexto para el agente EXECUTOR

### 0.1 Qué se pide

Hoy, «acumulado de Castilla hasta hoy» responde un **gauge** (102,4% REAL/PPTO) con la cifra
acumulada de enero–julio. El usuario pide que además muestre **una curva creciente**: el
acumulado mes a mes, subiendo, contra su presupuesto acumulado.

**El gauge se conserva** (a diferencia del plan CURVA-VENTANA): aquí el porcentaje SÍ es correcto
—acumulado real contra acumulado de presupuesto, ambos de meses cerrados— y quitarlo sería perder
información que hoy funciona. Se **añade** la curva debajo.

### 0.2 Rutas absolutas

| Qué | Ruta |
|---|---|
| Repo BACKEND (git) | `C:\APLICACIONES\ProdIA\Repo ProdIA\backend` |
| Repo FRONTEND (git) | `C:\APLICACIONES\ProdIA\Repo ProdIA\frontend` |
| MODIFICAR 1 | `...\backend\backend\app\features\consulta_v2\cuantificar\niveles.py` |
| MODIFICAR 2 | `...\backend\backend\app\features\consulta_v2\cuantificar\ejecutor.py` |
| MODIFICAR 3 | `...\backend\backend\app\features\consulta_v2\respuesta_cuantificar.py` |
| MODIFICAR 4 | `C:\APLICACIONES\ProdIA\Repo ProdIA\frontend\static\js\multitab_shell.js` |
| CREAR | `...\backend\backend\tests\test_curva_acumulada.py` |

⚠️ Repos **hermanos, no anidados** → **dos commits** (§4.2).

### 0.3 Cómo se corren los comandos

Backend, desde `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend`, PowerShell normal, sin
administrador, **línea por línea**, todo con `uv run`. El frontend no compila: Ctrl+F5 basta.

### 0.4 Convenciones que DEBES respetar

1. **HE4 — el mes EN CURSO no se suma.** Es la regla central de N2 (`niveles.py:5`). El mes en
   curso es proyección y se declara aparte en `en_curso`. **Nada de lo que hagas puede meterlo
   en el acumulado.**
2. **`niveles.py` reusa `analisis.desempeno` con 4 args explícitos** — no factorices, no
   optimices el bucle, no añadas consultas.
3. **Los avisos existentes no se tocan.** El «⚠️ El mes de agosto sigue en curso…» debe seguir
   apareciendo igual.

---

## 1. Hallazgos de la auditoría

Auditoría del 2026-09-03: lectura completa de `niveles.acumulado` (`niveles.py:13-41`),
`ejecutar_n2` (`ejecutor.py:165-209`), `_panel_datos` (`respuesta_cuantificar.py:105-169`),
`formatear_cuerpo` N2 (`validador.py:95-104`), `__cnPanelMesHtml` / `__cnPanelMesPintar` /
`__cnSerieMesInto` / `__cnSerieMesPlot` / `__cnFilSeriePlot` en `multitab_shell.js`, más conteo
de call sites con grep.

### 🟢 H1 — El dato YA se calcula y se tira. Coste marginal: cero consultas nuevas.

`niveles.acumulado` (`niveles.py:24-36`) ya recorre **mes a mes** con una llamada a `desempeno`
por mes, y en cada vuelta tiene `fila["real"]` y `fila["ppto"]`. Los suma y **descarta el
desglose**:

```python
    for m in range(1, ultimo + 1):
        dm = fn(entidad=..., periodo=_MESES[m])
        ...
        if dm["mes"]["completo"]:
            total_real += fila["real"]        # ← el valor mensual está aquí, y se pierde
            total_ppto += (fila["ppto"] or 0)
            meses.append(_MESES[m])
```

La curva acumulada es la **suma corrida de ese mismo bucle**. Acumular en una lista dentro del
bucle no cuesta ni una consulta más. Es el patrón exacto del `comparativo_mes` del 1-sep: el dato
ya viajaba y nadie lo leía.

### 🟢 H2 — `acumulado()` tiene UN solo call site de producción.

Medido: `ejecutor.py:174` (`ejecutar_n2`). En tests, `test_cuantificar.py:13` importa el módulo.
Añadir una clave al dict de retorno es **aditivo y seguro**: ningún consumidor la exige.

### 🔴 H3 — El pintor de N3 NO sirve: pinta UNA serie con una referencia HORIZONTAL.

`__cnSerieMesPlot` (`multitab_shell.js:2273`) recibe `(elp, meses, valores, nums, mesActual, ref,
refTxt, ...)`: **una** serie de valores y **una** `ref` escalar que dibuja como línea horizontal
(`shapes`). El presupuesto acumulado **no es una constante**: es una segunda curva creciente.

**No se puede reusar `__cnSerieMesPlot`.** Forzarlo exigiría cambiar su firma, y la comparten N3
y el panel de análisis → riesgo alto de romper lo que hoy funciona.

### 🟢 H4 — Pero SÍ existe el molde de dos series: `__cnFilSeriePlot`.

`multitab_shell.js:1386-1430` pinta varias curvas mensuales con `traces[]`, `hovermode:"x
unified"`, leyenda horizontal, marcador de mes proyectado y `Plotly.newPlot(elp, traces, layout)`.
**Ese es el patrón a clonar**, no a modificar (es de otro panel: filiales).

### 🟢 H5 — El panel N3/N4 se pinta SIN fetch. Esto abarata el plan enormemente.

`__cnPanelMesCargar` (`multitab_shell.js:4104-4120`) lo dice: *«Gemela de __cnCompProdCargar en el
guardián, pero SIN fetch: los datos ya viajan en panel.datos»*.

**Consecuencia:** este plan **no toca el proxy Flask, ni la caché TTL, ni `__cnDesempCache`** — los
dos bloqueantes (H9/H10) del plan CURVA-VENTANA aquí no existen. El dato viaja en la respuesta del
chat y se pinta directo.

### 🟡 H6 — El envoltorio `__cnPanelMesHtml` es reusable tal cual, con una clase host nueva.

`multitab_shell.js:4086-4100` construye el marco (color de producto + avisos) y recibe `hostCls`.
`__cnCuantSerieHtml` es literalmente `__cnPanelMesHtml(d, "cn-serie-mes")`. El panel nuevo es
`__cnPanelMesHtml(d, "cn-acum-mes")`. **Cero cambios en el envoltorio.**

### 🟡 H7 — El gauge de N2 vive en `cuant_kpi` y NO puede convivir con `cuant_acum` en un mismo tipo.

`_PANEL_TIPO` (`respuesta_cuantificar.py:51-53`) mapea nivel→tipo, uno a uno. N2 hoy cae al
default `cuant_kpi`. Si se cambia N2 a un tipo nuevo, **se pierde el gauge**, que aquí sí es
correcto (§0.1).

**Decisión cerrada:** el tipo nuevo `cuant_acum` **incluye el gauge Y la curva**. Su HTML se
construye concatenando el KPI que ya existe con el host del gráfico. Ver §3.4, donde se identifica
el constructor del KPI a reusar.

### 🟢 H8 — El texto de la burbuja (`validador.formatear_cuerpo`) NO se toca.

`validador.py:95-104` arma la frase de N2 desde `meses_cerrados`/`periodo_label`/`estado`. Nada de
lo que añade este plan entra ahí. **La burbuja del chat queda idéntica** — solo cambia el panel.

### 🟡 H9 — `en_curso` NO entra en la curva acumulada, pero SÍ se puede marcar.

HE4 prohíbe sumarlo. Pero la curva puede **terminar en el último mes cerrado** y el aviso ya
existente explica por qué agosto no está. **Decisión cerrada:** la curva llega hasta el último mes
cerrado, sin punto de proyección. Añadir un punto punteado para agosto obligaría a decidir si es
acumulado-con-proyección (una cifra que HOY NO EXISTE en ningún sitio) — eso es otro plan.

### 🟢 H11 (v2) — El constructor del KPI es `__cnCuantCardHtml`, y ya sabe de N2.

`multitab_shell.js:3438-3483`. Es el **fallback** de la cadena ternaria del dispatcher
(`:3989` → `: __cnCuantCardHtml(d)`), y **ya distingue N1 de N2** (`:3454-3456`):

```javascript
    if (dat.nivel === "N2") {
      realLbl = "Acumulado " + (dat.periodo_label || "");
      corte = (dat.meses_cerrados||0) + " mes..." + " cerrado...";
    } else { ... }
```

Es exactamente el gauge de la captura del usuario. **Se reusa tal cual, sin tocarlo.** El
marcador `__CN_KPI_HTML_FN` de la v1 queda eliminado: el executor ya no tiene que localizar nada.

### 🔴 H12 (v2) — BLOQUEANTE VISUAL: los avisos se pintarían DOS veces.

Medido en las dos funciones que la v1 concatenaba:

| Función | Línea | Qué hace con `d.avisos` |
|---|---|---|
| `__cnCuantCardHtml` | `:3463-3465` | Los pinta como filas `cp-p50__r` dentro del KPI |
| `__cnPanelMesHtml` | `:4088-4090` | Los pinta como `cq-aviso` bajo el gráfico |

La v1 hacía `kpi + ser`, es decir `__cnCuantCardHtml(d) + __cnPanelMesHtml(d, ...)` con **el mismo
`d`** → el aviso «⚠️ El mes de agosto sigue en curso; su proyección NO está incluida en el
acumulado» aparecería **duplicado**, una vez en cada mitad.

**Corrección (§3.4):** el envoltorio del gráfico recibe una copia de `d` **sin** `avisos`. Los
avisos se quedan donde ya estaban: dentro del KPI. Es la posición que el usuario ya conoce (se ve
en su captura, bajo «Corte»).

### 🟠 H13 (v2) — Registrar `cuant_acum` en el dispatcher es obligatorio, pero no por lo que parecía.

`__cnCuantCardHtml` es el **fallback** (`:3989`), así que un `panel.tipo` desconocido **ya cae
ahí** y pintaría el gauge correctamente. Sin registrar `cuant_acum`, el panel **no se rompería**:
simplemente saldría el gauge de siempre, **sin la curva** — un fallo silencioso.

Además, `__cnPanelMesCargar` solo se invoca para los tipos listados en `:4059`. **Ambos registros
son necesarios**; ninguno es opcional.

### 🟡 H15 (v2) — El `anio` no llega al panel. El fallback de la v1 era frágil.

`niveles.acumulado` **sí** devuelve `anio` (`niveles.py:40`), pero `ejecutar_n2` **no lo propaga**
a su contrato (`ejecutor.py:196-209`: no hay clave `anio`). La v1 escribía:

```python
d["anio"] = res.get("anio") or (res.get("mes") or {}).get("anio")
```

Ambos lados son `None` en N2 (`res["mes"]` no existe en el contrato de N2 — HE6 lo prohíbe
expresamente). El título habría salido como `«Crudo · acumulado  vs presupuesto»`, con un hueco.

**Corrección:** `ejecutar_n2` propaga `anio` explícitamente (1 línea, §3.2) y `_panel_datos` lo
lee sin fallback.

### 🟢 H10 — Sin colisión con `plan_CURVA-VENTANA_20260903.md`.

Comparten dos archivos (`ejecutor.py`, `respuesta_cuantificar.py`, `multitab_shell.js`) pero en
**funciones distintas**: aquel toca `ejecutar_n1dser`/rama N1DSER de `_panel_datos`/
`__cnCompProdCargar`; este toca `ejecutar_n2`/rama N2 de `_panel_datos`/`__cnPanelMesPintar`.
**No hay solapamiento de líneas.** Cualquier orden de ejecución vale.

---

## 2. Estado actual

| Pregunta | Nivel | Panel | Qué muestra |
|---|---|---|---|
| «acumulado de Castilla hasta hoy» | N2 | `cuant_kpi` | Gauge 102,4% + cifra + PPTO + «5 meses cerrados» |
| «producción de Castilla mes a mes» | N3 | `cuant_serie` | Curva mensual (no acumulada) + promedio |

**Objetivo:** que N2 pase a `cuant_acum` = **el mismo gauge de hoy** + una curva de dos series
(REAL acumulado y PPTO acumulado), creciente, de enero al último mes cerrado.

---

## 3. Especificación

### 3.1 MODIFICAR `niveles.py` — acumular la serie dentro del bucle que ya existe

Localiza `acumulado()` (`niveles.py:13-41`) y reemplaza el cuerpo **desde `total_real = total_ppto
= 0.0` hasta el `return` final** por:

```python
    total_real = total_ppto = 0.0
    meses, en_curso = [], None
    # [2026-09-03 · CURVA-ACUMULADA] La SUMA CORRIDA, mes a mes. El bucle ya traía el valor
    # mensual de cada mes y solo lo sumaba al total: aquí se conserva además el estado del
    # acumulado en cada paso, que es exactamente la curva creciente que el panel dibuja.
    # 🔑 Coste CERO: ni una consulta más. Es el mismo patrón de `comparativo_mes` (1-sep) —
    #    el dato ya se calculaba y se descartaba.
    # 🔑 HE4: solo entran los meses CERRADOS. El mes en curso queda fuera de la serie igual que
    #    queda fuera del total; meterlo aquí contradiría la regla que gobierna todo N2.
    serie_acum = []
    for m in range(1, ultimo + 1):
        dm = fn(entidad=resuelta["valor"], segmento="ecp", nivel=resuelta.get("nivel"), periodo=_MESES[m])
        if not dm.get("encontrada") or dm.get("sin_datos") or dm.get("sin_cierre"):
            continue
        fila = next((p for p in dm["por_producto"] if p["producto"] == dim_producto), None)
        if not fila or (fila["real"] == 0 and fila["ppto"] == 0):
            continue
        if dm["mes"]["completo"]:
            total_real += fila["real"]
            total_ppto += (fila["ppto"] or 0)
            meses.append(_MESES[m])
            serie_acum.append({
                "mes": _MESES[m][:3].capitalize(),   # "Ene" — mismo formato corto que ritmo_mensual
                "num": m,
                "real_acum": total_real,
                # `ppto_acum` es None si NINGÚN mes trajo presupuesto: dibujar una curva de ceros
                # afirmaría que el PPTO es cero, que es distinto de "no hay PPTO cargado".
                "ppto_acum": (total_ppto if total_ppto else None),
            })
        else:
            en_curso = {"nombre": _MESES[m], "real": fila["real"]}   # proyección; NO se suma (HE4)
    if not meses:
        return {"aplica": False,
                "texto": f"«{resuelta['valor']}» aún no tiene meses cerrados en {anio} para acumular."}
    return {"aplica": True, "real": total_real, "ppto": total_ppto, "meses": meses,
            "en_curso": en_curso, "anio": anio, "serie_acum": serie_acum}
```

⚠️ Lo único que cambia respecto al original: se añade `serie_acum = []`, el `serie_acum.append(...)`
dentro de la rama `completo`, y la clave `"serie_acum"` en el `return`. **El resto es idéntico** —
si te sale distinto, lo has reescrito de más.

### 3.2 MODIFICAR `ejecutor.py` — pasar la serie al contrato de N2

Localiza en `ejecutar_n2` el `return` final (`ejecutor.py:196-209`) y añade **una sola clave**,
inmediatamente después de la línea `"periodo_label": periodo_label, "meses_cerrados": len(ms), "en_curso": ac.get("en_curso"),`:

```python
        "periodo_label": periodo_label, "meses_cerrados": len(ms), "en_curso": ac.get("en_curso"),
        # [2026-09-03 · CURVA-ACUMULADA] La curva creciente del acumulado. Aditiva: quien no la
        # lea (la burbuja de texto, validador.formatear_cuerpo) sigue funcionando igual.
        # 🔑 `anio` se propaga EXPLÍCITAMENTE (v2/H15). `niveles.acumulado` lo devuelve desde
        #    siempre pero este contrato no lo llevaba, y N2 NO tiene la clave `mes` (HE6 lo
        #    prohíbe: nada de meses sintéticos), así que el panel no tenía de dónde sacar el año
        #    para el título del gráfico y salía un hueco.
        "anio": ac.get("anio"),
        "serie_acum": ac.get("serie_acum") or [],
```

⚠️ **No toques** `resultado`, `referencia_valor`, `cumplimiento_pct` ni `estado`: son los que
alimentan el gauge, que se conserva (H7).

### 3.3 MODIFICAR `respuesta_cuantificar.py` — tipo de panel nuevo + datos

**Edición A.** Localiza `_PANEL_TIPO` (`respuesta_cuantificar.py:51-53`):

```python
_PANEL_TIPO = {"N3": "cuant_serie", "N4": "cuant_var",
              "N1D": "cuant_dia_panel", "N1DSEL": "cuant_dia_panel",
              "N1DSER": "cuant_dia_panel"}   # N1/N2 -> "cuant_kpi" (Fase 3)
```

Reemplázalo por:

```python
# [2026-09-03 · CURVA-ACUMULADA] N2 pasa de `cuant_kpi` a `cuant_acum`: el MISMO gauge de
# siempre MÁS la curva creciente del acumulado. No es un panel distinto, es el de siempre con
# el gráfico que le faltaba — por eso `cuant_acum` construye el KPI y le añade el host.
# N1 sigue en `cuant_kpi` (su curva diaria la pinta otro camino).
_PANEL_TIPO = {"N3": "cuant_serie", "N4": "cuant_var",
              "N1D": "cuant_dia_panel", "N1DSEL": "cuant_dia_panel",
              "N1DSER": "cuant_dia_panel",
              "N2": "cuant_acum"}            # N1 -> "cuant_kpi" (Fase 3)
```

**Edición B.** Localiza en `_panel_datos` la rama N1/N2 (`respuesta_cuantificar.py:161-169`):

```python
        if nivel == "N2":
            d["periodo_label"] = res["periodo_label"]
            d["meses_cerrados"] = res["meses_cerrados"]
```

Reemplázala por:

```python
        if nivel == "N2":
            d["periodo_label"] = res["periodo_label"]
            d["meses_cerrados"] = res["meses_cerrados"]
            # [2026-09-03 · CURVA-ACUMULADA] La curva viaja EN EL PAYLOAD del chat: el panel
            # `cuant_acum` se pinta SIN fetch (multitab_shell.js:4105), igual que N3/N4. Por eso
            # este plan no toca el proxy Flask ni sus dos capas de caché.
            d["serie_acum"] = res.get("serie_acum") or []
            # [v2/H15] Sin fallback: `ejecutar_n2` ya lo propaga (§3.2). El fallback de la v1
            # (`res["mes"]["anio"]`) era humo — N2 no tiene clave `mes` por diseño (HE6).
            d["anio"] = res.get("anio")
```

### 3.4 MODIFICAR `multitab_shell.js` — el panel `cuant_acum`

> **v2:** el marcador `__CN_KPI_HTML_FN` de la v1 **queda eliminado**. La auditoría v2 identificó
> la función: es **`__cnCuantCardHtml`** (`multitab_shell.js:3438`), el fallback del dispatcher,
> que ya distingue N1 de N2 (H11). El executor no tiene que localizar ni decidir nada.

**Edición A.** En la cadena ternaria del dispatcher, localiza (`multitab_shell.js:3959-3961`):

```javascript
    var body = (panel.tipo === "cuant_serie")    ? __cnCuantSerieHtml(d)
             : (panel.tipo === "cuant_var")      ? __cnCuantVarHtml(d)
```

Reemplázalo por:

```javascript
    var body = (panel.tipo === "cuant_serie")    ? __cnCuantSerieHtml(d)
             : (panel.tipo === "cuant_var")      ? __cnCuantVarHtml(d)
             // [2026-09-03 · CURVA-ACUMULADA] N2 = el KPI de siempre + la curva del acumulado.
             // 🔑 Sin este ramal NO se rompe nada: `cuant_acum` caería al fallback
             //    `__cnCuantCardHtml` (:3989) y pintaría el gauge correcto... SIN la curva. Un
             //    fallo silencioso, que es peor que uno ruidoso (v2/H13).
             : (panel.tipo === "cuant_acum")     ? __cnCuantAcumHtml(d)
```

(el resto de la cadena, tal cual estaba).

**Edición C.** Localiza (`multitab_shell.js:4059`):

```javascript
    if (panel.tipo === "cuant_serie" || panel.tipo === "cuant_var") __cnPanelMesCargar(blk, d, panel.tipo);
```

Reemplázala por:

```javascript
    if (panel.tipo === "cuant_serie" || panel.tipo === "cuant_var" || panel.tipo === "cuant_acum") __cnPanelMesCargar(blk, d, panel.tipo);
```

**Edición D.** En `__cnPanelMesPintar` (`multitab_shell.js:4122-4135`), añade la rama del nuevo
tipo **antes** del cierre de la función:

```javascript
    } else if (tipo === "cuant_acum") {
      var ha = blk.querySelector(".cn-acum-mes");
      if (ha) __cnAcumMesInto(ha, d);
    }
```

**Edición E.** Añade las dos funciones nuevas **inmediatamente después** de
`function __cnCuantSerieHtml(d) { ... }` (`multitab_shell.js:4102`):

```javascript
  // [2026-09-03 · CURVA-ACUMULADA] N2 = el KPI de siempre + la curva creciente del acumulado.
  // 🔑 El gauge NO se sustituye: en N2 el porcentaje es correcto (acumulado real vs acumulado
  //    de presupuesto, ambos de meses CERRADOS) y quitarlo perdería información que ya sirve.
  //    Se CONCATENA el markup de __cnCuantCardHtml (:3438) con el envoltorio mensual (:4086),
  //    que ya sabe montar un host para Plotly.
  // 🔑 v2/H12 — LOS AVISOS VAN SOLO EN EL KPI. __cnCuantCardHtml los pinta (:3463) y
  //    __cnPanelMesHtml TAMBIÉN (:4088). Pasarle el mismo `d` a las dos duplicaría el aviso
  //    «⚠️ El mes de agosto sigue en curso…» en la misma tarjeta. Al envoltorio se le pasa una
  //    copia SIN `avisos`; se quedan donde el usuario ya los conoce, bajo "Corte".
  // 🔑 Sin `serie_acum` (p.ej. un solo mes cerrado) cae al KPI solo: nunca un hueco.
  function __cnCuantAcumHtml(d) {
    var kpi = __cnCuantCardHtml(d);
    if (!d.serie_acum || !d.serie_acum.length) return kpi;
    var dSinAvisos = {};
    for (var k in d) { if (Object.prototype.hasOwnProperty.call(d, k)) dSinAvisos[k] = d[k]; }
    dSinAvisos.avisos = [];
    return kpi + __cnPanelMesHtml(dSinAvisos, "cn-acum-mes");
  }

  // Curva ACUMULADA: dos series crecientes (REAL y PPTO). Molde = __cnFilSeriePlot (:1386),
  // que es el único pintor mensual de VARIAS trazas; __cnSerieMesPlot (:2273) no vale porque
  // su referencia es un ESCALAR dibujado como línea horizontal, y aquí el presupuesto acumulado
  // es otra curva que sube.
  function __cnAcumMesInto(hostEl, d) {
    var serie = d.serie_acum || [];
    var prod = String(d.producto || "");
    var nombre = prod.charAt(0).toUpperCase() + prod.slice(1).toLowerCase();
    var unidad = d.unidad || "bbl";
    var hd = esc(nombre) + ' · acumulado ' + (d.anio || "") + ' vs presupuesto';
    hostEl.innerHTML =
      '<div class="cn-ins__card"><div class="cn-ins__card-hd"><i class="bi bi-graph-up-arrow"></i> ' + hd + '</div>' +
      '<div class="cn-ins__plot" data-p></div>' +
      '<div class="cn-ins__cap" data-cap></div></div>';
    var elp = hostEl.querySelector("[data-p]");
    if (!serie.length) {
      elp.innerHTML = '<div class="p-2 text-muted small">Sin acumulado mensual para este producto.</div>';
      return;
    }
    if (!window.Plotly) { elp.innerHTML = '<div class="text-muted small p-2">(Plotly no disponible)</div>'; return; }
    // El gas se grafica en MSCF (÷1e6) y el hover formatea el valor ORIGINAL con __cnGasM (que
    // ya divide) — nunca el ya escalado: ese doble escalado es el bug documentado en :3650-3652.
    var esGas = String(prod).toUpperCase() === "GAS";
    var fmtD = esGas ? __cnGasM : function (v) { return __cnMilesEC(Math.round(v)); };
    var esc1 = function (v) { return (v == null) ? null : (esGas ? v / 1e6 : v); };
    var meses = serie.map(function (p) { return p.mes; });
    var col = __cnProdCol(prod);
    var traces = [{
      x: meses, y: serie.map(function (p) { return esc1(p.real_acum); }),
      name: "Real acumulado", type: "scatter", mode: "lines+markers",
      line: { color: col, width: 2.5, shape: "spline", smoothing: 0.8 },
      marker: { color: col, size: 7 },
      customdata: serie.map(function (p) { return fmtD(p.real_acum); }),
      hovertemplate: "%{x}<br>Real acum.: %{customdata}" + (unidad ? " " + unidad : "") + "<extra></extra>"
    }];
    // La curva de PPTO solo se dibuja si HAY presupuesto. `ppto_acum: null` significa "no hay
    // PPTO cargado", que es distinto de "el PPTO es cero" — pintar ceros afirmaría lo segundo.
    if (serie.some(function (p) { return p.ppto_acum != null; })) {
      traces.push({
        x: meses, y: serie.map(function (p) { return esc1(p.ppto_acum); }),
        name: "Presupuesto acumulado", type: "scatter", mode: "lines",
        line: { color: "#8a978f", width: 2, dash: "dot" }, connectgaps: false,
        customdata: serie.map(function (p) { return p.ppto_acum == null ? "—" : fmtD(p.ppto_acum); }),
        hovertemplate: "%{x}<br>PPTO acum.: %{customdata}" + (unidad ? " " + unidad : "") + "<extra></extra>"
      });
    }
    window.Plotly.newPlot(elp, traces, {
      margin: { l: 62, r: 18, t: 22, b: 30 }, height: 260, hovermode: "x unified",
      showlegend: true, legend: { orientation: "h", y: -0.18, x: 0, font: { size: 11 } },
      xaxis: { title: { text: "Mes", font: { size: 11 } }, tickfont: { size: 11 }, showgrid: false },
      yaxis: {
        title: { text: "Acumulado (" + (esGas ? "MSCF" : unidad) + ")", font: { size: 11 } },
        tickfont: { size: 10 }, rangemode: "tozero", separatethousands: true,
        gridcolor: "#eef1ef", zeroline: false
      },
      plot_bgcolor: "#fff", paper_bgcolor: "#fff"
    }, { displayModeBar: false, responsive: true });
    var cap = hostEl.querySelector("[data-cap]");
    if (cap) {
      var ult = serie[serie.length - 1];
      cap.innerHTML = 'Suma corrida de los <b>' + serie.length + '</b> meses cerrados de ' +
        esc(String(d.anio || "")) + '. El mes en curso no entra en el acumulado.';
    }
  }
```

🔴 **`__CN_KPI_HTML_FN` es un MARCADOR, no código.** Sustitúyelo por el nombre real de la función
que construye el KPI, hallado en la Edición A. Si lo dejas tal cual, el panel revienta.

> **v2 — corrección de un vacío de la v1:** esta advertencia sobre `__CN_KPI_HTML_FN` es un
> residuo de la v1 y **ya no aplica** (H11: el marcador se resolvió, `__cnCuantAcumHtml` en §3.4
> Edición E ya usa `__cnCuantCardHtml` directamente). Se deja tachada aquí, no borrada, para que
> quede constancia de qué decía la v1.

### 3.5 CREAR `tests/test_curva_acumulada.py`

> **v2 — sección completada.** Faltaba en la v1: el documento saltaba de §3.4 a §4 sin fijar el
> contenido de este archivo, y un EXECUTOR que lo detectó (regla NN-8/"decisiones cerradas del
> Planner") se detuvo en vez de improvisarlo. Correcto — y esto lo salda.

Crea el archivo completo con este contenido exacto:

```python
"""test_curva_acumulada.py — la curva creciente del acumulado N2 (plan CURVA-ACUMULADA, 2026-09-03).

Sin BD: `niveles.acumulado` se prueba con un `_desempeno_fn` FAKE, igual que
`test_cuantificar.py` hace para N2 hoy. Lo que se mide es el CABLEADO (HE4, la suma corrida,
el contrato hacia el panel), no el dato real.
"""
import pytest

from app.features.consulta_v2.cuantificar import niveles as _niveles
from app.features.consulta_v2.cuantificar import ejecutor as _ejecutor
from app.features.consulta_v2.respuesta_cuantificar import _panel_datos, _PANEL_TIPO

_ENT = {"valor": "CASTILLA", "nivel": "campo", "rama": "A", "zoom": []}

# 4 meses cerrados (ene-abr) con REAL/PPTO crecientes + mayo EN CURSO (no debe sumarse, HE4).
_MESES_FAKE = {
    1: {"real": 1000.0, "ppto": 1200.0}, 2: {"real": 1100.0, "ppto": 1200.0},
    3: {"real": 900.0,  "ppto": 1200.0}, 4: {"real": 1200.0, "ppto": 1200.0},
}


def _fake_desempeno(entidad="X", segmento="ecp", nivel=None, periodo=None):
    if periodo is None:                         # d0: consulta "sin periodo" -> último mes/año
        return {"encontrada": True, "sin_datos": False, "sin_cierre": False,
                "mes": {"anio": 2026, "mes": 5, "nombre": "Mayo", "completo": False}}
    _MESES_NUM = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5}
    m = _MESES_NUM[periodo]
    if m == 5:                                   # mayo: EN CURSO, no cerrado
        return {"encontrada": True, "sin_datos": False, "sin_cierre": False,
                "mes": {"anio": 2026, "mes": 5, "nombre": "Mayo", "completo": False},
                "por_producto": [{"producto": "CRUDO", "real": 400.0, "ppto": 1200.0}]}
    fila = _MESES_FAKE[m]
    return {"encontrada": True, "sin_datos": False, "sin_cierre": False,
            "mes": {"anio": 2026, "mes": m, "nombre": "X", "completo": True},
            "por_producto": [{"producto": "CRUDO", "real": fila["real"], "ppto": fila["ppto"]}]}


def _fake_desempeno_sin_ppto(entidad="X", segmento="ecp", nivel=None, periodo=None):
    """Ningún mes trae presupuesto: ppto_acum debe quedar en None, no en 0 (H1 del ejecutor)."""
    if periodo is None:
        return {"encontrada": True, "sin_datos": False, "sin_cierre": False,
                "mes": {"anio": 2026, "mes": 3, "nombre": "Marzo", "completo": False}}
    _MESES_NUM = {"enero": 1, "febrero": 2, "marzo": 3}
    m = _MESES_NUM[periodo]
    if m == 3:
        return {"encontrada": True, "sin_datos": False, "sin_cierre": False,
                "mes": {"anio": 2026, "mes": 3, "nombre": "Marzo", "completo": False},
                "por_producto": [{"producto": "CRUDO", "real": 300.0, "ppto": 0.0}]}
    return {"encontrada": True, "sin_datos": False, "sin_cierre": False,
            "mes": {"anio": 2026, "mes": m, "nombre": "X", "completo": True},
            "por_producto": [{"producto": "CRUDO", "real": 500.0, "ppto": 0.0}]}


# ---------------- niveles.acumulado: la suma corrida ----------------

def test_serie_acum_crece_mes_a_mes():
    r = _niveles.acumulado(_ENT, "CRUDO", _desempeno_fn=_fake_desempeno)
    assert r["aplica"] is True
    vals = [p["real_acum"] for p in r["serie_acum"]]
    assert vals == sorted(vals)                  # nunca baja: es una suma acumulada


def test_serie_acum_valores_exactos():
    r = _niveles.acumulado(_ENT, "CRUDO", _desempeno_fn=_fake_desempeno)
    vals = [p["real_acum"] for p in r["serie_acum"]]
    assert vals == [1000.0, 2100.0, 3000.0, 4200.0]
    ppto = [p["ppto_acum"] for p in r["serie_acum"]]
    assert ppto == [1200.0, 2400.0, 3600.0, 4800.0]


def test_serie_acum_excluye_el_mes_en_curso():
    """🔑 REGRESIÓN CENTRAL — HE4. Mayo está en curso (completo=False): NO debe aparecer en la
    serie ni mover el último valor de real_acum."""
    r = _niveles.acumulado(_ENT, "CRUDO", _desempeno_fn=_fake_desempeno)
    assert len(r["serie_acum"]) == 4              # solo ene-abr
    assert all(p["num"] != 5 for p in r["serie_acum"])
    assert r["serie_acum"][-1]["real_acum"] == r["real"]   # coincide con el total del gauge
    assert r["en_curso"] == {"nombre": "mayo", "real": 400.0}


def test_serie_acum_meses_cortos_y_numeros():
    r = _niveles.acumulado(_ENT, "CRUDO", _desempeno_fn=_fake_desempeno)
    assert [p["mes"] for p in r["serie_acum"]] == ["Ene", "Feb", "Mar", "Abr"]
    assert [p["num"] for p in r["serie_acum"]] == [1, 2, 3, 4]


def test_ppto_acum_none_sin_presupuesto():
    """Si NINGÚN mes trae PPTO, ppto_acum es None (no 0): pintar ceros afirmaría PPTO=0."""
    r = _niveles.acumulado(_ENT, "CRUDO", _desempeno_fn=_fake_desempeno_sin_ppto)
    assert all(p["ppto_acum"] is None for p in r["serie_acum"])


def test_acumulado_sigue_devolviendo_el_contrato_de_siempre():
    """No regresión: real/ppto/meses/en_curso/anio del contrato ORIGINAL siguen ahí."""
    r = _niveles.acumulado(_ENT, "CRUDO", _desempeno_fn=_fake_desempeno)
    assert r["real"] == 4200.0 and r["ppto"] == 4800.0
    assert r["meses"] == ["enero", "febrero", "marzo", "abril"]
    assert r["anio"] == 2026


# ---------------- ejecutor.ejecutar_n2: el contrato hacia el panel ----------------

def test_ejecutar_n2_propaga_serie_acum():
    res = _ejecutor.ejecutar_n2(_ENT, {"producto": "crudo", "unidad": "bbl"},
                                _desempeno_fn=_fake_desempeno)
    assert res["aplica"] is True
    assert len(res["serie_acum"]) == 4
    assert res["serie_acum"][-1]["real_acum"] == res["resultado"]["valor"]


def test_ejecutar_n2_propaga_anio():
    """🔑 H15 — N2 no tiene clave `mes`; `anio` debe salir EXPLÍCITO en el contrato."""
    res = _ejecutor.ejecutar_n2(_ENT, {"producto": "crudo", "unidad": "bbl"},
                                _desempeno_fn=_fake_desempeno)
    assert res["anio"] == 2026
    assert "mes" not in res


def test_ejecutar_n2_gauge_no_cambia():
    """No regresión: el gauge (resultado/referencia_valor/cumplimiento_pct/estado) es el de
    siempre — este plan es aditivo sobre N2, no lo reemplaza."""
    res = _ejecutor.ejecutar_n2(_ENT, {"producto": "crudo", "unidad": "bbl"},
                                _desempeno_fn=_fake_desempeno)
    assert res["resultado"]["valor"] == 4200.0
    assert res["referencia_valor"] == 4800.0
    assert res["cumplimiento_pct"] == round(4200.0 / 4800.0 * 100.0, 1)


# ---------------- respuesta_cuantificar: tipo de panel + datos ----------------

def test_tipo_panel_n2_es_cuant_acum():
    assert _PANEL_TIPO.get("N2") == "cuant_acum"


def test_tipo_panel_n1_sigue_siendo_kpi_por_defecto():
    """N1 NO está en _PANEL_TIPO: cae al default 'cuant_kpi' de _panel_datos.get(...). No
    regresión — este plan solo añade la clave N2."""
    assert "N1" not in _PANEL_TIPO


def test_panel_datos_n2_lleva_serie_acum_y_anio():
    res = _ejecutor.ejecutar_n2(_ENT, {"producto": "crudo", "unidad": "bbl"},
                                _desempeno_fn=_fake_desempeno)
    d = _panel_datos(res)
    assert d["serie_acum"] == res["serie_acum"]
    assert d["anio"] == 2026


def test_panel_datos_n2_sin_serie_da_lista_vacia_no_error():
    """Un N2 con un solo mes (o sin `serie_acum` en el contrato) no debe romper _panel_datos."""
    res = _ejecutor.ejecutar_n2(_ENT, {"producto": "crudo", "unidad": "bbl"},
                                _desempeno_fn=_fake_desempeno)
    del res["serie_acum"]
    d = _panel_datos(res)
    assert d["serie_acum"] == []
```

---

## 4. Orden de ejecución

| # | Acción | Archivo | Ref |
|---|---|---|---|
| 0 | **Línea base** (§6.1 comandos 2 y 3) ANTES de editar | — | §6.1 |
| 1 | `serie_acum` en el bucle | `cuantificar/niveles.py` | §3.1 |
| 2 | La serie entra al contrato N2 | `cuantificar/ejecutor.py` | §3.2 |
| 3 | Tipo `cuant_acum` + datos del panel (2 ediciones) | `respuesta_cuantificar.py` | §3.3 |
| 4 | Panel `cuant_acum` (4 ediciones + 2 funciones) | `multitab_shell.js` | §3.4 A-E |
| 5 | Crear los tests | `tests/test_curva_acumulada.py` | §3.5 |
| 6 | Validación estática | — | §6.1 |

> **v2:** el antiguo paso 4 («localizar el constructor del KPI») **desaparece**. La auditoría v2
> lo resolvió: es `__cnCuantCardHtml` (H11). Un paso menos y una decisión menos para el executor.

### 4.2 Los commits son DOS

Pasos 1-3 y 5 → repo `backend`. Paso 4 → repo `frontend`. **No los mezcles.** Pregunta al
usuario antes de commitear.

⚠️ **Despliegue conjunto.** Backend solo: el payload lleva `serie_acum` y el JS lo ignora →
comportamiento de hoy (inocuo). Frontend solo: el JS espera `cuant_acum` pero el backend manda
`cuant_kpi` → comportamiento de hoy (inocuo). **Ninguna mitad rompe nada**, pero la feature
requiere las dos.

---

## 5. Reglas no negociables

- **NN-1 (HE4).** El mes EN CURSO **no** entra en `serie_acum`. Es la regla que gobierna todo N2.
- **NN-2.** No toques `validador.formatear_cuerpo`: la burbuja del chat queda idéntica (H8).
- **NN-3.** No quites el gauge de N2 (H7). El porcentaje aquí es correcto.
- **NN-4.** No modifiques `__cnSerieMesPlot` ni `__cnFilSeriePlot`: son de N3 y del panel de
  filiales. `__cnFilSeriePlot` se **clona como molde**, no se reusa (H3, H4).
- **NN-5.** No añadas consultas a BD. La serie sale del bucle que ya existe (H1).
- **NN-6 (v2/H12).** Los avisos van **solo en el KPI**. Al envoltorio del gráfico se le pasa una
  copia de `d` con `avisos: []`. Pasarle el mismo `d` a las dos mitades **duplica el aviso en
  pantalla** — es el bug que la v1 introducía.
- **NN-7.** No modifiques `__cnCuantCardHtml` (`:3438`): lo usan N1, N2 y **todo tipo de panel no
  registrado** (es el fallback del dispatcher). Se **reusa**, no se toca.
- **NN-8.** Si una línea del plan no calza con el código real, **DETENTE**. No improvises.

---

## 6. Validación

### 6.1 Estática — la ejecuta el EXECUTOR

Desde `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend`, línea por línea:

```powershell
uv run pytest tests/test_curva_acumulada.py -q
```
→ Esperado: **todos PASAN** (~12 casos).

```powershell
uv run pytest tests/test_cuantificar.py tests/test_cuantificar_dia.py tests/test_cuantificar_ranking.py tests/test_analizar.py tests/test_slots_ventana.py -q
```
→ Esperado: **el mismo resultado que la línea base del paso 0** (era `3 failed, 289 passed,
1 skipped` + 42 de `test_slots_ventana.py`; los 3 fallos son de BD real, ajenos). Cualquier fallo
nuevo: **DETENTE**.

```powershell
uv run python -m app.features.consulta_v2.golden.run_golden_cuantificar
```
→ Esperado: **el mismo porcentaje que en el paso 0**. Este plan no toca el clasificador ni los
niveles: el golden **no debería moverse ni un punto**.

Desde `C:\APLICACIONES\ProdIA\Repo ProdIA\frontend`:

```powershell
node --check static/js/multitab_shell.js
```
→ Esperado: sin salida. Un error de sintaxis aquí **deja el chat entero muerto**, no solo este
panel. Si `node` no está, ábrelo en el navegador y mira F12 → Console.

```powershell
python -c "src=open('static/js/multitab_shell.js',encoding='utf-8').read(); print('OK' if 'dSinAvisos.avisos = []' in src and '__CN_KPI_HTML_FN' not in src else 'REVISAR: falta la guarda de avisos (NN-6) o quedo un marcador')"
```
→ Esperado: `OK`. Comprueba que aplicaste la guarda de avisos duplicados (H12/NN-6) y que no
quedó ningún marcador de la v1.

```powershell
python -c "src=open('static/js/multitab_shell.js',encoding='utf-8').read(); print('OK' if src.count('cuant_acum') >= 3 else 'REVISAR: cuant_acum debe aparecer en el dispatcher, en :4059 y en __cnPanelMesPintar')"
```
→ Esperado: `OK`. Los **tres** registros son obligatorios (H13): sin el de `:4059` el panel se
pinta sin curva y **sin ningún error visible**.

### 6.2 Humana — la ejecuta el USUARIO, en Pruebas

Tras `git pull` en ambos repos, reiniciar Flask e INGESTA, y **Ctrl+F5**:

| # | Qué probar | Esperado |
|---|---|---|
| 1 | «Acumulado de Castilla hasta hoy» | **El gauge de siempre** (102,4%, cifra, PPTO, «5 meses cerrados») **MÁS** una curva creciente debajo |
| 2 | La curva del punto 1 | Sube de enero a julio, **nunca baja**. Dos líneas: Real (color del producto) y Presupuesto (gris punteada) |
| 3 | El último punto de la curva | Coincide con la cifra del gauge (33.214.148 bbl) |
| 4 | El aviso | Sigue diciendo «⚠️ El mes de agosto sigue en curso…» y **agosto NO aparece en la curva** |
| 4-bis | 🔴 **Contar los avisos (H12).** Mirar cuántas veces sale ese ⚠️ en la tarjeta | **UNA sola vez**, bajo «Corte». Si sale dos (una en el KPI y otra bajo el gráfico), falta la guarda de NN-6 |
| 4-ter | El título del gráfico (H15) | «Crudo · acumulado **2026** vs presupuesto» — con el año, **sin hueco** |
| 5 | La burbuja del chat (texto) | **Idéntica a antes** (H8) |
| 6 | «Acumulado de gas de Cusiana» | Curva en **MSCF**, valores coherentes con el gauge |
| 7 | «Producción de Castilla mes a mes» (N3) | **Sin cambios**: curva mensual NO acumulada |
| 8 | «¿Cuánto produjo Castilla en abril?» (N1) | **Sin cambios**: gauge de siempre |
| 9 | F12 → Console en todas las anteriores | **0 errores** |
| 10 | Preguntar 1, cambiar de pestaña y volver | La curva se repinta (guardián `pendPaint`, H5) |

⚠️ **R3 (CLAUDE.md §10.4):** el executor **no** marca esto. Su estado tras §6.1 es
**«implementado, PENDIENTE de validación humana»**.

---

## 7. Fuera de alcance

- **Acumulado DIARIO dentro del mes en curso** («acumulado de agosto día a día»). Sale de
  `fact_produccion_dia_ecp`, no reconcilia con el mensual en BLANCOS
  (`HALLAZGO_concepto_multiplicidad.md`) y es un grano distinto. Plan aparte.
- **Punto de proyección** del mes en curso sobre la curva acumulada (H9): exigiría definir
  «acumulado proyectado», cifra que hoy no existe en ningún sitio.
- Acumulados **multi-año** o de rangos arbitrarios de meses. `acumulado()` es del año en curso.
- El gauge y la burbuja de texto (NN-2, NN-3).
- N1, N3, N4, N1D, N1DSEL, N1DSER y el ranking: no se tocan.
- El proxy Flask y sus cachés: **este plan no los necesita** (H5).

---

## 8. Prompt para el agente EXECUTOR

```
Eres un agente EXECUTOR. Lee completo el plan
C:\APLICACIONES\ProdIA\Repo ProdIA\backend\Planes\plan_CURVA-ACUMULADA_20260903.md
y ejecútalo AL PIE DE LA LETRA.

Reglas: CERO modificaciones al plan. Orden secuencial (§4). Si un paso falla, DETENTE y
reporta. NN-7: si una línea del plan no calza con el código real, DETENTE, no improvises.

Paso 0 OBLIGATORIO: línea base de §6.1 ANTES de editar nada.

🔴 NN-6 (H12): los avisos van SOLO en el KPI. __cnCuantCardHtml (:3463) y __cnPanelMesHtml
(:4088) pintan AMBOS `d.avisos`; pasarles el mismo objeto duplica en pantalla el aviso
«El mes de agosto sigue en curso». Al envoltorio del gráfico se le pasa una copia con
avisos: []. Hay un comando en §6.1 que lo verifica.

🔴 H13: `cuant_acum` debe quedar registrado en TRES sitios (dispatcher :3959, la línea :4059
y __cnPanelMesPintar). Si falta el de :4059, el panel sale con el gauge y SIN la curva, sin
ningún error en consola — un fallo silencioso. Hay un comando en §6.1 que los cuenta.

🔴 NN-1 (HE4): el mes EN CURSO no entra en la curva acumulada. Es la regla que gobierna N2.
🔴 NN-3: el gauge de N2 se CONSERVA. Aquí el porcentaje sí es correcto; el panel nuevo es el
gauge de siempre MÁS la curva.
🔴 NN-5: cero consultas nuevas a BD. La serie sale del bucle que ya existe en niveles.py.
🔴 NN-7: no modifiques __cnCuantCardHtml. Es el fallback del dispatcher y lo usa TODO panel
no registrado; se reusa tal cual.

Ojo: son DOS repos (backend y frontend) → DOS commits (§4.2). No los mezcles.
Este plan NO debe mover el golden ni un punto: no toca clasificador ni niveles.

Al terminar §6.1 tu estado es "implementado, PENDIENTE de validación humana" (R3,
CLAUDE.md §10.4) — NO marques la feature como verificada: no tienes navegador.

Reporta: ✅/❌ Paso N con la salida de los comandos.
Al final: archivos tocados por repo + baseline vs final + "¿Hago commit?"
```
