# Plan ejecutable — Fase 3 · Ejecución conversacional (DETERMINISTA, sin LLM) · **v2 (auditado)**

> **Cobertura: entrada 1 intent resuelto → salida 1 respuesta numérica.** Feature `consulta`.
> Este plan lo ejecuta un agente externo sin contexto previo. Rutas absolutas, código completo,
> decisiones cerradas. Al terminar: correr las Validaciones y reportar tabla PASS/FAIL.
> **v2** incorpora los hallazgos de auditoría F1–F8 (§0). NO commitear (lo hace el usuario).

---

## 0. Auditoría previa — hallazgos incorporados (§0.2 del CLAUDE.md)

| # | Severidad | Hallazgo | Resolución en este plan |
|---|-----------|----------|-------------------------|
| **F1** | 🔴 crítico | `desempeno` es un route handler (`@router.get`, con `segmento: str = Query("ecp")`). Llamarlo como `desempeno(entidad=X)` deja `segmento` como **objeto `Query`**, no `"ecp"`. | `ejecutar()` llama **siempre** `fn(entidad=…, segmento="ecp")` (explícito). Comentado en el código. |
| **F2** | 🟠 alto | La edición frontend original reintroducía la línea `<ul class="rb-chat__options">` que **ya existe** (línea 1936) → duplicación → render roto. | A4 reescrito: **reemplazo de UN solo fragmento** (el `<p>` placeholder). |
| **F3** | 🟠 alto | Con `segmento="ecp"` explícito, los fakes del test deben aceptar ese kwarg o dan `TypeError`. | Fakes con firma `(entidad=None, segmento="ecp", **_)`. |
| **F4** | 🟡 medio | `if not filas` era código muerto: `desempeno` siempre devuelve los 3 productos (en ceros). | Sustituido por chequeo honesto `real==0 and ppto==0` → "no reporta {producto}". |
| **F5** | 🟡 medio | `_estado(None)` → `""`, etiquetado "sin cierre" (confuso; es "sin meta/PPTO"). | Mapa `""→"sin meta"`. |
| **F6** | 🟡 medio | `agregacion` (promedio/acumulado) se extrae pero se ignora → engaña si piden "promedio diario". | Aviso honesto (el slot ya se copia al intent). |
| **F7** | 🟢 bajo | `try/except` en `_salida` oculta la causa si `ejecutar` falla → V3 fallaría en silencio. | El `except` **loguea el traceback** (`logging`), y degrada a `{aplica:false}`. |
| **F8** | ✅ verificado | Importar `analisis.api` desde `ejecucion.py`: **no** llama `get_settings()` a nivel módulo (todas lazy, líneas 581+), **no** abre BD (engine lazy), **no** hay ciclo (analisis no importa consulta). | Import directo es seguro; la recolección de tests no necesita `.env`. |

**Nota de arquitectura (deuda documentada, NO se ejecuta aquí):** reusar el route handler `desempeno()`
como función es un anti-patrón menor (defaults `Query`). La limpieza correcta —extraer el cálculo a un
helper `_desempeno_ecp(entidad)` que compartan endpoint y `ejecucion.py`— se **difiere** a una iteración
posterior para no tocar el endpoint del tablero en esta fase. Con `segmento="ecp"` explícito la llamada
directa es **segura hoy** (el único otro parámetro es `segmento`).

---

## 1. Contexto

La pestaña **Consulta** hoy hace slot-filling y **para en el intent validado** (D1): resuelve la entidad,
arma la huella y muestra la tarjeta «Entidad identificada» con acciones *placeholder*. El chat **entiende**
la pregunta pero **no entrega el número**.

El tablero **«Desempeño del mes»** (`GET /analisis/desempeno`) ya calcula, 100% determinista, la cifra
**REAL vs PPTO por producto** de cualquier entidad ECP para el último mes con dato. Ese endpoint es el
**motor de cálculo** que esta fase reutiliza → **coherencia chat↔tablero por construcción**.

**Enfoque acordado:** determinista primero (validar resultados); Gemma se involucra **después** (iteración
2, detrás de flag). Esta fase **no usa LLM**.

---

## 2. Objetivo (medible)

Dado un intent `completo` de **rama A (ECP)**:

1. `POST /consulta/preguntar` (o `/responder`) devuelve, además de `intent`+`huella`, el campo nuevo
   **`respuesta`** con la cifra REAL vs PPTO del mes por defecto.
2. Intent con **producto** (`aceite→CRUDO`/`gas`/`blancos`) → 1 cifra; sin producto → las 3.
3. `agua` → rechazo honesto. **Rama B (filial)** → mensaje honesto, no calcula.
4. El frontend pinta la respuesta como burbuja del bot, **reemplazando** el placeholder actual.
5. **Sin LLM.** Prosa 100% plantilla.

---

## 3. Decisiones cerradas

| ID | Decisión |
|----|----------|
| **D-F3-1** | Cifra **REAL vs PPTO por producto**, entidad resuelta, **mes por defecto** (último con dato = el del tablero). |
| **D-F3-2** | Solo **rama A (ECP)**. **Rama B (filial)** → mensaje honesto, no calcula (otra fuente + meta PROGRAMA → iter. 2). |
| **D-F3-3** | Producto: con producto → 1 cifra; sin producto → 3. `agua` → rechazo. |
| **D-F3-4** | Periodo: iter. 1 responde **siempre el mes por defecto**; periodo ≠ «este mes» → **aviso honesto**. YTD/mes cerrado/rango = fuera de alcance. |
| **D-F3-5** | **Sin LLM.** Plantilla determinista. Hook Gemma documentado y apagado (iter. 2). |
| **D-F3-6** | La respuesta viaja en el response de `/consulta/*` como `respuesta` (aditivo). Sin endpoint nuevo. |
| **D-F3-7** | Reusar `desempeno()` **verbatim** (con `segmento="ecp"`) → coherencia con el tablero. La limitación de identidad dual se hereda del tablero y se corrige en ambos a la vez, más adelante. |

---

## 4. Prerequisitos

- Backend INGESTA: `cd INGESTA\Rep_Prod\backend; uv run uvicorn app.main:app --port 8088 --reload`.
- PostgreSQL `daily_report_prod` con datos. Verificar: `GET http://localhost:8088/analisis/desempeno?entidad=RUBIALES` responde con `por_producto`.
- Ollama **NO** se usa en esta fase.

---

## 5. Inventario de archivos

Raíz = `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA`.

| # | Archivo | Acción |
|---|---------|--------|
| A1 | `INGESTA\Rep_Prod\backend\app\features\consulta\ejecucion.py` | **NUEVO** — motor `ejecutar()`. |
| A2 | `INGESTA\Rep_Prod\backend\app\features\consulta\maquina.py` | **EDIT** — copiar `producto`/`periodo`; llamar `ejecutar()` en `_salida`. |
| A3 | `INGESTA\Rep_Prod\backend\tests\test_consulta_ejecucion.py` | **NUEVO** — unit tests con `desempeno` inyectado (sin BD). |
| A4 | `static\js\multitab_shell.js` | **EDIT** — pintar `d.respuesta` (rama `completo` de `__cnRender`). |
| A5 | `static\css\colapsable.css` | **EDIT** — estilos `.cn-answer*`. |
| A6 | `templates\main.html` | **EDIT** — cache-buster `?v=`. |

**Prohibido editar:** `extraccion.py`, `resolver.py`, `analisis\api.py`, `routes\api.py`.

---

## 6. Especificación

### A1 — NUEVO `ejecucion.py`

Crear `INGESTA\Rep_Prod\backend\app\features\consulta\ejecucion.py` con **exactamente** esto:

```python
"""Fase 3 · Ejecución conversacional (DETERMINISTA, sin LLM).

Toma el intent resuelto (entidad rama A + producto/periodo/agregacion opcionales) y devuelve la cifra
REAL vs PPTO del mes, REUSANDO el mismo cálculo que alimenta el tablero 'Desempeño del mes'
(analisis.api.desempeno) -> coherencia chat<->tablero por construcción.

Frontera: aquí NO interviene el LLM. La prosa es 100% plantilla. El pulido con Gemma es iteración
posterior (irá detrás de un flag, igual que EJECUTIVO_USAR_LLM).
"""
from app.features.analisis.api import desempeno as _desempeno_ep, _estado

# intent.producto (extraído+groundeado por el LLM, minúsculas) -> producto del cálculo mensual.
# 'agua' NO existe a grano ECP (dim_tipo_producto solo CRUDO/GAS/BLANCOS) -> se rechaza.
_PROD_MAP = {"aceite": "CRUDO", "gas": "GAS", "blancos": "BLANCOS"}
_ESTADO_LABEL = {"ok": "Alineado", "warn": "Rezagado", "alert": "Foco", "": "sin meta"}
_PERIODO_DEFAULT = {"este mes", "mes actual", "el mes", "este mes en curso", "mes en curso"}


def _fmt(n):
    try:
        return f"{float(n):,.0f}".replace(",", ".")
    except Exception:
        return str(n)


def _linea(p):
    est_key = _estado(p["cumplimiento"])          # MISMA umbralización del tablero (ok/warn/alert/"")
    est = _ESTADO_LABEL.get(est_key, "")
    pct = f"{p['cumplimiento']}%" if p["cumplimiento"] is not None else "s/d"
    return {
        "producto": p["producto"],
        "real": p["real"],
        "cumplimiento": p["cumplimiento"],
        "estado": est,
        "texto": f"{p['producto']}: {_fmt(p['real'])} · {pct} del presupuesto ({est})",
    }


def ejecutar(resuelta: dict, producto: str | None, periodo: str | None,
             agregacion: str | None = None, _desempeno_fn=None) -> dict:
    """resuelta = {nivel, rama, valor}. Devuelve {aplica, texto|(encabezado,lineas,pie,avisos)}.
    _desempeno_fn: inyección para tests (evita la BD)."""
    fn = _desempeno_fn or _desempeno_ep

    # 1) Rama B (filial consolidada): otra fuente + meta PROGRAMA -> iteración 2.
    if resuelta.get("rama") == "B":
        return {"aplica": False,
                "texto": "Por ahora respondo entidades ECP (campo, pozo, gerencia, activo, área, "
                         "vicepresidencia). La cifra consolidada de una filial llega en la próxima iteración."}

    # 2) agua explícita -> rechazo honesto
    if producto == "agua":
        return {"aplica": False,
                "texto": "El agua no se reporta a grano diario ECP (solo crudo, gas y blancos). "
                         "¿Quieres crudo, gas o blancos?"}

    # 3) cálculo REUSANDO el del tablero. segmento='ecp' EXPLÍCITO (F1: desempeno es un route handler;
    #    sin pasarlo, 'segmento' sería un objeto Query, no la cadena "ecp").
    d = fn(entidad=resuelta["valor"], segmento="ecp")
    if not d.get("encontrada") or d.get("sin_datos"):
        return {"aplica": False, "texto": f"No tengo datos de producción para «{resuelta['valor']}»."}
    if d.get("sin_cierre"):
        return {"aplica": False,
                "texto": f"«{resuelta['valor']}» aún no tiene cierre mensual (REAL/PPTO) para el mes en curso."}

    mes = d["mes"]
    quiero = _PROD_MAP.get(producto)                       # None si no se pidió producto -> los 3
    filas = [p for p in d["por_producto"] if (quiero is None or p["producto"] == quiero)]

    # F4: producto pedido que la entidad NO reporta (real y ppto en 0) -> honesto, no "0 · s/d".
    if quiero and filas and filas[0]["real"] == 0 and filas[0]["ppto"] == 0:
        return {"aplica": False,
                "texto": f"«{resuelta['valor']}» no reporta {producto} en el mes en curso."}

    lineas = [_linea(p) for p in filas]

    avisos = []
    if periodo and periodo.strip().lower() not in _PERIODO_DEFAULT:
        avisos.append("Por ahora respondo el mes en curso; los periodos históricos llegan en una próxima iteración.")
    if agregacion == "promedio_diario":                    # F6: honesto si pidieron promedio
        avisos.append("Te doy el volumen del mes; el promedio diario llega en una próxima iteración.")

    corte = f"corte {mes['dias_con_data']}/{mes['dias_del_mes']}" if not mes["completo"] else "mes cerrado"
    return {
        "aplica": True,
        "entidad": resuelta["valor"],
        "nivel": resuelta.get("nivel"),
        "mes": mes,
        "encabezado": f"{resuelta['valor']} · {mes['nombre']} {mes['anio']} · {corte}",
        "lineas": lineas,
        "avisos": avisos,
        "pie": (f"Calculado sobre {mes['dias_con_data']} días con reporte."
                if mes["dias_con_data"] else "Cifra de cierre mensual (sin curva diaria)."),
    }
```

> `_estado` está a nivel módulo en `analisis\api.py` (línea 478); importarla asegura los **mismos umbrales**
> del tablero (≥90 ok / ≥75 warn / <75 alert). Verificado F8: el import no requiere `.env` ni abre BD.

### A2 — EDIT `maquina.py` (3 ediciones)

**Edición 1 — copiar `producto`/`periodo` del slot.** Reemplazar `_nuevo_intent` (líneas 38-42):
```python
def _nuevo_intent(slots):
    return {"status": "pendiente",
            "entidad": {"texto": slots.get("entidad"), "resuelta": None},
            "producto": None, "periodo": None, "agregacion": slots.get("agregacion"),
            "pendiente": None, "avisos": [], "_slots": slots}
```
por:
```python
def _nuevo_intent(slots):
    return {"status": "pendiente",
            "entidad": {"texto": slots.get("entidad"), "resuelta": None},
            "producto": slots.get("producto"), "periodo": slots.get("periodo"),
            "agregacion": slots.get("agregacion"),
            "pendiente": None, "avisos": [], "_slots": slots}
```

**Edición 2 — imports.** En la cabecera (líneas 1-4), añadir tras el import del resolver:
```python
import logging
from app.features.consulta.ejecucion import ejecutar
```

**Edición 3 — calcular la respuesta en `_salida` (rama `completo`).** Reemplazar el bloque (líneas 110-115):
```python
    if intent["status"] == "completo":
        r = intent["entidad"]["resuelta"]
        out["intent"] = {"entidad": intent["entidad"]["texto"], "nivel": r["nivel"], "rama": r["rama"],
                         "valor": r["valor"], "avisos": intent["avisos"]}
        out["huella"] = _huella(r)   # huella básica (rango temporal) de la entidad resuelta
```
por:
```python
    if intent["status"] == "completo":
        r = intent["entidad"]["resuelta"]
        out["intent"] = {"entidad": intent["entidad"]["texto"], "nivel": r["nivel"], "rama": r["rama"],
                         "valor": r["valor"], "avisos": intent["avisos"]}
        out["huella"] = _huella(r)   # huella básica (rango temporal) de la entidad resuelta
        # Fase 3 (determinista): cifra REAL vs PPTO reusando el motor del tablero. Regla madre: ningún
        # error interno llega feo al usuario; F7: se loguea el traceback para no depurar a ciegas.
        try:
            out["respuesta"] = ejecutar(r, intent.get("producto"), intent.get("periodo"),
                                        intent.get("agregacion"))
        except Exception:
            logging.getLogger("consulta.ejecucion").exception("ejecutar() falló")
            out["respuesta"] = {"aplica": False,
                                "texto": "No pude calcular la cifra en este momento. Intenta de nuevo."}
```

### A3 — NUEVO `test_consulta_ejecucion.py`

Crear `INGESTA\Rep_Prod\backend\tests\test_consulta_ejecucion.py`:

```python
from app.features.consulta.ejecucion import ejecutar


def _fake(por_producto, **extra):
    base = {"encontrada": True, "aplica_diario": True, "sin_cierre": False,
            "mes": {"anio": 2026, "mes": 5, "nombre": "Mayo",
                    "dias_con_data": 17, "dias_del_mes": 31, "completo": False},
            "por_producto": por_producto, "curva": {"fechas": [], "series": {}}}
    base.update(extra)
    def _fn(entidad=None, segmento="ecp", **_):   # F3: acepta segmento (ejecutar lo pasa explícito)
        return base
    return _fn


_PP = [{"producto": "CRUDO", "real": 88857284.0, "ppto": 93790748.0, "cumplimiento": 94.7},
       {"producto": "GAS", "real": 72259391.0, "ppto": 83072749.0, "cumplimiento": 87.0},
       {"producto": "BLANCOS", "real": 500.0, "ppto": 900.0, "cumplimiento": 55.2}]
_A = {"nivel": "campo", "rama": "A", "valor": "RUBIALES"}


def test_un_producto():
    r = ejecutar(_A, "aceite", None, _desempeno_fn=_fake(_PP))
    assert r["aplica"] is True and len(r["lineas"]) == 1
    assert r["lineas"][0]["producto"] == "CRUDO" and r["lineas"][0]["estado"] == "Alineado"
    assert "94.7%" in r["lineas"][0]["texto"]

def test_sin_producto_devuelve_tres():
    r = ejecutar(_A, None, None, _desempeno_fn=_fake(_PP))
    assert r["aplica"] is True and len(r["lineas"]) == 3
    assert r["lineas"][2]["estado"] == "Foco"      # BLANCOS 55.2 -> Foco

def test_agua_rechazada():
    r = ejecutar(_A, "agua", None, _desempeno_fn=_fake(_PP))
    assert r["aplica"] is False and "agua" in r["texto"].lower()

def test_rama_b_filial():
    r = ejecutar({"nivel": "filial", "rama": "B", "valor": "Hocol"}, "aceite", None, _desempeno_fn=_fake(_PP))
    assert r["aplica"] is False and "filial" in r["texto"].lower()

def test_periodo_historico_avisa():
    r = ejecutar(_A, "aceite", "marzo", _desempeno_fn=_fake(_PP))
    assert r["aplica"] is True and r["avisos"]

def test_agregacion_promedio_avisa():
    r = ejecutar(_A, "aceite", None, agregacion="promedio_diario", _desempeno_fn=_fake(_PP))
    assert r["aplica"] is True and any("promedio" in a.lower() for a in r["avisos"])

def test_producto_no_reportado():
    pp = [{"producto": "GAS", "real": 0.0, "ppto": 0.0, "cumplimiento": None}]
    r = ejecutar(_A, "gas", None, _desempeno_fn=_fake(pp))
    assert r["aplica"] is False and "no reporta" in r["texto"].lower()

def test_sin_cierre():
    r = ejecutar(_A, "aceite", None, _desempeno_fn=_fake(_PP, sin_cierre=True))
    assert r["aplica"] is False
```

### A4 — EDIT `multitab_shell.js` (reemplazo quirúrgico + helper)

**Paso 1 — reemplazo de UN fragmento** (F2: NO tocar la línea `<ul>` de arriba). En `static\js\multitab_shell.js`,
dentro de la rama `if (d.status === "completo")`, el `__cnBubble("assistant", …)` termina así (línea ~1937):
```javascript
        '<p class="rb-chat__note">Por ahora dejo el pedido listo; el número real llega en la siguiente fase.</p>');
```
Reemplazar **solo esa línea** por:
```javascript
        __cnRespuestaHtml(d.respuesta));
```
(El resto del string —kicker, huella, botones, `<ul>`— queda intacto.)

**Paso 2 — helper nuevo**, insertar **justo antes** de `function __cnRender(d) {` (línea ~1870):
```javascript
  function __cnRespuestaHtml(resp) {
    // Fase 3 determinista: burbuja con la cifra REAL vs PPTO. Sin resp -> nota honesta (compat).
    if (!resp) return '<p class="rb-chat__note">Por ahora dejo el pedido listo; el número real llega en la siguiente fase.</p>';
    if (!resp.aplica) return '<p class="rb-chat__note">' + esc(resp.texto || "") + '</p>';
    var lis = (resp.lineas || []).map(function (l) {
      return '<li class="cn-answer__row">' + esc(l.texto) + '</li>';
    }).join("");
    var av = (resp.avisos && resp.avisos.length)
      ? '<p class="rb-chat__note">' + resp.avisos.map(esc).join(" ") + '</p>' : "";
    return '<div class="cn-answer">' +
      '<div class="cn-answer__head">' + esc(resp.encabezado || "") + '</div>' +
      '<ul class="cn-answer__list">' + lis + '</ul>' +
      (resp.pie ? '<p class="rb-chat__note">' + esc(resp.pie) + '</p>' : "") + av +
      '</div>';
  }
```
> `esc` está en el mismo IIFE (se usa por todo el archivo). El helper devuelve string; **no** llama `__cnBubble`.

### A5 — EDIT `colapsable.css`

Añadir al final de `static\css\colapsable.css`:
```css
/* Fase 3 · respuesta numérica del chat de Consulta (determinista) */
.cn-answer { margin-top: 10px; border-top: 1px solid rgba(0,0,0,.08); padding-top: 8px; }
.cn-answer__head { font-weight: 600; font-size: .82rem; color: #14532d; margin-bottom: 6px; }
.cn-answer__list { list-style: none; margin: 0; padding: 0; }
.cn-answer__row { font-variant-numeric: tabular-nums; font-size: .86rem; padding: 3px 0;
  border-bottom: 1px dashed rgba(0,0,0,.06); }
.cn-answer__row:last-child { border-bottom: 0; }
```

### A6 — EDIT `templates\main.html`

Subir el cache-buster de `20260715e` a `20260715f` en las **2** referencias:
- Línea 5: `css/colapsable.css') }}?v=20260715f`
- Línea 82: `js/multitab_shell.js') }}?v=20260715f`

---

## 7. Orden de ejecución

1. **V0** (pre-check): `_estado` y `desempeno` existen; `GET /analisis/desempeno?entidad=RUBIALES` responde.
2. A1 → A2 → A3 → correr **V1**.
3. A4 → A5 → A6.
4. Correr **V2–V5**. Reportar tabla PASS/FAIL. **No commitear.**

---

## 8. Reglas no negociables

- **Sin LLM.** `ejecucion.py` no importa/llama Ollama ni `_llm_insight` (D-F3-5).
- **No duplicar cálculo.** `ejecucion.py` no escribe SQL: reusa `desempeno(..., segmento="ecp")` (D-F3-7, F1).
- **No tocar** `extraccion.py`, `resolver.py`, `analisis\api.py`, `routes\api.py`.
- **Regla madre:** ningún error feo al usuario. `_salida` envuelve `ejecutar()` en try/except (loguea, F7);
  `ejecutar()` siempre devuelve `{aplica:…}`.
- **Frontera LLM/Python intacta:** el LLM solo extrae; Python resuelve, calcula y redacta.
- **Contrato `/consulta` solo se AMPLÍA** con `respuesta` (aditivo).
- **A4 es quirúrgico:** reemplazar SOLO el fragmento del `<p>` placeholder; NO duplicar la línea `<ul>` (F2).

---

## 9. Validaciones (comando → resultado esperado)

| ID | Comando / acción | Esperado |
|----|------------------|----------|
| **V0** | `grep -n "^def _estado\|^def desempeno" INGESTA/Rep_Prod/backend/app/features/analisis/api.py` + `GET http://localhost:8088/analisis/desempeno?entidad=RUBIALES` | `_estado` y `desempeno` existen; el endpoint devuelve `por_producto` con `cumplimiento`. |
| **V1** | `cd INGESTA\Rep_Prod\backend; uv run pytest tests/test_consulta_ejecucion.py -q` | **8 passed.** |
| **V2** | `cd INGESTA\Rep_Prod\backend; uv run pytest -q` | Verde (sin regresión de `test_consulta_estado.py`). |
| **V3** | Backends arriba. `POST http://localhost:8088/consulta/preguntar` body `{"texto":"cuánto produjo Rubiales de crudo","conversation_id":"t1"}` | `status:"completo"`, `respuesta.aplica:true`, 1 línea CRUDO cuyo `cumplimiento` **== ** el de CRUDO en `GET /analisis/desempeno?entidad=RUBIALES`. |
| **V4** | `POST /consulta/preguntar` `{"texto":"producción de Hocol","conversation_id":"t2"}`; si desambigua, `POST /consulta/responder` eligiendo la opción **filial** | `respuesta.aplica:false`, texto con «filial» y «próxima iteración». |
| **V5** | Navegador (139 o dev): pestaña **Consulta** → «cuánto produjo Rubiales de crudo» | Burbuja `.cn-answer` (encabezado mes + línea CRUDO + pie «Calculado sobre N días»); el dashboard derecho sigue pintándose; **0 errores de consola**. |

> **V3 = criterio de coherencia crítico:** el `cumplimiento` del chat debe ser **idéntico** al del tablero
> para la misma entidad (misma fuente de cálculo). Si V3 da `aplica:false` inesperado, revisar el
> traceback logueado por F7 en la consola del backend.

---

## 10. Fuera de alcance (explícito)

- **Rama B / filiales por-entidad** → iteración 2 (`fact_produccion_diaria` + meta PROGRAMA).
- **Periodos explícitos** (mes cerrado, YTD, año, rango, día) → iter. 2 (solo mes por defecto + aviso).
- **Otros intents:** variación/evolución, comparación, ranking, contribución, gap, narrativa «por qué».
- **Pulido con Gemma** de la respuesta → iter. 2, detrás de flag.
- **`agregacion`** (promedio/acumulado): se avisa honestamente, no se aplica (siempre volumen del mes).
- **Refactor de `desempeno()` a helper compartido** (deuda documentada en §0) → iter. posterior.
- **Doble cómputo de `desempeno`** (server-side en `ejecutar` + fetch del dashboard): aceptado en iter. 1;
  optimización futura (compartir payload) documentada, no implementada.
```
