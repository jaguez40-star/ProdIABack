# HALLAZGO — El clasificador manda "¿cuántos X tiene Y?" a Cuantificar, no a Jerarquizar

**Fecha:** 2026-08-02 · **Estado (2026-08-03): CERRADO — los 3 sub-hallazgos (2.1, 2.2, 2.3)
resueltos.** Ver §5.
**Severidad:** media-alta — no da datos falsos (Cuantificar responde con datos reales de OTRA
pregunta), pero ignora por completo la intención del usuario en una construcción muy natural del
español ("¿cuántos pozos tiene Castilla?").

---

## 1. Síntoma observado

Dos preguntas de **conteo de jerarquía**, probadas en Motor v2 sobre entidades reales:

| Pregunta | Clasificó como | Debió ser |
|---|---|---|
| «¿Cuántos pozos tiene campo Castilla?» | Cuantificar → respondió la producción de crudo de Castilla (dato real, pregunta distinta) | Jerarquizar (conteo de pozos) |
| «La vicepresidencia GOR, ¿cuántas gerencias tiene?» | Cuantificar → respondió la producción de crudo de "la Gerencia GOR" | Jerarquizar (conteo de gerencias) **+** ver hallazgo 3 abajo |

En ambos casos el bot no dio un dato falso — dio el dato **correcto a una pregunta que nadie hizo**.

---

## 2. Causa raíz — tres hallazgos independientes

### 2.1 — El patrón genérico de Cuantificar es demasiado amplio y gana por precedencia

Verificado con `clasificar_capa1` directo:

```
"¿Cuántos pozos tiene campo Castilla?"          -> cuantificar, patrón: CUANT[OA]S?\b
"La vicepresidencia GOR, ¿cuántas gerencias tiene?" -> cuantificar, patrón: CUANT[OA]S?\b
```

`'CUANT[OA]S?\b'` (cuantificar) dispara con **cualquier** "cuánto/cuántos/cuánta/cuántas" en
cualquier parte del texto. `precedencia_colision: [analizar, cuantificar, jerarquizar]`
(`patrones_grupo.yaml:93`) hace que Cuantificar **siempre gane el empate** contra Jerarquizar.

🔑 **El proyecto ya resolvió esta MISMA trampa una vez, para otro sustantivo:** «¿cuántos días con
reporte hay de X?» trae "CUANTOS" pero pregunta disponibilidad, no cifra — por eso existe
`precedencia_maxima.jerarquizar` con `'CUANTOS DIAS CON REPORTE'`/`'DIAS CON REPORTE'`, evaluados
**antes** que los patrones normales de grupo. Esa protección nunca se generalizó a
`"cuántos (pozos|campos|gerencias|activos) tiene X"` — la misma clase de trampa, con otros
sustantivos.

### 2.2 — El patrón de conteo de Jerarquizar no cubre GERENCIA, y exige "cuáles" no "cuántos"

`patrones_grupo.yaml:44`:
```yaml
- '(CAMPOS?|POZOS?|ACTIVOS?)\s+(TIENE|CONFORMAN|INTEGRAN|COMPONEN)'
```
Falta `GERENCIAS?` en la alternativa. La variante que sí la incluye (`patrones_grupo.yaml:43`)
exige el prefijo `CUALES?` inmediatamente antes del sustantivo — "cuántas gerencias tiene" no
matchea porque dice "cuántas", no "cuáles". Para GERENCIA, ningún patrón de Jerarquizar puede
ganar la carrera aunque se arreglara 2.1: no hay patrón que la reconozca en absoluto en esta forma.

### 2.3 — El resolver de Cuantificar no hereda el "puente" de level-shift que Jerarquizar ya tiene

Verificado contra la BD real — `resolver('GOR')` en `consulta_v2/cuantificar/resolver.py` devuelve
**una sola identidad**: `{'nivel': 'gerencia', 'rama': 'A', 'valor': 'GOR'}`. No hay colisión que
resolver mal — GOR sencillamente no existe como código de `dim_vicepresidencia` en el índice de
Cuantificar, solo como valor de `dim_fuente.gerencia`.

Esto es el mismo *level-shift* documentado en la sesión S28 del proyecto (`core.map_campo_robustez`):
la columna `dim_fuente.gerencia` de INGESTA es, en la jerarquía real de negocio, **vicepresidencia**
(GOR/GAA/GNS son vicepresidencias que quedaron mal-nombradas "gerencia" en el esquema fuente).
**`respuesta_jerarquizar.py` ya construyó el puente** para esto ("educar sin negar el término del
usuario", vía `map_campo_robustez`) — pero el resolver de Cuantificar es un fork independiente
(`# FORK de consulta/resolver.py @ 2026-08-02`) que nunca heredó ese puente: etiqueta literal con
el nombre de columna de INGESTA (`_NIVEL_TEXTO["gerencia"] = "la Gerencia"`), sin saber que
semánticamente es una vicepresidencia. Por eso responde **"la Gerencia GOR"** cuando el usuario dijo
explícitamente **"la vicepresidencia GOR"**.

Este tercer hallazgo es independiente de 2.1/2.2: aunque el enrutamiento se arreglara mañana y la
pregunta llegara a Jerarquizar correctamente, si en algún punto Cuantificar vuelve a resolver una
entidad de este tipo (p. ej. en un N1 de producción: "cuánto produjo GOR"), seguiría etiquetándola
mal.

---

## 3. Camino — para el ciclo de entrenamiento del clasificador (NADA implementado)

Estos tres hallazgos son candidatos para el ciclo verificado de `audit_motor_clas.md §3`
(Control 3 / `revisar_lote.py`), no un parche directo:

1. **Generalizar `precedencia_maxima.jerarquizar`** con un patrón para conteo de jerarquía
   ("CUANTOS? (POZOS|CAMPOS|GERENCIAS|ACTIVOS) TIENE"), evaluado antes que
   `'CUANT[OA]S?\b'` — mismo mecanismo que ya protege "cuántos días con reporte".
2. **Añadir `GERENCIAS?` a la alternativa** de `'(CAMPOS?|POZOS?|ACTIVOS?)\s+(TIENE|...)'
   '` en `grupos.jerarquizar`, y considerar si "cuántas" debe aceptarse junto a "cuáles" en el
   patrón con prefijo.
3. **Extender el resolver de Cuantificar con el mismo puente de level-shift** que ya tiene
   `respuesta_jerarquizar.py` (leer `core.map_campo_robustez` para reconocer que
   `dim_fuente.gerencia` es, en realidad, vicepresidencia) — o, alternativamente, que Cuantificar
   reuse directamente la resolución de nivel de Jerarquizar en vez de mantener un catálogo de
   niveles propio y desincronizado.

Cualquiera de las tres requiere el golden correspondiente en verde antes de cerrarse — no se toca
`patrones_grupo.yaml` sin ese ciclo (regla explícita del propio archivo).

---

## 4. Cómo reproducir el diagnóstico (read-only, sin LLM)

```python
# desde INGESTA/Rep_Prod/backend, single-proceso:
from app.features.consulta_v2.patrones import clasificar_capa1
from app.features.consulta_v2.cuantificar.resolver import resolver

print(clasificar_capa1("¿Cuántos pozos tiene campo Castilla?"))
print(clasificar_capa1("La vicepresidencia GOR, ¿cuántas gerencias tiene?"))
print(resolver("GOR"))   # -> [{'nivel': 'gerencia', 'rama': 'A', 'valor': 'GOR'}], una sola identidad
```

> ⚠️ Las referencias de línea/salida de arriba son del estado PREVIO a la resolución (2026-08-02).
> Tras los commits `a0db67e` (R1+R3) y `a9c9c5d` (R2), la primera línea clasifica `jerarquizar`
> (no `cuantificar`) y `resolver("GOR")` sigue devolviendo `nivel:'gerencia'` pero ahora con
> `puente:True` — el diagnóstico se conserva como registro histórico.

---

## 5. Resolución (2 planes auditados, 2026-08-03)

### 5.1 — Causas 2.1 + 2.2 (enrutamiento): RESUELTAS (commit `a0db67e`, Plan A "R1+R3")

Nuevo patrón en `precedencia_maxima.jerarquizar` (`config/patrones_grupo.yaml`) — mismo mecanismo
que ya protegía "días con reporte": `CUANT[OA]S?\s+(CAMPOS?|POZOS?|ACTIVOS?|GERENCIAS?)\s+
(TIENE[N]?|CONFORMAN|INTEGRAN|COMPONEN|AGRUPA|HAY\s+EN)` — **exige el verbo estructural**. Sin él, la
auditoría verificó que el patrón se tragaba 5 preguntas legítimas de `analizar`/`cuantificar` desde
`precedencia_maxima` (que gana sobre todo) — regresión evitada antes de codificar, no encontrada
después. No se ancla (sin entidad, sigue pasando por el filtro de dominio → Capa 2).

**R3 (gap adicional hallado en la propia auditoría, no en el hallazgo original):** ningún módulo
calculaba el conteo de pozos — estaba diseñado en `variables_cuantificables.yaml → conteos:` pero
nunca implementado. `respuesta_jerarquizar.py` ahora añade "Pozos: N" (`COUNT(DISTINCT uwi)` en
`robustez_v02.ops.wells_attributes`, por los `rob_field` del nivel — join key verificado: Castilla=437,
Activo Castilla=766) en campo/activo/gerencia/vicepresidencia, con degradación con gracia si
`robustez_v02` no está disponible (p. ej. 139).

Plan: `Planes/plan_conteo_jerarquia_R1_R3_2026-08-03.md`.

### 5.2 — Causa 2.3 (etiqueta "la Gerencia GOR" en producción): RESUELTA (commit `a9c9c5d`, Plan B "R2")

`cuantificar/resolver.py` marca `puente=True` cuando un nivel resuelto `"gerencia"` es
**EXCLUSIVAMENTE** una vicepresidencia en `core.map_campo_robustez` (diferencia de conjuntos
`rob_vicepresidencia - rob_gerencia`, calculada en vivo — nunca una lista fija). `cuantificar/
ejecutor.py` usa esa marca para mostrar "la Vicepresidencia" en el texto de N1-N4, sin tocar el
`nivel` que usa la consulta SQL (sigue filtrando `dim_fuente.gerencia`, la columna correcta).

🔑 **Autocorrección durante la verificación del propio plan:** el primer borrador solo excluía el
código `GAN` como "ambiguo" (existe como vicepresidencia y como gerencia real distintas en robustez);
la ronda de verificación encontró que `rob_vicepresidencia ∩ rob_gerencia = {CPV, GAN, GXO}` — 3
códigos, no 1. La *lógica* del código (`vps - gers`) siempre calculó esto correctamente en vivo; el
error estaba en la narrativa del plan y en una validación con el conteo hardcodeado, corregidas antes
de implementar. Quedó como guarda de regresión permanente (pytest + humo manual).

**Decisión de diseño — sin frase educativa** (a diferencia de `respuesta_jerarquizar._con_puente`,
que dice *"lo que llamas «X» es, en realidad, Y"*): Cuantificar no rastrea con qué palabra el usuario
calificó la entidad, así que esa frase arriesgaría atribuirle un término que no usó. Corrección
silenciosa de la etiqueta en su lugar.

Plan: `Planes/plan_conteo_jerarquia_R2_2026-08-03.md`.

### 5.3 — Fuera de ambos planes (deuda anotada, no de este hallazgo)

- `respuesta_analizar.py` tiene la misma ocurrencia que 2.3 (`alcance = f"el {nivel} {ent_valor}"`),
  pero solo alimenta un prompt de LLM (con instrucción explícita de no repetirlo verbatim) — menor
  exposición, documentada, no corregida.
- El código ambiguo `GAN` y los 6 sin match en robustez (`GAO/GAR/GDA/GEE/GLH/GNS`) siguen mostrando
  "la Gerencia" — sin evidencia inequívoca en robustez para decidir la corrección.

### 5.4 — Validación

**R1+R3:** pytest 67/67 (7 nuevos + 60 no-regresión); golden 66/71=92% (gate ≥90%; los 5 fallos
restantes son deuda preexistente de no-determinismo de qwen en la franja `estructural`, ya
documentada y aceptada en el propio golden, verificados no relacionados con este cambio).

**R2:** pytest 91/91 (8 nuevos + 83 no-regresión); guarda de regresión contra BD real confirma GOR
incluido y CPV/GAN/GXO excluidos; humo end-to-end `resolver_unico('GOR')` → `puente=True`,
`_etiqueta_nivel` → `"la Vicepresidencia"`, nivel de query sin cambios.

Verificación en navegador / LLM en vivo: pendiente en el servidor de pruebas.
