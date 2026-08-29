# OCR de reportes cifrados (IRM) — Diagnóstico + Runbook para retomar

> **Estado al 2026-08-03.** Documento vivo. Reúne (1) el hallazgo de por qué ciertos `.xlsm` del
> Reporte Diario no se pueden ingerir, (2) las vías descartadas, y (3) el **workaround OCR** con
> `INGESTA/Rep_Prod/ocr.py` para reconstruir las tablas clave desde capturas de pantalla. Pensado
> para **retomar el proceso el día que se haga la actualización** sin re-investigar nada.

---

## 1. El problema (por qué esos archivos no entran)

Los reportes viven en `report/<YYYYMMDD>_Reporte Diario de Producción.xlsm`. Al 2026-08-03 hay 29
archivos (01→30 jul 2026, falta el 02). Se dividen en dos grupos nítidos:

| Grupo | Fechas | Firma | Estado |
|---|---|---|---|
| 🟢 **LIBRES** | 23 → 30 jul (8 archivos) | `50 4B 03 04` (`PK`, OOXML plano) | **Ingeribles** ya |
| 🔴 **CIFRADOS** | 01 → 22 jul (22 archivos) | `D0 CF 11 E0` (OLE2) | **No ingeribles** |

### Diagnóstico verificado (no es una contraseña — es IRM)
Se inspeccionó el contenedor OLE2 de los cifrados:
- Estructura interna: `\x06DataSpaces` + `EncryptedPackage` (~36 MB) + `Version`, **sin stream
  `EncryptionInfo`**.
- Nombre de la transformada: **`Microsoft.Metadata.DRMTransform`** / `DRMEncryptedTransform`.
- `msoffcrypto-tool` lo rechaza (`Unrecognized file format`) precisamente porque **no** es cifrado
  por contraseña ECMA-376.

**Conclusión:** es **IRM / Rights Management (AD RMS / Azure Information Protection)**. La clave la
custodia el servidor de rights management de Ecopetrol y se entrega como *use-license* solo a
usuarios autorizados y autenticados. **No hay contraseña, ni hash local, ni descifrado offline.**

### Cómo re-verificar el estado de los archivos (rápido)
```bash
cd report
for f in *.xlsm; do
  sig=$(head -c4 "$f" | xxd -p)
  [ "$sig" = "504b0304" ] && echo "$f LIBRE" || echo "$f CIFRADO/IRM"
done
```
(El pipeline detecta esto solo: `detector.nombres_de_hojas` hace `try/except zipfile.BadZipFile` →
un archivo IRM devuelve `set()` de hojas → se reporta como STD vacío / “no es un zip”.)

---

## 2. Vías descartadas (y por qué)

| Vía | Resultado |
|---|---|
| Contraseña / `VelvetSweatshop` / vacía | ❌ No aplica — no es cifrado por contraseña |
| `msoffcrypto` / descifrado offline / fuerza bruta | ❌ No soporta IRM; la clave está en el servidor, no en el archivo |
| Convertir a **PDF** | ❌ Requiere abrir/descifrar primero (misma autorización); el IRM suele **bloquear imprimir/exportar**; y un PDF **pierde la estructura tabular** → inútil para el ETL |
| Leer con openpyxl / pipeline | ❌ Ve el `.xlsm` como “no es un zip” |

**La única vía real a los datos** pasa por la **autorización RMS de un usuario habilitado**:
1. **(Preferida) Re-guardar sin IRM:** un usuario autorizado abre el `.xlsm`, quita la restricción
   (*Archivo → Información → Proteger libro → Acceso sin restricciones*) y **Guardar como** → queda
   OOXML plano, ingeribles al 100% con fidelidad total (es lo que ya ocurrió con los del 23–30 jul).
2. **Pedir el reenvío sin IRM** a quien genera el reporte.
3. **Workaround OCR** (este documento) — solo si (1) y (2) no son posibles y basta la **capa resumen**.

---

## 3. El workaround OCR — alcance (qué recupera y qué NO)

El detalle **ECP por campo/pozo** vive en 3 hojas RAW (`BDP_datos_dia` ~40K filas, `BDP_datos_mes`
~315K filas, `BDP_Programa`) → **físicamente imposible de fotografiar** → **queda fuera**.

Lo que la app **realmente consume** y **sí es fotografiable** (capa resumen empresa/corporativo):

| Hoja Excel a fotografiar | Alimenta (tabla destino) | Loader | Checksum disponible |
|---|---|---|---|
| **Producción filiales** (bloques REAL + PROGRAMA; PROYECCIÓN la ignora el loader) | `core.fact_produccion_diaria` | `load_filiales` | Σ7 productos = `Total G.E.` + vista agregada por empresa |
| **REPORTE_PRESIDENT** (bloque MES G:M) | `core.fact_tabla_hoja` (hoja=REPORTE_PRESIDENT) | `_reporte_president_extract` | Ecopetrol=ΣCrudo/Gas/Blancos; Upstream=Ecp+Fil; Δ=Real−BaseP50 |
| **POP Filiales y Exploración** (TOTAL por empresa) | `core.fact_plan_mensual` | `load_pop` | Débil → requiere revisión |
| **COMENTARIOS** (texto CRUDO/GAS/BLANCOS) | `core.fact_comentarios_produccion` | `load_comentarios` | Ninguno (texto) → requiere revisión |

> **Fuente del mapeo** (verificado en código, 2026-08-03): los endpoints de `analisis/` consumen
> `fact_produccion_diaria` (15×, la más usada, ← Producción filiales), `fact_produccion_mes_ecp` /
> `dia_ecp` / `programa_ecp` (← BDP, NO fotografiables), `fact_tabla_hoja` filtrando
> `hoja='REPORTE_PRESIDENT'`, `fact_plan_mensual` (← POP), `fact_comentarios_produccion` (← COMENTARIOS).

**Con OCR se enciende:** tablero **Filiales** + encabezado **P50/Compromiso** + POP + causas.
**Sigue vacío:** Desempeño ECP por campo, curva diaria, BOPD, PPTO diario, densidad, Consulta→
Cuantificar, análisis ejecutivo ECP. (Para eso, solo sirve el `.xlsm` sin IRM.)

### Por qué el enfoque es elegante (reusa el pipeline sin tocarlo)
Verificado en `backend/app/features/ingesta/services.py`:
- Un `.xlsx` **sin hojas BDP** entra por la **ruta STD** (`tiene_raw`=False) y aun así ejecuta
  `load_filiales` / `load_pop` / `load_comentarios` (gatillados por presencia de hoja) y
  `load_tablas_hoja` (línea ~1845, **fuera del `if raw`**) → carga REPORTE_PRESIDENT.
- `get_reporte` toma la fecha del nombre (`\d{8}`), así que el archivo reconstruido debe llamarse
  `20260701_*.xlsx`.
- `s()`/`num()` tratan `#REF!`/`#N/D` como nulos → el bloque DÍA (#REF!) de PRESIDENT no estorba.
- **Requisito:** el `.xlsx` reconstruido debe **imitar el layout** (posiciones/anclas), no solo
  volcar valores. `ocr.py` lo hace.

---

## 4. `ocr.py` — la herramienta

- **Ubicación:** `INGESTA/Rep_Prod/ocr.py`
- **Motor:** **Tesseract LOCAL** (decisión del usuario: respeta la confidencialidad IRM; **NO** se
  envían datos a terceros como Azure/Google/Textract).
- **Dependencias:** binario Tesseract + idioma **`spa`** instalados; `pytesseract`, `Pillow`
  (opcional `opencv-python` para upscale+binarizado). `openpyxl` ya viene en el venv.

### Qué hace
1. Recorre `report/<YYYYMMDD>/`, OCR de cada imagen → tokens con caja (`pytesseract.image_to_data`).
2. **Clasifica** cada imagen por anclas: `Base P50`→PRESIDENT · `COMENTARIO PROGRAMA` o
   `PRODUCTO+ACTIVOS+AREA`→COMENTARIOS · `POP Filiales`→POP · `EMPRESA`+`(crudo)`→Filiales.
   La vista **agregada** por empresa se detecta como `filiales_agg` (reservada para checksum, no se
   escribe como hoja).
3. **Reconstruye** cada hoja imitando el layout del loader correspondiente.
4. **Valida por checksum** (Filiales y PRESIDENT); POP/COMENTARIOS se marcan “requiere revisión”.
5. Escribe por carpeta:
   - `<fecha>_reconstruido_ocr.xlsx` (hojas nombradas exactamente como las modeladas)
   - `<fecha>_ocr_validacion.txt` (OK / FALLA(dif) por tabla/columna + veredicto)
6. COMENTARIOS repartido en varias imágenes (p.ej. 005+006) → se **acumula** en una hoja.

### Uso
```bash
cd INGESTA/Rep_Prod
uv run python ocr.py --solo 20260701           # una carpeta
uv run python ocr.py                            # todas las carpetas de report/
uv run python ocr.py --tesseract "C:\Program Files\Tesseract-OCR\tesseract.exe"   # si no está en PATH
uv run python ocr.py --ruta /otra/raiz --lang spa+eng
```

### Estado de calibración (IMPORTANTE al retomar)
- ✅ **Probado estáticamente:** `py_compile` OK; parser es-CO 10/10 (`19.800`→19800, `(2.966)`→-2966,
  `481,4`→481.4, `#REF!`→None…). Clasificación, checksums y escritura de layout: sólidos por diseño.
- ⚠️ **PENDIENTE de calibrar contra imágenes reales:** la **geometría OCR** (tolerancias de fila/
  columna en `agrupar_filas`/`_tol_columnas`, `--psm`, escala de `_cargar_preprocesada`). Tesseract
  sobre tablas densas rara vez sale perfecto al primer intento. El `*_ocr_validacion.txt` dirá qué
  columnas no cuadran → se ajustan tolerancias/psm hasta que Filiales y PRESIDENT queden en verde.
- El set de capturas de referencia ya existe: `report/20260701/001.png … 006.png` (Filiales,
  vista agregada, PRESIDENT, POP, COMENTARIOS×2). Verificado a mano que sus checksums cierran
  (Total G.E. y cruce Filiales 119.3 = PRESIDENT).

---

## 5. RUNBOOK — cómo retomar la actualización

**Pre-requisito de decisión:** si en ese momento hay un usuario autorizado que pueda **re-guardar
los `.xlsm` sin IRM**, hazlo — es superior (fidelidad total + recupera la capa ECP). El OCR es solo
el plan B para la capa resumen.

### Si se va por OCR:
1. **Capturar** las 4 hojas clave de cada día cifrado (ver §3). Guardar las imágenes en
   `report/<YYYYMMDD>/`. Tips:
   - Producción filiales y POP traen **ventana multi-día/multi-mes** en columnas → pocas capturas
     cubren varios días.
   - REPORTE_PRESIDENT es snapshot → **una por día**.
   - Incluir siempre `Total G.E.` y `PROMEDIO` (son los checksums).
2. **Verificar Tesseract:** `tesseract --version` y que exista el idioma `spa` (`tesseract --list-langs`).
3. **Correr** `uv run python ocr.py --solo <YYYYMMDD>` (o sin `--solo` para todas).
4. **Leer** `report/<YYYYMMDD>/<fecha>_ocr_validacion.txt`:
   - Veredicto `INGERIBLE` → seguir.
   - `REVISAR` → abrir el `.xlsx`, corregir a mano las celdas marcadas (o recapturar) y/o ajustar
     tolerancias/`--psm` en `ocr.py` y re-correr.
5. **Revisar visualmente** COMENTARIOS (no tiene checksum numérico).
6. **Ingerir** el `.xlsx` reconstruido por el flujo normal (ruta STD):
   - dev: `uv run python -m app.cli batch` (apuntando a la carpeta con los `.xlsx`), o el subcomando
     de archivo único. En 139: `desplegar_version.bat` + ingesta.
   - ⚠️ La ingesta hace **DELETE+INSERT por reporte/hoja** y `config_reporte` tiene UNIQUE
     `fecha_reporte`: si algún día YA tuviera datos, se sobrescriben. Para los días 01–22 jul hoy no
     hay datos, así que no hay colisión.
7. **Verificar** en el tablero: para esos días deben encenderse Filiales + encabezado P50; el resto
   ECP quedará vacío (esperado).

### Regla de oro
**Ninguna columna con checksum en FALLA se declara ingeribles.** El `.xlsx` se genera igual para
revisión, pero el reporte de validación lo marca y esa tabla se corrige o se omite.

---

## 6. Referencias de código

| Qué | Dónde |
|---|---|
| Detección NEW/STD (IRM → set vacío) | `backend/app/features/ingesta/detector.py` (`tiene_raw`, `nombres_de_hojas`) |
| Orquestador de ingesta (ruta STD carga Filiales/POP/Comentarios/tabla_hoja) | `backend/app/features/ingesta/services.py` (~1808–1845) |
| Layout que espera cada loader | `load_filiales` (334), `load_pop` (364), `load_comentarios` (302), `_reporte_president_extract` (1546) |
| Etiquetas/normalizadores (deben calzar) | `backend/app/features/ingesta/transforms.py` (`split_label`, `norm_emp`, `norm_prod`) |
| Helpers de parseo (ruido/fechas) | `backend/app/shared/utils.py` (`s`, `num`, `to_date`) |
| Herramienta OCR | `INGESTA/Rep_Prod/ocr.py` |
| Capturas de referencia | `report/20260701/001.png … 006.png` |

---

## 7. Pendientes

- [ ] Calibrar la geometría OCR de `ocr.py` contra `report/20260701/` (Filiales + PRESIDENT en verde).
- [ ] Extender/validar POP y COMENTARIOS con revisión visual.
- [ ] Correr el lote completo de los 22 días cifrados cuando existan sus capturas.
- [ ] (Ideal) Gestionar los `.xlsm` **sin IRM** con un usuario autorizado → haría innecesario el OCR
      y recuperaría además la capa ECP por campo.
