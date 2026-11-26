import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  resolve: { alias: { '@': fileURLToPath(new URL('.', import.meta.url)) } },
  oxc: { jsx: { runtime: 'automatic' } },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./new-components/dashboard/test-setup.ts'],
    include: ['./new-components/financial-analysis/**/*.test.{ts,tsx}'],
    restoreMocks: true,
    clearMocks: true,
    testTimeout: 15000,
  },
});
