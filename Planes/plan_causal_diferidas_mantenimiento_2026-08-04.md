# Plan ejecutable v2 AUDITADO — CAUSA causal con split Diferidas/Mantenimiento (histórico rotulado) + ACCIÓN atada

**Cobertura de datos: sin cambios** — no se toca DDL, ni ETL, ni esquema, ni se crea endpoint. Se lee
una columna YA existente (`CAUSE_NIVEL3`) de una BD YA usada (`AVM_DATADIF`). Backend-only (la
respuesta de Analizar es un string que la burbuja v2 ya pinta — sin cambios de JS/CSS).

> **v2:** reformulado tras una ronda de auditoría contra el código y la BD reales (§9 · A1-A6).
> El hallazgo A1 (rendimiento) cambió el diseño: el split **debe ir cacheado** o degradaba el chat.

---

## 0. Contexto (para un Executor sin memoria del proyecto)

El chat "Motor Q v2" (FastAPI, `INGESTA/Rep_Prod/backend/`) clasifica preguntas en 4 grupos. El grupo
**Analizar** responde causales ("¿cuál es la causa del gap de crudo?"). Su respuesta la arma
`analizar/plantilla.py::causal()` con bloques HECHO / CAUSA / ACCIÓN / DELTA por producto, VERBATIM
desde el motor `analisis.ejecutivo` (regla madre: **Python calcula, el LLM solo redacta un intro
cordial aparte**).

**Hoy** la CAUSA lista los CAMPOS que concentran el faltante del mes (REAL vs PPTO). El usuario pidió
asociar la CAUSA a dos factores del negocio y que la ACCIÓN dependa de ellos:
- **Diferidas** = dejar de producir **NO** programado.
- **Mantenimiento** = dejar de producir **programado**.

**Auditoría de datos (verificada contra la BD real, 2026-08-04):**
- `data/ECP_DIFERIDAS/ECP_DIFERIDAS.db` → tabla `AVM_DATADIF`, **1.142.599 filas**, ~954 MB, **NO
  versionada en git**. Columna **`CAUSE_NIVEL3`** con valores **`'Planeada'`** (= Mantenimiento),
  **`'No planeada'`** (= Diferidas), más `'Control de Producción'` y `NULL` (residuales → se ignoran).
- Volúmenes históricos globales CRUDO (`ACEITE_PERDIDO`): **No planeada 19.546.432 bbl** ·
  **Planeada 6.299.195 bbl** → **75,6 % / 24,4 %**.
- 🔴 **LÍMITE DURO:** `AVM_DATADIF` va de **2023-01-01 a 2025-07-30** — **0 filas en 2026**. El análisis
  causal es del mes en curso (mayo-2026). **No hay solape temporal** → el split SOLO puede presentarse
  como **CONTEXTO HISTÓRICO ROTULADO**, nunca como la causa del gap del mes.
- No existe fuente de "mantenimiento" del mes en curso (la pill "Mantenimientos" del panel es un mock).

**Decisión del usuario (opción A):** añadir el split histórico como contexto explícitamente rotulado y
atar la ACCIÓN al factor dominante — **sin** tocar la CAUSA del mes (campos), que es lo único real de
mayo-2026.

`consulta_v2` corre en un proceso FastAPI **separado** del Flask del app padre → el SQLite se lee
DIRECTO (nunca por HTTP). `analizar/diferidas.py` ya tiene el ancla de ruta y el contrato de
degradación ("si la BD falta → `sin_datos`, nunca truena").

---

## 1. Objetivo

Que la respuesta causal, para el/los producto(s) analizados (CRUDO/GAS), añada:
1. Una línea **CONTEXTO · {producto}** con el split histórico No planeado (diferidas) vs Planeado
   (mantenimiento), en % y volumen, **rotulada como histórica** (2023-2025, no el mes en curso).
2. Una **cláusula en la ACCIÓN** atada al factor dominante.

Degradación total: sin BD de diferidas (p. ej. **139, donde la BD no está subida**), o sin diferidas en
el alcance → respuesta **idéntica a hoy**. Nunca truena, nunca bloquea.

---

## 2. Prerequisitos

- Trabajar desde `INGESTA/Rep_Prod/backend`. Todo comando Python: `PYTHONPATH="$(pwd)" uv run ...`
  (si no: `ModuleNotFoundError: No module named 'app'`).
- Python solo vía `uv` (no hay `python` utilizable directo).
- **REGLA DE RAM (dev):** solo estáticos — `py_compile`, `pytest`. **NO** arrancar backend, **NO**
  llamar Ollama/LLM, **NO** navegador. Lo vivo lo verifica el usuario en el servidor de pruebas.
- La BD de diferidas **sí existe en dev** (953 MB) → V4 (BD real) es corrible en dev.

---

## 3. Inventario de archivos (rutas relativas a `INGESTA/Rep_Prod/backend/`)

| Archivo | Cambio |
|---|---|
| `app/features/consulta_v2/analizar/diferidas.py` | + `split_planeado()` **con caché** (nueva, al final) |
| `app/features/consulta_v2/analizar/plantilla.py` | + `_split_lineas()` + inyección en `causal()` (2 puntos) |
| `app/features/consulta_v2/respuesta_analizar.py` | + param `_split_fn`; causal path computa `split` |
| `tests/test_analizar.py` | + 4 tests nuevos **y** blindaje de 4 tests existentes (A2) |

**NO tocar:** `impacto_historico` (lo usa la sub-intención `diferidas`; debe quedar byte-idéntico), DDL,
ETL, la BD SQLite (no crear índices), `analisis/api.py`, frontend, golden, `maquina_q.py`, ni las otras
sub-intenciones (`proyeccion`/`diferidas`/`economia`).

---

## 4. Especificación (aplicar TAL CUAL; anclas de texto, **sin** números de línea — A4)

### 4.1 `analizar/diferidas.py` — `split_planeado()` **con caché** (A1)

Insertar **al final del archivo** (después de `impacto_historico`):

```python
# --- Split Planeada/No planeada (histórico) --------------------------------------------------
# A1 (auditoría 2026-08-04): este GROUP BY es un SCAN completo de 1,14 M filas (~11 s en frío; los
# índices ix_dd_cover/ix_dd_event NO cubren CAUSE_NIVEL3 ni GAS_PERDIDO → no hay index-only scan).
# `causal` es la sub-intención DEFAULT de Analizar, así que sin caché CADA pregunta causal pagaría
# ese costo — y el proxy Flask de /consulta2/preguntar tiene timeout=90 s (ya hay 502 reportados por
# Gemma en frío). El histórico es INMUTABLE (BD estática ene-2023→jul-2025, solo lectura) ⇒ cachear
# en proceso es seguro y elimina el costo repetido. Se cachea TAMBIÉN el "no disponible".
_SPLIT_CACHE: dict = {}


def split_planeado(campos: list[str] | None = None) -> dict:
    """Split HISTÓRICO Planeada (mantenimiento) vs No planeada (diferidas) del volumen perdido, por
    CAUSE_NIVEL3, CRUDO (bbl) y GAS. `campos`=None/[] -> ECP global. MISMO scoping (CAMPO/AREA) y
    contrato de degradación que impacto_historico — SIEMPRE degrada, nunca lanza. Cacheado (A1).

    🔑 SOLO histórico (la BD termina 2025-07): quien lo consume DEBE rotularlo como tal.

    Retorno:
      {"sin_datos": True, "motivo": "..."}   -- BD ausente / error de lectura
      {"sin_datos": True, "motivo": None}    -- BD presente, 0 diferidas clasificadas en el alcance
      {"sin_datos": False, "split": {"CRUDO": {...}, "GAS": {...}}}
    Cada producto presente (solo si volumen clasificado > 0):
      {"no_planeada": v, "planeada": v, "total_clasificado": v,
       "pct_no_planeada": %, "dominante": "no_planeada"|"planeada"}
    """
    up = sorted({c.strip().upper() for c in (campos or []) if c and c.strip()})
    ck = tuple(up)
    if ck in _SPLIT_CACHE:
        return _SPLIT_CACHE[ck]

    def _memo(res):
        _SPLIT_CACHE[ck] = res
        return res

    if _DIF_DB is None or not _DIF_DB.exists():
        return _memo({"sin_datos": True, "motivo": "BD de diferidas no disponible en este entorno"})

    where, params = "1=1", []
    if up:
        ph = ",".join("?" * len(up))
        where = f"(UPPER(TRIM(CAMPO)) IN ({ph}) OR UPPER(TRIM(AREA)) IN ({ph}))"
        params = up + up

    sql = (f"SELECT CAUSE_NIVEL3, SUM(COALESCE(ACEITE_PERDIDO,0)) ac, SUM(COALESCE(GAS_PERDIDO,0)) gas "
           f"FROM AVM_DATADIF WHERE {where} GROUP BY CAUSE_NIVEL3")
    try:
        con = sqlite3.connect(str(_DIF_DB))
        con.text_factory = lambda b: b.decode("utf-8", "replace")
        rows = con.execute(sql, params).fetchall()
        con.close()
    except sqlite3.Error as e:
        # El error NO se cachea: puede ser transitorio (lock/IO) y debe poder reintentarse.
        return {"sin_datos": True, "motivo": f"error leyendo diferidas: {e}"}

    def _prod(idx):
        np_ = pl_ = 0.0
        for r in rows:
            cat = (r[0] or "").strip().lower()   # 'planeada' | 'no planeada' | 'control de producción' | ''
            v = float(r[idx] or 0)
            if cat == "no planeada":
                np_ += v
            elif cat == "planeada":
                pl_ += v
        tot = np_ + pl_
        if tot <= 0:
            return None
        return {"no_planeada": round(np_), "planeada": round(pl_), "total_clasificado": round(tot),
                "pct_no_planeada": round(np_ / tot * 100, 1),
                "dominante": "no_planeada" if np_ >= pl_ else "planeada"}

    split = {}
    c, g = _prod(1), _prod(2)
    if c:
        split["CRUDO"] = c
    if g:
        split["GAS"] = g
    if not split:
        return _memo({"sin_datos": True, "motivo": None})
    return _memo({"sin_datos": False, "split": split})
```

### 4.2 `analizar/plantilla.py`

**(a)** Insertar este helper **inmediatamente antes** de la línea `def causal(d, entidad, producto=None) -> str:`

```python
def _split_lineas(split, prod):
    """(contexto_line, accion_clause) del split histórico Planeada/No planeada de `prod`, o (None, "").
    Solo CRUDO/GAS tienen columnas de volumen perdido (BLANCOS no) → para BLANCOS devuelve (None, "").
    ROTULA el histórico: la BD de diferidas termina 2025-07 y el análisis es del mes en curso."""
    s = ((split or {}).get("split") or {}).get(prod) if (split and not split.get("sin_datos")) else None
    if not s or not s.get("total_clasificado"):
        return None, ""
    pl = _PROD_L.get(prod, prod.lower())
    u = _UNIDAD.get(prod, "bbl")
    np_pct = s["pct_no_planeada"]
    p_pct = round(100 - np_pct, 1)
    ctx = (f"CONTEXTO · {pl} (histórico ene-2023 a jul-2025, NO el mes en curso): del volumen "
           f"diferido acumulado, {np_pct}% No planeado (diferidas · {_fmt(s['no_planeada'], prod)} {u}) "
           f"· {p_pct}% Planeado (mantenimiento · {_fmt(s['planeada'], prod)} {u}).")
    if s["dominante"] == "no_planeada":
        clause = ("; históricamente el diferido de este producto es mayormente NO planeado (falla), "
                  "foco en confiabilidad")
    else:
        clause = ("; históricamente el diferido de este producto es mayormente Planeado "
                  "(mantenimiento previsto)")
    return ctx, clause
```

**(b)** Cambiar la firma de `causal`:

```python
def causal(d, entidad, producto=None) -> str:
```
→
```python
def causal(d, entidad, producto=None, split=None) -> str:
```

y añadir al final de su docstring (antes de las comillas de cierre):

```python
    `split` = dict de diferidas.split_planeado(campos) o None: añade una línea CONTEXTO histórica
    (No planeado/Planeado) por producto y ata una cláusula a la ACCIÓN. Degrada si None/sin_datos.
```

**(c)** En el bloque **focalizado sin rezago** (dentro de `if producto:` → `if not rez:`), reemplazar
EXACTAMENTE:

```python
            else:
                lineas.append(f"HECHO · {pl}: no tiene meta definida en el periodo — no hay rezago "
                              "que explicar.")
            return "\n".join(lineas)
```
por:
```python
            else:
                lineas.append(f"HECHO · {pl}: no tiene meta definida en el periodo — no hay rezago "
                              "que explicar.")
            ctx_line, _ = _split_lineas(split, producto)   # contexto (sin cláusula: aquí no hay ACCIÓN)
            if ctx_line:
                lineas.append(ctx_line)
            return "\n".join(lineas)
```

**(d)** En el loop `for t in rez:`, reemplazar EXACTAMENTE (verificado byte-exact contra el repo):

```python
        # ACCIÓN (consultiva, no prescriptiva)
        if conc is not None and conc >= 70 and detr:
            lineas.append(f"ACCIÓN · {pl}: intervención focalizada en los {len(detr)} campos que "
                          "concentran el faltante (consultivo).")
        elif detr:
            lineas.append(f"ACCIÓN · {pl}: el faltante está distribuido; revisión más amplia "
                          "(consultivo).")

        # DELTA (vs promedio 2026)
        dl = _delta_texto(d, p)
        if dl:
            lineas.append(f"DELTA · {pl}: {dl}.")
```
por:
```python
        # ACCIÓN (consultiva, no prescriptiva) — + cláusula atada al factor histórico dominante.
        ctx_line, accion_clause = _split_lineas(split, p)
        accion = None
        if conc is not None and conc >= 70 and detr:
            accion = (f"ACCIÓN · {pl}: intervención focalizada en los {len(detr)} campos que "
                      "concentran el faltante (consultivo)")
        elif detr:
            accion = (f"ACCIÓN · {pl}: el faltante está distribuido; revisión más amplia "
                      "(consultivo)")
        if accion is not None:
            lineas.append(accion + (accion_clause or "") + ".")

        # DELTA (vs promedio 2026)
        dl = _delta_texto(d, p)
        if dl:
            lineas.append(f"DELTA · {pl}: {dl}.")

        # CONTEXTO histórico (Planeado/No planeado) — rotulado, tras el DELTA del producto.
        if ctx_line:
            lineas.append(ctx_line)
```

> Si no hay `detr`, `accion is None` y la cláusula se pierde a propósito (no hay ACCIÓN a la cual
> atarla); el CONTEXTO igual se muestra. Comportamiento intencional.

### 4.3 `respuesta_analizar.py`

**(a)** En la firma de `responder`, añadir `_split_fn=None` al final:

```python
              _ejecutivo_fn=None, _diferidas_fn=None, _economia_fn=None) -> str:
```
→
```python
              _ejecutivo_fn=None, _diferidas_fn=None, _economia_fn=None, _split_fn=None) -> str:
```

**(b)** Debajo de la línea `econ_fn = _economia_fn or _economia.impacto_economico`, añadir:

```python
    split_fn = _split_fn or _diferidas.split_planeado
```

**(c)** Reemplazar EXACTAMENTE:

```python
        cuerpo = _plantilla.causal(d, ent_valor, _producto_explicito(texto, ent_valor))
```
por:
```python
        # CONTEXTO histórico de diferidas (Planeada/No planeada). Solo en niveles donde el filtro SQL
        # por CAMPO/AREA aplica (campo/activo/global); gerencia/vice/operador/fuente -> split=None
        # (no se muestra un split global engañoso bajo una entidad que no lo es). Reusa el scoping de
        # campos de la sub-intención `diferidas`. Cacheado en split_planeado (A1).
        split = None
        if _diferidas.nivel_soportado(nivel):
            campos_split = (_diferidas.campos_de_activo(ent_valor) if nivel == "activo"
                            else ([ent_valor] if ent_valor else []))
            split = split_fn(campos_split)
        cuerpo = _plantilla.causal(d, ent_valor, _producto_explicito(texto, ent_valor), split)
```

### 4.4 `tests/test_analizar.py`

**(a) BLINDAR los 4 tests causales/proyección existentes (A2 — obligatorio).** Hoy llaman
`_ra.responder(...)` sin `_split_fn`; tras el cambio el default es el lector REAL de SQLite → esos
tests pasarían a depender de una BD de 954 MB (y su salida cambiaría según el entorno: en 139 la BD no
está). El propio archivo declara que "los datos de negocio vienen SIEMPRE inyectados". Por tanto:

Añadir el fake (junto a los otros fakes) y pasarlo en los 4 tests que hoy NO lo pasan:

```python
def _fake_split_vacio(campos=None):
    return {"sin_datos": True, "motivo": None}
```

Tests a blindar (añadirles `_split_fn=_fake_split_vacio`): `test_causal_hecho_causa_accion_delta`,
`test_causal_sin_evento_declara`, el test de "en meta"/REGLA CERO que llame a `responder`, y
`test_proyeccion_*` si invoca `responder` por el causal path. **Regla:** todo `_ra.responder(...)` que
NO sea de las sub-intenciones `diferidas`/`economia` debe llevar `_split_fn` explícito. Sus
aserciones actuales NO se tocan.

**(b) Tests nuevos** (al final del archivo). ⚠️ A3: **`_FAKE_D_REZAGO` no existe** en el archivo — el
dict se obtiene llamando a la función fake existente `_fake_con_rezago()`:

```python
# ---------------- 2026-08-04: split Diferidas/Mantenimiento (histórico) ----------------

def _fake_split_ok(campos=None):
    return {"sin_datos": False, "split": {
        "CRUDO": {"no_planeada": 19546432, "planeada": 6299195, "total_clasificado": 25845627,
                  "pct_no_planeada": 75.6, "dominante": "no_planeada"},
    }}

def _fake_split_planeada(campos=None):
    return {"sin_datos": False, "split": {
        "CRUDO": {"no_planeada": 2000000, "planeada": 8000000, "total_clasificado": 10000000,
                  "pct_no_planeada": 20.0, "dominante": "planeada"},
    }}


def test_plantilla_split_contexto_y_accion():
    """CONTEXTO rotulado + cláusula del factor dominante en la ACCIÓN."""
    out = _plantilla.causal(_fake_con_rezago(), None, "CRUDO", _fake_split_ok())
    assert "CONTEXTO · crudo (histórico ene-2023 a jul-2025, NO el mes en curso)" in out
    assert "75.6% No planeado" in out
    assert "24.4% Planeado" in out
    assert "foco en confiabilidad" in out          # dominante = no_planeada
    assert "ACCIÓN · crudo" in out

def test_plantilla_split_dominante_planeada():
    out = _plantilla.causal(_fake_con_rezago(), None, "CRUDO", _fake_split_planeada())
    assert "mantenimiento previsto" in out
    assert "20.0% No planeado" in out

def test_plantilla_split_ausente_no_rompe():
    """Sin split (None) o sin_datos: salida IDÉNTICA a hoy (sin CONTEXTO). Protege 139 (sin BD)."""
    assert "CONTEXTO ·" not in _plantilla.causal(_fake_con_rezago(), None, "CRUDO", None)
    assert "CONTEXTO ·" not in _plantilla.causal(_fake_con_rezago(), None, "CRUDO", _fake_split_vacio())

def test_responder_causal_inyecta_split():
    """responder() con _split_fn FAKE -> el CONTEXTO histórico llega a la respuesta."""
    out = _ra.responder("cual es la causa del gap de crudo?", entidad=None,
                        _ejecutivo_fn=_fake_con_rezago, _split_fn=_fake_split_ok)
    assert "CONTEXTO · crudo" in out
    assert "No planeado" in out
```

> Nota: `_fake_con_rezago()` acepta kwargs con defaults → llamarla sin args es válido. Verificar que su
> `titular` tenga CRUDO con `valor_pct < 100` y `gap_por_producto["CRUDO"]["detractores"]` no vacío
> (así es hoy). Si no fuera así, **DETENERSE y reportar** en vez de editar el fake existente.

---

## 5. Orden de ejecución

1. **Baseline (antes de tocar nada)** — anotar el número:
   `PYTHONPATH="$(pwd)" uv run pytest tests/ -q -k "analizar or consulta_v2 or cuantificar or jerarquizar or ranking or no_soportado or conteo_jerarquia or puente_gerencia"`
   → hoy **220 passed**. Si difiere, anotar el real y usarlo como referencia.
2. §4.1 (`diferidas.py`) → 3. §4.2 (`plantilla.py`) → 4. §4.3 (`respuesta_analizar.py`) →
   5. §4.4(a) blindaje → 6. §4.4(b) tests nuevos.
7. Validaciones §6 **en orden**. 🛑 **HARD STOP:** si V1/V2/V3 fallan, DETENERSE y reportar; no commitear.
8. Verde → commit + push.

---

## 6. Validaciones (comando → resultado esperado)

- **V1 · compila:**
  `PYTHONPATH="$(pwd)" uv run python -m py_compile app/features/consulta_v2/analizar/diferidas.py app/features/consulta_v2/analizar/plantilla.py app/features/consulta_v2/respuesta_analizar.py`
  → exit 0, sin salida.
- **V2 · tests de Analizar:** `PYTHONPATH="$(pwd)" uv run pytest tests/test_analizar.py -q`
  → verde, incluidos los 4 nuevos.
- **V3 · no-regresión (suite ampliada):** mismo comando del baseline
  → **baseline + 4**, 0 fallos.
- **V4 · BD real + caché (A1).** Script ad-hoc en scratchpad (NO versionar), con `PYTHONIOENCODING=utf-8`:
  ```python
  import os, time; os.environ["CONSULTA_ANALIZA_LLM"] = "false"
  from app.features.consulta_v2.analizar import diferidas as D
  t = time.time(); r = D.split_planeado(None); t1 = time.time() - t
  t = time.time(); D.split_planeado(None);      t2 = time.time() - t
  print(r.get("split", {}).get("CRUDO"), "| 1a: %.2fs | 2a(cache): %.4fs" % (t1, t2))
  ```
  ESPERADO (verificado 2026-08-04): `{'no_planeada': 19546432, 'planeada': 6299195,
  'total_clasificado': 25845627, 'pct_no_planeada': 75.6, 'dominante': 'no_planeada'}`,
  **2ª llamada ~0.0000 s** (caché efectiva). Si `pct_no_planeada` ≠ 75.6 → **reportar** (cambió el
  dato; no asumir). Si la BD faltara → `{'sin_datos': True, ...}` (degradación válida).

**NO declarar "verificado en navegador" ni "probado con el LLM"** — eso lo hace el usuario en el
servidor de pruebas tras el push.

---

## 7. Reglas no negociables

1. Aplicar §4 **TAL CUAL**. Si algo no compila o una firma/bloque no calza byte-exact con el repo,
   **DETENERSE y reportar** — no improvisar variantes.
2. **NO** tocar `impacto_historico` (sub-intención `diferidas` debe quedar byte-idéntica).
3. **NO** tocar DDL/ETL/la BD SQLite (no crear índices)/`analisis/api.py`/frontend/golden/`maquina_q.py`.
4. El CONTEXTO **SIEMPRE** rotulado "histórico ene-2023 a jul-2025, NO el mes en curso". Sin ese rótulo
   el cambio sería deshonesto (mezcla de periodos) — no quitarlo.
5. La caché de §4.1 es **obligatoria** (A1). No cachear el caso de error de SQLite (puede ser transitorio).
6. Degradación: `split` None/`sin_datos` ⇒ salida **idéntica a hoy** (`test_plantilla_split_ausente_no_rompe`).
7. Solo `py_compile` + `pytest` en dev (regla de RAM). Sin backend, sin LLM, sin navegador.

---

## 8. Fuera de alcance (explícito)

- **Atribuir el gap DEL MES (mayo-2026) a Planeado/No planeado con datos del mes** — imposible hoy:
  `AVM_DATADIF` termina 2025-07 (0 filas 2026) y no hay fuente de mantenimiento del mes en curso.
  Es un problema de **datos**, no de código (opción B, no se hace aquí).
- Cambiar la CAUSA del mes (campos detractores) — se conserva; el split es CONTEXTO adicional.
- Crear índice `CAUSE_NIVEL3` en la SQLite (954 MB, no versionada) — la caché resuelve el costo.
- Frontend, sub-intención `diferidas`, `proyeccion`, `economia`.
- **En 139 el CONTEXTO no aparecerá** hasta que se suba la BD de diferidas (documentado en CLAUDE.md:
  no cabe en git, >100 MB). Es degradación esperada, **no un bug**.

---

## 9. Registro de auditoría

### Ronda 1 (diseño)
- **D1** — `CAUSE_NIVEL3` es la columna correcta ('Planeada'/'No planeada'), verificado con `PRAGMA` +
  `DISTINCT`. `CAUSE_NIVEL2` es el tipo de causa (Pozo/Yacimiento/…), NO planeado/no-planeado.
- **D2** — Split SOLO histórico y rotulado (0 filas 2026, verificado). Presentarlo como causa del mes
  sería mezclar periodos.
- **D3** — `impacto_historico` intacto; se añade función hermana con el mismo scoping y contrato.
- **D4** — Split solo donde el filtro SQL aplica (`nivel_soportado`: campo/activo/global).
- **D5** — Solo CRUDO/GAS tienen volumen perdido; BLANCOS → (None,"").
- **D6** — La cláusula se ata al `dominante` histórico, pero la ACCIÓN sigue basada en los campos del
  mes: se enriquece, no se reemplaza.
- **D7** — Inyección `_split_fn` (espejo de `_diferidas_fn`/`_economia_fn`).

### Ronda 2 (auditoría v1 → v2, contra código y BD reales)
- 🔴 **A1 · RENDIMIENTO (cambió el diseño).** El GROUP BY global es un **SCAN de 1.142.599 filas =
  10,9 s en frío** (medido); `ix_dd_cover` cubre (EVENT_DATE, CAMPO, CAUSE_NIVEL4, CAUSE_NIVEL5,
  CAUSE_NIVEL2, ACEITE_PERDIDO) → **no** incluye `CAUSE_NIVEL3` ni `GAS_PERDIDO`, `EXPLAIN QUERY PLAN`
  confirma `SCAN`. Como `causal` es la sub-intención **DEFAULT**, cada pregunta causal global (justo el
  caso reportado por el usuario) sumaría ~11 s — encima de un **502 ya diagnosticado** (proxy Flask
  `timeout=90 s` + Gemma en frío). **Corrección: caché en proceso obligatoria** (§4.1); el histórico es
  inmutable ⇒ seguro. Medido: 2ª llamada **0,0000 s**. El filtrado por campo es barato (0,67 s).
- 🟠 **A2 · Dependencia oculta en tests existentes.** 4 tests causales llaman `responder()` sin
  `_split_fn`; con el default real pasarían a leer el SQLite de 954 MB, violando la política del propio
  archivo ("los datos de negocio vienen SIEMPRE inyectados") y volviéndose entorno-dependientes (en 139
  no hay BD). **Corrección: §4.4(a) los blinda con `_fake_split_vacio`.**
- 🟠 **A3 · `_FAKE_D_REZAGO` no existe.** v1 pedía "defínelo si no existe" (instrucción vaga, riesgo de
  que el Executor invente datos). Verificado: el archivo tiene la **función** `_fake_con_rezago`.
  **Corrección:** los tests nuevos llaman `_fake_con_rezago()`; si su forma no cumple, DETENERSE.
- 🟡 **A4 · Números de línea obsoletos.** v1 citaba líneas 48/51/104, desplazadas por el commit
  `d5dbb81`. **Corrección:** v2 usa anclas de texto byte-exact (verificadas contra el repo).
- 🟡 **A5 · 139 sin BD de diferidas.** El CONTEXTO no aparecerá allí. Se documenta en §8 como
  degradación esperada para que no se reporte como bug.
- 🟢 **A6 · Caché de errores.** El `sqlite3.Error` **no** se cachea (puede ser transitorio); sí se
  cachean "BD ausente" y "sin datos" (estados estables). Regla NN #5.

---

**Commit sugerido (tras V1-V4 verdes):**
```
feat(consulta_v2): Analizar causal + CONTEXTO histórico Diferidas/Mantenimiento y ACCIÓN atada

La CAUSA del mes (campos) se mantiene; se añade una línea CONTEXTO por producto con el split
histórico No planeado (diferidas) vs Planeado (mantenimiento) desde CAUSE_NIVEL3 (AVM_DATADIF,
2023-2025), ROTULADA como histórica (la BD no cubre 2026), y la ACCIÓN gana una cláusula atada al
factor dominante. A1: el GROUP BY es un SCAN de 1,14M filas (~11s) y causal es la sub-intención
default -> split_planeado va CACHEADO (histórico inmutable). A2: los tests causales existentes se
blindan con _split_fn fake (no dependen del SQLite). Degrada intacto sin BD (139). pytest <N+4>.
```
