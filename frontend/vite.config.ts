import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  // Where the dev proxy forwards /api. Configurable because a stale uvicorn
  // can keep port 8000 bound on Windows -- two processes may hold the same
  // port, and the old one can win, which shows up as 404s on new endpoints.
  // Set VITE_API_PROXY_TARGET=http://localhost:8001 to route around it.
  const target = env.VITE_API_PROXY_TARGET || 'http://localhost:8000'

  return {
    plugins: [
      react(),
      tailwindcss(),
      VitePWA({
        registerType: 'prompt',
        includeAssets: ['favicon.ico', 'apple-touch-icon.png'],

        manifest: {
          name: 'Sahayatri — Civic Reporting',
          short_name: 'Sahayatri',
          description:
            'Report local civic issues, track them to resolution, and reach emergency services.',
          lang: 'ne',
          dir: 'ltr',
          start_url: '/',
          scope: '/',
          display: 'standalone',
          orientation: 'portrait',
          background_color: '#FFFFFF',
          theme_color: '#1D293D',
          categories: ['government', 'utilities', 'social'],
          icons: [
            { src: '/icon-192.png', sizes: '192x192', type: 'image/png' },
            { src: '/icon-512.png', sizes: '512x512', type: 'image/png' },
            {
              src: '/icon-maskable-512.png',
              sizes: '512x512',
              type: 'image/png',
              purpose: 'maskable',
            },
          ],
          // Long-press the installed icon to jump straight to these.
          shortcuts: [
            {
              name: 'Report an issue',
              short_name: 'Report',
              url: '/report',
              icons: [{ src: '/icon-192.png', sizes: '192x192' }],
            },
            {
              name: 'Emergency SOS',
              short_name: 'SOS',
              url: '/sos',
              icons: [{ src: '/icon-192.png', sizes: '192x192' }],
            },
            {
              name: 'Civic services',
              short_name: 'Services',
              url: '/services',
              icons: [{ src: '/icon-192.png', sizes: '192x192' }],
            },
          ],
        },

        workbox: {
          globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
          navigateFallback: '/index.html',
          // Never let the shell swallow API calls.
          navigateFallbackDenylist: [/^\/api\//, /^\/docs\//],
          cleanupOutdatedCaches: true,

          runtimeCaching: [
            {
              // Emergency contacts are the one thing that must survive a dead
              // network -- that is precisely when someone needs a hospital
              // number. Serve from cache instantly, refresh in the background.
              urlPattern: /\/api\/services(\?.*)?$/,
              handler: 'StaleWhileRevalidate',
              options: {
                cacheName: 'civic-services',
                expiration: { maxEntries: 40, maxAgeSeconds: 60 * 60 * 24 * 30 },
                cacheableResponse: { statuses: [200] },
              },
            },
            {
              // Reference data changes almost never and the report form is
              // unusable without it.
              urlPattern: /\/api\/(categories|municipalities)(\/.*)?$/,
              handler: 'StaleWhileRevalidate',
              options: {
                cacheName: 'reference-data',
                expiration: { maxEntries: 30, maxAgeSeconds: 60 * 60 * 24 * 30 },
                cacheableResponse: { statuses: [200] },
              },
            },
            {
              // Everything else under /api is authenticated, per-user and
              // changes constantly: tickets, notifications, SOS, alerts,
              // duplicate suggestions. Caching any of it risks showing one
              // user another user's data from disk, or a resolved ticket as
              // still open. Always hit the network.
              urlPattern: /\/api\//,
              handler: 'NetworkOnly',
            },
          ],
        },

        devOptions: {
          // Lets you exercise install and offline behaviour with `npm run dev`
          // instead of only in a production build.
          enabled: true,
          type: 'module',
        },
      }),
    ],

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

    // `vite preview` does not inherit server.proxy, and the production build
    // is the only way to exercise the service worker and the install flow.
    // Without this, previewing the PWA means every API call 404s.
    preview: {
      port: 4173,
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
