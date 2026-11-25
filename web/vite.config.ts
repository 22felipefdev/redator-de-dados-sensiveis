import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Dentro do Compose o backend se chama "api". Fora dele, use API_URL.
const alvoApi = process.env.API_URL || 'http://api:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: alvoApi,
        changeOrigin: true,
      },
    },
  },
})
