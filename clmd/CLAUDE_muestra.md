# CLAUDE.md — Robustez V2.0 (FastAPI + React 19)

> Memoria de proyecto para Claude Code. Punto de entrada para retomar contexto sin tener que releer todo.
> **Codebase nuevo** (no es refactor de V01) — vertical slicing por features, alineado con `Plan_Migracion_Robustez_V06.docx` v0.6.

---

## 0. Idioma de comunicación

**⚠️ OBLIGATORIO:** Toda la comunicación con Claude Code debe ser **100% en español**. Sin excepciones:
- Mensajes del usuario → español
- Respuestas de Claude Code → español
- Comentarios en código → español (documentación, TODOs, ADRs)
- Commits → español (`feat(W1.4): crear robustez_v02_auth.db con DDL v0.2`)
- Nombres de ramas → español si es posible, en su defecto snake_case inglés

> Si Claude Code usa inglés, el usuario debe interrumpir y recordarle esta directriz explícitamente.

---

## 0.1 Estilo de respuesta — IMPORTANTE

- Sé breve y conciso. Ve directo al grano.
- No expliques lo que vas a hacer antes de hacerlo.
- No resumas lo que hiciste después de hacerlo, salvo que el resultado lo amerite.
- Sin preámbulos tipo "Claro", "Por supuesto", "Con gusto".
- Si la respuesta es código, entrega el código. Sin contexto innecesario.
- Si necesitas explicar, máximo 2-3 líneas.
- Responde siempre en español, usando tuteo informal.

---

## 0.2 Directiva obligatoria del Planner — auditoría previa antes de escribir

🔴 **ANTES de escribir cualquier plan (`plan:`) Claude Code debe ejecutar internamente los pasos 1-3 del flujo profesional §15** (Mapeo + Auditoría + Diagnóstico). NO entregar nunca un plan "v1 improvisado" para luego mejorarlo en "v2" cuando el usuario detecte fallos.

### Razón de esta directiva

Lecciones aprendidas en F4.8 y F5.0 (2026-05-23): Claude Code entregó planes improvisados sin auditar el código real. El usuario tuvo que pedir explícitamente "aplica el flujo profesional" para que la auditoría se hiciera. Resultado: 13 hallazgos en F4.8 v2 y 25 hallazgos en F5.0 v2 que **debieron descubrirse antes** de entregar el plan al usuario. Eso traslada la carga de validar la calidad del plan al usuario — inaceptable.

### Compromiso obligatorio

El plan que se entrega al usuario debe ser ya equivalente a un **v2 auditado**. Si la auditoría revela algo bloqueante (decisión D1-D14 afectada, riesgo crítico), avisar ANTES de escribir el plan completo.

### Checklist mínimo antes de escribir un plan

Si la tarea cumple ≥1 de estos criterios, los pasos 1-3 son obligatorios:
- Toca >3 archivos.
- Introduce primitivos, hooks, utils o servicios nuevos.
- Modifica archivos compartidos (`router.tsx`, `LayoutMain`, stores, `vite.config`, `package.json`).
- Implica imports cross-feature o cambios de routing.
- Cambia el contrato entre Interceptor 1 (Pydantic) e Interceptor 2 (mappers).

Acciones mínimas obligatorias antes de escribir:

1. **Grep del patrón de archivos similares ya existentes.** Ej.: si vas a crear un primitivo, leer `ls primitives/Button/` para confirmar la convención (incluye `.test.tsx`, `index.ts`, etc.).
2. **Read del archivo a modificar** completo, no de memoria.
3. **Verificación de paths `@use` SCSS** contra archivos vecinos a la misma profundidad.
4. **Lectura de configs relevantes** (`vitest.config.ts`, `vite.config.ts`, `package.json`, `_tokens.scss`, `.npmrc`).
5. **Cruzar contra deuda técnica §17** (DT-9, DT-10, DT-11, DT-13, DT-14, DT-15, DT-16, DT-17 — comprobar si la tarea las activa).
6. **Cruzar contra reglas duras §17.5 R1/R2/R3** (no tocar `.npmrc`, no acoplar selección al `data` de Plotly, no declarar "completado" sin validación humana).

### Qué hacer si la auditoría revela un bloqueante

- Decisión D1-D14 afectada → detener y escalar al usuario antes de seguir.
- DT-13 activa (la tarea requiere `pnpm install`) → escalar; no proponer instalación.
- Patrón del proyecto contradice una intención del plan → ajustar el plan al patrón, no inventar uno nuevo.

### Anti-patrones explícitamente prohibidos

- ❌ Entregar un plan v1 "rápido" sabiendo que falta auditar.
- ❌ Asumir paths, convenciones o configs "de memoria".
- ❌ Decir "esto probablemente funciona, lo confirma el typecheck" — confirmar antes de escribir, no después.
- ❌ Esperar a que el usuario pida "aplica el flujo profesional" — ya está aplicado por defecto.
- ❌ Justificar incoherencias con "el v2 las arreglará" — el v1 no debe existir.

---

## 0.3 Modo Planner para ejecución externa

Cuando el usuario escriba `plan:` al inicio de su mensaje, Claude Code actúa exclusivamente como **Planner**. NO ejecuta código. Solo genera un archivo `.md` en `Planes/` con la especificación completa para que un **agente externo sin acceso al repositorio ni contexto previo** pueda ejecutarlo al pie de la letra.

### Reglas del Planner

1. **Solo genera el plan, nunca ejecuta.** Cero archivos creados fuera de `Planes/`. Cero comandos bash. Cero ediciones a código. Solo el `.md`.
2. **El plan debe ser 100% autocontenido.** El agente executor NO tiene acceso a conversaciones previas, historial de Git, ni memoria de decisiones anteriores.
3. **Rutas absolutas siempre.** Nunca "el archivo del layout". Siempre `robustez_v02_frontend/src/shared/components/primitives/Button/Button.tsx`.
4. **Código de referencia obligatorio.** Si el plan pide crear un archivo, incluir el código completo.
5. **Contexto del proyecto inline.** Stack, estructura de carpetas relevante, convenciones, variables de entorno.
6. **Dependencias explícitas.** Qué debe existir antes + check de verificación ejecutable.
7. **Criterios de aceptación verificables** — tabla con comando y resultado esperado.
8. **Decisiones cerradas.** El executor no decide nada — solo implementa.
9. **Secciones obligatorias:** Contexto → Objetivo → Prerequisitos → Inventario archivos → Especificación → Orden ejecución → Reglas no negociables → Validaciones → Fuera de alcance.
10. **Naming:** `Planes/plan_[ID_TAREA]_[fecha].md`
11. **Modo A:** Mostrar ruta + resumen 5 líneas → esperar "¿Aprobado?"

> Especificación canónica completa: [`Migracion/instruccion_planner_claude_code.md`](./Migracion/instruccion_planner_claude_code.md)

### Prompt estándar para el executor

```
Eres un agente EXECUTOR. Lee completo el plan indicado y ejecútalo AL PIE DE LA LETRA.
Reglas: CERO modificaciones. Orden secuencial. Si falla, DETENTE. Reporta: ✅/❌ Paso N.
Al final: archivos tocados + "¿Hago commit?"
```

---

## 0.4 Modo Backup (`backup:`)

Cuando el usuario escriba `backup:` al inicio del mensaje, Claude Code ejecuta `pnpm backup` → `scripts/backup.ps1`. Único modo: full siempre (Tier 1 + Tier 2, ~350 MB).

- **Destino fijo:** `E:\APLICACIONES\Robustez\back_robustez_2.0` (se crea automáticamente).
- **Naming:** `backup_robustez_v02_{YYYYMMDD_HHMM}.zip`.
- **Retención:** indefinida — cleanup manual cuando haga falta.
- **Script:** [`scripts/backup.ps1`](./scripts/backup.ps1) (PowerShell puro, sin dependencias).

### Qué se respalda

**Tier 1 — Irrecuperables:**
- `robustez_v02_backend/.env` (SECRET_KEY único)
- `.claude/settings.local.json` (allowlist personal)
- BD SQLite: `robustez_v02_auth.db` (+ WAL/SHM) y `bitacora.db`
- `data/wells_attributes_duplicados.csv` (análisis intermedio)
- Carpetas: `Planes/`, `docs/claude/`, `Migracion/` (sin `Plantilla base/`)
- **Código untracked en `src/`, tests, scripts** (filtrado por extensión)
- `CLAUDE.md.bak_*`, `Start_*.bat`, `Gota.png`

**Tier 2 — Caros de regenerar:**
- `data/seeds/*.csv` (~215 MB)
- `data/robustez_v02.db` (~127 MB)

**Brechas conocidas (cubrir aparte si se necesita recovery total):**
- Código **tracked en git** — no hay git remote configurado, la historia vive solo en `.git/` local. Considerar configurar remote (Azure DevOps / GitHub privado) o `git bundle create repo.bundle --all`.
- **PostgreSQL schema `ops`** — la BD operacional real → `pg_dump -n ops robustez_v02 > ops_YYYYMMDD.sql`.
- `node_modules/`, `.venv/`, caches, `dist/` (regenerables con `pnpm setup`).

Cada .zip incluye `BACKUP_MANIFEST.md` en su raíz con: lista de archivos, `git HEAD`, branch y receta de restauración.

---

## 1. Descripción general

**Cliente:** Ecopetrol S.A.
**Proyecto:** WebApp Robustez V2.0 — migración de V01 (Flask + Vanilla JS, `../Des_Robustez/`) a stack moderno preservando paridad funcional y numérica.

**V01 sigue operativa** (`:5096` Des / `:5002` Prod). V2.0 en paralelo `:6024` (back) / `:6023` (front) — mismos puertos en dev local y servidor `10.100.26.139`.

### Qué hace la aplicación
Plataforma de analítica operacional para producción de hidrocarburos:
- Dashboard de KPIs (Qo, Qw, Qg) por pozo, campo, activo
- Análisis EBITDA en múltiples variantes (KUSD, USD/Bl, Real, Tasa, Activos, A+I)
- Priorización económica de pozos, predicción/regresiones, reportes Excel
- Login LDAP corporativo + RBAC granular por campo y sección

**Roles:** Admin (acceso total) | Limitado (ej. Orinoquia: solo campos asignados al grupo)

---

## 2. Stack tecnológico

### Backend (`robustez_v02_backend/`)

| Componente | Versión | Uso |
|------------|---------|-----|
| Python | 3.12+ | Lenguaje |
| FastAPI | latest | Framework + OpenAPI auto |
| SQLAlchemy | 2.0+ | ORM |
| Alembic | latest | Migraciones BD |
| Pydantic | 2.x | Validación + Interceptor 1 (alias) |
| ldap3 | 2.9+ | Auth AD `red.ecopetrol.com.co` |
| structlog | latest | Logs JSON UTC |
| itsdangerous | 2.x | Cookie firmada de sesión |
| uv | latest | Package manager |
| Ruff + Black + mypy | latest | Lint + format + type check |

### Frontend (`robustez_v02_frontend/`)

| Componente | Versión | Uso |
|------------|---------|-----|
| React | 19 | UI |
| TypeScript | 5.x | Tipado estricto |
| Vite | latest | Bundler / dev server |
| TanStack Query | v5 | Estado de servidor |
| Zustand | 5 | Estado global cliente |
| react-hook-form | 7.74 | Formularios |
| zod | 4.3 | Validación schemas |
| react-router-dom | latest | Routing SPA |
| Sass | latest | Estilos |
| Lucide React | latest | Iconografía tree-shakeable |
| openapi-typescript + openapi-fetch | latest | Tipos auto + cliente HTTP tipado |
| Vitest + RTL | latest | Tests unitarios |
| Playwright | latest | Tests E2E |
| pnpm | latest | Package manager + workspaces |

---

## 3. Estructura del monorepo

```
Des_robustez_2.0/
├── CLAUDE.md
├── package.json                       ← monorepo orchestrator (concurrently, husky, lint-staged)
├── pnpm-workspace.yaml
├── Start_Back.bat / Start_Front.bat   ← arranque rápido servidor (0.0.0.0:6024 / 0.0.0.0:6023)
├── Planes/                            ← 105 planes de ejecución para agente EXECUTOR
├── Migracion/                         ← documentos fuente (plan, DDL, Gantts)
├── .agents/skills/
│   └── emil-design-eng/SKILL.md       ← skill instalado (Emil Kowalski — UI polish + animation)
├── docs/
│   ├── decisions/                     ← ADR-001 monorepo, ADR-002 bitácora
│   └── claude/                        ← bd_operacional_v10, design_system, bitacora_guia, flujo_6_pasos
│
├── robustez_v02_backend/
│   ├── .env / .env.dev / .env.server / .env.example
│   ├── src/
│   │   ├── main.py                    ← monta 14 routers de features
│   │   ├── core/                      config (puertos/CORS/BD), logger, secrets, exceptions
│   │   ├── features/
│   │   │   ├── auth/                  api, services, repositories, models, schemas ✅
│   │   │   ├── permissions/           PermissionService + 4 tablas RBAC ✅
│   │   │   ├── audit/                 auth_events instrumentada ✅
│   │   │   ├── filters/               GET /hierarchy/{level} + /periods/years + /periods/months/{year} ✅
│   │   │   ├── kpis_financieros/      api + services + schemas + waterfall_service + waterfall_utilidades_service + waterfall_schemas ✅
│   │   │   ├── kpis_costos/           api + services + schemas + services_costos_fijos + services_costos_gastos + services_costos_usdbl ✅
│   │   │   ├── kpis_produccion/       api + services + schemas ✅ (🔴 valores inflados — DT-18)
│   │   │   ├── kpis_operacionales/    api + services + schemas (QO/QW/EBITDA pre-login) ✅
│   │   │   ├── kpis_mercado/          api + repository + services + schemas (Brent/WTI/TRM/Ecopetrol pre-login) ✅
│   │   │   ├── kpis_delta/            api + services + schemas (Δ BRENT, Δ DIF OIL, Δ PRODUCCIÓN, Δ TRM) ✅
│   │   │   ├── ebitda_rank/           api + services + schemas + well_condition parametrizado (3 criterios) ✅
│   │   │   ├── regression/            api + services + schemas (classify_well integrado) ✅
│   │   │   ├── detalle_ingresos/      api + services + schemas (GET /ingresos-combo — 4 series mensuales) ✅
│   │   │   ├── reports/               (stub — S7+)
│   │   │   └── prediction/            (stub — S7+)
│   │   ├── shared/                    db, utils, well_condition.py (classify_well + resolve_columns + build_condition_select_columns) ✅
│   │   └── middleware/                correlation_id, auth, request_logger
│   ├── alembic/versions/              0001_initial_auth.py
│   ├── tests/
│   │   ├── unit/                      127 passed + 3 skipped ✅
│   │   └── integration/               3 tests (incluye test_login_real.py vs LDAP) ✅
│   ├── scripts/                       37 scripts Python (ETL, bitácora, migración, validación)
│   └── data/                          robustez_v02_auth.db (8t, 1745 filas) · robustez_v02.db · bitacora.db
│
└── robustez_v02_frontend/
    ├── vite.config.ts                 ← lee VITE_PORT (6023) y VITE_BACKEND_PORT (6024) de env
    ├── src/
    │   ├── app/
    │   │   ├── App.tsx · router.tsx · providers.tsx
    │   │   ├── layouts/
    │   │   │   ├── LayoutMain.tsx      ← layout principal (Header + DrawerStrip + Footer + KpiTicker)
    │   │   │   └── components/
    │   │   │       ├── Header/         Header.tsx + AvatarPanel (tarjeta) + WaffleLauncher ✅
    │   │   │       ├── Footer/         Footer.tsx ✅
    │   │   │       └── Breadcrumb/     Breadcrumb.tsx + breadcrumbConfig.ts ✅
    │   │   └── store/
    │   │       ├── authStore.ts        sesión usuario ✅
    │   │       ├── drawerStore.ts      estado drawer ✅
    │   │       ├── filtersStore.ts     jerarquía draft/applied ✅
    │   │       ├── periodoStore.ts     período draft/applied + _isInitialized ✅
    │   │       ├── wellConfigStore.ts  well config draft/applied + countDraftFromDefault ✅
    │   │       └── tickerOverrideStore.ts  overrides ticker por ruta ✅
    │   ├── features/
    │   │   ├── auth/                   LoginPage (splash+BetaBanner+DashboardPreview) · hooks (useLogin/useLogout/useCurrentUser/useLoginKpis/useMarketKpis/useSessionExpiry) · mappers · schemas · services ✅
    │   │   ├── home/                   HomePage · Carousel ✅
    │   │   ├── filters/
    │   │   │   ├── schemas/            wellConfigSchema.ts (Zod, 4 uniones tipadas) ✅
    │   │   │   ├── services/           periodoService.ts · filtersService.ts ✅
    │   │   │   ├── utils/              periodoRange.ts ✅
    │   │   │   ├── hooks/              useHierarchyFilters.ts · usePeriodoFilters.ts ✅
    │   │   │   └── applied-filters/    AppliedFiltersPanel + MobileAppliedFiltersSheet + hooks + types ✅
    │   │   ├── ebitda_costos/
    │   │   │   ├── pages/              EbitdaCostosPage ✅
    │   │   │   ├── components/         EbitdaInspectorCard · InspectorHeader · InspectorSidebar · InspectorRail (chartPanels ×4) · ChartPillsMobile · WaterfallChart · InspectorThumbnail · InspectorExpandToggle ✅
    │   │   │   ├── hooks/              useEbitdaKpis · useKpiQoQw · useEbitdaWaterfallData · useUtilidadesWaterfallData · useUtilidadesKpis ✅
    │   │   │   ├── mappers/            ebitdaKpiMapper · ebitdaWaterfallMapper · utilidadesKpiMapper ✅
    │   │   │   ├── services/           ebitdaKpiService · kpiProductionService · ebitdaWaterfallService · utilidadesWaterfallService · utilidadesKpiService ✅
    │   │   │   ├── store/              inspectorUiStore (activeUnit · activeChart · expanded) ✅
    │   │   │   ├── utils/              formatInspectorValue ✅
    │   │   │   └── types/              waterfall.ts (con campo `type`) ✅
    │   │   ├── ebitda_rank/
    │   │   │   ├── pages/              EbitdaRankPage (layout 2-panel inline expand desktop · modal mobile) ✅
    │   │   │   ├── components/         TendenciaEbitdaChart · RangeSlider · KpiStrip · KpiCard · CardHeader · WellConditionMap · ChartModal · CollapsedTab · CurvasWaffle · CondicionWaffle (tiles) ✅
    │   │   │   ├── hooks/              useEbitdaRankData · useEbitdaKpis · useWellConditionData ✅
    │   │   │   ├── mappers/            ebitdaRankMapper · ebitdaKpiMapper · wellConditionMapper ✅
    │   │   │   ├── services/           ebitdaRankService · ebitdaKpiService · wellConditionService ✅
    │   │   │   └── types/              rankingTypes · wellCondition (ConditionCriterio) ✅
    │   │   ├── reports/
    │   │   │   ├── pages/              ReportsPage (layout sidebar + SoonPage placeholder) ✅
    │   │   │   ├── hooks/              useEbitdaKpis (ticker overrides) ✅
    │   │   │   ├── mappers/            ebitdaKpiMapper ✅
    │   │   │   └── services/           ebitdaKpiService ✅
    │   │   ├── regresiones/
    │   │   │   ├── pages/              RegresionesPage ✅
    │   │   │   ├── components/         CategoryChips · ChartModal · ControlSidebar · EquationCard · FeaturedChart · FieldSelect · InputsForm · PageHeader · ViewRail · WaterRangeSlider · charts/ (PlaneChart3D + PredVsActualChart) ✅
    │   │   │   ├── hooks/              useRegressionData ✅
    │   │   │   ├── mappers/            regressionMapper ✅
    │   │   │   ├── services/           regressionService ✅
    │   │   │   ├── schemas/            regressionSchema ✅
    │   │   │   ├── store/              predictionUiStore ✅
    │   │   │   └── utils/              calcOLS · calcMulti · calcPredict ✅
    │   │   ├── detalle_ingresos/
    │   │   │   ├── pages/              DetalleIngresosPage (sidebar + grid 2×2 + KPIs delta en ticker) ✅
    │   │   │   ├── charts/             ChartsGrid + ChartCard + ExpandToggleButton + chart.config ✅
    │   │   │   ├── components/         DeltaKpiStrip (standalone) ✅
    │   │   │   ├── hooks/              useIngresosCombo + useKpisDelta ✅
    │   │   │   ├── mappers/            kpisDeltaMapper ✅
    │   │   │   ├── services/           ingresosComboService + kpisDeltaService ✅
    │   │   │   ├── state/              chartsStore (Zustand expandedId) ✅
    │   │   │   └── types/              types.ts + deltaKpi.ts ✅
    │   │   ├── seguimiento/
    │   │   │   ├── pages/              SeguimientoPage (PageHeader + KpiRibbon mock + ChartRail + FeaturedChart) ✅
    │   │   │   ├── components/         PageHeader + KpiRibbon + KpiRibbonCard + KpiSparkline + ChartRail + ChartThumbnail + ExpandToggle + FeaturedChart + charts/ (EbitdaChart + QoQwChart + VarsChart) ✅
    │   │   │   ├── store/              seguimientoUiStore ✅
    │   │   │   ├── data/               mockKpis + mockSeries ✅
    │   │   │   ├── utils/              format (fmtK, fmtPct) + btnToPanel ✅
    │   │   │   └── types/              seguimiento.ts + series.ts ✅
    │   │   ├── detalle_costos/
    │   │   │   ├── pages/              DetalleCostosPage (sidebar + CostosGastosCard) ✅
    │   │   │   ├── components/         CostosGastosCard · StackedBarChart · StackedBarPreview · ComboBarPreview ✅
    │   │   │   ├── hooks/              useCostosFijosKpis · useCostosUsdBl ✅
    │   │   │   ├── mappers/            costosFijosKpiMapper ✅
    │   │   │   ├── services/           costosFijosKpiService · costosUsdBlService ✅
    │   │   │   └── types/              costosFijosKpi.ts ✅
    │   │   ├── detalle_dilucion/       DetalleDilucionPage (stub) ✅
    │   │   ├── mook_evaluacion/
    │   │   │   ├── pages/              MookEvaluacionPage (sidebar + BeneficiosTable + grid 2 charts SVG) ✅
    │   │   │   ├── components/         BeneficiosTable · RegresionChart (RegresionSvg) · DeltaEbitdaChart (DeltaEbitdaSvg) · MockChartModal (<dialog>) · MockCardHeader ✅
    │   │   │   ├── mock/               actividades.mock · regresion.mock · deltaEbitda.mock ✅
    │   │   │   ├── types/              mookEvaluacion.ts ✅
    │   │   │   ├── utils/              formatMiles.ts ✅
    │   │   │   └── styles/             _palette.scss ($mk-* 14 vars) ✅
    │   │   └── [analytics · admin · help · settings]   stubs — S7+
    │   └── shared/
    │       ├── components/
    │       │   ├── primitives/         Button · Input · Card · Badge · Spinner · Tooltip · Modal · Toast · UnitToggle (9 con tests) ✅
    │       │   ├── charts/             ComboChart (Plotly bar+line · createPlotlyComponent · useResizeHandler) ✅
    │       │   ├── navigation/         AppMenuPopover + AppList + AppPill + SubViewGrid + SubViewTile + nav.config (hover popover + tarjetas descripción) ✅
    │       │   ├── kpi/                KpiTicker (marquee animado + TickerItem delta layout INICIO|Δ|FIN) · Sparkline ✅
    │       │   ├── filters/
    │       │   │   ├── HierarchyPills/       F1 ✅ — acordeón 6 niveles · búsqueda >8 · teclado · auto-cleanup cascada
    │       │   │   ├── PeriodoControls/      F2 ✅ — MiniCalendar · YearMonthSelect · PeriodoSummary · RangeWarningBanner · bootstrap YTD fix
    │       │   │   └── WellConfigControls/   F3 ✅ — OptionTile<T> · BinarySelector<T> genéricos · icon-leading · accent CSS var
    │       │   ├── Drawer/
    │       │   │   ├── Drawer.tsx             3 tabs wireteados (jerarquía/período/wellconfig) Limpiar+Aplicar ✅
    │       │   │   ├── Drawer.module.scss     limpio (fix mobile top:var(--header-h)) ✅
    │       │   │   └── panels/               JerarquiaPanel + PeriodoPanel + WellConfigPanel ✅
    │       │   ├── ErrorBoundary · ErrorPages (Forbidden+NotFound) · SessionExpiryBanner · SoonPage · skeletons · ProtectedRoute ✅
    │       │   └── forms/                     (S6+)
    │       ├── icons/                         ✅
    │       ├── services/                      apiClient.ts (openapi-fetch tipado) ✅
    │       └── hooks/                         ✅
    ├── tests/
    │   ├── setup/                     vitest.setup.ts (jest-dom + ResizeObserver mock) ✅
    │   ├── unit/
    │   │   └── auth/                  ⚠️ UNTRACKED · tests rotos (ver DT-8)
    │   └── e2e/                       (Playwright — pendiente)
    └── docs/                          RESPONSIVE_STRATEGY.md ✅
```

**Regla operativa:** una feature solo importa de `shared/` o `core/`/`app/` — **nunca** de otra feature.

---

## 4. Decisiones bloqueadas (D1–D14)

| # | Decisión |
|---|----------|
| D1 | Ubicación: `E:\APLICACIONES\Robustez\Des_robustez_2.0\` con subcarpetas `robustez_v02_backend/` y `robustez_v02_frontend/` |
| D2 | Sin Azure DevOps esta semana (postponed a S6+) |
| D3 | Sin reverse proxy `/v02/` — back `:6024` / front `:6023` independientes (mismos puertos dev+servidor) |
| D4 | LDAP real desde día 1 (sin mock) — `red.ecopetrol.com.co` |
| D5 | Whitelist de emails abolida — solo tabla `app_users` |
| D6 | Seguridad: 6 capas según plan v0.6 §2.7 (HTTPS diferido a despliegue) |
| D7 | BD operacional v10 en uso desde S6 — solo `robustez_v02_auth.db` en MVP |
| D8 | Réplica completa diapositiva "services" + vínculos a placeholders en 8 secciones |
| D9 | 2 devs full-stack: J=backend lead, C=frontend lead |
| D10 | Modal zoom 70% post-login **eliminado** definitivamente |
| D11 | Plotly **activado en F7** — bundle `plotly.js` (~1.5MB gzip). Optimización a `plotly.js-finance-dist-min` documentada como DT-12 |
| D12 | Responsive ampliado a mobile en F6 — rango 360–1920px. M1 bottom sheet para <1024px. Estrategia: `frontend/docs/RESPONSIVE_STRATEGY.md` |
| D13 | DDL v0.2 aprobado para `robustez_v02_auth.db` (8 tablas) |
| D14 | Audit nivel MEDIO para MVP: `auth_events` activa, `user_actions` lista pero sin instrumentación |

---

## 5. Base de datos auth+audit (`robustez_v02_auth.db`)

**Fuente de verdad:** [`Migracion/DDL.md`](./Migracion/DDL.md) v0.2.

| # | Tabla | Rol |
|---|-------|-----|
| 1 | `permission_groups` | Grupos de permisos (Admin, Orinoquia, …) |
| 2 | `app_users` | Usuarios + cache `last_login_at` |
| 3 | `group_campo_permissions` | Campos por grupo |
| 4 | `group_section_permissions` | Secciones por grupo |
| 5 | `user_campo_permissions` | Extras de campo individuales |
| 6 | `user_section_permissions` | Extras de sección individuales |
| 7 | `user_actions` | Auditoría UI (lista, sin instrumentar en MVP) |
| 8 | `auth_events` | ★ NUEVA — Login/logout/expiración |

**Convenciones clave:**
- `auth_events` es la fuente canónica de sesión; `app_users.last_login_at` se actualiza en la misma transacción.
- `auth_events.domain` es `NOT NULL` sin DEFAULT — se lee de `core/config.py` (`AUTH_AD_DOMAIN`).
- `user_actions.details` tiene `CHECK (details IS NULL OR json_valid(details))`.
- Navegación tiene debounce 30s frontend + dedupe server-side + regla `prevSection !== nextSection`.

---

## 6. Sprint actual — S6 (inicio 2026-05-19)

**S5 W1 cerrada** ✅ — backend auth/permisos/audit operativo, frontend scaffold completo, BDs creadas, PostgreSQL schema `ops` + seeds listos.

**F2 cerrada** ✅ — PeriodoPanel bootstrap YTD fix + Drawer wiring Período + SCSS cleanup. 4 commits (faa2534 → 32be7e0).

**F3 cerrada** ✅ — WellConfigPanel rediseño completo: schema Zod + wellConfigStore draft/applied + OptionTile/BinarySelector genéricos + badge dinámico + Drawer wiring + SCSS cleanup. 6 commits (9a5aa6b → 0143b8f).

**Avance S6 al 2026-06-17 — commits:**

| Commit | Feature | Descripción |
|--------|---------|-------------|
| b784445 | FIX-stash | Rescate stash 67 archivos; `_tokens.scss` recupera `$rb-pop-shadow` |
| 1bd2734 | F20 | Perf PostgreSQL: CTE MATERIALIZED en 8 services — ticker 64s→2,4s (27×) |
| 1e98d40 | F21 | Inspector 4 waterfalls (EBITDA+Utilidades × USD/Bl\|KUSD) + vista móvil + pulido visual |

**Frontend operativo (pendiente commit acumulado + validación humana):**
- `ebitda_costos` — Inspector 4 waterfalls, vista móvil swipe/pills/flechas, transiciones liquid morph ⏳
- `ebitda_rank` — TendenciaEbitdaChart, WellConditionMap 4 trazas, inline expand desktop, CurvasWaffle (multi-select curvas), CondicionWaffle (single-select tiles 3 criterios: ebitda/util_oper/util_neta) ⏳
- `reports` — sidebar + ticker EBITDA real ⏳
- `regresiones` — RegresionesPage completa (PredVsActualChart + PlaneChart3D + ControlSidebar + calculadora OLS/multi) ⏳
- `seguimiento` — SeguimientoPage (KpiRibbon + ChartRail + 3 charts EbitdaChart/QoQwChart/VarsChart) ⏳
- `detalle_ingresos` — grid 2×2 combo charts + KPIs delta en cinta ✅ (validado en navegador)
- `detalle_costos` — StackedBarChart + tooltip custom + ComboBarPreview ✅ (validado parcialmente)
- `navigation` — AvatarPanel tarjeta + hover popover + tarjetas descripción hover ✅
- `mook_evaluacion` — tabla Plan/Real + 2 SVG charts + modal Ampliar ✅ (validado en navegador)

**🔴 Commit acumulado frontend PENDIENTE:** F13+F14+F15+F16+F21b+F21c + DEPLOY + F23 + F23b + fixes. Método: formatear ANTES de stagear, stagear por bloque lógico (NUNCA `git add -A`).

**✅ Despliegue en servidor** (2026-06-16): App operativa en `http://10.100.26.139:6023`. Puertos 6023/6024 unificados dev+servidor. Ver §11.1.

**Bloqueado activo:** 🔴 `poblar_postgres.py` — `wells_atributes.csv` tiene UWI duplicado `CAST0059` (línea 82). Decisión pendiente: deduplicar en script vs corregir CSV fuente.

---

## 7. Reglas operativas para Claude Code

1. **Cada commit referencia su tarea por ID.** Formato: `feat(W1.4): crear robustez_v02_auth.db con DDL v0.2`.
2. **Nunca cambiar decisiones bloqueadas (D1–D14) sin confirmación explícita.**
3. **Si una tarea se bloquea:** marcar `🔴 BLOCKED` y pasar a la siguiente. No quedarse atascado >1h.
4. **Cambios de scope** → `Migracion/PLAN_S5_W1.md` §"Cambios al plan".
5. **Decisiones técnicas no triviales** → ADR ligero en `docs/decisions/`.

---

## 8. Estado actual (2026-06-17 — sesión activa)

### Funcionalidades incorporadas — Frontend ✅

| Capa | Componentes operativos |
|---|---|
| **Auth UI** | LoginPage con splash + BetaBanner + DashboardPreview (Brent SVG histórico + ticker 4 KPIs). Auth hooks/store/guards + ProtectedRoute (lazy) + SessionExpiryBanner. Favicon `/public/favicon.png` (Gota.png) |
| **Layout** | Header (Waffle + AvatarPanel tarjeta + Breadcrumb) + Footer + DrawerStrip vertical (3 tabs) + Drawer 340px (lazy, fix mobile `top:var(--header-h)`) + KpiTicker animado. LayoutMain lazy desde `router.tsx`. ResolutionGuard **eliminado** (soporte mobile de facto). **AvatarPanel** rediseñado estilo tarjeta: avatar 48px + nombre completo + badge "ADMIN" (pill verde `#004236`) + email truncado + grid 3 cols de accesos rápidos (Admin, Configuración, Ayuda) con iconos 24px coloreados + borde sutil `rgb(0 0 0 / 6%)` + "Cerrar sesión" centrado rojo. Props: `username`, `fullName`, `email`, `isAdmin` desde `useAuthStore`. Header pasa `fullName` e `isAdmin` al panel. |
| **Home** | HomePage con Carousel + 3 paneles Drawer accesibles |
| **Primitivos UI** | Button, Input, Card, Badge, Spinner, Tooltip, Modal, Toast, UnitToggle (9 con tests). UnitToggle: segmented control genérico `T extends string`, role radiogroup |
| **Filtro Jerarquía (F1)** | `HierarchyPills` acordeón 6 niveles (VICEPRESIDENCIA / GERENCIA / ACTIVO / CAMPO / CAMPO_CONTRATO / POZO) con búsqueda interna >8 opciones + navegación teclado + auto-cleanup cascada + draft/applied + paleta Ecopetrol |
| **Filtro Período (F2)** | `PeriodoControls` con ModeSegmented (Rango / Mes único) + YearMonthSelect Desde/Hasta + MiniCalendar 6x2 (preview en range, interactivo en single) + PeriodoSummary + RangeWarningBanner (gaps/invalid) + draft/applied + `_isInitialized` + validación cross-year contra `ops.periods` vía `useQueries` |
| **Filtro Well Config (F3)** | `WellConfigControls` con 4 tiles icon-leading binarios (TipoPozo / Producto / EstadoPozo / Producción) + badge dinámico + subtítulo live + draft/applied + tipos genéricos `<T>` sin casts. Sin enlace a BD por ahora |
| **Applied Filters Panel (F4.1–F4.6)** | `AppliedFiltersPanel` (desktop sidebar) + `MobileAppliedFiltersSheet` (bottom sheet <1024px) montados en `EbitdaCostosPage`. Hooks `useAppliedFilters` + `useWellConfigAccents`. Helpers `formatRelativeES` + `useNow`. Stores con campo `appliedAt`. |
| **EBITDA Costos — Inspector 4 Waterfalls (F5.0–F21)** | `EbitdaInspectorCard`: layout rail de previews (izq) + chart + sidebar (der) desktop / 1col mobile. **4 gráficos waterfall**: EBITDA y Utilidades × (USD/Bl \| KUSD), seleccionables desde `InspectorRail` (4 thumbnails SVG vivos vía `CHART_PANELS` — fuente única en `chartPanels.tsx`). Estado en `inspectorUiStore` (Zustand: `activeUnit` `'USD/BI'\|'KUSD'`, `activeChart` `'ebitda'\|'utilidades'`, `expanded`). `WaterfallChart` custom (`type:'bar'` con bases calculadas — soporta totales intermedios: total lima `#CCD32A`, delta navy `#13355A`): **hover tooltip card** arriba-derecha (dot color + serie + valor, mismo formato que data labels, mismo ciclo de vida que la línea punteada vertical, early-exit por barra con `lastHoverIdx`); **`wrapLabel`** multilínea (≤12 chars/renglón, `<br>` Plotly) en ticks X desktop; **ResizeObserver → `Plots.resize`** (fix Ampliar/Reducir — Plotly solo escucha resize de ventana); data labels 10px. `InspectorHeader` sin dots de unidad (obsoletos con 4 gráficos; oculto en móvil). `InspectorSidebar` con **`pctBase` dinámico**: % "de los ingresos" (EBITDA) o "de la utilidad neta" (Utilidades) + reset H3 de `selectedKey` al cambiar de gráfico. Llena 100% altura disponible. Ruta `/ebitda-costos` activa. Hooks: `useEbitdaKpis` + `useKpiQoQw` + `useEbitdaWaterfallData` + `useUtilidadesWaterfallData`. |
| **Waterfall Utilidades (F21)** | 2 waterfalls nuevos (KUSD + USD/Bl) con puente contable **EBITDA → Amortización → Depreciación → Impuestos Costos y Gastos → Impairment → UTILIDAD OPERATIVA → Impuesto de renta → Financieros netos → Diferencia en cambio → UTILIDAD NETA** (11 barras, totales SIEMPRE de columnas BD, signos reales del dato — Dif. en cambio puede sumar). Misma lógica de filtros/selección de columnas/formato que el waterfall EBITDA. `utilidadesWaterfallService` + `useUtilidadesWaterfallData` + campo `type` en el mapper. Smoke verificado: EBITDA 1.797.083,27 / UO 1.333.984,13 / UN 392.669,69 KUSD; 33,63/24,96/7,35 USD/Bl. Residual contable conocido del puente (−36,6 MKUSD tramo UO / −55,3 tramo UN — dato fuente, reportar al dueño del Excel). ⏳ PENDIENTE validación humana. |
| **Waterfall — Vista móvil (F21-mobile)** | En ≤1023px el Inspector se transforma: rail y header ocultos (Ampliar era no-op en móvil); navegación entre los 4 gráficos por **swipe** (touch, umbral 48px, cíclico), **flechas** `ChevronLeft/Right` circulares 30px (hit-area 44px vía `::before`) y **`ChartPillsMobile`** (dots role=tablist + pills scrollables bajo el gráfico, activa ámbar, opera sobre el store). Ticks X **abreviados** (`abbreviateLabel`: stopwords de/en/y; "Impuesto de renta"→"I.Ren"); data labels ocultos (`textposition:'none'` — los valores viven en el hover/tap y la tarjeta); fuentes ejes 8px, título Y 9px. Tarjeta lateral compacta (`max-height:110px`, scroll interno profundo, tipografías reducidas); chart protagonista `min-height:400px`; padding página `12px 12px 80px` (reserva FilterBar colapsada). `prefers-reduced-motion` respetado. ⏳ PENDIENTE validación humana. |
| **EBITDA Inspector Transiciones (F13)** | `EbitdaInspectorCard` con animación `liquid morph` al alternar gráfico/unidad: clase `.chartCanvas` envuelve `<WaterfallChart>` DENTRO del `<Suspense>` con `` key={`${activeChart}-${activeUnit}`} `` (aislado del lazy chunk, sin flash). Keyframe `@chart-canvas-in` combina `clip-path: inset(... round 80px)` + `scale(0.92→1)` + `opacity(0→1)`, 500ms `cubic-bezier(0.4, 0, 0.2, 1)` (curva del proyecto). `InspectorThumbnail` con fixes Emil: `transition` con 4 props específicas (background/border-color/box-shadow/transform), `:active scale(0.97)` feedback de press, transición opacity en `.preview`, transición background+color en `.icon`. Sin `@media (prefers-reduced-motion)` local (regla global de `styles/index.scss` cubre). |
| **EBITDA Rank — Curva de Rentabilidad (F8)** | `EbitdaRankPage`: layout 2-panel (gráfico izq + mapa der) con `panelCard` + leyenda + segmented toggle + footer meta. **Expand inline desktop (≥1024px)**: botón "Ampliar"/"Reducir" (Maximize2/Minimize2) cambia `gridTemplateColumns` con `transition cubic-bezier(0.7,0,0.3,1) 0.4s`. Panel ampliado ocupa el grid (`1fr 44px` o `44px 1fr`); el otro colapsa a `CollapsedTab` vertical (44px ancho, icono naranja + label rotado `writing-mode:vertical-rl` + chevron). En mobile (<1024px) el comportamiento conserva el modal (`ChartModal`). **Fix H1**: `gridCols='1fr'` cuando `isMobile===true` para no sobreescribir `@media` con inline style. **Fix H2**: `useEffect(()=>{ if(isMobile) setExpanded(null) }, [isMobile])` resetea expanded al pasar a mobile. `aria-pressed` en botón toggle + `prefers-reduced-motion` desactiva la transición del grid. Notify Plotly de resize tras 450ms (post-transición). `TendenciaEbitdaChart` (Plotly): 3 series (EBITDA/Bl línea oscura + Aceite-Cum naranja + EBITDA-Cum verde) en 2 ejes Y, zonas de fondo verde/amarillo/rojo con interpolación KPI + zero-cross, línea KPI dashed, ejes monospace, sin markers. `RangeSlider` dual-thumb con paleta Ecopetrol `#004236`. `KpiStrip` (4 KPIs horizontales). `CardHeader` reutilizable. `WellConditionMap` con **4 traces por categoría**: ★ rentable (#2E8B47), ◆ marginal (#F4D124), ✚ no_rentable (#C5311E, cross-thin-open), ● otro (#6B7A8A) — agrupación por `categoria` con `CATEGORY_CONFIG` + `CATEGORY_ORDER`, paridad visual con `PredVsActualChart.tsx`. Chips de filtrado por categoría (`catChipOn/Off_<cls>`, 4 estados visuales, role switch + `aria-checked`). `ChartModal` (zoom modal mobile). Chart ocupa 100% altura disponible via `position:absolute;inset:0` + flex chain propagation + `:global()` overrides Plotly. `ebitdaRankMapper` + `ebitdaRankService` + `useEbitdaRankData`. **F23 — CurvasWaffle (multi-select curvas):** popover waffle con `WaffleTile` genérico (Eye/EyeOff toggle, 7 tiles en 2 grupos, botones "Todas"/"Ninguna", contador `N/7`), `curvesDef.ts` (7 curvas con iconos/colores), `useVisibleCurves` hook. **F23b — CondicionWaffle (single-select tiles criterio):** 3 tiles (EBITDA/Bl `#0A1F33` Coins, U.Oper/Bl `#8B5CF6` Gauge, U.Neta/Bl `#0EA5E9` Wallet), CSS var `--cond-color`, `aria-pressed`, Check ✓, click selecciona+cierra. `EbitdaRankPage` integra `criterio` state → `useWellConditionPoints(criterio)` + chips filtrados por criterio (ebitda: 4 categorías, util_oper/util_neta: 2). Backend: `classify_well()` parametrizado con `criterio`, `resolve_columns()` 12 variantes. Ruta `/ebitda-rank` activa. ⏳ PENDIENTE validación humana (V2-V10, F23b V5). |
| **Filtro UWI con lógica EBITDA (F6.1)** | `useHierarchyFilters.ts` envía `from/to_year/month + estado_pozo + produccion` al query `uwi`. El backend filtra pozos con EBITDA válido → 153 pozos (paridad V01). Formato delta KPIs: locale `es-CO`. |
| **KPI Ticker — EBITDA + Delta (F14)** | `KpiTicker` con 2 tipos de items: **`kpi`** (layout clásico: sparkline + val + delta) y **`delta`** (layout 3 filas: label+sparkline → valor delta grande → % + footer INICIO\|FIN con valores período). `KpiTickerEntry` extendido con `startVal`, `endVal`. `TickerItem.tsx` renderiza condicionalmente por `entry.type`. `KpiTickerOverride` extendido con `delta`, `neg`, `startVal`, `endVal`, `series`. `LayoutMain.tsx` consume `useKpisDelta()` de `detalle_ingresos` y pasa overrides reales a los 4 items delta. Ruta `/detalle-ingresos` muestra 8 items (4 KPI + 4 delta); resto de rutas solo 4 KPI. Formato locale español `es-CO`. ✅ Validado en navegador. |
| **Reports / EBITDA Seguimiento (F9)** | `ReportsPage`: layout sidebar (`AppliedFiltersPanel` desktop + `MobileAppliedFiltersSheet` <1024px) + `SoonPage` placeholder como contenido principal. KPI ticker con valores EBITDA reales vía `useEbitdaKpis` + `tickerOverrideStore`. Hook/service/mapper propios (aislamiento cross-feature). Ruta `/reports` activa con drawer + ticker. ⏳ PENDIENTE validación humana. |
| **Regresiones (F10)** | `RegresionesPage` completa: `ControlSidebar` (FieldSelect + InputsForm + WaterRangeSlider) + `ViewRail` (rail de vistas) + `FeaturedChart` + `EquationCard` + `CategoryChips`. Charts: `PredVsActualChart` (Plotly scatter 4 traces por categoría condición pozo) + `PlaneChart3D` (Plotly surface 3D). Utils: `calcOLS` + `calcMulti` + `calcPredict`. Store: `predictionUiStore`. Schema: `regressionSchema`. Backend `regression/services.py` integra `classify_well()`. Ruta `/regresiones` activa. ⏳ PENDIENTE validación humana. |
| **Detalle Ingresos — Grid 4 Combo Charts + KPIs Delta (F11+F14)** | `DetalleIngresosPage` (`/detalle-ingresos`): layout sidebar (`AppliedFiltersPanel` desktop + `MobileAppliedFiltersSheet` mobile) + `ChartsGrid` 2×2 con 4 `ChartCard` (Ingreso KUSD vs Brent/DifOil/TRM/Producción). `ComboChart` reutilizable (Plotly bar+line, `createPlotlyComponent` + `useResizeHandler`). `ExpandToggleButton` zoom + tecla Esc para colapsar. Zustand `chartsStore` con `expandedId`. `useIngresosCombo` consume `GET /api/v1/detalle-ingresos/ingresos-combo`. `chart.config.ts` define labels/colores/unidades. Tokens `$ec-*` añadidos a `_tokens.scss`. **KPIs Delta en cinta:** 4 items delta (Δ BRENT, Δ DIF OIL, Δ PRODUCCIÓN, Δ TRM) integrados en el `KpiTicker` del `LayoutMain` exclusivamente para esta ruta. Datos reales del backend vía `useKpisDelta` → `GET /api/v1/kpis-delta/`. Layout delta: INICIO \| Δ valor + % \| FIN con sparkline. Hook/service/mapper/types propios en `detalle_ingresos/`. ✅ Validado en navegador. |
| **Detalle Costos — Costos y Gastos (F15)** | `DetalleCostosPage` (`/detalle-costos`): layout sidebar (`AppliedFiltersPanel` desktop + `MobileAppliedFiltersSheet` mobile) + `CostosGastosCard` (inspector layout: rail thumbnails izq + chart area der + botón Ampliar/Reducir). `StackedBarChart` (Plotly stacked bar, `createPlotlyComponent` + `useResizeHandler`). `StackedBarPreview` (SVG miniatura memo). **Custom tooltip HTML** fijo centrado superior del chart (no Plotly nativo — `onMouseMove` calcula mes por posición X del mouse, `hovermode: false`). Formato `$3.604,3` (es-CO). Zustand no involucrado en hover (R2 ✅). `useCostosFijosKpis` + `useCostosGastosMensual` hooks (TanStack Query). `costosFijosKpiService` (2 endpoints: ticker + gastos mensual). `costosFijosKpiMapper` (ensureTwoPoints + sort avg desc). Types `CostosGastosSerie` + `CostosGastosMensualData`. **KPI Ticker Costos:** 11 keys en `TICKER_KEYS_BY_ROUTE['/detalle-costos']` (costos-fijos, costos-fijos-bl, 7 deltas). `LayoutMain.tsx` consume `useCostosFijosKpis` condicional + pasa overrides. `kpiTickerData.ts` con 11 mocks costos. Ruta `/detalle-costos` activa. **Tooltip reposicionado (2026-06-11):** `top:8px; right:16px` — fijo arriba-derecha dentro del card (antes flotaba fuera con `top:-100px`). ✅ Validado parcialmente. |
| **Navegación — Hover Popover (F12+F16+F16b)** | `AppMenuPopover` con comportamiento hover: sub-tiles aparecen on `onMouseEnter` (sin click). Click en app → navega siempre. `handleAppHover` actualiza `activeAppId` + `activeSubId` (primer sub por defecto). Tecla Esc cierra popover. Fix ESLint `no-unnecessary-type-assertion` (eliminado `activeApp!.subs!`). **F16 (2026-06-10):** título cambiado a "Robustez · Panel de Navegación". Texto "APLICACIONES" (eyebrow) eliminado. Opción "Admin" removida de `nav.config.ts` (accesible solo desde AvatarPanel). 6 items: Inicio, Utilidad Neta, Predicción, EBITDA Rank, EBITDA Seg. (con subs: Ingresos, Costos, Dilución), Mook - Evaluacion (accent warning). **F16b (2026-06-15):** `AppEntry.description?: string` opcional — zona derecha del popover alterna `SubViewGrid` / tarjeta `.descCard` según `hasSubs`. Textos para Utilidad Neta, Predicción, EBITDA Rank, Mook. Popover ampliado 460→560px, columna derecha 130→210px. |
| **Mook - Evaluación mock (F22)** | `MookEvaluacionPage` (`/mook-evaluacion`): layout sidebar (`AppliedFiltersPanel` desktop + `MobileAppliedFiltersSheet` mobile) + `BeneficiosTable` (header 2 niveles Plan azul/Real lima, 5 filas CAS46-CAS50, badges por estado, chips contexto) + grid 2 charts SVG. **`RegresionChart`**: subcomponente `RegresionSvg` con refs propios por instancia; marcadores X₁/X₂ calculados con `getPointAtLength`/`getTotalLength` (never hardcoded). **`DeltaEbitdaChart`**: subcomponente `DeltaEbitdaSvg({ patternId })` para evitar `id="mook-hatch"` duplicado en card+modal. **`MockChartModal`**: `<dialog>` nativo, `showModal()`. Fix StrictMode crítico: **NO** `dialog.close()` en cleanup del `useEffect` — encola evento `close` asíncrono que bajo doble-mount dispara `onClose()` → modal se cierra solo al abrir; solución: solo `removeEventListener`. Paleta local `_palette.scss` con `$mk-*`. `formatMiles` con separador `' '` (U+2009). Datos 100% mock. Ruta `/mook-evaluacion` activa con drawer (sin ticker). |
| **Drawer fix mobile** | `Drawer.module.scss` `@media ≤1023px`: `top: 0 → top: var(--header-h, 61px)`. Bug: el Header de la app (z-index:100) tapaba el header del drawer (z-index:56), dejando el botón X invisible → el panel de filtros no tenía salida en móvil. |
| **Seguimiento (F9-seg)** | `SeguimientoPage` (`/seguimiento`): `PageHeader` + `KpiRibbon` (mock KPIs con `KpiRibbonCard` + `KpiSparkline`) + `ChartRail` (rail de thumbnails `ChartThumbnail`) + `FeaturedChart` (chart principal con `ExpandToggle`). 3 charts SVG: `EbitdaChart` + `QoQwChart` + `VarsChart`. Store: `seguimientoUiStore`. Data mock: `mockKpis` + `mockSeries`. Utils: `format` (fmtK, fmtPct) + `btnToPanel`. Types: `seguimiento.ts` + `series.ts`. Ruta `/seguimiento` activa. ⏳ PENDIENTE datos reales del backend. |
| **Despliegue servidor (DEPLOY)** | App desplegada en `10.100.26.139:6023` (front) + `:6024` (back). Puertos unificados dev+servidor. `vite.config.ts` lee `VITE_PORT`/`VITE_BACKEND_PORT` de env vars. `config.py` CORS dual `localhost+servidor`. Perfiles `.env.dev` / `.env.server`. Script `make_deploy_zip.ps1` (zip sin .git/node_modules/.venv ~791 MB). Cookie `Secure=False` (sin HTTPS). Procedimiento: ver §11.1. ✅ Operativo. |

### Funcionalidades incorporadas — Backend ✅

| Módulo | Componentes operativos |
|---|---|
| **Auth** | LDAP real `red.ecopetrol.com.co` + cookie firmada `itsdangerous` + `auth_events` instrumentada. **Fix LDAP definitivo (2026-06-11):** resolver DNS fresco por intento de login (`dns.resolver.Resolver(configure=True)`) — dnspython cacheaba la config DNS del sistema en el primer uso, por lo que el login fallaba si el backend arrancaba antes que la VPN. Ya no importa el orden VPN/backend. |
| **Permissions** | RBAC con 4 tablas (`group_campo_permissions`, `group_section_permissions`, `user_campo_permissions`, `user_section_permissions`) + `PermissionService` |
| **Audit** | `auth_events` activa; `user_actions` lista sin instrumentación frontend (DT-7) |
| **Filters API** | `GET /filters/hierarchy/{level}` bidireccional con RBAC + `GET /filters/periods/years` + `GET /filters/periods/months/{year}`. Nivel `uwi` con EBITDA business logic (6 params extra: from/to year/month, estado_pozo, produccion) → 153 pozos paridad V01. |
| **KPIs Financieros** | `GET /api/v1/kpis-financieros/ebitda-summary` — retorna EBITDA KUSD + EBITDA/Bl (SUM÷SUM) con delta/pct/series mensuales. Columnas seleccionadas por (estado_pozo × produccion). `_sanitize_col` NULLIF PostgreSQL. Formato locale español. Incluye `waterfall_service` + `waterfall_schemas` (campo `type`) para datos de cascada. **F21:** `waterfall_utilidades_service.py` + endpoint `GET /api/v1/kpis-financieros/kpis/utilidades-waterfall` — puente EBITDA→UTILIDAD NETA (amortiz/deprec/imp_cosgas/impair se niegan; imp_renta/finan_netos/dif_en_cambio ya vienen como efecto con signo → tal cual; totales SIEMPRE de columnas BD). Mismo patrón CTE F20. |
| **Perf PostgreSQL (F20)** | Patrón anti-nested-loop en **8 services** que consultaban hecho×hecho: el planner estimaba `rows=1` en joins por PK de 6 columnas (selectividades correlacionadas multiplicadas) → nested loop re-ejecutaba la subquery `DISTINCT ON (uwi)` 26.304 veces (88s). Patrones aplicados: (A) `EXISTS (SELECT 1 FROM ops.wells_attributes w WHERE w.uwi = fr.uwi)` cuando NO hay filtros de jerarquía (kpis_operacionales ×4 — 360×); (B) **CTE prefiltro `MATERIALIZED`** con hecho base + wa + `where_sql` íntegro adentro, hechos secundarios fuera por PK (kpis_financieros, utilidades, costos_usdbl, waterfall_service, detalle_ingresos, ebitda_rank ×2, regression — 270×). EXISTS con jerarquía PROHIBIDO (9.275/13.450 uwis con jerarquía inconsistente). Resultado verificado: ticker 64s→2,4s en frío (27×), QO/QW idénticos a la UI pre-F20. |
| **KPIs Costos** | `GET /api/v1/kpis-costos/` — costos operacionales desglosados. 3 endpoints: (1) `costos-fijos-ticker` — 2 KPIs (Costos Fijos KUSD + USD/Bl) + 7 deltas (Δ costos, Δ costos/bl, Δ energía, Δ tratamiento, Δ M.subsuelo, Δ gasto, Δ costos levant). `CostosFijosTickerService` con `KUSD_COLUMN_MAP` × `BLS_COLUMN_MAP` por (produccion, estado). (2) `costos-gastos-mensual` — stacked bar data: `labels[]` (meses) + `series[]` (key, label, color, values). `CostosGastosMensualService` con 6 componentes (costos_fijos, gastos, tratamiento, m_subsuelo, energia + ingreso-costos calculado). JOIN operating_costs × flow_rates × wells_attributes (DISTINCT ON uwi). RBAC vía `_get_allowed_campos()`. (3) Endpoint base heredado. `services.py` (shared utils: `sanitize_col`, `build_where_and_params`, `KUSD_COLUMN_MAP`, `BLS_COLUMN_MAP`, `normalize_estado/produccion`, `safe_div`). Schemas: `schemas_costos_fijos.py` + `schemas_costos_gastos.py`. |
| **KPIs Producción** | `GET /api/v1/kpis-produccion/qo-qw` — retorna QO+QW+QG por mes. Filtros jerárquicos + well_status. 🔴 Valores inflados +46% por duplicados en `ops.wells_attributes` (causa raíz identificada, fix pendiente). |
| **EBITDA Rank** | `GET /api/v1/ebitda-rank/` — ranking de pozos por EBITDA/Bl descendente. `WellConditionService` integra `classify_well()` parametrizado con `criterio` (ebitda/util_oper/util_neta) + `fin_alias="fr"` + LEFT JOIN `operating_costs`. `resolve_columns()` con 12 variantes (3 criterios × 4 combos estado×produccion). Retorna `wells[]` + `well_count` + `kpi_ebitda_bl` + `summary` (rentable/marginal/no_rentable counts reales). Query param `criterio` controla umbrales de clasificación. API + services + schemas. |
| **Regression** | `GET /api/v1/regression/` — regresiones de producción. Integra `classify_well()` con `fin_alias="fin"` + LEFT JOIN `operating_costs`. Cada pozo clasificado por categoría de condición. API + services + schemas. |
| **Detalle Ingresos** | `GET /api/v1/detalle-ingresos/ingresos-combo` — series mensuales con 5 arrays: `ingreso_values` (KUSD) + `brent_values` (USD/bbl) + `difoil_values` (USD) + `trm_values` (COP/USD) + `prod_values` (BOPD). JOIN `financial_results × wells_attributes (DISTINCT ON uwi) × market_base_costs × flow_rates`. `INGRESO_COLUMN_MAP` + `PROD_COLUMN_MAP` por `(produccion, estado_pozo)`. `_sanitize_col()` NULLIF Infinity/NaN. RBAC vía `_get_allowed_campos()`. |
| **KPIs Delta (F14)** | `GET /api/v1/kpis-delta/` — 4 items: Δ BRENT (USD/bbl), Δ DIF OIL (USD/bbl), Δ PRODUCCIÓN (BOPD), Δ TRM (COP/USD). Cada item retorna `id`, `title`, `start`, `end`, `delta`, `pct`, `spark[]`, `unit`, `invert_tone`. BRENT y TRM son globales (sin filtro jerarquía). DIF OIL y PRODUCCIÓN filtran por RBAC + jerarquía. `PROD_COLUMN_MAP` por (produccion × estado_pozo). `_sanitize_col()` NULLIF Infinity/NaN. `DISTINCT ON (uwi)` para wells_attributes. Pydantic schemas `KpiDeltaItem` + `KpiDeltaResponse`. Query params con aliases (`vicePresidency`, `monthStart`, `monthEnd`, `estadoPozo`). |
| **Shared — Well Condition** | `src/shared/well_condition.py` — módulo compartido: `classify_well()` (rentable/marginal/no_rentable/otro), `resolve_columns()` (4 variantes estado×produccion, `fin_alias` parametrizable), `build_condition_select_columns()` (SQL sanitizado Infinity/NaN). Consumido por `ebitda_rank` y `regression`. 21 tests unitarios. |
| **Middleware stack** | correlation_id + auth + request_logger (structlog JSON UTC) |
| **Core** | config + logger + secrets + exceptions |

### Datos

| BD | Tipo | Estado |
|---|---|---|
| `robustez_v02_auth.db` | SQLite | 8 tablas DDL v0.2 + 1745 filas migradas de V01 |
| `bitacora.db` | SQLite | 5 tablas + 45 entradas (cambios diarios desde 4-may; semana 6 activa 2026-06-17) |
| `robustez_v02.db` | SQLite operacional | Esquema estrella (~127 MB), datos sin cargar |
| PostgreSQL `ops.*` | PostgreSQL 18.4 — `robustez:***@10.100.26.139:5432` | 6 tablas en schema `ops`. 13,450 filas `wells_attributes`, 216,641 `financial_results`. 🔴 `wells_attributes` tiene UWIs duplicados (2-4 copias) — causa raíz de KPI inflation |
| `data/seeds/*.csv` | CSVs | ~215 MB |

### Tests

- **Backend:** 127 passed + 3 skipped. Incluye `test_well_condition.py` (21 tests: classify_well + resolve_columns + build_condition_select_columns) + `test_filters_service.py` (15 tests F6.1). Coverage ~60% (DT-9, threshold 75%).
- **Frontend:** tests por feature (`HierarchyPills`, `PeriodoControls`, `WellConfigControls`, primitivos). Vitest jsdom + RTL + jest-dom + mock global de `ResizeObserver`. Coverage threshold global 80%.

### Decisiones técnicas adoptadas (paneles de filtro)

Stack único para los 3 paneles (Jerarquía, Período, Well Config):
- **Sass módulos** + **Lucide React** + **Zustand 5** + **Zod 3.24** + patrón **draft/applied**.
- **Paleta Ecopetrol estricta**: verde `#004236` + amarillo `#F7DB17` + variantes (`#059669`, `#d97706`, `#fff8dc`).
- **NO** Bootstrap, **NO** date-fns, **NO** react-hook-form en paneles.

### Pendiente inmediato

- **🔴 CRÍTICO**: Deduplicar `ops.wells_attributes` en PostgreSQL — causa raíz de KPI QO/QW inflados +46%. Con DISTINCT ON: QO=37,982 vs V01=38,120 (-0.4%). Dos opciones: (a) DELETE duplicados en BD, (b) DISTINCT ON en query. Decisión del usuario pendiente.
- **⏳ Validación humana**: `EbitdaRankPage` inline expand desktop (F8-inline-expand) — implementado 2026-05-27, pendiente confirmación V2-V10: carga grid 1.55fr/1fr (V2), Ampliar curva → 1fr 44px + CollapsedTab derecha (V3), Reducir restaura (V4), click CollapsedTab restaura (V5), Ampliar mapa → 44px 1fr + CollapsedTab izquierda (V6), resize a mobile resetea expanded (V7), Ampliar en mobile abre modal (V8), `prefers-reduced-motion` desactiva transición (V9), Plotly resize tras 450ms (V10).
- **⏳ Validación humana**: `WellConditionMap` (ebitda_rank) — 4 traces por categoría implementados 2026-05-27, pendiente confirmación usuario en navegador (V3-V5).
- **⏳ Validación humana**: `TendenciaEbitdaChart` (ebitda_rank) — ajustes visuales aplicados 2026-05-26, pendiente confirmación usuario en navegador.
- **⏳ Validación humana**: `PredVsActualChart` (regresiones) — categorías de condición implementadas, validado parcialmente por usuario.
- **⏳ Validación humana**: KPI ticker EBITDA KUSD + EBITDA/Bl (valores en pantalla, formato 1.234,56).
- **⏳ Validación humana**: F20 — paridad del ticker y KPIs tras la optimización de queries (valores verificados por script, falta confirmación en UI).
- **⏳ Validación humana**: F21 — 4 previews del rail, waterfalls de Utilidades (signos, % sobre UN, caso UN≤0), hover tooltip card de los waterfalls.
- **⏳ Validación humana**: vista móvil del waterfall — swipe, flechas, pills, labels abreviados, proporciones tarjeta 110px / chart 400px.
- **🔴 Commit acumulado del frontend** (pendiente explícito del usuario): F13+F14+F15+F16+F21b+F21c + DEPLOY + F23 + F23b + fixes. Método: formatear ANTES de stagear, stage explícito por bloque lógico (NUNCA `git add -A`). ~80 archivos modificados pendientes.
- Reportar al dueño del Excel/CSV: residual contable del puente F21 (−36,6 MKUSD UO / −55,3 UN) + 7 PKs duplicadas detectadas.
- Decidir destino de `tests/unit/auth/` untracked (residuos S5 W1 con tests rotos — ver DT-8).
- Resolver OOM de coverage en suite completa (ver DT-9).
- Deuda de docs: D12/`RESPONSIVE_STRATEGY.md` desactualizada — ResolutionGuard eliminado; soporte móvil de facto.
- **Próximo:** `DetalleDilucionPage` (mismo patrón stacked bar), reporte Excel ebitda_rank, deduplicación `wells_attributes`, seguimiento con datos reales.

> Historial completo de tareas: `git log` + `bitacora.db`.

---

## 9. Convenciones de código

### Naming entre back y front (Interceptores 1 y 2)

| Lugar | Convención | Ejemplo |
|-------|-----------|---------|
| Python (back) | `snake_case` | `ebitda_kusd` |
| TypeScript (front) | `camelCase` | `ebitdaKusd` |
| Contrato JSON heredado V01 | español literal con tildes | `"EBITDA (KUSD)"` |

- **Interceptor 1** — `backend/src/features/<f>/schemas.py`: Pydantic `alias` traduce `snake_case ↔ "EBITDA (KUSD)"`.
- **Interceptor 2** — `frontend/src/features/<f>/mappers/`: funciones puras `to<Entity>UI(api)` traducen `"EBITDA (KUSD)" ↔ camelCase`.

### Patrón Repository–Service–Route (backend)

- `repositories.py` — único punto autorizado para SQL
- `services.py` — lógica de negocio
- `api.py` — endpoints FastAPI (Router)
- `models.py` — entidades de dominio
- `schemas.py` — Pydantic con alias (Interceptor 1)

### Patrón feature frontend

- `pages/` — componentes de pantalla completa
- `components/` — UI específica del dominio
- `hooks/` — TanStack Query hooks (consumen mappers)
- `mappers/` — Interceptor 2
- `services/` — cliente HTTP tipado (openapi-fetch)

---

## 10. Estrategia responsive

> Detalle completo: [`robustez_v02_frontend/docs/RESPONSIVE_STRATEGY.md`](./robustez_v02_frontend/docs/RESPONSIVE_STRATEGY.md)

| Aspecto | Decisión |
|---------|----------|
| Target | Desktop/laptop + mobile básico (M1 bottom sheet) |
| Resolución crítica desktop | 1245×642 @ 100% zoom |
| Rango soportado | **360px → 1920px** (D12 actualizada en F6) |
| Breakpoint mobile | <1024px → layout M1 bottom sheet |
| Viewport <360px | No soportado (sin bloqueo activo) |
| Técnica primaria desktop | `clamp()` en tipografía y espaciados |
| Layout vars | CSS custom properties en `:root` (7 vars) |
| Adaptación a sidebar | Container queries + media queries |
| Validación obligatoria | Chrome DevTools 1245×642 + 1920×1080 + Samsung S8+ 360×740 |

### Identidad visual Ecopetrol
- Verde primario: `#004236` | Verde brillante: `#6CD300` | Amarillo: `#F7DB17` | Naranja: `#FF5F00`
- Neutros: `#f8f9fa / #ffffff / #1a1a2e / #e5e7eb / #111827 / #6b7280 / #9ca3af`
- Semánticos: `#059669 / #dc2626 / #d97706` con fondos pastel

---

## 11. Comandos clave

```bash
# Setup (raíz)
pnpm setup            # pnpm install + uv sync --extra dev + init:bitacora

# Orquestadores raíz
pnpm dev              # back :6024 + front :6023 con concurrently
pnpm lint             # back + front en paralelo
pnpm format           # autofix back + front
pnpm gen:types        # regenera tipos desde OpenAPI

# Backend (puerto 6024)
cd robustez_v02_backend
alembic upgrade head
uv run uvicorn src.main:app --reload --port 6024
uv run pytest tests/

# Frontend (puerto 6023)
cd robustez_v02_frontend
pnpm dev
pnpm test
pnpm test:e2e
pnpm build
```

> **NUNCA** ejecutar `pre-commit install` — husky orquesta el hook desde `.husky/pre-commit`.

---

## 11.1 Despliegue en servidor (`10.100.26.139`)

### Puertos fijos

| Servicio | Puerto | Bind |
|----------|--------|------|
| Frontend (Vite dev server) | **6023** | `0.0.0.0` |
| Backend (uvicorn) | **6024** | `0.0.0.0` |

Los puertos son los mismos en dev local y en el servidor. La configuración se unificó en el plan `DEPLOY_puertos_servidor_2026-06-16`.

### Archivos que definen los puertos

| Archivo | Qué configura |
|---------|---------------|
| `vite.config.ts` | `VITE_PORT` (default 6023), proxy a `VITE_BACKEND_PORT` (default 6024) |
| `config.py` | `app_port` default 6024, `cors_origins` default dual (localhost + servidor) |
| `package.json` raíz | `dev:back` → `--port 6024` |
| `Start_Back.bat` | `--host 0.0.0.0 --port 6024` |
| `frontend/package.json` | `gen:types` → `localhost:6024` |

### Para cambiar puertos en el futuro

`vite.config.ts` lee de env vars `VITE_PORT` y `VITE_BACKEND_PORT`. El backend lee `APP_PORT` del `.env`. Para un cambio de puertos basta con editar `.env` (backend) y setear env vars (frontend), sin tocar código.

### Switch dev local ↔ servidor

Ambos entornos usan los mismos puertos y la misma BD PostgreSQL (`10.100.26.139:5432`). La diferencia es:
- **Ruta de despliegue** — dev: `C:\APLICACIONES\Robustez\Des_robustez_2.0\`, servidor: `E:\APLICACIONES\Robustez\deploy_robustez_v02_YYYYMMDD\`
- **`.env`** — el `.env` real no se versiona; hay perfiles de referencia:
  - `.env.dev` — perfil desarrollo local
  - `.env.server` — perfil servidor
  - `.env.example` — plantilla genérica

**Procedimiento de deploy:**
1. Generar zip sin `.git`/`node_modules`/`.venv` (script `make_deploy_zip.ps1` en `C:\APLICACIONES\Robustez\`)
2. Descomprimir en servidor
3. `pnpm install` (desde raíz o frontend)
4. `cd robustez_v02_backend && uv sync --extra dev`
5. `copy .env.server .env` (o copiar el `.env` real del entorno anterior)
6. Abrir firewall puertos 6023 y 6024 (si no están abiertos)
7. Ejecutar `Start_Back.bat` + `Start_Front.bat` (2 consolas)
8. Acceso: `http://10.100.26.139:6023`

### Prerequisitos del servidor

- **Node.js** 20+ (`node --version`)
- **pnpm** 10+ (`npm install -g pnpm`)
- **Python** 3.12+ con **uv** (`uv --version`)
- **PostgreSQL** 18.4 en `10.100.26.139:5432` con schema `ops` poblado

### ⚠️ Cookie de sesión y HTTPS

`APP_ENV=development` → `Secure=False` en la cookie de sesión. Si se cambia a `APP_ENV=production`, el login **falla** sin HTTPS porque el navegador rechaza cookies con `Secure=True` sobre HTTP. Mantener `development` hasta configurar certificado SSL.

### Cambios aplicados en el plan DEPLOY (2026-06-16)

| Archivo | Cambio |
|---------|--------|
| `package.json` raíz | `dev:back` puerto 8765→6024 |
| `vite.config.ts` | puerto 5173→6023, proxy 8765→6024, lectura de env vars |
| `config.py` | `app_port` 8000→6024, `cors_origins` dual localhost+servidor |
| `.env.example` | puertos actualizados, CORS dual |
| `Start_Back.bat` | `--host 0.0.0.0 --port 6024` |
| `Start_Front.bat` | título `:6023` |
| `frontend/package.json` | `gen:types` URL 8765→6024 |
| `test_config_db.py` | aserción CORS genérica (sin URL literal) |
| `tmp_check_v01.py` | eliminado (credenciales hardcodeadas) |

---

## 12. Documentos fuente

| Documento | Propósito |
|-----------|-----------|
| [`Migracion/Plan_Migracion_Robustez_V06.docx`](./Migracion/Plan_Migracion_Robustez_V06.docx) | Plan estratégico de migración v0.6 |
| [`Migracion/DDL.md`](./Migracion/DDL.md) v0.2 | DDL aprobado `robustez_v02_auth.db` (8 tablas) |
| [`Migracion/db_new.md`](./Migracion/db_new.md) | Resumen BD operacional v10 |
| [`Migracion/schema_v02_operacional_v10.sql`](./Migracion/schema_v02_operacional_v10.sql) | DDL operacional |
| [`Migracion/Gantt_S5_W1_para_ClaudeCode.md`](./Migracion/Gantt_S5_W1_para_ClaudeCode.md) | Vista operativa S5 W1 (referencia histórica) |
| [`docs/decisions/`](./docs/decisions/) | ADRs del proyecto |
| [`docs/claude/bd_operacional_v10.md`](./docs/claude/bd_operacional_v10.md) | Detalle BD operacional (6 tablas, columnas, PRAGMAs) |
| [`docs/claude/design_system.md`](./docs/claude/design_system.md) | Plotly + elevación + movimiento + espaciado |
| [`docs/claude/bitacora_guia.md`](./docs/claude/bitacora_guia.md) | Guía completa bitácora (cómo alimentar y consultar) |
| [`docs/claude/flujo_6_pasos.md`](./docs/claude/flujo_6_pasos.md) | Flujo profesional de ejecución detallado |

### Referencia V01 (`../Des_Robustez/`)
- `app/login/auth_service.py` — LDAP V01
- `app/login/permissions_service.py` — RBAC V01
- `Data/ROBUSTEZ.db` — BD V01 fuente del migrate script

---

## 13. Glosario rápido

| Término | Definición |
|---------|-----------|
| **V01** | WebApp Robustez en producción (Flask + Vanilla JS), `Des_Robustez/` |
| **V2.0** | Nueva versión FastAPI + React 19 + TS, este monorepo |
| **MV1** | Mínimo Verificable 1 — flujo E2E login→home ✅ |
| **Feature** | Carpeta autocontenida con todo lo necesario para una capacidad funcional |
| **Interceptor 1** | Pydantic alias en `schemas.py` — snake_case ↔ JSON heredado |
| **Interceptor 2** | Mapper en `mappers/` — JSON heredado ↔ camelCase TS |
| **Audit nivel MEDIO** | Solo `auth_events` instrumentada; `user_actions` lista pero sin dispatcher |
| **3 niveles design system** | Primitivos → Compuestos → Estructurales |

---

## 14. BD Operacional v10 — `robustez_v02.db`

Esquema estrella: 2 dimensiones (`wells_attributes`, `periods`) + 4 hechos (`market_base_costs`, `flow_rates`, `operating_costs`, `financial_results`). PK compuesta `(UWI, AÑO, MES, ESTADO POZO)`. 83 columnas, 8 FKs, 9 índices.

**Estado:** BD creada (152 KB), PRAGMAs aplicados. Datos sin cargar hasta S6.

**Decisión crítica:** `ESTADO POZO IN ('ACT', 'INACT', 'ABA')` — 3 valores, NO 4. `A+I` es variante de cálculo, no fila.

**Nombres de columna:** legacy V01 preservado literalmente (tildes, espacios, mayúsculas, slashes).

> 📘 Detalle completo: [`docs/claude/bd_operacional_v10.md`](./docs/claude/bd_operacional_v10.md)

---

## 15. Skill: Flujo Profesional de Ejecución (6 pasos)

Antes de cualquier tarea no trivial: **Mapeo → Auditoría → Diagnóstico → Propuesta → Aplicación → Verificación**. No saltear pasos. Propuesta completa antes de aplicar. Si un hallazgo afecta D1–D14, detener y escalar.

> 📘 Detalle: [`docs/claude/flujo_6_pasos.md`](./docs/claude/flujo_6_pasos.md)

---

## 16. Skill: Frontend Design Guidelines

**Tono:** industrial-corporativo refinado. **Espaciado base 4px** (4/8/12/16/24). **Elevación 3 niveles** (base / card / modal). **Transiciones ≤ 300ms** con `cubic-bezier(0.4, 0, 0.2, 1)`. Respetar `prefers-reduced-motion`.

**Identidad Ecopetrol:** verde primario `#004236`, verde brillante `#6CD300`, amarillo `#F7DB17`, naranja `#FF5F00`. Tipografía Inter con `tabular-nums` en KPIs.

**Reglas:** variables CSS para colores, `tabular-nums` en KPIs, código production-grade. Nunca cambiar fuente Inter ni paletas corporativas.

> 📘 Detalle: [`docs/claude/design_system.md`](./docs/claude/design_system.md)

---

## 17. Deuda técnica conocida

| # | Item | Resolver en | Detalle breve |
|---|------|-------------|---------------|
| ~~DT-1~~ | ~~`--allow-empty-input` en `lint:style`~~ | ✅ Resuelta | Hay múltiples `.scss` reales (HierarchyPills, PeriodoControls, WellConfigControls). Quitar flag en próxima limpieza. |
| ~~DT-2~~ | ~~`--no-error-on-unmatched-pattern` en `lint:eslint`~~ | ✅ Resuelta | `src/**` ya tiene `.ts/.tsx` reales. Quitar flag en próxima limpieza. |
| ~~DT-3~~ | ~~typescript-eslint syntactic~~ | ✅ Resuelta | `recommendedTypeChecked` activo en `eslint.config.js` (verificado en F3). |
| ~~DT-4~~ | ~~`vitest.config.ts` sin `jsdom`~~ | ✅ Resuelta | `environment: 'jsdom'` + `@vitejs/plugin-react` configurados. |
| ~~DT-5~~ | ~~`setupFiles` no referenciado~~ | ✅ Resuelta | `tests/setup/vitest.setup.ts` activo con `jest-dom/vitest` + mock `ResizeObserver`. |
| DT-6 | `make` no instalado en Windows | A criterio | Alternativa: `uv run ruff check . && uv run black --check . && uv run mypy src` |
| DT-7 | `user_actions` sin instrumentación frontend | S6+ | Activar dispatcher con debounce 30s + dedupe server-side al arrancar KPIs |
| **DT-8** | **`tests/unit/auth/` untracked con tests rotos** | **Inmediato (antes de S6)** | Residuos de S5 W1 nunca commiteados. `LoginPage.test.tsx` (placeholder obsoleto) y `useCurrentUser.test.tsx` (falta wrapper `<Router>`). Decisión pendiente: borrar (recomendado), arreglar y commitear, o mantener como DT. Excluidos en F3 con `--exclude 'tests/unit/auth/**'`. |
| **DT-9** | **OOM al ejecutar `pnpm test:coverage` sobre suite completa** | **S6 inicio** | `singleFork: true` (mitigación OOM de tests normales, fix 6-may) + instrumentación v8 de coverage acumulan jsdom en un solo heap → `JavaScript heap out of memory`. Probar `pool: 'threads'` o `isolate: true` en `vitest.config.ts`. Detectado en cierre F3. |
| ~~DT-10~~ | ~~Inconsistencia puerto backend dev: `dev:back` en `:8000` vs proxy Vite a `:8765`~~ | ✅ Resuelta en DEPLOY (2026-06-17) | `package.json` `dev:back` ahora `:6024`, `vite.config.ts` proxy a `:6024`. Puertos unificados dev+servidor. |
| **DT-11** | **`matchMedia` no mockeado en `tests/setup/vitest.setup.ts`** | **Antes de testear F6** | El hook `useIsMobile` usa `window.matchMedia` que no existe en jsdom. Componentes que lo consuman fallan en tests. Solución: añadir mock global en `vitest.setup.ts`. Detectado en auditoría F6. |
| **🔴 DT-13** | **`node-linker=hoisted` rompe shims de binarios del frontend (`tsc`, `vite`, `eslint`, `prettier`, `vitest`, `stylelint`)** | **🔴 PRIORIDAD MÁXIMA — antes de cualquier `pnpm install` futuro** | Con `node-linker=hoisted` en `.npmrc` (raíz + frontend), pnpm instala TODAS las devDependencies en `Des_robustez_2.0/node_modules/` pero genera shims en `robustez_v02_frontend/node_modules/.bin/` apuntando a `..\<pkg>` (ruta inexistente). Resultado: `pnpm build`, `pnpm lint`, `pnpm test` fallan con `Cannot find module '.../robustez_v02_frontend/node_modules/typescript/bin/tsc'`. **Síntoma diagnóstico:** `ls frontend/node_modules/` muestra solo 1-2 paquetes. **`pnpm dev` SÍ funciona** porque Vite carga desde root vía resolución Node.js — esto enmascara el problema hasta que se necesita build/lint/test. **Causa raíz:** decisión `node-linker=hoisted` tomada por executor F7 sin ADR para resolver instalación de Plotly. **Riesgo si vuelve a pasar:** 1-3 horas perdidas diagnosticando. **Solución definitiva (sesión dedicada):** (a) revertir `.npmrc` a config estándar pnpm (quitar `node-linker=hoisted`), (b) borrar `node_modules/` de root + frontend con dev server PARADO, (c) `pnpm install` limpio desde root, (d) validar que Plotly carga sin warnings en :5173, (e) si Plotly falla, abrir ADR documentando por qué necesita hoisted + parchar shims manualmente como workaround documentado. **Parche temporal aplicado 2026-05-22:** shim `frontend/node_modules/.bin/tsc.CMD` editado manualmente a `..\..\..\node_modules\typescript\bin\tsc` — frágil, se rompe en próximo install. **Backups:** `.npmrc.bak_F7` en root y frontend. Detectado al intentar `pnpm build` post-F7. Ver §17.5 R1. |
| **🔴 DT-14** | **Plotly `data` array no debe depender de `selectedKey`/`hoveredKey` ni incluir `selectedpoints` reactivo** | **🔴 Cuando se retome el waterfall (S6)** | Plan F7 (abortado) incluyó `selectedKey` en deps del `useMemo` que construye el `data` array del waterfall, y `selectedpoints: [selectedIdx]` en el trace. Resultado: cada click/hover reconstruye el `data` → `react-plotly.js` llama `Plotly.react()` → re-anima barras desde 0 → si el usuario mueve el mouse mientras anima, animaciones se interrumpen y barras quedan COLAPSADAS visualmente (todas pegadas al eje cero salvo la última bajo el cursor). **Causa raíz arquitectural:** acoplar UI state interactivo con la fuente de verdad del chart. **Patrón correcto:** `useMemo` deps = `[steps, unitMode]` solamente. Selección visual se gestiona en sidebar/overlay externo o vía `Plotly.restyle()` imperativo. Sin `selectedpoints` en el trace. Sin estado global mutado en `onHover`. Detectado en F7 tras 4 fixes reactivos fallidos. Ver §17.5 R2. |
| **🔴 DT-15** | **"Build verde + lint verde + tests verde" ≠ "feature verificada" cuando hay interacción visual** | **🔴 Cualquier feature visual futura** | Executor F7 reportó ✅ TypeScript, ✅ ESLint, ✅ Prettier, ✅ Tests, ✅ `vite build` — y la feature estaba rota en runtime (gráfico colapsa al hover). Yo (Claude Code planner) cerré el ciclo basándome en el reporte del executor sin abrir el navegador a validar interacciones. **Causa raíz procesal:** el flujo 6 pasos §15 verifica artefactos estáticos (tipos, lint, build, tests automatizados), no comportamiento de runtime visual. **Protocolo correcto:** antes de declarar una feature visual "completada", el planner abre `http://localhost:5173/<ruta>`, prueba golden path + edge cases con interacción humana, revisa F12 Console (0 errores, 0 warnings Strict Mode). Si no puede abrir navegador → estado correcto es "PENDIENTE de validación humana", NO "verificado". El único que marca ✅ completada una feature visual es el usuario. Ver §17.5 R3. |
| **🔴 DT-16** | **Eliminar componentes "huérfanos" sin grep por path relativo lleva a romper typecheck horas después** | **🔴 Cualquier eliminación futura de carpeta/componente** | Plan F4.7 eliminó `src/shared/components/Breadcrumb/` declarándola huérfana porque el grep usó solo `"shared/components/Breadcrumb"`. `SoonPage.tsx` la importaba con path relativo `'../Breadcrumb'` y NO fue detectado. Typecheck pasó en F4.7 (cache de `.tsbuildinfo` o working tree distinto) pero falló al primer reintento en F4.8. **Regla obligatoria antes de eliminar `src/<dir>/<componente>/`:** correr 4 greps — `"<dir>/<componente>"`, `"./<componente>"`, `"../<componente>"`, `"@/<dir>/<componente>"` (si hay alias). Si CUALQUIERA devuelve match, NO eliminar. **Acción correctiva ejecutada:** carpeta restaurada en F4.8 con `Breadcrumb.tsx` (named export `Breadcrumb`, prop `items: { label, path? }[]`), `Breadcrumb.module.scss`, `index.ts`. Restauración inferida del uso real en `SoonPage.tsx:23`. |
| **🔴 DT-17** | **Barrel re-exports (`hooks/index.ts`) anulan tree-shaking en Vite dev mode** | **🔴 Cualquier import en página crítica de performance** | `LoginPage.tsx` importaba `useLogin` desde `'../hooks'` (barrel que re-exporta `useLogin` + `useLogout` + `useCurrentUser`). En `pnpm dev`, Vite descarga los 3 hooks aunque solo se use uno → `useLogout.ts` (2.4 KB) y `useCurrentUser.ts` (3.9 KB) viajaban en la carga de `/login` sin necesidad. **Solución aplicada en F4.9:** `import { useLogin } from '../hooks/useLogin'` (path directo al archivo, bypass del barrel). **Regla para futuras páginas críticas:** en `LoginPage`, `HomePage` y otras de carga inicial, importar siempre con path completo al archivo, NUNCA desde `index.ts` barrel. Aceptable para páginas internas no críticas. |
| **DT-18** | **`kpis_produccion/services.py` y `filters/services.py` no sanitizan Infinity/NaN** | **Cuando se retome kpis_produccion** | Si `flow_rates` o `financial_results` tienen valores Infinity/NaN (heredados del Excel V01), los KPIs QO/QW y el filtro UWI-EBITDA se corrompen. Solución: mover `_sanitize_col()` de `kpis_financieros/services.py` a `src/shared/utils.py` y reutilizar en todos los módulos que lean columnas numéricas de `ops.*`. |

**Regla:** cualquier `// TODO[Sx]:` en código → entrada espejo aquí. Al cerrar, eliminar de tabla + referenciar commit.

---

## 🔴 17.5 Lecciones críticas del F7 abortado (2026-05-22)

> **Contexto:** F7 (EBITDA Waterfall Inspector) costó **5+ horas perdidas** entre planificación, implementación, debugging y reverso completo. Resultado neto: 0 progreso, regresión al estado pre-F7 (SoonPage). Estas son las 3 reglas que evitan que esto se repita.

### 🔴 Regla R1 — NO MODIFICAR `.npmrc` sin ADR aprobado por el usuario

Cambiar `node-linker`, `store-dir`, `shamefully-hoist`, `public-hoist-pattern` o cualquier flag de pnpm afecta TODA la estructura de `node_modules/` del monorepo y rompe binarios silenciosamente.

**Si una librería nueva falla en `pnpm install`:**
- ❌ NUNCA activar `node-linker=hoisted` como atajo.
- ❌ NUNCA mover `store-dir` para "evitar permisos".
- ✅ Diagnosticar peer deps específicas con `pnpm why <pkg>`.
- ✅ Instalar con `--strict-peer-dependencies=false` puntual.
- ✅ Si no se resuelve en 15 min → DETENER, escalar al usuario con ADR.

**Verificación obligatoria pre-`pnpm install`:** ejecutar `cat .npmrc` (root + frontend) y avisar al usuario si aparece `hoisted` — el install puede regenerar shims rotos.

**Detalle:** [[DT-13]] en tabla §17.

---

### 🔴 Regla R2 — Charts Plotly: el `data` memoizado NUNCA depende de selección/hover

Plotly + `react-plotly.js` re-anima desde altura cero cada vez que recibe un `data` array con referencia nueva. Si las animaciones se interrumpen (porque el usuario mueve el mouse mientras anima), las barras quedan colapsadas visualmente.

**❌ Patrón PROHIBIDO:**

```tsx
const { data } = useMemo(() => {
  const selectedIdx = steps.findIndex((s) => s.key === selectedKey);
  return { data: [{ ...trace, selectedpoints: [selectedIdx] }] };
}, [steps, unitMode, selectedKey]); //  selectedKey EN DEPS = BUG GARANTIZADO
```

**✅ Patrón OBLIGATORIO:**

```tsx
// data solo depende de DATOS CRUDOS, jamás de UI state interactivo
const { data } = useMemo(() => {
  return { data: [trace] }; // sin selectedpoints
}, [steps, unitMode]); // ← selectedKey FUERA DE DEPS

// Selección visual se gestiona FUERA del data:
// - Sidebar/overlay externo que lee selectedKey del store
// - O `Plotly.restyle()` imperativo si se necesita resaltar barra
```

**Reglas duras:**
- Props `selectedKey`/`hoveredKey`/`activeIndex` NUNCA en deps de `useMemo` que construye `data` de Plotly.
- `onHover` de Plotly NUNCA debe mutar estado global (Zustand). Usar estado local efímero (`useState`) o no usar hover.
- Si el sidebar necesita reflejar hover, pasar el `hoveredKey` LOCAL al sidebar; el chart no se entera.
- `selectedpoints` en el trace = bandera roja. Re-evaluar antes de incluirlo.

**Detalle del bug:** [[DT-14]] en tabla §17.

---

### 🔴 Regla R3 — "Build verde" NO es "feature verificada" en componentes con interacción visual

El executor puede reportar:
- ✅ TypeScript exit 0
- ✅ ESLint exit 0
- ✅ Prettier exit 0
- ✅ Tests exit 0
- ✅ `vite build` exit 0

…y la feature **estar rota en runtime**. El executor no tiene navegador, no puede hacer hover, no puede ver el chart pintándose.

**Categorías de bug que NO detecta ninguna herramienta automática:**
- Animaciones interrumpidas / re-renders innecesarios de Plotly/D3/Chart.js.
- Layout colapsado por flex/grid en viewport real.
- Eventos de mouse mal cableados (hover roto, click duplicado).
- Race conditions en `useEffect` con Suspense + lazy import.
- Suspense que nunca resuelve por error en algún proveedor.

**Protocolo obligatorio antes de declarar "F* completada":**

1. El planner (yo, Claude Code) DEBE abrir `http://localhost:5173/<ruta-feature>` y validar:
   - Carga inicial sin errores en F12 Console.
   - Interacciones golden path: hover, click, teclado, toggle, filtros.
   - Persistencia de estado al navegar fuera/dentro.
   - 0 warnings de React Strict Mode en consola.
2. Si NO se puede abrir el navegador (sin acceso, dev server caído), declarar el estado como **"PENDIENTE de validación humana"**, NO como "verificado".
3. El usuario es el único que puede marcar una feature visual como ✅ completada.

**Reformulación del Paso 6 del flujo profesional (§15 + `docs/claude/flujo_6_pasos.md`):**

> **Verificación = build verde + lint verde + tests verde + INTERACCIÓN HUMANA EN NAVEGADOR.** Sin lo último, el estado correcto es "implementado pendiente de validación", no "completado".

**Detalle:** [[DT-15]] en tabla §17.

---

### Apéndice — Reglas de procedimiento de Claude Code derivadas

| # | Regla | Aplicación |
|---|-------|------------|
| P1 | Antes de cualquier `pnpm install`/`add`/`update` futuro: leer `.npmrc` y avisar al usuario si tiene flags no estándar. | Cada sesión |
| P2 | Plan que incluya Plotly/D3/Chart.js debe documentar EXPLÍCITAMENTE que `data` memoizado no depende de UI state interactivo. Si depende, el plan está mal y se rechaza. | Modo Planner |
| P3 | Reporte final del executor que diga "✅ completado" sin sección "Validación visual humana ⏳ PENDIENTE" → el planner debe rechazar el cierre y abrir navegador antes de declarar éxito. | Verificación post-executor |
| P4 | Si un fix reactivo (parche tras parche) se acumula >2 iteraciones sin resolver el bug, DETENER y revertir al estado anterior conocido bueno. No seguir parchando. | Debugging |
| P5 | "Atajo" en infraestructura compartida (`.npmrc`, lockfiles, `vite.config`, `tsconfig`) está PROHIBIDO sin ADR. Cualquier cambio debe estar justificado por escrito antes de aplicarse. | Modo Planner + Executor |

---

## 18. Bitácora de cambios (`bitacora.db`)

BD SQLite en `robustez_v02_backend/data/bitacora.db` (no versionada). Registra cambios diarios con narrativa técnica, artefactos no-código y contexto de impacto.

**5 tablas:** `semanas` | `cambios_diarios` | `archivos_afectados` | `detalles_tecnicos` | `artefactos`

```bash
# Inicialización
pnpm setup              # automático (omitir con SKIP_BITACORA=1)
pnpm init:bitacora      # manual

# Helper CLI
uv run python scripts/log_bitacora.py add-day --semana N --fecha FECHA --dia "Lunes" --resumen "..." --tareas W1.X --personas J C
uv run python scripts/log_bitacora.py list-changes --semana N

# Consulta rápida
sqlite3 data/bitacora.db "SELECT fecha, substr(resumen,1,80) FROM cambios_diarios ORDER BY fecha DESC LIMIT 5;"
```

**Regla de oro:** NUNCA UPDATE/DELETE. Solo INSERT. Si hay error pasado, agregar entrada correctiva nueva.

> 📘 Guía completa: [`docs/claude/bitacora_guia.md`](./docs/claude/bitacora_guia.md)

---

## 19. Bitácora de sesiones — changelog Claude Code

| Fecha | ID | Descripción del cambio | Archivos principales | Commits |
|-------|----|------------------------|----------------------|---------|
| 2026-05-04 al 09 | S5-W1 | Backend completo: auth LDAP + cookie firmada + RBAC 4 tablas + audit + middleware stack + core. Alembic 0001. BDs SQLite. ETL V01→V02 (1745 filas). 7 unit + 3 integration tests. | `src/main.py`, `features/auth/`, `features/permissions/`, `features/audit/`, `middleware/`, `alembic/versions/0001_initial_auth.py` | 862573b, 314f638 |
| 2026-05-09 al 16 | S5-W1 (post) | Frontend scaffold: LoginPage + splash + BetaBanner + DashboardPreview. Header + Footer + DrawerStrip + Drawer 340px. KpiTicker. HomePage + Carousel. ProtectedRoute + SessionExpiryBanner. 8 primitivos UI. ResolutionGuard. apiClient openapi-fetch. vitest jsdom + RTL + setup. | `app/layouts/`, `features/auth/`, `features/home/`, `shared/components/primitives/`, `shared/components/Drawer/`, `app/store/` | 5a32385, a35974c |
| 2026-05-17 al 18 | F1 | Filtro Jerarquía completo: `HierarchyPills` acordeón 6 niveles + búsqueda >8 opciones + navegación teclado + auto-cleanup cascada + `filtersStore` draft/applied + paleta Ecopetrol. Filters API backend. | `shared/components/filters/HierarchyPills/`, `app/store/filtersStore.ts`, `features/filters/` (backend) | — |
| 2026-05-18 al 19 | F2 | Filtro Período: `PeriodoControls` MiniCalendar + YearMonthSelect + PeriodoSummary + RangeWarningBanner. `periodoStore` draft/applied + `_isInitialized`. Bootstrap YTD fix (`yearsForBulk` incluye año más reciente mientras `!isInitialized`). Drawer wiring Período. SCSS cleanup. Lint fixes mocks `async→Promise.resolve`. | `shared/components/filters/PeriodoControls/`, `panels/PeriodoPanel.tsx`, `Drawer.tsx`, `Drawer.module.scss`, `app/store/periodoStore.ts` | faa2534, b067285, f80f2e8, 32be7e0 |
| 2026-05-19 al 20 | F3 | Filtro Well Config rediseño completo: `wellConfigSchema.ts` (Zod 4 uniones), `wellConfigStore` draft/applied + `countDraftFromDefault()`, `OptionTile<T>` + `BinarySelector<T>` genéricos sin casts, `WellConfigPanel` tiles icon-leading + badge dinámico + subtítulo live. Drawer wiring wellconfig. SCSS cleanup huérfanos. 11/13 validaciones ✅ (V7/V9 OOM — DT-9). | `features/filters/schemas/wellConfigSchema.ts`, `app/store/wellConfigStore.ts`, `shared/components/filters/WellConfigControls/`, `panels/WellConfigPanel.tsx`, `Drawer.tsx`, `Drawer.module.scss` | 9a5aa6b, 9028420, 96e9ce4, a55a343, bc6f36a, 0143b8f |
| 2026-05-23 | F4.7 | Optimización carga `/login` — sesión 1: lazy-load del `Drawer` desde `LayoutMain.tsx` con `React.lazy()` + `Suspense fallback={null}`. Eliminación errónea de carpeta `src/shared/components/Breadcrumb/` (revertida en F4.8 — ver DT-16). Análisis HAR `Costos_Diap.har` (baseline 9.80s `onContentLoad`). Plan en `Planes/plan_F4.7_lazy_drawer_2026-05-23.md`. | `src/app/layouts/LayoutMain.tsx` | sin commit (acumulado con F4.8) |
| 2026-05-23 | F4.7b | Pre-condición para F4.8: añadir `ProtectedRoute` envolviendo `<LayoutMain />` en `router.tsx` + rutas `/forbidden` y catch-all `*` con sus respectivos lazy components + limpieza comentarios obsoletos. | `src/app/router.tsx` | fcf967e |
| 2026-05-23 | F4.8 | Optimización carga `/login` — sesión 2: `LayoutMain` pasa a `React.lazy()` desde `router.tsx`, envuelto en `Suspense fallback={<PageLoader />}` dentro del `ProtectedRoute`. Restauración carpeta `src/shared/components/Breadcrumb/` (revierte error de F4.7 — ver DT-16). Plan v2 reformulado tras flujo profesional §15 CLAUDE.md (13 hallazgos integrados, ver `Planes/plan_F4.8_lazy_layoutmain_2026-05-23.md` §12). Impacto medido: `DOMContentLoaded` 9.80s → 9.20s (-600ms), transfer 4.1 MB → 3.9 MB (-200 KB), requests 50 → 57. | `src/app/router.tsx`, `src/shared/components/Breadcrumb/Breadcrumb.tsx`, `src/shared/components/Breadcrumb/Breadcrumb.module.scss`, `src/shared/components/Breadcrumb/index.ts` | pendiente |
| 2026-05-23 | F4.9 | Optimización carga `/login` — sesión 3: bypass del barrel `features/auth/hooks/index.ts` desde `LoginPage.tsx` (`from '../hooks'` → `from '../hooks/useLogin'`) para evitar descargar `useLogout.ts` + `useCurrentUser.ts` en `/login` (DT-17). `ProtectedRoute` pasa también a `React.lazy()` desde `router.tsx` — saca `ProtectedRoute.tsx` + `Spinner.tsx` + `Spinner.module.scss` del waterfall de `/login`. Validación funcional: `pnpm typecheck` ✅. Sin tests ni navegador (decisión del usuario — feature de login validada previamente, no se quiso re-validar). | `src/features/auth/pages/LoginPage.tsx`, `src/app/router.tsx` | pendiente |
| 2026-05-25 | F5.0 | `EbitdaInspectorCard` shell: `UnitToggle<UnitMode>` (USD/BI \| KUSD) genérico + sidebar 7 filas mock (Ingresos, M.Subsuelo, Dilución, Tratamiento, Energía, Transporte, Costos Fijos) con `formatInspectorValue` + `formatRevenuePct` + `formatRowValue`. ChartPlaceholder dashed. Layout grid 2col desktop / 1col mobile. `EbitdaCostosPage` reemplaza `SoonPage`. Spec waterfall futura: `robustez_v02_frontend/docs/Graf.md`. Directiva §0.2 CLAUDE.md formalizada (audit-first antes de cualquier plan). DT-16 + DT-17 documentados. Plan: `Planes/plan_F5.0_ebitda_inspector_card_2026-05-23.md`. | `EbitdaInspectorCard/`, `UnitToggle/`, `formatInspectorValue.ts`, `EbitdaCostosPage.tsx`, `docs/Graf.md`, `CLAUDE.md` | pendiente |
| 2026-05-25 | F5.0b | Fix cadena flex rota — card no llenaba altura vertical. Diagnóstico: 4 links rotos: `.layout` tenía `align-items:flex-start` + faltaba `flex:1`; `.main` faltaba `display:flex + flex-direction:column`; `.chartPlaceholder` tenía `clamp()` que capeaba altura. Fixes en 2 archivos SCSS: `EbitdaCostosPage.module.scss` (align-items:stretch, flex:1, display:flex) + `EbitdaInspectorCard.module.scss` (min-height fijo). `EbitdaInspectorCard` ocupa 100% de la altura disponible en viewport. | `EbitdaCostosPage.module.scss`, `EbitdaInspectorCard.module.scss` | pendiente |
| 2026-05-25 | F6.1-pozos | Paridad conteo pozos: V01 muestra 153, V02 mostraba 213 (raw wells_attributes). Implementado `FilterService._get_uwi_options_ebitda()`: JOIN flow_rates×wells_attributes×financial_results + HAVING EBITDA≠0 AND BLS≠0 AND EBITDA/Bl≠0. `filters/api.py` extendido con 6 query params (from/to_year/month, estado_pozo, produccion). Frontend: `useHierarchyFilters.ts` envía periodo applied + wellconfig applied al query uwi; `filtersService.ts` extiende `HierarchyParams` + fix URLSearchParams para números. Resultado: 153 pozos = paridad exacta V01. | `filters/services.py`, `filters/api.py`, `useHierarchyFilters.ts`, `filtersService.ts` | pendiente |
| 2026-05-25 | F6.1-diagnostico | Causa raíz KPI QO/QW inflados +46% identificada: `ops.wells_attributes` contiene UWIs duplicados (2-4 copias por UWI, ej. CHIC0002 ×4). JOIN `flow_rates × wells_attributes` multiplica silenciosamente cada fila de hechos ×N → QO V02=55.873 vs V01=38.120. Con `DISTINCT ON (uwi,year,month,well_status,pend_id_cc)`: QO=37.982 (-0.4% de V01). Documentado en CLAUDE.md §20 paso 5 sub-check (b). Fix pendiente: deduplicar `ops.wells_attributes` (decisión usuario). | `CLAUDE.md §20` | pendiente |
| 2026-05-25 | F5.2-fix | Fix formato numérico + sanitización PostgreSQL. `_sanitize_col()` → `NULLIF(NULLIF(NULLIF(col,'Infinity'::float8),'-Infinity'::float8),'NaN'::float8)` (idiomático). `_format_currency`/`_format_decimal` → locale español 1.234,56 (reemplazo `.replace(",","_").replace(".",",").replace("_",".")`). `formatDelta` mapper frontend → `'es-CO'` (paridad V01). DT-18 documentado. Validaciones: ruff ✅ mypy ✅ typecheck ✅ eslint ✅ 76/79 tests ✅. | `kpis_financieros/services.py`, `ebitdaKpiMapper.ts`, `CLAUDE.md §17` | pendiente |
| 2026-05-26 | F8-visual | Ajustes visuales `TendenciaEbitdaChart` para paridad con diseño `predict.md` §8.4: (1) Líneas sin markers (`mode:'lines'`), colores spec (`#0A1F33`, `#E08226`, `#2E8B47`), anchos 2/1.8/1.8. (2) Eje Y2 unificado para ambas series cumulativas (eliminado y3). (3) X-axis: labels ocultos, título "Pozos (ordenados por EBITDA/Bl)", índices numéricos en vez de UWI. (4) Fonts monospace en ticks/annotations. (5) Zonas opacidad 0.55/0.60 (era 0.35), KPI line `#6B7A8A` dashed. (6) Márgenes `{l:50,r:50,t:24,b:40}`, fondo blanco, Inter font. (7) Fix altura chart: `position:absolute;inset:0` + flex chain (`.chartSlot` → `.container` → `.chartArea` → `.chart`) + `:global()` overrides Plotly internals. (8) `RangeSlider` paleta Ecopetrol: fill `#004236`, thumb border `#004236`, label monospace uppercase. | `TendenciaEbitdaChart.tsx`, `TendenciaEbitdaChart.module.scss`, `RangeSlider.module.scss`, `EbitdaRankPage.module.scss` | pendiente |
| 2026-05-26 | F9-reports | `ReportsPage` (`/reports` — EBITDA Seguimiento): integración `AppliedFiltersPanel` sidebar desktop + `MobileAppliedFiltersSheet` mobile + KPI ticker con datos EBITDA reales. Creados `useEbitdaKpis`, `ebitdaKpiService`, `ebitdaKpiMapper` propios del feature (aislamiento cross-feature). `LayoutMain.tsx`: añadido `/reports` a `TICKER_KEYS_BY_ROUTE`. Fix previo sesión: Sparkline crash con `data.length < 2` guard + KPI ticker mismatch entre páginas (duplicación hook en `ebitda_rank`). Typecheck ✅. | `features/reports/pages/ReportsPage.tsx`, `features/reports/hooks/useEbitdaKpis.ts`, `features/reports/mappers/ebitdaKpiMapper.ts`, `features/reports/services/ebitdaKpiService.ts`, `features/reports/pages/ReportsPage.module.scss`, `app/layouts/LayoutMain.tsx` | pendiente |
| 2026-05-27 | F10-well-condition-backend | Módulo compartido `well_condition.py`: `classify_well()` (4 categorías: rentable/marginal/no_rentable/otro), `resolve_columns()` (4 variantes estado×produccion, `fin_alias` parametrizable para reutilizar entre features), `build_condition_select_columns()` (SQL con sanitización NULLIF Infinity/NaN). Integrado en `ebitda_rank/services.py` (`fin_alias="fr"`, LEFT JOIN oc) y `regression/services.py` (`fin_alias="fin"`, LEFT JOIN oc). 21 tests unitarios (`test_well_condition.py`): classify_well (11), resolve_columns (6), build_condition_select_columns (4). Fix import order ruff I001. Backend 127 tests passed. | `src/shared/well_condition.py`, `features/ebitda_rank/services.py`, `features/regression/services.py`, `tests/unit/test_well_condition.py` | pendiente |
| 2026-05-27 | F10-well-condition-map-frontend | `WellConditionMap.tsx` reemplazado: de 1 trace hardcoded (todos ★ verdes "Rentable") a 4 traces por categoría con `CATEGORY_CONFIG` + `CATEGORY_ORDER`. Símbolos: ★ star rentable (#2E8B47), ◆ diamond marginal (#F4D124), ✚ cross-thin-open no_rentable (#C5311E), ● circle otro (#6B7A8A). Paridad visual con `PredVsActualChart.tsx` (H1). Prop opcional `activeCategories?: ReadonlySet<string>` para filtrado de categorías desde el padre. `useMemo` deps = `[points, activeCategories]`. Agrupación `Map<string, WellPointUI[]>` con fallback a 'otro'. Plan: `Planes/plan_WELLCONDITIONMAP_traces_por_categoria_2026-05-27.md`. Typecheck ✅. Lint ✅. ⏳ PENDIENTE validación humana (V3-V5). | `features/ebitda_rank/components/WellConditionMap/WellConditionMap.tsx` | pendiente |
| 2026-05-27 | F11-detalle-ingresos-grid | Grid 2×2 de 4 combo charts (Ingreso KUSD vs Brent/DifOil/TRM/Producción) en `DetalleIngresosPage` reemplaza placeholder "En construcción". **Backend nuevo:** feature `detalle_ingresos/` con `api.py` + `services.py` + `schemas.py` + `__init__.py`. Endpoint `GET /api/v1/detalle-ingresos/ingresos-combo` con `INGRESO_COLUMN_MAP` + `PROD_COLUMN_MAP` por `(produccion, estado_pozo)`, JOIN financial_results×wells_attributes(DISTINCT ON uwi)×market_base_costs×flow_rates, `_sanitize_col()` Infinity/NaN, RBAC vía `_get_allowed_campos()`. Router montado en `main.py`. **Frontend nuevo:** primitivo `shared/components/charts/ComboChart/` (Plotly bar+line con `createPlotlyComponent(Plotly)` desde `plotly.js-dist-min` + `useResizeHandler` prop — patrón obligatorio del proyecto). Feature `detalle_ingresos/` con `pages/DetalleIngresosPage` (sidebar + grid), `charts/ChartsGrid` (2×2 con Esc collapse), `charts/ChartCard` (header + ComboChart + toggle), `charts/ExpandToggleButton` (Maximize2/Minimize2 Lucide), `charts/chart.config.ts`, `state/chartsStore.ts` (Zustand `expandedId`), `hooks/useIngresosCombo.ts` (TanStack Query, lee filtersStore FLAT + periodoStore.applied + wellConfigStore.applied con `.toLowerCase()`), `services/ingresosComboService.ts` (fetch + mapper snake_case→camelCase), `types.ts`. **Tokens:** 19 alias `$ec-*` añadidos a `_tokens.scss` (verde-soft, lime, amber, red, orange, yellow, ink, navy, body, muted, line, panel, off, white). **Regla R2:** `data` useMemo deps = `[labels, barValues, lineValues, lineColor, secondaryUnit]` solamente — sin UI state. Validaciones: TypeScript ✅, ESLint ✅, ruff ✅, mypy ✅, stylelint archivos nuevos ✅. Plan: `Planes/plan_DETALLE_INGRESOS_4graficas_2026-05-27.md`. ⏳ PENDIENTE validación humana en navegador. | `backend/src/features/detalle_ingresos/` (api/services/schemas), `backend/src/main.py`, `shared/components/charts/ComboChart/`, `features/detalle_ingresos/` (pages/charts/hooks/services/state/types), `styles/_tokens.scss` | pendiente |
| 2026-05-27 | F12-app-menu-hover | `AppMenuPopover.tsx` cambia comportamiento de click a hover: `handleAppHover` (on `onMouseEnter`) actualiza `activeAppId` + `activeSubId` (primer sub por defecto si existe). Click en app sigue navegando. Tecla Esc cierra. Fix ESLint `@typescript-eslint/no-unnecessary-type-assertion`: `activeApp!.subs!` → `hasSubs && activeApp?.subs ? activeApp.subs : []`. | `shared/components/navigation/AppMenuPopover.tsx` | pendiente |
| 2026-05-27 | F8-inline-expand | `EbitdaRankPage` reemplaza modal por **expand inline en desktop (≥1024px)**: botón "Ampliar"/"Reducir" alterna `gridTemplateColumns` (`1fr 44px` / `44px 1fr` / `1.55fr 1fr`) con `transition cubic-bezier(0.7,0,0.3,1) 0.4s`; el panel no-ampliado colapsa a `CollapsedTab` vertical (44px ancho, icono naranja + label rotado `writing-mode:vertical-rl` + chevron). Mobile (<1024px) conserva `ChartModal`. **Fix H1 (CRÍTICO):** `gridCols='1fr'` cuando `isMobile===true` para no sobreescribir `@media` con inline style. **Fix H2 (ALTO):** `useEffect(()=>{ if(isMobile) setExpanded(null) }, [isMobile])` resetea expanded al pasar a mobile. Nuevo componente `CollapsedTab` (props: `side`, `label`, `icon: 'trend'\|'map'`, `onClick`) con `Maximize2`/`Minimize2`/`TrendingUp`/`MapPin`/`ChevronLeft`/`ChevronRight` (lucide, sin nuevas deps). Nueva clase `.iconBtnActive` (amber `#d97706`, background `#fff8dc`). `aria-pressed` en botón toggle. `prefers-reduced-motion` desactiva transición. Notify Plotly de resize tras 450ms (post-transición). R2/R3 cumplidas. Plan: `Planes/plan_EBITDARANK_ampliar_inline_expand_2026-05-27.md`. Typecheck ✅. ⏳ PENDIENTE validación humana (V2-V10). | `features/ebitda_rank/components/CollapsedTab/CollapsedTab.tsx`, `CollapsedTab.module.scss`, `index.ts`, `features/ebitda_rank/pages/EbitdaRankPage.tsx`, `EbitdaRankPage.module.scss` | pendiente |
| 2026-05-28 | F13-skill-install | Instalado skill `emil-design-eng` (Emil Kowalski — UI polish, component design, animation decisions, invisible details). Comando: `npx skills add emilkowalski/skill`. Archivo `SKILL.md` (679 líneas) con framework de decisiones de animación, formato de review Before/After/Why, principios Sonner, reglas clip-path, prefers-reduced-motion, etc. Instalado con symlink a Claude Code + universal para 56 agentes (Codex/Gemini/Copilot/OpenCode +9 más). | `.agents/skills/emil-design-eng/SKILL.md` | sin commit |
| 2026-05-28 | F13-inspector-plan-v2 | Plan auditado (flujo profesional §15 CLAUDE.md) para transiciones del EBITDA Inspector. **v1** propuesto inicialmente sin auditoría; **v2** reformulado tras auditoría con 15 hallazgos integrados: H1 (regla global `prefers-reduced-motion` en `styles/index.scss` ya cubre — no añadir local), H2 (curva del proyecto `cubic-bezier(0.4, 0, 0.2, 1)` para cohesión vs curva Emil del skill `0.23, 1, 0.32, 1`), H3 (nombre del paquete `robustez-v02-frontend` con guiones, no underscores — v1 tenía comandos rotos), H6 (`stylelint-config-standard-scss@14` puede no reconocer `@starting-style` → usar `@keyframes` CSS universal), H7-H8 (`key={activeUnit}` en div INTERIOR al `<Suspense>` para NO remontar el lazy chunk del WaterfallChart → evita flash del Spinner), H9 (no incluir `pnpm build` en validaciones — innecesario para 3 archivos cosméticos). Plan v2 con 13 secciones, 3 archivos a modificar, 4 validaciones automáticas (typecheck + eslint + stylelint + prettier — sin build), prompt executor literal copy-paste. | `Planes/plan_EBITDA_INSPECTOR_transiciones_2026-05-27.md` | sin commit |
| 2026-05-28 | F13-inspector-impl | Executor ejecutó plan, pero NO respetó §3 (Decisiones técnicas) ni §9 (Reglas R7/R8/R9) del v2 — implementó patrón del v1 (con `@starting-style` + `@media (prefers-reduced-motion)` local + curva del skill + `key=` en wrapper externo `.chartArea`). Tras verificación, Claude aplicó correcciones para alinear con v2: (a) clase nueva `.chartCanvas` con `@keyframes chart-canvas-in` (kebab-case obligatorio por stylelint `keyframes-name-pattern`), (b) `key={activeUnit}` movido a div INTERIOR al `<Suspense>` envolviendo solo `<WaterfallChart>` → Suspense estable, sin remount del lazy chunk, sin flash del Spinner, (c) curva `cubic-bezier(0.4, 0, 0.2, 1)` del proyecto en TODAS las transitions, (d) `@media (prefers-reduced-motion)` local eliminado (global en `styles/index.scss:52-59` ya cubre con `!important`), (e) `transition: all` reemplazado por 4 props específicas (background/border-color/box-shadow/transform) en `.thumb` + `:active scale(0.97)` press feedback, (f) transition opacity en `.preview`, transition background+color en `.icon`. Validaciones: V1 typecheck ✅, V2 ESLint ✅ (max-warnings 0 limpio), V3 stylelint ✅ archivos modificados, V4 prettier ✅ (auto-fix aplicado). | `EbitdaInspectorCard.module.scss`, `EbitdaInspectorCard.tsx`, `InspectorThumbnail.module.scss` | sin commit |
| 2026-05-28 | F13-transition-iter | Iteración de 5 patrones de transición sobre `.chartCanvas` aplicando skill `emil-design-eng` — todos respetando R2/DT-14 (sin tocar Plotly), `key={activeUnit}` en div interior, curva del proyecto. **Iter 1** crossfade + blur: `opacity 0→1` + `filter: blur(2px)→blur(0)` 200ms. **Iter 2** wipe reveal: `clip-path: inset(0 100% 0 0)→inset(0 0 0 0)` 290ms→400ms (direccional izquierda→derecha). **Iter 3** ripple reveal: `clip-path: circle(0% at 50% 50%)→circle(150% at 50% 50%)` 400ms (concéntrico desde el centro). **Iter 4** morph collapse: `transform: scaleY(0.7)→scaleY(1)` + `opacity` con `transform-origin: bottom center` 400ms (barras crecen del piso). **Iter 5 — ESTADO FINAL**: liquid morph 500ms. 3 props animadas en paralelo: `clip-path: inset(12% 18% 12% 18% round 80px) → inset(0 0 0 0 round 0)` (blob asentándose), `transform: scale(0.92)→scale(1)`, `opacity: 0→1`. Efecto orgánico de "gota líquida que se asienta en el contenedor". ⏳ PENDIENTE validación humana en navegador. | `EbitdaInspectorCard.module.scss` | sin commit |
| 2026-05-28 | F14-kpis-delta-backend | **Backend nuevo:** feature `kpis_delta/` con `api.py` + `services.py` + `schemas.py`. Endpoint `GET /api/v1/kpis-delta/` retorna 4 items (Δ BRENT, Δ DIF OIL, Δ PRODUCCIÓN, Δ TRM) con `start`, `end`, `delta`, `pct`, `spark[]`, `unit`, `invert_tone`. BRENT y TRM globales (sin jerarquía); DIF OIL y PRODUCCIÓN con RBAC + jerarquía. `PROD_COLUMN_MAP` por (produccion × estado_pozo). `_sanitize_col()` NULLIF Infinity/NaN. `DISTINCT ON (uwi)` para wells_attributes. Router montado en `main.py`. Plan v2 auditado con 8 hallazgos críticos (H1-H8): H1 filtersStore plano, H2 periodoStore fromYear/fromMonth, H3 wellConfig toLowerCase(), H4 fetch+URL (no apiClient), H5 imports relativos, H6 start=spark[0] end=spark[-1], H7 _sanitize_col en todas las columnas, H8 ensureTwoPoints guard. | `backend/src/features/kpis_delta/` (api/services/schemas/__init__), `backend/src/main.py` | pendiente |
| 2026-05-28 | F14-kpis-delta-frontend | **Frontend:** hook `useKpisDelta` + service `kpisDeltaService` + mapper `kpisDeltaMapper` + types `deltaKpi.ts` creados dentro de `features/detalle_ingresos/` (no en seguimiento — KPIs delta son exclusivos de `/detalle-ingresos`). `SeguimientoPage` revertido a usar `MOCK_KPI_CARDS` (sin dependencia de backend delta). Componente `DeltaKpiStrip` creado como standalone (no usado actualmente — KPIs van en cinta). | `features/detalle_ingresos/hooks/useKpisDelta.ts`, `features/detalle_ingresos/services/kpisDeltaService.ts`, `features/detalle_ingresos/mappers/kpisDeltaMapper.ts`, `features/detalle_ingresos/types/deltaKpi.ts`, `features/detalle_ingresos/components/DeltaKpiStrip/`, `features/seguimiento/pages/SeguimientoPage.tsx` | pendiente |
| 2026-05-28 | F14-kpis-delta-ticker | **Integración en KpiTicker del LayoutMain:** `TICKER_KEYS_BY_ROUTE['/detalle-ingresos']` extendido con 4 keys delta (`delta-brent`, `delta-dif-oil`, `delta-produccion`, `delta-trm`). `LayoutMain.tsx` importa `useKpisDelta` de `detalle_ingresos` y pasa overrides reales (val, unit, delta, neg, startVal, endVal, series) a los items del ticker. `KpiTickerEntry` extendido con campos opcionales `startVal`, `endVal`. `KpiTickerOverride` extendido con `delta`, `neg`, `startVal`, `endVal`, `series`. `TickerItem.tsx` renderiza layout delta 3 filas: fila 1 (label + sparkline), fila 2 (valor delta grande), fila 3 (%), footer (INICIO valor+unit \| FIN valor+unit) separado con border-top. Estilos `.deltaLayout`, `.deltaHead`, `.deltaCenterVal`, `.deltaCenterPct`, `.deltaFooter`, `.deltaCol`, `.deltaColLabel`, `.deltaColVal`, `.deltaColUnit` en `KpiTicker.module.scss`. `kpiTickerData.ts` actualizado con `startVal`/`endVal` en datos mock delta. Solo visible en `/detalle-ingresos`. ✅ Validado en navegador. | `app/layouts/LayoutMain.tsx`, `shared/components/KpiTicker/TickerItem.tsx`, `shared/components/KpiTicker/KpiTicker.tsx`, `shared/components/KpiTicker/KpiTicker.module.scss`, `shared/components/KpiTicker/kpiTickerData.ts` | pendiente |
| 2026-06-04/05 | F15-detalle-costos-backend | **Backend nuevo:** 2 servicios adicionales en `kpis_costos/`: (1) `CostosFijosTickerService` (`services_costos_fijos.py`) — 2 KPIs (Costos Fijos KUSD + USD/Bl) + 7 deltas (Δ costos, Δ costos/bl, Δ energía, Δ tratamiento, Δ M.subsuelo, Δ gasto, Δ costos levant). `DELTA_COMPONENTS` configurable. JOIN operating_costs × flow_rates × wells_attributes (DISTINCT ON uwi). (2) `CostosGastosMensualService` (`services_costos_gastos.py`) — labels[] + series[] (6 componentes: costos_fijos, gastos, tratamiento, m_subsuelo, energia, ingreso-costos). RBAC + `_get_allowed_campos()`. Schemas: `schemas_costos_fijos.py` (CostosFijosKpiItem + CostosFijosDeltaItem + CostosFijosTickerResponse) + `schemas_costos_gastos.py` (CostosSerieItem + CostosGastosMensualResponse). Endpoint `GET /api/v1/kpis-costos/costos-gastos-mensual` montado en `api.py`. | `backend/src/features/kpis_costos/` (services_costos_fijos.py, services_costos_gastos.py, schemas_costos_fijos.py, schemas_costos_gastos.py, api.py) | pendiente |
| 2026-06-04/05 | F15-detalle-costos-frontend | **Frontend completo:** `DetalleCostosPage` reemplaza stub por layout sidebar + `CostosGastosCard`. `CostosGastosCard`: inspector layout con rail de thumbnails (izq) + chart area (der) + botón Ampliar/Reducir (Maximize2/Minimize2). `StackedBarChart` (Plotly stacked bar via `createPlotlyComponent` + `useResizeHandler`). `StackedBarPreview` (SVG miniatura memo). **Custom tooltip HTML** centrado superior del chart — NO usa Plotly hover nativo (prob. de compatibilidad con `createPlotlyComponent`), calcula mes por posición X del mouse vía `onMouseMove` nativo (`hovermode: false`). Formato `$3.604,3` (es-CO `fmtKusd`). Estado hover local `useState` — R2 cumplida (no Zustand, data deps = `[labels, series]`). `useCostosFijosKpis` + `useCostosGastosMensual` hooks. `costosFijosKpiService` (2 fetch). `costosFijosKpiMapper` (ensureTwoPoints, sort avg desc). Types `CostosGastosSerie` + 4 API interfaces. **KPI Ticker:** 11 keys en `TICKER_KEYS_BY_ROUTE['/detalle-costos']`. `LayoutMain.tsx` consume `useCostosFijosKpis` condicional (`hasCostosKeys`). `kpiTickerData.ts` con 11 mocks. ⏳ Tooltip posición centrada superior en ajuste final. | `features/detalle_costos/` (pages, components/CostosGastosCard, components/StackedBarChart, components/StackedBarPreview, hooks, mappers, services, types), `app/layouts/LayoutMain.tsx`, `shared/components/KpiTicker/kpiTickerData.ts` | pendiente |
| 2026-06-04/05 | F15-tooltip-custom | **Investigación tooltip Plotly:** `onHover` prop de `react-plotly.js` con `createPlotlyComponent(Plotly)` NO dispara callbacks (probado: `hoverinfo:'skip'`, `'none'`, `hovertemplate:'<extra></extra>'`, addEventListener `plotly_hover`, MutationObserver, `el.on('plotly_hover')`, `onAfterPlot`). Ninguno funcionó. **Solución final:** `onMouseMove` nativo en div contenedor + cálculo posición X del mouse vs márgenes Plotly (`MARGIN_LEFT=52, MARGIN_RIGHT=16`) + `Math.floor(x / barWidth)` para obtener índice del mes. `hovermode: false` desactiva hover nativo de Plotly. Tooltip es `position:absolute; top:0; left:50%; transform:translateX(-50%)` con `pointer-events:none` + `z-index:100`. **Lección aprendida:** `createPlotlyComponent` no conecta event handlers de react-plotly.js. Para hover custom en charts futuros, usar `onMouseMove` nativo, NO confiar en props de Plotly. | `StackedBarChart.tsx`, `StackedBarChart.module.scss` | pendiente |
| 2026-06-05 | FIX-postgres-credentials | **Fix credenciales PostgreSQL:** Nueva instancia **PostgreSQL 18.4** en `10.100.26.139:5432` con usuario `robustez`. Problema: app lanzaba `connection refused` aunque el `.env` tenía las credenciales correctas. Causa raíz: `config.py` tenía el valor `postgres:GET_DCA_db_2524@localhost:5432` hardcodeado como default Pydantic — si pydantic-settings fallaba al parsear el carácter `£` del `.env`, usaba el default antiguo. Fix: (1) `.env` → `postgresql://robustez:***@10.100.26.139:5432/robustez_v02`, (2) `.env.example` → placeholder con usuario/host correcto, (3) `config.py` → default cambiado a `robustez:changeme@10.100.26.139:5432`. Verificación: `get_settings().ops_database_url` lee el `.env` correcto; SQLAlchemy conecta: `wells_attributes` 13,450 filas, `financial_results` 216,641 filas. | `robustez_v02_backend/.env`, `robustez_v02_backend/.env.example`, `robustez_v02_backend/src/core/config.py` | sin commit (.env no se versiona) |
| 2026-06-10 | FIX-node-modules | **Reinstalación node_modules:** `pnpm install` desde frontend resolvió `Cannot find module vite/bin/vite.js` — directorio `node_modules/vite/` existía pero vacío (corrupción). pnpm eliminó y recreó `node_modules/` from scratch. 860 paquetes resueltos (860 reused, 0 downloaded). Sin `.npmrc` problemático (DT-13 resuelta previamente). | `robustez_v02_frontend/node_modules/` (regenerado), `pnpm-lock.yaml` | sin commit (node_modules no versionado) |
| 2026-06-10 | F16-avatar-panel-redesign | **Rediseño AvatarPanel estilo tarjeta:** Panel de usuario cambiado de lista vertical simple a tarjeta con grid de iconos. (1) Avatar 48px + nombre completo (`fullName` del store) + badge "ADMIN" pill verde `#004236` + email con text-overflow. (2) Grid 3 columnas: Admin (ShieldCheck verde), Configuración (Settings gris), Ayuda (HelpCircle violeta) — iconos 24px sin fondo, borde sutil `rgb(0 0 0 / 6%)`. (3) "Cerrar sesión" centrado rojo. (4) Tarjeta 300px, border-radius 16px, shadow más pronunciada. Props añadidas: `fullName: string | null`, `isAdmin: boolean` propagadas desde `LayoutMain → Header → AvatarPanel`. 3 iteraciones visuales con el usuario: v1 fondos coloreados (rechazado), v2 sin fondos + iconos más grandes, v3 bordes sutiles + padding ampliado. | `AvatarPanel.tsx`, `Header.tsx`, `Header.module.scss`, `LayoutMain.tsx` | pendiente |
| 2026-06-10 | F16-nav-cleanup | **Limpieza panel de navegación:** (1) Texto "APLICACIONES" (eyebrow) eliminado de `AppMenuPopover`. (2) Título cambiado de "Robustez · Navegar" a "Robustez · Panel de Navegación". (3) Opción "Admin" removida de `nav.config.ts` — Admin ahora solo accesible desde el AvatarPanel del usuario. Import `Settings` limpiado. 5 items de navegación: Inicio, Utilidad Neta, Predicción, EBITDA Rank, EBITDA Seg. (con subs). | `AppMenuPopover.tsx`, `nav.config.ts` | pendiente |
| 2026-06-11 | FIX-stash-restore | **Rescate del stash de otra sesión** (horas perdidas restaurando a mano): `git stash apply` rechazado por 2 archivos modificados idénticos al stash → `git restore` puntual de esos 2 + apply; único conflicto `uv.lock` resuelto con versión HEAD. **67 archivos restaurados**; `_tokens.scss` recuperó `$rb-pop-shadow` (causa real del error de compilación Vite). Commit de la sesión externa consolidado. | working tree completo (67 archivos), `styles/_tokens.scss`, `uv.lock` | b784445 |
| 2026-06-11 | FIX-ldap-resolver | **Fix definitivo del LDAP que fallaba "todos los días":** dnspython cachea la configuración DNS del sistema en su primer uso — si el backend arrancaba antes de conectar la VPN, el resolver quedaba sin los DNS corporativos y `red.ecopetrol.com.co` nunca resolvía. Fix: crear `dns.resolver.Resolver(configure=True)` **fresco en cada intento de login** (relee la config DNS vigente). Ya no importa el orden VPN/backend. | `robustez_v02_backend/src/features/auth/services.py` | pendiente |
| 2026-06-11 | F20-perf-postgres | **Optimización KPIs lentos (64s→2,4s, 27×):** causa raíz — el planner de PostgreSQL estimaba `rows=1` en joins hecho×hecho por PK de 6 columnas (selectividades correlacionadas multiplicadas) → nested loop re-ejecutaba la subquery `DISTINCT ON (uwi)` de wells_attributes **26.304 veces** (88s por query). Fix en **8 services** con 2 patrones validados: (A) `EXISTS` contra wells_attributes cuando NO hay filtros de jerarquía (`kpis_operacionales` ×4 — 360×); (B) CTE prefiltro `MATERIALIZED` (hecho base + wa + where_sql íntegro adentro; hechos secundarios fuera por PK) en kpis_financieros, utilidades_service, services_costos_usdbl, waterfall_service, detalle_ingresos, ebitda_rank ×2, regression (270×). EXISTS con jerarquía PROHIBIDO (9.275/13.450 uwis con jerarquía inconsistente — rompería semántica). Gate de paridad con **tolerancia calibrada** `abs(a-b) <= max(1e-9*max(\|a\|,\|b\|), 0.01)` (tolerancia 0 en SUM de float8 es imposible al cambiar el plan — orden de suma IEEE754; lección guardada en memoria). Verificado: QO 462.503 / QW 9.598.431 idénticos a la UI pre-F20. Plan: `Planes/plan_F20_perf_distinct_on_2026-06-11.md`. | `kpis_operacionales/services.py`, `kpis_financieros/services.py`, `kpis_financieros/utilidades_service.py`, `kpis_costos/services_costos_usdbl.py`, `kpis_financieros/waterfall_service.py`, `detalle_ingresos/services.py`, `ebitda_rank/services.py`, `regression/services.py` | 1bd2734 |
| 2026-06-11 | F21-waterfall-utilidades | **2 waterfalls nuevos (Utilidades KUSD + USD/Bl):** puente contable EBITDA → Amortización → Depreciación → Impuestos Costos y Gastos → Impairment → UTILIDAD OPERATIVA → Impuesto de renta → Financieros netos → Diferencia en cambio → UTILIDAD NETA (11 barras). **Backend:** `waterfall_utilidades_service.py` (CTE F20, signos: amortiz/deprec/imp_cosgas/impair positivos en BD → se niegan; imp_renta/finan_netos/dif_en_cambio ya como efecto con signo → tal cual; totales SIEMPRE de columnas BD), campo `type` en `waterfall_schemas.py`, endpoint `GET /kpis/utilidades-waterfall` en `api.py`. **Frontend:** `utilidadesWaterfallService` + `useUtilidadesWaterfallData`; `inspectorUiStore` gana `activeChart`; `InspectorRail` pasa de 2 a **4 paneles** (`CHART_PANELS` fuente única en `chartPanels.tsx`); `InspectorSidebar` con `pctBase`/`pctBaseLabel` dinámicos ("de los ingresos" / "de la utilidad neta"); reset H3 de `selectedKey` al cambiar de gráfico. Smoke verificado: EBITDA 1.797.083,27 / UO 1.333.984,13 / UN 392.669,69 KUSD; 33,63/24,96/7,35 USD/Bl; Dif. en cambio +21.487 hacia arriba. Residual contable del puente documentado (−36,6 MKUSD tramo UO / −55,3 tramo UN — dato fuente, reportar al dueño del Excel). Plan: `Planes/plan_F21_waterfall_utilidades_2026-06-11.md`. ⏳ PENDIENTE validación humana. | `waterfall_utilidades_service.py`, `waterfall_schemas.py`, `kpis_financieros/api.py`, `utilidadesWaterfallService.ts`, `useUtilidadesWaterfallData.ts`, `inspectorUiStore.ts`, `InspectorRail/`, `chartPanels.tsx`, `InspectorSidebar.tsx`, `EbitdaInspectorCard.tsx` | 1e98d40 |
| 2026-06-11 | F21b-waterfall-visual | **Pulido visual de los 4 waterfalls:** (1) `wrapLabel` — ticks X multilínea (≤12 chars/renglón, `<br>` Plotly) + fuente 10px. (2) Data labels reducidos a 10px para que quepan en las barras. (3) **Fix Ampliar/Reducir**: Plotly solo escucha resize de la VENTANA → `ResizeObserver` sobre el contenedor + `Plots.resize(gd)` (tipado local `plotlyRuntime` porque plotly.js-dist-min no trae tipos). (4) **Hover tooltip card** arriba-derecha dentro del card: dot color (lima total / navy delta) + nombre de serie + valor con `formatBarValue` compartido con los data labels; mismo ciclo de vida que la línea punteada vertical (`clearHover` en mouseleave/fuera de rango); early-exit por barra con `lastHoverIdx` ref. (5) Dots de unidad del `InspectorHeader` eliminados (obsoletos con 4 gráficos). (6) Tooltip de `StackedBarChart` (detalle_costos) reposicionado `top:8px; right:16px` dentro del card. | `WaterfallChart.tsx`, `WaterfallChart.module.scss`, `InspectorHeader.tsx`, `InspectorHeader.module.scss`, `detalle_costos/.../StackedBarChart.module.scss` | pendiente |
| 2026-06-11/12 | F21c-waterfall-mobile | **Vista móvil del waterfall (≤1023px) según spec `mobi_waterfall.md`:** (1) `ChartPillsMobile` nuevo (dots role=tablist + pills scrollables bajo el gráfico, activa ámbar, opera sobre `inspectorUiStore`, placeholders SCSS `%dot-base`/`%pill-base`, `prefers-reduced-motion`). (2) Navegación cíclica de los 4 paneles: **swipe** táctil sobre `chartArea` (umbral 48px) + **flechas** `ChevronLeft/Right` circulares 30px absolutas (hit-area 44px vía `::before`) con `goRelative(±1)`. (3) Ticks X **abreviados** (`abbreviateLabel`: stopwords de/en/y; multi-palabra → `X.Yyy`; >6 chars → 4+'.'). (4) Data labels ocultos en móvil (`textposition:'none'`); fuentes ejes 8px, título Y 9px. (5) Header oculto (Ampliar era no-op en móvil) — fix layout `flex-direction: column` en `.chartArea` (pills aplastaban el gráfico). (6) 3 rondas de proporciones con el usuario: tarjeta lateral compacta `max-height` 210→**110px** (scroll interno profundo, paddings/tipografías a la mitad), chart `min-height` 280→340→**400px`, padding página `12px 12px 80px` (reserva FilterBar colapsada 130→96→80). Stylelint ✅ typecheck ✅ ESLint ✅. ⏳ PENDIENTE validación humana en dispositivo. | `ChartPillsMobile/` (nuevo: .tsx, .module.scss, index.ts), `EbitdaInspectorCard.tsx`, `EbitdaInspectorCard.module.scss`, `WaterfallChart.tsx`, `WaterfallChart.module.scss`, `InspectorHeader.module.scss`, `InspectorSidebar.module.scss`, `EbitdaCostosPage.module.scss` | pendiente |
| 2026-06-12 | DOC-estado-s6 | **Actualización estado S6 completo:** reanudación de contexto tras compactación — reporte final F21 (commit `1e98d40` verificado: 12 archivos, 861 inserciones). CLAUDE.md §6 sprint actualizado con tabla de commits b784445/1bd2734/1e98d40, sección "Pendiente antes de ebitda_costos" eliminada (obsoleta — ebitda_costos es operativo). §8 "Datos": contador bitácora 38→39. §19: entrada DOC añadida. Bitácora DB semana 6: entrada 39 insertada. Estado del proyecto al cierre de sesión: 3 commits S6 + 13 features frontend operativas + 15 módulos backend. | `CLAUDE.md`, `robustez_v02_backend/data/bitacora.db` | — |
| 2026-06-12 | F22-mook-evaluacion | **Feature Mook - Evaluación (mock):** `MookEvaluacionPage` (`/mook-evaluacion`) con layout sidebar + `BeneficiosTable` (header 2 niveles Plan azul/Real lima, 5 filas CAS46-CAS50, badges por estado, chips contexto) + grid 2 charts SVG. `RegresionChart`: subcomponente `RegresionSvg` con refs propios por instancia; marcadores X₁/X₂ con `getPointAtLength`/`getTotalLength`. `DeltaEbitdaChart`: subcomponente `DeltaEbitdaSvg({ patternId })` para evitar `id="mook-hatch"` duplicado card+modal. `MockChartModal`: `<dialog>` nativo, `showModal()`. Paleta local `_palette.scss` `$mk-*`. `formatMiles` separador U+2009. Datos 100% mock. `nav.config.ts`: item mook (`AlertTriangle`, `accent:'warning'`). `breadcrumbConfig.ts`, `router.tsx`, `LayoutMain.tsx` (drawer, sin ticker). Plan: `Planes/plan_F22_mook_evaluacion_2026-06-12.md`. ✅ Validado en navegador (V1-V4). | `features/mook_evaluacion/` (completo), `nav.config.ts`, `breadcrumbConfig.ts`, `router.tsx`, `LayoutMain.tsx` | pendiente commit |
| 2026-06-12 | F22b-modal-ampliar | **Fix modal Ampliar (StrictMode race condition):** botones "Ampliar" de `RegresionChart` y `DeltaEbitdaChart` parecían no funcionar — el modal se abría y cerraba instantáneamente. Causa raíz: `dialog.close()` en cleanup del `useEffect` encola un evento `'close'` asíncrono; bajo StrictMode (doble mount) el evento llega cuando el segundo efecto ya tiene el listener activo → `onClose()` → `setExpanded(false)` → componente desmontado. Fix: eliminar completamente `dialog.close()` del cleanup (solo `removeEventListener`). **Mismo bug latente** en `ChartModal` de `ebitda_rank` y `regresiones` (pendiente fix). | `features/mook_evaluacion/components/MockChartModal/MockChartModal.tsx` | pendiente commit |
| 2026-06-15 | F16b-nav-descriptions | **Tarjetas hover de descripción en panel de navegación:** `AppEntry.description?: string` añadido a `navigation.ts`. `AppMenuPopover.tsx`: zona derecha del grid alterna `SubViewGrid` (apps con subs) / `<div.descCard>` (apps con `description` sin subs). Popover ampliado `460→560px`, columna derecha `130→210px`. Clase `.descCard` (flex center, 12.5px, borde `#d9e1ea`). Textos: Utilidad Neta (cascada EBITDA interactiva), Predicción (regresión simple/multivariable), EBITDA Rank (curva rentabilidad + mapa), Mook (propuesta evaluación pozos). `AppPill.tsx`: prop `accent?:'warning'` + clase `.pillWarning` (bg `#fffbeb`, border `#f0e2b6`). | `navigation.ts`, `nav.config.ts`, `AppMenuPopover.tsx`, `AppMenuPopover.module.scss`, `AppPill.tsx` | pendiente commit |
| 2026-06-15 | FIX-drawer-mobile | **Fix Drawer tapado en mobile:** `Drawer.module.scss` `@media ≤1023px` — `top: 0 → top: var(--header-h, 61px)`. Bug: el `LayoutMain` coloca el Header con `z-index: 100`; el drawer tiene `z-index: 56`. Con `top: 0` el drawer empezaba en el borde superior de la pantalla, pero el Header (más alto en el z-stack) tapaba visualmente el header del drawer con el botón X, dejando al usuario sin poder cerrar los filtros en móvil. | `shared/components/Drawer/Drawer.module.scss` | pendiente commit |
| 2026-06-15 | DOC-bitacora-s6 | **Actualización estado S6 al 2026-06-15:** CLAUDE.md §8 fecha, Mook/Drawer/NavDescriptions añadidos a tabla Frontend, Datos bitácora 39→41. §19 entradas F22/F22b/F16b/FIX-drawer añadidas. Bitácora DB entradas 40-41 insertadas. Total proyecto: 14 features frontend operativas (inc. Mook) + 15 módulos backend + 3 commits S6. | `CLAUDE.md`, `robustez_v02_backend/data/bitacora.db` | — |
| 2026-06-15 | F22b-ejecucion | **Ejecución plan F22b (modal Ampliar Mook):** Se ejecutó el plan `plan_F22b_ampliar_modal_mook_2026-06-12.md` v2 (hallazgos H-A..H-F integrados). **Creados:** `MockChartModal/MockChartModal.tsx` (`<dialog>` nativo + `showModal()` + backdrop + Esc nativo; min(1100px,94vw) × min(760px,92dvh)) + `MockChartModal.module.scss`. **Modificados:** `MockCardHeader.tsx` (`expandable?:boolean` → `onExpand?:()=>void` + `aria-haspopup=dialog`); `RegresionChart.tsx` (subcomp `RegresionSvg` con refs + `useLayoutEffect` propios por instancia — H-B); `DeltaEbitdaChart.tsx` (subcomp `DeltaEbitdaSvg({ patternId })` — H-A: card usa `"mook-hatch"`, modal usa `"mook-hatch-modal"`). Fix StrictMode documentado en el componente: NO `dialog.close()` en cleanup — encola evento `close` asíncrono que bajo doble-mount dispara `onClose()` instantáneamente; cleanup solo `removeEventListener` (H-C). `closeModal` con `useCallback` para estabilizar deps del `useEffect` del modal (H-F). V1 tsc ✅ V2 ESLint (max-warnings 0) ✅ V3 Stylelint ✅ V4 Prettier ✅. PENDIENTE validación humana en navegador. | `components/MockChartModal/MockChartModal.tsx`, `MockChartModal.module.scss`, `MockCardHeader.tsx`, `RegresionChart.tsx`, `DeltaEbitdaChart.tsx` | pendiente commit |
| 2026-06-15 | DOC-s6-f22b | **Actualización CLAUDE.md + bitácora post F22b:** §3 árbol `mook_evaluacion/` añadido (faltaba por omisión). §8 Datos bitácora 41→42. §19 entrada F22b-ejecucion añadida. Bitácora DB entrada 42 insertada. Estado: 15 features frontend operativas (Mook con Ampliar funcional) + 15 módulos backend. | `CLAUDE.md`, `robustez_v02_backend/data/bitacora.db` | — |
| 2026-06-16/17 | DEPLOY-servidor | **Despliegue en servidor `10.100.26.139`:** Puertos unificados 6023 (front) + 6024 (back) para dev local y servidor. Plan auditado con 10 hallazgos (H1-H10): `apiClient.ts` safe (baseUrl relativo), cookie Secure vs HTTPS, test CORS genérico, CORS dual origins. 9 archivos modificados: `package.json` raíz, `vite.config.ts` (+ lectura env vars `VITE_PORT`/`VITE_BACKEND_PORT`), `config.py`, `.env.example`, `Start_Back.bat`, `Start_Front.bat`, `frontend/package.json`, `test_config_db.py`. `tmp_check_v01.py` eliminado (credenciales). Perfiles `.env.dev` y `.env.server` creados. Script `make_deploy_zip.ps1` para generar zip sin `.git`/`node_modules`/`.venv` (~791 MB). Deploy verificado: app operativa en `http://10.100.26.139:6023`. Prerequisitos servidor: Node.js 24.13 + pnpm 10.33 + Python 3.14 + uv. CLAUDE.md §11.1 documenta procedimiento completo. | `vite.config.ts`, `config.py`, `.env.example`, `.env.dev`, `.env.server`, `Start_Back.bat`, `Start_Front.bat`, `package.json` (raíz + frontend), `test_config_db.py`, `make_deploy_zip.ps1`, `CLAUDE.md` | pendiente commit |
| 2026-06-17 | DOC-deploy-executor | **Ejecución plan DEPLOY + actualización CLAUDE.md:** Executor corrió los 9 pasos del plan `plan_DEPLOY_puertos_servidor_2026-06-16.md` — V1-V9 ejecutadas. V6 (ruff): 3 errores I001 pre-existentes en `scripts/` (no causados por el plan; `src/` y `tests/` limpios). V7 (pytest): 6 PASSED — exit 1 por threshold de coverage 75% (DT-9 pre-existente, no nuevo). Actualización CLAUDE.md: §11 puertos `:8000`/`:5173`→`:6024`/`:6023`; §17 DT-10 marcada resuelta; §8 bitácora 42→43; §19 entrada añadida. Bitácora DB entrada 43 insertada. | `CLAUDE.md`, `robustez_v02_backend/data/bitacora.db` | — |
| 2026-06-17 | F23-well-condition-criterio | **F23 WellCondition parametrizado por criterio:** Backend: `classify_well()` acepta `criterio` (ebitda/util_oper/util_neta) con umbrales diferenciados (ebitda: 3 categorías rentable/marginal/no_rentable, util_oper/util_neta: 2 categorías rentable/no_rentable). `resolve_columns()` expandido a 12 variantes (3 criterios × 4 combos estado×produccion). `ebitda_rank/services.py` pasa `criterio` al query. Frontend: `CurvasWaffle` (multi-select 7 curvas con `WaffleTile` genérico Eye/EyeOff + "Todas"/"Ninguna" + contador), `curvesDef.ts`, `useVisibleCurves`. `CondicionWaffle` v1 (dropdown). `EbitdaRankPage` integra `criterio` state + chips filtrados por criterio. Types: `ConditionCriterio` union type. | `shared/well_condition.py`, `ebitda_rank/services.py`, `ebitda_rank/components/CurvasWaffle/`, `ebitda_rank/components/CondicionWaffle/`, `ebitda_rank/pages/EbitdaRankPage.tsx`, `ebitda_rank/types/wellCondition.ts` | pendiente commit |
| 2026-06-17 | F23b-condicion-waffle-tiles | **F23b CondicionWaffle tiles:** Reescritura de dropdown a grid waffle tiles (patrón CurvasWaffle). 3 tiles single-select: EBITDA/Bl (`#0A1F33` Coins), U. Operativa/Bl (`#8B5CF6` Gauge), U. Neta/Bl (`#0EA5E9` Wallet). CSS var `--cond-color` (no `--curve-color`). Check ✓ en tile activo. Click selecciona y cierra popover. H1: `box-shadow 0.14s` en transitions del `.tile`. H3: `grid-template-columns: 1fr` en mobile ≤1023px. `prefers-reduced-motion` respetado. Plan v2 auditado: `plan_F23b_condicion_waffle_tiles_2026-06-17.md`. Executor verificado: V1-V4 ✅. ⏳ V5 validación humana en navegador. | `CondicionWaffle.tsx`, `CondicionWaffle.module.scss` | pendiente commit |
| 2026-06-17 | DOC-bitacora-f23 | **Actualización CLAUDE.md + bitácora post F23/F23b:** §3 árbol ebitda_rank actualizado (CurvasWaffle + CondicionWaffle + types). §6 ebitda_rank operativo ampliado. §8 Backend EBITDA Rank + Frontend F8 actualizados con F23/F23b. Datos bitácora 43→44. §19 entradas F23/F23b añadidas. Bitácora DB entrada 44 insertada. Estado: 15 features frontend + 15 módulos backend. | `CLAUDE.md`, `robustez_v02_backend/data/bitacora.db` | — |
| 2026-06-17 | DOC-bitacora-f23b | **Actualización CLAUDE.md + bitácora cierre sesión F23b:** §6 commit pendiente actualizado (+F23+F23b). §8 Datos bitácora 44→45. §8 Pendiente commit acumulado actualizado (~80 archivos, añadidos F23+F23b). §19 entrada añadida. Bitácora DB entrada 45 insertada. Estado final sesión: F23b V1-V4 ✅ (tsc/eslint/stylelint/prettier), V5 pendiente validación humana en navegador `/ebitda-rank`. | `CLAUDE.md`, `robustez_v02_backend/data/bitacora.db` | — |

---

## 20. Skill: Auditoría de Migración (`auditoria:`)

### Activación

Cuando el usuario escriba `<componente> auditoria:` (ej: `EBITDA KUSD auditoria:`, `Waterfall auditoria:`), Claude Code ejecuta los 5 pasos de auditoría sobre el proyecto V01 de producción.

### Fuente de verdad

**Proyecto V01 producción:** `E:\APLICACIONES\Robustez\Prod_rbt_20052026`

### Los 5 pasos obligatorios

| # | Paso | Qué hacer |
|---|------|-----------|
| **1** | **Tabla(s) y campos fuente** | Identificar en el proyecto V01 (`Prod_rbt_20052026`) qué tabla(s) y columnas alimentan el componente. Leer el código Python/SQL que genera los datos. Mostrar nombre de tabla, columnas usadas y tipo de dato. |
| **2** | **Lógica de cálculo (memoria de cálculo)** | Documentar la fórmula exacta: operaciones matemáticas, agregaciones (SUM, AVG, COUNT), divisiones, redondeos, formateo. Incluir pseudocódigo o la expresión SQL/Python literal del V01. |
| **3** | **Lógica de filtrado** | Documentar qué filtros afectan el resultado: vicepresidencia, gerencia, activo, campo, UWI, período (año/mes), estado pozo, tipo producción, u otros. Mostrar los WHERE/IF del código V01. |
| **4** | **Mapeo campos SQLite V01 → PostgreSQL V02** | Tabla de correspondencia columna por columna: nombre V01 (SQLite `ROBUSTEZ.db`) → nombre V02 (PostgreSQL `ops.*`). Marcar columnas sin equivalente o con transformación requerida. |
| **5** | **Verificación de paridad de datos (conteos y agregados)** | Comparar conteos de filas, UWIs distintos y agregados clave (SUM, COUNT DISTINCT) entre V01 SQLite y V02 PostgreSQL para el mismo filtro de prueba (ej: CHICHIMENE 2025 Activos Real). Ejecutar las siguientes verificaciones obligatorias: **(a) Filas duplicadas en tablas de hechos:** verificar si `ops.flow_rates`, `ops.financial_results`, `ops.operating_costs` tienen filas repetidas para la misma PK lógica (UWI+año+mes+estado+pend_id_cc). **(b) Filas duplicadas en tablas de dimensiones:** verificar si `ops.wells_attributes` tiene UWIs duplicados — esto es crítico porque un JOIN contra una dimensión con N copias **multiplica silenciosamente** cada fila de hechos ×N, inflando SUMs sin generar error SQL. **Lección F6.1:** `wells_attributes` tenía UWIs con 2-4 copias (ej: CHIC0002 ×4). El `JOIN flow_rates × wells_attributes` multiplicó la producción → QO V02=55,873 vs V01=38,120 (+46%). Con `DISTINCT ON` para deduplicar: QO=37,982 (-0.4% de V01). **(c) Filtros de negocio implícitos:** V01 puede excluir registros por condiciones no obvias (ej: `EBITDA != 0 AND Total Bls Mezcla != 0` para conteo de pozos — V02 mostraba 213 pozos vs V01 153). **(d) Doble estado por pozo/mes:** verificar si un mismo UWI tiene filas ACT e INACT en el mismo mes (V01 tiene una sola fila por UWI+mes+estado; si V02 tiene ambos, el SUM se infla). Si hay discrepancias, documentar causa raíz, impacto numérico y solución (deduplicar seeds vs ajustar query). |

### Formato de salida

Mostrar los 5 puntos por pantalla en formato tabla/código, listos para ser usados como insumo del plan de migración del componente.

### Reglas

- **Solo auditar, NO implementar.** Cero archivos creados. Cero ediciones a código V02.
- Si un campo V01 no tiene equivalente en V02, marcarlo como 🔴 **SIN MAPEO** y avisar.
- Si la lógica de cálculo es ambigua o tiene variantes (ej: Real vs Tasa), documentar TODAS las variantes.
- La auditoría se completa cuando los 5 puntos están documentados. El usuario decide el siguiente paso.

---

## 21. Patrón: Tooltip custom + línea punteada vertical en charts Plotly

> Implementado en `StackedBarChart` (F15 — 2026-06-05). Replicable en cualquier chart Plotly que use `createPlotlyComponent`.

### Por qué NO se usa el hover nativo de Plotly

`createPlotlyComponent(PlotlyLib)` desconecta los callbacks de `react-plotly.js` (`onHover`, `onUnhover`, `onAfterPlot`, `el.on('plotly_hover')`). Ninguno dispara. Ver F15 `tooltip-custom` en §19. Por eso se usa **`onMouseMove` nativo** sobre el `div` contenedor.

### Prerrequisito de layout

```
hovermode: false   ← desactiva el tooltip nativo de Plotly (evita doble tooltip)
margin: { l: N, r: M, t: T, b: B }   ← debe coincidir con MARGIN_LEFT / MARGIN_RIGHT / MARGIN_BOTTOM en el componente
```

### Arquitectura del componente

```
<div.container  position:relative  ref={containerRef}
                onMouseMove={handleMouseMove}
                onMouseLeave={() => { setHover(null); setVLineX(null); }}>

  {vLineX !== null && <div.vLine  style={{ left: vLineX }} />}   ← línea punteada
  {hover && <div.tooltipCard>...</div.tooltipCard>}               ← tarjeta tooltip
  <Plot ... />                                                     ← Plotly
</div>
```

**Regla de orden DOM:** `vLine` y `tooltipCard` van ANTES de `<Plot>` para que el z-index funcione sin conflictos con el SVG interno de Plotly.

### Estado

```tsx
const [hover,  setHover]  = useState<HoverInfo | null>(null);  // datos del tooltip
const [vLineX, setVLineX] = useState<number | null>(null);     // px desde left del container
const containerRef = useRef<HTMLDivElement>(null);
```

### Cálculo de posición (handleMouseMove)

```tsx
const MARGIN_LEFT  = 52;   // debe coincidir con layout.margin.l
const MARGIN_RIGHT = 16;   // debe coincidir con layout.margin.r

const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
  const rect = containerRef.current?.getBoundingClientRect();
  if (!rect || labels.length === 0) return;

  const plotWidth = rect.width - MARGIN_LEFT - MARGIN_RIGHT;  // ancho del área de datos
  const x = e.clientX - rect.left - MARGIN_LEFT;             // x relativo al área de datos

  if (x < 0 || x > plotWidth) { setHover(null); return; }

  const barWidth = plotWidth / labels.length;                 // ancho de cada columna
  const idx = Math.floor(x / barWidth);                      // índice de la columna hovereada
  if (idx < 0 || idx >= labels.length) { setHover(null); return; }

  // Centro de la barra en coordenadas del container
  setVLineX(MARGIN_LEFT + (idx + 0.5) * barWidth);

  // Construir datos del tooltip para el índice idx
  const month = labels[idx] ?? '';
  const rawItems = series.map((s) => ({ label: s.label, color: s.color, raw: s.values[idx] ?? 0 }));
  const total = rawItems.reduce((sum, it) => sum + it.raw, 0);
  const items = rawItems
    .sort((a, b) => b.raw - a.raw)              // orden descendente por valor
    .map((it) => ({
      label: it.label,
      color: it.color,
      value: fmtKusd(it.raw),
      pct: total > 0
        ? `${((it.raw / total) * 100).toLocaleString('es-CO', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`
        : '—',
    }));
  setHover({ month, items });
}, [labels, series]);
```

**Clave del cálculo:** Plotly divide el área de datos uniformemente entre las N columnas. El centro de la columna `idx` está en `MARGIN_LEFT + (idx + 0.5) * barWidth` píxeles desde el borde izquierdo del contenedor.

### SCSS — línea punteada

```scss
.container {
  position: relative;   /* ← obligatorio para que absolute de hijos funcione */
  /* ... resto de props */
}

.vLine {
  position: absolute;
  top: 0;
  bottom: 36px;         /* debe coincidir con layout.margin.b para no pisar el eje X */
  width: 0;
  border-left: 1.5px dashed #6b7a8a;
  pointer-events: none; /* no intercepta clicks ni mouse events */
  z-index: 10;
}
```

### SCSS — tarjeta tooltip

```scss
.tooltipCard {
  position: absolute;
  top: -100px;          /* sube la tarjeta 100px por encima del área del chart */
  left: 50%;
  transform: translateX(-50%);   /* centrado horizontal relativo al container */
  z-index: 100;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 10px 14px;
  box-shadow: 0 2px 8px rgb(0 0 0 / 0.1);
  pointer-events: none; /* no interfiere con onMouseMove del container */
  min-width: 200px;
}
/* Fila por serie: dot + label + value (pct) */
.tooltipRow   { display: flex; align-items: center; gap: 6px; padding: 2px 0; }
.tooltipDot   { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.tooltipLabel { flex: 1; color: #374151; white-space: nowrap; }
.tooltipValue { font-weight: 600; color: #1a1a2e; font-variant-numeric: tabular-nums; white-space: nowrap; }
.tooltipPct   { font-weight: 400; color: #6b7a8a; font-size: 11px; }
```

**Importante:** el contenedor padre de `.tooltipCard` debe tener `overflow: visible` (no `hidden`) para que la tarjeta pueda salir por encima del borde. En `CostosGastosCard.module.scss` se cambió `.card { overflow: hidden → visible }` por este motivo.

### Estructura de datos del tooltip

```tsx
interface HoverInfo {
  month: string;                                           // label del eje X (ej: "May")
  items: {
    label: string;   // nombre de la serie
    color: string;   // color hex para el dot
    value: string;   // valor formateado "$3.604,3"
    pct:   string;   // porcentaje del total "30,1%"
  }[];               // ordenado de mayor a menor valor
}
```

### Cómo replicar en otro chart Plotly

1. Añadir `position: relative` al div contenedor.
2. Declarar `MARGIN_LEFT` / `MARGIN_RIGHT` iguales a `layout.margin.l` / `layout.margin.r`.
3. Copiar `useState<HoverInfo | null>` + `useState<number | null>` + `useRef`.
4. Copiar `handleMouseMove` ajustando `labels` y `series` al shape de datos del chart.
5. Añadir `onMouseMove={handleMouseMove}` + `onMouseLeave` al contenedor.
6. Renderizar `<div.vLine style={{ left: vLineX }}>` y `<div.tooltipCard>` antes del `<Plot>`.
7. Ajustar `bottom` de `.vLine` para que coincida con `layout.margin.b`.
8. Ajustar `top` de `.tooltipCard` según el espacio disponible encima del chart.
9. Verificar que `hovermode: false` esté en el layout de Plotly.
10. Verificar que el padre no tenga `overflow: hidden`.

### Limitación conocida

El cálculo asume que Plotly divide el eje X uniformemente (válido para bar charts y series con el mismo dominio temporal). Para scatter plots o series con x irregulares, el cálculo de `idx` debe adaptarse usando la escala real del eje (requiere acceder a `gd._fullLayout.xaxis` via ref Plotly).
