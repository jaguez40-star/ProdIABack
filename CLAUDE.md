# CLAUDE.md — Espacio de trabajo `Repo ProdIA`

> Guía para trabajar en **esta** carpeta. Creada el 2026-08-29 a partir del conocimiento
> del monorepo `ProdIA-2.0`, la bitácora de agosto y el postmortem de la migración.
> Ver `BITACORA.md` (misma carpeta) para el historial y la última entrada.

---

## 1. Qué es esta carpeta

Es el espacio de trabajo del proyecto **ProdIA**, ya separado en los **dos repositorios**
que exige la convención de Azure DevOps, con la **misma estructura que producción**:

```
C:\APLICACIONES\ProdIA\Repo ProdIA\
├── frontend\      ← repo ProdIAWebFront — Flask + Jinja2      (puerto 5029)
└── backend\       ← repo ProdIABack     — FastAPI + React/TS  (puerto 5030)
```

Son **carpetas hermanas**, no anidadas. Espeja `E:\APLICACIONES\ProdIA_v2\{frontend,backend}`
en el servidor 139.

### De dónde viene el código y hacia dónde va

```
        github.com/jaguez40-star          ← origen de trabajo (sin VPN)
        ├── ProdIAWebFront  →  frontend\
        └── ProdIABack      →  backend\
                  │
                  ├──→ Local (esta máquina): editar
                  └──→ Servidor de pruebas: correr y probar
                                │
                                └──→ Azure DevOps `dev` ──→ Servidor 139 (producción)
```

**GitHub es el puente.** La máquina local no tiene VPN y no alcanza Azure DevOps; el
servidor de pruebas sí alcanza ambos. Por eso el flujo normal es: se edita en local, se
sube a GitHub, se baja en pruebas, se verifica, y solo entonces se lleva a Azure DevOps
para desplegar.

⚠️ **No configurar remotos de Azure DevOps ni identidad corporativa en la máquina local.**
Eso vive solo donde se despliega.

---

## 2. Los dos backends

La aplicación son **dos procesos**, no uno.

| | `frontend\` | `backend\` |
|---|---|---|
| Repo | ProdIAWebFront | ProdIABack |
| Stack | Flask + SocketIO, plantillas Jinja2 | FastAPI (gestionado con `uv`) |
| Puerto | **5029** | **5030** |
| Entrada | `app.py` | `backend\app\main.py` |
| BD | SQL Server / Azure Synapse + SQLite | PostgreSQL |
| Entorno | `venv\` (pip) | `backend\.venv\` (uv) |

**El navegador nunca habla con el 5030.** Flask hace de proxy interno mediante
`routes/api.py` (variable `INGESTA_API_URL`). Si una ruta nueva de INGESTA debe llegar al
navegador, hay que exponerla también en Flask.

### Estructura relevante

```
frontend\
├── app.py                  monolito Flask
├── routes/api.py           proxy hacia INGESTA
├── templates/  static/     UI (login, mainchat, consulta, análisis)
├── chatbot/                agentes, prompts, interfaces
├── install.bat             prepara venv + dependencias
├── verificar_deploy.ps1    integridad de un despliegue
└── exportar_azure.ps1      export limpio vía git archive

backend\
├── backend\app\features\   analisis, consulta, consulta_v2, ebitda,
│                           ingesta, kpis_prod, reportes, tablas
├── backend\tests\          ~30 archivos de test + golden sets YAML
├── frontend\               React + TypeScript + Vite (ingesta, kpis_prod, reportes)
├── db\migrations\          migraciones SQL
└── etl\                    pipeline de ingesta
```

---

## 3. Los tres entornos — NO son el mismo

| Entorno | Rol | VPN | Datos |
|---|---|---|---|
| **Local** (esta máquina) | Editar código | **No** | BD congelada en 2026-05-18, sin cierres mensuales |
| **Servidor de pruebas** | Correr y probar la app | Sí | Reales, vía el 139 |
| **Servidor 139** (`10.100.26.139`) | Producción | — | Reales y al día |

**Reglas que se ganaron a los golpes:**

- ❌ **Nunca** concluir nada sobre «el servidor» midiendo `localhost`. Son máquinas
  distintas con datos distintos.
- ❌ Desde local **no** hay acceso a Azure DevOps, a la BD del 139 ni a
  `\\10.100.25.161\Datagenesis`. No intentarlo.
- ✅ GitHub sí es alcanzable desde local (internet público).
- ✅ Para verificar código: importar el módulo en un proceso nuevo. Eso mide el fuente,
  y el fuente es igual en todas las máquinas.
- ✅ Cuando haga falta un dato del servidor, **pedir un comando concreto** y que el
  usuario pegue la salida. Uno decisivo, no una lista.

---

## 4. Puesta en marcha

### Requisitos que nadie instala por ti

- **Python 3.12.x exacto.** No 3.14: `onnxruntime==1.22.1` no tiene wheels para esa
  versión. Y ojo: `py -3` **ignora el PATH** y toma la más nueva instalada — comprobar
  con `py -0` y, si hace falta, invocar `py -3.12` explícitamente.
- `uv` (para el backend). Se instala con el script de Astral.
- ODBC Driver 18 for SQL Server (lo necesita `pyodbc`).
- Ollama con `gemma4:latest` (opcional, para el LLM local).

### Instalación

```powershell
# Front
cd 'C:\APLICACIONES\ProdIA\Repo ProdIA\frontend'
.\install.bat

# Back
cd 'C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend'
uv sync
```

⚠️ `install.bat` fue escrito para el layout **anidado** del monorepo. En este layout
separado mostrará dos AVISOS que **son normales, no fallos**:

- `[5/6] no se encontro ...\INGESTA\Rep_Prod\backend\pyproject.toml - se omite`
- `[6/6] no se hallo INGESTA\Rep_Prod\.env.example`

Termina en *«COMPLETADA - CON PENDIENTES»* y eso está bien: la parte de Flask sí se
instaló. El backend se instala aparte con `uv sync`.

### Arranque

```powershell
.\frontend\iniciar_frontend.bat    # Flask   → http://localhost:5029
.\backend\iniciar_backend.bat      # INGESTA → http://localhost:5030/health
```

Ambos corren **en la misma consola** que los invoca (sin ventana nueva), liberan su puerto
antes de arrancar y resuelven el intérprete base vía `pyvenv.cfg` — esto último evita el
trampolín `venv\Scripts\python.exe` que **WDAC bloquea en el servidor 139**.

`iniciar_frontend.bat` sirve tal cual. `iniciar_backend.bat` requiere una diferencia
respecto al del monorepo: `ING_DIR=%~dp0backend` en vez de `%~dp0INGESTA\Rep_Prod\backend`.

---

## 5. Los `.env` — las tres trampas conocidas

Ninguno se versiona. Hay **dos**: `frontend\.env` y `backend\.env`.

1. **BOM.** En PowerShell 5.1, `Set-Content -Encoding utf8` **siempre** añade BOM, y eso
   rompe `pydantic-settings` con un `database_url field required` desconcertante. Escribir
   siempre así:
   ```powershell
   [System.IO.File]::WriteAllText($f, $txt, (New-Object System.Text.UTF8Encoding($false)))
   ```
   Y verificar: los 3 primeros bytes no deben ser `EF BB BF`.

2. **Bloque DEV vs PROD.** `backend\.env` trae los dos; debe quedar activo **uno solo**.
   Fuera del 139, `DATABASE_URL` y `PGHOST` apuntan a `10.100.26.139` (requiere VPN), no a
   `localhost`.

3. **Guardar de verdad.** Editar en el editor sin `Ctrl+S` deja el archivo viejo en disco
   y el síntoma es indistinguible de un bug. Comprobar con `Get-Content`.

En producción, dejar **sin definir** `DEVELOPMENT_MODE` y `LOGIN_BYPASS_EMAILS`: si están,
se salta el LDAP.

---

## 6. Estado funcional del proyecto

- **Motor Q v2** con cuatro grupos de intención (Cuantificar, Jerarquizar, Analizar, OUT)
  más un detector de capacidades. Golden set de 92 casos al 96% (gate ≥90%).
- Dos interfaces de chat en paralelo: `/` (clásica) y `/mainchat`, ambas montan el mismo
  `multitab_shell.js`.
- Suite de 502+ tests pasando, con 10 fallos preexistentes y ajenos documentados.

### Deuda conocida (documentada, no bloqueante)

- El `rank` de «Focos de atención» no ordena realmente por impacto.
- No hay control de roles real más allá de la autenticación.
- `PLATA` en el léxico de economía dispara falsos positivos con «plataforma».
- El fallo «SIN RESPUESTA» en la primera pregunta tras cada reinicio sigue sin causa raíz.
- Corrupción física pendiente en `core.fact_tabla_hoja` (solo en la BD local).

---

## 7. Cómo trabajar aquí

- **Medir antes que razonar.** Para CSS y JS, el valor computado manda sobre el archivo:
  instrumentar y medir el DOM a la primera. Encadenar ajustes a ciegas no converge. A los
  dos intentos fallidos, parar y medir.
- **No medir endpoints FastAPI importándolos en proceso**: los defaults `Query(...)`
  falsean el resultado.
- **Conectar antes que construir.** Varias veces el trabajo real fue enchufar piezas que
  ya existían, no escribir nuevas. Revisar qué hay antes de crear.
- **Respetar el periodo de la pregunta.** Fue una fuente repetida de bugs silenciosos:
  responder el mes vigente ignorando el mes pedido, sin avisar.
- **Español** en respuestas y descripciones de avance.
- **Breve y claro.** La respuesta corta primero: conclusión, y solo el dato que la sostiene.
  Nada de tablas, listas ni resúmenes que no se hayan pedido. Si hay que decidir algo, una
  pregunta concreta al final — no un menú de opciones. Cuanto más corto, más productivo.
- **Comandos: decir siempre cómo se corren.** Con cada bloque, indicar **en qué carpeta**,
  si va **de una vez o línea por línea**, si hace falta **consola de administrador**, y qué
  salida se espera. Si el bloque es multilínea en PowerShell, avisar de que puede quedarse
  en `>>` y hay que pulsar Enter. Un comando sin esas cuatro cosas está a medias.

---

## 8. Recomendaciones

Recogidas de lo que costó caro en agosto. No son reglas abstractas: cada una tiene un
incidente detrás.

### Sobre los repos

**Una sola fuente de verdad, declarada.** Hoy conviven el monorepo `ProdIA-2.0` (GitHub) y
los dos repos de Azure DevOps. Mientras no se decida cuál manda, cada sincronización es una
oportunidad de perder contenido — que es exactamente lo que pasó con el puerto 5007.
Recomendación: **Azure DevOps `dev` es la fuente para lo que se despliega**, y el monorepo
queda como archivo histórico.

**Comparar por hash de blob, no por SHA de commit.** Estos repos nacieron de un export, así
que tienen historias distintas y sus SHA nunca coincidirán aunque el contenido sea idéntico.
Lo que sirve es comparar `git ls-tree -r HEAD` de cada uno y contrastar el hash de cada
archivo. Así se verificó, con certeza, que el código está alineado.

**No versionar binarios ni temporales.** El `.gitignore` ya cubre `vector_db/`, `temp_*`,
`*.bak` y `*[- ]Copy.*` — pero `ProdIAWebFront` arrastra ~151 MB que entraron antes de que
existiera esa regla. Sacarlos del índice; una vez dentro de la historia, quitarlos exige
reescribirla.

**Identidad de git según la máquina.** La identidad corporativa va solo donde se hace push
a Azure DevOps. En la máquina local no debe quedar configurada, ni remotos de Azure.

### Sobre el despliegue

**Verificar siempre, no cuando alguien se acuerda.** `verificar_deploy.ps1` existe y
funciona: comprueba el puerto, el rediseño del login y **todos** los estáticos que
`login.html` referencia. Debe correr como parte del despliegue, no a petición.

**Fijar Python por versión exacta.** No `>=3.12`, sino un pin real (`.python-version` o
`uv --python 3.12`). Un `py -3` en una máquina nueva toma la más reciente instalada y se
lleva por delante `onnxruntime`.

**Generar los `.env`, no editarlos a mano.** Un paso que valide que las variables requeridas
existen, con el formato esperado, sin BOM y sin plantillas a medio llenar — antes de
arrancar cualquier servicio.

**Documentar las políticas de rama de Azure DevOps de antemano.** Cuáles exigen PR, cuáles
bloquean ForcePush. Descubrirlas a los golpes costó varios intentos de push fallidos.

### Sobre cómo trabajar

**Medir en el entorno correcto, y decirlo.** Antes de afirmar algo sobre lo que el usuario
ve, preguntarse: *¿esto lo medí en su entorno o en el mío?* Si es el mío, decirlo al
reportar.

**Un comando decisivo, no una lista.** Cuando haga falta un dato del servidor, pedir uno
solo que zanje la duda.

**Conectar antes que construir.** El patrón más productivo del mes fue enchufar piezas que
ya existían. Revisar qué hay antes de escribir algo nuevo.

**Anotar y seguir.** Cuando el usuario describe su entorno, está dando contexto, no pidiendo
una auditoría. Si algo no cuadra, guardarlo y mencionarlo una vez, al final — no interrumpir
con ello.

---

## 9. El pipeline de despliegue

Definido el 2026-08-29. Es el proceso repetible que pedía el postmortem, y sustituye a la
cadena manual de exports y copias que costó ocho horas.

```
   LOCAL (sin VPN)              PRUEBAS (con VPN)                        139
   ──────────────               ─────────────────                        ───
                        ┌─ C:\APLICACIONES\ProdIA\Repo ProdIA
   editar ──push──→ GitHub          (clon de GitHub — aquí se PRUEBA)
                        │                    │
                        │                    │  skill  migrar-a-azure
                        │                    ▼
                        └─ C:\APLICACIONES_AZURE\Repo ProdIA
                                 (clon de Azure — aquí se PUBLICA)
                                             │
                                             └─push─→ Azure DevOps `dev` ──→ producción
```

### Las dos carpetas de Pruebas están separadas a propósito

Cada una tiene **su propio `.git` y un único remoto**. No se mezclan: así no hay forma de
empujar por error a Azure algo que no se ha probado, ni de contaminar el checkout de
pruebas con historia de Azure.

| Carpeta | Remoto | Para qué |
|---|---|---|
| `C:\APLICACIONES\ProdIA\Repo ProdIA` | GitHub `main` | Bajar lo nuevo y **probarlo** |
| `C:\APLICACIONES_AZURE\Repo ProdIA` | Azure DevOps `dev` | **Publicar** lo ya probado |

### El puente: skill `migrar-a-azure`

Vive en `frontend/.claude/skills/migrar-a-azure/`. Siempre en tres tiempos:

```powershell
.\.claude\skills\migrar-a-azure\migrar_a_azure.ps1            # 1. ¿qué hay pendiente?
.\.claude\skills\migrar-a-azure\migrar_a_azure.ps1 -Aplicar   # 2. copiar y verificar
.\.claude\skills\migrar-a-azure\migrar_a_azure.ps1 -Push      # 3. publicar en Azure
```

Una copia de archivos **no garantiza fidelidad** — fue la causa del incidente del puerto
5007. Por eso el script, después de copiar, compara el hash de blob de cada archivo
versionado contra el origen y **aborta si uno solo difiere**. También copia en modo espejo
(para que los borrados viajen), excluye `.env`, entornos y binarios regenerables, y escribe
el SHA de GitHub en el mensaje del commit de Azure, para que siempre se sepa qué versión
está desplegada.

### Reglas del pipeline

1. **Azure solo recibe de este pipeline.** Nunca commitear directo allí. Ya pasó dos veces
   (el commit inicial de julio y los arreglos a mano en el 139 el 26-ago) y es como nacen
   las «dos últimas versiones».
2. **Nada llega a Azure sin haber corrido en Pruebas.**
3. **`verificar_deploy.ps1` antes de dar por bueno un despliegue**, no cuando alguien se
   acuerda.
4. **En local, ningún remoto de Azure ni identidad corporativa.**
5. **El origen debe estar limpio** al migrar: lo que se publique tiene que corresponder a un
   commit real de GitHub, o se pierde la trazabilidad.

### Lo que todavía es manual

El tramo **Azure DevOps → servidor 139** no está automatizado. Es el hop que más caro salió
y el siguiente candidato a resolverse.

### Sobre desarrollar en local

Desde local **no hay VPN**, así que no se alcanza la BD del 139. En local se puede editar,
correr tests y goldens, y medir el DOM — nada de eso depende de los datos. Pero **cualquier
validación contra datos reales ocurre en Pruebas.** La BD local está congelada en mayo de
2026 y arrastra corrupción en `core.fact_tabla_hoja`: no sirve como referencia.

---

## 10. Modo Planner (`plan:`) y el flujo profesional

> Fuente canónica: `backend/clmd/CLAUDE_muestra.md` §0.2, §0.3, §15 y §17.5.
> Esta sección lo resume y lo adapta a ProdIA.

### 10.1 El flujo profesional — 6 pasos

Antes de cualquier tarea no trivial:

```
Mapeo → Auditoría → Diagnóstico → Propuesta → Aplicación → Verificación
```

**No saltarse pasos. Propuesta completa antes de aplicar.** Si un hallazgo toca una decisión
cerrada del usuario, detenerse y escalar.

### 10.2 🔴 Directiva obligatoria: auditar ANTES de escribir el plan

**Los pasos 1-3 (Mapeo + Auditoría + Diagnóstico) se ejecutan internamente ANTES de entregar
un plan.** El plan que llega al usuario debe ser ya equivalente a un **v2 auditado**.

❌ **Nunca** entregar un «v1 rápido» sabiendo que falta auditar, para arreglarlo en «v2»
cuando el usuario detecte los fallos. Eso traslada al usuario la carga de validar la calidad
del plan, y es inaceptable.

Se ganó a los golpes: hubo planes improvisados que produjeron 13 y 25 hallazgos en su v2 —
hallazgos que debieron descubrirse antes de entregar nada.

**La auditoría es obligatoria si la tarea cumple ≥1 de estos criterios:**

- Toca más de 3 archivos.
- Introduce funciones, módulos o utilidades nuevas.
- Modifica archivos compartidos (`multitab_shell.js`, `app.py`, `routes/api.py`, CSS global).
- Implica cambios en el contrato entre Flask y INGESTA.
- Toca el clasificador o el Motor Q v2.

**Acciones mínimas antes de escribir:**

1. **Grep del patrón ya existente.** Si vas a crear algo, mirar cómo se hizo lo equivalente.
   Casi siempre hay un precedente resuelto — clonarlo, no reinventarlo.
2. **Read completo del archivo a modificar.** Nunca de memoria.
3. **Contar los call sites reales** de lo que vas a cambiar. Un `grep -n` decide el diseño:
   si hay cinco y crees que hay cuatro, el plan nace roto.
4. **Cruzar contra la deuda conocida** (§6 de este documento).

### 10.3 Modo Planner: qué pasa cuando el usuario escribe `plan:`

Claude actúa **exclusivamente como Planner**. No ejecuta código.

| Regla | Detalle |
|---|---|
| Solo genera el plan | Cero archivos fuera de `Planes/`. Cero comandos. Cero ediciones a código |
| 100% autocontenido | El executor **no** tiene la conversación, ni el historial de git, ni memoria |
| Rutas absolutas | Nunca «el archivo del shell»; siempre la ruta completa |
| Código de referencia completo | Si el plan pide crear algo, va el código entero |
| Decisiones cerradas | El executor no decide nada, solo implementa |
| Criterios verificables | Tabla con comando y resultado esperado |
| Naming | `Planes/plan_[ID_TAREA]_[fecha].md` |
| Entrega | Ruta + resumen de 5 líneas → esperar **«¿Aprobado?»** |

**Secciones obligatorias del plan:**

```
0. Contexto para el agente EXECUTOR    ← proyecto, rutas, convenciones
1. Hallazgos de la auditoría           ← 🔴 bloqueante · 🟡 relevante · 🟢 confirmación
2. Estado actual                        ← qué está mirando el executor
3. Especificación                       ← MODIFICAR / AÑADIR, con código exacto
4. Orden de ejecución                   ← tabla numerada
5. Reglas no negociables
6. Validación                           ← 6.1 estática (executor) · 6.2 humana (usuario)
7. Fuera de alcance                     ← explícito
```

Los hallazgos van **antes** de la especificación y **la determinan**: explican por qué la §3
es como es. No son decorativos.

**Prompt estándar para el executor:**

```
Eres un agente EXECUTOR. Lee completo el plan indicado y ejecútalo AL PIE DE LA LETRA.
Reglas: CERO modificaciones. Orden secuencial. Si falla, DETENTE. Reporta: ✅/❌ Paso N.
Al final: archivos tocados + "¿Hago commit?"
```

### 10.4 🔴 Regla R3 — «build verde» NO es «feature verificada»

Un executor puede reportar tests ✅, lint ✅ y build ✅ **con la feature rota en runtime**.
No tiene navegador: no puede hacer hover, ni ver si un panel se pinta.

**Lo que ninguna herramienta automática detecta:**

- Animaciones interrumpidas, re-renders innecesarios.
- Layout colapsado por flex/grid en un viewport real.
- Eventos de ratón mal cableados (hover roto, clic duplicado).
- Un panel que se destruye al repintar su contenedor.

**Protocolo antes de declarar algo «completado»:**

1. Abrir `http://localhost:5029/<ruta>` y validar carga, interacciones del camino feliz,
   persistencia al navegar fuera y volver, y **F12 → Console con 0 errores**.
2. Si no se puede abrir el navegador, el estado correcto es
   **«implementado, PENDIENTE de validación humana»**, no «verificado».
3. **El único que marca ✅ una feature visual es el usuario.**

Esto vale doble aquí, porque la app real corre en el servidor de pruebas, no en local.

### 10.5 Anti-patrones prohibidos

- ❌ Entregar un plan v1 «rápido» sabiendo que falta auditar.
- ❌ Asumir rutas, convenciones o configuraciones «de memoria».
- ❌ «Esto probablemente funciona, ya lo confirmará el test» — confirmar **antes** de escribir.
- ❌ Esperar a que el usuario pida «aplica el flujo profesional»: ya está aplicado por defecto.
- ❌ Justificar incoherencias con «el v2 las arreglará» — el v1 no debería existir.
- ❌ Si un parche reactivo se acumula **más de 2 iteraciones** sin resolver el bug: **DETENER**
  y revertir al último estado bueno conocido. No seguir parchando.

### 10.6 Dónde viven los planes

```
frontend\Planes\      planes de UI, shell, paneles, login
backend\Planes\       planes del Motor Q, features, ETL, BD
```

Cada repo guarda los suyos. El naming es `plan_<slug>_<fecha>.md`, y los planes viejos se
conservan: son el registro de por qué el código es como es.

---

*Ver `BITACORA.md` para el historial. Guía de arranque detallada en
`frontend\SETUP_LOCAL.md`. Postmortem de la migración en
`frontend\POSTMORTEM_migracion_puertos_azure_20260826.md`.*
