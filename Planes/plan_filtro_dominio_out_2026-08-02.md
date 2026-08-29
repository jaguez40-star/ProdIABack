# Plan ejecutable — Filtro de dominio + grupo OUT (Motor Q v2 · cierre de Fase 1) · **v2 auditado**

> **Para el Executor.** Autocontenido. Rutas absolutas. Decisiones cerradas. No requiere
> contexto previo. Sigue el ORDEN de ejecución (§7) al pie de la letra y al final corre TODAS las
> validaciones (§8) reportando el resultado tal cual.
>
> **v2 (2026-08-02):** reformulado tras auditoría adversarial del plan v1 contra el código real
> (flujo §0.2 del CLAUDE.md). Los hallazgos y sus fixes están marcados **[H-x]** en cada sección.

---

## 1. Contexto

El **Motor Q v2** (`INGESTA/Rep_Prod/backend/app/features/consulta_v2/`) clasifica cada pregunta
libre en `jerarquizar | cuantificar | analizar | desconocido`, en 2 capas: **Capa 1** regex
(patrones en `config/patrones_grupo.yaml`) → si no atrapa, **Capa 2** LLM cerrado.

**Problema (verificado en la libreta):** la regex atrapa la **forma** de la pregunta ("cuánto",
"qué es", "mes a mes", "se ve recuperación") pero **no verifica que el tema sea producción** →
preguntas fuera de dominio se clasifican como del negocio:

| Pregunta off-topic | Regex atrapa (hoy) | Debería ser |
|---|---|---|
| "¿cuánto es la raíz cuadrada de 2?" | cuantificar (`CUANT[OA]S?`) | desconocido |
| "dame el precio del dólar mes a mes" | cuantificar (`MES A MES`) | desconocido |
| "¿qué información hay de Bogotá?" | jerarquizar (`QUE INFORMACION`) | desconocido |
| "¿qué es HBOMAX?" | jerarquizar (`QUE ES \w+`) | desconocido |
| "¿se ve recuperación en el Dollar?" | analizar (`SE VE RECUPERACION`) | desconocido |

Implementa el **filtro de dominio** de `motor_Q.md` §1.2, con el **refinamiento** de que el filtro
corre **solo tras patrones "genéricos"**; los "anclados" (`DETRACTORES`, `P50`, `PRODUCCION DE`…)
son señal de dominio y se saltan el filtro → una pregunta global legítima ("¿cuáles son los
detractores?") NO se va a OUT por no traer entidad.

---

## 2. Objetivo

Que la **Capa 1** produzca OUT (token interno `desconocido`, Decisión D1) cuando atrapó la forma
pero el tema no es de producción:

- Tras atrapar con un patrón **genérico**, validar: **¿entidad del catálogo O palabra de
  vocabulario?** Si ninguna → `desconocido` con `capa_resolutora = "regex+filtro"`.
- Los patrones **anclados** se saltan el filtro.
- La Capa 2 refuerza su prompt para OUT de temas que la regex no atrapa ("capital de Francia").
- El golden crece con casos OUT + guardas de no-regresión; gate ≥90% con paridad qwen/gemma.
- **[H-A]** Frontend: corregir la etiqueta `capa_resolutora` en la burbuja del Motor v2.
- **[H-B]** Control 2 (`senales.py`): la Señal 3 de abandono se restringe al desconocido del LLM.

Fuera de este objetivo (§9): el *tratamiento* rico de OUT (cortesía LLM + redirección + chips,
`motor_Q.md` §6). `desconocido` conserva el menú declarativo actual (`_mensaje`).

---

## 3. Prerequisitos

- Raíz dev: `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\`
  (en 139, la raíz equivalente del sub-proyecto es `INGESTA/Rep_Prod/`).
- Trabajar desde: `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend\`
- Python vía `uv` (`uv run ...`).
- **[H-F] PostgreSQL local ARRIBA** (`localhost:5432`, BD `daily_report_prod`) — **REQUISITO NUEVO
  para el golden**: con el filtro, varios casos del golden pasan porque su **entidad** se resuelve
  contra el catálogo (`detectar_entidad` → BD). Sin BD, esos casos caerían a OUT (fallo falso). El
  pre-check §8.0 lo verifica antes de correr el golden.
- Ollama accesible para Capa 2 (dev qwen2.5:3b local; paridad gemma4 en 139).
- **NO** se toca `consulta/` (v1 congelada). **NO** hay migración de BD (las columnas
  `grupo_asignado`/`capa_resolutora` de `core.clasificacion_log` son `TEXT` libre, sin CHECK).

---

## 4. Decisiones cerradas (no reabrir)

- **D1 · Token OUT = `desconocido`.** `motor_Q.md` lo llama "OUT"; el código mantiene `desconocido`
  (ya usado por `GRUPOS_VALIDOS`, `GRUPO_LABEL`, `log.GRUPOS`, el golden, el frontend `__V2_GRUPO`
  y las filas ya escritas). "OUT" (diseño) ≡ `desconocido` (código).
- **D2 · Filtro solo sobre patrones GENÉRICOS.** Cada patrón se marca genérico (filtra) o
  **anclado** (se salta). Set inicial de anclados en §6.1.
- **D3 · Doble criterio de dominio (OR):** patrón genérico pasa si `detectar_entidad(texto)` halla
  algo **O** hay palabra de `vocabulario_dominio.yaml`.
- **D4 · Nueva traza `capa_resolutora = "regex+filtro"`** (regex atrapó, filtro reclasificó a OUT).
  El KPI `pct_capa1` de `log.listar` (cuenta `capa='regex'` exacto) deja fuera los `regex+filtro` a
  propósito (son OUT, no resolución de dominio). NO cambiar ese KPI.
- **D5 · Son anclados** `META\b`, `P50\b`, `GAP\b`, `DETRACTORES`, `DIFERIDAS`, `EBITDA`, `NOPAT`,
  etc. (§6.1). Trade-off aceptado (§10 R-nuevo): "¿cuál es tu meta de vida?" quedaría en analizar
  (raro en un bot de producción); a cambio "¿cuánto falta para la meta?" (común, global) no va a OUT.
- **[H-B] D6 · La Señal 3 de `senales.py` (abandono) se restringe a `capa_resolutora='llm'`.** El
  OUT-por-filtro es una salida CONFIADA (regex + sin dominio); abandonar tras él es esperado. El
  desconocido del LLM es el incierto — es el único que la señal de abandono debe vigilar.

---

## 5. Inventario de archivos

Rutas absolutas dev (raíz `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\`):

| Acción | Archivo |
|---|---|
| **NUEVO** | `INGESTA\Rep_Prod\backend\app\features\consulta_v2\dominio.py` |
| **NUEVO** | `INGESTA\Rep_Prod\backend\app\features\consulta_v2\config\vocabulario_dominio.yaml` |
| MODIFICADO | `INGESTA\Rep_Prod\backend\app\features\consulta_v2\config\patrones_grupo.yaml` |
| MODIFICADO | `INGESTA\Rep_Prod\backend\app\features\consulta_v2\patrones.py` |
| MODIFICADO | `INGESTA\Rep_Prod\backend\app\features\consulta_v2\maquina_q.py` |
| MODIFICADO | `INGESTA\Rep_Prod\backend\app\features\consulta_v2\clasificador_llm.py` |
| MODIFICADO | `INGESTA\Rep_Prod\backend\app\features\consulta_v2\senales.py`  **[H-B]** |
| MODIFICADO | `INGESTA\Rep_Prod\backend\app\features\consulta_v2\golden\run_golden.py` |
| MODIFICADO | `INGESTA\Rep_Prod\backend\app\features\consulta_v2\golden\clasificacion_golden.yaml` |
| MODIFICADO | `INGESTA\Rep_Prod\backend\tests\test_consulta_v2_clasificador.py` |
| MODIFICADO | `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\static\js\multitab_shell.js`  **[H-A]** |
| MODIFICADO | `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\templates\main.html`  **[H-A] cache-buster** |

Sin cambios de DDL, migración, ni `consulta/` (v1).

---

## 6. Especificación (código de referencia completo)

### 6.1 `config/patrones_grupo.yaml` — añadir `patrones_anclados`

Al FINAL del archivo (tras `precedencia_colision: [...]`), añadir el bloque. NO modificar
`precedencia_maxima`, `grupos` ni `precedencia_colision`. **Las cadenas deben ser IDÉNTICAS
(carácter por carácter) a las que ya aparecen arriba** — el test §6.9 `test_anclados_existen`
lo verifica y debe pasar.

```yaml

# --- Filtro de dominio (motor_Q.md §1.2, Decisión D2) --------------------------------------
# Patrones ANCLADOS: señal inequívoca de dominio → se saltan el filtro (enrutan directo aunque
# no haya entidad ni palabra de vocabulario). El RESTO son "genéricos" y SÍ pasan por el filtro.
# Las cadenas calzan EXACTO con las de grupos/precedencia_maxima. Crece por el ciclo verificado.
patrones_anclados:
  # de precedencia_maxima (disponibilidad del dato — dominio puro):
  - 'CUANTOS DIAS CON REPORTE'
  - 'DIAS CON REPORTE'
  - 'COBERTURA'
  - 'DISPONIBILIDAD'
  - 'DISPONIBLE'
  - 'HUELLA'
  - 'DENSIDAD'
  # de jerarquizar (nombran niveles del catálogo):
  - 'CUALES?\s+(CAMPOS?|POZOS?|ACTIVOS?|GERENCIAS?)\s+(TIENE|CONFORMAN|INTEGRAN|COMPONEN)'
  - '(CAMPOS?|POZOS?|ACTIVOS?)\s+(TIENE|CONFORMAN|INTEGRAN|COMPONEN)'
  - 'DE\s+QUE\s+(ACTIVO|VICEPRESIDENCIA|CAMPO|EMPRESA|GERENCIA|FILIAL)'
  - 'A\s+QUE\s+(ACTIVO|VICEPRESIDENCIA|CAMPO|EMPRESA|GERENCIA|FILIAL)'
  - 'ES\s+(UNA?\s+)?(FILIAL|ACTIVO|CAMPO|POZO|GERENCIA)'
  - 'DONDE\s+ESTA\s+COLGAD[OA]'
  - 'JERARQUIA'
  # de cuantificar (producción explícita):
  - 'QUE\s+PRODUJO'
  - 'PRODUCCION\s+DE'
  # de analizar (métricas/objetos del negocio):
  - 'QUE\s+CAMPOS?\s+PESA[N]?'
  - 'DETRACTORES'
  - 'GAP\b'
  - 'P50\b'
  - 'META\b'
  - 'DIFERIDAS'
  - 'MANTENIMIENTOS?'
  - 'EBITDA'
  - 'NOPAT'
  - 'COMO\s+VAMOS'
  - 'VAMOS\s+A\s+(LLEGAR|CERRAR|ALCANZAR)'
```

### 6.2 `config/vocabulario_dominio.yaml` — NUEVO

**[H-G]** Vocabulario alineado con `motor_Q.md` §1.2 + `CIERRE` (necesario para "proyección de
cierre de mayo"). Se quitaron `AGUA`/`REGALIAS` (ambiguos; "producción de agua" ya pasa por el
patrón anclado `PRODUCCION DE`). Contenido exacto:

```yaml
# vocabulario_dominio.yaml — Filtro de dominio (motor_Q.md §1.2, Motor Q v2 · Fase 1)
#
# Segundo criterio del filtro (el primero es detectar_entidad): palabras inequívocamente de
# producción. Fragmentos REGEX con límite de palabra (\b...\b) sobre texto NORMALIZADO (norm():
# UPPER, sin acentos). CONSERVADOR: si una palabra es ambigua, NO incluirla. Crece por el ciclo
# verificado. Nota: algunos términos (P50, DIFERIDAS, EBITDA…) también son patrones anclados —
# la redundancia es inofensiva (la pregunta ya se habría saltado el filtro por el patrón).
#
# ⚠ Se carga UNA vez al arranque del backend → editar exige REINICIAR los backends.

version: 1
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
  - POZOS?
  - CAMPOS?
  - ACTIVOS?
  - EBITDA
  - NOPAT
  - WORKOVER
  - NV04
  - CIERRE
```

### 6.3 `dominio.py` — NUEVO

```python
"""Filtro de dominio (motor_Q.md §1.2) — ¿la pregunta menciona vocabulario de producción?

Segundo criterio del filtro (el primero es detectar_entidad, en maquina_q.py). Lista corta y
conservadora en config/vocabulario_dominio.yaml. Módulo PURO: solo depende de normaliza (sin BD,
sin LLM) → testeable como patrones.py. Compilado UNA vez (reiniciar backend para recargar).

FORK conceptual de la mecánica de patrones.py (carga perezosa de YAML) @ 2026-08-02.
"""
import re
import pathlib

import yaml

from app.features.consulta_v2.normaliza import norm

_CFG_PATH = pathlib.Path(__file__).parent / "config" / "vocabulario_dominio.yaml"

_RX = False   # False = no cargado; None = cargado pero vacío; regex compilado = cargado


def _cargar():
    """Compila el vocabulario en un solo regex \\b(a|b|...)\\b. Idempotente."""
    global _RX
    cfg = yaml.safe_load(_CFG_PATH.read_text(encoding="utf-8"))
    vocab = [str(v) for v in (cfg.get("vocabulario") or []) if v]
    _RX = re.compile(r"\b(" + "|".join(vocab) + r")\b") if vocab else None
    return _RX


def hay_palabra_dominio(texto: str) -> bool:
    """True si el texto normalizado contiene alguna palabra del vocabulario de dominio."""
    global _RX
    if _RX is False:
        _cargar()
    if _RX is None:
        return False
    return bool(_RX.search(norm(texto)))
```

### 6.4 `patrones.py` — exponer el set de anclados y `es_anclado()`

**(a)** En `_cargar()`, reemplazar:

```python
    comp = {"max": [], "grupos": {}, "precedencia": list(cfg["precedencia_colision"])}
```

por:

```python
    comp = {"max": [], "grupos": {}, "precedencia": list(cfg["precedencia_colision"]),
            "anclados": set(cfg.get("patrones_anclados") or [])}
```

**(b)** Al FINAL del archivo, añadir:

```python


def es_anclado(patrones_lista) -> bool:
    """True si ALGUNO de los patrones que atrapó la Capa 1 es de dominio-anclado (motor_Q.md §1.2,
    D2): esos se saltan el filtro. Los patrones_lista son las cadenas EXACTAS del YAML que devolvió
    clasificar_capa1(). NOTA (H-H): en una colisión, clasificar_capa1 devuelve solo los patrones
    del grupo GANADOR — el vocabulario cubre los casos en que un patrón anclado quedó en el grupo
    perdedor (todos mencionan CAMPO/POZO/ACTIVO, que están en el vocabulario)."""
    return any(p in _get()["anclados"] for p in (patrones_lista or []))
```

### 6.5 `maquina_q.py` — aplicar el filtro en `clasificar()`

**(a)** Imports: reemplazar

```python
from app.features.consulta_v2.patrones import clasificar_capa1
```

por

```python
from app.features.consulta_v2.patrones import clasificar_capa1, es_anclado
from app.features.consulta_v2.dominio import hay_palabra_dominio
```

**(b)** Reemplazar el tramo de `clasificar()` que va desde
`grupo, patrones = clasificar_capa1(texto)` hasta el `if not entidad:` (inclusive) por:

```python
    grupo, patrones = clasificar_capa1(texto)
    capa, entidad, diag = "regex", None, None
    if grupo is not None:
        # FILTRO DE DOMINIO (motor_Q.md §1.2 · D2/D3): la regex atrapó la FORMA; confirmar el TEMA.
        # Solo sobre patrones GENÉRICOS — los anclados ya son señal de dominio y se saltan.
        if not es_anclado(patrones):
            entidad = detectar_entidad(texto)
            if not entidad and not hay_palabra_dominio(texto):
                # Ni entidad del catálogo ni palabra de producción → fuera de dominio (OUT).
                # D1: el token OUT es 'desconocido'. Se conservan los patrones para trazar en la
                # libreta POR QUÉ disparó la regex; la entidad queda en None.
                grupo, capa = "desconocido", "regex+filtro"
    else:
        r = clasificar_capa2(texto)
        grupo, entidad, diag, capa = r["grupo"], r.get("entidad"), r.get("diag"), "llm"
        patrones = []
    if not entidad:
        entidad = detectar_entidad(texto)   # backstop (también aporta en Capa 1)
```

El resto de `clasificar()` (bloque `log_id`/`registrar` y el `return {...}`) queda IGUAL. El
mensaje de `desconocido` sigue siendo el menú declarativo actual (`_mensaje`) — no se toca.

### 6.6 `clasificador_llm.py` — reforzar el prompt de Capa 2 para OUT

Reemplazar en `PROMPT_CLASIFICADOR`:

```python
Si la pregunta no encaja en ninguno (saludos, texto suelto, un nombre a secas): "desconocido".
```

por:

```python
Si la pregunta NO es de producción petrolera ni de la información del sistema (matemáticas,
geografía, cultura general, entretenimiento, finanzas no petroleras, saludos, texto suelto,
un nombre a secas): "desconocido".
```

No cambiar `GRUPOS_VALIDOS`, ni `format:"json"`, ni `NUM_PREDICT`, ni el timeout.

### 6.7 `senales.py` — **[H-B]** la Señal 3 (abandono) solo sobre desconocido del LLM

En `escanear()`, **(a)** añadir `capa_resolutora` al SELECT de pendientes. Reemplazar:

```python
        pend = conn.execute(sa.text("""
            SELECT id, ts, usuario, texto_pregunta, grupo_asignado
              FROM core.clasificacion_log
             WHERE veredicto='pendiente' AND ts >= now() - make_interval(days => :d)
             ORDER BY ts
        """), {"d": dias}).mappings().all()
```

por:

```python
        pend = conn.execute(sa.text("""
            SELECT id, ts, usuario, texto_pregunta, grupo_asignado, capa_resolutora
              FROM core.clasificacion_log
             WHERE veredicto='pendiente' AND ts >= now() - make_interval(days => :d)
             ORDER BY ts
        """), {"d": dias}).mappings().all()
```

**(b)** En el bloque de la Señal 3, reemplazar:

```python
            # Señal 3 — abandono tras 'desconocido': nada del usuario después, y ya pasó la ventana
            if f["grupo_asignado"] == "desconocido":
```

por:

```python
            # Señal 3 — abandono tras 'desconocido' del LLM (H-B): el OUT-por-filtro (regex+filtro)
            # es una salida CONFIADA — abandonar tras un off-topic es esperado, no señal de fallo.
            if f["grupo_asignado"] == "desconocido" and f["capa_resolutora"] == "llm":
```

`registrar_senal_v1()` (Señal 2) NO se toca: casa por similitud sobre cualquier pendiente reciente,
independientemente de la capa, que es lo correcto (reformular tras un OUT sí es señal útil).

### 6.8 `golden/run_golden.py` — soportar la traza `regex+filtro`

**Motivo:** hoy `por_capa = {"regex": 0, "llm": 0}` y `por_capa[got["capa_resolutora"]] += 1`
lanzaría **KeyError** con `regex+filtro`. Reemplazar la función `main()` completa por:

```python
def main():
    p = pathlib.Path(__file__).with_name("clasificacion_golden.yaml")
    casos = yaml.safe_load(p.read_text(encoding="utf-8"))
    ok, por_capa = 0, {}
    fallos = []
    for c in casos:
        got = clasificar(c["pregunta"], log=False)
        acierto = got["grupo"] == c["esperado"]
        ok += acierto
        capa = got["capa_resolutora"]
        por_capa[capa] = por_capa.get(capa, 0) + 1
        marca = "OK " if acierto else "XX "
        extra = "" if acierto else f"  -> {got['grupo']} ({capa}, diag={got.get('llm_diag')})"
        print(f"{marca}[{c['esperado']:<12}] {c['pregunta']}{extra}")
        if not acierto:
            fallos.append(c["pregunta"])

    n = len(casos)
    pct = 100 * ok // n if n else 0
    n_regex = por_capa.get("regex", 0)
    n_filtro = por_capa.get("regex+filtro", 0)
    n_llm = por_capa.get("llm", 0)
    pct_regex = 100 * n_regex // n if n else 0
    print(f"\nEXACTITUD: {ok}/{n} = {pct}%   (gate: >=90%)")
    print(f"CAPA 1 dominio (regex):   {n_regex}/{n} = {pct_regex}%   "
          f"(A4: si <50%, engordar patrones — señal, no bloqueante)")
    print(f"CAPA 1 fuera de dominio (regex+filtro): {n_filtro}/{n}")
    print(f"CAPA 2 (LLM):             {n_llm}/{n}")
    if fallos:
        print("\nFALLOS:")
        for f in fallos:
            print(f"  - {f}")
```

### 6.9 `golden/clasificacion_golden.yaml` — añadir casos OUT + guardas

Añadir al FINAL (no borrar ni editar los 34 existentes):

```yaml

# ---- OUT / fuera de dominio: regex atrapó la FORMA, el filtro rechaza el TEMA (motor_Q.md §1.2) ----
- pregunta: "¿Cuánto es la raíz cuadrada de 2?"
  esperado: desconocido
- pregunta: "Dame el precio del dólar mes a mes"
  esperado: desconocido
- pregunta: "¿Qué información hay de Bogotá?"
  esperado: desconocido
- pregunta: "¿Qué es HBOMAX?"
  esperado: desconocido
- pregunta: "¿Se ve recuperación en el dólar?"
  esperado: desconocido
# OUT que la regex NO atrapa → lo decide la Capa 2 (LLM). Model-dependent (verificar paridad):
- pregunta: "¿Cuál es la capital de Francia?"
  esperado: desconocido
- pregunta: "Cuéntame un chiste"
  esperado: desconocido

# ---- Guardas de NO-REGRESIÓN: dominio GLOBAL sin entidad → NO debe irse a OUT (Decisión D2) ----
- pregunta: "¿Cuál es el gap contra el presupuesto?"
  esperado: analizar
- pregunta: "¿Cuánto crudo se perdió este mes?"
  esperado: cuantificar
```

### 6.10 `tests/test_consulta_v2_clasificador.py` — tests del filtro

**[H-C]** `clasificar_capa1`/`es_anclado`/`hay_palabra_dominio` son PUROS → se importan al tope.
`clasificar` (maquina_q) arrastra `clasificador_llm.get_settings()` al importar → se importa
**LOCAL dentro de cada test** para no romper la colección de pytest si falta `.env`.

**(a)** En los imports del tope del archivo, reemplazar la línea existente

```python
from app.features.consulta_v2.patrones import clasificar_capa1
```

por

```python
from app.features.consulta_v2.patrones import clasificar_capa1, es_anclado
from app.features.consulta_v2.dominio import hay_palabra_dominio
```

**(b)** Añadir, tras `test_capa1_acentos_normalizados`, este bloque:

```python
# ---------------- Filtro de dominio (motor_Q.md §1.2) ----------------

def test_vocabulario_detecta_crudo():
    assert hay_palabra_dominio("¿cuánto crudo se perdió?") is True

def test_vocabulario_ignora_offtopic():
    assert hay_palabra_dominio("¿cuánto es la raíz cuadrada de 2?") is False

def test_anclado_detractores():
    g, pats = clasificar_capa1("¿cuáles son los detractores?")
    assert g == "analizar" and es_anclado(pats) is True

def test_no_anclado_cuantos_generico():
    g, pats = clasificar_capa1("¿cuánto es la raíz cuadrada de 2?")
    assert g == "cuantificar" and es_anclado(pats) is False

def test_anclados_existen_en_patrones():
    # Guarda de deriva (H-H): cada cadena de patrones_anclados existe entre los patrones reales.
    from app.features.consulta_v2 import patrones as P
    c = P._get()
    reales = {p for _, _, p in c["max"]}
    for pares in c["grupos"].values():
        reales |= {p for _, p in pares}
    faltan = c["anclados"] - reales
    assert not faltan, f"patrones_anclados no presentes entre los patrones: {faltan}"

# Filtro end-to-end SIN entidad ni vocabulario → OUT. No usa LLM (la regex atrapó) y detectar_entidad
# degrada a None sin BD → estable con o sin Postgres. log=False: no escribe libreta. Import LOCAL (H-C).
def test_filtro_offtopic_va_a_desconocido():
    from app.features.consulta_v2.maquina_q import clasificar
    d = clasificar("¿cuánto es la raíz cuadrada de 2?", log=False)
    assert d["grupo"] == "desconocido" and d["capa_resolutora"] == "regex+filtro"

def test_filtro_que_es_offtopic_va_a_desconocido():
    from app.features.consulta_v2.maquina_q import clasificar
    d = clasificar("¿qué es HBOMAX?", log=False)
    assert d["grupo"] == "desconocido" and d["capa_resolutora"] == "regex+filtro"

def test_filtro_vocabulario_conserva_grupo():
    from app.features.consulta_v2.maquina_q import clasificar
    d = clasificar("¿cuánto crudo se perdió este mes?", log=False)
    assert d["grupo"] == "cuantificar" and d["capa_resolutora"] == "regex"

def test_filtro_anclado_no_va_a_out():
    from app.features.consulta_v2.maquina_q import clasificar
    d = clasificar("¿cuál es el gap contra el presupuesto?", log=False)
    assert d["grupo"] == "analizar" and d["capa_resolutora"] == "regex"
```

### 6.11 `static/js/multitab_shell.js` — **[H-A]** etiqueta correcta de `capa_resolutora`

En `__cnRenderV2`, reemplazar:

```javascript
    var via = d.capa_resolutora === "regex" ? "regex" : "LLM";
```

por:

```javascript
    var __V2VIA = { regex: "regex", "regex+filtro": "regex + filtro", llm: "LLM" };
    var via = __V2VIA[d.capa_resolutora] || "LLM";
```

(Sin esto, un OUT-por-filtro mostraría "vía LLM" en la burbuja, aunque el LLM nunca intervino. La
función es PURA y la usan tanto el chat de Consulta v2 como la burbuja de Test Clas — el fix aplica
a ambos.) La libreta de Test Clas ya muestra `esc(f.capa_resolutora)` crudo ("regex+filtro"), OK.

### 6.12 `templates/main.html` — **[H-A]** cache-buster

Subir el parámetro `?v=` de `multitab_shell.js` y `colapsable.css` al valor `20260802c1`
(reemplazar el valor actual de `?v=` en ambas etiquetas; usar la MISMA cadena que ya exista, solo
cambiando el sufijo). Objetivo: que el navegador recargue el JS con el fix H-A.

---

## 7. Orden de ejecución

1. `config/patrones_grupo.yaml` — `patrones_anclados` (§6.1).
2. `config/vocabulario_dominio.yaml` — NUEVO (§6.2).
3. `dominio.py` — NUEVO (§6.3).
4. `patrones.py` — `anclados` + `es_anclado()` (§6.4).
5. `maquina_q.py` — imports + filtro (§6.5).
6. `clasificador_llm.py` — prompt (§6.6).
7. `senales.py` — Señal 3 restringida a `capa='llm'` (§6.7).
8. `golden/run_golden.py` — fix KeyError (§6.8).
9. `golden/clasificacion_golden.yaml` — casos OUT + guardas (§6.9).
10. `tests/test_consulta_v2_clasificador.py` — tests (§6.10).
11. `static/js/multitab_shell.js` — etiqueta de capa (§6.11).
12. `templates/main.html` — cache-buster (§6.12).
13. Correr TODAS las validaciones §8. Reiniciar backends antes de las validaciones que usan la API
    (§8.5) — los YAML se cargan al arranque.

---

## 8. Validaciones (comando → resultado esperado)

Desde `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend\`.

**8.0 · [H-F] Pre-check de BD/entidad ANTES del golden** (si falla, el golden dará OUT falsos):
```
set PYTHONPATH=.
uv run python -c "from app.features.consulta_v2.maquina_q import detectar_entidad; print('ENTIDAD OK' if detectar_entidad('Rubiales') else 'SIN BD - abortar golden')"
```
Esperado: `ENTIDAD OK`. Si imprime `SIN BD`, levantar Postgres antes de §8.4.

**8.1 · Compilación**
```
uv run python -c "import py_compile; [py_compile.compile(f,doraise=True) for f in ['app/features/consulta_v2/dominio.py','app/features/consulta_v2/patrones.py','app/features/consulta_v2/maquina_q.py','app/features/consulta_v2/clasificador_llm.py','app/features/consulta_v2/senales.py','app/features/consulta_v2/golden/run_golden.py']]; print('PY OK')"
```
Esperado: `PY OK`.

**8.2 · YAML válidos**
```
uv run python -c "import yaml; yaml.safe_load(open('app/features/consulta_v2/config/patrones_grupo.yaml',encoding='utf-8')); yaml.safe_load(open('app/features/consulta_v2/config/vocabulario_dominio.yaml',encoding='utf-8')); print('YAML OK')"
```
Esperado: `YAML OK`.

**8.3 · Frontend JS** (desde la raíz del repo):
```
node --check "c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\static\js\multitab_shell.js"
```
Esperado: sin salida de error (exit 0).

**8.4 · Tests unitarios** (puros no requieren BD; los `_engine_o_skip` se saltan sin Postgres):
```
uv run pytest tests/test_consulta_v2_clasificador.py -q
```
Esperado: todos PASAN (nuevos + previos). 0 fallos.

**8.5 · Golden** — **CON Postgres arriba** (§8.0 en verde). Backends de app abajo por RAM:
```
set PYTHONPATH=.
uv run python app/features/consulta_v2/golden/run_golden.py
```
Esperado:
- `EXACTITUD: >=90%`. Los 34 originales siguen correctos (0 regresión).
- Los 5 OUT de forma-de-dominio → `[desconocido]` vía `regex+filtro`.
- Las 2 guardas (`gap contra presupuesto` → analizar; `crudo se perdió` → cuantificar) OK.
- Los 2 OUT sin regex (`capital de Francia`, `chiste`) dependen del LLM: si SOLO esos dos fallan
  con qwen, el gate igual se cumple (41/43 = 95%); anotarlos para el prompt, no re-abrir el filtro.

**8.6 · Prueba por la API** (backend v2 en `:8000`, REINICIADO tras los cambios). **[H-D/H-E]**
Sin `curl`, con `urllib` (agnóstico de shell). Off-topic → OUT por filtro:
```
uv run python -c "import urllib.request,json; r=urllib.request.urlopen(urllib.request.Request('http://localhost:8000/consulta2/preguntar', data=json.dumps({'texto':'cuanto es la raiz cuadrada de 2','conversation_id':'plan-test'}).encode(), headers={'Content-Type':'application/json'})); d=json.load(r); print(d['grupo'], d['capa_resolutora'])"
```
Esperado: `desconocido regex+filtro`.

Dominio con vocabulario → se conserva:
```
uv run python -c "import urllib.request,json; r=urllib.request.urlopen(urllib.request.Request('http://localhost:8000/consulta2/preguntar', data=json.dumps({'texto':'cuanto crudo se perdio este mes','conversation_id':'plan-test'}).encode(), headers={'Content-Type':'application/json'})); d=json.load(r); print(d['grupo'], d['capa_resolutora'])"
```
Esperado: `cuantificar regex`.

Global anclado → no OUT:
```
uv run python -c "import urllib.request,json; r=urllib.request.urlopen(urllib.request.Request('http://localhost:8000/consulta2/preguntar', data=json.dumps({'texto':'cual es el gap contra el presupuesto','conversation_id':'plan-test'}).encode(), headers={'Content-Type':'application/json'})); d=json.load(r); print(d['grupo'], d['capa_resolutora'])"
```
Esperado: `analizar regex`.

**8.7 · [H-D] Limpiar las filas de prueba** (borra lo que insertó §8.6):
```
uv run python -c "import sqlalchemy as sa; from app.core.db import get_engine; e=get_engine(); conn=e.connect(); tx=conn.begin(); n=conn.execute(sa.text(\"DELETE FROM core.clasificacion_log WHERE conversation_id='plan-test'\")).rowcount; tx.commit(); conn.close(); print('borradas', n)"
```
Esperado: `borradas 3`.

**8.8 · Paridad gemma4 (139 / cuando aplique):** repetir §8.5 con `CONSULTA_LLM_MODEL=gemma4:latest`
apuntando al Ollama de 139. Esperado ≥90%. Los `regex+filtro` son model-independent (no tocan LLM);
solo cambian los 2 OUT sin regex y las trampas sin verbo.

---

## 9. Fuera de alcance (NO hacer)

- **Tratamiento rico de OUT** (`motor_Q.md` §6): cortesía LLM ≤30 palabras + redirección fija +
  chips. Es capa de RESPUESTA; se hará cuando los grupos respondan. Aquí `desconocido` conserva su
  menú declarativo (`_mensaje`).
- **Renombrar** `desconocido`→`out` en enums/golden/frontend/BD (Decisión D1).
- Cambiar el KPI `pct_capa1` de `log.listar` (Decisión D4).
- Grupos respondiendo (Fases 2–6 de `motor_Q.md`), `sesion_intents`, validador pre-render,
  flujo proactivo, migración `007_pg_trgm`.

---

## 10. Reglas no negociables

1. **NO** tocar `app/features/consulta/` (v1 congelada) ni archivos fuera del inventario §5.
2. **NO** hay migración de BD. Si un paso pide `ALTER`/`CREATE`, está mal — detenerse.
3. El filtro corre **SOLO** sobre patrones genéricos; **jamás** sobre anclados (D2).
4. Las cadenas de `patrones_anclados` calzan EXACTO con las de `grupos`/`precedencia_maxima`
   (el test `test_anclados_existen_en_patrones` debe pasar).
5. El vocabulario es conservador: no añadir palabras ambiguas. El set inicial es el de §6.2.
6. La Capa 2 mantiene el parseo defensivo: JSON malo/timeout → `desconocido` (nunca adivinar).
7. Reiniciar los backends tras editar YAML (se cargan al arranque).
8. El golden **crece, nunca se poda**: no borrar ni editar los 34 casos existentes.
9. **[H-B]** El único cambio en `senales.py` es restringir la Señal 3 a `capa='llm'`. NO tocar la
   Señal 1 (reformulación) ni la Señal 2 (`registrar_senal_v1`).
10. **R-nuevo (documentar, no resolver):** anclar `META\b` mantiene un raro falso positivo
    ("¿cuál es tu meta de vida?" → analizar), aceptado a cambio de no mandar a OUT preguntas
    globales de meta. Si aparece en la libreta, es material del ciclo verificado, no un bug.
11. Si una validación de §8 falla por algo no previsto aquí, **detener y reportar** — no improvisar
    fuera del inventario.

---

## 11. Registro de auditoría (flujo §0.2 — para trazabilidad)

Hallazgos del plan v1 corregidos en este v2:

| # | Hallazgo | Fix |
|---|---|---|
| H-A | `__cnRenderV2` mostraría "vía LLM" para `regex+filtro` (el LLM no intervino) | §6.11 mapa de capa + §6.12 cache-buster |
| H-B | Señal 3 de `senales.py` marcaría "sospecha" a OUT-por-filtro bien clasificados (ruido) | §6.7 restringe a `capa='llm'` |
| H-C | Import de `clasificar` a nivel de módulo podía romper la colección de pytest | §6.10 import local en tests de integración |
| H-D | One-liner de limpieza no hacía commit (no borraba) | §8.7 begin/commit/close explícito |
| H-E | `curl` con escapes frágil entre shells | §8.6 `urllib` en `uv run python` |
| H-F | El golden pasó a depender de Postgres (resolución de entidad) sin aviso | §3 requisito + §8.0 pre-check |
| H-G | Vocabulario con `AGUA`/`REGALIAS` ambiguos | §6.2 alineado a `motor_Q.md` + `CIERRE` |
| H-H | `es_anclado` solo ve patrones del grupo ganador en colisión | Documentado (§6.4) + cubierto por vocabulario; verificado caso a caso |
```