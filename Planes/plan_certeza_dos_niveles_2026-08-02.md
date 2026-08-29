# Plan ejecutable — Filtro de dominio en DOS NIVELES de certeza (escalada a Capa 2)

> **Para el Executor.** Autocontenido. Rutas absolutas. Decisiones cerradas. No requiere contexto
> previo. Sigue el ORDEN de ejecución (§7) al pie de la letra y al final corre TODAS las
> validaciones (§8) reportando la salida literal.
>
> ⚠️ **LEE LA §8.5 ANTES DE CORRER EL GOLDEN:** este plan introduce **1 fallo ESPERADO** en el
> golden set (deuda documentada, no un error de ejecución). Si aparece ese fallo y solo ese, la
> validación es CORRECTA. Si aparece cualquier otro, detente y reporta.

---

## 1. Contexto

El **filtro de dominio** (`consulta_v2/dominio.py` + `config/vocabulario_dominio.yaml`, commit
`4d75dde`) valida, cuando la Capa 1 regex atrapa un patrón genérico, que la pregunta sea del
dominio: pasa si hay **entidad del catálogo** O **palabra del vocabulario**.

**Problema medido:** el vocabulario trata todas sus palabras como evidencia equivalente, y no lo
son. `CRUDO`, `P50`, `EBITDA` no existen fuera del petróleo. Pero `CAMPOS`, `POZOS`, `ACTIVOS`
son a la vez entidades del modelo **y** sustantivos comunes del español → dejan pasar preguntas
ajenas: *"¿Qué campos pesan más en la dieta mediterránea?"* clasifica como **Analizar**.

Retirar esas 3 palabras del vocabulario **no es opción** (decisión del usuario, 2026-08-02): son
entidades centrales del modelo y sostienen preguntas genéricas legítimas sin entidad nombrada
(*"¿cuántos campos hay?"*, *"¿qué campos están por debajo de la meta?"*), que morirían sin ellas.

**Verificado empíricamente** (no de memoria): las frases *"campos por debajo de la meta"* y
*"campos de la dieta mediterránea"* tienen **exactamente la misma evidencia léxica de dominio**
(la palabra `campos`). Lo único que las separa es **qué califica** a "campos" — información
gramatical. **Ninguna lista de palabras puede separarlas.** Lo que sí puede es el LLM.

---

## 2. Objetivo

Partir el filtro en **dos niveles de certeza** y delegar SOLO la franja dudosa a la Capa 2:

```
Regex atrapa grupo (patrón genérico, no anclado)
        │
        ▼
¿Entidad del catálogo?  ──SÍ──▶ grupo directo            (certeza FUERTE, cero LLM)
        │ NO
        ▼
¿Vocabulario?
   ├─ FUERTE (CRUDO, P50, PRODUCCION…) ──▶ grupo directo  (certeza FUERTE, cero LLM)
   ├─ ESTRUCTURAL (CAMPOS/POZOS/ACTIVOS) ──▶ Capa 2 confirma  ◀── LA FRANJA NUEVA
   └─ NINGUNA ──▶ desconocido                             (OUT por filtro, cero LLM)
```

**Balance MEDIDO en la franja real** (4 casos verificados con qwen2.5:3b, no estimados):

| Pregunta (entra a la franja) | Hoy | Con la propuesta | Efecto |
|---|---|---|---|
| campos … **dieta mediterránea** | analizar ✗ | desconocido ✓ | **ARREGLA** |
| cuántos **pozos sépticos** necesita una casa | cuantificar ✗ | desconocido ✓ | **ARREGLA** |
| qué **campos** están por debajo de la meta | analizar ✓ | desconocido ✗ | **ROMPE** (deuda §D5) |
| cuántos **campos** hay en total | cuantificar ✓ | cuantificar ✓ | neutro (paga latencia) |

**Ganancia neta: +1 acierto** (2 arreglos − 1 regresión). Es marginal en número; su valor real es
arquitectónico: pone al LLM exactamente donde la regex es estructuralmente ciega.

⚠️ **Corrección de una medición previa:** un sondeo inicial dio "6/7" — inflado. De 7 preguntas
candidatas, **3 no entran a la franja** porque la regex no las atrapa (`"qué pozos están parados"`,
`"cuáles son los activos con mejor desempeño"`, `"qué campos aportan más al total"` → `clasificar_capa1`
devuelve `None` → ya van a Capa 2 por el camino viejo). La propuesta no las toca.

---

## 3. Prerequisitos

- Raíz dev: `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\`
- Trabajar desde: `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend\`
- Python vía `uv` (`uv run ...`).
- **PostgreSQL local ARRIBA** (`localhost:5432`, BD `daily_report_prod`) — el golden resuelve
  entidades contra el catálogo (253 nombres). Pre-check en §8.0.
- **Ollama ARRIBA y respondiendo** (dev: `qwen2.5:3b`) — **NUEVO requisito respecto al plan
  anterior**: el golden ahora invoca la Capa 2 en la franja estructural. Pre-check en §8.0b.
- Punto de partida: commit `4d75dde` aplicado (filtro de dominio + 4 anclas retiradas).
- **NO** se toca `consulta/` (v1 congelada). **NO** hay migración de BD (`capa_resolutora` es
  `TEXT` libre, sin CHECK → los 2 valores nuevos entran sin DDL).

---

## 4. Decisiones cerradas (no reabrir)

- **D1 · Dos listas en el mismo YAML.** `vocabulario:` (fuerte, se mantiene el nombre por
  compatibilidad) + `estructural:` (nueva). `CAMPOS?`, `POZOS?`, `ACTIVOS?` **se MUEVEN** de la
  primera a la segunda. Ninguna palabra se elimina — el filtro sigue reconociéndolas como dominio.
- **D2 · API nueva `nivel_dominio(texto) -> "fuerte"|"estructural"|None`.** `hay_palabra_dominio()`
  se conserva como wrapper (`nivel_dominio(...) is not None`) para no romper los tests existentes.
- **D3 · Precedencia: FUERTE gana.** Si la frase trae una palabra fuerte Y una estructural
  (*"detractores de crudo"*), es fuerte → NO escala. Esto es lo que salva los 4 casos que la
  propuesta original rompía.
- **D4 · FALLBACK OBLIGATORIO.** Si la Capa 2 falla (`diag` no nulo: timeout/conexión/JSON malo)
  → **se conserva el grupo de la regex**, jamás `desconocido`. Razón operativa medida: en el
  entorno del usuario la Capa 2 timeoutea con frecuencia (badges `timeout` en la libreta). Sin
  este fallback, cada caída del LLM se tragaría una pregunta legítima. Con él, una caída degrada
  exactamente al comportamiento de hoy.
- **D5 · El caso que se rompe ENTRA al golden con su etiqueta CORRECTA.** *"¿Qué campos están por
  debajo de la meta?"* → `esperado: analizar`, y **fallará**. Es deuda VISIBLE, no se esconde ni
  se etiqueta al revés (eso corrompería el examen). Gate ≥90% se sigue cumpliendo.
- **D6 · La entidad del LLM NO se usa en la rama de escalada.** Se escaló precisamente porque
  `detectar_entidad` no halló nada; si el LLM inventa una, mentiría. Se ignora `r["entidad"]` ahí.
- **D7 · Dos trazas nuevas de `capa_resolutora`:** `regex+llm` (escaló y el LLM decidió) y
  `regex+llm_fallo` (escaló, el LLM falló, mandó la regex). El KPI `pct_capa1` de `log.listar`
  cuenta `capa='regex'` EXACTO → ninguna de las dos suma, correctamente (tocaron el LLM).
- **D8 · Los tests unitarios NO llaman al LLM real.** Usan `monkeypatch` sobre
  `maquina_q.clasificar_capa2` → deterministas y sin red. El golden sí lo llama (es su rol).

---

## 5. Inventario de archivos

| Acción | Ruta absoluta |
|---|---|
| MODIFICADO | `…\INGESTA\Rep_Prod\backend\app\features\consulta_v2\config\vocabulario_dominio.yaml` |
| MODIFICADO | `…\INGESTA\Rep_Prod\backend\app\features\consulta_v2\dominio.py` |
| MODIFICADO | `…\INGESTA\Rep_Prod\backend\app\features\consulta_v2\maquina_q.py` |
| MODIFICADO | `…\INGESTA\Rep_Prod\backend\app\features\consulta_v2\senales.py` |
| MODIFICADO | `…\INGESTA\Rep_Prod\backend\app\features\consulta_v2\golden\revisar_lote.py` **[H-J]** |
| MODIFICADO | `…\INGESTA\Rep_Prod\backend\app\features\consulta_v2\golden\clasificacion_golden.yaml` |
| MODIFICADO | `…\INGESTA\Rep_Prod\backend\tests\test_consulta_v2_clasificador.py` |
| MODIFICADO | `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\static\js\multitab_shell.js` |
| MODIFICADO | `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\templates\main.html` |

(`…` = `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA`)

Sin archivos nuevos. Sin DDL, sin migración, sin tocar `consulta/`, `patrones.py`,
`clasificador_llm.py`, `log.py`, `api.py`, `run_golden.py`.

---

## 6. Especificación (código de referencia exacto)

### 6.1 `config/vocabulario_dominio.yaml` — partir en dos listas

Reemplazar el archivo COMPLETO por:

```yaml
# vocabulario_dominio.yaml — Filtro de dominio (motor_Q.md §1.2, Motor Q v2 · Fase 1)
#
# DOS NIVELES DE CERTEZA (2026-08-02). El filtro ya no trata todas las palabras igual:
#
#   vocabulario  (FUERTE)      -> términos que NO existen fuera del petróleo. Su sola presencia
#                                 confirma el dominio: se enruta directo, sin gastar LLM.
#   estructural  (DÉBIL)       -> entidades centrales del modelo que además son sustantivos
#                                 comunes del español (campos de estudio, activos financieros,
#                                 pozos sépticos). Confirman el dominio SOLO tras pasar por la
#                                 Capa 2, que sí entiende el contexto gramatical.
#
# POR QUÉ existe la segunda lista (verificado 2026-08-02, no de memoria): "campos por debajo de
# la meta" (dominio) y "campos de la dieta mediterránea" (ajena) tienen la MISMA evidencia léxica
# — la palabra "campos". Ninguna lista puede separarlas; solo el análisis de contexto puede.
# NO se elimina ninguna palabra: quitar CAMPOS/POZOS/ACTIVOS mataría las preguntas genéricas
# legítimas sin entidad nombrada ("¿cuántos campos hay?"). Decisión del usuario.
#
# Fragmentos REGEX con límite de palabra (\b...\b) sobre texto NORMALIZADO (norm(): UPPER, sin
# acentos). CONSERVADOR: si una palabra es ambigua, va en `estructural`, no en `vocabulario`.
#
# ⚠ Se carga UNA vez al arranque del backend → editar exige REINICIAR los backends.

version: 2

# --- FUERTE: inequívocas del dominio -> enrutan directo -------------------------------------
vocabulario:
  - PRODUCCION
  - CRUDO
  - ACEITE
  - GAS
  - BLANCOS
  - BARRILES?
  - BBL
  - BOPD
  - MSCF
  - KBPE
  - DIFERIDAS
  - MANTENIMIENTOS?
  - PRESUPUESTO
  - PPTO
  - P50
  - EBITDA
  - NOPAT
  - WORKOVER
  - NV04
  - CIERRE

# --- ESTRUCTURAL: entidades del modelo, pero también español común -> exigen Capa 2 ---------
estructural:
  - CAMPOS?
  - POZOS?
  - ACTIVOS?
```

### 6.2 `dominio.py` — `nivel_dominio()` + wrapper de compatibilidad

Reemplazar el archivo COMPLETO por:

```python
"""Filtro de dominio (motor_Q.md §1.2) — ¿la pregunta menciona vocabulario de producción?

Segundo criterio del filtro (el primero es detectar_entidad, en maquina_q.py). Módulo PURO:
solo depende de normaliza (sin BD, sin LLM) → testeable como patrones.py. Compilado UNA vez
(reiniciar backend para recargar).

DOS NIVELES (2026-08-02): el vocabulario dejó de ser una lista plana. Ver el encabezado de
config/vocabulario_dominio.yaml para el porqué (resumen: "campos" es a la vez entidad del
modelo y sustantivo común del español → evidencia DÉBIL que exige confirmación de la Capa 2).

FORK conceptual de la mecánica de patrones.py (carga perezosa de YAML) @ 2026-08-02.
"""
import re
import pathlib

import yaml

from app.features.consulta_v2.normaliza import norm

_CFG_PATH = pathlib.Path(__file__).parent / "config" / "vocabulario_dominio.yaml"

_RX = False   # False = no cargado; dict {"fuerte": rx|None, "estructural": rx|None} = cargado


def _compilar(lista):
    """Une los fragmentos en un solo regex \\b(a|b|...)\\b. None si la lista viene vacía."""
    items = [str(v) for v in (lista or []) if v]
    return re.compile(r"\b(" + "|".join(items) + r")\b") if items else None


def _cargar():
    """Compila ambas listas. Idempotente."""
    global _RX
    cfg = yaml.safe_load(_CFG_PATH.read_text(encoding="utf-8"))
    _RX = {"fuerte": _compilar(cfg.get("vocabulario")),
           "estructural": _compilar(cfg.get("estructural"))}
    return _RX


def _get():
    return _RX if _RX is not False else _cargar()


def nivel_dominio(texto: str):
    """Cuánta certeza de dominio aporta el vocabulario. 'fuerte' | 'estructural' | None.

    'fuerte'      → término inequívoco (CRUDO, P50, EBITDA…): enruta directo, sin LLM.
    'estructural' → CAMPOS/POZOS/ACTIVOS: entidad del modelo Y español común → la Capa 2
                    confirma (D3: si además hay una palabra fuerte, gana 'fuerte').
    None          → ninguna palabra del vocabulario.
    """
    c = _get()
    n = norm(texto)
    if c["fuerte"] and c["fuerte"].search(n):
        return "fuerte"
    if c["estructural"] and c["estructural"].search(n):
        return "estructural"
    return None


def hay_palabra_dominio(texto: str) -> bool:
    """Compat: ¿hay CUALQUIER palabra de dominio (fuerte o estructural)? Se conserva porque la
    usan tests y porque expresa la pregunta binaria original del filtro."""
    return nivel_dominio(texto) is not None
```

### 6.3 `maquina_q.py` — escalada a Capa 2 en la franja estructural

**(a)** En los imports, reemplazar:

```python
from app.features.consulta_v2.dominio import hay_palabra_dominio
```

por:

```python
from app.features.consulta_v2.dominio import nivel_dominio
```

**(b)** Reemplazar el bloque de `clasificar()` que va desde
`grupo, patrones = clasificar_capa1(texto)` hasta el `if not entidad:` (inclusive) por:

```python
    grupo, patrones = clasificar_capa1(texto)
    capa, entidad, diag = "regex", None, None
    if grupo is not None:
        # FILTRO DE DOMINIO (motor_Q.md §1.2 · D2/D3): la regex atrapó la FORMA; confirmar el TEMA.
        # Solo sobre patrones GENÉRICOS — los anclados ya son señal de dominio y se saltan.
        if not es_anclado(patrones):
            entidad = detectar_entidad(texto)
            if not entidad:
                nivel = nivel_dominio(texto)
                if nivel is None:
                    # Ni entidad del catálogo ni palabra de producción → fuera de dominio (OUT).
                    # D1 del plan del filtro: el token OUT es 'desconocido'. Se conservan los
                    # patrones para trazar en la libreta POR QUÉ disparó la regex.
                    grupo, capa = "desconocido", "regex+filtro"
                elif nivel == "estructural":
                    # CERTEZA DÉBIL: la única evidencia es CAMPOS/POZOS/ACTIVOS, que también son
                    # español común. La regex no ve el contexto gramatical ("campos de la dieta
                    # mediterránea" vs "campos por debajo de la meta" traen la MISMA palabra) →
                    # lo confirma la Capa 2, que sí entiende contexto.
                    r = clasificar_capa2(texto)
                    if r.get("diag"):
                        # D4 · FALLBACK OBLIGATORIO: el LLM falló (timeout/conexión/JSON malo) →
                        # se CONSERVA el grupo de la regex. Una caída del LLM degrada al
                        # comportamiento previo; jamás se traga una pregunta legítima.
                        capa, diag = "regex+llm_fallo", r["diag"]
                    else:
                        # El LLM respondió: su veredicto manda. D6: su 'entidad' se IGNORA — se
                        # escaló porque el catálogo no halló ninguna; si la inventa, mentiría.
                        grupo, capa = r["grupo"], "regex+llm"
    else:
        r = clasificar_capa2(texto)
        grupo, entidad, diag, capa = r["grupo"], r.get("entidad"), r.get("diag"), "llm"
        patrones = []
    if not entidad:
        entidad = detectar_entidad(texto)   # backstop (también aporta en Capa 1)
```

El resto de `clasificar()` (bloque `log_id`/`registrar` y el `return {...}`) queda IGUAL.

**(c) [H-I] `_mensaje()` SÍ se toca** — hoy rotula mal las trazas nuevas. Reemplazar:

```python
    via = "vía regex" if capa == "regex" else "vía LLM"
```

por:

```python
    via = _VIA_TXT.get(capa, "vía LLM")
```

y añadir esta constante justo ANTES de `def _mensaje(`:

```python
# H-I: el rótulo debe decir la verdad de QUIÉN decidió. Sin este mapa, 'regex+llm_fallo'
# (el LLM no respondió y mandó la regex) se anunciaba como "vía LLM" — mentira al usuario y
# al revisor de la libreta.
_VIA_TXT = {"regex": "vía regex", "regex+filtro": "vía regex", "llm": "vía LLM",
            "regex+llm": "vía regex + LLM", "regex+llm_fallo": "vía regex"}
```

### 6.4 `senales.py` — la Señal 3 también vigila el desconocido de la franja

En `escanear()`, reemplazar:

```python
            if f["grupo_asignado"] == "desconocido" and f["capa_resolutora"] == "llm":
```

por:

```python
            if (f["grupo_asignado"] == "desconocido"
                    and f["capa_resolutora"] in ("llm", "regex+llm")):
```

Razón: un `desconocido` decidido por el LLM en la franja estructural es tan incierto como uno de
Capa 2 pura → merece la misma vigilancia de abandono. `regex+filtro` y `regex+llm_fallo` NO
entran (el primero es una salida confiada; el segundo conserva el grupo de la regex, no es
desconocido). No tocar la Señal 1 ni `registrar_senal_v1`.

### 6.4b `golden/revisar_lote.py` — **[H-J]** priorizar también la franja en la cola

La cola de revisión (Control 3) sube primero los casos resueltos por LLM porque son los menos
ciertos. Un `regex+llm` lo es igual y hoy quedaría al fondo. En la consulta de `revisar_lote.py`,
reemplazar:

```python
             ORDER BY (veredicto='sospecha') DESC, (capa_resolutora='llm') DESC, ts
```

por:

```python
             ORDER BY (veredicto='sospecha') DESC,
                      (capa_resolutora IN ('llm','regex+llm')) DESC, ts
```

Único cambio en ese archivo. No tocar el resto de la CLI.

### 6.5 `golden/clasificacion_golden.yaml` — 1 caso editado + 3 nuevos

**(a) EDITAR** el caso de la dieta mediterránea. Reemplazar este bloque:

```yaml
# ---- Falso positivo ACEPTADO por decisión del usuario (2026-08-02): CAMPOS/POZOS/ACTIVOS se
# quedan en el vocabulario (son las palabras reales del negocio, aunque también existan fuera de
# él) → cualquier frase que las use, sea del tema que sea, pasa el filtro. Distinto del caso de
# arriba (dieta mediterránea) que en su momento se probó como trampa; aquí queda documentado el
# comportamiento REAL y decidido, no un bug pendiente.
- pregunta: "¿Qué campos pesan más en la dieta mediterránea?"
  esperado: analizar
```

por:

```yaml
# ---- [2026-08-02 · certeza en 2 niveles] CAMPOS/POZOS/ACTIVOS siguen en el vocabulario (son
# entidades centrales del modelo) pero pasaron a nivel ESTRUCTURAL: su sola presencia ya no
# enruta — la Capa 2 confirma el contexto. Este caso deja de ser un falso positivo aceptado y
# pasa a resolverse bien. Depende del LLM (model-dependent: verificar paridad gemma4).
- pregunta: "¿Qué campos pesan más en la dieta mediterránea?"
  esperado: desconocido
```

**(b) AÑADIR** al final del archivo:

```yaml

# ---- [2026-08-02] Franja ESTRUCTURAL: la Capa 2 confirma cuando la única evidencia de dominio
# es CAMPOS/POZOS/ACTIVOS. Los 3 casos entran a la escalada (verificado: la regex SÍ los atrapa).
# Model-dependent — su veredicto lo emite el LLM, no la regex.
- pregunta: "¿Cuántos pozos sépticos necesita una casa?"
  esperado: desconocido
- pregunta: "¿Cuántos campos hay en total?"
  esperado: cuantificar

# ⚠️ DEUDA CONOCIDA Y MEDIDA (D5) — ESTE CASO FALLA HOY, A PROPÓSITO ESTÁ AQUÍ.
# El LLM (qwen2.5:3b) clasifica esta pregunta legítima de producción como 'desconocido'. Es el
# precio de la escalada: 2 casos arreglados por 1 roto (ganancia neta +1). Se registra con su
# etiqueta CORRECTA (analizar) para que la deuda quede VISIBLE en cada corrida del gate — NO se
# etiqueta al revés ni se omite, eso corrompería el examen. Vías de cierre (fuera de alcance de
# este plan): afinar el prompt de Capa 2 para que sepa que campos/pozos/activos son entidades de
# producción, o verificar si gemma4 en 139 sí acierta.
- pregunta: "¿Qué campos están por debajo de la meta?"
  esperado: analizar
```

### 6.6 `tests/test_consulta_v2_clasificador.py` — niveles + escalada + fallback

**(a)** En los imports del tope, reemplazar:

```python
from app.features.consulta_v2.dominio import hay_palabra_dominio
```

por:

```python
from app.features.consulta_v2.dominio import hay_palabra_dominio, nivel_dominio
```

**(b)** REEMPLAZAR el test `test_filtro_campos_es_falso_positivo_aceptado` completo (ya no
describe el comportamiento real) por el bloque siguiente. Los tests de escalada usan
`monkeypatch` (D8): prueban la LÓGICA sin red, deterministas.

```python
def test_nivel_dominio_fuerte():
    assert nivel_dominio("¿cuánto crudo se perdió?") == "fuerte"

def test_nivel_dominio_estructural():
    assert nivel_dominio("¿cuántos campos hay en total?") == "estructural"

def test_nivel_dominio_ninguno():
    assert nivel_dominio("¿cuánto es la raíz cuadrada de 2?") is None

def test_nivel_dominio_fuerte_gana_a_estructural():
    # D3: "detractores de crudo" trae CRUDO (fuerte) + implícitamente el dominio → NO escala.
    # Sin esta precedencia, la escalada rompía 4 casos legítimos del golden.
    assert nivel_dominio("explícame los detractores de crudo en los campos") == "fuerte"

def test_escalada_llm_decide_desconocido(monkeypatch):
    # Franja estructural + el LLM entiende el contexto ajeno → su veredicto manda.
    import app.features.consulta_v2.maquina_q as M
    monkeypatch.setattr(M, "clasificar_capa2",
                        lambda t: {"grupo": "desconocido", "entidad": None, "diag": None})
    d = M.clasificar("¿qué campos pesan más en la dieta mediterránea?", log=False)
    assert d["grupo"] == "desconocido" and d["capa_resolutora"] == "regex+llm"

def test_escalada_llm_confirma_dominio(monkeypatch):
    import app.features.consulta_v2.maquina_q as M
    monkeypatch.setattr(M, "clasificar_capa2",
                        lambda t: {"grupo": "cuantificar", "entidad": None, "diag": None})
    d = M.clasificar("¿cuántos campos hay en total?", log=False)
    assert d["grupo"] == "cuantificar" and d["capa_resolutora"] == "regex+llm"

def test_escalada_fallback_conserva_regex(monkeypatch):
    # D4 · EL TEST MÁS IMPORTANTE DEL PLAN: si el LLM falla, se conserva el grupo de la REGEX.
    # Sin esto, cada timeout de Ollama se tragaría una pregunta legítima de producción.
    import app.features.consulta_v2.maquina_q as M
    monkeypatch.setattr(M, "clasificar_capa2",
                        lambda t: {"grupo": "desconocido", "entidad": None, "diag": "timeout"})
    d = M.clasificar("¿qué campos están por debajo de la meta?", log=False)
    assert d["grupo"] == "analizar"                      # el de la regex, NO desconocido
    assert d["capa_resolutora"] == "regex+llm_fallo"
    assert d["llm_diag"] == "timeout"

def test_escalada_no_toma_entidad_del_llm(monkeypatch):
    # D6: se escaló porque el catálogo no halló entidad; si el LLM la inventa, se ignora.
    import app.features.consulta_v2.maquina_q as M
    monkeypatch.setattr(M, "clasificar_capa2",
                        lambda t: {"grupo": "analizar", "entidad": "MEDITERRANEA", "diag": None})
    d = M.clasificar("¿qué campos pesan más en la dieta mediterránea?", log=False)
    assert d["entidad_cruda"] != "MEDITERRANEA"

def test_vocabulario_fuerte_no_escala(monkeypatch):
    # Certeza fuerte → enruta directo, el LLM NI SE LLAMA (si se llamara, este test explota).
    import app.features.consulta_v2.maquina_q as M
    def _boom(t):
        raise AssertionError("la Capa 2 NO debe invocarse con vocabulario fuerte")
    monkeypatch.setattr(M, "clasificar_capa2", _boom)
    d = M.clasificar("explícame los detractores de crudo", log=False)
    assert d["grupo"] == "analizar" and d["capa_resolutora"] == "regex"

def test_mensaje_no_miente_en_fallback(monkeypatch):
    # H-I: si el LLM no respondió, el mensaje NO puede anunciar "vía LLM" — decidió la regex.
    import app.features.consulta_v2.maquina_q as M
    monkeypatch.setattr(M, "clasificar_capa2",
                        lambda t: {"grupo": "desconocido", "entidad": None, "diag": "timeout"})
    d = M.clasificar("¿qué campos están por debajo de la meta?", log=False)
    assert "vía regex" in d["mensaje"] and "vía LLM" not in d["mensaje"]
```

### 6.7 `static/js/multitab_shell.js` — rotular las 2 trazas nuevas

En `__cnRenderV2`, reemplazar:

```javascript
    var __V2VIA = { regex: "regex", "regex+filtro": "regex + filtro", llm: "LLM" };
    var via = __V2VIA[d.capa_resolutora] || "LLM";
```

por:

```javascript
    var __V2VIA = { regex: "regex", "regex+filtro": "regex + filtro", llm: "LLM",
                    "regex+llm": "regex + LLM", "regex+llm_fallo": "regex (LLM no respondió)" };
    var via = __V2VIA[d.capa_resolutora] || "LLM";
```

La libreta de Test Clas ya imprime `esc(f.capa_resolutora)` crudo → muestra los valores nuevos
sin cambios.

### 6.8 `templates/main.html` — cache-buster

Cambiar el valor de `?v=` de **ambas** etiquetas (`colapsable.css` y `multitab_shell.js`) al
valor `20260802d1`.

---

## 7. Orden de ejecución

1. `config/vocabulario_dominio.yaml` — dos listas (§6.1).
2. `dominio.py` — `nivel_dominio()` + wrapper (§6.2).
3. `maquina_q.py` — import + escalada + fallback (§6.3 a/b) **+ `_VIA_TXT` (§6.3c, H-I)**.
4. `senales.py` — Señal 3 incluye `regex+llm` (§6.4).
5. `golden/revisar_lote.py` — ORDER BY incluye `regex+llm` (§6.4b, H-J).
6. `golden/clasificacion_golden.yaml` — 1 editado + 3 nuevos (§6.5).
7. `tests/test_consulta_v2_clasificador.py` — 10 tests (§6.6).
8. `static/js/multitab_shell.js` — `__V2VIA` (§6.7).
9. `templates/main.html` — cache-buster (§6.8).
10. Correr TODAS las validaciones §8, en orden. Reiniciar backends antes de las que usan la API.

---

## 8. Validaciones (comando → resultado esperado)

Desde `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend\`.

**8.0 · Pre-check BD** (sin esto el golden da OUT falsos):
```
set PYTHONPATH=.
uv run python -c "from app.features.consulta_v2.maquina_q import detectar_entidad; print('ENTIDAD OK' if detectar_entidad('Rubiales') else 'SIN BD - abortar')"
```
Esperado: `ENTIDAD OK`.

**8.0b · Pre-check LLM** (NUEVO — el golden ahora invoca la Capa 2 en la franja):
```
uv run python -c "from app.features.consulta_v2.clasificador_llm import clasificar_capa2; r=clasificar_capa2('cuanto crudo produjo Castilla'); print('LLM OK' if not r.get('diag') else 'LLM CAIDO diag='+str(r['diag']))"
```
Esperado: `LLM OK`. Si sale `LLM CAIDO`, **detente**: el golden mediría el fallback, no la
escalada. (La primera llamada puede tardar ~30s por arranque en frío — es normal.)

**8.1 · Compilación**
```
uv run python -c "import py_compile; [py_compile.compile(f,doraise=True) for f in ['app/features/consulta_v2/dominio.py','app/features/consulta_v2/maquina_q.py','app/features/consulta_v2/senales.py','app/features/consulta_v2/golden/revisar_lote.py']]; print('PY OK')"
```
Esperado: `PY OK`.

**8.2 · YAML válidos + estructura de las 2 listas**
```
uv run python -c "import yaml; c=yaml.safe_load(open('app/features/consulta_v2/config/vocabulario_dominio.yaml',encoding='utf-8')); assert c.get('estructural'), 'falta lista estructural'; assert 'CAMPOS?' in c['estructural'], 'CAMPOS? debe estar en estructural'; assert 'CAMPOS?' not in c['vocabulario'], 'CAMPOS? NO debe seguir en vocabulario'; yaml.safe_load(open('app/features/consulta_v2/golden/clasificacion_golden.yaml',encoding='utf-8')); print('YAML OK')"
```
Esperado: `YAML OK`.

**8.3 · Frontend**
```
node --check "c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\static\js\multitab_shell.js"
```
Esperado: sin salida (exit 0).

**8.4 · Tests unitarios** (no tocan red: la Capa 2 va con monkeypatch)
```
uv run pytest tests/test_consulta_v2_clasificador.py -q
```
Esperado: **todos PASAN, 0 fallos**. Deben aparecer ~47 tests (38 previos + 10 nuevos − 1
reemplazado). Si falla `test_escalada_fallback_conserva_regex`, **detente** — es la guarda
crítica del plan (sin ella, cada timeout de Ollama se traga una pregunta legítima).

**8.5 · Golden** — ⚠️ **CON 1 FALLO ESPERADO** (D5)
```
set PYTHONPATH=.
uv run python app/features/consulta_v2/golden/run_golden.py
```
Esperado:
- `EXACTITUD: 56/57 = 98%` (o el conteo equivalente si el golden creció) → **gate ≥90% CUMPLIDO**.
- En la sección `FALLOS:` debe aparecer **exactamente uno**:
  `- ¿Qué campos están por debajo de la meta?`
- Debe aparecer un conteo no-cero en la línea nueva `CAPA 1 + LLM (regex+llm)`.
  *(Nota: `run_golden.py` ya agrupa las capas dinámicamente — no requiere cambios.)*
- 🔴 **Si aparece CUALQUIER otro fallo además de ese, DETENTE y reporta cuál** — sería una
  regresión no prevista, no la deuda documentada.

**8.6 · Prueba por la API** (backend reiniciado en `:8000`)

Franja estructural, tema ajeno → el LLM lo rechaza:
```
uv run python -c "import urllib.request,json; r=urllib.request.urlopen(urllib.request.Request('http://localhost:8000/consulta2/preguntar', data=json.dumps({'texto':'que campos pesan mas en la dieta mediterranea','conversation_id':'plan-test-2'}).encode(), headers={'Content-Type':'application/json'})); d=json.load(r); print(d['grupo'], d['capa_resolutora'])"
```
Esperado: `desconocido regex+llm`.

Vocabulario fuerte → directo, sin LLM:
```
uv run python -c "import urllib.request,json; r=urllib.request.urlopen(urllib.request.Request('http://localhost:8000/consulta2/preguntar', data=json.dumps({'texto':'explicame los detractores de crudo','conversation_id':'plan-test-2'}).encode(), headers={'Content-Type':'application/json'})); d=json.load(r); print(d['grupo'], d['capa_resolutora'])"
```
Esperado: `analizar regex`.

Sin evidencia alguna → OUT por filtro, sin LLM:
```
uv run python -c "import urllib.request,json; r=urllib.request.urlopen(urllib.request.Request('http://localhost:8000/consulta2/preguntar', data=json.dumps({'texto':'cuanto es la raiz cuadrada de 2','conversation_id':'plan-test-2'}).encode(), headers={'Content-Type':'application/json'})); d=json.load(r); print(d['grupo'], d['capa_resolutora'])"
```
Esperado: `desconocido regex+filtro`.

**8.7 · Limpiar las filas de prueba**
```
uv run python -c "import sqlalchemy as sa; from app.core.db import get_engine; e=get_engine(); conn=e.connect(); tx=conn.begin(); n=conn.execute(sa.text(\"DELETE FROM core.clasificacion_log WHERE conversation_id='plan-test-2'\")).rowcount; tx.commit(); conn.close(); print('borradas', n)"
```
Esperado: `borradas 3`.

**8.8 · Paridad gemma4 (139, cuando aplique):** repetir §8.5 con `CONSULTA_LLM_MODEL=gemma4:latest`.
Los casos de la franja son **model-dependent** — anotar si gemma4 resuelve el fallo conocido de D5
(sería el cierre natural de esa deuda).

---

## 9. Fuera de alcance (NO hacer)

- **Afinar el prompt de Capa 2** para enseñarle que campos/pozos/activos son entidades de
  producción (posible vía de cierre del fallo D5). No medido → no entra a este plan.
- **Tratamiento rico de OUT** (`motor_Q.md` §6: cortesía LLM + redirección + chips).
- Renombrar `desconocido`→`out`; cambiar el KPI `pct_capa1`; tocar `patrones.py`,
  `clasificador_llm.py`, `log.py`, `api.py`, `run_golden.py`.
- Añadir/quitar palabras del vocabulario más allá del movimiento de las 3 estructurales.
- Grupos respondiendo (Fases 2–6 de `motor_Q.md`), `sesion_intents`, validador pre-render.

---

## 10. Reglas no negociables

1. **NO** tocar `app/features/consulta/` (v1 congelada) ni archivos fuera del inventario §5.
2. **NO** hay migración de BD. Si un paso pide `ALTER`/`CREATE`, está mal — detente.
3. **El fallback (D4) no es opcional.** Si el LLM falla, se conserva el grupo de la regex. Un
   `desconocido` por timeout es inaceptable: se tragaría preguntas legítimas.
4. **Ninguna palabra sale del vocabulario.** Las 3 estructurales se MUEVEN de lista, no se borran.
5. **FUERTE gana sobre ESTRUCTURAL** (D3). Invertir esa precedencia rompe 4 casos del golden.
6. El golden **crece y se corrige con motivo escrito**, nunca se poda ni se etiqueta al revés.
   El caso de D5 va con `esperado: analizar` aunque falle.
7. En §8.5 se espera **exactamente 1 fallo** (el de D5). Uno más → detente y reporta.
8. Reiniciar los backends tras editar YAML (se cargan al arranque).
9. Los tests unitarios **no llaman al LLM real** (monkeypatch, D8) — deben correr sin Ollama.
10. Si una validación falla por algo no previsto aquí, **detente y reporta** — no improvises.

---

## 11. Registro de auditoría (flujo §0.2 — trazabilidad)

Mediciones hechas contra el código real ANTES de escribir este plan (no de memoria):

| # | Hallazgo | Efecto en el plan |
|---|---|---|
| A1 | La propuesta original (escalar con *cualquier* palabra de vocabulario) **rompe 4 casos** del golden: `detractores de crudo`, `proyección de cierre`, `crudo se perdió`, `meta de producción` — el LLM los manda a `desconocido` | Se añade D3 (fuerte gana) y la partición del vocabulario. Sin esto el plan es negativo |
| A2 | De 7 preguntas candidatas, **solo 4 entran** a la franja: 3 no las atrapa la regex (`clasificar_capa1→ None`) y ya iban a Capa 2 | Se corrige la ganancia declarada de "6/7" a **+1 neta**; el golden solo suma casos que SÍ ejercitan la franja |
| A3 | Balance real medido en la franja: 2 arreglos, **1 regresión**, 1 neutro con costo de latencia | D5: la regresión entra al golden con su etiqueta correcta como deuda visible; §8.5 declara el fallo esperado |
| A4 | En el entorno del usuario la Capa 2 timeoutea con frecuencia (badges `timeout` en la libreta) | D4: fallback obligatorio + `test_escalada_fallback_conserva_regex` como guarda crítica |
| A5 | `clasificar_capa2` distingue "respondió desconocido" (`diag=None`) de "falló" (`diag=timeout/conexion/json_invalido/grupo_invalido`) | El fallback se implementa sobre `r.get("diag")`, no sobre el grupo |
| A6 | `capa_resolutora` es `TEXT` libre en `core.clasificacion_log` (sin CHECK) | Los 2 valores nuevos entran sin migración |
| A7 | `run_golden.py` ya agrupa capas dinámicamente (`por_capa.get`) desde el fix del plan anterior | No requiere cambios: absorbe `regex+llm` y `regex+llm_fallo` solo |
| A8 | La Señal 3 de `senales.py` vigila `capa='llm'`; un `desconocido` de la franja sería igual de incierto pero no se vigilaría | §6.4 amplía a `('llm','regex+llm')` |
| A9 | Los tests que ejerciten la escalada llamarían al LLM real → lentos y no deterministas | D8: `monkeypatch` sobre `maquina_q.clasificar_capa2` |
| **H-I** | **`maquina_q.py:95` — `via = "vía regex" if capa == "regex" else "vía LLM"`: con `regex+llm_fallo` (el LLM NO respondió, decidió la regex) el chat anunciaría "vía LLM". Mentira al usuario y al revisor** | §6.3c: mapa `_VIA_TXT` + test `test_mensaje_no_miente_en_fallback` |
| **H-J** | **`revisar_lote.py:31` — `ORDER BY (capa_resolutora='llm') DESC` sube los casos inciertos a la cola de revisión; un `regex+llm` es igual de incierto y quedaba al fondo** | §6.4b: `IN ('llm','regex+llm')` |
| A10 | Consumidores de `capa_resolutora` inventariados por grep: `log.py:99` (KPI, D7 ✓), `run_golden.py:26` (dinámico ✓), `senales.py:97` (§6.4), `revisar_lote.py:31` (§6.4b), `multitab_shell.js:3347` (§6.7) y `:3761` (imprime crudo ✓) | Ninguno queda sin cubrir |
