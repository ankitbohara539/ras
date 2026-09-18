import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  // Where the dev proxy forwards /api. Configurable because a stale uvicorn
  // can keep port 8000 bound on Windows -- two processes may hold the same
  // port, and the old one can win, which shows up as 404s on new endpoints.
  // Set VITE_API_PROXY_TARGET=http://localhost:8001 to route around it.
  const target = env.VITE_API_PROXY_TARGET || 'http://localhost:8000'

  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173,
      strictPort: true,
      proxy: {
        '/api': {
          target,
          changeOrigin: true,
        },
      },
    },
  }
})
