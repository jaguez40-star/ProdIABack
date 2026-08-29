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
