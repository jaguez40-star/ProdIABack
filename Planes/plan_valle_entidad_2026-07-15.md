# Plan ejecutable — Valle explicado POR la entidad (Consulta · Desempeño ECP) · v1 (auditado)

> Ejecutable por un agente externo sin contexto. Rutas absolutas, código completo, decisiones cerradas.
> Al terminar: correr Validaciones y reportar tabla PASS/FAIL. **NO commitear** (lo hace el usuario).

---

## 0. Auditoría previa (§0.2 CLAUDE.md) — hallazgos verificados

**Contexto del bug (verificado en código + BD):** en el panel "Desempeño de {entidad}", la curva diaria de
crudo YA está filtrada a la entidad (`desempeno_insight`, `WHERE … AND (d.fuente_id IN :ids OR d.vice_id=:vid)`,
[api.py:669-674]), **pero** la tabla "POR QUÉ EL VALLE · EVENTOS" NO: `_eventos_valle(c, onset)` consulta
`fact_comentarios_produccion` solo por `fecha_reporte`, **sin filtro de entidad** ([api.py:505-516]) → muestra
los eventos GLOBALES de todos los campos (TIBU, CARACARA, HUILA…), no los de la entidad.

**Datos reales (verificados en BD):**
- Grano: `RUBIALES` → **1** `fuente_id` (un solo pozo/fuente en `dim_fuente`); `CASTILLA` → 5; `CHICHIMENE` → 9; `CUSIANA` → 3.
- **Rubiales SÍ reportó su motivo** el 2026-05-01 (inicio del valle): `[RUBIALES]` *"En proceso de
  estabilización luego de los eventos eléctricos presentados el día anterior."* — está en
  `fact_comentarios_produccion`, pero la tabla global lo ignora.

**Patrón a replicar:** ya existe `_valle_diagnostico_filiales` ([api.py:1351-1414]) que descompone el valle por
filial + `_valle_diag_fallback`. Este plan es su **análogo ECP** (descomposición por POZO + comentario de la entidad).

**Frontend:** `__cnRenderIns` ([multitab_shell.js:1378-1415]) pinta `valle_diagnostico` **solo si `__cnEsFil()`**
(línea 1402) → para ECP hay que abrir esa condición. La tabla de eventos (`d.eventos`) se pinta cuando no está vacía.

### Decisiones cerradas
| ID | Decisión |
|----|----------|
| **D-V1** | Panel **filtrado por entidad** → valle explicado POR la entidad; se **suprime** la tabla de eventos global (`eventos=[]`) y se entrega `valle_diagnostico`. |
| **D-V2** | Panel **GLOBAL** (sin entidad) → **sin cambios**: conserva la tabla de eventos global actual. |
| **D-V3** | El diagnóstico de entidad combina: **(A)** el/los comentario(s) que la entidad reportó el día de inicio del valle (motivo documentado real), y **(B)** si la entidad tiene **>1 pozo**, la descomposición por pozo (cuál cayó vs su promedio del resto del mes). |
| **D-V4** | **Determinista, sin LLM** (el comentario ES la causa; no hay que inventar nada). `generado_por:"base"`. Pulido con Gemma = iteración futura. |
| **D-V5** | 1 pozo (ej. Rubiales) → sin descomposición (el pozo ES la entidad); se usa su comentario. Si no hay comentario ni caída atribuible → fallback honesto ("revisar con operaciones de {entidad}"). |

---

## 1. Objetivo

`GET /analisis/desempeno_insight?entidad=RUBIALES` debe devolver `valle_diagnostico` (con el comentario real
de Rubiales) y `eventos:[]`. El panel GLOBAL (`?` sin entidad) queda idéntico (eventos globales, `valle_diagnostico:null`).
El frontend pinta la tarjeta "Diagnóstico del valle" también para entidades ECP.

---

## 2. Inventario de archivos

Raíz = `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA`.

| # | Archivo | Acción |
|---|---------|--------|
| B1 | `INGESTA\Rep_Prod\backend\app\features\analisis\api.py` | **EDIT** — nueva `_valle_diagnostico_entidad()` + branch en `desempeno_insight` + campo en el return. |
| B2 | `static\js\multitab_shell.js` | **EDIT** — `__cnRenderIns` pinta `valle_diagnostico` también para ECP. |
| B3 | `templates\main.html` | **EDIT** — cache-buster `?v=`. |

**Prohibido editar:** `_eventos_valle` (el global se conserva), `_valle_diagnostico_filiales`, `desempeno`, `ejecutivo`, `routes\api.py`.

---

## 3. Especificación

### B1.1 — NUEVA función `_valle_diagnostico_entidad` (api.py)

Insertar **justo después** de `_eventos_valle` (después de la línea 529, antes de `_extraer_json` / la sección de titular):

```python
def _valle_diagnostico_entidad(c, entidad, ids, vid, valle, y, mo, dim, onset):
    """Valle explicado POR la entidad (ECP). Determinista (sin LLM): (A) el/los comentario(s) que la
    entidad reportó el día de inicio del valle (motivo documentado real) y (B) si tiene >1 pozo, qué
    pozos cayeron (avg en días del valle vs avg en el resto del mes). Análogo ECP de
    _valle_diagnostico_filiales. NUNCA inventa causas: el comentario ES la causa (cuando existe)."""
    desde, hasta = valle["desde"], valle["hasta"]
    ini = f"{y:04d}-{mo:02d}-01"; fin = f"{y:04d}-{mo:02d}-{dim:02d}"

    # where sobre fact_produccion_dia_ecp (mismo criterio que el resto del insight)
    conds, params = [], {"ini": ini, "fin": fin, "desde": desde, "hasta": hasta}
    if ids: conds.append("d.fuente_id IN :ids"); params["ids"] = ids
    if vid is not None: conds.append("d.vice_id = :vid"); params["vid"] = vid
    where_d = "(" + " OR ".join(conds) + ")" if conds else "TRUE"

    # (B) descomposición por POZO: avg en días del valle vs avg en el resto del mes
    q = sa.text(f"""
        WITH dd AS (
          SELECT f.nombre pozo, d.fecha, SUM(d.volumen) v
          FROM core.fact_produccion_dia_ecp d
          JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = d.tipo_producto_id
          JOIN core.dim_fuente f ON f.fuente_id = d.fuente_id
          WHERE tp.nombre='CRUDO' AND d.fecha BETWEEN :ini AND :fin AND {where_d}
          GROUP BY 1, 2)
        SELECT pozo,
          AVG(v) FILTER (WHERE fecha BETWEEN :desde AND :hasta)     AS avg_valle,
          AVG(v) FILTER (WHERE fecha NOT BETWEEN :desde AND :hasta) AS avg_ref
        FROM dd GROUP BY 1""")
    if ids: q = q.bindparams(sa.bindparam("ids", expanding=True))
    rows = c.execute(q, params).all()
    drivers = []
    if len(rows) > 1:   # 1 pozo => el pozo ES la entidad (redundante) => sin descomposición
        for pozo, av, ar in rows:
            av = float(av or 0); ar = float(ar or 0)
            pct = round((av - ar) / ar * 100, 1) if ar else None
            if pct is not None and pct <= -3:
                drivers.append({"pozo": (pozo or "").strip(), "prod_valle": round(av),
                                "prod_ref": round(ar), "caida": round(av - ar), "caida_pct": pct})
        drivers.sort(key=lambda x: x["caida"])   # más negativo primero

    # (A) comentario(s) que la entidad reportó el día de inicio del valle
    if ids:
        nrows = c.execute(sa.text(
            "SELECT nombre, campo, grupo1, activos FROM core.dim_fuente WHERE fuente_id IN :ids"
        ).bindparams(sa.bindparam("ids", expanding=True)), {"ids": ids}).all()
    elif vid is not None:
        nrows = c.execute(sa.text(
            "SELECT nombre, campo, grupo1, activos FROM core.dim_fuente WHERE vice_id = :vid"), {"vid": vid}).all()
    else:
        nrows = []
    names = set()
    for r in nrows:
        for x in r:
            if x and str(x).strip():
                names.add(str(x).strip().upper())
    comentarios = []
    if names:
        cq = sa.text("""
            SELECT COALESCE(NULLIF(TRIM(fc.area),''), fc.activos) AS campo, fc.comentario
            FROM core.fact_comentarios_produccion fc
            JOIN core.config_reporte cr ON cr.reporte_id = fc.reporte_id
            WHERE cr.fecha_reporte = :onset
              AND fc.comentario IS NOT NULL AND LENGTH(TRIM(fc.comentario)) > 5
              AND (UPPER(TRIM(fc.area)) IN :names OR UPPER(TRIM(fc.activos)) IN :names)
        """).bindparams(sa.bindparam("names", expanding=True))
        for campo, com in c.execute(cq, {"onset": onset, "names": list(names)}):
            comentarios.append({"campo": (campo or "").strip(), "texto": (com or "").strip()[:220]})

    # composición determinista
    pozos_txt = ", ".join(f"{d['pozo']} ({d['caida_pct']}%)" for d in drivers[:3])
    if comentarios:
        diag = f"Lo que reportó {entidad} el {desde}: «{comentarios[0]['texto']}»"
        if drivers:
            diag += f" La caída se reflejó en {pozos_txt}."
        reco = None
    elif drivers:
        diag = (f"El valle de crudo ({desde} a {hasta}) de {entidad} se concentró en {pozos_txt}. "
                "El reporte diario no documenta un motivo operativo específico.")
        reco = f"Se recomienda revisar con operaciones de {entidad} la causa raíz de la caída."
    else:
        diag = (f"El valle de crudo ({desde} a {hasta}) de {entidad} no tiene un motivo documentado "
                "en el reporte diario ni se concentra en un pozo en particular.")
        reco = f"Se recomienda revisar con operaciones de {entidad} la causa de la caída."

    return {"valle": {"desde": desde, "hasta": hasta}, "drivers": drivers, "comentarios": comentarios,
            "generado_por": "base", "diagnostico": diag, "recomendacion": reco}
```

### B1.2 — Branch en `desempeno_insight` (api.py)

Reemplazar el bloque (líneas 679-687):
```python
        anotaciones, eventos, eventos_extra = None, [], {"campos": 0, "pozos_aprox": 0}
        if valle:
            from datetime import date as _date
            dd = [int(x) for x in valle["desde"].split("-")]
            eventos, eventos_extra = _eventos_valle(c, _date(*dd))   # INS-A: solo el día de inicio del valle
            anotaciones = {
                "banda": {"desde": valle["desde"], "hasta": valle["hasta"], "label": "valle"},
                "punto": {"fecha": valle["min_fecha"], "valor": valle["min_valor"], "label": ""},
            }
```
por:
```python
        anotaciones, eventos, eventos_extra = None, [], {"campos": 0, "pozos_aprox": 0}
        valle_diag = None
        if valle:
            from datetime import date as _date
            dd = [int(x) for x in valle["desde"].split("-")]
            onset = _date(*dd)
            if entidad:   # panel filtrado → valle explicado POR la entidad (su comentario + sus pozos). D-V1
                valle_diag = _valle_diagnostico_entidad(c, entidad, ids, vid, valle, y, mo, dim, onset)
            else:         # panel GLOBAL → tabla de eventos global (comportamiento actual). D-V2
                eventos, eventos_extra = _eventos_valle(c, onset)
            anotaciones = {
                "banda": {"desde": valle["desde"], "hasta": valle["hasta"], "label": "valle"},
                "punto": {"fecha": valle["min_fecha"], "valor": valle["min_valor"], "label": ""},
            }
```

### B1.3 — Campo en el return de `desempeno_insight` (api.py)

En el `return { … }` (líneas 779-791), añadir el campo `valle_diagnostico` **después** de la línea de `eventos`:
```python
            "eventos": eventos, "eventos_extra": eventos_extra,
```
→
```python
            "eventos": eventos, "eventos_extra": eventos_extra,
            "valle_diagnostico": valle_diag,   # D-V1: valle explicado por la entidad (None en el panel global)
```

### B2 — EDIT `multitab_shell.js` (`__cnRenderIns`)

Reemplazar la condición (línea 1402):
```javascript
    if (__cnEsFil() && vd && (vd.diagnostico || vd.recomendacion)) {
```
por:
```javascript
    if (vd && (vd.diagnostico || vd.recomendacion)) {   // filiales O entidad ECP con diagnóstico de valle
```
> Sin más cambios: para ECP el backend ya devuelve `eventos:[]` (no se pinta la tabla global) y
> `valle_diagnostico` con el comentario/pozos. Para filiales sigue igual. El GLOBAL no trae
> `valle_diagnostico` → la condición es falsa → conserva su tabla de eventos.

### B3 — EDIT `templates\main.html`

Subir el cache-buster de `20260715k` a `20260715l` en las 2 referencias.

---

## 4. Orden de ejecución

1. **V0** (línea base): `GET /analisis/desempeno_insight?entidad=RUBIALES` → `eventos` con campos ajenos (TIBU…), sin `valle_diagnostico`.
2. B1 (las 3 sub-ediciones) → B2 → B3.
3. Reiniciar el backend INGESTA (`:8088`) para cargar el código (sin `--reload`, matar/relanzar).
4. **V1–V5**. Reportar tabla PASS/FAIL. **No commitear.**

---

## 5. Reglas no negociables

- **El GLOBAL no se toca** (D-V2): sin `entidad`, la respuesta debe ser idéntica a hoy (`eventos` global, `valle_diagnostico:null`).
- **Determinista, sin LLM** (D-V4): `_valle_diagnostico_entidad` no llama a Ollama/`_llm_insight`.
- **No inventar causas**: el texto sale del comentario real o de las cifras de caída; nunca de una causa supuesta.
- **No tocar** `_eventos_valle`, `_valle_diagnostico_filiales`, `desempeno`, `ejecutivo`, `routes\api.py`.
- **Aditivo**: la respuesta solo GANA el campo `valle_diagnostico` (y `eventos` pasa a `[]` cuando hay entidad).

---

## 6. Validaciones (comando → esperado)

| ID | Acción | Esperado |
|----|--------|----------|
| **V1** | `GET http://localhost:8088/analisis/desempeno_insight?entidad=RUBIALES` | `valle_diagnostico` presente; `diagnostico` contiene *"estabilización"* (el comentario real de Rubiales); `eventos` = `[]`. |
| **V2** | `GET http://localhost:8088/analisis/desempeno_insight?entidad=CHICHIMENE` | `valle_diagnostico` con `drivers` NO vacío (pozos que cayeron), o comentario de Chichimene; `eventos` = `[]`. |
| **V3** | `GET http://localhost:8088/analisis/desempeno_insight` (SIN entidad) | **Sin regresión**: `eventos` global con campos (TIBU/CARACARA…), `valle_diagnostico` = `null`. |
| **V4** | `GET http://localhost:8088/analisis/desempeno_insight?entidad=RUBIALES` (revisar forma) | `curva_crudo` y `titular` intactos (solo Rubiales); nada más cambia salvo eventos/valle_diagnostico. |
| **V5** | Navegador (Ctrl+F5): Consulta → "cuánto produjo Rubiales de crudo" → panel Desempeño | La tarjeta **"Diagnóstico del valle (base)"** muestra el motivo de Rubiales (estabilización eléctrica); **ya NO** aparece la tabla global "Por qué el valle · eventos" con TIBU/CARACARA. 0 errores de consola. |

> Sugerencia para V1/V2/V3 sin servidor arriba: `cd INGESTA\Rep_Prod\backend; uv run python -c "from app.features.analisis.api import desempeno_insight as f; import json; print(json.dumps(f(entidad='RUBIALES'), ensure_ascii=False, default=str)[:1200])"` — nota: `desempeno_insight` es un route handler; al llamarlo directo, `segmento` queda como objeto Query pero NO se compara con "filiales" salvo `== 'filiales'` (seguro). Para forzar: pasar `segmento='ecp'`.

---

## 7. Fuera de alcance

- **Pulido con Gemma** del diagnóstico de entidad → iteración futura (hoy es determinista).
- **Descomposición por pozo en entidades de 1 fuente** (Rubiales) → no aplica (el pozo ES la entidad).
- **Panel GLOBAL** → intacto.
- **Matching de comentarios por vicepresidencia sin fuente** (vid puro): usa los nombres de `dim_fuente` bajo el `vice_id`; si no hay match, cae al fallback honesto. No se refina más en esta iteración.
