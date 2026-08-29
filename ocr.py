#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ocr.py — Reconstrucción de las tablas clave de un Reporte Diario a partir de CAPTURAS DE PANTALLA.

CONTEXTO
--------
Los .xlsm de algunos días llegan cifrados con IRM (Rights Management) y el pipeline de ingesta
NO puede leerlos (ver HALLAZGO de IRM). Como recurso, un usuario autorizado abre el archivo en
modo lectura y fotografía las TABLAS CLAVE. Este script toma esas imágenes y reconstruye un .xlsx
cuyas hojas se llaman e imitan el layout de las hojas originales, de modo que la INGESTA EXISTENTE
(ruta STD) lo procese sin ningún cambio en el pipeline.

Hojas soportadas (capa resumen — el detalle ECP por campo vive en hojas RAW no fotografiables):
    · "Producción filiales"        -> core.fact_produccion_diaria      (REAL + PROGRAMA)
    · "REPORTE_PRESIDENT"          -> core.fact_tabla_hoja             (bloque MES)
    · "POP Filiales y Exploración" -> core.fact_plan_mensual           (TOTAL por empresa)
    · "COMENTARIOS"                -> core.fact_comentarios_produccion  (texto)

ESTRUCTURA DE ENTRADA/SALIDA
----------------------------
    report/
      <YYYYMMDD>/
        001.png 002.png ...              (entrada: capturas)
        <YYYYMMDD>_reconstruido_ocr.xlsx (salida: hojas nombradas, layout imitado)
        <YYYYMMDD>_ocr_validacion.txt    (salida: reporte de checksums por tabla/columna)

MOTOR OCR
---------
Tesseract LOCAL (respeta la confidencialidad; NO se envían datos a terceros).
Requiere: binario Tesseract + idioma `spa` instalados, y `pytesseract`, `Pillow` (opcional `opencv-python`).

REGLA DE ORO
------------
Ninguna columna/tabla cuyo checksum FALLE se declara ingeribles. El .xlsx se genera igual (para
revisión humana), pero el reporte de validación la marca y la ingesta puede omitirla.

Uso:
    uv run python ocr.py                       # procesa todas las carpetas de report/
    uv run python ocr.py --solo 20260701       # una sola carpeta
    uv run python ocr.py --ruta /otra/ruta     # otra raíz de reportes
    uv run python ocr.py --tesseract "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

# ------------------------------------------------------------------ dependencias (con mensaje claro)
try:
    import pytesseract
    from PIL import Image
except ImportError as e:  # pragma: no cover - entorno del usuario
    sys.stderr.write(
        "FALTAN DEPENDENCIAS: instala `pytesseract` y `Pillow` (y el binario Tesseract + idioma `spa`).\n"
        f"Detalle: {e}\n")
    raise

try:
    import cv2  # opcional: solo para preprocesado (upscale + binarizado). Si no está, se usa PIL.
    import numpy as np
    _HAY_CV2 = True
except ImportError:  # pragma: no cover
    _HAY_CV2 = False

try:
    from openpyxl import Workbook
except ImportError as e:  # pragma: no cover
    sys.stderr.write("FALTA `openpyxl` (ya viene en el venv de INGESTA).\n")
    raise


# ================================================================== configuración
# Raíz de reportes por defecto: <repo>/report  (ocr.py vive en INGESTA/Rep_Prod/)
RUTA_REPORTES_DEFAULT = Path(__file__).resolve().parents[2] / "report"
EXT_IMG = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}

# Nombres EXACTOS de hoja que esperan los extractores/loaders del pipeline (services.py)
HOJA_FILIALES = "Producción filiales"
HOJA_PRESIDENT = "REPORTE_PRESIDENT"
HOJA_POP = "POP Filiales y Exploración"
HOJA_COMENTARIOS = "COMENTARIOS"

# Filas de producto de "Producción filiales" (orden y etiquetas que entiende split_label/norm_*)
FILIALES_FILAS = ["Hocol (crudo)", "Hocol (gas)", "America (crudo)", "America (gas)",
                  "Permian (crudo)", "Permian (gas)", "Permian (blancos)"]
# Entidades del bloque MES de REPORTE_PRESIDENT (orden vertical)
PRESIDENT_ENTIDADES = ["Crudo", "Gas", "Blancos", "Ecopetrol", "Filiales", "Upstream"]


# ================================================================== utilidades de texto/número
def _strip_acc(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c))


def norm_txt(t: str) -> str:
    """upper + sin acentos + colapsa espacios — para clasificar y buscar anclas."""
    return re.sub(r"\s+", " ", _strip_acc(str(t)).upper()).strip()


_NUM_NOISE = {"", "-", "–", "—", "#REF!", "#N/D", "#N/A", "#DIV/0!", "#VALUE!", "#NAME?", "N/D", "NA"}


def parse_num_esCO(raw):
    """Convierte un token es-CO a número.
        '19.800'    -> 19800      (punto = separador de miles)
        '1.916.317' -> 1916317
        '95,6'      -> 95.6       (coma = decimal)
        '(2.966)'   -> -2966      (paréntesis = negativo)
        '-3,8'      -> -3.8
        '-', '#REF!'-> None       (ruido/vacío)
    Devuelve int cuando no hay decimales, float si los hay, None si no es numérico.
    """
    if raw is None:
        return None
    t = str(raw).strip()
    if t.upper() in _NUM_NOISE or t == "":
        return None
    neg = False
    if t.startswith("(") and t.endswith(")"):
        neg, t = True, t[1:-1].strip()
    if t.startswith("-"):
        neg, t = True, t[1:].strip()
    # limpia cualquier caracter que no sea dígito, punto o coma (p.ej. flechas OCR, %, espacios)
    t = re.sub(r"[^\d.,]", "", t)
    if t == "":
        return None
    tiene_coma = "," in t
    if tiene_coma:
        # coma = decimal; punto = miles
        entero, _, dec = t.rpartition(",")
        entero = entero.replace(".", "")
        try:
            val = float(f"{entero}.{dec}") if dec else float(entero or "0")
        except ValueError:
            return None
    else:
        # solo puntos -> separadores de miles
        try:
            val = int(t.replace(".", ""))
        except ValueError:
            return None
    if neg:
        val = -val
    return val


# ================================================================== OCR: imagen -> tokens con caja
@dataclass
class Token:
    text: str
    x: int      # left
    y: int      # top
    w: int
    h: int

    @property
    def cx(self) -> float:
        return self.x + self.w / 2.0

    @property
    def cy(self) -> float:
        return self.y + self.h / 2.0


def _cargar_preprocesada(path: Path, escala: float = 2.0):
    """Devuelve una imagen PIL lista para OCR: upscale + binarizado si hay opencv."""
    if _HAY_CV2:
        img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise RuntimeError(f"No se pudo leer la imagen: {path}")
        if escala != 1.0:
            img = cv2.resize(img, None, fx=escala, fy=escala, interpolation=cv2.INTER_CUBIC)
        img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        return Image.fromarray(img)
    im = Image.open(path).convert("L")
    if escala != 1.0:
        im = im.resize((int(im.width * escala), int(im.height * escala)))
    return im


def ocr_tokens(path: Path, lang: str = "spa+eng", psm: int = 6) -> list[Token]:
    """OCR de una imagen -> lista de Token (palabra + caja). psm 6 = bloque uniforme de texto."""
    img = _cargar_preprocesada(path)
    cfg = f"--psm {psm}"
    data = pytesseract.image_to_data(img, lang=lang, config=cfg,
                                     output_type=pytesseract.Output.DICT)
    toks: list[Token] = []
    for i, txt in enumerate(data["text"]):
        if txt is None or str(txt).strip() == "":
            continue
        try:
            conf = float(data["conf"][i])
        except (ValueError, TypeError):
            conf = -1
        if conf >= 0 and conf < 30:      # descarta basura de baja confianza
            continue
        toks.append(Token(str(txt).strip(), int(data["left"][i]), int(data["top"][i]),
                          int(data["width"][i]), int(data["height"][i])))
    return toks


def texto_plano(toks: list[Token]) -> str:
    """Reconstruye el texto (para clasificar) uniendo tokens ordenados por fila y columna."""
    return " ".join(t.text for t in sorted(toks, key=lambda t: (round(t.cy / 12), t.cx)))


# ================================================================== agrupación en filas / columnas
def agrupar_filas(toks: list[Token], tol_ratio: float = 0.6) -> list[list[Token]]:
    """Agrupa tokens en filas por cercanía vertical. tol = fracción de la altura media del token."""
    if not toks:
        return []
    h_med = sorted(t.h for t in toks)[len(toks) // 2] or 12
    tol = h_med * tol_ratio
    filas: list[list[Token]] = []
    for t in sorted(toks, key=lambda t: t.cy):
        if filas and abs(t.cy - (sum(x.cy for x in filas[-1]) / len(filas[-1]))) <= tol:
            filas[-1].append(t)
        else:
            filas.append([t])
    for f in filas:
        f.sort(key=lambda t: t.cx)
    return filas


def unir_tokens_por_columna(fila: list[Token], centros_x: list[float], tol: float) -> dict[int, str]:
    """Asigna cada token de una fila a la columna (índice de centros_x) más cercana en x.
    Devuelve {idx_columna: texto_concatenado}. Tokens sin columna cercana se ignoran."""
    out: dict[int, list[str]] = {}
    for t in fila:
        j = min(range(len(centros_x)), key=lambda k: abs(t.cx - centros_x[k]))
        if abs(t.cx - centros_x[j]) <= tol:
            out.setdefault(j, []).append(t.text)
    return {j: " ".join(v) for j, v in out.items()}


def inferir_columnas_desde_fila(fila: list[Token]) -> list[float]:
    """Centros x de las columnas a partir de una fila de encabezado (p.ej. la de fechas)."""
    return [t.cx for t in sorted(fila, key=lambda t: t.cx)]


# ================================================================== clasificador de hoja
def clasificar(toks: list[Token]) -> str | None:
    """Determina a qué hoja pertenece una imagen por palabras ancla. Devuelve la clave de hoja o None.
    'filiales_agg' = la vista agregada por empresa (solo checksum, no se escribe como hoja)."""
    T = norm_txt(texto_plano(toks))
    if "BASE P50" in T or "COMPARATIVO DE PRODUCCION" in T:
        return HOJA_PRESIDENT
    if "COMENTARIO PROGRAMA" in T or ("PRODUCTO" in T and "ACTIVOS" in T and "AREA" in T):
        return HOJA_COMENTARIOS
    if "POP FILIALES" in T or ("PRODUCTO" in T and "TOTAL HOCOL" in T):
        return HOJA_POP
    if "EMPRESA" in T and ("REAL" in T or "PROGRAMA" in T):
        # detalle (con productos entre paréntesis) vs agregado por empresa
        if "(CRUDO)" in T or "(GAS)" in T or "(BLANCOS)" in T:
            return HOJA_FILIALES
        return "filiales_agg"
    return None


# ================================================================== resultado por hoja
@dataclass
class HojaResult:
    hoja: str
    grid: list[list] = field(default_factory=list)   # filas del .xlsx (layout imitado)
    checks: list[str] = field(default_factory=list)   # líneas del reporte de validación
    ok: bool = True                                    # False si algún checksum falló


# ================================================================== extractores por hoja
def extraer_filiales(toks: list[Token], agg: dict | None = None) -> HojaResult:
    """Reconstruye 'Producción filiales' (bloques REAL y PROGRAMA) imitando el layout de load_filiales:
        fila A='REAL'; fila A='EMPRESA' B..=fechas; filas A='Hocol (crudo)'.. B..=valores; A='Total G.E.'
    Checksum 1: suma de los 7 productos por fecha == 'Total G.E.'.
    Checksum 2 (si hay agg): crudo+gas por empresa == vista agregada.
    """
    res = HojaResult(HOJA_FILIALES)
    filas = agrupar_filas(toks)

    # localizar cada bloque por su etiqueta en la 1a columna
    def idx_de(label):
        for i, f in enumerate(filas):
            if f and norm_txt(f[0].text).startswith(label):
                return i
        return None

    bloques = []
    for etiqueta, tipo in [("REAL", "REAL"), ("PROGRAMA", "PROGRAMA")]:
        i = idx_de(etiqueta)
        if i is not None:
            bloques.append((tipo, i))
    if not bloques:
        res.ok = False
        res.checks.append("  [Filiales] NO se encontraron bloques REAL/PROGRAMA -> revisar imagen")
        return res

    for tipo, i0 in bloques:
        # la fila EMPRESA (con fechas) suele ser la siguiente a la etiqueta del bloque
        fila_emp = None
        for f in filas[i0:i0 + 3]:
            if any(norm_txt(t.text).startswith("EMPRESA") for t in f):
                fila_emp = f
                break
        if fila_emp is None:
            res.ok = False
            res.checks.append(f"  [Filiales/{tipo}] no se halló fila EMPRESA con fechas")
            continue
        fechas_tok = [t for t in fila_emp if norm_txt(t.text) not in ("EMPRESA", "PROMEDIO")]
        centros = inferir_columnas_desde_fila(fechas_tok)
        fechas = [t.text for t in sorted(fechas_tok, key=lambda t: t.cx)]
        tol = _tol_columnas(centros)

        res.grid.append([tipo])
        res.grid.append(["EMPRESA"] + fechas)

        matriz = {}   # fila_producto -> [valores por fecha]
        for prod in FILIALES_FILAS:
            fp = _buscar_fila_por_etiqueta(filas[i0:], prod)
            valores = ["" for _ in centros]
            if fp is not None:
                celdas = unir_tokens_por_columna([t for t in fp if t.cx > centros[0] - tol], centros, tol)
                for j in range(len(centros)):
                    valores[j] = parse_num_esCO(celdas.get(j, ""))
            matriz[prod] = valores
            res.grid.append([prod] + valores)

        # Total G.E. (para checksum + fidelidad humana)
        ft = _buscar_fila_por_etiqueta(filas[i0:], "TOTAL")
        totales = ["" for _ in centros]
        if ft is not None:
            celdas = unir_tokens_por_columna([t for t in ft if t.cx > centros[0] - tol], centros, tol)
            for j in range(len(centros)):
                totales[j] = parse_num_esCO(celdas.get(j, ""))
        res.grid.append(["Total G.E."] + totales)
        res.grid.append([])

        # ---- checksum 1: suma productos == Total G.E.
        okc = fallc = 0
        for j, fecha in enumerate(fechas):
            suma = sum(v for v in (matriz[p][j] for p in FILIALES_FILAS) if isinstance(v, (int, float)))
            tot = totales[j]
            if not isinstance(tot, (int, float)):
                continue
            if abs(suma - tot) <= 1:
                okc += 1
            else:
                fallc += 1
                res.checks.append(f"  [Filiales/{tipo}] {fecha}: Σproductos={suma} vs Total={tot} "
                                  f"** FALLA (dif {suma - tot:+}) **")
        res.checks.append(f"  [Filiales/{tipo}] checksum Total G.E.: {okc} OK / {fallc} FALLA")
        if fallc:
            res.ok = False

    return res


def extraer_president(toks: list[Token]) -> HojaResult:
    """Reconstruye 'REPORTE_PRESIDENT' bloque MES imitando lo que espera _reporte_president_extract:
        fila 1: [Producción, Real Mes, Proy Mes, 'Base P50', Delta, P50, Delta]
        filas : [entidad, real, proy, base_p50, delta, compromiso, delta]   (Crudo..Upstream)
    'Base P50' es el ANCLA que usa el extractor. El bloque DÍA (#REF!) se omite (lo ignora num()).
    Checksums: Ecopetrol == Crudo+Gas+Blancos ; Upstream == Ecopetrol+Filiales ; Delta == Real-BaseP50.
    """
    res = HojaResult(HOJA_PRESIDENT)
    filas = agrupar_filas(toks)

    # encabezado con "Base P50" -> define columnas del bloque MES
    fila_hdr = None
    for f in filas:
        if any("BASE P50" in norm_txt(t.text) for t in f) or \
           any(norm_txt(t.text) == "BASE" for t in f):
            fila_hdr = f
            break
    if fila_hdr is None:
        res.ok = False
        res.checks.append("  [PRESIDENT] no se encontró el ancla 'Base P50' -> revisar imagen")
        return res

    # Tomamos los tokens numéricos de encabezado a la derecha de la etiqueta de entidad.
    # Layout de salida fijo (6 medidas): Real, Proy, Base P50, DeltaP50, P50(compromiso), Delta
    HDR = ["Producción", "Real Mes", "Proy Mes", "Base P50", "Delta", "P50", "Delta"]
    res.grid.append(HDR)

    datos = {}   # entidad -> [real, proy, base, dp50, comp, dcomp]
    for ent in PRESIDENT_ENTIDADES:
        fp = _buscar_fila_por_etiqueta(filas, ent, exacto=True)
        vals = [""] * 6
        if fp is not None:
            nums = [parse_num_esCO(t.text) for t in sorted(fp, key=lambda t: t.cx)
                    if parse_num_esCO(t.text) is not None]
            # tomamos los 6 primeros numéricos de la fila (Real..Delta) — el bloque día viene en #REF!
            for k in range(min(6, len(nums))):
                vals[k] = nums[k]
        datos[ent] = vals
        res.grid.append([ent] + vals)
    res.grid.append([])

    # ---- checksums
    def val(ent, k):
        v = datos.get(ent, [""] * 6)[k]
        return v if isinstance(v, (int, float)) else None

    def chk(nombre, a, b, tol=0.2):
        if a is None or b is None:
            res.checks.append(f"  [PRESIDENT] {nombre}: dato faltante -> revisar")
            return
        if abs(a - b) <= tol:
            res.checks.append(f"  [PRESIDENT] {nombre}: OK ({a} ~ {b})")
        else:
            res.checks.append(f"  [PRESIDENT] {nombre}: ** FALLA {a} vs {b} (dif {a - b:+.1f}) **")
            res.ok = False

    for k, etiqueta in [(0, "Real"), (2, "BaseP50")]:
        suma = sum(x for x in (val(e, k) for e in ("Crudo", "Gas", "Blancos")) if x is not None)
        chk(f"Ecopetrol({etiqueta})=Σproductos", val("Ecopetrol", k), suma)
        ups = val("Ecopetrol", k)
        fil = val("Filiales", k)
        if ups is not None and fil is not None:
            chk(f"Upstream({etiqueta})=Ecp+Fil", val("Upstream", k), ups + fil)
    return res


def extraer_pop(toks: list[Token]) -> HojaResult:
    """Reconstruye 'POP Filiales y Exploración' con lo mínimo que lee load_pop:
        fila con B='Producto' C='Empresa' D..=fechas ; filas B='TOTAL <emp>' C=<emp> D..=valores.
    Checksum débil (no siempre hay total transversal): se marca 'requiere revisión'.
    """
    res = HojaResult(HOJA_POP)
    filas = agrupar_filas(toks)

    fila_hdr = None
    for f in filas:
        if any(norm_txt(t.text) == "PRODUCTO" for t in f):
            fila_hdr = f
            break
    if fila_hdr is None:
        res.ok = False
        res.checks.append("  [POP] no se encontró la fila de encabezado 'Producto' -> revisar")
        return res

    fechas_tok = [t for t in fila_hdr if norm_txt(t.text) not in ("PRODUCTO", "EMPRESA")
                  and (re.fullmatch(r"\d{8}", norm_txt(t.text)) or "PROMEDIO" in norm_txt(t.text))]
    centros = inferir_columnas_desde_fila(fechas_tok)
    fechas = [t.text for t in sorted(fechas_tok, key=lambda t: t.cx)]
    tol = _tol_columnas(centros)

    # encabezado (col A vacía; B=Producto, C=Empresa, D..=fechas)  — lo que espera load_pop
    res.grid.append(["", "Producto", "Empresa"] + fechas)

    for emp_label, emp_col in [("TOTAL HOCOL", "Hocol"), ("TOTAL EA", "EAI"), ("TOTAL PERMIAN", "Permian")]:
        fp = _buscar_fila_por_etiqueta(filas, emp_label)
        valores = ["" for _ in centros]
        if fp is not None:
            celdas = unir_tokens_por_columna([t for t in fp if t.cx > centros[0] - tol], centros, tol)
            for j in range(len(centros)):
                valores[j] = parse_num_esCO(celdas.get(j, ""))
        res.grid.append(["", emp_label, emp_col] + valores)

    res.checks.append("  [POP] extraído (checksum no aplicable a nivel fila) -> REQUIERE REVISIÓN VISUAL")
    return res


def extraer_comentarios(toks: list[Token]) -> HojaResult:
    """Reconstruye 'COMENTARIOS' con las columnas que lee load_comentarios:
        A=PRODUCTO (ffill) B=ACTIVOS C=AREA D=comentario E=comentario_programa (G=extra).
    Sin checksum numérico -> SIEMPRE se marca 'requiere revisión visual'.
    """
    res = HojaResult(HOJA_COMENTARIOS)
    filas = agrupar_filas(toks)

    res.grid.append(["PRODUCTO", "ACTIVOS", "AREA", "COMENTARIO", "COMENTARIO PROGRAMA"])
    # Heurística de columnas: 3 primeras cortas (producto/activo/area), el resto = comentario largo.
    n = 0
    for f in filas:
        if not f:
            continue
        cab = norm_txt(f[0].text)
        if cab in ("PRODUCTO", "PRODUCTOS") or cab.startswith("PRODUCTO"):
            continue
        # ordenar por x y separar las 3 primeras columnas del texto libre
        f = sorted(f, key=lambda t: t.cx)
        prod = f[0].text if f else ""
        activo = f[1].text if len(f) > 1 else ""
        area = f[2].text if len(f) > 2 else ""
        comentario = " ".join(t.text for t in f[3:]) if len(f) > 3 else ""
        if not (prod or activo or area or comentario):
            continue
        res.grid.append([prod, activo, area, comentario, comentario])
        n += 1
    res.checks.append(f"  [COMENTARIOS] {n} filas extraídas (texto, sin checksum) -> REQUIERE REVISIÓN VISUAL")
    return res


# ------------------------------------------------------------------ helpers de extracción
def _tol_columnas(centros: list[float]) -> float:
    """Tolerancia de asignación a columna = ~45% del paso medio entre columnas."""
    if len(centros) < 2:
        return 40.0
    pasos = [centros[i + 1] - centros[i] for i in range(len(centros) - 1)]
    paso = sorted(pasos)[len(pasos) // 2]
    return max(20.0, paso * 0.45)


def _buscar_fila_por_etiqueta(filas: list[list[Token]], etiqueta: str, exacto: bool = False):
    """Primera fila cuyo 1er token coincide con la etiqueta (por prefijo o exacto, sin acentos)."""
    E = norm_txt(etiqueta)
    for f in filas:
        if not f:
            continue
        a = norm_txt(f[0].text)
        if (a == E) if exacto else a.startswith(E):
            return f
    return None


# ================================================================== escritura del .xlsx
def escribir_excel(carpeta: Path, fecha: str, hojas: dict[str, HojaResult]) -> Path:
    """Escribe <fecha>_reconstruido_ocr.xlsx con una hoja por tabla reconstruida (layout imitado)."""
    wb = Workbook()
    wb.remove(wb.active)
    orden = [HOJA_FILIALES, HOJA_PRESIDENT, HOJA_POP, HOJA_COMENTARIOS]
    for nombre in orden:
        r = hojas.get(nombre)
        if not r or not r.grid:
            continue
        ws = wb.create_sheet(title=nombre[:31])
        for fila in r.grid:
            ws.append(fila)
    destino = carpeta / f"{fecha}_reconstruido_ocr.xlsx"
    wb.save(destino)
    return destino


def escribir_validacion(carpeta: Path, fecha: str, hojas: dict[str, HojaResult],
                        imgs_sin_clasificar: list[str]) -> Path:
    destino = carpeta / f"{fecha}_ocr_validacion.txt"
    lineas = [f"REPORTE DE VALIDACIÓN OCR — {fecha}", "=" * 60, ""]
    todo_ok = True
    for nombre, r in hojas.items():
        estado = "OK" if r.ok else "** CON FALLAS **"
        lineas.append(f"HOJA: {nombre}  [{estado}]")
        lineas.extend(r.checks or ["  (sin checks)"])
        lineas.append("")
        todo_ok = todo_ok and r.ok
    if imgs_sin_clasificar:
        lineas.append("IMÁGENES SIN CLASIFICAR (revisar manualmente):")
        lineas.extend(f"  - {n}" for n in imgs_sin_clasificar)
        lineas.append("")
    lineas.append("=" * 60)
    lineas.append("VEREDICTO: " + ("INGERIBLE (todos los checksums OK)" if todo_ok
                                    else "REVISAR — hay tablas con checksum en falla o pendientes de revisión"))
    destino.write_text("\n".join(lineas), encoding="utf-8")
    return destino


# ================================================================== orquestación por carpeta
def procesar_carpeta(carpeta: Path, lang: str) -> bool:
    fecha_m = re.search(r"(\d{8})", carpeta.name)
    fecha = fecha_m.group(1) if fecha_m else carpeta.name
    imgs = sorted(p for p in carpeta.iterdir() if p.suffix.lower() in EXT_IMG)
    if not imgs:
        print(f"  [{carpeta.name}] sin imágenes, se omite")
        return False

    print(f"  [{carpeta.name}] {len(imgs)} imágenes")
    hojas: dict[str, HojaResult] = {}
    agg_data: dict | None = None
    sin_clasificar: list[str] = []

    # 1a pasada: clasificar todas + capturar la vista agregada (checksum de filiales)
    clasificadas: list[tuple[Path, str, list[Token]]] = []
    for img in imgs:
        toks = ocr_tokens(img, lang=lang)
        clave = clasificar(toks)
        if clave is None:
            sin_clasificar.append(img.name)
            print(f"     {img.name}: SIN CLASIFICAR")
            continue
        print(f"     {img.name}: {clave}")
        clasificadas.append((img, clave, toks))

    # extraer por hoja (COMENTARIOS puede venir en varias imágenes -> se acumulan)
    for img, clave, toks in clasificadas:
        if clave == "filiales_agg":
            continue  # solo checksum futuro; no se escribe como hoja
        if clave == HOJA_FILIALES:
            r = extraer_filiales(toks, agg_data)
        elif clave == HOJA_PRESIDENT:
            r = extraer_president(toks)
        elif clave == HOJA_POP:
            r = extraer_pop(toks)
        elif clave == HOJA_COMENTARIOS:
            r = extraer_comentarios(toks)
        else:
            continue
        if clave in hojas:                      # acumular (p.ej. COMENTARIOS 005+006)
            hojas[clave].grid.extend(r.grid[1:] if clave == HOJA_COMENTARIOS else r.grid)
            hojas[clave].checks.extend(r.checks)
            hojas[clave].ok = hojas[clave].ok and r.ok
        else:
            hojas[clave] = r

    if not hojas:
        print(f"  [{carpeta.name}] no se reconstruyó ninguna hoja")
        escribir_validacion(carpeta, fecha, hojas, sin_clasificar)
        return False

    xlsx = escribir_excel(carpeta, fecha, hojas)
    val = escribir_validacion(carpeta, fecha, hojas, sin_clasificar)
    ok = all(h.ok for h in hojas.values())
    print(f"  [{carpeta.name}] -> {xlsx.name}  |  validación: {val.name}  |  "
          f"{'OK' if ok else 'REVISAR'}")
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(description="OCR de capturas -> .xlsx reconstruido para ingesta.")
    ap.add_argument("--ruta", default=str(RUTA_REPORTES_DEFAULT),
                    help="Raíz de reportes (contiene carpetas <YYYYMMDD>/). Def: <repo>/report")
    ap.add_argument("--solo", default=None, help="Procesar solo esta carpeta (nombre, p.ej. 20260701)")
    ap.add_argument("--lang", default="spa+eng", help="Idiomas Tesseract (def spa+eng)")
    ap.add_argument("--tesseract", default=os.environ.get("TESSERACT_CMD"),
                    help="Ruta al binario tesseract.exe (si no está en PATH)")
    args = ap.parse_args(argv)

    if args.tesseract:
        pytesseract.pytesseract.tesseract_cmd = args.tesseract

    raiz = Path(args.ruta)
    if not raiz.exists():
        sys.stderr.write(f"No existe la ruta de reportes: {raiz}\n")
        return 2

    carpetas = [raiz / args.solo] if args.solo else \
        sorted(p for p in raiz.iterdir() if p.is_dir())
    carpetas = [c for c in carpetas if c.exists() and c.is_dir()]
    if not carpetas:
        sys.stderr.write("No hay carpetas de reporte para procesar.\n")
        return 1

    print(f"Procesando {len(carpetas)} carpeta(s) en {raiz}")
    resultados = {c.name: procesar_carpeta(c, args.lang) for c in carpetas}
    print("\nRESUMEN:")
    for nombre, ok in resultados.items():
        print(f"  {nombre}: {'OK' if ok else 'REVISAR'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
