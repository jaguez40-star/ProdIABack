# Plan A (auditado) — Conteo de jerarquía: enrutar a Jerarquizar (R1) + conteo real de pozos (R3)

> **Modo:** ejecutable por un Executor externo. Rutas ABSOLUTAS. Código de referencia COMPLETO.
> **Fecha:** 2026-08-03 · **Planner:** Claude · **Auditado v2** (§0.2 del CLAUDE.md de INGESTA).
> Cierra 2.1 + 2.2 del `HALLAZGO_clasificador_conteo_jerarquia.md` + el gap de pozos hallado en auditoría.
> **R2 (etiquetado GOR en producción) va en un plan aparte** (Plan B) — NO se toca aquí.

**Cobertura: 2 piezas → 2** (R1 enrutamiento · R3 conteo de pozos). Sin recortes.

---

## 0. Auditoría (reproducida contra BD real, 2026-08-03)

**El hallazgo, verificado vigente** (`clasificar_capa1` directo): *"¿cuántos pozos tiene Castilla?"*,
*"¿cuántas gerencias tiene GOR?"*, *"¿cuántos campos tiene la gerencia GOR?"*, *"¿cuántos activos tiene
Rubiales?"* → **todas** `cuantificar` vía `CUANT[OA]S?\b`, y responden **producción** (pregunta distinta).

**🔑 Hallazgo que amplía el hallazgo original — el conteo se parte en dos:**
- **Jerarquizar YA cuenta** campo/activo/gerencia/vicepresidencia (embebido en `_cuerpo`: *"Campos (N):
  …"*, *"Activos (N): …"*, *"Gerencias (N): …"*). → enrutar esos conteos a Jerarquizar **funciona hoy**.
- **NADIE cuenta pozos.** `conteo_pozos` solo está DISEÑADO en `variables_cuantificables.yaml` (líneas
  120-131); no hay código que haga `COUNT(DISTINCT uwi)`. → *"¿cuántos pozos tiene Castilla?"* no tiene
  respuesta en ningún módulo. Por eso R1 (enrutar) **no basta** para pozos; hace falta R3 (construir el
  conteo). Los otros conteos sí quedan resueltos solo con R1.

**Datos del conteo de pozos, VERIFICADOS contra BD (cross-DB):**
- `get_ops_engine()` (conexión `robustez_v02`, esquema `ops`) **existe y funciona** (lo usa el feature
  `ebitda`). `ops.wells_attributes` = `uwi, vice_presidency, management, active, field, zone, …` · 13.482 pozos.
- **Join key confirmado:** `core.map_campo_robustez.rob_field` == `ops.wells_attributes.field`.
  Castilla → `rob_field='CASTILLA'` → `COUNT(DISTINCT uwi) WHERE field='CASTILLA'` = **437**.
- **Conteo por nivel** = unión de los `rob_field` del nivel: Activo CASTILLA (campos CASTILLA +
  CASTILLA NORTE) → `COUNT(DISTINCT uwi) WHERE field = ANY(rob_fields)` = **766**.
- 🔑 **Regla del catálogo confirmada:** el join por `rob_field` (766) DIFIERE de la columna aliaseada
  `active` (767) → contar por la jerarquía canónica de `map_campo_robustez`, NUNCA por las columnas de
  `wells_attributes`. `COUNT(DISTINCT uwi)` dedup automático → nunca suma subconteos (747 uwi en >1 campo).

### 0.1 — Verificación del plan contra el código real (delta v1 → v2, 2026-08-03)

| # | Hallazgo | Efecto si no se corrige | Corrección |
|---|---|---|---|
| **H1** 🔴 | **El patrón R1 de la v1 era DEMASIADO AMPLIO y causaba regresión de enrutamiento.** `CUANT[OA]S?\s+(CAMPOS?\|POZOS?\|ACTIVOS?\|GERENCIAS?)` (sin verbo) captura, verificado en vivo: *"cuántos campos están por debajo de la meta"* (hoy **analizar**), *"cuántos campos pesan más en el gap"* (**analizar**), *"cuántos pozos produjeron en mayo"* (**cuantificar**), *"cuántos campos incumplieron el presupuesto"* (**cuantificar**), *"cuántos activos están en foco"* (**cuantificar**). Como el patrón vive en `precedencia_maxima`, **sobrescribe TODO** → las 5 habrían pasado a Jerarquizar y respondido estructura en vez de análisis/cifra. | 5 preguntas legítimas rotas, incluyendo el terreno de Analizar. Regresión peor que el bug que arregla. | El patrón **exige el verbo estructural** (`TIENE[N]?\|CONFORMAN\|INTEGRAN\|COMPONEN\|AGRUPA\|HAY\s+EN`). Verificado: **6/6** capturas correctas de conteo, **0/6** falsos positivos. |
| **H2** 🟡 | El plan v1 declaraba `6 passed` en V3 con **5** funciones de test. | Criterio no verificable. | Conteo exacto **7** (5 originales + 2 guardas de regresión nuevas, §4.4). |
| **H3** 🟡 | La salida esperada de V2 citaba el patrón viejo. | El Executor no puede comparar. | V2 actualizado al patrón acotado. |
| **H4** ✅ | **Degradación de `ops` confirmada:** `get_ops_engine()` hace `raise RuntimeError("OPS_DATABASE_URL no configurada")` si falta la URL, y `pool_pre_ping` da `OperationalError` si la BD no responde. El `except Exception` de `_contar_pozos` captura ambos → `None` → línea omitida. **139 sin `robustez_v02` NO rompe.** | — | sin cambio |
| **H5** ✅ | **El filtro de dominio SIGUE aplicando** al patrón nuevo (no se ancla): *"cuántos campos hay en la dieta mediterránea"* no trae entidad y `campos` es vocabulario `estructural` → escala a Capa 2, no entra a Jerarquizar a ciegas. | — | sin cambio |

**Mejora incorporada:** las 5 frases de la regresión H1 entran como **guardas permanentes** — al golden
(§4.3) y a los tests (§4.4) — para que el defecto no pueda reaparecer al crecer el patrón (principio
`audit_motor_clas.md §3`: el error verificado se convierte en regresión permanente).

**Decisiones cerradas:**
- El conteo de pozos vive en **Jerarquizar** (donde ya viven los otros conteos → menor sorpresa; R1 ya
  envía los conteos allí). La sección `conteos:` del catálogo de Cuantificar queda como diseño no usado.
- R1 toca `patrones_grupo.yaml` → **exige el ciclo de golden** (casos verificados + golden en verde),
  regla del propio archivo. Este plan añade los casos al golden.
- R3 **degrada con gracia**: si `get_ops_engine()` falla (p.ej. 139 sin `robustez_v02`), se **omite** la
  línea de pozos — la respuesta de estructura sigue intacta. Nunca rompe.
- El patrón nuevo de R1 **NO** va en `patrones_anclados`: un *"cuántos pozos"* SIN entidad debe pasar por
  el filtro de dominio (vocabulario `estructural` → escala a Capa 2), como el resto de la franja estructural.

---

## 1. Objetivo

- **R1:** *"cuántos/cuántas (pozos|campos|gerencias|activos) …"* se clasifica **Jerarquizar** (no
  Cuantificar), vía `precedencia_maxima` (mismo mecanismo que ya protege "días con reporte").
- **R3:** Jerarquizar añade una línea **"Pozos: N"** (COUNT DISTINCT uwi desde `robustez_v02`, por los
  `rob_field` del nivel) a campo/activo/gerencia/vicepresidencia — con degradación si `ops` no está.

---

## 2. Prerequisitos + baseline

Desde `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend`:

```
uv run python -c "import app.features.consulta_v2.respuesta_jerarquizar, app.features.consulta_v2.patrones; from app.core.db import get_ops_engine; print('IMPORTS OK')"
```
Esperado: `IMPORTS OK`.

**Baseline (capturar ANTES de editar):**
```
uv run pytest tests/test_consulta_v2_clasificador.py -q
```
Anotar el resumen (se compara en V4).

**Regla de entorno:** en dev NO se levanta backend ni LLM. Validación estática: `py_compile` + tests
puros (monkeypatch, sin BD/LLM) + golden de los casos DETERMINISTAS (Capa 1, sin LLM). La verificación
del conteo REAL contra `robustez_v02` la hace el usuario en el servidor de pruebas (humo).

---

## 3. Inventario de archivos

(`...` = `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA`)

| Archivo (ruta absoluta) | Acción |
|---|---|
| `...\INGESTA\Rep_Prod\backend\app\features\consulta_v2\config\patrones_grupo.yaml` | **EDITAR** (R1: patrón en `precedencia_maxima.jerarquizar`) |
| `...\INGESTA\Rep_Prod\backend\app\features\consulta_v2\respuesta_jerarquizar.py` | **EDITAR** (R3: rob_field + conteo de pozos) |
| `...\INGESTA\Rep_Prod\backend\app\features\consulta_v2\golden\clasificacion_golden.yaml` | **EDITAR** (R1: casos de conteo) |
| `...\INGESTA\Rep_Prod\backend\tests\test_conteo_jerarquia.py` | **CREAR** (tests puros R1 + R3) |

**NO se toca:** `cuantificar/*` (eso es Plan B/R2), `slots.py`, `ejecutor.py`, `dominio.py`,
`maquina_q.py`, `no_soportado.py`, migraciones, frontend.

---

## 4. Especificación (código literal)

### 4.1 — R1: EDITAR `patrones_grupo.yaml`

Ruta: `...\INGESTA\Rep_Prod\backend\app\features\consulta_v2\config\patrones_grupo.yaml`

Localizar el bloque `precedencia_maxima:` → `jerarquizar:` (empieza con `- 'QUE INFORMACION'`). Añadir,
como PRIMER ítem de esa lista (antes de `- 'QUE INFORMACION'`):

```yaml
    # Conteo de jerarquía: "cuántos pozos/campos/gerencias/activos TIENE X". Trae CUANTOS pero pide
    # ESTRUCTURA (nº de sub-entidades), no una cifra. Mismo mecanismo que "días con reporte" (huella):
    # se evalúa ANTES que el 'CUANT[OA]S?\b' de cuantificar → gana el enrutamiento.
    # 🔑 EXIGE EL VERBO ESTRUCTURAL (TIENE/CONFORMAN/…/HAY EN). Sin él, el patrón se tragaba preguntas
    # de OTROS grupos y —al vivir en precedencia_maxima— las sobrescribía TODAS (regresión verificada
    # 2026-08-03): "cuántos campos están por debajo de la meta" y "cuántos campos pesan en el gap" son
    # ANALIZAR; "cuántos pozos produjeron en mayo" e "cuántos campos incumplieron el presupuesto" son
    # CUANTIFICAR. Con el verbo, esas 5 dejan de calzar y conservan su grupo.
    # NO se ancla (fuera de patrones_anclados): sin entidad, "pozos/campos/…" es vocabulario
    # ESTRUCTURAL → pasa por el filtro de dominio y escala a Capa 2 (franja estructural).
    - 'CUANT[OA]S?\s+(CAMPOS?|POZOS?|ACTIVOS?|GERENCIAS?)\s+(TIENE[N]?|CONFORMAN|INTEGRAN|COMPONEN|AGRUPA|HAY\s+EN)'
```

**NO** añadir esta cadena a `patrones_anclados`. El resto del YAML NO cambia.

### 4.2 — R3: EDITAR `respuesta_jerarquizar.py`

Ruta: `...\INGESTA\Rep_Prod\backend\app\features\consulta_v2\respuesta_jerarquizar.py`

**R3-a — actualizar el docstring del módulo.** Reemplazar las líneas (17-18):

```python
Alcance MVP: campo/activo/gerencia/vicepresidencia (+ operador para terceros). El CONTEO de pozos
NO vive aquí — es del motor de Cuantificar (grano uwi en robustez_v02.ops.wells_attributes).
```
por:
```python
Alcance: campo/activo/gerencia/vicepresidencia (+ operador para terceros). El CONTEO de pozos SÍ vive
aquí (R3, 2026-08-03): COUNT(DISTINCT uwi) sobre robustez_v02.ops.wells_attributes por los rob_field
del nivel (get_ops_engine, cross-DB). Degrada con gracia: si ops no está (p.ej. 139 sin robustez_v02),
se omite la línea de pozos y la estructura sigue intacta.
```

**R3-b — añadir el import de `get_ops_engine`.** Reemplazar:
```python
from app.core.db import get_engine
```
por:
```python
from app.core.db import get_engine, get_ops_engine
```

**R3-c — traer `rob_field` en `_cargar` y construir los mapas de nivel→rob_fields.**

Reemplazar el `SELECT` de `_cargar` (dentro de `with eng.connect() as c:`):
```python
        rows = c.execute(sa.text("""
            SELECT campo, operador, es_ecp, rob_activo, rob_gerencia, rob_vicepresidencia
            FROM core.map_campo_robustez""")).mappings().all()
```
por (añade `rob_field`):
```python
        rows = c.execute(sa.text("""
            SELECT campo, operador, es_ecp, rob_field, rob_activo, rob_gerencia, rob_vicepresidencia
            FROM core.map_campo_robustez""")).mappings().all()
```

En el mismo `_cargar`, añadir los acumuladores de rob_fields. Reemplazar:
```python
    act_campos, ger_campos, vp_campos, op_campos = {}, {}, {}, {}
    ger_activos, vp_ger, vp_activos = {}, {}, {}
```
por:
```python
    act_campos, ger_campos, vp_campos, op_campos = {}, {}, {}, {}
    ger_activos, vp_ger, vp_activos = {}, {}, {}
    # R3: rob_field por nivel (para COUNT(DISTINCT uwi) en robustez_v02). El rob_field es la clave de
    # join con ops.wells_attributes.field (verificado: rob_field==field).
    act_fields, ger_fields, vp_fields = {}, {}, {}
```

Dentro del bucle `for r in rows:`, añadir la captura de `rob_field` y poblar los mapas. Reemplazar:
```python
        campo = (r["campo"] or "").strip()
        op = (r["operador"] or "").strip()
        act = (r["rob_activo"] or "").strip()
        ger = (r["rob_gerencia"] or "").strip()
        vp = (r["rob_vicepresidencia"] or "").strip()
        kc = norm(campo)
        campo_row[kc] = {"campo": campo, "operador": op, "es_ecp": bool(r["es_ecp"]),
                         "activo": act or None, "gerencia": ger or None, "vp": vp or None}
```
por:
```python
        campo = (r["campo"] or "").strip()
        op = (r["operador"] or "").strip()
        rf = (r["rob_field"] or "").strip()
        act = (r["rob_activo"] or "").strip()
        ger = (r["rob_gerencia"] or "").strip()
        vp = (r["rob_vicepresidencia"] or "").strip()
        kc = norm(campo)
        campo_row[kc] = {"campo": campo, "operador": op, "es_ecp": bool(r["es_ecp"]),
                         "rob_field": rf or None,
                         "activo": act or None, "gerencia": ger or None, "vp": vp or None}
```

Aún dentro del bucle, poblar los mapas de fields por nivel. Reemplazar:
```python
        if act:
            idx.setdefault(norm(act), set()).add(("activo", act))
            _add(act_campos, norm(act), campo)
        if ger:
            idx.setdefault(norm(ger), set()).add(("gerencia", ger))
            _add(ger_campos, norm(ger), campo)
            if act:
                ger_activos.setdefault(norm(ger), set()).add(act)
        if vp:
            idx.setdefault(norm(vp), set()).add(("vicepresidencia", vp))
            _add(vp_campos, norm(vp), campo)
            if ger:
                vp_ger.setdefault(norm(vp), set()).add(ger)
            if act:
                vp_activos.setdefault(norm(vp), set()).add(act)
```
por (añade el poblado de *_fields con `rf`):
```python
        if act:
            idx.setdefault(norm(act), set()).add(("activo", act))
            _add(act_campos, norm(act), campo)
            if rf:
                act_fields.setdefault(norm(act), set()).add(rf)
        if ger:
            idx.setdefault(norm(ger), set()).add(("gerencia", ger))
            _add(ger_campos, norm(ger), campo)
            if act:
                ger_activos.setdefault(norm(ger), set()).add(act)
            if rf:
                ger_fields.setdefault(norm(ger), set()).add(rf)
        if vp:
            idx.setdefault(norm(vp), set()).add(("vicepresidencia", vp))
            _add(vp_campos, norm(vp), campo)
            if ger:
                vp_ger.setdefault(norm(vp), set()).add(ger)
            if act:
                vp_activos.setdefault(norm(vp), set()).add(act)
            if rf:
                vp_fields.setdefault(norm(vp), set()).add(rf)
```

Finalmente, incluir los mapas nuevos en `_DATA`. Reemplazar:
```python
    _DATA = {"idx": idx, "campo_row": campo_row, "act_campos": act_campos,
             "ger_campos": ger_campos, "vp_campos": vp_campos, "op_campos": op_campos,
             "ger_activos": ger_activos, "vp_ger": vp_ger, "vp_activos": vp_activos}
    return _DATA
```
por:
```python
    _DATA = {"idx": idx, "campo_row": campo_row, "act_campos": act_campos,
             "ger_campos": ger_campos, "vp_campos": vp_campos, "op_campos": op_campos,
             "ger_activos": ger_activos, "vp_ger": vp_ger, "vp_activos": vp_activos,
             "act_fields": act_fields, "ger_fields": ger_fields, "vp_fields": vp_fields}
    return _DATA
```

**R3-d — añadir el helper `_contar_pozos`.** Insertar INMEDIATAMENTE ANTES de `def _cuerpo(niv, canonical, data):`

```python
def _contar_pozos(rob_fields):
    """COUNT(DISTINCT uwi) en robustez_v02.ops.wells_attributes para los rob_field dados, o None.
    None = no hay fields (terceros sin robustez) o `ops` no está disponible (p.ej. 139 sin
    robustez_v02) → el llamador OMITE la línea de pozos (degradación con gracia). NUNCA lanza.
    🔑 COUNT(DISTINCT uwi) dedup automático → nunca suma subconteos (747 uwi en >1 campo). Se cuenta
    por rob_field (jerarquía canónica de map_campo_robustez), NO por las columnas aliaseadas de
    wells_attributes (verificado: difieren)."""
    fields = sorted({f for f in (rob_fields or set()) if f})
    if not fields:
        return None
    try:
        with get_ops_engine().connect() as c:
            return c.execute(sa.text(
                "SELECT COUNT(DISTINCT uwi) FROM ops.wells_attributes WHERE field = ANY(:fs)"),
                {"fs": fields}).scalar()
    except Exception:
        return None
```

**R3-e — pintar la línea de pozos en `_cuerpo`.** En cada nivel, añadir la línea cuando el conteo no
sea None. Reemplazos EXACTOS por nivel:

*Campo* — reemplazar:
```python
        if act:
            lineas.append(f"Otros campos del Activo {act}: "
                          f"{_lista(hermanos) if hermanos else 'ninguno (es el único)'}")
        return _bloque(f"«{canonical}» · Campo", lineas)
```
por:
```python
        if act:
            lineas.append(f"Otros campos del Activo {act}: "
                          f"{_lista(hermanos) if hermanos else 'ninguno (es el único)'}")
        npz = _contar_pozos({row.get("rob_field")})
        if npz is not None:
            lineas.append(f"Pozos: {npz}")
        return _bloque(f"«{canonical}» · Campo", lineas)
```

*Activo* — reemplazar:
```python
        lineas = [
            _uno_o_varios("Gerencia", "Gerencias", gers),
            _uno_o_varios("Vicepresidencia", "Vicepresidencias", vps),
            f"Campos ({len(set(campos))}): {_lista(campos)}",
        ]
        return _bloque(f"«{canonical}» · Activo", lineas)
```
por:
```python
        npz = _contar_pozos(data["act_fields"].get(norm(canonical), set()))
        lineas = [
            _uno_o_varios("Gerencia", "Gerencias", gers),
            _uno_o_varios("Vicepresidencia", "Vicepresidencias", vps),
            f"Campos ({len(set(campos))}): {_lista(campos)}",
            f"Pozos: {npz}" if npz is not None else None,
        ]
        return _bloque(f"«{canonical}» · Activo", lineas)
```

*Gerencia* — reemplazar:
```python
        lineas = [
            _uno_o_varios("Vicepresidencia", "Vicepresidencias", vps),
            f"Activos ({len(activos)}): {_lista(activos)}" if activos else None,
            f"Campos ({len(set(campos))}): {_lista(campos)}",
        ]
        return _bloque(f"«{canonical}» · Gerencia", lineas)
```
por:
```python
        npz = _contar_pozos(data["ger_fields"].get(norm(canonical), set()))
        lineas = [
            _uno_o_varios("Vicepresidencia", "Vicepresidencias", vps),
            f"Activos ({len(activos)}): {_lista(activos)}" if activos else None,
            f"Campos ({len(set(campos))}): {_lista(campos)}",
            f"Pozos: {npz}" if npz is not None else None,
        ]
        return _bloque(f"«{canonical}» · Gerencia", lineas)
```

*Vicepresidencia* — reemplazar:
```python
        lineas = [
            f"Gerencias ({len(gers)}): {_lista(gers)}" if gers else "Gerencias: 0",
            f"Activos ({len(activos)}): {_lista(activos)}" if activos else None,
            f"Campos ({len(set(campos))}): {_lista(campos)}",
        ]
        return _bloque(f"«{canonical}» · Vicepresidencia", lineas)
```
por:
```python
        npz = _contar_pozos(data["vp_fields"].get(norm(canonical), set()))
        lineas = [
            f"Gerencias ({len(gers)}): {_lista(gers)}" if gers else "Gerencias: 0",
            f"Activos ({len(activos)}): {_lista(activos)}" if activos else None,
            f"Campos ({len(set(campos))}): {_lista(campos)}",
            f"Pozos: {npz}" if npz is not None else None,
        ]
        return _bloque(f"«{canonical}» · Vicepresidencia", lineas)
```

(El nivel `operador` NO lleva pozos: los terceros no están en robustez. NO se toca.)

### 4.3 — R1: EDITAR `clasificacion_golden.yaml` (casos de conteo)

Ruta: `...\INGESTA\Rep_Prod\backend\app\features\consulta_v2\golden\clasificacion_golden.yaml`

Formato VERIFICADO del archivo: cada caso es `- pregunta: "..."` + línea `  esperado: <grupo>` (2
espacios de indentación, sin comillas en el grupo). Añadir estos 4 casos al final de la lista, con una
línea de comentario `# ---- conteo de jerarquia (R1) ----` encima:

```yaml
# ---- conteo de jerarquia (R1) ----
- pregunta: "¿Cuántos pozos tiene Castilla?"
  esperado: jerarquizar
- pregunta: "¿Cuántas gerencias tiene la vicepresidencia GOR?"
  esperado: jerarquizar
- pregunta: "¿Cuántos campos tiene la gerencia GOR?"
  esperado: jerarquizar
- pregunta: "¿Cuántos activos tiene Rubiales?"
  esperado: jerarquizar
# ---- guardas de regresion R1 (H1): "cuantos <sustantivo>" SIN verbo estructural NO es jerarquizar.
#      Verificado 2026-08-03: el patron sin verbo se las tragaba desde precedencia_maxima.
- pregunta: "¿Cuántos campos están por debajo de la meta?"
  esperado: analizar
- pregunta: "¿Cuántos campos pesan más en el gap?"
  esperado: analizar
- pregunta: "¿Cuántos pozos produjeron en mayo?"
  esperado: cuantificar
- pregunta: "¿Cuántos campos incumplieron el presupuesto?"
  esperado: cuantificar
- pregunta: "¿Cuántos activos están en foco?"
  esperado: cuantificar
```

### 4.4 — CREAR `test_conteo_jerarquia.py`

Ruta: `...\INGESTA\Rep_Prod\backend\tests\test_conteo_jerarquia.py`

```python
"""Tests PUROS (sin BD/LLM) de R1 (enrutamiento de conteo) y R3 (línea de pozos con degradación)."""
import app.features.consulta_v2.respuesta_jerarquizar as RJ
from app.features.consulta_v2.patrones import clasificar_capa1


# --- R1: el conteo de jerarquía se clasifica jerarquizar por Capa 1 (precedencia_maxima) ----------
def test_r1_conteo_va_a_jerarquizar():
    for q in ["¿cuántos pozos tiene Castilla?",
              "¿cuántas gerencias tiene la vicepresidencia GOR?",
              "¿cuántos campos tiene la gerencia GOR?",
              "¿cuántos activos tiene Rubiales?"]:
        grupo, _pat = clasificar_capa1(q)
        assert grupo == "jerarquizar", f"{q!r} → {grupo}"


def test_r1_no_rompe_produccion():
    # Una pregunta de producción SIGUE siendo cuantificar (no la captura el patrón de conteo).
    grupo, _ = clasificar_capa1("cuanto produjo Rubiales en mayo")
    assert grupo == "cuantificar"
    grupo, _ = clasificar_capa1("cuanto crudo acumulo Castilla")
    assert grupo == "cuantificar"


# --- GUARDAS DE REGRESIÓN (H1): "cuántos <sustantivo>" SIN verbo estructural conserva su grupo ------
# El patrón de conteo vive en precedencia_maxima (gana sobre TODO). Sin exigir el verbo, se tragaba
# estas 5 preguntas de analizar/cuantificar. Verificado en vivo 2026-08-03 — regresión permanente.
def test_r1_no_secuestra_analizar():
    for q in ["¿Cuántos campos están por debajo de la meta?",
              "¿Cuántos campos pesan más en el gap?"]:
        grupo, _ = clasificar_capa1(q)
        assert grupo == "analizar", f"{q!r} → {grupo} (el patrón de conteo lo secuestró)"


def test_r1_no_secuestra_cuantificar():
    for q in ["¿Cuántos pozos produjeron en mayo?",
              "¿Cuántos campos incumplieron el presupuesto?",
              "¿Cuántos activos están en foco?"]:
        grupo, _ = clasificar_capa1(q)
        assert grupo == "cuantificar", f"{q!r} → {grupo} (el patrón de conteo lo secuestró)"


# --- R3: _cuerpo pinta "Pozos: N" cuando hay conteo, y lo OMITE si ops no está (degradación) -------
_FAKE_DATA = {
    "campo_row": {"CASTILLA": {"campo": "CASTILLA", "operador": "ECOPETROL", "es_ecp": True,
                               "rob_field": "CASTILLA", "activo": "CASTILLA",
                               "gerencia": "PPC", "vp": "GAA"}},
    "act_campos": {"CASTILLA": ["CASTILLA"]},
    "act_fields": {"CASTILLA": {"CASTILLA"}},
}


def test_r3_cuerpo_pinta_pozos(monkeypatch):
    monkeypatch.setattr(RJ, "_contar_pozos", lambda fields: 437)
    body = RJ._cuerpo("campo", "CASTILLA", _FAKE_DATA)
    assert "Pozos: 437" in body


def test_r3_degrada_si_ops_no_esta(monkeypatch):
    monkeypatch.setattr(RJ, "_contar_pozos", lambda fields: None)   # ops caído → None
    body = RJ._cuerpo("campo", "CASTILLA", _FAKE_DATA)
    assert "Pozos" not in body            # línea OMITIDA, sin romper
    assert "«CASTILLA» · Campo" in body   # la estructura sigue intacta


def test_r3_contar_pozos_sin_fields_devuelve_None():
    # Puro: sin rob_fields (p.ej. tercero) → None sin tocar la BD.
    assert RJ._contar_pozos(set()) is None
    assert RJ._contar_pozos({None}) is None
```

---

## 5. Orden de ejecución

1. Prerequisitos + baseline (§2).
2. R1: editar `patrones_grupo.yaml` (§4.1).
3. R3: editar `respuesta_jerarquizar.py` (§4.2, en el orden R3-a…R3-e).
4. R1: añadir casos al golden (§4.3) — verificando la forma real del archivo.
5. Crear `test_conteo_jerarquia.py` (§4.4).
6. Validaciones (§6).

---

## 6. Validaciones (comando → esperado)

Desde `...\INGESTA\Rep_Prod\backend`.

**V1 — compilación:**
```
uv run python -m py_compile app/features/consulta_v2/respuesta_jerarquizar.py
```
Esperado: exit 0.

**V2 — import + carga del YAML de patrones (el caso insignia enruta a Jerarquizar):**
```
uv run python -c "from app.features.consulta_v2.patrones import clasificar_capa1; print(clasificar_capa1('¿cuántos pozos tiene Castilla?')[0])"
```
Esperado: `jerarquizar`.

**V2b — 🔑 GUARDA DE REGRESIÓN H1 (la validación más importante de este plan):**
```
uv run python -c "from app.features.consulta_v2.patrones import clasificar_capa1 as c; print([c(q)[0] for q in ['¿Cuántos campos están por debajo de la meta?','¿Cuántos campos pesan más en el gap?','¿Cuántos pozos produjeron en mayo?','¿Cuántos campos incumplieron el presupuesto?','¿Cuántos activos están en foco?']])"
```
Esperado EXACTO: `['analizar', 'analizar', 'cuantificar', 'cuantificar', 'cuantificar']`.
Si alguna dice `jerarquizar` → el patrón quedó demasiado amplio (falta el verbo estructural): **detenerse**.

**V3 — tests puros nuevos:**
```
uv run pytest tests/test_conteo_jerarquia.py -q
```
Esperado: **`7 passed`**, sin BD/LLM.

**V4 — no regresión del clasificador:**
```
uv run pytest tests/test_consulta_v2_clasificador.py -q
```
Esperado: mismo resumen del baseline de §2 (0 fallos nuevos).

**V5 — golden (los 4 casos nuevos son deterministas, Capa 1 → sin LLM):**
```
uv run python app/features/consulta_v2/golden/run_golden.py
```
Esperado: el runner reporta los 4 casos de conteo como `jerarquizar` OK y el gate global (≥90%) en
verde. ⚠️ Si el runner intenta llamar al LLM para OTROS casos y en dev no hay LLM, correr solo la
verificación determinista de los 4 casos nuevos vía V2 (repetir con las 4 frases) y anotar que el
golden completo se corre en el servidor. NO relajar el gate.

Si cualquier validación falla: **detenerse** y reportar comando + salida.

---

## 7. Fuera de alcance

- **R2 (etiquetado "la Gerencia GOR" en respuestas de PRODUCCIÓN de Cuantificar):** Plan B. Aquí NO se
  toca `cuantificar/`. R1 ya resuelve el GOR del CONTEO (lo enruta a Jerarquizar, que lo trata como VP).
- **Conteo de pozos "que produjeron" / por estado** (`conteo_pozos_produjeron`/`_activos` del catálogo):
  este plan cuenta pozos de REGISTRO (atemporal). Los otros conteos quedan como diseño no implementado.
- **Latencia cross-DB:** `_contar_pozos` corre una query a `robustez_v02` por respuesta de Jerarquizar.
  Aceptable para MVP (tabla de 13k filas, indexable). Cachear queda como mejora futura.
- **Verificación del conteo REAL** (437/766…): la hace el usuario en el servidor de pruebas (humo);
  en dev solo se valida la mecánica con monkeypatch.

---

## 8. Cierre (commit + documentación)

Commit sugerido:
```
feat(consulta_v2): conteo de jerarquia enrutado a Jerarquizar + conteo real de pozos (R1+R3)

R1: "cuantos pozos/campos/gerencias/activos tiene X" -> Jerarquizar via precedencia_maxima (antes
caia en Cuantificar y respondia produccion). R3: Jerarquizar cuenta pozos (COUNT DISTINCT uwi en
robustez_v02.ops.wells_attributes por los rob_field del nivel, cross-DB via get_ops_engine) con
degradacion si ops no esta. Join key rob_field==field verificado (Castilla 437 / activo 766).
Golden +4 casos de conteo. No toca cuantificar (R2 = plan aparte). Cierra 2.1/2.2 + gap de pozos.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
```

Tras el commit: bitácora S31 (o la que corresponda) + marcar 2.1/2.2 del
`HALLAZGO_clasificador_conteo_jerarquia.md` como resueltos (2.3 queda para Plan B).
