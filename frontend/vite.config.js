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
        main: resolve(__dirname, 'index.html'),
        settings: resolve(__dirname, 'settings.html'),
        relationMap: resolve(__dirname, 'relation-map.html'),
        manufacturers: resolve(__dirname, 'manufacturers.html')
      }
    }
  },
  test: {
    environment: 'jsdom',
    globals: true
  }
});
