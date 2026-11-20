import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  resolve: { alias: { '@': fileURLToPath(new URL('.', import.meta.url)) } },
  oxc: { jsx: { runtime: 'automatic' } },
  test: {
    environment: 'jsdom',
    setupFiles: ['./new-components/dashboard/test-setup.ts'],
    include: ['./components/database/*.test.tsx'],
    restoreMocks: true,
    clearMocks: true,
    testTimeout: 15000,
  },
});
