export default defineNuxtConfig({
  compatibilityDate: '2025-01-01',
  devtools: { enabled: true },
  modules: ['@nuxtjs/tailwindcss'],

  // Proxy WebSocket and REST API to FastAPI backend in dev
  nitro: {
    devProxy: {
      '/ws': {
        target: 'http://localhost:8000',
        ws: true,
        changeOrigin: true,
      },
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },

  runtimeConfig: {
    public: {
      // Override with NUXT_PUBLIC_API_BASE env var if needed
      apiBase: 'http://localhost:8000',
    },
  },

  app: {
    head: {
      title: 'VAI — AI VTuber',
      meta: [{ charset: 'utf-8' }, { name: 'viewport', content: 'width=device-width, initial-scale=1' }],
    },
  },
})
