# Plan v2 (AUDITADO) — Precarga del reporte global desde el Login + caché anti-estampida + residencia del LLM

> **Modo:** ejecutable por un Executor SIN contexto ni acceso previo al repo. Rutas absolutas, código
> completo, decisiones cerradas, criterios verificables. NO desviarse; si algo no calza con el código
> real, **detener y reportar** (no improvisar).
>
> **Este es un v2 auditado** (flujo §0.2 del CLAUDE.md de INGESTA: Mapeo → Auditoría → Diagnóstico →
> Propuesta). La v1 fue corregida por 4 hallazgos verificados contra el código real (ver §2).

---

## 1. Contexto

App **ProdIA** (Flask, `:8020`) + sub-backend **INGESTA** (FastAPI, `:8000`). El panel derecho
"**Desempeño del mes**" (global ECP) del chat de **Consulta** (dentro del *MultiTab Shell*) NO depende de
ninguna pregunta: es el panorama global por defecto. Hoy solo empieza a cargar cuando el usuario hace
login → clic "Análisis avanzado de producción diaria" → pestaña Consulta. Recién ahí espera al LLM.

**Objetivo del negocio:** que el reporte **empiece a cargarse apenas se llega a la página tras el login**,
para que al abrir Consulta el panel ya esté listo (cache-HIT) y la latencia se absorba durante la
navegación.

---

## 2. Auditoría previa — hallazgos (verificados contra el código, no de memoria)

> Estos hallazgos **cambian el plan**. Se documentan para que el Executor entienda el porqué de cada
> decisión y NO "restaure" lo que se quitó a propósito.

### 🔴 H-A — `/analisis/desempeno_insight` es CÓDIGO MUERTO → **NO se precarga**
`window.__cnDesempInsight` (definido en `multitab_shell.js:1952`) **no tiene ningún call site**: un grep
de `__cnDesempInsight(` sobre todo el archivo devuelve **solo la definición**. Además su host
`el("cn-ins")` no existe como `id` en el DOM actual (en la línea 2787 `cn-ins` se usa como **clase**, con
`id="cn-foco-day-N"`), y el bloque que lo alojaba está oculto por `__CN_DESEMP_VISIBLE = false`
(línea 1289).
**Consecuencia:** el plan v1 precargaba una **llamada LLM cara** (proxy `timeout=90`) cuyo resultado
**nadie consume**. → **Eliminado del plan.** El panel real son **2** fetches cacheables, no 3.

### 🔴 H-B — Sin caché server-side, el prefetch multiplica la carga del LLM por cada login
`grep -i "cache"` sobre `INGESTA/Rep_Prod/backend/app/features/analisis/api.py` → **0 coincidencias**:
`/analisis/ejecutivo` **recalcula y re-invoca a Gemma en CADA petición** (~180 s con
`EJECUTIVO_USAR_LLM=true`, que está ON en 139). Hoy ese costo solo se paga cuando **alguien abre el
panel**; con el prefetch se pagaría **en cada login**. Como Ollama **serializa** las generaciones, N
logins casi simultáneos se encolan: el último superaría el `timeout=200` del proxy Flask.
Agravante verificado: `app.py:65` usa `"async_mode": "threading"` (**no** eventlet) y los proxies usan
`requests` **bloqueante** → cada petición en vuelo **ocupa un hilo** del servidor hasta 200 s.
**Consecuencia:** sin mitigación, el prefetch podría **degradar** el sistema en hora pico en vez de
mejorarlo. → **Se añade el PASO 2 (caché TTL + single-flight en el proxy Flask).**

### 🟡 H-C — La caché NO se implementa en FastAPI (respeta la decisión previa AF-A2)
`consulta_v2/respuesta_analizar.py:19` hace `from app.features.analisis.api import ejecutivo as
_ejecutivo_ep` y su docstring dice explícitamente: *"NO se refactoriza `_ejecutivo_core` — AF-A2"*.
Envolver/renombrar `ejecutivo()` en FastAPI tocaría el corazón del tablero **y** del grupo Analizar
(ambos verificados en navegador el 2026-08-03) y contradiría una decisión de auditoría previa.
**Consecuencia:** la caché va en el **proxy Flask** (`routes/api.py`), que es exactamente la ruta que usan
el navegador y el prefetch. `ejecutivo()` de FastAPI **no se toca**; Analizar (que la llama in-process,
sin pasar por Flask) queda **intacto y sin cachear** — correcto, porque usa `pulir=False` y su payload es
distinto (mezclarlos habría servido texto determinista al tablero en vez de la prosa de Gemma).

### 🟢 H-D — La clave de caché del prefetch es CORRECTA (confirmación positiva)
Verificado en `multitab_shell.js:387`: al abrir Consulta sin entidad se ejecuta
`window.__cnAnalizar(null)` → `__cnSeg="ecp"`, `__cnNivel=null`, `__cnPeriodo=null` →
`__cnCacheKey(null)` = **`"ecp|__global__|-|-"`** y `__cnSegQS(null)` = **`""`** (sin querystring).
El prefetch usa exactamente eso → **cache-HIT garantizado**. Sin este chequeo, el trabajo se habría
tirado silenciosamente.

**Resumen del cambio v1 → v2:** se elimina 1 fetch inútil (H-A), se añade la caché anti-estampida en el
lugar de menor riesgo (H-B + H-C) y se secuencia el prefetch para no ocupar 2 hilos a la vez.

---

## 3. Objetivo (qué debe quedar funcionando)

1. **PASO 1 — Residencia del LLM** *(idempotente; puede estar ya aplicado)*: cada llamada real a Ollama
   manda `keep_alive` configurable (default `-1`) → una vez caliente, Gemma **no se descarga a los 5 min**.
2. **PASO 2 — Caché TTL + single-flight en el proxy Flask** de `/api/analisis/ejecutivo` y
   `/api/analisis/desempeno`: N logins concurrentes ⇒ **1 sola** generación LLM; el resto la reutiliza.
3. **PASO 3 — Prefetch desde el login**: al cargar la página principal se piden, **en secuencia**,
   `/api/analisis/desempeno` y `/api/analisis/ejecutivo` con el scope global, guardándolos en las cachés
   JS existentes con la clave `"ecp|__global__|-|-"`.
4. **PASO 4 — Ping en el login de Flask: NO se ejecuta** (ver §7).

---

## 4. Prerequisitos

- Repo raíz (app padre): `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\`
  ⚠️ En el equipo donde se **prueba** puede existir otro clon del mismo `origin`
  (p. ej. `...\12112025_prodIA_v02\ProdIA-2.0\`). Aplicar en el clon que se ejecuta, o commit+push y
  `git pull` allá.
- Backend INGESTA: `...\INGESTA\Rep_Prod\backend\` (se levanta con `uv`).
- `node` (para `node --check`) y `py` (para `py_compile`) disponibles.
- **Regla de RAM:** en la máquina de desarrollo (8 GB) **NO** levantar backend+LLM+navegador. Solo
  chequeos estáticos. Runtime/navegador se valida en el **servidor de pruebas** (`:8088`, Gemma caliente).

---

## 5. Inventario de archivos (rutas absolutas)

**Se modifican (6):**

| # | Archivo | Paso |
|---|---|---|
| 1 | `...\INGESTA\Rep_Prod\backend\app\core\config.py` | 1 *(idempotente)* |
| 2 | `...\INGESTA\Rep_Prod\backend\app\features\analisis\api.py` | 1 *(idempotente)* |
| 3 | `...\INGESTA\Rep_Prod\backend\app\features\consulta_v2\clasificador_llm.py` | 1 *(idempotente)* |
| 4 | `...\INGESTA\Rep_Prod\backend\app\features\consulta_v2\respuesta_base.py` | 1 *(idempotente)* |
| 5 | `...\INGESTA\Rep_Prod\backend\app\features\consulta_v2\respuesta_out.py` | 1 *(idempotente)* |
| 6 | `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\routes\api.py` | 2 |
| 7 | `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\static\js\multitab_shell.js` | 3 |
| 8 | `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\templates\main.html` | 3 |

**NO tocar:** `consulta/` v1 (congelado), `warmup.py`, `analisis/api.py::ejecutivo()` (AF-A2 — solo se
edita `_llm_insight_once` en el Paso 1), DDL/migraciones, ni nada fuera de esta lista.

---

## 6. Especificación

### PASO 1 — `keep_alive` en las llamadas reales a Ollama *(idempotente)*

> **Antes de cada edición, verificar si ya está aplicada** (grep de la cadena nueva). Si aparece,
> **saltar** esa edición y reportarlo. Si no, aplicar el reemplazo EXACTO.

#### 1.1 `config.py` — setting + property
**Verificación:** grep `consulta_keep_alive`. Si existe → saltar 1.1 completo.

**Edición A** — buscar el bloque EXACTO:
```python
    # CONSULTA_WARMUP=false; en 139 dejarlo true.
    consulta_warmup: bool = True
```
reemplazar por:
```python
    # CONSULTA_WARMUP=false; en 139 dejarlo true.
    consulta_warmup: bool = True
    # keep_alive de CADA petición REAL a Ollama (analisis.ejecutivo, clasificador, respuesta_*): cuánto
    # queda residente el modelo tras esa llamada. "-1" = indefinido (139). 🔑 El warm-up deja el modelo
    # residente con keep_alive=-1, PERO una petición real SIN keep_alive resetea el keep-alive de Ollama
    # al default de 5 min → el modelo se descarga en el primer hueco de inactividad y la siguiente
    # petición vuelve a pagar el frío ~342s (síntoma: "el análisis principal demora una eternidad").
    # Con "-1" cada inferencia REAFIRMA la residencia indefinida. En dev con RAM ajustada poner
    # CONSULTA_KEEP_ALIVE="5m" (o "0") para que qwen no quede residente para siempre.
    consulta_keep_alive: str = "-1"
```

**Edición B** — buscar el bloque EXACTO:
```python
    kpi_cierre_ambar_pct: float = 0.93

def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
```
reemplazar por:
```python
    kpi_cierre_ambar_pct: float = 0.93

    @property
    def keep_alive_ollama(self):
        """Valor de keep_alive para el body de Ollama: int si es numérico ("-1"/"0"/"600" segundos),
        si no la string de duración tal cual ("5m", "10m"). Ollama exige el ENTERO -1 como número JSON
        (la string "-1" la interpretaría como duración Go inválida y fallaría); "5m" sí va como string."""
        v = self.consulta_keep_alive.strip()
        try:
            return int(v)
        except ValueError:
            return v

def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
```

#### 1.2 `analisis/api.py` — SOLO el body de `_llm_insight_once`
**Verificación:** grep `keep_alive` en el archivo. Si aparece → saltar.
Buscar el bloque EXACTO:
```python
        body = _json.dumps({"model": s.consulta_llm_model, "prompt": prompt, "stream": False,
                            "format": "json",
                            "options": {"temperature": 0, "num_predict": 2048,
                                        "num_ctx": 8192}}).encode()
```
reemplazar por:
```python
        body = _json.dumps({"model": s.consulta_llm_model, "prompt": prompt, "stream": False,
                            "format": "json", "keep_alive": s.keep_alive_ollama,
                            "options": {"temperature": 0, "num_predict": 2048,
                                        "num_ctx": 8192}}).encode()
```
> ⚠️ **NO tocar `ejecutivo()`** ni ninguna otra función de este archivo (AF-A2).

#### 1.3 `clasificador_llm.py`
**Verificación:** grep `KEEP_ALIVE`. Si aparece → saltar 1.3.

**A** — buscar:
```python
MODELO = _s.consulta_llm_model        # .env: CONSULTA_LLM_MODEL
```
reemplazar por:
```python
MODELO = _s.consulta_llm_model        # .env: CONSULTA_LLM_MODEL
KEEP_ALIVE = _s.keep_alive_ollama     # reafirma la residencia del warm-up (sin esto vuelve el frío)
```
**B** — buscar:
```python
        "format": "json",
        "options": {"temperature": 0, "num_predict": NUM_PREDICT},
```
reemplazar por:
```python
        "format": "json",
        "keep_alive": KEEP_ALIVE,
        "options": {"temperature": 0, "num_predict": NUM_PREDICT},
```

#### 1.4 `respuesta_base.py`
**Verificación:** grep `_KEEP_ALIVE`. Si aparece → saltar 1.4.
Buscar el bloque EXACTO:
```python
_MODELO = _s.consulta_llm_model
_ENV_TIMEOUT = 30


def _llm(prompt: str) -> str:
    body = json.dumps({
        "model": _MODELO, "prompt": prompt, "stream": False, "format": "json",
        "options": {"temperature": 0.8, "num_predict": 160},
    }).encode()
```
reemplazar por:
```python
_MODELO = _s.consulta_llm_model
_KEEP_ALIVE = _s.keep_alive_ollama   # reafirma la residencia del warm-up (sin esto vuelve el frío)
_ENV_TIMEOUT = 30


def _llm(prompt: str) -> str:
    body = json.dumps({
        "model": _MODELO, "prompt": prompt, "stream": False, "format": "json",
        "keep_alive": _KEEP_ALIVE,
        "options": {"temperature": 0.8, "num_predict": 160},
    }).encode()
```

#### 1.5 `respuesta_out.py`
**Verificación:** grep `KEEP_ALIVE`. Si aparece → saltar 1.5.

**A** — buscar:
```python
MODELO = _s.consulta_llm_model        # .env: CONSULTA_LLM_MODEL
```
reemplazar por:
```python
MODELO = _s.consulta_llm_model        # .env: CONSULTA_LLM_MODEL
KEEP_ALIVE = _s.keep_alive_ollama     # reafirma la residencia del warm-up (sin esto vuelve el frío)
```
**B** — buscar:
```python
        "format": "json",
        # temp alta = variedad: cada OUT debe sonar distinta y hablar del tema preguntado.
        "options": {"temperature": 0.8, "num_predict": NUM_PREDICT},
```
reemplazar por:
```python
        "format": "json",
        "keep_alive": KEEP_ALIVE,
        # temp alta = variedad: cada OUT debe sonar distinta y hablar del tema preguntado.
        "options": {"temperature": 0.8, "num_predict": NUM_PREDICT},
```

---

### PASO 2 — Caché TTL + single-flight en el proxy Flask *(mitiga H-B)*

**Archivo:** `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\routes\api.py`

#### 2.1 Imports
**Verificación:** revisar la cabecera del archivo. Asegurar que `os`, `time` y `threading` estén
importados. Si alguno falta, **añadir solo el que falte** junto a los imports existentes del tope del
archivo (no reordenar ni tocar los demás).

#### 2.2 Helper de caché
Insertar el siguiente bloque **inmediatamente ANTES** de la línea que define la ruta del catálogo
(buscar `@api_bp.route("/analisis/president")` e insertar **antes** de ese decorador; si no se encuentra,
insertar antes de `@api_bp.route("/analisis/desempeno")`):

```python
# ---- Caché TTL + single-flight para los paneles de análisis (2026-08-04) --------------------------
# POR QUÉ: /analisis/ejecutivo NO tiene caché en FastAPI (verificado) → cada petición re-invoca a Gemma
# (~180s con EJECUTIVO_USAR_LLM=true). Con la precarga desde el login, CADA login dispararía una
# generación; como Ollama serializa, N logins casi simultáneos se encolan y el último revienta el
# timeout=200 de este proxy. Además app.py usa async_mode="threading" con `requests` BLOQUEANTE → cada
# petición en vuelo ocupa un hilo.
# QUÉ HACE: (1) TTL — el payload global se reutiliza N minutos; (2) single-flight — si M peticiones
# piden la MISMA clave y no hay caché, solo UNA llama al backend y las otras esperan y reciben su
# resultado (evita la estampida). Solo se cachean respuestas BUENAS (200 + sin marca de error).
# NO toca FastAPI: `analisis/api.py::ejecutivo()` queda intacto (decisión AF-A2) y el grupo Analizar,
# que la llama in-process con pulir=False, NO pasa por aquí → sin contaminación cruzada de payloads.
_ANALISIS_TTL_S = int(os.getenv("ANALISIS_CACHE_TTL", "900"))   # 15 min; el reporte cambia 1 vez/día
_ANALISIS_CACHE = {}            # clave -> (expira_ts, payload, status)
_ANALISIS_GUARD = threading.Lock()      # protege _ANALISIS_CACHE y _ANALISIS_INFLIGHT
_ANALISIS_INFLIGHT = {}         # clave -> threading.Lock (uno por clave)


def _analisis_cache_get(clave):
    """Devuelve (payload, status) si hay entrada viva; None si no hay o expiró."""
    with _ANALISIS_GUARD:
        v = _ANALISIS_CACHE.get(clave)
        if not v:
            return None
        if v[0] <= time.time():
            _ANALISIS_CACHE.pop(clave, None)
            return None
        return v[1], v[2]


def _analisis_inflight_lock(clave):
    with _ANALISIS_GUARD:
        lk = _ANALISIS_INFLIGHT.get(clave)
        if lk is None:
            lk = threading.Lock()
            _ANALISIS_INFLIGHT[clave] = lk
        return lk


def _analisis_es_cacheable(payload, status):
    """Solo se cachean respuestas útiles. MISMO criterio que las guardas del frontend: nunca cachear
    un error (dejaría el panel mostrando basura sin reintentar hasta que expire el TTL)."""
    if status != 200 or not isinstance(payload, dict):
        return False
    if payload.get("encontrada") is False or payload.get("sin_datos") or payload.get("error"):
        return False
    if (payload.get("meta") or {}).get("generado_por") == "error":   # Gemma falló (ejecutivo)
        return False
    return True


def _analisis_proxy_cacheado(ruta, params, timeout):
    """Proxy con caché TTL + single-flight. `ruta` es el path en INGESTA (ej. '/analisis/ejecutivo')."""
    clave = ruta + "?" + "&".join(f"{k}={params[k]}" for k in sorted(params))
    hit = _analisis_cache_get(clave)
    if hit:
        return jsonify(hit[0]), hit[1]
    lock = _analisis_inflight_lock(clave)
    with lock:                                  # single-flight: solo 1 generación por clave
        hit = _analisis_cache_get(clave)        # double-check: otro hilo pudo llenarla mientras esperábamos
        if hit:
            return jsonify(hit[0]), hit[1]
        try:
            resp = requests.get(f"{INGESTA_API_URL}{ruta}", params=params, timeout=timeout)
            payload, status = resp.json(), resp.status_code
        except requests.RequestException as e:
            return jsonify({"error": f"INGESTA no disponible: {e}"}), 502
        if _analisis_es_cacheable(payload, status):
            with _ANALISIS_GUARD:
                _ANALISIS_CACHE[clave] = (time.time() + _ANALISIS_TTL_S, payload, status)
        return jsonify(payload), status
# ---- fin caché de análisis -----------------------------------------------------------------------
```

#### 2.3 Usar el helper en `/analisis/desempeno`
Buscar el bloque EXACTO:
```python
        resp = requests.get(f"{INGESTA_API_URL}/analisis/desempeno", params=params, timeout=45)
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": f"INGESTA no disponible: {e}"}), 502
```
reemplazar por:
```python
        return _analisis_proxy_cacheado("/analisis/desempeno", params, 45)
    except requests.RequestException as e:
        return jsonify({"error": f"INGESTA no disponible: {e}"}), 502
```

#### 2.4 Usar el helper en `/analisis/ejecutivo`
Buscar el bloque EXACTO:
```python
        resp = requests.get(f"{INGESTA_API_URL}/analisis/ejecutivo", params=params, timeout=200)
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": f"INGESTA no disponible: {e}"}), 502
```
reemplazar por:
```python
        return _analisis_proxy_cacheado("/analisis/ejecutivo", params, 200)
    except requests.RequestException as e:
        return jsonify({"error": f"INGESTA no disponible: {e}"}), 502
```

> **NO** aplicar la caché a `/analisis/president`, `/analisis/desempeno_insight`, `/analisis/catalogo`,
> `/analisis/densidad`, `/analisis/cobertura` ni a `/ebitda/*` — fuera de alcance de este plan.

---

### PASO 3 — Prefetch del reporte global desde el login

#### 3.1 `multitab_shell.js` — función `__cnPrewarmGlobal`
**Ubicación:** justo después de `__cnCacheKey`. Buscar el bloque EXACTO:
```javascript
  function __cnCacheKey(entidad) {
    return __cnSeg + "|" + (entidad || "__global__") +
           "|" + (__cnNivel || "-") + "|" + (__cnPeriodo || "-");
  }
```
reemplazar por (el original **seguido de** la función nueva):
```javascript
  function __cnCacheKey(entidad) {
    return __cnSeg + "|" + (entidad || "__global__") +
           "|" + (__cnNivel || "-") + "|" + (__cnPeriodo || "-");
  }

  // ── Prefetch del panel global "Desempeño del mes" (ECP) al CARGAR LA PÁGINA, antes de que el usuario
  // abra el shell. Pide los MISMOS endpoints que pinta el panel y los guarda en las MISMAS cachés con la
  // MISMA clave global → al abrir Consulta es cache-HIT (instantáneo) y, aunque no alcance a terminar,
  // deja a Gemma caliente. Clave verificada: al abrir Consulta sin entidad corre __cnAnalizar(null) →
  // __cnSeg="ecp", __cnNivel=null, __cnPeriodo=null → "ecp|__global__|-|-" y querystring vacío.
  //
  // 🔒 REGLAS (no relajar):
  //  1) NO toca el DOM: el shell aún no está montado. Solo fetch + validación + caché. Tampoco fija
  //     __cnEjecD / __cnDesempData (son estado de pintado; los setea paint cuando el panel se abre).
  //  2) Guardas de "no cachear errores" IDÉNTICAS a las del panel: un error cacheado dejaría el panel
  //     mostrando basura sin reintentar.
  //  3) SECUENCIAL (desempeño → ejecutivo), no paralelo: el servidor Flask usa async_mode="threading"
  //     con proxies `requests` bloqueantes, así que cada fetch en vuelo ocupa un hilo (el de ejecutivo
  //     hasta 200s). Encadenarlos mantiene 1 hilo a la vez por usuario.
  //  4) NO se precarga /analisis/desempeno_insight: window.__cnDesempInsight NO tiene call sites y su
  //     host #cn-ins no existe en el DOM actual (bloque oculto, __CN_DESEMP_VISIBLE=false) → sería una
  //     llamada LLM cara que nadie consume.
  var __cnPrewarmed = false;
  function __cnPrewarmGlobal() {
    if (__cnPrewarmed) return;
    __cnPrewarmed = true;
    var key = __cnCacheKey(null);   // "ecp|__global__|-|-"
    var qs = __cnSegQS(null);       // "" (panorama global ECP)

    // 1) Desempeño (Postgres, barato). Guarda SOLO payloads válidos (misma guarda que __cnAnalizar).
    var p1 = __cnDesempCache[key] ? Promise.resolve() :
      fetch("/api/analisis/desempeno" + qs)
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (d && d.encontrada !== false && !d.sin_datos && !d.sin_cierre) __cnDesempCache[key] = d;
        })
        .catch(function () {});   // best-effort: si falla, el panel lo reintenta con su flujo normal

    // 2) Análisis ejecutivo (LLM Gemma, caro) — DESPUÉS del anterior. Misma guarda que
    //    __cnAnalisisEjecutivo: segmento ECP (__cnPayloadEsFil===false) y generado_por!=="error".
    p1.then(function () {
      if (__cnEjecCache[key]) return;
      return fetch("/api/analisis/ejecutivo" + qs)
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (d && d.encontrada !== false && !d.sin_datos &&
              __cnPayloadEsFil(d) === false && (d.meta || {}).generado_por !== "error") {
            __cnEjecCache[key] = d;
          }
        })
        .catch(function () {});
    });
  }
```

#### 3.2 `multitab_shell.js` — exponer `prewarm`
Buscar la línea EXACTA:
```javascript
  window.MultiTabShell = { mount: mount, unmount: unmount };
```
reemplazar por:
```javascript
  window.MultiTabShell = { mount: mount, unmount: unmount, prewarm: __cnPrewarmGlobal };
```

#### 3.3 `templates/main.html` — disparar el prefetch
**Edición A** — buscar el bloque EXACTO (final del `DOMContentLoaded`):
```html
        // Ensure panel manager is initialized correctly
        setTimeout(() => {
            if (window.panelManager) {
                console.log('Panel manager found, checking analytics panel...');
                window.panelManager.panels.analytics.visible = true;
                window.panelManager.updateLayout();
            }
        }, 100);
    });
```
reemplazar por:
```html
        // Ensure panel manager is initialized correctly
        setTimeout(() => {
            if (window.panelManager) {
                console.log('Panel manager found, checking analytics panel...');
                window.panelManager.panels.analytics.visible = true;
                window.panelManager.updateLayout();
            }
        }, 100);

        // Precarga del reporte global "Desempeño del mes" (ECP) apenas carga la página tras el login:
        // arranca los fetches del panel derecho y calienta Gemma MIENTRAS el usuario navega hacia
        // "Análisis avanzado" → al abrir Consulta el panel es cache-HIT. Data-only: NO monta el shell.
        if (window.MultiTabShell && typeof window.MultiTabShell.prewarm === 'function') {
            window.MultiTabShell.prewarm();
        }
    });
```

**Edición B (obligatoria)** — bump del cache-buster; sin esto el navegador sirve el JS viejo:
buscar la línea EXACTA:
```html
<script src="{{ url_for('static', filename='js/multitab_shell.js') }}?v=20260802j1"></script>
```
reemplazar por:
```html
<script src="{{ url_for('static', filename='js/multitab_shell.js') }}?v=20260804a1"></script>
```

---

## 7. PASO 4 — Ping en el login de Flask · **NO EJECUTAR**

**Decisión cerrada:** NO se implementa. El Paso 3 ya calienta Gemma al pedir `/analisis/ejecutivo`
milisegundos después del login; un ping server-side adicional solo adelantaría ~1-2 s del redirect y
tocaría el flujo de autenticación (más riesgo, menos beneficio). Documentado para trazabilidad.

---

## 8. Orden de ejecución

1. **Paso 1** (1.1 → 1.5), verificando idempotencia en cada edición. Reportar cuáles se aplicaron y
   cuáles ya estaban.
2. **Paso 2** (2.1 → 2.4).
3. **Paso 3** (3.1 → 3.3).
4. **NO** ejecutar el Paso 4.
5. Validaciones (§10) y reporte final (§11).

---

## 9. Reglas no negociables

1. **NO tocar** `consulta/` v1 (congelado), `warmup.py`, `analisis/api.py::ejecutivo()` (AF-A2),
   DDL/migraciones, ni archivos fuera del inventario §5.
2. **NO precargar `/analisis/desempeno_insight`** (H-A: código muerto). Si el Executor "ve la
   oportunidad" de agregarlo, **NO** hacerlo.
3. `__cnPrewarmGlobal` **JAMÁS toca el DOM** ni fija `__cnEjecD`/`__cnDesempData`. Solo fetch +
   validación + escritura en `__cnDesempCache` / `__cnEjecCache`.
4. Los 2 fetches del prefetch van **en secuencia**, no en paralelo (H-B: hilos bloqueados).
5. Las guardas de "no cachear errores" deben ser EXACTAS a las del panel (frontend) y a
   `_analisis_es_cacheable` (backend). **Nunca** cachear un payload con `encontrada===false`,
   `sin_datos`, `sin_cierre`, `error`, segmento cruzado o `generado_por==="error"`.
6. La clave del prefetch debe ser **exactamente** `__cnCacheKey(null)` con el scope global por defecto
   (`"ecp|__global__|-|-"`). Si difiere, NO habrá cache-HIT y el trabajo se desperdicia.
7. **Bump obligatorio** del cache-buster en `main.html` (3.3.B).
8. `keep_alive` va como **clave de primer nivel** del body JSON de Ollama (hermana de `options`, **no**
   dentro de `options`).
9. La caché del Paso 2 va **solo** en el proxy Flask, **solo** en las 2 rutas indicadas.
10. **NO** levantar backend + LLM + navegador en la máquina de desarrollo (regla de RAM).

---

## 10. Validaciones (comando → resultado esperado)

### 10.1 Estáticas (máquina de desarrollo)
- `node --check "c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\static\js\multitab_shell.js"`
  → exit 0, sin salida.
- Desde `...\INGESTA\Rep_Prod\backend`:
  `py -m py_compile app/core/config.py app/features/analisis/api.py app/features/consulta_v2/clasificador_llm.py app/features/consulta_v2/respuesta_base.py app/features/consulta_v2/respuesta_out.py`
  → sin errores.
- `py -m py_compile "c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\routes\api.py"` → sin errores.
- Grep de confirmación: `__cnPrewarmGlobal` usa `__cnCacheKey(null)` y `__cnSegQS(null)`;
  `window.MultiTabShell` incluye `prewarm`; `main.html` referencia `?v=20260804a1`;
  `routes/api.py` contiene `_analisis_proxy_cacheado` usado en **exactamente 2** rutas.
- **No regresión estática:** `grep -c "desempeno_insight" routes/api.py` debe seguir devolviendo su ruta
  intacta (sin caché) y `analisis/api.py::ejecutivo` no debe tener cambios (solo `_llm_insight_once`).

### 10.2 Runtime / navegador (servidor de pruebas `:8088`, Gemma caliente)
Commit + push; en el servidor `git pull` + reiniciar backends. Con DevTools → **Network**, "Preserve log":

1. **Login.** Antes de hacer clic en nada, confirmar en Network **2** peticiones sin querystring:
   `GET /api/analisis/desempeno` → 200, y **después** (secuencial) `GET /api/analisis/ejecutivo` → 200.
   **NO** debe aparecer `desempeno_insight`.
2. Esperar a que ambas terminen.
3. Clic en **"Análisis avanzado de producción diaria"** → pestaña **Consulta**. El panel
   "**Desempeño del mes**" debe pintarse **de inmediato** y **NO** debe dispararse una nueva petición a
   `/api/analisis/ejecutivo` (cache-HIT JS). *(Sí aparecerá `/api/analisis/president`: está fuera de
   alcance por diseño, es no-LLM y rápido.)*
4. **Caché server-side (Paso 2):** abrir una **segunda pestaña/sesión** y repetir el login. Su
   `GET /api/analisis/ejecutivo` debe responder en **milisegundos** (servido por la caché del proxy),
   no en ~180 s.
5. **Residencia del LLM (Paso 1):** dejar inactivo **>5 min**, luego hacer una consulta en el chat
   (Motor v2) → debe seguir rápido (Gemma no se descargó). Opcional:
   `GET http://10.100.26.139:11434/api/ps` → modelo residente con `expires_at` lejano.
6. **No regresión:** chat normal, reportes y pestañas Ingesta/Control/Análisis/Test Clas funcionan;
   el grupo **Analizar** del Motor v2 sigue respondiendo (causal/proyección/diferidas/economía);
   0 errores nuevos en consola.

**Criterio de aceptación:** 1-4 se cumplen y 5-6 no muestran regresión.

### 10.3 Deploy a 139 (cuando el usuario lo apruebe)
`desplegar_version.bat` (raíz): `git pull` + migraciones + reinicio de backends. **No** requiere cambios
de datos ni de esquema. Repetir §10.2 en 139.

---

## 11. Reporte final que debe entregar el Executor

1. Qué ediciones del Paso 1 se **aplicaron** y cuáles ya **estaban** (idempotencia).
2. Confirmación de los Pasos 2 y 3 aplicados, con las líneas donde quedaron.
3. Salida literal de cada comando de §10.1.
4. Cualquier bloque "buscar EXACTO" que **no** haya coincidido → **detener y reportar** (no improvisar).

---

## 12. Fuera de alcance (explícito)

- **`/analisis/desempeno_insight`**: no se precarga ni se cachea (H-A: código muerto). **No se elimina**
  el código muerto en este plan — es limpieza aparte, con su propia decisión.
- **`/analisis/president`**: no se cachea ni se precarga (no-LLM, rápido, sin caché JS que aprovechar).
- **Prefetch por entidad / drill-down**: solo el panorama **global**. Los análisis por entidad siguen
  bajo demanda.
- **Caché en FastAPI / refactor de `ejecutivo()`**: descartado por AF-A2 (H-C). El grupo **Analizar**
  sigue sin caché (llama in-process con `pulir=False`; su payload NO debe mezclarse con el del tablero).
- **Invalidación explícita de la caché tras una ingesta**: se resuelve por TTL (15 min, configurable con
  `ANALISIS_CACHE_TTL`). El reporte cambia ~1 vez/día, así que el TTL es suficiente. Si se necesita
  invalidación inmediata, es un plan aparte.
- **`consulta/` v1 (congelado)**: sus llamadas LLM (`narracion.py`, `extraccion.py`) NO reciben
  `keep_alive` → en Motor **v1** el keep-alive volvería a 5 min. El panel "Desempeño del mes" no usa v1,
  así que el objetivo no se ve afectado. **Deuda anotada.**
- **Paso 4** (ping en login de Flask): documentado, NO ejecutado.
