# plan_COMPARACION-PERIODOS_20260903 (v2 — auditado y verificado contra el código)

> Punto **3 de 4** de «inteligencia de tiempo». Cubre los tipos **2 (periodo vs periodo: MoM /
> YoY)** y **3 (real vs programa a lo largo del tiempo)**.
> Punto 1 cerrado (commits `5f4aae5`, `d95e566`). Punto 2 planificado en
> `plan_TENDENCIA_20260903.md`, pendiente de ejecución — **este plan es independiente de él**
> (§1 · P10).
>
> **v2**: el v1 se verificó línea a línea contra el código. Encontró **3 fallos que lo habrían
> roto en ejecución** (una ruta de archivo inexistente, un import equivocado en los tests y un
> `cerrado` que miente en el YoY) y 2 oportunidades de simplificación. Ver §1C.

---

## 0. Contexto para el agente EXECUTOR

Eres un agente EXECUTOR. No tienes la conversación previa ni el historial de git. Todo está aquí.

**Proyecto:** ProdIA — asistente de producción de Ecopetrol. Dos repos hermanos:

| Repo | Ruta absoluta | Stack |
|---|---|---|
| ProdIABack | `C:\APLICACIONES\ProdIA\Repo ProdIA\backend` | FastAPI + `uv`, puerto 5030 |
| ProdIAWebFront | `C:\APLICACIONES\ProdIA\Repo ProdIA\frontend` | Flask + Jinja2, puerto 5029 |

**Son dos commits separados.** Nunca uno solo para los dos.

**Motor Q v2 · Cuantificar** despacha por `slots["nivel_temporal"]` en
`cuantificar/ejecutor.py:65`. Niveles existentes: `N1` (mes puntual), `N1D` (día concreto),
`N1DSEL` (mejor/peor día), `N1DSER` (curva diaria), `N2` (acumulado), `N3` (serie mensual),
`N4` (variación mes a mes). Este plan añade **dos**: `NCMP` y `N3P`.

**Convenciones que se respetan sin excepción:**

- **HE4** — el mes EN CURSO es proyección. Nunca se compara en silencio contra un mes cerrado:
  si uno de los dos periodos está en curso, se **declara**.
- **HE6** — cada nivel trae SUS campos. No se fabrican claves sintéticas (`mes` en N2, etc.).
- **AF-3.7** — match de palabras sueltas por TOKEN (`\b`), nunca substring. «MAYO» ⊂ «MAYOR»
  produjo dos bugs históricos.
- **Módulos puros** — `slots.py` NO importa BD, NO llama `date.today()`. El techo entra por
  parámetro.
- **`norm()`** (`consulta_v2/normaliza.py`) hace UPPER + trim + colapsa espacios + pliega acentos
  y la ñ. Todos los patrones se escriben **en mayúscula y sin tildes**.
- **Español** en todo texto que vea el usuario.
- Comandos: PowerShell, desde la carpeta indicada, línea por línea salvo aviso.

**Prohibido decidir.** Si algo no está en este plan, DETENTE y reporta.

---

## 1. Hallazgos de la auditoría

Determinan la §3. No son decorativos.

### 🔴 P1 — `_periodo_texto` devuelve UN solo mes. «mayo vs julio» responde mayo, callando

`cuantificar/slots.py:432-448`:

```python
mo = next((m for m in _MESES if re.search(r"\b" + m + r"\b", t)), None)
```

`next(...)` toma **el primero que encuentra y para**. Con «compara mayo con julio en Castilla»
devuelve `"mayo"`, el motor responde mayo entero y **no avisa de que ignoró julio**. Es el bug del
periodo ignorado (CLAUDE.md §7) en su forma más limpia: no falla, responde otra cosa.

**Consecuencia:** el detector de comparación (§3.1) es un módulo NUEVO. `_periodo_texto` **no se
toca** — lo consumen N1, N2, N3, N4 y también `respuesta_analizar` (slots.py:455 lo expone como
`periodo_texto` justo para eso). Cambiar su contrato de `str|None` a algo plural rompería cinco
consumidores para arreglar uno.

### 🟢 P2 — El YoY NO necesita query nueva. `_periodo_texto` ya sabe leer «julio 2025»

Misma función, línea 447-448:

```python
ym = re.search(r"20\d\d", t)                 # año opcional ("abril 2026")
return f"{mo} {ym.group(0)}" if ym else mo
```

Y `desempeno(periodo="julio 2025")` lo aterriza: `_parse_periodo` (`analisis/api.py:372`) entiende
«mes» y «mes año». **El YoY de un mes se resuelve con una segunda llamada a `desempeno`**, igual
que `niveles.acumulado` llama una por mes. Cero SQL nuevo.

⚠️ Lo que NO existe es YoY de **año completo contra año completo** — eso sí exigiría agregar 12
meses de dos años. Va a §7 (fuera de alcance).

### 🔴 P3 — `no_soportado.py` rechaza «en el año 2025», pero NO «julio de 2025»

`no_soportado.py:51-54`:

```python
("anio",
 re.compile(r"\bTODO\s+EL\s+ANO|\bEN\s+EL\s+ANO\s+20\d\d|\bDURANTE\s+20\d\d|\bANUAL\b"),
 "un año completo", "un mes puntual o el acumulado del año", ...)
```

Verificado carácter a carácter: «¿cuánto produjo Castilla en julio de 2025 vs julio de 2026?» **no
casa** con ninguna de las cuatro alternativas → no se rechaza, llega al motor. ✅

Pero «¿cómo va 2026 **durante** 2025?» o «compara **el año 2025** con 2026» **sí** casan y caen al
rechazo honesto. Eso es **correcto y se conserva**: el YoY de año completo no está soportado (P2), y
un rechazo honesto es mejor que una cifra fabricada. **No se toca `no_soportado.py`.**

### 🔴 P4 — «VS» ya tiene dueño: la REFERENCIA. Un detector ingenuo se la roba

`cuantificar/slots.py:81`:

```python
("promedio_anio", ("PROMEDIO DEL ANO", "PROMEDIO ANUAL", "VS EL PROMEDIO",
                   "CONTRA EL PROMEDIO", "RESPECTO AL PROMEDIO")),
```

«¿cómo va Castilla **vs el promedio**?» es una pregunta de REFERENCIA (N1 con
`referencia=promedio_anio`), no de comparación de periodos. Un detector que capture `X vs Y` sin
guarda se la robaría y respondería otra cosa.

**Consecuencia:** §3.1 lleva `_RX_CMP_NO`, una guarda que descarta la comparación cuando lo que
sigue al conector es una REFERENCIA (promedio, presupuesto, ppto, meta, P50, operativo, contable) y
no un periodo. Sin esa guarda el plan introduce una regresión en una función que hoy es correcta.

### 🟢 P5 — `COMPARA`/`COMPARAME` en `incompleta.py` NO bloquea

`incompleta.py:42-47` los tiene como verbos de acción, pero `detectar()` (:52) exige **tres
condiciones conjuntivas**: hay verbo **Y** `hay_entidad is False` **Y** `nivel is None`. «compara
mayo con julio en Castilla» trae entidad → no dispara. ✅ No hay que tocar nada.

### 🟡 P6 — `comparativo_mes` ya existe, pero es otra cosa

`analisis/api.py:2043` devuelve `{mes_anterior, por_producto: {PROD: {actual, anterior}}}`. Es el
mes en curso vs el anterior, `None` en enero, y **es un subproducto de `ejecutivo()`** que alimenta
el bloque «Ojo con esto» de `analizar/plantilla.py:148`.

**No se reutiliza**: solo sabe hacer «actual vs anterior», no dos periodos arbitrarios, y vive en la
rama de Analizar. **No se toca** — el bloque de iniciativa depende de él.

### 🔴 P7 — NO existe serie mensual de PPTO. Es el coste real del tipo 3

Las diez consultas de PPTO en `analisis/api.py` llevan `WHERE m.fecha = :fin`: **un solo mes**. Y
`ritmo_mensual` (:614) filtra `WHERE es.nombre = 'REAL'` — solo REAL.

Para «real vs programa a lo largo del tiempo» hace falta el PPTO de cada mes. Dos caminos:

| | Cómo | Coste | Riesgo |
|---|---|---|---|
| **(a)** | N llamadas a `desempeno(periodo=mes)`, una por mes | ~7-12 consultas | **Ninguno**: es EXACTAMENTE lo que ya hace `niveles.acumulado` (:44-54), probado en producción |
| (b) | Query nueva de PPTO mensual en `analisis/api.py` | 1 consulta | Toca un archivo compartido con el tablero, y `desempeno` es el corazón del sistema |

**Decisión cerrada: (a).** Se clona el bucle de `acumulado`, que ya está validado. La eficiencia se
optimiza cuando duela, no antes — y aquí no duele: N2 ya paga ese precio hoy sin queja.

### 🔴 P8 — «mes a mes» es de N3. N3P tiene que ganarle sin robársela

`cuantificar/slots.py:36`: `_SERIE_PHRASES = ("MES A MES", "MES POR MES", "POR MES", "CADA MES")`
→ N3.

«¿cómo va el real **vs el presupuesto mes a mes**?» trae la frase de N3 **y** la señal de PPTO. Si
N3 gana, se pierde el presupuesto; si N3P se lleva todo «mes a mes», N3 desaparece.

**Consecuencia:** N3P exige **las dos señales a la vez** — serie (`_SERIE_*`) **Y** referencia
explícita al programa (`_RX_PROGRAMA`). Una sola no basta. Así «la serie mensual de Castilla» sigue
siendo N3 y «la serie mensual contra el presupuesto» pasa a N3P.

### 🟡 P9 — La ventana eleva el nivel al final de `extraer_slots`; hay orden que respetar

`slots.py:573-588` eleva `N1 → N1DSER` (ventana de días/semanas) y `N1 → N2` (ventana de >1 mes)
**después** de fijar `nivel`. Si la comparación se resolviera antes de eso, «compara los últimos 3
meses con los 3 anteriores» quedaría en un estado inconsistente.

**Consecuencia:** `NCMP`/`N3P` se resuelven **después** del bloque de ventana, y ganan sobre él.
Comparación + ventana simultáneas se declaran fuera de alcance (§7) con rechazo honesto.

### 🟢 P10 — Independencia del punto 2

`plan_TENDENCIA_20260903.md` toca `analizar/` (subrouter, plantilla, respuesta_analizar) y
`patrones_grupo.yaml`. Este plan toca `cuantificar/` (slots, niveles, ejecutor, validador) y
`respuesta_cuantificar.py`. **Intersección: solo `multitab_shell.js` y el cache-buster**, y en
funciones distintas. Se pueden ejecutar en cualquier orden.

⚠️ Si el punto 2 ya se ejecutó, el cache-buster estará en `?v=20260903g`; súbelo a `h`. Si no, de
`f` a `g`. **Mira el valor real antes de editar** (§3.9).

### 🟡 P11 — El cache-buster (lección del 2026-09-03)

`frontend/MainChat/templates/mainchat_layout.html:317` carga `multitab_shell.js` con `?v=...`. Ese
archivo cambió tres veces sin subir el `?v=`: el navegador sirvió su copia cacheada, el panel no
aparecía y **no había ningún error en consola**. Media sesión de diagnóstico.
**Si tocas `multitab_shell.js`, subes el `?v=` en el mismo commit.**

### 🔴 P13 — `_MESES` de `slots.py` NO se puede indexar por número de mes

`cuantificar/slots.py:84`:

```python
_MESES = ("enero febrero marzo abril mayo junio julio agosto septiembre setiembre "
          "octubre noviembre diciembre").split()
```

Es una lista **desde CERO** y con **14 elementos**: trae `"setiembre"` como segunda grafía. Por
tanto `_MESES[7]` es `"agosto"` (desplazado uno) y de septiembre en adelante todo queda corrido —
`_MESES[10]` sería `"octubre"` cuando debería ser `"noviembre"`.

⚠️ Esto **no es un bug del código actual**: nadie lo indexa por número, se recorre buscando
coincidencias (`_periodo_texto`, `_mes_nombrado`). Es una trampa para el código NUEVO de este plan,
que sí necesita ir de número a nombre para reconstruir «julio 2025».

Invertir `_MESES_NUM` tampoco sirve: dos claves apuntan al 9.

**Consecuencia:** §3.1 define `_MES_NOMBRE` explícito, 12 entradas. No se toca `_MESES`: sus dos
consumidores actuales lo usan correctamente y añadir/quitar grafías les cambiaría el
comportamiento.

⚠️ El `_MESES` de **`niveles.py`** (`["", "enero", ...]`, con cadena vacía en el índice 0) **sí**
está indexado desde 1 y `serie_programa` (§3.2) lo usa así, igual que `acumulado`. Son dos
constantes distintas con el mismo nombre en módulos distintos: no las confundas.

### 🟢 P12 — Los tres registros del panel

`multitab_shell.js` registra cada tipo de panel en **tres** sitios: el ternario de
`__cnPintarPanelCuant`, la línea de `__cnPanelMesCargar` y la rama de `__cnPanelMesPintar`. Saltarse
uno produce un panel que no pinta **sin error en consola**.

---

## 1C. Hallazgos de la VERIFICACIÓN del v1

El v1 se contrastó contra el código real. Esto es lo que estaba mal y por qué la §3 cambió.

### 🔴 V1 — `validador.py` no está donde el v1 decía. Los tests reventaban con `ImportError`

El v1 escribía `consulta_v2/validador.py` en §3.4, en la regla 9 y en el import de los tests. La
ruta real, verificada con `find`:

```
app/features/consulta_v2/cuantificar/validador.py
```

Vive **dentro de `cuantificar/`**, y su único consumidor lo importa así
(`respuesta_cuantificar.py:26`):

```python
from app.features.consulta_v2.cuantificar import validador as _validador
```

El v1 tenía en `test_cuantificar_comparacion.py` la línea
`from app.features.consulta_v2 import validador as _val`, que **no resuelve**: los dos tests de
contrato HE6 habrían fallado con `ImportError` antes de ejecutar una sola aserción.

**Corrección:** ruta y import arreglados en §3.4, §3.8 y §5.9.

### 🔴 V2 — `cerrado` MIENTE para un mes de otro año. El YoY lo habría rotulado mal

`analisis/api.py:660`:

```python
"cerrado": ((y, mo) < (amb["maxd"].year, amb["maxd"].month)) or (dias_rep >= dim)
```

La comparación es de **tuplas `(año, mes)`**, así que para `periodo="julio 2025"` con
`maxd=2026-08-30` da `(2025,7) < (2026,8)` → `True`. Correcto.

Pero el segundo término es la trampa: `dias_rep` cuenta días del **reporte diario**, y para un mes
de 2025 la tabla diaria puede no tener filas → `dias_rep=0`, `dias_del_mes=31`. El primer término
ya salva el caso, **pero `dias_con_data` y `dias_del_mes` viajan al aviso HE4 del v1**:

```python
avisos.append(f"{lado['periodo']} sigue en curso ({lado['dias_con_data']}/{lado['dias_del_mes']} días)")
```

Con un mes cerrado de 2025 ese aviso no se emite (porque `cerrado` es True), pero si el histórico
mensual existe y el diario no, el panel recibiría `dias_con_data: 0` y cualquier lectura futura de
esa clave afirmaría «0 de 31 días reportados» sobre un mes definitivo — la misma familia de bug que
`completo` vs `cerrado` que ya costó una sesión el 2026-09-03.

**Corrección:** §3.2 marca `diario_disponible` explícito y §3.3 solo emite el aviso de días cuando
ese flag es verdadero. Un mes sin reporte diario no se describe con días.

### 🟡 V3 — `_parse_periodo` casa el mes por SUBSTRING, no por token

`analisis/api.py:390`:

```python
mo = next((num for nombre, num in _MESES_NUM.items() if nombre in t), None)
```

Es `nombre in t`, es decir substring — exactamente el patrón que produjo el bug «MAYO» ⊂ «MAYOR» y
que `slots.py` corrigió a `\b` en dos sitios (AF-3.7).

**No es un problema para este plan**: `comparacion()` le pasa cadenas que el propio motor construye
(`"julio 2025"`), nunca texto del usuario. Pero conviene saberlo: **no le pases nunca la frase del
usuario a `desempeno(periodo=...)`**, solo periodos ya normalizados. Queda como regla en §5.

### 🟢 V4 — Los helpers del ejecutor existen y los alias son correctos

Verificado en `cuantificar/ejecutor.py`: `_PROD_MAP` (:22), `_cualificar` (:28),
`_etiqueta_nivel` (:40), `_niveles` (:15) y `_rechazo_comun` (:84). El código de §3.3 los usa bien.

### 🟢 V5 — El orden de ramas del validador confirma el diseño

`cuantificar/validador.py`: N3 (:37), N4 (:46), N1D (:62), N1DSER (:71), N1DSEL (:81), y en :90 el
comentario `# N1/N2 (usan resultado/referencia — solo aquí, ya descartados N3/N4)` seguido de la
lectura de `res["resultado"]`. **NCMP y N3P deben ir antes de :90**, como decía el v1. Confirmado.

### 🟡 V6 — El bloque de `cierre` tiene 4 ramas, no las que el v1 supuso

`respuesta_cuantificar.py:365-371` son cuatro asignaciones encadenadas. El v1 decía «busca el bloque
que fija el cierre… y añade antes del `else`», lo cual es correcto pero vago. §3.5c ahora nombra la
línea exacta (`elif res.get("nivel") == "N2": cierre = "¿Quieres el detalle de un mes puntual?"`,
:369) para que el executor no tenga que interpretar.

### 🟡 V7 — Simplificación: N3P y N2 comparten bucle, y eso es aceptable

`serie_programa` (§3.2) clona el bucle de `acumulado` (`niveles.py:44-54`). Se evaluó factorizar un
`_serie_mensual_core` compartido y **se descarta**: `acumulado` tiene reglas propias (HE4 estricto,
`desde_mes`, `omitidos`, `serie_acum`) que N3P no comparte, y unificarlas ataría dos niveles con
contratos distintos. El proyecto ya tomó esta decisión antes (`ejecutor.py`: «4 args explícitos, sin
factorizar un `_desempeno_core`»). Se duplica el bucle a propósito, y se dice por qué.

---

## 2. Estado actual

**`cuantificar/slots.py`** (~660 líneas). Módulo PURO. Contiene `_MESES` (lista de nombres en
minúscula), `_MESES_NUM` (dict `{nombre_minúscula: int}`), `_periodo_texto` (:432), el detector de
ventana `detectar_ventana` (:456) y `extraer_slots` (:540) que devuelve el dict de slots.

**`cuantificar/ejecutor.py`**: `ejecutar()` (:65) despacha por `nivel_temporal` con una cadena de
`if`. Cada `ejecutar_nX` devuelve el contrato §7 (dict con `aplica`, `nivel`, `entidad`,
`resultado`, `avisos`…) o `{aplica: False, texto}`.

**`cuantificar/niveles.py`**: `acumulado()` (:13) llama a `desempeno` una vez por mes en un bucle
`for m in range(...)`. Ese bucle es el molde de §3.3.

**`consulta_v2/cuantificar/validador.py`** (⚠️ dentro de `cuantificar/`, V1):
`formatear_cuerpo(res)` ramifica por `res["nivel"]`. **N3/N4/N1D/
N1DSER/N1DSEL van ANTES de leer `res["resultado"]`/`res["mes"]`**, porque esas claves no existen en
sus contratos (HE6). Los niveles nuevos deben ir en esa zona temprana.

**`consulta_v2/respuesta_cuantificar.py`**: `_PANEL_TIPO` (:55) mapea nivel → tipo de panel, y
`_panel_datos` (:110) arma el payload ramificando por nivel.

**`multitab_shell.js`** (488.355 bytes): dispatcher en `__cnPintarPanelCuant` (~:4269), envoltorio
`__cnPanelMesHtml(d, hostCls)` (~:4408), pintor multi-traza de referencia `__cnAcumMesInto`
(~:4452), y `__cnPanelMesPintar` (~:4536).

---

## 3. Especificación

### 3.1 MODIFICAR — `cuantificar/slots.py` · detector de comparación

**(a)** Añade estas constantes **justo después** del bloque `_RX_VENTANA` (~:181, tras el cierre
`)` de esa expresión):

```python
# ============================================================================
# [2026-09-03 · COMPARACION-PERIODOS] Punto 3 de inteligencia de tiempo, tipo 2.
# ============================================================================
# Conectores de comparación. Todos exigen DOS periodos: sin el segundo no hay comparación,
# y adivinarlo sería justo el fallo que este bloque existe para cerrar (P1).
_CMP_CONECTOR = r"(?:VS|VERSUS|CONTRA|FRENTE\s+A|COMPARAD[OA]\s+CON|COMPARADO\s+A|RESPECTO\s+A)"

# 🔴 P4 — GUARDA. "VS EL PROMEDIO" / "CONTRA EL PROMEDIO" / "RESPECTO AL PROMEDIO" ya son el
# detector de REFERENCIA (:81) y hoy resuelven bien a N1 con referencia=promedio_anio. Lo mismo
# vale para el presupuesto y sus escenarios: «¿cómo va Castilla vs el presupuesto?» es la
# pregunta N1 de toda la vida. Si el conector va seguido de una REFERENCIA en vez de un
# PERIODO, esto NO es una comparación de periodos y el detector se aparta.
# 🔑 Se mira lo que sigue al conector, no si la palabra aparece en la frase: «julio vs junio
#    contra el presupuesto» tiene las dos cosas y sí es una comparación de periodos.
_RX_CMP_NO = re.compile(
    _CMP_CONECTOR + r"\s+(?:EL\s+|LA\s+|AL\s+|LOS\s+|SU\s+)?"
    r"(?:PROMEDIO|PPTO|PRESUPUESTO|META|P50|OPERATIVO|CONTABLE|PROGRAMA|PLAN)\b")

# Periodo RELATIVO como segundo término: «julio vs el mes pasado», «vs el año pasado».
_RX_CMP_MES_PASADO = re.compile(r"\b(?:EL\s+)?MES\s+(?:PASADO|ANTERIOR)\b")
_RX_CMP_ANIO_PASADO = re.compile(
    r"\b(?:EL\s+)?(?:MISMO\s+MES\s+DEL\s+)?ANO\s+(?:PASADO|ANTERIOR)\b"
    r"|\bMISMO\s+MES\s+DE\s+20\d\d\b|\bINTERANUAL\b")

# 🔴 P13 — Número → nombre canónico, EXPLÍCITO. NO se puede indexar `_MESES` (:84) para esto:
# es una lista desde CERO y además trae "setiembre" como segunda grafía de septiembre, así que
# `_MESES[7]` es "agosto" (desplazado uno) y de septiembre en adelante todo queda corrido.
# `_MESES_NUM` tampoco vale invertido sin más: dos claves apuntan al 9.
_MES_NOMBRE = {1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
               7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre",
               12: "diciembre"}
```

**(b)** Añade esta función **justo antes** de `def extraer_slots` (~:540):

```python
def _periodo_en(fragmento: str, anio_defecto: int):
    """('julio 2025', 7, 2025) del fragmento, o None. Fragmento = un lado de la comparación.

    Devuelve la cadena LISTA para `desempeno(periodo=...)`, que entiende «mes» y «mes año»
    (_parse_periodo, analisis/api.py:372). El año va SIEMPRE explícito: en una comparación,
    dejarlo implícito es como se cuela un YoY que en realidad compara el mismo año consigo
    mismo. Se declara, no se asume en silencio.
    """
    mes = _mes_nombrado(fragmento)
    if mes is None:
        return None
    ym = re.search(r"\b(20\d\d)\b", fragmento)
    anio = int(ym.group(1)) if ym else anio_defecto
    return f"{_MES_NOMBRE[mes]} {anio}", mes, anio


def detectar_comparacion(texto: str, techo=None) -> dict | None:
    """Comparación de DOS periodos mensuales, o None. [2026-09-03 · COMPARACION-PERIODOS]

    Devuelve:
      {"clase": "meses"|"mom"|"yoy",
       "a": "julio 2026", "mes_a": 7, "anio_a": 2026,
       "b": "mayo 2026",  "mes_b": 5, "anio_b": 2026,
       "asumido": [...]}

    `techo` (date) = último día CON DATO, no el reloj. Fija el año por defecto y el mes de
    referencia cuando el usuario dice «vs el mes pasado» sin nombrar el primero. Sin techo se
    devuelve None: es preferible el rechazo honesto a inventar un ancla (misma regla que
    `detectar_ventana`). 🔑 Módulo PURO: el techo entra por parámetro, aquí no hay BD.

    🔴 Guarda P4: si al conector le sigue una REFERENCIA (promedio/presupuesto/meta/P50/…),
       esto NO es una comparación de periodos sino la pregunta N1 de referencia, que hoy
       funciona. Se devuelve None y el flujo sigue como siempre.
    """
    t = norm(texto or "")
    if techo is None:
        return None
    m = re.search(_CMP_CONECTOR, t)
    if m is None:
        return None
    if _RX_CMP_NO.search(t):
        return None                       # es una REFERENCIA, no dos periodos (P4)

    izq, der = t[:m.start()], t[m.end():]
    anio_techo = techo.year

    # --- lado B (lo que va DESPUÉS del conector) -------------------------------------
    # Se resuelve primero: es el que admite formas relativas, y de él depende cómo se lee A.
    b_rel = None
    if _RX_CMP_ANIO_PASADO.search(der):
        b_rel = "yoy"
    elif _RX_CMP_MES_PASADO.search(der):
        b_rel = "mom"

    a = _periodo_en(izq, anio_techo)
    if a is None:
        # Sin mes a la izquierda, el ancla es el mes del TECHO: «¿cómo vamos vs el año
        # pasado?» = el mes del techo contra su gemelo del año anterior. Se DECLARA.
        a = (f"{_MES_NOMBRE[techo.month]} {anio_techo}", techo.month, anio_techo)
        a_asumido = [f"periodo A = {a[0]} (el mes del último reporte)"]
    else:
        a_asumido = []

    if b_rel == "yoy":
        b = (f"{_MES_NOMBRE[a[1]]} {a[2] - 1}", a[1], a[2] - 1)
        clase = "yoy"
    elif b_rel == "mom":
        _m, _y = (a[1] - 1, a[2]) if a[1] > 1 else (12, a[2] - 1)
        b = (f"{_MES_NOMBRE[_m]} {_y}", _m, _y)
        clase = "mom"
    else:
        b = _periodo_en(der, anio_techo)
        if b is None:
            return None                   # hay conector pero no un segundo periodo → no aplica
        clase = "yoy" if (b[1] == a[1] and b[2] != a[2]) else "meses"

    if (a[1], a[2]) == (b[1], b[2]):
        return None                       # «julio vs julio»: no hay nada que comparar

    asumido = a_asumido + [f"comparacion {clase}: {a[0]} contra {b[0]}"]
    return {"clase": clase,
            "a": a[0], "mes_a": a[1], "anio_a": a[2],
            "b": b[0], "mes_b": b[1], "anio_b": b[2],
            "asumido": asumido}


# [2026-09-03 · COMPARACION-PERIODOS] Tipo 3: la serie mensual REAL **contra el PROGRAMA**.
# 🔴 P8 — Exige LAS DOS señales: serie (_SERIE_WORDS/_SERIE_PHRASES, que ya dan N3) Y una
#    referencia explícita al programa. Con una sola, «la serie mensual de Castilla» dejaría de
#    ser N3 o «vs el presupuesto» dejaría de ser N1: dos respuestas correctas rotas de golpe.
_RX_PROGRAMA = re.compile(r"\b(?:PROGRAMA|PRESUPUESTO|PPTO|META|PLAN)\b")
```

**(c)** En `_nivel_temporal` **no se toca nada**. La elevación va en `extraer_slots`.

**(d)** En `extraer_slots`, **después** del bloque de elevación por ventana (`elif (ventana is not
None and nivel == "N1" ... nivel = "N2"`, ~:586-588) y **antes** de `per = _periodo_texto(texto)`
(~:590), inserta:

```python
    # [2026-09-03 · COMPARACION-PERIODOS] Se resuelve AL FINAL, después de la ventana (P9): la
    # comparación es la intención más específica y gana a todas. Antes de `_periodo_texto`
    # porque ese detector solo ve UN mes y con dos nombrados devolvería el primero (P1).
    comparacion = detectar_comparacion(texto, techo)
    if comparacion is not None:
        # 🔑 Comparación + ventana a la vez («los últimos 3 meses vs los 3 anteriores») NO está
        #    soportada: se declina en el ejecutor con rechazo honesto, no se resuelve a medias.
        nivel = "NCMP"
    # [2026-09-03 · COMPARACION-PERIODOS] Tipo 3: serie REAL vs PROGRAMA. Exige LAS DOS señales
    # (P8) y solo eleva desde N3 — nunca desde N1/N2/N4, que responden otra cosa.
    elif nivel == "N3" and _RX_PROGRAMA.search(norm(texto or "")):
        nivel = "N3P"
```

**(e)** En el `return` de `extraer_slots` (~:628), añade la clave junto a `"ventana": ventana,`:

```python
        "comparacion": comparacion,
```

**(f)** En `menciona_dia` (~:278-287), añade la comparación a las razones para pedir el techo. **Sin
esto, `detectar_comparacion` recibiría `techo=None` por la ruta real y devolvería None siempre**: la
comparación funcionaría en los tests —donde el techo se pasa a mano— y NO en producción. Es
literalmente el bug que ese docstring ya documenta dos veces. Reemplaza la última línea
(`return detectar_ventana(texto, TECHO_CENTINELA) is not None`) por:

```python
    if detectar_ventana(texto, TECHO_CENTINELA) is not None:
        return True
    # 🔑 [2026-09-03] La COMPARACIÓN también necesita techo (fija el año por defecto y el mes
    #    ancla de «vs el mes pasado»). Mismo motivo, misma solución que la ventana de arriba.
    return detectar_comparacion(texto, TECHO_CENTINELA) is not None
```

### 3.2 MODIFICAR — `cuantificar/niveles.py` · comparación y serie con programa

Añade **al final** del archivo:

```python
def comparacion(resuelta: dict, dim_producto: str, cmp_: dict, _desempeno_fn=None) -> dict:
    """Los DOS periodos de una comparación, con su REAL y su PPTO. [2026-09-03 · COMPARACION]

    Dos llamadas a `desempeno`, una por periodo — el mismo patrón de `acumulado` (:44), que
    llama una vez por mes. Cero SQL nuevo: `_parse_periodo` ya entiende «julio 2025» (P2).

    🔑 Los 4 argumentos van EXPLÍCITOS. `desempeno` es un endpoint FastAPI y sus defaults son
       objetos Query(...); uno sobreviviente llegó al SQL y reventó con "cannot adapt type
       'Query'" (analisis/api.py:504-511). Mismo criterio que :25 y ejecutor.py:111.
    """
    fn = _desempeno_fn or _desempeno_ep
    out = {}
    for lado, periodo in (("a", cmp_["a"]), ("b", cmp_["b"])):
        d = fn(entidad=resuelta["valor"], segmento="ecp",
               nivel=resuelta.get("nivel"), periodo=periodo)
        if not d.get("encontrada") or d.get("sin_datos") or d.get("sin_cierre"):
            return {"aplica": False,
                    "texto": (f"No tengo cierre mensual de «{resuelta['valor']}» para "
                              f"{periodo}; sin ese dato la comparación sería media verdad.")}
        fila = next((p for p in d["por_producto"] if p["producto"] == dim_producto), None)
        if not fila or (fila["real"] == 0 and fila["ppto"] == 0):
            return {"aplica": False,
                    "texto": f"«{resuelta['valor']}» no reporta {dim_producto.lower()} en {periodo}."}
        mes = d["mes"]
        out[lado] = {
            "periodo": periodo, "real": fila["real"], "ppto": fila["ppto"] or 0,
            # [MES-CERRADO, 2026-09-03] `cerrado` ≠ `completo`. `completo` mide la cobertura del
            # reporte DIARIO; un mes ya cerrado puede tenerla incompleta (medido: CASTILLA mayo
            # 2026, 17/31) y seguir siendo definitivo. Aquí importa si la cifra es final.
            "cerrado": mes.get("cerrado", mes["completo"]),
            "dias_con_data": mes.get("dias_con_data"), "dias_del_mes": mes.get("dias_del_mes"),
            # 🔴 V2 — ¿hay reporte DIARIO de este mes? Para un periodo del año anterior el cierre
            # mensual puede existir sin que exista la tabla diaria: ahí `dias_con_data` vale 0 y
            # describir el mes como «0 de 31 días» sería falso sobre una cifra definitiva. Es la
            # misma familia del bug `completo` vs `cerrado` que costó una sesión el 2026-09-03.
            # `aplica_diario` lo dice `desempeno` desde `_ambito` (api.py:438); sin la clave se
            # asume que NO hay, que es el lado seguro (no se afirma nada sobre días).
            "diario_disponible": bool(d.get("aplica_diario")) and bool(mes.get("dias_con_data")),
            "nombre": mes.get("nombre"), "anio": mes.get("anio"),
        }
    a, b = out["a"], out["b"]
    delta = a["real"] - b["real"]
    return {"aplica": True, "a": a, "b": b, "delta": delta,
            "pct": (round(delta / b["real"] * 100.0, 1) if b["real"] else None),
            # Cumplimiento de cada lado contra SU propio presupuesto: comparar el REAL de julio
            # contra el PPTO de mayo no significa nada, y es el error fácil de esta pantalla.
            "cumpl_a": (round(a["real"] / a["ppto"] * 100.0, 1) if a["ppto"] else None),
            "cumpl_b": (round(b["real"] / b["ppto"] * 100.0, 1) if b["ppto"] else None)}


def serie_programa(resuelta: dict, dim_producto: str, _desempeno_fn=None) -> dict:
    """Serie mensual REAL **y PPTO** del año. [2026-09-03 · COMPARACION-PERIODOS, tipo 3]

    🔴 P7 — `ritmo_mensual` trae SOLO el REAL (`WHERE es.nombre = 'REAL'`, api.py:614) y todas
    las consultas de PPTO son de un solo mes (`WHERE m.fecha = :fin`). No existe una serie
    mensual de presupuesto en ninguna parte, así que se construye llamando a `desempeno` una
    vez por mes — el bucle de `acumulado` (:44-54), clonado, que lleva meses en producción.

    🔑 HE4: el mes EN CURSO entra en la serie pero marcado `cerrado: False`. A diferencia del
       acumulado —donde sumarlo falsearía un total— aquí es un punto de una curva y ocultarlo
       dejaría un hueco al final que el usuario leería como una caída.
    """
    fn = _desempeno_fn or _desempeno_ep
    d0 = fn(entidad=resuelta["valor"], segmento="ecp", nivel=resuelta.get("nivel"), periodo=None)
    if not d0.get("encontrada") or d0.get("sin_datos") or d0.get("sin_cierre"):
        return {"aplica": False,
                "texto": f"No tengo serie mensual de producción para «{resuelta['valor']}»."}
    anio, ultimo = d0["mes"]["anio"], d0["mes"]["mes"]
    puntos, omitidos = [], []
    for m in range(1, ultimo + 1):
        dm = fn(entidad=resuelta["valor"], segmento="ecp",
                nivel=resuelta.get("nivel"), periodo=_MESES[m])
        if not dm.get("encontrada") or dm.get("sin_datos") or dm.get("sin_cierre"):
            omitidos.append(_MESES[m]); continue
        fila = next((p for p in dm["por_producto"] if p["producto"] == dim_producto), None)
        if not fila or (fila["real"] == 0 and fila["ppto"] == 0):
            omitidos.append(_MESES[m]); continue
        puntos.append({
            "mes": _MESES[m][:3].capitalize(), "num": m,
            "real": fila["real"], "ppto": (fila["ppto"] or None),
            "cumpl": (round(fila["real"] / fila["ppto"] * 100.0, 1) if fila["ppto"] else None),
            "cerrado": (m < ultimo or dm["mes"].get("cerrado", dm["mes"]["completo"])),
        })
    if not puntos:
        return {"aplica": False,
                "texto": f"«{resuelta['valor']}» no tiene meses con cierre en {anio}."}
    con_meta = [p for p in puntos if p["cumpl"] is not None]
    return {"aplica": True, "puntos": puntos, "anio": anio, "omitidos": omitidos,
            "cumpl_medio": (round(sum(p["cumpl"] for p in con_meta) / len(con_meta), 1)
                            if con_meta else None),
            "meses_bajo_meta": sum(1 for p in con_meta if p["cumpl"] < 100)}
```

### 3.3 MODIFICAR — `cuantificar/ejecutor.py`

**(a)** En `ejecutar()` (:65), añade **antes** de la línea `if nt == "N4":`:

```python
    if nt == "NCMP":
        return ejecutar_ncmp(resuelta, slots, _desempeno_fn=_desempeno_fn)
    if nt == "N3P":
        return ejecutar_n3p(resuelta, slots, _desempeno_fn=_desempeno_fn)
```

Y actualiza el docstring de `ejecutar()` añadiendo `· NCMP comparación de periodos · N3P serie
real vs programa`.

**(b)** Añade **al final** del archivo:

```python
def ejecutar_ncmp(resuelta: dict, slots: dict, _desempeno_fn=None) -> dict:
    """NCMP: dos periodos mensuales comparados. [2026-09-03 · COMPARACION-PERIODOS, tipo 2]
    HE6: NO fabrica un `mes` sintético — trae `a`/`b`/`delta` propios."""
    rech = _rechazo_comun(resuelta, slots)
    if rech:
        return rech
    cmp_ = slots.get("comparacion")
    if not cmp_:
        return {"aplica": False, "texto": "No identifiqué los dos periodos que quieres comparar."}
    # 🔑 P9: comparación + ventana a la vez no está soportada. Se DECLINA en vez de resolver una
    #    de las dos y callarse la otra — que es el fallo que este plan entero viene a cerrar.
    if slots.get("ventana"):
        return {"aplica": False, "texto": (
            "Puedo comparar dos meses concretos, o darte una ventana móvil, pero todavía no las "
            "dos cosas a la vez. Dime los dos meses que quieres comparar.")}
    producto = slots["producto"]
    unidad = slots.get("unidad", "bbl")
    c = _niveles.comparacion(resuelta, _PROD_MAP[producto], cmp_, _desempeno_fn=_desempeno_fn)
    if not c.get("aplica"):
        return {"aplica": False, "texto": c["texto"]}

    a, b = c["a"], c["b"]
    _ETIQ = {"yoy": "interanual", "mom": "contra el mes anterior", "meses": "entre meses"}
    avisos = []
    if slots.get("descargo"):
        avisos.append(slots["descargo"])
    for lado in (a, b):
        # HE4 explícito: comparar un mes EN CURSO contra uno cerrado no es ilegítimo, pero
        # callarlo sí. Un mes a 30/31 días compite en desventaja y hay que decirlo.
        # 🔴 V2 — el detalle de días SOLO si hay reporte diario. Un mes de 2025 puede tener
        #    cierre mensual sin tabla diaria: ahí `dias_con_data` es 0 y decir «0 de 31 días»
        #    sobre una cifra definitiva sería una afirmación falsa.
        if not lado["cerrado"]:
            if lado["diario_disponible"]:
                avisos.append(f"{lado['periodo']} sigue en curso ({lado['dias_con_data']}/"
                              f"{lado['dias_del_mes']} días): su cifra todavía es una proyección.")
            else:
                avisos.append(f"{lado['periodo']} todavía no está cerrado: su cifra es "
                              f"provisional.")
    if slots.get("referencia", "PPTO") != "PPTO":
        avisos.append("Las referencias alternas (operativo/contable/promedio) por ahora solo "
                      "aplican al dato puntual de un mes; la comparación usa el presupuesto.")

    return {
        "aplica": True, "grupo": "cuantificar", "variable": slots.get("variable", "produccion_crudo"),
        "nivel": "NCMP",
        "entidad": {"nombre": resuelta["valor"], "nivel": resuelta.get("nivel"), "fue_asumida": False},
        "entidad_cualificada": _cualificar(resuelta),
        "producto": producto, "referencia": "PPTO", "unidad": unidad, "grano": "mes",
        "universo": "reporte_diario",
        "clase": cmp_["clase"], "clase_label": _ETIQ.get(cmp_["clase"], "entre periodos"),
        "a": a, "b": b, "delta": c["delta"], "pct": c["pct"],
        "cumpl_a": c["cumpl_a"], "cumpl_b": c["cumpl_b"],
        "huella": {"registros": 2, "es_proyeccion": not (a["cerrado"] and b["cerrado"])},
        "defaults_asumidos": slots.get("defaults_asumidos", []), "avisos": avisos,
        "zoom": resuelta.get("zoom", []),
    }


def ejecutar_n3p(resuelta: dict, slots: dict, _desempeno_fn=None) -> dict:
    """N3P: la serie mensual REAL contra el PROGRAMA. [2026-09-03 · COMPARACION-PERIODOS, tipo 3]
    HE6: contrato propio (`puntos`), sin `resultado` ni `mes`."""
    rech = _rechazo_comun(resuelta, slots)
    if rech:
        return rech
    producto = slots["producto"]
    unidad = slots.get("unidad", "bbl")
    s = _niveles.serie_programa(resuelta, _PROD_MAP[producto], _desempeno_fn=_desempeno_fn)
    if not s.get("aplica"):
        return {"aplica": False, "texto": s["texto"]}

    avisos = []
    if slots.get("descargo"):
        avisos.append(slots["descargo"])
    if s.get("omitidos"):
        _om = ", ".join(s["omitidos"])
        avisos.append(f"No tengo cierre mensual de {_om}; {'esos meses' if len(s['omitidos']) > 1 else 'ese mes'} "
                      f"no está{'n' if len(s['omitidos']) > 1 else ''} en la serie.")
    if s["puntos"] and not s["puntos"][-1]["cerrado"]:
        avisos.append(f"El último punto ({s['puntos'][-1]['mes']}) es el mes en curso: "
                      f"su cifra es una proyección, no un cierre.")
    if any(p["ppto"] is None for p in s["puntos"]):
        _sm = ", ".join(p["mes"] for p in s["puntos"] if p["ppto"] is None)
        avisos.append(f"Sin presupuesto cargado en {_sm}: esos meses salen sin línea de programa.")

    return {
        "aplica": True, "grupo": "cuantificar", "variable": slots.get("variable", "produccion_crudo"),
        "nivel": "N3P",
        "entidad": {"nombre": resuelta["valor"], "nivel": resuelta.get("nivel"), "fue_asumida": False},
        "entidad_cualificada": _cualificar(resuelta),
        "producto": producto, "referencia": "PPTO", "unidad": unidad, "grano": "mes",
        "universo": "reporte_diario",
        "puntos": s["puntos"], "anio": s["anio"],
        "cumpl_medio": s["cumpl_medio"], "meses_bajo_meta": s["meses_bajo_meta"],
        "huella": {"registros": len(s["puntos"]), "es_proyeccion": False},
        "defaults_asumidos": slots.get("defaults_asumidos", []), "avisos": avisos,
        "zoom": resuelta.get("zoom", []),
    }
```

### 3.4 MODIFICAR — `consulta_v2/cuantificar/validador.py`

🔴 **V1 — la ruta es `cuantificar/validador.py`, no `consulta_v2/validador.py`.** Ruta absoluta:
`C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\cuantificar\validador.py`

Orden real de las ramas de `formatear_cuerpo` (verificado): N3 (:37), N4 (:46), N1D (:62),
N1DSER (:71), N1DSEL (:81), y en **:90** el comentario
`# N1/N2 (usan resultado/referencia — solo aquí, ya descartados N3/N4)` seguido de
`real = fmt_valor(res["resultado"]["valor"], prod)`.

Inserta el bloque de abajo **después del `return linea` de la rama N1DSEL (:88) y antes del
comentario de :90**. Ahí es donde todavía no se ha leído `res["resultado"]` (V5).

```python
    # [2026-09-03 · COMPARACION-PERIODOS] VA ANTES de N1/N2 por la misma razón que N3/N4 (HE6):
    # su contrato NO trae `resultado` ni `mes` — leerlos abajo reventaría con KeyError.
    if nivel == "NCMP":
        a, b = res["a"], res["b"]
        subio = res["delta"] >= 0
        pct = f" ({'+' if subio else '-'}{abs(res['pct'])}%)" if res.get("pct") is not None else ""
        linea = (f"{res['entidad_cualificada']} produjo {fmt_valor(a['real'], prod)} {unidad} de "
                 f"{prod} en {a['periodo']} frente a {fmt_valor(b['real'], prod)} {unidad} en "
                 f"{b['periodo']}: {'subió' if subio else 'bajó'} "
                 f"{fmt_valor(abs(res['delta']), prod)} {unidad}{pct} ({res['clase_label']}).")
        # El cumplimiento de CADA lado contra SU propio presupuesto. Cruzarlos (REAL de julio vs
        # PPTO de mayo) es el error fácil de esta pantalla y no significa nada.
        if res.get("cumpl_a") is not None and res.get("cumpl_b") is not None:
            linea += (f" Contra su propio presupuesto: {res['cumpl_a']}% en {a['periodo']} y "
                      f"{res['cumpl_b']}% en {b['periodo']}.")
        for x in res.get("avisos", []):
            linea += f" ⚠️ {x}"
        return linea

    if nivel == "N3P":
        n = len(res["puntos"])
        cm = res.get("cumpl_medio")
        linea = (f"{res['entidad_cualificada']}, {prod} contra el programa en {res['anio']}: "
                 f"{n} mes{'es' if n != 1 else ''} con dato")
        linea += (f", cumplimiento medio {cm}%." if cm is not None
                  else ", sin presupuesto cargado para calcular cumplimiento.")
        if res.get("meses_bajo_meta"):
            k = res["meses_bajo_meta"]
            linea += (f" {k} mes{'es' if k != 1 else ''} por debajo de la meta. ")
        linea += " El detalle mes a mes está en la gráfica."
        for x in res.get("avisos", []):
            linea += f" ⚠️ {x}"
        return linea
```

### 3.5 MODIFICAR — `consulta_v2/respuesta_cuantificar.py`

**(a)** En `_PANEL_TIPO` (:55), añade las dos entradas:

```python
_PANEL_TIPO = {"N3": "cuant_serie", "N4": "cuant_var",
              "N1D": "cuant_dia_panel", "N1DSEL": "cuant_dia_panel",
              "N1DSER": "cuant_dia_panel",
              "N2": "cuant_acum",
              # [2026-09-03 · COMPARACION-PERIODOS] NCMP = barras agrupadas de los dos periodos;
              # N3P = la curva mensual con la línea del programa encima.
              "NCMP": "cuant_cmp", "N3P": "cuant_serie_ppto"}   # N1 -> "cuant_kpi" (Fase 3)
```

**(b)** En `_panel_datos` (:110), añade **antes** de `elif nivel == "N3":`:

```python
    # [2026-09-03 · COMPARACION-PERIODOS] Contratos propios (HE6): NCMP no tiene `resultado`
    # ni `mes`, y N3P no tiene `serie`. Se emiten sus claves y ninguna sintética.
    elif nivel == "NCMP":
        d.update({"a": res["a"], "b": res["b"], "delta": res["delta"], "pct": res.get("pct"),
                  "cumpl_a": res.get("cumpl_a"), "cumpl_b": res.get("cumpl_b"),
                  "clase": res.get("clase"), "clase_label": res.get("clase_label")})
    elif nivel == "N3P":
        d.update({"puntos": res["puntos"], "anio": res["anio"],
                  "cumpl_medio": res.get("cumpl_medio"),
                  "meses_bajo_meta": res.get("meses_bajo_meta")})
```

**(c)** El bloque del `cierre` son 4 asignaciones encadenadas en `respuesta_cuantificar.py:365-371`
(V6). La línea exacta a localizar es la de N2:

```python
    elif res.get("nivel") == "N2":
        cierre = "¿Quieres el detalle de un mes puntual?"      # <- :369
    else:
        cierre = _CIERRE   # HE3
```

Inserta las dos ramas nuevas **entre esa de N2 y el `else`**:

```python
    elif res.get("nivel") == "NCMP":
        cierre = "¿Quieres el detalle de uno de los dos meses?"
    elif res.get("nivel") == "N3P":
        cierre = "¿Quieres el detalle de un mes puntual?"
```

### 3.6 MODIFICAR — `frontend/static/js/multitab_shell.js` · panel de comparación

Añade los constructores y pintores **justo después** de `__cnAcumMesInto` (termina ~:4516):

```js
  // [2026-09-03 · COMPARACION-PERIODOS] NCMP: dos periodos, barras agrupadas Real vs PPTO.
  // Molde = __cnAcumMesInto (:4452). Barras y no líneas: son DOS puntos, y una línea entre dos
  // puntos sugiere una evolución continua que no existe — mayo y julio no son consecutivos.
  function __cnCuantCmpHtml(d) {
    if (!d || !d.a || !d.b) return "";
    return __cnPanelMesHtml(d, "cn-cmp-mes");
  }

  function __cnCmpMesInto(hostEl, d) {
    var a = d.a || {}, b = d.b || {};
    var prod = String(d.producto || "");
    var unidad = d.unidad || "bbl";
    var nombre = prod.charAt(0).toUpperCase() + prod.slice(1).toLowerCase();
    hostEl.innerHTML =
      '<div class="cn-ins__card"><div class="cn-ins__card-hd"><i class="bi bi-bar-chart-line"></i> ' +
      esc(nombre) + ' · ' + esc(String(a.periodo || "")) + ' vs ' + esc(String(b.periodo || "")) +
      '</div><div class="cn-ins__plot" data-p></div>' +
      '<div class="cn-ins__cap" data-cap></div></div>';
    var elp = hostEl.querySelector("[data-p]");
    if (!window.Plotly) { elp.innerHTML = '<div class="text-muted small p-2">(Plotly no disponible)</div>'; return; }
    // El gas se grafica en MSCF (÷1e6) y el hover formatea el valor ORIGINAL con __cnGasM (que
    // ya divide) — nunca el ya escalado: ese doble escalado es el bug documentado en :3650-3652.
    var esGas = String(prod).toUpperCase() === "GAS";
    var fmtD = esGas ? __cnGasM : function (v) { return __cnMilesEC(Math.round(v)); };
    var esc1 = function (v) { return (v == null) ? null : (esGas ? v / 1e6 : v); };
    var col = __cnProdCol(prod);
    // Orden B → A: se lee de izquierda a derecha como "de dónde venía" → "dónde está".
    var ejes = [String(b.periodo || ""), String(a.periodo || "")];
    var reales = [b.real, a.real], pptos = [b.ppto, a.ppto];
    var traces = [{
      x: ejes, y: reales.map(esc1), name: "Real", type: "bar",
      marker: { color: col },
      customdata: reales.map(fmtD),
      hovertemplate: "%{x}<br>Real: %{customdata} " + unidad + "<extra></extra>"
    }];
    // Cada periodo contra SU propio presupuesto. Si ninguno tiene meta, no se dibuja la serie:
    // barras a cero afirmarían que el presupuesto es cero, que no es lo mismo que no haberlo.
    if (pptos.some(function (v) { return v; })) {
      traces.push({
        x: ejes, y: pptos.map(esc1), name: "Presupuesto", type: "bar",
        marker: { color: "#c8d2cb" },
        customdata: pptos.map(function (v) { return v ? fmtD(v) : "—"; }),
        hovertemplate: "%{x}<br>PPTO: %{customdata} " + unidad + "<extra></extra>"
      });
    }
    window.Plotly.newPlot(elp, traces, {
      barmode: "group", margin: { l: 62, r: 18, t: 22, b: 30 }, height: 260,
      hovermode: "x unified", showlegend: true,
      legend: { orientation: "h", y: -0.18, x: 0, font: { size: 11 } },
      xaxis: { tickfont: { size: 11 }, showgrid: false },
      yaxis: {
        title: { text: "Producción (" + (esGas ? "MSCF" : unidad) + ")", font: { size: 11 } },
        tickfont: { size: 10 }, rangemode: "tozero", separatethousands: true,
        gridcolor: "#eef1ef", zeroline: false
      },
      plot_bgcolor: "#fff", paper_bgcolor: "#fff"
    }, { displayModeBar: false, responsive: true });
  }

  // [2026-09-03 · COMPARACION-PERIODOS] N3P: la serie mensual REAL con la línea del PROGRAMA.
  function __cnCuantSeriePptoHtml(d) {
    if (!d || !d.puntos || !d.puntos.length) return "";
    return __cnPanelMesHtml(d, "cn-seriep-mes");
  }

  function __cnSeriePptoInto(hostEl, d) {
    var pts = d.puntos || [];
    var prod = String(d.producto || "");
    var unidad = d.unidad || "bbl";
    var nombre = prod.charAt(0).toUpperCase() + prod.slice(1).toLowerCase();
    hostEl.innerHTML =
      '<div class="cn-ins__card"><div class="cn-ins__card-hd"><i class="bi bi-graph-up"></i> ' +
      esc(nombre) + ' · real vs programa ' + (d.anio || "") +
      '</div><div class="cn-ins__plot" data-p></div>' +
      '<div class="cn-ins__cap" data-cap></div></div>';
    var elp = hostEl.querySelector("[data-p]");
    if (!pts.length) {
      elp.innerHTML = '<div class="p-2 text-muted small">Sin serie mensual para este producto.</div>';
      return;
    }
    if (!window.Plotly) { elp.innerHTML = '<div class="text-muted small p-2">(Plotly no disponible)</div>'; return; }
    var esGas = String(prod).toUpperCase() === "GAS";
    var fmtD = esGas ? __cnGasM : function (v) { return __cnMilesEC(Math.round(v)); };
    var esc1 = function (v) { return (v == null) ? null : (esGas ? v / 1e6 : v); };
    var col = __cnProdCol(prod);
    var meses = pts.map(function (p) { return p.mes; });
    var traces = [{
      x: meses, y: pts.map(function (p) { return esc1(p.real); }),
      name: "Real", type: "scatter", mode: "lines+markers",
      line: { color: col, width: 2.5, shape: "spline", smoothing: 0.8 },
      marker: { color: col, size: 7 },
      customdata: pts.map(function (p) { return fmtD(p.real); }),
      hovertemplate: "%{x}<br>Real: %{customdata} " + unidad + "<extra></extra>"
    }];
    // `connectgaps:false`: un mes sin presupuesto deja hueco. Unirlo dibujaría una meta que
    // nadie cargó, justo entre los dos meses que sí la tienen.
    if (pts.some(function (p) { return p.ppto != null; })) {
      traces.push({
        x: meses, y: pts.map(function (p) { return esc1(p.ppto); }),
        name: "Programa", type: "scatter", mode: "lines+markers", connectgaps: false,
        line: { color: "#8a978f", width: 2, dash: "dot" },
        marker: { color: "#8a978f", size: 5 },
        customdata: pts.map(function (p) { return p.ppto == null ? "—" : fmtD(p.ppto); }),
        hovertemplate: "%{x}<br>Programa: %{customdata} " + unidad + "<extra></extra>"
      });
    }
    window.Plotly.newPlot(elp, traces, {
      margin: { l: 62, r: 18, t: 22, b: 30 }, height: 260, hovermode: "x unified",
      showlegend: true, legend: { orientation: "h", y: -0.18, x: 0, font: { size: 11 } },
      xaxis: { title: { text: "Mes", font: { size: 11 } }, tickfont: { size: 11 }, showgrid: false },
      yaxis: {
        title: { text: "Producción (" + (esGas ? "MSCF" : unidad) + ")", font: { size: 11 } },
        tickfont: { size: 10 }, rangemode: "tozero", separatethousands: true,
        gridcolor: "#eef1ef", zeroline: false
      },
      plot_bgcolor: "#fff", paper_bgcolor: "#fff"
    }, { displayModeBar: false, responsive: true });
  }
```

**Registra los DOS tipos en los TRES sitios** (P12). Son 6 ediciones, no 2.

1. En `__cnPintarPanelCuant`, **antes** del fallback `: __cnCuantCardHtml(d)`:

```js
             : (panel.tipo === "cuant_cmp")        ? __cnCuantCmpHtml(d)
             : (panel.tipo === "cuant_serie_ppto") ? __cnCuantSeriePptoHtml(d)
```

2. En la línea de `__cnPanelMesCargar` (~:4381):

```js
    if (panel.tipo === "cuant_serie" || panel.tipo === "cuant_var" || panel.tipo === "cuant_acum" || panel.tipo === "cuant_cmp" || panel.tipo === "cuant_serie_ppto") __cnPanelMesCargar(blk, d, panel.tipo);
```

3. En `__cnPanelMesPintar`, las dos ramas finales:

```js
    } else if (tipo === "cuant_cmp") {
      var hc = blk.querySelector(".cn-cmp-mes");
      if (hc) __cnCmpMesInto(hc, d);
    } else if (tipo === "cuant_serie_ppto") {
      var hp = blk.querySelector(".cn-seriep-mes");
      if (hp) __cnSeriePptoInto(hp, d);
    }
```

### 3.7 AÑADIR — `backend/backend/tests/test_slots_comparacion.py`

```python
"""test_slots_comparacion.py — comparación de periodos (punto 3, tipo 2) y serie vs programa
(tipo 3). Módulo PURO: ningún test toca BD; el techo se pasa a mano.
"""
import datetime

import pytest

from app.features.consulta_v2.cuantificar.slots import (
    detectar_comparacion, extraer_slots, menciona_dia, TECHO_CENTINELA,
)

_TECHO = datetime.date(2026, 8, 30)      # último día con reporte en Pruebas


# ---------------- formas que SÍ resuelven ----------------

@pytest.mark.parametrize("frase,ma,aa,mb,ab,clase", [
    ("produccion de Castilla en julio vs mayo", 7, 2026, 5, 2026, "meses"),
    ("compara julio con mayo en Castilla", 7, 2026, 5, 2026, "meses"),
    ("Castilla julio contra mayo", 7, 2026, 5, 2026, "meses"),
    ("Castilla julio frente a mayo", 7, 2026, 5, 2026, "meses"),
    ("Castilla julio 2026 vs julio 2025", 7, 2026, 7, 2025, "yoy"),
    ("produccion de Castilla en julio vs el ano pasado", 7, 2026, 7, 2025, "yoy"),
    ("produccion de Castilla en julio vs el mes pasado", 7, 2026, 6, 2026, "mom"),
])
def test_comparacion_resuelve(frase, ma, aa, mb, ab, clase):
    r = detectar_comparacion(frase, _TECHO)
    assert r is not None, frase
    assert (r["mes_a"], r["anio_a"]) == (ma, aa)
    assert (r["mes_b"], r["anio_b"]) == (mb, ab)
    assert r["clase"] == clase


def test_sin_mes_a_la_izquierda_ancla_en_el_techo_y_lo_declara():
    """«¿cómo vamos vs el año pasado?» = el mes del techo contra su gemelo. Se DECLARA."""
    r = detectar_comparacion("como vamos vs el ano pasado", _TECHO)
    assert (r["mes_a"], r["anio_a"]) == (8, 2026)
    assert (r["mes_b"], r["anio_b"]) == (8, 2025)
    assert any("mes del ultimo reporte" in a or "último reporte" in a for a in r["asumido"])


def test_enero_vs_mes_pasado_cruza_a_diciembre_del_ano_anterior():
    r = detectar_comparacion("produccion en enero vs el mes pasado", _TECHO)
    assert (r["mes_b"], r["anio_b"]) == (12, 2025)


# ---------------- 🔴 P4: la REFERENCIA no se toca ----------------

@pytest.mark.parametrize("frase", [
    "como va Castilla vs el promedio",
    "como va Castilla contra el promedio",
    "produccion de Castilla respecto al promedio",
    "como va Castilla vs el presupuesto",
    "Castilla frente a la meta",
    "Castilla vs el P50",
])
def test_referencia_no_es_comparacion_de_periodos(frase):
    """Estas ya resuelven a N1 con su referencia y hoy responden bien. Robárselas sería una
    regresión introducida por este plan."""
    assert detectar_comparacion(frase, _TECHO) is None, frase


def test_dos_meses_mas_referencia_si_es_comparacion():
    """«julio vs junio contra el presupuesto» tiene las dos cosas: la guarda mira lo que sigue
    al conector, no si la palabra aparece suelta en la frase."""
    r = detectar_comparacion("Castilla julio vs junio contra el presupuesto", _TECHO)
    assert r is not None and r["mes_a"] == 7 and r["mes_b"] == 6


# ---------------- formas que NO resuelven ----------------

def test_sin_conector_no_hay_comparacion():
    assert detectar_comparacion("produccion de Castilla en julio", _TECHO) is None


def test_conector_sin_segundo_periodo_no_resuelve():
    assert detectar_comparacion("Castilla julio vs Rubiales", _TECHO) is None


def test_mismo_periodo_no_se_compara():
    assert detectar_comparacion("Castilla julio 2026 vs julio 2026", _TECHO) is None


def test_sin_techo_no_hay_comparacion():
    """Sin ancla no se inventa el año: rechazo honesto (misma regla que detectar_ventana)."""
    assert detectar_comparacion("Castilla julio vs mayo", None) is None


# ---------------- integración con extraer_slots ----------------

def test_extraer_slots_eleva_a_ncmp():
    s = extraer_slots("produccion de Castilla en julio vs mayo", techo=_TECHO)
    assert s["nivel_temporal"] == "NCMP"
    assert s["comparacion"]["mes_a"] == 7 and s["comparacion"]["mes_b"] == 5


def test_la_ruta_real_pide_el_techo():
    """🔴 Sin esta rama en menciona_dia, detectar_comparacion recibiría techo=None en
    producción y devolvería None SIEMPRE: funcionaría en los tests y no en la app."""
    assert menciona_dia("produccion de Castilla en julio vs mayo") is True


def test_un_mes_solo_sigue_en_n1():
    s = extraer_slots("produccion de Castilla en julio", techo=_TECHO)
    assert s["nivel_temporal"] == "N1"
    assert s["comparacion"] is None


# ---------------- 🔴 P8: N3P exige LAS DOS señales ----------------

def test_serie_sola_sigue_siendo_n3():
    s = extraer_slots("produccion de Castilla mes a mes", techo=_TECHO)
    assert s["nivel_temporal"] == "N3"


def test_serie_mas_programa_es_n3p():
    s = extraer_slots("produccion de Castilla mes a mes vs el presupuesto", techo=_TECHO)
    assert s["nivel_temporal"] == "N3P"


def test_programa_solo_sigue_en_n1():
    """«vs el presupuesto» sin señal de serie es la pregunta N1 de siempre."""
    s = extraer_slots("como va Castilla vs el presupuesto", techo=_TECHO)
    assert s["nivel_temporal"] == "N1"


def test_ventana_sola_no_se_convierte_en_comparacion():
    """No-regresión del punto 1: la ventana móvil sigue elevando a N2."""
    s = extraer_slots("produccion de Castilla en los ultimos 3 meses", techo=_TECHO)
    assert s["nivel_temporal"] == "N2"
```

### 3.8 AÑADIR — `backend/backend/tests/test_cuantificar_comparacion.py`

```python
"""test_cuantificar_comparacion.py — ejecutores NCMP y N3P con `desempeno` inyectado.
Ningún test toca BD: `_desempeno_fn` es un doble.
"""
import datetime

import pytest

from app.features.consulta_v2.cuantificar import ejecutor as _ej
from app.features.consulta_v2.cuantificar.slots import extraer_slots
# 🔴 V1 — `validador` vive DENTRO de `cuantificar/`. El import por `consulta_v2.validador` no
# resuelve: es el mismo camino que usa respuesta_cuantificar.py:26.
from app.features.consulta_v2.cuantificar import validador as _val

_TECHO = datetime.date(2026, 8, 30)
_RESUELTA = {"valor": "CASTILLA", "nivel": "campo", "rama": "A"}
_MESN = {1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
         7: "Julio", 8: "Agosto"}


def _fake(por_periodo, ultimo=8, aplica_diario=True):
    """`por_periodo` = {"julio 2026": (real, ppto, cerrado), ...}. Un periodo ausente devuelve
    sin_cierre, que es como se comporta `desempeno` cuando no hay fila mensual.

    `aplica_diario` replica lo que `_ambito` (api.py:438) pone en la respuesta: False cuando la
    entidad no tiene filas en la tabla DIARIA — el caso de un mes histórico con cierre mensual
    pero sin reporte día a día (V2)."""
    def _fn(entidad=None, segmento="ecp", nivel=None, periodo=None):
        if periodo is None:
            return {"encontrada": True, "aplica_diario": aplica_diario,
                    "por_producto": [{"producto": "CRUDO", "real": 1, "ppto": 1}],
                    "mes": {"anio": 2026, "mes": ultimo, "nombre": _MESN[ultimo],
                            "completo": False, "cerrado": False,
                            "dias_con_data": 30, "dias_del_mes": 31}}
        key = periodo.lower()
        if key not in por_periodo:
            return {"encontrada": True, "sin_cierre": True}
        real, ppto, cerrado = por_periodo[key]
        num = next((n for n, s in _MESN.items() if s.lower() in key), 1)
        return {"encontrada": True, "aplica_diario": aplica_diario,
                "por_producto": [{"producto": "CRUDO", "real": real, "ppto": ppto}],
                "mes": {"anio": 2026, "mes": num, "nombre": _MESN[num],
                        "completo": cerrado, "cerrado": cerrado,
                        "dias_con_data": (30 if cerrado else 17) if aplica_diario else 0,
                        "dias_del_mes": 31}}
    return _fn


# ---------------- NCMP ----------------

def test_ncmp_calcula_delta_y_pct():
    s = extraer_slots("produccion de Castilla en julio vs mayo", techo=_TECHO)
    r = _ej.ejecutar(_RESUELTA, s, _desempeno_fn=_fake(
        {"julio 2026": (1100.0, 1000.0, True), "mayo 2026": (1000.0, 1000.0, True)}))
    assert r["aplica"] and r["nivel"] == "NCMP"
    assert r["delta"] == pytest.approx(100.0)
    assert r["pct"] == pytest.approx(10.0)
    assert r["cumpl_a"] == pytest.approx(110.0) and r["cumpl_b"] == pytest.approx(100.0)


def test_ncmp_declara_el_mes_en_curso():
    """HE4: comparar un mes en curso contra uno cerrado no es ilegítimo, pero callarlo sí."""
    s = extraer_slots("produccion de Castilla en agosto vs mayo", techo=_TECHO)
    r = _ej.ejecutar(_RESUELTA, s, _desempeno_fn=_fake(
        {"agosto 2026": (900.0, 1000.0, False), "mayo 2026": (1000.0, 1000.0, True)}))
    assert any("sigue en curso" in a for a in r["avisos"])


def test_ncmp_sin_reporte_diario_no_habla_de_dias():
    """🔴 V2 — un mes con cierre mensual pero SIN tabla diaria tiene dias_con_data=0. El aviso
    NO puede decir «0 de 31 días» sobre una cifra definitiva: ese es el bug `completo` vs
    `cerrado` entrando por otra puerta."""
    s = extraer_slots("produccion de Castilla en agosto vs mayo", techo=_TECHO)
    r = _ej.ejecutar(_RESUELTA, s, _desempeno_fn=_fake(
        {"agosto 2026": (900.0, 1000.0, False), "mayo 2026": (1000.0, 1000.0, True)},
        aplica_diario=False))
    assert any("provisional" in a for a in r["avisos"])
    assert not any("0/31" in a or "0 de 31" in a for a in r["avisos"])


def test_ncmp_sin_cierre_en_un_lado_declina():
    s = extraer_slots("produccion de Castilla en julio vs marzo", techo=_TECHO)
    r = _ej.ejecutar(_RESUELTA, s, _desempeno_fn=_fake({"julio 2026": (1100.0, 1000.0, True)}))
    assert r["aplica"] is False and "marzo" in r["texto"]


def test_ncmp_con_ventana_declina_honesto():
    """P9: comparación + ventana a la vez no está soportada; se declina, no se resuelve a medias."""
    s = extraer_slots("produccion de Castilla en julio vs mayo", techo=_TECHO)
    s["ventana"] = {"unidad": "mes", "cantidad": 3, "ini": "2026-06-01", "fin": "2026-08-30"}
    r = _ej.ejecutar(_RESUELTA, s, _desempeno_fn=_fake({}))
    assert r["aplica"] is False and "las dos cosas a la vez" in r["texto"]


def test_ncmp_cuerpo_no_revienta_sin_resultado_ni_mes():
    """HE6: el contrato de NCMP no trae `resultado` ni `mes`. Si el validador los leyera antes
    de ramificar, esto sería un KeyError."""
    s = extraer_slots("produccion de Castilla en julio vs mayo", techo=_TECHO)
    r = _ej.ejecutar(_RESUELTA, s, _desempeno_fn=_fake(
        {"julio 2026": (1100.0, 1000.0, True), "mayo 2026": (1000.0, 1000.0, True)}))
    cuerpo = _val.formatear_cuerpo(r)
    assert "julio 2026" in cuerpo and "mayo 2026" in cuerpo and "subió" in cuerpo


# ---------------- N3P ----------------

def test_n3p_serie_con_programa():
    s = extraer_slots("produccion de Castilla mes a mes vs el presupuesto", techo=_TECHO)
    r = _ej.ejecutar(_RESUELTA, s, _desempeno_fn=_fake(
        {f"{_MESN[m].lower()} 2026": (900.0 + m, 1000.0, m < 8) for m in range(1, 9)}))
    assert r["aplica"] and r["nivel"] == "N3P"
    assert len(r["puntos"]) == 8
    assert all(p["ppto"] == 1000.0 for p in r["puntos"])
    assert r["meses_bajo_meta"] == 8


def test_n3p_declara_los_meses_omitidos():
    s = extraer_slots("produccion de Castilla mes a mes vs el presupuesto", techo=_TECHO)
    r = _ej.ejecutar(_RESUELTA, s, _desempeno_fn=_fake(
        {f"{_MESN[m].lower()} 2026": (900.0, 1000.0, True) for m in (1, 2, 7, 8)}))
    assert any("marzo" in a for a in r["avisos"])


def test_n3p_cuerpo_no_revienta_sin_resultado_ni_mes():
    s = extraer_slots("produccion de Castilla mes a mes vs el presupuesto", techo=_TECHO)
    r = _ej.ejecutar(_RESUELTA, s, _desempeno_fn=_fake(
        {f"{_MESN[m].lower()} 2026": (900.0, 1000.0, True) for m in range(1, 9)}))
    cuerpo = _val.formatear_cuerpo(r)
    assert "programa" in cuerpo.lower() and "2026" in cuerpo
```

### 3.9 MODIFICAR — `frontend/MainChat/templates/mainchat_layout.html`

Línea 317 (P11). **Lee primero el valor real** — depende de si el punto 2 ya se ejecutó (P10):

- si dice `?v=20260903f` → ponlo en `?v=20260903g`
- si dice `?v=20260903g` → ponlo en `?v=20260903h`

---

## 4. Orden de ejecución

| # | Acción | Archivo |
|---|---|---|
| 1 | Detector de comparación + `_RX_PROGRAMA` + elevación + `menciona_dia` | `cuantificar/slots.py` (§3.1) |
| 2 | `comparacion()` y `serie_programa()` | `cuantificar/niveles.py` (§3.2) |
| 3 | Despacho + `ejecutar_ncmp` + `ejecutar_n3p` | `cuantificar/ejecutor.py` (§3.3) |
| 4 | Cuerpo de texto de los dos niveles | `consulta_v2/**cuantificar**/validador.py` (§3.4 · V1) |
| 5 | `_PANEL_TIPO`, `_panel_datos`, cierres | `consulta_v2/respuesta_cuantificar.py` (§3.5) |
| 6 | Tests del detector | `tests/test_slots_comparacion.py` (§3.7) |
| 7 | Tests de los ejecutores | `tests/test_cuantificar_comparacion.py` (§3.8) |
| 8 | **Validar backend** (§6.1, filas 1-4) | — |
| 9 | Paneles: 2 constructores, 2 pintores, **6 registros** | `frontend/static/js/multitab_shell.js` (§3.6) |
| 10 | Cache-buster (lee el valor actual antes) | `frontend/MainChat/templates/mainchat_layout.html` (§3.9) |
| 11 | DOS commits separados, backend y frontend | — |

**Si el paso 8 falla, DETENTE.** No sigas al frontend ni commitees.

---

## 5. Reglas no negociables

1. **CERO modificaciones fuera de este plan.** Si crees que falta algo, DETENTE y repórtalo.
2. **`slots.py` sigue PURO**: sin imports de BD, sin `date.today()`. El techo entra por parámetro.
3. **NO tocar `_periodo_texto`** (P1). Lo consumen N1/N2/N3/N4 y `respuesta_analizar`.
4. **NO tocar `no_soportado.py`** (P3). El rechazo del año completo es correcto y se conserva.
5. **NO tocar `comparativo_mes`** en `analisis/api.py` (P6): alimenta el bloque de iniciativa.
6. **La guarda `_RX_CMP_NO` es obligatoria** (P4). Sin ella, «vs el promedio» deja de funcionar.
   Hay 6 tests que lo fijan.
7. **N3P exige LAS DOS señales** (P8): serie **Y** programa. Nunca una sola.
8. **Los 4 argumentos de `desempeno` van SIEMPRE explícitos**: `entidad=`, `segmento=`, `nivel=`,
   `periodo=`. Nunca posicionales, nunca omitidos (defaults `Query(...)`, CLAUDE.md §7).
9. **NCMP y N3P van ANTES de N1/N2 en `cuantificar/validador.formatear_cuerpo`** (HE6): sus
   contratos no tienen `resultado` ni `mes`, y leerlos revienta con `KeyError`. **El archivo es
   `consulta_v2/cuantificar/validador.py`**, no `consulta_v2/validador.py` (V1).
14. **Nunca pases la frase del usuario a `desempeno(periodo=...)`** (V3): `_parse_periodo` casa el
    mes por SUBSTRING (`api.py:390`), así que «el día de MAYOR producción» resolvería mayo. Solo
    periodos ya construidos por el motor («julio 2025»).
15. **El aviso de días solo si `diario_disponible`** (V2). Un mes con cierre mensual y sin tabla
    diaria no se describe con «0 de 31 días».
10. **6 registros de panel, no 2** (P12): dos tipos × tres sitios.
11. **El cache-buster sube en el mismo commit que el JS** (P11).
12. **Dos commits**, uno por repo. Nunca uno solo.
13. Si un ajuste reactivo se acumula **más de 2 iteraciones** sin resolver, DETENTE y reporta.

---

## 6. Validación

### 6.1 Estática — la corres tú, EXECUTOR

Desde `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend`, PowerShell normal, línea por línea:

| # | Comando | Resultado esperado |
|---|---|---|
| 1 | `uv run pytest tests/test_slots_comparacion.py -q` | **27 passed** (7+6 parametrizados + 14 sueltos) |
| 2 | `uv run pytest tests/test_cuantificar_comparacion.py -q` | **9 passed** |
| 3 | `uv run pytest -q` | **822 passed, 10 failed** — la suite estaba en 786; los 10 son preexistentes (lista abajo) |
| 4 | `uv run python -c "import inspect; from app.features.consulta_v2.cuantificar import slots; s=inspect.getsource(slots); print('get_engine' not in s and 'date.today' not in s)"` | `True` — `slots.py` sigue puro |

⚠️ **NO corras `run_golden.py`** (clasificación, 92 casos): puede escalar a Capa 2 (Ollama) y en una
máquina sin Ollama devuelve un resultado engañoso. Va en §6.2.

**Los 10 fallos preexistentes**, que ya fallaban antes de este plan y NO son tuyos:

```
test_analisis_tarjetas_kpi.py::test_foco_por_promedio_cuando_no_hay_ppto
test_analisis_tarjetas_kpi.py::test_sin_tarjetas_no_genera_focos_de_promedio
test_consulta_v2_clasificador.py::test_escalada_fallback_conserva_regex
test_conteo_jerarquia.py::test_r1_no_secuestra_analizar
test_conteo_jerarquia.py::test_r3_cuerpo_pinta_pozos
test_conteo_jerarquia.py::test_r3_degrada_si_ops_no_esta
test_cuantificar_ranking.py::test_bd_real_top5_campos_crudo
test_cuantificar_ranking.py::test_bd_real_bottom5_campos_crudo
test_cuantificar_ranking.py::test_bd_real_gap_bottom_faltante_ordenado
test_jerarquizar_ranking.py::test_bd_real_campos_con_mas_pozos
```

Si aparece **cualquier otro**, es tuyo: DETENTE y repórtalo. Si dudas de si uno es preexistente,
compruébalo con `git stash -u` → correr → `git stash pop`.

### 6.2 Humana — la corre el USUARIO, no tú (regla R3)

**No marques ✅ ninguna feature visual.** Tú no tienes navegador. El estado que reportas es
«implementado, PENDIENTE de validación humana».

En el servidor de pruebas, tras `git pull` en los dos repos, reiniciar Flask e INGESTA y
**Ctrl+Shift+R**:

| # | Escribe en el chat | Esperado |
|---|---|---|
| 1 | «¿Cuánto produjo Castilla en julio vs mayo?» | Las dos cifras, el delta y el %, cada una contra SU presupuesto + barras agrupadas. **Antes: solo mayo** |
| 2 | «Compara julio con junio en Castilla» | Igual, clase «entre meses» |
| 3 | «¿Cuánto produjo Castilla en julio vs el mes pasado?» | julio vs junio, clase «contra el mes anterior» |
| 4 | «Castilla julio 2026 vs julio 2025» | **Interanual.** Si no hay datos de 2025, un rechazo honesto nombrando el periodo que falta — nunca una cifra inventada |
| 5 | «¿Cuánto produjo Castilla en agosto vs mayo?» | Aviso de que agosto sigue en curso (30/31 días) |
| 6 | «Producción de Castilla mes a mes vs el presupuesto» | Curva REAL + línea punteada de programa, cumplimiento medio y meses bajo meta |
| 7 | «¿Cómo va Castilla vs el promedio?» | El KPI con referencia promedio — **no debe cambiar** (P4) |
| 8 | «¿Cómo va Castilla vs el presupuesto?» | El KPI de siempre — **no debe cambiar** (P4) |
| 9 | «Producción de Castilla mes a mes» | La curva N3 de siempre — **no debe cambiar** (P8) |
| 10 | «¿Cuánto produjo Castilla en los últimos 3 meses?» | El acumulado del punto 1 — **no debe cambiar** |
| 11 | «¿Cuánto produjo Castilla en el año 2025?» | El rechazo honesto de siempre — **no debe cambiar** (P3) |
| 12 | F12 → Console en todas | 0 errores |

Los casos **7 a 11 son el control de no-regresión**: si alguno cambia, algo se pisó.

Y el gate del clasificador, en el servidor de pruebas:

```powershell
$env:PYTHONPATH="."; uv run python app/features/consulta_v2/golden/run_golden.py
```

Esperado: **≥90%** (hoy 96%).

---

## 7. Fuera de alcance

- **Punto 4** — quiebre temporal y racha/desde-cuándo. Plan aparte.
- **YoY de AÑO COMPLETO** («2026 vs 2025»). Exige agregar 12 meses de dos años y hoy
  `no_soportado.py` lo rechaza honestamente (P3). Ese rechazo se conserva: mejor un «no puedo» que
  una cifra fabricada.
- **DoD (día vs día).** El grano día tiene sus propios niveles (N1D/N1DSEL/N1DSER) y la comparación
  ahí es un plan en sí mismo. Hoy «el 5 de julio vs el 6» resuelve a N1D del primer día — un fallo
  silencioso conocido que este plan **no** cierra y que hay que anotar como deuda.
- **Comparar más de dos periodos** («enero vs febrero vs marzo»). Eso es la serie N3.
- **Comparación + ventana simultáneas** («los últimos 3 meses vs los 3 anteriores»). Se DECLINA con
  rechazo honesto (§3.3), no se resuelve a medias (P9).
- **Comparar dos ENTIDADES** («Castilla vs Rubiales»). Es otra dimensión —jerarquía, no tiempo— y no
  pertenece a inteligencia de tiempo. `detectar_comparacion` devuelve None ahí (hay test).
- **Tocar N3/N4.** N3P es un nivel nuevo; N3 se queda exactamente como está.
- El hueco de reporte diario de mayo (17/31) y junio (14/30) en Pruebas: es de ingesta, no de código.

---

> **Supuestos declarados** (las dos preguntas que quedaron abiertas al auditar):
> 1. **No sé si hay datos de 2025 en la BD.** Por eso el YoY **no depende** de que los haya: si
>    `desempeno(periodo="julio 2025")` vuelve sin cierre, `comparacion()` declina nombrando el
>    periodo que falta (§3.2). El caso 4 de §6.2 lo comprueba en vivo. Si resulta que no hay
>    histórico, la funcionalidad queda inerte pero **nunca miente** — y se activa sola el día que
>    se cargue 2025.
> 2. **Va un solo plan** con los tipos 2 y 3, porque comparten el detector, el ejecutor y el
>    fichero de tests. El orden de §4 permite parar limpio tras el paso 8 si algo se tuerce.
