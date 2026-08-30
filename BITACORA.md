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

### 7. El pipeline queda definido, y automatizado su último tramo

El usuario fijó el proceso completo:

```
LOCAL (sin VPN)          PRUEBAS (con VPN)                              139
editar ─push─→ GitHub ─pull─→ Repo ProdIA (probar)
                                   │ skill migrar-a-azure
                                   ▼
                          APLICACIONES_AZURE ─push─→ Azure DevOps ─→ producción
```

**Decisión explícita: las dos carpetas de Pruebas no comparten `.git`.** Se propuso
resolver el puente con dos remotos en un solo checkout —más simple y con fidelidad
garantizada por SHA— y el usuario lo descartó: no quiere que los dos git convivan en la
misma carpeta. Es una separación defendible: hace imposible empujar por error a Azure algo
sin probar, y mantiene el checkout de pruebas libre de historia corporativa.

Aceptada esa restricción, el puente tiene que ser una copia de archivos — **y una copia no
garantiza fidelidad**. Ese es exactamente el paso cuya causa raíz el postmortem del 26-ago
no pudo aislar, cuando llegaron a producción un `app.py` con puerto 5007 y un login viejo.

**Solución: medir en vez de confiar.** Se creó el skill `migrar-a-azure`
(`frontend/.claude/skills/migrar-a-azure/`), con dos piezas: `SKILL.md` con el
procedimiento y `migrar_a_azure.ps1` con el trabajo. Qué hace:

| Paso | Por qué |
|---|---|
| Exige el origen limpio | Lo publicado debe corresponder a un commit real de GitHub |
| Informa antes de escribir | Nuevos, modificados y **los que sobran en destino** |
| Copia en modo espejo | Sin eso, un archivo borrado sobrevive para siempre en Azure |
| Excluye `.env`, entornos, `vector_db`, respaldos | Pisar el `.env` cambiaría las credenciales del destino |
| **Verifica hash de blob de cada archivo** | Si uno solo difiere, aborta y no publica |
| Escribe el SHA de GitHub en el commit de Azure | Sin eso no se sabe qué versión está desplegada |

Por defecto **solo informa**; hay que pasar `-Aplicar` o `-Push` para que escriba.

Detalle que suele morder y que el script contempla: **robocopy devuelve 0 a 7 en éxito**,
solo 8 o más es fallo. Un `-ne 0` daría falsos errores.

También se ajustó el `.gitignore`: `.claude/` pasó a `.claude/*` con excepción para
`.claude/skills/`, porque los skills son procedimiento del proyecto y deben versionarse,
mientras que `settings.local.json` sigue siendo local. Verificado que el skill se versiona
y que los ajustes locales no.

⚠️ **Regla nueva: Azure solo recibe de este pipeline.** Nunca commitear directo allí. Ya
pasó dos veces —el commit inicial de julio y los arreglos a mano en el 139 el 26-ago— y es
justo así como nacen las «dos últimas versiones».

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
- [x] Definir el pipeline completo, con sus cinco reglas.
- [x] Crear el skill `migrar-a-azure` con verificación de fidelidad hash por hash.

**Del entorno de pruebas** — *lo siguiente por hacer*

- [ ] Copiar los dos `.env` (no vienen en el repo) y pasar el chequeo de BOM.
- [ ] Verificar `py -0` (hace falta 3.12.x, no 3.14) y correr `install.bat` + `uv sync`.
- [x] Crear los lanzadores adaptados al layout separado: `iniciar_backend.bat` con
      `ING_DIR=%~dp0backend` y `--host 127.0.0.1`.
- [ ] Arrancar y verificar con `verificar_deploy.ps1`.

**De los repos**

- [x] Commitear los lanzadores adaptados, para que el próximo clon los traiga y no haya que
      ponerlos a mano como en la 139.
- [ ] Llevar a Azure DevOps `dev` esta misma versión limpia, para que producción deje de
      arrastrar los 151 MB y quede alineada con GitHub.
- [x] Postmortem: **entra** (vive ya en `frontend\`). `start.bat`: **sale** (resto de julio,
      puerto 5001 y trampolín bloqueado por WDAC; nadie lo referenciaba).
- [ ] Decidir sobre los sueltos que quedan: `DIFERIDAS_MES.csv`, `image.png`, `.codex/`,
      `.vscode/`, `README.md`.
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

## Sesión del 29 de agosto (tarde) — Verificación contra el monorepo y layout de arranque

Se comparó el espacio de trabajo contra el monorepo `ProdIA-2.0` por **hash de blob**, que
es lo único que sirve cuando las historias de git son distintas.

**El código está intacto.** De 536 archivos versionados en el monorepo, **528 son idénticos**
y **ninguno de los que difieren es código fuente**. Las únicas diferencias eran los dos
`.gitignore` (endurecidos a propósito) y dos `.md`. La separación en dos repos no perdió
código.

**Lo que sí faltaba, y se arregló:**

- Los lanzadores del 27-ago (`iniciar_frontend.bat`, `iniciar_backend.bat`) no habían
  llegado a ningún repo, aunque `CLAUDE.md` §4 ya los documentaba. Entraron, cada uno en el
  suyo, y el del backend con `ING_DIR=%~dp0backend` y `--host 127.0.0.1`.
- Estaban en LF en el origen. Se escribieron en **CRLF**: ambos usan subrutinas y saltos,
  donde un batch en LF falla de forma errática.
- `projecto.md` y `data/bitacora/Cambios_Agosto.md` habían **retrocedido** a una versión
  anterior al 26-ago (decían puertos 8020/8088). Se restauraron. `projecto.md` además se
  adaptó al layout de dos repos; `Cambios_Agosto.md` se dejó **verbatim**, porque su propio
  pie dice que las entradas fechadas son histórico y no se tocan.
- `data/bitacora/ProdIA_agosto_2026.md` no estaba en el repo, aunque la carpeta sí se
  versiona. Entró verbatim, para no dejar la bitácora a medias.
- `start.bat` (julio: puerto 5001 y el trampolín que WDAC bloquea) se borró. Nadie lo
  referenciaba.
- El postmortem del 26-ago dejó de vivir solo en el monorepo.

**Lo que se verificó de paso, y no hizo falta tocar:** el skill `migrar-a-azure` no excluye
`.bat` ni `.claude/skills/`, así que lo nuevo viajará a Azure sin cambios;
`verificar_deploy.ps1` no referencia lanzadores ni rutas anidadas.

**Dos riesgos anotados para antes de estrenar el skill:** compara `git ls-tree` del origen
contra `git hash-object` del destino, así que si la máquina de Pruebas no tiene
`core.autocrlf=true` abortará en todos los archivos de texto; y excluye `.env` exacto
mientras el `.gitignore` del backend ya usa `.env*`.

**Deuda preexistente confirmada, no tocada:** `_test_robustez.py` (f-string sin cerrar) y
`_update_panorama_titles.py` (no es UTF-8) no compilan — pero son idénticos al monorepo y
la app no los importa.

---

## Sesión del 30 de agosto — El pipeline completo, probado de punta a punta

Se cerró el ciclo que faltaba desde el postmortem del 26-ago: un cambio recorrió las
**cuatro máquinas** —local, Pruebas, Azure DevOps y el servidor 139— con verificación en
cada salto, en **28 minutos**.

### Cambios de la sesión

| Fecha | Cambio | Archivos afectados |
|---|---|---|
| 30-ago | El skill no publica trazas del repositorio de trabajo: copia dirigida por `git ls-tree` en vez de `robocopy /MIR`, exclusión de documentación interna, y un chequeo que aborta si encuentra una traza | `frontend/.claude/skills/migrar-a-azure/migrar_a_azure.ps1`, `SKILL.md` |
| 30-ago | Limpieza de menciones a la herramienta de trabajo: 17 líneas en 13 archivos del front y 4 en 2 del back. Todas comentarios o documentación | `.gitignore`, `DISENO_CAPA_CONVERSACIONAL.md`, `MainChat/static/js/historial.js`, `ProdIA_Jun.md`, `arq_log.md`, `changesProdIA_last.md`, `migra.py`, `projecto.md`, `routes/auth.py`, `static/js/{dailyPerformanceReport,monthlyBalanceReport,multitab_shell,reportTabs}.js`, `backend/{analiza,cuant}.md` |
| 30-ago | `.gitignore` del front pasa a cubrir `.env*`, no solo `.env`. Un respaldo `.env.previo_*` con credenciales quedaba visible para git y bloqueaba la migración | `frontend/.gitignore` |
| 30-ago | Mensaje de publicación mínimo en Azure: solo `Version <sha>` y la fecha. El anterior describía el proceso de verificación. El temporal del mensaje se borra tras el commit | `migrar_a_azure.ps1` |
| 30-ago | Marca del login un 10% mayor y en el verde corporativo `--pv-primary` (#004236). Validado visualmente en Pruebas y en producción | `frontend/static/css/login.css` |
| 30-ago | Tres directrices de método en la sección 7: brevedad, claridad de comandos, camino más corto y actuar cuando la evidencia alcanza | `CLAUDE.md` (las tres copias) |

### 🔴 Hallazgo mayor: el frontend del 139 llevaba desde julio en la rama equivocada

`E:\APLICACIONES\ProdIA_v2\frontend` estaba en la rama **`prodia-v2`**, no en `dev`. El
backend sí estaba en `dev`. Por eso producción **nunca recibía** lo que se publicaba: un
`git pull` allí traía otra rama.

**Ahí está la causa raíz de las «dos últimas versiones» que el postmortem del 26-ago no
supo explicar.** Los 2 commits que `prodia-v2` tenía y `dev` no eran el import inicial de
julio —mismo contenido, historia distinta—, así que no se perdió trabajo.

### Lo que costó, y no fue el código

El código estaba bien desde el principio. Los cinco obstáculos fueron de entorno:

1. **Sin Python 3.12** en Pruebas ni en local. Resuelto con `uv python install 3.12` y
   `uv venv --seed`, sin admin y sin tocar el PATH. `install.bat` reutiliza el venv si ya
   existe, así que no hubo que modificarlo.
2. **Disco lleno** en Pruebas: 0,3 GB libres. 6,4 GB recuperados vaciando cachés de pip y uv.
3. **`uv` no podía crear enlaces duros** (`os error 396`) en carpeta con sincronización en
   nube. Resuelto con `--link-mode=copy`.
4. **Los `.env` repartidos entre dos despliegues viejos**, a cada uno le faltaba una pieza.
5. **Permisos**: los repos del 139 eran de `AEUECPAPRY005P\DevOps` y git no podía escribir.
   Resuelto clonando limpio en `E:\APLICACIONES\Repo ProdIA` y con `takeown` + `icacls`.

### 🔴 `OPS_DATABASE_URL` se pierde en cada despliegue

Faltaba en **tres sitios a la vez**: la copia local, el despliegue del 26-ago en Pruebas y
el `.env` vivo de producción. Sin ella, el **EBITDA Inspector** y **Analizar economía** se
quedan sin fuente, en silencio. No es un descuido puntual: es un patrón, y el generador de
`.env` que pide la sección 8 de `CLAUDE.md` sigue sin existir.

### Estado verificado al cierre

| Máquina | Ruta | Rama | Versión | Estado |
|---|---|---|---|---|
| Local (SKYNET) | `C:\APLICACIONES\ProdIA\Repo ProdIA` | `main` | `231c30a` | Editar. Sin VPN |
| Pruebas · trabajo | `C:\APLICACIONES\ProdIA\Repo ProdIA` | `main` | `231c30a` | Probar |
| Pruebas · Azure | `C:\APLICACIONES_AZURE\Repo ProdIA` | `dev` | `5549be4` | Publicar |
| **139 producción** | `E:\APLICACIONES\Repo ProdIA` | `dev` | `5549be4` | **Operativo** |

La instalación vieja `E:\APLICACIONES\ProdIA\ProdIA\ProdIA_Front\` queda **intacta como
respaldo**. `ProdIA_v2` quedó abandonada: no tenía `.env` ni entornos.

---

## Estructura actual del proyecto

### Las dos aplicaciones

| | `frontend\` — ProdIAWebFront | `backend\` — ProdIABack |
|---|---|---|
| Stack | Flask + SocketIO + Jinja2 | FastAPI, gestionado con `uv` |
| Puerto | **5029**, expuesto (`0.0.0.0`) | **5030**, solo `127.0.0.1` |
| Entrada | `app.py` | `backend\app\main.py` |
| Entorno | `venv\` (pip) | `backend\.venv\` (uv) |
| Python | 3.12.x exacto | 3.12.x exacto |
| BD | SQL Server / Synapse + SQLite | PostgreSQL (`daily_report_prod` + `robustez_v02`) |

El navegador **nunca** habla con el 5030: Flask hace de proxy vía `routes/api.py`
(`INGESTA_API_URL`).

### Endpoints de INGESTA en producción

```
/health                        /analisis/{catalogo,cobertura,densidad,desempeno,
/reportes  /reportes/ultimo               ejecutivo,huella,president,tendencia_filial}
/reportes/cobertura            /consulta/{preguntar,responder}
/tablas  /tablas/arbol         /consulta2/{preguntar,golden,senal,veredicto,pozos_geo,log}
/tablas/datos                  /ebitda/unificado-waterfall
/kpis-prod/produccion-dia      /ingesta/{archivo,upload,upload_stream,jobs,disponibles}
```

### Herramientas del pipeline

| Herramienta | Dónde | Para qué |
|---|---|---|
| `install.bat` | `frontend\` | Crea `venv\` e instala 156 dependencias. Reutiliza el venv si existe |
| `iniciar_frontend.bat` | `frontend\` | Arranca Flask :5029 en la misma consola |
| `iniciar_backend.bat` | `backend\` | Arranca INGESTA :5030 en `127.0.0.1` |
| `verificar_deploy.ps1` | `frontend\` | 8 chequeos: puerto, login rediseñado, todos los estáticos |
| `migrar-a-azure` | `frontend\.claude\skills\` | Publica en Azure: copia, verifica hash, chequea trazas |
| `exportar_azure.ps1` | `frontend\` | Export limpio vía `git archive` |

### El pipeline, en tres comandos

```
LOCAL                 PRUEBAS                    AZURE          139
git push  ────────>   git pull
                      migrar_a_azure.ps1 -Push ──────────>  git pull
                                                            iniciar_*.bat
                                                            verificar_deploy.ps1
```

**Lo que el skill garantiza antes de publicar:** copia dirigida por `git ls-tree` (nunca
archivos que git ignora), verificación hash por hash de los 249 archivos, y un chequeo que
aborta si encuentra trazas del repositorio de trabajo.

**Lo que NO viaja a Azure:** `.claude`, `.codex`, `Planes`, `clmd`, `data/bitacora`,
`CLAUDE.md`, `BITACORA.md`, más `.env`, entornos y binarios regenerables.

---

## 👉 Dónde retomamos (2026-08-30, fin de sesión)

### Lo que ya funciona

- **El pipeline completo**, probado con un cambio real de punta a punta.
- **El 139 es autónomo**: `git pull` sin admin, `upstream` fijado en `origin/dev`.
- **Trazabilidad por SHA**: cada commit de Azure lleva la versión del repo de trabajo, y el
  `reflog` de cada máquina registra la fecha de cada despliegue.

### Lo siguiente, en orden

**1. Generador de `.env`.** Es el pendiente más caro. `OPS_DATABASE_URL` se ha perdido tres
veces. Un script que valide variables requeridas, formato, ausencia de BOM y plantillas a
medio llenar — lo pide la sección 8 de `CLAUDE.md` desde el 29-ago.

**2. `Debug mode: on` en Flask de producción**, con el 5029 en `0.0.0.0`. El depurador de
Werkzeug permite ejecutar código desde el navegador ante cualquier traza. Decidirlo a
conciencia.

**3. Bug del skill:** el `-Push` sale con «al día» si la copia no cambió nada, aunque el
destino tenga commits sin publicar. Pasó tras un `-Aplicar` previo y hubo que commitear a
mano. El `-Push` directo sí funciona.

**4. Un `desplegar_139.ps1`** que haga parar → `pull` → arrancar → verificar en un comando.

### Decisiones abiertas

- Los dos commits ya publicados en Azure (`79d4dcf`, `5549be4`) conservan el mensaje viejo,
  que describía el proceso. Reescribirlos exige forzar el push contra `dev`.
- Identidades de git distintas por máquina: los commits salen como «Javier Guerrero» y como
  «Javier Alexander Guerrero Hernandez (EAM…)». No rompe nada.
- ¿Entran o salen los sueltos (`DIFERIDAS_MES.csv`, `image.png`, `README.md`, `.codex/`)?
- Restos en Azure de julio: 104 archivos excluidos, 53 con trazas dentro. El skill los
  informa pero no los borra.

### Contexto que no está en el código

- La máquina local **no tiene VPN**: no alcanza Azure DevOps ni la BD del 139. GitHub sí.
- La BD local está congelada en 2026-05-18 y con corrupción en `core.fact_tabla_hoja`.
- En Pruebas y en el 139, la BD responde con datos al día (`/reportes/ultimo` → 2026-08-23).
- El monorepo `ProdIA-2.0` es **archivo histórico**. Hoy sirvió para recuperar credenciales
  y documentación que se habían perdido en los despliegues.

---

*Documento de estado — actualizado 2026-08-30.*
