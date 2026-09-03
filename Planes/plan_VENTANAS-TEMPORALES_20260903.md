# plan_VENTANAS-TEMPORALES_20260903

**ID_TAREA:** `VENTANAS-TEMPORALES`
**Fecha:** 2026-09-03
**Rol del lector:** agente EXECUTOR
**Alcance:** UN solo archivo de producción (`slots.py`) + UN archivo de tests nuevo.

> **Verificación v2 (2026-09-03, segunda pasada):** el plan se auditó contra el código real
> aplicando el regex y la lógica de `detectar_ventana`, no razonándolos. **Todo lo esencial
> quedó confirmado midiendo:**
> - ✅ El regex `_RX_VENTANA` acierta 11/11 casos (7 que resuelven + 4 que rechazan), incluidos
>   «los últimos dos mil días» → None y «los últimos datos/reportes» → None (el `[A-Z]+` no
>   captura ruido sin unidad temporal detrás).
> - ✅ El cálculo de fechas coincide con TODOS los `assert` de §3.5: 30 días = [07-25, 08-23]
>   (30 contados), 3 meses = junio-01, cruce de año = 2025-12-01. El error de poste está bien
>   resuelto con `-1`.
> - ✅ **La regresión central está descartada por medición:** NINGUNA de las 11 frases de los
>   otros niveles (N1/N2/N3/N4/día/mes pasado) matchea `_RX_VENTANA`. La ventana es aditiva de
>   verdad, no puede robar preguntas.
> - ✅ H1 confirmado end-to-end: «mes pasado» resuelve en `slots.py:359` **y** `api.py:385-389`.
> - ✅ Imports ya presentes: `import datetime as _dt` (:13) y `import re` (:14). El código nuevo
>   los usa sin declararlos — no hay que añadir ninguno.
> - 🟡 **Hallazgo menor añadido (N1):** «el último día» NO lo captura `detectar_dia` (da None),
>   así que este plan lo resolvería como ventana de 1 día. Es coherente, pero conviene que el
>   executor lo sepa: no es una colisión, es cobertura nueva legítima.
>
> **Conclusión: el plan es correcto y seguro. Ejecutable tal como está, con los ajustes
> menores de referencias de línea de abajo.**

---

## 0. Contexto para el agente EXECUTOR

### 0.1 Proyecto

ProdIA. Backend FastAPI (repo `ProdIABack`) que resuelve preguntas en lenguaje natural sobre
producción de hidrocarburos. El componente relevante es el **Motor Q v2**, que clasifica cada
pregunta en 4 grupos (Cuantificar / Jerarquizar / Analizar / OUT) y luego aterriza "slots"
(mes, producto, nivel temporal, referencia) de forma **100% determinista, sin LLM**.

### 0.2 Rutas absolutas

| Qué | Ruta |
|---|---|
| Raíz del backend | `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend` |
| Archivo a MODIFICAR | `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\cuantificar\slots.py` |
| Archivo a CREAR | `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\tests\test_slots_ventana.py` |
| Tests existentes (NO tocar) | `...\backend\backend\tests\test_cuantificar.py`, `test_cuantificar_dia.py`, `test_analizar.py` |

### 0.3 Cómo se corren los comandos

**Todos los comandos de este plan se ejecutan en el servidor de PRUEBAS o en local**, en
PowerShell normal (no requiere administrador), **línea por línea**, desde la carpeta:

```powershell
cd 'C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend'
```

El entorno se gestiona con `uv`. Todo comando de Python va prefijado con `uv run`.

### 0.4 Convenciones del módulo que DEBES respetar

Estas no son sugerencias; son reglas que el archivo ya cumple y que la auditoría verificó:

1. **`slots.py` es PURO.** No consulta base de datos. Cualquier fecha de referencia entra
   como el parámetro `techo` (un `datetime.date`). **No añadas ningún import de BD, ni
   `datetime.date.today()`.** El reloj del servidor NO es la referencia: el reporte va ~100
   días atrás del día real, y usar `today()` produciría respuestas sobre fechas sin dato.
2. **Todo se compara sobre texto normalizado** por `norm()` (`app/features/consulta_v2/normaliza.py`),
   que devuelve MAYÚSCULAS sin tildes. `"año"` → `"ANO"`. Escribe tus patrones ya normalizados.
3. **Match por TOKEN (`\b...\b`), nunca por substring.** Es la regla AF-3.7. El archivo tiene
   DOS bugs históricos documentados por violarla (`"MAYO"` es substring de `"MAYOR"`, ver
   `slots.py:188-201` y `slots.py:349-357`). Un substring nuevo reintroduce esa familia de fallo.
4. **Nada se asume en silencio.** Si el resolutor rellena un dato que el usuario no dijo, lo
   declara en la lista `asumido` / `defaults_asumidos`. Este es el principio central del
   módulo — ver §5, regla NN-2.

---

## 1. Hallazgos de la auditoría

Ejecutada el 2026-09-03 sobre el código real: lectura completa de `slots.py` (452 líneas),
conteo de call sites con `grep` sobre `app/` y `tests/`, y lectura de `_parse_periodo` en
`analisis/api.py:378-394`.

### 🔴 H1 — «mes pasado» SÍ está soportado. La documentación del proyecto está equivocada.

`CLAUDE.md` §6 y `BITACORA.md` afirman: *«"mes pasado" no está soportado (cero coincidencias
en `slots.py`)»*. **Es falso.** Medido:

- `slots.py:359-360` → `if "pasado" in t or "anterior" in t: return "mes pasado"`
- `analisis/api.py:385-389` → recibe ese literal y calcula `(ref_y, ref_mo - 1)` con manejo
  correcto del cruce de año.

La cadena funciona de extremo a extremo. **Consecuencia para este plan: NO implementes
"mes pasado". Ya existe.** El paso 6 de §4 corrige la documentación.

⚠️ Lo que sí es cierto es un problema **distinto y más estrecho**: esa detección usa
`"pasado" in t` sobre texto **sin normalizar** (`_periodo_texto` hace `.lower()`, no `norm()`)
y sin `\b`. No se corrige aquí — no hay falso positivo medido y tocarlo altera una ruta viva
con tests propios (`test_analizar.py:135-137`). Queda registrado en §7.

### 🔴 H2 — La ventana relativa NO puede devolverse por `periodo_texto`. Rompería Cuantificar.

Primer diseño considerado: hacer que `_periodo_texto` devolviera `"ultimos 30 dias"`. **La
auditoría lo descarta.** `periodo_texto` se consume en 3 sitios de producción que esperan
*un nombre de mes o `None`*:

| Consumidor | Línea | Qué hace con el valor |
|---|---|---|
| `cuantificar/ejecutor.py` | 60, 112 | Lo pasa como `periodo=` al motor de desempeño |
| `cuantificar/ranking.py` | 199-200 | `if periodo_texto in _MES_NUM` → lo busca en un dict de meses |
| `respuesta_analizar.py` | 338 | Lo pasa al endpoint de análisis |

Un valor como `"ultimos 30 dias"` llegaría a `analisis/api.py:390`, no encontraría ningún mes,
devolvería `None` — y el motor **respondería el mes por defecto sin avisar**. Eso es
exactamente el bug del periodo ignorado que costó la sesión del 26-ago.

**Decisión cerrada: la ventana viaja en una CLAVE NUEVA (`ventana`), no en `periodo_texto`.**
`periodo_texto` no se toca. Los 3 consumidores siguen recibiendo lo mismo que hoy.

### 🔴 H3 — `_RX_RANGO_GUARDA` NO colisiona con «los últimos N días» (verificado midiendo).

`slots.py:139-141` contiene `\bLOS\s+\d+\s+DIAS`, que exige que el número siga **inmediatamente**
a `LOS`. En «los últimos 30 días» entre `LOS` y `30` está `ULTIMOS`, así que **NO** matchea.
Confirmado en v2 aplicando ambos patrones: «los últimos 30 días» resuelve como ventana y NO
cae al guarda.

La forma **sin «últimos»** sí la captura el guarda: «en los 30 días» → `LOS 30 DIAS` → hoy
`detectar_dia` devuelve `None` → rechazo honesto vía `no_soportado.py`. **Esa forma se deja
como está**, y la ventana solo se activa con marcador explícito (`ULTIMO`/`ULTIMA` + variantes).
Verificado: `detectar_ventana("en los 30 dias", techo)` → `None`. Ver §3, `_RX_VENTANA`.

### 🟡 H4 — La precedencia es un campo minado ya cableado. Hay UN solo lugar seguro.

`extraer_slots` (`slots.py:393-452`) resuelve el nivel en este orden exacto, y cada paso pisa
al anterior:

```
1. _nivel_temporal(texto)        → N1DSER | N4 | N3 | N2 | N1
2. override AF-4.9               → fuerza N1 si la señal de N2 fue débil
3. detectar_dia(texto, techo)    → GANA sobre todo: N1D | N1DSEL
4. if nivel == "N1DSER"          → resuelve periodo_serie_dia; si falla degrada a N1
```

Si la ventana se resolviera **antes** del paso 3, «el mejor día de los últimos 30 días» dejaría
de ser un selector de día. Si se resolviera **dentro** de `_nivel_temporal`, competiría con
N4/N3/N2 y les robaría preguntas — y esos niveles tienen tests que fallarían.

**Decisión cerrada: la ventana se resuelve DESPUÉS del paso 4, como capa aditiva que NO
modifica `nivel_temporal`.** Es un slot informativo más, igual que `referencia`. Ningún
`nivel_temporal` existente cambia de valor. Por eso este plan **no puede romper** los tests
de nivel de `test_cuantificar.py`.

### 🟡 H5 — «HASTA AHORA» y «HASTA HOY» ya están tomados por N2 (acumulado).

`_ACUM_KW_FUERTE` (`slots.py:27`) incluye `"HASTA AHORA"`, y `_RX_ACUM_GUARDA` (`slots.py:130-131`)
incluye `HASTA\s+(AHORA|HOY|LA\s+FECHA)`. No introduzcas ningún patrón de ventana que contenga
esas frases: le robarías preguntas a N2, que hoy funciona.

### 🟢 H6 — Confirmación: hay precedente exacto del contrato a clonar.

`periodo_serie_dia` (`slots.py:376-390`) es el molde: función pública, pura, devuelve
`dict | None`, con clave `asumido` de lista de strings, y su resultado se cuelga de una clave
propia del dict de salida (`serie_dia`) más un `extend` a `defaults_asumidos`
(`slots.py:439-440`). **Clona esa forma exactamente.** No inventes un contrato nuevo.

### 🟢 H7 — Confirmación: `_DIA_REL` ya define el vocabulario relativo de día.

`slots.py:77` → `{"ANTEAYER": -2, "ANTIER": -2, "AYER": -1, "HOY": 0}`, consumido en
`detectar_dia:270-272`. «Ayer» ya funciona y devuelve `{"clase":"relativo","delta":-1}`.
**No lo dupliques en la ventana.** La ventana es para RANGOS (N días/meses hacia atrás), no
para días puntuales.

---

## 2. Estado actual

El archivo `slots.py` resuelve hoy estos granos temporales:

| Grano | Cómo se pide | Slot de salida |
|---|---|---|
| Mes nombrado | «en abril», «mayo 2026» | `periodo_texto: "abril"` |
| Mes anterior | «el mes pasado» | `periodo_texto: "mes pasado"` |
| Día concreto | «el 15 de mayo» | `dia: {clase:"fecha", ...}` |
| Día relativo | «ayer», «antier» | `dia: {clase:"relativo", delta:-1}` |
| Día por selector | «el mejor día» | `dia: {clase:"selector", orden:"max"}` |
| Curva diaria de un mes | «día a día en junio» | `serie_dia: {anio, mes}` |

**Lo que NO existe y este plan añade:** la **ventana móvil hacia atrás** — «los últimos 30
días», «las últimas 6 semanas», «los últimos 3 meses». Hoy esas formas no producen ningún
slot temporal: caen a `periodo_texto = None` y el motor responde el mes por defecto **sin
declarar que ignoró la ventana pedida**.

Este plan es el **cimiento** de tres planes posteriores (sub-intenciones `tendencia`,
`comparacion_periodos` y `evento_temporal` de Analizar), que necesitan una ventana resuelta
para poder consultar una serie. **Este plan NO implementa ninguna de esas tres.**

---

## 3. Especificación

### 3.1 MODIFICAR `slots.py` — bloque de constantes

**Ubicación exacta:** inmediatamente **después** de la línea 141 (el cierre de
`_RX_RANGO_GUARDA`) y **antes** de la línea 144 (el comentario de `TECHO_CENTINELA`).

Inserta este bloque completo, tal cual:

```python
# [2026-09-03 · VENTANAS-TEMPORALES] Ventana MÓVIL hacia atrás: «los últimos 30 días», «las
# últimas 6 semanas», «los últimos 3 meses». Es un grano que no existía: hasta ahora la única
# forma de acotar el tiempo era nombrar un MES o un DÍA concreto, así que estas preguntas
# caían a `periodo_texto=None` y el motor respondía el mes por defecto SIN declarar que había
# ignorado la ventana — la misma degradación silenciosa que la guarda de :281-286 existe para
# impedir, entrando por la puerta del rango en vez de la del mes.
#
# 🔑 Exige marcador EXPLÍCITO (ULTIMO/ULTIMA + variantes). NO basta «los 30 días»: esa forma
#    ya la captura `_RX_RANGO_GUARDA` (:139) y cae al rechazo honesto de no_soportado.py.
#    Ampliar la ventana a esa forma le robaría el rechazo y respondería algo distinto de lo
#    que hoy responde, sin que ningún test lo detecte.
# 🔑 SIN "HASTA HOY"/"HASTA AHORA": están en `_ACUM_KW_FUERTE` (:27) y en `_RX_ACUM_GUARDA`
#    (:130) y hoy resuelven a N2 (acumulado). Un patrón de ventana que las incluyera le
#    robaría preguntas a N2, que funciona.
_UNIDAD_VENTANA = {"DIA": "dia", "DIAS": "dia",
                   "SEMANA": "semana", "SEMANAS": "semana",
                   "MES": "mes", "MESES": "mes"}

# Cardinales escritos con letra: «los últimos tres meses» es tan natural como «los últimos 3».
# Sin esto la forma con letra no matchea y cae al mes por defecto, en silencio.
_CARDINAL = {"UN": 1, "UNA": 1, "DOS": 2, "TRES": 3, "CUATRO": 4, "CINCO": 5, "SEIS": 6,
             "SIETE": 7, "OCHO": 8, "NUEVE": 9, "DIEZ": 10, "ONCE": 11, "DOCE": 12,
             "QUINCE": 15, "VEINTE": 20, "TREINTA": 30}

# Tres construcciones, todas con marcador explícito:
#   (a) «los últimos 30 días» / «las últimas 6 semanas»  → cantidad explícita
#   (b) «el último mes» / «la última semana»             → cantidad implícita = 1
#   (c) «los 30 días anteriores»                          → marcador POSPUESTO
# El cuantificador es opcional en (a) para admitir «últimos 30 días» sin artículo.
_RX_VENTANA = re.compile(
    r"\bULTIM[OA]S?\s+(\d{1,3}|[A-Z]+)\s+(DIAS?|SEMANAS?|MESES|MES)\b"
    r"|\bULTIM[OA]\s+(DIAS?|SEMANA|MES)\b"
    r"|\b(\d{1,3})\s+(DIAS?|SEMANAS?|MESES|MES)\s+(?:ANTERIORES|ATRAS|PREVIOS)\b"
)

# Techo de cordura. Una ventana de 4 dígitos («los últimos 9999 días») no es una pregunta
# real: es ruido o un intento de forzar una consulta gigante. Se rechaza devolviendo None
# (→ rechazo honesto) en vez de resolver una ventana absurda y consultar 27 años de serie.
_VENTANA_MAX = {"dia": 365, "semana": 52, "mes": 24}
```

### 3.2 MODIFICAR `slots.py` — función pública nueva

**Ubicación exacta:** inmediatamente **después** de la línea 390 (el `return` de
`periodo_serie_dia`) y **antes** de la línea 393 (`def extraer_slots`).

Inserta esta función completa, tal cual:

```python
def detectar_ventana(texto: str, techo=None) -> dict | None:
    """Ventana MÓVIL hacia atrás, o None si la pregunta no pide una. [2026-09-03 · VENTANAS-TEMPORALES]

    Devuelve:
      {"unidad": "dia"|"semana"|"mes", "cantidad": int,
       "ini": "YYYY-MM-DD", "fin": "YYYY-MM-DD", "asumido": [...]}

    `techo` (date) = último día CON DATO, no el reloj. Sin techo no se puede aterrizar la
    ventana en fechas y se devuelve None: es preferible el rechazo honesto a inventar un
    ancla. 🔑 Este módulo es PURO — el techo entra como PARÁMETRO, aquí no se consulta BD
    ni se llama a date.today(); el reporte va ~100 días atrás del reloj y anclar al reloj
    respondería sobre fechas sin dato.

    La ventana es INCLUSIVA en ambos extremos y termina en el techo: «los últimos 30 días»
    con techo=2026-08-23 es [2026-07-25, 2026-08-23], que son 30 días contados. Un `ini`
    calculado con `days=30` daría 31 días — el error de poste clásico, por eso va `- 1`.
    """
    t = norm(texto or "")
    m = _RX_VENTANA.search(t)
    if m is None:
        return None

    # Las 3 alternativas del regex dejan sus grupos en posiciones distintas; solo una casa.
    if m.group(1) is not None:            # (a) «últimos 30 días» / «últimos tres meses»
        crudo, uni_txt = m.group(1), m.group(2)
        if crudo.isdigit():
            cant = int(crudo)
        elif crudo in _CARDINAL:
            cant = _CARDINAL[crudo]
        else:
            return None                   # palabra no reconocida como cardinal: no se adivina
    elif m.group(3) is not None:          # (b) «el último mes» → cantidad implícita 1
        cant, uni_txt = 1, m.group(3)
    else:                                 # (c) «30 días anteriores»
        cant, uni_txt = int(m.group(4)), m.group(5)

    uni = _UNIDAD_VENTANA.get(uni_txt)
    if uni is None or cant < 1:
        return None
    if cant > _VENTANA_MAX[uni]:
        return None                       # fuera de rango razonable → rechazo honesto

    if techo is None:
        return None                       # sin ancla no hay ventana que aterrizar

    fin = techo
    if uni == "dia":
        ini = fin - _dt.timedelta(days=cant - 1)
    elif uni == "semana":
        ini = fin - _dt.timedelta(weeks=cant) + _dt.timedelta(days=1)
    else:                                 # mes: se retrocede por calendario, no por 30 días
        y, mo = fin.year, fin.month - (cant - 1)
        while mo < 1:
            y, mo = y - 1, mo + 12
        ini = _dt.date(y, mo, 1)

    return {"unidad": uni, "cantidad": cant,
            "ini": ini.isoformat(), "fin": fin.isoformat(),
            "asumido": [f"ventana={cant} {uni}(s) hasta {fin.isoformat()}"]}
```

### 3.3 MODIFICAR `slots.py` — enganche en `extraer_slots`

Hay **dos** ediciones dentro de `extraer_slots`, y ambas van **después** del bloque de
`sdia` (líneas 427-431), respetando la precedencia de H4.

**Edición 1.** Localiza estas líneas exactas (433-440 del archivo actual):

```python
    per = _periodo_texto(texto)
    defaults = [f"producto={prod}", f"referencia={ref}"]
    if per is None:
        defaults.append("periodo=mes actual")
    if dia is not None:
        defaults.extend(dia.get("asumido", []))
    if sdia is not None:
        defaults.extend(sdia.get("asumido", []))
```

Reemplázalas por:

```python
    # [2026-09-03 · VENTANAS-TEMPORALES] La ventana se resuelve AL FINAL, después de que el
    # nivel ya quedó fijado. Es una capa ADITIVA: NO toca `nivel_temporal`. Resolverla antes
    # de `detectar_dia` habría convertido «el mejor día de los últimos 30 días» en algo que
    # ya no es un selector de día; resolverla dentro de `_nivel_temporal` le habría robado
    # preguntas a N4/N3/N2. Aquí no puede pisar a nadie.
    ventana = detectar_ventana(texto, techo)

    per = _periodo_texto(texto)
    defaults = [f"producto={prod}", f"referencia={ref}"]
    # 🔑 El default «periodo=mes actual» NO se declara si hay ventana: sería una contradicción
    #    en la propia declaración de supuestos (la ventana ES el periodo, y no es un mes).
    if per is None and ventana is None:
        defaults.append("periodo=mes actual")
    if dia is not None:
        defaults.extend(dia.get("asumido", []))
    if sdia is not None:
        defaults.extend(sdia.get("asumido", []))
    if ventana is not None:
        defaults.extend(ventana.get("asumido", []))
```

**Edición 2.** Localiza el `return` final (líneas 441-452) y añade **una sola clave**,
`"ventana": ventana,` inmediatamente después de la línea `"serie_dia": sdia,`:

```python
        "dia": dia,
        "serie_dia": sdia,
        "ventana": ventana,
        "defaults_asumidos": defaults,
    }
```

### 3.4 MODIFICAR `slots.py` — `menciona_dia`

`menciona_dia` es el pre-check que decide si el llamador paga la consulta a BD del techo
(`respuesta_cuantificar.py:321`). **Una ventana necesita techo.** Sin esta edición,
`detectar_ventana` recibiría siempre `techo=None` por la ruta real y devolvería siempre
`None` — el bug exacto que documenta `slots.py:230-236` para la serie diaria.

Localiza el cuerpo actual (líneas 238-240):

```python
    if detectar_dia(texto, TECHO_CENTINELA) is not None:
        return True
    return _nivel_temporal(texto) == "N1DSER"
```

Reemplázalo por:

```python
    if detectar_dia(texto, TECHO_CENTINELA) is not None:
        return True
    if _nivel_temporal(texto) == "N1DSER":
        return True
    # 🔑 [2026-09-03] La VENTANA también necesita techo. Sin esta rama, `detectar_ventana`
    #    recibiría techo=None por la ruta real (el llamador no lo pediría) y devolvería None
    #    siempre: la ventana funcionaría en los tests —donde el techo se pasa a mano— y NO en
    #    producción. Es literalmente el bug que :230-236 documenta para la serie diaria.
    #    Se usa el CENTINELA, igual que arriba: solo importa si resuelve o no, no qué fecha sale.
    return detectar_ventana(texto, TECHO_CENTINELA) is not None
```

⚠️ **El nombre de la función queda impreciso** (una ventana de meses no "menciona un día").
**No la renombres.** Tiene 3 call sites de producción y ~8 en tests; renombrarla está fuera
del alcance de este plan (§7).

### 3.5 CREAR `tests/test_slots_ventana.py`

Crea el archivo completo con este contenido exacto:

```python
"""test_slots_ventana.py — ventana temporal móvil (plan VENTANAS-TEMPORALES, 2026-09-03).

Módulo PURO: ningún test de este archivo toca BD. El `techo` se pasa a mano salvo en
`test_ruta_real_pide_techo`, que reproduce lo que hace producción.
"""
import datetime

import pytest

from app.features.consulta_v2.cuantificar.slots import (
    detectar_ventana, extraer_slots, menciona_dia, TECHO_CENTINELA,
)

_TECHO = datetime.date(2026, 8, 23)      # último día con dato en Pruebas al escribir el plan


# ---------------- formas que SÍ resuelven ----------------

@pytest.mark.parametrize("frase,unidad,cant", [
    ("produccion de Castilla en los ultimos 30 dias", "dia", 30),
    ("produccion de Castilla los ultimos 7 dias", "dia", 7),
    ("como viene Castilla en las ultimas 6 semanas", "semana", 6),
    ("produccion de Castilla en los ultimos 3 meses", "mes", 3),
    ("produccion de Castilla en los ultimos tres meses", "mes", 3),
    ("produccion de Castilla el ultimo mes", "mes", 1),
    ("produccion de Castilla la ultima semana", "semana", 1),
    ("produccion de Castilla los 15 dias anteriores", "dia", 15),
])
def test_ventana_resuelve(frase, unidad, cant):
    r = detectar_ventana(frase, _TECHO)
    assert r is not None, frase
    assert r["unidad"] == unidad and r["cantidad"] == cant


def test_ventana_dias_es_inclusiva():
    """30 días contados hacia atrás desde el techo, ambos extremos incluidos."""
    r = detectar_ventana("los ultimos 30 dias", _TECHO)
    assert r["fin"] == "2026-08-23"
    assert r["ini"] == "2026-07-25"
    d0 = datetime.date.fromisoformat(r["ini"])
    d1 = datetime.date.fromisoformat(r["fin"])
    assert (d1 - d0).days + 1 == 30


def test_ventana_meses_retrocede_por_calendario():
    """3 meses desde agosto = junio, julio, agosto. Empieza el día 1 de junio."""
    r = detectar_ventana("los ultimos 3 meses", _TECHO)
    assert r["ini"] == "2026-06-01" and r["fin"] == "2026-08-23"


def test_ventana_meses_cruza_anio():
    r = detectar_ventana("los ultimos 3 meses", datetime.date(2026, 2, 10))
    assert r["ini"] == "2025-12-01"


def test_ventana_declara_el_supuesto():
    """Nada se asume en silencio: la ventana aterrizada se declara."""
    r = detectar_ventana("los ultimos 30 dias", _TECHO)
    assert r["asumido"] and "ventana=" in r["asumido"][0]


# ---------------- formas que NO deben resolver ----------------

@pytest.mark.parametrize("frase", [
    "cuanto produjo Castilla en abril",
    "cuanto produjo Castilla el 15 de mayo",
    "cuanto produjo Castilla ayer",
    "acumulado de Castilla hasta hoy",
    "produccion acumulada de Castilla en lo que va del año",
    "cuanto produjo Castilla",
])
def test_ventana_no_captura_lo_ajeno(frase):
    assert detectar_ventana(frase, _TECHO) is None, frase


def test_ventana_sin_marcador_explicito_no_resuelve():
    """«los 30 días» sin «últimos» ya lo captura _RX_RANGO_GUARDA y cae al rechazo honesto.
    Ampliar la ventana a esa forma le robaría ese rechazo."""
    assert detectar_ventana("produccion de Castilla en los 30 dias", _TECHO) is None


def test_ventana_sin_techo_no_inventa_ancla():
    assert detectar_ventana("los ultimos 30 dias", None) is None


@pytest.mark.parametrize("frase", [
    "los ultimos 9999 dias",
    "los ultimos 400 dias",
    "los ultimos 60 meses",
    "las ultimas 200 semanas",
])
def test_ventana_fuera_de_rango_se_rechaza(frase):
    assert detectar_ventana(frase, _TECHO) is None, frase


def test_ventana_cardinal_desconocido_no_adivina():
    assert detectar_ventana("los ultimos muchos dias", _TECHO) is None


# ---------------- integración con extraer_slots ----------------

def test_slots_expone_la_ventana():
    s = extraer_slots("produccion de Castilla en los ultimos 30 dias",
                      entidad_valor="CASTILLA", techo=_TECHO)
    assert s["ventana"] is not None and s["ventana"]["cantidad"] == 30


def test_slots_ventana_es_none_cuando_no_se_pide():
    s = extraer_slots("cuanto produjo Castilla en abril", entidad_valor="CASTILLA",
                      techo=_TECHO)
    assert s["ventana"] is None


@pytest.mark.parametrize("frase,nivel", [
    ("cuanto produjo Castilla", "N1"),
    ("acumulado de Castilla", "N2"),
    ("produccion de Castilla mes a mes", "N3"),
    ("como vario Castilla mes a mes", "N4"),
    ("produccion dia a dia de Castilla en junio", "N1DSER"),
])
def test_ventana_no_altera_ningun_nivel_existente(frase, nivel):
    """🔑 REGRESIÓN CENTRAL. La ventana es ADITIVA: si algún nivel cambiara de valor por
    culpa de esta capa, el plan habría roto Cuantificar en silencio."""
    assert extraer_slots(frase, techo=_TECHO)["nivel_temporal"] == nivel


def test_ventana_no_pisa_el_selector_de_dia():
    """«el mejor día de los últimos 30 días» sigue siendo un selector de día (N1DSEL).
    La ventana convive con él; no lo sustituye."""
    s = extraer_slots("el mejor dia de castilla de los ultimos 30 dias", techo=_TECHO)
    assert s["nivel_temporal"] == "N1DSEL"
    assert s["ventana"] is not None


def test_ventana_no_declara_mes_actual_como_default():
    """Declarar a la vez «periodo=mes actual» y una ventana es una contradicción."""
    s = extraer_slots("produccion de Castilla en los ultimos 30 dias", techo=_TECHO)
    assert not any("periodo=mes actual" in d for d in s["defaults_asumidos"])
    assert any("ventana=" in d for d in s["defaults_asumidos"])


def test_periodo_texto_no_se_contamina():
    """🔑 `periodo_texto` alimenta ranking.py:199 y analisis/api.py:390, que esperan un mes
    o None. Una ventana filtrándose ahí haría que el motor respondiera el mes por defecto
    sin avisar — el bug del periodo ignorado."""
    s = extraer_slots("produccion de Castilla en los ultimos 30 dias", techo=_TECHO)
    assert s["periodo_texto"] is None


def test_mes_pasado_sigue_funcionando():
    """H1: «mes pasado» YA estaba soportado antes de este plan. Test de no-regresión."""
    s = extraer_slots("cuanto produjo Castilla el mes pasado", techo=_TECHO)
    assert s["periodo_texto"] == "mes pasado"


# ---------------- la ruta real ----------------

@pytest.mark.parametrize("frase", [
    "produccion de Castilla en los ultimos 30 dias",
    "como viene Castilla en las ultimas 6 semanas",
    "produccion de Castilla el ultimo mes",
])
def test_ruta_real_pide_techo(frase):
    """🔑 El techo NO se pasa a mano: producción lo pide solo si `menciona_dia` dice que sí
    (respuesta_cuantificar.py:321). Sin la rama de ventana en `menciona_dia`, la ventana
    funcionaría en los tests y NO en producción."""
    assert menciona_dia(frase) is True
    techo = _TECHO if menciona_dia(frase) else None
    assert extraer_slots(frase, techo=techo)["ventana"] is not None


@pytest.mark.parametrize("frase", [
    "cuanto produjo Castilla en abril",
    "acumulado hasta hoy",
])
def test_menciona_dia_no_pide_techo_de_mas(frase):
    """La rama nueva no debe hacer que se pague una consulta de techo en preguntas mensuales."""
    assert menciona_dia(frase) is False


def test_centinela_no_se_filtra_al_resultado():
    """`menciona_dia` usa TECHO_CENTINELA (año 2000). Esa fecha es un artefacto interno y
    jamás debe aparecer en una ventana devuelta por la ruta real."""
    r = detectar_ventana("los ultimos 30 dias", TECHO_CENTINELA)
    assert r is not None and r["fin"].startswith("2000")   # solo aquí, por construcción
    s = extraer_slots("los ultimos 30 dias", techo=_TECHO)
    assert s["ventana"]["fin"] == "2026-08-23"
```

---

## 4. Orden de ejecución

| # | Acción | Archivo | Referencia |
|---|---|---|---|
| 1 | Insertar el bloque de constantes tras la línea 141 | `slots.py` | §3.1 |
| 2 | Insertar `detectar_ventana` tras la línea 390 | `slots.py` | §3.2 |
| 3 | Aplicar las 2 ediciones de `extraer_slots` | `slots.py` | §3.3 |
| 4 | Aplicar la edición de `menciona_dia` | `slots.py` | §3.4 |
| 5 | Crear el archivo de tests completo | `tests/test_slots_ventana.py` | §3.5 |
| 6 | Corregir la documentación equivocada (H1) | `CLAUDE.md`, `BITACORA.md` | §4.1 |
| 7 | Correr la validación estática | — | §6.1 |

### 4.1 Paso 6 — corrección documental (H1)

En `C:\APLICACIONES\ProdIA\Repo ProdIA\CLAUDE.md`, §6, sustituye la línea:

```
⚠️ Colateral sin abrir: **«mes pasado» no está soportado** (cero coincidencias en `slots.py`)
→ responde el mes vigente en silencio.
```

por:

```
✅ Corregido el 2026-09-03: **«mes pasado» SÍ está soportado** — `slots.py:359-360` lo devuelve
literal y `analisis/api.py:385-389` lo resuelve. La afirmación anterior («cero coincidencias»)
era falsa, medida contra el código. Lo que NO existía era la **ventana móvil** («los últimos 30
días»), añadida por `plan_VENTANAS-TEMPORALES_20260903.md`.
```

En `C:\APLICACIONES\ProdIA\Repo ProdIA\BITACORA.md`, localiza la línea que empieza con
`⚠️ **Colateral: «mes pasado» no está soportado**` (≈ línea 834) y añade **inmediatamente
debajo**, sin borrar la original (la bitácora es histórico, no se reescribe):

```
> **Corregido el 2026-09-03 (plan VENTANAS-TEMPORALES, H1):** la afirmación de arriba es
> FALSA. `slots.py:359-360` sí detecta «mes pasado»/«mes anterior» y `analisis/api.py:385-389`
> lo aterriza con cruce de año correcto. Lo que faltaba era la ventana móvil.
```

---

## 5. Reglas no negociables

- **NN-1.** No toques `periodo_texto` ni `_periodo_texto`. Tienen 3 consumidores de
  producción que esperan un nombre de mes o `None` (H2).
- **NN-2.** Toda resolución que rellene algo que el usuario no dijo va declarada en
  `asumido` / `defaults_asumidos`. Sin excepción.
- **NN-3.** `slots.py` sigue siendo puro: cero imports de BD, cero `date.today()`.
- **NN-4.** Ningún `nivel_temporal` existente puede cambiar de valor. Si un test de
  `test_cuantificar.py` o `test_cuantificar_dia.py` falla, **has roto Cuantificar: DETENTE**.
- **NN-5.** No renombres `menciona_dia` (§3.4).
- **NN-6.** No implementes ninguna sub-intención de Analizar. Este plan es solo el cimiento.
- **NN-7.** Si algo del plan no calza con el código real (una línea no está donde dice),
  **DETENTE y repórtalo**. No improvises una ubicación alternativa.

---

## 6. Validación

### 6.1 Estática — la ejecuta el EXECUTOR

Los tres comandos se corren **desde `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend`**,
en PowerShell normal, **línea por línea** (no pegues el bloque entero):

```powershell
uv run pytest tests/test_slots_ventana.py -q
```
→ Esperado: **todos los tests PASAN**, ~35 casos. `0 failed`.

```powershell
uv run pytest tests/test_cuantificar.py tests/test_cuantificar_dia.py tests/test_cuantificar_ranking.py tests/test_analizar.py -q
```
→ Esperado: **mismo resultado que antes del cambio**. Si aparece un `failed` que no estaba,
es NN-4: detente.

```powershell
uv run python -m app.features.consulta_v2.golden.run_golden_cuantificar
```
→ Esperado: **el mismo porcentaje que antes del cambio**. La ventana es aditiva y no debería
mover el golden ni un punto. Si lo mueve, algo pisó a un nivel existente.

⚠️ Corre el segundo y el tercero **antes** de empezar a editar, para tener la línea base. Sin
línea base no puedes distinguir un fallo tuyo de uno de los 10 fallos preexistentes que
`CLAUDE.md` §6 documenta.

### 6.2 Humana — la ejecuta el USUARIO

El executor **no** marca esto. Se hace en el servidor de Pruebas, con datos reales:

| # | Qué probar | Resultado esperado |
|---|---|---|
| 1 | Preguntar en `http://localhost:5029` «¿cuánto produjo Castilla en los últimos 30 días?» | La respuesta **no** debe afirmar una cifra mensual como si fuera la ventana. Con este plan solo, lo correcto es que siga respondiendo lo de hoy — la ventana se **detecta** pero todavía **no la consume nadie** |
| 2 | Preguntar «¿cuánto produjo Castilla el mes pasado?» | Sigue respondiendo el mes anterior, igual que antes (H1, no-regresión) |
| 3 | Preguntar «¿cuál fue el mejor día de Castilla?» | Sigue funcionando el selector de día |

⚠️ **Este plan no cambia ninguna respuesta visible al usuario.** Es cimiento: añade un slot
que todavía nadie lee. Si una respuesta cambia, es una regresión, no una mejora.

---

## 7. Fuera de alcance

Explícitamente **NO** se hace en este plan:

- Las sub-intenciones `tendencia`, `comparacion_periodos` y `evento_temporal` de Analizar.
  Son los tres planes siguientes y dependen de este.
- **Consumir** la ventana: ningún ejecutor, ranking ni endpoint la lee todavía. La clave
  `ventana` queda expuesta y sin consumidor, a propósito.
- Corregir que `_periodo_texto` detecte `"pasado"` por substring sobre texto sin normalizar
  (H1, segunda parte). Sin falso positivo medido, y con tests vivos encima.
- Renombrar `menciona_dia` a algo que describa también la ventana (§3.4).
- Ventanas que no terminan en el techo («los 30 días **de mayo**», «entre marzo y junio»).
  Hoy caen a `_RX_RANGO_GUARDA` y su rechazo honesto se conserva.
- **«el último día»** (verificado v2): `detectar_dia` no lo captura, así que este plan lo
  resolvería como ventana de 1 día. Es cobertura nueva legítima, NO una colisión — pero si se
  quisiera que fuera un selector de día (el más reciente con dato), sería otro plan.
- Trimestres y semestres. `_RX_RANGO_GUARDA:140` ya los rechaza honestamente.
- Cualquier cambio en frontend, en el clasificador (`maquina_q.py`), en `patrones_grupo.yaml`
  o en el golden de clasificación.

---

## 8. Prompt para el agente EXECUTOR

```
Eres un agente EXECUTOR. Lee completo el plan
C:\APLICACIONES\ProdIA\Repo ProdIA\backend\Planes\plan_VENTANAS-TEMPORALES_20260903.md
y ejecútalo AL PIE DE LA LETRA.
Reglas: CERO modificaciones al plan. Orden secuencial (§4). Si falla, DETENTE.
Antes de editar, corre la línea base de §6.1 (comandos 2 y 3).
Reporta: ✅/❌ Paso N.
Al final: archivos tocados + "¿Hago commit?"
```
