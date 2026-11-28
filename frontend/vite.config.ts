/// <reference types="vitest/config" />
import path from 'node:path'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Vite: https://vite.dev/config/ · Tailwind CSS v4: https://tailwindcss.com/docs/installation/using-vite
// shadcn alias: https://ui.shadcn.com/docs/installation/vite
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  server: {
    // Same origin in development: the httpOnly session cookie, the CSRF header and every response
    // header (X-Request-ID, Content-Disposition) work without loosening the API's CORS.
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}'],
  },
})
