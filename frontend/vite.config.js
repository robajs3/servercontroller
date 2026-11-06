import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Build trafia do app/static/spa (serwuje go Flask). Dev: `npm run dev` + proxy do panelu na :8000
// (uruchom backend z COOKIE_SECURE=0).
export default defineConfig({
  plugins: [react()],
  base: '/static/spa/',
  build: { outDir: 'dist', emptyOutDir: true, sourcemap: false },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/camera': 'http://127.0.0.1:8000',
      '/sw.js': 'http://127.0.0.1:8000',
      '/manifest.webmanifest': 'http://127.0.0.1:8000',
      '/static/pwa': 'http://127.0.0.1:8000',
    },
  },
});
