import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  // MapLibre loads its worker relative to its own module; pre-bundling breaks that path.
  optimizeDeps: { exclude: ['maplibre-gl'] },
  server: {
    host: true,
    proxy: {
      '/api': { target: process.env.API_URL ?? 'http://localhost:8000', timeout: 300_000 },
    },
  },
})
