import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import { fileURLToPath, URL } from 'node:url'

/**
 * El navegador solo habla con el backend Kotlin (`01_backend`, puerto 8082):
 * Vite le reenvía todo `/api`. El worker (8102) nunca se expone.
 *
 * Puerto 5175 fijo: el 5173 es de manuales-modulo y el 5174 de Monetización,
 * y los tres pueden correr a la vez. `strictPort` evita que Vite salte a otro
 * puerto en silencio (el backend solo admite CORS desde el 5175).
 */
// RADAR_BACKEND solo para probar contra otra copia (p. ej. una base de prueba en otro puerto).
const BACKEND = process.env.RADAR_BACKEND ?? 'http://localhost:8082'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: 5175,
    strictPort: true,
    proxy: {
      '/api': { target: BACKEND, changeOrigin: true },
    },
  },
  preview: {
    port: 5175,
    strictPort: true,
    proxy: {
      '/api': { target: BACKEND, changeOrigin: true },
    },
  },
})
