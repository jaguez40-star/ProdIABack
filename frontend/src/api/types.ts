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
