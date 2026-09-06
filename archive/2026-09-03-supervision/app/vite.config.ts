import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const API_PROXY_TARGET = 'http://localhost:8020';

// https://vitejs.dev/config/
export default defineConfig({
  base: '/app/',
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    // Listen on all interfaces and allow the Android emulator host alias
    // (10.0.2.2) so the WebView control app can reach the dev server.
    host: true,
    allowedHosts: true,
    proxy: {
      '/control': {
        target: API_PROXY_TARGET,
        changeOrigin: true,
        // The backend mounts the control API at /v1/control/... (prefix stripped
        // by nginx in prod). In dev we strip the leading /control ourselves.
        rewrite: (path) => path.replace(/^\/control/, ''),
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
});
