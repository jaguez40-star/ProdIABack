# plan_TENDENCIA_20260903 (v2 — auditado y verificado contra el código)

> Punto **2 de 4** de «inteligencia de tiempo». Cubre los tipos **4 (tendencia/evolución)**,
> **5 (ritmo de cambio / declinación)** y **6 (promedio móvil / suavizado)**.
> Punto 1 (acumulados MTD/YTD y ventanas) cerrado el 2026-09-03 — commits `5f4aae5` y `d95e566`.
>
> **v2**: el v1 se verificó línea a línea contra el código. Encontró 4 fallos que lo habrían roto
> en ejecución y 2 funciones que ya existían y el v1 iba a duplicar. Ver §1B.

---

## 0. Contexto para el agente EXECUTOR

Eres un agente EXECUTOR. No tienes la conversación previa ni el historial de git. Todo lo que
necesitas está aquí.

**Proyecto:** ProdIA — asistente de producción de Ecopetrol. Dos repos hermanos:

| Repo | Ruta absoluta | Stack |
|---|---|---|
| ProdIABack | `C:\APLICACIONES\ProdIA\Repo ProdIA\backend` | FastAPI + `uv`, puerto 5030 |
| ProdIAWebFront | `C:\APLICACIONES\ProdIA\Repo ProdIA\frontend` | Flask + Jinja2, puerto 5029 |

**Son dos commits separados.** Nunca uno solo para los dos.

**Motor Q v2** tiene 4 grupos: `cuantificar`, `jerarquizar`, `analizar`, `desconocido`. El grupo
`analizar` ya tiene 5 sub-intenciones (`causal`, `proyeccion`, `diferidas`, `economia`,
`referencia`) resueltas por `analizar/subrouter.py`. Este plan añade la **sexta**: `tendencia`.

**Convenciones que se respetan sin excepción:**

- **HE4** — el mes EN CURSO es proyección: nunca entra en un cálculo histórico.
- **AF-3.7** — match de palabras sueltas por TOKEN (`\b`), nunca substring. Dos bugs históricos
  nacieron de eso («MAYO» ⊂ «MAYOR»).
- **Módulos puros** — un módulo de cálculo NO importa BD, NO llama `date.today()`. Los datos entran
  por parámetro. `analizar/tendencia.py` (nuevo) es puro.
- **`norm()`** (`consulta_v2/normaliza.py`) hace UPPER + trim + colapsa espacios + pliega acentos y
  la ñ. Por eso todos los patrones se escriben **en mayúscula y sin tildes**.
- **Español** en todo texto que vea el usuario.
- Comandos: PowerShell, desde la carpeta indicada, línea por línea salvo aviso.

**Prohibido decidir.** Si algo no está en este plan, DETENTE y reporta. No improvises.

---

## 1. Hallazgos de la auditoría

Estos hallazgos **determinan** la §3.

### 🔴 H1 — «TENDENCIA» ya existe y hoy responde otra cosa

`analizar/subrouter.py:12` tiene `"TENDENCIA"` dentro de `_PROY`. Y `analizar/plantilla.py:310`
(`proyeccion`) responde el **ritmo DIARIO del mes en curso**:

> «para cerrar agosto, el crudo requiere 218.400 bbl/día en los 1 días restantes; va a un ritmo de
> 215.220 bbl/día → va camino de cerrar en meta»

Eso **no es una tendencia**. Hoy «¿cuál es la tendencia de Castilla?» devuelve el pace del mes con
total seguridad: el fallo silencioso de CLAUDE.md §6 — no falla, responde otra cosa.

**Consecuencia:** `"TENDENCIA"` **sale** de `_PROY` y pasa a `_TEND`. No es aditivo, es una
corrección de enrutado, y como tal se declara y se cubre con tests de no-regresión.

### 🟢 H2 — El golden de Analizar no se rompe

`golden/analizar_golden.yaml` tiene 10 casos: 3 `causal`, 3 `proyeccion`, 2 `diferidas`,
2 `economia`. Los 3 de `proyeccion` son «¿cómo vamos este mes?» (`COMO VAMOS`), «¿vamos a cerrar en
meta?» (`VAMOS A CERRAR`) y «¿cuál es la proyección de cierre?» (`PROYECCION`). **Ninguno depende de
`TENDENCIA`.** Verificado por grep: cero apariciones de «tendencia», «evolución», «declina»,
«ritmo» o «móvil» en los tres golden.

### 🟢 H3 — La Capa 1 del clasificador ya enruta bien

`config/patrones_grupo.yaml:241` ya tiene `TENDENCIA` bajo `analizar`. Una pregunta con esa palabra
llega al grupo correcto; solo se pierde en el sub-router. **No se toca el clasificador de grupo**
salvo para añadir vocabulario nuevo (§3.5).

### 🔴 H4 — Frontera con Cuantificar N3/N4: hay solape real

| Nivel | Qué responde | Panel | Disparadores (`cuantificar/slots.py:32-36`) |
|---|---|---|---|
| **N3** | La serie REAL mensual del año | `cuant_serie` | `SERIE`, `EVOLUCION`, `MENSUALES`, «mes a mes», «cada mes» |
| **N4** | Deltas mes a mes + waterfall | `cuant_var` | `VARIACION`, `SUBIO`, `BAJO`, `CRECIO`, `CAYO`, `DELTA` |

**Decisión cerrada (no la reabras):** este plan **NO toca Cuantificar**.

La frontera la fija la Capa 1, que ya funciona:

- «¿cómo varió Castilla mes a mes?» → **cuantificar N4**. Pide el DATO de cada salto.
- «¿cuál es la tendencia?» / «¿a qué ritmo declina?» → **analizar/tendencia**. Pide la LECTURA.

N3/N4 dan la serie; `tendencia` la **interpreta**. **`EVOLUCION` NO se añade a Analizar**: ya es de
N3 y robársela cambiaría una respuesta que hoy es correcta.

### 🟢 H5 — El dato ya existe: coste CERO de consultas

`analisis/api.py:607-637` construye `ritmo_mensual` y `desempeno()` lo devuelve:

```python
ritmo = {"meses": [], "meses_num": [], "series": {}, "promedio_mes": {},
         "promedio_dia": {}, "mes_actual": mo}
ritmo["meses"]     = [MESES_ES[m][:3] for m in meses_ord]   # ["Ene", "Feb", ...]
ritmo["meses_num"] = meses_ord                              # [1, 2, 3, ...]
ritmo["series"][p] = [round(real_mes[m][p]) ... ]           # {"CRUDO": [v1, v2, ...]}
```

Es la MISMA serie del tablero. **Ni una consulta nueva** — el mismo patrón que `serie_acum` en el
punto 1.

### 🟡 H6 — `_serie_puntos` es reutilizable, pero vive en Cuantificar

`cuantificar/niveles.py:91` hace una extracción parecida. **No se importa desde Analizar**: crearía
una dependencia cruzada entre features hermanas por ahorrar 8 líneas, y devuelve una tupla de 5
pensada para N3/N4. `tendencia.py` recibe los puntos ya extraídos.

### 🟡 H7 — Falta vocabulario, y es la mitad del trabajo

Cero apariciones en `consulta_v2/` de `DECLINACION`, `MEDIA MOVIL`, `PROMEDIO MOVIL`, `SUAVIZ`,
`COMO VIENE`, `VA SUBIENDO`, `RITMO DE CAIDA`. Un motor que calcula la tendencia pero no entiende
cómo se pide es un motor que nadie usa.

### 🟡 H8 — El cache-buster del JS

`frontend/MainChat/templates/mainchat_layout.html:317` carga `multitab_shell.js` con `?v=...`. El
2026-09-03 ese archivo cambió tres veces sin subir el `?v=`: el navegador sirvió su copia cacheada,
el panel no aparecía y **no había ningún error en consola**. Media sesión de diagnóstico.
**Si tocas `multitab_shell.js`, subes el `?v=` en el mismo commit.**

### 🟢 H9 — `defaults_asumidos` no se pinta en ninguna parte

0 coincidencias en `validador.py`, `_panel_datos` y `multitab_shell.js`. Todo lo que el usuario deba
saber va en `avisos`.

---

## 1B. Hallazgos de la VERIFICACIÓN del v1

El v1 se contrastó contra el código real. Esto es lo que estaba mal y por qué la §3 cambió.

### 🔴 V1 — Hay TRES puntos de entrada, no uno. El v1 habría dejado el fake sin inyectar

`respuesta_analizar.py` expone:

```python
145: def _responder_core(texto, entidad=None, usuario=None, conversation_id=None,
                         _ejecutivo_fn=None, _diferidas_fn=None, _economia_fn=None, _split_fn=None,
                         _p50_fn=None, _vp_fn=None, _president_fn=None, _serie_fn=None) -> dict
400: def responder(...) -> str                    # wrapper compat, devuelve solo el mensaje
412: def responder_con_panel(...) -> dict         # la que usa maquina_q.py:609
```

El v1 decía «añade `_desempeno_fn=None` al final de sus parámetros», en singular. Si solo se toca
`_responder_core`, **los dos wrappers no lo propagan** y los tests no pueden inyectar el fake por la
vía pública — que es la única que usa producción. El módulo habría quedado no testeable sin BD.

**Corrección:** el parámetro se añade y se propaga en **los tres** (§3.4c).

### 🔴 V2 — El comando del golden del v1 no existe

El v1 pedía `uv run python -m app.features.consulta_v2.golden.run_golden_analizar`. El docstring
real del script dice otra cosa:

```
⚠️ NO correr en dev con la BD (regla de RAM). Uso, desde backend/, en el SERVIDOR DE PRUEBAS:
    PYTHONPATH=. uv run python app/features/consulta_v2/golden/run_golden_analizar.py
```

**Corrección:** §6.1 lleva el comando real, y el golden de clasificación (92 casos) sale de la
validación del executor y pasa a §6.2 — puede escalar a Capa 2 (Ollama) y en una máquina sin Ollama
da un resultado engañoso.

### 🔴 V3 — Una sub-intención nueva sin casos en el golden es una sub-intención sin red

`analizar_golden.yaml` lo dice en su cabecera: *«CRECIMIENTO: toda corrección verificada entra AQUÍ
con su etiqueta correcta (regresión permanente — el error no regresa)»*. El v1 añadía la
sub-intención y **no tocaba el golden**: el gate habría seguido dando 10/10 sin probar ni una
pregunta de tendencia.

**Corrección:** §3.9, cuatro casos nuevos. El golden pasa de 10 a 14.

### 🔴 V4 — `respuesta_analizar.py` NO importa `desempeno`

Importa `ejecutivo as _ejecutivo_ep` (:21) y `president as _president_ep` (:34). El dict `d` que
circula por el módulo es el de **`ejecutivo`** (`meta`, `titular`, `tarjetas`, `pace_crudo`,
`detractores`) y **no tiene `ritmo_mensual`**. El v1 decía «comprueba si ya está importado» y dejaba
la decisión al executor, que es exactamente lo que §10.3 prohíbe.

**Corrección:** el import se especifica literal, sin condicional (§3.4a). No hay colisión de alias:
`_desempeno_ep` es nombre libre en ese módulo.

### 🟡 V5 — El producto explícito ya está resuelto; el v1 lo iba a ignorar

`respuesta_analizar.py:83-93` ya tiene:

```python
_PROD_EXPL = (("CRUDO", "CRUDO"), ("GAS", "GAS"), ("BLANCOS", "BLANCOS"), ("BLANCO", "BLANCOS"))
def _producto_explicito(texto, entidad_valor) -> str | None:   # "CRUDO"|"GAS"|"BLANCOS"|None
```

Y `analizar/plantilla.py:9-10` tiene `_UNIDAD = {"CRUDO": "bbl", "GAS": "MSCF", "BLANCOS": "bbl"}` y
`_PROD_L` para pasar a minúscula. El v1 fijaba `CRUDO` a pelo y mandaba GAS/BLANCOS a §7 «fuera de
alcance». Con la función delante, eso significa que **«la tendencia del gas de Cusiana» respondería
crudo en silencio** — el fallo de la casa, otra vez, y por no usar tres líneas que ya existen.

**Corrección:** el producto explícito entra en la especificación (§3.4b) y sale de §7. Es la
diferencia entre reutilizar y reinventar (CLAUDE.md §7: «conectar antes que construir»).

### 🟢 V6 — La rama GLOBAL funciona: `desempeno(entidad=None)` agrega todo ECP

`_ambito` (`analisis/api.py:397`) mete toda la resolución dentro de `if entidad:`; con `None` deja
`ids=[]` y `vid=None`, y el `where()` cae a `TRUE`, que es el universo ECP completo. El `return None`
por «no encontrada» está **dentro** de ese `if`, así que no se dispara. Analizar responde sin entidad
(RA-2) y la tendencia global funcionará igual.

### 🔴 V7 — Trampa de los defaults `Query(...)`

`desempeno` es un endpoint FastAPI. CLAUDE.md §7: *«No medir endpoints FastAPI importándolos en
proceso: los defaults `Query(...)` falsean el resultado»*. El propio archivo lo documenta en
`api.py:504-511`: un `Query(None)` sobreviviente llegó al SQL y reventó con
`psycopg.ProgrammingError: cannot adapt type 'Query'`, medido corriendo el golden real.

**Corrección:** regla explícita en §5 — los cuatro argumentos (`entidad`, `segmento`, `nivel`,
`periodo`) van SIEMPRE explícitos, igual que en `niveles.py:25` y `ejecutor.py:111-112`.

### 🟢 V8 — El dispatcher del panel sí sirve a Analizar

`__cnPintarPanelCuant` se invoca en `multitab_shell.js:6755` con `d.panel` para toda respuesta de
Consulta, y `analiza_foco` / `analiza_dif` / `p50_vp` ya viven en su cadena de ternarios. El diseño
del panel del v1 es correcto; se conserva.

### 🟢 V9 — `_fmt` existe y la firma del v1 era correcta

`analizar/plantilla.py:15` — `_fmt(valor, prod)` con `prod` en MAYÚSCULA («CRUDO»), que traduce con
`_PROD_L`. El uso del v1 se conserva.

### 🟡 V10 — Los tests de integración necesitan neutralizar el resolver

`_resolver_con_contexto` (:50) llama a `resolver.resolver_unico`, que toca el catálogo. Los 13 tests
de `test_p50_referencia.py` lo monkeypatchean. Los tests nuevos de integración harán lo mismo, con
una fixture explícita (§3.8) — si no, dependerían de BD y el executor no podría correrlos.

---

## 2. Estado actual

**`backend/backend/app/features/consulta_v2/analizar/`** contiene `__init__.py`, `diferidas.py`,
`economia.py`, `p50_referencia.py`, `plantilla.py`, `subrouter.py`. **No hay `tendencia.py`.**

**`subrouter.py`**: 41 líneas, una función pública `sub_intencion(texto) -> str`. Precedencia:
`economia` → `diferidas` → `proyeccion` → `referencia` → `causal`.

**`respuesta_analizar.py`**: `_responder_core` (:145) resuelve la sub-intención en :165 y despacha
con bloques `if sub == "...":` en :195 (`diferidas`), :228 (`economia`), :254 (`referencia`) y :349
(`proyeccion`). Los wrappers `responder` (:400) y `responder_con_panel` (:412) delegan en él.

**`multitab_shell.js`** (488.355 bytes): dispatcher en `__cnPintarPanelCuant` (~:4269), envoltorio
reutilizable `__cnPanelMesHtml(d, hostCls)` (~:4408), y el pintor más parecido al que necesitas es
`__cnAcumMesInto` (~:4452), que monta dos trazas Plotly.

---

## 3. Especificación

### 3.1 AÑADIR — `backend/backend/app/features/consulta_v2/analizar/tendencia.py`

Archivo NUEVO. Módulo **PURO**: no importa BD, no llama `date.today()`.

```python
"""analizar/tendencia.py — la LECTURA de la serie mensual: dirección, ritmo y suavizado.

Punto 2 de «inteligencia de tiempo» (tipos 4, 5 y 6). Cubre lo que la serie sola no dice:
si sube o baja, a qué ritmo, y si esa dirección es sostenida o ruido.

🔑 PURO. Los puntos entran como parámetro — quien los saca de `desempeno()["ritmo_mensual"]`
   es `respuesta_analizar`. Sin BD aquí, ni `date.today()`, ni imports de `analisis`.
🔑 HE4: solo entran meses CERRADOS. El mes en curso es una proyección y meterlo en la
   regresión inclinaría la recta con un dato incompleto — el error clásico de leer una
   tendencia sobre un mes a medio reportar. El filtro lo aplica el llamador, que es quien
   conoce `mes_actual`; este módulo confía en recibir la serie ya limpia.
"""

# Umbral bajo el cual la pendiente se lee como ESTABLE en vez de subida/bajada. 1% mensual
# sobre la media: por debajo de eso, la "tendencia" es ruido de operación, no una señal.
_UMBRAL_ESTABLE_PCT = 1.0
# R² mínimo para llamar SOSTENIDA a una dirección. Por debajo, la recta explica tan poco de
# la nube de puntos que afirmar "viene cayendo sostenidamente" sería una afirmación falsa:
# se rotula IRREGULAR y se dice el promedio, que sí es cierto.
_R2_SOSTENIDA = 0.5
# Ventana de la media móvil. 3 meses: suaviza el ruido mensual sin borrar un cambio real
# de nivel. Necesita 4 puntos para dar al menos 2 valores y que la curva se vea.
_VENTANA_MM = 3
_MIN_PUNTOS = 3          # con 2 puntos "la tendencia" es un delta, y eso ya lo da N4
_MIN_PUNTOS_MM = 4


def _regresion(valores: list) -> tuple:
    """Mínimos cuadrados sobre (i, valor) con i = 0..n-1. Devuelve (pendiente, intercepto, r2).

    La x es el ÍNDICE del punto, no el número de mes: así una serie con huecos (un mes sin
    dato) no distorsiona la escala — los meses presentes se tratan como pasos consecutivos,
    que es como los lee quien mira la curva.
    """
    n = len(valores)
    mx = (n - 1) / 2.0
    my = sum(valores) / n
    sxy = sum((i - mx) * (v - my) for i, v in enumerate(valores))
    sxx = sum((i - mx) ** 2 for i in range(n))
    if sxx == 0:
        return 0.0, my, 0.0
    b = sxy / sxx
    a = my - b * mx
    syy = sum((v - my) ** 2 for v in valores)
    # syy == 0 es una serie PLANA: la recta la explica perfectamente, r2 = 1.0. Devolver 0.0
    # la rotularía "irregular" cuando es lo más regular que existe.
    r2 = 1.0 if syy == 0 else max(0.0, min(1.0, 1 - sum(
        (v - (a + b * i)) ** 2 for i, v in enumerate(valores)) / syy))
    return b, a, r2


def media_movil(valores: list, ventana: int = _VENTANA_MM) -> list:
    """Media móvil simple, alineada al final. Los primeros `ventana-1` huecos van a None:
    Plotly con `connectgaps:false` no los dibuja, que es lo correcto — no hay media móvil
    de 3 meses en el primer mes, y rellenarla con el valor crudo sería inventar."""
    if len(valores) < ventana:
        return [None] * len(valores)
    out = [None] * (ventana - 1)
    for i in range(ventana - 1, len(valores)):
        out.append(sum(valores[i - ventana + 1:i + 1]) / ventana)
    return out


def leer(puntos: list) -> dict:
    """`puntos` = [{"mes": "Ene", "num": 1, "valor": 123.0}, ...] SOLO de meses cerrados.

    Devuelve {"aplica": True, direccion, pendiente, pct_mensual, pct_anualizado, r2,
              sostenida, media, primero, ultimo, n, serie_mm, valores, meses}
    o {"aplica": False, "texto": "..."} cuando no hay serie suficiente.
    """
    vals = [float(p["valor"]) for p in puntos if p.get("valor") is not None]
    meses = [p["mes"] for p in puntos if p.get("valor") is not None]
    if len(vals) < _MIN_PUNTOS:
        return {"aplica": False,
                "texto": (f"Solo tengo {len(vals)} mes{'es' if len(vals) != 1 else ''} cerrado"
                          f"{'s' if len(vals) != 1 else ''} con dato: hacen falta al menos "
                          f"{_MIN_PUNTOS} para leer una tendencia. Con dos meses lo que hay es "
                          f"una variación, y esa sí te la puedo dar.")}

    b, _a, r2 = _regresion(vals)
    media = sum(vals) / len(vals)
    pct_mensual = round(b / media * 100.0, 2) if media else 0.0
    # Anualizada por COMPOSICIÓN, no por ×12: una caída del 2% mensual NO es 24% anual sino
    # 21.5%. El ×12 exagera, y esta cifra se usa para hablar de declinación de campo.
    pct_anual = round(((1 + pct_mensual / 100.0) ** 12 - 1) * 100.0, 1)

    if abs(pct_mensual) < _UMBRAL_ESTABLE_PCT:
        direccion = "estable"
    elif b > 0:
        direccion = "al alza"
    else:
        direccion = "a la baja"

    mm = media_movil(vals) if len(vals) >= _MIN_PUNTOS_MM else [None] * len(vals)
    return {"aplica": True, "direccion": direccion, "pendiente": b,
            "pct_mensual": pct_mensual, "pct_anualizado": pct_anual, "r2": round(r2, 2),
            "sostenida": r2 >= _R2_SOSTENIDA, "media": media,
            "primero": meses[0], "ultimo": meses[-1], "n": len(vals),
            "serie_mm": mm, "valores": vals, "meses": meses}
```

### 3.2 MODIFICAR — `analizar/subrouter.py`

**(a)** Reemplaza el bloque de las **líneas 10-21** por:

```python
# [2026-09-03 · TENDENCIA] "TENDENCIA" SALE de _PROY. Estaba aquí desde el inicio y mandaba
# «¿cuál es la tendencia de Castilla?» a `proyeccion`, que responde el ritmo DIARIO del mes en
# curso («requiere 218.400 bbl/día en los días restantes») — otra cosa, dicha con seguridad.
# Verificado contra golden/analizar_golden.yaml: sus 3 casos de proyeccion casan con
# COMO VAMOS / VAMOS A CERRAR / PROYECCION. Ninguno depende de TENDENCIA.
_PROY = ("COMO VAMOS", "VAMOS A LLEGAR", "VAMOS A CERRAR", "VAMOS A ALCANZAR",
         "PROYECCION", "SE VE RECUPERACION", "VA A CERRAR", "COMO VA A CERRAR",
         "PROYECTA", "CAMINO DE")
# [2026-09-03 · TENDENCIA] La LECTURA de la serie mensual: dirección, ritmo, suavizado.
# 🔑 SIN "EVOLUCION" ni "MES A MES": son disparadores de N3 en cuantificar/slots.py:35-36 y
#    hoy responden la curva mensual correctamente. Robárselos cambiaría una respuesta buena.
# 🔑 SIN "SUBIO"/"BAJO"/"VARIO": son de N4 (waterfall de deltas, slots.py:32). N3/N4 dan la
#    serie; esta sub-intención la INTERPRETA. Son complementarias, no rivales.
_TEND = ("TENDENCIA", "DECLINACION", "DECLINANDO", "DECLINA", "MEDIA MOVIL",
         "PROMEDIO MOVIL", "SUAVIZAD", "RITMO DE CAIDA", "RITMO DE DECLIN",
         "COMO VIENE", "VIENE SUBIENDO", "VIENE BAJANDO", "VIENE CAYENDO",
         "VA SUBIENDO", "VA BAJANDO", "VA CAYENDO", "SIGUE CAYENDO", "SIGUE SUBIENDO")
_DIFERIDAS = ("DIFERIDAS", "MANTENIMIENTO", "MANTENIMIENTOS")
_ECON = ("EBITDA", "NOPAT", "MARGEN", "RENTABILIDAD", "PLATA")
# [2026-08-13] P50 pedido como REFERENCIA (una cifra), no como tema causal. "P50" en el texto NO
# significa "análisis causal" — significa que el usuario eligió una referencia. Token exacto sobre
# `toks` (norm() NO retira '?'/'¿', HE7 — "…del P50?" no calzaría con un `in` de frase a secas).
_PUNCT = "¿?¡!.,;:()[]{}\"'`"
_REFERENCIA = ("P50",)
_CAUSAL_EXPL = ("POR QUE", "A QUE SE DEBE", "EXPLICA", "CAUSAS DE",
                "DETRACTORES", "QUE PASO CON", "PESAN", "PESA")
```

**(b)** Reemplaza el cuerpo de `sub_intencion` (**líneas 24-40**) por:

```python
def sub_intencion(texto: str) -> str:
    """causal (default) | proyeccion | diferidas | economia | referencia | tendencia.
    Precedencia: economia/diferidas ganan (son fuentes distintas), luego TENDENCIA, luego
    proyeccion, luego referencia (P50 sin señal causal explícita), luego causal."""
    t = norm(texto or "")
    if any(k in t for k in _ECON):
        return "economia"
    if any(k in t for k in _DIFERIDAS):
        return "diferidas"
    # [2026-09-03 · TENDENCIA] ANTES de proyeccion, no después. «¿cómo viene Castilla, vamos a
    # cerrar en meta?» trae las dos señales; la tendencia es la que el usuario nombró primero y
    # la que `proyeccion` no sabe responder. Al revés, `_PROY` volvería a capturarla y este
    # bloque no se alcanzaría nunca — que es exactamente el bug que este plan corrige.
    if any(k in t for k in _TEND):
        return "tendencia"
    if any(k in t for k in _PROY):
        return "proyeccion"
    # Debajo de proyeccion a propósito: "¿vamos a llegar al P50?" sigue siendo proyección — solo
    # las preguntas que piden LA CIFRA caen aquí.
    toks = {w.strip(_PUNCT) for w in t.split()}
    if any(k in toks for k in _REFERENCIA) and not any(k in t for k in _CAUSAL_EXPL):
        return "referencia"
    return "causal"
```

### 3.3 AÑADIR — función `tendencia` en `analizar/plantilla.py`

Añade **al final** del archivo. Usa `_fmt` (:15) y `_UNIDAD` (:9), que YA existen (V5, V9).

```python
def tendencia(t: dict, entidad, producto: str = "CRUDO") -> str:
    """Lectura de la serie mensual: dirección, ritmo y suavizado. `t` = analizar.tendencia.leer().

    `producto` en MAYÚSCULA ("CRUDO"|"GAS"|"BLANCOS"), como lo devuelve
    respuesta_analizar._producto_explicito. La unidad sale de _UNIDAD, no se pasa por parámetro:
    duplicar esa tabla es como nacen las divergencias entre bbl y MSCF.

    🔑 El texto NO repite la serie mes a mes — son hasta 12 cifras y la curva ya está en el
       panel. Dice lo que la curva no puede decir sola: si sube o baja, a qué ritmo y si esa
       dirección es de fiar.
    """
    scope = entidad or "Global (toda la producción ECP)"
    pl = _PROD_L.get(producto, "crudo")
    if not t.get("aplica"):
        return f"📊 {scope}\n{t['texto']}"

    u = _UNIDAD.get(producto, "bbl")
    dirn, pm = t["direccion"], t["pct_mensual"]
    rango = f"{t['primero']}–{t['ultimo']}"
    cab = f"📊 {scope} · {pl} · {rango} ({t['n']} meses cerrados)\nTENDENCIA · "

    if dirn == "estable":
        cuerpo = (f"la producción está ESTABLE: el cambio medio es de {abs(pm)}% mensual, por "
                  f"debajo del 1% que separa una tendencia real del ruido de operación. "
                  f"Promedio del periodo: {_fmt(t['media'], producto)} {u}/mes.")
    else:
        # El signo va en la palabra, no en el número: "cae un -2.3%" es una doble negación que
        # se lee mal. abs() en la cifra y la dirección en el verbo.
        verbo = "sube" if dirn == "al alza" else "cae"
        firmeza = ("de forma sostenida" if t["sostenida"]
                   else "de forma irregular (los meses se dispersan mucho de la línea)")
        cuerpo = (f"la producción viene {dirn.upper()}: {verbo} {abs(pm)}% al mes {firmeza}, "
                  f"lo que a doce meses equivale a {abs(t['pct_anualizado'])}% "
                  f"{'de crecimiento' if dirn == 'al alza' else 'de declinación'}. "
                  f"Promedio del periodo: {_fmt(t['media'], producto)} {u}/mes.")

    if any(v is not None for v in t.get("serie_mm") or []):
        cuerpo += " La media móvil de 3 meses está en la gráfica."
    else:
        cuerpo += (f" No dibujo media móvil de 3 meses: hacen falta 4 meses cerrados y tengo "
                   f"{t['n']}.")
    # HE4 explícito: quien lee una tendencia necesita saber que el mes en curso no cuenta.
    cuerpo += " El mes en curso NO entra: su cifra todavía es una proyección."
    return cab + cuerpo
```

### 3.4 MODIFICAR — `respuesta_analizar.py`

**(a) Import.** Añade **exactamente** esta línea junto al import de `president` (:34). Verificado
(V4): `desempeno` NO está importado y `_desempeno_ep` es nombre libre.

```python
from app.features.analisis.api import desempeno as _desempeno_ep
```

Y junto a los demás imports de `analizar` (:29-33):

```python
from app.features.consulta_v2.analizar import tendencia as _tendencia
```

**(b) El bloque de la sub-intención.** Insértalo **justo antes** de `if sub == "proyeccion":`
(:349):

```python
    # [2026-09-03 · TENDENCIA] Punto 2 de inteligencia de tiempo. Lee la serie mensual que
    # `desempeno` ya devuelve en `ritmo_mensual` — CERO consultas nuevas (H5).
    # 🔑 Los 4 argumentos van EXPLÍCITOS. `desempeno` es un endpoint FastAPI y sus defaults son
    #    objetos Query(...); uno sobreviviente llegó al SQL y reventó con "cannot adapt type
    #    'Query'" (analisis/api.py:504-511). Mismo patrón que niveles.py:25 y ejecutor.py:111.
    # 🔑 HE4: solo meses CERRADOS. `mes_actual` marca el que está en curso y se descarta aquí;
    #    la serie de `ritmo_mensual` lo incluye porque el tablero lo pinta punteado, pero una
    #    regresión sobre un mes a medio reportar inclina la recta con un dato incompleto.
    # 🔑 El producto sale de `_producto_explicito` (:86), que YA existe: sin él, «la tendencia
    #    del gas de Cusiana» respondería crudo en silencio (V5).
    if sub == "tendencia":
        _prod = _producto_explicito(texto, ent_valor) or "CRUDO"
        _d = _desempeno_fn(entidad=ent_valor, segmento="ecp", nivel=nivel, periodo=None)
        if not _d.get("encontrada") or _d.get("sin_datos"):
            return {"mensaje": f"No tengo serie mensual de producción para {alcance}.",
                    "panel": None}
        _r = _d.get("ritmo_mensual") or {}
        _act = _r.get("mes_actual")
        _puntos = [
            {"mes": m, "num": n, "valor": v}
            for m, n, v in zip(_r.get("meses") or [], _r.get("meses_num") or [],
                               (_r.get("series") or {}).get(_prod) or [])
            if v is not None and (_act is None or n < _act)
        ]
        _t = _tendencia.leer(_puntos)
        cuerpo = _plantilla.tendencia(_t, ent_valor, _prod)
        intro = _intro(alcance, usuario)
        mensaje = respuesta_base.envolver(
            intro, cuerpo, "¿Quieres el detalle mes a mes, o la proyección de cierre?")
        # Panel SOLO si hay lectura (mismo criterio que p50_vp/diferidas): sin serie, un bloque
        # en la pila repetiría el mismo "no tengo datos" que ya dice el texto.
        panel = None
        if _t.get("aplica"):
            panel = {"tipo": "analiza_tend", "datos": {
                "entidad_cualificada": alcance,
                "producto": _plantilla._PROD_L.get(_prod, "crudo"),   # minúscula: __cnProdCol
                "unidad": _plantilla._UNIDAD.get(_prod, "bbl"),
                "anio": (_d.get("mes") or {}).get("anio"),
                "meses": _t["meses"], "valores": _t["valores"], "serie_mm": _t["serie_mm"],
                "direccion": _t["direccion"], "pct_mensual": _t["pct_mensual"],
                "avisos": [],
            }}
        return {"mensaje": mensaje, "panel": panel}
```

**(c) 🔴 La inyección, en los TRES puntos de entrada (V1).**

1. En `_responder_core` (:145-147), añade `_desempeno_fn=None` al final de la lista de parámetros.
2. Junto a las asignaciones de :155-162, añade:

```python
    # [2026-09-03 · TENDENCIA] Inyectable como los demás `_fn`: los tests pasan una serie fija
    # y este módulo no toca BD en pruebas.
    desemp_fn = _desempeno_fn or _desempeno_ep
```

⚠️ En el bloque (b), usa `desemp_fn(...)`, **no** `_desempeno_fn(...)`: el parámetro crudo puede
ser `None`. (Si prefieres, renombra en (b); lo que no puede quedar es la variable sin resolver.)

3. En `responder` (:400-409) y en `responder_con_panel` (:412-421): añade `_desempeno_fn=None` a
   la firma **y** `_desempeno_fn=_desempeno_fn` a la llamada interna a `_responder_core`. **Los
   dos wrappers, no uno.** `maquina_q.py:609` usa `responder_con_panel`; si no lo propaga, el fake
   no llega nunca.

### 3.5 MODIFICAR — `config/patrones_grupo.yaml`

Bajo la clave `analizar:` (:221), **añade al final de la lista**. `TENDENCIA` ya está; no lo
dupliques.

```yaml
    # [2026-09-03 · TENDENCIA] Formas de pedir la LECTURA de la serie que la Capa 1 no atrapaba
    # y caían al LLM (o a cuantificar por 'PRODUCCION\s+DE'). NO se añade 'EVOLUCION' ni
    # 'MES\s+A\s+MES': son de N3 en cuantificar y hoy responden la curva correctamente.
    - 'DECLINACION'
    - 'DECLINA\w*'
    - '(MEDIA|PROMEDIO)\s+MOVIL'
    - 'SUAVIZAD\w*'
    - 'RITMO\s+DE\s+(CAIDA|DECLIN\w*)'
    - 'COMO\s+VIENE'
    - '(VIENE|VA)\s+(SUBIENDO|BAJANDO|CAYENDO)'
```

### 3.6 MODIFICAR — `frontend/static/js/multitab_shell.js`

**(a)** Añade constructor y pintor **justo después** de `__cnAcumMesInto` (termina ~:4516 con su
bloque `if (cap) { ... }`):

```js
  // [2026-09-03 · TENDENCIA] Panel de la sub-intención `tendencia` de Analizar. Dos trazas:
  // REAL mensual y media móvil de 3 meses. Molde = __cnAcumMesInto (:4452), el único pintor
  // mensual multi-traza de la pila.
  // 🔑 Sin tarjeta KPI: aquí no hay un número único que destacar — la respuesta ES la forma de
  //    la curva, y el texto del chat ya da dirección y ritmo.
  function __cnAnzTendHtml(d) {
    if (!d || !d.valores || d.valores.length < 3) return "";
    return __cnPanelMesHtml(d, "cn-tend-mes");
  }

  function __cnTendMesInto(hostEl, d) {
    var meses = d.meses || [], vals = d.valores || [], mm = d.serie_mm || [];
    var prod = String(d.producto || "");
    var unidad = d.unidad || "bbl";
    var nombre = prod.charAt(0).toUpperCase() + prod.slice(1).toLowerCase();
    hostEl.innerHTML =
      '<div class="cn-ins__card"><div class="cn-ins__card-hd"><i class="bi bi-graph-up"></i> ' +
      esc(nombre) + ' · tendencia mensual ' + (d.anio || "") +
      '</div><div class="cn-ins__plot" data-p></div>' +
      '<div class="cn-ins__cap" data-cap></div></div>';
    var elp = hostEl.querySelector("[data-p]");
    if (!vals.length) {
      elp.innerHTML = '<div class="p-2 text-muted small">Sin serie mensual para este producto.</div>';
      return;
    }
    if (!window.Plotly) { elp.innerHTML = '<div class="text-muted small p-2">(Plotly no disponible)</div>'; return; }
    // El gas se grafica en MSCF (÷1e6) y el hover formatea el valor ORIGINAL con __cnGasM (que
    // ya divide) — nunca el ya escalado: ese doble escalado es el bug documentado en :3650-3652.
    var esGas = String(prod).toUpperCase() === "GAS";
    var fmtD = esGas ? __cnGasM : function (v) { return __cnMilesEC(Math.round(v)); };
    var esc1 = function (v) { return (v == null) ? null : (esGas ? v / 1e6 : v); };
    var col = __cnProdCol(prod);
    var traces = [{
      x: meses, y: vals.map(esc1), name: "Real mensual",
      type: "scatter", mode: "lines+markers",
      line: { color: col, width: 2.5, shape: "spline", smoothing: 0.8 },
      marker: { color: col, size: 7 },
      customdata: vals.map(fmtD),
      hovertemplate: "%{x}<br>Real: %{customdata} " + unidad + "<extra></extra>"
    }];
    // La media móvil solo se dibuja si HAY valores. `connectgaps:false` deja el hueco de los
    // primeros 2 meses en blanco: no existe media de 3 meses ahí, y unirlo la inventaría.
    if (mm.some(function (v) { return v != null; })) {
      traces.push({
        x: meses, y: mm.map(esc1), name: "Media móvil 3M",
        type: "scatter", mode: "lines", connectgaps: false,
        line: { color: "#8a978f", width: 2, dash: "dot" },
        customdata: mm.map(function (v) { return v == null ? "—" : fmtD(v); }),
        hovertemplate: "%{x}<br>MM3: %{customdata} " + unidad + "<extra></extra>"
      });
    }
    window.Plotly.newPlot(elp, traces, {
      margin: { l: 62, r: 18, t: 22, b: 30 }, height: 260, hovermode: "x unified",
      showlegend: true, legend: { orientation: "h", y: -0.18, x: 0, font: { size: 11 } },
      xaxis: { title: { text: "Mes", font: { size: 11 } }, tickfont: { size: 11 }, showgrid: false },
      yaxis: {
        title: { text: "Producción (" + (esGas ? "MSCF" : unidad) + ")", font: { size: 11 } },
        tickfont: { size: 10 }, separatethousands: true, gridcolor: "#eef1ef", zeroline: false
      },
      plot_bgcolor: "#fff", paper_bgcolor: "#fff"
    }, { displayModeBar: false, responsive: true });
  }
```

**(b) Registra `analiza_tend` en los TRES sitios.** Los tres, no dos — el panel del punto 1 falló
por saltarse uno.

1. En `__cnPintarPanelCuant`, el ternario **antes** del fallback `: __cnCuantCardHtml(d)`:

```js
             : (panel.tipo === "analiza_tend")    ? __cnAnzTendHtml(d)
```

2. En la línea que llama a `__cnPanelMesCargar` (~:4381):

```js
    if (panel.tipo === "cuant_serie" || panel.tipo === "cuant_var" || panel.tipo === "cuant_acum" || panel.tipo === "analiza_tend") __cnPanelMesCargar(blk, d, panel.tipo);
```

3. En `__cnPanelMesPintar`, la rama final:

```js
    } else if (tipo === "analiza_tend") {
      var ht = blk.querySelector(".cn-tend-mes");
      if (ht) __cnTendMesInto(ht, d);
    }
```

### 3.7 MODIFICAR — `frontend/MainChat/templates/mainchat_layout.html`

Línea 317 (H8). Estado actual `?v=20260903f` → déjalo en `?v=20260903g`:

```html
<script defer src="{{ url_for('static', filename='js/multitab_shell.js') }}?v=20260903g"></script>
```

### 3.8 AÑADIR — `backend/backend/tests/test_analizar_tendencia.py`

```python
"""test_analizar_tendencia.py — sub-intención `tendencia` de Analizar (punto 2 de
inteligencia de tiempo: tipos 4 evolución, 5 declinación, 6 media móvil).

Ningún test toca BD: `_desempeno_fn` se inyecta y el resolver se neutraliza con la fixture
`sin_entidad` (mismo recurso que los 13 tests de test_p50_referencia.py).
"""
import pytest

from app.features.consulta_v2 import respuesta_analizar as _ra
from app.features.consulta_v2.analizar import subrouter as _sr
from app.features.consulta_v2.analizar import tendencia as _t

_MS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def _pts(vals):
    return [{"mes": _MS[i], "num": i + 1, "valor": v} for i, v in enumerate(vals)]


def _fake_desempeno(vals, mes_actual=None, anio=2026):
    """Doble de `desempeno`: devuelve un `ritmo_mensual` con la serie pedida. GAS = ×2 para
    comprobar que el producto explícito elige la serie correcta."""
    n = len(vals)
    def _fn(entidad=None, segmento="ecp", nivel=None, periodo=None):
        return {"encontrada": True, "mes": {"anio": anio}, "ritmo_mensual": {
            "meses": _MS[:n], "meses_num": list(range(1, n + 1)),
            "series": {"CRUDO": list(vals), "GAS": [v * 2 for v in vals]},
            "mes_actual": mes_actual}}
    return _fn


@pytest.fixture
def sin_entidad(monkeypatch):
    """Neutraliza el catálogo → rama GLOBAL (V6/V10). Sin esto los tests pedirían BD."""
    monkeypatch.setattr(_ra._resolver, "resolver_unico", lambda *a, **k: None)


# ---------------- el sub-router ----------------

@pytest.mark.parametrize("frase", [
    "cual es la tendencia de Castilla",
    "a que ritmo esta declinando Castilla",
    "cual es la declinacion de Castilla",
    "muestrame la media movil de Castilla",
    "como viene la produccion de Castilla",
    "Castilla viene cayendo?",
    "la produccion va subiendo o bajando en Castilla",
])
def test_subrouter_manda_a_tendencia(frase):
    assert _sr.sub_intencion(frase) == "tendencia", frase


@pytest.mark.parametrize("frase", [
    "como vamos este mes",
    "vamos a cerrar en meta",
    "cual es la proyeccion de cierre",
])
def test_los_3_casos_del_golden_de_proyeccion_no_se_mueven(frase):
    """Sacar TENDENCIA de _PROY no debe robarle a proyeccion ninguno de sus casos (H2)."""
    assert _sr.sub_intencion(frase) == "proyeccion", frase


def test_tendencia_gana_a_proyeccion_cuando_estan_las_dos():
    assert _sr.sub_intencion("como viene Castilla, vamos a cerrar en meta") == "tendencia"


def test_economia_y_diferidas_siguen_ganando():
    assert _sr.sub_intencion("cual es la tendencia del EBITDA") == "economia"
    assert _sr.sub_intencion("tendencia de las diferidas") == "diferidas"


# ---------------- la lectura ----------------

def test_serie_a_la_baja_sostenida():
    r = _t.leer(_pts([1000, 950, 900, 850, 800]))
    assert r["aplica"] and r["direccion"] == "a la baja"
    assert r["pct_mensual"] < 0 and r["sostenida"] is True


def test_serie_al_alza():
    r = _t.leer(_pts([800, 850, 900, 950, 1000]))
    assert r["direccion"] == "al alza" and r["pct_mensual"] > 0


def test_serie_plana_es_estable():
    r = _t.leer(_pts([1000, 1000, 1000, 1000]))
    assert r["direccion"] == "estable"
    assert r["r2"] == 1.0          # una recta plana la explica perfectamente


def test_ruido_bajo_el_umbral_es_estable():
    """±0.06% mensual es ruido de operación, no una tendencia."""
    assert _t.leer(_pts([1000, 1004, 998, 1006, 1002]))["direccion"] == "estable"


def test_serie_erratica_no_se_declara_sostenida():
    r = _t.leer(_pts([1000, 600, 1100, 500, 900, 400]))
    assert r["direccion"] == "a la baja" and r["sostenida"] is False


def test_anualizado_compone_no_multiplica():
    """-2% mensual son -21.5% anuales, NO -24%. El ×12 exagera la declinación."""
    r = _t.leer(_pts([1000, 980, 960.4, 941.19, 922.37]))
    assert r["pct_mensual"] == pytest.approx(-2.0, abs=0.2)
    assert r["pct_anualizado"] == pytest.approx(-21.5, abs=1.0)


def test_menos_de_3_meses_declina_honesto():
    r = _t.leer(_pts([1000, 900]))
    assert r["aplica"] is False and "variación" in r["texto"]


def test_media_movil_alineada_al_final_con_huecos():
    mm = _t.media_movil([3, 6, 9, 12], 3)
    assert mm[0] is None and mm[1] is None
    assert mm[2] == pytest.approx(6.0)     # (3+6+9)/3
    assert mm[3] == pytest.approx(9.0)     # (6+9+12)/3


def test_media_movil_no_se_calcula_con_3_puntos():
    """Con 3 meses daría UN solo valor: un punto suelto que no es una curva."""
    assert all(v is None for v in _t.leer(_pts([1000, 950, 900]))["serie_mm"])


# ---------------- integración (sin BD) ----------------

def test_he4_el_mes_en_curso_no_entra(sin_entidad):
    """8 meses de serie con mes_actual=8: solo entran los 7 cerrados. El 8º vale 10 y, si
    entrara, hundiría la pendiente y el texto diría 8 meses."""
    r = _ra.responder_con_panel(
        "cual es la tendencia de la produccion",
        _desempeno_fn=_fake_desempeno([1000] * 7 + [10], mes_actual=8))
    assert "7 meses cerrados" in r["mensaje"]
    assert r["panel"]["datos"]["valores"] == [1000.0] * 7


def test_producto_explicito_elige_la_serie_de_gas(sin_entidad):
    """«la tendencia del gas» debe leer la serie GAS (×2 en el fake) y rotular MSCF (V5)."""
    r = _ra.responder_con_panel(
        "cual es la tendencia del gas",
        _desempeno_fn=_fake_desempeno([1000, 950, 900, 850], mes_actual=5))
    assert r["panel"]["datos"]["producto"] == "gas"
    assert r["panel"]["datos"]["unidad"] == "MSCF"
    assert r["panel"]["datos"]["valores"] == [2000.0, 1900.0, 1800.0, 1700.0]


def test_sin_serie_suficiente_no_emite_panel(sin_entidad):
    """Con 2 meses cerrados se declina en texto y NO se abre un bloque en la pila."""
    r = _ra.responder_con_panel(
        "cual es la tendencia de la produccion",
        _desempeno_fn=_fake_desempeno([1000, 900], mes_actual=3))
    assert r["panel"] is None
    assert "variación" in r["mensaje"]


def test_el_fake_se_inyecta_por_el_wrapper_publico(sin_entidad):
    """🔴 V1: `responder` y `responder_con_panel` deben PROPAGAR `_desempeno_fn`. Si solo se
    añadió a `_responder_core`, este test pega contra la BD real y falla."""
    msg = _ra.responder(
        "cual es la tendencia de la produccion",
        _desempeno_fn=_fake_desempeno([1000, 950, 900, 850, 800], mes_actual=6))
    assert "TENDENCIA" in msg and "a la baja".upper() in msg.upper()
```

> ⚠️ Si algún test de integración falla por el intro del LLM, comprueba que
> `CONSULTA_ANALIZA_LLM` esté en `false` en el entorno de test. `_intro` devuelve `''` con el flag
> apagado; encendido intentaría llamar a Ollama.

### 3.9 MODIFICAR — `golden/analizar_golden.yaml` (🔴 V3)

Añade estos **4 casos al final**. El formato es `pregunta` / `entidad` / `sub`, el mismo de los 10
existentes. El golden pasa de 10 a **14** casos.

```yaml

# --- tendencia (2026-09-03, punto 2 de inteligencia de tiempo) ---
# La cabecera de este archivo lo pide: toda corrección verificada entra aquí como regresión
# permanente. «TENDENCIA» resolvía a `proyeccion` y respondía el pace diario del mes.
- pregunta: "¿cuál es la tendencia de Castilla?"
  entidad: "CASTILLA"
  sub: tendencia
- pregunta: "¿a qué ritmo está declinando Rubiales?"
  entidad: "RUBIALES"
  sub: tendencia
- pregunta: "¿cómo viene la producción de crudo?"
  entidad: null
  sub: tendencia
- pregunta: "muéstrame la media móvil de Cusiana"
  entidad: "CUSIANA"
  sub: tendencia
```

---

## 4. Orden de ejecución

| # | Acción | Archivo |
|---|---|---|
| 1 | CREAR el módulo puro | `analizar/tendencia.py` (§3.1) |
| 2 | MODIFICAR vocabulario y precedencia | `analizar/subrouter.py` (§3.2) |
| 3 | AÑADIR la plantilla de texto | `analizar/plantilla.py` (§3.3) |
| 4 | MODIFICAR imports + bloque + **los 3 puntos de entrada** | `respuesta_analizar.py` (§3.4) |
| 5 | MODIFICAR los patrones de Capa 1 | `config/patrones_grupo.yaml` (§3.5) |
| 6 | AÑADIR 4 casos al golden | `golden/analizar_golden.yaml` (§3.9) |
| 7 | CREAR los tests | `tests/test_analizar_tendencia.py` (§3.8) |
| 8 | Validar backend (§6.1, filas 1-4) | — |
| 9 | MODIFICAR el panel (3 registros) | `frontend/static/js/multitab_shell.js` (§3.6) |
| 10 | SUBIR el cache-buster | `frontend/MainChat/templates/mainchat_layout.html` (§3.7) |
| 11 | DOS commits separados, backend y frontend | — |

**Si el paso 8 falla, DETENTE.** No sigas al frontend ni commitees.

---

## 5. Reglas no negociables

1. **CERO modificaciones fuera de este plan.** Si crees que falta algo, DETENTE y repórtalo.
2. **`analizar/tendencia.py` es PURO.** Ni un import de `analisis`, ni de BD, ni `date.today()`.
3. **`_desempeno_fn` se propaga en los TRES puntos de entrada** (V1). Si solo lo pones en
   `_responder_core`, `test_el_fake_se_inyecta_por_el_wrapper_publico` fallará — está para eso.
4. **Los 4 argumentos de `desempeno` van SIEMPRE explícitos** (V7): `entidad=`, `segmento=`,
   `nivel=`, `periodo=`. Nunca posicionales, nunca omitidos.
5. **No tocar `cuantificar/`.** N3 y N4 se quedan como están (H4): ni vocabulario, ni paneles.
6. **No añadir `EVOLUCION`, `MES A MES`, `SUBIO`, `BAJO`, `VARIO`** a `_TEND` ni a los patrones.
7. **HE4** — el mes en curso NUNCA entra en la regresión ni en la media móvil.
8. **Los 3 registros del panel**, no 2. Un panel registrado a medias falla en silencio.
9. **El cache-buster sube en el mismo commit que el JS** (H8). Sin excepción.
10. **Dos commits**, uno por repo. Nunca uno solo.
11. Si un ajuste reactivo se acumula **más de 2 iteraciones** sin resolver, DETENTE y reporta.

---

## 6. Validación

### 6.1 Estática — la corres tú, EXECUTOR

Desde `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend`, PowerShell normal, línea por línea:

| # | Comando | Resultado esperado |
|---|---|---|
| 1 | `uv run pytest tests/test_analizar_tendencia.py -q` | **25 passed** |
| 2 | `uv run pytest -q` | **811 passed, 10 failed** — la suite estaba en 786; los 10 fallos son preexistentes (lista abajo) |
| 3 | `uv run python -c "import inspect; from app.features.consulta_v2.analizar import tendencia as t; s=inspect.getsource(t); print(('import' not in s.split('\"\"\"')[2]) and 'today' not in s)"` | `True` — el módulo es puro |
| 4 | `$env:PYTHONPATH="."; uv run python app/features/consulta_v2/golden/run_golden_analizar.py` | **14/14** |

⚠️ **La fila 4 lleva el comando real** (V2): es una ruta de archivo, no `python -m`. El script fuerza
`CONSULTA_ANALIZA_LLM=false` y usa un `_ejecutivo_fn` FAKE, así que no necesita BD ni LLM.

⚠️ **NO corras `run_golden.py`** (el de clasificación, 92 casos). Puede escalar a Capa 2 (Ollama) y
en una máquina sin Ollama devuelve un resultado engañoso. Va en §6.2, en el servidor de pruebas.

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
| 1 | «¿Cuál es la tendencia de Castilla?» | Dirección, % mensual y % anualizado + curva con media móvil. **Antes: el pace diario del mes** |
| 2 | «¿A qué ritmo está declinando Castilla?» | Lo mismo, con la declinación anualizada |
| 3 | «¿Cómo viene la producción de Castilla?» | Igual — es la forma coloquial |
| 4 | «Muéstrame la media móvil de Castilla» | La curva con la traza punteada MM3 visible |
| 5 | «¿Cuál es la tendencia del gas de Cusiana?» | Serie de GAS y unidad **MSCF**, no bbl (V5) |
| 6 | «¿Cómo vamos este mes?» | La proyección de cierre — **no debe cambiar** |
| 7 | «¿Vamos a cerrar en meta?» | La proyección — **no debe cambiar** |
| 8 | «¿Cómo varió Castilla mes a mes?» | El waterfall de N4 — **no debe cambiar** |
| 9 | «Acumulado de Castilla» | El gauge + curva acumulada — **no debe cambiar** |
| 10 | F12 → Console en todas | 0 errores |

Los casos 6-9 son el control de no-regresión: si alguno cambia, algo se pisó.

Además, en el servidor de pruebas, el gate del clasificador (V2):

```powershell
$env:PYTHONPATH="."; uv run python app/features/consulta_v2/golden/run_golden.py
```

Esperado: **≥90%** (hoy 96%).

---

## 7. Fuera de alcance

- **Punto 3** — comparación de periodos (MoM/DoD/YoY, real vs programa en el tiempo). Plan aparte.
- **Punto 4** — quiebre temporal y racha/desde-cuándo. Plan aparte.
- **Tendencia a grano DÍA.** Solo mensual: una regresión sobre 30 días con huecos de reporte daría
  una pendiente que no significa nada.
- **Tocar N3/N4 de Cuantificar** (H4): ni vocabulario, ni paneles, ni el waterfall.
- **Proyección hacia adelante** (extrapolar la recta a meses futuros). El tipo 7 —«proyección/
  cierre»— ya lo cubre `sub == "proyeccion"` con el pace diario, que es fuente distinta y más fiable
  dentro del mes.
- **Retirar «TENDENCIA» del YAML de patrones**: ahí se queda, enruta al grupo correcto.
- **La recta de tendencia dibujada en el panel.** El v1 la proponía como tercera traza; se retira:
  con REAL + media móvil la forma ya se lee, y una tercera línea sobre 7 puntos satura el gráfico.
  El número (% mensual) va en el texto, que es donde se puede leer.
- El hueco de reporte diario de mayo (17/31) y junio (14/30) en Pruebas: es de ingesta, no de
  código, y no afecta al REAL mensual que esta tendencia usa.

---

> **Nota de alcance ampliado respecto al v1:** GAS y BLANCOS **sí** entran (V5). El v1 los mandaba a
> «fuera de alcance» sin saber que `_producto_explicito` y `_UNIDAD` ya existían en el propio módulo.
