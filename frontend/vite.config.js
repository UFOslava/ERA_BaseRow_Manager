import { defineConfig } from 'vite';
import { resolve } from 'path';

export default defineConfig({
  server: {
    port: 3000,
    host: '127.0.0.1'
  },
  build: {
    rollupOptions: {
      input: {
        main: resolve(import.meta.dirname, 'index.html'),
        settings: resolve(import.meta.dirname, 'settings.html'),
        relationMap: resolve(import.meta.dirname, 'relation-map.html'),
        manufacturers: resolve(import.meta.dirname, 'manufacturers.html')
      }
    }
  },
  test: {
    environment: 'jsdom',
    globals: true
  }
});
