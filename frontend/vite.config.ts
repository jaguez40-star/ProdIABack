import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Proxy de DEV: el front llama rutas relativas (/ingesta, /reportes, /kpis-prod, /health) y Vite las
// reenvía al backend en :5030 → evita CORS. En PROD el front se sirve desde FastAPI (mismo origen).
// F1: objeto literal explícito (no Object.fromEntries) para no fallar `tsc -b` con tipos no-tupla.
const target = 'http://localhost:5030'
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
