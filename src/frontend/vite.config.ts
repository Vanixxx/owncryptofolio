import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// The frontend always calls /api/...; in development Vite forwards it to the backend,
// in the container both come from one origin. No CORS anywhere (ADR 0016).
export default defineConfig({
  // the ECharts chunk (~530 kB) loads only with an opened price chart
  build: { chunkSizeWarningLimit: 600 },
  plugins: [react(), tailwindcss()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    allowedHosts: true, // dev server in the LAN, reached by IP or Unraid hostname
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
  test: { environment: 'node' },
})
