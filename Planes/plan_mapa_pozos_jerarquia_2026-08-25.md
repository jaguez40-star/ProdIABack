# Plan QV2-MAPA — el panel de Jerarquizar gana un mapa de pozos a la derecha

**ID tarea:** QV2-MAPA
**Fecha:** 2026-08-25
**Versión:** v2 (RE-auditada — 5 hallazgos nuevos sobre el v1, ver §1B)
**Maqueta aprobada:** https://claude.ai/code/artifact/f0cee978-f59c-4e23-ac14-597a8653f141

**Alcance:** el panel derecho de las preguntas de **jerarquía** pasa de mostrar solo el
árbol a mostrar **árbol a la izquierda + mapa de pozos sobre Colombia a la derecha**.

**Decisiones cerradas del usuario:**
1. **Todos los puntos iguales** — no se colorea por estado del pozo (ver R5).
2. El mapa abre **centrado y acercado (320%)** sobre el elemento consultado, no en
   Colombia completa.
3. **Solo se rotula** el campo consultado; los demás se identifican al pasar el cursor.
4. El panel mide **exactamente el alto del árbol**, sin altura mínima impuesta.
5. Contorno del país en **verde oscuro** (`--rb-green`), no gris.

---

## 0. Contexto para el agente EXECUTOR

> El executor NO tiene acceso a conversaciones previas ni al historial de Git.

**Proyecto:** ProdIA 2.0 — asistente conversacional de producción de Ecopetrol.
Flask (8020) sirve el frontend; INGESTA/FastAPI (8088) el motor.

**Raíz del repo:** `c:\APLICACIONES\ProdIA\12112025_prodIA\ProdIA-2.0\ProdIA-2.0\`

**Qué es el panel hoy:** cuando el usuario pregunta «¿qué es CASTILLA?», el Motor Q v2
clasifica como `jerarquizar`, y `respuesta_jerarquizar.py` devuelve
`{mensaje, panel:{tipo:"jerarq_arbol", datos:{...}}}`. El frontend
(`multitab_shell.js::__cnJerArbolHtml`) pinta el árbol VP→GER→ACT→CMP con un pie
«Pozos asociados · 437».

**Qué se quiere:** el árbol se queda como está en una columna izquierda, y a la derecha
aparece un mapa que ubica los pozos de esa entidad dentro de Colombia.

**Dos bases de datos distintas** (no confundirlas):

| BD | engine | contiene |
|---|---|---|
| `daily_report_prod` | `get_engine()` | `core.map_campo_robustez` (la jerarquía) |
| `robustez_v02` | `get_ops_engine()` | `ops.wells_attributes`, `ops.field_polygons` |

**Convenciones obligatorias:**
- Código, comentarios y docstrings **en español**.
- JS **ES5**: `var` + `function`. Sin `const`/`let`, arrow functions ni template literals.
- Python: SQLAlchemy Core (`sa.text`), nunca ORM.
- El HTML del frontend se compone concatenando strings; texto variable por `esc()`.

---

## 1. 🔴 Hallazgos de la auditoría — leer ANTES de escribir código

### 🔴 H1 — La tabla tiene grano de ZONA, no de pozo (el más importante)

Medido sobre `robustez_v02`: **40.542 filas ÷ 13.504 UWI = exactamente 3,0**. Un pozo con
tres zonas productoras genera tres filas — verificado en `CAS00356`, idénticas salvo la
columna `zone`.

**Toda consulta debe deduplicar por `uwi`.** El backend actual ya lo hace bien
(`_contar_pozos` usa `COUNT(DISTINCT uwi)`, y su docstring lo documenta); `ebitda/api.py:77`
usa `SELECT DISTINCT ON (uwi)`. El endpoint nuevo debe seguir el mismo criterio o los
conteos salen inflados ×3.

Cifras reales tras deduplicar:

| | filas (mal) | UWI (correcto) |
|---|---|---|
| Total | 40.542 | **13.504** |
| Con coordenada usable | 25.920 | **8.216** |
| CASTILLA | 1.871 | **437** (423 ubicables) |
| CHICHIMENE | 958 | **213** (212 ubicables) |

`437` es exactamente lo que muestra el panel hoy. **Es la cifra correcta.**

### 🔴 H2 — X e Y vienen INVERTIDAS en los pozos

Medido: 25.920 de 26.041 filas traen la **latitud en `coordinate_bottom_x`** y la
**longitud en `coordinate_bottom_y`**. Cero filas en el orden esperado.

`ops.field_polygons`, en cambio, está bien (`x_coord`=lon, `y_coord`=lat). **Las dos tablas
usan convenciones opuestas.** Cruzarlas sin corregir manda los pozos al océano Índico.

→ La corrección va **en la consulta SQL del backend**, en un solo sitio. No debe repetirse
en el frontend ni en ningún otro consumidor.

### 🔴 H3 — 121 pozos con coordenadas imposibles

Valores como `x=1133.00` o `y=0.25`, que no son Colombia ni invirtiendo. Un solo punto
perdido rompe la escala de todo el mapa → **filtrar en la consulta** con el bounding box de
Colombia (`lat -4..13`, `lon -80..-66`).

### 🟡 H4 — El frontend YA tiene el patrón de carga asíncrona que hace falta

`cuant_dia_panel` (línea 3335) y `analiza_foco` pintan un **placeholder** y lo rellenan
después con `fetch`, disparado en la línea 3411:

```js
if (panel.tipo === "cuant_dia_panel") __cnCompProdCargar(blk, d, "-stk" + __cnStackSeq);
```

→ El mapa usa **exactamente ese patrón**. No inventar uno nuevo: el árbol se pinta
inmediato (ya viene en el panel) y el mapa llega por `fetch` sin bloquearlo.

### 🟡 H5 — Los `rob_field` por nivel YA están calculados en el backend

`_cargar()` construye `act_fields`, `ger_fields` y `vp_fields` (líneas 76-126): el conjunto
de campos ECP que cuelga de cada activo / gerencia / VP. `_contar_pozos` ya los consume.

→ El endpoint nuevo **reusa esa misma resolución**. No hay que reconstruir la jerarquía.

### 🟢 H6 — El contrato del panel no cambia

`_panel()` (línea 552) ya devuelve `entidad` y `nivel` dentro de `datos`. Son los dos
únicos parámetros que el mapa necesita para pedir sus puntos. **Cero cambios en el
contrato**; solo se añade el bloque del mapa en el render.

### 🟡 H7 — Cobertura parcial, y hay que decirlo

- **15 de 118 campos** tienen contorno (`ops.field_polygons`), y **10 de esos 15 no
  cierran** el polígono (último vértice ≠ primero) → hay que cerrarlos al dibujar.
- Los 15 **cruzan por nombre** con `wells_attributes` sin tabla de equivalencias.
- **62 campos** tienen 5+ pozos ubicables — son los que se pintan en la vista país.

### 🔴 H8 — DATO SOSPECHOSO: La Cira e Infantas caen en el departamento equivocado

Casi todos los pozos de **LA CIRA** e **INFANTAS** aparecen cerca de `lon −70.8` (Orinoquía)
cuando ambos campos están en el **Magdalena Medio** santandereano, ~350 km al oeste.

No es error de lectura: la BD trae esas coordenadas así. **Sin un mapa el error era
invisible.** Un mapa da autoridad: esos dos campos mostrarían una ubicación falsa con toda
ella. Ver §7 — hay que decidir antes de publicar.

---

## 1B. 🔴🔴 RE-AUDITORÍA (v2) — 5 hallazgos que corrigen el v1

> Segunda pasada del flujo §15 sobre el propio plan, midiendo el código. Uno es
> BLOQUEANTE: el v1 no habría funcionado.

### 🔴 R1 — BLOQUEANTE: falta el proxy de Flask. El `fetch` daría 404

El frontend llama a `/api/consulta2/pozos_geo`, pero **Flask no tiene catch-all**: cada ruta
de `/api/consulta2/*` se declara UNA POR UNA en `routes/api.py` (verificado: `preguntar`,
`veredicto`, `veredicto_lote`, `senal`, `log`, `golden` — seis rutas, seis funciones).

Sin añadir la suya, el endpoint responde correctamente en INGESTA (8088) pero el navegador
recibe **404 de Flask** y el mapa nunca carga. El v1 omitía este archivo por completo.

**Corrección:** §2.6 (nueva) añade el proxy, calcado de `consulta2/log` — el único GET
existente, que ya resuelve el reenvío de query params con `params=request.args`.

### 🔴 R2 — `fuera_estructura` tiene su propio `return`: mi guarda era redundante Y equivocada

`__cnJerArbolHtml` corta en la línea 3902 con un `return` temprano para ese caso — **nunca
llega** al `return` final que el v1 modificaba. La condición `d.fuera_estructura` de mi
guarda era código muerto.

No es solo cosmético: revela que la rama existe y **no debe recibir mapa** (un campo fuera
de la estructura económica no tiene `rob_field`). Al no tocar ese `return`, ya queda
correcto — pero la guarda del §3.1 se simplifica y se documenta el porqué.

### 🟡 R3 — El peor caso de altura es la MITAD de lo que temía (medido)

El v1 avisaba de que una VP podía estirar el panel. Medido sobre `map_campo_robustez`:

| VP | gerencias | activos | campos | nodos en panel |
|---|---|---|---|---|
| GAA (la mayor) | 2 | 5 | 14 | **~22** |
| DFL | 1 | 2 | 4 | ~8 |

Con nodos de 33px, el peor caso real es **~825px**, no los 1419px teóricos del tope de 14×3
grupos. Es una altura perfectamente usable para un mapa — **el riesgo no existe** y el
`align-items:stretch` del §3.5 lo cubre sin tope artificial.

### 🟢 R4 — Rendimiento: la VP más grande son 1.118 pozos, no «>5.000»

El v1 anotaba como riesgo que una VP pudiera agregar más de 5.000 pozos. Medido: la VP con
más campos (**GPA**, 27 `rob_field`) tiene **1.118 pozos únicos**. Canvas dibuja eso sin
despeinarse.

→ Se retira ese riesgo de §7. La nota sobre agregar por campo queda como posibilidad futura
si algún día crece el catálogo, no como advertencia de este plan.

### 🟢 R5 — Confirmaciones que sostienen el v1

- **`campo_row[k]["rob_field"]`** existe con ese nombre exacto (`respuesta_jerarquizar.py:94`)
  → la rama `"campo"` de `rob_fields_de()` es correcta. Se retira la advertencia del v1.
- **Prefijo del router:** `APIRouter(prefix="/consulta2")` confirmado (`api.py:7`).
- **`respuesta_jerarquizar` NO está importado** en `api.py` (solo `maquina_q`, `log`,
  `senales`) → el import del §2.4 es obligatorio, no opcional.
- **Prefijos `.jm*` y `.jq-split` libres:** 0 coincidencias en CSS y JS. Sin colisión.
- **Sin listeners globales de `wheel`/`mousemove`** en el shell → los del §3.3 no pisan nada.

---

## 2. Especificación — BACKEND

### 2.1 CREAR — `app/features/consulta_v2/pozos_geo.py`

Módulo nuevo. Único sitio donde vive la corrección de coordenadas.

```python
"""pozos_geo.py — coordenadas de pozos y contornos de campo para el panel de Jerarquizar.

Lee robustez_v02 (get_ops_engine): ops.wells_attributes y ops.field_polygons. Es el ÚNICO
sitio donde se corrigen las coordenadas; ningún consumidor debe repetir estas reglas.

🔑 GRANO DE ZONA (H1). wells_attributes NO tiene una fila por pozo sino por ZONA productora:
medido 2026-08-25, 40.542 filas / 13.504 uwi = exactamente 3,0. Un pozo con 3 zonas da 3
filas (verificado en CAS00356: idénticas salvo `zone`). SIEMPRE DISTINCT ON (uwi) — contar
filas infla los conteos x3. Es el mismo criterio de _contar_pozos (COUNT DISTINCT uwi) y de
ebitda/api.py:77.

🔑 X/Y INVERTIDAS (H2). En wells_attributes la LATITUD viene en coordinate_bottom_x y la
LONGITUD en coordinate_bottom_y: medido, 25.920 de 26.041 filas están así y CERO en el orden
esperado. field_polygons, en cambio, está bien (x_coord=lon). Las dos tablas usan
convenciones opuestas; aquí se normaliza a {lon, lat} y hacia afuera solo salen esos nombres.

🔑 SOLO COORDENADA DE FONDO. coordinate_surface_x/y está VACÍA en las 40.542 filas (medido:
ni un solo valor). Lo que se publica es el fondo del pozo, que en un horizontal puede estar
a km de la cabeza. Si algún día se puebla la superficie, se cambia aquí.

🔑 FILTRO DE COLOMBIA (H3). 121 pozos traen coordenadas imposibles (x=1133.00, y=0.25). Un
solo punto perdido rompe la escala del mapa entero -> se descartan en el WHERE.
"""
import sqlalchemy as sa

from app.core.db import get_ops_engine

# Bounding box de Colombia continental. Descarta el ruido de ingesta (H3) sin recortar
# ningún campo real: el más occidental (ORITO, Putumayo) está en lon -76,9.
_LAT_MIN, _LAT_MAX = -4.5, 13.0
_LON_MIN, _LON_MAX = -80.0, -66.0

# El pozo se identifica por uwi; la coordenada NO varía entre sus duplicados (medido: 0 uwi
# con más de una coordenada distinta), así que DISTINCT ON puede quedarse con cualquiera.
_SQL_POZOS = sa.text("""
    SELECT DISTINCT ON (uwi)
           uwi,
           coordinate_bottom_y AS lon,   -- ¡invertidas! ver docstring
           coordinate_bottom_x AS lat
      FROM ops.wells_attributes
     WHERE field = ANY(:fields)
       AND coordinate_bottom_x BETWEEN :lat_min AND :lat_max
       AND coordinate_bottom_y BETWEEN :lon_min AND :lon_max
     ORDER BY uwi
""")

_SQL_TOTAL = sa.text("""
    SELECT COUNT(DISTINCT uwi) FROM ops.wells_attributes WHERE field = ANY(:fields)
""")

_SQL_POLY = sa.text("""
    SELECT field, x_coord AS lon, y_coord AS lat
      FROM ops.field_polygons
     WHERE field = ANY(:fields)
     ORDER BY field, seq
""")

# Centroides de TODOS los campos, para la vista país. MEDIANA y no promedio: LA CIRA tiene
# pozos dispersos y el promedio arrastra el centroide fuera del campo.
_SQL_CENTROIDES = sa.text("""
    SELECT field,
           COUNT(DISTINCT uwi) AS n,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY coordinate_bottom_y) AS lon,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY coordinate_bottom_x) AS lat
      FROM ops.wells_attributes
     WHERE coordinate_bottom_x BETWEEN :lat_min AND :lat_max
       AND coordinate_bottom_y BETWEEN :lon_min AND :lon_max
     GROUP BY field
    HAVING COUNT(DISTINCT uwi) >= 5
     ORDER BY 2 DESC
""")

_BBOX = {"lat_min": _LAT_MIN, "lat_max": _LAT_MAX, "lon_min": _LON_MIN, "lon_max": _LON_MAX}

_CENTROIDES = None   # caché de proceso: el catálogo no cambia entre reinicios


def _redondear(v, n=5):
    return None if v is None else round(float(v), n)


def geo(rob_fields):
    """{pozos, total, ubicables, contornos} para los rob_field dados, o None si `ops` no está.

    NUNCA lanza: si robustez_v02 no está disponible (p.ej. el servidor 139 sin esa BD), se
    devuelve None y el llamador OMITE el mapa — el árbol sigue intacto. Mismo criterio de
    degradación con gracia que _contar_pozos en respuesta_jerarquizar.
    """
    fields = sorted({f for f in (rob_fields or set()) if f})
    if not fields:
        return None
    try:
        eng = get_ops_engine()
        with eng.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
            p = dict(_BBOX); p["fields"] = fields
            pozos = [{"uwi": r[0], "lon": _redondear(r[1]), "lat": _redondear(r[2])}
                     for r in c.execute(_SQL_POZOS, p)]
            total = c.execute(_SQL_TOTAL, {"fields": fields}).scalar() or 0
            contornos = {}
            for f, lon, lat in c.execute(_SQL_POLY, {"fields": fields}):
                contornos.setdefault(f, []).append([_redondear(lon), _redondear(lat)])
    except Exception:
        return None
    return {"pozos": pozos, "total": int(total), "ubicables": len(pozos),
            "contornos": contornos}


def centroides():
    """[{f, n, lon, lat}] de los campos con 5+ pozos ubicables (62 al 2026-08-25), para la
    vista país. Se cachea en proceso: es un catálogo, no cambia dentro de una sesión.
    [] si `ops` no está disponible — la vista país se degrada a solo el contorno."""
    global _CENTROIDES
    if _CENTROIDES is not None:
        return _CENTROIDES
    try:
        eng = get_ops_engine()
        with eng.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
            _CENTROIDES = [{"f": r[0], "n": int(r[1]),
                            "lon": _redondear(r[2], 4), "lat": _redondear(r[3], 4)}
                           for r in c.execute(_SQL_CENTROIDES, _BBOX)]
    except Exception:
        return []            # sin cachear: reintenta en la próxima llamada
    return _CENTROIDES
```

### 2.2 CREAR — `app/features/consulta_v2/geo_colombia.py`

El contorno del país. **Archivo aparte** para no mezclar datos con lógica.

```python
"""geo_colombia.py — contorno simplificado de Colombia continental para el panel del mapa.

108 vértices [lon, lat], suficientes para orientar. NO es cartografía oficial: si el panel
sale a producción, sustituir por un GeoJSON del IGAC o usar el `scattergeo` de Plotly, que
ya viene con el país. Se sirve desde el backend (y no embebido en el JS) para poder
cambiarlo sin tocar el frontend.
"""

CONTORNO = [
    [-77.40, 8.67], [-77.35, 8.67], [-77.20, 8.50], [-77.10, 8.20], [-76.90, 8.10],
    [-76.85, 7.90], [-76.75, 8.00], [-76.60, 8.20], [-76.40, 8.60], [-76.10, 8.95],
    [-75.70, 9.40], [-75.60, 9.45], [-75.30, 9.30], [-75.30, 9.80], [-75.10, 10.20],
    [-74.85, 10.75], [-74.40, 10.95], [-74.20, 11.10], [-73.90, 11.30], [-73.50, 11.20],
    [-73.10, 11.35], [-72.50, 11.75], [-72.20, 11.85], [-71.70, 12.45], [-71.30, 12.35],
    [-71.10, 12.20], [-71.13, 11.85], [-71.35, 11.60], [-71.90, 11.45], [-72.20, 11.15],
    [-72.45, 10.85], [-72.65, 10.35], [-72.90, 10.00], [-72.95, 9.60], [-72.75, 9.30],
    [-72.50, 9.10], [-72.35, 8.65], [-72.40, 8.35], [-72.20, 8.10], [-72.05, 7.75],
    [-71.80, 7.40], [-71.55, 7.10], [-71.15, 6.95], [-70.75, 7.10], [-70.30, 6.95],
    [-69.90, 6.25], [-69.40, 6.15], [-68.95, 6.20], [-68.30, 6.15], [-67.85, 6.30],
    [-67.45, 6.20], [-67.30, 6.00], [-67.45, 5.60], [-67.60, 5.20], [-67.85, 4.55],
    [-67.65, 3.85], [-67.30, 3.40], [-67.85, 2.85], [-67.20, 2.40], [-66.90, 1.75],
    [-66.87, 1.22], [-67.10, 1.15], [-67.30, 1.90], [-67.90, 1.75], [-68.20, 1.72],
    [-68.20, 1.10], [-69.85, 1.07], [-69.85, 0.60], [-69.55, 0.65], [-69.40, 0.90],
    [-69.20, 0.75], [-69.20, -0.55], [-69.60, -0.75], [-69.95, -4.20], [-70.05, -2.60],
    [-70.70, -2.20], [-71.40, -2.30], [-72.40, -2.40], [-73.15, -2.60], [-73.65, -1.80],
    [-74.20, -1.00], [-74.80, -0.20], [-75.30, 0.10], [-75.80, 0.10], [-76.30, 0.40],
    [-77.00, 0.35], [-77.45, 0.40], [-77.70, 0.80], [-77.85, 0.85], [-78.20, 1.05],
    [-78.60, 1.25], [-78.85, 1.45], [-78.60, 1.80], [-78.75, 2.30], [-78.35, 2.60],
    [-77.90, 2.70], [-77.65, 3.20], [-77.35, 3.90], [-77.45, 4.30], [-77.30, 4.80],
    [-77.40, 5.40], [-77.30, 5.80], [-77.50, 6.30], [-77.35, 6.80], [-77.60, 7.20],
    [-77.75, 7.70], [-77.45, 8.05], [-77.40, 8.67],
]
```

### 2.3 MODIFICAR — `respuesta_jerarquizar.py`: exponer los `rob_fields` del nivel

El endpoint necesita resolver «entidad + nivel → conjunto de rob_field». La resolución ya
existe dentro de `_cargar()` (H5) pero no está expuesta. **Añadir** esta función pública
justo después de `_contar_pozos` (~línea 230):

```python
def rob_fields_de(nivel, canonical):
    """Conjunto de rob_field (campos ECP) que cuelgan de `canonical` en ese `nivel`.

    [2026-08-25] QV2-MAPA. Extraído para que el endpoint del mapa resuelva la MISMA
    jerarquía que el árbol — sin esto tendría que reconstruirla y las dos vistas podrían
    divergir. Reusa los índices que _cargar() ya construye (act_fields/ger_fields/vp_fields,
    :76-126), los mismos que consume _contar_pozos.

    set() vacío si el nivel no aplica o la tabla no está: el llamador omite el mapa.
    """
    try:
        data = _cargar()
    except Exception:
        return set()
    k = norm(canonical or "")
    if nivel == "campo":
        row = data["campo_row"].get(k) or {}
        rf = row.get("rob_field")
        return {rf} if rf else set()
    if nivel == "activo":
        return set(data["act_fields"].get(k, set()))
    if nivel == "gerencia":
        return set(data["ger_fields"].get(k, set()))
    if nivel == "vicepresidencia":
        return set(data["vp_fields"].get(k, set()))
    return set()          # operador y otros: sin mapa
```

> ⚠️ El executor debe **verificar la clave real** de `campo_row` leyendo `_cargar()`
> (~líneas 86-105) antes de dar por buena la rama `"campo"`. Si el campo guarda el
> `rob_field` con otro nombre, ajustar — no inventar.

### 2.4 MODIFICAR — `app/features/consulta_v2/api.py`: endpoint nuevo

**Añadir** al final del archivo, junto a los demás endpoints:

```python
@router.get("/pozos_geo")
def pozos_geo(entidad: str, nivel: str):
    """Puntos de los pozos de una entidad + contornos + contexto país, para el panel del
    mapa de Jerarquizar (QV2-MAPA).

    Las coordenadas salen YA corregidas y deduplicadas de pozos_geo.geo(): el frontend NO
    aplica ninguna regla geográfica (ver el docstring de pozos_geo).

    `disponible: False` cuando robustez_v02 no está (p.ej. el servidor 139): el frontend
    oculta el mapa y deja el árbol intacto — nunca un panel roto.
    """
    fields = respuesta_jerarquizar.rob_fields_de(nivel, entidad)
    g = _pozos_geo.geo(fields) if fields else None
    if g is None:
        return {"disponible": False}
    return {
        "disponible": True,
        "entidad": entidad,
        "nivel": nivel,
        "pozos": g["pozos"],
        "total": g["total"],              # UWI únicos del nivel (coincide con el pie del árbol)
        "ubicables": g["ubicables"],      # los que tienen coordenada usable
        "contornos": g["contornos"],      # {campo: [[lon,lat], ...]} — solo 15 campos lo tienen
        "campos": _pozos_geo.centroides(),  # contexto país (62 campos)
        "colombia": geo_colombia.CONTORNO,
    }
```

Y **añadir los imports** al principio del archivo, junto a los existentes:

```python
from app.features.consulta_v2 import pozos_geo as _pozos_geo
from app.features.consulta_v2 import geo_colombia
from app.features.consulta_v2 import respuesta_jerarquizar
```

> ⚠️ `respuesta_jerarquizar` puede estar ya importado — comprobarlo antes de duplicar.

### 2.5 NO tocar `_panel()` — el contrato ya sirve (H6)

`datos` ya lleva `entidad` y `nivel`, que es todo lo que el frontend necesita para pedir el
mapa. **No añadir campos al panel**: los puntos viajan por su propio endpoint, igual que
hace `cuant_dia_panel`.

---

### 2.6 🔴 MODIFICAR — `routes/api.py`: el proxy de Flask (fix de R1)

**BLOQUEANTE.** El navegador habla con Flask (8020), no con INGESTA (8088). Flask **no tiene
catch-all** para `/api/consulta2/*`: cada ruta se declara una por una. Sin esto el `fetch`
del frontend recibe **404** aunque el endpoint de INGESTA funcione.

**Localizar** el proxy `consulta2/golden` (~línea 784) y **añadir DESPUÉS**, antes del
siguiente `@api_bp.route` que no sea de consulta2:

```python
@api_bp.route("/consulta2/pozos_geo", methods=["GET"])
def consulta2_pozos_geo():
    """Proxy del mapa de pozos del panel de Jerarquizar (QV2-MAPA).

    GET con query params (entidad, nivel) → se reenvían con params=request.args, igual que
    consulta2/log. timeout=30: es SQL puro sobre robustez_v02, sin LLM de por medio.
    """
    try:
        resp = requests.get(f"{INGESTA_API_URL}/consulta2/pozos_geo",
                            params=request.args, timeout=30)
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": f"INGESTA no disponible: {e}"}), 502
```

> El patrón es copia literal de `consulta2/log` (:775-782), el único GET de este grupo —
> `params=request.args` es justo lo que lo distingue de los proxies POST.

---

## 3. Especificación — FRONTEND

### 3.1 MODIFICAR — `static/js/multitab_shell.js` · `__cnJerArbolHtml`

**Localizar** el `return` final de `__cnJerArbolHtml` (~línea 3960):

```js
    return '<div class="jq-tree" role="tree">' + html + '</div>' + __cnJerPieHtml(d.pozos);
```

**Sustituir por:**

```js
    // [2026-08-25] QV2-MAPA · dos columnas: árbol a la izquierda, mapa a la derecha.
    // El árbol se pinta YA (sus datos vienen en el panel); el mapa llega por fetch y se
    // rellena después — mismo patrón asíncrono que cuant_dia_panel (:3335/:3411).
    // El pie de "Pozos asociados" se MUEVE a la cabecera del mapa, donde tiene contexto.
    // Sin entidad/nivel no hay nada que pedir: se devuelve el árbol solo, como antes.
    // NO se comprueba `fuera_estructura`: esa rama tiene su propio return al principio de
    // la función (:3902) y nunca llega hasta aquí (R2). Un campo fuera de la estructura
    // económica no tiene rob_field, así que tampoco debe pedir mapa — ya queda correcto
    // por no tocar aquel return.
    var arbol = '<div class="jq-tree" role="tree">' + html + '</div>';
    if (!d.entidad || !d.nivel) {
      return arbol + __cnJerPieHtml(d.pozos);
    }
    return '<div class="jq-split">' +
        '<div class="jq-split__arbol">' + arbol + '</div>' +
        '<div class="jq-split__mapa jm" data-entidad="' + esc(d.entidad) + '"' +
             ' data-nivel="' + esc(d.nivel) + '">' +
          '<div class="jm__hd"><span class="jm__t">Ubicación en Colombia</span>' +
            '<span class="jm__zoom">' +
              '<button type="button" class="jm__zb is-on" data-z="pais">Colombia</button>' +
              '<button type="button" class="jm__zb" data-z="campo">Acercar</button>' +
            '</span></div>' +
          '<div class="jm__lienzo"><canvas class="jm__cv"></canvas>' +
            '<div class="jm__ctrl">' +
              '<button type="button" class="jm__zc" data-a="mas" title="Acercar">+</button>' +
              '<button type="button" class="jm__zc" data-a="menos" title="Alejar">−</button>' +
              '<span class="jm__pct">100%</span>' +
              '<button type="button" class="jm__zc" data-a="reset" title="Ver todo">⤢</button>' +
            '</div>' +
            '<div class="jm__tip"></div>' +
            '<div class="jm__carga">Cargando mapa…</div>' +
          '</div>' +
        '</div>' +
      '</div>';
```

### 3.2 AÑADIR — el módulo del mapa

**Insertar** el bloque completo justo ANTES de `__cnJerArbolHtml`. Es la traducción directa
de la maqueta aprobada; el executor debe copiarlo tal cual.

```js
  // ---------------------------------------------------------------------------
  // [2026-08-25] QV2-MAPA · Mapa de pozos del panel de Jerarquizar.
  // Traducción de la maqueta aprobada (artifact f0cee978). Canvas y no Plotly: son miles
  // de puntos y un scatter de Plotly con esa cardinalidad va notablemente más lento; el
  // dibujo aquí es un arc() por punto sin interacción por elemento.
  //
  // 🔒 El frontend NO aplica NINGUNA regla geográfica: los puntos llegan ya deduplicados
  //    (H1), con lon/lat ya corregidos (H2) y ya filtrados (H3) desde pozos_geo.py.
  // ---------------------------------------------------------------------------
  var __JM_MIN = 1, __JM_MAX = 14, __JM_MARGEN = 8;
  var __JM_DEF = 3.2;        // zoom de apertura: el campo y sus vecinos de cuenca
  var __jmCache = {};        // "entidad|nivel" -> payload del endpoint

  function __jmEstado(box) {
    // Cada mapa guarda su estado en el propio nodo: en la pila puede haber varios paneles
    // vivos a la vez y un estado global los mezclaría.
    if (!box.__jm) {
      box.__jm = {vista: "pais", d: null,
                  zoom: {pais: {k: 1, tx: 0, ty: 0}, campo: {k: 1, tx: 0, ty: 0}},
                  pintados: [], arrastre: null};
    }
    return box.__jm;
  }

  // Escala IGUAL en ambos ejes o la silueta sale deformada. El zoom se aplica DESPUÉS del
  // encuadre base y alrededor del centro, para que k=1 sea siempre la vista completa.
  function __jmProy(x0, x1, y0, y1, W, H, pad, z) {
    var ew = x1 - x0, eh = y1 - y0;
    var s = Math.min((W - pad * 2) / ew, (H - pad * 2) / eh);
    var ox = (W - ew * s) / 2, oy = (H - eh * s) / 2, cx = W / 2, cy = H / 2;
    return {
      k: z.k,
      X: function (lon) { return cx + ((ox + (lon - x0) * s) - cx) * z.k + z.tx; },
      Y: function (lat) { return cy + ((H - (oy + (lat - y0) * s)) - cy) * z.k + z.ty; }
    };
  }

  function __jmLienzo(box) {
    var cv = box.querySelector(".jm__cv"), host = box.querySelector(".jm__lienzo");
    var r = host.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
    var W = Math.max(10, r.width), H = Math.max(10, r.height);
    cv.width = W * dpr; cv.height = H * dpr;
    cv.style.width = W + "px"; cv.style.height = H + "px";
    var ctx = cv.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    return {ctx: ctx, W: W, H: H, cv: cv};
  }

  function __jmVar(v) {
    return getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  }

  function __jmPintaPais(box) {
    var st = __jmEstado(box), d = st.d, g = __jmLienzo(box), ctx = g.ctx;
    st.pintados = [];
    var COL = d.colombia, lons = [], lats = [];
    COL.forEach(function (p) { lons.push(p[0]); lats.push(p[1]); });
    var P = __jmProy(Math.min.apply(null, lons), Math.max.apply(null, lons),
                     Math.min.apply(null, lats), Math.max.apply(null, lats),
                     g.W, g.H, 14, st.zoom.pais);
    ctx.beginPath();
    COL.forEach(function (p, i) {
      i ? ctx.lineTo(P.X(p[0]), P.Y(p[1])) : ctx.moveTo(P.X(p[0]), P.Y(p[1]));
    });
    ctx.closePath();
    ctx.fillStyle = __jmVar("--rb-green-softer") || "#f1f9f4"; ctx.fill();
    // Contorno en verde oscuro (decisión del usuario): es el borde del país, la referencia
    // que ancla todo. El trazo NO escala con el zoom — a 10x taparía la costa.
    ctx.strokeStyle = __jmVar("--rb-green") || "#0e5c3a"; ctx.lineWidth = 1.6; ctx.stroke();

    var campos = d.campos || [], mx = 0;
    campos.forEach(function (c) { if (c.n > mx) mx = c.n; });
    var oro = __jmVar("--rb-chat-gold") || "#C9962E";
    var vd = __jmVar("--rb-green-mid") || "#15794c";
    var kr = Math.sqrt(P.k);   // radio amortiguado: lineal se comería el mapa al acercar
    var foco = __jmFoco(d);
    campos.forEach(function (c) {
      var es = (c.f === foco), rad = (2.2 + Math.sqrt(c.n / mx) * 9) * kr;
      var sx = P.X(c.lon), sy = P.Y(c.lat);
      st.pintados.push({sx: sx, sy: sy, r: Math.max(rad, 5),
                        txt: c.f + " · " + c.n.toLocaleString("es-CO") + " pozos"});
      ctx.beginPath(); ctx.arc(sx, sy, rad, 0, 6.2832);
      ctx.fillStyle = es ? oro : vd; ctx.globalAlpha = es ? 0.95 : 0.32; ctx.fill();
      ctx.globalAlpha = 1;
      // SOLO se rotula el campo consultado (decisión del usuario): en el Meta y el
      // Magdalena hay decenas de campos a pocos km y nombrarlos todos tapaba el que importa.
      if (es) {
        ctx.beginPath(); ctx.arc(sx, sy, rad + 4.5, 0, 6.2832);
        ctx.strokeStyle = oro; ctx.lineWidth = 1.6; ctx.stroke();
        ctx.font = '700 11.5px ui-monospace, Menlo, Consolas, monospace';
        ctx.textAlign = "center";
        ctx.lineWidth = 3.5; ctx.strokeStyle = "#f6f8f7";   // halo: cae sobre otros círculos
        ctx.strokeText(c.f, sx, sy - rad - 9);
        ctx.fillStyle = "#1A2A24"; ctx.fillText(c.f, sx, sy - rad - 9);
      }
    });
    box.querySelector(".jm__t").textContent =
      "Ubicación en Colombia · " + (d.total || 0).toLocaleString("es-CO") + " pozos";
  }

  // El campo a resaltar: si la entidad es un campo, ella misma; si es activo/gerencia/VP,
  // el de más pozos entre los suyos (los demás siguen visibles en verde).
  function __jmFoco(d) {
    if (d.nivel === "campo") return d.entidad;
    var mejor = null, n = -1, dentro = {};
    (d.pozos || []).forEach(function () {});   // los pozos no traen field: se usa contornos/campos
    (d.campos || []).forEach(function (c) { dentro[c.f] = c.n; });
    Object.keys(d.contornos || {}).forEach(function (f) {
      if (dentro[f] != null && dentro[f] > n) { n = dentro[f]; mejor = f; }
    });
    return mejor || d.entidad;
  }

  function __jmPintaCampo(box) {
    var st = __jmEstado(box), d = st.d, g = __jmLienzo(box), ctx = g.ctx;
    st.pintados = [];
    var pts = d.pozos || [], xs = [], ys = [];
    pts.forEach(function (p) { xs.push(p.lon); ys.push(p.lat); });
    var polys = [];
    Object.keys(d.contornos || {}).forEach(function (f) {
      polys.push(d.contornos[f]);
      d.contornos[f].forEach(function (v) { xs.push(v[0]); ys.push(v[1]); });
    });
    if (!xs.length) { box.querySelector(".jm__t").textContent = "Sin pozos ubicables"; return; }
    var x0 = Math.min.apply(null, xs), x1 = Math.max.apply(null, xs);
    var y0 = Math.min.apply(null, ys), y1 = Math.max.apply(null, ys);
    var mx = (x1 - x0) * 0.10 || 0.01, my = (y1 - y0) * 0.10 || 0.01;
    var P = __jmProy(x0 - mx, x1 + mx, y0 - my, y1 + my, g.W, g.H, 16, st.zoom.campo);

    polys.forEach(function (poly) {
      if (poly.length < 2) return;
      ctx.beginPath();
      poly.forEach(function (v, i) {
        i ? ctx.lineTo(P.X(v[0]), P.Y(v[1])) : ctx.moveTo(P.X(v[0]), P.Y(v[1]));
      });
      ctx.closePath();   // se cierra AQUÍ: 10 de los 15 polígonos no cierran en la BD (H7)
      ctx.fillStyle = __jmVar("--rb-green-soft") || "#e6f4ec";
      ctx.globalAlpha = 0.5; ctx.fill(); ctx.globalAlpha = 1;
      ctx.strokeStyle = __jmVar("--rb-green-mid") || "#15794c"; ctx.lineWidth = 1.4;
      ctx.setLineDash([5, 4]); ctx.stroke(); ctx.setLineDash([]);
    });
    // TODOS los puntos IGUALES (decisión del usuario): la tabla tiene grano de zona y 3.780
    // pozos aparecen ACT en una zona e INACT en otra — colorear exigiría una regla de
    // negocio que aún no está definida. Un pozo = un punto, sin afirmar de más.
    var rp = 3.1 * Math.sqrt(P.k);
    ctx.fillStyle = __jmVar("--rb-green-mid") || "#15794c"; ctx.globalAlpha = 0.82;
    pts.forEach(function (p) {
      var sx = P.X(p.lon), sy = P.Y(p.lat);
      st.pintados.push({sx: sx, sy: sy, r: Math.max(rp, 5), txt: p.uwi});
      ctx.beginPath(); ctx.arc(sx, sy, rp, 0, 6.2832); ctx.fill();
    });
    ctx.globalAlpha = 1;
    var sinC = polys.length ? "" : " · sin contorno";
    box.querySelector(".jm__t").textContent =
      pts.length.toLocaleString("es-CO") + " de " + (d.total || 0).toLocaleString("es-CO") +
      " pozos" + sinC;
  }

  function __jmPinta(box) {
    var st = __jmEstado(box);
    if (!st.d) return;
    (st.vista === "pais" ? __jmPintaPais : __jmPintaCampo)(box);
    __jmUI(box);
  }

  function __jmUI(box) {
    var st = __jmEstado(box), z = st.zoom[st.vista];
    var pct = box.querySelector(".jm__pct");
    if (pct) pct.textContent = Math.round(z.k * 100) + "%";
    box.querySelector(".jm__lienzo").style.cursor = z.k > 1 ? "grab" : "default";
  }

  // Encuadre de apertura: centrado y acercado sobre el campo consultado (decisión del
  // usuario). Se pinta una vez a k=1 para conocer su posición base y se resuelve el
  // desplazamiento que lo lleva al centro — así vale para cualquier campo, no solo dos.
  function __jmEncuadra(box) {
    var st = __jmEstado(box), z = st.zoom.pais;
    z.k = 1; z.tx = 0; z.ty = 0;
    __jmPintaPais(box);
    var foco = __jmFoco(st.d), mio = null;
    for (var i = 0; i < st.pintados.length; i++) {
      if (st.pintados[i].txt.indexOf(foco + " ·") === 0) { mio = st.pintados[i]; break; }
    }
    if (!mio) return;
    var r = box.querySelector(".jm__cv").getBoundingClientRect();
    z.k = __JM_DEF;
    z.tx = -(mio.sx - r.width / 2) * __JM_DEF;
    z.ty = -(mio.sy - r.height / 2) * __JM_DEF;
  }

  function __jmZoom(box, nk, px, py) {
    var st = __jmEstado(box), z = st.zoom[st.vista];
    nk = Math.max(__JM_MIN, Math.min(__JM_MAX, nk));
    if (nk === z.k) return;
    if (px != null) {
      // El punto bajo el cursor se queda QUIETO. La proyección escala respecto al CENTRO:
      //   S = c + (B-c)*k + t   =>   t' = t + (S - c - t)*(1 - k'/k)
      // Compensar sobre el origen en vez del centro desplaza el mapa (verificado).
      var r = box.querySelector(".jm__cv").getBoundingClientRect();
      var f = 1 - nk / z.k;
      z.tx += (px - r.width / 2 - z.tx) * f;
      z.ty += (py - r.height / 2 - z.ty) * f;
    }
    z.k = nk;
    if (z.k === 1) { z.tx = 0; z.ty = 0; }
    __jmPinta(box);
  }

  // Carga asíncrona: mismo patrón que __cnCompProdCargar (H4).
  function __cnJerMapaCargar(blk) {
    var box = blk.querySelector(".jm");
    if (!box) return;
    var ent = box.getAttribute("data-entidad"), niv = box.getAttribute("data-nivel");
    var key = ent + "|" + niv;
    var carga = box.querySelector(".jm__carga");
    var p = __jmCache[key] ? Promise.resolve(__jmCache[key]) :
      fetch("/api/consulta2/pozos_geo?entidad=" + encodeURIComponent(ent) +
            "&nivel=" + encodeURIComponent(niv))
        .then(function (r) { return r.json(); })
        .then(function (d) { if (d && d.disponible) __jmCache[key] = d; return d; });
    p.then(function (d) {
      if (!d || !d.disponible || !(d.pozos || []).length) {
        // Degradación con gracia: sin robustez_v02 o sin pozos ubicables se retira el mapa
        // y el árbol se queda con todo el ancho. NUNCA un panel roto.
        var split = blk.querySelector(".jq-split");
        if (split) split.classList.add("is-solo");
        return;
      }
      var st = __jmEstado(box);
      st.d = d;
      if (carga) carga.remove();
      __jmEncuadra(box);
      __jmPinta(box);
    }).catch(function () {
      var split = blk.querySelector(".jq-split");
      if (split) split.classList.add("is-solo");
    });
  }
```

### 3.3 AÑADIR — los eventos (delegados)

**Insertar** después del bloque anterior. Delegación en `document`: los paneles se crean y
destruyen con la pila, así que un listener por nodo se perdería.

```js
  // Delegación en document (los paneles nacen y mueren con la pila; un listener por nodo
  // moriría con él). Todos los handlers salen si el clic no cae dentro de un .jm.
  document.addEventListener("click", function (e) {
    var t = e.target;
    if (!t || typeof t.closest !== "function") return;
    var box = t.closest(".jm");
    if (!box) return;
    var zb = t.closest(".jm__zb");
    if (zb) {
      box.querySelectorAll(".jm__zb").forEach(function (o) { o.classList.remove("is-on"); });
      zb.classList.add("is-on");
      var st = __jmEstado(box);
      st.vista = zb.getAttribute("data-z");
      // Volver a "Colombia" reencuadra sobre el campo, igual que al abrir: devolver el país
      // entero obligaría a buscar el punto otra vez.
      if (st.vista === "pais") __jmEncuadra(box);
      __jmPinta(box);
      return;
    }
    var zc = t.closest(".jm__zc");
    if (zc) {
      var a = zc.getAttribute("data-a"), s2 = __jmEstado(box), z = s2.zoom[s2.vista];
      var r = box.querySelector(".jm__cv").getBoundingClientRect();
      if (a === "reset") { s2.zoom[s2.vista] = {k: 1, tx: 0, ty: 0}; __jmPinta(box); }
      else __jmZoom(box, z.k * (a === "mas" ? 1.5 : 1 / 1.5), r.width / 2, r.height / 2);
    }
  });

  document.addEventListener("wheel", function (e) {
    var t = e.target;
    if (!t || typeof t.closest !== "function") return;
    var box = t.closest(".jm__lienzo");
    if (!box) return;
    box = box.closest(".jm");
    if (!box || !__jmEstado(box).d) return;
    e.preventDefault();
    var r = box.querySelector(".jm__cv").getBoundingClientRect();
    __jmZoom(box, __jmEstado(box).zoom[__jmEstado(box).vista].k * (e.deltaY < 0 ? 1.18 : 1 / 1.18),
             e.clientX - r.left, e.clientY - r.top);
  }, {passive: false});

  document.addEventListener("mousedown", function (e) {
    var t = e.target;
    if (!t || typeof t.closest !== "function") return;
    var box = t.closest(".jm");
    if (!box || t.closest(".jm__zc") || t.closest(".jm__zb")) return;
    var st = __jmEstado(box);
    if (st.zoom[st.vista].k <= 1) return;
    st.arrastre = {x: e.clientX, y: e.clientY,
                   tx: st.zoom[st.vista].tx, ty: st.zoom[st.vista].ty};
    box.querySelector(".jm__lienzo").style.cursor = "grabbing";
    e.preventDefault();
  });

  document.addEventListener("mousemove", function (e) {
    var t = e.target;
    if (!t || typeof t.closest !== "function") return;
    var box = t.closest(".jm");
    if (!box) return;
    var st = __jmEstado(box);
    if (!st.d) return;
    if (st.arrastre) {
      var z = st.zoom[st.vista];
      z.tx = st.arrastre.tx + (e.clientX - st.arrastre.x);
      z.ty = st.arrastre.ty + (e.clientY - st.arrastre.y);
      box.querySelector(".jm__tip").classList.remove("is-on");
      __jmPinta(box);
      return;
    }
    var r = box.querySelector(".jm__cv").getBoundingClientRect();
    var mx = e.clientX - r.left, my = e.clientY - r.top, best = null, bd = Infinity;
    for (var i = 0; i < st.pintados.length; i++) {
      var p = st.pintados[i], dx = p.sx - mx, dy = p.sy - my, d2 = dx * dx + dy * dy;
      if (d2 < p.r * p.r * 2.6 && d2 < bd) { bd = d2; best = p; }
    }
    var tip = box.querySelector(".jm__tip");
    if (best) {
      tip.textContent = best.txt;
      tip.style.left = best.sx + "px"; tip.style.top = best.sy + "px";
      tip.classList.add("is-on");
    } else tip.classList.remove("is-on");
  });

  document.addEventListener("mouseup", function () {
    document.querySelectorAll(".jm").forEach(function (box) {
      var st = box.__jm;
      if (!st || !st.arrastre) return;
      st.arrastre = null;
      box.querySelector(".jm__lienzo").style.cursor = st.zoom[st.vista].k > 1 ? "grab" : "default";
    });
  });

  var __jmTmr = null;
  window.addEventListener("resize", function () {
    clearTimeout(__jmTmr);
    __jmTmr = setTimeout(function () {
      document.querySelectorAll(".jm").forEach(function (box) {
        if (box.__jm && box.__jm.d) __jmPinta(box);
      });
    }, 140);
  });
```

### 3.4 MODIFICAR — disparar la carga tras insertar el bloque

**Localizar** la línea 3411 (el disparo gemelo de `cuant_dia_panel`):

```js
    if (panel.tipo === "cuant_dia_panel") __cnCompProdCargar(blk, d, "-stk" + __cnStackSeq);
```

**Añadir justo debajo:**

```js
    // [2026-08-25] QV2-MAPA · mismo patrón: el árbol ya está pintado y el mapa se rellena
    // después, sin bloquearlo.
    if (panel.tipo === "jerarq_arbol") __cnJerMapaCargar(blk);
```

### 3.5 AÑADIR — CSS en `static/css/colapsable.css`

**Insertar** después del bloque `.jq-*` existente (~línea 2305, tras `.jq-tree--deep`):

```css
/* ============================================================
   [2026-08-25] QV2-MAPA · Jerarquizar en dos columnas: árbol + mapa
   ============================================================ */
/* La altura NO se fija aquí: la manda el ÁRBOL, que es de alto natural. El mapa se estira
   a esa altura con align-items:stretch. Si el árbol crece (una VP lista más hijos), el
   mapa crece con él — sin número mágico que mantener. */
.jq-split { display: flex; align-items: stretch; gap: 0; }
.jq-split__arbol { flex: 0 0 auto; min-width: 0; padding-right: 12px; }
.jq-split__mapa { flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column;
  border-left: 1px solid var(--rb-border,#e3e8e5); background: #f6f8f7;
  border-radius: 0 8px 8px 0; overflow: hidden; }
/* Degradación: sin mapa disponible el árbol se queda con todo el ancho (nunca un hueco). */
.jq-split.is-solo .jq-split__mapa { display: none; }
.jq-split.is-solo .jq-split__arbol { flex: 1 1 auto; padding-right: 0; }

.jm__hd { flex: 0 0 auto; display: flex; align-items: center; gap: 8px; padding: 6px 12px;
  border-bottom: 1px solid var(--rb-border,#e3e8e5); }
.jm__t { flex: 1 1 auto; min-width: 0; font-size: 11.5px; font-weight: 600;
  letter-spacing: .05em; text-transform: uppercase; color: #6E7C75;
  font-family: ui-monospace, Menlo, Consolas, monospace;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.jm__zoom { flex: 0 0 auto; display: inline-flex; border: 1px solid var(--rb-border,#e3e8e5);
  border-radius: 7px; overflow: hidden; }
.jm__zb { font: inherit; font-size: 11px; font-weight: 600; color: #6E7C75; background: #fff;
  border: 0; padding: 4px 10px; cursor: pointer; }
.jm__zb + .jm__zb { border-left: 1px solid var(--rb-border,#e3e8e5); }
.jm__zb:hover { color: #2f4a3d; }
.jm__zb.is-on { background: var(--rb-green,#0e5c3a); color: #fff; }
.jm__zb:focus-visible { outline: 2px solid var(--rb-green-mid,#15794c); outline-offset: -2px; }

/* overflow:hidden — sin esto el canvas se desborda del panel al hacer zoom.
   min-height:0 — un ítem flex no encoge por debajo de su contenido sin esto, y el
   canvas ampliado estiraría el panel entero. */
.jm__lienzo { flex: 1 1 auto; position: relative; min-height: 0; overflow: hidden; }
.jm__cv { display: block; width: 100%; height: 100%; }
.jm__carga { position: absolute; inset: 0; display: grid; place-items: center;
  font-size: 12px; color: #8a968f; }

.jm__ctrl { position: absolute; top: 8px; right: 8px; display: flex; flex-direction: column;
  border: 1px solid var(--rb-border,#e3e8e5); border-radius: 8px; overflow: hidden;
  background: #fff; box-shadow: 0 1px 4px rgb(16 40 30 / 10%); z-index: 4; }
.jm__zc { width: 26px; height: 24px; border: 0; background: #fff; color: #3C4A44;
  font: 600 13px/1 inherit; cursor: pointer; display: grid; place-items: center; padding: 0; }
.jm__zc + .jm__zc, .jm__pct + .jm__zc { border-top: 1px solid var(--rb-border,#e3e8e5); }
.jm__zc:hover { background: var(--rb-green-softer,#f1f9f4); color: var(--rb-green,#0e5c3a); }
.jm__zc:focus-visible { outline: 2px solid var(--rb-green-mid,#15794c); outline-offset: -2px; }
.jm__pct { border-top: 1px solid var(--rb-border,#e3e8e5); font-size: 8.5px; font-weight: 600;
  color: #8a968f; text-align: center; padding: 3px 0;
  font-family: ui-monospace, Menlo, Consolas, monospace; font-variant-numeric: tabular-nums; }

.jm__tip { position: absolute; pointer-events: none; opacity: 0; transition: opacity .12s;
  background: #1A2A24; color: #fff; font-size: 11px; padding: 4px 7px; border-radius: 5px;
  font-family: ui-monospace, Menlo, Consolas, monospace; white-space: nowrap; z-index: 5;
  transform: translate(-50%,-140%); }
.jm__tip.is-on { opacity: 1; }

/* Móvil / panel estrecho: las dos mitades se apilan y el mapa toma altura propia. */
@media (max-width: 720px) {
  .jq-split { flex-direction: column; }
  .jq-split__arbol { padding-right: 0; padding-bottom: 10px; }
  .jq-split__mapa { border-left: 0; border-top: 1px solid var(--rb-border,#e3e8e5);
    border-radius: 0 0 8px 8px; min-height: 240px; }
}
@media (prefers-reduced-motion: reduce) { .jm__tip { transition: none; } }
```

---

## 4. Orden de ejecución

| # | Acción | Archivo | § |
|---|---|---|---|
| 1 | Crear `geo_colombia.py` | `consulta_v2/geo_colombia.py` | 2.2 |
| 2 | Crear `pozos_geo.py` | `consulta_v2/pozos_geo.py` | 2.1 |
| 3 | Añadir `rob_fields_de()` | `consulta_v2/respuesta_jerarquizar.py` | 2.3 |
| 4 | Endpoint `/pozos_geo` + imports | `consulta_v2/api.py` | 2.4 |
| 5 | **🔴 Proxy de Flask** (sin esto el fetch da 404) | `routes/api.py` | 2.6 |
| 6 | **Probar los DOS puertos** (§6.1) antes de tocar el frontend | — | — |
| 7 | CSS | `static/css/colapsable.css` | 3.5 |
| 8 | Módulo del mapa (`__jm*`) | `static/js/multitab_shell.js` | 3.2 |
| 9 | Eventos delegados | `static/js/multitab_shell.js` | 3.3 |
| 10 | Reescribir el `return` de `__cnJerArbolHtml` | `static/js/multitab_shell.js` | 3.1 |
| 11 | Disparo tras insertar el bloque | `static/js/multitab_shell.js` | 3.4 |
| 12 | Validar (§6) | — | — |

> El backend va **entero antes** que el frontend: así el paso 6 verifica el contrato con
> datos reales, y el JS se escribe contra algo que ya se sabe que responde.
> Dentro del JS, las funciones (7-8) van antes de los call sites (9-10).

---

## 5. Reglas no negociables

1. **`DISTINCT ON (uwi)` / `COUNT(DISTINCT uwi)` siempre** (H1). Contar filas infla ×3.
2. **La corrección de coordenadas vive SOLO en `pozos_geo.py`** (H2). El frontend no aplica
   ninguna regla geográfica.
3. **NO colorear los pozos por estado** — todos iguales (decisión del usuario, ver §7/R5).
4. **NO tocar el contrato del panel** (`_panel()`): `entidad` y `nivel` ya viajan (H6).
5. **NO tocar `__cnJerOperadorHtml` ni `__cnJerRankHtml`**: el mapa es solo para
   `jerarq_arbol`.
6. **Degradación con gracia:** sin `robustez_v02`, sin `rob_fields` o sin pozos ubicables →
   `disponible:false` y el árbol se queda solo, a ancho completo. Nunca un panel roto ni una
   excepción que tumbe la respuesta.
7. **JS ES5** (`var` + `function`), **Python con SQLAlchemy Core**.
8. **Altura:** el CSS NO fija altura al panel — la manda el árbol (`align-items:stretch`).
9. Todo comentario **en español**.
10. **El proxy de Flask NO es opcional** (R1): Flask no tiene catch-all para
   `/api/consulta2/*`. Sin la ruta nueva, el mapa da 404 aunque INGESTA responda.
11. **Prefijos `.jm*` / `.jq-split` y `__jm*`** — verificado que están libres. No usar
   `cn-*`, que es el namespace del resto del shell.
12. Si algo del plan no calza con el código real → **DETENERSE** y reportar, no improvisar.

---

## 6. Validación

### 6.1 Backend — con los backends ARRANCADOS · probar LOS DOS puertos (R1)

> ⚠️ **NO medir llamando a las funciones del endpoint en proceso**: los defaults
> `Query(...)` de FastAPI falsean el resultado. Se prueba por HTTP.

```powershell
# 0. 🔴 EL PROXY (8020) — es el que usa el navegador. Si este falla, falta la §2.6.
Invoke-RestMethod "http://localhost:8020/api/consulta2/pozos_geo?entidad=CASTILLA&nivel=campo" |
  Select-Object disponible,total,ubicables

# 1. Campo con contorno (directo a INGESTA)
Invoke-RestMethod "http://localhost:8088/consulta2/pozos_geo?entidad=CHICHIMENE&nivel=campo" |
  Select-Object disponible,total,ubicables

# 2. Campo SIN contorno
Invoke-RestMethod "http://localhost:8088/consulta2/pozos_geo?entidad=CASTILLA&nivel=campo" |
  Select-Object disponible,total,ubicables

# 3. Nivel superior (agrega varios campos)
Invoke-RestMethod "http://localhost:8088/consulta2/pozos_geo?entidad=PPC&nivel=gerencia" |
  Select-Object disponible,total,ubicables
```

| Verificación | Esperado |
|---|---|
| CHICHIMENE · `total` | **213** — igual que el pie del árbol |
| CHICHIMENE · `ubicables` | **212** |
| CHICHIMENE · `contornos` | 1 clave, con 104 vértices |
| CASTILLA · `total` | **437** — igual que el pie del árbol |
| CASTILLA · `ubicables` | **423** |
| CASTILLA · `contornos` | `{}` vacío |
| `campos` (todas) | 62 elementos |
| `colombia` | 108 vértices |
| Coordenadas | `lon` ≈ −73,6 y `lat` ≈ 3,9 — **si salen al revés, H2 está mal aplicado** |

> 🔴 **Dos criterios de fallo. Cualquiera de ellos = DETENERSE:**
> 1. Si `total` no coincide con el número del pie del árbol («Pozos asociados»), la
>    deduplicación está mal (H1).
> 2. Si el **puerto 8020 da 404** y el 8088 responde, falta el proxy de la §2.6 (R1).

### 6.2 Frontend ⏳ PENDIENTE DE VALIDACIÓN HUMANA

Es un cambio visual e interactivo: **no hay test automático que lo cubra**, y aplica la
regla del proyecto «build verde ≠ feature verificada». Al terminar, el estado correcto es
**«implementado, pendiente de validación humana»**.

Reiniciar backends, abrir `http://localhost:8020/mainchat` → pestaña **Consulta**:

1. «¿qué es CASTILLA?» → árbol a la izquierda **y mapa a la derecha**.
2. El mapa abre **centrado y acercado** sobre CASTILLA, con su nombre rotulado.
3. **Solo CASTILLA lleva nombre**; los demás círculos, sin rótulo.
4. El contorno del país se ve en **verde oscuro**.
5. El panel **mide lo que el árbol** — sin hueco muerto debajo ni desborde.
6. Zoom: rueda, arrastre, `+`/`−`, `⤢` (vuelve a Colombia entera), y el punto bajo el cursor
   **no se mueve** al girar la rueda.
7. «Acercar» → un punto por pozo, **todos del mismo color**. En CASTILLA el título dice
   «423 de 437 pozos · sin contorno».
8. «¿qué es CHICHIMENE?» → en «Acercar» **sí se ve el polígono** del campo.
9. Hover sobre un pozo → su UWI; sobre un círculo en vista país → campo y nº de pozos.
10. **Varios paneles en la pila:** preguntar por 2-3 entidades seguidas y comprobar que cada
    mapa mantiene **su propio zoom** (el estado vive en el nodo, no en una global).
11. «¿qué es POE?» (gerencia) → el mapa agrega los pozos de sus campos.
12. **F12 → Console:** 0 errores.

---

## 7. Fuera de alcance y decisiones pendientes

- **🔴 R5 · Color por estado del pozo — NO entra.** Decisión del usuario. La razón:
  `wells_attributes` tiene grano de zona y **3.780 UWI aparecen ACT en una zona e INACT en
  otra** (p. ej. `ABAN0022` → 2 ACT, 1 INACT). Colorear exigiría decidir qué estado gana
  —prioridad ACT, zona más reciente, zona principal— y eso es una **regla de negocio sin
  definir**. Retomar en una segunda fase, con el criterio acordado por escrito.
- **🔴 R4 · LA CIRA e INFANTAS mal ubicados (H8).** Hay que verificarlo contra la fuente
  **antes de publicar el panel a usuarios**, o esos dos campos mostrarán una ubicación falsa
  con la autoridad de un mapa. No lo arregla este plan: si el dato está mal en origen, el
  arreglo va en la ingesta.
- **R1 · Coordenada de superficie vacía.** Se pinta el fondo del pozo. Si el Excel de V01 sí
  la trae, el arreglo va en la carga, no aquí.
- **Contorno oficial del país.** El de `geo_colombia.py` es aproximado (108 vértices). Para
  producción: GeoJSON del IGAC o `scattergeo` de Plotly.
- **Rendimiento: medido, NO es un riesgo (R4).** La VP con más campos (GPA, 27 `rob_field`)
  agrega **1.118 pozos únicos** — Canvas los dibuja sin problema. Y el árbol más alto (GAA)
  ocupa ~825px, no los 1419 teóricos (R3). Si el catálogo creciera mucho, la salida sería
  agregar por campo a nivel VP; hoy no hace falta.
- **Navegación por teclado dentro del mapa.** No la tiene el waffle existente del proyecto;
  queda como deuda simétrica.
