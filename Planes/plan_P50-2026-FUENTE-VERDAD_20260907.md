# Plan `P50-2026-FUENTE-VERDAD` — `core.p50_2026` como respaldo del P50 global mensual

| | |
|---|---|
| **ID tarea** | `P50-2026-FUENTE-VERDAD` |
| **Fecha** | 2026-09-07 |
| **Versión** | **v2 — re-auditado.** La v1 tenía un defecto de alcance (H1) que la habría dejado sin efecto visible. Ver §1.0 |
| **Repo** | `backend` (ProdIABack) |
| **Alcance** | Que el P50 mensual global salga de `core.p50_2026` cuando la hoja `REPORTE_PRESIDENT` no tenga ese mes ingerido |
| **Qué NO se toca** | El P50 por vicepresidencia · las tarjetas por producto · **el frontend** · el clasificador · los extractores de ingesta · `cuantificar/ejecutor.py` |

### Decisiones cerradas del usuario

1. La tabla `core.p50_2026` **ya existe y ya está poblada** en la BD local con los 12 meses. El executor **NO** la crea ni la modifica desde Python.
2. Solo se carga **P50**. El real y la proyección de la lámina quedan fuera.
3. La fuente de esos 12 valores es una **lámina gerencial transcrita a mano**. El usuario lo aceptó tras advertírselo.
4. El P50 vive **solo a nivel global**. No se inventa desglose por producto, VP, activo ni campo.

---

## §0 Contexto para el agente EXECUTOR

**Proyecto:** ProdIA — consulta conversacional de producción de petróleo y gas de Ecopetrol. Son **dos procesos**: Flask en el 5029 (UI) y FastAPI/INGESTA en el 5030 (datos). El navegador nunca habla con el 5030: Flask hace de proxy.

**Este plan toca UN SOLO archivo de código, del backend FastAPI, más una migración SQL.**

| | |
|---|---|
| Archivo a modificar | `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\analisis\api.py` |
| Archivo a crear | `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\db\migrations\011_p50_2026.sql` |
| Carpeta de trabajo | `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend` |
| Intérprete | `uv run python` (NO `python` a secas) |

**Qué es el P50:** el compromiso corporativo de producción, pactado en `kboepd` (miles de barriles equivalentes de petróleo por día). Se pacta para **Ecopetrol como un todo** — nunca por campo o activo. Es la vara contra la que la alta gerencia mide el cumplimiento.

**La tabla `core.p50_2026`** (ya creada — no la toques):

```
mes        SMALLINT PRIMARY KEY   -- 1..12
mes_nombre VARCHAR(12)            -- 'Enero'...'Diciembre'
p50        NUMERIC(8,2)           -- 744.20, 741.20, ...
unidad     VARCHAR(10)            -- 'kboepd'
fuente     VARCHAR(60)            -- 'lamina Produccion Equivalente G.E. 2026'
```

Valores enero→diciembre: `744.2 741.2 732.8 714.9 726.7 728.0 747.0 740.4 735.0 741.8 738.3 733.3`.

**Convenciones obligatorias:**
- Python 3.12. Código y comentarios **en español**.
- Los comentarios de este proyecto explican **por qué**, no qué. Sigue ese estilo y fecha los cambios con `[2026-09-07]`.
- SQL con `sa.text(...)` y parámetros nombrados (`:mes`), **nunca** interpolación de cadenas.
- **Si algo del plan no calza con el código real: DETENTE y reporta. No improvises.**

---

## §1 Hallazgos de la auditoría

### §1.0 🔴 Qué falló en la v1 de este plan (y por qué existe la v2)

La v1 proponía rellenar la entidad **`Upstream`** dentro del array `totales`. Se re-auditó contra el frontend y **el cambio no habría tenido ningún efecto visible**: los dos consumidores solo miran `productos`, nunca `totales` (H1). Habría sido un cambio verde en todas las pruebas estáticas y **muerto en runtime** — justo el fallo que la regla R3 del proyecto advierte.

Los hallazgos H1, H2 y H3 son nuevos de la v2 y **reescriben la especificación entera**.

### §1.1 🔴 H1 — El frontend solo lee `productos`; `totales` no lo mira nadie

Medido en los dos únicos consumidores:

```javascript
// multitab_shell.js:5755  __cnPaintP50Header
if (!d || d.encontrada === false || !(d.productos && d.productos.length)) {
    row2.innerHTML = '...Compromiso P50 no disponible · falta ingerir REPORTE_PRESIDENT...';
    return;
}
row2.innerHTML = d.productos.map(__cnP50CardHtml).join("");

// multitab_shell.js:6838  __cnSaludoDesdeDesemp
.then(function (p) { if (p && p.productos) { __cnSalP50 = p; __cnSaludoRefresh(); } })
```

Y un grep de `totales` sobre `multitab_shell.js` no devuelve **ninguna** coincidencia relacionada con este endpoint (las 3 que salen son de otros paneles: `huecos_totales`, comentarios de barras).

**Consecuencia que determina la §3:** rellenar `Upstream` en `totales` no cambia nada de lo que ve el usuario. El respaldo debe entrar por **`productos`** para tener efecto.

### §1.2 🔴 H2 — `productos` son productos, no un total: no se puede meter `Upstream` ahí

`__cnP50CardHtml` (`multitab_shell.js:3696-3749`) trata cada card como un **producto físico**:

- `__cnProdId(PROD)` (`:3700`) busca icono y color por nombre de producto. Con `"Upstream"` devolvería el neutro `#6E7C75`.
- Rotula la cifra como **`kbpe`** literal (`:3735`) y pinta un anillo `REAL / P50` (`:3733`).
- Muestra `Real del mes`, `Compromiso`, `Proyección cierre`, `Programa día`, `Real día` y `Gap vs P50` — **seis medidas que el respaldo no tiene**.

Meter una card `Upstream` en `productos` produciría una tarjeta gris, sin real, con anillo a 0 y cinco filas con guiones, **al lado** de Crudo/Gas/Blancos. Visualmente sería un fallo, no una mejora.

**Decisión de diseño derivada:** el respaldo **NO** entra en `productos` como una card más. Entra como un **campo nuevo de primer nivel** en la respuesta (`p50_respaldo`), que no rompe a ningún consumidor actual porque ninguno lo lee, y deja el dato disponible para quien lo quiera pintar después.

⚠️ Esto significa que **este plan no hace aparecer el P50 en pantalla por sí solo**. Deja el dato servido y trazable; pintarlo es un plan de frontend aparte (§7). Está dicho aquí para que nadie espere un cambio visual.

### §1.3 🔴 H3 — La rama global del chat lee producto, o `Ecopetrol` — nunca `Upstream`

`respuesta_analizar.py:291-295`:

```python
card = next((p for p in info.get("productos", [])
            if p.get("entidad", "").upper() == producto), None)
if card is None:
    card = next((t for t in info.get("totales", [])
                if t.get("entidad") == "Ecopetrol"), None)
```

Y `formatear_cifra_global` (`p50_referencia.py:262-278`) **exige real y P50 a la vez**:

```python
if real is None or p50 is None:
    return f"No tengo el P50 de {ent} disponible en este momento."
```

**Doble consecuencia:** el chat nunca consulta `Upstream`, y aunque lo hiciera, una card con P50 pero sin `real_mes` produce el mensaje de «no disponible». Por eso el chat queda **fuera de alcance** (§7) y no se toca `p50_referencia.py`.

### §1.4 🟢 H4 — La escala coincide: `kboepd` ≡ `kbpe`

Riesgo candidato a bug silencioso, **descartado con medición** contra la BD local (`daily_report_prod`, reporte 18 = 2026-05-18):

| entidad | `base_p50` en BD | `core.p50_2026` (mayo) |
|---|---|---|
| **Upstream** | **726.73** | **726.7** ✅ |
| Ecopetrol | 611.01 | — |
| Filiales | 115.72 | — |
| Crudo | 521.82 | — |

Coinciden. El endpoint rotula `"unidad": "kbpe"` (`api.py:2681`) y la tabla dice `kboepd`: **misma escala, distinto rótulo**. No hay conversión que hacer.

🔑 Importa porque el proyecto ya tiene un incidente de escalas mezcladas (`p50_referencia.py:27-38`, ratios ×5,8 / ×36). Aquí **no** aplica.

### §1.5 🟡 H5 — `president()` se ancla a un `reporte_id`, no a un mes

`api.py:2648-2652` elige **un** reporte (el de `fecha_reporte` máxima con esa hoja) y pivota solo sus filas. No hay noción de «serie de meses».

La tabla nueva es una serie de 12 meses **sin reporte asociado**. El puente correcto es el mes de `fecha_reporte`, que ya se calcula como `corte` (`api.py:2657`).

⚠️ Desfase verificado que **NO** hay que replicar: un reporte del **día 1** trae aún el P50 del **mes anterior** (reporte del 2026-03-01 → P50 de febrero; del 2026-05-01 → P50 de abril). El respaldo usa el mes de `fecha_reporte` tal cual; cuando el mes ingerido existe, manda el ingerido y el respaldo ni se calcula.

### §1.6 🟡 H6 — Las migraciones se aplican con `apply_migration.py`, y deben ser idempotentes

Existe la herramienta del proyecto: `backend\backend\apply_migration.py`. Su docstring (`:12-14`) es explícito:

> «Las migraciones deben ser IDEMPOTENTES (IF NOT EXISTS / ON CONFLICT): este script las ejecuta tal cual, **sin llevar registro de cuáles ya se aplicaron**. Reaplicar una migración idempotente es un no-op seguro.»

Usa `get_engine()` en vez de `psql` **a propósito**: la contraseña local lleva un `£` que rompe la autenticación al pasarla por línea de comandos (`:5-7`).

Uso: `uv run python apply_migration.py ../db/migrations/011_p50_2026.sql` desde `backend\backend`.

Convención de cabecera, tomada de `010_clasificacion_log.sql:1`: primera línea `-- NNN_nombre.sql · Idempotente.`, seguida de un bloque que explica **de dónde sale el dato** y **por qué** se decidió así.

Numeración libre verificada: `001`…`010`, luego la **011**.

### §1.7 🟡 H7 — Sin `real_mes` no hay `cumpl_p50`, y así debe quedar

`_card()` (`api.py:2664-2677`) calcula `cumpl_p50 = real/p50*100` solo si hay ambos. Con el respaldo hay P50 pero **no hay real**.

⚠️ **Prohibido inventar un `real_mes`** para que salga un porcentaje: sería exactamente el fallo silencioso que este proyecto persigue («responde otra cosa con seguridad», `CLAUDE.md` §6).

### §1.8 🟢 H8 — Los tests inyectan el endpoint; no tocan BD

`backend/tests/test_p50_referencia.py` es el único test que menciona `president`. `respuesta_analizar.py:149` acepta `_president_fn` como inyección. El cambio no los rompe.

### §1.9 🟢 H9 — La BD local tiene corrupción física en `fact_tabla_hoja`

Documentado en `CLAUDE.md` §6 y **reproducido durante esta auditoría**: un `SELECT ... GROUP BY hoja` aborta con `DataCorrupted: 5 invalid pages among blocks 3759..3774`.

Se sortea con `SET enable_seqscan = off` (fuerza el índice y evita los bloques dañados). `SET zero_damaged_pages` **no** sirve: exige superusuario y `robustez` no lo es.

⚠️ Es un problema **solo de la BD local**. Ese `SET` es para las verificaciones manuales de §6.1 — **no** va al código de producción.

### §1.10 🟢 H10 — El pipeline de despliegue no se ve afectado

Cruzado contra `CLAUDE.md` §9. El cambio es backend puro (`ProdIABack`), sin tocar `frontend/routes/api.py` ni estáticos, así que `verificar_deploy.ps1` (que valida puerto y estáticos del login) no cambia de resultado.

⚠️ **Pero la migración sí es un paso manual extra en cada entorno.** El pipeline `migrar-a-azure` copia archivos, **no ejecuta SQL**. Sin correr `apply_migration.py` en Pruebas y en el 139, la tabla no existirá allí y el respaldo quedará inerte (no falla: el `SELECT` no encuentra fila y devuelve `None` — ver H11).

### §1.11 🟡 H11 — Si la tabla no existe, el endpoint NO debe caerse

Consecuencia directa de H10: habrá una ventana en la que el código esté desplegado y la migración no aplicada. Un `SELECT` contra una tabla inexistente lanza `ProgrammingError` y **tumbaría `/president` entero**, rompiendo el panorama que hoy funciona.

**Por eso la consulta del respaldo va envuelta en `try/except`** y ante cualquier fallo deja `p50_respaldo = None`. Degrada al comportamiento actual en vez de romper.

---

## §2 Estado actual

`api.py:2625-2682`, función `president()`:

1. Elige `rid` — el `reporte_id` con `fecha_reporte` máxima que tenga la hoja `REPORTE_PRESIDENT` (`:2648-2652`).
2. Si no hay ninguno → `{"encontrada": False}` (`:2653-2654`).
3. Lee `fr` / `corte` = `fecha_reporte` de ese reporte (`:2655-2657`).
4. Pivota `entidad × medida` en el dict `piv` (`:2658-2662`).
5. `_card(ent)` arma cada tarjeta (`:2664-2677`).
6. Devuelve `productos` + `totales` (`:2679-2682`).

**El hueco:** si el mes en curso no está ingerido, `piv` no trae nada de ese mes y el frontend muestra «Compromiso P50 no disponible · falta ingerir REPORTE_PRESIDENT en este entorno» (`multitab_shell.js:5756`).

---

## §3 Especificación

### 3.1 AÑADIR — migración `011_p50_2026.sql`

**Crear** `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\db\migrations\011_p50_2026.sql` con **exactamente** este contenido:

```sql
-- 011_p50_2026.sql · Idempotente.
-- Serie P50 mensual 2026 (nivel Upstream global), en kboepd.
--
-- DE DONDE SALE (2026-09-07)
--   El P50 solo entra al sistema dentro de la hoja REPORTE_PRESIDENT de cada reporte diario.
--   Un mes sin reporte ingerido no tiene P50, y el panorama corporativo se queda sin la cifra
--   de referencia ("Compromiso P50 no disponible"). Esta tabla guarda los 12 meses del
--   compromiso 2026 para servir de RESPALDO cuando la ingesta no cubre ese mes.
--
--   ORIGEN DEL DATO: lamina gerencial "Produccion Equivalente G.E. 2026", transcrita A MANO.
--   NO proviene de la ingesta y NO tiene reporte_id que lo respalde. La columna `fuente` lo
--   deja explicito para que nadie lo confunda con un dato medido.
--
-- ESCALA: kboepd. Verificado el 2026-09-07 contra REPORTE_PRESIDENT (reporte 18, 2026-05-18):
--   Upstream base_p50 = 726.73 y esta tabla para mayo = 726.7. Es la MISMA magnitud que el
--   endpoint /president rotula como "kbpe" -- distinto rotulo, misma escala. No hay conversion.
--
-- GRANO: Upstream global. NO hay desglose por producto, vicepresidencia, activo ni campo,
--   porque el P50 no se pacta a esos niveles (ver p50_referencia.py, cabecera del modulo).

CREATE TABLE IF NOT EXISTS core.p50_2026 (
    mes        SMALLINT     PRIMARY KEY CHECK (mes BETWEEN 1 AND 12),
    mes_nombre VARCHAR(12)  NOT NULL,
    p50        NUMERIC(8,2) NOT NULL,
    unidad     VARCHAR(10)  NOT NULL DEFAULT 'kboepd',
    fuente     VARCHAR(60)  NOT NULL DEFAULT 'lamina Produccion Equivalente G.E. 2026'
);

COMMENT ON TABLE core.p50_2026 IS
    'Serie P50 mensual 2026 (Upstream) en kboepd. Origen: lamina gerencial, transcrito a mano - NO proviene de ingesta.';

-- ON CONFLICT: reejecutar la migracion deja los mismos 12 valores, no duplica ni acumula.
INSERT INTO core.p50_2026 (mes, mes_nombre, p50) VALUES
    ( 1, 'Enero',      744.20),
    ( 2, 'Febrero',    741.20),
    ( 3, 'Marzo',      732.80),
    ( 4, 'Abril',      714.90),
    ( 5, 'Mayo',       726.70),
    ( 6, 'Junio',      728.00),
    ( 7, 'Julio',      747.00),
    ( 8, 'Agosto',     740.40),
    ( 9, 'Septiembre', 735.00),
    (10, 'Octubre',    741.80),
    (11, 'Noviembre',  738.30),
    (12, 'Diciembre',  733.30)
ON CONFLICT (mes) DO UPDATE
    SET mes_nombre = EXCLUDED.mes_nombre,
        p50        = EXCLUDED.p50;
```

### 3.2 MODIFICAR — `api.py`, función `president()`

**Archivo:** `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\analisis\api.py`

#### Cambio 3.2.a — leer el respaldo

**LOCALIZAR** estas líneas exactas (`api.py:2658-2662`):

```python
        piv = {}
        for r in c.execute(sa.text("""
            SELECT dims->>'entidad' ent, dims->>'medida' med, valor
            FROM core.fact_tabla_hoja WHERE hoja='REPORTE_PRESIDENT' AND reporte_id=:r"""), {"r": rid}):
            piv.setdefault(r[0], {})[r[1]] = float(r[2])
```

**SUSTITUIR POR:**

```python
        piv = {}
        for r in c.execute(sa.text("""
            SELECT dims->>'entidad' ent, dims->>'medida' med, valor
            FROM core.fact_tabla_hoja WHERE hoja='REPORTE_PRESIDENT' AND reporte_id=:r"""), {"r": rid}):
            piv.setdefault(r[0], {})[r[1]] = float(r[2])

        # [2026-09-07] RESPALDO del P50 global (plan P50-2026-FUENTE-VERDAD). El P50 solo entra
        # al sistema dentro de REPORTE_PRESIDENT, asi que un mes sin reporte ingerido deja el
        # panorama corporativo sin cifra de referencia. Cuando falta, se toma de core.p50_2026:
        # serie de 12 meses en la MISMA escala (verificado -- Upstream base_p50 = 726.73 en el
        # reporte del 2026-05-18 y 726.7 en la tabla para mayo).
        # 🔑 Va como campo APARTE, no dentro de `productos`: esas cards son productos fisicos
        # (icono, color y anillo Real/P50 por producto, multitab_shell.js:3696) y una entidad
        # global ahi saldria gris, sin real y con cinco filas en guion.
        # 🔑 try/except: la migracion 011 es un paso MANUAL por entorno y el pipeline no ejecuta
        # SQL, asi que habra una ventana con el codigo desplegado y la tabla sin crear. Sin esta
        # guarda, /president entero se caeria y rompería el panorama que hoy si funciona.
        p50_respaldo = None
        if fr and fr[0] and fr[0].year == 2026 and "base_p50" not in piv.get("Upstream", {}):
            try:
                fila = c.execute(sa.text(
                    "SELECT p50 FROM core.p50_2026 WHERE mes = :mes"), {"mes": fr[0].month}).first()
                if fila and fila[0] is not None:
                    p50_respaldo = float(fila[0])
            except Exception:
                p50_respaldo = None      # tabla ausente -> se degrada al comportamiento actual
```

#### Cambio 3.2.b — exponerlo en la respuesta

**LOCALIZAR** estas líneas exactas (`api.py:2679-2682`):

```python
    productos = [_card(e) for e in ["Crudo", "Gas", "Blancos"] if e in piv]
    totales = [_card(e) for e in ["Ecopetrol", "Filiales", "Upstream"] if e in piv]
    return {"encontrada": True, "reporte_id": rid, "corte": corte, "unidad": "kbpe",
            "productos": productos, "totales": totales}
```

**SUSTITUIR POR:**

```python
    productos = [_card(e) for e in ["Crudo", "Gas", "Blancos"] if e in piv]
    totales = [_card(e) for e in ["Ecopetrol", "Filiales", "Upstream"] if e in piv]
    # `p50_respaldo` es ADITIVO: ningun consumidor actual lo lee (el frontend solo mira
    # `productos`, multitab_shell.js:5755 y :6838), asi que anadirlo no cambia ninguna pantalla.
    # Queda servido y trazable para quien lo pinte despues. `null` cuando el mes SI esta ingerido
    # -- es el caso normal, y significa "no hizo falta respaldo".
    return {"encontrada": True, "reporte_id": rid, "corte": corte, "unidad": "kbpe",
            "productos": productos, "totales": totales,
            "p50_respaldo": ({"base_p50": p50_respaldo, "entidad": "Upstream",
                              "mes": fr[0].month, "fuente": "core.p50_2026"}
                             if p50_respaldo is not None else None)}
```

#### Cambio 3.2.c — actualizar el docstring

**LOCALIZAR** (`api.py:2627-2631`):

```python
    """Tarjeta P50 por producto desde la hoja REPORTE_PRESIDENT (fact_tabla_hoja) — escala kbpe
    corporativa (mundo P50, NO la del fact diario). Fuente ÚNICA con BLANCOS Real/Proy/P50 + el
    'compromiso' (Reto). Sin `periodo` toma el reporte más reciente que tenga la hoja; con `periodo`
    (YYYY-MM) el más reciente de ese mes. Devuelve por entidad TODAS las medidas + cumplimiento vs P50;
    la referencia del semáforo (P50 vs PPTO) la decide el frontend — este endpoint es agnóstico."""
```

**SUSTITUIR POR:**

```python
    """Tarjeta P50 por producto desde la hoja REPORTE_PRESIDENT (fact_tabla_hoja) — escala kbpe
    corporativa (mundo P50, NO la del fact diario). Fuente ÚNICA con BLANCOS Real/Proy/P50 + el
    'compromiso' (Reto). Sin `periodo` toma el reporte más reciente que tenga la hoja; con `periodo`
    (YYYY-MM) el más reciente de ese mes. Devuelve por entidad TODAS las medidas + cumplimiento vs P50;
    la referencia del semáforo (P50 vs PPTO) la decide el frontend — este endpoint es agnóstico.
    [2026-09-07] Añade `p50_respaldo`: si el reporte elegido es de 2026 y NO trae `base_p50` de
    Upstream, esa única cifra se sirve desde `core.p50_2026` (misma escala, transcrita de la lámina
    gerencial). Campo ADITIVO — `null` cuando el mes sí está ingerido. NO entra en `productos` ni
    `totales` y NO lleva real: sin real medido no hay cumplimiento, y fabricarlo sería inventar."""
```

---

## §4 Orden de ejecución

| # | Acción | Archivo | Verificación |
|---|---|---|---|
| 1 | Crear la migración §3.1 | `backend\db\migrations\011_p50_2026.sql` | El archivo existe y termina en `;` |
| 2 | Aplicar §3.2.a (lectura del respaldo) | `analisis\api.py` | El bloque queda **después** de poblar `piv` y **antes** de `def _card` |
| 3 | Aplicar §3.2.b (campo en la respuesta) | `analisis\api.py` | — |
| 4 | Aplicar §3.2.c (docstring) | `analisis\api.py` | — |
| 5 | Verificación estática §6.1 (V1→V7) | — | Todos en verde |

⚠️ **El orden 2→3 no es negociable:** `p50_respaldo` debe existir antes de que el `return` la referencie, o el endpoint revienta con `NameError` en la primera petición.

⚠️ **El paso 1 NO se ejecuta contra la BD.** La tabla ya existe en local (decisión 1). La migración es para que Pruebas y el 139 la tengan; aplicarla allí es responsabilidad del despliegue, no del executor (§6.2).

---

## §5 Reglas no negociables

1. **CERO modificaciones** fuera de lo escrito en §3. Si ves algo mejorable, anótalo y repórtalo al final — no lo cambies.
2. **NO crear ni poblar `core.p50_2026` desde Python.** Ya existe en la BD local.
3. **NO ejecutar `apply_migration.py`** contra la BD local: la tabla ya está y reaplicar es innecesario aquí.
4. **NO tocar** `p50_referencia.py`, `respuesta_analizar.py`, `cuantificar/ejecutor.py`, `multitab_shell.js` ni `frontend/routes/api.py`.
5. **NO meter el respaldo en `productos` ni en `totales`.** H1 y H2 lo prohíben: rompería las tarjetas por producto.
6. **NO inventar `real_mes` ni `compromiso`.** Sin real no hay cumplimiento, y así debe quedar.
7. **NO cambiar el rótulo `"unidad": "kbpe"`.** Está medido que es la misma escala (H4); cambiarlo rompería a los consumidores por una cuestión cosmética.
8. **NO quitar el `try/except`** de §3.2.a. Es lo que evita tumbar `/president` en la ventana entre despliegue y migración (H11).
9. Código y comentarios **en español**. SQL siempre con `sa.text(...)` y parámetros nombrados.
10. **Si algo no calza con el código real: DETENTE y reporta.**

---

## §6 Validación

### 6.1 Estática — la hace el EXECUTOR

Todos los comandos desde `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend`, **uno por uno**, en PowerShell normal (no requiere administrador).

| # | Comando | Resultado esperado |
|---|---|---|
| V1 | `uv run python -c "import ast; ast.parse(open(r'app/features/analisis/api.py',encoding='utf-8').read()); print('sintaxis OK')"` | `sintaxis OK` |
| V2 | `uv run python -c "from app.features.analisis import api; print('import OK')"` | `import OK` |
| V3 | `uv run python -c "s=open(r'app/features/analisis/api.py',encoding='utf-8').read(); print('p50_respaldo:', s.count('p50_respaldo'))"` | `p50_respaldo: 6` |
| V4 | `uv run pytest tests/test_p50_referencia.py -q` | Todos pasan (H8: usan inyección, no BD) |
| V5 | `uv run pytest -q` | Sin regresiones nuevas. ⚠️ Hay **10 fallos preexistentes y ajenos** documentados en `CLAUDE.md` §6 — esos no cuentan |

**V6 — la tabla está y tiene los 12 meses.** Bloque multilínea: al pegarlo en PowerShell puede quedarse en `>>`; pulsa Enter.

```powershell
uv run python -c "
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
load_dotenv('../.env')
e = create_engine(os.environ['DATABASE_URL'])
with e.connect() as c:
    print('filas:', c.execute(text('SELECT count(*) FROM core.p50_2026')).scalar())
    print('mayo:', c.execute(text('SELECT p50 FROM core.p50_2026 WHERE mes=5')).scalar())
"
```

Esperado: `filas: 12` y `mayo: 726.70`.

**V7 — 🔑 la prueba que decide: el respaldo NO pisa el dato ingerido.**

La BD local tiene el reporte del 2026-05-18, que **sí** trae `Upstream base_p50 = 726.73`. Por tanto `p50_respaldo` debe salir **`None`**, y `Upstream` en `totales` debe seguir con **726.73** (el ingerido, no el 726.70 de la tabla).

```powershell
uv run python -c "
from fastapi.testclient import TestClient
from app.main import app
r = TestClient(app).get('/analisis/president').json()
up = [t for t in r.get('totales',[]) if t['entidad']=='Upstream']
print('corte:', r.get('corte'), '| unidad:', r.get('unidad'))
print('p50_respaldo:', r.get('p50_respaldo'))
print('Upstream base_p50:', up[0]['base_p50'] if up else 'AUSENTE')
print('productos:', [p['entidad'] for p in r.get('productos',[])])
"
```

Esperado, **exactamente**:
- `corte: 2026-05-18` · `unidad: kbpe`
- `p50_respaldo: None`
- `Upstream base_p50: 726.73`
- `productos: ['Crudo', 'Gas', 'Blancos']` ← **tres, sin `Upstream` colado**

⚠️ **Si `p50_respaldo` NO es `None`, o `base_p50` sale `726.7`, o `productos` trae una cuarta entrada → el respaldo está pisando el dato ingerido. DETENTE y reporta.**

### 6.2 Humana — la hace el USUARIO

El executor **no puede** validar esto: no tiene navegador, y la app real corre en el **servidor de pruebas**, no en local.

| # | Qué mirar | Dónde |
|---|---|---|
| H-1 | El encabezado del panorama sigue igual que antes: las tres tarjetas Crudo/Gas/Blancos, con su cumplimiento. **Este plan no debe cambiar nada visible** | `http://localhost:5029` → panorama corporativo |
| H-2 | F12 → Console **sin errores** | Navegador |
| H-3 | F12 → Network → `/api/analisis/president` → la respuesta trae el campo `p50_respaldo` (en `null` si el mes está ingerido) | Navegador |
| H-4 | **En Pruebas:** aplicar la migración antes de dar por bueno el despliegue — `cd backend\backend` y `uv run python apply_migration.py ../db/migrations/011_p50_2026.sql`. Esperado: `[OK] Migracion aplicada: 011_p50_2026.sql` | Servidor de pruebas |

**Estado al terminar el executor: «implementado, PENDIENTE de validación humana».** Nunca «completado» (regla R3, `CLAUDE.md` §10.4).

---

## §7 Fuera de alcance

Lo siguiente **NO** se hace aquí. Está escrito para que el executor no tome iniciativas.

| Qué | Por qué |
|---|---|
| **Pintar el P50 de respaldo en pantalla** | H1+H2: el frontend solo lee `productos`, y esas cards son productos físicos. Requiere un plan de frontend con su propio diseño de tarjeta (una card de total, no de producto) |
| **Que el chat responda el P50 de meses no ingeridos** | H3: la rama global lee producto o `Ecopetrol`, y `formatear_cifra_global` exige real **y** P50. Plan aparte, con medición del golden |
| **Desbloquear el P50 en Cuantificar** (`ejecutor.py:110-114`) | Toca el Motor Q. Exige medir el golden de 92 casos antes y después (gate ≥90%), y hay un caso que **debe seguir rechazando** («¿cuánto produjo Rubiales vs el P50?») |
| **P50 por vicepresidencia** | La tabla es Upstream global. El P50 por VP sale de `NEW MES-AÑO` t8 en bpd — otra fuente, otra escala |
| **Cargar el real y la proyección de la lámina** | Decisión 2 del usuario: solo P50 por ahora |
| **Cargar la meta y la proyección ANUAL** (735,3 / 719,4) | Existen en la hoja `Reporte DPP` (tablas 4 y 5, fila `TOTAL UPSTREAM`) y **ya se ingieren**. Conectarlas es un plan distinto, y mejor que transcribir a mano |
| **Arreglar o renombrar `core.vw_p50_quemado`** | Mal nombrada (filtra `PPTO`, no P50) y con **cero consumidores**. Deuda real, ajena a este plan |
| **Reparar la corrupción de `fact_tabla_hoja`** | Solo afecta a la BD local (H9). Deuda conocida en `CLAUDE.md` §6 |
| **Migrar a Azure / desplegar** | Se hace con el skill `migrar-a-azure`, después de validar en Pruebas (`CLAUDE.md` §9) |
