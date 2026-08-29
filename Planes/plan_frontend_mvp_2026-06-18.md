# Plan EXECUTOR — Frontend MVP (React 19 + Vite + TS) sobre la API existente

> **Versión:** v2 (re-auditada contra TS estricto + template Vite 7/React 19; correcciones F1–F5 en §11)
> **Fecha:** 2026-06-18
> **Autocontenido.** El agente EXECUTOR no tiene contexto previo: ejecuta al pie de la letra, en orden.

---

## 1. Contexto

`Robustez V2.0` (ingesta de reportes Excel `.xlsm` de producción Ecopetrol a PostgreSQL) tiene un
**backend FastAPI funcional** en `c:\Users\user\Documents\Rep_Prod\backend\` con estos endpoints
(formas JSON ya verificadas en el código):

| Endpoint | Respuesta |
|---|---|
| `GET /health` | `{"status":"ok"}` |
| `GET /ingesta/disponibles` | `[{nombre, tipo:'NEW'\|'STD', fecha:str\|null, ya_ingerido:bool}]` |
| `POST /ingesta/archivo` body `{nombre}` | `{archivo, reporte_id, tipo_archivo, tiene_raw, filas_por_tabla:{}}` |
| `POST /ingesta/jobs` body `{nombres?:string[]\|null}` | `{job_id, total}` |
| `GET /ingesta/jobs` | `[JobEstado]` |
| `GET /ingesta/jobs/{id}` | `JobEstado` = `{job_id, estado, total, procesados, errores, archivos?, resultado?, mensaje?, creado_at, actualizado_at}` |
| `GET /reportes` | `[{reporte_id, fecha_reporte, tipo_archivo, tiene_raw, nivel_detalle}]` |
| `GET /reportes/cobertura` | `[{reporte_id, tipo_archivo, ecp_mes, ecp_dia, filiales}]` |
| `GET /kpis-prod/produccion-dia?fecha=YYYY-MM-DD` | `[{tipo_producto, vol_estimado:number\|null}]` |

**No existe frontend.** Tampoco hay Node/npm en la máquina. El backend **no tiene CORS**.

## 2. Objetivo

Construir un **frontend MVP** alineado con el stack de la arquitectura (React 19 + Vite + TypeScript +
Bootstrap 5.3 + TanStack Query + Zustand), espejo del backend por features, con 3 páginas:

1. **Ingesta** (cockpit principal): tabla de `disponibles` (NEW/STD, ya_ingerido), disparar ingesta de
   uno o de un lote como **job**, y **barra de progreso en vivo** (polling de `GET /ingesta/jobs/{id}`)
   + historial de jobs.
2. **Reportes/Cobertura**: tabla de `GET /reportes/cobertura`.
3. **KPIs Producción**: input de fecha → `GET /kpis-prod/produccion-dia` → barras simples.

**Wiring:** dev con **proxy de Vite** (evita CORS); prod sirviendo `frontend/dist` desde **FastAPI**
(`StaticFiles`, mismo origen). El front llama **rutas relativas** (`/ingesta`, `/reportes`, …) en ambos.

## 3. Prerequisitos (verificar ANTES de empezar)

| # | Comando (PowerShell) | Esperado |
|---|---|---|
| P1 | `Test-Path 'c:\Users\user\Documents\Rep_Prod\backend\app\main.py'` | `True` |
| P2 | `cd 'c:\Users\user\Documents\Rep_Prod\backend'; uv run pytest -q` | tests en verde (baseline) |
| P3 | `(Get-Command winget -ErrorAction SilentlyContinue) -ne $null` | `True` (si `False`, ver §6.1 fallback) |
| P4 | API arranca: `uv run uvicorn app.main:app --port 8000` y `Invoke-RestMethod http://127.0.0.1:8000/ingesta/disponibles` | array de ≥30 items |

Herramientas: **`uv`** para el backend, **`npm`** (tras instalar Node) para el front. Comentarios y
textos de UI en **español**. Puerto API = **8000**, puerto Vite dev = **5173**.

## 4. Inventario de archivos

| Acción | Ruta |
|---|---|
| **INSTALAR** | Node.js LTS (toolchain) |
| **SCAFFOLD** | `c:\Users\user\Documents\Rep_Prod\frontend\` (Vite react-ts) |
| **REEMPLAZAR** | `frontend\vite.config.ts` |
| **REEMPLAZAR** | `frontend\src\main.tsx` |
| **REEMPLAZAR** | `frontend\src\App.tsx` |
| **CREAR** | `frontend\src\api\types.ts` |
| **CREAR** | `frontend\src\api\client.ts` |
| **CREAR** | `frontend\src\store.ts` |
| **CREAR** | `frontend\src\features\ingesta\hooks.ts` |
| **CREAR** | `frontend\src\features\ingesta\IngestaPage.tsx` |
| **CREAR** | `frontend\src\features\reportes\ReportesPage.tsx` |
| **CREAR** | `frontend\src\features\kpis_prod\KpisPage.tsx` |
| **REEMPLAZAR** | `backend\app\main.py` (CORS + StaticFiles) |
| **EDITAR (append)** | `c:\Users\user\Documents\Rep_Prod\.gitignore` |

❌ **NO tocar:** `etl/`, `data/`, `.env`, `CLAUDE.md`, `db/`, ni las features del backend salvo `main.py`.

## 5. Especificación (código de referencia COMPLETO)

### 5.1 `frontend/vite.config.ts` (REEMPLAZAR)
```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Proxy de DEV: el front llama rutas relativas (/ingesta, /reportes, /kpis-prod, /health) y Vite las
// reenvía al backend en :8000 → evita CORS. En PROD el front se sirve desde FastAPI (mismo origen).
// F1: objeto literal explícito (no Object.fromEntries) para no fallar `tsc -b` con tipos no-tupla.
const target = 'http://localhost:8000'
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/ingesta': { target, changeOrigin: true },
      '/reportes': { target, changeOrigin: true },
      '/kpis-prod': { target, changeOrigin: true },
      '/health': { target, changeOrigin: true },
    },
  },
})
```

### 5.2 `frontend/src/main.tsx` (REEMPLAZAR)
```tsx
// F2: named imports (StrictMode, createRoot) — alineado con el template React 19 y compatible con
// verbatimModuleSyntax que activa Vite 7/react-ts (los default imports darían fricción de build).
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import 'bootstrap/dist/css/bootstrap.min.css'
import App from './App'

const qc = new QueryClient({ defaultOptions: { queries: { refetchOnWindowFocus: false } } })

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={qc}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
```

### 5.3 `frontend/src/api/types.ts` (CREAR)
```ts
export interface ArchivoDisponible { nombre: string; tipo: 'NEW' | 'STD'; fecha: string | null; ya_ingerido: boolean }
export interface ResultadoIngesta { archivo: string; reporte_id: number; tipo_archivo: string; tiene_raw: boolean; filas_por_tabla: Record<string, number> }
export interface JobCreado { job_id: number; total: number }
export interface JobEstado {
  job_id: number
  estado: 'PENDIENTE' | 'EN_PROCESO' | 'COMPLETADO' | 'ERROR'
  total: number; procesados: number; errores: number
  archivos?: string[] | null
  resultado?: Record<string, unknown>[] | null
  mensaje?: string | null
  creado_at: string; actualizado_at: string
}
export interface Cobertura { reporte_id: number; tipo_archivo: string | null; ecp_mes: number; ecp_dia: number; filiales: number }
export interface KpiProduccionDia { tipo_producto: string; vol_estimado: number | null }
```

### 5.4 `frontend/src/api/client.ts` (CREAR)
```ts
import type { ArchivoDisponible, ResultadoIngesta, JobCreado, JobEstado, Cobertura, KpiProduccionDia } from './types'

async function http<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...init })
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`
    try { const j = await r.json(); msg = JSON.stringify(j.detail ?? j) } catch { /* sin body JSON */ }
    throw new Error(msg)
  }
  return r.json() as Promise<T>
}

export const api = {
  disponibles: () => http<ArchivoDisponible[]>('/ingesta/disponibles'),
  ingerirArchivo: (nombre: string) => http<ResultadoIngesta>('/ingesta/archivo', { method: 'POST', body: JSON.stringify({ nombre }) }),
  crearJob: (nombres?: string[]) => http<JobCreado>('/ingesta/jobs', { method: 'POST', body: JSON.stringify({ nombres: nombres ?? null }) }),
  listarJobs: () => http<JobEstado[]>('/ingesta/jobs'),
  estadoJob: (id: number) => http<JobEstado>(`/ingesta/jobs/${id}`),
  cobertura: () => http<Cobertura[]>('/reportes/cobertura'),
  produccionDia: (fecha: string) => http<KpiProduccionDia[]>(`/kpis-prod/produccion-dia?fecha=${fecha}`),
}
```

### 5.5 `frontend/src/store.ts` (CREAR)
```ts
import { create } from 'zustand'

type Tab = 'ingesta' | 'reportes' | 'kpis'
interface UI { tab: Tab; jobActivo: number | null; setTab: (t: Tab) => void; setJob: (id: number | null) => void }

export const useUI = create<UI>((set) => ({
  tab: 'ingesta',
  jobActivo: null,
  setTab: (tab) => set({ tab }),
  setJob: (jobActivo) => set({ jobActivo }),
}))
```

### 5.6 `frontend/src/App.tsx` (REEMPLAZAR)
```tsx
import { useUI } from './store'
import IngestaPage from './features/ingesta/IngestaPage'
import ReportesPage from './features/reportes/ReportesPage'
import KpisPage from './features/kpis_prod/KpisPage'

const TABS = [
  { id: 'ingesta', label: 'Ingesta' },
  { id: 'reportes', label: 'Reportes' },
  { id: 'kpis', label: 'KPIs Producción' },
] as const

export default function App() {
  const { tab, setTab } = useUI()
  return (
    <div className="container-fluid py-3">
      <header className="d-flex align-items-center mb-3">
        <h4 className="me-4 mb-0">Robustez V2.0 — Ingesta</h4>
        <ul className="nav nav-pills">
          {TABS.map((t) => (
            <li className="nav-item" key={t.id}>
              <button className={`nav-link ${tab === t.id ? 'active' : ''}`} onClick={() => setTab(t.id)}>{t.label}</button>
            </li>
          ))}
        </ul>
      </header>
      {tab === 'ingesta' && <IngestaPage />}
      {tab === 'reportes' && <ReportesPage />}
      {tab === 'kpis' && <KpisPage />}
    </div>
  )
}
```

### 5.7 `frontend/src/features/ingesta/hooks.ts` (CREAR)
```ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/client'

export const useDisponibles = () => useQuery({ queryKey: ['disponibles'], queryFn: api.disponibles })
export const useJobs = () => useQuery({ queryKey: ['jobs'], queryFn: api.listarJobs, refetchInterval: 4000 })

export function useJob(id: number | null) {
  return useQuery({
    queryKey: ['job', id],
    queryFn: () => api.estadoJob(id as number),
    enabled: id != null,
    // Polling hasta que el job termine; luego deja de refrescar.
    refetchInterval: (q) => {
      const e = q.state.data?.estado
      return e === 'COMPLETADO' || e === 'ERROR' ? false : 1500
    },
  })
}

export function useLanzarJob() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (nombres?: string[]) => api.crearJob(nombres),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['jobs'] }) },
  })
}
```

### 5.8 `frontend/src/features/ingesta/IngestaPage.tsx` (CREAR)
```tsx
import { useState } from 'react'
import { useDisponibles, useJob, useJobs, useLanzarJob } from './hooks'
import { useUI } from '../../store'

export default function IngestaPage() {
  const disp = useDisponibles()
  const jobs = useJobs()
  const lanzar = useLanzarJob()
  const { jobActivo, setJob } = useUI()
  const job = useJob(jobActivo)
  const [sel, setSel] = useState<Set<string>>(new Set())

  const toggle = (n: string) =>
    setSel((s) => { const x = new Set(s); x.has(n) ? x.delete(n) : x.add(n); return x })

  async function lanzarJob(todos: boolean) {
    const nombres = todos ? undefined : [...sel]
    if (!todos && nombres!.length === 0) return
    const r = await lanzar.mutateAsync(nombres)
    setJob(r.job_id)
  }

  if (disp.isLoading) return <p>Cargando archivos…</p>
  if (disp.error) return <div className="alert alert-danger">Error: {String(disp.error)}</div>

  return (
    <div className="row g-3">
      <div className="col-lg-8">
        <div className="d-flex gap-2 mb-2">
          <button className="btn btn-primary btn-sm" disabled={lanzar.isPending || sel.size === 0} onClick={() => lanzarJob(false)}>
            Ingerir seleccionados ({sel.size})
          </button>
          <button className="btn btn-outline-secondary btn-sm" disabled={lanzar.isPending} onClick={() => lanzarJob(true)}>
            Ingerir todos
          </button>
        </div>
        <table className="table table-sm table-hover align-middle">
          <thead><tr><th></th><th>Archivo</th><th>Tipo</th><th>Fecha</th><th>Ingerido</th></tr></thead>
          <tbody>
            {disp.data!.map((a) => (
              <tr key={a.nombre}>
                <td><input type="checkbox" checked={sel.has(a.nombre)} onChange={() => toggle(a.nombre)} /></td>
                <td className="text-truncate" style={{ maxWidth: 360 }} title={a.nombre}>{a.nombre}</td>
                <td><span className={`badge ${a.tipo === 'NEW' ? 'bg-success' : 'bg-secondary'}`}>{a.tipo}</span></td>
                <td>{a.fecha ?? '—'}</td>
                <td>{a.ya_ingerido ? '✓' : ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="col-lg-4">
        <h6>Progreso del job</h6>
        {job.data ? (
          <div className="card card-body">
            <div>Job #{job.data.job_id} — <b>{job.data.estado}</b></div>
            <div className="progress my-2" style={{ height: 22 }}>
              <div className="progress-bar" style={{ width: `${(job.data.procesados / Math.max(job.data.total, 1)) * 100}%` }}>
                {job.data.procesados}/{job.data.total}
              </div>
            </div>
            {job.data.errores > 0 && <div className="text-danger">Errores: {job.data.errores}</div>}
          </div>
        ) : <p className="text-muted">Sin job activo.</p>}

        <h6 className="mt-3">Historial</h6>
        <ul className="list-group">
          {jobs.data?.slice(0, 8).map((j) => (
            <li key={j.job_id} className="list-group-item d-flex justify-content-between" role="button" onClick={() => setJob(j.job_id)}>
              <span>#{j.job_id}</span><span>{j.estado}</span><span>{j.procesados}/{j.total}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
```

### 5.9 `frontend/src/features/reportes/ReportesPage.tsx` (CREAR)
```tsx
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'

export default function ReportesPage() {
  const cob = useQuery({ queryKey: ['cobertura'], queryFn: api.cobertura })
  if (cob.isLoading) return <p>Cargando…</p>
  if (cob.error) return <div className="alert alert-danger">Error: {String(cob.error)}</div>
  return (
    <table className="table table-sm table-striped">
      <thead><tr><th>Reporte</th><th>Tipo</th><th>ECP mes</th><th>ECP día</th><th>Filiales</th></tr></thead>
      <tbody>
        {cob.data!.map((r) => (
          <tr key={r.reporte_id}>
            <td>{r.reporte_id}</td><td>{r.tipo_archivo ?? '—'}</td>
            <td>{r.ecp_mes}</td><td>{r.ecp_dia}</td><td>{r.filiales}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
```

### 5.10 `frontend/src/features/kpis_prod/KpisPage.tsx` (CREAR)
```tsx
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'

export default function KpisPage() {
  const [fecha, setFecha] = useState('2024-10-03')
  const k = useQuery({ queryKey: ['kpi-dia', fecha], queryFn: () => api.produccionDia(fecha), enabled: !!fecha })
  const max = Math.max(1, ...(k.data?.map((d) => d.vol_estimado ?? 0) ?? [0]))
  return (
    <div>
      <div className="mb-3">
        <label className="form-label">Fecha (YYYY-MM-DD)</label>
        <input className="form-control" style={{ maxWidth: 220 }} value={fecha} onChange={(e) => setFecha(e.target.value)} />
      </div>
      {k.isLoading && <p>Cargando…</p>}
      {k.error && <div className="alert alert-danger">Error: {String(k.error)}</div>}
      {k.data?.length === 0 && <p className="text-muted">Sin datos para esa fecha.</p>}
      {k.data?.map((d) => (
        <div key={d.tipo_producto} className="mb-2">
          <div className="d-flex justify-content-between"><span>{d.tipo_producto}</span><span>{(d.vol_estimado ?? 0).toLocaleString()}</span></div>
          <div className="progress" style={{ height: 20 }}>
            <div className="progress-bar bg-info" style={{ width: `${((d.vol_estimado ?? 0) / max) * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
  )
}
```

### 5.11 `backend/app/main.py` (REEMPLAZAR contenido completo)
```python
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.features.ingesta.api import router as ingesta_router
from app.features.reportes.api import router as reportes_router
from app.features.kpis_prod.api import router as kpis_prod_router

configure_logging()
app = FastAPI(title=get_settings().app_name)

# CORS solo para el dev server de Vite (mismo equipo). En prod el front se sirve aquí (mismo origen).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"], allow_headers=["*"],
)

app.include_router(ingesta_router)
app.include_router(reportes_router)
app.include_router(kpis_prod_router)

@app.get("/health")
def health():
    return {"status": "ok"}

# Servir el build del front (si existe) en el mismo origen. DEBE ir DESPUÉS de los routers para no
# tapar las rutas de la API. parents[2] = raíz del repo (backend/app/main.py -> backend -> raíz).
_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="frontend")
```

### 5.12 `.gitignore` (append al final)
```
# Frontend
frontend/node_modules/
frontend/dist/
```

## 6. Orden de ejecución

1. **Instalar Node LTS** y refrescar PATH en la sesión:
   ```powershell
   winget install OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements -e
   # refrescar PATH en la sesión actual (winget no lo propaga al proceso vivo):
   $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
   node --version; npm --version
   ```
   **Fallback si no hay `winget`:** instala `fnm` o descarga el MSI de https://nodejs.org (LTS) e
   instala; luego repite el refresco de PATH y verifica `node --version`. Si tras esto `node` no
   responde, **DETENTE y reporta** (sin Node no se puede construir el front).

2. **Scaffold Vite** (no interactivo) en la raíz del repo. **F4:** si `frontend/` ya existe,
   `create-vite` se vuelve interactivo (pide overwrite) → DETENTE y reporta en vez de continuar.
   ```powershell
   cd 'c:\Users\user\Documents\Rep_Prod'
   if (Test-Path '.\frontend') { Write-Error 'frontend/ ya existe — abortar (revisar antes de sobreescribir)'; exit 1 }
   npx --yes create-vite@latest frontend --template react-ts
   ```

3. **Instalar dependencias** del front:
   ```powershell
   cd 'c:\Users\user\Documents\Rep_Prod\frontend'
   npm install
   npm install bootstrap @tanstack/react-query zustand
   ```

4. **Crear/Reemplazar** los archivos del front §5.1–§5.10 con el contenido exacto.

5. **Reemplazar** `backend/app/main.py` §5.11.

6. **Append** a `.gitignore` §5.12.

7. **Build** del front:
   ```powershell
   cd 'c:\Users\user\Documents\Rep_Prod\frontend'; npm run build
   ```

8. Ejecutar **Validaciones** §7.

## 7. Validaciones (criterio de aceptación: comando → resultado esperado)

| # | Comando | Esperado |
|---|---|---|
| **VF1** | `node --version; npm --version` | Imprime versiones (Node ≥ 20) |
| **VF2** | `cd ...\frontend; npm run build` | Exit 0 (compila `tsc` + `vite build`) y `Test-Path ...\frontend\dist\index.html` = `True` |
| **VF3** | `cd ...\backend; uv run pytest -q` | Tests en verde (los edits de `main.py` no rompen nada) |
| **VF4** | Arrancar `uv run uvicorn app.main:app --port 8000`; `Invoke-WebRequest http://127.0.0.1:8000/ -UseBasicParsing` | HTML que contiene `id="root"` (FastAPI sirve el build) |
| **VF5** | (mismo server) `Invoke-RestMethod http://127.0.0.1:8000/ingesta/disponibles` | Array JSON (la API NO quedó tapada por el StaticFiles) |
| **VF6** | `(Get-Content ...\etl\ingesta_prototipo.py \| Measure-Object -Line).Lines` | 492 (ETL legacy intacto) |
| **VF7** *(manual, dev)* | Terminal A: `uv run uvicorn app.main:app --port 8000`. Terminal B: `cd frontend; npm run dev`. Abrir `http://localhost:5173` | Carga la UI; pestaña **Ingesta** lista 37 archivos; **F3:** seleccionar **UN archivo STD** (rápido, ~segundos) y "Ingerir seleccionados" crea un job y la barra avanza a COMPLETADO (vía proxy, sin error CORS). NO usar "Ingerir todos" aquí: dispararía los 16 NEW (~3–4 min c/u) |

Si **cualquier** validación automática (VF1–VF6) falla: **DETENTE**, reporta `❌ VFn` con el error
exacto, no improvises fuera del plan.

## 8. Reglas no negociables

1. **NO** tocar `etl/`, `data/`, `.env`, `CLAUDE.md`, `db/`, ni features del backend salvo `main.py`.
2. El front llama **rutas relativas** (`/ingesta`, `/reportes`, `/kpis-prod`, `/health`); **nunca**
   hardcodear `http://localhost:8000` en el código del front (eso lo resuelve el proxy/мismo origen).
3. El `StaticFiles` se monta en `/` **después** de los routers; condicionado a que `dist` exista.
4. Backend con **`uv`**; front con **`npm`**. Textos de UI y comentarios en **español**.
5. CORS limitado a los orígenes de Vite (`localhost:5173`, `127.0.0.1:5173`); no abrir `*`.
6. Orden secuencial. Si un paso falla, detente y reporta.

## 9. Fuera de alcance (NO hacer)

- Plotly / TanStack Table / export a Excel (el MVP usa tablas y barras Bootstrap).
- Autenticación / login (feature `auth` aparte).
- Filtros jerárquicos VP→Gerencia→Activo→Pozo.
- React Router / multi-página con rutas (MVP usa pestañas por estado en Zustand).
- Subida de `.xlsm` desde el navegador, SSE/WebSocket (el progreso es por polling).
- Dockerización / despliegue NSSM (queda para Ops).

---

## 11. Hallazgos de la re-auditoría (v1 → v2)

Auditoría audit-first (§0.2) del propio plan contra TS estricto, el template Vite 7/React 19 y el
arranque del backend.

| # | Severidad | Hallazgo | Corrección en v2 |
|---|---|---|---|
| **F1** | 🔴 Rompe build | `Object.fromEntries(...)` para el proxy infiere `(string\|obj)[][]`, no tuplas → `tsc -b` (parte de `npm run build`) lo rechaza. | §5.1: objeto literal explícito de proxy. |
| **F2** | 🟠 Fricción build | `main.tsx` con `import React`/`import ReactDOM` default choca con `verbatimModuleSyntax` del template. | §5.2: named imports `StrictMode`/`createRoot`. |
| **F3** | 🟠 UX validación | VF7 "Ingerir todos" lanzaría 37 archivos (16 NEW ~3–4 min c/u ≈ 1 h) en un smoke test. | §7 VF7: ingerir **un STD** seleccionado (segundos). |
| **F4** | 🟡 Robustez | `npx create-vite` sobre `frontend/` existente es interactivo (pide overwrite) → cuelga al executor. | §6.2: guarda `if (Test-Path frontend) { abort }`. |
| **F5** | 🟢 Verificado | Riesgo de que `StaticFiles` en `/` tapara la API/`/docs` o rompiera pytest sin build. | Sin cambio: el mount va **después** de los routers (orden de rutas) y bajo `if _DIST.is_dir()` (pytest sin build no monta nada). Coherente. |

**Coherencia de pipelines verificada:** (a) `main.py` solo **añade** CORS + StaticFiles; los routers
`ingesta/reportes/kpis-prod` y `/health` quedan intactos y se evalúan antes del mount. (b) `test_health.py`
sigue verde (el guard evita exigir `dist`). (c) El front llama rutas relativas → mismo código sirve en
dev (proxy) y prod (mismo origen). (d) Nada toca `etl/`, `data/`, `db/`, `.env`, ni las features del
backend → el pipeline de ingesta y la CLI siguen igual. **Versión de Node:** Vite 7 exige Node
≥20.19/22.12; `winget OpenJS.NodeJS.LTS` instala 22.x → cumple.

---

## 10. Prompt para el agente EXECUTOR (copiar tal cual)

```
Eres un agente EXECUTOR. Trabajas en c:\Users\user\Documents\Rep_Prod\.
Lee COMPLETO el plan Planes/plan_frontend_mvp_2026-06-18.md y ejecútalo AL PIE DE LA LETRA, en el orden de §6.

Reglas no negociables (§8):
- Instala Node LTS (§6.1) y refresca el PATH en la sesión antes de usar npm. Sin Node, DETENTE.
- NO toques etl/, data/, .env, CLAUDE.md, db/, ni features del backend salvo app/main.py.
- El front llama rutas RELATIVAS (/ingesta, /reportes, /kpis-prod, /health); nunca hardcodees http://localhost:8000 en el código del front.
- StaticFiles se monta en "/" DESPUÉS de los routers y solo si frontend/dist existe.
- Backend con uv, front con npm. Textos de UI y comentarios en español. CORS solo a localhost:5173.

Ejecuta los pasos 1–8 de §6. Luego corre VF1–VF6 (VF7 es manual, descríbela pero no la bloquees).
Si un paso o validación automática falla: DETENTE y reporta "❌ VFn/Paso n" con el error exacto.

Al terminar: árbol de archivos creados + tabla de resultados VF1–VF6 + "¿Hago commit?".
```
