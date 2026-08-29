# Plan v2 · P50 como REFERENCIA en ANALIZAR — declinar honesto por nivel + ruta a vicepresidencia

**Fecha:** 2026-08-13 · **Planner:** Claude · **Ejecuta:** Executor
**Estado:** **v2 AUDITADO** — 6 hallazgos de la ronda adversarial corregidos ANTES de codificar (§8)

**Cobertura: rutas de respuesta entrada 4 → salida 5** (se AÑADE `referencia`; las 4 existentes
—causal, proyeccion, diferidas, economia— quedan intactas). Ninguna se retira.

---

## 1. CONTEXTO — el defecto que se corrige

Ante **«dame el P50 para el campo Rubiales»**, el chat responde HOY (ejecutado 2026-08-13):

```
📊 RUBIALES · Mayo 2026
Crudo cerró al 95.6% del presupuesto — Alineado, con un valle del 1 de mayo al 3 de mayo.
⟦Dónde está el faltante⟧
El campo con mayor faltante concentra el 100.0%:
  · RUBIALES −566.752 bbl
...
```

**El usuario pidió P50 y recibió PPTO.** El patrón `P50\b` solo sirvió para ENRUTAR a `analizar`;
nunca se usó como referencia. No hay advertencia del cambio de vara.

Modo de fallo más peligroso del motor: entidad correcta, mes correcto, cifras correctas, causas
reales — **y contesta una pregunta distinta a la formulada.** No parece un error.

**Precedente que se viola:** P50 y PPTO NO son intercambiables — verificado 2026-07-30, *el gas
cumple el P50 (101,9%) e incumple el presupuesto (76%)*. Misma producción, veredictos opuestos.

---

## 2. AUDITORÍA — hechos medidos contra la BD (NO re-verificar, SÍ respetar)

Medido 2026-08-13, Postgres local `daily_report_prod`, `reporte_id=18` (fecha_reporte 2026-05-18).

### A1 · El P50 NO existe a nivel campo — en ninguna de las 16 hojas

| Fuente | Granularidad más fina | ¿campo? |
|---|---|---|
| `P50 Acumulado` t1-t4 | `producto` | ❌ |
| `REPORTE_PRESIDENT` t2 | `entidad` (Crudo/Gas/Blancos/Ecopetrol/Filiales/Upstream) | ❌ |
| `NEW MES-AÑO` **t8 «P50 ECP»** | **`vice` × `producto`** ← el más fino que existe | ❌ |
| `CALCULO DE TRIMESTRE` t5-t7 | trimestre | ❌ |
| `P50 Quemado` t1 | tiene `activos`, pero `escenario='PPTO'` — **no es P50** | ❌ |
| `PROGRAMA` / `BDP_Programa` | **132 campos**, pero `escenario=NULL` (programa operativo) | ❌ |

**Confirmación estructural:** `core.dim_escenario` = 4 filas exactas (`CONTABLE`, `PPTO`,
`OPERATIVO`, `REAL`). **P50 NO es un escenario del modelo.**
⇒ El declinar NO es «falta ingerir». Es que **la cifra no se define a ese nivel**.

### A2 · Los 4 cuadrantes (nivel × referencia)

| Nivel | Referencia | ¿Existe? | Fuente |
|---|---|---|---|
| Campo | Presupuesto | ✅ mayo | `analisis.ejecutivo` (ya en uso) |
| Vicepresidencia | P50 | ⚠️ **solo hasta abril** | `NEW MES-AÑO` t8 + t2 |
| Empresa (ECP) | P50 | ✅ mayo | `REPORTE_PRESIDENT` |
| **Campo** | **P50** | ❌ **NO EXISTE** | — |

### A3 · 🔑 El REAL por vicepresidencia termina en ABRIL

| Tabla | Cobertura |
|---|---|
| `NEW MES-AÑO` t8 (P50) | ene → **dic** |
| `NEW MES-AÑO` t2 (REAL PROMEDIO MES) | ene → **abr** |

Join t8⟕t2 sobre `fecha='2026-05-31'` → **SIN DATO en las 12 filas** (medido).
⇒ **La fecha se LEE del dato, JAMÁS se hardcodea** (R5).

### A4 · Cifras de referencia (abril-2026, CRUDO, bbl) — para tests

```
VICE      REAL        P50       %          VICE      REAL       P50       %
GOR     143669     154700    92.9 ▼        GCT      13890     13242   104.9 ▲
GAA     105201     101835   103.3 ▲        GAN      11864     12401    95.7 ▼
GLH      88944      93784    94.8 ▼        DFL       9670      8622   112.2 ▲
GNS      40740      40602   100.3 ▲        PRP       5363      6249    85.8 ▼
GRM      32740      34777    94.1 ▼        CPV       2567      2945    87.2 ▼
GPA      22764      25026    91.0 ▼        ────────────────────────────────
GTA      15134      15623    96.9 ▼        SUMA    492549    509804    96.6  → 8 de 12 bajo P50
```

**Reconcilia** con el cumplimiento corporativo ⇒ el corte no inventa otra realidad.
⚠️ **Escala = bbl, NO kbpe** (el encabezado del panel es kbpe). Rotular siempre (R6).
⚠️ **GXO está en t2 (REAL) y NO en t8 (P50)** → un `LEFT JOIN` desde t8 lo omite en silencio (R7).

### A5 · 🔑 El mapeo campo→VP cubre solo el 58% — ACOTA EL ALCANCE

`core.map_campo_robustez`: **139 campos, 80 con `rob_vicepresidencia` (58%)**. Los 59 sin VP son
**terceros** (Parex, SierraCol, Frontera, Hocol) — la tabla modela el universo ECP-operado (S28).

```
t8 vice            : CPV DFL GAA GAN GCT GLH GNS GOR GPA GRM GTA GXO PRP
en robustez (11/13): CPV DFL GAA GAN GCT     GOR GPA GRM GTA GXO PRP
NO en robustez     :                 GLH GNS        ← 2 códigos huérfanos
```

Campos por VP: GPA 27 · GAA 14 · GRM 11 · DFL 4 · GTA 4 · **GOR 2** · GAN 2 · GCT 2 · CPV 1 · GXO 1 · PRP 1.
⇒ **La ruta «P50 de tu VP» NO se puede ofrecer siempre** (D4/M6).

### A6 · RUBIALES → GOR (confirmado)

```
('RUBIALES','RUBIALES','ECOPETROL',true,'RUBIALES','RUBIALES','POE','GOR')
```
`rob_gerencia='POE'`, `rob_vicepresidencia='GOR'`. **Usar `rob_vicepresidencia`, NUNCA
`rob_gerencia`** (level-shift ya documentado).
⚠️ `core.dim_vicepresidencia` (GGN/GPU/GOX/GGS/VAS/VFS/VEX/VRC/VAO/VRO/VPI) **no comparte NI UN
código con t8** (intersección = ∅). Otra taxonomía. **No usarla.**

### A7 · Enrutamiento actual (medido con `clasificar_capa1`)

Las 3 formas («dame el P50 para el campo rubiales», «cual es el P50 de Rubiales?», «Que campos
estan por debajo del P50?») → `grupo=analizar`, `dominio=fuerte`, `sub=causal`, `patrones=['P50\b']`,
**sin LLM**. El bug vive en `causal`, que responde contra PPTO.

---

## 3. HALLAZGOS DE LA AUDITORÍA ADVERSARIAL (§0.2) — corrigen el plan v1

🔴 **Estos 6 puntos invalidaron supuestos del v1. Son la razón de ser de esta v2.**

| # | Hallazgo (verificado en código) | Corrección aplicada |
|---|---|---|
| **H1** | 🔴 **`responder()` NO es el punto de entrada.** El dispatcher real es `_responder_core()`; `responder()` es un wrapper compat que devuelve `str`, y `maquina_q` usa **`responder_con_panel()`**. El v1 decía «añadir la rama al dispatcher» sin nombrarlo → el Executor pudo tocar el wrapper. | §5 Paso 3 nombra **`_responder_core`** explícitamente y prohíbe tocar los 2 wrappers. |
| **H2** | 🔴 **El orden del dispatcher NO es el del subrouter.** `_responder_core` resuelve la **entidad ANTES** de ramificar por sub-intención, y las ramas `diferidas`/`economia` van **después**. Si `referencia` se inserta antes de resolver entidad, no sabría el nivel; si va después del bloque `ejecutivo`, paga un cálculo que descarta. | §5 Paso 3 fija la posición **exacta**: bloque «3c», tras `economia` y **ANTES** del paso 4 (`fn(...)` del ejecutivo). |
| **H3** | ⚠️ **El drill de ANALIZAR ya consume `PROYECCION`/`CIERRE`/`CAMPO(S)`/`DETALLE`.** Mi mensaje del declinar decía «Contra el **presupuesto**…» y «el P50 de su **vicepresidencia**» — ninguna de las 2 palabras está en el drill ⇒ **la respuesta del usuario habría caído a `None`** (sin continuación). | §4 M9 + §5 Paso 4: añadir `PRESUPUESTO`/`PPTO` y `VICEPRESIDENCIA`/`VP` al drill, mapeando a destinos válidos. |
| **H4** | ⚠️ **`_AFIRM` tras `referencia` daría `proyeccion`.** La rama `else` del drill hace `"causal" if sub=="proyeccion" else "proyeccion"` — con `sub='referencia'` un «sí» devolvería una PROYECCIÓN, no lo ofrecido. | §5 Paso 4: rama explícita para `sub=='referencia'`. Refuerza M5 (nunca cerrar en sí/no). |
| **H5** | ⚠️ **`nivel_soportado` ya existe 2 veces** (`diferidas.py:37`, `economia.py:20`) con firma idéntica `(nivel) -> bool` y el patrón «la regla de nivel vive en el módulo» (FC-3/H8). Mi v1 la reinventaba con otro nombre de constante. | §5 Paso 2 replica la firma y el estilo EXACTOS (`_NIVELES_OK`), para que el dispatcher la use igual que las otras 2. |
| **H6** | ⚠️ **`norm()` NO quita `?`/`¿`.** Está documentado (HE7, bug real 2026-08-02): un token pegado al signo no calza. El v1 aceptaba `"P50" in t` sin más. | §5 Paso 1: match por token con `strip(_PUNCT)`, reusando el patrón de `_producto_explicito`. |

**Oportunidad de mejora detectada (no es defecto):** `_responder_core` ya acepta inyección de
dependencias (`_ejecutivo_fn`, `_diferidas_fn`, `_economia_fn`, `_split_fn`) para que los tests no
toquen BD/LLM. **El módulo nuevo debe seguir ese patrón** (`_p50_fn`, `_vp_fn`) → tests sin BD.

---

## 4. DISEÑO

### 4.1 Principio rector

> **El nivel decide, no la palabra.** «P50» no significa «análisis causal»: significa que el
> usuario eligió una REFERENCIA. Si el nivel resuelto la soporta → dar la cifra. Si no → declinar
> y ofrecer solo las vecinas que EXISTAN.

### 4.2 Sub-intención `referencia` — precedencia

```
economia > diferidas > proyeccion > referencia > causal
```

**Debajo de `proyeccion`** a propósito: «¿vamos a llegar al P50?» debe seguir siendo proyección.
Solo las preguntas que piden **la cifra** caen en `referencia`.

**Disparo:** token `P50` presente **Y** sin señal causal explícita
(`POR QUE`, `A QUE SE DEBE`, `EXPLICA`, `CAUSAS DE`, `DETRACTORES`, `QUE PASO CON`, `PESA(N)`).

| Pregunta | sub-intención |
|---|---|
| «dame el P50 para el campo rubiales» | `referencia` ← NUEVO |
| «cuál es el P50 de crudo?» | `referencia` ← NUEVO |
| «qué campos están por debajo del P50?» | `referencia` ← NUEVO |
| «por qué estamos bajo el P50?» | `causal` (sin cambio) |
| «vamos a llegar al P50?» | `proyeccion` (sin cambio) |
| «cómo va el EBITDA?» | `economia` (sin cambio) |

### 4.3 Matriz de respuesta

| Nivel resuelto | ¿P50? | Respuesta |
|---|---|---|
| `None` (global ECP) | ✅ | **Cifra** desde `REPORTE_PRESIDENT` |
| `vicepresidencia` | ⚠️ hasta abril | **Cifra**, periodo declarado |
| `campo` / `activo` | ❌ | **DECLINAR** + opciones |
| `gerencia` / rama B / otro | ❌ | **DECLINAR** sin opción de VP |

### 4.4 El mensaje del declinar — APROBADO POR EL USUARIO 2026-08-13

```
No tengo un P50 para RUBIALES. El P50 es un compromiso corporativo: se pacta
para Ecopetrol como un todo y el desglose más fino que existe es por
vicepresidencia — nunca por campo.

Lo que sí tengo de RUBIALES:

  · Contra el presupuesto, mayo — cerró al 95,6%, con un faltante de
    566.752 bbl frente a la meta del mes.

  · El P50 de su vicepresidencia (GOR) — en abril, el último mes con real
    por vicepresidencia, quedó en 92,9%.

Dime cuál te sirve: el presupuesto o la vicepresidencia.
```

**Reglas NO negociables:**

| # | Regla | Por qué |
|---|---|---|
| M1 | La NEGACIÓN va **primero**, antes de toda cifra | Un número primero hace asumir que ése es el P50 |
| M2 | Decir **por qué** («se pacta para ECP como un todo») | Distingue LÍMITE del negocio de HUECO de datos |
| M3 | **Nombrar el nivel** («el Campo X») | D-A5; nombres duales resuelven a Campo |
| M4 | Cada opción **declara su periodo** | Son meses distintos (mayo vs abril) — A3 |
| M5 | **NUNCA cerrar en pregunta sí/no** | Un «sí» cae en `_AFIRM` de `_continuacion` y devuelve otra cosa (H4) |
| M6 | La opción de VP **se OMITE** si no existe VP ofrecible | A5: 58% de cobertura, GLH/GNS huérfanos |
| M7 | Sin veredictos, solo números | Umbrales de chat y panel discrepan (defecto ya corregido) |
| M8 | `panel = None` | Es un declinar; el artifact grafica un P50 que para ese campo NO existe → texto y gráfico se contradirían |
| **M9** | **El cierre debe usar palabras que el drill RECONOZCA** | H3: «presupuesto»/«vicepresidencia» deben existir en `_continuacion` o la respuesta muere en `None` |

**Si M6 se activa** (sin VP): queda UNA opción y el cierre pasa a
`«Si quieres el detalle contra el presupuesto, dímelo.»` — sigue cumpliendo M5 y M9
(`PRESUPUESTO` estará en el drill).

---

## 5. IMPLEMENTACIÓN

### Paso 1 · `analizar/subrouter.py`

**Ruta:** `INGESTA/Rep_Prod/backend/app/features/consulta_v2/analizar/subrouter.py`

- Añadir arriba (junto a las otras constantes):
```python
_PUNCT = "¿?¡!.,;:()[]{}\"'`"
_REFERENCIA = ("P50",)
_CAUSAL_EXPL = ("POR QUE", "A QUE SE DEBE", "EXPLICA", "CAUSAS DE",
                "DETRACTORES", "QUE PASO CON", "PESAN", "PESA")
```
- En `sub_intencion()`, **después** del bloque `_PROY` y **antes** del `return "causal"`:
```python
    # P50 pedido como REFERENCIA (una cifra), no como tema causal. Token exacto: norm() NO
    # retira '?'/'¿' (HE7) → "…del P50?" no calzaría con un `in` a secas.
    toks = {w.strip(_PUNCT) for w in t.split()}
    if any(k in toks for k in _REFERENCIA) and not any(k in t for k in _CAUSAL_EXPL):
        return "referencia"
```
- ⚠️ `_CAUSAL_EXPL` se compara contra `t` (frases con espacios), `_REFERENCIA` contra `toks`
  (token suelto). **Son dos comparaciones distintas a propósito.**
- Actualizar el docstring de `sub_intencion` (hoy enumera 4 valores).

### Paso 2 · `analizar/p50_referencia.py` — NUEVO

**Ruta:** `.../consulta_v2/analizar/p50_referencia.py`

```python
_NIVELES_OK = (None, "vicepresidencia")

def nivel_soportado(nivel: str | None) -> bool
    """El P50 solo se define global (ECP) o por vicepresidencia (NEW MES-AÑO t8).
    campo/activo/gerencia/operador/fuente -> False. Misma firma que
    diferidas.nivel_soportado / economia.nivel_soportado (FC-3/H8)."""
    return nivel in _NIVELES_OK

def vp_de_campo(campo: str) -> str | None
    """BD. core.map_campo_robustez -> rob_vicepresidencia.
    ⚠️ rob_vicepresidencia, NUNCA rob_gerencia (A6). None si no está o no tiene VP (59/139, A5)."""

def p50_por_vp(vice: str, producto: str = "CRUDO") -> dict | None
    """BD. Join NEW MES-AÑO t8 (P50) ⟕ t2 (REAL) por (reporte_id, fecha, dims).
    Devuelve {'vice','producto','fecha','real','p50','pct'} de la ÚLTIMA fecha con AMBOS
    valores (hoy 2026-04-30, A3 — LEÍDA del dato, nunca hardcodeada), o None si la VP no
    está en t8 (GLH/GNS, A5) o no hay REAL."""

def formatear_declinar(entidad, nivel, ppto_pct, ppto_gap, unidad, vp_info) -> str
    """PURA. Mensaje de §4.4 respetando M1-M9. vp_info=None -> omite la 2ª opción (M6)."""
```

**Reglas de implementación:**

- **R-A · Caché en proceso OBLIGATORIA** para ambas funciones de BD. Precedente:
  `analizar/diferidas.py::_SPLIT_CACHE` (10,96 s → 0,0000 s). **Acotar SIEMPRE por
  `reporte_id`**: un `dims->>'x'` sin esa cláusula hace scan de 62M filas (medido: timeout >120 s).
- **R-B · Los errores NO se cachean** (transitorios); «sin datos» sí. Igual que `_SPLIT_CACHE`.
- **R-C · El cuerpo lo escribe PYTHON, nunca el LLM.** `intro_valido` rechaza todo texto del LLM
  con dígitos → un mensaje con cifras redactado por Gemma sería descartado. Precedente:
  `analizar/plantilla.py`.
- **R-D · Formato es-CO reusando helpers existentes** (`cuantificar/validador.py::fmt_valor` o el
  de `plantilla.py`). **No escribir un formateador nuevo.**
- **R-E · Inyección de dependencias** (`_p50_fn`, `_vp_fn`) siguiendo el patrón que
  `_responder_core` ya usa → tests sin BD.

### Paso 3 · `respuesta_analizar.py` — 🔴 POSICIÓN EXACTA (H1+H2)

**Ruta:** `.../consulta_v2/respuesta_analizar.py`

- **Editar `_responder_core()`** — NO `responder()` ni `responder_con_panel()` (son wrappers; H1).
- Añadir import: `from app.features.consulta_v2.analizar import p50_referencia as _p50`.
- Añadir los params de inyección `_p50_fn=None, _vp_fn=None` a `_responder_core` **y propagarlos
  en los DOS wrappers** (ambos reenvían todos los `_*_fn`).
- **Insertar el bloque nuevo como «3c»**: después del bloque `if sub == "economia":` y
  **ANTES** del comentario `# 4) Motor: ejecutivo con args explícitos` (H2).

```python
    # 3c) REFERENCIA (P50 pedido como cifra). El P50 NO se define por campo/activo (A1): a esos
    #     niveles se declina y se ofrecen las vecinas que EXISTAN (M6). Va ANTES del paso 4 para
    #     no pagar `ejecutivo` cuando la respuesta es un declinar... salvo que SÍ lo necesite
    #     para el dato de presupuesto (ver abajo).
    if sub == "referencia":
        if _p50.nivel_soportado(nivel):
            ...  # cifra ECP-global o por VP  (usa _p50_fn)
        # nivel NO soportado -> declinar. Necesita el % vs PPTO del campo => sí llama a `fn`,
        # pero SOLO aquí y con el mismo patrón del paso 4 (pulir=False).
        ...
        return {"mensaje": mensaje, "panel": None}
```

- El envoltorio cordial se aplica igual que las otras ramas:
  `respuesta_base.envolver(intro, cuerpo, cierre)` con `intro = _intro(alcance, usuario)`.
- **El `cierre` de esta rama NO puede ser `_CIERRE` ni `_CIERRE_PROY`** (ambos ofrecen otra cosa).
  Definir constante nueva junto a ellas.

### Paso 4 · `maquina_q.py` — drill y memoria (H3+H4)

**Ruta:** `.../consulta_v2/maquina_q.py`

**(a) Drill de ANALIZAR** (~línea 125-140). En la cadena de `elif`, **antes** de la rama `_AFIRM`:
```python
        elif any(k in t for k in ("PRESUPUESTO", "PPTO")):
            destino = "causal"          # el análisis vs PPTO es la ruta causal existente
        elif any(k in t for k in ("VICEPRESIDENCIA", "VP")):
            destino = "referencia"
```
**(b) Rama `_AFIRM`** — hoy `destino = "causal" if ctx.get("sub")=="proyeccion" else "proyeccion"`.
Añadir ANTES de esa línea:
```python
            if ctx.get("sub") == "referencia":
                destino = "causal"      # tras el declinar, "sí" = el detalle vs presupuesto
```
**(c) Reescritura** — añadir el destino `referencia` al bloque de reescrituras:
```python
        if destino == "referencia":
            return f"cual es el p50 de la produccion {pieza_a}{cola_a}".strip()
```
⚠️ **Toda reescritura lleva «produccion»** (vocabulario FUERTE del filtro de dominio) → enruta por
regex sin gastar LLM. Regla ya establecida.

**(d) Memoria:** el guardado de ctx de ANALIZAR (~línea 470) llama a
`_subrouter_analizar.sub_intencion(efectivo)` → **`sub='referencia'` se guarda solo**. No tocar.

🔴 **NO reordenar los drills existentes.** Está documentado que *el orden ES la corrección*
(3 bugs reales por colisión el 2026-08-02).

---

## 6. TESTS

**Archivo NUEVO:** `INGESTA/Rep_Prod/backend/tests/test_p50_referencia.py`

### Puros (sin BD, sin LLM)

| # | Caso | Espera |
|---|---|---|
| T1 | `sub_intencion("dame el p50 para el campo rubiales")` | `"referencia"` |
| T2 | `sub_intencion("por que estamos bajo el p50?")` | `"causal"` |
| T3 | `sub_intencion("vamos a llegar al p50?")` | `"proyeccion"` |
| T4 | `sub_intencion("como va el ebitda?")` | `"economia"` |
| T5 | `sub_intencion("que campos estan por debajo del p50?")` | `"referencia"` |
| **T6** | `sub_intencion("cual es el P50?")` ← **con signo pegado** | `"referencia"` (guard de H6) |
| T7 | `nivel_soportado("campo")`/`("activo")`/`("gerencia")` | `False` |
| T8 | `nivel_soportado(None)`/`("vicepresidencia")` | `True` |
| T9 | `formatear_declinar(..., vp_info=None)` | NO menciona vicepresidencia (M6) |
| T10 | `formatear_declinar(...)` completo | 1ª línea = NEGACIÓN (M1) |
| T11 | `formatear_declinar(...)` | NO termina en `?` de sí/no (M5) |
| T12 | `formatear_declinar(...)` | Contiene el NIVEL, «el Campo» (M3) |
| T13 | `formatear_declinar(...)` | Ambas opciones nombran su mes (M4) |
| **T14** | `formatear_declinar(...)` | El cierre contiene `presupuesto` y/o `vicepresidencia` (M9/H3) |
| **T15** | `_responder_core(..., sub referencia, _p50_fn/_vp_fn inyectados)` | `panel is None` (M8) |

### Con BD (marcar `skipif` si no hay Postgres)

| # | Caso | Espera |
|---|---|---|
| T16 | `vp_de_campo("RUBIALES")` | `"GOR"` (A6) |
| T17 | `vp_de_campo("CAJUA")` | `None` (tercero, A5) |
| T18 | `p50_por_vp("GOR","CRUDO")` | `fecha=2026-04-30`, `pct≈92.9` (A4) |
| T19 | `p50_por_vp("GLH","CRUDO")` | `None` (GLH no está en robustez, A5) |

### No-regresión OBLIGATORIA

- `pytest` completo. Baseline **397**.
  ⚠️ **4 fallos PREEXISTENTES** en `test_analisis_tarjetas_kpi` y `test_conteo_jerarquia`
  (verificados con `git stash` el 2026-08-12). **No son regresión.** Confirmar que siguen siendo
  **exactamente esos 4**.
- `run_golden.py` → **34/34** (este plan NO toca `patrones_grupo.yaml`; si se mueve, algo se rompió).
- `run_golden_analizar.py` → **10/10**.
- `test_analizar.py` → **27/27** (las 4 sub-intenciones previas intactas).

---

## 7. VERIFICACIÓN

### Dev (SOLO estático — regla del proyecto: cero LLM/backend, RAM 8 GB)

1. `py_compile` de los 4 archivos tocados.
2. `pytest` (los puros no requieren BD).
3. Consultas puntuales a Postgres en proceso aislado, con `SET statement_timeout` y acotadas
   por `reporte_id`.
4. `git diff --stat` → confirmar que **NO** se tocaron `respuesta_cuantificar.py`,
   `respuesta_jerarquizar.py`, `patrones_grupo.yaml` ni frontend.

### Servidor de pruebas (usuario)

| # | Pregunta | Espera |
|---|---|---|
| V1 | «dame el P50 para el campo Rubiales» | Declinar §4.4 con GOR y ambos periodos |
| V2 | «cuál es el P50 de crudo?» | **Cifra** ECP-global (NO declinar) |
| V3 | «dame el P50 de Cajúa» | Declinar **sin** opción de VP (M6) |
| V4 | «por qué estamos bajo el P50?» | Causal de siempre — sin regresión |
| V5 | «vamos a llegar al P50?» | Proyección de siempre — sin regresión |
| V6 | «cuánto produjo Rubiales en mayo?» | Cuantificar intacto |
| V7 | Tras V1, responder «el presupuesto» | Va a causal, **no** a un acumulado (H3/M9) |
| V8 | Tras V1, responder «la vicepresidencia» | Va a la cifra por VP (H3) |
| V9 | Tras V1, responder «sí» | Va a causal, **no** a proyección (H4) |

⚠️ **Recargar la página antes de V1**: `__cnHistory` guarda HTML ya renderizado y `__cnReplay` lo
repinta sin volver a llamar al backend.

---

## 8. ORDEN DE EJECUCIÓN

1. Paso 1 + T1-T6 → confirmar enrutamiento **antes** de escribir lógica.
2. Paso 2 + T7-T14 (puros).
3. T16-T19 (BD) → confirmar que las funciones de datos devuelven lo de §2.
4. Paso 3 (posición exacta H2) + T15.
5. Paso 4 (drill) + V7-V9 en local si es posible.
6. No-regresión completa (§6).
7. Commit. **NO pushear** hasta que el usuario verifique V1-V9.

---

## 9. DECISIONES Y RIESGOS

| # | Decisión | Razón |
|---|---|---|
| **R1** | **NO mover `P50\b`** de `analizar` a `cuantificar` | `precedencia_colision:[analizar,cuantificar,jerarquizar]` está diseñada para que las señales mixtas ganen hacia analizar («cuánto nos falta para la meta» → analizar). `META\b`/`DETRACTORES` ya se retiraron de anclados el 2026-08-02 por disparar sobre temas ajenos. Tocar el enrutamiento arriesga el golden de 34 para resolver algo que una sub-intención resuelve de forma ADITIVA. |
| **D2** | Vocabulario `COMPROMISO`/`RETO`/`CIERRE DE BRECHAS` **fuera de alcance** | Hoy caen en OUT (`grupo=None`) pese a `dominio='fuerte'`. Épica aparte, y hoy inútil: el RETO **es idéntico al P50** en los 12 reportes medidos. |
| **D3** | **Sin panel nuevo** | Declinar → `panel=None` (M8). La ruta VP podría graficarse reusando `__cnRankDotHtml`, pero es frontend y va en otro plan. |
| **D4** | La ruta VP se ofrece **solo si existe** | A5. Ofrecer un camino que muere al elegirlo es peor que no ofrecerlo. |
| **R5** | ⚠️ El REAL por VP se congela en abril | **La fecha se lee del dato, JAMÁS se hardcodea.** Si t2 nunca avanza, la ruta envejece en silencio. |
| **R6** | ⚠️ Escalas distintas (bbl vs kbpe) | El corte VP está en bbl; el encabezado del panel en kbpe. **Rotular siempre.** |
| **R7** | GXO en t2 y no en t8 | `LEFT JOIN` desde t8 lo omite en silencio. No afecta al declinar (consulta UNA VP); sí a un futuro listado. Anotado. |
| **R8** | ⚠️ El declinar **sí llama a `ejecutivo`** | Necesita el % vs PPTO del campo. Usar `pulir=False` como el paso 4, o se cuelga 180 s con Gemma en 139 (RA-1). |

---

## 10. FUERA DE ALCANCE

- Vocabulario del compromiso en el clasificador (D2).
- Panel/gráfico de P50 por vicepresidencia (D3).
- El artifact `cierre_brechas.html` — su caso nativo es **ECP global**, no campo.
- **Bloqueo de fondo:** el RETO CORPORATIVO es **idéntico** al P50 (12 reportes: 0 diferencias,
  máx 0; y `compromiso == base_p50` en las 6 entidades de `REPORTE_PRESIDENT`). Mientras siga así,
  «¿cumplimos lo que ADEMÁS prometimos?» **no tiene dato que la responda** — y eso no se arregla
  con código.
