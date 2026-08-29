import { create } from 'zustand'

type Tab = 'ingesta' | 'reportes' | 'kpis'
interface UI { tab: Tab; jobActivo: number | null; setTab: (t: Tab) => void; setJob: (id: number | null) => void }

export const useUI = create<UI>((set) => ({
  tab: 'ingesta',
  jobActivo: null,
  setTab: (tab) => set({ tab }),
  setJob: (jobActivo) => set({ jobActivo }),
}))
