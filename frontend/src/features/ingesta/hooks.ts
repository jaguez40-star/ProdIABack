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
