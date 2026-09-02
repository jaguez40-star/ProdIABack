# plan_INICIATIVA-ANALIZAR_20260901 — Bloque «Ojo con esto» en el chat de ANALIZAR

> Plan v2 auditado (flujo profesional §10 de CLAUDE.md). Mapeo, auditoría y diagnóstico
> ejecutados ANTES de escribir esta especificación: 3 exploraciones de código + 1 diseño
> contrastado + verificación directa de cada afirmación que sostiene el diseño.

---

## 0. Contexto para el agente EXECUTOR

**Proyecto:** ProdIA — asistente conversacional de producción de Ecopetrol. Dos procesos:
Flask (frontend, :5029) y FastAPI «INGESTA» (backend, :5030). Este plan toca **solo el backend**.

**Raíz del repo backend:** `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\`
⚠️ El paquete Python vive con doble anidamiento: `backend\backend\app\...`. Todas las rutas de
este plan son absolutas.

**Qué se construye:** el grupo ANALIZAR del Motor Q v2 responde hoy «dónde está el faltante» y
«por qué», pero descarta hallazgos que el propio backend ya calcula en la misma llamada
(`d["flags"]` llega al chat y nadie lo lee). Se añade un bloque final `⟦Ojo con esto⟧` que
señala proactivamente: producto crítico, brecha concentrada, valle (con su estado
activo/recuperado), ritmo de cierre exigente, y comparación frente al mes anterior.

**Decisiones cerradas por el usuario (no reabrir):**
- Aparece en el **texto de la respuesta del chat** (no en el panel, no al abrir).
- Incluye los 4 flags existentes + comparativo vs mes anterior.
- El estado del valle (¿sigue abierto?) es información crítica: se incluye.
- **Cero riesgo:** solo añadir. Si un cálculo falla, el bloque no se emite y todo queda igual.

**Convenciones del módulo destino** (`consulta_v2/analizar/plantilla.py`):
- Bloques con marcador `⟦…⟧`; líneas de detalle con prefijo `  · `.
- Helpers de bloque devuelven `list[str]`; `[]` = «no se emite» (regla N5: nunca fabricar).
- Formateadores existentes a REUSAR: `_fmt(valor, prod)` (es-CO, GAS÷1e6), `_dia_mes(iso)`
  («2026-05-06» → «6 de mayo»), `_PROD_L` (nombres en minúscula), `_UNIDAD`.
- `calendar` se importa DENTRO de las funciones en `analisis/api.py`, no a nivel de módulo.

**Cómo correr los tests** (consola normal, no requiere admin):
```powershell
cd 'C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend'
.venv\Scripts\python.exe -m pytest tests/test_analizar.py tests/test_p50_referencia.py -q
```
Salida esperada hoy (baseline a confirmar en el Paso 0): todos pasando en esos dos archivos.
La suite global tiene 10 fallos preexistentes documentados y ajenos a este cambio.

---

## 1. Hallazgos de la auditoría (determinan la §3)

### 🔴 H1 — El motor de hallazgos YA existe y el chat lo descarta
`_flags_ejecutivo()` en `backend\backend\app\features\analisis\api.py:1355-1377` produce:

| tipo | condición | llaves del dict |
|---|---|---|
| `producto_critico` | `valor_pct < 60` | `severidad:"alta"`, `producto`, `pct` |
| `gap_concentrado` | `concentracion_pct >= 70` | `severidad:"media"`, `producto`, `concentracion_pct`, `campos` |
| `valle_activo` | siempre que haya valle | `severidad:"media"/"baja"`, `activo:bool`, `desde`, `hasta` |
| `pace_exigente` | `delta_pct >= 10` | `severidad:"media"`, `delta_pct`, `requerido_dia`, `promedio_dia`, `restantes` |

Viaja en el return de `ejecutivo()` bajo `"flags"` (`api.py:1996`). `respuesta_analizar.py:318`
lo recibe en `d` y lo pasa a `plantilla.causal(d,…)` en `:345`. Nadie en `consulta_v2` lo lee.
**No hay que construir un detector: hay que conectar el que existe.**

### 🔴 H2 — El mes anterior ya está en RAM, con el mes descartado
`api.py:1783-1798`: la consulta de `hist_anio` ya trae `(producto, mes, volumen)` de TODOS los
meses anteriores del año (`EXTRACT(month) < :hmo`), pero `_h.setdefault(_nom, []).append(_v)`
**tira el número de mes**. Verificado: `hist_anio` tiene UN solo consumidor (`_tarjetas_kpi`,
`:1987`). Convertir `_h` a dict-por-mes conserva `hist_anio` con valor idéntico
(`sum(d.values())/len(d)` ≡ `sum(l)/len(l)`). **Cero consultas SQL nuevas.**

### 🔴 H3 — Palabras que los tests prohíben (assert `not in`)
En `backend\backend\tests\test_analizar.py`: `HECHO`, `CAUSA`, `ACCIÓN`, `DELTA` (mayúsculas,
`:102`), `Pediste` (`:161`), `faltante`/`déficit` en minúscula en ruta en-meta (`:172` — el test
más importante del proyecto, REGLA CERO), `Formación` (`:214`), `COBERTURA PARCIAL`
(`:300/:335`), `703` (`:306`), `CONTEXTO ·`, `ACCIÓN ·`, `histórico ene-2023` (`:375-376`).
Ningún golden asevera texto (solo grupo de intención): `run_golden.py:31` compara únicamente
`got["grupo"]`. El gate `/consulta2/golden` ≥90% **no puede moverse** con este cambio.

### 🔴 H4 — `_fake_en_meta` hereda de `_fake_con_rezago`
`test_analizar.py:73-79`: `_fake_en_meta` llama a `_fake_con_rezago` y muta titular/tarjetas/
gap/valle, **pero no toca `flags`**. Al poblar los flags del fake base (Paso 4), el test
existente de la REGLA CERO (`:166-172`) pasa a ejercitar automáticamente el peor caso: bloque
emitido en ruta en-meta con vocabulario prohibido vigilado. Es un test de estrés gratuito.

### 🟡 H5 — Repetición: el cuerpo ya narra parte de los hallazgos
- `causal()` `:195-197` ya escribe «, con un valle del X al Y» en la apertura de CRUDO rezagado.
- `_dl_bloque()` `:83-88` ya emite la concentración («Los N mayores concentran el 75%»).
El bloque nuevo debe DEDUPLICAR: valle → solo el estado si las fechas ya se dijeron;
`gap_concentrado` → omitir si `_dl_bloque` ya se emitió para ese producto.

### 🟡 H6 — El cierre es un contrato con el drill
`respuesta_analizar.py:46-47` (`_CIERRE`/`_CIERRE_PROY`) ↔ `maquina_q.py:209-240`. Ya hubo un
fallo histórico por ofrecer algo que el motor no sabía responder. **El bloque solo AFIRMA,
nunca ofrece. Ninguna línea termina en `?`. El cierre no se toca.**

### 🟡 H7 — La ruta p50 exige que nada se anteponga al cuerpo
`test_p50_referencia.py:94`: `primera.startswith("No tengo un P50 para RUBIALES.")`. Al vivir
el helper DENTRO de `causal()`, las rutas p50/proyección/diferidas/economía quedan fuera **por
construcción** (nunca llaman a `causal()`).

### 🟢 H8 — El tablero y el proxy toleran la clave nueva
`multitab_shell.js` no lee `.flags` ni itera claves del payload (verificado por grep); el proxy
Flask (`routes/api.py:227`, caché TTL) reenvía JSON verbatim. Una clave añadida es inerte.
Matiz: tras desplegar, el caché TTL puede servir brevemente respuestas SIN la clave nueva — el
helper degrada a `[]`, inofensivo.

### 🟢 H9 — El comparativo mezcla bases distintas, y es aceptable
El REAL mensual del mes en curso es la fila `fecha=fin` (proyección de cierre); el mes anterior
es cierre real. Es la MISMA base que la tarjeta «vs promedio del año» ya en producción
(`hist_prom`). La redacción debe ser neutra («frente a julio, crudo bajó 6%») sin sugerir
cierre definitivo.

---

## 2. Estado actual (lo que el executor va a mirar)

- `plantilla.causal()` (`consulta_v2\analizar\plantilla.py:125-212`) tiene TRES ramas con
  return propio: producto-sin-rezago (`:142-160`), REGLA CERO (`:162-177`), con-rezago
  (`:179-212`). El patrón de bloque opcional está en `:199-207`.
- `respuesta_analizar._responder_core()` llama `fn(entidad=…, pulir=False)` en `:318` y
  `_plantilla.causal(d, ent_valor, producto, split, impacto)` en `:345`. **No se modifica.**
- Los fakes de test están en `test_analizar.py:42-79`; hoy `"flags": []` (línea 69).

---

## 3. Especificación

### 3.1 MODIFICAR `backend\backend\app\features\analisis\api.py` — comparativo del mes anterior

**(a) Líneas 1783-1798** — conservar el mes en `_h` (dict por mes, no lista):

```python
        hist_anio = {}
        _h = {}                                     # {prod: {mes:int -> vol:float}}
        for _nom, _mm, _v in c.execute(_b(f"""
                SELECT tp.nombre, EXTRACT(month FROM m.fecha)::int, SUM(m.volumen)
                FROM core.fact_produccion_mes_ecp m
                JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = m.tipo_producto_id
                JOIN core.dim_escenario es ON es.escenario_id = m.escenario_id
                WHERE es.nombre = 'REAL' AND EXTRACT(year FROM m.fecha) = :hy
                  AND EXTRACT(month FROM m.fecha) < :hmo AND {where('m')}
                GROUP BY 1, 2"""), {**base, "hy": y, "hmo": mo}).all():
            _v = float(_v or 0)
            if _v > 0:
                _h.setdefault(_nom, {})[int(_mm)] = _v
        for _nom, _vals in _h.items():
            if _vals:
                hist_anio[_nom] = round(sum(_vals.values()) / len(_vals))
```

(La consulta NO cambia; solo la acumulación. `hist_anio` conserva valor idéntico.)

**(b) En el return de `ejecutivo()` (`:1988-1999`)** — añadir UNA clave (aditivo puro):

```python
            # [2026-09-01] Comparativo vs mes anterior para el bloque de iniciativa del chat
            # (consulta_v2/analizar). Sale del desglose por mes que esta misma función ya
            # consultaba para hist_anio y descartaba. None en enero (la query filtra por año:
            # no se cruza a diciembre del año anterior — nunca inventar). `actual` es la fila
            # mensual REAL del mes en curso (proyección de cierre), la misma base que hist_prom.
            "comparativo_mes": ({
                "mes_anterior": f"{MESES_ES[mo - 1].lower()} {y}",
                "por_producto": {
                    t["producto"]: {"actual": t["real"], "anterior": _h.get(t["producto"], {}).get(mo - 1)}
                    for t in titular
                },
            } if mo > 1 else None),
```

`MESES_ES`, `mo`, `y`, `titular` y `_h` ya están en scope (verificado). Ningún consumidor
actual lee esta clave.

### 3.2 AÑADIR helper `_iniciativa_bloque()` en `backend\backend\app\features\consulta_v2\analizar\plantilla.py`

Colocar DESPUÉS de `_causas_bloque` (tras la línea ~122). Código completo:

```python
def _iniciativa_bloque(d, ya_dicho=None) -> list:
    """«Ojo con esto»: hallazgos que el motor ya calculó y la pregunta no pidió. [] si no hay
    nada — regla N5, como _dl_bloque/_causas_bloque. SOLO AFIRMA: ninguna línea termina en «?»
    (el cierre es un contrato con el drill de maquina_q; ofrecer algo que el motor no sabe
    responder es el fallo histórico documentado en respuesta_analizar.py:49-54).
    Vocabulario vigilado: jamás «faltante»/«déficit» (REGLA CERO, test_analizar.py:172) ni los
    tokens HECHO/CAUSA/ACCIÓN/DELTA/Pediste/CONTEXTO ·/ACCIÓN · que los tests prohíben.
    `ya_dicho`: set con lo que el cuerpo ya narró — {"valle_fechas"} y/o {"conc:CRUDO", ...} —
    para no repetir (el HECHO de crudo ya dice las fechas del valle; _dl_bloque ya dice la
    concentración). try/except integral: el contrato de cero riesgo es que un fallo aquí sea
    indistinguible de «sin hallazgos»."""
    try:
        ya = ya_dicho or set()
        flags = d.get("flags") or []
        lineas = []

        # 1) producto crítico (severidad alta — siempre primero)
        for f in flags:
            if isinstance(f, dict) and f.get("tipo") == "producto_critico" and f.get("pct") is not None:
                pl = _PROD_L.get(f.get("producto"), str(f.get("producto") or "").lower())
                lineas.append(f"  · {pl.capitalize()} está en zona crítica: {f['pct']}% del presupuesto, por debajo del 60%.")

        # 2) comparativo vs mes anterior (solo variaciones >= 5%; sin PPTO de por medio)
        cm = d.get("comparativo_mes") or {}
        mes_ant = cm.get("mes_anterior")
        for p, v in (cm.get("por_producto") or {}).items():
            act, ant = (v or {}).get("actual"), (v or {}).get("anterior")
            if not (mes_ant and act and ant):
                continue
            pct = round((act / ant - 1) * 100, 1)
            if abs(pct) < 5.0:
                continue
            pl = _PROD_L.get(p, p.lower())
            verbo = "subió" if pct > 0 else "bajó"
            u = _UNIDAD.get(p, "bbl")
            lineas.append(f"  · Frente a {mes_ant}, {pl} {verbo} {abs(pct)}% "
                          f"({_fmt(act, p)} vs {_fmt(ant, p)} {u}).")

        # 3) valle — el estado es lo crítico (¿sigue abierto?); si el cuerpo ya dijo las
        #    fechas (apertura de CRUDO rezagado), solo se emite el estado.
        for f in flags:
            if isinstance(f, dict) and f.get("tipo") == "valle_activo":
                if "valle_fechas" in ya:
                    lineas.append("  · Ese valle sigue abierto a la fecha de corte — todavía no se recupera."
                                  if f.get("activo") else
                                  "  · Ese valle ya se recuperó.")
                else:
                    rng = f"del {_dia_mes(f.get('desde'))} al {_dia_mes(f.get('hasta'))}"
                    lineas.append(f"  · El valle de crudo {rng} sigue abierto a la fecha de corte — todavía no se recupera."
                                  if f.get("activo") else
                                  f"  · El valle de crudo {rng} ya se recuperó.")

        # 4) ritmo de cierre exigente
        for f in flags:
            if isinstance(f, dict) and f.get("tipo") == "pace_exigente" and f.get("requerido_dia"):
                lineas.append(f"  · Para cerrar crudo en presupuesto se necesitan {_fmt(f['requerido_dia'], 'CRUDO')} bbl/día "
                              f"en los {f.get('restantes')} días restantes — un {f.get('delta_pct')}% sobre el promedio "
                              f"actual de {_fmt(f.get('promedio_dia'), 'CRUDO')} bbl/día.")

        # 5) brecha concentrada — solo si _dl_bloque NO la dijo ya para ese producto
        for f in flags:
            if isinstance(f, dict) and f.get("tipo") == "gap_concentrado":
                if f"conc:{f.get('producto')}" in ya:
                    continue
                pl = _PROD_L.get(f.get("producto"), str(f.get("producto") or "").lower())
                campos = ", ".join(f.get("campos") or [])
                sufijo = f": {campos}" if campos else ""
                lineas.append(f"  · La brecha de {pl} está concentrada: ~{f.get('concentracion_pct')}% en pocos campos{sufijo}.")

        if not lineas:
            return []
        return ["⟦Ojo con esto⟧"] + lineas[:3]      # tope duro: 3 hallazgos, por severidad
    except Exception:
        return []                                     # cero riesgo: fallo == sin hallazgos
```

### 3.3 MODIFICAR `plantilla.py` — enganche en las TRES ramas de `causal()`

El valle y el comparativo pueden existir sin rezago, así que el bloque va también en las ramas
tempranas (decisión: el estado del valle es información crítica). El **texto previo de cada
rama no se toca ni una letra** — solo se añade antes de cada `return`.

**(a) Rama producto-sin-rezago** — hoy `:157-160`. Tras `if ctx_line: lineas.append(ctx_line)`:

```python
        ini = _iniciativa_bloque(d)
        if ini:
            lineas.append("")
            lineas.extend(ini)
        return "\n".join(lineas)
```

**(b) Rama REGLA CERO** — hoy `:162-177`. Antes de su `return "\n".join(lineas)`:

```python
        ini = _iniciativa_bloque(d)
        if ini:
            lineas.append("")
            lineas.extend(ini)
```

**(c) Rama con-rezago** — hoy `:179-212`. Construir `ya_dicho` y engancharlo tras
`lineas.append("\n\n".join(bloques_prod))`:

```python
    ya = set()
    if d.get("valle") and any(t["producto"] == "CRUDO" for t in rez):
        ya.add("valle_fechas")            # la apertura de CRUDO ya dijo «con un valle del X al Y»
    for t in rez:
        if gap.get(t["producto"], {}).get("detractores"):
            ya.add(f"conc:{t['producto']}")   # _dl_bloque ya dijo la concentración
    ini = _iniciativa_bloque(d, ya)
    if ini:
        lineas.append("")
        lineas.extend(ini)
    return "\n".join(lineas).rstrip()
```

### 3.4 MODIFICAR `backend\backend\tests\test_analizar.py`

**(a) Ampliar `_fake_con_rezago`** (línea 69): sustituir `"flags": [],` por:

```python
        "flags": [
            {"tipo": "valle_activo", "severidad": "media", "activo": True,
             "desde": "2026-05-06", "hasta": "2026-05-12"},
            {"tipo": "pace_exigente", "severidad": "media", "delta_pct": 82.0,
             "requerido_dia": 428, "promedio_dia": 235, "restantes": 14},
        ],
        "comparativo_mes": {"mes_anterior": "abril 2026", "por_producto": {
            "CRUDO": {"actual": 8000.0, "anterior": 9000.0},
            "GAS": {"actual": 5000.0, "anterior": 4950.0}}},
```

(`_fake_en_meta` hereda esto sin tocarlo — H4: la REGLA CERO queda estresada gratis.)

**(b) Añadir al final del archivo** (sección nueva `# ---------------- iniciativa ----------------`):

```python
# ---------------- iniciativa (⟦Ojo con esto⟧, 2026-09-01) ----------------

def _fake_flags_todos():
    d = _fake_con_rezago()
    d["flags"] = [
        {"tipo": "producto_critico", "severidad": "alta", "producto": "CRUDO", "pct": 55.0},
        {"tipo": "gap_concentrado", "severidad": "media", "producto": "CRUDO",
         "concentracion_pct": 75.0, "campos": ["CAJUA", "CPO-09"]},
        {"tipo": "valle_activo", "severidad": "media", "activo": True,
         "desde": "2026-05-06", "hasta": "2026-05-12"},
        {"tipo": "pace_exigente", "severidad": "media", "delta_pct": 82.0,
         "requerido_dia": 428, "promedio_dia": 235, "restantes": 14},
    ]
    return d


def test_iniciativa_valle_activo_dice_estado():
    out = _plantilla.causal(_fake_con_rezago(), None, "CRUDO", _fake_split_vacio(), _fake_impacto_vacio())
    assert "⟦Ojo con esto⟧" in out
    assert "sigue abierto" in out
    # dedupe: la apertura ya dijo las fechas; el bloque no las repite
    assert out.count("6 de mayo") == 1


def test_iniciativa_valle_recuperado():
    d = _fake_con_rezago()
    d["flags"][0]["activo"] = False
    out = _plantilla.causal(d, None, "CRUDO", _fake_split_vacio(), _fake_impacto_vacio())
    assert "ya se recuperó" in out and "sigue abierto" not in out


def test_iniciativa_comparativo_mes_anterior():
    out = _plantilla.causal(_fake_con_rezago(), None, "CRUDO", _fake_split_vacio(), _fake_impacto_vacio())
    assert "abril 2026" in out and "bajó" in out          # 8000 vs 9000 = −11.1%
    assert "subió" not in out                              # GAS varía 1% < umbral 5%: no se emite


def test_iniciativa_regla_cero_emite_sin_contaminar():
    # _fake_en_meta HEREDA los flags de _fake_con_rezago: la REGLA CERO recibe el bloque y
    # el vocabulario sigue limpio. Complemento activo de test_regla_cero_no_inventa_rezago.
    r = _ra.responder("¿por qué está corto Castilla?", entidad="CASTILLA",
                      _ejecutivo_fn=lambda **k: _fake_en_meta(**k), _split_fn=_fake_split_vacio,
                      _diferidas_fn=_fake_impacto_vacio)
    assert "no hay rezago" in r.lower()
    assert "faltante" not in r.lower() and "déficit" not in r.lower()
    assert "⟦Ojo con esto⟧" in r


def test_iniciativa_sin_material_no_emite():
    d = _fake_con_rezago()
    d["flags"] = []; d["comparativo_mes"] = None
    out = _plantilla.causal(d, None, "CRUDO", _fake_split_vacio(), _fake_impacto_vacio())
    assert "⟦Ojo con esto⟧" not in out


def test_iniciativa_sin_tokens_prohibidos():
    out = _plantilla.causal(_fake_flags_todos(), None, "CRUDO", _fake_split_vacio(), _fake_impacto_vacio())
    ini = out[out.index("⟦Ojo con esto⟧"):]
    for tok in ("HECHO", "CAUSA", "ACCIÓN", "DELTA", "Pediste", "Formación",
                "COBERTURA PARCIAL", "CONTEXTO ·", "ACCIÓN ·", "histórico ene-2023"):
        assert tok not in ini
    for tok in ("faltante", "déficit"):
        assert tok not in ini.lower()
    assert "?" not in ini                                  # H6: el bloque solo afirma


def test_iniciativa_tope_tres_lineas():
    out = _plantilla.causal(_fake_flags_todos(), None, "CRUDO", _fake_split_vacio(), _fake_impacto_vacio())
    ini = out[out.index("⟦Ojo con esto⟧"):]
    assert sum(1 for l in ini.split("\n") if l.startswith("  · ")) <= 3


def test_iniciativa_flags_malformados_no_rompen():
    d = _fake_con_rezago()
    d["flags"] = [{"tipo": "producto_critico"}, {"tipo": "desconocido_futuro"}, None, "basura"]
    d["comparativo_mes"] = {"mes_anterior": "abril 2026", "por_producto": {"CRUDO": None}}
    out = _plantilla.causal(d, None, "CRUDO", _fake_split_vacio(), _fake_impacto_vacio())
    assert isinstance(out, str)                            # no lanza; degrada


def test_iniciativa_solo_en_causal():
    r = _ra.responder("¿cómo cerraría el mes?", entidad=None,
                      _ejecutivo_fn=lambda **k: _fake_con_rezago(**k), _split_fn=_fake_split_vacio,
                      _diferidas_fn=_fake_impacto_vacio)
    if "proyección" in r.lower() or "cerrar" in r.lower():
        assert "⟦Ojo con esto⟧" not in r
```

⚠️ Nota sobre firmas: los tests existentes llaman `causal(fake, None, "CRUDO", split)` con 4
args y a veces 5 (`impacto`). Verificar la firma real de `causal` antes de escribir los tests
nuevos y ajustar la posición de `_fake_impacto_vacio()` a lo que la firma exija — copiar el
patrón de la llamada existente en `test_analizar.py:371`.

---

## 4. Orden de ejecución

| # | Paso | Verificación | Si falla |
|---|---|---|---|
| 0 | Baseline: `pytest tests/test_analizar.py tests/test_p50_referencia.py -q` | anotar N pasados | DETENTE: baseline roto es problema previo |
| 1 | §3.2 — helper `_iniciativa_bloque` en `plantilla.py` (sin conectar) | `py_compile` OK; suite igual al baseline | revisar sintaxis |
| 2 | §3.3 — enganche en las 3 ramas de `causal()` | suite **igual al baseline** (flags aún `[]` en fakes → bloque no emite) | el helper emite sin material: revisar contrato `[]` |
| 3 | §3.4a — ampliar `_fake_con_rezago` | suite igual al baseline (los asserts `not in` vigilan el bloque nuevo) | hay un token prohibido en la redacción del helper: corregir TEXTO, jamás el assert |
| 4 | §3.4b — tests nuevos | los 9 pasan | ajustar según firma real de `causal` |
| 5 | §3.1 — `comparativo_mes` en `api.py` | `py_compile` + `pytest tests/test_analisis_focos_gap.py tests/test_analizar.py -q` | revisar scope de variables |
| 6 | Suite completa: `pytest tests/ -q` | mismos 10 fallos preexistentes, ni uno más | comparar contra baseline |
| 7 | Golden: no aplica reejecutar en local (BD congelada); el gate no puede moverse (H3) | — | — |

**Corte de fase:** los pasos 0-4 son entregables por sí solos (bloque con flags, sin
comparativo — el helper degrada si `comparativo_mes` no existe). Si el paso 5 se complica,
parar ahí sin dejar nada a medias.

---

## 5. Reglas no negociables

1. **No tocar** `maquina_q.py`, el clasificador, `respuesta_analizar.py`, ni los cierres
   `_CIERRE`/`_CIERRE_PROY` (H6).
2. **No modificar ningún assert existente.** Si un test se pone rojo, se corrige la redacción
   del helper — nunca el test.
3. **El texto actual de las tres ramas de `causal()` no cambia ni una letra**: solo se añade.
4. Ninguna línea del bloque termina en `?` (H6). Ninguna contiene «faltante», «déficit»,
   `HECHO`, `CAUSA`, `ACCIÓN`, `DELTA`, `Pediste`, `CONTEXTO ·`, `ACCIÓN ·` (H3).
5. Ningún dato se fabrica: sin flag → sin línea; enero → sin comparativo (no cruzar al año
   anterior); `anterior` None/0 → sin línea.
6. Tope duro: 3 líneas de hallazgo. Umbral del comparativo: |Δ| ≥ 5%.
7. `pulir=False` se mantiene: nada de esto pasa por el LLM (mismo argumento que
   `capacidades.py` — un inventario redactado por el modelo promete lo que no existe).
8. La consulta SQL de `hist_anio` no cambia; solo la acumulación en `_h`.

---

## 6. Validación

### 6.1 Estática (executor)

```powershell
cd 'C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend'
.venv\Scripts\python.exe -m py_compile app\features\consulta_v2\analizar\plantilla.py app\features\analisis\api.py
.venv\Scripts\python.exe -m pytest tests/test_analizar.py tests/test_p50_referencia.py -q
.venv\Scripts\python.exe -m pytest tests/ -q
```
Esperado: 9 tests nuevos en verde; baseline intacto; los 10 fallos preexistentes sin cambios.

### 6.2 Humana (usuario) — la BD local está congelada: se valida en PRUEBAS

Tras `git pull` + reiniciar INGESTA en el servidor de pruebas:

| Pregunta en el chat | Esperado |
|---|---|
| «analiza el comportamiento del producto crudo» | La respuesta cierra con `⟦Ojo con esto⟧`; máx. 3 líneas; el comparativo cuadra con la gráfica mensual del panel |
| Pregunta por un producto/entidad **en meta** | Si hay valle o comparativo relevante, el bloque aparece SIN mencionar faltante; si no hay nada, no aparece |
| «¿cómo vamos con la proyección?» | Sin bloque (exclusivo de causal) |
| F12 → Console | 0 errores; el tablero pinta idéntico (H8) |

**El único que marca ✅ es el usuario.** Estado hasta entonces: «implementado, PENDIENTE de
validación humana».

### 6.3 Despliegue (pipeline configurado — sin desvíos)

Backend solamente → commit a GitHub `main` → `git pull` en Pruebas → validar §6.2 →
`migrar-a-azure` (3 tiempos; el default ya publica en `prodiav2`) → en el 139: `git pull` +
reiniciar INGESTA. ⚠️ El proxy Flask cachea `/analisis/ejecutivo` (TTL): reiniciar Flask tras
el despliegue para no servir payloads viejos sin la clave nueva (degrada a «sin bloque», no
rompe — H8).

---

## 7. Fuera de alcance

- Comparación contra el mismo mes del año anterior (solo mes previo del año en curso).
- La causa documentada por campo (`detractores[].eventos` / `_comentarios_campo_mes`): existe
  y no se usa — candidato al siguiente paso, no a este.
- `campos_sin_meta`, `reconciliado`/`desfase_pct`, `valle_diagnostico` por pozo: material
  identificado para futuras iteraciones.
- Cualquier cambio en frontend, panel derecho, cierres del chat o clasificador.
- El pulido LLM (`secciones`) sigue descartado con `pulir=False`.
