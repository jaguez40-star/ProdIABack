# HALLAZGO — Multiplicidad de `concepto` y falta de fuente única (día ↔ mes)

**Fecha:** 2026-07-25 · **Estado:** diagnóstico cerrado; arreglo de fondo PENDIENTE (toca ETL).
**Severidad:** alta para la curva diaria de BLANCOS; potencial (a validar) para el KPI de CRUDO/GAS.

---

## 1. Síntoma observado

En el panel «Desempeño del mes» (Consulta), para **BLANCOS** la **tarjeta KPI** y el **gráfico de
curva diaria** se contradicen en dirección:

| | Tarjeta KPI (medida mensual) | Gráfico curva diaria |
|---|---|---|
| Producción de Mayo | **619k** bbl/mes | media **66.871** bbl/día |
| Referencia 2026 | **856k** bbl/mes | **28.533** bbl/día |
| Veredicto | **72% → Por debajo** | **~134% → Por encima** |

La misma entidad, la misma comparación conceptual ("Mayo vs promedio 2026"), apunta en **direcciones
opuestas**. En CRUDO y GAS esto NO ocurre (ambos coherentes).

---

## 2. Causa raíz

La dimensión **`concepto`** del modelo ECP tiene 4–5 valores que son **atribuciones del mismo
volumen físico**, no volúmenes que se sumen entre sí:

- `DERECO` (derechos económicos), `MONETIZACION`, `PROPIEDAD`, `REGALIADISP` (regalías dispuestas),
  y en crudo además `CAMPOS_REG_ESP`.

Ni la **curva diaria** (`SUM(d.volumen)` sobre `core.fact_produccion_dia_ecp`) ni el **KPI mensual**
(`SUM(m.volumen)` sobre `core.fact_produccion_mes_ecp`) filtran por `concepto`: **suman todos**. El
problema es que esa suma **significa cosas distintas según el producto y según el fact**.

### 2.1 Evidencia — DIARIO, mayo 2026, por producto × concepto

```
BLANCOS :  DERECO=284.204  MONETIZACION=284.204  PROPIEDAD=284.204  REGALIADISP=284.204   (4 COPIAS idénticas → ×4)
GAS     :  DERECO=9.965.094  MONETIZACION=9.965.094  PROPIEDAD=9.965.094  REGALIADISP=9.965.094  (4 COPIAS → ×4)
CRUDO   :  REGALIADISP=DERECO=PROPIEDAD=12.122.638  +  CAMPOS_REG_ESP=6.335.167  +  MONETIZACION=5.787.471  (mixto)
```

### 2.2 Evidencia — MENSUAL REAL, mayo 2026, por producto × concepto

```
BLANCOS :  DERECO=208.825  MONETIZACION=163.892  REGALIADISP=127.236  PROPIEDAD=118.962   (DISTINTOS → suman 618.914)
GAS     :  DERECO=MONETIZACION=PROPIEDAD=REGALIADISP=18.064.848                            (COPIAS → ×4 = 72.259.391)
CRUDO   :  REGALIADISP=DERECO=PROPIEDAD=22.214.321  +  CAMPOS_REG_ESP=11.656.288  +  MONETIZACION=10.558.033
```

### 2.3 La asimetría que rompe BLANCOS

| Producto | concepto en MENSUAL | concepto en DIARIO | ¿Diario reconcilia con mensual? |
|---|---|---|---|
| CRUDO | copias (×4) + extras | mixto | ✅ (ambos inflan igual) |
| GAS | **copias idénticas (×4)** | **copias idénticas (×4)** | ✅ (ambos inflan igual) |
| **BLANCOS** | **distintos → particiones que SUMAN** | **copias idénticas (×4)** | ❌ (mensual ×1, diario ×4) |

- CRUDO/GAS: el diario y el mensual inflan **igual** → reconcilian (curva ~11% por debajo, coherente).
- BLANCOS: mensual = suma de 4 particiones distintas = **618.914** (= tarjeta KPI, correcto). Diario =
  4 **copias** de 284.204 = **1.136.815 = ×4**. De ahí el "134% por encima" falso.
- Prueba: BLANCOS diario 1 concepto = **284.204**; ×4 = **1.136.815** (factor exacto 4,0). El volumen
  físico de blancos ronda 284.204 (16.718 bbl/día), no 66.871.

---

## 3. Ancla validada por el usuario (importante)

**Rubiales · CRUDO · mayo · REAL** — número validado por el usuario contra su Excel = **12.357.703**:

```
DERECO=3.089.426  MONETIZACION=3.089.426  PROPIEDAD=3.089.426  REGALIADISP=3.089.426
SUM(todos) = 12.357.703   ✅  (= 4 × 3.089.426)
```

⇒ Para el **mensual**, sumar los conceptos **da el número oficial** (coincide con el Excel). Es decir,
el KPI mensual (fuente de verdad del tablero) **está bien tal como lo usamos** para los 3 productos.

⚠️ **Hallazgo colateral a validar con negocio (NO tocado):** que el volumen "oficial" de crudo/gas sea
la **suma de 4 conceptos idénticos** (= 4× un solo concepto) conviene confirmarlo con quien genera el
reporte. Si el Excel efectivamente reporta así, es correcto (y así se asume, porque el usuario validó
esas cifras). Pero si fuese un artefacto de ingesta, afectaría todo el tablero, no solo Blancos.

---

## 4. Conclusión preliminar (revisada por la auditoría del Paso 2 — ver §4bis)

- La dimensión `concepto` mezcla **dos semánticas** (copias vs particiones). En BLANCOS-diario son
  copias (×4); en BLANCOS-mensual son particiones.
- Pero la auditoría del Paso 2 demuestra que **el `concepto` NO es la causa de fondo de Blancos**:
  ni siquiera filtrando el mismo concepto reconcilian diario y mensual (ver §4bis).

---

## 4bis. AUDITORÍA PASO 2 (2026-07-25) — ETL + reconciliación diario↔mensual

### El ETL no duplica; la multiplicidad viene de la fuente
`load_fact_dia` / `load_fact_mes` (`ingesta/services.py`) insertan la hoja RAW **fila por fila**, sin
replicar. Las claves `uk_dia` y `uk_mes` **ambas incluyen `concepto_id`** → preservan las 4 filas por
concepto (no colisionan). Al grano fino (fuente+producto+socio): BLANCOS-diario = `4 conceptos, 1 solo
volumen` (copias exactas); BLANCOS-mensual = `4 conceptos, 2-3 volúmenes` (particiones). Es un artefacto
**de las hojas fuente** (`BDP_datos_dia` replica el volumen en los 4 conceptos), no del ETL.

### Reconciliación diario↔mensual en ABRIL 2026 (mes cerrado)

| producto | DIA÷MES (sumando todo) | DIA÷MES (solo `PROPIEDAD`) |
|---|---|---|
| CRUDO | **0,99** ✅ | **0,99** ✅ |
| GAS | **1,01** ✅ | **1,01** ✅ |
| **BLANCOS** | **2,10** ❌ | **3,06** ❌ |

⇒ CRUDO/GAS reconcilian con **cualquier** criterio (fuente coherente). BLANCOS **no reconcilia bajo
ningún criterio de concepto** → el problema **no es** `concepto`.

### Causa de fondo de BLANCOS: dos modelos de producto distintos entre las hojas
Desglosando BLANCOS·abril·`PROPIEDAD` por corriente:

- **DIARIO** = suma de **corrientes físicas** de líquidos: GLP 311.269 + CONDENSADO 92.373 +
  GASOLINA 24.790 + PROPANO 20.364 + NAP 14.845 + BUTANO 11.435 + PENTANO 3.124 + APIASOL 3.001
  = **481.201**. La columna `producto` va poblada por corriente.
- **MENSUAL** = un **único agregado** bajo el proceso **"GAS CONVERTIDO MME"** = **157.265**, con la
  columna `producto` **vacía**.

Son **dos vistas de negocio distintas del mismo "BLANCOS"**: el diario lo mide por corriente física de
líquido; el mensual lo mide como "gas convertido". No son el mismo universo → **irreconciliables con los
datos actuales** (3,06×). Para CRUDO/GAS ambas hojas usan el mismo modelo → reconcilian.

### Conclusión del Paso 2
- **CRUDO / GAS:** ya tienen fuente coherente (diario ≈ mensual). **Nada que arreglar.**
- **BLANCOS:** el fact diario y el mensual son **fuentes distintas con semántica de producto distinta**.
  **No hay arreglo técnico** (ni por concepto ni por corriente) sin una **decisión de negocio**: definir
  qué es "la producción de blancos" (¿la suma de corrientes del diario, o el "GAS CONVERTIDO MME" del
  mensual, que es lo que hoy alimenta el KPI validado?). Requiere validación con quien genera el reporte.
- El **Paso 1 ya aplicado** (la curva diaria de BLANCOS no se compara vs el promedio 2026, solo muestra
  forma/tendencia) es la respuesta correcta mientras esa decisión de negocio no exista.

### Colateral (crudo/gas): sumar 4 conceptos idénticos = ×4
Sigue en pie el punto de §3: el KPI de crudo/gas suma 4 conceptos-copia (Rubiales 12.357.703 = 4×
3.089.426). Como diario y mensual lo hacen IGUAL, reconcilian y el usuario lo validó contra su Excel.
Se asume correcto, pero conviene confirmarlo con negocio en la misma conversación.

---

## 5. Camino

1. **Paso 1 — presentación (inmediato, HECHO en commit aparte):** que BLANCOS **no compare** su curva
   diaria contra el promedio 2026 (revertir la referencia forzada). Blancos vuelve a compararse contra
   el promedio de su propio mes; su título deja de decir "vs promedio diario 2026". Quita la
   contradicción visible sin tocar datos. CRUDO/GAS quedan igual.
2. **Paso 2 — auditoría (HECHA, ver §4bis):** el ETL no duplica y las claves incluyen `concepto`. Se
   descartó que `concepto` sea la causa de fondo de BLANCOS (no reconcilia ni filtrando el mismo
   concepto). La causa es que el fact diario y el mensual **modelan BLANCOS distinto** (corrientes de
   líquido vs "GAS CONVERTIDO MME"). **No hay arreglo técnico sin decisión de negocio.** CRUDO/GAS OK.
3. **Paso 3 — decisión de negocio (PENDIENTE, requiere al usuario / a quien genera el reporte):**
   definir "la producción de blancos" (suma de corrientes del diario vs "GAS CONVERTIDO MME" del
   mensual) y confirmar el colateral crudo/gas (¿el volumen oficial es la suma de 4 conceptos idénticos,
   o un solo concepto?). Solo con esa definición se puede construir una fuente única real; entre tanto,
   el Paso 1 mantiene la coherencia visual sin inventar datos.

---

## 6. Cómo reproducir el diagnóstico (read-only)

```python
# desde INGESTA/Rep_Prod/backend, con el backend apagado o en paralelo:
from app.core.db import get_engine; import sqlalchemy as sa
eng = get_engine()
with eng.connect() as c:
    # DIARIO por producto × concepto (mayo 2026)
    c.execute(sa.text("""
      SELECT tp.nombre, cc.nombre, SUM(d.volumen)
      FROM core.fact_produccion_dia_ecp d
      JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id=d.tipo_producto_id
      LEFT JOIN core.dim_concepto cc ON cc.concepto_id=d.concepto_id
      WHERE d.fecha BETWEEN '2026-05-01' AND '2026-05-31' GROUP BY 1,2 ORDER BY 1,3 DESC"""))
    # MENSUAL REAL por producto × concepto: cambiar a fact_produccion_mes_ecp + JOIN dim_escenario (REAL)
```
