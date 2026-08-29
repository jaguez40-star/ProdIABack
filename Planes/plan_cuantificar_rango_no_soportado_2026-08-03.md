# Plan v2 (auditado) — Cuantificar: rechazo honesto de rango-de-días/trimestre/semana (bug #5)

> **Modo:** ejecutable por un Executor externo (sin contexto previo ni conocimiento del repo).
> Todo lo necesario está aquí. Rutas ABSOLUTAS. Código de referencia COMPLETO. Decisiones CERRADAS.
> **Fecha:** 2026-08-03 · **Planner:** Claude · **Auditado v2** según §0.2 del CLAUDE.md de INGESTA.

**Cobertura: 1 defecto → 1 fix** (bug #5, la única deuda de calidad atacada esta ronda). Sin recortes.

---

## 0. Auditoría previa (reproducida contra el código real, 2026-08-03)

**El defecto (bug #5), verificado read-only y VIGENTE:** una pregunta de Cuantificar CON entidad y un
**rango de días** (o trimestre/semana) NO cae en OUT — entra a Cuantificar, y `cuantificar/slots.py`
la **degrada en silencio al mes completo**, devolviendo otra cifra con la misma confianza visual.

Reproducción (`extraer_slots(texto, "RUBIALES")` + `no_soportado.detectar(texto)`):

| Texto | `no_soportado` | slots hoy | Resultado hoy |
|---|---|---|---|
| «entre el 5 y el 10 de mayo … Rubiales» | `rango_dias` | N1 / mayo | **mes completo de mayo** (mal) |
| «los primeros 10 días de mayo …» | `rango_dias` | N1 / mayo | mes completo (mal) |
| «cuánto en el primer trimestre …» | `trimestre` | N1 / None | último mes (mal) |
| «producción trimestral de Castilla» | `trimestre` | N1 / None | último mes (mal) |
| «cuánto produjo esta semana …» | `semana` | N1 / None | último mes (mal) |

**🔑 Hallazgo de auditoría que MOLDEA el fix — `anio` NO se debe rechazar:**

| Texto | `no_soportado` | slots hoy | ¿Soportado? |
|---|---|---|---|
| «cuánto acumuló Rubiales **en el año 2026**» | `anio` | **N2** | **SÍ** (acumulado YTD) |
| «acumulado del año de Rubiales» | `None` | N2 | SÍ |
| «en todo el año» / «producción anual» | `anio` | N1 / None | degrada (leve) |

`no_soportado.detectar` marca `anio` también para *"en el año 2026"*, que Cuantificar **SÍ** responde
por N2 (acumulado). **Rechazar `anio` en bloque regresaría el acumulado.** Por eso el set a rechazar
excluye `anio` (el caso *"todo el año → último mes"* es una degradación menor, separada, NO el bug #5;
ver §7 Fuera de alcance).

**Set seguro verificado:** rechazar **solo** `{rango_dias, trimestre, semana}`. Ninguna pregunta
soportada (N1 mes, N2 acumulado, N3 serie, N4 variación) dispara esos tres códigos → **cero falsos
rechazos** (verificado con los 13 casos de la tabla de auditoría).

### 0.1 — Verificación del plan contra el código real (delta de auditoría, 2026-08-03)

Se auditó cada cambio del plan contra `respuesta_cuantificar.responder` y `cuantificar/resolver.py`.
No aparecieron defectos (a diferencia del plan de OUT). Confirmaciones + 1 riesgo + edges:

| # | Verificación | Resultado |
|---|---|---|
| **VA1** | **El punto de inserción es seguro.** La guarda se inserta DESPUÉS del `return` del bloque `ambiguo`, así que un `{"ambiguo": [...]}` (que no tiene clave `rama`) **nunca** llega a la guarda. Todo dict resuelto de `resolver_unico` (len==1 o colisión `auto`) **sí** trae `rama` (viene del índice `{nivel,rama,valor}`). El `zoom` (D-D5) se descarta en el rechazo, lo cual es correcto: ofrecer «ver como Activo» no ayuda — el Activo tampoco calcula un rango de días. | ✅ sin cambio |
| **VA2** | **Punto único de entrada.** `maquina_q` llama a `respuesta_cuantificar.responder` en un solo sitio (rama `cuantificar`); el drill de continuación reescribe el texto ANTES de clasificar → también fluye por `responder`. Un solo choke point. | ✅ sin cambio |
| **VA3 ⚠️** | **Riesgo de FALSO rechazo (heredado de `no_soportado`, aceptado):** el regex `LOS \d+ DIAS` marca `rango_dias` también en *«en los 30 días de mayo»*, que en realidad pide el **mes completo** (30 = días de mayo). Se rechazaría con «me pediste un rango de días…», y el usuario tendría que reformular a «en mayo». Es **raro** (fraseo inusual; casi todos dicen «en mayo») y **recuperable** (el mensaje pide nombrar el mes). NO se corrige aquí: el regex vive en `no_soportado.py`, que es compartido con la ruta OUT — tocarlo excede el alcance de este fix. | ⚠️ documentado (§7) |
| **VA4** | **Combo rango + producto no soportado** (p.ej. «agua entre el 5 y el 10»): la guarda de rango dispara PRIMERO (corre antes de `slots`/`ejecutor`, donde vive el rechazo de agua). El mensaje de rango promete «el mes completo» aunque agua tampoco exista a mes — pero es honesto en dos pasos (al pedir el mes, cae el rechazo de agua), **sin dato erróneo**. Combo rarísimo. | ✅ aceptado (§7) |
| **VA5** | **Los tests son PUROS.** Importar `respuesta_cuantificar` es BD-safe (`maquina_q` ya lo importa; `_catalogo.get()` solo lee el YAML; el índice del resolver es perezoso, no conecta al importar). El test de integración hace `monkeypatch` de `_resolver.resolver_unico` **y** de `_ejecutor.ejecutar` → cero BD/LLM. El caso «deja pasar» usa un `ejecutar` falso que devuelve `aplica:False` → `responder` retorna ANTES de `_intro`/`_validador` (sin LLM). | ✅ sin cambio |

**Edge NO cubierto (documentado, no es bug #5):** el seguimiento CORTO *«del 5 al 10?»* (≤5 tokens,
SIN entidad en el texto, apoyado en `_CTX`) NO lo atrapa este fix: `responder` recibe `entidad=None`,
`resolver_unico` no halla entidad en «del 5 al 10» → devuelve el mensaje «No identifiqué una entidad»
(honesto, **no** una cifra equivocada). El daño de bug #5 (número equivocado con la misma confianza)
**sí** queda resuelto para el caso documentado (entidad EN el texto: «…Rubiales entre el 5 y el 10»).
Atrapar el seguimiento corto exigiría leer `_CTX` desde `maquina_q` (como en OUT) — fuera de alcance.

**Decisiones cerradas:**
- El fix vive SOLO en `respuesta_cuantificar.py` (el dispatcher). **NO** toca el clasificador
  (`patrones_grupo.yaml`), ni `slots.py`, ni `ejecutor.py`, ni `dominio.py`. No requiere el ciclo de
  entrenamiento (esto no cambia enrutamiento; solo añade un rechazo honesto dentro de Cuantificar).
- Se **REUSA** `no_soportado.py` (detector + mensaje) ya en producción desde el commit `3bbae0f` —
  mismo molde de rechazo honesto de la ruta OUT. Cero lógica nueva de detección.
- El mensaje **nunca termina en pregunta sí/no** (heredado de `no_soportado.mensaje`): un «sí» caería
  en el drill `_AFIRM` de `maquina_q._continuacion` y devolvería el acumulado. Ya está garantizado por
  el módulo reusado (misma regla H1 del plan de OUT).

---

## 1. Objetivo

Que Cuantificar, ante un **rango de días / trimestre / semana** sobre una entidad resuelta (rama A),
responda un **rechazo honesto** que nombra la entidad y dice qué SÍ puede — en vez de calcular el mes
completo en silencio. `{mensaje, panel:None}` (contrato del grupo intacto).

---

## 2. Prerequisitos (verificar ANTES de tocar nada)

Desde `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend`:

```
uv run python -c "import app.features.consulta_v2.respuesta_cuantificar, app.features.consulta_v2.no_soportado; print('IMPORTS OK')"
```
Esperado: `IMPORTS OK`. Si falla → detenerse y reportar.

**Baseline (capturar ANTES de editar, se compara en V4):**
```
uv run pytest tests/test_cuantificar.py tests/test_no_soportado.py -q
```
Anotar la línea de resumen. Ese es el número a igualar después.

**Regla de entorno (NO negociable):** en dev NO se levanta backend ni LLM (RAM 8 GB). Validación
**estática**: `py_compile` + tests PUROS (sin BD, sin LLM). El módulo `no_soportado` y el helper nuevo
son puros; el test de integración usa `monkeypatch` sobre el resolver (no toca BD).

---

## 3. Inventario de archivos

(`...` = `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA`)

| Archivo (ruta absoluta) | Acción |
|---|---|
| `...\INGESTA\Rep_Prod\backend\app\features\consulta_v2\respuesta_cuantificar.py` | **EDITAR** (import + helper + guarda en `responder`) |
| `...\INGESTA\Rep_Prod\backend\tests\test_cuantificar_rango.py` | **CREAR** (tests puros: policy + integración monkeypatch) |

**NO se toca:** `no_soportado.py` (se reusa tal cual), `cuantificar/*` (slots/ejecutor/resolver/…),
`patrones_grupo.yaml`, `dominio.py`, `maquina_q.py`, migraciones, frontend, golden.

---

## 4. Especificación (código literal)

### 4.1 — EDITAR `respuesta_cuantificar.py`

Ruta: `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend\app\features\consulta_v2\respuesta_cuantificar.py`

**C1 — añadir el import.** Localizar el bloque de imports que termina en
`from app.features.consulta_v2.cuantificar import validador as _validador`. Añadir DEBAJO:

```python
from app.features.consulta_v2 import no_soportado as _no_soportado
```

**C2 — añadir la constante + el helper puro,** INMEDIATAMENTE ANTES de la línea
`def responder(texto: str, entidad: str | None = None, usuario=None, conversation_id=None):`

```python
# Bug #5: formas de periodo que el usuario pide pero Cuantificar aún NO calcula → rechazo honesto en
# vez de degradar en silencio al mes completo (verificado 2026-08-03: rango de días/trimestre/semana
# dan N1+mes/None → responderían el mes entero). Se REUSA no_soportado.detectar (el mismo detector
# determinista de la ruta OUT, commit 3bbae0f). 🔑 'anio' NO está en el set: N2 (acumulado) SÍ
# responde el año — "en el año 2026" da N2 — y rechazarlo regresaría el acumulado.
_FORMAS_RECHAZO = ("rango_dias", "trimestre", "semana")


def _forma_no_soportada(texto: str):
    """Código de forma NO soportada por Cuantificar (rango de días/trimestre/semana), o None.
    Puro (sin BD/LLM): delega en no_soportado.detectar y filtra por el set seguro auditado."""
    f = _no_soportado.detectar(texto)
    return f if f in _FORMAS_RECHAZO else None
```

**C3 — insertar la guarda en `responder`,** JUSTO DESPUÉS del bloque `if resuelta.get("ambiguo"):`
(el que devuelve el mensaje de «coincide con más de una entidad») y ANTES del comentario `# AF10:`.

Texto ACTUAL a localizar (para insertar entre ambos bloques):

```python
    if resuelta.get("ambiguo"):
        nombres = ", ".join(sorted({r["valor"] for r in resuelta["ambiguo"]}))
        return {"mensaje": (f"«{entidad or texto}» coincide con más de una entidad ({nombres}). "
                            "La desambiguación llega en una próxima fase; por ahora prueba con un nombre único."),
                "panel": None}

    # AF10: la entidad YA está resuelta (D-D5) → se le pasa a slots para que su nombre no contamine
```

Reemplazarlo por (se inserta el bloque nuevo en medio; los dos bloques existentes NO cambian):

```python
    if resuelta.get("ambiguo"):
        nombres = ", ".join(sorted({r["valor"] for r in resuelta["ambiguo"]}))
        return {"mensaje": (f"«{entidad or texto}» coincide con más de una entidad ({nombres}). "
                            "La desambiguación llega en una próxima fase; por ahora prueba con un nombre único."),
                "panel": None}

    # Bug #5: no degradar en silencio un rango de días/trimestre/semana al mes completo. La entidad ya
    # está resuelta → se puede nombrar en el rechazo honesto (molde de OUT, no_soportado.mensaje).
    # Solo rama A (ECP): la rama B (filial) ya la corta ejecutar (_rechazo_comun) con su propio mensaje.
    if resuelta.get("rama") != "B":
        _forma = _forma_no_soportada(texto)
        if _forma:
            return {"mensaje": _no_soportado.mensaje(_forma, resuelta["valor"]), "panel": None}

    # AF10: la entidad YA está resuelta (D-D5) → se le pasa a slots para que su nombre no contamine
```

**NADA más de `respuesta_cuantificar.py` cambia.**

### 4.2 — CREAR `test_cuantificar_rango.py`

Ruta: `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend\tests\test_cuantificar_rango.py`

Crear con este contenido EXACTO (**5 funciones de test**):

```python
"""Tests PUROS (sin BD, sin LLM) del rechazo honesto de rango/trimestre/semana en Cuantificar (bug #5).

La policy (_forma_no_soportada) es pura. La integración (responder) se prueba con monkeypatch sobre el
resolver → NO toca la BD: el rechazo retorna ANTES de ejecutar (que sí necesitaría datos)."""
import app.features.consulta_v2.respuesta_cuantificar as RC
from app.features.consulta_v2.respuesta_cuantificar import _forma_no_soportada


# --- Policy pura: qué se rechaza y qué NO -----------------------------------------------------
def test_rechaza_rango_trimestre_semana():
    assert _forma_no_soportada("entre el 5 y el 10 de mayo cuanto produjo Rubiales") == "rango_dias"
    assert _forma_no_soportada("los primeros 10 dias de mayo cuanto") == "rango_dias"
    assert _forma_no_soportada("cuanto en el primer trimestre de Rubiales") == "trimestre"
    assert _forma_no_soportada("produccion trimestral de Castilla") == "trimestre"
    assert _forma_no_soportada("cuanto produjo esta semana Rubiales") == "semana"


def test_NO_rechaza_anio_porque_N2_lo_soporta():
    # 🔑 Guarda de regresión: 'anio' NO se rechaza — N2 (acumulado) responde el año.
    assert _forma_no_soportada("cuanto acumulo Rubiales en el ano 2026") is None
    assert _forma_no_soportada("acumulado del año de Rubiales") is None
    assert _forma_no_soportada("produccion anual de Rubiales") is None      # anio → excluido del set


def test_NO_rechaza_lo_soportado():
    assert _forma_no_soportada("cuanto produjo Rubiales en mayo") is None   # N1
    assert _forma_no_soportada("serie mensual de Castilla") is None         # N3
    assert _forma_no_soportada("como vario mes a mes Rubiales") is None     # N4
    assert _forma_no_soportada("cuanto produjo Rubiales") is None           # N1 default


# --- Integración: responder() devuelve el rechazo honesto SIN tocar la BD ----------------------
def test_responder_rechaza_rango_sin_ejecutar(monkeypatch):
    # Resolver fake (rama A) → responder NO debe llegar al ejecutor (que necesitaría datos).
    monkeypatch.setattr(RC._resolver, "resolver_unico",
                        lambda x: {"valor": "RUBIALES", "rama": "A", "nivel": "campo"})
    def _boom(*a, **k):
        raise AssertionError("ejecutar NO debe llamarse en un rechazo de forma no soportada")
    monkeypatch.setattr(RC._ejecutor, "ejecutar", _boom)
    r = RC.responder("entre el 5 y el 10 de mayo cuanto produjo Rubiales", entidad="RUBIALES")
    assert r["panel"] is None
    assert "RUBIALES" in r["mensaje"]
    assert "rango de días" in r["mensaje"] and "mes completo" in r["mensaje"]
    assert "¿Quieres" not in r["mensaje"]   # H1: no invita a un "sí" (drill _AFIRM → acumulado)


def test_responder_deja_pasar_lo_soportado(monkeypatch):
    # Una pregunta soportada NO se rechaza: responder llega al ejecutor (aquí lo interceptamos).
    monkeypatch.setattr(RC._resolver, "resolver_unico",
                        lambda x: {"valor": "RUBIALES", "rama": "A", "nivel": "campo"})
    marca = {"llamado": False}
    def _fake_ejecutar(resuelta, slots):
        marca["llamado"] = True
        return {"aplica": False, "texto": "stub"}      # corta antes del validador/BD
    monkeypatch.setattr(RC._ejecutor, "ejecutar", _fake_ejecutar)
    r = RC.responder("cuanto produjo Rubiales en mayo", entidad="RUBIALES")
    assert marca["llamado"] is True                     # NO se rechazó por forma → siguió el flujo
    assert r["panel"] is None                           # (el stub devuelve aplica:False)
```

---

## 5. Orden de ejecución

1. Prerequisitos + baseline (§2).
2. Editar `respuesta_cuantificar.py` (§4.1 — C1, C2, C3).
3. Crear `test_cuantificar_rango.py` (§4.2).
4. Validaciones (§6) en orden.

---

## 6. Validaciones (comando → resultado esperado)

Desde `...\INGESTA\Rep_Prod\backend`.

**V1 — compilación:**
```
uv run python -m py_compile app/features/consulta_v2/respuesta_cuantificar.py
```
Esperado: sin salida, exit 0.

**V2 — import:**
```
uv run python -c "from app.features.consulta_v2.respuesta_cuantificar import _forma_no_soportada, responder; print('OK')"
```
Esperado: `OK`.

**V3 — tests nuevos (policy + integración):**
```
uv run pytest tests/test_cuantificar_rango.py -q
```
Esperado: **`5 passed`**, sin BD ni LLM.

**V4 — no regresión:**
```
uv run pytest tests/test_cuantificar.py tests/test_no_soportado.py -q
```
Esperado: **el mismo resumen del baseline de §2** — 0 fallos nuevos.

**V5 — humo de la policy (la tabla de auditoría en una línea):**
```
uv run python -c "from app.features.consulta_v2.respuesta_cuantificar import _forma_no_soportada as f; print([f(t) for t in ['entre el 5 y el 10 de mayo','primer trimestre','esta semana','en el ano 2026 acumulado','cuanto en mayo']])"
```
Esperado: `['rango_dias', 'trimestre', 'semana', None, None]` — los 3 primeros se rechazan; el año
(N2) y el mes puntual NO.

Si cualquier validación falla: **detenerse** y reportar comando + salida completa.

---

## 7. Fuera de alcance (explícito)

- **`anio` en bloque:** NO se rechaza (N2 acumulado lo soporta). El caso *"todo el año / anual → último
  mes"* es una degradación menor y separada del bug #5 (rango de días); queda como deuda aparte.
- **Rango de MESES por nombre** (*"de enero a marzo"*, sin dígitos): no lo detecta `no_soportado`
  (regex por dígitos) y slots toma el 1.er mes → también degrada, pero es otra forma, fuera de bug #5.
- **Día único** (*"el 5 de mayo"*, sin "días"/rango): tampoco lo cubre el detector; no es un rango.
- **Seguimiento CORTO sin entidad** (*"del 5 al 10?"* tras hablar de Rubiales, apoyado en `_CTX`):
  da «No identifiqué una entidad» (honesto, no una cifra), no el rechazo con nombre. Ver VA edge (§0.1).
- **Falso rechazo raro de *"los N días de {mes}"* con N = largo del mes** (VA3): rechazado como rango
  aunque signifique el mes completo; recuperable. No se corrige (regex compartido con OUT).
- **Combo rango + producto no soportado** (agua): gana el rechazo de rango; honesto en dos pasos (VA4).
- **Los 3 sub-hallazgos de `HALLAZGO_clasificador_conteo_jerarquia.md`** (2.1/2.2/2.3, enrutamiento de
  conteo): requieren el ciclo de entrenamiento del clasificador — NO son parte de este plan.
- **Verificación en navegador / LLM en vivo / deploy 139:** las hace el usuario en el servidor de pruebas.

---

## 8. Cierre (commit + documentación)

Mensaje de commit sugerido:
```
fix(consulta_v2): Cuantificar rechaza honesto rango-de-dias/trimestre/semana (bug #5)

Antes degradaba en silencio un rango de dias al mes completo (otra cifra, misma confianza).
Ahora respuesta_cuantificar detecta la forma (reusa no_soportado, mismo detector que OUT) y
responde el rechazo honesto que nombra la entidad. 🔑 'anio' se EXCLUYE del set: N2 (acumulado)
si responde el año -- rechazarlo regresaria el acumulado (verificado). Solo rama A; rama B ya la
corta ejecutor. No toca patrones/slots/ejecutor/clasificador. Sin ciclo de entrenamiento.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
```

Tras el commit, actualizar:
- `INGESTA/Rep_Prod/CLAUDE.md` §12 — fila de bitácora (S31).
- El estado del bug #5 donde esté anotado (bitácora S30 / plan de OUT §9): marcarlo **RESUELTO**.
