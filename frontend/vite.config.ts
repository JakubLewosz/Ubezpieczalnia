import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    watch: { ignored: ['**/playwright-report/**', '**/test-results/**'] },
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: Object.fromEntries(
      ['/api', '/admin', '/static'].map((path) => [
        path,
        {
          target:
            process.env.VITE_API_PROXY_TARGET ||
            process.env.API_PROXY_TARGET ||
            'http://127.0.0.1:8000',
          changeOrigin: false,
        },
      ]),
    ),
  },
  preview: { host: '127.0.0.1', port: 5173, strictPort: true },
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    include: ['tests/**/*.test.{ts,tsx}'],
    restoreMocks: true,
  },
});
