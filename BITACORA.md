# Bitácora — ProdIA

> Recreada el **2026-08-29** en el espacio de trabajo `Repo ProdIA`, a partir de
> `data/bitacora/ProdIA_agosto_2026.md` del monorepo `ProdIA-2.0`.
> Rango: **2026-08-01 → 2026-08-29**. Ver `CLAUDE.md` para la guía de trabajo.

---

## Panorama de agosto 2026

229 commits hasta el 26-ago, más tres sesiones de infraestructura (27 y 29-ago) sin
commits de producto. El mes tiene tres grandes bloques:

1. **2–13 ago (109 commits) — Consolidación del Motor Q v2.** Los cuatro grupos de
   intención del chat (Cuantificar, Jerarquizar, Analizar, OUT) pasan de esqueleto a
   responder con cifras reales, memoria conversacional y paneles gráficos apilados.
2. **20–24 ago (38 commits) — Capa de presentación.** Rediseño del login, MainChat pasa
   de cascarón a interfaz real, fix del scroll de Insights, y rediseño del panel
   Jerarquizar como árbol con conectores.
3. **25–29 ago — Cierre del mes.** Cuantificar a grano día, resiliencia ante timeouts,
   hallazgo de corrupción física en la BD local, panel «Comportamiento {Producto}»,
   navegación de módulos, hilo de chat tipo timeline, mapa de pozos, pulido medido en
   vivo, y finalmente la migración de puertos, la separación en dos repos y el primer
   despliegue a Azure DevOps.

### Bloques por commits

| Bloque | Fechas | Commits | Eje principal |
|---|---|---:|---|
| Motor Q v2 | 2–4 ago | 60 | Los 4 grupos de intención + filtro de dominio + Test Clas |
| Paneles y gráficos | 11–12 ago | 15 | Pila acumulativa, dot plot, dona, identidad por producto |
| P50 y mantenimientos | 13 ago | 9 | P50 como referencia, Eventos_OW real, panel por vicepresidencia |
| Despliegue e ingesta | 20 ago | 2 | Ingesta por lote no interactiva para el servidor 139 |
| UI y entorno | 21 ago | 7 | Login rediseñado, MainChat, arranque en Consulta, `install.bat` |
| MainChat real + Jerarquizar | 24 ago | 31 | MainChat funcional, scroll de Insights corregido, árbol |
| Cuantificar a grano día | 25 ago | 6 | Vocabulario de arranque, grano día N1D/N1DSEL |
| Resiliencia e ingesta | 25 ago (pm) | 1 | Timeout sin perder la pregunta; corrupción BD local |
| Panel de día + rendimiento | 25 ago (noche) | 4 | Implementación del panel; fix de caché duplicada |
| Navegación de módulos | 25 ago (cierre) | 1 | Consulta/Análisis al waffle, `tabExiste()` |
| Asistente sobre sí mismo | 25 ago (noche) | 3 | 4º detector del clasificador (`capacidades.py`) |
| Hilo tipo timeline | 25 ago (noche) | 6 | Burbujas → hilo de una columna |
| Mapa de pozos | 25 ago (noche) | 1 | Mapa sobre Colombia, coordenadas corregidas |
| Pulido medido en vivo | 26 ago | 4 | Fixes de layout y de contexto conversacional |
| Periodo de la pregunta | 26 ago (2ª) | 6 | Analizar deja de ser ciego al mes; panel de Diferidas |
| Atajos, login y UI | 26 ago (3ª) | 11 | Atajos de chat, login con constelación animada |
| Migración de puertos + Azure | 26 ago (4ª) | — | Puertos 5029/5030, 2 repos, primer deploy al 139 |
| Lanzadores sin consola nueva | 27 ago | 0 | `iniciar_frontend.bat` / `iniciar_backend.bat` |
| Verificación y clonado limpio | 29 ago | 0 | Este espacio de trabajo |

---

## Hitos que conviene no olvidar

**Motor Q v2 (2–4 ago).** Cuantificar, Jerarquizar, Analizar y OUT, más clasificador con
pestaña Test Clas, memoria conversacional, warm-up del LLM y RBAC de pestañas.

**P50 (13 ago).** La hoja del P50 está en promedio diario, no en la escala del fact —
aplicar la conversión equivocada daba cifras mil veces menores **sin error visible**.

**Scroll de Insights (24 ago).** Cinco iteraciones hasta hallar la causa real: un listener
de scroll en `document` capturaba el auto-scroll del chat. Se resolvió midiendo la traza en
la app real, no razonando sobre el archivo. De ahí nace la regla de medir antes que razonar.

**Grano día (25 ago).** De 11 variaciones de pregunta, solo 3 funcionaban: todo Cuantificar
colgaba de la palabra literal «cuánto». Se cerraron las 8 restantes. El dato diario termina
el 2026-05-17, así que «ayer» no tiene dato pero «el 15 de mayo» sí.

**Corrupción de BD (25 ago).** `psycopg.errors.DataCorrupted` en la BD local, por errores
de disco y apagado inesperado del 23–24 de agosto — no es problema del ETL.
`bronze.idx_landing_payload` reparado; `core.fact_tabla_hoja` (41 GB) sin reparar.

**Caché del proxy (25 ago).** El panel tardaba minutos porque la clave de caché incluía el
parámetro `pulir`, partiéndose en dos entradas.

**Mapa de pozos (25 ago).** `ops.wells_attributes` tiene grano de zona, no de pozo
(inflaba conteos ×3), y traía latitud/longitud invertidas.

**Analizar ciego al mes (26 ago).** Ignoraba el mes pedido y respondía siempre el vigente,
sin avisar. También: «mayo» era substring de «mayor» en el detector de periodo.

---

## Sesión del 26 de agosto (4ª parte) — Migración de puertos y primer despliegue a Azure

Lo que arrancó como «cambiar 2 puertos» (8020/8088 → **5029/5030**) escaló a ~8 horas:
separar el monorepo en los dos repos que exige Azure DevOps (`ProdIAWebFront` /
`ProdIABack`) y hacer el primer despliegue verificado en el servidor 139.

Causas raíz confirmadas en el camino:

| Síntoma | Causa |
|---|---|
| `.env` no reflejaba la edición | Editado en VS Code, nunca guardado con Ctrl+S |
| Migración conectaba a `localhost` | Bloque DEV activo en `.env`, PROD comentado |
| `database_url field required` | BOM añadido por `Set-Content -Encoding utf8` en PS 5.1 |
| `onnxruntime` sin wheel | Python 3.14 recién liberado |
| `install.bat` seguía viendo 3.14 | `py -3` no respeta el PATH; usa su registro interno |
| Flask arrancaba en el puerto 5007 | Contenido desincronizado en el checkout de Azure |
| Panel del login ausente | `login-steps.js` con 404 y `login.css` desactualizado |

Quedaron dos herramientas reutilizables: **`exportar_azure.ps1`** (export limpio con
`git archive`) y **`verificar_deploy.ps1`** (verifica puerto, rediseño del login y **todos**
los estáticos que `login.html` referencia).

Sin resolver: en qué paso exacto de la cadena `GitHub → export → Azure DevOps` se perdió
contenido. Hipótesis abierta, no hecho verificado.

**Pedido explícito que sigue vigente: construir un pipeline de despliegue real.**

---

## Sesión del 27 de agosto — Lanzadores separados sin consola nueva

Se confirma el procedimiento de deploy fresco en el 139 (evitando la carpeta `ProdIA_Front`
con el ACL roto en `data\logs`) y se añaden `iniciar_frontend.bat` (Flask :5029) e
`iniciar_backend.bat` (INGESTA :5030), que arrancan **en la misma consola** que los invoca,
a diferencia de `iniciar_backends.bat`, que abre dos ventanas y queda intacto.

Ambos reutilizan la lógica de resolver el intérprete base vía `pyvenv.cfg`, para evitar el
trampolín `venv\Scripts\python.exe` que WDAC bloquea en el 139.

⚠️ Diferencia pendiente de confirmar: `iniciar_backend.bat` levanta uvicorn en
`--host 0.0.0.0`, mientras `iniciar_backends.bat` usa `127.0.0.1` para el mismo servicio.
No afecta el proxy interno (Flask le habla por `localhost`); solo cambia si el puerto 5030
queda expuesto a la red.

---

## Sesión del 29 de agosto — Verificación de repos y clonado limpio desde Azure

**0 commits de producto.** Sesión de normalización: dejar de trabajar sobre copias de
procedencia incierta y partir de un origen verificado.

### 1. Verificación del estado de los repos

Se compararon los tres repos **por hash de blob** (no por SHA de commit, porque tienen
historias distintas al haber nacido de un export):

| Comparación | Resultado |
|---|---|
| GitHub `ProdIABack` ↔ monorepo `INGESTA/Rep_Prod` | **Idéntico** — 275/275, 0 diferencias |
| GitHub `ProdIAWebFront` ↔ monorepo (sin INGESTA) | **Idéntico en código** — 252/255; las 6 diferencias son doc y `.gitignore`, por diseño |
| Copia local del monorepo ↔ GitHub `origin/main` | Sincronizada en `5a566dd` |

🔑 **Hallazgo positivo**: en Azure DevOps, `app.py`, `templates/login.html`,
`static/css/login.css` y `static/js/login-steps.js` tienen hash **idéntico** al monorepo.
Es decir, **la desincronización del postmortem —el puerto 5007 y el login viejo— está
resuelta**. La cerró el commit `af83a118` («sync: contenido completo y verificado desde el
monorepo»). Ese punto del postmortem puede darse por cerrado.

### 2. Mapa de entornos, explicitado

| Entorno | Rol | VPN |
|---|---|---|
| Local | Editar código | **No** |
| Servidor de pruebas | Correr y probar | Sí |
| Servidor 139 (`10.100.26.139`) | Producción, `E:\APLICACIONES\ProdIA_v2\` | — |

De ahí la fricción de fondo del proyecto: **el código nace donde no se puede probar, y se
prueba donde no se edita.**

### 3. Clonado limpio en el servidor de pruebas

Primer intento con layout **anidado** (back dentro de `frontend\INGESTA\Rep_Prod`), que era
lo que exigía `iniciar_backends.bat`. Se descartó al ver la estructura real de producción:
**dos carpetas hermanas**, `frontend\` y `backend\`. Funciona así precisamente gracias a los
lanzadores separados del 27-ago.

Clonado definitivo desde **Azure DevOps** (org `ecopetrolad`, proyecto
`HUBCienciaDatosUpstreamLAB`, rama `dev`) a `C:\APLICACIONES\ProdIA\Repo ProdIA\`:

```
frontend   405 objetos, 54.75 MiB
backend    303 objetos,  3.32 MiB
```

Los `.env` se reutilizaron de `ProdIA-2.1` (no se versionan, son propios de cada máquina).
🔑 **El chequeo de BOM encontró uno**: `backend\.env` traía `EF BB BF`, justo lo que rompió
`pydantic-settings` en la sesión del 26. Reescrito con `UTF8Encoding($false)`. Cazado antes
de arrancar, no después de horas de depuración.

### 4. Diferencias de Azure respecto al monorepo

`ProdIABack`: **idéntico**, más un `README.md` propio.

`ProdIAWebFront`: idéntico en código, con 33 archivos de más, todos del commit inicial de
julio (`aef6e606`):

```
14  vector_db/            51.5 MB   (ChromaDB, regenerable)
 3  data/*.db, *.zip      99.8 MB   (ROBUSTEZ.db, ROBUSTEZ.zip, chat_history.db)
 6  copias manuales                 (*.bak, "- Copy")
 4  temporales                      (temp_*.txt, temp_*.py, image.png)
 3  config de editores              (.claude, .codex, .vscode)
```

Unos **151 MB versionados** que el monorepo ignora a propósito — su `.gitignore` ya cubre
`vector_db/`, `temp_*`, `*.bak` y `*[- ]Copy.*`.

🔑 `INGESTA/Rep_Prod` en Azure **no es una carpeta**: es un **gitlink** (modo `160000`)
apuntando al commit `197942d` de ProdIABack. Alguien commiteó el repo anidado como
submódulo sin `.gitmodules`. Por eso el clon no descarga nada ahí y tampoco da error.
Es residuo del layout anidado ya abandonado.

### 5. Limpieza en local

Las dos carpetas se copiaron a esta máquina solo para verificarlas. Hecha la verificación:

- **Se eliminó el `.git` de ambas.** No queda ningún remoto ni historial de Azure DevOps en
  la máquina local. Son copias de trabajo, no checkouts.
- Se retiró la identidad corporativa de git que se había configurado para firmar un commit
  de sincronización; ese commit se revirtió.

### 6. GitHub como puente entre las dos máquinas

Decisión de fondo de la sesión: **usar GitHub (`jaguez40-star`) como origen de trabajo**,
porque es lo único que alcanzan las dos máquinas. La local no tiene VPN y no llega a Azure
DevOps; el servidor de pruebas llega a los dos. Queda así:

```
GitHub  ──→ Local (editar)  y  ──→ Pruebas (correr) ──→ Azure DevOps ──→ 139
```

Esto ataca directamente la fricción de fondo del proyecto: hasta hoy, el código nacía donde
no se podía probar.

**Los dos repos de GitHub se reescribieron desde cero.** No se crearon nuevos —
`ProdIAWebFront` y `ProdIABack` ya existían— sino que se les empujó una historia nueva de un
solo commit con el contenido verificado:

| Repo | Antes | Ahora | Archivos |
|---|---|---|---:|
| `ProdIAWebFront` | `a2384c3` | `6bef0d9` | 262 |
| `ProdIABack` | `2df5463` | `1584fa8` | 278 |

🔑 **La limpieza salió gratis.** Al nacer la historia de un `git init` nuevo, el
`.gitignore` que ya existía dejó fuera solos los ~151 MB de `vector_db/`, `data/*.db`,
`data/*.zip`, copias `.bak` y temporales que Azure arrastraba desde julio. El clon del
frontend pasó de **54.75 MiB a 12.57 MiB**. Con esto queda hecha la recomendación 3.

**Dos correcciones de seguridad e higiene por el camino:**

- 🔑 El `.gitignore` del backend solo tenía `.env`, que **no cubre `.env.bak`** — y ese
  archivo, generado al arreglar el BOM, tenía credenciales de PostgreSQL dentro. Se borró
  el archivo y la regla pasó a `.env*` con excepción para `.env.example`. Se verificó, antes
  de subir, que ningún `.env`, `.bak` ni credencial estuviera en el índice.
- El `.gitignore` del frontend excluía `CLAUDE.md`. Se quitó esa regla: ahora es
  documentación del proyecto y debe versionarse. Tanto `CLAUDE.md` como `BITACORA.md` van
  dentro de **los dos** repos, para que cada uno se explique solo al clonarlo.

**Clonado final en el servidor de pruebas** desde GitHub, a
`C:\APLICACIONES\ProdIA\Repo ProdIA\{frontend,backend}` (se borraron antes las carpetas
previas). Verificado: `app.py`, `backend\app\main.py` y `CLAUDE.md` presentes.

Quedaron sin tocar 7 archivos sueltos del commit de julio que el `.gitignore` no cubre
(`DIFERIDAS_MES.csv`, `image.png`, `start.bat`, `README.md`, `.claude/`, `.codex/`,
`.vscode/`), y el postmortem sigue solo en el monorepo.

---

## Pendientes al cierre del 29 de agosto

**Ya hecho en esta sesión**

- [x] Verificar que los repos están alineados (por hash de blob).
- [x] Clonar limpio en el servidor de pruebas, con el layout de producción.
- [x] Reescribir los repos de GitHub con historia nueva y contenido verificado.
- [x] Limpiar los ~151 MB de extras — salió gratis al reiniciar la historia.
- [x] Retirar el gitlink `INGESTA/Rep_Prod`.
- [x] Cerrar el agujero del `.gitignore` que habría versionado `.env.bak` con credenciales.
- [x] Versionar `CLAUDE.md` y `BITACORA.md` dentro de los dos repos.

**Del entorno de pruebas** — *lo siguiente por hacer*

- [ ] Copiar los dos `.env` (no vienen en el repo) y pasar el chequeo de BOM.
- [ ] Verificar `py -0` (hace falta 3.12.x, no 3.14) y correr `install.bat` + `uv sync`.
- [ ] Crear los lanzadores adaptados al layout separado: `iniciar_backend.bat` necesita
      `ING_DIR=%~dp0backend`.
- [ ] Arrancar y verificar con `verificar_deploy.ps1`.

**De los repos**

- [ ] Commitear los lanzadores adaptados, para que el próximo clon los traiga y no haya que
      ponerlos a mano como en la 139.
- [ ] Llevar a Azure DevOps `dev` esta misma versión limpia, para que producción deje de
      arrastrar los 151 MB y quede alineada con GitHub.
- [ ] Decidir si el postmortem y los 7 archivos sueltos de julio (`DIFERIDAS_MES.csv`,
      `image.png`, `start.bat`, `.claude/`, `.codex/`, `.vscode/`, `README.md`) entran o
      salen.
- [ ] Borrar, si ya no hacen falta, los `.env` con credenciales que quedaron en la copia
      local de `Repo ProdIA`.

**De fondo**

- [ ] **El pipeline de despliegue real.** Sigue siendo el pedido central del postmortem:
      un solo camino de despliegue, verificación automática de integridad, Python fijado
      por versión exacta, `.env` generados y no editados a mano, y las políticas de rama de
      Azure DevOps documentadas de antemano.

**Deuda funcional conocida** (documentada, no bloqueante): el `rank` de Focos de atención
no ordena por impacto; falta control de roles real; `PLATA` choca con «plataforma»; el
fallo «SIN RESPUESTA» en la primera pregunta tras reinicio sigue sin causa raíz; corrupción
pendiente en `core.fact_tabla_hoja` (solo BD local).

---

## Recomendaciones (2026-08-29)

Priorizadas por relación valor/esfuerzo. Las tres primeras son de horas; la cuarta es el
trabajo de fondo.

### 1. Cerrar el entorno de pruebas — *primero, porque desbloquea todo lo demás*

Sin la app corriendo desde el clon nuevo, no hay forma de validar ningún cambio. Es el paso
más corto y el que devuelve más: `py -0` → `install.bat` → `uv sync` → lanzadores →
`verificar_deploy.ps1`.

### 2. Sincronizar la documentación a Azure

Los únicos archivos donde el monorepo va adelante son cuatro documentos: `projecto.md`,
`Cambios_Agosto.md`, `ProdIA_agosto_2026.md` y el postmortem. No es urgente, pero es la
última brecha de contenido real entre las dos fuentes, y cerrarla permite declarar Azure
como fuente única sin asteriscos.

### 3. Limpiar `ProdIAWebFront` — ✅ **hecho el 29-ago**

Sacar del índice los ~151 MB de binarios (`vector_db/`, `data/*.db`, `data/ROBUSTEZ.zip`),
las seis copias manuales (`*.bak`, `- Copy`), los cuatro temporales y la config de editores.
Añadirlos al `.gitignore` — que ya los cubre en el monorepo. Retirar también el gitlink
`INGESTA/Rep_Prod`, residuo del layout anidado.

Beneficio concreto: el clon baja de 54.75 MiB a ~17 MiB, y deja de arrastrarse historia
pesada que nadie usa.

⚠️ Sacarlos del índice **no** los borra de la historia. Si se quiere recuperar el espacio de
verdad hay que reescribirla, y eso es una decisión aparte que afecta a todos los clones.

### 4. El pipeline de despliegue — *el pedido de fondo*

Sigue siendo lo que el postmortem pidió en mayúsculas, y nada de lo hecho hasta ahora lo
sustituye. Cinco piezas:

| Pieza | Estado hoy |
|---|---|
| Un solo camino de despliegue | Cadena manual de exports, copias y merges entre 3 repos y 2 máquinas |
| Verificación automática de integridad | `verificar_deploy.ps1` existe, pero se corre a mano |
| Python fijado por versión exacta | Solo `>=3.12` en `pyproject.toml`; sin pin real |
| `.env` generados y validados | Editados a mano; el BOM volvió a aparecer el 29-ago |
| Políticas de rama de Azure documentadas | Se descubren al chocar con ellas |

Sin esto, cada «solo cambia dos puertos» vuelve a costar ocho horas.

### 5. Decisiones pendientes, pequeñas pero que conviene no dejar colgando

- **Declarar la fuente de verdad.** Recomendación: Azure DevOps `dev` para lo que se
  despliega; el monorepo `ProdIA-2.0` como archivo histórico. Mientras haya dos «últimas
  versiones», cada sincronización puede perder contenido.
- **Commitear los lanzadores en su repo.** Hoy el `iniciar_backend.bat` del 139 se puso a
  mano y no está en ningún repositorio: el próximo clon no lo trae.
- **Confirmar `--host 0.0.0.0` vs `127.0.0.1`** en `iniciar_backend.bat`. No afecta al proxy
  interno, pero decide si el 5030 queda expuesto a la red.
- **Los tres `.env` con credenciales** copiados a la máquina local
  (`frontend\.env`, `backend\.env`, `backend\.env.bak`): borrarlos si no se van a usar ahí.

---

*Documento de estado — actualizado 2026-08-29.*
