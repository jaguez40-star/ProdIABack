# Auditoría de viabilidad — Motor de Cuantificación (Motor Q v2, Etapa B)

> **Fecha:** 2026-08-02 · **Método:** cada celda verificada contra la BD dev en vivo
> (`daily_report_prod` local + `ECP_DIFERIDAS.db`), **no de memoria**. Sin cambios de código.
> **Propósito:** antes de construir la rama *Cuantificar*, decidir qué `variable × modo` responde
> HOY y **con qué nivel de confianza / con qué referencia** — porque la matriz "14 × 4" no está
> por explorar: varias celdas ya están muertas y demostrablemente mienten.

---

## ★ DECISIÓN DE FUENTE POR DEFECTO (2026-08-02, usuario) — gobierna todo el catálogo

Existen **DOS mundos de producción que no reconcilian (~6,5×)**. Regla de enrutamiento fija:

```
DEFAULT = REPORTE DIARIO (INGESTA · daily_report_prod)
          → toda cifra de producción crudo/gas/blancos.
          Es la más completa: incluye terceros, tiene gas+blancos, grano día+mes,
          referencias REAL/PPTO/P50, y es LA CIFRA OFICIAL que ve el gerente.

BAJAR a ROBUSTEZ (robustez_v02.ops) SOLO si la pregunta pide:
          → pozo (cuántos/producción por pozo) · economía (EBITDA/breakeven/revenue) · agua

NUNCA mezclar los dos en una misma respuesta (no reconcilian) →
          robustez entra como vía EXPLÍCITA y ROTULADA ("universo robustez, ECP-neto"),
          jamás sumando números de los dos mundos en la misma frase.
```

Por qué INGESTA es el más completo (verificado): cobertura +⅓ (terceros), productos (gas+blancos, que
robustez no tiene), grano día, referencias PPTO/P50, y autoridad (cifra reportada). Robustez es el
especialista para lo que INGESTA estructuralmente no puede: pozo, plata, agua.

---

## ★ DECISIÓN DE REFERENCIA/META POR DEFECTO (2026-08-02, usuario)

"La meta" NO es un número — hay hasta 5 referencias de plan y **no coinciden** (crudo abril: REAL 85,4M ·
PPTO 89,2M · OPERATIVO 90,3M · PROGRAMA versionado · P50 corporativo). Es el eje que causó el bug
55,2% vs 100,1%. Regla fija:

```
DEFAULT meta = PPTO (fact_mes, escenario PPTO)   → toda comparación cumplimiento/gap por defecto
Explícitas y ROTULADAS:
   OPERATIVO  = presupuesto revisado (~PPTO +1%, fact_mes)
   CONTABLE   = cierre contable (SOLO meses cerrados, fact_mes)
   P50/Compromiso = corporativo kbpe (REPORTE_PRESIDENT, no reconcilia ~5,8×)
   promedio-año = derivada (referencia de blancos)
PROGRAMA (fact_programa_ecp) = NO usar aún → está VERSIONADO (V1..V19; sumar sin filtrar versión
   infla 8×) + distinguir volumen/produccion_total/part_ecp. Requiere regla de versión antes de exponerse.
```

Suelo honesto de "cumplimiento": trío **REAL / PPTO / OPERATIVO** (misma escala, fact_mes). Toda respuesta
declara la referencia usada.

---

## 0. Definición de los niveles de confianza

| Nivel | Significado | Regla |
|-------|-------------|-------|
| 🟢 **ALTA** | Computado, reconciliado y verificado contra la BD | responder el número directo |
| 🟡 **MEDIA** | Computable pero con un caveat que hay que **decir en la respuesta** (proyección≠acumulado, fuente única sin cruce, unidad sin confirmar, campos sin meta) | responder + descargo |
| 🔴 **NO / SIN_DATOS** | La fuente no existe o no reconcilia | **no prometer** — rechazar o declarar el hueco |

Principio rector (audit_motor_clas): *"anotación sin veredicto = ruido"*. Aquí: **respuesta sin
referencia declarada = mentira potencial** — el mismo 96,8% es "Alineado" o "Ajustado" según el umbral,
y el mismo producto da 55,2% vs 100,1% según la referencia (P50 vs promedio-2026).

---

## 1. Los dos ejes (aterrizados del código y la BD, no inventados)

### Eje 1 — VARIABLES (qué cantidad se pide)
Universo REAL de productos = **solo 3**: `dim_tipo_producto` = {CRUDO, GAS, BLANCOS}. **`agua` no es un
producto** (no existe fila). Lo demás que el clasificador reconoce como vocabulario
(`vocabulario_dominio.yaml`: DIFERIDAS, MANTENIMIENTOS, EBITDA, NOPAT, WORKOVER, NV04) **no tiene
cómputo** en `analisis/` ni `consulta/` — son *declaradas-pero-no-implementadas*.

### Eje 2 — MODOS (referencia × escenario × grano)
Hallazgo estructural de primer orden, verificado en el esquema:

- **`fact_produccion_dia_ecp` NO tiene `escenario_id` ni `proceso_id`** — solo `volumen/vol_estimado/promedio` + `producto`. **El grano DÍA es REAL puro**: no hay PPTO/P50 a día. La "ejecución diaria vs PPTO" del panel prorratea el PPTO mensual.
- **`fact_produccion_mes_ecp` sí** tiene `escenario_id` {CONTABLE, PPTO, OPERATIVO, REAL} y `proceso_id` {PROD_TOTAL, VENTA-GRAVABLE, CONSUMO, **GAS CONVERTIDO MME**}. Solo se consultan REAL y PPTO.
- **P50 / Compromiso NO viven en el star schema** — viven en `fact_tabla_hoja` (hoja `REPORTE_PRESIDENT`), en **kbpe corporativo**, y **no reconcilian** con el fact (crudo ×5,8 · gas ×36 · blancos ×2). Son sistemas de unidades distintos.
- **Periodo:** v1 solo soporta **MES** (`_parse_periodo`); año/trimestre/semana no.
- **Nivel de entidad:** hasta Campo/Activo (vía `map_campo_activo`). **`pozo` es alias de `fuente`; el grano de pozo NO existe** (deuda declarada).

---

## 2. La matriz de veredictos  (VARIABLE × MODO)

Columnas = modos. `REAL/mes` · `PPTO/mes` · `P50-Compromiso` · `promedio-año (vs 2026)` · `curva día (REAL)` · `pozo` · `año/trim/sem`.

| Variable | REAL/mes | PPTO/mes | P50-Comp. | prom-año | curva/día | pozo | año/trim |
|----------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| **CRUDO** producción | 🟢 | 🟢 | 🟡¹ | 🟢 | 🟢² | 🔴 | 🔴 |
| **GAS** producción | 🟡³ | 🟢 | 🟡¹ | 🟢 | 🟡³ | 🔴 | 🔴 |
| **BLANCOS** producción | 🟡⁴ | 🟢 | 🟡⁵ | 🟡⁶ | 🔴⁷ | 🔴 | 🔴 |
| **Agua** | 🔴⁸ | 🔴⁸ | 🔴 | 🔴 | 🔴⁸ | 🔴 | 🔴 |
| **Diferidas** (perdido crudo/gas) | 🟡⁹ | — | — | — | — | — | 🔴¹⁰ |
| **Diferidas blancos** | 🔴¹¹ | — | — | — | — | — | 🔴 |
| **EBITDA / NOPAT / plata** | 🔴¹² | 🔴 | 🔴 | 🔴 | 🔴 | 🔴 | 🔴 |
| **Mantenimientos / workover** | 🔴¹³ | 🔴 | 🔴 | 🔴 | 🔴 | 🔴 | 🔴 |
| **P50 / Compromiso** (como cifra) | 🟡¹ | — | 🟢¹⁴ | — | — | 🔴 | 🔴 |

### Notas (cada una respaldada por dato o por comentario en código)

1. **P50 es ECP-global y en kbpe**, no reconcilia con el fact (×5,8/×36/×2). Se puede dar el % de cumplimiento vs P50 (`REPORTE_PRESIDENT`) pero **no** mezclado con los bbl del tablero, y **no** por campo. → MEDIA: responder con la etiqueta "kbpe corporativo".
2. **CRUDO día↔mes reconcilia:** abril 85.417.841 (mes) vs 84.981.276 (día) = **0,99**. MTD/bopd-avg solo se calculan para crudo.
3. **GAS reconcilia en total** (abril 66.663.907 vs 67.366.690 = 1,01) **pero**: (a) los 4 conceptos son copias idénticas (16.841.673 ×4) → el "volumen" es un ×4 consistente, no el físico; (b) REAL sale de proceso `VENTA-GRAVABLE`/`CONSUMO` (¿cuál es "producción"?); (c) **unidad MSCF sin confirmar** (KPC/KPCD). GAS está excluido de MTD/bopd por esto. → MEDIA.
4. **BLANCOS/mes = proceso `GAS CONVERTIDO MME`** (agregado convertido, único proceso de blancos REAL). Es el número que usa el tablero, pero está desconectado del físico. → MEDIA.
5. **BLANCOS P50 solo existe en `REPORTE_PRESIDENT`** (única fuente con blancos, 14,4 kbpe). Fuente única, kbpe. → MEDIA.
6. **BLANCOS promedio-año:** el `promedio_dia` se **excluye** para blancos (no reconcilia); a grano mes es computable pero con la discrepancia documentada (856k tarjeta vs 828k cálculo, ~3%). → MEDIA.
7. **BLANCOS día ✗ NO reconcilia:** abril mes 916.592 vs día 1.924.803 = **2,10**. Día = 4 copias físicas (481.201 ×4); mes = MME ×2. Irreconciliable con el esquema actual → **NO** dar curva diaria de blancos vs referencia. (Ver `HALLAZGO_concepto_multiplicidad.md`.)
8. **Agua:** **NO existe en `daily_report_prod`** — cero filas. (El `ILIKE '%agua%'` que antes dio "19.440" era **falso positivo**: matcheaba nombres de campo — Cupi**agua**, Pal**agua**, **Agua**s Blancas, Y**agua**ra, La J**agua**. Ninguna fila es agua producida; `producto ~* '^agua'` = 0.) La lógica de negocio es correcta (el agua se produce, se mide en **bbl**), pero **el dato no está en esta base**. Sí existe en **`ROBUSTEZ.db`** (`Producción Agua Dia_Mes` ~9,6M/2026, `Tasa Producción Agua` bpd), grano UWI, 2025-2026. → 🔴 en la BD de producción; 🟡 solo si se conecta ROBUSTEZ (misma decisión cross-DB que EBITDA).
9. **Diferidas crudo/gas:** `ACEITE_PERDIDO`/`GAS_PERDIDO` en `ECP_DIFERIDAS.db`, histórico verificado **2023-01-01 → 2025-07-30**. Útil como marco causal-histórico (Pareto por causa NV04). → MEDIA (histórico).
10. **NO enlaza con el mes en curso:** la BD termina jul-2025; no solapa 2026. El puente causa↔desviación del mes solo sería posible por comentarios (~33% cobertura). En **139 = SIN_DATOS** (la BD de 954 MB no está subida).
11. **Diferidas blancos:** **no existe columna** de blancos perdido (`AVM_DATADIF` tiene ACEITE/GAS/AGUA_PERDIDO, no blancos). → NO se puede atribuir causa a blancos por volumen.
12. **Plata:** no existe en `daily_report_prod`, **pero SÍ en `ROBUSTEZ.db`** (`RESULTADOSREGRESION`: `EBITDA (Activo) KUSD`, Breakeven, Costos, Transporte, Dilución), grano UWI/campo, años 2025-2026, **solo aceite**. → 🟡 (existe) con dos caveats duros: (a) es **otra base** (SQLite del Flask, el motor v2/FastAPI no la conecta hoy) y (b) es **otro universo** (economía por pozo, no reconciliado con el fact de producción). No es NOPAT directo (hay EBITDA, no NOPAT).
13. **Mantenimientos/workover:** vocabulario reconocido, **sin fuente de datos** (la pill del panel es mock). → NO.
14. **P50/Compromiso como cifra propia:** 🟢 desde `REPORTE_PRESIDENT` para Crudo/Gas/Blancos + Ecopetrol/Filiales/Upstream, en kbpe. Es la única celda P50 en verde, pero **solo a nivel corporativo** (no drill-down a campo).

> **Rama B (Filiales)** tiene su propia semántica: no hay PPTO → la referencia es **REAL vs PROGRAMA**
> y proyección vs su promedio-2026. Es 🟢 en ese marco, pero **no comparte referencia con ECP** — no
> mezclar.

---

## 3. Lo que la matriz dice para el orden de construcción

**Cuantificar NO es "14 variables"** — es esencialmente **3 productos** con un mapa de confianza muy
desigual:

- **El núcleo 🟢 real y honesto:** CRUDO {REAL, PPTO, promedio-año, día} + GAS {PPTO} + los tres {PPTO/mes} + la tarjeta P50 corporativa. Eso es lo que un motor puede prometer sin descargo.
- **La franja 🟡** (GAS/BLANCOS en varias combinaciones) **exige que la respuesta declare la referencia y la unidad**. Sin eso, el motor reproduce automáticamente el bug del saludo (55,2% vs 100,1%).
- **La zona 🔴** (agua, blancos-día, plata, mantenimientos, diferidas-del-mes) hay que **cablearla como rechazo explícito del clasificador**, no descubrirla en runtime. Varias ya están en el vocabulario del clasificador → el clasificador *entiende* la pregunta pero el motor *no puede responderla*: ese gap debe ser una respuesta honesta ("reconozco la pregunta pero no tengo la fuente"), no un número inventado.

**Analizar (rama causal): 🔴 estructural, confirmado en la BD.** `uk_mes` =
`fecha,fuente_id,concepto_id,socio_id,tipo_producto_id,producto,escenario_id,proceso_id` — **sin
`reporte_id`** (y `uk_dia` tampoco). Cada reporte diario sobrescribe la fila del mes → **no existe el
histórico "cómo se veía mayo hace 7 días"** y el anterior **ya se perdió**. El delta causal por campo
solo será posible tras: añadir `reporte_id` a `uk_mes` + re-ingerir, **y solo da historia hacia
adelante**. Confirma poner Analizar de último y como *trabajo de datos*, no de UI.

---

## 4. Precondición pendiente (no bloquea esta auditoría, sí la construcción)

Decidir la política de **Anillo 2**: Cuantificar ya existe a medias en v1 (`consulta/ejecucion.py`
responde REAL vs PPTO del mes). Ponerlo como "buque insignia" de v2 obliga a decidir **ya** si v2
forkea las calculadoras del tablero (`analisis.desempeno`) o las comparte. Clasificar no lee datos;
Cuantificar sí — por eso la decisión se difería "hasta construir el primer grupo", y ese momento es
este.

---

## 5. Evidencia cruda (para reproducir)

- Reconciliación abril-2026 (mes cerrado), `sum(volumen)`:
  - CRUDO: mes 85.417.841 · día 84.981.276 · **0,99 ✓**
  - GAS: mes 66.663.907 · día 67.366.690 · **1,01 ✓** (4 conceptos idénticos ×16.841.673)
  - BLANCOS: mes 916.592 · día 1.924.803 · **2,10 ✗** (día 4×481.201 físico vs mes MME ×2)
- Cobertura: `fact_dia` 2025-11-25→**2026-05-17** · `fact_mes` 2024-12-31→2026-12-31 (PPTO forward).
- `ECP_DIFERIDAS.AVM_DATADIF`: EVENT_DATE 2023-01-01→2025-07-30; columnas de pérdida = ACEITE_PERDIDO / GAS_PERDIDO / AGUA_PERDIDO (**sin blancos**).
- Conceptos en BD (5, no 3): REGALIADISP, DERECO, PROPIEDAD, MONETIZACION, CAMPOS_REG_ESP.
- `fact_dia.producto` = corrientes físicas (GLP/CONDENSADO/GASOLINA/MEZCLA…); agua ILIKE = 19.440 filas.
- `fact_programa_ecp` = 217.962 filas, hasta 2026-06-30. `dim_fuente` = 253 fuentes / 139 campos, **sin columna pozo**.
- `ROBUSTEZ.db.RESULTADOSREGRESION` = EBITDA/Breakeven/Costos KUSD, grano UWI+CAMPO+GERENCIA, años 2025-2026.

---

## 6. Validación cruzada contra el plan (motor_Q.md §4.3 — catálogo `variables_cuantificables.yaml`)

Contraste celda por celda del catálogo del plan contra la evidencia de la BD.

| Variable del plan | Fuente que declara | Veredicto vs auditoría |
|---|---|---|
| `produccion_crudo` | fact_diario | 🟢 **CONFIRMA** (día↔mes 0,99) |
| `produccion_gas` | fact_diario | 🟡 **MATIZA** — reconcilia pero unidad MSCF sin confirmar (el plan ya lo marca R3) + 4 conceptos ×4 + proceso REAL ambiguo (VENTA-GRAVABLE vs CONSUMO) |
| `produccion_blancos` | fact_diario | 🔴 **CONTRADICE parcial** — el plan lo trata plano; en realidad **depende del grano**: 🟡 a N2/mes, **🔴 a N1/N3/N4 diario** (ratio 2,10). Sumar `fact_diario` de blancos da el número ×2 equivocado |
| `produccion_agua` | fact_diario / agua | 🟡 **AMBOS a medias** — no es `dim_tipo_producto` (mi 🔴) pero el dato existe (19.440 filas, corrige mi 🔴). Veto de código pendiente de explicar |
| `produccion_kbpe`, `base_p50`, `compromiso` | reporte_president | 🟡 **CONFIRMA** — kbpe, solo corporativo, no reconcilia con el fact (×5,8/×36/×2) |
| `programa` | bdp_programa | 🟢 **CONFIRMA** — `fact_programa_ecp` 217.962 filas hasta 2026-06-30 |
| `gap`, `cumplimiento` | derivada real−programa | 🟢 **CONFIRMA** — a grano mes (`_gap_campo`) |
| `volumen_diferidas`, `dias_paro`, `conteo_incidentes` | diferidas | 🟡 **MATIZA** — histórico 2023→jul-2025 (no toca 2026), crudo/gas/agua **sin blancos**, y **otra base** (SQLite) |
| `conteo_pozos` | dimension | 🔴 **CONTRADICE** — no hay grano pozo en `daily_report_prod` (`dim_fuente` es fuente/campo). Pozo real vive en ROBUSTEZ/Diferidas (otras bases) |
| `conteo_campos` | dimension | 🟢 **CONFIRMA** (139 campos) |
| `ingresos`, `ebitda`, `nopat` | robustez | 🟡 **EL PLAN CORRIGE MI AUDITORÍA** — existe en `ROBUSTEZ.db` (hay EBITDA, **no NOPAT**), solo aceite; pero **otra base** + **otro universo** no reconciliado |

### Tres puntos ciegos del catálogo del plan (no son errores de detalle, son estructurales)

**A · El catálogo es 1-D (variable→fuente); la viabilidad es 2-D (variable×grano).**
BLANCOS es el caso testigo: `produccion_blancos: fact_diario` es correcto para acumular al mes
pero **falso a grano diario**. El catálogo debe llevar el grano válido por variable, o el motor
sumará corrientes físicas diarias y devolverá el número ×2. Mi matriz §2 es justo esa 2ª dimensión.

**B · El catálogo abarca 4 bases físicas; el motor v2 (FastAPI) hoy conecta a UNA.**
- Postgres `daily_report_prod` → fact_diario, reporte_president, bdp_programa ✓ (v2 llega)
- `ECP_DIFERIDAS.db` (SQLite) → volumen_diferidas, dias_paro, conteo_incidentes ✗
- `ROBUSTEZ.db` (SQLite) → ingresos, ebitda, nopat ✗

**6 de las 18 variables viven en SQLite que el motor v2 no conecta.** El plan no lo menciona.
Traerlas exige conexión cross-DB desde FastAPI o un proxy por Flask (como ya hace
`/api/diferidas/frecuencia`). Es una decisión de arquitectura previa, no un detalle de implementación.

**C · Son dos universos que no reconcilian.**
"Cuánto produjo Rubiales" (bbl, daily_report_prod, 2026) y "EBITDA de Rubiales" (KUSD, ROBUSTEZ,
regresión 2025-2026 por pozo) son marcos distintos. Un mismo motor Cuantificar que responda ambos
debe **rotular la base y el universo** en cada respuesta, o mezclará plata con barriles.

### Dónde el plan y la auditoría coinciden fuerte
- **Cero traicionero (`SIN_REPORTE ≠ 0`)** del plan §4.5 = mi hallazgo `absent→0`. Refinamiento: la señal difiere por grano (mensual → fila ausente; diario → 0 explícito).
- **Huella primero** (§4.6) y **techo 2026-05-17** (R4) = verificados idénticos.
- **Default producto por volumen dominante** (§4.4, riesgo Hocol) = correcto y necesario.

---

## 7. ¿Se puede cuantificar la JERARQUÍA? (tras S28 — `map_campo_robustez` + `wells_attributes`)

**Veredicto: SÍ, el ajuste lo habilita** — el grano de pozo (que `daily_report_prod` NO tenía) ahora
existe en `robustez_v02.ops.wells_attributes` (**13.482 pozos**), y las consultas de conteo por nivel
corren. Verificado:

- Estructura total (wells_attributes): **20 VP · 37 gerencias(management) · 53 activos · 118 campos(field) · 13.482 pozos**.
- `COUNT(DISTINCT uwi)` por nivel funciona: p.ej. VP `GOR` = 2.537 pozos / 2 gerencias / 2 activos / 4 campos; gerencia `PPC` = 767 pozos.
- Conteos de estructura (cuántas gerencias/activos/campos por VP) salen directo de `core.map_campo_robustez` (en `daily_report_prod`, **sin cross-DB**) para el universo ECP; `cuántos pozos` requiere el salto a `robustez_v02` (cross-DB).

### Cuatro caveats que hay que cablear (o el conteo miente)

**J-1 · Ceiling 58% de campos = ~⅓ de la PRODUCCIÓN (no es nota al pie).** `map_campo_robustez` = 81 ECP
+ 58 terceros. Materialidad medida (abril 2026 REAL): terceros = **32,5% del crudo · 34,9% del gas ·
21,6% de blancos**. Operadores: SierraCol (20 campos), Cepcolsa (9), Gran Tierra (6), Parex, Frontera,
Emerald, Hocol… (11 en total). **Doble naturaleza verificada:** los terceros **NO tienen jerarquía
robustez** (rob_* NULL — robustez solo modela ECP-operado) **pero SÍ tienen la taxonomía vieja de INGESTA**
(`dim_fuente.gerencia` GNS/GAN + `activos = 'NO OPERADOS'`). → La duda es un **fork de decisión**: para
preguntas de estructura que tocan terceros, (A) robustez-only → se omite ⅓ de la producción; (B) fallback
a `dim_fuente` → cobertura total pero dos taxonomías cosidas. Semántica: un campo de Parex **no está bajo
una gerencia ECP** (es `NO OPERADOS`), así que "cuántas gerencias tiene la VP X" (operativa) los excluye
legítimamente, pero "cuántos campos/pozos hay / cuánto produjeron" (portafolio) **debe** incluirlos o
miente por un tercio.
> **✅ DECISIÓN DEL USUARIO (2026-08-02): EXCLUIR terceros.** Los conteos de jerarquía son **estructura
> operativa ECP** — solo `es_ecp=true` (81 campos). Toda respuesta de conteo **declara** el recorte
> ("N; no incluye campos operados por terceros"). **Consecuencia asumida:** una pregunta de *portafolio
> total* ("cuántos campos hay en total") responderá el número ECP, no el total con participaciones — por
> eso el aviso de recorte es obligatorio, no opcional.

**J-2 · El grano de `wells_attributes` es uwi×zona, no uwi** (40.157 filas / 13.482 pozos ≈ 3 zonas por
pozo). `COUNT(DISTINCT uwi)` es correcto para "cuántos pozos", **pero `well_status` es por zona**: contar
distinct-uwi por estado suma 18.052 > 13.482 (un pozo puede estar ACT en una zona y ABA en otra — **3.671
pozos, 27%, son mixtos**).
> **✅ DECISIÓN DEL USUARIO (2026-08-02): reportar la COMPOSICIÓN por estado, no un solo "activos".**
> Tratamiento: **partición** = a cada pozo se le asigna UN estado por prioridad "el más vivo"
> (**ACT > SUS > INACT > ABA**) → suma exacta al total. Resultado verificado:
> **ACT 6.989 · SUS 735 · INACT 986 · ABA 4.772 = 13.482.** "Pozos activos" = 6.989 (alguna zona ACT).
> Nota: es estado de REGISTRO (ver J-4), no "produjo en el mes".

**J-3 · "Colisión" de RUBIALES = SINONIMIA (no colisión). RESUELTA.** El usuario lo declaró y el dato lo
confirma: `GOR/POE` y `VAO/ORIENTE` son **sinónimos** — las dos rutas de RUBIALES comparten **1.457 de
1.459 pozos** (los mismos pozos, doble etiqueta). Conteo correcto = unión = **2.131** (el `DISTINCT uwi`
ya lo dedup­lica). **No era Rubiales solo:** **112 de 118 campos** aparecen bajo >1 par VP/gerencia → las
columnas `vice_presidency`/`management` de `wells_attributes` **están aliaseadas**, no particionan. La
"colisión" fue un artefacto de agrupar por VP+gerencia+campo a la vez.
> **✅ TRATAMIENTO (2026-08-02):** (1) **Siempre `COUNT(DISTINCT uwi)`** al nivel pedido — nunca SUM de
> subconteos (🔑 **747 uwi pertenecen a >1 campo**, sumar por campo duplica). (2) La **jerarquía canónica**
> (qué VP/gerencia/activo tiene un campo) se toma de **`map_campo_robustez`** (1 asignación por campo), NO
> de las columnas aliaseadas de wells. Validado: VP GOR naive 2.537 ≈ canónico 2.536. ⚠️ Corrige un dato
> previo de esta auditoría: los "pozos por VP" crudos NO particionan los 13.482 (un pozo puede llevar 2
> etiquetas de VP); usar el mapa canónico + distinct uwi.

**J-4 · "Pozos" es un conteo de REGISTRO, no de producción.** `wells_attributes` es un **catálogo
estático** de pozos (sin fecha; con estado). El fact de producción es 2026 y **no tiene grano de pozo**.
→ "cuántos pozos tiene Rubiales" (registro: 2.131) **≠** "cuántos pozos produjeron en mayo" (imposible con
el fact). Son **dos universos**: estructura (robustez, atemporal) vs producción (INGESTA, 2026). No
mezclar el conteo de pozos con el volumen producido como si fueran el mismo periodo.
> **Verificado (2026-08-02):** el REPORTE DIARIO (BDP→fact) no tiene grano pozo — `bronze.bdp_datos_dia/_mes/_programa`
> llegan a `fuente`/`idbdp` (dia idbdp 213/fuente 163 = campos) + `producto`. **PERO** ↓
> **🔧 CORRECCIÓN (2026-08-02): la producción por pozo SÍ existe — en `robustez_v02.ops.flow_rates`.**
> Grano uwi×año×mes×zona (310.104 filas, 13.482 pozos, **2025-01→2026-06**): `production_oil_day_month`,
> `production_water_day_month`, `total_bbl_blend`, `production_days` + `ops.financial_results` (EBITDA/
> breakeven/revenue por pozo/mes). → **"cuántos pozos produjeron crudo en abril 2026" = 5.779** (`oil_day_month>0`);
> **agua por pozo también** (5.784 pozos, 9,7M). ⚠️ **3 caveats duros:** (a) **NO reconcilia con el reporte
> diario** — crudo abril fact 85,4M vs flow_rates blend 13,2M (~6,5×) / oil_day 0,46M (~186×): es el
> universo robustez (ECP-operado, prob. participación-neta, mensual), el mismo desfase de escala que el
> mundo P50; (b) **sin gas** (solo oil/water/blend); (c) ECP-only (58% ceiling, J-1). → Fila 5 pasa de 🔴 a
> **🟡: answerable en el universo robustez, NO en el del reporte diario.** No se pueden sumar los pozos de
> flow_rates y decir que dan el volumen del campo del reporte — son dos accountings.

**J-5 · Level-shift de vocabulario. RESUELTA (opción A · educar suave).** Lo que INGESTA/el reporte llama
"gerencia" (GOR, GAA, GLH…) es en robustez la **vicepresidencia**; la gerencia real es `management`
(POE, PPC, PDH…), nivel que INGESTA no tiene. Ej.: RUBIALES → INGESTA gerencia GOR = robustez VP GOR /
gerencia POE. A veces el código también cambia (GLH→GCH).
> **✅ DECISIÓN DEL USUARIO (2026-08-02): opción A — educar suave.** Aceptar el término del usuario y
> tender puente a la estructura oficial sin negarlo: *"lo que llamas gerencia GOR es la Vicepresidencia
> GOR, que agrupa las gerencias POE y PPÑ"*. 🔑 **El puente NO es 1:1 — es data-driven:** 6 de 11
> gerencias INGESTA mapean a 1 VP robustez; **5 mapean a 2 VPs** (GPA→GPA+VAO, GRM→GRM+VRC, GTA→GTA+VRC,
> CPV→CPV+VRC, PRP→PRP+VPI) → para esas la frase LISTA lo que agrupa, no afirma equivalencia. Tabla de
> puente derivable de `map_campo_robustez` (sin dato nuevo). **Solo afecta la PROSA**, no el conteo (J-3
> ya lo blinda con distinct-uwi + jerarquía canónica).

### Qué queda cuantificable por jerarquía, con qué confianza

| Pregunta | Fuente | Confianza |
|---|---|---|
| ¿cuántas gerencias/activos/campos tiene la VP X? | `map_campo_robustez` (ECP) o `wells_attributes` | 🟢 (ECP) · 🔴 terceros |
| ¿cuántos pozos tiene {VP/gerencia/activo/campo ECP}? | `wells_attributes` `COUNT(DISTINCT uwi)` | 🟡 — registro, no producción; +colisión de nombre |
| ¿cuántos pozos ACTIVOS? | `wells_attributes` `well_status` | 🔴 — grano uwi×zona, necesita regla |
| ¿cuántos pozos tiene {campo tercero}? | — | 🔴 — no está en robustez |
| ¿cuántos pozos produjeron en {mes}? | `robustez_v02.ops.flow_rates` | 🟡 — SÍ existe (5.779 crudo abr-26), pero universo robustez (no reconcilia con el reporte, ECP-only, sin gas) |
| ¿cuánto produjo/EBITDA cada pozo en {mes}? | `flow_rates` / `financial_results` | 🟡 — oil/water/blend + EBITDA por pozo/mes (2025-01→2026-06); universo robustez, cross-DB |

**Conclusión:** el S28 **desbloquea** el conteo estructural de la jerarquía (antes imposible) — es un avance
real. Pero es un conteo de **catálogo/registro** con techo ECP (58%), y separado del universo de
producción. Para el catálogo de Cuantificar, "conteo_pozos" y "conteo_gerencias/activos" entran como
variables **🟡 nuevas** (fuente `robustez_v02`, cross-DB, atemporal), NO como parte del fact de producción.

---

---

## 8. Eje TEMPORAL — niveles N1-N4 × grano × producto (verificado 2026-08-02)

**Cobertura:** MES `fact_mes` REAL = **18 meses** continuos (dic-2024→may-2026), los 3 productos.
DÍA `fact_dia` = **174 días continuos, 0 huecos** a nivel agregado (nov-2025→17-may-2026), REAL puro.
(La Densidad reporta huecos POR ENTIDAD → cero traicionero sigue aplicando por entidad.)

| Nivel (motor_Q §4.2) | MES (18m, 3 productos) | DÍA (174d, nov25→may26) |
|---|---|---|
| **N1 puntual** | 🟢 mes cerrado · 🟡 mes en curso = proyección | 🟢 crudo/gas · 🟡 blancos (×2) |
| **N2 acumulado** | 🟢 cerrados · 🟡 curso: proy ≠ acumulado | 🟢 crudo · 🔴 blancos · 🟡 gas |
| **N3 serie** | 🟢 los 3 (18 puntos) | 🟢 crudo/gas · 🔴 blancos |
| **N4 variación** | 🟢 · 🟡 salto 2025→26 | 🟡 crudo/gas (ruidoso) · 🔴 blancos |

**Caveats a cablear:**
- **T-1 · Mes en curso = PROYECCIÓN, no acumulado.** Verificado: mayo diario 17d = 48,5M vs mayo mensual
  REAL = 88,9M (extrapolado). Distinguir "va acumulado X (N días)" de "proyecta cerrar Y". Nunca leer la
  proyección como acumulado.
- **T-2 · Blancos solo a MES** (sin N2/N3/N4 a día por el ×2). Crudo: todo. Gas: todo con asterisco de unidad.
- **T-3 · Salto 2025→2026 (+30%)** en la serie REAL (crudo ~66M dic-25 → ~89M ene-26). N4 que cruce el
  salto refleja probable cambio de alcance/metodología, no crecimiento real. Avisar en variaciones inter-anuales.
- **T-4 · Periodo v1 = solo MES** (`_parse_periodo`); año/trimestre/semana no se parsean.
- **T-5 · Techos:** día hasta 2026-05-17; mes REAL hasta may-2026 (con la proyección de T-1).

---

## 9. CATÁLOGO CONSOLIDADO (entregable) → `catalogo_cuantificar_DRAFT.yaml`

El catálogo accionable (el contrato que leerá el motor) vive en
**`INGESTA/Rep_Prod/catalogo_cuantificar_DRAFT.yaml`**. Matriz de un vistazo:

| Variable | Unidad | Fuente | Grano | Confianza |
|---|---|---|---|---|
| **crudo** | bbl | INGESTA | día + mes | 🟢 |
| **gas** | MSCF† | INGESTA | día + mes | 🟡 (unidad†) |
| **blancos** | bbl | INGESTA | **solo mes** | 🟡 mes · 🔴 día |
| **agua** | bbl | robustez | mes | 🟡 (universo robustez) |
| **gap / cumplimiento** | bbl / % | INGESTA (vs PPTO) | mes | 🟢 |
| **diferidas** (crudo/gas) | bbl | ECP_DIFERIDAS | histórico | 🟡 (hasta jul-25) |
| **conteo gerencias/activos/campos** | # | map_campo_robustez | — | 🟢 ECP |
| **conteo pozos** | # | robustez wells | — | 🟡 (registro) |
| **pozos activos** | # | robustez wells | — | 🟡 (partición) |
| **pozos que produjeron / prod por pozo** | #/bbl | robustez flow_rates | mes | 🟡 (universo robustez) |
| **EBITDA / breakeven / revenue** | kUSD | robustez financial | pozo·mes | 🟡 (solo aceite) |

† unidad del gas pendiente de confirmar (MSCF vs KPC/KPCD).

**Referencias:** default **PPTO**; explícitas OPERATIVO/CONTABLE/P50/promedio-año; PROGRAMA bloqueado
(versionado). **Niveles N1-N4 × grano:** §8. **7 combinaciones NO soportadas** (rechazo explícito):
agua-en-reporte, blancos-día, pozos-en-unidades-del-reporte, gas-por-pozo, NOPAT/plata-en-INGESTA,
mantenimientos, diferidas-blancos, año/trim/semana. Todas las reglas de honestidad en el YAML §reglas.

---

### Conclusión de la validación
El catálogo del plan es **direccionalmente correcto** y más completo que mi lista inicial en un punto
(EBITDA/pozo existen en ROBUSTEZ, que yo no había mirado). Pero como *contrato de construcción* le
faltan tres columnas: **grano válido**, **base física** y **universo/reconciliación**. Sin ellas, 3 de
las 18 variables entregarían un número equivocado o irrecuperable (blancos-diario, conteo_pozos,
cualquier cruce plata↔barriles). Recomendación: el YAML debe ser
`variable × grano × base × confianza`, no `variable → fuente`.
