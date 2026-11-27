import { fileURLToPath, URL } from 'node:url';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// Dentro do Compose o backend se chama "api". Fora dele, use API_URL (ou VITE_API_URL).
const alvoApi = process.env.API_URL || process.env.VITE_API_URL || 'http://api:8000';

export default defineConfig({
    plugins: [react()],
    resolve: {
        alias: {
            '@': fileURLToPath(new URL('./src', import.meta.url)),
        },
    },
    server: {
        host: '0.0.0.0',
        port: 5173,
        proxy: {
            '/api': {
                target: alvoApi.replace(/\/$/, ''),
                changeOrigin: true,
            },
        },
    },
    preview: {
        proxy: {
            '/api': {
                target: alvoApi.replace(/\/$/, ''),
                changeOrigin: true,
            },
        },
    },
});
